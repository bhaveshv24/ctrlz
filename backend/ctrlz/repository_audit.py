"""Bounded, read-only source inspection. Never imports or executes uploaded code."""
import ast
import json
import re
import tomllib
from pathlib import Path
import httpx
from packaging.requirements import Requirement
from .repository import SKIP_DIRS, sensitive

MAX_PACKAGES = 200


def source_review(root):
    findings, syntax, checked = [], [], 0
    def finding(path, line, rule, message):
        if len(findings) < 100:
            findings.append({'path':path,'line':line,'rule':rule,'severity':'warning','message':message,'confidence':'potential risk; review data flow and intended behavior'})
    for file in sorted(root.rglob('*')):
        rel = file.relative_to(root)
        if not file.is_file() or file.is_symlink() or any(p in SKIP_DIRS for p in rel.parts) or sensitive(rel.as_posix()):continue
        if file.suffix not in {'.py','.js','.jsx','.mjs','.cjs','.ts','.tsx'}:continue
        if file.stat().st_size > 256000:continue
        checked += 1
        text = file.read_text(encoding='utf-8', errors='replace')
        path = rel.as_posix()
        if file.suffix == '.py':
            try:tree = ast.parse(text, filename=path)
            except SyntaxError as exc:
                syntax.append({'path':path,'line':exc.lineno,'message':exc.msg})
                continue
            aliases = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for item in node.names:aliases[item.asname or item.name] = item.name
                elif isinstance(node, ast.ImportFrom):
                    for item in node.names:aliases[item.asname or item.name] = (node.module or '')+'.'+item.name
            def name(node):
                if isinstance(node,ast.Name):return aliases.get(node.id,node.id)
                if isinstance(node,ast.Attribute):return name(node.value)+'.'+node.attr
                return ''
            for node in ast.walk(tree):
                if isinstance(node,ast.Call):
                    call = name(node.func)
                    if call in {'eval','exec','builtins.eval','builtins.exec'}:
                        finding(path,node.lineno,'dynamic-code','Dynamic code evaluation can execute untrusted input.')
                    if call in {'pickle.load','pickle.loads','dill.load','dill.loads','yaml.unsafe_load'}:
                        finding(path,node.lineno,'unsafe-deserialization','Deserializing untrusted content can execute code.')
                    if call == 'yaml.load' and not any(k.arg=='Loader' and name(k.value) in {'yaml.SafeLoader','yaml.CSafeLoader'} for k in node.keywords):
                        finding(path,node.lineno,'unsafe-yaml','Use a safe YAML loader for untrusted input.')
                    if call in {'os.system','os.popen'}:
                        finding(path,node.lineno,'shell-execution','Shell commands need review for untrusted command input.')
                    if call.startswith('subprocess.') and any(k.arg=='shell' and isinstance(k.value,ast.Constant) and k.value.value is True for k in node.keywords):
                        finding(path,node.lineno,'shell-execution','Shell execution requires strict control of command input.')
                    if any(k.arg=='verify' and isinstance(k.value,ast.Constant) and k.value.value is False for k in node.keywords):
                        finding(path,node.lineno,'tls-verification-disabled','TLS certificate verification is disabled.')
                    if call.endswith(('.execute','.executemany')) and node.args and isinstance(node.args[0], (ast.JoinedStr, ast.BinOp)):
                        finding(path,node.lineno,'constructed-sql','Constructed SQL needs review; prefer bound parameters for user input.')
        else:
            patterns = [(r'\beval\s*\(', 'dynamic-code','Dynamic code evaluation needs an input trust review.'),
                (r'\bnew\s+Function\s*\(', 'dynamic-code','Generated functions can execute untrusted input.'),
                (r'\.innerHTML\s*=', 'html-injection','HTML assignment needs review for untrusted content.'),
                (r'rejectUnauthorized\s*:\s*false', 'tls-verification-disabled','TLS certificate verification is disabled.')]
            for pattern, rule, message in patterns:
                for match in re.finditer(pattern,text):finding(path,text.count('\n',0,match.start())+1,rule,message)
        for line, value in enumerate(text.splitlines(),1):
            # Report location only: never echo a possible secret into a report.
            if re.search(r'''(?i)\b(?:api_key|secret_key|password|access_token)\s*[:=]\s*["'][^"'\s]{12,}["']''',value):
                finding(path,line,'embedded-credential','Possible embedded credential. Use server-side configuration and review whether rotation is needed.')
    return {'state':'findings' if findings or syntax else 'no_findings','files_checked':checked,'findings':findings,'syntax_errors':syntax,
        'limitations':['Targeted Python AST and JavaScript/TypeScript pattern checks, not a comprehensive security audit.', 'Source files larger than 256 KiB are skipped; findings are capped at 100. Unsupported languages are not scanned.', 'No JavaScript/TypeScript compiler, full data-flow, authentication logic or penetration testing is performed by static checks.', 'No finding is proof of safety; runtime behavior requires tests.']}


def _manifest_inventory(root):
    packages, gaps = set(), []
    lock = root/'package-lock.json'
    if lock.is_file():
        try:
            data = json.loads(lock.read_text(encoding='utf-8'))
            entries = data.get('packages')
            if not isinstance(entries,dict):gaps.append('Legacy npm lockfile format is not covered.')
            else:
                for path, item in entries.items():
                    if 'node_modules/' not in path or not isinstance(item,dict):continue
                    version = item.get('version','')
                    name = item.get('name') or path.rsplit('node_modules/',1)[1]
                    if isinstance(name,str) and isinstance(version,str) and re.fullmatch(r'\d[^\s/]*',version) and not item.get('link'):packages.add(('npm',name,version))
        except (ValueError,OSError):gaps.append('npm lockfile could not be read.')
    elif (root/'package.json').is_file():gaps.append('npm dependencies need package-lock.json with resolved versions.')
    uv = root/'uv.lock'
    if uv.is_file():
        try:
            entries = tomllib.loads(uv.read_text(encoding='utf-8')).get('package',[])
            if not isinstance(entries,list):raise ValueError('Invalid package list')
            for item in entries:
                if not isinstance(item,dict) or not isinstance(item.get('source',{}),dict):raise ValueError('Invalid package entry')
                if item.get('source',{}).get('registry') and isinstance(item.get('version'),str) and isinstance(item.get('name'),str):packages.add(('PyPI',item['name'],item['version']))
        except (ValueError,OSError,KeyError):gaps.append('uv.lock could not be read.')
    req = root/'requirements.txt'
    if req.is_file() and not uv.is_file():
        for line in req.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):continue
            try:
                item = Requirement(line)
                pins = list(item.specifier)
                if not item.url and len(pins)==1 and pins[0].operator=='==' and '*' not in pins[0].version:
                    packages.add(('PyPI',item.name,pins[0].version))
                else:gaps.append('An unpinned or external Python requirement could not be checked.')
            except ValueError:gaps.append('A Python requirement could not be parsed.')
    if (root/'pyproject.toml').is_file() and not uv.is_file() and not req.is_file():gaps.append('Python dependency versions need uv.lock or pinned requirements.txt.')
    valid = {p for p in packages if len(p[1]) <= 214 and len(p[2]) <= 100 and re.fullmatch(r'[A-Za-z0-9_.@/-]+',p[1]) and re.fullmatch(r'[A-Za-z0-9_.+!-]+',p[2])}
    if len(valid)!=len(packages):gaps.append('Unsupported package identifiers or versions were excluded.')
    ordered = sorted(valid)
    if len(ordered)>MAX_PACKAGES:gaps.append(f'Only the first {MAX_PACKAGES} resolved packages were checked.')
    return ordered[:MAX_PACKAGES], sorted(set(gaps))


def dependency_inventory(root):
    names = {'package-lock.json','package.json','requirements.txt','pyproject.toml','uv.lock'}
    directories = sorted({p.parent for p in root.rglob('*') if p.is_file() and not p.is_symlink() and p.name in names and not any(part in SKIP_DIRS for part in p.relative_to(root).parts)})
    packages, gaps = set(), []
    if len(directories)>50:gaps.append('Only the first 50 dependency directories were inspected.')
    for directory in directories[:50]:
        items, missing = _manifest_inventory(directory)
        packages.update(items)
        prefix = directory.relative_to(root).as_posix()
        gaps.extend(prefix+': '+message for message in missing)
    if len(packages)>MAX_PACKAGES:gaps.append(f'Only the first {MAX_PACKAGES} resolved packages across the snapshot were checked.')
    return sorted(packages)[:MAX_PACKAGES], sorted(set(gaps))


async def dependency_review(root, client):
    packages, gaps = dependency_inventory(root)
    result = {'state':'not_checked','packages_checked':0,'findings':[],'coverage_gaps':gaps,
        'provider':'OSV','privacy':'Only package names, ecosystems and resolved versions are sent to OSV. Source and credentials are not sent.'}
    if not packages:
        result['detail']='No supported resolved dependency versions were found.'
        return result
    try:
        response = await client.post('https://api.osv.dev/v1/querybatch',json={'queries':[{'package':{'ecosystem':ecosystem,'name':name},'version':version} for ecosystem,name,version in packages]},timeout=12,follow_redirects=False)
        response.raise_for_status()
        rows = response.json()['results']
        if not isinstance(rows,list) or len(rows)!=len(packages):raise ValueError('Incomplete advisory response')
        for (ecosystem,name,version), row in zip(packages,rows):
            if not isinstance(row,dict) or row.get('error'):raise ValueError('Invalid advisory response')
            if row.get('next_page_token'):gaps.append('Additional advisory pages were not retrieved; results are partial.')
            for item in row.get('vulns',[]):
                advisory = item.get('id','')
                if not isinstance(advisory,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}',advisory):continue
                if len(result['findings'])<100:result['findings'].append({'package':name,'version':version,'ecosystem':ecosystem,'advisory':advisory,'url':'https://osv.dev/vulnerability/'+advisory})
                else:gaps.append('Advisory display is capped at 100 findings.')
        result.update(state='findings' if result['findings'] else 'no_known_advisories',packages_checked=len(packages),coverage_gaps=sorted(set(gaps)))
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        result.update(state='unavailable',detail='The advisory service could not complete this check. Dependency security remains unknown.')
    return result


async def inspect_all(runner, request, execution_enabled, client):
    import asyncio
    import time
    from .repository import inspect_repository, git
    repo = await asyncio.to_thread(runner.repository, request.repository)
    assessment = await asyncio.to_thread(inspect_repository, repo, request.acceptance_profile)
    source, dependencies = await asyncio.gather(asyncio.to_thread(source_review, repo), dependency_review(repo, client))
    diagnosis = {'status':'blocked','passed':0,'failed':0,'skipped':0,
        'baseline':{'cases':[],'output':'Tests were not executed.','exit_code':None},
        'message':'Static inspection complete. Runtime tests were not executed.'}
    tests = {'state':'not_run','reason':'No supported test runner was detected.'}
    if not execution_enabled:
        tests['reason']='This host has no enabled isolated runner. Source and dependency checks still ran.'
    elif assessment['supported']:
        try:
            diagnosis = await asyncio.to_thread(runner.diagnose, request)
            tests = {'state':diagnosis['status'],'reason':diagnosis['message']}
        except (ValueError,RuntimeError,OSError):
            tests = {'state':'unavailable','reason':'Isolated tests could not run. Check Docker images, dependency setup and runner availability.'}
    issues = bool(source['findings'] or source['syntax_errors'] or dependencies['findings'])
    review = issues or tests['state'] != 'healthy' or dependencies['state'] in {'not_checked','unavailable'} or bool(dependencies['coverage_gaps'])
    diagnosis['inspection'] = {'version':1,'commit':await asyncio.to_thread(git,['rev-parse','HEAD'],repo),'checked_at':time.time(),
        'summary':'review_required' if review else 'checks_passed_with_limits','source':source,'dependencies':dependencies,
        'tests':tests,'health':{'state':'attention_needed' if review else 'checks_passed_with_limits','profile':assessment['profile_label'],'test_files':assessment['test_file_count'],'warnings':assessment['warnings'],
        'scope':'Repository readiness and isolated tests, not deployed uptime or a guarantee of security.'}}
    if issues and diagnosis['status']=='healthy':diagnosis['message']='Existing tests passed. Source or dependency findings need review.'
    return diagnosis

"""Bounded inert source capture. Uses read-only Git objects or REST; never clones or commits."""
import ast
import base64
import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import Path
from urllib.parse import quote
from .github import normalize_github
from .repository import relative_path, sensitive, SKIP_DIRS, test_file, git
from .runtime_security import Redactor

MAX_FILES=120
MAX_BYTES=1024*1024


def tree_digest(files):
    return hashlib.sha256(json.dumps({p:hashlib.sha256(v.encode()).hexdigest() for p,v in sorted(files.items())},sort_keys=True).encode()).hexdigest()


def allowed(path):
    p=relative_path(path)
    return not sensitive(path) and not any(x in SKIP_DIRS or x.startswith('.') for x in p.parts) and (p.suffix in {'.py','.js','.mjs','.ts','.tsx','.json','.toml','.txt'} or p.name=='README.md')


def bounded(files):
    if not files or len(files)>MAX_FILES or sum(len(v.encode()) for v in files.values())>MAX_BYTES:
        raise ValueError('Audit source must contain 1–120 safe files within 1 MiB')
    for path,value in files.items():
        if not allowed(path) or len(value.encode())>65536:raise ValueError('Unsafe or oversized audit source')
    return files


def unzip(raw):
    if len(raw)>2*1024*1024:raise ValueError('Audit ZIP limit is 2 MiB')
    files={};total=0
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.infolist())>300:raise ValueError('Too many archive entries')
        for entry in z.infolist():
            relative_path(entry.orig_filename)
            relative_path(entry.filename)
            mode=entry.external_attr>>16
            if stat.S_ISLNK(mode) or mode and stat.S_IFMT(mode) not in {0,stat.S_IFREG,stat.S_IFDIR}:raise ValueError('Special archive file rejected')
            total+=entry.file_size
            if total>MAX_BYTES:raise ValueError('Expanded audit ZIP exceeds 1 MiB')
            if entry.is_dir() or not allowed(entry.filename):continue
            if entry.filename in files:raise ValueError('Duplicate archive path')
            files[entry.filename]=z.read(entry).decode('utf-8')
    return bounded(files)


async def capture(source,config,deployment):
    sha=deployment.commit_sha
    if not sha:raise ValueError('An exact deployment commit is required; upload a snapshot for an explicitly uncertain revision instead')
    repo=normalize_github(config.github_url)
    local=source.local_repositories.get(repo['full_name'])
    if local:
        root=Path(local).resolve()
        actual=normalize_github(git(['config','--get','remote.origin.url'],root))
        if actual['full_name'].lower()!=repo['full_name'].lower():raise ValueError('Repository identity mismatch')
        if git(['rev-parse','--verify',sha+'^{commit}'],root)!=sha:raise ValueError('Commit mismatch')
        paths=git(['ls-tree','-r','--name-only',sha],root).splitlines()
        def read(path):return git(['show',sha+':'+path],root)
        files={}
        for path in paths:
            if not allowed(path):continue
            if len(files)>=MAX_FILES:break
            if int(git(['cat-file','-s',sha+':'+path],root))<=65536:files[path]=read(path)
        return bounded(files),sha,'Verified read-only local Git object; publication not asserted'
    base='/repos/'+repo['full_name']
    commit,error=await source.get('api.github.com',base+'/commits/'+sha,source.github_token)
    if error or not isinstance(commit,dict) or commit.get('sha')!=sha:raise ValueError('Exact repository revision unavailable: '+str(error or 'commit mismatch'))
    tree,error=await source.get('api.github.com',base+'/git/trees/'+sha+'?recursive=1',source.github_token)
    if error or not isinstance(tree,dict) or tree.get('truncated'):raise ValueError('Bounded repository tree unavailable')
    entries=[e for e in tree.get('tree',[]) if e.get('type')=='blob' and e.get('mode')!='120000' and e.get('size',65537)<=65536 and allowed(e['path'])]
    # Prefer source/models/tests over dependency lockfiles; enforce a bounded REST budget.
    entries.sort(key=lambda e:(e['path'].endswith('lock.json'),not e['path'].endswith('.py'),not test_file(e['path']),e['path']))
    files={}
    for entry in entries[:32]:
        blob,error=await source.get('api.github.com',base+'/contents/'+quote(entry['path'],safe='/')+'?ref='+sha,source.github_token)
        if error or not isinstance(blob,dict) or blob.get('encoding')!='base64':continue
        files[entry['path']]=base64.b64decode(blob['content']).decode('utf-8')
    return bounded(files),sha,'GitHub exact commit; up to 32 bounded files, not complete repository coverage'


def inspect(files):
    snippets=[];anchors=[];gaps=[];languages=set();candidates=[]
    redactor=Redactor()
    for path,content in files.items():
        if path.endswith('.py'):
            languages.add('python')
            try:tree=ast.parse(content)
            except SyntaxError:continue
            for node in ast.walk(tree):
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and not test_file(path):
                    anchors.append({'path':path,'function':node.name,'line':node.lineno,'end_line':node.end_lineno,'async':isinstance(node,ast.AsyncFunctionDef),'generator':any(isinstance(n,(ast.Yield,ast.YieldFrom)) for n in ast.walk(node)),'arguments':[a.arg for a in node.args.args]})
                    if not node.decorator_list:
                        keys={k.value for n in ast.walk(node) if isinstance(n,ast.Dict) for k in n.keys if isinstance(k,ast.Constant) and isinstance(k.value,str)}
                        if 'id' in keys:
                            fields={'instance_id':'result.id'}
                            for key in ['resource_id','user_id','request_id','trace_id']:
                                if key in keys:fields[key]='result.'+key
                            candidates.append({'path':path,'function':node.name,'role':'start','fields':fields,'completion_key':None,'completion_value':None})
                        identifiers=[arg.arg for arg in node.args.args if arg.arg.endswith(('_id',)) and not re.search('user|trace|request',arg.arg)]
                        strings=[n.value for n in ast.walk(node) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
                        completed=next((x for x in ['completed','done'] if x in strings),None)
                        if len(identifiers)==1 and completed and any('status' in x for x in strings):
                            candidates.append({'path':path,'function':node.name,'role':'complete','fields':{'instance_id':'arg.'+identifiers[0]},'completion_key':'result.status','completion_value':completed})
                if isinstance(node,ast.ExceptHandler) and node.body and all(isinstance(n,(ast.Pass,ast.Return,ast.Continue)) for n in node.body):gaps.append({'path':path,'line':node.lineno,'observation':'Exception handler has no explicit log/raise in its body; intent requires review'})
        elif path.endswith(('.js','.ts','.mjs','.tsx')):languages.add('javascript/typescript')
        if path.endswith(('.py','.js','.ts','.mjs','.tsx','.toml','.json')) and not path.endswith('lock.json'):
            lines=content.splitlines()
            # Bounded beginning plus keyword context, retaining real line references.
            selected=set(range(min(60,len(lines))))
            for n,line in enumerate(lines):
                if re.search(r'job|queue|task|commit|paid|complete|pending|except|catch|emit|trace',line,re.I):selected.update(range(max(0,n-3),min(len(lines),n+5)))
            snippets.append({'path':path,'lines':[{ 'line':n+1,'text':redactor.text(lines[n])} for n in sorted(selected)[:180]],'test':test_file(path)})
    return {'languages':sorted(languages),'anchors':anchors[:150],'hook_candidates':candidates[:30],'static_observations':gaps[:30],'snippets':snippets[:30],'limits':['Static inspection is partial and does not prove all failure paths.','Hook candidates are syntactic suggestions, not verified business rules. Verify return shapes and completion meaning in source/tests.','Python function instrumentation is supported; JavaScript/TypeScript audit is advisory, not patchable in this release.']}


def validate_rule(rule,files,context):
    for loc in rule.evidence:
        if loc.path not in files or loc.line>len(files[loc.path].splitlines()):raise ValueError('Unknown source evidence location')
    anchors={(a['path'],a['function']):a for a in context['anchors']}
    if rule.instrumentation_driver=='campuspass_committed_session':
        needed=['backend/campuspass/main.py','backend/campuspass/db.py','backend/campuspass/worker.py']
        if not all(p in files for p in needed) or ('backend/campuspass/main.py','create_app') not in anchors:raise ValueError('Committed-session driver requires the verified CampusPass source layout')
        if rule.hooks:raise ValueError('Session driver uses fixed audited model events, not arbitrary function hooks')
    for hook in rule.hooks:
        anchor=anchors.get((hook.path,hook.function))
        if not anchor or anchor['generator'] or not hook.path.endswith('.py'):raise ValueError('Unsupported instrumentation anchor')
        if test_file(hook.path):raise ValueError('Tests are immutable')
        for value in hook.fields.values():
            if value.startswith('arg.') and value.split('.')[1] not in anchor['arguments']:raise ValueError('Unknown argument correlation field')
    return rule

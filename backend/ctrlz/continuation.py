import asyncio
import ast
import hashlib
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from pydantic import ValidationError
from .models import ImportRequest
from .repository import editable, git, inspect_repository, relative_path
from .sandbox import Sandbox
from .code_tournament import CodeTournament


def command(args, cwd=None, timeout=60):
    if args[0] != 'git':
        raise ValueError('Only named Git operations are available')
    return git(args[1:], cwd, timeout)


def validate_path(root: Path, relative: str):
    root = root.resolve(); path = relative_path(relative)
    if not editable(relative):
        raise ValueError('Only bounded product source files may change; tests, configuration and manifests are immutable')
    target = root.joinpath(*path.parts); current = root
    for part in path.parts:
        current = current/part
        if current.is_symlink():
            raise ValueError('Symlink source paths are forbidden')
    if not target.resolve().is_relative_to(root):
        raise ValueError('Source escapes workspace')
    return target


def immutable_digest(root, paths, protected=()):
    hashes = {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths if not editable(p) or p in protected}
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


def embedded_doctests(root, paths):
    result = {}
    for name in paths:
        if Path(name).suffix != '.py' or not editable(name):continue
        try:tree = ast.parse((root/name).read_text())
        except (SyntaxError,UnicodeError,OSError):
            result[name]=[]
            continue
        docs = [ast.get_docstring(node, clean=False) for node in ast.walk(tree) if isinstance(node,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef))]
        result[name] = [doc for doc in docs if doc and '>>>' in doc]
    return result


def acceptance(baseline, candidate, immutable):
    before, after = baseline['cases'], candidate['cases']
    same_ids = Counter(c['id'] for c in before) == Counter(c['id'] for c in after)
    collection_failure = baseline['exit_code'] == 2 or any(text in baseline['output'] for text in ['SyntaxError', 'ERR_MODULE_NOT_FOUND', 'ImportError while importing'])
    original_skips = Counter(c['id'] for c in before if c.get('status') == 'skipped')
    new_skips = Counter(c['id'] for c in after if c.get('status') == 'skipped')
    skips_preserved = all(number <= original_skips[name] for name, number in new_skips.items())
    passed_cases = sum(c['passed'] for c in after)
    all_required = passed_cases > 0 and all(c['passed'] or c.get('status') == 'skipped' for c in after) and skips_preserved
    checks = {'candidate_tests': candidate['exit_code'] == 0, 'regression_proven': baseline['exit_code'] in {1, 2}, 'same_acceptance_tests': immutable and (same_ids or collection_failure), 'all_required_cases_passed': all_required, 'no_new_skips': skips_preserved}
    return checks, {'collected_test_identities_preserved': same_ids, 'baseline_collection_failure': collection_failure, 'baseline_cases': len(before), 'candidate_cases': len(after), 'passed_cases': passed_cases}


class Continuation:
    def __init__(self, store, reasoner, root: Path, artifacts: Path, notifier=None):
        self.notifier = notifier
        self.store, self.reasoner = store, reasoner
        self.root, self.artifacts = root.resolve(), artifacts.resolve()
        self.root.mkdir(parents=True, exist_ok=True); self.artifacts.mkdir(parents=True, exist_ok=True)

    def repository(self, value):
        repo = Path(value).resolve()
        if not repo.is_relative_to(self.root) or repo == self.root:
            raise ValueError('Import the repository into the managed workspace first')
        if not (repo/'.git').exists():
            raise ValueError('Import requires a committed Git snapshot')
        if git(['status', '--porcelain'], repo):
            raise ValueError('Commit or re-import local changes before repair')
        return repo

    @staticmethod
    def sandbox(worktree):
        return Sandbox(worktree, 'python-pytest').run()

    async def run(self, incident_id, request: ImportRequest):
        reasoner = self.reasoner
        worktree = None; repo = None; added = False; sandbox = None
        try:
            self.store.update(incident_id, status='diagnosing', error=None, reasoning_provider=getattr(reasoner, 'provider', 'test fixture'), model=getattr(reasoner, 'selected_model', None))
            repo = await asyncio.to_thread(self.repository, request.repository)
            inspection = inspect_repository(repo, request.acceptance_profile)
            if not inspection['supported']:
                raise ValueError('Unsupported repair environment: '+'; '.join(inspection['warnings']))
            self.store.record(incident_id, 'repository_assessment', {k:v for k,v in inspection.items() if k != 'files'})
            self.store.update(incident_id, repair_profile=inspection['profile'])
            metadata = {}
            provenance = repo/'.git/ctrlz-import.json'
            if provenance.is_file():
                metadata = json.loads(provenance.read_text())
                self.store.record(incident_id, 'source_provenance', metadata)
            commit = git(['rev-parse', 'HEAD'], repo)
            worktree = Path(tempfile.mkdtemp(prefix='ctrlz-worktree-')).resolve()/'candidate'
            await asyncio.to_thread(git, ['worktree', 'add', '--detach', str(worktree), commit], repo)
            added = True; worktree.chmod(0o755)
            paths = git(['ls-files'], worktree).splitlines()
            for name in paths:
                target = worktree/name
                if target.is_symlink() or not target.resolve().is_relative_to(worktree.resolve()):
                    raise ValueError('Unsafe snapshot path')
                for directory in target.parents:
                    if directory == worktree.parent:break
                    directory.chmod(0o755)
                target.chmod(0o644)
            protected = set(inspection['tests'])
            immutable = immutable_digest(worktree, paths, protected)
            doctests = embedded_doctests(worktree, paths)
            sandbox = Sandbox(worktree, inspection['profile'], request.install_dependencies)
            dependency_report = await asyncio.to_thread(sandbox.prepare, inspection)
            self.store.record(incident_id, 'dependency_environment', dependency_report)
            if inspection['profile'] != 'python-pytest':
                (worktree/'node_modules').mkdir(exist_ok=True)
            baseline = await asyncio.to_thread(sandbox.run)
            self.store.record(incident_id, 'baseline_tests', baseline)
            if baseline['exit_code'] not in {1, 2} or not baseline['cases']:
                raise ValueError('The full baseline must reproduce a failing test or collection error; no verified regression is available')
            if inspection['profile'] == 'javascript-vitest':
                for case in baseline['cases']:
                    path = case['id'].split('::',1)[0].removeprefix('/workspace/')
                    if path in paths:protected.add(path)
                immutable = immutable_digest(worktree, paths, protected)
            def qualify(candidate):
                unchanged = immutable_digest(worktree, paths, protected) == immutable and embedded_doctests(worktree, paths) == doctests
                return acceptance(baseline,candidate,unchanged)
            tournament = CodeTournament(self.store,incident_id,repo,worktree,sandbox,baseline,protected,qualify)
            await tournament.retry()
            await tournament.compensate(metadata)
            initial = {}
            failed_ids = ' '.join(c['id'] for c in baseline['cases'] if not c['passed'])
            relevant_tests = [p for p in inspection['tests'] if Path(p).stem in failed_ids]
            failure_output = baseline.get('output', '')
            implicated_sources = [name for name in inspection['editable_files'] if name in failure_output]
            selected = implicated_sources+[p for p in paths if p in {'pyproject.toml', 'package.json', 'requirements.txt'}]+inspection['editable_files'][:3]+relevant_tests+inspection['tests'][:2]
            budget = 20000
            for name in dict.fromkeys(selected):
                text = (worktree/name).read_text(errors='replace')
                excerpt = text[:min(8000,budget)]
                if excerpt:initial[name] = excerpt
                budget -= len(excerpt)
                if budget <= 0:break
            self.store.record(incident_id, 'repository_context', {'commit':commit,'files':{name:{'excerpt_characters':len(text),'excerpt_sha256':hashlib.sha256(text.encode()).hexdigest()} for name,text in initial.items()}})
            feedback = None; originals = {}; new_files = set()
            agent_runs = 0
            passed = False
            checks = {'candidate_tests':False}
            details = {}
            diff = ''
            result = {'exit_code':4,'cases':[],'output':'No valid agent proposal'}
            agent_error = None
            for attempt in range(3):
                for name, original in originals.items():
                    target = worktree/name
                    if original is None:
                        target.unlink(missing_ok=True)
                    else:target.write_text(original)
                for name in new_files:
                    git(['reset', '--', name], worktree)
                originals = {}; new_files = set()
                self.store.update(incident_id, status='planning')
                context = {**baseline, 'profile': inspection['profile'], 'repository_tree': paths[:1000], 'previous_attempt': feedback, '_workspace': str(worktree), '_allowed_files': paths, '_record': lambda payload:self.store.record(incident_id,'tool_result',payload)}
                try:
                    proposal = await reasoner.code(request, initial, context)
                except ValidationError as exc:
                    feedback = {'attempt':attempt+1,'schema_error':str(exc)[:2000],'instruction':'Return the required path, before and after for every edit; preserve tests and source boundaries'}
                    self.store.record(incident_id,'code_proposal_rejected',feedback)
                    if attempt == 2:break
                    continue
                except Exception as exc:
                    agent_error = type(exc).__name__+': '+str(exc)[:300]
                    self.store.record(incident_id,'code_proposal_rejected',{'attempt':attempt+1,'error':agent_error})
                    break
                self.store.update(incident_id, requirement_assessment=[item.model_dump() for item in proposal.requirements], continuation_plan=proposal.continuation_plan)
                self.store.record(incident_id, 'code_proposal', {'attempt': attempt+1, **proposal.model_dump()})
                result = {'exit_code': 4, 'cases': [], 'output': 'Candidate not validated'}
                try:
                    replacements = {}
                    for change in proposal.changes:
                        validate_path(worktree, change.path)
                        if change.path in protected:raise ValueError('Acceptance test files are immutable')
                        if change.path in replacements:raise ValueError('Duplicate full-file replacement')
                        replacements[change.path] = change.content
                    for edit in proposal.edits:
                        target = validate_path(worktree, edit.path)
                        if edit.path in protected:raise ValueError('Acceptance test files are immutable')
                        text = replacements.get(edit.path, target.read_text() if target.is_file() else '')
                        if text.count(edit.before) != 1:
                            raise ValueError('Exact edit must match one and only one source occurrence')
                        replacements[edit.path] = text.replace(edit.before, edit.after, 1)
                    for name, content in replacements.items():
                        target = validate_path(worktree, name)
                        if len(content.encode()) > 256000 or '\x00' in content:
                            raise ValueError('Source change exceeds bounded text limits')
                        if target.suffix == '.py':ast.parse(content, filename=name)
                    for name, content in replacements.items():
                        target = validate_path(worktree, name)
                        originals[name] = target.read_text() if target.exists() else None
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(content); target.chmod(0o644)
                        for directory in target.parents:
                            if directory == worktree.parent:break
                            directory.chmod(0o755)
                        if name not in paths:
                            git(['add', '--intent-to-add', '--', name], worktree); new_files.add(name)
                    self.store.update(incident_id, status='verifying')
                    agent_runs += 1
                    result = await asyncio.to_thread(sandbox.run)
                except (SyntaxError, ValueError) as exc:
                    result['output'] = f'{type(exc).__name__}: {str(exc)[:600]}'
                diff = git(['diff', '--no-ext-diff', '--no-textconv'], worktree)
                unchanged = immutable_digest(worktree, paths, protected) == immutable and embedded_doctests(worktree, paths) == doctests
                checks, details = acceptance(baseline, result, unchanged)
                checks['nonempty_patch'] = bool(diff)
                passed = all(checks.values())
                self.store.record(incident_id, 'candidate_tests', {'attempt': attempt+1, 'passed': passed, 'acceptance': details, **result})
                if passed:break
                feedback = {'attempt': attempt+1, 'candidate': proposal.model_dump(), 'test_result': result, 'acceptance': details}
            tournament.agent(result,checks,details,diff,agent_runs,agent_error)
            winner = tournament.record()
            if winner:
                result, checks, details, diff = winner['result'], winner['checks'], winner['acceptance'], winner['patch']
                passed = True
            else:
                passed = False
            unchanged = immutable_digest(worktree,paths,protected)==immutable
            self.store.record(incident_id, 'verification', {**result, 'passed': passed, 'checks': checks, 'acceptance': details, 'original_commit': commit, 'tests_immutable': unchanged, 'selected_strategy':winner['id'] if winner else None})
            artifact = self.artifacts/f'{incident_id}.patch'; artifact.write_text(diff)
            self.store.update(incident_id, status='resolved' if passed else 'escalated', error=None if passed else 'No candidate passed the original acceptance suite within three attempts', verification={'passed':passed,'checks':checks}, patch=diff, commit=commit, remaining_risks=([winner['reason'],'Verified against the imported acceptance suite only; patch review and deployment remain operator actions.'] if winner else []) if passed else ['No verified repair; inspect the test evidence and unsupported requirements.'])
            self.store.record(incident_id, 'record', {'resolved':passed,'artifact':'patch','profile':inspection['profile']})
        except Exception as exc:
            self.store.update(incident_id, status='blocked' if any(word in str(exc).lower() for word in ['docker','dependency','dependencies','unsupported']) else 'escalated', error=f'Repository repair: {type(exc).__name__}: {str(exc)[:600] or "Reasoning exceeded its execution budget; retry when the provider is available"}')
            self.store.record(incident_id, 'continuation_failed', {'error_type':type(exc).__name__,'message':str(exc)[:600]})
        finally:
            if sandbox:
                try:await asyncio.to_thread(sandbox.close)
                except Exception as exc:self.store.record(incident_id,'sandbox_cleanup_required',{'reason':str(exc)[:200]})
            if worktree and repo:
                if added:
                    try:await asyncio.to_thread(git,['worktree','remove','--force',str(worktree)],repo)
                    except Exception:self.store.record(incident_id,'worktree_cleanup_required',{'worktree':str(worktree)})
                shutil.rmtree(worktree.parent,ignore_errors=True)
            if self.notifier and self.store.get(incident_id)["status"] in {"resolved", "blocked", "escalated"}:
                await self.notifier(incident_id)

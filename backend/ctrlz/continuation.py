import asyncio
import ast
import hashlib
import json
import re
import io
import zipfile
import zlib
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from pydantic import ValidationError
from .models import ImportRequest, CodeProposal, SourceEdit
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
        try:tree = ast.parse((root/name).read_text(encoding='utf-8'))
        except (SyntaxError,UnicodeError,OSError):
            result[name]=[]
            continue
        docs = [ast.get_docstring(node, clean=False) for node in ast.walk(tree) if isinstance(node,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef))]
        result[name] = [doc for doc in docs if doc and '>>>' in doc]
    return result


def preserve_rejection_guards(before, after, filename):
    if Path(filename).suffix != '.py':
        return
    def conditions(source):
        tree = ast.parse(source, filename=filename)
        signatures = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.If) or not any(isinstance(statement, ast.Raise) for statement in node.body):
                continue
            for comparison in ast.walk(node.test):
                if isinstance(comparison, ast.Compare) and any(isinstance(part, ast.Constant) and isinstance(part.value, str) for part in comparison.comparators):
                    signatures.append(ast.dump(ast.Tuple(elts=[comparison.left, *comparison.comparators], ctx=ast.Load())))
        return Counter(signatures)
    try:
        original = conditions(before)
    except SyntaxError:
        return
    candidate = conditions(after)
    if original - candidate:
        raise ValueError(f'{filename}: repair removes or changes a rejection precondition. Preserve the required state/value and fix the comparison without removing validation or substituting a blacklist.')


def guard_comparison_repairs(root, names, limit=4):
    groups = []
    for name in names:
        if Path(name).suffix != '.py':continue
        target = validate_path(root, name)
        if not target.is_file():continue
        source = target.read_text(encoding='utf-8')
        try:tree = ast.parse(source)
        except SyntaxError:continue
        proposals = []
        for branch in ast.walk(tree):
            if not isinstance(branch, ast.If) or not any(isinstance(statement, ast.Raise) for statement in branch.body):continue
            for node in ast.walk(branch.test):
                if not isinstance(node, ast.Compare) or len(node.ops) != 1 or not isinstance(node.left, (ast.Name, ast.Attribute)):continue
                if not isinstance(node.comparators[0], ast.Constant) or not isinstance(node.comparators[0].value, str):continue
                # Synthesize fail-closed required-state guards only. Never turn
                # a required-state rejection into a blacklist of that state.
                if not isinstance(node.ops[0], ast.Eq):continue
                before = ast.get_source_segment(source, node)
                if not before or source.count(before) != 1:continue
                old, new = '==', '!='
                proposals.append(CodeProposal(diagnosis='Evaluate a minimal rejection-guard comparison correction; preserve its required value and all other source.', edits=[SourceEdit(path=name, before=before, after=before.replace(old,new,1))]))
        if proposals:groups.append(proposals[:limit])
    # Cover distinct traceback files before spending the budget on more guards
    # from a large entry point that may only be forwarding another file's error.
    return [group[index] for index in range(limit) for group in groups if len(group) > index][:limit]


class EditMatchError(ValueError):
    def __init__(self, path, matches, source):
        super().__init__(f'{path}: before snippet matched {matches} source occurrences; exactly one is required. Read the original file and return a complete revised candidate.')
        self.path, self.source = path, source[:16000]


def proposal_sources(root, proposal, protected):
    replacements = {}
    for change in proposal.changes:
        validate_path(root, change.path)
        if change.path in protected:raise ValueError('Acceptance test files are immutable')
        if change.path in replacements:raise ValueError('Duplicate full-file replacement')
        replacements[change.path] = change.content
    for edit in proposal.edits:
        target = validate_path(root, edit.path)
        if edit.path in protected:raise ValueError('Acceptance test files are immutable')
        text = replacements.get(edit.path, target.read_text(encoding='utf-8') if target.is_file() else '')
        matches = text.count(edit.before)
        if matches != 1:
            raise EditMatchError(edit.path, matches, text)
        replacements[edit.path] = text.replace(edit.before, edit.after, 1)
    return replacements


def acceptance(baseline, candidate, immutable, mode='repair'):
    before, after = baseline['cases'], candidate['cases']
    same_ids = Counter(c['id'] for c in before) == Counter(c['id'] for c in after)
    collection_failure = baseline['exit_code'] == 2 or any(text in baseline['output'] for text in ['SyntaxError', 'ERR_MODULE_NOT_FOUND', 'ImportError while importing'])
    original_skips = Counter(c['id'] for c in before if c.get('status') == 'skipped')
    new_skips = Counter(c['id'] for c in after if c.get('status') == 'skipped')
    skips_preserved = all(number <= original_skips[name] for name, number in new_skips.items())
    passed_cases = sum(c['passed'] for c in after)
    all_required = passed_cases > 0 and all(c['passed'] or c.get('status') == 'skipped' for c in after) and skips_preserved
    checks = {'candidate_tests': candidate['exit_code'] == 0, 'regression_proven': baseline['exit_code'] in {1, 2}, 'same_acceptance_tests': immutable and (same_ids or collection_failure), 'all_required_cases_passed': all_required, 'no_new_skips': skips_preserved}
    if mode == 'complete':
        checks.pop('regression_proven')
        checks['baseline_established'] = baseline['exit_code'] in {0, 1, 2} and bool(before)
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

    def repaired_archive(self, incident):
        if not incident.get('verification', {}).get('passed') or not incident.get('patch'):
            raise ValueError('A verified source patch is required before downloading repaired code')
        repository = Path(incident['import_request']['repository']).resolve()
        if not repository.is_relative_to(self.root) or repository == self.root:
            raise ValueError('Repository is outside the managed workspace')
        key = hashlib.sha256(json.dumps([str(repository), incident.get('commit'), incident['patch']], ensure_ascii=True).encode()).hexdigest()
        cached = self.artifacts/(key+'.repaired.zip')
        if cached.is_file():
            try:
                contents = cached.read_bytes()
                with zipfile.ZipFile(io.BytesIO(contents)) as archive:
                    if archive.namelist() and archive.testzip() is None:
                        return contents
            except (OSError, zipfile.BadZipFile, EOFError, zlib.error, RuntimeError):
                pass
        repo = self.repository(incident['import_request']['repository'])
        with tempfile.TemporaryDirectory(prefix='ctrlz-export-') as directory:
            workspace = Path(directory)/'repository'
            git(['clone', '--no-hardlinks', '--no-local', str(repo), str(workspace)], repo)
            # Export the snapshot that passed verification, even if HEAD moved later.
            if incident.get('commit'):
                git(['checkout', '--detach', incident['commit']], workspace)
            patch = Path(directory)/'verified.patch'
            patch.write_bytes(incident['patch'].encode('utf-8'))
            git(['apply', '--check', '--ignore-space-change', str(patch)], workspace)
            # Windows checkout metadata/line endings can differ from the index.
            # Apply to the checked-out files, then stage the resulting snapshot.
            git(['apply', '--ignore-space-change', str(patch)], workspace)
            git(['add', '--all'], workspace)
            for name in git(['diff', '--cached', '--name-only', '-z'], workspace, raw=True).decode('utf-8').split('\0'):
                if not name:continue
                validate_path(workspace, name)
            output = io.BytesIO()
            export_root = workspace
            export_names = [name for name in git(['ls-files', '-z'], workspace, raw=True).decode('utf-8').split('\0') if name]
            metadata_path = repo/'.git/ctrlz-import.json'
            metadata = json.loads(metadata_path.read_text()) if metadata_path.is_file() else {}
            subdirectory = metadata.get('provenance', {}).get('subdirectory', '')
            if subdirectory:
                full_source = repo/'.git/ctrlz-full-source'
                if not full_source.is_dir():
                    raise ValueError('This older import retained only the selected package. Re-import the full repository to download all project files.')
                export_root = Path(directory)/'full-repository'
                shutil.copytree(full_source, export_root, symlinks=True)
                package = export_root.joinpath(*relative_path(subdirectory).parts)
                shutil.rmtree(package)
                shutil.copytree(workspace, package, ignore=shutil.ignore_patterns('.git'), symlinks=True)
                export_names = [p.relative_to(export_root).as_posix() for p in export_root.rglob('*') if p.is_file() or p.is_symlink()]
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name in export_names:
                    path = export_root.joinpath(*relative_path(name).parts)
                    if path.is_symlink() or not path.resolve().is_relative_to(export_root.resolve()):
                        raise ValueError('Unsafe export path')
                    archive.write(path, 'repaired-repository/'+name)
            contents = output.getvalue()
            # Publish the complete artifact atomically. Later downloads do not
            # need Git, a surviving import folder, or another patch application.
            with tempfile.NamedTemporaryFile(dir=self.artifacts, suffix='.tmp', delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(contents)
            try:
                temporary.replace(cached)
            finally:
                temporary.unlink(missing_ok=True)
            return contents

    def diagnose(self, request: ImportRequest):
        repo = self.repository(request.repository)
        inspection = inspect_repository(repo, request.acceptance_profile)
        if not inspection['supported']:
            raise ValueError('Unsupported test environment: '+'; '.join(inspection['warnings']))
        with tempfile.TemporaryDirectory(prefix='ctrlz-diagnose-') as directory:
            workspace = Path(directory)/'repository'
            shutil.copytree(repo, workspace, ignore=shutil.ignore_patterns('.git'), symlinks=True)
            Path(directory).chmod(0o755)
            for path in [workspace, *workspace.rglob('*')]:
                if path.is_symlink():
                    raise ValueError('Unsafe snapshot path')
                path.chmod(0o755 if path.is_dir() else 0o644)
            sandbox = Sandbox(workspace, inspection['profile'], request.install_dependencies)
            try:
                sandbox.prepare(inspection)
                if inspection['profile'] != 'python-pytest':
                    (workspace/'node_modules').mkdir(exist_ok=True)
                baseline = sandbox.run()
            finally:
                sandbox.close()
        cases = baseline['cases']
        repairable = baseline['exit_code'] in {1, 2} and bool(cases)
        healthy = baseline['exit_code'] == 0 and any(c['passed'] for c in cases)
        return {'status': 'failing' if repairable else 'healthy' if healthy else 'blocked',
                'baseline': baseline,
                'passed': sum(c['passed'] for c in cases),
                'failed': sum(c.get('status') in {'failed', 'error'} for c in cases),
                'skipped': sum(c.get('status') == 'skipped' for c in cases),
                'message': 'Failures reproduced. Ready to repair.' if repairable else
                           'The existing tests pass. No failing regression was detected.' if healthy else
                           'Tests could not establish a repairable baseline. Review the runner output.'}

    async def run(self, incident_id, request: ImportRequest):
        reasoner = self.reasoner
        worktree = None; repo = None; added = False; sandbox = None
        try:
            self.store.update(incident_id, status='diagnosing', error=None, import_request=request.model_dump(), download_ready=False, reasoning_provider=getattr(reasoner, 'provider', 'test fixture'), model=getattr(reasoner, 'selected_model', None))
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
            if baseline['exit_code'] not in ({0, 1, 2} if request.mode == 'complete' else {1, 2}) or not baseline['cases']:
                raise ValueError('Project completion requires a collected baseline test suite before source changes.' if request.mode == 'complete' else 'The full baseline must reproduce a failing test or collection error; no verified regression is available')
            if inspection['profile'] == 'javascript-vitest':
                for case in baseline['cases']:
                    path = case['id'].split('::',1)[0].removeprefix('/workspace/')
                    if path in paths:protected.add(path)
                immutable = immutable_digest(worktree, paths, protected)
            def qualify(candidate):
                unchanged = immutable_digest(worktree, paths, protected) == immutable and embedded_doctests(worktree, paths) == doctests
                return acceptance(baseline,candidate,unchanged,request.mode)
            tournament = CodeTournament(self.store,incident_id,repo,worktree,sandbox,baseline,protected,qualify)
            if request.mode == 'repair':
                await tournament.retry()
                await tournament.compensate(metadata)
            initial = {}
            failed_ids = ' '.join(c['id'] for c in baseline['cases'] if not c['passed'])
            relevant_tests = [p for p in inspection['tests'] if Path(p).stem in failed_ids]
            failure_output = baseline.get('output', '')
            implicated_sources = [name for name in inspection['editable_files'] if name in failure_output]
            implicated_sources.sort(key=lambda name:len(re.findall(re.escape(name)+r':\d+:\s+\w*(?:Error|Exception)', failure_output)), reverse=True)
            # Prioritize failing test context over unrelated source excerpts.
            selected = implicated_sources+relevant_tests+inspection['tests'][:2]+[p for p in paths if p in {'pyproject.toml', 'package.json', 'requirements.txt'}]+inspection['editable_files'][:3]
            budget = 42000
            for name in dict.fromkeys(selected):
                text = (worktree/name).read_text(encoding='utf-8', errors='replace')
                excerpt = text[:min(12000,budget)]
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
            repair_origin = None
            for attempt in range(3):
                for name, original in originals.items():
                    target = worktree/name
                    if original is None:
                        target.unlink(missing_ok=True)
                    else:target.write_bytes(original.encode('utf-8'))
                for name in new_files:
                    git(['reset', '--', name], worktree)
                originals = {}; new_files = set()
                self.store.update(incident_id, status='planning')
                context = {**baseline, 'mode':request.mode, 'profile': inspection['profile'], 'repository_tree': paths[:1000], 'previous_attempt': feedback, '_workspace': str(worktree), '_allowed_files': paths, '_record': lambda payload:self.store.record(incident_id,'tool_result',payload)}
                proposal = None
                for format_attempt in range(3):
                    proposal = None
                    context['previous_attempt'] = feedback
                    try:
                        proposal = await reasoner.code(request, initial, context)
                        replacements = proposal_sources(worktree, proposal, protected)
                        break
                    except EditMatchError as exc:
                        proposal = None
                        feedback = {**(feedback or {}), 'attempt':attempt+1, 'edit_error':str(exc), 'original_source':{'path':exc.path, 'content':exc.source}, 'instruction':'Do not repeat the rejected edit. Match the original source exactly once. Keep the previous test failure evidence and fix its cause; never edit acceptance tests.'}
                        self.store.record(incident_id,'code_proposal_rejected',{'attempt':attempt+1, 'format_attempt':format_attempt+1, **feedback})
                    except ValidationError as exc:
                        proposal = None
                        feedback = {**(feedback or {}), 'attempt':attempt+1, 'schema_error':str(exc)[:3000], 'instruction':'Return a complete candidate against the original snapshot, retaining the previous test failure feedback. Each exact edit has ONLY path, before, after. Do not add is_edit or other metadata. Include a nonempty changes or edits array.'}
                        self.store.record(incident_id,'code_proposal_rejected',{'attempt':attempt+1, 'format_attempt':format_attempt+1, **feedback})
                    except Exception as exc:
                        agent_error = type(exc).__name__+': '+str(exc)[:300]
                        self.store.record(incident_id,'code_proposal_rejected',{'attempt':attempt+1,'error':agent_error})
                        break
                if proposal is None:
                    agent_error = agent_error or 'The reasoning provider did not return a valid source proposal after three format retries'
                    break
                self.store.update(incident_id, diagnosis=proposal.diagnosis, requirement_assessment=[item.model_dump() for item in proposal.requirements], continuation_plan=proposal.continuation_plan)
                self.store.record(incident_id, 'code_proposal', {'attempt': attempt+1, **proposal.model_dump()})
                result = {'exit_code': 4, 'cases': [], 'output': 'Candidate not validated'}
                try:
                    replacements = proposal_sources(worktree, proposal, protected)
                    for name, content in replacements.items():
                        target = validate_path(worktree, name)
                        if len(content.encode()) > 256000 or '\x00' in content:
                            raise ValueError('Source change exceeds bounded text limits')
                        if target.suffix == '.py':
                            ast.parse(content, filename=name)
                            preserve_rejection_guards(target.read_text(encoding='utf-8') if target.exists() else '', content, name)
                    for name, content in replacements.items():
                        target = validate_path(worktree, name)
                        originals[name] = target.read_text(encoding='utf-8') if target.exists() else None
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(content.encode('utf-8')); target.chmod(0o644)
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
                if 'repair removes or changes a rejection precondition' in result['output']:
                    self.store.record(incident_id, 'code_proposal_rejected', {'attempt':attempt+1, 'error':result['output'], 'phase':'guard_validation'})
                    for guard_proposal in guard_comparison_repairs(worktree, [name for name in replacements if name+': repair removes or changes a rejection precondition' in result['output']]):
                        edit = guard_proposal.edits[0]
                        target = validate_path(worktree, edit.path)
                        if edit.path in protected:continue
                        original = target.read_text(encoding='utf-8')
                        content = original.replace(edit.before, edit.after, 1)
                        preserve_rejection_guards(original, content, edit.path)
                        target.write_bytes(content.encode('utf-8'))
                        try:
                            self.store.update(incident_id, status='verifying')
                            agent_runs += 1
                            guard_result = await asyncio.to_thread(sandbox.run)
                            guard_checks, guard_details = qualify(guard_result)
                            guard_passed = all(guard_checks.values())
                            self.store.record(incident_id, 'guard_candidate_tests', {'attempt':attempt+1, 'edit':edit.model_dump(), 'passed':guard_passed, **guard_result})
                            if guard_passed:
                                originals[edit.path] = original
                                result = guard_result
                                repair_origin = 'Bounded rejection-guard comparison search passed original immutable acceptance; no repository-specific patch was supplied'
                                self.store.record(incident_id, 'code_proposal', {'attempt':attempt+1, 'origin':'guard_comparison_search', **guard_proposal.model_dump()})
                                self.store.update(incident_id, diagnosis=guard_proposal.diagnosis)
                                break
                        finally:
                            if edit.path not in originals:target.write_bytes(original.encode('utf-8'))
                diff = git(['diff', '--no-ext-diff', '--no-textconv'], worktree)
                unchanged = immutable_digest(worktree, paths, protected) == immutable and embedded_doctests(worktree, paths) == doctests
                checks, details = acceptance(baseline, result, unchanged,request.mode)
                checks['nonempty_patch'] = bool(diff)
                passed = all(checks.values())
                self.store.record(incident_id, 'candidate_tests', {'attempt': attempt+1, 'passed': passed, 'acceptance': details, **result})
                if passed:break
                # A failed model candidate may target a symptom rather than the
                # throwing guard. Probe bounded comparisons from traceback files
                # against the original snapshot and immutable acceptance suite.
                feedback = {'attempt': attempt+1, 'candidate': proposal.model_dump(), 'test_result': result, 'acceptance': details}
                if request.mode == 'repair' and implicated_sources:
                    tournament.restore()
                    originals = {}; new_files = set()
                    for guard_proposal in guard_comparison_repairs(worktree, implicated_sources):
                        edit = guard_proposal.edits[0]
                        if edit.path in protected:continue
                        target = validate_path(worktree, edit.path)
                        original = target.read_bytes()
                        content = original.decode('utf-8').replace(edit.before, edit.after, 1)
                        preserve_rejection_guards(original.decode('utf-8'), content, edit.path)
                        target.write_bytes(content.encode('utf-8'))
                        try:
                            agent_runs += 1
                            guard_result = await asyncio.to_thread(sandbox.run)
                            guard_checks, guard_details = qualify(guard_result)
                            guard_passed = all(guard_checks.values())
                            self.store.record(incident_id, 'guard_candidate_tests', {'attempt':attempt+1, 'origin':'traceback_comparison_search', 'edit':edit.model_dump(), 'passed':guard_passed, **guard_result})
                            if guard_passed:
                                result, checks, details = guard_result, guard_checks, guard_details
                                diff = git(['diff', '--no-ext-diff', '--no-textconv'], worktree)
                                checks['nonempty_patch'] = bool(diff)
                                passed = bool(diff)
                                repair_origin = 'Bounded traceback comparison search passed original immutable acceptance; source values inferred from this repository'
                                self.store.record(incident_id, 'code_proposal', {'attempt':attempt+1, 'origin':'traceback_comparison_search', **guard_proposal.model_dump()})
                                self.store.update(incident_id, diagnosis=guard_proposal.diagnosis)
                                break
                        finally:
                            if not passed:target.write_bytes(original)
                    if passed:break
            tournament.agent(result,checks,details,diff,agent_runs,repair_origin or agent_error)
            winner = tournament.record()
            if winner:
                result, checks, details, diff = winner['result'], winner['checks'], winner['acceptance'], winner['patch']
                passed = True
            else:
                passed = False
            unchanged = immutable_digest(worktree,paths,protected)==immutable
            self.store.record(incident_id, 'verification', {**result, 'passed': passed, 'checks': checks, 'acceptance': details, 'original_commit': commit, 'tests_immutable': unchanged, 'selected_strategy':winner['id'] if winner else None})
            artifact = self.artifacts/f'{incident_id}.patch'; artifact.write_bytes(diff.encode('utf-8'))
            if passed and diff:
                contents = await asyncio.to_thread(self.repaired_archive, {
                    'import_request': request.model_dump(), 'commit': commit,
                    'patch': diff, 'verification': {'passed': True},
                })
                self.store.update(incident_id, download_ready=True)
                self.store.record(incident_id, 'repaired_archive', {'bytes':len(contents), 'sha256':hashlib.sha256(contents).hexdigest()})
            self.store.update(incident_id, status='resolved' if passed else 'escalated', error=None if passed else (agent_error or 'No candidate passed the original acceptance suite within three repair attempts. Last failure: '+result.get('output','No test output')[-500:]), verification={'passed':passed,'checks':checks}, patch=diff, commit=commit, remaining_risks=([winner['reason'],'Verified against the imported acceptance suite only; patch review and deployment remain operator actions.'] if winner else []) if passed else ['No verified repair; inspect the test evidence and unsupported requirements.'])
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

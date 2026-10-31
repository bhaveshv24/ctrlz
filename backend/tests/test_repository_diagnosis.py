import io
import zipfile
from pathlib import Path

import pytest
from ctrlz.continuation import Continuation
from ctrlz.models import ImportRequest
from ctrlz.repository import RepositoryImports, git


def imported(tmp_path, source=None):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('logic.py', source or 'def allowed(value):\n    return value != 2\n')
        z.writestr('test_logic.py', 'from logic import allowed\ndef test_allowed():\n    assert allowed(2)\n')
    root = tmp_path/'imports'
    snapshot = RepositoryImports(root).import_zip(archive.getvalue())
    return Continuation(None, None, root, tmp_path/'artifacts'), snapshot


@pytest.mark.parametrize('code,cases,status', [
    (1, [{'id': 'test_allowed', 'passed': False, 'status': 'failed'}], 'failing'),
    (0, [{'id': 'test_allowed', 'passed': True, 'status': 'passed'}], 'healthy'),
    (125, [], 'blocked'),
    (0, [{'id': 'test_allowed', 'passed': False, 'status': 'skipped'}], 'blocked'),
])
def test_diagnosis_uses_real_runner_results_and_leaves_source_clean(tmp_path, monkeypatch, code, cases, status):
    runner, snapshot = imported(tmp_path)
    closed = []
    class Sandbox:
        def __init__(self, workspace, profile, install_dependencies):
            assert workspace != Path(snapshot['repository'])
        def prepare(self, inspection):
            pass
        def run(self):
            return {'exit_code': code, 'cases': cases, 'output': 'runner output'}
        def close(self):
            closed.append(True)
    monkeypatch.setattr('ctrlz.continuation.Sandbox', Sandbox)
    result = runner.diagnose(ImportRequest(repository=snapshot['repository']))
    assert result['status'] == status
    assert result['baseline']['output'] == 'runner output'
    assert git(['status', '--porcelain'], snapshot['repository']) == ''
    assert closed == [True]


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_repaired_archive_requires_verification_and_keeps_original_tests(tmp_path, newline):
    runner, snapshot = imported(tmp_path, ('def allowed(value):\n    return value != 2\n').replace('\n', newline))
    repo = Path(snapshot['repository'])
    original = (repo/'logic.py').read_text()
    (repo/'logic.py').write_text(original.replace('!=', '=='))
    patch = git(['diff'], repo)
    git(['checkout', '--', 'logic.py'], repo)
    incident = {'import_request': {'repository': str(repo)}, 'patch': patch, 'verification': {'passed': False}}
    with pytest.raises(ValueError, match='verified'):
        runner.repaired_archive(incident)
    incident['verification']['passed'] = True
    with zipfile.ZipFile(io.BytesIO(runner.repaired_archive(incident))) as archive:
        assert 'value == 2' in archive.read('repaired-repository/logic.py').decode()
        assert archive.read('repaired-repository/test_logic.py') == (repo/'test_logic.py').read_bytes()
        assert not any('/.git/' in name for name in archive.namelist())
    assert (repo/'logic.py').read_text() == original
    assert git(['status', '--porcelain'], repo) == ''


def test_repaired_archive_includes_new_source_files(tmp_path):
    runner, snapshot = imported(tmp_path)
    repo = Path(snapshot['repository'])
    (repo/'helper.py').write_text('VALUE = 2\n')
    git(['add', '--intent-to-add', 'helper.py'], repo)
    patch = git(['diff'], repo)
    git(['reset', '--', 'helper.py'], repo)
    (repo/'helper.py').unlink()
    incident = {'import_request': {'repository': str(repo)}, 'patch': patch, 'verification': {'passed': True}}
    with zipfile.ZipFile(io.BytesIO(runner.repaired_archive(incident))) as archive:
        assert archive.read('repaired-repository/helper.py') == b'VALUE = 2\n'


@pytest.mark.parametrize('kind', ['zip', 'local', 'github'])
def test_package_repair_exports_whole_repository(tmp_path, monkeypatch, kind):
    from ctrlz.repository import RepositorySource
    source = tmp_path/'sources/project'
    (source/'backend').mkdir(parents=True)
    (source/'frontend/src').mkdir(parents=True)
    files = {'backend/logic.py': 'def allowed(value):\n    return value != 2\n',
             'backend/test_logic.py': 'from logic import allowed\ndef test_allowed(): assert allowed(2)\n',
             'frontend/src/main.tsx': 'export const app = "original frontend";\n',
             'docker-compose.yml': 'services: {}\n', 'README.md': 'Full project\n',
             '.env': 'SECRET=excluded\n'}
    for name, content in files.items():
        (source/name).write_bytes(content.encode())
    imports = RepositoryImports(tmp_path/'imports')
    if kind == 'zip':
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            for name, content in files.items():archive.writestr('project/'+name, content)
        snapshot = imports.import_zip(data.getvalue(), 'backend')
    else:
        monkeypatch.setenv('REPOSITORY_SOURCE_ROOTS', str(tmp_path/'sources'))
        if kind == 'github':
            import ctrlz.repository as module
            original_git = module.git
            def clone_fixture(args, cwd, **kwargs):
                if args[0] == 'clone':
                    import shutil
                    shutil.copytree(source, Path(args[-1]))
                    return ''
                return original_git(args, cwd, **kwargs)
            monkeypatch.setattr(module, 'git', clone_fixture)
            git(['init', '-b', 'main'], source)
            git(['add', '.'], source)
            git(['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test', 'commit', '-m', 'Source'], source)
        snapshot = imports.import_source(RepositorySource(kind=kind, source=str(source) if kind == 'local' else 'https://github.com/example/project', subdirectory='backend'))
    repo = Path(snapshot['repository'])
    (repo/'logic.py').write_bytes(files['backend/logic.py'].replace('!=', '==').encode())
    patch = git(['diff'], repo)
    git(['checkout', '--', 'logic.py'], repo)
    runner = Continuation(None, None, imports.root, tmp_path/'artifacts')
    incident = {'import_request': {'repository': str(repo)}, 'commit': snapshot['commit'],
                'patch': patch, 'verification': {'passed': True}}
    with zipfile.ZipFile(io.BytesIO(runner.repaired_archive(incident))) as archive:
        assert b'value == 2' in archive.read('repaired-repository/backend/logic.py')
        for name in ['frontend/src/main.tsx', 'docker-compose.yml', 'README.md', 'backend/test_logic.py']:
            assert archive.read('repaired-repository/'+name) == files[name].encode()
        assert not any('/.git/' in name or name.endswith('/.env') for name in archive.namelist())


def test_repaired_archive_uses_verified_commit_and_unicode_paths(tmp_path):
    runner, snapshot = imported(tmp_path)
    repo = Path(snapshot['repository'])
    name = 'résumé.py'
    git(['config', 'user.name', 'Archive regression test'], repo)
    git(['config', 'user.email', 'archive@example.test'], repo)
    original = 'MESSAGE = "café"\n'
    repaired = 'MESSAGE = "こんにちは"\n'
    (repo/name).write_bytes(original.encode('utf-8'))
    git(['add', '--', name], repo)
    git(['commit', '-m', 'Unicode source'], repo)
    commit = git(['rev-parse', 'HEAD'], repo)
    (repo/name).write_bytes(repaired.encode('utf-8'))
    patch = git(['diff'], repo, raw=True).decode('utf-8')
    git(['checkout', '--', name], repo)
    (repo/name).write_bytes(b'MESSAGE = "later unrelated change"\n')
    git(['add', '--', name], repo)
    git(['commit', '-m', 'Move HEAD after verification'], repo)
    incident = {'import_request': {'repository': str(repo)}, 'commit': commit,
                'patch': patch, 'verification': {'passed': True}}
    for _ in range(2):
        with zipfile.ZipFile(io.BytesIO(runner.repaired_archive(incident))) as archive:
            assert archive.read('repaired-repository/'+name) == repaired.encode('utf-8')
            assert archive.read('repaired-repository/test_logic.py') == (repo/'test_logic.py').read_bytes()
    assert (repo/name).read_bytes() == b'MESSAGE = "later unrelated change"\n'


@pytest.mark.asyncio
async def test_diagnose_api_authentication_and_automatic_defaults(tmp_path, monkeypatch):
    import httpx
    from ctrlz.main import create_app
    from ctrlz.store import Store
    monkeypatch.setenv('CTRLZ_OPERATOR_TOKEN', 'diagnosis-fixture-token')
    monkeypatch.setenv('CTRLZ_CODE_EXECUTION_ENABLED', 'true')
    monkeypatch.setenv('DATA_DIR', str(tmp_path/'data'))
    monkeypatch.setenv('IMPORT_ROOT', str(tmp_path/'imports'))
    class Books:
        def search(self, query): return []
    class Reasoner:
        provider = 'fixture'
    seen = []
    def diagnose(self, request):
        seen.append(request)
        return {'status': 'failing', 'failed': 1}
    monkeypatch.setattr(Continuation, 'diagnose', diagnose)
    store = Store(f"sqlite:///{tmp_path/'api.db'}")
    app = create_app(store=store, reasoner=Reasoner(), runbooks=Books(), monitor=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.post('/repositories/diagnose', json={'repository': 'fixture'})).status_code == 401
        response = await client.post('/repositories/diagnose', json={'repository': 'fixture', 'install_dependencies': True}, headers={'X-Operator-Token': 'diagnosis-fixture-token'})
        assert response.status_code == 200
        assert response.json()['status'] == 'failing'
        assert seen[0].requirements and seen[0].install_dependencies
    await app.state.engine.client.aclose()
    store.engine.dispose()


@pytest.mark.parametrize('replacement', ['if not payment:', 'if not payment or payment.status == "failed":'])
def test_repair_cannot_drop_required_state_or_replace_it_with_blacklist(replacement):
    from ctrlz.continuation import preserve_rejection_guards
    source = 'if not payment or payment.status == "paid":\n    raise ValueError("Payment required")\n'
    with pytest.raises(ValueError, match='precondition'):
        preserve_rejection_guards(source, source.replace('if not payment or payment.status == "paid":', replacement), 'worker.py')
    preserve_rejection_guards(source, source.replace('==', '!='), 'worker.py')


@pytest.mark.asyncio
async def test_schema_retries_preserve_test_feedback_and_do_not_spend_repair_attempts(tmp_path, monkeypatch):
    from ctrlz.models import CodeProposal, SourceEdit
    from ctrlz.store import Store
    runner, snapshot = imported(tmp_path)
    store = Store(f"sqlite:///{tmp_path/'retry.db'}")
    runner.store = store
    seen = []
    class Sandbox:
        profile = 'python-pytest'
        def __init__(self, workspace, profile, install_dependencies): self.workspace = workspace
        def prepare(self, inspection): return {'phase': 'fixture'}
        def run(self):
            passed = 'return value == 2' in (self.workspace/'logic.py').read_text()
            return {'exit_code': 0 if passed else 1, 'cases': [{'id': 'test_logic::test_allowed', 'passed': passed, 'status': 'passed' if passed else 'failed'}], 'output': 'passed' if passed else 'logic.py: assertion failure'}
        def close(self): pass
    class Reasoner:
        async def code(self, request, files, context):
            seen.append(context['previous_attempt'])
            if len(seen) == 1:
                return CodeProposal(diagnosis='Wrong candidate', edits=[SourceEdit(path='logic.py', before='return value != 2', after='return None')])
            assert context['previous_attempt']['test_result']['exit_code'] == 1
            if len(seen) == 2: return CodeProposal.model_validate({'diagnosis': 'Missing edit'})
            if len(seen) == 3:
                return CodeProposal.model_validate({'diagnosis': 'Malformed edit', 'edits': [{'path':'logic.py', 'before':'return value != 2', 'after':'return value == 2', 'unexpected_extra': True}]})
            assert len(seen) == 4
            assert 'test_logic.py' in files and 'assert allowed(2)' in files['test_logic.py']
            return CodeProposal(diagnosis='Correct comparison', edits=[SourceEdit(path='logic.py', before='return value != 2', after='return value == 2')])
    monkeypatch.setattr('ctrlz.continuation.Sandbox', Sandbox)
    runner.reasoner = Reasoner()
    incident, _ = store.create('code-import', 'code', snapshot['repository'], {})
    await runner.run(incident['id'], ImportRequest(repository=snapshot['repository']))
    result = store.get(incident['id'])
    assert result['status'] == 'resolved', result
    assert result['diagnosis'] == 'Correct comparison'
    attempts = [e['payload']['attempt'] for e in store.events() if e['stage'] == 'candidate_tests']
    assert attempts == [1, 2]
    assert len(seen) == 4
    assert git(['status','--porcelain'], snapshot['repository']) == ''
    store.engine.dispose()


def test_rejection_guard_check_allows_repairing_invalid_python_syntax():
    from ctrlz.continuation import preserve_rejection_guards
    preserve_rejection_guards('def broken(:\n', 'def broken():\n    return 2\n', 'logic.py')


@pytest.mark.asyncio
async def test_unsafe_guard_proposal_triggers_bounded_automatic_repair(tmp_path, monkeypatch):
    from ctrlz.models import CodeProposal, SourceEdit
    from ctrlz.store import Store
    source = 'def allowed(value):\n    if value.status == "ready":\n        raise ValueError("Ready state required")\n    return True\n'
    runner, snapshot = imported(tmp_path, source)
    store = Store(f"sqlite:///{tmp_path/'guard.db'}")
    runner.store = store
    calls = []
    class Sandbox:
        profile = 'python-pytest'
        def __init__(self, workspace, profile, install_dependencies): self.workspace = workspace
        def prepare(self, inspection): return {'phase': 'fixture'}
        def run(self):
            passed = 'value.status != "ready"' in (self.workspace/'logic.py').read_text()
            return {'exit_code': 0 if passed else 1, 'cases': [{'id': 'test_logic::test_allowed', 'passed': passed, 'status': 'passed' if passed else 'failed'}], 'output': 'passed' if passed else 'logic.py: ValueError: Ready state required'}
        def close(self): pass
    class Reasoner:
        async def code(self, request, files, context):
            calls.append(True)
            return CodeProposal(diagnosis='Unsafe suggested removal', edits=[SourceEdit(path='logic.py', before='if value.status == "ready":', after='if not value:')])
    monkeypatch.setattr('ctrlz.continuation.Sandbox', Sandbox)
    runner.reasoner = Reasoner()
    incident, _ = store.create('code-import', 'code', snapshot['repository'], {})
    await runner.run(incident['id'], ImportRequest(repository=snapshot['repository']))
    result = store.get(incident['id'])
    assert result['status'] == 'resolved', result
    assert len(calls) == 1
    assert '+    if value.status != "ready":' in result['patch']
    assert any(e['stage'] == 'guard_candidate_tests' and e['payload']['passed'] for e in store.events())
    assert (Path(snapshot['repository'])/'logic.py').read_text() == source
    store.engine.dispose()


def test_advisory_metadata_cannot_discard_an_otherwise_valid_source_edit():
    from ctrlz.models import CodeProposal
    proposal = CodeProposal.model_validate({'diagnosis': 'Fix comparison', 'requirements': [{'requirement': 'Existing test', 'status': 'failed'}], 'edits': [{'path': 'logic.py', 'before': 'x == 2', 'after': 'x != 2', 'is_edit': True}]})
    assert proposal.requirements[0].status == 'incomplete'
    assert proposal.edits[0].after == 'x != 2'
    assert 'is_edit' not in proposal.edits[0].model_dump()

import io
import zipfile
from pathlib import Path

import pytest
from ctrlz.continuation import Continuation
from ctrlz.models import ImportRequest
from ctrlz.repository import RepositoryImports, git


def imported(tmp_path):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('logic.py', 'def allowed(value):\n    return value != 2\n')
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


def test_repaired_archive_requires_verification_and_keeps_original_tests(tmp_path):
    runner, snapshot = imported(tmp_path)
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

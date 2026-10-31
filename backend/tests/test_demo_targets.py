import pytest
from pathlib import Path
from ctrlz.demo_targets import repository_target, service_target
from ctrlz.demo_repository import mutation, injected_copy
from ctrlz.repository import RepositoryImports, git
from ctrlz.models import Project


def fixture_repo(tmp_path, source='def allowed(x):\n    return x == 2\n'):
    root = tmp_path/'original'
    root.mkdir()
    (root/'logic.py').write_text(source)
    (root/'test_logic.py').write_text('from logic import allowed\ndef test_allowed():\n    assert allowed(2)\n')
    git(['init'],root)
    git(['add','.'],root)
    git(['-c','user.name=Test','-c','user.email=test@localhost','commit','-m','fixture'],root)
    return root


def test_scenarios_repository_real_facts_and_disabled_reason(tmp_path):
    root = fixture_repo(tmp_path)
    target = repository_target(root)
    assert target['facts']['test_file_count'] == 1
    assert target['facts']['editable_files'] == ['logic.py']
    assert target['facts']['profile'] == 'python-pytest'
    assert all(s['disabled_reason'] is None for s in target['scenarios'])
    (root/'test_logic.py').unlink()
    assert all(s['disabled_reason'] for s in repository_target(root)['scenarios'])


def test_unsupported_mutation_and_non_test_source(tmp_path):
    root = fixture_repo(tmp_path, 'def allowed(x):\n    return True\n')
    target = repository_target(root)
    assert target['scenarios'][0]['disabled_reason'] is None
    assert target['scenarios'][1]['disabled_reason']
    assert mutation(root, {'editable_files':['test_logic.py'], 'tests':['test_logic.py']}) is None


def test_generic_service_never_exposes_campus_faults():
    p = Project(id='api',name='API',base_url='http://localhost:9000').model_dump()
    target = service_target(p)
    assert [s['id'] for s in target['scenarios']] == ['monitor','contract','fault']
    assert target['scenarios'][-1]['disabled_reason']
    assert target['facts']['health_path'] == p['integration']['health_path']
    p['enabled'] = False
    assert service_target(p)['scenarios'][0]['disabled_reason']


def test_campus_scenarios_only_for_explicit_adapter(monkeypatch):
    from ctrlz.presets import campuspass_project
    p = campuspass_project(id='campus',name='Campus',base_url='http://localhost:9000').model_dump()
    assert all(s['disabled_reason'] for s in service_target(p)['scenarios'])
    monkeypatch.setenv('CTRLZ_DEMO_CONTROLS_ENABLED','true')
    p['demo_enabled'] = True
    assert [s['id'] for s in service_target(p)['scenarios']] == ['outage','workflow']
    assert all(s['disabled_reason'] is None for s in service_target(p)['scenarios'])


class FakeSandbox:
    mode = 'regression'
    def __init__(self, root, *args):self.root = root
    def prepare(self, inspection):return {'phase':'fixture'}
    def run(self):
        changed = '!=' in (self.root/'logic.py').read_text()
        passed = not changed or self.mode == 'survived'
        if self.mode == 'broken':passed = False
        return {'exit_code':0 if passed else 1,'cases':[{'id':'test_allowed','passed':passed}], 'output':'fixture only'}
    def close(self):pass


@pytest.mark.parametrize('mode', ['regression','survived','broken'])
async def test_mutation_proves_failure_and_preserves_original(tmp_path,monkeypatch,mode):
    root = fixture_repo(tmp_path)
    original = (root/'logic.py').read_bytes()
    head = git(['rev-parse','HEAD'],root)
    imports = RepositoryImports(tmp_path/'imports')
    monkeypatch.setattr('ctrlz.demo_repository.Sandbox',FakeSandbox)
    monkeypatch.setattr(FakeSandbox,'mode',mode)
    events = []
    if mode == 'regression':
        snapshot, disclosure = await injected_copy(root,imports,False,lambda *args:events.append(args))
        assert disclosure['disclosed'] and disclosure['failing_baseline']['exit_code'] == 1
        assert '!=' in (Path(snapshot['repository'])/'logic.py').read_text()
        assert (Path(snapshot['repository'])/'test_logic.py').read_bytes() == (root/'test_logic.py').read_bytes()
        assert not git(['status','--porcelain'],Path(snapshot['repository']))
    else:
        with pytest.raises(ValueError):await injected_copy(root,imports,False,lambda *args:events.append(args))
        assert not list(imports.root.iterdir())
    assert (root/'logic.py').read_bytes() == original
    assert git(['rev-parse','HEAD'],root) == head
    assert not git(['status','--porcelain'],root)


def test_target_run_history_isolated(tmp_path):
    from ctrlz.store import Store
    store = Store('sqlite:///'+str(tmp_path/'history.db'))
    store.demo_start('request-one','repo-one','repair')
    store.demo_start('request-two','repo-two','injected')
    assert [r['id'] for r in store.demo_runs('repo-one')] == ['request-one']


async def test_repository_demo_api_runs_normal_repair_and_discloses_receipt(tmp_path, monkeypatch):
    import asyncio
    import httpx
    from ctrlz.main import create_app
    from ctrlz.store import Store
    from test_core import EmptyRunbooks, TestReasoner
    imports = RepositoryImports(tmp_path/'imports')
    root = fixture_repo(tmp_path)
    managed = imports.root/'repo-fixture'
    managed.mkdir()
    imports._copy(root,managed)
    imports._commit(managed, {'kind':'local'}, [])
    monkeypatch.setenv('IMPORT_ROOT',str(imports.root))
    monkeypatch.setenv('DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setenv('CTRLZ_OPERATOR_TOKEN','test-only')
    monkeypatch.setattr('ctrlz.demo_repository.Sandbox',FakeSandbox)
    monkeypatch.setattr(FakeSandbox,'mode','regression')
    calls = []
    async def repair(self,incident_id,request):
        calls.append(request)
        self.store.update(incident_id,status='blocked',error='No fixture model repair provided')
    monkeypatch.setattr('ctrlz.continuation.Continuation.run',repair)
    store = Store('sqlite:///'+str(tmp_path/'api.db'))
    async with httpx.AsyncClient() as remote:
        app = create_app(store,remote,TestReasoner(),EmptyRunbooks(),monitor=False)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            assert (await client.get('/demo/targets')).status_code == 401
            client.headers['X-Operator-Token']='test-only'
            targets = (await client.get('/demo/targets')).json()
            assert targets[0]['id'] == str(managed)
            body = {'repository':str(managed),'scenario':'injected','request_id':'test-demo-injected'}
            assert (await client.post('/demo/repositories/run',json=body)).status_code == 202
            await asyncio.gather(*app.state.tasks)
            assert len(calls) == 1 and calls[0].repository != str(managed)
            rows = (await client.get('/demo/runs',params={'target':str(managed)})).json()
            incident_id = rows[0]['incident_id']
            receipt = (await client.get(f'/incidents/{incident_id}/receipt')).json()
            assert receipt['incident']['injected_regression']['proven']
            assert not receipt['success']
            brief = (await client.get(f'/incidents/{incident_id}/brief')).text
            assert 'Disclosed injected regression' in brief
            await client.post('/demo/repositories/run',json=body)
            assert len(calls) == 1
            assert (await client.post('/demo/repositories/run',json={**body,'repository':str(root)})).status_code == 422


@pytest.mark.skipif(__import__('os').getenv('RUN_DOCKER_TESTS') != '1',reason='Explicit Docker integration suite')
async def test_real_sandbox_injection_proves_failure(tmp_path):
    root = fixture_repo(tmp_path)
    snapshot, disclosure = await injected_copy(root,RepositoryImports(tmp_path/'imports'),False,lambda *args:None)
    assert disclosure['clean_baseline']['exit_code'] == 0
    assert disclosure['failing_baseline']['exit_code'] == 1
    assert (root/'logic.py').read_text() == 'def allowed(x):\n    return x == 2\n'

"""Real Postgres integration: CTRLZ_TEST_POSTGRES_URL must name a disposable test DB."""
import os
import uuid
import pytest
from concurrent.futures import ThreadPoolExecutor
from ctrlz.accounts import Accounts, Credentials
from ctrlz.store import Store

pytestmark = pytest.mark.skipif(not os.getenv('CTRLZ_TEST_POSTGRES_URL'), reason='Disposable Postgres URL not configured')


def test_postgres_accounts_persist_and_workspace_isolation(tmp_path):
    url = os.environ['CTRLZ_TEST_POSTGRES_URL']
    accounts = Accounts(tmp_path, url)
    credentials = Credentials(email=uuid.uuid4().hex+'@example.com', password='integration-password-123')
    user = accounts.create(credentials)
    token = accounts.login(credentials)['token']
    restarted = Accounts(tmp_path/'fresh-disk', url)
    assert restarted.resolve(token) == user
    first = Store(url, namespace=user['id'])
    other = Store(url, namespace=uuid.uuid4().hex)
    project = {'id':'same-id', 'name':'First private workspace'}
    first.save_project(project)
    assert other.projects() == []
    restored = Store(url, namespace=user['id'])
    assert restored.projects() == [project]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: restored.create('same-id','code','same-resource',{}), range(4)))
    assert sum(created for _, created in results) == 1
    incident = results[0][0]
    restored.record(incident['id'], 'test', {'persisted':True})
    restored.observe('same-id', {}, [])
    assert len(restored.probes('same-id')) == 1
    assert restored.events()[0]['payload']['persisted']
    assert restored.demo_start('same-request','same-id','repair')[1]
    assert not restored.demo_start('same-request','same-id','repair')[1]
    with accounts.connect() as db:
        db.execute('DELETE FROM attempts')
    accounts.throttle('integration-key', limit=1)
    with pytest.raises(Exception) as throttled:accounts.throttle('integration-key', limit=1)
    assert throttled.value.status_code == 429
    with first.engine.connect() as db:
        assert db.exec_driver_sql("SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public' AND tablename IN ('users','incidents')").scalar() == 0
        assert db.exec_driver_sql("SELECT relrowsecurity FROM pg_class JOIN pg_namespace n ON n.oid=relnamespace WHERE n.nspname='ctrlz_accounts' AND relname='users'").scalar()
    restarted.logout(token)
    with pytest.raises(Exception) as exc:accounts.resolve(token)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_postgres_gateway_survives_empty_local_disk(tmp_path, monkeypatch):
    import httpx
    from ctrlz.main import create_app
    class Books:
        def search(self, query):return []
    monkeypatch.setenv('DATABASE_URL', os.environ['CTRLZ_TEST_POSTGRES_URL'])
    monkeypatch.setenv('DATA_DIR', str(tmp_path/'before'))
    monkeypatch.setenv('IMPORT_ROOT', str(tmp_path/'imports'))
    monkeypatch.setenv('CTRLZ_ALLOW_REGISTRATION', 'true')
    credentials = {'email':uuid.uuid4().hex+'@example.com', 'password':'gateway-password-123'}
    app = create_app(runbooks=Books(), monitor=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        result = await client.post('/auth/register', json=credentials)
        assert result.status_code == 201, result.text
        headers = {'Authorization':'Bearer '+result.json()['token']}
        project = {'id':'persisted', 'name':'Persisted service', 'base_url':'https://example.com', 'enabled':False}
        assert (await client.post('/projects', json=project, headers=headers)).status_code == 200
    monkeypatch.setenv('DATA_DIR', str(tmp_path/'after'))
    restarted = create_app(runbooks=Books(), monitor=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted), base_url='http://test') as client:
        assert (await client.get('/auth/me', headers=headers)).status_code == 200
        assert (await client.get('/projects', headers=headers)).json()[0]['id'] == 'persisted'

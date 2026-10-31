import httpx
import pytest
from ctrlz.accounts import Accounts, Credentials
from ctrlz.main import create_app


class Books:
    def search(self, query):
        return []


def test_seed_and_password_storage(tmp_path):
    accounts = Accounts(tmp_path)
    accounts.seed()
    accounts.seed()
    users = accounts.users()
    assert len(users) == 3
    assert sum(u['role'] == 'admin' for u in users) == 2
    assert (tmp_path / 'initial-credentials.txt').stat().st_mode & 0o777 == 0o600
    with accounts.connect() as db:
        assert all(len(r['password']) == 128 and len(r['salt']) == 32 for r in db.execute('SELECT * FROM users'))


@pytest.mark.asyncio
async def test_email_login_isolation_roles_logout_and_restart(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path}/admin.db')
    monkeypatch.setenv('IMPORT_ROOT', str(tmp_path / 'admin-imports'))
    monkeypatch.setenv('CTRLZ_ADMIN_1_PASSWORD', 'admin-one-password-123')
    monkeypatch.setenv('CTRLZ_ALLOW_REGISTRATION', 'true')
    app = create_app(runbooks=Books(), monitor=False)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/projects')).status_code == 401
        assert (await client.post('/auth/login', json={'email':'admin1@ctrlz.local','password':'wrong-password-123'})).status_code == 401
        first = (await client.post('/auth/register', json={'email':'First@Example.com','password':'first-password-123'})).json()
        second = (await client.post('/auth/register', json={'email':'second@example.com','password':'second-password-123'})).json()
        headers = {'X-Operator-Token':first['token']}
        other = {'X-Operator-Token':second['token']}
        assert first['user']['email'] == 'first@example.com'
        project = {'id':'my-service','name':'Independent service','base_url':'https://example.com','enabled':False}
        assert (await client.post('/projects', json=project, headers=headers)).status_code == 200
        saved = (await client.get('/projects', headers=headers)).json()
        assert len(saved) == 1
        assert saved[0]['token_env'].startswith('CTRLZ_USER_')
        assert (await client.post('/projects',json={**project,'adapter':'campuspass-v1'},headers=headers)).status_code == 403
        assert (await client.get('/projects', headers=other)).json() == []
        assert (await client.get('/auth/users', headers=headers)).status_code == 403
        assert (await client.post('/repositories/import', headers=headers, json={'kind':'local','source':'/tmp'})).status_code == 403
        # Data and SSE events cannot be read through another account.
        ws = tmp_path / 'workspaces' / first['user']['id']
        from ctrlz.store import Store
        store = Store(f'sqlite:///{ws / "workspace.db"}')
        incident, _ = store.create('my-service','outage','service',{})
        store.record(incident['id'],'private',{'secret':'first-user'})
        assert (await client.get('/incidents/'+incident['id'],headers=other)).status_code == 404
        assert (await client.get('/incidents',headers=other)).json() == []
        store.engine.dispose()
        admin = (await client.post('/auth/login',json={'email':'admin1@ctrlz.local','password':'admin-one-password-123'})).json()
        ah = {'Authorization':'Bearer '+admin['token']}
        assert len((await client.get('/auth/users',headers=ah)).json()) == 5
        assert (await client.get('/projects',headers=ah)).json() == []
        assert (await client.post('/auth/password',headers=headers,json={'current_password':'first-password-123','password':'changed-password-123'})).status_code == 200
        assert (await client.get('/projects',headers=headers)).status_code == 401
        replacement = (await client.post('/auth/login',json={'email':'first@example.com','password':'changed-password-123'})).json()
        assert len((await client.get('/projects',headers={'X-Operator-Token':replacement['token']})).json()) == 1
        assert (await client.post('/auth/logout',headers=other)).status_code == 200
        assert (await client.get('/projects',headers=other)).status_code == 401
    # Sessions and account workspaces survive an application restart.
    app2 = create_app(runbooks=Books(), monitor=False)
    async with app2.router.lifespan_context(app2), httpx.AsyncClient(transport=httpx.ASGITransport(app=app2),base_url='http://test') as client:
        assert len((await client.get('/projects',headers={'X-Operator-Token':replacement['token']})).json()) == 1


def test_throttling_expiry_and_registration_role(tmp_path):
    accounts = Accounts(tmp_path)
    accounts.create(Credentials(email='person@example.com',password='long-password-123'))
    for _ in range(2):
        accounts.throttle('example', 2)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        accounts.throttle('example', 2)
    assert exc.value.status_code == 429
    session = accounts.login(Credentials(email='person@example.com',password='long-password-123'))
    with accounts.connect() as db:
        db.execute('UPDATE sessions SET expires=0')
    with pytest.raises(HTTPException):
        accounts.resolve(session['token'])


@pytest.mark.asyncio
async def test_host_execution_gate_keeps_incident_unchanged(tmp_path, monkeypatch):
    from ctrlz.store import Store
    monkeypatch.setenv('CTRLZ_OPERATOR_TOKEN','test-operator')
    monkeypatch.setenv('CTRLZ_CODE_EXECUTION_ENABLED','false')
    monkeypatch.setenv('DATA_DIR',str(tmp_path / 'data'))
    monkeypatch.setenv('IMPORT_ROOT',str(tmp_path / 'imports'))
    store = Store(f'sqlite:///{tmp_path}/gate.db')
    app = create_app(store=store,runbooks=Books(),monitor=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'X-Operator-Token':'test-operator'}) as client:
        caps = (await client.get('/capabilities')).json()
        assert not caps['code_execution_enabled']
        assert (await client.post('/continuations',json={'repository':'unused','requirements':'Restore the original behavior'})).status_code == 503
        incident,_ = store.create('code-import','code','unused',{})
        store.update(incident['id'],status='blocked')
        assert (await client.post('/incidents/'+incident['id']+'/retry')).status_code == 503
        assert store.get(incident['id'])['status'] == 'blocked'
    store.engine.dispose()

import importlib.util
import json
import os
import subprocess
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient


def load_supervisor(tmp_path, monkeypatch):
    monkeypatch.setenv('SUPERVISOR_DB', str(tmp_path / 'supervisor.db'))
    monkeypatch.setenv('SUPERVISOR_RECOVERY_TOKEN', 'supervisor-test-token')
    spec = importlib.util.spec_from_file_location('worker_supervisor_test',Path(__file__).resolve().parents[2] / 'examples/worker-supervisor/app.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_restart_gates_and_uncertain_intent(tmp_path, monkeypatch):
    module = load_supervisor(tmp_path,monkeypatch)
    state = {'revision':'a'*64,'worker':{'running':False}}
    calls = []
    monkeypatch.setattr(module,'snapshot',lambda:state.copy())
    def restart(*args):
        calls.append(args)
        raise module.HTTPException(503,'Daemon unavailable')
    monkeypatch.setattr(module,'docker',restart)
    with TestClient(module.app) as c:
        h = {'X-Recovery-Token':'supervisor-test-token'}
        body = {'request_id':'safe-request-id','expected_revision':'a'*64}
        assert c.post('/internal/restart',json=body).status_code == 401
        assert c.post('/internal/restart',json={**body,'container':'other'},headers=h).status_code == 422
        assert c.post('/internal/restart',json={**body,'expected_revision':'b'*64},headers=h).status_code == 409
        assert c.post('/internal/restart',json=body,headers=h).status_code == 503
        assert c.post('/internal/restart',json=body,headers=h).status_code == 409
        assert calls == [('restart','--time','10',module.name)]


@pytest.mark.skipif(os.getenv('RUN_DOCKER_TESTS') != '1', reason='Opt-in disposable Docker worker')
def test_real_fixed_container_restart(tmp_path, monkeypatch):
    name = 'ctrlz-supervisor-test-'+uuid.uuid4().hex[:10]
    monkeypatch.setenv('CTRLZ_WORKER_CONTAINER',name)
    image = 'campuspass-api:latest'
    check = subprocess.run(['docker','image','inspect',image],capture_output=True)
    if check.returncode:
        pytest.skip('Build optional CampusPass image before this Docker acceptance test')
    subprocess.run(['docker','run','-d','--name',name,'--network','none','--entrypoint','python',image,'-m','http.server','18888'],check=True,capture_output=True)
    try:
        subprocess.run(['docker','stop','--time','1',name],check=True,capture_output=True)
        module = load_supervisor(tmp_path,monkeypatch)
        with TestClient(module.app) as c:
            h = {'X-Recovery-Token':'supervisor-test-token'}
            before = c.get('/internal/state',headers=h).json()
            assert not before['worker']['running']
            body = {'request_id':'restart-real-container','expected_revision':before['revision']}
            response = c.post('/internal/restart',json=body,headers=h)
            assert response.status_code == 200 and response.json()['worker']['running']
            assert c.get('/health').json()['ready']
            assert c.post('/internal/restart',json=body,headers=h).json() == response.json()
            assert c.post('/internal/restart',json={**body,'request_id':'new-running-request'},headers=h).status_code == 409
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True)

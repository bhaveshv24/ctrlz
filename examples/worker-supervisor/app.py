"""Run on a trusted Docker host. Authorizes exactly one configured worker restart."""
import hashlib
import json
import os
import re
import secrets
import sqlite3
import subprocess
import threading
from pathlib import Path
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

name = os.environ.get('CTRLZ_WORKER_CONTAINER', 'ctrlz-checkout-demo')
if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}', name):
    raise ValueError('Invalid fixed worker container name')
path = Path(os.environ.get('SUPERVISOR_DB', './supervisor.db'))
lock = threading.Lock()
app = FastAPI(title='Fixed worker recovery supervisor')
with sqlite3.connect(path) as db:
    db.execute('CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY, revision TEXT, result TEXT)')


def auth(x_recovery_token: str = Header(default='')):
    expected = os.environ.get('SUPERVISOR_RECOVERY_TOKEN', '')
    if not expected or not secrets.compare_digest(expected, x_recovery_token):
        raise HTTPException(401, 'Recovery token required')


def docker(*args):
    result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=25)
    if result.returncode:
        raise HTTPException(503, 'Configured worker or Docker daemon unavailable; escalate to operator')
    return result.stdout + (result.stderr if args[0] == "logs" else "")


def snapshot():
    raw = json.loads(docker('inspect', name))[0]
    state = raw['State']
    identity = {k:state.get(k) for k in ['Status','Running','StartedAt','FinishedAt','ExitCode']}
    return {'revision':hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest(),
            'worker':{'name':name,'running':bool(state['Running']),'status':state['Status']},
            'deployment':{'image':raw['Config']['Image'],'created':raw['Created']},
            'metrics':{'restart_count':raw['RestartCount'],'exit_code':state['ExitCode']}}


@app.get('/health')
def health():
    state = snapshot()
    return {'ready':state['worker']['running']}


@app.get('/internal/state', dependencies=[Depends(auth)])
def diagnostics():
    state = snapshot()
    # Logs are read-only and bounded; no user-provided commands or container names.
    state['logs'] = docker('logs', '--tail', '30', name)[-6000:]
    return state


class Restart(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: str = Field(min_length=8,max_length=100)
    expected_revision: str = Field(min_length=64,max_length=64)


@app.post('/internal/restart', dependencies=[Depends(auth)])
def restart(body: Restart):
    with lock, sqlite3.connect(path) as db:
        previous = db.execute('SELECT revision,result FROM operations WHERE id=?',(body.request_id,)).fetchone()
        if previous:
            if previous[0] != body.expected_revision:
                raise HTTPException(409,'Request ID reused with a different revision')
            # Persisted intent with no result is uncertain: never blindly restart again.
            if not previous[1]:
                raise HTTPException(409,'Prior restart outcome uncertain; inspect worker and reconcile manually')
            return json.loads(previous[1])
        before = snapshot()
        if before['revision'] != body.expected_revision or before['worker']['running']:
            raise HTTPException(409,'Worker state changed or worker already running')
        db.execute('INSERT INTO operations VALUES(?,?,NULL)',(body.request_id,body.expected_revision))
        db.commit()
        docker('restart', '--time', '10', name)
        after = snapshot()
        db.execute('UPDATE operations SET result=? WHERE id=?',(json.dumps(after),body.request_id))
        db.commit()
        return after

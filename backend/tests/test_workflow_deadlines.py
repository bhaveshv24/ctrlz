import copy,time
import pytest
from sqlalchemy import select
from test_workflow_observability import env,active,event,send,tasks
from ctrlz.workflow_deadlines import DeadlineCheck


async def targeted(env,monkeypatch):
    p=await active(env,monkeypatch);w=env[0].state.workflows
    stored=w.proposal(p['id']);stored['activation']['check_mode']='deadline_targeted';w.save_proposal(stored)
    return stored,w


def result(p,item,state='pending'):
    e=event(p,kind='workflow.reconciled',state=state)
    e['workflow'].update(instance_id=item['instance_id'],resource_id=item['resource_id'],started_at=item['started_at'],check_id=item['check_id'],check_lease=item['lease'])
    return e


async def test_999_completions_cancel_checks_one_overdue_read(env,monkeypatch):
    p,w=await targeted(env,monkeypatch);base=time.time();w.clock=lambda:base
    for start in range(0,1000,50):
        await send(env,[event(p,n=n,kind='workflow.started',timestamp=base-1) for n in range(start+1,start+51)],source='app')
    # Use a separate source minute bucket for this local transport-budget test.
    from ctrlz.runtime_store import RuntimeRate
    with env[2].sessions.begin() as db:
        row=db.get(RuntimeRate,'workflow-test/local/app');row.events=0
    for start in range(1,1000,50):
        await send(env,[event(p,n=n,kind='workflow.completed',timestamp=base) for n in range(start+1,min(start+51,1001))],source='app')
    assert w.deadlines.claim('workflow-test','local','state') is None
    w.clock=lambda:base+2
    item=w.deadlines.claim('workflow-test','local','state');assert item['instance_id']=='job-1'
    assert w.deadlines.claim('workflow-test','local','state') is None
    response=result(p,item);response['timestamp']=base+2
    await send(env,[response])
    assert len(env[2].incidents())==1
    assert w.deadlines.claim('workflow-test','local','state') is None
    repeated=await send(env,[response]);assert repeated['duplicates']==1


async def test_stale_result_after_completion_rejected(env,monkeypatch):
    p,w=await targeted(env,monkeypatch)
    await send(env,[event(p,kind='workflow.started',timestamp=time.time()-10)],source='app')
    item=w.deadlines.claim('workflow-test','local','state');assert item
    await send(env,[event(p,kind='workflow.completed')],source='app')
    await send(env,[result(p,item)],expected=409)
    assert env[2].incidents()==[]


async def test_lost_completion_is_confirmed_complete_without_incident(env,monkeypatch):
    p,w=await targeted(env,monkeypatch)
    await send(env,[event(p,kind='workflow.started',timestamp=time.time()-10)],source='app')
    item=w.deadlines.claim('workflow-test','local','state')
    await send(env,[result(p,item,'completed')])
    assert env[2].incidents()==[] and w.db.summary(p['id'])['counts']=={'completed':1}


async def test_missing_record_unknown_is_not_failure(env,monkeypatch):
    p,w=await targeted(env,monkeypatch)
    await send(env,[event(p,kind='workflow.started',timestamp=time.time()-10)],source='app')
    item=w.deadlines.claim('workflow-test','local','state')
    await send(env,[result(p,item,'unknown')])
    assert env[2].incidents()==[] and w.deadlines.claim('workflow-test','local','state') is None


async def test_lease_expiry_restart_and_attempt_budget(env,monkeypatch):
    p,w=await targeted(env,monkeypatch)
    await send(env,[event(p,kind='workflow.started',timestamp=time.time()-10)],source='app')
    first=w.deadlines.claim('workflow-test','local','state');now=time.time()
    from ctrlz.workflow_deadlines import Deadlines
    restarted=Deadlines(w)
    for n in range(1,4):
        w.clock=lambda:now+n*31
        item=restarted.claim('workflow-test','local','state')
        assert bool(item)==(n<3)
    assert env[2].incidents()==[]


async def test_wrong_source_and_unsolicited_snapshot_rejected(env,monkeypatch):
    p,w=await targeted(env,monkeypatch)
    await send(env,[event(p,kind='workflow.started',timestamp=time.time()-10)],source='app')
    assert w.deadlines.claim('other-project','local','state') is None
    assert w.deadlines.claim('workflow-test','local','app') is None
    await send(env,[event(p)],expected=409)

def test_targeted_lookup_requires_unique_index_and_reads_one_record(tmp_path):
    import importlib.util,sqlite3
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('targeted_checker',Path(__file__).resolve().parents[2]/'scripts/workflow_deadline_checker.py')
    checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
    path=tmp_path/'jobs.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY, resource_id TEXT,status TEXT,created REAL)')
        db.executemany('INSERT INTO jobs VALUES(?,?,?,?)',[(str(n),'resource-'+str(n),'pending' if n==1 else 'completed',1) for n in range(1000)])
    before=path.read_bytes()
    assert checker.lookup(path,'jobs','id','resource_id','status','created','1')['status']=='pending'
    assert checker.lookup(path,'jobs','id','resource_id','status','created','missing') is None
    assert path.read_bytes()==before
    with pytest.raises(ValueError):checker.lookup(path,'jobs','resource_id','resource_id','status','created','resource-1')

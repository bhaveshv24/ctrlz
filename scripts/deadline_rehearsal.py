"""Reprocess the real 1,000-operation fixture evidence in an isolated deadline monitor.

No simulated success/failure records: source events and DB are from the observed
workflow demo. This is evidence replay plus real targeted reads, not a fresh load test.
"""
import asyncio,json,os,time,sys
from pathlib import Path
import httpx
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from ctrlz.main import create_workspace_app
from ctrlz.store import Store
from ctrlz.workflow_store import AuditRow,ProposalRow
from ctrlz.reasoning import NIMReasoner
from ctrlz.runbooks import Runbooks
from workflow_deadline_checker import lookup


async def main():
    source=ROOT/'backend/data/workflow-demo';dest=ROOT/'backend/data/deadline-rehearsal'
    dest.mkdir(parents=True,exist_ok=True)
    if (dest/'result.json').exists():raise RuntimeError('Preserving prior result; use its report rather than overwriting')
    for k,v in dotenv_values(ROOT/'.env').items():
        if v is not None:os.environ[k]=v
    os.environ['CTRLZ_OPERATOR_TOKEN']='isolated-deadline-rehearsal';os.environ['DATA_DIR']=str(dest)
    old=Store('sqlite:///'+str(source/'ctrlz.db'))
    from ctrlz.workflow_store import WorkflowStorage
    storage=WorkflowStorage(old)
    p=next(p for p in storage.proposals() if p.get('patch') and p.get('approval'))
    a=storage.get(AuditRow,p['audit_id']);config=old.project(p['project_id'])
    store=Store('sqlite:///'+str(dest/'ctrlz.db'));store.save_project(config)
    app=create_workspace_app(store=store,reasoner=NIMReasoner(),runbooks=Runbooks(ROOT/'runbooks',dest/'chroma'),monitor=False)
    w=app.state.workflows
    p['activation'].update(check_mode='deadline_targeted',last_event=None,primary_event_seen=False)
    p['status']='deployment_observed';p.pop('scan_cursor',None);p['admissions']=0
    w.db.save(AuditRow,a['id'],a);w.save_proposal(p)
    w.file(a['id'],'source.json').write_text((source/'control-data/workflow-observability'/a['id']/'source.json').read_text())
    for sid in ['app','state']:w.runtime.secrets.provision(p['project_id'],p['deployment_id'],sid)
    events=[json.loads(line) for line in (source/'application-stdout.jsonl').read_text().splitlines() if line.startswith('{')]
    assert len(events)==1999
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://test',timeout=60) as client:
        base='/telemetry/'+p['project_id']+'/'+p['deployment_id']+'/'
        app_headers={'Authorization':'Bearer '+w.runtime.secrets.get(p['project_id'],p['deployment_id'],'app')}
        for offset in range(0,len(events),50):
            while True:
                r=await client.post(base+'app',headers=app_headers,json={'events':events[offset:offset+50]})
                if r.status_code==429:
                    print('Respecting source rate limit during real-evidence replay.',flush=True);await asyncio.sleep(60);continue
                r.raise_for_status();break
        before=w.db.summary(p['id'])['counts'];assert before=={'completed':999,'pending':1},before
        checked=0
        item=w.deadlines.claim(p['project_id'],p['deployment_id'],'state');assert item
        record=lookup(source/'application-data/jobs.db','jobs','id','resource_id','status','created',item['instance_id']);checked+=1
        assert record['resource_id']=='resource-0001' and record['status']=='pending'
        response={'event_id':'deadline-real-'+item['check_id'],'timestamp':time.time(),'severity':'info','message':'Real targeted indexed database check during evidence replay',
            'workflow':{'audit_id':p['id'],'workflow_id':p['rule']['id'],'kind':'workflow.reconciled','instance_id':item['instance_id'],'resource_id':item['resource_id'],'started_at':record['created'],'state':record['status'],'revision':item['revision'],'artifact_digest':item['artifact_digest'],'check_id':item['check_id'],'check_lease':item['lease']}}
        state_headers={'Authorization':'Bearer '+w.runtime.secrets.get(p['project_id'],p['deployment_id'],'state')}
        r=await client.post(base+'state',headers=state_headers,json={'events':[response]});r.raise_for_status()
        r=await client.post(base+'state',headers=state_headers,json={'events':[response]});r.raise_for_status();assert r.json()['duplicates']==1
        assert w.deadlines.claim(p['project_id'],p['deployment_id'],'state') is None
        if app.state.tasks:await asyncio.gather(*list(app.state.tasks))
        incidents=store.incidents();assert len(incidents)==1
        incident=incidents[0]
        result={'mode':'Replay of genuine previously executed HTTP workflow evidence plus real read-only state lookup','operations':1000,'completed':999,'incomplete':1,'application_state_lookups':checked,'completed_operation_lookups':0,'full_table_scans':0,'incident_id':incident['id'],'incident_status':incident['status'],'affected_resource':incident['workflow_evidence']['resource_id'],'model':incident.get('model'),'diagnosis':incident.get('diagnosis'),'recovery_executed':bool(incident.get('operation_intents'))}
        (dest/'result.json').write_text(json.dumps(result,indent=2));(dest/'receipt.json').write_text(json.dumps(app.state.engine.receipt(incident['id']),indent=2))
        print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':asyncio.run(main())

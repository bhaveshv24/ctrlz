import importlib.util,time
from pathlib import Path
import httpx
from test_workflow_observability import env,send,event
from test_workflow_deadlines import targeted,result


async def test_authenticated_long_poll_dispatch_and_result(env,monkeypatch):
    p,w=await targeted(env,monkeypatch)
    await send(env,[event(p,kind='workflow.started',timestamp=time.time()-10)],source='app')
    app,c,store,tokens,_=env
    path='/telemetry/workflow-test/local/state?transport=long_poll'
    assert (await c.get(path)).status_code==401
    r=await c.get(path,headers={'Authorization':'Bearer '+tokens['state']});assert r.status_code==200
    item=r.json()['check'];assert item['instance_id']=='job-1'
    await send(env,[result(p,item)])
    assert len(store.incidents())==1


async def test_public_gateway_denies_all_control_routes():
    path=Path(__file__).resolve().parents[2]/'scripts/telemetry_gateway.py'
    spec=importlib.util.spec_from_file_location('gateway_test',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    app=module.create_gateway('http://127.0.0.1:18070',{'/telemetry/operator/hosted/render/app','/telemetry/operator/hosted/render/state'})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://test') as c:
        for route in ['/','/auth/login','/projects','/incidents/x/approve','/docs','/telemetry/operator/another/render/app']:
            assert (await c.get(route)).status_code==404
        assert (await c.delete('/telemetry/operator/hosted/render/app')).status_code==404
        assert (await c.get('/telemetry/operator/hosted/render/app')).status_code==400


async def test_recovery_handoff_binds_existing_adapter_to_same_deployment(env):
    from ctrlz.models import Project
    app,c,store,_,_=env
    from test_workflow_observability import OP,proposal,tasks
    p=await proposal(env)
    config=store.project('workflow-test');config['repository_monitoring']['deployments'][0]['application_url']='https://campus.example.com';store.save_project(config)
    runtime,created=store.create('workflow-test','runtime','order-failure',{'runtime_event':{'deployment_id':'local'}})
    oid='11111111-1111-1111-1111-111111111111'
    store.update(runtime['id'],workflow_evidence={'proposal_id':p['id'],'resource_id':oid})
    recovery=Project(id='recovery',name='Explicit recovery',adapter='campuspass-v1',base_url='https://campus.example.com',automatic_detection=False).model_dump()
    store.save_project(recovery)
    r=await c.post('/incidents/'+runtime['id']+'/workflow-recovery',headers=OP,json={'project_id':'recovery'})
    assert r.status_code==200 and r.json()['execution_authorized'] is False
    await tasks(app)
    target=store.get(r.json()['incident_id'])
    assert target['resource']==oid and target['project_id']=='recovery' and not target.get('operation_intents')
    recovery['base_url']='https://other.example.com';store.save_project(recovery)
    r=await c.post('/incidents/'+runtime['id']+'/workflow-recovery',headers=OP,json={'project_id':'recovery'})
    assert r.status_code==403


async def test_recovery_only_project_does_not_poll_application(env):
    from ctrlz.models import Project
    app,c,store,_,_=env
    store.save_project(Project(id='recovery',name='Explicit recovery',adapter='campuspass-v1',base_url='https://never-polled.example.com',automatic_detection=False).model_dump())
    await app.state.scan()
    assert store.probes('recovery')==[]

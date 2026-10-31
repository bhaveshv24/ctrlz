"""Runtime integration tests use an explicitly labeled deterministic reasoner.

Live NVIDIA and real file-collector evidence are rehearsed separately.
"""
import base64
import copy
import hashlib
import hmac
import json
import time
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from ctrlz.main import create_app
from ctrlz.models import Project
from ctrlz.runtime_models import EventBatch, RepositoryMonitoring, RuntimeAssessment
from ctrlz.runtime_source import SourceEvidence
from ctrlz.runtime_store import RuntimeStorage
from ctrlz.store import Store
from test_core import EmptyRunbooks

SHA='a'*40
OTHER_SHA='b'*40
HEADERS={'X-Operator-Token':'runtime-test-operator'}


def project(**changes):
    result={'id':'runtime-demo','name':'Runtime demo','project_type':'repository-deployment','adapter':'runtime-v1','enabled':True,'repository_monitoring':{'github_url':'https://github.com/example/runtime-demo','deployments':[{'id':'staging','platform':'vps','service_id':'worker','environment':'staging','commit_sha':SHA,'sources':[{'id':'logs','connector':'generic-events'}]}]}}
    result.update(changes)
    return result


def event(event_id='event-1',**changes):
    return {'event_id':event_id,'timestamp':time.time(),'severity':'error','error_type':'TypeError','message':'Cannot compare capacity with string input','frames':[{'path':'reservation.py','line':2,'function':'can_reserve'}],**changes}


class RuntimeReasoner:
    provider='explicit deterministic runtime test fixture; no live AI'
    selected_model='fixture'
    async def runtime_assess(self,evidence):
        assert evidence['execution_permissions']==[]
        return RuntimeAssessment(diagnosis='Observed TypeError; source evidence must determine whether validation is missing.',uncertainties=['Production reproduction has not been executed.'],recommendations=[{'id':'validate-input','category':'code_patch','summary':'Investigate input validation','rationale':'The captured exception identifies a comparison failure.','evidence_ids':evidence['evidence_ids'][:1],'risks':['Caller contract remains unknown.'],'verification_plan':['Reproduce mixed-type input and verify intended behavior.']}])


def github_transport(request):
    if '/commits/' in request.url.path:
        sha=request.url.path.rsplit('/',1)[1]
        return httpx.Response(200,json={'sha':sha,'files':[{'filename':'reservation.py','status':'modified','patch':'@@ -1 +1 @@\n-return available > requested\n+return available >= requested'}]})
    if '/contents/' in request.url.path:
        assert request.url.params['ref'] in {SHA,OTHER_SHA}
        return httpx.Response(200,json={'type':'file','size':70,'encoding':'base64','content':base64.b64encode(b'def can_reserve(available, requested):\n    return available >= requested\n').decode()})
    return httpx.Response(200,json={'full_name':'example/runtime-demo'})


@pytest.fixture
async def env(tmp_path,monkeypatch):
    monkeypatch.setenv('CTRLZ_OPERATOR_TOKEN','runtime-test-operator')
    monkeypatch.setenv('DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setenv('IMPORT_ROOT',str(tmp_path/'imports'))
    monkeypatch.delenv('CTRLZ_RUNTIME_LOCAL_REPOS',raising=False)
    store=Store(f'sqlite:///{tmp_path}/runtime.db')
    outbound=httpx.AsyncClient(transport=httpx.MockTransport(github_transport))
    app=create_app(store=store,client=outbound,reasoner=RuntimeReasoner(),runbooks=EmptyRunbooks(),monitor=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://test') as client:
        r=await client.post('/projects',headers=HEADERS,json=project());assert r.status_code==200,r.text
        r=await client.post('/projects/runtime-demo/runtime/sources/provision',headers=HEADERS,json={'deployment_id':'staging','source_id':'logs'});assert r.status_code==200
        token=Path(r.json()['credential_file']).read_text()
        yield app,client,store,{'Authorization':'Bearer '+token},token
        if app.state.tasks:await __import__('asyncio').gather(*list(app.state.tasks))
    await outbound.aclose();store.engine.dispose()


async def ingest(env,events,headers=None,path='/telemetry/runtime-demo/staging/logs'):
    app,client,store,credentials,_=env
    result=await client.post(path,headers=headers if headers is not None else credentials,json={'events':events})
    if app.state.tasks:await __import__('asyncio').gather(*list(app.state.tasks))
    return result


def test_existing_projects_default_to_http():
    p=Project(id='old',name='Old HTTP',base_url='http://localhost:8001')
    assert p.project_type=='http' and p.repository_monitoring is None
    assert Project.model_validate(project()).base_url is None


@pytest.mark.parametrize('change',[{'adapter':'unknown'},{'base_url':'http://localhost:8001'},{'contract':{'allowed':['restart']}},{'demo_enabled':True},{'project_type':'http'}])
def test_runtime_contract_rejects_unsafe_or_ambiguous_configuration(change):
    with pytest.raises(ValidationError):Project.model_validate(project(**change))


@pytest.mark.parametrize('url',['https://evil.test/repo/name','https://user:secret@github.com/owner/repo','owner','../escape','https://github.com/../escape'])
def test_invalid_repository(url):
    data=project();data['repository_monitoring']['github_url']=url
    with pytest.raises(ValidationError):Project.model_validate(data)


@pytest.mark.parametrize('platform',['unknown','cloudwatch'])
def test_unknown_provider_is_not_decoratively_connected(platform):
    data=project();data['repository_monitoring']['deployments'][0]['platform']=platform
    with pytest.raises(ValidationError):Project.model_validate(data)


async def test_actual_event_creates_incident_source_mapping_and_pending_review(env):
    result=await ingest(env,[event()]);assert result.status_code==200
    app,client,store,_,_=env
    assert len(store.incidents())==1
    incident=store.incidents()[0]
    assert incident['kind']=='runtime' and incident['status']=='awaiting_review'
    assert incident['source_evidence']['commit_sha']==SHA
    assert incident['source_evidence']['files'][0]['context'].endswith('return available >= requested')
    assert incident['verification']['passed'] is False
    receipt=(await client.get('/incidents/'+incident['id']+'/receipt',headers=HEADERS)).json()
    assert receipt['success'] is False and not receipt['replay_supported']
    assert not any(e['stage']=='operation_intent' for e in receipt['events'])
    assert (await client.post('/incidents/'+incident['id']+'/approve',headers=HEADERS,json={'approval_hash':'a'*64})).status_code==409


async def test_authentication_and_wrong_source_binding(env):
    assert (await ingest(env,[event()],headers={})).status_code==401
    assert (await ingest(env,[event()],headers={'Authorization':'Bearer wrong'})).status_code==401
    assert (await ingest(env,[event()],path='/telemetry/other/staging/logs')).status_code==404
    assert (await ingest(env,[event()],path='/telemetry/runtime-demo/production/logs')).status_code==404
    assert (await ingest(env,[event()],path='/telemetry/runtime-demo/staging/other')).status_code==404


async def test_schema_size_and_unsafe_paths(env):
    bad=event();bad['command']='rm -rf anything'
    assert (await ingest(env,[bad])).status_code==422
    assert (await ingest(env,[event(frames=[{'path':'../../.env','line':1}])])).status_code==422
    assert (await ingest(env,[event(message='x'*9000)])).status_code==422
    _,client,_,headers,_=env
    assert (await client.post('/telemetry/runtime-demo/staging/logs',headers=headers,content=b'x'*262145)).status_code==413
    assert (await ingest(env,[event(str(n)) for n in range(51)])).status_code==422


async def test_idempotency_conflict_and_grouping_multiple_users(env):
    e=event(user_id='student@example.com',request_id='request-one')
    assert (await ingest(env,[e])).json()['accepted']==1
    assert (await ingest(env,[e])).json()['duplicates']==1
    assert (await ingest(env,[{**e,'message':'different error'}])).status_code==409
    assert (await ingest(env,[event('event-2',user_id='other@example.com',request_id='request-two')])).status_code==200
    store=env[2];assert len(store.incidents())==1
    incident=store.incidents()[0];assert incident['runtime_summary']['events']==2 and incident['runtime_summary']['affected_users']==2
    raw=RuntimeStorage(store).rows(project_id='runtime-demo')
    assert all('@' not in row['user_id'] for row in raw)


async def test_deployments_and_different_errors_remain_separate(env):
    app,client,store,credentials,_=env
    data=project();other=copy.deepcopy(data['repository_monitoring']['deployments'][0]);other['id']='production';other['environment']='production';other['commit_sha']=OTHER_SHA;data['repository_monitoring']['deployments'].append(other)
    assert (await client.post('/projects',headers=HEADERS,json=data)).status_code==200
    r=await client.post('/projects/runtime-demo/runtime/sources/provision',headers=HEADERS,json={'deployment_id':'production','source_id':'logs'})
    other_headers={'Authorization':'Bearer '+Path(r.json()['credential_file']).read_text()}
    assert (await ingest(env,[event()])).status_code==200
    assert (await ingest(env,[event()],headers=other_headers,path='/telemetry/runtime-demo/production/logs')).status_code==200
    assert (await ingest(env,[event('different',error_type='ConnectionError')])).status_code==200
    assert len(store.incidents())==3
    assert (await ingest(env,[event('wrong')],path='/telemetry/runtime-demo/production/logs')).status_code==401


async def test_no_data_and_ordinary_warnings_do_not_imply_health(env):
    _,client,store,_,_=env
    coverage=(await client.get('/projects/runtime-demo/runtime',headers=HEADERS)).json()['deployments'][0]
    assert coverage['state']=='no_recent_events'
    assert (await ingest(env,[event(severity='warning',error_type=None,frames=[],http_status=404)])).status_code==200
    assert store.incidents()==[]
    overview=(await client.get('/overview',headers=HEADERS)).json()
    assert overview['projects'][0]['state']=='observing' # Evidence arrived; health still explicitly unknown.
    assert 'healthy' not in json.dumps(overview['projects'][0])


async def test_three_http_failures_and_out_of_order_events(env):
    first=event('one',timestamp=time.time()-20,severity='info',error_type=None,frames=[],http_status=503,route='/api/items/123?token=private')
    assert (await ingest(env,[first])).status_code==200
    assert env[2].incidents()==[]
    await ingest(env,[{**first,'event_id':'two','timestamp':first['timestamp']-1}])
    assert env[2].incidents()==[]
    await ingest(env,[{**first,'event_id':'three','timestamp':first['timestamp']+1}])
    assert len(env[2].incidents())==1
    assert env[2].incidents()[0]['runtime_summary']['affected_users'] is None


async def test_redaction_before_database_and_model(env):
    _,_,store,_,token=env
    e=event(message='password=hunter2 api_key=secret123 email=student@example.com Authorization: Bearer abcdefghijkl '+token,stack='access_token=abcdefg\nCookie: session=topsecret',user_id='real-person@example.com',route='/api?password=hidden')
    assert (await ingest(env,[e])).status_code==200
    content=json.dumps(RuntimeStorage(store).rows())+json.dumps(store.incidents())+json.dumps(store.events())
    for value in ['hunter2','secret123','student@example.com','abcdefghijkl',token,'topsecret','real-person@example.com','password=hidden']:
        assert value not in content


async def test_review_is_exact_stale_safe_and_never_executes(env):
    _,client,store,_,_=env
    await ingest(env,[event()]);incident=store.incidents()[0];r=incident['runtime_recommendations'][0]
    path='/incidents/'+incident['id']+'/recommendations/review'
    payload={'recommendation_id':r['id'],'review_hash':'0'*64,'decision':'accept'}
    assert (await client.post(path,headers=HEADERS,json=payload)).status_code==409
    payload['review_hash']=r['review_hash']
    assert (await client.post(path,json=payload)).status_code==401
    assert (await client.post(path,headers=HEADERS,json=payload)).status_code==200
    assert store.get(incident['id'])['status']=='recommendation_reviewed'
    assert not store.get(incident['id'])['verification']['passed']
    assert (await client.post(path,headers=HEADERS,json=payload)).status_code==409


async def test_new_evidence_invalidates_review_and_decline_prevents_execution(env):
    _,client,store,_,_=env
    await ingest(env,[event()]);incident=store.incidents()[0];r=incident['runtime_recommendations'][0]
    await ingest(env,[event('later')])
    payload={'recommendation_id':r['id'],'review_hash':r['review_hash'],'decision':'accept'}
    assert (await client.post('/incidents/'+incident['id']+'/recommendations/review',headers=HEADERS,json=payload)).status_code==409
    await client.post('/incidents/'+incident['id']+'/retry',headers=HEADERS,json={})
    if env[0].state.tasks:await __import__('asyncio').gather(*list(env[0].state.tasks))
    r=store.get(incident['id'])['runtime_recommendations'][0]
    assert (await client.post('/incidents/'+incident['id']+'/recommendations/review',headers=HEADERS,json={'recommendation_id':r['id'],'review_hash':r['review_hash'],'decision':'decline'})).status_code==200
    assert store.get(incident['id'])['status']=='escalated'
    assert not any(e['stage']=='operation_intent' for e in store.events())


async def test_handoff_is_context_only_and_requires_auth(env):
    _,client,store,_,_=env
    await ingest(env,[event()]);incident=store.incidents()[0]
    path='/incidents/'+incident['id']+'/repair-context'
    assert (await client.get(path)).status_code==401
    body=(await client.get(path,headers=HEADERS)).json()
    assert body['deployed_revision']==SHA and body['repository']=='https://github.com/example/runtime-demo'
    assert 'No import' in body['boundary']


async def test_disabled_monitor_rejects_events(env):
    _,client,store,_,_=env
    data=project(enabled=False);await client.post('/projects',headers=HEADERS,json=data)
    assert (await ingest(env,[event()])).status_code==409
    assert store.incidents()==[]


async def test_missing_model_credentials_blocks_without_fake_diagnosis(env,monkeypatch):
    from ctrlz.reasoning import NIMReasoner
    monkeypatch.delenv('NVIDIA_API_KEY',raising=False)
    env[0].state.engine.runtime_monitor.reasoner=NIMReasoner()
    await ingest(env,[event()]);incident=env[2].incidents()[0]
    assert incident['status']=='blocked' and not incident.get('diagnosis')
    assert not incident.get('runtime_recommendations')


async def test_source_exact_revision_and_unknown_do_not_use_main():
    paths=[]
    def respond(request):paths.append(str(request.url));return github_transport(request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        source=SourceEvidence(client,github_token='',local_repositories={})
        p=Project.model_validate(project());d=p.repository_monitoring.deployments[0]
        mapping=await source.correlate(p.repository_monitoring,d,{'commit_sha':OTHER_SHA,'frames':[{'path':'reservation.py','line':2}]})
        assert mapping['state']=='exact_github_revision' and mapping['commit_sha']==OTHER_SHA
        assert all('main' not in path for path in paths)
        paths.clear();d.commit_sha=None
        mapping=await source.correlate(p.repository_monitoring,d,{'frames':[]})
        assert mapping['state']=='unknown_revision' and paths==[]


async def test_github_unavailable_discloses_uncertainty():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(503))) as client:
        source=SourceEvidence(client,github_token='',local_repositories={});p=Project.model_validate(project())
        mapping=await source.correlate(p.repository_monitoring,p.repository_monitoring.deployments[0],{'frames':[]})
        assert mapping['state']=='provider_http_503' and mapping['files']==[]


async def test_vercel_signature_and_project_environment_filter(env):
    _,client,store,_,_=env
    data=project();d=data['repository_monitoring']['deployments'][0];d.update(platform='vercel',service_id='prj_verified',deployment_ref='dpl_test',environment='preview',sources=[{'id':'drain','connector':'vercel-drain'}])
    await client.post('/projects',headers=HEADERS,json=data)
    r=await client.post('/projects/runtime-demo/runtime/sources/provision',headers=HEADERS,json={'deployment_id':'staging','source_id':'drain'})
    token=Path(r.json()['credential_file']).read_text()
    row={'id':'vercel-1','timestamp':time.time()*1000,'projectId':'prj_verified','deploymentId':'dpl_test','environment':'preview','source':'lambda','level':'error','message':'Unexpected function failure'}
    raw=json.dumps([row]).encode();signature=hmac.new(token.encode(),raw,hashlib.sha1).hexdigest();url='/telemetry/runtime-demo/staging/drain'
    assert (await client.post(url,content=raw,headers={'x-vercel-signature':'bad'})).status_code==401
    assert (await client.post(url,content=raw,headers={'x-vercel-signature':signature})).status_code==200
    wrong=json.dumps([{**row,'projectId':'other-project'}]).encode()
    assert (await client.post(url,content=wrong,headers={'x-vercel-signature':hmac.new(token.encode(),wrong,hashlib.sha1).hexdigest()})).status_code==403
    assert 'clientIp' not in json.dumps(RuntimeStorage(store).rows())


async def test_rate_limit_is_persistent(env):
    from ctrlz.runtime_store import RuntimeRate
    _,_,store,_,_=env
    with store.sessions.begin() as db:db.add(RuntimeRate(scope='runtime-demo/staging/logs',minute=int(time.time()//60),batches=120,events=0))
    assert (await ingest(env,[event()])).status_code==429


async def test_existing_project_cannot_be_reinterpreted_as_new_type(env):
    _,client,store,_,_=env
    old={'id':'old-http','name':'Existing HTTP','base_url':'http://localhost:8080','enabled':False}
    assert (await client.post('/projects',headers=HEADERS,json=old)).status_code==200
    assert (await client.post('/projects',headers=HEADERS,json=project(id='old-http'))).status_code==409
    assert store.project('old-http')['project_type']=='http'


async def test_event_deployment_reference_must_match_configured_target(env):
    _,client,_,_,_=env
    data=project();data['repository_monitoring']['deployments'][0]['deployment_ref']='actual-staging'
    await client.post('/projects',headers=HEADERS,json=data)
    assert (await ingest(env,[event(deployment_ref='other-production')])).status_code==403


async def test_vercel_metadata_repository_mismatch_is_not_correlated():
    def respond(request):return httpx.Response(200,json={'id':'dpl_test','projectId':'prj_test','target':'production','meta':{'githubCommitSha':SHA,'githubCommitOrg':'another','githubCommitRepo':'repository'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        source=SourceEvidence(client,github_token='',vercel_token='explicit-test-provider-token',local_repositories={})
        data=project();data['repository_monitoring']['deployments'][0].update(platform='vercel',service_id='prj_test',environment='production',deployment_ref='dpl_test')
        p=Project.model_validate(data)
        result=await source.correlate(p.repository_monitoring,p.repository_monitoring.deployments[0],{'frames':[]})
        assert result['state']=='repository_mismatch' and result['files']==[]


async def test_missing_source_maps_disclosed_without_inventing_frames():
    async with httpx.AsyncClient(transport=httpx.MockTransport(github_transport)) as client:
        source=SourceEvidence(client,github_token='',local_repositories={});p=Project.model_validate(project())
        result=await source.correlate(p.repository_monitoring,p.repository_monitoring.deployments[0],{'frames':[{'path':'assets/app.min.js','line':2}]})
        assert any('source maps' in u for u in result['uncertainties'])


async def test_retention_bounds_raw_events_without_deleting_incident_receipts(env):
    _,_,store,_,_=env
    await ingest(env,[event()]);incident=store.incidents()[0]
    storage=RuntimeStorage(store);storage.maximum=1
    first=storage.rows()[0]
    next_event={k:v for k,v in first.items() if k not in {'id','received_at','incident_id'}};next_event['event_id']='retention-new'
    storage.ingest('test-retention',[next_event])
    assert len(storage.rows())==1
    assert store.get(incident['id'])['evidence']['runtime_event']['event_id']=='event-1'
    assert store.events(incident_id=incident['id'])


async def test_account_gateway_binds_collector_to_workspace_and_no_other_permissions(tmp_path,monkeypatch):
    monkeypatch.setenv('DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path}/admin.db')
    monkeypatch.setenv('IMPORT_ROOT',str(tmp_path/'imports'))
    monkeypatch.setenv('CTRLZ_ALLOW_REGISTRATION','true')
    outbound=httpx.AsyncClient(transport=httpx.MockTransport(github_transport))
    app=create_app(client=outbound,reasoner=RuntimeReasoner(),runbooks=EmptyRunbooks(),monitor=False)
    async with app.router.lifespan_context(app),httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://test') as c:
        accounts=[]
        for n in [1,2]:
            r=await c.post('/auth/register',json={'email':f'collector-user-{n}@example.test','password':'collector-test-password-123'})
            assert r.status_code==201
            user=r.json();auth={'Authorization':'Bearer '+user['token']}
            assert (await c.post('/projects',headers=auth,json=project())).status_code==200
            setup=await c.post('/projects/runtime-demo/runtime/sources/provision',headers=auth,json={'deployment_id':'staging','source_id':'logs'})
            assert setup.status_code==200
            secret=Path(setup.json()['credential_file']).read_text()
            assert secret not in setup.text
            accounts.append((user,auth,secret))
        (first,auth,key),(other,other_auth,other_key)=accounts
        endpoint=f"/telemetry/{first['user']['id']}/runtime-demo/staging/logs"
        accepted=await c.post(endpoint,headers={'Authorization':'Bearer '+key},json={'events':[event()]})
        assert accepted.status_code==200,accepted.text
        wrong=f"/telemetry/{other['user']['id']}/runtime-demo/staging/logs"
        assert (await c.post(wrong,headers={'Authorization':'Bearer '+key},json={'events':[event()]})).status_code==401
        assert (await c.get('/projects',headers={'Authorization':'Bearer '+key})).status_code==401
        assert (await c.get('/incidents',headers=other_auth)).json()==[]
        if accepted.json()['incident_ids']:
            incident_id=accepted.json()['incident_ids'][0]
            assert (await c.get('/incidents/'+incident_id,headers=other_auth)).status_code==404
    await outbound.aclose()


async def test_rollback_without_previous_deployment_evidence_is_deterministically_blocked(env):
    class RollbackReasoner(RuntimeReasoner):
        async def runtime_assess(self,evidence):
            result=await super().runtime_assess(evidence)
            result.recommendations[0].category='rollback'
            return result
    env[0].state.engine.runtime_monitor.reasoner=RollbackReasoner()
    await ingest(env,[event()]);incident=env[2].incidents()[0];r=incident['runtime_recommendations'][0]
    assert r['review_policy']['reviewable'] is False
    response=await env[1].post('/incidents/'+incident['id']+'/recommendations/review',headers=HEADERS,json={'recommendation_id':r['id'],'review_hash':r['review_hash'],'decision':'accept'})
    assert response.status_code==409


async def test_operator_source_hints_do_not_invent_stack_frame_lines():
    async with httpx.AsyncClient(transport=httpx.MockTransport(github_transport)) as client:
        source=SourceEvidence(client,github_token='',local_repositories={})
        data=project();data['repository_monitoring']['deployments'][0]['source_paths']=['reservation.py']
        p=Project.model_validate(data)
        result=await source.correlate(p.repository_monitoring,p.repository_monitoring.deployments[0],{'frames':[]})
        assert result['files'][0]['line'] is None
        assert 'operator-configured' in result['files'][0]['location_evidence']
        assert any('did not supply stack frames' in u for u in result['uncertainties'])


async def test_invalid_model_citations_have_one_bounded_real_reasoner_revision(env):
    class RevisingReasoner(RuntimeReasoner):
        calls=0
        async def runtime_assess(self,evidence):
            self.calls+=1
            result=await super().runtime_assess(evidence)
            if self.calls==1:result.recommendations[0].evidence_ids=['invented-evidence']
            else:assert evidence.get('validation_feedback')
            return result
    reasoner=RevisingReasoner();env[0].state.engine.runtime_monitor.reasoner=reasoner
    await ingest(env,[event()])
    assert reasoner.calls==2 and env[2].incidents()[0]['status']=='awaiting_review'
    assert sum(e['stage']=='assessment_revision' for e in env[2].events())==1


async def test_immutable_source_cache_is_exact_revision_and_discloses_provider_failure(env,monkeypatch):
    app,client,store,_,_=env
    await ingest(env,[event()]);incident=store.incidents()[0]
    async def unavailable(*args):return None,'github_rate_limited'
    monkeypatch.setattr(app.state.engine.runtime_monitor.source,'get',unavailable)
    assert (await client.post('/incidents/'+incident['id']+'/retry',headers=HEADERS,json={})).status_code==200
    if app.state.tasks:await __import__('asyncio').gather(*list(app.state.tasks))
    result=store.get(incident['id'])
    assert result['source_evidence']['cached_immutable_source'] is True
    assert result['source_evidence']['commit_sha']==SHA
    assert result['source_evidence']['refresh_error']=='github_rate_limited'
    assert result['status']=='awaiting_review'


async def test_partial_source_retrieval_is_disclosed():
    def partial(request):
        return httpx.Response(404) if 'missing.py' in request.url.path else github_transport(request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(partial)) as client:
        source=SourceEvidence(client,github_token='',local_repositories={})
        data=project();data['repository_monitoring']['deployments'][0]['source_paths']=['reservation.py','missing.py']
        p=Project.model_validate(data)
        result=await source.correlate(p.repository_monitoring,p.repository_monitoring.deployments[0],{'frames':[]})
        assert len(result['files'])==1
        assert any('partial' in u for u in result['uncertainties'])


def test_vercel_ndjson_exception_extracts_only_observed_relative_stack():
    from ctrlz.runtime_connectors import VercelDrain
    data=project();data['repository_monitoring']['deployments'][0].update(platform='vercel',service_id='prj_test',environment='preview')
    deployment=Project.model_validate(data).repository_monitoring.deployments[0]
    raw=json.dumps({'id':'provider-event','timestamp':time.time()*1000,'projectId':'prj_test','deploymentId':'dpl_real','environment':'preview','customEnvironment':None,'source':'lambda','level':'error','message':'TypeError: invalid comparison\n at reserve (src/app.ts:24:3)'}).encode()+b'\n'
    secret='explicit-test-signature-secret'
    result=VercelDrain().decode(raw,{'x-vercel-signature':hmac.new(secret.encode(),raw,hashlib.sha1).hexdigest()},secret,deployment)
    assert result.events[0].error_type=='TypeError'
    assert result.events[0].frames[0].path=='src/app.ts'
    assert result.events[0].frames[0].line==24
    assert result.events[0].user_id is None and result.events[0].request_id is None


async def test_reinvestigation_clears_current_review_but_preserves_review_history(env):
    app,client,store,_,_=env
    await ingest(env,[event()]);incident=store.incidents()[0];r=incident['runtime_recommendations'][0]
    await client.post('/incidents/'+incident['id']+'/recommendations/review',headers=HEADERS,json={'recommendation_id':r['id'],'review_hash':r['review_hash'],'decision':'accept'})
    assert store.get(incident['id'])['recommendation_review']['decision']=='accept'
    assert (await client.post('/incidents/'+incident['id']+'/retry',headers=HEADERS,json={})).status_code==200
    if app.state.tasks:await __import__('asyncio').gather(*list(app.state.tasks))
    current=store.get(incident['id'])
    assert current['status']=='awaiting_review' and current['recommendation_review'] is None
    assert any(e['stage']=='recommendation_review' for e in store.events(incident_id=incident['id']))

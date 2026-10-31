"""Deterministic provider tests, plus explicitly real offline Docker verification."""
import ast
import copy
import io
import json
import os
import subprocess
import time
import zipfile
from pathlib import Path
import httpx
import pytest
from ctrlz.main import create_app
from ctrlz.store import Store
from ctrlz.runtime_models import RuntimeAssessment
from ctrlz.workflow_models import AuditAssessment,WorkflowRule,RuleDecision,Activation,PatchPlan
from ctrlz.workflow_source import inspect,unzip,tree_digest,validate_rule
from ctrlz.workflow_patch import compile_patch,verify,validate_business_ast
from ctrlz.workflow_service import WorkflowObservability
from test_core import EmptyRunbooks

FIXTURE=Path(__file__).resolve().parents[2]/'examples/workflow-observability'
FILES={p.name:p.read_text() for p in FIXTURE.glob('*.py')}
OP={'X-Operator-Token':'workflow-unit-operator'}

def rule():
    tree=ast.parse(FILES['jobs.py']);locations=[{'path':'jobs.py','line':n.lineno} for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'submit','process'}]
    return WorkflowRule(id='document-processing',name='Document processing',description='A durable submission should eventually have a completed processing result.',evidence=locations,
        start_condition='submit commits a pending job and returns its id',completion_condition='The same job is completed with its processing result',failure_conditions=['Job remains pending beyond the reviewed deadline'],
        existing_signals=['Durable jobs table status and created timestamp'],missing_signals=['No lifecycle correlation event for the worker early return'],classification='confirmed_gap',technique='instrumentation',deadline_seconds=2,
        allowed_fields=['instance_id','resource_id','user_id'],hooks=[{'path':'jobs.py','function':'submit','role':'start','fields':{'instance_id':'result.id','resource_id':'result.resource_id','user_id':'result.user_id'}},
        {'path':'jobs.py','function':'process','role':'complete','fields':{'instance_id':'arg.job_id','resource_id':'result.resource_id','user_id':'result.user_id'},'completion_key':'result.status','completion_value':'completed'}],
        uncertainties=['The deadline requires developer approval.'],privacy='Only approved IDs; users are pseudonymized before export.',overhead='Bounded background stdout queue; no network in application.',permissions=['Read-only selected jobs table through independent collector'],independent_verification='Compare authoritative durable job status, not missing logs.',coverage_limits=['Lifecycle export is best-effort.','Only this reviewed job workflow is covered.'])

class Reasoner:
    provider='Explicit deterministic workflow unit-test fixture; not NVIDIA'
    selected_model='fixture'
    calls=0
    async def workflow_audit(self,context):
        assert context['source']['anchors'] and all(not s['path'].startswith('.env') for s in context['source']['snippets'])
        return AuditAssessment(summary='Known fixture has a silent pending branch.',workflows=[rule()],limitations=['Deterministic test provider, not live AI'])
    async def workflow_patch(self,context):return PatchPlan(hooks=context['rule']['hooks'],rationale='Exact reviewed observation hooks only')
    async def runtime_assess(self,context):
        self.calls+=1
        assert context['approved_workflow_evidence']['resource_id']
        return RuntimeAssessment(diagnosis='One independently observed durable operation remains pending. No global restart is justified.',uncertainties=['A safe targeted retry contract is not configured.'],recommendations=[{'id':'investigate-job','category':'escalation','summary':'Investigate this specific job','rationale':'Independent durable evidence identifies one resource.','evidence_ids':context['evidence_ids'][:1],'verification_plan':['Read the same authoritative job and confirm the expected result.'],'risks':['Do not replay business side effects without a safe contract.']}])

def archive(files=FILES):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:
        for path,content in files.items():z.writestr(path,content)
    return b.getvalue()

def project():
    return {'id':'workflow-test','name':'Workflow fixture','project_type':'repository-deployment','adapter':'runtime-v1','enabled':True,
        'repository_monitoring':{'github_url':'https://github.com/example/documents','deployments':[{'id':'local','platform':'local','service_id':'documents','environment':'test','sources':[{'id':'app','connector':'generic-events'},{'id':'state','connector':'generic-events'}]}]}}

@pytest.fixture
async def env(tmp_path,monkeypatch):
    monkeypatch.setenv('CTRLZ_OPERATOR_TOKEN',OP['X-Operator-Token']);monkeypatch.setenv('DATA_DIR',str(tmp_path/'data'));monkeypatch.setenv('IMPORT_ROOT',str(tmp_path/'imports'));monkeypatch.setenv('CTRLZ_CODE_EXECUTION_ENABLED','true')
    store=Store('sqlite:///'+str(tmp_path/'ctrlz.db'));reasoner=Reasoner()
    outbound=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(503)))
    app=create_app(store=store,client=outbound,reasoner=reasoner,runbooks=EmptyRunbooks(),monitor=False)
    client=httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://test')
    assert (await client.post('/projects',headers=OP,json=project())).status_code==200
    tokens={}
    for source in ['app','state']:
        r=await client.post('/projects/workflow-test/runtime/sources/provision',headers=OP,json={'deployment_id':'local','source_id':source})
        tokens[source]=Path(r.json()['credential_file']).read_text()
    yield app,client,store,tokens,reasoner
    if app.state.tasks:await __import__('asyncio').gather(*list(app.state.tasks))
    await client.aclose();await outbound.aclose();store.engine.dispose()

async def tasks(app):
    if app.state.tasks:await __import__('asyncio').gather(*list(app.state.tasks))

async def proposal(env):
    app,c,store,tokens,_=env
    response=await c.post('/projects/workflow-test/workflow-audits/snapshot?deployment_id=local&source_id=app',headers=OP,content=archive())
    assert response.status_code==202
    await tasks(app)
    data=(await c.get('/projects/workflow-test/workflow-audits',headers=OP)).json()
    assert data['audits'][0]['status']=='proposed',data
    return data['proposals'][0]

async def approved(env):
    p=await proposal(env);app,c,*_=env
    r=await c.post('/workflow-proposals/'+p['id']+'/decision',headers=OP,json={'proposal_hash':p['proposal_hash'],'decision':'approve'})
    assert r.status_code==200;return r.json()

async def active(env,monkeypatch):
    p=await approved(env);app,c,*_=env
    # Explicit mocked sandbox report for API-state tests. Real Docker is tested separately below.
    monkeypatch.setattr('ctrlz.workflow_patch.verify',lambda *args,**kw:{'passed':True,'checks':{'explicit_unit_test_sandbox_stub':True},'limitations':['Mocked verification only']})
    r=await c.post('/workflow-proposals/'+p['id']+'/generate',headers=OP,json={'approval_hash':p['approval']['hash']});assert r.status_code==202
    await tasks(app);p=app.state.workflows.proposal(p['id']);assert p['status']=='awaiting_deployment',p
    body={'approval_hash':p['approval']['hash'],'revision':'sha256:'+p['patch']['source_digest'],'artifact_digest':p['patch']['instrumentation_digest'],'reconciliation_source_id':'state'}
    r=await c.post('/workflow-proposals/'+p['id']+'/activate',headers=OP,json=body);assert r.status_code==200,r.text
    return r.json()

def event(p,n=1,kind='workflow.reconciled',state='pending',timestamp=None,**fields):
    return {'event_id':f'event-{n}-{kind}-{state}','timestamp':timestamp or time.time(),'severity':'info','message':'Approved workflow observation',
        'workflow':{'audit_id':p['id'],'workflow_id':p['rule']['id'],'kind':kind,'instance_id':f'job-{n}','resource_id':f'resource-{n}',
        'artifact_digest':p['activation']['artifact_digest'],'revision':p['activation']['revision'],**({'started_at':time.time()-10,'state':state} if kind=='workflow.reconciled' else {}),**fields}}

async def send(env,events,source='state',expected=200):
    app,c,store,tokens,_=env
    r=await c.post('/telemetry/workflow-test/local/'+source,headers={'Authorization':'Bearer '+tokens[source]},json={'events':events})
    assert r.status_code==expected,r.text
    await tasks(app);return r.json()

def test_static_source_records_async_gap_and_exact_lines():
    context=inspect(FILES)
    assert any(x['function']=='submit' for x in context['anchors'])
    assert any(x['function']=='process' for x in context['anchors'])
    assert validate_rule(rule(),FILES,context)

def test_statically_swallowed_exception_is_not_invented_as_proof():
    context=inspect({'worker.py':'def task():\n    try: work()\n    except Exception: pass\n'})
    assert context['static_observations'][0]['line']==3
    assert 'review' in context['static_observations'][0]['observation']

def test_existing_observation_and_unsupported_language_are_visible():
    context=inspect({'worker.ts':'queue.process(async job => { logger.info("completed", job.id); });'})
    assert context['languages']==['javascript/typescript'] and not context['anchors']
    assert 'advisory' in ' '.join(context['limits'])

@pytest.mark.parametrize('path',['../escape.py','/absolute.py','tests/../../escape.py'])
def test_snapshot_path_escape_rejected(path):
    with pytest.raises(ValueError):unzip(archive({path:'pass'}))

def test_secret_files_are_not_sent_for_audit():
    files=unzip(archive({**FILES,'.env':'NVIDIA_API_KEY=private-value','credentials.json':'{}'}))
    assert '.env' not in files and 'credentials.json' not in files
    assert 'private-value' not in json.dumps(inspect(files))

def test_unknown_evidence_and_argument_rejected():
    r=rule();r.evidence[0].line=99999
    with pytest.raises(ValueError):validate_rule(r,FILES,inspect(FILES))
    r=rule();r.hooks[0].fields['instance_id']='arg.unknown'
    with pytest.raises(ValueError):validate_rule(r,FILES,inspect(FILES))

def test_patch_preserves_business_ast_and_original_source():
    before=copy.deepcopy(FILES);r=rule();candidate,patch=compile_patch(FILES,r,PatchPlan(hooks=r.hooks,rationale='Unit test constrained plan'),'wf-'+'a'*24,'a'*64)
    assert FILES==before and candidate['test_jobs.py']==FILES['test_jobs.py']
    assert patch['changed_files']==['jobs.py','_ctrlz_observe.py']
    assert not any('resource-0001' in line for line in patch['diff'].splitlines() if line.startswith(('+','-'))) # Context may mention the disclosed fault; no changed line repairs it.
    validate_business_ast(FILES['jobs.py'],candidate['jobs.py'])

def test_arbitrary_business_replacement_and_ai_scope_change_rejected():
    with pytest.raises(ValueError):validate_business_ast('def f(): return 1','def f(): return 2')
    r=rule();hooks=copy.deepcopy(r.hooks);hooks[0].function='connect'
    with pytest.raises(ValueError):compile_patch(FILES,r,PatchPlan(hooks=hooks,rationale='Unsafe scope change'),'wf-'+'b'*24,'a'*64)

async def test_proposal_persisted_before_approval_and_unapproved_generation_denied(env):
    p=await proposal(env);app,c,*_=env
    assert p['status']=='proposed' and p['approval'] is None and p['revision'].startswith('sha256:')
    r=await c.post('/workflow-proposals/'+p['id']+'/generate',headers=OP,json={'approval_hash':'a'*64});assert r.status_code==409

async def test_rejected_proposal_cannot_generate(env):
    p=await proposal(env);app,c,*_=env
    r=await c.post('/workflow-proposals/'+p['id']+'/decision',headers=OP,json={'proposal_hash':p['proposal_hash'],'decision':'reject'});assert r.status_code==200
    r=await c.post('/workflow-proposals/'+p['id']+'/generate',headers=OP,json={'approval_hash':'a'*64});assert r.status_code==409

async def test_edit_deadline_invalidates_approval(env):
    p=await approved(env);app,c,*_=env;r=copy.deepcopy(p['rule']);r['deadline_seconds']+=10
    response=await c.post('/workflow-proposals/'+p['id']+'/decision',headers=OP,json={'proposal_hash':p['proposal_hash'],'decision':'edit','rule':r})
    assert response.status_code==200 and response.json()['approval'] is None and response.json()['proposal_hash']!=p['proposal_hash']
    assert (await c.post('/workflow-proposals/'+p['id']+'/generate',headers=OP,json={'approval_hash':p['approval']['hash']})).status_code==409

async def test_project_revision_change_invalidates_generation(env):
    p=await approved(env);app,c,store,*_=env
    config=project();config['repository_monitoring']['deployments'][0]['commit_sha']='b'*40;store.save_project(config)
    assert (await c.post('/workflow-proposals/'+p['id']+'/generate',headers=OP,json={'approval_hash':p['approval']['hash']})).status_code==409

async def test_missing_ai_is_reported_not_fabricated(env,monkeypatch):
    app,c,*_=env
    async def fail(context):raise RuntimeError('Provider unavailable')
    monkeypatch.setattr(app.state.workflows.runtime.reasoner,'workflow_audit',fail)
    response=await c.post('/projects/workflow-test/workflow-audits/snapshot?deployment_id=local&source_id=app',headers=OP,content=archive())
    await tasks(app);a=app.state.workflows.db.get(__import__('ctrlz.workflow_store',fromlist=['AuditRow']).AuditRow,response.json()['id'])
    assert a['status']=='blocked' and a['proposals']==[]

async def test_activation_requires_matching_artifact_and_events(env,monkeypatch):
    p=await active(env,monkeypatch);assert p['status']=='deployment_observed'
    e=event(p);e['workflow']['revision']='a'*40
    await send(env,[e],expected=409)
    e=event(p);e['workflow']['artifact_digest']='f'*64
    await send(env,[e],expected=409)

async def test_source_and_approved_fields_are_enforced(env,monkeypatch):
    p=await active(env,monkeypatch)
    await send(env,[event(p)],source='app',expected=403)
    e=event(p);e['trace_id']='unapproved-trace'
    await send(env,[e],expected=422)

async def test_completion_before_start_and_duplicate_delivery(env,monkeypatch):
    p=await active(env,monkeypatch);done=event(p,kind='workflow.completed',timestamp=time.time()-1)
    await send(env,[done],source='app');result=await send(env,[done],source='app');assert result['duplicates']==1
    await send(env,[event(p,kind='workflow.started',timestamp=time.time()-2)],source='app')
    assert env[0].state.workflows.db.summary(p['id'])['counts']=={'completed':1}
    assert env[2].incidents()==[]

async def test_missing_completion_is_quality_warning_not_confirmed_failure(env,monkeypatch):
    p=await active(env,monkeypatch)
    await send(env,[event(p,kind='workflow.started',timestamp=time.time()-5)],source='app')
    stored=env[0].state.workflows.proposal(p['id'])
    assert stored.get('monitoring_warning') and env[2].incidents()==[]

async def test_within_deadline_does_not_fail(env,monkeypatch):
    p=await active(env,monkeypatch);e=event(p);e['workflow']['started_at']=e['timestamp']
    await send(env,[e]);assert env[2].incidents()==[]

async def test_stale_source_does_not_confirm_failure(env,monkeypatch):
    p=await active(env,monkeypatch);w=env[0].state.workflows
    w.clock=lambda:time.time()+120
    await send(env,[event(p,kind='workflow.started')],source='app')
    await w.reconcile('workflow-test');assert env[2].incidents()==[]

async def test_one_incomplete_among_1000_no_recent_record_limit(env,monkeypatch):
    p=await active(env,monkeypatch)
    for start in range(0,1000,50):
        events=[event(p,n=n,state='pending' if n==1 else 'completed') for n in range(start+1,start+51)]
        if start==0:events[0]['user_id']='approved-pseudonymous-user'
        await send(env,events)
    summary=env[0].state.workflows.db.summary(p['id'])
    assert summary['counts']=={'pending':1,'completed':999}
    incidents=env[2].incidents();assert len(incidents)==1
    incident=incidents[0];assert incident['workflow_evidence']['resource_id']=='resource-1'
    assert incident['workflow_evidence']['instance_id']=='job-1'
    assert incident['workflow_evidence']['user_id']!='approved-pseudonymous-user'
    assert env[4].calls==1 and incident['status']=='awaiting_review'
    assert not incident.get('operation_intents') and not any(e['stage']=='operation_intent' for e in env[2].events(incident_id=incident['id']))
    assert 'global restart' in incident['diagnosis']
    assert env[0].state.workflows.runtime.coverage(project())[0]['state']=='error_detected'

async def test_monitoring_state_survives_service_restart(env,monkeypatch):
    p=await active(env,monkeypatch);e=event(p,kind='workflow.started')
    await send(env,[e],source='app')
    w=WorkflowObservability(env[0].state.workflows.runtime,env[0].state.workflows.root.parent)
    assert w.db.summary(p['id'])['counts']=={'pending':1}
    assert w.proposal(p['id'])['activation']['revision']==p['activation']['revision']

async def test_unknown_user_remains_unknown_and_explicit_failure_is_scoped(env,monkeypatch):
    p=await active(env,monkeypatch);await send(env,[event(p)])
    i=env[2].incidents()[0]
    assert i['workflow_evidence']['user_id'] is None and i['runtime_summary']['affected_users'] is None
    assert i['verification']['passed'] is False

async def test_authentication_and_unknown_workspace_records(env):
    app,c,*_=env
    assert (await c.get('/projects/workflow-test/workflow-audits')).status_code==401
    assert (await c.post('/workflow-proposals/wf-'+'f'*24+'/decision',headers=OP,json={'proposal_hash':'a'*64,'decision':'approve'})).status_code==404

async def test_periodic_scan_preserves_runtime_monitoring_extension(env):
    await env[0].state.scan()
    assert env[2].incidents()==[]

async def test_optional_workflow_field_preserves_legacy_provider_retry_digest(env):
    from ctrlz.runtime_models import RuntimeEvent
    runtime=env[0].state.workflows.runtime
    p,d,s=runtime.target('workflow-test','local','app')
    incoming={'event_id':'pre-feature-event','timestamp':time.time(),'severity':'info','message':'An ordinary pre-feature provider event'}
    legacy=runtime.normalize(p,d,s,RuntimeEvent.model_validate(incoming));legacy.pop('workflow',None)
    runtime.storage.ingest('workflow-test/local/app',[legacy])
    response=await send(env,[incoming],source='app')
    assert response['duplicates']==1 and response['accepted']==0

async def test_explicit_failure_creates_resource_scoped_incident(env,monkeypatch):
    p=await active(env,monkeypatch)
    await send(env,[event(p,kind='workflow.failed')],source='app')
    assert len(env[2].incidents())==1
    assert env[2].incidents()[0]['workflow_evidence']['observation']=='explicit failure'

async def test_reconciliation_failure_is_degraded_not_business_failure(env,monkeypatch):
    p=await active(env,monkeypatch)
    await send(env,[event(p,kind='workflow.reconciliation_failed',instance_id=None)],source='state')
    current=env[0].state.workflows.proposal(p['id'])
    assert current['status']=='monitoring_degraded' and env[2].incidents()==[]

async def test_stale_authoritative_observation_does_not_confirm_current_failure(env,monkeypatch):
    p=await active(env,monkeypatch)
    e=event(p,timestamp=time.time()-120);e['workflow']['started_at']=time.time()-150
    await send(env,[e]);assert env[2].incidents()==[]
    assert env[0].state.workflows.proposal(p['id'])['status']=='monitoring_degraded'

async def test_reconciliation_without_patch_is_a_supported_preferred_strategy(env):
    p=await proposal(env);app,c,*_=env
    r=copy.deepcopy(p['rule']);r['technique']='read_only_reconciliation';r['hooks']=[]
    response=await c.post('/workflow-proposals/'+p['id']+'/decision',headers=OP,json={'proposal_hash':p['proposal_hash'],'decision':'edit','rule':r});assert response.status_code==200
    p=response.json();response=await c.post('/workflow-proposals/'+p['id']+'/decision',headers=OP,json={'proposal_hash':p['proposal_hash'],'decision':'approve'});p=response.json()
    response=await c.post('/workflow-proposals/'+p['id']+'/activate',headers=OP,json={'approval_hash':p['approval']['hash'],'revision':p['revision'],'artifact_digest':p['proposal_hash'],'reconciliation_source_id':'state'})
    assert response.status_code==200 and not response.json().get('patch')
    await send(env,[event(response.json())]);assert len(env[2].incidents())==1

async def test_duplicate_generation_request_is_rejected(env,monkeypatch):
    p=await approved(env);app,c,*_=env
    monkeypatch.setattr('ctrlz.workflow_patch.verify',lambda *a,**kw:{'passed':True,'checks':{},'limitations':['Mocked sandbox report']})
    body={'approval_hash':p['approval']['hash']}
    first=await c.post('/workflow-proposals/'+p['id']+'/generate',headers=OP,json=body)
    second=await c.post('/workflow-proposals/'+p['id']+'/generate',headers=OP,json=body)
    assert first.status_code==202 and second.status_code==409
    await tasks(app)

async def test_failed_verification_is_not_awaiting_deployment(env,monkeypatch):
    p=await approved(env);app,c,*_=env
    monkeypatch.setattr('ctrlz.workflow_patch.verify',lambda *a,**kw:{'passed':False,'checks':{'candidate_tests':False},'limitations':['Explicit failing sandbox stub']})
    await c.post('/workflow-proposals/'+p['id']+'/generate',headers=OP,json={'approval_hash':p['approval']['hash']});await tasks(app)
    current=app.state.workflows.proposal(p['id']);assert current['status']=='tests_failed'
    response=await c.post('/workflow-proposals/'+p['id']+'/activate',headers=OP,json={'approval_hash':p['approval']['hash'],'revision':'sha256:'+current['patch']['source_digest'],'artifact_digest':current['patch']['instrumentation_digest']})
    assert response.status_code==409

async def test_source_snapshot_tampering_invalidates_generation(env):
    p=await approved(env);app,c,*_=env
    path=app.state.workflows.file(p['audit_id'],'source.json');data=json.loads(path.read_text());data['jobs.py']+='\n# changed\n';path.write_text(json.dumps(data))
    response=await c.post('/workflow-proposals/'+p['id']+'/generate',headers=OP,json={'approval_hash':p['approval']['hash']})
    assert response.status_code==409

@pytest.mark.parametrize('field',['arg.password','result.email','arg.authorization','result.secret_token'])
def test_sensitive_correlation_mapping_is_rejected(field):
    data=rule().model_dump();data['hooks'][0]['fields']['user_id']=field
    with pytest.raises(ValueError):WorkflowRule.model_validate(data)

def test_optional_mapping_is_narrowed_without_broadening_privacy_scope():
    data=rule().model_dump();data['hooks'][0]['fields']['trace_id']='arg.unavailable_trace'
    result=WorkflowRule.model_validate(data)
    assert 'trace_id' not in result.allowed_fields and 'trace_id' not in result.hooks[0].fields
    assert any('Privacy normalization' in x for x in result.coverage_limits)

def test_job_id_never_becomes_user_identity_or_resource_association():
    data=rule().model_dump();data['hooks'][1]['fields'].update(user_id='arg.job_id',resource_id='arg.job_id')
    result=WorkflowRule.model_validate(data)
    assert 'user_id' not in result.hooks[1].fields and 'resource_id' not in result.hooks[1].fields
    assert result.hooks[0].fields['user_id']=='result.user_id'

async def test_exact_github_revision_and_bounded_source_capture():
    import base64
    from ctrlz.runtime_source import SourceEvidence
    from ctrlz.models import Project
    from ctrlz.workflow_source import capture
    cfg=project();cfg['repository_monitoring']['deployments'][0]['commit_sha']='a'*40
    cfg=Project.model_validate(cfg)
    seen=[]
    def provider(request):
        seen.append(str(request.url))
        if '/commits/' in request.url.path:return httpx.Response(200,json={'sha':'a'*40})
        if '/git/trees/' in request.url.path:return httpx.Response(200,json={'tree':[{'type':'blob','mode':'100644','size':len(v),'path':k} for k,v in FILES.items()]})
        path=request.url.path.split('/contents/',1)[1]
        return httpx.Response(200,json={'encoding':'base64','content':base64.b64encode(FILES[path].encode()).decode()})
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
        files,sha,provenance=await capture(SourceEvidence(client,local_repositories={}),cfg.repository_monitoring,cfg.repository_monitoring.deployments[0])
    assert sha=='a'*40 and files==FILES and 'GitHub exact commit' in provenance
    assert not any('main' in url for url in seen)

async def test_source_provider_unavailable_does_not_substitute_main():
    from ctrlz.runtime_source import SourceEvidence
    from ctrlz.models import Project
    from ctrlz.workflow_source import capture
    cfg=project();cfg['repository_monitoring']['deployments'][0]['commit_sha']='a'*40;cfg=Project.model_validate(cfg)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(503))) as client:
        with pytest.raises(ValueError,match='Exact repository revision unavailable'):
            await capture(SourceEvidence(client,local_repositories={}),cfg.repository_monitoring,cfg.repository_monitoring.deployments[0])

def test_read_only_collector_visits_1000_rows_and_rejects_sql(tmp_path):
    import importlib.util,sqlite3
    spec=importlib.util.spec_from_file_location('collector_under_test',Path(__file__).resolve().parents[2]/'scripts/workflow_sqlite_collector.py')
    collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
    path=tmp_path/'jobs.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE jobs(id TEXT,resource TEXT,status TEXT,created REAL)')
        db.executemany('INSERT INTO jobs VALUES(?,?,?,?)',[(str(n),'resource-'+str(n),'pending' if n==0 else 'completed',1) for n in range(1000)])
    before=path.read_bytes();rows=list(collector.snapshots(path,'jobs','id','resource','status','created'))
    assert len(rows)==1000 and rows[0]['status']=='pending' and path.read_bytes()==before
    with pytest.raises(ValueError):list(collector.snapshots(path,'jobs; DROP TABLE jobs','id','resource','status','created'))

def test_real_docker_instrumentation_equivalence(tmp_path,monkeypatch):
    # This test executes imported source only in the same offline Docker Sandbox used by repair.
    socket='/run/user/'+str(os.getuid())+'/docker.sock'
    if not os.getenv('DOCKER_HOST') and Path(socket).exists():monkeypatch.setenv('DOCKER_HOST','unix://'+socket)
    try:r=subprocess.run(['docker','image','inspect','ctrlz-sandbox:local'],capture_output=True,timeout=15)
    except (OSError,subprocess.TimeoutExpired):pytest.skip('Docker unavailable; no host execution fallback')
    if r.returncode:pytest.skip('Existing Python sandbox image unavailable')
    r=rule();candidate,patch=compile_patch(FILES,r,PatchPlan(hooks=r.hooks,rationale='Exact approved plan'),'wf-'+'c'*24,'a'*64)
    result=verify(FILES,candidate,tmp_path/'verification')
    assert result['passed'],result
    assert len(result['baseline']['cases'])==5 and len(result['candidate']['cases'])==5 and len(result['instrumentation']['cases'])==9

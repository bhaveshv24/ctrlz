"""Workflow discovery, exact approval, safe patch export and durable reconciliation."""
import asyncio
import json
import time
import uuid
import copy
from pathlib import Path
from sqlalchemy import select,func,delete
from fastapi import HTTPException
from .runtime_store import digest
from .runtime_security import Redactor
from .workflow_models import WorkflowRule,WorkflowLimits
from .workflow_source import capture,inspect,unzip,validate_rule,tree_digest
from .workflow_store import AuditRow,ProposalRow,InstanceRow,WorkflowStorage
from . import workflow_reasoning,workflow_patch


class WorkflowObservability:
    def __init__(self,runtime,directory,clock=time.time):
        self.runtime=runtime;self.store=runtime.store;self.db=WorkflowStorage(self.store)
        self.root=Path(directory)/'workflow-observability';self.root.mkdir(parents=True,exist_ok=True,mode=0o700);self.root.chmod(0o700)
        self.clock=clock;self.lock=asyncio.Lock();self.jobs=asyncio.Semaphore(2)
        self.limits=WorkflowLimits()
        from .workflow_deadlines import Deadlines
        self.deadlines=Deadlines(self)

    def file(self,audit_id,name):
        if not __import__('re').fullmatch(r'wf-[a-f0-9]{24}',audit_id):raise ValueError('Invalid artifact ID')
        root=self.root/audit_id;root.mkdir(exist_ok=True)
        return root/name

    def files(self,audit_id):return json.loads(self.file(audit_id,'source.json').read_text())

    def save_proposal(self,p):
        self.db.save(ProposalRow,p['id'],p)

    def proposal(self,key):return self.db.get(ProposalRow,key)

    def binding(self,p,rule,project=None):
        project=project or self.store.project(p['project_id'])
        return digest({'project':project,'proposal_id':p['id'],'deployment_id':p['deployment_id'],'environment':p['environment'],
            'revision':p['revision'],'source_digest':p['source_digest'],'rule':rule,'monitoring_only':True})

    def start(self,project_id,deployment_id,source_id):
        project,deployment,source=self.runtime.target(project_id,deployment_id,source_id)
        if source.connector!='generic-events':raise ValueError('Workflow events require a generic authenticated structured-event source')
        with self.store.sessions() as db:
            active=db.scalar(select(func.count()).select_from(AuditRow).where(AuditRow.payload['status'].as_string()=='analyzing'))
        if active>=2:raise ValueError('Two workflow audits are already in progress in this workspace')
        key='wf-'+uuid.uuid4().hex[:24]
        record={'id':key,'project_id':project_id,'deployment_id':deployment_id,'source_id':source_id,'environment':deployment.environment,
            'repository':project.repository_monitoring.github_url,'status':'analyzing','created':self.clock(),'revision':deployment.commit_sha,'proposals':[]}
        self.db.save(AuditRow,key,record);self.store.record('workflow:'+key,'workflow_audit_requested',{'project_id':project_id,'deployment_id':deployment_id})
        return record

    async def analyze(self,key,archive=None):
        async with self.jobs:
            a=self.db.get(AuditRow,key)
            try:
                project,deployment,_=self.runtime.target(a['project_id'],a['deployment_id'],a['source_id'])
                if archive is None:files,revision,provenance=await capture(self.runtime.source,project.repository_monitoring,deployment)
                else:
                    files=unzip(archive);revision='sha256:'+tree_digest(files)
                    provenance='Operator-uploaded inert source snapshot. GitHub identity/deployment commit not independently verified.'
                self.file(key,'source.json').write_text(json.dumps(files))
                context=inspect(files)
                # Keep evidence bounded without cutting JSON or inventing source lines.
                while len(json.dumps(context))>60000 and context['snippets']:context['snippets'].pop()
                a.update(revision=revision,source_digest=tree_digest(files),provenance=provenance,source_context=context)
                self.db.save(AuditRow,key,a)
                answer=await workflow_reasoning.audit(self.runtime.reasoner,{'repository':a['repository'],'revision':revision,'deployment':deployment.model_dump(),'source':context,
                    'observability_goals':['Detect incomplete operations using independent authoritative state where authorized.','Preserve originating request/user correlation when it is available at initiation but lost across an asynchronous boundary.'],
                    'runtime_capabilities':{'structured_event_ingestion':True,'durable_database_access':'Not granted by a source audit; requires independent explicitly authorized collector','custom_application_apis_required':False}})
                if len({r.id for r in answer.workflows})!=len(answer.workflows):raise ValueError('Duplicate workflow IDs')
                ids=[]
                for rule in answer.workflows:
                    validate_rule(rule,files,context)
                    p={k:a[k] for k in ['project_id','deployment_id','source_id','environment','repository','revision','source_digest','provenance']}
                    p.update(id='wf-'+uuid.uuid4().hex[:24],audit_id=key,status='proposed',rule=Redactor().tree(rule.model_dump()),approval=None,activation=None)
                    p['proposal_hash']=self.binding(p,p['rule']);self.save_proposal(p);ids.append(p['id'])
                a.update(status='proposed',summary=answer.summary,limitations=answer.limitations,proposals=ids,provider=self.runtime.reasoner.provider,model=getattr(self.runtime.reasoner,'selected_model',None))
                self.store.record('workflow:'+key,'workflow_audit_completed',{'proposal_ids':ids,'revision':revision,'provider':a['provider'],'model':a['model']})
            except Exception as exc:
                a.update(status='blocked',error='Workflow audit unavailable: '+type(exc).__name__,detail=Redactor().text(str(exc))[:300])
                self.store.record('workflow:'+key,'workflow_audit_blocked',{'error_type':type(exc).__name__})
            self.db.save(AuditRow,key,a)

    async def decide(self,key,decision,actor):
        async with self.lock:
            p=self.proposal(key)
            if p['status'] in {'generation_queued','generating'}:raise ValueError('Wait for current generation before editing')
            if decision.proposal_hash!=p['proposal_hash'] or p['proposal_hash']!=self.binding(p,p['rule']):raise ValueError('Source, project or proposal changed; re-audit before approval')
            if decision.decision=='edit':
                if decision.rule is None:raise ValueError('Edited rule required')
                a=self.db.get(AuditRow,p['audit_id']);files=self.files(a['id'])
                validate_rule(decision.rule,files,a['source_context'])
                p.update(rule=decision.rule.model_dump(),status='proposed',approval=None,activation=None,patch=None,verification=None)
                p['proposal_hash']=self.binding(p,p['rule'])
            elif decision.decision=='reject':p.update(status='rejected',approval=None,activation=None)
            else:
                if decision.rule is not None:raise ValueError('Edit and approve must be separate review actions')
                approval={'actor':actor,'timestamp':self.clock(),'proposal_hash':p['proposal_hash'],'monitoring_only':True}
                approval['hash']=digest(approval)
                p.update(status='approved',approval=approval,approved_project=copy.deepcopy(self.store.project(p['project_id'])))
            self.save_proposal(p);self.store.record('workflow:'+key,'workflow_rule_'+decision.decision,{'actor':actor,'proposal_hash':p['proposal_hash'],'approval':p.get('approval')})
            return p

    def approved(self,p,approval_hash,deployment_phase=False):
        project=None
        if deployment_phase and p.get('approved_project'):
            current=copy.deepcopy(self.store.project(p['project_id']));project=p['approved_project']
            old=next(d for d in project['repository_monitoring']['deployments'] if d['id']==p['deployment_id'])
            for d in current['repository_monitoring']['deployments']:
                if d['id']==p['deployment_id']:d['commit_sha']=old.get('commit_sha')
            if current!=project:raise ValueError('Project or monitoring source changed; renewed review required')
        if not p.get('approval') or p['approval']['hash']!=approval_hash or p['approval']['proposal_hash']!=self.binding(p,p['rule'],project):
            raise ValueError('Exact current monitoring approval required')
        if tree_digest(self.files(p['audit_id']))!=p['source_digest']:raise ValueError('Pinned source snapshot changed')

    async def generate(self,key,approval_hash,install_dependencies=False):
        async with self.jobs:
            p=self.proposal(key)
            try:
                self.approved(p,approval_hash)
                if p['status']!='generation_queued':raise ValueError('An exclusively reserved approved generation is required')
                rule=WorkflowRule.model_validate(p['rule'])
                if rule.technique!='instrumentation':raise ValueError('Selected technique does not require an instrumentation patch')
                p['status']='generating';self.save_proposal(p)
                files=self.files(p['audit_id'])
                plan=await workflow_reasoning.patch_plan(self.runtime.reasoner,{'rule':p['rule'],'source':self.db.get(AuditRow,p['audit_id'])['source_context'],'approval_hash':approval_hash})
                # Validate again after the potentially slow provider call.
                self.approved(self.proposal(key),approval_hash)
                candidate,patch=workflow_patch.compile_patch(files,rule,plan,key,approval_hash)
                # Do not export original hardcoded credentials merely because they
                # happened to be present in an imported repository.
                import os,re
                private=[v for k,v in os.environ.items() if len(v)>=8 and any(x in k.upper() for x in ['TOKEN','PASSWORD','SECRET','API_KEY'])]
                if any(any(v in text for v in private) or re.search(r'-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----|nvapi-[A-Za-z0-9_-]{15,}|github_pat_[A-Za-z0-9_]{15,}',text) for text in candidate.values()):
                    raise ValueError('Potential private credential in source; review a sanitized snapshot before exporting')
                output=self.file(key,'artifact').parent
                workflow_patch.export(output,candidate,patch)
                p['patch']=patch;self.save_proposal(p)
                verification=await asyncio.to_thread(workflow_patch.verify,files,candidate,output/'verification'/uuid.uuid4().hex,install_dependencies)
                self.approved(self.proposal(key),approval_hash)
                p.update(status='awaiting_deployment' if verification['passed'] else 'tests_failed',verification=Redactor().tree(verification))
                self.store.record('workflow:'+key,'instrumentation_verification',{'passed':verification['passed'],'checks':verification['checks'],'deployed':False})
            except Exception as exc:
                p.update(status='generation_blocked',error='Instrumentation generation blocked: '+type(exc).__name__,detail=Redactor().text(str(exc))[:400])
                self.store.record('workflow:'+key,'instrumentation_blocked',{'error_type':type(exc).__name__})
            self.save_proposal(p)

    async def queue_generation(self,key,approval_hash):
        async with self.lock:
            p=self.proposal(key);self.approved(p,approval_hash)
            if p['status'] not in {'approved','tests_failed'} or p['rule']['technique']!='instrumentation':raise ValueError('An approved instrumentation proposal is required')
            with self.store.sessions() as db:
                active=db.scalar(select(func.count()).select_from(ProposalRow).where(ProposalRow.payload['status'].as_string().in_(['generation_queued','generating'])))
            if active>=2:raise ValueError('Two instrumentation generations are already in progress')
            p['status']='generation_queued';self.save_proposal(p)

    async def activate(self,key,binding,actor):
        async with self.lock:
            p=self.proposal(key);self.approved(p,binding.approval_hash,deployment_phase=True)
            instrumented=p['rule']['technique']=='instrumentation'
            if instrumented:
                if p['status']!='awaiting_deployment' or not p.get('verification',{}).get('passed'):raise ValueError('Verified instrumentation artifact required before activation')
                if binding.artifact_digest!=p['patch']['instrumentation_digest']:raise ValueError('Different instrumentation artifact')
            else:
                if p['status']!='approved' or p['rule']['technique'] not in {'existing_telemetry','read_only_reconciliation'}:raise ValueError('This strategy has no verified activation adapter')
                if binding.artifact_digest!=p['proposal_hash']:raise ValueError('Existing-source monitoring must bind the exact approved rule hash')
                if p['rule']['technique']=='read_only_reconciliation' and not binding.reconciliation_source_id:raise ValueError('Independent durable-state source required')
            project,deployment,_=self.runtime.target(p['project_id'],p['deployment_id'])
            if binding.check_mode=='deadline_targeted' and not binding.reconciliation_source_id:raise ValueError('Deadline checks require an independent source')
            if binding.reconciliation_source_id:
                _,_,source=self.runtime.target(p['project_id'],p['deployment_id'],binding.reconciliation_source_id)
                if source.connector!='generic-events' or source.id==p['source_id']:raise ValueError('Independent reconciliation requires its own authenticated source')
            if binding.revision.startswith('sha256:'):
                expected='sha256:'+p['patch']['source_digest'] if instrumented else p['revision']
                if deployment.platform!='local' or binding.revision!=expected:raise ValueError('Local snapshot deployment must match approved source digest')
            elif deployment.commit_sha!=binding.revision:
                raise ValueError('Update deployment to the actually deployed commit before activation')
            elif instrumented:
                # For Git deployments, verify that the deployed commit is exactly
                # the reviewed patch on top of the pinned original commit.
                from .github import normalize_github
                from urllib.parse import quote
                import base64
                repo=normalize_github(p['repository']);base='/repos/'+repo['full_name']
                commit,error=await self.runtime.source.get('api.github.com',base+'/commits/'+binding.revision,self.runtime.source.github_token)
                if error or not isinstance(commit,dict) or commit.get('sha')!=binding.revision:raise ValueError('Deployed Git revision could not be independently checked')
                snapshot_audit=p['revision'].startswith('sha256:')
                if not snapshot_audit and ([x['sha'] for x in commit.get('parents',[])]!=[p['revision']] or {x['filename'] for x in commit.get('files',[])}!=set(p['patch']['changed_files'])):
                    raise ValueError('Deployed revision includes changes beyond the exact reviewed instrumentation patch')
                with __import__('zipfile').ZipFile(self.file(key,'instrumented-source.zip')) as z:
                    paths=z.namelist() if snapshot_audit else p['patch']['changed_files']
                    if len(paths)>40:raise ValueError('Snapshot-to-Git activation exceeds bounded source verification')
                    for path in paths:
                        data,error=await self.runtime.source.get('api.github.com',base+'/contents/'+quote(path,safe='/')+'?ref='+binding.revision,self.runtime.source.github_token)
                        if error or not isinstance(data,dict) or data.get('encoding')!='base64' or base64.b64decode(data.get('content',''))!=z.read(path):
                            raise ValueError('Deployed instrumentation does not match reviewed artifact')
            # A changed deployment commit does not retrospectively approve different source rules.
            p.update(status='deployment_observed',activation={**binding.model_dump(),'actor':actor,'at':self.clock(),'last_event':None,'last_reconciliation':None,'verification':'Operator-bound deployment; authenticated telemetry still required'})
            self.save_proposal(p);self.store.record('workflow:'+key,'workflow_deployment_binding',p['activation'])
            return p

    def validate_signal(self,project,deployment,source,event):
        signal=event.get('workflow')
        if not signal:return
        try:p=self.proposal(signal['audit_id'])
        except KeyError:raise HTTPException(403,'Unknown workflow proposal')
        a=p.get('activation')
        if p['project_id']!=project.id or p['deployment_id']!=deployment.id or not a or p['status'] not in {'deployment_observed','monitoring_active','monitoring_degraded'}:
            raise HTTPException(403,'Workflow is not approved and deployment-bound for this source')
        if signal['workflow_id']!=p['rule']['id'] or signal['artifact_digest']!=a['artifact_digest'] or signal['revision']!=a['revision']:
            raise HTTPException(409,'Workflow revision or instrumentation digest does not match activation')
        if source.id not in {p['source_id'],a.get('reconciliation_source_id')}:raise HTTPException(403,'Source not approved for workflow')
        authoritative=signal['kind']=='workflow.reconciled'
        if authoritative and source.id!=a.get('reconciliation_source_id'):raise HTTPException(403,'Authoritative state requires independent reconciler source')
        if authoritative and a.get('check_mode')=='deadline_targeted':
            try:self.deadlines.validate(p,{**event,'source_id':source.id})
            except ValueError as exc:raise HTTPException(409,str(exc))
        used={k for k in ['instance_id','resource_id','parent_id'] if signal.get(k)}|{k for k in ['request_id','trace_id','user_id'] if event.get(k)}
        if not used<=set(p['rule']['allowed_fields']):raise HTTPException(422,'Telemetry fields exceed approved privacy scope')
        if event.get('session_id'):raise HTTPException(422,'Session identifiers are not approved workflow fields')
        if signal['kind'] not in {'workflow.heartbeat','workflow.reconciliation_failed'} and not signal.get('instance_id'):raise HTTPException(422,'Workflow instance identifier required')
        if authoritative and (signal.get('started_at') is None or signal.get('state') is None):raise HTTPException(422,'Durable reconciliation needs authoritative start time and state')
        if signal.get('started_at') is not None and signal['started_at']>event['timestamp']:raise HTTPException(422,'Start cannot follow observation time')
        if event['timestamp']>self.clock()+5:raise HTTPException(422,'Workflow source clock is too far ahead')

    def ingest(self,events):
        for event in events:
            signal=event.get('workflow')
            if not signal:continue
            p=self.proposal(signal['audit_id']);activation=p['activation'];activation['last_event']=max(activation.get('last_event') or 0,event['timestamp'])
            authoritative=event['source_id']==activation.get('reconciliation_source_id')
            if event['source_id']==p['source_id'] and signal['kind'] in {'workflow.started','workflow.completed','workflow.failed'}:
                activation['primary_event_seen']=True
            if authoritative:activation['last_reconciliation']=event['timestamp']
            if authoritative and signal['kind'] in {'workflow.reconciled','workflow.heartbeat'}:activation['reconciliation_error']=False
            p['status']='monitoring_active';self.save_proposal(p)
            if signal['kind']=='workflow.reconciliation_failed':
                activation['reconciliation_error']=True
                p.update(status='monitoring_degraded',monitoring_warning='Independent state collection failed; completion is unknown.')
                self.save_proposal(p);continue
            if signal['kind']=='workflow.heartbeat':continue
            key=digest([p['id'],activation['revision'],signal['instance_id']])
            with self.store.sessions.begin() as db:
                row=db.get(InstanceRow,key)
                if row is None:
                    count=db.scalar(select(func.count()).select_from(InstanceRow).where(InstanceRow.proposal_id==p['id']))
                    if count>=self.limits.maximum_records:raise HTTPException(429,'Workflow record capacity reached; retain unresolved operations and apply backpressure')
                    started=signal.get('started_at') or event['timestamp']
                    row=InstanceRow(key=key,proposal_id=p['id'],instance_id=signal['instance_id'],state='pending',deadline=started+p['rule']['deadline_seconds'],updated=self.clock(),payload={})
                    db.add(row)
                old=row.payload
                # Occurrence timestamps prevent late starts from undoing completion.
                if event['timestamp']<old.get('last_timestamp',0):continue
                state=signal.get('state') if authoritative and signal['kind']=='workflow.reconciled' else {'workflow.started':'pending','workflow.completed':'completed','workflow.failed':'failed','workflow.cancelled':'cancelled'}.get(signal['kind'],'unknown')
                if row.state in {'completed','cancelled'} and state in {'pending','running','unknown'} and not authoritative:continue
                payload={**old,'last_timestamp':event['timestamp'],'resource_id':signal.get('resource_id') or old.get('resource_id'),
                    'user_id':event.get('user_id') or old.get('user_id'),'request_id':event.get('request_id') or old.get('request_id'),'trace_id':event.get('trace_id') or old.get('trace_id'),'last_event':event}
                if authoritative:
                    payload.update(authoritative_state=state,authoritative_at=event['timestamp'])
                    row.deadline=signal['started_at']+p['rule']['deadline_seconds']
                if state=='failed':row.deadline=min(row.deadline,event['timestamp'])
                row.payload=payload;row.updated=self.clock();row.state=state or 'unknown'
                if authoritative and signal.get('check_id'):
                    self.deadlines.finish(db,event)
                self.deadlines.schedule(db,row,p)
                # Terminal records expire; unresolved records are never silently dropped.
                db.execute(delete(InstanceRow).where(InstanceRow.proposal_id==p['id'],InstanceRow.state.in_(['completed','cancelled']),InstanceRow.updated<self.clock()-self.limits.retention_days*86400))

    async def reconcile(self,project_id):
        ids=[]
        async with self.lock:
            for p in self.db.proposals(project_id=project_id):
                a=p.get('activation')
                if not a:continue
                if p['rule']['technique']=='instrumentation' and 'primary_event_seen' not in a:
                    from .runtime_store import RuntimeRow
                    with self.store.sessions() as db:
                        prior=db.scalar(select(RuntimeRow).where(RuntimeRow.project_id==p['project_id'],RuntimeRow.deployment_id==p['deployment_id'],RuntimeRow.source_id==p['source_id'],
                            RuntimeRow.payload['workflow']['audit_id'].as_string()==p['id'],RuntimeRow.payload['workflow']['revision'].as_string()==a['revision'],
                            RuntimeRow.payload['workflow']['artifact_digest'].as_string()==a['artifact_digest'],
                            RuntimeRow.payload['workflow']['kind'].as_string().in_(['workflow.started','workflow.completed','workflow.failed'])).limit(1))
                        a['primary_event_seen']=prior is not None
                        if prior:a['primary_evidence_id']=prior.id
                now=self.clock();fresh=now-(a.get('last_event') or 0)<60 and not a.get('reconciliation_error')
                if p['rule']['technique']=='instrumentation' and not a.get('primary_event_seen'):fresh=False
                p['status']='monitoring_active' if fresh else 'monitoring_degraded'
                p['monitoring_warning']=None if fresh else 'No recent authenticated evidence; missing completion is not proof of business failure.'
                with self.store.sessions() as db:
                    q=select(InstanceRow).where(InstanceRow.proposal_id==p['id'],InstanceRow.state.in_(['pending','running','failed','unknown']),InstanceRow.deadline<=now,
                        InstanceRow.payload['last_event']['workflow']['revision'].as_string()==a['revision'])
                    cursor=p.get('scan_cursor','')
                    rows=db.scalars(q.where(InstanceRow.key>cursor).order_by(InstanceRow.key).limit(500)).all()
                    if not rows and cursor:
                        rows=db.scalars(q.order_by(InstanceRow.key).limit(500)).all()
                    p['scan_cursor']=rows[-1].key if rows else ''
                    samples=[(r.key,r.instance_id,r.state,dict(r.payload)) for r in rows]
                for key,instance,state,payload in samples:
                    if payload.get('incident_id'):continue
                    authoritative=now-payload.get('authoritative_at',0)<60 and payload.get('authoritative_state') in {'pending','running','failed'}
                    explicit_failure=state=='failed' and fresh and now-payload.get('last_timestamp',0)<60
                    if not authoritative and not explicit_failure:
                        p['monitoring_warning']='Overdue completion is unknown: lifecycle delivery is best-effort or reconciler state is stale.'
                        continue
                    minute=int(now//60)
                    if p.get('admission_minute')!=minute:p.update(admission_minute=minute,admissions=0)
                    if p.get('admissions',0)>=3:break # Persistent per-proposal budget; never per successful operation.
                    event=payload['last_event'];evidence={**event,'error_type':'WorkflowIncomplete','message':'Approved workflow deadline exceeded; '+('independently observed durable state is incomplete' if authoritative else 'explicit workflow failure observed')}
                    fingerprint=digest([p['id'],a['revision'],instance])
                    incident,created=self.store.create(project_id,'runtime',fingerprint,{'runtime_event':evidence,'detection_rule':'approved_workflow_reconciliation'})
                    self.store.update(incident['id'],workflow_evidence={'proposal_id':p['id'],'approved_rule':p['rule'],'approval':p['approval'],
                        'instance_id':instance,'resource_id':payload.get('resource_id'),'user_id':payload.get('user_id'),'identity':'approved pseudonymous ID' if payload.get('user_id') else 'unknown',
                        'observation':'authoritative overdue incomplete' if authoritative else 'explicit failure','revision':a['revision'],'last_evidence':event,
                        'source_revision':p['revision'],'source_provenance':p['provenance'],
                        'source_context':self.db.get(AuditRow,p['audit_id']).get('source_context',{}),
                        'instrumentation_diff':(p.get('patch') or {}).get('diff','')[:10000]},
                        runtime_summary={'events':1,'last_received':now,'affected_users':1 if payload.get('user_id') else None,'identity_coverage':'Only approved supplied pseudonymous IDs'},runtime_samples=[evidence])
                    if created:self.store.record(incident['id'],'detect',{'rule':'approved_workflow_reconciliation','proposal_id':p['id'],'instance_id':instance,'resource_id':payload.get('resource_id')})
                    if created:p['admissions']=p.get('admissions',0)+1
                    with self.store.sessions.begin() as db:
                        r=db.get(InstanceRow,key);r.payload={**r.payload,'incident_id':incident['id']}
                    ids.append(incident['id'])
                self.save_proposal(p)
        return ids

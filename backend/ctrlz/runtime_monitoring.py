"""Runtime evidence uses the existing incident store, model provider and receipts.

This integration never calls operational adapters, imports code or executes repairs.
"""
import asyncio
import json
import re
import time
from fastapi import HTTPException
from .models import Project
from .runtime_models import RuntimeAssessment
from .runtime_store import RuntimeStorage, digest
from .runtime_security import SourceSecrets, Redactor
from .runtime_source import SourceEvidence


def event_fingerprint(event):
    route=(event.get('route') or '').split('?',1)[0]
    route=re.sub(r'[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}',':id',route)
    route=re.sub(r'/\d+(?=/|$)','/:id',route)
    frames=[{k:f.get(k) for k in ['path','line','function']} for f in event.get('frames',[])]
    message=re.sub(r'\b[0-9a-fA-F-]{8,}\b|\b\d+\b',':value',event['message']) if not frames else None
    return digest({k:event.get(k) for k in ['project_id','deployment_id','environment','deployment_ref','commit_sha','error_type']} | {'frames':frames,'route':route,'message':message})


class RuntimeMonitoring:
    def __init__(self, store, client, reasoner, runbooks, directory, github_token=None, vercel_token=None, local_repositories=None):
        self.store,self.client,self.reasoner,self.runbooks=store,client,reasoner,runbooks
        self.storage=RuntimeStorage(store)
        self.secrets=SourceSecrets(directory, store)
        self.source=SourceEvidence(client,github_token,vercel_token,local_repositories)
        self.locks={}
        self.review_locks={}
        self.detection_lock=asyncio.Lock()

    def target(self, project_id, deployment_id, source_id=None):
        try:project=Project.model_validate(self.store.project(project_id))
        except (KeyError,ValueError):raise HTTPException(404,'Runtime target not found')
        if project.project_type!='repository-deployment':raise HTTPException(404,'Runtime target not found')
        deployment=next((d for d in project.repository_monitoring.deployments if d.id==deployment_id),None)
        if not deployment:raise HTTPException(404,'Runtime deployment not found')
        source=next((s for s in deployment.sources if s.id==source_id),None) if source_id else None
        if source_id and not source:raise HTTPException(404,'Runtime source not found')
        return project,deployment,source

    def normalize(self, project, deployment, source, event):
        secret=self.secrets.get(project.id,deployment.id,source.id)
        r=Redactor([secret])
        data=event.model_dump()
        if data.get('workflow') is None:data.pop('workflow',None) # Preserve pre-feature delivery digests for ordinary events.
        if data.get('workflow'):
            if not hasattr(self,'workflows'):raise HTTPException(409,'Workflow observability is unavailable')
            self.workflows.validate_signal(project,deployment,source,data)
        if deployment.deployment_ref and data['deployment_ref'] and data['deployment_ref'] != deployment.deployment_ref:
            raise HTTPException(403,'Event deployment reference does not match configured target')
        if not time.time()-7*86400 <= data['timestamp'] <= time.time()+300:
            raise HTTPException(422,'Event timestamp must be within retention window and five minutes of future clock skew')
        data['user_id']=self.secrets.pseudonym(data['user_id'])
        data['session_id']=self.secrets.pseudonym(data['session_id'])
        if data['route']:data['route']=data['route'].split('?',1)[0].split('#',1)[0]
        # Supplied references are opaque labels; never fetched. Strip URL query data.
        if data['evidence_ref']:data['evidence_ref']=data['evidence_ref'].split('?',1)[0]
        data=r.tree(data)
        data.update(project_id=project.id,deployment_id=deployment.id,environment=deployment.environment,source_id=source.id,source_provider=source.connector)
        # Deployment ID is configured evidence. Commit stays unknown unless supplied/configured.
        data['deployment_ref']=data['deployment_ref'] or deployment.deployment_ref
        data['commit_sha']=data['commit_sha'] or deployment.commit_sha
        data['signal']=data['severity'] in {'error','fatal'} or (data['http_status'] is not None and data['http_status']>=500)
        if data.get('workflow'):data['signal']=False # Evaluated by the approved workflow reconciler, not duplicate runtime detection.
        data['fingerprint']=event_fingerprint(data)
        return data

    async def accept(self, project, deployment, source, batch):
        if not project.enabled:raise HTTPException(409,'Monitoring is disabled for this project')
        if batch is None:return {'accepted':0,'duplicates':0,'incident_ids':[]}
        normalized=[self.normalize(project,deployment,source,e) for e in batch.events]
        ids,duplicates=self.storage.ingest('/'.join([project.id,deployment.id,source.id]),normalized)
        if hasattr(self,'workflows'):
            pending=[e for e in self.storage.rows(project_id=project.id,unprocessed=True,limit=1000) if e.get('workflow')]
            self.workflows.ingest(reversed(pending))
            for e in pending:self.storage.link(e['id'],None)
        incidents=await self.detect(project.id)
        if hasattr(self,'workflows'):incidents+=await self.workflows.reconcile(project.id)
        return {'accepted':len(ids),'duplicates':duplicates,'incident_ids':incidents}

    async def detect(self, project_id):
        async with self.detection_lock:
            rows=self.storage.rows(project_id=project_id,unprocessed=True,limit=1000)
            all_rows=self.storage.rows(project_id=project_id,limit=10000)
            ids=[]
            for event in reversed(rows):
                if event.get('workflow'):continue # Only the approved processor may acknowledge workflow delivery.
                if not event['signal']:
                    self.storage.link(event['id'],None)
                    continue
                similar=[e for e in all_rows if e['fingerprint']==event['fingerprint'] and abs(e['timestamp']-event['timestamp'])<=60 and e['signal']]
                exception=event['severity']=='fatal' or bool(event['error_type'] or event['frames'] or event['stack']) and event['severity']=='error'
                if not exception and len(similar)<3:
                    # Keep pending until further evidence crosses the threshold.
                    continue
                incident,created=self.store.create(project_id,'runtime',event['fingerprint'],{'runtime_event':event,'detection_rule':'runtime_exception' if exception else 'three_failures_in_60s'})
                for member in similar:
                    if not member['incident_id']:
                        self.storage.link(member['id'],incident['id'])
                self.storage.link(event['id'],incident['id'])
                affected=self.storage.rows(incident_id=incident['id'],limit=10000)
                users={e['user_id'] for e in affected if e.get('user_id')}
                self.store.update(incident['id'],runtime_summary={'events':len(affected),'last_received':max(e['received_at'] for e in affected),'affected_users':len(users) if users else None,'identity_coverage':'Only supplied pseudonymous IDs; unknown users are not counted'},runtime_samples=affected[:5])
                if created:self.store.record(incident['id'],'detect',incident['evidence'])
                self.store.record(incident['id'],'runtime_event',{'runtime_evidence_id':event['id'],'source_event_id':event['event_id'],'source_id':event['source_id'],'fingerprint':event['fingerprint']})
                ids.append(incident['id'])
            return list(dict.fromkeys(ids))

    def binding(self, incident, recommendation):
        project=self.store.project(incident['project_id'])
        return digest({'incident_id':incident['id'],'recommendation':recommendation,'project':project,'runtime_summary':incident.get('runtime_summary'),'source_evidence':incident.get('source_evidence'),'execution':'disabled'})

    async def investigate(self, incident_id):
        async with self.locks.setdefault(incident_id,asyncio.Lock()):
            incident=self.store.get(incident_id)
            if incident['status'] in {'awaiting_review','recommendation_reviewed'}:return
            try:
                event=incident['evidence']['runtime_event']
                project,deployment,_=self.target(incident['project_id'],event['deployment_id'])
                if not project.enabled:
                    self.store.update(incident_id,status='blocked',error='Monitoring disabled before investigation')
                    return
                self.store.update(incident_id,status='diagnosing',error=None,diagnosis=None,runtime_assessment=None,runtime_recommendations=[],recommendation_review=None,reasoning_provider=self.reasoner.provider,model=getattr(self.reasoner,'selected_model',None))
                self.store.record(incident_id,'diagnose',{'mode':'read_only_runtime_evidence','provider':self.reasoner.provider,'model':getattr(self.reasoner,'selected_model',None)})
                mapping=await self.source.correlate(project.repository_monitoring,deployment,event)
                if mapping.get('state') in {'github_rate_limited','provider_http_403','provider_http_503','provider_unavailable'}:
                    # A previously verified immutable blob remains evidence at the
                    # same SHA. Keep provider failure and cache provenance explicit.
                    from .github import normalize_github
                    expected_repo=normalize_github(project.repository_monitoring.github_url)['full_name'].lower()
                    expected_sha=event.get('commit_sha') or deployment.commit_sha
                    previous=next((e for e in reversed(self.store.events(incident_id=incident_id)) if e['stage']=='source_correlation' and e['payload'].get('state')=='exact_github_revision' and e['payload'].get('commit_sha')==expected_sha and e['payload'].get('repository',{}).get('full_name','').lower()==expected_repo and e['payload'].get('files')),None)
                    if previous:
                        mapping={**previous['payload'],'cached_immutable_source':True,'cached_evidence_event_id':previous['id'],'cached_observed_at':previous['timestamp'],'refresh_error':mapping['state'],'uncertainties':previous['payload'].get('uncertainties',[])+['Current GitHub refresh failed; using previously recorded source at the identical repository and immutable commit.']}
                source_id=self.store.record(incident_id,'source_correlation',mapping)
                self.store.update(incident_id,source_evidence=mapping)
                books=await asyncio.to_thread(self.runbooks.search,'runtime exception '+(event.get('error_type') or '')+' '+event['message'][:300])
                book_id=self.store.record(incident_id,'tool_result',{'tool':'runbook_search','result':books})
                current=self.store.get(incident_id)
                context={'incident_id':incident_id,'runtime_evidence':current.get('runtime_samples',[event]),'affected':current.get('runtime_summary'),'deployment':deployment.model_dump(),'repository':project.repository_monitoring.github_url,'source_evidence':mapping,'runbooks':books,'evidence_ids':[str(source_id),str(book_id)]+['runtime:'+str(e['id']) for e in current.get('runtime_samples',[event])],'execution_permissions':[],'verification':'Not performed; recommendation only. No reproduction or test run has occurred.'}
                if current.get('workflow_evidence'):
                    context['approved_workflow_evidence']=current['workflow_evidence']
                    context['workflow_guidance']='One affected operation does not justify a global restart. Missing lifecycle delivery alone is not a confirmed failure. Recommend resource-scoped investigation; retry requires separately authorized application semantics.'
                context=Redactor([self.secrets.get(project.id,deployment.id,s.id) for s in deployment.sources]).tree(context)
                if not hasattr(self.reasoner,'runtime_assess'):
                    from .reasoning import ReasoningUnavailable
                    raise ReasoningUnavailable('Configured reasoner has no runtime assessment capability')
                allowed=set(context['evidence_ids'])
                for attempt in range(2):
                    try:
                        assessment=await self.reasoner.runtime_assess(context)
                        if not isinstance(assessment,RuntimeAssessment):assessment=RuntimeAssessment.model_validate(assessment)
                        if len({r.id for r in assessment.recommendations}) != len(assessment.recommendations):
                            raise ValueError('Recommendation IDs must be unique')
                        for recommendation in assessment.recommendations:
                            if not set(recommendation.evidence_ids)<=allowed:raise ValueError('Assessment cited unknown evidence')
                        break
                    except ValueError as exc:
                        if attempt:raise
                        self.store.record(incident_id,'assessment_revision',{'attempt':1,'reason':'Typed assessment or evidence citation validation failed','error_type':type(exc).__name__})
                        context['validation_feedback']='Previous output failed schema/evidence validation. Return the exact schema with unique recommendation IDs. Every evidence_ids entry must be exactly one of: '+json.dumps(context['evidence_ids'])
                data=Redactor().tree(assessment.model_dump())
                self.store.update(incident_id,status='awaiting_review',diagnosis=data['diagnosis'],runtime_assessment=data,verification={'passed':False,'checks':{},'state':'not_run','reason':'Read-only recommendations; production recovery is not established.'},remaining_risks=data['uncertainties'])
                current=self.store.get(incident_id)
                reviews=[]
                for r in data['recommendations']:
                    reason = 'Review only; execution permissions remain empty.'
                    reviewable = True
                    if r['category'] == 'rollback':
                        reviewable, reason = False, 'No verified previous-deployment evidence; rollback recommendation is blocked.'
                    elif r['category'] == 'code_patch' and not mapping.get('files'):
                        reviewable, reason = False, 'No exact-revision source context retrieved; investigate before reviewing a code patch.'
                    proposed = {**r, 'review_policy':{'reviewable':reviewable,'reason':reason}}
                    reviews.append({**proposed,'review_hash':self.binding(current,proposed),'execution_permitted':False})
                self.store.update(incident_id,runtime_recommendations=reviews)
                self.store.record(incident_id,'diagnosis',{'text':data['diagnosis'],'uncertainties':data['uncertainties']})
                self.store.record(incident_id,'recommendations',{'items':reviews,'execution_permitted':False})
            except Exception as exc:
                from .reasoning import ReasoningUnavailable
                blocked=isinstance(exc,ReasoningUnavailable)
                self.store.update(incident_id,status='blocked' if blocked else 'escalated',error='Runtime diagnosis unavailable: '+type(exc).__name__+'. No simulated reasoning or recovery was substituted.')
                validation_reason = str(exc) if str(exc) in {'Assessment cited unknown evidence', 'Recommendation IDs must be unique'} else None
                self.store.record(incident_id,'blocked' if blocked else 'escalated',{'error_type':type(exc).__name__,'validation_reason':validation_reason,'execution_permitted':False})

    async def review(self, incident_id, recommendation_id, review_hash, decision):
        async with self.review_locks.setdefault(incident_id,asyncio.Lock()):
            incident=self.store.get(incident_id)
            if incident['kind']!='runtime' or incident['status']!='awaiting_review':raise ValueError('No runtime recommendation awaiting review')
            recommendation=next((r for r in incident.get('runtime_recommendations',[]) if r['id']==recommendation_id),None)
            if not recommendation:raise ValueError('Unknown recommendation')
            if not recommendation.get('review_policy',{}).get('reviewable'):
                raise ValueError('Deterministic evidence policy blocks this recommendation; reinvestigate')
            proposed={k:v for k,v in recommendation.items() if k not in {'review_hash','execution_permitted'}}
            if review_hash!=recommendation['review_hash'] or review_hash!=self.binding(incident,proposed):raise ValueError('Recommendation, target or evidence changed; reinvestigate before review')
            self.store.update(incident_id,status='recommendation_reviewed' if decision=='accept' else 'escalated',recommendation_review={'id':recommendation_id,'decision':decision,'review_hash':review_hash,'executed':False})
            self.store.record(incident_id,'recommendation_review',{'id':recommendation_id,'decision':decision,'review_hash':review_hash,'executed':False})

    def handoff(self, incident_id):
        incident=self.store.get(incident_id)
        if incident['kind']!='runtime':raise ValueError('Runtime incident required')
        event=incident['evidence']['runtime_event']
        project,deployment,_=self.target(incident['project_id'],event['deployment_id'])
        return {'schema_version':1,'incident_id':incident_id,'repository':project.repository_monitoring.github_url,'deployed_revision':incident.get('source_evidence',{}).get('commit_sha'),'deployment':deployment.model_dump(),'source_mapping':incident.get('source_evidence'),'error_evidence':incident.get('runtime_samples'),'workflow_evidence':incident.get('workflow_evidence'),'diagnosis':incident.get('diagnosis'),'recommendations':incident.get('runtime_recommendations',[]),'expected_behavior':'Operator must confirm expected behavior and supply a reproduction before repair.','suggested_tests':['Reproduce this exact observed failure at the deployed revision.','Verify expected success and error handling with immutable regression tests.'],'boundary':'Context only. Import a matching managed snapshot in Repository repair. No import, sandbox execution, patch or deployment has been performed.'}

    def coverage(self, project):
        project=Project.model_validate(project)
        result=[]
        for deployment in project.repository_monitoring.deployments:
            summary=self.storage.summary(project.id,deployment.id)
            credentials=all(bool(self.secrets.get(project.id,deployment.id,s.id)) for s in deployment.sources)
            age=time.time()-(summary['last_event_at'] or 0)
            state='paused' if not project.enabled else 'incomplete_configuration' if not credentials else 'no_recent_events' if summary['last_event_at'] is None or age>300 else 'error_detected' if summary['error_count'] else 'observing'
            open_incidents=sum(i['project_id']==project.id and i['kind']=='runtime' and i['status']!='resolved' and i.get('evidence',{}).get('runtime_event',{}).get('deployment_id')==deployment.id for i in self.store.incidents())
            if project.enabled and open_incidents:state='error_detected'
            result.append({'deployment':deployment.model_dump(),'state':state,'credentials_configured':credentials,**summary,'open_incidents':open_incidents,'capabilities':['read_only_diagnosis','recommendation_review','source_correlation','repair_context_export'],'execution_permitted':False})
        return result

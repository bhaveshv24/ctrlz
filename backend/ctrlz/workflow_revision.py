"""Renew monitoring review for an unchanged, already deployed CampusPass observer.
No source execution, new instrumentation, inherited approval, or deployment authority.
"""
import ast,base64,copy,json,re,uuid,zipfile
from urllib.parse import quote
from .github import normalize_github
from .workflow_source import bounded,inspect,tree_digest,validate_rule
from .workflow_models import WorkflowRule
from .workflow_store import AuditRow,InstanceRow
from sqlalchemy import select,func
from .runtime_store import digest

HELPER='backend/campuspass/_ctrlz_session_observer.py'
MAIN='backend/campuspass/main.py'
DB='backend/campuspass/db.py'

def anchors(files):
    tree=ast.parse(files[MAIN]);imports=[];calls=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom) and node.module=='_ctrlz_session_observer':imports.append(ast.dump(node,include_attributes=False))
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='_ctrlz_session_attach':calls.append(ast.dump(node,include_attributes=False))
    if len(imports)!=1 or len(calls)!=1:raise ValueError('Expected exactly one reviewed observer import and attachment')
    models={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(files[DB]).body if isinstance(n,ast.ClassDef) and n.name in {'Order','Payment','Job','Ticket'}}
    if len(models)!=4:raise ValueError('Required reviewed durable models missing')
    return {'imports':imports,'calls':calls,'models':models}

def verify_unchanged_observer(previous,current):
    if previous.get(HELPER)!=current.get(HELPER):raise ValueError('Observer changed; a new instrumentation audit is required')
    if anchors(previous)!=anchors(current):raise ValueError('Observer attachment or durable model mapping changed; a new audit is required')
    return {'observer_sha256':__import__('hashlib').sha256(current[HELPER].encode()).hexdigest(),'anchors':digest(anchors(current))}

async def propose(service,key,revision,actor):
    if not re.fullmatch('[0-9a-f]{40}',revision):raise ValueError('Exact deployed Git SHA required')
    async with service.lock:
        p=service.proposal(key)
        with service.store.sessions() as db:
            outstanding=db.scalar(select(func.count()).select_from(InstanceRow).where(InstanceRow.proposal_id==key,InstanceRow.state.not_in(['completed','cancelled'])))
        if outstanding:raise ValueError('Finish or investigate outstanding workflows before reviewing a new deployment revision')
        if p['rule'].get('instrumentation_driver')!='campuspass_committed_session' or not p.get('patch') or not p.get('verification',{}).get('passed'):
            raise ValueError('Only an existing verified trusted observer can be reviewed for reuse')
        if p.get('revision_review') and p['revision_review']['revision']==revision:raise ValueError('This revision already has a pending or approved review')
        repo=normalize_github(p['repository']);base='/repos/'+repo['full_name']
        commit,error=await service.runtime.source.get('api.github.com',base+'/commits/'+revision,service.runtime.source.github_token)
        if error or not isinstance(commit,dict) or commit.get('sha')!=revision:raise ValueError('GitHub commit could not be verified in the expected repository')
        current={}
        for path in [MAIN,DB,HELPER,'backend/campuspass/worker.py','backend/campuspass/demo_target.py']:
            data,error=await service.runtime.source.get('api.github.com',base+'/contents/'+quote(path,safe='/')+'?ref='+revision,service.runtime.source.github_token)
            if error or not isinstance(data,dict) or data.get('encoding')!='base64':raise ValueError('Bounded source unavailable at deployed revision')
            current[path]=base64.b64decode(data.get('content',''),validate=False).decode()
        bounded(current)
        with zipfile.ZipFile(service.file(key,'instrumented-source.zip')) as z:
            previous={path:z.read(path).decode() for path in [MAIN,DB,HELPER]}
        checks=verify_unchanged_observer(previous,current)
        rule=copy.deepcopy(p['rule']);rule.update(technique='existing_telemetry',classification='sufficient',missing_signals=[],hooks=[])
        rule['coverage_limits']=list(rule['coverage_limits'])[:8]+['Existing observer verified unchanged at the reviewed Git revision. Other business-code changes require developer review; static anchor equality does not prove universal semantic equivalence.']
        context=inspect(current);validate_rule(WorkflowRule.model_validate(rule),current,context)
        old=copy.deepcopy(p);audit_id='wf-'+uuid.uuid4().hex[:24]
        service.file(audit_id,'source.json').write_text(json.dumps(current))
        service.file(audit_id,'previous-proposal.json').write_text(json.dumps(old))
        project=copy.deepcopy(service.store.project(p['project_id']))
        for deployment in project['repository_monitoring']['deployments']:
            if deployment['id']==p['deployment_id']:deployment['commit_sha']=revision
        service.store.save_project(project)
        review={'revision':revision,'previous_revision':(old.get('activation') or {}).get('revision'),'previous_audit':old['audit_id'],'artifact_digest':p['patch']['instrumentation_digest'],**checks}
        p.update(audit_id=audit_id,revision=revision,source_digest=tree_digest(current),rule=rule,status='proposed',approval=None,activation=None,approved_project=None,
            revision_review=review,provenance='GitHub commit and unchanged observer/model anchors independently checked; developer must renew monitoring approval for changed business source.')
        p['proposal_hash']=service.binding(p,p['rule'])
        service.db.save(AuditRow,audit_id,{'id':audit_id,'project_id':p['project_id'],'deployment_id':p['deployment_id'],'source_id':p['source_id'],'environment':p['environment'],'repository':p['repository'],'created':service.clock(),'status':'complete','revision':revision,'source_context':context,'proposals':[p['id']],'provider':'Deterministic source-revision review','model':None,'summary':'Existing instrumentation is unchanged. Review the new deployed revision and renew monitoring-only approval. No AI audit, patch generation or deployment is claimed.'})
        service.save_proposal(p);service.store.record('workflow:'+key,'workflow_revision_review_proposed',{'actor':actor,'review':review,'old_approval':old.get('approval'),'new_proposal_hash':p['proposal_hash']})
        return p

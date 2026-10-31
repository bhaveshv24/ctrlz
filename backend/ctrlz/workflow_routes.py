"""Workspace-authenticated workflow onboarding; collector auth remains in telemetry routes."""
import json
from fastapi import Depends,HTTPException,Request
from fastapi.responses import FileResponse
from .workflow_models import AuditRequest,RuleDecision,GenerationRequest,Activation
from .workflow_store import AuditRow


def install_workflow_routes(app,auth,workflows,spawn,code_execution):
    def guarded(function):
        try:return function()
        except KeyError:raise HTTPException(404,'Workflow record not found')
        except ValueError as exc:raise HTTPException(409,str(exc))

    @app.get('/projects/{project_id}/workflow-audits',dependencies=[Depends(auth)])
    def audits(project_id:str):
        project=guarded(lambda:workflows.store.project(project_id))
        if project.get('project_type')!='repository-deployment':raise HTTPException(422,'Repository/deployment project required')
        return {'audits':workflows.db.audits(project_id),'proposals':[{**p,'monitoring':workflows.db.summary(p['id'])} for p in workflows.db.proposals(project_id=project_id)]}

    @app.post('/projects/{project_id}/workflow-audits',dependencies=[Depends(auth)],status_code=202)
    async def analyze(project_id:str,body:AuditRequest):
        record=guarded(lambda:workflows.start(project_id,body.deployment_id,body.source_id))
        spawn(workflows.analyze(record['id']))
        return record

    @app.post('/projects/{project_id}/workflow-audits/snapshot',dependencies=[Depends(auth)],status_code=202)
    async def snapshot(project_id:str,deployment_id:str,source_id:str,request:Request):
        raw=b''
        async for chunk in request.stream():
            raw+=chunk
            if len(raw)>2*1024*1024:raise HTTPException(413,'Audit snapshot limit is 2 MiB')
        target=AuditRequest(deployment_id=deployment_id,source_id=source_id)
        record=guarded(lambda:workflows.start(project_id,target.deployment_id,target.source_id))
        spawn(workflows.analyze(record['id'],raw))
        return record

    @app.post('/workflow-proposals/{proposal_id}/decision',dependencies=[Depends(auth)])
    async def decide(proposal_id:str,body:RuleDecision,request:Request):
        actor=(getattr(request.state,'principal',None) or {}).get('id','operator')
        try:return await workflows.decide(proposal_id,body,actor)
        except KeyError:raise HTTPException(404,'Workflow proposal not found')
        except ValueError as exc:raise HTTPException(409,str(exc))

    @app.post('/workflow-proposals/{proposal_id}/generate',dependencies=[Depends(auth)],status_code=202)
    async def generate(proposal_id:str,body:GenerationRequest):
        code_execution()
        try:await workflows.queue_generation(proposal_id,body.approval_hash)
        except KeyError:raise HTTPException(404,'Workflow proposal not found')
        except ValueError as exc:raise HTTPException(409,str(exc))
        spawn(workflows.generate(proposal_id,body.approval_hash,body.install_dependencies))
        return {'status':'queued','deployed':False}

    @app.post('/workflow-proposals/{proposal_id}/activate',dependencies=[Depends(auth)])
    async def activate(proposal_id:str,body:Activation,request:Request):
        actor=(getattr(request.state,'principal',None) or {}).get('id','operator')
        try:return await workflows.activate(proposal_id,body,actor)
        except KeyError:raise HTTPException(404,'Workflow proposal not found')
        except ValueError as exc:raise HTTPException(409,str(exc))

    @app.get('/workflow-proposals/{proposal_id}/artifacts/{artifact}',dependencies=[Depends(auth)])
    def artifact(proposal_id:str,artifact:str):
        p=guarded(lambda:workflows.proposal(proposal_id))
        names={'patch':('instrumentation.patch','text/plain'),'source':('instrumented-source.zip','application/zip')}
        if artifact not in names or not p.get('patch'):raise HTTPException(404,'Generated artifact not found')
        name,media=names[artifact];path=workflows.file(proposal_id,name)
        if not path.is_file() or path.is_symlink():raise HTTPException(404,'Generated artifact unavailable')
        return FileResponse(path,media_type=media,filename=name)

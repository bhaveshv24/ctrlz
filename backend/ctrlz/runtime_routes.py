"""Authenticated project/review APIs and source-authenticated bounded ingestion."""
import json
from fastapi import Depends, HTTPException, Request
from pydantic import ValidationError, Field
from typing import Literal
from .models import Project, Strict
from .runtime_connectors import CONNECTORS


class SourceTarget(Strict):
    deployment_id: str
    source_id: str


class Review(Strict):
    recommendation_id: str
    review_hash: str = Field(min_length=64,max_length=64)
    decision: Literal['accept','decline']


def install_runtime_routes(app, auth, runtime, spawn, scope_key):
    async def queue_pending(ids):
        for incident_id in ids:
            if runtime.store.get(incident_id)['status']=='detected':spawn(runtime.investigate(incident_id))

    @app.post('/runtime-projects/test',dependencies=[Depends(auth)])
    async def test_connection(body: Project):
        if body.project_type!='repository-deployment':raise HTTPException(422,'Repository/deployment project required')
        config=body.repository_monitoring
        from .github import normalize_github
        repo=normalize_github(config.github_url)
        if repo['full_name'] in runtime.source.local_repositories:
            deployment=config.deployments[0]
            result=await runtime.source.correlate(config,deployment,{'commit_sha':deployment.commit_sha,'frames':[]})
            repository={'state':result['state'],'identity':repo,'deployed_revision':result.get('commit_sha')}
        else:
            metadata,error=await runtime.source.get('api.github.com','/repos/'+repo['full_name'],runtime.source.github_token)
            repository={'state':error or ('accessible' if isinstance(metadata,dict) and str(metadata.get('full_name','')).lower()==repo['full_name'].lower() else 'repository_mismatch'),'identity':repo}
        deployments=[]
        for deployment in config.deployments:
            observed=await runtime.source.vercel_metadata(deployment) if deployment.platform=='vercel' else {'state':'collector_setup_required'}
            deployments.append({'id':deployment.id,'environment':deployment.environment,'metadata':observed,'telemetry':'No live connection is inferred from this test. Provision a source and send real events.'})
        return {'repository':repository,'deployments':deployments,'execution_permitted':False}

    @app.post('/projects/{project_id}/runtime/sources/provision',dependencies=[Depends(auth)])
    def provision(project_id: str, body: SourceTarget):
        _,deployment,source=runtime.target(project_id,body.deployment_id,body.source_id)
        path=runtime.secrets.provision(project_id,deployment.id,source.id)
        runtime.store.record('runtime-project:'+project_id,'source_provisioned',{'deployment_id':deployment.id,'source_id':source.id,'connector':source.connector,'credential_returned':False})
        return {'configured':True,'credential_file':str(path.resolve()),'receiver_path':f'/telemetry/{scope_key}/{project_id}/{deployment.id}/{source.id}','instructions':'Credential is stored server-side only. An authorized server operator must provision it to the collector/drain. Never put it in client-side code.'}

    @app.get('/projects/{project_id}/runtime',dependencies=[Depends(auth)])
    def coverage(project_id: str):
        try:project=runtime.store.project(project_id)
        except KeyError:raise HTTPException(404,'Project not found')
        if project.get('project_type')!='repository-deployment':raise HTTPException(422,'Repository/deployment project required')
        return {'deployments':runtime.coverage(project),'events':runtime.storage.rows(project_id=project_id,limit=100),'incidents':[i for i in runtime.store.incidents() if i['project_id']==project_id]}

    @app.post('/telemetry/{project_id}/{deployment_id}/{source_id}')
    async def telemetry(project_id: str,deployment_id: str,source_id: str,request: Request):
        project,deployment,source=runtime.target(project_id,deployment_id,source_id)
        secret=runtime.secrets.get(project_id,deployment_id,source_id)
        if not secret:raise HTTPException(401,'Source not provisioned')
        raw=b''
        async for chunk in request.stream():
            raw+=chunk
            if len(raw)>262144:raise HTTPException(413,'Telemetry body limit is 256 KiB')
        try:batch=CONNECTORS[source.connector].decode(raw,request.headers,secret,deployment)
        except ValidationError:raise HTTPException(422,'Telemetry schema rejected; raw values are not reflected')
        result=await runtime.accept(project,deployment,source,batch)
        await queue_pending(result['incident_ids'])
        return result

    @app.post('/incidents/{incident_id}/recommendations/review',dependencies=[Depends(auth)])
    async def review(incident_id: str,body: Review):
        try:await runtime.review(incident_id,body.recommendation_id,body.review_hash,body.decision)
        except KeyError:raise HTTPException(404,'Incident not found')
        except ValueError as exc:raise HTTPException(409,str(exc))
        return runtime.store.get(incident_id)

    @app.get('/incidents/{incident_id}/repair-context',dependencies=[Depends(auth)])
    def handoff(incident_id: str):
        try:return runtime.handoff(incident_id)
        except KeyError:raise HTTPException(404,'Incident not found')
        except ValueError as exc:raise HTTPException(422,str(exc))

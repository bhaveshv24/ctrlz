"""Read exact deployed source only: GitHub REST or operator-allowlisted local Git."""
import asyncio
import base64
import json
import os
import re
from pathlib import Path
from urllib.parse import quote
import httpx
from .github import normalize_github
from .runtime_security import Redactor


class SourceEvidence:
    def __init__(self, client, github_token=None, vercel_token=None, local_repositories=None):
        self.client=client
        self.github_token=os.getenv('GITHUB_TOKEN','') if github_token is None else github_token
        self.vercel_token=os.getenv('VERCEL_TOKEN','') if vercel_token is None else vercel_token
        if local_repositories is None:
            try:local_repositories=json.loads(os.getenv('CTRLZ_RUNTIME_LOCAL_REPOS','{}'))
            except ValueError:local_repositories={}
        self.local_repositories=local_repositories
        self.redactor=Redactor([self.github_token,self.vercel_token])

    async def get(self, host, path, token):
        # Constant provider origins and server-generated paths. Never follow redirects.
        headers={'Accept':'application/vnd.github+json','User-Agent':'CtrlZ-Runtime-Monitor'}
        if token:headers['Authorization']='Bearer '+token
        try:
            async with self.client.stream('GET','https://'+host+path,headers=headers,timeout=12,follow_redirects=False) as response:
                if not response.is_success:
                    if host == 'api.github.com' and response.status_code in {403,429} and response.headers.get('x-ratelimit-remaining') == '0':
                        return None,'github_rate_limited'
                    return None,'provider_http_'+str(response.status_code)
                body=b''
                async for chunk in response.aiter_bytes():
                    body+=chunk
                    if len(body)>300000:return None,'provider_response_too_large'
                return json.loads(body),None
        except (httpx.HTTPError,ValueError):
            return None,'provider_unavailable'

    async def vercel_metadata(self, deployment, observed_ref=None):
        ref=observed_ref or deployment.deployment_ref
        if not self.vercel_token or not ref:
            return {'state':'credentials_or_deployment_missing','commit_sha':None}
        query='?teamId='+quote(deployment.vercel_team_id,safe='') if deployment.vercel_team_id else ''
        body,error=await self.get('api.vercel.com','/v13/deployments/'+quote(ref,safe='')+query,self.vercel_token)
        if error or not isinstance(body,dict):return {'state':error or 'invalid_metadata','commit_sha':None}
        if body.get('id') != ref or body.get('projectId',body.get('project',{}).get('id')) != deployment.service_id:
            return {'state':'deployment_project_mismatch','commit_sha':None}
        target=body.get('target') or ('preview' if body.get('readyState') else None)
        if target != deployment.environment:
            return {'state':'deployment_environment_mismatch','commit_sha':None}
        meta=body.get('meta',{})
        sha=meta.get('githubCommitSha')
        repo='/'.join([meta.get('githubCommitOrg',''),meta.get('githubCommitRepo','')])
        return {'state':'observed','commit_sha':sha if isinstance(sha,str) and re.fullmatch(r'[0-9a-f]{40}',sha) else None,'repository':repo if repo!='/' else None,'deployment_ref':ref,'source':'https://api.vercel.com/v13/deployments/'+ref}

    def local_read(self, repository, sha, frames):
        from .repository import git, sensitive
        configured=self.local_repositories.get(repository['full_name'])
        if not configured:return None
        root=Path(configured).resolve()
        actual=normalize_github(git(['config','--get','remote.origin.url'],root))
        if actual['full_name'].lower()!=repository['full_name'].lower():
            return {'state':'repository_mismatch','commit_sha':sha,'files':[]}
        resolved=git(['rev-parse','--verify',sha+'^{commit}'],root)
        if resolved!=sha:raise ValueError('Local commit mismatch')
        files=[]
        for frame in frames[:4]:
            path=frame['path']
            if sensitive(path) or not path.endswith(('.py','.js','.ts','.tsx','.jsx','.mjs','.json')):continue
            spec=sha+':'+path
            try:
                if int(git(['cat-file','-s',spec],root))>65536:continue
                lines=git(['show',spec],root).splitlines()
                line=frame['line'] or 1
                start=max(0,line-21);end=min(len(lines),line+20)
                files.append({'path':path,'line':frame['line'],'start_line':start+1,'context':'\n'.join(f'{n+1}: {lines[n]}' for n in range(start,end))[:8000],'source':f"{repository['url']}/blob/{sha}/{path}#L{line}",'provenance':'operator-allowlisted local Git object; remote publication not established','location_evidence':'observed stack frame' if frame['line'] else 'operator-configured source hint; failing line unknown'})
            except ValueError:continue
        return {'state':'exact_local_revision','commit_sha':sha,'repository':repository,'files':files,'recent_changes':[],'uncertainties':['Local Git object verified against configured repository identity; commit may be unpublished. No recent-change comparison was retrieved.']}

    async def correlate(self, config, deployment, event):
        repo=normalize_github(config.github_url)
        supplied=event.get('commit_sha')
        sha=supplied or deployment.commit_sha
        uncertainty=[]
        metadata=None
        if deployment.platform=='vercel':
            metadata=await self.vercel_metadata(deployment,event.get('deployment_ref'))
            if metadata.get('repository') and metadata['repository'].lower()!=repo['full_name'].lower():
                return {'state':'repository_mismatch','commit_sha':None,'files':[]}
            if metadata.get('commit_sha'):
                if supplied and supplied != metadata['commit_sha']:
                    return {'state':'revision_conflict','commit_sha':None,'files':[]}
                sha=metadata['commit_sha']
            else:uncertainty.append('Vercel deployed revision not independently resolved; supplied revision is an operator/collector assertion.')
        if not sha:return {'state':'unknown_revision','commit_sha':None,'files':[],'uncertainties':['Exact deployed commit unavailable. Current main was not substituted.']}
        if supplied and deployment.commit_sha and supplied != deployment.commit_sha:
            uncertainty.append('Event revision differs from configured deployment revision; analyzing the event revision, not current main.')
        frames=event.get('frames',[])
        if not frames and deployment.source_paths:
            frames=[{'path':path,'line':None} for path in deployment.source_paths]
            uncertainty.append('Source paths were configured by the operator; telemetry did not supply stack frames or a failing line.')
        uncertainty.append('Revision-to-deployment association comes from the configured collector/operator unless independently resolved by provider metadata.')
        if any(f['path'].endswith('.min.js') or '/assets/' in '/'+f['path'] for f in frames):
            uncertainty.append('Minified/bundled stack detected; original source maps are not available.')
        if repo['full_name'] in self.local_repositories:
            try:result=await asyncio.to_thread(self.local_read,repo,sha,frames)
            except (ValueError,OSError):result={'state':'local_revision_unavailable','commit_sha':sha,'files':[]}
            result['uncertainties']=result.get('uncertainties',[])+uncertainty
            return self.redactor.tree(result)
        base='/repos/'+repo['full_name']
        commit,error=await self.get('api.github.com',base+'/commits/'+sha,self.github_token)
        if error or not isinstance(commit,dict) or commit.get('sha')!=sha:
            return {'state':error or 'revision_unavailable','commit_sha':sha,'files':[],'uncertainties':['Commit could not be validated in expected GitHub repository; no fallback to main.']}
        files=[]
        for frame in frames[:4]:
            from .repository import sensitive
            path=frame['path']
            if sensitive(path):continue
            data,failure=await self.get('api.github.com',base+'/contents/'+quote(path,safe='/')+'?ref='+sha,self.github_token)
            if failure or not isinstance(data,dict) or data.get('type')!='file' or data.get('size',65537)>65536 or data.get('encoding')!='base64':continue
            try:lines=base64.b64decode(data['content'],validate=False).decode('utf-8').splitlines()
            except (ValueError,UnicodeError,KeyError):continue
            line=frame['line'] or 1
            start=max(0,line-21);end=min(len(lines),line+20)
            files.append({'path':path,'line':frame['line'],'start_line':start+1,'context':'\n'.join(f'{n+1}: {lines[n]}' for n in range(start,end))[:8000],'source':f"{repo['url']}/blob/{sha}/{quote(path,safe='/')}#L{line}",'provenance':'GitHub REST exact commit','location_evidence':'observed stack frame' if frame['line'] else 'operator-configured source hint; failing line unknown'})
        changes=[{'path':f.get('filename'),'status':f.get('status'),'patch':str(f.get('patch',''))[:2500]} for f in commit.get('files',[])[:5] if not __import__('ctrlz.repository',fromlist=['sensitive']).sensitive(f.get('filename',''))]
        if len(files) < min(4,len(frames)):
            uncertainty.append('Some requested source files were unavailable or outside safety/size bounds; this source context is partial.')
        return self.redactor.tree({'state':'exact_github_revision','commit_sha':sha,'repository':repo,'files':files,'recent_changes':changes,'provider_metadata':metadata,'uncertainties':uncertainty+(['No matching source frames retrieved.'] if not files else [])})

"""Read-only, bounded GitHub evidence. Unknown is never represented by zero."""
import asyncio
import copy
import hashlib
import os
import time
import httpx
from .github import normalize_github


class RepoIntelligence:
    ttl = 300

    def __init__(self, store, client, token=None):
        self.store, self.client = store, client
        self.token = token
        self.locks = {}

    async def scan(self, repository, refresh=False):
        identity = normalize_github(repository)
        token = os.getenv('GITHUB_TOKEN','') if self.token is None else self.token
        scope = hashlib.sha256(token.encode()).hexdigest()[:20]
        key = 'repo-intelligence:'+identity['full_name'].lower()+':'+scope
        async with self.locks.setdefault(key,asyncio.Lock()):
            events = self.store.events(incident_id=key)
            previous = next((e['payload'] for e in reversed(events) if e['stage']=='repository_intelligence'), None)
            if previous and not refresh and time.time()-previous['observed_at'] < self.ttl:
                return {**copy.deepcopy(previous),'cached':True}
            result = {'repository':identity,'observed_at':time.time(),'cached':False,'state':'complete','authentication':'token' if token else 'anonymous','values':{},'warnings':[],'retry_at':None}
            semaphore = asyncio.Semaphore(3)
            headers = {'Accept':'application/vnd.github+json','User-Agent':'CtrlZ-Repo-Intelligence'}
            if token:headers['Authorization']='Bearer '+token
            base = '/repos/'+identity['full_name']

            def value(name, data, source, coverage='complete', reason=None):
                result['values'][name] = {'value':data,'source':source,'observed_at':time.time(),'coverage':coverage,'reason':reason}

            async def request(path, params=None):
                source = 'https://api.github.com'+path
                if result['retry_at']:
                    return None,source,'rate_limited',None
                try:
                    async with semaphore:
                        response = await self.client.get(source,params=params,headers=headers,timeout=8,follow_redirects=False)
                    if response.status_code in {301,302,307,308}:
                        target = response.headers.get('location','')
                        if not target.startswith('https://api.github.com/repos/'):
                            return None,source,'unsafe_redirect',None
                        async with semaphore:
                            response = await self.client.get(target,params=params,headers=headers,timeout=8,follow_redirects=False)
                        source = target
                    source = str(response.request.url)
                    if response.status_code in {403,429} and (response.headers.get('x-ratelimit-remaining')=='0' or response.status_code==429 or 'rate limit' in response.text.lower()):
                        try:retry = time.time()+float(response.headers['retry-after']) if 'retry-after' in response.headers else float(response.headers.get('x-ratelimit-reset',time.time()+60))
                        except ValueError:retry=time.time()+60
                        result['retry_at']=max(time.time()+1,retry)
                        result['state']='rate_limited'
                        return None,source,'rate_limited',response
                    if response.status_code==404:return None,source,'not_found_or_inaccessible',response
                    if response.status_code==401:return None,source,'token_rejected',response
                    if response.status_code in {204,409}:return None,source,'empty_or_unavailable',response
                    if not response.is_success:return None,source,'access_denied' if response.status_code==403 else 'github_unavailable',response
                    return response.json(),source,None,response
                except (httpx.HTTPError,ValueError):
                    return None,source,'timeout_or_invalid_response',None

            meta,source,error,_ = await request(base)
            if not isinstance(meta,dict) or not meta.get('full_name'):
                result['state']=error or 'github_unavailable'
                value('repository',None,source,'unavailable',result['state'])
                if previous:
                    result['previous_snapshot']={'observed_at':previous['observed_at'],'values':previous['values']}
                self.store.record(key,'repository_intelligence',result)
                return result
            canonical = normalize_github(meta['full_name'])
            result['repository']=canonical
            for name,field in [('archived','archived'),('fork','fork'),('size_kib','size'),('default_branch','default_branch'),('last_activity','pushed_at')]:
                value(name,meta.get(field),source,'complete' if field in meta else 'unavailable')
            value('license',meta.get('license'),source,'complete' if 'license' in meta else 'unavailable','No license detected' if 'license' in meta and meta['license'] is None else None)
            # Resolve the canonical default-branch SHA before querying CI.
            commits,csource,cerror,_ = await request(base+'/commits',{'per_page':1})
            empty = cerror=='empty_or_unavailable' or isinstance(commits,list) and not commits
            value('empty',True if empty else False if isinstance(commits,list) and commits else None,csource,'complete' if empty or isinstance(commits,list) else 'unavailable',cerror)
            head = commits[0] if isinstance(commits,list) and commits else None
            value('last_commit',{'sha':head.get('sha'),'message':head.get('commit',{}).get('message'),'date':head.get('commit',{}).get('committer',{}).get('date'),'url':head.get('html_url')} if head else None,csource,'complete' if head else 'unavailable','No commits yet' if empty else cerror)
            sha = head.get('sha') if head else None

            async def load(name,path,params=None,transform=None):
                data,origin,failure,response = await request(path,params)
                coverage = 'sampled' if response is not None and 'rel="next"' in response.headers.get('link','') else 'complete'
                try:
                    if failure:raise ValueError(failure)
                    if name=='readme':data={'present':True,'path':data['path'],'url':data.get('html_url')}
                    elif transform:
                        if isinstance(data,dict) and type(data.get('total_count')) is int:
                            rows = data.get('workflow_runs',data.get('check_runs',[]))
                            if data['total_count'] > len(rows):coverage='sampled'
                        data=transform(data)
                    value(name,data,origin,coverage)
                except (ValueError,KeyError,TypeError):
                    if name=='readme' and failure=='not_found_or_inaccessible' and meta.get('private') is False:value(name,{'present':False},origin)
                    else:value(name,None,origin,'unavailable',failure or 'invalid_response')
                return data,response,failure

            jobs = [load('languages',base+'/languages'),load('contributors',base+'/contributors',{'per_page':100},lambda rows:[{'login':r.get('login'),'contributions':r.get('contributions')} for r in rows]),load('readme',base+'/readme')]
            for kind in ['issues','prs']:
                query=f'repo:{canonical["full_name"]} is:{"issue" if kind=="issues" else "pr"} is:open'
                async def count(name=kind,q=query):
                    data,origin,failure,_ = await request('/search/issues',{'q':q,'per_page':1})
                    if failure or not isinstance(data,dict) or type(data.get('total_count')) is not int:
                        value('open_'+name,None,origin,'unavailable',failure or 'invalid_response')
                    else:value('open_'+name,data['total_count'],origin,'sampled' if data.get('incomplete_results') else 'complete','GitHub search index count')
                jobs.append(count())
            if sha:
                jobs += [load('workflow_runs',base+'/actions/runs',{'head_sha':sha,'per_page':20},lambda d:d['workflow_runs']),load('check_runs',base+'/commits/'+sha+'/check-runs',{'per_page':100},lambda d:d['check_runs']),load('commit_status',base+'/commits/'+sha+'/status',transform=lambda d:{'state':d['state'],'statuses':d['statuses']})]
            await asyncio.gather(*jobs)
            if sha:
                checks=[];unavailable=False;sampled=False
                for name in ['workflow_runs','check_runs','commit_status']:
                    item=result['values'][name];unavailable |= item['coverage']=='unavailable';sampled |= item['coverage']=='sampled'
                    rows=item['value'] if name!='commit_status' else (item['value'] or {}).get('statuses')
                    for row in rows or []:
                        if row.get('head_sha') and row['head_sha']!=sha:continue
                        status=row.get('conclusion') or row.get('state') or row.get('status')
                        checks.append({'name':row.get('name') or row.get('context') or 'Workflow','status':status,'url':row.get('html_url') or row.get('target_url'),'head_sha':sha})
                failing=[c for c in checks if c['status'] in {'failure','error','timed_out','action_required','startup_failure'}]
                ci='failing' if failing else 'unknown' if unavailable else 'no_ci' if not checks else 'pending' if any(c['status'] in {'queued','in_progress','pending','waiting','requested'} for c in checks) else 'passing' if all(c['status'] in {'success','neutral','skipped'} for c in checks) else 'attention'
                value('ci',{'status':ci,'head_sha':sha,'checks':checks,'failing_checks':failing},'GitHub Actions, check runs and commit statuses on HEAD','sampled' if unavailable or sampled else 'complete')
            else:value('ci',None,csource,'unavailable','No observable HEAD')
            for name in ['workflow_runs','check_runs','commit_status']:result['values'].pop(name,None)
            if empty:result['state']='empty'
            elif any(v['coverage']=='unavailable' for v in result['values'].values()) and result['state']=='complete':result['state']='partial'
            if result['retry_at'] and previous:result['previous_snapshot']={'observed_at':previous['observed_at'],'values':previous['values']}
            result['warnings']=[f'{name}: {v["reason"] or "unavailable"}' for name,v in result['values'].items() if v['coverage']=='unavailable']
            self.store.record(key,'repository_intelligence',result)
            return result

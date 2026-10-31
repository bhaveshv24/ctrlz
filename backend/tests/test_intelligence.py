import asyncio
import httpx
import pytest
from ctrlz.github import normalize_github
from ctrlz.intelligence import RepoIntelligence
from ctrlz.store import Store

@pytest.mark.parametrize('text',['owner/repo','https://github.com/owner/repo','https://github.com/owner/repo.git','git@github.com:owner/repo.git','ssh://git@github.com/owner/repo.git','https://github.com/owner/repo/tree/main/src','https://github.com/owner/repo/blob/main/file.py'])
def test_shared_normalizer(text):
    assert normalize_github(text)['url']=='https://github.com/owner/repo'

@pytest.mark.parametrize('text',['','owner','https://evil.test/owner/repo','https://token@github.com/owner/repo','owner/../repo','https://github.com:8080/owner/repo','https://github.com/owner/repo/unknown'])
def test_malformed_inputs(text):
    with pytest.raises(ValueError):normalize_github(text)


def handler(mode,seen):
    def response(request):
        seen.append(request)
        path=request.url.path
        if mode in {'not_found','private'} and path=='/repos/owner/repo':return httpx.Response(404)
        if mode=='outage':return httpx.Response(503)
        if path=='/repos/owner/repo':return httpx.Response(200,json={'full_name':'owner/repo','private':False,'default_branch':'main','archived':mode=='archived','fork':mode=='fork','size':2,'pushed_at':'2026-10-30T00:00:00Z','license':None})
        if path.endswith('/commits'):
            if mode=='empty':return httpx.Response(409)
            return httpx.Response(200,json=[{'sha':'abc','commit':{'message':'Update','committer':{'date':'2026-10-30T00:00:00Z'}}}])
        if path.endswith('/languages'):
            if mode=='timeout':raise httpx.ReadTimeout('timeout',request=request)
            if mode=='rate_limit':return httpx.Response(403,headers={'x-ratelimit-remaining':'0','x-ratelimit-reset':'1999999999'},json={'message':'API rate limit exceeded'})
            if mode=='partial':return httpx.Response(403)
            return httpx.Response(200,json={'Python':100})
        if path.endswith('/contributors'):return httpx.Response(200,json=[{'login':'dev','contributions':3}],headers={'link':'<https://api.github.com/repos/owner/repo/contributors?page=2>; rel="next"'})
        if path.endswith('/readme'):return httpx.Response(404)
        if path=='/search/issues':return httpx.Response(200,json={'total_count':2,'incomplete_results':False})
        if path.endswith('/actions/runs'):return httpx.Response(200,json={'total_count':0,'workflow_runs':[]})
        if path.endswith('/check-runs'):return httpx.Response(200,json={'total_count':1 if mode=='failing' else 0,'check_runs':[{'name':'Tests','conclusion':'failure','head_sha':'abc','html_url':'https://github.com/owner/repo/actions/runs/1'}] if mode=='failing' else []})
        if path.endswith('/status'):return httpx.Response(200,json={'state':'pending','statuses':[]})
        raise AssertionError(path)
    return response

@pytest.mark.parametrize('mode',['public','private','not_found','empty','archived','fork','no_ci','rate_limit','timeout','partial','outage','failing'])
async def test_each_scan_scenario(tmp_path,monkeypatch,mode):
    monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    store=Store(f'sqlite:///{tmp_path}/scan.db');seen=[]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler(mode,seen))) as client:
        result=await RepoIntelligence(store,client).scan('owner/repo')
    values=result['values']
    assert all({'value','source','coverage','observed_at'}<=set(v) for v in values.values())
    if mode in {'private','not_found'}:assert result['state']=='not_found_or_inaccessible'
    elif mode=='outage':assert result['state']=='github_unavailable'
    elif mode=='empty':assert result['state']=='empty' and values['empty']['value'] is True and values['ci']['coverage']=='unavailable'
    elif mode=='archived':assert values['archived']['value'] is True
    elif mode=='fork':assert values['fork']['value'] is True
    elif mode=='rate_limit':assert result['retry_at']==1999999999 and values['last_commit']['value']['sha']=='abc'
    elif mode in {'timeout','partial'}:assert values['languages']['coverage']=='unavailable' and result['state']=='partial'
    elif mode=='failing':assert values['ci']['value']['status']=='failing' and values['ci']['value']['failing_checks'][0]['head_sha']=='abc'
    else:assert values['ci']['value']['status']=='no_ci'
    if mode in {'public','no_ci'}:
        assert values['license']['value'] is None and values['license']['coverage']=='complete'
        assert values['readme']['value']=={'present':False}
        assert values['contributors']['coverage']=='sampled'
    assert store.events()[-1]['stage']=='repository_intelligence'
    store.engine.dispose()

async def test_cache_refresh_and_credential_isolation(tmp_path,monkeypatch):
    store=Store(f'sqlite:///{tmp_path}/cache.db');seen=[];monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler('public',seen))) as client:
        scan=RepoIntelligence(store,client)
        first=await scan.scan('owner/repo');count=len(seen)
        assert (await scan.scan('https://github.com/owner/repo.git'))['cached'] and len(seen)==count
        await scan.scan('owner/repo',True);assert len(seen)>count
        monkeypatch.setenv('GITHUB_TOKEN','test-token-not-a-real-secret')
        assert not (await scan.scan('owner/repo'))['cached']
        assert seen[-1].headers['Authorization']=='Bearer test-token-not-a-real-secret'
    assert first['authentication']=='anonymous'
    store.engine.dispose()

async def test_refresh_preserves_previous_snapshot_when_rate_limited(tmp_path):
    store=Store(f'sqlite:///{tmp_path}/partial.db');seen=[];mode=['public']
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:handler(mode[0],seen)(r))) as client:
        scan=RepoIntelligence(store,client);first=await scan.scan('owner/repo');mode[0]='rate_limit'
        second=await scan.scan('owner/repo',True)
        assert second['previous_snapshot']['values']==first['values'] and second['retry_at']
    store.engine.dispose()

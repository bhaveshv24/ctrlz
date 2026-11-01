import httpx,pytest
from ctrlz.render_readonly import RenderReadOnly

def test_bound_service_and_paginated_redacted_deduplicated_logs():
    calls=[]
    def handler(req):
        assert req.method=='GET' and req.headers['Authorization']=='Bearer private-test-key'
        calls.append(req)
        if req.url.path.endswith('/services'):return httpx.Response(200,json=[{'service':{'id':'srv-good','ownerId':'tea-owner','serviceDetails':{'url':'https://campuspass.test'}}}])
        assert req.url.params['resource']=='srv-good' and req.url.params['ownerId']=='tea-owner'
        log={'id':'event1','message':'order-1 password=hidden student@example.test','timestamp':'2026-11-01T00:00:00Z','labels':[{'name':'resource','value':'srv-good'}]}
        bad={**log,'id':'wrong-service','labels':[{'name':'resource','value':'srv-other'}]}
        return httpx.Response(200,json={'logs':[log,bad],'hasMore':len(calls)==2,'nextStartTime':'2026-11-01T00:00:00Z','nextEndTime':'2026-11-01T01:00:00Z'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        r=RenderReadOnly(c,'private-test-key');service=r.service('https://campuspass.test')
        logs,truncated=r.logs(service,'order-1')
        assert len(logs)==1 and not truncated
        assert 'hidden' not in logs[0]['message'] and 'student@' not in logs[0]['message']
        assert r.logs(service,'order-1',['event1'])[0]==[]

@pytest.mark.parametrize('status',[401,403,429,503])
def test_provider_failure_never_claims_connection(status):
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(status))) as c:
        with pytest.raises(RuntimeError,match=str(status)):RenderReadOnly(c,'private-test-key').service('https://campuspass.test')

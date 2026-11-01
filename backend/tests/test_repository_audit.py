import json
from pathlib import Path
import httpx
import pytest
from ctrlz.repository_audit import source_review, dependency_review, inspect_all
from ctrlz.models import ImportRequest


def test_static_source_risks_syntax_and_secret_redaction_without_execution(tmp_path):
    marker = tmp_path/'executed'
    secret = 'do-not-echo-this-credential'
    (tmp_path/'app.py').write_text(f"from subprocess import run as command\nimport pathlib\npathlib.Path({str(marker)!r}).write_text('unsafe')\ncommand('echo '+input(),shell=True)\npassword='{secret}'\n",encoding='utf-8')
    (tmp_path/'broken.py').write_text('def unfinished(:\n',encoding='utf-8')
    (tmp_path/'web.ts').write_text('element.innerHTML = userInput;',encoding='utf-8')
    report = source_review(tmp_path)
    assert not marker.exists()
    assert {'shell-execution','embedded-credential','html-injection'} <= {f['rule'] for f in report['findings']}
    assert report['syntax_errors'][0]['path'] == 'broken.py'
    assert secret not in json.dumps(report)


async def test_advisory_scan_queries_exact_versions_and_reports_matches(tmp_path):
    (tmp_path/'requirements.txt').write_text('requests==2.19.0\nflask>=2\n',encoding='utf-8')
    def response(request):
        body = json.loads(request.content)
        assert body == {'queries':[{'package':{'ecosystem':'PyPI','name':'requests'},'version':'2.19.0'}]}
        assert 'source' not in request.content.decode()
        return httpx.Response(200,json={'results':[{'vulns':[{'id':'GHSA-test-advisory'}]}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        result = await dependency_review(tmp_path,client)
    assert result['state'] == 'findings'
    assert result['findings'][0]['package'] == 'requests'
    assert result['coverage_gaps']


@pytest.mark.parametrize('payload', [{'results':[]},{'results':[{'error':{'message':'unavailable'}}]}])
async def test_incomplete_or_failed_provider_is_not_reported_as_clean(tmp_path,payload):
    (tmp_path/'requirements.txt').write_text('requests==2.19.0',encoding='utf-8')
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload))) as client:
        assert (await dependency_review(tmp_path,client))['state'] == 'unavailable'


async def test_npm_transitive_dependencies_and_no_lock_coverage(tmp_path):
    (tmp_path/'package-lock.json').write_text(json.dumps({'packages':{'':{'name':'my-private-source'},'node_modules/a':{'version':'1.2.3'},'node_modules/a/node_modules/@scope/b':{'version':'2.0.0'}}}),encoding='utf-8')
    def response(request):
        queries = json.loads(request.content)['queries']
        assert {q['package']['name'] for q in queries} == {'a','@scope/b'}
        return httpx.Response(200,json={'results':[{},{}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        result = await dependency_review(tmp_path,client)
        assert result['state'] == 'no_known_advisories' and result['packages_checked'] == 2
        (tmp_path/'package-lock.json').unlink()
        (tmp_path/'package.json').write_text('{}',encoding='utf-8')
        assert (await dependency_review(tmp_path,client))['state'] == 'not_checked'


async def test_inspect_works_without_docker_and_cannot_read_another_workspace(tmp_path):
    from test_repository_diagnosis import imported
    runner,snapshot = imported(tmp_path)
    request = ImportRequest(repository=snapshot['repository'])
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:pytest.fail('No exact dependencies to query'))) as client:
        result = await inspect_all(runner,request,False,client)
        assert result['inspection']['source']['files_checked'] >= 2
        assert result['inspection']['tests']['state'] == 'not_run'
        assert result['status'] == 'blocked' and result['baseline']['cases'] == []
        with pytest.raises(ValueError):await inspect_all(runner,ImportRequest(repository=str(tmp_path/'outside')),False,client)


async def test_passing_tests_do_not_hide_static_risks(tmp_path,monkeypatch):
    from test_repository_diagnosis import imported
    runner,snapshot = imported(tmp_path, 'def allowed(value):\n    return eval(value)\n')
    monkeypatch.setattr(runner,'diagnose',lambda request:{'status':'healthy','message':'Tests pass','passed':1,'failed':0,'skipped':0,'baseline':{'cases':[]}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:pytest.fail('No pinned packages'))) as client:
        result=await inspect_all(runner,ImportRequest(repository=snapshot['repository']),True,client)
    assert result['inspection']['summary']=='review_required'
    assert result['inspection']['source']['findings'][0]['rule']=='dynamic-code'
    assert 'need review' in result['message']


async def test_audit_endpoint_auth_and_host_without_runner(tmp_path,monkeypatch):
    from test_repository_diagnosis import imported
    from ctrlz.main import create_app
    from ctrlz.store import Store
    runner,snapshot=imported(tmp_path)
    monkeypatch.setenv('CTRLZ_OPERATOR_TOKEN','audit-test-token')
    monkeypatch.setenv('CTRLZ_CODE_EXECUTION_ENABLED','false')
    monkeypatch.setenv('IMPORT_ROOT',str(runner.root))
    monkeypatch.setenv('DATA_DIR',str(tmp_path/'data'))
    class Reasoner:provider='audit fixture'
    class Books:
        def search(self, query):return []
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:pytest.fail('No pinned packages'))) as outbound:
        app=create_app(store=Store('sqlite:///'+str(tmp_path/'api.db')),client=outbound,reasoner=Reasoner(),runbooks=Books(),monitor=False)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            body={'repository':snapshot['repository']}
            assert (await client.post('/repositories/audit',json=body)).status_code==401
            response=await client.post('/repositories/audit',json=body,headers={'X-Operator-Token':'audit-test-token'})
            assert response.status_code==200,response.text
            assert response.json()['inspection']['tests']['state']=='not_run'
            assert (await client.post('/repositories/audit',json={'repository':str(tmp_path/'foreign')},headers={'X-Operator-Token':'audit-test-token'})).status_code==422


async def test_pagination_is_visible_as_partial_coverage(tmp_path):
    (tmp_path/'requirements.txt').write_text('requests==2.19.0',encoding='utf-8')
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'results':[{'next_page_token':'more'}]}))) as client:
        result=await dependency_review(tmp_path,client)
    assert 'partial' in ' '.join(result['coverage_gaps'])


async def test_monorepo_dependency_manifests_are_included(tmp_path):
    backend=tmp_path/'backend';backend.mkdir()
    (backend/'requirements.txt').write_text('requests==2.19.0',encoding='utf-8')
    skipped=tmp_path/'node_modules';skipped.mkdir()
    (skipped/'requirements.txt').write_text('private-package==1.0.0',encoding='utf-8')
    def response(request):
        queries=json.loads(request.content)['queries']
        assert len(queries)==1 and queries[0]['package']['name']=='requests'
        return httpx.Response(200,json={'results':[{}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        assert (await dependency_review(tmp_path,client))['packages_checked']==1

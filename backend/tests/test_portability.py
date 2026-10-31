"""Portability contracts and source trust boundaries; no live model calls."""
import io
import json
import zipfile
import httpx
import pytest
from pydantic import ValidationError
from ctrlz.models import Project, Candidate, Action
from ctrlz.repository import RepositoryImports, RepositorySource, inspect_repository, editable
from ctrlz.http_adapter import HTTPAdapter
from ctrlz.safety import evaluate
from ctrlz.continuation import acceptance
from ctrlz.engine import Engine
from ctrlz.store import Store


def queue_project(risk='low'):
    return Project(id='dispatch', name='Dispatch service', base_url='https://dispatch.test', contract={'allowed':['resume_dispatch']}, integration={'diagnostics_path':'/internal/state', 'health_checks':[{'pointer':'/ready','value':True}], 'service_checks':[{'pointer':'/paused','value':False,'label':'Dispatcher running'}], 'operations':[{'name':'resume_dispatch','description':'Resume a paused dispatch queue without dropping jobs','path':'/internal/resume','effect':'resume','risk':risk,'preconditions':[{'pointer':'/paused','value':True,'label':'Dispatcher paused'}]}]})


async def test_generic_service_recovery_and_unknown_operation_rejection(tmp_path):
    state = {'paused': True, 'revision': 4}; seen = []
    def service(request):
        if request.url.path == '/health':return httpx.Response(200,json={'ready':not state['paused']})
        if request.method == 'GET':return httpx.Response(200,json=state)
        payload=json.loads(request.content); seen.append(payload)
        if payload['expected_revision'] != state['revision']:return httpx.Response(409)
        state.update(paused=False,revision=5)
        return httpx.Response(200,json={'resumed':True})
    class Fixture:
        provider='explicit test fixture'
        async def diagnose(self,*args):return 'Paused dispatcher'
        async def plan(self,*args,**kwargs):
            from ctrlz.models import RecoveryPlan
            return RecoveryPlan(diagnosis='Paused queue',candidates=[Candidate(id='resume',rationale='Resume existing queue',actions=[Action(operation='resume_dispatch')]),Candidate(id='bad',rationale='Unregistered',actions=[Action(operation='erase_queue')])])
    store=Store(f'sqlite:///{tmp_path}/dispatch.db'); project=queue_project(); store.save_project(project.model_dump())
    async with httpx.AsyncClient(transport=httpx.MockTransport(service)) as client:
        adapter=HTTPAdapter(project,client)
        assert list(adapter.faults(await adapter.read('health'),await adapter.read('workflows')))
        incident,_=store.create(project.id,'outage','service',{})
        await Engine(store,client,Fixture(),None).run(incident['id'])
        result=store.get(incident['id'])
        assert result['status']=='resolved',result
        assert result['verification']['passed']
        assert not next(r for r in result['tournament'] if r['candidate_id']=='bad')['eligible']
        assert len(seen)==1 and seen[0]['expected_revision']==4
    store.engine.dispose()


async def test_default_monitoring_needs_no_campus_fields():
    project=Project(id='web',name='Unrelated service',base_url='https://web.test')
    assert project.adapter=='generic-http-v1' and project.contract.allowed==[]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'status':'up'}))) as client:
        adapter=HTTPAdapter(project,client)
        assert list(adapter.faults(await adapter.read('health'),await adapter.read('workflows')))==[]
        assert (await adapter.read('workflows'))['configured'] is False


def test_risky_operation_requires_approval_and_parameters_are_exact():
    project=queue_project('high'); adapter=HTTPAdapter(project,None); diagnostics={'ok':True,'configured':True,'body':{'revision':2,'paused':True}}
    candidate=Candidate(id='resume',rationale='Resume queue',actions=[Action(operation='resume_dispatch')])
    assert evaluate(candidate,project,diagnostics,adapter,'service')['approval_required']
    candidate.actions[0].parameters={'shell':'rm'}
    assert not evaluate(candidate,project,diagnostics,adapter,'service',True)['eligible']
    assert not evaluate(Candidate(id='unknown',rationale='No',actions=[Action(operation='unknown')]),project,diagnostics,adapter,'service',True)['eligible']


async def test_http_success_is_insufficient_when_postcondition_fails():
    project=queue_project()
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'ready':True,'paused':True}))) as client:
        assert not (await HTTPAdapter(project,client).verify('outage','service'))['passed']


@pytest.mark.parametrize('path',['https://evil.test/state','//evil','/../secrets','/a?url=x'])
def test_integration_paths_cannot_escape_registered_origin(path):
    with pytest.raises(ValidationError):Project(id='web',name='Web',base_url='https://web.test',integration={'diagnostics_path':path})


def zip_bytes(files):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as archive:
        for path,content in files.items():
            # ZipInfo's constructor normalizes backslashes on Windows. Assign after
            # construction so malicious archive fixtures keep their actual bytes.
            entry = zipfile.ZipInfo()
            entry.filename = path
            archive.writestr(entry, content)
    return data.getvalue()


def test_zip_import_profiles_and_secret_omission(tmp_path):
    result=RepositoryImports(tmp_path/'imports').import_zip(zip_bytes({'sample/src/index.mjs':'export const a=1','sample/test/index.test.mjs':"import {test} from 'node:test'; test('a',()=>{});",'sample/package.json':json.dumps({'scripts':{'test':'node --test'},'type':'module'}),'sample/.env':'SECRET=never-copy','sample/node_modules/evil.js':'bad'}))
    assert result['supported'] and result['profile']=='node-test'
    assert not (tmp_path/'imports'/result['id']/'.env').exists()
    assert result['provenance']['kind']=='zip'
    assert len(result['tests'])==1


@pytest.mark.parametrize('path',['../outside.py','/absolute.py','folder/../../escape.py','x\\escape.py'])
def test_zip_path_traversal_is_rejected(tmp_path,path):
    with pytest.raises(ValueError):RepositoryImports(tmp_path/'imports').import_zip(zip_bytes({path:'bad'}))
    assert list((tmp_path/'imports').iterdir())==[]


def test_local_source_copy_and_external_path_denial(tmp_path,monkeypatch):
    root=tmp_path/'sources'; source=root/'original'; source.mkdir(parents=True)
    (source/'main.py').write_text('def ready(): return True')
    (source/'test_main.py').write_text('from main import ready\ndef test_ready(): assert ready()')
    monkeypatch.setenv('REPOSITORY_SOURCE_ROOTS',str(root))
    imports=RepositoryImports(tmp_path/'imports'); result=imports.import_source(RepositorySource(kind='local',source=str(source)))
    assert result['profile']=='python-pytest' and result['supported']
    assert (source/'.git').exists() is False
    with pytest.raises(ValueError):imports.import_source(RepositorySource(kind='local',source='/tmp'))


def test_unsupported_runner_and_dependency_url_fail_closed(tmp_path):
    (tmp_path/'main.py').write_text('a=1'); (tmp_path/'test_main.py').write_text('def test_one(): assert False')
    (tmp_path/'requirements.txt').write_text('unsafe @ https://other.test/code.whl')
    assessment=inspect_repository(tmp_path)
    assert not assessment['supported'] and 'URL/path' in assessment['warnings'][0]
    assert not editable('tests/test_changed.ts') and not editable('vitest.config.ts') and editable('src/format.ts')


def test_acceptance_prevents_disappearing_tests_or_new_skips():
    baseline={'exit_code':1,'output':'failed','cases':[{'id':'a','passed':False,'status':'failed'},{'id':'b','passed':True,'status':'passed'}]}
    candidate={'exit_code':0,'output':'','cases':[{'id':'a','passed':True,'status':'passed'}]}
    assert not all(acceptance(baseline,candidate,True)[0].values())
    candidate['cases'].append({'id':'b','passed':False,'status':'skipped'})
    assert not acceptance(baseline,candidate,True)[0]['no_new_skips']


async def test_authenticated_upload_inspection_and_dependency_consent(tmp_path,monkeypatch):
    from ctrlz.main import create_app
    monkeypatch.setenv('CTRLZ_OPERATOR_TOKEN','test-operator')
    monkeypatch.setenv('IMPORT_ROOT',str(tmp_path/'imports'))
    monkeypatch.setenv('DATA_DIR',str(tmp_path/'data'))
    store=Store(f'sqlite:///{tmp_path}/api.db')
    class Books:
        def search(self,query):return []
    app=create_app(store=store,runbooks=Books(),monitor=False)
    contents=zip_bytes({'source.py':'def ready():return True','test_source.py':'def test_source():assert False','requirements.txt':'typing-extensions==4.16.0'})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.post('/repositories/upload',content=contents)).status_code==401
        headers={'X-Operator-Token':'test-operator'}
        imported=await client.post('/repositories/upload',content=contents,headers=headers)
        assert imported.status_code==201,imported.text
        data=imported.json()
        inspected=await client.get('/repositories/inspect',params={'repository':data['repository']},headers=headers)
        assert inspected.json()['dependency_install_required']
        refused=await client.post('/continuations',json={'repository':data['repository'],'requirements':'Repair the failing test without changing acceptance'},headers=headers)
        assert refused.status_code==422 and 'Approve' in refused.text
        assert store.incidents()==[]
    await app.state.engine.client.aclose();store.engine.dispose()


def test_custom_pytest_acceptance_filenames_are_protected(tmp_path):
    (tmp_path/'library.py').write_text('def value():return 1')
    (tmp_path/'checks.py').write_text('def check_value():assert False')
    (tmp_path/'pytest.ini').write_text('[pytest]\npython_files = checks.py\npython_functions = check_*\n')
    result=inspect_repository(tmp_path,'python-pytest')
    assert result['tests']==['checks.py'] and result['editable_files']==['library.py']


def test_embedded_doctest_changes_are_detected(tmp_path):
    from ctrlz.continuation import embedded_doctests
    file=tmp_path/'library.py'
    file.write_text('def value():\n    """>>> value()\n    1\n    """\n    return 0\n')
    before=embedded_doctests(tmp_path,['library.py'])
    file.write_text(file.read_text().replace('return 0','return 1'))
    assert embedded_doctests(tmp_path,['library.py'])==before
    file.write_text(file.read_text().replace('    1\n','    0\n'))
    assert embedded_doctests(tmp_path,['library.py'])!=before

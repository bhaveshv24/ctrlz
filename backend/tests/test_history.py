import json
from pathlib import Path
import pytest
from ctrlz.repository import RepositoryImports,RepositorySource,git
from ctrlz.code_tournament import choose,diff_size


def commit(repo,message):
    git(['add','--force','.'],repo)
    git(['-c','user.name=Fixture','-c','user.email=test@localhost','commit','--allow-empty','-m',message],repo)
    return git(['rev-parse','HEAD'],repo)


def history_fixture(root):
    root.mkdir();git(['init','-b','main'],root)
    (root/'calc.py').write_text('def total(a,b):\n    return a+b\n')
    (root/'test_calc.py').write_text('from calc import total\ndef test_total(): assert total(2,3)==5\n')
    (root/'.env').write_text('FIXTURE_SECRET=excluded-value-not-real\n')
    good=commit(root,'good')
    (root/'calc.py').write_text('def total(a,b):\n    return a-b\n');bad=commit(root,'bad')
    (root/'README.md').write_text('Fixture only');commit(root,'unrelated documentation')
    return good,bad


def test_import_preserves_sanitized_source_history_not_original_objects(tmp_path,monkeypatch):
    source=tmp_path/'source';good,bad=history_fixture(source)
    monkeypatch.setenv('REPOSITORY_SOURCE_ROOTS',str(tmp_path))
    data=RepositoryImports(tmp_path/'imports').import_source(RepositorySource(kind='local',source=str(source)))
    repo=Path(data['repository']);assert 2<=len(data['history'])<=30
    assert bad in [r['upstream_commit'] for r in data['history']]
    for entry in data['history']:
        files=git(['ls-tree','-r','--name-only',entry['snapshot_commit']],repo).splitlines()
        assert '.env' not in files
        assert git(['show',entry['snapshot_commit']+':test_calc.py'],repo)==git(['show','HEAD:test_calc.py'],repo)
    assert (source/'.env').exists() and not (repo/'.env').exists()
    assert git(['log','--all','--format=%s'],repo).splitlines()[0]=='Explicitly imported source snapshot'


def test_strategy_selection_is_deterministic():
    strategies=[{'id':'REPLAN','eligible':True,'diff_lines':4,'sandbox_runs':1},{'id':'COMPENSATE','eligible':True,'diff_lines':2,'sandbox_runs':5},{'id':'RETRY','eligible':False,'diff_lines':0,'sandbox_runs':2}]
    assert choose(strategies)['id']=='COMPENSATE'
    strategies[0]['diff_lines']=2
    assert choose(strategies)['id']=='REPLAN'
    assert diff_size('--- a\n+++ b\n-a\n+b\n context\n')==2


@pytest.mark.skipif(__import__('os').getenv('RUN_DOCKER_TESTS')!='1',reason='Requires actual Docker runtime')
async def test_known_bad_history_compensates_as_patch_only(tmp_path,monkeypatch):
    from ctrlz.store import Store
    from ctrlz.continuation import Continuation
    from ctrlz.models import ImportRequest,CodeProposal,FileChange
    from ctrlz.brief import receipt_markdown
    from ctrlz.engine import Engine
    source=tmp_path/'source';_,bad=history_fixture(source);monkeypatch.setenv('REPOSITORY_SOURCE_ROOTS',str(tmp_path))
    imported=RepositoryImports(tmp_path/'imports').import_source(RepositorySource(kind='local',source=str(source)))
    class Fixture:
        provider='Explicit test fixture'
        async def code(self,*args):return CodeProposal(diagnosis='Deliberately nonpassing test candidate',changes=[FileChange(path='calc.py',content='def total(a,b):\n    return a*b\n')])
    store=Store(f'sqlite:///{tmp_path}/history.db');incident,_=store.create('code-import','code',imported['repository'],{})
    await Continuation(store,Fixture(),tmp_path/'imports',tmp_path/'patches').run(incident['id'],ImportRequest(repository=imported['repository'],requirements='Repair total and preserve the existing acceptance suite'))
    result=store.get(incident['id']);assert result['status']=='resolved',result
    assert result['selected_code_strategy']=='COMPENSATE' and result['suspect_commit']['upstream_commit']==bad
    strategies={s['id']:s for s in result['code_tournament']}
    assert set(strategies)=={'RETRY','COMPENSATE','REPLAN'}
    assert strategies['COMPENSATE']['sandbox_runs']<=6 and strategies['RETRY']['sandbox_runs']==2
    assert 'return a+b' in result['patch'] and (source/'calc.py').read_text().endswith('return a-b\n')
    assert (Path(imported['repository'])/'calc.py').read_text().endswith('return a-b\n')
    assert 'COMPENSATE' in receipt_markdown(Engine(store,None,Fixture(),None).receipt(incident['id']))
    patch=tmp_path/'review.patch';patch.write_text(result['patch'])
    git(['apply','--check',str(patch)],source)
    assert any(e['stage']=='tournament' for e in store.events())
    store.engine.dispose()


async def test_retry_requires_two_passing_reruns_and_no_invented_patch():
    from ctrlz.code_tournament import CodeTournament
    baseline={'exit_code':1,'cases':[{'id':'original','passed':False,'status':'failed'}],'output':'failed'}
    passed={'exit_code':0,'cases':[{'id':'original','passed':True,'status':'passed'}],'output':'passed'}
    class Store:
        def record(self,*args):pass
    class Sandbox:
        def __init__(self,results):self.results=iter(results)
        def run(self):return next(self.results)
    def check(result):return {'passed':result['exit_code']==0},{}
    tournament=CodeTournament.__new__(CodeTournament)
    tournament.store=Store();tournament.incident_id='test';tournament.strategies=[];tournament.check=check
    tournament.sandbox=Sandbox([passed,baseline])
    assert not (await tournament.retry())['eligible']
    tournament.sandbox=Sandbox([passed,passed])
    result=await tournament.retry()
    assert result['eligible'] and result['patch']=='' and result['sandbox_runs']==2 and 'flaky' in result['reason']

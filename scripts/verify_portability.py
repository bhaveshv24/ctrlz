"""Live NIM proof: disclosed upstream regression and independent TypeScript fixture.
Run from backend: .venv/bin/python ../scripts/verify_portability.py
Never executes imported code on the host. Full receipts remain in data/.
"""
import asyncio,json,os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv('../.env',override=True)
from ctrlz.repository import RepositoryImports,RepositorySource,git,inspect_repository
from ctrlz.sandbox import Sandbox
from ctrlz.continuation import Continuation
from ctrlz.models import ImportRequest
from ctrlz.reasoning import NIMReasoner
from ctrlz.store import Store
from ctrlz.engine import Engine

async def repair(store,snapshot,requirements):
    request=ImportRequest(repository=snapshot['repository'],requirements=requirements,install_dependencies=True)
    incident,_=store.create('code-import','code',snapshot['repository'],{'requirements':requirements,'proof':'Live NIM portability validation'})
    store.update(incident['id'],import_request=request.model_dump())
    store.record(incident['id'],'detect',{'explicit_import':True,'validation_run':True,'provenance':snapshot['provenance']})
    print(json.dumps({'started':incident['id'],'source':snapshot['provenance'],'profile':snapshot['profile']}),flush=True)
    await Continuation(store,NIMReasoner(),Path('../imports'),Path('data/patches')).run(incident['id'],request)
    receipt=Engine(store,None,NIMReasoner(),None).receipt(incident['id'])
    output=Path('data')/('portability-'+incident['id']+'.json');output.write_text(json.dumps(receipt,indent=2))
    result=receipt['incident'];print(json.dumps({'finished':incident['id'],'status':result['status'],'error':result.get('error'),'checks':result.get('verification'),'receipt':str(output)}),flush=True)
    return result['status']=='resolved'

async def main(store):
    imports=RepositoryImports(Path('../imports'))
    data=await asyncio.to_thread(imports.import_source,RepositorySource(kind='github',source='https://github.com/r1chardj0n3s/parse'))
    repo=Path(data['repository']);assessment=inspect_repository(repo);sandbox=Sandbox(repo,assessment['profile'],True)
    try:
        setup=await asyncio.to_thread(sandbox.prepare,assessment);healthy=await asyncio.to_thread(sandbox.run)
        Path('data/upstream-healthy-baseline.json').write_text(json.dumps({'provenance':data['provenance'],'dependency_setup':setup,'tests':healthy},indent=2))
        print(json.dumps({'upstream_healthy_exit':healthy['exit_code'],'cases':len(healthy['cases']),'output':healthy['output'][-1500:]}),flush=True)
        if healthy['exit_code']!=0:raise RuntimeError('Unmodified upstream suite is not green in the supported environment')
    finally:await asyncio.to_thread(sandbox.close)
    path=repo/'parse/__init__.py';text=path.read_text()
    if text.count('return float(string[:-1]) / 100.0')!=1:raise RuntimeError('Upstream differs; controlled injection needs review')
    path.write_text(text.replace('return float(string[:-1]) / 100.0','return float(string[:-1]) / 10.0'))
    git(['add','--','parse/__init__.py'],repo);git(['-c','user.name=CtrlZ Validation','-c','user.email=validation@localhost','commit','-m','Disclosed controlled percentage regression for validation'],repo)
    data['provenance']['controlled_regression']={'file':'parse/__init__.py','description':'Intentionally changed percentage conversion; not an upstream defect','original_upstream_suite_passed':True,'upstream_test_cases':len(healthy['cases'])}
    metadata=repo/'.git/ctrlz-import.json';original=json.loads(metadata.read_text());original.update(provenance=data['provenance'],commit=git(['rev-parse','HEAD'],repo));metadata.write_text(json.dumps(original))
    ts=imports.import_source(RepositorySource(kind='local',source=str(Path('../examples/invoice-typescript').resolve())))
    results=await asyncio.gather(repair(store,data,'Repair the percentage field conversion regression while preserving all existing upstream tests and other conversion behavior.'),repair(store,ts,'Fix invoice totals: decimal currency prices must sum as integer cents without floating point accumulation. Preserve the existing acceptance tests.'))
    Path('data/portability-proof-result.json').write_text(json.dumps({'passed':all(results),'results':results,'upstream':data['provenance'],'typescript_fixture':ts['provenance']},indent=2))
    if not all(results):raise RuntimeError('Live repair failed; inspect complete receipts')

if __name__=='__main__':
    store=Store(os.getenv('DATABASE_URL','sqlite:///./ctrlz.db'))
    try:asyncio.run(main(store))
    finally:store.engine.dispose()

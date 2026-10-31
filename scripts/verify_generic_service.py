"""Live NIM proof over real localhost HTTP, against an independent dispatch service.
Run from backend. Programmatic test-operator approval is explicitly recorded.
"""
import asyncio,json,os,secrets,subprocess,sys
from pathlib import Path
import httpx
from dotenv import load_dotenv
load_dotenv('../.env',override=True)
from ctrlz.models import Project
from ctrlz.store import Store
from ctrlz.engine import Engine
from ctrlz.reasoning import NIMReasoner
from ctrlz.runbooks import Runbooks
async def main():
    token=secrets.token_urlsafe(32);os.environ['DISPATCH_RECOVERY_TOKEN']=token
    env={k:v for k,v in os.environ.items() if not any(x in k for x in ['KEY','TOKEN','SECRET','PASSWORD'])}
    env['DISPATCH_RECOVERY_TOKEN']=token
    fixture=Path('../examples/dispatch-service').resolve()
    with Path('data/dispatch-service.log').open('w') as log:
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','app:app','--host','127.0.0.1','--port','18002'],cwd=fixture,env=env,stdout=log,stderr=log)
        store=Store(os.getenv('DATABASE_URL','sqlite:///./ctrlz.db'))
        try:
            async with httpx.AsyncClient() as client:
                for _ in range(80):
                    try:
                        if (await client.get('http://127.0.0.1:18002/health')).is_success:break
                    except httpx.HTTPError:pass
                    await asyncio.sleep(.1)
                else:raise RuntimeError('Fixture did not start')
                config=json.loads((fixture/'project.json').read_text());config.update(enabled=False)
                project=Project.model_validate(config);store.save_project(project.model_dump())
                engine=Engine(store,client,NIMReasoner(),Runbooks(Path('../runbooks'),Path('data/generic-proof-chroma')))
                adapter=engine.adapter({'project_id':project.id});health=await adapter.read('health')
                incident,_=store.create(project.id,'outage','service',{'health':health,'validation_fixture':True});store.record(incident['id'],'detect',{'health':health,'actual_http':True})
                print(json.dumps({'started':incident['id'],'adapter':project.adapter}),flush=True)
                await engine.run(incident['id']);result=store.get(incident['id'])
                if result['status']=='awaiting_approval':
                    store.record(incident['id'],'test_operator_approval',{'physical_human_click':False,'scope':'local dispatch fixture'})
                    await engine.approve(incident['id'],result['approval_hash'])
                result=store.get(incident['id']);receipt=engine.receipt(incident['id'])
                Path('data/generic-live-receipt.json').write_text(json.dumps(receipt,indent=2))
                print(json.dumps({'finished':incident['id'],'status':result['status'],'error':result.get('error'),'verification':result.get('verification')}),flush=True)
                if result['status']!='resolved':raise RuntimeError('Generic service did not verify')
        finally:
            proc.terminate();proc.wait(timeout=10);store.engine.dispose()
if __name__=='__main__':asyncio.run(main())

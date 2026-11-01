"""Dedicated local CtrlZ for hosted CampusPass deadline telemetry; never pushes/deploys."""
import argparse,io,json,os,subprocess,sys,zipfile,secrets,socket,time
from pathlib import Path
import httpx
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'backend/data/hosted-deadlines';API='http://127.0.0.1:18070';PROJECT='campuspass-hosted-deadlines'

def private(name,value):
    DATA.mkdir(parents=True,exist_ok=True);fd=os.open(DATA/name,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:json.dump(value,f,indent=2)
def call(c,method,path,**kw):
    r=c.request(method,path,**kw)
    if not r.is_success:raise RuntimeError(f'{method} {path}: HTTP {r.status_code}')
    return r.json()

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['serve','prepare','status','configure','pause','reset','recovery-project']);p.add_argument('--revision');p.add_argument('--public-origin');a=p.parse_args();DATA.mkdir(parents=True,exist_ok=True)
    lines=(ROOT/'backend/data/initial-credentials.txt').read_text().splitlines()
    if a.action=='serve':
        env={**os.environ,**{k:v for k,v in dotenv_values(ROOT/'.env').items() if v is not None}}
        env.update(DATA_DIR=str(DATA/'data'),DATABASE_URL='sqlite:///'+str(DATA/'ctrlz.db'),RUNBOOK_DIR=str(ROOT/'runbooks'),IMPORT_ROOT=str(DATA/'imports'),CTRLZ_CORS_ORIGINS='http://localhost:18072,http://127.0.0.1:18072',CTRLZ_ADMIN_1_EMAIL=lines[0].split(': ',1)[1],CTRLZ_ADMIN_1_PASSWORD=lines[1].split(': ',1)[1],CTRLZ_ALLOW_REGISTRATION='false',CTRLZ_CODE_EXECUTION_ENABLED='true')
        for port in [18070,18072]:
            for attempt in range(40):
                with socket.socket() as probe:
                    try:probe.bind(('127.0.0.1',port));break
                    except OSError:
                        with socket.socket() as listener:
                            if listener.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('Demo port has a running service: '+str(port))
                        time.sleep(2)
            else:raise RuntimeError('Demo port unavailable')
        subprocess.run([sys.executable,str(ROOT/'scripts/dev.py'),'--api-port','18070','--web-port','18072'],cwd=ROOT,env=env,check=True);return
    if a.action in {'pause','reset'}:
        token=dotenv_values(ROOT/'.env').get('CAMPUSPASS_HOSTED_RECOVERY_TOKEN')
        if not token:raise RuntimeError('Existing hosted recovery token missing')
        with httpx.Client(timeout=60,follow_redirects=False) as c:
            r=c.post('https://campuspass-api-2jx6.onrender.com/demo/fault',headers={'X-Recovery-Token':token},json={'fault':'worker_paused' if a.action=='pause' else 'none'})
            if not r.is_success:raise RuntimeError('Hosted fault control rejected: HTTP '+str(r.status_code))
            print('Controlled fault state:',r.json()['fault'])
        return
    with httpx.Client(base_url=API,timeout=180) as c:
        auth=DATA/'session.json'
        if auth.exists():session=json.loads(auth.read_text())
        else:
            session=call(c,'POST','/auth/login',json={'email':lines[0].split(': ',1)[1],'password':lines[1].split(': ',1)[1]});private('session.json',{'token':session['token']})
        c.headers['Authorization']='Bearer '+session['token']
        if a.action=='recovery-project':
            project={'id':'campuspass-hosted-recovery','name':'CampusPass hosted · explicitly authorized recovery','adapter':'campuspass-v1','base_url':'https://campuspass-api-2jx6.onrender.com','token_env':'CAMPUSPASS_HOSTED_RECOVERY_TOKEN','enabled':True,'automatic_detection':False,'demo_enabled':True,'timeout_seconds':15,'latency_ms':15000,'contract':{'allowed':['restore_checkout','resume_worker','retry_order'],'approval_required':['resume_worker'],'invariants':['no_duplicate_entitlements','no_destructive_operations']}}
            call(c,'POST','/projects',json=project);print('Recovery target registered with automatic HTTP polling disabled. Only explicit correlated incident handoff invokes diagnosis.');return
        if a.action=='prepare':
            # A new audit attempt retains prior proposals and incident history.
            project={'id':PROJECT,'name':'Hosted CampusPass · event-driven ticket fulfillment','project_type':'repository-deployment','adapter':'runtime-v1','enabled':True,'repository_monitoring':{'github_url':'https://github.com/AtharvMitt/CampusPass','deployments':[{'id':'render','platform':'docker','service_id':'campuspass-api','environment':'controlled-demo','application_url':'https://campuspass-api-2jx6.onrender.com','sources':[{'id':'lifecycle','connector':'generic-events'},{'id':'deadline-state','connector':'generic-events'}]}]}}
            call(c,'POST','/projects',json=project);setup={}
            for source in ['lifecycle','deadline-state']:setup[source]=call(c,'POST',f'/projects/{PROJECT}/runtime/sources/provision',json={'deployment_id':'render','source_id':source})
            private('setup.json',setup);private('gateway-paths.json',[v['receiver_path'] for v in setup.values()])
            raw=io.BytesIO();campus=ROOT.parent/'CampusPass'
            with zipfile.ZipFile(raw,'w') as z:
                for f in (campus/'backend/campuspass').glob('*.py'):z.writestr('backend/campuspass/'+f.name,f.read_text())
                for f in (campus/'backend/tests').glob('test_*.py'):z.writestr('backend/tests/'+f.name,f.read_text())
                z.writestr('backend/pyproject.toml',(campus/'backend/pyproject.toml').read_text())
            audit=call(c,'POST',f'/projects/{PROJECT}/workflow-audits/snapshot?deployment_id=render&source_id=lifecycle',content=raw.getvalue());private('audit.json',audit)
            print('Live AI audit requested for the actual local CampusPass source snapshot. Review in http://localhost:18072/#projects; source publication is not yet verified.')
        else:
            data=call(c,'GET',f'/projects/{PROJECT}/workflow-audits');private('audit-state.json',data)
            if a.action=='status':
                print(json.dumps({'audits':[{'id':x['id'],'status':x['status'],'error':x.get('detail')} for x in data['audits']],'proposals':[{'id':x['id'],'status':x['status'],'name':x['rule']['name'],'technique':x['rule']['technique']} for x in data['proposals']]},indent=2));return
            proposal=next((x for x in data['proposals'] if x.get('approval') and x['rule']['technique']=='instrumentation' and x.get('verification',{}).get('passed')),None)
            if not proposal:raise RuntimeError('Review/approve and generate a verified ticket instrumentation patch first; no automatic approval')
            if not a.revision or not __import__('re').fullmatch('[a-f0-9]{40}',a.revision):raise RuntimeError('Actual deployed full Git SHA required')
            from urllib.parse import urlsplit
            origin=urlsplit(a.public_origin or '')
            if origin.scheme!='https' or origin.path not in {'','/'} or origin.username or origin.query:raise RuntimeError('Public HTTPS origin required')
            project=next(x for x in call(c,'GET','/projects') if x['id']==PROJECT);project['repository_monitoring']['deployments'][0]['commit_sha']=a.revision;call(c,'POST','/projects',json=project)
            call(c,'POST','/workflow-proposals/'+proposal['id']+'/activate',json={'approval_hash':proposal['approval']['hash'],'revision':a.revision,'artifact_digest':proposal['patch']['instrumentation_digest'],'reconciliation_source_id':'deadline-state','check_mode':'deadline_targeted'})
            setup=json.loads((DATA/'setup.json').read_text());values={'CTRLZ_WORKFLOW_ENABLED':'true','CTRLZ_PROPOSAL_ID':proposal['id'],'CTRLZ_WORKFLOW_ID':proposal['rule']['id'],'CTRLZ_ARTIFACT_DIGEST':proposal['patch']['instrumentation_digest'],'CTRLZ_DEPLOYED_REVISION':a.revision}
            for prefix,source in [('APP','lifecycle'),('STATE','deadline-state')]:
                values['CTRLZ_'+prefix+'_RECEIVER']=a.public_origin.rstrip('/')+setup[source]['receiver_path'];values['CTRLZ_'+prefix+'_SOURCE_TOKEN']=Path(setup[source]['credential_file']).read_text().strip()
            if 'user_id' in proposal['rule']['allowed_fields']:values['CTRLZ_USER_PSEUDONYM_KEY']=secrets.token_hex(32)
            # Private Render settings file, never echoed or committed.
            fd=os.open(DATA/'render-workflow.env',os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as f:
                for k,v in values.items():f.write(k+'='+v+'\n')
            print('Activation bound to deployed SHA. Private Render settings saved to backend/data/hosted-deadlines/render-workflow.env; never share or commit this file.')

if __name__=='__main__':main()

"""Ten real synthetic accounts/checkouts; never approves CtrlZ recovery.
Credentials and detailed state stay in a private local run file. No cloud deployment.
"""
import argparse,json,os,secrets,subprocess,sys,time,uuid
from pathlib import Path
import httpx
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'backend/data/ten-purchase-demo'
HOST='https://campuspass-api-2jx6.onrender.com'

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:json.dump(value,f,indent=2)

def call(c,method,path,**kwargs):
    r=c.request(method,path,**kwargs)
    if not r.is_success:raise RuntimeError(f'{method} {path}: HTTP {r.status_code}; inspect application/incident before repeating')
    return r.json()

def serve():
    campus=ROOT.parent/'CampusPass'
    if not campus.exists():raise RuntimeError('Expected sibling CampusPass checkout')
    DATA.mkdir(parents=True,exist_ok=True,mode=0o700)
    env={**os.environ,**{k:v for k,v in dotenv_values(ROOT/'.env').items() if v is not None}}
    tokenfile=DATA/'local-token.json'
    if not tokenfile.exists():save(tokenfile,{'token':secrets.token_urlsafe(32)})
    token=json.loads(tokenfile.read_text())['token']
    lines=(ROOT/'backend/data/initial-credentials.txt').read_text().splitlines()
    env.update(CTRLZ_ADMIN_1_EMAIL=lines[0].split(': ',1)[1],CTRLZ_ADMIN_1_PASSWORD=lines[1].split(': ',1)[1],
        DATABASE_URL='sqlite:///'+str(DATA/'ctrlz.db'),DATA_DIR=str(DATA/'data'),IMPORT_ROOT=str(DATA/'imports'),
        RUNBOOK_DIR=str(ROOT/'runbooks'),CTRLZ_CORS_ORIGINS='http://localhost:18092,http://127.0.0.1:18092',
        CTRLZ_DEMO_CONTROLS_ENABLED='true',TEN_DEMO_RECOVERY_TOKEN=token,MONITOR_INTERVAL='2')
    appenv={**env,'DATABASE_URL':'sqlite:///'+str(DATA/'campuspass.db'),'RECOVERY_TOKEN':token,'DEMO_MODE':'true',
        'CAMPUSPASS_REQUIRE_LOGIN':'true','CTRLZ_WORKFLOW_ENABLED':'false'}
    # This isolated rehearsal uses the existing HTTP adapter; hosted telemetry is a separate path.
    commands=[([str(campus/'backend/.venv/bin/python'),'-m','uvicorn','campuspass.main:create_app','--factory','--host','127.0.0.1','--port','18091'],campus/'backend',appenv),
      ([sys.executable,str(ROOT/'scripts/dev.py'),'--api-port','18090','--web-port','18092'],ROOT,env),
      (['npm','run','dev','--','--port','18094','--strictPort'],campus/'frontend',{**appenv,'CAMPUSPASS_PROXY_TARGET':'http://127.0.0.1:18091'})]
    import socket
    for port in [18090,18091,18092,18094]:
        for attempt in range(45):
            with socket.socket() as probe:
                try:probe.bind(('127.0.0.1',port));break
                except OSError:
                    with socket.socket() as listener:
                        if listener.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('Demo port already has a running service: '+str(port))
                    time.sleep(2)
        else:raise RuntimeError('Demo port not available: '+str(port))
    processes=[]
    try:
        for cmd,cwd,e in commands:processes.append(subprocess.Popen(cmd,cwd=cwd,env=e))
        while all(p.poll() is None for p in processes):time.sleep(.5)
    except KeyboardInterrupt:pass
    finally:
        for p in processes:
            if p.poll() is None:p.terminate()
        for p in processes:
            try:p.wait(timeout=15)
            except subprocess.TimeoutExpired:p.kill()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['serve','setup','start','status','verify','repeat','scenario-c','reset'])
    p.add_argument('--hosted',action='store_true',help='Explicitly target the controlled Render demo (mutating actions require operator intent)')
    p.add_argument('--ctrlz',help='Defaults to local rehearsal 18090 or hosted dashboard API 18070')
    a=p.parse_args()
    a.ctrlz=a.ctrlz or ('http://127.0.0.1:18070' if a.hosted else 'http://127.0.0.1:18090')
    if a.action=='serve':serve();return
    target=HOST if a.hosted else 'http://127.0.0.1:18091'
    runfile=DATA/('hosted-run.json' if a.hosted else 'local-run.json')
    config=dotenv_values(ROOT/'.env')
    token=config.get('CAMPUSPASS_HOSTED_RECOVERY_TOKEN') if a.hosted else json.loads((DATA/'local-token.json').read_text())['token']
    if not token:raise RuntimeError('Required server-side recovery credential missing')
    with httpx.Client(base_url=target,headers={'X-Recovery-Token':token},timeout=60,follow_redirects=False) as app:
        def ctrlz():
            c=httpx.Client(base_url=a.ctrlz,timeout=90,follow_redirects=False)
            lines=(ROOT/'backend/data/initial-credentials.txt').read_text().splitlines()
            cache=DATA/('ctrlz-session-'+str(__import__('hashlib').sha256(a.ctrlz.encode()).hexdigest()[:8])+'.json')
            session=json.loads(cache.read_text()) if cache.exists() else call(c,'POST','/auth/login',json={'email':lines[0].split(': ',1)[1],'password':lines[1].split(': ',1)[1]})
            save(cache,{'token':session['token']});c.headers['Authorization']='Bearer '+session['token'];return c
        if a.action=='setup':
            c=ctrlz()
            try:
                project={'id':'campuspass-ten-local','name':'CampusPass · ten-customer local rehearsal','base_url':target,'adapter':'campuspass-v1','token_env':'TEN_DEMO_RECOVERY_TOKEN','enabled':True,'demo_enabled':True,'timeout_seconds':15,'latency_ms':15000,'contract':{'allowed':['restore_checkout','resume_worker','retry_order'],'approval_required':['resume_worker','retry_order'],'invariants':['no_duplicate_entitlements','no_destructive_operations']}}
                if a.hosted:
                    project=next((x for x in call(c,'GET','/projects') if x['id']=='campuspass-hosted-recovery'),None)
                    if not project or project.get('base_url')!=HOST or project.get('adapter')!='campuspass-v1':raise RuntimeError('Existing hosted recovery project missing or target mismatch; follow hosted guide first')
                    project['contract']['approval_required']=list(dict.fromkeys(project['contract']['approval_required']+['retry_order']))
                    project['automatic_detection']=False
                call(c,'POST','/projects',json=project)
            finally:c.close()
            print('CampusPass recovery contract configured. retry_order requires exact-candidate human approval. Hosted B retains event-driven detection.');return
        if a.action=='scenario-c':
            if a.hosted:
                with_retry_client=ctrlz()
                try:
                    project=next(x for x in call(with_retry_client,'GET','/projects') if x['id']=='campuspass-hosted-recovery')
                    if project.get('base_url')!=HOST:raise RuntimeError('Recovery target mismatch')
                    project['automatic_detection']=True
                    call(with_retry_client,'POST','/projects',json=project)
                finally:with_retry_client.close()
            call(app,'POST','/demo/fault',json={'fault':'checkout_outage'})
            print('Real checkout outage injected. Open Demo Lab/Incidents; no recovery approved by this script.');return
        if a.action=='reset':
            call(app,'POST','/demo/fault',json={'fault':'none'})
            if runfile.exists():
                run=json.loads(runfile.read_text());call(app,'POST','/demo/target-fault/cancel',json=run['fault'])
            if a.hosted:
                c=ctrlz()
                try:
                    project=next(x for x in call(c,'GET','/projects') if x['id']=='campuspass-hosted-recovery')
                    project['automatic_detection']=False
                    call(c,'POST','/projects',json=project)
                finally:c.close()
            print('Global fault cleared; any armed target cancelled; orders, failed jobs and history retained. Hosted operational polling disabled again.');return
        if a.hosted and a.action in {'start','repeat'}:
            c=ctrlz()
            try:
                projects=call(c,'GET','/projects')
                recovery=next(x for x in projects if x['id']=='campuspass-hosted-recovery')
                if recovery.get('automatic_detection',True) or 'retry_order' not in recovery['contract']['approval_required']:
                    raise RuntimeError('Run setup --hosted first: B must retain polling disabled and retry approval required')
                source=next(x for x in projects if x['id']=='campuspass-hosted-deadlines')
                if not source['enabled']:raise RuntimeError('Hosted event-driven project is disabled')
                proposals=call(c,'GET','/projects/campuspass-hosted-deadlines/workflow-audits')['proposals']
                p=next(x for x in proposals if x['id']=='wf-32cc4935463d4865ab7f7ff4')
                activation=p.get('activation') or {}
                if p['status']!='monitoring_active' or not activation.get('primary_event_seen') or time.time()-(activation.get('last_event') or 0)>120:
                    raise RuntimeError('Recent lifecycle telemetry not verified. Make one healthy baseline purchase through Vercel after updating Render settings')
                if activation.get('check_mode')!='deadline_targeted' or activation.get('reconciliation_source_id')!='deadline-state':
                    raise RuntimeError('Approved independent deadline checker is not configured')
                sys.path.insert(0,str(ROOT/'backend'))
                from ctrlz.render_readonly import RenderReadOnly
                with httpx.Client() as provider:
                    reader=RenderReadOnly(provider,config.get('RENDER_API_KEY'));metadata=reader.deployment(reader.service(HOST))
                if metadata.get('commit')!=activation.get('revision'):raise RuntimeError('Actual Render revision differs from approved monitoring')
            finally:c.close()
        if a.action=='start':
            if runfile.exists():raise RuntimeError('Existing run retained. Use repeat to reuse its ten accounts, or status/verify; never overwrite history')
            run=call(app,'POST','/demo/ten-customers');run['url']=target;run['orders']=[]
            save(runfile,run)
        else:
            run=json.loads(runfile.read_text())
            if run['url']!=target:raise RuntimeError('Run target mismatch')
        if a.action in {'start','repeat'}:
            if a.action=='repeat':
                old=[call(app,'GET','/orders/'+o) for o in run.get('orders',[])]
                if len(old)!=10 or not all(v['job']=='done' and len(v['tickets'])==1 for v in old):raise RuntimeError('Finish recovery before repeating')
                save(DATA/('history-'+str(uuid.uuid4())+'.json'),run)
            run.update(request_ids=[str(uuid.uuid4()) for _ in range(10)],orders=[])
            run['fault']={'request_id':run['request_ids'][4],'activation_id':str(uuid.uuid4())}
            save(runfile,run)
            call(app,'POST','/demo/target-fault',json=run['fault'])
            # Sequential requests, ten distinct accounts. Auth sessions remain private.
            for user,key in zip(run['customers'],run['request_ids']):
                login=call(app,'POST','/auth/login',json={'email':user['email'],'password':user['password']})
                r=call(app,'POST','/checkout',headers={'Authorization':'Bearer '+login['token']},json={'event_id':'agentathon','email':user['email'],'request_id':key})
                run['orders'].append(r['id']);save(runfile,run)
            for _ in range(60):
                views=[call(app,'GET','/orders/'+o) for o in run['orders']]
                if all(v['job'] in {'done','failed'} for v in views):break
                time.sleep(.5)
            assert len(views)==10 and sum(v['job']=='done' for v in views)==9
            assert views[4]['job']=='failed' and not views[4]['tickets'] and all(v['payment']=='paid' for v in views)
            run['before']=views;save(runfile,run)
            print('10 real synthetic accounts, 10 sequential simulated purchases: 9 completed, customer 5 failed.')
            print('Affected order:',run['orders'][4]);print('Review customer 5 credentials privately in',runfile)
        views=[call(app,'GET','/orders/'+o) for o in run['orders']]
        if a.action=='verify':
            assert len(views)==10 and all(v['payment']=='paid' and v['job']=='done' and len(v['tickets'])==1 and v['tickets'][0]['valid'] for v in views),'Recovery incomplete; approve the pending targeted retry in CtrlZ'
            assert [v for i,v in enumerate(views) if i!=4]==[v for i,v in enumerate(run['before']) if i!=4],'Unrelated order changed'
            assert [v['payment_reference'] for v in views]==[v['payment_reference'] for v in run['before']]
            assert all(call(app,'GET','/tickets/'+v['tickets'][0]['id']+'/verify')['valid'] for v in views)
            # Repeat only AFTER human-approved recovery has already completed.
            payload={'request_id':str(uuid.uuid4()),'expected_revision':call(app,'GET','/diagnostics')['revision'],'order_id':run['orders'][4]}
            first=call(app,'POST','/operations/retry_order',json=payload);second=call(app,'POST','/operations/retry_order',json=payload)
            assert first==second and first['created'] is False
            assert call(app,'GET','/orders/'+run['orders'][4])==views[4]
            run['verification']={'passed':True,'orders':10,'valid_unique_tickets':10,'unchanged_payments':True,'other_nine_unchanged':True,'idempotency':True};save(runfile,run)
            print(json.dumps(run['verification'],indent=2))
        else:
            print(json.dumps({'orders':len(views),'completed':sum(v['job']=='done' for v in views),'failed':sum(v['job']=='failed' for v in views),'tickets':sum(len(v['tickets']) for v in views),'affected_order':run['orders'][4],'website_healthy':call(app,'GET','/health')['checkout_available']},indent=2))

if __name__=='__main__':main()

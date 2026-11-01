"""Isolated CampusPass source-monitoring demo; primary CampusPass is untouched."""
import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
REVISION='f4b3e817e6c80075c91f23f6c2a6cbb3f4e6d0a1'
DATA=ROOT/'backend/data/runtime-demo/campuspass-source'
PROJECT_ID='campuspass-source-runtime'


def private_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:json.dump(value,f)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['serve','register','trigger','status','export'])
    args=parser.parse_args()
    campus=(ROOT.parent/'CampusPass').resolve();DATA.mkdir(parents=True,exist_ok=True)
    if args.action=='serve':
        # The running Python source must match the exact deployed revision.
        subprocess.run(['git','diff','--quiet',REVISION,'--','backend/campuspass/*.py'],cwd=campus,check=True)
        env=dotenv_values(campus/'.env')
        os.environ['RECOVERY_TOKEN']=env['RECOVERY_TOKEN'];os.environ['DEMO_MODE']='true'
        os.environ['DATABASE_URL']='sqlite:///'+str(DATA/'campuspass.db')
        sys.path.insert(0,str(campus/'backend'))
        import uvicorn
        uvicorn.run('campuspass.main:create_app',factory=True,host='127.0.0.1',port=18031,access_log=False)
        return
    if args.action=='trigger':
        env=dotenv_values(campus/'.env')
        with httpx.Client(base_url='http://127.0.0.1:18031',headers={'X-Recovery-Token':env['RECOVERY_TOKEN']},timeout=10) as c:
            r=c.post('/demo/fault',json={'fault':'worker_defect'});r.raise_for_status()
            r=c.post('/checkout',json={'event_id':'agentathon','email':'isolated-runtime-demo@example.com','request_id':str(uuid.uuid4())});r.raise_for_status()
            print('Created a real simulated paid order in the isolated database; existing worker_defect will execute. No primary service was changed.')
        return
    session=DATA/'session.json'
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=20,follow_redirects=False) as c:
        def call(method,path,**kw):
            r=c.request(method,path,**kw)
            if not r.is_success:raise RuntimeError(f'{method} {path}: HTTP {r.status_code}')
            return r.json()
        if args.action=='register':
            lines=(ROOT/'backend/data/initial-credentials.txt').read_text().splitlines()
            login=call('POST','/auth/login',json={'email':lines[0].split(': ',1)[1],'password':lines[1].split(': ',1)[1]})
            private_json(session,{'token':login['token']})
        c.headers['Authorization']='Bearer '+json.loads(session.read_text())['token']
        if args.action=='register':
            project={'id':PROJECT_ID,'name':'CampusPass · repository and worker runtime','project_type':'repository-deployment','adapter':'runtime-v1','enabled':True,'repository_monitoring':{'github_url':'https://github.com/AtharvMitt/CampusPass','deployments':[{'id':'isolated-staging','platform':'local','service_id':'campuspass-worker','environment':'staging','application_url':'http://127.0.0.1:18031','deployment_ref':'campuspass-isolated-worker','commit_sha':REVISION,'source_paths':['backend/campuspass/ticket_reference.py','backend/campuspass/worker.py'],'sources':[{'id':'worker-errors','connector':'generic-events'}]}]}}
            existing=next((p for p in call('GET','/projects') if p['id']==PROJECT_ID),None)
            if existing and existing.get('project_type')!='repository-deployment':parser.error('Project ID belongs to another integration')
            call('POST','/projects',json=project)
            setup=call('POST',f'/projects/{PROJECT_ID}/runtime/sources/provision',json={'deployment_id':'isolated-staging','source_id':'worker-errors'})
            private_json(DATA/'setup.json',setup)
            print('CampusPass repository registered at '+REVISION+' with isolated staging worker telemetry.')
            print('Receiver: http://127.0.0.1:8000'+setup['receiver_path'])
            print('Private collector credential file: '+setup['credential_file'])
            print('Source hints are operator-configured. No stack frames or exact failing line are invented.')
        else:
            for i in call('GET','/incidents'):
                if i['project_id']!=PROJECT_ID:continue
                if args.action=='export':
                    receipt=call('GET',f"/incidents/{i['id']}/receipt")
                    (DATA/(i['id']+'.json')).write_text(json.dumps(receipt,indent=2))
                    r=c.get(f"/incidents/{i['id']}/brief");r.raise_for_status();(DATA/(i['id']+'.md')).write_text(r.text)
                print(json.dumps({k:i.get(k) for k in ['id','status','diagnosis','source_evidence','runtime_recommendations','recommendation_review','error']},indent=2))
                print('Dashboard: http://localhost:5173/#incident/'+i['id'])


if __name__=='__main__':main()

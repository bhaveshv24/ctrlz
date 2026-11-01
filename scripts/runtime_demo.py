"""Prepare and inspect the disclosed local runtime-monitoring demonstration.

Never approves recommendations, repairs code, or creates incidents directly.
"""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import httpx

ROOT=Path(__file__).resolve().parents[1]
DEPLOYED_REVISION='08f66e7c565ea42d2dd26e992cb5681326e74a9e'


def private_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:json.dump(value,f)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['register','status','export'])
    parser.add_argument('--api',default='http://127.0.0.1:8000')
    parser.add_argument('--project-id',default='runtime-reservation')
    args=parser.parse_args()
    origin=urlsplit(args.api)
    if origin.scheme!='http' or origin.hostname not in {'127.0.0.1','localhost'} or origin.username or origin.password or origin.path not in {'','/'} or origin.query or origin.fragment:
        parser.error('Demo login is restricted to a loopback HTTP API')
    data=ROOT/'backend/data/runtime-demo'/args.project_id
    # Prevent script arguments from becoming arbitrary file paths.
    import re
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,40}',args.project_id):parser.error('Invalid project ID')
    session=data/'session.json'
    with httpx.Client(base_url=args.api,timeout=20,follow_redirects=False) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            if not response.is_success:raise RuntimeError(f'{method} {path}: HTTP {response.status_code}; inspect local application state')
            return response.json()
        if args.action=='register':
            credentials=(ROOT/'backend/data/initial-credentials.txt').read_text().splitlines()
            login=call('POST','/auth/login',json={'email':credentials[0].split(': ',1)[1],'password':credentials[1].split(': ',1)[1]})
            private_json(session,{'token':login['token']})
        if not session.exists():parser.error('Run register first')
        client.headers['Authorization']='Bearer '+json.loads(session.read_text())['token']
        if args.action=='register':
            project={'id':args.project_id,'name':'Reservation runtime · controlled local demonstration','project_type':'repository-deployment','adapter':'runtime-v1','enabled':True,'repository_monitoring':{'github_url':'https://github.com/bhaveshv24/ctrlz','deployments':[{'id':'local-staging','platform':'local','service_id':'reservation-demo','environment':'staging','application_url':'http://127.0.0.1:18021','deployment_ref':'reservation-local-v1','commit_sha':DEPLOYED_REVISION,'sources':[{'id':'application-log','connector':'generic-events'}]}]}}
            existing=next((p for p in call('GET','/projects') if p['id']==args.project_id),None)
            if existing and (existing.get('project_type')!='repository-deployment' or existing.get('repository_monitoring',{}).get('github_url')!=project['repository_monitoring']['github_url']):
                parser.error('Existing project ID belongs to another integration; choose a new ID')
            call('POST','/projects',json=project)
            setup=call('POST',f'/projects/{args.project_id}/runtime/sources/provision',json={'deployment_id':'local-staging','source_id':'application-log'})
            private_json(data/'setup.json',{'project_id':args.project_id,'revision':DEPLOYED_REVISION,**setup})
            print('Registered repository and local staging deployment. No telemetry or recovery is fabricated.')
            print('Application:')
            print(f'backend/.venv/bin/python examples/runtime-monitoring/app.py --revision {DEPLOYED_REVISION} --data-dir backend/data/runtime-demo/{args.project_id}')
            print('Collector (separate terminal; credential stays in its private file):')
            print(f"python scripts/runtime_log_collector.py --file backend/data/runtime-demo/{args.project_id}/application.jsonl --cursor backend/data/runtime-demo/{args.project_id}/collector-cursor.json --endpoint {args.api}{setup['receiver_path']} --token-file {setup['credential_file']}")
            print('Healthy request: http://127.0.0.1:18021/reserve | deliberate real failure: http://127.0.0.1:18021/fail')
        else:
            incidents=[i for i in call('GET','/incidents') if i['project_id']==args.project_id]
            for incident in incidents:
                if args.action=='export':
                    receipt=call('GET',f"/incidents/{incident['id']}/receipt")
                    (data/(incident['id']+'.json')).write_text(json.dumps(receipt,indent=2))
                    response=client.get(f"/incidents/{incident['id']}/brief");response.raise_for_status();(data/(incident['id']+'.md')).write_text(response.text)
                print(json.dumps({'id':incident['id'],'status':incident['status'],'model':incident.get('model'),'source_state':incident.get('source_evidence',{}).get('state'),'source_revision':incident.get('source_evidence',{}).get('commit_sha'),'diagnosis':incident.get('diagnosis'),'error':incident.get('error'),'recommendations':incident.get('runtime_recommendations'),'verification':incident.get('verification')},indent=2))
                print('Dashboard: http://localhost:5173/#incident/'+incident['id'])
            if not incidents:print('No runtime incident yet. Trigger /fail and run the collector; do not create an incident manually.')


if __name__=='__main__':main()

"""Review and bind an unchanged deployed observer. Never approves or deploys."""
import argparse,json,sys
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from dotenv import dotenv_values
from ten_purchase_demo import ROOT,HOST,save,call
sys.path.insert(0,str(ROOT/'backend'))
from ctrlz.render_readonly import RenderReadOnly
DATA=ROOT/'backend/data/hosted-deadlines'
PROJECT='campuspass-hosted-deadlines'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['review','configure','status']);p.add_argument('--public-origin');a=p.parse_args()
    env=dotenv_values(ROOT/'.env')
    with httpx.Client(timeout=120,follow_redirects=False) as provider:
        reader=RenderReadOnly(provider,env.get('RENDER_API_KEY'));service=reader.service(HOST);deployment=reader.deployment(service)
        revision=deployment.get('commit')
        if not revision:raise RuntimeError('No independently observed live Render commit')
    session=json.loads((DATA/'session.json').read_text())
    with httpx.Client(base_url='http://127.0.0.1:18070',headers={'Authorization':'Bearer '+session['token']},timeout=180,follow_redirects=False) as c:
        data=call(c,'GET','/projects/'+PROJECT+'/workflow-audits')
        proposal=next(x for x in data['proposals'] if x['id']=='wf-32cc4935463d4865ab7f7ff4')
        if a.action=='review':
            if (proposal.get('revision_review') or {}).get('revision')==revision:print('Revision review already exists; no approval reset.');return
            result=call(c,'POST','/workflow-proposals/'+proposal['id']+'/revision-review',json={'revision':revision})
            print('Observed Render commit:',revision);print('Unchanged observer and model mappings verified. Review and approve monitoring in http://localhost:18072/#projects. No approval or deployment performed.');return
        if a.action=='status':
            print(json.dumps({'service':service['id'],'render_revision':revision,'proposal_status':proposal['status'],'approved':bool(proposal.get('approval')),'bound_revision':(proposal.get('activation') or {}).get('revision'),'monitoring':proposal.get('monitoring')},indent=2));return
        origin=urlsplit(a.public_origin or '')
        if origin.scheme!='https' or not origin.hostname or origin.path not in {'','/'} or origin.username or origin.password or origin.query or origin.fragment:raise RuntimeError('Public HTTPS tunnel origin required')
        if not proposal.get('approval') or (proposal.get('revision_review') or {}).get('revision')!=revision:raise RuntimeError('Approve the actual deployed revision review first')
        call(c,'POST','/workflow-proposals/'+proposal['id']+'/activate',json={'approval_hash':proposal['approval']['hash'],'revision':revision,'artifact_digest':proposal['patch']['instrumentation_digest'],'reconciliation_source_id':'deadline-state','check_mode':'deadline_targeted'})
        setup=json.loads((DATA/'setup.json').read_text());values={k:v for k,v in dotenv_values(DATA/'render-workflow.env').items() if v is not None}
        values.update(CTRLZ_WORKFLOW_ENABLED='true',CTRLZ_DEPLOYED_REVISION=revision,CTRLZ_PROPOSAL_ID=proposal['id'],CTRLZ_WORKFLOW_ID=proposal['rule']['id'],CTRLZ_ARTIFACT_DIGEST=proposal['patch']['instrumentation_digest'])
        for prefix,source in [('APP','lifecycle'),('STATE','deadline-state')]:
            values['CTRLZ_'+prefix+'_RECEIVER']=a.public_origin.rstrip('/')+setup[source]['receiver_path']
            values['CTRLZ_'+prefix+'_SOURCE_TOKEN']=Path(setup[source]['credential_file']).read_text().strip()
        import os
        fd=os.open(DATA/'render-workflow.env',os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as f:
            for k,v in values.items():f.write(k+'='+v+'\n')
        print('Revision approved and bound; existing credentials/pseudonym key preserved. Copy private backend/data/hosted-deadlines/render-workflow.env into Render settings and redeploy the same commit. Monitoring remains unverified until matching telemetry arrives.')
if __name__=='__main__':main()

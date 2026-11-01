"""Read actual CampusPass worker failure records into a selected JSONL log.

No source patches, fault resets, order creation or incident creation. IDs are
stable hashes of observed job/attempt/error records; original failure time and
stack frames are unknown. The output explicitly uses observation timestamps.
"""
import argparse
import hashlib
import hmac
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from dotenv import dotenv_values


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:18031')
    parser.add_argument('--env-file',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--state',required=True)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    u=urlsplit(args.url)
    if u.scheme!='http' or u.hostname not in {'127.0.0.1','localhost'} or u.username or u.password or u.query or u.fragment or u.path not in {'','/'}:parser.error('This CampusPass demonstration observer uses loopback only')
    if not re.fullmatch(r'[0-9a-f]{40}',args.revision):parser.error('Exact deployed revision required')
    token=dotenv_values(args.env_file).get('RECOVERY_TOKEN')
    if not token:parser.error('Recovery token missing; never printed')
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.touch(exist_ok=True)
    state=Path(args.state)
    seen=set(json.loads(state.read_text())) if state.exists() else set()
    with httpx.Client(base_url=args.url,headers={'X-Recovery-Token':token},timeout=10,follow_redirects=False) as client:
        while True:
            response=client.get('/diagnostics');response.raise_for_status()
            for job in response.json().get('logs',[]):
                if job.get('status')!='failed' or not job.get('error'):continue
                identity=json.dumps({k:job.get(k) for k in ['job_id','attempts','error']},sort_keys=True)
                event_id=hmac.new(token.encode(),identity.encode(),hashlib.sha256).hexdigest()
                if event_id in seen:continue
                error=re.sub(r'[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}','[order-reference-redacted]',job['error'])
                event={'event_id':event_id,'timestamp':time.time(),'timestamp_kind':'observed','severity':'error','error_type':error.split(':',1)[0],'message':error,'frames':[],'commit_sha':args.revision,'deployment_ref':'campuspass-isolated-worker','evidence_ref':'CampusPass /diagnostics failed-job record; original failure timestamp and stack frames unavailable'}
                with output.open('a') as f:f.write(json.dumps(event)+'\n')
                seen.add(event_id)
                state.parent.mkdir(parents=True,exist_ok=True);state.write_text(json.dumps(sorted(seen)[-1000:]))
                print('Observed actual failed worker record; wrote sanitized telemetry with unknown stack and observation timestamp.',flush=True)
            if args.once:break
            time.sleep(2)


if __name__=='__main__':main()

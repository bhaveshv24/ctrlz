"""Controlled runtime exception; application log is observed by a separate collector.

Loads only the existing, pinned reservation fixture from this CtrlZ checkout.
No CampusPass state or Scenario A repair machinery is used or changed.
"""
import argparse
import importlib.util
import json
import subprocess
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--data-dir',required=True)
    parser.add_argument('--port',type=int,default=18021)
    args=parser.parse_args()
    if len(args.revision)!=40 or any(c not in '0123456789abcdef' for c in args.revision):parser.error('Full deployed SHA required')
    repo=Path(__file__).resolve().parents[2]
    directory=Path(args.data_dir).resolve();directory.mkdir(parents=True,exist_ok=True)
    relative='examples/reservation-python/reservation.py'
    source=subprocess.run(['git','show',args.revision+':'+relative],cwd=repo,capture_output=True,check=True).stdout
    deployed=directory/'deployed-source'/relative;deployed.parent.mkdir(parents=True,exist_ok=True);deployed.write_bytes(source)
    spec=importlib.util.spec_from_file_location('pinned_reservation_demo',deployed)
    reservation=importlib.util.module_from_spec(spec);spec.loader.exec_module(reservation)
    log=directory/'application.jsonl'
    log.touch(exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_args):pass
        def do_GET(self):
            request_id=str(uuid.uuid4())
            if self.path not in {'/reserve','/fail'}:
                self.send_response(404);self.end_headers();return
            try:
                # /fail deliberately models an invalid configuration/input reaching
                # the real deployed function. The underlying exception actually occurs.
                requested='three' if self.path=='/fail' else 3
                result=reservation.can_reserve(5,requested)
                status,payload=200,{'can_reserve':result,'request_id':request_id}
            except Exception as exc:
                status,payload=500,{'error':'Controlled runtime demonstration; inspect CtrlZ incident','request_id':request_id}
                frames=[]
                for frame in traceback.extract_tb(exc.__traceback__):
                    try:path=str(Path(frame.filename).relative_to(directory/'deployed-source'))
                    except ValueError:continue
                    frames.append({'path':path,'line':frame.lineno,'function':frame.name})
                event={'event_id':str(uuid.uuid4()),'timestamp':time.time(),'severity':'error','error_type':type(exc).__name__,'message':str(exc),'stack':''.join(traceback.format_exception_only(type(exc),exc)).strip(),'frames':frames,'http_status':500,'route':self.path,'request_id':request_id,'deployment_ref':'reservation-local-v1','commit_sha':args.revision,'evidence_ref':'application.jsonl'}
                with log.open('a') as f:f.write(json.dumps(event)+'\n')
            self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(payload).encode())

    print('Controlled reservation application: http://127.0.0.1:'+str(args.port)+'/reserve | trigger: /fail',flush=True)
    print('Application source pinned to '+args.revision+'; errors are written to the selected JSONL file.',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()


if __name__=='__main__':main()

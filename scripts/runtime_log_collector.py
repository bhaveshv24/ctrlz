"""Independent read-only JSONL application-log forwarder (Python standard library).

Only the explicitly selected regular file is read. Collector cursor advances only
when CtrlZ acknowledges the event; retries retain the original source event ID.
"""
import argparse
import http.client
import json
import os
import stat
import time
from pathlib import Path
from urllib.parse import urlsplit


def post(endpoint, token, events):
    target=urlsplit(endpoint)
    if target.scheme not in {'http','https'} or not target.hostname or target.username or target.password or target.query or target.fragment or not target.path.startswith('/telemetry/'):
        raise ValueError('Use a telemetry endpoint without credentials/query')
    if target.scheme=='http' and target.hostname not in {'localhost','127.0.0.1','::1'}:
        raise ValueError('Remote collectors require HTTPS')
    cls=http.client.HTTPSConnection if target.scheme=='https' else http.client.HTTPConnection
    connection=cls(target.hostname,target.port,timeout=15)
    try:
        connection.request('POST',target.path,body=json.dumps({'events':events}).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        response=connection.getresponse();body=response.read(8192)
        if response.status!=200:raise RuntimeError('Collector delivery HTTP '+str(response.status))
        return json.loads(body)
    finally:connection.close()


def collect_once(log_file, cursor_file, endpoint, token):
    source=Path(log_file)
    if source.suffix not in {'.log','.jsonl'} or any(part in {'.ssh','.aws','credentials'} or part.startswith('.env') for part in source.parts):
        raise ValueError('Select one application .jsonl/.log file; credential paths are prohibited')
    if source.is_symlink():raise OSError('Symlink log sources are prohibited')
    fd=os.open(source,os.O_RDONLY | getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'rb') as handle:
        info=os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):raise ValueError('Source must be a regular log file')
        identity=[info.st_dev,info.st_ino]
        cursor_path=Path(cursor_file)
        cursor=json.loads(cursor_path.read_text()) if cursor_path.exists() else {}
        offset=cursor.get('offset',0) if cursor.get('identity')==identity else 0
        if offset>info.st_size:offset=0
        handle.seek(offset)
        sent=0
        while True:
            line=handle.readline(65537)
            if not line:break
            if len(line)>65536:raise ValueError('Application log line exceeds 64 KiB; cursor not advanced')
            if not line.endswith(b'\n'):break # Writer has not completed this record.
            data=json.loads(line)
            if not isinstance(data,dict) or 'event_id' not in data:raise ValueError('Structured log must carry its original event_id')
            result=post(endpoint,token,[data])
            offset=handle.tell()
            cursor_path.parent.mkdir(parents=True,exist_ok=True)
            temp=cursor_path.with_name(cursor_path.name+'.tmp')
            flags=os.O_WRONLY|os.O_CREAT|os.O_TRUNC|getattr(os,'O_NOFOLLOW',0)
            out=os.open(temp,flags,0o600)
            with os.fdopen(out,'w') as f:json.dump({'identity':identity,'offset':offset},f)
            os.replace(temp,cursor_path)
            print(json.dumps({'accepted':result.get('accepted'),'duplicates':result.get('duplicates'),'incident_ids':result.get('incident_ids',[])}),flush=True)
            sent+=1
        return sent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file',required=True)
    parser.add_argument('--cursor',required=True)
    parser.add_argument('--endpoint',required=True)
    parser.add_argument('--token-file',required=True)
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    token_path=Path(args.token_file)
    if token_path.is_symlink():parser.error('Use a regular source credential file')
    if os.name!='nt' and token_path.stat().st_mode & 0o077:parser.error('Source credential file must be private (mode 600)')
    token=token_path.read_text().strip()
    if not token:parser.error('Source credential is empty')
    while True:
        try:collect_once(args.file,args.cursor,args.endpoint,token)
        except (OSError,ValueError,RuntimeError,http.client.HTTPException) as exc:
            # Never print the raw log line, response, credential or exception payload.
            print('Collector delivery failed ('+type(exc).__name__+'); event remains pending.',flush=True)
            if args.once:return 1
        if args.once:return 0
        time.sleep(2)


if __name__=='__main__':raise SystemExit(main())

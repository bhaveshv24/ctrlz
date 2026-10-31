"""Operator-selected read-only SQLite snapshot -> authenticated workflow evidence.

No application API, arbitrary SQL, remote SSH, request bodies or automatic recovery.
This bounded one-shot collector can be run by an operator's scheduler.
"""
import argparse
import hashlib
import hmac
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError


def snapshots(database,table,id_column,resource_column,state_column,created_column,user_column=None):
    names=[table,id_column,resource_column,state_column,created_column]+([user_column] if user_column else [])
    if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}',v) for v in names):raise ValueError('Only approved SQL identifiers, never SQL expressions')
    path=Path(database)
    if path.is_symlink() or not path.is_file():raise ValueError('Select an existing regular application database')
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA query_only=ON');db.row_factory=sqlite3.Row
        known={r['name'] for r in db.execute('PRAGMA table_info("'+table+'")')}
        if not set(names[1:])<=known:raise ValueError('Approved columns do not match schema')
        columns=','.join('"'+v+'"' for v in names[1:]);cursor=0;count=0
        while True:
            rows=db.execute('SELECT rowid AS _cursor,'+columns+' FROM "'+table+'" WHERE rowid>? ORDER BY rowid LIMIT 500',(cursor,)).fetchall()
            if not rows:return
            for row in rows:
                cursor=row['_cursor'];count+=1
                if count>100000:raise ValueError('Snapshot capacity reached; partition the authorized source')
                yield dict(row)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['database','receiver','token-file','proposal','workflow','revision','artifact-digest','table','id-column','resource-column','state-column','created-column']:p.add_argument('--'+name,required=True)
    p.add_argument('--user-column');p.add_argument('--pseudonym-key-file');p.add_argument('--interval',type=int,default=0,help='0 for one snapshot; 5–3600 seconds for continuous read-only reconciliation');a=p.parse_args()
    if a.interval and not 5<=a.interval<=3600:p.error('Polling interval must be 5–3600 seconds')
    u=urlsplit(a.receiver)
    if u.scheme!='https' and not (u.scheme=='http' and u.hostname in {'localhost','127.0.0.1','::1'}):p.error('Receiver must use HTTPS or explicit loopback HTTP')
    if u.username or u.password or u.query or u.fragment:p.error('Receiver must not contain credentials/query/fragment')
    key=Path(a.token_file).read_text().strip();salt=Path(a.pseudonym_key_file).read_text().strip() if a.pseudonym_key_file else None
    batch=[];sent=0;versions={}
    def flush():
        nonlocal sent
        if not batch:return
        raw=json.dumps({'events':batch}).encode()
        for attempt in range(4):
            try:
                with urlopen(Request(a.receiver,data=raw,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'}),timeout=20) as response:response.read(10000)
                sent+=len(batch);batch.clear();return
            except HTTPError as error:
                if error.code!=429 or attempt==3:raise RuntimeError('Collector delivery rejected: HTTP '+str(error.code)) from None
                time.sleep(min(60,max(1,int(error.headers.get('Retry-After','60')))))
        raise RuntimeError('Delivery backpressure exhausted; rerun snapshot rather than assuming success')
    while True:
        run=uuid.uuid4().hex;sent_before=sent;seen=0
        for n,row in enumerate(snapshots(a.database,a.table,a.id_column,a.resource_column,a.state_column,a.created_column,a.user_column)):
            seen+=1;identifier=str(row[a.id_column]);version=hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()
            if row[a.state_column] in {'completed','cancelled'} and versions.get(identifier)==version:continue
            now=time.time();workflow={'audit_id':a.proposal,'workflow_id':a.workflow,'kind':'workflow.reconciled','instance_id':identifier,'resource_id':str(row[a.resource_column]),'started_at':row[a.created_column],
                'state':row[a.state_column],'artifact_digest':a.artifact_digest,'revision':a.revision}
            event={'event_id':hashlib.sha256((run+':'+str(n)).encode()).hexdigest(),'timestamp':now,'severity':'info','message':'Independent read-only durable job observation','workflow':workflow}
            if a.user_column and salt:event['user_id']=hmac.new(salt.encode(),str(row[a.user_column]).encode(),hashlib.sha256).hexdigest()[:24]
            batch.append(event);versions[identifier]=version
            if len(batch)==50:flush()
        flush()
        if sent==sent_before:
            batch.append({'event_id':run,'timestamp':time.time(),'severity':'info','message':'Authorized reconciliation source heartbeat','workflow':{'audit_id':a.proposal,'workflow_id':a.workflow,'kind':'workflow.heartbeat','artifact_digest':a.artifact_digest,'revision':a.revision}});flush()
        print(json.dumps({'observed_records':seen,'events_delivered':sent-sent_before,'database_mode':'read_only','business_mutations':0}),flush=True)
        if not a.interval:break
        time.sleep(a.interval)


if __name__=='__main__':main()

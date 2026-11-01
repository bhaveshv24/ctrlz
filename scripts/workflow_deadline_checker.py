"""Connected read-only checker: one indexed application lookup per dispatched overdue job."""
import argparse,json,re,sqlite3,time,uuid
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit


def lookup(database,table,id_column,resource_column,state_column,created_column,instance_id):
    names=[table,id_column,resource_column,state_column,created_column]
    if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}',x) for x in names):raise ValueError('Invalid configured identifier')
    path=Path(database)
    if path.is_symlink() or not path.is_file():raise ValueError('Authorized database is unavailable')
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=2) as db:
        db.execute('PRAGMA query_only=ON');db.row_factory=sqlite3.Row
        columns=db.execute('PRAGMA table_info("'+table+'")').fetchall()
        unique=[r['name'] for r in columns if r['pk']]==[id_column]
        for index in db.execute('PRAGMA index_list("'+table+'")').fetchall():
            if not index['unique']:continue
            indexed=db.execute('PRAGMA index_info("'+index['name'].replace('"','""')+'")').fetchall()
            unique=unique or [r['name'] for r in indexed]==[id_column]
        if not unique:raise ValueError('Target lookup requires an indexed unique operation ID')
        row=db.execute('SELECT "'+resource_column+'","'+state_column+'","'+created_column+'" FROM "'+table+'" WHERE "'+id_column+'"=?',(instance_id,)).fetchone()
        return dict(row) if row else None


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['database','receiver','token-file','table','id-column','resource-column','state-column','created-column']:p.add_argument('--'+name,required=True)
    p.add_argument('--metrics-file');a=p.parse_args()
    url=urlsplit(a.receiver)
    if url.scheme!='https' and not(url.scheme=='http' and url.hostname in {'127.0.0.1','localhost','::1'}):p.error('HTTPS or loopback receiver required')
    if url.username or url.password or url.query or url.fragment:p.error('Unsafe receiver URL')
    headers={'Authorization':'Bearer '+Path(a.token_file).read_text().strip()}
    metrics={'application_lookups':0,'results_delivered':0,'lookup_errors':0};cache={}
    while True:
        try:
            with urlopen(Request(a.receiver,headers=headers),timeout=40) as stream:
                for raw in stream:
                    line=raw.decode().strip()
                    if not line.startswith('data: '):continue
                    item=json.loads(line[6:]);key=(item['check_id'],item['lease'])
                    if key not in cache:
                        state='unknown';resource=item.get('resource_id');started=item['started_at']
                        try:
                            metrics['application_lookups']+=1
                            row=lookup(a.database,a.table,a.id_column,a.resource_column,a.state_column,a.created_column,item['instance_id'])
                            if row and str(row[a.resource_column])==resource:
                                state=row[a.state_column];started=row[a.created_column]
                            if state not in {'pending','running','completed','failed','cancelled'}:state='unknown'
                        except (OSError,ValueError,sqlite3.Error):metrics['lookup_errors']+=1
                        event={'event_id':uuid.uuid4().hex,'timestamp':time.time(),'severity':'info','message':'Deadline-triggered independent operation check',
                            'workflow':{'audit_id':item['proposal_id'],'workflow_id':item['workflow_id'],'kind':'workflow.reconciled','instance_id':item['instance_id'],'resource_id':resource,'revision':item['revision'],'artifact_digest':item['artifact_digest'],'started_at':started,'state':state,'check_id':item['check_id'],'check_lease':item['lease']}}
                        cache[key]=event
                        if len(cache)>1000:cache.pop(next(iter(cache)))
                    body=json.dumps({'events':[cache[key]]}).encode()
                    try:
                        with urlopen(Request(a.receiver,data=body,headers={**headers,'Content-Type':'application/json'}),timeout=20) as response:response.read(10000)
                        metrics['results_delivered']+=1
                    except Exception:pass # Lease expiry permits bounded redelivery; never replays a business action.
                    if a.metrics_file:Path(a.metrics_file).write_text(json.dumps(metrics))
                    print(json.dumps(metrics),flush=True)
        except Exception:
            time.sleep(2) # Reconnect only to CtrlZ; no application database polling.


if __name__=='__main__':main()

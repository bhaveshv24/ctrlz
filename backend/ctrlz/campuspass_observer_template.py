"""Optional observation of committed business records; never changes transactions.

Render companion sends lifecycle events and answers only leased, indexed checks.
No customer bodies, emails, recovery tokens or new application endpoints.
"""
import hashlib,hmac,json,os,queue,sqlite3,threading,time,uuid
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from sqlalchemy import event
from .db import Job,Ticket,Order


class Observer:
    def __init__(self,engine,sessions,config=None):
        self.config=dict(config if config is not None else os.environ)
        self.config.setdefault('CTRLZ_DEPLOYED_REVISION',self.config.get('RENDER_GIT_COMMIT',''))
        self.enabled=self.config.get('CTRLZ_WORKFLOW_ENABLED','false').lower()=='true'
        self.queue=queue.Queue(maxsize=512);self.stop_event=threading.Event()
        self.metrics={'events_sent':0,'events_dropped':0,'targeted_reads':0,'check_results':0,'errors':0}
        self.listeners=[];self.threads=[];self.database=engine.url.database
        if not self.enabled:return
        for key in ['CTRLZ_APP_RECEIVER','CTRLZ_STATE_RECEIVER']:
            url=urlsplit(self.config.get(key,''))
            if url.scheme!='https' and not(url.scheme=='http' and url.hostname in {'localhost','127.0.0.1'}):raise ValueError('Observation receiver requires HTTPS or loopback')
            if url.username or url.password or url.query or url.fragment:raise ValueError('Invalid observation receiver')
        for key in ['CTRLZ_APP_SOURCE_TOKEN','CTRLZ_STATE_SOURCE_TOKEN','CTRLZ_PROPOSAL_ID','CTRLZ_WORKFLOW_ID','CTRLZ_ARTIFACT_DIGEST','CTRLZ_DEPLOYED_REVISION']:
            if not self.config.get(key):raise ValueError('Incomplete optional workflow configuration: '+key)
        def flushed(session,context):
            pending=session.info.setdefault('ctrlz_observations',[])
            for obj in session.new:
                if isinstance(obj,Job):
                    order=session.get(Order,obj.order_id)
                    pending.append(('workflow.started',obj.order_id,order.customer_id if order else None))
                elif isinstance(obj,Ticket) and obj.valid==1:pending.append(('workflow.completed',obj.order_id,None))
        def committed(session):
            for kind,order_id,user in session.info.pop('ctrlz_observations',[]):self.emit(kind,order_id,user)
        def rolled_back(session):session.info.pop('ctrlz_observations',None)
        for name,fn in [('after_flush',flushed),('after_commit',committed),('after_rollback',rolled_back)]:
            def safe(*args,_fn=fn,**kwargs):
                try:_fn(*args,**kwargs)
                except Exception:self.metrics['errors']+=1
            event.listen(sessions,name,safe);self.listeners.append((sessions,name,safe))

    def emit(self,kind,order_id,user=None):
        try:
            workflow={'audit_id':self.config['CTRLZ_PROPOSAL_ID'],'workflow_id':self.config['CTRLZ_WORKFLOW_ID'],'kind':kind,'instance_id':order_id,'resource_id':order_id,
                'artifact_digest':self.config['CTRLZ_ARTIFACT_DIGEST'],'revision':self.config['CTRLZ_DEPLOYED_REVISION']}
            payload={'event_id':uuid.uuid4().hex,'timestamp':time.time(),'severity':'info','message':'Committed ticket workflow observation','workflow':workflow}
            salt=self.config.get('CTRLZ_USER_PSEUDONYM_KEY')
            if user and salt and self.config.get('CTRLZ_COLLECT_USER')=='true':payload['user_id']=hmac.new(salt.encode(),user.encode(),hashlib.sha256).hexdigest()[:24]
            self.queue.put_nowait(payload)
        except Exception:self.metrics['events_dropped']+=1

    def lookup(self,order_id):
        self.metrics['targeted_reads']+=1
        with sqlite3.connect(Path(self.database).resolve().as_uri()+'?mode=ro',uri=True,timeout=2) as db:
            db.execute('PRAGMA query_only=ON')
            row=db.execute('SELECT o.id,o.created,p.status,j.status,(SELECT count(*) FROM tickets t WHERE t.order_id=o.id AND t.valid=1) FROM orders o LEFT JOIN payments p ON p.order_id=o.id LEFT JOIN jobs j ON j.order_id=o.id WHERE o.id=?',(order_id,)).fetchone()
        if row is None:return None
        state='completed' if row[2]=='paid' and row[3]=='done' and row[4]==1 else 'pending' if row[2]=='paid' else 'unknown'
        return {'state':state,'started_at':row[1]}

    def sender(self):
        with httpx.Client(timeout=10,follow_redirects=False) as client:
            while not self.stop_event.is_set():
                try:payload=self.queue.get(timeout=.5)
                except queue.Empty:continue
                for attempt in range(3):
                    try:
                        r=client.post(self.config['CTRLZ_APP_RECEIVER'],headers={'Authorization':'Bearer '+self.config['CTRLZ_APP_SOURCE_TOKEN']},json={'events':[payload]});r.raise_for_status()
                        self.metrics['events_sent']+=1;break
                    except Exception:
                        self.metrics['errors']+=1
                        if self.stop_event.wait(1):break
                self.queue.task_done()

    def checker(self):
        cache={}
        with httpx.Client(timeout=httpx.Timeout(40,connect=10),follow_redirects=False) as client:
            headers={'Authorization':'Bearer '+self.config['CTRLZ_STATE_SOURCE_TOKEN']}
            while not self.stop_event.is_set():
                try:
                    with client.stream('GET',self.config['CTRLZ_STATE_RECEIVER'],params={'transport':'long_poll'},headers=headers) as stream:
                        stream.raise_for_status()
                        message=json.loads(stream.read())
                        for line in ['data: '+json.dumps(message['check'])] if message.get('check') else []:
                            if self.stop_event.is_set():return
                            if not line.startswith('data: '):continue
                            item=json.loads(line[6:]);key=(item['check_id'],item['lease'])
                            if item['proposal_id']!=self.config['CTRLZ_PROPOSAL_ID'] or item['revision']!=self.config['CTRLZ_DEPLOYED_REVISION'] or item['artifact_digest']!=self.config['CTRLZ_ARTIFACT_DIGEST']:continue
                            if item['instance_id']!=item['resource_id']:continue
                            if key not in cache:
                                try:record=self.lookup(item['instance_id'])
                                except Exception:record=None;self.metrics['errors']+=1
                                signal={'audit_id':item['proposal_id'],'workflow_id':item['workflow_id'],'kind':'workflow.reconciled','instance_id':item['instance_id'],'resource_id':item['resource_id'],
                                    'artifact_digest':item['artifact_digest'],'revision':item['revision'],'check_id':item['check_id'],'check_lease':item['lease'],
                                    'started_at':record['started_at'] if record else item['started_at'],'state':record['state'] if record else 'unknown'}
                                cache[key]={'event_id':uuid.uuid4().hex,'timestamp':time.time(),'severity':'info','message':'Targeted paid-order entitlement reconciliation','workflow':signal}
                                if len(cache)>512:cache.pop(next(iter(cache)))
                            r=client.post(self.config['CTRLZ_STATE_RECEIVER'],headers=headers,json={'events':[cache[key]]})
                            if r.is_success:self.metrics['check_results']+=1
                except Exception:
                    self.metrics['errors']+=1
                    self.stop_event.wait(2)

    def start(self):
        if self.enabled:
            for target in [self.sender,self.checker]:
                t=threading.Thread(target=target,daemon=True);t.start();self.threads.append(t)

    def close(self):
        self.stop_event.set()
        for owner,name,fn in self.listeners:event.remove(owner,name,fn)


def attach(app,sessions,engine,contract):
    config=dict(os.environ)
    config.update(CTRLZ_PROPOSAL_ID=contract['proposal_id'],CTRLZ_WORKFLOW_ID=contract['workflow_id'],CTRLZ_ARTIFACT_DIGEST=contract['artifact_digest'])
    config['CTRLZ_COLLECT_USER']='true' if 'user_id' in contract['allowed_fields'] else 'false'
    try:observer=Observer(engine,sessions,config)
    except Exception:
        # Invalid optional monitoring configuration must not break business startup.
        app.state.workflow_observation_status='configuration_invalid'
        return
    from contextlib import asynccontextmanager
    original=app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(target):
        try:observer.start()
        except Exception:observer.metrics['errors']+=1
        try:
            async with original(target):yield
        finally:observer.close()
    app.router.lifespan_context=lifespan
    app.state.workflow_observer=observer

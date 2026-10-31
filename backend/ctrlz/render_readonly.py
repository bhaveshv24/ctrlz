"""Bounded documented Render GETs. No infrastructure mutations or arbitrary URLs."""
from datetime import datetime, timezone, timedelta
from .runtime_security import Redactor

API='https://api.render.com/v1'

class RenderReadOnly:
    def __init__(self,client,key):
        if not key:raise ValueError('RENDER_API_KEY is not configured')
        self.client,self.key=client,key
        self.redactor=Redactor([key])
    def get(self,path,params=None):
        r=self.client.get(API+path,params=params,headers={'Authorization':'Bearer '+self.key,'Accept':'application/json'},timeout=30,follow_redirects=False)
        if not r.is_success:raise RuntimeError('Render read-only API returned HTTP '+str(r.status_code))
        return r.json()
    def service(self,url):
        cursor=None
        for _ in range(10):
            rows=self.get('/services',{'limit':100,**({'cursor':cursor} if cursor else {})})
            for row in rows:
                service=row.get('service',{})
                if service.get('serviceDetails',{}).get('url','').rstrip('/')==url.rstrip('/'):
                    return {'id':service['id'],'ownerId':service['ownerId'],'url':url,'repo':service.get('repo'),'branch':service.get('branch')}
            if not rows or len(rows)<100:break
            next_cursor=rows[-1].get('cursor')
            if not next_cursor or next_cursor==cursor:break
            cursor=next_cursor
        raise RuntimeError('Expected CampusPass URL not found in bounded authorized Render service listing')
    def logs(self,service,order_id=None,seen=()):
        start=(datetime.now(timezone.utc)-timedelta(minutes=30)).isoformat()
        end=datetime.now(timezone.utc).isoformat();events=[];known=set(seen)
        for _ in range(10):
            params={'ownerId':service['ownerId'],'resource':service['id'],'direction':'forward','limit':100,'startTime':start,'endTime':end}
            if order_id:params['text']=order_id
            page=self.get('/logs',params)
            for log in page.get('logs',[]):
                labels={x['name']:x['value'] for x in log.get('labels',[])}
                if labels.get('resource')!=service['id']:continue
                if log['id'] in known:continue
                if order_id and order_id not in log.get('message',''):continue
                known.add(log['id']);events.append({'id':log['id'],'timestamp':log.get('timestamp'),'message':self.redactor.text(log.get('message',''))[:8000],'service_id':service['id']})
            if not page.get('hasMore'):return events,False
            nxt=(page.get('nextStartTime'),page.get('nextEndTime'))
            if not all(nxt) or nxt==(start,end):raise RuntimeError('Render pagination failed to advance')
            start,end=nxt
        return events,True
    def deployment(self,service):
        rows=self.get('/services/'+service['id']+'/deploys',{'limit':20})
        live=next((r['deploy'] for r in rows if r.get('deploy',{}).get('status')=='live'),None)
        return {'state':'observed' if live else 'unknown','id':live.get('id') if live else None,'commit':live.get('commit',{}).get('id') if live else None}

"""Independent HTTP integration fixture: a paused dispatch queue, no CampusPass code."""
import hmac,os
from uuid import UUID
from fastapi import FastAPI,Header,HTTPException
from pydantic import BaseModel,ConfigDict
app=FastAPI(title='Dispatch Queue integration fixture')
state={'paused':True,'revision':1,'pending_jobs':3,'completed_jobs':0}
requests={}
def auth(x_recovery_token:str=Header(default='')):
    expected=os.environ.get('DISPATCH_RECOVERY_TOKEN','')
    if not expected or not hmac.compare_digest(expected,x_recovery_token):raise HTTPException(401,'Recovery token required')
@app.get('/health')
def health():return {'ready':not state['paused'],'service':'dispatch-queue'}
@app.get('/internal/state')
def diagnostics(x_recovery_token:str=Header(default='')):
    auth(x_recovery_token);return state
class Resume(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str
    expected_revision:int
@app.post('/internal/resume')
def resume(body:Resume,x_recovery_token:str=Header(default='')):
    auth(x_recovery_token)
    try:UUID(body.request_id)
    except ValueError:raise HTTPException(422,'UUID required')
    if body.request_id in requests:return requests[body.request_id]
    if body.expected_revision!=state['revision']:raise HTTPException(409,'Revision changed')
    if not state['paused']:raise HTTPException(409,'Dispatcher already running')
    state.update(paused=False,revision=state['revision']+1,completed_jobs=state['completed_jobs']+state['pending_jobs'],pending_jobs=0)
    result={'resumed':True,'revision':state['revision']};requests[body.request_id]=result
    return result

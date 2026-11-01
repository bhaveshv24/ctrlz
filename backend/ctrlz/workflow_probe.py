"""Standalone generated probe: stdlib only, bounded best-effort stdout, no network.

Disabled unless CTRLZ_OBSERVE_ENABLED=1. Export loss cannot prove business failure.
"""
import functools
import hashlib
import hmac
import inspect
import json
import os
import queue
import re
import sys
import threading
import time
import uuid

_queue=queue.Queue(maxsize=256)
_lock=threading.Lock()
_thread=None
_dropped=0


def _writer():
    while True:
        value=_queue.get()
        try:
            sys.stdout.write(json.dumps(value,separators=(',',':'))+'\n')
            sys.stdout.flush()
        except Exception:
            pass
        finally:
            _queue.task_done()


def _emit(event):
    global _thread,_dropped
    if os.getenv('CTRLZ_OBSERVE_ENABLED')!='1':return
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread=threading.Thread(target=_writer,daemon=True,name='ctrlz-observation')
            _thread.start()
    try:_queue.put_nowait(event)
    except queue.Full:_dropped+=1


def _value(expression,arguments,result):
    parts=expression.split('.')
    value=arguments if parts[0]=='arg' else result
    for key in parts[1:]:
        if type(value) is not dict:return None
        value=value.get(key)
    return value


def _send(config,arguments,result,kind,error=None):
    # Telemetry errors never escape into the application. No request/response capture.
    try:
        if os.getenv('CTRLZ_OBSERVE_ENABLED')!='1':return
        values={}
        for name,path in config['fields'].items():
            value=_value(path,arguments,result)
            if type(value) not in (str,int):continue
            value=str(value)
            if name=='user_id':
                salt=os.getenv('CTRLZ_OBSERVE_PSEUDONYM_KEY','')
                if not salt:continue
                value=hmac.new(salt.encode(),value.encode(),hashlib.sha256).hexdigest()[:24]
            if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',value):values[name]=value
        if 'instance_id' not in values:return
        workflow={k:config[k] for k in ('audit_id','workflow_id','artifact_digest')}
        revision=os.getenv('CTRLZ_OBSERVE_REVISION','')
        if not re.fullmatch(r'(?:[a-f0-9]{40}|sha256:[a-f0-9]{64})',revision):return
        workflow.update(revision=revision,kind=kind)
        workflow.update({k:v for k,v in values.items() if k in {'instance_id','resource_id','parent_id'}})
        if error:workflow['error_class']=type(error).__name__
        event={'event_id':uuid.uuid4().hex,'timestamp':time.time(),'severity':'info','message':'Approved workflow observation','workflow':workflow}
        event.update({k:v for k,v in values.items() if k in {'request_id','trace_id','user_id'}})
        _emit(event)
    except BaseException:
        # Only the observation is isolated. Original application calls are outside this guard.
        return


def observe(**config):
    def decorate(function):
        signature=inspect.signature(function)
        def arguments(args,kwargs):
            try:return dict(signature.bind_partial(*args,**kwargs).arguments)
            except Exception:return {}
        def finished(bound,result):
            try:
                if config['role']=='start':_send(config,bound,result,'workflow.started')
                elif _value(config['completion_key'],bound,result)==config['completion_value']:_send(config,bound,result,'workflow.completed')
            except BaseException:pass
        if inspect.iscoroutinefunction(function):
            @functools.wraps(function)
            async def wrapped(*args,**kwargs):
                bound=arguments(args,kwargs)
                try:result=await function(*args,**kwargs)
                except BaseException as error:
                    _send(config,bound,None,'workflow.failed',error);raise
                finished(bound,result)
                return result
        else:
            @functools.wraps(function)
            def wrapped(*args,**kwargs):
                bound=arguments(args,kwargs)
                try:result=function(*args,**kwargs)
                except BaseException as error:
                    _send(config,bound,None,'workflow.failed',error);raise
                finished(bound,result)
                return result
        return wrapped
    return decorate

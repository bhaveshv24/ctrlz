"""Provider boundaries. No provider URL is accepted from telemetry payloads."""
import hashlib
import hmac
import json
import re
from typing import Protocol
from fastapi import HTTPException
from .runtime_models import EventBatch, StackFrame


class RuntimeConnector(Protocol):
    def decode(self, raw: bytes, headers, secret: str, deployment) -> EventBatch: ...


class GenericEvents:
    def decode(self, raw, headers, secret, deployment):
        supplied=headers.get('authorization','')
        if not secret or not hmac.compare_digest(supplied,'Bearer '+secret):
            raise HTTPException(401,'Source credential required')
        return EventBatch.model_validate_json(raw)


class VercelDrain:
    """Official JSON/NDJSON log-drain format, HMAC-SHA1 over exact raw bytes."""
    def decode(self, raw, headers, secret, deployment):
        expected=hmac.new(secret.encode(),raw,hashlib.sha1).hexdigest()
        if not secret or not hmac.compare_digest(headers.get('x-vercel-signature',''),expected):
            raise HTTPException(401,'Invalid Vercel drain signature')
        try:
            rows=json.loads(raw) if raw.lstrip().startswith(b'[') else [json.loads(line) for line in raw.splitlines() if line.strip()]
        except (ValueError,UnicodeError):
            raise HTTPException(422,'Invalid drain JSON')
        if not isinstance(rows,list) or not 1 <= len(rows) <= 50:
            raise HTTPException(413,'Drain requires 1–50 records')
        events=[]
        for row in rows:
            if not isinstance(row,dict) or row.get('projectId') != deployment.service_id or (row.get('customEnvironment') or row.get('environment')) != deployment.environment:
                raise HTTPException(403,'Drain project/environment does not match configured target')
            if deployment.deployment_ref and row.get('deploymentId') != deployment.deployment_ref:
                raise HTTPException(403,'Drain deployment does not match configured target')
            # Build output is not an observed runtime exception.
            if row.get('source') not in {'lambda','edge','static','external'}:
                continue
            if not isinstance(row.get('timestamp'),(int,float)) or not row.get('deploymentId'):
                raise HTTPException(422,'Drain event lacks timestamp/deployment')
            proxy=row.get('proxy') or {}
            if not isinstance(proxy,dict):raise HTTPException(422,'Invalid provider proxy metadata')
            status=row.get('statusCode',proxy.get('statusCode'))
            if status is not None and not 100 <= status <= 599:status=None
            message=row.get('message','')
            if not isinstance(message,str):raise HTTPException(422,'Invalid provider message')
            error=re.search(r'\b([A-Za-z][A-Za-z0-9_.]*(?:Error|Exception)|Error|Exception):',message)
            frames=[]
            for match in re.finditer(r'(?:\bat\s+(?:[\w.]+\s+\()?)([\w./-]+\.[cm]?[jt]sx?):(\d+)(?::\d+)?',message):
                try:frames.append(StackFrame(path=match[1],line=int(match[2])).model_dump())
                except ValueError:continue
            events.append({'event_id':row.get('id'),'timestamp':row['timestamp']/1000,'severity':row.get('level'),'error_type':error[1] if error else None,'message':message,'stack':message if frames else None,'frames':frames[:12], 'http_status':status,'route':row.get('path'),'request_id':row.get('requestId'),'trace_id':row.get('traceId',row.get('trace.id')),'deployment_ref':row['deploymentId']})
        if not events:
            return None
        return EventBatch.model_validate({'events':events})


CONNECTORS={'generic-events':GenericEvents(),'vercel-drain':VercelDrain()}

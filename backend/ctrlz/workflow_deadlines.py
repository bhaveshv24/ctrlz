"""Durable, leased, resource-scoped deadline checks. Never reads application state."""
import secrets
import time
from sqlalchemy import String,Float,JSON,Index,select,text
from sqlalchemy.orm import Mapped,mapped_column
from .database import private_tables
from .store import Base
from .runtime_store import digest
from .workflow_store import InstanceRow,ProposalRow


class DeadlineCheck(Base):
    __tablename__='workflow_deadline_checks'
    __table_args__=(Index('deadline_ready','state','due'),)
    id:Mapped[str]=mapped_column(String,primary_key=True)
    proposal_id:Mapped[str]=mapped_column(index=True)
    instance_key:Mapped[str]=mapped_column(index=True)
    source_id:Mapped[str]
    due:Mapped[float]=mapped_column(Float)
    state:Mapped[str]
    payload:Mapped[dict]=mapped_column(JSON)


class Deadlines:
    def __init__(self,workflows):
        self.w=workflows;self.store=workflows.store
        Base.metadata.create_all(self.store.engine)
        private_tables(self.store.engine, Base.metadata.tables)

    def schedule(self,db,row,p):
        activation=p.get('activation') or {}
        if activation.get('check_mode')!='deadline_targeted' or not activation.get('reconciliation_source_id'):return
        item=db.get(DeadlineCheck,row.key)
        if row.state in {'completed','cancelled'}:
            if item and item.state not in {'done','cancelled'}:item.state='cancelled'
            return
        if item is None:
            db.add(DeadlineCheck(id=row.key,proposal_id=p['id'],instance_key=row.key,source_id=activation['reconciliation_source_id'],due=row.deadline,state='waiting',payload={'revision':activation['revision'],'artifact_digest':activation['artifact_digest'],'instance_id':row.instance_id,'attempts':0}))

    def claim(self,project,deployment,source):
        now=self.w.clock()
        with self.store.sessions.begin() as db:
            self.store.lock(db)
            # Bounded admission; leases recover after disconnect/restart.
            items=db.scalars(select(DeadlineCheck).join(ProposalRow,ProposalRow.id==DeadlineCheck.proposal_id).where(ProposalRow.project_id==project,ProposalRow.payload['deployment_id'].as_string()==deployment,DeadlineCheck.source_id==source,DeadlineCheck.state.in_(['waiting','leased']),DeadlineCheck.due<=now).order_by(DeadlineCheck.due).limit(100)).all()
            for item in items:
                p=self.w.proposal(item.proposal_id);a=p.get('activation') or {}
                if p['project_id']!=project or p['deployment_id']!=deployment:continue
                row=db.get(InstanceRow,item.instance_key)
                if not row or row.state in {'completed','cancelled'} or a.get('revision')!=item.payload['revision'] or a.get('artifact_digest')!=item.payload['artifact_digest'] or a.get('reconciliation_source_id')!=source or p['status'] not in {'monitoring_active','monitoring_degraded','deployment_observed'}:
                    item.state='cancelled';continue
                if not self.store.project(project).get('enabled'):continue
                if item.payload['attempts']>=3:
                    item.state='unavailable';continue
                nonce=secrets.token_hex(24);item.state='leased';item.due=now+30
                item.payload={**item.payload,'nonce':nonce,'attempts':item.payload['attempts']+1,'lease_until':now+30}
                return {'check_id':item.id,'lease':nonce,'proposal_id':p['id'],'workflow_id':p['rule']['id'],'instance_id':row.instance_id,'resource_id':row.payload.get('resource_id'),'revision':a['revision'],'artifact_digest':a['artifact_digest'],'started_at':row.deadline-p['rule']['deadline_seconds'],'deadline':row.deadline}
        return None

    def validate(self,p,event):
        signal=event['workflow']
        if not signal.get('check_id') or not signal.get('check_lease'):raise ValueError('A leased deadline check is required')
        with self.store.sessions() as db:
            item=db.get(DeadlineCheck,signal.get('check_id'))
            if not item or item.proposal_id!=p['id'] or item.source_id!=event['source_id'] or item.payload.get('nonce')!=signal.get('check_lease'):
                raise ValueError('Unknown or unauthorized deadline check')
            # Exact result replay may retry ingestion after a lost acknowledgement.
            signature=digest(signal)
            if item.state=='done' and item.payload.get('result_digest')==signature:return False
            row=db.get(InstanceRow,item.instance_key)
            if item.state!='leased' or item.due<self.w.clock() or not row or row.state in {'completed','cancelled'}:
                raise ValueError('Expired or cancelled deadline check')
            if signal.get('instance_id')!=row.instance_id or signal.get('resource_id')!=row.payload.get('resource_id') or signal.get('revision')!=item.payload['revision'] or signal.get('artifact_digest')!=item.payload['artifact_digest']:
                raise ValueError('Deadline result does not match the exact operation')
        return True

    def finish(self,db,event):
        signal=event['workflow'];item=db.get(DeadlineCheck,signal['check_id'])
        item.state='done';item.payload={**item.payload,'result_digest':digest(signal),'outcome':signal.get('state','unknown')}

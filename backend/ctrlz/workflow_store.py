"""Additive workspace-local audit and active-operation tables."""
import time
from sqlalchemy import JSON, Float, String, Index, select, func
from sqlalchemy.orm import Mapped, mapped_column
from .store import Base


class AuditRow(Base):
    __tablename__='workflow_audits'
    id: Mapped[str]=mapped_column(String,primary_key=True)
    project_id: Mapped[str]=mapped_column(index=True)
    created: Mapped[float]=mapped_column(Float,default=time.time)
    payload: Mapped[dict]=mapped_column(JSON)


class ProposalRow(Base):
    __tablename__='workflow_proposals'
    id: Mapped[str]=mapped_column(String,primary_key=True)
    audit_id: Mapped[str]=mapped_column(index=True)
    project_id: Mapped[str]=mapped_column(index=True)
    payload: Mapped[dict]=mapped_column(JSON)


class InstanceRow(Base):
    __tablename__='workflow_instances'
    __table_args__=(Index('workflow_due','proposal_id','state','deadline'),)
    key: Mapped[str]=mapped_column(String,primary_key=True)
    proposal_id: Mapped[str]=mapped_column(index=True)
    instance_id: Mapped[str]
    state: Mapped[str]=mapped_column(String)
    deadline: Mapped[float]=mapped_column(Float)
    updated: Mapped[float]=mapped_column(Float)
    payload: Mapped[dict]=mapped_column(JSON)


class WorkflowStorage:
    def __init__(self,store):
        self.store=store;Base.metadata.create_all(store.engine)

    def get(self,table,key):
        with self.store.sessions() as db:
            row=db.get(table,key)
            if row is None:raise KeyError('Unknown workflow record')
            return dict(row.payload)

    def save(self,table,key,value):
        with self.store.sessions.begin() as db:
            row=db.get(table,key)
            if row:row.payload=value
            elif table is AuditRow:db.add(table(id=key,project_id=value['project_id'],payload=value))
            else:db.add(table(id=key,audit_id=value['audit_id'],project_id=value['project_id'],payload=value))

    def proposals(self,project_id=None,audit_id=None):
        with self.store.sessions() as db:
            q=select(ProposalRow)
            if project_id:q=q.where(ProposalRow.project_id==project_id)
            if audit_id:q=q.where(ProposalRow.audit_id==audit_id)
            return [r.payload for r in db.scalars(q)]

    def audits(self,project_id):
        with self.store.sessions() as db:
            return [r.payload for r in db.scalars(select(AuditRow).where(AuditRow.project_id==project_id).order_by(AuditRow.created.desc()).limit(20))]

    def summary(self,proposal_id):
        with self.store.sessions() as db:
            counts=dict(db.execute(select(InstanceRow.state,func.count()).where(InstanceRow.proposal_id==proposal_id).group_by(InstanceRow.state)).all())
            active=[{'instance_id':r.instance_id,'state':r.state,'deadline':r.deadline,**r.payload} for r in db.scalars(select(InstanceRow).where(InstanceRow.proposal_id==proposal_id,InstanceRow.state.not_in(['completed','cancelled'])).order_by(InstanceRow.deadline).limit(100))]
            return {'counts':counts,'incomplete':active,'display_limit':100,'detection_limit':'Indexed pending scan; not limited to displayed records'}

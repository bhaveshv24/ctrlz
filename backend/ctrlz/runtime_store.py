"""Bounded workspace-local runtime evidence, delivery deduplication and rate limits."""
import hashlib
import json
import time
from sqlalchemy import JSON, Float, Integer, String, Boolean, UniqueConstraint, delete, select, text, func
from sqlalchemy.orm import Mapped, mapped_column
from fastapi import HTTPException
from .store import Base


class RuntimeRow(Base):
    __tablename__ = 'runtime_events'
    __table_args__ = (UniqueConstraint('project_id','deployment_id','source_id','event_id'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(index=True)
    deployment_id: Mapped[str]
    source_id: Mapped[str]
    event_id: Mapped[str]
    received: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[float] = mapped_column(Float)
    fingerprint: Mapped[str] = mapped_column(index=True)
    digest: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    incident_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)


class RuntimeRate(Base):
    __tablename__ = 'runtime_rate_limits'
    scope: Mapped[str] = mapped_column(String, primary_key=True)
    minute: Mapped[int]
    batches: Mapped[int]
    events: Mapped[int]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',',':')).encode()).hexdigest()


class RuntimeStorage:
    maximum = 10000
    retention = 7*86400

    def __init__(self, store):
        self.store = store
        Base.metadata.create_all(store.engine)

    @staticmethod
    def view(row):
        return {'id':row.id,'received_at':row.received,'incident_id':row.incident_id,**row.payload}

    def ingest(self, scope, events):
        now = time.time()
        with self.store.sessions.begin() as db:
            db.execute(text('BEGIN IMMEDIATE'))
            rate = db.get(RuntimeRate, scope)
            minute = int(now//60)
            if not rate:
                rate = RuntimeRate(scope=scope,minute=minute,batches=0,events=0)
                db.add(rate)
            if rate.minute != minute:
                rate.minute,rate.batches,rate.events = minute,0,0
            if rate.batches >= 120 or rate.events+len(events) > 1000:
                raise HTTPException(429,'Source ingestion rate exceeded',headers={'Retry-After':'60'})
            rate.batches += 1
            rate.events += len(events)
            rows,duplicates = [],0
            for event in events:
                prior = db.scalar(select(RuntimeRow).where(RuntimeRow.project_id==event['project_id'],RuntimeRow.deployment_id==event['deployment_id'],RuntimeRow.source_id==event['source_id'],RuntimeRow.event_id==event['event_id']))
                hashed = digest(event)
                if prior:
                    if prior.digest != hashed:
                        raise HTTPException(409,'Event ID reused for different sanitized content')
                    duplicates += 1
                    continue
                row = RuntimeRow(project_id=event['project_id'],deployment_id=event['deployment_id'],source_id=event['source_id'],event_id=event['event_id'],received=now,timestamp=event['timestamp'],fingerprint=event['fingerprint'],digest=hashed,payload=event,processed=False)
                db.add(row)
                db.flush()
                rows.append(row.id)
            # Bounded raw telemetry only. Incident snapshots/flight recorder are retained.
            db.execute(delete(RuntimeRow).where(RuntimeRow.received < now-self.retention))
            keep = select(RuntimeRow.id).order_by(RuntimeRow.id.desc()).limit(self.maximum)
            db.execute(delete(RuntimeRow).where(RuntimeRow.id.not_in(keep)))
            db.execute(delete(RuntimeRate).where(RuntimeRate.minute < minute-1440))
            return rows,duplicates

    def rows(self, project_id=None, incident_id=None, unprocessed=False, limit=100):
        with self.store.sessions() as db:
            q = select(RuntimeRow)
            if project_id:q=q.where(RuntimeRow.project_id==project_id)
            if incident_id:q=q.where(RuntimeRow.incident_id==incident_id)
            if unprocessed:q=q.where(RuntimeRow.processed==False)
            return [self.view(r) for r in db.scalars(q.order_by(RuntimeRow.id.desc()).limit(limit))]

    def link(self, row_id, incident_id):
        with self.store.sessions.begin() as db:
            row=db.get(RuntimeRow,row_id)
            if row:
                row.incident_id,row.processed=incident_id,True

    def summary(self, project_id, deployment_id=None):
        with self.store.sessions() as db:
            q=select(RuntimeRow).where(RuntimeRow.project_id==project_id)
            if deployment_id:q=q.where(RuntimeRow.deployment_id==deployment_id)
            rows=db.scalars(q.order_by(RuntimeRow.id.desc()).limit(self.maximum)).all()
            errors=[r for r in rows if r.payload.get('signal')]
            users={r.payload['user_id'] for r in errors if r.payload.get('user_id')}
            return {'event_count':len(rows),'error_count':len(errors),'last_received':max((r.received for r in rows),default=None),'last_event_at':max((r.timestamp for r in rows),default=None),'measured_affected_users':len(users) if users else None,'user_coverage':'pseudonymous IDs only; events without IDs are unknown'}

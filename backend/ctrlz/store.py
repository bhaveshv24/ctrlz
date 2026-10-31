import time
import uuid
from sqlalchemy import JSON, Float, Integer, String, create_engine, delete, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    config: Mapped[dict] = mapped_column(JSON)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str]
    kind: Mapped[str]
    resource: Mapped[str]
    status: Mapped[str]
    created: Mapped[float] = mapped_column(Float)
    updated: Mapped[float] = mapped_column(Float)
    data: Mapped[dict] = mapped_column(JSON)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str]
    timestamp: Mapped[float] = mapped_column(Float)
    stage: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)


class Probe(Base):
    __tablename__ = "monitor_probes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(index=True)
    timestamp: Mapped[float] = mapped_column(Float)
    result: Mapped[dict] = mapped_column(JSON)


class DemoRun(Base):
    __tablename__ = "demo_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str]
    scenario: Mapped[str]
    created: Mapped[float] = mapped_column(Float)
    result: Mapped[dict] = mapped_column(JSON)


class Store:
    def __init__(self, url="sqlite:///./ctrlz.db"):
        self.engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def projects(self):
        with self.sessions() as s:
            return [p.config for p in s.scalars(select(ProjectRow))]

    def project(self, project_id):
        with self.sessions() as s:
            row = s.get(ProjectRow, project_id)
            if row is None:
                raise KeyError(project_id)
            return row.config

    def save_project(self, config):
        with self.sessions.begin() as s:
            row = s.get(ProjectRow, config["id"])
            if row:
                row.config = config
            else:
                s.add(ProjectRow(id=config["id"], config=config))

    def observe(self, project_id, health, workflows):
        with self.sessions.begin() as s:
            s.add(Probe(project_id=project_id, timestamp=time.time(), result={"health": health, "workflows": workflows}))
            s.flush()
            retained = select(Probe.id).where(Probe.project_id == project_id).order_by(Probe.id.desc()).limit(120)
            s.execute(delete(Probe).where(Probe.project_id == project_id, Probe.id.not_in(retained)))

    def probes(self, project_id):
        with self.sessions() as s:
            return [{"id": p.id, "timestamp": p.timestamp, **p.result} for p in s.scalars(select(Probe).where(Probe.project_id == project_id).order_by(Probe.id))]

    def demo_start(self, request_id, project_id, scenario):
        with self.sessions.begin() as s:
            s.execute(text("BEGIN IMMEDIATE"))
            row = s.get(DemoRun, request_id)
            if row:
                if row.project_id != project_id or row.scenario != scenario:
                    raise ValueError("Demo request ID was already used for different parameters")
                return {"id": row.id, "project_id": row.project_id, "scenario": row.scenario, "created": row.created, **row.result}, False
            row = DemoRun(id=request_id, project_id=project_id, scenario=scenario, created=time.time(), result={"status": "executing"})
            s.add(row)
            return {"id": row.id, "project_id": row.project_id, "scenario": row.scenario, "created": row.created, **row.result}, True

    def demo_finish(self, request_id, result):
        with self.sessions.begin() as s:
            s.get(DemoRun, request_id).result = result

    def demo_runs(self, project_id=None):
        with self.sessions() as s:
            return [{"id": r.id, "project_id": r.project_id, "scenario": r.scenario, "created": r.created, **r.result} for r in s.scalars(select(DemoRun).where(DemoRun.project_id == project_id).order_by(DemoRun.created.desc()).limit(30) if project_id else select(DemoRun).order_by(DemoRun.created.desc()).limit(30))]

    @staticmethod
    def view(i):
        return {"id": i.id, "project_id": i.project_id, "kind": i.kind, "resource": i.resource, "status": i.status, "created": i.created, "updated": i.updated, **i.data}

    def create(self, project_id, kind, resource, evidence):
        with self.sessions.begin() as s:
            s.execute(text("BEGIN IMMEDIATE"))
            existing = s.scalar(select(Incident).where(Incident.project_id == project_id, Incident.kind == kind, Incident.resource == resource, Incident.status != "resolved"))
            if existing:
                return self.view(existing), False
            now = time.time()
            i = Incident(id=str(uuid.uuid4()), project_id=project_id, kind=kind, resource=resource, status="detected", created=now, updated=now, data={"evidence": evidence})
            s.add(i)
            return self.view(i), True

    def get(self, incident_id):
        with self.sessions() as s:
            row = s.get(Incident, incident_id)
            if row is None:
                raise KeyError(incident_id)
            return self.view(row)

    def incidents(self):
        with self.sessions() as s:
            return [self.view(i) for i in s.scalars(select(Incident).order_by(Incident.created.desc()))]

    def update(self, incident_id, *, status=None, **data):
        with self.sessions.begin() as s:
            row = s.get(Incident, incident_id)
            if status:
                row.status = status
            row.updated = time.time()
            row.data = {**row.data, **data}

    def record(self, incident_id, stage, payload):
        with self.sessions.begin() as s:
            e = Event(incident_id=incident_id, timestamp=time.time(), stage=stage, payload=payload)
            s.add(e)
            s.flush()
            return e.id

    def events(self, after=0, incident_id=None):
        with self.sessions() as s:
            query = select(Event).where(Event.id > after).order_by(Event.id)
            if incident_id:
                query = query.where(Event.incident_id == incident_id)
            else:
                query = query.limit(1000)
            return [{"id": e.id, "incident_id": e.incident_id, "timestamp": e.timestamp, "stage": e.stage, "payload": e.payload} for e in s.scalars(query)]

    def interrupt_inflight(self):
        for incident in self.incidents():
            if incident["status"] in {"diagnosing", "planning", "executing", "verifying"}:
                self.update(incident["id"], status="escalated", error="Process interrupted; retry reconciles persisted operation keys")
                self.record(incident["id"], "interrupted", {"previous_status": incident["status"]})

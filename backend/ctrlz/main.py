from .settings import Settings
import asyncio
import contextlib
import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from .adapter import ADAPTERS
from .continuation import Continuation
from .engine import Engine
from .demo import DemoControls, DemoRequest
from .demo_targets import repository_target, service_target
from .demo_repository import injected_copy
from .insights import overview
from .intelligence import RepoIntelligence
from .brief import receipt_markdown
from .models import Candidate, ImportRequest, Project
from .repository import RepositoryImports, RepositorySource, inspect_repository, MAX_UPLOAD, PROFILES
from .replay import Replay
from .reasoning import NIMReasoner
from .runbooks import Runbooks
from .store import Store


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approval_hash: str


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: str


class DeclineRequest(Approval):
    reason: str = Field(default="Operator declined the proposed recovery", min_length=1, max_length=500)


class RepositoryDemoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository: str
    scenario: Literal["repair", "injected"]
    request_id: str = Field(min_length=8, max_length=90, pattern=r"^[a-zA-Z0-9_-]+$")
    requirements: str = Field(default="Restore all original acceptance tests without editing tests or weakening behavior.", min_length=10, max_length=20000)
    install_dependencies: bool = False


def create_workspace_app(store=None, client=None, reasoner=None, runbooks=None, monitor=True, workspace_root=None):
    settings = Settings()
    store = store or Store(settings.DATABASE_URL)
    tasks = set()
    own_client = client is None
    client = client or httpx.AsyncClient()
    data_dir = Path(workspace_root) if workspace_root else settings.DATA_DIR
    runbooks = runbooks or Runbooks(settings.RUNBOOK_DIR, data_dir / "chroma")
    engine = Engine(store, client, reasoner or NIMReasoner(), runbooks)
    continuation = Continuation(store, engine.reasoner, (data_dir / "imports") if workspace_root else settings.IMPORT_ROOT, data_dir / "patches", notifier=engine.notify)
    imports = RepositoryImports(continuation.root)
    intelligence = RepoIntelligence(store, client, token="" if workspace_root else None)
    if workspace_root:
        engine.notification_webhook = os.getenv("CTRLZ_USER_" + Path(workspace_root).name.upper() + "_NOTIFICATION_WEBHOOK", "")
    replay = Replay(store)
    demo_controls = DemoControls(store, client)

    def require_code_execution():
        if not settings.CTRLZ_CODE_EXECUTION_ENABLED:
            raise HTTPException(503, 'Repository execution is disabled on this host; use the Docker-capable runner deployment')

    def spawn(coro):
        task = asyncio.create_task(coro)
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    async def scan():
        for config in store.projects():
            project = Project.model_validate(config)
            if not project.enabled:
                continue
            adapter = ADAPTERS[project.adapter](project, client)
            health, workflows = await asyncio.gather(adapter.read("health"), adapter.read("workflows"))
            store.observe(project.id, health, workflows)
            for kind, resource, evidence in adapter.faults(health, workflows):
                incident, created = store.create(project.id, kind, resource, evidence)
                if created:
                    store.record(incident["id"], "detect", evidence)
                    spawn(engine.run(incident["id"]))

    async def monitor_loop():
        while True:
            try:
                await scan()
            except Exception:
                import logging
                logging.getLogger(__name__).exception("Monitor scan failed")
            await asyncio.sleep(settings.MONITOR_INTERVAL)

    @asynccontextmanager
    async def lifespan(app):
        store.interrupt_inflight()
        for incident in store.incidents():
            if incident["status"] == "detected":
                spawn(engine.run(incident["id"]))
        poller = asyncio.create_task(monitor_loop()) if monitor else None
        yield
        if poller:
            poller.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await poller
        for task in list(tasks):
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if own_client:
            await client.aclose()
        store.engine.dispose()

    app = FastAPI(title="CtrlZ Recovery API", version="0.1.0", lifespan=lifespan)
    app.state.store, app.state.engine, app.state.scan, app.state.tasks = store, engine, scan, tasks
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type", "X-Operator-Token", "Last-Event-ID"])

    def auth(request: Request, x_operator_token: str = Header(default="")):
        if getattr(request.state, "principal", None):
            return request.state.principal
        expected = settings.CTRLZ_OPERATOR_TOKEN.get_secret_value()
        if not expected or not secrets.compare_digest(expected, x_operator_token):
            raise HTTPException(401, "Operator token required")

    def get_incident(incident_id):
        try:
            return store.get(incident_id)
        except KeyError:
            raise HTTPException(404, "Incident not found")

    @app.get("/health")
    def health():
        return {"status": "healthy", "nim_configured": bool(settings.NVIDIA_API_KEY.get_secret_value()), "provider": engine.reasoner.provider, "model": getattr(engine.reasoner, "selected_model", None), "demo_controls_enabled": settings.CTRLZ_DEMO_CONTROLS_ENABLED}

    @app.get("/overview", dependencies=[Depends(auth)])
    def insights():
        return overview(store)

    @app.get("/demo/runs", dependencies=[Depends(auth)])
    def demo_runs(target: str | None = None):
        return demo_controls.runs(target)

    @app.get("/demo/targets", dependencies=[Depends(auth)])
    async def demo_targets():
        targets = [service_target(p) for p in store.projects()]
        for path in sorted(continuation.root.glob('repo-*')):
            try:
                repo = await asyncio.to_thread(continuation.repository, str(path))
                metadata = repo/'.git/ctrlz-import.json'
                if metadata.is_file() and json.loads(metadata.read_text()).get('provenance',{}).get('kind') == 'disclosed-injected-regression':
                    continue
                targets.append(await asyncio.to_thread(repository_target, repo))
            except (ValueError, OSError):
                continue
        return targets

    @app.post("/demo/repositories/run", dependencies=[Depends(auth)], status_code=202)
    async def demo_repository_run(body: RepositoryDemoRequest):
        require_code_execution()
        try:
            repo = await asyncio.to_thread(continuation.repository, body.repository)
            target = await asyncio.to_thread(repository_target, repo)
            scenario = next(s for s in target['scenarios'] if s['id'] == body.scenario)
            if scenario['disabled_reason']:
                raise ValueError(scenario['disabled_reason'])
            if target['facts']['dependency_install_required'] and not body.install_dependencies:
                raise ValueError('Approve isolated dependency setup first')
            run, created = store.demo_start(body.request_id, str(repo), body.scenario)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        if created:
            spawn(run_repository_demo(body, repo))
        return run

    async def run_repository_demo(body, repo):
        incident = None
        try:
            incident, created = store.create('demo-repository', 'code', body.request_id, {'repository':str(repo), 'scenario':body.scenario})
            store.record(incident['id'], 'detect', {'explicit_demo':True,'scenario':body.scenario,'repository':str(repo)})
            store.demo_finish(body.request_id, {'status':'running','incident_id':incident['id']})
            repository = str(repo)
            if body.scenario == 'injected':
                store.update(incident['id'], status='diagnosing', injected_regression={'disclosed':True,'original_repository':str(repo),'proven':False})
                snapshot, disclosure = await injected_copy(repo, imports, body.install_dependencies, lambda stage,payload:store.record(incident['id'],stage,payload))
                repository = snapshot['repository']
                store.update(incident['id'], injected_regression={**disclosure,'proven':True})
                store.record(incident['id'], 'injected_regression', disclosure)
            request = ImportRequest(repository=repository, requirements=body.requirements, context='Demo Lab: '+('DISCLOSED INJECTED REGRESSION. Repair the mutated copy only.' if body.scenario == 'injected' else 'Repair the selected imported snapshot; existing immutable acceptance tests govern success.'), install_dependencies=body.install_dependencies)
            store.update(incident['id'], import_request=request.model_dump())
            await continuation.run(incident['id'], request)
            store.demo_finish(body.request_id, {'status':store.get(incident['id'])['status'],'incident_id':incident['id']})
        except Exception as exc:
            message = str(exc)[:600] if isinstance(exc,(ValueError,RuntimeError)) else 'Sandbox setup failed; inspect the recorded evidence.'
            if incident:
                store.update(incident['id'], status='blocked', error=message)
                store.record(incident['id'], 'demo_setup_failed', {'message':message})
            store.demo_finish(body.request_id, {'status':'failed','message':message,'incident_id':incident['id'] if incident else None})

    @app.post("/demo/projects/{project_id}/run", dependencies=[Depends(auth)])
    async def demo_run(project_id: str, body: DemoRequest):
        return await demo_controls.run(project_id, body)

    @app.get("/projects", dependencies=[Depends(auth)])
    def projects():
        return store.projects()

    @app.post("/projects", dependencies=[Depends(auth)])
    def project(body: Project, request: Request):
        principal = getattr(request.state, "principal", None)
        if principal and principal['role'] != 'admin':
            if body.adapter != 'generic-http-v1':
                raise HTTPException(403, 'Demonstration presets require an administrator')
            body.token_env = 'CTRLZ_USER_' + principal['id'].upper() + '_RECOVERY_TOKEN'
        store.save_project(body.model_dump())
        return body

    @app.get("/incidents", dependencies=[Depends(auth)])
    def incidents():
        return store.incidents()

    @app.get("/incidents/{incident_id}", dependencies=[Depends(auth)])
    def incident(incident_id: str):
        return get_incident(incident_id)

    @app.get("/incidents/{incident_id}/receipt", dependencies=[Depends(auth)])
    def receipt(incident_id: str):
        get_incident(incident_id)
        return engine.receipt(incident_id)

    @app.get("/incidents/{incident_id}/brief", dependencies=[Depends(auth)])
    def brief(incident_id: str):
        get_incident(incident_id)
        return PlainTextResponse(receipt_markdown(engine.receipt(incident_id)), media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="ctrlz-{incident_id}.md"'})

    @app.post("/incidents/{incident_id}/approve", dependencies=[Depends(auth)])
    async def approve(incident_id: str, body: Approval):
        get_incident(incident_id)
        try:
            await engine.approve(incident_id, body.approval_hash)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return store.get(incident_id)

    @app.post("/incidents/{incident_id}/decline", dependencies=[Depends(auth)])
    async def decline(incident_id: str, body: DeclineRequest):
        get_incident(incident_id)
        try:
            await engine.decline(incident_id, body.approval_hash, body.reason)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return store.get(incident_id)

    @app.post("/incidents/{incident_id}/retry", dependencies=[Depends(auth)])
    async def retry(incident_id: str):
        incident = get_incident(incident_id)
        if incident["status"] not in {"blocked", "escalated"}:
            raise HTTPException(409, "Only blocked or escalated incidents can retry")
        if incident["kind"] == "code":
            require_code_execution()
        store.update(incident_id, status="detected")
        store.record(incident_id, "retry", {"operator_requested": True})
        if incident["kind"] == "code":
            require_code_execution()
            spawn(continuation.run(incident_id, ImportRequest.model_validate(incident["import_request"])))
        else:
            spawn(engine.run(incident_id))
        return {"queued": True}

    @app.get("/runtime", dependencies=[Depends(auth)])
    async def runtime():
        from .runtime import inspect_runtime
        webhook = getattr(engine, "notification_webhook", settings.NOTIFICATION_WEBHOOK_URL.get_secret_value())
        return await asyncio.to_thread(inspect_runtime, settings, store, runbooks, engine.reasoner, webhook)

    @app.get("/capabilities", dependencies=[Depends(auth)])
    def capabilities():
        return {"code_execution_enabled": settings.CTRLZ_CODE_EXECUTION_ENABLED, "sources": ["github", "zip", "local"], "profiles": {key:{"label":value["label"],"image":value["image"]} for key,value in PROFILES.items()}, "maximum_upload_bytes": MAX_UPLOAD, "maximum_attempts": 3, "generic_http": True, "dependency_setup": "Explicit approval; npm scripts disabled / Python wheels only; tests offline", "publishes_changes": False}

    @app.post("/repositories/import", dependencies=[Depends(auth)], status_code=201)
    async def import_repository(body: RepositorySource, request: Request):
        principal = getattr(request.state, "principal", None)
        if principal and principal["role"] != "admin" and body.kind == "local":
            raise HTTPException(403, "Upload a ZIP or connect GitHub; server-folder imports require an administrator")
        try:
            return await asyncio.to_thread(imports.import_source, body)
        except (ValueError, RuntimeError, OSError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/repositories/upload", dependencies=[Depends(auth)], status_code=201)
    async def upload_repository(request: Request):
        contents = bytearray()
        async for chunk in request.stream():
            contents.extend(chunk)
            if len(contents) > MAX_UPLOAD:
                raise HTTPException(413, "ZIP upload exceeds 25 MiB")
        try:
            return await asyncio.to_thread(imports.import_zip, bytes(contents))
        except Exception as exc:
            raise HTTPException(422, "Invalid ZIP snapshot: "+str(exc)[:400]) from exc

    @app.get("/repositories/intelligence", dependencies=[Depends(auth)])
    async def repository_intelligence(repository: str, refresh: bool = False):
        try:
            return await intelligence.scan(repository, refresh)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/repositories/inspect", dependencies=[Depends(auth)])
    async def inspect_snapshot(repository: str, profile: str = "auto"):
        if profile != "auto" and profile not in PROFILES:
            raise HTTPException(422, "Unknown test profile")
        try:
            repo = await asyncio.to_thread(continuation.repository, repository)
            return await asyncio.to_thread(inspect_repository, repo, profile)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/continuations", dependencies=[Depends(auth)], status_code=202)
    async def import_code(body: ImportRequest):
        require_code_execution()
        try:
            repo = await asyncio.to_thread(continuation.repository, body.repository)
            assessment = await asyncio.to_thread(inspect_repository, repo, body.acceptance_profile)
            if not assessment['supported']:
                raise ValueError('; '.join(assessment['warnings']))
            if assessment['dependency_install_required'] and not body.install_dependencies:
                raise ValueError('Approve isolated dependency setup before starting this repair')
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        incident, created = store.create("code-import", "code", str(repo), {"requirements": body.requirements, "context": body.context})
        if created:
            store.update(incident["id"], import_request=body.model_dump())
            store.record(incident["id"], "detect", {"explicit_import": True, "repository": str(repo)})
            spawn(continuation.run(incident["id"], body))
        return store.get(incident["id"])

    @app.post("/incidents/{incident_id}/replay", dependencies=[Depends(auth)], status_code=202)
    async def replay_candidate(incident_id: str, body: ReplayRequest):
        require_code_execution()
        incident = get_incident(incident_id)
        if incident["kind"] == "code" or store.project(incident["project_id"]).get("adapter") != "campuspass-v1":
            raise HTTPException(422, "Replay is available only for the explicit CampusPass demonstration fixture")
        candidates = incident.get("plan", {}).get("candidates", [])
        candidate = next((c for c in candidates if c["id"] == body.candidate_id), None)
        if not candidate or incident["kind"] not in {"outage", "workflow"}:
            raise HTTPException(422, "Unknown candidate or unsupported fixture")
        spawn(replay.run(incident_id, Candidate.model_validate(candidate)))
        return {"queued": True, "candidate_id": body.candidate_id}

    @app.get("/events", dependencies=[Depends(auth)])
    async def events(request: Request, after: int = 0, last_event_id: str = Header(default="0")):
        try:
            cursor = max(after, int(last_event_id))
        except ValueError:
            raise HTTPException(422, "Invalid event cursor")

        async def stream():
            nonlocal cursor
            while not await request.is_disconnected():
                validator = getattr(request.state, 'validate_session', None)
                if validator:
                    try: validator()
                    except HTTPException: break
                rows = store.events(cursor)
                for event in rows:
                    cursor = event["id"]
                    yield f"id: {cursor}\nevent: recovery\ndata: {json.dumps(event)}\n\n"
                if not rows:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(1)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return app


def create_app(store=None, client=None, reasoner=None, runbooks=None, monitor=True):
    if store is not None:
        return create_workspace_app(store, client, reasoner, runbooks, monitor)
    from .access import create_account_app
    return create_account_app(client=client, reasoner=reasoner, runbooks=runbooks, monitor=monitor)

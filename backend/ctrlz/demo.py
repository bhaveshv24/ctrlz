"""Operator-only fault setup, deliberately separate from autonomous recovery decisions."""
import os
from typing import Literal
from fastapi import HTTPException
from pydantic import Field
from .adapter import CampusPassAdapter
from .models import Project, Strict


class DemoRequest(Strict):
    request_id: str = Field(min_length=8, max_length=90, pattern=r"^[a-zA-Z0-9_-]+$")
    scenario: Literal["outage", "workflow", "worker_defect", "reset"]


class DemoControls:
    def __init__(self, store, client):
        self.store, self.client = store, client

    async def run(self, project_id, request: DemoRequest):
        if os.getenv("CTRLZ_DEMO_CONTROLS_ENABLED", "false").lower() != "true":
            raise HTTPException(403, "Demo controls are disabled in this environment")
        try:
            project = Project.model_validate(self.store.project(project_id))
        except KeyError:
            raise HTTPException(404, "Project not found")
        if not project.demo_enabled or project.adapter != "campuspass-v1":
            raise HTTPException(403, "This project has not opted into controlled demo faults")
        if not project.enabled and request.scenario != "reset":
            raise HTTPException(409, "Enable monitoring before starting a scenario")
        try:
            run, created = self.store.demo_start(request.request_id, project_id, request.scenario)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        if not created:
            return run
        adapter = CampusPassAdapter(project, self.client)
        faults = {"outage": "checkout_outage", "workflow": "worker_paused", "worker_defect": "worker_defect", "reset": "none"}
        result = {"status": "failed", "message": "Setup not completed; inspect the target before creating a new run"}
        try:
            response = await self.client.post(project.base_url + "/demo/fault", headers=adapter.headers, json={"fault": faults[request.scenario]}, timeout=10, follow_redirects=False)
            response.raise_for_status()
            result = {"status": "injected", "fault": faults[request.scenario], "revision": response.json()["revision"], "message": "Waiting for the independent monitor; no recovery decision was scripted"}
            if request.scenario in {"workflow", "worker_defect"}:
                response = await self.client.post(project.base_url + "/checkout", json={"event_id": "agentathon", "email": "rehearsal@example.com", "request_id": "demo-" + request.request_id}, timeout=10, follow_redirects=False)
                response.raise_for_status()
                result["order_id"] = response.json()["id"]
            if request.scenario == "reset":
                result["message"] = "Injected fault cleared; orders and incident history preserved"
            return {**run, **result}
        except Exception as exc:
            result = {"status": "failed", "error_type": type(exc).__name__, "message": "Target rejected the setup or the result is uncertain. Check its state; this request will not be blindly repeated."}
            raise HTTPException(502, result["message"]) from exc
        finally:
            self.store.demo_finish(request.request_id, result)

    def runs(self, project_id=None):
        incidents = self.store.incidents()
        rows = self.store.demo_runs(project_id)
        for run in rows:
            if run.get("incident_id") or run["scenario"] in {"repair", "injected"}:
                incident = next((i for i in incidents if i["id"] == run.get("incident_id")), None)
                run["incident_status"] = incident["status"] if incident else None
                continue
            kind = "outage" if run["scenario"] == "outage" else "workflow"
            resource = run.get("order_id", "service")
            match = next((i for i in incidents if i["project_id"] == run["project_id"] and i["kind"] == kind and i["resource"] == resource and i["created"] >= run["created"]), None)
            run["incident_id"] = match["id"] if match else None
            run["incident_status"] = match["status"] if match else None
        return rows

import asyncio
import hashlib
import json
import uuid
from urllib.parse import urlsplit
from .settings import Settings
from .adapter import ADAPTERS
from .models import Candidate, Project, RecoveryPlan
from .reasoning import ReasoningUnavailable
from .safety import evaluate, tournament


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class Engine:
    def __init__(self, store, client, reasoner, runbooks):
        self.store, self.client, self.reasoner, self.runbooks = store, client, reasoner, runbooks
        self.locks = {}

    def adapter(self, incident):
        project = Project.model_validate(self.store.project(incident["project_id"]))
        return ADAPTERS[project.adapter](project, self.client)

    @staticmethod
    def reasoning_context(incident):
        return {key: incident[key] for key in ["id", "project_id", "kind", "resource", "evidence", "created"] if key in incident}

    async def run(self, incident_id):
        lock = self.locks.setdefault(incident_id, asyncio.Lock())
        async with lock:
            incident = self.store.get(incident_id)
            if incident["status"] in {"resolved", "awaiting_approval"}:
                return
            if incident["kind"] == "code":
                return
            if incident["kind"] == "runtime":
                await self.runtime_monitor.investigate(incident_id)
                return
            try:
                # An earlier operation could have succeeded before its result was persisted.
                if incident.get("operation_intents"):
                    verification = await self.adapter(incident).verify(incident["kind"], incident["resource"])
                    self.store.record(incident_id, "reconciliation", verification)
                    if verification["passed"]:
                        await self.finish(incident_id, verification)
                        return
                from .flow import RecoveryFlow
                await RecoveryFlow(self, incident_id).kickoff_async()
            except ReasoningUnavailable as exc:
                self.store.update(incident_id, status="blocked", error=str(exc))
                self.store.record(incident_id, "blocked", {"reason": str(exc)})
            except Exception as exc:
                # Persist safe error type; credentials and HTTP request headers never recorded.
                self.store.update(incident_id, status="escalated", error=f"Recovery failed: {type(exc).__name__}: {str(exc)[:300]}")
                self.store.record(incident_id, "escalated", {"error_type": type(exc).__name__})

    async def diagnose(self, incident_id):
        incident = self.store.get(incident_id)
        self.store.update(incident_id, status="diagnosing", error=None, reasoning_provider=self.reasoner.provider, model=getattr(self.reasoner, "selected_model", None))
        self.store.record(incident_id, "diagnose", {"provider": self.reasoner.provider, "model": getattr(self.reasoner, "selected_model", None)})
        diagnosis = await self.reasoner.diagnose(self.reasoning_context(incident), self.adapter(incident), self.store, self.runbooks)
        self.store.record(incident_id, "diagnosis", {"text": diagnosis})
        self.store.update(incident_id, diagnosis=diagnosis)
        return diagnosis

    async def plan(self, incident_id, diagnosis, feedback=None):
        incident = self.store.get(incident_id)
        self.store.update(incident_id, status="planning")
        plan = await self.reasoner.plan(self.reasoning_context(incident), diagnosis, self.adapter(incident), self.store, self.runbooks, feedback=feedback)
        if len({c.id for c in plan.candidates}) != len(plan.candidates):
            raise ValueError("Candidate IDs must be unique")
        self.store.update(incident_id, plan=plan.model_dump())
        self.store.record(incident_id, "plan", plan.model_dump())
        return plan

    async def evaluate_execute(self, incident_id, plan: RecoveryPlan, revision=0):
        incident = self.store.get(incident_id)
        adapter = self.adapter(incident)
        diagnostics = await adapter.read("diagnostics")
        self.store.record(incident_id, "precondition_evidence", diagnostics)
        results, selected = tournament(plan.candidates, adapter.project, diagnostics, adapter, incident["resource"])
        self.store.record(incident_id, "tournament", {"results": results, "selection_rule": "eligible, no approval, fewer actions, stable ID"})
        self.store.update(incident_id, tournament=results)
        if not selected:
            if revision < 1:
                self.store.record(incident_id, "plan_revision", {"attempt": revision+1, "rejection_feedback": results})
                updated = await self.plan(incident_id, incident.get("diagnosis", plan.diagnosis), feedback=results)
                return await self.evaluate_execute(incident_id, updated, revision=revision+1)
            self.store.update(incident_id, status="escalated", error="No eligible strategy; new evidence or code repair required")
            return
        decision = next(r for r in results if r["candidate_id"] == selected.id)
        self.store.update(incident_id, selected=selected.model_dump())
        if decision["approval_required"]:
            approval_revision = adapter.revision(diagnostics)
            approval_hash = fingerprint({"incident_id": incident_id, "candidate": selected.model_dump(), "project": adapter.project.model_dump(), "revision": approval_revision})
            self.store.update(incident_id, status="awaiting_approval", approval_hash=approval_hash, approval_revision=approval_revision)
            self.store.record(incident_id, "approval_required", {"candidate": selected.id, "approval_hash": approval_hash})
            return
        await self.execute(incident_id, selected, approved=False)

    async def approve(self, incident_id, approval_hash):
        async with self.locks.setdefault(incident_id, asyncio.Lock()):
            incident = self.store.get(incident_id)
            if incident["status"] != "awaiting_approval" or incident.get("approval_hash") != approval_hash:
                raise ValueError("Approval does not match pending plan")
            candidate = Candidate.model_validate(incident["selected"])
            project = self.adapter(incident).project
            if fingerprint({"incident_id": incident_id, "candidate": candidate.model_dump(), "project": project.model_dump(), "revision": incident.get("approval_revision")}) != approval_hash:
                raise ValueError("Plan or contract changed; replan before approval")
            self.store.record(incident_id, "authorized", {"candidate": candidate.id, "approval_hash": approval_hash})
            try:
                await self.execute(incident_id, candidate, approved=True)
            except Exception as exc:
                self.store.update(incident_id, status="escalated", error=f"Approved execution failed: {type(exc).__name__}")
                self.store.record(incident_id, "escalated", {"error_type": type(exc).__name__})

    async def decline(self, incident_id, approval_hash, reason):
        async with self.locks.setdefault(incident_id, asyncio.Lock()):
            incident = self.store.get(incident_id)
            if incident["status"] != "awaiting_approval" or incident.get("approval_hash") != approval_hash:
                raise ValueError("Decision does not match the pending plan")
            self.store.update(incident_id, status="escalated", error="Operator declined recovery: " + reason)
            self.store.record(incident_id, "approval_declined", {"approval_hash": approval_hash, "reason": reason})

    async def execute(self, incident_id, candidate, approved):
        incident = self.store.get(incident_id)
        adapter = self.adapter(incident)
        diagnostics = await adapter.read("diagnostics")
        if approved and incident.get("approval_revision") != adapter.revision(diagnostics):
            self.store.update(incident_id, status="escalated", error="Approval is stale; service revision changed. Reinvestigate before authorizing again.")
            self.store.record(incident_id, "approval_stale", {"expected_revision": incident.get("approval_revision"), "observed_revision": adapter.revision(diagnostics)})
            return
        decision = evaluate(candidate, adapter.project, diagnostics, adapter, incident["resource"], approved)
        self.store.record(incident_id, "safety_gate", decision)
        if not decision["eligible"] or decision["approval_required"]:
            self.store.update(incident_id, status="escalated", error="Fresh safety checks rejected execution")
            return
        self.store.update(incident_id, status="executing")
        intents = incident.get("operation_intents", {})
        for index, action in enumerate(candidate.actions):
            # Re-check each action with current remote state, including after a prior action.
            diagnostics = await adapter.read("diagnostics")
            if approved and index == 0 and incident.get("approval_revision") != adapter.revision(diagnostics):
                self.store.update(incident_id, status="escalated", error="Approval is stale; service revision changed before operation intent")
                self.store.record(incident_id, "approval_stale", {"expected_revision": incident.get("approval_revision"), "observed_revision": adapter.revision(diagnostics)})
                return
            single = Candidate(id=candidate.id, rationale=candidate.rationale, actions=[action])
            gate = evaluate(single, adapter.project, diagnostics, adapter, incident["resource"], approved)
            self.store.record(incident_id, "safety_gate", gate)
            if not gate["eligible"] or gate["approval_required"]:
                self.store.update(incident_id, status="escalated", error="Action precondition changed")
                return
            key = fingerprint(action.model_dump())
            if key not in intents:
                intents[key] = {"request_id": str(uuid.uuid4()), "revision": adapter.revision(diagnostics), "action": action.model_dump()}
                self.store.update(incident_id, operation_intents=intents)
                self.store.record(incident_id, "operation_intent", intents[key])
            intent = intents[key]
            result = await adapter.execute(action, intent["request_id"], intent["revision"])
            self.store.record(incident_id, "operation_result", {"action": action.model_dump(), "result": result})
        self.store.update(incident_id, status="verifying")
        verification = await adapter.verify(incident["kind"], incident["resource"])
        await self.finish(incident_id, verification)

    async def finish(self, incident_id, verification):
        self.store.record(incident_id, "verification", verification)
        resolved = verification["passed"]
        self.store.update(incident_id, status="resolved" if resolved else "escalated", verification=verification, remaining_risks=["Mitigation does not establish a permanent code fix."] if resolved else ["Independent acceptance checks failed."])
        self.store.record(incident_id, "record", {"resolved": resolved})
        await self.notify(incident_id)

    async def notify(self, incident_id):
        url = getattr(self, "notification_webhook", None)
        if url is None:
            url = Settings().NOTIFICATION_WEBHOOK_URL.get_secret_value()
        if not url:
            self.store.record(incident_id, "notification", {"delivered": False, "reason": "Webhook not configured"})
            return
        incident = self.store.get(incident_id)
        text = f"CtrlZ · {incident['kind']} · {incident['id']} · {incident['status']}. Independent verification: {incident.get('verification', {}).get('passed')}. Review the recovery receipt for remaining risks."
        payload = {"content": text} if urlsplit(url).hostname in {"discord.com", "discordapp.com"} else {"text": text}
        try:
            response = await self.client.post(url, json=payload, timeout=10, follow_redirects=False)
            self.store.record(incident_id, "notification", {"delivered": response.is_success, "status": response.status_code})
        except Exception as exc:
            self.store.record(incident_id, "notification", {"delivered": False, "error_type": type(exc).__name__})

    def receipt(self, incident_id):
        incident = self.store.get(incident_id)
        receipt = {"schema_version": 1, "incident": incident, "events": self.store.events(incident_id=incident_id), "success": incident["status"] == "resolved" and incident.get("verification", {}).get("passed") is True, "reasoning_provider": incident.get("reasoning_provider", self.reasoner.provider), "model": incident.get("model"), "replay_supported": incident["kind"] != "code" and any(p["id"] == incident["project_id"] and p.get("adapter") == "campuspass-v1" for p in self.store.projects())}
        receipt["integrity"] = {"algorithm": "sha256", "snapshot_digest": fingerprint(receipt), "scope": "Checksum of this JSON snapshot excluding integrity; not a digital signature"}
        return receipt

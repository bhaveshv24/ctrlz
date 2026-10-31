import os
import time
import httpx
from .models import Project
from .http_adapter import HTTPAdapter


class CampusPassAdapter:
    """Business specifics are confined to this explicit, replaceable adapter."""
    def __init__(self, project: Project, client: httpx.AsyncClient):
        self.project, self.client = project, client

    operations = {"restore_checkout", "resume_worker", "retry_order"}
    operation_semantics = {"restore_checkout": "Restore a confirmed checkout fault; no order_id", "resume_worker": "Resume only an interrupted worker; no order_id; requires approval", "retry_order": "Idempotently continue the incident order; order_id required", "force_issue_ticket": "Prohibited duplicate-prone counterexample"}

    @staticmethod
    def action_parameters(action):
        return action.order_id

    def validate_action(self, action):
        return not action.parameters and (action.operation == "retry_order") == (action.order_id is not None)

    def needs_approval(self, operation):
        return operation == "resume_worker"

    @staticmethod
    def revision(diagnostics):
        return diagnostics.get("body", {}).get("revision")

    @property
    def headers(self):
        return {"X-Recovery-Token": os.getenv(self.project.token_env, "")}

    async def read(self, name, order_id=None):
        paths = {"health": "/health", "diagnostics": "/diagnostics", "workflows": "/workflows"}
        if name in {"order", "ticket"}:
            from uuid import UUID
            UUID(order_id)
            path = f"/orders/{order_id}" if name == "order" else f"/tickets/{order_id}/verify"
        else:
            path = paths[name]
        start = time.monotonic()
        try:
            response = await self.client.get(self.project.base_url + path, headers=self.headers, timeout=self.project.timeout_seconds, follow_redirects=False)
            elapsed = round((time.monotonic() - start) * 1000, 2)
            try:
                body = response.json()
            except ValueError:
                body = {"error": "Non-JSON response"}
            result = {"ok": response.is_success, "status": response.status_code, "latency_ms": elapsed, "body": body, "configured": True}
            if name == "health":
                result["accepted"] = response.is_success and body.get("checkout_available") is True and elapsed <= self.project.latency_ms
            return result
        except httpx.HTTPError as exc:
            return {"ok": False, "latency_ms": round((time.monotonic()-start)*1000, 2), "error": type(exc).__name__, "body": {}}

    def faults(self, health, workflows):
        if not health["ok"] or health["latency_ms"] > self.project.latency_ms or health["body"].get("checkout_available") is not True:
            yield "outage", "service", {"health": health}
        if workflows["ok"]:
            for order in workflows["body"].get("discrepancies", []):
                if order.get("payment") == "paid":
                    yield "workflow", order["id"], {"workflow": order}

    @staticmethod
    def precondition(operation, diagnostics, order_id, resource):
        if not diagnostics["ok"] or "revision" not in diagnostics["body"]:
            return False, "No fresh authenticated diagnostics/revision"
        fault = diagnostics["body"].get("fault")
        if operation == "restore_checkout":
            return resource == "service" and fault in {"checkout_outage", "checkout_slow"}, "Service incident and faulted checkout circuit required"
        if operation == "resume_worker":
            return resource != "service" and fault == "worker_paused", "Workflow incident and paused worker required; code defects cannot be cleared"
        if operation == "retry_order":
            return fault == "none" and order_id == resource, "Worker must be ready and order must match incident"
        return False, "No adapter precondition for operation"

    async def execute(self, action, request_id, revision):
        response = await self.client.post(self.project.base_url + "/operations/" + action.operation, headers=self.headers, json={"request_id": request_id, "expected_revision": revision, "order_id": action.order_id}, timeout=10, follow_redirects=False)
        response.raise_for_status()
        return response.json()

    async def verify(self, kind, resource):
        if kind == "workflow":
            result = await self.read("order", resource)
            body = result["body"]
            tickets = body.get("tickets", [])
            checks = {"order_read": result["ok"], "correct_order": body.get("id") == resource, "payment_paid": body.get("payment") == "paid", "exactly_one_ticket": len(tickets) == 1, "valid_entitlement": len(tickets) == 1 and tickets[0].get("valid") is True, "job_completed": body.get("job") == "done"}
            ticket_verification = None
            if len(tickets) == 1 and tickets[0].get("id"):
                ticket_verification = await self.read("ticket", tickets[0]["id"])
            checks["ticket_verified_by_application"] = bool(ticket_verification and ticket_verification["ok"] and ticket_verification["body"].get("valid") is True and ticket_verification["body"].get("ticket_id") == tickets[0]["id"])
            return {"passed": all(checks.values()), "checks": checks, "evidence": result, "ticket_verification": ticket_verification}
        observations = []
        import asyncio
        for _ in range(3):
            result = await self.read("health")
            observations.append(result)
            await asyncio.sleep(0.1)
        checks = {"three_healthy_observations": all(r["ok"] and r["body"].get("checkout_available") is True for r in observations), "latency_within_contract": all(r["latency_ms"] <= self.project.latency_ms for r in observations)}
        return {"passed": all(checks.values()), "checks": checks, "evidence": observations}


ADAPTERS = {"generic-http-v1": HTTPAdapter, "campuspass-v1": CampusPassAdapter}

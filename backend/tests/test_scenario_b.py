"""Scenario B regressions; deterministic fixtures are not live AI evidence."""
import uuid

import httpx
import pytest

from ctrlz.adapter import CampusPassAdapter
from ctrlz.engine import Engine
from ctrlz.models import Action, Candidate, RecoveryPlan
from ctrlz.presets import campuspass_project
from test_core import EmptyRunbooks, TestReasoner, campus, store


async def pending_orders(store, campus, client):
    store.save_project(campuspass_project(id="demo", name="Campus", base_url=campus).model_dump())
    await client.post(campus + "/demo/fault", headers={"X-Recovery-Token": "test-recovery"}, json={"fault": "worker_paused"})
    engine = Engine(store, client, TestReasoner(), EmptyRunbooks())
    incidents = []
    for _ in range(2):
        order = (await client.post(campus + "/checkout", json={"event_id": "agentathon", "email": "student@example.com", "request_id": str(uuid.uuid4())})).json()
        incident, _ = store.create("demo", "workflow", order["id"], {})
        await engine.run(incident["id"])
        incidents.append(store.get(incident["id"]))
    return engine, incidents


async def test_approval_cannot_cross_incidents_with_identical_candidates(store, campus):
    async with httpx.AsyncClient() as client:
        engine, (first, second) = await pending_orders(store, campus, client)
        assert first["selected"] == second["selected"]
        assert first["approval_hash"] != second["approval_hash"]
        with pytest.raises(ValueError):
            await engine.approve(second["id"], first["approval_hash"])
        assert not (await client.get(campus + "/orders/" + second["resource"])).json()["tickets"]


async def test_revision_change_invalidates_approval_even_if_worker_paused_again(store, campus):
    async with httpx.AsyncClient() as client:
        engine, (first, _) = await pending_orders(store, campus, client)
        for fault in ["none", "worker_paused"]:
            await client.post(campus + "/demo/fault", headers={"X-Recovery-Token": "test-recovery"}, json={"fault": fault})
        await engine.approve(first["id"], first["approval_hash"])
        result = store.get(first["id"])
        assert result["status"] == "escalated"
        assert "stale" in result["error"]
        assert not any(e["stage"] == "operation_intent" for e in store.events(incident_id=first["id"]))
        assert not (await client.get(campus + "/orders/" + first["resource"])).json()["tickets"]


async def test_revision_race_before_operation_intent_is_rejected(store, campus, monkeypatch):
    async with httpx.AsyncClient() as client:
        engine, (first, _) = await pending_orders(store, campus, client)
        adapter = engine.adapter(first)
        original_read = adapter.read
        changed = False

        async def changing_read(name, order_id=None):
            nonlocal changed
            result = await original_read(name, order_id)
            if name == "diagnostics" and not changed:
                changed = True
                await client.post(campus + "/demo/fault", headers={"X-Recovery-Token": "test-recovery"}, json={"fault": "worker_paused"})
            return result

        monkeypatch.setattr(adapter, "read", changing_read)
        monkeypatch.setattr(engine, "adapter", lambda incident: adapter)
        await engine.approve(first["id"], first["approval_hash"])
        assert store.get(first["id"])["status"] == "escalated"
        assert not any(e["stage"] == "operation_intent" for e in store.events(incident_id=first["id"]))
        assert not (await client.get(campus + "/orders/" + first["resource"])).json()["tickets"]


@pytest.mark.parametrize("wrong_order,valid_ticket", [(True, True), (False, False), (False, True)])
async def test_verification_checks_order_identity_and_application_ticket(wrong_order, valid_ticket):
    order_id, ticket_id = str(uuid.uuid4()), str(uuid.uuid4())
    paths = []

    def respond(request):
        paths.append(request.url.path)
        if request.url.path.startswith("/orders/"):
            return httpx.Response(200, json={"id": str(uuid.uuid4()) if wrong_order else order_id, "payment": "paid", "job": "done", "tickets": [{"id": ticket_id, "valid": True}]})
        return httpx.Response(200, json={"ticket_id": ticket_id, "valid": valid_ticket})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        adapter = CampusPassAdapter(campuspass_project(id="demo", name="Campus", base_url="http://campus.test"), client)
        result = await adapter.verify("workflow", order_id)
    assert result["passed"] == (not wrong_order and valid_ticket)
    assert paths == [f"/orders/{order_id}", f"/tickets/{ticket_id}/verify"]


async def test_defect_is_escalated_without_operational_mutation(store, campus):
    async with httpx.AsyncClient() as client:
        engine, (first, _) = await pending_orders(store, campus, client)
        await client.post(campus + "/demo/fault", headers={"X-Recovery-Token": "test-recovery"}, json={"fault": "worker_defect"})
        store.update(first["id"], status="detected")
        await engine.run(first["id"])
        result = store.get(first["id"])
        assert result["status"] == "escalated"
        assert not any(e["stage"] == "operation_intent" for e in store.events(incident_id=first["id"]))

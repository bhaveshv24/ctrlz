import httpx
import pytest
from ctrlz.brief import receipt_markdown
from ctrlz.engine import Engine, fingerprint
from ctrlz.insights import overview
from ctrlz.main import create_app
from ctrlz.presets import campuspass_project as Project
from test_core import campus, store, EmptyRunbooks, TestReasoner


def observations(healthy=True, workflows=True, missing=None):
    return {"ok": healthy, "latency_ms": 42, "body": {"checkout_available": healthy}}, {"ok": workflows, "latency_ms": 5, "body": {"discrepancies": missing or []}}


def test_probe_history_is_bounded_and_unknown_business_state_is_not_healthy(store):
    store.save_project(Project(id="demo", name="Demo", base_url="http://localhost:8001").model_dump())
    assert overview(store)["projects"][0]["state"] == "unknown"
    for _ in range(125):
        store.observe("demo", *observations(workflows=False))
    assert len(store.probes("demo")) == 120
    assert overview(store)["projects"][0]["state"] == "partial"
    store.observe("demo", *observations(missing=[{"id": "paid-order"}]))
    assert overview(store)["projects"][0]["state"] == "attention"
    store.observe("demo", *observations(healthy=False))
    assert overview(store)["projects"][0]["state"] == "disrupted"


def test_recovery_metrics_use_verified_event_time_not_later_receipt_or_replay(store, monkeypatch):
    current = [100.0]
    monkeypatch.setattr("ctrlz.store.time.time", lambda: current[0])
    incident, _ = store.create("demo", "outage", "service", {})
    current[0] = 110.0
    store.record(incident["id"], "verification", {"passed": True})
    store.record(incident["id"], "tournament", {"results": [{"eligible": False}, {"eligible": True}]})
    store.update(incident["id"], status="resolved", verification={"passed": True})
    current[0] = 500.0
    store.record(incident["id"], "replay_result", {"verification": {"passed": True}})
    store.update(incident["id"], remaining_risks=["mitigation"])
    other, _ = store.create("demo", "workflow", "order", {})
    store.update(other["id"], status="resolved", verification={"passed": False})
    result = overview(store)["summary"]
    assert result["verified_recoveries"] == 1
    assert result["median_recovery_seconds"] == 10
    assert result["rejected_evaluations"] == 1
    assert result["verified_workflows"] == 0


def test_receipt_checksum_and_success_cannot_be_asserted_without_verification(store):
    incident, _ = store.create("demo", "outage", "service", {})
    store.update(incident["id"], status="resolved", verification={"passed": False, "checks": {"healthy": False}})
    engine = Engine(store, None, TestReasoner(), EmptyRunbooks())
    receipt = engine.receipt(incident["id"])
    assert receipt["success"] is False
    checksum = receipt.pop("integrity")["snapshot_digest"]
    assert fingerprint(receipt) == checksum
    receipt["success"] = True
    assert fingerprint(receipt) != checksum
    markdown = receipt_markdown(engine.receipt(incident["id"]))
    assert "FAIL: healthy" in markdown and "not a digital signature" in markdown


async def test_demo_controls_auth_opt_in_idempotency_and_autonomous_detection(store, campus, monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CTRLZ_OPERATOR_TOKEN", "operator")
    monkeypatch.delenv("CTRLZ_DEMO_CONTROLS_ENABLED", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    project = Project(id="demo", name="Demo", base_url=campus)
    store.save_project(project.model_dump())
    async with httpx.AsyncClient() as remote:
        app = create_app(store, remote, runbooks=EmptyRunbooks(), monitor=False)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ctrlz") as api:
            body = {"request_id": "rehearsal-request", "scenario": "workflow"}
            assert (await api.get("/overview")).status_code == 401
            assert (await api.post("/demo/projects/demo/run", json=body)).status_code == 401
            api.headers["X-Operator-Token"] = "operator"
            assert (await api.post("/demo/projects/demo/run", json=body)).status_code == 403
            monkeypatch.setenv("CTRLZ_DEMO_CONTROLS_ENABLED", "true")
            assert (await api.post("/demo/projects/demo/run", json=body)).status_code == 403
            project.demo_enabled = True
            store.save_project(project.model_dump())
            first = await api.post("/demo/projects/demo/run", json=body)
            second = await api.post("/demo/projects/demo/run", json=body)
            assert first.status_code == second.status_code == 200
            assert first.json()["order_id"] == second.json()["order_id"]
            assert not store.incidents(), "Fault setup must not script an incident or recovery"
            assert (await api.post("/demo/projects/demo/run", json={**body, "scenario": "outage"})).status_code == 409
            import asyncio
            await asyncio.sleep(1.1)
            await app.state.scan()
            await asyncio.gather(*app.state.tasks)
            runs = (await api.get("/demo/runs")).json()
            assert runs[0]["incident_id"] == store.incidents()[0]["id"]
            assert store.incidents()[0]["status"] == "blocked", "No NIM credential means no simulated recovery"
            assert (await api.get("/overview")).json()["projects"][0]["state"] == "attention"


async def test_operator_can_decline_exact_pending_recovery_without_execution(store, campus):
    async with httpx.AsyncClient() as client:
        store.save_project(Project(id="demo", name="Campus", base_url=campus).model_dump())
        await client.post(campus + "/demo/fault", headers={"X-Recovery-Token": "test-recovery"}, json={"fault": "worker_paused"})
        order = (await client.post(campus + "/checkout", json={"event_id": "agentathon", "email": "decline@example.com", "request_id": "declined-order-request"})).json()["id"]
        incident, _ = store.create("demo", "workflow", order, {})
        engine = Engine(store, client, TestReasoner(), EmptyRunbooks())
        await engine.run(incident["id"])
        pending = store.get(incident["id"])
        assert pending["status"] == "awaiting_approval"
        with pytest.raises(ValueError):
            await engine.decline(incident["id"], "outdated-hash", "No")
        await engine.decline(incident["id"], pending["approval_hash"], "Need further investigation")
        assert store.get(incident["id"])["status"] == "escalated"
        assert not any(e["stage"] == "operation_result" for e in store.events())
        assert not (await client.get(campus + "/orders/" + order)).json()["tickets"]

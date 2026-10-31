import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
import httpx
import pytest
from ctrlz.adapter import CampusPassAdapter
from ctrlz.continuation import validate_path
from ctrlz.engine import Engine
from ctrlz.main import create_app
from ctrlz.models import Action, Candidate, RecoveryPlan
from ctrlz.presets import campuspass_project as Project
from ctrlz.reasoning import NIMReasoner, ReasoningUnavailable
from ctrlz.safety import evaluate, tournament
from ctrlz.store import Store


class TestReasoner:
    __test__ = False
    provider = "explicit test fixture (no live AI)"

    async def diagnose(self, incident, adapter, store, runbooks):
        result = await adapter.read("diagnostics")
        store.record(incident["id"], "tool_result", {"tool": "diagnostics", "result": result})
        return "Test fixture observes " + result["body"].get("fault", "unknown")

    async def plan(self, incident, diagnosis, adapter, store, runbooks, feedback=None):
        diagnostics = await adapter.read("diagnostics")
        fault = diagnostics["body"].get("fault")
        operation = "restore_checkout" if incident["kind"] == "outage" else "resume_worker" if fault == "worker_paused" else "retry_order"
        action = Action(operation=operation, order_id=incident["resource"] if operation == "retry_order" else None)
        return RecoveryPlan(diagnosis=diagnosis, candidates=[Candidate(id="safe", rationale="Test recovery", actions=[action]), Candidate(id="unsafe", rationale="Unsafe strategy must be blocked", actions=[Action(operation="force_issue_ticket")])])


class EmptyRunbooks:
    def search(self, query):
        return []


@pytest.fixture
def store(tmp_path):
    result = Store(f"sqlite:///{tmp_path}/ctrlz.db")
    yield result
    result.engine.dispose()


@pytest.fixture
def campus(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[3] / "campuspass" / "backend"
    if not source.exists():
        pytest.skip("Cross-repository test requires sibling campuspass checkout")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "PYTHONPATH": str(source), "DATABASE_URL": f"sqlite:///{tmp_path}/campus.db", "RECOVERY_TOKEN": "test-recovery", "DEMO_MODE": "true"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "campuspass.main:create_app", "--factory", "--host", "127.0.0.1", "--port", str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(base + "/health").status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.05)
    else:
        proc.terminate()
        raise RuntimeError(proc.communicate(timeout=10)[1].decode())
    monkeypatch.setenv("CAMPUSPASS_RECOVERY_TOKEN", "test-recovery")
    yield base
    proc.terminate()
    proc.communicate(timeout=10)


def test_gate_blocks_even_after_approval():
    project = Project(id="demo", name="Demo", base_url="http://localhost:8001")
    adapter = CampusPassAdapter(project, None)
    evidence = {"ok": True, "body": {"fault": "checkout_outage", "revision": 1}}
    for name in ["delete_database", "force_issue_ticket", "shell", "restart_container"]:
        candidate = Candidate(id="bad", rationale="Unsafe", actions=[Action(operation=name)])
        assert evaluate(candidate, project, evidence, adapter, "service", approved=True)["eligible"] is False


def test_gate_requires_fresh_preconditions_and_exact_order():
    project = Project(id="demo", name="Demo", base_url="http://localhost:8001")
    adapter = CampusPassAdapter(project, None)
    candidate = Candidate(id="retry", rationale="retry", actions=[Action(operation="retry_order", order_id="wrong")])
    assert not evaluate(candidate, project, {"ok": True, "body": {"fault": "none", "revision": 2}}, adapter, "actual")["eligible"]
    assert not evaluate(candidate, project, {"ok": False, "body": {}}, adapter, "wrong")["eligible"]


def test_recorder_restart_and_deduplication(tmp_path):
    url = f"sqlite:///{tmp_path}/persist.db"
    first = Store(url)
    incident, created = first.create("demo", "outage", "service", {})
    assert created
    same, created = first.create("demo", "outage", "service", {})
    assert not created and same["id"] == incident["id"]
    event_id = first.record(incident["id"], "executing", {"request_id": "kept"})
    first.update(incident["id"], status="executing")
    first.engine.dispose()
    second = Store(url)
    second.interrupt_inflight()
    assert second.get(incident["id"])["status"] == "escalated"
    assert second.events(0)[0]["id"] == event_id
    assert second.events(event_id)[0]["stage"] == "interrupted"
    second.engine.dispose()


@pytest.mark.parametrize("path", ["../escape.py", "/tmp/escape.py", "tests/test_app.py", ".env", "setup.py", "src/../../escape.py", "src\\escape.py"])
def test_continuation_rejects_paths(tmp_path, path):
    with pytest.raises(ValueError):
        validate_path(tmp_path, path)


def test_continuation_rejects_symlink(tmp_path):
    if os.name == "nt":
        pytest.skip("Windows symlinks require elevated permissions")
    (tmp_path / "source.py").symlink_to(tmp_path / "target.py")
    with pytest.raises(ValueError):
        validate_path(tmp_path, "source.py")


async def test_real_http_outage_recovery_and_blocked_alternative(store, campus):
    async with httpx.AsyncClient() as client:
        project = Project(id="demo", name="Campus", base_url=campus)
        store.save_project(project.model_dump())
        await client.post(campus + "/demo/fault", headers={"X-Recovery-Token": "test-recovery"}, json={"fault": "checkout_outage"})
        adapter = CampusPassAdapter(project, client)
        assert not (await adapter.read("health"))["ok"]
        incident, _ = store.create("demo", "outage", "service", {})
        engine = Engine(store, client, TestReasoner(), EmptyRunbooks())
        await engine.run(incident["id"])
        result = store.get(incident["id"])
        assert result["status"] == "resolved", result
        assert result["verification"]["passed"]
        rejected = next(r for r in result["tournament"] if r["candidate_id"] == "unsafe")
        assert not rejected["eligible"]
        assert any(e["stage"] == "operation_result" for e in store.events())
        assert engine.receipt(incident["id"])["success"]


async def test_workflow_approval_and_exactly_one_ticket(store, campus):
    async with httpx.AsyncClient() as client:
        store.save_project(Project(id="demo", name="Campus", base_url=campus).model_dump())
        await client.post(campus + "/demo/fault", headers={"X-Recovery-Token": "test-recovery"}, json={"fault": "worker_paused"})
        order = (await client.post(campus + "/checkout", json={"event_id": "agentathon", "email": "student@example.com", "request_id": "workflow-request"})).json()["id"]
        incident, _ = store.create("demo", "workflow", order, {})
        engine = Engine(store, client, TestReasoner(), EmptyRunbooks())
        await engine.run(incident["id"])
        pending = store.get(incident["id"])
        assert pending["status"] == "awaiting_approval", pending
        assert not (await client.get(campus + "/orders/" + order)).json()["tickets"]
        with pytest.raises(ValueError):
            await engine.approve(incident["id"], "wrong")
        await engine.approve(incident["id"], pending["approval_hash"])
        assert store.get(incident["id"])["status"] == "resolved"
        assert len((await client.get(campus + "/orders/" + order)).json()["tickets"]) == 1


async def test_monitor_detects_without_prompt_and_deduplicates(store, campus, monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    async with httpx.AsyncClient() as client:
        store.save_project(Project(id="demo", name="Campus", base_url=campus).model_dump())
        await client.post(campus + "/demo/fault", headers={"X-Recovery-Token": "test-recovery"}, json={"fault": "checkout_outage"})
        # Missing NIM credentials intentionally blocks recovery, preserving the detected incident.
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
        app = create_app(store, client, runbooks=EmptyRunbooks(), monitor=False)
        await app.state.scan()
        await asyncio.gather(*app.state.tasks)
        await app.state.scan()
        assert len(store.incidents()) == 1
        assert store.incidents()[0]["status"] == "blocked"


async def test_verifier_rejects_healthy_but_missing_ticket(campus):
    async with httpx.AsyncClient() as client:
        await client.post(campus + "/demo/fault", headers={"X-Recovery-Token": "test-recovery"}, json={"fault": "worker_paused"})
        order = (await client.post(campus + "/checkout", json={"event_id": "agentathon", "email": "student@example.com", "request_id": "missing-ticket-request"})).json()["id"]
        adapter = CampusPassAdapter(Project(id="demo", name="Campus", base_url=campus), client)
        assert (await adapter.read("health"))["ok"]
        assert not (await adapter.verify("workflow", order))["passed"]


async def test_replans_once_from_gate_feedback(store, campus):
    class RevisingReasoner(TestReasoner):
        calls = 0
        async def plan(self, incident, diagnosis, adapter, store, runbooks, feedback=None):
            self.calls += 1
            if self.calls == 1:
                return RecoveryPlan(diagnosis="Initial invalid plan", candidates=[Candidate(id="invalid", rationale="Invented operation", actions=[Action(operation="restart_everything")]), Candidate(id="empty", rationale="No action", actions=[])])
            assert feedback and all(not r["eligible"] for r in feedback)
            return await super().plan(incident, diagnosis, adapter, store, runbooks, feedback)
    async with httpx.AsyncClient() as client:
        store.save_project(Project(id="demo", name="Campus", base_url=campus).model_dump())
        await client.post(campus+"/demo/fault",headers={"X-Recovery-Token":"test-recovery"},json={"fault":"checkout_outage"})
        incident, _ = store.create("demo", "outage", "service", {})
        reasoner = RevisingReasoner()
        await Engine(store, client, reasoner, EmptyRunbooks()).run(incident["id"])
        assert reasoner.calls == 2
        assert store.get(incident["id"])["status"] == "resolved"
        assert len([e for e in store.events() if e["stage"] == "plan_revision"]) == 1


def test_missing_credentials_are_explicit(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(ReasoningUnavailable):
        NIMReasoner.llm()


@pytest.mark.parametrize("configured,expected", [("openai/nvidia/nemotron-model", "nvidia/nemotron-model"), ("nvidia/nemotron-model", "nvidia/nemotron-model"), ("openai/gpt-oss-120b", "openai/gpt-oss-120b")])
def test_nvidia_model_routing_prefix(monkeypatch, configured, expected):
    monkeypatch.setenv("NVIDIA_API_KEY", "explicit-test-key-never-sent")
    monkeypatch.setenv("NVIDIA_MODEL", configured)
    assert NIMReasoner.llm().model == expected


def test_nemotron_structured_output_budget(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "explicit-test-key-never-sent")
    monkeypatch.setenv("NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
    monkeypatch.delenv("NVIDIA_ENABLE_THINKING", raising=False)
    llm = NIMReasoner.llm()
    assert llm.additional_params["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
    assert llm.max_tokens >= 8192


def test_chroma_retrieval(tmp_path):
    from ctrlz.runbooks import Runbooks
    source = tmp_path / "runbooks"
    source.mkdir()
    (source / "worker.md").write_text("worker ticket retry idempotency")
    books = Runbooks(source, tmp_path / "chroma")
    assert books.search("worker ticket")[0]["id"] == "worker.md"

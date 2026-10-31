import httpx
import pytest
from pydantic import ValidationError

from ctrlz.engine import Engine
from ctrlz.main import create_app
from ctrlz.models import ImportRequest
from ctrlz.continuation import Continuation
from ctrlz.settings import Settings
from ctrlz.store import Store
from ctrlz import runtime


class Books:
    def search(self, query):
        return []


class Reasoner:
    provider = "explicit test fixture"
    selected_model = "fixture-model"


@pytest.mark.parametrize("name,value", [
    ("MONITOR_INTERVAL", "0"), ("MONITOR_INTERVAL", "nan"),
    ("NVIDIA_MAX_TOKENS", "12"), ("CTRLZ_CODE_EXECUTION_ENABLED", "perhaps"),
    ("NVIDIA_BASE_URL", "https://user:secret@example.com/v1"),
    ("CTRLZ_CORS_ORIGINS", "*"),
])
def test_invalid_settings_fail_before_startup(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings()


def test_dotenv_and_environment_precedence_preserve_secret_redaction(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("NVIDIA_API_KEY=private-fixture-key\nMONITOR_INTERVAL=9\n")
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setenv("MONITOR_INTERVAL", "3")
    settings = Settings(_env_file=path)
    assert settings.MONITOR_INTERVAL == 3
    assert settings.NVIDIA_API_KEY.get_secret_value() == "private-fixture-key"
    assert "private-fixture-key" not in repr(settings)


@pytest.mark.asyncio
async def test_runtime_is_authenticated_and_reports_real_component_states(tmp_path, monkeypatch):
    monkeypatch.setenv("CTRLZ_OPERATOR_TOKEN", "runtime-token")
    monkeypatch.setenv("CTRLZ_CODE_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("IMPORT_ROOT", str(tmp_path / "imports"))
    seen = []
    def command(arguments):
        seen.append(arguments)
        return {"state": "unavailable", "detail": "fixture daemon unavailable"} if arguments[0] == "docker" else {"state": "available", "detail": "git fixture"}
    monkeypatch.setattr(runtime, "command_status", command)
    store = Store(f"sqlite:///{tmp_path / 'workspace.db'}")
    app = create_app(store=store, reasoner=Reasoner(), runbooks=Books(), monitor=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/runtime")).status_code == 401
        response = await client.get("/runtime", headers={"X-Operator-Token": "runtime-token"})
        assert response.status_code == 200
        rows = {row["name"]: row for row in response.json()["components"]}
        assert rows["Workspace database"]["state"] == "available"
        assert rows["Docker daemon"]["state"] == "unavailable"
        assert rows["NVIDIA NIM"]["verified"] is False
        assert "Outcome notifications" not in rows
        assert not any("image" in command for command in seen)
        assert "runtime-token" not in response.text
    await app.state.engine.client.aclose()
    store.engine.dispose()


@pytest.mark.asyncio
async def test_blocked_repository_repair_also_notifies(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'events.db'}")
    incident, _ = store.create("code-import", "code", "missing-repository", {})
    notified = []
    async def notify(incident_id):
        notified.append(store.get(incident_id))
    continuation = Continuation(store, Reasoner(), tmp_path / "imports", tmp_path / "patches", notifier=notify)
    await continuation.run(incident["id"], ImportRequest(repository="missing-repository", requirements="Repair the reproduced failure"))
    assert len(notified) == 1
    assert notified[0]["status"] in {"blocked", "escalated"}
    store.engine.dispose()


@pytest.mark.asyncio
async def test_legacy_model_override_cannot_change_repair_reasoner(tmp_path):
    request = ImportRequest.model_validate({
        "repository": "missing-repository",
        "requirements": "Repair the reproduced failure",
        "model": "other-provider/other-model",
    })
    assert "model" not in request.model_dump()
    assert "model" not in ImportRequest.model_json_schema()["properties"]
    store = Store(f"sqlite:///{tmp_path / 'model-check.db'}")
    incident, _ = store.create("code-import", "code", "missing-repository", {})
    continuation = Continuation(store, Reasoner(), tmp_path / "imports", tmp_path / "patches")
    await continuation.run(incident["id"], request)
    assert store.get(incident["id"])["model"] == "fixture-model"
    store.engine.dispose()

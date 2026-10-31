import asyncio
import os
import secrets
import subprocess
import uuid
from pathlib import Path
import httpx
from .adapter import CampusPassAdapter
from .models import Action, Candidate
from .presets import campuspass_project as Project
from .safety import evaluate


class Replay:
    """Only the controlled CampusPass v1 fixtures, in a unique Compose project/storage."""
    def __init__(self, store):
        self.store = store
        self.lock = asyncio.Lock()

    async def run(self, incident_id, candidate: Candidate):
        async with self.lock:
            root = Path(os.getenv("REPLAY_CAMPUSPASS_DIR", "../../campuspass")).resolve()
            template = root / "demo" / "docker-compose.replay.yml"
            project_name = "ctrlz-replay-" + uuid.uuid4().hex[:10]
            token = secrets.token_urlsafe(32)
            env = {**os.environ, "REPLAY_TOKEN": token}
            prefix = ["docker", "compose", "-p", project_name, "-f", str(template)]
            def compose(args, timeout=180):
                result = subprocess.run(prefix+args, env=env, capture_output=True, text=True, timeout=timeout)
                if result.returncode:
                    raise RuntimeError("Replay compose failed: " + result.stderr[-300:])
                return result.stdout
            self.store.record(incident_id, "replay_started", {"candidate_id": candidate.id, "isolation": project_name})
            try:
                if not template.is_file():
                    raise RuntimeError("Controlled replay template is unavailable")
                incident = self.store.get(incident_id)
                if incident["kind"] not in {"outage", "workflow"}:
                    raise ValueError("Unsupported replay kind")
                await asyncio.to_thread(compose, ["up", "--build", "-d", "api"])
                address = (await asyncio.to_thread(compose, ["port", "api", "8001"])).strip()
                base = "http://" + address
                async with httpx.AsyncClient() as client:
                    for _ in range(60):
                        try:
                            if (await client.get(base + "/health")).is_success:
                                break
                        except httpx.HTTPError:
                            pass
                        await asyncio.sleep(0.5)
                    else:
                        raise RuntimeError("Replay service never became healthy")
                    headers = {"X-Recovery-Token": token}
                    fault = "checkout_outage" if incident["kind"] == "outage" else "worker_paused"
                    response = await client.post(base+"/demo/fault", headers=headers, json={"fault": fault})
                    response.raise_for_status()
                    resource = "service"
                    if incident["kind"] == "workflow":
                        response = await client.post(base+"/checkout", json={"event_id": "agentathon", "email": "replay@example.com", "request_id": str(uuid.uuid4())})
                        response.raise_for_status()
                        resource = response.json()["id"]
                    env_name = "CTRLZ_REPLAY_" + uuid.uuid4().hex.upper()
                    os.environ[env_name] = token
                    try:
                        project = Project(id="replay", name="Isolated replay", base_url=base, token_env=env_name)
                        adapter = CampusPassAdapter(project, client)
                        baseline = await adapter.verify(incident["kind"], resource)
                        self.store.record(incident_id, "replay_baseline", {"candidate_id": candidate.id, "verification": baseline})
                        if baseline["passed"]:
                            raise RuntimeError("Replay failed to reproduce the incident")
                        mapped = candidate.model_copy(update={"actions": [Action(operation=a.operation, order_id=resource if a.order_id else None) for a in candidate.actions]})
                        for action in mapped.actions:
                            diagnostics = await adapter.read("diagnostics")
                            # Explicit operator replay request authorizes allowed actions only inside this fixture.
                            gate = evaluate(Candidate(id=mapped.id, rationale=mapped.rationale, actions=[action]), project, diagnostics, adapter, resource, approved=True)
                            if not gate["eligible"]:
                                raise ValueError("Replay safety gate rejected candidate")
                            await adapter.execute(action, str(uuid.uuid4()), diagnostics["body"]["revision"])
                        verification = await adapter.verify(incident["kind"], resource)
                        self.store.record(incident_id, "replay_result", {"candidate_id": candidate.id, "verification": verification, "fixture": fault, "production_mutated": False})
                    finally:
                        os.environ.pop(env_name, None)
            except Exception as exc:
                self.store.record(incident_id, "replay_failed", {"candidate_id": candidate.id, "error_type": type(exc).__name__, "reason": str(exc)[:300]})
            finally:
                try:
                    await asyncio.to_thread(compose, ["down", "-v", "--remove-orphans"], 60)
                except Exception:
                    self.store.record(incident_id, "replay_cleanup_required", {"compose_project": project_name})

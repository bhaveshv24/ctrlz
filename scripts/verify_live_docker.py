"""Opt-in live NIM acceptance against a separate local CampusPass Docker service.

Run from ctrlz/backend: uv run python ../scripts/verify_live_docker.py
Requires CAMPUSPASS_PORT=18001 docker compose up -d api in the sibling app.
Only controlled local demo faults are injected. Receipts include all failed attempts.
"""
import asyncio
import json
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv

load_dotenv("../.env", override=True)

from ctrlz.main import create_app
from ctrlz.presets import campuspass_project as Project
from ctrlz.reasoning import NIMReasoner
from ctrlz.runbooks import Runbooks
from ctrlz.store import Store


async def main():
    base = "http://127.0.0.1:18001"
    store = Store("sqlite:///./data/live-docker.db")
    store.save_project(Project(id="campuspass-docker", name="CampusPass Docker", base_url=base).model_dump())
    async with httpx.AsyncClient() as client:
        headers = {"X-Recovery-Token": os.environ["CAMPUSPASS_RECOVERY_TOKEN"]}
        runbooks = Runbooks(Path("../runbooks"), Path("./data/live-docker-chroma"))
        app = create_app(store, client, NIMReasoner(), runbooks)
        async with app.router.lifespan_context(app):
            for scenario, fault in [("C", "checkout_outage"), ("B", "worker_paused")]:
                response = await client.post(base+"/demo/fault", headers=headers, json={"fault": fault})
                response.raise_for_status()
                if scenario == "B":
                    import uuid
                    response = await client.post(base+"/checkout", json={"event_id": "agentathon", "email": "live-demo@example.com", "request_id": str(uuid.uuid4())})
                    response.raise_for_status()
                print(f"Scenario {scenario}: controlled Docker fault injected; waiting for autonomous monitor", flush=True)
                for _ in range(600):
                    matches = [i for i in store.incidents() if i["kind"] == ("outage" if scenario == "C" else "workflow")]
                    if matches:
                        incident = matches[0]
                        if incident["status"] == "awaiting_approval":
                            # Test operator explicitly authorizes this local demo operation.
                            # This exercises the approval API semantics; it is not a claim that a human clicked.
                            store.record(incident["id"], "test_operator_approval", {"physical_human_click": False, "scope": "local demo fixture"})
                            await app.state.engine.approve(incident["id"], incident["approval_hash"])
                            incident = store.get(incident["id"])
                        if incident["status"] in {"resolved", "escalated", "blocked"}:
                            receipt = app.state.engine.receipt(incident["id"])
                            output = Path(f"./data/live-scenario-{scenario}.json")
                            output.write_text(json.dumps(receipt, indent=2))
                            print({"scenario": scenario, "status": incident["status"], "verification": incident.get("verification"), "receipt": str(output.resolve())}, flush=True)
                            if incident["status"] != "resolved":
                                raise RuntimeError(f"Scenario {scenario} did not verify: {incident.get('error')}")
                            break
                    await asyncio.sleep(1)
                else:
                    raise TimeoutError(f"Scenario {scenario} exceeded the live test deadline")


if __name__ == "__main__":
    asyncio.run(main())

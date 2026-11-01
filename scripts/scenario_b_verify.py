"""Verify a recovered local CampusPass order and exercise idempotent retries.

Run only AFTER human approval and successful recovery. This never approves an
incident, clears a fault, creates an order, or repeats payment.
"""
import argparse
import json
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("order_id", type=lambda value: str(uuid.UUID(value)))
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    args = parser.parse_args()
    url = urlsplit(args.url)
    if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"} or url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
        parser.error("This rehearsal utility accepts a loopback HTTP origin only")
    root = Path(__file__).resolve().parents[1]
    campus = root.parent / "campuspass"
    token = dotenv_values(campus / ".env").get("RECOVERY_TOKEN")
    if not token:
        parser.error("CampusPass .env must contain RECOVERY_TOKEN; it is never printed")

    with httpx.Client(base_url=args.url, headers={"X-Recovery-Token": token}, timeout=15, follow_redirects=False) as client:
        def read(path):
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        before = read("/orders/" + args.order_id)
        diagnostics = read("/diagnostics")
        assert diagnostics["fault"] == "none", "Worker must already be ready; approve recovery in CtrlZ first"
        assert before["id"] == args.order_id and before["payment"] == "paid" and before["job"] == "done"
        assert len(before["tickets"]) == 1 and before["tickets"][0]["valid"] is True
        payload = {"request_id": str(uuid.uuid4()), "expected_revision": diagnostics["revision"], "order_id": args.order_id}
        responses = []
        for _ in range(2):
            response = client.post("/operations/retry_order", json=payload)
            response.raise_for_status()
            responses.append(response.json())
        assert responses[0] == responses[1] and responses[0]["created"] is False
        fresh = {**payload, "request_id": str(uuid.uuid4()), "expected_revision": read("/diagnostics")["revision"]}
        response = client.post("/operations/retry_order", json=fresh)
        response.raise_for_status()
        assert response.json()["created"] is False
        after = read("/orders/" + args.order_id)
        ticket = read("/tickets/" + before["tickets"][0]["id"] + "/verify")
        checks = {
            "payment_still_paid": after["payment"] == "paid",
            "same_payment_reference": after["payment_reference"] == before["payment_reference"],
            "exactly_one_unchanged_ticket": len(after["tickets"]) == 1 and after["tickets"] == before["tickets"],
            "job_done": after["job"] == "done",
            "ticket_valid_in_application": ticket["valid"] is True,
            "identical_request_replayed": responses[0] == responses[1],
            "fresh_retry_preserved_entitlement": response.json()["created"] is False,
        }
        assert all(checks.values()), checks
    evidence = {"description": "Real HTTP operator retry rehearsal after human-approved recovery; no AI or approval simulated", "before": before, "after": after, "checks": checks, "replayed_request": payload, "replayed_results": responses, "fresh_retry_result": response.json(), "ticket_verification": ticket}
    directory = root / "backend/data/scenario-b"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("idempotency-" + args.order_id + "-" + payload["request_id"] + ".json")
    path.write_text(json.dumps(evidence, indent=2))
    print(json.dumps({"passed": True, "order_id": args.order_id, "checks": checks, "evidence": str(path)}, indent=2))


if __name__ == "__main__":
    main()

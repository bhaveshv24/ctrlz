# Repeatable judging demonstration

## Target-aware Demo Lab (standalone)

1. From the CtrlZ root, start the existing configured workspace with
   `uv run --project backend python scripts/dev.py`. Open http://localhost:5173 and sign in
   with the local CTRLZ_OPERATOR_TOKEN. Docker sandbox images and NVIDIA NIM credentials
   are required for a live verified repair, as described in README.md.
2. In Repository repair, import the server folder
   `examples/reservation-python` using its absolute path in your checkout. This is an
   explicitly synthetic healthy fixture with no dependencies, not an upstream defect.
3. Open Demo Lab → Refresh targets → choose the imported repository. Inspect the actual
   Python/pytest profile, detected test-file count and editable source list. Counts shown
   before execution are files, not guessed collected test cases.
4. Choose **Disclosed injected regression**, review the copy-only disclosure, and run it.
   CtrlZ proves a passing original baseline, applies one deterministic non-test mutation in
   a separate managed copy, and requires the same collected test identities to fail. A
   surviving mutation, unsupported source, missing Docker or originally failing suite stops
   setup honestly; no successful repair is claimed. The mutation is bounded to one candidate.
5. Follow recovery from this target's persisted run history. Inspect the baseline events,
   normal RETRY/COMPENSATE/REPLAN tournament and original immutable acceptance checks. Export
   the receipt, which explicitly discloses injection. A patch stays local to the copied snapshot.
6. For an already broken imported repository, choose **Repair** instead, with requirements
   describing its intended behavior. Approve isolated dependency setup only when needed.
7. Select a generic HTTP project to inspect its configured health/workflow paths, registered
   operations and contract. **View monitoring** opens Projects; **Review contract** opens its
   settings. Unsupported fault injection stays disabled with a reason. These read-only views
   do not create fabricated recovery runs. The dispatch service example needs no CampusPass.
8. CampusPass C/B and reset controls appear only for the CampusPass adapter. History is scoped
   to the selected target and keeps incident and receipt links. Refresh targets after importing
   another repository or editing a service configuration.

## Optional CampusPass rehearsal


For a local controlled demonstration, set CTRLZ_DEMO_CONTROLS_ENABLED=true in CtrlZ's
backend `.env`, restart the API, and opt the CampusPass project into “Allow controlled demo
faults” in Project settings. CampusPass must also have DEMO_MODE=true and matching backend
recovery credentials. Public deployments default these flags off.

Open Demo Lab, choose the project and start C or B. Review the target and fault effect in
the dialog. The run history waits for the independent monitor and then links the resulting
incident. Read Story → Strategies → Flight recorder → Receipt. For B, review the exact
candidate and explicitly authorize it or decline it. JSON and readable Markdown exports
are available from the receipt. Focus view changes presentation layout only.

For repository repair, use the standalone target-aware flow above; the historical fixture below remains optional.
The CLI fault controls remain available for independent operation and fallback rehearsal.

Use two independent Git checkouts and the local setup in README.md. Keep the live
dashboard, CampusPass, and the receipt download visible. Use real NVIDIA credentials.
The default contract deliberately requires approval for resuming a paused worker.

## Before the optional CampusPass demo

1. Start Docker Desktop, build ctrlz-sandbox:local, install dependencies, generate local
   `.env` files with scripts/setup_env.py, and set NVIDIA_API_KEY / NVIDIA_MODEL.
2. Run scripts/dev.py. Sign into CtrlZ using CTRLZ_OPERATOR_TOKEN from its local `.env`.
3. Connect CampusPass at http://localhost:8001 (host mode) or http://campuspass-api:8001
   (Compose mode). The recovery token must match in the two backend environments.
4. Run a normal checkout first. Show the async ticket transition and ticket verification.
5. Optional: set NOTIFICATION_WEBHOOK_URL and restart the CtrlZ API to send a real summary.

## C — Autonomous outage recovery

Run from CampusPass with RECOVERY_TOKEN set in your shell:

```sh
uv run --project backend python demo/control.py outage
```

Do not send a troubleshooting prompt. Within one monitor interval CtrlZ creates an incident.
Open it and follow actual diagnostic tool results, runbook retrieval, diagnosis and strategy
evaluation. An unsafe alternative is rejected by the deterministic gate. A permitted circuit
restoration executes, and three independent health/latency checks must pass. Download the
receipt. Show webhook delivery status if configured. This is a mitigation, not proof of a
permanent defect fix. For a latency fault use `slow` instead of `outage`.

## B — Healthy website, paid customer without a ticket

```sh
uv run --project backend python demo/control.py pause
uv run --project backend python demo/control.py checkout
```

The website health stays green while a paid order lacks an entitlement. After the grace
period CtrlZ detects the workflow discrepancy, inspects real worker records, and compares
plans. The force_issue_ticket strategy is blocked. A resume_worker proposal pauses at the
approval panel. Review the exact candidate and approve it. Independent verification checks
payment=paid, exactly one valid ticket, and job=done. Repeated authorized retries return the
same entitlement; they cannot create another ticket due to the database uniqueness rule.

The `defect` fault invokes the real legacy_reference UUID formatter bug. A restart/resume
is rejected. Import the isolated code fixture below to obtain a reviewed patch; do not
represent resetting the demo fault as deploying a permanent fix.

## A — Explicitly imported development continuity

From CtrlZ:

```sh
python scripts/create_continuation_demo.py --campuspass ../campuspass
```

In Code recovery, paste the absolute path printed by the script and requirements from
the generated requirements.md. Supply conversation context only if you explicitly want it
used. CtrlZ executes the failing baseline in a Docker sandbox, sends the bounded source
snapshot and supplied requirements to NVIDIA through the Code Recovery Agent, applies
source-only changes in a detached Git worktree, and runs the same immutable tests again.
All tests must execute and pass. The output is a patch artifact, not an automatic merge.
The source branch remains untouched. Re-run using a new fixture destination for another
presentation. The nested demo fixture repository is ignored and is not a third product repo.

## Recovery Replay

For an operational incident, choose “Replay in isolation” on a candidate. The host backend
creates a uniquely named Compose project, database volume, local port and service token;
reproduces the supported checkout/worker fault; evaluates the same operation allowlist;
and records baseline/candidate verification in the original incident’s flight recorder.
It removes only its own resources afterward. Replaying a prohibited candidate is expected
to fail. This feature needs the sibling CampusPass source and host Docker access.

## Reset and cleanup

`demo/control.py reset` clears the injected fault only; previous orders, incidents, and
receipts remain for auditing. Resolved incidents permit a new incident on the next fault.
Blocked/escalated incidents remain deduplicated; correct configuration and choose Retry.
No reset silently deletes customer or incident records. For a completely fresh practice
run, stop the apps and point DATABASE_URL / DATA_DIR at new empty local paths. Compose
replay volumes are disposable and cleaned automatically; normal app volumes are persistent.

## If something fails

Missing/invalid key: incident remains blocked/escalated; update `.env`, restart API, Retry.
User may set NVIDIA_MODEL either as `nvidia/model-id` or `openai/nvidia/model-id`; CtrlZ
normalizes the optional CrewAI routing prefix. Native `openai/gpt-oss-*` catalog IDs remain
intact. API liveness reports key presence, not successful provider authentication.
Nemotron 3-family models use NVIDIA's documented direct-answer setting by default to
reserve output capacity for tool calls and structured code. Set NVIDIA_ENABLE_THINKING=true
to enable model reasoning traces, and increase NVIDIA_MAX_TOKENS if needed. The default
output budget is 8192 tokens. See [NVIDIA's setting documentation](https://build.nvidia.com/playbooks/nim-llm/instructions).
Revision conflict: re-investigate; do not bypass the precondition. Worker defect: code
repair pathway. Docker unavailable: no host execution fallback. Notification failure:
recovery remains accurately recorded, with undelivered status. CI files are provided;
cross-platform execution must be observed separately before claiming it passed.

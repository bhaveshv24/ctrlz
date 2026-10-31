> This handoff describes the pre-implementation starting point. Deadline-driven code
> has since been added locally. Read `DEADLINE_DRIVEN_MONITORING.md` and inspect
> the current diff/tests for the implemented state.

# Handoff: deadline-triggered workflow checks

## Current task

The user wants the recommended low-load workflow-monitoring method implemented:

1. Observe a real operation-start event and persist its deadline in CtrlZ.
2. Observe completion/cancellation events and cancel the pending deadline check.
3. If the deadline expires without completion, request a targeted, independent,
   read-only check of that specific operation.
4. Confirm incomplete durable state before creating a business-failure incident.
5. Missing evidence, collector disconnection or an unavailable database must mean
   unknown/degraded monitoring, not a confirmed failed transaction.

Do not repeatedly scan the application's database or poll custom application
health/workflow APIs for this new path. CtrlZ can manage its own local timers and
durable queue. Existing Generic HTTP and CampusPass adapter behavior must remain
backward compatible; do not silently claim those legacy paths became event-driven.

The user authorized safe LOCAL checkpoint commits in both repositories before
implementation. These checkpoints are now completed. Nothing was pushed.

| Repository | Branch | Checkpoint SHA |
| --- | --- | --- |
| CtrlZ | main | b6927cdb9fb1f662cd0db05a86633638ce15d23f |
| CampusPass | main | ed63de400b76136ca4dc26f4e63716966dfb1b49 |

CtrlZ checkpoint message: `chore: checkpoint CtrlZ before deadline-driven workflow checks`.
CampusPass checkpoint message: `chore: checkpoint CampusPass before deadline-driven workflow checks`.
CampusPass's checkpoint is intentionally EMPTY: its remaining differences are
tracked database/cache/build/dependency artifacts, not uncommitted source changes.
Those files were preserved and excluded. CtrlZ's prior local Scenario B guide is
still untracked because it contains live ticket references. Keep it out of commits.

**No deadline-driven implementation changes have been made after these commits.**
The interrupted turn was auditing and designing the next implementation.
This handoff document is the only new post-checkpoint file written for handoff.

## Workspace and restrictions

- CtrlZ: `/home/atharv/Documents/PES/Hackathon/ctrlz`
- CampusPass: `/home/atharv/Documents/PES/Hackathon/CampusPass`
- Lowercase sibling symlink `campuspass` points to CampusPass; do not rename repos.
- Preserve existing `.env` and credentials. Never print their values or private
  session JSON files. Runtime data below `backend/data` is ignored/private.
- No pushes, fetches, pulls, fork synchronization, branch changes, resets or clean.
  Leave new feature changes uncommitted unless the user explicitly requests otherwise.
- Teammate owns Scenario A. Do not edit continuation.py, repository.py, sandbox.py,
  repair/worktree logic, Scenario A fixtures/tests, ContinuationForm or DemoLab.
- No cloud deployment or production mutation is authorized by this task.
- Do not spawn subagents unless explicitly authorized by the user/instructions.

## Read these first

1. `docs/AI_WORKFLOW_OBSERVABILITY.md` — implemented audit, approval, patch and
   current reconciliation behavior, limits, API concepts and startup commands.
2. `docs/AI_WORKFLOW_OBSERVABILITY_VALIDATION.md` — actual previous test/demo
   results, file inventory, scope and preserved Scenario A boundary.
3. `docs/AI_WORKFLOW_DEMO.md` — actual demo commands/clicks.
4. `backend/ctrlz/workflow_service.py` — proposal binding, activation, signal
   validation, durable instance ingestion and current reconciliation engine.
5. `backend/ctrlz/workflow_store.py` and `workflow_models.py` — tables, indexed
   deadlines, strict events and approvals.
6. `scripts/workflow_sqlite_collector.py` — current full-table polling collector
   that the new deadline-targeted path should replace as the demo default.
7. `scripts/workflow_demo.py` — isolated server, generated fixture deployment,
   1,000 real HTTP operations, lifecycle forwarding and current polling `watch`.
8. `backend/ctrlz/runtime_monitoring.py`, `runtime_routes.py`, `main.py`, `access.py`
   — authenticated ingestion, incident integration, periodic local scan and gateway.
9. `backend/tests/test_workflow_observability.py` — current 44 workflow cases.
10. `frontend/src/components/WorkflowAudit.tsx`, RuntimeProjectCard.tsx,
    RuntimeProjectForm.tsx and RuntimeIncident.tsx — existing UI extension points.

For broader product context, read README.md and
`docs/REPOSITORY_DEPLOYMENT_MONITORING.md`. Do not rebuild the existing framework.

## What already works

The workflow feature is checkpointed and was genuinely demonstrated:

- NVIDIA/CrewAI audits bounded, pinned source and proposes reviewable rules.
- Exact rule/source/deployment/privacy approvals are persisted.
- AI selects approved hooks; a deterministic compiler adds Python decorators and
  a stdlib probe. Business AST and original tests are preserved.
- Baseline/candidate tests run offline in the existing Docker sandbox.
- The generated probe emits start/completion/failure events, with a bounded
  nonblocking stdout queue and optional pseudonymous user correlation.
- Workflow events use existing scoped, source-authenticated runtime ingestion.
- Independent SQLite reconciliation currently confirms overdue operations by
  polling durable records. Missing completion logs alone only cause warnings.
- Incidents reuse existing AI diagnosis, recommendation review and receipts.
  There are no new recovery execution permissions.

Previous actual results: CtrlZ **206 passed, 8 skipped**; frontend **32 passed**
and build passed. CampusPass **14 backend + 8 proxy tests passed**, build passed.
Generated fixture: 5 baseline, the same 5 candidate, 9 including probe tests passed.

Live demo: 1,000 sequential real requests, 999 completed jobs, one pending job,
HTTP health 200; 1,000 start and 999 completion signals; zero explicit errors.
Exactly one incident, correct job/resource and verified pseudonymous user.
Human physically approved monitoring and generation. No business recovery occurred.

Existing demo incident:
`af81a8eb-089c-4e9a-be66-06ba9e2640e4`
http://localhost:18052/#incident/af81a8eb-089c-4e9a-be66-06ba9e2640e4

It remains awaiting_review, with success=false, correctly: the fixture's deliberate
incompletion was detected, not repaired.

## Current runtime topology (inspect before changing processes)

- Main CtrlZ: 8000 / 5173, existing workflows and teammate work; leave untouched.
- Main CampusPass: 8001 / 5174.
- Separate hosted-rehearsal CtrlZ may still run on 18040 / 18042.
- Workflow demo CtrlZ: 18050 / 18052.
- Owned workflow fixture is a Docker container named `ctrlz-workflow-demo-...`,
  with an ownership label recorded in `backend/data/workflow-demo/run.json`.
  It has no external network. Business HTTP requests run inside the container.
- A continuous polling collector may still run via `scripts/workflow_demo.py watch`
  and its `workflow_sqlite_collector.py --interval 15` child. Stop only this owned
  watcher when replacing it, not unrelated processes or containers.
- Rootless Docker: `DOCKER_HOST=unix:///run/user/1000/docker.sock`.
- Existing Python sandbox image `ctrlz-sandbox:local` was built with explicit user
  approval. Reuse it; do not download additional dependencies silently.
- Backend Python: `backend/.venv/bin/python` (3.12). Frontend deps already installed.

Runtime artifacts under `backend/data/workflow-demo/` include private session and
source-credential paths, generated source, approval records, operation/lifecycle
counts, actual receipts and browser screenshots. Read selectively; do not print
session files, `.env`, token files or application.env.

## Suggested implementation design (not yet implemented)

Prefer a new feature-owned durable deadline-check queue, integrated with the
existing instance/event pipeline. Start queues work; completion/cancellation
cancels it. A local CtrlZ timer wakes on events or the nearest deadline.

A deployment-side read-only checker can maintain a long-lived authenticated
connection to CtrlZ and receive due checks. SSE on the existing telemetry URL
using GET is a possible design: it avoids adding custom APIs to the application
and keeps project/deployment/source authorization. Existing POST ingestion stays
compatible. Inspect access.py's exact telemetry path dispatch before choosing URLs.

Important queue requirements:

- Persist target, proposal/version, operation ID, deadline and check state.
- Scope every work item and result to the approved independent source.
- Use leases/nonces, bounded attempts, restart recovery and result deduplication.
- Reject stale results after completion, cancellation, rule/deployment changes,
  expired leases or disabled projects. Never overwrite a newer completion.
- Replayed identical results should be idempotent, including after lost ACKs.
- Normal path: zero independent database lookups for completed operations; one
  targeted indexed lookup for an overdue operation. Bounded redelivery after a
  checker crash may repeat a safe read; do not promise distributed exactly-once I/O.
- Database unavailable/missing row/unknown status gives monitoring-quality
  uncertainty, not a fabricated business failure. No unbounded rechecking.
- Keepalive/heartbeat traffic must touch only CtrlZ/control-plane state, not scan
  the application database. A source heartbeat is not proof that an operation
  completed or that its database is accessible.
- Legacy snapshot reconciliation should remain explicit/backward compatible.
  New activations/demo should choose deadline-targeted mode and label it accurately.

The targeted SQLite checker should accept only operator-configured identifiers and
an existing read-only database. Use a parameterized lookup by indexed/unique job ID,
not arbitrary SQL, table scans, application URLs, SSH or Docker socket mounts.
Check actual resource association, preserve unknown user/trace IDs, and never read
request bodies or secrets. Cache result delivery for safe network retry where useful.

## Verification and live-demo considerations

Add focused tests for completion-before-deadline cancelling work, exactly one
targeted read for one incomplete operation among 1,000, delayed/out-of-order events,
lost completion confirmed complete by a targeted read, collector/database outage,
source isolation, lease expiry, stale responses, duplicate delivery, bounded retries,
restart persistence and no periodic full-table scans. Preserve existing regressions.

Existing telemetry limits are 1,000 events/minute/source. Do NOT bypass them for
the demo. 1,000 operations emit ~1,999 lifecycle events. For a realistic live
deadline demo, forward logs concurrently and pace requests below the event budget
(e.g. ~8 operations/second). Sending all starts/completions in delayed batches after
the requests can create many unnecessary overdue checks due to collector backlog.
State this is 1,000 distinct sequential operations, not 1,000 concurrent users.

Use a fresh isolated demo directory with `CTRLZ_WORKFLOW_DEMO_DIR` below
`backend/data`, preserving the old successful run and its receipts. Do not delete
history. Existing instrumentation may be reusable if its approved rule and source
binding are unchanged; any edited rule/deadline/fields must invalidate approval.
Do not auto-approve new monitoring rules or code changes in the judge-facing flow.

Typical regression commands from CtrlZ root:

```bash
DOCKER_HOST=unix:///run/user/1000/docker.sock backend/.venv/bin/python -m pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend run build
```

CampusPass regression commands from its root:

```bash
backend/.venv/bin/python -m pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend run build
```

Leave new implementation changes uncommitted. At the end report both checkpoint
SHAs, exact test/demo results, application DB lookup counts, remaining polling
paths/limitations and final read-only Git status. Never claim hosted Render/Vercel
was migrated unless it was separately authorized and actually deployed/tested.

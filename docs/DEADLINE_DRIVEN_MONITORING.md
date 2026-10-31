# Deadline-triggered independent checks

Local checkpoints before this change:

- CtrlZ: `b6927cdb9fb1f662cd0db05a86633638ce15d23f`
- CampusPass: `ed63de400b76136ca4dc26f4e63716966dfb1b49` (empty: no safe uncommitted source changes).

New code remains local and uncommitted. No push or cloud deployment occurred.

## Operation flow

1. Approved start event arrives through existing authenticated ingestion.
2. CtrlZ persists an indexed check with the operation's original deadline.
3. Completion/cancellation cancels the check. No independent application read is
   required for that operation.
4. A separately authenticated checker maintains an SSE connection to the exact
   provisioned telemetry receiver URL, using GET instead of POST. The API checks
   only its own queue while the connection is idle, never application state.
5. At the deadline, CtrlZ leases a check containing one operation ID. The checker
   performs a parameterized read-only lookup through a unique indexed column.
6. The result is posted to existing telemetry ingestion with the exact check ID,
   lease, revision, artifact, instance and resource. Unsolicited state snapshots
   are rejected for deadline-targeted activations.
7. An overdue pending/running record can create an existing runtime incident.
   A confirmed completed record closes monitoring without a business incident.
   Missing records, access failure, unknown state or disconnection stay unknown.

The application adds no custom CtrlZ endpoint. The checker needs explicit existing
database read access. A GitHub link alone cannot grant that access.

## Reliability and limits

Checks are durable, leased for 30 seconds and redelivered at most three times.
Source/project/deployment bindings are enforced. Completion before a reply causes
the stale reply to fail. Replayed identical acknowledged results are idempotent.
Restarting CtrlZ preserves waiting/leased checks. Disabled projects are not leased.
Changed versions cancel incompatible queued work.

The normal path performs zero application reads for completed operations, and
one indexed lookup for the overdue operation. A lost connection or checker crash
may repeat a safe read after lease expiration; this is bounded at-least-once
delivery, not distributed exactly-once I/O. There is no automatic repeated
business operation or recovery. An unfinished check becomes unavailable after its
attempt budget instead of running an unbounded retry loop.

CtrlZ currently inspects its own local queue once per second while the SSE
connection is open. This is control-plane polling, not application health/API or
database polling. The checker reconnects to CtrlZ on connection loss. No database
work is performed while idle. Existing Generic HTTP/CampusPass APIs still use
their original polling contracts. Existing snapshot activations stay compatible.

Lifecycle signals are best-effort: a lost start event cannot create a deadline.
Delayed completion delivery can cause a targeted check even when business work
finished. Use durable queue/change streams or reliable event forwarding for
stronger coverage. Do not claim universal silent-failure detection.

## Configure

New UI activation selects deadline-targeted mode when an independent source is
chosen. API activation accepts `check_mode: "deadline_targeted"` and requires
`reconciliation_source_id`. Old records and omitted values retain snapshot mode.

Run the operator-configured checker on the host with the authorized SQLite file:

```bash
python scripts/workflow_deadline_checker.py \
  --database /authorized/path/jobs.db \
  --receiver https://CTRLZ-HOST/telemetry/WORKSPACE/PROJECT/DEPLOYMENT/SOURCE \
  --token-file /private/scoped-source-token \
  --table jobs --id-column id --resource-column resource_id \
  --state-column status --created-column created \
  --metrics-file /private/deadline-metrics.json
```

Configured SQL identifiers are validated; arbitrary SQL and missing unique indexes
are rejected. Query-only SQLite mode is used. The checker never accepts a database
path, table name or query from the queued event. State values use the existing
normalized workflow vocabulary.

`workflow_demo.py run` now activates deadline-targeted mode and forwards real
lifecycle events without running the full-table snapshot collector.
`workflow_demo.py watch` launches the connected checker instead of periodic scans.
Run only after the isolated demo source is approved and verified, as described in
`AI_WORKFLOW_DEMO.md`. Existing demo histories are not overwritten.

## Verification

Focused tests cover 999 cancelled checks plus one overdue item, stale replies,
lost completion reconciled as completed, unknown durable state, restart/lease
expiry, bounded attempts and source isolation. Full regression tests preserve
existing integrations.

`backend/.venv/bin/python scripts/deadline_rehearsal.py` reprocesses the genuine
previously executed 1,000-operation lifecycle evidence into an isolated CtrlZ DB,
performs a real targeted read against that fixture's actual durable records, and
uses the configured NVIDIA reasoner. It is explicitly evidence replay, not a new
load test or a hosted deployment test. Results and the receipt are saved under
ignored `backend/data/deadline-rehearsal/`.

## Observed rehearsal result

The recorded-evidence rehearsal passed: 1,000 distinct original operations,
999 completed, one incomplete; **one real indexed application lookup, zero reads
for completed operations, zero full-table state scans**. Exactly one incident
identified `resource-0001`. Real NVIDIA reasoning completed and recommendations
remain awaiting review. No recovery action executed. This was replay of genuine
prior application events plus a real durable-state read, not a new load test.

Frontend: 32 tests passed and build passed (existing bundle-size advisory).
Full backend regression results are reported in the final response.

# HTTP contracts v1

All CtrlZ endpoints except `/health` and API documentation require X-Operator-Token.
Administrative CampusPass endpoints require X-Recovery-Token. Keys come from environment
variables and are never sent to browser bundles or NVIDIA prompts.

## CtrlZ

The evaluation-driven redesign also adds:

- `GET /overview`: persisted probe snapshots/history plus measured outcome aggregates.
  Missing workflow observations remain unknown/partial even if the homepage is healthy.
- `POST /incidents/{id}/decline`: `{approval_hash, reason?}` declines the exact pending plan
  and leaves the incident escalated, without executing any operation.
- `GET /incidents/{id}/brief`: readable Markdown receipt attachment.
- `GET /demo/runs`: persisted fault-setup runs linked to independently detected incidents.
- `POST /demo/projects/{project_id}/run`: `{request_id, scenario}` where scenario is outage,
  workflow, worker_defect or reset. Requires operator authentication, global
  CTRLZ_DEMO_CONTROLS_ENABLED=true and project.demo_enabled=true. Reset preserves orders
  and incident history. Duplicate setup IDs return the existing result; conflicting reuse
  is rejected and uncertain side effects are not blindly repeated.

All these routes require X-Operator-Token. Project now accepts demo_enabled (default false).
JSON receipts include an integrity snapshot checksum; this is not a digital signature.

| Method/path | Request | Result |
|---|---|---|
| GET /health | none | liveness, NIM key presence (not validity) |
| GET /projects | none | project configurations |
| POST /projects | Project | validated upsert, including recovery contract |
| GET /incidents | none | persisted incident list |
| GET /incidents/{id} | none | complete persisted state |
| GET /incidents/{id}/receipt | none | incident, all recorded events, success flag |
| POST /incidents/{id}/approve | {approval_hash} | exact pending plan execution |
| POST /incidents/{id}/retry | {} | asynchronous reconciliation and new investigation |
| POST /incidents/{id}/replay | {candidate_id} | asynchronous isolated fixture evaluation |
| POST /continuations | {repository, requirements, context?} | 202 code import incident |
| GET /events?after=N | Last-Event-ID header optional | authenticated resumable SSE |

Project example (not secrets):
```json
{"id":"campuspass","name":"CampusPass","base_url":"http://localhost:8001","adapter":"campuspass-v1","token_env":"CAMPUSPASS_RECOVERY_TOKEN","timeout_seconds":2,"latency_ms":1500,"enabled":true,"contract":{"allowed":["restore_checkout","resume_worker","retry_order"],"approval_required":["resume_worker"],"max_actions":3,"invariants":["no_duplicate_entitlements","no_destructive_operations"]}}
```

Project registration is a trusted operator operation: its configured origin grants outbound
HTTP access to that service. Do not expose project registration to untrusted users. Adapter
names are a static registry. To support another app, implement the read/detect/precondition/
execute/verify adapter interface and register its typed operation semantics in the gate.

## CampusPass

Public: GET /events, /events/{id}, /health, /orders/{id}, /tickets/{id}/verify;
POST /checkout with {event_id, email, request_id}. Checkout reusing a request ID with
different parameters returns 409. Order IDs and ticket IDs are unguessable demo capabilities.

Authenticated: GET /diagnostics returns revision, fault, metrics and actual job logs;
GET /workflows returns paid orders missing tickets after a 1-second grace period.
POST /operations/{restore_checkout|resume_worker|retry_order} accepts
{request_id, expected_revision, order_id?}. Only retry_order accepts/requires order_id.
The same request with the same ID returns the recorded result; parameter reuse and stale
revisions return 409. Operation record and business mutation commit in one DB transaction.
POST /demo/fault accepts {fault: none|checkout_outage|checkout_slow|worker_paused|worker_defect}
only when demo mode is enabled. No SQL, shell commands, or container operations are accepted.

Invariants: a unique tickets.order_id, paid payment before issuance, unique checkout request
IDs, unique operation request IDs, and transaction-serialized SQLite writes. Default human
approval for resume_worker is enforced in CtrlZ; CampusPass independently enforces the
authenticated allowlist, revision and business preconditions.


## Generic integration and source imports

See [PORTABILITY.md](PORTABILITY.md) for the current generic Project schema, import endpoints,
dependency consent, supported runners and example HTTP contract. CampusPass-specific operations
in earlier examples are now an explicit optional adapter; new projects default to generic HTTP
with no permitted mutation.

## Target-aware Demo Lab

- `GET /demo/targets`: operator-authenticated managed repository and configured service targets,
  inspected facts and scenario `disabled_reason`. Test-file counts are discovery, not execution.
- `GET /demo/runs?target=<target-id>`: latest 30 persisted runs for exactly that target, including
  incident IDs/status. Omitting `target` retains the existing combined-history behavior.
- `POST /demo/repositories/run`: `{repository, scenario: "repair" | "injected", request_id,
  requirements?, install_dependencies?}`. Returns 202 and a persisted run; existing events/store
  record progress. Unsupported profiles and unapproved dependency setup return 422. The managed
  repository path must already be imported. Request IDs are idempotent for a target/scenario.
- Injected runs require a passing clean suite, apply one bounded mutation in a separate sanitized
  copy, then require a failing suite with the same test identities before invoking normal repair.
  Setup failures are persisted as failures with linked blocked incidents. Original snapshots are
  untouched. JSON incidents and receipts expose `injected_regression`; readable receipts disclose it.
- Generic service fault injection remains forbidden by the backend. Existing CampusPass fault
  endpoints retain their environment, adapter and project opt-in gates.

> Deadline-driven update: new activations with an independent source use the
> `deadline_targeted` mode. Start events create durable checks inside CtrlZ;
> completion/cancellation cancels them. A connected checker receives only overdue
> operation IDs and performs one indexed read per dispatched operation. The
> snapshot collector documented below remains a compatibility option, not the
> default new demo path. See `DEADLINE_DRIVEN_MONITORING.md` for exact behavior.

# AI Workflow Observability

CtrlZ can audit a connected repository for asynchronous completion gaps, persist
reviewable monitoring proposals, and compile a constrained observability patch.
It can then monitor individually correlated operations using authenticated events
and independently collected durable state. Existing HTTP projects, CampusPass
operations, provider ingestion, runtime incidents and repository repair coexist.

No Git commits, pushes, application deployments or production mutations are part
of this workflow. Approval of monitoring is not approval of recovery or deployment.

## Onboarding and source evidence

1. Connect a **Repository + Deployment Monitoring** project. HTTP onboarding is
   unchanged. Identify the deployment/environment and source credentials.
2. Optionally add an independent reconciliation source in deployment settings.
   The existing project card provisions a separate server-side key for each source.
3. Choose **AI Workflow Audit · optional** on the project card.
4. Select a deployment and choose **Analyze workflows for silent failures**.
   An exact configured Git commit is required for Git source retrieval. CtrlZ
   validates it against the expected repository using read-only GitHub REST or an
   administrator-allowlisted local Git object. It never fetches, checks out or
   executes repository source on the host.
5. Alternatively supply a small ZIP snapshot. ZIP paths, file types, symlinks,
   expanded size and sensitive paths are checked. Its source is content-pinned;
   Git identity and deployment association are explicitly unverified. No fake Git
   commit is created for a snapshot.

Bounds: at most 120 safe snapshot files/1 MiB, 64 KiB per file, 2 MiB ZIP request,
32 remotely retrieved files and a bounded model context. Dependencies, databases,
credential files and generated directories are excluded. An incomplete tree is
not described as exhaustive coverage.

Python AST inspection enumerates actual functions, arguments, source locations,
generator status and simple swallowed-exception observations. Bounded source,
tests, manifests, queue/state/logging context and deployment capabilities go to
the existing NVIDIA/CrewAI provider. Source comments and logs are untrusted data.
Sensitive strings are redacted before model input. Audit failures and invalid
provider output remain blocked records, not deterministic fake AI answers.

Python ordinary synchronous/asynchronous functions are initially patchable.
FastAPI code can be audited, but decorated route handlers, generators, ambiguous
function names and unsupported anchors are refused by the patch compiler.
JavaScript/TypeScript/Node/Next.js source can be inspected for advisory proposals;
this release does not generate or verify Node instrumentation patches.

## Proposal and exact approval

Each workflow includes source evidence, the start/completion conditions, deadline,
existing and missing signals, proposed technique, approved correlation fields,
permissions, overhead, privacy, independent verification and uncertainty.

Classifications distinguish confirmed, suspected and possible gaps, sufficient
existing observability and insufficient evidence. Deadlines are proposals, not
inferred contractual SLAs. Static analysis cannot prove all silent-failure paths.

The developer can approve, reject or edit the completion description, deadline,
technique and collected fields. Saved edits invalidate the prior approval. Optional AI hook mappings outside the declared collection scope are removed before review and the narrowing is disclosed. Unsupported identity associations (for example job ID as user ID) are omitted; they never become inferred user identity.
Approval binds project configuration, deployment/environment, exact audited
revision/content digest, workflow rule, correlation mappings, identity and time.
Generation revalidates that binding and the immutable source snapshot. A project
or source change before generation requires renewed review. Generation requests
are reserved exclusively, preventing duplicate concurrent jobs.

Technique options:

| Technique | Actual support |
| --- | --- |
| Existing telemetry | Approved normalized lifecycle events; requires a configured producer/forwarder |
| Zero-code instrumentation | Recommendation only; no automatic OpenTelemetry installation or native OTLP receiver |
| External read-only reconciliation | Separate authenticated collector; included SQLite snapshot collector requires operator-authorized existing records |
| Generated instrumentation | Constrained Python hooks plus standalone stdlib probe and offline Docker verification |
| Insufficient evidence | Explain missing facts; no coverage or patch claimed |

An existing sufficient state source can be approved without generating a patch.
For critical gaps, independent durable-state reconciliation is preferred over
declaring missing logs to be failed transactions.

## How instrumentation is generated and verified

The model first proposes typed hooks and monitoring rules. After approval it selects the exact approved hook indices and explains the observation strategy; it cannot rewrite those mappings or return executable code. A deterministic compiler:

- Adds an import and observation decorators at the reviewed function anchors.
- Adds a standalone `_ctrlz_observe.py` in the relevant module directory.
- Preserves original business statements and verifies AST equality after removing
  only the generated import/decorators.
- Leaves original tests, manifests, transaction boundaries, retries, authorization,
  calculations, business return values and exceptions untouched.
- Refuses generators, pre-decorated/ambiguous functions, helper collisions,
  sensitive field mappings and detectable private credentials in exported source.

The probe is disabled by default. With `CTRLZ_OBSERVE_ENABLED=1` and an explicit
`CTRLZ_OBSERVE_REVISION`, it emits bounded structured events to a daemon stdout
writer. The queue holds at most 256 events and drops on saturation. It has no
network exporter, no retry loop and no request/response-body capture. Export
failures are isolated from the original operation. Original exceptions propagate.
Optional user correlation requires a private `CTRLZ_OBSERVE_PSEUDONYM_KEY`; without
one the probe omits the user rather than emitting a raw identity.

There is still resource/latency overhead. Decorators alter function identity and
best-effort lifecycle delivery can lose records on crash, full buffers or blocked
stdout. This does not give exactly-once observation or mathematical equivalence.

Verification reuses the existing Python Docker sandbox without changing Scenario
A's repair logic. Baseline and candidate run the same immutable original tests
offline, with read-only source mounts, resource limits and no host execution.
Dedicated probe tests check emission, return identity, export-failure isolation,
exception propagation and async/disabled behavior. Original tests also exercise
representative persistent-state outcomes. Passing tests support equivalence only
for tested behavior; the original business AST is checked independently.

Declared application dependencies require a separate explicit setup authorization.
No manifest/lockfile is silently changed. Dependency setup and offline test phases
are separate. Missing Docker/images, unsupported runners, failed baselines or
failed candidate checks block a verified artifact. There is no host-test fallback.

The UI displays actual test counts/checks, changed files, full unified diff,
downloadable patch and an instrumented-source ZIP. Failed and unverified results
are labeled. Downloading does not deploy anything.

## Deployment and activation

The owner reviews and deploys the artifact separately. Configure the probe and
existing generic JSONL collector on the selected host; credentials stay server-side.
For a hosted Git deployment, activation requires the actual configured deployed
commit. Its parent must be the audited commit and its changed files/content must
match the reviewed instrumentation patch. Additional source changes require a new
audit. Provider/API access failures block verification, not silently activate it.

For the explicitly local demo, the actual extracted candidate tree is pinned by a
`sha256:` content revision. No GitHub publication is asserted. An authenticated
collector/operator is trusted to identify the deployment correctly; this is not
hardware-backed remote attestation.

Record the deployed revision and independent state source in the audit panel.
Status is **deployment_observed** until matching authenticated events arrive. Instrumented workflows also need an actual authenticated start/completion/failure signal from the application source; a reconciliation-source heartbeat alone cannot prove the patch is emitting.
Wrong rule ID, instrumentation digest, revision, source, target or unapproved
correlation fields are rejected. No evidence means unverified/degraded coverage,
never a healthy transaction. Existing-telemetry/reconciliation-only activation
uses the exact approved proposal hash as its instrumentation contract identifier.

After deployment, removal means disabling observation, stopping the configured
collector and reverting the reviewed hook/helper changes through the owner's
normal deployment process. CtrlZ never performs that deployment automatically.

## Events, reconciliation and affected resources

The existing bounded source-authenticated runtime ingestion accepts an optional
typed `workflow` field. Kinds include started, completed, failed, cancelled,
timeout, reconciled, reconciliation_failed and heartbeat. IDs are optional except
for an actual operation instance on operation events. Missing identities are not
invented. Project/environment/source binding comes from the authenticated route.
Users are pseudonymized before persistence and AI input.

The application source cannot claim authoritative reconciliation: that requires
a different independently authorized source key. The SQLite collector reads an
explicitly selected existing database in `mode=ro`, sets query-only mode, validates
table/column identifiers and paginates every record. It accepts no SQL expressions,
does not need a custom application API and performs no business mutation.
Its deployment-side permissions and column semantics must be reviewed by the
operator. It defaults to one bounded snapshot; `--interval 15` keeps observing
pending operations, sends changed terminal states, and emits a heartbeat on empty
cycles. It is not a native queue/database change-data-capture integration.

The durable instance table indexes active state/deadline. A persisted scan cursor
prevents the first page of uncertain operations from hiding later operations.
Detection is not capped at the latest 200 rows. Duplicate events are idempotent;
delayed starts do not undo completed operations. State and approval survive CtrlZ
restart. Three new incidents per proposal per minute bound model admission;
successful operations invoke no model. Similar occurrences retain distinct
operation/resource identities rather than collapsing unrelated resources.

An overdue authoritative pending/running record with fresh independent evidence
can create a workflow runtime incident. An explicit fresh failure also qualifies.
An overdue start without authoritative evidence produces a coverage warning, not
a confirmed failed transaction. Stale sources and reconciliation errors leave
completion unknown. Cancelling/completing an operation is not an executed CtrlZ
recovery and does not automatically produce a successful recovery receipt.

Records are bounded to 100,000 per proposal. Terminal records expire after seven
days by default (`CTRLZ_WORKFLOW_RETENTION_DAYS`, 1–90); unresolved operations are retained with backpressure rather than silently
discarded. The runtime pipeline's existing seven-day/10,000 raw-event limits and
per-source rate limits still apply. This is a local prototype, not an unbounded
production telemetry store. The record cap is configurable with `CTRLZ_WORKFLOW_MAXIMUM_RECORDS` (1,000–1,000,000).

## Incidents and recovery

Workflow findings use the existing runtime incident engine, source context,
NVIDIA/CrewAI assessment, runbooks, deterministic recommendation policy, review
binding and receipts. Evidence includes the approved definition, source snapshot,
observed deployment revision, specific resource, pseudonymous user if actually
supplied, and authoritative observation versus missing-delivery uncertainty.

Read-only recommendations can suggest resource-specific investigation, separately
authorized safe retry, code investigation or escalation. A single incomplete job
does not justify a global restart. No new operational execution permissions are
granted. Existing CampusPass retry/resume operations remain confined to its
separate adapter/contract. A source defect can be exported to the existing repair
workflow as context without bypassing sandbox or acceptance restrictions.

## Reproduce the isolated 1,000-operation demo

Prerequisites: existing Python venv, frontend dependencies, configured NVIDIA
credentials, rootless Docker and the existing Python sandbox image. Keep existing
`.env` credentials; do not regenerate them. If the sandbox image is absent, obtain
explicit approval before building/downloading it:

```bash
docker -H unix:///run/user/1000/docker.sock build -t ctrlz-sandbox:local -f backend/Dockerfile.sandbox backend
```

From CtrlZ root:

```bash
DOCKER_HOST=unix:///run/user/1000/docker.sock backend/.venv/bin/python scripts/workflow_demo.py serve
```

In another terminal:

```bash
backend/.venv/bin/python scripts/workflow_demo.py audit
backend/.venv/bin/python scripts/workflow_demo.py status
```

Open `http://localhost:18052/#projects` and sign in using the existing private local
admin credentials. This is a separate local API/dashboard and SQLite history;
ports 5173/8000, CampusPass and Scenario A are not restarted. The fixture ZIP is
supplied locally and content-pinned, not falsely described as a published GitHub
repository. Invalid model attempts remain blocked in audit history; a deliberate
new attempt is available with `audit --retry-audit`.

1. Open **AI Workflow Audit · optional** on the document-processing project.
2. Review the discovered completion gap and lost cross-queue user correlation.
   The caller ID exists at submission but is not in the durable job table.
3. Review/edit the deadline, source anchors and approved fields. Approve the rule.
4. Choose **Generate and verify instrumentation**. No dependency setup is needed
   by this stdlib fixture. Inspect the unchanged business code plus new decorators,
   the actual baseline/candidate/instrumentation test checks and the diff.
5. After a passing artifact, run the following explicitly local demonstration:

```bash
DOCKER_HOST=unix:///run/user/1000/docker.sock backend/.venv/bin/python scripts/workflow_demo.py run
backend/.venv/bin/python scripts/workflow_demo.py status
backend/.venv/bin/python scripts/workflow_demo.py export
```

To keep independent source coverage fresh, run this in another terminal:

```bash
backend/.venv/bin/python scripts/workflow_demo.py watch
```

Stop `watch` with Ctrl+C. Missing or stopped collectors become degraded coverage;
they do not turn every operation into a failed business transaction.

`run` requires an actually approved and tested patch. It installs only the
generated artifact in a separate resource-bounded container with **no external
network**. A client inside the container sends **1,000 distinct sequential HTTP
submissions**, not a 1,000-concurrent-user load test. Every submission returns 202,
999 jobs complete and `resource-0001` deliberately stays pending without an
exception. Health remains 200. Actual generated lifecycle output is forwarded
through source authentication with rate-limit backpressure, then an independent
read-only collector observes all 1,000 durable rows.

The generated probe must emit real start/completion events. Independent state
establishes the silent failure; missing logs alone do not. Verify the specific
resource and any reliably captured pseudonymous user in the runtime incident.
Review the real diagnosis/recommendations and receipt. No application repair,
global restart or other 999-job mutation is performed.

Artifacts, private session files, source ZIP, operation counts, event counts,
managed source, test reports and receipts live below ignored
`backend/data/workflow-demo/`. To stop only the owned fixture container:

```bash
DOCKER_HOST=unix:///run/user/1000/docker.sock backend/.venv/bin/python scripts/workflow_demo.py stop-fixture
```

Ctrl+C in the `serve` terminal stops only that demo API/frontend. Histories and
records are preserved. For another run, first stop the old fixture, `watch` and `serve`. Preserve the old
directory, then `export CTRLZ_WORKFLOW_DEMO_DIR="$PWD/backend/data/workflow-demo-next"`
in each new terminal before repeating `serve`, `audit`, UI review and `run`. The
new directory must be a dedicated child of `backend/data`. The script refuses to
overwrite an existing 1,000-operation run.

## Known limits and troubleshooting

- A GitHub link/public URL alone does not provide runtime access. Hosting/log or
  collector permissions must still be granted. No cloud connection is fabricated.
- The initial patch compiler supports a narrow, safe Python function scope, not
  arbitrary middleware/transaction/queue modifications or Node patches.
- The source context is bounded. Some workflows may be missed or require more
  evidence. A proposal is not proof of intended business behavior.
- If audit is blocked, inspect its typed error. Missing Git revision, provider
  access or invalid schema must be corrected; there is no silent mock fallback.
- If generation is blocked, inspect source/approval drift, Docker/image availability,
  original test validity and separately approved dependency requirements.
- A plain lifecycle timeout is not authoritative business failure. Configure an
  approved state source or accept explicitly limited best-effort coverage.
- The SQLite collector expects normalized pending/running/completed/failed/cancelled/unknown state values; other state machines require a reviewed adapter.
- SQLite source collection is read-only and operator-configured; PostgreSQL,
  queues, OTLP, native Render/AWS collection and browser telemetry require their
  own adapters. Existing generic sources remain available.
- No reliable user ID means unknown user. IP/time/user-agent are not identity.
- No event or matching deployed revision means monitoring is not verified active.

## Short judge walkthrough

Show the optional audit beside existing HTTP/runtime integrations. Explain the
source evidence and proposed rule, approve it, inspect the generated diff and real
offline test results, then run the 1,000-operation command. Show healthy HTTP and
999 completed jobs alongside the one independently observed incomplete resource.
Open the automatically created runtime incident, explain observed facts versus AI
hypotheses, show the specific operation/user association, and review the receipt.
The recommendation remains a human-reviewed proposal, not an executed repair.

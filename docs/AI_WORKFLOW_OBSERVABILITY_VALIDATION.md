# Implementation and observed validation

## Local state and preservation

Both repositories were audited before changes. CtrlZ's authorized local checkpoint
is `8d0f94e65581d9553ff72ba45494d627a8832ca5`; CampusPass remains at
`a20c0c30a83c2ebefd4786e56da7164e5dfb67ed`. No commits, staging, pushes, fetches,
pulls, branch changes or remote modifications occurred during this feature phase.
The checkpoint was created in the separately authorized preceding phase.

CampusPass source was not modified. Its pre-existing tracked database, bytecode,
dependency/build artifacts remain preserved. Existing environment files were read
privately and not overwritten. No cloud service was changed. The new demonstration
uses ports 18050/18052; existing 8000/5173 and 8001/5174 still returned HTTP 200.

Scenario A continuation, managed repository importer, repair sandbox, worktree
logic, fixtures, acceptance tests and demonstration UI were not edited. Existing
non-Docker Scenario A checks passed. Eight existing optional integration tests
remain skipped; they are not represented as executed repair acceptance.

## Reused architecture

The extension reuses workspace/account authorization, runtime source credentials,
strict ingestion and rate limits, persistent incident/events, the periodic scan,
NVIDIA/CrewAI configuration, source evidence, recommendation policy/review,
flight recorder, receipts and the existing Docker Sandbox. It adds tables without
reinterpreting existing project records or migrating away their history.

The AI audits bounded source and tests, proposes workflow rules and hook anchors,
and selects the exact approved hook indices for generation. A deterministic
compiler produces observability-only source changes. Original business AST and
tests are preserved. Imported source is executed only in resource-limited Docker
containers with offline test networking, not on the host.

## Actual test results

| Scope | Observed result |
| --- | --- |
| CtrlZ backend full suite | **206 passed, 8 skipped, 0 failed** |
| New workflow tests | **44 passed**, including real Docker patch verification |
| CtrlZ frontend | **32 passed**, 7 files |
| CtrlZ frontend production build | Passed; existing large-chunk advisory |
| CampusPass backend regression | **14 passed**, one existing deprecation warning |
| CampusPass frontend proxy tests | **8 passed** |
| CampusPass frontend production build | Passed |
| Generated artifact baseline | **5 original tests passed** in offline Docker |
| Generated artifact candidate | The same **5 original tests passed** |
| Candidate with dedicated instrumentation tests | **9 passed** |
| Source/test immutability and business AST checks | Passed |

Unit/API tests use an explicitly labeled deterministic provider and, where stated,
mocked sandbox reports for state-machine cases. A separate real Docker test runs
the baseline/candidate/probe checks. The live observations below used the genuine
NVIDIA provider. The pre-existing Python sandbox image was built only after the
user explicitly authorized its Docker downloads; no host dependency install was
performed and no application dependencies were added.

## Actual live demonstration

- The owner-approved local fixture source was imported as an inert ZIP and pinned
  by content digest. GitHub publication/identity was explicitly unverified; no
  fake commit, checkout or repository was created.
- Real NVIDIA audit identified the deliberate early return leaving a pending job
  and the lost originating-user association across its queue boundary.
- Invalid provider/schema attempts were blocked and retained in history. Fixes
  addressed NVIDIA's unsupported `propertyNames` schema keyword, source-path
  syntax, redundant overbroad mappings and incorrect job-to-user associations.
- The model initially suggested zero-code monitoring. That unsupported strategy
  was explicitly revised into a reviewable instrumentation proposal. Optional
  unsupported mappings were removed with disclosed warnings. No inferred rule
  was silently approved and no job ID was used as a user ID.
- The human operator approved the displayed five-second controlled-demo rule and
  clicked generation in the actual UI. Identity/time/hash are persisted.
- NVIDIA selected the exact approved hooks; the compiler generated `jobs.py`
  decorators and `_ctrlz_observe.py`. No business statement or test was changed.
  All six verification checks passed and the artifact awaited developer deployment.
- A separate, explicitly authorized local container ran that exact artifact, with
  its extracted source digest checked against the reviewed candidate. The container
  has no external network and no host Docker socket mount.
- **1,000 actual sequential HTTP submissions** returned 202 and produced 1,000
  distinct jobs. **999 completed, one remained pending; health stayed HTTP 200.**
- The generated probe emitted **1,000 started and 999 completed** events. There
  were **zero explicit error events**, and no raw email values in those events.
- The collector respected existing source rate limits, including a real
  backpressure wait. No limits were bypassed for the demo.
- An independently authenticated read-only SQLite collector visited all 1,000
  durable rows, including the oldest incomplete operation, with no business writes.
- Exactly **one** runtime incident was created for **resource-0001** and its actual
  job ID. Its pseudonymous user was checked against the real submission identity
  and both pseudonymization steps. Missing request/trace IDs remained unknown.
- Real NVIDIA diagnosis identified the deliberately pending branch. Recommendations
  remain **awaiting_review**, with execution disabled. A code-patch recommendation
  without independently mapped Git source was conservatively blocked; investigation
  and configuration recommendations remain reviewable. No recovery was executed.
- Restarting only the CtrlZ demo monitor preserved approvals, workflow instances,
  the incident and receipt. The application container was not restarted. Continuous
  read-only reconciliation then refreshed coverage to monitoring_active.
- Final counts remained 999 completed/one pending, with exactly one incident and
  no operation intent. Original fixture source remained byte-identical to the
  imported baseline. The other 999 operations were not disturbed.

The actual incident is `af81a8eb-089c-4e9a-be66-06ba9e2640e4` at
http://localhost:18052/#incident/af81a8eb-089c-4e9a-be66-06ba9e2640e4.
Its receipt correctly has `success=false`: detection/diagnosis is not a completed
business recovery. This controlled fixture is intentionally left pending.

Evidence below ignored `backend/data/workflow-demo/` includes `operations.json`,
`lifecycle.json`, `live-checks.json`, approval/generation records, actual source/diff
artifacts, test reports, receipt JSON/Markdown and genuine browser screenshots.
Private tokens and session files are not presentation material.

## Exact implementation files

New backend modules:

- `backend/ctrlz/workflow_models.py`
- `backend/ctrlz/workflow_source.py`
- `backend/ctrlz/workflow_reasoning.py`
- `backend/ctrlz/workflow_patch.py`
- `backend/ctrlz/workflow_probe.py`
- `backend/ctrlz/workflow_store.py`
- `backend/ctrlz/workflow_service.py`
- `backend/ctrlz/workflow_routes.py`

Minimal shared integration:

- `backend/ctrlz/main.py`: install the optional service/routes and reconcile during
  repository-project scans. The service variable deliberately differs from the
  HTTP workflow response variable to preserve both scan branches.
- `backend/ctrlz/runtime_models.py`: optional typed workflow payload.
- `backend/ctrlz/runtime_store.py`: bounded ID lookup utility.
- `backend/ctrlz/runtime_monitoring.py`: approved workflow ingestion, no duplicate
  runtime detection, workflow context/handoff, active-incident project status.
- `backend/ctrlz/brief.py`: include the approved workflow and affected operation.
- `frontend/src/api.ts`: additive workflow evidence type.
- `frontend/src/components/RuntimeProjectCard.tsx`: optional audit panel.
- `frontend/src/components/RuntimeProjectForm.tsx`: optional audit guidance and
  independent reconciliation source configuration.
- `frontend/src/components/RuntimeIncident.tsx`: affected workflow/resource/user.

New frontend/tests/tools/docs:

- `frontend/src/components/WorkflowAudit.tsx`
- `frontend/src/workflow-observability.test.ts`
- `backend/tests/test_workflow_observability.py`
- `examples/workflow-observability/jobs.py`
- `examples/workflow-observability/app.py`
- `examples/workflow-observability/test_jobs.py`
- `scripts/workflow_demo.py`
- `scripts/workflow_sqlite_collector.py`
- `docs/AI_WORKFLOW_OBSERVABILITY.md`
- `docs/AI_WORKFLOW_DEMO.md`
- This validation report.

## Boundaries and incomplete scope

Patch generation supports narrow ordinary Python sync/async function anchors.
Decorated route handlers, generators, ambiguous functions and arbitrary Node
patches are refused. JavaScript/TypeScript inspection is advisory. Native OTLP,
automatic OpenTelemetry installation, database/queue providers beyond the reviewed
SQLite collector, browser error collection and universal hosting integration are
not implemented by this feature.

Real GitHub audit/activation logic uses pinned REST source and exact patch-content
checks, with mocked-provider regression tests. The new fixture's live demo used a
content-pinned snapshot rather than a published deployed Git commit. That is not
claimed as a live GitHub deployment integration test.

State reconciliation needs explicitly authorized records and reviewed semantics.
The SQLite collector expects the normalized state vocabulary. Missing or stale
telemetry produces degraded coverage/uncertainty, not proof of failure. Probe
delivery remains best-effort, and functional equivalence is supported by tested
behavior and AST checks, not a mathematical guarantee.

No automatic repair, targeted retry adapter, production deployment, global restart
or business recovery is added. CampusPass's original contracts remain separate.
User approval of instrumentation never grants those permissions.

Startup commands, safe stops and repeat-run directory isolation are in
[AI_WORKFLOW_OBSERVABILITY.md](AI_WORKFLOW_OBSERVABILITY.md). Exact judge-facing
actions are in [AI_WORKFLOW_DEMO.md](AI_WORKFLOW_DEMO.md).

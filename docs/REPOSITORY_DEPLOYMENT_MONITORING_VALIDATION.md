# Local implementation and validation report

## Result

Repository + Deployment Monitoring is implemented as a new CtrlZ project type.
The existing HTTP service integration and CampusPass preset remain available.
A real isolated CampusPass worker failure reached the new runtime ingestion path,
was correlated with source from the user's fork at its deployed revision, and was
diagnosed by the configured NVIDIA model. Recommendations remain read-only.

The main incident is `47daa93a-9e90-4319-8438-931c34f3c649`:
http://localhost:5173/#incident/47daa93a-9e90-4319-8438-931c34f3c649

It is awaiting review. Its receipt has `success=false`: no operation, code patch,
production deployment, rollback or verified production recovery has occurred.

## Checkpoints and Git authorization

| Repository | Branch | Before | Safe checkpoint |
|---|---|---|---|
| CtrlZ | main | `08f66e7c565ea42d2dd26e992cb5681326e74a9e` | `2233aea096eb45d1610c9b055b9ce1971746b980` |
| CampusPass | main | `39727a3ab6c15d8e585b721ce9c60bb0a7f4c5e5` | `f4b3e817e6c80075c91f23f6c2a6cbb3f4e6d0a1` |

Messages: `chore: checkpoint CtrlZ before deployment monitoring` and
`chore: checkpoint CampusPass before deployment monitoring`.
Both repositories were inspected for staged changes/conflicts before staging;
there were none. Explicit reviewed source paths were staged and inspected.
Credentials, runtime SQLite files, generated dependencies/build files, bytecode,
private evidence and the compatibility symlink were excluded. The old Scenario B
local guide remained uncommitted because it contains local transaction references.

The user later explicitly authorized a CampusPass push. Only checkpoint `f4b3e81`
was fast-forward pushed to `AtharvMitt/CampusPass` main. CtrlZ was not pushed.
There was no fork synchronization, fetch, pull, upstream merge, rebase, branch
switch or force push. No further source commits were made after the checkpoints.
All new integration changes remain uncommitted in CtrlZ. CampusPass has no new
monitoring-related source edits; its remaining changes are pre-existing generated
runtime/dependency/build artifacts and database history.

## Architecture reused

Existing workspace/account authorization, Project records, incident/event store,
periodic scan, NVIDIA/CrewAI configuration, Chroma runbooks, authenticated SSE,
receipt/checksum exports, GitHub normalization, source-path checks and the existing
Repository repair UI are reused. New raw telemetry tables are additive; existing
projects/incidents/configurations are not migrated away or deleted.

Old records default to HTTP semantics. A project ID cannot be converted to a
new integration type by overwriting it. Repository monitoring needs no base URL
or health endpoint and has no operational execution contract.

## New modules and exact source files

Backend modules added:

- `backend/ctrlz/runtime_models.py`: repository, multiple deployment/source and
  event/recommendation schemas; explicit unknown fields and source hints.
- `backend/ctrlz/runtime_security.py`: private scoped source credentials,
  pseudonymization and redaction before storage and reasoning.
- `backend/ctrlz/runtime_store.py`: additive normalized event storage, durable
  event identity, quotas and bounded raw-event retention.
- `backend/ctrlz/runtime_connectors.py`: generic event receiver and signed
  Vercel JSON/NDJSON normalization; observed relative JS frames only.
- `backend/ctrlz/runtime_source.py`: bounded fixed-origin GitHub/Vercel reads,
  exact-revision source and optional trusted read-only local Git evidence.
- `backend/ctrlz/runtime_monitoring.py`: grouping/detection, source correlation,
  AI assessment, deterministic recommendation checks, exact review binding,
  source-cache provenance and sanitized repair handoff.
- `backend/ctrlz/runtime_routes.py`: source provisioning, telemetry, coverage,
  connection test, review and repair-context APIs.

Shared backend modules modified minimally:

- `models.py`: distinct project type; old HTTP defaults preserved.
- `main.py`: register runtime routes/monitor; preserve existing HTTP scan; reject
  project-type replacement; runtime-only re-investigation states.
- `access.py`: source-key ingestion dispatch bound to a known workspace; source
  credentials cannot access account/project/review APIs.
- `engine.py`: route runtime incidents to read-only investigation.
- `reasoning.py`: add runtime assessment using the existing provider; code-repair
  method is unchanged.
- `insights.py`: runtime coverage without fabricated health probes.
- `brief.py`: include runtime/source/recommendation context in Markdown receipts.

Frontend modules added:

- `frontend/src/components/RuntimeProjectForm.tsx`
- `frontend/src/components/RuntimeProjectCard.tsx`
- `frontend/src/components/RuntimeIncident.tsx`
- `frontend/src/runtime-projects.ts`
- `frontend/src/runtime-projects.test.ts`

Shared frontend modules changed:

- `App.tsx`: render the new project cards and pass authentication to onboarding.
- `api.ts`: additive runtime types, optional HTTP origin for the new project type.
- `components/ProjectDialog.tsx`: retain HTTP/CampusPass and add new onboarding.
- `components/SignalCard.tsx`: accurate runtime summary with unknown health.
- `components/IncidentWorkspace.tsx`: reuse routing/receipt loading; runtime view;
  reject a stale receipt when its incident ID differs from the selected incident.
- `presentation.ts`: runtime title and the receipt identity guard.

Tools/fixtures/tests/docs added:

- `scripts/runtime_log_collector.py`
- `scripts/runtime_demo.py`
- `scripts/campuspass_runtime_demo.py`
- `scripts/campuspass_runtime_producer.py`
- `examples/runtime-monitoring/app.py`
- `backend/tests/test_runtime_monitoring.py`
- `backend/tests/test_runtime_collector.py`
- `docs/REPOSITORY_DEPLOYMENT_MONITORING.md`
- This report.

No dependency manifests or lockfiles needed changes.

## Actual tests executed

| Command / scope | Final result |
|---|---|
| CtrlZ backend `python -m pytest -q` | **162 passed, 8 skipped, 0 failed** |
| CtrlZ frontend `npm --prefix frontend test` | **27 passed, 0 failed**, 6 test files |
| CtrlZ frontend `npm --prefix frontend run build` | Passed; existing large-chunk advisory remains |
| CampusPass backend `python -m pytest -q` | **14 passed, 0 failed** |
| CampusPass frontend production build | Passed |
| Python syntax compilation for new modules/scripts | Passed |
| `git diff --check` | Passed |

Backend tests ran on the host for their real local HTTP fixtures; databases were
isolated. Eight opt-in Docker acceptance tests were skipped. Their execution is
not claimed. CampusPass has no frontend test script.

The first existing-backend compatibility run passed all 112 original tests.
Final tests include 50 additional backend cases and eight additional frontend
cases. Existing generic registration/monitoring/contracts, Scenario B approval/
verification/idempotency, Scenario C outage recovery and existing incident/account
APIs remain covered. Scenario A's existing non-Docker tests passed; its actual
Docker repair acceptance was not rerun here.

Unit tests use explicit mocked providers and deterministic reasoners. They are
separate from the live NVIDIA and GitHub observations below.

## Real local evidence

1. The normal applications remained at ports 5173/8000 and 5174/8001.
2. CampusPass Python source was checked against pushed revision `f4b3e81` before
   starting a separate worker/API process on port 18031 with a separate database.
3. A real simulated paid checkout invoked the unchanged `worker_defect` fixture.
   The real UUID-to-integer formatter raised ValueError and the job was stored failed.
4. A read-only producer observed the actual diagnostics record, removed the order
   reference, retained unknown user/stack/occurrence fields, and wrote JSONL.
5. The independent generic collector sent one event through source-authenticated
   HTTP ingestion. One runtime incident was created automatically.
6. GitHub REST validated commit `f4b3e81` in `AtharvMitt/CampusPass` and returned
   the actual formatter source. Operator-configured source hints and unknown
   failing frame were clearly labeled. Initial requested source context was partial.
7. NVIDIA `nvidia/nemotron-3.5-lightning-30b-a3b` through CrewAI produced a diagnosis
   identifying the formatter defect and reviewable recommendations.
8. The main source-monitoring incident is left awaiting a fresh human review;
   execution permissions are empty and verification remains not run.
9. The supplemental reservation fixture produced a genuine HTTP 500, actual
   relative Python frame and server request ID, proving the generic file collector.
   Its first invalid model citation was rejected and retained in history.
10. Repeated anonymous GitHub access later hit its API rate limit. The actual UI
    connection test reported `github_rate_limited`, rather than claiming access.
    Re-investigation reused only prior immutable evidence for the same repo/SHA,
    with the failed refresh and cache provenance displayed.
11. Browser onboarding created a separate project with two environments and left
    it disabled until source credentials/telemetry are configured.
12. Programmatic browser review was exercised, including an exposed stale receipt
    bug that was fixed and regression-tested. The review records explicitly say
    `executed=false`. This is not represented as a physical human approval.
13. Repair-context export and the existing Repository repair link were exercised;
    no import, continuation, patch or repair execution was started.
14. Browser export controls were invoked; the user declined some downloads. Final
    JSON/Markdown/context export checks were instead saved directly in the
    workspace. No further browser downloads are required or triggered.
15. Final smoke checks confirmed the original Scenario B resolved receipt, primary
    CampusPass health/fault-cleared state, pending new review, and no runtime
    operation intent or false successful recovery.

The stale receipt guard prevents old incident evidence/actions from being rendered
while a newly selected incident's receipt is loading. Review bindings still
validate incident, recommendation, configuration, revision/source and telemetry
snapshot. Reinvestigation clears the current review display while retaining its
audit record; a stale or declined decision never executes an operation.

## Providers and limitations

Generic ingestion and selected JSONL file collection are implemented and observed
live locally. Vercel signed JSON/NDJSON reception and read-only metadata interfaces
are implemented and mocked-provider tested, **not live Vercel verified**. No token
was present, no Vercel deployment was made, and no public HTTPS receiver/tunnel was
created. The user is handling deployment separately. Drains require an eligible
paid plan; source/provider configuration is still required after deployment.

AWS uses generic collector compatibility only; native CloudWatch and native OTLP
are not implemented. Client-side browser instrumentation and per-user recovery
are not implemented. Reliable supplied IDs can support pseudonymous correlation,
but this CampusPass diagnostic feed does not supply them, so affected users remain
unknown. A shared deployment cannot automatically be rolled back for one user.

No universal root-cause correctness, production readiness, automatic repair or
actual rollback is claimed. AI outputs remain hypotheses/recommendations for
review. Exact-source validation is not independent attestation that every running
process uses that SHA; the local fixture verifies its tracked source at startup.

## Startup and judge walkthrough

Full commands, telemetry schema, limits, credential setup, disable/reset behavior,
Vercel requirements and troubleshooting are in
`docs/REPOSITORY_DEPLOYMENT_MONITORING.md`.

Short judge sequence:

1. Open Projects and compare Generic HTTP/CampusPass with the new Repository +
   Deployment option. Show CampusPass's fork, staging deployment and pinned SHA.
2. Show the isolated deployment and explain that the primary storefront is unchanged.
3. Run the disclosed isolated `campuspass_runtime_demo.py trigger` with its producer
   and collector running. A real worker failure is observed, not a fake UI incident.
4. Follow the automatically created/grouped runtime incident. Show observed facts,
   unknown user/stack fields and source at the actual configured revision.
5. Show the real NVIDIA hypothesis and alternatives. Explain source hints versus
   observed frames and GitHub cache/rate-limit status honestly.
6. Review the exact recommendation. Acceptance records review only; no deployment
   action or recovery is claimed. Stale evidence requires re-investigation.
7. Show the existing repair-workflow link and sanitized context; do not start a
   repair against the teammate's working tree.
8. Open Flight recorder and Receipt. `success=false` is correct for this read-only
   integration. Export deliberately only if the operator wants a download.

## Final Git status and running state

Exact read-only status snapshots are under
`backend/data/runtime-demo/final-validation/git-status-ctrlz.txt` and
`git-status-campuspass.txt`. Both indexes are empty. CtrlZ remains at checkpoint
`2233aea`; new integration work is local/uncommitted. CampusPass remains at pushed
checkpoint `f4b3e81`, with the pre-existing generated/database changes uncommitted.
The lowercase sibling symlink still points to the original CampusPass checkout.
No credentials/configuration or customer history was deleted or overwritten.

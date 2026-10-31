# Repository + Deployment Monitoring

CtrlZ can analyze a connected repository and monitor its deployed applications
through supported observability integrations, correlate runtime failures with
source revisions, and propose controlled recovery actions for review.

This is a new project type. Generic HTTP and the CampusPass preset keep their
original registration, monitoring, execution contracts and approval behavior.
Existing project records default to HTTP. Changing an existing project's type is
rejected; use a new ID so history is not reinterpreted.

## What is implemented

- GitHub repository identity plus multiple independently configured deployments.
- Structured project onboarding, metadata connection tests and coverage cards.
- Workspace/source-authenticated event ingestion; normalized durable evidence.
- Automatic exception and repeated-failure detection, grouping and deduplication.
- Exact-revision GitHub source retrieval, optional trusted local Git evidence,
  and clearly labeled operator source hints when stack frames are unavailable.
- Existing NVIDIA/CrewAI configuration, runbooks, incident store and flight recorder.
- Read-only recovery recommendations, exact-target human review and receipts.
- Sanitized context export and a link to the existing Repository repair workflow.
- A standard-library JSONL collector and a real isolated CampusPass demonstration.

A GitHub link alone provides source identity, not runtime visibility. Operators
must connect telemetry and identify deployed revisions. Client/browser failures
require client-side instrumentation; server evidence does not reveal every device
failure. No deployment operation, automatic code patch, rollback, restart or
production database modification is authorized by this integration.

## Providers and observation paths

| Path | Implementation and verification |
|---|---|
| Generic structured-event ingestion | Implemented; unit/integration tests and real local HTTP delivery |
| VPS/application JSONL file collector | Implemented and independently runnable; selected file only; real local delivery |
| Docker application logs | Forward structured logs from an explicitly selected exported/mounted application file; no Docker socket or remote command execution |
| CampusPass diagnostic producer | Reads actual authenticated failed-worker records, redacts order references, writes JSONL for the same collector |
| Vercel JSON/NDJSON Log Drain | Signed receiver implemented; HMAC/project/environment/deployment tests use fixtures; live account not configured |
| Vercel deployment metadata | Bounded read-only official API connector; requires server-side Vercel token; no live authenticated provider test claimed |
| AWS | Generic collector-compatible application logs; native CloudWatch ingestion is not implemented |
| OTLP/OpenTelemetry | No native OTLP receiver implemented; an external trusted forwarder must convert to the structured-event schema |

Vercel's current documentation states that Drains require **Pro or Enterprise**;
Hobby and Pro Trial do not provide non-audit drains. See
[Drains availability](https://vercel.com/docs/drains),
[signature verification](https://vercel.com/docs/drains/security),
[log format](https://vercel.com/docs/drains/reference/logs), and
[deployment metadata API](https://vercel.com/docs/rest-api/deployments/get-a-deployment-by-id-or-url).
No Vercel token was configured during implementation, so no live Vercel connection
or real hosted log delivery is claimed.

## Project onboarding

1. Open Projects → Connect project.
2. Select **Repository + Deployment Monitoring**. Generic HTTP and CampusPass
   remain separate choices.
3. Enter a new project name/ID and GitHub URL. Optional branch preference is
   advisory; source diagnosis never substitutes current main for a deployed SHA.
4. Add deployments. Each has its own ID, platform, service identifier, environment,
   optional application URL, actual deployment reference and known full commit SHA.
   Add another deployment for a worker, frontend, production or staging environment.
5. Select structured events or, for Vercel, a signed drain. Unsupported native
   providers are not described as connected. The optional application URL is
   informational and is not fetched; no fake backend URL or health endpoint is required.
6. Optional advanced source hints are repository-relative files, used only when
   telemetry has no stack frame. They are explicitly labeled as operator hints;
   the failing line remains unknown.
7. Test repository/provider metadata, review the coverage disclosure, then save.
8. On the project card, **Provision source credential** for each source. The
   browser receives the receiver path and credential-file location, never its value.
   An authorized server operator provisions that private file to the collector.
9. Enable monitoring in project settings when ready to receive events. Until
   actual telemetry arrives, health is unknown. Disable this setting to reject
   new events and stop new runtime investigation for that project.

Connection testing checks repository accessibility and optional provider metadata.
It does not simulate telemetry or prove application health. Cards distinguish
missing source credentials, monitoring disabled, no recent events, receiving
telemetry and observed errors. Failed metadata tests expose provider status.

## Authentication and credentials

Collector receiver:

```
POST /telemetry/WORKSPACE/PROJECT/DEPLOYMENT/SOURCE
Authorization: Bearer SOURCE_CREDENTIAL
Content-Type: application/json
```

`WORKSPACE` is `operator` for the shared administrator workspace, or the ordinary
user's account ID. Source keys are scoped to that workspace/project/deployment/
source. They cannot authenticate dashboard, review or project-management APIs.
A different user's credential cannot inject into this workspace.

Credentials are private mode-600 files under `DATA_DIR/runtime-secrets`; the
parent directory is mode 700. Existing .env files are not regenerated or printed.
Use HTTPS across hosts. The demonstration scripts restrict account login to
loopback. Never embed collector credentials in browser code or screenshots.

Public GitHub access works anonymously subject to API limits. For private source,
an administrator configures a least-privilege GitHub token with repository
Contents read access on the server (`GITHUB_TOKEN`). User workspaces use the
server-configured `CTRLZ_USER_<ACCOUNT_ID_UPPERCASE>_GITHUB_TOKEN`; they never
inherit an administrator's private token. Vercel follows the same pattern with
`VERCEL_TOKEN` / `CTRLZ_USER_<ACCOUNT_ID_UPPERCASE>_VERCEL_TOKEN`, scoped to the
relevant team/project for read-only metadata.

## Structured event schema

```
{
  "events": [{
    "event_id": "source-log-entry-123",
    "timestamp": 1790000000.0,
    "timestamp_kind": "occurred",
    "severity": "error",
    "error_type": "TypeError",
    "message": "Comparison failed",
    "frames": [{"path": "src/reservation.py", "line": 24, "function": "reserve"}],
    "http_status": 500,
    "route": "/api/reserve",
    "request_id": "actual-request-id",
    "commit_sha": "FULL_40_CHARACTER_DEPLOYED_SHA"
  }]
}
```

This is a schema example, not a payload to send verbatim. Use actual timestamps,
IDs, paths and SHAs. Unknown optional fields must be omitted. Optional stack,
trace ID, user/session ID, deployment reference and opaque evidence reference are
supported. User/session IDs are pseudonymized before persistence. Route queries
are removed. Messages, source excerpts and stacks are redacted before storage/AI;
headers, arbitrary extra fields and full customer objects are not accepted.
Redaction is conservative but is not a substitute for minimizing sensitive data
at the producer. Do not intentionally log secrets or full customer records.

CampusPass's producer has no original failure timestamp or stack trace from its
diagnostic endpoint. It explicitly emits `timestamp_kind=observed`, sends no user,
request or stack identifiers, and uses operator-configured source hints. Its
source-event identity is a stable keyed hash of the observed failure record.
No affected-user count or observed failing line is invented.

## Limits, grouping and retention

- Maximum request body: 256 KiB; maximum batch: 50 events.
- Per source: 120 batches / 1,000 events per minute, persisted across restarts.
- Accepted source timestamps: within seven days and five minutes of future skew.
- Raw telemetry retained for at most seven days / 10,000 events per workspace.
  Incident snapshots, diagnosis and receipt audit history are retained separately.
- Event identity is scoped to project/deployment/source. Identical deliveries are
  acknowledged as duplicates; a reused ID with different sanitized content is rejected.
- Fingerprints include project, environment, deployment/reference, revision,
  error type, normalized stack/route, and normalized message when frames are absent.
  Different deployments/revisions are separate. User IDs do not split one underlying
  fault; measurable pseudonymous affected-user counts are shown separately.
- Error/fatal exceptions with error/stack evidence create an incident immediately.
  Plain errors/HTTP 5xx without exception evidence require three matching failures
  within 60 seconds. Ordinary warnings and client 404s do not create incidents.
- No request-denominator error-rate spike claim is made. Out-of-order events are
  accepted within retention. Delivery/observation time is distinct from occurrence time.

The JSONL collector reads only its explicitly selected regular .jsonl/.log file,
rejects symlink and credential paths, limits individual lines to 64 KiB, waits for
complete lines and advances a durable cursor only after HTTP acknowledgment.
Retries preserve the source's event ID. It never executes log content or shell
commands. It works on a VPS without custom CtrlZ health endpoints. For Docker,
select/export only the intended application container's structured logs; no
untrusted container receives a host Docker socket.

## Exact source correlation

The event/deployment supplies the deployed SHA, or Vercel metadata resolves it.
CtrlZ validates the full commit through the expected GitHub repository and fetches
bounded source excerpts from that SHA. It never reads arbitrary URLs from logs.
Provider hosts are fixed, redirects are disabled, responses/excerpts are bounded,
and credential/database paths and path traversal are rejected.

A configured SHA is an operator assertion about what is deployed; validating that
commit on GitHub proves source identity, not independent process attestation.
The demo verifies its running local source against that commit before startup.
When stack frames exist, their actual paths/lines select context. If they do not,
optional operator source hints are labeled as such, with no fabricated line.
Missing commit, inaccessible GitHub, missing source maps and mismatched repository
metadata remain explicit uncertainty. Current main is never a silent fallback.
Recent changed-file context from the deployed commit is bounded and may be partial.

For offline/local use only, a server operator may set `CTRLZ_RUNTIME_LOCAL_REPOS`
to a JSON mapping from GitHub owner/repo to trusted local Git checkout paths.
Only exact read-only Git objects are inspected, repository identity is checked,
and evidence is labeled local/unpublished rather than GitHub-verified. Ordinary
user workspaces do not inherit this server-file access. No git fetch is performed.

## AI, review and repair handoff

The existing NVIDIA model receives sanitized runtime samples, deployment identity,
exact source evidence, available runbooks and actual measurable correlation IDs.
Evidence citations and structured output are validated. One bounded model revision
is allowed after invalid output; both rejection and retry stay in the audit trail.
Provider failure produces blocked/escalated state, never fabricated diagnosis.

Recommendations cover code patches, configuration, operational investigation,
dependencies and escalation. Rollback proposals without actual previous-deployment
evidence are deterministically blocked. Code-patch review requires retrieved
exact-revision source context. No recommendation gains execution permission.

**Accept recommendation · no execution** records human review of the exact
proposal, target configuration, revision/source evidence and telemetry snapshot.
Changed evidence/configuration makes the review stale. Decline records rejection.
Neither decision executes anything or marks recovery verified. The receipt keeps
`success=false` until a separate actual verification mechanism exists.

**Download repair context** exports sanitized repository/revision/error/source/
reproduction hints; **Open Repository repair** opens the existing workflow. The
operator imports the correct snapshot and supplies expected behavior. No Scenario A
continuation/worktree/sandbox/patch logic was changed. Passing tests must not be
presented as universal proof that a production incident is fixed.

## Local CampusPass source-monitoring demonstration

The normal applications remain at CtrlZ 5173/8000 and CampusPass 5174/8001.
The new demo uses a separate CampusPass process/database on 18031. Its code is
verified against `f4b3e817e6c80075c91f23f6c2a6cbb3f4e6d0a1` in
`AtharvMitt/CampusPass`. The primary storefront and Scenario B history are preserved.
The legacy formatter is deliberately defective and remains unchanged.

From the CtrlZ checkout, start/reuse the normal stack once:

```sh
backend/.venv/bin/python scripts/dev.py --campuspass
```

Wait for both APIs to finish startup. Do not start a competing stack. The existing
launcher can briefly reject a port because of closing connections; if no listener
exists, wait about a minute rather than killing unrelated processes.

In separate terminals, from the same CtrlZ directory:

```sh
# 1. Isolated CampusPass deployment; primary database is untouched.
backend/.venv/bin/python scripts/campuspass_runtime_demo.py serve

# 2. Register repository/deployment and provision the private source credential.
backend/.venv/bin/python scripts/campuspass_runtime_demo.py register

# 3. Observe actual failed-worker records into a JSONL source.
backend/.venv/bin/python scripts/campuspass_runtime_producer.py \
  --env-file ../CampusPass/.env \
  --output backend/data/runtime-demo/campuspass-source/worker.jsonl \
  --state backend/data/runtime-demo/campuspass-source/producer-state.json \
  --revision f4b3e817e6c80075c91f23f6c2a6cbb3f4e6d0a1
```

The producer runs continuously. In another terminal, read the printed receiver
and private token-file path from `register`, then run:

```sh
python scripts/runtime_log_collector.py \
  --file backend/data/runtime-demo/campuspass-source/worker.jsonl \
  --cursor backend/data/runtime-demo/campuspass-source/collector-cursor.json \
  --endpoint http://127.0.0.1:8000/telemetry/operator/campuspass-source-runtime/isolated-staging/worker-errors \
  --token-file PRIVATE_CREDENTIAL_FILE_PRINTED_BY_REGISTER
```

Finally, trigger the actual existing defect in the isolated app:

```sh
backend/.venv/bin/python scripts/campuspass_runtime_demo.py trigger
backend/.venv/bin/python scripts/campuspass_runtime_demo.py status
```

A real simulated payment/order is created in the isolated database; the actual
worker calls `legacy_reference`, raises a ValueError and records the failed job.
The observer reads that record, the collector sends it, and CtrlZ creates a
runtime incident and reads source from the fork at the pinned revision. AI
reasoning may take time. It should recommend investigation/validation/code repair
for review, without pretending a restart repairs the formatter.

Open Projects → **CampusPass · repository and worker runtime** → **View runtime
incidents**. In the incident, show Evidence, exact revision, source-hint disclosure,
AI hypothesis, Recommendations, human review, Flight recorder and Receipt.
The CLI `export` action saves actual JSON/Markdown receipts under the ignored
`backend/data/runtime-demo/campuspass-source/` directory.

To stop safely, disable this new project's monitoring, then Ctrl+C only its
producer, collector and isolated server terminals. No history/database deletion
is necessary. Do not clear a defect and call that a deployed code fix.

## Supplemental actual-stack collector fixture

`python scripts/runtime_demo.py register` prints commands for the independent
reservation application, pinned to the existing public CtrlZ source commit
`08f66e7c565ea42d2dd26e992cb5681326e74a9e`. Its `/reserve` request succeeds;
`/fail` deliberately passes an invalid type to the real pinned function, causing
HTTP 500 and a genuine Python traceback. Its JSONL logger supplies actual relative
stack frames and a server-generated request ID, exercising automatic frame-based
GitHub correlation without source hints. It creates no fake browser incident.
This fixture demonstrates the generic collector; CampusPass is the main target.

## Vercel setup and limitations

Create a Repository + Deployment project with platform Vercel, exact Vercel
project ID, environment and optionally deployment/team IDs. Provision a source
with `connector=vercel-drain`. An authorized operator reads its private server
credential and configures it as the drain signature secret, selects JSON or NDJSON,
and restricts the upstream drain to the intended project/environment/runtime sources.

The receiver verifies HMAC-SHA1 over the exact raw body using constant-time
comparison of `x-vercel-signature`; it also verifies project, environment and any
configured deployment reference. Non-runtime build logs are ignored. No IP,
headers, cookies or user-agent payloads are collected from provider proxy metadata.

Hosted Vercel cannot deliver to localhost. A reachable HTTPS receiver is required;
**no tunnel, public endpoint or local-machine exposure was created or authorized**.
Configure authorized hosting/networking separately before claiming live drain
receipt. The metadata API uses a server-side read token, not dashboard scraping.
No undocumented runtime-log polling endpoint is used.

## Troubleshooting

- 401: source credential absent/incorrect, wrong workspace, or invalid drain signature.
- 403: wrong provider project/environment/deployment; do not bypass these checks.
- 409: monitoring disabled, reused event ID with different content, stale review,
  changed project type, or unsupported evidence for a recommendation.
- 413/422: payload/batch/schema/time-window limits; raw log values are not reflected.
- 429: source quota exceeded; collector leaves cursor pending for retry.
- No events: check the actual file, receiver path, source provisioning and monitoring
  flag. A repository connection test cannot establish telemetry flow.
- GitHub unavailable: source remains uncertain; correct access/rate limits and
  reinvestigate. Never substitute main or label missing code as analyzed.
- AI unavailable/invalid output: inspect the flight recorder and reinvestigate after
  resolving provider settings; no deterministic response replaces the live model.
- First failed reservation assessment: an invalid model evidence citation was
  rejected in the real rehearsal. The rejection remains recorded; bounded revision
  and explicit valid-citation feedback were added and regression-tested.

## Local checkpoint and publication scope

Before implementing this feature, reviewed safe changes were checkpointed locally:

- CtrlZ: `08f66e7c565ea42d2dd26e992cb5681326e74a9e` →
  `2233aea096eb45d1610c9b055b9ce1971746b980`.
- CampusPass: `39727a3ab6c15d8e585b721ce9c60bb0a7f4c5e5` →
  `f4b3e817e6c80075c91f23f6c2a6cbb3f4e6d0a1`.

Both branches remained main. No Scenario A edits or staged work were present.
Tracked runtime databases/dependencies/bytecode/build artifacts were excluded.
The old Scenario B guide, which contains local transaction references, was left
uncommitted. No credentials, incident/customer evidence or local compatibility
symlink was staged.

The user subsequently explicitly authorized pushing CampusPass to their fork.
Only the reviewed CampusPass checkpoint was fast-forward pushed to
`AtharvMitt/CampusPass` main. No fork sync, git fetch/pull, upstream merge, force
push or CtrlZ push occurred. All new integration changes remain uncommitted in
CtrlZ; CampusPass's new monitoring uses its existing pushed source without further
source edits or commits.

## Observed local validation

The local end-to-end CampusPass incident is
`47daa93a-9e90-4319-8438-931c34f3c649` in project `campuspass-source-runtime`.
An actual isolated worker failure was observed, normalized, persisted and detected.
The live NVIDIA Nemotron 3.5 Lightning model diagnosed the legacy formatter issue
using real error evidence and the formatter source fetched from the fork at the
pinned SHA. Only part of the requested source context was initially retrieved;
worker/caller behavior remains something to investigate, not an established fact.
The original occurrence time, users and stack frames are unknown and labeled so.

Repeated anonymous GitHub access later returned HTTP 403. The connection test
must show the real provider failure rather than claim connectivity. Source
refresh now distinguishes rate-limit responses where GitHub supplies the header,
and may reuse previously recorded immutable source only for the same repository
and exact SHA, with cache provenance and failed-refresh uncertainty disclosed.
This never substitutes current main. A least-privilege GitHub read token is useful
for repeatable rehearsals involving many source requests.

A browser test exposed stale receipt rendering while moving between incidents.
The UI now refuses to render a receipt whose incident ID differs from the selected
incident, and runtime view state is reset per incident. The programmatic test
review affected a read-only recommendation; no operation executed. Its audit event
is retained. Reinvestigation clears only the current review display, preserving
the review in the flight recorder and producing a fresh pending recommendation.
Programmatic review tests are not represented as physical human approval.

No new runtime repair has been executed, no verified patch has been claimed, and
no production recovery has been declared. Live Vercel tests are deferred until
the user supplies deployment access and explicitly authorized receiver hosting.
Collector source-file rotation/retention remains the operator's responsibility;
the server-side raw-event retention limits apply to its normalized telemetry DB.

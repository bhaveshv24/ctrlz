# Hosted CampusPass: full source-to-recovery rehearsal

For the ten-customer targeted-failure and checkout-outage presentation, use [CAMPUSPASS_10_USER_JUDGE_DEMO.md](CAMPUSPASS_10_USER_JUDGE_DEMO.md). This guide retains the original global worker-pause fallback.

This demonstration uses CampusPass's Vercel storefront, Render backend and a
local isolated CtrlZ dashboard. Payments remain simulated. It requires the
operator to approve monitoring, review generated code, deploy it, then separately
approve recovery. No commit/push/deployment is implied by generating a patch.

## Topology and prerequisite

- Storefront: https://campus-pass-six.vercel.app/
- Backend: https://campuspass-api-2jx6.onrender.com
- Dedicated local CtrlZ API/dashboard: 18070/18072.
- Local telemetry-only gateway: 18073. It permits only the two configured
  telemetry receiver paths. No dashboard, account or recovery API is exposed.
- A temporary authorized HTTPS tunnel points only at the gateway.

Keep the local existing `CAMPUSPASS_HOSTED_RECOVERY_TOKEN` private. Render's
matching `RECOVERY_TOKEN` remains server-side. Render must enable `DEMO_MODE=true`
only for this controlled demo. The Free service loses data on redeploy/sleep.

## 1. Start local CtrlZ and inspect source

From CtrlZ root:

```bash
DOCKER_HOST=unix:///run/user/1000/docker.sock backend/.venv/bin/python scripts/hosted_deadline_demo.py serve
```

In another terminal:

```bash
backend/.venv/bin/python scripts/hosted_deadline_demo.py prepare
backend/.venv/bin/python scripts/hosted_deadline_demo.py status
```

Open http://localhost:18072/#projects and sign in with the existing local admin
credentials. Open **AI Workflow Audit · optional** on the hosted project. It audits
the actual locally supplied CampusPass source and tests, content-pinned as a ZIP.
This does not claim that uncommitted source is already published/deployed.

## 2. Review and generate monitoring

Review the ticket-fulfillment rule. Expected meaning:

- Start: a committed issuance job for a paid order.
- Complete: a committed valid ticket for that same order; independent verification
  also requires paid payment and a done job.
- IDs: actual order ID for instance/resource; optional pseudonym of the actual
  account ID. No email, password or request/response-body capture.
- Deadline: choose a realistic demo value such as 15 seconds; review it explicitly.
- Instrumentation driver: `campuspass_committed_session`. It uses committed
  SQLAlchemy model events rather than modifying decorated route handlers.

The AI may propose an incomplete or unsupported rule. Inspect the result; do not
approve invented mappings or claim unsupported zero-code behavior is active.
Failed attempts remain recorded. The server validates real source evidence and
the narrow CampusPass source layout.

Click **Approve monitoring rule**, then **Generate and verify instrumentation**.
CampusPass's declared Python dependencies require separate sandbox-download
authorization: review and check that option if allowed. Tests execute offline after
dependency setup. No dependencies are installed on your host.

Review the full diff. It adds one import, one factory attachment and a separate
`backend/campuspass/_ctrlz_session_observer.py`. It preserves the worker,
deliberately defective formatter, payment calculations, original tests, business
transactions and return values. Committed Job/Ticket events produce observations;
rollback produces no start event. The sender/checker are optional and disabled
unless explicitly configured. Telemetry failures are fail-open and bounded.

Wait for actual passing baseline, candidate and dedicated instrumentation tests.
Download the patch/source only when you intend to review/deploy it. An exported
patch is not a deployment. The driver is a trusted constrained code template
selected from the approved AI proposal, not unrestricted AI-written business code.

## 3. Publish and deploy the reviewed candidate

The agent must receive separate authorization before any commit/push. Stage only
the reviewed generated source, never `.env`, databases, caches, dependencies,
screenshots or private telemetry artifacts. Do not sync the fork or push CtrlZ.

Deploy that exact CampusPass candidate on Render. The Vercel frontend needs no
source change: its existing API proxy still reaches the same backend. Record the
full deployed Git SHA from Render. Source-to-Git activation verifies the generated
artifact against that commit; mismatches or unavailable source verification block
activation. If it came from an uploaded snapshot, all bounded candidate files are
checked, not a fabricated parent SHA.

## 4. Establish the restricted telemetry connection

Start the exact-path gateway:

```bash
backend/.venv/bin/python scripts/telemetry_gateway.py \
  --paths-file backend/data/hosted-deadlines/gateway-paths.json
```

With explicitly authorized `cloudflared` installed locally:

```bash
.dev-tools/cloudflared tunnel --url http://127.0.0.1:18073 --no-autoupdate
```

Copy the temporary HTTPS origin. The hostname changes when the tunnel restarts.
Cloudflare Quick Tunnels do not support SSE, so this companion uses bounded
long-polling against **CtrlZ's queue**. It never periodically scans the application
database or calls its health/workflow APIs. Empty waits cause no application reads.
Source authentication remains mandatory. Never tunnel the full CtrlZ API directly.

After source approval, generation and actual Render deployment:

```bash
backend/.venv/bin/python scripts/hosted_deadline_demo.py configure \
  --revision FULL_RENDER_COMMIT_SHA \
  --public-origin https://YOUR-TEMPORARY-TUNNEL.trycloudflare.com
```

This writes private Render settings to
`backend/data/hosted-deadlines/render-workflow.env` with mode 0600. Open it locally
and copy only those settings into Render's **Environment** page. Do not paste
tokens in chat, screenshots, docs or frontend variables. They include the two
source receivers/keys, approved proposal/workflow IDs, instrumentation digest,
deployed revision and optional user-pseudonym key. Save and redeploy Render.
An environment-only redeploy must still use the exact source commit configured.

Do not proceed until matching authenticated start/completion evidence is observed.
No telemetry means unverified monitoring, not a healthy workflow.

## 5. Healthy purchase

Wake Render directly at `/health` before presenting. Open the Vercel storefront,
create a disposable demo account, sign in and buy one simulated ticket normally.
Verify it in **My tickets**. The start/completion events should cancel the deadline
without a state lookup. Source tokens and user identity are never exposed in UI.

## 6. Inject the real worker interruption

Register the explicit recovery target with HTTP polling disabled:

```bash
backend/.venv/bin/python scripts/hosted_deadline_demo.py recovery-project
backend/.venv/bin/python scripts/hosted_deadline_demo.py pause
```

Buy a separate simulated ticket in the same authenticated Vercel account. Show
that the website remains available and payment is recorded, but issuance needs
attention. The committed job-start event registers this specific order's deadline.

When overdue, local CtrlZ dispatches the order ID to the Render companion. The
companion performs one indexed read-only reconciliation of existing order,
payment, job and ticket state. It never retries payment or issues a ticket.
Fresh authoritative incompletion creates the runtime incident; missing completion
logs alone do not prove business failure. Inspect the actual order ID and
pseudonymous account association. Unknown request/trace IDs remain unknown.

## 7. Diagnose, authorize and verify recovery

In the workflow runtime incident, inspect the AI diagnosis and evidence. Click
**Investigate affected order recovery · approval still required**, supplying
`campuspass-hosted-recovery` if asked. This explicit handoff checks the same
deployment URL and real order ID, then invokes the existing CampusPass recovery
engine; no recovery is authorized by the handoff.

Review its real diagnostics, strategy evaluation and exact pending candidate.
Force issuance stays blocked. Retry stays blocked while paused. Authorize
`resume_worker` only after reviewing it. This resumes a shared worker; it is not
a per-account code patch. Its target order still gets independent verification.

Show the same customer's order history and use **Verify ticket**. Confirm paid
payment, done job, exactly one valid ticket and no duplicate payment. Preserve
both the workflow detection receipt and separate verified recovery receipt.
The original read-only runtime investigation must not masquerade as executed
recovery merely because its operational handoff later succeeded.

## 8. Safe reset and repeat

```bash
backend/.venv/bin/python scripts/hosted_deadline_demo.py reset
```

This clears only the injected fault. Keep order/incident history. Another demo
purchase gets a different real order ID. Stop the temporary tunnel when finished.
Disable Render's optional workflow setting/DEMO_MODE after the controlled demo;
its environment redeploy may erase Free-tier data. Keep local receipts.

## Verification boundary

The reviewed generated source was published with explicit operator authorization
to the CampusPass fork as `c3c928526c0c4e5f4efb31cc23a6689ca4335132`.
Only `backend/campuspass/main.py` and
`backend/campuspass/_ctrlz_session_observer.py` were committed. Both matched the
verified source archive byte for byte. The isolated baseline passed 14 tests,
the candidate passed the same 14 original tests, and the candidate with dedicated
instrumentation checks passed 18 tests. No fork synchronization occurred.
Render deployment, telemetry activation and the new hosted rehearsal remain
separate steps; publication alone does not establish monitoring coverage.

The operator subsequently deployed this commit and configured the private source
settings. A real authenticated Vercel purchase emitted start/completion events;
its local deadline was cancelled with zero reconciliation attempts. A second
authenticated purchase under the real worker-paused fault remained paid without
a ticket while health stayed healthy. Its deadline caused one targeted Render
state check and one runtime incident:
`a9d2b7c1-a265-4a2a-a904-8f24c3f798e2`. The affected order and HMAC account
pseudonym were independently matched. Source correlation reported
`exact_github_revision` at the published commit. Live NVIDIA assessment completed,
but its prose incorrectly asserted job completion and questioned telemetry setup;
these statements are hypotheses contradicted by observed evidence, not verified
facts. The receipt preserves the original assessment.

An explicit operational handoff created recovery incident
`f52bf41f-3744-4a25-9a03-3c3f34eae6e6`. The actual diagnostics gate accepted only
the paused-worker resume candidate for human approval, blocked retry while paused,
and rejected force issuance. The operator then approved candidate c1 in the
browser. Authorization was recorded before operation intent and execution.
Recovery resolved with all seven independent checks passing. The authenticated
Vercel account retrieved and verified its one valid ticket; repeated resume,
retry (same and new request keys) and checkout preserved the existing payment
and entitlement. Replayed approval was rejected. The fault was cleared by the
approved resume, the job completed without an error and its discrepancy cleared.
The hosted API rehearsal passed **46 assertions, zero failures**, and retained
one runtime detection incident plus its separate resolved recovery incident.
This is two distinct hosted purchases, not a hosted 1,000-user load test.
Private evidence is under
`backend/data/hosted-deadlines/rehearsal/`. The temporary tunnel hostname must be
read from the current private settings rather than copied from an old session.

## Short judge walkthrough using the configured deployment

1. Open http://localhost:18072/#projects, choose the hosted event-driven project,
   then **AI Workflow Audit · optional**. Show the saved Normal Paid Order
   Lifecycle source evidence, reviewed 15-second rule, human approval, generated
   diff and actual 14/14/18 isolated test results. This is the audit and patch
   already performed; do not describe an already-instrumented deployment as an
   uninstrumented initial state. A new `prepare` invocation audits current local
   source and does not rewind the repository or deployed source.
2. Open the Vercel storefront, sign in to a demo customer account and buy a normal
   simulated ticket. In **My tickets**, click **Verify ticket**. Explain that
   committed start/completion events cancel the deadline before a state check.
3. Run `backend/.venv/bin/python scripts/hosted_deadline_demo.py pause`, then buy
   another simulated ticket in that account. Show paid payment, missing ticket
   and healthy website. Wait at least the reviewed 15-second deadline plus
   transport time. One indexed authoritative check confirms this specific order
   is incomplete; a missing log alone would not prove failure.
4. Open the newly detected runtime incident. Show the exact deployed Git revision,
   resource ID, pseudonymous account association and observed evidence. Review AI
   hypotheses critically. Click **Investigate affected order recovery · approval
   still required**, using `campuspass-hosted-recovery` when asked.
5. Open the linked recovery incident, inspect strategies and **Review decision**.
   Explain the deterministic force-issue/retry rejection, then explicitly approve
   c1. Wait for **resolved** and all seven verification checks. Refresh the same
   account's **My tickets** and verify its recovered ticket. Show the persisted
   receipt and idempotency evidence from the completed rehearsal. A new manual
   run must establish its own evidence before making the same claims.

The resume action affects the shared worker; it is not a per-user code fix. Order
and account correlation identifies the affected transaction. Generated monitoring
currently uses a narrow CampusPass session driver, not universal automatic
instrumentation for arbitrary repositories. NVIDIA output is advisory and the
observed inaccurate claims remain a known diagnosis-quality limitation.

Hosted proof requires the actual generated patch deployed on Render, the private
source settings, accessible gateway/tunnel, and an observed hosted rehearsal.
Local tests or a healthy deployed website alone do not establish that chain.
Do not claim any pending deployment step has passed.

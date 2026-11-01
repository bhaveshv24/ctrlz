# CampusPass: one failed customer among ten, then checkout-outage recovery

Use only the synthetic, simulated-payment CampusPass deployment. No external payment gateway or real charge is involved. Ten requests are sequential, from ten separate synthetic accounts—not a concurrent load test.

## Current implementation and evidence

- CampusPass fork release: `d200fa804b35e24c23e75774cc0acac8e86e8256`.
- Vercel: https://campus-pass-six.vercel.app/
- Render API: https://campuspass-api-2jx6.onrender.com
- Independently discovered Render service: `srv-dbj1vejbc2fs73bk9o4g`.
- Local hosted-demo CtrlZ dashboard/API: http://localhost:18072 / http://127.0.0.1:18070.
- B uses the retained approved CampusPass committed-session observer, lifecycle events, deadline dispatch, and an order-scoped authoritative database check. The operational recovery project has automatic HTTP workflow detection **disabled**.
- C temporarily enables the existing health/availability monitor. This deliberately polls availability; it is separate from B's event-driven monitoring.
- Render logs are retrieved through documented read-only API calls, scoped to the actual service. They support the investigation. Missing tickets are established by authoritative workflow state, not inferred from absent logs.
- Operational recovery is deliberately CampusPass-specific. NVIDIA chooses among registered actions; deterministic gates grant no arbitrary commands.

## 1. Start local CtrlZ

From the configured laptop's restored CtrlZ checkout:

```bash
cd /home/atharv/Documents/PES/Hackathon/ctrlz
DOCKER_HOST=unix:///run/user/1000/docker.sock backend/.venv/bin/python scripts/hosted_deadline_demo.py serve
```

Leave it running. Open http://localhost:18072/#projects and sign in with the existing local admin account. Do not run `prepare` against this configured workspace: that older helper re-registers the project and is unnecessary for repeat demonstrations.

Existing `.env` values: NVIDIA_API_KEY, NVIDIA_MODEL, CAMPUSPASS_HOSTED_RECOVERY_TOKEN, CTRLZ_DEMO_CONTROLS_ENABLED=true, and RENDER_API_KEY. Never display the file. Render needs matching RECOVERY_TOKEN, DEMO_MODE=true and CAMPUSPASS_REQUIRE_LOGIN=true. Source tokens stay server-side.

## 2. Verify hosted code and review a changed revision

```bash
backend/.venv/bin/python scripts/render_demo_logs.py
backend/.venv/bin/python scripts/hosted_ten_setup.py status
```

The Render metadata, rather than a configured label alone, establishes the actual live commit. The Vercel bundle must include “Retry simulated payment”; Render OpenAPI must include `/demo/target-fault` and `/demo/ten-customers`.

When the source revision changes, run:

```bash
backend/.venv/bin/python scripts/hosted_ten_setup.py review
```

In Projects, open **AI Workflow Audit · optional** on the hosted event-driven project. Review the pinned revision, original completion rule, 15-second demo deadline and approved fields. Click **Approve monitoring rule**. This does not approve recovery or deployment. The unchanged observer, exact attachment and four durable model definitions are checked against the original verified artifact. Changed observer/model mappings are rejected and require a new audit. Other business-code changes still need human review.

This revision review is deterministic verification of existing instrumentation, not a new AI discovery or new generated patch. Historical audit and approval records remain available.

## 3. Connect Render to the local telemetry receiver

In separate terminals:

```bash
backend/.venv/bin/python scripts/telemetry_gateway.py --paths-file backend/data/hosted-deadlines/gateway-paths.json
.dev-tools/cloudflared tunnel --url http://127.0.0.1:18073 --no-autoupdate
```

The gateway exposes only the configured authenticated telemetry paths, not the dashboard or recovery API. Record the temporary HTTPS origin printed by cloudflared. Then:

```bash
backend/.venv/bin/python scripts/hosted_ten_setup.py configure --public-origin https://YOUR-CURRENT-TUNNEL.trycloudflare.com
```

Open `backend/data/hosted-deadlines/render-workflow.env` **privately** in an editor. Copy the specified values into Render → CampusPass API → Environment, preserving unrelated values and existing RECOVERY_TOKEN. Save/redeploy the **same source commit**. Never print this file in the presentation. The helper preserves source credentials and the pseudonym key. It does not modify Render.

A tunnel restart changes its origin and requires this setup again. A free Render redeploy can erase ephemeral orders/accounts: finish environment setup **before** starting purchases. Never redeploy during pending recovery approval.

## 4. Require human approval for targeted retry

```bash
backend/.venv/bin/python scripts/ten_purchase_demo.py setup --hosted
```

This preserves the existing hosted recovery target and adds `retry_order` to its normal approval-required contract. `resume_worker` remains approval-required. Automatic detection stays off for this operational target; B comes from event-driven workflow evidence.

First make one normal purchase through Vercel and check its ticket. Run `hosted_ten_setup.py status`: require matching authenticated telemetry at the actual revision before proceeding. Missing telemetry is unverified monitoring, not a healthy business workflow.

## 5. Scenario B: ten real accounts, one selected failure

```bash
backend/.venv/bin/python scripts/ten_purchase_demo.py start --hosted
backend/.venv/bin/python scripts/ten_purchase_demo.py status --hosted
```

`start` provisions ten synthetic accounts using an authenticated demo-only operator route, then signs into each and submits its normal checkout. Account creation retains the existing 50-account deployment limit. It arms one one-shot fault for customer 5's exact checkout request **before** submitting that checkout. All ten payments are simulated and paid; the actual worker fails that one job and consumes the fault. It keeps processing the other nine. There is no global worker pause.

Expected real output: 10 orders, 9 completed, 1 failed, 9 tickets, healthy website. Keep this terminal visible as the measured count; there are no decorative counters.

Open `backend/data/ten-purchase-demo/hosted-run.json` privately. Use `customers[4]` email/password to sign into Vercel in a private browser window. These are genuine synthetic account credentials. Show **My tickets**: this account's paid order has no ticket. Never show the credentials file or passwords on the projector. Another synthetic account can show a successful ticket.

After the approved deadline, follow the new workflow incident from **View runtime incidents**. Check its resource ID matches the terminal's affected order, and inspect the pseudonymous user association. Completion logs alone are insufficient: the deadline companion checks paid order, failed job, and missing ticket in the actual database.

```bash
backend/.venv/bin/python scripts/render_demo_logs.py
```

The retained provider evidence must contain `DemoTicketIssuanceFailure` for that exact order/job. Its private output file is `backend/data/ten-purchase-demo/render-log-evidence.json`. This companion does not insert another incident or manufacture an error. No matching result means provider-log evidence is not yet verified.

## 6. Investigate and authorize only the affected order

In the runtime incident click **Investigate affected order recovery · approval still required**. This opens the linked operational incident, not a second customer failure. Inspect NVIDIA diagnosis, actual order/worker diagnostics, strategies and policy results.

The expected eligible action is `retry_order` for this order. Global `resume_worker` is inappropriate because the worker is ready; force issuance remains prohibited. If AI selects no eligible strategy, report escalation and reinvestigate; never force success.

Click **Review decision**, inspect the exact candidate/order, then **Authorize cN** for the candidate actually displayed. Do not assume its ID is always c1. This approval is separate from monitoring approval and is bound to candidate, incident, contract and observed service revision.

Wait for **Resolved** and all independent verification checks. Refresh **My tickets** in the affected account and verify its ticket.

```bash
backend/.venv/bin/python scripts/ten_purchase_demo.py verify --hosted
```

This requires all ten original orders to be paid, done and each to have one valid ticket; verifies every ticket through the real application; compares payment references and the other nine full order views; then repeats only an already-completed authorized retry using the same idempotency key. It never authorizes the pending recovery. Expected: 10 valid unique tickets, unchanged payments, other nine unchanged, idempotency true.

Export the operational incident's JSON/readable receipt and retain the linked runtime incident's evidence receipt. A read-only runtime recommendation is not itself executed recovery.

## 7. Scenario C: checkout fails before simulated payment

Finish B first. In Vercel, open an event's **Get your pass** dialog. Keep it open. In the terminal:

```bash
backend/.venv/bin/python scripts/ten_purchase_demo.py scenario-c --hosted
```

Immediately click **Confirm simulated payment**. The real backend rejects checkout with HTTP 503 **before** creating an order/payment. The dialog says the simulated payment was not attempted. The existing availability monitor detects the outage and NVIDIA proposes a registered `restore_checkout` action. This operation is automatically allowed by the current contract; unlike B's targeted retry it does not require approval by default.

Show the outage incident and independent three-probe verification. Once healthy, CampusPass's existing 8-second availability check changes the still-open purchase dialog to **Retry simulated payment**, explaining that the previous attempt did not go through. Click it once. Show the resulting ticket.

This is a controlled simulated checkout/payment-availability failure, not repair of a real external payment provider. A generic network timeout must **not** be described as a confirmed unsuccessful charge. There is no automatic payment replay.

The AI may restore availability before you submit the browser purchase. If so, finish the run and repeat the injection while the dialog is ready; do not claim a failed purchase occurred unless you actually observed the 503.

## 8. Reset and repeat safely

```bash
backend/.venv/bin/python scripts/ten_purchase_demo.py reset --hosted
```

This clears the global fault, cancels only an unconsumed target, retains orders/failed-job history, and disables operational HTTP detection again. A consumed failure is resolved by approved retry, not by reset.

For the next B run, reuse the ten existing accounts:

```bash
backend/.venv/bin/python scripts/ten_purchase_demo.py repeat --hosted
```

This requires the previous ten orders to be complete, archives the old run privately, and creates ten new uniquely identified checkouts. It preserves all history. If Render erased its ephemeral data, the saved accounts are no longer valid; retain/archive the old private run and set up a new run rather than silently replacing it. Repeated login attempts are subject to the normal application throttles; do not bypass them.

## Local fallback, already rehearsed

```bash
backend/.venv/bin/python scripts/ten_purchase_demo.py serve
# Another terminal:
backend/.venv/bin/python scripts/ten_purchase_demo.py setup
backend/.venv/bin/python scripts/ten_purchase_demo.py start
# Human approves in http://localhost:18092
backend/.venv/bin/python scripts/ten_purchase_demo.py verify
backend/.venv/bin/python scripts/ten_purchase_demo.py scenario-c
```

Local CtrlZ: 18092; CampusPass storefront: 18094; application API: 18091. This isolated fallback uses the existing HTTP workflow adapter, **not** the hosted event-driven pipeline. It must be labeled accordingly. Existing records live in `backend/data/ten-purchase-demo/`, separate from the normal databases.

## Four-to-six-minute presentation

1. Explain: a working website does not imply a completed customer transaction. Show connected repository, independently observed Render commit and received telemetry.
2. Show measured 10/9/1 results and the affected synthetic customer's missing ticket. Explain disclosed one-shot fault injection.
3. Open the deadline/reconciliation evidence and the genuine matching Render worker log. Show one affected order and pseudonymous account association.
4. Open linked recovery, show NVIDIA's explanation and deterministic rejection of inappropriate operations. Authorize only the selected targeted retry.
5. Show 10/10 independent ticket verification, unchanged payments/other orders, idempotency and export receipts.
6. Show C: confirmed rejection before simulated payment, availability recovery, and customer-authorized retry. Explain uncertain payments require reconciliation in a real gateway integration.

## Scope and troubleshooting

- Monitoring/recovery remain deliberately specialized for CampusPass. This does not prove arbitrary-repository recovery.
- A source revision, observer, rule or credential mismatch must stop activation/ingestion; do not relabel old evidence as the new deployment.
- Broken/expired tunnel: restore gateway/tunnel and update Render's two receiver origins, preserving credentials. Do this before purchases.
- No workflow evidence: inspect observer settings, proposal ID, exact deployed SHA, source keys and tunnel; leave recovery polling disabled for hosted B.
- Stale approval: reinvestigate and review a new candidate; do not reuse its approval hash.
- Render log API failure: show the error honestly; do not substitute local stdout as Render evidence. Official interface: https://api-docs.render.com/reference/list-logs .
- Preserve `.env`, private run files, SQLite data, historical incidents and generated credentials. Never `git add -A` in these repositories.

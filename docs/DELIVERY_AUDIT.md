# Scenario promise audit — 31 October 2026

The original A/B/C brief is an implementation target, not proof of production deployment.
CtrlZ is a general repository and HTTP-workflow recovery product. CampusPass is an optional
fixture. No campus identity, student email domain or CampusPass repository is required.

| Promise | Implementation / evidence | Boundary |
|---|---|---|
| A: connect/upload repository and conversation/requirements | GitHub public HTTPS, ZIP, allowed admin server folders; requirements/context form | Managed copies; private GitHub import not supported |
| A: inspect files, Git history/changes and tests | repository.py, history.py, intelligence.py, immutable baseline tests | Python pytest / Node test / locked Vitest only |
| A: completed/incomplete requirements and evidence-based continuation plan | CodeProposal requirement findings with evidence paths and continuation plan, persisted to incident and receipt | Model assessment can be unknown; tests prove only covered behavior; requires a reproduced failing acceptance suite |
| A: select alternative model and use NVIDIA NIM coding tools | Per-repair optional model; bounded source read/search/edit; CrewAI NIM | A real configured NVIDIA key and available model are necessary; no simulated success |
| A: execute, test, receipt | isolated worktree, offline Docker acceptance tests, immutable tests, patch and JSON/Markdown receipt | Patch review/deployment remain operator actions |
| B: paid order has valid accessible ticket | CampusPass workflow grace rule, payment/ownership checks and unique ticket entitlement | Demonstration payments are simulated, not real payment settlement |
| B: inspect database/jobs/logs/status | authenticated diagnostics, workflows and resource endpoints, recorded model tool calls | Generic applications must expose their own authorized evidence/API contract |
| B: resume/reconcile safely or escalate | deterministic invariants, revisions and durable request keys; unsafe issuance blocked | Uncertain payment/ownership never licenses blind issuance |
| B: authenticated alternative retrieval | CampusPass email account, owned checkout and /me/orders; tickets fetched from DB across browser sessions | Does not claim delivery to an inbox. Guest legacy orders require organizer help when login is required |
| B: inspect external delivery failure and recover existing ticket | Authenticated account retrieval is independent of mail transport | This fixture has no real mail provider integration or delivery webhook. Do not describe email sending/delivery as demonstrated |
| B: tournament and one entitlement after retry | safety gate, tournament evidence, unique order-ticket database constraint, retry tests | Fault injection/replay is controlled fixture behavior |
| C: lightweight monitoring triggers real agents | persisted HTTP health/latency/business probes and diagnosis flow | One backend process; no LLM polling loop |
| C: real metrics/logs/container/deployment evidence and runbooks | registered HTTP diagnostics; Chroma; independent worker-supervisor exposes Docker inspect/logs/image/start state | Supervisor supplies current deployment metadata, not a cloud deployment-history API |
| C: narrowly scoped worker restart | independent examples/worker-supervisor; fixed container, approval, revision, durable intent | Trusted Docker host only. Default CampusPass outage mitigation restores its circuit, not a container restart |
| C: compare mitigations and reject unsafe proposals | deterministic allowlist/risk/precondition gate, bounded planner revision | No unrestricted shell, cloud rollback or arbitrary infrastructure permissions |
| C: verify and receipt | three fresh health probes plus configured business assertions, persisted events/receipt | Container liveness alone is insufficient for real checkout acceptance |
| C: Slack/Discord report | webhook sender records transport result | Needs operator-provided webhook; no external message was sent in this work |
| Provider caveat | Render operational deployment and full Docker-host deployment documented | Vercel/Supabase provider-management/rollback integrations are not implemented; provider failure escalates |
| Email-based product access | two seeded admins, one user, registration, sign in/out, password change, admin-created users | Email/password identity, no mailbox verification or password-reset email; controlled/invite-only hosting |
| Beyond CampusPass | generic HTTP contracts; independent dispatch and Docker worker integrations; three repair profiles; isolated user workspaces | New apps need supported tests or explicit HTTP integration; “everyone” does not mean arbitrary autonomous access |

## New account behavior

First normal startup creates admin1@ctrlz.local, admin2@ctrlz.local and user@ctrlz.local.
Passwords are generated separately and written only to DATA_DIR/initial-credentials.txt (0600),
or supplied using CTRLZ_ADMIN_1/ADMIN_2/USER_EMAIL and corresponding PASSWORD variables.
Admins share the existing operator workspace; each ordinary user gets their own database,
repository imports, patch artifacts, incident history and SSE stream. Roles are server-assigned.
Ordinary users cannot import arbitrary host folders, use the demo adapter, choose a shared
backend secret or reuse the server GitHub token. Their recovery-token environment variable is
CTRLZ_USER_<UPPERCASE_ACCOUNT_ID>_RECOVERY_TOKEN.
Set these server-side; the browser never receives their values. Separate application
projects may share this account's token only if deliberately configured to do so.

## Verification for this change

Latest full Docker-enabled run: **99 CtrlZ tests passed**, including a real disposable
container restart and persisted-intent/retry checks. The additional host-execution gate
check passed in the targeted account suite (four tests). CtrlZ production frontend build
and **18 frontend tests passed**. CampusPass production build and **10 backend tests passed**,
including authenticated customer ownership and one entitlement after repeated issuance.
The local browser showed email/password sign-in as the primary entry screen. Two admin
accounts and one ordinary account were generated in the local credential file.
Live NVIDIA provider calls, external notification delivery and public hosting were not
repeated as part of this change. Existing live receipts remain historical evidence.

## Before unrestricted public signup

This is a controlled deployment with up to 50 accounts and one backend process. Separate
workspace files provide application-level isolation, not OS/process isolation. Keep Render
invite-only. Add verified email and password recovery, a tenant credential vault, quotas,
durable distributed jobs, dedicated sandbox runners, outbound network policy and audited
provider integrations before offering untrusted public code execution. In particular,
registered HTTP origins remain operator-authorized; arbitrary internet signup plus access
to internal network targets is outside this deployment's security boundary.

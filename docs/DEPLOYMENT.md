# Public demo deployment preparation

For the new email accounts, Vercel/Render blueprint and provider comparison, start with
[HOSTING_PLAN.md](HOSTING_PLAN.md) and [DELIVERY_AUDIT.md](DELIVERY_AUDIT.md). The host-service
instructions below are the full Docker execution topology; operator-token login references
are historical. Normal browser sign-in now uses email/password.

Status: templates and local validation only. No host, domain, public URL or deployment
has been claimed. Complete SUBMISSION_CHECKLIST.md on 31 October 2026.

## Choose the execution boundary deliberately

The full three-scenario demo needs a host that can run long-lived Python services, retain
SQLite/Chroma data, reach NVIDIA NIM, and execute isolated Docker tests. A static frontend
host alone cannot provide these capabilities. Container-only hosting without a dedicated
sandbox runner supports operational B/C; do not claim code continuation or replay there.

The supplied full-feature template uses a Linux VM, two independent service users and
repositories, a rootless Docker daemon for the CtrlZ service user, and a Caddy HTTPS edge.
The public browser never receives the NVIDIA key or CampusPass recovery token. CtrlZ's
operator token is entered into its HTTPS UI and stored only for that browser session.
This remains a single-operator controlled demo, not multi-tenant production infrastructure.

## Files provided

- deploy/Caddyfile: two domains, independent static roots and loopback API proxies.
- deploy/ctrlz-api.service: one recovery API/monitor process; writes restricted to data/imports.
- deploy/campuspass-api.service: independent API/worker and persistence.
- deploy/production.env.example: required configuration, no credentials.

The service templates assume /srv/agentathon/{ctrlz,campuspass}, users ctrlz/campuspass,
and their respective .venv environments. Adapt the paths/users to the actual host before
installing. Public provisioning and DNS changes wait until the host/domain choice is made.

## Deployment sequence

1. Publish and clone the two repositories independently. Install Python 3.12, uv, Node 22+,
   Git, Caddy and Docker using their official distribution instructions. Keep the APIs on
   loopback; expose only HTTPS/HTTP through the edge and SSH through the host's access policy.
2. Run `uv sync --frozen` in each backend and `npm ci && npm run build` in each frontend.
   Build ctrlz-sandbox:local and ctrlz-node-sandbox:local images as the CtrlZ rootless Docker user. Rehearse
   a sandbox test under the same service user, not under a privileged administrator account.
3. Create the data directories, ctrlz/imports, ctrlz/backend/data/sandbox-tmp and a clean
   committed continuation fixture under imports. Ensure the CtrlZ user owns its writable
   directories and CampusPass owns only its own data directory. Caddy needs read/traverse
   access to the two frontend/dist directories; never serve a repository root.
4. Create separate mode-600 backend environment files. Generate fresh operator and recovery
   tokens; match the two backend recovery tokens. Set the NVIDIA key/model only in CtrlZ.
   Configure the actual rootless DOCKER_HOST in CtrlZ's file if code/replay is enabled.
   Do not pass either backend .env into Caddy or mount the host's privileged Docker socket.
5. Install the reviewed service units; start exactly one CtrlZ process and one CampusPass
   process. Confirm /health from loopback and confirm CtrlZ's authenticated API rejects a
   missing token. With the provided protection settings, keep sandbox temporary paths in
   the configured shared TMPDIR so the rootless daemon can mount the actual worktree path.
6. Provide both domain names and ACME_EMAIL to Caddy. Point DNS to the chosen host, validate
   the Caddyfile, and start the edge. Verify trusted HTTPS and `/api/events` through the
   deployed proxy. Caddy's [automatic HTTPS](https://caddyserver.com/docs/automatic-https)
   and [reverse-proxy behavior](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
   are described in its official documentation.
7. Sign in over HTTPS and register CampusPass using the backend origin reachable by CtrlZ
   (loopback in the host-service topology). Keep project demo opt-in and the two backend
   demo flags disabled until the controlled rehearsal is ready. Then explicitly enable
   only this demo app for judging; restart APIs after environment changes.
8. Run C, B and A, confirm independent checks and download receipts. Validate that code
   test containers have no network or credentials; approved dependency setup is a separate
   credential-free networked phase and original branches remain untouched.
   Confirm actual notification delivery if it will be demonstrated. Record the real URLs
   and CI/video/deck links in the submission checklist.

## Operations and fallback

Persist SQLite databases, Chroma storage, patch artifacts and imported repositories on the
host, not an ephemeral deployment filesystem. Back up databases using a SQLite-consistent
backup method while quiescent or via SQLite's backup API; copying a changing database file
is not a tested backup strategy. Keep receipts as incident evidence with controlled access.
After restart, interrupted incidents escalate for explicit reconciliation/retry.

The initial environment/host choice is still pending. Before publishing, exercise the
provided service hardening under the actual rootless Docker setup and verify resource use;
local Docker tests do not prove that a future hosting provider supports the same boundary.
If hosting cannot support isolated A/replay, demonstrate those parts locally and label that
boundary clearly in the live UI/video/pitch. Never substitute a prerecorded recovery for live execution.

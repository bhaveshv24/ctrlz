# Deployment decision and plan

Drafted 31 October 2026. No resources purchased or public deployment performed.

## Decision

**Vercel + Render is the best near-term match of the two options for the current code.**
Vercel serves the React/Vite build. A persistent Render Python/Docker web service runs the
FastAPI API, SSE, continuously running monitor and recovery orchestration. Supabase is a
useful future managed Postgres/Auth/Storage layer, but does not replace this Python backend
or the Docker test runner. The two provider combinations do not supply equivalent services.

| Option | Fit for this code | Missing work |
|---|---|---|
| Vercel + Supabase only | Frontend, managed identity/data; hosted Edge Functions have bounded CPU/wall time | Port SQLAlchemy SQLite locking and stores, migrate auth, rewrite or separately host CrewAI/monitor, add sandbox execution |
| Vercel + Render | Closest fit: long-lived Python backend and persistent disk | Full Docker sandbox/replay still needs a trusted Docker-capable host or a new authenticated remote runner integration |
| Vercel + Docker-capable VM | All current features with existing host templates and rootless Docker | VM operations, backups, updates and resource controls |
| Vercel + Render + Supabase + runner (later) | Managed auth/data plus durable orchestration/execution | A deliberate migration, tenant policies and task queue; not required for the hackathon |

Vercel Functions and Supabase Edge Functions have execution limits. We have not evaluated
newer Vercel daemon/sandbox products as adapters for this code; the supplied implementation
uses ordinary Python processes and a local Docker CLI, not either provider's execution API.
Render Docker deployment means running a service image; it does not establish access to a
Docker daemon for creating arbitrary child test containers. Do not claim A/replay is hosted
on Render using this blueprint.

Sources checked for this decision:
- https://render.com/docs/docker
- https://render.com/docs/disks
- https://render.com/docs/background-workers
- https://vercel.com/docs/functions/limitations
- https://supabase.com/docs/guides/functions/limits
- https://supabase.com/docs/guides/getting-started/architecture

## Stage 1 — controlled hosted operational demo

1. Use the CtrlZ repository as the Render blueprint root; render.yaml and
   deploy/Dockerfile.render build from this repository without a CampusPass sibling.
   The template selects a paid service with persistent disk and one Uvicorn process.
   Review provider plan/memory pricing in the dashboard before provisioning.
2. Enter NVIDIA_API_KEY, selected model, two real admin emails and their distinct strong
   initial passwords, and the initial user email/password. Use provider secret fields.
   Seeds do not rotate existing passwords: use Account settings to change them later.
   Leave public registration, operator-token access and code execution disabled.
3. Put all state under /var/data/ctrlz: account/session database, operator and user incident
   databases, Chroma, imports, patches and CrewAI files. The blueprint sets these paths.
   Verify mount ownership/write access and restore behavior on the actual host.
4. Deploy Vercel with Root Directory frontend, Vite preset, build npm run build, output dist.
   Set VITE_API_URL=https://YOUR-RENDER-SERVICE.onrender.com (without /api or trailing slash).
   frontend/vercel.json is included. The development /api proxy is only for local use.
5. Set CTRLZ_CORS_ORIGINS to the exact HTTPS Vercel/custom frontend origin, then redeploy
   Render. Separate multiple explicitly trusted origins by commas; no wildcard.
6. Sign in as both admins and the user. Confirm /projects rejects anonymous requests,
   ordinary users cannot list accounts, private workspaces start empty, and logout rejects
   the old session. Test /events streaming through the real HTTPS hosts and reconnects.
7. Connect an independently hosted Generic HTTP service. Configure only its approved
   diagnostics/actions/acceptance assertions and server-side recovery token. For an
   ordinary user the required token variable is listed in DELIVERY_AUDIT.md. Use a narrowly
   scoped key, not the provider's global administration key.
8. Inject a controlled service fault; verify real monitoring, diagnosis, tournament,
   approval, execution, three probes and business assertions. Download the receipt.
   Supply a webhook only if a real incident summary should be sent; validate its delivery
   yourself before calling it demonstrated. No external message is sent by provisioning.
9. Restart/redeploy Render; verify the disk preserves accounts, sessions, projects and
   receipts and the monitor resumes. Back up all SQLite databases consistently and test
   restoration. One instance only: the application uses local locks and SQLite transactions.

Code repair endpoints explicitly return 503 on this template rather than pretending Docker
execution is available. Repository inspection/import remains available. Keep feature labels
honest in the judging walkthrough.

## Stage 2 — full A/B/C demo

For all current features, serve the frontend on Vercel and run the backend on a dedicated
Linux VM using docs/DEPLOYMENT.md, deploy/ctrlz-api.service and rootless Docker sandbox
images. Point VITE_API_URL and exact backend CORS to that VM's HTTPS API origin. If retaining
Render, first implement and verify an authenticated remote execution boundary; setting a
Docker host URL alone is not a finished runner design and is not in this blueprint.

Run the optional CampusPass API independently, with CAMPUSPASS_REQUIRE_LOGIN=true and its
own recovery token/database. Its authenticated customer ticket view does not need email
transport. For the real container-restart variant, deploy examples/worker-supervisor on
its trusted Docker host and connect the supplied generic project contract. Verify actual
checkout/business assertions in addition to container liveness.

Go-live acceptance: full Docker tests; sign-in/role/isolation checks; live NIM A/B/C receipts;
external webhook result if advertised; restart/backup rehearsal; no secrets in browser
assets; ownership controls on customer ticket retrieval. Public multi-tenant SaaS requires
additional security and infrastructure work listed in DELIVERY_AUDIT.md.

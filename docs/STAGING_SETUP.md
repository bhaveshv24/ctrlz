# Deploy staging: frontend, backend and persistent database

Current repository: https://github.com/bhaveshv24/ctrlz . Local checkout:
`/Users/bvell/Documents/GitHub/ctrlz`.

This deployment hosts the dashboard, email accounts, API, monitoring and generic HTTP
recovery. It does not host Docker repository execution. Use a Docker-capable VM for the
full Scenario A and Compose replay, as described in HOSTING_PLAN.md.

## 1. Accounts and staging branch

Sign in to GitHub, Render and Vercel. Authorize Render and Vercel to access only the CtrlZ
repository. Connect their Codex integrations if you want Codex to configure and verify them.
Choose a paid Render service/disk plan in the dashboard; the supplied blueprint selects
`standard` and a 10 GB persistent disk. Check the displayed total before provisioning.

Keep the working deployment on a `staging` branch while A/B/C develop separately. Push a
reviewed baseline there. Include render.yaml, deploy/Dockerfile.render, .dockerignore,
frontend/vercel.json and scripts/check_deployment.py. Do not push any .env files or data.
The blueprint inherits the repository's default branch unless you explicitly add
`branch: staging` to its service definition; set this before creating the staging Blueprint
if your repository default remains main. For a manually configured service, select staging
in the service's Branch field. In Vercel, verify staging receives Preview deployments.
Reserve main/Production for the integrated release.

## 2. Prepare hosted account credentials

A private bootstrap template has been generated at `deploy/.env.render.local` with three
unique random passwords. It is ignored by Git and has permissions 0600. Open it locally,
choose the desired two admin emails and one user email, and fill the NVIDIA_API_KEY.
Do not paste its contents into chat, GitHub or frontend environment variables.
Existing account passwords are preserved across restarts; seed variables only create
missing accounts. Change an existing password through Account settings.

To generate a new template at a different path:

```sh
python3 scripts/create_hosted_env.py --output deploy/.env.render.new \
  --admin1 founder-one@example.com --admin2 founder-two@example.com --user tester@example.com
```

The script refuses to overwrite an existing file.

## 3. Create the Render backend and database

Render dashboard → New → Blueprint → select bhaveshv24/ctrlz → use render.yaml.
Name the staging Blueprint `ctrlz-staging`. For a manual deployment, use:

| Setting | Value |
|---|---|
| Runtime | Docker |
| Dockerfile | ./deploy/Dockerfile.render |
| Docker build context | . (repository root) |
| Branch | staging |
| Health check | /health |
| Instance count | 1 |
| Persistent disk mount | /var/data/ctrlz |
| Disk size | 10 GB, as budgeted |

Enter the prompted secrets from the private bootstrap file. Initially CORS may be
`http://localhost:5173`; update it to the exact Vercel origin in step 5. Set the NVIDIA model
to one your API key can actually access. Keep CTRLZ_ALLOW_REGISTRATION=false,
CTRLZ_ALLOW_OPERATOR_TOKEN=false and CTRLZ_CODE_EXECUTION_ENABLED=false.

The blueprint supplies these database/storage paths automatically:

```text
DATABASE_URL=sqlite:////var/data/ctrlz/ctrlz.db
DATA_DIR=/var/data/ctrlz
IMPORT_ROOT=/var/data/ctrlz/imports
RUNBOOK_DIR=/app/runbooks
CREWAI_STORAGE_DIR=/var/data/ctrlz/crewai
```

No Supabase or separately provisioned database is needed for this version. Startup creates
accounts.db, the operator database, separate user workspace databases and Chroma on the
persistent disk. A Render Postgres connection URL is not a drop-in replacement: current
SQLite locking, account storage and per-user databases require a migration first.

Wait until Render reports Live and open `https://YOUR-BACKEND.onrender.com/health`.
It must return healthy. Save the backend origin with no trailing slash and no /api suffix.

## 4. Create the Vercel frontend

Vercel → Add New Project → import the same GitHub repository.

| Setting | Value |
|---|---|
| Root Directory | frontend |
| Framework | Vite |
| Install Command | npm ci |
| Build Command | npm run build |
| Output Directory | dist |
| Environment variable | VITE_API_URL=https://YOUR-BACKEND.onrender.com |

Set VITE_API_URL for the environment used by staging (normally Preview). If Vercel first
creates a Production deployment of main, set the variable for Production too, or deploy
staging explicitly and use its Preview URL. Confirm which branch/environment the URL uses.
Changing VITE_API_URL requires another frontend build/deployment. Never add NVIDIA keys,
account passwords or backend tokens to VITE_* variables: they are browser-visible.

## 5. Connect the two origins

Copy the actual frontend HTTPS origin into Render:

```text
CTRLZ_CORS_ORIGINS=https://YOUR-FRONTEND.vercel.app
```

Use the exact preview origin if you are testing a preview URL. Add a stable staging domain
when available; preview URLs change between deployments. Explicit additional trusted origins
may be comma-separated. Redeploy/restart Render after changing the value.

## 6. Verify the live deployment

From the repository root:

```sh
python3 scripts/check_deployment.py \
  --backend https://YOUR-BACKEND.onrender.com \
  --frontend https://YOUR-FRONTEND.vercel.app \
  --email admin1@ctrlz.local
```

Use the actual seeded email. The checker prompts for the password without echoing it.
Repeat for the second administrator and the ordinary user. It checks frontend/backend
reachability, exact CORS, invite-only registration, anonymous rejection, login, role
permissions, workspace access and session revocation. It does not inject faults, call the
LLM, send notifications or print credentials. Its repository-execution result should say
disabled for this Render deployment.

In a browser, confirm sign-in, overview and live updates. Create a disabled test project,
restart the Render service, and verify the project/account persists. Use a separate user
workspace to verify isolation. Then connect only an authorized demo service and rehearse
real diagnosis/recovery with the scenario owner; cloud-hosted localhost is not your laptop.

## 7. Database operations and later integration

Keep one API instance/process. All account/session data, DB files, Chroma and imported
artifacts must remain under the persistent mount. Test a consistent SQLite backup/restore
before relying on this for an event; do not copy a database during writes as your backup
procedure. Do not overwrite staging data with local demo databases or credentials.

After each scenario merges into staging, redeploy both affected services and repeat the
checker plus that scenario's acceptance tests. Merge into main only after A/B/C integration
passes. For full A execution, add the Docker-capable VM topology first; do not toggle the
Render execution flag just to make the button run.

## Local validation completed

The production frontend and Render Docker image both built successfully. A disposable
container using this image passed live health, exact-origin CORS, invite-only signup,
anonymous rejection, both admin accounts, ordinary-user permissions and logout revocation.
A separate fixed-port container restart preserved the account, session and a disabled
project on a persistent Docker volume. These local tests do not claim cloud deployment
or prove the Render host's mount permissions. No cloud service was provisioned.

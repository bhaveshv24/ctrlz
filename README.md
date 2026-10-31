# CtrlZ

Autonomous software recovery for developers and small teams. CtrlZ inspects repositories,
reproduces failures in Docker, compares recovery strategies and returns a verified **patch**.
It also monitors independent HTTP services through explicit recovery contracts.
CampusPass is an optional demonstration, not a prerequisite.

## Five-command quick start

Prerequisites: Python 3.12, [uv](https://docs.astral.sh/uv/), Node 22+, Git and running Docker.
From this **CtrlZ checkout only**, run:

```sh
uv sync --project backend --extra test --python 3.12
npm --prefix frontend ci
uv run --project backend python scripts/setup_env.py
uv run --project backend python scripts/build_sandboxes.py
uv run --project backend python scripts/dev.py
```

After command 3, add your NVIDIA_API_KEY and chosen NVIDIA_MODEL to `.env` locally before
running command 5. Never put secrets in frontend code. Setup preserves any existing `.env`.
The dashboard is [localhost:5173](http://localhost:5173). Sign in with an email account. First API startup creates two administrators and one user;
read the generated passwords in `backend/data/initial-credentials.txt` (private, ignored by Git).
Use Workspace settings to change passwords or create users. Each ordinary user has a private
workspace. Admins share the existing operator workspace. API documentation: [127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
No Git remote or GitHub account is required for ZIP/local repository repair or HTTP integration.

## Architecture

```text
Detect -> Diagnose -> Plan -> Evaluate -> Authorize -> Execute -> Verify -> Record
  HTTP / repository evidence -> CrewAI + NVIDIA NIM -> deterministic contract gate
  -> approved operations / isolated worktree -> independent tests -> persisted receipt
```

The model proposes; Python safety checks authorize; actual tests and HTTP observations
establish success. SQLite records incidents and evidence; Chroma retrieves local runbooks.
The React/Vite dashboard receives persisted events through authenticated SSE.

## Repository repair

Open **Repository repair**. Import a public GitHub URL, upload a ZIP or copy an allowed local
folder. Inspect its test profile, describe the regression and approve dependency setup if
needed. Python/pytest, Node test and locked Vitest profiles run in isolated Docker containers.
The baseline must reproduce a failure. Tests, configuration and manifests stay immutable.
Download the patch and receipt, then review the patch yourself. CtrlZ never pushes, merges,
deploys or writes to a remote repository. See [support limits](docs/PORTABILITY.md).

For a disclosed local history fixture, run `uv run --project backend python
scripts/create_history_demo.py` from this checkout. Import the printed server-folder path;
request a fix for total amount calculation while preserving acceptance tests. Its known
regression lets you inspect RETRY / COMPENSATE / REPLAN and a reviewable patch without a remote.

## Generic HTTP integration

**Projects → Connect project → Generic HTTP service** accepts your service origin and health
path. Defaults permit monitoring only. Add fixed operation paths, typed parameters, revision
checks, preconditions and postconditions to authorize recovery. Set the named recovery-token
environment variable on the backend and matching service, then restart the backend.

An independent runnable example is included at [examples/dispatch-service](examples/dispatch-service).
Use its [project.json](examples/dispatch-service/project.json) for the endpoint/contract shape.
Set DISPATCH_RECOVERY_TOKEN locally on both processes; start the fixture with the backend's
uvicorn from its directory on port 18002. It starts with a paused queue. Its registered resume
operation needs approval; verification checks health and all three completed fixture jobs.
No CampusPass code is used. The live local rehearsal script is `scripts/verify_generic_service.py`
(run from backend with its virtual-environment Python); it labels programmatic test approval.

## Optional CampusPass demonstration

Only for the ticket-workflow scenarios and controlled Compose replay, place a separate
CampusPass checkout beside CtrlZ. Run `uv sync --project ../campuspass/backend --extra test
--python 3.12` and `npm --prefix ../campuspass/frontend ci`. Then:

```sh
uv run --project backend python scripts/setup_env.py --campuspass
uv run --project backend python scripts/dev.py --campuspass
```

Select the explicit CampusPass preset when connecting its origin `http://127.0.0.1:8001`.
Its storefront is localhost:5174. Demo faults require backend flags and project opt-in.
The optional sibling integration tests skip when that checkout is absent.

## Verification

```sh
uv run --project backend pytest -q
npm --prefix frontend run build && npm --prefix frontend test
```

The root pytest configuration restricts discovery to our backend tests: imported repository
code is never collected on the host. For real Docker acceptance, prefix the first command
with RUN_DOCKER_TESTS=1 (PowerShell: set `$env:RUN_DOCKER_TESTS="1"` first).
[Current counts and submission status](docs/SUBMISSION_CHECKLIST.md),
[feature evidence](docs/FEATURE_CHECKLIST.md), [API](docs/API.md),
[portability validation](docs/PORTABILITY_VALIDATION.md), [local handoff](docs/HANDOFF.md).

## Boundaries

One backend/monitor process, two seeded administrators and isolated ordinary-user workspaces. No multiple Uvicorn workers against the same
incident database. Missing model credentials block reasoning; no simulated model replaces it.
Unsupported test environments and failed acceptance escalate. Dependency downloads require
approval in a separate credential-free container; candidate tests run offline. This is a local
hackathon system, not a public multi-tenant execution service. Docker Compose API containers
do not contain a host Docker socket; use the host backend for worktree/sandbox execution.
External webhook delivery, hosted CI, public hosting and final submission media are not
claimed verified. No remote publication or deployment is part of the current scope.


## Delivery audit and hosting decision

See [promise-by-promise audit](docs/DELIVERY_AUDIT.md) and
[deployment decision and staged plan](docs/HOSTING_PLAN.md). Vercel + Render fits the current
operational backend better than Vercel + Supabase alone. Full Docker repository repair
requires the dedicated Docker-capable host topology. `render.yaml` disables code execution
and public signup explicitly. `frontend/vercel.json` configures the Vite frontend.
The independent [worker supervisor](examples/worker-supervisor/README.md) demonstrates a
real, fixed-container restart through the generic HTTP contract without CampusPass.

CLI scripts using the old operator header need explicit local
`CTRLZ_ALLOW_OPERATOR_TOKEN=true`; browser login always uses email/password.

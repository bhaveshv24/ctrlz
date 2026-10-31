# CtrlZ beyond CampusPass

CtrlZ has two independent entry points: repair an imported repository, or monitor/recover
an explicitly integrated HTTP service. Neither requires CampusPass. CampusPass is an
optional application-specific adapter and replay fixture.

## A judge brings a broken repository

1. Open **Repository repair**. Choose a public HTTPS GitHub URL, ZIP, or server folder.
2. Inspect the detected test runner, tests, source files, dependency plan and support warnings.
3. Describe the regression and intended behavior; optionally supply logs or conversation context.
4. Explicitly approve dependency setup when required. Start **Reproduce & repair**.
5. Show the actual failing baseline, agent file reads, proposed edits, candidate results and
   independent verification in the flight recorder. Download the patch and receipt.
6. Review and apply the patch in the original repository yourself; rerun your full project checks
   before merging or deploying. CtrlZ does not push, merge or deploy a generated patch.

A green baseline is reported as no reproduced regression, not a successful repair. Unsupported
projects produce an explanation. A failed repair retains its real evidence and escalates.

### Supported environments

| Environment | Test command | Dependency setup |
|---|---|---|
| Python 3.12 | `python -m pytest` + JUnit, full discovered suite | Root requirements.txt or PEP 621 dependencies/test extras/test dependency group; common test requirements files. Index packages only; binary wheels required. |
| JavaScript / Node 22 | `node --test` + JUnit | npm registry packages with package-lock.json v2/v3; `npm ci --ignore-scripts` |
| JavaScript / TypeScript | Locked Vitest 3, 4 or 5 + JUnit | Same locked npm setup; Vitest 5 file-system module cache disabled for read-only tests |

These are bounded repair profiles, not support for every application in those languages.
Select a self-contained package subdirectory for a monorepo. Jest, pnpm/yarn-only locks,
workspace linking, browser/E2E tests, databases, external service-dependent tests, native
source builds, private dependencies and arbitrary custom test scripts need additional
integration. The importer does not install the package itself via setup.py or execute
npm lifecycle scripts. Preserve tests/configuration that work within these boundaries.

Imports: 25 MiB ZIP, 64 MiB expanded snapshot, 3,000 files. GitHub import accepts public
`https://github.com/owner/repository` URLs only. ZIP paths/links are checked. Common
credentials, .env files, databases, caches, .git and installed dependencies are excluded;
this is a filename-based filter, not a complete secret scanner. Local source folders must
be inside `REPOSITORY_SOURCE_ROOTS` (OS path-separated); defaults to the checkout's parent.
Snapshots retain source provenance and an upstream commit or archive digest.

Repairs run in detached worktrees. Up to three proposals; at most eight product source
files per proposal; exact text edits support larger files and bounded new source modules.
Tests, manifests and configuration remain immutable and hash-checked. Acceptance compares
JUnit identities, requires real passing cases and rejects newly skipped tests. A baseline
collection failure can change collected identities after its cause is repaired; unchanged
suite bytes and zero new skips remain required. Existing skips are disclosed and preserved.
Verification proves the imported suite passed, not that every possible defect is fixed.

Tests run in non-root, read-only Docker containers with no network, no host Docker socket,
no application credentials, dropped capabilities and CPU/memory/process/time limits.
Dependency setup is separate: only manifests enter a credential-free networked container;
PyPI wheels or locked npm packages enter a temporary volume reused read-only across tests.
Install logs record resolved versions; unpinned Python requirements can resolve differently
on a later run. Volumes and worktrees are removed afterward; cleanup failures are recorded.
Use a dedicated Docker host/user for untrusted projects; this is a single-operator hackathon
system rather than a hardened public multi-tenant execution service.

## Connect another service

Choose **Generic HTTP service** in **Connect a service**. The default observes GET /health
and allows zero mutations. Workflow monitoring is explicitly shown as unconfigured until
its endpoints/assertions exist. HTTP success, latency and configured readiness assertions
jointly determine health; no checkout/ticket fields are required.

For recovery, the service owner supplies:

- Fixed same-origin diagnostics/operation paths and the recovery token's environment name.
- A diagnostic revision, typed flat operation parameters and explicit preconditions.
- An allowlist, approval rules, bounded action count and post-recovery assertions.
- Server-side enforcement of request_id idempotency and expected_revision checks.

The generic adapter sends POST `{request_id, expected_revision, ...parameters}` only to a
registered operation. It never invents shell commands or discovers privileged operations.
High-risk operations always require exact-plan approval, even if the contract's approval
list omits them. All actions are rechecked against fresh diagnostics before execution.
The application must implement idempotency and revision checks; a configuration declaration
alone cannot make an arbitrary endpoint safe.

Read [the independent dispatch-queue example](../examples/dispatch-service/project.json).
Start its fixture from its directory using `uvicorn app:app --port 18002` with a
DISPATCH_RECOVERY_TOKEN, set the same variable on CtrlZ, and register its JSON config.
The fixture starts paused with three pending jobs. Recovery resumes dispatching; verification
requires three accepted health probes, dispatcher running, zero pending jobs and three
completed jobs. Its operation needs approval. It has no CampusPass dependency.

For workflow monitoring, expose `{"discrepancies":[{"id":"resource-id",...}]}`, a resource
path such as `/jobs/{resource}`, and explicit resource_checks using JSON pointers. Mark
resource parameters `resource_bound: true` to bind them to the detected incident.
Acceptance assertions support typed scalar equality, scalar membership and existence.

## API

All endpoints below require X-Operator-Token. No key is accepted in the request body.

- POST /repositories/import: `{kind: "github" | "local", source, subdirectory?: ""}`.
- POST /repositories/upload: raw ZIP body, not multipart.
- GET /repositories/inspect?repository=...&profile=auto: managed clean snapshot assessment.
- GET /capabilities: profiles, source types and execution boundaries.
- POST /continuations: `{repository, requirements, context?, acceptance_profile?, install_dependencies?}`.
- POST /projects: Project with adapter generic-http-v1, integration and contract.

An import is a new managed snapshot, never a mutation of the original source. Assessment
is static; actual runtime/dependency compatibility is established by the baseline, not
promised by detection alone. Replay is available only for the explicit CampusPass fixture.

## Evidence and rehearsal

`verify_portability.py` imports the real public parse repository, verifies its unmodified
suite, injects a disclosed percentage regression into its managed snapshot, then requests
a real NIM repair. It also repairs the independent TypeScript invoice fixture through
locked dependency setup. This is a controlled regression, not discovery of an upstream bug.
`verify_generic_service.py` uses real localhost HTTP and real NIM reasoning against the
dispatch service. It explicitly records programmatic test-operator approval; it does not
claim that a person clicked. Run scripts from backend with its virtual-environment Python.
Full receipts and failed attempts remain in backend/data and the local incident database.

## Repository intelligence and repair readiness

`GET /repositories/intelligence?repository=owner/repo&refresh=false` is operator-authenticated,
read-only GitHub REST evidence. Import and intelligence share normalization for owner/repo,
HTTPS/.git/SSH and tree/blob links. Optional GITHUB_TOKEN stays server-side. Public scans
work anonymously within GitHub's rate limits. Private scan access does not grant clone
credentials: use an authorized local snapshot or ZIP for private repairs.
Every value records source, observed_at and complete/sampled/unavailable coverage. Missing
values are unknown; GitHub's 404 can mean absent or inaccessible. The five-minute cache is
scoped to repository and credentials and stored in existing events, with no new job table
or SSE endpoint. Rate-limited refreshes retain available results and the previous snapshot.
CI combines Actions, checks and statuses for the observed HEAD; failing checks can prefill
repair requirements. This neither reruns remote CI nor changes a repository.

## History-aware code tournament

New Git imports retain up to 29 sanitized first-parent source snapshots plus the final
imported snapshot (30 maximum). ZIPs and older flattened imports remain repairable but
have no compensation history. The original `.git` objects, author messages and historical
secret files are never copied into managed history. Each source snapshot is filtered with
the same source/path/secret rules; current HEAD acceptance, manifests and configuration
stay fixed. Thus this is source-history testing against today's acceptance suite, not a
claim to reproduce every historical dependency environment. Historical source is bounded
per file, snapshot and total (128 MiB); unsafe/unavailable history is explicitly reported.

RETRY runs the original suite twice more. Two passing reruns qualify a zero-diff outcome
with an explicit flaky-test warning; they do not establish a permanent source fix.
COMPENSATE searches the latest 16 snapshots of the retained history: one passing lower
bound, up to four bisect runs and one revert test, at most six sandbox runs. It records an
observed adjacent good/bad source boundary under a monotonic-history assumption; earlier
or non-monotonic regressions may be inconclusive. A conflicting revert, missing lower bound,
changed acceptance or excessive source scope does not qualify. REPLAN evaluates the bounded
agent patch loop even when compensation succeeds; model failure cannot erase a verified
compensation candidate. All three are recorded, with reasons for nonqualification.
Selection is deterministic: pass original immutable acceptance; smallest added/deleted-line
count; fewest strategy sandbox runs; stable strategy ID. Results and suspect upstream/snapshot
SHAs appear in Story, Strategies and Receipt, including the readable brief. Revert and model
patches are artifacts only. Original sources, Git refs and remote repositories are not mutated.

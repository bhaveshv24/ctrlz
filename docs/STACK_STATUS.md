# CtrlZ stack implementation

The frontend and API start together with `npm run dev`. Settings → Recovery runtime →
Check runtime inspects installed packages, a real database query, the runbook collection,
Git, the Docker daemon and configured sandbox images. Credential presence is reported
separately from verified inference or webhook delivery.

| Layer | Implementation |
|---|---|
| Frontend | React, TypeScript and Vite with existing routes and forms |
| Styling | Tailwind, Lucide, branded CSS and lazy-loaded Three.js |
| API | FastAPI REST, authenticated account gateway and isolated workspaces |
| Agents | CrewAI diagnosis, sequential planning/operations agents and RecoveryFlow |
| Model | CrewAI LLM with NVIDIA NIM's OpenAI-compatible endpoint and structured Pydantic outputs |
| Configuration | Pydantic Settings validates process environment supplied from .env by the launcher |
| Persistence | SQLAlchemy/SQLite incidents, contracts, probes, intents, events and receipts |
| Retrieval | Persistent ChromaDB runbook index with local deterministic embeddings |
| Source management | Bounded Git inspection, sanitized imports, detached worktrees and reviewable patches |
| Verification | Offline Docker pytest, Node test and locked Vitest acceptance profiles |
| Monitoring | asyncio and HTTPX health, workflow probes and independent verification |
| Diagnostics | Registered read-only HTTP tools and a fixed-container Docker worker supervisor |
| Live updates | Authenticated SSE, event cursors, reconnect and polling fallback |
| Notifications | Slack/Discord webhook transport with persisted delivery results for service and code outcomes |
| Sandbox | Restricted containers, immutable acceptance tests and separately approved dependency setup |
| CI | GitHub Actions matrix for Linux/macOS/Windows and Linux Docker acceptance |
| Tests | pytest, HTTPX integration tests, real Docker tests and frontend Vitest |

The worker supervisor adds bounded CPU, memory, network, block-I/O and PID samples to its
authenticated diagnostics endpoint. It accepts only a fixed configured container and
named operations. Ordinary recovery agents do not receive a general shell.

Compose creates its own named network and persists repository imports alongside incident data.
The default API container exposes monitoring/API functionality. Repository execution requires
the documented Docker-capable host runner configuration.

The current Git tree excludes dependencies, bytecode, generated databases, credentials and
local incident artifacts. Existing local files remain available. Removing files from current
tracking does not remove them from older commits.

## Verified in this checkout

- Full Docker-enabled backend suite passed 113 tests.
- Production frontend build and 18 Vitest tests passed.
- The in-app browser signed into an isolated local account and executed the normal Settings runtime check.
  SQLite, three indexed runbooks, Git, Docker and all supported sandbox images were available.
- Docker Compose configuration validation passed.
- Hosted CI and external inference/notification calls have not been run by this change.

## Verification limits

Automated tests use explicitly identified model fixtures and mock webhook transports.
Live NVIDIA inference and external webhook delivery require configured accounts.
Hosted Actions and Windows/macOS runner results exist only after the workflow actually runs.
This change does not claim public multi-tenant production readiness or hosted deployment.

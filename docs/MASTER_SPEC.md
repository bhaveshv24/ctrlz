# CtrlZ — Agentathon 2026

Team: Commitment Issues. Product: autonomous software recovery for small teams.
CampusPass is a separate demonstration application, never part of the recovery core.

## Sources and limitations
The supplied implementation directive is the authoritative scope. The imported chat API
returned only its last five turns, with no older cursor. Earlier conversation details
cannot be reconstructed or claimed as read. Preserve future decisions in these docs.

## Architecture
Two independent Git repositories under agentathon/: ctrlz and campuspass. Python 3.12,
FastAPI, Pydantic, SQLAlchemy/SQLite; React/TypeScript/Vite/Tailwind; CrewAI agents and
Flows; NVIDIA NIM; ChromaDB runbooks; HTTPX/asyncio monitoring; SSE; Docker Compose;
Git worktrees; pytest; macOS/Windows CI; optional Slack/Discord webhooks.

Lifecycle: Detect → Diagnose → Plan → Evaluate → Authorize → Execute → Verify → Record.
One coordinator handles health, workflow, and explicitly imported code incidents.
Flight recorder stores every transition, diagnostic tool result, proposal, gate decision,
operation intent/result, independent verification, and receipt. Recovery is never inferred
from an LLM's prose. Exceptions escalate; missing credentials block reasoning explicitly.

## External interface v1
Project configuration pins an HTTP origin, diagnostic/health/workflow paths, secret-token
environment variable, named operations, verification rules and a recovery contract.
No project-supplied arbitrary shell, SQL, URL, or container name is executed.

CampusPass exposes GET /health, /diagnostics, /workflows, /orders/{id};
POST /operations/{name} accepts {request_id, expected_revision, order_id?}.
Administrative reads/writes require X-Recovery-Token. Mutations are idempotent by request
ID, preconditioned on revision and constrained to named repair operations. Demo faults
have their own authenticated, explicitly enabled API. Public checkout is idempotent by
client request ID; ticket entitlements are unique by order ID at the database layer.

CtrlZ exposes projects, incidents, receipts, persisted SSE events, scoped approval and
retry endpoints, and explicit continuation imports. Mutation API requires operator token.
Approval is bound to incident + exact candidate and contract and does not bypass forbidden
operations. Requests are local-operator actions; no public multi-tenant auth is claimed.

## Safety and recovery contracts
Unknown operations and unknown parameters fail closed. Plan evaluation uses Boolean
eligibility, concrete preconditions and available verification evidence, never invented
scores. High-risk allowed operations pause for human approval; prohibited operations stay
blocked after approval. Recheck evidence immediately before mutation. Persist intent first;
after uncertain failures reconcile through idempotent endpoint replay and verification.
On process restart, interrupted work escalates for explicit retry, never silently succeeds.

Code imports must be under an operator-configured repository root. A clean committed Git
snapshot becomes a detached worktree. Only bounded text files may change; no tests/config/
symlinks/secrets. Candidate code runs only in a networkless, nonroot, resource-limited
Docker sandbox without host credentials or Docker socket. Produce a patch for review;
never silently change the imported branch. Acceptance tests are operator-owned and immutable.

## Scenarios
A: explicitly supplied repo + requirements + conversation context → evidence inspection,
NIM continuation proposal → isolated patch → baseline/candidate tests → verified artifact.
B: paid order missing entitlement despite healthy website → inspect worker/payments/tickets,
reject force issuance, compare retry vs restart vs code repair, continue workflow idempotently,
verify exactly one valid ticket. Genuine worker code defect uses the code import pathway.
C: injected checkout outage detected by monitor → real health/diagnostics + retrieved runbook,
compare options, reject unauthorized destructive operation, execute mitigation, verify stable
health and checkout availability, send webhook receipt. A mitigation is not a permanent fix.

## Delivery boundaries
At bootstrap no API key was available and Docker's daemon was stopped. The user subsequently
supplied a NVIDIA key and selected Nemotron 3.5 Lightning. Docker was started and real live
acceptance runs were performed; current evidence belongs in FEATURE_CHECKLIST.md.
Isolation-dependent features fail closed when Docker is unavailable. Offline tests inject an explicitly labeled
test reasoner; it is never exposed as live agent intelligence. Replay supports controlled
CampusPass fault environments; arbitrary production replay is out of scope.

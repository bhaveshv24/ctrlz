# CtrlZ local project handoff

CtrlZ is the primary product; CampusPass is an optional independent demo. Start from the
five-command standalone quick start in README.md. Current usage/limits are in PORTABILITY.md.

- Recovery engine: backend/ctrlz/engine.py and flow.py; deterministic gate in safety.py.
- Repository import/repair: repository.py, continuation.py and sandbox.py.
- Generic integration: http_adapter.py and integration_models.py.
- Dashboard: frontend/src/App.tsx; incident workspace in components/IncidentWorkspace.tsx.
- Evidence: SQLite incidents/events, locally ignored backend/data receipts and patch artifacts.
- Credentials: server-side .env only; never print, stage or publish its contents.
- Review boundary: return patches; no pushing, merging, deployment or remote repository writes.
- Local verification and current counts: SUBMISSION_CHECKLIST.md and FEATURE_CHECKLIST.md.

Run exactly one backend monitor. Start Docker before code repair. Missing credentials block
real reasoning. Existing supported tests must reproduce a regression; source snapshots and
immutable acceptance tests are preserved. Historical live model evidence is documented in
PORTABILITY_VALIDATION.md, including disclosed injected regressions and earlier failed attempts.

Submission is due 31 October 2026. Public hosting, remote publication and media are not
verified by a local test pass and are outside the current authorized scope.

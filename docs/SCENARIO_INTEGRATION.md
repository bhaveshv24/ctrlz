# Scenario integration into main

Integrated `origin/Merged-scenarios` at `f2f8b04`, which already contains
`origin/scenario-a` at `f23b341`, onto main at `3727980`.
The pre-merge main is retained as `backup/main-before-scenario-integration`.
No branches were deleted and no changes were pushed.

Preserved main's Supabase account/workspace persistence, session/network recovery,
Windows ZIP validation and byte-preserving exports, motion choreography, and removal
of numbered intro navigation, external notifications and unwanted settings panels.
Retained both sides of the ProjectDialog and stylesheet conflicts.

Integration repairs beyond Git conflict resolution:

- Adapted runtime ingestion and workflow deadline leases from SQLite-only locking
  to the existing per-workspace Postgres transaction locks.
- Enabled RLS on the new private workspace tables.
- Persisted source credentials and pseudonym salt in private Postgres workspace
  tables, retaining the server-only credential-file provisioning interface.
- Shared a bounded PostgreSQL pool across schemas; restored driver row factories
  after account reads so pooled workspace reads remain compatible.
- Included additive runtime/workflow tables and sequence IDs in SQLite migration.
- Applied original ZIP-name validation to workflow audit uploads on Windows too.
- Removed Linux-only assumptions from Docker integration tests and checked log
  symlinks on hosts without O_NOFOLLOW.
- Extended the PostgreSQL CI job to exercise runtime and workflow/deadline suites.

Validation includes frontend build/tests, backend Docker acceptance, real disposable
Postgres account/workspace/telemetry tests and workflow deadline reconciliation,
including one incomplete item among 1,000 workflows. Windows/macOS/Linux remote CI
and hosted end-to-end checks still require the user's push/deployment. Live external
AI, production collectors and provider credentials were not exercised by local fixtures.

Uploaded source snapshots, local Git worktrees, audit source artifacts and exported
ZIPs still require durable artifact storage on an ephemeral host. Database persistence
and credential persistence do not replace that storage. A local Docker daemon is not
a remote runner for Render.

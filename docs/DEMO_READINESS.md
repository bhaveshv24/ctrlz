# Final demo readiness — 1 November 2026

## Verified in this audit

- Full Docker-enabled backend suite: 279 passed, 3 skipped.
- Frontend: 60 tests passed; TypeScript and Vite production build passed.
- Coverage includes account roles/isolation, repository import/audit, sandbox repair and completion, exported evidence, workflow monitoring and recovery guards. Fixture tests do not prove a live model recovery.
- A real request to the locally configured NVIDIA model returned HTTP 200 with content. This proves provider access, not an end-to-end model repair.
- Public frontend and backend health returned HTTP 200; favicon exists.
- Frontend bundle references the correct Render API and contains consolidated repository inspection.
- Exact frontend CORS preflight succeeded; anonymous projects request returned 401; public sign-up is enabled as intended.

## Remaining boundaries before claiming every component works

- Hosted authenticated pages, runtime capabilities, database restart persistence and a full live recovery were not exercised in this audit: no matching hosted account credentials were available. No new production accounts or recovery actions were created.
- Render Free does not provide the local Docker execution boundary. Rehearse full repair/completion locally using the Docker-capable launcher; do not claim a hosted repair until a runner is available and actually verified.
- Account gateway OpenAPI lists authentication routes only; absence of workspace routes there is not evidence that deployment lacks those routes.
- Three backend cases were skipped; the passing count does not include them. A disposable PostgreSQL integration environment is not configured for this run.
- Visual interaction/animation QA was not performed because browser use is disabled in the current Work settings. Automated frontend tests and build do not prove animation quality.
- Uploaded repositories and patch files on ephemeral hosted disk are not made durable merely by using PostgreSQL. Download demo artifacts before a restart/redeploy.

## Final rehearsal

1. Start Docker and run `python3 dev.py` from the repository root. Sign in locally.
2. Import the intended demo ZIP, inspect, review findings, reproduce a failure, repair, and download ZIP/patch/receipt. For completion, explicitly select completion and provide requirements.
3. Demonstrate B/C only against your configured controlled service; verify the resulting independent health/workflow evidence and approval behavior.
4. On the public site, sign in, open each tab and confirm live data/loading/error states. Verify a real inspection report rather than only the login screen.
5. Before presenting, download the latest artifacts and confirm the exact deployed source version. All pushes and deployments remain the user's action.

## Checker correction

`scripts/check_deployment.py` now accepts intentional public sign-up. Use `--require-invite-only` when checking an invite-only staging environment.

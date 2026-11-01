---
name: ctrlz-repository-inspection
description: Implement or verify CtrlZ's Inspect repository flow for unfinished projects and completed code that needs review, including source risks, dependency advisories, readiness, isolated baseline tests and evidence export.
---

# CtrlZ repository inspection

Use for changes to the repository repair tab's Inspect flow or verification of its
inspection promise. This skill does not authorize pushing, deploying, editing user
repositories, or claiming comprehensive security certification.

## Product contract

Inspect produces one report tied to the imported snapshot commit:

- Static source findings with file/line locations, rule and uncertainty. Parse Python
  without importing it. Treat JavaScript/TypeScript pattern matches as potential risks,
  not confirmed exploits. Never include suspected credential values in evidence.
- Known dependency advisories for resolved npm lockfile packages and pinned PyPI/uv
  versions. OSV receives only ecosystem, package name and version; disclose that on
  the Inspect form. Ranges, unsupported locks, truncation, advisory errors and missing
  dependency versions remain explicit coverage gaps, never a green security result.
- Repository readiness: supported test profile, acceptance files and configuration
  warnings. This is not deployed uptime or a live production health check.
- An actual baseline test run only in the existing Docker sandbox. Dependency setup
  uses its existing permissions, tests remain offline, and source is unchanged.
  No runner, unsupported profiles and failed setup are visible blocked/unavailable
  results. Static/advisory checks still return when Docker execution is disabled.

Passing tests do not suppress source or dependency findings. No findings means only
that the completed bounded checks found none. Do not label the repository secure or
fully healthy. Inspection itself does not repair, rewrite tests, install on the host,
execute package scripts on the host, change manifests, commit or deploy.

## Implementation map

From the CtrlZ repo root, inspect these files before changing the flow:

- `backend/ctrlz/repository_audit.py`: static checks, resolved dependency inventory,
  advisory lookup and consolidated result.
- `backend/ctrlz/main.py`: authenticated `POST /repositories/audit`; validate the
  managed workspace through Continuation.repository before reading source.
- `backend/ctrlz/continuation.py` and `sandbox.py`: baseline and isolated execution.
- `frontend/src/components/ContinuationForm.tsx`: Inspect calls the audit endpoint,
  preserves loading/error states, and allows report-only inspection without Docker.
- `frontend/src/components/RepositoryInspection.tsx`: visible findings, coverage,
  test state, limitations and downloadable report.

Keep the old `/repositories/diagnose` contract compatible. Repairs still require
reproduced acceptance failures; completing features remains a separate explicit
mode. A vulnerability that needs a new regression test is not automatically verified
just because unrelated existing tests passed.

## Verification

Use inert risky fixtures, mock advisory success/failure/pagination and test both
passing and failing baselines. Prove that source stays unchanged, scripts do not run
on the host, another user's snapshot is rejected, and unavailable checks cannot be
reported as clean. Run backend audit tests, frontend report tests and the production
build; use Docker acceptance where execution behavior changed. Never substitute
fixture results for live provider or production verification.

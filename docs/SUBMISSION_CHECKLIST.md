# Submission checklist — 31 October 2026

Current scope is **local only and patch-only**. There is no remote for this project; no remote
creation, pushing, merging, deployment or remote repository writes are authorized.

| Deliverable | Actual state |
|---|---|
| Code | Local Git repository; phase commits only. No hosted repository URL exists. |
| Documentation | Standalone five-command CtrlZ quick start; CampusPass optional; current local handoff. |
| Demo video | Not recorded in this phase. Use real receipts and disclose inference waits. |
| Pitch deck | Final alignment not verified. |
| Live project link | Localhost only. No public deployment is claimed. |

## Current executed checks

Target-aware Demo Lab, 31 October: `uv run --project backend pytest -q`: **87 passed, 7 skipped**.
`npm --prefix frontend run build && npm --prefix frontend test`: **build passed, 18 tests passed**.
The seven skips require explicit RUN_DOCKER_TESTS=1. The current full Docker-enabled suite
passed **94 tests**. Browser QA for this pass was blocked by Work settings; API QA passed.

## Local judging sequence

1. Start CtrlZ alone using README.md; no CampusPass checkout is required.
2. Import ZIP/local/GitHub source, inspect readiness and reproduce a baseline failure.
3. Review compared strategies, original acceptance checks and the exported patch/receipt.
4. Demonstrate the included generic dispatch HTTP service and its scoped approval.
5. Optionally demonstrate CampusPass only if its independent checkout is available.

- [ ] Final video recorded and reviewed.
- [ ] Final pitch deck matches actual behavior and boundaries.
- [ ] Latest receipts/patches reviewed locally.
- [ ] Public deliverable requirements reconciled with the decision not to publish remotely now.

No metric, public URL, delivered notification or hosted CI run is inferred from local tests.

Phase C: known-bad sanitized history selected COMPENSATE, exported a patch that passed
`git apply --check`, and left both original and imported HEAD unchanged. Nine targeted
Docker/history tests passed, including the existing Python/Node/Vitest repair and replay tests.

Historical pre-Demo-Lab Docker-enabled full suite: **84 passed** (`RUN_DOCKER_TESTS=1 uv run --project backend pytest -q`).
Recovery Core uses separate lazy Three.js/GSAP chunks. See PHASE_VALIDATION.md for the
phase-by-phase results, native browser evidence and the explicit unverified-items list.

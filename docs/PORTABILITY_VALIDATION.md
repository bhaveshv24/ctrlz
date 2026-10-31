# Portability validation — 31 October 2026

Actual local execution with the configured NVIDIA model
`nvidia/nemotron-3.5-lightning-30b-a3b`, CrewAI, Docker Desktop and real HTTP.
These are execution results, not predicted judge scores or production claims.

| Proof | Result | Local incident |
|---|---|---|
| Independent TypeScript invoice fixture | Live NIM patch; original 3/3 Vitest tests pass after approved locked npm setup; candidate tests offline | 176c4966-05e1-4c13-aa47-f5f663a402ae |
| Public Python parse snapshot | Unmodified upstream first verified 117 passed / 1 existing skip; disclosed percentage regression then repaired by NIM; same 118 case identities, 117 pass / same skip | 4480cb07-9fc6-432e-9fa2-9bb477e9dc7f |
| Independent dispatch queue service | Real localhost HTTP + live NIM diagnosis/planning, unregistered strategy rejected, high-risk approval required, all four post-recovery checks pass; all 3 jobs completed | 6cb6b57d-485d-4e67-9986-35df467d0ca2 |

Python provenance: https://github.com/r1chardj0n3s/parse at
7f07b64089338ee7b7db85a752eb45c4816c2657. Its original license and test files were retained.
The defect was deliberately injected into a managed snapshot. It was not an upstream bug.
No patch was pushed upstream or applied to the original repository.

The TypeScript fixture is purpose-built and independent of CampusPass; it is not a claim
that a third-party JavaScript project had this defect. Both source snapshots stayed unchanged;
patches came from detached worktrees. The generic service uses no CampusPass adapter or
business fields. Its approval was a programmatic test-operator approval, explicitly recorded,
not a claim of a physical human click. Its temporary process has been stopped and its
project monitoring is disabled; receipts remain inspectable.

Earlier failed repairs, malformed model output, runtime-cache failures and provider timeouts
were retained. They led to fixes for dependency-volume copy permissions, Vitest's module
cache on read-only filesystems, JUnit failure detail capture, bounded schema feedback and
smaller initial context. Successful receipts do not erase earlier failures. Live inference
latency varies substantially; do not promise instant fixes during judging.

## Automated checks

**52 backend tests passed** with RUN_DOCKER_TESTS=1, including the sibling CampusPass integration.
Backend suite includes real Python/Node/Vitest worktree execution and optional CampusPass
Compose replay. It covers generic HTTP monitoring without checkout fields, independent
service recovery, preconditions, high-risk approval, typed parameters, postcondition failure,
source imports, ZIP traversal, local source boundaries, dependency consent, test identities,
new skips, custom pytest filenames and embedded doctest preservation. Test fixtures are
explicitly labeled and never presented as live AI calls.

Frontend production build and six existing frontend tests pass. Desktop browser checks
verified local-folder import → detected TypeScript profile → dependency approval boundary,
generic service onboarding with blank fields, and healthy HTTP monitoring with workflow
checks shown as **Not configured**. The new mobile viewport check could not run because
the browser viewport capability was unavailable; do not claim it passed this session.

## Remaining submission work

This local build is not publicly deployed. Remote repositories, live hosting/TLS, final
pitch deck, video and clean-browser public-link checks remain in SUBMISSION_CHECKLIST.md.
DEPLOYMENT.md describes the prepared host topology and both sandbox images. A deployment
without Docker execution supports HTTP recovery only and must be labeled accordingly.

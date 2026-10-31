# Implementation plan

1. Establish two repositories, shared HTTP contracts and source-of-truth docs.
2. CampusPass: persistent checkout, worker, unique entitlements, fault controls, tests.
3. CtrlZ: recorder, project contracts, adapters, safety, tournament, verifier, coordinator.
4. CrewAI/NIM tools and Flow, Chroma runbooks, monitor, approvals, receipts, notifications.
5. Isolated continuation and replay, with fail-closed Docker execution.
6. Connected recovery dashboard and independent CampusPass storefront.
7. Cross-repository HTTP integration tests, frontend builds, Docker/CI/setup/demo docs.

Track Implemented / Tested / Demonstrated separately in FEATURE_CHECKLIST.md. A test using
an injected reasoner validates execution infrastructure, not live NIM reasoning. Do not mark
Docker, NVIDIA, or webhook delivery demonstrated without observing them.


## Portability completion

The executed extension is documented in PORTABILITY.md and PORTABILITY_VALIDATION.md.
This supersedes earlier dependency-free Python-only and CampusPass-default assumptions.

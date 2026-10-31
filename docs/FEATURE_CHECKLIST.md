# Feature completion and evidence

New account/hosting work and exact A/B/C promise coverage are recorded in
[DELIVERY_AUDIT.md](DELIVERY_AUDIT.md). The baseline totals and single-operator UI statements
below describe the earlier revision; see that audit for current validation.

Updated 31 October 2026. Implemented, tested and demonstrated are separate claims.

Current required checks (target-aware Demo Lab): **87 backend tests passed, 7 Docker tests skipped**;
frontend production build passed; **18 frontend tests passed**. Full Docker-enabled suite: **94 passed**. The previous full Docker-enabled
portability run passed **52 backend tests** including the optional sibling integrations.
Hosted CI and external notifications are not claimed verified. Counts below are historical
only where explicitly labeled; this paragraph is the current baseline.

| Feature | Implemented | Tested | Demonstrated / evidence |
|---|---|---|---|
| Two independent product Git repositories | Yes | Yes | Separate ctrlz/.git and campuspass/.git; parent has no .git |
| Shared v1 HTTP adapter contract | Yes | Yes | Real localhost HTTP integration tests |
| CrewAI agents + Flows + NVIDIA NIM | Yes | Yes | Live selected Nemotron 3.5 Lightning model, actual read tool calls |
| ChromaDB runbook retrieval | Yes | Yes | Live agent selected search_runbooks; lexical hash embeddings |
| Autonomous health/workflow monitoring | Yes | Yes | Live Docker outage detected without troubleshooting prompt |
| Scenario B paid-order recovery | Yes | Yes | Live NIM Docker recovery, approval pause, exactly one valid entitlement |
| Flight recorder and persisted restart state | Yes | Yes | SQLite events, interrupted execution escalation, cursor tests |
| Deterministic safety gate | Yes | Yes | Live model's invented operations rejected; prohibited strategies blocked |
| Constraint-based recovery tournament | Yes | Yes | Actual precondition/allowlist results, no invented numeric scores |
| Bounded planner revision from gate feedback | Yes | Yes | Regression test observes exactly one allowed revision |
| Scoped approval pause / contract binding | Yes | Yes | Real HTTP test pauses before worker resume; wrong hash rejected |
| Idempotent operations and unique ticket entitlements | Yes | Yes | Concurrent retries, stale revisions, request-key conflict tests |
| Independent health/business verification | Yes | Yes | Live C health checks; missing-ticket verifier rejects healthy website |
| Code continuation, worktree and Docker tests | Yes | Yes | Live NIM patch incident 3fbdca88-0f10-4441-91f9-d48544f2477b |
| Code revision from syntax/test failures | Yes | Yes | Invalid syntax fixture revised; same acceptance tests required |
| Isolated recovery replay | Yes | Yes | Real disposable Compose outage reproduced/repaired; resources cleaned |
| Recovery receipts and downloadable JSON | Yes | Yes | Persisted evidence, candidates, decisions, actions and verification |
| React control center + authenticated SSE | Yes | Yes | Browser project registration, live timeline, desktop/mobile layouts |
| CampusPass checkout, worker and ticket verification | Yes | Yes | Browser simulated checkout → valid entitlement |
| Genuine legacy-worker defect and patch pathway | Yes | Yes | Actual UUID formatter defect reproduced; verified NIM patch artifact |
| Docker images and separate persistence | Yes | Yes | Four images built; live CampusPass container and replay |
| Webhook notification delivery | Yes | Mock transport tested | External Slack/Discord delivery requires a supplied webhook |
| macOS/Windows/Linux CI configuration | Yes | Local macOS tested | Hosted GitHub Actions not executed in this workspace |
| Arbitrary production infrastructure recovery | No | No | Only explicitly registered adapter operations are supported |
| Automatic merge or deployment of code patches | No | No | Deliberately requires a separate operator review/deploy step |

## Executed automated checks

- Required backend command: 87 passed, 7 optional Docker checks skipped.
- Required frontend command: production build passed, 18 tests passed.
- Historical Docker-enabled portability validation: 52 passed.
- CampusPass is optional; its historical nine tests are not part of the standalone prerequisite.

## Live model evidence

User-supplied model: `nvidia/nemotron-3.5-lightning-30b-a3b`. The optional CrewAI `openai/`
routing prefix is normalized without changing the user’s model selection. The live code
agent initially produced an invalid patch and later hit a reasoning-token budget limit;
those failures remain recorded. After provider settings and feedback handling were fixed,
the code passed both immutable tests and yielded a verified patch. The original branch
was never modified.

Host outage incident `46aae9fe-2148-46e0-98e4-60af2a4c42db` recovered through actual NIM
tool selection, allowlisted execution and three fresh health probes. Earlier rejected
plans remain in its QA flight recorder, rather than being hidden.

The independent live Docker run writes full receipts under backend/data/live-scenario-C.json
and backend/data/live-scenario-B.json as each scenario finishes. These local evidence files
are ignored by Git because incident evidence should not automatically be published.
The live test explicitly labels its programmatic operator approval; it does not claim a
physical human clicked a button. Judges can exercise the actual approval UI in DEMO_GUIDE.md.

Both live Docker scenarios passed: C incident `f0bdb5a1-6ff5-4ff5-8ba7-3361604fcc05`
and B incident `bc07ce66-d83e-4043-b6f5-f0ed9bdf9a55`. Scenario B independently read the
paid order back with job=done and exactly one valid ticket. All four final Docker images
built successfully; the nonroot CtrlZ API and both nginx frontend/API proxies returned
successful real HTTP responses during container smoke tests.

Final running-configuration check also passed: incident
`11f9d056-bcad-47e5-819b-68cdad133868` was detected and recovered autonomously by the
normal CtrlZ API after its last reload. The persisted model is Nemotron 3.5 Lightning;
all three fresh health probes passed. This receipt and the verified code incident are
visible in the normal running dashboard after operator sign-in.

## Scope limits to communicate

Repair supports bounded Python/pytest, Node test and locked Vitest profiles with existing
acceptance tests and optional explicitly approved isolated dependency setup. It returns a tested patch, not a deployed fix. Replay supports the
controlled CampusPass fault fixtures and never mutates the original service. The default
CtrlZ Compose container has no host Docker socket; use the host backend for sandbox/replay.
One operator and one backend/monitor process are supported. This is a local hackathon
system, with no claim of multi-tenant production readiness.

## Portability extension

See PORTABILITY.md for usage and limits, and PORTABILITY_VALIDATION.md for actual results.
New defaults are generic HTTP with zero permitted mutations. Source import supports public
GitHub, ZIP and allowed local folders. Repair profiles cover Python/pytest, Node test and
locked Vitest, with explicit isolated dependency setup and offline test verification.

Repo Intelligence: shared GitHub normalizer, source/coverage-aware REST evidence, credential-scoped
event cache and Repair readiness with failing-HEAD CI prefill. Twenty-eight mocked cases cover
normalization, malformed inputs, access, empty/archived/fork/no-CI, limits, timeout, partial data and cache.

Phase C: known-bad sanitized history selected COMPENSATE, exported a patch that passed
`git apply --check`, and left both original and imported HEAD unchanged. Nine targeted
Docker/history tests passed, including the existing Python/Node/Vitest repair and replay tests.

Historical pre-Demo-Lab full Docker-enabled suite: 84 passed. Phase D: branded procedural Three.js on sign-in
and Overview, GSAP ScrollTrigger enhancement, mobile/reduced/low-power capability policy
tests, static fallback, resource cleanup, and native Chrome visual verification.
See PHASE_VALIDATION.md; its remaining Hallmark findings and unverified modes are disclosed.


## Target-aware Demo Lab

Repository cards derive from inspected profiles, detected test files and editable product files.
A disclosed injected regression runs only in a sanitized managed copy after proving a passing
original baseline and a failing copied baseline with the same collected tests. Normal repair
then produces a patch; the source snapshot stays unchanged. Generic HTTP targets offer only
monitoring and contract review, with unsupported fault injection disabled and explained.
CampusPass C/B/reset controls remain adapter-specific. History is scoped per target, linking
incidents and receipts; injection disclosure appears in both Story and Markdown/JSON receipts.
Ten new backend tests and five frontend capability tests cover these boundaries. Browser
visual QA was blocked by disabled local browser access; live Docker/API proof was performed.

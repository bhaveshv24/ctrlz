# Local phase validation — 31 October 2026

No remote was added, no remote repository created and no push/merge/deployment performed.
All changes are local phase commits. .env was neither printed nor staged.

| Phase | Required backend command | Frontend build / tests | Additional evidence |
|---|---|---|---|
| A | 47 passed, 5 Docker checks skipped | Passed / 6 passed | Standalone quick start, optional CampusPass, ignored build cache, no pasted handoff |
| B | 75 passed, 5 skipped | Passed / 6 passed | 28 mocked GitHub scenarios; later actual anonymous REST scan through the form |
| C | 78 passed, 6 skipped | Passed / 6 passed | 9 targeted Docker/history tests passed; known bad commit identified, revert artifact accepted, git apply --check passed |
| D | Final check recorded in SUBMISSION_CHECKLIST.md | Final check recorded there | Native Chrome 3D rendering, isolated overview/login/repair navigation and console checks |

## Recovery Core

Three.js 0.187 and GSAP 3.15 are lazy chunks; no React rendering framework was replaced.
The procedural keycap uses four draw calls and about 2,100 triangles; no external 3D model,
HDR environment or photo downloads. Effective pixel ratio is capped at 1.5; visible rendering
is capped at approximately 30fps and paused offscreen/hidden. Geometry, materials, textures,
observers, listeners and ScrollTriggers are disposed on unmount. Static initial drawing
precedes replacing the fallback. Mobile, coarse pointers, low CPU/memory and reduced motion
skip 3D imports; reduced-motion changes also tear down active 3D.

Build measurements: scene chunk about 140 KiB gzip plus about 46 KiB gzip for GSAP and
ScrollTrigger. Vite warns about the scene's >500 KiB uncompressed size; it is a separate
lazy chunk, not part of the initial application load. No warning was hidden by changing
Vite thresholds. Seven capability-policy tests cover desktop/mobile/reduced/touch/low-power
and missing optional hardware hints.

Native Chrome displayed the dimensional lime undo assembly. The in-app browser's capture
intermittently omitted the GPU layer; a native screenshot was used to verify actual rendering.
The QA workspace loaded Overview, removed its canvas on Repository repair navigation, and
completed an actual anonymous GitHub REST scan. Console warning/error capture was empty in
these tested flows. No production credentials were used to log into QA.

Hallmark before/after kept checks retained 8/8 links, 7/7 fields and 73/73 existing handlers.
Colors/fonts were moved to root tokens without changing the existing values. Mechanical
findings fell from 496 FAIL / 307 REFLEX to 37 FAIL / 4 REFLEX before the final additive
motion tests. The remaining style findings concern the existing verbatim labels, punctuation
and monospace voice that the user explicitly required retaining. This is not a claim of a
zero-finding Hallmark audit. Its automated render tier was unavailable (puppeteer-core absent);
native/in-app browser checks were used instead. Existing routes and copy were preserved.

## Cinematic Recovery Core refinement

The follow-up visual pass adapts the reference reel's visible floating-panel and particle
motifs to CtrlZ. Sign-in and Overview share a procedural layered undo core, three recovery
strategy panels, rewind fragments and particle trails. These labels explain the architecture;
they do not represent measured incident outcomes. Existing content, routes and recovery
behavior remain intact. Pause/resume and replay controls are keyboard accessible.

The scene uses 700 or 1,400 procedural particles depending on CPU hints, 36 instanced fragments,
a 30 fps rendering cap and a maximum 1.5 pixel ratio. No downloaded models or textures were
added. Mobile, coarse-pointer, reduced-motion and low-resource eligibility gates remain.
This richer scene supersedes the initial Phase D geometry description above. Its lazy scene
chunk is 566.68 kB minified / 142.84 kB gzip; Vite's chunk-size advisory remains visible.

Validation: backend `uv run --project backend pytest -q`: **78 passed, 6 skipped**;
frontend build passed and `npm --prefix frontend test`: **13 passed**. Native Chrome displayed
the new sign-in scene; pause and replay were exercised in the in-app browser, with no captured
console warnings or errors. The updated Overview composition was build-checked but not
visually rechecked in an authenticated workspace in this pass. Hallmark kept checks remain
8/8 links, 7/7 fields and 73/73 handlers, with the same 37 FAIL / 4 REFLEX retained-style
findings; its automated render tier remains unavailable. Full Docker tests were not rerun
for this frontend-only pass.

## Unverified / boundaries

- Physical mobile hardware, battery measurements, real reduced-motion OS toggling and forced
  GPU/context-loss presentation were not exercised; capability gates and CSS fallbacks exist.
- Private-repository and rate-limit/timeout variants are mocked tests, not live privileged calls.
- Hosted CI, external webhook delivery, public hosting, submission media and remote publication
  are not verified and were not performed.
- History compensation searches at most 16 snapshots inside the retained 30-snapshot source
  history, assumes a good-to-bad transition, and may be inconclusive on older/non-monotonic
  failures or dependency/configuration changes. It never claims an exhaustive historical audit.
- Generated/model/revert repairs remain patch artifacts; no original or remote branch is changed.


## Target-aware Demo Lab stages

Stage 1 (`52a810e`): target-derived scenario metadata; copy-only, deterministic source mutation;
passing clean baseline and same-identity failing copied baseline required before normal repair;
per-target persisted history; explicit JSON/Markdown injection disclosure. Required checks:
87 passed / 7 skipped backend; build passed / 13 frontend tests passed. All 10 new backend tests
also passed with Docker enabled, including a real copied-baseline failure proof.

Stage 2: combined service/repository target selector, real capability facts, editable requirements,
dependency opt-in, disabled reasons, target-scoped history and receipt export, incident disclosure,
and a healthy standalone reservation fixture. Required checks: 87 passed / 7 skipped backend;
build passed / 18 frontend tests passed. Full RUN_DOCKER_TESTS=1 backend suite: 94 passed.
The existing Vite lazy scene chunk-size advisory remains.

Isolated live API QA selected three target types, proved two clean test cases then a failing
mutated baseline in Docker, retained the untouched original and linked the incident/receipt.
With no NIM key in QA it correctly escalated without asserting success. No new live NIM repair
or service fault injection was performed. Local browser access was disabled in Work settings,
so this pass could not visually verify Demo Lab. Temporary QA services were stopped afterward.
No remote repositories, credentials or deployment settings were changed.

Mutation coverage is deliberately bounded: first eligible Python comparison or standalone JS/TS
boolean return, one candidate only. Unsupported syntax is disabled; an ineffective mutation or
an originally failing suite records a setup failure instead of inventing a regression. Detected
file counts are labeled as files; actual executed test cases appear only in sandbox evidence.

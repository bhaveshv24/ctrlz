# Evaluation-driven redesign — validation record

30 October 2026. This records observed checks, not predicted judging scores.

## Implemented changes

- New responsive control center with explicit empty/error/loading/unknown states, project
  signals, measured outcomes, incident filtering, code continuity and an evidence library.
- Persisted health/workflow probe history, capped at 120 observations per project. Service
  availability is displayed separately from business-workflow consistency and monitoring gaps.
- Incident workspace separates the investigation snapshot, alternatives, deterministic
  decisions, executed operations, independent verification, remaining risks and patch artifact.
- Exact-candidate approval review plus decline support. A declined recovery stays unresolved.
- JSON receipt snapshot checksums and a readable Markdown export. Checksums are explicitly
  not described as signatures or an immutable ledger.
- Authenticated, project-opt-in Demo Lab with idempotent setup requests and persisted run
  history. Setup injects actual CampusPass faults; the monitor creates the incident separately.
- Accessible modal portals make the background inert, trap focus, support Escape and restore
  focus. Incident tabs support arrow/Home/End navigation. Mobile closed navigation is removed
  from keyboard/accessibility navigation. Reduced motion and visible focus styles are included.
- CampusPass separates payment, worker issuance and entitlement status; exports actual order
  receipts; announces verification; and has an accessible checkout modal and outage banner.
- Deployment templates, Caddy configuration and a dated submission checklist are prepared.
  No public hosting or submission has been performed.

## Automated results

- CtrlZ: **31 Python tests passed**, including actual isolated Docker tests and Compose replay.
  New checks cover unknown business-health state, bounded probe retention, measured recovery
  timing, receipt integrity, demo authorization/opt-in/idempotency, autonomous detection, and
  exact-plan decline without executing a mutation. Sandbox tests also run with a restrictive
  service umask to verify the deployed nonroot test container can read its isolated worktree.
- CampusPass: **9 Python tests passed**.
- CtrlZ frontend: **6 tests passed**; TypeScript checks include unused-code checks; production build.
- CampusPass frontend: production TypeScript/build check passed.
- Caddy: the supplied two-domain configuration passed `caddy validate` locally. The test
  did not provision public DNS, obtain a public certificate, or exercise Linux service units.

## Observed browser checks

- Operator login loaded actual API data and live SSE updates.
- Updated CampusPass checkout was exercised in the browser: payment recorded → ticket pending →
  issuance complete → valid entitlement. Only the verified ticket displayed its verification result.
  The checkout modal exposed only its dialog in the accessibility tree and focused its email field.
- Project dialog: background excluded from accessibility tree, Tab entered modal,
  Shift+Tab wrapped to its last control, Escape closed it and restored the invoking control.
- Incident tabs: ArrowRight moved focus/selection from Story to Strategies.
- 390px mobile layout: document width equals viewport width (390px), with usable open/close
  navigation. The desktop layout was inspected at 1280px; temporary viewport override reset.
- Demo C was started through the new UI. Incident `3edaa856-15e7-4ff6-b539-5e49cdb9fb86`
  was detected autonomously, compared four real model proposals, blocked the unsafe/inapplicable
  alternatives, executed restore_checkout and independently verified recovery in **23 seconds**.
- Demo B was started through the new UI. Incident `0e639183-602f-4e43-afe8-8d5893f23a99`
  detected a missing ticket while the website stayed healthy, paused for approval, and completed
  after the browser operator explicitly authorized C1. All five independent order/entitlement/job
  checks passed, including exactly one valid ticket. Its recorded elapsed time includes the
  entire approval wait; that delay was not hidden or replaced by an invented faster metric.

The UI checks used a separate local operator-test workspace with the real NVIDIA NIM model.
The normal monitor was paused to avoid two coordinators acting on the same target and was
restored afterward. The normal local CampusPass project is opted into the new rehearsal
controls. Future deployments still default to controls disabled.

## Remaining release work

Follow SUBMISSION_CHECKLIST.md for remote repositories, final documentation, demo recording,
pitch deck and a real public URL. Host/domain selection, public TLS, rootless Docker under
the actual service account, external webhook delivery and hosted CI remain to be verified.
This is focused accessibility testing, not a claim of full WCAG certification.

# Judge walkthrough: one silent failure among 1,000 operations

This is an isolated local document-processing fixture. It uses actual HTTP
requests, a background queue, SQLite records, generated instrumentation, source
authentication and the configured NVIDIA model. It is not a concurrent-user load
test and does not use custom CtrlZ application endpoints.

## Start

From CtrlZ root, with its existing environment and dependencies:

```bash
DOCKER_HOST=unix:///run/user/1000/docker.sock backend/.venv/bin/python scripts/workflow_demo.py serve
```

In another terminal:

```bash
backend/.venv/bin/python scripts/workflow_demo.py audit
backend/.venv/bin/python scripts/workflow_demo.py status
```

Open `http://localhost:18052/#projects`. The existing dashboard on 5173 remains
separate. Sign in with the existing private local admin credentials.

## Review the proposed workflow

1. On the document-processing project, open **AI Workflow Audit · optional**.
2. Show the actual source-backed workflow and uncertainty. The source is an
   explicitly supplied content-pinned fixture ZIP, not a claimed GitHub deployment.
3. Explain: “A request creates durable pending work. Completion occurs later in
   a worker. A successful HTTP response does not prove the work completed.”
4. Review the completion rule, source locations, deadline, selected technique and
   collected fields. For the controlled demo, a five-second deadline is suitable.
   Generic zero-code instrumentation is a recommendation, not an implemented
   business-completion adapter. Select the reviewed instrumentation strategy if
   lifecycle/user correlation signals are required.
5. Approve only the rule you intend to monitor. User IDs are optional and
   pseudonymous; a job ID is never treated as user identity.

## Generate and review the patch

Choose **Generate and verify instrumentation**. Leave dependency download approval
unchecked for this stdlib fixture. Inspect the actual verification report and diff:
the original business statements and tests remain unchanged; the diff adds
observation decorators and a standalone bounded probe.

Explain: “The AI proposes observations. A constrained compiler generates the patch.
Approval is bound to the source and rule. The patch is tested offline and returned
for review; it has not been pushed or deployed by downloading it.”

## Run the isolated experiment

```bash
DOCKER_HOST=unix:///run/user/1000/docker.sock backend/.venv/bin/python scripts/workflow_demo.py run
```

This explicitly authorized local demo installs the reviewed artifact in its own
network-isolated container. It submits 1,000 distinct requests sequentially. All
return 202, 999 jobs complete, and the disclosed `resource-0001` branch remains
pending without throwing an exception. Rate-limit backpressure can pause event
delivery; do not disable the limit to speed up the presentation.

Connect the independent deadline checker in another terminal:

```bash
backend/.venv/bin/python scripts/workflow_demo.py watch
```

Show the workflow counts in the audit panel, then open its runtime incident.
Explain: “Missing logs can be lost telemetry. Here a separate read-only collector
confirmed the same durable job was still incomplete after the approved deadline.”

Show the affected resource, actual job ID, source revision and pseudonymous user
only when supplied. No request/trace identity is invented. Show the real AI
diagnosis and pending recommendations. No global restart or targeted retry is
authorized by this monitoring approval, and no repair is claimed.

## Receipt and safe stop

```bash
backend/.venv/bin/python scripts/workflow_demo.py export
DOCKER_HOST=unix:///run/user/1000/docker.sock backend/.venv/bin/python scripts/workflow_demo.py stop-fixture
```

Exports are below `backend/data/workflow-demo/`. Stop `watch` and `serve` with
Ctrl+C. History and source artifacts remain. For a fresh rehearsal, preserve the
old directory and use a new `CTRLZ_WORKFLOW_DEMO_DIR` under `backend/data` in each
terminal. See [the complete guide](AI_WORKFLOW_OBSERVABILITY.md).

The new `watch` connects to CtrlZ and reads only dispatched overdue operation IDs.
It does not poll or scan the application database. Run it after lifecycle evidence
is delivered for a deterministic replay-style demonstration; a production forwarder
should stream events promptly, otherwise delivery lag may cause additional checks.

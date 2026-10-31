# Narrow Docker worker restart (Scenario C)

Run this supervisor on a trusted host with a rootless Docker daemon, separately from an
application worker. It exposes no shell tool and accepts no container name from a request.
It inspects container status, deployment image, restart count and bounded logs, then restarts
only the fixed stopped container after revision checks and CtrlZ operator approval.
Persisted request intents prevent a crash from silently causing a second restart.
A running but slow worker escalates: this example does not guess that restarting is safe.

Set `SUPERVISOR_RECOVERY_TOKEN` on both CtrlZ and the supervisor; set
`CTRLZ_WORKER_CONTAINER` to the exact worker container name. Start using the CtrlZ backend
Python environment, from this directory:

```sh
../../backend/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 18003
```

Connect `project.json` using Generic HTTP service. Stop only your disposable demonstration
worker to inject the failure. CtrlZ detects `ready=false`; inspect the real diagnostic tool
evidence, review the tournament and approve the fixed restart. Its generic verifier checks
three new health responses plus `worker.running=true`. Add service-specific business
assertions when configuring a real application: container liveness alone does not establish
checkout correctness. Never expose this supervisor directly to the public internet or give
it a privileged host Docker socket. This integration is independent of CampusPass.

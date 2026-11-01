# Local and hosted execution compatibility

The Vercel frontend calls the Render API. The Render container includes Git and Python,
but no reachable Docker daemon or sandbox images. Supabase stores database state; it
does not execute repository tests. Static source inspection and dependency advisories
can work while test execution, repair and completion cannot.

## Current compatibility

- Public site on Render: static repository inspection, advisory lookup, account and
  configured monitoring APIs. Capability checks now report actual Docker availability.
- Local launcher with Docker: sandbox tests, source repair and project completion.
- Tests that did not run are not displayed as `0 passed / 0 failed` or downloadable errors.

## Full hosted execution

For the existing implementation, deploy the API to a Docker-capable Linux host using
`docs/DEPLOYMENT.md` and the supplied service templates. Build both sandbox images using
`scripts/build_sandboxes.py`. Use persistent storage for imports and generated artifacts.
Keep provider secrets in the backend, and retain network-disabled test containers.
Update Vercel's VITE_API_URL to the HTTPS origin of that API and allow the exact frontend
origin in CTRLZ_CORS_ORIGINS. Rebuild the frontend after changing its environment.
Verify `/capabilities` while signed in, then inspect and repair a controlled fixture.

Setting CTRLZ_CODE_EXECUTION_ENABLED=true on Render does not provide Docker.
Installing a Docker CLI alone does not provide a daemon. Never execute uploaded code
directly inside the API process as a fallback.

A separate hosted sandbox or authenticated runner service is another architecture, but
it is not integrated here. It needs file transfer, sandbox lifecycle, dependency setup,
offline tests and artifact verification before claiming compatibility. No hosting
resources or paid services were provisioned by this change.

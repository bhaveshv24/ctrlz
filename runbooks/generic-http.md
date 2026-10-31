# Generic HTTP service recovery
Use only the operation semantics registered by this service's integration contract.
Read authenticated diagnostics; compare revision and declared preconditions. An HTTP 200
health response can still fail a configured readiness assertion. High-risk mutations need
approval for the exact plan and contract. Never invent a shell, container restart, or database
operation. If no allowed operation addresses the fault, escalate for repository repair.
For a paused dispatch queue, a registered resume operation may restore dispatching while
retaining jobs. The service must enforce idempotency keys and expected_revision atomically.
After mutation, verify configured readiness and diagnostic postconditions; do not treat a
successful mutation response as successful recovery.

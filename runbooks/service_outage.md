# Checkout unavailable or slow
Inspect health, latency and authenticated diagnostics before a mutation. A checkout circuit
fault can be mitigated with restore_checkout only if fresh diagnostics confirms the fault.
Deleting a database, disabling authentication, and arbitrary container restart are forbidden.
Verify three successful health probes, checkout_available=true and contract latency bound.
This controlled circuit restoration is a mitigation; investigate the initiating cause separately.

# Paid order without entitlement
Read workflows, then worker logs and actual order/payment/ticket records. A paused worker
can be resumed only with approval under the default contract. A ready worker can retry the
specific order through the idempotent retry_order operation. Never force-create a ticket:
that strategy risks duplicate entitlements. Verify payment=paid, exactly one valid ticket
and job=done. A worker_defect is a code issue: escalate to an explicitly imported repository
and run immutable regression tests in the code sandbox. Restart cannot fix a genuine defect.

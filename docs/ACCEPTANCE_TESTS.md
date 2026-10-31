# Acceptance criteria

- Repositories have separate Git roots; parent has no .git.
- Checkout persists order/payment/job. Repeated client request returns same order.
- Worker generates a unique valid ticket. Concurrent retries cannot duplicate entitlement.
- Fault endpoints require demo mode and token. Public endpoints expose no administrative data.
- Monitor detects HTTP failure/latency and missing workflow entitlement without operator prompt.
- Diagnostic tools return actual remote evidence and persist results.
- CrewAI selects read tools and proposes structured alternatives with NVIDIA NIM.
- Deterministic gate blocks unknown/destructive/duplicate-prone actions, even after approval.
- Evaluation logs concrete acceptance/precondition results and never invented numeric scores.
- Revision mismatch is rejected; uncertain operation retries use the same idempotency key.
- High-risk operation pauses; approval binds exact plan. Restart preserves evidence/approvals.
- Successful recovery requires fresh independent health or workflow assertions.
- One incident per active project/resource; unresolved incidents do not multiply every poll.
- Receipts contain evidence, alternatives, safety, actions, checks, remaining risks.
- SSE resumes from recorded event ID, including after backend restart.
- Continuation rejects path traversal/symlinks/test changes; uses worktree and Docker sandbox;
  baseline fails and immutable candidate tests pass before verified patch artifact is produced.
- Replay starts a separate disposable Compose project with separate storage and no production
  credentials, observes injected fault and independently verifies the proposed operation.
- Frontends build/typecheck and read actual APIs; unavailable services produce honest errors.
- CI runs Python tests on macOS/Windows and frontend build/tests on Linux.
- Live judging separately requires NIM credentials, Docker daemon, and notification webhook.

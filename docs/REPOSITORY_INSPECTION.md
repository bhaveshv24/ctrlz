# Repository inspection

The repair tab's **Inspect repository** action imports an inert managed snapshot,
then calls authenticated `POST /repositories/audit` for the consolidated report.
The old `/repositories/diagnose` remains available for baseline-only clients.

The report is tied to the snapshot commit and includes:

- Python syntax and targeted AST security checks: dynamic code evaluation, shell
  execution, unsafe deserialization/YAML, constructed SQL and disabled TLS checks.
- JavaScript/TypeScript patterns for dynamic code, HTML assignment and disabled TLS.
- Potential embedded credentials, with location only; values are never echoed.
- Known dependency advisory IDs from OSV for resolved npm package-lock entries,
  uv.lock packages and exactly pinned Python requirements. Nested package directories
  are included; generated dependency folders are excluded. Only package names,
  versions and ecosystems leave the server. No repository content is sent to OSV.
- Repository readiness and a real isolated baseline test run when the selected
  profile and Docker runner are available. Test execution stays offline; existing
  isolated dependency setup rules still apply.

The UI shows findings, test state, coverage gaps and a downloadable JSON report.
When Docker is disabled or unavailable, static/advisory results still return with
an explicit not-run/unavailable test state. Unsupported profiles, provider failures,
missing lockfiles and unresolved version ranges cannot produce an all-clear result.

Static checks are heuristics, not a comprehensive security assessment. They do not
perform full taint analysis, authentication review, penetration testing or deployed
uptime probes. Files above 256 KiB are skipped and source findings are capped at 100.
Dependency directories are capped at 50; resolved packages at 200; displayed advisory
findings at 100. Truncation and advisory pagination are shown as coverage gaps.

Inspection never changes user source. Existing tests passing do not override source
or dependency findings. Repairs still require a reproduced failing baseline;
completion is an explicit separate action. Existing acceptance tests cannot by
themselves prove that a new security requirement or feature is implemented correctly.
No code is automatically deployed.

Advisory API contract: https://google.github.io/osv.dev/post-v1-querybatch/
Reusable implementation skill: `skills/ctrlz-repository-inspection/SKILL.md`.

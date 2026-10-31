from .models import Candidate, Project




def evaluate(candidate: Candidate, project: Project, diagnostics, adapter, resource, approved=False):
    checks = []
    if not candidate.actions or len(candidate.actions) > project.contract.max_actions:
        return {"candidate_id": candidate.id, "eligible": False, "approval_required": False, "checks": [{"passed": False, "reason": "Action count outside contract"}]}
    needs_approval = False
    seen = set()
    # Multi-action plans need evidence between mutations; evaluate only first action now.
    for action in candidate.actions:
        allowed = action.operation in adapter.operations and action.operation in project.contract.allowed
        params = allowed and adapter.validate_action(action)
        unique = action.operation not in seen
        seen.add(action.operation)
        checks.append({"operation": action.operation, "passed": allowed and params and unique, "reason": "Allowlist, typed parameters and no repeated operation"})
        needs_approval |= action.operation in project.contract.approval_required or (allowed and adapter.needs_approval(action.operation))
    pre, reason = adapter.precondition(candidate.actions[0].operation, diagnostics, adapter.action_parameters(candidate.actions[0]), resource)
    checks.append({"passed": pre, "reason": reason})
    return {"candidate_id": candidate.id, "eligible": all(c["passed"] for c in checks), "approval_required": needs_approval and not approved, "checks": checks}


def tournament(candidates, project, diagnostics, adapter, resource):
    results = [evaluate(c, project, diagnostics, adapter, resource) for c in candidates]
    eligible = [(c, r) for c, r in zip(candidates, results) if r["eligible"]]
    # Objective lexicographic order: no approval then fewer mutations. No LLM scores.
    eligible.sort(key=lambda cr: (cr[1]["approval_required"], len(cr[0].actions), cr[0].id))
    return results, eligible[0][0] if eligible else None

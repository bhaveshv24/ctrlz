from datetime import datetime, timezone


def receipt_markdown(receipt):
    incident = receipt["incident"]
    date = datetime.fromtimestamp(incident["created"], timezone.utc).isoformat()
    verification = incident.get("verification", {})
    lines = ["# CtrlZ — Recovery receipt", "", f"Incident: {incident['id']}", f"Project: {incident['project_id']}", f"Detected (UTC): {date}", f"Status: {incident['status']}", f"Independently verified: {receipt['success']}", f"Reasoning: {receipt['reasoning_provider']}", f"Model: {receipt.get('model') or 'Not recorded'}", "", "## Diagnosis", "", incident.get("diagnosis") or "See recorded source evidence.", "", "## Strategies evaluated", ""]
    if incident.get("requirement_assessment"):
        lines += ["", "## Requirements reconstructed from repository evidence", "", "Agent assessment only; independent tests establish verification."]
        for finding in incident['requirement_assessment']:
            lines.append(f"- {finding['status']}: {finding['requirement']} — {finding['explanation']} (files: {', '.join(finding['evidence_paths']) or 'unknown'})")
        lines += ["", "## Continuation plan", ""] + [f"- {step}" for step in incident.get('continuation_plan', [])]
    if incident.get("injected_regression"):
        disclosure = incident["injected_regression"]
        lines += ["", "## Disclosed injected regression", "", "This is an intentionally injected demo regression in a separate managed copy; the original snapshot was not modified.", "Proven failing baseline: "+str(disclosure.get("proven", False)), "Mutation: "+str(disclosure.get("file", "Not applied"))+" · "+str(disclosure.get("kind", "Unavailable")), ""]
    for result in incident.get("tournament", []):
        lines.append(f"- {result['candidate_id']}: {'eligible' if result['eligible'] else 'blocked'}; approval required: {result['approval_required']}")
        lines.extend(f"  - {'PASS' if check['passed'] else 'FAIL'}: {check['reason']}" for check in result["checks"])
    if incident.get('code_tournament'):
        lines += ['', '## Code recovery tournament', '', 'Selection: passing original immutable acceptance, smallest changed-line count, fewest strategy sandbox runs.', '', 'Selected: '+str(incident.get('selected_code_strategy'))]
        for strategy in incident['code_tournament']:
            lines.append(f"- {strategy['id']}: eligible={strategy['eligible']}; changed lines={strategy['diff_lines']}; sandbox runs={strategy['sandbox_runs']}; {strategy['reason']}")
        if incident.get('suspect_commit'):
            suspect=incident['suspect_commit']
            lines.append('Suspect source commit: '+str(suspect.get('upstream_commit') or suspect['snapshot_commit']))
    if incident.get('kind') == 'runtime':
        import json
        if incident.get('workflow_evidence'):
            lines += ['', '## Approved workflow and affected operation', '', '```json', json.dumps(incident['workflow_evidence'],indent=2), '```']
        lines += ['', '## Runtime evidence and source revision', '', 'Read-only investigation. Recommendations are not executed recovery.', '', '```json', json.dumps({'affected':incident.get('runtime_summary'), 'source':incident.get('source_evidence'), 'events':incident.get('runtime_samples')},indent=2), '```', '', '## Recovery recommendations awaiting human review', '']
        for recommendation in incident.get('runtime_recommendations', []):
            lines += [f"- {recommendation['id']} ({recommendation['category']}): {recommendation['summary']}", '  Rationale: '+recommendation['rationale'], '  Evidence: '+', '.join(recommendation['evidence_ids'])]
        lines += ['', 'Review: '+json.dumps(incident.get('recommendation_review')), 'Execution permitted: false. No production recovery or test reproduction is claimed.']
    lines += ["", "## Independent acceptance checks", ""]
    lines.extend(f"- {'PASS' if value else 'FAIL'}: {key}" for key, value in verification.get("checks", {}).items())
    if not verification:
        lines.append("No independent verification recorded. Recovery is not proven.")
    lines += ["", "## Recorded execution", ""]
    for event in receipt["events"]:
        if event["stage"] in {"operation_intent", "operation_result", "authorized", "candidate_tests", "replay_result", "notification"}:
            lines.append(f"- Event {event['id']}: {event['stage']}; inspect the JSON receipt for exact evidence.")
    lines += ["", "## Remaining risks", ""]
    lines.extend("- " + risk for risk in incident.get("remaining_risks", ["Unresolved investigations retain their uncertainties."]))
    lines += ["", "## Evidence snapshot", "", f"JSON SHA-256: {receipt['integrity']['snapshot_digest']}", "This identifies the accompanying JSON snapshot; it is not a digital signature.", ""]
    return "\n".join(lines)

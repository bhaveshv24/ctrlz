"""Observed operational outcomes. No estimated savings, synthetic scores or confidence."""
import statistics
import time


def overview(store, runtime_monitor=None):
    incidents = store.incidents()
    durations, rejected, tools = [], 0, 0
    verified = [i for i in incidents if i["status"] == "resolved" and i.get("verification", {}).get("passed") is True]
    for incident in incidents:
        events = store.events(incident_id=incident["id"])
        rejected += sum(sum(not r["eligible"] for r in e["payload"].get("results", [])) for e in events if e["stage"] == "tournament")
        tools += sum(e["stage"] == "tool_result" for e in events)
        if incident in verified:
            finishes = [e["timestamp"] for e in events if e["stage"] == "verification" and e["payload"].get("passed") is True]
            if finishes:
                durations.append(max(0, min(finishes) - incident["created"]))
    projects = []
    for project in store.projects():
        if project.get("project_type") == "repository-deployment":
            coverage = runtime_monitor.coverage(project) if runtime_monitor else []
            states = [d["state"] for d in coverage]
            state = "paused" if not project.get("enabled", True) else "error_detected" if "error_detected" in states else "observing" if states and all(s == "observing" for s in states) else "no_recent_events" if states else "incomplete_configuration"
            projects.append({"project":project,"state":state,"latest":None,"history":[],"runtime_coverage":coverage})
            continue
        probes = store.probes(project["id"])
        latest = probes[-1] if probes else None
        state = "unknown"
        if not project.get("enabled", True):
            state = "paused"
        elif latest:
            health, workflows = latest["health"], latest["workflows"]
            if time.time() - latest["timestamp"] > 30:
                state = "stale"
            elif not health.get("accepted", health["ok"]) or health.get("latency_ms", 0) > project.get("latency_ms", 1500):
                state = "disrupted"
            elif not workflows["ok"]:
                state = "partial"
            elif workflows["body"].get("discrepancies"):
                state = "attention"
            else:
                state = "healthy"
        projects.append({"project": project, "state": state, "latest": latest, "history": [{"timestamp": p["timestamp"], "latency_ms": p["health"].get("latency_ms"), "ok": p["health"]["ok"]} for p in probes[-40:]]})
    return {"generated_at": time.time(), "summary": {"verified_recoveries": len(verified), "open_incidents": sum(i["status"] != "resolved" for i in incidents), "approvals_waiting": sum(i["status"] == "awaiting_approval" for i in incidents), "rejected_evaluations": rejected, "tool_executions": tools, "verified_workflows": sum(i["kind"] == "workflow" for i in verified), "median_recovery_seconds": round(statistics.median(durations), 2) if durations else None, "measured_recoveries": len(durations)}, "projects": projects}

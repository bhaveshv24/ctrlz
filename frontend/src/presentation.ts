import type { FlightEvent, Incident, Receipt } from "./api";
export const words = (value: string) => value.replaceAll("_", " ");
export const title = (i: Incident) =>
  i.kind === "outage"
    ? "Service interrupted"
    : i.kind === "workflow"
      ? "Workflow needs recovery"
      : "Repository repair";
export const tone = (s: string) =>
  ["resolved", "healthy", "passed", "verified"].includes(s)
    ? "green"
    : ["awaiting_approval", "attention", "partial", "stale"].includes(s)
      ? "amber"
      : ["blocked", "escalated", "disrupted", "failed"].includes(s)
        ? "red"
        : "slate";
export const duration = (seconds: number | null | undefined) => {
  if (seconds == null) return "—";
  if (seconds < 60) return Math.round(seconds) + "s";
  if (seconds < 3600)
    return Math.floor(seconds / 60) + "m " + Math.round(seconds % 60) + "s";
  return (seconds / 3600).toFixed(1) + "h";
};
export const clock = (seconds: number) =>
  new Date(seconds * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
export const stamp = (seconds: number) =>
  new Date(seconds * 1000).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
export function measuredDuration(receipt: Receipt) {
  const end = receipt.events.find(
    (e) => e.stage === "verification" && e.payload.passed === true,
  );
  return end ? Math.max(0, end.timestamp - receipt.incident.created) : null;
}
export function eventSummary(event: FlightEvent): string {
  const p = event.payload;
  if (event.stage === "tool_result") {
    const r = p.result;
    if (p.tool === "read_repository_file")
      return `Read ${p.path} · line ${p.start_line}`;
    if (p.tool === "search_repository") return `Searched snapshot: ${p.query}`;
    if (p.tool === "runbook_search")
      return `${r?.length || 0} runbooks retrieved`;
    return `${p.tool || "Tool"} · ${r?.status ? "HTTP " + r.status : r?.ok ? "Returned evidence" : "Request failed"}${r?.latency_ms != null ? " · " + r.latency_ms + "ms" : ""}`;
  }
  if (event.stage === "tournament")
    return `${p.results?.length || 0} strategies evaluated against the contract`;
  if (event.stage === "safety_gate")
    return `${p.eligible ? "Eligible" : "Blocked"} · ${p.candidate_id || "candidate"}${p.approval_required ? " · approval required" : ""}`;
  if (event.stage === "operation_result")
    return `${p.action?.operation || "Operation"} · result recorded`;
  if (event.stage === "verification") {
    const checks = Object.values(p.checks || {});
    return `${checks.filter(Boolean).length}/${checks.length} checks passed · ${p.passed ? "verified" : "unresolved"}`;
  }
  if (event.stage === "candidate_tests")
    return `Attempt ${p.attempt || 1} · ${p.passed ? "tests passed" : "candidate rejected"}`;
  if (event.stage === "notification")
    return p.delivered
      ? "Summary delivered"
      : p.reason || "Delivery not confirmed";
  if (event.stage === "plan_revision")
    return "Planner revising from deterministic rejection feedback";
  if (event.stage === "replay_result")
    return p.verification?.passed
      ? "Isolated replay passed"
      : "Replay acceptance failed";
  return words(event.stage);
}
export const lifecycle = (receipt: Receipt) => {
  const stages =
    receipt.incident.kind === "code"
      ? [
          ["Detect", ["detect"]],
          ["Reproduce", ["baseline_tests"]],
          ["Continue", ["code_proposal"]],
          ["Verify", ["verification"]],
          ["Record", ["verification"]],
        ]
      : [
          ["Detect", ["detect"]],
          ["Diagnose", ["diagnose", "diagnosis"]],
          ["Plan", ["plan"]],
          ["Evaluate", ["tournament"]],
          ["Authorize", ["authorized", "safety_gate"]],
          ["Execute", ["operation_result"]],
          ["Verify", ["verification"]],
          ["Record", ["record"]],
        ];
  return stages.map(([name, events]) => ({
    name: name as string,
    recorded: receipt.events.some((e) =>
      (events as string[]).includes(e.stage),
    ),
  }));
};

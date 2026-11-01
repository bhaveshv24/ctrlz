export type Act = (
  fn: () => Promise<unknown>,
  message?: string,
) => Promise<boolean>;
export const API = (import.meta.env.VITE_API_URL || "/api").replace(/\/+$/, "");
export type Action = {
  operation: string;
  order_id?: string | null;
  parameters?: Record<string, string | number | boolean>;
};
export type Candidate = {
  id: string;
  rationale: string;
  actions: Action[];
  risks: string[];
};
export type Evaluation = {
  candidate_id: string;
  eligible: boolean;
  approval_required: boolean;
  checks: { passed: boolean; reason: string; operation?: string }[];
};
export type Verification = {
  passed: boolean;
  checks: Record<string, boolean>;
  evidence?: unknown;
};
export type Incident = {
  check_commands?: {setup:string;test:string;basis:string;directory?:string;server?:string;requests?:string;api_note?:string};
  id: string;
  project_id: string;
  kind: string;
  resource: string;
  status: string;
  created: number;
  updated: number;
  error?: string;
  injected_regression?: {
    disclosed: boolean;
    proven?: boolean;
    file?: string;
    kind?: string;
    original_repository: string;
  };
  diagnosis?: string;
  requirement_assessment?: {requirement: string; status: string; evidence_paths: string[]; explanation: string}[];
  continuation_plan?: string[];
  model?: string;
  approval_hash?: string;
  selected?: Candidate;
  plan?: { diagnosis: string; candidates: Candidate[] };
  tournament?: Evaluation[];
  verification?: Verification;
  remaining_risks?: string[];
  patch?: string;
  import_request?: {mode?: "repair" | "complete"; requirements?: string};
  commit?: string;
  runtime_summary?: { events: number; affected_users: number | null; last_received: number; identity_coverage: string };
  runtime_samples?: Record<string, any>[];
  workflow_evidence?: {proposal_id:string;approved_rule:Record<string,any>;instance_id:string;resource_id:string|null;user_id:string|null;identity:string;observation:string;revision:string;source_revision:string;source_provenance:string;last_evidence:unknown};
  source_evidence?: { state: string; commit_sha?: string; files?: {path: string; line: number | null; context: string; source: string; provenance: string; location_evidence?: string}[]; uncertainties?: string[] };
  runtime_assessment?: { diagnosis: string; uncertainties: string[] };
  runtime_recommendations?: RuntimeRecommendation[];
  recommendation_review?: {id: string; decision: string; executed: boolean};
  selected_code_strategy?: string;
  suspect_commit?: {
    snapshot_commit: string;
    upstream_commit?: string | null;
  } | null;
  code_tournament?: {
    id: string;
    eligible: boolean;
    sandbox_runs: number;
    diff_lines: number;
    reason: string;
  }[];
};
export type Project = {
  id: string;
  name: string;
  base_url: string | null;
  project_type?: "http" | "repository-deployment";
  repository_monitoring?: { github_url: string; preferred_ref?: string | null; deployments: RuntimeDeployment[] } | null;
  enabled: boolean;
  demo_enabled: boolean;
  adapter?: string;
  integration?: Record<string, unknown>;
  token_env?: string;
  timeout_seconds?: number;
  latency_ms?: number;
  contract: {
    allowed: string[];
    approval_required: string[];
    max_actions?: number;
    invariants?: string[];
  };
};
export type FlightEvent = {
  id: number;
  incident_id: string;
  timestamp: number;
  stage: string;
  payload: Record<string, any>;
};
export type Receipt = {
  check_commands?: {setup:string;test:string;basis:string;directory?:string;server?:string;requests?:string;api_note?:string};
  schema_version: number;
  replay_supported?: boolean;
  incident: Incident;
  events: FlightEvent[];
  success: boolean;
  reasoning_provider: string;
  model?: string;
  integrity: { algorithm: string; snapshot_digest: string; scope: string };
};
export type ProbeResult = {
  ok: boolean;
  accepted?: boolean;
  configured?: boolean;
  status?: number;
  latency_ms: number;
  body: Record<string, any>;
  error?: string;
};
export type ProjectSignal = {
  project: Project;
  state: string;
  runtime_coverage?: RuntimeCoverage[];
  latest: null | {
    timestamp: number;
    health: ProbeResult;
    workflows: ProbeResult;
  };
  history: { timestamp: number; latency_ms: number; ok: boolean }[];
};
export type Overview = {
  generated_at: number;
  summary: {
    verified_recoveries: number;
    open_incidents: number;
    approvals_waiting: number;
    rejected_evaluations: number;
    tool_executions: number;
    verified_workflows: number;
    median_recovery_seconds: number | null;
    measured_recoveries: number;
  };
  projects: ProjectSignal[];
};
export type DemoRun = {
  id: string;
  project_id: string;
  scenario: string;
  created: number;
  status: string;
  message?: string;
  order_id?: string;
  incident_id?: string;
  incident_status?: string;
};
export type Runtime = {
  nim_configured: boolean;
  provider: string;
  model?: string;
  demo_controls_enabled: boolean;
};
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  token: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(API + path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: signal ?? AbortSignal.timeout(90000),
  });
  } catch (error) {
    if (signal?.aborted) throw error;
    const timedOut = error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError");
    throw new Error(timedOut
      ? "The server took too long to respond. Please retry in a moment."
      : "Couldn’t reach the server. Check your connection and try again.");
  }
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new ApiError(
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail.map((item: {msg?: string}) => item.msg || "Invalid input").join("; ")
          : `Request failed (${response.status}). Please try again.`,
      response.status,
    );
  }
  try { return await response.json(); }
  catch { throw new Error("The server returned an unexpected response. Please try again."); }
}
export function saveFile(
  name: string,
  content: string,
  type = "application/json",
) {
  saveBlob(name, new Blob([content], { type }));
}
export function saveBlob(name: string, content: Blob) {
  const url = URL.createObjectURL(content);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export async function downloadRepairedZip(id: string, token: string) {
  const response = await fetch(API + "/incidents/" + encodeURIComponent(id) + "/repaired.zip", {
    headers: { Authorization: "Bearer " + token },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.detail || `Repaired ZIP download failed (${response.status}). Try again.`);
  }
  const blob = await response.blob();
  const signature = new Uint8Array(await blob.slice(0, 4).arrayBuffer());
  if (signature[0] !== 0x50 || signature[1] !== 0x4b || signature[2] !== 3 || signature[3] !== 4) {
    throw new Error("The server did not return a valid repository ZIP. Retry the download.");
  }
  saveBlob("ctrlz-" + id + "-repaired.zip", blob);
}
export async function downloadBrief(id: string, token: string) {
  const response = await fetch(API + "/incidents/" + id + "/brief", {
    headers: { Authorization: "Bearer " + token },
  });
  if (!response.ok) throw new Error("Could not download the recovery brief");
  saveFile("ctrlz-" + id + ".md", await response.text(), "text/markdown");
}
export function parseFrame(frame: string): FlightEvent | null {
  const data = frame
    .split("\n")
    .filter((l) => l.startsWith("data:"))
    .map((l) => l.slice(5).trim())
    .join("\n");
  return data ? JSON.parse(data) : null;
}
export async function stream(
  token: string,
  signal: AbortSignal,
  onEvent: (event: FlightEvent) => void,
  cursor: { current: number },
  onOpen?: () => void,
) {
  const response = await fetch(API + "/events?after=" + cursor.current, {
    headers: { Authorization: "Bearer " + token },
    signal,
  });
  if (!response.ok || !response.body)
    throw new Error("Live stream unavailable");
  onOpen?.();
  const reader = response.body.getReader(),
    decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let at;
      while (
        (at = buffer.indexOf("\n\n")) >= 0 ||
        (at = buffer.indexOf("\r\n\r\n")) >= 0
      ) {
        const cr = buffer.slice(at, at + 4) === "\r\n\r\n";
        const frame = buffer.slice(0, at).replaceAll("\r\n", "\n");
        buffer = buffer.slice(at + (cr ? 4 : 2));
        const event = parseFrame(frame);
        if (event && event.id > cursor.current) {
          cursor.current = event.id;
          onEvent(event);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export type RuntimeDeployment = {
  id: string;
  platform: "local" | "vps" | "docker" | "vercel" | "aws";
  service_id: string;
  environment: string;
  application_url?: string | null;
  deployment_ref?: string | null;
  commit_sha?: string | null;
  vercel_team_id?: string | null;
  source_paths?: string[];
  sources: { id: string; connector: "generic-events" | "vercel-drain" }[];
};
export type RuntimeCoverage = {
  deployment: RuntimeDeployment;
  state: string;
  credentials_configured: boolean;
  last_received: number | null;
  last_event_at: number | null;
  event_count: number;
  error_count: number;
  open_incidents?: number;
  measured_affected_users: number | null;
  execution_permitted: false;
};
export type RuntimeRecommendation = {
  id: string; category: string; summary: string; rationale: string;
  evidence_ids: string[]; risks: string[]; proposed_change?: string | null;
  verification_plan: string[]; review_hash: string; execution_permitted: false;
  review_policy?: { reviewable: boolean; reason: string };
};

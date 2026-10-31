import { api, type DemoRun, type Incident, type Overview, type Runtime } from "./api";

/** Only private workspace records determine whether the dashboard can open. */
export async function loadWorkspace(token: string) {
  const [overview, incidents] = await Promise.all([
    api<Overview>("/overview", token),
    api<Incident[]>("/incidents", token),
  ]);
  return { overview, incidents };
}

/** These panels can be unavailable without invalidating a successful sign-in. */
export async function loadWorkspaceMetadata(token: string) {
  const [runtime, runs] = await Promise.all([
    api<Runtime>("/health", token, undefined, AbortSignal.timeout(8000)).catch(() => null),
    api<DemoRun[]>("/demo/runs", token, undefined, AbortSignal.timeout(8000)).catch(() => []),
  ]);
  return { runtime, runs };
}

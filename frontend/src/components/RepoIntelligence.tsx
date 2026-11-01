import { useState } from "react";
import { api } from "../api";
type Evidence = {
  value: any;
  source: string;
  observed_at: number;
  coverage: "complete" | "sampled" | "unavailable";
  reason?: string;
};
type Scan = {
  state: string;
  repository: { full_name: string };
  observed_at: number;
  cached: boolean;
  values: Record<string, Evidence>;
  warnings: string[];
  retry_at: number | null;
  previous_snapshot?: { observed_at: number; values: Record<string, Evidence> };
};
export default function RepoIntelligence({
  token,
  repository,
  assessment,
  onPrefill,
}: {
  token: string;
  repository: string;
  assessment?: {
    supported: boolean;
    profile_label: string;
    tests: string[];
    dependency_install_required: boolean;
  } | null;
  onPrefill: (text: string) => void;
}) {
  const [scan, setScan] = useState<Scan | null>(null),
    [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [scanned, setScanned] = useState("");
  const current = scan && scanned === repository ? scan : null;
  const run = async (refresh = false) => {
    setLoading(true);
    setError("");
    try {
      const data = await api<Scan>(
        "/repositories/intelligence?repository=" +
          encodeURIComponent(repository) +
          "&refresh=" +
          refresh,
        token,
      );
      setScan(data);
      setScanned(repository);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };
  const display = (name: string, format?: (value: any) => string) => {
    const item = current?.values[name];
    if (!item || item.coverage === "unavailable") return "Unknown";
    if (item.value === null) return item.reason || "Not detected";
    return format ? format(item.value) : String(item.value);
  };
  const ci = current?.values.ci?.value;
  const languages = current?.values.languages;
  const total =
    languages?.value && typeof languages.value === "object"
      ? Object.values(languages.value).reduce<number>(
          (sum, v) => sum + (typeof v === "number" ? v : 0),
          0,
        )
      : 0;
  return (
    <section className="repo-intelligence" aria-label="Repair readiness">
      <div className="row-between">
        <h3>Repair readiness</h3>
        {repository && (
          <button
            type="button"
            className="button secondary"
            disabled={loading}
            onClick={() => run(Boolean(current))}
          >
            {loading
              ? "Reading GitHub…"
              : current
                ? "Refresh GitHub evidence"
                : "Scan GitHub evidence"}
          </button>
        )}
      </div>
      {!repository && (
        <p>
          Choose a GitHub source for remote evidence. ZIP uploads use
          the imported acceptance suite.
        </p>
      )}
      {loading && (
        <p role="status">
          Reading repository metadata, HEAD checks and available activity.
          Existing results remain visible.
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {assessment && (
        <dl className="readiness-facts">
          <div>
            <dt>Test profile</dt>
            <dd>
              {assessment.profile_label}: {" "}
              {assessment.supported ? "supported" : "needs preparation"}
            </dd>
          </div>
          <div>
            <dt>Acceptance files detected</dt>
            <dd>{assessment.tests.length}</dd>
          </div>
          <div>
            <dt>Dependency approval</dt>
            <dd>
              {assessment.dependency_install_required
                ? "Required before repair"
                : "Not required"}
            </dd>
          </div>
        </dl>
      )}
      {current && (
        <>
          <p role="status">
            <strong>{current.repository.full_name}</strong>: {" "}
            {current.state.replaceAll("_", " ")}
            {current.cached ? " (cached)" : ""}. Observed{" "}
            {new Date(current.observed_at * 1000).toLocaleString()}.
          </p>
          {current.state === "not_found_or_inaccessible" && (
            <p>
              Repository not found or private without access. GitHub does not
              distinguish these cases; configure a permitted server-side
              GITHUB_TOKEN if needed.
            </p>
          )}
          {current.state === "empty" && (
            <p>
              No commits yet. Repository metadata is available; there is no HEAD
              to test or repair.
            </p>
          )}
          {current.values.archived?.value === true && (
            <p>
              Archived repository. Inspection and local patch review remain
              available; no remote changes are made.
            </p>
          )}
          {current.values.fork?.value === true && (
            <p>
              Fork: commit and contributor history may be inherited from
              upstream.
            </p>
          )}
          {current.retry_at && (
            <p>
              GitHub rate limit reached. Loaded evidence is preserved. Retry
              after {new Date(current.retry_at * 1000).toLocaleString()}.
            </p>
          )}
          <dl className="readiness-facts">
            <div>
              <dt>CI on HEAD</dt>
              <dd>
                {ci?.status === "no_ci"
                  ? "No CI detected"
                  : ci?.status || "Unknown"}
              </dd>
            </div>
            <div>
              <dt>Last commit</dt>
              <dd>
                {display(
                  "last_commit",
                  (v) =>
                    (v.sha?.slice(0, 10) || "Unknown") + " " + (v.date || ""),
                )}
              </dd>
            </div>
            <div>
              <dt>Last push</dt>
              <dd>{display("last_activity")}</dd>
            </div>
            <div>
              <dt>Open issues / PRs</dt>
              <dd>
                {display("open_issues")} / {display("open_prs")}
              </dd>
            </div>
            <div>
              <dt>Contributors observed</dt>
              <dd>
                {display(
                  "contributors",
                  (v) =>
                    v.length +
                    " (" +
                    current.values.contributors.coverage +
                    ")",
                )}
              </dd>
            </div>
            <div>
              <dt>License / README</dt>
              <dd>
                {display("license", (v) => v.spdx_id || v.name)} /{" "}
                {display("readme", (v) =>
                  v.present ? "Detected" : "Not detected",
                )}
              </dd>
            </div>
          </dl>
          {total > 0 && (
            <div aria-label="Repository language bytes">
              {Object.entries(languages?.value || {})
                .filter(([, v]) => typeof v === "number")
                .map(([name, bytes]) => (
                  <div className="language-row" key={name}>
                    <span>{name}</span>
                    <meter min={0} max={total} value={bytes as number} />
                    <small>
                      {Math.round(((bytes as number) / total) * 100)}%
                    </small>
                  </div>
                ))}
            </div>
          )}
          {ci?.failing_checks?.length > 0 && (
            <button
              type="button"
              className="button secondary"
              onClick={() =>
                onPrefill(
                  `Repair failing CI on HEAD ${ci.head_sha}. Observed checks: ${ci.failing_checks.map((c: any) => c.name + " (" + c.status + ")" + (c.url ? " " + c.url : "")).join("; ")}. Reproduce the failure with the existing immutable acceptance suite and return a reviewed patch only.`,
                )
              }
            >
              Use failing HEAD checks in requirements
            </button>
          )}
          {current.previous_snapshot && (
            <p>
              Previous evidence retained from{" "}
              {new Date(
                current.previous_snapshot.observed_at * 1000,
              ).toLocaleString()}
              ; refresh did not establish a complete current snapshot.
            </p>
          )}
          <details>
            <summary>Sources and coverage</summary>
            {Object.entries(current.values).map(([name, v]) => (
              <p key={name}>
                <strong>{name.replaceAll("_", " ")}</strong>: {v.coverage}
                {v.reason ? ": " + v.reason : ""}
                <br />
                <small>
                  {v.source}: {new Date(v.observed_at * 1000).toLocaleString()}
                </small>
              </p>
            ))}
          </details>
        </>
      )}
    </section>
  );
}

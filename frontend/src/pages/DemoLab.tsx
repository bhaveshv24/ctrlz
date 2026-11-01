import { useState, useEffect, useCallback } from "react";
import {
  ShieldCheck,
  ArrowRight,
  ArrowUpRight,
  RotateCcw,
  Code2,
} from "lucide-react";
import {
  api,
  downloadBrief,
  type Act,
  type Project,
  type ProjectSignal,
  type DemoRun,
} from "../api";
import { stamp, words } from "../presentation";
import { navigate } from "../navigation";
import { Badge, Empty, Dialog } from "../components/ui";
import { DemoPlate } from "../components/DemoPlate";
import PageTitle from "../components/PageTitle";
import {
  scenarioReason,
  type DemoTarget,
  type DemoScenario,
} from "../demo-targets";

export default function DemoLab({
  projects,
  runs,
  enabled,
  token,
  busy,
  act,
  open,
  onEnable,
}: {
  projects: ProjectSignal[];
  runs: DemoRun[];
  enabled: boolean;
  token: string;
  busy: boolean;
  act: Act;
  open: (id: string) => void;
  onEnable: (p: Project) => void;
}) {
  const [targets, setTargets] = useState<DemoTarget[]>([]),
    [targetId, setTargetId] = useState(""),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [history, setHistory] = useState<DemoRun[]>([]),
    [historyTarget, setHistoryTarget] = useState(""),
    [historyError, setHistoryError] = useState(""),
    [scenario, setScenario] = useState<DemoScenario | null>(null),
    [presentation, setPresentation] = useState(false),
    [requirements, setRequirements] = useState(
      "Restore all original acceptance tests without editing tests or weakening behavior.",
    ),
    [approve, setApprove] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api<DemoTarget[]>("/demo/targets", token);
      setTargets(result);
      setTargetId((current) =>
        result.some((t) => t.id === current) ? current : result[0]?.id || "",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load targets");
    } finally {
      setLoading(false);
    }
  }, [token]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    setHistory([]);
    setHistoryError("");
  }, [targetId]);
  useEffect(() => {
    let active = true;
    if (!targetId) return;
    const refresh = async () => {
      try {
        const rows = await api<DemoRun[]>(
          "/demo/runs?target=" + encodeURIComponent(targetId),
          token,
        );
        if (active) {
          setHistory(rows);
          setHistoryTarget(targetId);
          setHistoryError("");
        }
      } catch (e) {
        if (active)
          setHistoryError(
            e instanceof Error ? e.message : "Could not load history",
          );
      }
    };
    void refresh();
    const interval = window.setInterval(() => void refresh(), 4000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [targetId, token, runs]);
  const target = targets.find((t) => t.id === targetId),
    project = projects.find((p) => p.project.id === targetId)?.project,
    close = useCallback(() => setScenario(null), []);
  const start = (choice: DemoScenario) => {
    if (choice.id === "monitor") {
      navigate("projects");
      return;
    }
    if (choice.id === "contract" && project) {
      onEnable(project);
      return;
    }
    setScenario(choice);
  };
  return (
    <div className={presentation ? "demo-lab presentation" : "demo-lab"}>
      <PageTitle
        eyebrow="LIVE REHEARSAL / REAL EVIDENCE"
        heading="Demo Lab"
        copy="Scenarios follow the selected repository or service. Every runnable action uses real checks; unsupported controls stay disabled."
        action={
          <button
            className="button secondary"
            aria-pressed={presentation}
            onClick={() => setPresentation(!presentation)}
          >
            {presentation ? "Exit focus view" : "Focus view"}
            <ArrowUpRight size={15} />
          </button>
        }
      />
      {target && (
        <DemoPlate
          target={target}
          scenario={scenario}
          runs={history}
          observed={historyTarget === target.id && !historyError}
        />
      )}
      <div className="demo-workspace">
        <label>
          Demonstration target
          <select
            value={targetId}
            onChange={(e) => {
              setTargetId(e.target.value);
              setApprove(false);
              setScenario(null);
            }}
            aria-label="Demonstration target"
          >
            {targets.map((t) => (
              <option key={t.id} value={t.id}>
                {t.kind === "repository" ? "Repository" : "Service"} / {t.name}
              </option>
            ))}
            {!targets.length && (
              <option value="">
                {loading ? "Loading targets…" : "No target connected"}
              </option>
            )}
          </select>
        </label>
        <button
          className="button secondary"
          disabled={loading || busy}
          onClick={() => void load()}
        >
          Refresh targets
        </button>
        <button className="inline-link" onClick={() => navigate("continuity")}>
          Import repository
          <ArrowRight size={14} />
        </button>
        <span className="demo-boundary">
          <ShieldCheck size={16} />
          Patch artifacts only for repositories.
        </span>
      </div>
      {error && (
        <div className="alert warning" role="alert">
          {error}
        </div>
      )}
      {loading && (
        <p role="status">
          Inspecting managed snapshots and configured services…
        </p>
      )}
      {!loading && !targets.length && !error && (
        <Empty title="Choose a real target first">
          Import a repository in Repository repair or connect a service in
          Projects.
        </Empty>
      )}
      {target && (
        <>
          <section
            className="card demo-target-facts"
            aria-label="Selected target facts"
          >
            <div className="section-title">
              <h2>{target.name}</h2>
              <Badge state="unknown">
                {target.kind === "repository"
                  ? "Managed snapshot"
                  : target.facts.adapter}
              </Badge>
            </div>
            {target.kind === "repository" ? (
              <>
                <p>
                  <strong>{target.facts.profile_label}</strong> ·{" "}
                  {target.facts.test_file_count} detected test files ·{" "}
                  {target.facts.source_count} editable source files
                </p>
                <p className="muted">
                  These are file counts, not executed test counts. Actual test
                  cases and pass/fail results appear after a sandbox run.
                </p>
                <details>
                  <summary>Tests and editable files</summary>
                  <p>
                    Tests: {target.facts.tests?.join(", ") || "None detected"}
                  </p>
                  <p>
                    Editable:{" "}
                    {target.facts.editable_files?.join(", ") || "None detected"}
                  </p>
                </details>
                <p className="muted">
                  Snapshot: <code>{target.id}</code>
                </p>
                <label>
                  Repair requirements
                  <textarea
                    aria-label="Demo repair requirements"
                    rows={3}
                    value={requirements}
                    onChange={(e) => setRequirements(e.target.value)}
                  />
                </label>
                {target.facts.dependency_install_required && (
                  <label className="check-row">
                    <input
                      type="checkbox"
                      checked={approve}
                      onChange={(e) => setApprove(e.target.checked)}
                    />
                    Approve isolated dependency installation. Tests remain
                    offline; no host execution.
                  </label>
                )}
              </>
            ) : (
              <>
                <p>
                  Service: <code>{target.facts.origin}</code>
                </p>
                <p>
                  Health:{" "}
                  <code>{target.facts.health_path || "Not configured"}</code> ·
                  Workflow:{" "}
                  <code>{target.facts.workflow_path || "Not configured"}</code>
                </p>
                <p>
                  Registered operations:{" "}
                  {target.facts.operations?.join(", ") || "None"}
                </p>
                <details>
                  <summary>Recovery contract</summary>
                  <pre>{JSON.stringify(target.facts.contract, null, 2)}</pre>
                </details>
                <p>
                  Monitoring{" "}
                  {target.facts.monitoring_enabled ? "enabled" : "disabled"}.{" "}
                  {target.facts.adapter === "generic-http-v1"
                    ? "Monitoring and contract review are available; this service has no demo fault controls."
                    : "CampusPass fixture controls require explicit opt-in."}
                </p>
              </>
            )}
          </section>
          <div className="scenario-grid">
            {target.scenarios.map((choice) => {
              const reason = scenarioReason(
                target,
                choice,
                approve,
                requirements,
              );
              return (
                <article
                  className={"scenario-card scenario-" + choice.id}
                  key={choice.id}
                >
                  <div className="scenario-top">
                    <span>
                      {target.kind === "repository"
                        ? "REPOSITORY SCENARIO"
                        : "SERVICE SCENARIO"}
                    </span>
                    <Code2 size={23} />
                  </div>
                  <h2>{choice.title}</h2>
                  <p>{choice.description}</p>
                  <div className="scenario-proof">
                    <span>{reason ? "UNAVAILABLE" : "EVIDENCE BOUNDARY"}</span>
                    <p id={"reason-" + choice.id}>
                      {reason ||
                        (choice.id === "injected"
                          ? "Explicitly injected. Passing original → failing copied baseline → normal repair → immutable acceptance checks."
                          : target.kind === "repository"
                            ? "A failing baseline is required. Success means the same original acceptance tests pass."
                            : "Only the selected target’s configured capabilities are used.")}
                    </p>
                  </div>
                  <button
                    className="button"
                    disabled={busy || !!reason}
                    aria-describedby={"reason-" + choice.id}
                    onClick={() => start(choice)}
                  >
                    {choice.id === "monitor"
                      ? "View monitoring"
                      : choice.id === "contract"
                        ? "Review contract"
                        : "Start scenario"}
                    <ArrowRight size={16} />
                  </button>
                </article>
              );
            })}
          </div>
        </>
      )}
      <div className="demo-lower">
        <section className="card">
          <div className="section-title">
            <div>
              <h2>Rehearsal history</h2>
            </div>
            {project?.adapter === "campuspass-v1" && (
              <button
                className="inline-link"
                disabled={busy || !enabled || !project.demo_enabled}
                onClick={() =>
                  setScenario({
                    id: "reset",
                    title: "Clear injected fault",
                    description: "Clear only the CampusPass demo fault.",
                    disabled_reason: null,
                  })
                }
              >
                <RotateCcw size={14} />
                Clear injected fault
              </button>
            )}
          </div>
          {historyError && <p role="alert">{historyError}</p>}
          {history.length ? (
            <div className="run-list">
              {history.map((run) => (
                <div className="run-row" key={run.id}>
                  <span className="run-letter">
                    {run.scenario === "injected"
                      ? "I"
                      : run.scenario === "repair"
                        ? "R"
                        : run.scenario === "outage"
                          ? "C"
                          : run.scenario === "reset"
                            ? "↺"
                            : "B"}
                  </span>
                  <div>
                    <strong>
                      {run.scenario === "injected"
                        ? "Disclosed injected regression"
                        : words(run.scenario) + " scenario"}
                    </strong>
                    <p>{stamp(run.created)}</p>
                    {run.message && <p>{run.message}</p>}
                  </div>
                  <Badge state={run.incident_status || run.status} />
                  {run.incident_id ? (
                    <>
                      <button
                        className="inline-link"
                        onClick={() => open(run.incident_id!)}
                      >
                        Follow recovery
                        <ArrowRight size={14} />
                      </button>
                      <button
                        className="inline-link"
                        onClick={() =>
                          act(() => downloadBrief(run.incident_id!, token))
                        }
                      >
                        Receipt
                      </button>
                    </>
                  ) : (
                    <span className="run-message">
                      {run.status === "failed"
                        ? "Setup failed; inspect target"
                        : run.scenario === "reset"
                          ? "History preserved"
                          : run.status === "executing"
                            ? "Preparing scenario"
                            : "Waiting for monitor detection"}
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <Empty title="No runs for this target">
              Repository scenarios and CampusPass rehearsals retain incident and
              receipt links here. Monitoring and contract review do not
              fabricate recovery runs.
            </Empty>
          )}
        </section>
        <aside className="card rehearsal-notes">
          <h2>
            Show the decision.
            <br />
            Then show the proof.
          </h2>
          <ol>
            <li>Select the real target and inspect its capabilities.</li>
            <li>
              For injected regressions, disclose the mutation before running it.
            </li>
            <li>Inspect baseline results and compared recovery strategies.</li>
            <li>Review the patch and immutable acceptance checks.</li>
            <li>Close with the incident receipt.</li>
          </ol>
          <p>
            Inference takes real time. Setup failure is not a verified recovery.
            Repository patches never publish changes.
          </p>
        </aside>
      </div>
      {scenario && target && (
        <Dialog title={scenario.title} onClose={close} busy={busy}>
          <p className="dialog-copy">
            Target: <strong>{target.name}</strong>
          </p>
          <div className="alert warning">
            <ShieldCheck size={18} />
            <span>
              {scenario.id === "injected"
                ? "DISCLOSED INJECTED REGRESSION: one deterministic mutation will be applied to a separate managed copy. The original snapshot is never modified. The passing original and failing copied baseline must both be proven."
                : scenario.description}
            </span>
          </div>
          <div className="dialog-actions">
            <button
              className="button secondary"
              disabled={busy}
              onClick={close}
            >
              Cancel
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={() =>
                act(
                  async () => {
                    if (target.kind === "repository") {
                      await api("/demo/repositories/run", token, {
                        repository: target.id,
                        scenario: scenario.id,
                        request_id: crypto.randomUUID(),
                        requirements,
                        install_dependencies: approve,
                      });
                    } else
                      await api("/demo/projects/" + target.id + "/run", token, {
                        scenario: scenario.id,
                        request_id: crypto.randomUUID(),
                      });
                    close();
                  },
                  target.kind === "repository"
                    ? "Scenario queued; inspect real baseline evidence"
                    : "Controlled CampusPass setup requested",
                )
              }
            >
              {busy
                ? "Starting…"
                : "Run " +
                  (scenario.id === "injected"
                    ? "disclosed injection"
                    : "scenario")}
              <ArrowRight size={15} />
            </button>
          </div>
        </Dialog>
      )}
    </div>
  );
}

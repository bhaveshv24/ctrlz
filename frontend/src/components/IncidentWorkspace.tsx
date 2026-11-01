import RepositoryCheckGuide from "./RepositoryCheckGuide";
import RecoveryProgress from "./RecoveryProgress";
import MotionHeading from "./MotionHeading";
import RuntimeIncident from "./RuntimeIncident";
import { useCallback, useEffect, useState } from "react";
import { StoryPlate } from "./StoryPlate";
import { FilePlate } from "./FilePlate";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  Check,
  Code2,
  FileJson,
  GitCompareArrows,
  Play,
  RotateCcw,
  ShieldCheck,
  Terminal,
  X,
} from "lucide-react";
import {
  api,
  downloadBrief,
  downloadRepairedZip,
  saveFile,
  type Candidate,
  type FlightEvent,
  type Incident,
  type Receipt,
} from "../api";
import {
  clock,
  duration,
  eventSummary,
  lifecycle,
  measuredDuration,
  stamp,
  receiptMatchesIncident,
  title,
  words,
} from "../presentation";
import { Badge, CheckList, Dialog, Loading } from "./ui";

type Props = {
  incident: Incident;
  token: string;
  revision: number;
  onBack: () => void;
  onChange: () => Promise<void>;
  notify: (text: string) => void;
};
export default function IncidentWorkspace({
  incident,
  token,
  revision,
  onBack,
  onChange,
  notify,
}: Props) {
  const [receipt, setReceipt] = useState<Receipt | null>(null),
    [tab, setTab] = useState("Story"),
    [sceneView, setSceneView] = useState("timeline"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [approval, setApproval] = useState(false);
  useEffect(() => {
    let active = true;
    api<Receipt>("/incidents/" + incident.id + "/receipt", token)
      .then((r) => {
        if (active) { setReceipt(r); setError(""); }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [incident.id, incident.updated, token, revision]);
  const closeApproval = useCallback(() => setApproval(false), []);
  const act = async (fn: () => Promise<unknown>, message?: string) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await onChange().catch(() => {});
      try {
        const result = await api<Receipt>("/incidents/" + incident.id + "/receipt", token);
        setReceipt(result);
      } catch {
        setError("Action completed, but the updated receipt could not load. Refresh before taking another action.");
      }
      if (message) notify(message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  if (!receipt || !receiptMatchesIncident(receipt, incident.id))
    return (
      <>
        <button className="back-button" onClick={onBack}>
          <ArrowLeft size={15} />
          Back to incidents
        </button>
        {error ? (
          <div className="alert danger" role="alert">
            {error}
          </div>
        ) : (
          <Loading />
        )}
      </>
    );
  if (receipt.incident.kind === "runtime") return <RuntimeIncident key={receipt.incident.id} receipt={receipt} token={token} onBack={onBack} onChange={onChange} />;
  const i = receipt.incident,
    verified = receipt.success,
    stages = lifecycle(receipt),
    candidates = i.plan?.candidates || [],
    decisions = i.tournament || [],
    tools = receipt.events.filter((e) => ["tool_result", "repository_context", "baseline_tests", "code_proposal_rejected", "candidate_tests", "guard_candidate_tests"].includes(e.stage)),
    lastProposal = receipt.events.filter(e => e.stage === "code_proposal").slice(-1)[0]?.payload,
    baseline = receipt.events.find(e => e.stage === "baseline_tests"),
    terminal = ["resolved", "blocked", "escalated"].includes(i.status),
    tabs = [
      "Story",
      "Strategies",
      "Flight recorder",
      "Receipt",
      ...(i.patch ? ["Patch"] : []),
    ];
  const downloadRepairedRepository = async () => {
    setBusy(true);
    setError("");
    try {
      await downloadRepairedZip(i.id, token);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <button className="back-button" onClick={onBack}>
        <ArrowLeft size={15} />
        All incidents
      </button>
      <div className="page-title incident-title">
        <div>
          <div className="eyebrow">
            RECOVERY WORKSPACE <span>/</span> {i.id.slice(0, 8)}
          </div>
          <MotionHeading text={title(i)}/>
          <p>
            {i.project_id} <span>·</span> Detected {stamp(i.created)}
          </p>
        </div>
        <div className="heading-actions">
          <Badge state={i.status} />
          {i.kind === "code" && ["escalated", "blocked"].includes(i.status) && (
            <button className="button primary" disabled={busy} onClick={() => act(() => api("/incidents/" + i.id + "/retry-repair", token, {}), "Repair restarted with the original source and tests.")}>
              <RotateCcw size={16} />{i.import_request?.mode === "complete" ? "Retry completion" : "Retry repair"}
            </button>
          )}
          {baseline && (
            <button className="button secondary" onClick={() => {
              const data = baseline.payload;
              const cases = Array.isArray(data.cases) ? data.cases : [];
              saveFile("ctrlz-" + i.id + "-before-repair.txt", [
                "CtrlZ — Errors before repair",
                "Incident: " + i.id,
                "Original commit: " + (i.commit || "Unavailable"),
                "Exit code: " + String(data.exit_code),
                "", "Failing checks:",
                ...cases.filter(c => !c.passed && c.status !== "skipped").map(c => "- " + c.id + " (" + c.status + ")"),
                "", "Original test output:", String(data.output || "No output captured."),
              ].join("\n"), "text/plain;charset=utf-8");
            }}>
              <ArrowDownToLine size={15} />Download errors before repair
            </button>
          )}
          {verified && i.patch && (
            <button className="button primary" disabled={busy} onClick={downloadRepairedRepository}>
              <ArrowDownToLine size={16} />
              {busy ? "Preparing download…" : i.import_request?.mode === "complete" ? "Download updated project (.zip)" : "Download fixed code (.zip)"}
            </button>
          )}
          <button
            className="button secondary"
            onClick={() =>
              act(async () =>
                saveFile(
                  "ctrlz-" + i.id + ".json",
                  JSON.stringify(
                    await api("/incidents/" + i.id + "/receipt", token),
                    null,
                    2,
                  ),
                ),
              )
            }
          >
            <ArrowDownToLine size={15} />
            Export evidence
          </button>
        </div>
      </div>
      {error && (
        <div className="alert danger" role="alert">
          {error}
        </div>
      )}
      <div
        className={
          "outcome-banner " +
          (verified
            ? "verified"
            : i.status === "awaiting_approval"
              ? "approval"
              : "pending")
        }
      >
        <span className="outcome-symbol">
          {verified ? (
            <ShieldCheck size={25} />
          ) : i.status === "awaiting_approval" ? (
            <GitCompareArrows size={25} />
          ) : (
            <Terminal size={25} />
          )}
        </span>
        <div>
          <strong>
            {verified
              ? (i.import_request?.mode === "complete" ? "Project changes tested. Ready for review." : "Recovery verified. Evidence retained.")
              : i.status === "awaiting_approval"
                ? "The next decision is yours."
                : i.status === "escalated" || i.status === "blocked"
                  ? "Recovery is not yet proven."
                  : "Investigation in progress."}
          </strong>
          <p>
            {verified
              ? i.kind === "code"
                ? i.selected_code_strategy === "RETRY"
                  ? "The original tests passed on both reruns. Flaky behavior remains; no source patch was produced."
                  : i.import_request?.mode === "complete" ? "The generated changes passed the existing tests. Review prompt coverage and remaining work before using the project." : "The candidate passed the original acceptance tests. The patch is ready for review."
                : "Independent checks passed after the permitted action. Remaining risks are recorded below."
              : i.error ||
                "Agents propose a recovery. Your contract controls what can execute."}
          </p>
        </div>
        {verified && (
          <div className="outcome-duration">
            <b>{duration(measuredDuration(receipt))}</b>
            <small>detect → verify</small>
          </div>
        )}
      </div>
      {i.injected_regression && (
        <div className="alert warning" role="note">
          <ShieldCheck size={18} />
          <span>
            <strong>Disclosed injected regression.</strong> This demonstration
            uses a deliberately mutated copy; the original snapshot is
            untouched.{" "}
            {i.injected_regression.proven
              ? `Passing original and failing copied baselines proven. Mutation: ${i.injected_regression.file} (${i.injected_regression.kind}).`
              : "A failing injected baseline has not yet been proven."}
          </span>
        </div>
      )}
      <RecoveryProgress stages={stages} active={!terminal && i.status !== "awaiting_approval"} />
      <div
        className="workspace-tabs"
        role="tablist"
        aria-label="Incident views"
      >
        {tabs.map((name, index) => (
          <button
            role="tab"
            tabIndex={tab === name ? 0 : -1}
            onKeyDown={(e) => {
              let next = index;
              if (e.key === "ArrowRight") next = (index + 1) % tabs.length;
              else if (e.key === "ArrowLeft")
                next = (index + tabs.length - 1) % tabs.length;
              else if (e.key === "Home") next = 0;
              else if (e.key === "End") next = tabs.length - 1;
              else return;
              e.preventDefault();
              setTab(tabs[next]);
              document
                .getElementById("tab-" + tabs[next].replaceAll(" ", "-"))
                ?.focus();
            }}
            aria-selected={tab === name}
            aria-controls="incident-view"
            id={"tab-" + name.replaceAll(" ", "-")}
            key={name}
            onClick={() => setTab(name)}
          >
            {name}
            {name === "Strategies" && candidates.length > 0 && (
              <span>{candidates.length}</span>
            )}
          </button>
        ))}
      </div>
      <div
        key={tab}
        id="incident-view"
        role="tabpanel"
        aria-labelledby={"tab-" + tab.replaceAll(" ", "-")}
        tabIndex={0}
      >
        {tab === "Story" &&
          i.kind === "code" &&
          receipt.events.some((e) => e.stage === "repository_assessment") && (
            <label className="scene-choice">
              Scene
              <select
                value={sceneView}
                onChange={(e) => setSceneView(e.target.value)}
              >
                <option value="timeline">Event timeline</option>
                <option value="files">Repository file graph</option>
              </select>
            </label>
          )}
        {tab === "Story" && sceneView === "timeline" && (
          <StoryPlate receipt={receipt} />
        )}
        {tab === "Story" &&
          sceneView === "files" &&
          i.kind === "code" &&
          receipt.events
            .filter((e) => e.stage === "repository_assessment")
            .slice(-1)
            .map((e) => (
              <FilePlate
                key={e.id}
                inspection={e.payload}
                events={receipt.events}
              />
            ))}
        {tab === "Story" && i.kind === "code" && (
          <CodeComparison incident={i} />
        )}
        {tab === "Story" && (
          <div className="incident-columns">
            <div>
              <section className="card">
                <div className="section-title">
                  <div>
                    <h2>Investigation snapshot</h2>
                  </div>
                  <span className="source-label">
                    {receipt.model ? "NVIDIA NIM" : "Recorded diagnosis"}
                  </span>
                </div>
                <p className="snapshot-note">
                  Recorded before execution. Final acceptance results are shown
                  in independent verification.
                </p>
                <div className="markdown">
                  <Markdown remarkPlugins={[remarkGfm]} skipHtml>
                    {i.diagnosis ||
                      i.plan?.diagnosis || lastProposal?.diagnosis ||
                      (terminal ? "No valid diagnosis was returned. Inspect the recorded test results and rejected proposals below." : "Read-only diagnostic tools are gathering evidence.")}
                  </Markdown>
                </div>
                {!!i.requirement_assessment?.length && <details>
                  <summary>Requirements reconstructed from repository evidence</summary>
                  <p className="snapshot-note">Agent assessment; independent tests establish verification.</p>
                  <ul>{i.requirement_assessment.map((finding, n) => <li key={n}>
                    <strong>{finding.status}: {finding.requirement}</strong>
                    <p>{finding.explanation}</p><code>{finding.evidence_paths.join(", ") || "Evidence unknown"}</code>
                  </li>)}</ul>
                  <h3>Continuation plan</h3>
                  <ol>{i.continuation_plan?.map((step,n) => <li key={n}>{step}</li>)}</ol>
                </details>}
              </section>
              <section className="card">
                <div className="section-title">
                  <div>
                    <h2>Observed, not assumed</h2>
                  </div>
                  <span className="count">{tools.length} evidence records</span>
                </div>
                {tools.length ? (
                  tools.slice(-6).map((e) => <Evidence key={e.id} event={e} />)
                ) : (
                  <p className="subtle">
                    No diagnostic tool output has been recorded.
                  </p>
                )}
              </section>
            </div>
            <aside>
              <section className="card selected-strategy">
                <h2>
                  {i.selected
                    ? "Selected recovery"
                    : i.kind === "code" ? (i.selected_code_strategy ? "Selected: " + i.selected_code_strategy : terminal ? "No repair passed verification" : "Evaluating repair candidates") : "No strategy selected yet"}
                </h2>
                {i.selected ? (
                  <>
                    <div className="operation-list">
                      {i.selected.actions.map((a, n) => (
                        <div key={n}>
                          <span>{String(n + 1).padStart(2, "0")}</span>
                          <code>{a.operation}</code>
                          {a.order_id && (
                            <small>Order {a.order_id.slice(0, 8)}</small>
                          )}
                        </div>
                      ))}
                    </div>
                    <p>{i.selected.rationale}</p>
                    <button
                      className="inline-link"
                      onClick={() => setTab("Strategies")}
                    >
                      Compare alternatives
                      <ArrowRight size={14} />
                    </button>
                  </>
                ) : (
                  <p>
                    {i.kind === "code"
                      ? i.selected_code_strategy ? "The selected candidate passed the original acceptance suite." : terminal ? "Candidates were rejected. No verified repair is available for this run." : "CtrlZ is testing candidates against the existing acceptance suite."
                      : "The planner must produce an eligible strategy before execution."}
                  </p>
                )}
              </section>
              {i.status === "awaiting_approval" && (
                <section className="card approval-card">
                  <ShieldCheck size={23} />
                  <h2>Approval required</h2>
                  <p>
                    Review the exact actions and risks. Authorization applies to
                    this candidate and contract; preconditions are checked
                    again.
                  </p>
                  <button
                    className="button primary full"
                    onClick={() => setApproval(true)}
                  >
                    Review decision
                    <ArrowRight size={15} />
                  </button>
                </section>
              )}
              <section className="card">
                <h2>Independent verification</h2>
                {i.kind === "code" && i.import_request?.mode !== "complete" && <RepositoryCheckGuide profile={String((i as Incident & {repair_profile?:string}).repair_profile || baseline?.payload.profile || "")} repaired={verified} failures={i.diagnosis && Array.isArray(baseline?.payload.cases) ? baseline.payload.cases.filter(c => c.status === "failed" || c.status === "error") : []} />}
                {i.verification ? (
                  <CheckList checks={i.verification.checks} />
                ) : (
                  <p className="subtle">
                    No acceptance result yet. An agent's recommendation cannot
                    mark this incident successful.
                  </p>
                )}
              </section>
              {i.remaining_risks?.length && (
                <section className="risk-card">
                  <h3>What remains uncertain</h3>
                  {i.remaining_risks.map((r, n) => (
                    <p key={n}>{r}</p>
                  ))}
                </section>
              )}
              {["blocked", "escalated"].includes(i.status) && (
                <button
                  className="button secondary full"
                  disabled={busy}
                  onClick={() =>
                    act(
                      () => api("/incidents/" + i.id + "/retry", token, {}),
                      "Investigation queued with fresh evidence",
                    )
                  }
                >
                  <RotateCcw size={15} />
                  Reinvestigate
                </button>
              )}
            </aside>
          </div>
        )}
        {tab === "Strategies" && (
          <>
            <div className="view-intro">
              <h2>A tournament of evidence.</h2>
              <p>
                Alternatives are compared by permissions, current preconditions
                and action count. There are no invented scores. Replay evidence
                is shown separately from live verification.
              </p>
            </div>
            {i.kind === "code" && <CodeComparison incident={i} />}
            <div className="strategy-grid">
              {candidates.map((c) => {
                const decision = decisions.find((d) => d.candidate_id === c.id),
                  replay = receipt.events
                    .filter(
                      (e) =>
                        e.payload.candidate_id === c.id &&
                        [
                          "replay_started",
                          "replay_result",
                          "replay_failed",
                        ].includes(e.stage),
                    )
                    .at(-1);
                return (
                  <article
                    className={
                      "card strategy-card " +
                      (i.selected?.id === c.id ? "chosen" : "")
                    }
                    key={c.id}
                  >
                    <div className="strategy-top">
                      <span className="strategy-id">{c.id}</span>
                      {decision ? (
                        <Badge
                          state={decision.eligible ? "healthy" : "blocked"}
                        >
                          {decision.eligible ? "Eligible" : "Blocked"}
                        </Badge>
                      ) : (
                        <Badge state="unknown">Not evaluated</Badge>
                      )}
                    </div>
                    <h3>
                      {i.selected?.id === c.id
                        ? "Selected strategy"
                        : "Alternative strategy"}
                    </h3>
                    <p>{c.rationale}</p>
                    <div className="operation-list">
                      {c.actions.map((a, n) => (
                        <div key={n}>
                          <code>{a.operation}</code>
                        </div>
                      ))}
                      {!c.actions.length && (
                        <p>No executable actions proposed.</p>
                      )}
                    </div>
                    {decision && (
                      <div className="strategy-checks">
                        {decision.checks.map((check, n) => (
                          <div
                            key={n}
                            className={check.passed ? "pass" : "fail"}
                          >
                            {check.passed ? (
                              <Check size={14} />
                            ) : (
                              <X size={14} />
                            )}
                            <span>{check.reason}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {c.risks?.length > 0 && (
                      <details className="disclosure">
                        <summary>
                          Risks and tradeoffs ({c.risks.length})
                        </summary>
                        <ul>
                          {c.risks.map((risk, n) => (
                            <li key={n}>{risk}</li>
                          ))}
                        </ul>
                      </details>
                    )}
                    {decision?.approval_required && (
                      <div className="approval-note">
                        Explicit operator approval required
                      </div>
                    )}
                    {receipt.replay_supported && (
                      <div className="replay-control">
                        <button
                          className="button secondary"
                          disabled={busy || replay?.stage === "replay_started"}
                          onClick={() =>
                            act(
                              () =>
                                api("/incidents/" + i.id + "/replay", token, {
                                  candidate_id: c.id,
                                }),
                              "Isolated replay queued; watch the flight recorder",
                            )
                          }
                        >
                          <Play size={13} />
                          Replay in isolation
                        </button>
                        {replay && (
                          <span className="subtle">
                            {replay.stage === "replay_started"
                              ? "Started; awaiting result"
                              : replay.stage === "replay_failed"
                                ? "Replay failed"
                                : replay.payload.verification?.passed
                                  ? "Replay verified"
                                  : "Acceptance failed"}
                          </span>
                        )}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
            {!candidates.length && i.kind !== "code" && (
              <div className="card subtle">
                No recovery candidates have been recorded yet.
              </div>
            )}
          </>
        )}
        {tab === "Flight recorder" && (
          <section className="card recorder">
            <div className="section-title">
              <div>
                <h2>Every meaningful step.</h2>
              </div>
              <span className="count">{receipt.events.length} events</span>
            </div>
            {receipt.events.map((e) => (
              <details className="flight-event" key={e.id}>
                <summary>
                  <span className="event-index">
                    {String(e.id).padStart(2, "0")}
                  </span>
                  <div>
                    <strong>{words(e.stage)}</strong>
                    <p>{eventSummary(e)}</p>
                  </div>
                  <time>{clock(e.timestamp)}</time>
                </summary>
                <pre>{JSON.stringify(e.payload, null, 2)}</pre>
              </details>
            ))}
          </section>
        )}
        {tab === "Receipt" && (
          <section className="card receipt-card">
            <div className="receipt-heading">
              <div className="receipt-logo">
                <RotateCcw size={24} />
              </div>
              <span>CTRLZ / RECOVERY RECEIPT</span>
              <Badge state={verified ? "verified" : "unknown"}>
                {verified ? "Verified recovery" : "Unresolved"}
              </Badge>
            </div>
            <h2>{title(i)}</h2>
            <p className="subtle">{i.id}</p>
            <div className="receipt-facts">
              <div>
                <small>Project</small>
                <strong>{i.project_id}</strong>
              </div>
              <div>
                <small>Detected</small>
                <strong>{stamp(i.created)}</strong>
              </div>
              <div>
                <small>Measured recovery</small>
                <strong>{duration(measuredDuration(receipt))}</strong>
              </div>
              <div>
                <small>Recorded events</small>
                <strong>{receipt.events.length}</strong>
              </div>
            </div>
            {i.kind === "code" && <CodeComparison incident={i} />}
            <h3>Acceptance evidence</h3>
            {i.verification ? (
              <CheckList checks={i.verification.checks} />
            ) : (
              <p>No independent verification has been recorded.</p>
            )}
            <h3>Remaining risks</h3>
            {i.remaining_risks?.map((risk, n) => (
              <p className="receipt-risk" key={n}>
                {risk}
              </p>
            ))}
            <div className="receipt-provenance">
              <span>
                <ShieldCheck size={15} />
                Recorded provenance
              </span>
              <p>
                {receipt.reasoning_provider}
                {receipt.model ? " / " + receipt.model : ""}
              </p>
              <code>
                {receipt.integrity?.snapshot_digest || "Checksum not available"}
              </code>
              <small>
                SHA-256 identifies this exported snapshot. It is not a digital
                signature.
              </small>
            </div>
            <div className="receipt-actions">
              <button
                className="button primary"
                onClick={() =>
                  saveFile(
                    "ctrlz-" + i.id + ".json",
                    JSON.stringify(receipt, null, 2),
                  )
                }
              >
                <FileJson size={16} />
                Download JSON
              </button>
              <button
                className="button secondary"
                onClick={() => act(() => downloadBrief(i.id, token))}
              >
                <ArrowDownToLine size={16} />
                Download readable brief
              </button>
            </div>
          </section>
        )}
        {tab === "Patch" && (
          <section className="card">
            <div className="section-title">
              <div>
                <h2>A change you can review.</h2>
              </div>
              <button
                className="button secondary"
                onClick={() =>
                  saveFile(
                    "ctrlz-" + i.id + ".patch",
                    i.patch || "",
                    "text/plain",
                  )
                }
              >
                <ArrowDownToLine size={15} />
                Download patch
              </button>
            </div>
            <div className="alert information">
              <Code2 size={18} />
              <span>
                {verified
                  ? "This candidate passed the original acceptance tests."
                  : "This candidate has not passed the required acceptance tests."}{" "}
                The imported branch was not modified; merge and deployment
                remain separate operator actions.
              </span>
            </div>
            {verified && <button className="button primary" disabled={busy} onClick={downloadRepairedRepository}><ArrowDownToLine size={16} />Download fixed code (.zip)</button>}
            <pre className="patch-view">{i.patch}</pre>
          </section>
        )}
      </div>
      {approval && (
        <Dialog
          title="Authorize this recovery?"
          onClose={closeApproval}
          busy={busy}
        >
          <p className="dialog-copy">
            Only the following candidate will be authorized. The deterministic
            gate will check current state again before executing.
          </p>
          <ApprovalDetail candidate={i.selected!} />
          <div className="dialog-actions">
            <button
              className="button secondary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await api("/incidents/" + i.id + "/decline", token, {
                    approval_hash: i.approval_hash,
                    reason: "Operator declined the proposed recovery",
                  });
                  closeApproval();
                }, "Plan declined; incident remains unresolved")
              }
            >
              Decline plan
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await api("/incidents/" + i.id + "/approve", token, {
                    approval_hash: i.approval_hash,
                  });
                  closeApproval();
                }, "Decision recorded; inspect independent verification")
              }
            >
              <ShieldCheck size={16} />
              {busy ? "Checking…" : "Authorize " + i.selected?.id}
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}
function ApprovalDetail({ candidate }: { candidate: Candidate }) {
  return (
    <div className="approval-detail">
      <strong>Candidate {candidate.id}</strong>
      <p>{candidate.rationale}</p>
      {candidate.actions.map((a, n) => (
        <div className="approval-action" key={n}>
          <code>{a.operation}</code>
          {a.order_id && <small>Order {a.order_id}</small>}
          {a.parameters &&
            Object.entries(a.parameters).map(([key, value]) => (
              <small key={key}>
                {key}: {String(value)}
              </small>
            ))}
        </div>
      ))}
      {candidate.risks?.length > 0 && (
        <ul>
          {candidate.risks.map((r, n) => (
            <li key={n}>{r}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
function Evidence({ event }: { event: FlightEvent }) {
  const p = event.payload,
    r = event.stage === "tool_result" ? p.result : p;
  return (
    <details className="evidence-item">
      <summary>
        <span className="evidence-icon">
          <Terminal size={16} />
        </span>
        <div>
          <strong>
            {event.stage !== "tool_result" ? words(event.stage) : p.tool === "runbook_search"
              ? "Runbook retrieval"
              : words(p.tool || "diagnostic tool")}
          </strong>
          <p>{eventSummary(event)}</p>
        </div>
        <span className="evidence-reference">#{event.id}</span>
      </summary>
      <pre>{JSON.stringify(r, null, 2)}</pre>
    </details>
  );
}

function CodeComparison({ incident }: { incident: Incident }) {
  return (
    <section className="code-comparison" aria-label="Code recovery tournament">
      <h3>Code recovery tournament</h3>
      <p>
        Original immutable acceptance must pass. Selection: smallest
        changed-line count, then fewest strategy sandbox runs.
      </p>
      {incident.selected_code_strategy && (
        <p>
          Selected: <strong>{incident.selected_code_strategy}</strong>
        </p>
      )}
      {incident.suspect_commit && (
        <p>
          Suspect source commit:{" "}
          <code>
            {incident.suspect_commit.upstream_commit ||
              incident.suspect_commit.snapshot_commit}
          </code>
        </p>
      )}
      <div className="tournament-table">
        <table>
          <thead>
            <tr>
              <th>Strategy</th>
              <th>Acceptance</th>
              <th>Changed lines</th>
              <th>Sandbox runs</th>
            </tr>
          </thead>
          <tbody>
            {incident.code_tournament?.map((s) => (
              <tr key={s.id}>
                <th scope="row">{s.id}</th>
                <td>{s.eligible ? "Passed" : "Not qualified"}</td>
                <td>{s.diff_lines}</td>
                <td>{s.sandbox_runs}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {incident.code_tournament?.map((s) => (
        <p key={s.id}>
          <strong>{s.id}:</strong> {s.reason}
        </p>
      ))}
      {!incident.code_tournament && (
        <p>
          Strategies are still being evaluated. No winner has been established.
        </p>
      )}
    </section>
  );
}

import { ArrowUpRight, FolderGit2 } from "lucide-react";
import type { ProjectSignal } from "../api";
import { clock } from "../presentation";
import { Badge, Sparkline } from "./ui";
export default function SignalCard({
  signal,
  nested = false,
  onManage,
}: {
  signal: ProjectSignal;
  nested?: boolean;
  onManage: () => void;
}) {
  const { project, latest, state, history } = signal,
    service = latest?.health.accepted ?? latest?.health.ok,
    workflow = latest?.workflows.configured !== false && latest?.workflows.ok,
    missing = workflow
      ? latest?.workflows.body.discrepancies?.length || 0
      : null;
  return (
    <article className={nested ? "signal-card nested" : "card signal-card"}>
      <div className="signal-top">
        <div className="project-symbol">
          <FolderGit2 size={20} />
        </div>
        <div>
          <h3>{project.name}</h3>
          <p>{project.base_url}</p>
        </div>
        <Badge state={state} />
      </div>
      <div className="signal-readings">
        <div>
          <small>Service</small>
          <strong>
            <span
              className={
                latest ? (service ? "dot green" : "dot red") : "dot slate"
              }
            />
            {!latest ? "Not observed" : service ? "Responding" : "Disrupted"}
          </strong>
        </div>
        <div>
          <small>Workflow checks</small>
          <strong>
            <span
              className={
                missing === null
                  ? "dot slate"
                  : missing
                    ? "dot amber"
                    : "dot green"
              }
            />
            {missing === null
              ? latest?.workflows.configured === false
                ? "Not configured"
                : "Not observed"
              : missing
                ? `${missing} ${missing === 1 ? "discrepancy" : "discrepancies"}`
                : "No discrepancy"}
          </strong>
        </div>
        <div>
          <small>Response time</small>
          <strong>
            {latest ? Math.round(latest.health.latency_ms) + " ms" : "—"}
          </strong>
        </div>
      </div>
      <Sparkline history={history} />
      <div className="signal-bottom">
        <span>
          {latest
            ? "Last probe " + clock(latest.timestamp)
            : "Waiting for the first probe"}
          {state === "stale" ? " · stale" : ""}
        </span>
        <button className="inline-link" onClick={onManage}>
          Manage
          <ArrowUpRight size={13} />
        </button>
      </div>
    </article>
  );
}

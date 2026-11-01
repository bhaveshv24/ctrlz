import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import {
  ArrowRight,
  Check,
  ChevronRight,
  LoaderCircle,
  ShieldCheck,
  X,
} from "lucide-react";
import type { Incident, ProjectSignal } from "../api";
import { duration, stamp, title, tone, words } from "../presentation";
export function Badge({
  state,
  children,
}: {
  state: string;
  children?: ReactNode;
}) {
  return (
    <span className={"badge " + tone(state)}>
      {children || words(state)}
    </span>
  );
}
export function Dialog({
  title,
  children,
  onClose,
  busy = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
}) {
  const root = useRef<HTMLDivElement>(null),
    close = useRef(onClose),
    isBusy = useRef(busy);
  close.current = onClose;
  isBusy.current = busy;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement,
      overflow = document.body.style.overflow,
      application = document.getElementById("root"),
      wasInert = application?.inert || false;
    document.body.style.overflow = "hidden";
    if (application) application.inert = true;
    root.current?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isBusy.current) {
        e.preventDefault();
        close.current();
      }
      if (e.key === "Tab") {
        const elements = Array.from(
          root.current?.querySelectorAll<HTMLElement>(
            'button:not(:disabled),input:not(:disabled),textarea,select,a[href],[tabindex="0"]',
          ) || [],
        );
        const first = elements[0],
          last = elements.at(-1);
        if (!first) {
          e.preventDefault();
          return;
        }
        if (
          e.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === root.current)
        ) {
          e.preventDefault();
          last?.focus();
        } else if (
          !e.shiftKey &&
          (document.activeElement === last ||
            document.activeElement === root.current)
        ) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.body.style.overflow = overflow;
      if (application) application.inert = wasInert;
      document.removeEventListener("keydown", key);
      previous?.focus();
    };
  }, []);
  return createPortal(
    <div className="modal-backdrop">
      <div
        className="dialog"
        ref={root}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        tabIndex={-1}
      >
        <div className="dialog-heading">
          <div>
            <h2 id="dialog-title">{title}</h2>
          </div>
          <button
            className="icon-button"
            aria-label="Close dialog"
            onClick={onClose}
            disabled={busy}
          >
            <X size={19} />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}
export function Empty({
  title: heading,
  children,
  action,
  onAction,
}: {
  title: string;
  children: ReactNode;
  action?: string;
  onAction?: () => void;
}) {
  return (
    <div className="empty">
      <div className="empty-orbit">
        <ShieldCheck size={25} />
      </div>
      <h3>{heading}</h3>
      <p>{children}</p>
      {action && (
        <button className="button secondary" onClick={onAction}>
          {action}
          <ArrowRight size={15} />
        </button>
      )}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle size={24} className="spin" />
      <p>Loading recorded evidence…</p>
    </div>
  );
}
export function Sparkline({ history }: { history: ProjectSignal["history"] }) {
  if (history.length < 2)
    return <div className="sparkline-empty">Waiting for more probes</div>;
  const maximum = Math.max(...history.map((p) => p.latency_ms || 0), 1);
  const path = history
    .map(
      (p, i) =>
        `${i ? "L" : "M"}${(i / (history.length - 1)) * 220},${42 - ((p.latency_ms || 0) / maximum) * 34}`,
    )
    .join(" ");
  return (
    <svg
      className="sparkline"
      viewBox="0 0 220 48"
      role="img"
      aria-label={`Observed request latency: ${history.length} probes, latest ${history.at(-1)?.latency_ms} milliseconds`}
    >
      <path d={path + " L220,48 L0,48 Z"} fill="currentColor" opacity=".08" />
      <path
        d={path}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
export function IncidentList({
  incidents,
  onSelect,
  compact = false,
}: {
  incidents: Incident[];
  onSelect: (id: string) => void;
  compact?: boolean;
}) {
  return (
    <div className="incident-list">
      {incidents.map((i) => (
        <button
          className="incident-row"
          key={i.id}
          onClick={() => onSelect(i.id)}
        >
          <span className={"incident-mark " + tone(i.status)}>
            {i.status === "resolved" ? (
              <Check size={17} />
            ) : (
              <span aria-hidden="true">!</span>
            )}
          </span>
          <div className="incident-name">
            <strong>{title(i)}</strong>
            <span>
              {i.project_id}
              <b>·</b>
              <code>{i.id.slice(0, 8)}</code>
            </span>
          </div>
          <Badge state={i.status} />
          {!compact && <time>{stamp(i.created)}</time>}
          <ChevronRight size={16} className="row-arrow" />
        </button>
      ))}
    </div>
  );
}
export function Metric({
  name,
  value,
  note,
  accent = false,
}: {
  name: string;
  value: string | number;
  note: string;
  accent?: boolean;
}) {
  return (
    <article className={"metric " + (accent ? "metric-accent" : "")}>
      <span>{name}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}
export function CheckList({ checks }: { checks?: Record<string, boolean> | null }) {
  if (!checks || Object.keys(checks).length === 0) {
    return <p role="status">Verification checks will appear when this attempt has been tested.</p>;
  }
  return (
    <div className="acceptance-list">
      {Object.entries(checks).map(([name, passed]) => (
        <div key={name}>
          <span className={passed ? "check-icon" : "fail-icon"}>
            {passed ? <Check size={13} /> : <X size={13} />}
          </span>
          <span>{words(name)}</span>
          <strong className={passed ? "text-green" : "text-red"}>
            {passed ? "Passed" : "Failed"}
          </strong>
        </div>
      ))}
    </div>
  );
}
export function Elapsed({ seconds }: { seconds: number | null }) {
  return <>{duration(seconds)}</>;
}

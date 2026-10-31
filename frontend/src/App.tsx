import RuntimeStatus from "./components/RuntimeStatus";
import AccountSettings from "./components/AccountSettings";
import MotionHeading from "./components/MotionHeading";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Bell,
  BookOpen,
  Check,
  ChevronDown,
  Code2,
  FlaskConical,
  FolderGit2,
  LayoutDashboard,
  LoaderCircle,
  LogOut,
  Menu,
  Plus,
  RotateCcw,
  Search,
  Settings,
  ShieldCheck,
  TriangleAlert,
  X,
} from "lucide-react";
import { api, API, ApiError, type Act, type Project } from "./api";
import { useControlCenter } from "./hooks/useControlCenter";
import { Badge, Empty, IncidentList, Metric } from "./components/ui";
import IncidentWorkspace from "./components/IncidentWorkspace";
import { duration, title, words } from "./presentation";
import { navigate } from "./navigation";
import { useRouteMotion } from "./hooks/useRouteMotion";
import PageTitle from "./components/PageTitle";
import SignalCard from "./components/SignalCard";
import ProjectDialog from "./components/ProjectDialog";
import ContinuationForm from "./components/ContinuationForm";
import DemoLab from "./pages/DemoLab";
import { OverviewPlate } from "./components/OverviewPlate";
import { QualitySetting } from "./components/RecoveryScene";
import { useRecoveryMotion } from "./hooks/useRecoveryMotion";

const NAV = [
  { id: "overview", name: "Overview", icon: LayoutDashboard },
  { id: "incidents", name: "Incidents", icon: Activity },
  { id: "projects", name: "Projects", icon: FolderGit2 },
  { id: "continuity", name: "Repository repair", icon: Code2 },
  { id: "demo", name: "Demo Lab", icon: FlaskConical },
  { id: "evidence", name: "Evidence library", icon: BookOpen },
];
export default function App() {
  const [token, setToken] = useState(
      sessionStorage.getItem("ctrlz-token") || "",
    ),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [register, setRegister] = useState(false),
    [registrationEnabled, setRegistrationEnabled] = useState(false),
    [account, setAccount] = useState<{email: string; role: string} | null>(null),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [mobileNav, setMobileNav] = useState(false),
    [projectEdit, setProjectEdit] = useState<Project | "new" | null>(null);
  const onNavigate = useCallback(() => {
    setMobileNav(false);
    setProjectEdit(null);
  }, []);
  const route = useRouteMotion(onNavigate);
  const data = useControlCenter(token),
    page = route.split("/")[0],
    selected = route.startsWith("incident/")
      ? data.incidents.find((i) => i.id === route.split("/")[1])
      : null;
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 6000);
    return () => clearTimeout(timer);
  }, [notice]);
  const notify = useCallback((text: string) => setNotice(text), []),
    closeProject = useCallback(() => setProjectEdit(null), []);
  const act: Act = async (fn, message) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await data.refresh();
      if (message) notify(message);
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    fetch(API + "/auth/config").then(r => r.json()).then(c => setRegistrationEnabled(c.registration_enabled)).catch(() => {});
  }, []);
  useEffect(() => {
    if (!token) return;
    let disposed = false;
    let retry: ReturnType<typeof setTimeout>;
    const identify = async () => {
      try {
        const user = await api<{email: string; role: string}>("/auth/me", token);
        if (!disposed) setAccount(user);
      } catch (e) {
        if (disposed) return;
        if (e instanceof ApiError && e.status === 401) {
          sessionStorage.removeItem("ctrlz-token"); setToken(""); setAccount(null);
        } else {
          // A transport error does not prove that a persisted session is invalid.
          retry = setTimeout(identify, 3000);
        }
      }
    };
    void identify();
    return () => { disposed = true; clearTimeout(retry); };
  }, [token]);
  const connect = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const result = await api<{token: string; user: {email: string; role: string}}>(register ? "/auth/register" : "/auth/login", "", {email, password});
      sessionStorage.setItem("ctrlz-token", result.token);
      setAccount(result.user); setToken(result.token); setPassword("");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  const disconnect = () => {
    api("/auth/logout", token, {}).catch(() => {});
    sessionStorage.removeItem("ctrlz-token");
    setToken(""); setPassword(""); setAccount(null);
  };
  const open = (id: string) => navigate("incident/" + id),
    projects = data.overview?.projects || [],
    summary = data.overview?.summary;
  useRecoveryMotion(route, data.ready);
  useEffect(() => {
    document.body.classList.toggle("studio-login", !data.ready);
  }, [data.ready]);
  if (!data.ready)
    return (
      <div className="login-page">
        <div className="login-art">
          <span className="art-coordinate">
            SYSTEM RECOVERY / HUMAN CONTROL
          </span>
          <div className="login-statement">
            <span className="eyebrow">AUTONOMOUS SOFTWARE RECOVERY</span>
            <h1>
              <span className="title-line">
                <span>Get your time</span>
              </span>{" "}
              <span className="title-line">
                <span>back.</span>
              </span>
            </h1>
            <p>
              Evidence before action.
              <br />
              Verification before victory.
            </p>
          </div>
        </div>
        <main className="login-content">
          <button
            type="button"
            className="brand login-replay"
            aria-label="Return to the opening hero"
            onClick={() =>
              window.dispatchEvent(new Event("ctrlz-replay-intro"))
            }
          >
            <span className="brand-symbol">
              <RotateCcw size={22} />
            </span>
            CtrlZ<span className="wordmark-dot">.</span>
          </button>
          <div className="login-form">
            <span className="eyebrow">WELCOME TO YOUR CONTROL CENTER</span>
            <h2>Back to building.</h2>
            <p>
              Connect to your recovery workspace. Your systems, decisions and
              evidence are waiting.
            </p>
            {token ? <div role="status" aria-live="polite">
              <p>Signed in. Connecting to your workspace…</p>
              <p>Your session is saved. If the connection drops, we’ll retry automatically.</p>
              <button className="button secondary full" onClick={() => data.refresh().catch(() => {})}>Retry workspace connection</button>
              <button className="button secondary full" onClick={disconnect}>Sign out</button>
            </div> : <form onSubmit={connect}>
              <label htmlFor="email">Email address</label>
              <input id="email" type="email" autoComplete="email" value={email}
                onChange={e => setEmail(e.target.value)} placeholder="you@company.com" required />
              <label htmlFor="password">Password</label>
              <input id="password" type="password" autoComplete={register ? "new-password" : "current-password"}
                minLength={12} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} required />
              <small>Connect any supported repository or HTTP service to your recovery workspace.</small>
              <button className="button primary full" disabled={busy}>
                {busy ? <LoaderCircle size={17} className="spin" /> : <ArrowRight size={17} />}
                {register ? "Create your account" : "Sign in"}
              </button>
              {registrationEnabled && <button type="button" className="button secondary full" onClick={() => {setRegister(!register);setError("");}}>
                {register ? "Already have an account? Sign in" : "New to CtrlZ? Create an account"}
              </button>}
            </form>}
            {(error || data.error) && (
              <div className="alert danger" role="alert">
                {error || data.error}
              </div>
            )}
            <div className="login-trust">
              <ShieldCheck size={16} />
              <span>Actions stay governed by your recovery contract.</span>
            </div>
          </div>
          <footer>
            COMMITMENT ISSUES<span>AGENTATHON 2026</span>
          </footer>
        </main>
      </div>
    );
  return (
    <div className="application">
      <a
        className="skip-link"
        href="#main-content"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Skip to main content
      </a>
      <aside className={"sidebar " + (mobileNav ? "is-open" : "")}>
        <a href="#overview" className="brand" aria-label="CtrlZ overview">
          <span className="brand-symbol">
            <RotateCcw size={21} />
          </span>
          CtrlZ<span className="wordmark-dot">.</span>
          <span className="edition">v0.2</span>
        </a>
        <div className="workspace-switch">
          <span className="workspace-monogram">CI</span>
          <div>
            <strong>{account?.role === "admin" ? "Administration" : "My workspace"}</strong>
            <span>Recovery workspace</span>
          </div>
          <ChevronDown size={13} />
        </div>
        <span className="nav-caption">CONTROL CENTER</span>
        <nav aria-label="Main navigation">
          {NAV.map(({ id, name, icon: Icon }) => (
            <a
              key={id}
              href={"#" + id}
              aria-current={
                page === id || (page === "incident" && id === "incidents")
                  ? "page"
                  : undefined
              }
            >
              <Icon size={18} />
              <span>{name}</span>
              {id === "incidents" && !!summary?.open_incidents && (
                <b>{summary.open_incidents}</b>
              )}
              {id === "demo" && <small>LIVE</small>}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-principle">
            <div>
              <ShieldCheck size={18} />
              <span>Autonomy, with boundaries.</span>
            </div>
            <p>
              The agent can propose.
              <br />
              Your contract has the final word.
            </p>
            <span className="principle-line" />
          </div>
          <a
            href="#settings"
            className={
              "sidebar-settings " + (page === "settings" ? "current" : "")
            }
          >
            <Settings size={17} />
            Workspace settings
          </a>
          <div className="operator">
            <span className="operator-avatar">CI</span>
            <div>
              <strong>{account?.email || "Signed in"}</strong>
              <span>{account?.role || "user"}</span>
            </div>
            <button aria-label="Disconnect workspace" onClick={disconnect}>
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="mobile-menu icon-button"
              aria-label={mobileNav ? "Close navigation" : "Open navigation"}
              aria-expanded={mobileNav}
              onClick={() => setMobileNav(!mobileNav)}
            >
              {mobileNav ? <X size={20} /> : <Menu size={20} />}
            </button>
            <span>Workspace</span>
            <span>/</span>
            <strong>
              {selected
                ? "Recovery workspace"
                : NAV.find((n) => n.id === page)?.name || "Settings"}
            </strong>
          </div>
          <div className="topbar-actions">
            <span className={"connection " + data.connection}>
              <i />
              {data.connection === "live"
                ? "Live stream"
                : data.connection === "polling"
                  ? "Polling updates"
                  : data.connection === "offline"
                    ? "Offline"
                    : "Connecting"}
            </span>
            <button
              className="notification-button"
              aria-label={`${summary?.approvals_waiting || 0} approvals waiting`}
              onClick={() => {
                setFilter("approval");
                navigate("incidents");
              }}
            >
              <Bell size={17} />
              {!!summary?.approvals_waiting && <i />}
            </button>
            <span className="top-avatar">CI</span>
          </div>
        </header>
        <main id="main-content" tabIndex={-1} className="main-content">
          {(error || data.error) && (
            <div className="alert danger" role="alert">
              <TriangleAlert size={17} />
              <span>{error || data.error}</span>
              {error && (
                <button
                  className="icon-button"
                  aria-label="Dismiss error"
                  onClick={() => setError("")}
                >
                  <X size={16} />
                </button>
              )}
            </div>
          )}
          {notice && (
            <div className="toast" role="status">
              <Check size={16} />
              {notice}
            </div>
          )}
          {selected ? (
            <IncidentWorkspace
              key={selected.id}
              incident={selected}
              token={token}
              revision={data.events.at(-1)?.id || 0}
              onBack={() => navigate("incidents")}
              onChange={data.refresh}
              notify={notify}
            />
          ) : page === "incident" ? (
            <Empty title="Incident not found">
              This incident is not in the connected workspace.
            </Empty>
          ) : (
            <>
              {page === "overview" && (
                <>
                  <div className="page-title">
                    <div>
                      <div className="eyebrow">
                        <span className="live-dot" /> RECOVERY OPERATIONS
                      </div>
                      <MotionHeading text="Back to building." />
                      <p>
                        See what needs attention. Understand every decision.
                        Keep the proof.
                      </p>
                    </div>
                    <button
                      className="button dark"
                      onClick={() => navigate("continuity")}
                    >
                      <Code2 size={16} />
                      Repair a repository
                      <ArrowUpRight size={14} />
                    </button>
                  </div>
                  {data.overview && <OverviewPlate overview={data.overview} />}
                  <div className="command-banner overview-recovery-banner">
                    <div className="command-emblem">
                      <ShieldCheck size={26} />
                    </div>
                    <div>
                      <strong>
                        {summary?.open_incidents
                          ? `${summary.open_incidents} incident${summary.open_incidents === 1 ? "" : "s"} ${summary.open_incidents === 1 ? "needs" : "need"} a way forward.`
                          : "A recovery is only as good as its evidence."}
                      </strong>
                      <p>
                        {summary?.approvals_waiting
                          ? `${summary.approvals_waiting} scoped decision${summary.approvals_waiting === 1 ? " is" : "s are"} waiting for your review.`
                          : "Agents investigate. Contracts govern. Independent checks decide success."}
                      </p>
                    </div>
                    <span className="command-label">NVIDIA NIM × CREWAI</span>
                  </div>
                  <div className="metrics-grid">
                    <Metric
                      name="Verified recoveries"
                      value={summary?.verified_recoveries || 0}
                      note="Independent acceptance checks passed"
                      accent
                    />
                    <Metric
                      name="Median recovery"
                      value={duration(summary?.median_recovery_seconds)}
                      note={`From ${summary?.measured_recoveries || 0} measured incident timelines`}
                    />
                    <Metric
                      name="Rejected evaluations"
                      value={summary?.rejected_evaluations || 0}
                      note="Strategies blocked by deterministic checks"
                    />
                    <Metric
                      name="Waiting for you"
                      value={summary?.approvals_waiting || 0}
                      note="Scoped operator approvals"
                    />
                  </div>
                  <div className="section-heading">
                    <div>
                      <span className="eyebrow">LIVE SIGNALS</span>
                      <h2>Health is more than a green homepage.</h2>
                    </div>
                    <button
                      className="inline-link"
                      onClick={() => setProjectEdit("new")}
                    >
                      <Plus size={15} />
                      Connect project
                    </button>
                  </div>
                  <div className="signal-grid">
                    {projects.map((p) => (
                      <SignalCard
                        key={p.project.id}
                        signal={p}
                        onManage={() => {
                          navigate("projects");
                        }}
                      />
                    ))}
                    {!projects.length && (
                      <div className="card">
                        <Empty
                          title="Connect your first project"
                          action="Connect project"
                          onAction={() => setProjectEdit("new")}
                        >
                          Monitor real service health and business workflows
                          from one workspace.
                        </Empty>
                      </div>
                    )}
                  </div>
                  <div className="dashboard-bottom">
                    <section className="card queue-card">
                      <div className="section-title">
                        <div>
                          <span className="eyebrow">RECOVERY QUEUE</span>
                          <h2>What happened. What happens next.</h2>
                        </div>
                        <button
                          className="inline-link"
                          onClick={() => navigate("incidents")}
                        >
                          All incidents
                          <ArrowRight size={14} />
                        </button>
                      </div>
                      {data.incidents.length ? (
                        <IncidentList
                          incidents={data.incidents.slice(0, 5)}
                          onSelect={open}
                          compact
                        />
                      ) : (
                        <Empty
                          title="No incidents recorded"
                          action="Rehearse a scenario"
                          onAction={() => navigate("demo")}
                        >
                          Monitoring creates the first incident when a real
                          signal crosses its contract.
                        </Empty>
                      )}
                    </section>
                    <section className="card proof-card">
                      <span className="proof-symbol">
                        <GitMark />
                      </span>
                      <span className="eyebrow">THE CTRLZ DIFFERENCE</span>
                      <h2>
                        A model proposes.
                        <br />
                        Your contract decides.
                      </h2>
                      <p>
                        Every strategy must earn the right to execute. Every
                        recovery must pass independent checks.
                      </p>
                      <div className="proof-stat">
                        <strong>{summary?.tool_executions || 0}</strong>
                        <span>
                          diagnostic tool results
                          <br />
                          persisted as evidence
                        </span>
                      </div>
                      <button
                        className="inline-link"
                        onClick={() => navigate("evidence")}
                      >
                        Explore the evidence
                        <ArrowRight size={14} />
                      </button>
                    </section>
                  </div>
                </>
              )}
              {page === "incidents" && (
                <>
                  <PageTitle
                    eyebrow="THE COMPLETE RECOVERY RECORD"
                    heading="Every incident has a story."
                    copy="Follow the evidence from the first signal to the last independent check."
                  />
                  <section className="card">
                    <div className="list-toolbar">
                      <div className="segmented" aria-label="Filter incidents">
                        {[
                          ["all", "All incidents"],
                          ["active", "Active"],
                          ["approval", "Needs approval"],
                          ["resolved", "Verified"],
                        ].map(([id, name]) => (
                          <button
                            aria-pressed={filter === id}
                            className={filter === id ? "selected" : ""}
                            key={id}
                            onClick={() => setFilter(id)}
                          >
                            {name}
                          </button>
                        ))}
                      </div>
                      <label className="search-field">
                        <Search size={16} />
                        <input
                          aria-label="Search incidents"
                          placeholder="Search projects or incident IDs"
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                        />
                      </label>
                    </div>
                    {data.incidents.filter(
                      (i) =>
                        (filter === "all" ||
                          (filter === "active" && i.status !== "resolved") ||
                          (filter === "approval" &&
                            i.status === "awaiting_approval") ||
                          (filter === "resolved" &&
                            i.status === "resolved" &&
                            i.verification?.passed)) &&
                        `${i.project_id} ${i.id} ${title(i)}`
                          .toLowerCase()
                          .includes(query.toLowerCase()),
                    ).length ? (
                      <IncidentList
                        incidents={data.incidents.filter(
                          (i) =>
                            (filter === "all" ||
                              (filter === "active" &&
                                i.status !== "resolved") ||
                              (filter === "approval" &&
                                i.status === "awaiting_approval") ||
                              (filter === "resolved" &&
                                i.status === "resolved" &&
                                i.verification?.passed)) &&
                            `${i.project_id} ${i.id} ${title(i)}`
                              .toLowerCase()
                              .includes(query.toLowerCase()),
                        )}
                        onSelect={open}
                      />
                    ) : (
                      <Empty title="No incidents in this view">
                        Try another filter, or let the monitor detect a new
                        incident.
                      </Empty>
                    )}
                  </section>
                </>
              )}
              {page === "projects" && (
                <>
                  <PageTitle
                    eyebrow="INDEPENDENT APPLICATIONS"
                    heading="Their systems. Your control."
                    copy="Each project has its own signals, permissions and recovery contract."
                    action={
                      <button
                        className="button primary"
                        onClick={() => setProjectEdit("new")}
                      >
                        <Plus size={16} />
                        Connect project
                      </button>
                    }
                  />
                  <div className="project-grid">
                    {projects.map((p) => (
                      <section
                        className="card project-panel"
                        key={p.project.id}
                      >
                        <SignalCard
                          signal={p}
                          nested
                          onManage={() => setProjectEdit(p.project)}
                        />
                        <div className="contract-summary">
                          <h3>
                            <ShieldCheck size={16} />
                            Recovery contract
                          </h3>
                          <div className="operation-chips">
                            {p.project.contract.allowed.map((op) => (
                              <code key={op}>{op}</code>
                            ))}
                          </div>
                          <p>
                            Approval required:{" "}
                            {p.project.contract.approval_required.join(", ") ||
                              "None of the permitted operations"}
                          </p>
                          <div className="project-actions">
                            <button
                              className="button secondary"
                              onClick={() => setProjectEdit(p.project)}
                            >
                              <Settings size={14} />
                              Project settings
                            </button>
                            <button
                              className="inline-link"
                              onClick={() => {
                                setQuery(p.project.id);
                                setFilter("all");
                                navigate("incidents");
                              }}
                            >
                              View incidents
                              <ArrowRight size={14} />
                            </button>
                          </div>
                        </div>
                      </section>
                    ))}
                  </div>
                  {!projects.length && (
                    <section className="card">
                      <Empty
                        title="Your applications belong here"
                        action="Connect project"
                        onAction={() => setProjectEdit("new")}
                      >
                        Keep recovery decisions governed by a project-specific
                        contract.
                      </Empty>
                    </section>
                  )}
                </>
              )}
              {page === "demo" && (
                <DemoLab
                  projects={projects}
                  runs={data.runs}
                  enabled={!!data.runtime?.demo_controls_enabled}
                  token={token}
                  busy={busy}
                  act={act}
                  open={open}
                  onEnable={setProjectEdit}
                />
              )}
              {page === "continuity" && (
                <>
                  <PageTitle
                    eyebrow="VERIFIED REPOSITORY REPAIR"
                    heading="Bring a broken repo. Leave with proof."
                    copy="Python, JavaScript or TypeScript. Reproduce the regression, repair it in isolation, and inspect every result."
                  />
                  <div className="continuity-layout">
                    <ContinuationForm
                      token={token}
                      act={act}
                      busy={busy}
                      open={open}
                    />
                    <aside className="card continuity-guide">
                      <div className="guide-icon">
                        <Code2 size={24} />
                      </div>
                      <h2>
                        Repository in.
                        <br />A tested change out.
                      </h2>
                      <ol>
                        {[
                          [
                            "Inspect",
                            "Import the repository and automatically run its existing tests. Extra context is optional.",
                          ],
                          [
                            "Isolate",
                            "Reproduce acceptance failures in a detached Git worktree and Docker sandbox.",
                          ],
                          [
                            "Fix",
                            "Review the failures and click Fix failing code to start the repair.",
                          ],
                          [
                            "Prove",
                            "Run the same tests. Keep failed attempts. Download verified repaired code, a patch and test evidence.",
                          ],
                        ].map(([heading, copy], index) => (
                          <li key={heading}>
                            <span>{index + 1}</span>
                            <div>
                              <h3>{heading}</h3>
                              <p>{copy}</p>
                            </div>
                          </li>
                        ))}
                      </ol>
                      <div className="guide-note">
                        <ShieldCheck size={16} />
                        Your original branch stays untouched.
                      </div>
                    </aside>
                  </div>
                </>
              )}
              {page === "evidence" && (
                <>
                  <PageTitle
                    eyebrow="OUTCOMES YOU CAN INSPECT"
                    heading="The proof travels with you."
                    copy="A recovery receipt connects the incident, rejected alternatives, executed actions and acceptance checks."
                  />
                  <div className="metrics-grid three">
                    <Metric
                      name="Verified outcomes"
                      value={summary?.verified_recoveries || 0}
                      note="Backed by acceptance results"
                      accent
                    />
                    <Metric
                      name="Verified workflows"
                      value={summary?.verified_workflows || 0}
                      note="Entitlement and job assertions passed"
                    />
                    <Metric
                      name="Recorded tool results"
                      value={summary?.tool_executions || 0}
                      note="Returned evidence, not model confidence"
                    />
                  </div>
                  <section className="card">
                    <div className="section-title">
                      <h2>Recovery receipts</h2>
                      <span className="source-label">
                        JSON + readable brief + snapshot checksum
                      </span>
                    </div>
                    {data.incidents.length ? (
                      <IncidentList
                        incidents={data.incidents}
                        onSelect={open}
                      />
                    ) : (
                      <Empty title="Proof starts with a real incident">
                        Receipts appear as actual investigations are recorded.
                      </Empty>
                    )}
                  </section>
                  <div className="principles-grid">
                    {[
                      [
                        "Evidence over confidence",
                        "The displayed metrics are computed from persisted events. No estimated time or money saved.",
                      ],
                      [
                        "Checks over claims",
                        "An LLM cannot mark its own repair successful. Tests and system assertions make that decision.",
                      ],
                      [
                        "A history you can share",
                        "Download the complete JSON or a readable Markdown brief. Snapshot checksums identify exactly which JSON was exported.",
                      ],
                    ].map(([heading, copy]) => (
                      <article key={heading}>
                        <ShieldCheck size={19} />
                        <h3>{heading}</h3>
                        <p>{copy}</p>
                      </article>
                    ))}
                  </div>
                </>
              )}
              {page === "settings" && (
                <>
                  <PageTitle
                    eyebrow="WORKSPACE CONFIGURATION"
                    heading="Know what’s connected."
                    copy="Runtime configuration and capability boundaries, without exposing credentials."
                  />
                  <RuntimeStatus token={token} />
                  <AccountSettings token={token} admin={account?.role === "admin"} signedOut={disconnect} />
                  <div className="settings-grid">
                    <section className="card">
                      <h2>Reasoning and access</h2>
                      <dl className="settings-list">
                        <div>
                          <dt>Provider</dt>
                          <dd>{data.runtime?.provider || "Temporarily unavailable"}</dd>
                        </div>
                        <div>
                          <dt>Selected model</dt>
                          <dd>
                            <code>
                              {data.runtime ? data.runtime.model || "Not configured" : "Temporarily unavailable"}
                            </code>
                          </dd>
                        </div>
                        <div>
                          <dt>NVIDIA key</dt>
                          <dd>
                            <Badge
                              state={
                                !data.runtime ? "unknown" : data.runtime.nim_configured
                                  ? "healthy"
                                  : "blocked"
                              }
                            >
                              {!data.runtime ? "Unknown" : data.runtime.nim_configured
                                ? "Present"
                                : "Missing"}
                            </Badge>
                          </dd>
                        </div>
                        <div>
                          <dt>Updates</dt>
                          <dd>{words(data.connection)}</dd>
                        </div>
                        <div>
                          <dt>Rehearsal controls</dt>
                          <dd>
                            {!data.runtime ? "Temporarily unavailable" : data.runtime.demo_controls_enabled
                              ? "Enabled; project opt-in required"
                              : "Disabled"}
                          </dd>
                        </div>
                      </dl>
                      <p className="subtle">
                        Key presence is not a provider authentication check.
                        Credentials remain in backend configuration.
                      </p>
                      <QualitySetting />
                      <button className="button secondary" onClick={disconnect}>
                        <LogOut size={15} />
                        Disconnect session
                      </button>
                    </section>
                    <section className="card deployment-card">
                      <span className="eyebrow">DEPLOYMENT PREPARATION</span>
                      <h2>Ready for the next step.</h2>
                      <p>
                        The deployment checklist lives with the source so the
                        release is reviewable and repeatable.
                      </p>
                      <ul>
                        <li>
                          <Check size={15} />
                          Independent repositories and Docker images
                        </li>
                        <li>
                          <Check size={15} />
                          Persistent databases and same-origin API proxy
                        </li>
                        <li>
                          <Check size={15} />
                          Server-side credentials and explicit approvals
                        </li>
                        <li>
                          <span className="pending-dot" />
                          Hosting, domains and public URLs still to verify
                        </li>
                      </ul>
                      <div className="guide-note">
                        Current connection: {window.location.host}
                      </div>
                      <small>
                        A public demo deployment does not make this a
                        multi-tenant production service.
                      </small>
                    </section>
                  </div>
                </>
              )}
            </>
          )}
          <footer className="workspace-footer">
            <span>
              <ShieldCheck size={13} />
              EVIDENCE BEFORE CONFIDENCE.
            </span>
            <span>
              CtrlZ <b>/</b> Recovery for every team <b>/</b> 2026
            </span>
          </footer>
        </main>
      </div>
      {projectEdit && (
        <ProjectDialog
          project={projectEdit}
          busy={busy}
          onClose={closeProject}
          onSubmit={async (p) => {
            const ok = await act(
              () => api("/projects", token, p),
              "Project configuration saved",
            );
            if (ok) closeProject();
          }}
        />
      )}
    </div>
  );
}
function GitMark() {
  return <span aria-hidden="true">⌘</span>;
}

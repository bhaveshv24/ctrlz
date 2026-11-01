import { useEffect, useState } from "react";
import { FilePlate } from "./FilePlate";
import RepoIntelligence from "./RepoIntelligence";
import RepositoryInspection, {type InspectionReport} from "./RepositoryInspection";
import {
  Code2,
  ArrowRight,
  LoaderCircle,
  ShieldCheck,
  FolderGit2,
  Upload,
  Bug,
  Sparkles,
} from "lucide-react";
import RepositoryCheckGuide from "./RepositoryCheckGuide";
import { repositoryAction } from "../repository-action";
import { api, ApiError, API, saveFile, type Incident, type Act } from "../api";

type Assessment = {
  check_commands?: {setup:string;test:string;basis:string};
  files?: string[];
  repository: string;
  profile: string;
  profile_label: string;
  supported: boolean;
  tests: string[];
  test_file_count: number;
  source_count: number;
  editable_files: string[];
  file_count: number;
  dependencies: string[];
  dependency_install_required: boolean;
  warnings: string[];
  provenance?: { kind: string; url?: string; upstream_commit?: string; subdirectory?: string };
  omitted_files?: string[];
};
type Diagnosis = {
  inspection?: InspectionReport;
  status: "failing" | "healthy" | "blocked";
  message: string;
  passed: number;
  failed: number;
  skipped: number;
  baseline: { output: string; cases: { id: string; status: string; detail: string }[] };
};
export default function ContinuationForm({
  token,
  act,
  busy,
  open,
}: {
  token: string;
  act: Act;
  busy: boolean;
  open: (id: string) => void;
}) {
  const [mode, setMode] = useState<"repair" | "complete" | null>(null);
  const [kind, setKind] = useState("github"),
    [source, setSource] = useState(""),
    [file, setFile] = useState<File | null>(null),
    [snapshot, setSnapshot] = useState<Assessment | null>(null),
    [requirements, setRequirements] = useState(""),
    [context, setContext] = useState(""),
    [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null);
  const [scanning, setScanning] = useState(false);
  const [inspectionError, setInspectionError] = useState("");
  const [executionEnabled, setExecutionEnabled] = useState(false);
  const [executionReason, setExecutionReason] = useState("Checking isolated runner availability…");
  useEffect(() => {
    api<{code_execution_enabled: boolean; execution_reason?: string}>("/capabilities",token).then(c => { setExecutionEnabled(c.code_execution_enabled); setExecutionReason(c.execution_reason || "Running repairs requires a Docker-capable backend."); }).catch(() => { setExecutionEnabled(false); setExecutionReason("Runner availability could not be checked. Retry when the backend is reachable; static inspection remains available."); });
  }, [token]);
  const reset = () => {
    setSnapshot(null);
    setDiagnosis(null);
    setInspectionError("");
  };
  const scan = async (assessment: Assessment) => {
    setDiagnosis(null);
    setScanning(true);
    setInspectionError("");
    try {
      const result = await api<Diagnosis>("/repositories/audit", token, {
        repository: assessment.repository,
        acceptance_profile: assessment.profile,
        install_dependencies: true,
      }, AbortSignal.timeout(360000));
      setDiagnosis(result);
    } catch (error) {
      const message = error instanceof ApiError && error.status === 404
        ? "The deployed backend does not provide repository inspection yet. Deploy the latest backend on Render, then retry inspection."
        : error instanceof Error ? error.message : "Repository inspection failed. Please retry.";
      setInspectionError(message);
      throw error;
    } finally {
      setScanning(false);
    }
  };
  const action = repositoryAction(mode || "repair", diagnosis?.status || null, executionEnabled, !!snapshot?.supported, !!inspectionError);
  if (!mode) return (
    <section className="repository-mode-picker">
      <h2>What would you like to do?</h2>
      <p className="muted">Bring your repository. Choose the kind of help you need.</p>
      <div className="repository-mode-grid">
        <button type="button" className="repository-mode-card" disabled={busy} onClick={() => { setMode("repair"); reset(); }}>
          <Bug size={28} aria-hidden="true" />
          <strong>Debug & fix errors</strong>
          <span>Find failing tests, repair the cause, and download the tested code.</span>
          <span className="repository-mode-action">Fix my repository <ArrowRight size={16} /></span>
        </button>
        <button type="button" className="repository-mode-card" disabled={busy} onClick={() => { setMode("complete"); reset(); }}>
          <Sparkles size={28} aria-hidden="true" />
          <strong>Complete an unfinished project</strong>
          <span>Import your work, describe what is missing, and build on the existing source.</span>
          <span className="repository-mode-action">Continue my project <ArrowRight size={16} /></span>
        </button>
      </div>
    </section>
  );
  return (
    <form
      className="card continuation-form"
      onSubmit={(e) => {
        e.preventDefault();
        act(async () => {
          if (!snapshot) {
            let imported: Assessment;
            if (kind === "zip") {
              if (!file) throw new Error("Choose a repository ZIP first.");
              if (file.size > 25 * 1024 * 1024)
                throw new Error("ZIP uploads must be under 25 MiB.");
              const response = await fetch(API + "/repositories/upload", {
                signal: AbortSignal.timeout(90000),
                method: "POST",
                headers: {
                  Authorization: "Bearer " + token,
                  "Content-Type": "application/zip",
                },
                body: file,
              });
              const data = await response.json().catch(() => { throw new Error("The server could not process the ZIP upload. Please try again."); });
              if (!response.ok)
                throw new Error(
                  typeof data.detail === "string"
                    ? data.detail
                    : "Could not import ZIP",
                );
              imported = data;
            } else
              imported = await api<Assessment>("/repositories/import", token, {
                kind,
                source,
              });
            setSnapshot(imported);
            await scan(imported);
          } else if (!action.startsChanges) {
            await scan(snapshot);
          } else {
            const i = await api<Incident>("/continuations", token, {
              repository: snapshot.repository,
              mode,
              ...(requirements.trim() ? { requirements: requirements.trim() } : {}),
              context,
              acceptance_profile: snapshot.profile,
              install_dependencies: true,
            });
            open(i.id);
          }
        });
      }}
    >
      <button className="inline-link" type="button" disabled={busy} onClick={() => setMode(null)}>← Choose a different goal</button>
      {!executionEnabled && <p role="status" className="alert">{executionReason}</p>}
      <span className="eyebrow">
        {snapshot ? (mode === "complete" ? "03 / DESCRIBE THE FINISH LINE" : "02 / AUTOMATIC DIAGNOSIS") : "02 / BRING A REPOSITORY"}
      </span>
      <h2>
        {mode === "complete" ? (snapshot ? "What should we finish?" : "Pick up where you left off.") : snapshot
          ? "Evidence first. Then fix."
          : "Your repo. Your acceptance tests."}
      </h2>
      <p className="muted">
        {mode === "complete" ? "Import your project, then describe the missing features or unfinished work. CtrlZ proposes source changes and runs the existing tests." : "Connect a repository. CtrlZ runs its existing tests automatically, then offers a fix for reproduced failures."}
      </p>
      <RepoIntelligence
        token={token}
        repository={
          kind === "github" ? source : snapshot?.provenance?.url || ""
        }
        assessment={snapshot}
        onPrefill={(text) =>
          setRequirements((previous) =>
            previous ? previous + "\n\n" + text : text,
          )
        }
      />
      {!snapshot && <p className="muted">Inspect checks source risks, known dependency advisories and repository readiness. Only resolved package names and versions are sent to OSV. Supported tests run in isolation when a runner is available; your source stays unchanged.</p>}
      {!snapshot ? (
        <>
          <label>
            Repository source
            <select
              value={kind}
              onChange={(e) => {
                setKind(e.target.value);
                setSource("");
                reset();
              }}
            >
              <option value="github">Public GitHub repository</option>
              <option value="zip">Upload a ZIP snapshot</option>
            </select>
          </label>
          {kind === "zip" ? (
            <label>
              Repository ZIP
              <input
                type="file"
                accept=".zip,application/zip"
                required
                onChange={(e) => {
                  setFile(e.target.files?.[0] || null);
                  reset();
                }}
              />
              <small>
                25 MiB upload / 64 MiB expanded / 3,000 files maximum. Include
                existing tests and dependency lockfiles.
              </small>
            </label>
          ) : (
            <>
              <label>
                Public GitHub URL
                <input
                  type="text"
                  required
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  placeholder="https://github.com/owner/repository"
                />
                <small>
                  Public HTTPS repositories only. Private credentials are never requested.
                </small>
              </label>
            </>
          )}
          <div className="form-note">
            <ShieldCheck size={18} />
            <span>
              Source is copied into a clean managed Git snapshot. Common
              secrets, databases, installed dependencies and build caches are
              excluded. Tests run only in Docker.
            </span>
          </div>
          <button className="button primary" disabled={busy}>
            {busy ? (
              <LoaderCircle size={16} className="spin" />
            ) : kind === "zip" ? (
              <Upload size={16} />
            ) : (
              <FolderGit2 size={16} />
            )}
            Inspect repository
            <ArrowRight size={15} />
          </button>
        </>
      ) : (
        <>
          {mode === "complete" && <label className="completion-prompt">
            What would you like completed? <span className="completion-required">Required</span>
            <textarea rows={6} value={requirements} onChange={e => setRequirements(e.target.value)} required minLength={10} maxLength={20000}
              placeholder="Describe what already works, what is unfinished, and how the finished feature should behave. For example: finish the task filters, connect them to the existing API, and show clear empty and error states." />
            <small>Be specific about the expected result. Existing tests check regressions; review the generated changes against your prompt. This flow needs a supported test setup and preserves tests, dependency manifests and configuration.</small>
          </label>}
          <p className="form-note">The download contains the imported source{snapshot.provenance?.subdirectory ? `, with ${snapshot.provenance.subdirectory} repaired in its original location` : " at the repository root"}. A separate frontend repository is not added automatically. Dependencies, secrets and build caches are excluded.</p>
          <details className="repository-disclosure" open={!snapshot.supported}>
            <summary>Repository files & detected test setup (optional)</summary>
          <FilePlate inspection={snapshot} />
          <div className="repository-assessment" role="status">
            <div className="row-between">
              <strong>{snapshot.profile_label}</strong>
              <span
                className={`badge ${snapshot.supported ? "green" : "amber"}`}
              >
                {snapshot.supported ? "Profile detected" : "Needs preparation"}
              </span>
            </div>
            <p>
              {snapshot.file_count} files / {snapshot.test_file_count}{" "}
              acceptance {snapshot.test_file_count === 1 ? "file" : "files"} ·{" "}
              {snapshot.source_count} source{" "}
              {snapshot.source_count === 1 ? "file" : "files"}
            </p>
            <small>
              Snapshot: {snapshot.repository.split("/").pop()}
              {snapshot.provenance?.upstream_commit
                ? " / upstream " +
                  snapshot.provenance.upstream_commit.slice(0, 10)
                : ""}
            </small>
            {snapshot.warnings.map((w) => (
              <p key={w} className="import-warning">
                {w}
              </p>
            ))}
            {Boolean(snapshot.omitted_files?.length) && (
              <p>
                {snapshot.omitted_files?.length} sensitive files excluded from
                the snapshot.
              </p>
            )}
            <details>
              <summary>Acceptance files & dependency plan</summary>
              <ul>
                {snapshot.tests.slice(0, 15).map((p) => (
                  <li key={p}>
                    <code>{p}</code>
                  </li>
                ))}
              </ul>
              <p>
                {snapshot.dependencies.length
                  ? snapshot.dependencies.join(", ")
                  : "No third-party dependency setup required."}
              </p>
            </details>
          </div>
          </details>
          <button
            className="inline-link"
            type="button"
            onClick={reset}
            disabled={busy}
          >
            Choose another repository
          </button>
          <section aria-live="polite" className="repository-assessment repository-results">
            <h3>{scanning ? "Inspecting source, dependencies and tests…" : diagnosis ? (mode === "complete" && diagnosis.status === "healthy" && diagnosis.inspection?.summary !== "review_required" ? "Baseline tests pass. Ready to continue your project." : diagnosis.message) : inspectionError ? "Inspection could not finish" : "Repository imported. Inspection is ready."}</h3>
            {inspectionError && <p role="alert" className="alert">{inspectionError}</p>}
            {!scanning && !inspectionError && diagnosis?.status === "healthy" && mode === "repair" && <p>The existing tests passed, so there is no reproduced test failure to repair. Review the inspection findings, or choose project completion to request missing functionality.</p>}
            {scanning && <p className="muted">Checking source risks and dependency advisories, then running supported tests in isolation. This can take a few minutes.</p>}
            {diagnosis?.inspection && <RepositoryInspection report={diagnosis.inspection} />}
            {diagnosis && (!diagnosis.inspection || ["healthy", "failing"].includes(diagnosis.inspection.tests.state)) && <>
              <p>{diagnosis.passed} passed / {diagnosis.failed} failed / {diagnosis.skipped} skipped</p>
              <button type="button" className="button secondary" onClick={() => saveFile("ctrlz-errors-before-repair.txt", [
                "CtrlZ — Tests before repair", `Result: ${diagnosis.status}`,
                `${diagnosis.passed} passed / ${diagnosis.failed} failed / ${diagnosis.skipped} skipped`,
                "", ...diagnosis.baseline.cases.filter(c => c.status === "failed" || c.status === "error").map(c => `${c.id}\n${c.detail || ""}`),
                "", "Original test output:", diagnosis.baseline.output,
              ].join("\n"), "text/plain;charset=utf-8")}>Download errors before repair</button>
              {diagnosis.baseline.cases.filter(c => c.status === "failed" || c.status === "error").map(c =>
                <details key={c.id}><summary>{c.id}</summary><pre className="patch-view">{c.detail}</pre></details>
              )}
              {(mode === "complete" || diagnosis.status === "failing") && <RepositoryCheckGuide commands={snapshot.check_commands} profile={snapshot.profile} completion={mode === "complete"} baselineRecorded={true} requirement={requirements} failures={diagnosis.baseline.cases.filter(c => c.status === "failed" || c.status === "error")} />}
              <details><summary>Full test output</summary><pre className="patch-view">{diagnosis.baseline.output}</pre></details>
            </>}
          </section>
          <details className="repository-disclosure">
            <summary>Additional instructions (optional)</summary>
            {mode === "repair" && <label>
              Intended behavior
              <textarea rows={3} value={requirements} onChange={e => setRequirements(e.target.value)} minLength={10} maxLength={20000}
                placeholder="Only needed for behavior the existing tests do not describe." />
            </label>}
            <label>
              Additional context
              <textarea rows={3} value={context} onChange={e => setContext(e.target.value)} maxLength={20000}
                placeholder="Optional logs or constraints." />
            </label>
          </details>
          <div className="form-note">
            <ShieldCheck size={18} />
            <span>
              Up to three attempts. Tests, manifests and configuration stay
              immutable. A verified result includes a repaired repository ZIP, a patch, and test evidence. Applying and deploying it remain separate actions.
            </span>
          </div>
          <div className="repository-form-actions">
          {diagnosis?.inspection && <button type="button" className="button secondary" disabled={busy} onClick={() => act(() => scan(snapshot))}>Inspect again</button>}
          <button
            className="button primary"
            disabled={
              busy || scanning || action.disabled
            }
          >
            {busy ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <Code2 size={16} />
            )}
            {busy ? (scanning ? "Inspecting & running tests…" : mode === "complete" ? "Starting project completion…" : "Starting repair…") : action.label}
            <ArrowRight size={15} />
          </button>
          </div>
        </>
      )}
    </form>
  );
}

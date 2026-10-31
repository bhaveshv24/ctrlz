import { useEffect, useState } from "react";
import { FilePlate } from "./FilePlate";
import RepoIntelligence from "./RepoIntelligence";
import {
  Code2,
  ArrowRight,
  LoaderCircle,
  ShieldCheck,
  FolderGit2,
  Upload,
} from "lucide-react";
import { api, API, type Incident, type Act } from "../api";

type Assessment = {
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
  provenance?: { kind: string; url?: string; upstream_commit?: string };
  omitted_files?: string[];
};
type Diagnosis = {
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
  const [kind, setKind] = useState("github"),
    [source, setSource] = useState(""),
    [subdirectory, setSubdirectory] = useState(""),
    [file, setFile] = useState<File | null>(null),
    [snapshot, setSnapshot] = useState<Assessment | null>(null),
    [requirements, setRequirements] = useState(""),
    [context, setContext] = useState(""),
    [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null);
  const [scanning, setScanning] = useState(false);
  const [executionEnabled, setExecutionEnabled] = useState(true);
  useEffect(() => {
    api<{code_execution_enabled: boolean}>("/capabilities",token).then(c => setExecutionEnabled(c.code_execution_enabled)).catch(() => {});
  }, [token]);
  const reset = () => {
    setSnapshot(null);
    setDiagnosis(null);
  };
  const scan = async (assessment: Assessment) => {
    setDiagnosis(null);
    setScanning(true);
    try {
      const result = await api<Diagnosis>("/repositories/diagnose", token, {
        repository: assessment.repository,
        acceptance_profile: assessment.profile,
        install_dependencies: true,
      });
      setDiagnosis(result);
    } finally {
      setScanning(false);
    }
  };
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
              const response = await fetch(API + "/repositories/upload?subdirectory=" + encodeURIComponent(subdirectory), {
                method: "POST",
                headers: {
                  Authorization: "Bearer " + token,
                  "Content-Type": "application/zip",
                },
                body: file,
              });
              const data = await response.json();
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
                subdirectory,
              });
            setSnapshot(imported);
            if (imported.supported && executionEnabled) await scan(imported);
          } else if (!diagnosis || diagnosis.status !== "failing") {
            await scan(snapshot);
          } else {
            const i = await api<Incident>("/continuations", token, {
              repository: snapshot.repository,
              ...(requirements.trim() ? { requirements } : {}),
              context,
              acceptance_profile: snapshot.profile,
              install_dependencies: true,
            });
            open(i.id);
          }
        });
      }}
    >
      {!executionEnabled && <p role="status" className="alert">This host supports repository inspection. Running repairs requires the Docker-capable runner deployment.</p>}
      <span className="eyebrow">
        {snapshot ? "02 / AUTOMATIC DIAGNOSIS" : "01 / BRING A REPOSITORY"}
      </span>
      <h2>
        {snapshot
          ? "Evidence first. Then fix."
          : "Your repo. Your acceptance tests."}
      </h2>
      <p className="muted">
        Connect a repository. CtrlZ runs its existing tests automatically, then offers a fix for reproduced failures.
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
      {!snapshot && <p className="muted">Inspection runs tests in an isolated container and downloads declared dependencies without install scripts. Your original folder stays unchanged.</p>}
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
              <option value="local">Folder on the CtrlZ server</option>
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
                25 MiB upload · 64 MiB expanded · 3,000 files maximum. Include
                existing tests and dependency lockfiles.
              </small>
            </label>
          ) : (
            <>
              <label>
                {kind === "github" ? "Public GitHub URL" : "Server folder path"}
                <input
                  type="text"
                  required
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  placeholder={
                    kind === "github"
                      ? "https://github.com/owner/repository"
                      : "/absolute/path/to/project"
                  }
                />
                <small>
                  {kind === "github"
                    ? "Public HTTPS repositories only. Private credentials are never requested."
                    : "The folder must be inside the server’s configured source roots. Your original folder stays untouched."}
                </small>
              </label>
              <label>
                Package subdirectory <span className="optional">optional</span>
                <input
                  value={subdirectory}
                  onChange={(e) => setSubdirectory(e.target.value)}
                  placeholder="packages/my-service"
                />
                <small>Choose the package to test and repair, such as backend. The download preserves the full imported repository, including its frontend. A backend-only repository cannot include a separate frontend repository.</small>
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
          {kind === "zip" && <label>Package subdirectory <span className="optional">optional</span>
            <input value={subdirectory} onChange={e => setSubdirectory(e.target.value)} placeholder="backend" />
            <small>Upload the full repository ZIP and select the package to repair. The download includes the full imported source, including the frontend.</small>
          </label>}
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
          <details open={!snapshot.supported}>
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
              {snapshot.file_count} files · {snapshot.test_file_count}{" "}
              acceptance {snapshot.test_file_count === 1 ? "file" : "files"} ·{" "}
              {snapshot.source_count} source{" "}
              {snapshot.source_count === 1 ? "file" : "files"}
            </p>
            <small>
              Snapshot: {snapshot.repository.split("/").pop()}
              {snapshot.provenance?.upstream_commit
                ? " · upstream " +
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
          <section aria-live="polite" className="repository-assessment">
            <h3>{scanning ? "Running repository tests…" : diagnosis ? diagnosis.message : "Ready to run the existing tests"}</h3>
            {scanning && <p className="muted">Preparing declared dependencies and collecting real failures. This can take a few minutes.</p>}
            {diagnosis && <>
              <p>{diagnosis.passed} passed · {diagnosis.failed} failed · {diagnosis.skipped} skipped</p>
              {diagnosis.baseline.cases.filter(c => c.status === "failed" || c.status === "error").map(c =>
                <details key={c.id}><summary>{c.id}</summary><pre className="patch-view">{c.detail}</pre></details>
              )}
              <details><summary>Full test output</summary><pre className="patch-view">{diagnosis.baseline.output}</pre></details>
            </>}
          </section>
          <details>
            <summary>Additional instructions (optional)</summary>
            <label>
              Intended behavior
              <textarea rows={3} value={requirements} onChange={e => setRequirements(e.target.value)} minLength={10} maxLength={20000}
                placeholder="Only needed for behavior the existing tests do not describe." />
            </label>
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
          <button
            className="button primary"
            disabled={
              busy ||
              !snapshot.supported || !executionEnabled
            }
          >
            {busy ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <Code2 size={16} />
            )}
            {busy ? (scanning ? "Inspecting & running tests…" : "Starting repair…") : diagnosis?.status === "failing" ? "Fix failing code" : "Run tests again"}
            <ArrowRight size={15} />
          </button>
        </>
      )}
    </form>
  );
}

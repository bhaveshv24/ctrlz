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
    [model, setModel] = useState(""),
    [approve, setApprove] = useState(false);
  const [executionEnabled, setExecutionEnabled] = useState(true);
  useEffect(() => {
    api<{code_execution_enabled: boolean}>("/capabilities",token).then(c => setExecutionEnabled(c.code_execution_enabled)).catch(() => {});
  }, [token]);
  const reset = () => {
    setSnapshot(null);
    setApprove(false);
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
              const response = await fetch(API + "/repositories/upload", {
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
            setApprove(false);
          } else {
            const i = await api<Incident>("/continuations", token, {
              repository: snapshot.repository,
              requirements,
              context,
              model: model.trim() || null,
              acceptance_profile: snapshot.profile,
              install_dependencies: approve,
            });
            open(i.id);
          }
        });
      }}
    >
      {!executionEnabled && <p role="status" className="alert">This host supports repository inspection. Running repairs requires the Docker-capable runner deployment.</p>}
      <span className="eyebrow">
        {snapshot ? "02 / REPRODUCE & REPAIR" : "01 / BRING A REPOSITORY"}
      </span>
      <h2>
        {snapshot
          ? "A clear boundary. A testable fix."
          : "Your repo. Your acceptance tests."}
      </h2>
      <p className="muted">
        Import a snapshot, reproduce the failure, and review a patch backed by
        the same tests.
      </p>
      <label>Alternative NVIDIA NIM model (optional)
        <input value={model} onChange={e => setModel(e.target.value)} placeholder="Use the configured default, or enter provider/model" pattern="[a-zA-Z0-9_./\-]+" maxLength={150} />
        <small>The selected model uses the server’s NVIDIA credentials. Provider availability is checked when reasoning runs.</small>
      </label>
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
          <button
            className="inline-link"
            type="button"
            onClick={reset}
            disabled={busy}
          >
            Choose another repository
          </button>
          <label>
            What is broken?
            <textarea
              rows={4}
              value={requirements}
              onChange={(e) => setRequirements(e.target.value)}
              minLength={10}
              maxLength={20000}
              required
              placeholder="Describe the failure, intended behavior, and the existing tests that should pass."
            />
          </label>
          <label>
            Context to carry forward <span className="optional">optional</span>
            <textarea
              rows={3}
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="Relevant error logs, requirements, or an explicit conversation handoff."
            />
          </label>
          {snapshot.dependency_install_required && (
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={approve}
                onChange={(e) => setApprove(e.target.checked)}
              />
              <span>
                <strong>Allow isolated dependency setup</strong>
                <small>
                  Download declared packages in a credential-free container. npm
                  install scripts are disabled; Python uses binary wheels.
                  Baseline and candidate tests then run offline.
                </small>
              </span>
            </label>
          )}
          <div className="form-note">
            <ShieldCheck size={18} />
            <span>
              Up to three attempts. Tests, manifests and configuration stay
              immutable. A verified result is a reviewable patch; applying and
              deploying it remain separate actions.
            </span>
          </div>
          <button
            className="button primary"
            disabled={
              busy ||
              !snapshot.supported ||
              (snapshot.dependency_install_required && !approve)
            }
          >
            {busy ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <Code2 size={16} />
            )}
            Reproduce & repair
            <ArrowRight size={15} />
          </button>
        </>
      )}
    </form>
  );
}

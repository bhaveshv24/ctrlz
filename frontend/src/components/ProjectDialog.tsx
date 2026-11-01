import { useState } from "react";
import { ArrowRight } from "lucide-react";
import type { Project } from "../api";
import { Dialog } from "./ui";
import RuntimeProjectForm from "./RuntimeProjectForm";
const genericContract = {
  allowed: [],
  approval_required: [],
  max_actions: 3,
  invariants: ["no_destructive_operations", "idempotent_mutations"],
};
const campusContract = {
  allowed: ["restore_checkout", "resume_worker", "retry_order"],
  approval_required: ["resume_worker"],
  max_actions: 3,
  invariants: [
    "no_duplicate_entitlements",
    "no_destructive_operations",
    "idempotent_mutations",
  ],
};
export default function ProjectDialog({
  project,
  busy,
  onClose,
  onSubmit,
  submitError = "",
  token = "",
}: {
  submitError?: string;
  project: Project | "new";
  busy: boolean;
  onClose: () => void;
  onSubmit: (project: unknown) => Promise<void>;
  token?: string;
}) {
  const existing = project === "new" ? null : project;
  const [runtimeMode, setRuntimeMode] = useState(existing?.project_type === "repository-deployment");
  const [name, setName] = useState(existing?.name || ""),
    [id, setId] = useState(existing?.id || ""),
    [url, setUrl] = useState(existing?.base_url || ""),
    [enabled, setEnabled] = useState(existing?.enabled ?? true),
    [demo, setDemo] = useState(existing?.demo_enabled ?? false),
    [adapter, setAdapter] = useState(existing?.adapter || "generic-http-v1"),
    [tokenEnv, setTokenEnv] = useState(
      existing?.token_env || "SERVICE_RECOVERY_TOKEN",
    ),
    [integration, setIntegration] = useState(
      JSON.stringify(
        existing?.integration || { health_path: "/health", health_checks: [] },
        null,
        2,
      ),
    ),
    [contract, setContract] = useState(
      JSON.stringify(existing?.contract || genericContract, null, 2),
    ),
    [error, setError] = useState("");
  if (runtimeMode) return <RuntimeProjectForm submitError={submitError} project={existing} token={token} busy={busy} onClose={onClose} onBack={() => existing ? onClose() : setRuntimeMode(false)} onSubmit={onSubmit} />;
  return (
    <Dialog
      title={existing ? "Project settings" : "Connect a project"}
      onClose={onClose}
      busy={busy}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          try {
            const parsed = JSON.parse(integration),
              rules = JSON.parse(contract);
            setError("");
            onSubmit({
              ...existing,
              id,
              name,
              base_url: url,
              enabled,
              adapter,
              token_env: tokenEnv,
              demo_enabled: adapter === "campuspass-v1" && demo,
              integration: parsed,
              contract: rules,
            });
          } catch {
            setError(
              "Integration and recovery contract must contain valid JSON objects.",
            );
          }
        }}
      >
        <p className="dialog-copy">
          Monitor any HTTP service. Add named recovery operations and measurable
          acceptance checks when you want guarded automatic recovery.
        </p>
        <label>
          Integration
          <select
            value={adapter}
            onChange={(e) => {
              if (e.target.value === "runtime-v1") { setRuntimeMode(true); return; }
              const campus = e.target.value === "campuspass-v1";
              setAdapter(e.target.value);
              setContract(
                JSON.stringify(
                  campus ? campusContract : genericContract,
                  null,
                  2,
                ),
              );
              setTokenEnv(
                campus ? "CAMPUSPASS_RECOVERY_TOKEN" : "SERVICE_RECOVERY_TOKEN",
              );
              setIntegration(
                JSON.stringify(
                  { health_path: "/health", health_checks: [] },
                  null,
                  2,
                ),
              );
              setDemo(false);
            }}
          >
            <option value="generic-http-v1">Generic HTTP service</option>
            {!existing && <option value="runtime-v1">Repository + Deployment Monitoring</option>}
            <option value="campuspass-v1">
              CampusPass: optional demonstration preset
            </option>
          </select>
        </label>
        <div className="form-grid">
          <label>
            Project name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={100}
              placeholder="Your service"
            />
          </label>
          <label>
            Project ID
            <input
              value={id}
              onChange={(e) => setId(e.target.value)}
              required
              pattern="[a-z][a-z0-9_-]{0,40}"
              disabled={!!existing}
              placeholder="my-service"
            />
          </label>
        </div>
        <label>
          Backend origin
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
            placeholder="https://service.example.com"
          />
        </label>
        <label>
          Recovery token environment variable
          <input
            value={tokenEnv}
            onChange={(e) => setTokenEnv(e.target.value)}
            required
            pattern="[A-Z][A-Z0-9_]{0,80}"
          />
          <small>
            Set the secret on the CtrlZ server. Enter its variable name here,
            never the secret itself.
          </small>
        </label>
        {adapter === "generic-http-v1" && (
          <details className="integration-details">
            <summary>Health checks & recovery contract</summary>
            <p className="dialog-copy">
              The default observes GET /health and permits no mutations.
              Configure fixed same-origin paths, typed operation parameters,
              diagnostic preconditions and post-recovery assertions. See
              docs/PORTABILITY.md for a complete service example.
            </p>
            <label>
              HTTP integration JSON
              <textarea
                rows={9}
                value={integration}
                onChange={(e) => setIntegration(e.target.value)}
                spellCheck={false}
              />
            </label>
            <label>
              Recovery contract JSON
              <textarea
                rows={7}
                value={contract}
                onChange={(e) => setContract(e.target.value)}
                spellCheck={false}
              />
            </label>
          </details>
        )}
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
          />
          <span>
            <strong>Monitor this service</strong>
            <small>
              Observe its configured health and optional workflow consistency
              signals.
            </small>
          </span>
        </label>
        {adapter === "campuspass-v1" && (
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={demo}
              onChange={(e) => setDemo(e.target.checked)}
            />
            <span>
              <strong>Allow controlled demo faults</strong>
              <small>
                Only for a demonstration environment that separately enables
                fault injection.
              </small>
            </span>
          </label>
        )}
        {(error || submitError) && (
          <p role="alert" className="import-warning">
            {error || submitError}
          </p>
        )}
        <div className="dialog-actions">
          <button
            className="button secondary"
            type="button"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button className="button primary" disabled={busy}>
            {busy ? "Saving…" : "Save service"}
            <ArrowRight size={15} />
          </button>
        </div>
      </form>
    </Dialog>
  );
}

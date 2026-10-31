import { useState } from "react";
import { api } from "../api";

type ComponentStatus = {
  name: string;
  state: string;
  version?: string;
  detail?: string;
  verified?: boolean;
};

export default function RuntimeStatus({ token }: { token: string }) {
  const [components, setComponents] = useState<ComponentStatus[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function inspect() {
    setBusy(true);
    setError("");
    try {
      const result = await api<{ components: ComponentStatus[] }>(
        "/runtime",
        token,
      );
      setComponents(result.components);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card">
      <div className="row-between">
        <h2>Recovery runtime</h2>
        <button
          type="button"
          className="button secondary"
          disabled={busy}
          onClick={inspect}
        >
          {busy ? "Checking runtime…" : "Check runtime"}
        </button>
      </div>
      <p className="muted">
        Inspect installed services and sandbox availability. Provider
        credentials and webhook delivery are verified by recorded runs.
      </p>
      {error && <p role="alert">{error}</p>}
      <dl className="runtime-components" aria-live="polite">
        {components.map((component) => (
          <div key={component.name}>
            <dt>{component.name}</dt>
            <dd>
              <strong>{component.state}</strong>
              {component.version && " · " + component.version}
              {component.detail && <span>{component.detail}</span>}
              {component.verified === false && (
                <span>
                  Connection or delivery has not been tested by this check.
                </span>
              )}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

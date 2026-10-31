import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  stream,
  type DemoRun,
  type FlightEvent,
  type Incident,
  type Overview,
  type Runtime,
} from "../api";
import { loadWorkspace, loadWorkspaceMetadata } from "../control-center-data";
export function useControlCenter(token: string) {
  const [overview, setOverview] = useState<Overview | null>(null),
    [incidents, setIncidents] = useState<Incident[]>([]),
    [runtime, setRuntime] = useState<Runtime | null>(null),
    [runs, setRuns] = useState<DemoRun[]>([]),
    [events, setEvents] = useState<FlightEvent[]>([]),
    [ready, setReady] = useState(false),
    [loadedToken, setLoadedToken] = useState(""),
    [error, setError] = useState(""),
    [connection, setConnection] = useState("connecting");
  const cursor = useRef({ current: 0 }),
    activeToken = useRef(token),
    inflight = useRef<{token: string; promise: Promise<void>} | null>(null);
  activeToken.current = token;
  const refresh = useCallback(async () => {
    if (inflight.current?.token === token) return inflight.current.promise;
    const current = token;
    const operation = async () => {
      try {
        // Health can fail in the browser even when authenticated API reads succeed.
        // Start optional metadata in parallel; never make it a login prerequisite.
        void loadWorkspaceMetadata(current).then(({ runtime, runs }) => {
          if (activeToken.current !== current) return;
          setRuntime(runtime);
          setRuns(runs);
        });
        const { overview, incidents } = await loadWorkspace(current);
        if (activeToken.current !== current) return;
        setOverview(overview);
        setIncidents(incidents);
        setLoadedToken(current);
        setReady(true);
        setError("");
      } catch (e) {
        if (activeToken.current === current) {
          if (e instanceof ApiError && e.status === 401) setReady(false);
          setError((e as Error).message);
          setConnection("offline");
        }
        throw e;
      } finally {
        if (inflight.current === pending) inflight.current = null;
      }
    };
    const pending = { token, promise: operation() };
    inflight.current = pending;
    return pending.promise;
  }, [token]);
  useEffect(() => {
    setReady(false);
    setEvents([]);
    cursor.current.current = 0;
    inflight.current = null;
    setError("");
    setOverview(null);
    setIncidents([]);
    setRuntime(null);
    setRuns([]);
    setConnection("connecting");
    if (!token) return;
    let disposed = false;
    let retry: ReturnType<typeof setTimeout>;
    const load = () => {
      refresh().catch((e) => {
        if (!disposed && !(e instanceof ApiError && e.status === 401))
          retry = setTimeout(load, 3000);
      });
    };
    load();
    return () => { disposed = true; clearTimeout(retry); };
  }, [token, refresh]);
  useEffect(() => {
    if (!ready || !token) return;
    const abort = new AbortController();
    let retry: ReturnType<typeof setTimeout>,
      debounce: ReturnType<typeof setTimeout>;
    const connect = async () => {
      try {
        await stream(
          token,
          abort.signal,
          (e) => {
            setEvents((old) => [...old.slice(-299), e]);
            clearTimeout(debounce);
            debounce = setTimeout(() => refresh().catch(() => {}), 180);
          },
          cursor.current,
          () => setConnection("live"),
        );
      } catch {
        if (!abort.signal.aborted) setConnection("polling");
      }
      if (!abort.signal.aborted) {
        setConnection("polling");
        retry = setTimeout(connect, 3000);
      }
    };
    connect();
    const poll = setInterval(() => refresh().catch(() => {}), 8000);
    return () => {
      abort.abort();
      clearTimeout(retry);
      clearTimeout(debounce);
      clearInterval(poll);
    };
  }, [ready, token, refresh]);
  return {
    overview,
    incidents,
    runtime,
    runs,
    events,
    ready: ready && loadedToken === token,
    error,
    connection,
    refresh,
  };
}

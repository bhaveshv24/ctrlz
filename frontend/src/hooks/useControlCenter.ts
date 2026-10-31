import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  ApiError,
  stream,
  type DemoRun,
  type FlightEvent,
  type Incident,
  type Overview,
  type Runtime,
} from "../api";
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
    inflight = useRef<Promise<void> | null>(null);
  activeToken.current = token;
  const refresh = useCallback(async () => {
    if (inflight.current) return inflight.current;
    const current = token;
    const operation = async () => {
      try {
        const [o, i, r, d] = await Promise.all([
          api<Overview>("/overview", token),
          api<Incident[]>("/incidents", token),
          api<Runtime>("/health", token),
          api<DemoRun[]>("/demo/runs", token),
        ]);
        if (activeToken.current !== current) return;
        setOverview(o);
        setIncidents(i);
        setRuntime(r);
        setRuns(d);
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
        inflight.current = null;
      }
    };
    inflight.current = operation();
    return inflight.current;
  }, [token]);
  useEffect(() => {
    setReady(false);
    setEvents([]);
    cursor.current.current = 0;
    inflight.current = null;
    if (!token) return;
    refresh().catch(() => {});
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

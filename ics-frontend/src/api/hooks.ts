// src/api/hooks.ts
import { useEffect, useRef, useState } from 'react';
import { api, getApiBase } from './client';
import type { Summary, CallsList, CallDetail } from './types';

// --- helper: safely stringify query params for URLSearchParams ---
function toQueryString(
  obj: Record<string, string | number | boolean | undefined | null>
): string {
  const entries = Object.entries(obj)
    .filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => [k, String(v)] as [string, string]);
  return new URLSearchParams(entries).toString();
}

// Try multiple paths your API might expose
const CANDIDATE_SUMMARY_PATHS = [
  '/analytics/summary',
  '/summary',
  '/api/summary',
  '/v1/summary',
  '/v1/api/summary',
];

// Try multiple param shapes
const PARAM_SHAPES: Array<(since: string, until: string) => Record<string, string>> = [
  (s, u) => ({ since: s, until: u }),
  (s, u) => ({ start: s, end: u }),
  (s, u) => ({ date_from: s, date_to: u }),
];

type QueryState<T> = {
  data: T | null;
  error: any;
  isLoading: boolean;
  isFetching: boolean;
  refetch: () => Promise<void>;
  lastTriedUrl: React.MutableRefObject<string>;
};

export function useSummary(since: string, until: string): QueryState<Summary> {
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState<any>(null);
  const [isLoading, setLoading] = useState(false);
  const [isFetching, setFetching] = useState(false);

  const lastUrl = useRef<string>('');
  const abortRef = useRef<AbortController | null>(null);

  async function fetchSummary() {
    // cancel any in-flight request
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    setFetching(true);
    setError(null);

    let surfacedError: any = null;

    try {
      for (const path of CANDIDATE_SUMMARY_PATHS) {
        for (const build of PARAM_SHAPES) {
          const params = build(since, until);

          // 1) GET
          try {
            lastUrl.current = `${getApiBase()}${path}?${toQueryString(params)}`;
            const res = await api.get(path, { params, signal: ac.signal as AbortSignal });
            setData(res.data ?? null);
            setFetching(false);
            return;
          } catch (e: any) {
            if (ac.signal.aborted) return;
            const code = e?.response?.status as number | undefined;
            surfacedError = surfacedError ?? e;
            if (code && (code === 401 || code === 403 || code >= 500)) {
              throw e;
            }
          }

          // 2) POST
          try {
            lastUrl.current = `${getApiBase()}${path} [POST]`;
            const res = await api.post(path, params, { signal: ac.signal as AbortSignal });
            setData(res.data ?? null);
            setFetching(false);
            return;
          } catch (e: any) {
            if (ac.signal.aborted) return;
            const code = e?.response?.status as number | undefined;
            surfacedError = surfacedError ?? e;
            if (code && (code === 401 || code === 403 || code >= 500)) {
              throw e;
            }
            // try next combo
          }
        }
      }
      throw surfacedError ?? new Error('No summary endpoint responded');
    } catch (e) {
      if (!abortRef.current?.signal.aborted) {
        setError(e);
        setData(null);
      }
    } finally {
      if (!abortRef.current?.signal.aborted) setFetching(false);
    }
  }

  useEffect(() => {
    setLoading(true);
    fetchSummary().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [since, until]);

  return { data, error, isLoading, isFetching, refetch: fetchSummary, lastTriedUrl: lastUrl };
}

export function useCalls(since: string, until: string, limit = 50, offset = 0): QueryState<CallsList> {
  const [data, setData] = useState<CallsList | null>(null);
  const [error, setError] = useState<any>(null);
  const [isLoading, setLoading] = useState(false);
  const [isFetching, setFetching] = useState(false);

  const lastUrl = useRef<string>('');
  const abortRef = useRef<AbortController | null>(null);

  async function fetchCalls() {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    setFetching(true);
    setError(null);

    try {
      const path = '/calls';
      const params = { since, until, limit, offset };
      lastUrl.current = `${getApiBase()}${path}?${toQueryString(params)}`;
      const res = await api.get(path, { params, signal: ac.signal as AbortSignal });
      setData(res.data ?? null);
    } catch (e) {
      if (!abortRef.current?.signal.aborted) {
        setError(e);
        setData(null);
      }
    } finally {
      if (!abortRef.current?.signal.aborted) setFetching(false);
    }
  }

  useEffect(() => {
    setLoading(true);
    fetchCalls().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [since, until, limit, offset]);

  return { data, error, isLoading, isFetching, refetch: fetchCalls, lastTriedUrl: lastUrl };
}

export function useCallDetail(id?: string) {
  const [data, setData] = useState<CallDetail | null>(null);
  const [error, setError] = useState<any>(null);
  const [isLoading, setLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    const ac = new AbortController();
    setLoading(true);
    api
      .get(`/calls/${id}`, { signal: ac.signal as AbortSignal })
      .then((res) => setData(res.data ?? null))
      .catch((e) => {
        if (!ac.signal.aborted) setError(e);
      })
      .finally(() => {
        if (!ac.signal.aborted) setLoading(false);
      });
    return () => ac.abort();
  }, [id]);

  return { data, error, isLoading };
}

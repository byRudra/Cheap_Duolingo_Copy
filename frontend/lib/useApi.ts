"use client";

import { useCallback, useEffect, useState } from "react";

interface ApiState<T> {
  data: T | null;
  error: unknown;
  loading: boolean;
}

/**
 * Fetch on mount with loading/error state and a `reload` for Retry buttons.
 * Changing `key` (e.g. the active course id) refetches.
 */
export function useApi<T>(fetcher: () => Promise<T>, key?: string | number | null) {
  const [state, setState] = useState<ApiState<T>>({ data: null, error: null, loading: true });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetcher().then(
      (data) => {
        if (!cancelled) setState({ data, error: null, loading: false });
      },
      (error: unknown) => {
        if (!cancelled) setState({ data: null, error, loading: false });
      },
    );
    return () => {
      cancelled = true;
    };
    // `fetcher` is expected to be a stable module-level function.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version, key]);

  const reload = useCallback(() => {
    setState((s) => ({ ...s, error: null, loading: true }));
    setVersion((v) => v + 1);
  }, []);

  return { ...state, reload };
}

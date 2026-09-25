"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { Me } from "@/lib/types";

interface UserStatsValue {
  me: Me | null;
  error: unknown;
  loading: boolean;
  /** Re-read `/api/me`; call after answers (hearts) and lesson completion. */
  refresh: () => Promise<void>;
}

const UserStatsContext = createContext<UserStatsValue | null>(null);

export function UserStatsProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const next = await api.me();
      setMe(next);
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    api.me().then(
      (next) => {
        if (cancelled) return;
        setMe(next);
        setLoading(false);
      },
      (err: unknown) => {
        if (cancelled) return;
        setError(err);
        setLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  // Hearts regenerate lazily on the server; re-read when the next one is due.
  useEffect(() => {
    if (!me?.next_heart_at) return;
    const delay = new Date(me.next_heart_at).getTime() - Date.now() + 1000;
    const timer = window.setTimeout(() => void refresh(), Math.max(delay, 1000));
    return () => window.clearTimeout(timer);
  }, [me?.next_heart_at, refresh]);

  const value = useMemo(() => ({ me, error, loading, refresh }), [me, error, loading, refresh]);
  return <UserStatsContext.Provider value={value}>{children}</UserStatsContext.Provider>;
}

export function useUserStats(): UserStatsValue {
  const value = useContext(UserStatsContext);
  if (!value) throw new Error("useUserStats must be used inside <UserStatsProvider>");
  return value;
}

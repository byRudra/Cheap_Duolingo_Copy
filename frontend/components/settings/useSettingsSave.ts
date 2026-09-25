"use client";

import { useCallback, useState } from "react";

import { useUserStats } from "@/context/UserStatsContext";
import { api, errorMessage } from "@/lib/api";
import type { Settings, SettingsUpdate } from "@/lib/types";

type Field = keyof Settings;
type FieldErrors = Partial<Record<Field, string>>;

function without<T extends object>(source: T, fields: readonly Field[]): T {
  const copy = { ...source };
  for (const field of fields) delete (copy as Partial<Record<Field, unknown>>)[field];
  return copy;
}

/**
 * PATCH /api/me/settings with an optimistic overlay: the control shows the new
 * value immediately, the server's `Me` replaces the cached stats on success,
 * and the overlay is dropped (reverting the control) on failure.
 */
export function useSettingsSave() {
  const { me, replace } = useUserStats();
  const [overlay, setOverlay] = useState<SettingsUpdate>({});
  const [pending, setPending] = useState<readonly Field[]>([]);
  const [errors, setErrors] = useState<FieldErrors>({});

  const save = useCallback(
    async (update: SettingsUpdate): Promise<boolean> => {
      const fields = Object.keys(update) as Field[];
      setOverlay((current) => ({ ...current, ...update }));
      setPending((current) => [...current, ...fields]);
      setErrors((current) => without(current, fields));
      try {
        replace(await api.updateSettings(update));
        return true;
      } catch (err) {
        const message = errorMessage(err);
        setErrors((current) => ({ ...current, ...Object.fromEntries(fields.map((f) => [f, message])) }));
        return false;
      } finally {
        setOverlay((current) => without(current, fields));
        setPending((current) => current.filter((f) => !fields.includes(f)));
      }
    },
    [replace],
  );

  function value<K extends Field>(field: K): Settings[K] | undefined {
    const optimistic = overlay[field] as Settings[K] | undefined;
    return optimistic ?? me?.settings[field];
  }

  return {
    save,
    value,
    isPending: (field: Field) => pending.includes(field),
    error: (field: Field) => errors[field],
  };
}

export type SettingsSaver = ReturnType<typeof useSettingsSave>;

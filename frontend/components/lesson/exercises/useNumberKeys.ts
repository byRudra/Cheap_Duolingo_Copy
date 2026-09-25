"use client";

import { useEffect, useEffectEvent } from "react";

/** Keys 1–N pick an option, unless the learner is typing in a field. */
export function useNumberKeys(count: number, disabled: boolean, onPick: (index: number) => void) {
  const handle = useEffectEvent((event: KeyboardEvent) => {
    if (disabled || event.repeat || event.metaKey || event.ctrlKey || event.altKey) return;
    const target = event.target as HTMLElement | null;
    if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
    const n = Number(event.key);
    if (Number.isInteger(n) && n >= 1 && n <= Math.min(count, 9)) {
      event.preventDefault();
      onPick(n - 1);
    }
  });

  useEffect(() => {
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, []);
}

"use client";

import { useTheme, type ThemePreference } from "@/lib/theme";

const OPTIONS: { value: ThemePreference; label: string; icon: string }[] = [
  { value: "light", label: "Light", icon: "☀️" },
  { value: "dark", label: "Dark", icon: "🌙" },
  { value: "system", label: "System", icon: "💻" },
];

/** Segmented Light / Dark / System control. `compact` shows icons only. */
export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { preference, setPreference } = useTheme();
  return (
    <div role="radiogroup" aria-label="Theme" className="inline-flex rounded-2xl border-2 border-line bg-surface p-1">
      {OPTIONS.map(({ value, label, icon }) => {
        const active = preference === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={compact ? `${label} theme` : undefined}
            title={`${label} theme`}
            onClick={() => setPreference(value)}
            className={`flex min-h-11 min-w-11 items-center justify-center gap-1.5 rounded-xl px-3 text-sm font-extrabold transition-colors ${
              active ? "bg-card text-secondary shadow-sm" : "text-muted hover:text-ink"
            }`}
          >
            <span aria-hidden="true">{icon}</span>
            {!compact && label}
          </button>
        );
      })}
    </div>
  );
}

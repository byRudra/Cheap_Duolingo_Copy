"use client";

import { useId } from "react";

interface ToggleRowProps {
  label: string;
  description: string;
  checked: boolean;
  /** While a save is in flight the switch ignores presses but keeps keyboard focus. */
  pending?: boolean;
  onChange: (next: boolean) => void;
  children?: React.ReactNode;
}

/** A labelled on/off setting: `<button role="switch">` with a visible pill. */
export function ToggleRow({ label, description, checked, pending = false, onChange, children }: ToggleRowProps) {
  const id = useId();
  const labelId = `${id}-label`;
  const descId = `${id}-desc`;

  return (
    <li className="flex flex-col gap-2 py-3">
      <div className="flex min-h-14 items-center justify-between gap-4">
        <div className="min-w-0">
          <p id={labelId} className="font-extrabold">
            {label}
          </p>
          <p id={descId} className="text-sm text-muted">
            {description}
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={checked}
          aria-labelledby={labelId}
          aria-describedby={descId}
          aria-disabled={pending || undefined}
          aria-busy={pending || undefined}
          onClick={() => {
            if (!pending) onChange(!checked);
          }}
          className={`grid min-h-11 min-w-16 shrink-0 place-items-center rounded-2xl ${
            pending ? "cursor-progress opacity-60" : "cursor-pointer"
          }`}
        >
          <span
            aria-hidden="true"
            className={`flex h-8 w-14 items-center rounded-full border-2 p-0.5 transition-colors ${
              checked ? "justify-end border-primary-dark bg-primary" : "justify-start border-line-dark bg-locked"
            }`}
          >
            <span className="h-6 w-6 rounded-full bg-white shadow-sm" />
          </span>
        </button>
      </div>
      {children}
    </li>
  );
}

"use client";

import type { InputHTMLAttributes } from "react";

/** A settings card with its own h2. */
export function SettingsSection({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={`${id}-heading`} className="rounded-2xl border-2 border-line bg-card p-4 sm:p-5">
      <h2 id={`${id}-heading`} className="text-lg font-extrabold">
        {title}
      </h2>
      {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
      <div className="mt-3">{children}</div>
    </section>
  );
}

/** Inline error for a failed save. Renders nothing when there's no message. */
export function FieldError({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="mt-2 rounded-xl bg-danger-light px-3 py-2 text-sm font-bold text-danger-ink">
      {message}
    </p>
  );
}

interface RadioCardProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "className" | "children"> {
  checked: boolean;
  /** Ignore changes (and dim the card) while a save is pending, without dropping focus. */
  pending?: boolean;
  children: React.ReactNode;
  className?: string;
}

/**
 * A chunky, card-shaped radio button. Uses a native (visually hidden) radio so
 * arrow keys, grouping and the checked state come for free.
 */
export function RadioCard({ checked, pending = false, children, className = "", onChange, ...input }: RadioCardProps) {
  return (
    <label
      className={`relative flex min-h-14 cursor-pointer items-center gap-3 rounded-2xl border-2 border-b-4 p-3 transition-colors has-focus-visible:outline-3 has-focus-visible:outline-offset-2 has-focus-visible:outline-secondary ${
        checked ? "border-secondary bg-secondary-light" : "border-line bg-card hover:bg-surface"
      } ${pending ? "cursor-progress opacity-70" : ""} ${className}`}
    >
      <input
        type="radio"
        className="sr-only"
        checked={checked}
        aria-disabled={pending || undefined}
        onChange={(event) => {
          if (!pending) onChange?.(event);
        }}
        {...input}
      />
      {children}
    </label>
  );
}

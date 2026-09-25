"use client";

import { useEffect, useId, useRef } from "react";

interface ModalProps {
  title: string;
  onClose?: () => void;
  children: React.ReactNode;
}

/** Accessible dialog: focus moves inside on open, Escape closes (if closable). */
export function Modal({ title, onClose, children }: ModalProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const focusable = panelRef.current?.querySelector<HTMLElement>("button:not([disabled]), a[href]");
    focusable?.focus();
    return () => previous?.focus?.();
  }, []);

  useEffect(() => {
    if (!onClose) return;
    const close = onClose;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") close();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 p-0 sm:items-center sm:p-4 animate-fade-in">
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="w-full max-w-md animate-slide-up rounded-t-3xl bg-white p-6 shadow-xl sm:rounded-3xl"
      >
        <h2 id={titleId} className="sr-only">
          {title}
        </h2>
        {children}
      </div>
    </div>
  );
}

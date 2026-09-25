"use client";

import Link from "next/link";
import { forwardRef, useEffect, useRef } from "react";

import type { SkillNode as Skill } from "@/lib/types";

import { buttonClasses } from "../ui/Button";
import { CheckIcon, LockIcon } from "../ui/icons";
import { ProgressRing } from "../ui/ProgressRing";

interface SkillNodeProps {
  skill: Skill;
  unitColor: string;
  offset: number;
  isCurrent: boolean;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
}

const STATE_LABEL: Record<Skill["state"], string> = {
  LOCKED: "locked",
  AVAILABLE: "ready to start",
  IN_PROGRESS: "in progress",
  COMPLETED: "completed",
};

export const SkillNode = forwardRef<HTMLDivElement, SkillNodeProps>(function SkillNode(
  { skill, unitColor, offset, isCurrent, open, onToggle, onClose },
  ref,
) {
  const popoverRef = useRef<HTMLDivElement>(null);
  const locked = skill.state === "LOCKED";
  const completed = skill.state === "COMPLETED";
  const fill = locked ? "var(--color-locked)" : completed ? "var(--color-gold)" : unitColor;
  const edge = locked ? "var(--color-locked-dark)" : completed ? "var(--color-gold-dark)" : "rgba(0,0,0,.22)";
  const popoverId = `skill-popover-${skill.id}`;

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    function onPointer(event: PointerEvent) {
      const root = popoverRef.current?.parentElement;
      if (root && !root.contains(event.target as Node)) onClose();
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  const lessonNumber = Math.min(skill.lessons_completed + 1, skill.lessons_total);

  return (
    <div ref={ref} className="relative flex flex-col items-center" style={{ transform: `translateX(${offset}px)` }}>
      {isCurrent && !open && (
        <div className="absolute -top-11 z-10 animate-bounce-soft rounded-xl border-2 border-line bg-white px-3 py-1.5 text-sm font-extrabold tracking-wide text-primary uppercase shadow-sm">
          {skill.state === "AVAILABLE" ? "Start" : "Continue"}
          <span className="absolute -bottom-2 left-1/2 h-3 w-3 -translate-x-1/2 rotate-45 border-r-2 border-b-2 border-line bg-white" />
        </div>
      )}

      <ProgressRing
        progress={completed ? 100 : skill.progress}
        size={104}
        stroke={8}
        color={completed ? "var(--color-gold)" : unitColor}
        trackColor={locked ? "transparent" : "var(--color-line)"}
      >
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-controls={popoverId}
          aria-label={`${skill.title}, ${STATE_LABEL[skill.state]}, ${skill.lessons_completed} of ${skill.lessons_total} lessons`}
          className={`relative grid h-18 w-18 place-items-center rounded-full border-b-[6px] text-3xl transition-transform duration-75 active:translate-y-1 active:border-b-2 ${
            isCurrent ? "motion-safe:animate-bounce-soft" : ""
          }`}
          style={{ backgroundColor: fill, borderColor: edge }}
        >
          <span className={locked ? "opacity-40 grayscale" : ""} aria-hidden="true">
            {skill.icon}
          </span>
          {locked && (
            <span className="absolute -right-1 -bottom-1 grid h-7 w-7 place-items-center rounded-full border-2 border-white bg-locked-dark text-white">
              <LockIcon className="h-4 w-4" />
            </span>
          )}
          {completed && (
            <span className="absolute -right-1 -bottom-1 grid h-7 w-7 place-items-center rounded-full border-2 border-white bg-gold-dark text-white">
              <CheckIcon className="h-4 w-4" />
            </span>
          )}
        </button>
      </ProgressRing>
      <p className={`mt-1 text-sm font-extrabold ${locked ? "text-muted" : "text-ink"}`}>{skill.title}</p>

      {open && (
        <div
          ref={popoverRef}
          id={popoverId}
          role="dialog"
          aria-label={skill.title}
          className="absolute top-full z-20 mt-3 w-72 animate-fade-in rounded-2xl p-4 text-white shadow-lg"
          style={{ backgroundColor: locked ? "var(--color-surface)" : completed ? "var(--color-gold)" : unitColor }}
        >
          <span
            className="absolute -top-2 left-1/2 h-4 w-4 -translate-x-1/2 rotate-45"
            style={{ backgroundColor: locked ? "var(--color-surface)" : completed ? "var(--color-gold)" : unitColor }}
          />
          <h3 className={`text-lg font-extrabold ${locked ? "text-ink" : ""}`}>{skill.title}</h3>
          {locked ? (
            <>
              <p className="mb-3 text-sm text-muted">Complete the previous skill to unlock</p>
              <button type="button" disabled className={buttonClasses("primary", "w-full")}>
                Locked
              </button>
            </>
          ) : (
            <>
              <p className="mb-3 text-sm font-bold opacity-90">
                {completed
                  ? `Completed · ${skill.lessons_total} of ${skill.lessons_total} lessons`
                  : `Lesson ${lessonNumber} of ${skill.lessons_total}`}
              </p>
              <Link
                href={`/lesson/${skill.next_lesson_id}`}
                className="btn-chunky w-full border-line bg-white"
                style={{ color: completed ? "var(--color-gold-dark)" : unitColor }}
              >
                {completed ? "Practice" : skill.state === "IN_PROGRESS" ? "Continue" : "Start"}
              </Link>
            </>
          )}
        </div>
      )}
    </div>
  );
});

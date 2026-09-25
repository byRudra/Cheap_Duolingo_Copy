"use client";

import { useEffect, useRef, useState } from "react";

import { useUserStats } from "@/context/UserStatsContext";
import { api, errorMessage } from "@/lib/api";
import type { CourseSummary } from "@/lib/types";

import { CourseFlag } from "../ui/CourseFlag";
import { CheckIcon } from "../ui/icons";

/** Flag button that opens every course; picking one switches the active course. */
export function CourseSwitcher({ align = "left", showTitle = false }: { align?: "left" | "right"; showTitle?: boolean }) {
  const { me, replace } = useUserStats();
  const [open, setOpen] = useState(false);
  const [courses, setCourses] = useState<CourseSummary[] | null>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    api.courses().then(
      (list) => !cancelled && setCourses(list),
      (err: unknown) => !cancelled && setError(errorMessage(err)),
    );
    function onPointer(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      cancelled = true;
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!me) return null;
  const active = me.active_course;

  async function choose(course: CourseSummary) {
    if (course.id === active.id) {
      setOpen(false);
      return;
    }
    setPendingId(course.id);
    setError(null);
    try {
      replace(await api.setCourse(course.id));
      setOpen(false);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="true"
        aria-label={`Course: ${active.title}. Change course`}
        className="flex min-h-11 items-center gap-2 rounded-xl px-2 font-extrabold hover:bg-surface"
      >
        <CourseFlag code={active.language_code} emoji={active.flag_emoji} className="h-6 w-9" />
        {showTitle && <span>{active.title}</span>}
      </button>

      {open && (
        <div
          className={`absolute top-full z-40 mt-2 w-72 animate-fade-in rounded-2xl border-2 border-line bg-card p-2 shadow-xl ${
            align === "right" ? "right-0" : "left-0"
          }`}
        >
          <p className="px-3 pt-2 pb-1 text-xs font-black tracking-wide text-muted uppercase">My courses</p>
          {courses === null && !error && <p className="px-3 py-3 text-sm text-muted">Loading…</p>}
          <ul>
            {courses?.map((course) => (
              <li key={course.id}>
                <button
                  type="button"
                  onClick={() => void choose(course)}
                  disabled={pendingId !== null}
                  aria-current={course.id === active.id ? "true" : undefined}
                  className={`flex min-h-14 w-full items-center gap-3 rounded-xl px-3 py-2 text-left hover:bg-surface disabled:opacity-60 ${
                    course.id === active.id ? "bg-secondary-light" : ""
                  }`}
                >
                  <CourseFlag code={course.language_code} emoji={course.flag_emoji} className="h-7 w-10" />
                  <span className="min-w-0 flex-1">
                    <span className="block font-extrabold">{course.title}</span>
                    <span className="block text-xs text-muted">
                      {course.lessons_completed}/{course.lessons_total} lessons · {course.progress}%
                    </span>
                  </span>
                  {course.id === active.id && <CheckIcon className="h-5 w-5 text-secondary" />}
                  {pendingId === course.id && <span className="text-xs text-muted">…</span>}
                </button>
              </li>
            ))}
          </ul>
          {error && (
            <p role="alert" className="px-3 py-2 text-sm font-bold text-danger">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

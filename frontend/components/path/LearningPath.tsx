"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { Course } from "@/lib/types";

import { EmptyState } from "../ui/States";
import { SkillNode } from "./SkillNode";

/** Horizontal offset for the n-th node: a gentle sine wave, not a grid. */
function waveOffset(index: number): number {
  return Math.round(Math.sin((index * Math.PI) / 4) * 72);
}

export function LearningPath({ course }: { course: Course }) {
  const [openSkillId, setOpenSkillId] = useState<number | null>(null);
  const currentRef = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpenSkillId(null), []);

  // Bring the learner's current skill into view on load.
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    currentRef.current?.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" });
  }, [course.current_skill_id]);

  if (course.units.length === 0) {
    return <EmptyState title="No units yet" message="This course doesn't have any lessons yet." />;
  }

  let globalIndex = 0;
  return (
    <div className="flex flex-col gap-10">
      {course.units.map((unit) => (
        <section key={unit.id} aria-labelledby={`unit-${unit.id}`}>
          <header
            className="mb-10 rounded-2xl border-b-4 px-5 py-4 text-white"
            style={{ backgroundColor: unit.color, borderColor: "rgba(0,0,0,.2)" }}
          >
            <p className="text-sm font-extrabold tracking-wide uppercase opacity-80">Unit {unit.order_index}</p>
            <h2 id={`unit-${unit.id}`} className="text-2xl font-black">
              {unit.title}
            </h2>
            <p className="font-semibold opacity-90">{unit.description}</p>
          </header>
          <ol className="flex flex-col items-center gap-16">
            {unit.skills.map((skill) => {
              const offset = waveOffset(globalIndex++);
              const isCurrent = skill.id === course.current_skill_id;
              return (
                <li key={skill.id} className={openSkillId === skill.id ? "relative z-20" : "relative"}>
                  <SkillNode
                    ref={isCurrent ? currentRef : undefined}
                    skill={skill}
                    unitColor={unit.color}
                    offset={offset}
                    isCurrent={isCurrent}
                    open={openSkillId === skill.id}
                    onToggle={() => setOpenSkillId((id) => (id === skill.id ? null : skill.id))}
                    onClose={close}
                  />
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}

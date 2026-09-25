"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Mascot } from "@/components/Mascot";
import { DailyGoalCard, HeartsCard, RightRail } from "@/components/home/RightRail";
import { LearningPath } from "@/components/path/LearningPath";
import { buttonClasses } from "@/components/ui/Button";
import { FlameIcon } from "@/components/ui/icons";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { useUserStats } from "@/context/UserStatsContext";
import { api } from "@/lib/api";
import { maybeSendStreakReminder } from "@/lib/reminder";
import type { Course } from "@/lib/types";
import { useApi } from "@/lib/useApi";

const GREETINGS: Record<string, string> = {
  es: "¡Hola",
  fr: "Bonjour",
  pa: "ਸਤ ਸ੍ਰੀ ਅਕਾਲ",
  en: "Hello",
};

function PathSkeleton() {
  return (
    <div className="flex flex-col items-center gap-9" aria-label="Loading your path" role="status">
      <Skeleton className="h-24 w-full" />
      {[0, 51, 72, 51, 0].map((x, i) => (
        <div key={i} style={{ transform: `translateX(${x}px)` }}>
          <Skeleton className="h-18 w-18 rounded-full" />
        </div>
      ))}
    </div>
  );
}

function Hero({ course }: { course: Course }) {
  const { me } = useUserStats();
  const skills = course.units.flatMap((u) => u.skills);
  const lessonsTotal = skills.reduce((n, s) => n + s.lessons_total, 0);
  const lessonsDone = skills.reduce((n, s) => n + s.lessons_completed, 0);
  const current = skills.find((s) => s.id === course.current_skill_id);
  const greeting = GREETINGS[course.language_code] ?? "Hello";
  const pct = lessonsTotal ? Math.round((lessonsDone / lessonsTotal) * 100) : 0;

  return (
    <section className="mb-10 flex items-center gap-4 rounded-2xl border-2 border-line p-4 sm:p-5" aria-label="Your progress">
      <Mascot mood="cheer" className="h-20 w-20 shrink-0 sm:h-24 sm:w-24" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-extrabold tracking-wide text-muted uppercase">{course.title} course</p>
        <h1 className="text-2xl font-black">
          {greeting}
          {me ? `, ${me.display_name}` : ""}!
        </h1>
        <div className="mt-2 flex items-center gap-2">
          <div className="h-3 flex-1 overflow-hidden rounded-full bg-line" aria-hidden="true">
            <div className="h-full rounded-full bg-primary transition-[width] duration-700" style={{ width: `${pct}%` }} />
          </div>
          <span className="text-sm font-extrabold text-muted">
            {lessonsDone}/{lessonsTotal} lessons
          </span>
        </div>
        {current?.next_lesson_id ? (
          <Link href={`/lesson/${current.next_lesson_id}`} className={buttonClasses("primary", "mt-3 w-full sm:w-auto")}>
            {current.state === "AVAILABLE" ? "Start" : "Continue"}: {current.title}
          </Link>
        ) : (
          <p className="mt-3 font-bold text-primary-ink">You&apos;ve completed the whole course. Amazing work!</p>
        )}
      </div>
    </section>
  );
}

function StreakReminder() {
  const { me } = useUserStats();
  const show = !!me && me.settings.daily_reminder && !me.streak_extended_today;

  useEffect(() => {
    if (show && me) maybeSendStreakReminder(me.today, me.streak);
  }, [show, me]);

  if (!show || !me) return null;
  return (
    <div role="status" className="mb-6 flex items-center gap-3 rounded-2xl border-2 border-streak/40 bg-gold-light p-4">
      <FlameIcon className="h-9 w-9 shrink-0 text-streak" />
      <p className="font-bold text-gold-ink">
        {me.streak > 0
          ? `Your ${me.streak}-day streak is waiting — finish one lesson today to keep it alive!`
          : "Start a streak today: finish one lesson and come back tomorrow."}
      </p>
    </div>
  );
}

export default function HomePage() {
  const { me } = useUserStats();
  const { data: course, error, loading, reload } = useApi(api.course, me?.active_course.id ?? null);

  return (
    <div className="mx-auto flex max-w-5xl gap-12 px-4 pt-6 lg:px-8">
      <div className="min-w-0 flex-1 pb-40">
        <div className="mx-auto max-w-md">
          <StreakReminder />
          {loading ? (
            <PathSkeleton />
          ) : error || !course ? (
            <ErrorState error={error} onRetry={reload} />
          ) : (
            <>
              <Hero course={course} />
              {/* On mobile the right rail is hidden: surface goal + hearts inline. */}
              <div className="mb-10 grid gap-4 lg:hidden">
                <DailyGoalCard />
                {me && me.hearts < me.max_hearts && <HeartsCard />}
              </div>
              <LearningPath course={course} />
            </>
          )}
        </div>
      </div>
      <aside className="sticky top-6 hidden h-fit w-80 shrink-0 lg:block" aria-label="Your stats">
        <RightRail />
      </aside>
    </div>
  );
}

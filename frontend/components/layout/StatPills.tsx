"use client";

import { useUserStats } from "@/context/UserStatsContext";

import { FlameIcon, GemIcon, HeartIcon } from "../ui/icons";
import { Skeleton } from "../ui/States";

/** Compact streak · gems · hearts readout used in the mobile top bar and rail. */
export function StatPills() {
  const { me, loading } = useUserStats();

  if (loading && !me) {
    return (
      <div className="flex items-center gap-3" aria-hidden="true">
        <Skeleton className="h-7 w-14" />
        <Skeleton className="h-7 w-14" />
        <Skeleton className="h-7 w-14" />
      </div>
    );
  }
  if (!me) return null;

  const streakActive = me.streak_extended_today;
  return (
    <div className="flex items-center gap-1 sm:gap-3">
      <span
        className={`flex items-center gap-1 rounded-xl px-2 py-1 font-extrabold ${streakActive ? "text-streak" : "text-locked-dark"}`}
        title={streakActive ? "Streak extended today" : "Complete a lesson to extend your streak"}
      >
        <FlameIcon className="h-6 w-6" />
        <span aria-label={`${me.streak} day streak`}>{me.streak}</span>
      </span>
      <span className="flex items-center gap-1 rounded-xl px-2 py-1 font-extrabold text-gem">
        <GemIcon className="h-6 w-6" />
        <span aria-label={`${me.gems} gems`}>{me.gems}</span>
      </span>
      <span className="flex items-center gap-1 rounded-xl px-2 py-1 font-extrabold text-heart">
        <HeartIcon className="h-6 w-6" />
        <span aria-label={`${me.hearts} of ${me.max_hearts} hearts`}>{me.hearts}</span>
      </span>
    </div>
  );
}

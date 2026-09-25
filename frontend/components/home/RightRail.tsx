"use client";

import Link from "next/link";
import { useState } from "react";

import { useUserStats } from "@/context/UserStatsContext";
import { api, errorMessage } from "@/lib/api";

import { CourseSwitcher } from "../layout/CourseSwitcher";
import { StatPills } from "../layout/StatPills";
import { Button, buttonClasses } from "../ui/Button";
import { Countdown } from "../ui/Countdown";
import { FlameIcon, GemIcon, HeartIcon } from "../ui/icons";
import { ProgressRing } from "../ui/ProgressRing";
import { Skeleton } from "../ui/States";

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border-2 border-line p-5" aria-label={title}>
      <h2 className="mb-3 text-lg font-extrabold">{title}</h2>
      {children}
    </section>
  );
}

export function StreakCard() {
  const { me } = useUserStats();
  if (!me) return <Skeleton className="h-28" />;
  return (
    <Card title="Streak">
      <div className="flex items-center gap-4">
        <FlameIcon
          className={`h-14 w-14 ${me.streak > 0 ? "text-streak" : "text-locked-dark"} ${me.streak_extended_today ? "animate-flame" : ""}`}
        />
        <div>
          <p className="text-2xl font-black">
            {me.streak} day{me.streak === 1 ? "" : "s"}
          </p>
          <p className="text-sm text-muted">
            {me.streak_extended_today
              ? "You've practiced today. See you tomorrow!"
              : me.streak > 0
                ? "Complete a lesson today to keep it alive."
                : "Complete a lesson to start a streak."}
          </p>
        </div>
      </div>
    </Card>
  );
}

export function DailyGoalCard() {
  const { me } = useUserStats();
  if (!me) return <Skeleton className="h-28" />;
  const { earned, goal, met } = me.daily_goal;
  const pct = Math.round((Math.min(earned, goal) / goal) * 100);
  return (
    <Card title="Daily goal">
      <div className="flex items-center gap-4">
        <ProgressRing progress={pct} size={64} stroke={8} color={met ? "var(--color-gold)" : "var(--color-primary)"}>
          <span className="text-sm font-black">{pct}%</span>
        </ProgressRing>
        <div>
          <p className="text-xl font-black">
            {earned} / {goal} XP
          </p>
          <p className="text-sm text-muted">{met ? "Goal complete. Great work!" : `${goal - earned} XP to go today`}</p>
        </div>
      </div>
    </Card>
  );
}

export function HeartsCard() {
  const { me, refresh } = useUserStats();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!me) return <Skeleton className="h-36" />;
  const full = me.hearts >= me.max_hearts;
  const canAfford = me.gems >= me.refill_cost;

  async function refill() {
    setPending(true);
    setError(null);
    try {
      await api.refillHearts();
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <Card title="Hearts">
      <div className="mb-3 flex gap-1" aria-label={`${me.hearts} of ${me.max_hearts} hearts`} role="img">
        {Array.from({ length: me.max_hearts }, (_, i) => (
          <HeartIcon key={i} className={`h-8 w-8 ${i < me.hearts ? "text-heart" : "text-locked"}`} />
        ))}
      </div>
      <p className="mb-3 text-sm text-muted">
        {full ? (
          "Full hearts. Every mistake costs one."
        ) : me.next_heart_at ? (
          <>
            Next heart in <Countdown to={me.next_heart_at} /> · 1 every {me.heart_regen_minutes} min
          </>
        ) : null}
      </p>
      {!full && (
        <div className="flex flex-col gap-2">
          <Button variant="secondary" fullWidth disabled={pending || !canAfford} onClick={refill}>
            Refill <GemIcon className="h-5 w-5" /> {me.refill_cost}
          </Button>
          <Link href="/practice" className={buttonClasses("outline", "w-full")}>
            Practice to earn a heart
          </Link>
        </div>
      )}
      {!full && !canAfford && <p className="mt-2 text-sm text-muted">Not enough gems for a refill.</p>}
      {error && (
        <p role="alert" className="mt-2 text-sm font-bold text-danger">
          {error}
        </p>
      )}
    </Card>
  );
}

export function RightRail() {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <CourseSwitcher align="left" />
        <StatPills />
      </div>
      <StreakCard />
      <DailyGoalCard />
      <HeartsCard />
    </div>
  );
}

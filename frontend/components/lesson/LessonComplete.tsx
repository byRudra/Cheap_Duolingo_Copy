"use client";

import { useEffect, useState } from "react";

import type { CompletionSummary } from "@/lib/types";

import { Mascot } from "../Mascot";
import { Button } from "../ui/Button";
import { BoltIcon, FlameIcon, TargetIcon } from "../ui/icons";
import { ProgressRing } from "../ui/ProgressRing";

const CONFETTI_COLORS = ["#46b936", "#1fa5ea", "#ffb91f", "#ff4b6e", "#8b5cf6", "#ff8a1f"];

/** Deterministic pseudo-random spread so render stays pure. */
function Confetti() {
  return (
    <div className="pointer-events-none fixed inset-0 z-40 overflow-hidden" aria-hidden="true">
      {Array.from({ length: 48 }, (_, i) => {
        const r = (n: number) => ((i * 9301 + n * 49297) % 233280) / 233280;
        return (
          <span
            key={i}
            className="confetti-piece"
            style={
              {
                left: `${r(1) * 100}%`,
                backgroundColor: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
                "--delay": `${r(2) * 0.8}s`,
                "--duration": `${2.2 + r(3) * 1.6}s`,
                "--drift": `${(r(4) - 0.5) * 240}px`,
                "--spin": `${360 + r(5) * 540}deg`,
              } as React.CSSProperties
            }
          />
        );
      })}
    </div>
  );
}

function useCountUp(target: number, durationMs = 900): number {
  const [value, setValue] = useState(0);
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0;
    const start = performance.now();
    function tick(now: number) {
      const t = reduced ? 1 : Math.min(1, (now - start) / durationMs);
      setValue(Math.round(target * (1 - (1 - t) ** 3)));
      if (t < 1) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, durationMs]);
  return value;
}

function StatTile({
  label,
  tone,
  icon,
  children,
}: {
  label: string;
  tone: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex-1 overflow-hidden rounded-2xl border-2" style={{ borderColor: tone }}>
      <p className="px-2 py-1 text-center text-xs font-black tracking-wide text-white uppercase" style={{ backgroundColor: tone }}>
        {label}
      </p>
      <div className="flex items-center justify-center gap-1.5 px-2 py-3 text-2xl font-black" style={{ color: tone }}>
        {icon}
        {children}
      </div>
    </div>
  );
}

export function LessonComplete({ summary, onContinue }: { summary: CompletionSummary; onContinue: () => void }) {
  const xp = useCountUp(summary.xp_earned);
  const goalPct = Math.round((Math.min(summary.daily_goal.earned, summary.daily_goal.goal) / summary.daily_goal.goal) * 100);
  const celebrate = !summary.already_completed;

  return (
    <div className="flex min-h-screen flex-col">
      {celebrate && <Confetti />}

      {/* Achievement toasts */}
      {summary.new_achievements.length > 0 && (
        <div className="fixed top-4 right-4 left-4 z-50 flex flex-col items-end gap-2 sm:left-auto" role="status">
          {summary.new_achievements.map((a, i) => (
            <div
              key={a.code}
              className="flex w-full animate-slide-in items-center gap-3 rounded-2xl border-2 border-gold bg-gold-light px-4 py-3 shadow-lg sm:w-80"
              style={{ animationDelay: `${0.6 + i * 0.25}s`, animationFillMode: "backwards" }}
            >
              <span className="text-3xl" aria-hidden="true">
                {a.icon}
              </span>
              <div>
                <p className="text-xs font-black tracking-wide text-gold-dark uppercase">Achievement unlocked</p>
                <p className="font-extrabold">{a.title}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      <main className="mx-auto flex w-full max-w-lg flex-1 flex-col items-center justify-center gap-6 px-4 py-10 text-center">
        <Mascot mood="cheer" className="h-32 w-32 animate-bounce-soft" />
        <div>
          <h1 className="text-3xl font-black text-gold-dark">
            {summary.already_completed ? "Lesson already completed" : summary.perfect ? "Perfect lesson!" : "Lesson complete!"}
          </h1>
          {summary.perfect && !summary.already_completed && (
            <p className="mt-2 inline-block animate-pop rounded-full bg-gold-light px-3 py-1 text-sm font-black text-gold-dark">
              🎯 No mistakes · perfect bonus
            </p>
          )}
          {summary.already_completed && <p className="mt-2 text-muted">This attempt was already counted. No extra XP.</p>}
        </div>

        <div className="flex w-full gap-3">
          <StatTile label="Total XP" tone="var(--color-gold)" icon={<BoltIcon className="h-6 w-6" />}>
            <span aria-label={`${summary.xp_earned} XP earned`}>+{xp}</span>
          </StatTile>
          <StatTile label="Accuracy" tone="var(--color-primary)" icon={<TargetIcon className="h-6 w-6" />}>
            {summary.accuracy}%
          </StatTile>
          <StatTile label="Streak" tone="var(--color-streak)" icon={<FlameIcon className={`h-7 w-7 ${summary.streak.extended ? "animate-flame" : ""}`} />}>
            {summary.streak.after}
          </StatTile>
        </div>

        {summary.streak.extended && (
          <p className="font-extrabold text-streak">
            🔥 Streak extended: {summary.streak.before} → {summary.streak.after} days
          </p>
        )}

        <div className="flex w-full items-center gap-4 rounded-2xl border-2 border-line p-4 text-left">
          <ProgressRing
            progress={goalPct}
            size={64}
            stroke={8}
            color={goalPct >= 100 ? "var(--color-gold)" : "var(--color-primary)"}
          >
            <span className="text-sm font-black">{goalPct}%</span>
          </ProgressRing>
          <div>
            <p className="font-extrabold">{summary.daily_goal.just_met ? "Daily goal complete! 🎉" : "Daily goal"}</p>
            <p className="text-sm text-muted">
              {summary.daily_goal.earned} / {summary.daily_goal.goal} XP today
            </p>
          </div>
        </div>

        <div className="w-full rounded-2xl border-2 border-line p-4 text-left">
          <p className="font-extrabold">
            {summary.skill.title} · {summary.skill.progress}%
          </p>
          <div className="mt-2 h-3 overflow-hidden rounded-full bg-line" aria-hidden="true">
            <div className="h-full rounded-full bg-primary transition-[width] duration-700" style={{ width: `${summary.skill.progress}%` }} />
          </div>
          {summary.newly_unlocked_skill && (
            <p className="mt-3 animate-pop font-extrabold text-secondary">🔓 New skill unlocked: {summary.newly_unlocked_skill.title}</p>
          )}
        </div>
      </main>

      <footer className="border-t-2 border-line">
        <div className="mx-auto flex max-w-3xl justify-end px-4 py-5 sm:py-7">
          <Button onClick={onContinue} className="w-full sm:w-auto sm:min-w-44" autoFocus>
            Continue
          </Button>
        </div>
      </footer>
    </div>
  );
}

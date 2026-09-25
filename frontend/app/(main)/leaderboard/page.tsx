"use client";

import { RankBadge } from "@/components/leaderboard/RankBadge";
import { Avatar } from "@/components/profile/Avatar";
import { TrophyIcon } from "@/components/ui/icons";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import { api } from "@/lib/api";
import type { LeaderboardEntry } from "@/lib/types";
import { useApi } from "@/lib/useApi";

function LeaderboardRow({ entry }: { entry: LeaderboardEntry }) {
  const you = entry.is_current_user;
  return (
    <li
      aria-current={you ? "true" : undefined}
      className={`flex min-h-16 items-center gap-3 rounded-2xl border-2 px-2 py-2 sm:gap-4 sm:px-4 ${
        you ? "border-secondary bg-secondary-light" : "border-transparent"
      }`}
    >
      <RankBadge rank={entry.rank} />
      <Avatar name={entry.display_name} color={entry.avatar_color} className="h-11 w-11 text-lg sm:h-12 sm:w-12 sm:text-xl" />
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <span className="truncate font-extrabold">{entry.display_name}</span>
        {you && (
          <span className="shrink-0 rounded-lg border-2 border-secondary bg-card px-2 text-xs font-black tracking-wide uppercase">
            You
          </span>
        )}
      </div>
      <span className="shrink-0 font-extrabold tabular-nums">{entry.xp} XP</span>
    </li>
  );
}

function LeaderboardSkeleton() {
  return (
    <div role="status" aria-label="Loading leaderboard" className="flex flex-col gap-2 p-2">
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="flex min-h-16 items-center gap-3 px-2 sm:gap-4 sm:px-4">
          <Skeleton className="h-8 w-8 rounded-full" />
          <Skeleton className="h-11 w-11 rounded-full sm:h-12 sm:w-12" />
          <Skeleton className="h-5 flex-1" />
          <Skeleton className="h-5 w-16" />
        </div>
      ))}
    </div>
  );
}

export default function LeaderboardPage() {
  const { data, error, loading, reload } = useApi(api.leaderboard);

  return (
    <div className="mx-auto max-w-3xl px-4 pt-6 pb-10">
      <header className="mb-6 flex items-center gap-4">
        <span className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl bg-gold-light">
          <TrophyIcon className="h-10 w-10 text-gold" />
        </span>
        <div>
          <h1 className="text-3xl font-black">Leaderboard</h1>
          <p className="text-muted">Earn XP to climb the ranks</p>
        </div>
      </header>

      <section aria-label="Rankings" className="rounded-2xl border-2 border-line">
        {loading ? (
          <LeaderboardSkeleton />
        ) : error || !data ? (
          <ErrorState error={error} onRetry={reload} title="Couldn't load the leaderboard" />
        ) : data.entries.length === 0 ? (
          <EmptyState title="No learners yet" message="Complete a lesson to be the first on the board." />
        ) : (
          <ol className="flex animate-fade-in flex-col gap-1 p-2">
            {data.entries.map((entry) => (
              <LeaderboardRow key={entry.user_id} entry={entry} />
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

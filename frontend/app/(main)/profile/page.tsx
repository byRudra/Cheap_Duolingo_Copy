"use client";

import { Avatar } from "@/components/profile/Avatar";
import { CourseFlag } from "@/components/ui/CourseFlag";
import { BoltIcon, CheckIcon, FlameIcon, GemIcon, LockIcon, TargetIcon, TrophyIcon } from "@/components/ui/icons";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { api } from "@/lib/api";
import type { Achievement, Profile } from "@/lib/types";
import { useApi } from "@/lib/useApi";

function formatDate(iso: string, options: Intl.DateTimeFormatOptions): string {
  return new Date(iso).toLocaleDateString("en-US", options);
}

function ProfileHeader({ profile }: { profile: Profile }) {
  return (
    <header className="flex flex-col items-center gap-4 border-b-2 border-line pb-6 text-center sm:flex-row sm:items-center sm:gap-6 sm:text-left">
      <Avatar name={profile.display_name} color={profile.avatar_color} className="h-24 w-24 text-5xl sm:h-28 sm:w-28" />
      <div className="min-w-0">
        <h1 className="truncate text-3xl font-black">{profile.display_name}</h1>
        <p className="font-bold text-muted">@{profile.username}</p>
        <p className="mt-1 text-sm text-muted">
          Joined{" "}
          <time dateTime={profile.joined_at}>{formatDate(profile.joined_at, { month: "long", year: "numeric" })}</time>
        </p>
        <p className="mt-3 inline-flex items-center gap-2 rounded-xl border-2 border-line px-3 py-1 text-sm font-extrabold">
          <CourseFlag code={profile.course_language_code} emoji={profile.course_flag} className="h-4 w-6" />
          Learning {profile.course_title}
        </p>
      </div>
    </header>
  );
}

interface Stat {
  label: string;
  value: string;
  icon: React.ReactNode;
}

function statsFor(profile: Profile): Stat[] {
  return [
    { label: "Total XP", value: String(profile.total_xp), icon: <BoltIcon className="h-8 w-8 text-gold" /> },
    {
      label: "Day streak",
      value: String(profile.streak),
      icon: <FlameIcon className={`h-8 w-8 ${profile.streak > 0 ? "text-streak" : "text-locked-dark"}`} />,
    },
    { label: "Longest streak", value: String(profile.longest_streak), icon: <TrophyIcon className="h-8 w-8 text-streak" /> },
    {
      label: "Lessons completed",
      value: String(profile.lessons_completed),
      icon: <CheckIcon className="h-8 w-8 text-primary" />,
    },
    {
      label: "Skills completed",
      value: `${profile.skills_completed} / ${profile.skills_total}`,
      icon: <TargetIcon className="h-8 w-8 text-secondary" />,
    },
    { label: "Gems", value: String(profile.gems), icon: <GemIcon className="h-8 w-8 text-gem" /> },
  ];
}

function StatGrid({ profile }: { profile: Profile }) {
  return (
    <section aria-labelledby="stats-heading">
      <h2 id="stats-heading" className="mb-3 text-xl font-extrabold">
        Statistics
      </h2>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {statsFor(profile).map(({ label, value, icon }) => (
          <li key={label} className="flex items-center gap-3 rounded-2xl border-2 border-line p-3 sm:p-4">
            <span className="shrink-0">{icon}</span>
            <div className="min-w-0">
              <p className="text-xl font-black sm:text-2xl">{value}</p>
              <p className="text-sm leading-tight text-muted">{label}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function AchievementCard({ achievement }: { achievement: Achievement }) {
  const { unlocked } = achievement;
  return (
    <li
      className={`flex items-center gap-4 rounded-2xl border-2 p-4 ${
        unlocked ? "border-gold" : "border-dashed border-line-dark"
      }`}
    >
      <span
        className={`relative grid h-14 w-14 shrink-0 place-items-center rounded-full text-3xl ${
          unlocked ? "bg-gold-light" : "bg-locked grayscale"
        }`}
        aria-hidden="true"
      >
        <span className={unlocked ? "" : "opacity-40"}>{achievement.icon}</span>
        {!unlocked && (
          <span className="absolute -right-1 -bottom-1 grid h-7 w-7 place-items-center rounded-full border-2 border-white bg-locked-dark text-white">
            <LockIcon className="h-4 w-4" />
          </span>
        )}
      </span>
      <div className="min-w-0">
        <h3 className={`font-extrabold ${unlocked ? "" : "text-muted"}`}>{achievement.title}</h3>
        <p className="text-sm text-muted">{achievement.description}</p>
        <p className="mt-1 text-xs font-extrabold tracking-wide uppercase">
          {unlocked && achievement.unlocked_at ? (
            <>
              Unlocked{" "}
              <time dateTime={achievement.unlocked_at}>
                {formatDate(achievement.unlocked_at, { month: "short", day: "numeric", year: "numeric" })}
              </time>
            </>
          ) : unlocked ? (
            "Unlocked"
          ) : (
            <span className="text-muted">Locked</span>
          )}
        </p>
      </div>
    </li>
  );
}

function AchievementGrid({ achievements }: { achievements: Achievement[] }) {
  const unlockedCount = achievements.filter((a) => a.unlocked).length;
  return (
    <section aria-labelledby="achievements-heading">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 id="achievements-heading" className="text-xl font-extrabold">
          Achievements
        </h2>
        <p className="text-sm font-bold text-muted">
          {unlockedCount} of {achievements.length} unlocked
        </p>
      </div>
      {achievements.length === 0 ? (
        <p className="rounded-2xl border-2 border-line p-4 text-muted">No achievements to show yet.</p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {achievements.map((achievement) => (
            <AchievementCard key={achievement.code} achievement={achievement} />
          ))}
        </ul>
      )}
    </section>
  );
}

function ProfileSkeleton() {
  return (
    <div role="status" aria-label="Loading profile" className="flex flex-col gap-8">
      <div className="flex flex-col items-center gap-4 border-b-2 border-line pb-6 sm:flex-row sm:gap-6">
        <Skeleton className="h-24 w-24 rounded-full sm:h-28 sm:w-28" />
        <div className="flex w-full max-w-60 flex-col items-center gap-2 sm:items-start">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-8 w-36" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    </div>
  );
}

export default function ProfilePage() {
  const { data: profile, error, loading, reload } = useApi(api.profile);

  return (
    <div className="mx-auto max-w-3xl px-4 pt-6 pb-10">
      {(loading || !profile) && <h1 className="sr-only">Profile</h1>}
      {loading ? (
        <ProfileSkeleton />
      ) : error || !profile ? (
        <ErrorState error={error} onRetry={reload} title="Couldn't load your profile" />
      ) : (
        <div className="flex animate-fade-in flex-col gap-8">
          <ProfileHeader profile={profile} />
          <StatGrid profile={profile} />
          <AchievementGrid achievements={profile.achievements} />
        </div>
      )}
    </div>
  );
}

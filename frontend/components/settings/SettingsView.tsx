"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { CourseFlag } from "@/components/ui/CourseFlag";
import { Modal } from "@/components/ui/Modal";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { useUserStats } from "@/context/UserStatsContext";
import { api, errorMessage } from "@/lib/api";
import { notificationsSupported, requestReminderPermission } from "@/lib/reminder";
import { playSound } from "@/lib/sound";
import type { CourseSummary, Me } from "@/lib/types";

import { ProfileSection } from "./ProfileSection";
import { FieldError, RadioCard, SettingsSection } from "./shared";
import { ToggleRow } from "./Toggle";
import { useSettingsSave, type SettingsSaver } from "./useSettingsSave";

function LanguageSection({ me }: { me: Me }) {
  const { replace } = useUserStats();
  const [courses, setCourses] = useState<CourseSummary[] | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api.courses().then(
      (list) => !cancelled && setCourses(list),
      (err: unknown) => !cancelled && setLoadError(err),
    );
    return () => {
      cancelled = true;
    };
  }, [version]);

  async function choose(course: CourseSummary) {
    if (course.id === me.active_course.id) return;
    setPendingId(course.id);
    setError(null);
    try {
      replace(await api.setCourse(course.id));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPendingId(null);
    }
  }

  return (
    <SettingsSection id="language" title="Learning language" description="Switch courses any time. Progress in every course is kept.">
      {loadError !== null ? (
        <ErrorState
          error={loadError}
          onRetry={() => {
            setLoadError(null);
            setVersion((v) => v + 1);
          }}
          title="Couldn't load courses"
        />
      ) : courses === null ? (
        <div className="grid gap-3 sm:grid-cols-2" aria-label="Loading courses" role="status">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : (
        <div role="radiogroup" aria-label="Learning language" className="grid gap-3 sm:grid-cols-2">
          {courses.map((course) => {
            const checked = course.id === me.active_course.id;
            return (
              <RadioCard
                key={course.id}
                name="course"
                value={course.id}
                checked={checked}
                pending={pendingId !== null}
                onChange={() => void choose(course)}
              >
                <CourseFlag code={course.language_code} emoji={course.flag_emoji} className="h-8 w-12" />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2 font-extrabold">
                    {course.title}
                    {checked && (
                      <span className="rounded-lg bg-secondary px-2 py-0.5 text-xs text-white uppercase">Current</span>
                    )}
                  </span>
                  <span className="block text-xs text-muted">{course.description}</span>
                  <span className="block text-xs font-bold text-muted">
                    {course.lessons_completed}/{course.lessons_total} lessons · {course.progress}%
                  </span>
                </span>
                {pendingId === course.id && <span className="text-xs text-muted">Switching…</span>}
              </RadioCard>
            );
          })}
        </div>
      )}
      <FieldError message={error} />
    </SettingsSection>
  );
}

function NotificationsSection({ saver }: { saver: SettingsSaver }) {
  const reminder = saver.value("daily_reminder") ?? true;
  const alerts = saver.value("achievement_alerts") ?? true;
  const [permission, setPermission] = useState<string | null>(null);

  async function toggleReminder(next: boolean) {
    const saved = await saver.save({ daily_reminder: next });
    if (saved && next) setPermission(await requestReminderPermission());
  }

  const permissionText =
    permission === "granted"
      ? "Browser notifications on."
      : permission === "denied" || permission === "unsupported"
        ? "Browser notifications are blocked. You'll still see reminders in the app."
        : null;

  return (
    <SettingsSection id="notifications" title="Notifications">
      <ul className="divide-y-2 divide-line">
        <ToggleRow
          label="Daily streak reminder"
          description={
            notificationsSupported()
              ? "A reminder on the home screen (and a browser notification) until you practise today."
              : "A reminder on the home screen until you practise today."
          }
          checked={reminder}
          pending={saver.isPending("daily_reminder")}
          onChange={(next) => void toggleReminder(next)}
        >
          {permissionText && (
            <p aria-live="polite" className="text-sm font-bold text-muted">
              {permissionText}
            </p>
          )}
          <FieldError message={saver.error("daily_reminder")} />
        </ToggleRow>
        <ToggleRow
          label="Achievement alerts"
          description="Pop-ups on the lesson-complete screen when you unlock an achievement."
          checked={alerts}
          pending={saver.isPending("achievement_alerts")}
          onChange={(next) => void saver.save({ achievement_alerts: next })}
        >
          <FieldError message={saver.error("achievement_alerts")} />
        </ToggleRow>
      </ul>
    </SettingsSection>
  );
}

function SoundSection({ saver }: { saver: SettingsSaver }) {
  const sound = saver.value("sound_effects") ?? true;
  return (
    <SettingsSection id="sound" title="Sound">
      <ul className="divide-y-2 divide-line">
        <ToggleRow
          label="Sound effects"
          description="Chimes for correct answers, mistakes and finished lessons."
          checked={sound}
          pending={saver.isPending("sound_effects")}
          onChange={(next) => {
            void saver.save({ sound_effects: next });
            if (next) playSound("correct", true);
          }}
        >
          <div>
            <Button variant="outline" onClick={() => playSound("correct", true)}>
              🔊 Play a test sound
            </Button>
          </div>
          <FieldError message={saver.error("sound_effects")} />
        </ToggleRow>
      </ul>
    </SettingsSection>
  );
}

type ResetScope = "course" | "demo";

function AccountSection({ me }: { me: Me }) {
  const router = useRouter();
  const { refresh } = useUserStats();
  const [confirming, setConfirming] = useState<ResetScope | null>(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function reset(scope: ResetScope) {
    setPending(true);
    setError(null);
    try {
      const result = await api.reset(scope);
      await refresh();
      setMessage(result.message);
      setConfirming(null);
      if (scope === "demo") router.push("/");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  const courseTitle = me.active_course.title;
  return (
    <SettingsSection id="account" title="Account">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="font-bold text-muted">Username</dt>
        <dd className="font-extrabold">@{me.username}</dd>
        <dt className="font-bold text-muted">Total XP</dt>
        <dd className="font-extrabold">{me.xp}</dd>
      </dl>
      <div className="mt-4 flex flex-col gap-3 sm:flex-row">
        <Button variant="danger" onClick={() => setConfirming("course")}>
          Reset {courseTitle} progress
        </Button>
        <Button variant="outline" onClick={() => setConfirming("demo")}>
          Restore demo data
        </Button>
      </div>
      {message && (
        <p aria-live="polite" className="mt-3 rounded-xl bg-primary-light px-3 py-2 text-sm font-bold text-primary-ink">
          {message}
        </p>
      )}
      <FieldError message={error} />

      {confirming && (
        <Modal title={confirming === "course" ? `Reset ${courseTitle} progress?` : "Restore demo data?"} onClose={() => setConfirming(null)}>
          <div className="flex flex-col gap-2 text-center">
            <p className="text-xl font-black">
              {confirming === "course" ? `Reset your ${courseTitle} progress?` : "Restore the demo data?"}
            </p>
            <p className="text-muted">
              {confirming === "course"
                ? `Every ${courseTitle} lesson goes back to locked (the first skill stays open). Your XP, streak, gems and achievements are kept.`
                : "Everything is reset to the seeded demo: all learners, progress, XP, streaks, gems and achievements. Handy before a demo."}
            </p>
          </div>
          <div className="mt-6 flex flex-col gap-3">
            <Button variant="danger" fullWidth disabled={pending} onClick={() => void reset(confirming)}>
              {pending ? "Working…" : confirming === "course" ? "Reset progress" : "Restore demo"}
            </Button>
            <Button variant="ghost" fullWidth disabled={pending} onClick={() => setConfirming(null)}>
              Cancel
            </Button>
          </div>
          <FieldError message={error} />
        </Modal>
      )}
    </SettingsSection>
  );
}

export function SettingsView() {
  const { me, error, loading, refresh } = useUserStats();
  const saver = useSettingsSave();

  return (
    <div className="mx-auto max-w-3xl px-4 pt-6 pb-10">
      <h1 className="mb-6 text-3xl font-black">Settings</h1>
      {!me ? (
        loading ? (
          <div className="flex flex-col gap-5" role="status" aria-label="Loading settings">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-40" />
            ))}
          </div>
        ) : (
          <ErrorState error={error} onRetry={() => void refresh()} title="Couldn't load your settings" />
        )
      ) : (
        <div className="flex flex-col gap-5">
          <ProfileSection me={me} saver={saver} />
          <SettingsSection id="appearance" title="Appearance" description="Light, dark, or follow your device.">
            <ThemeToggle />
          </SettingsSection>
          <LanguageSection me={me} />
          <NotificationsSection saver={saver} />
          <SoundSection saver={saver} />
          <AccountSection me={me} />
        </div>
      )}
    </div>
  );
}

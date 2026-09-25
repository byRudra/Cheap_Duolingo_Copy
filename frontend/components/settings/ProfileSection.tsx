"use client";

import { useState } from "react";

import { Avatar } from "@/components/profile/Avatar";
import { Button } from "@/components/ui/Button";
import { CheckIcon } from "@/components/ui/icons";
import type { Me } from "@/lib/types";
import { DAILY_GOAL_CHOICES } from "@/lib/types";

import { FieldError, RadioCard, SettingsSection } from "./shared";
import type { SettingsSaver } from "./useSettingsSave";

const NAME_MAX = 30;

const AVATAR_COLORS: { value: string; name: string }[] = [
  { value: "#22C55E", name: "Green" },
  { value: "#1FA5EA", name: "Blue" },
  { value: "#8B5CF6", name: "Purple" },
  { value: "#EC4899", name: "Pink" },
  { value: "#EF4444", name: "Red" },
  { value: "#F97316", name: "Orange" },
  { value: "#EAB308", name: "Yellow" },
  { value: "#14B8A6", name: "Teal" },
];

const GOAL_LABELS: Record<(typeof DAILY_GOAL_CHOICES)[number], string> = {
  10: "Casual",
  20: "Regular",
  30: "Serious",
  50: "Intense",
};

const sameColor = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();

/** The palette always contains the learner's current colour (even a custom one). */
function paletteFor(current: string) {
  if (AVATAR_COLORS.some((c) => sameColor(c.value, current))) return AVATAR_COLORS;
  return [{ value: current, name: "Current colour" }, ...AVATAR_COLORS.slice(0, -1)];
}

function DisplayNameForm({ me, saver }: { me: Me; saver: SettingsSaver }) {
  const saved = me.settings.display_name;
  // null = untouched, so the field always mirrors the server value until edited.
  const [draft, setDraft] = useState<string | null>(null);
  const [justSaved, setJustSaved] = useState(false);
  const pending = saver.isPending("display_name");

  const value = draft ?? saved;
  const trimmed = value.trim();
  const valid = trimmed.length > 0 && trimmed.length <= NAME_MAX;
  const changed = trimmed !== saved;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!valid || !changed || pending) return;
    if (await saver.save({ display_name: trimmed })) {
      setDraft(null);
      setJustSaved(true);
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <label htmlFor="display-name" className="font-extrabold">
        Display name
      </label>
      <p id="display-name-hint" className="text-sm text-muted">
        Shown on your profile and the leaderboard. Up to {NAME_MAX} characters.
      </p>
      <div className="mt-2 flex flex-col gap-3 sm:flex-row">
        <input
          id="display-name"
          name="display_name"
          type="text"
          autoComplete="nickname"
          maxLength={NAME_MAX}
          value={value}
          onChange={(event) => {
            setDraft(event.target.value);
            setJustSaved(false);
          }}
          aria-describedby="display-name-hint display-name-status"
          aria-invalid={!valid || undefined}
          className="min-h-12 w-full min-w-0 flex-1 rounded-2xl border-2 border-line bg-surface px-4 font-bold text-ink placeholder:text-muted focus:border-secondary"
        />
        <Button type="submit" variant="secondary" disabled={!valid || !changed || pending} className="shrink-0">
          {pending ? "Saving…" : "Save"}
        </Button>
      </div>
      <p id="display-name-status" aria-live="polite" className="mt-1 min-h-5 text-sm font-bold">
        {!valid ? (
          <span className="text-danger-ink">Your name can&apos;t be empty.</span>
        ) : justSaved ? (
          <span className="inline-flex items-center gap-1 text-primary-ink">
            <CheckIcon className="h-4 w-4" /> Saved
          </span>
        ) : (
          <span className="text-muted">
            {trimmed.length}/{NAME_MAX}
          </span>
        )}
      </p>
      <FieldError message={saver.error("display_name")} />
    </form>
  );
}

function AvatarColorPicker({ me, saver }: { me: Me; saver: SettingsSaver }) {
  const current = saver.value("avatar_color") ?? me.settings.avatar_color;
  const pending = saver.isPending("avatar_color");

  return (
    <fieldset>
      <legend className="font-extrabold">Avatar colour</legend>
      <div className="mt-2 flex items-center gap-4">
        <Avatar name={me.settings.display_name} color={current} className="h-16 w-16 shrink-0 text-3xl" />
        <div className="flex flex-wrap gap-2">
          {paletteFor(me.settings.avatar_color).map((color) => {
            const checked = sameColor(color.value, current);
            return (
              <label
                key={color.value}
                title={color.name}
                className={`grid h-11 w-11 cursor-pointer place-items-center rounded-full border-4 transition-transform has-focus-visible:outline-3 has-focus-visible:outline-offset-2 has-focus-visible:outline-secondary ${
                  checked ? "scale-110 border-ink" : "border-transparent hover:scale-105"
                } ${pending ? "cursor-progress opacity-70" : ""}`}
                style={{ backgroundColor: color.value }}
              >
                <input
                  type="radio"
                  name="avatar_color"
                  value={color.value}
                  className="sr-only"
                  checked={checked}
                  aria-label={color.name}
                  aria-disabled={pending || undefined}
                  onChange={() => {
                    if (!pending && !checked) void saver.save({ avatar_color: color.value });
                  }}
                />
                {checked && (
                  <span aria-hidden="true" className="grid h-6 w-6 place-items-center rounded-full bg-black/35">
                    <CheckIcon className="h-4 w-4 text-white" />
                  </span>
                )}
              </label>
            );
          })}
        </div>
      </div>
      <FieldError message={saver.error("avatar_color")} />
    </fieldset>
  );
}

function DailyGoalPicker({ me, saver }: { me: Me; saver: SettingsSaver }) {
  const current = saver.value("daily_goal_xp") ?? me.settings.daily_goal_xp;
  const pending = saver.isPending("daily_goal_xp");

  return (
    <fieldset>
      <legend className="font-extrabold">Daily goal</legend>
      <p className="text-sm text-muted">How much XP you aim to earn each day.</p>
      <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {DAILY_GOAL_CHOICES.map((goal) => {
          const checked = current === goal;
          return (
            <RadioCard
              key={goal}
              name="daily_goal_xp"
              value={goal}
              checked={checked}
              pending={pending}
              onChange={() => {
                if (!checked) void saver.save({ daily_goal_xp: goal });
              }}
              className="flex-col items-start gap-0.5"
            >
              <span className={`font-extrabold ${checked ? "text-secondary-ink" : ""}`}>{GOAL_LABELS[goal]}</span>
              <span className="text-sm text-muted">{goal} XP per day</span>
            </RadioCard>
          );
        })}
      </div>
      <FieldError message={saver.error("daily_goal_xp")} />
    </fieldset>
  );
}

export function ProfileSection({ me, saver }: { me: Me; saver: SettingsSaver }) {
  return (
    <SettingsSection id="profile" title="Profile">
      <div className="flex flex-col gap-6">
        <DisplayNameForm me={me} saver={saver} />
        <AvatarColorPicker me={me} saver={saver} />
        <DailyGoalPicker me={me} saver={saver} />
      </div>
    </SettingsSection>
  );
}

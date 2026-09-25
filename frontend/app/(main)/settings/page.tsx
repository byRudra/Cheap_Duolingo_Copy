import type { Metadata } from "next";

import { Mascot } from "@/components/Mascot";

export const metadata: Metadata = {
  title: "Settings · Habla",
};

interface SettingRow {
  id: string;
  label: string;
  description: string;
  /** Preview-only default; nothing is persisted. */
  on: boolean;
}

interface SettingSection {
  id: string;
  title: string;
  rows: SettingRow[];
}

const SECTIONS: SettingSection[] = [
  {
    id: "profile",
    title: "Profile",
    rows: [
      { id: "public-profile", label: "Public profile", description: "Let other learners see your stats.", on: true },
      { id: "show-leaderboard", label: "Show on leaderboard", description: "Appear in the rankings.", on: true },
    ],
  },
  {
    id: "notifications",
    title: "Notifications",
    rows: [
      { id: "daily-reminder", label: "Daily reminder", description: "A nudge to practice every day.", on: true },
      { id: "streak-alerts", label: "Streak alerts", description: "Warn me before my streak ends.", on: true },
      { id: "weekly-report", label: "Weekly report", description: "A summary of your week by email.", on: false },
    ],
  },
  {
    id: "sound",
    title: "Sound",
    rows: [
      { id: "sound-effects", label: "Sound effects", description: "Play sounds for right and wrong answers.", on: true },
      { id: "cheers", label: "Motivational messages", description: "Let Pico cheer you on in lessons.", on: true },
    ],
  },
  {
    id: "language",
    title: "Language",
    rows: [
      { id: "immersion", label: "Spanish interface", description: "Show menus and buttons in Spanish.", on: false },
      { id: "listening", label: "Listening exercises", description: "Include audio questions in lessons.", on: false },
    ],
  },
  {
    id: "account",
    title: "Account",
    rows: [
      { id: "email-updates", label: "Email updates", description: "Product news and learning tips.", on: false },
      { id: "private-mode", label: "Private mode", description: "Hide your activity from other learners.", on: false },
    ],
  },
];

function ComingSoonSwitch({ row }: { row: SettingRow }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={row.on}
      aria-labelledby={`${row.id}-label`}
      aria-describedby={`${row.id}-desc ${row.id}-soon`}
      disabled
      className="grid min-h-11 min-w-14 cursor-not-allowed place-items-center"
    >
      <span
        aria-hidden="true"
        className={`flex h-8 w-14 items-center rounded-full border-2 p-0.5 ${
          row.on ? "justify-end border-primary/40 bg-primary/35" : "justify-start border-line-dark bg-locked"
        }`}
      >
        <span className="h-6 w-6 rounded-full bg-white shadow-sm" />
      </span>
    </button>
  );
}

function SettingRowItem({ row }: { row: SettingRow }) {
  return (
    <li className="flex min-h-16 items-center justify-between gap-4 py-3">
      <div className="min-w-0">
        <p id={`${row.id}-label`} className="font-extrabold">
          {row.label}
        </p>
        <p id={`${row.id}-desc`} className="text-sm text-muted">
          {row.description}
        </p>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1 sm:flex-row sm:items-center sm:gap-3">
        <span
          id={`${row.id}-soon`}
          className="rounded-lg bg-gold-light px-2 py-0.5 text-[11px] font-extrabold tracking-wide whitespace-nowrap uppercase"
        >
          Coming soon
        </span>
        <ComingSoonSwitch row={row} />
      </div>
    </li>
  );
}

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 pt-6 pb-10">
      <h1 className="mb-4 text-3xl font-black">Settings</h1>

      <div role="note" className="mb-6 flex items-center gap-3 rounded-2xl border-2 border-secondary bg-secondary-light p-4">
        <Mascot className="h-12 w-12 shrink-0" />
        <p className="text-sm">
          <strong className="font-extrabold">Settings are a preview.</strong> These options are coming soon, so
          nothing on this page is saved yet.
        </p>
      </div>

      <div className="flex flex-col gap-5">
        {SECTIONS.map((section) => (
          <section
            key={section.id}
            aria-labelledby={`${section.id}-heading`}
            className="rounded-2xl border-2 border-line px-4 pt-4 pb-1 sm:px-5"
          >
            <h2 id={`${section.id}-heading`} className="text-lg font-extrabold">
              {section.title}
            </h2>
            <ul className="divide-y-2 divide-line">
              {section.rows.map((row) => (
                <SettingRowItem key={row.id} row={row} />
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

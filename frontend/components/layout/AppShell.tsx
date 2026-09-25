"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { APP_NAME, APP_WORDMARK } from "@/lib/brand";

import { Mascot } from "../Mascot";
import { HomeIcon, SettingsIcon, TrophyIcon, UserIcon } from "../ui/icons";
import { ThemeToggle } from "../ui/ThemeToggle";
import { CourseSwitcher } from "./CourseSwitcher";
import { StatPills } from "./StatPills";

const NAV = [
  { href: "/", label: "Learn", Icon: HomeIcon },
  { href: "/leaderboard", label: "Leaderboard", Icon: TrophyIcon },
  { href: "/profile", label: "Profile", Icon: UserIcon },
  { href: "/settings", label: "Settings", Icon: SettingsIcon },
] as const;

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen lg:pl-64">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r-2 border-line px-4 py-6 lg:flex">
        <Link href="/" className="mb-8 flex items-center gap-2 px-3" aria-label={`${APP_NAME} home`}>
          <Mascot className="h-11 w-11" />
          <span className="text-3xl font-black tracking-tight text-primary">{APP_WORDMARK}</span>
        </Link>
        <nav aria-label="Main" className="flex flex-col gap-2">
          {NAV.map(({ href, label, Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-12 items-center gap-4 rounded-2xl border-2 px-4 py-2 text-sm font-extrabold tracking-wide uppercase transition-colors ${
                  active
                    ? "border-secondary/60 bg-secondary-light text-secondary"
                    : "border-transparent text-muted hover:bg-surface"
                }`}
              >
                <Icon className="h-7 w-7" />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto flex flex-col gap-2 px-1">
          <p className="px-2 text-xs font-black tracking-wide text-muted uppercase">Theme</p>
          <ThemeToggle compact />
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b-2 border-line bg-card/95 px-4 backdrop-blur lg:hidden">
        <div className="flex items-center gap-1">
          <Link href="/" aria-label={`${APP_NAME} home`} className="grid h-11 w-11 place-items-center">
            <Mascot className="h-9 w-9" />
          </Link>
          <CourseSwitcher />
        </div>
        <StatPills />
      </header>

      <main className="pb-24 lg:pb-10">{children}</main>

      {/* Mobile bottom tabs */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-30 flex h-16 items-stretch justify-around border-t-2 border-line bg-card lg:hidden"
      >
        {NAV.map(({ href, label, Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              aria-label={label}
              aria-current={active ? "page" : undefined}
              className={`flex min-w-16 flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-extrabold uppercase ${
                active ? "text-secondary" : "text-muted"
              }`}
            >
              <span className={`rounded-xl px-3 py-0.5 ${active ? "bg-secondary-light" : ""}`}>
                <Icon className="h-7 w-7" />
              </span>
              {label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

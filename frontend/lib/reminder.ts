"use client";

import { APP_NAME } from "./brand";

const SENT_KEY = "reminder-sent-on";

export function notificationsSupported(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}

/** Ask for browser notification permission (called when the reminder is switched on). */
export async function requestReminderPermission(): Promise<NotificationPermission | "unsupported"> {
  if (!notificationsSupported()) return "unsupported";
  if (Notification.permission !== "default") return Notification.permission;
  return Notification.requestPermission();
}

/** At most one browser notification per day while today's streak is still open. */
export function maybeSendStreakReminder(today: string, streak: number): void {
  if (!notificationsSupported() || Notification.permission !== "granted") return;
  try {
    if (localStorage.getItem(SENT_KEY) === today) return;
    localStorage.setItem(SENT_KEY, today);
  } catch {
    return;
  }
  const body =
    streak > 0
      ? `Your ${streak}-day streak is waiting. A quick lesson keeps it alive!`
      : "A 3-minute lesson is all it takes to start a streak today.";
  new Notification(`${APP_NAME} reminder`, { body, icon: "/icon.svg" });
}

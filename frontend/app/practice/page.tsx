import type { Metadata } from "next";

import { LessonPlayer } from "@/components/lesson/LessonPlayer";

export const metadata: Metadata = { title: "Heart practice" };

export default function PracticePage() {
  return <LessonPlayer practice />;
}

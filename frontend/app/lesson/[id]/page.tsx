import { notFound } from "next/navigation";

import { LessonPlayer } from "@/components/lesson/LessonPlayer";

export default async function LessonPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const lessonId = Number(id);
  if (!Number.isInteger(lessonId) || lessonId <= 0) notFound();
  return <LessonPlayer lessonId={lessonId} />;
}

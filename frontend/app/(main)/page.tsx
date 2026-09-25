"use client";

import { RightRail } from "@/components/home/RightRail";
import { LearningPath } from "@/components/path/LearningPath";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";

function PathSkeleton() {
  return (
    <div className="flex flex-col items-center gap-9" aria-label="Loading your path" role="status">
      <Skeleton className="h-24 w-full" />
      {[0, 51, 72, 51, 0].map((x, i) => (
        <div key={i} style={{ transform: `translateX(${x}px)` }}>
          <Skeleton className="h-18 w-18 rounded-full" />
        </div>
      ))}
    </div>
  );
}

export default function HomePage() {
  const { data: course, error, loading, reload } = useApi(api.course);

  return (
    <div className="mx-auto flex max-w-5xl gap-12 px-4 pt-6 lg:px-8">
      <div className="min-w-0 flex-1 pb-40">
        <div className="mx-auto max-w-md">
          {loading ? <PathSkeleton /> : error || !course ? <ErrorState error={error} onRetry={reload} /> : <LearningPath course={course} />}
        </div>
      </div>
      <aside className="sticky top-6 hidden h-fit w-80 shrink-0 lg:block" aria-label="Your stats">
        <RightRail flag={course?.language_code} />
      </aside>
    </div>
  );
}

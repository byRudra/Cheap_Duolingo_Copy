import type {
  Achievement,
  AnswerPayload,
  AnswerResult,
  AttemptStart,
  CompletionSummary,
  Course,
  Leaderboard,
  LessonMeta,
  Me,
  Profile,
  RefillResult,
} from "./types";

const BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** Typed error carrying the backend's `{ detail: { code, message } }` body. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function isApiError(error: unknown, code?: string): error is ApiError {
  return error instanceof ApiError && (code === undefined || error.code === code);
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Something went wrong. Please try again.";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Can't reach the server. Is the backend running?");
  }

  if (!response.ok) {
    let code = `HTTP_${response.status}`;
    let message = `Request failed (${response.status}).`;
    try {
      const body: unknown = await response.json();
      const detail = (body as { detail?: unknown }).detail;
      if (detail && typeof detail === "object" && "code" in detail && "message" in detail) {
        code = String(detail.code);
        message = String(detail.message);
      }
    } catch {
      // Non-JSON error body: keep the generic message.
    }
    throw new ApiError(response.status, code, message);
  }
  return (await response.json()) as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  me: () => request<Me>("/api/me"),
  refillHearts: () => post<RefillResult>("/api/me/hearts/refill"),
  course: () => request<Course>("/api/course"),
  lesson: (lessonId: number) => request<LessonMeta>(`/api/lessons/${lessonId}`),
  startLesson: (lessonId: number) => post<AttemptStart>(`/api/lessons/${lessonId}/start`),
  answer: (attemptId: number, exerciseId: number, answer: AnswerPayload) =>
    post<AnswerResult>(`/api/attempts/${attemptId}/answer`, { exercise_id: exerciseId, answer }),
  complete: (attemptId: number) => post<CompletionSummary>(`/api/attempts/${attemptId}/complete`),
  profile: () => request<Profile>("/api/profile"),
  leaderboard: () => request<Leaderboard>("/api/leaderboard"),
  achievements: () => request<Achievement[]>("/api/achievements"),
};

// Mirrors backend/app/schemas.py. Server state is only ever read from these.

export type SkillState = "LOCKED" | "AVAILABLE" | "IN_PROGRESS" | "COMPLETED";
export type LessonStatus = "LOCKED" | "AVAILABLE" | "COMPLETED";
export type AttemptStatus = "IN_PROGRESS" | "COMPLETED" | "FAILED";
export type AttemptMode = "LESSON" | "PRACTICE";
export type ExerciseType =
  | "MULTIPLE_CHOICE"
  | "WORD_BANK"
  | "MATCH_PAIRS"
  | "FILL_BLANK"
  | "TYPE_ANSWER";

// ── Courses ──────────────────────────────────────────────────────────────────

export interface CourseBrief {
  id: number;
  title: string;
  language_code: string;
  flag_emoji: string;
}

export interface CourseSummary extends CourseBrief {
  description: string;
  is_active: boolean;
  lessons_completed: number;
  lessons_total: number;
  progress: number;
}

// ── Settings ─────────────────────────────────────────────────────────────────

export const DAILY_GOAL_CHOICES = [10, 20, 30, 50] as const;

export interface Settings {
  display_name: string;
  avatar_color: string;
  daily_goal_xp: number;
  sound_effects: boolean;
  daily_reminder: boolean;
  achievement_alerts: boolean;
}

export type SettingsUpdate = Partial<Settings>;

export interface ResetResult {
  scope: "course" | "demo";
  message: string;
}

// ── /api/me ──────────────────────────────────────────────────────────────────

export interface DailyGoal {
  goal: number;
  earned: number;
  met: boolean;
}

export interface Me {
  id: number;
  username: string;
  display_name: string;
  avatar_color: string;
  xp: number;
  gems: number;
  hearts: number;
  max_hearts: number;
  next_heart_at: string | null;
  heart_regen_minutes: number;
  refill_cost: number;
  streak: number;
  longest_streak: number;
  streak_extended_today: boolean;
  daily_goal: DailyGoal;
  today: string;
  active_course: CourseBrief;
  settings: Settings;
}

export interface RefillResult {
  hearts: number;
  gems: number;
  next_heart_at: string | null;
}

// ── /api/course ──────────────────────────────────────────────────────────────

export interface LessonNode {
  id: number;
  title: string;
  order_index: number;
  status: LessonStatus;
}

export interface SkillNode {
  id: number;
  title: string;
  icon: string;
  order_index: number;
  state: SkillState;
  progress: number;
  lessons_completed: number;
  lessons_total: number;
  next_lesson_id: number | null;
  lessons: LessonNode[];
}

export interface UnitNode {
  id: number;
  title: string;
  description: string;
  color: string;
  order_index: number;
  skills: SkillNode[];
}

export interface Course {
  id: number;
  title: string;
  language_code: string;
  flag_emoji: string;
  current_skill_id: number | null;
  units: UnitNode[];
}

// ── Lessons and attempts ─────────────────────────────────────────────────────

export interface LessonMeta {
  id: number;
  title: string;
  order_index: number;
  lessons_in_skill: number;
  exercise_count: number;
  status: LessonStatus;
  is_practice: boolean;
  skill_id: number;
  skill_title: string;
  skill_icon: string;
  unit_title: string;
  unit_color: string;
  xp_reward: number;
  course_id: number;
  course_title: string;
  language_code: string;
}

export interface MultipleChoicePayload {
  options: string[];
}
export interface WordBankPayload {
  tiles: string[];
}
export interface MatchPairsPayload {
  pairs: { left: string; right: string }[];
}
export interface FillBlankPayload {
  sentence: string;
  options: string[];
}
export interface TypeAnswerPayload {
  placeholder?: string;
}

interface ExerciseBase<T extends ExerciseType, P> {
  id: number;
  type: T;
  prompt: string;
  payload: P;
}

export type Exercise =
  | ExerciseBase<"MULTIPLE_CHOICE", MultipleChoicePayload>
  | ExerciseBase<"WORD_BANK", WordBankPayload>
  | ExerciseBase<"MATCH_PAIRS", MatchPairsPayload>
  | ExerciseBase<"FILL_BLANK", FillBlankPayload>
  | ExerciseBase<"TYPE_ANSWER", TypeAnswerPayload>;

export type ExerciseOf<T extends ExerciseType> = Extract<Exercise, { type: T }>;

/** What each exercise type submits (§5). */
export type AnswerPayload =
  | { answer: string }
  | { tiles: string[] }
  | { completed: true }
  | { text: string };

export interface AttemptStart {
  attempt_id: number;
  mode: AttemptMode;
  lesson: LessonMeta;
  exercises: Exercise[];
  hearts: number;
  max_hearts: number;
}

export interface AnswerResult {
  correct: boolean;
  correct_answer: string | null;
  explanation: string | null;
  note: string | null;
  hearts: number;
  out_of_hearts: boolean;
}

export interface AchievementBrief {
  code: string;
  title: string;
  icon: string;
}

export interface CompletionSummary {
  attempt_id: number;
  status: AttemptStatus;
  mode: AttemptMode;
  hearts: number;
  hearts_restored: number;
  xp_earned: number;
  perfect: boolean;
  already_completed: boolean;
  mistakes: number;
  accuracy: number;
  total_xp: number;
  streak: { before: number; after: number; extended: boolean };
  daily_goal: { earned: number; goal: number; just_met: boolean };
  skill: { id: number; title: string; progress: number; state: SkillState };
  newly_unlocked_skill: { id: number; title: string } | null;
  new_achievements: AchievementBrief[];
}

// ── Social ───────────────────────────────────────────────────────────────────

export interface Achievement {
  code: string;
  title: string;
  description: string;
  icon: string;
  unlocked: boolean;
  unlocked_at: string | null;
}

export interface Profile {
  id: number;
  username: string;
  display_name: string;
  avatar_color: string;
  joined_at: string;
  total_xp: number;
  gems: number;
  streak: number;
  longest_streak: number;
  lessons_completed: number;
  skills_completed: number;
  skills_total: number;
  course_title: string;
  course_flag: string;
  course_language_code: string;
  courses: CourseSummary[];
  achievements: Achievement[];
}

export interface LeaderboardEntry {
  rank: number;
  user_id: number;
  display_name: string;
  avatar_color: string;
  xp: number;
  is_current_user: boolean;
}

export interface Leaderboard {
  entries: LeaderboardEntry[];
}

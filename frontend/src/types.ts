export type User = { user_uid: string; username: string; email: string | null; created_at: string };
export type Subject = { subject_uid: string; name: string; user_uid: string; exam_date: string | null };
export type Topic = { topic_uid: string; name: string; subject_uid: string; difficulty: string | null; is_done: boolean };
export type Task = { task_uid: string; title: string; topic_uid: string; is_done: boolean; deadline: string | null; priority: "LOW" | "MEDIUM" | "HIGH"; notes: string | null };
export type Session = { study_uid: string; subject_uid: string; topic_uid: string | null; task_uid: string | null; started_at: string; duration_minutes: number | null; notes: string | null };
export type Page<T> = { items: T[]; page: number; page_size: number; total: number; pages: number };
export type GeneratedNotes = {
  title: string;
  summary: string;
  sections: { heading: string; content: string }[];
  key_points: string[];
  review_questions: string[];
};
export type GeneratedStudyPlan = {
  title: string;
  overview: string;
  steps: { day: number; title: string; objective: string; activities: string[]; duration_minutes: number }[];
  success_criteria: string[];
};
export type AiMaterial = {
  material_uid: string;
  topic_uid: string;
  task_uid: string | null;
  material_type: "notes" | "plan";
  title: string;
  content: GeneratedNotes | GeneratedStudyPlan;
  created_at: string;
};

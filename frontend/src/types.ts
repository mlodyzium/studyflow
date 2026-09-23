export type User = { user_uid: string; username: string; email: string | null; created_at: string };
export type Subject = { subject_uid: string; name: string; user_uid: string; exam_date: string | null };
export type Topic = { topic_uid: string; name: string; subject_uid: string; difficulty: string | null; is_done: boolean };
export type Task = { task_uid: string; title: string; topic_uid: string; is_done: boolean; deadline: string | null; priority: "LOW" | "MEDIUM" | "HIGH"; notes: string | null };
export type Session = { study_uid: string; title: string; subject_uid: string; topic_uid: string | null; task_uid: string | null; started_at: string; duration_minutes: number | null; notes: string | null };
export type GeneratedSessionNote = { title: string; notes: string };
export type Page<T> = { items: T[]; page: number; page_size: number; total: number; pages: number };
export type GeneratedNotes = {
  task_title: string;
  title: string;
  summary: string;
  sections: { heading: string; content: string }[];
  key_points: string[];
  review_questions: string[];
};
export type GeneratedStudyPlan = {
  task_title: string;
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
export type AiConversation = { conversation_uid: string; title: string; user_message: string; assistant_message: string; proposal: T3achProposal; created_at: string };
export type T3achTaskProposal = { title: string; priority: "LOW" | "MEDIUM" | "HIGH"; deadline_days: number | null; notes: string | null };
export type T3achProposal = { reply: string; needs_clarification: boolean; question: string | null; subject_name: string | null; topic_name: string | null; difficulty: string | null; tasks: T3achTaskProposal[]; intent: "organize"|"study_plan"|"notes"|"edit"; target_kind: "subject"|"topic"|"task"|null; target_name: string|null; new_name: string|null; new_priority: "LOW"|"MEDIUM"|"HIGH"|null; new_is_done: boolean|null; days:number; minutes_per_day:number; preview: GeneratedNotes|GeneratedStudyPlan|null };
export type T3achExecuteResult = { message: string; subject_uid: string|null; topic_uid: string|null; task_uids: string[]; created_subject: boolean; created_topic: boolean };

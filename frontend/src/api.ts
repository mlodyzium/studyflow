import type { Page, Session, Subject, Task, Topic, User } from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "/api";
let token = localStorage.getItem("studyflow_token");

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers },
  });
  if (response.status === 401) { clearToken(); window.dispatchEvent(new Event("studyflow:logout")); }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "Coś poszło nie tak. Spróbuj ponownie.");
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export function setToken(value: string) { token = value; localStorage.setItem("studyflow_token", value); }
export function clearToken() { token = null; localStorage.removeItem("studyflow_token"); }
export const hasToken = () => Boolean(token);

export const api = {
  login: (username: string, password: string) => request<{ access_token: string }>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  register: (username: string, email: string, password: string) => request<User>("/auth/register", { method: "POST", body: JSON.stringify({ username, email: email || null, password }) }),
  me: () => request<User>("/users/me"),
  updateMe: (data: { username?: string; email?: string | null; password?: string }) => request<User>("/users/me", { method: "PATCH", body: JSON.stringify(data) }),
  subjects: () => request<Page<Subject>>("/subjects?page_size=100"),
  topics: () => request<Page<Topic>>("/topics?page_size=100"),
  tasks: () => request<Page<Task>>("/tasks?page_size=100&sort=deadline&order=asc"),
  sessions: () => request<Page<Session>>("/study-sessions?page_size=100"),
  addSubject: (data: { name: string; exam_date: string | null }) => request<Subject>("/subjects", { method: "POST", body: JSON.stringify(data) }),
  updateSubject: (id: string, data: { name?: string; exam_date?: string | null }) => request<Subject>(`/subjects/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteSubject: (id: string) => request<void>(`/subjects/${id}`, { method: "DELETE" }),
  addTopic: (data: { name: string; subject_uid: string; difficulty: string }) => request<Topic>("/topics", { method: "POST", body: JSON.stringify(data) }),
  updateTopic: (id: string, data: Partial<Pick<Topic, "name" | "subject_uid" | "difficulty" | "is_done">>) => request<Topic>(`/topics/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteTopic: (id: string) => request<void>(`/topics/${id}`, { method: "DELETE" }),
  addTask: (data: { title: string; topic_uid: string; deadline: string | null; priority: string; notes?: string | null }) => request<Task>("/tasks", { method: "POST", body: JSON.stringify(data) }),
  updateTask: (id: string, data: Partial<Task>) => request<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteTask: (id: string) => request<void>(`/tasks/${id}`, { method: "DELETE" }),
  addSession: (data: { subject_uid: string; topic_uid?: string | null; task_uid?: string | null; duration_minutes: number; notes: string | null }) => request<Session>("/study-sessions", { method: "POST", body: JSON.stringify(data) }),
  deleteSession: (id: string) => request<void>(`/study-sessions/${id}`, { method: "DELETE" }),
  updateSession: (id: string, data: { subject_uid?: string; topic_uid?: string | null; task_uid?: string | null; duration_minutes?: number; notes?: string | null }) => request<Session>(`/study-sessions/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
};

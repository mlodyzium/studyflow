import type { AiConversation, AiMaterial, GeneratedNotes, GeneratedStudyPlan, Page, PlanDay, Review, Session, StudyPlan, Subject, T3achExecuteResult, T3achProposal, Task, Topic, User } from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "/api";
let token = localStorage.getItem("studyflow_token");

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try { response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers },
  }); } catch { throw new Error("Nie można połączyć się ze StudyFlow. Sprawdź adres strony i czy serwer działa."); }
  if (response.status === 401) { clearToken(); window.dispatchEvent(new Event("studyflow:logout")); }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) && body.detail[0]?.msg ? String(body.detail[0].msg).replace(/^Value error, /, "") : "Coś poszło nie tak. Spróbuj ponownie.";
    const retrySeconds=Number(response.headers.get("Retry-After"));
    const wait=Number.isFinite(retrySeconds)&&retrySeconds>0
      ?retrySeconds>=60?`${Math.ceil(retrySeconds/60)} min`:`${Math.ceil(retrySeconds)} s`
      :null;
    throw new Error(response.status === 429 && wait ? `${detail} Ponów za ${wait}.` : detail);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export function setToken(value: string) { token = value; localStorage.setItem("studyflow_token", value); }
export function clearToken() { token = null; localStorage.removeItem("studyflow_token"); }
export const hasToken = () => Boolean(token);

async function allPages<T>(path:string):Promise<Page<T>> {
  const first=await request<Page<T>>(`${path}${path.includes("?")?"&":"?"}page=1&page_size=100`);
  if(first.pages<=1)return first;
  const rest=await Promise.all(Array.from({length:first.pages-1},(_,i)=>request<Page<T>>(`${path}${path.includes("?")?"&":"?"}page=${i+2}&page_size=100`)));
  return {...first,items:[...first.items,...rest.flatMap(page=>page.items)]};
}

async function download(path:string,filename:string,print=false):Promise<void>{
  const preview=print?window.open("about:blank","_blank"):null;
  try{
    const response=await fetch(`${BASE}${path}`,{headers:token?{Authorization:`Bearer ${token}`}:{}});
    if(!response.ok)throw new Error("Nie udało się pobrać pliku.");
    const url=URL.createObjectURL(await response.blob());
    if(print){if(preview)preview.location.href=url;else{const link=document.createElement("a");link.href=url;link.download=filename;link.click()}window.setTimeout(()=>URL.revokeObjectURL(url),60000)}
    else{const link=document.createElement("a");link.href=url;link.download=filename;link.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000)}
  }catch(err){preview?.close();throw err}
}

async function speech(text: string): Promise<Blob> {
  let response:Response;
  try{response = await fetch(`${BASE}/ai/t3ach/speech`, {method: "POST", headers: {"Content-Type": "application/json", ...(token ? {Authorization: `Bearer ${token}`} : {})}, body: JSON.stringify({text})})}
  catch{throw new Error("Nie można połączyć się z generatorem głosu. Sprawdź połączenie i spróbuj ponownie.")}
  if (!response.ok) {const body=await response.json().catch(()=>({}));throw new Error(typeof body.detail==="string"?body.detail:"Nie udało się wygenerować głosu.")}
  return response.blob();
}

export const api = {
  login: (username: string, password: string) => request<{ access_token: string }>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  register: (username: string, email: string, password: string) => request<User>("/auth/register", { method: "POST", body: JSON.stringify({ username: username.trim(), email: email.trim() || null, password, confirm_password: password, timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||"Europe/Warsaw" }) }),
  me: () => request<User>("/users/me"),
  updateMe: (data: { username?: string; email?: string | null; password?: string;timezone?:string;preferred_minutes?:number;preferred_study_time?:string;task_shortcut?:string;ai_shortcut?:string;onboarding_complete?:boolean }) => request<User>("/users/me", { method: "PATCH", body: JSON.stringify(data.password ? {...data,confirm_password:data.password} : data) }),
  subjects: () => allPages<Subject>("/subjects"),
  archivedSubjects: () => allPages<Subject>("/subjects?archived=true"),
  topics: () => allPages<Topic>("/topics"),
  tasks: () => allPages<Task>("/tasks?sort=deadline&order=asc"),
  sessions: () => allPages<Session>("/study-sessions"),
  addSubject: (data: { name: string; exam_date: string | null;color?:string;tags?:string[] }) => request<Subject>("/subjects", { method: "POST", body: JSON.stringify(data) }),
  updateSubject: (id: string, data: { name?: string; exam_date?: string | null;color?:string;tags?:string[];archived?:boolean }) => request<Subject>(`/subjects/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteSubject: (id: string) => request<void>(`/subjects/${id}`, { method: "DELETE" }),
  addTopic: (data: { name: string; subject_uid: string; difficulty: string }) => request<Topic>("/topics", { method: "POST", body: JSON.stringify(data) }),
  updateTopic: (id: string, data: Partial<Pick<Topic, "name" | "subject_uid" | "difficulty" | "is_done">>) => request<Topic>(`/topics/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteTopic: (id: string) => request<void>(`/topics/${id}`, { method: "DELETE" }),
  generateNotes: (id: string, data: { detail_level: "short" | "standard" | "detailed"; task_uid?: string | null; custom_goal?: string | null }) =>
    request<GeneratedNotes>(`/ai/topics/${id}/notes`, { method: "POST", body: JSON.stringify({ language: "polski", ...data }) }),
  generatePlan: (id: string, data: { days: number; minutes_per_day: number; task_uid?: string | null; custom_goal?: string | null }) =>
    request<GeneratedStudyPlan>(`/ai/topics/${id}/plan`, { method: "POST", body: JSON.stringify({ language: "polski", sent_at:new Date().toISOString(), ...data }) }),
  manualNote:(id:string,title:string,content:string)=>request<GeneratedNotes>(`/ai/topics/${id}/manual-note`,{method:"POST",body:JSON.stringify({title,content})}),
  fallbackPlan:(id:string,goal:string,days:number,minutes_per_day:number)=>request<GeneratedStudyPlan>(`/ai/topics/${id}/fallback-plan`,{method:"POST",body:JSON.stringify({goal,days,minutes_per_day,sent_at:new Date().toISOString()})}),
  aiMaterials: (taskId?: string) => request<AiMaterial[]>(`/ai/materials${taskId ? `?task_uid=${taskId}` : ""}`),
  deleteAiMaterial: (id: string) => request<void>(`/ai/materials/${id}`, { method: "DELETE" }),
  t3achHistory: () => request<AiConversation[]>("/ai/t3ach/history"),
  deleteT3achConversation: (id: string) => request<void>(`/ai/t3ach/history/${id}`, { method: "DELETE" }),
  addTask: (data: { title: string; topic_uid: string; deadline: string | null; priority: string; notes?: string | null }) => request<Task>("/tasks", { method: "POST", body: JSON.stringify(data) }),
  updateTask: (id: string, data: Partial<Task>) => request<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteTask: (id: string) => request<void>(`/tasks/${id}`, { method: "DELETE" }),
  addSession: (data: { title: string; subject_uid: string; topic_uid?: string | null; task_uid?: string | null; duration_minutes: number; notes: string | null }) => request<Session>("/study-sessions", { method: "POST", body: JSON.stringify(data) }),
  deleteSession: (id: string) => request<void>(`/study-sessions/${id}`, { method: "DELETE" }),
  updateSession: (id: string, data: { title?: string; subject_uid?: string; topic_uid?: string | null; task_uid?: string | null; duration_minutes?: number; notes?: string | null }) => request<Session>(`/study-sessions/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  generateSessionNote: (description: string) => request<import("./types").GeneratedSessionNote>("/ai/session-note", { method: "POST", body: JSON.stringify({ description, language: "polski" }) }),
  proposeT3ach: (message: string, history: {role:"user"|"assistant";text:string}[] = [], previous_proposal: T3achProposal|null = null) => request<T3achProposal>("/ai/t3ach/propose", { method: "POST", body: JSON.stringify({ message, language: "polski", history: history.map(item=>({...item,text:item.text.slice(0,500)})), previous_proposal_uid: previous_proposal?.proposal_uid, sent_at:new Date().toISOString() }) }),
  executeT3ach: (proposal: T3achProposal) => request<T3achExecuteResult>("/ai/t3ach/execute", { method: "POST", body: JSON.stringify({proposal_uid:proposal.proposal_uid}) }),
  t3achSpeech: speech,
  plans:()=>request<StudyPlan[]>("/plans"),
  updatePlanDay:(planId:string,dayId:string,data:Partial<Pick<PlanDay,"is_done"|"scheduled_date"|"scheduled_time"|"duration_minutes"|"title"|"objective"|"activities">>)=>request<PlanDay>(`/plans/${planId}/days/${dayId}`,{method:"PATCH",body:JSON.stringify(data)}),
  shiftPlan:(id:string,start_date:string)=>request<StudyPlan>(`/plans/${id}/shift`,{method:"PATCH",body:JSON.stringify({start_date})}),
  duplicatePlan:(id:string,start_date:string)=>request<StudyPlan>(`/plans/${id}/duplicate`,{method:"POST",body:JSON.stringify({start_date})}),
  regeneratePlanDay:(planId:string,dayId:string,custom_goal:string)=>request<PlanDay>(`/plans/${planId}/days/${dayId}/regenerate`,{method:"POST",body:JSON.stringify({custom_goal})}),
  createPlanTasks:(id:string,create_tasks:boolean)=>request<StudyPlan>(`/plans/${id}/calendar-tasks`,{method:"POST",body:JSON.stringify({create_tasks})}),
  reviews:()=>request<Review[]>("/reviews"),
  answerReview:(id:string,rating:"forgot"|"hard"|"easy")=>request<Review>(`/reviews/${id}/answer`,{method:"POST",body:JSON.stringify({rating})}),
  exportCalendar:()=>download("/calendar/export.ics","studyflow.ics"),
  exportNoteMarkdown:(id:string)=>download(`/ai/materials/${id}/export.md`,`notatka-${id}.md`),
  printNote:(id:string)=>download(`/ai/materials/${id}/print`,`notatka-${id}.html`,true),
};

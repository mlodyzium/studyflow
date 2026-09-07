import { FormEvent, useEffect, useMemo, useState } from "react";
import { ArrowRight, BookOpen, CalendarDays, Check, ChevronRight, CirclePlus, Clock3, Layers3, LayoutDashboard, ListTodo, LogOut, Menu, Moon, MoreHorizontal, Pencil, Play, Search, Sparkles, Sun, Trash2, X } from "lucide-react";
import { api, clearToken, hasToken, setToken } from "./api";
import type { Session, Subject, Task, Topic, User } from "./types";

type View = "overview" | "subjects" | "topics" | "tasks";
type Modal = "subject" | "topic" | "task" | "session" | null;
type EditTarget = { kind: "subject"; value: Subject } | { kind: "topic"; value: Topic } | { kind: "task"; value: Task };

const fmtDate = (value: string | null) => value ? new Intl.DateTimeFormat("pl-PL", { day: "numeric", month: "short" }).format(new Date(value)) : "Bez terminu";
const initials = (name: string) => name.slice(0, 2).toUpperCase();

function Brand() {
  return <div className="brand"><span className="brand-mark"><Sparkles size={18} /></span><span>studyflow<span className="dot">.</span></span></div>;
}

function Auth({ onReady }: { onReady: () => void }) {
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError("");
    const data = new FormData(e.currentTarget);
    const username = String(data.get("username")); const password = String(data.get("password"));
    try {
      if (register) await api.register(username, String(data.get("email")), password);
      const result = await api.login(username, password); setToken(result.access_token); onReady();
    } catch (err) { setError(err instanceof Error ? err.message : "Nie udało się zalogować."); }
    finally { setBusy(false); }
  }
  return <main className="auth-page">
    <div className="orb orb-one" /><div className="orb orb-two" />
    <section className="auth-story">
      <Brand />
      <div><span className="eyebrow"><span /> Twój spokojny system nauki</span><h1>Mniej chaosu.<br /><em>Więcej postępu.</em></h1><p>Zamień ambitne plany w małe, konkretne kroki. StudyFlow pomaga skupić się na tym, co naprawdę ważne.</p></div>
      <div className="quote"><div className="avatars"><span>MK</span><span>AN</span><span>+2k</span></div><p>Dołącz do osób, które uczą się mądrzej, nie dłużej.</p></div>
    </section>
    <section className="auth-panel">
      <form className="auth-card" onSubmit={submit}>
        <div className="mobile-brand"><Brand /></div>
        <p className="kicker">Witaj {register ? "w StudyFlow" : "ponownie"}</p>
        <h2>{register ? "Utwórz konto" : "Gotowy na kolejny krok?"}</h2>
        <p className="muted">{register ? "Zacznij porządkować naukę już dziś." : "Zaloguj się i kontynuuj swój plan."}</p>
        <label>Nazwa użytkownika<input name="username" minLength={2} required placeholder="np. mateusz" autoComplete="username" /></label>
        {register && <label>E-mail <span className="optional">opcjonalnie</span><input name="email" type="email" placeholder="ty@email.pl" /></label>}
        <label>Hasło<input name="password" type="password" minLength={8} required placeholder="Minimum 8 znaków" autoComplete={register ? "new-password" : "current-password"} /></label>
        {error && <p className="form-error">{error}</p>}
        <button className="primary wide" disabled={busy}>{busy ? <span className="loader" /> : <>{register ? "Załóż konto" : "Wejdź do aplikacji"}<ArrowRight size={18} /></>}</button>
        <p className="switch">{register ? "Masz już konto?" : "Nie masz jeszcze konta?"} <button type="button" onClick={() => { setRegister(!register); setError(""); }}>{register ? "Zaloguj się" : "Utwórz je"}</button></p>
      </form>
    </section>
  </main>;
}

function ModalForm({ type, subjects, topics, close, done }: { type: Exclude<Modal, null>; subjects: Subject[]; topics: Topic[]; close: () => void; done: () => void }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const title = { subject: "Nowy przedmiot", topic: "Nowy temat", task: "Nowe zadanie", session: "Zapisz sesję" }[type];
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError(""); const f = new FormData(e.currentTarget);
    try {
      if (type === "subject") await api.addSubject({ name: String(f.get("name")), exam_date: String(f.get("date")) || null });
      if (type === "topic") await api.addTopic({ name: String(f.get("name")), subject_uid: String(f.get("subject")), difficulty: String(f.get("difficulty")) });
      if (type === "task") await api.addTask({ title: String(f.get("name")), topic_uid: String(f.get("topic")), deadline: String(f.get("deadline")) ? new Date(String(f.get("deadline"))).toISOString() : null, priority: String(f.get("priority")) });
      if (type === "session") await api.addSession({ subject_uid: String(f.get("subject")), duration_minutes: Number(f.get("minutes")), notes: String(f.get("notes")) || null });
      done();
    } catch (err) { setError(err instanceof Error ? err.message : "Nie udało się zapisać."); } finally { setBusy(false); }
  }
  return <div className="modal-backdrop" onMouseDown={close}><form className="modal" onSubmit={submit} onMouseDown={e => e.stopPropagation()}><button className="icon close" type="button" onClick={close}><X /></button><span className="kicker">Dodaj do StudyFlow</span><h2>{title}</h2>
    {(type === "subject" || type === "topic" || type === "task") && <label>Nazwa<input name="name" required autoFocus placeholder={type === "subject" ? "np. Matematyka" : type === "topic" ? "np. Pochodne" : "Co trzeba zrobić?"} /></label>}
    {(type === "topic" || type === "session") && <label>Przedmiot<select name="subject" required>{subjects.map(s => <option key={s.subject_uid} value={s.subject_uid}>{s.name}</option>)}</select></label>}
    {type === "subject" && <label>Data egzaminu<input name="date" type="date" /></label>}
    {type === "topic" && <label>Poziom trudności<select name="difficulty"><option>Łatwy</option><option>Średni</option><option>Trudny</option></select></label>}
    {type === "task" && <><label>Temat<select name="topic" required>{topics.map(t => <option key={t.topic_uid} value={t.topic_uid}>{t.name}</option>)}</select></label><div className="field-row"><label>Termin<input name="deadline" type="datetime-local" /></label><label>Priorytet<select name="priority"><option value="MEDIUM">Średni</option><option value="HIGH">Wysoki</option><option value="LOW">Niski</option></select></label></div></>}
    {type === "session" && <><label>Czas w minutach<input name="minutes" type="number" min="1" required defaultValue="45" /></label><label>Notatka<textarea name="notes" placeholder="Co udało Ci się zrobić?" /></label></>}
    {error && <p className="form-error">{error}</p>}<button className="primary wide" disabled={busy || ((type === "topic" || type === "session") && !subjects.length) || (type === "task" && !topics.length)}>{busy ? <span className="loader" /> : "Zapisz"}</button>
  </form></div>;
}

function EditForm({ target, subjects, topics, close, done }: { target: EditTarget; subjects: Subject[]; topics: Topic[]; close: () => void; done: () => void }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError(""); const f = new FormData(e.currentTarget);
    try {
      if (target.kind === "subject") await api.updateSubject(target.value.subject_uid, { name: String(f.get("name")), exam_date: String(f.get("date")) || null });
      if (target.kind === "topic") await api.updateTopic(target.value.topic_uid, { name: String(f.get("name")), subject_uid: String(f.get("subject")), difficulty: String(f.get("difficulty")), is_done: f.get("done") === "on" });
      if (target.kind === "task") await api.updateTask(target.value.task_uid, { title: String(f.get("name")), topic_uid: String(f.get("topic")), deadline: String(f.get("deadline")) ? new Date(String(f.get("deadline"))).toISOString() : null, priority: String(f.get("priority")) as Task["priority"] });
      done();
    } catch (err) { setError(err instanceof Error ? err.message : "Nie udało się zapisać zmian."); } finally { setBusy(false); }
  }
  const subject = target.kind === "subject" ? target.value : null;
  const topic = target.kind === "topic" ? target.value : null;
  const task = target.kind === "task" ? target.value : null;
  return <div className="modal-backdrop" onMouseDown={close}><form className="modal" onSubmit={submit} onMouseDown={e => e.stopPropagation()}><button className="icon close" type="button" onClick={close}><X /></button><span className="kicker">EDYCJA</span><h2>{target.kind === "subject" ? "Edytuj przedmiot" : target.kind === "topic" ? "Edytuj temat" : "Edytuj zadanie"}</h2>
    <label>Nazwa<input name="name" required autoFocus defaultValue={task?.title ?? topic?.name ?? subject?.name} /></label>
    {subject && <label>Data egzaminu<input name="date" type="date" defaultValue={subject.exam_date ?? ""} /></label>}
    {topic && <><label>Przedmiot<select name="subject" defaultValue={topic.subject_uid}>{subjects.map(s => <option key={s.subject_uid} value={s.subject_uid}>{s.name}</option>)}</select></label><label>Poziom trudności<input name="difficulty" defaultValue={topic.difficulty ?? ""} /></label><label className="toggle-line"><input name="done" type="checkbox" defaultChecked={topic.is_done} /> Temat ukończony</label></>}
    {task && <><label>Temat<select name="topic" defaultValue={task.topic_uid}>{topics.map(t => <option key={t.topic_uid} value={t.topic_uid}>{t.name}</option>)}</select></label><div className="field-row"><label>Termin<input name="deadline" type="datetime-local" defaultValue={task.deadline ? task.deadline.slice(0,16) : ""} /></label><label>Priorytet<select name="priority" defaultValue={task.priority}><option value="LOW">Niski</option><option value="MEDIUM">Średni</option><option value="HIGH">Wysoki</option></select></label></div></>}
    {error && <p className="form-error">{error}</p>}<button className="primary wide" disabled={busy}>{busy ? <span className="loader" /> : "Zapisz zmiany"}</button>
  </form></div>;
}

function App() {
  const [authenticated, setAuthenticated] = useState(hasToken());
  const [user, setUser] = useState<User | null>(null); const [subjects, setSubjects] = useState<Subject[]>([]); const [topics, setTopics] = useState<Topic[]>([]); const [tasks, setTasks] = useState<Task[]>([]); const [sessions, setSessions] = useState<Session[]>([]);
  const [view, setView] = useState<View>("overview"); const [modal, setModal] = useState<Modal>(null); const [editing, setEditing] = useState<EditTarget | null>(null); const [loading, setLoading] = useState(true); const [menu, setMenu] = useState(false); const [search, setSearch] = useState("");
  const [theme, setTheme] = useState<"light" | "dark">(() => localStorage.getItem("studyflow_theme") === "dark" ? "dark" : "light");
  const [subjectMenu, setSubjectMenu] = useState<string | null>(null);
  async function load() { setLoading(true); try { const [u,s,t,ta,se] = await Promise.all([api.me(), api.subjects(), api.topics(), api.tasks(), api.sessions()]); setUser(u); setSubjects(s.items); setTopics(t.items); setTasks(ta.items); setSessions(se.items); } catch { if (!hasToken()) setAuthenticated(false); } finally { setLoading(false); } }
  useEffect(() => { if (authenticated) load(); }, [authenticated]);
  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem("studyflow_theme", theme); }, [theme]);
  useEffect(() => { const out = () => setAuthenticated(false); addEventListener("studyflow:logout", out); return () => removeEventListener("studyflow:logout", out); }, []);
  const done = tasks.filter(t => t.is_done).length; const minutes = sessions.reduce((sum, s) => sum + (s.duration_minutes ?? 0), 0);
  const filtered = useMemo(() => tasks.filter(t => t.title.toLowerCase().includes(search.toLowerCase())), [tasks, search]);
  const topicName = (id: string) => topics.find(t => t.topic_uid === id)?.name ?? "Bez tematu";
  async function toggle(task: Task) { await api.updateTask(task.task_uid, { is_done: !task.is_done }); setTasks(v => v.map(t => t.task_uid === task.task_uid ? { ...t, is_done: !t.is_done } : t)); }
  async function remove(id: string) { await api.deleteTask(id); setTasks(v => v.filter(t => t.task_uid !== id)); }
  async function removeSubject(subject: Subject) { if (!confirm(`Usunąć przedmiot „${subject.name}” razem z jego tematami?`)) return; try { await api.deleteSubject(subject.subject_uid); await load(); } catch (err) { alert(err instanceof Error ? err.message : "Nie udało się usunąć przedmiotu."); } }
  async function removeTopic(topic: Topic) { if (!confirm(`Usunąć temat „${topic.name}” i powiązane zadania?`)) return; try { await api.deleteTopic(topic.topic_uid); await load(); } catch (err) { alert(err instanceof Error ? err.message : "Nie udało się usunąć tematu."); } }
  function startTask() { if (!subjects.length) { setView("subjects"); setModal("subject"); return; } if (!topics.length) { setView("topics"); setModal("topic"); return; } setModal("task"); }
  function logout() { clearToken(); setAuthenticated(false); }
  if (!authenticated) return <><Auth onReady={() => setAuthenticated(true)} /><button className="auth-theme" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-label="Zmień motyw">{theme === "light" ? <Moon /> : <Sun />}</button></>;
  return <div className="app-shell">
    <aside className={menu ? "sidebar open" : "sidebar"}><div className="side-head"><Brand /><button className="icon mobile-close" onClick={() => setMenu(false)}><X /></button></div><nav>
      <button className={view === "overview" ? "active" : ""} onClick={() => { setView("overview"); setMenu(false); }}><LayoutDashboard />Przegląd</button>
      <button className={view === "subjects" ? "active" : ""} onClick={() => { setView("subjects"); setMenu(false); }}><BookOpen />Przedmioty<span>{subjects.length}</span></button>
      <button className={view === "topics" ? "active" : ""} onClick={() => { setView("topics"); setMenu(false); }}><Layers3 />Tematy<span>{topics.length}</span></button>
      <button className={view === "tasks" ? "active" : ""} onClick={() => { setView("tasks"); setMenu(false); }}><ListTodo />Zadania<span>{tasks.filter(t => !t.is_done).length}</span></button>
    </nav><div className="side-focus"><span><Sparkles size={14} /> Dobra passa</span><strong>{Math.min(sessions.length, 7)} dni</strong><p>Każdy mały krok się liczy.</p></div><button className="theme-toggle" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>{theme === "light" ? <Moon /> : <Sun />}<span>{theme === "light" ? "Ciemny motyw" : "Jasny motyw"}</span></button><button className="profile" onClick={logout}><span>{initials(user?.username ?? "SF")}</span><div><strong>{user?.username}</strong><small>Wyloguj się</small></div><LogOut size={17} /></button></aside>
    {menu && <div className="menu-shade" onClick={() => setMenu(false)} />}
    <main className="content"><header><button className="icon menu-button" onClick={() => setMenu(true)}><Menu /></button><div><span className="kicker">{new Intl.DateTimeFormat("pl-PL", { weekday: "long", day: "numeric", month: "long" }).format(new Date())}</span><h1>{view === "overview" ? `Cześć, ${user?.username ?? "Uczniu"} 👋` : view === "subjects" ? "Twoje przedmioty" : view === "topics" ? "Twoje tematy" : "Twoje zadania"}</h1></div><button className="primary" onClick={() => view === "subjects" ? setModal("subject") : view === "topics" ? (subjects.length ? setModal("topic") : setModal("subject")) : startTask()}><CirclePlus size={18} />{view === "subjects" ? "Dodaj przedmiot" : view === "topics" ? "Dodaj temat" : "Dodaj zadanie"}</button></header>
      {loading ? <div className="loading-page"><span className="loader" /><p>Układamy Twój dzień…</p></div> : <>
      {view === "overview" && <>
        <section className="hero"><div><span className="eyebrow"><span /> DZISIAJ</span><h2>Zrób jedną rzecz.<br /><em>Potem kolejną.</em></h2><p>Masz {tasks.filter(t => !t.is_done).length} otwartych zadań. Wybierz jedno i ruszaj — reszta może chwilę poczekać.</p><button className="light-button" onClick={() => setView("tasks")}><Play size={16} fill="currentColor" /> Zacznij działać</button></div><div className="hero-ring"><svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="51" /><circle className="progress" cx="60" cy="60" r="51" style={{ strokeDashoffset: 320 - 320 * (tasks.length ? done/tasks.length : 0) }} /></svg><strong>{tasks.length ? Math.round(done/tasks.length*100) : 0}%</strong><span>ukończone</span></div></section>
        <section className="stats"><article><span className="stat-icon mint"><Check /></span><div><small>Ukończone zadania</small><strong>{done}<i> / {tasks.length}</i></strong></div></article><article><span className="stat-icon violet"><Clock3 /></span><div><small>Czas nauki</small><strong>{Math.floor(minutes/60)}h <i>{minutes%60}min</i></strong></div></article><article><span className="stat-icon orange"><BookOpen /></span><div><small>Aktywne przedmioty</small><strong>{subjects.length}</strong></div></article></section>
        <div className="dashboard-grid"><section className="panel float-panel"><div className="panel-head"><div><span className="kicker">NAJBLIŻSZE</span><h3>Zadania na teraz</h3></div><button className="text-button" onClick={() => setView("tasks")}>Wszystkie <ChevronRight /></button></div>{!topics.length ? <Empty text="Dodaj temat, aby utworzyć pierwsze zadanie" action={() => setView(subjects.length ? "topics" : "subjects")} /> : <TaskList tasks={tasks.filter(t => !t.is_done).slice(0,5)} topicName={topicName} toggle={toggle} remove={remove} edit={task=>setEditing({kind:"task",value:task})} />}</section>
        <section className="panel subjects-mini"><div className="panel-head"><div><span className="kicker">PRZEDMIOTY</span><h3>Twój kierunek</h3></div><button className="icon" onClick={() => setModal("subject")}><CirclePlus /></button></div>{subjects.slice(0,4).map((s,i) => <article key={s.subject_uid}><span className={`subject-letter c${i%4}`}>{s.name[0]}</span><div><strong>{s.name}</strong><small>{topics.filter(t => t.subject_uid === s.subject_uid).length} tematów</small></div><span className="date"><CalendarDays />{fmtDate(s.exam_date)}</span></article>)}{!subjects.length && <Empty text="Dodaj pierwszy przedmiot" action={() => setModal("subject")} />}</section></div>
      </>}
      {view === "subjects" && <section className="subject-view view-enter"><div className="section-toolbar"><p>Porządkuj materiał w przedmioty i mniejsze tematy.</p><button className="secondary" onClick={() => subjects.length ? setModal("topic") : setModal("subject")}><CirclePlus /> Dodaj temat</button></div>{!subjects.length ? <Onboarding title="Zacznij od pierwszego przedmiotu" text="Przedmiot jest bazą Twojego planu. Potem dodasz do niego tematy i zadania — poprowadzimy Cię krok po kroku." action="Dodaj pierwszy przedmiot" click={() => setModal("subject")} /> : <div className="subject-grid">{subjects.map((s,i) => { const own = topics.filter(t => t.subject_uid === s.subject_uid); return <article className="subject-card" key={s.subject_uid}><div className="card-top"><span className={`subject-letter large c${i%4}`}>{s.name[0]}</span><div className="card-menu"><button className="icon" onClick={() => setSubjectMenu(subjectMenu === s.subject_uid ? null : s.subject_uid)}><MoreHorizontal /></button>{subjectMenu === s.subject_uid && <div className="dropdown"><button onClick={() => { setEditing({kind:"subject",value:s}); setSubjectMenu(null); }}><Pencil />Edytuj</button><button className="danger" onClick={() => removeSubject(s)}><Trash2 />Usuń</button></div>}</div></div><h3>{s.name}</h3><p><CalendarDays /> {fmtDate(s.exam_date)}</p><div className="topic-progress"><span><b>{own.filter(t=>t.is_done).length}</b> z {own.length} tematów</span><div><i style={{width:`${own.length ? own.filter(t=>t.is_done).length/own.length*100 : 0}%`}} /></div></div>{own.slice(0,3).map(t => <small className="topic-chip" key={t.topic_uid}>{t.name}</small>)}</article>; })}<button className="add-card" onClick={() => setModal("subject")}><CirclePlus /><strong>Nowy przedmiot</strong><span>Zacznij kolejny kierunek</span></button></div>}</section>}
      {view === "topics" && <section className="subject-view view-enter">{!subjects.length ? <Onboarding title="Najpierw dodaj przedmiot" text="Każdy temat musi należeć do przedmiotu. Utwórz pierwszy przedmiot, a zaraz potem dodasz do niego materiał." action="Dodaj przedmiot" click={() => setModal("subject")} /> : !topics.length ? <Onboarding title="Podziel materiał na tematy" text="Tematy zamieniają duży przedmiot w konkretne etapy. Dodaj pierwszy, a następnie przypisz do niego zadania." action="Dodaj pierwszy temat" click={() => setModal("topic")} /> : <div className="topic-grid">{topics.map(topic => <article className={topic.is_done ? "topic-card complete" : "topic-card"} key={topic.topic_uid}><button className="topic-check" onClick={async()=>{await api.updateTopic(topic.topic_uid,{is_done:!topic.is_done});load();}}>{topic.is_done && <Check />}</button><div><span className="kicker">{subjects.find(s=>s.subject_uid===topic.subject_uid)?.name}</span><h3>{topic.name}</h3><p>{topic.difficulty || "Bez poziomu"} · {tasks.filter(t=>t.topic_uid===topic.topic_uid).length} zadań</p></div><div className="row-actions"><button className="icon" onClick={()=>setEditing({kind:"topic",value:topic})}><Pencil /></button><button className="icon trash" onClick={()=>removeTopic(topic)}><Trash2 /></button></div></article>)}</div>}</section>}
      {view === "tasks" && <section className="panel task-view view-enter">{!subjects.length || !topics.length ? <Onboarding title={!subjects.length ? "Najpierw utwórz przedmiot" : "Zadanie potrzebuje tematu"} text={!subjects.length ? "Przedmiot i temat pomagają zachować porządek. Zaczniemy od pierwszego kroku." : "Dodaj temat do jednego z przedmiotów, a potem od razu utworzysz swoje pierwsze zadanie."} action={!subjects.length ? "Dodaj przedmiot" : "Dodaj temat"} click={() => setModal(!subjects.length ? "subject" : "topic")} /> : <><div className="tasks-toolbar"><div className="search"><Search /><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Szukaj zadania…" /></div><span>{filtered.filter(t=>!t.is_done).length} do zrobienia</span></div><TaskList tasks={filtered} topicName={topicName} toggle={toggle} remove={remove} edit={task=>setEditing({kind:"task",value:task})} /></>}</section>}
      </>}
    </main>
    {modal && <ModalForm type={modal} subjects={subjects} topics={topics} close={() => setModal(null)} done={() => { setModal(null); load(); }} />}
    {editing && <EditForm target={editing} subjects={subjects} topics={topics} close={() => setEditing(null)} done={() => { setEditing(null); load(); }} />}
    <button className="floating-session" onClick={() => setModal("session")} title="Zapisz sesję nauki"><Clock3 /><span>Zapisz naukę</span></button>
  </div>;
}

function Empty({ text, action }: { text: string; action?: () => void }) { return <div className="empty"><Sparkles /><p>{text}</p>{action && <button onClick={action}>Dodaj teraz</button>}</div>; }
function Onboarding({title,text,action,click}:{title:string;text:string;action:string;click:()=>void}) { return <div className="onboarding"><span><Sparkles /></span><h2>{title}</h2><p>{text}</p><button className="primary" onClick={click}><CirclePlus />{action}</button></div>; }
function TaskList({ tasks, topicName, toggle, remove, edit }: { tasks: Task[]; topicName: (id:string)=>string; toggle:(t:Task)=>void; remove:(id:string)=>void; edit?:(t:Task)=>void }) {
  if (!tasks.length) return <Empty text="Tu jest czysto. Dobra robota!" />;
  return <div className="task-list">{tasks.map(task => <article className={task.is_done ? "task done" : "task"} key={task.task_uid}><button className="check" onClick={() => toggle(task)}>{task.is_done && <Check />}</button><div><strong>{task.title}</strong><span>{topicName(task.topic_uid)} · {fmtDate(task.deadline)}</span></div><i className={`priority ${task.priority.toLowerCase()}`}>{task.priority === "HIGH" ? "Wysoki" : task.priority === "LOW" ? "Niski" : "Średni"}</i><span className="row-actions">{edit && <button className="icon" onClick={() => edit(task)}><Pencil /></button>}<button className="icon trash" onClick={() => remove(task.task_uid)}><Trash2 /></button></span></article>)}</div>;
}

export default App;

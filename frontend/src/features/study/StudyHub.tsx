import { locale, t } from "../../i18n";
import {useEffect,useState} from "react";
import {ArrowRight, BookOpen, CalendarDays, CheckCircle2, Clock3, Copy, Download, RotateCcw, Sparkles} from "lucide-react";
import {api} from "../../api";
import type {Review, StudyPlan, Subject, Task, Topic, User} from "../../types";

const dayKey=(date:Date)=>`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;
const offsetDay=(value:string,offset:number)=>{const date=new Date(`${value}T12:00`);date.setDate(date.getDate()+offset);return dayKey(date)};

export function GoogleEventLink({title,date,details,time,duration,timeZone}:{title:string;date:string;details:string;time?:string|null;duration?:number;timeZone?:string}){
  const start=time?new Date(`${date}T${time}:00`):null;
  const end=start?new Date(start.getTime()+(duration??45)*60000):null;
  const stamp=(value:Date)=>`${value.getFullYear()}${String(value.getMonth()+1).padStart(2,"0")}${String(value.getDate()).padStart(2,"0")}T${String(value.getHours()).padStart(2,"0")}${String(value.getMinutes()).padStart(2,"0")}00`;
  const dates=start&&end?`${stamp(start)}/${stamp(end)}`:`${date.replaceAll("-","")}/${offsetDay(date,1).replaceAll("-","")}`;
  const params=new URLSearchParams({action:"TEMPLATE",text:title,dates,details,...(time&&timeZone?{ctz:timeZone}:{})});
  return <a className="text-button" href={`https://calendar.google.com/calendar/render?${params}`} target="_blank" rel="noopener noreferrer">Google Calendar <ArrowRight size={14}/></a>;
}

function PlanDaySchedule({day,save,busy}:{day:StudyPlan["days"][number];save:(data:{scheduled_date?:string;scheduled_time?:string|null;duration_minutes?:number})=>void;busy:boolean}){
  const [minutes,setMinutes]=useState(String(day.duration_minutes));
  const [minuteError,setMinuteError]=useState("");
  useEffect(()=>setMinutes(String(day.duration_minutes)),[day.duration_minutes]);
  function saveMinutes(){const value=Number(minutes);if(!Number.isInteger(value)||value<5||value>240){setMinuteError(t("Enter 5–240 minutes."));return}setMinuteError("");if(value!==day.duration_minutes)save({duration_minutes:value})}
  return <div className="plan-day-schedule"><label>{t("Date")}<input type="date" value={day.scheduled_date} disabled={busy} onChange={event=>event.target.value&&save({scheduled_date:event.target.value})}/></label><label>{t("Time")}<span>{t("(optional)")}</span><input type="time" value={day.scheduled_time??""} disabled={busy} onChange={event=>save({scheduled_time:event.target.value||null})}/></label><label>{t("Study time")}<span>(min)</span><input type="text" inputMode="numeric" pattern="[0-9]+" value={minutes} disabled={busy} onChange={event=>{setMinuteError("");setMinutes(event.target.value.replace(/\D/g,""))}} onBlur={saveMinutes} onKeyDown={event=>{if(event.key==="Enter")event.currentTarget.blur()}}/>{minuteError&&<small className="form-error" role="alert">{minuteError}</small>}</label></div>;
}

export function StudyHub({user,subjects,topics,tasks,plans,reviews,onChanged,openTask,openMaterials}:{user:User;subjects:Subject[];topics:Topic[];tasks:Task[];plans:StudyPlan[];reviews:Review[];onChanged:()=>Promise<void>;openTask:(task:Task)=>void;openMaterials:()=>void}){
  const today=dayKey(new Date());
  const activeTasks=tasks.filter(task=>!task.is_done);
  const dueToday=activeTasks.filter(task=>task.deadline&&dayKey(new Date(task.deadline))===today);
  const overdue=activeTasks.filter(task=>task.deadline&&dayKey(new Date(task.deadline))<today);
  const exam=subjects.filter(subject=>subject.exam_date&&subject.exam_date>=today).sort((a,b)=>a.exam_date!.localeCompare(b.exam_date!))[0];
  const planDays=plans.flatMap(plan=>plan.days.filter(day=>!day.is_done&&day.scheduled_date===today).map(day=>({plan,day})));
  const dueReviews=reviews.filter(review=>new Date(review.due_at)<=new Date());
  const [busy,setBusy]=useState<string|null>(null);const [error,setError]=useState("");
  async function answer(review:Review,rating:"forgot"|"hard"|"easy"){setBusy(review.review_uid);setError("");try{await api.answerReview(review.review_uid,rating);await onChanged()}catch(err){setError(err instanceof Error?err.message:t("Failed to save review."))}finally{setBusy(null)}}
  return <section className="study-hub panel"><div className="panel-head"><div><span className="kicker">{t("YOUR DAY")}</span><h3>{t("What to do now")}</h3></div><small>{new Intl.DateTimeFormat(locale(),{dateStyle:"long"}).format(new Date())}</small></div>
    <div className="study-hub-grid">
      <article><Clock3/><strong>{t("Today")}</strong><b>{dueToday.length} {t("tasks")}</b>{dueToday.slice(0,2).map(task=><button key={task.task_uid} onClick={()=>openTask(task)}>{task.title}<ArrowRight size={14}/></button>)}{!dueToday.length&&<small>{t("No tasks due today.")}</small>}</article>
      <article><RotateCcw/><strong>{t("Overdue")}</strong><b>{overdue.length} {t("tasks")}</b>{overdue.slice(0,2).map(task=><button key={task.task_uid} onClick={()=>openTask(task)}>{task.title}<ArrowRight size={14}/></button>)}{!overdue.length&&<small>{t("All caught up.")}</small>}</article>
      <article><CalendarDays/><strong>{t("Upcoming exam")}</strong><b>{exam?exam.name:t("No deadline")}</b><small>{exam?.exam_date?new Intl.DateTimeFormat(locale(),{dateStyle:"long"}).format(new Date(`${exam.exam_date}T12:00`)):t("Set a date in the subject.")}</small></article>
      <article><BookOpen/><strong>{t("Plan for today")}</strong><b>{planDays.length} {t("stages")}</b>{planDays.slice(0,2).map(({plan,day})=><div key={day.day_uid}><small>{plan.title}</small><p>{day.title} · {day.duration_minutes} min</p></div>)}{!planDays.length&&<small>{t("You have no plan stage for today.")}</small>}</article>
      <article><Sparkles/><strong>{t("Reviews")}</strong><b>{dueReviews.length} {t("materials")}</b>{dueReviews.slice(0,2).map(review=><div key={review.review_uid}><small>{topics.find(topic=>topic.topic_uid===review.topic_uid)?.name??t("AI Material")}</small><div className="study-review-actions"><button disabled={busy===review.review_uid} onClick={openMaterials}>{t("Open")}</button><button disabled={busy===review.review_uid} onClick={()=>answer(review,"forgot")}>{t("Forgot")}</button><button disabled={busy===review.review_uid} onClick={()=>answer(review,"hard")}>{t("Hard")}</button><button disabled={busy===review.review_uid} onClick={()=>answer(review,"easy")}>{t("Easy")}</button></div></div>)}{!dueReviews.length&&<small>{t("Reviews are scheduled for later.")}</small>}</article>
    </div>{error&&<p className="form-error">{error}</p>}
  </section>;
}

export function PlanBoard({plans,user,onChanged}:{plans:StudyPlan[];user:User;onChanged:()=>Promise<void>}){
  const [busy,setBusy]=useState<string|null>(null);const [error,setError]=useState("");
  const today=dayKey(new Date());
  async function action(id:string,call:()=>Promise<unknown>){setBusy(id);setError("");try{await call();await onChanged()}catch(err){setError(err instanceof Error?err.message:t("Failed to change plan."))}finally{setBusy(null)}}
  if(!plans.length)return null;
  return <section className="plan-board panel"><div className="panel-head"><div><span className="kicker">{t("STUDY PLANS")}</span><h3>{t("Your plans")}</h3></div><button className="secondary compact" onClick={()=>action("export",()=>api.exportCalendar())}><Download size={16}/>{t(".ics export")}</button></div>{error&&<p className="form-error">{error}</p>}
    {plans.map(plan=>{const done=plan.days.filter(day=>day.is_done).length;return <details key={plan.plan_uid} open={plan.days.some(day=>day.scheduled_date===today)}><summary><div><strong>{plan.title}</strong><small>{done}/{plan.days.length} {t("days completed · since")}{plan.start_date}</small></div><span>{plan.days.length?Math.round(done/plan.days.length*100):0}%</span></summary><p>{plan.overview}</p>
      <div className="plan-board-actions"><label>{t("Shift start")}<input type="date" defaultValue={plan.start_date} onChange={event=>{if(event.target.value)void action(plan.plan_uid,()=>api.shiftPlan(plan.plan_uid,event.target.value))}}/></label><button disabled={busy===plan.plan_uid} onClick={()=>action(plan.plan_uid,()=>api.duplicatePlan(plan.plan_uid,offsetDay(today,1)))}><Copy size={15}/>{t("Duplicate")}</button><button disabled={busy===plan.plan_uid} onClick={()=>action(plan.plan_uid,()=>api.createPlanTasks(plan.plan_uid,!plan.days.some(day=>day.calendar_task_uid)))}>{plan.days.some(day=>day.calendar_task_uid)?t("Delete calendar tasks"):t("Create separate tasks")}</button></div>
      <div className="plan-board-days">{plan.days.map(day=><article key={day.day_uid} className={day.is_done?"done":""}><button className="plan-day-check" aria-label={day.is_done?t("Mark as undone"):t("Mark day as completed")} onClick={()=>action(day.day_uid,()=>api.updatePlanDay(plan.plan_uid,day.day_uid,{is_done:!day.is_done}))}>{day.is_done&&<CheckCircle2 size={18}/>}</button><div><small>{day.scheduled_date} · {day.scheduled_time??t("without a fixed time")} · {day.duration_minutes} min</small><strong>{t("Day")}{day.day_number}: {day.title}</strong><PlanDaySchedule day={day} busy={busy===day.day_uid} save={data=>void action(day.day_uid,()=>api.updatePlanDay(plan.plan_uid,day.day_uid,data))}/><p>{day.objective}</p><ul>{day.activities.map((activity,index)=><li key={index}>{activity}</li>)}</ul><div className="plan-day-actions"><GoogleEventLink title={t("Study: {0}", day.title)} date={day.scheduled_date} time={day.scheduled_time} duration={day.duration_minutes} timeZone={user.timezone} details={`${plan.title}\n${day.objective}\n${day.activities.join("\n")}`}/><button disabled={busy===day.day_uid} onClick={()=>{const goal=window.prompt(t("What to improve on this day?"),day.objective);if(goal!==null)void action(day.day_uid,()=>api.regeneratePlanDay(plan.plan_uid,day.day_uid,goal))}}><Sparkles size={14}/>{t("Improve this day")}</button></div></div></article>)}</div>
      <small>{t("Each day can have a different time and hour. Without a time, the calendar event is all-day. Zone:")}{user.timezone}.</small>
    </details>})}
  </section>;
}

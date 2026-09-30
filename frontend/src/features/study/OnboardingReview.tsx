import {useState} from "react";
import {BookOpen,CalendarDays,Check,RotateCcw} from "lucide-react";
import type {GeneratedNotes,GeneratedStudyPlan} from "../../types";

type Kind="notes"|"plan";
type Props={subjectName:string;topicName:string;notes:GeneratedNotes|null;plan:GeneratedStudyPlan|null;busy:boolean;error:string;onNotes:(value:GeneratedNotes)=>void;onPlan:(value:GeneratedStudyPlan)=>void;onRegenerate:(kind:Kind)=>void;onSave:()=>void;onBack:()=>void};

export function OnboardingReview({subjectName,topicName,notes,plan,busy,error,onNotes,onPlan,onRegenerate,onSave,onBack}:Props){
  const [tab,setTab]=useState<Kind>(notes?"notes":"plan");
  const [editing,setEditing]=useState(false);
  const active=tab==="notes"?notes:plan;
  function planDayLabel(day:number){const scheduled=plan?.steps.find(step=>step.day===day)?.scheduled_date;if(!scheduled&&!plan?.start_date)return `Dzień ${day}`;const date=new Date(`${scheduled??plan?.start_date}T12:00:00`);if(!scheduled)date.setDate(date.getDate()+day-1);return new Intl.DateTimeFormat("pl-PL",{weekday:"long",day:"numeric",month:"long"}).format(date)}
  return <div className="onboarding-review">
    <p className="review-intro">Utworzono przedmiot „{subjectName}” i temat „{topicName}”. Sprawdź {notes&&plan?"notatkę i plan":notes?"notatkę":"plan"} poniżej. Materiały zapiszemy{plan?" i dodamy plan do kalendarza":""} dopiero po Twoim zatwierdzeniu.</p>
    {notes&&plan&&<div className="review-tabs" role="tablist" aria-label="Materiały do sprawdzenia"><button role="tab" aria-selected={tab==="notes"} className={tab==="notes"?"selected":""} onClick={()=>{setTab("notes");setEditing(false)}}><BookOpen size={16}/>Notatka</button><button role="tab" aria-selected={tab==="plan"} className={tab==="plan"?"selected":""} onClick={()=>{setTab("plan");setEditing(false)}}><CalendarDays size={16}/>Plan nauki</button></div>}
    <div className="review-toolbar"><strong>{tab==="notes"?"Notatka do nauki":"Plan nauki"}</strong><div><button type="button" className="secondary" disabled={busy} onClick={()=>setEditing(value=>!value)}>{editing?"Zobacz podgląd":"Edytuj"}</button><button type="button" className="secondary" disabled={busy} onClick={()=>onRegenerate(tab)}><RotateCcw size={14}/>Generuj ponownie</button></div></div>
    <div className="review-content" aria-live="polite">
      {tab==="notes"&&notes&&(editing?<div className="review-editor">
        <label>Tytuł notatki<input maxLength={160} value={notes.title} onChange={event=>onNotes({...notes,title:event.target.value})}/></label>
        <label>Tytuł zadania do notatki<input maxLength={120} value={notes.task_title} onChange={event=>onNotes({...notes,task_title:event.target.value})}/></label>
        <label>Podsumowanie<textarea maxLength={1200} value={notes.summary} onChange={event=>onNotes({...notes,summary:event.target.value})}/></label>
        {notes.sections.map((section,index)=><div className="review-edit-card" key={index}><label>Nagłówek sekcji {index+1}<input maxLength={120} value={section.heading} onChange={event=>onNotes({...notes,sections:notes.sections.map((item,i)=>i===index?{...item,heading:event.target.value}:item)})}/></label><label>Treść<textarea maxLength={4000} value={section.content} onChange={event=>onNotes({...notes,sections:notes.sections.map((item,i)=>i===index?{...item,content:event.target.value}:item)})}/></label></div>)}
        <label>Najważniejsze punkty <small>jeden w wierszu</small><textarea value={notes.key_points.join("\n")} onChange={event=>onNotes({...notes,key_points:event.target.value.split("\n")})}/></label>
        <label>Pytania kontrolne <small>jedno w wierszu</small><textarea value={notes.review_questions.join("\n")} onChange={event=>onNotes({...notes,review_questions:event.target.value.split("\n")})}/></label>
      </div>:<div className="review-preview"><h3>{notes.title}</h3><p className="ai-summary">{notes.summary}</p>{notes.sections.map((section,index)=><article key={index}><h4>{section.heading}</h4><p>{section.content}</p></article>)}<h4>Najważniejsze punkty</h4><ul>{notes.key_points.map((point,index)=><li key={index}>{point}</li>)}</ul>{notes.review_questions.length>0&&<><h4>Sprawdź się</h4><ol>{notes.review_questions.map((question,index)=><li key={index}>{question}</li>)}</ol></>}</div>)}
      {tab==="plan"&&plan&&(editing?<div className="review-editor">
        <label>Tytuł planu<input maxLength={160} value={plan.title} onChange={event=>onPlan({...plan,title:event.target.value})}/></label>
        <label>Opis planu<textarea maxLength={1200} value={plan.overview} onChange={event=>onPlan({...plan,overview:event.target.value})}/></label>
        {plan.steps.map((step,index)=><div className="review-edit-card" key={step.day}><strong>Dzień {step.day} · {planDayLabel(step.day)}</strong><label>Tytuł<input maxLength={160} value={step.title} onChange={event=>onPlan({...plan,steps:plan.steps.map((item,i)=>i===index?{...item,title:event.target.value}:item)})}/></label><label>Cel<textarea maxLength={1000} value={step.objective} onChange={event=>onPlan({...plan,steps:plan.steps.map((item,i)=>i===index?{...item,objective:event.target.value}:item)})}/></label><label>Ćwiczenia <small>jedno w wierszu</small><textarea value={step.activities.join("\n")} onChange={event=>onPlan({...plan,steps:plan.steps.map((item,i)=>i===index?{...item,activities:event.target.value.split("\n")}:item)})}/></label><label>Czas w minutach<input type="number" min={5} max={300} value={step.duration_minutes} onChange={event=>onPlan({...plan,steps:plan.steps.map((item,i)=>i===index?{...item,duration_minutes:Number(event.target.value)}:item)})}/></label></div>)}
        <label>Po czym poznasz, że umiesz? <small>jeden punkt w wierszu</small><textarea value={plan.success_criteria.join("\n")} onChange={event=>onPlan({...plan,success_criteria:event.target.value.split("\n")})}/></label>
      </div>:<div className="review-preview"><h3>{plan.title}</h3><p className="ai-summary">{plan.overview}</p><p className="review-date">Start: {planDayLabel(1)}</p>{plan.steps.map(step=><article key={step.day}><strong>Dzień {step.day} · {planDayLabel(step.day)} · {step.duration_minutes} min</strong><h4>{step.title}</h4><p>{step.objective}</p><ul>{step.activities.map((activity,index)=><li key={index}>{activity}</li>)}</ul></article>)}<h4>Po czym poznasz, że umiesz?</h4><ul>{plan.success_criteria.map((criterion,index)=><li key={index}>{criterion}</li>)}</ul></div>)}
    </div>
    {error&&<p className="form-error" role="alert">{error}</p>}
    <div className="first-run-actions"><button className="secondary" disabled={busy} onClick={onBack}>Wróć do ustawień</button><button className="primary" disabled={busy||!active} onClick={onSave}>{busy?<span className="loader"/>:<Check size={16}/>}Zatwierdź i zapisz {notes&&plan?"oba materiały":"materiał"}</button></div>
  </div>;
}

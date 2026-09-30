import { locale, t } from "../../i18n";
import {useState} from "react";
import {BookOpen,CalendarDays,Check,RotateCcw} from "lucide-react";
import type {GeneratedNotes,GeneratedStudyPlan} from "../../types";

type Kind="notes"|"plan";
type Props={subjectName:string;topicName:string;notes:GeneratedNotes|null;plan:GeneratedStudyPlan|null;busy:boolean;error:string;onNotes:(value:GeneratedNotes)=>void;onPlan:(value:GeneratedStudyPlan)=>void;onRegenerate:(kind:Kind)=>void;onSave:()=>void;onBack:()=>void};

export function OnboardingReview({subjectName,topicName,notes,plan,busy,error,onNotes,onPlan,onRegenerate,onSave,onBack}:Props){
  const [tab,setTab]=useState<Kind>(notes?"notes":"plan");
  const [editing,setEditing]=useState(false);
  const active=tab==="notes"?notes:plan;
  function planDayLabel(day:number){const scheduled=plan?.steps.find(step=>step.day===day)?.scheduled_date;if(!scheduled&&!plan?.start_date)return t("Day {0}", day);const date=new Date(`${scheduled??plan?.start_date}T12:00:00`);if(!scheduled)date.setDate(date.getDate()+day-1);return new Intl.DateTimeFormat(locale(),{weekday:"long",day:"numeric",month:"long"}).format(date)}
  return <div className="onboarding-review">
    <p className="review-intro">{t("Created subject \"")}{subjectName}{t("\" and topic \"")}{topicName}{t("\". Check")}{notes&&plan?t("note and plan"):notes?t("note"):"plan"} {t(" below. We will save the materials")}{plan?t(" and add the plan to your calendar"):""} {t(" only after your approval.")}</p>
    {notes&&plan&&<div className="review-tabs" role="tablist" aria-label={t("Materials to review")}><button role="tab" aria-selected={tab==="notes"} className={tab==="notes"?"selected":""} onClick={()=>{setTab("notes");setEditing(false)}}><BookOpen size={16}/>{t("Note")}</button><button role="tab" aria-selected={tab==="plan"} className={tab==="plan"?"selected":""} onClick={()=>{setTab("plan");setEditing(false)}}><CalendarDays size={16}/>{t("Study plan")}</button></div>}
    <div className="review-toolbar"><strong>{tab==="notes"?t("Study note"):t("Study plan")}</strong><div><button type="button" className="secondary" disabled={busy} onClick={()=>setEditing(value=>!value)}>{editing?t("Preview"):t("Edit")}</button><button type="button" className="secondary" disabled={busy} onClick={()=>onRegenerate(tab)}><RotateCcw size={14}/>{t("Regenerate")}</button></div></div>
    <div className="review-content" aria-live="polite">
      {tab==="notes"&&notes&&(editing?<div className="review-editor">
        <label>{t("Note title")}<input maxLength={160} value={notes.title} onChange={event=>onNotes({...notes,title:event.target.value})}/></label>
        <label>{t("Task title for note")}<input maxLength={120} value={notes.task_title} onChange={event=>onNotes({...notes,task_title:event.target.value})}/></label>
        <label>{t("Summary")}<textarea maxLength={1200} value={notes.summary} onChange={event=>onNotes({...notes,summary:event.target.value})}/></label>
        {notes.sections.map((section,index)=><div className="review-edit-card" key={index}><label>{t("Section header")}{index+1}<input maxLength={120} value={section.heading} onChange={event=>onNotes({...notes,sections:notes.sections.map((item,i)=>i===index?{...item,heading:event.target.value}:item)})}/></label><label>{t("Content")}<textarea maxLength={4000} value={section.content} onChange={event=>onNotes({...notes,sections:notes.sections.map((item,i)=>i===index?{...item,content:event.target.value}:item)})}/></label></div>)}
        <label>{t("Key points")}<small>{t("one per line")}</small><textarea value={notes.key_points.join("\n")} onChange={event=>onNotes({...notes,key_points:event.target.value.split("\n")})}/></label>
        <label>{t("Check questions")}<small>{t("one per line")}</small><textarea value={notes.review_questions.join("\n")} onChange={event=>onNotes({...notes,review_questions:event.target.value.split("\n")})}/></label>
      </div>:<div className="review-preview"><h3>{notes.title}</h3><p className="ai-summary">{notes.summary}</p>{notes.sections.map((section,index)=><article key={index}><h4>{section.heading}</h4><p>{section.content}</p></article>)}<h4>{t("Key points")}</h4><ul>{notes.key_points.map((point,index)=><li key={index}>{point}</li>)}</ul>{notes.review_questions.length>0&&<><h4>{t("Test yourself")}</h4><ol>{notes.review_questions.map((question,index)=><li key={index}>{question}</li>)}</ol></>}</div>)}
      {tab==="plan"&&plan&&(editing?<div className="review-editor">
        <label>{t("Plan title")}<input maxLength={160} value={plan.title} onChange={event=>onPlan({...plan,title:event.target.value})}/></label>
        <label>{t("Plan description")}<textarea maxLength={1200} value={plan.overview} onChange={event=>onPlan({...plan,overview:event.target.value})}/></label>
        {plan.steps.map((step,index)=><div className="review-edit-card" key={step.day}><strong>{t("Day")}{step.day} · {planDayLabel(step.day)}</strong><label>{t("Title")}<input maxLength={160} value={step.title} onChange={event=>onPlan({...plan,steps:plan.steps.map((item,i)=>i===index?{...item,title:event.target.value}:item)})}/></label><label>{t("Goal")}<textarea maxLength={1000} value={step.objective} onChange={event=>onPlan({...plan,steps:plan.steps.map((item,i)=>i===index?{...item,objective:event.target.value}:item)})}/></label><label>{t("Exercises")}<small>{t("one per line")}</small><textarea value={step.activities.join("\n")} onChange={event=>onPlan({...plan,steps:plan.steps.map((item,i)=>i===index?{...item,activities:event.target.value.split("\n")}:item)})}/></label><label>{t("Time in minutes")}<input type="number" min={5} max={300} value={step.duration_minutes} onChange={event=>onPlan({...plan,steps:plan.steps.map((item,i)=>i===index?{...item,duration_minutes:Number(event.target.value)}:item)})}/></label></div>)}
        <label>{t("How will you know you've mastered it?")}<small>{t("one point per line")}</small><textarea value={plan.success_criteria.join("\n")} onChange={event=>onPlan({...plan,success_criteria:event.target.value.split("\n")})}/></label>
      </div>:<div className="review-preview"><h3>{plan.title}</h3><p className="ai-summary">{plan.overview}</p><p className="review-date">Start: {planDayLabel(1)}</p>{plan.steps.map(step=><article key={step.day}><strong>{t("Day")}{step.day} · {planDayLabel(step.day)} · {step.duration_minutes} min</strong><h4>{step.title}</h4><p>{step.objective}</p><ul>{step.activities.map((activity,index)=><li key={index}>{activity}</li>)}</ul></article>)}<h4>{t("How will you know you've mastered it?")}</h4><ul>{plan.success_criteria.map((criterion,index)=><li key={index}>{criterion}</li>)}</ul></div>)}
    </div>
    {error&&<p className="form-error" role="alert">{error}</p>}
    <div className="first-run-actions"><button className="secondary" disabled={busy} onClick={onBack}>{t("Return to settings")}</button><button className="primary" disabled={busy||!active} onClick={onSave}>{busy?<span className="loader"/>:<Check size={16}/>}{t("Approve and save")}{notes&&plan?t("both materials"):t("material")}</button></div>
  </div>;
}

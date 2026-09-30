import { t } from "../../i18n";
import {FormEvent,useRef,useState} from "react";
import {ArrowRight,BookOpen,CalendarDays,CheckCircle2,Keyboard,Sparkles,X} from "lucide-react";
import {api} from "../../api";
import type {GeneratedNotes,GeneratedStudyPlan,User} from "../../types";
import {shortcutFromKey,shortcutsConflict} from "../../shortcut";
import {DatePicker} from "./DatePicker";
import {OnboardingReview} from "./OnboardingReview";

export function FirstRunWizard({user,onDone}:{user:User;onDone:(message?:string)=>Promise<void>}){
  const [step,setStep]=useState(0);const [subject,setSubject]=useState("");const [topic,setTopic]=useState("");const [goal,setGoal]=useState("");const [examDate,setExamDate]=useState("");const [difficulty,setDifficulty]=useState(t("Medium"));const [minutes,setMinutes]=useState(String(user.preferred_minutes));const [shortcut,setShortcut]=useState(user.task_shortcut);const [aiShortcut,setAiShortcut]=useState(user.ai_shortcut);const [kind,setKind]=useState<"notes"|"plan"|"both"|"none">("both");const [busy,setBusy]=useState(false);const [error,setError]=useState("");const [createdSubject,setCreatedSubject]=useState<string|null>(null);const [createdTopic,setCreatedTopic]=useState<string|null>(null);const [noteDraft,setNoteDraft]=useState<GeneratedNotes|null>(null);const [planDraft,setPlanDraft]=useState<GeneratedStudyPlan|null>(null);
  const materialsAccepted=useRef(false);
  function captureShortcut(event:React.KeyboardEvent<HTMLInputElement>,kind:"task"|"ai"){
    if(event.key==="Tab")return;
    event.preventDefault();
    const value=shortcutFromKey(event);
    if(value===null)return;
    if(shortcutsConflict(value,kind==="task"?aiShortcut:shortcut)){setError(t("This combination is already assigned to another shortcut. Please choose a different one."));return}
    setError("");
    if(kind==="task")setShortcut(value);else setAiShortcut(value);
  }
  function planDays(){return examDate?Math.min(30,Math.max(1,Math.ceil((new Date(`${examDate}T12:00`).getTime()-Date.now())/86400000))):7}
  async function finish(skip=false){setBusy(true);setError("");try{
    const minuteCount=Number(minutes);
    if(!skip&&(!Number.isInteger(minuteCount)||minuteCount<10||minuteCount>240))throw new Error(t("Enter a time from 10 to 240 minutes."));
    if(shortcutsConflict(shortcut,aiShortcut))throw new Error(t("Task and AI Assistant shortcuts must be different."));
    await api.updateMe({...(skip?{}:{preferred_minutes:minuteCount}),task_shortcut:shortcut,ai_shortcut:aiShortcut,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||user.timezone});
    if(!skip){let subjectId=createdSubject;if(!subjectId){const newSubject=await api.addSubject({name:subject.trim(),exam_date:examDate||null});subjectId=newSubject.subject_uid;setCreatedSubject(subjectId)}else await api.updateSubject(subjectId,{exam_date:examDate||null});
      let topicId=createdTopic;if(!topicId){const newTopic=await api.addTopic({name:topic.trim(),subject_uid:subjectId,difficulty});topicId=newTopic.topic_uid;setCreatedTopic(topicId)}
      setNoteDraft(null);setPlanDraft(null);
      if(kind==="notes"||kind==="both")setNoteDraft(await api.generateNotes(topicId,{detail_level:"standard",custom_goal:goal.trim()||null,preview_only:true}));
      if(kind==="plan"||kind==="both")setPlanDraft(await api.generatePlan(topicId,{days:planDays(),minutes_per_day:minuteCount,custom_goal:goal.trim()||null,preview_only:true}));
      if(kind!=="none"){setStep(3);return}
    }
    await api.updateMe({onboarding_complete:true});await onDone(skip?undefined:t("First subject and topic created."));
  }catch(err){setError(err instanceof Error?err.message:t("Failed to prepare the plan. Data has been saved, you can try again."))}finally{setBusy(false)}}
  async function regenerate(material:"notes"|"plan"){
    if(!createdTopic)return;
    setBusy(true);setError("");
    try{
      if(material==="notes")setNoteDraft(await api.generateNotes(createdTopic,{detail_level:"standard",custom_goal:goal.trim()||null,preview_only:true}));
      else setPlanDraft(await api.generatePlan(createdTopic,{days:planDays(),minutes_per_day:Number(minutes),custom_goal:goal.trim()||null,preview_only:true}));
    }catch(err){setError(err instanceof Error?err.message:t("Failed to regenerate the material."))}finally{setBusy(false)}
  }
  async function accept(){
    if(!createdTopic)return;
    setBusy(true);setError("");
    try{
      const cleanLines=(values:string[])=>values.map(value=>value.trim()).filter(Boolean);
      const notes=noteDraft?{...noteDraft,task_title:noteDraft.task_title.trim(),title:noteDraft.title.trim(),summary:noteDraft.summary.trim(),sections:noteDraft.sections.map(item=>({heading:item.heading.trim(),content:item.content.trim()})),key_points:cleanLines(noteDraft.key_points),review_questions:cleanLines(noteDraft.review_questions)}:null;
      const plan=planDraft?{...planDraft,title:planDraft.title.trim(),overview:planDraft.overview.trim(),steps:planDraft.steps.map(item=>({...item,title:item.title.trim(),objective:item.objective.trim(),activities:cleanLines(item.activities)})),success_criteria:cleanLines(planDraft.success_criteria)}:null;
      if(notes&&(!notes.title||!notes.task_title||!notes.summary||!notes.key_points.length||notes.sections.some(item=>!item.heading||!item.content)))throw new Error(t("Complete the title, summary, sections, and key points of the note."));
      if(plan&&(!plan.title||!plan.overview||!plan.success_criteria.length||plan.steps.some(item=>!item.title||!item.objective||!item.activities.length||!Number.isInteger(item.duration_minutes)||item.duration_minutes<5||item.duration_minutes>300)))throw new Error(t("Complete the description, goals, exercises, and correct duration for each day of the plan."));
      if(!materialsAccepted.current){await api.acceptMaterials(createdTopic,{notes,plan,minutes_per_day:Number(minutes)});materialsAccepted.current=true}
      await api.updateMe({onboarding_complete:true});
      await onDone(noteDraft&&planDraft?t("Note and study plan saved. You can find the plan in the calendar."):noteDraft?t("Study note saved."):t("Study plan saved to calendar."));
    }catch(err){setError(err instanceof Error?err.message:t("Failed to save materials. Correct the data and try again."))}finally{setBusy(false)}
  }
  function next(event:FormEvent){event.preventDefault();if(subject.trim()&&topic.trim())setStep(2)}
  return <div className="modal-backdrop first-run-backdrop"><section className={`first-run-wizard modal ${step===3?"review-wizard":""}`} role="dialog" aria-modal="true" aria-label={t("First study plan")}>{step!==3&&<button className="icon close" onClick={()=>void finish(true)} aria-label={t("Skip setup")}><X/></button>}<span className="kicker">{t("YOUR START ·")}{step+1}/{kind==="none"?3:4}</span><h2>{step===0?t("Set your shortcut"):step===1?t("What do you want to master?"):step===2?t("How do you want to study?"):t("Review and confirm materials")}</h2>{step!==3&&<p>{step===0?t("Press your own combination for quick task adding. On Mac you can use ⌘ or Option. You can also leave the shortcut disabled."):t("We will set up the first topic and prepare material tailored to your goal.")}</p>}
    {step===0?<div className="first-run-shortcut"><label><Keyboard size={18}/> {t("Your shortcut")}<input value={shortcut} readOnly onKeyDown={event=>captureShortcut(event,"task")} placeholder={t("Click and press the combination")} autoFocus/></label><small>{t("Use a combination with ⌘, Ctrl, or Option. Backspace disables the shortcut.")}</small><label><Sparkles size={18}/> {t("AI Assistant Shortcut")}<input value={aiShortcut} readOnly onKeyDown={event=>captureShortcut(event,"ai")} placeholder={t("Click and press a different combination")}/></label><button className="secondary" onClick={()=>{setShortcut("");setAiShortcut("");setError("")}}>{t("No shortcuts")}</button>{error&&<p className="form-error">{error}</p>}<button className="primary wide" onClick={()=>{if(shortcutsConflict(shortcut,aiShortcut)){setError(t("Task and AI Assistant shortcuts must be different."));return}setError("");setStep(1)}}>{t("Next")}<ArrowRight size={17}/></button></div>:step===1?<form onSubmit={next}><label>{t("Subject")}<input value={subject} onChange={event=>setSubject(event.target.value)} required maxLength={100} placeholder={t("e.g. Computer Science")} autoFocus/></label><label>{t("Topic")}<input value={topic} onChange={event=>setTopic(event.target.value)} required maxLength={100} placeholder={t("e.g. SQL")}/></label><label>{t("Your goal")}<textarea value={goal} onChange={event=>setGoal(event.target.value)} maxLength={500} placeholder={t("e.g. Prepare for an exam")}/></label><label>{t("Level")}<select value={difficulty} onChange={event=>setDifficulty(event.target.value)}><option>{t("Easy")}</option><option>{t("Medium")}</option><option>{t("Hard")}</option></select></label><div className="first-run-actions"><button className="secondary" type="button" onClick={()=>setStep(0)}>{t("Back")}</button><button className="primary">{t("Next")}<ArrowRight size={17}/></button></div></form>:step===3?<OnboardingReview subjectName={subject} topicName={topic} notes={noteDraft} plan={planDraft} busy={busy} error={error} onNotes={setNoteDraft} onPlan={setPlanDraft} onRegenerate={material=>void regenerate(material)} onSave={()=>void accept()} onBack={()=>{setError("");setStep(2)}}/>:<div><div className="first-run-grid"><label>{t("Exam date")}<span className="optional">{t("optional")}</span><DatePicker name="exam_date" defaultValue={examDate} onChange={setExamDate}/></label><label>{t("Suggested daily time")}<span className="optional">{t("you can change this later for each day individually")}</span><input type="text" inputMode="numeric" pattern="[0-9]+" value={minutes} onChange={event=>setMinutes(event.target.value.replace(/\D/g,""))} placeholder={t("e.g. 45")}/></label></div><div className="first-run-kind"><button className={kind==="both"?"selected":""} onClick={()=>setKind("both")}><Sparkles/>{t("Note and plan")}</button><button className={kind==="notes"?"selected":""} onClick={()=>setKind("notes")}><BookOpen/>{t("Note")}</button><button className={kind==="plan"?"selected":""} onClick={()=>setKind("plan")}><CalendarDays/>Plan</button><button className={kind==="none"?"selected":""} onClick={()=>setKind("none")}><CheckCircle2/>{t("Topic only")}</button></div>{error&&<p className="form-error">{error} {t("You can try again or finish without AI.")}</p>}<div className="first-run-actions"><button className="secondary" disabled={!!createdTopic||busy} onClick={()=>setStep(1)}>{t("Back")}</button><button className="primary" disabled={busy||!minutes||Number(minutes)<10||Number(minutes)>240} onClick={()=>void finish()}>{busy?t("Preparing..."):createdTopic?t("Regenerate"):kind==="none"?t("Create topic"):t("Create and check materials")}</button></div>{createdTopic&&error&&<button className="text-button" onClick={()=>void finish(true)}>{t("Finish without generating")}</button>}</div>}
    {step!==3&&<button className="first-run-skip" disabled={busy} onClick={()=>void finish(true)}>{t("Skip, I will configure later")}</button>}
  </section></div>;
}

import {FormEvent,useRef,useState} from "react";
import {ArrowRight,BookOpen,CalendarDays,CheckCircle2,Keyboard,Sparkles,X} from "lucide-react";
import {api} from "../../api";
import type {GeneratedNotes,GeneratedStudyPlan,User} from "../../types";
import {shortcutFromKey,shortcutsConflict} from "../../shortcut";
import {DatePicker} from "./DatePicker";
import {OnboardingReview} from "./OnboardingReview";

export function FirstRunWizard({user,onDone}:{user:User;onDone:(message?:string)=>Promise<void>}){
  const [step,setStep]=useState(0);const [subject,setSubject]=useState("");const [topic,setTopic]=useState("");const [goal,setGoal]=useState("");const [examDate,setExamDate]=useState("");const [difficulty,setDifficulty]=useState("Średni");const [minutes,setMinutes]=useState(String(user.preferred_minutes));const [shortcut,setShortcut]=useState(user.task_shortcut);const [aiShortcut,setAiShortcut]=useState(user.ai_shortcut);const [kind,setKind]=useState<"notes"|"plan"|"both"|"none">("both");const [busy,setBusy]=useState(false);const [error,setError]=useState("");const [createdSubject,setCreatedSubject]=useState<string|null>(null);const [createdTopic,setCreatedTopic]=useState<string|null>(null);const [noteDraft,setNoteDraft]=useState<GeneratedNotes|null>(null);const [planDraft,setPlanDraft]=useState<GeneratedStudyPlan|null>(null);
  const materialsAccepted=useRef(false);
  function captureShortcut(event:React.KeyboardEvent<HTMLInputElement>,kind:"task"|"ai"){
    if(event.key==="Tab")return;
    event.preventDefault();
    const value=shortcutFromKey(event);
    if(value===null)return;
    if(shortcutsConflict(value,kind==="task"?aiShortcut:shortcut)){setError("Ta kombinacja jest już przypisana do drugiego skrótu. Wybierz inną.");return}
    setError("");
    if(kind==="task")setShortcut(value);else setAiShortcut(value);
  }
  function planDays(){return examDate?Math.min(30,Math.max(1,Math.ceil((new Date(`${examDate}T12:00`).getTime()-Date.now())/86400000))):7}
  async function finish(skip=false){setBusy(true);setError("");try{
    const minuteCount=Number(minutes);
    if(!skip&&(!Number.isInteger(minuteCount)||minuteCount<10||minuteCount>240))throw new Error("Wpisz czas od 10 do 240 minut.");
    if(shortcutsConflict(shortcut,aiShortcut))throw new Error("Skróty zadania i Asystenta AI muszą być różne.");
    await api.updateMe({...(skip?{}:{preferred_minutes:minuteCount}),task_shortcut:shortcut,ai_shortcut:aiShortcut,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||user.timezone});
    if(!skip){let subjectId=createdSubject;if(!subjectId){const newSubject=await api.addSubject({name:subject.trim(),exam_date:examDate||null});subjectId=newSubject.subject_uid;setCreatedSubject(subjectId)}else await api.updateSubject(subjectId,{exam_date:examDate||null});
      let topicId=createdTopic;if(!topicId){const newTopic=await api.addTopic({name:topic.trim(),subject_uid:subjectId,difficulty});topicId=newTopic.topic_uid;setCreatedTopic(topicId)}
      setNoteDraft(null);setPlanDraft(null);
      if(kind==="notes"||kind==="both")setNoteDraft(await api.generateNotes(topicId,{detail_level:"standard",custom_goal:goal.trim()||null,preview_only:true}));
      if(kind==="plan"||kind==="both")setPlanDraft(await api.generatePlan(topicId,{days:planDays(),minutes_per_day:minuteCount,custom_goal:goal.trim()||null,preview_only:true}));
      if(kind!=="none"){setStep(3);return}
    }
    await api.updateMe({onboarding_complete:true});await onDone(skip?undefined:"Utworzono pierwszy przedmiot i temat.");
  }catch(err){setError(err instanceof Error?err.message:"Nie udało się przygotować planu. Dane zostały zachowane, możesz ponowić próbę.")}finally{setBusy(false)}}
  async function regenerate(material:"notes"|"plan"){
    if(!createdTopic)return;
    setBusy(true);setError("");
    try{
      if(material==="notes")setNoteDraft(await api.generateNotes(createdTopic,{detail_level:"standard",custom_goal:goal.trim()||null,preview_only:true}));
      else setPlanDraft(await api.generatePlan(createdTopic,{days:planDays(),minutes_per_day:Number(minutes),custom_goal:goal.trim()||null,preview_only:true}));
    }catch(err){setError(err instanceof Error?err.message:"Nie udało się ponownie wygenerować materiału.")}finally{setBusy(false)}
  }
  async function accept(){
    if(!createdTopic)return;
    setBusy(true);setError("");
    try{
      const cleanLines=(values:string[])=>values.map(value=>value.trim()).filter(Boolean);
      const notes=noteDraft?{...noteDraft,task_title:noteDraft.task_title.trim(),title:noteDraft.title.trim(),summary:noteDraft.summary.trim(),sections:noteDraft.sections.map(item=>({heading:item.heading.trim(),content:item.content.trim()})),key_points:cleanLines(noteDraft.key_points),review_questions:cleanLines(noteDraft.review_questions)}:null;
      const plan=planDraft?{...planDraft,title:planDraft.title.trim(),overview:planDraft.overview.trim(),steps:planDraft.steps.map(item=>({...item,title:item.title.trim(),objective:item.objective.trim(),activities:cleanLines(item.activities)})),success_criteria:cleanLines(planDraft.success_criteria)}:null;
      if(notes&&(!notes.title||!notes.task_title||!notes.summary||!notes.key_points.length||notes.sections.some(item=>!item.heading||!item.content)))throw new Error("Uzupełnij tytuł, podsumowanie, sekcje i najważniejsze punkty notatki.");
      if(plan&&(!plan.title||!plan.overview||!plan.success_criteria.length||plan.steps.some(item=>!item.title||!item.objective||!item.activities.length||!Number.isInteger(item.duration_minutes)||item.duration_minutes<5||item.duration_minutes>300)))throw new Error("Uzupełnij opis, cele, ćwiczenia i poprawny czas każdego dnia planu.");
      if(!materialsAccepted.current){await api.acceptMaterials(createdTopic,{notes,plan,minutes_per_day:Number(minutes)});materialsAccepted.current=true}
      await api.updateMe({onboarding_complete:true});
      await onDone(noteDraft&&planDraft?"Zapisano notatkę i plan nauki. Plan znajdziesz w kalendarzu.":noteDraft?"Zapisano notatkę do nauki.":"Zapisano plan nauki w kalendarzu.");
    }catch(err){setError(err instanceof Error?err.message:"Nie udało się zapisać materiałów. Popraw dane i spróbuj ponownie.")}finally{setBusy(false)}
  }
  function next(event:FormEvent){event.preventDefault();if(subject.trim()&&topic.trim())setStep(2)}
  return <div className="modal-backdrop first-run-backdrop"><section className={`first-run-wizard modal ${step===3?"review-wizard":""}`} role="dialog" aria-modal="true" aria-label="Pierwszy plan nauki">{step!==3&&<button className="icon close" onClick={()=>void finish(true)} aria-label="Pomiń konfigurację"><X/></button>}<span className="kicker">TWÓJ START · {step+1}/{kind==="none"?3:4}</span><h2>{step===0?"Ustaw swój skrót":step===1?"Co chcesz opanować?":step===2?"Jak chcesz się uczyć?":"Sprawdź i zatwierdź materiały"}</h2>{step!==3&&<p>{step===0?"Naciśnij własną kombinację do szybkiego dodawania zadania. Na Macu możesz użyć ⌘ lub Option. Możesz też zostawić skrót wyłączony.":"Ustawimy pierwszy temat i przygotujemy materiał dopasowany do Twojego celu."}</p>}
    {step===0?<div className="first-run-shortcut"><label><Keyboard size={18}/> Twój skrót<input value={shortcut} readOnly onKeyDown={event=>captureShortcut(event,"task")} placeholder="Kliknij i naciśnij kombinację" autoFocus/></label><small>Użyj kombinacji z ⌘, Ctrl lub Option. Backspace wyłącza skrót.</small><label><Sparkles size={18}/> Skrót Asystenta AI<input value={aiShortcut} readOnly onKeyDown={event=>captureShortcut(event,"ai")} placeholder="Kliknij i naciśnij inną kombinację"/></label><button className="secondary" onClick={()=>{setShortcut("");setAiShortcut("");setError("")}}>Bez skrótów</button>{error&&<p className="form-error">{error}</p>}<button className="primary wide" onClick={()=>{if(shortcutsConflict(shortcut,aiShortcut)){setError("Skróty zadania i Asystenta AI muszą być różne.");return}setError("");setStep(1)}}>Dalej <ArrowRight size={17}/></button></div>:step===1?<form onSubmit={next}><label>Przedmiot<input value={subject} onChange={event=>setSubject(event.target.value)} required maxLength={100} placeholder="np. Informatyka" autoFocus/></label><label>Temat<input value={topic} onChange={event=>setTopic(event.target.value)} required maxLength={100} placeholder="np. SQL"/></label><label>Twój cel<textarea value={goal} onChange={event=>setGoal(event.target.value)} maxLength={500} placeholder="np. Przygotować się do kolokwium"/></label><label>Poziom<select value={difficulty} onChange={event=>setDifficulty(event.target.value)}><option>Łatwy</option><option>Średni</option><option>Trudny</option></select></label><div className="first-run-actions"><button className="secondary" type="button" onClick={()=>setStep(0)}>Wróć</button><button className="primary">Dalej <ArrowRight size={17}/></button></div></form>:step===3?<OnboardingReview subjectName={subject} topicName={topic} notes={noteDraft} plan={planDraft} busy={busy} error={error} onNotes={setNoteDraft} onPlan={setPlanDraft} onRegenerate={material=>void regenerate(material)} onSave={()=>void accept()} onBack={()=>{setError("");setStep(2)}}/>:<div><div className="first-run-grid"><label>Data egzaminu <span className="optional">opcjonalnie</span><DatePicker name="exam_date" defaultValue={examDate} onChange={setExamDate}/></label><label>Sugerowany czas na dzień <span className="optional">możesz później zmienić osobno dla każdego dnia</span><input type="text" inputMode="numeric" pattern="[0-9]+" value={minutes} onChange={event=>setMinutes(event.target.value.replace(/\D/g,""))} placeholder="np. 45"/></label></div><div className="first-run-kind"><button className={kind==="both"?"selected":""} onClick={()=>setKind("both")}><Sparkles/>Notatka i plan</button><button className={kind==="notes"?"selected":""} onClick={()=>setKind("notes")}><BookOpen/>Notatka</button><button className={kind==="plan"?"selected":""} onClick={()=>setKind("plan")}><CalendarDays/>Plan</button><button className={kind==="none"?"selected":""} onClick={()=>setKind("none")}><CheckCircle2/>Tylko temat</button></div>{error&&<p className="form-error">{error} Możesz spróbować ponownie albo dokończyć bez AI.</p>}<div className="first-run-actions"><button className="secondary" disabled={!!createdTopic||busy} onClick={()=>setStep(1)}>Wróć</button><button className="primary" disabled={busy||!minutes||Number(minutes)<10||Number(minutes)>240} onClick={()=>void finish()}>{busy?"Przygotowuję…":createdTopic?"Ponów generowanie":kind==="none"?"Utwórz temat":"Utwórz i sprawdź materiały"}</button></div>{createdTopic&&error&&<button className="text-button" onClick={()=>void finish(true)}>Dokończ bez generowania</button>}</div>}
    {step!==3&&<button className="first-run-skip" disabled={busy} onClick={()=>void finish(true)}>Pomiń, skonfiguruję później</button>}
  </section></div>;
}

import { locale, t } from "../../i18n";
import {FormEvent,useEffect,useRef,useState} from "react";
import {ArrowLeft,ArrowRight,BookOpen,CalendarDays,CheckCircle2,ChevronRight,CirclePlus,Keyboard,Mic,MicOff,Play,Send,Sparkles,X,Pencil} from "lucide-react";
import {api} from "../../api";
import {planDayLabel} from "./planDates";
import type {GeneratedNotes,GeneratedStudyPlan,Subject,Task,Topic,T3achProposal} from "../../types";

type VoiceState="idle"|"listening"|"thinking"|"speaking";
export type T3achMemory={turns:{role:"user"|"assistant";text:string}[];proposal:T3achProposal|null;transcript:string;response:string};
function t3achAnswer(proposal:T3achProposal):string {
  return proposal.question||proposal.reply;
}

function T3achMaterialPreview({proposal}:{proposal:T3achProposal}) {
  const preview=proposal.preview;
  if(!preview)return null;
  const notes="notes" in preview?preview.notes:"sections" in preview?preview:null;
  const plan="plan" in preview?preview.plan:"steps" in preview?preview:null;
  if(!notes&&!plan)return null;
  return <section className="voice-material-preview"><small>{t("AI MATERIALS · PREVIEW BEFORE SAVING")}</small>{notes&&<article><span>{t("STUDY NOTE")}</span><h3>{notes.title}</h3><p>{notes.summary}</p>{notes.sections.map((section,index)=><div key={index}><h4>{section.heading}</h4><p>{section.content}</p></div>)}<h4>{t("Key points")}</h4><ul>{notes.key_points.map((point,index)=><li key={index}>{point}</li>)}</ul>{notes.review_questions.length>0&&<><h4>{t("Test yourself")}</h4><ol>{notes.review_questions.map((question,index)=><li key={index}>{question}</li>)}</ol></>}</article>}{plan&&<article><span>{t("STUDY PLAN · FROM")}{plan.start_date??proposal.plan_start_date??"—"} {t("· TOTAL")}{plan.steps.reduce((sum,step)=>sum+step.duration_minutes,0)} MIN</span><h3>{plan.title}</h3><p>{plan.overview}</p>{plan.steps.map(step=><div key={step.day}><h4>{planDayLabel(plan.start_date??proposal.plan_start_date,step.day,step.scheduled_date)}: {step.title} · {step.duration_minutes} min</h4><p>{step.objective}</p><ul>{step.activities.map((activity,index)=><li key={index}>{activity}</li>)}</ul></div>)}</article>}</section>;
}

export function VoiceT3ach({close,onSaved,openGenerator,memory,remember}:{close:()=>void;onSaved:()=>Promise<void>;openGenerator:()=>void;memory:T3achMemory;remember:(value:T3achMemory)=>void}) {
  const [state,setState]=useState<VoiceState>("idle");
  const [transcript,setTranscript]=useState(memory.transcript);
  const [response,setResponse]=useState(memory.response||t("Click the orb and say what you need."));
  const [proposal,setProposal]=useState<T3achProposal|null>(memory.proposal?.needs_clarification?null:memory.proposal);
  const requestPendingRef=useRef(false);
  const mountedRef=useRef(true);
  const pendingController=useRef<AbortController|null>(null);
  const conversationRef=useRef<{role:"user"|"assistant";text:string}[]>(memory.turns);
  const proposalRef=useRef<T3achProposal|null>(memory.proposal);
  const [textMode,setTextMode]=useState(false);
  const [input,setInput]=useState("");
  const [error,setError]=useState("");
  const [voiceError,setVoiceError]=useState("");
  const [saving,setSaving]=useState(false);
  const [revisionMode,setRevisionMode]=useState(false);
  const recognitionRef=useRef<any>(null);
  const listeningRef=useRef(false);
  const transcriptRef=useRef("");
  const audioRef=useRef<HTMLAudioElement|null>(null);
  const audioContextRef=useRef<AudioContext|null>(null);
  const audioSourceRef=useRef<AudioBufferSourceNode|null>(null);
  const audioUrlRef=useRef<string|null>(null);
  const speechRequestRef=useRef(0);
  const supported=Boolean((window as any).SpeechRecognition||(window as any).webkitSpeechRecognition);

  function stopAudio(){
    speechRequestRef.current++;
    window.speechSynthesis?.cancel();
    audioSourceRef.current?.stop();audioSourceRef.current=null;
    audioRef.current?.pause();audioRef.current=null;
    if(audioUrlRef.current){URL.revokeObjectURL(audioUrlRef.current);audioUrlRef.current=null}
  }

  function unlockAudio(){
    try{
      audioContextRef.current??=new AudioContext();
      const context=audioContextRef.current;
      void context.resume().catch(()=>{});
      const silent=context.createBufferSource();silent.buffer=context.createBuffer(1,1,context.sampleRate);silent.connect(context.destination);silent.start();
    }catch{ /* The browser may not support Web Audio. */ }
  }

  function readWithDevice(text:string,request:number,reason:string){
    if(request!==speechRequestRef.current)return;
    setVoiceError(reason);
    if(!("speechSynthesis" in window)||!("SpeechSynthesisUtterance" in window)){
      setState("idle");setVoiceError(t("The AI voice is unavailable, and this browser does not support text-to-speech. The response remains visible."));return;
    }
    try{
      const utterance=new SpeechSynthesisUtterance(text);
      utterance.lang=locale();
      utterance.rate=1;
      const selectedVoice=window.speechSynthesis.getVoices().find(voice=>voice.lang.toLowerCase().startsWith(locale().slice(0,2)));
      if(selectedVoice)utterance.voice=selectedVoice;
      utterance.onstart=()=>{if(request===speechRequestRef.current)setState("speaking")};
      utterance.onend=()=>{if(request===speechRequestRef.current)setState("idle")};
      utterance.onerror=event=>{if(request===speechRequestRef.current){setState("idle");setVoiceError(event.error==="not-allowed"?t("The AI voice is unavailable. The browser blocked autoplay; click \"Read with device voice\"."):t("The AI voice is unavailable and the device voice failed to read the response."))}};
      window.speechSynthesis.speak(utterance);
    }catch{
      if(request===speechRequestRef.current){setState("idle");setVoiceError(t("The AI voice is unavailable and the browser speech failed to start. The text response remains visible."))}
    }
  }

  async function speak(text:string){
    if(!mountedRef.current)return;
    stopAudio();setVoiceError("");const request=speechRequestRef.current;
    let fallbackStarted=false;
    const fallback=()=>{
      if(fallbackStarted||request!==speechRequestRef.current)return;
      fallbackStarted=true;
      audioRef.current?.pause();audioRef.current=null;
      if(audioUrlRef.current){URL.revokeObjectURL(audioUrlRef.current);audioUrlRef.current=null}
      readWithDevice(text,request,t("The AI voice is temporarily unavailable. Switching to the device voice."));
    };
    try{
      const blob=await api.t3achSpeech(text.split("\n\n")[0].slice(0,1500));
      if(request!==speechRequestRef.current)return;
      const url=URL.createObjectURL(blob);audioUrlRef.current=url;
      const context=audioContextRef.current;
      if(context?.state==="running"){
        try{
          const buffer=await context.decodeAudioData(await blob.arrayBuffer());
          if(request!==speechRequestRef.current)return;
          const source=context.createBufferSource();source.buffer=buffer;source.connect(context.destination);audioSourceRef.current=source;
          source.onended=()=>{if(request===speechRequestRef.current){audioSourceRef.current=null;stopAudio();setState("idle")}};
          source.start();setState("speaking");return;
        }catch{ /* Try playing the file directly. */ }
      }
      const player=new Audio(url);audioRef.current=player;
      player.onended=()=>{if(request===speechRequestRef.current){stopAudio();setState("idle")}};
      player.onerror=fallback;
      await player.play();
      if(request===speechRequestRef.current)setState("speaking");
    }catch{fallback()}
  }

  async function ask(value:string){
    const clean=value.trim();if(clean.length<1)return;
    if(requestPendingRef.current||saving)return;
    requestPendingRef.current=true;
    pendingController.current=new AbortController();
    const previous=proposalRef.current;
    stopAudio();
    setTranscript(clean);setResponse("");setError("");setVoiceError("");setState("thinking");
    try{
      const result=await api.proposeT3ach(clean,conversationRef.current.slice(-30),previous,pendingController.current?.signal);
      if(!mountedRef.current)return;
      setProposal(result.needs_clarification?null:result);proposalRef.current=result;
      setRevisionMode(false);
      const answer=t3achAnswer(result);
      conversationRef.current=[...conversationRef.current,{role:"user" as const,text:clean},{role:"assistant" as const,text:result.question||result.reply}].slice(-30);
      setResponse(answer);
      remember({turns:conversationRef.current,proposal:result,transcript:clean,response:answer});
      setState("idle");
      void speak(answer);
    }catch(err){if(!mountedRef.current)return;const message=err instanceof Error?err.message:t("T3ACH cannot respond right now.");setError(message);setResponse("");setInput(clean);setTextMode(true);setRevisionMode(Boolean(previous));setState("idle");remember({turns:conversationRef.current,proposal:previous,transcript:clean,response:""})}finally{requestPendingRef.current=false}
  }

  function listen(){
    unlockAudio();
    if(listeningRef.current){listeningRef.current=false;recognitionRef.current?.stop();setState("thinking");const value=transcriptRef.current.trim();if(value.length>=1)void ask(value);else{setState("idle");setError(t("Say a bit more and try again."))}return}
    if(!supported){setTextMode(true);setError(t("This browser does not support speech recognition. You can type your message."));return}
    stopAudio();
    const Recognition=(window as any).SpeechRecognition||(window as any).webkitSpeechRecognition;
    const recognition=new Recognition();recognitionRef.current=recognition;
    recognition.lang=locale();recognition.interimResults=true;recognition.continuous=true;
    listeningRef.current=true;transcriptRef.current="";
    recognition.onstart=()=>{setState("listening");setTranscript("");setError("")};
    recognition.onresult=(event:any)=>{const text=Array.from(event.results,(result:any)=>result[0].transcript).join(" ").trim();transcriptRef.current=text;setTranscript(text)};
    recognition.onerror=(event:any)=>{if(event.error==="no-speech"&&listeningRef.current)return;listeningRef.current=false;setState("idle");if(event.error!=="aborted")setError(event.error==="not-allowed"?t("Please allow the browser access to your microphone."):t("Could not recognize speech. Please try again."))};
    recognition.onend=()=>{if(listeningRef.current){try{recognition.start()}catch{listeningRef.current=false;setState("idle")}}};
    recognition.start();
  }

  async function approve(){if(!proposal||saving||revisionMode||state==="thinking")return;unlockAudio();stopAudio();setSaving(true);setState("thinking");try{const result=await api.executeT3ach(proposal);setProposal(null);proposalRef.current=null;setResponse(result.message);conversationRef.current=[...conversationRef.current,{role:"assistant" as const,text:result.message}].slice(-30);remember({turns:conversationRef.current,proposal:null,transcript,response:result.message});await onSaved();void speak(t("Done. {0}", result.message))}catch(err){const message=err instanceof Error?err.message:t("Failed to save changes.");setError(message);setState("idle")}finally{setSaving(false)}}
  useEffect(()=>{mountedRef.current=true;return()=>{mountedRef.current=false;pendingController.current?.abort();listeningRef.current=false;recognitionRef.current?.abort();stopAudio();void audioContextRef.current?.close();audioContextRef.current=null}},[]);
  function submit(event:FormEvent){event.preventDefault();unlockAudio();const value=input;if(value.trim().length<1)return;setInput("");void ask(value)}
  const label=state==="listening"?t("Listening — click again when finished"):state==="thinking"?t("Thinking…"):state==="speaking"?t("Responding…"):t("Ready");
  return <div className={`voice-t3ach-backdrop ${state}`}><button className="voice-close" onClick={close} aria-label={t("Close")}><X/></button><div className="voice-t3ach-stage"><div className="voice-name"><small>STUDYFLOW AGENT</small><h1>T3ACH</h1></div><button className="voice-orb" onClick={state==="idle"||state==="listening"?listen:undefined} disabled={state==="thinking"||state==="speaking"} aria-label={state==="listening"?t("Finish speaking"):t("Start conversation")}><span className="orb-core"><Sparkles/></span><i/><i/><i/><b className="voice-bars">{Array.from({length:18},(_,index)=><em key={index}/>)}</b></button><div className="voice-state"><span/><strong>{label}</strong><p>{transcript?`„${transcript}”`:response}</p>{response&&transcript&&<small>{response}</small>}</div>{conversationRef.current.length>2&&<details className="voice-material-preview"><summary>{t("Conversation history")}</summary>{conversationRef.current.slice(0,-2).map((turn,index)=><p key={index}><strong>{turn.role==="user"?t("You"):"T3ACH"}: </strong>{turn.text}</p>)}</details>}{error&&<div className="voice-error">{error}</div>}{voiceError&&<div className="voice-error voice-audio-error" role="status">{voiceError}</div>}{voiceError&&response&&state==="idle"&&<button className="voice-replay" onClick={()=>{stopAudio();readWithDevice(response,speechRequestRef.current,t("Reading the response using device voice."))}}><Play/>{t("Read with device voice")}</button>}{proposal&&<div className="voice-proposal"><small>{t("PREVIEW · NOTHING SAVED YET")}</small><h3>{proposal.intent==="session"?proposal.session_title:`${proposal.subject_name} → ${proposal.topic_name}`}</h3><p>{proposal.intent==="session"?t("\n{0} · {1} · {2} minutes · {3}", proposal.session_completed?"Odbyta sesja":"Planowana sesja", proposal.session_date??"", proposal.session_duration_minutes, proposal.session_notes??""):""}</p><div><button className="secondary" disabled={saving||state==="thinking"} onClick={()=>{setProposal(null);proposalRef.current=null;setRevisionMode(false);remember({turns:conversationRef.current,proposal:null,transcript,response})}}>{t("Dismiss")}</button><button className="secondary" type="button" onClick={()=>{setRevisionMode(true);setTextMode(true);setError("");setInput("")}} disabled={saving||state==="thinking"}><Pencil/>{t("Correct proposal")}</button><button className="primary" type="button" onClick={approve} disabled={saving||revisionMode||state==="thinking"}><CheckCircle2/>{saving?t("Saving…"):t("Confirm")}</button></div></div>}{proposal&&<T3achMaterialPreview proposal={proposal}/>}<div className="voice-controls"><button disabled={state==="thinking"||saving} onClick={()=>{stopAudio();conversationRef.current=[];proposalRef.current=null;setProposal(null);setTranscript("");setResponse(t("New conversation. How can I help?"));setInput("");setError("");setRevisionMode(false);remember({turns:[],proposal:null,transcript:"",response:""})}}><CirclePlus/><span>{t("New conversation")}</span></button><button onClick={listen} disabled={state!=="idle"&&state!=="listening"}>{state==="listening"?<MicOff/>:<Mic/>}<span>{state==="listening"?t("Finish and send"):t("Speak")}</span></button><button onClick={()=>setTextMode(value=>!value)}><Keyboard/><span>{t("Type")}</span></button><button onClick={openGenerator}><BookOpen/><span>{t("Note / plan")}</span></button></div>{textMode&&<form className="voice-text-form" onSubmit={submit}><input autoFocus value={input} onChange={event=>setInput(event.target.value)} maxLength={3000} placeholder={revisionMode?t("Write what to change in the proposal…"):t("Write to T3ACH…")}/><button className="primary" disabled={input.trim().length<1||state==="thinking"}><Send/></button></form>}</div></div>
}

export function AiAssistantV2({subjects,topics,tasks,initialTopic,onSaved,onNeedSubject,openT3ach,close}:{subjects:Subject[];topics:Topic[];tasks:Task[];initialTopic:Topic|null;onSaved:()=>Promise<void>;onNeedSubject:()=>void;openT3ach:()=>void;close:()=>void}) {
  type Mode="notes"|"plan";
  const initialSubject=initialTopic?.subject_uid??subjects[0]?.subject_uid??"";
  const initialTopicName=initialTopic?.name??topics.find(item=>item.subject_uid===initialSubject)?.name??"";
  const [mode,setMode]=useState<Mode|null>(null);
  const [subjectId,setSubjectId]=useState(initialSubject);
  const [topicText,setTopicText]=useState(initialTopicName);
  const [taskText,setTaskText]=useState("");
  const [level,setLevel]=useState<"short"|"standard"|"detailed">("standard");
  const [days,setDays]=useState("7"); const [minutes,setMinutes]=useState("45");
  const [notes,setNotes]=useState<GeneratedNotes|null>(null); const [plan,setPlan]=useState<GeneratedStudyPlan|null>(null);
  const [busy,setBusy]=useState(false); const [error,setError]=useState("");
  const [draft,setDraft]=useState<T3achProposal|null>(null);
  const [saved,setSaved]=useState(false);
  const controllerRef=useRef<AbortController|null>(null);
  const activeRef=useRef(true);
  useEffect(()=>{activeRef.current=true;return()=>{activeRef.current=false;controllerRef.current?.abort()}},[]);
  const [manualContent,setManualContent]=useState("");
  const availableTopics=topics.filter(item=>item.subject_uid===subjectId);
  const matchedTopic=availableTopics.find(item=>item.name.trim().toLocaleLowerCase("pl")===topicText.trim().toLocaleLowerCase("pl"));
  const availableTasks=matchedTopic?tasks.filter(item=>item.topic_uid===matchedTopic.topic_uid):[];
  function resetResult(){setNotes(null);setPlan(null);setDraft(null);setSaved(false);setError("")}
  function chooseSubject(value:string){setSubjectId(value);setTopicText(topics.find(item=>item.subject_uid===value)?.name??"");setTaskText("");resetResult()}
  if(!mode)return <div className="modal-backdrop ai-backdrop" onMouseDown={close}><section className="ai-assistant ai-assistant-v2 ai-hub" onMouseDown={event=>event.stopPropagation()}><button className="icon close" onClick={close}><X/></button><header><span><Sparkles/></span><div><small>STUDYFLOW AI</small><h2>{t("AI Assistant")}</h2></div></header><div className="ai-hub-grid"><button className="ai-hub-t3ach" onClick={openT3ach}><span className="ai-hub-orb"><Sparkles/></span><div><small>{t("MAIN ASSISTANT")}</small><strong>T3ACH</strong><p>{t("Describe your goal. T3ACH will suggest a subject, topic, and specific tasks, and will save them only after your confirmation.")}</p><b>{t("Start conversation")}<ArrowRight/></b></div></button><div className="ai-hub-tools"><button onClick={()=>setMode("notes")}><BookOpen/><div><strong>{t("Note")}</strong><p>{t("Explanation, key information, and review questions.")}</p></div><ChevronRight/></button><button onClick={()=>setMode("plan")}><CalendarDays/><div><strong>{t("Study plan")}</strong><p>{t("Plan divided into days, goals, and activities.")}</p></div><ChevronRight/></button></div></div></section></div>;
  if(!subjects.length)return <div className="modal-backdrop ai-backdrop" onMouseDown={close}><section className="ai-assistant ai-assistant-v2" onMouseDown={event=>event.stopPropagation()}><button className="icon close" onClick={close}><X/></button><header><span><Sparkles/></span><div><small>STUDYFLOW AI</small><h2>{t("Start with a subject")}</h2></div></header><div className="ai-ready"><BookOpen/><h3>{t("Assistant is ready")}</h3><p>{t("Add the first subject, then type a new topic here to generate material immediately.")}</p><button className="primary" onClick={onNeedSubject}><CirclePlus/>{t("Add first subject")}</button></div></section></div>;
  async function generate(fallback=false){
    if(!mode||!subjectId||!topicText.trim()||busy)return;
    if(mode==="plan"&&(!Number.isInteger(Number(days))||Number(days)<1||Number(days)>30||!Number.isInteger(Number(minutes))||Number(minutes)<10||Number(minutes)>240)){setError(t("Enter 1–30 days and 10–240 minutes."));return}
    if(fallback&&mode==="notes"&&manualContent.trim().length<10){setError(t("Enter at least 10 characters for the note."));return}
    setBusy(true);resetResult();controllerRef.current=new AbortController();
    try{
      const selectedTask=availableTasks.find(item=>item.title.trim().toLocaleLowerCase("pl")===taskText.trim().toLocaleLowerCase("pl"));
      const result=await api.draftMaterial({subject_uid:subjectId,topic_name:topicText.trim(),mode,detail_level:level,custom_goal:taskText.trim()||null,task_uid:selectedTask?.task_uid,days:Number(days),minutes_per_day:Number(minutes),fallback,manual_content:fallback&&mode==="notes"?manualContent.trim():null},controllerRef.current.signal);
      if(!activeRef.current)return;
      setDraft(result);
      if(mode==="notes")setNotes(result.preview as GeneratedNotes);else setPlan(result.preview as GeneratedStudyPlan);
    }catch(err){if(activeRef.current)setError(err instanceof Error?err.message:t("Failed to generate material."))}finally{if(activeRef.current)setBusy(false)}
  }
  async function saveDraft(){
    if(!draft||busy||saved)return;
    setBusy(true);setError("");
    try{await api.executeT3ach(draft);if(activeRef.current)setSaved(true);await onSaved()}
    catch(err){if(activeRef.current)setError(err instanceof Error?err.message:t("Failed to save material."))}
    finally{if(activeRef.current)setBusy(false)}
  }
  async function useFallback(){await generate(true)}
  return <div className="modal-backdrop ai-backdrop" onMouseDown={close}><section className="ai-assistant ai-assistant-v2" onMouseDown={event=>event.stopPropagation()}><button className="icon close" onClick={close}><X/></button><header><span><Sparkles/></span><div><small>STUDYFLOW AI</small><h2>{mode==="notes"?t("Notes generator"):mode==="plan"?t("Study plan"):t("What would you like to prepare?")}</h2></div></header>{!mode?<div className="ai-mode-grid"><button onClick={()=>setMode("notes")}><BookOpen/><strong>{t("Note")}</strong><p>{t("Clear explanation, key information, and review questions.")}</p><span>{t("Select")}<ChevronRight/></span></button><button onClick={()=>setMode("plan")}><CalendarDays/><strong>{t("Study plan")}</strong><p>{t("A plan divided into days, goals, and specific activities.")}</p><span>{t("Select")}<ChevronRight/></span></button></div>:<><div className="ai-config"><button className="ai-back" disabled={busy} onClick={()=>{setMode(null);resetResult()}}><ArrowLeft/>{t("Change type")}</button><div className="ai-form-grid"><label>{t("Subject")}<select value={subjectId} onChange={event=>chooseSubject(event.target.value)} disabled={busy}>{subjects.map(item=><option value={item.subject_uid} key={item.subject_uid}>{item.name}</option>)}</select></label><label>{t("Topic")}<span>{t("— select or type new")}</span><input list="ai-topic-options" value={topicText} onChange={event=>{setTopicText(event.target.value);setTaskText("");resetResult()}} disabled={busy} maxLength={100} placeholder={t("e.g., Quadratic equations")}/><datalist id="ai-topic-options">{availableTopics.map(item=><option value={item.name} key={item.topic_uid}/>)}</datalist><small className="ai-field-help">{t("A new topic will be created after approving the material.")}</small></label><label className="ai-goal-field">{t("Task or goal")}<span>{t("— select or type your own")}</span><input list="ai-task-options" value={taskText} onChange={event=>{setTaskText(event.target.value);resetResult()}} disabled={busy} maxLength={500} placeholder={t("e.g., Prepare me for a quiz")}/><datalist id="ai-task-options">{availableTasks.map(item=><option value={item.title} key={item.task_uid}/>)}</datalist><small className="ai-field-help">{t("You can save the material after reviewing the preview.")}</small></label>{mode==="notes"?<label>{t("Length")}<select value={level} onChange={event=>{setLevel(event.target.value as typeof level);resetResult()}} disabled={busy}><option value="short">{t("Short")}</option><option value="standard">{t("Standard")}</option><option value="detailed">{t("Detailed")}</option></select></label>:<><label>{t("Number of days")}<input type="number" min={1} max={30} value={days} disabled={busy} onChange={event=>{setDays(event.target.value);resetResult()}}/></label><label>{t("Approx. minutes per day")}<input type="number" min={10} max={240} value={minutes} disabled={busy} onChange={event=>{setMinutes(event.target.value);resetResult()}}/></label></>}</div></div>{busy&&<div className="ai-generating"><span className="loader"/><h3>{mode==="notes"?t("Creating note…"):t("Creating plan…")}</h3><p>{t("This may take a dozen or so seconds.")}</p></div>}{error&&<div className="ai-error"><p>{error}</p><small>{t("Your input remains in the form. You can retry generating.")}</small><div>{mode==="notes"?<><textarea value={manualContent} onChange={event=>setManualContent(event.target.value)} maxLength={12000} placeholder={t("You can also enter your own note and save it in the materials.")}/><button className="secondary" disabled={busy||!manualContent.trim()} onClick={useFallback}>{t("Preview of your own note")}</button></>:<button className="secondary" disabled={busy} onClick={useFallback}>{t("Create a simple plan without AI")}</button>}</div></div>}{notes&&<div className="ai-result"><h2>{notes.title}</h2><p className="ai-summary">{notes.summary}</p>{notes.sections.map((section,i)=><article key={`${section.heading}-${i}`}><h3>{section.heading}</h3><p>{section.content}</p></article>)}<h3>{t("Key points")}</h3><ul>{notes.key_points.map((point,i)=><li key={i}>{point}</li>)}</ul><h3>{t("Test yourself")}</h3><ol>{notes.review_questions.map((question,i)=><li key={i}>{question}</li>)}</ol></div>}{plan&&<div className="ai-result"><h2>{plan.title}</h2><p className="ai-summary">{plan.overview}</p><div className="ai-plan-steps">{plan.steps.map(step=><article key={step.day}><span>{planDayLabel(plan.start_date,step.day,step.scheduled_date)}</span><div><h3>{step.title}</h3><p>{step.objective}</p><ul>{step.activities.map(activity=><li key={activity}>{activity}</li>)}</ul></div><strong>{step.duration_minutes} min</strong></article>)}</div><h3>{t("How will you know you've mastered it?")}</h3><ul>{plan.success_criteria.map((item,i)=><li key={i}>{item}</li>)}</ul></div>}<footer>{draft&&<><span role="status">{saved?t("Material saved"):t("Preview — not yet saved")}</span><button className="primary" disabled={busy||saved} onClick={()=>void saveDraft()}>{saved?t("Saved"):t("Approve and save")}</button></>}<button className="primary" disabled={busy||!subjectId||!topicText.trim()} onClick={()=>void generate()}><Sparkles/>{notes||plan?t("Regenerate"):mode==="notes"?t("Generate note"):t("Create plan")}</button></footer></>}</section></div>
}

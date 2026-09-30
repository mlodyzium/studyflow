import {FormEvent,useEffect,useRef,useState} from "react";
import {ArrowLeft,ArrowRight,BookOpen,CalendarDays,CheckCircle2,ChevronRight,CirclePlus,Keyboard,Mic,MicOff,Play,Send,Sparkles,X,Pencil} from "lucide-react";
import {api} from "../../api";
import type {GeneratedNotes,GeneratedStudyPlan,Subject,Task,Topic,T3achProposal} from "../../types";

type VoiceState="idle"|"listening"|"thinking"|"speaking";
export type T3achMemory={turns:{role:"user"|"assistant";text:string}[];proposal:T3achProposal|null;transcript:string;response:string};
function t3achAnswer(proposal:T3achProposal):string {
  return proposal.question||proposal.reply;
}

function planDayLabel(startDate:string|null|undefined,day:number):string {
  if(!startDate)return `Dzień ${day}`;
  const date=new Date(`${startDate}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate()+day-1);
  return `Dzień ${day} · ${new Intl.DateTimeFormat("pl-PL",{weekday:"long",day:"numeric",month:"long",timeZone:"UTC"}).format(date)}`;
}

function T3achMaterialPreview({proposal}:{proposal:T3achProposal}) {
  const preview=proposal.preview;
  if(!preview)return null;
  const notes="notes" in preview?preview.notes:"sections" in preview?preview:null;
  const plan="plan" in preview?preview.plan:"steps" in preview?preview:null;
  if(!notes&&!plan)return null;
  return <section className="voice-material-preview"><small>MATERIAŁY AI · PODGLĄD PRZED ZAPISEM</small>{notes&&<article><span>NOTATKA DO NAUKI</span><h3>{notes.title}</h3><p>{notes.summary}</p>{notes.sections.map((section,index)=><div key={index}><h4>{section.heading}</h4><p>{section.content}</p></div>)}<h4>Najważniejsze punkty</h4><ul>{notes.key_points.map((point,index)=><li key={index}>{point}</li>)}</ul>{notes.review_questions.length>0&&<><h4>Sprawdź się</h4><ol>{notes.review_questions.map((question,index)=><li key={index}>{question}</li>)}</ol></>}</article>}{plan&&<article><span>PLAN NAUKI · OD {proposal.plan_start_date??"DZISIAJ"} · ŁĄCZNIE {plan.steps.reduce((sum,step)=>sum+step.duration_minutes,0)} MIN</span><h3>{plan.title}</h3><p>{plan.overview}</p>{plan.steps.map(step=><div key={step.day}><h4>{planDayLabel(step.scheduled_date??plan.start_date??proposal.plan_start_date,step.scheduled_date?1:step.day)}: {step.title} · {step.duration_minutes} min</h4><p>{step.objective}</p><ul>{step.activities.map((activity,index)=><li key={index}>{activity}</li>)}</ul></div>)}</article>}</section>;
}

export function VoiceT3ach({close,onSaved,openGenerator,memory,remember}:{close:()=>void;onSaved:()=>Promise<void>;openGenerator:()=>void;memory:T3achMemory;remember:(value:T3achMemory)=>void}) {
  const [state,setState]=useState<VoiceState>("idle");
  const [transcript,setTranscript]=useState(memory.transcript);
  const [response,setResponse]=useState(memory.response||"Kliknij kulę i powiedz, czego potrzebujesz.");
  const [proposal,setProposal]=useState<T3achProposal|null>(memory.proposal);
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
    }catch{ /* Przeglądarka może nie obsługiwać Web Audio. */ }
  }

  function readWithDevice(text:string,request:number,reason:string){
    if(request!==speechRequestRef.current)return;
    setVoiceError(reason);
    if(!("speechSynthesis" in window)||!("SpeechSynthesisUtterance" in window)){
      setState("idle");setVoiceError("Głos AI jest niedostępny, a ta przeglądarka nie obsługuje czytania tekstu. Odpowiedź pozostaje widoczna.");return;
    }
    try{
      const utterance=new SpeechSynthesisUtterance(text);
      utterance.lang="pl-PL";
      utterance.rate=1;
      const polishVoice=window.speechSynthesis.getVoices().find(voice=>voice.lang.toLowerCase().startsWith("pl"));
      if(polishVoice)utterance.voice=polishVoice;
      utterance.onstart=()=>{if(request===speechRequestRef.current)setState("speaking")};
      utterance.onend=()=>{if(request===speechRequestRef.current)setState("idle")};
      utterance.onerror=event=>{if(request===speechRequestRef.current){setState("idle");setVoiceError(event.error==="not-allowed"?"Głos AI jest niedostępny. Przeglądarka zablokowała automatyczny odczyt; kliknij „Czytaj głosem urządzenia”.":"Głos AI jest niedostępny i nie udało się przeczytać odpowiedzi głosem urządzenia.")}};
      window.speechSynthesis.speak(utterance);
    }catch{
      if(request===speechRequestRef.current){setState("idle");setVoiceError("Głos AI jest niedostępny i nie udało się uruchomić odczytu przeglądarki. Odpowiedź tekstowa pozostaje widoczna.")}
    }
  }

  async function speak(text:string){
    stopAudio();setVoiceError("");const request=speechRequestRef.current;
    let fallbackStarted=false;
    const fallback=()=>{
      if(fallbackStarted||request!==speechRequestRef.current)return;
      fallbackStarted=true;
      audioRef.current?.pause();audioRef.current=null;
      if(audioUrlRef.current){URL.revokeObjectURL(audioUrlRef.current);audioUrlRef.current=null}
      readWithDevice(text,request,"Głos AI jest chwilowo niedostępny. Przełączam na głos urządzenia.");
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
        }catch{ /* Spróbuj odtworzyć plik bezpośrednio. */ }
      }
      const player=new Audio(url);audioRef.current=player;
      player.onended=()=>{if(request===speechRequestRef.current){stopAudio();setState("idle")}};
      player.onerror=fallback;
      await player.play();
      if(request===speechRequestRef.current)setState("speaking");
    }catch{fallback()}
  }

  async function ask(value:string){
    const clean=value.trim();if(clean.length<3)return;
    if(state==="thinking"||saving)return;
    const previous=proposalRef.current;
    stopAudio();
    setTranscript(clean);setResponse("");setError("");setVoiceError("");setState("thinking");
    try{
      const result=await api.proposeT3ach(clean,conversationRef.current.slice(-8),previous);
      setProposal(result.needs_clarification?null:result);proposalRef.current=result;
      setRevisionMode(false);
      const answer=t3achAnswer(result);
      conversationRef.current=[...conversationRef.current,{role:"user" as const,text:clean},{role:"assistant" as const,text:result.question||result.reply}].slice(-10);
      setResponse(answer);
      remember({turns:conversationRef.current,proposal:result.needs_clarification?null:result,transcript:clean,response:answer});
      setState("idle");
      void speak(answer);
    }catch(err){const message=err instanceof Error?err.message:"T3ACH nie może teraz odpowiedzieć.";setError(message);setResponse("");setInput(clean);setTextMode(true);setRevisionMode(Boolean(previous));setState("idle");remember({turns:conversationRef.current,proposal:previous,transcript:clean,response:""})}
  }

  function listen(){
    unlockAudio();
    if(listeningRef.current){listeningRef.current=false;recognitionRef.current?.stop();setState("thinking");const value=transcriptRef.current.trim();if(value.length>=3)void ask(value);else{setState("idle");setError("Powiedz trochę więcej i spróbuj ponownie.")}return}
    if(!supported){setTextMode(true);setError("Ta przeglądarka nie obsługuje rozpoznawania mowy. Możesz wpisać wiadomość.");return}
    stopAudio();
    const Recognition=(window as any).SpeechRecognition||(window as any).webkitSpeechRecognition;
    const recognition=new Recognition();recognitionRef.current=recognition;
    recognition.lang="pl-PL";recognition.interimResults=true;recognition.continuous=true;
    listeningRef.current=true;transcriptRef.current="";
    recognition.onstart=()=>{setState("listening");setTranscript("");setError("")};
    recognition.onresult=(event:any)=>{const text=Array.from(event.results,(result:any)=>result[0].transcript).join(" ").trim();transcriptRef.current=text;setTranscript(text)};
    recognition.onerror=(event:any)=>{if(event.error==="no-speech"&&listeningRef.current)return;listeningRef.current=false;setState("idle");if(event.error!=="aborted")setError(event.error==="not-allowed"?"Zezwól przeglądarce na dostęp do mikrofonu.":"Nie udało się rozpoznać głosu. Spróbuj ponownie.")};
    recognition.onend=()=>{if(listeningRef.current){try{recognition.start()}catch{listeningRef.current=false;setState("idle")}}};
    recognition.start();
  }

  async function approve(){if(!proposal||saving||revisionMode||state==="thinking")return;unlockAudio();stopAudio();setSaving(true);setState("thinking");try{const result=await api.executeT3ach(proposal);setProposal(null);proposalRef.current=null;setResponse(result.message);conversationRef.current=[...conversationRef.current,{role:"assistant" as const,text:result.message}].slice(-10);remember({turns:conversationRef.current,proposal:null,transcript,response:result.message});await onSaved();void speak(`Gotowe. ${result.message}`)}catch(err){const message=err instanceof Error?err.message:"Nie udało się zapisać zmian.";setError(message);setState("idle")}finally{setSaving(false)}}
  useEffect(()=>()=>{listeningRef.current=false;recognitionRef.current?.abort();stopAudio();void audioContextRef.current?.close();audioContextRef.current=null},[]);
  function submit(event:FormEvent){event.preventDefault();unlockAudio();const value=input;if(value.trim().length<3)return;setInput("");void ask(value)}
  const label=state==="listening"?"Słucham — kliknij ponownie, gdy skończysz":state==="thinking"?"Myślę…":state==="speaking"?"Odpowiadam…":"Gotowy";
  return <div className={`voice-t3ach-backdrop ${state}`}><button className="voice-close" onClick={close} aria-label="Zamknij"><X/></button><div className="voice-t3ach-stage"><div className="voice-name"><small>STUDYFLOW AGENT</small><h1>T3ACH</h1></div><button className="voice-orb" onClick={state==="idle"||state==="listening"?listen:undefined} disabled={state==="thinking"||state==="speaking"} aria-label={state==="listening"?"Zakończ wypowiedź":"Rozpocznij rozmowę"}><span className="orb-core"><Sparkles/></span><i/><i/><i/><b className="voice-bars">{Array.from({length:18},(_,index)=><em key={index}/>)}</b></button><div className="voice-state"><span/><strong>{label}</strong><p>{transcript?`„${transcript}”`:response}</p>{response&&transcript&&<small>{response}</small>}</div>{error&&<div className="voice-error">{error}</div>}{voiceError&&<div className="voice-error voice-audio-error" role="status">{voiceError}</div>}{voiceError&&response&&state==="idle"&&<button className="voice-replay" onClick={()=>{stopAudio();readWithDevice(response,speechRequestRef.current,"Czytam odpowiedź głosem urządzenia.")}}><Play/>Czytaj głosem urządzenia</button>}{proposal&&<div className="voice-proposal"><small>PODGLĄD · NIC JESZCZE NIE ZAPISANO</small><h3>{proposal.intent==="session"?proposal.session_title:`${proposal.subject_name} → ${proposal.topic_name}`}</h3><p>{proposal.intent==="session"?`\n${proposal.session_duration_minutes} minut · ${proposal.session_notes??""}`:""}</p><div><button className="secondary" onClick={()=>{setProposal(null);proposalRef.current=null;setRevisionMode(false);remember({turns:conversationRef.current,proposal:null,transcript,response})}}>Odrzuć</button><button className="secondary" type="button" onClick={()=>{setRevisionMode(true);setTextMode(true);setError("");setInput("")}} disabled={saving||state==="thinking"}><Pencil/>Popraw propozycję</button><button className="primary" type="button" onClick={approve} disabled={saving||revisionMode||state==="thinking"}><CheckCircle2/>{saving?"Zapisuję…":"Zatwierdź"}</button></div></div>}{proposal&&<T3achMaterialPreview proposal={proposal}/>}<div className="voice-controls"><button onClick={listen} disabled={state!=="idle"&&state!=="listening"}>{state==="listening"?<MicOff/>:<Mic/>}<span>{state==="listening"?"Zakończ i wyślij":"Mów"}</span></button><button onClick={()=>setTextMode(value=>!value)}><Keyboard/><span>Wpisz</span></button><button onClick={openGenerator}><BookOpen/><span>Notatka / plan</span></button></div>{textMode&&<form className="voice-text-form" onSubmit={submit}><input autoFocus value={input} onChange={event=>setInput(event.target.value)} maxLength={3000} placeholder={revisionMode?"Napisz, co zmienić w propozycji…":"Napisz do T3ACH…"}/><button className="primary" disabled={input.trim().length<3||state==="thinking"}><Send/></button></form>}</div></div>
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
  const [createdTopicId,setCreatedTopicId]=useState<string|null>(null);
  const [manualContent,setManualContent]=useState("");
  const availableTopics=topics.filter(item=>item.subject_uid===subjectId);
  const matchedTopic=availableTopics.find(item=>item.name.trim().toLocaleLowerCase("pl")===topicText.trim().toLocaleLowerCase("pl"));
  const availableTasks=matchedTopic?tasks.filter(item=>item.topic_uid===matchedTopic.topic_uid):[];
  function resetResult(){setNotes(null);setPlan(null);setError("")}
  function chooseSubject(value:string){setSubjectId(value);setTopicText(topics.find(item=>item.subject_uid===value)?.name??"");setTaskText("");setCreatedTopicId(null);resetResult()}
  if(!mode)return <div className="modal-backdrop ai-backdrop" onMouseDown={close}><section className="ai-assistant ai-assistant-v2 ai-hub" onMouseDown={event=>event.stopPropagation()}><button className="icon close" onClick={close}><X/></button><header><span><Sparkles/></span><div><small>STUDYFLOW AI</small><h2>Asystent AI</h2></div></header><div className="ai-hub-grid"><button className="ai-hub-t3ach" onClick={openT3ach}><span className="ai-hub-orb"><Sparkles/></span><div><small>GŁÓWNY ASYSTENT</small><strong>T3ACH</strong><p>Opisz swój cel. T3ACH zaproponuje przedmiot, temat i konkretne zadania, a zapisze je dopiero po Twoim potwierdzeniu.</p><b>Rozpocznij rozmowę <ArrowRight/></b></div></button><div className="ai-hub-tools"><button onClick={()=>setMode("notes")}><BookOpen/><div><strong>Notatka</strong><p>Wyjaśnienie, najważniejsze informacje i pytania kontrolne.</p></div><ChevronRight/></button><button onClick={()=>setMode("plan")}><CalendarDays/><div><strong>Plan nauki</strong><p>Plan podzielony na dni, cele i aktywności.</p></div><ChevronRight/></button></div></div></section></div>;
  if(!subjects.length)return <div className="modal-backdrop ai-backdrop" onMouseDown={close}><section className="ai-assistant ai-assistant-v2" onMouseDown={event=>event.stopPropagation()}><button className="icon close" onClick={close}><X/></button><header><span><Sparkles/></span><div><small>STUDYFLOW AI</small><h2>Zacznij od przedmiotu</h2></div></header><div className="ai-ready"><BookOpen/><h3>Asystent jest gotowy</h3><p>Dodaj pierwszy przedmiot, a potem wpiszesz tutaj nowy temat i od razu wygenerujesz materiał.</p><button className="primary" onClick={onNeedSubject}><CirclePlus/>Dodaj pierwszy przedmiot</button></div></section></div>;
  async function generate(){
    if(!mode||!subjectId||!topicText.trim())return;
    if(mode==="plan"&&(!Number.isInteger(Number(days))||Number(days)<1||Number(days)>30||!Number.isInteger(Number(minutes))||Number(minutes)<10||Number(minutes)>240)){setError("Wpisz 1–30 dni i 10–240 minut.");return}
    setBusy(true);resetResult();
    try{
      const topic=matchedTopic??(createdTopicId?{topic_uid:createdTopicId}:await api.addTopic({name:topicText.trim(),subject_uid:subjectId,difficulty:"Średni"}));
      setCreatedTopicId(topic.topic_uid);
      const selectedTask=tasks.find(item=>item.topic_uid===topic.topic_uid&&item.title.trim().toLocaleLowerCase("pl")===taskText.trim().toLocaleLowerCase("pl"));
      const context={task_uid:selectedTask?.task_uid??null,custom_goal:selectedTask?null:taskText.trim()||null};
      if(mode==="notes")setNotes(await api.generateNotes(topic.topic_uid,{detail_level:level,...context}));
      else setPlan(await api.generatePlan(topic.topic_uid,{days:Number(days),minutes_per_day:Number(minutes),...context}));
      await onSaved();
    }catch(err){setError(err instanceof Error?err.message:"Nie udało się wygenerować materiału.")}finally{setBusy(false)}
  }
  async function useFallback(){if(!subjectId||!topicText.trim())return;if(mode==="plan"&&(!Number.isInteger(Number(days))||Number(days)<1||Number(days)>30||!Number.isInteger(Number(minutes))||Number(minutes)<10||Number(minutes)>240)){setError("Wpisz 1–30 dni i 10–240 minut.");return}setBusy(true);setError("");try{const topic=matchedTopic??(createdTopicId?{topic_uid:createdTopicId}:await api.addTopic({name:topicText.trim(),subject_uid:subjectId,difficulty:"Średni"}));setCreatedTopicId(topic.topic_uid);if(mode==="notes"){if(!manualContent.trim())throw new Error("Wpisz treść notatki.");setNotes(await api.manualNote(topic.topic_uid,topicText.trim(),manualContent.trim()))}else setPlan(await api.fallbackPlan(topic.topic_uid,taskText.trim()||topicText.trim(),Number(days),Number(minutes)));await onSaved()}catch(err){setError(err instanceof Error?err.message:"Nie udało się zapisać materiału.")}finally{setBusy(false)}}
  return <div className="modal-backdrop ai-backdrop" onMouseDown={close}><section className="ai-assistant ai-assistant-v2" onMouseDown={event=>event.stopPropagation()}><button className="icon close" onClick={close}><X/></button><header><span><Sparkles/></span><div><small>STUDYFLOW AI</small><h2>{mode==="notes"?"Generator notatek":mode==="plan"?"Plan nauki":"Co chcesz przygotować?"}</h2></div></header>{!mode?<div className="ai-mode-grid"><button onClick={()=>setMode("notes")}><BookOpen/><strong>Notatka</strong><p>Czytelne wyjaśnienie, kluczowe informacje i pytania kontrolne.</p><span>Wybierz <ChevronRight/></span></button><button onClick={()=>setMode("plan")}><CalendarDays/><strong>Plan nauki</strong><p>Plan podzielony na dni, cele i konkretne aktywności.</p><span>Wybierz <ChevronRight/></span></button></div>:<><div className="ai-config"><button className="ai-back" onClick={()=>{setMode(null);resetResult()}}><ArrowLeft/>Zmień rodzaj</button><div className="ai-form-grid"><label>Przedmiot<select value={subjectId} onChange={event=>chooseSubject(event.target.value)} disabled={busy}>{subjects.map(item=><option value={item.subject_uid} key={item.subject_uid}>{item.name}</option>)}</select></label><label>Temat <span>— wybierz lub wpisz nowy</span><input list="ai-topic-options" value={topicText} onChange={event=>{setTopicText(event.target.value);setTaskText("");setCreatedTopicId(null);resetResult()}} disabled={busy} maxLength={100} placeholder="np. Równania kwadratowe"/><datalist id="ai-topic-options">{availableTopics.map(item=><option value={item.name} key={item.topic_uid}/>)}</datalist><small className="ai-field-help">Jeżeli wpiszesz nową nazwę, temat zostanie utworzony automatycznie.</small></label><label className="ai-goal-field">Zadanie lub cel <span>— wybierz lub wpisz własny</span><input list="ai-task-options" value={taskText} onChange={event=>{setTaskText(event.target.value);resetResult()}} disabled={busy} maxLength={500} placeholder="np. Przygotuj mnie do kartkówki"/><datalist id="ai-task-options">{availableTasks.map(item=><option value={item.title} key={item.task_uid}/>)}</datalist><small className="ai-field-help">Własny opis utworzy nowe zadanie z krótkim tytułem dobranym przez AI.</small></label>{mode==="notes"?<label>Długość<select value={level} onChange={event=>setLevel(event.target.value as typeof level)} disabled={busy}><option value="short">Krótka</option><option value="standard">Standardowa</option><option value="detailed">Szczegółowa</option></select></label>:<><label>Liczba dni<input type="number" min={1} max={30} value={days} onChange={event=>setDays(event.target.value)}/></label><label>Orientacyjnie minut dziennie<input type="number" min={10} max={240} value={minutes} onChange={event=>setMinutes(event.target.value)}/></label></>}</div></div>{busy&&<div className="ai-generating"><span className="loader"/><h3>{mode==="notes"?"Tworzę notatkę…":"Układam plan…"}</h3><p>To może potrwać kilkanaście sekund.</p></div>}{error&&<div className="ai-error"><p>{error}</p><small>Twój wpis pozostaje w formularzu. Możesz ponowić generowanie.</small><div>{mode==="notes"?<><textarea value={manualContent} onChange={event=>setManualContent(event.target.value)} maxLength={12000} placeholder="Możesz też wpisać własną notatkę i zapisać ją w materiałach."/><button className="secondary" disabled={busy||!manualContent.trim()} onClick={useFallback}>Zapisz własną notatkę</button></>:<button className="secondary" disabled={busy} onClick={useFallback}>Utwórz prosty plan bez AI</button>}</div></div>}{notes&&<div className="ai-result"><h2>{notes.title}</h2><p className="ai-summary">{notes.summary}</p>{notes.sections.map((section,i)=><article key={`${section.heading}-${i}`}><h3>{section.heading}</h3><p>{section.content}</p></article>)}<h3>Najważniejsze punkty</h3><ul>{notes.key_points.map((point,i)=><li key={i}>{point}</li>)}</ul><h3>Sprawdź się</h3><ol>{notes.review_questions.map((question,i)=><li key={i}>{question}</li>)}</ol></div>}{plan&&<div className="ai-result"><h2>{plan.title}</h2><p className="ai-summary">{plan.overview}</p><div className="ai-plan-steps">{plan.steps.map(step=><article key={step.day}><span>{planDayLabel(step.scheduled_date??plan.start_date,step.scheduled_date?1:step.day)}</span><div><h3>{step.title}</h3><p>{step.objective}</p><ul>{step.activities.map(activity=><li key={activity}>{activity}</li>)}</ul></div><strong>{step.duration_minutes} min</strong></article>)}</div><h3>Po czym poznasz, że umiesz?</h3><ul>{plan.success_criteria.map((item,i)=><li key={i}>{item}</li>)}</ul></div>}<footer><button className="primary" disabled={busy||!subjectId||!topicText.trim()} onClick={generate}><Sparkles/>{notes||plan?"Generuj ponownie":mode==="notes"?"Generuj notatkę":"Ułóż plan"}</button></footer></>}</section></div>
}

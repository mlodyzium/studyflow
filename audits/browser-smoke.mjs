import assert from 'node:assert/strict';
import {chromium} from '/tmp/browser/node_modules/playwright-core/index.mjs';
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
const context=await browser.newContext({viewport:{width:1280,height:900}});
const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
const user={user_uid:'u1',username:'Tester',email:null,created_at:'2026-09-30T12:00:00Z',timezone:'Europe/Warsaw',language:'pl',preferred_minutes:45,preferred_study_time:'18:00',task_shortcut:'Alt+T',ai_shortcut:'Alt+A',onboarding_complete:true};
const subject={subject_uid:'s1',name:'Matematyka',user_uid:'u1',exam_date:null,color:'#c8f05a',tags:[],archived_at:null};
const note={task_title:'Nauka',title:'Testowa notatka',summary:'Podstawy',sections:[{heading:'Wzór',content:'y=ax+b'}],key_points:['Współczynniki'],review_questions:[]};
let drafts=0,saves=0,speeches=0,bulkCount=0,releaseAsk,askStarted;const asked=new Promise(r=>askStarted=r);
const proposal={proposal_uid:'p1',reply:'Gotowy podgląd',needs_clarification:false,question:null,subject_name:'Matematyka',topic_name:'Algebra',intent:'notes',material_types:['notes'],tasks:[],preview:note};
await context.addInitScript(()=>{localStorage.setItem('studyflow_token','browser-test');if(!localStorage.getItem('studyflow_language'))localStorage.setItem('studyflow_language','pl')});
await page.route('**/api/**',async route=>{
 const path=new URL(route.request().url()).pathname.replace('/api','');const method=route.request().method();
 let data;
 if(path==='/users/me'){if(method==='PATCH')user.language=route.request().postDataJSON().language;data=user;}
 else if(path==='/subjects')data={items:[subject],total:1,pages:1,page:1,page_size:100};
 else if(['/topics','/tasks','/study-sessions'].includes(path))data={items:[],total:0,pages:1,page:1,page_size:100};
 else if(path==='/study-sessions/summary')data={today_minutes:0,week_minutes:0,streak:0};
 else if(['/plans','/reviews','/ai/t3ach/history'].includes(path))data=[];
 else if(path==='/ai/materials/draft'){drafts++;data=proposal;}
 else if(path==='/ai/t3ach/execute'){saves++;data={message:'Zapisano',task_uids:[]};}
 else if(path==='/ai/materials')data=Array.from({length:1001},(_,i)=>({material_uid:`m${i}`,topic_uid:'t1',material_type:'notes',title:`Notatka ${i}`,content:note,created_at:'2026-09-30T12:00:00Z'}));
 else if(path==='/ai/history/bulk-delete'){bulkCount=route.request().postDataJSON().ids.length;await route.fulfill({status:204});return;}
 else if(path==='/ai/t3ach/propose'){askStarted();await new Promise(r=>releaseAsk=r);data=proposal;}
 else if(path==='/ai/t3ach/speech'){speeches++;await route.fulfill({status:503,json:{detail:'offline'}});return;}
 else throw Error(`Unexpected ${method} ${path}`);
 try{await route.fulfill({status:200,json:data})}catch(e){if(path!=='/ai/t3ach/propose')throw e;}
});
try{
 await page.goto('http://studyflow-ui-audit');
 await page.getByRole('button',{name:'Otwórz Asystenta AI'}).click();
 await page.locator('.ai-hub-tools button').filter({hasText:'Notatka'}).click();
 await page.getByPlaceholder('np. Równania kwadratowe').fill('Algebra');
 await page.getByRole('button',{name:'Generuj notatkę',exact:true}).click();
 await page.getByText('Podgląd — jeszcze niezapisany').waitFor();assert.equal(saves,0);
 await page.getByRole('button',{name:'Generuj ponownie',exact:true}).click();
 await page.getByText('Podgląd — jeszcze niezapisany').waitFor();assert.equal(saves,0);assert.equal(drafts,2);
 await page.getByRole('button',{name:'Zatwierdź i zapisz'}).click();
 await page.getByText('Materiał zapisany',{exact:true}).waitFor();assert.equal(saves,1);
 await page.locator('.ai-assistant .close').click();
 await page.getByRole('button',{name:'Historia materiałów',exact:true}).click();
 await page.getByLabel('Zaznacz pierwsze 1000').check();
 await page.getByText('Zaznaczono: 1000',{exact:true}).waitFor();
 page.once('dialog',dialog=>dialog.accept());await page.getByRole('button',{name:'Usuń zaznaczone (1000)'}).click();
 await page.getByRole('button',{name:'Materiały (1)',exact:true}).waitFor();assert.equal(bulkCount,1000);
 await page.locator('.ai-history-modal .close').click();
 await page.getByTitle('Porozmawiaj z T3ACH').click();await page.getByRole('button',{name:'Wpisz',exact:true}).click();
 await page.getByPlaceholder('Napisz do T3ACH…').fill('Napisz notatkę');await page.getByPlaceholder('Napisz do T3ACH…').press('Enter');await asked;
 await page.getByRole('button',{name:'Zamknij',exact:true}).click();releaseAsk();
 await page.getByRole('button',{name:'Otwórz Asystenta AI'}).waitFor();
 await page.setViewportSize({width:390,height:844});
 await page.getByTitle('Porozmawiaj z T3ACH').click();
 await page.getByText('Kliknij kulę i powiedz, czego potrzebujesz.',{exact:true}).waitFor();
 assert.equal(speeches,0);assert.equal(await page.evaluate(()=>localStorage.getItem('studyflow_t3ach_u1')),null);
 await page.setViewportSize({width:1280,height:900});
 user.language='en';await page.evaluate(()=>localStorage.setItem('studyflow_language','en'));await page.reload();
 await page.getByText('What to do now',{exact:true}).waitFor();
 assert.equal(await page.locator('html').getAttribute('lang'),'en');
 await page.locator('.profile-settings .profile').click();
 await page.getByRole('button',{name:'User settings'}).click();
 await page.getByLabel('Language').selectOption('pl');
 await page.getByRole('button',{name:'Save settings'}).click();
 await page.getByText('Co warto zrobić teraz',{exact:true}).waitFor();
 assert.equal(await page.locator('html').getAttribute('lang'),'pl');
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({browser:'Chromium',checks:['preview without saving','regenerate without duplicate','explicit approval','bulk limit 1000','close cancels late AI response','mobile assistant opens','English interface','switch to Polish and persist','no JS runtime errors'],result:'passed'}));
}finally{await browser.close()}

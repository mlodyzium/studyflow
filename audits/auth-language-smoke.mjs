import assert from 'node:assert/strict';
import {chromium} from '/tmp/browser/node_modules/playwright-core/index.mjs';

const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
const context=await browser.newContext({viewport:{width:1280,height:900}});
const page=await context.newPage();
const errors=[];
page.on('pageerror',error=>errors.push(error.message));
let registered,registeredHeader,loginHeader,updated;
const user={user_uid:'u1',username:'Learner',email:null,created_at:'2026-09-30T12:00:00Z',timezone:'Europe/Warsaw',language:'pl',preferred_minutes:45,preferred_study_time:'18:00',task_shortcut:'',ai_shortcut:'',onboarding_complete:true};

await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname.replace('/api','');
  const method=route.request().method();
  let data;
  if(path==='/auth/register'){
    registered=route.request().postDataJSON();
    registeredHeader=route.request().headers()['accept-language'];
    data=user;
  } else if(path==='/auth/login'){
    loginHeader=route.request().headers()['accept-language'];
    data={access_token:'browser-test'};
  } else if(path==='/users/me'&&method==='PATCH'){
    updated=route.request().postDataJSON();
    user.language=updated.language;
    data=user;
  } else if(path==='/users/me')data=user;
  else if(path==='/subjects')data={items:[],total:0,pages:1,page:1,page_size:100};
  else if(['/topics','/tasks','/study-sessions'].includes(path))data={items:[],total:0,pages:1,page:1,page_size:100};
  else if(path==='/study-sessions/summary')data={today_minutes:0,week_minutes:0,streak:0};
  else if(['/plans','/reviews'].includes(path))data=[];
  else throw Error(`Unexpected ${method} ${path}`);
  await route.fulfill({status:path==='/auth/register'?201:200,json:data});
});

try{
  await page.goto('http://studyflow-ui-audit');
  const language=page.getByRole('button',{name:'Language'});
  await language.waitFor();
  assert.equal(await page.getByRole('menuitemradio').count(),0);
  assert.equal(await page.locator('html').getAttribute('lang'),'en');
  await page.locator('input[name="username"]').fill('Learner');
  await page.locator('input[name="password"]').fill('secret123');
  await language.click();
  assert.equal(await page.getByRole('menuitemradio',{name:'English'}).getAttribute('aria-checked'),'true');
  await page.keyboard.press('Escape');
  assert.equal(await page.getByRole('menuitemradio').count(),0);
  await language.click();
  await page.getByRole('menuitemradio',{name:'Polski'}).click();
  await page.getByText('Gotowy na kolejny krok?',{exact:true}).waitFor();
  assert.equal(await page.locator('html').getAttribute('lang'),'pl');
  assert.equal(await page.locator('input[name="username"]').inputValue(),'Learner');
  assert.equal(await page.locator('input[name="password"]').inputValue(),'secret123');
  await page.getByRole('button',{name:'Utwórz je'}).click();
  await page.locator('input[name="confirm_password"]').fill('secret123');
  await page.getByRole('button',{name:'Załóż konto'}).click();
  await page.getByText('Co warto zrobić teraz',{exact:true}).waitFor();
  assert.equal(registered.language,'pl');
  assert.equal(registeredHeader,'pl');
  assert.equal(loginHeader,'pl');
  assert.equal(updated.language,'pl');
  await page.locator('.profile-settings .profile').click();
  const profileMenu=page.locator('.profile-settings-menu');
  assert.equal(await profileMenu.locator(':scope > :first-child').getAttribute('class'),'profile-language');
  await profileMenu.getByRole('combobox',{name:'Język'}).selectOption('en');
  await page.waitForFunction(() => document.documentElement.lang === 'en');
  await page.getByRole('heading',{name:'Hello, Learner 👋'}).waitFor();
  assert.equal(updated.language,'en');
  await page.locator('.profile-settings .profile').click();
  await page.getByRole('button',{name:'User settings'}).click();
  assert.equal(await page.locator('.profile-modal select[name="language"]').count(),0);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({browser:'Chromium',checks:['globe menu and Escape','language switch on auth screen','form values preserved','registration uses Polish','login uses Polish','profile menu language selection','account preference updated','language removed from user settings'],result:'passed'}));
}finally{await browser.close()}

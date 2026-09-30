import {test} from 'node:test';
import assert from 'node:assert/strict';
import {planDayLabel} from '../src/features/ai/planDates.ts';

let selectedLanguage='en';
globalThis.localStorage={getItem:()=>selectedLanguage};

test('explicit dates keep consecutive day numbers across a weekend',()=>{
  selectedLanguage='pl';
  const labels=['2026-10-02','2026-10-05','2026-10-06'].map((date,index)=>planDayLabel('2026-10-02',index+1,date));
  assert.match(labels[0],/^Dzień 1 · piątek, 2 października$/);
  assert.match(labels[1],/^Dzień 2 · poniedziałek, 5 października$/);
  assert.match(labels[2],/^Dzień 3 · wtorek, 6 października$/);
});
test('legacy plans without dates use the start date and step number',()=>{
  selectedLanguage='pl';
  assert.match(planDayLabel('2026-09-30',2),/^Dzień 2 · czwartek, 1 października$/);
  assert.equal(planDayLabel(null,3),'Dzień 3');
});

test('English is the default for plan day labels',()=>{
  selectedLanguage='en';
  assert.equal(planDayLabel(null,3),'Day 3');
  assert.match(planDayLabel('2026-10-02',1),/^Day 1 · Friday 2 October$/);
});

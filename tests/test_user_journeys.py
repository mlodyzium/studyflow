from tests.test_api import client, auth_headers, create_subject
from app.services import ai as ai_service
from app.schemas.ai import T3achProposal, GeneratedStudyPlan
from fastapi.testclient import TestClient
from app.main import app
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def setup_plan(client, headers):
    subject=create_subject(client,headers,'Matematyka')
    topic=client.post('/topics',headers=headers,json={'name':'Algebra','subject_uid':subject['subject_uid']}).json()
    response=client.post(f"/ai/topics/{topic['topic_uid']}/fallback-plan",headers=headers,json={'goal':'Ćwiczenie algebry','days':3,'minutes_per_day':30})
    assert response.status_code==200,response.text
    return topic,client.get('/plans',headers=headers).json()[0]


def test_audit_ai_rename_conflict(client, monkeypatch):
    headers,_=auth_headers(client,'audit-rename')
    create_subject(client,headers,'Matematyka'); create_subject(client,headers,'Fizyka')
    async def proposal(*args,**kwargs):
        return T3achProposal(reply='Zmieniam nazwę',intent='edit',target_kind='subject',target_name='Matematyka',new_name='Fizyka')
    monkeypatch.setattr(ai_service,'generate_t3ach_proposal',proposal)
    p=client.post('/ai/t3ach/propose',headers=headers,json={'message':'Zmień nazwę Matematyka na Fizyka'}).json()
    with TestClient(app,raise_server_exceptions=False) as http:
        result=http.post('/ai/t3ach/execute',headers=headers,json={'proposal_uid':p['proposal_uid']})
    assert result.status_code in (409,422),f'actual status={result.status_code}'


def test_audit_move_calendar_task_syncs_plan(client):
    headers,_=auth_headers(client,'audit-calendar')
    _,plan=setup_plan(client,headers)
    plan=client.post(f"/plans/{plan['plan_uid']}/calendar-tasks",headers=headers,json={'create_tasks':True}).json()
    day=plan['days'][0]
    target=(date.fromisoformat(day['scheduled_date'])+timedelta(days=3)).isoformat()
    assert client.patch(f"/tasks/{day['calendar_task_uid']}",headers=headers,json={'deadline':target+'T12:00:00Z'}).status_code==200
    actual=client.get(f"/plans/{plan['plan_uid']}",headers=headers).json()['days'][0]['scheduled_date']
    assert actual==target,f'task={target}, plan={actual}'


def test_audit_plan_day_null_validation(client):
    headers,_=auth_headers(client,'audit-null')
    _,plan=setup_plan(client,headers)
    with TestClient(app,raise_server_exceptions=False) as http:
        result=http.patch(f"/plans/{plan['plan_uid']}/days/{plan['days'][0]['day_uid']}",headers=headers,json={'title':None})
    assert result.status_code==422,f'actual status={result.status_code}'


def test_audit_direct_generator_tomorrow(client,monkeypatch):
    headers,_=auth_headers(client,'audit-start')
    topic,_=setup_plan(client,headers)
    starts=[]
    async def generate(*args,**kwargs):
        starts.append(kwargs['start_date'])
        return GeneratedStudyPlan(task_title='Algebra',title='Plan',overview='Nauka',steps=[{'day':i,'title':'Etap','objective':'Nauka','activities':['Zadania'],'duration_minutes':30} for i in range(1,args[4]+1)],success_criteria=['Rozumiem'])
    monkeypatch.setattr(ai_service,'generate_study_plan',generate)
    tomorrow=datetime.now(timezone.utc).astimezone(ZoneInfo('Europe/Warsaw')).date()+timedelta(days=1)
    result=client.post(f"/ai/topics/{topic['topic_uid']}/plan",headers=headers,json={'days':3,'minutes_per_day':30,'custom_goal':'Zacznij od jutra'})
    assert result.status_code==200,result.text
    assert starts==[tomorrow],str(starts)


def test_audit_deleted_conversation_continuation(client,monkeypatch):
    headers,_=auth_headers(client,'audit-history')
    async def proposal(*args,**kwargs):
        return T3achProposal(reply='Jaki temat?',needs_clarification=True,intent='study_plan')
    monkeypatch.setattr(ai_service,'generate_t3ach_proposal',proposal)
    first=client.post('/ai/t3ach/propose',headers=headers,json={'message':'Plan nauki'}).json()
    assert client.post('/ai/history/bulk-delete',headers=headers,json={'kind':'chats','ids':[first['proposal_uid']]}).status_code==204
    result=client.post('/ai/t3ach/propose',headers=headers,json={'message':'Algebra','previous_proposal_uid':first['proposal_uid'],'history':[{'role':'user','text':'Plan nauki'}]})
    assert result.status_code==200,f'actual={result.status_code} {result.text}'


def test_audit_plan_start_metadata_after_moving_first_day(client):
    headers,_=auth_headers(client,'audit-plan-start')
    _,plan=setup_plan(client,headers)
    target=(date.fromisoformat(plan['start_date'])-timedelta(days=1)).isoformat()
    assert client.patch(f"/plans/{plan['plan_uid']}/days/{plan['days'][0]['day_uid']}",headers=headers,json={'scheduled_date':target}).status_code==200
    actual=client.get(f"/plans/{plan['plan_uid']}",headers=headers).json()
    assert actual['start_date']==target,f"start={actual['start_date']}, first day={target}"


def test_audit_combined_redistribution_and_content_change(client,monkeypatch):
    headers,_=auth_headers(client,'audit-mixed')
    calls=[]
    async def propose(*args,**kwargs):
        return T3achProposal(reply='Poprawiam',intent='study_plan',subject_name='Matematyka',topic_name='Algebra',days=3,minutes_per_day=30)
    async def generate(*args,**kwargs):
        calls.append(args[-1])
        return GeneratedStudyPlan(task_title='Algebra',title='Plan',overview='Nauka',steps=[{'day':i,'title':'Etap','objective':'Nauka','activities':['Zadania tekstowe' if len(calls)>1 else 'Czytanie teorii'],'duration_minutes':30} for i in range(1,args[4]+1)],success_criteria=['Rozumiem'])
    monkeypatch.setattr(ai_service,'generate_t3ach_proposal',propose)
    monkeypatch.setattr(ai_service,'generate_study_plan',generate)
    first=client.post('/ai/t3ach/propose',headers=headers,json={'message':'Plan algebry na 3 dni po 30 minut'}).json()
    result=client.post('/ai/t3ach/propose',headers=headers,json={'message':'Rozłóż czas równomiernie i dodaj zadania tekstowe','previous_proposal_uid':first['proposal_uid']})
    assert result.status_code==200,result.text
    assert 'Zadania tekstowe' in result.json()['preview']['steps'][0]['activities'],result.json()['preview']['steps'][0]['activities']


def test_audit_future_session_is_not_completed_study(client,monkeypatch):
    headers,_=auth_headers(client,'audit-session')
    async def propose(*args,**kwargs):
        return T3achProposal(reply='Sesja jutro',intent='session',subject_name='Matematyka',topic_name='Algebra',session_title='Nauka jutro',session_duration_minutes=45)
    monkeypatch.setattr(ai_service,'generate_t3ach_proposal',propose)
    first=client.post('/ai/t3ach/propose',headers=headers,json={'message':'Zaplanuj sesję algebry jutro na 45 minut'}).json()
    result=client.post('/ai/t3ach/execute',headers=headers,json={'proposal_uid':first['proposal_uid']})
    assert result.status_code==200,result.text
    summary=client.get('/study-sessions/summary',headers=headers).json()
    assert summary['today_minutes']==0,summary


def test_draft_does_not_create_topic_until_acceptance(client, monkeypatch):
    from app.schemas.ai import GeneratedNotes
    headers,_=auth_headers(client,'draft-preview')
    subject=create_subject(client,headers,'Matematyka')
    async def notes(*args,**kwargs):
        return GeneratedNotes(task_title='Nauka',title='Notatka',summary='Podstawy',sections=[{'heading':'Wzór','content':'y=ax+b'}],key_points=['Wzór'])
    monkeypatch.setattr(ai_service,'generate_topic_notes',notes)
    data={'subject_uid':subject['subject_uid'],'topic_name':'Nowy temat','mode':'notes'}
    first=client.post('/ai/materials/draft',headers=headers,json=data)
    assert first.status_code==200,first.text
    assert client.get('/topics',headers=headers).json()['total']==0
    assert client.get('/tasks',headers=headers).json()['total']==0
    assert client.get('/ai/materials',headers=headers).json()==[]
    assert client.post('/ai/materials/draft',headers=headers,json=data).status_code==200
    assert client.get('/topics',headers=headers).json()['total']==0
    uid=first.json()['proposal_uid']
    assert client.post('/ai/t3ach/execute',headers=headers,json={'proposal_uid':uid}).status_code==200
    assert client.post('/ai/t3ach/execute',headers=headers,json={'proposal_uid':uid}).status_code==409
    assert client.get('/topics',headers=headers).json()['total']==1
    assert len(client.get('/ai/materials',headers=headers).json())==1


def test_draft_failure_and_foreign_subject_do_not_write(client,monkeypatch):
    from fastapi import HTTPException
    headers,_=auth_headers(client,'draft-fail')
    other,_=auth_headers(client,'draft-foreign')
    subject=create_subject(client,headers,'Matematyka')
    async def fail(*args,**kwargs): raise HTTPException(status_code=503,detail='AI niedostępne')
    monkeypatch.setattr(ai_service,'generate_topic_notes',fail)
    data={'subject_uid':subject['subject_uid'],'topic_name':'Nowy temat','mode':'notes'}
    assert client.post('/ai/materials/draft',headers=other,json=data).status_code==404
    assert client.post('/ai/materials/draft',headers=headers,json=data).status_code==503
    assert client.get('/topics',headers=headers).json()['total']==0
    assert client.get('/ai/t3ach/history',headers=headers).json()==[]


def test_plan_operations_deny_other_account(client):
    headers,_=auth_headers(client,'secure-plan')
    other,_=auth_headers(client,'secure-other')
    _,plan=setup_plan(client,headers)
    root=f"/plans/{plan['plan_uid']}"
    day=root+f"/days/{plan['days'][0]['day_uid']}"
    operations=[('GET',root,None),('DELETE',root,None),('PATCH',root+'/shift',{'start_date':'2026-10-10'}),
                ('POST',root+'/duplicate',{'start_date':'2026-10-10'}),('POST',root+'/calendar-tasks',{'create_tasks':True}),
                ('PATCH',day,{'is_done':True}),('POST',day+'/regenerate',{'custom_goal':'Zmień'})]
    for method,url,data in operations:
        result=client.request(method,url,headers=other,json=data)
        assert result.status_code==404,(method,url,result.text)
    assert client.get(root,headers=headers).status_code==200


def test_patch_nulls_rejected_and_five_minute_day_supported(client):
    headers,_=auth_headers(client,'patch-nulls')
    topic,plan=setup_plan(client,headers)
    for path,field in [(f"/subjects/{topic['subject_uid']}",'name'),(f"/topics/{topic['topic_uid']}",'subject_uid')]:
        assert client.patch(path,headers=headers,json={field:None}).status_code==422
    day=f"/plans/{plan['plan_uid']}/days/{plan['days'][0]['day_uid']}"
    assert client.patch(day,headers=headers,json={'duration_minutes':5}).status_code==200
    assert client.patch(day,headers=headers,json={'activities':['   ']}).status_code==422


def test_note_export_escapes_html_and_does_not_leak(client):
    headers,_=auth_headers(client,'export-owner')
    other,_=auth_headers(client,'export-other')
    subject=create_subject(client,headers,'Matematyka')
    response=client.post('/ai/materials/draft',headers=headers,json={'subject_uid':subject['subject_uid'],'topic_name':'Test','mode':'notes','fallback':True,'manual_content':'<script>alert(1)</script>'})
    assert response.status_code==200,response.text
    assert client.post('/ai/t3ach/execute',headers=headers,json={'proposal_uid':response.json()['proposal_uid']}).status_code==200
    material=client.get('/ai/materials',headers=headers).json()[0]['material_uid']
    printed=client.get(f'/ai/materials/{material}/print',headers=headers)
    assert '<script>alert(1)</script>' not in printed.text
    assert '&lt;script&gt;' in printed.text
    for ending in ['print','export.md']:
        assert client.get(f'/ai/materials/{material}/{ending}',headers=other).status_code==404
    assert client.get('/users/me',headers={'Authorization':'Bearer malformed.token'}).status_code==401


def test_repeated_equalization_keeps_new_content(client,monkeypatch):
    headers,_=auth_headers(client,'audit-preserve-content')
    calls=[]
    async def propose(*args,**kwargs):
        return T3achProposal(reply='Poprawiam',intent='study_plan',subject_name='Matematyka',topic_name='Algebra',days=3,minutes_per_day=30,revision_changes_content='tekstowe' in args[0])
    async def generate(*args,**kwargs):
        calls.append(args[-1])
        return GeneratedStudyPlan(task_title='Algebra',title='Plan',overview='Nauka',steps=[{'day':i,'title':'Etap','objective':'Nauka','activities':['Zadania tekstowe' if len(calls)>1 else 'Teoria'],'duration_minutes':30} for i in range(1,args[4]+1)],success_criteria=['Rozumiem'])
    monkeypatch.setattr(ai_service,'generate_t3ach_proposal',propose)
    monkeypatch.setattr(ai_service,'generate_study_plan',generate)
    first=client.post('/ai/t3ach/propose',headers=headers,json={'message':'Plan algebry na 3 dni po 30 minut'}).json()
    second=client.post('/ai/t3ach/propose',headers=headers,json={'message':'Wyrównaj czas i dodaj zadania tekstowe','previous_proposal_uid':first['proposal_uid']}).json()
    third=client.post('/ai/t3ach/propose',headers=headers,json={'message':'Wyrównaj czas ponownie','previous_proposal_uid':second['proposal_uid']})
    assert third.status_code==200,third.text
    assert third.json()['preview']['steps'][0]['activities']==['Zadania tekstowe']


def test_required_user_fields_and_oversized_task_are_validated(client):
    headers,_=auth_headers(client,'audit-fields')
    topic,_=setup_plan(client,headers)
    assert client.patch('/users/me',headers=headers,json={'timezone':None}).status_code==422
    assert client.post('/tasks',headers=headers,json={'topic_uid':topic['topic_uid'],'title':'x'*161}).status_code==422


def test_offline_draft_remains_available_when_ai_quota_is_exhausted(client,monkeypatch):
    from fastapi import HTTPException
    headers,_=auth_headers(client,'offline-quota')
    subject=create_subject(client,headers,'Matematyka')
    def limited(*args): raise HTTPException(status_code=429,detail='Limit AI')
    monkeypatch.setattr('app.routers.ai._limit_generation',limited)
    data={'subject_uid':subject['subject_uid'],'topic_name':'Algebra','mode':'notes','manual_content':'Moja własna notatka'}
    assert client.post('/ai/materials/draft',headers=headers,json=data).status_code==429
    assert client.post('/ai/materials/draft',headers=headers,json={**data,'fallback':True}).status_code==200

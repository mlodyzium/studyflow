import sys
sys.path.insert(0, '/app/tests')
from test_api import client, auth_headers, create_subject
from app.services import ai as ai_service
from app.schemas.ai import T3achProposal, GeneratedStudyPlan
from fastapi.testclient import TestClient
from app.main import app
from datetime import date, timedelta


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
    from app.services import plans
    monkeypatch.setattr(plans,'start_date_for',lambda *args:date(2026,9,30))
    result=client.post(f"/ai/topics/{topic['topic_uid']}/plan",headers=headers,json={'days':3,'minutes_per_day':30,'custom_goal':'Zacznij od jutra'})
    assert result.status_code==200,result.text
    assert starts==[date(2026,10,1)],str(starts)


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

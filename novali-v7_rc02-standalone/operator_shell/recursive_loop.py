"""Reviewed terminal lessons -> Novali questions -> bounded practice.

This controller never reviews its own questions or raises a spending ceiling.
New questions retain ancestor costs and cannot reset exhausted follow-up depth.
"""
from __future__ import annotations
import copy
import secrets
import time
from pathlib import Path
from . import research_procedures as records, recursive_growth as growth
from . import recursive_failure_review as recovery, recursive_practice_checks as checks
from . import recursive_evaluator as evaluator, recursive_causal as causal, learning_episodes as learning
from .research_tools import read_json,write_json,digest

MAX_QUESTIONS_PER_ROOT=3
FOCI=('rule_dispatch','state_encoding')


def configure(root: Path, *, enabled: bool, authority_reference: str, question_contract: str='executable_question_v2') -> dict:
    if type(enabled) is not bool or len(authority_reference)<16:raise ValueError('explicit_loop_policy_required')
    if question_contract not in ('legacy_v1','executable_question_v2'):raise ValueError('known_question_contract_required')
    result=records.store(root,'recursive_loop_policies',{'enabled':enabled,'authority_reference':authority_reference,'question_contract':question_contract,
        'max_questions_per_root':MAX_QUESTIONS_PER_ROOT,'question_calls':2,'practice_calls':2,
        'allowance_added':0,'requires_independent_question_review':True})
    write_json(root/'research_methods/recursive_loop_policy_latest.json',{'policy_id':result['id']})
    return result


def policy(root: Path) -> dict:
    pointer=read_json(root/'research_methods/recursive_loop_policy_latest.json')
    return records.read(root,'recursive_loop_policies',pointer['policy_id']) if pointer else {}


def review_terminal(root: Path, episode_id: str, *, reviewer: str, evidence_reference: str) -> dict:
    prior=next((r for r in growth.rows(root,'recursive_terminal_lessons') if r['episode_id']==episode_id),None)
    if prior:
        if prior['implementation']!=records.implementation():raise ValueError('terminal_lesson_requires_revalidation')
        return prior
    episode,task,account,attempt=recovery.owned(root,episode_id)
    if episode.get('followup_depth',0)<recovery.MAX_FOLLOWUPS:raise ValueError('terminal_lineage_required')
    review=recovery.review(root,episode_id,decision='close',reviewer=reviewer,evidence_reference=evidence_reference)
    # A closed, independently replayed receipt is evidence, not retry authority.
    if review['implementation']!=records.implementation():raise ValueError('terminal_review_requires_revalidation')
    return records.store(root,'recursive_terminal_lessons',{'episode_id':episode_id,'review_id':review['id'],
        'root_episode_id':episode.get('root_episode_id',episode_id),'source_id':episode['source_id'],
        'attempt_id':attempt['id'],'attempt_sha256':digest(attempt),'implementation':records.implementation(),
        'proposal':review['prior_proposal'],'report':review['prior_instrument_report'],
        'protected_states':review['protected_discovery_states'],'unresolved':review['findings']['findings'],
        'retained_usage':read_json(root/'research_methods/episode_accounts'/(episode_id+'.json'))['usage'],
        'available_focus':list(FOCI),'scope':'paired_presence_diagnostics_of_cached_record_primitives',
        'scientific_progress_credited':False,'allowance_added':0})


def validate_lesson(root: Path, lesson: dict) -> None:
    from .recursive_review_queue import lesson_current
    if not lesson_current(root,lesson):raise ValueError('terminal_lesson_requires_revalidation')
    attempt=records.read(root,'attempts',lesson['attempt_id'])
    if digest(attempt)!=lesson['attempt_sha256']:raise ValueError('terminal_attempt_changed')
    account=read_json(root/'research_methods/episode_accounts'/(lesson['episode_id']+'.json'))
    if account.get('inflight') or any(account['usage'][k]<v for k,v in lesson['retained_usage'].items()):
        raise ValueError('terminal_costs_or_settlement_changed')
    if lesson.get('use_outcome_id'):
        from .recursive_use import verify
        verify(root,records.read(root,'recursive_use_outcomes',lesson['use_outcome_id']))


def question_schema(foci: list[str]) -> dict:
    from .planner_authoring import _object,_enum
    text=lambda n:{'type':'string','minLength':16,'maxLength':n}
    return _object({'focus':_enum(foci),'objective':text(160),'hypothesis':text(200),'changed_approach':text(200),
        'observable':_enum(['effective_operation','state_errors']),'expected_relation':_enum(['same','different']),
        'falsifier':text(160),'cases':{'type':'array','minItems':2,'maxItems':2,
            'items':growth.schema()['properties']['practice_cases']['items']}})


def measure_question(proposal: dict, lesson: dict, foci: list[str], *, contract: str='legacy_v1', definitions: dict | None=None) -> dict:
    from .recursive_contract import validate
    from . import recursive_questions as executable,recursive_expansion as expansion
    if contract==executable.VERSION:executable.validate(proposal,foci,list(definitions or executable.BASE))
    else:validate(proposal,question_schema(foci))
    a,b=proposal['cases']
    if a['fields']!=b['fields']:raise ValueError('paired_probe_requires_identical_selected_fields')
    all_keys=set(a['record'])|set(b['record'])
    changed=[k for k in all_keys if (k in a['record'])!=(k in b['record']) or a['record'].get(k)!=b['record'].get(k)]
    if len(changed)!=1 or changed[0] not in a['fields']:raise ValueError('change_exactly_one_selected_key_presence')
    key=changed[0]
    if (key in a['record'])==(key in b['record']):raise ValueError('presence_toggle_required_not_value_renaming')
    present=a['record'] if key in a['record'] else b['record']
    if present[key] is not None:raise ValueError('contrast_absence_with_explicit_null')
    outputs=[evaluator.execute(lesson['proposal']['strategy'],c) for c in (a,b)]
    errors=[evaluator.oracle(c,o) for c,o in zip((a,b),outputs)]
    if not any(errors):raise ValueError('diagnostic_must_exercise_reviewed_failure')
    measured=[expansion.measure(proposal['observable'],c,o) for c,o in zip((a,b),outputs)]
    observed='same' if measured[0]==measured[1] else 'different'
    result={'input_sha256':digest(proposal['cases']),'observed':measured,'observed_relation':observed,
        'hypothesis_status':'supported_on_public_probe' if observed==proposal['expected_relation'] else 'refuted_on_public_probe',
        'scope':'question_diagnostic_only','method_acceptance_credit':False,'changed_field':key}
    if contract==executable.VERSION:
        result['executable_claim']=executable.binding(proposal,lesson['proposal']['strategy'],definitions or executable.BASE)
        result['falsifier_triggered']=observed==proposal['falsifier']
    return result


def context(root: Path, episode: dict, task: dict) -> dict:
    lesson=records.read(root,'recursive_terminal_lessons',episode['terminal_lesson_id'])
    from . import recursive_questions as executable,recursive_expansion as expansion,recursive_review_queue as queue
    version=queue.question_contract(root,episode)
    result={'bundle_visible':{'task':'Formulate a narrower learning question from the reviewed failure.',
        'available_focus':episode['available_focus'],'previous_method':lesson['proposal']['strategy'],
        'retained_case_coverage':lesson['protected_states'],'diagnostic':checks.diagnostic(lesson['proposal']['strategy']),
        'control_semantics':causal.SEMANTICS,'prior_question':task.get('last_question'),
        'feedback':task.get('feedback',{}),'remaining_calls':2-task['model_calls'],
        'experiment_contract':'Two cases: same selected fields and values except one selected key changes between absent and explicit null. Exercise the failure. Predict the named observable; justify a distinct learning objective and method.'},
        'bundle_schema':question_schema(episode['available_focus']),
        'bundle_instructions':'Author your own question, paired diagnostic, hypothesis and falsifier. The exhausted investigation stays closed. A schema-valid question is not approval or method improvement. Independent review is required.',
        'provider_time_budget_seconds':110}
    if lesson.get('use_outcome_id'):
        from .recursive_use import verify,compact_trace
        result['bundle_visible']['diagnostic']=compact_trace(verify(root,records.read(root,'recursive_use_outcomes',lesson['use_outcome_id'])))
    if version==executable.VERSION:
        definitions=expansion.definitions(root)
        result['bundle_schema']={'anyOf':[executable.schema(episode['available_focus'],list(definitions)),expansion.request_schema()]}
        result['bundle_visible'].update(measurements=definitions,requestable_measurements=expansion.CATALOG,
            experiment_contract='Retained method is fixed. Toggle one selected key absent/null; hold everything else fixed. Predict equality or inequality of the named measurement. Falsifier must be the opposite relation. Objective explains relevance, not unexecuted controls.')
        result['bundle_instructions']='Author a bounded question or request a missing measurement. Measurement definitions are exact. Do not claim universal or causal conclusions from two inputs. Questions and capability requests need independent review; requests grant no execution authority.'
    return result


def admit(root: Path, *, stamp: float, shared: dict, configured: dict, acceptance_seed: int | None=None) -> dict | None:
    if acceptance_seed is not None and (type(acceptance_seed) is not int or not 0<=acceptance_seed<2**31):raise ValueError('bounded_seed_required')
    control=policy(root)
    if not control.get('enabled'):return None
    previous=growth.rows(root,'learning_episodes')
    # Approved questions have priority over starting additional question authoring.
    for review in growth.rows(root,'recursive_question_reviews'):
        if review['decision']!='approve' or review['implementation']!=records.implementation():continue
        if any(e.get('question_review_id')==review['id'] for e in previous):continue
        question=records.read(root,'recursive_questions',review['question_id'])
        from .recursive_expansion import definitions
        if question.get('contract')=='executable_question_v2' and question['proposal']['observable'] not in definitions(root):continue
        lesson=records.read(root,'recursive_terminal_lessons',question['terminal_lesson_id']);validate_lesson(root,lesson)
        parent=records.read(root,'learning_episodes',lesson['episode_id'])
        body={'family':'recursive_practice','failure_id':parent['failure_id'],'failure_key':digest(['approved_recursive_question',review['id']]),
            'source_id':lesson['source_id'],'stage':parent['stage'],'baseline':growth.active(root),'seed':secrets.randbits(31) if acceptance_seed is None else acceptance_seed,
            'evaluator_sha256':evaluator.fingerprint(),'recursive_policy_id':configured['id'],'practice_contract':checks.VERSION,
            'correction_format':'causal_v3','parent_episode_id':parent['id'],'root_episode_id':lesson['root_episode_id'],
            'followup_depth':recovery.MAX_FOLLOWUPS,'prior_attempt_id':lesson['attempt_id'],'failure_review_id':lesson['review_id'],
            'question_id':question['id'],'question_review_id':review['id'],'input_sha256':digest(question),
            **({'use_outcome_id':lesson['use_outcome_id']} if lesson.get('use_outcome_id') else {})}
        task={'state':'ready','model_calls':0,'attempt_ids':[],'failure_id':parent['failure_id'],
            'last_proposal':lesson['proposal'],'protected_discovery_states':lesson['protected_states'],
            'feedback':checks.feedback(lesson['proposal'],lesson['report'],checks.assess(lesson['proposal'],lesson['report'],parent['stage']))}
        if body.get('use_outcome_id'):
            from .recursive_use import add_findings
            task['feedback']['practice_checks']=add_findings(root,body,lesson['proposal'],task['feedback']['practice_checks'])
        return save_episode(root,body,task,stamp,shared,control)
    for lesson in growth.rows(root,'recursive_terminal_lessons'):
        from .recursive_review_queue import lesson_current
        if not lesson_current(root,lesson):continue
        validate_lesson(root,lesson)
        rooted=[e for e in previous if e.get('family')=='recursive_question' and e.get('root_episode_id')==lesson['root_episode_id']]
        if len(rooted)>=control['max_questions_per_root']:continue
        same_lesson=[e for e in rooted if e.get('terminal_lesson_id')==lesson['id']]
        capability_review=None
        if same_lesson:
            from .recursive_expansion import definitions
            for e in same_lesson:
                t=read_json(root/'research_methods/episode_tasks'/(e['id']+'.json'))
                if not t.get('expansion_review_id'):continue
                er=records.read(root,'recursive_expansion_reviews',t['expansion_review_id'])
                request=records.read(root,'recursive_expansion_requests',er['request_id'])
                if er['decision']=='approve' and er['implementation']==records.implementation() and request['proposal']['primitive'] in definitions(root) and not any(x.get('capability_review_id')==er['id'] for x in rooted):
                    capability_review=er['id'];break
            if not capability_review:continue
        used={q['proposal']['focus'] for q in growth.rows(root,'recursive_questions') if q['root_episode_id']==lesson['root_episode_id']}
        foci=[f for f in lesson['available_focus'] if f not in used]
        if not foci:continue
        parent=records.read(root,'learning_episodes',lesson['episode_id'])
        body={'family':'recursive_question','failure_id':parent['failure_id'],'failure_key':digest(['recursive_question',lesson['id']]),
            'root_episode_id':lesson['root_episode_id'],'parent_episode_id':parent['id'],'terminal_lesson_id':lesson['id'],
            'available_focus':foci,'input_sha256':digest(lesson),'question_contract':control.get('question_contract','executable_question_v2'),
            **({'capability_review_id':capability_review} if capability_review else {})}
        task={'state':'ready','model_calls':0,'attempt_ids':[],'failure_id':parent['failure_id'],'feedback':{}}
        return save_episode(root,body,task,stamp,shared,control)
    return None


def save_episode(root: Path, body: dict, task: dict, stamp: float, shared: dict, control: dict) -> dict:
    # Recheck cadence even when this function is used outside the scheduler.
    _,earliest=learning.admission_window(root,shared,now=stamp)
    if stamp<earliest:raise ValueError('recursive_loop_shared_window_required')
    body.update(implementation=records.implementation(),policy_id=shared['id'],loop_policy_id=control['id'],admitted_at=stamp,
        reserved={k:shared['limits']['episode_'+k] for k in ('model_calls','tool_calls','compute_seconds')},
        validation_reserved_before_provider=True,scientific_allowance_added=0)
    prepared=context(root,body,task) if body['family']=='recursive_question' else growth.context(root,body,task)
    growth.reserve_context(prepared,first=True)
    episode=records.store(root,'learning_episodes',body);task['learning_episode_id']=episode['id']
    write_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'),task)
    return task


def advance(root: Path, task: dict, *, planner) -> dict:
    from . import practice_transaction as transaction
    eid=task['learning_episode_id'];tp=root/'research_methods/episode_tasks'/(eid+'.json');ap=root/'research_methods/episode_accounts'/(eid+'.json')
    transaction.recover(root,tp,ap);task=read_json(tp);episode=records.read(root,'learning_episodes',eid)
    if task['state']!='ready' or episode['family']!='recursive_question':raise ValueError('ready_recursive_question_required')
    if task['failure_id']!=episode['failure_id']:raise ValueError('owned_question_task_required')
    retained=read_json(ap)
    if retained.get('inflight'):
        retained['usage']['compute_seconds']+=retained['inflight']['reserved_seconds'];retained['inflight']=None
        task.update(state='exhausted_requires_review',model_calls=retained['usage']['model_calls'],feedback={'reason':'uncertain_question_dispatch_retained'})
        receipt=records.store(root,'episode_interruptions',{'episode_id':eid,'usage':copy.deepcopy(retained['usage']),'allowance_added':0})
        transaction.commit(root,tp,ap,task,retained,receipt,kind='episode_interruptions');return task
    limits,account,_,_=learning.practice_budget(root,task)
    write_json(ap,account)
    autonomy=read_json(root/'autonomy/status.json');control=policy(root)
    if not control.get('enabled') or control['id']!=episode['loop_policy_id'] or not autonomy.get('active') or autonomy.get('emergency_stop'):
        raise ValueError('recursive_question_controls_changed')
    remaining=limits['max_compute_seconds']-account['usage']['compute_seconds']
    if task['model_calls']>=2 or remaining<30 or account['usage']['tool_calls']+6>limits['max_tool_calls']:
        task['state']='exhausted_requires_review';write_json(tp,task);return task
    prepared=context(root,episode,task);prepared['provider_time_budget_seconds']=min(110,remaining-30)
    started=time.monotonic();dispatched=False;response=None;report=None;old_hook=getattr(planner,'dispatch_hook',None)
    def dispatch():
        nonlocal dispatched
        if dispatched:return
        dispatched=True;account['usage']['model_calls']+=1
        account['inflight']={'phase':'dispatched','reserved_seconds':min(140,remaining)};write_json(ap,account)
    try:
        growth.reserve_context(prepared,first=not task['model_calls'])
        if callable(getattr(planner,'preflight',None)):
            payload=planner.preflight('child_bundle',prepared)
            if payload['options']['num_predict']>1000:raise ValueError('question_output_reservation_limit')
        planner.dispatch_hook=dispatch
        if not getattr(planner,'supports_dispatch_hook',False):dispatch()
        response=planner('child_bundle',prepared);dispatch();account['usage']['tool_calls']+=6
        task['last_question']=copy.deepcopy(response)
        lesson=records.read(root,'recursive_terminal_lessons',episode['terminal_lesson_id']);validate_lesson(root,lesson)
        from . import recursive_questions as executable,recursive_expansion as expansion,recursive_review_queue as queue
        version=queue.question_contract(root,episode)
        if version==executable.VERSION and isinstance(response,dict) and response.get('intent')=='request_capability':
            request=expansion.submit(root,episode,response)
            task.update(state='awaiting_recursive_expansion_review',expansion_request_id=request['id'],feedback={'independent_expansion_review_required':True})
        else:
            definitions=expansion.definitions(root)
            report=measure_question(response,lesson,episode['available_focus'],contract=version,definitions=definitions)
            question=records.store(root,'recursive_questions',{'episode_id':eid,'terminal_lesson_id':lesson['id'],
                'root_episode_id':lesson['root_episode_id'],'proposal':response,'diagnostic':report,'authored_by':'Novali',
                'contract':version,'measurement_definitions':definitions,'acceptance':'independent_semantic_review_required'})
            task.update(state='awaiting_recursive_question_review',question_id=question['id'],feedback={'diagnostic':report})
    except Exception as exc:
        task.update(state='ready' if dispatched and account['usage']['model_calls']<2 else 'exhausted_requires_review',
                    feedback={'reason':str(exc)[:500],'costs_retained':True})
    finally:
        planner.dispatch_hook=old_hook;account['usage']['compute_seconds']=round(account['usage']['compute_seconds']+time.monotonic()-started,4)
        account['inflight']=None;task['model_calls']=account['usage']['model_calls']
        receipt=records.store(root,'attempts',{'learning_episode_id':eid,'failure_id':episode['failure_id'],'response':response,
            'submitted_response':response,'report':report,'feedback':task['feedback'],'provider_dispatched':dispatched,
            'provider_metadata':getattr(planner,'last_metadata',{}),'usage_after':copy.deepcopy(account['usage'])})
        task['attempt_ids'].append(receipt['id']);transaction.commit(root,tp,ap,task,account,receipt,kind='attempts')
    return task


def review_question(root: Path, question_id: str, *, decision: str, reviewer: str, evidence_reference: str, findings: list[str] | None=None) -> dict:
    if decision not in ('approve','reject','revise') or min(len(reviewer),len(evidence_reference))<16:raise ValueError('independent_question_review_required')
    question=records.read(root,'recursive_questions',question_id);episode=records.read(root,'learning_episodes',question['episode_id'])
    tp=root/'research_methods/episode_tasks'/(episode['id']+'.json');task=read_json(tp)
    old=next((r for r in growth.rows(root,'recursive_question_reviews') if r['question_id']==question_id),None)
    if old:
        if old['decision']!=decision:raise ValueError('immutable_question_review_decision')
        if task.get('applied_question_review_id')==old['id']:return old
        result=old
    else:
        if task.get('question_id')!=question_id or task['state']!='awaiting_recursive_question_review':raise ValueError('owned_pending_question_required')
        if not any(records.read(root,'attempts',a)['response']==question['proposal'] for a in task['attempt_ids']):raise ValueError('novali_authored_question_required')
        if decision=='revise' and (task['model_calls']>=2 or not findings or len(findings)>4 or any(not isinstance(f,str) or not 8<=len(f)<=240 for f in findings)):
            raise ValueError('remaining_call_and_precise_findings_required')
        lesson=records.read(root,'recursive_terminal_lessons',question['terminal_lesson_id']);validate_lesson(root,lesson)
        from .lesson_review_budget import charge
        with charge(root,episode):
            from .recursive_expansion import definitions
            if question.get('contract')=='executable_question_v2' and question['proposal']['observable'] not in definitions(root):raise ValueError('question_adapter_no_longer_available')
            measured=measure_question(question['proposal'],lesson,episode['available_focus'],contract=question.get('contract','legacy_v1'),definitions=question.get('measurement_definitions'))
            if measured!=question['diagnostic']:raise ValueError('question_measurement_changed')
            if decision=='approve' and any(q['id']!=question_id and q['root_episode_id']==question['root_episode_id'] and q['proposal']['focus']==question['proposal']['focus']
                and any(r['question_id']==q['id'] and r['decision']=='approve' for r in growth.rows(root,'recursive_question_reviews')) for q in growth.rows(root,'recursive_questions')):
                raise ValueError('renamed_focus_cannot_renew_practice')
            result=records.store(root,'recursive_question_reviews',{'question_id':question_id,'decision':decision,'reviewer':reviewer,
                'evidence_reference':evidence_reference,'findings':findings or [],'implementation':records.implementation(),'allowance_added':0,
                'scope':'distinct_diagnostic_question_not_method_adoption'})
    if task.get('question_id')==question_id:
        task['applied_question_review_id']=result['id']
        if decision=='revise':task.update(state='ready',feedback={'independent_findings':result['findings']},last_question=question['proposal'])
        else:task.update(state='recursive_question_reviewed',question_review_id=result['id'])
        write_json(tp,task)
    return result


def status(root: Path) -> dict:
    control=policy(root);episodes=growth.rows(root,'learning_episodes')
    questions=[e for e in episodes if e['family']=='recursive_question']
    pending=[read_json(root/'research_methods/episode_tasks'/(e['id']+'.json')) for e in questions]
    return {'enabled':control.get('enabled',False),'terminal_lessons':len(growth.rows(root,'recursive_terminal_lessons')),
        'question_episodes':len(questions),'questions':[{'episode_id':t['learning_episode_id'],'state':t['state'],'question_id':t.get('question_id'),
            'remaining_calls':max(0,2-t['model_calls'])} for t in pending],
        'max_questions_per_root':control.get('max_questions_per_root',MAX_QUESTIONS_PER_ROOT),
        'automatic_semantic_review':False,'capability_expansion':'new_adapters_or_authority_require_separate_review',
        'closure':'proposal_and_practice_scheduled;semantic_review_and_verified_downstream_reuse_required'}

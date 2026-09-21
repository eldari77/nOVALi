"""Novali-authored curricula and learning strategies under existing reservations.

Operator review controls promotion. The first adapter covers pure cached-record
work; it cannot grant research calls, edit artifacts, or change the evaluator.
"""
from __future__ import annotations
import copy
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from . import research_procedures as records, learning_episodes as episodes
from . import recursive_evaluator as evaluator
from .research_tools import digest, read_json, write_json

VERSION='recursive_growth_v1'


def rows(root: Path, kind: str) -> list[dict[str, Any]]:
    return [records.read(root,kind,p.stem) for p in sorted((root/'research_methods'/kind).glob('*.json'))]


def configure(root: Path, *, enabled: bool, authority_reference: str, correction_format: str='causal_v3') -> dict[str, Any]:
    if type(enabled) is not bool or not 16<=len(authority_reference)<=1600:
        raise ValueError('explicit_recursive_policy_required')
    if correction_format not in ('typed_v2','causal_v3'):raise ValueError('known_correction_format_required')
    result=records.store(root,'recursive_policies',{'enabled':enabled,'authority_reference':authority_reference,'correction_format':correction_format,
        'contract':VERSION,'adapter':evaluator.VERSION,'max_stage':2,'max_attempts':2,
        'acceptance':'independent_review_and_withheld_transfer','allowance_added':0})
    write_json(root/'research_methods/recursive_policy_latest.json',{'policy_id':result['id']})
    return result


def policy(root: Path) -> dict[str, Any]:
    pointer=read_json(root/'research_methods/recursive_policy_latest.json')
    return records.read(root,'recursive_policies',pointer['policy_id']) if pointer else {}


def review_source(root: Path, attempt_id: str, *, reviewer: str, evidence_reference: str) -> dict[str, Any]:
    """Review an owned instrument failure; do not provide a proposed solution."""
    if min(len(reviewer),len(evidence_reference))<16:raise ValueError('independent_failure_review_required')
    attempt=records.read(root,'attempts',attempt_id)
    existing=next((r for r in rows(root,'recursive_sources') if r['attempt_id']==attempt_id),None)
    if existing:
        if existing['attempt_sha256']!=digest(attempt):raise ValueError('reviewed_recursive_source_changed')
        return existing  # Reworded reviews do not create a new admission identity.
    episode=records.read(root,'learning_episodes',attempt['learning_episode_id'])
    task=read_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'))
    if attempt_id not in task['attempt_ids'] or not attempt.get('provider_dispatched'):
        raise ValueError('owned_dispatched_attempt_required')
    response=attempt.get('response') or {}
    source=next((s for s in episode.get('frozen_question_choices',[]) if s['id']==response.get('source_id')),None)
    if not source:raise ValueError('supported_frozen_instrument_source_required')
    from .question_measurements import observe
    replay=observe(source,response)
    if replay.get('status')!='measured':raise ValueError('independent_failure_measurement_required')
    # A failed scientific prediction alone is not a source-state repair task.
    failures=replay['runs']['changed']['counterexamples']
    if not failures:raise ValueError('observed_state_preservation_failure_required')
    return records.store(root,'recursive_sources',{'attempt_id':attempt_id,'episode_id':episode['id'],
        'attempt_sha256':digest(attempt),'source_sha256':digest(source),'measurement_sha256':digest(replay),
        'finding':{'code':'source_state_preservation_required','counterexamples':failures[:2]},
        'reviewer':reviewer,'evidence_reference':evidence_reference,'reviewed_at':time.time(),
        'scope':'teach_cached_projection_contract_not_domain_solution','allowance_added':0})


def active(root: Path) -> dict[str, Any]:
    pointer=read_json(root/'research_methods/recursive_strategy_latest.json')
    if not pointer:return {'strategy':copy.deepcopy(evaluator.BASELINE),'version_id':None,'generation':0}
    version=records.read(root,'recursive_versions',pointer['version_id'])
    if version['evaluator_sha256']!=evaluator.fingerprint():
        raise ValueError('recursive_strategy_requires_evaluator_revalidation')
    return {**version,'version_id':version['id']}


def schema() -> dict[str, Any]:
    from .planner_authoring import _object, _enum
    text=lambda n:{'type':'string','minLength':12,'maxLength':n}
    case=_object({'record':{'type':'object','maxProperties':4,'additionalProperties':{
        'anyOf':[{'type':'null'},{'type':'boolean'},{'type':'number'},{'type':'string','maxLength':32}]}},
        'fields':{'type':'array','minItems':1,'maxItems':4,'uniqueItems':True,
                  'items':{'type':'string','minLength':1,'maxLength':32}}})
    return _object({'objective':text(160),'weakness':_enum(list(evaluator.WEAKNESSES)),
        'relevance':text(240),'strategy':evaluator.strategy_schema(),
        'practice_cases':{'type':'array','minItems':1,'maxItems':2,'items':case},
        'prediction':_object({'quantity':_enum(['context_bytes','successes','batches']),
                              'direction':_enum(['decrease','increase','unchanged'])}),
        'falsifier':text(160)})


def check(proposal: Any) -> None:
    from operator_shell import recursive_contract as jsonschema
    jsonschema.validate(proposal,schema())
    for case in proposal['practice_cases']:
        if any(len(k)>32 for k in case['record']):raise ValueError('bounded_discovery_field_name_required')
        evaluator.execute(evaluator.BASELINE,case)
    if len(json.dumps(proposal,allow_nan=False).encode())>2500:raise ValueError('bounded_curriculum_proposal_required')


def progress(root: Path, source_id: str) -> int:
    approved=[r for r in rows(root,'recursive_reviews') if r['source_id']==source_id and r['decision']=='approve'
              and r['evaluator_sha256']==evaluator.fingerprint()]
    return min(2,1+max((r['stage'] for r in approved),default=-1))


def admit(root: Path, *, now: float | None = None) -> dict[str, Any] | None:
    configured=policy(root);shared=episodes.policy(root) or {};autonomy=read_json(root/'autonomy/status.json')
    if not configured.get('enabled') or not shared.get('enabled') or not autonomy.get('active') or autonomy.get('emergency_stop'):return None
    stamp,earliest=episodes.admission_window(root,shared,now=now)
    if stamp<earliest:return None
    baseline=active(root)
    previous=rows(root,'learning_episodes')
    from . import recursive_failure_review as recovery, recursive_practice_checks as checks
    followup=recovery.admit(root,previous,baseline,stamp,shared,configured)
    if followup:return followup
    from .recursive_loop import admit as admit_loop
    successor=admit_loop(root,stamp=stamp,shared=shared,configured=configured)
    if successor:return successor
    for source in sorted(rows(root,'recursive_sources'),key=lambda r:r['reviewed_at'],reverse=True):
        attempt=records.read(root,'attempts',source['attempt_id'])
        if digest(attempt)!=source['attempt_sha256']:raise ValueError('reviewed_recursive_source_changed')
        stage=progress(root,source['id'])
        key=digest([source['id'],stage,baseline['version_id'],evaluator.fingerprint()])
        if any(e['failure_key']==key for e in previous):continue
        provisional={'source_id':source['id'],'stage':stage,'baseline':baseline,
                     'reserved':{'model_calls':shared['limits']['episode_model_calls']}}
        prepared=context(root,provisional,{'model_calls':0,'feedback':{}})
        reserve_context(prepared,first=True)  # No admission or charge until both envelopes fit.
        failure=records.store(root,'failures',{'failure_family':'recursive_practice','parent_id':source['id'],
            'parent_contract_sha256':digest(source),'failure':source['finding']['code'],'failed_command':{}})
        episode=records.store(root,'learning_episodes',{'family':'recursive_practice','failure_id':failure['id'],
            'failure_key':key,'input_sha256':digest(source),'source_id':source['id'],'stage':stage,
            'recursive_policy_id':configured['id'],'policy_id':shared['id'],'implementation':records.implementation(),
            'baseline':baseline,'seed':secrets.randbits(31),'evaluator_sha256':evaluator.fingerprint(),
            'admitted_at':stamp,'reserved':{k:shared['limits']['episode_'+k] for k in ('model_calls','tool_calls','compute_seconds')},
            'validation_reserved_before_provider':True,'scientific_allowance_added':0,'practice_contract':checks.VERSION,'correction_format':configured.get('correction_format','causal_v3')})
        task={'learning_episode_id':episode['id'],'failure_id':failure['id'],'state':'ready','model_calls':0,
              'attempt_ids':[],'feedback':{},'grants_execution_authority':False}
        write_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'),task)
        return task
    return None


def context(root: Path, episode: dict, task: dict, *, memory: bool = True, correction_interface: str = 'focused') -> dict:
    source=records.read(root,'recursive_sources',episode['source_id'])
    lessons=[]
    if memory:
        lessons=methods(root)
    original=records.read(root,'attempts',source['attempt_id'])
    parent=records.read(root,'learning_episodes',source['episode_id'])
    frozen=next(s for s in parent['frozen_question_choices'] if s['id']==original['response']['source_id'])
    from .question_measurements import inputs
    data,fields=inputs(frozen)
    case={'record':data,'fields':fields}
    projection=evaluator.execute(episode['baseline']['strategy'],case)
    if evaluator.oracle(case,projection):raise ValueError('adopted_learning_strategy_regressed_current_input')
    learning_input={'fields':fields,'evidence':projection['evidence']}
    if len(json.dumps(learning_input).encode())>900:
        learning_input={'status':'full_example_exceeds_context_limit','source_sha256':digest(case)}
    visible={'task':'Propose a falsifiable practice question and an executable learning strategy.',
        'stage':episode['stage'],'requirements':['preserve exact absent/null/false/zero/unknown states',
            'complete every selected field','avoid regressions on changed inputs'],
        'stage_acceptance':('transfer without regressions' if episode['stage']<2 else 'transfer and strictly better correctness or fewer context bytes than frozen baseline'),
        'observed_failure':source['finding'],'baseline':episode['baseline']['strategy'],
        'learning_input':learning_input,
        'learning_input_effect':{'version_id':episode['baseline']['version_id'],'input_sha256':digest(case),
            'state_preservation_verified':True,'context_bytes':projection['context_bytes'],
            'batches':projection['batches'],'consumed_in_authoring_context':True},
        'control_semantics':{'batch_size':'partition selected fields into batches','projection':'whole_input retains all input; selected_slots retains every selected state; present_slots omits absent fields',
            'ordering':'order fields before batching','stopping':'all_batches completes work; first_batch stops after one batch',
            'rules':'first matching count threshold overrides projection; no rule uses a case ID'},
        'remaining_calls':episode['reserved']['model_calls']-task['model_calls'],'lessons':[{k:m[k] for k in ('id','strategy','unresolved_findings') if k in m} for m in lessons[-1:]],
        'previous_proposal':task.get('last_proposal'),'feedback':task.get('feedback',{}),
        'original_prediction':task.get('original_prediction')}
    visible['feedback']=copy.deepcopy(visible['feedback'])
    if 'changes' in visible['feedback']:
        visible['feedback']['changes']=[{'path':c['path'],'before_sha256':digest(c['before']),'after_sha256':digest(c['after'])} for c in visible['feedback']['changes']]
    if correction_interface not in ('focused','typed','path','full_proposal'):raise ValueError('known_correction_interface_required')
    response_schema=schema();correction_bindings=None
    from . import recursive_practice_checks as checks
    quality=task.get('feedback',{}).get('practice_checks')
    if correction_interface in ('focused','typed','path') and episode.get('practice_contract')==checks.VERSION and task.get('last_proposal') and quality and checks.paths(quality):
        visible['correction_contract']={'editable_paths':checks.paths(quality),
            'preserve_other_fields':True,'substantive_effective_change_required':True}
        response_schema=checks.correction_schema(schema(),task['last_proposal'],checks.paths(quality))
    if task.get('last_rejected_patch'):
        from .recursive_corrections import compact_packet
        visible['last_rejected_patch']=compact_packet(task['last_rejected_patch'])
    visible['protected_discovery_states']=task.get('protected_discovery_states',[])
    if (correction_interface in ('focused','typed') and episode.get('correction_format') in ('typed_v2','causal_v3')
            and visible.get('correction_contract') and not task.get('revision_review_id')):
        from .recursive_corrections import offered,describe
        fields,response_schema=offered(schema(),task['last_proposal'],checks.paths(quality))
        if episode.get('correction_format')=='causal_v3' and correction_interface=='focused':
            from . import recursive_causal as causal
            fields,response_schema,binding=causal.offered(schema(),task['last_proposal'],checks.paths(quality),diagnostic=quality['diagnostic'])
            visible['causal_binding']=binding;visible['control_semantics']=causal.SEMANTICS
            if binding['matched_rule'] is not None:
                visible['control_semantics']={k:v for k,v in causal.SEMANTICS.items() if k!='batch' or 'stop' in fields}
        correction_bindings=fields
        visible['typed_correction_contract']={'fields':{k:{**describe(v['value_contract']),
            **({'const':v['value_contract']['const']} if 'const' in v['value_contract'] else {})} for k,v in fields.items()},'max_edits':6,'omit_unchanged_supporting_fields':True}
        visible.pop('correction_contract',None)
    if episode.get('failure_review_id'):
        review=records.read(root,'recursive_failure_reviews',episode['failure_review_id'])
        visible['followup_contract']={'parent_attempt':review['attempt_id'],
            'original_prediction':review['original_prediction'], 'retained_hypothesis_status':'refuted' if quality and task['feedback'].get('hypothesis_status')=='refuted' else 'see_original_report',
            'changed_strategy_required':True,'remaining_lineage_followups':review['max_followups']-review['followup_depth']}
    if task.get('revision_review_id'):
        revision=records.read(root,'recursive_revision_reviews',task['revision_review_id'])
        visible['revision_contract']={'editable_fields':[f['path'] for f in revision['findings']],
                                      'keep_all_other_fields_unchanged':True,'original_prediction':revision['original_prediction']}
        from .planner_authoring import _object
        response_schema=_object({'corrections':_object({f['path'].lstrip('/'):schema()['properties'][f['path'].lstrip('/')]
                                                       for f in revision['findings']})})
    if correction_interface=='full_proposal':
        visible['feedback']={k:v for k,v in visible['feedback'].items() if k not in ('practice_checks','changes')}
        visible['feedback']['unresolved']='Preserve selected source states; independently review relevance and falsifier.'
    if visible.get('typed_correction_contract'):
        # Source history stays in immutable receipts; these are the current actionable bindings.
        visible={k:visible[k] for k in ('task','stage','requirements','stage_acceptance','previous_proposal',
            'learning_input_effect','typed_correction_contract','protected_discovery_states','remaining_calls',
            'original_prediction','last_rejected_patch','followup_contract','causal_binding',
            *(['control_semantics'] if visible.get('causal_binding') else [])) if k in visible}
        visible['feedback']={'hypothesis_status':task['feedback'].get('hypothesis_status'),
            'diagnostic':quality['diagnostic'],'findings':quality['findings'],
            'transfer':{k:task['feedback'].get('transfer',{}).get(k) for k in ('cases','candidate_successes','baseline_successes','candidate_context_bytes','baseline_context_bytes')}}
        if task['feedback'].get('repair_comparison'):visible['feedback']['repair_comparison']=task['feedback']['repair_comparison']
        if task['feedback'].get('question_probe'):visible['feedback']['question_probe']=task['feedback']['question_probe']
        if visible.get('causal_binding'):
            visible['task']='Repair the diagnosed operation.'
            # These immutable fields are bound in the dispatch receipt and are not editable here.
            visible['previous_proposal']={k:v for k,v in visible['previous_proposal'].items() if k not in ('objective','weakness')}
    if episode.get('question_id'):
        question=records.read(root,'recursive_questions',episode['question_id'])
        from .recursive_questions import brief
        visible['accepted_practice_question']=brief(question['proposal'])
    if episode.get('use_outcome_id') and visible.get('feedback',{}).get('diagnostic'):
        from .recursive_use import compact_trace
        visible['feedback']['diagnostic']=compact_trace(visible['feedback']['diagnostic'])
    return {'bundle_visible':visible,'bundle_schema':response_schema,'correction_bindings':correction_bindings,
        'bundle_instructions':'Author and justify your own repair; predict the named metric and falsifier. Preserve valid fields and observed states. Diagnostics grant no acceptance. Typed contract: return edits with field handle and typed value; obey bounds, omit unchanged fields. Path contract: corrections keyed by exact offered paths. Revision contract: corrections keyed by offered names. Repair, refutation and improvement need separate review; bytes do not prove research success or speed.'}


def reserve_context(prepared: dict, *, first: bool) -> dict:
    from .child_planning import reserve
    visible=copy.deepcopy(prepared['bundle_visible'])
    if first:
        retained=len(json.dumps({'previous_proposal':visible.get('previous_proposal'),'feedback':visible.get('feedback',{}),'last_rejected_patch':visible.get('last_rejected_patch')},separators=(',',':')).encode())
        visible['retry_reserve']='x'*max(0,4000-retained)
    return reserve(prepared['bundle_instructions'],visible,1000)


def advance(root: Path, task: dict, *, planner, correction_interface: str = 'focused') -> dict:
    from . import practice_transaction as transaction
    task_path=root/'research_methods/episode_tasks'/(task['learning_episode_id']+'.json')
    account_path=root/'research_methods/episode_accounts'/task_path.name
    transaction.recover(root,task_path,account_path);task=read_json(task_path)
    if task['state']!='ready':raise ValueError('ready_recursive_task_required')
    retained=read_json(account_path)
    if retained.get('inflight'):
        # Dispatch increments the account before the task projection. Settle the
        # uncertain reservation before practice_budget checks their agreement.
        episode=records.read(root,'learning_episodes',task['learning_episode_id'])
        if episode['failure_id']!=task['failure_id']:raise ValueError('owned_recursive_interruption_required')
        retained['usage']['compute_seconds']+=retained['inflight']['reserved_seconds']
        retained['inflight']=None
        task.update(state='exhausted_requires_review',model_calls=retained['usage']['model_calls'],
                    feedback={'reason':'uncertain_dispatch_retained','costs_retained':True})
        receipt=records.store(root,'episode_interruptions',{'episode_id':episode['id'],
            'usage':copy.deepcopy(retained['usage']),'reason':'uncertain_recursive_dispatch_retained',
            'allowance_added':0})
        transaction.commit(root,task_path,account_path,task,retained,receipt,kind='episode_interruptions')
        return task
    limits,account,account_path,task_path=episodes.practice_budget(root,task)
    episode=records.read(root,'learning_episodes',task['learning_episode_id'])
    autonomy=read_json(root/'autonomy/status.json')
    if (policy(root).get('id')!=episode['recursive_policy_id'] or not policy(root).get('enabled')
            or not autonomy.get('active') or autonomy.get('emergency_stop') or episode['evaluator_sha256']!=evaluator.fingerprint()):
        raise ValueError('recursive_controls_changed')
    if episode.get('loop_policy_id'):
        from .recursive_loop import policy as loop_policy
        control=loop_policy(root)
        if not control.get('enabled') or control['id']!=episode['loop_policy_id']:raise ValueError('recursive_loop_controls_changed')
    remaining=limits['max_compute_seconds']-account['usage']['compute_seconds']
    if task['model_calls']>=2 or remaining<30 or account['usage']['tool_calls']+8>limits['max_tool_calls']:
        task['state']='exhausted_requires_review';write_json(task_path,task);return task
    prepared=context(root,episode,task,correction_interface=correction_interface);prepared['provider_time_budget_seconds']=min(110,remaining-30)
    from . import recursive_corrections as corrections, recursive_rejections as rejections
    validation_envelope=rejections.freeze(prepared,task.get('last_proposal'))
    started=time.monotonic();dispatched=False;response=None;submitted=None;report=None
    rejection_packet=None;validation_request_id=None
    write_json(account_path,account)
    old_hook=getattr(planner,'dispatch_hook',None)
    def dispatch():
        nonlocal dispatched,validation_request_id
        if dispatched:return
        request=records.store(root,'recursive_validation_requests',{'episode_id':episode['id'],'call':account['usage']['model_calls']+1,
            'envelope':validation_envelope,'visible_context_sha256':digest(prepared['bundle_visible'])})
        validation_request_id=request['id']
        dispatched=True;account['usage']['model_calls']+=1
        account['inflight']={'phase':'dispatched','reserved_seconds':min(140,remaining),'validation_request_id':validation_request_id}
        write_json(account_path,account)
    try:
        # Reserve both the current response and bounded retry feedback before dispatch.
        reserve_context(prepared,first=not task['model_calls'])
        if callable(getattr(planner,'preflight',None)):
            payload=planner.preflight('child_bundle',prepared)
            if payload['options']['num_predict']>1000:raise ValueError('recursive_output_reservation_limit')
        planner.dispatch_hook=dispatch
        if not getattr(planner,'supports_dispatch_hook',False):dispatch()
        submitted=planner('child_bundle',prepared);dispatch();response=submitted
        account['usage']['tool_calls']+=6
        changes=[]
        if prepared['bundle_visible'].get('typed_correction_contract'):
            from . import recursive_causal as causal
            resolver=causal.resolve if prepared['bundle_visible'].get('causal_binding') else corrections.resolve
            response,changes=resolver(submitted,task['last_proposal'],prepared['bundle_schema'],prepared['correction_bindings'])
        if prepared['bundle_visible'].get('correction_contract') and not task.get('revision_review_id'):
            from . import recursive_practice_checks as checks
            response,changes=checks.resolve(submitted,task['last_proposal'],prepared['bundle_schema'])
        if task.get('revision_review_id'):
            from .recursive_contract import validate
            validate(submitted,prepared['bundle_schema'])
            parent=records.read(root,'recursive_candidates',task['revision_parent_candidate_id'])['proposal']
            response={**copy.deepcopy(parent),**copy.deepcopy(submitted['corrections'])}
        check(response)
        if task.get('revision_review_id'):
            revision=records.read(root,'recursive_revision_reviews',task['revision_review_id'])
            prior=records.read(root,'recursive_candidates',revision['candidate_id'])['proposal']
            editable={f['path'].lstrip('/') for f in revision['findings']}
            from .question_quality import cosmetic_only
            unchanged=[key for key in editable if cosmetic_only(prior.get(key),response.get(key))]
            changed_valid=[key for key in prior if key not in editable and response.get(key)!=prior[key]]
            if unchanged or changed_valid:
                raise ValueError('Substantive review repair required; unchanged='+str(unchanged)+'; changed valid fields='+str(changed_valid))
        report=evaluator.evaluate(response,episode['baseline']['strategy'],episode['seed'],episode['stage'])
        from . import recursive_practice_checks as checks
        quality=checks.assess(response,report,episode['stage']) if episode.get('practice_contract')==checks.VERSION else None
        if quality is not None:
            from .recursive_use import add_findings
            quality=add_findings(root,episode,response,quality)
        if quality:
            covered=set(quality['coverage']['covered_states'])
            lost=sorted(set(task.get('protected_discovery_states',[]))-covered)
            if lost:
                quality['practice_eligible']=False
                quality['findings'].append({'path':'/practice_cases','requirement':'Preserve previously demonstrated discovery coverage.','missing':lost})
            task['protected_discovery_states']=sorted(set(task.get('protected_discovery_states',[]))|covered)
        task.setdefault('original_prediction',{'prediction':copy.deepcopy(response['prediction']),'status':report['hypothesis_status']})
        prior_proposal=task.get('last_proposal')
        task['last_proposal']=response
        if quality:
            task['feedback']=checks.feedback(response,report,quality)
            task['feedback']['changes']=changes
            if prior_proposal and prepared['bundle_visible'].get('causal_binding'):
                task['feedback']['repair_comparison']=causal.comparison(prior_proposal['strategy'],response['strategy'])
        else:
            task['feedback']={'hypothesis_status':report['hypothesis_status'],'transfer':report['transfer'],'regression':report['regression']}
        changed_approach=True
        if episode.get('prior_attempt_id'):
            original=records.read(root,'recursive_failure_reviews',episode['failure_review_id']).get('prior_proposal') or records.read(root,'attempts',episode['prior_attempt_id'])['response']
            changed_approach=checks.behavior_signature(original['strategy'])!=checks.behavior_signature(response['strategy'])
            if episode.get('correction_format')=='causal_v3':
                from .recursive_causal import comparison
                task['feedback']['ancestor_repair_comparison']=comparison(original['strategy'],response['strategy'])
                changed_approach=task['feedback']['ancestor_repair_comparison']['failure_repair_demonstrated']
            task['feedback']['changed_approach']=changed_approach
            task['feedback']['original_prediction']=original['prediction']
        if not changed_approach:
                quality['findings'].append({'path':'/strategy','requirement':'Repair the diagnosed failure while preserving correct behavior; representation changes alone do not establish repair.'})
        question_probe=None
        if episode.get('question_id'):
            question=records.read(root,'recursive_questions',episode['question_id'])
            question_probe=evaluator.assess(response['strategy'],episode['baseline']['strategy'],question['proposal']['cases'])
            task['feedback']['question_probe']={k:question_probe[k] for k in ('cases','candidate_successes','regressions','complete')}
            if not question_probe['complete']:changed_approach=False
        if report['method_review_eligible'] and (quality is None or quality['practice_eligible']) and changed_approach:
            candidate=records.store(root,'recursive_candidates',{'episode_id':episode['id'],'source_id':episode['source_id'],
                'proposal':response,'report':report,'stage':episode['stage'],'authored_by':'Novali',
                'baseline':episode['baseline'],'acceptance':'independent_review_required',
                'revision_review_id':task.get('revision_review_id'),
                'practice_checks':quality,'correction_changes':changes,'prior_attempt_id':episode.get('prior_attempt_id'),'protected_discovery_states':task.get('protected_discovery_states',[]),'question_probe':question_probe})
            task.update(state='awaiting_recursive_review',candidate_id=candidate['id'])
        else:task['state']='ready' if account['usage']['model_calls']<2 else 'exhausted_requires_review'
    except Exception as exc:
        if submitted is not None and validation_envelope['prior']:
            if validation_envelope['wire_format']=='causal_v3':
                from .recursive_causal import rejection
                rejection_packet=rejection(validation_envelope['prior'],submitted,prepared['bundle_schema'],prepared['correction_bindings'],protected_states=task.get('protected_discovery_states',[]))
            else:
                rejection_packet=corrections.packet(validation_envelope['prior'],submitted,prepared['bundle_schema'],
                    typed=validation_envelope['wire_format']=='typed_v2',stage=episode['stage'],protected_states=task.get('protected_discovery_states',[]))
            task['last_rejected_patch']=rejection_packet
            task['protected_discovery_states']=sorted(set(task.get('protected_discovery_states',[]))|set(rejection_packet['observed_discovery_states']))
        validation_envelope['rejection']=str(exc)[:600]
        # Preparation does not consume a call or spin automatically; uncertain dispatch does.
        task.update(state=('ready' if dispatched and account['usage']['model_calls']<2 else 'exhausted_requires_review'),
            feedback={**task.get('feedback',{}),'reason':str(exc)[:600],
                      'provider_dispatched':dispatched,'costs_retained':True})
        if isinstance(response,dict) and set(response)==set(schema()['properties']):
            try:check(response)
            except (ValueError,TypeError):pass
            else:task['last_proposal']=response
    finally:
        planner.dispatch_hook=old_hook
        account['usage']['compute_seconds']=round(account['usage']['compute_seconds']+time.monotonic()-started,4)
        account['inflight']=None;task['model_calls']=account['usage']['model_calls']
        receipt=records.store(root,'attempts',{'learning_episode_id':episode['id'],'failure_id':episode['failure_id'],
            'response':response,'submitted_response':submitted,'feedback':task['feedback'],'report':report,'provider_dispatched':dispatched,
            'provider_metadata':getattr(planner,'last_metadata',{}),'usage_after':copy.deepcopy(account['usage']),
            'learning_input_effect':prepared['bundle_visible']['learning_input_effect'],
            'practice_contract':episode.get('practice_contract'),'correction_interface':correction_interface,'validation_envelope':validation_envelope,
            'rejection_packet':rejection_packet,'validation_request_id':validation_request_id})
        task['attempt_ids'].append(receipt['id'])
        transaction.commit(root,task_path,account_path,task,account,receipt,kind='attempts')
    return task


def restart_report(root: Path, candidate: dict, episode: dict) -> dict:
    """Reload the stored Novali program in a new process and execute fresh tasks."""
    command=[sys.executable,'-B','-m','operator_shell.recursive_growth','restart',str(root),candidate['id']]
    result=subprocess.run(command,capture_output=True,text=True,timeout=15,
        env={**os.environ,'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'})
    if result.returncode:raise ValueError('recursive_restart_execution_failed:'+result.stderr[-300:])
    report=json.loads(result.stdout)
    if (report['candidate_sha256']!=digest(candidate) or report['process_id']==os.getpid()
            or report['evaluator_sha256']!=evaluator.fingerprint()):raise ValueError('independent_restart_binding_failed')
    return report


def revision_compatible(root: Path, episode: dict, task: dict) -> bool:
    if episode.get('family')!='recursive_practice' or not task.get('revision_review_id'):return False
    review=records.read(root,'recursive_revision_reviews',task['revision_review_id'])
    candidate=records.read(root,'recursive_candidates',review['candidate_id'])
    return (candidate['episode_id']==episode['id'] and candidate['id']==task.get('revision_parent_candidate_id')
        and review['implementation']==records.implementation() and review['evaluator_sha256']==evaluator.fingerprint()
        and episode['evaluator_sha256']==evaluator.fingerprint())


def review(root: Path, candidate_id: str, *, decision: str, reviewer: str, evidence_reference: str,
           findings: list[dict[str,str]] | None = None) -> dict:
    if decision not in {'approve','reject','revise'} or min(len(reviewer),len(evidence_reference))<16:
        raise ValueError('independent_semantic_review_required')
    old=next((r for r in rows(root,'recursive_reviews') if r['candidate_id']==candidate_id),None)
    if old:
        apply_review(root,old)
        return old
    candidate=records.read(root,'recursive_candidates',candidate_id)
    episode=records.read(root,'learning_episodes',candidate['episode_id'])
    task_path=root/'research_methods/episode_tasks'/(episode['id']+'.json');task=read_json(task_path)
    if task.get('candidate_id')!=candidate_id or candidate['report']['evaluator_sha256']!=evaluator.fingerprint():
        raise ValueError('owned_current_recursive_candidate_required')
    if not any(records.read(root,'attempts',a)['response']==candidate['proposal'] for a in task['attempt_ids']):
        raise ValueError('novali_authored_candidate_required')
    if decision=='revise':
        if (task['state']!='awaiting_recursive_review' or task['model_calls']>=episode['reserved']['model_calls']
                or task.get('revision_review_id') or not isinstance(findings,list) or not 1<=len(findings)<=4
                or any(set(f)!={'path','requirement','counterexample'} or f['path'].lstrip('/') not in schema()['properties']
                       or any(not isinstance(v,str) or not 1<=len(v)<=300 for v in f.values()) for f in findings)):
            raise ValueError('bounded_review_findings_and_original_unused_call_required')
        from .lesson_review_budget import charge
        revised={**task,'state':'ready','last_proposal':candidate['proposal'],
                 'feedback':{'independent_review_findings':findings,'original_hypothesis_status':candidate['report']['hypothesis_status']}}
        prepared=context(root,episode,revised);reserve_context(prepared,first=False)
        with charge(root,episode):
            review=records.store(root,'recursive_revision_reviews',{'candidate_id':candidate_id,
                'implementation':records.implementation(),'evaluator_sha256':evaluator.fingerprint(),
                'findings':findings,'reviewer':reviewer,'evidence_reference':evidence_reference,
                'allowance_added':0,'original_prediction':candidate['proposal']['prediction']})
            revised.update(revision_review_id=review['id'],revision_parent_candidate_id=candidate_id)
            write_json(task_path,revised)
        return review
    from .lesson_review_budget import charge
    with charge(root,episode):
        check(candidate['proposal'])
        replay=evaluator.evaluate(candidate['proposal'],episode['baseline']['strategy'],episode['seed'],episode['stage'])
        if replay!=candidate['report']:raise ValueError('frozen_recursive_report_not_reproduced')
        if episode.get('question_id'):
            question=records.read(root,'recursive_questions',episode['question_id'])
            probe=evaluator.assess(candidate['proposal']['strategy'],episode['baseline']['strategy'],question['proposal']['cases'])
            if probe!=candidate.get('question_probe') or (decision=='approve' and not probe['complete']):raise ValueError('accepted_question_probe_must_pass')
        restarted=restart_report(root,candidate,episode)
        from . import recursive_practice_checks as checks
        quality=checks.assess(candidate['proposal'],replay,episode['stage'])
        if decision=='approve' and set(candidate.get('protected_discovery_states',[]))-set(quality['coverage']['covered_states']):
            raise ValueError('discovery_coverage_regression')
        if decision=='approve' and candidate.get('practice_checks') and candidate['practice_checks']!=quality:
            raise ValueError('current_practice_checks_required')
        if decision=='approve' and (not replay['method_review_eligible'] or not restarted['result']['complete'] or not quality['practice_eligible']):
            raise ValueError('withheld_transfer_regression_and_successful_restart_required')
        if decision=='approve' and episode['stage']==2 and active(root)['version_id']!=episode['baseline']['version_id']:
            raise ValueError('frozen_strategy_baseline_changed')
        review=records.store(root,'recursive_reviews',{'candidate_id':candidate_id,'source_id':episode['source_id'],
            'stage':episode['stage'],'decision':decision,'reviewer':reviewer,'evidence_reference':evidence_reference,
            'evaluator_sha256':evaluator.fingerprint(),'replay':replay,'restart':restarted,
            'reviewed_at':time.time(),'allowance_added':0,'scope':'cached_projection_only'})
        apply_review(root,review)
    return review


def apply_review(root: Path, review: dict) -> None:
    """Idempotently complete interrupted promotion without replaying charges."""
    candidate=records.read(root,'recursive_candidates',review['candidate_id'])
    episode=records.read(root,'learning_episodes',candidate['episode_id'])
    task_path=root/'research_methods/episode_tasks'/(episode['id']+'.json');task=read_json(task_path)
    if task.get('review_id')==review['id']:return
    if task.get('candidate_id')!=candidate['id']:raise ValueError('review_target_changed')
    if review['decision']=='approve' and episode['stage']==2:
        version=records.store(root,'recursive_versions',{'strategy':candidate['proposal']['strategy'],
            'parent_version_id':episode['baseline']['version_id'],'generation':episode['baseline']['generation']+1,
            'review_id':review['id'],'candidate_id':candidate['id'],'evaluator_sha256':review['evaluator_sha256']})
        if active(root)['version_id'] not in (episode['baseline']['version_id'],version['id']):
            raise ValueError('preserve_newer_strategy_version')
        write_json(root/'research_methods/recursive_strategy_latest.json',{'version_id':version['id']})
    task.update(state='recursive_reviewed',review_id=review['id']);write_json(task_path,task)


def retain_procedure(root: Path, candidate_id: str, *, reviewer: str, evidence_reference: str,
                     unresolved_findings: list[str]) -> dict:
    """Retain a verified pure program without approving its failed explanation."""
    if (min(len(reviewer),len(evidence_reference))<16 or not isinstance(unresolved_findings,list)
            or not 1<=len(unresolved_findings)<=6 or any(not isinstance(f,str) or not 8<=len(f)<=300 for f in unresolved_findings)):
        raise ValueError('independent_scoped_program_review_and_unresolved_findings_required')
    old=next((r for r in rows(root,'recursive_method_reviews') if r['candidate_id']==candidate_id),None)
    if old:return old
    candidate=records.read(root,'recursive_candidates',candidate_id)
    episode=records.read(root,'learning_episodes',candidate['episode_id'])
    task=read_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'))
    if not any(records.read(root,'attempts',a)['response']==candidate['proposal'] for a in task['attempt_ids']):
        raise ValueError('owned_novali_program_required')
    if candidate['report']['evaluator_sha256']!=evaluator.fingerprint():raise ValueError('current_program_proof_required')
    from .lesson_review_budget import charge
    with charge(root,episode):
        replay=evaluator.evaluate(candidate['proposal'],episode['baseline']['strategy'],episode['seed'],episode['stage'])
        restarted=restart_report(root,candidate,episode)
        if not all(replay[k]['complete'] for k in ('authored_cases','transfer','regression')) or not restarted['result']['complete']:
            raise ValueError('successful_program_transfer_and_restart_required')
        return records.store(root,'recursive_method_reviews',{'candidate_id':candidate_id,'reviewer':reviewer,
            'evidence_reference':evidence_reference,'unresolved_findings':unresolved_findings,
            'evaluator_sha256':evaluator.fingerprint(),'replay':replay,'restart':restarted,
            'scope':'pure_cached_projection_practice_only','question_approved':False,
            'curriculum_advancement':False,'strategy_promotion':False,'hypothesis_status':replay['hypothesis_status'],
            'allowance_added':0})


def methods(root: Path) -> list[dict]:
    reviews=[r for r in rows(root,'recursive_reviews') if r['decision']=='approve']+rows(root,'recursive_method_reviews')
    result={}
    quarantined={records.read(root,'recursive_use_outcomes',r['outcome_id'])['candidate_id'] for r in rows(root,'recursive_use_reviews') if r['decision']=='approve'}
    for review in reviews:
        if review['candidate_id'] in quarantined:continue
        if review['evaluator_sha256']!=evaluator.fingerprint():continue
        candidate=records.read(root,'recursive_candidates',review['candidate_id'])
        result[candidate['id']]={'id':candidate['id'],'strategy':candidate['proposal']['strategy'],'review_id':review['id'],
            'scope':'cached record projections only; inspect applicability on current input; no research or question acceptance',
            'unresolved_findings':review.get('unresolved_findings',[])}
    return list(result.values())


def rollback(root: Path, *, expected_version_id: str, reviewer: str, reason: str) -> dict:
    current=active(root)
    if current['version_id']!=expected_version_id or min(len(reviewer),len(reason))<16:
        raise ValueError('exact_reviewed_rollback_required')
    parent=current['parent_version_id']
    result=records.store(root,'recursive_rollbacks',{'version_id':expected_version_id,'parent_version_id':parent,
        'reviewer':reviewer,'reason':reason,'costs_retained':True})
    write_json(root/'research_methods/recursive_strategy_latest.json',{'version_id':parent} if parent else {})
    return result


def status(root: Path) -> dict:
    try:version=active(root)
    except ValueError as exc:version={'blocked':str(exc)}
    from .recursive_failure_review import status as failure_status
    from .recursive_loop import status as loop_status
    from .recursive_review_queue import status as queue_status
    from .recursive_use import scorecard
    return {'policy':policy(root),'active_strategy':version,'failed_attempt_reviews':failure_status(root),
        'learning_loop':loop_status(root),'independent_review_queue':queue_status(root),'downstream_use':scorecard(root),
        'pending_reviews':[read_json(p)['candidate_id'] for p in (root/'research_methods/episode_tasks').glob('*.json')
                           if read_json(p).get('state')=='awaiting_recursive_review'],
        'reviewed_sources':len(rows(root,'recursive_sources')),'scientific_allowance_added':0,
        'retained_practice_procedures':[m['id'] for m in methods(root)],
        'capability_claim':'instrument transfer only; planner reuse and research advantage require separate evaluation'}


if __name__=='__main__':
    if len(sys.argv)!=4 or sys.argv[1]!='restart':raise SystemExit('restart ROOT CANDIDATE_ID required')
    root=Path(sys.argv[2]);candidate=records.read(root,'recursive_candidates',sys.argv[3])
    episode=records.read(root,'learning_episodes',candidate['episode_id'])
    report=evaluator.assess(candidate['proposal']['strategy'],episode['baseline']['strategy'],
                            evaluator.cases(episode['seed']^0x73CA,2))
    print(json.dumps({'candidate_sha256':digest(candidate),'process_id':os.getpid(),
        'evaluator_sha256':evaluator.fingerprint(),'result':report}))

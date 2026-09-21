"""Bounded, Novali-authored transport strategies and measured action costs."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from .research_tools import digest, read_json

GROUPS = {
    'evidence': ['inspect_source','inspect_dependency','retrieve_evidence','inspect_record'],
    'formulation': ['register_claim','register_formal_claim','check_measurement','request_capability'],
    'evaluation': ['submit_research_plan','propose_revision','evaluate_revision'],
    'decision': ['decide_revision','submit_review_response','request_capability'],
}
ADOPTION_CRITERIA = {'candidate_passes':3,'restart_retained':True,'maximum_baseline_cost_ratio':1.05,
    'retention':'successful_fresh_task_resumption_and_strategy_reuse',
    'comparison':'same reviewed guidance in both arms; only planning strategy differs'}


def schema() -> dict[str, Any]:
    from .planner_authoring import _object, _string
    return _object({'name':_string(8,100), 'rationale':_string(8,200),
        'instruction_mode':{'type':'string','enum':['full','compact_catalog']},
        'excerpt_chars':{'type':'integer','enum':[1024,2048,4000]},
        'command_scope':{'type':'string','enum':['all_executable','current_stage']}})


def validate(profile: Mapping[str, Any]) -> None:
    from .method_patches import _valid
    if not _valid(profile, schema()): raise ValueError('typed_bounded_planning_strategy_required')


def signature(profile: Mapping[str, Any]) -> str:
    validate(profile)
    return digest({k:v for k,v in profile.items() if k not in {'name','rationale'}})


def hypothesis_schema() -> dict[str, Any]:
    from .planner_authoring import _object, _string
    return _object({'mechanism':_string(12,400), 'falsifier':_string(12,400),
        'metric':{'type':'string','enum':['context_bytes','instruction_chars','schema_bytes','action_seconds','prompt_seconds']},
        'predicted_reduction_percent':{'type':'number','minimum':1,'maximum':90},
        'changed_fields':{'type':'array','minItems':1,'maxItems':3,'uniqueItems':True,
            'items':{'type':'string','enum':['excerpt_chars','instruction_mode','command_scope']}}})


def validate_hypothesis(hypothesis: Any, profile: Mapping[str, Any], previous: Mapping[str, Any]) -> None:
    from .method_patches import _valid
    if not _valid(hypothesis,hypothesis_schema()): raise ValueError('typed_strategy_cost_hypothesis_required')
    changed = {k for k in ('excerpt_chars','instruction_mode','command_scope') if profile[k]!=previous[k]}
    if len(set(hypothesis['changed_fields']))!=len(hypothesis['changed_fields']) or set(hypothesis['changed_fields'])!=changed:
        raise ValueError('hypothesis_changed_fields_must_match_actual_strategy_changes')


def authoring_inputs(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Cost strategy authors need structure; the checker retains full source input."""
    import json
    result=copy.deepcopy(dict(inputs)); context=result.pop('planning_context',None)
    local=result.get('local_measurements') or {}
    effects=local.get('effects',{})
    if effects and all(len(key)==64 for key in effects):
        labels={key:'effect_'+str(index) for index,key in enumerate(sorted(effects))}
        local['effects']={labels[key]:value for key,value in effects.items()}
        for choice in local.get('choices',[]):
            if choice.get('effect') in labels:choice['effect']=labels[choice['effect']]
        local['display_scope']='Short labels within this catalog; immutable hashes remain in measurement_id.'
    application=result.get('lesson_applicability') or {}
    for row in application.get('lessons',[]):
        keep={'id','input_sha256','original_verdict','scope','method_adoption_authorized','hypothesis','profile','observations'}
        for key in list(row):
            if key not in keep:row.pop(key)
        row['hypothesis']={key:value for key,value in row['hypothesis'].items()
                           if key in ('metric','predicted_reduction_percent')}
        row['profile']={key:value for key,value in row['profile'].items()
                        if key in ('instruction_mode','excerpt_chars','command_scope')}
        row['observations']=[{key:value for key,value in observation.items() if key!='definition'}
                              for observation in row.get('observations',[])]
    if result.get('lesson_applicability') and result.get('question_opportunity'):
        opportunity=result['question_opportunity']
        opportunity['lesson']={'id':opportunity['lesson']['id'],'evidence_location':'lesson_applicability.lessons'}
    if not isinstance(context,dict):return result
    if isinstance(result.get('previous_strategy'),dict):
        previous=result['previous_strategy']
        result['previous_strategy_provenance']={'sha256':digest(previous),'scope':'historical_proposal_not_current_instructions'}
        result['previous_strategy']={k:previous[k] for k in ('excerpt_chars','instruction_mode','command_scope')}
    theory=context.get('theory',{}); memory=context.get('evidence_memory',{})
    result['planning_context_outline']={
        'scope':'method_strategy_authorship_only_full_frozen_context_retained_by_checker',
        'frozen_context_sha256':digest(context),
        'component_bytes':{k:len(json.dumps(v,separators=(',',':')).encode()) for k,v in context.items()},
        'claim_kinds':[c.get('kind') for c in theory.get('claims',[])],
        'revision_statuses':[r.get('status') for r in theory.get('revisions',[])],
        'evaluation_count':len(theory.get('evaluations',[])),
        'evidence_page_count':len(memory.get('pages',[])),
        'retrievable_excerpt_lengths':[len(r.get('text','')) for r in memory.get('claim_linked_excerpts',[])],
        'allowed_commands':context.get('call_allowance',{}).get('allowed_commands',[]),
        'required_action_present':bool(context.get('call_allowance',{}).get('required_first_action')),
        'strategy_controls':['excerpt_chars','instruction_mode','command_scope']}
    return result


def project(context: Mapping[str, Any], profile: Mapping[str, Any]) -> dict[str, Any]:
    validate(profile); result = copy.deepcopy(dict(context))
    # Keep navigation, reviews, unresolved assumptions and source bindings intact.
    for row in result.get('evidence_memory', {}).get('claim_linked_excerpts', []):
        text = row.get('text','')
        if len(text) > profile['excerpt_chars']:
            row.update(text=text[:profile['excerpt_chars']], text_truncated=True, full_excerpt_sha256=digest(text))
    return result


def commands(context: Mapping[str, Any], available: list[str], profile: Mapping[str, Any]) -> list[str]:
    validate(profile)
    if profile['command_scope'] == 'all_executable': return available
    theory = context.get('theory', {})
    if theory.get('evaluations'): stage = 'decision'
    elif any(c.get('kind') == 'mathematical' for c in theory.get('claims', [])) or any(
            r.get('status') == 'proposed' for r in theory.get('revisions', [])): stage = 'evaluation'
    elif not context.get('evidence_memory', {}).get('pages'): stage = 'evidence'
    else: stage = 'formulation'
    # Inspection and capability/review routes remain escape paths in every stage.
    keep = set(GROUPS[stage] + GROUPS['evidence'] + ['request_capability','submit_review_response'])
    required = context.get('call_allowance', {}).get('required_first_action', {}) or {}
    if required.get('command'): keep.add(required['command'])
    selected = [c for c in available if c in keep]
    return selected or available


def instructions(text: str, profile: Mapping[str, Any]) -> str:
    validate(profile)
    if profile['instruction_mode'] == 'full': return text
    # Only redundant JSON command catalog lines are shortened. Semantic rules,
    # uncertainty requirements, authority boundaries and explanations remain.
    catalog = {command for group in GROUPS.values() for command in group}
    return '\n'.join(line for line in text.splitlines() if line.split(': ',1)[0] not in catalog)


def preflight_check(context: Mapping[str, Any], profile: Mapping[str, Any], *, _baseline=None, _planner=None) -> dict[str, Any]:
    from .research_runtime import local_planner, ResearchPolicy
    from .theory_methods import dependency_choices
    import json
    context={k:v for k,v in context.items() if k!='planning_profile'}
    validate(profile); planner = _planner or local_planner(ResearchPolicy())
    baseline = None; baseline_error = None
    if _baseline is not None: baseline, baseline_error = _baseline
    else:
        try: baseline = planner.preflight('plan',context)
        except ValueError as exc:
            from .method_repair import UNDISPATCHED_FAILURES
            if str(exc) not in UNDISPATCHED_FAILURES: raise
            baseline_error = str(exc)
    candidate = planner.preflight('plan',{**context,'planning_profile':dict(profile)})
    before=json.loads(baseline['messages'][1]['content']) if baseline else context
    after=json.loads(candidate['messages'][1]['content'])
    if dependency_choices(before) != dependency_choices(after): raise ValueError('planning_strategy_lost_evidence_binding')
    for key in ('call_allowance','research_feedback'):
        if before.get(key) != after.get(key): raise ValueError('planning_strategy_changed_required_context')
    def sizes(payload):
        return {'context_bytes':len(payload['messages'][1]['content'].encode()),
            'instruction_chars':len(payload['messages'][0]['content']),
            'schema_bytes':len(json.dumps(payload['format'],separators=(',',':')).encode())} if payload else None
    before_sizes, after_sizes = sizes(baseline), sizes(candidate)
    return {'structural_preflight_passed':True,'baseline_payload_bytes':len(json.dumps(baseline).encode()) if baseline else None,
        'baseline_preflight_error':baseline_error,
        'candidate_payload_bytes':len(json.dumps(candidate).encode()),'provider_dispatched':False,
        'baseline_components':before_sizes,'candidate_components':after_sizes,
        'component_changes':{k:after_sizes[k]-before_sizes[k] for k in after_sizes} if before_sizes else None,
        'effective_input_sha256':digest({'context':{k:v for k,v in after.items() if k!='planning_profile'},
            'instructions':candidate['messages'][0]['content'],'schema':candidate['format']}),
        'production_completion_demonstrated':False,'requires_independent_production_evaluation':True}


def measurement_catalog(context: Mapping[str, Any]) -> dict[str, Any]:
    """Thirteen local preflights; no candidate selection, provider calls or answers."""
    import itertools
    from .research_runtime import local_planner, ResearchPolicy
    from .method_repair import UNDISPATCHED_FAILURES
    context={k:v for k,v in context.items() if k!='planning_profile'}
    planner=local_planner(ResearchPolicy()); baseline=None; error=None
    try: baseline=planner.preflight('plan',context)
    except ValueError as exc:
        if str(exc) not in UNDISPATCHED_FAILURES: raise
        error=str(exc)
    choices=[]; effects={}; baseline_sizes=None
    for mode,chars,scope in itertools.product(('full','compact_catalog'),(1024,2048,4000),('all_executable','current_stage')):
        controls={'instruction_mode':mode,'excerpt_chars':chars,'command_scope':scope}
        profile={'name':'Measured control combination','rationale':'Fixed diagnostic labels; choose your own strategy and explanation.',**controls}
        try:
            result=preflight_check(context,profile,_baseline=(baseline,error),_planner=planner)
            baseline_sizes=result['baseline_components']; key=result['effective_input_sha256']
            effects.setdefault(key,{'components':result['candidate_components'],'changes':result['component_changes']})
            choices.append({**controls,'effect':key})
        except ValueError as exc:choices.append({**controls,'error':str(exc)[:160]})
    return {'scope':'local_transport_measurement_only','checks':13,'provider_dispatched':False,
        'baseline_components':baseline_sizes,'baseline_error':error,'choices':choices,'effects':effects,
        'labels_are_fixed':True,'actual_proposal_is_remeasured':True,
        'latency_effect':'unknown_until_independent_experiment','no_strategy_selected':True}


def prediction_contract(candidate: Mapping[str, Any]) -> dict[str, Any] | None:
    hypothesis=candidate.get('strategy_hypothesis')
    if hypothesis is None:return None
    from .method_patches import _valid
    if not _valid(hypothesis,hypothesis_schema()):raise ValueError('typed_strategy_cost_hypothesis_required')
    return {'candidate_id':candidate['id'],'hypothesis':copy.deepcopy(hypothesis),
        'preflight':copy.deepcopy(candidate.get('assessment',{})),
        'comparison':'unprofiled_baseline_matched_completed_trajectories',
        'verdict_scope':'quantitative_prediction_on_frozen_cases_not_causal_proof'}


def hypothesis_result(output: Path, manifest: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    """Assess the frozen prediction independently of method usefulness/adoption."""
    import math
    contract=manifest.get('prediction_contract')
    outcome={'verdict':'inconclusive','scope':'quantitative_prediction_on_frozen_cases_not_causal_proof',
        'adoption_is_separate':True,'manifest_sha256':manifest['sha256']}
    if not contract:return {**outcome,'reason':'no_frozen_prediction'}
    hypothesis=contract['hypothesis']; metric=hypothesis['metric']
    outcome.update(metric=metric,predicted_reduction_percent=hypothesis['predicted_reduction_percent'])
    baseline=candidate=None
    if metric in ('context_bytes','instruction_chars','schema_bytes'):
        assessment=contract['preflight']
        baseline=(assessment.get('baseline_components') or {}).get(metric)
        candidate=(assessment.get('candidate_components') or {}).get(metric)
    else:
        if not result['complete'] or any(result['passes'].get(arm)!=result['cases_per_arm'] for arm in ('with_guidance','without_guidance')):
            return {**outcome,'reason':'matched_complete_outcomes_required'}
        costs=dict(result.get('arm_action_seconds',{}))
        if metric=='prompt_seconds':
            costs={'with_guidance':0.0,'without_guidance':0.0}
            receipts=list((output/'attempts').glob('*.json'))
            if not receipts:return {**outcome,'reason':'phase_measurements_missing'}
            for path in receipts:
                row=read_json(path); metadata=row.get('provider_metadata',{})
                seconds=metadata.get('timing',{}).get('provider_prompt_seconds')
                if metadata.get('provider_outcome')!='response_received' or type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<0:
                    return {**outcome,'reason':'phase_measurements_missing_or_invalid'}
                costs[row['trajectory'].split('/')[-1]]+=seconds
        baseline=costs.get('without_guidance');candidate=costs.get('with_guidance')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (baseline,candidate)) or baseline<=0 or candidate<0:
        return {**outcome,'reason':'valid_comparable_measurements_required'}
    maximum=baseline*(1-hypothesis['predicted_reduction_percent']/100)
    return {**outcome,'verdict':'supported' if candidate<=maximum else 'refuted',
        'reason':'frozen_numerical_prediction_checked','baseline':baseline,'candidate':candidate,
        'required_maximum':maximum,'observed_reduction_percent':100*(baseline-candidate)/baseline}


def hypothesis_history(root: Path) -> list[dict[str, Any]]:
    from . import research_procedures as records
    paths=sorted((root/'research_methods/planning_reviews').glob('*.json'),key=lambda p:p.stat().st_mtime_ns)[-6:]
    return [{'review_id':row['id'],'method_decision':row['decision'],'hypothesis_result':row['hypothesis_result']}
        for path in paths for row in [records.read(root,'planning_reviews',path.stem)] if row.get('hypothesis_result')]


def cost_diagnostics(output: Path) -> dict[str, Any]:
    """Bounded measurements, without fixture source, hidden cases or answers."""
    from .production_planner_eval import _load, summary
    manifest, account = _load(output)
    attempts = sorted((read_json(p) for p in (output/'attempts').glob('*.json')),
                      key=lambda row:(row['usage_after']['compute_seconds'],row['usage_after']['model_calls']))
    last = 0.0; rows = []
    for row in attempts:
        metadata = row.get('provider_metadata',{}); timing = metadata.get('timing',{})
        seconds = row['usage_after']['compute_seconds']-last; last=row['usage_after']['compute_seconds']
        task=row['task']
        rows.append({'trajectory':row['trajectory'],'action_seconds':seconds,
            'deadline_margin_seconds':manifest['limits']['timeout_seconds']-seconds,
            'provider_outcome':metadata.get('provider_outcome','unknown'),
            'prompt_seconds':timing.get('provider_prompt_seconds'),
            'generation_seconds':timing.get('provider_generation_seconds'),
            'load_seconds':timing.get('provider_load_seconds'),
            'transport_seconds':timing.get('transport_seconds'),
            'context_bytes':metadata.get('context_utf8_bytes'),'instruction_chars':metadata.get('instruction_chars'),
            'schema_bytes':metadata.get('schema_utf8_bytes'), 'state':task['state'],
            'stages':task.get('stages'), 'feedback':str(task.get('feedback',''))[:160]})
    known = [r for r in rows if type(r['prompt_seconds']) in (int,float) and type(r['generation_seconds']) in (int,float)]
    from .production_planner_eval import stage_progress
    from .theory_workspace import TheoryWorkspace
    progress = {}
    for case in manifest['cases']:
        sub=output/case['directory']; ws=TheoryWorkspace(sub/'state','study',repo_root=sub/'repo')
        progress[case['key']]=stage_progress(ws,read_json(ws._path('runs',case['work']['run_id'])))
    return {'scope':'method_cost_measurements_only','actions':rows[-12:],
        'trajectory_progress':progress,
        'action_count':len(rows),'actions_omitted':max(0,len(rows)-12),
        'completed_phase_measurements':len(known),
        'known_prompt_seconds':sum(r['prompt_seconds'] for r in known),
        'known_generation_seconds':sum(r['generation_seconds'] for r in known),
        'unknown_outcomes':sum(r['provider_outcome']=='unknown' for r in rows),
        'usage':account['usage'],'frozen_limits':manifest['limits'],
        'missing_components_are_unknown':True,'does_not_establish_strategy_causality':True,
        'hypothesis_result':hypothesis_result(output,manifest,summary(output))}


def recent_costs(workspace: Any) -> list[dict[str, Any]]:
    paths = sorted((workspace.base/'resource_receipts').glob('*.json'), key=lambda p:p.stat().st_mtime_ns)[-6:]
    return [{**{k:row.get(k) for k in ('call','command','outcome','action_seconds','local_seconds')},
        'timing':row.get('provider_metadata',{}).get('timing',{}),
        'prompt_tokens':row.get('provider_metadata',{}).get('prompt_eval_count'),
        'output_tokens':row.get('provider_metadata',{}).get('eval_count')}
        for p in paths for row in [read_json(p)]]


def context(root: Path) -> dict[str, Any] | None:
    from . import research_procedures as records
    pointer = read_json(root/'research_methods/planning_profile_latest.json')
    if not pointer: return None
    review = records.read(root,'planning_reviews',pointer['review_id'])
    if review['decision'] != 'approve' or review.get('profile_proof') != proof_dependencies(): return None
    from .provider_recovery import current_provider_identity
    if review['provider_identity'] != current_provider_identity(): return None
    candidate = records.read(root,'planning_candidates',review['candidate_id'])
    return candidate['profile']


def proof_dependencies() -> dict[str, str]:
    from .production_planner_eval import fingerprint
    unrelated = {'learning_episodes.py','resource_experiments.py','research_maintenance.py','experiment_learning.py',
                 'method_learning.py','method_continuation.py','method_repair.py'}
    return {k:v for k,v in fingerprint().items() if k not in unrelated}


def review(root: Path, candidate_id: str, output: Path, *, reviewer: str, authority_reference: str) -> dict[str, Any]:
    """Independent frozen production checks are the only adoption gate."""
    from . import production_planner_eval as evaluation, research_procedures as records
    from .theory_workspace import TheoryWorkspace
    from .provider_recovery import current_provider_identity
    from .research_tools import write_json
    if not reviewer.strip() or not authority_reference.strip(): raise ValueError('independent_strategy_review_required')
    candidate=records.read(root,'planning_candidates',candidate_id)
    manifest,_=evaluation._load(output); result=evaluation.summary(output)
    if manifest.get('prediction_contract')!=prediction_contract(candidate):raise ValueError('frozen_prediction_contract_changed')
    if (manifest.get('version')!='production_planner_v2' or manifest.get('planning_profile')!=candidate['profile'] or manifest['implementation']!=evaluation.fingerprint()
            or manifest.get('adoption_criteria')!=ADOPTION_CRITERIA
            or not manifest.get('provider_identity') or manifest['provider_identity']!=current_provider_identity()):
        raise ValueError('current_frozen_strategy_evaluation_required')
    if not result['complete']: raise ValueError('complete_strategy_evaluation_required')
    independent_passes = {arm:0 for arm in ('with_guidance','without_guidance')}
    for case in manifest['cases']:
        directory=output/case['directory']; ws=TheoryWorkspace(directory/'state','study',repo_root=directory/'repo')
        state=read_json(ws._path('runs',case['work']['run_id']))
        if evaluation._score(ws,case,state): independent_passes[case['arm']]+=1
    costs=result['arm_action_seconds']
    accepted=(result['passes']['with_guidance']==3 and independent_passes['with_guidance']==3
        and result['restart_retained'] and costs['with_guidance']<=costs['without_guidance']*1.05)
    status=read_json(root/'autonomy/status.json')
    if status.get('active') is not True or status.get('emergency_stop'): raise ValueError('strategy_adoption_controls_blocked')
    record=records.store(root,'planning_reviews',{'candidate_id':candidate_id,'manifest_sha256':manifest['sha256'],
        'result_sha256':digest(result),'independent_passes':independent_passes,'arm_compute_seconds':costs,
        'decision':'approve' if accepted else 'reject','reviewer':reviewer,'authority_reference':authority_reference,
        'implementation':evaluation.fingerprint(),'provider_identity':manifest['provider_identity'],
        'profile_proof':proof_dependencies(),
        'restart_retained':result['restart_retained'],'parent_continuation_authorized':False,
        'hypothesis_result':hypothesis_result(output,manifest,result)})
    if accepted: write_json(root/'research_methods/planning_profile_latest.json',{'review_id':record['id']})
    return record

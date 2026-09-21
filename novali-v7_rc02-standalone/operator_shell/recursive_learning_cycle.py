"""Frozen isolated correction-to-consumption evaluation, with honest partial results.

Acquisition uses a real owned Novali failure. Operator semantic review remains
external. Restart probes require independent processes and equal-budget controls.
"""
from __future__ import annotations
import copy
import hashlib
import shutil
import time
from pathlib import Path
from . import recursive_growth as growth, recursive_failure_review as recovery
from . import recursive_practice_checks as checks, recursive_capability_eval as capability
from . import recursive_evaluator as evaluator, learning_episodes as learning
from .research_tools import read_json, digest, write_json

INTERFACES = ('focused', 'path')


def fingerprint() -> dict:
    return {**capability.fingerprint(), 'recursive_learning_cycle.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def prepare(root: Path, output: Path, episode_id: str, *, model: str, seed: int, reuse_seeds: list[int]) -> dict:
    if output.exists() or not model or type(seed) is not int or not 0<=seed<2**31:
        raise ValueError('fresh_frozen_learning_cycle_required')
    if not 2<=len(reuse_seeds)<=8 or len(set(reuse_seeds))!=len(reuse_seeds) or any(type(s) is not int or s<0 for s in reuse_seeds):
        raise ValueError('two_to_eight_distinct_restart_tasks_required')
    episode,task,account,attempt=recovery.owned(root,episode_id)
    snapshot=output/'snapshot'
    shutil.copytree(root/'research_methods',snapshot/'research_methods')
    write_json(snapshot/'autonomy/status.json',read_json(root/'autonomy/status.json'))
    return capability.save(output/'plan.json',{'parent_episode_id':episode_id,'parent_attempt_id':attempt['id'],
        'parent_attempt_sha256':digest(attempt),'parent_usage':account['usage'],'model':model,'seed':seed,
        'reuse_seeds':reuse_seeds,'interfaces':list(INTERFACES),'implementation':fingerprint(),
        'terminal_question':episode.get('followup_depth',0)>=recovery.MAX_FOLLOWUPS,
        'calls_per_interface':4 if episode.get('followup_depth',0)>=recovery.MAX_FOLLOWUPS else 2,
        'calls_per_phase':2,'question_admitted_at':max(time.time(),max(e['admitted_at'] for e in growth.rows(root,'learning_episodes'))+7201),
        'output_tokens':1000,'provider_seconds':110,
        'acceptance':'substantive_behavior_repair_then_independent_review_then_downstream_consumption_then_restart_reuse',
        'scientific_allowance_added':0,'live_execution_authority':False})


def plan_for(output: Path) -> dict:
    plan=capability.checked(output/'plan.json')
    if plan['implementation']!=fingerprint():raise ValueError('frozen_cycle_implementation_changed')
    return plan


def acquire(output: Path, interface: str, *, planner) -> dict:
    plan=plan_for(output)
    if interface not in INTERFACES:raise ValueError('known_interface_required')
    arm=output/interface;root=arm/'state'
    receipt=arm/'acquisition.json'
    if receipt.exists():return capability.checked(receipt)
    if plan.get('terminal_question'):
        from . import recursive_loop as loop
        authored=capability.checked(arm/'question-authoring.json')
        reviewed=next((r for r in growth.rows(root,'recursive_question_reviews') if r['question_id']==authored.get('question_id') and r['decision']=='approve'),None)
        if not reviewed:raise ValueError('independently_reviewed_question_required')
        intent=arm/'practice-intent.json'
        if intent.exists():raise ValueError('interrupted_practice_admission_requires_review')
        capability.save(intent,{'question_review_id':reviewed['id'],'plan_sha256':plan['sha256']})
        shared=learning.policy(root);stamp=plan['question_admitted_at']+shared.get('admission_interval_seconds',7200)+1
        task=loop.admit(root,stamp=stamp,shared=shared,configured=growth.policy(root),acceptance_seed=plan['seed'])
    else:
        if root.exists():raise ValueError('interrupted_cycle_requires_review_no_free_restart')
        shutil.copytree(output/'snapshot',root)
        parent=plan['parent_episode_id']
        review=recovery.review(root,parent,decision='followup',reviewer='Independent frozen evaluation replay',
            evidence_reference='Replay the owned failed instrument and provide no authored repair; isolated comparison only.')
        shared=learning.policy(root);stamp,earliest=learning.admission_window(root,shared)
        if stamp<earliest:raise ValueError('snapshot_budget_window_not_available')
        task=recovery.admit(root,growth.rows(root,'learning_episodes'),growth.active(root),stamp,shared,growth.policy(root),acceptance_seed=plan['seed'])
    if task is None or growth.records.read(root,'learning_episodes',task['learning_episode_id'])['family']!='recursive_practice':raise ValueError('frozen_followup_not_eligible')
    capability.save(receipt,{'state':'reserved','episode_id':task['learning_episode_id'],'plan_sha256':plan['sha256'],
                             'interface':interface,'calls_reserved':2})
    for _ in range(2):
        if task['state']!='ready':break
        def bound_context(context):
            result=copy.deepcopy(context);result['task']={'planner_model':plan['model']}
            return result
        def preflight(phase, context):
            prepared=planner.preflight(phase,bound_context(context))
            if prepared['model']!=plan['model'] or prepared['options']['num_predict']!=plan['output_tokens']:
                raise ValueError('frozen_cycle_model_and_budget_required')
            return prepared
        def checked_planner(phase, context):
            old=getattr(planner,'dispatch_hook',None)
            try:
                planner.dispatch_hook=getattr(checked_planner,'dispatch_hook',None)
                result=planner(phase,bound_context(context))
                checked_planner.last_metadata=getattr(planner,'last_metadata',{})
                return result
            finally:planner.dispatch_hook=old
        if callable(getattr(planner,'preflight',None)):checked_planner.preflight=preflight
        checked_planner.supports_dispatch_hook=getattr(planner,'supports_dispatch_hook',False)
        task=growth.advance(root,task,planner=checked_planner,correction_interface=interface)
    account=read_json(root/'research_methods/episode_accounts'/(task['learning_episode_id']+'.json'))
    return capability.save(receipt,{'state':task['state'],'episode_id':task['learning_episode_id'],
        'interface':interface,'plan_sha256':plan['sha256'],'candidate_id':task.get('candidate_id'),
        'attempt_ids':task['attempt_ids'],'usage':account['usage'],'calls_reserved':2,
        'requires_independent_semantic_review':bool(task.get('candidate_id'))})


def author_question(output: Path, interface: str, *, planner) -> dict:
    from . import recursive_loop as loop
    plan=plan_for(output)
    if not plan.get('terminal_question') or interface not in INTERFACES:raise ValueError('terminal_question_plan_required')
    arm=output/interface;root=arm/'state';receipt=arm/'question-authoring.json'
    if receipt.exists():return capability.checked(receipt)
    if root.exists():raise ValueError('interrupted_question_requires_review_no_free_restart')
    shutil.copytree(output/'snapshot',root)
    if not loop.policy(root).get('enabled'):raise ValueError('explicit_frozen_loop_policy_required')
    loop.review_terminal(root,plan['parent_episode_id'],reviewer='Independent isolated terminal replay',
        evidence_reference='Verify the retained failure and partial coverage without supplying a question or method.')
    task=loop.admit(root,stamp=plan['question_admitted_at'],shared=learning.policy(root),configured=growth.policy(root))
    if not task:raise ValueError('frozen_question_admission_required')
    capability.save(receipt,{'state':'reserved','episode_id':task['learning_episode_id'],'calls_reserved':2,'plan_sha256':plan['sha256']})
    def bound(context):
        result=copy.deepcopy(context);result['task']={'planner_model':plan['model']};return result
    def checked(phase,context):
        old=getattr(planner,'dispatch_hook',None)
        try:
            planner.dispatch_hook=getattr(checked,'dispatch_hook',None)
            result=planner(phase,bound(context));checked.last_metadata=getattr(planner,'last_metadata',{});return result
        finally:planner.dispatch_hook=old
    def preflight(phase,context):
        value=planner.preflight(phase,bound(context))
        if value['model']!=plan['model'] or value['options']['num_predict']!=plan['output_tokens']:raise ValueError('frozen_question_model_and_budget_required')
        return value
    if callable(getattr(planner,'preflight',None)):checked.preflight=preflight
    checked.supports_dispatch_hook=getattr(planner,'supports_dispatch_hook',False)
    for _ in range(2):
        if task['state']!='ready':break
        task=loop.advance(root,task,planner=checked)
    account=read_json(root/'research_methods/episode_accounts'/(task['learning_episode_id']+'.json'))
    return capability.save(receipt,{'state':task['state'],'episode_id':task['learning_episode_id'],'question_id':task.get('question_id'),
        'calls_reserved':2,'usage':account['usage'],'attempt_ids':task['attempt_ids'],'plan_sha256':plan['sha256']})


def prepare_reuse(output: Path, interface: str) -> dict:
    """Call only after independent operator review of the isolated candidate."""
    plan=plan_for(output);arm=output/interface;root=arm/'state'
    acquisition=capability.checked(arm/'acquisition.json')
    candidate=acquisition.get('candidate_id')
    reviewed=next((r for r in growth.rows(root,'recursive_reviews') if r['candidate_id']==candidate and r['decision']=='approve'),None)
    if not reviewed:raise ValueError('independently_approved_corrected_candidate_required')
    accepted=growth.records.read(root,'recursive_candidates',candidate)
    proposal=accepted['proposal']
    if set(accepted.get('protected_discovery_states',[]))-set(checks.coverage(proposal,accepted['stage'])['covered_states']):
        raise ValueError('previous_discovery_coverage_must_survive_repair')
    parent=growth.records.read(root,'attempts',plan['parent_attempt_id'])
    if parent.get('report'):original=parent['response']
    else:
        from .recursive_rejections import replay
        original=replay(root,parent)['prior']
    if checks.behavior_signature(proposal['strategy'])==checks.behavior_signature(original['strategy']):
        raise ValueError('substantive_correction_required')
    reuse=arm/'reuse'
    if not reuse.exists():
        # Frozen control is the pre-acquisition snapshot, so it receives no new method.
        capability.prepare(output/'snapshot',reuse,model=plan['model'],seeds=plan['reuse_seeds'])
    generation=capability.generation(root,reuse)
    return capability.save(arm/'review_binding.json',{'candidate_id':candidate,'review_id':reviewed['id'],
        'generation_name':generation['name'],'plan_sha256':plan['sha256'],'substantive_correction':True,
        'protected_discovery_states':accepted.get('protected_discovery_states',[]),'discovery_coverage_preserved':True})


def consume(output: Path, interface: str) -> dict:
    """Materialize and independently consume accepted work from the first fresh task.

    Remaining seeds measure later restart reuse; this receipt alone is insufficient.
    """
    plan=plan_for(output);arm=output/interface;root=arm/'state'
    binding=capability.checked(arm/'review_binding.json')
    seed=plan['reuse_seeds'][0]
    path=arm/'reuse/probes'/binding['generation_name']/'with_memory'/(str(seed)+'.json')
    probe=capability.checked(path)
    if not probe.get('successful_reviewed_reuse') or probe['response']['method_id']!=binding['candidate_id']:
        raise ValueError('accepted_method_downstream_use_required')
    candidate=growth.records.read(root,'recursive_candidates',binding['candidate_id'])
    case=evaluator.cases(seed^0x185D,2,count=1)[0]
    artifact={'input_sha256':digest(case),'slots':evaluator.execute(candidate['proposal']['strategy'],case)['slots']}
    if probe['input_sha256']!=digest(case) or evaluator.oracle(case,artifact):
        raise ValueError('downstream_state_contract_failed')
    artifact=capability.save(arm/'downstream_artifact.json',artifact)
    # Consumer reads the persisted artifact rather than trusting the author's claim.
    persisted=capability.checked(arm/'downstream_artifact.json')
    if evaluator.oracle(case,persisted):raise ValueError('persisted_artifact_consumption_failed')
    from .recursive_use import consume as consume_method
    use=consume_method(root,candidate['id'],case,consumer_episode_id=candidate['episode_id'],
        operation_key='frozen-cycle:'+plan['sha256']+':'+interface)
    if not use['accepted']:raise ValueError('independent_cached_consumer_rejected')
    return capability.save(arm/'consumption.json',{'candidate_id':candidate['id'],'review_id':binding['review_id'],
        'probe_sha256':probe['sha256'],'artifact_sha256':artifact['sha256'],'seed':seed,
        'consumed_selected_fields':list(persisted['slots']),'accepted_downstream_work':True,'use_outcome_id':use['id'],
        'scope':'isolated_cached_record_consumer_not_live_child_delivery'})


def summarize(output: Path) -> dict:
    plan=plan_for(output);arms={}
    for interface in INTERFACES:
        arm=output/interface
        if not (arm/'acquisition.json').exists():
            arms[interface]={'state':'practice_not_run','complete_learning_cycle':False,
                'question_authoring':capability.checked(arm/'question-authoring.json') if (arm/'question-authoring.json').exists() else None};continue
        acquisition=capability.checked(arm/'acquisition.json')
        value={'acquisition':acquisition,'complete_learning_cycle':False}
        if plan.get('terminal_question'):value['question_authoring']=capability.checked(arm/'question-authoring.json')
        if (arm/'review_binding.json').exists():
            binding=capability.checked(arm/'review_binding.json')
            comparison=capability.summarize(arm/'reuse',binding['generation_name'])
            value['restart_comparison']=comparison
            consumption=capability.checked(arm/'consumption.json') if (arm/'consumption.json').exists() else None
            probes=[capability.checked(p) for p in (arm/'reuse/probes'/binding['generation_name']/'with_memory').glob('*.json')]
            later=[p for p in probes if p['seed']!=plan['reuse_seeds'][0]]
            value['complete_learning_cycle']=bool(consumption and comparison['complete'] and later and
                all(p.get('successful_reviewed_reuse') and p['response']['method_id']==binding['candidate_id'] for p in later)
                and len({p['process_id'] for p in probes})==len(probes))
        arms[interface]=value
    return {'plan_sha256':plan['sha256'],'arms':arms,'comparative_learning_advantage':'not_established',
            'scientific_progress_credited':False,'scope':'isolated_cached_record_learning_cycle'}

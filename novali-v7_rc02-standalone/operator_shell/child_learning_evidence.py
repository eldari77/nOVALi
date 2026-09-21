"""Integrity-checked, answer-free patterns from settled child learning archives."""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
from typing import Any
from .research_tools import digest, read_json
from . import research_procedures as records


def inspect(output: Path) -> dict[str, Any]:
    from .child_directive_eval import load
    from .directive_candidates import assess
    manifest,state=load(output,require_current_implementation=False)
    if manifest.get('version') not in {'child_learning_cycle_v1','child_learning_cycle_v2','child_learning_cycle_v3','child_learning_cycle_v4','child_learning_cycle_v5','child_learning_cycle_v6','child_learning_cycle_v7','child_learning_cycle_v8'}:
        raise ValueError('versioned_child_learning_archive_required')
    cases=manifest['cases']; names=[c['name'] for c in cases]
    if manifest['version']=='child_learning_cycle_v3':
        expected={'with_memory','without_memory','with_memory_focused','without_memory_focused'}
        for adapter in {c['adapter'] for c in cases}:
            group=[c for c in cases if c['adapter']==adapter]
            if len(group)!=4 or {c['arm'] for c in group}!=expected:
                raise ValueError('complete_memory_by_profile_controls_required')
            def source_inputs(case):
                return {phase:{k:v for k,v in frozen.items() if k not in {'permitted_context_profiles','initial_context_profile'}}
                        for phase,frozen in case['inputs'].items()}
            if len({digest(source_inputs(c)) for c in group})!=1:
                raise ValueError('matched_source_inputs_across_profiles_required')
    if (not 1<=len(cases)<=12 or len(set(names))!=len(names) or any(
        c['arm'] not in ('with_memory','without_memory','with_memory_focused','without_memory_focused') or c['name']!=c['adapter']+'/'+c['arm'] for c in cases)):
        raise ValueError('owned_matched_child_cases_required')
    for adapter,profile in {(c['adapter'], c['arm'].endswith('_focused')) for c in cases}:
        pair=[c for c in cases if c['adapter']==adapter and c['arm'].endswith('_focused') == profile]
        if len(pair)!=2 or len({digest(c['inputs']) for c in pair})!=1: raise ValueError('equal_input_child_controls_required')
    receipts={key:read_json(output/'receipts'/(key+'.json')) for key in state['receipts']}
    if any(r['case'] not in names for r in receipts.values()): raise ValueError('owned_child_receipt_required')
    patterns={}; evidence=[]
    def count(key): patterns[key]=patterns.get(key,0)+1
    total=0
    for case in cases:
        base=output/case['name']; root=base/'state'; progress=read_json(base/'progress.json')
        if progress['phase']!='complete': raise ValueError('settled_complete_child_cycle_required')
        owned=[r for r in receipts.values() if r['case']==case['name']]
        if set(progress['receipt_ids'])!={r['sha256'] for r in owned}: raise ValueError('child_progress_receipt_lineage_mismatch')
        if sum(r['calls'] for r in owned)!=progress['calls']: raise ValueError('child_case_call_accounting_mismatch')
        total+=progress['calls']
        for phase in ('train','reuse'):
            rows=[r for r in owned if r['phase']==phase]
            if not rows: raise ValueError('child_training_and_fresh_receipts_required')
            accepted=False; observed_own_failure=False; observed_correction=False
            for receipt in rows:
                task=receipt['result']; eid=task['learning_episode_id']
                if manifest['version'] in {'child_learning_cycle_v7','child_learning_cycle_v8'}:
                    seed_ids={s['method']['id'] for s in manifest.get('live_method_seeds',[]) if s['method']['adapter']==case['adapter']}
                    response=task.get('previous_response',{}); selected=response.get('lesson_id')
                    expected_seed=bool(receipt.get('accepted_artifact_and_consumed') and receipt['process']!=manifest['prepared_process']
                        and selected in seed_ids and response.get('lesson_use') in {'apply','adapt'} and case['arm']=='with_memory'
                        and receipt.get('method_adopted_for_retrieval'))
                    if receipt.get('live_seed_method_reused')!=expected_seed or receipt.get('selected_live_seed_id')!=(selected if selected in seed_ids else None):
                        raise ValueError('live_method_reuse_attribution_mismatch')
                    if receipt is rows[-1] and bool(progress.get(phase+'_live_seed_reused'))!=expected_seed:
                        raise ValueError('live_method_reuse_progress_mismatch')
                episode=records.read(root,'learning_episodes',eid)
                if episode['frozen_child_inputs']!=case['inputs'][phase]: raise ValueError('frozen_child_case_inputs_changed')
                for aid in task['attempt_ids']:
                    attempt=records.read(root,'attempts',aid)
                    if attempt['learning_episode_id']!=eid: raise ValueError('owned_child_attempt_required')
                from .child_failure_patterns import receipt_details
                for detail in receipt_details(receipt): count('child_'+detail['code'])
                if receipt['calls'] and task['attempt_ids']:
                    attempt=records.read(root,'attempts',task['attempt_ids'][-1])
                    if attempt['outcome']!=task['feedback']: raise ValueError('child_attempt_feedback_changed')
                    if attempt.get('provider_outcome_uncertain'): count('child_provider_outcome_uncertain')
                    for issue in attempt['outcome'].get('field_issues',[]): count('child_'+issue['code'])
                if receipt.get('accepted_artifact_and_consumed'):
                    candidate=records.read(root,'child_candidates',task['candidate_id'])
                    if assess(candidate['frozen'],candidate['context'],candidate['response'])!=candidate['assessment']:
                        raise ValueError('child_candidate_assessment_mismatch')
                    if manifest['version'] in {'child_learning_cycle_v4','child_learning_cycle_v5','child_learning_cycle_v6','child_learning_cycle_v7','child_learning_cycle_v8'}:
                        from .child_workflow_tasks import judge
                        if judge(candidate):raise ValueError('workflow_semantic_acceptance_mismatch')
                    consumption=receipt['consumption']; artifact=base/(phase+'-child-workspace')/consumption['target_artifact']
                    if not artifact.is_file() or hashlib.sha256(artifact.read_bytes()).hexdigest()!=consumption['artifact_sha256']:
                        raise ValueError('actual_child_consumption_evidence_required')
                    accepted=True
                if receipt.get('error'): count('child_delivery_not_completed')
                if manifest['version'] in {'child_learning_cycle_v6','child_learning_cycle_v7','child_learning_cycle_v8'}:
                    corrected=bool(receipt.get('accepted_artifact_and_consumed') and observed_own_failure)
                    if receipt.get('corrected_own_attempt')!=corrected:raise ValueError('owned_child_correction_attribution_mismatch')
                    observed_correction=observed_correction or corrected
                    feedback=task.get('feedback',{})
                    observed_own_failure=observed_own_failure or bool(receipt['calls'] and not receipt.get('accepted_artifact_and_consumed') and (
                        receipt.get('error') or feedback.get('field_issues') or feedback.get('method_assessment',{}).get('field_issues')
                        or feedback.get('reason','').startswith('Expecting')))
                    if receipt.get('independent_correction_queued'):
                        returns=[records.read(root,'child_correction_returns',p.stem) for p in (root/'research_methods/child_correction_returns').glob('*.json')]
                        if not any(r['candidate_id']==task.get('candidate_id') and r['episode_id']==eid for r in returns):
                            raise ValueError('independent_correction_return_receipt_required')
                evidence.append(receipt['sha256'])
            if accepted!=progress[phase+'_passed']: raise ValueError('child_phase_verdict_mismatch')
            if manifest['version'] in {'child_learning_cycle_v6','child_learning_cycle_v7','child_learning_cycle_v8'} and (observed_correction!=bool(progress.get(phase+'_self_corrected'))
                    or observed_own_failure!=bool(progress.get(phase+'_own_failure'))):raise ValueError('child_correction_progress_mismatch')
            if not accepted: count('child_'+phase+'_acceptance_not_met')
        fresh=[r for r in owned if r['phase']=='reuse'][-1]
        reused=bool(progress['train_passed'] and progress['reuse_passed'] and progress.get('training_method_adopted',True)
            and fresh.get('method_adopted_for_retrieval',True) and case['arm'].startswith('with_memory')
            and fresh['process']!=progress['train_process'] and fresh['result'].get('previous_response',{}).get('lesson_id')==progress.get('training_candidate_id')
            and fresh['result'].get('previous_response',{}).get('lesson_use') in ('apply','adapt'))
        if reused!=progress['verified_reuse']: raise ValueError('child_reuse_attribution_mismatch')
        if case['arm'].startswith('with_memory') and not reused: count('child_verified_reuse_not_demonstrated')
    if total!=state['calls']: raise ValueError('child_archive_call_accounting_mismatch')
    return {'manifest_sha256':manifest['sha256'],'archive_state_sha256':digest(state),'evidence_sha256':digest(evidence),
        'historical_implementation':manifest['fingerprint'],'calls':state['calls'],'patterns':patterns,
        'scope':'observed_child_failure_patterns_only_no_answers_or_withheld_cases'}

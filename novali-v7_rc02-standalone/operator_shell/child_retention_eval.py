"""Paired fresh-task retention after independently accepted method acquisition."""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
from . import child_directive_eval as evaluation, child_live_seeds, research_procedures as records
from .research_tools import digest, read_json, write_json

VERSION = 'child_retention_v1'


def prepare(output: Path, *, seed_root: Path, candidate_ids: tuple[str, ...], model: str,
            provider_seconds: int = 120, procedure_execution: bool = True) -> dict[str, Any]:
    proofs = child_live_seeds.capture(seed_root, candidate_ids)
    # Acquisition must be owned by a real planner attempt, not an evaluator-authored fixture.
    acquisition_attempts = {}
    for proof in proofs:
        candidate = proof['candidate']
        attempts = [records.read(seed_root,'attempts',p.stem) for p in (seed_root/'research_methods/attempts').glob('*.json')]
        owned = [a for a in attempts if a.get('learning_episode_id')==candidate['learning_episode_id']
                 and a.get('response')==candidate['response'] and a.get('provider_dispatched')]
        if not owned: raise ValueError('planner_authored_acquisition_attempt_required')
        acquisition_attempts[candidate['id']] = owned[-1]
    adapters = tuple(dict.fromkeys(p['method']['adapter'] for p in proofs))
    manifest = evaluation.prepare(output,model=model,provider_seconds=provider_seconds,adapters=adapters,
        seed_root=seed_root,seed_candidate_ids=candidate_ids,procedure_execution=procedure_execution,retention_only=True)
    manifest.update(retention_contract=VERSION, acquisition_attempts=acquisition_attempts, acquisition_credit=False, training_answer_supplied=False,
        control='Identical fresh inputs and budgets after process restart. Only access to frozen accepted method memory differs.')
    manifest['limits'].update(training_calls=0,total_model_calls=2*len(manifest['cases']))
    for case in manifest['cases']:
        path=output/case['name']/'progress.json'; progress=read_json(path)
        progress.update(phase='reuse',train_process=manifest['prepared_process'], acquisition_skipped=True)
        write_json(path,progress)
    manifest['sha256']=digest({k:v for k,v in manifest.items() if k!='sha256'})
    write_json(output/'manifest.json',manifest)
    evaluation._save(output,read_json(output/'evaluation.json'))
    return manifest


def inspect(output: Path) -> dict[str, Any]:
    from . import directive_candidates as candidates
    from .child_workflow_tasks import judge
    from .child_failure_patterns import receipt_details
    manifest,state=evaluation.load(output,require_current_implementation=False)
    if manifest.get('retention_contract')!=VERSION or manifest.get('acquisition_credit') is not False:
        raise ValueError('frozen_retention_contract_required')
    if manifest['limits']['training_calls']!=0 or manifest['limits']['total_model_calls']!=2*len(manifest['cases']):
        raise ValueError('equal_bounded_fresh_task_budget_required')
    seeds={s['method']['id']:s for s in manifest['live_method_seeds']}
    if not seeds: raise ValueError('accepted_acquisition_required_before_retention')
    for cid,proof in seeds.items():
        attempt=manifest.get('acquisition_attempts',{}).get(cid,{})
        if (attempt.get('id')!='attempt-'+digest({k:v for k,v in attempt.items() if k!='id'})[:24]
                or attempt.get('response')!=proof['candidate']['response'] or not attempt.get('provider_dispatched')
                or attempt.get('learning_episode_id')!=proof['candidate']['learning_episode_id']):
            raise ValueError('intact_owned_acquisition_proof_required')
    receipts=[read_json(output/'receipts'/(k+'.json')) for k in state['receipts']]
    patterns={}; rows=[]
    for adapter in {c['adapter'] for c in manifest['cases']}:
        pair=[c for c in manifest['cases'] if c['adapter']==adapter]
        if len(pair)!=2 or {c['arm'] for c in pair}!=set(evaluation.ARMS) or len({digest(c['inputs']['reuse']) for c in pair})!=1:
            raise ValueError('equal_input_memory_controls_required')
    for case in manifest['cases']:
        root=output/case['name']/'state'; progress=read_json(output/case['name']/'progress.json')
        owned=[r for r in receipts if r['case']==case['name']]
        if progress['phase']!='complete' or not owned or set(progress['receipt_ids'])!={r['sha256'] for r in owned}:
            raise ValueError('complete_owned_retention_trajectory_required')
        last=owned[-1]['result'];task_path=root/'research_methods/episode_tasks'/(last['learning_episode_id']+'.json')
        account=read_json(root/'research_methods/episode_accounts'/task_path.name)
        if (read_json(task_path)!=last or account.get('inflight') or last['model_calls']!=sum(r['calls'] for r in owned)
                or not 0<=last['model_calls']<=2):raise ValueError('settled_retention_account_required')
        passed=False; reused=False
        for receipt in owned:
            if receipt['phase']!='reuse' or receipt['process']==manifest['prepared_process']:
                raise ValueError('fresh_work_in_restarted_process_required')
            task=receipt['result'];eid=task['learning_episode_id']
            episode=records.read(root,'learning_episodes',eid)
            if episode['frozen_child_inputs']!=case['inputs']['reuse']:raise ValueError('frozen_retention_inputs_changed')
            if receipt['calls']:
                attempt=records.read(root,'attempts',task['attempt_ids'][-1])
                if attempt['learning_episode_id']!=eid or attempt['outcome']!=task['feedback']:
                    raise ValueError('owned_retention_attempt_required')
            for detail in receipt_details(receipt):
                key='child_'+detail['code'];patterns[key]=patterns.get(key,0)+1
            if receipt.get('accepted_artifact_and_consumed'):
                cid=task['candidate_id'];candidate=records.read(root,'child_candidates',cid)
                if candidates.assess(candidate['frozen'],candidate['context'],candidate['response'])!=candidate['assessment'] or judge(candidate):
                    raise ValueError('independent_retention_acceptance_failed')
                from .child_review import latest
                from .child_repairs import verify_review
                review=latest(root,cid)
                if review.get('decision')!='approve' or review.get('candidate_id')!=cid:
                    raise ValueError('independent_artifact_approval_required')
                adopted=bool(review.get('method_approved'))
                verify_review(candidate,review.get('finding_resolutions'),'approve' if adopted else 'defer')
                if receipt.get('method_adopted_for_retrieval')!=adopted:raise ValueError('separate_method_adoption_verdict_required')
                if adopted:child_live_seeds.capture(root,(cid,))
                consumed=receipt['consumption']
                uses=[records.read(root,'child_consumption',p.stem) for p in (root/'research_methods/child_consumption').glob('*.json')]
                if not any(u.get('candidate_id')==cid and u.get('review_id')==review['id'] and u.get('use')=='verified_resident_artifact_write'
                           and u.get('artifact_sha256')==consumed.get('artifact_sha256') for u in uses):
                    raise ValueError('review_linked_actual_consumption_required')
                path=output/case['name']/'reuse-child-workspace'/consumed['target_artifact']
                if hashlib.sha256(path.read_bytes()).hexdigest()!=consumed['artifact_sha256']:
                    raise ValueError('actual_retention_consumption_required')
                selected=candidate['response'].get('lesson_id');use=candidate['response'].get('lesson_use')
                def mechanics(method):return {k:method.get(k) for k in ('representation','adapter','bindings','steps','stop_conditions')}
                passed=True;reused=bool(adopted and case['arm']=='with_memory' and selected in seeds and use in {'apply','adapt'}
                    and mechanics(candidate['response']['method'])==mechanics(seeds[selected]['method']))
                if receipt.get('live_seed_method_reused')!=reused:raise ValueError('retention_reuse_attribution_mismatch')
        if bool(progress['reuse_passed'])!=passed:raise ValueError('retention_verdict_mismatch')
        if not passed:patterns['child_reuse_acceptance_not_met']=patterns.get('child_reuse_acceptance_not_met',0)+1
        rows.append({'case':case['name'],'fresh_success':passed,'verified_method_reuse':reused,'acquisition_credit':False})
    return {'manifest_sha256':manifest['sha256'],'archive_state_sha256':digest(state),'evidence_sha256':digest(state['receipts']), 'historical_implementation':manifest['fingerprint'],'calls':state['calls'],
        'evidence_receipts':state['receipts'],'patterns':patterns,'cases':rows,
        'retention_contract':VERSION,'verified_reuse_after_restart':sum(r['verified_method_reuse'] for r in rows),
        'fresh_task_success':{arm:sum(r['fresh_success'] for r in rows if r['case'].endswith('/'+arm)) for arm in evaluation.ARMS},
        'acquisition_credit':False,'scope':'reviewable_retention_evidence_only_no_scientific_or_general_growth_credit',
        'scientific_progress_credited':False,'sustained_advantage':'unproven'}

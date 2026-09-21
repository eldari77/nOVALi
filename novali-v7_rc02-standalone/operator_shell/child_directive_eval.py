"""Frozen real-planner child learning trajectories with matched no-memory arms.

Training and fresh tasks have different supplied values and evidence identities.
Every provider attempt runs through production admission, accounting, validation,
reviewed bundles and the real child artifact writer. No scientific score is inferred.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

from . import child_directive_learning as practice, directive_candidates as candidates
from . import directive_obligations as obligations, learning_episodes as episodes, research_runtime as runtime
from . import research_procedures as records
from .research_tools import digest, read_json, write_json

PROCESS = uuid.uuid4().hex
ARMS = ('with_memory', 'without_memory')
REPAIR_ARMS = (*ARMS, 'with_memory_focused', 'without_memory_focused')


def fingerprint() -> dict[str, str]:
    base = Path(__file__).parent
    return {name: hashlib.sha256((base / name).read_bytes()).hexdigest() for name in
        ('directive_obligations.py', 'directive_candidates.py', 'child_directive_learning.py', 'child_directive_eval.py',
         'research_runtime.py', 'research_procedures.py', 'learning_episodes.py', 'practice_transaction.py', 'conveyor_child.py',
         'child_contracts.py', 'child_review.py', 'child_delivery.py', 'child_learning_evidence.py',
         'child_repairs.py', 'child_context.py', 'child_failure_learning.py', 'child_review_findings.py',
         'child_planning.py', 'child_procedure_programs.py', 'child_research_actions.py', 'child_evidence_selection.py', 'child_measurements.py', 'child_workflow_tasks.py', 'practice_experiments.py',
         'child_execution.py','child_failure_patterns.py','child_retention_eval.py','child_correction.py','child_refinement.py','research_change_review.py','child_relevance.py','child_live_seeds.py','next_practice.py','question_partitions.py','question_failure_learning.py')}


def _case(root: Path, adapter: str, phase: str, *, growth: bool = False) -> dict[str, Any]:
    did = 'directive-' + phase; eid = 'research-' + phase
    target = 'technical_documentation.md' if adapter == 'interface_contract' else 'records.json'
    directory = root / 'conveyor/campaigns' / did / 'drafts'; directory.mkdir(parents=True, exist_ok=True)
    if adapter == 'record_extraction':
        data = {'domain': 'laboratory_catalog' if phase == 'train' else 'archival_collection', 'items': [
            {'label': 'optical fixture', 'source': 'Lumen Archive', 'quantity': 0, 'condition': None} if phase == 'train' else
            {'label': 'manuscript folder', 'source': 'unknown', 'quantity': 7, 'condition': 'documented'}]}
        if growth:
            data['items'].append({'label':'second current record','condition':'unknown','quantity':False})
            if phase=='reuse':data['entries']=list(reversed(data.pop('items')))
        write_json(directory / target, data)
    elif adapter == 'evidence_binding':
        write_json(directory / target, {'domain': 'library_catalog' if phase == 'train' else 'weather_archive', 'observation':
            'The catalog lists seven entries with unresolved author dates.' if phase == 'train' else
            'The archive lists five stations with unknown calibration dates.', 'scientific_conclusion': 'unknown',
            'provenance_status':'Independent corroboration has not been supplied.'})
    else:
        (directory / target).write_text(('Archive import validates incoming catalog records.' if phase == 'train' else
            'A simulation export sends bounded event records to an archive.') +
            ' Define one proposed handoff with a finite threshold, matching units, an existing fixture reference and unknown-on-invalid behavior. '
            'No measured operating performance is available.\n', encoding='utf-8')
    write_json(directory / 'validation_fixtures.json', {'fixture': 'record-boundaries-' + phase, 'execution': 'not_performed'})
    raw = (directory / target).read_bytes()
    result = {'artifact_ref': 'drafts/' + target, 'sha256': hashlib.sha256(raw).hexdigest(),
              'text': raw.decode(), 'scope': 'artifact_content_only', 'metrics': {'bytes': len(raw)}}
    task = {'directive_id': did, 'directive_text': 'Improve the traceability of this review-only research artifact.',
        'target_artifact': target, 'requested_rows': [{'required_fields': ['source', 'quantity', 'condition', 'verified_date']}]
            if adapter == 'record_extraction' else [],
        'gaps': [{'kind': 'unknown_external_truth', 'fields': ['independent_evidence'], 'action': 'retain unverified claims as unresolved'}]}
    if growth and adapter=='record_extraction' and phase=='reuse':task['requested_rows'][0]['required_fields'].reverse()
    contract = {'task': task}; state = {'episode_id': eid, 'state': 'waiting_for_changed_input', 'contract_sha256': digest(contract),
        'usage': {'model_calls': 4, 'tool_calls': 1, 'compute_seconds': 440}, 'observations':
        [{'action_id': 'inspect-' + phase, 'ok': True, 'result': result, 'result_sha256': digest(result)}] if adapter == 'evidence_binding' else []}
    if adapter == 'evidence_binding':
        supplied=read_json(directory/target)
        state['plan']={'prediction':{'action_id':'inspect-'+phase,'metric':'bytes','operator':'>','value':0}}
        state['last_rejected_response']={'interpretation':'These supplied observations do not establish external truth.',
            'next_question':'What independent evidence is needed to resolve the remaining uncertainty?', 'candidate_artifact':{},
            'claims':[{'kind':'observation','text':supplied[key], 'evidence_refs':[{'action_id':'inspect-'+phase,'text':supplied[key]}]}
                      for key in ('observation','provenance_status')]}
        canonical=root/'conveyor/campaigns'/did/'canonical'/target
        write_json(canonical,supplied)
        other={**result,'artifact_ref':'canonical/'+target}
        state['observations'].append({'action_id':'inspect-canonical-'+phase,'ok':True,'result':other,'result_sha256':digest(other)})
    base = root / 'conveyor/research/episodes' / eid
    write_json(base / 'contract.json', contract); write_json(base / 'state.json', state)
    latest = read_json(root / 'conveyor/research/latest.json')
    write_json(root / 'conveyor/research/latest.json', {'directives': [*latest.get('directives', []), {'directive_id': did, 'episode_id': eid}]})
    return obligations.build(root, eid)


def _save(output: Path, state: dict[str, Any]) -> None:
    state = {k: v for k, v in state.items() if k != 'sha256'}
    state['case_trees'] = _trees(output)
    state['sha256'] = digest(state); write_json(output / 'evaluation.json', state)


def _trees(output: Path) -> dict[str, str]:
    modern = read_json(output/'manifest.json').get('version') in {'child_learning_cycle_v3','child_learning_cycle_v4','child_learning_cycle_v5','child_learning_cycle_v6','child_learning_cycle_v7','child_learning_cycle_v8'}
    arms = REPAIR_ARMS if modern else ARMS
    return {adapter + '/' + arm: digest({p.relative_to(output / adapter / arm).as_posix():
        hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((output / adapter / arm).rglob('*'))
        if p.is_file() and p.suffix in ('.json', '.md')}) for adapter in obligations.ADAPTERS for arm in arms}


def prepare(output: Path, *, model: str, provider_seconds: int = 120, adapters: tuple[str, ...] = obligations.ADAPTERS, repair_interface: bool = False, workflow: bool = False, growth: bool = False, correction: bool = False, relevance: bool = False, seed_root: Path | None = None, seed_candidate_ids: tuple[str, ...] = (), diagnostic: bool = False, procedure_execution: bool = False, retention_only: bool = False) -> dict[str, Any]:
    if output.exists(): raise ValueError('fresh_child_evaluation_directory_required')
    if type(provider_seconds) is not int or not 30 <= provider_seconds <= 120: raise ValueError('bounded_provider_seconds_required')
    if not adapters or len(set(adapters)) != len(adapters) or any(adapter not in obligations.ADAPTERS for adapter in adapters):
        raise ValueError('unique_registered_child_evaluation_adapters_required')
    from .child_live_seeds import capture
    if bool(seed_root) != bool(seed_candidate_ids): raise ValueError('live_seed_root_and_ids_required_together')
    seeds = capture(seed_root,seed_candidate_ids) if seed_root else []
    if any(s['method']['adapter'] not in adapters for s in seeds): raise ValueError('live_seed_adapter_must_be_evaluated')
    if diagnostic and seeds: raise ValueError('diagnostic_requires_own_attempt_without_method_seeds')
    relevance = relevance or bool(seeds) or diagnostic
    correction = correction or relevance
    growth = growth or correction
    workflow = workflow or growth
    repair_interface = repair_interface or workflow
    cases = []; stamps = time.time(); arms = REPAIR_ARMS if repair_interface and not workflow else ARMS
    for adapter in adapters:
        for arm in arms:
            name = adapter + '/' + arm; root = output / name / 'state'
            write_json(root / 'autonomy/status.json', {'active': True, 'emergency_stop': False})
            episodes.configure(root, limits={**episodes.DEFAULT_LIMITS, 'max_episodes_per_day': 12,
                'model_calls_per_week': 168, 'tool_calls_per_week': 2184, 'compute_seconds_per_week': 23520},
                enabled=True, admission_interval_seconds=7200, authority_reference='Frozen isolated evaluation funding')
            practice.configure(root, directive_ids=['directive-train', 'directive-reuse'], enabled=True,
                               authority_reference='Frozen isolated child learning evaluation', enable_repairs=repair_interface,
                               context_profiles=('focused',) if correction else ('full','focused') if growth else ('focused',) if arm.endswith('_focused') else ('full',),enable_research_tools=workflow,enable_growth=growth,enable_correction=correction,enable_relevance=relevance,enable_procedure_execution=procedure_execution)
            frozen = {phase: _case(root, adapter, phase,growth=growth) for phase in ('train', 'reuse')}
            if workflow:
                from .child_workflow_tasks import prepare_inputs
                frozen=prepare_inputs(root,adapter,seed_candidate=not (diagnostic or retention_only))
            episode = practice.admit(root, frozen['train'], now=stamps)
            case = {'name': name, 'adapter': adapter, 'arm': arm, 'inputs': frozen, 'train_episode_id': episode['id']}
            cases.append(case)
            write_json(output / name / 'progress.json', {'phase': 'train', 'episode_id': episode['id'], 'calls': 0,
                'train_passed': False, 'reuse_passed': False, 'verified_reuse': False, 'receipt_ids': [], 'train_process': None})
    manifest = {'version': 'child_learning_cycle_v8' if diagnostic else 'child_learning_cycle_v7' if relevance or seeds else 'child_learning_cycle_v6' if correction else 'child_learning_cycle_v5' if growth else 'child_learning_cycle_v4' if workflow else 'child_learning_cycle_v3' if repair_interface else 'child_learning_cycle_v2', 'fingerprint': fingerprint(), 'model': model, 'cases': cases,
        **({'relevance_contract':True,'live_method_seeds':seeds,'seed_scope':'Previously reviewed and consumed live methods; no scientific or training credit from importing them.'} if relevance or seeds else {}),
        'limits': {'training_calls': 2, 'fresh_task_calls': 2 if growth else 1, 'total_model_calls': (4 if growth else 3) * len(arms) * len(adapters), 'provider_seconds': provider_seconds,
                   'per_episode_seconds': 280, 'per_episode_checks': 26},
        'acceptance': 'Independent artifact validation, original-verifier replay for rejected citations, approved isolated revision, actual resident child consumption, then successful fresh-task revision after a different process starts. Verified reuse also requires selecting the consumed method and passing its current-input applicability contract. Artifact writes do not establish support or scientific success.',
        'control': ('Matched current source tasks, focused projections and call ceilings; only reviewed method memory differs.' if correction else
            'Matched current source tasks and call ceilings. Within each profile, only reviewed method memory differs. Full and focused profiles are crossed with memory availability; report profile cost and successful reuse separately.'),
        'diagnostic_obligation_track': diagnostic, 'training_answer_supplied': False if diagnostic else workflow,
        'growth_contract': growth, 'correction':correction, 'repair_interface': repair_interface, **({'workflow':True,'workflow_acceptance':'Original citation repair or question-matched artifact measurement, scoped independent review, actual delivery and method-selected success on a fresh task in a new process. Rejection retains unresolved findings and gives no credit.'} if workflow else {}),
        'scientific_progress_credited': False, 'research_performance': 'not_evaluated', 'prepared_process': PROCESS}
    manifest['sha256'] = digest(manifest); write_json(output / 'manifest.json', manifest)
    _save(output, {'calls': 0, 'inflight': None, 'receipts': [], 'next_index': 0})
    return manifest


def load(output: Path, *, require_current_implementation: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = read_json(output / 'manifest.json'); state = read_json(output / 'evaluation.json')
    if manifest.get('version') not in {'child_learning_cycle_v1','child_learning_cycle_v2','child_learning_cycle_v3','child_learning_cycle_v4','child_learning_cycle_v5','child_learning_cycle_v6','child_learning_cycle_v7','child_learning_cycle_v8'}:
        raise ValueError('registered_child_evaluation_version_required')
    for row in (manifest, state):
        if row.get('sha256') != digest({k: v for k, v in row.items() if k != 'sha256'}): raise ValueError('child_evaluation_integrity_failure')
    if manifest['version'] in {'child_learning_cycle_v7', 'child_learning_cycle_v8'}:
        from .child_live_seeds import validate
        seeds=manifest.get('live_method_seeds',[])
        if not isinstance(seeds,list) or len(seeds)>2 or len({s['method']['id'] for s in seeds})!=len(seeds):
            raise ValueError('bounded_distinct_live_seed_proofs_required')
        for proof in seeds: validate(proof)
        if manifest['version'] == 'child_learning_cycle_v8' and (seeds or not manifest.get('diagnostic_obligation_track') or manifest.get('training_answer_supplied') is not False):
            raise ValueError('diagnostic_requires_unseeded_obligation_track')
    cases=manifest.get('cases',[])
    if (not isinstance(cases,list) or not 1<=len(cases)<=(12 if manifest['version']=='child_learning_cycle_v3' else 6) or any(not isinstance(c,dict)
            or c.get('adapter') not in obligations.ADAPTERS or c.get('arm') not in (REPAIR_ARMS if manifest['version']=='child_learning_cycle_v3' else ARMS)
            or c.get('name')!=c['adapter']+'/'+c['arm'] for c in cases)
            or len({c['name'] for c in cases})!=len(cases)):
        raise ValueError('owned_bounded_child_cases_required')
    if require_current_implementation and manifest['fingerprint'] != fingerprint(): raise ValueError('frozen_child_evaluator_changed')
    if state['inflight']: raise ValueError('interrupted_child_evaluation_requires_review_costs_retained')
    if state.get('case_trees') != _trees(output): raise ValueError('child_evaluation_saved_state_changed')
    if len(state['receipts']) != len(set(state['receipts'])): raise ValueError('unique_child_evaluation_receipts_required')
    for receipt in state['receipts']:
        if not isinstance(receipt, str) or not re.fullmatch(r'[a-f0-9]{64}', receipt): raise ValueError('owned_child_receipt_hash_required')
        path = output / 'receipts' / (receipt + '.json'); record = read_json(path)
        if record.get('sha256') != receipt or digest({k: v for k, v in record.items() if k != 'sha256'}) != receipt:
            raise ValueError('child_evaluation_receipt_changed')
    actual_calls = sum(episodes.status(output / case['name'] / 'state')['episode_usage']['model_calls'] for case in manifest['cases'])
    if actual_calls != state['calls'] or not 0 <= actual_calls <= manifest['limits']['total_model_calls']:
        raise ValueError('child_evaluation_call_accounting_changed')
    return manifest, state


def _accept_and_consume(root: Path, candidate_id: str, workspace: Path, *, workflow: bool = False) -> dict[str, Any]:
    candidate = records.read(root, 'child_candidates', candidate_id)
    resolutions=None
    if workflow:
        from .child_workflow_tasks import acceptance
        resolutions=acceptance(root,candidate)
    candidates.review(root, candidate_id, decision='approve', reviewer='Frozen independent structural evaluator',
                      authority_reference='Isolated evaluation acceptance contract; no live authority',
                      method_decision='approve' if candidate['assessment'].get('method_assessment',{}).get('eligible_for_independent_adoption') else 'defer',
                      finding_resolutions=resolutions)
    frozen = candidate['frozen']
    delivery = candidates.delivery(root, frozen['directive_id'], consumer='evaluation_support_context', persist=True)
    source = root / 'conveyor/campaigns' / frozen['directive_id'] / 'drafts'
    shutil.copytree(source, workspace)
    from .conveyor_child import _write_resident_artifact
    metrics = _write_resident_artifact(checkout={'directive_id': frozen['directive_id'], 'reviewed_child_artifact_revisions': delivery},
        workspace=workspace, target_artifact=Path(frozen['target_artifact']).name, work_order={})
    receipt = metrics.get('reviewed_child_revision_consumed', {})
    # Disjoint accepted batches can share one composed delivery. Verify its
    # kernel manifest and ownership, not the hash of a candidate in isolation.
    owned_delivery = [row for row in delivery if candidate_id in
        [part['candidate_id'] for part in row.get('parts', [row])]]
    if (len(owned_delivery) != 1 or receipt.get('artifact_sha256') != owned_delivery[0]['artifact_sha256']
            or candidate_id not in receipt.get('candidate_ids', [receipt.get('candidate_id')])
            or not receipt.get('changed')):
        raise ValueError('reviewed_artifact_not_consumed_by_child')
    from .child_delivery import record_use
    record_use(root, frozen['directive_id'], receipt, workspace=workspace, consumer='evaluation_resident_child',
        checkout={'directive_id': frozen['directive_id'], 'reviewed_child_artifact_revisions': delivery})
    return receipt


def step(output: Path, *, planner=None) -> dict[str, Any]:
    with runtime.research_lease(output) as owned:
        if not owned: raise ValueError('child_evaluation_busy')
        manifest, state = load(output); cases = manifest['cases']; selected = None
        for offset in range(len(cases)):
            index = (state['next_index'] + offset) % len(cases); case = cases[index]
            progress = read_json(output / case['name'] / 'progress.json')
            if progress['phase'] != 'complete': selected = (index, case, progress); break
        if selected is None: return summary(output)
        index, case, progress = selected; base = output / case['name']; root = base / 'state'; phase = progress['phase']
        if phase == 'reuse' and progress['train_process'] == PROCESS: raise ValueError('new_process_required_for_child_transfer')
        if state['calls'] >= manifest['limits']['total_model_calls']: raise ValueError('frozen_child_call_limit')
        if phase == 'reuse' and not progress.get('reuse_episode_id'):
            original = records.read(root, 'learning_episodes', case['train_episode_id'])
            episode = practice.admit(root, case['inputs']['reuse'], now=max(time.time(), original['admitted_at'] + 7200))
            progress.update(episode_id=episode['id'], reuse_episode_id=episode['id'])
        task_path = root / 'research_methods/episode_tasks' / (progress['episode_id'] + '.json'); task = read_json(task_path)
        if planner is None:
            from .llm_interface import configured_ollama_model
            if configured_ollama_model() != manifest['model']: raise ValueError('frozen_child_evaluation_provider_changed')
            planner = runtime.local_planner(dataclasses.replace(runtime.load_policy(root), enabled=True,
                max_output_tokens=1800, model_timeout_seconds=manifest['limits']['provider_seconds']))
        state['inflight'] = {'case': case['name'], 'phase': phase, 'reserved_calls': 1,
                             'reserved_seconds': manifest['limits']['provider_seconds']}
        _save(output, state); started = time.monotonic()
        # Both arms use the production function. Only memory visibility differs.
        before_calls = task['model_calls']
        seed_methods=[s['method'] for s in manifest.get('live_method_seeds',[]) if s['method']['adapter']==case['adapter']]
        visible=[] if case['arm'].startswith('without_memory') else [*seed_methods,*candidates.methods(root)]
        with patch.object(candidates, 'methods', return_value=visible):
            result = practice.advance(root, task, planner=planner)
        new_calls = result['model_calls'] - before_calls; state['calls'] += new_calls; progress['calls'] += new_calls
        passed = False; consumption = {}; error = None; correction_queued=False
        if result.get('candidate_id'):
            try:
                findings=[]
                if manifest.get('correction'):
                    from .child_workflow_tasks import judge
                    findings=judge(records.read(root,'child_candidates',result['candidate_id']))
                if findings and result['model_calls']<2:
                    from .child_review import return_for_correction
                    candidates.review(root,result['candidate_id'],decision='revise',reviewer='Frozen independent question checker',
                        authority_reference='Return actionable counterexamples within the original unused budget.',findings=findings)
                    return_for_correction(root,result['candidate_id']);correction_queued=True
                    error='independent_counterexample_correction_queued'
                else:
                    consumption = _accept_and_consume(root, result['candidate_id'], base / (phase + '-child-workspace'),workflow=manifest.get('workflow',False))
                    passed = True
            except (ValueError, KeyError, OSError) as exc: error = str(exc)
        receipt = {'case': case['name'], 'phase': phase, 'process': PROCESS, 'calls': new_calls,
            'result': result, 'accepted_artifact_and_consumed': passed, 'consumption': consumption, 'error': error,
            'elapsed_seconds': time.monotonic() - started, 'usage': episodes.status(root)['episode_usage']}
        if manifest.get('correction'):
            receipt['independent_correction_queued']=correction_queued
            own_failure=bool(new_calls and not passed and (error or result.get('feedback',{}).get('field_issues')
                or result.get('feedback',{}).get('method_assessment',{}).get('field_issues')
                or result.get('feedback',{}).get('reason','').startswith('Expecting')))
            receipt['corrected_own_attempt']=bool(passed and progress.get(phase+'_own_failure'))
            progress[phase+'_own_failure']=bool(progress.get(phase+'_own_failure') or own_failure)
            progress[phase+'_self_corrected']=bool(progress.get(phase+'_self_corrected') or receipt['corrected_own_attempt'])
        if result.get('candidate_id'):
            authored=records.read(root,'child_candidates',result['candidate_id'])
            receipt['original_citation_verifier_passed']=authored['assessment'].get('citation_replay',{}).get('original_verifier_passed',False)
        receipt['support_research_success_demonstrated']=False
        if task.get('attempt_ids') or result.get('attempt_ids'):
            last_attempt = records.read(root, 'attempts', result['attempt_ids'][-1])
            receipt['phase_measurements'] = last_attempt.get('provider_metadata', {})
            receipt['context_choice'] = last_attempt.get('context_choice', {})
        receipt['method_adopted_for_retrieval'] = any(m['id'] == result.get('candidate_id') for m in candidates.methods(root))
        if manifest['version'] in {'child_learning_cycle_v7', 'child_learning_cycle_v8'}:
            selected=result.get('previous_response',{}).get('lesson_id')
            use=result.get('previous_response',{}).get('lesson_use')
            receipt['live_seed_method_reused']=bool(passed and PROCESS!=manifest['prepared_process']
                and selected in {m['id'] for m in seed_methods} and use in {'apply','adapt'}
                and case['arm']=='with_memory' and receipt['method_adopted_for_retrieval'])
            if manifest.get('retention_contract') and receipt['live_seed_method_reused']:
                seed=next(m for m in seed_methods if m['id']==selected)
                actual=result.get('previous_response',{}).get('method',{})
                receipt['live_seed_method_reused']=all(actual.get(k)==seed.get(k) for k in ('representation','adapter','bindings','steps','stop_conditions'))
            receipt['selected_live_seed_id']=selected if selected in {m['id'] for m in seed_methods} else None
            progress[phase+'_live_seed_reused']=receipt['live_seed_method_reused']
        receipt['sha256'] = digest(receipt); write_json(output / 'receipts' / (receipt['sha256'] + '.json'), receipt)
        state['receipts'].append(receipt['sha256']); progress['receipt_ids'].append(receipt['sha256'])
        if phase == 'train':
            progress['train_process'] = PROCESS
            if not correction_queued and (passed or result['state'] != 'ready' or result['model_calls'] >= 2):
                progress.update(phase='reuse', train_passed=passed, training_candidate_id=result.get('candidate_id'),
                    training_method_adopted=receipt['method_adopted_for_retrieval'])
        elif not correction_queued and (passed or result['state'] != 'ready' or result['model_calls'] >= manifest['limits']['fresh_task_calls']):
            selected_lesson = result.get('previous_response', {}).get('lesson_id')
            use = result.get('previous_response', {}).get('lesson_use')
            progress.update(phase='complete', reuse_passed=passed, restart_process_verified=PROCESS != progress['train_process'],
                verified_reuse=bool(passed and progress['train_passed'] and progress.get('training_method_adopted', True)
                                    and receipt['method_adopted_for_retrieval'] and selected_lesson == progress.get('training_candidate_id')
                                    and use in ('apply', 'adapt') and case['arm'].startswith('with_memory')))
        write_json(base / 'progress.json', progress)
        state.update(inflight=None, next_index=(index + 1) % len(cases)); _save(output, state)
        return summary(output)


def summary(output: Path) -> dict[str, Any]:
    manifest, state = load(output)
    rows = [{'case': case['name'], **read_json(output / case['name'] / 'progress.json'),
             'usage': episodes.status(output / case['name'] / 'state')['episode_usage']} for case in manifest['cases']]
    profiles={case['name']:('focused' if manifest.get('correction') or case['arm'].endswith('_focused') else 'full') for case in manifest['cases']}
    return {'version': manifest['version'], 'complete': all(r['phase'] == 'complete' for r in rows),
        'calls': state['calls'], 'limits': manifest['limits'], 'cases': rows,
        'accepted_and_consumed_training': sum(r['train_passed'] for r in rows),
        'fresh_task_success': {arm: sum(r['reuse_passed'] for r in rows if r['case'].split('/')[1] == arm) for arm in dict.fromkeys(c['arm'] for c in manifest['cases'])},
        'profile_costs': {profile: {'model_calls': sum(r['usage']['model_calls'] for r in rows if profiles[r['case']]==profile),
            'compute_seconds': round(sum(r['usage']['compute_seconds'] for r in rows if profiles[r['case']]==profile),4)} for profile in ('full','focused')},
        'verified_reuse_after_restart': sum(r['verified_reuse'] for r in rows),
        **({'live_seed_reuse_by_arm':{arm:sum(bool(r.get(p+'_live_seed_reused')) for r in rows if r['case'].endswith('/'+arm) for p in ('train','reuse')) for arm in ARMS},
            'frozen_live_seed_ids':[s['method']['id'] for s in manifest.get('live_method_seeds',[])]} if manifest['version']=='child_learning_cycle_v7' else {}),
        **({'corrected_own_attempts':sum(bool(r.get(p+'_self_corrected')) for r in rows for p in ('train','reuse')),
            'correction_then_verified_reuse':sum(bool(r.get('train_self_corrected') and r['verified_reuse']) for r in rows)} if manifest.get('correction') else {}),
        'comparative_learning': comparative(rows),
        'scientific_progress_credited': False, 'broader_research_improvement': 'unproven'}


def comparative(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Predeclared conjunction: correction, consumption, method adoption and reuse.

    Report every pair and require every tested domain to improve. Even this
    finite-suite result is not evidence of sustained or general improvement.
    """
    pairs = []
    for domain in sorted({r['case'].split('/')[0] for r in rows}):
        memory = next(r for r in rows if r['case'] == domain + '/with_memory')
        control = next(r for r in rows if r['case'] == domain + '/without_memory')
        complete = memory['phase'] == control['phase'] == 'complete'
        cycle = bool(memory.get('train_self_corrected') and memory.get('train_passed') and
                     memory.get('training_method_adopted') and memory.get('verified_reuse') and memory.get('restart_process_verified'))
        pairs.append({'domain': domain, 'complete': complete, 'memory_complete_learning_cycle': cycle,
                      'memory_fresh_success': bool(memory.get('reuse_passed')), 'control_fresh_success': bool(control.get('reuse_passed')),
                      'strict_learning_advantage': bool(complete and cycle and not control.get('reuse_passed'))})
    return {'pairs': pairs, 'equal_budget_control_required': True,
            'complete_learning_cycles': sum(p['memory_complete_learning_cycle'] for p in pairs),
            'suite_advantage': bool(pairs and all(p['strict_learning_advantage'] for p in pairs)),
            'sustained_advantage': 'unproven', 'scope': 'frozen_tasks_only_no_scientific_or_general_growth_credit'}

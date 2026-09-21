"""Frozen question -> independent review -> practice -> restart transfer trial.

Question review is explicit and cannot be granted by the authoring planner.
Every step starts a new process; only method retrieval differs between paired arms.
"""
from __future__ import annotations

import dataclasses
import hashlib
import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

from . import child_directive_eval as child_eval, child_directive_learning as child
from . import directive_candidates as candidates, learning_episodes as episodes
from . import next_practice as questions, research_procedures as records, research_runtime as runtime
from .research_tools import digest, read_json, write_json

PROCESS = uuid.uuid4().hex
VERSION = 'successor_learning_cycle_v1'


def fingerprint() -> dict[str, str]:
    base = Path(__file__).parent
    return {**child_eval.fingerprint(), **{name: hashlib.sha256((base / name).read_bytes()).hexdigest()
        for name in ('successor_cycle_eval.py', 'successor_evidence.py', 'followup_cycle_eval.py')}}


def save(path: Path, body: dict[str, Any]) -> None:
    body = {k: v for k, v in body.items() if k != 'sha256'}
    write_json(path, {**body, 'sha256': digest(body)})


def checked(path: Path) -> dict[str, Any]:
    row = read_json(path)
    if not row or row.get('sha256') != digest({k: v for k, v in row.items() if k != 'sha256'}):
        raise ValueError('successor_evaluation_integrity_failure')
    return row


def trees(output: Path) -> dict[str, str]:
    return {a + '/' + arm: digest({p.relative_to(output / a / arm).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((output / a / arm).rglob('*')) if p.is_file() and p.suffix in {'.json', '.md'}})
        for a in ('record_extraction', 'evidence_binding') for arm in child_eval.ARMS}


def save_state(output: Path, state: dict[str, Any]) -> None:
    save(output / 'evaluation.json', {**state, 'case_trees': trees(output)})


def prepare(output: Path, *, model: str, provider_seconds: int = 120, structured_experiments: bool = False, semantic_experiments: bool = False, compact_methods: bool = False, repairable_questions: bool = False, context_pressure: bool = False, focused_corrections: bool = False, executable_measurements: bool = False, diagnosed_corrections: bool = False, followup_histories: dict[str, Any] | None = None) -> dict[str, Any]:
    if repairable_questions and not compact_methods or context_pressure and not repairable_questions: raise ValueError('repairable_compact_trial_required')
    if compact_methods and not semantic_experiments: raise ValueError("compact_methods_require_semantic_trial")
    if semantic_experiments and not structured_experiments: raise ValueError("structured_semantic_trial_required")
    if output.exists(): raise ValueError('fresh_successor_evaluation_directory_required')
    if type(provider_seconds) is not int or not 30 <= provider_seconds <= 120:
        raise ValueError('bounded_provider_seconds_required')
    cases = []
    for adapter in ('record_extraction', 'evidence_binding'):
        for arm in child_eval.ARMS:
            name = adapter + '/' + arm; root = output / name / 'state'
            write_json(root / 'autonomy/status.json', {'active': True, 'emergency_stop': False})
            episodes.configure(root, enabled=True, admission_interval_seconds=7200,
                authority_reference='Frozen isolated successor trial funding; no live allowance',
                limits={**episodes.DEFAULT_LIMITS, 'max_episodes_per_day': 12,
                    'model_calls_per_week': 168, 'tool_calls_per_week': 2184, 'compute_seconds_per_week': 23520})
            child.configure(root, directive_ids=['directive-train', 'directive-reuse'], enabled=True,
                authority_reference='Frozen isolated successor trial scope', enable_repairs=True,
                context_profiles=('focused',), enable_research_tools=True, enable_growth=True,
                enable_correction=True, enable_relevance=True, enable_procedure_execution=structured_experiments)
            questions.configure(root, enabled=True, authority_reference='Frozen isolated successor authoring scope',
                structured_experiments=structured_experiments, enable_partitions=structured_experiments,
                enable_failure_followups=structured_experiments, semantic_experiments=semantic_experiments,compact_methods=compact_methods,repairable_questions=repairable_questions,focused_corrections=focused_corrections,executable_measurements=executable_measurements,diagnosed_corrections=diagnosed_corrections)
            inputs = {phase: child_eval._case(root, adapter, phase, growth=True) for phase in ('train', 'reuse')}
            choices = [r for r in questions.catalog(root) if r['frozen']['directive_id'] == 'directive-train'
                       and r['obligation']['adapter'] == adapter]
            if not choices: raise ValueError('frozen_question_opportunity_required')
            if context_pressure:
                for choice in choices:
                    choice['reviewed_failures']=[{'id':'diagnostic-'+str(i),'code':'output_exhausted' if i%2 else 'preparation_context_exceeded',
                        'observation':'A historical attempt exceeded its bounded resource reservation. This supports testing a changed approach, not assuming it works.',
                        'measurements':[{'context_utf8_bytes':4200+i*100,'output_token_limit':650,'eval_count':300,'phases_seconds':{'provider_prompt_seconds':18.0}} for _ in range(3)],
                        'scope':'historical_failure_mechanism_only_no_task_answers','review_id':'independent-frozen-pressure-fixture'} for i in range(4)]
            if followup_histories:
                from .followup_cycle_eval import install
                source=install(root,followup_histories,adapter)
                choices=[source];inputs['train']=source['frozen']
                child.configure(root,directive_ids=[source['frozen']['directive_id'],'directive-reuse'],enabled=True,
                    authority_reference='Frozen reviewed follow-up trial; no live authority',enable_repairs=True,
                    context_profiles=('focused',),enable_research_tools=True,enable_growth=True,
                    enable_correction=True,enable_relevance=True,enable_procedure_execution=True)
            # Freeze the evaluator's domain scope; all selection/authoring is production code.
            with patch.object(questions, 'catalog', return_value=choices): task = questions.admit(root)
            if task is None:raise ValueError('followup_admission_reservation_failed')
            case = {'name': name, 'adapter': adapter, 'arm': arm, 'inputs': inputs,
                    'question_episode_id': task['learning_episode_id'], 'question_choices_sha256': digest(questions.visible(choices))}
            cases.append(case)
            save(output / name / 'progress.json', {'phase': 'question', 'episode_id': task['learning_episode_id'],
                'question_passed': False, 'question_self_corrected': False, 'train_passed': False,
                'reuse_passed': False, 'verified_reuse': False, 'calls': 0, 'receipt_ids': [], 'processes': []})
    manifest = {'version': VERSION, 'model': model, 'fingerprint': fingerprint(), 'cases': cases,
        'followup_history_sha256':followup_histories['sha256'] if followup_histories else None,
        'semantic_revision_track': semantic_experiments, 'compact_methods':compact_methods, 'repairable_questions':repairable_questions, 'context_pressure':context_pressure, 'focused_corrections':focused_corrections,'executable_measurements':executable_measurements,'diagnosed_corrections':diagnosed_corrections,
        'authoring_contract': 'practice_experiment_v2' if structured_experiments else 'legacy_successor_question',
        'limits': {'question_calls': 2, 'training_calls': 2, 'fresh_calls': 2, 'total_calls': 24,
                   'provider_seconds': provider_seconds, 'per_episode_seconds': 280, 'per_episode_checks': 26},
        'acceptance': 'Independent question novelty/applicability/falsifier review, accepted consumed training work, correction of an owned failure and successful selected-method reuse on fresh inputs after restart.',
        'controls': 'Matched source inputs, registered adapter scope, funding and provider; only learned-method retrieval differs.',
        'partition_acceptance': 'A consumed partial batch cannot pass the original obligation; training retains its frozen two-call cap.',
        'prepared_process': PROCESS, 'scientific_progress_credited': False}
    save(output / 'manifest.json', manifest)
    save_state(output, {'calls': 0, 'receipts': [], 'next_index': 0, 'inflight': None})
    return checked(output / 'manifest.json')


def load(output: Path, *, require_current: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest, state = checked(output / 'manifest.json'), checked(output / 'evaluation.json')
    if manifest['version'] != VERSION or require_current and manifest['fingerprint'] != fingerprint():
        raise ValueError('frozen_successor_implementation_required')
    expected = {a + '/' + arm for a in ('record_extraction', 'evidence_binding') for arm in child_eval.ARMS}
    if len(manifest['cases']) != 4 or {c['name'] for c in manifest['cases']} != expected or any(
            c['name'] != c['adapter'] + '/' + c['arm'] for c in manifest['cases']):
        raise ValueError('owned_matched_successor_cases_required')
    for adapter in ('record_extraction', 'evidence_binding'):
        pair = [c for c in manifest['cases'] if c['adapter'] == adapter]
        if len({digest(c['inputs']) for c in pair}) != 1 or len({c['question_choices_sha256'] for c in pair}) != 1:
            raise ValueError('equal_source_and_question_controls_required')
    if state['inflight']: raise ValueError('uncertain_evaluation_step_requires_independent_settlement')
    if len(set(state['receipts'])) != len(state['receipts']): raise ValueError('unique_successor_receipts_required')
    if state.get('case_trees') != trees(output): raise ValueError('successor_saved_state_changed')
    receipts = [checked(output / 'receipts' / (key + '.json')) for key in state['receipts']]
    if sum(r['calls'] for r in receipts) != state['calls'] or state['calls'] > manifest['limits']['total_calls']:
        raise ValueError('successor_evaluation_call_accounting_changed')
    for case in manifest['cases']:
        base = output / case['name']; root = base / 'state'; progress = checked(base / 'progress.json')
        owned = [r for r in receipts if r['case'] == case['name']]
        if progress['receipt_ids'] != [r['sha256'] for r in owned]: raise ValueError('owned_successor_receipts_required')
        if sum(r['calls'] for r in owned) != episodes.status(root)['episode_usage']['model_calls']:
            raise ValueError('successor_case_accounting_changed')
        for phase, frozen in case['inputs'].items():
            from .directive_obligations import assert_current
            assert_current(root, frozen)
        for receipt in owned:
            for aid in receipt['result'].get('attempt_ids', []):
                records.read(root, 'attempts', aid)
            if receipt.get('consumption'):
                path = base / (receipt['phase'] + '-child-workspace') / receipt['consumption']['target_artifact']
                if hashlib.sha256(path.read_bytes()).hexdigest() != receipt['consumption']['artifact_sha256']:
                    raise ValueError('verified_downstream_artifact_required')
    return manifest, state


def review_question(output: Path, case_name: str, *, decision: str, reviewer: str,
                    novelty: str, applicability: str, findings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    with runtime.research_lease(output) as owned:
        if not owned: raise ValueError('successor_evaluation_busy')
        manifest, state = load(output)
        if case_name not in {c['name'] for c in manifest['cases']}: raise ValueError('owned_case_required')
        base = output / case_name; root = base / 'state'; progress = checked(base / 'progress.json')
        if progress['phase'] != 'question_review': raise ValueError('settled_question_review_required')
        receipt = questions.review(root, progress['question_id'], decision=decision, reviewer=reviewer,
            authority_reference='Frozen isolated successor cycle: explicit independent question review only',
            novelty_evidence=novelty, applicability_evidence=applicability, findings=findings)
        progress.update(question_passed=decision == 'approve', question_review_id=receipt['id'],
                        phase='train_admission' if decision == 'approve' else 'question' if decision == 'revise' else 'complete')
        if decision == 'approve':
            task = read_json(root / 'research_methods/episode_tasks' / (progress['episode_id'] + '.json'))
            progress['question_self_corrected'] = verified_question_correction(root, task)
        if decision == 'revise':
            progress.update(question_own_failure=True, semantic_revision_requested=True)
            progress.pop('question_id', None)
        save(base / 'progress.json', progress)
        save_state(output, state)
        return receipt


def step(output: Path, *, planner=None) -> dict[str, Any]:
    with runtime.research_lease(output) as owned:
        if not owned: raise ValueError('successor_evaluation_busy')
        manifest, state = load(output); cases = manifest['cases']; selected = None
        for offset in range(len(cases)):
            index = (state['next_index'] + offset) % len(cases); case = cases[index]
            progress = checked(output / case['name'] / 'progress.json')
            if progress['phase'] not in {'complete', 'question_review'}: selected = index, case, progress; break
        if selected is None: return summary(output)
        index, case, progress = selected; base = output / case['name']; root = base / 'state'
        if PROCESS in progress['processes']: raise ValueError('new_process_required_for_each_successor_action')
        if progress['phase'] in {'train_admission', 'reuse_admission'}:
            phase = 'train' if progress['phase'] == 'train_admission' else 'reuse'
            frozen = questions.pending(root)[0] if phase == 'train' else case['inputs']['reuse']
            stamp = max(e['admitted_at'] for e in episodes._episodes(root)) + 7200
            episode = child.admit(root, frozen, now=stamp)
            progress.update(phase=phase, episode_id=episode['id'])
        phase = progress['phase']; task = read_json(root / 'research_methods/episode_tasks' / (progress['episode_id'] + '.json'))
        if state['calls'] >= manifest['limits']['total_calls']: raise ValueError('frozen_successor_call_limit')
        if planner is None:
            from .llm_interface import configured_ollama_model
            if configured_ollama_model() != manifest['model']: raise ValueError('frozen_successor_provider_required')
            planner = runtime.local_planner(dataclasses.replace(runtime.load_policy(root), enabled=True,
                model_timeout_seconds=manifest['limits']['provider_seconds'], max_output_tokens=1800))
        state['inflight'] = {'case': case['name'], 'phase': phase, 'reserved_calls': 1, 'reserved_seconds': 140}
        save_state(output, state)
        before = task['model_calls']; passed = False; error = None; consumption = {}; correction_queued = False
        visible = candidates.methods(root) if case['arm'] == 'with_memory' else []
        with patch.object(candidates, 'methods', return_value=visible):
            result = questions.advance(root, task, planner=planner) if phase == 'question' else child.advance(root, task, planner=planner)
        calls = result['model_calls'] - before
        if phase == 'question':
            if result.get('refutation_id'):
                progress['scoped_refutation_id']=result['refutation_id']
            if result.get('question_id'):
                progress.update(phase='question_review', question_id=result['question_id'],
                    question_self_corrected=verified_question_correction(root,result))
            elif result['state'] != 'ready': progress['phase'] = 'complete'
        elif result.get('candidate_id'):
            try:
                from .child_workflow_tasks import judge
                findings = judge(records.read(root, 'child_candidates', result['candidate_id']))
                if findings and result['model_calls'] < 2:
                    from .child_review import return_for_correction
                    candidates.review(root, result['candidate_id'], decision='revise', reviewer='Frozen independent workflow checker',
                        authority_reference='Original-budget correction with independent counterexamples', findings=findings)
                    return_for_correction(root, result['candidate_id']); correction_queued = True
                    error = 'independent_counterexample_correction_queued'
                else:
                    consumption = child_eval._accept_and_consume(root, result['candidate_id'], base / (phase + '-child-workspace'), workflow=True)
                    passed = True
                    if phase == 'train' and progress.get('question_id'):
                        question = records.read(root, 'successor_questions', progress['question_id'])
                        if question['response'].get('field_batches'):
                            from .question_partitions import progress as partition_progress
                            completion = partition_progress(root, question)
                            progress['partition_progress'] = completion
                            passed = completion['original_obligation_complete']
                            if not passed: error = 'partial_batch_consumed_original_obligation_incomplete'
            except (ValueError, KeyError, OSError) as exc: error = str(exc)
        adopted = any(m['id'] == result.get('candidate_id') for m in candidates.methods(root))
        own_failure = bool(calls and not passed and (error or result.get('feedback', {}).get('field_issues')))
        corrected = bool(passed and progress.get(phase + '_own_failure'))
        progress[phase + '_own_failure'] = bool(progress.get(phase + '_own_failure') or own_failure)
        if phase != 'question':
            progress[phase + '_self_corrected'] = bool(progress.get(phase + '_self_corrected') or corrected)
            if not correction_queued and (passed or result['state'] != 'ready' or result['model_calls'] >= 2):
                progress[phase + '_passed'] = passed
                if phase == 'train':
                    progress.update(phase='reuse_admission', training_candidate_id=result.get('candidate_id'),
                                    training_method_adopted=adopted, train_process=PROCESS)
                else:
                    response = result.get('previous_response', {})
                    progress.update(phase='complete', restart_process_verified=PROCESS != progress.get('train_process'),
                        verified_reuse=bool(passed and progress['train_passed'] and progress.get('training_method_adopted')
                            and adopted and case['arm'] == 'with_memory' and PROCESS != progress.get('train_process')
                            and response.get('lesson_id') == progress.get('training_candidate_id')
                            and response.get('lesson_use') in {'apply', 'adapt'}))
        receipt = {'case': case['name'], 'phase': phase, 'process': PROCESS, 'calls': calls,
            'result': result, 'accepted_artifact_and_consumed': passed, 'consumption': consumption,
            'error': error, 'corrected_own_attempt': corrected, 'method_adopted': adopted,
            'usage': episodes.status(root)['episode_usage']}
        if result.get('attempt_ids'):
            attempt = records.read(root, 'attempts', result['attempt_ids'][-1])
            receipt['phase_measurements'] = attempt.get('provider_metadata', {})
        key = digest(receipt); save(output / 'receipts' / (key + '.json'), receipt)
        state['receipts'].append(key); state['calls'] += calls
        progress['receipt_ids'].append(key); progress['calls'] += calls; progress['processes'].append(PROCESS)
        save(base / 'progress.json', progress)
        state.update(inflight=None, next_index=(index + 1) % len(cases)); save_state(output, state)
        return summary(output)


def verified_question_correction(root: Path, task: dict[str, Any]) -> bool:
    from .question_quality import cosmetic_only
    syntax={'operation_format_requires_prose','terminal_punctuation_required','linked_measurement_review'}
    substantive=lambda findings:any(f.get('original_code',f.get('code')) not in syntax for f in findings)
    attempts=[records.read(root,'attempts',aid) for aid in task.get('attempt_ids',[])]
    if not task.get('question_id') or len(attempts)<2:return False
    pointer=read_json(root/'research_methods/successor_review_latest'/(task['question_id']+'.json'))
    if not pointer or records.read(root,'successor_reviews',pointer['review_id'])['decision']!='approve':return False
    final=attempts[-1].get('response')
    if task.get('semantic_revision_id'):
        reviewed=records.read(root,'successor_reviews',task['semantic_revision_id'])
        original=records.read(root,'successor_questions',reviewed['question_id'])
        if (reviewed.get('decision')=='revise' and substantive(reviewed.get('findings',[]))
            and reviewed.get('question_sha256')==digest(original)
            and not cosmetic_only(original['response'],final)):return True
    return any(a.get('response') and a.get('provider_dispatched',True)
        and substantive(a.get('feedback',{}).get('field_issues',[])) and not cosmetic_only(a['response'],final)
        for a in attempts[:-1])


def summary(output: Path) -> dict[str, Any]:
    manifest, state = load(output)
    rows = [{'case': c['name'], **checked(output / c['name'] / 'progress.json')} for c in manifest['cases']]
    comparison = child_eval.comparative(rows)
    for pair in comparison['pairs']:
        memory = next(r for r in rows if r['case'] == pair['domain'] + '/with_memory')
        pair['memory_complete_learning_cycle'] &= bool(memory['question_passed'])
        pair['strict_learning_advantage'] &= bool(memory['question_passed'])
    comparison['complete_learning_cycles'] = sum(p['memory_complete_learning_cycle'] for p in comparison['pairs'])
    comparison['suite_advantage'] = all(p['strict_learning_advantage'] for p in comparison['pairs'])
    return {'version': VERSION, 'calls': state['calls'], 'complete': all(r['phase'] == 'complete' for r in rows),
        'scoped_refutations':sum(bool(r.get('scoped_refutation_id')) for r in rows),
        'accepted_question_then_corrected_work_and_reuse': comparison['complete_learning_cycles'],
        'partial_batch_consumption_is_original_completion': False,
        'semantic_question_corrections': sum(bool(r.get('semantic_revision_requested') and r['question_passed'] and r['question_self_corrected']) for r in rows),
        'question_corrections': sum(r['question_self_corrected'] for r in rows),
        'awaiting_question_review': [r['case'] for r in rows if r['phase'] == 'question_review'], 'cases': rows,
        'fresh_success': {arm: sum(r['reuse_passed'] for r in rows if r['case'].endswith('/' + arm)) for arm in child_eval.ARMS},
        'comparative_learning': comparison, 'scientific_progress_credited': False, 'broader_improvement': 'unproven'}


def inspect_archive(output: Path) -> dict[str, Any]:
    manifest, state = load(output, require_current=False)
    patterns = {}; evidence = []
    for case in manifest['cases']:
        progress = checked(output / case['name'] / 'progress.json')
        if progress['phase'] != 'complete': raise ValueError('settled_complete_successor_cycle_required')
    for key in state['receipts']:
        receipt = checked(output / 'receipts' / (key + '.json'))
        result = receipt['result']; root = output / receipt['case'] / 'state'
        for finding in result.get('feedback', {}).get('field_issues', []):
            code = 'successor_' + finding['code']; patterns[code] = patterns.get(code, 0) + 1
        if receipt.get('error'):
            code = 'successor_independent_acceptance_not_met'; patterns[code] = patterns.get(code, 0) + 1
        if result.get('feedback', {}).get('reason') and not receipt['accepted_artifact_and_consumed'] and receipt['phase'] != 'question':
            code = 'successor_task_not_completed'; patterns[code] = patterns.get(code, 0) + 1
        if receipt['accepted_artifact_and_consumed']:
            candidate = records.read(root, 'child_candidates', result['candidate_id'])
            from .child_workflow_tasks import judge
            if candidates.assess(candidate['frozen'], candidate['context'], candidate['response']) != candidate['assessment'] or judge(candidate):
                raise ValueError('independent_successor_acceptance_mismatch')
        evidence.append(key)
    return {'manifest_sha256': manifest['sha256'], 'archive_state_sha256': digest(state),
        'evidence_sha256': digest(evidence), 'historical_implementation': manifest['fingerprint'],
        'calls': state['calls'], 'patterns': patterns,
        'scope': 'observed_successor_failure_patterns_only_no_answers_or_withheld_cases'}

"""Novali-authored successor questions; review and practice spend separate windows."""
from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Any

from . import research_procedures as records, learning_episodes as episodes
from .research_tools import digest, read_json, write_json


def configure(root: Path, *, enabled: bool, authority_reference: str, structured_experiments: bool = False,
              enable_partitions: bool = False, enable_failure_followups: bool = False,
              semantic_experiments: bool = False, compact_methods: bool = False, repairable_questions: bool = False, focused_corrections: bool = False, executable_measurements: bool = False, diagnosed_corrections: bool = False) -> dict[str, Any]:
    if type(diagnosed_corrections) is not bool or diagnosed_corrections and not focused_corrections:
        raise ValueError('diagnosed_corrections_require_focused_corrections')
    if type(executable_measurements) is not bool or executable_measurements and not focused_corrections:
        raise ValueError('executable_measurements_require_focused_corrections')
    if type(focused_corrections) is not bool or focused_corrections and not repairable_questions:
        raise ValueError("focused_corrections_require_repairable_questions")
    if type(repairable_questions) is not bool or repairable_questions and not compact_methods:
        raise ValueError('repairable_questions_require_compact_methods')
    if type(compact_methods) is not bool or compact_methods and not semantic_experiments:
        raise ValueError('operational_methods_require_semantic_experiments')
    if type(semantic_experiments) is not bool or semantic_experiments and not (structured_experiments and enable_partitions):
        raise ValueError('semantic_experiments_require_structured_partitions')
    if any(type(v) is not bool for v in (enable_partitions, enable_failure_followups)) or (enable_partitions or enable_failure_followups) and not structured_experiments:
        raise ValueError('structured_successor_controls_required')
    if type(enabled) is not bool or type(structured_experiments) is not bool or not 8 <= len(authority_reference) <= 1600:
        raise ValueError('explicit_successor_policy_required')
    configured = records.store(root, 'successor_policies', {'enabled': enabled, 'authority_reference': authority_reference,
        'max_questions_per_basis': 1, 'max_practice_per_question': 12 if enable_partitions else 1,
        'funding': 'existing_shared_learning_windows',
        **({'quality_contract':'operational_question_v1'} if compact_methods else {}),
        **({'repair_contract':'question_repair_v1'} if repairable_questions else {}),
        **({'focus_contract':'question_focus_v1'} if focused_corrections else {}),
        **({'measurement_contract':'question_measurements_v2'} if executable_measurements else {}),
        **({'diagnosis_contract':'question_diagnosis_v1'} if diagnosed_corrections else {}),
        'automatic_approval': False, 'max_catalog_entries': 8,
        **({'semantic_contract':'question_semantics_v1'} if semantic_experiments else {}),
        **({'authoring_contract': 'practice_experiment_v2'} if structured_experiments else {}),
        **({'partition_enabled': True, 'max_batches_per_question': 12} if enable_partitions else {}),
        **({'failure_followups_enabled': True, 'max_failure_followups_per_lineage': 1} if enable_failure_followups else {})})
    write_json(root / 'research_methods/successor_policy.json', {'id': configured['id']})
    return configured


def policy(root: Path) -> dict[str, Any]:
    pointer = read_json(root / 'research_methods/successor_policy.json')
    return records.read(root, 'successor_policies', pointer['id']) if pointer else {}


def objective_key(row: dict[str, Any]) -> str:
    frozen, obligation = row['frozen'], row['obligation']
    return digest([frozen['directive_id'], obligation['id'], obligation.get('unit')])


def selection_blocked(root: Path, choices: list[dict[str, Any]]) -> bool:
    current = {objective_key(r): r['basis_sha256'] for r in choices}
    for episode in episodes._episodes(root):
        if episode.get('selection_contract') != 'successor_selection_v2': continue
        task = read_json(root / 'research_methods/episode_tasks' / (episode['id'] + '.json'))
        if task.get('selected_source_id') or task.get('question_id'): continue
        if task.get('state') == 'ready': return True
        # A failed selection needs changed evidence/source on an original choice.
        # Adding an unrelated menu entry or waiting another day cannot reset it.
        old = episode['frozen_question_choices']
        if not any(objective_key(r) in current and current[objective_key(r)] != r['basis_sha256'] for r in old):
            return True
    return False


def catalog(root: Path) -> list[dict[str, Any]]:
    from . import child_directive_learning as child, successor_evidence
    configured = child.policy(root)
    used, legacy_used = set(), set()
    for episode in episodes._episodes(root):
        if episode.get('family') != 'successor_question': continue
        task = read_json(root / 'research_methods/episode_tasks' / (episode['id'] + '.json'))
        old = episode['frozen_question_choices']
        selected_id = task.get('selected_source_id')
        if task.get('question_id'):
            selected_id = records.read(root, 'successor_questions', task['question_id'])['source']['id']
        selected = [r for r in old if r['id'] == selected_id]
        if episode.get('selection_contract') == 'successor_selection_v2':
            used.update(r['basis_sha256'] for r in selected)
        else:
            # No retroactive restoration of previously spent legacy catalogs.
            legacy_used.update(objective_key(r) for r in (selected or old))
    rows = []
    for source in read_json(root / 'conveyor/research/latest.json').get('directives', []):
        if source.get('directive_id') not in configured.get('directive_ids', []) or not source.get('episode_id'): continue
        try: frozen = child.current(root, source['episode_id'])
        except (ValueError, KeyError, OSError): continue
        for obligation in frozen['obligations']:
            if not obligation.get('adapter') or obligation.get('blocked_reason') in {
                    'verified_artifact_consumed', 'partition_practice_in_progress', 'partition_verified_consumed',
                    'pending_independent_review', 'reviewed_correction_queued'}: continue
            failures = successor_evidence.context(root, obligation['adapter'])
            if not obligation['eligible'] and not failures: continue
            basis = {'directive_id': frozen['directive_id'], 'source': frozen['substantive_source_sha256'],
                     'obligation_id': obligation['id'], 'unit': obligation.get('unit'),
                     'failure_evidence_ids': [r['id'] for r in failures]}
            key = digest(basis)
            row = {'id': 'question-source-' + key[:24], 'basis_sha256': key,
                'frozen': frozen, 'obligation': obligation, 'reviewed_failures': failures,
                'requires_independent_reopening': not obligation['eligible']}
            if key not in used and objective_key(row) not in legacy_used: rows.append(row)
    from .question_failure_learning import pending
    return (pending(root) + rows)[:8]


def visible_failures(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One representative per mechanism; measured failures must not be hidden by duplicates."""
    unique = {}
    for row in rows:
        key = row.get('code') or row['id']
        rank = lambda r: (bool(r.get('measurements')), r.get('observations', 0), r['id'])
        if key not in unique or rank(row) > rank(unique[key]): unique[key] = row
    ordered = sorted(unique.values(), key=lambda r: (-bool(r.get('measurements')), -r.get('observations',0), r.get('code',''), r['id']))
    result = []
    for row in ordered[:6]:
        item = {k:row[k] for k in ('id','adapter','code','observation','observations','review_id','observed_failure_patterns','scope','kind') if k in row}
        if row.get('measurements'):
            item['measurements'] = [{k:v for k,v in m.items() if k in ('provider_dispatched','context_utf8_bytes','output_token_limit','eval_count','done_reason','phases_seconds')}
                for m in row['measurements'][:2]]
            item['additional_measurement_count'] = max(0,len(row['measurements'])-2)
        result.append(item)
    return result


def visible(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from .question_quality import source_states
    return [{'id': r['id'], 'obligation': {k: r['obligation'][k] for k in
             ('id', 'adapter', 'objective', 'target_artifact', 'unit', 'completion_check', 'blocked_reason') if k in r['obligation']},
             'source_states': source_states(r),
             'reviewed_failures': visible_failures(r['reviewed_failures']), 'requires_independent_reopening': r['requires_independent_reopening'],
             **({'failure_followup': r['failure_followup']} if r.get('failure_followup') else {})}
            for r in rows]


def project_context(context: dict[str, Any]) -> dict[str, Any]:
    if context.get('authoring_contract') == 'practice_experiment_v2' and 'failure_evidence_metadata' in context:
        return copy.deepcopy(context)
    result = copy.deepcopy(context); evidence = {}
    if result.get('measurement_contract') and any(r['obligation']['adapter']!='record_extraction' for r in result['choices']):
        result.pop('measurement_contract',None)
    for choice in result['choices']:
        failures = choice.pop('reviewed_failures', [])
        keys = []
        for failure in failures:
            key = failure.get('id') or failure.get('review_id') or digest(failure)
            evidence[key] = failure; keys.append(key)
        choice['failure_evidence_ids'] = keys
    result['failure_evidence'] = evidence
    if context.get('quality_contract'):
        result['bound_evaluators']={r['id']:r['obligation']['completion_check'] for r in result['choices']}
    if context.get('authoring_contract') == 'practice_experiment_v2':
        from .practice_experiments import compact
        result = compact(result)
    if context.get('repair_contract'):
        from .question_repair import project
        result=project(result)
    if context.get('focus_contract'):
        from .question_focus import project
        result=project(result)
    from .question_diagnosis import augment
    return augment(result)


def authoring_menu(rows: list[dict[str, Any]], configured: dict[str, Any]) -> list[dict[str, Any]]:
    """Fit whole opportunities before reservation; unoffered rows remain eligible."""
    if configured.get('authoring_contract') != 'practice_experiment_v2': return rows
    original_rows=rows
    from .child_planning import reserve
    if configured.get('focus_contract') and any(r.get('failure_followup') for r in rows):
        rows=[r for r in rows if r.get('failure_followup')][:1]
    if configured.get('measurement_contract') and rows:
        instrumented=rows[0]['obligation']['adapter']=='record_extraction'
        rows=[r for r in rows if (r['obligation']['adapter']=='record_extraction')==instrumented]
    offered = []
    for row in rows:
        context = project_context({'choices': visible([*offered, row]), 'authoring_contract': configured['authoring_contract'],
            'partition_enabled': configured.get('partition_enabled', False),
            'semantic_contract': configured.get('semantic_contract'),
            'quality_contract': configured.get('quality_contract'),
            'repair_contract': configured.get('repair_contract'),
        'focus_contract': configured.get('focus_contract'),
        'measurement_contract': configured.get('measurement_contract'),
        'diagnosis_contract': configured.get('diagnosis_contract'),
            'feedback': {}, 'previous_proposal': None, 'selected_source_id': None,
            'remaining_resources': {'model_calls': 2, 'tool_calls': 26, 'compute_seconds': 280.0,
                                    'validation_seconds_reserved': 20}})
        try:
            if context.get('repair_contract'):
                from .question_repair import reserve_cycle
                reserve_cycle(context)
            else:reserve(contract(context)[0], context, 650)
            offered.append(row)
        except ValueError as exc:
            if str(exc) not in {'child_input_plus_output_reservation_exceeded','question_feedback_reservation_exceeded'}: raise
    if not offered:
        selected_ids={r['id'] for r in rows}
        remaining=[r for r in original_rows if r['id'] not in selected_ids]
        if remaining:return authoring_menu(remaining,configured)
    return offered


def resume_preparation(root: Path, episode_id: str, *, planner, reviewer: str, evidence_reference: str) -> dict[str, Any]:
    """Independent, once-only repair of a zero-dispatch preparation failure."""
    if any(not isinstance(v, str) or not 16 <= len(v) <= 1600 for v in (reviewer, evidence_reference)):
        raise ValueError('independent_preparation_repair_evidence_required')
    episode = records.read(root, 'learning_episodes', episode_id)
    task_path = root / 'research_methods/episode_tasks' / (episode_id + '.json')
    account_path = root / 'research_methods/episode_accounts' / (episode_id + '.json')
    task, account = read_json(task_path), read_json(account_path)
    if task.get('model_calls',0)>0:
        from .question_repair import recover
        return recover(root,episode_id,planner=planner,reviewer=reviewer,evidence_reference=evidence_reference)
    history = [records.read(root, 'successor_preparation_repairs', p.stem)
               for p in (root / 'research_methods/successor_preparation_repairs').glob('*.json')]
    history = [r for r in history if r['episode_id'] == episode_id]
    previous = records.read(root, 'successor_preparation_repairs', task['preparation_repair_id']) if task.get('preparation_repair_id') else None
    compatibility_recheck = bool(previous and len(history) == 1 and previous['implementation'] != records.implementation()
        and task.get('state') == 'awaiting_review' and task.get('feedback', {}).get('reason') == 'learning_episode_policy_or_implementation_changed'
        and previous['attempt_ids'] == task.get('attempt_ids'))
    if history and not compatibility_recheck:
        raise ValueError('settled_unused_preparation_reservation_required')
    if (episode.get('family') != 'successor_question' or task.get('state') != 'exhausted_no_candidate' and not compatibility_recheck
            or task.get('preparation_repair_id') and not compatibility_recheck or account.get('inflight')
            or task.get('model_calls') != 0 or account.get('usage', {}).get('model_calls') != 0
            or task.get('question_id') or not task.get('attempt_ids')):
        raise ValueError('settled_unused_preparation_reservation_required')
    attempts = [records.read(root, 'attempts', aid) for aid in task['attempt_ids']]
    if any(a.get('provider_dispatched') is not False or a.get('response') is not None
           or 'child_input_plus_output_reservation_exceeded' not in a.get('feedback', {}).get('reason', '') for a in attempts):
        raise ValueError('verified_local_context_preparation_failure_required')
    configured = policy(root)
    if configured.get('id') != episode['successor_policy_id'] or not configured.get('enabled'):
        raise ValueError('current_successor_policy_required')
    from .directive_obligations import assert_current
    from .lesson_review_budget import charge
    for choice in episode['frozen_question_choices']: assert_current(root, choice['frozen'])
    if not callable(getattr(planner, 'preflight', None)): raise ValueError('production_preflight_required')
    with charge(root, episode):
        context = project_context({'choices': visible(episode['frozen_question_choices']), 'feedback': task['feedback'],
            'previous_proposal': None, 'remaining_resources': {'model_calls': 2, 'validation_seconds_reserved': 20}})
        planner.preflight('successor_question', context)
        review_record = records.store(root, 'successor_preparation_repairs', {'episode_id': episode_id,
            'task_before_sha256': digest(task), 'account_before_sha256': digest(account),
            'previous_review_id': previous['id'] if previous else None,
            'attempt_ids': task['attempt_ids'], 'implementation': records.implementation(),
            'projected_context_sha256': digest(context), 'reviewer': reviewer, 'evidence_reference': evidence_reference,
            'scientific_allowance_added': 0, 'funding': 'existing_unused_reservation_only'})
    task.update(state='ready', preparation_repair_id=review_record['id'],
                feedback={'reason': 'independently_verified_context_repair', 'costs_retained': True})
    write_json(task_path, task)
    return review_record


def preparation_compatible(root: Path, episode: dict[str, Any], task: dict[str, Any]) -> bool:
    if episode.get('family') != 'successor_question' or not task.get('preparation_repair_id'): return False
    review_record = records.read(root, 'successor_preparation_repairs', task['preparation_repair_id'])
    if review_record.get('repair_contract'):
        account=read_json(root/'research_methods/episode_accounts'/(episode['id']+'.json'))
        if (review_record.get('successor_policy_id')!=policy(root).get('id') or
            review_record.get('policy_id')!=episode['policy_id'] or review_record.get('reserved')!=episode['reserved'] or
            any(account.get('usage',{}).get(k,-1)<v for k,v in review_record['usage_before'].items())):return False
    return bool(review_record['episode_id'] == episode['id'] and review_record['implementation'] == records.implementation()
        and set(review_record['attempt_ids']) <= set(task.get('attempt_ids', []))
        and review_record.get('scientific_allowance_added') == 0)


def contract(context: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    from . import practice_experiments
    if context.get('authoring_contract') == practice_experiments.VERSION:
        if context.get('focus_contract'):
            from .question_feedback import bounded_schema
            instructions,schema=practice_experiments.contract(context)
            return instructions+' Use ASCII prose; exact sources stay bound by ID.',bounded_schema(schema)
        return practice_experiments.contract(context)
    from .planner_authoring import _object, _string, _enum
    return ('Choose one unresolved obligation or independently observed failure. Author your own distinct practice question, '
        'a substantive changed approach, and a concrete falsifier. Select the exact existing completion check. '
        'Explain how the selected failure mechanism applies to this obligation and what it cannot establish. '
        'Use previous_proposal and every feedback field issue to correct your own result. A selected source is fixed for this episode. '
        'Respect remaining_resources and preserve complete short explanations. Do not supply answers or claim success. '
        'Independent review is required before a separately funded practice window; this proposal grants no retry or allowance.',
        _object({'source_id': _enum([r['id'] for r in context['choices']]), 'objective': _string(16, 240),
                 'changed_approach': _string(16, 320), 'falsifier': _string(16, 240), 'evidence_applicability': _string(16, 240),
                 'completion_check': _enum(list(dict.fromkeys(r['obligation']['completion_check'] for r in context['choices'])))}))


class QuestionValidationError(ValueError):
    def __init__(self, findings: list[dict[str, Any]]):
        self.findings = findings
        super().__init__(';'.join(f["path"] + ':' + f["code"] for f in findings))


def check(rows: list[dict[str, Any]], response: Any, *, authoring_contract: str | None = None,
          partition_enabled: bool = False, measurement_contract: str | None = None) -> dict[str, Any]:
    from . import practice_experiments
    if isinstance(response,dict) and 'measurement' in response and not measurement_contract:
        raise QuestionValidationError([{'path':'/measurement','code':'executable_measurement_required',
            'guidance':'This task has no registered measurement instrument; do not bypass its method checks.'}])
    if authoring_contract == practice_experiments.VERSION:
        if partition_enabled and isinstance(response, dict) and 'field_batches' not in response:
            raise practice_experiments.InvalidExperiment([{'path':'/field_batches','code':'required_field_missing',
                'guidance':'Use [] for the full obligation or a complete disjoint partition.'}])
        return practice_experiments.check(rows, response)
    schema = contract({'choices': visible(rows)})[1]
    findings = []
    def issue(path, code, **details): findings.append({'path': path, 'code': code, **details})
    if not isinstance(response, dict):
        raise QuestionValidationError([{'path': '/', 'code': 'typed_successor_question_required'}])
    for key in sorted(set(response) - set(schema['properties'])):
        issue('/' + key, 'unexpected_field')
    for key, rule in schema['properties'].items():
        value = response.get(key)
        if key not in response: issue('/' + key, 'required_field_missing'); continue
        if not isinstance(value, str): issue('/' + key, 'string_required'); continue
        if not rule.get('minLength', 1) <= len(value) <= rule.get('maxLength', 2000):
            issue('/' + key, 'bounded_text_required', actual_length=len(value),
                  min_length=rule.get('minLength', 1), max_length=rule.get('maxLength', 2000))
        if 'enum' in rule and value not in rule['enum']:
            issue('/' + key, 'invalid_reference', permitted=rule['enum'])
    source = next((r for r in rows if r['id'] == response.get('source_id')), None)
    if source:
        if response.get('completion_check') != source['obligation']['completion_check']:
            issue('/completion_check', 'completion_check_must_match_selected_obligation', expected=source['obligation']['completion_check'])
        normalized = lambda v: ' '.join(v.lower().split()).strip(' .!?') if isinstance(v, str) else None
        prose = [normalized(response.get(k)) for k in ('objective', 'changed_approach', 'falsifier')]
        if all(prose) and (len(set(prose)) != 3 or prose[0] == normalized(source['obligation']['objective'])):
            issue('/objective', 'distinct_question_approach_and_falsifier_required')
    if findings: raise QuestionValidationError(findings)
    return source


def admit(root: Path, *, now: float | None = None) -> dict[str, Any] | None:
    configured = policy(root); shared = episodes.policy(root)
    autonomy = read_json(root / 'autonomy/status.json')
    if not configured.get('enabled') or not shared.get('enabled') or not autonomy.get('active') or autonomy.get('emergency_stop'):
        return None
    stamp, earliest = episodes.admission_window(root, shared, now=now)
    if stamp < earliest:
        return None
    choices = catalog(root)
    if not choices or selection_blocked(root, choices):
        return None
    followups = [r for r in choices if r.get('failure_followup')]
    if followups: choices = followups[:1]
    choices = authoring_menu(choices, configured)
    if not choices: return None
    # One offered catalog gets one bounded authoring episode; failed calls do
    # not remove the tried-basis record. No fresh attempt by rewording the task.
    failure = records.store(root, 'failures', {'failure_family': 'successor_question',
        'failure': 'unresolved_obligations_or_reviewed_failures', 'parent_id': choices[0]['id'],
        'parent_contract_sha256': digest(visible(choices)), 'usage_before': {}, 'failed_command': {}})
    episode = records.store(root, 'learning_episodes', {'family': 'successor_question', 'failure_id': failure['id'],
        'selection_contract': 'successor_selection_v2', 'authoring_contract': configured.get('authoring_contract'),
        'partition_enabled': configured.get('partition_enabled', False),
        'semantic_contract': configured.get('semantic_contract'),
            'quality_contract': configured.get('quality_contract'),
        'repair_contract': configured.get('repair_contract'),
        'focus_contract': configured.get('focus_contract'),
        'measurement_contract': configured.get('measurement_contract'),
        'diagnosis_contract': configured.get('diagnosis_contract'),
        'failure_followup_review_ids': [r['failure_followup']['review_id'] for r in choices if r.get('failure_followup')],
        'failure_key': digest(visible(choices)), 'successor_basis': choices[0]['basis_sha256'],
        'offered_successor_bases': [r['basis_sha256'] for r in choices], 'successor_policy_id': configured['id'],
        'frozen_question_choices': choices, 'implementation': records.implementation(), 'policy_id': shared['id'],
        'admitted_at': stamp, 'reserved': {k: shared['limits']['episode_' + k] for k in ('model_calls', 'tool_calls', 'compute_seconds')},
        'validation_reserved_before_provider': True, 'scientific_allowance_added': 0})
    task = {'learning_episode_id': episode['id'], 'failure_id': failure['id'], 'state': 'ready',
            'model_calls': 0, 'attempt_ids': [], 'feedback': {}, 'grants_execution_authority': False}
    write_json(root / 'research_methods/episode_tasks' / (episode['id'] + '.json'), task)
    return task


def advance(root: Path, task: dict[str, Any], *, planner) -> dict[str, Any]:
    from . import practice_transaction as transaction
    from .action_budget import ActionBudget
    task_path = root / 'research_methods/episode_tasks' / (task['learning_episode_id'] + '.json')
    account_path = root / 'research_methods/episode_accounts' / task_path.name
    if transaction.recover(root, task_path, account_path):
        task = read_json(task_path)
    task = read_json(task_path)
    if task.get('state') != 'ready': raise ValueError('ready_owned_question_required')
    account = read_json(account_path)
    if account.get('inflight'):
        account['usage']['compute_seconds'] += account['inflight']['reserved_seconds']
        account['inflight'] = None
        task.update(state='exhausted_no_candidate', model_calls=account['usage']['model_calls'], feedback={'reason': 'uncertain_successor_attempt_retained'})
        write_json(account_path, account); write_json(task_path, task)
        return task
    limits, account, account_path, task_path = episodes.practice_budget(root, task)
    episode = records.read(root, 'learning_episodes', task['learning_episode_id'])
    configured = policy(root); autonomy = read_json(root / 'autonomy/status.json')
    from .question_revision import compatible as revision_compatible
    if (configured.get('id') != episode['successor_policy_id'] and not revision_compatible(root, episode, task) and not preparation_compatible(root,episode,task)) or not configured.get('enabled') or not autonomy.get('active') or autonomy.get('emergency_stop'):
        raise ValueError('successor_controls_blocked')
    remaining = limits['max_compute_seconds'] - account['usage']['compute_seconds']
    if task['model_calls'] >= limits['max_model_calls'] or remaining <= 21 or account['usage']['tool_calls'] + 4 > limits['max_tool_calls']:
        task.update(state='exhausted_no_candidate'); write_json(task_path, task); return task
    budget = ActionBudget(min(140, remaining), reserve_seconds=20)
    choices = episode['frozen_question_choices']
    if task.get('selected_source_id'): choices=[r for r in choices if r['id']==task['selected_source_id']]
    context=retry_context(root,episode,task,account)
    prior=context.get('previous_proposal')
    if prior is None and episode.get('focus_contract'):
        prior=next((s['failure_followup'].get('previous_proposal') for s in choices if s.get('failure_followup')),None)
    context['provider_time_budget_seconds']=min(120,budget.provider_seconds())
    from .question_diagnosis import VerifiedRefutation
    started = time.monotonic(); dispatched = False; response = None; submitted = None; changes = []; measurement_result = None
    old_hook = getattr(planner, 'dispatch_hook', None)
    account['inflight'] = {'phase': 'preparing', 'reserved_seconds': min(140, remaining)}
    write_json(account_path, account)
    def dispatch():
        nonlocal dispatched
        if dispatched: return
        dispatched = True; account['usage']['model_calls'] += 1
        account['inflight']['phase'] = 'dispatched'; write_json(account_path, account)
    try:
        from .directive_obligations import assert_current
        for choice in choices: assert_current(root, choice['frozen'])
        context = project_context(context)
        if callable(getattr(planner, 'preflight', None)): planner.preflight('successor_question', context)
        planner.dispatch_hook = dispatch
        if not getattr(planner, 'supports_dispatch_hook', False): dispatch()
        submitted = planner('successor_question', context)
        response = submitted
        dispatch()  # Returned output proves a call even for a provider lacking hooks.
        account['usage']['tool_calls'] += 2
        from . import practice_experiments
        from .question_diagnosis import refute
        if context.get('diagnosis_contract') and isinstance(submitted,dict) and submitted.get('decision')=='refute':
            refute(context, choices, submitted)
        if episode.get('authoring_contract') == practice_experiments.VERSION:
            response = prior  # A rejected patch never replaces its canonical baseline.
            response, changes = practice_experiments.resolve(context, submitted)
        if context.get('quality_contract') and isinstance(response,dict):
            from .question_quality import derive
            response=derive(response)
        if context.get('measurement_contract') and isinstance(response,dict):
            from .question_measurements import derive as derive_measurement
            response=derive_measurement(response, contract=context.get('measurement_contract'))
        if context.get('semantic_contract') and isinstance(response, dict):
            from .question_semantics import resolve as resolve_semantics
            response = resolve_semantics(context, response)
        selected = next((r for r in choices if isinstance(response, dict) and r['id'] == response.get('source_id')), None)
        if selected:
            task['selected_source_id'] = selected['id']
            # Persist ownership even if validation or settlement is interrupted.
            write_json(task_path, task)
        from .question_diagnosis import repair_findings as diagnosis_findings
        issues=diagnosis_findings(context,changes); source=selected
        try:
            source = check(choices,response,authoring_contract=episode.get('authoring_contract'),
                           partition_enabled=episode.get('partition_enabled',False),measurement_contract=context.get('measurement_contract'))
        except (practice_experiments.InvalidExperiment,QuestionValidationError) as exc:
            issues.extend(exc.findings)
        if source and isinstance(response,dict):
            if context.get('semantic_contract'):
                from .question_semantics import findings,preview
                from .question_revision import unchanged_findings
                issues.extend(findings(source,response));issues.extend(unchanged_findings(root,task,response))
            if context.get('quality_contract'):
                from .question_quality import findings as quality_findings, repair_findings
                issues.extend(quality_findings(source,response,compact=True,structured=bool(context.get('repair_contract'))))
                from .question_feedback import canonical
                original_issues=canonical(context.get('feedback',{}),context.get('finding_guidance',{})).get('field_issues',[])
                issues.extend(repair_findings(prior,response,original_issues))
                from .question_quality import requirement_findings
                issues.extend(requirement_findings(source,response,original_issues))
                issues=[{**f,'path':'/method'} if f.get('path') in {'/method_before','/method_after'} else f for f in issues]
            if source.get('failure_followup'):
                from .question_failure_learning import check_changed
                try:check_changed(source,response)
                except practice_experiments.InvalidExperiment as exc:issues.extend(exc.findings)
        if context.get('measurement_contract') and source and isinstance(response,dict):
            from .question_measurements import findings as measurement_findings,evaluate
            issues.extend(measurement_findings(source,response))
            # Independent safe observations survive unrelated authoring rejection.
            measurement_result=evaluate(source,response)
            from .question_measurements import artifact_findings
            issues.extend(artifact_findings(measurement_result))
        if context.get('repair_contract'):
            from .question_repair import expand_findings
            issues=expand_findings(issues,response or {})
        if context.get('focus_contract'):
            from .question_focus import findings as focused_findings
            issues=focused_findings(issues)
        if issues:raise practice_experiments.InvalidExperiment(issues)
        question = records.store(root, 'successor_questions', {'episode_id': episode['id'], 'response': response,
            'evidence_bindings': {key: row.get('id', key) for key, row in context.get('failure_evidence', {}).items()},
            'evidence_metadata': context.get('failure_evidence_metadata', {}),
            'semantic_contract': context.get('semantic_contract'),
            'quality_contract': context.get('quality_contract'),
            'repair_contract': context.get('repair_contract'),
            'focus_contract': context.get('focus_contract'),
            'measurement_contract': context.get('measurement_contract'),
            'measurement_result': measurement_result,
            'revision_parent_question_id': task.get('revision_parent_question_id'),
            'semantic_revision_id': task.get('semantic_revision_id'),
            'unresolved_review_findings': original_issues if context.get('quality_contract') else context.get('feedback',{}).get('field_issues',[]),
            'execution_preview': preview(source, response) if context.get('semantic_contract') else None,
            'source': source, 'standing_objective': source['obligation']['objective'],
            'completion_check': source['obligation']['completion_check'], 'authoring_contract': episode.get('authoring_contract'), 'signature': digest([source['basis_sha256'], response]), 'authored_by': 'Novali',
            'acceptance': 'independent_semantic_review_then_separate_shared_practice_window'})
        task.update(state='awaiting_question_review', question_id=question['id'],
                    feedback={'measurement_result':measurement_result} if measurement_result else {})
    except VerifiedRefutation as exc:
        from .question_repair import last_parsed
        original_attempt=(records.read(root,'attempts',exc.receipt['parent_origin']['original_attempt_id'])
            if exc.receipt.get('parent_origin') else last_parsed(root,task))
        if not original_attempt:raise ValueError('owned_original_refutation_attempt_required')
        response=original_attempt['response']; measurement_result=exc.measurement
        refutation=records.store(root,'question_refutations',{**exc.receipt,'episode_id':episode['id'],'authored_by':'Novali',
            'original_attempt_id':original_attempt['id'],'original_proposal':response,'original_proposal_sha256':digest(response)})
        task.update(state='refuted_requires_review',refutation_id=refutation['id'],feedback={'reason':str(exc),'field_issues':exc.receipt['unresolved_findings']})
    except Exception as exc:
        # Provider/schema errors retain the full dispatch charge. Local failures
        # stop until reviewed repair rather than spinning free preparations.
        task.update(state='ready' if dispatched and account['usage']['model_calls'] < limits['max_model_calls'] else 'exhausted_no_candidate',
                    feedback={'reason': type(exc).__name__ + ': ' + str(exc)[:400],
                              'field_issues': [({**f,'path':'/execution_scope'} if context.get('semantic_contract') and f.get('path') in {'/field_batches','/scope_mode'} else f) for f in getattr(exc,'findings',[])] + ([f for f in context.get('feedback', {}).get('field_issues', [])
                                  if f not in getattr(exc, 'findings', [])] if response is prior or not dispatched else []),
                              'field_changes': changes,
                              'costs_retained': True, 'selected_source_id': task.get('selected_source_id')})
    finally:
        planner.dispatch_hook = old_hook
        repair_outcome = None
        if prior and isinstance(response,dict) and measurement_result is not None and account['usage']['tool_calls'] + 2 <= limits['max_tool_calls']:
            from .repair_outcomes import compare
            repair_source = next((s for s in choices if s['id']==response.get('source_id')),None)
            if repair_source:
                account['usage']['tool_calls'] += 2
                repair_outcome = compare(repair_source,prior,response,task['feedback'].get('field_issues',[]))
                task['feedback']['repair_status'] = repair_outcome['repair_status']
        if measurement_result is not None:
            from .question_measurements import feedback_observation
            task['feedback']['measurement_observation']=feedback_observation(measurement_result)
        if context.get('focus_contract'):
            from .question_feedback import canonical
            try:task['feedback']=canonical(task['feedback'],context.get('finding_guidance',{}))
            except ValueError as feedback_error:
                # Still settle a dispatched call; unresolved references block recovery.
                task['feedback']['finding_guidance']=copy.deepcopy(context.get('finding_guidance',{}))
                task['feedback']['reason']=str(feedback_error)
                task['state']='exhausted_no_candidate'
        account['usage']['compute_seconds'] = round(account['usage']['compute_seconds'] + time.monotonic() - started, 4)
        account['inflight'] = None; task['model_calls'] = account['usage']['model_calls']
        from .question_repair import prediction_lineage
        receipt = records.store(root, 'attempts', {'learning_episode_id': episode['id'], 'failure_id': task['failure_id'], 'response': response,
            **({'prediction_lineage':prediction_lineage(prior,response)} if context.get('repair_contract') else {}),
            'diagnosis_contract':context.get('diagnosis_contract'),
            'submitted_response': submitted, 'field_changes': changes, 'measurement_result': measurement_result,
            'repair_outcome': repair_outcome,
            'provider_metadata': getattr(planner, 'last_metadata', {}),
            'feedback': task['feedback'], 'provider_dispatched': dispatched, 'usage_after': copy.deepcopy(account['usage'])})
        task['attempt_ids'].append(receipt['id'])
        transaction.commit(root, task_path, account_path, task, account, receipt, kind='attempts')
    return task


def review(root: Path, question_id: str, *, decision: str, reviewer: str, authority_reference: str,
           novelty_evidence: str, applicability_evidence: str,
           findings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if decision == 'revise':
        from .question_revision import request
        return request(root, question_id, reviewer=reviewer, authority_reference=authority_reference,
            novelty_evidence=novelty_evidence, applicability_evidence=applicability_evidence, findings=findings)
    from . import directive_obligations as obligations
    question = records.read(root, 'successor_questions', question_id)
    prior = read_json(root / 'research_methods/successor_review_latest' / (question_id + '.json'))
    if prior:
        reviewed = records.read(root, 'successor_reviews', prior['review_id'])
        if reviewed['decision'] != decision: raise ValueError('successor_review_is_terminal')
        return reviewed
    episode = records.read(root, 'learning_episodes', question['episode_id'])
    task = read_json(root / 'research_methods/episode_tasks' / (episode['id'] + '.json'))
    if task.get('state') != 'awaiting_question_review' or task.get('question_id') != question_id:
        raise ValueError('settled_owned_question_required_for_review')
    if decision == 'approve':
        check(episode['frozen_question_choices'], question['response'], authoring_contract=episode.get('authoring_contract'),
              partition_enabled=episode.get('partition_enabled', False),measurement_contract=question.get('measurement_contract'))
        if question.get('semantic_contract'):
            from .question_revision import compatible as revision_compatible
            if (task.get('semantic_revision_id') and not revision_compatible(root, episode, task) or
                not task.get('semantic_revision_id') and episode['implementation'] != records.implementation()
                and not preparation_compatible(root,episode,task)):
                raise ValueError('current_reviewed_question_implementation_required')
            from .question_semantics import findings as semantic_findings
            issues = semantic_findings(question['source'], question['response'])
            if issues: raise QuestionValidationError(issues)
    if decision not in {'approve', 'reject'} or any(not isinstance(v, str) or not 16 <= len(v) <= 1600
            for v in (reviewer, authority_reference, novelty_evidence, applicability_evidence)):
        raise ValueError('independent_novelty_and_applicability_review_required')
    if decision == 'approve': obligations.assert_current(root, question['source']['frozen'])
    if decision == 'approve' and question.get('quality_contract'):
        from .question_quality import findings as quality_findings
        issues=quality_findings(question['source'],question['response'],compact=True,structured=bool(question.get('repair_contract')))
        from .question_quality import requirement_findings
        issues.extend(requirement_findings(question['source'],question['response'],question.get('unresolved_review_findings',[])))
        if issues:raise QuestionValidationError(issues)
    if decision == 'approve' and question['source'].get('failure_followup'):
        from .question_failure_learning import check_changed
        check_changed(question['source'], question['response'])
    if decision=='approve' and question.get('measurement_contract'):
        from .question_measurements import evaluate
        measured=evaluate(question['source'],question['response'])
        from .question_measurements import artifact_findings
        artifact_issues=artifact_findings(measured)
        if artifact_issues:raise QuestionValidationError(artifact_issues)
        if measured.get('status')=='inconclusive' or measured!=question.get('measurement_result'):
            raise ValueError('independently_reproduced_question_measurement_required')
    from .lesson_review_budget import charge
    if findings is not None:
        from .question_focus import validate_review_findings
        validate_review_findings(findings)
    with charge(root, episode):
        reviewed = records.store(root, 'successor_reviews', {'question_id': question_id, 'decision': decision, 'reviewer': reviewer,
            'authority_reference': authority_reference, 'novelty_evidence': novelty_evidence, 'applicability_evidence': applicability_evidence,
            'basis_sha256': question['source']['basis_sha256'], 'implementation': records.implementation(),
            'reviewed_requirements':copy.deepcopy(question.get('unresolved_review_findings',[])),
            **({'findings':copy.deepcopy(findings)} if findings is not None else {}),
            'execution_requires_separate_shared_reservation': True})
    write_json(root / 'research_methods/successor_review_latest' / (question_id + '.json'), {'review_id': reviewed['id']})
    return reviewed


def pending(root: Path) -> list[dict[str, Any]]:
    if not policy(root).get('enabled'): return []
    used = {e.get('successor_question_id') for e in episodes._episodes(root)}
    result = []
    for path in sorted((root / 'research_methods/successor_review_latest').glob('*.json')):
        reviewed = records.read(root, 'successor_reviews', read_json(path)['review_id'])
        if reviewed['decision'] != 'approve' or reviewed['implementation'] != records.implementation(): continue
        question = records.read(root, 'successor_questions', reviewed['question_id'])
        if question['response'].get('field_batches'):
            from .question_partitions import pending as pending_partitions
            try: result.extend(pending_partitions(root, question, reviewed))
            except (ValueError, KeyError, OSError): pass
            continue
        if reviewed['question_id'] in used: continue
        frozen = copy.deepcopy(question['source']['frozen'])
        frozen['obligations'] = [{**question['source']['obligation'], 'eligible': True, 'blocked_reason': None}]
        frozen['successor_review'] = reviewed; frozen['accepted_practice_question'] = question['response']
        result.append(frozen)
    return result


def status(root: Path) -> dict[str, Any]:
    configured = policy(root); shared = episodes.policy(root)
    try:
        now, earliest = episodes.admission_window(root, shared) if shared else (0, 0)
        reason = 'waiting_for_shared_window' if now < earliest else 'eligible_for_question_authoring'
    except ValueError as exc:
        earliest = None; reason = str(exc)
    raw_choices = catalog(root) if configured.get('enabled') else []
    offered = authoring_menu(raw_choices, configured)
    choices = visible(offered)
    awaiting = [read_json(p).get('question_id') for p in (root / 'research_methods/episode_tasks').glob('*.json')
                if read_json(p).get('state') == 'awaiting_question_review' and not (root / 'research_methods/successor_review_latest' / (str(read_json(p).get('question_id')) + '.json')).exists()]
    if choices and selection_blocked(root, raw_choices): reason = 'selection_failure_requires_review'
    if not choices: reason = 'awaiting_independent_question_review' if awaiting else 'no_unpracticed_question_basis'
    if raw_choices and not offered: reason = 'authoring_context_requires_reduction_before_reservation'
    return {'policy': configured, 'choices': choices, 'questions_awaiting_review': awaiting,
            'refutations_awaiting_review':[p.stem for p in (root/'research_methods/question_refutations').glob('*.json')
                if not (root/'research_methods/question_refutation_review_latest'/(p.stem+'.json')).exists()],
            'partition_progress': partition_status(root),
            'additional_eligible_choices': len(raw_choices) - len(offered),
            'approved_practice_queue': len(pending(root)), 'not_before': earliest,
            'queue_reason': reason,
            'scientific_allowance_added': 0}


def partition_status(root: Path) -> list[dict[str, Any]]:
    from .question_partitions import progress
    result = []
    for p in (root/'research_methods/successor_review_latest').glob('*.json'):
        review_record = records.read(root, 'successor_reviews', read_json(p)['review_id'])
        if review_record['decision'] != 'approve': continue
        question = records.read(root, 'successor_questions', review_record['question_id'])
        if question['response'].get('field_batches'): result.append(progress(root, question))
    return result

def retry_context(root: Path, episode: dict[str, Any], task: dict[str, Any], account: dict[str, Any]) -> dict[str, Any]:
    limits=account['limits']; remaining=limits['max_compute_seconds']-account['usage']['compute_seconds']
    choices = episode['frozen_question_choices']
    if task.get('selected_source_id'):
        choices = [r for r in choices if r['id'] == task['selected_source_id']]
    prior = None
    if task.get('attempt_ids'):
        prior = records.read(root, 'attempts', task['attempt_ids'][-1]).get('response')
    if task.get('repair_contract') or episode.get('repair_contract'):
        from .question_repair import last_parsed
        prior=(last_parsed(root,task) or {}).get('response')
    from .question_feedback import restore
    feedback=restore(root,task) if episode.get('focus_contract') else task['feedback']
    context = {'choices': visible(choices), 'feedback': feedback,
               'partition_enabled': episode.get('partition_enabled', False),
               'quality_contract': episode.get('quality_contract'),
               'repair_contract': task.get('repair_contract') or episode.get('repair_contract'),
               'focus_contract': task.get('focus_contract') or episode.get('focus_contract'),
               'measurement_contract': task.get('measurement_contract') or episode.get('measurement_contract'),
               'diagnosis_contract': episode.get('diagnosis_contract'),
               'semantic_contract': task.get('semantic_contract') or episode.get('semantic_contract'),
               'authoring_contract': episode.get('authoring_contract'),
               'previous_proposal': prior, 'selected_source_id': task.get('selected_source_id'),
               'remaining_resources': {'model_calls': limits['max_model_calls'] - account['usage']['model_calls'],
                    'tool_calls': limits['max_tool_calls'] - account['usage']['tool_calls'],
                    'compute_seconds': max(0, round(remaining, 4)), 'validation_seconds_reserved': 20},
               'provider_time_budget_seconds': 120}
    if task.get('semantic_revision_id'):
        for choice in context['choices']:
            choice.pop('failure_followup', None)  # The current reviewed proposal and findings supersede the old authoring-recovery prompt.
        context['semantic_revision_id'] = task['semantic_revision_id']
    if context.get('semantic_contract') and prior:
        from .question_semantics import preview
        plan = preview(choices[0], prior)
        context['execution_preview'] = {k:plan[k] for k in ('mode','original_field_count','batch_field_counts','missing_and_unknown_values')}
        if prior.get('field_batches'): context['execution_preview']['execution_batches'] = prior['field_batches']
        context['execution_preview']['original_unit_ref'] = 'choices[0].obligation.unit'
    return context

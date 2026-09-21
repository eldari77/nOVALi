"""Relevant-change context and explicit observable scope, without new allowance."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from .research_tools import digest, read_json

VERSION = 'research_change_review_v1'
QUANTITIES = {'bytes': 'content_size', 'visible_chars': 'content_size', 'numeric_token_count': 'numeric_content',
              'content_changed': 'content_difference', 'result_count': 'search_discovery'}
SCOPES = ['content_size', 'numeric_content', 'content_difference', 'search_discovery', 'field_state', 'model_effect', 'external_fact', 'unknown']


def enabled(root: Path) -> bool:
    from .child_directive_learning import policy
    return bool(policy(root).get('correction_enabled'))


def context(root: Path, task: Mapping[str, Any]) -> dict[str, Any]:
    """Use verified delivery metadata; never guess that an arbitrary edit is harmless."""
    if not enabled(root):
        return {}
    from .research_learning import experiences
    from .child_delivery import assert_reviewed_source_transition
    current = task.get('artifacts', {})
    histories = []
    for state, prior in experiences(root):
        if prior.get('directive_id') != task.get('directive_id') or prior.get('support_revision') != task.get('support_revision'):
            continue
        changes = []
        for ref in sorted(set(current) | set(prior.get('artifacts', {}))):
            before = prior.get('artifacts', {}).get(ref, {}); after = current.get(ref, {})
            if before == after:
                continue
            known = False
            if before.get('sha256') and after.get('sha256'):
                try:
                    assert_reviewed_source_transition(root, {'parent_episode_id': state['episode_id'],
                        'parent_contract_sha256': state['contract_sha256'], 'directive_id': task['directive_id'],
                        'dependencies': {ref: before['sha256']}})
                    known = True
                except (ValueError, KeyError, OSError):
                    pass
            changes.append({'artifact_ref': ref, 'before_sha256': before.get('sha256'), 'after_sha256': after.get('sha256'),
                'classification': 'verified_reviewed_addendum' if known else 'content_change_requires_relevance_assessment',
                'new_domain_evidence_established': False})
        if changes:
            ignored = {'artifacts', 'input_fingerprint', 'episode_index'}
            other_changed = {k: v for k, v in prior.items() if k not in ignored} != {k: v for k, v in task.items() if k not in ignored}
            histories.append({'episode_id': state['episode_id'], 'changes': changes[:12], 'other_inputs_changed': other_changed,
                'all_changes_verified_addenda': len(changes) <= 12 and all(c['classification'] == 'verified_reviewed_addendum' for c in changes),
                'prior_failure': state.get('feedback', ''), 'prior_state': state.get('state'),
                'prior_question': (state.get('last_rejected_response') or state.get('plan') or {}).get('question', ''),
                'prior_prediction': (state.get('last_rejected_response') or state.get('plan') or {}).get('prediction', {})})
    result = {'version': VERSION, 'history': histories[-4:],
              'instruction': 'Distinguish changed annotation from evidence that can change the answer. Explain relevance and declare the quantity your question needs. Unknown remains unknown.',
              'scientific_allowance_added': 0}
    result['sha256'] = digest(result)
    return result


def annotation_only_blocker(root: Path, task: Mapping[str, Any]) -> dict[str, Any]:
    review = context(root, task)
    match = next((h for h in reversed(review.get('history', [])) if h['all_changes_verified_addenda'] and not h['other_inputs_changed']
                  and h['prior_state'] == 'waiting_for_changed_input'), None)
    if not match:
        return {}
    return {'state': 'waiting_for_relevant_change', 'reason': 'verified_addenda_do_not_reopen_failed_research',
            'prior_episode_id': match['episode_id'], 'change_review': review,
            'next_action': 'Use bounded method practice or supply independently reviewed relevant evidence.',
            'scientific_allowance_added': 0, 'grants_execution_authority': False}


def contract(context: dict[str, Any], instructions: str, schema: dict[str, Any] | str) -> tuple[str, dict[str, Any] | str]:
    if not context.get('change_review'):
        return instructions, schema
    import copy
    from .planner_authoring import _object, _enum, _string
    schema = copy.deepcopy(schema)
    assessment = _object({'change_sha256': {'const': context['change_review']['sha256']},
        'relevance': _enum(['relevant', 'irrelevant', 'unknown']), 'explanation': _string(12, 240),
        'question_scope': _enum(SCOPES), 'measurement_can_answer': _enum(['yes', 'no', 'unknown']),
        'measurement_reason': _string(12, 240)})
    # The plan schema is open JSON in legacy planners. Add the bounded assessment
    # only to a concrete experiment variant, retaining capability-request variants.
    def bind(node: dict[str, Any]) -> None:
        props = node.get('properties', {})
        if 'actions' in props:
            props['change_assessment'] = assessment
            node.setdefault('required', []).append('change_assessment')
        for variant in node.get('oneOf', []) + node.get('anyOf', []):
            bind(variant)
    if isinstance(schema, dict):
        bind(schema)
    else:
        import json
        instructions += ' Experiment change_assessment schema: ' + json.dumps(assessment, separators=(',', ':'))
    return (instructions + ' Include change_assessment for an experiment. Explain whether the changed input matters. '
        'Declare the question scope separately from the offered metric. Numeric-token counts cannot establish field presence, '
        'and content diagnostics cannot establish external facts. If no offered metric answers the question, record no/unknown '
        'and request a precisely bounded measurement capability instead of claiming a discriminating experiment.', schema)


def check(plan: Mapping[str, Any], review: Mapping[str, Any]) -> dict[str, Any]:
    if not review:
        return {}
    from .child_correction import complete_sentence
    assessment = plan.get('change_assessment', {})
    keys = {'change_sha256', 'relevance', 'explanation', 'question_scope', 'measurement_can_answer', 'measurement_reason'}
    if not isinstance(assessment, dict) or set(assessment) != keys or assessment.get('change_sha256') != review['sha256']:
        raise ValueError('current_relevant_change_assessment_required')
    if (assessment['relevance'] not in {'relevant','irrelevant','unknown'} or assessment['question_scope'] not in SCOPES
            or assessment['measurement_can_answer'] not in {'yes','no','unknown'}):
        raise ValueError('typed_relevance_and_observable_scope_required')
    if any(not isinstance(assessment[k], str) or not 12 <= len(assessment[k]) <= 240 or not complete_sentence(assessment[k])
           for k in ('explanation', 'measurement_reason')):
        raise ValueError('complete_relevance_and_measurement_explanations_required')
    metric = plan.get('prediction', {}).get('metric')
    known_scope = QUANTITIES.get(metric, 'model_effect' if isinstance(metric,str) and (metric.endswith('_mse') or metric=='candidate_gain') else 'unknown')
    if assessment['measurement_can_answer'] != 'yes' or assessment['question_scope'] != known_scope or known_scope == 'unknown':
        raise ValueError('observable_does_not_discriminate_declared_question_request_measurement')
    if assessment['relevance'] != 'relevant':
        raise ValueError('relevant_evidence_or_changed_method_required')
    return {'scope_agreement_verified': True, 'semantic_relevance_requires_independent_review': True,
            'scientific_claim_verified': False, 'assessment': dict(assessment)}

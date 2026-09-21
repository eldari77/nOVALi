"""Independently reviewed, task-scoped failure evidence without fixture answers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import learning_evidence, research_procedures as records
from .research_tools import digest, read_json


DESCRIPTIONS = {
    'operation_format_requires_prose':'An operation was expressed as an identifier; this formatting issue is separate from completeness and semantic adequacy.',
    'unchanged_correction':'The submitted correction did not substantively change the implicated field.',
    'diagnosed_correction_required':'The correction omitted a bounded decision tied to an existing finding and target.',
    'diagnosis_must_bind_current_finding':'The correction diagnosis did not bind an offered requirement and its implicated target.',
    'diagnosed_target_not_edited':'The submitted edit did not change the field selected by its diagnosis.',
    'independent_refutation_not_established':'A claimed refutation lacked a matching independently replayed original comparison.',
    'refutation_requires_independent_replay':'The refutation must use the dedicated independent measurement path.',
    'measurement_scope_mismatch':'The proposed scope differed from the scope executed by the measurement instrument.',
    'executable_measurement_required':'The comparison lacked a registered executable instrument.',
    'measurement_prediction_mismatch':'The quantity, phase or falsifier disagreed with the predicted direction.',
    'registered_measurement_operations_required':'The proposed operations could not run on the registered instrument.',
    'measurement_input_unavailable':'The selected cached input was unavailable or ambiguous.',
    'measurement_adapter_unavailable':'The task needs an independently reviewed measurement capability.',
    'measurement_input_budget_exceeded':'The selected cached input exceeded the instrument limit.',
    'unchanged_method': 'The proposed baseline and changed method were identical.',
    'structured_operations_required': 'The operation lacked the required input binding, action or check structure.',
    'unfinished_operation': 'A specific operation action or check was unfinished.',
    'linked_measurement_review': 'Review the prediction, observable and falsifier together; already consistent supporting fields may remain unchanged.',
    'bounded_operational_method_required': 'The method did not specify bounded baseline and changed operations.',
    'unfinished_operational_definition': 'An operation or comparison contained an unfinished expression.',
    'evaluator_is_not_a_method': 'A bound evaluator name was used in place of an operational method definition.',
    'source_state_preservation_required': 'The proposed observable or measured operation failed to preserve required source-value states.',
    'value_presence_is_not_correctness': 'The proposed measurement conflated populated values with correct results.',
    'substantive_operation_change_required': 'The proposed operational change was cosmetic or unchanged.',
    'requirement_not_repaired': 'An edit left the originally reported requirement unresolved.',
    'hypothesis_observable_mismatch': 'The observable did not measure the selected hypothesis quantity.',

    'semantic_finding_unchanged': 'A reviewed semantic finding remained unchanged in the submitted revision.',
    'scope_mode_partition_mismatch': 'The selected execution mode disagreed with the submitted partition.',
    'explicit_execution_scope_required': 'The proposal did not explicitly choose full-unit or partitioned execution.',
    'invalid_prediction_evidence_binding': 'The prediction referenced evidence outside the selected task.',
    'evidence_phase_mismatch': 'The referenced observed failure occurred in a different execution phase.',
    'predictions_are_not_observed_results': 'An untested prediction was presented as an observed result.',
    'typed_untested_prediction_required': 'The proposal did not provide the required bounded prediction fields.',

    'terminal_punctuation_required': 'The explanation omitted final punctuation inside its field limit; this is a syntax finding, not proof of incomplete reasoning.',
    'incomplete_explanation': 'The explanation contained an unfinished ending or invalid whitespace; semantic completeness still requires review.',
    'bounded_complete_sentence_required': 'The explanation could not fit the declared field bounds.',
    'partition_must_cover_each_required_field_once': 'The proposed batches omitted, repeated or introduced fields relative to the original obligation.',
    'reviewed_failure_requires_changed_approach': 'The follow-up did not change the approach or failed fields identified by independent review.',
    'invalid_reference': 'A submitted identifier did not match the permitted current task bindings.',
    'required_field_missing': 'The submitted proposal omitted a required field.',
    'distinct_question_approach_and_falsifier_required': 'The objective, changed approach and falsifier were not distinct testable statements.',
    'source_state_mismatch': 'A submitted value-state classification disagreed with the supplied source. Missing, unresolved, zero and false must remain distinct.',
    'bounded_text_required': 'A submitted explanation exceeded its field limit; the complete meaning must fit the declared bound.',
    'complete_short_explanation_required': 'An explanation did not form a complete, bounded statement of its contribution.',
    'substantive_field_or_method_change_required': 'The attempted correction did not change the artifact field or method required by its unresolved finding.',
    'provider_outcome_uncertain': 'Provider dispatch did not yield a confirmed complete result; retained cost is not evidence of task completion.',
    'independent_acceptance_not_met': 'A produced candidate failed the independent task acceptance check.',
}


def inspect(archive: Path) -> dict[str, Any]:
    proof = learning_evidence.inspect(archive)
    manifest = read_json(archive / 'manifest.json')
    if manifest.get('version') not in {'child_learning_cycle_v6', 'child_learning_cycle_v7', 'child_learning_cycle_v8', 'successor_learning_cycle_v1'}:
        raise ValueError('scoped_child_failure_archive_required')
    cases = {c['name']: c for c in manifest['cases']}
    state = read_json(archive / 'evaluation.json')
    from .child_failure_patterns import receipt_details, DESCRIPTIONS as FAILURE_DESCRIPTIONS
    descriptions = {**DESCRIPTIONS, **FAILURE_DESCRIPTIONS}
    measurements = {}
    grouped: dict[tuple[str, str], set[str]] = {}
    unsupported: dict[tuple[str,str],set[str]] = {}
    for key in state['receipts']:
        receipt = read_json(archive / 'receipts' / (key + '.json'))
        case = cases[receipt['case']]
        task = receipt['result']
        details = receipt_details(receipt)
        codes = {d['code'] for d in details}
        for detail in details: measurements[(case['adapter'],detail['code'],key)] = detail['measurements']
        if receipt['calls'] and task.get('attempt_ids'):
            attempt = records.read(archive / case['name'] / 'state', 'attempts', task['attempt_ids'][-1])
            if attempt.get('provider_outcome_uncertain'):
                codes.add('provider_outcome_uncertain')
            feedback = attempt.get('outcome', attempt.get('feedback', {}))
            for issue in feedback.get('field_issues',[]):
                code=issue.get('code')
                if code in DESCRIPTIONS:codes.add(code)
                elif isinstance(code,str):unsupported.setdefault((case['adapter'],code),set()).add(key)
        if receipt.get('error'):
            codes.add('independent_acceptance_not_met')
        for code in codes:
            grouped.setdefault((case['adapter'], code), set()).add(key)
    details = []
    for (adapter, code), keys in sorted(grouped.items()):
        body = {'adapter': adapter, 'code': code, 'observation': descriptions[code],
                'evidence_receipts': sorted(keys), 'observations': len(keys),
                'scope': 'failure_mechanism_only_no_fixture_values_or_solutions',
                **({'measurements':[{'receipt':key,**measurements[(adapter,code,key)]} for key in sorted(keys) if (adapter,code,key) in measurements]}
                   if any((adapter,code,key) in measurements for key in keys) else {})}
        if code=='linked_measurement_review':body['kind']='supporting_guidance_not_an_independent_failure'
        details.append({'id': 'failure-detail-' + digest(body)[:24], **body})
    return {'archive_proof': proof, 'details': details, **({'unsupported_findings':[
        {'adapter':a,'code':c,'evidence_receipts':sorted(keys)} for (a,c),keys in sorted(unsupported.items())]} if unsupported else {})}


def propose(root: Path, archive: Path, *, repo_root: Path) -> dict[str, Any]:
    archive = archive.resolve(); repo_root = repo_root.resolve()
    if not archive.is_relative_to(repo_root / 'runtime_data/generated'):
        raise ValueError('owned_development_archive_required')
    proof = inspect(archive)
    if proof.get('unsupported_findings'):
        raise ValueError('unsupported_scoped_findings_require_mapping:'+','.join(sorted({f['code'] for f in proof['unsupported_findings']})))
    if not proof['details']:
        raise ValueError('scoped_observed_failure_required')
    return records.store(root, 'successor_evidence_proposals', {
        'archive_path': archive.relative_to(repo_root).as_posix(), 'proof': proof,
        'scientific_allowance_added': 0, 'requires_independent_review': True})


def review(root: Path, proposal_id: str, *, reviewer: str, authority_reference: str,
           repo_root: Path) -> dict[str, Any]:
    if any(not isinstance(v, str) or not 16 <= len(v) <= 1600 for v in (reviewer, authority_reference)):
        raise ValueError('independent_scoped_evidence_review_required')
    proposal = records.read(root, 'successor_evidence_proposals', proposal_id)
    archive = learning_evidence._inside(repo_root, proposal['archive_path'])
    if inspect(archive) != proposal['proof']:
        raise ValueError('scoped_evidence_changed_before_review')
    return records.store(root, 'successor_evidence_reviews', {
        'proposal_id': proposal_id, 'proposal_sha256': digest(proposal), 'decision': 'approve',
        'reviewer': reviewer, 'authority_reference': authority_reference, 'scientific_allowance_added': 0})


def context(root: Path, adapter: str) -> list[dict[str, Any]]:
    """Review timestamps and unrelated adapters never alter a task's basis."""
    details = {}
    for path in sorted((root / 'research_methods/successor_evidence_reviews').glob('*.json')):
        review_record = records.read(root, 'successor_evidence_reviews', path.stem)
        proposal = records.read(root, 'successor_evidence_proposals', review_record['proposal_id'])
        if digest(proposal) != review_record['proposal_sha256']:
            raise ValueError('scoped_evidence_integrity_failure')
        if review_record['decision'] != 'approve':
            continue
        for detail in proposal['proof']['details']:
            if detail['adapter'] == adapter:
                details[detail['id']] = {**detail, 'review_id': review_record['id'],
                    'scientific_allowance_added': 0, 'method_adoption_authorized': False}
    return [details[key] for key in sorted(details)]

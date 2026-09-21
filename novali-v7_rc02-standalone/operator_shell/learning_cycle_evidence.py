"""Answer-free historical cycle failures for independent learning review."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from .research_tools import digest, read_json


def inspect(output: Path) -> dict[str, Any]:
    from .learning_cycle_eval import load, ARMS
    manifest,state=load(output,require_current_implementation=False)
    patterns={};evidence=[]
    def count(name: str) -> None:
        patterns[name]=patterns.get(name,0)+1
    for arm in ARMS:
        progress=read_json(output/arm/'progress.json')
        if progress['phase']!='complete':raise ValueError('settled_complete_learning_cycle_required')
        from . import research_procedures as records
        root=output/arm/'state'
        receipts=[read_json(output/'receipts'/(key+'.json')) for key in state['receipts']]
        question_receipts=[r for r in receipts if r['arm']==arm and r['phase']=='question' and r.get('attempt_id')]
        accepted=[r for r in question_receipts if r['outcome'].get('question_id') and not r['outcome'].get('error')]
        if bool(accepted)!=progress['question_passed']:raise ValueError('cycle_question_verdict_mismatch')
        if accepted:
            question=records.read(root,'practice_questions',accepted[-1]['outcome']['question_id'])
            if question['id']!=progress['question_id']:raise ValueError('cycle_question_lineage_mismatch')
        from .practice_lessons import memory
        retained=memory(root)
        if bool(retained)!=progress['practice_passed']:raise ValueError('cycle_practice_verdict_mismatch')
        if retained and not any(r['id']==progress['practice_lesson_id'] for r in retained):
            raise ValueError('cycle_retained_lesson_mismatch')
        from .decision_learning_eval import _score
        for kind,row in progress['reuse'].items():
            matching=[r for r in receipts if r['arm']==arm and r['phase']=='reuse' and r['case_kind']==kind]
            if not matching:raise ValueError('owned_cycle_reuse_receipt_required')
            receipt=matching[-1];case=next(c for c in manifest['cases'] if c['arm']==arm and c['kind']==kind)
            fresh=output/case['directory']/'state';attempt=records.read(fresh,'attempts',receipt['attempt_id'])
            if _score(fresh,case,attempt)!=row['passed']:raise ValueError('independent_cycle_reuse_verdict_mismatch')
            application=attempt.get('lesson_application') or {}
            verified=bool(row['passed'] and application.get('comparisons_verified') and
                application.get('authored',{}).get('lesson_id')==progress.get('practice_lesson_id') and
                application['authored']['decision'] in ('reuse','adapt') and
                receipt['process_id']!=progress.get('practice_process_id'))
            if row['verified_method_reuse']!=verified:raise ValueError('cycle_reuse_attribution_mismatch')
        if not progress['question_passed']:count('no_independently_accepted_question')
        elif not progress['practice_passed']:count('practice_did_not_produce_checked_lesson')
        elif len(progress['reuse'])<2:count('learning_cycle_stopped_before_fresh_tasks')
        for row in progress['reuse'].values():
            if not row['passed']:count('fresh_task_did_not_meet_acceptance')
            if arm=='with_memory' and not row['verified_method_reuse']:
                count('retained_method_reuse_not_demonstrated')
        evidence.append(digest(progress))
    for key in state['receipts']:
        receipt=read_json(output/'receipts'/(key+'.json'));evidence.append(key)
        if receipt.get('provider_metadata',{}).get('provider_outcome')=='unknown':
            count('provider_completion_uncertain')
        if 'falsifier_must_test_selected_observable' in str(receipt.get('outcome',{})):
            count('falsifier_referenced_different_quantity')
        if 'application_' in str(receipt.get('outcome',{})):
            count('lesson_applicability_comparison_rejected')
    return {'manifest_sha256':manifest['sha256'],'archive_state_sha256':digest(state),
        'evidence_sha256':digest(evidence),'historical_implementation':manifest['implementation'],
        'calls':state['calls'],'patterns':patterns,
        'scope':'observed_failure_patterns_only_no_answers_or_withheld_cases'}

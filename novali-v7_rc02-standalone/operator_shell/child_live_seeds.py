"""Freeze provenance of actually reviewed and consumed live methods for evaluation."""
from __future__ import annotations
import copy
from pathlib import Path
from typing import Any
from . import directive_candidates as candidates, research_procedures as records
from .research_tools import digest


def validate(proof: dict[str, Any]) -> None:
    if not isinstance(proof,dict) or any(not isinstance(proof.get(k),dict) for k in ('candidate','review','consumption','method')):
        raise ValueError('complete_live_method_provenance_required')
    for kind, key in (('child_candidates','candidate'),('child_reviews','review'),('child_consumption','consumption')):
        row = proof[key]
        expected = kind.rstrip('s')+'-'+digest({k:v for k,v in row.items() if k!='id'})[:24]
        if row.get('id') != expected: raise ValueError('live_method_seed_record_integrity_failure')
    candidate, review, consumed = proof['candidate'], proof['review'], proof['consumption']
    if (review.get('candidate_id') != candidate['id'] or review.get('decision') != 'approve'
            or not review.get('method_approved') or consumed.get('candidate_id') != candidate['id']
            or consumed.get('review_id') != review['id']
            or consumed.get('use') != 'verified_resident_artifact_write'):
        raise ValueError('reviewed_and_consumed_live_method_required')
    if candidates.assess(candidate['frozen'],candidate['context'],candidate['response']) != candidate['assessment']:
        raise ValueError('live_method_seed_assessment_changed')
    from .child_repairs import verify_review
    verify_review(candidate,review.get('finding_resolutions'),'approve')
    from .child_procedure_programs import evaluate
    evaluate(candidate['response']['method'],candidate['context'],candidate['response']['payload'])
    expected = {'id':candidate['id'],**candidate['response']['method'],'precondition':candidate['response']['method']['adapter'],
        'scope':'reviewed_and_consumed_structure_only_recheck_current_evidence','transfer_verified':False}
    if proof.get('method') != expected: raise ValueError('live_method_seed_content_mismatch')


def capture(root: Path, candidate_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    if not 1 <= len(candidate_ids) <= 2 or len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError('one_or_two_distinct_reviewed_live_methods_required')
    from .child_review import latest
    available = {m['id']:m for m in candidates.methods(root)}
    result = []
    for cid in candidate_ids:
        if cid not in available: raise ValueError('live_method_not_adopted_and_consumed')
        matches = [records.read(root,'child_consumption',p.stem) for p in (root/'research_methods/child_consumption').glob('*.json')]
        consumed = next((r for r in matches if r.get('candidate_id')==cid and r.get('use')=='verified_resident_artifact_write'),None)
        proof = {'method':copy.deepcopy(available[cid]),'candidate':records.read(root,'child_candidates',cid),
            'review':latest(root,cid),'consumption':consumed,'scope':'frozen_live_provenance_only_no_new_approval'}
        validate(proof); result.append(proof)
    return result

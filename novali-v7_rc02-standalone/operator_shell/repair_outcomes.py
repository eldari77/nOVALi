"""Independently replay a local repair without granting novelty or adoption."""
from __future__ import annotations
from typing import Any
from .research_tools import digest
from . import question_measurements as measurement


def compare(source: dict[str, Any], before: Any, after: Any, unresolved: list) -> dict[str, Any]:
    base = {'repair_status':'not_established', 'invention_status':'not_established',
            'adoption_credit':False, 'allowance_added':0, 'scientific_progress_credited':False,
            'unresolved_findings':unresolved, 'original_prediction':(before or {}).get('hypothesis'),
            'before_sha256':digest(before), 'after_sha256':digest(after)}
    if not isinstance(before,dict) or not isinstance(after,dict): return base
    try:
        data, keys = measurement.inputs(source)
        prior = measurement.observe(source,before); current = measurement.observe(source,after)
        if prior.get('status') != 'measured' or current.get('status') != 'measured': return base
        if prior['input_sha256'] != current['input_sha256'] or prior['selection_sha256'] != current['selection_sha256']:
            return base
        def failures(report): return {c['field'] for c in report['runs']['changed']['counterexamples']}
        old, new = failures(prior), failures(current)
        repaired, regressed = sorted(old-new), sorted(new-old)
        changed = before['method']['changed_operation'] != after['method']['changed_operation']
        status = ('regressed' if regressed else 'verified_local_repair' if repaired and changed else 'not_established')
        return {**base, 'repair_status':status, 'repaired_fields':repaired, 'regressed_fields':regressed,
                'remaining_failed_fields':sorted(new), 'previously_correct_preserved':not regressed,
                'before':prior, 'after':current, 'source_sha256':digest(source),
                'scope':'same_cached_input_only_transfer_and_downstream_use_not_established',
                'hypothesis_status':measurement.evaluate(source,after)['status'],
                'matches_baseline':after['method']['changed_operation']==after['method']['baseline_operation']}
    except (ValueError,KeyError,TypeError): return base

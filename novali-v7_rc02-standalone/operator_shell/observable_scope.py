"""Explicit measurement scope; prose is never evidence for another quantity."""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

from .authoring_contract import METRICS

UNITS = {'context_bytes':'bytes','instruction_chars':'characters','schema_bytes':'bytes',
         'action_seconds':'seconds','prompt_seconds':'seconds'}
STATIC_METRICS = ('context_bytes','instruction_chars','schema_bytes')


def observations(assessment: Mapping[str, Any]) -> list[dict[str, Any]]:
    before=assessment.get('baseline_components') or {};after=assessment.get('candidate_components') or {}
    rows=[]
    for metric,definition in METRICS.items():
        a,b=before.get(metric),after.get(metric)
        known=all(type(v) in (int,float) and math.isfinite(v) for v in (a,b)) and a>0 and b>=0
        rows.append({'metric':metric,'unit':UNITS[metric],'definition':definition,
            'baseline':a if known else None,'candidate':b if known else None,
            'observed_reduction_percent':100*(a-b)/a if known else None,
            'effect':('decrease' if b<a else 'increase' if b>a else 'unchanged') if known else 'unknown',
            'scope':'supplied_frozen_input_only','measurement_available':known})
    return rows


def falsifier_issues(hypothesis: Any) -> list[dict[str, Any]]:
    if not isinstance(hypothesis,dict) or hypothesis.get('metric') not in METRICS:return []
    text=str(hypothesis.get('falsifier','')).lower()
    mentioned=[metric for metric in METRICS if re.search(r'\b'+metric.replace('_',r'[_\s]+')+r'\b',text)]
    other=[metric for metric in mentioned if metric!=hypothesis['metric']]
    if not other:return []
    return [{'field':'strategy_hypothesis.falsifier','reason':'falsifier_must_test_selected_observable',
        'selected_metric':hypothesis['metric'],'other_metrics':other,
        'explanation':'State the falsifying observation for the selected quantity. Distinct quantities require separate hypotheses; a size result does not establish latency.'}]


def contract(hypothesis: Mapping[str, Any]) -> dict[str, Any]:
    metric=hypothesis['metric']
    return {'metric':metric,'unit':UNITS[metric],'definition':METRICS[metric],
        'test':'observed_reduction_percent_at_least_prediction',
        'prediction_percent':hypothesis['predicted_reduction_percent'],
        'scope':'selected_quantity_on_frozen_input_only',
        'other_quantities_require_separate_evaluation':True,
        'prose_semantics_fully_verified':False}

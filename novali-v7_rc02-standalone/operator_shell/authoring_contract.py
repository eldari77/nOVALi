"""One action projection and complete diagnostics for bounded method authoring."""
from __future__ import annotations

import math
from typing import Any, Mapping

from . import planner_resources as resources
from .method_patches import _valid


METRICS = {
    'context_bytes': 'UTF-8 bytes of the user context only; excludes instructions and schema',
    'instruction_chars': 'Characters of the system instructions only',
    'schema_bytes': 'UTF-8 bytes of the output schema only',
    'action_seconds': 'Seconds for the complete action, including local work',
    'prompt_seconds': 'Provider-reported prompt processing seconds; excludes loading and generation',
}


def eligibility(context: Mapping[str, Any]) -> dict[str, Any]:
    inputs = context.get('inputs', {})
    pending = inputs.get('prediction_correction_available')
    forecast = inputs.get('admission_forecast', {}).get('production', {})
    date = forecast.get('not_before')
    correction = isinstance(pending, dict) and bool(pending.get('attempt_id'))
    decision = inputs.get('hypothesis_decision_available')
    decision_available = isinstance(decision,dict) and decision.get('verdict')=='refuted' and bool(decision.get('finding_id'))
    if decision_available:
        measured=decision.get('counterexample',{}).get('observed_reduction_percent')
        correction=correction and type(measured) in (int,float) and math.isfinite(measured) and measured>=1
    defer = (forecast.get('state') == 'waiting_for_policy_window' and type(date) in (float, int)
             and math.isfinite(date) and date > 0)
    return {'planning_strategy': True, 'capability_request': True,
            'prediction_correction': correction,
            'correction_attempt_id': pending['attempt_id'] if correction else None,
            'hypothesis_resolution':decision_available,'hypothesis_revision':decision_available,
            'defer_until_validation': defer, 'defer_not_before': date if defer else None}


def field_issues(value: Any, shape: Mapping[str, Any], path: str) -> list[dict[str, Any]]:
    """Report all independently checkable shape errors, without repairing data."""
    if _valid(value, shape):
        if shape.get('uniqueItems') and len({repr(v) for v in value}) != len(value):
            return [{'field': path, 'reason': 'unique_values_required'}]
        return []
    if shape.get('type') == 'object' and isinstance(value, dict):
        rows = [{'field': path + '.' + k, 'reason': 'unexpected_field'} for k in sorted(set(value)-set(shape['properties']))]
        for k, spec in shape['properties'].items():
            rows.extend(field_issues(value[k], spec, path+'.'+k) if k in value else
                        [{'field': path+'.'+k, 'reason': 'required_field_missing'}])
        return rows
    return [{'field': path, 'reason': 'value_outside_contract', 'actual': value, 'expected': dict(shape)}]


def diagnose(response: Mapping[str, Any], inputs: Mapping[str, Any], *, revision_used: bool = False) -> list[dict[str, Any]]:
    from .planner_authoring import _object, _string
    rows = field_issues(response.get('planning_strategy'), resources.schema(), 'planning_strategy')
    hypothesis = response.get('strategy_hypothesis')
    if hypothesis is not None:
        rows += field_issues(hypothesis, resources.hypothesis_schema(), 'strategy_hypothesis')
        from .observable_scope import falsifier_issues
        rows += falsifier_issues(hypothesis)
    profile = response.get('planning_strategy')
    if _valid(profile, resources.schema()) and isinstance(hypothesis, dict):
        previous = inputs.get('previous_strategy', {'instruction_mode':'full','excerpt_chars':4000,'command_scope':'all_executable'})
        changed = [k for k in ('excerpt_chars','instruction_mode','command_scope') if profile[k] != previous[k]]
        declared=hypothesis.get('changed_fields')
        if not isinstance(declared,list) or any(not isinstance(v,str) for v in declared) or sorted(declared) != sorted(changed):
            rows.append({'field':'strategy_hypothesis.changed_fields',
                         'reason':'hypothesis_changed_fields_must_match_actual_strategy_changes',
                         'actual':hypothesis.get('changed_fields'), 'expected':changed,
                         'differences':{k:{'before':previous[k], 'after':profile[k]} for k in changed}})
    if 'prediction_correction' in response:
        eligible = eligibility({'inputs': inputs})
        correction = response['prediction_correction']
        rows += field_issues(correction, _object({'attempt_id':_string(8,100),'reason':_string(12,300)}), 'prediction_correction')
        if not eligible['prediction_correction'] or revision_used:
            rows.insert(0, {'field':'prediction_correction', 'reason':'prediction_correction_unavailable',
                           'explanation':'No eligible refuted prediction is pending. Submit a new strategy without prediction_correction.',
                           'eligible_attempt_ids':[]})
        elif isinstance(correction, dict) and correction.get('attempt_id') != eligible['correction_attempt_id']:
            rows.insert(0, {'field':'prediction_correction.attempt_id', 'reason':'prediction_correction_reference_mismatch',
                           'actual':correction.get('attempt_id'), 'expected':eligible['correction_attempt_id']})
        elif eligible['prediction_correction']:
            base=inputs['prediction_correction_available'].get('base_response',{})
            if base:
                for key in ('planning_strategy',):
                    if response.get(key)!=base.get(key):
                        rows.append({'field':key,'reason':'bounded_prediction_correction_must_preserve_strategy',
                                     'actual':response.get(key),'expected':base.get(key)})
                old=base.get('strategy_hypothesis',{})
                for key in ('metric','changed_fields','mechanism','falsifier'):
                    if not isinstance(hypothesis,dict) or hypothesis.get(key)!=old.get(key):
                        rows.append({'field':'strategy_hypothesis.'+key,'reason':'bounded_prediction_correction_must_preserve_measurement',
                                     'expected':old.get(key)})
    if 'hypothesis_revision' in response:
        binding=inputs.get('hypothesis_decision_available')
        if not binding:
            rows.append({'field':'hypothesis_revision','reason':'current_owned_hypothesis_evidence_link_required'})
        else:
            from .hypothesis_decisions import link_schema
            rows+=field_issues(response['hypothesis_revision'],link_schema(binding),'hypothesis_revision')
            old=binding['hypothesis']
            if isinstance(hypothesis,dict) and all(hypothesis.get(k)==old[k] for k in ('metric','mechanism','falsifier')):
                rows.append({'field':'strategy_hypothesis','reason':'numerical_change_uses_prediction_correction'})
            if _valid(profile,resources.schema()):
                for k in ('excerpt_chars','instruction_mode','command_scope'):
                    if profile[k]!=binding['profile'][k]:
                        rows.append({'field':'planning_strategy.'+k,'reason':'hypothesis_revision_preserves_untested_controls',
                            'before':binding['profile'][k],'after':profile[k]})
    return rows


def prediction_issue(hypothesis: Any, assessment: Mapping[str, Any]) -> dict[str, Any] | None:
    if not _valid(hypothesis, resources.hypothesis_schema()): return None
    metric = hypothesis['metric']; before = (assessment.get('baseline_components') or {}).get(metric)
    after = (assessment.get('candidate_components') or {}).get(metric)
    if (type(before) not in (int,float) or type(after) not in (int,float)
            or not math.isfinite(before) or not math.isfinite(after) or before<=0 or after<0):return None
    maximum = before*(1-hypothesis['predicted_reduction_percent']/100)
    if after <= maximum: return None
    return {'field':'strategy_hypothesis.predicted_reduction_percent', 'reason':'strategy_preflight_prediction_not_met',
            'metric':metric, 'definition':METRICS[metric], 'baseline':before, 'candidate':after,
            'required_maximum':maximum, 'observed_reduction_percent':100*(before-after)/before if before else None}


class AuthoringError(ValueError):
    def __init__(self, issues: list[dict[str, Any]], assessment: dict[str, Any]):
        super().__init__(issues[0]['reason'])
        self.field_issues = issues
        self.assessment = assessment

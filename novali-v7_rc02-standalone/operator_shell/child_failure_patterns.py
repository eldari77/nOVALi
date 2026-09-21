"""Answer-free failure mechanisms and observed costs, including undispatched work."""
from __future__ import annotations
from typing import Any

DESCRIPTIONS = {
    'output_exhausted': 'Generation reached its output limit before a complete response; test a smaller response or bounded references.',
    'incomplete_response': 'A dispatched response was incomplete; no task completion was established.',
    'malformed_response': 'A dispatched response could not be parsed as one complete structured object.',
    'preparation_context_exceeded': 'Local preparation could not reserve input and output together; no provider call was dispatched.',
}


def classify(feedback: dict[str, Any], metadata: dict[str, Any], *, dispatched: bool) -> list[str]:
    reason = str(feedback.get('reason',''))
    if not dispatched:
        return ['preparation_context_exceeded'] if any(s in reason for s in (
            'input_plus_output_reservation_exceeded','no_current_route_fits_complete_response_reservation',
            'child_authoring_grammar_budget_exceeded')) else []
    if 'incomplete_child_response' in reason:
        return ['output_exhausted' if metadata.get('done_reason') == 'length' else 'incomplete_response']
    if reason.startswith(('Extra data:', 'Expecting ', 'Unterminated string', 'Invalid control character')):
        return ['malformed_response']
    return []


def measurements(metadata: dict[str, Any], *, dispatched: bool) -> dict[str, Any]:
    if not dispatched: return {'provider_dispatched':False}
    return {'provider_dispatched':True, **{k:metadata[k] for k in
        ('context_utf8_bytes','output_token_limit','eval_count','done_reason','configured_context_tokens') if k in metadata},
        'phases_seconds':{k:v for k,v in metadata.get('timing',{}).items() if k in
            ('preflight_seconds','provider_prompt_seconds','provider_generation_seconds','transport_seconds')},
        'scope':'observed_costs_not_causal_explanation'}


def receipt_details(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    dispatched = bool(receipt['calls'])
    metadata = receipt.get('phase_measurements',{}) if dispatched else {}
    return [{'code':code, 'observation':DESCRIPTIONS[code], 'measurements':measurements(metadata,dispatched=dispatched)}
        for code in classify(receipt.get('result',{}).get('feedback',{}),metadata,dispatched=dispatched)]

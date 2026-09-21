"""Executable, versioned hypotheses for controlled cached-input questions."""
from __future__ import annotations
from . import recursive_contract as contract
from .research_tools import digest

VERSION = 'executable_question_v2'
BASE = {
    'effective_operation': {'unit':'operation_id','meaning':'chosen projection after first-match rule dispatch'},
    'state_errors': {'unit':'count','meaning':'number of selected-field mismatches against the independent state oracle'},
}


def schema(foci: list[str], observables: list[str]) -> dict:
    from .planner_authoring import _object, _enum
    from .recursive_growth import schema as proposal_schema
    case=proposal_schema()['properties']['practice_cases']['items']
    case['properties']['fields']['maxItems']=12
    case['properties']['record']['maxProperties']=12
    return _object({'focus':_enum(foci),
        'objective':{'type':'string','minLength':16,'maxLength':120},
        'observable':_enum(observables),'expected_relation':_enum(['same','different']),
        'falsifier':_enum(['same','different']),
        'cases':{'type':'array','minItems':2,'maxItems':2,'items':case}})


def validate(proposal: dict, foci: list[str], observables: list[str]) -> None:
    contract.validate(proposal,schema(foci,observables))
    if proposal['falsifier']==proposal['expected_relation']:
        raise ValueError('falsifier_must_contradict_prediction_for_the_same_observable')


def binding(proposal: dict, strategy: dict, definitions: dict) -> dict:
    return {'contract':VERSION,'observable':proposal['observable'],
        'definition':definitions[proposal['observable']],
        'controls_sha256':digest(strategy),'input_sha256':digest(proposal['cases']),
        'intervention':'one_selected_key_absent_vs_explicit_null',
        'prediction':proposal['expected_relation'],'falsified_by':proposal['falsifier'],
        'scope':'these_two_inputs_under_the_retained_method_only',
        'causality_or_universal_claim':False}


def brief(proposal: dict) -> dict:
    if 'changed_approach' in proposal:  # Frozen legacy format.
        return {k:proposal[k] for k in ('focus','objective','hypothesis','falsifier')}
    return {k:proposal[k] for k in ('focus','objective','observable','expected_relation','falsifier')}

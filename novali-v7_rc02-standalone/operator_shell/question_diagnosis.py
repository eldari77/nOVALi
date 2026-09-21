"""Bounded diagnosis before correction; measured refutation never earns adoption."""
from __future__ import annotations

import copy
from typing import Any
from .research_tools import digest

VERSION = 'question_diagnosis_v1'


def requirements(context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    from .question_feedback import canonical
    result = {}
    for f in canonical(context.get('feedback', {}), context.get('finding_guidance', {})).get('field_issues', []):
        if f['code'] == 'linked_measurement_review':
            continue
        key = f.get('requirement_id') or 'r' + digest([f['path'], f.get('original_code', f['code'])])[:16]
        result[key] = f
    return result


def implicated(context: dict[str, Any], finding: dict[str, Any], paths: list[str]) -> list[str]:
    path = finding['path']
    if context.get('measurement_contract') and path in {'/observable','/failure_condition','/measurement'}:
        path = '/hypothesis'
    return [p for p in paths if p == path or p.startswith(path + '/') or path.startswith(p + '/')]


def narrow_paths(context: dict[str, Any], paths: list[str]) -> list[str]:
    """Keep an unchallenged baseline fixed while the failed operation is repaired."""
    if not context.get('diagnosis_contract'):
        return paths
    issues = list(requirements(context).values())
    baseline_failed = any(f['path'].startswith('/method/baseline_operation') for f in issues)
    result = []
    for path in paths:
        if path == '/method' and context.get('measurement_contract'):
            result.append('/method/changed_operation/action')
            if baseline_failed:
                result.append('/method/baseline_operation/action')
        elif path.startswith('/method/baseline_operation') and not baseline_failed:
            continue
        else:
            result.append(path)
    return sorted(set(result))


def augment(context: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(context)
    if not result.get('diagnosis_contract') or not result.get('previous_proposal'):
        return result
    for finding in result.get('feedback',{}).get('field_issues',[]):
        if finding['code']!='linked_measurement_review':
            finding.setdefault('requirement_id','r'+digest([finding['path'],finding.get('original_code',finding['code'])])[:16])
    from .practice_experiments import editable
    paths = editable(result)
    result['correction_requirements'] = {
        key: {'code': f.get('original_code', f['code']), 'targets': implicated(result, f, paths)}
        for key, f in requirements(result).items() if implicated(result, f, paths)}
    return result


def schema(context: dict[str, Any], edit_schema: dict[str, Any]) -> dict[str, Any]:
    from .planner_authoring import _object, _enum
    from .practice_experiments import editable
    paths = editable(context)
    diagnoses = [_object({'requirement': {'const': key}, 'target': _enum(targets)})
        for key, f in requirements(context).items() if (targets := implicated(context, f, paths))]
    if not diagnoses:
        return edit_schema
    diagnosis = {'anyOf': diagnoses}
    # Each branch binds the diagnosed requirement, target and replacement.
    # A model can no longer diagnose /hypothesis and accidentally edit /method.
    items = edit_schema['properties']['edits']['items']
    items = items.get('anyOf', [items])
    repairs = []
    for key, finding in requirements(context).items():
        for target in implicated(context, finding, paths):
            item = next(i for i in items if i['properties']['path'].get('enum') == [target])
            repairs.append(_object({'requirement': {'const': key}, 'target': {'const': target},
                                    'value': copy.deepcopy(item['properties']['value'])}))
    supporting = copy.deepcopy(edit_schema['properties']['edits'])
    supporting['minItems'] = 0
    supporting['maxItems'] = max(0, len(paths) - 1)
    arms = [_object({'decision': {'const': 'repair'}, 'repair': {'anyOf': repairs},
                     'supporting_edits': supporting})]
    observation = context.get('feedback', {}).get('measurement_observation', {})
    if observation.get('hypothesis_status') == 'refuted' and observation.get('report_sha256'):
        arms.append(_object({'decision': {'const': 'refute'}, 'diagnosis': diagnosis,
            'report_sha256': {'const': observation['report_sha256']}}))
    return {'anyOf': arms}


def validate(context: dict[str, Any], submitted: Any) -> dict[str, Any]:
    from .practice_experiments import InvalidExperiment, editable
    if not isinstance(submitted, dict):
        raise InvalidExperiment([{'path':'/', 'code':'diagnosed_correction_required'}])
    if submitted.get('decision') == 'repair' and 'repair' in submitted:
        repair = submitted.get('repair')
        if (set(submitted) != {'decision','repair','supporting_edits'} or not isinstance(repair,dict)
                or set(repair) != {'requirement','target','value'} or not isinstance(submitted['supporting_edits'],list)):
            raise InvalidExperiment([{'path':'/repair','code':'bound_diagnosis_and_replacement_required'}])
        submitted = {'decision':'repair', 'diagnosis':{k:repair[k] for k in ('requirement','target')},
                     'edits':[{'path':repair['target'],'value':repair['value']}, *submitted['supporting_edits']]}
    decision = submitted.get('decision')
    expected = {'decision','diagnosis','edits'} if decision == 'repair' else {'decision','diagnosis','report_sha256'}
    diagnosis = submitted.get('diagnosis')
    if (decision not in {'repair','refute'} or set(submitted) != expected or not isinstance(diagnosis, dict)
            or set(diagnosis) != {'requirement','target'}):
        raise InvalidExperiment([{'path':'/', 'code':'diagnosed_correction_required'}])
    finding = requirements(context).get(diagnosis['requirement'])
    if not finding or diagnosis['target'] not in implicated(context, finding, editable(context)):
        raise InvalidExperiment([{'path':'/', 'code':'diagnosis_must_bind_current_finding'}])
    if decision == 'repair' and not any(isinstance(e,dict) and e.get('path') == diagnosis['target'] for e in submitted.get('edits', [])):
        raise InvalidExperiment([{'path':diagnosis['target'], 'code':'diagnosed_target_not_edited',
            'guidance':'Edit the diagnosed target; unrelated changes do not address this finding.'}])
    if decision == 'repair':
        from .question_focus import value_at
        from .question_quality import cosmetic_only
        edit=next(e for e in submitted['edits'] if e['path']==diagnosis['target'])
        if cosmetic_only(value_at(context.get('previous_proposal',{}),diagnosis['target']),edit.get('value')):
            raise InvalidExperiment([{'path':diagnosis['target'],'code':'unchanged_correction',
                'guidance':'The diagnosed field must change substantively; omit unchanged supporting fields.'}])
    return submitted


def repair_findings(context: dict[str, Any], changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not context.get('diagnosis_contract'):
        return []
    from .question_quality import cosmetic_only
    return [{'path': c['path'], 'code':'unchanged_correction',
        'guidance':'The submitted value did not substantively change. Diagnose the remaining contradiction before editing.',
        'counterexample': {'before_sha256':digest(c['before']),'after_sha256':digest(c['after'])}}
        for c in changes if cosmetic_only(c['before'],c['after'])]


class VerifiedRefutation(Exception):
    def __init__(self, receipt: dict[str, Any], measurement: dict[str, Any]):
        self.receipt = receipt
        self.measurement = measurement
        super().__init__('independently_measured_refutation_requires_review')


def refute(context: dict[str, Any], sources: list[dict[str, Any]], submitted: Any) -> None:
    from .practice_experiments import InvalidExperiment
    from .question_measurements import evaluate, feedback_observation
    validate(context, submitted)
    prior = context['previous_proposal']
    source = next(s for s in sources if s['id'] == prior['source_id'])
    origin=context.get('parent_refutation_origin')
    if origin:
        prior=origin['original_proposal']
    result = evaluate(source, prior)
    observation = feedback_observation(result)
    if (result.get('status') != 'refuted' or submitted.get('report_sha256') != observation.get('report_sha256')
            or submitted.get('report_sha256') != context.get('feedback', {}).get('measurement_observation', {}).get('report_sha256')):
        raise InvalidExperiment([{'path':'/hypothesis','code':'independent_refutation_not_established',
            'guidance':'Refutation requires the unchanged prediction and its independently replayed contradictory measurement.'}])
    raise VerifiedRefutation({'original_proposal':prior,'original_proposal_sha256':digest(prior),
        **({'parent_origin':origin} if origin else {}),
        'diagnosis':submitted['diagnosis'],'measurement':result,'scope':'original_cached_comparison_only',
        'acceptance':'independent_review_required','adoption_credit':False,'allowance_added':0,
        'unresolved_findings':list(requirements(context).values())}, result)


def review_refutation(root, refutation_id: str, *, reviewer: str, evidence_reference: str) -> dict[str, Any]:
    """Acknowledge a reproduced negative result without opening any work or budget."""
    from . import research_procedures as records
    from .research_tools import read_json, write_json
    from .question_measurements import evaluate
    from .lesson_review_budget import charge
    if any(not isinstance(v,str) or not 16 <= len(v) <= 1600 for v in (reviewer,evidence_reference)):
        raise ValueError('independent_refutation_review_required')
    refutation=records.read(root,'question_refutations',refutation_id)
    pointer=root/'research_methods/question_refutation_review_latest'/(refutation_id+'.json')
    previous=read_json(pointer)
    if previous:return records.read(root,'question_refutation_reviews',previous['review_id'])
    episode=records.read(root,'learning_episodes',refutation['episode_id'])
    attempt=records.read(root,'attempts',refutation['original_attempt_id'])
    owner=episode['id']
    if refutation.get('parent_origin'):
        origin=refutation['parent_origin'];owner=origin['parent_episode_id']
        sources=[s for s in episode.get('frozen_question_choices',[]) if s.get('failure_followup',{}).get('review_id')==origin['review_id']]
        if len(sources)!=1 or sources[0]['failure_followup'].get('refutation_origin')!=origin:
            raise ValueError('owned_reviewed_parent_refutation_required')
    if (attempt['learning_episode_id']!=owner or attempt['response']!=refutation['original_proposal']
            or digest(attempt['response'])!=refutation['original_proposal_sha256']):
        raise ValueError('immutable_owned_original_prediction_required')
    source=sources[0] if refutation.get('parent_origin') else next(s for s in episode['frozen_question_choices'] if s['id']==attempt['response']['source_id'])
    measured=evaluate(source,attempt['response'])
    if measured.get('status')!='refuted' or measured!=refutation['measurement']:
        raise ValueError('independent_refutation_not_reproduced')
    with charge(root,episode):
        result=records.store(root,'question_refutation_reviews',{'refutation_id':refutation_id,
            'refutation_sha256':digest(refutation),'reviewer':reviewer,'evidence_reference':evidence_reference,
            'decision':'acknowledge_scoped_refutation','adoption_credit':False,'allowance_added':0,
            'scope':refutation['scope'],'unresolved_findings':refutation['unresolved_findings']})
    write_json(pointer,{'review_id':result['id']})
    return result

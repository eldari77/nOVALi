"""Lossless working projections and finite leaf edits for question correction."""
from __future__ import annotations

import copy
from typing import Any
from .research_tools import digest

VERSION = 'question_focus_v1'
LEAVES = tuple('/method/'+operation+'/'+field for operation in
    ('baseline_operation','changed_operation') for field in ('action','check'))


def validate_review_findings(findings: Any) -> None:
    from .practice_experiments import FIELDS
    allowed={'/measurement'}|{'/'+k for k in FIELDS}|{'/method','/hypothesis','/execution_scope'}|set(LEAVES)
    if (not isinstance(findings,list) or not 1<=len(findings)<=10 or any(
        not isinstance(f,dict) or set(f)!={'path','code','guidance'} or f.get('path') not in allowed or
        not isinstance(f.get('code'),str) or not 3<=len(f['code'])<=100 or
        not isinstance(f.get('guidance'),str) or not 16<=len(f['guidance'])<=480 for f in findings)):
        raise ValueError('bounded_field_specific_semantic_findings_required')


def value_at(value: Any, path: str) -> Any:
    for key in path.lstrip('/').split('/'):
        if not isinstance(value,dict): return None
        value=value.get(key)
    return value


def assign(value: dict[str, Any], path: str, replacement: Any) -> None:
    keys=path.lstrip('/').split('/'); target=value
    for key in keys[:-1]: target=target[key]
    target[keys[-1]]=copy.deepcopy(replacement)


def paths(context: dict[str, Any], offered: list[str]) -> list[str]:
    prior=context.get('previous_proposal',{})
    method=prior.get('method')
    from .question_repair import method_findings
    structural=any(f['code']=='structured_operations_required' for f in method_findings(method))
    result=[]
    for path in offered:
        if path=='/method' and not structural and not context.get('measurement_contract'): result.extend(LEAVES)
        else: result.append(path)
    return sorted(set(result))


def findings(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map a known diagnostic's subject to a finite editable path."""
    result=[]
    for original in issues:
        item=copy.deepcopy(original)
        if item.get('path')=='/method' and item.get('code') in {'unfinished_operation','operation_format_requires_prose'}:
            subject=item.get('guidance','').split(' ',1)[0]
            path=item.get('subject') or '/method/'+subject.replace('.','/')
            if path in LEAVES:item['path']=path
        result.append(item)
    named={f['path'] for f in result if f.get('code')=='unfinished_operation' and f['path'] in LEAVES}
    if len(named)==1:
        for item in result:
            if item.get('path')=='/method' and item.get('code')=='incomplete_explanation':item['path']=next(iter(named))
    from .question_feedback import canonical
    return canonical({"field_issues":result})["field_issues"]


def project(context: dict[str, Any]) -> dict[str, Any]:
    result=copy.deepcopy(context)
    # Follow-ups are selected singly before reservation. Do not merge unrelated baselines.
    followups=[c for c in result['choices'] if c.get('failure_followup')]
    if followups and len(result['choices'])!=1: raise ValueError('single_followup_projection_required')
    for choice in followups:
        original=choice['failure_followup']
        if 'previous_proposal' not in original: continue  # already projected
        prior=copy.deepcopy(original.get('previous_proposal'))
        if isinstance(prior,dict):
            if result.get('diagnosis_contract'):
                # The reviewed successor binds the same frozen obligation plus its
                # review. Rebind only that owned source identity, not authored work.
                prior['source_id']=choice['id']
                result['selected_source_id']=choice['id']
            if isinstance(prior.get('method'),dict):
                prior.pop('method_before',None);prior.pop('method_after',None)
            for key in ('input_scope','field_batches','scope_mode'):prior.pop(key,None)
        if not result.get('previous_proposal'):
            result['previous_proposal']=prior
            result['feedback']={'field_issues':copy.deepcopy(original['field_issues'])}
            if result.get('diagnosis_contract') and original.get('refutation_origin'):
                result['parent_refutation_origin']=copy.deepcopy(original['refutation_origin'])
                result['feedback']['measurement_observation']=copy.deepcopy(original['measurement_observation'])
        choice['failure_followup']={k:original[k] for k in
            ('review_id','parent_episode_id','repair_kind','retained_costs','maximum_followups')}
        choice['failure_followup']['reference_sha256']=digest(original)
        # The immutable review resolves the full prior, diagnostics and phase receipts.
        timing={}
        for row in original.get('phase_measurements',[]):
            for phase,seconds in row.get('timing',{}).items():
                if type(seconds) in (int,float):timing.setdefault(phase,[]).append(seconds)
        if timing:choice['failure_followup']['phase_ranges_seconds']={k:[min(v),max(v)] for k,v in timing.items()}
    prior=result.get('previous_proposal')
    if isinstance(prior,dict):
        aliases={v.get('id',k):k for k,v in result.get('failure_evidence',{}).items()}
        h=prior.get('hypothesis',{})
        if isinstance(h,dict):h['evidence_ids']=[aliases.get(k,k) for k in h.get('evidence_ids',[])]
        if result.get('diagnosis_contract') and isinstance(h,dict):
            # A repair retains its cited evidence and every finding-specific
            # reference. Unrelated authoring opportunities are not repair input.
            needed=set(h.get('evidence_ids',[]))
            needed.update(aliases.get(f['evidence_id'],f['evidence_id']) for f in
                result.get('feedback',{}).get('field_issues',[]) if f.get('evidence_id'))
            if needed:
                result['failure_evidence']={k:v for k,v in result.get('failure_evidence',{}).items() if k in needed}
    from .question_feedback import canonical
    result['feedback']=canonical(result.get('feedback',{}),result.get('finding_guidance',{}))
    feedback=result['feedback']
    if feedback.get('field_issues'):
        from .question_repair import expand_findings
        feedback['field_issues']=findings(expand_findings(feedback['field_issues'],prior or {}))
        # One copy per repeated guidance; every path/code and original finding survives.
        guidance={}
        for item in feedback['field_issues']:
            if item.get('guidance'):
                text=item.pop('guidance');key='g'+digest(text)[:8]
                if key in guidance and guidance[key]!=text:raise ValueError('ambiguous_guidance_reference')
                guidance[key]=text;item['guidance_ref']=key
        if guidance:result['finding_guidance']=guidance
    result['input_bindings']={'selected_obligation':'obligation selected by source_id; use its target_artifact and unit without repeating paths'}
    # Immutable evidence IDs already resolve review, scope and full measurements.
    # Keep the observations and actual values; omit duplicated provenance envelopes.
    for item in result.get('failure_evidence',{}).values():
        item.pop('metadata',None)
        item.pop('measurement_reference',None)
    result['failure_evidence_metadata']={}
    result.pop('failure_evidence_scopes',None)
    result['evidence_scope']='Reviewed historical failure mechanisms, not current results. Evidence IDs resolve their full reviewed records.'
    return result

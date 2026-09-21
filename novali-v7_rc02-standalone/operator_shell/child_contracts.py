"""Bounded work units, explicit evidence subjects and replayable child corrections."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from . import research_learning
from .research_tools import digest, read_json

VERSION = 'child_work_units_v2'
PARAMETERS = {'record_extraction': ['record_id', 'required_fields'],
              'evidence_binding': ['evidence_handle', 'subject_ref'],
              'interface_contract': ['target_artifact', 'fixture_ref']}


def citation_windows(observations: list[dict[str, Any]], targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expose contiguous cached context around existing anchors, without new evidence."""
    research_learning.evidence_options(observations)  # Validate the same bounded original observations.
    windows = []
    for row in observations[:12]:
        if not row.get('ok'): continue
        result = row.get('result', {}); text = str(result.get('text', ''))[:4000]
        revision = digest(result)
        for target in targets:
            if row['action_id'] not in target['action_ids']: continue
            for anchor in target['anchors']:
                if not isinstance(anchor, str) or len(anchor) < 8: continue
                offset = text.find(anchor)
                if offset < 0: continue  # Missing text stays missing; never reconstruct an anchor.
                start = max(0, offset - 32); end = min(len(text), offset + min(len(anchor), 400) + 32)
                window = {'handle': 'evidence-' + digest([row['action_id'], revision, 'child_citation_window_v1', start, end])[:24],
                    'action_id': row['action_id'], 'kind': 'text', 'text': text[start:end],
                    'scope': result.get('scope', 'unassessed'), 'result_sha256': revision,
                    'offset_chars': start, 'end_chars': end, 'retrieval': 'contiguous_original_cached_text'}
                if window not in windows: windows.append(window)
                if len(windows) >= 12: return windows
    return windows


def refine(root: Path, frozen: dict[str, Any]) -> dict[str, Any]:
    """Split work without granting another attempt at already selected coverage."""
    from .directive_obligations import content
    state = read_json(root/'conveyor/research/episodes'/frozen['parent_episode_id']/'state.json')
    originals = frozen['obligations']; units = []
    fields = frozen['required_fields'] + frozen['unprojected_required_fields']
    raw = content(root, frozen['directive_id'], frozen['target_artifact'])
    table = []
    if frozen['target_artifact'].endswith('.json'):
        data = json.loads(raw)
        if not isinstance(data,dict): raise ValueError('bounded_object_artifact_required')
        for key, value in data.items():
            if key == 'novali_research_addenda' or not isinstance(value, list): continue
            table = [{'row_id': '/'+key.replace('~','~0').replace('/','~1')+'/'+str(i), 'record': row}
                     for i,row in enumerate(value) if isinstance(row,dict)]
            if table: break
    frozen['records'] = table
    frozen['work_contract'] = VERSION
    from .learning_evidence import context as learning_context
    frozen['reviewed_failure_patterns'] = learning_context(root)
    for original in originals:
        if original['adapter'] == 'record_extraction':
            for row in table:
                for offset in range(0,len(fields),12):
                    unit = {'row_id':row['row_id'], 'fields':fields[offset:offset+12]}
                    body = {**original, 'unit':unit}
                    body['id'] = 'obligation-'+digest([VERSION,original['id'],unit])[:24]
                    units.append(body)
        else: units.append(original)
    frozen['obligations'] = units
    rejected = state.get('last_rejected_response', {})
    if (frozen['prior_research_feedback']['field_issues'] and isinstance(rejected,dict)
            and isinstance(rejected.get('claims'),list) and state.get('plan')):
        replay = {'plan':state['plan'],'observations':state.get('observations',[]),'interpretation':rejected}
        # Do not present a partial replay as an original-verifier success.
        if len(json.dumps(replay).encode()) <= 60000:
            frozen['citation_replay'] = replay
            targets = []
            for i,claim in enumerate(rejected['claims']):
                if claim.get('kind')!='observation': continue
                refs = claim.get('evidence_refs',[])
                targets.append({'claim_index':i, 'text':claim['text'],
                    'anchors':[r.get('text','') for r in refs if isinstance(r,dict)] or [claim.get('quote','')],
                    'action_ids':[r.get('action_id') if isinstance(r,dict) else r for r in refs]})
            frozen['repair_targets'] = targets
            all_options = research_learning.evidence_options(replay['observations'])
            linked = [e for e in all_options if e['kind']=='text' and any(e['action_id'] in t['action_ids'] for t in targets)]
            from .child_directive_learning import policy
            if policy(root).get('repair_interface_enabled'):
                linked = citation_windows(replay['observations'], targets) + linked
            # Retain all bounded cached choices from the original verifier, not just the first observation.
            frozen['evidence_options'] = linked[:32]
            for o in units:
                if o['adapter']=='evidence_binding':
                    o['unit']={'claim_indices':[t['claim_index'] for t in targets]}
                    o['objective']='Repair the original rejected citations; preserve claims and replay their original verifier.'
                    available=all(any(e['action_id'] in t['action_ids'] and any(
                        anchor[start:start+8] in e['text'] for anchor in t['anchors'] for start in range(max(0,len(anchor)-7)))
                        for e in linked[:32]) for t in targets)
                    o['eligible']=bool(linked and targets and available)
                    if not o['eligible']: o['blocked_reason']='original_citation_anchor_not_in_cached_choices'
        else:
            for o in units:
                if o['adapter']=='evidence_binding':
                    o.update(eligible=False,blocked_reason='original_verifier_replay_exceeds_bounded_input_limit')
    frozen['evidence_subjects'] = []
    if not frozen.get('repair_targets'):
        for e in frozen['evidence_options']:
            if e['kind']!='text': continue
            matches = []
            for row in table:
                for field,value in row['record'].items():
                    if isinstance(value,str) and 8<=len(value)<=400 and value in e['text']:
                        matches.append({'subject_ref':row['row_id']+'/'+field, 'literal':value, 'evidence_handle':e['handle']})
            if matches: frozen['evidence_subjects'].extend(matches)
            elif not table:
                frozen['evidence_subjects'].append({'subject_ref':frozen['target_artifact'], 'literal':e['text'], 'evidence_handle':e['handle']})
        if not frozen['evidence_subjects']:
            for o in units:
                if o['adapter']=='evidence_binding':
                    o.update(eligible=False,blocked_reason='matching_cached_subject_evidence_unavailable')
    from .child_directive_learning import policy
    if policy(root).get('repair_interface_enabled'):
        from .child_repairs import VERSION as REPAIRS
        frozen['repair_contract'] = REPAIRS
        frozen['permitted_context_profiles'] = policy(root).get('context_profiles', ['full', 'focused'])
        frozen['initial_context_profile'] = frozen['permitted_context_profiles'][0]
        if policy(root).get('research_tools_enabled'):
            from .child_research_actions import VERSION as TOOLS
            from .child_measurements import freeze
            frozen['research_tools_contract']=TOOLS
            frozen['measurement_inputs']=freeze(root,frozen) if any(o['adapter']=='interface_contract' for o in units) else []
            if policy(root).get('growth_enabled'):
                from .child_planning import VERSION as GROWTH
                frozen['growth_contract']=GROWTH
                if policy(root).get('correction_enabled'):
                    from .child_correction import VERSION as CORRECTION
                    frozen['correction_contract']=CORRECTION
                    if policy(root).get('procedure_execution_enabled'):
                        from .child_execution import VERSION as EXECUTION
                        frozen['procedure_execution_contract']=EXECUTION
                    if policy(root).get('relevance_enabled'):
                        from .child_relevance import VERSION as RELEVANCE
                        frozen['relevance_contract']=RELEVANCE
    return frozen


def coverage(candidate: dict[str, Any], obligation: dict[str, Any]) -> bool:
    response=candidate.get('response',{}); payload=response.get('payload',{})
    method=response.get('method',{})
    if not isinstance(payload,dict) or not isinstance(method,dict) or method.get('adapter') != obligation['adapter']: return False
    unit=obligation.get('unit',{})
    if obligation['adapter']=='record_extraction':
        fields=payload.get('fields',[])
        return (isinstance(fields,list) and payload.get('row_id')==unit.get('row_id') and set(unit.get('fields',[])) <=
                {f.get('field') for f in fields if isinstance(f,dict) and isinstance(f.get('field'),str)})
    return True


def project(frozen: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Offer at most four work units and only their record values; keep parked work in status."""
    context['work_contract']=VERSION
    eligible=[o for o in context['obligations'] if o['eligible']][:4]
    context['obligations']=eligible
    rows={o.get('unit',{}).get('row_id') for o in eligible}
    context['records']=[{'row_id':r['row_id'],'record':{k:v for k,v in r['record'].items() if any(
        o.get('unit',{}).get('row_id')==r['row_id'] and k in o['unit']['fields'] for o in eligible)}}
        for r in frozen['records'] if r['row_id'] in rows]
    context['repair_targets']=frozen.get('repair_targets',[])
    context['evidence_subjects']=frozen.get('evidence_subjects',[])
    context['required_fields']=list(dict.fromkeys(f for o in eligible for f in o.get('unit',{}).get('fields',[])))
    context['unprojected_required_fields']=[]
    context['remaining_work_units']=len([o for o in frozen['obligations'] if o['eligible']])-len(eligible)
    context['method_parameters']=PARAMETERS
    if frozen.get('revision_review'):
        context['revision_review']=frozen['revision_review']
        context['previous_candidate']=frozen['revision_candidate']['response']
    # Reviewed patterns are supplied by the caller; no lookup against a guessed live root.
    context['reviewed_failure_patterns']=frozen.get('reviewed_failure_patterns',[])
    return context


def check(context: dict[str, Any], response: dict[str, Any], issue) -> None:
    if context.get('work_contract')!=VERSION: return
    selected=next((o for o in context['obligations'] if o['id']==response.get('obligation_id')),None)
    if not selected: return
    method=response.get('method',{}); adapter=selected['adapter']; payload=response.get('payload',{})
    if not isinstance(method,dict) or not isinstance(payload,dict): return  # The outer validator already reports these typed-field errors.
    expected=PARAMETERS[adapter]
    typed_method = method.get('representation') in {'child_parameter_bindings_v1','child_measurement_program_v1','child_artifact_program_v1'}
    applicability=method.get('applicability',{})
    if not typed_method and (not isinstance(applicability,dict) or set(applicability)!={'input_kind','parameters','unknown_behavior'}
            or applicability.get('input_kind')!=adapter or applicability.get('parameters')!=expected
            or applicability.get('unknown_behavior')!='recheck_and_stop'):
        issue('/method/applicability','current_input_applicability_contract_required',expected,applicability)
    steps=method.get('steps',[])
    if isinstance(steps,list) and not typed_method:
        joined=' '.join(s for s in steps if isinstance(s,str))
        if any('{'+parameter+'}' not in joined for parameter in expected):
            issue('/method/steps','parameterized_current_inputs_required',expected,joined)
        if re.search(r'(?:evidence|obligation|child_candidate)-[a-zA-Z0-9]{8,}|(?:drafts|canonical)/[a-zA-Z0-9_]',joined):
            issue('/method/steps','historical_bindings_are_not_reusable_parameters')
    for path,text,limit in [('/rationale',response.get('rationale'),256)]+[
            ('/method/steps/'+str(i),s,200) for i,s in enumerate(steps if isinstance(steps,list) else [])]:
        if isinstance(text,str) and (text.count('`')%2 or len(text)>=limit and not text.rstrip().endswith(('.', '!', '?'))):
            issue(path,'incomplete_bounded_text_rephrase_concisely',None,text)
    if adapter=='evidence_binding' and not context.get('repair_targets'):
        matches=[s for s in context['evidence_subjects'] if s['subject_ref']==payload.get('subject_ref')
                 and s['evidence_handle']==payload.get('evidence_handle')]
        if not matches or not any(isinstance(payload.get('quote'),str) and payload['quote'] in s['literal'] for s in matches):
            issue('/payload/subject_ref','quote_must_match_selected_source_subject',context['evidence_subjects'],payload.get('subject_ref'))


def check_repairs(context: dict[str, Any], payload: dict[str, Any], issue) -> None:
    repairs=payload.get('repairs',[]); targets=context['repair_targets']
    if set(payload)!={'repairs'} or not isinstance(repairs,list) or len(repairs)!=len(targets):
        issue('/payload/repairs','repair_every_original_observation_required'); return
    seen=[]; options={e['handle']:e for e in context['evidence_options']}
    for i,repair in enumerate(repairs):
        if not isinstance(repair,dict) or set(repair)!={'claim_index','evidence_handle','quote'}:
            issue('/payload/repairs/'+str(i),'typed_original_citation_repair_required'); continue
        target=next((t for t in targets if type(repair['claim_index']) is int and t['claim_index']==repair['claim_index']),None)
        option=options.get(repair['evidence_handle']) if isinstance(repair['evidence_handle'],str) else None
        quote=repair['quote']
        if type(repair['claim_index']) is int: seen.append(repair['claim_index'])
        else: issue('/payload/repairs/'+str(i)+'/claim_index','original_integer_claim_index_required')
        if (not target or not option or option['action_id'] not in target['action_ids'] or not isinstance(quote,str)
                or not 8<=len(quote)<=400 or quote not in option['text']
                or not any(quote in anchor for anchor in target['anchors'])):
            issue('/payload/repairs/'+str(i),'retain_original_claim_evidence_and_literal_anchor',target,repair)
    if sorted(seen)!=sorted(t['claim_index'] for t in targets): issue('/payload/repairs','unique_original_claim_indices_required')


def replay(frozen: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    if not frozen.get('citation_replay') or response['method']['adapter']!='evidence_binding': return {}
    from .research_episodes import verify_result
    original=frozen['citation_replay']; revised=copy.deepcopy(original['interpretation'])
    options={e['handle']:e for e in frozen['evidence_options']}
    for repair in response['payload']['repairs']:
        claim=revised['claims'][repair['claim_index']]
        claim.pop('evidence_handle',None)
        claim.update(evidence_refs=[options[repair['evidence_handle']]['action_id']],quote=repair['quote'])
    submitted=copy.deepcopy(revised)
    verification=verify_result(original['plan'],original['observations'],revised)
    return {'original_verifier_passed':True,'original_input_sha256':digest(original),
            'revised_interpretation':submitted,'verification':verification,
            'scope':'original_citation_validation_only_not_claim_semantic_truth'}

"""Select cached spans without retyping their bytes or manufacturing provenance."""
from __future__ import annotations
from typing import Any
from .research_tools import digest


def options(context: dict[str, Any]) -> list[dict[str, Any]]:
    literals=[a for t in context.get('repair_targets',[]) for a in t['anchors']]
    literals += [s['literal'] for s in context.get('evidence_subjects',[])]
    result=[]
    for source in context.get('evidence_options',[]):
        if source['kind']!='text':continue
        origin=source.get('offset_chars')
        if origin is None:
            origin=next((n for n in range(0,1600,160) if source['handle']=='evidence-'+digest(
                [source['action_id'],source['result_sha256'],'text',str(n)])[:24]),None)
        if origin is None:continue
        # Include source fragments as distractors. Matching a cached passage is
        # distinct from selecting one that repairs the actual claim.
        texts=list(dict.fromkeys([s for s in literals if isinstance(s,str) and 8<=len(s)<=400 and s in source['text']]
            +([source['text']] if 8<=len(source['text'])<=400 else [])))
        for text in texts:
            start=source['text'].index(text)
            row={'source_id':source['handle'],'action_id':source['action_id'],'result_sha256':source['result_sha256'],
                'start_chars':origin+start,'end_chars':origin+start+len(text),'literal':text,
                'coordinate_space':'original_observation_text','scope':source['scope']}
            result.append({'span_id':'span-'+digest(row)[:24],**row})
    if len(result)>64:raise ValueError('evidence_selection_limit_preserve_required_bindings')
    return result


def resolve(context: dict[str, Any], selections: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from .directive_candidates import CandidateError
    targets=context.get('repair_targets',[])
    if not isinstance(selections,list) or len(selections)!=(len(targets) if targets else 1):
        raise CandidateError([{'path':'/selections','code':'select_every_required_claim_once'}])
    offered=options(context); receipts=[]; repairs=[]; seen=set(); payload={}
    for index,selected in enumerate(selections):
        required={'source_id','span_id','claim_index' if targets else 'subject_ref'}
        if not isinstance(selected,dict) or set(selected)!=required:
            raise CandidateError([{'path':f'/selections/{index}','code':'typed_cached_selection_required'}])
        span=next((s for s in offered if s['source_id']==selected['source_id'] and s['span_id']==selected['span_id']),None)
        if not span:raise CandidateError([{'path':f'/selections/{index}','code':'current_source_and_span_pair_required'}])
        if targets:
            claim=selected['claim_index']
            if type(claim) is not int or claim in seen or claim not in {t['claim_index'] for t in targets}:
                raise CandidateError([{'path':f'/selections/{index}/claim_index','code':'unique_original_claim_required'}])
            seen.add(claim);repairs.append({'claim_index':claim,'evidence_handle':span['source_id'],'quote':span['literal']})
        else:payload={'evidence_handle':span['source_id'],'quote':span['literal'],'subject_ref':selected['subject_ref']}
        receipts.append({**span,**{k:v for k,v in selected.items() if k not in {'source_id','span_id'}}})
    return ({'repairs':sorted(repairs,key=lambda r:r['claim_index'])} if targets else payload),receipts


def attest(context: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows=payload.get('repairs',[payload]); offered=options(context); receipts=[]
    for row in rows:
        span=next((s for s in offered if s['source_id']==row.get('evidence_handle') and s['literal']==row.get('quote')),None)
        if not span:raise ValueError('offered_literal_span_required')
        receipts.append({**span,**{k:row[k] for k in ('claim_index','subject_ref') if k in row}})
    return receipts

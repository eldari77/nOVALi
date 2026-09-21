"""Compose reviewed disjoint addenda and verify actual child writes separately from context delivery."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any
from . import research_procedures as records
from .research_tools import digest, read_json


def assert_reviewed_source_transition(root: Path, frozen: dict[str, Any]) -> None:
    """Permit failure reassessment after an owned, verified addendum write only.

    This does not authorize a stale candidate or mutate its evidence. The next
    episode rebuilds current dependencies before it can be admitted.
    """
    from .directive_obligations import content
    from .child_review import latest
    from .research_tools import identifier
    directory=root/'conveyor/research/episodes'/identifier(frozen['parent_episode_id'])
    if digest(read_json(directory/'contract.json'))!=frozen['parent_contract_sha256']:raise ValueError('child_parent_contract_changed')
    uses=None; checkouts=None; reviewed_cache={}
    for ref,old_sha in frozen['dependencies'].items():
        current=hashlib.sha256(content(root,frozen['directive_id'],ref)).hexdigest()
        if current==old_sha:continue
        if uses is None:
            uses=[records.read(root,'child_consumption',p.stem) for p in (root/'research_methods/child_consumption').glob('*.json')]
            checkouts=[c for p in (root/'conveyor/checkouts').glob('*.json') if (c:=read_json(p)).get('directive_id')==frozen['directive_id']]
        edges={}
        for checkout in checkouts:
            for row in checkout.get('reviewed_child_artifact_revisions',[]):
                if (row.get('target_artifact')!=ref or row.get('directive_id')!=frozen['directive_id']
                        or row.get('composition_version')!='reviewed_disjoint_addenda_v1'):continue
                source=row.get('source_sha256');destination=row.get('artifact_sha256')
                if not isinstance(source,str) or not isinstance(destination,str) or not row.get('parts'):continue
                approved=True
                for part in row['parts']:
                    cid=part['candidate_id']
                    if cid not in reviewed_cache:reviewed_cache[cid]=(latest(root,cid),records.read(root,'child_candidates',cid))
                    reviewed,candidate=reviewed_cache[cid]
                    approved=approved and reviewed.get('id')==part['review_id'] and reviewed.get('decision')=='approve' and any(
                        u.get('candidate_id')==part['candidate_id'] and u.get('review_id')==part['review_id']
                        and u.get('artifact_sha256')==destination and u.get('use')=='verified_resident_artifact_write' for u in uses)
                    approved=approved and candidate['base_sha256']==source and candidate['frozen']['directive_id']==frozen['directive_id']
                    approved=approved and candidate['frozen']['target_artifact']==ref
                if approved:edges.setdefault(source,set()).add(destination)
        # An earlier source may precede several consumed deliveries. Every edge
        # must have its own current review and verified intermediate write.
        # Visiting each recorded hash once also terminates cycles without treating
        # a shortcut, a context delivery or an unreviewed edit as evidence.
        reachable={old_sha};frontier=[old_sha]
        while frontier and current not in reachable:
            for successor in edges.get(frontier.pop(),set())-reachable:
                reachable.add(successor);frontier.append(successor)
        if current not in reachable:raise ValueError('unreviewed_child_source_transition:'+ref)


def delivery(root: Path, directive_id: str, *, consumer: str='', persist: bool=False) -> list[dict[str, Any]]:
    from . import directive_candidates as candidates, directive_obligations as obligations
    items=candidates._single_delivery(root,directive_id)
    # A reviewed correction supersedes its own predecessor, never unrelated work.
    predecessors={records.read(root,'child_candidates',i['candidate_id']).get('previous_candidate_id') for i in items}
    items=[i for i in items if i['candidate_id'] not in predecessors]
    grouped={}
    for item in items: grouped.setdefault(item['target_artifact'],[]).append(item)
    result=[]
    for target,parts in sorted(grouped.items()):
        parts=sorted(parts,key=lambda p:p['addendum']['obligation_id'])
        if len({p['source_sha256'] for p in parts})!=1 or len({p['addendum']['obligation_id'] for p in parts})!=len(parts):
            continue  # A conflicting slot requires explicit supersession; no implicit winner.
        base=obligations.content(root,directive_id,target); output=base; dependencies={}
        for item in parts:
            dependencies.update(item['dependencies'])
            output=candidates.render(output,target,item['addendum']['obligation_id'],item['addendum'])
        # Bound the complete change relative to its original base, not only each step.
        if len(output)>80000 or len(output)-len(base)>14000: continue
        attestation={'directive_id':directive_id,'dependencies':dependencies,
                     'reviews':[i['review_id'] for i in parts]}
        # Each source was rechecked by _single_delivery immediately before this kernel checkout.
        row={**parts[0], 'composition_version':'reviewed_disjoint_addenda_v1','parts':parts,
             'artifact_sha256':hashlib.sha256(output).hexdigest(),'dependencies':dependencies,
             'kernel_dependency_attestation':{**attestation,'sha256':digest(attestation)}}
        if len(json.dumps([*result,row]).encode())>64000: break
        result.append(row)
        if persist:
            if not consumer.strip(): raise ValueError('named_downstream_consumer_required')
            records.store(root,'child_context_deliveries',{'consumer':consumer,'directive_id':directive_id,
                'candidate_ids':[i['candidate_id'] for i in parts],'artifact_sha256':row['artifact_sha256'],
                'scope':'context_only_no_completed_work_or_reuse_credit'})
    return result


def reconcile_use(root: Path, child: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    """Kernel-owned checkout and campaign paths, never paths submitted in planner output."""
    from .research_tools import identifier
    try:
        did=identifier(child['directive_id']); checkout_id=identifier(child['checkout_id'])
        checkout=read_json(root/'conveyor/checkouts'/(checkout_id+'.json'))
        if checkout.get('directive_id')!=did: raise ValueError('owned_directive_checkout_required')
        # Resident children write the campaign draft mount. They cannot select another workspace here.
        workspace=root/'conveyor/campaigns'/did/'drafts'
        uses=record_use(root,did,receipt,workspace=workspace,consumer=identifier(child['child_run_id']),checkout=checkout)
        return {'state':'verified_artifact_write','receipt_ids':[r['id'] for r in uses], 'research_success_demonstrated':False}
    except (ValueError, KeyError, OSError, TypeError) as exc:
        return {'state':'unverified','reason':str(exc)[:500],'research_success_demonstrated':False}


def materialize(checkout: dict[str, Any], workspace: Path, target: str) -> dict[str, Any] | None:
    from .directive_candidates import render
    rows=[r for r in checkout.get('reviewed_child_artifact_revisions',[]) if r.get('directive_id')==checkout.get('directive_id')
          and r.get('target_artifact')=='drafts/'+target]
    if not rows: return None
    if len(rows)!=1: raise ValueError('conflicting_reviewed_child_revisions_require_review')
    row=rows[0]; parts=row['parts']; attestation=row.get('kernel_dependency_attestation',{})
    expected={'directive_id':row['directive_id'],'dependencies':row['dependencies'],'reviews':[p['review_id'] for p in parts]}
    if attestation!={**expected,'sha256':digest(expected)}: raise ValueError('current_kernel_dependency_attestation_required')
    if (Path(target).name!=target or not target.endswith(('.json','.md')) or not 1<=len(parts)<=12
            or len({p['addendum']['obligation_id'] for p in parts})!=len(parts)):
        raise ValueError('bounded_unique_reviewed_composition_required')
    path=workspace/target
    if path.is_symlink() or not path.is_file() or path.stat().st_size>80000: raise ValueError('existing_child_base_required')
    base=path.read_bytes(); sha=hashlib.sha256(base).hexdigest()
    if sha not in (row['source_sha256'],row['artifact_sha256']): raise ValueError('child_revision_base_changed')
    for ref,expected_sha in row['dependencies'].items():
        if ref=='drafts/'+target: continue
        # Canonical inputs are read-only kernel attestations, not writable child aliases.
        if ref.startswith('canonical/'):
            if len(Path(ref).parts)!=2: raise ValueError('bounded_canonical_dependency_required')
            continue
        if not ref.startswith('drafts/') or len(Path(ref).parts)!=2: raise ValueError('bounded_dependency_required')
        dep=workspace/Path(ref).name
        if dep.is_symlink() or not dep.is_file() or dep.stat().st_size>64000 or hashlib.sha256(dep.read_bytes()).hexdigest()!=expected_sha:
            raise ValueError('child_dependency_changed:'+ref)
    if sha==row['source_sha256']:
        output=base
        for part in parts:
            if part['source_sha256']!=sha: raise ValueError('composition_source_disagreement')
            output=render(output,target,part['addendum']['obligation_id'],part['addendum'])
        if len(output)>80000 or len(output)-len(base)>14000 or hashlib.sha256(output).hexdigest()!=row['artifact_sha256']:
            raise ValueError('reviewed_composition_output_changed')
        temporary=path.with_suffix(path.suffix+'.revision.tmp');temporary.write_bytes(output);temporary.replace(path)
    receipt={'candidate_id':parts[0]['candidate_id'],'review_id':parts[0]['review_id'],
        'candidate_ids':[p['candidate_id'] for p in parts],'review_ids':[p['review_id'] for p in parts],
        'artifact_sha256':row['artifact_sha256'],'target_artifact':target,'changed':sha!=row['artifact_sha256'],
        'consumer':'resident_child_artifact_writer','scientific_claim_verified':False,'canonical_promotion_authorized':False}
    return {'claim_count':0,'novelty_count':0,'technical_depth_contract_passed':False,
        'remaining_failed_gates':['existing_support_acceptance_and_operator_review'],'reviewed_child_revision_consumed':receipt}


def record_use(root: Path, directive_id: str, receipt: dict[str, Any], *, workspace: Path, consumer: str, checkout: dict[str, Any]) -> list[dict[str, Any]]:
    """A context receipt cannot call this path: validate the materialized bytes and all current reviews."""
    from .child_review import latest
    if not consumer.strip() or receipt.get('consumer')!='resident_child_artifact_writer': raise ValueError('actual_child_receipt_required')
    target=receipt.get('target_artifact','')
    if Path(target).name!=target or not target: raise ValueError('bounded_child_target_required')
    path=workspace/target
    if path.is_symlink() or not path.is_file() or path.stat().st_size>80000 or hashlib.sha256(path.read_bytes()).hexdigest()!=receipt.get('artifact_sha256'):
        raise ValueError('actual_child_artifact_hash_required')
    ids=receipt.get('candidate_ids',[receipt.get('candidate_id')]); reviews=receipt.get('review_ids',[receipt.get('review_id')])
    if not 1<=len(ids)<=12 or len(ids)!=len(reviews) or len(set(ids))!=len(ids): raise ValueError('bounded_owned_consumption_required')
    manifests=[r for r in checkout.get('reviewed_child_artifact_revisions',[]) if r.get('directive_id')==directive_id
        and r.get('target_artifact')=='drafts/'+target and r.get('artifact_sha256')==receipt['artifact_sha256']
        and [p['candidate_id'] for p in r.get('parts',[r])]==ids and [p['review_id'] for p in r.get('parts',[r])]==reviews]
    if len(manifests)!=1: raise ValueError('owned_kernel_checkout_receipt_required')
    result=[]
    for candidate_id,review_id in zip(ids,reviews):
        candidate=records.read(root,'child_candidates',candidate_id); reviewed=latest(root,candidate_id)
        if candidate['frozen']['directive_id']!=directive_id or reviewed.get('id')!=review_id or reviewed.get('decision')!='approve':
            raise ValueError('current_approved_candidate_required')
        # Check that the current file contains this exact reviewed addendum, not merely a reported hash.
        addendum=candidate['artifact_change']['after']; slot=addendum['obligation_id']; raw=path.read_text()
        if target.endswith('.json'):
            if json.loads(raw).get('novali_research_addenda',{}).get(slot)!=addendum: raise ValueError('reviewed_addendum_missing')
        elif json.dumps(addendum,indent=2,sort_keys=True,ensure_ascii=False) not in raw: raise ValueError('reviewed_addendum_missing')
        result.append({'candidate_id':candidate_id,'review_id':review_id,
            'consumer':consumer,'artifact_sha256':receipt['artifact_sha256'],'use':'verified_resident_artifact_write',
            'research_success_demonstrated':False,'support_acceptance':'not_established_by_artifact_write'})
    return [records.store(root,'child_consumption',body) for body in result]

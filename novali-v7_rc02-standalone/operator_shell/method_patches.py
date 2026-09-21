"""Typed replacement patches over a retained proposal; never generated repairs."""
from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from . import executable_measurement, method_contracts
from .planner_authoring import _object
from .research_tools import digest


class PatchError(ValueError):
    def __init__(self, reason: str, path: str):
        super().__init__(reason)
        self.field_issues=[{'field':path,'reason':reason}]


def _valid(value: Any, spec: Mapping[str, Any]) -> bool:
    if 'const' in spec and value != spec['const']:
        return False
    if 'enum' in spec and value not in spec['enum']:
        return False
    kind = spec.get('type')
    if kind == 'object':
        return type(value) is dict and set(value) == set(spec['properties']) and all(
            _valid(value[k], v) for k, v in spec['properties'].items())
    if kind == 'array':
        return type(value) is list and spec.get('minItems', 0) <= len(value) <= spec.get('maxItems', 64) and all(
            _valid(v, spec['items']) for v in value)
    if kind == 'string':
        return type(value) is str and spec.get('minLength', 0) <= len(value.strip()) <= spec.get('maxLength', 256)
    if kind == 'boolean':
        return type(value) is bool
    if kind in {'integer', 'number'}:
        if type(value) not in ((int,) if kind == 'integer' else (int, float)):
            return False
        try:
            return math.isfinite(value) and spec.get('minimum', -float('inf')) <= value <= spec.get('maximum', float('inf'))
        except OverflowError:
            return False
    return False


def base_proposal(original: Mapping[str, Any], previous: Any = None) -> dict[str, Any] | None:
    base = previous.get('proposal') if isinstance(previous, dict) else None
    base = base or original.get('proposal', original.get('fixture'))
    schema = method_contracts.schema() if original['kind'] == 'method_capability' else executable_measurement.schema()
    return copy.deepcopy(base) if _valid(base, schema) else None


def fields(original: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    """The frozen measurement spec is never a patch target."""
    schema = method_contracts.schema() if original['kind'] == 'method_capability' else executable_measurement.schema()
    prefix = '/acceptance' if original['kind'] == 'method_capability' else ''
    section = schema['properties']['acceptance'] if prefix else schema
    source = base['acceptance'] if prefix else base
    result = {}
    if prefix:
        for name, shape in section['properties'].items():
            if name == 'cases': continue
            if name == 'limits':
                result.update({prefix+'/limits/'+k: v for k,v in shape['properties'].items()})
            else: result[prefix+'/'+name] = shape
    for index in range(len(source['cases'])):
        for name, shape in section['properties']['cases']['items']['properties'].items():
            result[f'{prefix}/cases/{index}/{name}'] = shape
    return result


def schema(original: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    alternatives = [_object({'path': {'type':'string','const':path}, 'value':shape})
                    for path,shape in fields(original,base).items()]
    return _object({'base_sha256': {'type':'string','const':digest(base)},
        'edits': {'type':'array','minItems':1,'maxItems':8,'items':{'anyOf':alternatives}}})


def _apply(original: Mapping[str, Any], base: Mapping[str, Any], patch: Mapping[str, Any], *, reject_noop: bool) -> dict[str, Any]:
    if type(patch) is not dict or set(patch) != {'base_sha256','edits'} or patch['base_sha256'] != digest(base):
        raise PatchError('patch_requires_exact_retained_proposal','patch.base_sha256')
    edits=patch['edits']
    if type(edits) is not list or not 1 <= len(edits) <= 8:
        raise ValueError('one_to_eight_focused_edits_required')
    allowed=fields(original,base); result=copy.deepcopy(base); seen=set()
    for index,edit in enumerate(edits):
        if type(edit) is not dict or set(edit) != {'path','value'} or not isinstance(edit['path'],str):
            raise PatchError('typed_replacement_edit_required',f'patch.edits[{index}]')
        path=edit['path']
        if path not in allowed or path in seen or not _valid(edit['value'],allowed[path]):
            raise PatchError('unique_allowed_typed_patch_field_required',f'patch.edits[{index}]:{path}')
        seen.add(path); keys=path[1:].split('/'); node=result
        for key in keys[:-1]: node=node[int(key)] if isinstance(node,list) else node[key]
        key=int(keys[-1]) if isinstance(node,list) else keys[-1]
        node[key]=copy.deepcopy(edit['value'])
    if reject_noop and result == base:
        raise PatchError('changed_patch_value_required','patch.edits')
    return result


def apply(original: Mapping[str, Any], base: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    return _apply(original, base, patch, reject_noop=True)


def effects(original: Mapping[str, Any], base: Mapping[str, Any], patch: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Describe validated edits, including no-ops, without selecting replacements."""
    result = _apply(original, base, patch, reject_noop=False)
    rows = []
    for edit in patch['edits']:
        before, after = base, result
        for key in edit['path'][1:].split('/'):
            before = before[int(key)] if isinstance(before, list) else before[key]
            after = after[int(key)] if isinstance(after, list) else after[key]
        rows.append({'path': edit['path'], 'before': before, 'after': after,
                     'changed': before != after})
    return rows


def validate_resolutions(bindings: Any, findings: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    changed = {row['path'] for row in rows if row['changed']}
    if not isinstance(bindings, dict) or set(bindings) != {f['code'] for f in findings}:
        raise PatchError('resolution_requires_finding_edit_binding', 'resolution_edits')
    for code, paths in bindings.items():
        if (not isinstance(paths, list) or not 1 <= len(paths) <= 8
                or any(not isinstance(path, str) or path not in changed for path in paths)
                or len(set(paths)) != len(paths)):
            raise PatchError('resolution_requires_changed_edit', 'resolution_edits.' + code)


def feedback_paths(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach exact locations to counterexamples, without choosing replacements."""
    rows=[]
    for issue in issues:
        row=dict(issue)
        if type(row.get('case_index')) is int:
            row['paths']=[f'/cases/{row["case_index"]}/kind',f'/cases/{row["case_index"]}/expected']
        rows.append(row)
    return rows

"""Planner-facing authoring aids; never an evaluator or a budget migration.

The workspace remains the authority for scientific records and validation. These
projections expose its constraints early, without rewriting model-authored claims.
"""
from __future__ import annotations

import copy
import json
from typing import Any, Mapping

from .research_tools import digest

VERSION = "planner_authoring_v1"


class AuthoringError(ValueError):
    def __init__(self, issues: list[dict[str, Any]]):
        super().__init__(issues[0].get("reason", "specific_" + issues[0]["field"] + "_required"))
        self.field_issues = issues


def validate_authoring(command: str, arguments: Mapping[str, Any]) -> None:
    """Report all invalid descriptive strings before dispatch, retaining model cost."""
    fields: list[tuple[list[Any], str, Any, int]] = []
    issues = []
    if command == "register_claim" and isinstance(arguments.get("claim"), dict):
        claim = arguments["claim"]
        base = ["arguments", "claim"]
        for key, expected, maximum, reason in (("definitions", dict, 12, "explicit_claim_definitions_required"),
                ("assumptions", list, 8, "bounded_assumptions_required")):
            value = claim.get(key)
            if not isinstance(value, expected) or not 1 <= len(value) <= maximum:
                issues.append({"path": base + [key], "field": key, "reason": reason,
                    "expected_type": "object" if expected is dict else "array",
                    "minimum_items": 1, "maximum_items": maximum,
                    "actual_items": len(value) if isinstance(value, expected) else None})
        if isinstance(claim.get("definitions"), dict):
            fields.extend((base + ["definitions", k], "definition", v, 500)
                          for k, v in list(claim["definitions"].items())[:12])
        if isinstance(claim.get("assumptions"), list):
            fields.extend((base + ["assumptions", i], "assumption", v, 500)
                          for i, v in enumerate(claim["assumptions"][:8]))
        for key in ("statement", "scope", *(() if claim.get("kind") == "mathematical"
                                            else ("operationalization", "falsification"))):
            fields.append((base + [key], key, claim.get(key), 2000))
    elif command == "request_capability":
        fields.extend((["arguments", k], k, arguments.get(k), 2000)
                      for k in ("capability", "why_needed", "acceptance_test", "bounded_scope"))
    for path, field, value, maximum in fields:
        length = len(value.strip()) if isinstance(value, str) else None
        if length is None or not 8 <= length <= maximum:
            issues.append({"path": path, "field": field, "expected_type": "string",
                "minimum_length": 8, "maximum_length": maximum, "actual_trimmed_length": length})
    if issues:
        raise AuthoringError(issues)


def _object(properties: dict[str, Any], optional: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"type": "object", "properties": properties,
            "required": [k for k in properties if k not in optional], "additionalProperties": False}


def _string(minimum: int = 8, maximum: int = 2000) -> dict[str, Any]:
    # Large bounded string repetitions can exceed the provider's grammar
    # complexity limit. Generation is concise; workspace acceptance is unchanged.
    return {"type": "string", "minLength": minimum, "maxLength": min(maximum, 256)}


def _enum(values: list[str]) -> dict[str, Any]:
    return {"type": "string", "enum": values} if values else _string(1, 120)


def argument_schema(context: Mapping[str, Any], commands: list[str]) -> dict[str, Any]:
    """Typed generation shapes supplement, never replace, authoritative validation.

    Arguments are a union; dispatch still checks the selected command and all
    cross-field bindings. IDs come from the current public context, never guesses.
    """
    theory = context.get("theory", {})
    sources = list(theory.get("subject", {}).get("sources", {}))
    claims = [r["id"] for r in theory.get("claims", [])]
    revisions = [r["id"] for r in theory.get("revisions", []) if r.get("status") == "proposed"]
    source_ids = {"type": "array", "items": _enum(sources), "minItems": 1, "maxItems": 8}
    claim_ids = {"type": "array", "items": _enum(claims), "maxItems": 8}
    formal = _object({"domains": {"type": "object", "minProperties": 1, "maxProperties": 4,
        "additionalProperties": {"type": "array", "minItems": 1, "maxItems": 16,
            "items": {"anyOf": [{"type": "number"}, _string(1, 80)]}}},
        "left": _string(1, 500), "relation": _enum(["==", "<", ">", "<=", ">="]), "right": _string(1, 500)})
    common = {"statement": _string(), "definitions": {"type": "object", "minProperties": 1,
        "maxProperties": 12, "additionalProperties": _string(8, 500)},
        "assumptions": {"type": "array", "items": _string(8, 500), "minItems": 1, "maxItems": 8},
        "scope": _string(), "dependencies": claim_ids, "source_ids": source_ids}
    claim = {"anyOf": [_object({"kind": _enum(["mathematical"]), **common, "formal_spec": formal}),
        _object({"kind": _enum(["empirical", "interpretive"]), **common,
                 "operationalization": _string(), "falsification": _string()})]}
    from .nine_d_testing import model_schemas, METRICS as testing_metrics
    authorized = theory.get("subject", {}).get("evaluators", {})
    additional_models = model_schemas(authorized)
    metric = _enum(["counterexample_count", "checked_cases", "candidate_gain", "candidate_holdout_mse",
        *(metric for evaluator in authorized for metric in testing_metrics.get(evaluator, []))])
    prediction = _object({"metric": metric, "relation": _enum(["==", "<", ">", "<=", ">="]), "value": {"type": "number"}})
    falsifier = copy.deepcopy(prediction)
    falsifier["properties"]["relation"] = _enum(["!=", "==", "<", ">", "<=", ">="])
    forecast = _object({"evaluator_id": _enum(["nine_d_forecast_v1"]),
        "features": {"type": "array", "items": _string(1, 500), "minItems": 9, "maxItems": 9},
        "ablate_indices": {"type": "array", "minItems": 1, "maxItems": 8,
            "items": {"type": "integer", "minimum": 0, "maximum": 8}}})
    empirical_models = {"anyOf": [*([forecast] if not authorized or "nine_d_forecast_v1" in authorized else []), *additional_models]}
    plan = _object({"claim_id": _enum(claims), "observable": _object({
        "evaluator_id": _enum(list(theory.get("subject", {}).get("evaluators", {}))), "metric": metric}),
        "prediction": prediction, "falsifier": falsifier, "mechanism": _string(), "falsification": _string(),
        "budget": _object({"tool_calls": {"const": 2}, "evaluations": {"const": 1},
                            "compute_seconds": {"type": "integer", "enum": [31, 46]}}),
        "model_spec": empirical_models}, optional=("model_spec",))
    if not empirical_models["anyOf"]:
        plan["properties"].pop("model_spec")
    source = _object({"source_id": _enum(sources), "offset_chars": {"type": "integer", "minimum": 0}})
    shapes = {
        "inspect_source": source, "retrieve_evidence": source,
        "inspect_dependency": _object({**source["properties"], "claim_id": _enum(claims), "question": _string()}),
        "inspect_record": _object({"kind": _enum(["claims", "revisions", "evaluations", "decisions"]),
            "id": _enum([r["id"] for k in ("claims", "revisions", "evaluations", "decisions") for r in theory.get(k, [])])}),
        "register_claim": _object({"claim": claim}), "submit_research_plan": plan,
        "evaluate_revision": _object({"revision_id": _enum(revisions)}),
        "decide_revision": _object({"revision_id": _enum(revisions), "decision": _enum(["accept", "reject", "revise"])}),
        "request_capability": _object({k: _string() for k in ("capability", "why_needed", "acceptance_test", "bounded_scope")}),
    }
    from .theory_methods import dependency_choices
    from .theory_result_views import SECTIONS
    if any("baseline_fidelity_verified" in row.get("assessment", {}) for row in theory.get("evaluations", [])):
        shapes["inspect_record"] = {"anyOf": [shapes["inspect_record"], _object({"kind": {"const": "evaluations"},
            "id": _enum([row["id"] for row in theory.get("evaluations", [])]), "section": _enum(list(SECTIONS)),
            "offset_chars": {"type": "integer", "minimum": 0}})]}
    choices=dependency_choices(context)
    if choices:
        shapes['inspect_dependency']={'anyOf':[_object({**{key:{'const':value} for key,value in choice.items()},
            'question':_string()}) for choice in choices]}
    from .research_semantics import measurement_schema
    from .executable_measurement import schema as executable_schema
    shapes["check_measurement"] = executable_schema()
    if context.get("semantic_authoring_version"):
        shapes["request_capability"]["properties"]["measurement_contract"] = measurement_schema()
        shapes["request_capability"]["required"].append("measurement_contract")
    shapes["register_formal_claim"] = _object({"formal_spec": formal, **{k:common[k] for k in ("definitions", "assumptions", "source_ids")}})
    reviews = context.get("research_feedback", {}).get("pending_reviews", [])
    if reviews:
        from .research_semantics import review_response_schema
        shapes["request_capability"]["properties"]["review_response"] = review_response_schema(reviews)
        shapes["request_capability"]["required"].append("review_response")
    shapes["submit_review_response"] = _object({"review_id": _enum([r["id"] for r in reviews]),
        "resolutions": {"type": "object", "minProperties": 1, "maxProperties": 6, "additionalProperties": _string(8, 160)},
        "revised_kind": _enum(["claims"]),
        "revised_record_id": _enum([r["id"] for r in theory.get("claims", [])
            if r["id"] not in {v["target"]["record_id"] for v in reviews}])})
    # The legacy proposal path stays available with its existing authoring shape.
    shapes["propose_revision"] = _object({"parent_revision_id": _string(1, 120),
        "claim_ids": {**claim_ids, "minItems": 1}, "changes": {"type": "array", "minItems": 1, "maxItems": 8,
            "items": _object({"target": _enum(["definition", "assumption", "scope", "equation", "mechanism"]),
                **{k: _string() for k in ("before", "after", "reason")}})},
        "model_spec": {"anyOf": [_object({"evaluator_id": _enum(["finite_domain_v1"]), "property": formal}), *empirical_models["anyOf"]]},
        "predictions": {"type": "array", "items": prediction, "minItems": 1, "maxItems": 4},
        "mechanism": _string(), "falsification": _string()})
    alternatives = []
    for command in commands:
        shape = shapes[command]
        if shape not in alternatives:
            alternatives.append(shape)
    return {"anyOf": alternatives}


def compact_transport_context(context: Mapping[str, Any]) -> dict[str, Any]:
    """Bound the model projection while leaving complete receipts on disk.

    Byte limits are conservative input bounds, not an assertion of exact model
    token counts. The provider's actual prompt count is recorded separately.
    """
    result = copy.deepcopy(dict(context))
    evaluators = result.get("theory", {}).get("subject", {}).get("evaluators", {})
    if evaluators and not any(key in evaluators for key in ("nine_d_forecast_v1", "nine_d_intervention_v1", "nine_d_comparison_v2")):
        # The frozen work object keeps its original identity. Only the prompt
        # projection hides inputs/functions of an unavailable evaluator family.
        result.get("task", {}).pop("evaluator_help", None)
    allowance = result.get("call_allowance", {})
    if "source_read_history" in allowance:
        allowance.pop("source_read_history")
        allowance["source_history_available_in"] = "evidence_memory.pages"
    memory = result.get("evidence_memory", {})
    omitted = {}
    from .theory_methods import dependency_choices
    choices = dependency_choices(result)
    required = allowance.get("required_first_action") or {}
    if required.get("command") == "inspect_dependency":
        binding = {k: required.get("arguments", {}).get(k) for k in ("claim_id", "source_id", "offset_chars")}
        if binding not in choices:
            raise ValueError("required_dependency_binding_missing_from_context")
    # Preserve all offered bindings. Navigation is not acquired evidence; compact
    # its metadata instead of dropping unread entries according to list position.
    pairs = {(r["source_id"], r["offset_chars"]) for r in choices}
    index = memory.get("dependency_index", [])
    selected = [r for r in index if (r.get("source_id"), r.get("unread_offset_chars")) in pairs]
    memory["dependency_index"] = []
    for row in selected:
        entry = {k: row[k] for k in ("source_id", "unread_offset_chars", "symbol") if k in row}
        if entry not in memory["dependency_index"]:
            memory["dependency_index"].append(entry)
    omitted["dependency_index"] = len(index) - len(memory["dependency_index"])
    pages = memory.get("pages", [])
    memory["pages"] = pages[-16:]
    omitted["pages"] = max(0, len(pages)-16)
    remaining = 5000
    for page in memory.get("claim_linked_excerpts", []):
        original = page.get("text", "")
        excerpt = original[:min(4000, remaining)]
        remaining -= len(excerpt)
        if excerpt != original:
            page.update(text=excerpt, excerpt_sha256=digest(excerpt), truncated=True)
    memory["claim_linked_excerpts"] = [p for p in memory.get("claim_linked_excerpts", []) if p.get("text")]
    result["context_projection"] = {"version": VERSION, "omitted_navigation_entries": omitted,
        "full_records_retained": True, "scientific_progress_credited": False}
    def size() -> int:
        return len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    for key in ("pages", "claim_linked_excerpts"):
        rows = memory.get(key, [])
        while size() > 14000 and len(rows) > 1:
            rows.pop()
            omitted[key] = omitted.get(key, 0) + 1
    # Excerpts are retrievable from immutable receipts. Truncation is explicit,
    # hashed, and only used under pressure; findings and unknowns stay intact.
    for page in reversed(memory.get("claim_linked_excerpts", [])):
        if size() <= 14000:
            break
        original = page.get("text", "")
        keep = max(256, len(original) - (size()-14000))
        excerpt = original[:keep]
        if excerpt != original:
            page.update(text=excerpt, excerpt_sha256=digest(excerpt), truncated=True)
    if size() > 18000:
        raise ValueError("theory_context_size_limit_inspect_targeted_records")
    if dependency_choices(result) != choices:
        raise ValueError("context_projection_changed_dependency_bindings")
    return result


def bind_command_schema(context: Mapping[str, Any], catalog: Mapping[str, Any]) -> dict[str, Any]:
    """Bind each command to its own arguments in the provider grammar.

    Independent command and argument unions admit cross-command combinations.
    The catalog remains useful for inspection; transport uses complete branches.
    Runtime dispatch still validates every choice and its current evidence.
    """
    branches=[]
    for command in catalog['properties']['command']['enum']:
        shape=argument_schema(context,[command])['anyOf'][0]
        branches.append(_object({'command':{'const':command},'arguments':shape,
            'why':_string(8,160)},optional=('why',)))
    return {'anyOf':branches}

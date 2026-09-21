"""Explicit meanings and finite statements, without choosing a research answer."""
from __future__ import annotations

import copy
import json
from typing import Any, Mapping

from .theory_workspace import TheoryWorkspace, text

VERSION = "research_semantics_v1"
REQUEST_FIELDS = {"capability", "why_needed", "acceptance_test", "bounded_scope"}
STATISTICS = ["variance", "relative_stddev", "relative_range", "max_absolute_error", "quantile", "custom", "unresolved", "identity", "absolute_difference", "range"]
LESSONS = {
    "metric_undefined": "Define the quantity, units, statistic and reference before a threshold comparison. Preserve unresolved source choices.",
    "calibration_unverified": "Specify how calibration and provenance are verified; an adjective is not measurement evidence.",
    "acceptance_incomplete": "Freeze independently checkable below, boundary, above and invalid cases before execution.",
    "acquisition_missing": "Distinguish computing on supplied values from acquiring and validating the observations.",
    "existing_tool_available": "Inspect the current tool and evidence inventory before requesting a capability that already exists.",
    "formal_alignment": "Choose the exact finite proposition and domain; its rendered statement must preserve its quantifier.",
    "resource_bounds_missing": "Declare enforceable total samples, elapsed time and attempts; retain failed-attempt costs.",
    "evaluator_mismatch": "Match the evaluator's actual observable and intervention to the claim; request a missing evaluator without substituting another measurement.",
    "evidence_coverage": "Check the inspected source ranges and unread dependencies before making an implementation claim.",
}


def validate_measurement_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    fields = {"quantity", "unit", "statistic", "reference", "threshold_unit", "procedure",
        "calibration", "uncertainty", "invalid_outcome", "unresolved", "cases", "limits"}
    if not isinstance(contract, dict) or not fields <= set(contract) or set(contract)-fields-{"executable"}:
        raise ValueError("explicit_measurement_contract_required")
    for key in ("quantity", "unit", "reference", "threshold_unit", "procedure", "calibration", "uncertainty"):
        value = contract[key]
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 500:
            raise ValueError("bounded_measurement_" + key + "_required")
    if contract["statistic"] not in STATISTICS or contract["invalid_outcome"] not in {"reject", "indeterminate"}:
        raise ValueError("explicit_statistic_and_invalid_outcome_required")
    unresolved = contract["unresolved"]
    if not isinstance(unresolved, list) or len(unresolved) > 6:
        raise ValueError("bounded_unresolved_measurement_choices_required")
    for issue in unresolved:
        text(issue, "unresolved_measurement_choice", 500)
    if contract["statistic"] == "unresolved" and not unresolved:
        raise ValueError("unresolved_statistic_requires_explicit_question")
    if contract["statistic"] == "variance" and contract["threshold_unit"].strip().lower() in {"%", "percent", "percentage"}:
        raise ValueError("variance_percent_dimension_mismatch_define_normalization")
    limits = contract["limits"]
    if (not isinstance(limits, dict) or set(limits) != {"samples", "seconds", "attempts"}
            or any(type(v) is not int for v in limits.values())
            or not 0 <= limits["samples"] <= 100000 or not 1 <= limits["seconds"] <= 3600
            or not 1 <= limits["attempts"] <= 3):
        raise ValueError("enforceable_measurement_limits_required")
    cases = contract["cases"]
    if not isinstance(cases, list) or len(cases) > 8:
        raise ValueError("bounded_boundary_acceptance_cases_required")
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"kind", "input", "expected"} or case["kind"] not in {"below", "boundary", "above", "invalid"}:
            raise ValueError("typed_boundary_acceptance_case_required")
        for key in ("input", "expected"):
            text(case[key], "acceptance_" + key, 500)
    if not unresolved and "executable" not in contract and {c["kind"] for c in cases} != {"below", "boundary", "above", "invalid"}:
        raise ValueError("below_boundary_acceptance_above_and_invalid_cases_required")
    if "executable" in contract:
        from .executable_measurement import check, MeasurementError
        executable=contract["executable"]
        if not isinstance(executable,dict) or set(executable)!={"spec","cases"}:
            raise ValueError("typed_executable_measurement_required")
        result=check(executable["spec"],executable["cases"],require_coverage=True)
        for key in ("quantity","unit","statistic","threshold_unit","invalid_outcome","unresolved","limits"):
            if contract[key]!=executable["spec"][key]:
                raise ValueError("measurement_declaration_disagrees_with_executable_"+key)
        if contract["reference"] != f"{executable['spec']['reference']} {executable['spec']['unit']}":
            raise ValueError("measurement_reference_must_match_executable_value_and_unit")
        if not result["passed"]:
            raise MeasurementError(result)
    return {"version": VERSION, "specification_complete": not unresolved,
        "semantic_review_required": True, "scientific_progress_credited": False,
        "grants_execution_authority": False}


def validate_capability_request(request: Mapping[str, Any], *, require_contract: bool = True) -> dict[str, Any]:
    allowed = REQUEST_FIELDS | {"measurement_contract", "review_response"}
    if not isinstance(request, dict) or not REQUEST_FIELDS <= set(request) or set(request) - allowed:
        raise ValueError("typed_capability_request_required")
    result = {key: text(request[key], key) for key in sorted(REQUEST_FIELDS)}
    if require_contract or "measurement_contract" in request:
        contract = request.get("measurement_contract")
        assessment = validate_measurement_contract(contract)
        if "executable" in contract:
            from .executable_measurement import validate_statement
            validate_statement(contract["executable"]["spec"],request["acceptance_test"])
        result.update(measurement_contract=copy.deepcopy(contract), semantic_assessment=assessment)
    return result


def review_response_schema(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    from .planner_authoring import _object, _string
    return {"anyOf": [_object({"review_id": {"const": review["id"]},
        "resolutions": _object({finding["code"]: _string(8, 160) for finding in review["findings"]})}) for review in reviews]}


def register_formal_claim(workspace: TheoryWorkspace, arguments: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(arguments, dict) or set(arguments) != {"formal_spec", "definitions", "assumptions", "source_ids"}:
        raise ValueError("typed_finite_claim_required")
    from .theory_evaluators import validate_spec
    formal = arguments["formal_spec"]
    validate_spec({"evaluator_id": "finite_domain_v1", "property": formal})
    # Rendering supplies no proposition, quantifier choice, result or interpretation.
    domain = json.dumps(formal["domains"], sort_keys=True)
    statement = f"For every assignment in {domain}: ({formal['left']}) {formal['relation']} ({formal['right']})."
    return workspace.register_claim({**copy.deepcopy(arguments), "kind": "mathematical",
        "statement": statement, "scope": "Exactly the Cartesian product of the explicitly declared finite domains.",
        "dependencies": []})


def measurement_schema() -> dict[str, Any]:
    from .planner_authoring import _object, _string, _enum
    # Short fields keep the provider grammar and response within bounded size.
    result = _object({**{key: _string(1, 160) for key in
        ("quantity", "unit", "reference", "threshold_unit", "procedure", "calibration", "uncertainty")},
        "statistic": _enum(STATISTICS), "invalid_outcome": _enum(["reject", "indeterminate"]),
        "unresolved": {"type": "array", "maxItems": 6, "items": _string(8, 160)},
        "cases": {"type": "array", "maxItems": 4, "items": _object({"kind": _enum(["below", "boundary", "above", "invalid"]),
            "input": _string(8, 160), "expected": _string(8, 160)})},
        "limits": _object({"samples": {"type": "integer", "minimum": 0, "maximum": 100000},
            "seconds": {"type": "integer", "minimum": 1, "maximum": 3600},
            "attempts": {"type": "integer", "minimum": 1, "maximum": 3}})})
    from .executable_measurement import schema
    result["properties"]["executable"] = schema()
    return result


def validate_claim_alignment(claim: Mapping[str, Any]) -> None:
    """Catch explicit quantifier conflicts in legacy prose; never certify arbitrary prose."""
    if claim.get("kind") != "mathematical":
        return
    statement = claim.get("statement", "").lower()
    if any(phrase in statement for phrase in ("if and only if", "there exists", "for some ")):
        raise ValueError("formal_alignment_requires_canonical_finite_claim")

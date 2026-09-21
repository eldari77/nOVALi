"""Bounded, domain-independent acceptance fixtures for proposed capabilities.

These predicates check supplied records, never external truth or acquisition.
"""
from __future__ import annotations

from typing import Any, Mapping

from .planner_authoring import _object, _string, _enum

PLACEHOLDERS = {"", "tbd", "unknown", "null", "none", "n/a", "generic", "placeholder"}
HELP = ("required_fields names fields inside each record, not case kinds. minimum_records is the minimum record count WITHIN ONE CASE, not the number of cases. "
    "A positive case has at least minimum_records records and every record supplies every required_fields name exactly with a non-placeholder value. "
    "With available evidence and valid resources, a missing/placeholder required field or too few records yields negative/fail. "
    "evidence_available=false yields unknown/indeterminate. Exceeding limits.records, limits.seconds or limits.attempts yields resource_limit/indeterminate. "
    "Resource limits apply separately to each case. Words such as ambiguous in a supplied value do not change the predicate. "
    "The four case kinds are test categories, never required record-field names.")


class ContractError(ValueError):
    def __init__(self, issues: list[dict[str, Any]]):
        super().__init__("typed_acceptance_contract_requires_correction")
        self.field_issues = issues


def schema() -> dict[str, Any]:
    integer = lambda maximum: {"type": "integer", "minimum": 1, "maximum": maximum}
    fields = {"type": "array", "maxItems": 8, "items": _object({"name": _string(1, 64), "value": _string(0, 100)})}
    case = _object({"kind": _enum(["positive", "negative", "unknown", "resource_limit"]),
        "records": {"type": "array", "maxItems": 4, "items": _object({"fields": fields})},
        "evidence_available": {"type": "boolean"}, "seconds": {"type": "integer", "minimum": 0, "maximum": 61},
        "attempts": integer(4), "expected": _enum(["pass", "fail", "indeterminate"])})
    return _object({"capability": _string(8, 120), "why_needed": _string(8, 256), "bounded_scope": _string(8, 256),
        "acceptance": _object({"observable": _string(8, 256), "proves": _string(8, 256), "does_not_prove": _string(8, 256),
            "required_fields": {"type": "array", "items": _string(1, 64), "minItems": 1, "maxItems": 8},
            "minimum_records": integer(4), "limits": _object({"records": integer(4), "seconds": integer(60), "attempts": integer(3)}),
            "cases": {"type": "array", "minItems": 4, "maxItems": 4, "items": case}})})


def _shape(value: Any, spec: Mapping[str, Any], path: str = "proposal") -> list[dict[str, Any]]:
    """Use the same small schema at generation and validation boundaries."""
    issues: list[dict[str, Any]] = []
    kind = spec["type"]
    expected = {"object": dict, "array": list, "integer": int, "string": str, "boolean": bool}[kind]
    if type(value) is not expected:
        return [{"field": path, "reason": "expected_" + kind}]
    if kind == "object":
        if set(value) != set(spec["properties"]):
            issues.append({"field": path, "reason": "complete_typed_fields_required", "required": list(spec["properties"])})
        for key in set(value) & set(spec["properties"]): issues.extend(_shape(value[key], spec["properties"][key], path+"."+key))
    elif kind == "array":
        if not spec.get("minItems", 0) <= len(value) <= spec["maxItems"]:
            issues.append({"field": path, "reason": "bounded_case_items_required"})
        for index, item in enumerate(value[:spec["maxItems"]]): issues.extend(_shape(item, spec["items"], f"{path}[{index}]"))
    elif kind == "string":
        if "enum" in spec and value not in spec["enum"] or not spec.get("minLength", 0) <= len(value.strip()) <= spec.get("maxLength", 256):
            issues.append({"field": path, "reason": "specific_bounded_string_required"})
    elif kind == "integer" and not spec["minimum"] <= value <= spec["maximum"]:
        issues.append({"field": path, "reason": "bounded_integer_required"})
    return issues


def validate(proposal: Mapping[str, Any]) -> dict[str, Any]:
    issues = _shape(proposal, schema())
    if issues: raise ContractError(issues)
    contract = proposal["acceptance"]
    required = contract["required_fields"]
    if len(required) != len(set(required)) or contract["minimum_records"] > contract["limits"]["records"]:
        issues.append({"field": "acceptance", "reason": "unique_fields_and_feasible_record_limit_required"})
    results = []
    for index, case in enumerate(contract["cases"]):
        duplicate = any(len(r["fields"]) != len({f["name"] for f in r["fields"]}) for r in case["records"])
        if duplicate: issues.append({"field": f"acceptance.cases[{index}]", "reason": "ambiguous_duplicate_field"})
        over = (len(case["records"]) > contract["limits"]["records"] or case["seconds"] > contract["limits"]["seconds"]
                or case["attempts"] > contract["limits"]["attempts"])
        valid = len(case["records"]) >= contract["minimum_records"]
        for record in case["records"]:
            values = {f["name"]: f["value"].strip().casefold() for f in record["fields"]}
            valid = valid and all(values.get(name, "") not in PLACEHOLDERS for name in required)
        kind = "resource_limit" if over else "unknown" if not case["evidence_available"] else "positive" if valid else "negative"
        actual = "indeterminate" if kind in {"unknown", "resource_limit"} else "pass" if valid else "fail"
        results.append({"kind": kind, "actual": actual})
        if (case["kind"], case["expected"]) != (kind, actual):
            issues.append({"field": f"acceptance.cases[{index}]", "reason": "independent_case_mismatch", "actual": actual, "kind": kind})
    if {r["kind"] for r in results} != {"positive", "negative", "unknown", "resource_limit"}:
        issues.append({"field": "acceptance.cases", "reason": "positive_negative_unknown_resource_coverage_required"})
    if issues: raise ContractError(issues)
    return {"passed": True, "results": results, "evidence_scope": "supplied_record_structure_only",
            "semantic_review_required": True, "scientific_progress_credited": False}

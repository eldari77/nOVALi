"""Planner-owned conditional use of measured lessons; no inferred transfer."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from .research_tools import digest, read_json, write_json
from .authoring_contract import AuthoringError, METRICS, field_issues

VERSION = "lesson_applicability_v1"
CONTROLS = ("instruction_mode", "excerpt_chars", "command_scope")


def configure(root: Path, *, enabled: bool, authority_reference: str) -> dict[str, Any]:
    if type(enabled) is not bool or not authority_reference.strip():
        raise ValueError("explicit_lesson_applicability_policy_required")
    row = {"version": VERSION, "enabled": enabled, "authority_reference": authority_reference,
           "scientific_allowance_added": 0, "method_adoption_authorized": False}
    write_json(root / "research_methods/lesson_applicability_policy.json", row)
    return row


def attach(inputs: dict[str, Any], *, enabled: bool) -> None:
    if not enabled:
        return
    memory = list(inputs.get("hypothesis_memory", []))
    opportunity = inputs.get("question_opportunity", {})
    if opportunity.get("lesson"):
        memory.append(opportunity["lesson"])
    unique = {row["id"]: row for row in memory}
    current = inputs.get("hypothesis_decision_available") or {}
    admitted = inputs.get("accepted_practice_question") or {}
    metric = (admitted.get("hypothesis") or current.get("hypothesis") or {}).get("metric")
    context_hash = digest(inputs["planning_context"])
    # Relevance affects presentation only. The planner still chooses applicability.
    ranked = sorted(unique.values(), key=lambda r: (
        r.get("input_sha256") != context_hash, r["hypothesis"]["metric"] != metric, r["id"]))
    inputs["lesson_applicability"] = {
        "version": VERSION, "current_input_sha256": context_hash, "current_metric": metric,
        "lessons": ranked[:6], "omitted_count": max(0, len(ranked)-6),
        "instruction": "Compare current quantity, controls and input assumptions. Choose reuse, adapt or disregard. A prior numerical result never establishes a new task's result.",
        "assumptions": "Same frozen input is checkable; semantic equivalence of changed sources is unknown.",
    }
    # One evidence projection prevents duplicate old proposals from dominating context.
    inputs["hypothesis_memory"] = []


def schema(context: Mapping[str, Any]) -> dict[str, Any] | None:
    from .planner_authoring import _object, _string
    binding = context.get("inputs", {}).get("lesson_applicability", {})
    if not binding.get("lessons"):
        return None
    return _object({
        "lesson_id": {"type": "string", "enum": [r["id"] for r in binding["lessons"]]},
        "current_metric": {"type": "string", "enum": list(METRICS)},
        "decision": {"type": "string", "enum": ["reuse", "adapt", "disregard"]},
        "input_relation": {"type": "string", "enum": ["same_frozen_input", "changed_input_requires_check"]},
        "control_relation": {"type": "string", "enum": ["same", "different", "not_selected"]},
        "reason": _string(12, 300),
    })


def validate(response: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any] | None:
    if not isinstance(response,Mapping):
        raise ValueError("typed_lesson_application_response_required")
    expected = schema(context)
    if expected is None:
        if "lesson_application" in response:
            raise ValueError("lesson_application_requires_offered_evidence")
        return None
    application = response.get("lesson_application")
    issues = field_issues(application, expected, "lesson_application")
    if issues:
        raise AuthoringError(issues, {})
    inputs = context["inputs"]; binding = inputs["lesson_applicability"]
    lesson = next(row for row in binding["lessons"] if row["id"] == application["lesson_id"])
    intent = response.get("intent")
    hypothesis = response.get("hypothesis") or response.get("question", {}).get("hypothesis") or {}
    metric = hypothesis.get("metric") or response.get("metric") or binding.get("current_metric")
    if intent == "practice_question":
        metric = inputs["accepted_practice_question"]["hypothesis"]["metric"]
    if intent in ("refute", "withdraw", "correct_prediction"):
        metric = inputs["hypothesis_decision_available"]["hypothesis"]["metric"]
    if metric and application["current_metric"] != metric:
        issues.append({"field": "lesson_application.current_metric", "reason": "application_must_address_current_quantity",
                       "expected": metric, "actual": application["current_metric"]})
    profile = response.get("strategy") or response.get("question", {}).get("strategy")
    if intent == "practice_question":
        profile = inputs["accepted_practice_question"]["question"]["strategy"]
    if intent in ("refute", "withdraw", "correct_prediction", "new_hypothesis"):
        profile = (inputs.get("hypothesis_decision_available") or {}).get("profile")
    controls = "not_selected" if not profile else ("same" if all(
        profile[k] == lesson["profile"][k] for k in CONTROLS) else "different")
    relation = "same_frozen_input" if lesson["input_sha256"] == binding["current_input_sha256"] else "changed_input_requires_check"
    for key, value in (("input_relation", relation), ("control_relation", controls)):
        if application[key] != value:
            issues.append({"field": "lesson_application."+key, "reason": "application_comparison_mismatch",
                           "expected": value, "actual": application[key]})
    if application["decision"] == "reuse" and (relation != "same_frozen_input" or controls != "same"
            or application["current_metric"] != lesson["hypothesis"]["metric"]):
        issues.append({"field": "lesson_application.decision", "reason": "changed_conditions_require_adaptation_or_disregard"})
    if issues:
        raise AuthoringError(issues, {})
    return {"authored": copy.deepcopy(application), "lesson_sha256": digest(lesson),
            "current_input_sha256": binding["current_input_sha256"],
            "comparisons_verified": True, "rationale_semantics_verified": False,
            "current_outcome_requires_independent_check": True, "method_adoption_authorized": False}


def enabled(root: Path) -> bool:
    return read_json(root / "research_methods/lesson_applicability_policy.json").get("enabled") is True

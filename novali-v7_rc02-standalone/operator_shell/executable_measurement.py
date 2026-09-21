"""Bounded arithmetic acceptance checks; no acquisition or scientific authority."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Mapping

VERSION = "executable_measurement_v1"
STATISTICS = ("identity", "max_absolute_error", "absolute_difference", "range")
COMPARISONS = ("<", "<=", "==", ">=", ">")
OUTCOMES = ("pass", "fail", "indeterminate")


class MeasurementError(ValueError):
    def __init__(self, result: dict[str, Any]):
        super().__init__("executable_acceptance_counterexample_requires_correction")
        self.field_issues = result["counterexamples"]
        self.assessment = result


def number(value: Any) -> Decimal:
    if type(value) not in (int, float):
        raise ValueError("finite_measurement_number_required")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("finite_measurement_number_required") from exc
    if not result.is_finite() or abs(result) > Decimal("1e30"):
        raise ValueError("finite_bounded_measurement_number_required")
    return result


def validate(spec: Mapping[str, Any]) -> None:
    fields = {"quantity", "unit", "statistic", "reference", "comparison", "threshold", "threshold_unit",
        "sample_count", "validity", "invalid_outcome", "unresolved", "limits"}
    if not isinstance(spec, dict) or set(spec) != fields:
        raise ValueError("typed_executable_measurement_required")
    for key in ("quantity", "unit", "statistic", "threshold_unit"):
        if not isinstance(spec[key], str) or not 1 <= len(spec[key].strip()) <= 120:
            raise ValueError("bounded_measurement_label_required")
    if spec["unit"] != spec["threshold_unit"]:
        raise ValueError("measurement_unit_mismatch")
    if spec["comparison"] not in COMPARISONS or spec["invalid_outcome"] not in ("reject", "indeterminate"):
        raise ValueError("explicit_measurement_decision_required")
    number(spec["reference"]); number(spec["threshold"])
    if number(spec["threshold"]) < 0:
        raise ValueError("nonnegative_threshold_required")
    if type(spec["sample_count"]) is not int or not 1 <= spec["sample_count"] <= 32:
        raise ValueError("bounded_measurement_sample_count_required")
    limits=spec["limits"]
    if (not isinstance(limits,dict) or set(limits)!={"samples","seconds","attempts"}
            or any(type(v) is not int for v in limits.values())
            or not spec["sample_count"] <= limits["samples"] <= 100000
            or not 1 <= limits["seconds"] <= 3600 or not 1 <= limits["attempts"] <= 3):
        raise ValueError("measurement_resource_limits_inconsistent")
    valid=spec["validity"]
    if not isinstance(valid,dict) or set(valid)!={"minimum","maximum","required_evidence"}:
        raise ValueError("explicit_validity_conditions_required")
    if number(valid["minimum"]) > number(valid["maximum"]):
        raise ValueError("measurement_validity_range_inconsistent")
    for values in (valid["required_evidence"], spec["unresolved"]):
        if not isinstance(values,list) or len(values)>6 or any(not isinstance(v,str) or not 1<=len(v)<=160 for v in values):
            raise ValueError("bounded_measurement_conditions_required")
    if len(set(valid["required_evidence"])) != len(valid["required_evidence"]):
        raise ValueError("duplicate_measurement_condition")
    if spec["statistic"] not in STATISTICS and not spec["unresolved"]:
        raise ValueError("unsupported_statistic_requires_explicit_unresolved_choice")
    if ((spec["statistic"] == "identity" and spec["sample_count"] != 1)
            or (spec["statistic"] == "absolute_difference" and spec["sample_count"] != 2)):
        raise ValueError("statistic_sample_count_mismatch")


def render(spec: Mapping[str, Any]) -> str:
    validate(spec)
    return (f"{spec['quantity']}: {spec['statistic']} of {spec['sample_count']} values in {spec['unit']}, "
        f"reference {spec['reference']}, {spec['comparison']} {spec['threshold']} {spec['threshold_unit']}; "
        f"invalid evidence: {spec['invalid_outcome']}; unresolved: {len(spec['unresolved'])}.")


def validate_statement(spec: Mapping[str, Any], statement: str) -> None:
    if statement != render(spec):
        raise ValueError("executable_statement_must_match_canonical_measurement")


def _observe(spec: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    fields={"kind","values","unit","evidence","seconds","attempts","expected"}
    if not isinstance(row,dict) or set(row)!=fields or row["kind"] not in ("below","boundary","above","invalid"):
        raise ValueError("typed_executable_fixture_required")
    if row["expected"] not in OUTCOMES or not isinstance(row["values"],list) or len(row["values"])>32:
        raise ValueError("bounded_executable_fixture_required")
    if not isinstance(row["evidence"],list) or len(row["evidence"])>6 or any(not isinstance(x,str) or len(x)>160 for x in row["evidence"]):
        raise ValueError("bounded_fixture_evidence_required")
    reasons=[]
    try:
        values=[number(v) for v in row["values"]]
    except ValueError:
        values=[]; reasons.append("invalid_numeric_input")
    valid=spec["validity"]
    if len(values)!=spec["sample_count"]: reasons.append("sample_count_mismatch")
    if any(v<number(valid["minimum"]) or v>number(valid["maximum"]) for v in values): reasons.append("outside_validity_range")
    if row["unit"]!=spec["unit"]: reasons.append("unit_mismatch")
    if not set(valid["required_evidence"])<=set(row["evidence"]): reasons.append("required_evidence_missing")
    for key in ("seconds","attempts"):
        try:
            value=number(row[key])
            if value<0 or value>spec["limits"][key] or (key=="attempts" and (type(row[key]) is not int or value<1)):
                reasons.append(key+"_budget_exceeded")
        except ValueError: reasons.append("invalid_"+key)
    if spec["unresolved"] or spec["statistic"] not in STATISTICS:
        return {"actual":"indeterminate","kind":"invalid","metric":None,"reasons":["unresolved_measurement",*reasons]}
    if reasons:
        return {"actual":"fail" if spec["invalid_outcome"]=="reject" else "indeterminate",
            "kind":"invalid","metric":None,"reasons":reasons}
    with localcontext() as ctx:
        ctx.prec=80
        metric={"identity":lambda:values[0], "max_absolute_error":lambda:max(abs(v-number(spec["reference"])) for v in values),
            "absolute_difference":lambda:abs(values[0]-values[1]), "range":lambda:max(values)-min(values)}[spec["statistic"]]()
        threshold=number(spec["threshold"])
        passed={"<":metric<threshold,"<=":metric<=threshold,"==":metric==threshold,">=":metric>=threshold,">":metric>threshold}[spec["comparison"]]
    return {"actual":"pass" if passed else "fail","kind":"below" if metric<threshold else "above" if metric>threshold else "boundary",
        "metric":str(metric),"reasons":[]}


def check(spec: Mapping[str, Any], cases: list[dict[str, Any]], *, require_coverage: bool = False) -> dict[str, Any]:
    validate(spec)
    if not isinstance(cases,list) or len(cases)>8:
        raise ValueError("bounded_executable_cases_required")
    results=[]; errors=[]
    for index,row in enumerate(cases):
        result={"case_index":index,**_observe(spec,row)}; results.append(result)
        if result["actual"]!=row["expected"] or result["kind"]!=row["kind"]:
            errors.append({**result,"expected":row["expected"],"declared_kind":row["kind"],"field":"cases","reason":"outcome_or_case_kind_mismatch"})
    ready=not spec["unresolved"] and spec["statistic"] in STATISTICS
    if require_coverage and ready and {r["kind"] for r in results}!={"below","boundary","above","invalid"}:
        errors.append({"field":"cases","reason":"independent_boundary_coverage_required"})
    return {"version":VERSION,"ready":ready,"passed":bool(cases) and not errors,"results":results,
        "counterexamples":errors,"semantic_review_required":True,"scientific_progress_credited":False,"grants_execution_authority":False}


def schema() -> dict[str, Any]:
    from .planner_authoring import _object, _string, _enum
    numeric={"type":"number"}
    strings={"type":"array","maxItems":6,"items":_string(1,120)}
    return _object({"spec":_object({"quantity":_string(1,120),"unit":_string(1,40),
        "statistic":_enum([*STATISTICS,"unresolved"]),"reference":numeric,"comparison":_enum(list(COMPARISONS)),
        "threshold":numeric,"threshold_unit":_string(1,40),"sample_count":{"type":"integer","minimum":1,"maximum":32},
        "validity":_object({"minimum":numeric,"maximum":numeric,"required_evidence":strings}),
        "invalid_outcome":_enum(["reject","indeterminate"]),"unresolved":strings,
        "limits":_object({"samples":{"type":"integer","minimum":1,"maximum":100000},
            "seconds":{"type":"integer","minimum":1,"maximum":3600},"attempts":{"type":"integer","minimum":1,"maximum":3}})}),
        "cases":{"type":"array","minItems":1,"maxItems":4,"items":_object({"kind":_enum(["below","boundary","above","invalid"]),
            "values":{"type":"array","maxItems":32,"items":numeric},"unit":_string(1,40),"evidence":strings,
            "seconds":numeric,"attempts":{"type":"integer"},"expected":_enum(list(OUTCOMES))})}})

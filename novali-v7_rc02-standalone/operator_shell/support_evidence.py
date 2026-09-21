from __future__ import annotations

import re

from typing import Any, Iterable, Mapping


SUPPORT_EVIDENCE_ROW_LIMIT = 24
SUPPORT_PREVIEW_ONLY_KEYS = {
    "action_suggestions_preview",
    "requested_scope_preview",
    "tag_preview",
    "claim_preview",
    "implementation_guidance_preview",
    "caveat_preview",
    "candidate_assumptions_preview",
    "decision_axes_preview",
    "validation_questions_preview",
}
SUPPORT_ROW_KEYS = (
    "child_support_rows",
    "evidence_rows",
    "source_rows",
    "citation_summaries",
)
PLACEHOLDER_FRAGMENTS = (
    "tbd",
    "todo",
    "unknown",
    "not specified",
    "operator-approved supplier required",
    "operator approved supplier required",
    "source_ref:*manufacturer_candidate",
    "manufacturer_candidate",
    "source_backed_candidate",
    "_candidate",
    "generic connector",
    "generic measurement",
    "generic support",
)
CONTEXT_ONLY_SOURCE_HINTS = (
    "role_profile",
    "role-profile",
    "post_ladder_synthesis",
    "autonomy_context",
    "local_context_fallback",
    "redacted research evidence",
)
CONTEXT_ONLY_CLAIM_FRAGMENTS = (
    "local role profile",
    "bounded learning pressure",
    "recent redacted research evidence exists",
    "frontier synthesis suggests",
    "post-ladder synthesis",
)
WRONG_DOMAIN_FRAGMENTS = (
    "space resource extraction",
    "lunar regolith",
    "asteroid mining",
)
BUILD_DEPTH_FIELD_TERMS = (
    "manufacturer",
    "supplier",
    "mpn",
    "part number",
    "datasheet",
    "source url",
    "citation",
    "quantity",
    "unit cost",
    "cost basis",
    "electrical rating",
    "rating",
    "compliance",
    "alternative",
    "risk",
    "fixture",
    "execution gate",
    "connector",
    "pinout",
    "protocol",
    "signal level",
    "sample rate",
    "bandwidth",
    "latency",
    "isolation",
    "safety limit",
    "failure behavior",
    "validation hook",
    "measurement method",
    "pass/fail",
    "threshold",
    "calibration",
    "verification method",
    "severity",
    "occurrence",
    "detection",
    "detectability",
    "rpn",
    "mitigation",
    "residual risk",
    "standard",
)
ROLE_LANE_COMPONENT_REQUIRED_FIELDS = (
    "manufacturer",
    "mpn",
    "datasheet_url",
    "electrical_rating",
    "quantity",
    "unit_cost",
    "alternatives",
    "measurable_spec",
    "substitution_allowed",
    "test_equipment",
    "risk_if_missing",
    "validation_fixture_ref",
    "linked_risk_control_ref",
    "standards_assumption",
    "go_no_go_trace",
)


def _text(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _ref_tail(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    return text.split("#")[-1].split(":")[-1].strip()


def _is_placeholder(value: Any) -> bool:
    text = _text(value).lower()
    if not text:
        return True
    return any(fragment in text for fragment in PLACEHOLDER_FRAGMENTS)


def _looks_like_concrete_source(value: Any) -> bool:
    text = _text(value).lower()
    if not text or _is_placeholder(text):
        return False
    if any(fragment in text for fragment in CONTEXT_ONLY_SOURCE_HINTS):
        return False
    if text.startswith(("http://", "https://", "doi:", "isbn:", "datasheet:", "spec:", "standard:")):
        return True
    if any(marker in text for marker in ("datasheet", "standard", "specification", "manual", "app note", "application note")):
        return True
    return False


def _inferred_field_coverage(
    value: Mapping[str, Any],
    *,
    required_fields: Iterable[str],
    required_gates: Iterable[str],
) -> list[str]:
    explicit: list[str] = []
    for source in (
        value.get("covered_fields"),
        value.get("field_coverage"),
        value.get("support_evidence_field_coverage"),
        value.get("required_fields"),
        value.get("required_field"),
    ):
        explicit.extend(_list_texts(source))
    coverage = list(
        dict.fromkeys(
            normalize_support_field_name(item)
            for item in explicit
            if normalize_support_field_name(item)
        )
    )
    haystack = " ".join(
        [
            _text(value.get("claim") or value.get("summary") or value.get("text")),
            _text(value.get("relevance") or value.get("rationale") or value.get("target_gate_relevance")),
            _text(value.get("target_gate") or value.get("required_gate") or value.get("gate")),
            " ".join(_list_texts(value.get("covered_fields") or value.get("field_coverage"))),
            " ".join(
                str(item)
                for item in list(
                    value.get("spec_values")
                    or value.get("concrete_spec_values")
                    or []
                )
                if str(item).strip()
            )
            if isinstance(value.get("spec_values") or value.get("concrete_spec_values"), list)
            else _text(value.get("spec_values") or value.get("concrete_spec_values")),
        ]
    ).lower()
    for field in list(required_fields or []):
        field_text = _text(field).lower()
        normalized_field = normalize_support_field_name(field)
        if field_text and field_text in haystack and normalized_field not in set(coverage):
            coverage.append(normalized_field)
    for term in BUILD_DEPTH_FIELD_TERMS:
        normalized_term = normalize_support_field_name(term)
        if term in haystack and normalized_term not in set(coverage):
            coverage.append(normalized_term)
    for gate in list(required_gates or []):
        gate_text = _text(gate).lower()
        normalized_gate = normalize_support_field_name(gate)
        if gate_text and gate_text in haystack and normalized_gate not in set(coverage):
            coverage.append(normalized_gate)
    return coverage


def _build_depth_requested(payload: Mapping[str, Any], *, target_artifact: str, required_fields: Iterable[str], required_gates: Iterable[str]) -> bool:
    summary = payload.get("payload_summary", {})
    summary_map = summary if isinstance(summary, Mapping) else {}
    text = " ".join(
        [
            _text(target_artifact),
            _text(payload.get("requested_pack_family") or summary_map.get("requested_pack_family")),
            _text(payload.get("capability") or summary_map.get("capability")),
            " ".join(_list_texts(payload.get("requested_tags") or summary_map.get("requested_tags"))),
            " ".join(_text(item) for item in list(required_fields or [])),
            " ".join(_text(item) for item in list(required_gates or [])),
        ]
    ).lower()
    return bool(
        "directive_build_grade_synthesis_pack" in text
        or "build_grade" in text
        or "build-grade" in text
        or target_artifact.endswith(".json")
        or list(required_fields or [])
        or list(required_gates or [])
    )


def _list_texts(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, tuple):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def normalize_support_field_name(value: Any) -> str:
    text = _text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_") if text else ""
    text = re.sub(r"_+", "_", text)
    aliases = {
        "manufacturer": "manufacturer",
        "manufacturers": "manufacturer",
        "supplier": "manufacturer",
        "suppliers": "manufacturer",
        "vendor": "manufacturer",
        "vendors": "manufacturer",
        "maker": "manufacturer",
        "mpn": "mpn",
        "mpn": "mpn",
        "manufacturer_part_number": "mpn",
        "part_number": "mpn",
        "part_numbers": "mpn",
        "p_n": "mpn",
        "pn": "mpn",
        "datasheet": "datasheet_url",
        "datasheets": "datasheet_url",
        "datasheet_url": "datasheet_url",
        "datasheet_urls": "datasheet_url",
        "datasheet_source": "datasheet_url",
        "datasheet_source_url": "datasheet_url",
        "datasheet_source_urls": "datasheet_url",
        "datasheet_source_link": "datasheet_url",
        "source_url": "datasheet_url",
        "source_urls": "datasheet_url",
        "source_link": "datasheet_url",
        "source_links": "datasheet_url",
        "source": "datasheet_url",
        "sources": "datasheet_url",
        "citation": "datasheet_url",
        "citation_ref": "datasheet_url",
        "citations": "datasheet_url",
        "quantity": "quantity",
        "qty": "quantity",
        "validation_fixture": "validation_fixture_ref",
        "fixture": "validation_fixture_ref",
        "fixtures": "validation_fixture_ref",
        "fixture_ref": "validation_fixture_ref",
        "fixture_refs": "validation_fixture_ref",
        "fixture_link": "validation_fixture_ref",
        "fixture_links": "validation_fixture_ref",
        "linked_fixture": "validation_fixture_ref",
        "linked_fixtures": "validation_fixture_ref",
        "wiring": "fixture_wiring",
        "fixture_wirings": "fixture_wiring",
        "calibration": "calibration_steps",
        "calibration_step": "calibration_steps",
        "measurement": "measurement_method",
        "measurement_methods": "measurement_method",
        "threshold": "pass_fail_thresholds",
        "thresholds": "pass_fail_thresholds",
        "pass_fail": "pass_fail_thresholds",
        "pass_fail_threshold": "pass_fail_thresholds",
        "risk": "linked_risk_control_ref",
        "risks": "linked_risk_control_ref",
        "risk_ref": "linked_risk_control_ref",
        "risk_refs": "linked_risk_control_ref",
        "risk_control": "linked_risk_control_ref",
        "risk_controls": "linked_risk_control_ref",
        "risk_link": "linked_risk_control_ref",
        "risk_links": "linked_risk_control_ref",
        "linked_risk": "linked_risk_control_ref",
        "linked_risk_control": "linked_risk_control_ref",
        "linked_risk_controls": "linked_risk_control_ref",
        "electrical_rating": "electrical_rating",
        "electrical_ratings": "electrical_rating",
        "rating": "electrical_rating",
        "ratings": "electrical_rating",
        "cost": "unit_cost",
        "cost_basis": "unit_cost",
        "source_cost": "unit_cost",
        "unit_cost": "unit_cost",
        "unit_costs": "unit_cost",
        "cost_estimate": "unit_cost",
        "cost_estimates": "unit_cost",
        "standards": "standards_assumption",
        "standard": "standards_assumption",
        "standards_assumption": "standards_assumption",
        "standards_assumptions": "standards_assumption",
        "standard_assumption": "standards_assumption",
        "standard_assumptions": "standards_assumption",
        "go_no_go": "go_no_go_trace",
        "go_no_go_trace": "go_no_go_trace",
        "go_no_go_traces": "go_no_go_trace",
        "go_nogo": "go_no_go_trace",
        "go_nogo_trace": "go_no_go_trace",
        "go_nogo_traces": "go_no_go_trace",
        "go_no_go_evidence": "go_no_go_trace",
        "pass_fail_trace": "go_no_go_trace",
        "pass_fail_threshold": "go_no_go_trace",
        "acceptance_trace": "go_no_go_trace",
        "sample_rates": "sample_rate",
        "sampling": "sample_rate",
        "sampling_rate": "sample_rate",
        "bandwidth_budget": "bandwidth",
        "latency": "latency_budget",
        "latency_budget": "latency_budget",
        "latency_budget_ms": "latency_budget",
        "isolation": "electrical_isolation",
        "electrical_isolation": "electrical_isolation",
        "isolated": "electrical_isolation",
        "safety": "safety_limit",
        "safety_limits": "safety_limit",
        "failure": "failure_behavior",
        "failure_behaviour": "failure_behavior",
        "failure_behaviours": "failure_behavior",
        "failure_behavior": "failure_behavior",
        "failure_behaviors": "failure_behavior",
        "validation": "validation_hooks",
        "validation_hook": "validation_hooks",
        "validation_hooks": "validation_hooks",
        "hal": "hardware_abstraction_layer_id",
        "hal_id": "hardware_abstraction_layer_id",
        "hardware_abstraction_layer": "hardware_abstraction_layer_id",
        "hardware_abstraction_layer_id": "hardware_abstraction_layer_id",
        "device_manifest": "device_capability_manifest_ref",
        "device_capability_manifest": "device_capability_manifest_ref",
        "device_capability_manifest_ref": "device_capability_manifest_ref",
        "capability_manifest": "device_capability_manifest_ref",
        "manifest_ref": "device_capability_manifest_ref",
    }
    return aliases.get(text, text)


def normalize_support_role_lane(value: Any) -> str:
    text = _text(value).lower()
    text = re.sub(r"[^a-z0-9/]+", "_", text).strip("_") if text else ""
    text = re.sub(r"_+", "_", text)
    aliases = {
        "thermal": "thermal_sensor_interface",
        "thermal_sensor": "thermal_sensor_interface",
        "thermal_sensor_interface": "thermal_sensor_interface",
        "separate_thermal": "thermal_sensor_interface",
        "separate_thermal_sensor": "thermal_sensor_interface",
        "separate_thermal_sensor_interface": "thermal_sensor_interface",
        "temperature": "thermal_sensor_interface",
        "temperature_sensor": "thermal_sensor_interface",
        "current": "current_sensor_interface",
        "current_sensor": "current_sensor_interface",
        "current_sensor_interface": "current_sensor_interface",
        "magnetic_field": "magnetic_field_sensor_or_gaussmeter",
        "magnetic_field_sensor": "magnetic_field_sensor_or_gaussmeter",
        "magnetic_field_sensor_or_gaussmeter": "magnetic_field_sensor_or_gaussmeter",
        "gaussmeter": "magnetic_field_sensor_or_gaussmeter",
        "magnetic_field/gaussmeter": "magnetic_field_sensor_or_gaussmeter",
        "coolant": "coolant_flow_or_temperature_sensor",
        "coolant_flow": "coolant_flow_or_temperature_sensor",
        "coolant_flow_or_temperature_sensor": "coolant_flow_or_temperature_sensor",
        "coolant_temperature": "coolant_flow_or_temperature_sensor",
        "coolant_flow_temperature": "coolant_flow_or_temperature_sensor",
        "daq": "daq_logger_or_microcontroller_interface",
        "daq_logging": "daq_logger_or_microcontroller_interface",
        "logger": "daq_logger_or_microcontroller_interface",
        "logging": "daq_logger_or_microcontroller_interface",
        "microcontroller": "daq_logger_or_microcontroller_interface",
        "daq/logging": "daq_logger_or_microcontroller_interface",
        "daq/logger_or_microcontroller": "daq_logger_or_microcontroller_interface",
        "daq_or_microcontroller": "daq_logger_or_microcontroller_interface",
        "daq_microcontroller": "daq_logger_or_microcontroller_interface",
        "daq_logger": "daq_logger_or_microcontroller_interface",
        "daq_logger_or_microcontroller_interface": "daq_logger_or_microcontroller_interface",
        "logger_or_microcontroller_interface": "daq_logger_or_microcontroller_interface",
        "daq_logger_microcontroller_interface": "daq_logger_or_microcontroller_interface",
    }
    return aliases.get(text, text)


def _support_role_lanes_from_row(row: Mapping[str, Any]) -> list[str]:
    roles: list[str] = []
    for key in ("target_role", "role", "required_for", "category", "function", "subsystem", "row_id", "item_id", "name"):
        raw = row.get(key)
        values = raw if isinstance(raw, (list, tuple, set)) else [raw]
        for value in values:
            for part in re.split(r"[,;|]+", _text(value)):
                normalized = normalize_support_role_lane(part)
                if normalized and normalized not in roles:
                    roles.append(normalized)
    return roles


def _spec_value_mapping(value: Any) -> dict[str, str]:
    values: dict[str, str] = {}
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = normalize_support_field_name(key)
            if normalized and _text(item):
                values[normalized] = _text(item)
        return values
    items = value if isinstance(value, (list, tuple, set)) else _list_texts(value)
    for item in items:
        text = _text(item)
        if not text:
            continue
        if "=" in text:
            key, raw_value = text.split("=", 1)
        elif ":" in text:
            key, raw_value = text.split(":", 1)
        else:
            continue
        normalized = normalize_support_field_name(key)
        if normalized and _text(raw_value):
            values[normalized] = _text(raw_value)
    return values


def _row_component_values(row: Mapping[str, Any]) -> dict[str, str]:
    values = _spec_value_mapping(row.get("spec_values") or row.get("concrete_spec_values") or {})
    requested_row_fields = {
        "alternatives",
        "measurable_spec",
        "substitution_allowed",
        "test_equipment",
        "risk_if_missing",
        "equipment",
        "fixture_wiring",
        "calibration_steps",
        "measurement_method",
        "pass_fail_thresholds",
        "linked_bom_refs",
        "linked_risk_control_refs",
        "execution_gate",
        "hazard_id",
        "failure_mode",
        "effect",
        "severity",
        "occurrence",
        "detectability",
        "mitigation",
        "linked_bom_ref",
        "verification_fixture_ref",
        "go_no_go_criteria",
    }
    for key, value in row.items():
        normalized = normalize_support_field_name(key)
        if (
            normalized
            and normalized in set(ROLE_LANE_COMPONENT_REQUIRED_FIELDS).union(requested_row_fields)
            and _text(value)
        ):
            values.setdefault(normalized, _text(value))
    if _looks_like_concrete_source(row.get("source_url") or row.get("url") or row.get("citation_ref")):
        values.setdefault("datasheet_url", _text(row.get("source_url") or row.get("url") or row.get("citation_ref")))
    return values


def assess_component_selection_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    required_roles: Iterable[Any] = (),
    target_artifact: str = "",
) -> dict[str, Any]:
    required = [
        normalize_support_role_lane(role)
        for role in _list_texts(list(required_roles or []))
        if normalize_support_role_lane(role)
    ]
    required = list(dict.fromkeys(required))
    if not required:
        return {
            "schema_name": "ComponentSelectionAssessment",
            "component_selection_workbench_state": "not_required",
            "component_selection_rejected_row_reasons": [],
            "support_role_lane_required_roles": [],
            "support_role_lane_accepted_rows": [],
            "support_role_lane_uncovered_roles": [],
            "grants_execution_authority": False,
        }
    row_list = [dict(row) for row in rows if isinstance(row, Mapping)]
    accepted_roles: set[str] = set()
    accepted_rows: list[dict[str, str]] = []
    rejected_reasons: list[str] = []
    for row in row_list:
        row_target = _text(row.get("target_artifact") or row.get("artifact"))
        row_id = _text(row.get("row_id") or row.get("support_row_id") or row.get("engineering_evidence_row_id"))
        if target_artifact and row_target and row_target != target_artifact:
            rejected_reasons.append(f"wrong_target:{row_id or 'unknown'}:{row_target}")
            continue
        role_values = _support_role_lanes_from_row(row)
        role = next((candidate for candidate in role_values if candidate in required), "")
        if not role:
            rejected_reasons.append(f"wrong_or_missing_role_lane:{row_id or 'unknown'}")
            continue
        covered = {
            normalize_support_field_name(field)
            for field in list(row.get("covered_fields", []) or row.get("required_fields", []) or [])
            if normalize_support_field_name(field)
        }
        covered.update(
            normalize_support_field_name(field)
            for field in list(row.get("support_evidence_field_coverage", []) or [])
            if normalize_support_field_name(field)
        )
        values = _row_component_values(row)
        covered.update(values.keys())
        missing: list[str] = []
        for field in ROLE_LANE_COMPONENT_REQUIRED_FIELDS:
            value = values.get(field, "")
            if field not in covered and not value:
                missing.append(field)
                continue
            if value and _is_placeholder(value):
                missing.append(field)
        if missing:
            for field in missing:
                rejected_reasons.append(f"missing_role_lane_required_field:{role}:{field}")
            continue
        if role not in accepted_roles:
            accepted_roles.add(role)
            accepted_rows.append(
                {
                    "target_role": role,
                    "row_id": row_id,
                    "coverage_state": "accepted",
                }
            )
    uncovered = [role for role in required if role not in accepted_roles]
    if uncovered:
        for role in uncovered:
            rejected_reasons.append(f"missing_required_role_lane:{role}")
    state = "accepted" if not uncovered and accepted_rows else "rejected"
    return {
        "schema_name": "ComponentSelectionAssessment",
        "component_selection_workbench_state": state,
        "component_selection_rejected_row_reasons": sorted(set(rejected_reasons)),
        "support_role_lane_required_roles": required,
        "support_role_lane_accepted_rows": accepted_rows,
        "support_role_lane_uncovered_roles": uncovered,
        "grants_execution_authority": False,
    }


def assess_requested_row_coverage(
    rows: Iterable[Mapping[str, Any]],
    *,
    requested_rows: Iterable[Mapping[str, Any]] = (),
    target_artifact: str = "",
) -> dict[str, Any]:
    requested = [
        dict(row)
        for row in list(requested_rows or [])
        if isinstance(row, Mapping) and _text(row.get("requested_row_id"))
    ]
    if not requested:
        return {
            "schema_name": "RequestedRowCoverageAssessment",
            "requested_row_coverage_state": "not_required",
            "accepted_requested_row_ids": [],
            "uncovered_requested_row_ids": [],
            "rejected_requested_rows": [],
            "grants_execution_authority": False,
        }
    requested_by_id = {
        _text(row.get("requested_row_id")): row
        for row in requested
        if _text(row.get("requested_row_id"))
    }
    accepted: set[str] = set()
    rejected: list[dict[str, Any]] = []
    for raw_row in rows:
        if not isinstance(raw_row, Mapping):
            continue
        row = dict(raw_row)
        row_id = _text(row.get("row_id") or row.get("support_row_id") or row.get("engineering_evidence_row_id"))
        requested_row_id = _text(row.get("requested_row_id"))
        if not requested_row_id:
            rejected.append(
                {
                    "requested_row_id": "",
                    "row_id": row_id,
                    "rejected_reasons": ["missing_requested_row_id"],
                }
            )
            continue
        request = requested_by_id.get(requested_row_id)
        if not request:
            rejected.append(
                {
                    "requested_row_id": requested_row_id,
                    "row_id": row_id,
                    "rejected_reasons": ["unknown_requested_row_id"],
                }
            )
            continue
        reasons: list[str] = []
        requested_target = _text(request.get("target_artifact") or target_artifact)
        row_target = _text(row.get("target_artifact") or row.get("artifact"))
        if requested_target and row_target and row_target != requested_target:
            reasons.append("requested_row_target_mismatch")
        requested_target_row = _text(
            request.get("target_row_id")
            or request.get("target_fixture_ref")
            or request.get("fixture_ref")
            or request.get("design_artifact_row_id")
        )
        if requested_target == "validation_fixtures.json" and requested_target_row:
            row_target_tails = {
                _ref_tail(value)
                for value in (
                    row.get("target_row_id"),
                    row.get("target_fixture_ref"),
                    row.get("fixture_ref"),
                    row.get("validation_fixture_ref"),
                    row.get("fixture_id"),
                    row.get("design_artifact_row_id"),
                )
                if _ref_tail(value)
            }
            requested_tail = _ref_tail(requested_target_row)
            if requested_tail and requested_tail not in row_target_tails:
                reasons.append("requested_row_target_row_mismatch")
        requested_role = normalize_support_role_lane(request.get("target_role") or request.get("role"))
        if requested_role:
            row_roles = _support_role_lanes_from_row(row)
            if requested_role not in row_roles:
                reasons.append("requested_row_role_mismatch")
        required_fields = {
            normalize_support_field_name(field)
            for field in list(request.get("required_fields", []) or [])
            if normalize_support_field_name(field)
        }
        covered_fields = {
            normalize_support_field_name(field)
            for field in list(
                row.get("covered_fields", [])
                or row.get("required_fields", [])
                or row.get("support_evidence_field_coverage", [])
                or []
            )
            if normalize_support_field_name(field)
        }
        values = _row_component_values(row)
        covered_fields.update(values.keys())
        missing_fields = sorted(
            field
            for field in required_fields
            if field not in covered_fields
            or not values.get(field, "")
            or _is_placeholder(values.get(field, ""))
        )
        if missing_fields:
            reasons.append("missing_requested_row_fields:" + ",".join(missing_fields[:8]))
        if reasons:
            rejected.append(
                {
                    "requested_row_id": requested_row_id,
                    "row_id": row_id,
                    "rejected_reasons": list(dict.fromkeys(reasons)),
                }
            )
            continue
        accepted.add(requested_row_id)
    uncovered = [
        requested_id
        for requested_id in requested_by_id
        if requested_id not in accepted
    ]
    state = "accepted" if not uncovered else "incomplete"
    return {
        "schema_name": "RequestedRowCoverageAssessment",
        "requested_row_coverage_state": state,
        "accepted_requested_row_ids": sorted(accepted),
        "uncovered_requested_row_ids": uncovered,
        "rejected_requested_rows": rejected,
        "grants_execution_authority": False,
    }


def support_manifest_covered_fields(
    manifest: Mapping[str, Any],
    *,
    target_artifact: str = "",
) -> list[str]:
    target = _text(target_artifact)
    covered: list[str] = []

    def _add(values: Any) -> None:
        for item in _list_texts(values):
            normalized = normalize_support_field_name(item)
            if normalized and normalized not in covered:
                covered.append(normalized)

    _add(manifest.get("covered_fields") or manifest.get("field_coverage") or manifest.get("support_evidence_field_coverage"))
    for pack in list(manifest.get("packs", []) or []):
        if not isinstance(pack, Mapping):
            continue
        pack_target = _text(pack.get("target_artifact") or pack.get("artifact"))
        if target and pack_target and pack_target != target:
            continue
        _add(pack.get("covered_fields") or pack.get("field_coverage") or pack.get("support_evidence_field_coverage"))
        for row in list(pack.get("rows", []) or []):
            if not isinstance(row, Mapping):
                continue
            row_target = _text(row.get("target_artifact") or row.get("artifact"))
            if target and row_target and row_target != target:
                continue
            _add(
                row.get("covered_fields")
                or row.get("field_coverage")
                or row.get("support_evidence_field_coverage")
                or row.get("required_fields")
            )
    return sorted(covered)


def assess_support_field_coverage(
    manifest: Mapping[str, Any],
    *,
    target_artifact: str = "",
    required_fields: Iterable[str] = (),
) -> dict[str, Any]:
    required = sorted(
        {
            normalize_support_field_name(item)
            for item in list(required_fields or [])
            if normalize_support_field_name(item)
        }
    )
    covered = support_manifest_covered_fields(manifest, target_artifact=target_artifact)
    covered_set = set(covered)
    covered_required = [field for field in required if field in covered_set]
    uncovered = [field for field in required if field not in covered_set]
    row_count = 0
    try:
        row_count = int(manifest.get("total_row_count", 0) or 0)
    except (TypeError, ValueError):
        row_count = 0
    if not required:
        state = "not_required"
    elif row_count <= 0:
        state = "missing_support_rows"
    elif uncovered:
        state = "insufficient_field_coverage"
    else:
        state = "adequate"
    return {
        "schema_name": "SupportAdequacyAssessment",
        "support_adequacy_state": state,
        "support_required_missing_fields": required,
        "support_covered_missing_fields": covered_required,
        "support_uncovered_missing_fields": uncovered,
        "support_manifest_covered_fields": covered,
        "support_pack_rows_available": row_count,
        "grants_execution_authority": False,
    }


def _row_values(payload: Mapping[str, Any]) -> Iterable[tuple[str, list[Any]]]:
    summary = payload.get("payload_summary", {})
    summary_map = summary if isinstance(summary, Mapping) else {}
    for key in SUPPORT_ROW_KEYS:
        for source in (payload, summary_map):
            values = source.get(key, []) if isinstance(source, Mapping) else []
            if isinstance(values, Mapping):
                values = [values]
            if isinstance(values, list):
                yield key, list(values)


def _payload_summary_has_rows(payload: Mapping[str, Any]) -> bool:
    summary = payload.get("payload_summary", {})
    if not isinstance(summary, Mapping):
        return False
    return any(bool(summary.get(key)) for key in SUPPORT_ROW_KEYS)


def _normalize_row(
    value: Mapping[str, Any],
    *,
    row_kind: str,
    target_artifact: str,
    required_fields: Iterable[str],
    required_gates: Iterable[str],
    build_depth: bool,
) -> tuple[dict[str, Any], list[str]]:
    reasons: list[str] = []
    row_id = _text(value.get("row_id"))
    claim = _text(value.get("claim") or value.get("summary") or value.get("text"))
    source_hint = _text(
        value.get("source_hint")
        or value.get("source_url")
        or value.get("source")
        or value.get("url")
        or value.get("citation_ref")
    )
    source_url = _text(value.get("source_url") or value.get("url"))
    citation_ref = _text(value.get("citation_ref"))
    evidence_ref = _text(value.get("evidence_ref"))
    row_target_artifact = _text(value.get("target_artifact") or value.get("artifact"))
    target_gate = _text(value.get("target_gate") or value.get("required_gate") or value.get("gate"))
    raw_spec_values = value.get("spec_values")
    if raw_spec_values is None:
        raw_spec_values = value.get("concrete_spec_values")
    if isinstance(raw_spec_values, Mapping):
        spec_values: Any = dict(raw_spec_values)
    elif isinstance(raw_spec_values, list):
        spec_values = list(raw_spec_values)
    elif isinstance(raw_spec_values, tuple):
        spec_values = list(raw_spec_values)
    else:
        spec_values = _list_texts(raw_spec_values)
    required_field_values = _inferred_field_coverage(
        value,
        required_fields=required_fields,
        required_gates=required_gates,
    )
    relevance = _text(value.get("relevance") or value.get("rationale") or value.get("target_gate_relevance"))
    if not row_id:
        reasons.append("missing_row_id")
    if not claim or _is_placeholder(claim):
        reasons.append("missing_concrete_claim")
    if not (source_hint or source_url or citation_ref):
        reasons.append("missing_source_hint")
    source_quality = "concrete" if (
        _looks_like_concrete_source(source_url)
        or _looks_like_concrete_source(citation_ref)
        or _looks_like_concrete_source(source_hint)
    ) else "context_only" if source_hint else "missing"
    claim_lower = claim.lower()
    if any(fragment in claim_lower for fragment in CONTEXT_ONLY_CLAIM_FRAGMENTS):
        reasons.append("context_summary_not_build_depth_evidence")
    if any(fragment in claim_lower for fragment in WRONG_DOMAIN_FRAGMENTS):
        reasons.append("support_evidence_domain_mismatch")
    if build_depth and source_quality != "concrete":
        reasons.append("missing_concrete_source_reference")
    if build_depth and not required_field_values:
        reasons.append("missing_required_field_coverage")
    if not evidence_ref:
        reasons.append("missing_evidence_ref")
    if bool(value.get("grants_execution_authority", False)):
        reasons.append("grants_execution_authority_not_allowed")

    target_terms = [_text(target_artifact).lower()]
    target_terms.extend(_text(item).lower() for item in required_fields if _text(item))
    target_terms.extend(_text(item).lower() for item in required_gates if _text(item))
    relevance_text = " ".join(
        [
            row_target_artifact,
            target_gate,
            relevance,
            " ".join(required_field_values),
        ]
    ).lower()
    if not (row_target_artifact or target_gate or required_field_values or relevance):
        reasons.append("missing_target_relevance")
    if target_artifact and row_target_artifact and row_target_artifact != target_artifact:
        reasons.append("support_evidence_target_mismatch")

    row = {
        "row_id": row_id,
        "engineering_evidence_row_id": _text(value.get("engineering_evidence_row_id")),
        "support_row_id": _text(value.get("support_row_id")),
        "requested_row_id": _text(value.get("requested_row_id")),
        "source_candidate_id": _text(value.get("source_candidate_id")),
        "target_row_id": _text(value.get("target_row_id") or value.get("design_artifact_row_id")),
        "design_artifact_row_id": _text(value.get("design_artifact_row_id")),
        "target_role": _text(value.get("target_role") or value.get("role") or value.get("required_for")),
        "role": _text(value.get("role")),
        "required_for": _text(value.get("required_for")),
        "operator_seed_pack_id": _text(value.get("operator_seed_pack_id")),
        "operator_seed_template_id": _text(value.get("operator_seed_template_id")),
        "operator_seed_pack_template_bound": bool(value.get("operator_seed_pack_template_bound", False)),
        "row_kind": row_kind,
        "support_row_kind": _text(value.get("support_row_kind") or value.get("obligation_kind")),
        "technology_design_obligation_id": _text(value.get("technology_design_obligation_id")),
        "r_and_d_design_brief_id": _text(value.get("r_and_d_design_brief_id")),
        "claim": claim,
        "source_hint": source_hint,
        "source_url": source_url,
        "citation_ref": citation_ref,
        "evidence_ref": evidence_ref,
        "target_artifact": row_target_artifact,
        "target_gate": target_gate,
        "required_fields": required_field_values,
        "covered_fields": required_field_values,
        "spec_values": spec_values,
        "relevance": relevance,
        "support_evidence_source_quality": source_quality,
        "support_evidence_field_coverage": required_field_values,
        "support_evidence_domain_match": "support_evidence_domain_mismatch" not in reasons,
        "support_evidence_contract_passed": not reasons,
        "grants_execution_authority": False,
    }
    return row, reasons


def extract_consumable_support_evidence(
    payload: Mapping[str, Any],
    *,
    target_artifact: str = "",
    required_fields: Iterable[str] = (),
    required_gates: Iterable[str] = (),
    row_limit: int = SUPPORT_EVIDENCE_ROW_LIMIT,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    rejected_reasons: list[str] = []
    raw_row_count = 0
    build_depth = _build_depth_requested(
        payload,
        target_artifact=target_artifact,
        required_fields=required_fields,
        required_gates=required_gates,
    )
    for row_kind, values in _row_values(payload):
        for value in values:
            if not isinstance(value, Mapping):
                rejected_reasons.append("non_mapping_support_row")
                continue
            raw_row_count += 1
            row, reasons = _normalize_row(
                value,
                row_kind=row_kind,
                target_artifact=target_artifact,
                required_fields=required_fields,
                required_gates=required_gates,
                build_depth=build_depth,
            )
            if reasons:
                rejected_reasons.extend(reasons)
                continue
            rows.append(row)
            if len(rows) >= max(1, int(row_limit or SUPPORT_EVIDENCE_ROW_LIMIT)):
                break
        if len(rows) >= max(1, int(row_limit or SUPPORT_EVIDENCE_ROW_LIMIT)):
            break

    if rows:
        state = "consumable"
        reasons = []
    elif raw_row_count:
        state = "no_source_backed_rows"
        reasons = sorted(set(rejected_reasons or ["zero_consumable_support_rows"]))
    else:
        summary = payload.get("payload_summary", {})
        summary_map = summary if isinstance(summary, Mapping) else {}
        has_preview = any(bool(summary_map.get(key) or payload.get(key)) for key in SUPPORT_PREVIEW_ONLY_KEYS)
        state = "metadata_only" if has_preview or payload else "missing_or_unreadable"
        reasons = ["zero_consumable_support_rows"]
        if has_preview:
            reasons.append("preview_metadata_only")

    return {
        "rows": rows,
        "consumable_support_row_count": len(rows),
        "support_archive_payload_summary_rows_used": bool(rows and _payload_summary_has_rows(payload)),
        "support_role_lane_covered_roles": sorted(
            {
                role
                for row in rows
                for role in _support_role_lanes_from_row(row)
                if role
            }
        ),
        "support_pack_consumability_state": state,
        "non_consumable_support_reasons": reasons,
        "support_pack_source_missing": state == "missing_or_unreadable",
        "build_depth_consumable_support_row_count": len(rows) if build_depth else 0,
        "support_evidence_contract_passed": bool(rows) if build_depth else state == "consumable",
        "support_evidence_field_coverage": sorted(
            {
                field
                for row in rows
                for field in list(row.get("support_evidence_field_coverage", []) or [])
                if str(field).strip()
            }
        ),
        "support_evidence_source_quality": "source_backed" if rows else "insufficient",
        "support_evidence_domain_match": "support_evidence_domain_mismatch" not in reasons,
        "support_evidence_rejected_reasons": reasons,
        "grants_execution_authority": False,
    }


def support_consumability_summary(
    payload: Mapping[str, Any],
    *,
    target_artifact: str = "",
    required_fields: Iterable[str] = (),
    required_gates: Iterable[str] = (),
) -> dict[str, Any]:
    extracted = extract_consumable_support_evidence(
        payload,
        target_artifact=target_artifact,
        required_fields=required_fields,
        required_gates=required_gates,
    )
    return {
        "consumable_support_row_count": int(extracted.get("consumable_support_row_count", 0) or 0),
        "support_archive_payload_summary_rows_used": bool(
            extracted.get("support_archive_payload_summary_rows_used", False)
        ),
        "support_pack_consumability_state": str(extracted.get("support_pack_consumability_state", "") or ""),
        "non_consumable_support_reasons": list(extracted.get("non_consumable_support_reasons", []) or []),
        "support_pack_source_missing": bool(extracted.get("support_pack_source_missing", False)),
        "build_depth_consumable_support_row_count": int(
            extracted.get("build_depth_consumable_support_row_count", 0) or 0
        ),
        "support_evidence_contract_passed": bool(
            extracted.get("support_evidence_contract_passed", False)
        ),
        "support_evidence_field_coverage": list(
            extracted.get("support_evidence_field_coverage", []) or []
        ),
        "support_role_lane_covered_roles": list(
            extracted.get("support_role_lane_covered_roles", []) or []
        ),
        "support_evidence_source_quality": str(
            extracted.get("support_evidence_source_quality", "") or ""
        ),
        "support_evidence_domain_match": bool(
            extracted.get("support_evidence_domain_match", False)
        ),
        "support_evidence_rejected_reasons": list(
            extracted.get("support_evidence_rejected_reasons", []) or []
        ),
        "grants_execution_authority": False,
    }

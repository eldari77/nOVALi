from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .operator_feedback_obligations import parse_operator_feedback_obligations
from .support_evidence import normalize_support_field_name


TASK_MANAGER_SCHEMA_VERSION = "novali_conveyor_task_manager_v1"
TASK_MANAGER_SNAPSHOT_SCHEMA_NAME = "TaskManagerSnapshot"
TASK_MANAGER_LEASE_SCHEMA_NAME = "TaskManagerLease"
TASK_MANAGER_REPAIR_INTENT_SCHEMA_NAME = "TaskManagerRepairIntent"
TASK_MANAGER_REPAIR_APPLIED_SCHEMA_NAME = "TaskManagerRepairApplied"
TERMINAL_CHILD_STATES = {"returned", "failed", "stopped"}
TERMINAL_DIRECTIVE_STATES = {"accepted", "rejected", "split"}
TASK_MANAGER_DEFAULT_MAX_ACTIVE_CHILDREN = 4
TASK_MANAGER_LEASE_TTL_SECONDS = 600
TASK_MANAGER_EMPTY_LEASE_STALE_SECONDS = 30

INTERFACE_SPEC_REQUIRED_SUPPORT_FIELDS = (
    "connector",
    "pinout",
    "protocol",
    "signal_level",
    "sample_rate",
    "bandwidth",
    "latency_budget",
    "electrical_isolation",
    "safety_limit",
    "failure_behavior",
    "validation_hooks",
    "hardware_abstraction_layer_id",
    "device_capability_manifest_ref",
    "bom_ref",
    "validation_fixture_ref",
    "linked_risk_control_ref",
)

ROLE_SPLIT_REQUIRED_SUPPORT_FIELDS = (
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

FULL_DIVE_LINKED_ARTIFACT_RETARGET_ORDER = (
    "bill_of_materials.json",
    "risk_controls.json",
    "validation_fixtures.json",
)

LINKED_ARTIFACT_REQUIRED_FIELDS = {
    "bill_of_materials.json": (
        "manufacturer",
        "mpn",
        "datasheet_url",
        "electrical_rating",
        "quantity",
        "unit_cost",
        "cost_basis",
        "alternatives",
        "measurable_spec",
        "substitution_allowed",
        "test_equipment",
        "risk_if_missing",
        "validation_fixture_ref",
        "compliance_notes",
        "linked_risk_control_ref",
        "standards_assumption",
        "go_no_go_trace",
        "execution_gate",
    ),
    "risk_controls.json": (
        "detection",
        "rpn",
        "residual_risk",
        "standard_ref",
        "verification_method",
        "linked_bom_ref",
        "verification_fixture_ref",
        "execution_gate",
    ),
    "validation_fixtures.json": (
        "equipment",
        "fixture_wiring",
        "calibration_steps",
        "measurement_method",
        "pass_fail_thresholds",
        "linked_bom_refs",
        "linked_risk_control_refs",
        "execution_gate",
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_utc_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _record_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(
        "|".join(json.dumps(part, sort_keys=True, default=str) for part in parts).encode("utf-8")
    ).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _list_texts(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item or "").strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _normalized_fields(*values: Any) -> list[str]:
    fields: list[str] = []
    for value in values:
        for item in _list_texts(value):
            normalized = normalize_support_field_name(item)
            if normalized and normalized not in fields:
                fields.append(normalized)
    return fields


def _json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _artifact_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in (
        "interfaces",
        "items",
        "components",
        "rows",
        "risk_controls",
        "controls",
        "fixtures",
        "validation_fixtures",
    ):
        for item in list(payload.get(key, []) or []):
            if isinstance(item, Mapping):
                rows.append(dict(item))
    if not rows and payload:
        rows.append(dict(payload))
    return rows


def _row_has_field(row: Mapping[str, Any], field: str) -> bool:
    normalized = normalize_support_field_name(field)
    aliases = {
        "datasheet_url": ("source_url", "datasheet_source_url"),
        "unit_cost": ("cost_basis",),
        "electrical_rating": ("electrical_ratings", "ratings"),
        "pass_fail_thresholds": ("acceptance_thresholds",),
        "validation_fixture_ref": ("fixture_ref", "validation_fixture_refs"),
        "linked_risk_control_ref": ("risk_ref", "risk_refs", "linked_risk_control_refs"),
        "hardware_abstraction_layer_id": ("hal_id", "hal_ref"),
        "device_capability_manifest_ref": ("device_manifest_ref", "device_manifest"),
    }
    candidate_fields = [field, normalized, *aliases.get(normalized, ())]
    for candidate in candidate_fields:
        value = row.get(candidate)
        if value not in ("", None, [], {}):
            return True
    return False


def _draft_artifact(operator_root: str | Path, directive_id: str, artifact: str) -> dict[str, Any]:
    return _json_file(
        Path(operator_root)
        / "conveyor"
        / "campaigns"
        / directive_id
        / "drafts"
        / artifact
    )


def _artifact_contract_complete(
    operator_root: str | Path,
    *,
    directive_id: str,
    artifact: str,
    required_fields: Iterable[str],
) -> bool:
    rows = _artifact_rows(_draft_artifact(operator_root, directive_id, artifact))
    if not rows:
        return False
    for field in required_fields:
        if not any(_row_has_field(row, field) for row in rows):
            return False
    return True


def _identity_token(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.split("#")[-1].split(":")[-1].strip()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _row_identity_tokens(row: Mapping[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for field in (
        "requested_row_id",
        "closes_requested_row_id",
        "target_row_id",
        "closes_target_row_id",
        "design_artifact_row_id",
        "closes_design_artifact_row_id",
        "fixture_id",
        "item_id",
        "control_id",
        "row_id",
        "id",
        "name",
    ):
        token = _identity_token(row.get(field))
        if token:
            tokens.add(token)
    for field in ("support_row_ids", "evidence_refs"):
        raw = row.get(field, []) or []
        values = raw if isinstance(raw, (list, tuple, set)) else [raw]
        for item in values:
            token = _identity_token(item)
            if token:
                tokens.add(token)
    return tokens


def _accepted_requested_row_ids_for_support(request: Mapping[str, Any], *, target_artifact: str) -> list[str]:
    accepted: list[str] = []
    for field in (
        "accepted_requested_row_ids",
        "accepted_fmea_requested_row_ids",
        "accepted_validation_fixture_requested_row_ids",
        "accepted_enriched_role_lane_row_ids",
    ):
        if field.startswith("accepted_validation_fixture") and target_artifact != "validation_fixtures.json":
            continue
        if field.startswith("accepted_fmea") and target_artifact != "risk_controls.json":
            continue
        for item in list(request.get(field, []) or []):
            text = str(item or "").strip()
            if text and text not in accepted:
                accepted.append(text)
    return accepted


def _requested_row_materialization_assessment(
    operator_root: str | Path,
    *,
    directive_id: str,
    target_artifact: str,
    request: Mapping[str, Any],
) -> dict[str, Any]:
    accepted_ids = _accepted_requested_row_ids_for_support(request, target_artifact=target_artifact)
    requested_rows = [
        dict(row)
        for row in list(request.get("requested_rows", []) or [])
        if isinstance(row, Mapping) and str(row.get("requested_row_id", "") or "").strip()
    ]
    if not accepted_ids or not requested_rows:
        return {
            "support_materialization_closure_state": "not_required",
            "support_materialization_pending_requested_row_ids": [],
        }
    requested_by_id = {
        str(row.get("requested_row_id", "") or "").strip(): row
        for row in requested_rows
        if str(row.get("requested_row_id", "") or "").strip()
    }
    rows = _artifact_rows(_draft_artifact(operator_root, directive_id, target_artifact))
    pending: list[str] = []
    for requested_id in accepted_ids:
        requested = requested_by_id.get(requested_id, {})
        requested_tokens = {_identity_token(requested_id)}
        for field in (
            "target_row_id",
            "target_fixture_ref",
            "fixture_ref",
            "design_artifact_row_id",
            "target_role",
        ):
            token = _identity_token(requested.get(field))
            if token:
                requested_tokens.add(token)
        required_fields = [
            normalize_support_field_name(field)
            for field in list(requested.get("required_fields", []) or LINKED_ARTIFACT_REQUIRED_FIELDS.get(target_artifact, ()))
            if normalize_support_field_name(field)
        ]
        matched = False
        for row in rows:
            if bool(row.get("grants_execution_authority", False)):
                continue
            row_tokens = _row_identity_tokens(row)
            if not requested_tokens.intersection(row_tokens):
                continue
            if all(_row_has_field(row, field) for field in required_fields):
                matched = True
                break
        if not matched:
            pending.append(requested_id)
    return {
        "support_materialization_closure_state": "closed" if not pending else "pending",
        "support_materialization_pending_requested_row_ids": pending,
        "support_materialization_pending_reason": "visible_artifact_rows_missing_requested_row_closure"
        if pending
        else "",
    }


def _retarget_closed_interface_for_admission(
    operator_root: str | Path,
    *,
    directive: Mapping[str, Any],
    target_artifact: str,
) -> tuple[str, dict[str, Any]]:
    target = str(target_artifact or "").strip()
    retarget_chain = ("interface_specifications.json",) + tuple(FULL_DIVE_LINKED_ARTIFACT_RETARGET_ORDER)
    if target not in retarget_chain[:-1]:
        return target, {}
    directive_id = str(directive.get("directive_id", "") or "").strip()
    if not directive_id:
        return target, {}
    required_fields = (
        INTERFACE_SPEC_REQUIRED_SUPPORT_FIELDS
        if target == "interface_specifications.json"
        else LINKED_ARTIFACT_REQUIRED_FIELDS.get(target, ())
    )
    if not _artifact_contract_complete(
        operator_root,
        directive_id=directive_id,
        artifact=target,
        required_fields=required_fields,
    ):
        return target, {}
    next_candidates = (
        FULL_DIVE_LINKED_ARTIFACT_RETARGET_ORDER
        if target == "interface_specifications.json"
        else FULL_DIVE_LINKED_ARTIFACT_RETARGET_ORDER[
            FULL_DIVE_LINKED_ARTIFACT_RETARGET_ORDER.index(target) + 1 :
        ]
    )
    for linked_artifact in next_candidates:
        if not _artifact_contract_complete(
            operator_root,
            directive_id=directive_id,
            artifact=linked_artifact,
            required_fields=LINKED_ARTIFACT_REQUIRED_FIELDS.get(linked_artifact, ()),
        ):
            remaining = [
                item
                for item in next_candidates
                if item == linked_artifact
                or not _artifact_contract_complete(
                    operator_root,
                    directive_id=directive_id,
                    artifact=item,
                    required_fields=LINKED_ARTIFACT_REQUIRED_FIELDS.get(item, ()),
                )
            ]
            return linked_artifact, {
                "partial_target_correct_closure": True,
                "closed_target_artifact": target,
                "next_linked_artifact_target": linked_artifact,
                "remaining_linked_artifact_gaps": remaining,
                "support_admission_retarget_reason": (
                    "partial_target_correct_closure"
                    if target == "interface_specifications.json"
                    else "linked_target_artifact_closure"
                ),
            }
    return target, {}


def _normalize_role_lane(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9/]+", "_", text).strip("_")
    text = re.sub(r"_+", "_", text)
    aliases = {
        "thermal": "thermal_sensor_interface",
        "thermal_sensor": "thermal_sensor_interface",
        "thermal_sensor_interface": "thermal_sensor_interface",
        "separate_thermal": "thermal_sensor_interface",
        "separate_thermal_sensor": "thermal_sensor_interface",
        "separate_thermal_sensor_interface": "thermal_sensor_interface",
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
        "daq": "daq_logger_or_microcontroller_interface",
        "daq_logging": "daq_logger_or_microcontroller_interface",
        "logger": "daq_logger_or_microcontroller_interface",
        "microcontroller": "daq_logger_or_microcontroller_interface",
        "daq/logger": "daq_logger_or_microcontroller_interface",
        "daq_logger": "daq_logger_or_microcontroller_interface",
        "daq_logger_or_microcontroller_interface": "daq_logger_or_microcontroller_interface",
        "logger_or_microcontroller_interface": "daq_logger_or_microcontroller_interface",
        "daq_logger_microcontroller_interface": "daq_logger_or_microcontroller_interface",
    }
    return aliases.get(text, text)


def _list_role_lanes(value: Any) -> list[str]:
    roles: list[str] = []
    if isinstance(value, Mapping):
        for key in ("target_role", "role", "required_for", "category", "function", "subsystem", "row_id", "item_id", "name"):
            roles.extend(_list_role_lanes(value.get(key)))
        return list(dict.fromkeys(role for role in roles if role))
    if isinstance(value, (list, tuple, set)):
        for item in value:
            roles.extend(_list_role_lanes(item))
        return list(dict.fromkeys(role for role in roles if role))
    text = str(value or "").strip()
    if not text:
        return []
    parts = re.split(r"[,;|]+", text)
    for part in parts:
        normalized = _normalize_role_lane(part)
        if normalized:
            roles.append(normalized)
    return list(dict.fromkeys(roles))


def _required_role_lanes_for_directive(
    directive: Mapping[str, Any],
    *,
    target_artifact: str,
) -> list[str]:
    if target_artifact != "bill_of_materials.json":
        return []
    feedback = str(directive.get("operator_feedback", "") or "")
    if not feedback:
        return []
    contract = parse_operator_feedback_obligations(feedback)
    roles: list[str] = []
    for split in list(contract.required_role_splits or []):
        if str(split.artifact_name or "").strip() and str(split.artifact_name or "").strip() != target_artifact:
            continue
        if _normalize_role_lane(split.base_role) != "sensor_array":
            continue
        for role in split.required_roles:
            normalized = _normalize_role_lane(role)
            if normalized and normalized not in roles:
                roles.append(normalized)
    return roles


def _operator_feedback_target_artifact(directive: Mapping[str, Any]) -> str:
    feedback = str(directive.get("operator_feedback", "") or "").strip()
    if not feedback:
        return ""
    explicit = re.search(
        r"target\s+artifact\s*:\s*([a-z0-9_./-]+\.json)",
        feedback,
        flags=re.IGNORECASE,
    )
    if explicit:
        return str(explicit.group(1) or "").strip()
    return ""


def _support_role_lane_assessment(
    request: Mapping[str, Any],
    *,
    directive: Mapping[str, Any],
    target_artifact: str,
) -> dict[str, Any]:
    required_roles = _required_role_lanes_for_directive(directive, target_artifact=target_artifact)
    if not required_roles:
        return {
            "support_role_lane_coverage_state": "not_required",
            "support_role_lane_required_roles": [],
            "support_role_lane_covered_roles": [],
            "support_role_lane_uncovered_roles": [],
        }
    covered_roles = _list_role_lanes(
        request.get("support_role_lane_covered_roles")
        or request.get("materialized_role_split_rows")
        or request.get("support_role_lanes")
    )
    covered_set = set(covered_roles)
    uncovered = [role for role in required_roles if role not in covered_set]
    state = "adequate" if not uncovered else "insufficient_role_lane_coverage"
    return {
        "support_role_lane_coverage_state": state,
        "support_role_lane_required_roles": required_roles,
        "support_role_lane_covered_roles": covered_roles,
        "support_role_lane_uncovered_roles": uncovered,
    }


def _support_required_fields_for_admission(
    request: Mapping[str, Any],
    *,
    target_artifact: str,
) -> list[str]:
    explicit = _normalized_fields(
        request.get("missing_field_coverage"),
        request.get("support_uncovered_missing_fields"),
        request.get("post_materialization_uncovered_fields"),
        request.get("depth_missing_fields"),
        request.get("missing_fields"),
    )
    if target_artifact == "interface_specifications.json":
        required = list(INTERFACE_SPEC_REQUIRED_SUPPORT_FIELDS)
        if len(explicit) >= len(required):
            return explicit
        return _normalized_fields(required)
    if target_artifact == "bill_of_materials.json" and list(
        request.get("support_role_lane_required_roles", []) or request.get("support_role_lane_covered_roles", []) or []
    ):
        return _normalized_fields(explicit, ROLE_SPLIT_REQUIRED_SUPPORT_FIELDS)
    return explicit


def _support_covered_fields_for_admission(request: Mapping[str, Any]) -> list[str]:
    return _normalized_fields(
        request.get("support_covered_missing_fields"),
        request.get("support_evidence_field_coverage"),
        request.get("covered_fields"),
        request.get("field_coverage"),
    )


def _support_request_state(request: Mapping[str, Any]) -> str:
    state = str(request.get("state", "") or "").strip()
    support_state = str(request.get("support_state", "") or "").strip()
    terminal_states = {"failed", "rejected", "superseded", "cancelled"}
    if support_state in terminal_states:
        return support_state
    if state in terminal_states:
        return state
    if state in {
        "commercial_source_acquisition_required",
        "source_backed_rows_required",
        "pending_operator_review",
        "blocked_for_support",
    }:
        return state
    return support_state or state


def _decomposed_requested_parent_ids_covered(
    request: Mapping[str, Any],
    *,
    accepted_ids: Iterable[str] | None = None,
) -> set[str]:
    accepted_set = {
        str(item or "").strip()
        for item in list(accepted_ids or request.get("accepted_requested_row_ids", []) or [])
        if str(item or "").strip()
    }
    children_by_parent: dict[str, set[str]] = {}
    for item in list(request.get("requested_rows", []) or []):
        if not isinstance(item, Mapping):
            continue
        requested_id = str(item.get("requested_row_id", "") or "").strip()
        parent_id = str(item.get("decomposed_from_requested_row_id", "") or "").strip()
        if not requested_id or not parent_id:
            continue
        children_by_parent.setdefault(parent_id, set()).add(requested_id)
    return {
        parent_id
        for parent_id, child_ids in children_by_parent.items()
        if child_ids and child_ids.issubset(accepted_set)
    }


def _prune_decomposed_parent_uncovered_ids(
    uncovered_ids: Iterable[str],
    request: Mapping[str, Any],
    *,
    accepted_ids: Iterable[str] | None = None,
) -> tuple[list[str], list[str]]:
    closed_parent_ids = _decomposed_requested_parent_ids_covered(
        request,
        accepted_ids=accepted_ids,
    )
    pruned: list[str] = []
    removed: list[str] = []
    for item in uncovered_ids:
        requested_id = str(item or "").strip()
        if not requested_id:
            continue
        if requested_id in closed_parent_ids:
            removed.append(requested_id)
            continue
        pruned.append(requested_id)
    return pruned, removed


def _requested_row_coverage_complete(request: Mapping[str, Any]) -> tuple[bool, list[str], list[str]]:
    requested_rows = [
        dict(item)
        for item in list(request.get("requested_rows", []) or [])
        if isinstance(item, Mapping)
    ]
    requested_ids = [
        str(row.get("requested_row_id", "") or "").strip()
        for row in requested_rows
        if str(row.get("requested_row_id", "") or "").strip()
    ]
    accepted_ids = [
        str(item or "").strip()
        for item in list(request.get("accepted_requested_row_ids", []) or [])
        if str(item or "").strip()
    ]
    accepted_set = set(accepted_ids)
    uncovered_ids = [
        str(item or "").strip()
        for item in list(request.get("uncovered_requested_row_ids", []) or [])
        if str(item or "").strip()
    ]
    uncovered_ids, _closed_parent_ids = _prune_decomposed_parent_uncovered_ids(
        uncovered_ids,
        request,
        accepted_ids=accepted_ids,
    )
    if not uncovered_ids:
        uncovered_ids = [
            requested_id
            for requested_id in requested_ids
            if requested_id not in accepted_set
        ]
    complete = bool(requested_ids) and not uncovered_ids and set(requested_ids).issubset(accepted_set)
    return complete, accepted_ids, uncovered_ids


def _support_admission_assessment(
    request: Mapping[str, Any],
    *,
    target_artifact: str,
) -> dict[str, Any]:
    support_id = str(request.get("support_request_id", "") or "").strip()
    if not request:
        return {
            "support_admission_state": "missing_support_request",
            "support_admission_blocker_reason": "missing_support_request",
            "support_admission_request_id": support_id,
            "support_admission_uncovered_fields": _support_required_fields_for_admission(
                {},
                target_artifact=target_artifact,
            ),
        }
    request_target = str(request.get("target_artifact", "") or "").strip()
    if target_artifact and request_target and request_target != target_artifact:
        return {
            "support_admission_state": "wrong_target",
            "support_admission_blocker_reason": "support_request_targets_different_artifact",
            "support_admission_request_id": support_id,
            "support_admission_uncovered_fields": _support_required_fields_for_admission(
                request,
                target_artifact=target_artifact,
            ),
        }
    if (
        bool(request.get("technology_design_obligation_active", False))
        and str(request.get("support_satisfaction_mode", "") or "") == "technology_design_obligation"
        and _support_request_state(request) == "satisfied"
        and str(request.get("r_and_d_design_brief_id", "") or "").strip()
    ):
        requested_rows = [
            dict(item)
            for item in list(request.get("requested_rows", []) or [])
            if isinstance(item, Mapping)
        ]
        requested_ids = [
            str(row.get("requested_row_id", "") or "").strip()
            for row in requested_rows
            if str(row.get("requested_row_id", "") or "").strip()
        ]
        commercial_requested = any(
            bool(row.get("commercial_component_source_required", False))
            for row in requested_rows
        )
        role_lanes = [
            str(item or "").strip()
            for item in list(request.get("support_role_lane_required_roles", []) or [])
            if str(item or "").strip()
        ]
        commercial_fields = {
            "manufacturer",
            "mpn",
            "datasheet_url",
            "electrical_rating",
            "quantity",
            "unit_cost",
            "cost_basis",
            "alternatives",
            "validation_fixture_ref",
            "linked_risk_control_ref",
            "standards_assumption",
            "measurable_spec",
            "test_equipment",
            "risk_if_missing",
            "go_no_go_trace",
        }
        required_fields = set(_support_required_fields_for_admission(request, target_artifact=target_artifact))
        commercial_bom_target = bool(
            target_artifact == "bill_of_materials.json"
            and (required_fields & commercial_fields)
        )
        if commercial_requested or role_lanes or commercial_bom_target:
            return {
                "support_admission_state": "insufficient_requested_row_coverage",
                "support_admission_blocker_reason": (
                    "design_brief_cannot_satisfy_commercial_requested_rows"
                    if requested_rows or role_lanes
                    else "design_brief_cannot_satisfy_commercial_bom_fields"
                ),
                "support_admission_request_id": support_id,
                "support_admission_uncovered_fields": requested_ids or role_lanes or sorted(required_fields & commercial_fields),
                "uncovered_requested_row_ids": requested_ids,
            }
        return {
            "support_admission_state": "r_and_d_design_brief_ready",
            "support_admission_blocker_reason": "",
            "support_admission_request_id": support_id,
            "support_admission_uncovered_fields": [],
            "child_work_mode": "design_only_reduction",
            "r_and_d_design_brief_ready": True,
        }
    state = _support_request_state(request)
    requested_row_coverage_complete, accepted_requested_ids, coverage_uncovered_ids = (
        _requested_row_coverage_complete(request)
    )
    stale_commercial_flags_cleared = (
        state == "commercial_source_acquisition_required"
        or bool(request.get("commercial_source_acquisition_required", False))
        or bool(request.get("source_backed_rows_required", False))
    ) and str(request.get("support_state", "") or "").strip() == "satisfied" and requested_row_coverage_complete
    if stale_commercial_flags_cleared:
        state = "satisfied"
    if state == "commercial_source_acquisition_required" or bool(
        request.get("commercial_source_acquisition_required", False)
    ) and not requested_row_coverage_complete:
        requested_rows = [
            dict(item)
            for item in list(request.get("requested_rows", []) or [])
            if isinstance(item, Mapping)
        ]
        requested_ids = [
            str(row.get("requested_row_id", "") or "").strip()
            for row in requested_rows
            if str(row.get("requested_row_id", "") or "").strip()
        ]
        uncovered_requested_ids = [
            str(item or "").strip()
            for item in list(request.get("uncovered_requested_row_ids", []) or [])
            if str(item or "").strip()
        ] or requested_ids
        uncovered_requested_ids, closed_abstract_ids = _prune_decomposed_parent_uncovered_ids(
            uncovered_requested_ids,
            request,
            accepted_ids=request.get("accepted_requested_row_ids", []),
        )
        uncovered_fields = uncovered_requested_ids or _support_required_fields_for_admission(
            request,
            target_artifact=target_artifact,
        )
        assessment = {
            "support_admission_state": "commercial_source_acquisition_required",
            "support_admission_blocker_reason": "source_backed_rows_required",
            "support_admission_request_id": support_id,
            "support_admission_uncovered_fields": uncovered_fields,
            "uncovered_requested_row_ids": uncovered_requested_ids,
            "requested_row_count": len(requested_ids),
            "accepted_requested_row_ids": [
                str(item or "").strip()
                for item in list(request.get("accepted_requested_row_ids", []) or [])
                if str(item or "").strip()
            ],
            "commercial_source_acquisition_required": True,
            "source_backed_rows_required": True,
        }
        if closed_abstract_ids:
            assessment["closed_abstract_requested_row_ids"] = closed_abstract_ids
            assessment["support_admission_parity_repair_state"] = (
                "decomposed_abstract_requested_rows_closed_by_child_rows"
            )
        return assessment
    if bool(request.get("support_provider_quality_blocker", False)):
        return {
            "support_admission_state": "provider_quality_blocked",
            "support_admission_blocker_reason": "support_provider_quality_blocker",
            "support_admission_request_id": support_id,
            "support_admission_uncovered_fields": _support_required_fields_for_admission(
                request,
                target_artifact=target_artifact,
            ),
        }
    if state == "pending_operator_review":
        return {
            "support_admission_state": "pending_operator_review",
            "support_admission_blocker_reason": "support_request_pending_operator_review",
            "support_admission_request_id": support_id,
            "support_admission_uncovered_fields": _support_required_fields_for_admission(
                request,
                target_artifact=target_artifact,
            ),
        }
    if state != "satisfied":
        return {
            "support_admission_state": "support_not_satisfied",
            "support_admission_blocker_reason": "support_request_not_satisfied",
            "support_admission_request_id": support_id,
            "support_admission_uncovered_fields": _support_required_fields_for_admission(
                request,
                target_artifact=target_artifact,
            ),
        }
    try:
        consumable_count = int(request.get("consumable_support_row_count", 0) or 0)
    except (TypeError, ValueError):
        consumable_count = 0
    try:
        build_depth_count = int(request.get("build_depth_consumable_support_row_count", 0) or 0)
    except (TypeError, ValueError):
        build_depth_count = 0
    if state == "satisfied" and consumable_count <= 0:
        return {
            "support_admission_state": "missing_support_rows",
            "support_admission_blocker_reason": "support_request_has_no_consumable_rows",
            "support_admission_request_id": support_id,
            "support_admission_uncovered_fields": _support_required_fields_for_admission(
                request,
                target_artifact=target_artifact,
            ),
        }
    if target_artifact == "interface_specifications.json" and state == "satisfied" and build_depth_count <= 0:
        return {
            "support_admission_state": "insufficient_field_coverage",
            "support_admission_blocker_reason": "support_request_has_no_build_depth_rows",
            "support_admission_request_id": support_id,
            "support_admission_uncovered_fields": _support_required_fields_for_admission(
                request,
                target_artifact=target_artifact,
            ),
        }
    requested_rows = [
        dict(item)
        for item in list(request.get("requested_rows", []) or [])
        if isinstance(item, Mapping)
    ]
    if requested_rows:
        requested_ids = [
            str(row.get("requested_row_id", "") or "").strip()
            for row in requested_rows
            if str(row.get("requested_row_id", "") or "").strip()
        ]
        accepted_requested_id_set = set(accepted_requested_ids)
        uncovered_requested_ids = list(coverage_uncovered_ids)
        if uncovered_requested_ids:
            return {
                "support_admission_state": "insufficient_requested_row_coverage",
                "support_admission_blocker_reason": "support_request_missing_requested_row_coverage",
                "support_admission_request_id": support_id,
                "support_admission_uncovered_fields": uncovered_requested_ids,
                "uncovered_requested_row_ids": uncovered_requested_ids,
                "requested_row_count": len(requested_ids),
                "accepted_requested_row_ids": sorted(accepted_requested_id_set),
            }
    required = _support_required_fields_for_admission(request, target_artifact=target_artifact)
    covered = _support_covered_fields_for_admission(request)
    uncovered = [field for field in required if field not in set(covered)]
    post_state = str(request.get("post_materialization_support_adequacy_state", "") or "").strip()
    post_uncovered = _normalized_fields(request.get("post_materialization_uncovered_fields"))
    stale_post_uncovered = [
        field for field in post_uncovered if field not in set(covered)
    ]
    if post_state and post_state not in {"adequate", "not_required"} and stale_post_uncovered:
        return {
            "support_admission_state": "insufficient_field_coverage",
            "support_admission_blocker_reason": post_state,
            "support_admission_request_id": support_id,
            "support_admission_uncovered_fields": stale_post_uncovered or uncovered or required,
        }
    if required and uncovered:
        return {
            "support_admission_state": "insufficient_field_coverage",
            "support_admission_blocker_reason": (
                "support_request_stale_adequacy_missing_required_field_coverage"
                if post_state == "adequate"
                else "support_request_missing_required_field_coverage"
            ),
            "support_admission_request_id": support_id,
            "support_admission_uncovered_fields": uncovered,
        }
    return {
        "support_admission_state": "adequate",
        "support_admission_blocker_reason": "",
        "support_admission_request_id": support_id,
        "support_admission_uncovered_fields": [],
        "accepted_requested_row_ids": sorted(set(accepted_requested_ids)),
        "commercial_source_acquisition_required": False if stale_commercial_flags_cleared else bool(
            request.get("commercial_source_acquisition_required", False)
        ),
        "source_backed_rows_required": False if stale_commercial_flags_cleared else bool(
            request.get("source_backed_rows_required", False)
        ),
        "support_admission_parity_repair_state": (
            "stale_commercial_flags_ignored_after_requested_row_coverage"
            if stale_commercial_flags_cleared
            else ""
        ),
    }


def _conveyor_root(operator_root: str | Path) -> Path:
    root = Path(operator_root)
    return root if root.name == "conveyor" else root / "conveyor"


def _directives_root(operator_root: str | Path) -> Path:
    return _conveyor_root(operator_root) / "directives"


def _children_root(operator_root: str | Path) -> Path:
    return _conveyor_root(operator_root) / "children"


def _returns_root(operator_root: str | Path) -> Path:
    return _conveyor_root(operator_root) / "returns"


def _support_requests_root(operator_root: str | Path) -> Path:
    return _conveyor_root(operator_root) / "support_requests"


def _task_manager_root(operator_root: str | Path) -> Path:
    return _conveyor_root(operator_root) / "task_manager"


def _leases_root(operator_root: str | Path) -> Path:
    return _task_manager_root(operator_root) / "leases"


def _repair_intents_root(operator_root: str | Path) -> Path:
    return _task_manager_root(operator_root) / "repair_intents"


def _snapshot_path(operator_root: str | Path) -> Path:
    return _task_manager_root(operator_root) / "snapshot_latest.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(dict(payload), indent=2, sort_keys=True) + "\n"
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass


def persist_bounded_status_snapshot(
    operator_root: str | Path,
    *,
    task_manager_snapshot: Mapping[str, Any] | None = None,
    refreshed_by: str = "task_manager_snapshot",
) -> dict[str, Any]:
    now = _utc_now()
    snapshot = dict(task_manager_snapshot or _read_json(_snapshot_path(operator_root)))
    directive_tasks = [
        {
            key: task.get(key)
            for key in (
                "directive_id",
                "directive_state",
                "task_state",
                "active_child_run_id",
                "active_child_run_ids",
                "pending_operator_review_return_ids",
                "support_admission_state",
                "support_admission_blocker_reason",
                "support_admission_request_id",
                "provider_field_lane_request_id",
                "support_admission_provider_field_lane_request_id",
                "support_admission_uncovered_fields",
                "support_pointer_role",
                "support_pointer_repaired_from_support_request_id",
                "current_linked_artifact_support_request_id",
                "support_role_lane_required_roles",
                "support_role_lane_covered_roles",
                "support_role_lane_uncovered_roles",
                "target_artifact",
                "child_work_mode",
                "r_and_d_design_brief_ready",
                "resident_support_handoff_state",
                "resident_support_handoff_blockers",
                "resident_support_handoff_stale_seconds",
                "resident_support_handoff_finalized",
                "support_handoff_repair_state",
                "support_handoff_repaired_work_order_id",
            )
            if key in task
        }
        for task in list(snapshot.get("directive_tasks", []) or [])
        if isinstance(task, Mapping)
    ]
    active_child_ids: list[str] = []
    for task in directive_tasks:
        ids = [
            str(item).strip()
            for item in list(task.get("active_child_run_ids", []) or [])
            if str(item).strip()
        ]
        active_child = str(task.get("active_child_run_id", "") or "").strip()
        if active_child and active_child not in ids:
            ids.append(active_child)
        for child_id in ids:
            if child_id not in active_child_ids:
                active_child_ids.append(child_id)
    pending_return_ids: list[str] = []
    for task in directive_tasks:
        for return_id in list(task.get("pending_operator_review_return_ids", []) or []):
            text = str(return_id or "").strip()
            if text and text not in pending_return_ids:
                pending_return_ids.append(text)
    support_blockers = [
        {
            "directive_id": task.get("directive_id"),
            "support_admission_state": task.get("support_admission_state"),
            "support_admission_blocker_reason": task.get("support_admission_blocker_reason"),
            "support_admission_request_id": task.get("support_admission_request_id"),
            "provider_field_lane_request_id": task.get("provider_field_lane_request_id", ""),
            "support_admission_provider_field_lane_request_id": task.get(
                "support_admission_provider_field_lane_request_id",
                "",
            ),
            "support_admission_uncovered_fields": task.get("support_admission_uncovered_fields", []),
            "support_pointer_role": task.get("support_pointer_role", ""),
            "support_pointer_repaired_from_support_request_id": task.get(
                "support_pointer_repaired_from_support_request_id",
                "",
            ),
            "current_linked_artifact_support_request_id": task.get(
                "current_linked_artifact_support_request_id",
                "",
            ),
            "support_role_lane_required_roles": task.get("support_role_lane_required_roles", []),
            "support_role_lane_covered_roles": task.get("support_role_lane_covered_roles", []),
            "support_role_lane_uncovered_roles": task.get("support_role_lane_uncovered_roles", []),
            "target_artifact": task.get("target_artifact"),
            "resident_support_handoff_state": task.get("resident_support_handoff_state", ""),
            "resident_support_handoff_blockers": task.get("resident_support_handoff_blockers", []),
            "resident_support_handoff_stale_seconds": task.get("resident_support_handoff_stale_seconds", 0),
            "resident_support_handoff_finalized": task.get("resident_support_handoff_finalized", False),
            "support_handoff_repair_state": task.get("support_handoff_repair_state", ""),
        }
        for task in directive_tasks
        if str(task.get("task_state", "") or "") == "blocked_for_support"
    ]
    payload = {
        "ok": True,
        "schema_name": "NovaliConveyorKernel",
        "schema_version": "novali_conveyor_kernel_v1",
        "generated_at": now,
        "bounded_status_read": True,
        "lightweight_status": True,
        "control_plane_response_mode": "degraded_fallback",
        "control_plane_degraded_reason": "bounded_status_snapshot_only",
        "bounded_status_payload_mode": "skinny_snapshot",
        "bounded_status_raw_snapshot_served": True,
        "bounded_status_raw_snapshot_source": "pre_rendered_file",
        "snapshot_only_read": True,
        "bounded_status_worker_skipped": True,
        "bounded_status_snapshot_source": "pre_rendered_file",
        "bounded_status_snapshot_persisted_at": now,
        "bounded_status_snapshot_refreshed_by": str(refreshed_by or "task_manager_snapshot"),
        "task_manager_mode": str(snapshot.get("task_manager_mode", "") or ""),
        "directive_task_summaries": directive_tasks,
        "active_child_ids": active_child_ids,
        "active_child_count": len(active_child_ids),
        "pending_return_ids": pending_return_ids,
        "pending_return_count": len(pending_return_ids),
        "support_blockers": support_blockers,
        "support_blocker_count": len(support_blockers),
        "return_counts_by_review_state": {"pending_operator_review": len(pending_return_ids)},
        "bounded_status_truth_floor_applied": True,
        "truth_floor_pending_return_count": len(pending_return_ids),
        "return_truth_stale_cache_overridden": bool(len(pending_return_ids) == 0),
        "return_truth_source": "task_manager_snapshot_current_reviewable",
        "current_return_truth_source": "task_manager_snapshot_current_reviewable",
        "task_manager_snapshot_generated_at": str(snapshot.get("generated_at", "") or ""),
        "task_manager_snapshot_freshness_state": str(snapshot.get("snapshot_freshness_state", "") or ""),
        "grants_execution_authority": False,
    }
    _write_json(_conveyor_root(operator_root) / "bounded_status_snapshot_latest.json", payload)
    return payload


def _load_items(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        payload = _read_json(path)
        if payload:
            rows.append(payload)
    return rows


def _append_ledger(operator_root: str | Path, name: str, payload: Mapping[str, Any]) -> None:
    path = _conveyor_root(operator_root) / "ledgers" / f"{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(payload), sort_keys=True) + "\n")


def _record_time(row: Mapping[str, Any]) -> datetime | None:
    return _parse_utc_time(
        row.get("updated_at")
        or row.get("generated_at")
        or row.get("created_at")
        or ""
    )


def _pending_return_is_current(
    packet: Mapping[str, Any],
    *,
    directive: Mapping[str, Any],
    returns_for_directive: Iterable[Mapping[str, Any]],
) -> bool:
    if str(packet.get("review_state", "") or "") != "pending_operator_review":
        return False
    directive_state = str(directive.get("state", "") or "")
    if directive_state in {"queued", "requeued", "running"}:
        directive_time = _record_time(directive)
        packet_time = _record_time(packet)
        if directive_time and packet_time and directive_time > packet_time:
            return False
    packet_id = str(packet.get("return_packet_id", "") or "")
    packet_time = _record_time(packet)
    superseding_states = {"requeued", "accepted", "rejected", "split", "superseded"}
    for other in returns_for_directive:
        other_id = str(other.get("return_packet_id", "") or "")
        if packet_id and other_id == packet_id:
            continue
        other_state = str(other.get("review_state", "") or "")
        if other_state not in superseding_states:
            continue
        other_time = _record_time(other)
        if packet_time and other_time and other_time > packet_time:
            return False
    return True


def _active_child(child: Mapping[str, Any]) -> bool:
    child_id = str(child.get("child_run_id", "") or "").strip()
    state = str(child.get("state", "") or "").strip()
    return bool(child_id) and not bool(child.get("spawn_suppressed", False)) and state not in TERMINAL_CHILD_STATES


def _child_container_missing(child: Mapping[str, Any], *, inspect_containers: bool, runner: Any | None) -> bool:
    if bool(child.get("container_missing", False)):
        return True
    if str(child.get("missing_container_reason", "") or "").strip():
        return True
    if not inspect_containers or runner is None:
        return False
    try:
        inspected = dict(runner.inspect_child_container(dict(child)))
    except Exception:
        return False
    state = str(inspected.get("state", "") or "").strip().lower()
    return state in {"missing", "not_found", "not-found", "unknown"} or bool(inspected.get("missing", False))


def _active_leases(operator_root: str | Path, *, now: datetime | None = None) -> list[dict[str, Any]]:
    now_dt = now or datetime.now(timezone.utc)
    active: list[dict[str, Any]] = []
    for lease in _load_items(_leases_root(operator_root)):
        if str(lease.get("lease_state", "") or "") not in {"leased", "running"}:
            continue
        expires_at = _parse_utc_time(lease.get("expires_at", ""))
        if expires_at and expires_at < now_dt:
            continue
        active.append(lease)
    return active


def _open_leases_with_state(
    operator_root: str | Path,
    *,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now_dt = now or datetime.now(timezone.utc)
    active: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    for lease in _load_items(_leases_root(operator_root)):
        if str(lease.get("lease_state", "") or "") not in {"leased", "running"}:
            continue
        expires_at = _parse_utc_time(lease.get("expires_at", ""))
        if expires_at and expires_at < now_dt:
            expired = dict(lease)
            expired["repair_reason"] = str(expired.get("repair_reason", "") or "lease_expired")
            expired["stale_lease_reason"] = "lease_expired"
            stale.append(expired)
            continue
        leased_child_id = str(lease.get("leased_child_run_id", "") or "").strip()
        if str(lease.get("lease_state", "") or "") == "leased" and not leased_child_id:
            updated_at = _parse_utc_time(lease.get("updated_at", "") or lease.get("created_at", ""))
            age_seconds = (
                (now_dt - updated_at).total_seconds()
                if updated_at is not None
                else TASK_MANAGER_EMPTY_LEASE_STALE_SECONDS
            )
            if age_seconds >= TASK_MANAGER_EMPTY_LEASE_STALE_SECONDS:
                stale_empty = dict(lease)
                stale_empty["repair_reason"] = str(
                    stale_empty.get("repair_reason", "") or "empty_lease_without_child"
                )
                stale_empty["stale_lease_reason"] = "empty_lease_without_child"
                stale.append(stale_empty)
                continue
        active.append(lease)
    return active, stale


def _lease_by_directive(operator_root: str | Path, directive_id: str) -> dict[str, Any]:
    rows = [
        lease
        for lease in _load_items(_leases_root(operator_root))
        if str(lease.get("directive_id", "") or "") == directive_id
    ]
    rows.sort(key=lambda row: str(row.get("updated_at", "") or row.get("created_at", "")))
    return rows[-1] if rows else {}


def _repair_intent(
    *,
    directive_id: str,
    repair_reason: str,
    child_run_ids: Iterable[str] = (),
) -> dict[str, Any]:
    child_ids = [str(child_id) for child_id in child_run_ids if str(child_id)]
    return {
        "schema_name": TASK_MANAGER_REPAIR_INTENT_SCHEMA_NAME,
        "schema_version": TASK_MANAGER_SCHEMA_VERSION,
        "repair_intent_id": _record_id("task-repair", directive_id, repair_reason, child_ids),
        "directive_id": directive_id,
        "repair_reason": repair_reason,
        "child_run_ids": child_ids,
        "created_at": _utc_now(),
        "grants_execution_authority": False,
    }


def build_task_manager_snapshot(
    operator_root: str | Path,
    *,
    scheduler: Mapping[str, Any] | None = None,
    inspect_containers: bool = False,
    runner: Any | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    now = _utc_now()
    now_dt = datetime.now(timezone.utc).replace(microsecond=0)
    scheduler_payload = dict(scheduler or _read_json(_conveyor_root(operator_root) / "scheduler_state_latest.json"))
    directives = _load_items(_directives_root(operator_root))
    children = _load_items(_children_root(operator_root))
    returns = _load_items(_returns_root(operator_root))
    support_requests = _load_items(_support_requests_root(operator_root))
    directive_by_id = {
        str(directive.get("directive_id", "") or ""): directive
        for directive in directives
        if str(directive.get("directive_id", "") or "")
    }
    returns_by_directive: dict[str, list[dict[str, Any]]] = {}
    for packet in returns:
        directive_id = str(packet.get("directive_id", "") or "")
        if directive_id:
            returns_by_directive.setdefault(directive_id, []).append(packet)
    active_children = [child for child in children if _active_child(child)]
    active_by_directive: dict[str, list[dict[str, Any]]] = {}
    for child in active_children:
        directive_id = str(child.get("directive_id", "") or "")
        if directive_id:
            active_by_directive.setdefault(directive_id, []).append(child)
    pending_review_by_directive: dict[str, list[str]] = {}
    stale_pending_review_by_directive: dict[str, list[str]] = {}
    for packet in returns:
        if str(packet.get("review_state", "") or "") != "pending_operator_review":
            continue
        directive_id = str(packet.get("directive_id", "") or "")
        if not directive_id:
            continue
        packet_id = str(packet.get("return_packet_id", "") or "")
        directive = directive_by_id.get(directive_id, {})
        if directive and _pending_return_is_current(
            packet,
            directive=directive,
            returns_for_directive=returns_by_directive.get(directive_id, []),
        ):
            pending_review_by_directive.setdefault(directive_id, []).append(packet_id)
        else:
            stale_pending_review_by_directive.setdefault(directive_id, []).append(packet_id)
    pending_review = set(pending_review_by_directive)
    support_by_id = {
        str(request.get("support_request_id", "") or ""): request
        for request in support_requests
        if str(request.get("support_request_id", "") or "")
    }

    def _support_target_matches(request: Mapping[str, Any], target_artifact: str) -> bool:
        request_target = str(request.get("target_artifact", "") or "").strip()
        target = str(target_artifact or "").strip()
        return bool(not request_target or not target or request_target == target)

    def _current_pending_support_state(
        directive: Mapping[str, Any],
        *,
        target_artifact_override: str = "",
    ) -> tuple[bool, list[str], dict[str, Any]]:
        directive_id = str(directive.get("directive_id", "") or "")
        metadata = dict(directive.get("metadata", {}) or {})
        target_artifact = str(
            target_artifact_override
            or metadata.get("initial_work_order_target_artifact", "")
            or ""
        ).strip()
        support_candidates: list[tuple[str, str]] = []
        if target_artifact == "risk_controls.json":
            support_candidates.extend(
                [
                    (
                        "current_risk_control_support_request_id",
                        str(metadata.get("current_risk_control_support_request_id", "") or "").strip(),
                    ),
                    (
                        "risk_control_support_request_id",
                        str(metadata.get("risk_control_support_request_id", "") or "").strip(),
                    ),
                ]
            )
        elif target_artifact == "validation_fixtures.json":
            support_candidates.extend(
                [
                    (
                        "current_validation_fixture_support_request_id",
                        str(metadata.get("current_validation_fixture_support_request_id", "") or "").strip(),
                    ),
                    (
                        "validation_fixture_support_request_id",
                        str(metadata.get("validation_fixture_support_request_id", "") or "").strip(),
                    ),
                ]
            )
        support_candidates.append(
            ("support_request_id", str(metadata.get("support_request_id", "") or "").strip())
        )
        unique_candidates: list[tuple[str, str]] = []
        seen_support_ids: set[str] = set()
        for role, support_id in support_candidates:
            if not support_id or support_id in seen_support_ids:
                continue
            seen_support_ids.add(support_id)
            unique_candidates.append((role, support_id))
        current_support_id = ""
        current_support_pointer_role = ""
        current_support: dict[str, Any] = {}
        for role, support_id in unique_candidates:
            candidate = support_by_id.get(support_id, {})
            if candidate and _support_target_matches(candidate, target_artifact):
                current_support_id = support_id
                current_support_pointer_role = role
                current_support = candidate
                break
        if not current_support_id and target_artifact:
            same_target_candidates = [
                dict(request)
                for request in support_requests
                if str(request.get("directive_id", "") or "") == directive_id
                and str(request.get("target_artifact", "") or "") == target_artifact
                and _support_request_state(request) not in {"failed", "rejected", "superseded", "cancelled"}
            ]
            if same_target_candidates:
                same_target_candidates.sort(
                    key=lambda row: str(row.get("updated_at", "") or row.get("created_at", "") or "")
                )
                current_support = same_target_candidates[-1]
                current_support_id = str(current_support.get("support_request_id", "") or "")
                current_support_pointer_role = "same_target_support_request"
        if not current_support_id and unique_candidates:
            current_support_pointer_role, current_support_id = unique_candidates[0]
            current_support = support_by_id.get(current_support_id, {}) if current_support_id else {}
        pending_ids = [
            str(request.get("support_request_id", "") or "")
            for request in support_requests
            if str(request.get("directive_id", "") or "") == directive_id
            and _support_request_state(request) == "pending_operator_review"
            and _support_target_matches(request, target_artifact)
        ]
        if current_support:
            assessment = _support_admission_assessment(
                current_support,
                target_artifact=target_artifact,
            )
            if current_support_pointer_role:
                assessment["support_pointer_role"] = current_support_pointer_role
            primary_support_id = str(metadata.get("support_request_id", "") or "").strip()
            if primary_support_id and primary_support_id != current_support_id:
                assessment["support_pointer_repaired_from_support_request_id"] = primary_support_id
            role_assessment = _support_role_lane_assessment(
                current_support,
                directive=directive,
                target_artifact=target_artifact,
            )
            assessment.update(role_assessment)
            if (
                str(role_assessment.get("support_role_lane_coverage_state", "") or "")
                == "insufficient_role_lane_coverage"
                and str(assessment.get("support_admission_state", "") or "") == "adequate"
            ):
                assessment["support_admission_state"] = "insufficient_role_lane_coverage"
                assessment["support_admission_blocker_reason"] = "support_request_missing_required_role_lanes"
                assessment["support_admission_uncovered_fields"] = list(
                    role_assessment.get("support_role_lane_uncovered_roles", []) or []
                )
            if str(assessment.get("support_admission_state", "") or "") == "adequate":
                materialization = _requested_row_materialization_assessment(
                    operator_root,
                    directive_id=directive_id,
                    target_artifact=target_artifact,
                    request=current_support,
                )
                assessment.update(materialization)
                pending_materialization = list(
                    materialization.get("support_materialization_pending_requested_row_ids", []) or []
                )
                if pending_materialization:
                    assessment["support_admission_state"] = "support_materialization_pending"
                    assessment["support_admission_blocker_reason"] = "support_materialization_pending"
                    assessment["support_admission_uncovered_fields"] = pending_materialization
                    assessment["support_materialization_pending_reason"] = str(
                        materialization.get("support_materialization_pending_reason", "")
                        or "visible_artifact_rows_missing_requested_row_closure"
                    )
            if str(assessment.get("support_admission_state", "") or "") in {
                "adequate",
                "r_and_d_design_brief_ready",
            }:
                return False, [item for item in pending_ids if item and item != current_support_id], assessment
            return True, [], assessment
        if current_support_id:
            if (
                str(metadata.get("support_recovery_state", "") or "")
                == "r_and_d_design_brief_ready"
                and str(metadata.get("r_and_d_design_brief_id", "") or "").strip()
                and target_artifact
            ):
                return False, [], {
                    "support_admission_state": "r_and_d_design_brief_ready",
                    "support_admission_blocker_reason": "",
                    "support_admission_request_id": current_support_id,
                    "support_admission_uncovered_fields": [],
                }
            assessment = _support_admission_assessment({}, target_artifact=target_artifact)
            assessment["support_admission_request_id"] = current_support_id
            if current_support_pointer_role:
                assessment["support_pointer_role"] = current_support_pointer_role
            return True, [], assessment
        assessment = {
            "support_admission_state": "not_required",
            "support_admission_blocker_reason": "",
            "support_admission_request_id": "",
            "support_admission_uncovered_fields": [],
        }
        if pending_ids:
            assessment = {
                "support_admission_state": "pending_operator_review",
                "support_admission_blocker_reason": "support_request_pending_operator_review",
                "support_admission_request_id": pending_ids[0],
                "support_admission_uncovered_fields": [],
            }
        return bool(pending_ids), [], assessment

    active_child_ids = {
        str(child.get("child_run_id", "") or "")
        for child in active_children
        if str(child.get("child_run_id", "") or "")
    }
    active_leases = []
    open_leases, stale_leases = _open_leases_with_state(operator_root)
    retained_stale_leases: list[dict[str, Any]] = []
    for stale in stale_leases:
        leased_child_id = str(stale.get("leased_child_run_id", "") or "").strip()
        if (
            str(stale.get("stale_lease_reason", "") or "") == "lease_expired"
            and leased_child_id
            and leased_child_id in active_child_ids
        ):
            renewed = dict(stale)
            renewed["lease_state"] = "running"
            renewed["repair_reason"] = ""
            renewed.pop("stale_lease_reason", None)
            renewed["lease_renewal_reason"] = "active_child_still_running"
            renewed["lease_renewed_at"] = now
            renewed["updated_at"] = now
            renewed["expires_at"] = (
                now_dt + timedelta(seconds=TASK_MANAGER_LEASE_TTL_SECONDS)
            ).isoformat()
            open_leases.append(renewed)
            if persist:
                _write_json(_leases_root(operator_root) / f"{renewed['task_id']}.json", renewed)
                _append_ledger(operator_root, "task_manager_leases", renewed)
            continue
        retained_stale_leases.append(stale)
    stale_leases = retained_stale_leases
    for lease in open_leases:
        leased_child_id = str(lease.get("leased_child_run_id", "") or "").strip()
        if leased_child_id and leased_child_id not in active_child_ids:
            stale = dict(lease)
            stale["repair_reason"] = str(stale.get("repair_reason", "") or "leased_child_not_active")
            stale["stale_lease_reason"] = "leased_child_not_active"
            stale_leases.append(stale)
            continue
        active_leases.append(lease)
    active_lease_by_directive = {
        str(lease.get("directive_id", "") or ""): lease
        for lease in active_leases
        if str(lease.get("directive_id", "") or "")
    }

    directive_tasks: list[dict[str, Any]] = []
    repair_intents_by_id: dict[str, dict[str, Any]] = {}
    for directive in directives:
        directive_id = str(directive.get("directive_id", "") or "")
        if not directive_id:
            continue
        state = str(directive.get("state", "") or "")
        directive_children = list(active_by_directive.get(directive_id, []) or [])
        child_ids = [str(child.get("child_run_id", "") or "") for child in directive_children]
        repair_reasons: list[str] = []
        if len(directive_children) > 1:
            repair_reasons.append("duplicate_active_children_for_directive")
        if any(
            _child_container_missing(child, inspect_containers=inspect_containers, runner=runner)
            for child in directive_children
        ):
            repair_reasons.append("missing_container_for_running_child")
        active_child_id = str(directive.get("active_child_run_id", "") or "").strip()
        if active_child_id and active_child_id not in set(child_ids):
            repair_reasons.append("phantom_active_child_run_id")
        metadata = dict(directive.get("metadata", {}) or {})
        feedback_target_artifact = _operator_feedback_target_artifact(directive)
        base_target_artifact = (
            feedback_target_artifact
            or str(metadata.get("initial_work_order_target_artifact", "") or "")
        )
        task_target_artifact, target_retarget = _retarget_closed_interface_for_admission(
            operator_root,
            directive=directive,
            target_artifact=base_target_artifact,
        )
        if feedback_target_artifact:
            task_target_artifact = feedback_target_artifact
            target_retarget = {
                **target_retarget,
                "support_admission_retarget_reason": "operator_feedback_target_artifact",
                "operator_feedback_target_artifact": feedback_target_artifact,
            }
        if task_target_artifact == "risk_controls.json" and not feedback_target_artifact:
            risk_support_ids = [
                str(metadata.get("current_risk_control_support_request_id", "") or "").strip(),
                str(metadata.get("risk_control_support_request_id", "") or "").strip(),
                str(metadata.get("support_request_id", "") or "").strip(),
            ]
            selected_risk_support: dict[str, Any] = {}
            for risk_support_id in risk_support_ids:
                if not risk_support_id:
                    continue
                candidate = support_by_id.get(risk_support_id, {})
                if str(candidate.get("target_artifact", "") or "") != "risk_controls.json":
                    continue
                if _support_request_state(candidate) != "satisfied":
                    continue
                materialized = (
                    str(candidate.get("risk_control_materialization_state", "") or "") == "materialized"
                    or str(candidate.get("support_materialization_state", "") or "")
                    == "visible_risk_control_rows_materialized"
                )
                if not materialized:
                    continue
                selected_risk_support = dict(candidate)
                break
            fixture_support_id = str(
                metadata.get("current_validation_fixture_support_request_id", "")
                or selected_risk_support.get("current_validation_fixture_support_request_id", "")
                or metadata.get("validation_fixture_support_request_id", "")
                or selected_risk_support.get("validation_fixture_support_request_id", "")
                or ""
            ).strip()
            fixture_support = support_by_id.get(fixture_support_id, {}) if fixture_support_id else {}
            if fixture_support and str(fixture_support.get("target_artifact", "") or "") == "validation_fixtures.json":
                task_target_artifact = "validation_fixtures.json"
                target_retarget = {
                    **target_retarget,
                    "partial_target_correct_closure": True,
                    "closed_target_artifact": "risk_controls.json",
                    "next_linked_artifact_target": "validation_fixtures.json",
                    "remaining_linked_artifact_gaps": ["validation_fixtures.json"],
                    "support_admission_retarget_reason": "visible_risk_control_closure",
                }
        (
            pending_support_current,
            ignored_stale_pending_support_ids,
            support_admission,
        ) = _current_pending_support_state(
            directive,
            target_artifact_override=task_target_artifact,
        )
        if target_retarget:
            support_admission.update(
                {
                    "partial_target_correct_closure": True,
                    "closed_target_artifact": str(target_retarget.get("closed_target_artifact", "") or ""),
                    "next_linked_artifact_target": str(
                        target_retarget.get("next_linked_artifact_target", "") or ""
                    ),
                    "remaining_linked_artifact_gaps": list(
                        target_retarget.get("remaining_linked_artifact_gaps", []) or []
                    ),
                    "support_admission_retarget_reason": str(
                        target_retarget.get("support_admission_retarget_reason", "") or ""
                    ),
                }
            )
        metadata_uncovered_requested_ids = [
            str(item or "").strip()
            for item in list(metadata.get("uncovered_requested_row_ids", []) or [])
            if str(item or "").strip()
        ]
        current_support_request_id = str(
            support_admission.get("support_admission_request_id", "") or ""
        ).strip()
        metadata_support_request_id = str(metadata.get("support_request_id", "") or "").strip()
        current_support_uncovered_ids = [
            str(item or "").strip()
            for item in list(
                support_admission.get("uncovered_requested_row_ids", [])
                or support_admission.get("support_admission_uncovered_fields", [])
                or []
            )
            if str(item or "").strip()
        ]
        current_support_accepted_ids = [
            str(item or "").strip()
            for item in list(support_admission.get("accepted_requested_row_ids", []) or [])
            if str(item or "").strip()
        ]
        if (
            current_support_uncovered_ids
            and current_support_request_id
        ):
            metadata_uncovered_requested_ids = current_support_uncovered_ids
        elif (
            metadata_uncovered_requested_ids
            and current_support_request_id
            and current_support_accepted_ids
            and set(metadata_uncovered_requested_ids).issubset(set(current_support_accepted_ids))
        ):
            metadata_uncovered_requested_ids = []
        metadata_commercial_blocker = (
            bool(metadata.get("commercial_source_acquisition_required", False))
            or bool(metadata.get("source_backed_rows_required", False))
        ) and bool(metadata_uncovered_requested_ids)
        if metadata_commercial_blocker:
            task_target_artifact = str(
                "bill_of_materials.json"
                if str(
                    metadata.get("provider_field_lane_request_id", "")
                    or metadata.get("support_request_id", "")
                    or ""
                ).startswith("provider-field-lane")
                else (
                    metadata.get("support_blocker_target_artifact", "")
                    or metadata.get("continuous_campaign_latest_target_artifact", "")
                    or metadata.get("initial_work_order_target_artifact", "")
                    or metadata.get("support_recovery_target_artifact", "")
                    or task_target_artifact
                )
            ).strip() or task_target_artifact
            pending_support_current = True
            commercial_support_request_id = str(
                support_admission.get("support_admission_request_id", "")
                or metadata.get("support_request_id", "")
                or ""
            ).strip()
            if commercial_support_request_id.startswith("provider-field-lane"):
                commercial_support_request_id = str(metadata.get("support_request_id", "") or "").strip()
            support_admission = {
                **support_admission,
                "support_admission_state": "commercial_source_acquisition_required",
                "support_admission_blocker_reason": "source_backed_rows_required",
                "support_admission_request_id": commercial_support_request_id,
                "provider_field_lane_request_id": str(
                    metadata.get("provider_field_lane_request_id", "")
                    or support_admission.get("provider_field_lane_request_id", "")
                    or ""
                ),
                "support_admission_provider_field_lane_request_id": str(
                    metadata.get("provider_field_lane_request_id", "")
                    or support_admission.get("provider_field_lane_request_id", "")
                    or ""
                ),
                "support_admission_uncovered_fields": metadata_uncovered_requested_ids,
                "uncovered_requested_row_ids": metadata_uncovered_requested_ids,
                "accepted_requested_row_ids": current_support_accepted_ids
                or list(support_admission.get("accepted_requested_row_ids", []) or []),
                "commercial_source_acquisition_required": True,
                "source_backed_rows_required": True,
                "support_admission_metadata_override": True,
            }
            if persist and task_target_artifact:
                directive_path = _directives_root(operator_root) / f"{directive_id}.json"
                latest_directive = _read_json(directive_path) or dict(directive)
                repaired_metadata = dict(latest_directive.get("metadata", {}) or metadata)
                needs_metadata_repair = any(
                    str(repaired_metadata.get(key, "") or "").strip() != task_target_artifact
                    for key in (
                        "initial_work_order_target_artifact",
                        "continuous_campaign_latest_target_artifact",
                        "support_blocker_target_artifact",
                    )
                )
                if needs_metadata_repair:
                    repaired_metadata["initial_work_order_target_artifact"] = task_target_artifact
                    repaired_metadata["continuous_campaign_latest_target_artifact"] = task_target_artifact
                    repaired_metadata["support_blocker_target_artifact"] = task_target_artifact
                    repaired_metadata["support_recovery_target_artifact"] = task_target_artifact
                    repaired_metadata["support_recovery_state"] = "commercial_source_acquisition_required"
                    repaired_metadata["support_blocker_reason"] = "source_backed_rows_required"
                    repaired_metadata["commercial_source_acquisition_required"] = True
                    repaired_metadata["source_backed_rows_required"] = True
                    repaired_metadata["support_target_parity_repaired"] = True
                    repaired_metadata["support_target_parity_repaired_at"] = now
                    latest_directive["metadata"] = repaired_metadata
                    latest_directive["updated_at"] = now
                    _write_json(directive_path, latest_directive)
                    directive = latest_directive
                    metadata = repaired_metadata
        child_runtime_blocker = bool(
            metadata.get("child_runtime_no_first_checkpoint", False)
            or str(directive.get("blocked_reason", "") or "").strip() == "child_runtime_no_first_checkpoint"
        )
        if child_runtime_blocker:
            pending_support_current = True
            task_target_artifact = str(
                metadata.get("initial_work_order_target_artifact", "")
                or metadata.get("support_blocker_target_artifact", "")
                or task_target_artifact
            ).strip() or task_target_artifact
            support_admission = {
                **support_admission,
                "support_admission_state": "child_runtime_no_first_checkpoint",
                "support_admission_blocker_reason": "child_runtime_no_first_checkpoint",
                "support_admission_request_id": str(
                    support_admission.get("support_admission_request_id", "")
                    or metadata.get("support_request_id", "")
                    or ""
                ),
                "child_runtime_no_first_checkpoint": True,
                "child_lifecycle_classification": str(
                    metadata.get("child_lifecycle_classification", "")
                    or "blocked_pass_completed_not_review_ready"
                ),
                "support_admission_metadata_override": True,
            }
        resident_handoff_blocker = bool(
            metadata.get("resident_support_handoff_finalized", False)
            or str(directive.get("blocked_reason", "") or "").strip()
            == "resident_support_handoff_missing"
        )
        if resident_handoff_blocker:
            pending_support_current = True
            task_target_artifact = str(
                metadata.get("initial_work_order_target_artifact", "")
                or metadata.get("support_blocker_target_artifact", "")
                or task_target_artifact
            ).strip() or task_target_artifact
            support_admission = {
                **support_admission,
                "support_admission_state": "support_handoff_missing",
                "support_admission_blocker_reason": "resident_support_handoff_missing",
                "support_admission_request_id": str(
                    support_admission.get("support_admission_request_id", "")
                    or metadata.get("support_request_id", "")
                    or ""
                ),
                "resident_support_handoff_state": str(
                    metadata.get("resident_support_handoff_state", "")
                    or "finalized_missing_handoff"
                ),
                "resident_support_handoff_blockers": list(
                    metadata.get("resident_support_handoff_blockers", []) or []
                ),
                "resident_support_handoff_stale_seconds": float(
                    metadata.get("resident_support_handoff_stale_seconds", 0.0) or 0.0
                ),
                "resident_support_handoff_finalized": True,
                "child_lifecycle_classification": str(
                    metadata.get("child_lifecycle_classification", "")
                    or "blocked_pass_completed_not_review_ready"
                ),
                "support_admission_metadata_override": True,
            }
        resident_no_delta_blocker = bool(
            metadata.get("resident_support_backed_no_delta_finalized", False)
            or str(directive.get("blocked_reason", "") or "").strip()
            == "resident_support_backed_no_delta_finalized"
        )
        resident_no_delta_followup_target = str(
            metadata.get("resident_no_delta_followup_target_artifact", "") or ""
        ).strip()
        resident_no_delta_followup_ready = bool(
            metadata.get("resident_no_delta_followup_ready", False)
            and resident_no_delta_followup_target
        )
        resident_no_delta_followup_active = bool(
            resident_no_delta_followup_ready
            and (
                resident_no_delta_blocker
                or metadata.get("resident_no_delta_followup_work_order_repaired", False)
            )
        )
        if (
            resident_no_delta_followup_active
            and not metadata_commercial_blocker
            and not feedback_target_artifact
        ):
            pending_support_current = False
            task_target_artifact = resident_no_delta_followup_target
            support_admission = {
                **support_admission,
                "support_admission_state": "not_required",
                "support_admission_blocker_reason": "",
                "support_admission_request_id": "",
                "support_admission_uncovered_fields": [],
                "child_lifecycle_classification": str(
                    metadata.get("child_lifecycle_classification", "")
                    or "blocked_pass_completed_not_review_ready"
                ),
                "resident_support_backed_no_delta_finalized": True,
                "resident_no_delta_followup_ready": True,
                "resident_no_delta_followup_target_artifact": resident_no_delta_followup_target,
                "resident_no_delta_followup_work_order_repaired": bool(
                    metadata.get("resident_no_delta_followup_work_order_repaired", False)
                ),
                "support_admission_metadata_override": True,
            }
        elif resident_no_delta_blocker and not metadata_commercial_blocker and not feedback_target_artifact:
            pending_support_current = True
            task_target_artifact = str(
                metadata.get("initial_work_order_target_artifact", "")
                or metadata.get("support_blocker_target_artifact", "")
                or task_target_artifact
            ).strip() or task_target_artifact
            support_admission = {
                **support_admission,
                "support_admission_state": "resident_support_backed_no_delta_finalized",
                "support_admission_blocker_reason": "resident_support_backed_no_delta_finalized",
                "support_admission_request_id": str(
                    support_admission.get("support_admission_request_id", "")
                    or metadata.get("support_request_id", "")
                    or ""
                ),
                "child_lifecycle_classification": str(
                    metadata.get("child_lifecycle_classification", "")
                    or "blocked_pass_completed_not_review_ready"
                ),
                "resident_support_backed_no_delta_finalized": True,
                "support_admission_metadata_override": True,
            }
        implementation_readiness_content_depth_target = str(
            metadata.get("implementation_readiness_content_depth_target_artifact", "") or ""
        ).strip()
        implementation_readiness_content_depth_active = bool(
            metadata.get("implementation_readiness_content_depth_repaired", False)
            and implementation_readiness_content_depth_target
        )
        if implementation_readiness_content_depth_active and not metadata_commercial_blocker:
            pending_support_current = False
            task_target_artifact = implementation_readiness_content_depth_target
            support_admission = {
                **support_admission,
                "support_admission_state": "not_required",
                "support_admission_blocker_reason": "",
                "support_admission_request_id": "",
                "support_admission_uncovered_fields": [],
                "implementation_readiness_content_depth_repaired": True,
                "implementation_readiness_content_depth_target_artifact": implementation_readiness_content_depth_target,
                "support_admission_metadata_override": True,
            }
        technical_documentation_depth_plateau = bool(
            metadata.get("technical_documentation_depth_plateau_finalized", False)
            or str(directive.get("blocked_reason", "") or "").strip()
            == "technical_documentation_depth_support_required"
        )
        if technical_documentation_depth_plateau and not metadata_commercial_blocker:
            technical_documentation_support_id = str(
                metadata.get("technical_documentation_depth_support_request_id", "")
                or metadata.get("support_request_id", "")
                or support_admission.get("support_admission_request_id", "")
                or ""
            ).strip()
            technical_documentation_uncovered_ids = [
                str(item or "").strip()
                for item in list(metadata.get("uncovered_requested_row_ids", []) or [])
                if str(item or "").strip()
            ]
            pending_support_current = True
            task_target_artifact = "technical_documentation.md"
            support_admission = {
                **support_admission,
                "support_admission_state": "technical_documentation_depth_support_required",
                "support_admission_blocker_reason": "technical_documentation_depth_support_required",
                "support_admission_request_id": technical_documentation_support_id,
                "support_admission_uncovered_fields": technical_documentation_uncovered_ids,
                "uncovered_requested_row_ids": technical_documentation_uncovered_ids,
                "support_pointer_role": "technical_documentation_depth_support_request_id"
                if technical_documentation_support_id
                == str(metadata.get("technical_documentation_depth_support_request_id", "") or "").strip()
                else "support_request_id",
                "technical_documentation_depth_plateau_finalized": True,
                "technical_documentation_depth_plateau_failed_gates": list(
                    metadata.get("technical_documentation_depth_plateau_failed_gates", []) or []
                ),
                "child_lifecycle_classification": str(
                    metadata.get("child_lifecycle_classification", "")
                    or "blocked_pass_completed_not_review_ready"
                ),
                "support_admission_metadata_override": True,
            }
            if persist:
                directive_path = _directives_root(operator_root) / f"{directive_id}.json"
                latest_directive = _read_json(directive_path) or dict(directive)
                repaired_metadata = dict(latest_directive.get("metadata", {}) or metadata)
                needs_metadata_repair = (
                    str(repaired_metadata.get("support_request_id", "") or "").strip()
                    != technical_documentation_support_id
                    or str(repaired_metadata.get("support_blocker_target_artifact", "") or "").strip()
                    != "technical_documentation.md"
                    or str(repaired_metadata.get("initial_work_order_target_artifact", "") or "").strip()
                    != "technical_documentation.md"
                    or str(repaired_metadata.get("continuous_campaign_latest_target_artifact", "") or "").strip()
                    != "technical_documentation.md"
                )
                if needs_metadata_repair:
                    if technical_documentation_support_id:
                        repaired_metadata["support_request_id"] = technical_documentation_support_id
                        repaired_metadata["technical_documentation_depth_support_request_id"] = (
                            technical_documentation_support_id
                        )
                    repaired_metadata["support_blocker_target_artifact"] = "technical_documentation.md"
                    repaired_metadata["initial_work_order_target_artifact"] = "technical_documentation.md"
                    repaired_metadata["continuous_campaign_latest_target_artifact"] = "technical_documentation.md"
                    repaired_metadata["support_recovery_target_artifact"] = "technical_documentation.md"
                    repaired_metadata["support_blocker_reason"] = "technical_documentation_depth_support_required"
                    repaired_metadata["support_admission_state"] = "technical_documentation_depth_support_required"
                    repaired_metadata["support_admission_blocker_reason"] = (
                        "technical_documentation_depth_support_required"
                    )
                    repaired_metadata["support_pointer_role"] = "technical_documentation_depth_support_request_id"
                    repaired_metadata["technical_documentation_depth_support_required"] = True
                    repaired_metadata["technical_documentation_depth_support_pointer_repaired"] = True
                    repaired_metadata["technical_documentation_depth_support_pointer_repaired_at"] = now
                    latest_directive["state"] = "blocked_for_support"
                    latest_directive["blocked_reason"] = "technical_documentation_depth_support_required"
                    latest_directive["metadata"] = repaired_metadata
                    latest_directive["updated_at"] = now
                    _write_json(directive_path, latest_directive)
                    directive = latest_directive
                    metadata = repaired_metadata

        if (
            feedback_target_artifact
            and task_target_artifact != feedback_target_artifact
            and not resident_no_delta_followup_active
            and not implementation_readiness_content_depth_active
            and not technical_documentation_depth_plateau
        ):
            task_target_artifact = feedback_target_artifact
            (
                pending_support_current,
                ignored_stale_pending_support_ids,
                support_admission,
            ) = _current_pending_support_state(
                directive,
                target_artifact_override=task_target_artifact,
            )
            support_admission = {
                **support_admission,
                "support_admission_retarget_reason": "operator_feedback_target_artifact",
                "operator_feedback_target_artifact": feedback_target_artifact,
                "support_admission_metadata_override": True,
            }

        selected_support_id = str(support_admission.get("support_admission_request_id", "") or "").strip()
        repaired_from_support_id = str(
            support_admission.get("support_pointer_repaired_from_support_request_id", "") or ""
        ).strip()
        if (
            persist
            and selected_support_id
            and repaired_from_support_id
            and task_target_artifact in {"risk_controls.json", "validation_fixtures.json"}
            and str(support_admission.get("support_admission_state", "") or "") != "wrong_target"
        ):
            directive_path = _directives_root(operator_root) / f"{directive_id}.json"
            latest_directive = _read_json(directive_path) or dict(directive)
            repaired_metadata = dict(latest_directive.get("metadata", {}) or metadata)
            repaired_metadata["support_request_id"] = selected_support_id
            repaired_metadata["support_blocker_target_artifact"] = task_target_artifact
            repaired_metadata["initial_work_order_target_artifact"] = task_target_artifact
            repaired_metadata["continuous_campaign_latest_target_artifact"] = task_target_artifact
            repaired_metadata["support_pointer_repaired_from_support_request_id"] = repaired_from_support_id
            if task_target_artifact == "risk_controls.json":
                repaired_metadata["current_risk_control_support_request_id"] = selected_support_id
                repaired_metadata["risk_control_support_request_id"] = selected_support_id
                repaired_metadata["support_pointer_role"] = "current_risk_control_support_request_id"
            else:
                repaired_metadata["current_validation_fixture_support_request_id"] = selected_support_id
                repaired_metadata["validation_fixture_support_request_id"] = selected_support_id
                repaired_metadata["support_pointer_role"] = "current_validation_fixture_support_request_id"
            latest_directive["metadata"] = repaired_metadata
            latest_directive["updated_at"] = now
            _write_json(directive_path, latest_directive)
            directive = latest_directive
            metadata = repaired_metadata

        support_admission_state = str(support_admission.get("support_admission_state", "") or "")
        if state in TERMINAL_DIRECTIVE_STATES:
            task_state = "terminal"
        elif repair_reasons:
            task_state = "stale_or_repairable"
        elif directive_id in pending_review:
            task_state = "blocked_for_review"
        elif pending_support_current:
            task_state = "blocked_for_support"
        elif directive_children:
            task_state = "running"
        elif directive_id in active_lease_by_directive:
            task_state = "leased"
        elif support_admission_state == "r_and_d_design_brief_ready":
            task_state = "eligible"
        elif state in {"queued", "requeued"}:
            task_state = "eligible"
        else:
            task_state = "terminal"

        for reason in repair_reasons:
            intent = _repair_intent(
                directive_id=directive_id,
                repair_reason=reason,
                child_run_ids=child_ids or ([active_child_id] if active_child_id else []),
            )
            repair_intents_by_id[intent["repair_intent_id"]] = intent

        lease = active_lease_by_directive.get(directive_id, {})
        directive_tasks.append(
            {
                "directive_id": directive_id,
                "directive_state": state,
                "task_state": task_state,
                "active_child_run_id": active_child_id,
                "active_child_run_ids": child_ids,
                "pending_operator_review": directive_id in pending_review,
                "pending_operator_review_return_ids": list(
                    pending_review_by_directive.get(directive_id, []) or []
                ),
                "ignored_stale_pending_return_ids": list(
                    stale_pending_review_by_directive.get(directive_id, []) or []
                ),
                "stale_pending_return_count": len(
                    list(stale_pending_review_by_directive.get(directive_id, []) or [])
                ),
                "pending_support": pending_support_current,
                "ignored_stale_pending_support_ids": ignored_stale_pending_support_ids,
                "stale_pending_support_count": len(ignored_stale_pending_support_ids),
                "support_admission_state": str(
                    support_admission_state
                ),
                "support_admission_blocker_reason": str(
                    support_admission.get("support_admission_blocker_reason", "") or ""
                ),
                "support_admission_uncovered_fields": list(
                    support_admission.get("support_admission_uncovered_fields", []) or []
                ),
                "support_admission_request_id": str(
                    support_admission.get("support_admission_request_id", "") or ""
                ),
                "provider_field_lane_request_id": str(
                    support_admission.get("provider_field_lane_request_id", "") or ""
                ),
                "support_admission_provider_field_lane_request_id": str(
                    support_admission.get("support_admission_provider_field_lane_request_id", "") or ""
                ),
                "support_admission_parity_repair_state": str(
                    support_admission.get("support_admission_parity_repair_state", "") or ""
                ),
                "support_pointer_role": str(
                    support_admission.get("support_pointer_role", "") or ""
                ),
                "support_pointer_repaired_from_support_request_id": str(
                    support_admission.get("support_pointer_repaired_from_support_request_id", "") or ""
                ),
                "current_linked_artifact_support_request_id": str(
                    support_admission.get("support_admission_request_id", "") or ""
                )
                if task_target_artifact in {"risk_controls.json", "validation_fixtures.json"}
                else "",
                "support_materialization_pending_reason": str(
                    support_admission.get("support_materialization_pending_reason", "") or ""
                ),
                "support_materialization_pending_requested_row_ids": list(
                    support_admission.get("support_materialization_pending_requested_row_ids", []) or []
                ),
                "support_materialization_closure_state": str(
                    support_admission.get("support_materialization_closure_state", "") or ""
                ),
                "resident_support_handoff_state": str(
                    support_admission.get("resident_support_handoff_state", "")
                    or metadata.get("resident_support_handoff_state", "")
                    or ""
                ),
                "resident_support_handoff_blockers": list(
                    support_admission.get("resident_support_handoff_blockers", [])
                    or metadata.get("resident_support_handoff_blockers", [])
                    or []
                ),
                "resident_support_handoff_stale_seconds": float(
                    support_admission.get("resident_support_handoff_stale_seconds", 0.0)
                    or metadata.get("resident_support_handoff_stale_seconds", 0.0)
                    or 0.0
                ),
                "resident_support_handoff_finalized": bool(
                    support_admission.get("resident_support_handoff_finalized", False)
                    or metadata.get("resident_support_handoff_finalized", False)
                ),
                "support_handoff_repair_state": str(
                    support_admission.get("support_handoff_repair_state", "")
                    or metadata.get("support_handoff_repair_state", "")
                    or ""
                ),
                "support_handoff_repaired_work_order_id": str(
                    support_admission.get("support_handoff_repaired_work_order_id", "")
                    or metadata.get("support_handoff_repaired_work_order_id", "")
                    or ""
                ),
                "child_work_mode": str(
                    metadata.get("child_work_mode", "")
                    or (
                        "design_only_reduction"
                        if str(support_admission.get("support_admission_state", "") or "")
                        == "r_and_d_design_brief_ready"
                        else ""
                    )
                ),
                "r_and_d_design_brief_ready": bool(
                    metadata.get("r_and_d_design_brief_ready", False)
                    or str(support_admission.get("support_admission_state", "") or "")
                    == "r_and_d_design_brief_ready"
                ),
                "support_role_lane_coverage_state": str(
                    support_admission.get("support_role_lane_coverage_state", "") or ""
                ),
                "support_role_lane_uncovered_roles": list(
                    support_admission.get("support_role_lane_uncovered_roles", []) or []
                ),
                "support_role_lane_required_roles": list(
                    support_admission.get("support_role_lane_required_roles", []) or []
                ),
                "support_role_lane_covered_roles": list(
                    support_admission.get("support_role_lane_covered_roles", []) or []
                ),
                "lease_state": str(lease.get("lease_state", "") or ""),
                "task_id": str(lease.get("task_id", "") or _record_id("task", directive_id)),
                "repair_reasons": repair_reasons,
                "target_artifact": task_target_artifact,
                "partial_target_correct_closure": bool(target_retarget),
                "closed_target_artifact": str(target_retarget.get("closed_target_artifact", "") or ""),
                "next_linked_artifact_target": str(
                    target_retarget.get("next_linked_artifact_target", "") or ""
                ),
                "remaining_linked_artifact_gaps": list(
                    target_retarget.get("remaining_linked_artifact_gaps", []) or []
                ),
            }
        )

    admissible = [row for row in directive_tasks if row["task_state"] == "eligible"]
    repair_intents = list(repair_intents_by_id.values())
    duplicate_count = sum(
        1 for intent in repair_intents if intent["repair_reason"] == "duplicate_active_children_for_directive"
    )
    snapshot = {
        "schema_name": TASK_MANAGER_SNAPSHOT_SCHEMA_NAME,
        "schema_version": TASK_MANAGER_SCHEMA_VERSION,
        "generated_at": now,
        "task_manager_mode": str(scheduler_payload.get("task_manager_mode", "shadow") or "shadow"),
        "task_manager_cutover_enabled": bool(scheduler_payload.get("task_manager_cutover_enabled", False)),
        "directive_tasks": directive_tasks,
        "admissible_directives": admissible,
        "admissible_directive_count": len(admissible),
        "active_lease_count": len(active_leases),
        "active_leases": active_leases,
        "stale_lease_count": len(stale_leases),
        "stale_leases": stale_leases,
        "repair_intents": repair_intents,
        "repair_intent_count": len(repair_intents),
        "duplicate_suppression_count": duplicate_count,
        "mismatch_count": len(repair_intents),
        "stale_pending_return_count": sum(
            len(list(ids or [])) for ids in stale_pending_review_by_directive.values()
        ),
        "ignored_stale_pending_return_ids": [
            packet_id
            for ids in stale_pending_review_by_directive.values()
            for packet_id in list(ids or [])
            if packet_id
        ],
        "stale_pending_support_count": sum(
            len(list(row.get("ignored_stale_pending_support_ids", []) or []))
            for row in directive_tasks
        ),
        "ignored_stale_pending_support_ids": [
            support_id
            for row in directive_tasks
            for support_id in list(row.get("ignored_stale_pending_support_ids", []) or [])
            if support_id
        ],
        "snapshot_freshness_state": "fresh",
        "snapshot_refreshed_by": "build_task_manager_snapshot",
        "grants_execution_authority": False,
    }
    if persist:
        _write_json(_snapshot_path(operator_root), snapshot)
        persist_bounded_status_snapshot(
            operator_root,
            task_manager_snapshot=snapshot,
            refreshed_by="build_task_manager_snapshot",
        )
        _append_ledger(operator_root, "task_manager_snapshots", snapshot)
        for intent in repair_intents:
            _write_json(_repair_intents_root(operator_root) / f"{intent['repair_intent_id']}.json", intent)
    return snapshot


def apply_task_manager_repairs(
    operator_root: str | Path,
    *,
    scheduler: Mapping[str, Any] | None = None,
    inspect_containers: bool = False,
    runner: Any | None = None,
) -> dict[str, Any]:
    before = build_task_manager_snapshot(
        operator_root,
        scheduler=scheduler,
        inspect_containers=inspect_containers,
        runner=runner,
        persist=False,
    )
    now = _utc_now()
    applied: list[dict[str, Any]] = []
    released_lease_count = 0

    for lease in list(before.get("stale_leases", []) or []):
        if not isinstance(lease, Mapping):
            continue
        task_id = str(lease.get("task_id", "") or "")
        directive_id = str(lease.get("directive_id", "") or "")
        if not task_id:
            continue
        reason = str(
            lease.get("stale_lease_reason", "")
            or lease.get("repair_reason", "")
            or "stale_lease_released"
        )
        updated = dict(lease)
        updated["lease_state"] = "released"
        updated["repair_reason"] = reason
        updated["repair_applied_at"] = now
        updated["updated_at"] = now
        _write_json(_leases_root(operator_root) / f"{task_id}.json", updated)
        _append_ledger(operator_root, "task_manager_leases", updated)
        released_lease_count += 1
        repair = {
            "schema_name": TASK_MANAGER_REPAIR_APPLIED_SCHEMA_NAME,
            "schema_version": TASK_MANAGER_SCHEMA_VERSION,
            "repair_applied_id": _record_id("task-repair-applied", task_id, directive_id, reason),
            "task_id": task_id,
            "directive_id": directive_id,
            "leased_child_run_id": str(lease.get("leased_child_run_id", "") or ""),
            "repair_reason": reason,
            "created_at": now,
            "grants_execution_authority": False,
        }
        _append_ledger(operator_root, "task_manager_repairs_applied", repair)
        applied.append(repair)

    directive_by_id = {
        str(directive.get("directive_id", "") or ""): directive
        for directive in _load_items(_directives_root(operator_root))
        if str(directive.get("directive_id", "") or "")
    }
    active_children = [child for child in _load_items(_children_root(operator_root)) if _active_child(child)]
    active_child_ids_by_directive: dict[str, set[str]] = {}
    for child in active_children:
        directive_id = str(child.get("directive_id", "") or "")
        child_id = str(child.get("child_run_id", "") or "")
        if directive_id and child_id:
            active_child_ids_by_directive.setdefault(directive_id, set()).add(child_id)

    cleared_active_child_count = 0
    for task in list(before.get("directive_tasks", []) or []):
        if not isinstance(task, Mapping):
            continue
        directive_id = str(task.get("directive_id", "") or "")
        if not directive_id:
            continue
        repair_reasons = {str(reason) for reason in list(task.get("repair_reasons", []) or [])}
        if "phantom_active_child_run_id" not in repair_reasons:
            continue
        directive = dict(directive_by_id.get(directive_id, {}) or {})
        if not directive:
            continue
        active_child_id = str(directive.get("active_child_run_id", "") or "")
        if not active_child_id or active_child_id in active_child_ids_by_directive.get(directive_id, set()):
            continue
        directive["active_child_run_id"] = ""
        if str(directive.get("state", "") or "") == "running":
            directive["state"] = "requeued"
        directive["task_manager_repair_reason"] = "phantom_active_child_run_id"
        directive["updated_at"] = now
        _write_json(_directives_root(operator_root) / f"{directive_id}.json", directive)
        repair = {
            "schema_name": TASK_MANAGER_REPAIR_APPLIED_SCHEMA_NAME,
            "schema_version": TASK_MANAGER_SCHEMA_VERSION,
            "repair_applied_id": _record_id("task-repair-applied", directive_id, active_child_id, "phantom_active_child_run_id"),
            "task_id": str(task.get("task_id", "") or _record_id("task", directive_id)),
            "directive_id": directive_id,
            "leased_child_run_id": active_child_id,
            "repair_reason": "phantom_active_child_run_id",
            "created_at": now,
            "grants_execution_authority": False,
        }
        _append_ledger(operator_root, "task_manager_repairs_applied", repair)
        applied.append(repair)
        cleared_active_child_count += 1

    after = build_task_manager_snapshot(
        operator_root,
        scheduler=scheduler,
        inspect_containers=inspect_containers,
        runner=runner,
        persist=True,
    )
    return {
        "ok": True,
        "schema_name": "TaskManagerRepairBatch",
        "schema_version": TASK_MANAGER_SCHEMA_VERSION,
        "generated_at": now,
        "task_manager_repair_applied_count": len(applied),
        "task_manager_released_stale_lease_count": released_lease_count,
        "task_manager_cleared_stale_active_child_count": cleared_active_child_count,
        "applied_repairs": applied,
        "snapshot": after,
        "grants_execution_authority": False,
    }


def task_manager_capacity(scheduler: Mapping[str, Any]) -> int:
    try:
        env_cap = max(
            1,
            int(os.environ.get("NOVALI_TASK_MANAGER_MAX_ACTIVE_CHILDREN", str(TASK_MANAGER_DEFAULT_MAX_ACTIVE_CHILDREN)) or TASK_MANAGER_DEFAULT_MAX_ACTIVE_CHILDREN),
        )
    except ValueError:
        env_cap = TASK_MANAGER_DEFAULT_MAX_ACTIVE_CHILDREN
    max_concurrency = max(1, int(scheduler.get("max_concurrency", env_cap) or env_cap))
    return max(1, min(env_cap, max_concurrency))


def acquire_task_manager_leases(
    operator_root: str | Path,
    *,
    scheduler: Mapping[str, Any],
    limit: int | None = None,
    inspect_containers: bool = False,
    runner: Any | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    snapshot = build_task_manager_snapshot(
        operator_root,
        scheduler=scheduler,
        inspect_containers=inspect_containers,
        runner=runner,
        persist=True,
    )
    capacity = task_manager_capacity(scheduler)
    active_count = len([row for row in snapshot["directive_tasks"] if row["task_state"] in {"leased", "running"}])
    open_slots = max(0, capacity - active_count)
    if limit is not None:
        open_slots = min(open_slots, max(0, int(limit)))
    admissions = list(snapshot.get("admissible_directives", []) or [])[:open_slots]
    now = _utc_now()
    now_dt = datetime.now(timezone.utc)
    leases: list[dict[str, Any]] = []
    for task in admissions:
        directive_id = str(task.get("directive_id", "") or "")
        existing = _lease_by_directive(operator_root, directive_id)
        epoch = int(existing.get("lease_epoch", 0) or 0) + 1
        lease = {
            "schema_name": TASK_MANAGER_LEASE_SCHEMA_NAME,
            "schema_version": TASK_MANAGER_SCHEMA_VERSION,
            "task_id": str(task.get("task_id", "") or _record_id("task", directive_id)),
            "directive_id": directive_id,
            "leased_child_run_id": "",
            "lease_state": "leased",
            "lease_epoch": epoch,
            "admission_reason": "eligible_directive_task",
            "repair_reason": "",
            "created_at": now,
            "updated_at": now,
            "expires_at": (now_dt + timedelta(seconds=TASK_MANAGER_LEASE_TTL_SECONDS)).replace(microsecond=0).isoformat(),
            "grants_execution_authority": False,
        }
        _write_json(_leases_root(operator_root) / f"{lease['task_id']}.json", lease)
        _append_ledger(operator_root, "task_manager_leases", lease)
        leases.append(lease)
    refreshed = build_task_manager_snapshot(
        operator_root,
        scheduler=scheduler,
        inspect_containers=inspect_containers,
        runner=runner,
        persist=True,
    )
    return refreshed, leases


def load_task_manager_snapshot(operator_root: str | Path) -> dict[str, Any]:
    return _read_json(_snapshot_path(operator_root))


def _admissible_tasks_from_snapshot(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    explicit = [
        dict(task)
        for task in list(snapshot.get("admissible_directives", []) or [])
        if isinstance(task, Mapping)
    ]
    if explicit:
        return explicit
    return [
        dict(task)
        for task in list(snapshot.get("directive_tasks", []) or [])
        if isinstance(task, Mapping)
        and str(task.get("task_state", "") or "") == "eligible"
    ]


def _release_stale_empty_leases_for_cached_admission(
    operator_root: str | Path,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    _, stale_leases = _open_leases_with_state(operator_root, now=now)
    released: list[dict[str, Any]] = []
    timestamp = _utc_now()
    for lease in stale_leases:
        stale_reason = str(lease.get("stale_lease_reason", "") or "")
        leased_child_id = str(lease.get("leased_child_run_id", "") or "").strip()
        if stale_reason not in {"empty_lease_without_child", "lease_expired"}:
            continue
        if stale_reason == "lease_expired" and leased_child_id:
            continue
        task_id = str(lease.get("task_id", "") or "").strip()
        directive_id = str(lease.get("directive_id", "") or "").strip()
        if not task_id or not directive_id:
            continue
        updated = dict(lease)
        updated["lease_state"] = "released"
        updated["repair_reason"] = "empty_lease_without_child" if not leased_child_id else stale_reason
        updated["released_by"] = "bounded_admission_cached_snapshot"
        updated["updated_at"] = timestamp
        _write_json(_leases_root(operator_root) / f"{task_id}.json", updated)
        _append_ledger(operator_root, "task_manager_leases", updated)
        released.append(updated)
    return released


def _snapshot_with_released_empty_leases(
    snapshot: Mapping[str, Any],
    *,
    released_leases: Sequence[Mapping[str, Any]],
    now: str,
) -> dict[str, Any]:
    released_directive_ids = {
        str(lease.get("directive_id", "") or "").strip()
        for lease in released_leases
        if str(lease.get("directive_id", "") or "").strip()
    }
    if not released_directive_ids:
        return dict(snapshot)
    refreshed = dict(snapshot)
    directive_tasks: list[dict[str, Any]] = []
    for task in list(snapshot.get("directive_tasks", []) or []):
        if not isinstance(task, Mapping):
            continue
        row = dict(task)
        directive_id = str(row.get("directive_id", "") or "").strip()
        if (
            directive_id in released_directive_ids
            and str(row.get("task_state", "") or "") == "leased"
            and not str(row.get("active_child_run_id", "") or "").strip()
        ):
            row["task_state"] = "eligible"
            row["lease_state"] = "released"
            row["lease_repair_reason"] = "empty_lease_without_child"
            row["lease_state_source"] = "bounded_admission_cached_snapshot_repair"
            row["updated_at"] = now
        directive_tasks.append(row)

    active_leases = [
        dict(lease)
        for lease in list(snapshot.get("active_leases", []) or [])
        if isinstance(lease, Mapping)
        and str(lease.get("directive_id", "") or "").strip() not in released_directive_ids
    ]
    admissible_directives = [
        dict(task)
        for task in directive_tasks
        if str(task.get("task_state", "") or "") == "eligible"
    ]
    refreshed["directive_tasks"] = directive_tasks
    refreshed["active_leases"] = active_leases
    refreshed["active_lease_count"] = len(active_leases)
    refreshed["admissible_directives"] = admissible_directives
    refreshed["admissible_directive_count"] = len(admissible_directives)
    refreshed["bounded_admission_released_stale_empty_lease_count"] = len(released_directive_ids)
    refreshed["bounded_admission_released_stale_empty_lease_directive_ids"] = sorted(released_directive_ids)
    return refreshed


def acquire_task_manager_leases_from_cached_snapshot(
    operator_root: str | Path,
    *,
    scheduler: Mapping[str, Any],
    limit: int | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    snapshot = load_task_manager_snapshot(operator_root)
    if not snapshot:
        return {
            "schema_name": TASK_MANAGER_SNAPSHOT_SCHEMA_NAME,
            "schema_version": TASK_MANAGER_SCHEMA_VERSION,
            "generated_at": _utc_now(),
            "snapshot_freshness_state": "missing_cached_snapshot",
            "snapshot_refreshed_by": "bounded_admission_cached_snapshot_missing",
            "directive_tasks": [],
            "admissible_directives": [],
            "admissible_directive_count": 0,
            "active_lease_count": 0,
            "active_leases": [],
            "grants_execution_authority": False,
        }, []

    now_dt = datetime.now(timezone.utc)
    now = _utc_now()
    released_stale_empty_leases = _release_stale_empty_leases_for_cached_admission(
        operator_root,
        now=now_dt,
    )
    working_snapshot = _snapshot_with_released_empty_leases(
        snapshot,
        released_leases=released_stale_empty_leases,
        now=now,
    )
    capacity = task_manager_capacity(scheduler)
    active_count = len(
        [
            row
            for row in list(working_snapshot.get("directive_tasks", []) or [])
            if isinstance(row, Mapping)
            and str(row.get("task_state", "") or "") in {"leased", "running"}
        ]
    )
    open_slots = max(0, capacity - active_count)
    if limit is not None:
        open_slots = min(open_slots, max(0, int(limit)))
    admissions = _admissible_tasks_from_snapshot(working_snapshot)[:open_slots]
    leases: list[dict[str, Any]] = []
    for task in admissions:
        directive_id = str(task.get("directive_id", "") or "")
        if not directive_id:
            continue
        existing = _lease_by_directive(operator_root, directive_id)
        if str(existing.get("lease_state", "") or "") in {"leased", "running"}:
            continue
        epoch = int(existing.get("lease_epoch", 0) or 0) + 1
        lease = {
            "schema_name": TASK_MANAGER_LEASE_SCHEMA_NAME,
            "schema_version": TASK_MANAGER_SCHEMA_VERSION,
            "task_id": str(task.get("task_id", "") or _record_id("task", directive_id)),
            "directive_id": directive_id,
            "leased_child_run_id": "",
            "lease_state": "leased",
            "lease_epoch": epoch,
            "admission_reason": "eligible_directive_task_cached_snapshot",
            "repair_reason": "",
            "created_at": now,
            "updated_at": now,
            "expires_at": (now_dt + timedelta(seconds=TASK_MANAGER_LEASE_TTL_SECONDS)).replace(microsecond=0).isoformat(),
            "grants_execution_authority": False,
        }
        _write_json(_leases_root(operator_root) / f"{lease['task_id']}.json", lease)
        _append_ledger(operator_root, "task_manager_leases", lease)
        leases.append(lease)

    leased_directive_ids = {str(lease.get("directive_id", "") or "") for lease in leases}
    refreshed = dict(working_snapshot)
    refreshed["generated_at"] = now
    refreshed["snapshot_refreshed_by"] = "bounded_admission_cached_snapshot_lease"
    refreshed["snapshot_freshness_state"] = "cached_bounded_admission"
    refreshed["bounded_admission_cached_snapshot_used"] = True
    refreshed["grants_execution_authority"] = False
    directive_tasks: list[dict[str, Any]] = []
    for task in list(working_snapshot.get("directive_tasks", []) or []):
        if not isinstance(task, Mapping):
            continue
        row = dict(task)
        if str(row.get("directive_id", "") or "") in leased_directive_ids:
            row["task_state"] = "leased"
            row["lease_state"] = "leased"
            row["lease_state_source"] = "bounded_admission_cached_snapshot_lease"
            row["updated_at"] = now
        directive_tasks.append(row)
    refreshed["directive_tasks"] = directive_tasks
    cached_active_leases = [
        dict(lease)
        for lease in list(working_snapshot.get("active_leases", []) or [])
        if isinstance(lease, Mapping)
    ]
    refreshed["active_leases"] = cached_active_leases + leases
    refreshed["active_lease_count"] = len(refreshed["active_leases"])
    remaining_admissible = [
        task
        for task in _admissible_tasks_from_snapshot(working_snapshot)
        if str(task.get("directive_id", "") or "") not in leased_directive_ids
    ]
    refreshed["admissible_directives"] = remaining_admissible
    refreshed["admissible_directive_count"] = len(remaining_admissible)
    _write_json(_snapshot_path(operator_root), refreshed)
    persist_bounded_status_snapshot(
        operator_root,
        task_manager_snapshot=refreshed,
        refreshed_by="bounded_admission_cached_snapshot_lease",
    )
    return refreshed, leases


def update_task_manager_lease_after_spawn(
    operator_root: str | Path,
    *,
    directive_id: str,
    child_run_id: str,
    spawn_failed: bool,
) -> dict[str, Any]:
    lease = _lease_by_directive(operator_root, directive_id)
    if not lease:
        return {}
    now = _utc_now()
    now_dt = datetime.now(timezone.utc).replace(microsecond=0)
    updated = dict(lease)
    updated["leased_child_run_id"] = str(child_run_id or "")
    updated["lease_state"] = "released_failed" if spawn_failed else "running"
    updated["updated_at"] = now
    if spawn_failed:
        updated["repair_reason"] = "spawn_failed"
    else:
        updated["repair_reason"] = ""
        updated["lease_renewal_reason"] = "spawn_fulfilled"
        updated["lease_renewed_at"] = now
        updated["expires_at"] = (
            now_dt + timedelta(seconds=TASK_MANAGER_LEASE_TTL_SECONDS)
        ).isoformat()
    _write_json(_leases_root(operator_root) / f"{updated['task_id']}.json", updated)
    _append_ledger(operator_root, "task_manager_leases", updated)
    return updated


def release_task_manager_lease(
    operator_root: str | Path,
    *,
    directive_id: str,
    reason: str,
    child_run_id: str = "",
) -> dict[str, Any]:
    lease = _lease_by_directive(operator_root, directive_id)
    if not lease:
        return {}
    expected_child_id = str(child_run_id or "").strip()
    leased_child_id = str(lease.get("leased_child_run_id", "") or "").strip()
    if (
        not expected_child_id
        and leased_child_id
        and str(lease.get("lease_state", "") or "") == "running"
        and str(reason or "") == "spawn_suppressed_existing_active_child"
    ):
        suppressed = dict(lease)
        suppressed["lease_release_suppressed"] = True
        suppressed["lease_release_suppressed_reason"] = "running_child_lease_requires_explicit_child_id"
        suppressed["requested_release_reason"] = str(reason or "")
        suppressed["updated_at"] = _utc_now()
        _append_ledger(operator_root, "task_manager_leases", suppressed)
        return suppressed
    if expected_child_id and leased_child_id and leased_child_id != expected_child_id:
        suppressed = dict(lease)
        suppressed["lease_release_suppressed"] = True
        suppressed["lease_release_suppressed_reason"] = "leased_child_run_id_mismatch"
        suppressed["requested_release_child_run_id"] = expected_child_id
        suppressed["requested_release_reason"] = str(reason or "")
        suppressed["updated_at"] = _utc_now()
        _append_ledger(operator_root, "task_manager_leases", suppressed)
        return suppressed
    updated = dict(lease)
    updated["lease_state"] = "released"
    updated["repair_reason"] = str(reason or "")
    if expected_child_id:
        updated["released_child_run_id"] = expected_child_id
    updated["updated_at"] = _utc_now()
    _write_json(_leases_root(operator_root) / f"{updated['task_id']}.json", updated)
    _append_ledger(operator_root, "task_manager_leases", updated)
    snapshot = build_task_manager_snapshot(operator_root, persist=True)
    snapshot["snapshot_refreshed_by"] = "release_task_manager_lease"
    snapshot["snapshot_freshness_state"] = "fresh"
    _write_json(_snapshot_path(operator_root), snapshot)
    return updated

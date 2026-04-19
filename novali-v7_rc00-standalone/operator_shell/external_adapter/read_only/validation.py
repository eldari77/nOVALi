from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from operator_shell.controller_isolation import build_default_lane_registry
from operator_shell.observability.redaction import REDACTED, redact_value

from .schemas import (
    ObservationIntegrityResult,
    ObservationValidationResult,
    ReadOnlyObservation,
    ReadOnlyWorldSnapshot,
)

STALE_SNAPSHOT_MAX_AGE_HOURS = 72
STALE_SNAPSHOT_REVIEW_THRESHOLD_HOURS = 168
FORBIDDEN_DOMAIN_TERMS = (
    "space engineers",
    "spaceengineers",
    "grid block",
    "voxel asteroid",
    "assembler block",
)
REQUIRED_SNAPSHOT_FIELDS = (
    "schema_version",
    "source_kind",
    "source_name",
    "source_ref",
    "snapshot_id",
    "snapshot_created_at",
    "observed_at",
    "read_only",
    "environment_kind",
    "lane_id",
    "observed_entities",
    "observed_relationships",
    "observed_metrics",
    "integrity_markers",
    "mutation_allowed",
    "notes_redacted",
    "package_version",
    "branch",
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).astimezone(timezone.utc)


def _safe_iso(raw_value: str | None) -> datetime | None:
    candidate = str(raw_value or "").strip()
    if not candidate:
        return None
    try:
        normalized = candidate.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(timezone.utc)
    except ValueError:
        return None


def hash_file(path: str | Path) -> str:
    payload = Path(path).read_bytes()
    return hashlib.sha256(payload).hexdigest()


def _path_hint(source_ref: str | Path | None) -> str:
    if not source_ref:
        return "<unknown>"
    return Path(str(source_ref)).name or "<unknown>"


def snapshot_from_payload(
    payload: Mapping[str, Any],
    *,
    source_ref: str | Path | None = None,
) -> ReadOnlyWorldSnapshot:
    raw = dict(payload or {})
    return ReadOnlyWorldSnapshot(
        schema_version=str(raw.get("schema_version", "")).strip(),
        source_kind=str(raw.get("source_kind", "")).strip(),
        source_name=str(raw.get("source_name", "")).strip(),
        source_ref=str(raw.get("source_ref", "")).strip() or _path_hint(source_ref),
        snapshot_id=str(raw.get("snapshot_id", "")).strip(),
        snapshot_created_at=str(raw.get("snapshot_created_at", "")).strip(),
        observed_at=str(raw.get("observed_at", "")).strip(),
        read_only=bool(raw.get("read_only", False)),
        environment_kind=str(raw.get("environment_kind", "")).strip(),
        lane_id=str(raw.get("lane_id", "")).strip(),
        observed_entities=list(raw.get("observed_entities", []) or []),
        observed_relationships=list(raw.get("observed_relationships", []) or []),
        observed_metrics=list(raw.get("observed_metrics", []) or []),
        integrity_markers=dict(raw.get("integrity_markers", {}) or {}),
        mutation_allowed=bool(raw.get("mutation_allowed", False)),
        notes_redacted=str(raw.get("notes_redacted", "")).strip(),
        package_version=str(raw.get("package_version", "")).strip(),
        branch=str(raw.get("branch", "")).strip(),
    )


def build_observation_summary(snapshot: ReadOnlyWorldSnapshot) -> ReadOnlyObservation:
    entity_count = len(list(snapshot.observed_entities or []))
    relationship_count = len(list(snapshot.observed_relationships or []))
    metric_count = len(list(snapshot.observed_metrics or []))
    summary = (
        f"{snapshot.source_name or 'fixture'} observed {entity_count} entity(ies), "
        f"{relationship_count} relationship(s), and {metric_count} metric(s) in "
        f"{snapshot.environment_kind or 'generic_non_se_sandbox'} for {snapshot.lane_id or 'unknown_lane'}."
    )
    return ReadOnlyObservation(
        snapshot_id=snapshot.snapshot_id or "<missing_snapshot_id>",
        lane_id=snapshot.lane_id or "<missing_lane>",
        entity_count=entity_count,
        relationship_count=relationship_count,
        metric_count=metric_count,
        summary_redacted=str(redact_value(summary, key="observation_summary") or ""),
        observed_at=snapshot.observed_at or "",
    )


def _collect_strings(value: Any) -> list[tuple[str | None, str]]:
    collected: list[tuple[str | None, str]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_name = str(key)
            collected.extend(_collect_strings_with_key(item, key_name))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            collected.extend(_collect_strings(item))
    elif isinstance(value, str):
        collected.append((None, value))
    return collected


def _collect_strings_with_key(value: Any, key: str) -> list[tuple[str | None, str]]:
    collected: list[tuple[str | None, str]] = []
    if isinstance(value, Mapping):
        for inner_key, item in value.items():
            collected.extend(_collect_strings_with_key(item, str(inner_key)))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            if isinstance(item, Mapping):
                collected.extend(_collect_strings(item))
            elif isinstance(item, str):
                collected.append((key, item))
    elif isinstance(value, str):
        collected.append((key, value))
    return collected


def _contains_secret_like_content(snapshot: ReadOnlyWorldSnapshot) -> bool:
    payload = snapshot.to_dict()
    for key, value in _collect_strings(payload):
        redacted = redact_value(value, key=key)
        if redacted == REDACTED and value != REDACTED:
            return True
    return False


def _contains_forbidden_domain_term(snapshot: ReadOnlyWorldSnapshot) -> bool:
    text = json.dumps(snapshot.to_dict(), sort_keys=True, default=str).lower()
    return any(term in text for term in FORBIDDEN_DOMAIN_TERMS)


def _known_lane_ids(package_root: str | Path | None) -> set[str]:
    if package_root is None:
        return {"lane_director", "lane_sovereign_good", "lane_sovereign_dark"}
    registry = build_default_lane_registry(package_root)
    return {lane.lane_id for lane in registry.lanes}


def validate_snapshot_schema(
    snapshot: ReadOnlyWorldSnapshot,
    *,
    package_root: str | Path | None = None,
    reference_time: datetime | None = None,
) -> ObservationValidationResult:
    findings: list[str] = []
    missing_fields: list[str] = []
    duplicate_entity_ids: list[str] = []
    unknown_relationship_references: list[str] = []
    review_reasons: list[str] = []
    validation_status = "clean"
    reference = reference_time or _now_utc()

    payload = snapshot.to_dict()
    for field_name in REQUIRED_SNAPSHOT_FIELDS:
        value = payload.get(field_name)
        if (
            value is None
            or (isinstance(value, str) and value == "")
            or (
                field_name in {"observed_entities", "observed_relationships", "observed_metrics"}
                and not isinstance(value, list)
            )
        ):
            if field_name in {"observed_entities", "observed_relationships", "observed_metrics"} and isinstance(value, list):
                continue
            missing_fields.append(field_name)
    if missing_fields:
        review_reasons.append("read_only_schema_missing_field")
        findings.append("Missing required field(s): " + ", ".join(sorted(missing_fields)))
        validation_status = "failed"

    if snapshot.schema_version != "rc87.v1":
        review_reasons.append("read_only_schema_invalid")
        findings.append("schema_version must equal rc87.v1")
        validation_status = "failed"
    if snapshot.read_only is not True:
        review_reasons.append("read_only_schema_invalid")
        findings.append("read_only must remain true")
        validation_status = "failed"
    if snapshot.mutation_allowed is not False:
        review_reasons.append("read_only_schema_invalid")
        findings.append("mutation_allowed must remain false")
        validation_status = "failed"
    if snapshot.source_kind != "static_fixture":
        review_reasons.append("read_only_schema_invalid")
        findings.append("source_kind must remain static_fixture")
        validation_status = "failed"
    if snapshot.environment_kind != "generic_non_se_sandbox":
        review_reasons.append("read_only_schema_invalid")
        findings.append("environment_kind must remain generic_non_se_sandbox")
        validation_status = "failed"
    known_lanes = _known_lane_ids(package_root)
    if not snapshot.lane_id:
        review_reasons.append("read_only_schema_missing_field")
        findings.append("lane_id is required")
        validation_status = "failed"
    elif snapshot.lane_id not in known_lanes:
        review_reasons.append("read_only_schema_invalid")
        findings.append("lane_id must reference a known identity lane")
        validation_status = "failed"
    if not isinstance(snapshot.observed_entities, list):
        review_reasons.append("read_only_schema_invalid")
        findings.append("observed_entities must be a list")
        validation_status = "failed"
    if not isinstance(snapshot.observed_relationships, list):
        review_reasons.append("read_only_schema_invalid")
        findings.append("observed_relationships must be a list")
        validation_status = "failed"
    if not isinstance(snapshot.observed_metrics, list):
        review_reasons.append("read_only_schema_invalid")
        findings.append("observed_metrics must be a list")
        validation_status = "failed"

    entity_ids: set[str] = set()
    for entity in list(snapshot.observed_entities or []):
        entity_id = str(dict(entity).get("entity_id", "")).strip()
        if entity_id and entity_id in entity_ids:
            duplicate_entity_ids.append(entity_id)
        elif entity_id:
            entity_ids.add(entity_id)
    if duplicate_entity_ids:
        review_reasons.append("read_only_schema_invalid")
        findings.append("duplicate entity_id detected")
        validation_status = "failed"

    for relationship in list(snapshot.observed_relationships or []):
        relationship_payload = dict(relationship)
        source_entity_id = str(relationship_payload.get("source_entity_id", "")).strip()
        target_entity_id = str(relationship_payload.get("target_entity_id", "")).strip()
        relationship_id = str(relationship_payload.get("relationship_id", "")).strip() or "<missing_relationship_id>"
        if source_entity_id and source_entity_id not in entity_ids:
            unknown_relationship_references.append(f"{relationship_id}:source:{source_entity_id}")
        if target_entity_id and target_entity_id not in entity_ids:
            unknown_relationship_references.append(f"{relationship_id}:target:{target_entity_id}")
    if unknown_relationship_references:
        review_reasons.append("read_only_schema_invalid")
        findings.append("relationship references unknown entity_id")
        validation_status = "failed"

    observed_at = _safe_iso(snapshot.observed_at)
    if observed_at is None:
        review_reasons.append("read_only_schema_missing_field")
        findings.append("observed_at must be present and ISO-8601 parseable")
        validation_status = "failed"
        stale_snapshot = False
    else:
        stale_snapshot = observed_at < (reference - timedelta(hours=STALE_SNAPSHOT_MAX_AGE_HOURS))
        if stale_snapshot and validation_status == "clean":
            validation_status = "warning"
            findings.append("observed_at is older than the proof freshness threshold")
            if observed_at < (reference - timedelta(hours=STALE_SNAPSHOT_REVIEW_THRESHOLD_HOURS)):
                review_reasons.append("read_only_stale_snapshot")
                validation_status = "review_required"

    if _contains_forbidden_domain_term(snapshot):
        review_reasons.append("read_only_forbidden_domain_term")
        findings.append("forbidden domain term detected in snapshot content")
        validation_status = "failed"
    if _contains_secret_like_content(snapshot):
        review_reasons.append("read_only_secret_detected")
        findings.append("credential-like or secret-like content detected in snapshot content")
        validation_status = "failed"

    deduped_reasons = sorted(set(review_reasons), key=review_reasons.index)
    review_required = bool(deduped_reasons)
    return ObservationValidationResult(
        validation_status=validation_status,
        review_required=review_required,
        review_reasons=deduped_reasons,
        findings=findings,
        missing_fields=missing_fields,
        duplicate_entity_ids=duplicate_entity_ids,
        unknown_relationship_references=unknown_relationship_references,
        stale_snapshot=stale_snapshot,
    )


def validate_observation_integrity(
    snapshot: ReadOnlyWorldSnapshot,
    *,
    package_root: str | Path | None = None,
    validation_result: ObservationValidationResult | None = None,
    reference_time: datetime | None = None,
) -> ObservationIntegrityResult:
    validation = validation_result or validate_snapshot_schema(
        snapshot,
        package_root=package_root,
        reference_time=reference_time,
    )
    findings: list[str] = []
    review_reasons: list[str] = list(validation.review_reasons)
    integrity_status = "clean"
    reference = reference_time or _now_utc()
    lane_attribution_status = "valid"
    stale_snapshot = validation.stale_snapshot

    observed_at = _safe_iso(snapshot.observed_at)
    if observed_at is not None and observed_at < (reference - timedelta(hours=STALE_SNAPSHOT_MAX_AGE_HOURS)):
        stale_snapshot = True
        findings.append("snapshot age exceeded the proof freshness threshold")
        if observed_at < (reference - timedelta(hours=STALE_SNAPSHOT_REVIEW_THRESHOLD_HOURS)):
            review_reasons.append("read_only_stale_snapshot")
            integrity_status = "review_required"
        elif integrity_status == "clean":
            integrity_status = "warning"

    conflict_detected = False
    metric_values: dict[str, set[str]] = {}
    for metric in list(snapshot.observed_metrics or []):
        metric_payload = dict(metric)
        metric_name = str(metric_payload.get("metric_name", "")).strip()
        metric_value = str(metric_payload.get("metric_value", "")).strip()
        if not metric_name:
            continue
        metric_values.setdefault(metric_name, set()).add(metric_value)
        if len(metric_values[metric_name]) > 1:
            conflict_detected = True
    if conflict_detected:
        review_reasons.append("read_only_conflicting_observation")
        findings.append("conflicting observation detected across metrics with the same metric_name")
        integrity_status = "review_required"

    forbidden_domain_term = _contains_forbidden_domain_term(snapshot)
    if forbidden_domain_term:
        review_reasons.append("read_only_forbidden_domain_term")
        findings.append("forbidden domain term detected")
        integrity_status = "failed"

    secret_detected = _contains_secret_like_content(snapshot)
    if secret_detected:
        review_reasons.append("read_only_secret_detected")
        findings.append("secret-like content detected")
        integrity_status = "failed"

    mutation_request_detected = bool(snapshot.mutation_allowed) or any(
        str(key).strip().lower() in {"requested_operation", "mutation_request", "requested_action"}
        for key in dict(snapshot.integrity_markers or {}).keys()
    )
    if mutation_request_detected:
        review_reasons.append("read_only_mutation_requested")
        findings.append("snapshot carries mutation semantics that a read-only adapter must refuse")
        integrity_status = "failed"

    if snapshot.lane_id != "lane_director":
        lane_attribution_status = "wrong_lane"
        review_reasons.append("read_only_wrong_lane_attribution")
        findings.append("read-only sandbox observations must remain attributed to lane_director in rc87 proof paths")
        integrity_status = "review_required" if integrity_status == "clean" else integrity_status
    if not snapshot.lane_id:
        lane_attribution_status = "review_required"

    if validation.validation_status in {"failed", "review_required"} and integrity_status == "clean":
        integrity_status = "review_required"
    elif validation.validation_status == "warning" and integrity_status == "clean":
        integrity_status = "warning"

    deduped_reasons = sorted(set(review_reasons), key=review_reasons.index)
    review_required = bool(deduped_reasons)
    return ObservationIntegrityResult(
        integrity_status=integrity_status,
        review_required=review_required,
        review_reasons=deduped_reasons,
        findings=findings,
        lane_attribution_status=lane_attribution_status,
        stale_snapshot=stale_snapshot,
        conflicting_observations=conflict_detected,
        forbidden_domain_term=forbidden_domain_term,
        secret_detected=secret_detected,
        mutation_request_detected=mutation_request_detected,
    )

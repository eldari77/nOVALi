from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, Mapping

from operator_shell.observability.redaction import redact_value

from .schemas import ControllerLaneIdentity, CrossLaneMessageEnvelope, IdentityBleedFinding


def _finding_id(*parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"isolation-finding-{digest}"


def _finding(
    *,
    finding_type: str,
    severity: str,
    source_lane_id: str,
    target_lane_id: str | None,
    affected_namespace: str | None,
    evidence_summary: str,
) -> IdentityBleedFinding:
    return IdentityBleedFinding(
        finding_id=_finding_id(
            finding_type,
            source_lane_id,
            str(target_lane_id or ""),
            str(affected_namespace or ""),
            evidence_summary,
        ),
        finding_type=finding_type,
        severity=severity,
        source_lane_id=source_lane_id,
        target_lane_id=target_lane_id,
        affected_namespace=affected_namespace,
        evidence_summary_redacted=str(redact_value(evidence_summary, key="evidence_summary") or ""),
        review_ticket_id=None,
        replay_packet_id=None,
    )


def detect_namespace_collisions(lanes: Iterable[ControllerLaneIdentity]) -> list[IdentityBleedFinding]:
    findings: list[IdentityBleedFinding] = []
    by_field = {
        "doctrine_namespace": "doctrine_namespace_collision",
        "memory_namespace": "memory_namespace_collision",
        "summary_namespace": "summary_namespace_collision",
        "intervention_namespace": "intervention_namespace_collision",
        "replay_namespace": "replay_namespace_collision",
        "review_namespace": "review_namespace_collision",
    }
    lane_list = list(lanes)
    for field_name, finding_type in by_field.items():
        seen: dict[str, str] = {}
        for lane in lane_list:
            candidate = str(getattr(lane, field_name, "")).strip()
            if not candidate:
                continue
            prior_lane = seen.get(candidate)
            if prior_lane and prior_lane != lane.lane_id:
                findings.append(
                    _finding(
                        finding_type=finding_type,
                        severity="high",
                        source_lane_id=prior_lane,
                        target_lane_id=lane.lane_id,
                        affected_namespace=candidate,
                        evidence_summary=f"{field_name} reused across {prior_lane} and {lane.lane_id}.",
                    )
                )
            else:
                seen[candidate] = lane.lane_id
    return findings


def detect_hidden_shared_scratchpad(path_by_lane: Mapping[str, str]) -> list[IdentityBleedFinding]:
    findings: list[IdentityBleedFinding] = []
    seen: dict[str, str] = {}
    for lane_id, candidate in path_by_lane.items():
        normalized = str(candidate or "").strip()
        if not normalized:
            continue
        prior_lane = seen.get(normalized)
        if prior_lane and prior_lane != lane_id:
            findings.append(
                _finding(
                    finding_type="hidden_shared_scratchpad_detected",
                    severity="critical",
                    source_lane_id=prior_lane,
                    target_lane_id=lane_id,
                    affected_namespace=normalized,
                    evidence_summary=f"Hidden shared scratchpad path reused across {prior_lane} and {lane_id}.",
                )
            )
        else:
            seen[normalized] = lane_id
    return findings


def detect_cross_lane_message_violation(
    envelope: CrossLaneMessageEnvelope,
) -> list[IdentityBleedFinding]:
    findings: list[IdentityBleedFinding] = []
    if envelope.mediated_by_lane_id != "lane_director":
        findings.append(
            _finding(
                finding_type="unauthorized_cross_lane_message",
                severity="high",
                source_lane_id=envelope.source_lane_id,
                target_lane_id=envelope.target_lane_id,
                affected_namespace="cross_lane_message",
                evidence_summary="Cross-lane communication bypassed Director mediation.",
            )
        )
    if envelope.message_type in {"doctrine_transfer", "memory_dump"}:
        findings.append(
            _finding(
                finding_type=f"{envelope.message_type}_detected",
                severity="critical",
                source_lane_id=envelope.source_lane_id,
                target_lane_id=envelope.target_lane_id,
                affected_namespace="cross_lane_message",
                evidence_summary=f"Forbidden cross-lane message type {envelope.message_type} was proposed.",
            )
        )
    if envelope.approval_status in {"blocked", "rejected", "review_required"} and not findings:
        findings.append(
            _finding(
                finding_type="forbidden_message_type",
                severity="high",
                source_lane_id=envelope.source_lane_id,
                target_lane_id=envelope.target_lane_id,
                affected_namespace="cross_lane_message",
                evidence_summary=f"Cross-lane message {envelope.message_type} was not approved.",
            )
        )
    return findings


def detect_wrong_lane_marker(
    *,
    owner_lane_id: str,
    reserved_markers: Mapping[str, str],
    artifact_text: str,
    finding_type: str,
    severity: str = "high",
) -> list[IdentityBleedFinding]:
    findings: list[IdentityBleedFinding] = []
    normalized_text = str(artifact_text or "")
    for lane_id, marker in reserved_markers.items():
        if lane_id == owner_lane_id:
            continue
        if marker and marker in normalized_text:
            findings.append(
                _finding(
                    finding_type=finding_type,
                    severity=severity,
                    source_lane_id=owner_lane_id,
                    target_lane_id=lane_id,
                    affected_namespace="lane_artifact",
                    evidence_summary=f"{owner_lane_id} artifact contains reserved marker for {lane_id}.",
                )
            )
    return findings


def detect_secret_leakage(
    *,
    lane_id: str,
    artifact_text: str,
    fake_seeds: Iterable[str],
) -> list[IdentityBleedFinding]:
    for seed in fake_seeds:
        if seed and seed in str(artifact_text or ""):
            return [
                _finding(
                    finding_type="fake_secret_leakage",
                    severity="critical",
                    source_lane_id=lane_id,
                    target_lane_id=None,
                    affected_namespace="lane_artifact",
                    evidence_summary=f"{lane_id} artifact contains fake secret material.",
                )
            ]
    return []


def detect_authority_claim(lane: ControllerLaneIdentity) -> list[IdentityBleedFinding]:
    findings: list[IdentityBleedFinding] = []
    if bool(lane.adoption_authority):
        findings.append(
            _finding(
                finding_type="unauthorized_authority_claim",
                severity="critical",
                source_lane_id=lane.lane_id,
                target_lane_id=None,
                affected_namespace="lane_identity",
                evidence_summary=f"{lane.lane_id} claimed adoption authority.",
            )
        )
    if bool(lane.coordination_authority):
        findings.append(
            _finding(
                finding_type="unauthorized_authority_claim",
                severity="critical",
                source_lane_id=lane.lane_id,
                target_lane_id=None,
                affected_namespace="lane_identity",
                evidence_summary=f"{lane.lane_id} claimed coordination authority.",
            )
        )
    if bool(lane.active):
        findings.append(
            _finding(
                finding_type="active_lane_without_approval",
                severity="critical",
                source_lane_id=lane.lane_id,
                target_lane_id=None,
                affected_namespace="lane_identity",
                evidence_summary=f"{lane.lane_id} was marked active without an explicit proof-only override.",
            )
        )
    return findings


def detect_telemetry_identity(
    records: Iterable[Mapping[str, str]],
) -> list[IdentityBleedFinding]:
    findings: list[IdentityBleedFinding] = []
    for index, record in enumerate(records):
        if not str(record.get("novali.controller.role", "")).strip() or not str(
            record.get("novali.controller.lane", "")
        ).strip():
            findings.append(
                _finding(
                    finding_type="lane_telemetry_missing_identity",
                    severity="high",
                    source_lane_id="lane_director",
                    target_lane_id=None,
                    affected_namespace="telemetry",
                    evidence_summary=f"Lane-specific telemetry record {index + 1} omitted controller lane identity.",
                )
            )
    return findings


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""

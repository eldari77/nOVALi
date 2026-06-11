from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

RC88_SCHEMA_VERSION = "rc88.v1"
RC88_PACKAGE_VERSION = "rc88"
NOVALI_BRANCH = "novali-v6"


def _to_serializable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _to_serializable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _to_serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_serializable(item) for item in value]
    return value


@dataclass(slots=True)
class OperatorAlertCandidate:
    alert_id: str
    alert_type: str
    source: str
    source_milestone: str
    severity: str
    status: str
    title: str
    summary_redacted: str
    operator_action_required: str
    created_at: str
    updated_at: str
    evidence_bundle_id: str
    replay_packet_ids: list[str] = field(default_factory=list)
    review_ticket_ids: list[str] = field(default_factory=list)
    rollback_analysis_ids: list[str] = field(default_factory=list)
    mutation_refusal_ids: list[str] = field(default_factory=list)
    source_immutability_ref: str | None = None
    lane_id: str | None = None
    controller_isolation_finding_ids: list[str] = field(default_factory=list)
    telemetry_trace_hint: str | None = None
    lm_dimension_hints: list[str] = field(default_factory=list)
    acknowledgement_required: bool = True
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    closure_reason: str | None = None
    superseded_by_alert_id: str | None = None
    schema_version: str = RC88_SCHEMA_VERSION
    package_version: str = RC88_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class OperatorAlertEvidenceBundle:
    evidence_bundle_id: str
    alert_id: str
    source: str
    source_case: str
    replay_packet_refs: list[str] = field(default_factory=list)
    review_ticket_refs: list[str] = field(default_factory=list)
    rollback_analysis_refs: list[str] = field(default_factory=list)
    mutation_refusal_refs: list[str] = field(default_factory=list)
    source_immutability_refs: list[str] = field(default_factory=list)
    lane_attribution_refs: list[str] = field(default_factory=list)
    telemetry_refs: list[str] = field(default_factory=list)
    status_endpoint_snapshot_ref: str | None = None
    package_validation_refs: list[str] = field(default_factory=list)
    evidence_integrity_status: str = "clean"
    evidence_integrity_findings: list[str] = field(default_factory=list)
    redaction_status: str = "clean"
    created_at: str = ""
    schema_version: str = RC88_SCHEMA_VERSION
    package_version: str = RC88_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class OperatorAlertLifecycleEvent:
    event_id: str
    alert_id: str
    action: str
    previous_status: str
    new_status: str
    actor: str
    note_redacted: str | None
    replacement_alert_id: str | None
    created_at: str
    schema_version: str = RC88_SCHEMA_VERSION
    package_version: str = RC88_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class OperatorAlertAcknowledgement:
    alert_id: str
    actor: str
    noted_at: str
    note_redacted: str | None = None
    schema_version: str = RC88_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class OperatorAlertReviewRecord:
    alert_id: str
    actor: str
    reviewed_at: str
    note_redacted: str | None = None
    schema_version: str = RC88_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class OperatorAlertSummary:
    alert_count: int
    raised_count: int
    acknowledged_count: int
    reviewed_count: int
    blocked_count: int
    critical_count: int
    high_count: int
    warning_count: int
    latest_alert_id: str | None
    latest_alert_type: str | None
    latest_evidence_bundle_id: str | None
    latest_operator_action_required: str | None
    read_only_alert_count: int
    telemetry_alert_candidate_count: int
    telemetry_shutdown_alert_count: int
    identity_bleed_alert_count: int
    latest_telemetry_shutdown_alert_id: str | None
    status: str
    schema_version: str = RC88_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ReadOnlyAdapterAdmissionCriteria:
    criteria_id: str
    criteria_label: str
    checks: dict[str, bool]
    notes: list[str]
    schema_version: str = RC88_SCHEMA_VERSION
    package_version: str = RC88_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ReadOnlyAdapterAdmissionAssessment:
    assessment_id: str
    target_name: str
    target_kind: str
    assessment_scope: str
    admission_status: str
    summary_redacted: str
    rationale_redacted: str
    satisfied_checks: list[str] = field(default_factory=list)
    blocked_checks: list[str] = field(default_factory=list)
    planning_only: bool = False
    operator_action_required: str | None = None
    created_at: str = ""
    schema_version: str = RC88_SCHEMA_VERSION
    package_version: str = RC88_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class SpaceEngineersTransitionDecisionMemo:
    memo_id: str
    recommendation: str
    implementation_blocked: bool
    planning_only: bool
    completed_gates: list[str] = field(default_factory=list)
    blocked_work: list[str] = field(default_factory=list)
    decision_options: list[str] = field(default_factory=list)
    created_at: str = ""
    schema_version: str = RC88_SCHEMA_VERSION
    package_version: str = RC88_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)

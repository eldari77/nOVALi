from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

RC87_SCHEMA_VERSION = "rc87.v1"
RC87_PACKAGE_VERSION = "rc87"
NOVALI_BRANCH = "novali-v6"
DEFAULT_READ_ONLY_ADAPTER_NAME = "static_fixture_read_only"
DEFAULT_READ_ONLY_ADAPTER_KIND = "read_only_fixture"
OBSERVATION_REPLAY_KIND = "read_only_observation"


def _to_serializable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _to_serializable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _to_serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_serializable(item) for item in value]
    return value


@dataclass(slots=True)
class ObservationSourceMetadata:
    source_kind: str
    source_name: str
    source_ref_hint: str
    loaded_at: str
    fixture_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ReadOnlyWorldSnapshot:
    source_kind: str = ""
    source_name: str = ""
    source_ref: str = ""
    snapshot_id: str = ""
    snapshot_created_at: str = ""
    observed_at: str = ""
    read_only: bool = True
    environment_kind: str = ""
    lane_id: str = ""
    observed_entities: list[dict[str, Any]] = field(default_factory=list)
    observed_relationships: list[dict[str, Any]] = field(default_factory=list)
    observed_metrics: list[dict[str, Any]] = field(default_factory=list)
    integrity_markers: dict[str, Any] = field(default_factory=dict)
    mutation_allowed: bool = False
    notes_redacted: str = ""
    schema_version: str = RC87_SCHEMA_VERSION
    package_version: str = RC87_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ReadOnlyObservation:
    snapshot_id: str
    lane_id: str
    entity_count: int
    relationship_count: int
    metric_count: int
    summary_redacted: str
    observed_at: str
    schema_version: str = RC87_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ObservationValidationResult:
    validation_status: str
    review_required: bool
    review_reasons: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    duplicate_entity_ids: list[str] = field(default_factory=list)
    unknown_relationship_references: list[str] = field(default_factory=list)
    stale_snapshot: bool = False
    schema_version: str = RC87_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ObservationIntegrityResult:
    integrity_status: str
    review_required: bool
    review_reasons: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    lane_attribution_status: str = "unknown"
    stale_snapshot: bool = False
    conflicting_observations: bool = False
    forbidden_domain_term: bool = False
    secret_detected: bool = False
    mutation_request_detected: bool = False
    schema_version: str = RC87_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ObservationReplayPacket:
    replay_packet_id: str
    source_ref_hint: str
    snapshot_id: str
    lane_id: str
    source_controller: str
    governing_directive_ref: str
    observation_summary_redacted: str
    entity_count: int
    relationship_count: int
    metric_count: int
    validation_status: str
    integrity_status: str
    review_required: bool
    review_reasons: list[str]
    mutation_refused: bool
    schema_version: str = RC87_SCHEMA_VERSION
    replay_kind: str = OBSERVATION_REPLAY_KIND
    adapter_name: str = DEFAULT_READ_ONLY_ADAPTER_NAME
    adapter_kind: str = DEFAULT_READ_ONLY_ADAPTER_KIND
    source_kind: str = "static_fixture"
    review_ticket_id: str | None = None
    rollback_analysis_id: str | None = None
    prior_snapshot_ref: str | None = None
    checkpoint_ref: str | None = None
    mutation_refusal_id: str | None = None
    telemetry_trace_hint: str | None = None
    created_at: str = ""
    package_version: str = RC87_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ObservationRollbackAnalysis:
    rollback_analysis_id: str
    replay_packet_id: str
    snapshot_id: str
    prior_good_snapshot_ref: str | None
    checkpoint_ref: str | None
    recovery_possible: bool
    recovery_action: str
    recovery_performed: bool
    restore_allowed: bool
    restore_performed: bool
    evidence_preserved: bool
    bad_snapshot_evidence_ref: str
    operator_action_required: str
    ambiguity_detected: bool
    ambiguity_reasons: list[str]
    created_at: str
    schema_version: str = RC87_SCHEMA_VERSION
    package_version: str = RC87_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ReadOnlyMutationRefusal:
    refusal_id: str
    request_id: str
    lane_id: str
    requested_operation: str
    refusal_reason: str
    created_at: str
    schema_version: str = RC87_SCHEMA_VERSION
    adapter_name: str = DEFAULT_READ_ONLY_ADAPTER_NAME
    adapter_kind: str = DEFAULT_READ_ONLY_ADAPTER_KIND
    severity: str = "critical"
    review_required: bool = True
    review_ticket_id: str | None = None
    replay_packet_id: str | None = None
    package_version: str = RC87_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ReadOnlyAdapterReviewContext:
    review_trigger: str
    severity: str
    review_required: bool
    review_reasons: list[str]
    lane_id: str
    action_id: str
    action_type: str
    action_status: str
    source_ref_hint: str
    operator_action_required: str
    telemetry_trace_hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ReadOnlyAdapterStatus:
    enabled: bool
    mode: str
    status: str
    adapter_name: str
    adapter_kind: str
    source_kind: str
    environment_kind: str
    latest_snapshot_id: str | None
    latest_replay_packet_id: str | None
    latest_review_ticket_id: str | None
    latest_rollback_analysis_id: str | None
    latest_mutation_refusal_id: str | None
    validation_status: str
    integrity_status: str
    review_required: bool
    review_reasons: list[str]
    mutation_allowed: bool
    mutation_refused_count: int
    observation_count: int
    bad_snapshot_count: int
    stale_snapshot_count: int
    conflicting_observation_count: int
    lane_id: str | None
    lane_attribution_status: str
    lm_portal_trace_confirmation: str
    schema_version: str = RC87_SCHEMA_VERSION
    advisory_copy: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)

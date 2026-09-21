from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

RC84_SCHEMA_VERSION = "rc84.v1"
RC85_SCHEMA_VERSION = "rc85.v1"
LATEST_EXTERNAL_ADAPTER_SCHEMA_VERSION = RC85_SCHEMA_VERSION
NOVALI_BRANCH = "novali-v6"
NOVALI_PACKAGE_VERSION = "rc85"
LEGACY_EXTERNAL_ADAPTER_PACKAGE_VERSION = "rc84"
DEFAULT_ADAPTER_NAME = "mock_external_world"
DEFAULT_ADAPTER_KIND = "mock"


def _to_serializable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _to_serializable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _to_serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_serializable(item) for item in value]
    return value


@dataclass(slots=True)
class ExternalActionPreconditions:
    summary: str
    required: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    safe_scope: str = "mock_only"
    payload_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class AdapterReviewRequirement:
    review_required: bool
    review_reasons: list[str] = field(default_factory=list)
    review_status: str = "clear"
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class WorldSnapshot:
    snapshot_id: str
    adapter_name: str
    adapter_kind: str
    source_controller: str
    world_state_ref: str
    summary: str
    observed_at: str
    telemetry_context: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ExternalActionProposal:
    action_id: str
    adapter_name: str
    adapter_kind: str
    action_type: str
    action_version: str
    source_controller: str
    governing_directive_ref: str
    intended_effect: str
    arguments_redacted: dict[str, Any]
    preconditions: ExternalActionPreconditions
    expected_duration_ms: int
    timeout_ms: int
    idempotency_key: str
    requires_review: bool
    review_reasons: list[str]
    created_at: str
    telemetry_context: dict[str, str] = field(default_factory=dict)
    status: str = "proposed"

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class PreconditionValidationResult:
    valid: bool
    status: str
    summary: str
    preconditions: ExternalActionPreconditions
    review_requirement: AdapterReviewRequirement

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ExternalActionResult:
    action_id: str
    adapter_name: str
    adapter_kind: str
    action_type: str
    status: str
    result_summary: str
    completed_at: str
    duration_ms: int
    failure_reason_redacted: str | None = None
    uncertainty_reason_redacted: str | None = None
    review_required: bool = False
    review_reasons: list[str] = field(default_factory=list)
    mock_mutation_performed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ReviewHoldEscalation:
    severity: str
    escalation_status: str
    escalation_reasons: list[str] = field(default_factory=list)
    operator_action_required: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ReviewHoldLinkage:
    replay_packet_id: str | None = None
    replay_packet_path_hint: str | None = None
    rollback_analysis_id: str | None = None
    rollback_analysis_path_hint: str | None = None
    checkpoint_ref: str | None = None
    prior_stable_state_ref: str | None = None
    telemetry_trace_hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ReviewHoldDecisionContext:
    action_status: str
    review_required: bool
    evidence_integrity_status: str = "warning"
    repeated_uncertainty_count: int = 0
    rollback_candidate: bool = False
    rollback_analysis_missing: bool = False
    checkpoint_available: bool = False
    proof_kind: str = "mock_membrane"

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ReplayPacket:
    schema_version: str
    replay_packet_id: str
    action_id: str
    adapter_name: str
    adapter_kind: str
    source_controller: str
    governing_directive_ref: str
    action_type: str
    intended_effect: str
    preconditions_summary: str
    pre_state_snapshot_ref: str
    post_state_result: str
    status: str
    result_summary: str
    failure_reason_redacted: str | None
    uncertainty_reason_redacted: str | None
    retry_count: int
    timeout_ms: int
    rollback_candidate: bool
    rollback_analysis_ref: str | None
    review_required: bool
    review_reasons: list[str]
    kill_switch_state: str
    telemetry_trace_hint: str
    created_at: str
    completed_at: str
    review_item_id: str | None = None
    review_status: str = "clear"
    rollback_analysis_id: str | None = None
    checkpoint_ref: str | None = None
    prior_stable_state_ref: str | None = None
    escalation_status: str = "clear"
    escalation_reasons: list[str] = field(default_factory=list)
    evidence_integrity_status: str = "warning"
    restore_allowed: bool = False
    restore_performed: bool = False
    package_version: str = NOVALI_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class RollbackAnalysis:
    rollback_analysis_id: str
    replay_packet_id: str
    action_id: str
    rollback_possible: bool
    rollback_candidate: bool
    rollback_scope: str
    prior_stable_state_ref: str
    checkpoint_ref: str | None = None
    checkpoint_available: bool = False
    evidence_preserved: bool = True
    evidence_paths: list[str] = field(default_factory=list)
    operator_action_required: bool = True
    reason_redacted: str = ""
    ambiguity_level: str = "low"
    ambiguity_reasons: list[str] = field(default_factory=list)
    restore_allowed: bool = False
    restore_performed: bool = False
    created_at: str = ""
    schema_version: str = RC85_SCHEMA_VERSION
    package_version: str = NOVALI_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class KillSwitchEvent:
    kill_switch_event_id: str
    adapter_name: str
    adapter_kind: str
    reason_redacted: str
    scope: str
    state: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class EvidenceIntegrityResult:
    evidence_integrity_status: str
    evidence_integrity_findings: list[str] = field(default_factory=list)
    replay_packet_id: str | None = None
    review_item_id: str | None = None
    rollback_analysis_id: str | None = None
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ExternalAdapterReviewItem:
    review_item_id: str
    schema_version: str = RC85_SCHEMA_VERSION
    source: str = "external_adapter"
    adapter_name: str = DEFAULT_ADAPTER_NAME
    adapter_kind: str = DEFAULT_ADAPTER_KIND
    action_id: str = ""
    action_type: str = ""
    action_status: str = ""
    review_status: str = "pending_review"
    review_reasons: list[str] = field(default_factory=list)
    severity: str = "warning"
    operator_action_required: str = ""
    governing_directive_ref: str = ""
    replay_packet_id: str | None = None
    replay_packet_path_hint: str | None = None
    rollback_analysis_id: str | None = None
    rollback_analysis_path_hint: str | None = None
    checkpoint_ref: str | None = None
    prior_stable_state_ref: str | None = None
    kill_switch_state: str = "inactive"
    created_at: str = ""
    updated_at: str = ""
    telemetry_trace_hint: str | None = None
    package_version: str = NOVALI_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH
    evidence_integrity_status: str = "warning"
    escalation_status: str = "clear"
    escalation_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ReviewHoldStatusSummary:
    enabled: bool
    mode: str
    status: str
    pending_count: int
    escalated_count: int
    evidence_missing_count: int
    last_review_item_id: str | None = None
    last_replay_packet_id: str | None = None
    last_rollback_analysis_id: str | None = None
    review_items: list[dict[str, Any]] = field(default_factory=list)
    advisory_copy: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)


@dataclass(slots=True)
class ExternalAdapterStatus:
    enabled: bool
    mode: str
    status: str
    adapter_name: str
    adapter_kind: str
    schema_version: str
    last_proof_result: str
    last_action_status: str | None
    last_review_required: bool
    review_reasons: list[str]
    last_replay_packet_id: str | None
    replay_packet_count: int
    kill_switch_state: str
    telemetry_enabled: bool
    lm_portal_trace_confirmation: str
    last_review_item_id: str | None = None
    last_rollback_analysis_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(self)

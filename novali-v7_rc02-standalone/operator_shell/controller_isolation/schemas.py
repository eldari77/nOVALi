from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

RC86_SCHEMA_VERSION = "rc86.v1"
RC86_PACKAGE_VERSION = "rc86"
NOVALI_BRANCH = "novali-v6"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


@dataclass
class SerializableDataclass:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ControllerLaneIdentity(SerializableDataclass):
    lane_id: str
    lane_role: str
    lane_display_name: str
    namespace_root: str
    doctrine_namespace: str
    memory_namespace: str
    summary_namespace: str
    intervention_namespace: str
    replay_namespace: str
    review_namespace: str
    telemetry_identity: str
    active: bool = False
    mode: str = "mock_only"
    authority_level: str = "evidence_namespace"
    adoption_authority: bool = False
    coordination_authority: bool = False
    can_execute_external_actions: bool = False
    schema_version: str = RC86_SCHEMA_VERSION
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    package_version: str = RC86_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH


@dataclass
class ControllerLaneRegistry(SerializableDataclass):
    lanes: list[ControllerLaneIdentity]
    schema_version: str = RC86_SCHEMA_VERSION
    generated_at: str = field(default_factory=_now_iso)
    package_version: str = RC86_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH

    @property
    def lane_count(self) -> int:
        return len(self.lanes)

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["lane_count"] = self.lane_count
        return payload


@dataclass
class LaneNamespace(SerializableDataclass):
    lane_id: str
    lane_role: str
    namespace_root: str
    doctrine_path: str
    memory_path: str
    summary_path: str
    intervention_path: str
    replay_review_path: str
    review_path: str
    schema_version: str = RC86_SCHEMA_VERSION
    created_at: str = field(default_factory=_now_iso)
    package_version: str = RC86_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH


@dataclass
class LaneDoctrineArtifact(SerializableDataclass):
    lane_id: str
    lane_role: str
    doctrine_namespace: str
    doctrine_summary_redacted: str
    allowed_scope: list[str]
    forbidden_scope: list[str]
    source: str = "mock_isolation_proof"
    schema_version: str = RC86_SCHEMA_VERSION
    created_at: str = field(default_factory=_now_iso)
    package_version: str = RC86_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH


@dataclass
class LaneMemoryArtifact(SerializableDataclass):
    lane_id: str
    memory_namespace: str
    memory_summary_redacted: str
    memory_items_count: int
    no_hidden_shared_state: bool = True
    schema_version: str = RC86_SCHEMA_VERSION
    last_updated_at: str = field(default_factory=_now_iso)
    package_version: str = RC86_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH


@dataclass
class LaneSummaryArtifact(SerializableDataclass):
    lane_id: str
    summary_namespace: str
    summary_redacted: str
    continuity_note: str
    schema_version: str = RC86_SCHEMA_VERSION
    created_at: str = field(default_factory=_now_iso)
    package_version: str = RC86_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH


@dataclass
class LaneInterventionHistory(SerializableDataclass):
    lane_id: str
    event_type: str
    review_status: str
    summary_redacted: str
    schema_version: str = RC86_SCHEMA_VERSION
    created_at: str = field(default_factory=_now_iso)
    package_version: str = RC86_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH


@dataclass
class LaneReplayReviewBinding(SerializableDataclass):
    lane_id: str
    binding_kind: str
    artifact_id: str
    artifact_path_hint: str
    summary_redacted: str
    schema_version: str = RC86_SCHEMA_VERSION
    created_at: str = field(default_factory=_now_iso)
    package_version: str = RC86_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH


@dataclass
class DirectorApprovalRecord(SerializableDataclass):
    message_id: str
    approval_status: str
    review_required: bool
    review_reasons: list[str]
    director_lane_id: str = "lane_director"
    approval_record_id: str = ""
    schema_version: str = RC86_SCHEMA_VERSION
    created_at: str = field(default_factory=_now_iso)
    package_version: str = RC86_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH

    def __post_init__(self) -> None:
        if not self.approval_record_id:
            suffix = self.message_id.rsplit("-", 1)[-1]
            self.approval_record_id = f"director-approval-{suffix}"


@dataclass
class CrossLaneMessageEnvelope(SerializableDataclass):
    message_id: str
    source_lane_id: str
    target_lane_id: str
    approval_record_id: str
    approval_status: str
    message_type: str
    payload_summary_redacted: str
    allowed_scope: str
    review_required: bool
    review_reasons: list[str]
    replay_packet_id: str | None
    schema_version: str = RC86_SCHEMA_VERSION
    mediated_by_lane_id: str = "lane_director"
    created_at: str = field(default_factory=_now_iso)
    delivered_at: str | None = None
    package_version: str = RC86_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH


@dataclass
class IdentityBleedFinding(SerializableDataclass):
    finding_id: str
    finding_type: str
    severity: str
    source_lane_id: str
    target_lane_id: str | None
    affected_namespace: str | None
    evidence_summary_redacted: str
    review_ticket_id: str | None
    replay_packet_id: str | None
    schema_version: str = RC86_SCHEMA_VERSION
    review_required: bool = True
    created_at: str = field(default_factory=_now_iso)
    package_version: str = RC86_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH


@dataclass
class ControllerIsolationReviewItem(SerializableDataclass):
    review_ticket_id: str
    finding_id: str
    finding_type: str
    lane_id: str
    source_lane_id: str
    target_lane_id: str | None
    review_trigger: str
    review_status: str
    severity: str
    operator_action_required: str
    review_reasons: list[str]
    replay_packet_id: str | None
    replay_packet_path_hint: str | None
    message_id: str | None
    evidence_integrity_status: str
    source: str = "controller_isolation"
    schema_version: str = RC86_SCHEMA_VERSION
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    package_version: str = RC86_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH


@dataclass
class ControllerIsolationReplayPacket(SerializableDataclass):
    replay_packet_id: str
    lane_id: str
    source_lane_id: str
    target_lane_id: str | None
    intended_effect: str
    status: str
    result_summary_redacted: str
    review_required: bool
    review_reasons: list[str]
    evidence_integrity_status: str
    message_id: str | None = None
    finding_id: str | None = None
    review_ticket_id: str | None = None
    schema_version: str = RC86_SCHEMA_VERSION
    replay_kind: str = "controller_isolation"
    created_at: str = field(default_factory=_now_iso)
    package_version: str = RC86_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH


@dataclass
class LaneIsolationStatus(SerializableDataclass):
    enabled: bool
    mode: str
    status: str
    lanes: list[dict[str, Any]]
    lane_count: int
    isolation_checks: dict[str, str]
    identity_bleed: dict[str, Any]
    cross_lane_messages: dict[str, Any]
    lm_portal_trace_confirmation: str
    advisory_copy: list[str]
    schema_version: str = RC86_SCHEMA_VERSION


@dataclass
class LaneIsolationProofResult(SerializableDataclass):
    proof_id: str
    result: str
    lane_count: int
    finding_count: int
    review_ticket_count: int
    replay_packet_count: int
    schema_version: str = RC86_SCHEMA_VERSION
    generated_at: str = field(default_factory=_now_iso)
    package_version: str = RC86_PACKAGE_VERSION
    branch: str = NOVALI_BRANCH

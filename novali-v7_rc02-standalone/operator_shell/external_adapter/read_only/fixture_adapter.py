from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from operator_shell.observability.redaction import redact_value

from .schemas import (
    DEFAULT_READ_ONLY_ADAPTER_KIND,
    DEFAULT_READ_ONLY_ADAPTER_NAME,
    ObservationIntegrityResult,
    ObservationReplayPacket,
    ObservationRollbackAnalysis,
    ObservationSourceMetadata,
    ObservationValidationResult,
    ReadOnlyAdapterStatus,
    ReadOnlyMutationRefusal,
    ReadOnlyWorldSnapshot,
)
from .validation import build_observation_summary, hash_file, snapshot_from_payload, validate_observation_integrity, validate_snapshot_schema


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _path_hint(source_ref: str | Path) -> str:
    return Path(str(source_ref)).name or "<unknown>"


@dataclass(slots=True)
class ReadOnlyAdapterContext:
    source_controller: str = "novali_controller"
    governing_directive_ref: str = "read_only.fixture.rc87"
    proof_kind: str = "read_only_adapter_sandbox_proof"
    telemetry_trace_hint: str = "rc87.read_only_adapter.proof"


class ReadOnlyExternalAdapter(ABC):
    @abstractmethod
    def load_snapshot(self, source_ref: str | Path) -> ReadOnlyWorldSnapshot:
        raise NotImplementedError

    @abstractmethod
    def validate_snapshot_schema(self, snapshot: ReadOnlyWorldSnapshot) -> ObservationValidationResult:
        raise NotImplementedError

    @abstractmethod
    def validate_observation_integrity(
        self,
        snapshot: ReadOnlyWorldSnapshot,
        validation_result: ObservationValidationResult | None = None,
    ) -> ObservationIntegrityResult:
        raise NotImplementedError

    @abstractmethod
    def summarize_observation(self, snapshot: ReadOnlyWorldSnapshot) -> str:
        raise NotImplementedError

    @abstractmethod
    def emit_observation_replay(
        self,
        snapshot: ReadOnlyWorldSnapshot,
        validation: ObservationValidationResult,
        integrity: ObservationIntegrityResult,
        *,
        prior_snapshot_ref: str | None = None,
        checkpoint_ref: str | None = None,
        review_ticket_id: str | None = None,
        rollback_analysis_id: str | None = None,
        mutation_refusal: ReadOnlyMutationRefusal | None = None,
    ) -> ObservationReplayPacket:
        raise NotImplementedError

    @abstractmethod
    def request_observation_rollback_analysis(
        self,
        replay_packet: ObservationReplayPacket,
        prior_snapshot_ref: str | None,
    ) -> ObservationRollbackAnalysis:
        raise NotImplementedError

    @abstractmethod
    def refuse_mutation_request(
        self,
        request: dict[str, Any],
        reason: str,
    ) -> ReadOnlyMutationRefusal:
        raise NotImplementedError

    @abstractmethod
    def get_read_only_status(self) -> ReadOnlyAdapterStatus:
        raise NotImplementedError


class StaticFixtureReadOnlyAdapter(ReadOnlyExternalAdapter):
    def __init__(
        self,
        *,
        package_root: str | Path,
        context: ReadOnlyAdapterContext | None = None,
        adapter_name: str = DEFAULT_READ_ONLY_ADAPTER_NAME,
        adapter_kind: str = DEFAULT_READ_ONLY_ADAPTER_KIND,
    ) -> None:
        self.package_root = Path(package_root).resolve()
        self.context = context or ReadOnlyAdapterContext()
        self.adapter_name = str(adapter_name or DEFAULT_READ_ONLY_ADAPTER_NAME)
        self.adapter_kind = str(adapter_kind or DEFAULT_READ_ONLY_ADAPTER_KIND)
        self._status = ReadOnlyAdapterStatus(
            enabled=True,
            mode="fixture_read_only",
            status="ready",
            adapter_name=self.adapter_name,
            adapter_kind=self.adapter_kind,
            source_kind="static_fixture",
            environment_kind="generic_non_se_sandbox",
            latest_snapshot_id=None,
            latest_replay_packet_id=None,
            latest_review_ticket_id=None,
            latest_rollback_analysis_id=None,
            latest_mutation_refusal_id=None,
            validation_status="unknown",
            integrity_status="unknown",
            review_required=False,
            review_reasons=[],
            mutation_allowed=False,
            mutation_refused_count=0,
            observation_count=0,
            bad_snapshot_count=0,
            stale_snapshot_count=0,
            conflicting_observation_count=0,
            lane_id=None,
            lane_attribution_status="unknown",
            lm_portal_trace_confirmation="not_recorded",
            advisory_copy=[
                "Read-only adapter: observation only.",
                "No real external-world mutation.",
                "Observation replay packets are evidence, not authority.",
                "Controller authority and review gates remain unchanged.",
                "No Space Engineers behavior is active.",
            ],
        )

    def _source_metadata(self, source_ref: str | Path) -> ObservationSourceMetadata:
        path = Path(source_ref).resolve()
        return ObservationSourceMetadata(
            source_kind="static_fixture",
            source_name=path.stem,
            source_ref_hint=_path_hint(path),
            loaded_at=_now_iso(),
            fixture_sha256=hash_file(path),
        )

    def load_snapshot(self, source_ref: str | Path) -> ReadOnlyWorldSnapshot:
        path = Path(source_ref).resolve()
        payload = json.loads(path.read_text(encoding="utf-8"))
        snapshot = snapshot_from_payload(payload, source_ref=path)
        metadata = self._source_metadata(path)
        if not snapshot.source_name:
            snapshot.source_name = metadata.source_name
        if not snapshot.source_kind:
            snapshot.source_kind = metadata.source_kind
        if not snapshot.source_ref:
            snapshot.source_ref = metadata.source_ref_hint
        self._status.latest_snapshot_id = snapshot.snapshot_id or None
        self._status.source_kind = snapshot.source_kind or "static_fixture"
        self._status.environment_kind = snapshot.environment_kind or "generic_non_se_sandbox"
        self._status.lane_id = snapshot.lane_id or None
        return snapshot

    def validate_snapshot_schema(self, snapshot: ReadOnlyWorldSnapshot) -> ObservationValidationResult:
        result = validate_snapshot_schema(snapshot, package_root=self.package_root)
        self._status.validation_status = result.validation_status
        self._status.review_required = result.review_required
        self._status.review_reasons = list(result.review_reasons)
        if result.validation_status in {"failed", "review_required"}:
            self._status.bad_snapshot_count += 1
        if result.stale_snapshot:
            self._status.stale_snapshot_count += 1
        return result

    def validate_observation_integrity(
        self,
        snapshot: ReadOnlyWorldSnapshot,
        validation_result: ObservationValidationResult | None = None,
    ) -> ObservationIntegrityResult:
        result = validate_observation_integrity(
            snapshot,
            package_root=self.package_root,
            validation_result=validation_result,
        )
        self._status.integrity_status = result.integrity_status
        self._status.review_required = result.review_required
        self._status.review_reasons = list(result.review_reasons)
        self._status.lane_id = snapshot.lane_id or None
        self._status.lane_attribution_status = result.lane_attribution_status
        if result.conflicting_observations:
            self._status.conflicting_observation_count += 1
        return result

    def summarize_observation(self, snapshot: ReadOnlyWorldSnapshot) -> str:
        return build_observation_summary(snapshot).summary_redacted

    def emit_observation_replay(
        self,
        snapshot: ReadOnlyWorldSnapshot,
        validation: ObservationValidationResult,
        integrity: ObservationIntegrityResult,
        *,
        prior_snapshot_ref: str | None = None,
        checkpoint_ref: str | None = None,
        review_ticket_id: str | None = None,
        rollback_analysis_id: str | None = None,
        mutation_refusal: ReadOnlyMutationRefusal | None = None,
    ) -> ObservationReplayPacket:
        observation = build_observation_summary(snapshot)
        digest = hashlib.sha1(
            "|".join(
                [
                    snapshot.snapshot_id or "<missing_snapshot_id>",
                    snapshot.lane_id or "<missing_lane>",
                    validation.validation_status,
                    integrity.integrity_status,
                    mutation_refusal.refusal_id if mutation_refusal is not None else "",
                ]
            ).encode("utf-8")
        ).hexdigest()[:12]
        replay = ObservationReplayPacket(
            replay_packet_id=f"read-only-replay-{digest}",
            source_ref_hint=_path_hint(snapshot.source_ref or snapshot.source_name or "fixture"),
            snapshot_id=snapshot.snapshot_id or "<missing_snapshot_id>",
            lane_id=snapshot.lane_id or "<missing_lane>",
            source_controller=self.context.source_controller,
            governing_directive_ref=self.context.governing_directive_ref,
            observation_summary_redacted=observation.summary_redacted,
            entity_count=observation.entity_count,
            relationship_count=observation.relationship_count,
            metric_count=observation.metric_count,
            validation_status=validation.validation_status,
            integrity_status=integrity.integrity_status,
            review_required=bool(validation.review_required or integrity.review_required),
            review_reasons=list(dict.fromkeys(list(validation.review_reasons) + list(integrity.review_reasons))),
            review_ticket_id=str(review_ticket_id or "") or None,
            rollback_analysis_id=str(rollback_analysis_id or "") or None,
            prior_snapshot_ref=str(prior_snapshot_ref or "") or None,
            checkpoint_ref=str(checkpoint_ref or "") or None,
            mutation_refused=mutation_refusal is not None,
            mutation_refusal_id=mutation_refusal.refusal_id if mutation_refusal is not None else None,
            telemetry_trace_hint=self.context.telemetry_trace_hint,
            created_at=_now_iso(),
            package_version="rc87",
        )
        self._status.latest_replay_packet_id = replay.replay_packet_id
        self._status.observation_count += 1
        self._status.status = (
            "review_required"
            if replay.review_required
            else "observed"
        )
        return replay

    def request_observation_rollback_analysis(
        self,
        replay_packet: ObservationReplayPacket,
        prior_snapshot_ref: str | None,
    ) -> ObservationRollbackAnalysis:
        analysis_digest = hashlib.sha1(
            "|".join([replay_packet.replay_packet_id, replay_packet.snapshot_id, str(prior_snapshot_ref or "")]).encode("utf-8")
        ).hexdigest()[:12]
        analysis = ObservationRollbackAnalysis(
            rollback_analysis_id=f"read-only-rollback-{analysis_digest}",
            replay_packet_id=replay_packet.replay_packet_id,
            snapshot_id=replay_packet.snapshot_id,
            prior_good_snapshot_ref=str(prior_snapshot_ref or "") or None,
            checkpoint_ref=replay_packet.checkpoint_ref,
            recovery_possible=bool(prior_snapshot_ref),
            recovery_action=(
                "Preserve the prior-good snapshot pointer while retaining bad snapshot evidence."
                if prior_snapshot_ref
                else "Preserve bad snapshot evidence and require operator review because no prior-good snapshot is available."
            ),
            recovery_performed=bool(prior_snapshot_ref),
            restore_allowed=False,
            restore_performed=False,
            evidence_preserved=True,
            bad_snapshot_evidence_ref=f"observation_replay_packets/{replay_packet.replay_packet_id}.json",
            operator_action_required=(
                "Inspect the bad snapshot evidence and confirm whether the prior-good observation should remain authoritative."
            ),
            ambiguity_detected=not bool(prior_snapshot_ref),
            ambiguity_reasons=[] if prior_snapshot_ref else ["no_prior_good_snapshot"],
            created_at=_now_iso(),
            package_version="rc87",
        )
        self._status.latest_rollback_analysis_id = analysis.rollback_analysis_id
        return analysis

    def refuse_mutation_request(
        self,
        request: dict[str, Any],
        reason: str,
    ) -> ReadOnlyMutationRefusal:
        request_id = str(request.get("request_id", "")).strip() or f"mutation-request-{hashlib.sha1(json.dumps(request, sort_keys=True, default=str).encode('utf-8')).hexdigest()[:10]}"
        requested_operation = str(request.get("requested_operation", "")).strip() or "unknown_operation"
        lane_id = str(request.get("lane_id", "")).strip() or "lane_director"
        refusal_digest = hashlib.sha1(
            "|".join([request_id, lane_id, requested_operation, reason]).encode("utf-8")
        ).hexdigest()[:12]
        refusal = ReadOnlyMutationRefusal(
            refusal_id=f"mutation-refusal-{refusal_digest}",
            request_id=request_id,
            lane_id=lane_id,
            requested_operation=requested_operation,
            refusal_reason=str(redact_value(reason, key="refusal_reason") or ""),
            created_at=_now_iso(),
            package_version="rc87",
        )
        self._status.latest_mutation_refusal_id = refusal.refusal_id
        self._status.mutation_refused_count += 1
        self._status.review_required = True
        self._status.status = "review_blocked"
        self._status.review_reasons = list(
            dict.fromkeys(list(self._status.review_reasons) + ["read_only_mutation_requested"])
        )
        return refusal

    def get_read_only_status(self) -> ReadOnlyAdapterStatus:
        return self._status

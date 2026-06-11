from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .schemas import (
    ExternalActionProposal,
    ExternalActionResult,
    KillSwitchEvent,
    PreconditionValidationResult,
    ReplayPacket,
    RollbackAnalysis,
    WorldSnapshot,
)


@dataclass(slots=True)
class AdapterContext:
    source_controller: str
    governing_directive_ref: str
    proof_kind: str = "mock_membrane"
    telemetry_trace_hint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ExternalWorldAdapter(ABC):
    @abstractmethod
    def get_world_snapshot(self, context: AdapterContext) -> WorldSnapshot:
        raise NotImplementedError

    @abstractmethod
    def propose_action(
        self,
        snapshot: WorldSnapshot,
        action_request: dict[str, Any],
    ) -> ExternalActionProposal:
        raise NotImplementedError

    @abstractmethod
    def validate_preconditions(
        self,
        proposal: ExternalActionProposal,
        snapshot: WorldSnapshot,
    ) -> PreconditionValidationResult:
        raise NotImplementedError

    @abstractmethod
    def execute_bounded_action(self, proposal: ExternalActionProposal) -> ExternalActionResult:
        raise NotImplementedError

    @abstractmethod
    def acknowledge_result(
        self,
        action_id: str,
        result: ExternalActionResult,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def emit_replay_packet(
        self,
        proposal: ExternalActionProposal,
        result: ExternalActionResult,
        snapshot: WorldSnapshot,
        review_state: dict[str, Any],
    ) -> ReplayPacket:
        raise NotImplementedError

    @abstractmethod
    def request_rollback_analysis(self, replay_packet: ReplayPacket) -> RollbackAnalysis:
        raise NotImplementedError

    @abstractmethod
    def trigger_kill_switch(self, reason: str, scope: str) -> KillSwitchEvent:
        raise NotImplementedError

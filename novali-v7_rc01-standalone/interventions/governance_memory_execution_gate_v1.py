from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from .ledger import intervention_data_dir


EXECUTION_PERMISSION_SCHEMA_NAME = "GovernanceMemoryExecutionPermission"
EXECUTION_PERMISSION_SCHEMA_VERSION = "governance_memory_execution_permission_v1"

ALLOWED = "allowed"
SHADOW_ONLY = "shadow_only"
BLOCKED_PENDING_REOPEN = "blocked_pending_reopen"
NON_AUTHORITATIVE_OBSERVATION_ONLY = "non_authoritative_observation_only"

HOLD_BLOCKED_PROPOSAL_TYPES = {
    "critic_split",
    "proposal_learning_loop",
    "routing_rule",
    "safety_veto_patch",
    "score_reweight",
    "support_contract",
}

GOVERNANCE_MEMORY_AUTHORITY_PATH = intervention_data_dir() / "governance_memory_authority_latest.json"


class GovernanceExecutionBlockedError(RuntimeError):
    def __init__(
        self,
        permission: dict[str, Any],
        *,
        intake_record: dict[str, Any] | None = None,
        intake_error: str | None = None,
    ) -> None:
        self.permission = copy.deepcopy(dict(permission))
        self.intake_record = copy.deepcopy(dict(intake_record or {}))
        self.intake_error = None if intake_error is None else str(intake_error)

        message = (
            "Governance authority blocked execution: "
            f"{self.permission.get('action_kind')} -> {self.permission.get('permission_state')} "
            f"({self.permission.get('reason')})"
        )
        artifact_path = str(self.intake_record.get("artifact_path", ""))
        if artifact_path:
            message += f" [reopen intake: {artifact_path}]"
        elif self.intake_error:
            message += f" [reopen intake emission failed: {self.intake_error}]"
        super().__init__(message)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_resolved_state() -> tuple[dict[str, Any], str | None]:
    try:
        from .governance_memory_resolver_v1 import resolve_governance_memory_current_state

        return resolve_governance_memory_current_state(), None
    except Exception as exc:  # pragma: no cover - safety-first fallback
        return {}, f"{type(exc).__name__}: {exc}"


def _canonical_posture(resolved_state: dict[str, Any]) -> dict[str, Any]:
    return dict(resolved_state.get("canonical_current_posture", {}))


def _reopen_not_supported(posture: dict[str, Any]) -> bool:
    reopen = dict(posture.get("reopen_eligibility", {}))
    branch_status = str(reopen.get("branch_reopen_candidate_status", ""))
    benchmark_supported = bool(reopen.get("benchmark_controlled_reopen_supported", False))
    return branch_status == "requires_new_evidence" and not benchmark_supported


def _governed_work_loop_closed(posture: dict[str, Any]) -> bool:
    return str(posture.get("governed_work_loop_status", "")) == "hold_position_closed_out_v1"


def _template_memory_line_blocked(template_name: str, posture: dict[str, Any]) -> tuple[bool, str]:
    template = str(template_name)
    if _governed_work_loop_closed(posture) and "governed_work_loop" in template:
        return True, "governed work-loop line is closed out and cannot continue by momentum"
    return False, ""


def _proposal_context(template_name: str) -> dict[str, Any]:
    from .taxonomy import build_proposal_template, proposal_evaluation_semantics

    proposal = build_proposal_template(str(template_name))
    proposal_type = str(proposal.get("proposal_type", ""))
    evaluation_semantics = str(
        proposal.get("evaluation_semantics") or proposal_evaluation_semantics(proposal_type)
    )
    return {
        "template_name": str(template_name),
        "proposal_type": proposal_type,
        "evaluation_semantics": evaluation_semantics,
        "scope": str(proposal.get("scope", "")),
    }


def _permission_record(
    *,
    action_kind: str,
    permission_state: str,
    reason: str,
    resolved_state: dict[str, Any],
    template_context: dict[str, Any] | None = None,
    conflict_tags: list[str] | None = None,
    resolution_error: str | None = None,
) -> dict[str, Any]:
    posture = _canonical_posture(resolved_state)
    return {
        "schema_name": EXECUTION_PERMISSION_SCHEMA_NAME,
        "schema_version": EXECUTION_PERMISSION_SCHEMA_VERSION,
        "resolved_at": _now(),
        "action_kind": str(action_kind),
        "permission_state": str(permission_state),
        "allowed_to_execute": str(permission_state) != BLOCKED_PENDING_REOPEN,
        "governance_enforced": True,
        "canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
        "canonical_posture": {
            "current_operating_stance": str(posture.get("current_operating_stance", "")),
            "current_branch_state": str(posture.get("current_branch_state", "")),
            "held_baseline_template": str(posture.get("held_baseline_template", "")),
            "routing_status": str(posture.get("routing_status", "")),
            "reopen_eligibility": dict(posture.get("reopen_eligibility", {})),
        },
        "selector_frontier_conclusions": dict(resolved_state.get("selector_frontier_conclusions", {})),
        "capability_boundaries": dict(resolved_state.get("capability_boundaries", {})),
        "binding_decisions": dict(resolved_state.get("binding_decisions", {})),
        "authority_mutation_state": dict(resolved_state.get("authority_mutation_state", {})),
        "template_context": dict(template_context or {}),
        "conflict_tags": list(conflict_tags or []),
        "reason": str(reason),
        "resolution_error": None if resolution_error is None else str(resolution_error),
    }


def build_execution_permission(
    *,
    action_kind: str,
    template_name: str | None = None,
) -> dict[str, Any]:
    resolved_state, resolution_error = _safe_resolved_state()
    if resolution_error is not None:
        return _permission_record(
            action_kind=action_kind,
            permission_state=BLOCKED_PENDING_REOPEN,
            reason="canonical authority could not be resolved, so governed execution is blocked pending review",
            resolved_state={},
            template_context={"template_name": str(template_name or "")},
            conflict_tags=["canonical_authority_unavailable"],
            resolution_error=resolution_error,
        )

    posture = _canonical_posture(resolved_state)
    operating_stance = str(posture.get("current_operating_stance", ""))
    branch_state = str(posture.get("current_branch_state", ""))
    routing_status = str(posture.get("routing_status", ""))
    reopen_not_supported = _reopen_not_supported(posture)

    if action_kind in {"proposal_analytics", "proposal_recommend"}:
        return _permission_record(
            action_kind=action_kind,
            permission_state=NON_AUTHORITATIVE_OBSERVATION_ONLY,
            reason="this runtime surface is observational only and cannot mutate canonical authority",
            resolved_state=resolved_state,
            conflict_tags=["non_authoritative_runtime_surface"],
        )

    if action_kind == "governed_execution":
        return _permission_record(
            action_kind=action_kind,
            permission_state=ALLOWED,
            reason=(
                "canonical authority allows the bounded operator-enveloped governed execution surface; "
                "protected-surface mutation remains blocked by frozen operator constraints and runtime guards"
            ),
            resolved_state=resolved_state,
            conflict_tags=["bounded_operator_envelope", "mutable_shell_only"],
        )

    if action_kind in {"benchmark_only", "trusted_benchmark_pack_cli"}:
        return _permission_record(
            action_kind=action_kind,
            permission_state=SHADOW_ONLY,
            reason="the frozen benchmark pack remains readable under hold posture, but only as a shadow-only evaluation surface",
            resolved_state=resolved_state,
            conflict_tags=["hold_and_consolidate", "shadow_only"],
        )

    if action_kind in {"training_loop", "compare_live_ab"}:
        if branch_state == "paused_with_baseline_held" or operating_stance == "hold_and_consolidate":
            return _permission_record(
                action_kind=action_kind,
                permission_state=BLOCKED_PENDING_REOPEN,
                reason="the branch is paused with the baseline held, so runtime execution is blocked pending a governed reopen",
                resolved_state=resolved_state,
                conflict_tags=[
                    "paused_with_baseline_held",
                    "hold_and_consolidate",
                    "reopen_not_supported_without_new_evidence",
                ],
            )
        return _permission_record(
            action_kind=action_kind,
            permission_state=ALLOWED,
            reason="canonical authority does not currently block this runtime action",
            resolved_state=resolved_state,
        )

    if action_kind == "proposal_runner":
        context = _proposal_context(str(template_name or ""))
        template_blocked, template_reason = _template_memory_line_blocked(
            str(template_name or ""),
            posture,
        )
        if template_blocked:
            return _permission_record(
                action_kind=action_kind,
                permission_state=BLOCKED_PENDING_REOPEN,
                reason=template_reason,
                resolved_state=resolved_state,
                template_context=context,
                conflict_tags=["closed_governed_work_loop_line"],
            )

        proposal_type = str(context.get("proposal_type", ""))
        evaluation_semantics = str(context.get("evaluation_semantics", ""))

        if proposal_type == "memory_summary":
            return _permission_record(
                action_kind=action_kind,
                permission_state=SHADOW_ONLY,
                reason="memory-summary execution is allowed only as a shadow-safe diagnostic and does not reopen branch posture",
                resolved_state=resolved_state,
                template_context=context,
                conflict_tags=["shadow_only", "diagnostic_memory_surface"],
            )

        if proposal_type in HOLD_BLOCKED_PROPOSAL_TYPES and (
            operating_stance == "hold_and_consolidate"
            or branch_state == "paused_with_baseline_held"
            or reopen_not_supported
        ):
            conflict_tags = [
                "hold_and_consolidate",
                "paused_with_baseline_held",
                "reopen_not_supported_without_new_evidence",
            ]
            if proposal_type == "routing_rule" or routing_status == "routing_deferred":
                conflict_tags.append("routing_deferred")
            return _permission_record(
                action_kind=action_kind,
                permission_state=BLOCKED_PENDING_REOPEN,
                reason=(
                    "canonical authority holds this exploratory or control-changing proposal family closed until new evidence clears the reopen bar"
                ),
                resolved_state=resolved_state,
                template_context=context,
                conflict_tags=conflict_tags,
            )

        if evaluation_semantics == "diagnostic":
            return _permission_record(
                action_kind=action_kind,
                permission_state=SHADOW_ONLY,
                reason="diagnostic proposal execution remains shadow-only under governed authority",
                resolved_state=resolved_state,
                template_context=context,
                conflict_tags=["shadow_only", "diagnostic_probe"],
            )

        return _permission_record(
            action_kind=action_kind,
            permission_state=ALLOWED,
            reason="canonical authority allows this proposal execution surface",
            resolved_state=resolved_state,
            template_context=context,
        )

    return _permission_record(
        action_kind=action_kind,
        permission_state=BLOCKED_PENDING_REOPEN,
        reason="unknown governed action kind; execution is blocked until the action surface is explicitly classified",
        resolved_state=resolved_state,
        template_context={"template_name": str(template_name or "")},
        conflict_tags=["unknown_action_kind"],
    )


def require_execution_permission(permission: dict[str, Any]) -> None:
    if str(permission.get("permission_state", "")) == BLOCKED_PENDING_REOPEN:
        intake_record: dict[str, Any] | None = None
        intake_error: str | None = None
        try:
            from .governance_memory_reopen_intake_v1 import emit_governance_reopen_intake

            intake_record = emit_governance_reopen_intake(
                permission=permission,
                requested_by_surface="governed_runtime_preflight",
            )
        except Exception as exc:  # pragma: no cover - blocking must survive intake failures
            intake_error = f"{type(exc).__name__}: {exc}"
        raise GovernanceExecutionBlockedError(
            permission,
            intake_record=intake_record,
            intake_error=intake_error,
        )


def format_execution_permission(permission: dict[str, Any]) -> str:
    posture = dict(permission.get("canonical_posture", {}))
    return (
        f"{permission.get('action_kind')} -> {permission.get('permission_state')} "
        f"(stance={posture.get('current_operating_stance')}, "
        f"branch={posture.get('current_branch_state')}, "
        f"routing={posture.get('routing_status')}; "
        f"reason={permission.get('reason')})"
    )

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any

from .common import OPERATOR_POLICY_ROOT_ENV


WORK_SUMMARY_SCHEMA_NAME = "GovernedExecutionWorkSummary"
WORK_SUMMARY_SCHEMA_VERSION = "governed_execution_work_summary_v1"
FILE_PLAN_SCHEMA_NAME = "GovernedExecutionFilePlan"
FILE_PLAN_SCHEMA_VERSION = "governed_execution_file_plan_v1"
IMPLEMENTATION_BUNDLE_SCHEMA_NAME = "GovernedExecutionImplementationBundleSummary"
IMPLEMENTATION_BUNDLE_SCHEMA_VERSION = "governed_execution_implementation_bundle_summary_v1"
WORKSPACE_ARTIFACT_INDEX_SCHEMA_NAME = "GovernedExecutionWorkspaceArtifactIndex"
WORKSPACE_ARTIFACT_INDEX_SCHEMA_VERSION = "governed_execution_workspace_artifact_index_v1"
CONTROLLER_SUMMARY_SCHEMA_NAME = "GovernedExecutionControllerSummary"
CONTROLLER_SUMMARY_SCHEMA_VERSION = "governed_execution_controller_summary_v1"
SUCCESSOR_READINESS_EVALUATION_SCHEMA_NAME = "GovernedExecutionSuccessorReadinessEvaluation"
SUCCESSOR_READINESS_EVALUATION_SCHEMA_VERSION = "governed_execution_successor_readiness_evaluation_v1"
SUCCESSOR_DELIVERY_MANIFEST_SCHEMA_NAME = "GovernedExecutionSuccessorDeliveryManifest"
SUCCESSOR_DELIVERY_MANIFEST_SCHEMA_VERSION = "governed_execution_successor_delivery_manifest_v1"
TRUSTED_PLANNING_EVIDENCE_SCHEMA_NAME = "GovernedExecutionTrustedPlanningEvidence"
TRUSTED_PLANNING_EVIDENCE_SCHEMA_VERSION = "governed_execution_trusted_planning_evidence_v1"
MISSING_DELIVERABLES_SCHEMA_NAME = "GovernedExecutionMissingDeliverablesSummary"
MISSING_DELIVERABLES_SCHEMA_VERSION = "governed_execution_missing_deliverables_summary_v1"
NEXT_STEP_DERIVATION_SCHEMA_NAME = "GovernedExecutionNextStepDerivation"
NEXT_STEP_DERIVATION_SCHEMA_VERSION = "governed_execution_next_step_derivation_v1"
COMPLETION_EVALUATION_SCHEMA_NAME = "GovernedExecutionCompletionEvaluation"
COMPLETION_EVALUATION_SCHEMA_VERSION = "governed_execution_completion_evaluation_v1"
SUCCESSOR_REVIEW_SUMMARY_SCHEMA_NAME = "GovernedExecutionSuccessorReviewSummary"
SUCCESSOR_REVIEW_SUMMARY_SCHEMA_VERSION = "governed_execution_successor_review_summary_v1"
SUCCESSOR_PROMOTION_RECOMMENDATION_SCHEMA_NAME = "GovernedExecutionSuccessorPromotionRecommendation"
SUCCESSOR_PROMOTION_RECOMMENDATION_SCHEMA_VERSION = "governed_execution_successor_promotion_recommendation_v1"
SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_NAME = "GovernedExecutionSuccessorNextObjectiveProposal"
SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_VERSION = "governed_execution_successor_next_objective_proposal_v1"
SUCCESSOR_RESEED_REQUEST_SCHEMA_NAME = "GovernedExecutionSuccessorReseedRequest"
SUCCESSOR_RESEED_REQUEST_SCHEMA_VERSION = "governed_execution_successor_reseed_request_v1"
SUCCESSOR_RESEED_DECISION_SCHEMA_NAME = "GovernedExecutionSuccessorReseedDecision"
SUCCESSOR_RESEED_DECISION_SCHEMA_VERSION = "governed_execution_successor_reseed_decision_v1"
SUCCESSOR_CONTINUATION_LINEAGE_SCHEMA_NAME = "GovernedExecutionSuccessorContinuationLineage"
SUCCESSOR_CONTINUATION_LINEAGE_SCHEMA_VERSION = "governed_execution_successor_continuation_lineage_v1"
SUCCESSOR_EFFECTIVE_NEXT_OBJECTIVE_SCHEMA_NAME = "GovernedExecutionSuccessorEffectiveNextObjective"
SUCCESSOR_EFFECTIVE_NEXT_OBJECTIVE_SCHEMA_VERSION = "governed_execution_successor_effective_next_objective_v1"
SUCCESSOR_AUTO_CONTINUE_POLICY_SCHEMA_NAME = "GovernedExecutionSuccessorAutoContinuePolicy"
SUCCESSOR_AUTO_CONTINUE_POLICY_SCHEMA_VERSION = "governed_execution_successor_auto_continue_policy_v1"
SUCCESSOR_AUTO_CONTINUE_STATE_SCHEMA_NAME = "GovernedExecutionSuccessorAutoContinueState"
SUCCESSOR_AUTO_CONTINUE_STATE_SCHEMA_VERSION = "governed_execution_successor_auto_continue_state_v1"
SUCCESSOR_AUTO_CONTINUE_DECISION_SCHEMA_NAME = "GovernedExecutionSuccessorAutoContinueDecision"
SUCCESSOR_AUTO_CONTINUE_DECISION_SCHEMA_VERSION = "governed_execution_successor_auto_continue_decision_v1"
SUCCESSOR_CANDIDATE_PROMOTION_BUNDLE_SCHEMA_NAME = "GovernedExecutionSuccessorCandidatePromotionBundle"
SUCCESSOR_CANDIDATE_PROMOTION_BUNDLE_SCHEMA_VERSION = "governed_execution_successor_candidate_promotion_bundle_v1"
SUCCESSOR_COMPLETION_KNOWLEDGE_PACK_SCHEMA_NAME = "NovaliSuccessorCompletionKnowledgePack"
SUCCESSOR_COMPLETION_KNOWLEDGE_PACK_SCHEMA_VERSION = "novali_successor_completion_knowledge_pack_v1"
WORKSPACE_CONTINUATION_KNOWLEDGE_PACK_SCHEMA_NAME = "NovaliWorkspaceContinuationKnowledgePack"
WORKSPACE_CONTINUATION_KNOWLEDGE_PACK_SCHEMA_VERSION = "novali_workspace_continuation_knowledge_pack_v1"
SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_NAME = "NovaliSuccessorPromotionReviewKnowledgePack"
SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_VERSION = "novali_successor_promotion_review_knowledge_pack_v1"
INTERNAL_SUCCESSOR_COMPLETION_SOURCE_ID = "internal_knowledge_pack:successor_completion_v1"
INTERNAL_WORKSPACE_CONTINUATION_SOURCE_ID = "internal_knowledge_pack:workspace_continuation_v1"
INTERNAL_SUCCESSOR_PROMOTION_REVIEW_SOURCE_ID = "internal_knowledge_pack:successor_promotion_review_v1"
CYCLE_EXECUTION_MODEL = "single_cycle_per_governed_execution_invocation"
MULTI_CYCLE_EXECUTION_MODEL = "multi_cycle_bounded_governed_execution"
STOP_REASON_COMPLETED = "completed_by_directive_stop_condition"
STOP_REASON_NO_WORK = "no_admissible_bounded_work"
STOP_REASON_BLOCKED = "blocked_by_policy"
STOP_REASON_FAILURE = "bounded_failure"
STOP_REASON_MAX_CAP = "max_cycle_cap_reached"
STOP_REASON_SINGLE_CYCLE = "single_cycle_invocation_completed"
SUCCESSOR_COMPLETION_RULE = "all_required_deliverables_present_inside_active_workspace"
REVIEW_STATUS_REQUIRED = "review_required"
PROMOTION_RECOMMENDED_STATE = "promotion_recommended"
PROMOTION_NOT_RECOMMENDED_STATE = "promotion_not_recommended"
NEXT_OBJECTIVE_AVAILABLE_STATE = "next_objective_available"
PROMOTION_DEFERRED_STATE = "promotion_deferred"
RESEED_PENDING_REVIEW_STATE = "reseed_pending_review"
RESEED_APPROVED_STATE = "reseed_approved"
RESEED_REJECTED_STATE = "reseed_rejected"
RESEED_DEFERRED_STATE = "reseed_deferred"
RESEED_MATERIALIZED_STATE = "reseed_materialized"
AUTO_CONTINUE_REASON_DISABLED = "auto_continue_not_enabled"
AUTO_CONTINUE_REASON_NOT_WHITELISTED = "objective_class_not_whitelisted"
AUTO_CONTINUE_REASON_REVIEW_REQUIRED = "operator_review_required"
AUTO_CONTINUE_REASON_MAX_CHAIN_REACHED = "max_auto_continue_chain_reached"
AUTO_CONTINUE_REASON_INCOMPATIBLE_POLICY = "incompatible_runtime_policy"
AUTO_CONTINUE_REASON_EXECUTED = "auto_continue_executed"
AUTO_CONTINUE_REASON_NO_PROPOSAL = "no_proposed_next_objective"
AUTO_CONTINUE_ORIGIN_MANUAL = "manual_approval"
AUTO_CONTINUE_ORIGIN_POLICY = "policy_auto_continue"
OBJECTIVE_SOURCE_DIRECTIVE = "directive_objective"
OBJECTIVE_SOURCE_APPROVED_RESEED = "approved_reseed_objective"
SUPPORTED_FIRST_WORK_ACTION_CLASSES = {
    "low_risk_shell_change",
    "diagnostic_schema_materialization",
    "append_only_ledger_write",
}
WORKSPACE_ARTIFACT_CATEGORIES = ("plans", "docs", "src", "tests", "artifacts")
AUTO_CONTINUE_OBJECTIVE_CLASSES = (
    "review_and_expand_workspace_local_implementation",
    "strengthen_successor_test_coverage",
    "improve_successor_package_readiness",
    "refine_operator_observability_bundle",
    "prepare_candidate_promotion_bundle",
)


class GovernedExecutionFailure(RuntimeError):
    def __init__(self, message: str, *, session_artifact_path: str = "", summary_artifact_path: str = "") -> None:
        self.session_artifact_path = str(session_artifact_path)
        self.summary_artifact_path = str(summary_artifact_path)
        super().__init__(message)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def session_artifact_path(workspace_root: str | Path) -> Path:
    return Path(workspace_root) / "artifacts" / "governed_execution_session_latest.json"


def load_session_summary(workspace_root: str | Path | None) -> dict[str, Any]:
    if not workspace_root:
        return {}
    return load_json(session_artifact_path(workspace_root))


def controller_artifact_path(workspace_root: str | Path) -> Path:
    return Path(workspace_root) / "artifacts" / "governed_execution_controller_latest.json"


def load_controller_summary(workspace_root: str | Path | None) -> dict[str, Any]:
    if not workspace_root:
        return {}
    return load_json(controller_artifact_path(workspace_root))


def _append_event(log_path: Path, payload: dict[str, Any]) -> None:
    if str(log_path) in {"", "."}:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _event(
    log_path: Path,
    *,
    event_type: str,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    workspace_root: str,
    **extra: Any,
) -> None:
    _append_event(
        log_path,
        {
            "event_type": event_type,
            "timestamp": _now(),
            "session_id": session_id,
            "directive_id": directive_id,
            "execution_profile": execution_profile,
            "workspace_id": workspace_id,
            "workspace_root": workspace_root,
            **dict(extra),
        },
    )


def _write_text(
    path: Path,
    text: str,
    *,
    log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    workspace_root: str,
    work_item_id: str,
    artifact_kind: str,
) -> None:
    _event(
        log_path,
        event_type="file_write_planned",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=workspace_root,
        work_item_id=work_item_id,
        artifact_kind=artifact_kind,
        path=str(path),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _event(
        log_path,
        event_type="file_write_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=workspace_root,
        work_item_id=work_item_id,
        artifact_kind=artifact_kind,
        path=str(path),
        bytes_written=len(text.encode("utf-8")),
    )


def _write_json(path: Path, payload: dict[str, Any], **kwargs: Any) -> None:
    _write_text(path, _dump(payload), **kwargs)


def _relative_to_workspace(workspace_root: Path, path: Path) -> str:
    return path.relative_to(workspace_root).as_posix()


def _is_under_path(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _classify_workspace_artifact(relative_path: str) -> str:
    parts = [part for part in Path(relative_path).parts if part not in {"."}]
    if not parts:
        return "other"
    root = parts[0]
    return root if root in WORKSPACE_ARTIFACT_CATEGORIES else "other"


def _build_workspace_artifact_index_payload(workspace_root: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}
    for path in sorted(workspace_root.rglob("*")):
        if not path.is_file():
            continue
        relative_path = _relative_to_workspace(workspace_root, path)
        category = _classify_workspace_artifact(relative_path)
        category_counts[category] = category_counts.get(category, 0) + 1
        records.append(
            {
                "relative_path": relative_path,
                "category": category,
                "size_bytes": int(path.stat().st_size),
            }
        )
    next_recommended_cycle = "materialize_workspace_local_implementation"
    has_python_source = any(
        item["category"] == "src" and str(item["relative_path"]).endswith(".py")
        for item in records
    )
    has_python_tests = any(
        item["category"] == "tests" and str(item["relative_path"]).endswith(".py")
        for item in records
    )
    has_continuation_gap_analysis = any(
        str(item["relative_path"]) == "plans/successor_continuation_gap_analysis.md"
        for item in records
    )
    has_successor_readiness_bundle = all(
        any(str(item["relative_path"]) == relative_path for item in records)
        for relative_path in (
            "src/successor_shell/successor_manifest.py",
            "tests/test_successor_manifest.py",
            "docs/successor_package_readiness_note.md",
            "artifacts/successor_readiness_evaluation_latest.json",
            "artifacts/successor_delivery_manifest_latest.json",
        )
    )
    if has_successor_readiness_bundle:
        next_recommended_cycle = "operator_review_required"
    elif has_continuation_gap_analysis:
        next_recommended_cycle = "materialize_successor_package_readiness_bundle"
    elif has_python_source and has_python_tests:
        next_recommended_cycle = "plan_successor_package_gap_closure"
    elif has_python_source:
        next_recommended_cycle = "add_workspace_local_tests"
    return {
        "schema_name": WORKSPACE_ARTIFACT_INDEX_SCHEMA_NAME,
        "schema_version": WORKSPACE_ARTIFACT_INDEX_SCHEMA_VERSION,
        "generated_at": _now(),
        "workspace_root": str(workspace_root),
        "artifact_count": len(records),
        "category_counts": category_counts,
        "artifacts": records,
        "next_recommended_cycle": next_recommended_cycle,
    }


def _workspace_paths(workspace_root: Path) -> dict[str, Path]:
    return {
        "docs_root": workspace_root / "docs",
        "src_root": workspace_root / "src",
        "tests_root": workspace_root / "tests",
        "artifacts_root": workspace_root / "artifacts",
        "cycles_root": workspace_root / "artifacts" / "cycles",
        "plans_root": workspace_root / "plans",
        "plan_path": workspace_root / "plans" / "bounded_work_cycle_plan.md",
        "design_path": workspace_root / "docs" / "mutable_shell_successor_design_note.md",
        "src_readme_path": workspace_root / "src" / "README.md",
        "tests_readme_path": workspace_root / "tests" / "README.md",
        "file_plan_path": workspace_root / "artifacts" / "bounded_work_file_plan.json",
        "summary_path": workspace_root / "artifacts" / "bounded_work_summary_latest.json",
        "implementation_summary_path": workspace_root / "artifacts" / "implementation_bundle_summary_latest.json",
        "workspace_artifact_index_path": workspace_root / "artifacts" / "workspace_artifact_index_latest.json",
        "controller_summary_path": workspace_root / "artifacts" / "governed_execution_controller_latest.json",
        "trusted_planning_evidence_path": workspace_root / "artifacts" / "trusted_planning_evidence_latest.json",
        "missing_deliverables_path": workspace_root / "artifacts" / "missing_deliverables_latest.json",
        "next_step_derivation_path": workspace_root / "artifacts" / "next_step_derivation_latest.json",
        "completion_evaluation_path": workspace_root / "artifacts" / "completion_evaluation_latest.json",
        "review_summary_path": workspace_root / "artifacts" / "successor_review_summary_latest.json",
        "promotion_recommendation_path": workspace_root / "artifacts" / "successor_promotion_recommendation_latest.json",
        "next_objective_proposal_path": workspace_root / "artifacts" / "successor_next_objective_proposal_latest.json",
        "reseed_request_path": workspace_root / "artifacts" / "successor_reseed_request_latest.json",
        "reseed_decision_path": workspace_root / "artifacts" / "successor_reseed_decision_latest.json",
        "continuation_lineage_path": workspace_root / "artifacts" / "successor_continuation_lineage_latest.json",
        "effective_next_objective_path": workspace_root / "artifacts" / "successor_effective_next_objective_latest.json",
        "auto_continue_state_path": workspace_root / "artifacts" / "successor_auto_continue_state_latest.json",
        "auto_continue_decision_path": workspace_root / "artifacts" / "successor_auto_continue_decision_latest.json",
        "implementation_note_path": workspace_root / "docs" / "successor_shell_iteration_notes.md",
        "continuation_gap_plan_path": workspace_root / "plans" / "successor_continuation_gap_analysis.md",
        "readiness_note_path": workspace_root / "docs" / "successor_package_readiness_note.md",
        "promotion_bundle_note_path": workspace_root / "docs" / "successor_promotion_bundle_note.md",
        "implementation_package_root": workspace_root / "src" / "successor_shell",
        "implementation_init_path": workspace_root / "src" / "successor_shell" / "__init__.py",
        "implementation_module_path": workspace_root / "src" / "successor_shell" / "workspace_contract.py",
        "readiness_module_path": workspace_root / "src" / "successor_shell" / "successor_manifest.py",
        "implementation_test_path": workspace_root / "tests" / "test_workspace_contract.py",
        "readiness_test_path": workspace_root / "tests" / "test_successor_manifest.py",
        "readiness_summary_path": workspace_root / "artifacts" / "successor_readiness_evaluation_latest.json",
        "delivery_manifest_path": workspace_root / "artifacts" / "successor_delivery_manifest_latest.json",
        "promotion_bundle_manifest_path": workspace_root / "artifacts" / "successor_candidate_promotion_bundle_latest.json",
    }


def successor_auto_continue_policy_path(root: str | Path | None) -> Path:
    base = Path(root) if root is not None else Path(
        os.environ.get(OPERATOR_POLICY_ROOT_ENV, "").strip() or Path.cwd()
    )
    return base / "successor_auto_continue_policy_latest.json"


def _objective_class_from_objective_id(objective_id: str) -> str:
    token = str(objective_id or "").strip()
    return token if token in AUTO_CONTINUE_OBJECTIVE_CLASSES else token


def _unique_string_list(items: list[Any]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for item in items:
        token = str(item or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        values.append(token)
    return values


def _split_objective_classes(value: Any) -> list[str]:
    raw = str(value or "").replace("\r", "\n").replace(",", "\n").replace(";", "\n")
    tokens = []
    seen: set[str] = set()
    for item in raw.splitlines():
        token = str(item or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def build_default_successor_auto_continue_policy() -> dict[str, Any]:
    return {
        "schema_name": SUCCESSOR_AUTO_CONTINUE_POLICY_SCHEMA_NAME,
        "schema_version": SUCCESSOR_AUTO_CONTINUE_POLICY_SCHEMA_VERSION,
        "generated_at": _now(),
        "enabled": False,
        "allowed_objective_classes": [],
        "available_objective_classes": list(AUTO_CONTINUE_OBJECTIVE_CLASSES),
        "max_auto_continue_chain_length": 1,
        "require_manual_approval_for_first_entry": True,
        "require_review_supported_proposals": True,
        "policy_scope": "approved_bounded_next_objective_classes_only",
    }


def _sanitize_successor_auto_continue_policy(payload: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(payload.get("enabled", False))
    if isinstance(payload.get("enabled"), str):
        enabled = str(payload.get("enabled", "")).strip().lower() in {"1", "true", "yes", "on", "enabled"}
    allowed_classes = [
        item
        for item in _split_objective_classes(payload.get("allowed_objective_classes", ""))
        if item in AUTO_CONTINUE_OBJECTIVE_CLASSES
    ]
    if isinstance(payload.get("allowed_objective_classes"), list):
        allowed_classes = [
            str(item).strip()
            for item in list(payload.get("allowed_objective_classes", []))
            if str(item).strip() in AUTO_CONTINUE_OBJECTIVE_CLASSES
        ]
    max_chain = int(payload.get("max_auto_continue_chain_length", 1) or 1)
    if max_chain < 1:
        max_chain = 1
    require_first_entry = bool(payload.get("require_manual_approval_for_first_entry", True))
    if isinstance(payload.get("require_manual_approval_for_first_entry"), str):
        require_first_entry = str(payload.get("require_manual_approval_for_first_entry", "")).strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
            "disabled",
        }
    require_review_supported = bool(payload.get("require_review_supported_proposals", True))
    if isinstance(payload.get("require_review_supported_proposals"), str):
        require_review_supported = str(payload.get("require_review_supported_proposals", "")).strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
            "disabled",
        }
    return {
        "schema_name": SUCCESSOR_AUTO_CONTINUE_POLICY_SCHEMA_NAME,
        "schema_version": SUCCESSOR_AUTO_CONTINUE_POLICY_SCHEMA_VERSION,
        "generated_at": _now(),
        "enabled": enabled,
        "allowed_objective_classes": allowed_classes,
        "available_objective_classes": list(AUTO_CONTINUE_OBJECTIVE_CLASSES),
        "max_auto_continue_chain_length": max_chain,
        "require_manual_approval_for_first_entry": require_first_entry,
        "require_review_supported_proposals": require_review_supported,
        "policy_scope": "approved_bounded_next_objective_classes_only",
    }


def load_successor_auto_continue_policy(root: str | Path | None) -> dict[str, Any]:
    path = successor_auto_continue_policy_path(root)
    payload = load_json(path)
    if not payload:
        return build_default_successor_auto_continue_policy()
    return _sanitize_successor_auto_continue_policy(payload)


def save_successor_auto_continue_policy(payload: dict[str, Any], *, root: str | Path | None) -> dict[str, Any]:
    cleaned = _sanitize_successor_auto_continue_policy(payload)
    path = successor_auto_continue_policy_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump(cleaned), encoding="utf-8")
    return cleaned


def load_successor_auto_continue_state(workspace_root: str | Path | None) -> dict[str, Any]:
    if not workspace_root:
        return {}
    return load_json(_workspace_paths(Path(workspace_root))["auto_continue_state_path"])


def load_successor_auto_continue_decision(workspace_root: str | Path | None) -> dict[str, Any]:
    if not workspace_root:
        return {}
    return load_json(_workspace_paths(Path(workspace_root))["auto_continue_decision_path"])


def _write_successor_auto_continue_state_and_decision(
    *,
    workspace_root: Path,
    operator_root: str | Path | None,
    review_summary: dict[str, Any],
    promotion_recommendation: dict[str, Any],
    next_objective_proposal: dict[str, Any],
    reseed_request_path: str,
    reseed_decision_path: str,
    continuation_lineage_path: str,
    effective_next_objective_path: str,
    continuation_authorized: bool,
    decision_reason: str,
    decision_actor: str,
    authorization_origin: str,
    operator_decision: str,
    effective_objective_id: str,
    effective_objective_title: str,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    policy_path = successor_auto_continue_policy_path(operator_root)
    policy_payload = load_successor_auto_continue_policy(operator_root)
    prior_state = load_successor_auto_continue_state(workspace_root)
    proposed_objective_id = str(next_objective_proposal.get("objective_id", "")).strip()
    proposed_objective_class = _objective_class_from_objective_id(proposed_objective_id)
    effective_objective_class = _objective_class_from_objective_id(effective_objective_id)
    prior_manual_classes = _unique_string_list(
        list(prior_state.get("manually_approved_objective_classes", []))
    )
    current_chain_count = int(prior_state.get("current_chain_count", 0) or 0)
    if authorization_origin == AUTO_CONTINUE_ORIGIN_POLICY and continuation_authorized:
        current_chain_count += 1
    elif operator_decision in {"approve", "reject", "defer"}:
        current_chain_count = 0

    manual_classes = list(prior_manual_classes)
    if operator_decision == "approve" and proposed_objective_class:
        manual_classes = _unique_string_list(manual_classes + [proposed_objective_class])

    state_payload = {
        "schema_name": SUCCESSOR_AUTO_CONTINUE_STATE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_AUTO_CONTINUE_STATE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(review_summary.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "policy_path": str(policy_path),
        "enabled": bool(policy_payload.get("enabled", False)),
        "allowed_objective_classes": list(policy_payload.get("allowed_objective_classes", [])),
        "available_objective_classes": list(policy_payload.get("available_objective_classes", [])),
        "max_auto_continue_chain_length": int(
            policy_payload.get("max_auto_continue_chain_length", 1) or 1
        ),
        "require_manual_approval_for_first_entry": bool(
            policy_payload.get("require_manual_approval_for_first_entry", True)
        ),
        "require_review_supported_proposals": bool(
            policy_payload.get("require_review_supported_proposals", True)
        ),
        "current_chain_count": int(current_chain_count),
        "manually_approved_objective_classes": manual_classes,
        "last_decision_reason": decision_reason,
        "last_decision_actor": decision_actor,
        "last_continuation_origin": authorization_origin,
        "last_operator_decision": operator_decision,
        "last_completed_objective_id": str(review_summary.get("completed_objective_id", "")),
        "last_completed_objective_source_kind": str(
            review_summary.get("completed_objective_source_kind", "")
        ),
        "last_proposed_objective_id": proposed_objective_id,
        "last_proposed_objective_class": proposed_objective_class,
        "last_effective_objective_id": effective_objective_id,
        "last_effective_objective_class": effective_objective_class,
        "continuation_authorized": continuation_authorized,
        "auto_continue_executed": authorization_origin == AUTO_CONTINUE_ORIGIN_POLICY
        and continuation_authorized,
        "review_summary_path": str(paths["review_summary_path"]),
        "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
        "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
        "reseed_request_path": str(reseed_request_path),
        "reseed_decision_path": str(reseed_decision_path),
        "continuation_lineage_path": str(continuation_lineage_path),
        "effective_next_objective_path": str(effective_next_objective_path),
    }
    decision_payload = {
        "schema_name": SUCCESSOR_AUTO_CONTINUE_DECISION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_AUTO_CONTINUE_DECISION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(review_summary.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "policy_path": str(policy_path),
        "enabled": bool(policy_payload.get("enabled", False)),
        "allowed_objective_classes": list(policy_payload.get("allowed_objective_classes", [])),
        "max_auto_continue_chain_length": int(
            policy_payload.get("max_auto_continue_chain_length", 1) or 1
        ),
        "require_manual_approval_for_first_entry": bool(
            policy_payload.get("require_manual_approval_for_first_entry", True)
        ),
        "require_review_supported_proposals": bool(
            policy_payload.get("require_review_supported_proposals", True)
        ),
        "decision_reason": decision_reason,
        "decision_actor": decision_actor,
        "authorization_origin": authorization_origin,
        "operator_decision": operator_decision,
        "continuation_authorized": continuation_authorized,
        "current_chain_count": int(current_chain_count),
        "completed_objective_id": str(review_summary.get("completed_objective_id", "")),
        "completed_objective_source_kind": str(
            review_summary.get("completed_objective_source_kind", "")
        ),
        "promotion_recommendation_state": str(
            promotion_recommendation.get("promotion_recommendation_state", "")
        ),
        "review_status": str(review_summary.get("review_status", "")),
        "proposed_objective_id": proposed_objective_id,
        "proposed_objective_class": proposed_objective_class,
        "effective_objective_id": effective_objective_id,
        "effective_objective_class": effective_objective_class,
        "effective_objective_title": effective_objective_title,
        "review_summary_path": str(paths["review_summary_path"]),
        "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
        "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
        "reseed_request_path": str(reseed_request_path),
        "reseed_decision_path": str(reseed_decision_path),
        "continuation_lineage_path": str(continuation_lineage_path),
        "effective_next_objective_path": str(effective_next_objective_path),
    }
    paths["auto_continue_state_path"].parent.mkdir(parents=True, exist_ok=True)
    paths["auto_continue_state_path"].write_text(_dump(state_payload), encoding="utf-8")
    paths["auto_continue_decision_path"].write_text(_dump(decision_payload), encoding="utf-8")
    return {
        "state": state_payload,
        "decision": decision_payload,
        "state_path": str(paths["auto_continue_state_path"]),
        "decision_path": str(paths["auto_continue_decision_path"]),
        "policy_path": str(policy_path),
    }


def _evaluate_successor_auto_continue(
    *,
    workspace_root: Path,
    session: dict[str, Any],
    execution_profile: str,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    stop_reason: str,
    review_outputs: dict[str, Any],
    reseed_outputs: dict[str, Any],
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    review_summary = dict(review_outputs.get("review_summary", {}))
    promotion_recommendation = dict(review_outputs.get("promotion_recommendation", {}))
    next_objective_proposal = dict(review_outputs.get("next_objective_proposal", {}))
    operator_root = _operator_root_from_session(session)
    policy_payload = load_successor_auto_continue_policy(operator_root)
    proposed_objective_id = str(next_objective_proposal.get("objective_id", "")).strip()
    proposed_objective_class = _objective_class_from_objective_id(proposed_objective_id)
    prior_state = load_successor_auto_continue_state(workspace_root)
    prior_chain_count = int(prior_state.get("current_chain_count", 0) or 0)
    manual_classes = _unique_string_list(
        list(prior_state.get("manually_approved_objective_classes", []))
    )

    decision_reason = AUTO_CONTINUE_REASON_DISABLED
    continuation_authorized = False
    authorization_origin = ""
    materialized_outputs = dict(reseed_outputs)

    if stop_reason != STOP_REASON_COMPLETED:
        decision_reason = AUTO_CONTINUE_REASON_REVIEW_REQUIRED
    elif not proposed_objective_id:
        decision_reason = AUTO_CONTINUE_REASON_NO_PROPOSAL
    elif not bool(policy_payload.get("enabled", False)):
        decision_reason = AUTO_CONTINUE_REASON_DISABLED
    elif execution_profile != "bounded_active_workspace_coding" or not str(workspace_root).strip():
        decision_reason = AUTO_CONTINUE_REASON_INCOMPATIBLE_POLICY
    elif bool(review_summary.get("operator_review_required", False)) and bool(
        policy_payload.get("require_review_supported_proposals", True)
    ) and not str(promotion_recommendation.get("promotion_recommendation_state", "")).strip():
        decision_reason = AUTO_CONTINUE_REASON_REVIEW_REQUIRED
    elif proposed_objective_class not in list(policy_payload.get("allowed_objective_classes", [])):
        decision_reason = AUTO_CONTINUE_REASON_NOT_WHITELISTED
    elif bool(policy_payload.get("require_manual_approval_for_first_entry", True)) and (
        proposed_objective_class not in manual_classes
    ):
        decision_reason = AUTO_CONTINUE_REASON_REVIEW_REQUIRED
    elif prior_chain_count >= int(policy_payload.get("max_auto_continue_chain_length", 1) or 1):
        decision_reason = AUTO_CONTINUE_REASON_MAX_CHAIN_REACHED
    else:
        materialized_outputs = materialize_successor_reseed_decision(
            workspace_root=workspace_root,
            operator_decision="auto_continue",
            actor="successor_auto_continue_policy",
            operator_root=operator_root,
        )
        decision_reason = AUTO_CONTINUE_REASON_EXECUTED
        continuation_authorized = True
        authorization_origin = AUTO_CONTINUE_ORIGIN_POLICY

    state_outputs = _write_successor_auto_continue_state_and_decision(
        workspace_root=workspace_root,
        operator_root=operator_root,
        review_summary=review_summary,
        promotion_recommendation=promotion_recommendation,
        next_objective_proposal=next_objective_proposal,
        reseed_request_path=str(materialized_outputs.get("reseed_request_path", "")),
        reseed_decision_path=str(materialized_outputs.get("reseed_decision_path", "")),
        continuation_lineage_path=str(materialized_outputs.get("continuation_lineage_path", "")),
        effective_next_objective_path=str(
            materialized_outputs.get("effective_next_objective_path", "")
        ),
        continuation_authorized=continuation_authorized,
        decision_reason=decision_reason,
        decision_actor="successor_auto_continue_policy",
        authorization_origin=authorization_origin,
        operator_decision="auto_continue" if continuation_authorized else "no_auto_continue",
        effective_objective_id=str(
            dict(materialized_outputs.get("effective_next_objective", {})).get("objective_id", "")
        ).strip(),
        effective_objective_title=str(
            dict(materialized_outputs.get("effective_next_objective", {})).get("title", "")
        ).strip(),
    )

    if str(runtime_event_log_path):
        _event(
            runtime_event_log_path,
            event_type="successor_auto_continue_evaluated",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=str(workspace_root.name),
            workspace_root=str(workspace_root),
            auto_continue_reason=decision_reason,
            proposed_objective_id=proposed_objective_id,
            objective_class=proposed_objective_class,
            continuation_authorized=continuation_authorized,
            authorization_origin=authorization_origin,
            auto_continue_chain_count=int(
                dict(state_outputs.get("state", {})).get("current_chain_count", 0) or 0
            ),
            max_auto_continue_chain_length=int(
                policy_payload.get("max_auto_continue_chain_length", 1) or 1
            ),
            auto_continue_policy_path=str(state_outputs.get("policy_path", "")),
            auto_continue_state_path=str(state_outputs.get("state_path", "")),
            auto_continue_decision_path=str(state_outputs.get("decision_path", "")),
        )
    return {
        "reason": decision_reason,
        "continuation_authorized": continuation_authorized,
        "authorization_origin": authorization_origin,
        "reseed_outputs": materialized_outputs,
        "policy": policy_payload,
        "state": dict(state_outputs.get("state", {})),
        "decision": dict(state_outputs.get("decision", {})),
        "policy_path": str(state_outputs.get("policy_path", "")),
        "state_path": str(state_outputs.get("state_path", "")),
        "decision_path": str(state_outputs.get("decision_path", "")),
    }


def _workspace_baseline(workspace_root: Path) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    baseline_paths = [
        paths["plan_path"],
        paths["design_path"],
        paths["file_plan_path"],
        paths["summary_path"],
        paths["src_readme_path"],
        paths["tests_readme_path"],
    ]
    planning_summary = load_json(paths["summary_path"])
    return {
        **paths,
        "baseline_artifact_paths": [str(path) for path in baseline_paths if path.exists()],
        "has_planning_baseline": all(path.exists() for path in baseline_paths),
        "planning_summary": planning_summary,
        "implementation_materialized": all(
            path.exists()
            for path in (
                paths["implementation_init_path"],
                paths["implementation_module_path"],
                paths["implementation_test_path"],
                paths["implementation_note_path"],
                paths["implementation_summary_path"],
            )
        ),
        "continuation_gap_materialized": all(
            path.exists()
            for path in (
                paths["continuation_gap_plan_path"],
                paths["trusted_planning_evidence_path"],
                paths["missing_deliverables_path"],
                paths["next_step_derivation_path"],
                paths["completion_evaluation_path"],
            )
        ),
        "readiness_materialized": all(
            path.exists()
            for path in (
                paths["readiness_module_path"],
                paths["readiness_test_path"],
                paths["readiness_note_path"],
                paths["readiness_summary_path"],
                paths["delivery_manifest_path"],
            )
        ),
        "review_materialized": all(
            path.exists()
            for path in (
                paths["review_summary_path"],
                paths["promotion_recommendation_path"],
                paths["next_objective_proposal_path"],
            )
        ),
        "reseed_materialized": all(
            path.exists()
            for path in (
                paths["reseed_request_path"],
                paths["reseed_decision_path"],
                paths["continuation_lineage_path"],
                paths["effective_next_objective_path"],
            )
        ),
        "promotion_bundle_materialized": all(
            path.exists()
            for path in (
                paths["promotion_bundle_note_path"],
                paths["promotion_bundle_manifest_path"],
            )
        ),
    }


def _directive_text_blob(current_directive: dict[str, Any]) -> str:
    return " ".join(
        [
            str(current_directive.get("directive_text", "")).strip(),
            str(current_directive.get("clarified_intent_summary", "")).strip(),
            *[str(item).strip() for item in list(current_directive.get("constraints", []))],
            *[str(item).strip() for item in list(current_directive.get("success_criteria", []))],
            *[str(item).strip() for item in list(current_directive.get("trusted_sources", []))],
        ]
    ).lower()


def _package_root_from_session(session: dict[str, Any]) -> Path:
    package_root = str(session.get("package_root", "")).strip()
    if package_root:
        return Path(package_root)
    return Path(__file__).resolve().parents[1]


def _operator_root_from_session(session: dict[str, Any]) -> Path:
    operator_root = str(session.get("operator_policy_root", "")).strip()
    if operator_root:
        return Path(operator_root)
    env_root = str(os.environ.get(OPERATOR_POLICY_ROOT_ENV, "")).strip()
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parents[1] / "operator_state"


def _knowledge_pack_fallback_path(package_root: Path, source_id: str) -> Path:
    knowledge_pack_root = package_root / "trusted_sources" / "knowledge_packs"
    if source_id == INTERNAL_SUCCESSOR_COMPLETION_SOURCE_ID:
        return knowledge_pack_root / "successor_completion_knowledge_pack_v1.json"
    if source_id == INTERNAL_WORKSPACE_CONTINUATION_SOURCE_ID:
        return knowledge_pack_root / "workspace_continuation_knowledge_pack_v1.json"
    if source_id == INTERNAL_SUCCESSOR_PROMOTION_REVIEW_SOURCE_ID:
        return knowledge_pack_root / "successor_promotion_review_knowledge_pack_v1.json"
    return knowledge_pack_root / "unknown_knowledge_pack.json"


def _session_binding_rows(session: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("source_id", "")).strip(): dict(item)
        for item in list(dict(session.get("trusted_source_bindings", {})).get("bindings", []))
        if str(item.get("source_id", "")).strip()
    }


def _session_availability_rows(session: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("source_id", "")).strip(): dict(item)
        for item in list(dict(session.get("trusted_source_availability", {})).get("sources", []))
        if str(item.get("source_id", "")).strip()
    }


def _load_internal_knowledge_pack(
    *,
    session: dict[str, Any],
    source_id: str,
    expected_schema_name: str,
    expected_schema_version: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    package_root = _package_root_from_session(session)
    bindings_by_source = _session_binding_rows(session)
    availability_by_source = _session_availability_rows(session)
    binding = dict(bindings_by_source.get(source_id, {}))
    availability = dict(availability_by_source.get(source_id, {}))
    fallback_path = _knowledge_pack_fallback_path(package_root, source_id)
    candidate_path = str(binding.get("path_hint", "")).strip()
    load_status = "missing"
    reason = "knowledge pack binding is missing from the frozen operator session"

    if candidate_path and bool(binding.get("enabled", False)) and bool(availability.get("ready_for_launch", False)):
        load_status = "loaded_from_trusted_source_binding"
        reason = str(availability.get("availability_reason", "ready")).strip() or "ready"
    elif not binding and fallback_path.exists():
        candidate_path = str(fallback_path)
        load_status = "loaded_from_packaged_fallback"
        reason = "binding missing from frozen session; packaged fallback was used conservatively"
    else:
        candidate_path = candidate_path or str(fallback_path)
        reason = str(availability.get("availability_reason", reason)).strip() or reason

    payload = load_json(Path(candidate_path)) if candidate_path else {}
    loaded = (
        str(payload.get("schema_name", "")).strip() == expected_schema_name
        and str(payload.get("schema_version", "")).strip() == expected_schema_version
    )
    if not loaded:
        if payload:
            load_status = "invalid_schema"
            reason = (
                f"expected {expected_schema_name}/{expected_schema_version} but found "
                f"{payload.get('schema_name', '<missing>')}/{payload.get('schema_version', '<missing>')}"
            )
        else:
            load_status = "missing_or_unreadable"

    return payload if loaded else {}, {
        "source_id": source_id,
        "source_kind": str(binding.get("source_kind", availability.get("source_kind", "local_bundle"))).strip()
        or "local_bundle",
        "path_hint": str(candidate_path),
        "binding_enabled": bool(binding.get("enabled", False)) if binding else False,
        "ready_for_launch": bool(availability.get("ready_for_launch", False)) if availability else bool(load_status == "loaded_from_packaged_fallback"),
        "load_status": load_status,
        "loaded": loaded,
        "reason": reason,
        "schema_name": str(payload.get("schema_name", "")) if loaded else "",
        "schema_version": str(payload.get("schema_version", "")) if loaded else "",
        "pack_id": str(payload.get("pack_id", "")) if loaded else "",
    }


def _relative_path_status(workspace_root: Path, relative_path: str) -> dict[str, Any]:
    absolute_path = workspace_root / Path(relative_path)
    return {
        "relative_path": relative_path,
        "absolute_path": str(absolute_path),
        "present": absolute_path.exists(),
    }


def _evaluate_successor_completion(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    completion_pack: dict[str, Any],
) -> dict[str, Any]:
    directive_blob = _directive_text_blob(current_directive)
    deliverable_checks: list[dict[str, Any]] = []
    completed_by_id: dict[str, bool] = {}

    for deliverable in list(completion_pack.get("deliverables", [])):
        row = dict(deliverable)
        deliverable_id = str(row.get("deliverable_id", "")).strip()
        if not deliverable_id:
            continue
        required_tokens = [str(item).strip().lower() for item in list(row.get("required_when_tokens_any", [])) if str(item).strip()]
        required = bool(row.get("required", False))
        if required_tokens:
            required = any(token in directive_blob for token in required_tokens)
        evidence_rows = [
            _relative_path_status(workspace_root, str(item))
            for item in list(row.get("evidence_relative_paths", []))
            if str(item).strip()
        ]
        evidence_paths_present = [item for item in evidence_rows if bool(item.get("present", False))]
        completed = bool(not required or all(item["present"] for item in evidence_rows))
        completed_by_id[deliverable_id] = completed
        deliverable_checks.append(
            {
                "deliverable_id": deliverable_id,
                "title": str(row.get("title", deliverable_id)),
                "required": required,
                "completed": completed,
                "missing_evidence_relative_paths": [
                    str(item.get("relative_path", ""))
                    for item in evidence_rows
                    if not bool(item.get("present", False))
                ],
                "evidence_paths_present": [str(item.get("absolute_path", "")) for item in evidence_paths_present],
                "evidence_rows": evidence_rows,
            }
        )

    missing_required = [item for item in deliverable_checks if bool(item.get("required", False)) and not bool(item.get("completed", False))]
    completed = len(missing_required) == 0 and bool(deliverable_checks)
    partial_states: list[str] = []
    if completed_by_id.get("planning_bundle") and not completed_by_id.get("implementation_bundle"):
        partial_states.append("planning_bundle_only")
    if completed_by_id.get("implementation_bundle") and not completed_by_id.get("continuation_gap_analysis"):
        partial_states.append("first_implementation_bundle_only")
    if completed_by_id.get("continuation_gap_analysis") and not completed_by_id.get("successor_readiness_bundle"):
        partial_states.append("ready_for_readiness_bundle")

    reason = (
        "required bounded successor deliverables are present inside the active workspace"
        if completed
        else "bounded successor deliverables remain incomplete inside the active workspace"
    )
    return {
        "schema_name": COMPLETION_EVALUATION_SCHEMA_NAME,
        "schema_version": COMPLETION_EVALUATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "completion_pack_id": str(completion_pack.get("pack_id", "")),
        "completion_rule": str(completion_pack.get("completion_rule", SUCCESSOR_COMPLETION_RULE)),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_root": str(workspace_root),
        "completed": completed,
        "reason": reason,
        "partial_completion_states": partial_states,
        "required_deliverable_count": sum(1 for item in deliverable_checks if bool(item.get("required", False))),
        "missing_required_deliverables": [
            {
                "deliverable_id": str(item.get("deliverable_id", "")),
                "title": str(item.get("title", "")),
                "missing_evidence_relative_paths": list(item.get("missing_evidence_relative_paths", [])),
            }
            for item in missing_required
        ],
        "deliverable_checks": deliverable_checks,
        "recommended_stop": completed,
    }


def _humanize_objective_id(objective_id: str) -> str:
    token = str(objective_id or "").strip().replace("_", " ")
    return token[:1].upper() + token[1:] if token else ""


def _objective_template_rows(review_pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("objective_id", "")).strip(): dict(item)
        for item in list(review_pack.get("objective_templates", []))
        if str(item.get("objective_id", "")).strip()
    }


def _collect_cycle_output_paths(cycle_rows: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in cycle_rows:
        for field_name in ("output_artifact_paths", "newly_created_paths"):
            for item in list(row.get(field_name, [])):
                candidate = str(item).strip()
                if not candidate or candidate in seen:
                    continue
                seen.add(candidate)
                ordered.append(candidate)
    return ordered


def _cycle_history_summary(cycle_rows: list[dict[str, Any]]) -> dict[str, Any]:
    cycle_kind_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for row in cycle_rows:
        cycle_kind = str(row.get("cycle_kind", "")).strip() or "unknown"
        status = str(row.get("status", "")).strip() or "unknown"
        cycle_kind_counts[cycle_kind] = cycle_kind_counts.get(cycle_kind, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "cycle_count": len(cycle_rows),
        "cycle_kind_counts": cycle_kind_counts,
        "status_counts": status_counts,
        "latest_cycle_index": int(cycle_rows[-1].get("cycle_index", 0)) if cycle_rows else 0,
        "latest_cycle_kind": str(cycle_rows[-1].get("cycle_kind", "")) if cycle_rows else "",
    }


def load_successor_effective_next_objective(workspace_root: str | Path | None) -> dict[str, Any]:
    if not workspace_root:
        return {}
    return load_json(_workspace_paths(Path(workspace_root))["effective_next_objective_path"])


def _active_effective_next_objective(workspace_root: Path) -> dict[str, Any]:
    payload = load_successor_effective_next_objective(workspace_root)
    if not payload:
        return {}
    reseed_state = str(payload.get("reseed_state", "")).strip()
    execution_state = str(payload.get("execution_state", "")).strip().lower()
    if not bool(payload.get("continuation_authorized", False)):
        return {}
    if reseed_state not in {RESEED_APPROVED_STATE, RESEED_MATERIALIZED_STATE}:
        return {}
    if execution_state in {"completed", "rejected", "deferred", "superseded"}:
        return {}
    if not str(payload.get("objective_id", "")).strip():
        return {}
    return payload


def _current_objective_context(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
) -> dict[str, Any]:
    active_objective = _active_effective_next_objective(workspace_root)
    if active_objective:
        objective_id = str(active_objective.get("objective_id", "")).strip()
        return {
            "source_kind": OBJECTIVE_SOURCE_APPROVED_RESEED,
            "objective_id": objective_id,
            "objective_class": _objective_class_from_objective_id(objective_id),
            "title": str(active_objective.get("title", "")).strip() or _humanize_objective_id(objective_id),
            "rationale": str(active_objective.get("rationale", "")).strip(),
            "authorization_origin": str(active_objective.get("authorization_origin", "")).strip(),
            "approved_from_request_path": str(active_objective.get("reseed_request_path", "")).strip(),
            "approved_from_decision_path": str(active_objective.get("reseed_decision_path", "")).strip(),
            "approved_from_lineage_path": str(active_objective.get("continuation_lineage_path", "")).strip(),
            "effective_next_objective_path": str(
                _workspace_paths(workspace_root)["effective_next_objective_path"]
            ),
            "payload": active_objective,
        }
    objective_id = str(current_directive.get("directive_id", "")).strip()
    title = (
        str(current_directive.get("clarified_intent_summary", "")).strip()
        or str(current_directive.get("directive_text", "")).strip()
        or _humanize_objective_id(objective_id)
    )
    return {
        "source_kind": OBJECTIVE_SOURCE_DIRECTIVE,
        "objective_id": objective_id,
        "objective_class": _objective_class_from_objective_id(objective_id),
        "title": title,
        "rationale": "Using the original directive as the current bounded objective context.",
        "authorization_origin": "",
        "approved_from_request_path": "",
        "approved_from_decision_path": "",
        "approved_from_lineage_path": "",
        "effective_next_objective_path": "",
        "payload": {},
    }


def _effective_objective_stage(objective_id: str) -> dict[str, Any]:
    objective = str(objective_id or "").strip()
    if objective == "prepare_candidate_promotion_bundle":
        return {
            "stage_id": "candidate_promotion_bundle",
            "cycle_kind": "planning_only",
            "next_recommended_cycle": "operator_review_required",
            "title": "Materialize the candidate promotion bundle for operator review.",
            "work_item_id": "successor_candidate_promotion_bundle",
            "rationale": "The operator approved a bounded promotion-bundle objective derived from the prior completed successor package.",
        }
    stage_map = {
        "materialize_workspace_local_implementation": "first_implementation_bundle",
        "review_and_expand_workspace_local_implementation": "first_implementation_bundle",
        "strengthen_successor_test_coverage": "successor_readiness_bundle",
        "improve_successor_package_readiness": "successor_readiness_bundle",
        "materialize_successor_package_readiness_bundle": "successor_readiness_bundle",
        "plan_successor_package_gap_closure": "continuation_gap_analysis",
    }
    stage_id = str(stage_map.get(objective, "")).strip()
    if not stage_id:
        return {}
    cycle_kind = "planning_only" if stage_id in {"initial_planning_bundle", "continuation_gap_analysis"} else "implementation_bearing"
    return {
        "stage_id": stage_id,
        "cycle_kind": cycle_kind,
        "next_recommended_cycle": objective,
        "title": _humanize_objective_id(objective),
        "work_item_id": objective,
        "rationale": "The operator approved this bounded next objective from the prior review artifacts.",
    }


def _evaluate_current_objective_completion(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    completion_pack: dict[str, Any],
) -> dict[str, Any]:
    objective_context = _current_objective_context(
        current_directive=current_directive,
        workspace_root=workspace_root,
    )
    base_evaluation = _evaluate_successor_completion(
        current_directive=current_directive,
        workspace_root=workspace_root,
        completion_pack=completion_pack,
    )
    if objective_context["source_kind"] != OBJECTIVE_SOURCE_APPROVED_RESEED:
        return {
            **base_evaluation,
            "current_objective": objective_context,
        }

    objective_id = str(objective_context.get("objective_id", "")).strip()
    paths = _workspace_paths(workspace_root)
    if objective_id == "prepare_candidate_promotion_bundle":
        evidence_rows = [
            _relative_path_status(workspace_root, "docs/successor_promotion_bundle_note.md"),
            _relative_path_status(
                workspace_root,
                "artifacts/successor_candidate_promotion_bundle_latest.json",
            ),
        ]
        missing_relative_paths = [
            str(item.get("relative_path", ""))
            for item in evidence_rows
            if not bool(item.get("present", False))
        ]
        completed = not missing_relative_paths
        reason = (
            "approved candidate promotion bundle deliverables are present inside the active workspace"
            if completed
            else "approved candidate promotion bundle deliverables remain incomplete inside the active workspace"
        )
        return {
            "schema_name": COMPLETION_EVALUATION_SCHEMA_NAME,
            "schema_version": COMPLETION_EVALUATION_SCHEMA_VERSION,
            "generated_at": _now(),
            "completion_pack_id": "approved_next_objective_prepare_candidate_promotion_bundle_v1",
            "completion_rule": "approved_reseed_objective_deliverables_present_inside_active_workspace",
            "directive_id": str(current_directive.get("directive_id", "")),
            "workspace_root": str(workspace_root),
            "completed": completed,
            "reason": reason,
            "partial_completion_states": ([] if completed else ["approved_candidate_promotion_bundle_pending"]),
            "required_deliverable_count": len(evidence_rows),
            "missing_required_deliverables": [
                {
                    "deliverable_id": "candidate_promotion_bundle",
                    "title": "Candidate promotion bundle",
                    "missing_evidence_relative_paths": missing_relative_paths,
                }
            ]
            if missing_relative_paths
            else [],
            "deliverable_checks": [
                {
                    "deliverable_id": "candidate_promotion_bundle",
                    "title": "Candidate promotion bundle",
                    "required": True,
                    "completed": completed,
                    "missing_evidence_relative_paths": missing_relative_paths,
                    "evidence_paths_present": [
                        str(item.get("absolute_path", ""))
                        for item in evidence_rows
                        if bool(item.get("present", False))
                    ],
                    "evidence_rows": evidence_rows,
                }
            ],
            "recommended_stop": completed,
            "current_objective": objective_context,
            "effective_next_objective_path": str(paths["effective_next_objective_path"]),
        }
    return {
        **base_evaluation,
        "completed": False,
        "recommended_stop": False,
        "reason": (
            f"approved next objective {objective_id} remains active and requires a bounded continuation cycle "
            "before completion can be re-evaluated"
        ),
        "current_objective": objective_context,
        "effective_next_objective_path": str(paths["effective_next_objective_path"]),
    }


def _derive_review_next_objective(
    *,
    review_pack: dict[str, Any],
    promotable: bool,
    promotion_state: str,
    weak_areas: list[dict[str, Any]],
    completion_evaluation: dict[str, Any],
    next_recommended_cycle: str,
    current_objective: dict[str, Any],
) -> dict[str, Any]:
    templates = _objective_template_rows(review_pack)
    if str(current_objective.get("source_kind", "")).strip() == OBJECTIVE_SOURCE_APPROVED_RESEED:
        objective_id = ""
        rationale = (
            "The approved bounded continuation objective is complete enough for review in this slice, "
            "but any further continuation remains explicitly operator-reviewed and is not proposed automatically."
        )
        return {
            "schema_name": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_NAME,
            "schema_version": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_VERSION,
            "generated_at": _now(),
            "proposal_state": PROMOTION_DEFERRED_STATE,
            "objective_id": objective_id,
            "objective_class": "",
            "title": "No automatic follow-on objective proposed",
            "rationale": rationale,
            "promotion_recommendation_state": promotion_state,
            "operator_review_required": True,
            "authorized_for_automatic_execution": False,
            "bounded_objective_complete": bool(completion_evaluation.get("completed", False)),
        }
    objective_id = ""

    if promotable:
        objective_id = "prepare_candidate_promotion_bundle"
    else:
        for item in weak_areas:
            candidate = str(item.get("failure_objective_id", "")).strip()
            if candidate:
                objective_id = candidate
                break
        if not objective_id:
            candidate = str(next_recommended_cycle).strip()
            if candidate and candidate != "operator_review_required":
                objective_id = candidate

    template = dict(templates.get(objective_id, {}))
    proposal_state = NEXT_OBJECTIVE_AVAILABLE_STATE if objective_id else PROMOTION_DEFERRED_STATE
    rationale = (
        str(template.get("rationale", "")).strip()
        if template
        else (
            "No further bounded objective is proposed automatically in this slice."
            if not objective_id
            else f"Proposed from the current bounded review state: {objective_id}."
        )
    )
    if not objective_id and bool(completion_evaluation.get("completed", False)):
        rationale = (
            "The bounded objective is complete, but continuation remains explicitly review-gated "
            "until an operator accepts a next bounded objective."
        )

    return {
        "schema_name": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_NAME,
        "schema_version": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_VERSION,
        "generated_at": _now(),
        "proposal_state": proposal_state,
        "objective_id": objective_id,
        "objective_class": _objective_class_from_objective_id(objective_id),
        "title": str(template.get("title", "")).strip() or _humanize_objective_id(objective_id) or "No next bounded objective proposed",
        "rationale": rationale,
        "promotion_recommendation_state": promotion_state,
        "operator_review_required": True,
        "authorized_for_automatic_execution": False,
        "bounded_objective_complete": bool(completion_evaluation.get("completed", False)),
    }


def _evaluate_successor_review_and_promotion(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    session: dict[str, Any],
    stop_reason: str,
    stop_detail: str,
    next_recommended_cycle: str,
    completion_evaluation: dict[str, Any],
    cycle_rows: list[dict[str, Any]],
    latest_summary_artifact_path: str,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    current_objective = _current_objective_context(
        current_directive=current_directive,
        workspace_root=workspace_root,
    )
    review_pack, review_source = _load_internal_knowledge_pack(
        session=session,
        source_id=INTERNAL_SUCCESSOR_PROMOTION_REVIEW_SOURCE_ID,
        expected_schema_name=SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_NAME,
        expected_schema_version=SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_VERSION,
    )
    review_state_model = dict(review_pack.get("review_status_model", {}))
    artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    readiness_summary = load_json(paths["readiness_summary_path"])
    delivery_manifest = load_json(paths["delivery_manifest_path"])
    cycle_history_summary = _cycle_history_summary(cycle_rows)
    cycle_output_paths = _collect_cycle_output_paths(cycle_rows)
    outputs_outside_workspace = [
        item
        for item in cycle_output_paths
        if item and not _is_under_path(Path(str(item)), workspace_root)
    ]
    completion_ready = (
        bool(completion_evaluation.get("completed", False))
        and bool(readiness_summary.get("completion_ready", False))
        and bool(delivery_manifest.get("completion_ready", False))
    )

    check_rows: list[dict[str, Any]] = []
    weak_areas: list[dict[str, Any]] = []
    for item in list(review_pack.get("promotion_checks", [])):
        row = dict(item)
        check_id = str(row.get("check_id", "")).strip()
        if not check_id:
            continue
        title = str(row.get("title", check_id))
        required_relative_paths = [
            str(path).strip() for path in list(row.get("required_relative_paths", [])) if str(path).strip()
        ]
        evidence_rows = [_relative_path_status(workspace_root, relative_path) for relative_path in required_relative_paths]
        missing_relative_paths = [
            str(entry.get("relative_path", ""))
            for entry in evidence_rows
            if not bool(entry.get("present", False))
        ]
        passed = True
        details: list[str] = []
        if missing_relative_paths:
            passed = False
            details.append("missing required paths: " + ", ".join(missing_relative_paths))
        expected_stop_reason = str(row.get("expected_stop_reason", "")).strip()
        if expected_stop_reason and stop_reason != expected_stop_reason:
            passed = False
            details.append(f"expected stop reason {expected_stop_reason} but observed {stop_reason or '<none>'}")
        disallowed_stop_reasons = [
            str(value).strip() for value in list(row.get("disallowed_stop_reasons", [])) if str(value).strip()
        ]
        if disallowed_stop_reasons and stop_reason in disallowed_stop_reasons:
            passed = False
            details.append(f"observed disallowed stop reason {stop_reason}")
        if bool(row.get("requires_output_within_workspace", False)) and outputs_outside_workspace:
            passed = False
            details.append("output paths escaped the bounded active workspace")
        if bool(row.get("requires_completion_ready", False)) and not completion_ready:
            passed = False
            details.append("completion claims are not backed by readiness artifacts")

        check_row = {
            "check_id": check_id,
            "title": title,
            "passed": passed,
            "required_relative_paths": required_relative_paths,
            "missing_relative_paths": missing_relative_paths,
            "details": "; ".join(details) if details else "passed",
            "failure_objective_id": str(row.get("failure_objective_id", "")).strip(),
        }
        check_rows.append(check_row)
        if not passed:
            weak_areas.append(check_row)

    promotable = bool(check_rows) and not weak_areas
    review_status = str(review_state_model.get("review_status_default", REVIEW_STATUS_REQUIRED)).strip() or REVIEW_STATUS_REQUIRED
    promotion_state = (
        str(review_state_model.get("promotion_recommended_state", PROMOTION_RECOMMENDED_STATE)).strip()
        if promotable
        else str(review_state_model.get("promotion_not_recommended_state", PROMOTION_NOT_RECOMMENDED_STATE)).strip()
    ) or (PROMOTION_RECOMMENDED_STATE if promotable else PROMOTION_NOT_RECOMMENDED_STATE)
    proposal_payload = _derive_review_next_objective(
        review_pack=review_pack,
        promotable=promotable,
        promotion_state=promotion_state,
        weak_areas=weak_areas,
        completion_evaluation=completion_evaluation,
        next_recommended_cycle=next_recommended_cycle,
        current_objective=current_objective,
    )
    bounded_deliverables_present = [
        str(item.get("relative_path", ""))
        for item in list(delivery_manifest.get("deliverables", []))
        if bool(item.get("present", False))
    ]
    recommendation_rationale = (
        "The bounded successor package satisfies the current bounded completion and review rubric, so promotion is recommended for explicit operator review."
        if promotable
        else (
            "Promotion is not recommended yet because bounded review checks still report missing or weak areas."
            if weak_areas
            else "Promotion is not recommended because review evidence is incomplete."
        )
    )
    confidence = "conservative_high" if promotable else ("conservative_medium" if bool(completion_evaluation.get("completed", False)) else "conservative_low")

    recommendation_payload = {
        "schema_name": SUCCESSOR_PROMOTION_RECOMMENDATION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_PROMOTION_RECOMMENDATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "completed_objective_id": str(current_objective.get("objective_id", "")),
        "completed_objective_source_kind": str(current_objective.get("source_kind", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "review_status": review_status,
        "promotion_recommendation_state": promotion_state,
        "promotion_recommended": promotable,
        "confidence": confidence,
        "rationale": recommendation_rationale,
        "bounded_objective_complete": bool(completion_evaluation.get("completed", False)),
        "stop_reason": stop_reason,
        "stop_detail": stop_detail,
        "protected_surfaces_untouched": not outputs_outside_workspace,
        "outputs_within_active_workspace": not outputs_outside_workspace,
        "operator_review_required": True,
        "requires_operator_review_before_promotion": True,
        "criteria_results": check_rows,
        "weak_areas": weak_areas,
        "knowledge_pack_source": review_source,
    }
    review_summary = {
        "schema_name": SUCCESSOR_REVIEW_SUMMARY_SCHEMA_NAME,
        "schema_version": SUCCESSOR_REVIEW_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "completed_objective_id": str(current_objective.get("objective_id", "")),
        "completed_objective_source_kind": str(current_objective.get("source_kind", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "cycle_history_summary": cycle_history_summary,
        "latest_summary_artifact_path": str(latest_summary_artifact_path or ""),
        "bounded_deliverables_present": bounded_deliverables_present,
        "missing_or_weak_areas": weak_areas,
        "review_status": review_status,
        "promotion_recommendation_state": promotion_state,
        "promotion_recommended": promotable,
        "operator_review_required": True,
        "next_objective_state": str(proposal_payload.get("proposal_state", PROMOTION_DEFERRED_STATE)),
        "next_objective_id": str(proposal_payload.get("objective_id", "")),
        "next_objective_title": str(proposal_payload.get("title", "")),
        "bounded_objective_complete": bool(completion_evaluation.get("completed", False)),
        "stop_reason": stop_reason,
        "stop_detail": stop_detail,
        "completion_evaluation": completion_evaluation,
        "artifact_index_path": str(paths["workspace_artifact_index_path"]),
        "artifact_count": int(artifact_index.get("artifact_count", 0) or 0),
        "knowledge_pack_source": review_source,
    }
    return {
        "review_summary": review_summary,
        "promotion_recommendation": recommendation_payload,
        "next_objective_proposal": {
            **proposal_payload,
            "directive_id": str(current_directive.get("directive_id", "")),
            "completed_objective_id": str(current_objective.get("objective_id", "")),
            "completed_objective_source_kind": str(current_objective.get("source_kind", "")),
            "workspace_id": str(workspace_root.name),
            "workspace_root": str(workspace_root),
        },
    }


def _materialize_successor_review_outputs(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    session: dict[str, Any],
    stop_reason: str,
    stop_detail: str,
    next_recommended_cycle: str,
    completion_evaluation: dict[str, Any],
    cycle_rows: list[dict[str, Any]],
    latest_summary_artifact_path: str,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    review_payloads = _evaluate_successor_review_and_promotion(
        current_directive=current_directive,
        workspace_root=workspace_root,
        session=session,
        stop_reason=stop_reason,
        stop_detail=stop_detail,
        next_recommended_cycle=next_recommended_cycle,
        completion_evaluation=completion_evaluation,
        cycle_rows=cycle_rows,
        latest_summary_artifact_path=latest_summary_artifact_path,
    )
    latest_paths = [
        (paths["review_summary_path"], dict(review_payloads.get("review_summary", {})), "successor_review_summary_json"),
        (
            paths["promotion_recommendation_path"],
            dict(review_payloads.get("promotion_recommendation", {})),
            "successor_promotion_recommendation_json",
        ),
        (
            paths["next_objective_proposal_path"],
            dict(review_payloads.get("next_objective_proposal", {})),
            "successor_next_objective_proposal_json",
        ),
    ]
    _event(
        runtime_event_log_path,
        event_type="successor_review_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        stop_reason=stop_reason,
    )
    for artifact_path, artifact_payload, artifact_kind in latest_paths:
        _write_json(
            artifact_path,
            artifact_payload,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id="successor_review_and_promotion",
            artifact_kind=artifact_kind,
        )

    latest_cycle_index = int(_cycle_history_summary(cycle_rows).get("latest_cycle_index", 0) or 0)
    if latest_cycle_index > 0:
        cycle_prefix = paths["cycles_root"] / f"cycle_{latest_cycle_index:03d}"
        archive_rows = [
            (cycle_prefix.with_name(f"{cycle_prefix.name}_successor_review_summary.json"), dict(review_payloads.get("review_summary", {}))),
            (
                cycle_prefix.with_name(f"{cycle_prefix.name}_successor_promotion_recommendation.json"),
                dict(review_payloads.get("promotion_recommendation", {})),
            ),
            (
                cycle_prefix.with_name(f"{cycle_prefix.name}_successor_next_objective_proposal.json"),
                dict(review_payloads.get("next_objective_proposal", {})),
            ),
        ]
        for artifact_path, artifact_payload in archive_rows:
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")

    review_summary = dict(review_payloads.get("review_summary", {}))
    promotion_recommendation = dict(review_payloads.get("promotion_recommendation", {}))
    next_objective_proposal = dict(review_payloads.get("next_objective_proposal", {}))
    _event(
        runtime_event_log_path,
        event_type="successor_review_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        review_status=str(review_summary.get("review_status", "")),
        review_summary_path=str(paths["review_summary_path"]),
    )
    _event(
        runtime_event_log_path,
        event_type="promotion_recommendation_recorded",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        promotion_recommendation_state=str(promotion_recommendation.get("promotion_recommendation_state", "")),
        recommendation_path=str(paths["promotion_recommendation_path"]),
        reason=str(promotion_recommendation.get("rationale", "")),
    )
    _event(
        runtime_event_log_path,
        event_type="next_objective_proposed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        proposed_objective_id=str(next_objective_proposal.get("objective_id", "")),
        next_objective_state=str(next_objective_proposal.get("proposal_state", "")),
        next_objective_proposal_path=str(paths["next_objective_proposal_path"]),
        reason=str(next_objective_proposal.get("rationale", "")),
    )
    return {
        **review_payloads,
        "review_summary_path": str(paths["review_summary_path"]),
        "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
        "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
    }


def _build_pending_reseed_outputs(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    review_outputs: dict[str, Any],
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    review_summary = dict(review_outputs.get("review_summary", {}))
    promotion_recommendation = dict(review_outputs.get("promotion_recommendation", {}))
    next_objective_proposal = dict(review_outputs.get("next_objective_proposal", {}))
    completed_objective_id = str(review_summary.get("completed_objective_id", "")).strip() or str(
        current_directive.get("directive_id", "")
    ).strip()
    completed_objective_source_kind = str(
        review_summary.get("completed_objective_source_kind", OBJECTIVE_SOURCE_DIRECTIVE)
    ).strip() or OBJECTIVE_SOURCE_DIRECTIVE
    proposed_objective_id = str(next_objective_proposal.get("objective_id", "")).strip()
    proposed_objective_class = _objective_class_from_objective_id(proposed_objective_id)
    reseed_state = RESEED_PENDING_REVIEW_STATE if proposed_objective_id else RESEED_DEFERRED_STATE
    request_rationale = (
        "A reviewed bounded next objective is available and awaits explicit operator approval before continuation."
        if proposed_objective_id
        else "No executable next bounded objective is proposed automatically in this slice; operator review remains required."
    )
    request_payload = {
        "schema_name": SUCCESSOR_RESEED_REQUEST_SCHEMA_NAME,
        "schema_version": SUCCESSOR_RESEED_REQUEST_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "completed_objective_id": completed_objective_id,
        "completed_objective_source_kind": completed_objective_source_kind,
        "review_summary_path": str(review_outputs.get("review_summary_path", "")),
        "promotion_recommendation_path": str(
            review_outputs.get("promotion_recommendation_path", "")
        ),
        "next_objective_proposal_path": str(review_outputs.get("next_objective_proposal_path", "")),
        "review_status": str(review_summary.get("review_status", "")),
        "promotion_recommendation_state": str(
            promotion_recommendation.get("promotion_recommendation_state", "")
        ),
        "proposal_state": str(next_objective_proposal.get("proposal_state", "")),
        "proposed_objective_id": proposed_objective_id,
        "proposed_objective_class": proposed_objective_class,
        "proposed_objective_title": str(next_objective_proposal.get("title", "")),
        "reseed_state": reseed_state,
        "operator_review_required": True,
        "continuation_authorized": False,
        "rationale": request_rationale,
    }
    decision_payload = {
        "schema_name": SUCCESSOR_RESEED_DECISION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_RESEED_DECISION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "completed_objective_id": completed_objective_id,
        "completed_objective_source_kind": completed_objective_source_kind,
        "reseed_state": reseed_state,
        "operator_decision": "pending_review",
        "operator_note": "",
        "continuation_authorized": False,
        "proposed_objective_id": proposed_objective_id,
        "proposed_objective_class": proposed_objective_class,
        "proposed_objective_title": str(next_objective_proposal.get("title", "")),
        "reseed_request_path": str(paths["reseed_request_path"]),
    }
    effective_payload = {
        "schema_name": SUCCESSOR_EFFECTIVE_NEXT_OBJECTIVE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_EFFECTIVE_NEXT_OBJECTIVE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "completed_objective_id": completed_objective_id,
        "completed_objective_source_kind": completed_objective_source_kind,
        "reseed_state": reseed_state,
        "continuation_authorized": False,
        "authorized_for_execution": False,
        "execution_state": "awaiting_operator_review" if proposed_objective_id else "no_authorized_continuation",
        "objective_id": "",
        "objective_class": "",
        "title": "",
        "rationale": request_rationale,
        "authorization_origin": "",
        "reseed_request_path": str(paths["reseed_request_path"]),
        "reseed_decision_path": str(paths["reseed_decision_path"]),
        "review_summary_path": str(review_outputs.get("review_summary_path", "")),
        "promotion_recommendation_path": str(
            review_outputs.get("promotion_recommendation_path", "")
        ),
        "next_objective_proposal_path": str(review_outputs.get("next_objective_proposal_path", "")),
    }
    lineage_payload = {
        "schema_name": SUCCESSOR_CONTINUATION_LINEAGE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_CONTINUATION_LINEAGE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "completed_objective_id": completed_objective_id,
        "completed_objective_source_kind": completed_objective_source_kind,
        "review_summary_path": str(review_outputs.get("review_summary_path", "")),
        "promotion_recommendation_path": str(
            review_outputs.get("promotion_recommendation_path", "")
        ),
        "next_objective_proposal_path": str(review_outputs.get("next_objective_proposal_path", "")),
        "reseed_request_path": str(paths["reseed_request_path"]),
        "reseed_decision_path": str(paths["reseed_decision_path"]),
        "effective_next_objective_path": str(paths["effective_next_objective_path"]),
        "reseed_state": reseed_state,
        "operator_decision": "pending_review",
        "continuation_authorized": False,
        "proposed_objective_id": proposed_objective_id,
        "proposed_objective_class": proposed_objective_class,
        "proposed_objective_title": str(next_objective_proposal.get("title", "")),
        "effective_objective_id": "",
        "effective_objective_class": "",
        "authorization_origin": "",
    }
    return {
        "request": request_payload,
        "decision": decision_payload,
        "effective_next_objective": effective_payload,
        "continuation_lineage": lineage_payload,
        "reseed_request_path": str(paths["reseed_request_path"]),
        "reseed_decision_path": str(paths["reseed_decision_path"]),
        "continuation_lineage_path": str(paths["continuation_lineage_path"]),
        "effective_next_objective_path": str(paths["effective_next_objective_path"]),
    }


def _materialize_successor_reseed_request_outputs(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    review_outputs: dict[str, Any],
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    payloads = _build_pending_reseed_outputs(
        current_directive=current_directive,
        workspace_root=workspace_root,
        review_outputs=review_outputs,
    )
    write_rows = [
        (paths["reseed_request_path"], dict(payloads.get("request", {})), "successor_reseed_request_json"),
        (paths["reseed_decision_path"], dict(payloads.get("decision", {})), "successor_reseed_decision_json"),
        (
            paths["continuation_lineage_path"],
            dict(payloads.get("continuation_lineage", {})),
            "successor_continuation_lineage_json",
        ),
        (
            paths["effective_next_objective_path"],
            dict(payloads.get("effective_next_objective", {})),
            "successor_effective_next_objective_json",
        ),
    ]
    for artifact_path, artifact_payload, artifact_kind in write_rows:
        _write_json(
            artifact_path,
            artifact_payload,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id="successor_reseed_request",
            artifact_kind=artifact_kind,
        )
    _event(
        runtime_event_log_path,
        event_type="successor_reseed_request_materialized",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        reseed_state=str(dict(payloads.get("request", {})).get("reseed_state", "")),
        proposed_objective_id=str(dict(payloads.get("request", {})).get("proposed_objective_id", "")),
        reseed_request_path=str(paths["reseed_request_path"]),
    )
    return payloads


def materialize_successor_reseed_decision(
    *,
    workspace_root: str | Path,
    operator_decision: str,
    operator_note: str = "",
    actor: str = "operator_web_ui",
    operator_root: str | Path | None = None,
) -> dict[str, Any]:
    workspace_root_path = Path(workspace_root)
    paths = _workspace_paths(workspace_root_path)
    review_summary = load_json(paths["review_summary_path"])
    promotion_recommendation = load_json(paths["promotion_recommendation_path"])
    next_objective_proposal = load_json(paths["next_objective_proposal_path"])
    if not review_summary or not next_objective_proposal:
        raise GovernedExecutionFailure(
            "reseed decision requires existing review and next-objective proposal artifacts",
            summary_artifact_path=str(paths["review_summary_path"]),
        )
    decision_key = str(operator_decision or "").strip().lower()
    if decision_key not in {"approve", "reject", "defer", "auto_continue"}:
        raise GovernedExecutionFailure(
            "unsupported reseed decision; expected approve, reject, defer, or auto_continue"
        )
    proposed_objective_id = str(next_objective_proposal.get("objective_id", "")).strip()
    proposed_objective_class = _objective_class_from_objective_id(proposed_objective_id)
    if decision_key in {"approve", "auto_continue"} and not proposed_objective_id:
        raise GovernedExecutionFailure(
            "cannot approve continuation because no bounded next objective is currently proposed"
        )

    request_outputs = _build_pending_reseed_outputs(
        current_directive={"directive_id": str(review_summary.get("directive_id", ""))},
        workspace_root=workspace_root_path,
        review_outputs={
            "review_summary": review_summary,
            "promotion_recommendation": promotion_recommendation,
            "next_objective_proposal": next_objective_proposal,
            "review_summary_path": str(paths["review_summary_path"]),
            "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
            "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
        },
    )
    request_payload = dict(request_outputs.get("request", {}))
    completed_objective_id = str(request_payload.get("completed_objective_id", "")).strip()
    completed_objective_source_kind = str(
        request_payload.get("completed_objective_source_kind", OBJECTIVE_SOURCE_DIRECTIVE)
    ).strip() or OBJECTIVE_SOURCE_DIRECTIVE

    reseed_state = {
        "approve": RESEED_APPROVED_STATE,
        "reject": RESEED_REJECTED_STATE,
        "defer": RESEED_DEFERRED_STATE,
        "auto_continue": RESEED_APPROVED_STATE,
    }[decision_key]
    continuation_authorized = decision_key in {"approve", "auto_continue"}
    effective_state = RESEED_MATERIALIZED_STATE if continuation_authorized else reseed_state
    effective_objective_id = proposed_objective_id if continuation_authorized else ""
    effective_objective_class = (
        proposed_objective_class if continuation_authorized else ""
    )
    effective_title = (
        str(next_objective_proposal.get("title", "")).strip() if continuation_authorized else ""
    )
    effective_rationale = (
        str(next_objective_proposal.get("rationale", "")).strip()
        if continuation_authorized
        else f"Operator decision recorded as {decision_key}; no executable next objective is active."
    )
    authorization_origin = (
        AUTO_CONTINUE_ORIGIN_POLICY
        if decision_key == "auto_continue"
        else (AUTO_CONTINUE_ORIGIN_MANUAL if continuation_authorized else "")
    )
    decision_payload = {
        "schema_name": SUCCESSOR_RESEED_DECISION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_RESEED_DECISION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(review_summary.get("directive_id", "")),
        "workspace_id": str(workspace_root_path.name),
        "workspace_root": str(workspace_root_path),
        "completed_objective_id": completed_objective_id,
        "completed_objective_source_kind": completed_objective_source_kind,
        "reseed_state": reseed_state,
        "operator_decision": decision_key,
        "operator_note": str(operator_note or "").strip(),
        "decision_actor": actor,
        "continuation_authorized": continuation_authorized,
        "proposed_objective_id": proposed_objective_id,
        "proposed_objective_class": proposed_objective_class,
        "proposed_objective_title": str(next_objective_proposal.get("title", "")),
        "authorization_origin": authorization_origin,
        "reseed_request_path": str(paths["reseed_request_path"]),
    }
    effective_payload = {
        "schema_name": SUCCESSOR_EFFECTIVE_NEXT_OBJECTIVE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_EFFECTIVE_NEXT_OBJECTIVE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(review_summary.get("directive_id", "")),
        "workspace_id": str(workspace_root_path.name),
        "workspace_root": str(workspace_root_path),
        "completed_objective_id": completed_objective_id,
        "completed_objective_source_kind": completed_objective_source_kind,
        "reseed_state": effective_state,
        "continuation_authorized": continuation_authorized,
        "authorized_for_execution": continuation_authorized,
        "execution_state": "approved_pending_execution" if continuation_authorized else "not_authorized",
        "objective_id": effective_objective_id,
        "objective_class": effective_objective_class,
        "title": effective_title,
        "rationale": effective_rationale,
        "operator_decision": decision_key,
        "operator_note": str(operator_note or "").strip(),
        "authorization_origin": authorization_origin,
        "review_summary_path": str(paths["review_summary_path"]),
        "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
        "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
        "reseed_request_path": str(paths["reseed_request_path"]),
        "reseed_decision_path": str(paths["reseed_decision_path"]),
        "continuation_lineage_path": str(paths["continuation_lineage_path"]),
    }
    lineage_payload = {
        "schema_name": SUCCESSOR_CONTINUATION_LINEAGE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_CONTINUATION_LINEAGE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(review_summary.get("directive_id", "")),
        "workspace_id": str(workspace_root_path.name),
        "workspace_root": str(workspace_root_path),
        "completed_objective_id": completed_objective_id,
        "completed_objective_source_kind": completed_objective_source_kind,
        "review_summary_path": str(paths["review_summary_path"]),
        "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
        "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
        "reseed_request_path": str(paths["reseed_request_path"]),
        "reseed_decision_path": str(paths["reseed_decision_path"]),
        "effective_next_objective_path": str(paths["effective_next_objective_path"]),
        "reseed_state": effective_state,
        "operator_decision": decision_key,
        "continuation_authorized": continuation_authorized,
        "proposed_objective_id": proposed_objective_id,
        "proposed_objective_class": proposed_objective_class,
        "effective_objective_id": effective_objective_id,
        "effective_objective_class": effective_objective_class,
        "effective_objective_title": effective_title,
        "authorization_origin": authorization_origin,
    }
    request_payload["generated_at"] = _now()
    request_payload["reseed_state"] = effective_state if continuation_authorized else reseed_state
    request_payload["operator_decision"] = decision_key
    request_payload["operator_note"] = str(operator_note or "").strip()
    request_payload["continuation_authorized"] = continuation_authorized
    request_payload["effective_objective_id"] = effective_objective_id
    request_payload["proposed_objective_class"] = proposed_objective_class
    request_payload["effective_objective_class"] = effective_objective_class
    request_payload["authorization_origin"] = authorization_origin

    for artifact_path, artifact_payload in (
        (paths["reseed_request_path"], request_payload),
        (paths["reseed_decision_path"], decision_payload),
        (paths["effective_next_objective_path"], effective_payload),
        (paths["continuation_lineage_path"], lineage_payload),
    ):
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")

    session_summary = load_session_summary(workspace_root_path)
    runtime_event_log_path = Path(str(session_summary.get("runtime_event_log_path", "")).strip())
    session_id = str(session_summary.get("session_id", "")).strip() or "operator_review"
    directive_id = str(review_summary.get("directive_id", "")).strip()
    execution_profile = str(session_summary.get("execution_profile", "")).strip() or "bounded_active_workspace_coding"
    auto_continue_outputs: dict[str, Any] = {
        "state": load_successor_auto_continue_state(workspace_root_path),
        "decision": load_successor_auto_continue_decision(workspace_root_path),
        "state_path": str(paths["auto_continue_state_path"]),
        "decision_path": str(paths["auto_continue_decision_path"]),
    }
    if decision_key != "auto_continue":
        auto_continue_outputs = _write_successor_auto_continue_state_and_decision(
            workspace_root=workspace_root_path,
            operator_root=operator_root,
            review_summary=review_summary,
            promotion_recommendation=promotion_recommendation,
            next_objective_proposal=next_objective_proposal,
            reseed_request_path=str(paths["reseed_request_path"]),
            reseed_decision_path=str(paths["reseed_decision_path"]),
            continuation_lineage_path=str(paths["continuation_lineage_path"]),
            effective_next_objective_path=str(paths["effective_next_objective_path"]),
            continuation_authorized=continuation_authorized,
            decision_reason={
                "approve": "manual_approval_recorded",
                "reject": "manual_reject_recorded",
                "defer": "manual_defer_recorded",
            }[decision_key],
            decision_actor=actor,
            authorization_origin=authorization_origin,
            operator_decision=decision_key,
            effective_objective_id=effective_objective_id,
            effective_objective_title=effective_title,
        )
    if str(runtime_event_log_path):
        _event(
            runtime_event_log_path,
            event_type="successor_reseed_decision_recorded",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=str(workspace_root_path.name),
            workspace_root=str(workspace_root_path),
            reseed_state=reseed_state,
            operator_decision=decision_key,
            continuation_authorized=continuation_authorized,
            proposed_objective_id=proposed_objective_id,
            objective_class=proposed_objective_class,
            authorization_origin=authorization_origin,
            reseed_decision_path=str(paths["reseed_decision_path"]),
        )
        _event(
            runtime_event_log_path,
            event_type="successor_effective_next_objective_materialized",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=str(workspace_root_path.name),
            workspace_root=str(workspace_root_path),
            reseed_state=effective_state,
            continuation_authorized=continuation_authorized,
            effective_objective_id=effective_objective_id,
            objective_class=effective_objective_class,
            authorization_origin=authorization_origin,
            effective_next_objective_path=str(paths["effective_next_objective_path"]),
        )
    return {
        "request": request_payload,
        "decision": decision_payload,
        "effective_next_objective": effective_payload,
        "continuation_lineage": lineage_payload,
        "auto_continue_state": dict(auto_continue_outputs.get("state", {})),
        "auto_continue_decision": dict(auto_continue_outputs.get("decision", {})),
        "reseed_request_path": str(paths["reseed_request_path"]),
        "reseed_decision_path": str(paths["reseed_decision_path"]),
        "continuation_lineage_path": str(paths["continuation_lineage_path"]),
        "effective_next_objective_path": str(paths["effective_next_objective_path"]),
        "auto_continue_state_path": str(paths["auto_continue_state_path"]),
        "auto_continue_decision_path": str(paths["auto_continue_decision_path"]),
    }


def _update_effective_next_objective_after_run(
    *,
    workspace_root: Path,
    current_objective: dict[str, Any],
    completion_evaluation: dict[str, Any],
    stop_reason: str,
    stop_detail: str,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    payload = load_json(paths["effective_next_objective_path"])
    if not payload:
        return {}
    if (
        str(current_objective.get("source_kind", "")).strip() != OBJECTIVE_SOURCE_APPROVED_RESEED
        or str(payload.get("objective_id", "")).strip()
        != str(current_objective.get("objective_id", "")).strip()
    ):
        return payload
    updated = dict(payload)
    updated["generated_at"] = _now()
    updated["last_stop_reason"] = str(stop_reason)
    updated["last_stop_detail"] = str(stop_detail)
    if bool(completion_evaluation.get("completed", False)):
        updated["execution_state"] = "completed"
        updated["completed_at"] = _now()
        updated["continuation_authorized"] = False
        updated["authorized_for_execution"] = False
    elif stop_reason in {STOP_REASON_SINGLE_CYCLE, STOP_REASON_MAX_CAP}:
        updated["execution_state"] = "awaiting_additional_reentry"
    elif stop_reason in {STOP_REASON_FAILURE, STOP_REASON_NO_WORK, STOP_REASON_BLOCKED}:
        updated["execution_state"] = "execution_blocked"
    paths["effective_next_objective_path"].write_text(_dump(updated), encoding="utf-8")
    lineage_payload = load_json(paths["continuation_lineage_path"])
    if lineage_payload:
        lineage_payload["generated_at"] = _now()
        lineage_payload["effective_objective_id"] = str(updated.get("objective_id", ""))
        lineage_payload["effective_objective_execution_state"] = str(
            updated.get("execution_state", "")
        )
        lineage_payload["continuation_authorized"] = bool(
            updated.get("continuation_authorized", False)
        )
        lineage_payload["last_stop_reason"] = str(stop_reason)
        lineage_payload["last_stop_detail"] = str(stop_detail)
        paths["continuation_lineage_path"].write_text(_dump(lineage_payload), encoding="utf-8")
    return updated


def _derive_next_step_from_continuation_pack(
    *,
    current_directive: dict[str, Any],
    continuation_pack: dict[str, Any],
    completion_evaluation: dict[str, Any],
    workspace_root: Path,
) -> dict[str, Any]:
    completed_by_id = {
        str(item.get("deliverable_id", "")): bool(item.get("completed", False))
        for item in list(completion_evaluation.get("deliverable_checks", []))
        if str(item.get("deliverable_id", "")).strip()
    }
    stages = [dict(item) for item in list(continuation_pack.get("stages", []))]
    selected_stage: dict[str, Any] = {}
    stage_reason = ""
    missing_deliverables = list(completion_evaluation.get("missing_required_deliverables", []))

    for stage in stages:
        requires_deliverables = [str(item).strip() for item in list(stage.get("requires_deliverables", [])) if str(item).strip()]
        missing_gate = [str(item).strip() for item in list(stage.get("missing_deliverables_gate", [])) if str(item).strip()]
        if not all(completed_by_id.get(item, False) for item in requires_deliverables):
            continue
        if not any(not completed_by_id.get(item, False) for item in missing_gate):
            continue
        selected_stage = {
            "stage_id": str(stage.get("stage_id", "")),
            "title": str(stage.get("title", "")),
            "cycle_kind": str(stage.get("cycle_kind", "")),
            "work_item_id": str(stage.get("work_item_id", "")),
            "rationale": str(stage.get("rationale", "")),
            "next_recommended_cycle": str(stage.get("next_recommended_cycle", "")),
            "requires_deliverables": requires_deliverables,
            "missing_deliverables_gate": missing_gate,
        }
        stage_reason = (
            f"selected {selected_stage['stage_id']} because "
            + ", ".join(missing_gate)
            + " remain incomplete under the bounded successor rubric"
        )
        break

    if not selected_stage and bool(completion_evaluation.get("completed", False)):
        stage_reason = "no further cycle is required because the bounded successor completion rubric is satisfied"
    elif not selected_stage:
        stage_reason = "no admissible continuation stage matched the current bounded deliverable state"

    return {
        "schema_name": NEXT_STEP_DERIVATION_SCHEMA_NAME,
        "schema_version": NEXT_STEP_DERIVATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "continuation_pack_id": str(continuation_pack.get("pack_id", "")),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_root": str(workspace_root),
        "selected_stage": selected_stage,
        "reason": stage_reason,
        "admissible_work_remaining": bool(selected_stage),
        "next_recommended_cycle": str(selected_stage.get("next_recommended_cycle", "")),
        "missing_required_deliverables": missing_deliverables,
    }


def _derive_next_step_with_objective_context(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    completion_evaluation: dict[str, Any],
    base_next_step: dict[str, Any],
) -> dict[str, Any]:
    objective_context = dict(
        completion_evaluation.get(
            "current_objective",
            _current_objective_context(
                current_directive=current_directive,
                workspace_root=workspace_root,
            ),
        )
    )
    if str(objective_context.get("source_kind", "")).strip() != OBJECTIVE_SOURCE_APPROVED_RESEED:
        return {
            **dict(base_next_step),
            "current_objective": objective_context,
        }
    if bool(completion_evaluation.get("completed", False)):
        return {
            "schema_name": NEXT_STEP_DERIVATION_SCHEMA_NAME,
            "schema_version": NEXT_STEP_DERIVATION_SCHEMA_VERSION,
            "generated_at": _now(),
            "continuation_pack_id": "approved_reseed_objective",
            "directive_id": str(current_directive.get("directive_id", "")),
            "workspace_root": str(workspace_root),
            "selected_stage": {},
            "reason": str(completion_evaluation.get("reason", "")).strip()
            or "the approved bounded continuation objective is already complete",
            "admissible_work_remaining": False,
            "next_recommended_cycle": "operator_review_required",
            "missing_required_deliverables": list(
                completion_evaluation.get("missing_required_deliverables", [])
            ),
            "current_objective": objective_context,
        }
    selected_stage = _effective_objective_stage(str(objective_context.get("objective_id", "")))
    if not selected_stage:
        return {
            "schema_name": NEXT_STEP_DERIVATION_SCHEMA_NAME,
            "schema_version": NEXT_STEP_DERIVATION_SCHEMA_VERSION,
            "generated_at": _now(),
            "continuation_pack_id": "approved_reseed_objective",
            "directive_id": str(current_directive.get("directive_id", "")),
            "workspace_root": str(workspace_root),
            "selected_stage": {},
            "reason": (
                "the approved next objective is recorded, but this slice does not yet materialize a bounded "
                "execution stage for that objective"
            ),
            "admissible_work_remaining": False,
            "next_recommended_cycle": "operator_review_required",
            "missing_required_deliverables": list(
                completion_evaluation.get("missing_required_deliverables", [])
            ),
            "current_objective": objective_context,
        }
    return {
        "schema_name": NEXT_STEP_DERIVATION_SCHEMA_NAME,
        "schema_version": NEXT_STEP_DERIVATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "continuation_pack_id": "approved_reseed_objective",
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_root": str(workspace_root),
        "selected_stage": selected_stage,
        "reason": (
            f"using the operator-approved bounded next objective {objective_context.get('objective_id', '')} "
            "as the current governed continuation target"
        ),
        "admissible_work_remaining": True,
        "next_recommended_cycle": str(selected_stage.get("next_recommended_cycle", "")),
        "missing_required_deliverables": list(
            completion_evaluation.get("missing_required_deliverables", [])
        ),
        "current_objective": objective_context,
    }


def _build_trusted_planning_context(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    session: dict[str, Any],
    cycle_index: int,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    work_item_id: str,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    baseline = _workspace_baseline(workspace_root)
    completion_pack, completion_source = _load_internal_knowledge_pack(
        session=session,
        source_id=INTERNAL_SUCCESSOR_COMPLETION_SOURCE_ID,
        expected_schema_name=SUCCESSOR_COMPLETION_KNOWLEDGE_PACK_SCHEMA_NAME,
        expected_schema_version=SUCCESSOR_COMPLETION_KNOWLEDGE_PACK_SCHEMA_VERSION,
    )
    continuation_pack, continuation_source = _load_internal_knowledge_pack(
        session=session,
        source_id=INTERNAL_WORKSPACE_CONTINUATION_SOURCE_ID,
        expected_schema_name=WORKSPACE_CONTINUATION_KNOWLEDGE_PACK_SCHEMA_NAME,
        expected_schema_version=WORKSPACE_CONTINUATION_KNOWLEDGE_PACK_SCHEMA_VERSION,
    )
    workspace_artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    completion_evaluation = _evaluate_current_objective_completion(
        current_directive=current_directive,
        workspace_root=workspace_root,
        completion_pack=completion_pack,
    )
    base_next_step = _derive_next_step_from_continuation_pack(
        current_directive=current_directive,
        continuation_pack=continuation_pack,
        completion_evaluation=completion_evaluation,
        workspace_root=workspace_root,
    )
    next_step = _derive_next_step_with_objective_context(
        current_directive=current_directive,
        workspace_root=workspace_root,
        completion_evaluation=completion_evaluation,
        base_next_step=base_next_step,
    )
    missing_deliverables = {
        "schema_name": MISSING_DELIVERABLES_SCHEMA_NAME,
        "schema_version": MISSING_DELIVERABLES_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "missing_required_deliverables": list(completion_evaluation.get("missing_required_deliverables", [])),
        "missing_required_deliverable_count": len(list(completion_evaluation.get("missing_required_deliverables", []))),
        "next_recommended_cycle": str(next_step.get("next_recommended_cycle", "")),
    }
    planning_evidence = {
        "schema_name": TRUSTED_PLANNING_EVIDENCE_SCHEMA_NAME,
        "schema_version": TRUSTED_PLANNING_EVIDENCE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "cycle_index": int(cycle_index),
        "directive_trusted_sources": [str(item) for item in list(current_directive.get("trusted_sources", []))],
        "consulted_workspace_artifacts": {
            "bounded_work_summary_latest": str(paths["summary_path"]) if paths["summary_path"].exists() else "",
            "implementation_bundle_summary_latest": str(paths["implementation_summary_path"]) if paths["implementation_summary_path"].exists() else "",
            "workspace_artifact_index_latest": str(paths["workspace_artifact_index_path"]),
        },
        "knowledge_packs": [completion_source, continuation_source],
        "workspace_artifact_index": workspace_artifact_index,
        "baseline_state": {
            "has_planning_baseline": bool(baseline.get("has_planning_baseline", False)),
            "implementation_materialized": bool(baseline.get("implementation_materialized", False)),
            "continuation_gap_materialized": bool(baseline.get("continuation_gap_materialized", False)),
            "readiness_materialized": bool(baseline.get("readiness_materialized", False)),
            "promotion_bundle_materialized": bool(baseline.get("promotion_bundle_materialized", False)),
        },
        "current_objective": dict(completion_evaluation.get("current_objective", {})),
    }

    latest_writes = [
        (paths["workspace_artifact_index_path"], workspace_artifact_index, "workspace_artifact_index_json"),
        (paths["trusted_planning_evidence_path"], planning_evidence, "trusted_planning_evidence_json"),
        (paths["missing_deliverables_path"], missing_deliverables, "missing_deliverables_json"),
        (paths["next_step_derivation_path"], next_step, "next_step_derivation_json"),
        (paths["completion_evaluation_path"], completion_evaluation, "completion_evaluation_json"),
    ]
    for artifact_path, artifact_payload, artifact_kind in latest_writes:
        _write_json(
            artifact_path,
            artifact_payload,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=work_item_id,
            artifact_kind=artifact_kind,
        )

    cycle_prefix = paths["cycles_root"] / f"cycle_{int(cycle_index):03d}"
    archive_rows = [
        (cycle_prefix.with_name(f"{cycle_prefix.name}_trusted_planning_evidence.json"), planning_evidence),
        (cycle_prefix.with_name(f"{cycle_prefix.name}_missing_deliverables.json"), missing_deliverables),
        (cycle_prefix.with_name(f"{cycle_prefix.name}_next_step_derivation.json"), next_step),
        (cycle_prefix.with_name(f"{cycle_prefix.name}_completion_evaluation.json"), completion_evaluation),
    ]
    for artifact_path, artifact_payload in archive_rows:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")

    _event(
        runtime_event_log_path,
        event_type="trusted_planning_evidence_consulted",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(cycle_index),
        consulted_sources=[
            str(item.get("source_id", ""))
            for item in list(planning_evidence.get("knowledge_packs", []))
            if bool(item.get("loaded", False))
        ],
        trusted_planning_evidence_path=str(paths["trusted_planning_evidence_path"]),
    )
    _event(
        runtime_event_log_path,
        event_type="missing_deliverables_identified",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(cycle_index),
        missing_required_deliverable_count=int(missing_deliverables.get("missing_required_deliverable_count", 0)),
        missing_deliverables_path=str(paths["missing_deliverables_path"]),
    )
    _event(
        runtime_event_log_path,
        event_type="next_cycle_derived",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(cycle_index),
        stage_id=str(dict(next_step.get("selected_stage", {})).get("stage_id", "")),
        cycle_kind=str(dict(next_step.get("selected_stage", {})).get("cycle_kind", "")),
        next_recommended_cycle=str(next_step.get("next_recommended_cycle", "")),
        next_step_derivation_path=str(paths["next_step_derivation_path"]),
    )
    _event(
        runtime_event_log_path,
        event_type="completion_evaluation_recorded",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(cycle_index),
        completed=bool(completion_evaluation.get("completed", False)),
        reason=str(completion_evaluation.get("reason", "")),
        completion_evaluation_path=str(paths["completion_evaluation_path"]),
    )
    return {
        "planning_evidence": planning_evidence,
        "missing_deliverables": missing_deliverables,
        "next_step": next_step,
        "completion_evaluation": completion_evaluation,
        "artifact_paths": {
            "trusted_planning_evidence_path": str(paths["trusted_planning_evidence_path"]),
            "missing_deliverables_path": str(paths["missing_deliverables_path"]),
            "next_step_derivation_path": str(paths["next_step_derivation_path"]),
            "completion_evaluation_path": str(paths["completion_evaluation_path"]),
            "workspace_artifact_index_path": str(paths["workspace_artifact_index_path"]),
        },
    }


def _invocation_model_for_mode(controller_mode: str) -> str:
    return (
        MULTI_CYCLE_EXECUTION_MODEL
        if str(controller_mode).strip() == "multi_cycle"
        else CYCLE_EXECUTION_MODEL
    )


def _cycle_summary_archive_path(workspace_root: Path, cycle_index: int) -> Path:
    return _workspace_paths(workspace_root)["cycles_root"] / f"cycle_{int(cycle_index):03d}_summary.json"


def _directive_completion_evaluation(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    session: dict[str, Any],
    latest_cycle_summary: dict[str, Any],
) -> dict[str, Any]:
    completion_pack, completion_source = _load_internal_knowledge_pack(
        session=session,
        source_id=INTERNAL_SUCCESSOR_COMPLETION_SOURCE_ID,
        expected_schema_name=SUCCESSOR_COMPLETION_KNOWLEDGE_PACK_SCHEMA_NAME,
        expected_schema_version=SUCCESSOR_COMPLETION_KNOWLEDGE_PACK_SCHEMA_VERSION,
    )
    completion_evaluation = _evaluate_current_objective_completion(
        current_directive=current_directive,
        workspace_root=workspace_root,
        completion_pack=completion_pack,
    )
    return {
        **completion_evaluation,
        "directive_completion_possible": bool(completion_pack),
        "fallback_used": not bool(completion_source.get("loaded", False)),
        "latest_cycle_kind": str(latest_cycle_summary.get("cycle_kind", "")).strip(),
        "knowledge_pack_source": completion_source,
    }


def _augment_cycle_payloads(
    *,
    payload: dict[str, Any],
    workspace_root: Path,
    cycle_index: int,
    controller_mode: str,
    latest_cycle_summary: dict[str, Any],
    completion_evaluation: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    invocation_model = _invocation_model_for_mode(controller_mode)
    summary_artifact_path = str(
        dict(payload.get("work_cycle", {})).get("summary_artifact_path", "")
    ).strip() or str(_workspace_paths(workspace_root)["summary_path"])
    cycle_archive_path = _cycle_summary_archive_path(workspace_root, cycle_index)
    augmented_summary = {
        **dict(latest_cycle_summary),
        "cycle_index": int(cycle_index),
        "invocation_model": invocation_model,
        "controller_mode": str(controller_mode),
        "cycle_summary_archive_path": str(cycle_archive_path),
        "directive_completion_evaluation": completion_evaluation,
    }
    cycle_archive_path.parent.mkdir(parents=True, exist_ok=True)
    Path(summary_artifact_path).write_text(_dump(augmented_summary), encoding="utf-8")
    cycle_archive_path.write_text(_dump(augmented_summary), encoding="utf-8")

    work_cycle = {
        **dict(payload.get("work_cycle", {})),
        "cycle_index": int(cycle_index),
        "invocation_model": invocation_model,
        "controller_mode": str(controller_mode),
        "cycle_summary_archive_path": str(cycle_archive_path),
        "directive_completion_evaluation": completion_evaluation,
    }
    updated_payload = {
        **dict(payload),
        "work_cycle": work_cycle,
    }
    return updated_payload, augmented_summary, str(cycle_archive_path)


def _implementation_module_source(*, directive_id: str) -> str:
    return (
        dedent(
            f'''
            """Workspace-local helper for bounded successor review.

            Generated during a governed implementation-bearing cycle for
            `{directive_id}`.
            """

            from __future__ import annotations

            from dataclasses import asdict, dataclass
            from pathlib import Path
            from typing import Iterable


            KNOWN_WORKSPACE_CATEGORIES = ("plans", "docs", "src", "tests", "artifacts", "other")


            @dataclass(frozen=True)
            class WorkspaceArtifactRecord:
                relative_path: str
                category: str
                size_bytes: int


            def classify_workspace_artifact(relative_path: str) -> str:
                parts = [part for part in Path(relative_path).parts if part not in {{'.'}}]
                if not parts:
                    return "other"
                root = parts[0]
                if root in KNOWN_WORKSPACE_CATEGORIES[:-1]:
                    return root
                return "other"


            def iter_workspace_artifact_records(workspace_root: str | Path) -> list[WorkspaceArtifactRecord]:
                root = Path(workspace_root)
                if not root.exists():
                    return []
                records: list[WorkspaceArtifactRecord] = []
                for path in sorted(root.rglob("*")):
                    if not path.is_file():
                        continue
                    relative_path = path.relative_to(root).as_posix()
                    records.append(
                        WorkspaceArtifactRecord(
                            relative_path=relative_path,
                            category=classify_workspace_artifact(relative_path),
                            size_bytes=path.stat().st_size,
                        )
                    )
                return records


            def recommend_next_cycle(records: Iterable[WorkspaceArtifactRecord]) -> str:
                record_list = list(records)
                has_python_source = any(
                    record.category == "src" and record.relative_path.endswith(".py")
                    for record in record_list
                )
                has_python_tests = any(
                    record.category == "tests" and record.relative_path.endswith(".py")
                    for record in record_list
                )
                has_continuation_gap_analysis = any(
                    record.relative_path == "plans/successor_continuation_gap_analysis.md"
                    for record in record_list
                )
                has_successor_readiness_bundle = all(
                    any(record.relative_path == relative_path for record in record_list)
                    for relative_path in (
                        "src/successor_shell/successor_manifest.py",
                        "tests/test_successor_manifest.py",
                        "docs/successor_package_readiness_note.md",
                        "artifacts/successor_readiness_evaluation_latest.json",
                        "artifacts/successor_delivery_manifest_latest.json",
                    )
                )
                if has_successor_readiness_bundle:
                    return "operator_review_required"
                if has_continuation_gap_analysis:
                    return "materialize_successor_package_readiness_bundle"
                if has_python_source and has_python_tests:
                    return "plan_successor_package_gap_closure"
                if has_python_source:
                    return "add_workspace_local_tests"
                return "materialize_workspace_local_implementation"


            def build_workspace_artifact_index(workspace_root: str | Path) -> dict[str, object]:
                records = iter_workspace_artifact_records(workspace_root)
                category_counts: dict[str, int] = {{}}
                for record in records:
                    category_counts[record.category] = category_counts.get(record.category, 0) + 1
                return {{
                    "workspace_root": str(Path(workspace_root)),
                    "artifact_count": len(records),
                    "category_counts": category_counts,
                    "artifacts": [asdict(record) for record in records],
                    "next_recommended_cycle": recommend_next_cycle(records),
                }}


            def render_workspace_artifact_report(workspace_root: str | Path) -> str:
                index = build_workspace_artifact_index(workspace_root)
                lines = [
                    "Workspace Artifact Index",
                    "",
                    f"Workspace root: {{index['workspace_root']}}",
                    f"Artifact count: {{index['artifact_count']}}",
                    f"Next recommended cycle: {{index['next_recommended_cycle']}}",
                    "",
                    "Categories:",
                ]
                for category, count in sorted(dict(index["category_counts"]).items()):
                    lines.append(f"- {{category}}: {{count}}")
                return "\\n".join(lines)
            '''
        ).strip()
        + "\n"
    )


def _implementation_init_source(*, include_readiness_helpers: bool = False) -> str:
    readiness_import_block = ""
    readiness_exports = ""
    if include_readiness_helpers:
        readiness_import_block = (
            "from .successor_manifest import (\n"
            "    build_successor_delivery_manifest,\n"
            "    render_successor_readiness_report,\n"
            ")\n"
        )
        readiness_exports = (
            '    "build_successor_delivery_manifest",\n'
            '    "render_successor_readiness_report",\n'
        )
    return (
        dedent(
            f"""
            \"\"\"Workspace-local successor shell helpers.\"\"\"

            from .workspace_contract import (
                build_workspace_artifact_index,
                classify_workspace_artifact,
                recommend_next_cycle,
                render_workspace_artifact_report,
            )
            {readiness_import_block}

            __all__ = [
                "build_workspace_artifact_index",
                "classify_workspace_artifact",
                "recommend_next_cycle",
                "render_workspace_artifact_report",
{readiness_exports.rstrip()}
            ]
            """
        ).strip()
        + "\n"
    )


def _implementation_test_source() -> str:
    return (
        dedent(
            """
            from __future__ import annotations

            import importlib.util
            import sys
            import tempfile
            import unittest
            from pathlib import Path


            def _load_workspace_contract_module():
                module_path = Path(__file__).resolve().parents[1] / "src" / "successor_shell" / "workspace_contract.py"
                spec = importlib.util.spec_from_file_location("workspace_contract", module_path)
                if spec is None or spec.loader is None:
                    raise RuntimeError(f"Unable to load workspace contract module from {module_path}")
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                return module


            class WorkspaceContractTests(unittest.TestCase):
                def test_build_workspace_artifact_index_groups_workspace_outputs(self) -> None:
                    module = _load_workspace_contract_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        (root / "plans").mkdir(parents=True, exist_ok=True)
                        (root / "src").mkdir(parents=True, exist_ok=True)
                        (root / "tests").mkdir(parents=True, exist_ok=True)
                        (root / "plans" / "bounded_work_cycle_plan.md").write_text("plan", encoding="utf-8")
                        (root / "src" / "module.py").write_text("print('ok')\\n", encoding="utf-8")
                        (root / "tests" / "test_module.py").write_text("assert True\\n", encoding="utf-8")

                        index = module.build_workspace_artifact_index(root)

                        self.assertEqual(index["category_counts"]["plans"], 1)
                        self.assertEqual(index["category_counts"]["src"], 1)
                        self.assertEqual(index["category_counts"]["tests"], 1)
                        self.assertEqual(
                            index["next_recommended_cycle"],
                            "plan_successor_package_gap_closure",
                        )

                def test_render_workspace_artifact_report_mentions_workspace_root(self) -> None:
                    module = _load_workspace_contract_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        (root / "artifacts").mkdir(parents=True, exist_ok=True)
                        (root / "artifacts" / "summary.json").write_text("{}", encoding="utf-8")

                        report = module.render_workspace_artifact_report(root)

                        self.assertIn("Workspace Artifact Index", report)
                        self.assertIn(str(root), report)


            if __name__ == "__main__":
                unittest.main()
            """
        ).strip()
        + "\n"
    )


def _implementation_note_text(
    *,
    directive_id: str,
    workspace_id: str,
    implementation_bundle_kind: str,
    deferred_items: list[dict[str, str]],
) -> str:
    return (
        "\n".join(
            [
                "# Successor Shell Iteration Notes",
                "",
                f"Directive ID: `{directive_id}`",
                f"Workspace: `{workspace_id}`",
                f"Implementation bundle: `{implementation_bundle_kind}`",
                "",
                "This cycle advances the workspace from planning-only artifacts into a small real implementation bundle.",
                "",
                "Implemented now:",
                "- a workspace-local Python package export under `src/successor_shell/`",
                "- a real artifact-index and review helper module under `src/successor_shell/workspace_contract.py`",
                "- an executable regression module under `tests/test_workspace_contract.py`",
                "- operator-readable JSON summaries for the implementation bundle and workspace artifact index",
                "",
                "Still deferred:",
                *[f"- {item['item']}: {item['reason']}" for item in deferred_items],
                "",
            ]
        )
        + "\n"
    )


def _continuation_gap_analysis_text(
    *,
    directive_id: str,
    workspace_id: str,
    missing_deliverables: list[dict[str, Any]],
    next_step: dict[str, Any],
) -> str:
    selected_stage = dict(next_step.get("selected_stage", {}))
    lines = [
        "# Successor Continuation Gap Analysis",
        "",
        f"Directive ID: `{directive_id}`",
        f"Workspace: `{workspace_id}`",
        "",
        "This planning cycle consulted internal trusted-source knowledge packs and current workspace artifacts",
        "to determine what bounded successor deliverables still remain inside the active workspace.",
        "",
        "Missing deliverables:",
    ]
    if missing_deliverables:
        lines.extend(
            [
                f"- `{str(item.get('deliverable_id', ''))}`: "
                + ", ".join(str(path) for path in list(item.get("missing_evidence_relative_paths", [])))
                for item in missing_deliverables
            ]
        )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "Selected next bounded step:",
            f"- stage: `{str(selected_stage.get('stage_id', '') or '<none>')}`",
            f"- cycle kind: `{str(selected_stage.get('cycle_kind', '') or '<none>')}`",
            f"- next recommended cycle: `{str(next_step.get('next_recommended_cycle', '') or '<none>')}`",
            f"- rationale: {str(next_step.get('reason', '') or '<none recorded>')}",
            "",
            "This remains bounded mutable-shell planning only. Protected-surface mutation remains excluded.",
            "",
        ]
    )
    return "\n".join(lines)


def _successor_manifest_source() -> str:
    return (
        dedent(
            """
            \"\"\"Workspace-local successor readiness helpers.\"\"\"

            from __future__ import annotations

            from pathlib import Path


            REQUIRED_SUCCESSOR_DELIVERABLES = (
                "plans/bounded_work_cycle_plan.md",
                "docs/mutable_shell_successor_design_note.md",
                "src/successor_shell/workspace_contract.py",
                "tests/test_workspace_contract.py",
                "plans/successor_continuation_gap_analysis.md",
                "docs/successor_package_readiness_note.md",
            )


            def build_successor_delivery_manifest(workspace_root: str | Path) -> dict[str, object]:
                root = Path(workspace_root)
                deliverables = []
                for relative_path in REQUIRED_SUCCESSOR_DELIVERABLES:
                    path = root / relative_path
                    deliverables.append(
                        {
                            "relative_path": relative_path,
                            "present": path.exists(),
                            "absolute_path": str(path),
                        }
                    )
                return {
                    "workspace_root": str(root),
                    "deliverables": deliverables,
                    "completion_ready": all(item["present"] for item in deliverables),
                }


            def render_successor_readiness_report(workspace_root: str | Path) -> str:
                manifest = build_successor_delivery_manifest(workspace_root)
                lines = [
                    "Successor Readiness Report",
                    "",
                    f"Workspace root: {manifest['workspace_root']}",
                    f"Completion ready: {manifest['completion_ready']}",
                    "",
                    "Deliverables:",
                ]
                for item in manifest["deliverables"]:
                    marker = "present" if item["present"] else "missing"
                    lines.append(f"- {marker}: {item['relative_path']}")
                return "\\n".join(lines)
            """
        ).strip()
        + "\n"
    )


def _successor_manifest_test_source() -> str:
    return (
        dedent(
            """
            from __future__ import annotations

            import importlib.util
            import sys
            import tempfile
            import unittest
            from pathlib import Path


            def _load_successor_manifest_module():
                module_path = Path(__file__).resolve().parents[1] / "src" / "successor_shell" / "successor_manifest.py"
                spec = importlib.util.spec_from_file_location("successor_manifest", module_path)
                if spec is None or spec.loader is None:
                    raise RuntimeError(f"Unable to load successor manifest module from {module_path}")
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                return module


            class SuccessorManifestTests(unittest.TestCase):
                def test_build_successor_delivery_manifest_marks_missing_files(self) -> None:
                    module = _load_successor_manifest_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        (root / "plans").mkdir(parents=True, exist_ok=True)
                        (root / "plans" / "bounded_work_cycle_plan.md").write_text("plan", encoding="utf-8")

                        manifest = module.build_successor_delivery_manifest(root)

                        self.assertFalse(manifest["completion_ready"])
                        self.assertTrue(any(item["relative_path"] == "plans/bounded_work_cycle_plan.md" for item in manifest["deliverables"]))

                def test_render_successor_readiness_report_mentions_completion_ready(self) -> None:
                    module = _load_successor_manifest_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        report = module.render_successor_readiness_report(root)
                        self.assertIn("Successor Readiness Report", report)
                        self.assertIn("Completion ready:", report)


            if __name__ == "__main__":
                unittest.main()
            """
        ).strip()
        + "\n"
    )


def _readiness_note_text(
    *,
    directive_id: str,
    workspace_id: str,
    deferred_items: list[dict[str, str]],
) -> str:
    return (
        "\n".join(
            [
                "# Successor Package Readiness Note",
                "",
                f"Directive ID: `{directive_id}`",
                f"Workspace: `{workspace_id}`",
                "",
                "This implementation-bearing cycle materializes a bounded successor readiness bundle",
                "inside the active workspace only.",
                "",
                "Implemented now:",
                "- `src/successor_shell/successor_manifest.py`",
                "- `tests/test_successor_manifest.py`",
                "- `docs/successor_package_readiness_note.md`",
                "- `artifacts/successor_readiness_evaluation_latest.json`",
                "- `artifacts/successor_delivery_manifest_latest.json`",
                "",
                "Still deferred:",
                *[f"- {item['item']}: {item['reason']}" for item in deferred_items],
                "",
            ]
        )
        + "\n"
    )


def _select_planning_work_item(current_directive: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    skipped = [
        {
            "work_item_id": "protected_surface_rewrite_candidate",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        }
    ]
    admissible = sorted(
        {
            str(item).strip()
            for item in list(current_directive.get("allowed_action_classes", []))
            if str(item).strip()
        }
        & SUPPORTED_FIRST_WORK_ACTION_CLASSES
    )
    text = str(current_directive.get("directive_text", "")).strip()
    clarified = str(current_directive.get("clarified_intent_summary", "")).strip()
    if not text and not clarified:
        skipped.append(
            {
                "work_item_id": "bounded_successor_workspace_bundle",
                "reason": "directive text and clarified intent summary are missing",
            }
        )
        return None, skipped
    if not admissible:
        skipped.append(
            {
                "work_item_id": "bounded_successor_workspace_bundle",
                "reason": "no admissible first-cycle action classes are enabled",
            }
        )
        return None, skipped
    return (
        {
            "work_item_id": "bounded_successor_workspace_bundle",
            "title": "Produce a bounded successor-planning bundle inside the active workspace.",
            "selected_action_classes": admissible,
            "rationale": "start with workspace-local planning, design, and scaffold outputs only",
            "cycle_kind": "planning_only",
        },
        skipped,
    )


def _select_implementation_work_item(
    current_directive: dict[str, Any],
    *,
    baseline: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    skipped = [
        {
            "work_item_id": "protected_surface_rewrite_candidate",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        }
    ]
    admissible = sorted(
        {
            str(item).strip()
            for item in list(current_directive.get("allowed_action_classes", []))
            if str(item).strip()
        }
        & SUPPORTED_FIRST_WORK_ACTION_CLASSES
    )
    if not baseline.get("has_planning_baseline", False):
        skipped.append(
            {
                "work_item_id": "implementation_bundle_workspace_contract",
                "reason": "planning baseline artifacts are missing from the active workspace",
            }
        )
        return None, skipped
    if not admissible:
        skipped.append(
            {
                "work_item_id": "implementation_bundle_workspace_contract",
                "reason": "no admissible implementation-cycle action classes are enabled",
            }
        )
        return None, skipped
    if baseline.get("implementation_materialized", False):
        skipped.append(
            {
                "work_item_id": "implementation_bundle_workspace_contract",
                "reason": "the first implementation bundle already exists; further implementation is deferred to a later reviewed cycle",
            }
        )
        return None, skipped
    return (
        {
            "work_item_id": "implementation_bundle_workspace_contract",
            "title": "Materialize a workspace-local artifact contract and review helper bundle.",
            "selected_action_classes": admissible,
            "rationale": "build a small real code/test bundle directly from the existing planning baseline",
            "implementation_bundle_kind": "workspace_artifact_contract",
            "cycle_kind": "implementation_bearing",
        },
        skipped,
    )


def _select_continuation_planning_work_item(
    current_directive: dict[str, Any],
    *,
    planning_context: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    skipped = [
        {
            "work_item_id": "protected_surface_rewrite_candidate",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        }
    ]
    admissible = sorted(
        {
            str(item).strip()
            for item in list(current_directive.get("allowed_action_classes", []))
            if str(item).strip()
        }
        & SUPPORTED_FIRST_WORK_ACTION_CLASSES
    )
    selected_stage = dict(dict(planning_context.get("next_step", {})).get("selected_stage", {}))
    if str(selected_stage.get("stage_id", "")).strip() != "continuation_gap_analysis":
        skipped.append(
            {
                "work_item_id": "successor_continuation_gap_analysis",
                "reason": "continuation gap analysis is not the currently selected bounded next stage",
            }
        )
        return None, skipped
    if not admissible:
        skipped.append(
            {
                "work_item_id": "successor_continuation_gap_analysis",
                "reason": "no admissible continuation-planning action classes are enabled",
            }
        )
        return None, skipped
    return (
        {
            "work_item_id": "successor_continuation_gap_analysis",
            "title": "Produce a trusted-evidence continuation gap analysis for the bounded successor workspace.",
            "selected_action_classes": admissible,
            "rationale": str(dict(planning_context.get("next_step", {})).get("reason", "")),
            "cycle_kind": "planning_only",
        },
        skipped,
    )


def _select_readiness_implementation_work_item(
    current_directive: dict[str, Any],
    *,
    planning_context: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    skipped = [
        {
            "work_item_id": "protected_surface_rewrite_candidate",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        }
    ]
    admissible = sorted(
        {
            str(item).strip()
            for item in list(current_directive.get("allowed_action_classes", []))
            if str(item).strip()
        }
        & SUPPORTED_FIRST_WORK_ACTION_CLASSES
    )
    selected_stage = dict(dict(planning_context.get("next_step", {})).get("selected_stage", {}))
    if str(selected_stage.get("stage_id", "")).strip() != "successor_readiness_bundle":
        skipped.append(
            {
                "work_item_id": "successor_readiness_bundle",
                "reason": "successor readiness bundle is not the currently selected bounded next stage",
            }
        )
        return None, skipped
    if not admissible:
        skipped.append(
            {
                "work_item_id": "successor_readiness_bundle",
                "reason": "no admissible readiness-implementation action classes are enabled",
            }
        )
        return None, skipped
    return (
        {
            "work_item_id": "successor_readiness_bundle",
            "title": "Materialize a bounded successor readiness bundle inside the active workspace.",
            "selected_action_classes": admissible,
            "rationale": str(dict(planning_context.get("next_step", {})).get("reason", "")),
            "implementation_bundle_kind": "successor_package_readiness_bundle",
            "cycle_kind": "implementation_bearing",
        },
        skipped,
    )


def _finalize_session_artifacts(
    *,
    payload: dict[str, Any],
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    brief_lines: list[str],
) -> None:
    session_text = _dump(payload)
    session_artifact_path.write_text(session_text, encoding="utf-8")
    session_archive_path.write_text(session_text, encoding="utf-8")
    brief_path.write_text("\n".join(brief_lines).strip() + "\n", encoding="utf-8")


def _complete_no_admissible_work(
    *,
    payload: dict[str, Any],
    workspace_root: Path,
    plans_root: Path,
    summary_path: Path,
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    skipped: list[dict[str, str]],
    reason: str,
    include_implementation_deferred_event: bool = False,
) -> dict[str, Any]:
    explanation_path = plans_root / "no_admissible_bounded_work.md"
    _write_text(
        explanation_path,
        "# No Admissible Bounded Work\n\n- " + "\n- ".join(item["reason"] for item in skipped) + "\n",
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id="no_admissible_bounded_work",
        artifact_kind="no_work_explanation_markdown",
    )
    work_summary = {
        "schema_name": WORK_SUMMARY_SCHEMA_NAME,
        "schema_version": WORK_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "status": "no_admissible_bounded_work",
        "cycle_kind": "no_admissible_bounded_work",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "reason": reason,
        "selected_work_item": {},
        "skipped_work_items": skipped,
        "output_artifact_paths": [str(explanation_path), str(summary_path)],
        "newly_created_paths": [str(explanation_path)],
        "deferred_items": skipped,
        "next_recommended_cycle": "operator_review_required",
    }
    _write_json(
        summary_path,
        work_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id="no_admissible_bounded_work",
        artifact_kind="bounded_work_summary_json",
    )
    payload.update(
        {
            "generated_at": _now(),
            "directive_id": directive_id,
            "status": "no_admissible_bounded_work",
            "reason": reason,
            "work_cycle": {
                "work_item_id": "no_admissible_bounded_work",
                "cycle_kind": "no_admissible_bounded_work",
                "invocation_model": CYCLE_EXECUTION_MODEL,
                "summary_artifact_path": str(summary_path),
                "output_artifact_paths": list(work_summary["output_artifact_paths"]),
                "newly_created_paths": [str(explanation_path)],
                "skipped_work_items": skipped,
                "next_recommended_cycle": "operator_review_required",
            },
        }
    )
    _finalize_session_artifacts(
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=[
            "# Governed Execution Brief",
            "",
            "Status: no_admissible_bounded_work",
            f"Reason: {reason}",
            f"Explanation: {explanation_path}",
        ],
    )
    if include_implementation_deferred_event:
        _event(
            runtime_event_log_path,
            event_type="implementation_bundle_deferred",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            reason=reason,
            explanation_path=str(explanation_path),
        )
    _event(
        runtime_event_log_path,
        event_type="no_admissible_bounded_work",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        explanation_path=str(explanation_path),
        summary_artifact_path=str(summary_path),
    )
    _event(
        runtime_event_log_path,
        event_type="work_loop_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        status="no_admissible_bounded_work",
        output_artifact_paths=list(work_summary["output_artifact_paths"]),
    )
    return payload


def _run_planning_cycle(
    *,
    payload: dict[str, Any],
    current_directive: dict[str, Any],
    workspace_root: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    selected, skipped = _select_planning_work_item(current_directive)
    for item in skipped:
        _event(
            runtime_event_log_path,
            event_type="work_item_skipped",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=str(item.get("work_item_id", "")),
            reason=str(item.get("reason", "")),
        )

    if not selected:
        return _complete_no_admissible_work(
            payload=payload,
            workspace_root=workspace_root,
            plans_root=paths["plans_root"],
            summary_path=paths["summary_path"],
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            skipped=skipped,
            reason="no admissible bounded first work item was available under the current directive and action-class constraints",
        )

    _event(
        runtime_event_log_path,
        event_type="work_item_selected",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        title=str(selected.get("title", "")),
        rationale=str(selected.get("rationale", "")),
        selected_action_classes=list(selected.get("selected_action_classes", [])),
    )
    directive_text = str(current_directive.get("directive_text", "")).strip()
    clarified = str(current_directive.get("clarified_intent_summary", "")).strip()
    constraints = [str(item) for item in list(current_directive.get("constraints", []))]
    trusted_sources = [str(item) for item in list(current_directive.get("trusted_sources", []))]
    success_criteria = [str(item) for item in list(current_directive.get("success_criteria", []))]
    deferred_items = [
        {
            "item": "workspace_local_implementation_bundle",
            "reason": "this first cycle is intentionally planning-only so the next cycle can implement from an explicit baseline",
        },
        {
            "item": "protected_surface_mutation",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        },
    ]

    _write_text(
        paths["plan_path"],
        "\n".join(
            [
                "# Bounded Work Cycle Plan",
                "",
                f"Directive ID: `{directive_id}`",
                f"Workspace: `{workspace_id} -> {workspace_root}`",
                "",
                directive_text or clarified,
                "",
                "Writable roots:",
                *[f"- `{item}`" for item in list(payload.get("allowed_write_roots", []))],
                "",
                "Protected roots:",
                *[f"- `{item}`" for item in list(payload.get("protected_root_hints", []))],
                "",
                "Selected outputs:",
                "- `plans/bounded_work_cycle_plan.md`",
                "- `docs/mutable_shell_successor_design_note.md`",
                "- `src/README.md`",
                "- `tests/README.md`",
                "- `artifacts/bounded_work_file_plan.json`",
                "- `artifacts/bounded_work_summary_latest.json`",
                "",
            ]
        )
        + "\n",
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="work_plan_markdown",
    )
    _write_text(
        paths["design_path"],
        "\n".join(
            [
                "# Mutable-Shell Successor Design Note",
                "",
                clarified or directive_text,
                "",
                "Binding constraints:",
                *[f"- {item}" for item in constraints],
                "",
                "Trusted sources in scope:",
                *[f"- `{item}`" for item in trusted_sources],
                "",
                "Success criteria carried forward:",
                *[f"- {item}" for item in success_criteria],
                "",
            ]
        )
        + "\n",
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="design_note_markdown",
    )
    _write_text(
        paths["src_readme_path"],
        "# Workspace Source Scaffold\n\nThis area is reserved for bounded mutable-shell implementation work only.\n",
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="src_scaffold_readme",
    )
    _write_text(
        paths["tests_readme_path"],
        "# Workspace Test Scaffold\n\nThis area is reserved for bounded workspace-local regression coverage only.\n",
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="tests_scaffold_readme",
    )
    file_plan = {
        "schema_name": FILE_PLAN_SCHEMA_NAME,
        "schema_version": FILE_PLAN_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "planned_files": [
            {
                "relative_path": "src/successor_shell/__init__.py",
                "purpose": "workspace-local package export for successor shell helpers",
                "status": "proposed_not_created",
            },
            {
                "relative_path": "src/successor_shell/workspace_contract.py",
                "purpose": "workspace-local artifact index and review helper",
                "status": "proposed_not_created",
            },
            {
                "relative_path": "tests/test_workspace_contract.py",
                "purpose": "workspace-local regression coverage for the artifact contract helper",
                "status": "proposed_not_created",
            },
            {
                "relative_path": "docs/successor_shell_iteration_notes.md",
                "purpose": "implementation-bearing cycle note and deferred-item summary",
                "status": "proposed_not_created",
            },
        ],
        "protected_surfaces_excluded_by_default": [
            "main.py",
            "theory/nined_core.py",
            "routing logic",
            "thresholds",
            "live policy",
            "benchmark semantics",
        ],
    }
    _write_json(
        paths["file_plan_path"],
        file_plan,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="file_plan_json",
    )

    output_paths = [
        str(paths["plan_path"]),
        str(paths["design_path"]),
        str(paths["src_readme_path"]),
        str(paths["tests_readme_path"]),
        str(paths["file_plan_path"]),
        str(paths["trusted_planning_evidence_path"]),
        str(paths["missing_deliverables_path"]),
        str(paths["next_step_derivation_path"]),
        str(paths["completion_evaluation_path"]),
        str(paths["summary_path"]),
    ]
    work_summary = {
        "schema_name": WORK_SUMMARY_SCHEMA_NAME,
        "schema_version": WORK_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "status": "work_completed",
        "cycle_kind": "planning_only",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "reason": "completed one bounded successor-planning work cycle inside the active workspace",
        "selected_work_item": selected,
        "skipped_work_items": skipped,
        "output_artifact_paths": output_paths,
        "newly_created_paths": [
            str(paths["plan_path"]),
            str(paths["design_path"]),
            str(paths["src_readme_path"]),
            str(paths["tests_readme_path"]),
            str(paths["file_plan_path"]),
        ],
        "deferred_items": deferred_items,
        "next_recommended_cycle": "materialize_workspace_local_implementation",
    }
    _write_json(
        paths["summary_path"],
        work_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="bounded_work_summary_json",
    )
    payload.update(
        {
            "generated_at": _now(),
            "directive_id": directive_id,
            "status": "work_completed",
            "reason": work_summary["reason"],
            "work_cycle": {
                "work_item_id": str(selected.get("work_item_id", "")),
                "title": str(selected.get("title", "")),
                "cycle_kind": "planning_only",
                "invocation_model": CYCLE_EXECUTION_MODEL,
                "summary_artifact_path": str(paths["summary_path"]),
                "output_artifact_paths": output_paths,
                "newly_created_paths": work_summary["newly_created_paths"],
                "skipped_work_items": skipped,
                "next_recommended_cycle": "materialize_workspace_local_implementation",
            },
        }
    )
    _finalize_session_artifacts(
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=[
            "# Governed Execution Brief",
            "",
            f"Status: {payload['status']}",
            f"Directive ID: `{directive_id}`",
            f"Workspace: `{workspace_id} -> {workspace_root}`",
            "",
            "Outputs:",
            *[f"- `{item}`" for item in output_paths],
        ],
    )
    _event(
        runtime_event_log_path,
        event_type="work_loop_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        status="work_completed",
        cycle_kind="planning_only",
        work_item_id=str(selected.get("work_item_id", "")),
        output_artifact_paths=output_paths,
        summary_artifact_path=str(paths["summary_path"]),
    )
    return payload


def _run_implementation_cycle(
    *,
    payload: dict[str, Any],
    current_directive: dict[str, Any],
    workspace_root: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
) -> dict[str, Any]:
    baseline = _workspace_baseline(workspace_root)
    _event(
        runtime_event_log_path,
        event_type="implementation_planning_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        baseline_artifact_paths=list(baseline.get("baseline_artifact_paths", [])),
    )
    selected, skipped = _select_implementation_work_item(current_directive, baseline=baseline)
    for item in skipped:
        _event(
            runtime_event_log_path,
            event_type="work_item_skipped",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=str(item.get("work_item_id", "")),
            reason=str(item.get("reason", "")),
        )

    if not selected:
        return _complete_no_admissible_work(
            payload=payload,
            workspace_root=workspace_root,
            plans_root=baseline["plans_root"],
            summary_path=baseline["summary_path"],
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            skipped=skipped,
            reason="no admissible implementation-bearing work item was available under the current directive, baseline, and action-class constraints",
            include_implementation_deferred_event=True,
        )

    _event(
        runtime_event_log_path,
        event_type="implementation_item_selected",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        title=str(selected.get("title", "")),
        rationale=str(selected.get("rationale", "")),
        implementation_bundle_kind=str(selected.get("implementation_bundle_kind", "")),
        baseline_artifact_paths=list(baseline.get("baseline_artifact_paths", [])),
    )

    baseline["implementation_package_root"].mkdir(parents=True, exist_ok=True)
    deferred_items = [
        {
            "item": "protected_surface_mutation",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        },
        {
            "item": "live_trusted_source_network_queries",
            "reason": "trusted-source live network expansion remains deferred in this cycle",
        },
        {
            "item": "repo_wide_mutation",
            "reason": "this bundle remains bounded to the active workspace and generated/log roots only",
        },
    ]

    _write_text(
        baseline["implementation_init_path"],
        _implementation_init_source(),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_package_init",
    )
    _write_text(
        baseline["implementation_module_path"],
        _implementation_module_source(directive_id=directive_id),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_module_python",
    )
    _write_text(
        baseline["implementation_test_path"],
        _implementation_test_source(),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_test_python",
    )
    _event(
        runtime_event_log_path,
        event_type="test_scaffold_created",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        path=str(baseline["implementation_test_path"]),
        work_item_id=str(selected.get("work_item_id", "")),
    )
    _write_text(
        baseline["implementation_note_path"],
        _implementation_note_text(
            directive_id=directive_id,
            workspace_id=workspace_id,
            implementation_bundle_kind=str(selected.get("implementation_bundle_kind", "")),
            deferred_items=deferred_items,
        ),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_iteration_note_markdown",
    )

    file_plan = load_json(baseline["file_plan_path"])
    planned_files = list(file_plan.get("planned_files", []))
    updated_file_statuses = {
        "src/successor_shell/__init__.py": "created",
        "src/successor_shell/workspace_contract.py": "created",
        "tests/test_workspace_contract.py": "created",
        "docs/successor_shell_iteration_notes.md": "created",
    }
    if not planned_files:
        planned_files = [
            {
                "relative_path": relative_path,
                "purpose": "materialized during the first implementation-bearing workspace cycle",
                "status": status,
            }
            for relative_path, status in updated_file_statuses.items()
        ]
    else:
        seen_paths: set[str] = set()
        for item in planned_files:
            relative_path = str(item.get("relative_path", "")).strip()
            if not relative_path:
                continue
            seen_paths.add(relative_path)
            if relative_path in updated_file_statuses:
                item["status"] = updated_file_statuses[relative_path]
        for relative_path, status in updated_file_statuses.items():
            if relative_path in seen_paths:
                continue
            planned_files.append(
                {
                    "relative_path": relative_path,
                    "purpose": "materialized during the first implementation-bearing workspace cycle",
                    "status": status,
                }
            )
    file_plan["schema_name"] = FILE_PLAN_SCHEMA_NAME
    file_plan["schema_version"] = FILE_PLAN_SCHEMA_VERSION
    file_plan["generated_at"] = _now()
    file_plan["directive_id"] = directive_id
    file_plan["workspace_id"] = workspace_id
    file_plan["planned_files"] = planned_files
    file_plan["protected_surfaces_excluded_by_default"] = file_plan.get(
        "protected_surfaces_excluded_by_default",
        [
            "main.py",
            "theory/nined_core.py",
            "routing logic",
            "thresholds",
            "live policy",
            "benchmark semantics",
        ],
    )
    _write_json(
        baseline["file_plan_path"],
        file_plan,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="file_plan_json",
    )

    workspace_artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    _write_json(
        baseline["workspace_artifact_index_path"],
        workspace_artifact_index,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="workspace_artifact_index_json",
    )

    created_files = [
        str(baseline["implementation_init_path"]),
        str(baseline["implementation_module_path"]),
        str(baseline["implementation_test_path"]),
        str(baseline["implementation_note_path"]),
        str(baseline["workspace_artifact_index_path"]),
    ]
    implementation_summary = {
        "schema_name": IMPLEMENTATION_BUNDLE_SCHEMA_NAME,
        "schema_version": IMPLEMENTATION_BUNDLE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "cycle_kind": "implementation_bearing",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "implementation_bundle_kind": str(selected.get("implementation_bundle_kind", "")),
        "baseline_artifact_paths": list(baseline.get("baseline_artifact_paths", [])),
        "created_files": created_files,
        "deferred_items": deferred_items,
        "next_recommended_cycle": "plan_successor_package_gap_closure",
        "implementation_summary": (
            "Materialized a workspace-local artifact contract helper, executable test module, "
            "iteration note, and artifact index summary without touching protected repo surfaces."
        ),
    }
    _write_json(
        baseline["implementation_summary_path"],
        implementation_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_bundle_summary_json",
    )
    created_files.append(str(baseline["implementation_summary_path"]))

    output_paths = [
        str(baseline["implementation_init_path"]),
        str(baseline["implementation_module_path"]),
        str(baseline["implementation_test_path"]),
        str(baseline["implementation_note_path"]),
        str(baseline["file_plan_path"]),
        str(baseline["workspace_artifact_index_path"]),
        str(baseline["trusted_planning_evidence_path"]),
        str(baseline["missing_deliverables_path"]),
        str(baseline["next_step_derivation_path"]),
        str(baseline["completion_evaluation_path"]),
        str(baseline["implementation_summary_path"]),
        str(baseline["summary_path"]),
    ]
    work_summary = {
        "schema_name": WORK_SUMMARY_SCHEMA_NAME,
        "schema_version": WORK_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "status": "work_completed",
        "cycle_kind": "implementation_bearing",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "implementation_bundle_kind": str(selected.get("implementation_bundle_kind", "")),
        "reason": "completed one bounded implementation-bearing workspace cycle inside the active workspace",
        "selected_work_item": selected,
        "skipped_work_items": skipped,
        "baseline_artifact_paths": list(baseline.get("baseline_artifact_paths", [])),
        "output_artifact_paths": output_paths,
        "newly_created_paths": created_files,
        "deferred_items": deferred_items,
        "next_recommended_cycle": "plan_successor_package_gap_closure",
    }
    _write_json(
        baseline["summary_path"],
        work_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="bounded_work_summary_json",
    )

    payload.update(
        {
            "generated_at": _now(),
            "directive_id": directive_id,
            "status": "work_completed",
            "reason": work_summary["reason"],
            "work_cycle": {
                "work_item_id": str(selected.get("work_item_id", "")),
                "title": str(selected.get("title", "")),
                "cycle_kind": "implementation_bearing",
                "invocation_model": CYCLE_EXECUTION_MODEL,
                "implementation_bundle_kind": str(selected.get("implementation_bundle_kind", "")),
                "summary_artifact_path": str(baseline["summary_path"]),
                "output_artifact_paths": output_paths,
                "newly_created_paths": created_files,
                "skipped_work_items": skipped,
                "deferred_items": deferred_items,
                "next_recommended_cycle": "plan_successor_package_gap_closure",
            },
        }
    )
    _finalize_session_artifacts(
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=[
            "# Governed Execution Brief",
            "",
            f"Status: {payload['status']}",
            f"Directive ID: `{directive_id}`",
            f"Workspace: `{workspace_id} -> {workspace_root}`",
            "Cycle kind: implementation_bearing",
            f"Implementation bundle: `{selected.get('implementation_bundle_kind', '')}`",
            "",
            "Outputs:",
            *[f"- `{item}`" for item in output_paths],
        ],
    )
    _event(
        runtime_event_log_path,
        event_type="implementation_bundle_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        implementation_bundle_kind=str(selected.get("implementation_bundle_kind", "")),
        created_files=created_files,
        summary_artifact_path=str(baseline["summary_path"]),
    )
    _event(
        runtime_event_log_path,
        event_type="work_loop_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        status="work_completed",
        cycle_kind="implementation_bearing",
        work_item_id=str(selected.get("work_item_id", "")),
        output_artifact_paths=output_paths,
        summary_artifact_path=str(baseline["summary_path"]),
    )
    return payload


def _run_continuation_planning_cycle(
    *,
    payload: dict[str, Any],
    current_directive: dict[str, Any],
    workspace_root: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    planning_context: dict[str, Any],
) -> dict[str, Any]:
    baseline = _workspace_baseline(workspace_root)
    selected, skipped = _select_continuation_planning_work_item(
        current_directive,
        planning_context=planning_context,
    )
    for item in skipped:
        _event(
            runtime_event_log_path,
            event_type="work_item_skipped",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=str(item.get("work_item_id", "")),
            reason=str(item.get("reason", "")),
        )

    if not selected:
        return _complete_no_admissible_work(
            payload=payload,
            workspace_root=workspace_root,
            plans_root=baseline["plans_root"],
            summary_path=baseline["summary_path"],
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            skipped=skipped,
            reason="no admissible continuation-planning work item was available under the current directive, workspace state, and trusted planning evidence",
        )

    _event(
        runtime_event_log_path,
        event_type="work_item_selected",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        title=str(selected.get("title", "")),
        rationale=str(selected.get("rationale", "")),
        selected_action_classes=list(selected.get("selected_action_classes", [])),
    )

    missing_deliverables = list(dict(planning_context.get("missing_deliverables", {})).get("missing_required_deliverables", []))
    next_step = dict(planning_context.get("next_step", {}))
    deferred_items = [
        {
            "item": "successor_readiness_bundle",
            "reason": "the trusted planning evidence indicates a further implementation-bearing readiness bundle is still required",
        },
        {
            "item": "protected_surface_mutation",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        },
    ]

    _write_text(
        baseline["continuation_gap_plan_path"],
        _continuation_gap_analysis_text(
            directive_id=directive_id,
            workspace_id=workspace_id,
            missing_deliverables=missing_deliverables,
            next_step=next_step,
        ),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="continuation_gap_analysis_markdown",
    )

    file_plan = load_json(baseline["file_plan_path"])
    planned_files = list(file_plan.get("planned_files", []))
    planned_lookup = {
        str(item.get("relative_path", "")).strip(): item
        for item in planned_files
        if str(item.get("relative_path", "")).strip()
    }
    for relative_path, purpose in (
        ("src/successor_shell/successor_manifest.py", "workspace-local readiness and successor delivery manifest helper"),
        ("tests/test_successor_manifest.py", "workspace-local regression coverage for the successor readiness helper"),
        ("docs/successor_package_readiness_note.md", "readiness bundle note summarizing successor package scope and remaining deferments"),
        ("artifacts/successor_readiness_evaluation_latest.json", "structured readiness evaluation for the bounded successor package"),
        ("artifacts/successor_delivery_manifest_latest.json", "structured successor delivery manifest for operator review"),
    ):
        if relative_path in planned_lookup:
            planned_lookup[relative_path]["status"] = "proposed_not_created"
            continue
        planned_files.append(
            {
                "relative_path": relative_path,
                "purpose": purpose,
                "status": "proposed_not_created",
            }
        )
    file_plan["generated_at"] = _now()
    file_plan["planned_files"] = planned_files
    _write_json(
        baseline["file_plan_path"],
        file_plan,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="file_plan_json",
    )

    workspace_artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    _write_json(
        baseline["workspace_artifact_index_path"],
        workspace_artifact_index,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="workspace_artifact_index_json",
    )

    created_files = [str(baseline["continuation_gap_plan_path"])]
    output_paths = [
        str(baseline["continuation_gap_plan_path"]),
        str(baseline["trusted_planning_evidence_path"]),
        str(baseline["missing_deliverables_path"]),
        str(baseline["next_step_derivation_path"]),
        str(baseline["completion_evaluation_path"]),
        str(baseline["workspace_artifact_index_path"]),
        str(baseline["summary_path"]),
    ]
    work_summary = {
        "schema_name": WORK_SUMMARY_SCHEMA_NAME,
        "schema_version": WORK_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "status": "work_completed",
        "cycle_kind": "planning_only",
        "planning_bundle_kind": "successor_continuation_gap_analysis",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "reason": "completed one trusted-evidence continuation planning cycle inside the active workspace",
        "selected_work_item": selected,
        "skipped_work_items": skipped,
        "output_artifact_paths": output_paths,
        "newly_created_paths": created_files,
        "deferred_items": deferred_items,
        "next_recommended_cycle": "materialize_successor_package_readiness_bundle",
    }
    _write_json(
        baseline["summary_path"],
        work_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="bounded_work_summary_json",
    )
    payload.update(
        {
            "generated_at": _now(),
            "directive_id": directive_id,
            "status": "work_completed",
            "reason": work_summary["reason"],
            "work_cycle": {
                "work_item_id": str(selected.get("work_item_id", "")),
                "title": str(selected.get("title", "")),
                "cycle_kind": "planning_only",
                "planning_bundle_kind": "successor_continuation_gap_analysis",
                "invocation_model": CYCLE_EXECUTION_MODEL,
                "summary_artifact_path": str(baseline["summary_path"]),
                "output_artifact_paths": output_paths,
                "newly_created_paths": created_files,
                "skipped_work_items": skipped,
                "deferred_items": deferred_items,
                "next_recommended_cycle": "materialize_successor_package_readiness_bundle",
            },
        }
    )
    _finalize_session_artifacts(
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=[
            "# Governed Execution Brief",
            "",
            f"Status: {payload['status']}",
            f"Directive ID: `{directive_id}`",
            f"Workspace: `{workspace_id} -> {workspace_root}`",
            "Cycle kind: planning_only",
            "Planning bundle: successor_continuation_gap_analysis",
            "",
            "Outputs:",
            *[f"- `{item}`" for item in output_paths],
        ],
    )
    _event(
        runtime_event_log_path,
        event_type="work_loop_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        status="work_completed",
        cycle_kind="planning_only",
        work_item_id=str(selected.get("work_item_id", "")),
        output_artifact_paths=output_paths,
        summary_artifact_path=str(baseline["summary_path"]),
    )
    return payload


def _run_readiness_implementation_cycle(
    *,
    payload: dict[str, Any],
    current_directive: dict[str, Any],
    workspace_root: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    planning_context: dict[str, Any],
) -> dict[str, Any]:
    baseline = _workspace_baseline(workspace_root)
    _event(
        runtime_event_log_path,
        event_type="implementation_planning_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        baseline_artifact_paths=list(baseline.get("baseline_artifact_paths", [])),
    )
    selected, skipped = _select_readiness_implementation_work_item(
        current_directive,
        planning_context=planning_context,
    )
    for item in skipped:
        _event(
            runtime_event_log_path,
            event_type="work_item_skipped",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=str(item.get("work_item_id", "")),
            reason=str(item.get("reason", "")),
        )

    if not selected:
        return _complete_no_admissible_work(
            payload=payload,
            workspace_root=workspace_root,
            plans_root=baseline["plans_root"],
            summary_path=baseline["summary_path"],
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            skipped=skipped,
            reason="no admissible readiness implementation bundle was available under the current directive, workspace state, and trusted planning evidence",
            include_implementation_deferred_event=True,
        )

    _event(
        runtime_event_log_path,
        event_type="implementation_item_selected",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        title=str(selected.get("title", "")),
        rationale=str(selected.get("rationale", "")),
        implementation_bundle_kind=str(selected.get("implementation_bundle_kind", "")),
        baseline_artifact_paths=list(baseline.get("baseline_artifact_paths", [])),
    )

    deferred_items = [
        {
            "item": "protected_surface_mutation",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        },
        {
            "item": "live_trusted_source_network_queries",
            "reason": "trusted-source live network expansion remains deferred in this cycle",
        },
        {
            "item": "repo_wide_mutation",
            "reason": "this bundle remains bounded to the active workspace and generated/log roots only",
        },
    ]

    _write_text(
        baseline["implementation_init_path"],
        _implementation_init_source(include_readiness_helpers=True),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_package_init",
    )
    _write_text(
        baseline["readiness_module_path"],
        _successor_manifest_source(),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="successor_manifest_python",
    )
    _write_text(
        baseline["readiness_test_path"],
        _successor_manifest_test_source(),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="successor_manifest_test_python",
    )
    _event(
        runtime_event_log_path,
        event_type="test_scaffold_created",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        path=str(baseline["readiness_test_path"]),
        work_item_id=str(selected.get("work_item_id", "")),
    )
    _write_text(
        baseline["readiness_note_path"],
        _readiness_note_text(
            directive_id=directive_id,
            workspace_id=workspace_id,
            deferred_items=deferred_items,
        ),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="successor_readiness_note_markdown",
    )

    delivery_manifest = {
        "schema_name": SUCCESSOR_DELIVERY_MANIFEST_SCHEMA_NAME,
        "schema_version": SUCCESSOR_DELIVERY_MANIFEST_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "deliverables": [
            {
                "relative_path": relative_path,
                "absolute_path": str(workspace_root / relative_path),
                "present": bool((workspace_root / relative_path).exists()),
            }
            for relative_path in (
                "plans/bounded_work_cycle_plan.md",
                "docs/mutable_shell_successor_design_note.md",
                "src/successor_shell/workspace_contract.py",
                "tests/test_workspace_contract.py",
                "plans/successor_continuation_gap_analysis.md",
                "src/successor_shell/successor_manifest.py",
                "tests/test_successor_manifest.py",
                "docs/successor_package_readiness_note.md",
            )
        ],
    }
    delivery_manifest["completion_ready"] = all(
        bool(item.get("present", False)) for item in list(delivery_manifest.get("deliverables", []))
    )
    _write_json(
        baseline["delivery_manifest_path"],
        delivery_manifest,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="successor_delivery_manifest_json",
    )
    readiness_evaluation = {
        "schema_name": SUCCESSOR_READINESS_EVALUATION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_READINESS_EVALUATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "cycle_kind": "implementation_bearing",
        "implementation_bundle_kind": str(selected.get("implementation_bundle_kind", "")),
        "completion_ready": bool(delivery_manifest.get("completion_ready", False)),
        "delivery_manifest_path": str(baseline["delivery_manifest_path"]),
        "created_files": [
            str(baseline["readiness_module_path"]),
            str(baseline["readiness_test_path"]),
            str(baseline["readiness_note_path"]),
            str(baseline["readiness_summary_path"]),
            str(baseline["delivery_manifest_path"]),
        ],
        "deferred_items": deferred_items,
        "next_recommended_cycle": "operator_review_required",
        "readiness_summary": "Materialized the bounded successor readiness bundle inside the active workspace.",
    }
    _write_json(
        baseline["readiness_summary_path"],
        readiness_evaluation,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="successor_readiness_evaluation_json",
    )

    file_plan = load_json(baseline["file_plan_path"])
    planned_files = list(file_plan.get("planned_files", []))
    for item in planned_files:
        relative_path = str(item.get("relative_path", "")).strip()
        if relative_path in {
            "src/successor_shell/successor_manifest.py",
            "tests/test_successor_manifest.py",
            "docs/successor_package_readiness_note.md",
            "artifacts/successor_readiness_evaluation_latest.json",
            "artifacts/successor_delivery_manifest_latest.json",
        }:
            item["status"] = "created"
    file_plan["generated_at"] = _now()
    file_plan["planned_files"] = planned_files
    _write_json(
        baseline["file_plan_path"],
        file_plan,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="file_plan_json",
    )

    workspace_artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    _write_json(
        baseline["workspace_artifact_index_path"],
        workspace_artifact_index,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="workspace_artifact_index_json",
    )

    created_files = [
        str(baseline["readiness_module_path"]),
        str(baseline["readiness_test_path"]),
        str(baseline["readiness_note_path"]),
        str(baseline["readiness_summary_path"]),
        str(baseline["delivery_manifest_path"]),
    ]
    output_paths = [
        str(baseline["implementation_init_path"]),
        str(baseline["readiness_module_path"]),
        str(baseline["readiness_test_path"]),
        str(baseline["readiness_note_path"]),
        str(baseline["trusted_planning_evidence_path"]),
        str(baseline["missing_deliverables_path"]),
        str(baseline["next_step_derivation_path"]),
        str(baseline["completion_evaluation_path"]),
        str(baseline["readiness_summary_path"]),
        str(baseline["delivery_manifest_path"]),
        str(baseline["file_plan_path"]),
        str(baseline["workspace_artifact_index_path"]),
        str(baseline["summary_path"]),
    ]
    work_summary = {
        "schema_name": WORK_SUMMARY_SCHEMA_NAME,
        "schema_version": WORK_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "status": "work_completed",
        "cycle_kind": "implementation_bearing",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "implementation_bundle_kind": str(selected.get("implementation_bundle_kind", "")),
        "reason": "completed one bounded successor readiness implementation cycle inside the active workspace",
        "selected_work_item": selected,
        "skipped_work_items": skipped,
        "output_artifact_paths": output_paths,
        "newly_created_paths": created_files,
        "deferred_items": deferred_items,
        "next_recommended_cycle": "operator_review_required",
    }
    _write_json(
        baseline["summary_path"],
        work_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="bounded_work_summary_json",
    )
    payload.update(
        {
            "generated_at": _now(),
            "directive_id": directive_id,
            "status": "work_completed",
            "reason": work_summary["reason"],
            "work_cycle": {
                "work_item_id": str(selected.get("work_item_id", "")),
                "title": str(selected.get("title", "")),
                "cycle_kind": "implementation_bearing",
                "invocation_model": CYCLE_EXECUTION_MODEL,
                "implementation_bundle_kind": str(selected.get("implementation_bundle_kind", "")),
                "summary_artifact_path": str(baseline["summary_path"]),
                "output_artifact_paths": output_paths,
                "newly_created_paths": created_files,
                "skipped_work_items": skipped,
                "deferred_items": deferred_items,
                "next_recommended_cycle": "operator_review_required",
            },
        }
    )
    _finalize_session_artifacts(
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=[
            "# Governed Execution Brief",
            "",
            f"Status: {payload['status']}",
            f"Directive ID: `{directive_id}`",
            f"Workspace: `{workspace_id} -> {workspace_root}`",
            "Cycle kind: implementation_bearing",
            f"Implementation bundle: `{selected.get('implementation_bundle_kind', '')}`",
            "",
            "Outputs:",
            *[f"- `{item}`" for item in output_paths],
        ],
    )
    _event(
        runtime_event_log_path,
        event_type="implementation_bundle_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        implementation_bundle_kind=str(selected.get("implementation_bundle_kind", "")),
        created_files=created_files,
        summary_artifact_path=str(baseline["summary_path"]),
    )
    _event(
        runtime_event_log_path,
        event_type="work_loop_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        status="work_completed",
        cycle_kind="implementation_bearing",
        work_item_id=str(selected.get("work_item_id", "")),
        output_artifact_paths=output_paths,
        summary_artifact_path=str(baseline["summary_path"]),
    )
    return payload


def _run_promotion_bundle_cycle(
    *,
    payload: dict[str, Any],
    current_directive: dict[str, Any],
    workspace_root: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
) -> dict[str, Any]:
    baseline = _workspace_baseline(workspace_root)
    objective_context = _current_objective_context(
        current_directive=current_directive,
        workspace_root=workspace_root,
    )
    selected = {
        "work_item_id": "successor_candidate_promotion_bundle",
        "title": "Prepare a candidate promotion bundle for operator review.",
        "rationale": "The operator approved the bounded next objective proposed by successor review.",
        "planning_bundle_kind": "candidate_promotion_bundle",
    }
    _event(
        runtime_event_log_path,
        event_type="work_item_selected",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        title=str(selected.get("title", "")),
        rationale=str(selected.get("rationale", "")),
        selected_action_classes=["diagnostic_schema_materialization"],
    )
    review_summary = load_json(baseline["review_summary_path"])
    promotion_recommendation = load_json(baseline["promotion_recommendation_path"])
    next_objective_proposal = load_json(baseline["next_objective_proposal_path"])
    delivery_manifest = load_json(baseline["delivery_manifest_path"])
    readiness_summary = load_json(baseline["readiness_summary_path"])

    note_text = dedent(
        f"""
        # Successor Promotion Bundle Note

        Objective: `{objective_context.get('objective_id', '')}`

        This bounded continuation cycle materialized a candidate promotion bundle inside the
        active workspace so an operator can inspect the completed successor package and its
        lineage without broadening permissions or bypassing review.

        Reviewed successor package:
        - Directive id: `{directive_id}`
        - Workspace id: `{workspace_id}`
        - Review status: `{review_summary.get('review_status', '')}`
        - Promotion recommendation: `{promotion_recommendation.get('promotion_recommendation_state', '')}`
        - Proposal approved from: `{baseline['next_objective_proposal_path']}`

        This bundle remains review-oriented only. It does not promote anything automatically,
        and it does not mutate protected repo surfaces.
        """
    ).strip() + "\n"
    _write_text(
        baseline["promotion_bundle_note_path"],
        note_text,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="successor_promotion_bundle_markdown",
    )
    promotion_bundle_payload = {
        "schema_name": SUCCESSOR_CANDIDATE_PROMOTION_BUNDLE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_CANDIDATE_PROMOTION_BUNDLE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "objective_id": str(objective_context.get("objective_id", "")),
        "objective_source_kind": str(objective_context.get("source_kind", "")),
        "review_summary_path": str(baseline["review_summary_path"]),
        "promotion_recommendation_path": str(baseline["promotion_recommendation_path"]),
        "next_objective_proposal_path": str(baseline["next_objective_proposal_path"]),
        "continuation_lineage_path": str(baseline["continuation_lineage_path"]),
        "delivery_manifest_path": str(baseline["delivery_manifest_path"]),
        "readiness_summary_path": str(baseline["readiness_summary_path"]),
        "completion_ready": bool(readiness_summary.get("completion_ready", False)),
        "bundle_items": [
            str(baseline["promotion_bundle_note_path"]),
            str(baseline["promotion_bundle_manifest_path"]),
            str(baseline["review_summary_path"]),
            str(baseline["promotion_recommendation_path"]),
            str(baseline["next_objective_proposal_path"]),
            str(baseline["continuation_lineage_path"]),
        ],
        "delivery_manifest_deliverables": list(delivery_manifest.get("deliverables", [])),
        "operator_review_required": True,
        "automatic_promotion_permitted": False,
        "next_recommended_cycle": "operator_review_required",
    }
    _write_json(
        baseline["promotion_bundle_manifest_path"],
        promotion_bundle_payload,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="successor_candidate_promotion_bundle_json",
    )
    workspace_artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    _write_json(
        baseline["workspace_artifact_index_path"],
        workspace_artifact_index,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="workspace_artifact_index_json",
    )
    created_files = [
        str(baseline["promotion_bundle_note_path"]),
        str(baseline["promotion_bundle_manifest_path"]),
    ]
    output_paths = [
        str(baseline["promotion_bundle_note_path"]),
        str(baseline["promotion_bundle_manifest_path"]),
        str(baseline["workspace_artifact_index_path"]),
        str(baseline["summary_path"]),
    ]
    deferred_items = [
        {
            "item": "automatic_promotion",
            "reason": "promotion remains operator-reviewed and is not executed automatically in this slice",
        },
        {
            "item": "protected_surface_mutation",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        },
    ]
    work_summary = {
        "schema_name": WORK_SUMMARY_SCHEMA_NAME,
        "schema_version": WORK_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "status": "work_completed",
        "cycle_kind": "planning_only",
        "planning_bundle_kind": "candidate_promotion_bundle",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "reason": "completed one bounded promotion-bundle cycle inside the active workspace",
        "selected_work_item": selected,
        "skipped_work_items": [],
        "output_artifact_paths": output_paths,
        "newly_created_paths": created_files,
        "deferred_items": deferred_items,
        "next_recommended_cycle": "operator_review_required",
    }
    _write_json(
        baseline["summary_path"],
        work_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="bounded_work_summary_json",
    )
    payload.update(
        {
            "generated_at": _now(),
            "directive_id": directive_id,
            "status": "work_completed",
            "reason": work_summary["reason"],
            "work_cycle": {
                "work_item_id": str(selected.get("work_item_id", "")),
                "title": str(selected.get("title", "")),
                "cycle_kind": "planning_only",
                "planning_bundle_kind": "candidate_promotion_bundle",
                "invocation_model": CYCLE_EXECUTION_MODEL,
                "summary_artifact_path": str(baseline["summary_path"]),
                "output_artifact_paths": output_paths,
                "newly_created_paths": created_files,
                "skipped_work_items": [],
                "deferred_items": deferred_items,
                "next_recommended_cycle": "operator_review_required",
            },
        }
    )
    _finalize_session_artifacts(
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=[
            "# Governed Execution Brief",
            "",
            f"Status: {payload['status']}",
            f"Directive ID: `{directive_id}`",
            f"Workspace: `{workspace_id} -> {workspace_root}`",
            "Cycle kind: planning_only",
            "Planning bundle: candidate_promotion_bundle",
            "",
            "Outputs:",
            *[f"- `{item}`" for item in output_paths],
        ],
    )
    _event(
        runtime_event_log_path,
        event_type="work_loop_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        status="work_completed",
        cycle_kind="planning_only",
        work_item_id=str(selected.get("work_item_id", "")),
        output_artifact_paths=output_paths,
        summary_artifact_path=str(baseline["summary_path"]),
    )
    return payload


def run_initial_bounded_workspace_work(
    *,
    bootstrap_summary: dict[str, Any],
    session: dict[str, Any],
    payload: dict[str, Any],
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    planning_context: dict[str, Any],
    cycle_index: int,
) -> dict[str, Any]:
    workspace_root = Path(str(payload.get("workspace_root", "")))
    paths = _workspace_paths(workspace_root)
    for root in (
        paths["docs_root"],
        paths["src_root"],
        paths["tests_root"],
        paths["artifacts_root"],
        paths["plans_root"],
    ):
        root.mkdir(parents=True, exist_ok=True)

    runtime_event_log_path = Path(str(payload.get("runtime_event_log_path", "")).strip())
    directive_state_path = Path(str(dict(bootstrap_summary.get("artifact_paths", {})).get("directive_state", "")).strip())
    current_directive = dict(load_json(directive_state_path).get("current_directive_state", {}))
    directive_id = str(current_directive.get("directive_id", payload.get("directive_id", ""))).strip() or str(payload.get("directive_id", ""))
    execution_profile = str(payload.get("execution_profile", "")).strip()
    workspace_id = str(payload.get("workspace_id", "")).strip()
    session_id = str(session.get("session_id", ""))

    _event(
        runtime_event_log_path,
        event_type="governed_execution_planning_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(cycle_index),
        directive_state_path=str(directive_state_path),
    )

    stage_id = str(dict(dict(planning_context.get("next_step", {})).get("selected_stage", {})).get("stage_id", "")).strip()
    if stage_id == "initial_planning_bundle":
        return _run_planning_cycle(
            payload=payload,
            current_directive=current_directive,
            workspace_root=workspace_root,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
        )
    if stage_id == "first_implementation_bundle":
        return _run_implementation_cycle(
            payload=payload,
            current_directive=current_directive,
            workspace_root=workspace_root,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
        )
    if stage_id == "continuation_gap_analysis":
        return _run_continuation_planning_cycle(
            payload=payload,
            current_directive=current_directive,
            workspace_root=workspace_root,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            planning_context=planning_context,
        )
    if stage_id == "successor_readiness_bundle":
        return _run_readiness_implementation_cycle(
            payload=payload,
            current_directive=current_directive,
            workspace_root=workspace_root,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            planning_context=planning_context,
        )
    if stage_id == "candidate_promotion_bundle":
        return _run_promotion_bundle_cycle(
            payload=payload,
            current_directive=current_directive,
            workspace_root=workspace_root,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
        )
    return _complete_no_admissible_work(
        payload=payload,
        workspace_root=workspace_root,
        plans_root=paths["plans_root"],
        summary_path=paths["summary_path"],
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        skipped=[
            {
                "work_item_id": "governed_execution_stage_selection",
                "reason": str(dict(planning_context.get("next_step", {})).get("reason", "")).strip()
                or "no admissible stage was selected from the trusted planning evidence",
            }
        ],
        reason="no admissible bounded work stage was selected from trusted planning evidence",
    )


def run_governed_workspace_work_controller(
    *,
    bootstrap_summary: dict[str, Any],
    session: dict[str, Any],
    payload: dict[str, Any],
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    controller_mode: str,
    max_cycles_per_invocation: int,
) -> dict[str, Any]:
    workspace_root = Path(str(payload.get("workspace_root", "")))
    paths = _workspace_paths(workspace_root)
    for root in (
        paths["docs_root"],
        paths["src_root"],
        paths["tests_root"],
        paths["artifacts_root"],
        paths["plans_root"],
        paths["cycles_root"],
    ):
        root.mkdir(parents=True, exist_ok=True)

    runtime_event_log_path = Path(str(payload.get("runtime_event_log_path", "")).strip())
    directive_state_path = Path(
        str(dict(bootstrap_summary.get("artifact_paths", {})).get("directive_state", "")).strip()
    )
    current_directive = dict(load_json(directive_state_path).get("current_directive_state", {}))
    directive_id = (
        str(current_directive.get("directive_id", payload.get("directive_id", ""))).strip()
        or str(payload.get("directive_id", ""))
    )
    execution_profile = str(payload.get("execution_profile", "")).strip()
    workspace_id = str(payload.get("workspace_id", "")).strip()
    session_id = str(session.get("session_id", ""))
    invocation_model = _invocation_model_for_mode(controller_mode)
    controller_summary_path = paths["controller_summary_path"]
    prior_controller_summary = load_json(controller_summary_path)

    _event(
        runtime_event_log_path,
        event_type="governed_execution_controller_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        controller_mode=str(controller_mode),
        invocation_model=invocation_model,
        max_cycles_per_invocation=int(max_cycles_per_invocation),
    )

    cycle_rows: list[dict[str, Any]] = []
    stop_reason = ""
    stop_detail = ""
    latest_summary_artifact_path = ""
    latest_cycle_summary_archive_path = ""
    latest_completion_evaluation: dict[str, Any] = {}

    current_payload = dict(payload)
    for cycle_index in range(1, int(max_cycles_per_invocation) + 1):
        planning_context = _build_trusted_planning_context(
            current_directive=current_directive,
            workspace_root=workspace_root,
            session=session,
            cycle_index=int(cycle_index),
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            work_item_id="governed_execution_controller",
        )
        pre_cycle_completion = dict(planning_context.get("completion_evaluation", {}))
        selected_stage = dict(dict(planning_context.get("next_step", {})).get("selected_stage", {}))
        if bool(pre_cycle_completion.get("completed", False)):
            stop_reason = STOP_REASON_COMPLETED
            stop_detail = str(pre_cycle_completion.get("reason", "")).strip()
            latest_completion_evaluation = pre_cycle_completion
            latest_summary_artifact_path = str(paths["summary_path"]) if paths["summary_path"].exists() else latest_summary_artifact_path
            break
        if not selected_stage:
            stop_reason = STOP_REASON_NO_WORK
            stop_detail = str(dict(planning_context.get("next_step", {})).get("reason", "")).strip() or (
                "no admissible bounded work remains under the current directive and trusted planning evidence"
            )
            latest_completion_evaluation = pre_cycle_completion
            latest_summary_artifact_path = str(paths["summary_path"]) if paths["summary_path"].exists() else latest_summary_artifact_path
            break
        _event(
            runtime_event_log_path,
            event_type="governed_execution_cycle_started",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            cycle_index=int(cycle_index),
            controller_mode=str(controller_mode),
            invocation_model=invocation_model,
            stage_id=str(selected_stage.get("stage_id", "")),
            cycle_kind=str(selected_stage.get("cycle_kind", "")),
            next_recommended_cycle=str(dict(planning_context.get("next_step", {})).get("next_recommended_cycle", "")),
        )
        current_payload = run_initial_bounded_workspace_work(
            bootstrap_summary=bootstrap_summary,
            session=session,
            payload=current_payload,
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            planning_context=planning_context,
            cycle_index=int(cycle_index),
        )
        work_cycle = dict(current_payload.get("work_cycle", {}))
        latest_summary_artifact_path = (
            str(work_cycle.get("summary_artifact_path", "")).strip() or str(paths["summary_path"])
        )
        latest_cycle_summary = load_json(Path(latest_summary_artifact_path))
        latest_completion_evaluation = _directive_completion_evaluation(
            current_directive=current_directive,
            workspace_root=workspace_root,
            session=session,
            latest_cycle_summary=latest_cycle_summary,
        )
        current_payload, augmented_summary, latest_cycle_summary_archive_path = _augment_cycle_payloads(
            payload=current_payload,
            workspace_root=workspace_root,
            cycle_index=int(cycle_index),
            controller_mode=controller_mode,
            latest_cycle_summary=latest_cycle_summary,
            completion_evaluation=latest_completion_evaluation,
        )

        cycle_status = str(current_payload.get("status", "")).strip()
        cycle_kind = str(dict(current_payload.get("work_cycle", {})).get("cycle_kind", "")).strip()
        cycle_row = {
            "cycle_index": int(cycle_index),
            "cycle_kind": cycle_kind,
            "status": cycle_status,
            "summary_artifact_path": latest_summary_artifact_path,
            "cycle_summary_archive_path": latest_cycle_summary_archive_path,
            "next_recommended_cycle": str(
                dict(current_payload.get("work_cycle", {})).get("next_recommended_cycle", "")
            ).strip(),
            "output_artifact_paths": list(dict(current_payload.get("work_cycle", {})).get("output_artifact_paths", [])),
            "newly_created_paths": list(dict(current_payload.get("work_cycle", {})).get("newly_created_paths", [])),
        }
        cycle_rows.append(cycle_row)

        _event(
            runtime_event_log_path,
            event_type="directive_stop_condition_evaluated",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            cycle_index=int(cycle_index),
            completed=bool(latest_completion_evaluation.get("completed", False)),
            reason=str(latest_completion_evaluation.get("reason", "")),
            fallback_used=bool(latest_completion_evaluation.get("fallback_used", False)),
        )
        _event(
            runtime_event_log_path,
            event_type="governed_execution_cycle_completed",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            cycle_index=int(cycle_index),
            cycle_kind=cycle_kind,
            status=cycle_status,
            summary_artifact_path=latest_summary_artifact_path,
            cycle_summary_archive_path=latest_cycle_summary_archive_path,
        )

        if cycle_status == STOP_REASON_FAILURE:
            stop_reason = STOP_REASON_FAILURE
            stop_detail = str(current_payload.get("reason", "")).strip()
            break
        if cycle_status == STOP_REASON_NO_WORK:
            stop_reason = STOP_REASON_NO_WORK
            stop_detail = str(current_payload.get("reason", "")).strip()
            break
        if bool(latest_completion_evaluation.get("completed", False)):
            stop_reason = STOP_REASON_COMPLETED
            stop_detail = str(latest_completion_evaluation.get("reason", "")).strip()
            break
        if str(controller_mode).strip() == "single_cycle":
            stop_reason = STOP_REASON_SINGLE_CYCLE
            stop_detail = "single-cycle mode stops after one bounded cycle and returns control to the operator"
            break

    if not stop_reason:
        stop_reason = STOP_REASON_MAX_CAP
        stop_detail = (
            f"bounded governed execution reached the operator-selected cycle cap of {int(max_cycles_per_invocation)}"
        )

    latest_cycle_index = int(cycle_rows[-1]["cycle_index"]) if cycle_rows else 0
    latest_cycle_kind = str(cycle_rows[-1].get("cycle_kind", "")) if cycle_rows else ""
    latest_next_recommended_cycle = (
        str(cycle_rows[-1].get("next_recommended_cycle", ""))
        if cycle_rows
        else str(load_json(paths["next_step_derivation_path"]).get("next_recommended_cycle", ""))
    )
    if not latest_summary_artifact_path and paths["summary_path"].exists():
        latest_summary_artifact_path = str(paths["summary_path"])
    review_cycle_rows = cycle_rows or list(dict(prior_controller_summary).get("cycle_rows", []))
    if not latest_cycle_index and review_cycle_rows:
        latest_cycle_index = int(review_cycle_rows[-1].get("cycle_index", 0) or 0)
    if not latest_cycle_kind and review_cycle_rows:
        latest_cycle_kind = str(review_cycle_rows[-1].get("cycle_kind", ""))
    if not latest_summary_artifact_path:
        latest_summary_artifact_path = str(
            dict(prior_controller_summary).get("latest_summary_artifact_path", "")
        ).strip()
    if not latest_completion_evaluation:
        latest_completion_evaluation = dict(
            dict(prior_controller_summary).get("directive_completion_evaluation", {})
        )
    current_objective = dict(
        latest_completion_evaluation.get(
            "current_objective",
            _current_objective_context(
                current_directive=current_directive,
                workspace_root=workspace_root,
            ),
        )
    )
    review_outputs = _materialize_successor_review_outputs(
        current_directive=current_directive,
        workspace_root=workspace_root,
        session=session,
        stop_reason=stop_reason,
        stop_detail=stop_detail,
        next_recommended_cycle=latest_next_recommended_cycle,
        completion_evaluation=latest_completion_evaluation,
        cycle_rows=review_cycle_rows,
        latest_summary_artifact_path=latest_summary_artifact_path,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
    )
    updated_effective_next_objective = _update_effective_next_objective_after_run(
        workspace_root=workspace_root,
        current_objective=current_objective,
        completion_evaluation=latest_completion_evaluation,
        stop_reason=stop_reason,
        stop_detail=stop_detail,
    )
    if (
        str(current_objective.get("source_kind", "")).strip() == OBJECTIVE_SOURCE_APPROVED_RESEED
        and not bool(latest_completion_evaluation.get("completed", False))
    ):
        reseed_outputs = {
            "request": load_json(paths["reseed_request_path"]),
            "decision": load_json(paths["reseed_decision_path"]),
            "continuation_lineage": load_json(paths["continuation_lineage_path"]),
            "effective_next_objective": updated_effective_next_objective
            or load_json(paths["effective_next_objective_path"]),
            "reseed_request_path": str(paths["reseed_request_path"]),
            "reseed_decision_path": str(paths["reseed_decision_path"]),
            "continuation_lineage_path": str(paths["continuation_lineage_path"]),
            "effective_next_objective_path": str(paths["effective_next_objective_path"]),
        }
    else:
        reseed_outputs = _materialize_successor_reseed_request_outputs(
            current_directive=current_directive,
            workspace_root=workspace_root,
            review_outputs=review_outputs,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
        )
    auto_continue_outputs = _evaluate_successor_auto_continue(
        workspace_root=workspace_root,
        session=session,
        execution_profile=execution_profile,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        stop_reason=stop_reason,
        review_outputs=review_outputs,
        reseed_outputs=reseed_outputs,
    )
    reseed_outputs = dict(auto_continue_outputs.get("reseed_outputs", reseed_outputs))
    controller_summary = {
        "schema_name": CONTROLLER_SUMMARY_SCHEMA_NAME,
        "schema_version": CONTROLLER_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "controller_mode": str(controller_mode),
        "invocation_model": invocation_model,
        "max_cycles_per_invocation": int(max_cycles_per_invocation),
        "cycles_completed": len(cycle_rows),
        "latest_cycle_index": latest_cycle_index,
        "latest_cycle_kind": latest_cycle_kind,
        "latest_summary_artifact_path": latest_summary_artifact_path,
        "latest_cycle_summary_archive_path": latest_cycle_summary_archive_path,
        "latest_trusted_planning_evidence_path": str(paths["trusted_planning_evidence_path"]),
        "latest_missing_deliverables_path": str(paths["missing_deliverables_path"]),
        "latest_next_step_derivation_path": str(paths["next_step_derivation_path"]),
        "latest_completion_evaluation_path": str(paths["completion_evaluation_path"]),
        "latest_successor_review_summary_path": str(review_outputs.get("review_summary_path", "")),
        "latest_successor_promotion_recommendation_path": str(
            review_outputs.get("promotion_recommendation_path", "")
        ),
        "latest_successor_next_objective_proposal_path": str(
            review_outputs.get("next_objective_proposal_path", "")
        ),
        "latest_successor_reseed_request_path": str(reseed_outputs.get("reseed_request_path", "")),
        "latest_successor_reseed_decision_path": str(reseed_outputs.get("reseed_decision_path", "")),
        "latest_successor_continuation_lineage_path": str(
            reseed_outputs.get("continuation_lineage_path", "")
        ),
        "latest_successor_effective_next_objective_path": str(
            reseed_outputs.get("effective_next_objective_path", "")
        ),
        "stop_reason": stop_reason,
        "stop_detail": stop_detail,
        "directive_completion_evaluation": latest_completion_evaluation,
        "next_recommended_cycle": latest_next_recommended_cycle,
        "current_objective_source_kind": str(current_objective.get("source_kind", "")),
        "current_objective_id": str(current_objective.get("objective_id", "")),
        "current_objective_class": str(current_objective.get("objective_class", "")),
        "current_objective_title": str(current_objective.get("title", "")),
        "review_status": str(dict(review_outputs.get("review_summary", {})).get("review_status", "")),
        "promotion_recommendation_state": str(
            dict(review_outputs.get("promotion_recommendation", {})).get("promotion_recommendation_state", "")
        ),
        "next_objective_state": str(
            dict(review_outputs.get("next_objective_proposal", {})).get("proposal_state", "")
        ),
        "next_objective_id": str(dict(review_outputs.get("next_objective_proposal", {})).get("objective_id", "")),
        "next_objective_class": str(
            dict(review_outputs.get("next_objective_proposal", {})).get("objective_class", "")
        ),
        "operator_review_required": bool(
            dict(review_outputs.get("review_summary", {})).get("operator_review_required", False)
        ),
        "reseed_state": str(
            dict(reseed_outputs.get("effective_next_objective", {})).get(
                "reseed_state",
                dict(reseed_outputs.get("request", {})).get("reseed_state", ""),
            )
        ),
        "continuation_authorized": bool(
            dict(reseed_outputs.get("effective_next_objective", {})).get(
                "continuation_authorized", False
            )
        ),
        "effective_next_objective_id": str(
            dict(reseed_outputs.get("effective_next_objective", {})).get("objective_id", "")
        ),
        "effective_next_objective_class": str(
            dict(reseed_outputs.get("effective_next_objective", {})).get("objective_class", "")
        ),
        "effective_next_objective_authorization_origin": str(
            dict(reseed_outputs.get("effective_next_objective", {})).get("authorization_origin", "")
        ),
        "latest_successor_auto_continue_policy_path": str(
            auto_continue_outputs.get("policy_path", "")
        ),
        "latest_successor_auto_continue_state_path": str(
            auto_continue_outputs.get("state_path", "")
        ),
        "latest_successor_auto_continue_decision_path": str(
            auto_continue_outputs.get("decision_path", "")
        ),
        "auto_continue_enabled": bool(
            dict(auto_continue_outputs.get("policy", {})).get("enabled", False)
        ),
        "auto_continue_allowed_objective_classes": list(
            dict(auto_continue_outputs.get("policy", {})).get("allowed_objective_classes", [])
        ),
        "auto_continue_chain_count": int(
            dict(auto_continue_outputs.get("state", {})).get("current_chain_count", 0) or 0
        ),
        "auto_continue_chain_cap": int(
            dict(auto_continue_outputs.get("policy", {})).get("max_auto_continue_chain_length", 1)
            or 1
        ),
        "auto_continue_last_reason": str(auto_continue_outputs.get("reason", "")),
        "auto_continue_last_origin": str(auto_continue_outputs.get("authorization_origin", "")),
        "cycle_rows": cycle_rows,
        "successor_review_summary": dict(review_outputs.get("review_summary", {})),
        "successor_promotion_recommendation": dict(review_outputs.get("promotion_recommendation", {})),
        "successor_next_objective_proposal": dict(review_outputs.get("next_objective_proposal", {})),
        "successor_reseed_request": dict(reseed_outputs.get("request", {})),
        "successor_reseed_decision": dict(reseed_outputs.get("decision", {})),
        "successor_continuation_lineage": dict(reseed_outputs.get("continuation_lineage", {})),
        "successor_effective_next_objective": dict(reseed_outputs.get("effective_next_objective", {})),
        "successor_auto_continue_policy": dict(auto_continue_outputs.get("policy", {})),
        "successor_auto_continue_state": dict(auto_continue_outputs.get("state", {})),
        "successor_auto_continue_decision": dict(auto_continue_outputs.get("decision", {})),
    }
    controller_summary_path.write_text(_dump(controller_summary), encoding="utf-8")

    if paths["workspace_artifact_index_path"].exists():
        workspace_artifact_index = _build_workspace_artifact_index_payload(workspace_root)
        _write_json(
            paths["workspace_artifact_index_path"],
            workspace_artifact_index,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id="governed_execution_controller",
            artifact_kind="workspace_artifact_index_json",
        )

    final_reason = str(current_payload.get("reason", "")).strip()
    if stop_reason == STOP_REASON_COMPLETED:
        final_reason = (
            "completed bounded governed execution by directive-derived stop condition after "
            f"{len(cycle_rows)} cycle(s); operator review is still required before any promotion or next-objective continuation"
        )
    elif stop_reason == STOP_REASON_MAX_CAP:
        final_reason = stop_detail
    elif stop_reason == STOP_REASON_SINGLE_CYCLE:
        final_reason = stop_detail
    elif not final_reason:
        final_reason = stop_detail

    current_payload["generated_at"] = _now()
    if stop_reason == STOP_REASON_COMPLETED and not cycle_rows:
        current_payload["status"] = STOP_REASON_COMPLETED
    elif stop_reason == STOP_REASON_NO_WORK and not cycle_rows:
        current_payload["status"] = STOP_REASON_NO_WORK
    elif stop_reason == STOP_REASON_MAX_CAP:
        current_payload["status"] = STOP_REASON_MAX_CAP
    current_payload["reason"] = final_reason
    current_payload["governed_execution_controller"] = controller_summary
    current_payload["controller_artifact_path"] = str(controller_summary_path)
    current_payload["successor_review"] = dict(review_outputs.get("review_summary", {}))
    current_payload["successor_promotion_recommendation"] = dict(
        review_outputs.get("promotion_recommendation", {})
    )
    current_payload["successor_next_objective_proposal"] = dict(
        review_outputs.get("next_objective_proposal", {})
    )
    current_payload["successor_reseed_request"] = dict(reseed_outputs.get("request", {}))
    current_payload["successor_reseed_decision"] = dict(reseed_outputs.get("decision", {}))
    current_payload["successor_continuation_lineage"] = dict(
        reseed_outputs.get("continuation_lineage", {})
    )
    current_payload["successor_effective_next_objective"] = dict(
        reseed_outputs.get("effective_next_objective", {})
    )
    current_payload["successor_auto_continue_policy"] = dict(
        auto_continue_outputs.get("policy", {})
    )
    current_payload["successor_auto_continue_state"] = dict(
        auto_continue_outputs.get("state", {})
    )
    current_payload["successor_auto_continue_decision"] = dict(
        auto_continue_outputs.get("decision", {})
    )

    brief_lines = [
        "# Governed Execution Brief",
        "",
        f"Status: {current_payload.get('status', '')}",
        f"Directive ID: `{directive_id}`",
        f"Workspace: `{workspace_id} -> {workspace_root}`",
        f"Controller mode: `{controller_mode}`",
        f"Invocation model: `{invocation_model}`",
        f"Cycles completed: `{len(cycle_rows)}`",
        f"Current objective source: `{current_objective.get('source_kind', '') or '<none>'}`",
        f"Current objective id: `{current_objective.get('objective_id', '') or '<none>'}`",
        f"Current objective class: `{current_objective.get('objective_class', '') or '<none>'}`",
        f"Stop reason: `{stop_reason}`",
        f"Latest cycle kind: `{latest_cycle_kind or '<none>'}`",
        f"Review status: `{dict(review_outputs.get('review_summary', {})).get('review_status', '') or '<none>'}`",
        f"Promotion recommendation: `{dict(review_outputs.get('promotion_recommendation', {})).get('promotion_recommendation_state', '') or '<none>'}`",
        f"Next objective proposal: `{dict(review_outputs.get('next_objective_proposal', {})).get('objective_id', '') or '<none>'}`",
        f"Next objective class: `{dict(review_outputs.get('next_objective_proposal', {})).get('objective_class', '') or '<none>'}`",
        f"Reseed state: `{dict(reseed_outputs.get('effective_next_objective', {})).get('reseed_state', '') or dict(reseed_outputs.get('request', {})).get('reseed_state', '') or '<none>'}`",
        f"Continuation authorized: `{bool(dict(reseed_outputs.get('effective_next_objective', {})).get('continuation_authorized', False))}`",
        f"Auto-continue enabled: `{bool(dict(auto_continue_outputs.get('policy', {})).get('enabled', False))}`",
        f"Auto-continue reason: `{str(auto_continue_outputs.get('reason', '') or '<none>')}`",
        f"Auto-continue chain: `{int(dict(auto_continue_outputs.get('state', {})).get('current_chain_count', 0) or 0)}/{int(dict(auto_continue_outputs.get('policy', {})).get('max_auto_continue_chain_length', 1) or 1)}`",
        f"Latest summary artifact: `{latest_summary_artifact_path or '<none>'}`",
        f"Controller summary: `{controller_summary_path}`",
        f"Review summary: `{str(review_outputs.get('review_summary_path', '')) or '<none>'}`",
        f"Auto-continue state: `{str(auto_continue_outputs.get('state_path', '')) or '<none>'}`",
    ]
    _finalize_session_artifacts(
        payload=current_payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=brief_lines,
    )
    _event(
        runtime_event_log_path,
        event_type="governed_execution_controller_stopped",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        controller_mode=str(controller_mode),
        invocation_model=invocation_model,
        cycles_completed=len(cycle_rows),
        latest_cycle_index=latest_cycle_index,
        stop_reason=stop_reason,
        stop_detail=stop_detail,
        controller_artifact_path=str(controller_summary_path),
        latest_summary_artifact_path=latest_summary_artifact_path,
    )
    return current_payload

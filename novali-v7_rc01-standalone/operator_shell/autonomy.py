from __future__ import annotations

import ctypes
import gc
import hashlib
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .bounded_workspace_work import (
    GovernedExecutionFailure,
    TRUSTED_SOURCE_EXTERNAL_API_BASE_URL,
    TRUSTED_SOURCE_EXTERNAL_MODEL_PREFERENCE,
    TRUSTED_SOURCE_EXTERNAL_PROVIDER_ID,
    _extract_responses_structured_json,
    _extract_responses_structured_json_with_outcome,
    _trusted_source_external_json_request,
)
from .observability.enrichment import (
    record_autonomy_churn_breaker,
    record_autonomy_operation_executed,
    record_autonomy_operation_proposed,
    record_high_impact_validation,
    record_meaningful_work_evaluation,
    record_memory_disk_spill,
    record_memory_smoothing,
    record_memory_trim,
    record_oom_guard,
    record_promotion_packet_state,
    record_service_recycle_requested,
    record_trusted_source_triage,
)
from .observability.redaction import redact_value
from .policy import (
    load_trusted_source_bindings_or_default,
    load_trusted_source_credential_status,
    load_trusted_source_provider_status,
    load_trusted_source_secrets_or_default,
    validate_trusted_source_bindings,
)


AUTONOMY_CHARTER_SCHEMA_NAME = "AutonomyCharter"
AUTONOMY_GOAL_SCHEMA_NAME = "AutonomousGoalRecord"
RESEARCH_REQUEST_SCHEMA_NAME = "ResearchRequest"
RESEARCH_EVIDENCE_SCHEMA_NAME = "ResearchEvidenceBundle"
PLAN_CANDIDATE_SCHEMA_NAME = "PlanCandidate"
OPERATION_PROPOSAL_SCHEMA_NAME = "OperationProposal"
APPROVAL_BOARD_DECISION_SCHEMA_NAME = "ApprovalBoardDecision"
AUTONOMY_CYCLE_SCHEMA_NAME = "AutonomyCycleRecord"
SELF_MODIFICATION_SCHEMA_NAME = "SelfModificationProposal"
PROMOTION_DECISION_SCHEMA_NAME = "PromotionDecision"
PROMOTION_RESULT_SCHEMA_NAME = "PromotionResult"
ROLLBACK_RECORD_SCHEMA_NAME = "RollbackRecord"
MEMORY_PRESSURE_STATUS_SCHEMA_NAME = "MemoryPressureStatus"
MEMORY_ARCHIVE_MANIFEST_SCHEMA_NAME = "MemoryArchiveManifest"
MEMORY_ARCHIVE_ATTEMPT_SCHEMA_NAME = "MemoryArchiveAttempt"
MEMORY_RECOVERY_REQUEST_SCHEMA_NAME = "MemoryRecoveryRequest"
LEDGER_COMPACTION_ATTEMPT_SCHEMA_NAME = "LedgerCompactionAttempt"
LEDGER_COMPACTION_CURSOR_SCHEMA_NAME = "LedgerCompactionCursor"
LEDGER_COMPACTION_SEGMENT_MANIFEST_SCHEMA_NAME = "LedgerCompactionSegmentManifest"
MEANINGFUL_WORK_EVALUATION_SCHEMA_NAME = "MeaningfulWorkEvaluation"
CAPABILITY_NOVELTY_EVALUATION_SCHEMA_NAME = "CapabilityNoveltyEvaluation"
POST_LADDER_SYNTHESIS_SCHEMA_NAME = "PostLadderSynthesis"
ROLE_SPECIALIZATION_PROFILE_SCHEMA_NAME = "RoleSpecializationProfile"
CAPABILITY_USEFULNESS_EVALUATION_SCHEMA_NAME = "CapabilityUsefulnessEvaluation"
SELF_CURRICULUM_CHALLENGE_SCHEMA_NAME = "SelfCurriculumChallenge"
METACOGNITIVE_REPLAY_SCHEMA_NAME = "MetacognitiveReplay"
ADAPTIVE_LEARNING_SYNTHESIS_SCHEMA_NAME = "AdaptiveLearningSynthesis"
ADAPTIVE_LEARNING_BACKOFF_SCHEMA_NAME = "AdaptiveLearningBackoffEvaluation"
ADAPTIVE_LEARNING_GAP_FAMILY_SCHEMA_NAME = "AdaptiveLearningGapFamilyEvaluation"
ADAPTIVE_LEARNING_HOOK_STALL_SCHEMA_NAME = "AdaptiveLearningHookStallEvaluation"
CAPABILITY_HOOK_CONSUMPTION_SCHEMA_NAME = "CapabilityHookConsumption"
CAPABILITY_CONSUMPTION_CONTRACT_SCHEMA_NAME = "CapabilityConsumptionContract"
RUNTIME_CAPABILITY_ADAPTER_SCHEMA_NAME = "RuntimeCapabilityAdapter"
CAPABILITY_CONSUMPTION_EVENT_SCHEMA_NAME = "CapabilityConsumptionEvent"
CAPABILITY_RETIREMENT_EVALUATION_SCHEMA_NAME = "CapabilityRetirementEvaluation"
EXECUTION_BUDGET_GUARDRAIL_SCHEMA_NAME = "ExecutionBudgetGuardrailEvaluation"
TRUSTED_SOURCE_TRIAGE_DIGEST_SCHEMA_NAME = "TrustedSourceLiteratureTriageDigest"
HIGH_IMPACT_VALIDATION_SCHEMA_NAME = "HighImpactOperationValidation"
LIBRARIAN_GAP_REQUEST_SCHEMA_NAME = "LibrarianGapRequest"
AUTONOMY_STATUS_SCHEMA_NAME = "NovaliAutonomyStatus"

AUTONOMY_SCHEMA_VERSION = "novali_autonomy_v1"
DIRECTIVE_OUTCOME_NUDGE_INTERVAL = 7

DEFAULT_FORBIDDEN_OBJECTIVES = (
    "bypass operator review, approval, or emergency-stop controls",
    "hide, delete, or falsify autonomy evidence",
    "exfiltrate secrets or store raw credentials in autonomy records",
    "perform destructive or irreversible operations without rollback evidence",
    "operate systems outside approved adapters and approved targets",
    "modify protected roots outside the promotion path",
)

APPROVAL_BOARD_ROLES = (
    "planner",
    "research_verifier",
    "safety_ops_judge",
    "implementation_verifier",
    "promotion_judge",
)

SUPPORTED_OPERATION_ACTIONS = (
    "novali_stack_status",
    "novali_health_check",
    "novali_stack_restart",
    "ollama_model_pull",
    "state_backup",
    "governed_start_next_invocation",
    "promote_self_modification_candidate",
    "post_ladder_synthesis",
    "adaptive_learning_synthesis",
    "trusted_source_literature_triage_digest",
    "memory_ledger_compaction",
    "memory_pressure_archive",
)

HIGH_IMPACT_AUTONOMY_ACTIONS = {
    "promote_self_modification_candidate",
    "post_ladder_synthesis",
    "adaptive_learning_synthesis",
    "trusted_source_literature_triage_digest",
    "memory_ledger_compaction",
    "memory_pressure_archive",
}

MEMORY_PRESSURE_WARNING_PERCENT = 75.0
MEMORY_PRESSURE_ACTION_PERCENT = 85.0
MEMORY_PRESSURE_CRITICAL_PERCENT = 92.0
MEMORY_PRESSURE_STALE_STATUS_SECONDS = 60
OOM_GUARD_SOFT_PERCENT_DEFAULT = 74.0
OOM_GUARD_HIBERNATE_PERCENT_DEFAULT = 76.0
OOM_GUARD_RECYCLE_PERCENT_DEFAULT = 78.0
MEMORY_SMOOTHING_ENTER_PERCENT_DEFAULT = 72.0
MEMORY_SMOOTHING_EXIT_PERCENT_DEFAULT = 68.0
AGGRESSIVE_MEMORY_SMOOTHING_ENTER_PERCENT_DEFAULT = 55.0
AGGRESSIVE_MEMORY_SMOOTHING_EXIT_PERCENT_DEFAULT = 45.0
OOM_GUARD_RECOVERY_STATES = {
    "hibernated_for_memory_pressure",
    "service_recycle_requested",
    "restart_required_external_operator",
}
NOVALI_SERVICE_RECYCLE_EXIT_CODE = 75
MEMORY_ARCHIVE_CANDIDATE_SUFFIXES = (".json", ".jsonl", ".log", ".txt", ".md")
MEMORY_ARCHIVE_SKIP_NAME_FRAGMENTS = (
    "latest",
    "status",
    "charter",
    "credential",
    "secret",
    "api_key",
    "apikey",
    "token",
    "openai",
    "memory_archive",
)
MEMORY_ARCHIVE_DEFAULT_MIN_AGE_SECONDS = 600
MEMORY_ARCHIVE_DEFAULT_MAX_FILES = 500
MEMORY_ARCHIVE_DEFAULT_MAX_BYTES = 768 * 1024 * 1024
MEMORY_ARCHIVE_DEFAULT_TIMEOUT_SECONDS = 45
MEMORY_ARCHIVE_DEFAULT_MAX_SCAN_ENTRIES = 10000
LEDGER_COMPACTION_DEFAULT_TIMEOUT_SECONDS = 20
LEDGER_COMPACTION_DEFAULT_HOT_TAIL_RECORDS = 1000
LEDGER_COMPACTION_DEFAULT_MAX_LEDGERS = 3
LEDGER_COMPACTION_DEFAULT_MAX_SOURCE_BYTES = 25 * 1024 * 1024
TRUSTED_SOURCE_TRIAGE_ADAPTIVE_WINDOW = 8
TRUSTED_SOURCE_TRIAGE_ADAPTIVE_THRESHOLD = 5
TRUSTED_SOURCE_TRIAGE_GOVERNED_CONTINUATION_THRESHOLD = 7
TRUSTED_SOURCE_TRIAGE_MAX_ATTEMPTS = 2
MEMORY_ARCHIVE_PRUNE_DIR_NAMES = {
    ".cache",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "build",
    "dist",
    "memory_archive",
    "memory_pressure",
    "node_modules",
}

PROMOTION_LADDER_STAGES = (
    "candidate",
    "admitted_candidate",
    "staged_adoption",
    "canary_adopted",
    "promoted",
)

CAPABILITY_GAP_KINDS = (
    "promotion_packet_generation",
    "promotion_novelty_memory",
    "promotion_result_summarization",
    "governed_start_health_probe",
    "autonomy_loop_stall_detection",
    "trusted_source_readiness_probe",
)

CAPABILITY_KIND_SUMMARIES = {
    "promotion_packet_generation": (
        "Autonomy generated a broker-ready promotion packet with manifest, tests, rollback, "
        "and canary evidence for a writable Novali-owned capability record."
    ),
    "promotion_novelty_memory": (
        "Track recent promoted capability kinds and steer future cycles toward novel capability gaps."
    ),
    "promotion_result_summarization": (
        "Summarize promotion outcomes so later planning can distinguish useful promotion from artifact churn."
    ),
    "governed_start_health_probe": (
        "Record governed-start health evidence before repeating launch or continuation proposals."
    ),
    "autonomy_loop_stall_detection": (
        "Detect repeated autonomy-cycle patterns and surface a bounded remediation objective."
    ),
    "trusted_source_readiness_probe": (
        "Capture whether trusted-source configuration is ready without storing raw credentials."
    ),
}

CAPABILITY_PLANNER_HOOK_SUFFIXES = {
    "goal_drift_guardrails_v1": "goal_drift_guardrails",
    "tool_failure_classifier_v1": "tool_failure_classifier",
    "budget_aware_throttling_v1": "budget_aware_throttling",
    "dependency_fingerprint_cache_v1": "dependency_fingerprint_cache",
    "execution_budget_guardrails_v1": "execution_budget_guardrails",
    "idempotent_tool_invocation_ledger_v1": "idempotent_tool_invocation_ledger",
}

DEFAULT_NOVELTY_REPEAT_REASONS = (
    "failed_canary",
    "failed_rollback",
    "missing_evidence_repair",
    "explicit_directive_need",
)
BLOCKED_GROWTH_EVIDENCE_GAP_ID = "autonomy_growth_blocked_evidence_v1"
TRUSTED_SOURCE_SYNTHESIS_MAX_ATTEMPTS = 2
ADAPTIVE_LEARNING_BACKOFF_REPEAT_THRESHOLD = 5
ADAPTIVE_LEARNING_GAP_FAMILY_REPEAT_THRESHOLD = 5
ADAPTIVE_LEARNING_HOOK_STALL_THRESHOLD = 5
ADAPTIVE_LEARNING_HOOK_STALL_USEFULNESS = {"evidence_only", "dormant", "needs_followup"}
ADAPTIVE_LEARNING_HOOK_STALL_HOOK_TYPES = {
    "dependency_fingerprint_cache",
    "goal_drift_guardrails",
}
RUNTIME_HOOK_ADAPTER_BEHAVIORS = {
    "budget_stall_throttling",
    "duplicate_suppression",
    "execution_budget_guardrails",
    "failure_classification",
    "planner_bias",
    "read_only_evidence_synthesis",
    "replay_fingerprint_support",
    "status_summarization",
}

CAPABILITY_CONSUMPTION_CONTRACT_STALE_EVALUATIONS = 5

RUNTIME_ADAPTER_BEHAVIOR_BY_HOOK_TYPE = {
    "budget_aware_throttling": "budget_stall_throttling",
    "dependency_fingerprint_cache": "duplicate_suppression",
    "execution_budget_guardrails": "execution_budget_guardrails",
    "goal_drift_guardrails": "planner_bias",
    "idempotent_tool_invocation_ledger": "duplicate_suppression",
    "tool_failure_classifier": "failure_classification",
}

ADAPTIVE_LEARNING_FAMILY_VARIANT_WORDS = {
    "buffer",
    "compiler",
    "generation",
    "generator",
    "guard",
    "loop",
    "packager",
    "playbook",
    "runbook",
    "state",
    "synthesis",
    "tracker",
    "writer",
}

ADAPTIVE_LEARNING_FAMILY_ALIASES = {
    "artifact_churn_resistance": {"artifact", "churn", "resistance"},
    "capability_usefulness_reinforcement": {"capability", "usefulness", "reinforcement"},
    "prototype_build_test": {"prototype", "build", "test"},
    "technology_tradeoff_scoring": {"technology", "tradeoff", "scoring"},
    "trusted_source_literature_synthesis": {"trusted", "source", "literature", "synthesis"},
}

SECRET_LIKE_PATTERN = re.compile(
    r"(?i)(bearer\s+[a-z0-9._\-]{12,}|sk-[a-z0-9_\-]{16,}|api[_-]?key\s*[:=]\s*\S+|password\s*[:=]\s*\S+|token\s*[:=]\s*\S+)"
)


class AutonomyValidationError(ValueError):
    pass


class AutonomyOperationRefusedError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def _compact_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_payload(payload: Any, *, length: int = 12) -> str:
    return hashlib.sha256(_compact_json(payload).encode("utf-8")).hexdigest()[:length]


def _short_ref(value: Any, *, prefix: str = "ref", length: int = 12) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return f"{prefix}_{hashlib.sha256(text.encode('utf-8', errors='ignore')).hexdigest()[:length]}"


def _record_id(prefix: str, payload: Mapping[str, Any]) -> str:
    stamp = _now().replace(":", "").replace(".", "")
    return f"{prefix}-{stamp}-{_hash_payload(payload)}"


def _truncate(value: Any, limit: int = 4000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...[truncated {len(text) - limit} chars]"


AUTONOMY_AUDIT_IDENTIFIER_KEYS = {
    "attempt_id",
    "already_promoted_gap_ids",
    "archive_bundle_path",
    "archive_member",
    "archive_root",
    "capability_gap_id",
    "capability_gap_priority_order",
    "capability_consumption_contract_id",
    "capability_consumption_contract_ids",
    "capability_consumption_event_id",
    "capability_hook_consumption_id",
    "capability_kind",
    "capability_retirement_evaluation_id",
    "budget_guardrail_evaluation_id",
    "candidate_gap_id",
    "consumed_capability_kind",
    "consumed_capability_kinds",
    "cooldown_blocked_kinds",
    "current_capability_kind",
    "cycle_id",
    "decision_id",
    "explicitly_consumed_capability_kind",
    "explicitly_consumed_capability_kinds",
    "gap_id",
    "goal_id",
    "high_impact_validation_id",
    "latest_synthesis_id",
    "manifest_path",
    "member_gap_ids",
    "meaningful_work_id",
    "next_capability_gap_proposal",
    "novelty_evaluation_id",
    "operation_id",
    "operation_result_id",
    "plan_candidate_id",
    "post_ladder_synthesis_id",
    "referenced_capability_kind",
    "referenced_capability_kinds",
    "referenced_planner_hook_capability",
    "referenced_runtime_hook_capability",
    "role_profile_id",
    "planner_hook_reference",
    "planner_hook_references",
    "runtime_hook_adapter_gap_id",
    "runtime_capability_adapter_id",
    "runtime_capability_adapter_ids",
    "runtime_hook_reference",
    "runtime_hook_references",
    "usefulness_evaluation_id",
    "curriculum_challenge_id",
    "metacognitive_replay_id",
    "adaptive_learning_synthesis_id",
    "adaptive_learning_backoff_id",
    "adaptive_learning_gap_family_id",
    "adaptive_learning_gap_family_evaluation_id",
    "adaptive_learning_gap_proposal",
    "adaptive_learning_hook_stall_id",
    "adaptive_learning_repeated_gap_id",
    "hook_adapter_candidate_gap_id",
    "family_backoff_id",
    "family_member_gap_ids",
    "family_representative_gap_id",
    "latest_curriculum_gap_proposal",
    "latest_consumed_capability_kind",
    "representative_gap_id",
    "repeated_learning_gap_id",
    "memory_archive_id",
    "memory_archive_attempt_id",
    "memory_pressure_status_id",
    "memory_recovery_request_id",
    "promotion_decision_id",
    "promotion_result_id",
    "research_bundle_id",
    "research_request_id",
    "rollback_record_id",
    "recent_promoted_kinds",
    "rejected_gap_candidates",
    "selected_capability_gap",
    "selected_capability_kind",
    "self_modification_id",
    "source_capability_kind",
    "source_packet_path",
    "source_path",
    "source_path_hint",
    "stalled_capability_kind",
    "target_packet_path",
    "target_path",
    "trusted_source_triage_digest_id",
    "used_capability_kind",
    "used_capability_kinds",
    "capabilities_lacking_consumption_contracts",
    "contracted_capability_kind",
    "contracted_capability_kinds",
}


def _redact_autonomy_value(value: Any, *, key: str | None = None) -> Any:
    key_text = str(key or "").strip()
    if key_text in AUTONOMY_AUDIT_IDENTIFIER_KEYS and isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return {
            str(inner_key): _redact_autonomy_value(inner_value, key=str(inner_key))
            for inner_key, inner_value in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_redact_autonomy_value(item, key=key) for item in value]
    return redact_value(value, key=key)


def autonomy_root(operator_root: str | Path) -> Path:
    return Path(operator_root) / "autonomy"


def _charter_path(operator_root: str | Path) -> Path:
    return autonomy_root(operator_root) / "charter.json"


def _status_path(operator_root: str | Path) -> Path:
    return autonomy_root(operator_root) / "status.json"


def _ledger_path(operator_root: str | Path, name: str) -> Path:
    return autonomy_root(operator_root) / "ledgers" / f"{name}.jsonl"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    redacted = _redact_autonomy_value(dict(payload))
    path.write_text(_json_dump(redacted) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _append_ledger(operator_root: str | Path, name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    path = _ledger_path(operator_root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    redacted = _redact_autonomy_value(dict(payload))
    try:
        offset = path.stat().st_size if path.exists() else 0
    except OSError:
        offset = 0
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redacted, sort_keys=True, ensure_ascii=False) + "\n")
    try:
        from .disk_spill import update_ledger_index_after_append

        update_ledger_index_after_append(operator_root, name, offset, redacted)
    except Exception:
        pass
    return dict(redacted)


def _read_ledger(operator_root: str | Path, name: str, *, limit: int = 50) -> list[dict[str, Any]]:
    try:
        from .disk_spill import read_ledger_tail_indexed

        rows = read_ledger_tail_indexed(operator_root, name, limit=limit)
        if rows:
            return rows
    except Exception:
        pass
    path = _ledger_path(operator_root, name)
    if not path.exists():
        return []
    rows: deque[dict[str, Any]] = deque(maxlen=max(1, int(limit or 1)))
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)
    except OSError:
        return []
    return list(rows)


def _latest(operator_root: str | Path, name: str) -> dict[str, Any]:
    try:
        from .disk_spill import latest_ledger_entry

        latest = latest_ledger_entry(operator_root, name)
        if latest:
            return latest
    except Exception:
        pass
    rows = _read_ledger(operator_root, name, limit=1)
    return rows[-1] if rows else {}


def _operation_result_by_operation_id(
    operator_root: str | Path,
    operation_id: str,
    *,
    limit: int = 200,
) -> dict[str, Any]:
    operation_id = str(operation_id or "").strip()
    if not operation_id:
        return {}
    try:
        from .disk_spill import lookup_ledger_by_operation_id

        result = lookup_ledger_by_operation_id(operator_root, operation_id)
        if result:
            return result
    except Exception:
        pass
    for row in reversed(_read_ledger(operator_root, "operation_results", limit=limit)):
        if str(row.get("operation_id", "") or "").strip() == operation_id:
            return row
    return {}


def _latest_open_operation_proposal(operator_root: str | Path) -> dict[str, Any]:
    latest = _latest(operator_root, "operation_proposals")
    if latest:
        proposal = dict(latest)
        operation_id = str(proposal.get("operation_id", "") or "").strip()
        result = _operation_result_by_operation_id(operator_root, operation_id)
        if result:
            return {}
        return proposal
    return {}


def _relative_package_path(package_root: str | Path, path: str | Path) -> str:
    package = Path(package_root).resolve()
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(package)).replace("\\", "/")
    except ValueError:
        return str(resolved)


def _secret_leak_indicators(payload: Any) -> list[str]:
    text = _compact_json(payload)
    indicators: list[str] = []
    if SECRET_LIKE_PATTERN.search(text):
        indicators.append("secret-like credential pattern")
    if "FAKE_OPENAI_API_KEY" in text or "SHOULD_NOT_EXPORT" in text:
        indicators.append("fake secret fixture")
    return indicators


def _parse_autonomy_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _latest_promotion_packet_evidence(
    operator_root: str | Path,
    *,
    max_age_seconds: int = 48 * 60 * 60,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    latest_promotion_result = _latest(operator_root, "promotion_results")
    latest_promotion_result_created_at = _parse_autonomy_timestamp(
        latest_promotion_result.get("created_at")
    )
    for row in reversed(_read_ledger(operator_root, "self_modification_proposals", limit=80)):
        packet = dict(row.get("promotion_packet", {}) or {})
        if not packet:
            continue
        created_at = _parse_autonomy_timestamp(row.get("created_at"))
        if created_at is None:
            continue
        if (
            latest_promotion_result_created_at is not None
            and latest_promotion_result_created_at >= created_at
            and str(latest_promotion_result.get("status", ""))
            in {"promoted", "completed", "canary_adopted"}
        ):
            continue
        age_seconds = max(0.0, (now - created_at).total_seconds())
        if age_seconds > max_age_seconds:
            continue
        required_fields = (
            "capability_kind",
            "changed_file_manifest",
            "test_commands",
            "rollback_plan",
            "canary_plan",
        )
        if not all(packet.get(field) for field in required_fields):
            continue
        evidence = {
            "promotion_packet_evidence_state": "fresh",
            "promotion_packet_evidence_age_seconds": round(age_seconds, 3),
            "promotion_packet_ref": _hash_payload(
                {
                    "self_modification_id": row.get("self_modification_id", ""),
                    "capability_kind": packet.get("capability_kind", ""),
                },
                length=12,
            ),
            "capability_kind": str(packet.get("capability_kind", "")),
        }
        return evidence
    return {
        "promotion_packet_evidence_state": "missing",
        "promotion_packet_evidence_age_seconds": None,
        "promotion_packet_ref": "",
        "capability_kind": "",
    }


def _latest_growth_needs_promotion_packet(operator_root: str | Path) -> bool:
    latest_meaningful = _latest(operator_root, "meaningful_work_evaluations")
    latest_promotion = _latest(operator_root, "promotion_decisions")
    weak_text = " ".join(
        str(item)
        for item in list(latest_meaningful.get("weak_areas", []) or [])
        + list(latest_promotion.get("weak_areas", []) or [])
    ).lower()
    if not (
        "missing promotion packet" in weak_text
        or "missing changed-file manifest" in weak_text
    ):
        return False
    return _latest_promotion_packet_evidence(operator_root).get(
        "promotion_packet_evidence_state"
    ) != "fresh"


def _autonomy_churn_classifier(
    operator_root: str | Path,
    *,
    limit: int = 12,
) -> dict[str, Any]:
    rows = _read_ledger(operator_root, "meaningful_work_evaluations", limit=limit)
    latest = dict(rows[-1] if rows else {})
    signature = str(latest.get("signal_signature", "") or "").strip()
    capability_kind = str(latest.get("capability_kind", "") or "").strip()
    promotion_packet_ref = str(latest.get("promotion_packet_ref", "") or "").strip()
    repeat_count = 0
    if signature:
        for row in reversed(rows):
            row_signature = str(row.get("signal_signature", "") or "").strip()
            row_capability = str(row.get("capability_kind", "") or "").strip()
            row_packet_ref = str(row.get("promotion_packet_ref", "") or "").strip()
            if row_signature != signature:
                break
            if capability_kind and row_capability and row_capability != capability_kind:
                break
            if promotion_packet_ref and row_packet_ref and row_packet_ref != promotion_packet_ref:
                break
            repeat_count += 1
    weak_text = " ".join(
        str(item) for item in list(latest.get("weak_areas", []) or [])
    ).lower()
    repeated_delta_blocked = not bool(latest.get("meaningful_delta", True))
    active = bool(
        signature
        and (
            "repeated signal signature" in weak_text
            or "artifact churn" in weak_text
            or (repeat_count >= 3 and repeated_delta_blocked)
        )
    )
    churn = {
        "schema_name": "AutonomyChurnState",
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "churn_state": "active" if active else "clear",
        "churn_repeat_count": repeat_count,
        "churn_signature_ref": _hash_payload(
            {"signal_signature": signature},
            length=12,
        )
        if signature
        else "",
        "repeated_capability_kind": capability_kind,
        "repeated_promotion_packet_ref": promotion_packet_ref,
        "recommended_breaker_action": (
            "governed_start_next_invocation" if active else ""
        ),
        "suppressed_action": (
            "duplicate_promotion_packet_staging"
            if active and (capability_kind or promotion_packet_ref)
            else ""
        ),
        "suppress_duplicate_promotion": bool(
            active and (capability_kind or promotion_packet_ref)
        ),
        "directive_track_depth_target": (
            "deepen_existing_or_next_concrete_track" if active else ""
        ),
        "reason": "repeated_signal_signature" if active else "no_active_churn",
        "result": "active" if active else "clear",
    }
    return churn


def _latest_deepened_directive_track_delta(operator_root: str | Path) -> dict[str, Any]:
    empty_delta = {
        "track_id": "",
        "artifact_depth": "",
        "depth_iteration": 0,
        "artifact_ref": "",
        "new_information_delta": "",
        "new_information_delta_signature": "",
        "delta_materially_new": False,
        "delta_rejection_reason": "",
        "deliverable_kind": "",
        "delta_focus_id": "",
        "delta_focus_label": "",
        "focus_rotation_state": "",
        "delta_layer_id": "",
        "delta_layer_label": "",
        "layer_rotation_state": "",
        "progress_generated_at": "",
        "credit_source": "",
        "operation_result_id": "",
        "directive_dossier_artifact_relative_path": "",
        "directive_dossier_artifact_ref": "",
        "directive_dossier_signature": "",
        "directive_dossier_materially_new": False,
        "directive_dossier_rejection_reason": "",
        "directive_source_coverage_state": "",
        "librarian_gap_reuse_decision": "",
        "trusted_source_retrieval_validation_state": "",
        "directive_dossier_progress_generated_at": "",
    }
    for row in reversed(_read_ledger(operator_root, "operation_results", limit=40)):
        result = dict(row.get("result", {}) or {})
        track_id = str(result.get("selected_directive_track_id", "") or "").strip()
        artifact_path = str(
            result.get("directive_track_artifact_relative_path")
            or result.get("directive_track_artifact_path")
            or ""
        ).strip()
        artifact_depth = str(result.get("artifact_depth", "") or "").strip()
        try:
            depth_iteration = int(result.get("depth_iteration", 0) or 0)
        except (TypeError, ValueError):
            depth_iteration = 0
        new_delta = str(result.get("new_information_delta", "") or "").strip()
        delta_materially_new = bool(result.get("delta_materially_new", False))
        delta_rejection_reason = str(
            result.get("delta_rejection_reason", "") or ""
        ).strip()
        deliverable_kind = str(
            result.get("selected_deliverable_kind")
            or result.get("deliverable_kind")
            or ""
        ).strip()
        delta_signature = str(
            result.get("new_information_delta_signature", "") or ""
        ).strip()
        delta_focus_id = str(result.get("delta_focus_id", "") or "").strip()
        delta_focus_label = str(result.get("delta_focus_label", "") or "").strip()
        focus_rotation_state = str(
            result.get("focus_rotation_state", "") or ""
        ).strip()
        delta_layer_id = str(result.get("delta_layer_id", "") or "").strip()
        delta_layer_label = str(result.get("delta_layer_label", "") or "").strip()
        layer_rotation_state = str(
            result.get("layer_rotation_state", "") or ""
        ).strip()
        progress_generated_at = str(
            result.get("directive_track_progress_generated_at", "") or ""
        ).strip()
        credit_source = str(result.get("directive_track_credit_source", "") or "").strip()
        dossier_artifact_path = str(
            result.get("directive_dossier_artifact_relative_path")
            or result.get("latest_directive_dossier_ref")
            or ""
        ).strip()
        dossier_signature = str(
            result.get("directive_dossier_signature", "") or ""
        ).strip()
        dossier_materially_new = bool(
            result.get("directive_dossier_materially_new", False)
        )
        dossier_rejection_reason = str(
            result.get("directive_dossier_rejection_reason", "") or ""
        ).strip()
        source_coverage_state = str(
            result.get("directive_source_coverage_state", "") or ""
        ).strip()
        librarian_reuse_decision = str(
            result.get("librarian_gap_reuse_decision", "") or ""
        ).strip()
        trusted_source_validation = str(
            result.get("trusted_source_retrieval_validation_state", "") or ""
        ).strip()
        dossier_progress_generated_at = str(
            result.get("directive_dossier_progress_generated_at", "") or ""
        ).strip()
        if not (track_id or artifact_path or dossier_artifact_path):
            if str(row.get("action", "") or result.get("action", "") or "") == (
                "governed_start_next_invocation"
            ):
                return dict(empty_delta)
            continue
        if (
            artifact_depth == "deepened_track_packet"
            or depth_iteration >= 2
            or bool(new_delta)
            or bool(dossier_artifact_path)
        ):
            return {
                "track_id": track_id,
                "artifact_depth": artifact_depth or "deepened_track_packet",
                "depth_iteration": max(depth_iteration, 2),
                "artifact_ref": _hash_payload(
                    {
                        "track_id": track_id,
                        "artifact": artifact_path,
                        "iteration": depth_iteration,
                        "delta_signature": delta_signature,
                    },
                    length=12,
                ),
                "new_information_delta": new_delta,
                "new_information_delta_signature": delta_signature,
                "delta_materially_new": delta_materially_new,
                "delta_rejection_reason": delta_rejection_reason,
                "deliverable_kind": deliverable_kind,
                "delta_focus_id": delta_focus_id,
                "delta_focus_label": delta_focus_label,
                "focus_rotation_state": focus_rotation_state,
                "delta_layer_id": delta_layer_id,
                "delta_layer_label": delta_layer_label,
                "layer_rotation_state": layer_rotation_state,
                "progress_generated_at": progress_generated_at,
                "credit_source": credit_source,
                "operation_result_id": str(row.get("operation_result_id", "") or ""),
                "directive_dossier_artifact_relative_path": dossier_artifact_path,
                "directive_dossier_artifact_ref": _hash_payload(
                    {
                        "artifact": dossier_artifact_path,
                        "signature": dossier_signature,
                        "generated_at": dossier_progress_generated_at,
                    },
                    length=12,
                )
                if dossier_artifact_path
                else "",
                "directive_dossier_signature": dossier_signature,
                "directive_dossier_materially_new": dossier_materially_new,
                "directive_dossier_rejection_reason": dossier_rejection_reason,
                "directive_source_coverage_state": source_coverage_state,
                "librarian_gap_reuse_decision": librarian_reuse_decision,
                "trusted_source_retrieval_validation_state": trusted_source_validation,
                "directive_dossier_progress_generated_at": dossier_progress_generated_at,
            }
    return dict(empty_delta)


def _memory_pressure_root(operator_root: str | Path) -> Path:
    return Path(operator_root) / "memory_pressure"


def _memory_archive_attempts_root(operator_root: str | Path) -> Path:
    return _memory_pressure_root(operator_root) / "archive_attempts"


def _latest_memory_archive_attempt(operator_root: str | Path) -> dict[str, Any]:
    return _read_json(_memory_pressure_root(operator_root) / "attempt_latest.json")


def _ledger_compaction_attempts_root(operator_root: str | Path) -> Path:
    return _memory_pressure_root(operator_root) / "ledger_compaction_attempts"


def _ledger_archive_root(operator_root: str | Path) -> Path:
    return autonomy_root(operator_root) / "ledger_archive"


def _latest_ledger_compaction_attempt(operator_root: str | Path) -> dict[str, Any]:
    return _read_json(_memory_pressure_root(operator_root) / "ledger_compaction_attempt_latest.json")


def _persist_ledger_compaction_attempt(
    operator_root: str | Path,
    attempt: Mapping[str, Any],
    *,
    started_at: float,
) -> dict[str, Any]:
    payload = dict(attempt)
    payload["updated_at"] = _now()
    payload["elapsed_ms"] = round((time.perf_counter() - started_at) * 1000.0, 3)
    attempt_id = str(payload.get("ledger_compaction_attempt_id", "") or "")
    record = _redact_autonomy_value(payload)
    _write_json(_memory_pressure_root(operator_root) / "ledger_compaction_attempt_latest.json", record)
    if attempt_id:
        _write_json(_ledger_compaction_attempts_root(operator_root) / f"{attempt_id}.json", record)
    return dict(record)


def _persist_memory_archive_attempt(
    operator_root: str | Path,
    attempt: Mapping[str, Any],
    *,
    started_at: float,
) -> dict[str, Any]:
    payload = dict(attempt)
    payload["updated_at"] = _now()
    payload["elapsed_ms"] = round((time.perf_counter() - started_at) * 1000.0, 3)
    attempt_id = str(payload.get("memory_archive_attempt_id", "") or "")
    record = _redact_autonomy_value(payload)
    _write_json(_memory_pressure_root(operator_root) / "attempt_latest.json", record)
    if attempt_id:
        _write_json(_memory_archive_attempts_root(operator_root) / f"{attempt_id}.json", record)
    return dict(record)


def _latest_abandoned_memory_archive(operator_root: str | Path) -> dict[str, Any]:
    archive_root = Path(operator_root) / "memory_archive"
    if not archive_root.exists():
        return {}
    latest_attempt = _latest_memory_archive_attempt(operator_root)
    running_archive_id = (
        str(latest_attempt.get("memory_archive_id", "") or "")
        if str(latest_attempt.get("status", "") or "") == "running"
        else ""
    )
    try:
        archive_dirs = sorted(
            [path for path in archive_root.iterdir() if path.is_dir()],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return {}
    for archive_dir in archive_dirs[:10]:
        if running_archive_id and archive_dir.name == running_archive_id:
            continue
        manifest = _read_json(archive_dir / "manifest.json")
        if str(manifest.get("status", "")) == "completed":
            return {}
        if manifest:
            continue
        try:
            child_count = sum(1 for _ in archive_dir.iterdir())
        except OSError:
            child_count = 0
        return {
            "memory_archive_id": archive_dir.name,
            "archive_root": str(archive_dir),
            "status": "abandoned_partial_archive",
            "child_count": child_count,
        }
    return {}


def _cleanup_empty_abandoned_memory_archives(operator_root: str | Path) -> dict[str, Any]:
    archive_root = Path(operator_root) / "memory_archive"
    started = _now()
    result: dict[str, Any] = {
        "schema_name": "NovaliMemoryArchiveCleanup",
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": started,
        "updated_at": started,
        "status": "completed",
        "archive_root": str(archive_root),
        "removed_count": 0,
        "removed_archive_ids": [],
        "skipped_count": 0,
        "skipped_archive_ids": [],
    }
    if not archive_root.exists():
        return result
    try:
        archive_root_resolved = archive_root.resolve()
        archive_dirs = [path for path in archive_root.iterdir() if path.is_dir()]
    except OSError as exc:
        result["status"] = "failed"
        result["error_note"] = str(exc)
        return result
    for archive_dir in archive_dirs:
        try:
            archive_dir.resolve().relative_to(archive_root_resolved)
        except (OSError, ValueError):
            result["skipped_count"] = int(result["skipped_count"]) + 1
            result["skipped_archive_ids"].append(archive_dir.name)
            continue
        manifest = _read_json(archive_dir / "manifest.json")
        try:
            child_count = sum(1 for _ in archive_dir.iterdir())
        except OSError:
            child_count = 1
        if manifest or child_count > 0:
            result["skipped_count"] = int(result["skipped_count"]) + 1
            result["skipped_archive_ids"].append(archive_dir.name)
            continue
        try:
            archive_dir.rmdir()
        except OSError as exc:
            result["skipped_count"] = int(result["skipped_count"]) + 1
            result["skipped_archive_ids"].append(archive_dir.name)
            result["error_note"] = str(exc)
            continue
        result["removed_count"] = int(result["removed_count"]) + 1
        result["removed_archive_ids"].append(archive_dir.name)
    result["updated_at"] = _now()
    _write_json(_memory_pressure_root(operator_root) / "partial_archive_cleanup_latest.json", result)
    return _redact_autonomy_value(result)


def _read_int_file(path: Path) -> int | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text or text == "max":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _proc_self_rss_bytes() -> int | None:
    try:
        text = Path("/proc/self/status").read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"^VmRSS:\s+(\d+)\s+kB$", text, flags=re.MULTILINE)
    if not match:
        return None
    return int(match.group(1)) * 1024


def _latest_governed_invocation_window(operator_root: str | Path) -> dict[str, Any]:
    return _read_json(Path(operator_root) / "governed_invocation_window_latest.json")


def _memory_limit_from_sysconf() -> int | None:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, OSError, ValueError):
        return None
    if not pages or not page_size:
        return None
    return int(pages) * int(page_size)


def _measure_memory_bytes() -> dict[str, Any]:
    override_used = os.environ.get("NOVALI_MEMORY_PRESSURE_TEST_USED_BYTES", "").strip()
    override_limit = os.environ.get("NOVALI_MEMORY_PRESSURE_TEST_LIMIT_BYTES", "").strip()
    if override_used and override_limit:
        try:
            return {
                "used_bytes": int(override_used),
                "limit_bytes": int(override_limit),
                "source": "environment_override",
            }
        except ValueError:
            pass
    cgroup_v2_current = Path("/sys/fs/cgroup/memory.current")
    cgroup_v2_max = Path("/sys/fs/cgroup/memory.max")
    used = _read_int_file(cgroup_v2_current)
    limit = _read_int_file(cgroup_v2_max)
    if used is not None and limit is not None and limit > 0:
        return {"used_bytes": used, "limit_bytes": limit, "source": "cgroup_v2"}
    cgroup_v1_current = Path("/sys/fs/cgroup/memory/memory.usage_in_bytes")
    cgroup_v1_limit = Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    used = _read_int_file(cgroup_v1_current)
    limit = _read_int_file(cgroup_v1_limit)
    if used is not None and limit is not None and limit > 0:
        return {"used_bytes": used, "limit_bytes": limit, "source": "cgroup_v1"}
    used = _proc_self_rss_bytes()
    limit = _memory_limit_from_sysconf()
    if used is not None and limit is not None and limit > 0:
        return {"used_bytes": used, "limit_bytes": limit, "source": "proc_self_rss"}
    return {"used_bytes": 0, "limit_bytes": 0, "source": "unavailable"}


def _memory_pressure_band(percent: float) -> str:
    if percent >= MEMORY_PRESSURE_CRITICAL_PERCENT:
        return "critical"
    if percent >= MEMORY_PRESSURE_ACTION_PERCENT:
        return "action"
    if percent >= MEMORY_PRESSURE_WARNING_PERCENT:
        return "warning"
    return "normal"


def _env_bool(name: str, default: bool = True) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off", "disabled"}


def _env_float(name: str, default: float, *, minimum: float = 0.0) -> float:
    try:
        value = float(str(os.environ.get(name, "")).strip() or default)
    except ValueError:
        value = default
    return max(minimum, value)


def _oom_guard_config() -> dict[str, Any]:
    soft = _env_float("NOVALI_OOM_GUARD_SOFT_PERCENT", OOM_GUARD_SOFT_PERCENT_DEFAULT)
    hibernate = _env_float(
        "NOVALI_OOM_GUARD_HIBERNATE_PERCENT",
        OOM_GUARD_HIBERNATE_PERCENT_DEFAULT,
    )
    recycle = _env_float(
        "NOVALI_OOM_GUARD_RECYCLE_PERCENT",
        OOM_GUARD_RECYCLE_PERCENT_DEFAULT,
    )
    if hibernate < soft:
        hibernate = soft
    if recycle < hibernate:
        recycle = hibernate
    return {
        "enabled": _env_bool("NOVALI_OOM_GUARD_ENABLED", True),
        "soft_percent": soft,
        "hibernate_percent": hibernate,
        "recycle_percent": recycle,
    }


def _memory_smoothing_config() -> dict[str, Any]:
    profile = str(os.environ.get("NOVALI_MEMORY_SPILL_PROFILE", "balanced") or "balanced").strip().lower()
    if profile not in {"balanced", "aggressive"}:
        profile = "balanced"
    default_enter = (
        AGGRESSIVE_MEMORY_SMOOTHING_ENTER_PERCENT_DEFAULT
        if profile == "aggressive"
        else MEMORY_SMOOTHING_ENTER_PERCENT_DEFAULT
    )
    default_exit = (
        AGGRESSIVE_MEMORY_SMOOTHING_EXIT_PERCENT_DEFAULT
        if profile == "aggressive"
        else MEMORY_SMOOTHING_EXIT_PERCENT_DEFAULT
    )
    enter = _env_float(
        "NOVALI_MEMORY_SMOOTHING_ENTER_PERCENT",
        default_enter,
    )
    exit_percent = _env_float(
        "NOVALI_MEMORY_SMOOTHING_EXIT_PERCENT",
        default_exit,
    )
    if exit_percent > enter:
        exit_percent = enter
    return {
        "enabled": _env_bool("NOVALI_MEMORY_SMOOTHING_ENABLED", True),
        "memory_spill_profile": profile,
        "enter_percent": enter,
        "exit_percent": exit_percent,
    }


def _trim_process_memory() -> dict[str, Any]:
    collected = gc.collect()
    result = "unsupported"
    error_note = ""
    if os.name == "posix":
        try:
            libc = ctypes.CDLL("libc.so.6")
            trim_result = int(libc.malloc_trim(0))
            result = "trimmed" if trim_result else "unsupported"
        except Exception as exc:
            result = "failed"
            error_note = type(exc).__name__
    return {
        "result": result,
        "last_trim_result": result,
        "cache_eviction_count": int(collected or 0),
        "trim_error_class": error_note,
    }


def _memory_smoothing_evaluation(
    *,
    percent: float,
    previous_status: Mapping[str, Any],
    oom_guard_state: str,
) -> dict[str, Any]:
    config = _memory_smoothing_config()
    enabled = bool(config.get("enabled", True))
    enter = float(config.get("enter_percent", MEMORY_SMOOTHING_ENTER_PERCENT_DEFAULT) or 0.0)
    exit_percent = float(config.get("exit_percent", MEMORY_SMOOTHING_EXIT_PERCENT_DEFAULT) or 0.0)
    profile = str(config.get("memory_spill_profile", "balanced") or "balanced")
    previous_state = str(previous_status.get("memory_smoothing_state", "normal") or "normal")
    previous_entered_at = str(previous_status.get("cooling_entered_at", "") or "")
    previous_high = float(previous_status.get("memory_high_watermark_percent", 0.0) or 0.0)
    high_watermark = round(max(previous_high, float(percent or 0.0)), 3)
    now = _now()
    if not enabled:
        return {
            "memory_smoothing_enabled": False,
            "memory_spill_profile": profile,
            "memory_smoothing_enter_percent": enter,
            "memory_smoothing_exit_percent": exit_percent,
            "memory_smoothing_state": "normal",
            "latest_smoothing_action": "disabled",
            "latest_spill_action": "disabled",
            "cooling_entered_at": "",
            "cooling_exit_percent": exit_percent,
            "memory_high_watermark_percent": round(float(percent or 0.0), 3),
        }
    if oom_guard_state in {"hibernate_required", "recycle_required"}:
        return {
            "memory_smoothing_enabled": True,
            "memory_spill_profile": profile,
            "memory_smoothing_enter_percent": enter,
            "memory_smoothing_exit_percent": exit_percent,
            "memory_smoothing_state": "failed_to_cool",
            "latest_smoothing_action": "hard_guard_required",
            "latest_spill_action": "hard_guard_required",
            "cooling_entered_at": previous_entered_at or now,
            "cooling_exit_percent": exit_percent,
            "memory_high_watermark_percent": high_watermark,
        }
    cooling_was_active = previous_state in {"cooling", "spilling", "failed_to_cool"}
    if float(percent or 0.0) >= enter:
        smoothing_action = "cooling_continues" if cooling_was_active else "cooling_started"
        spill_action = "refresh_indexes_and_trim" if profile == "aggressive" else "trim_and_remeasure"
        if profile == "aggressive" and not cooling_was_active:
            smoothing_action = "aggressive_spill_started"
        return {
            "memory_smoothing_enabled": True,
            "memory_spill_profile": profile,
            "memory_smoothing_enter_percent": enter,
            "memory_smoothing_exit_percent": exit_percent,
            "memory_smoothing_state": "cooling",
            "latest_smoothing_action": smoothing_action,
            "latest_spill_action": spill_action,
            "cooling_entered_at": previous_entered_at or now,
            "cooling_exit_percent": exit_percent,
            "memory_high_watermark_percent": high_watermark,
        }
    if cooling_was_active and float(percent or 0.0) > exit_percent:
        return {
            "memory_smoothing_enabled": True,
            "memory_spill_profile": profile,
            "memory_smoothing_enter_percent": enter,
            "memory_smoothing_exit_percent": exit_percent,
            "memory_smoothing_state": "cooling",
            "latest_smoothing_action": "cooling_hysteresis_hold",
            "latest_spill_action": (
                "refresh_indexes_and_trim" if profile == "aggressive" else "trim_and_remeasure"
            ),
            "cooling_entered_at": previous_entered_at or now,
            "cooling_exit_percent": exit_percent,
            "memory_high_watermark_percent": high_watermark,
        }
    if cooling_was_active:
        return {
            "memory_smoothing_enabled": True,
            "memory_spill_profile": profile,
            "memory_smoothing_enter_percent": enter,
            "memory_smoothing_exit_percent": exit_percent,
            "memory_smoothing_state": "recovered",
            "latest_smoothing_action": "cooling_recovered",
            "latest_spill_action": "cooling_recovered",
            "cooling_entered_at": previous_entered_at,
            "cooling_exit_percent": exit_percent,
            "memory_high_watermark_percent": high_watermark,
        }
    return {
        "memory_smoothing_enabled": True,
        "memory_spill_profile": profile,
        "memory_smoothing_enter_percent": enter,
        "memory_smoothing_exit_percent": exit_percent,
        "memory_smoothing_state": "normal",
        "latest_smoothing_action": "none",
        "latest_spill_action": "none",
        "cooling_entered_at": "",
        "cooling_exit_percent": exit_percent,
        "memory_high_watermark_percent": round(float(percent or 0.0), 3),
    }


def _oom_guard_evaluation(
    *,
    used_bytes: int,
    limit_bytes: int,
    percent: float,
    pressure_band: str,
    latest_recovery: Mapping[str, Any],
) -> dict[str, Any]:
    config = _oom_guard_config()
    headroom_bytes = max(0, int(limit_bytes or 0) - int(used_bytes or 0))
    state = "disabled"
    action = "none"
    reason = "oom guard disabled"
    if bool(config.get("enabled", True)):
        state = "normal"
        action = "none"
        reason = "memory below oom guard soft threshold"
        if percent >= float(config.get("recycle_percent", OOM_GUARD_RECYCLE_PERCENT_DEFAULT)):
            state = "recycle_required"
            action = "request_service_recycle"
            reason = "memory at or above oom guard recycle threshold"
        elif percent >= float(config.get("hibernate_percent", OOM_GUARD_HIBERNATE_PERCENT_DEFAULT)):
            state = "hibernate_required"
            action = "hibernate_for_memory_pressure"
            reason = "memory at or above oom guard hibernate threshold"
        elif percent >= float(config.get("soft_percent", OOM_GUARD_SOFT_PERCENT_DEFAULT)):
            state = "soft_warning"
            action = "warn"
            reason = "memory at or above oom guard soft threshold"
    return {
        "oom_guard_enabled": bool(config.get("enabled", True)),
        "oom_guard_soft_percent": float(config.get("soft_percent", 0.0)),
        "oom_guard_hibernate_percent": float(config.get("hibernate_percent", 0.0)),
        "oom_guard_recycle_percent": float(config.get("recycle_percent", 0.0)),
        "oom_guard_state": state,
        "oom_guard_action": action,
        "oom_guard_reason": reason,
        "hibernate_recommended": state in {"hibernate_required", "recycle_required"},
        "service_recycle_recommended": state == "recycle_required",
        "memory_headroom_gib": round(headroom_bytes / (1024 ** 3), 3) if headroom_bytes else 0,
        "pressure_band": pressure_band,
        "last_recycle_request_id": (
            str(latest_recovery.get("memory_recovery_request_id", ""))
            if str(latest_recovery.get("recovery_state", "")) == "service_recycle_requested"
            else ""
        ),
    }


def memory_pressure_status(operator_root: str | Path, *, persist: bool = True) -> dict[str, Any]:
    measurement = _measure_memory_bytes()
    used = int(measurement.get("used_bytes", 0) or 0)
    limit = int(measurement.get("limit_bytes", 0) or 0)
    percent = round((used / limit) * 100.0, 3) if used > 0 and limit > 0 else 0.0
    band = _memory_pressure_band(percent)
    previous_status = _read_json(_memory_pressure_root(operator_root) / "status_latest.json")
    previous_created = _record_created_at(previous_status)
    measurement_age_seconds = (
        max(0.0, round((datetime.now(timezone.utc) - previous_created).total_seconds(), 3))
        if previous_created
        else 0.0
    )
    previous_status_stale = (
        bool(previous_status)
        and (previous_created is None or measurement_age_seconds > MEMORY_PRESSURE_STALE_STATUS_SECONDS)
    )
    latest_archive = _latest(operator_root, "memory_archive_manifests")
    latest_attempt = _latest_memory_archive_attempt(operator_root)
    latest_compaction_attempt = _latest_ledger_compaction_attempt(operator_root)
    abandoned_archive = _latest_abandoned_memory_archive(operator_root)
    latest_recovery = _latest(operator_root, "memory_recovery_requests")
    if (
        band == "normal"
        and str(latest_recovery.get("recovery_state", "")) in OOM_GUARD_RECOVERY_STATES
    ):
        latest_recovery = _write_memory_recovery_restored_request(
            operator_root=operator_root,
            prior_recovery=latest_recovery,
            status_after_recovery={
                "pressure_band": band,
                "memory_percent": percent,
                "measurement_source": str(measurement.get("source", "")),
            },
        )
    oom_guard = _oom_guard_evaluation(
        used_bytes=used,
        limit_bytes=limit,
        percent=percent,
        pressure_band=band,
        latest_recovery=latest_recovery,
    )
    smoothing = _memory_smoothing_evaluation(
        percent=percent,
        previous_status=previous_status,
        oom_guard_state=str(oom_guard.get("oom_guard_state", "normal")),
    )
    trim_result: dict[str, Any] = {}
    smoothing_state = str(smoothing.get("memory_smoothing_state", "normal"))
    if persist and smoothing_state in {"cooling", "spilling", "recovered"}:
        trim_result = _trim_process_memory()
    desired_recovery_state = (
        "service_recycle_requested"
        if str(oom_guard.get("oom_guard_state", "")) == "recycle_required"
        else "hibernated_for_memory_pressure"
        if str(oom_guard.get("oom_guard_state", "")) == "hibernate_required"
        else ""
    )
    if (
        persist
        and desired_recovery_state
        and str(latest_recovery.get("recovery_state", "")) != desired_recovery_state
    ):
        latest_recovery = _write_memory_guard_recovery_request(
            operator_root=operator_root,
            recovery_state=desired_recovery_state,
            oom_guard=oom_guard,
            status_after_measurement={
                "pressure_band": band,
                "memory_percent": percent,
                "measurement_source": str(measurement.get("source", "")),
            },
        )
        oom_guard["last_recycle_request_id"] = (
            str(latest_recovery.get("memory_recovery_request_id", ""))
            if desired_recovery_state == "service_recycle_requested"
            else ""
        )
    attempt_status = str(latest_attempt.get("status", "") or "")
    attempt_archived_count = int(latest_attempt.get("archived_count", 0) or 0)
    compaction_status = str(latest_compaction_attempt.get("status", "") or "")
    compaction_record_count = int(latest_compaction_attempt.get("compacted_record_count", 0) or 0)
    compaction_progress_class = str(
        latest_compaction_attempt.get("latest_compaction_progress_class", "")
        or latest_compaction_attempt.get("compaction_progress_class", "")
    )
    if not compaction_progress_class:
        if compaction_status == "timeout_with_progress" or (
            compaction_status == "timeout" and compaction_record_count > 0
        ):
            compaction_progress_class = "timeout_with_progress"
        elif compaction_status == "timeout":
            compaction_progress_class = "timeout_no_progress"
        elif compaction_status:
            compaction_progress_class = compaction_status
    restart_after_stall = (
        band in {"warning", "action", "critical"}
        and attempt_status in {"timeout", "completed_with_warnings", "failed"}
        and attempt_archived_count <= 0
    )
    restart_after_compaction = (
        band in {"warning", "action", "critical"}
        and (
            bool(latest_compaction_attempt.get("restart_recommended_after_compaction", False))
            or (
                compaction_status in {"timeout", "timeout_no_progress", "no_progress", "completed_with_warnings", "failed"}
                and compaction_record_count <= 0
            )
        )
    )
    partial_archive_detected = bool(abandoned_archive) or attempt_status in {
        "timeout",
        "completed_with_warnings",
        "failed",
    }
    partial_archive_attention_required = bool(
        partial_archive_detected and band in {"warning", "action", "critical"}
    )
    partial_archive_cleanup_state = "not_required"
    if abandoned_archive:
        partial_archive_cleanup_state = (
            "empty_abandoned_archive_detected"
            if int(abandoned_archive.get("child_count", 0) or 0) <= 0
            else "non_empty_abandoned_archive_detected"
        )
    ledger_index_state = "not_configured"
    data_at_rest_catalog_state = "not_configured"
    cache_view_age_seconds = 0.0
    spill_runtime_log_bytes = 0
    spill_cold_artifact_bytes = 0
    spill_volume_bytes = 0
    spill_pointer_count = 0
    spill_backlog_count = 0
    spill_mode = "move_cold"
    latest_spill_result = "unknown"
    spill_sweeper_state = "idle"
    spill_activity_state = "idle"
    next_spill_due_at = ""
    last_spill_started_at = ""
    last_spill_finished_at = ""
    runtime_log_segment_count = 0
    runtime_log_bundle_count = 0
    runtime_log_bundle_bytes = 0
    runtime_log_small_file_backlog_count = 0
    runtime_log_bundle_latest_result = ""
    runtime_log_active_tail_bytes = 0
    cold_artifact_backlog_count = 0
    cold_artifact_backlog_bytes = 0
    spill_budget_bytes = 0
    spill_budget_used_bytes = 0
    try:
        from .disk_spill import data_at_rest_catalog_path, spill_status

        index_dir = autonomy_root(operator_root) / "ledger_indexes"
        ledger_index_state = "ready" if index_dir.exists() and any(index_dir.glob("*.index.json")) else "warming"
        state_root = os.environ.get("NOVALI_STATE_ROOT", "")
        if state_root:
            catalog_path = data_at_rest_catalog_path(state_root)
            if catalog_path.exists():
                data_at_rest_catalog_state = "ready"
                created = _record_created_at(_read_json(catalog_path))
                if created is not None:
                    cache_view_age_seconds = max(
                        0.0,
                        round((datetime.now(timezone.utc) - created).total_seconds(), 3),
                    )
            else:
                data_at_rest_catalog_state = "warming"
            spill = spill_status(state_root)
            spill_runtime_log_bytes = int(spill.get("runtime_log_spill_bytes", 0) or 0)
            spill_cold_artifact_bytes = int(spill.get("cold_artifact_spill_bytes", 0) or 0)
            spill_volume_bytes = int(spill.get("spill_volume_bytes", 0) or 0)
            spill_pointer_count = int(spill.get("spill_pointer_count", 0) or 0)
            spill_backlog_count = int(spill.get("spill_backlog_count", 0) or 0)
            spill_mode = str(spill.get("spill_mode", "move_cold") or "move_cold")
            latest_spill_result = str(spill.get("latest_spill_result", "unknown") or "unknown")
            spill_sweeper_state = str(spill.get("spill_sweeper_state", "idle") or "idle")
            spill_activity_state = str(spill.get("spill_activity_state", "idle") or "idle")
            next_spill_due_at = str(spill.get("next_spill_due_at", "") or "")
            last_spill_started_at = str(spill.get("last_spill_started_at", "") or "")
            last_spill_finished_at = str(spill.get("last_spill_finished_at", "") or "")
            runtime_log_segment_count = int(spill.get("runtime_log_segment_count", 0) or 0)
            runtime_log_bundle_count = int(spill.get("runtime_log_bundle_count", 0) or 0)
            runtime_log_bundle_bytes = int(spill.get("runtime_log_bundle_bytes", 0) or 0)
            runtime_log_small_file_backlog_count = int(spill.get("runtime_log_small_file_backlog_count", 0) or 0)
            runtime_log_bundle_latest_result = str(spill.get("runtime_log_bundle_latest_result", "") or "")
            runtime_log_active_tail_bytes = int(spill.get("runtime_log_active_tail_bytes", 0) or 0)
            cold_artifact_backlog_count = int(spill.get("cold_artifact_backlog_count", 0) or 0)
            cold_artifact_backlog_bytes = int(spill.get("cold_artifact_backlog_bytes", 0) or 0)
            spill_budget_bytes = int(spill.get("spill_budget_bytes", 0) or 0)
            spill_budget_used_bytes = int(spill.get("spill_budget_used_bytes", 0) or 0)
    except Exception:
        ledger_index_state = "unknown"
        data_at_rest_catalog_state = "unknown"
    disk_spill_bytes = max(
        0,
        int(latest_compaction_attempt.get("archived_bytes", 0) or 0)
        + int(latest_attempt.get("recovered_bytes", 0) or 0),
    )
    disk_spill_bytes += max(0, spill_runtime_log_bytes + runtime_log_bundle_bytes + spill_cold_artifact_bytes)
    status = {
        "schema_name": MEMORY_PRESSURE_STATUS_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "memory_pressure_status_id": "",
        "used_bytes": used,
        "limit_bytes": limit,
        "used_gib": round(used / (1024 ** 3), 3) if used else 0,
        "limit_gib": round(limit / (1024 ** 3), 3) if limit else 0,
        "memory_percent": percent,
        "pressure_band": band,
        "measurement_source": str(measurement.get("source", "")),
        "measurement_age_seconds": measurement_age_seconds,
        "stale_measurement": False,
        "fresh_measurement_required": previous_status_stale,
        "previous_memory_pressure_status_id": str(previous_status.get("memory_pressure_status_id", "")),
        "previous_pressure_band": str(previous_status.get("pressure_band", "")),
        "warning_threshold_percent": MEMORY_PRESSURE_WARNING_PERCENT,
        "action_threshold_percent": MEMORY_PRESSURE_ACTION_PERCENT,
        "critical_threshold_percent": MEMORY_PRESSURE_CRITICAL_PERCENT,
        "oom_guard_enabled": bool(oom_guard.get("oom_guard_enabled", True)),
        "oom_guard_soft_percent": float(oom_guard.get("oom_guard_soft_percent", 0.0) or 0.0),
        "oom_guard_hibernate_percent": float(
            oom_guard.get("oom_guard_hibernate_percent", 0.0) or 0.0
        ),
        "oom_guard_recycle_percent": float(
            oom_guard.get("oom_guard_recycle_percent", 0.0) or 0.0
        ),
        "oom_guard_state": str(oom_guard.get("oom_guard_state", "normal")),
        "oom_guard_action": str(oom_guard.get("oom_guard_action", "none")),
        "oom_guard_reason": str(oom_guard.get("oom_guard_reason", "")),
        "hibernate_recommended": bool(oom_guard.get("hibernate_recommended", False)),
        "service_recycle_recommended": bool(
            oom_guard.get("service_recycle_recommended", False)
        ),
        "memory_smoothing_enabled": bool(smoothing.get("memory_smoothing_enabled", True)),
        "memory_spill_profile": str(smoothing.get("memory_spill_profile", "balanced") or "balanced"),
        "memory_smoothing_enter_percent": float(
            smoothing.get("memory_smoothing_enter_percent", 0.0) or 0.0
        ),
        "memory_smoothing_exit_percent": float(
            smoothing.get("memory_smoothing_exit_percent", 0.0) or 0.0
        ),
        "memory_smoothing_state": smoothing_state,
        "memory_high_watermark_percent": float(
            smoothing.get("memory_high_watermark_percent", percent) or 0.0
        ),
        "cooling_entered_at": str(smoothing.get("cooling_entered_at", "")),
        "cooling_exit_percent": float(smoothing.get("cooling_exit_percent", 0.0) or 0.0),
        "latest_smoothing_action": str(smoothing.get("latest_smoothing_action", "none")),
        "latest_spill_action": str(smoothing.get("latest_spill_action", "none")),
        "ledger_index_state": ledger_index_state,
        "data_at_rest_catalog_state": data_at_rest_catalog_state,
        "cache_view_age_seconds": cache_view_age_seconds,
        "index_hit_rate": 1.0 if ledger_index_state == "ready" else 0.0,
        "last_trim_result": str(
            trim_result.get("last_trim_result")
            or previous_status.get("last_trim_result", "")
            or ""
        ),
        "cache_eviction_count": int(trim_result.get("cache_eviction_count", 0) or 0),
        "disk_spill_bytes": disk_spill_bytes,
        "spill_mode": spill_mode,
        "runtime_log_spill_bytes": spill_runtime_log_bytes,
        "runtime_log_bundle_count": runtime_log_bundle_count,
        "runtime_log_bundle_bytes": runtime_log_bundle_bytes,
        "runtime_log_small_file_backlog_count": runtime_log_small_file_backlog_count,
        "runtime_log_bundle_latest_result": runtime_log_bundle_latest_result,
        "cold_artifact_spill_bytes": spill_cold_artifact_bytes,
        "spill_volume_bytes": spill_volume_bytes,
        "spill_pointer_count": spill_pointer_count,
        "spill_backlog_count": spill_backlog_count,
        "latest_spill_result": latest_spill_result,
        "spill_sweeper_state": spill_sweeper_state,
        "spill_activity_state": spill_activity_state,
        "next_spill_due_at": next_spill_due_at,
        "last_spill_started_at": last_spill_started_at,
        "last_spill_finished_at": last_spill_finished_at,
        "runtime_log_segment_count": runtime_log_segment_count,
        "runtime_log_active_tail_bytes": runtime_log_active_tail_bytes,
        "cold_artifact_backlog_count": cold_artifact_backlog_count,
        "cold_artifact_backlog_bytes": cold_artifact_backlog_bytes,
        "spill_budget_bytes": spill_budget_bytes,
        "spill_budget_used_bytes": spill_budget_used_bytes,
        "memory_headroom_gib": float(oom_guard.get("memory_headroom_gib", 0.0) or 0.0),
        "last_recycle_request_id": (
            str(latest_recovery.get("memory_recovery_request_id", ""))
            if str(latest_recovery.get("recovery_state", "")) == "service_recycle_requested"
            else str(oom_guard.get("last_recycle_request_id", ""))
        ),
        "archive_recommended": band in {"warning", "action", "critical"},
        "restart_recommended": band in {"action", "critical"},
        "latest_archive_id": str(latest_archive.get("memory_archive_id", "")),
        "latest_recovered_bytes": int(latest_archive.get("recovered_bytes", 0) or 0),
        "latest_recovery_state": str(latest_recovery.get("recovery_state", "")),
        "latest_archive_attempt_id": str(latest_attempt.get("memory_archive_attempt_id", "")),
        "latest_archive_attempt_status": attempt_status,
        "latest_archive_attempt_phase": str(latest_attempt.get("phase", "")),
        "latest_archive_attempt_elapsed_ms": float(latest_attempt.get("elapsed_ms", 0.0) or 0.0),
        "latest_archive_attempt_timeout_reason": str(
            latest_attempt.get("timeout_reason", "") or latest_attempt.get("error_note", "")
        ),
        "latest_archive_attempt_archived_count": attempt_archived_count,
        "latest_archive_attempt_recovered_bytes": int(latest_attempt.get("recovered_bytes", 0) or 0),
        "latest_ledger_compaction_attempt_id": str(
            latest_compaction_attempt.get("ledger_compaction_attempt_id", "")
        ),
        "latest_ledger_compaction_status": compaction_status,
        "latest_compaction_progress_class": compaction_progress_class,
        "latest_ledger_compaction_phase": str(latest_compaction_attempt.get("phase", "")),
        "latest_ledger_compaction_elapsed_ms": float(
            latest_compaction_attempt.get("elapsed_ms", 0.0) or 0.0
        ),
        "latest_ledger_compaction_timeout_reason": str(
            latest_compaction_attempt.get("timeout_reason", "")
            or latest_compaction_attempt.get("error_note", "")
        ),
        "ledger_compaction_compacted_ledger_count": int(
            latest_compaction_attempt.get("compacted_ledger_count", 0) or 0
        ),
        "ledger_compaction_compacted_record_count": compaction_record_count,
        "ledger_compaction_compacted_bytes": int(
            latest_compaction_attempt.get("bytes_reduced", 0) or 0
        ),
        "ledger_compaction_hot_tail_records": int(
            latest_compaction_attempt.get("hot_tail_records", LEDGER_COMPACTION_DEFAULT_HOT_TAIL_RECORDS)
            or LEDGER_COMPACTION_DEFAULT_HOT_TAIL_RECORDS
        ),
        "ledger_compaction_archive_segment_count": _ledger_compaction_segment_count(operator_root),
        "restart_recommended_after_compaction": restart_after_compaction,
        "latest_abandoned_partial_archive": abandoned_archive,
        "partial_archive_detected": partial_archive_detected,
        "partial_archive_attention_required": partial_archive_attention_required,
        "partial_archive_cleanup_state": partial_archive_cleanup_state,
        "restart_recommended_after_archive_stall": restart_after_stall,
    }
    status["memory_pressure_status_id"] = _record_id("memory-pressure", status)
    try:
        record_oom_guard(status)
    except Exception:
        pass
    try:
        record_memory_smoothing(status)
    except Exception:
        pass
    if trim_result:
        try:
            record_memory_trim({**status, **trim_result})
        except Exception:
            pass
    if disk_spill_bytes > 0 or str(status.get("latest_spill_action", "")) == "refresh_indexes_and_trim":
        try:
            record_memory_disk_spill(
                {
                    **status,
                    "result": "completed" if disk_spill_bytes > 0 else "scheduled",
                    "spill_kind": (
                        "ledger_compaction"
                        if disk_spill_bytes > 0
                        else "ledger_index_refresh"
                    ),
                }
            )
        except Exception:
            pass
    if not persist:
        return _redact_autonomy_value(status)
    record = _redact_autonomy_value(status)
    _write_json(_memory_pressure_root(operator_root) / "status_latest.json", record)
    if (
        str(record.get("memory_smoothing_state", "")) in {"normal", "recovered"}
        and not bool(record.get("service_recycle_recommended", False))
    ):
        runtime_status = _read_json(_status_path(operator_root))
        if str(runtime_status.get("latest_recycle_executor_state", "")) == "scheduled":
            runtime_status["latest_recycle_executor_state"] = "recovered_after_restart"
            runtime_status["latest_recycle_executor_reason"] = "memory_normal_after_restart"
            runtime_status["last_refresh_result"] = "memory_recycle_state_cleared"
            runtime_status["generated_at"] = _now()
            _write_json(_status_path(operator_root), runtime_status)
    return dict(record)


def _latest_memory_pressure_status(operator_root: str | Path) -> dict[str, Any]:
    latest = _read_json(_memory_pressure_root(operator_root) / "status_latest.json")
    if not latest:
        return memory_pressure_status(operator_root, persist=True)
    created = _record_created_at(latest)
    if created is None:
        return memory_pressure_status(operator_root, persist=True)
    age_seconds = max(0.0, (datetime.now(timezone.utc) - created).total_seconds())
    if age_seconds > MEMORY_PRESSURE_STALE_STATUS_SECONDS:
        return memory_pressure_status(operator_root, persist=True)
    latest = dict(latest)
    latest["measurement_age_seconds"] = round(age_seconds, 3)
    latest["stale_measurement"] = False
    latest["fresh_measurement_required"] = False
    return latest


def _safe_int_env(name: str, default: int, *, minimum: int = 0) -> int:
    try:
        value = int(str(os.environ.get(name, "")).strip() or default)
    except ValueError:
        value = default
    return max(minimum, value)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return path.name


def _ledger_compaction_deadline_reached(started_at: float, timeout_seconds: float) -> bool:
    return timeout_seconds > 0 and (time.perf_counter() - started_at) >= timeout_seconds


def _ledger_record_timestamp(line: str) -> str:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, Mapping):
        return ""
    for key in ("created_at", "updated_at", "generated_at", "timestamp"):
        value = str(payload.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _ledger_compaction_cursor_path(operator_root: str | Path, ledger_name: str) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", ledger_name).strip("_") or "ledger"
    return _memory_pressure_root(operator_root) / "ledger_compaction_cursors" / f"{safe_name}.json"


def _write_ledger_compaction_cursor(
    operator_root: str | Path,
    cursor: Mapping[str, Any],
) -> dict[str, Any]:
    ledger_name = str(cursor.get("ledger_name", "") or "")
    record = _redact_autonomy_value(dict(cursor))
    _write_json(_ledger_compaction_cursor_path(operator_root, ledger_name), record)
    _append_ledger(operator_root, "ledger_compaction_cursors", record)
    return dict(record)


def _ledger_compaction_segment_count(operator_root: str | Path) -> int:
    archive_root = _ledger_archive_root(operator_root)
    if not archive_root.exists():
        return 0
    try:
        return sum(1 for _ in archive_root.glob("*/*.manifest.json"))
    except OSError:
        return 0


def _ledger_compaction_candidate_ledgers(
    operator_root: str | Path,
    *,
    hot_tail_records: int,
    max_ledgers: int,
    max_source_bytes: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    ledgers_root = autonomy_root(operator_root) / "ledgers"
    skipped: dict[str, int] = {}
    if not ledgers_root.exists():
        skipped["missing_ledgers_root"] = 1
        return [], skipped
    excluded_names = {
        "ledger_compaction_attempts",
        "ledger_compaction_cursors",
        "ledger_compaction_segment_manifests",
    }
    candidates: list[dict[str, Any]] = []
    source_bytes = 0
    try:
        paths = sorted(
            [path for path in ledgers_root.glob("*.jsonl") if path.is_file()],
            key=lambda path: path.stat().st_size,
            reverse=False,
        )
    except OSError:
        skipped["candidate_scan_error"] = 1
        return [], skipped
    for path in paths:
        ledger_name = path.stem
        if ledger_name in excluded_names:
            skipped["compaction_own_ledger"] = skipped.get("compaction_own_ledger", 0) + 1
            continue
        try:
            size = path.stat().st_size
        except OSError:
            skipped["unreadable"] = skipped.get("unreadable", 0) + 1
            continue
        if source_bytes + size > max_source_bytes:
            skipped["source_byte_limit_reached"] = skipped.get("source_byte_limit_reached", 0) + 1
            continue
        try:
            with path.open("rb") as handle:
                record_count = sum(1 for line in handle if line.strip())
        except OSError:
            skipped["unreadable"] = skipped.get("unreadable", 0) + 1
            continue
        if record_count <= hot_tail_records:
            skipped["below_hot_tail"] = skipped.get("below_hot_tail", 0) + 1
            continue
        source_bytes += size
        candidates.append(
            {
                "ledger_name": ledger_name,
                "path": path,
                "source_bytes": size,
                "record_count": record_count,
            }
        )
        if len(candidates) >= max_ledgers:
            break
    return candidates, skipped


def _compact_one_ledger(
    *,
    operator_root: str | Path,
    ledger_name: str,
    path: Path,
    hot_tail_records: int,
    operation_id: str,
) -> dict[str, Any]:
    source_hasher = hashlib.sha256()
    total_records = 0
    source_bytes_len = 0
    with path.open("rb") as handle:
        for raw_line in handle:
            source_bytes_len += len(raw_line)
            source_hasher.update(raw_line)
            if raw_line.strip():
                total_records += 1
    source_sha256 = source_hasher.hexdigest()
    if total_records <= hot_tail_records:
        return {"status": "skipped", "reason": "below_hot_tail", "ledger_name": ledger_name}
    cold_record_count = total_records - hot_tail_records
    segment_seed = {
        "ledger_name": ledger_name,
        "operation_id": operation_id,
        "record_count": cold_record_count,
        "source_sha256": source_sha256,
        "created_at": _now(),
    }
    segment_id = _record_id("ledger-segment", segment_seed)
    segment_root = _ledger_archive_root(operator_root) / ledger_name
    segment_root.mkdir(parents=True, exist_ok=True)
    segment_path = segment_root / f"{segment_id}.jsonl.gz"
    manifest_path = segment_root / f"{segment_id}.manifest.json"
    temp_segment = segment_path.with_suffix(segment_path.suffix + ".tmp")
    temp_manifest = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temp_source = path.with_suffix(path.suffix + ".tmp")
    archived_hasher = hashlib.sha256()
    archived_bytes_len = 0
    hot_lines: list[str] = []
    first_archived_line = ""
    last_archived_line = ""
    record_index = 0
    with gzip.open(temp_segment, "wb") as handle:
        with path.open("rb") as source_handle:
            for raw_line in source_handle:
                if not raw_line.strip():
                    continue
                line = raw_line.decode("utf-8", errors="replace").strip()
                if record_index < cold_record_count:
                    encoded = (line + "\n").encode("utf-8")
                    handle.write(encoded)
                    archived_hasher.update(encoded)
                    archived_bytes_len += len(encoded)
                    if not first_archived_line:
                        first_archived_line = line
                    last_archived_line = line
                else:
                    hot_lines.append(line)
                record_index += 1
    archived_sha256 = archived_hasher.hexdigest()
    verified_hasher = hashlib.sha256()
    with gzip.open(temp_segment, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            verified_hasher.update(chunk)
    verified_sha256 = verified_hasher.hexdigest()
    if verified_sha256 != archived_sha256:
        try:
            temp_segment.unlink(missing_ok=True)
        except OSError:
            pass
        raise OSError("ledger compaction segment verification failed")
    manifest = {
        "schema_name": LEDGER_COMPACTION_SEGMENT_MANIFEST_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "ledger_compaction_segment_manifest_id": "",
        "operation_id": operation_id,
        "ledger_name": ledger_name,
        "segment_id": segment_id,
        "segment_path": str(segment_path),
        "manifest_path": str(manifest_path),
        "source_ledger_path_hint": str(path),
        "source_record_count_before": total_records,
        "source_record_count_after": len(hot_lines),
        "hot_tail_records": hot_tail_records,
        "archived_record_count": cold_record_count,
        "source_bytes_before": source_bytes_len,
        "source_bytes_after": len(("\n".join(hot_lines) + "\n").encode("utf-8")),
        "archived_bytes": archived_bytes_len,
        "source_fingerprint_before": f"sha256:{source_sha256}",
        "archived_uncompressed_fingerprint": f"sha256:{archived_sha256}",
        "archived_gzip_fingerprint": f"sha256:{_hash_file(temp_segment)}",
        "first_archived_timestamp": _ledger_record_timestamp(first_archived_line),
        "last_archived_timestamp": _ledger_record_timestamp(last_archived_line),
        "source_start_record_index": 0,
        "source_end_record_index": max(0, cold_record_count - 1),
        "redaction_status": "manifest_contains_hashes_counts_offsets_and_path_hints_only",
        "secret_handling": "manifest never stores ledger record payloads or credential values",
    }
    manifest["ledger_compaction_segment_manifest_id"] = _record_id("ledger-segment-manifest", manifest)
    temp_manifest.write_text(_json_dump(_redact_autonomy_value(manifest)) + "\n", encoding="utf-8")
    hot_bytes = ("\n".join(hot_lines) + "\n").encode("utf-8")
    temp_source.write_bytes(hot_bytes)
    os.replace(temp_segment, segment_path)
    os.replace(temp_manifest, manifest_path)
    os.replace(temp_source, path)
    manifest_record = _append_ledger(operator_root, "ledger_compaction_segment_manifests", manifest)
    _write_json(manifest_path, manifest_record)
    cursor = {
        "schema_name": LEDGER_COMPACTION_CURSOR_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "updated_at": _now(),
        "ledger_compaction_cursor_id": "",
        "operation_id": operation_id,
        "ledger_name": ledger_name,
        "latest_segment_id": segment_id,
        "latest_segment_manifest_id": str(manifest_record.get("ledger_compaction_segment_manifest_id", "")),
        "hot_tail_records": hot_tail_records,
        "compacted_record_count": cold_record_count,
        "source_record_count_after": len(hot_lines),
        "source_fingerprint_after": f"sha256:{hashlib.sha256(hot_bytes).hexdigest()}",
    }
    cursor["ledger_compaction_cursor_id"] = _record_id("ledger-cursor", cursor)
    _write_ledger_compaction_cursor(operator_root, cursor)
    return {
        "status": "compacted",
        "ledger_name": ledger_name,
        "segment_id": segment_id,
        "segment_path": str(segment_path),
        "manifest_path": str(manifest_path),
        "compacted_record_count": cold_record_count,
        "bytes_reduced": max(0, source_bytes_len - len(hot_bytes)),
        "archived_bytes": archived_bytes_len,
        "source_record_count_after": len(hot_lines),
        "manifest": manifest_record,
    }


def _memory_ledger_compaction(
    *,
    operator_root: str | Path,
    operation: Mapping[str, Any],
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    operation_timeout = int(timeout_seconds or LEDGER_COMPACTION_DEFAULT_TIMEOUT_SECONDS)
    compaction_timeout = min(
        operation_timeout,
        _safe_int_env(
            "NOVALI_LEDGER_COMPACTION_TIMEOUT_SECONDS",
            LEDGER_COMPACTION_DEFAULT_TIMEOUT_SECONDS,
            minimum=1,
        ),
    )
    hot_tail_records = _safe_int_env(
        "NOVALI_LEDGER_COMPACTION_HOT_TAIL_RECORDS",
        LEDGER_COMPACTION_DEFAULT_HOT_TAIL_RECORDS,
        minimum=1,
    )
    max_ledgers = _safe_int_env(
        "NOVALI_LEDGER_COMPACTION_MAX_LEDGERS",
        LEDGER_COMPACTION_DEFAULT_MAX_LEDGERS,
        minimum=1,
    )
    max_source_bytes = _safe_int_env(
        "NOVALI_LEDGER_COMPACTION_MAX_SOURCE_BYTES",
        LEDGER_COMPACTION_DEFAULT_MAX_SOURCE_BYTES,
        minimum=1,
    )
    operation_id = str(operation.get("operation_id", ""))
    status_before = memory_pressure_status(operator_root, persist=True)
    attempt = {
        "schema_name": LEDGER_COMPACTION_ATTEMPT_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "updated_at": "",
        "ledger_compaction_attempt_id": "",
        "operation_id": operation_id,
        "phase": "initialized",
        "status": "running",
        "timeout_seconds": compaction_timeout,
        "elapsed_ms": 0.0,
        "source_root": str(autonomy_root(operator_root) / "ledgers"),
        "archive_root": str(_ledger_archive_root(operator_root)),
        "hot_tail_records": hot_tail_records,
        "max_ledgers_per_pass": max_ledgers,
        "max_source_bytes_per_pass": max_source_bytes,
        "candidate_ledger_count": 0,
        "compacted_ledger_count": 0,
        "compacted_record_count": 0,
        "bytes_reduced": 0,
        "archived_bytes": 0,
        "archive_segment_count": _ledger_compaction_segment_count(operator_root),
        "compacted_ledgers": [],
        "skipped_counts": {},
        "timeout_reason": "",
        "latest_compaction_progress_class": "",
        "error_note": "",
        "restart_recommended_after_compaction": False,
        "recovery_recommendation": "Ledger compaction attempt started; no recovery decision recorded yet.",
    }
    attempt["ledger_compaction_attempt_id"] = _record_id("ledger-compaction-attempt", attempt)
    _persist_ledger_compaction_attempt(operator_root, attempt, started_at=started_at)
    attempt["phase"] = "candidate_discovery"
    _persist_ledger_compaction_attempt(operator_root, attempt, started_at=started_at)
    candidates, skipped = _ledger_compaction_candidate_ledgers(
        operator_root,
        hot_tail_records=hot_tail_records,
        max_ledgers=max_ledgers,
        max_source_bytes=max_source_bytes,
    )
    attempt["candidate_ledger_count"] = len(candidates)
    attempt["skipped_counts"] = skipped
    attempt["phase"] = "segment_write"
    _persist_ledger_compaction_attempt(operator_root, attempt, started_at=started_at)
    compacted: list[dict[str, Any]] = []
    timed_out = False
    error_note = ""
    for candidate in candidates:
        if _ledger_compaction_deadline_reached(started_at, float(compaction_timeout)):
            timed_out = True
            skipped["compaction_deadline_reached"] = skipped.get("compaction_deadline_reached", 0) + 1
            break
        try:
            result = _compact_one_ledger(
                operator_root=operator_root,
                ledger_name=str(candidate.get("ledger_name", "")),
                path=Path(candidate.get("path")),
                hot_tail_records=hot_tail_records,
                operation_id=operation_id,
            )
        except (OSError, UnicodeError) as exc:
            error_note = str(exc)
            skipped["compaction_error"] = skipped.get("compaction_error", 0) + 1
            break
        if str(result.get("status", "")) == "compacted":
            compacted.append(result)
            attempt["compacted_ledger_count"] = len(compacted)
            attempt["compacted_record_count"] = sum(
                int(item.get("compacted_record_count", 0) or 0) for item in compacted
            )
            attempt["bytes_reduced"] = sum(int(item.get("bytes_reduced", 0) or 0) for item in compacted)
            attempt["archived_bytes"] = sum(int(item.get("archived_bytes", 0) or 0) for item in compacted)
            attempt["compacted_ledgers"] = [
                {
                    "ledger_name": str(item.get("ledger_name", "")),
                    "segment_id": str(item.get("segment_id", "")),
                    "compacted_record_count": int(item.get("compacted_record_count", 0) or 0),
                    "bytes_reduced": int(item.get("bytes_reduced", 0) or 0),
                }
                for item in compacted
            ]
            _persist_ledger_compaction_attempt(operator_root, attempt, started_at=started_at)
    if _ledger_compaction_deadline_reached(started_at, float(compaction_timeout)):
        timed_out = True
    status_after = memory_pressure_status(operator_root, persist=True)
    no_eligible_ledgers = not candidates and not error_note
    no_progress = not compacted and not error_note and not no_eligible_ledgers
    recent_attempts = _read_ledger(operator_root, "ledger_compaction_attempts", limit=2)
    recent_stalled = [
        row
        for row in recent_attempts
        if str(row.get("status", "")) in {"timeout", "no_progress", "completed_with_warnings"}
        and int(row.get("compacted_record_count", 0) or 0) <= 0
    ]
    restart_after_compaction = (
        str(status_after.get("pressure_band", "")) in {"action", "critical"}
        or (
            str(status_after.get("pressure_band", "")) == "warning"
            and (timed_out or no_progress)
            and len(recent_stalled) >= 1
        )
    )
    progress_class = (
        "failed"
        if error_note
        else "no_eligible_ledgers"
        if no_eligible_ledgers
        else "timeout_with_progress"
        if timed_out and compacted
        else "timeout_before_progress"
        if timed_out and not compacted
        else "timeout_no_progress"
        if timed_out
        else "no_progress"
        if no_progress
        else "completed"
    )
    final_status = (
        "failed"
        if error_note
        else "no_eligible_ledgers"
        if progress_class == "no_eligible_ledgers"
        else "timeout_with_progress"
        if progress_class == "timeout_with_progress"
        else "timeout"
        if progress_class in {"timeout_no_progress", "timeout_before_progress"}
        else "no_progress"
        if no_progress
        else "completed"
    )
    attempt["phase"] = "completed" if final_status == "completed" else "bounded_exit"
    attempt["status"] = final_status
    attempt["skipped_counts"] = skipped
    attempt["archive_segment_count"] = _ledger_compaction_segment_count(operator_root)
    attempt["timeout_reason"] = "ledger compaction deadline reached" if timed_out else ""
    attempt["latest_compaction_progress_class"] = progress_class
    attempt["error_note"] = error_note
    attempt["restart_recommended_after_compaction"] = restart_after_compaction
    attempt["recovery_recommendation"] = (
        "Ledger compaction reduced persisted ledger tails, but process memory may require a Novali service restart to reclaim."
        if restart_after_compaction
        else "Ledger compaction exited within bounds; no restart recommendation from compaction attempt."
    )
    persisted_attempt = _persist_ledger_compaction_attempt(operator_root, attempt, started_at=started_at)
    _append_ledger(operator_root, "ledger_compaction_attempts", persisted_attempt)
    recovery_request: dict[str, Any] = {}
    if str(status_after.get("oom_guard_state", "")) in {"hibernate_required", "recycle_required"}:
        recovery_request = dict(_latest(operator_root, "memory_recovery_requests"))
    elif str(status_after.get("pressure_band", "")) in {"action", "critical"}:
        recovery_request = _write_memory_recovery_request(
            operator_root=operator_root,
            archive_id=str(attempt.get("ledger_compaction_attempt_id", "")),
            operation_id=operation_id,
            status_after_archive=status_after,
        )
    memory_pressure_status(operator_root, persist=True)
    service_recycle = maybe_recycle_service_after_memory_heavy_cycle(
        operator_root=operator_root,
        reason="ledger_compaction_completed_with_high_rss",
        operation_id=operation_id,
    )
    return {
        "exit_code": 0
        if final_status in {"completed", "no_progress", "no_eligible_ledgers", "timeout_with_progress"}
        else 1,
        "ledger_compaction_attempt_id": str(attempt.get("ledger_compaction_attempt_id", "")),
        "status": final_status,
        "latest_compaction_progress_class": progress_class,
        "phase": str(attempt.get("phase", "")),
        "timed_out": timed_out,
        "timeout_reason": str(attempt.get("timeout_reason", "")),
        "error_note": error_note,
        "candidate_ledger_count": len(candidates),
        "compacted_ledger_count": len(compacted),
        "compacted_record_count": int(attempt.get("compacted_record_count", 0) or 0),
        "bytes_reduced": int(attempt.get("bytes_reduced", 0) or 0),
        "archived_bytes": int(attempt.get("archived_bytes", 0) or 0),
        "hot_tail_records": hot_tail_records,
        "archive_segment_count": int(attempt.get("archive_segment_count", 0) or 0),
        "compacted_ledgers": list(attempt.get("compacted_ledgers", []) or []),
        "skipped_counts": skipped,
        "pressure_band_before": status_before.get("pressure_band", ""),
        "pressure_band_after": status_after.get("pressure_band", ""),
        "memory_percent_after": status_after.get("memory_percent", 0),
        "memory_smoothing_state": str(status_after.get("memory_smoothing_state", "normal")),
        "latest_smoothing_action": str(status_after.get("latest_smoothing_action", "")),
        "last_trim_result": str(status_after.get("last_trim_result", "")),
        "cache_eviction_count": int(status_after.get("cache_eviction_count", 0) or 0),
        "disk_spill_bytes": int(status_after.get("disk_spill_bytes", 0) or 0),
        "oom_guard_state": str(status_after.get("oom_guard_state", "normal")),
        "oom_guard_action": str(status_after.get("oom_guard_action", "none")),
        "service_recycle_recommended": bool(
            status_after.get("service_recycle_recommended", False)
        ),
        "hibernate_recommended": bool(status_after.get("hibernate_recommended", False)),
        "last_recycle_request_id": str(status_after.get("last_recycle_request_id", "")),
        "restart_recommended_after_compaction": restart_after_compaction,
        "recovery_request": recovery_request,
        "service_recycle": service_recycle,
    }


def _memory_archive_source_roots(
    *,
    operator_root: str | Path,
    state_root: str | Path,
    package_root: str | Path,
) -> list[tuple[str, Path]]:
    package = Path(package_root)
    roots: list[tuple[str, Path]] = [
        ("operator_state", Path(operator_root)),
        ("runtime_data_logs", Path(state_root).parent / "logs"),
        ("active_workspace", package / "novali-active_workspace"),
    ]
    seen: set[Path] = set()
    unique: list[tuple[str, Path]] = []
    for label, root in roots:
        try:
            resolved = root.resolve()
        except OSError:
            resolved = root
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append((label, root))
    return unique


def _looks_secret_like_file(path: Path) -> bool:
    try:
        size = path.stat().st_size
    except OSError:
        return True
    sample_size = min(size, 2 * 1024 * 1024)
    try:
        with path.open("rb") as handle:
            text = handle.read(sample_size).decode("utf-8", errors="ignore")
    except OSError:
        return True
    return bool(SECRET_LIKE_PATTERN.search(text) or "FAKE_OPENAI_API_KEY" in text or "SHOULD_NOT_EXPORT" in text)


def _memory_archive_skip_reason(path: Path, *, source_root: Path, archive_root: Path, now_seconds: float) -> str:
    name_text = path.name.lower()
    path_text = str(path).lower()
    try:
        resolved = path.resolve()
    except OSError:
        return "unreadable"
    try:
        resolved.relative_to(archive_root.resolve())
        return "archive_output_tree"
    except ValueError:
        pass
    if not path.is_file():
        return "not_file"
    if path.suffix.lower() not in MEMORY_ARCHIVE_CANDIDATE_SUFFIXES:
        return "unsupported_suffix"
    if any(fragment in name_text or fragment in path_text for fragment in MEMORY_ARCHIVE_SKIP_NAME_FRAGMENTS):
        return "active_or_sensitive_name"
    try:
        stat = path.stat()
    except OSError:
        return "unreadable"
    if stat.st_size <= 0:
        return "empty"
    min_age_seconds = _safe_int_env(
        "NOVALI_MEMORY_ARCHIVE_MIN_AGE_SECONDS",
        MEMORY_ARCHIVE_DEFAULT_MIN_AGE_SECONDS,
        minimum=0,
    )
    if (now_seconds - stat.st_mtime) < min_age_seconds:
        return "not_cold"
    if _looks_secret_like_file(path):
        return "secret_like_content"
    try:
        resolved.relative_to(source_root.resolve())
    except ValueError:
        return "outside_source_root"
    return ""


def _memory_archive_deadline_reached(started_at: float, timeout_seconds: float) -> bool:
    return timeout_seconds > 0 and (time.perf_counter() - started_at) >= timeout_seconds


def _should_prune_memory_archive_dir(path: Path, *, archive_root: Path) -> bool:
    name_text = path.name.lower()
    path_text = str(path).lower()
    if name_text in MEMORY_ARCHIVE_PRUNE_DIR_NAMES:
        return True
    if "latest_candidate" in path_text:
        return True
    try:
        path.resolve().relative_to(archive_root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _iter_memory_archive_candidates(
    *,
    operator_root: str | Path,
    state_root: str | Path,
    package_root: str | Path,
    archive_root: Path,
    started_at: float,
    timeout_seconds: float,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    skipped: dict[str, int] = {}
    now_seconds = time.time()
    max_files = _safe_int_env("NOVALI_MEMORY_ARCHIVE_MAX_FILES", MEMORY_ARCHIVE_DEFAULT_MAX_FILES, minimum=1)
    max_bytes = _safe_int_env("NOVALI_MEMORY_ARCHIVE_MAX_BYTES", MEMORY_ARCHIVE_DEFAULT_MAX_BYTES, minimum=1)
    max_scan_entries = _safe_int_env(
        "NOVALI_MEMORY_ARCHIVE_MAX_SCAN_ENTRIES",
        MEMORY_ARCHIVE_DEFAULT_MAX_SCAN_ENTRIES,
        minimum=1,
    )
    total_bytes = 0
    scanned_entries = 0
    scanned_dirs = 0
    timed_out = False
    for label, source_root in _memory_archive_source_roots(
        operator_root=operator_root,
        state_root=state_root,
        package_root=package_root,
    ):
        if _memory_archive_deadline_reached(started_at, timeout_seconds):
            timed_out = True
            skipped["archive_deadline_reached"] = skipped.get("archive_deadline_reached", 0) + 1
            break
        if not source_root.exists():
            skipped["missing_source_root"] = skipped.get("missing_source_root", 0) + 1
            continue
        for dirpath, dirnames, filenames in os.walk(source_root):
            current_dir = Path(dirpath)
            scanned_dirs += 1
            dirnames[:] = [
                dirname
                for dirname in sorted(dirnames)
                if not _should_prune_memory_archive_dir(current_dir / dirname, archive_root=archive_root)
            ]
            for filename in sorted(filenames):
                scanned_entries += 1
                if scanned_entries >= max_scan_entries:
                    skipped["scan_limit_reached"] = skipped.get("scan_limit_reached", 0) + 1
                    return candidates, skipped, {
                        "scanned_entries": scanned_entries,
                        "scanned_dirs": scanned_dirs,
                        "timed_out": False,
                        "scan_limit_reached": True,
                        "max_scan_entries": max_scan_entries,
                    }
                if _memory_archive_deadline_reached(started_at, timeout_seconds):
                    timed_out = True
                    skipped["archive_deadline_reached"] = skipped.get("archive_deadline_reached", 0) + 1
                    return candidates, skipped, {
                        "scanned_entries": scanned_entries,
                        "scanned_dirs": scanned_dirs,
                        "timed_out": True,
                        "scan_limit_reached": False,
                        "max_scan_entries": max_scan_entries,
                    }
                path = current_dir / filename
                reason = _memory_archive_skip_reason(
                    path,
                    source_root=source_root,
                    archive_root=archive_root,
                    now_seconds=now_seconds,
                )
                if reason:
                    skipped[reason] = skipped.get(reason, 0) + 1
                    continue
                size = path.stat().st_size
                if len(candidates) >= max_files or total_bytes + size > max_bytes:
                    skipped["archive_limit_reached"] = skipped.get("archive_limit_reached", 0) + 1
                    continue
                if _memory_archive_deadline_reached(started_at, timeout_seconds):
                    timed_out = True
                    skipped["archive_deadline_reached"] = skipped.get("archive_deadline_reached", 0) + 1
                    return candidates, skipped, {
                        "scanned_entries": scanned_entries,
                        "scanned_dirs": scanned_dirs,
                        "timed_out": True,
                        "scan_limit_reached": False,
                        "max_scan_entries": max_scan_entries,
                    }
                total_bytes += size
                relative_path = _safe_relative_path(source_root, path)
                candidates.append(
                    {
                        "source_label": label,
                        "source_root": str(source_root),
                        "source_path": str(path),
                        "relative_path": relative_path,
                        "size_bytes": size,
                        "sha256": _hash_file(path),
                    }
                )
    return candidates, skipped, {
        "scanned_entries": scanned_entries,
        "scanned_dirs": scanned_dirs,
        "timed_out": timed_out,
        "scan_limit_reached": False,
        "max_scan_entries": max_scan_entries,
    }


def _write_memory_recovery_request(
    *,
    operator_root: str | Path,
    archive_id: str,
    operation_id: str,
    status_after_archive: Mapping[str, Any],
) -> dict[str, Any]:
    band = str(status_after_archive.get("pressure_band", "normal"))
    recovery_state = (
        "restart_required_external_operator"
        if band in {"action", "critical"}
        else "restored"
    )
    request = {
        "schema_name": MEMORY_RECOVERY_REQUEST_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "memory_recovery_request_id": "",
        "operation_id": operation_id,
        "memory_archive_id": archive_id,
        "pressure_band_after_archive": band,
        "memory_percent_after_archive": status_after_archive.get("memory_percent", 0),
        "recovery_state": recovery_state,
        "restart_recommendation": (
            "Restart the novali service through an approved external operator path; direct in-container restart is unavailable in v1."
            if recovery_state == "restart_required_external_operator"
            else "No restart required after archive."
        ),
        "restart_adapter_available": False,
        "restart_target": "novali",
        "authority_boundary": "Archive/restart recovery remains broker-gated and emergency-stop controlled.",
    }
    request["memory_recovery_request_id"] = _record_id("memory-recovery", request)
    record = _append_ledger(operator_root, "memory_recovery_requests", request)
    _write_json(_memory_pressure_root(operator_root) / "recovery_latest.json", record)
    return record


def _write_memory_recovery_restored_request(
    *,
    operator_root: str | Path,
    prior_recovery: Mapping[str, Any],
    status_after_recovery: Mapping[str, Any],
) -> dict[str, Any]:
    request = {
        "schema_name": MEMORY_RECOVERY_REQUEST_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "memory_recovery_request_id": "",
        "operation_id": str(prior_recovery.get("operation_id", "")),
        "memory_archive_id": str(
            prior_recovery.get("memory_archive_id", "")
            or prior_recovery.get("archive_id", "")
        ),
        "previous_memory_recovery_request_id": str(
            prior_recovery.get("memory_recovery_request_id", "")
        ),
        "pressure_band_after_archive": str(status_after_recovery.get("pressure_band", "normal")),
        "memory_percent_after_archive": status_after_recovery.get("memory_percent", 0),
        "measurement_source": str(status_after_recovery.get("measurement_source", "")),
        "recovery_state": "restored_after_restart",
        "restart_recommendation": (
            "Fresh memory measurement is below the warning threshold; previous restart-required "
            "memory pressure has been cleared."
        ),
        "restart_adapter_available": False,
        "restart_target": "novali",
        "authority_boundary": "Memory recovery status refresh does not bypass governed review, broker, or emergency-stop controls.",
    }
    request["memory_recovery_request_id"] = _record_id("memory-recovery", request)
    record = _append_ledger(operator_root, "memory_recovery_requests", request)
    _write_json(_memory_pressure_root(operator_root) / "recovery_latest.json", record)
    return record


def _write_memory_guard_recovery_request(
    *,
    operator_root: str | Path,
    recovery_state: str,
    oom_guard: Mapping[str, Any],
    status_after_measurement: Mapping[str, Any],
    operation_id: str = "",
) -> dict[str, Any]:
    state = str(recovery_state or "").strip()
    action = str(oom_guard.get("oom_guard_action", "") or "")
    request = {
        "schema_name": MEMORY_RECOVERY_REQUEST_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "memory_recovery_request_id": "",
        "operation_id": operation_id,
        "memory_archive_id": "",
        "pressure_band_after_archive": str(status_after_measurement.get("pressure_band", "normal")),
        "memory_percent_after_archive": status_after_measurement.get("memory_percent", 0),
        "measurement_source": str(status_after_measurement.get("measurement_source", "")),
        "recovery_state": state,
        "oom_guard_state": str(oom_guard.get("oom_guard_state", "")),
        "oom_guard_action": action,
        "oom_guard_reason": str(oom_guard.get("oom_guard_reason", "")),
        "service_recycle_recommended": state == "service_recycle_requested",
        "hibernate_recommended": state in {
            "hibernated_for_memory_pressure",
            "service_recycle_requested",
        },
        "restart_recommendation": (
            "Pause governed launches and let Docker Compose recycle the novali service after persisted state is flushed."
            if state == "service_recycle_requested"
            else "Pause governed launches until a fresh memory measurement returns to a safe band."
        ),
        "restart_adapter_available": state == "service_recycle_requested",
        "restart_target": "novali",
        "authority_boundary": "Memory pressure hibernation/recycle preserves checkpoint resume semantics and does not enable stale recovery.",
    }
    request["memory_recovery_request_id"] = _record_id("memory-recovery", request)
    record = _append_ledger(operator_root, "memory_recovery_requests", request)
    _write_json(_memory_pressure_root(operator_root) / "recovery_latest.json", record)
    if state == "service_recycle_requested":
        try:
            record_service_recycle_requested(
                {
                    **record,
                    "pressure_band": request["pressure_band_after_archive"],
                    "recycle_reason": request["oom_guard_reason"],
                    "lifecycle_state": "paused_for_memory_pressure",
                    "last_recycle_request_id": request["memory_recovery_request_id"],
                }
            )
        except Exception:
            pass
    return record


def maybe_recycle_service_after_memory_heavy_cycle(
    *,
    operator_root: str | Path,
    reason: str,
    operation_id: str = "",
    lifecycle_state: str = "paused_for_memory_pressure",
) -> dict[str, Any]:
    status = memory_pressure_status(operator_root, persist=True)
    if not bool(status.get("service_recycle_recommended", False)):
        return {
            "service_recycle_requested": False,
            "oom_guard_state": str(status.get("oom_guard_state", "normal")),
            "memory_percent": status.get("memory_percent", 0),
        }
    latest_recovery = _latest(operator_root, "memory_recovery_requests")
    payload = {
        **status,
        "operation_id": operation_id,
        "result": "requested",
        "recycle_reason": reason,
        "lifecycle_state": lifecycle_state,
        "last_recycle_request_id": str(
            latest_recovery.get("memory_recovery_request_id", "")
            or status.get("last_recycle_request_id", "")
        ),
    }
    try:
        record_service_recycle_requested(payload)
    except Exception:
        pass
    default_exit = not bool(os.environ.get("NOVALI_MEMORY_PRESSURE_TEST_USED_BYTES", "").strip())
    if _env_bool("NOVALI_OOM_GUARD_EXIT_ON_RECYCLE", default_exit):
        try:
            time.sleep(0.05)
        finally:
            os._exit(NOVALI_SERVICE_RECYCLE_EXIT_CODE)
    return {
        "service_recycle_requested": True,
        "oom_guard_state": str(status.get("oom_guard_state", "recycle_required")),
        "memory_percent": status.get("memory_percent", 0),
        "last_recycle_request_id": str(payload.get("last_recycle_request_id", "")),
        "recycle_exit_code": NOVALI_SERVICE_RECYCLE_EXIT_CODE,
    }


def _memory_pressure_archive(
    *,
    operator_root: str | Path,
    state_root: str | Path,
    package_root: str | Path,
    operation: Mapping[str, Any],
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    operation_timeout = int(timeout_seconds or MEMORY_ARCHIVE_DEFAULT_TIMEOUT_SECONDS)
    archive_timeout = min(
        operation_timeout,
        _safe_int_env(
            "NOVALI_MEMORY_ARCHIVE_TIMEOUT_SECONDS",
            MEMORY_ARCHIVE_DEFAULT_TIMEOUT_SECONDS,
            minimum=1,
        ),
    )
    status_before = memory_pressure_status(operator_root, persist=True)
    archive_seed = {
        "operation_id": str(operation.get("operation_id", "")),
        "created_at": _now(),
        "pressure_band": status_before.get("pressure_band", ""),
    }
    archive_id = _record_id("memory-archive", archive_seed)
    archive_root = Path(operator_root) / "memory_archive" / archive_id
    moved_root = archive_root / "moved_files"
    manifest_path = archive_root / "manifest.json"
    bundle_path = archive_root / "evidence_bundle.tar.gz"
    source_roots = [
        {"label": label, "path": str(root)}
        for label, root in _memory_archive_source_roots(
            operator_root=operator_root,
            state_root=state_root,
            package_root=package_root,
        )
    ]
    attempt = {
        "schema_name": MEMORY_ARCHIVE_ATTEMPT_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "updated_at": "",
        "memory_archive_attempt_id": "",
        "memory_archive_id": archive_id,
        "operation_id": str(operation.get("operation_id", "")),
        "phase": "initialized",
        "status": "running",
        "archive_root": str(archive_root),
        "manifest_path": str(manifest_path),
        "archive_bundle_path": str(bundle_path),
        "source_roots": source_roots,
        "timeout_seconds": archive_timeout,
        "elapsed_ms": 0.0,
        "candidate_count": 0,
        "archived_count": 0,
        "recovered_bytes": 0,
        "skipped_counts": {},
        "scan_stats": {},
        "timeout_reason": "",
        "error_note": "",
        "restart_recommended_after_archive_stall": False,
        "recovery_recommendation": "Archive attempt started; no recovery decision recorded yet.",
    }
    attempt["memory_archive_attempt_id"] = _record_id("memory-archive-attempt", attempt)
    _persist_memory_archive_attempt(operator_root, attempt, started_at=started_at)
    if str(status_before.get("pressure_band", "")) in {"warning", "action", "critical"}:
        attempt["phase"] = "ledger_compaction_first"
        _persist_memory_archive_attempt(operator_root, attempt, started_at=started_at)
        compaction_result = _memory_ledger_compaction(
            operator_root=operator_root,
            operation=operation,
            timeout_seconds=archive_timeout,
        )
        status_after_compaction = memory_pressure_status(operator_root, persist=True)
        compacted_records = int(compaction_result.get("compacted_record_count", 0) or 0)
        compaction_status = str(compaction_result.get("status", ""))
        wrapper_status = (
            "completed"
            if compaction_status == "completed"
            else "completed_with_progress"
            if compaction_status == "timeout_with_progress"
            else "completed_with_warnings"
        )
        restart_after_compaction = bool(
            compaction_result.get("restart_recommended_after_compaction", False)
        )
        archive_root.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_name": MEMORY_ARCHIVE_MANIFEST_SCHEMA_NAME,
            "schema_version": AUTONOMY_SCHEMA_VERSION,
            "created_at": _now(),
            "memory_archive_id": archive_id,
            "operation_id": str(operation.get("operation_id", "")),
            "memory_archive_attempt_id": str(attempt.get("memory_archive_attempt_id", "")),
            "status": wrapper_status,
            "archive_mode": "ledger_compaction_first",
            "archive_root": str(archive_root),
            "archive_bundle_path": "",
            "source_roots": source_roots,
            "candidate_count": 0,
            "archived_count": 0,
            "skipped_counts": {},
            "scan_stats": {
                "recursive_archive_scan_skipped": True,
                "reason": "memory pressure uses ledger-aware compaction before broad artifact archive",
            },
            "archived_files": [],
            "total_archived_bytes": 0,
            "recovered_bytes": 0,
            "redaction_status": "manifest_contains_path_hints_hashes_and_sizes_only",
            "secret_handling": "ledger compaction manifests never store record payloads or credential values",
            "timeout_seconds": archive_timeout,
            "timed_out": bool(compaction_result.get("timed_out", False)),
            "timeout_reason": str(compaction_result.get("timeout_reason", "")),
            "error_note": str(compaction_result.get("error_note", "")),
            "archive_reclaims_process_memory": False,
            "ledger_compaction_attempt_id": str(compaction_result.get("ledger_compaction_attempt_id", "")),
            "ledger_compaction_status": compaction_status,
            "ledger_compaction_compacted_ledger_count": int(
                compaction_result.get("compacted_ledger_count", 0) or 0
            ),
            "ledger_compaction_compacted_record_count": compacted_records,
            "ledger_compaction_compacted_bytes": int(compaction_result.get("bytes_reduced", 0) or 0),
            "ledger_compaction_hot_tail_records": int(
                compaction_result.get("hot_tail_records", LEDGER_COMPACTION_DEFAULT_HOT_TAIL_RECORDS)
                or LEDGER_COMPACTION_DEFAULT_HOT_TAIL_RECORDS
            ),
            "ledger_compaction_archive_segment_count": int(
                compaction_result.get("archive_segment_count", 0) or 0
            ),
            "restart_recommended_after_compaction": restart_after_compaction,
            "restart_recommended_after_archive_stall": restart_after_compaction,
            "status_before_archive": status_before,
            "status_after_archive": status_after_compaction,
        }
        record = _append_ledger(operator_root, "memory_archive_manifests", manifest)
        _write_json(manifest_path, record)
        _write_json(_memory_pressure_root(operator_root) / "archive_latest.json", record)
        attempt["phase"] = (
            "completed"
            if wrapper_status in {"completed", "completed_with_progress"}
            else "bounded_exit"
        )
        attempt["status"] = wrapper_status
        attempt["candidate_count"] = 0
        attempt["archived_count"] = 0
        attempt["recovered_bytes"] = 0
        attempt["scan_stats"] = dict(manifest["scan_stats"])
        attempt["ledger_compaction_attempt_id"] = str(compaction_result.get("ledger_compaction_attempt_id", ""))
        attempt["ledger_compaction_status"] = compaction_status
        attempt["ledger_compaction_compacted_ledger_count"] = int(
            compaction_result.get("compacted_ledger_count", 0) or 0
        )
        attempt["ledger_compaction_compacted_record_count"] = compacted_records
        attempt["ledger_compaction_compacted_bytes"] = int(compaction_result.get("bytes_reduced", 0) or 0)
        attempt["timeout_reason"] = str(compaction_result.get("timeout_reason", ""))
        attempt["error_note"] = str(compaction_result.get("error_note", ""))
        attempt["restart_recommended_after_archive_stall"] = restart_after_compaction
        attempt["recovery_recommendation"] = (
            "Ledger compaction completed or exited within bounds; restart may still be needed to reclaim process RSS."
        )
        _persist_memory_archive_attempt(operator_root, attempt, started_at=started_at)
        memory_pressure_status(operator_root, persist=True)
        service_recycle = maybe_recycle_service_after_memory_heavy_cycle(
            operator_root=operator_root,
            reason="memory_archive_ledger_compaction_completed_with_high_rss",
            operation_id=str(operation.get("operation_id", "")),
        )
        return {
            "exit_code": 0
            if wrapper_status in {"completed", "completed_with_progress"}
            else 1,
            "memory_archive_id": archive_id,
            "memory_archive_attempt_id": str(attempt.get("memory_archive_attempt_id", "")),
            "manifest_path": str(manifest_path),
            "archive_bundle_path": "",
            "archive_mode": "ledger_compaction_first",
            "archived_count": 0,
            "recovered_bytes": 0,
            "pressure_band_before": status_before.get("pressure_band", ""),
            "pressure_band_after": status_after_compaction.get("pressure_band", ""),
            "memory_percent_after": status_after_compaction.get("memory_percent", 0),
            "oom_guard_state": str(status_after_compaction.get("oom_guard_state", "normal")),
            "oom_guard_action": str(status_after_compaction.get("oom_guard_action", "none")),
            "service_recycle_recommended": bool(
                status_after_compaction.get("service_recycle_recommended", False)
            ),
            "hibernate_recommended": bool(
                status_after_compaction.get("hibernate_recommended", False)
            ),
            "last_recycle_request_id": str(
                status_after_compaction.get("last_recycle_request_id", "")
            ),
            "status": wrapper_status,
            "timed_out": bool(compaction_result.get("timed_out", False)),
            "timeout_reason": str(compaction_result.get("timeout_reason", "")),
            "ledger_compaction": compaction_result,
            "ledger_compaction_attempt_id": str(compaction_result.get("ledger_compaction_attempt_id", "")),
            "ledger_compaction_status": compaction_status,
            "ledger_compaction_compacted_record_count": compacted_records,
            "ledger_compaction_compacted_bytes": int(compaction_result.get("bytes_reduced", 0) or 0),
            "restart_recommended_after_archive_stall": restart_after_compaction,
            "restart_recommended_after_compaction": restart_after_compaction,
            "recovery_request": dict(compaction_result.get("recovery_request", {}) or {}),
            "service_recycle": service_recycle,
        }
    archive_root.mkdir(parents=True, exist_ok=True)
    attempt["phase"] = "candidate_discovery"
    _persist_memory_archive_attempt(operator_root, attempt, started_at=started_at)
    candidates, skipped, scan_stats = _iter_memory_archive_candidates(
        operator_root=operator_root,
        state_root=state_root,
        package_root=package_root,
        archive_root=Path(operator_root) / "memory_archive",
        started_at=started_at,
        timeout_seconds=float(archive_timeout),
    )
    attempt["candidate_count"] = len(candidates)
    attempt["skipped_counts"] = skipped
    attempt["scan_stats"] = scan_stats
    attempt["phase"] = "bundle_write"
    _persist_memory_archive_attempt(operator_root, attempt, started_at=started_at)
    archived_files: list[dict[str, Any]] = []
    recovered_bytes = 0
    timed_out = bool(scan_stats.get("timed_out", False))
    error_note = ""
    try:
        with tarfile.open(bundle_path, "w:gz") as tar:
            for item in candidates:
                if _memory_archive_deadline_reached(started_at, float(archive_timeout)):
                    timed_out = True
                    skipped["archive_deadline_reached"] = skipped.get("archive_deadline_reached", 0) + 1
                    break
                source = Path(str(item["source_path"]))
                if not source.exists() or not source.is_file():
                    skipped["source_missing_before_archive"] = skipped.get("source_missing_before_archive", 0) + 1
                    continue
                arcname = f'{item["source_label"]}/{item["relative_path"]}'
                tar.add(source, arcname=arcname, recursive=False)
                if _memory_archive_deadline_reached(started_at, float(archive_timeout)):
                    timed_out = True
                    skipped["archive_deadline_reached"] = skipped.get("archive_deadline_reached", 0) + 1
                    break
                target = moved_root / str(item["source_label"]) / str(item["relative_path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
                recovered_bytes += int(item.get("size_bytes", 0) or 0)
                archived_files.append(
                    {
                        "source_label": str(item.get("source_label", "")),
                        "source_path_hint": str(item.get("source_path", "")),
                        "relative_path": str(item.get("relative_path", "")),
                        "size_bytes": int(item.get("size_bytes", 0) or 0),
                        "sha256": str(item.get("sha256", "")),
                        "archive_member": arcname,
                        "moved_to": str(target),
                        "retention_decision": "moved_to_archive",
                    }
                )
                attempt["archived_count"] = len(archived_files)
                attempt["recovered_bytes"] = recovered_bytes
    except OSError as exc:
        error_note = str(exc)
    status_after = memory_pressure_status(operator_root, persist=True)
    scan_limited = bool(scan_stats.get("scan_limit_reached", False))
    manifest_status = (
        "failed"
        if error_note
        else "timeout"
        if timed_out
        else "completed_with_warnings"
        if scan_limited
        else "completed"
    )
    restart_after_stall = (
        str(status_after.get("pressure_band", "")) in {"warning", "action", "critical"}
        and (timed_out or recovered_bytes <= 0)
    )
    manifest = {
        "schema_name": MEMORY_ARCHIVE_MANIFEST_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "memory_archive_id": archive_id,
        "operation_id": str(operation.get("operation_id", "")),
        "memory_archive_attempt_id": str(attempt.get("memory_archive_attempt_id", "")),
        "status": manifest_status,
        "archive_root": str(archive_root),
        "archive_bundle_path": str(bundle_path),
        "source_roots": source_roots,
        "candidate_count": len(candidates),
        "archived_count": len(archived_files),
        "skipped_counts": skipped,
        "scan_stats": scan_stats,
        "archived_files": archived_files,
        "total_archived_bytes": recovered_bytes,
        "recovered_bytes": recovered_bytes,
        "redaction_status": "manifest_contains_path_hints_hashes_and_sizes_only",
        "secret_handling": "credential-like names and secret-like contents are skipped",
        "timeout_seconds": archive_timeout,
        "timed_out": timed_out,
        "timeout_reason": "memory archive deadline reached" if timed_out else "",
        "error_note": error_note,
        "scan_limit_reached": scan_limited,
        "archive_reclaims_process_memory": False,
        "restart_recommended_after_archive_stall": restart_after_stall,
        "status_before_archive": status_before,
        "status_after_archive": status_after,
    }
    record = _append_ledger(operator_root, "memory_archive_manifests", manifest)
    _write_json(manifest_path, record)
    _write_json(_memory_pressure_root(operator_root) / "archive_latest.json", record)
    attempt["phase"] = "completed" if manifest_status == "completed" else "bounded_exit"
    attempt["status"] = "completed" if manifest_status == "completed" else "completed_with_warnings"
    if timed_out:
        attempt["status"] = "timeout"
        attempt["timeout_reason"] = "memory archive deadline reached"
    if error_note:
        attempt["status"] = "failed"
        attempt["error_note"] = error_note
    if scan_limited and not timed_out and not error_note:
        attempt["error_note"] = "memory archive scan limit reached"
    attempt["candidate_count"] = len(candidates)
    attempt["archived_count"] = len(archived_files)
    attempt["recovered_bytes"] = recovered_bytes
    attempt["skipped_counts"] = skipped
    attempt["scan_stats"] = scan_stats
    attempt["restart_recommended_after_archive_stall"] = restart_after_stall
    attempt["recovery_recommendation"] = (
        "Archive completed, but process memory may require a Novali service restart to reclaim."
        if restart_after_stall
        else "Archive completed or exited within bounds; no restart recommendation from archive attempt."
    )
    _persist_memory_archive_attempt(operator_root, attempt, started_at=started_at)
    recovery_request: dict[str, Any] = {}
    if str(status_after.get("oom_guard_state", "")) in {"hibernate_required", "recycle_required"}:
        recovery_request = dict(_latest(operator_root, "memory_recovery_requests"))
    elif str(status_after.get("pressure_band", "")) in {"action", "critical"}:
        recovery_request = _write_memory_recovery_request(
            operator_root=operator_root,
            archive_id=archive_id,
            operation_id=str(operation.get("operation_id", "")),
            status_after_archive=status_after,
        )
    memory_pressure_status(operator_root, persist=True)
    service_recycle = maybe_recycle_service_after_memory_heavy_cycle(
        operator_root=operator_root,
        reason="memory_archive_completed_with_high_rss",
        operation_id=str(operation.get("operation_id", "")),
    )
    return {
        "exit_code": 0 if manifest_status == "completed" else 1,
        "memory_archive_id": archive_id,
        "memory_archive_attempt_id": str(attempt.get("memory_archive_attempt_id", "")),
        "manifest_path": str(manifest_path),
        "archive_bundle_path": str(bundle_path),
        "archived_count": len(archived_files),
        "recovered_bytes": recovered_bytes,
        "pressure_band_before": status_before.get("pressure_band", ""),
        "pressure_band_after": status_after.get("pressure_band", ""),
        "memory_percent_after": status_after.get("memory_percent", 0),
        "oom_guard_state": str(status_after.get("oom_guard_state", "normal")),
        "oom_guard_action": str(status_after.get("oom_guard_action", "none")),
        "service_recycle_recommended": bool(
            status_after.get("service_recycle_recommended", False)
        ),
        "hibernate_recommended": bool(status_after.get("hibernate_recommended", False)),
        "last_recycle_request_id": str(status_after.get("last_recycle_request_id", "")),
        "status": manifest_status,
        "timed_out": timed_out,
        "timeout_reason": "memory archive deadline reached" if timed_out else "",
        "restart_recommended_after_archive_stall": restart_after_stall,
        "recovery_request": recovery_request,
        "service_recycle": service_recycle,
    }


def _latest_current_directive_text(observations: Mapping[str, Any]) -> str:
    directive = dict(observations.get("current_directive", {}) or {})
    chunks = [
        directive.get("directive_id", ""),
        directive.get("directive_path", ""),
        directive.get("path", ""),
        directive.get("title", ""),
        directive.get("summary", ""),
        directive.get("clarified_intent_summary", ""),
    ]
    for path_key in ("directive_path", "path"):
        path_text = str(directive.get(path_key, "") or "").strip()
        if not path_text:
            continue
        try:
            path = Path(path_text)
            if path.exists() and path.is_file():
                payload = _read_json(path)
                chunks.extend(
                    [
                        payload.get("title", ""),
                        payload.get("objective", ""),
                        payload.get("directive_text", ""),
                        payload.get("clarified_intent_summary", ""),
                    ]
                )
        except OSError:
            pass
    return _truncate(" ".join(str(item) for item in chunks if str(item).strip()), 3000)


def _infer_mission_domain(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ("space", "orbital", "asteroid", "lunar", "resource extraction", "isru")):
        return "space_resource_extraction_and_expansion"
    if any(term in lowered for term in ("monitoring", "observability", "logicmonitor", "alert")):
        return "enterprise_monitoring_operations"
    if lowered.strip():
        return "directive_defined_specialization"
    return "unassigned"


def _domain_skill_defaults(domain: str) -> tuple[list[str], list[str], list[str]]:
    if domain == "space_resource_extraction_and_expansion":
        return (
            ["research synthesis", "prototype planning", "systems decomposition"],
            [
                "trusted-source literature synthesis",
                "prototype build/test instruction generation",
                "technology tradeoff scoring",
            ],
            ["domain citations", "prototype constraints", "validation criteria"],
        )
    if domain == "enterprise_monitoring_operations":
        return (
            ["state observation", "runbook drafting", "health evidence capture"],
            ["adapter diagnostics", "incident pattern replay"],
            ["current platform constraints"],
        )
    return (
        ["state observation", "evidence synthesis"],
        ["role-specific research adapter", "directive-specific success metric"],
        ["directive domain context"],
    )


def _role_specialization_profile(
    *,
    operator_root: str | Path,
    observations: Mapping[str, Any],
    persist: bool = True,
) -> dict[str, Any]:
    directive_text = _latest_current_directive_text(observations)
    domain = _infer_mission_domain(directive_text)
    useful_defaults, missing_defaults, knowledge_defaults = _domain_skill_defaults(domain)
    latest_meaningful = _latest(operator_root, "meaningful_work_evaluations")
    latest_synthesis = _latest(operator_root, "post_ladder_syntheses")
    latest_usefulness = _latest(operator_root, "capability_usefulness_evaluations")
    weak_areas = [
        str(item)
        for item in list(latest_meaningful.get("weak_areas", []) or [])
        if str(item).strip()
    ]
    recurring_blockers = list(dict.fromkeys(weak_areas[:5]))
    trusted_source_ready = bool(latest_synthesis.get("trusted_source_ready", False))
    missing_skills = list(missing_defaults)
    if "repeated signal signature; likely artifact churn" in weak_areas:
        missing_skills.append("artifact churn resistance")
    if latest_usefulness and str(latest_usefulness.get("usefulness", "")) in {"evidence_only", "dormant", "needs_followup"}:
        missing_skills.append("capability usefulness reinforcement")
    profile = {
        "schema_name": ROLE_SPECIALIZATION_PROFILE_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "role_profile_id": "",
        "assigned_role": (
            "self-specializing autonomous directive worker"
            if domain != "unassigned"
            else "unassigned autonomy worker"
        ),
        "inferred_mission_domain": domain,
        "current_specialization_thesis": (
            f"Novali should grow capabilities that make it more effective for {domain} "
            "while preserving governed execution, evidence, rollback, and emergency-stop boundaries."
        ),
        "useful_skills": list(dict.fromkeys(useful_defaults)),
        "missing_skills": list(dict.fromkeys(missing_skills)),
        "trusted_knowledge_gaps": list(dict.fromkeys(knowledge_defaults)),
        "recurring_blockers": recurring_blockers,
        "preferred_adapters": [
            "local_repo_state",
            "operator_state_artifacts",
            TRUSTED_SOURCE_EXTERNAL_PROVIDER_ID if trusted_source_ready else "trusted_source_ready_probe",
        ],
        "next_learning_pressure": (
            missing_skills[0]
            if missing_skills
            else "measure later usefulness of promoted capabilities"
        ),
        "authority_boundary": "Role profile is guidance evidence only; it does not mutate the charter or authorize execution.",
    }
    profile["role_profile_id"] = _record_id("role-profile", profile)
    if not persist:
        return _redact_autonomy_value(profile)
    record = _append_ledger(operator_root, "role_specialization_profiles", profile)
    _write_json(autonomy_root(operator_root) / "role_specialization_profile_latest.json", record)
    return record


def _record_created_at(record: Mapping[str, Any]) -> datetime | None:
    text = str(record.get("created_at", "") or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _after_created_at(record: Mapping[str, Any], cutoff: datetime | None) -> bool:
    if cutoff is None:
        return True
    created = _record_created_at(record)
    return created is not None and created > cutoff


def _payload_contains_capability(value: Any, capability_kind: str) -> bool:
    if not capability_kind:
        return False
    if isinstance(value, Mapping):
        return any(_payload_contains_capability(item, capability_kind) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_payload_contains_capability(item, capability_kind) for item in value)
    return str(value or "").strip() == capability_kind


def _first_present_payload(record: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in record:
            return record.get(key)
    result = dict(record.get("result", {}) or {})
    for key in keys:
        if key in result:
            return result.get(key)
    return None


def _truthy_marker(record: Mapping[str, Any], keys: tuple[str, ...]) -> bool:
    value = _first_present_payload(record, keys)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    return str(value or "").strip().lower() in {"true", "yes", "positive", "reduced", "improved", "prevented"}


def _capability_explicitly_referenced(record: Mapping[str, Any], capability_kind: str) -> bool:
    explicit_keys = (
        "consumed_capability_kind",
        "consumed_capability_kinds",
        "explicitly_consumed_capability_kind",
        "explicitly_consumed_capability_kinds",
        "used_capability_kind",
        "used_capability_kinds",
        "referenced_capability_kind",
        "referenced_capability_kinds",
    )
    if _payload_contains_capability(_first_present_payload(record, explicit_keys), capability_kind):
        return True
    return False


def _capability_associated(record: Mapping[str, Any], capability_kind: str) -> bool:
    return (
        str(record.get("capability_kind", "") or "") == capability_kind
        or str(record.get("capability_gap_id", "") or "") == capability_kind
        or _capability_explicitly_referenced(record, capability_kind)
    )


def _strict_usefulness_signals(
    *,
    capability_kind: str,
    promotion_cutoff: datetime | None,
    operation_rows: list[dict[str, Any]],
    meaningful_rows: list[dict[str, Any]],
    consumption_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    strong_signals: list[dict[str, str]] = []
    counts = {
        "explicit_consumption_count": 0,
        "decision_change_count": 0,
        "failure_prevention_count": 0,
        "directive_progress_improvement_count": 0,
        "operator_intervention_reduction_count": 0,
        "runtime_hook_reference_count": 0,
    }

    def add_signal(kind: str, row: Mapping[str, Any], source: str) -> None:
        counts[f"{kind}_count"] += 1
        strong_signals.append(
            {
                "signal_type": kind,
                "source": source,
                "record_id": str(
                    row.get("operation_result_id")
                    or row.get("meaningful_work_id")
                    or row.get("capability_consumption_event_id")
                    or row.get("cycle_id")
                    or ""
                ),
                "created_at": str(row.get("created_at", "")),
            }
        )

    explicit_keys = (
        "consumed_capability_kind",
        "consumed_capability_kinds",
        "explicitly_consumed_capability_kind",
        "explicitly_consumed_capability_kinds",
        "used_capability_kind",
        "used_capability_kinds",
    )
    hook_keys = (
        "runtime_hook_reference",
        "runtime_hook_references",
        "planner_hook_reference",
        "planner_hook_references",
        "runtime_hook_adapter_gap_id",
        "stalled_capability_kind",
    )
    for row in list(consumption_rows or []):
        if not _after_created_at(row, promotion_cutoff):
            continue
        if not _payload_contains_capability(
            _first_present_payload(
                row,
                (
                    "consumed_capability_kind",
                    "consumed_capability_kinds",
                    "explicitly_consumed_capability_kind",
                    "explicitly_consumed_capability_kinds",
                    "capability_kind",
                ),
            ),
            capability_kind,
        ):
            continue
        add_signal("explicit_consumption", row, "capability_consumption_event")
        if bool(row.get("recognized_runtime_hook_invocation", False)) or list(
            row.get("runtime_hook_references", []) or []
        ):
            add_signal("runtime_hook_reference", row, "capability_consumption_event")
        if _truthy_marker(row, ("decision_changed_by_capability", "decision_influenced", "changed_decision")):
            add_signal("decision_change", row, "capability_consumption_event")
        if _truthy_marker(row, ("repeat_failure_prevented", "failure_prevented", "prevented_repeat_failure")):
            add_signal("failure_prevention", row, "capability_consumption_event")
        if _truthy_marker(row, ("budget_prevented_overrun", "prevented_budget_overrun")):
            add_signal("failure_prevention", row, "capability_consumption_event")
        if _truthy_marker(row, ("operator_intervention_reduced", "operator_intervention_reduction", "reduced_operator_intervention")):
            add_signal("operator_intervention_reduction", row, "capability_consumption_event")
        progress_delta = _first_present_payload(row, ("directive_progress_delta", "directive_progress_improvement"))
        try:
            progress_delta_float = float(progress_delta or 0)
        except (TypeError, ValueError):
            progress_delta_float = 0.0
        if progress_delta_float > 0 or _truthy_marker(row, ("directive_progress_improved_by_capability",)):
            add_signal("directive_progress_improvement", row, "capability_consumption_event")

    for source, rows in (("operation_result", operation_rows), ("meaningful_work", meaningful_rows)):
        for row in rows:
            if not _after_created_at(row, promotion_cutoff):
                continue
            explicitly_consumed = _payload_contains_capability(
                _first_present_payload(row, explicit_keys),
                capability_kind,
            )
            if explicitly_consumed:
                add_signal("explicit_consumption", row, source)
            if _payload_contains_capability(_first_present_payload(row, hook_keys), capability_kind):
                add_signal("runtime_hook_reference", row, source)
            elif explicitly_consumed and list(_first_present_payload(row, hook_keys) or []):
                add_signal("runtime_hook_reference", row, source)
            associated = _capability_associated(row, capability_kind)
            if not associated:
                continue
            if _truthy_marker(row, ("decision_changed_by_capability", "decision_influenced", "changed_decision")):
                add_signal("decision_change", row, source)
            if _truthy_marker(row, ("repeat_failure_prevented", "failure_prevented", "prevented_repeat_failure")):
                add_signal("failure_prevention", row, source)
            if _truthy_marker(row, ("budget_prevented_overrun", "prevented_budget_overrun")):
                add_signal("failure_prevention", row, source)
            if _truthy_marker(row, ("operator_intervention_reduced", "operator_intervention_reduction", "reduced_operator_intervention")):
                add_signal("operator_intervention_reduction", row, source)
            progress_delta = _first_present_payload(row, ("directive_progress_delta", "directive_progress_improvement"))
            try:
                progress_delta_float = float(progress_delta or 0)
            except (TypeError, ValueError):
                progress_delta_float = 0.0
            if progress_delta_float > 0 or _truthy_marker(row, ("directive_progress_improved_by_capability",)):
                add_signal("directive_progress_improvement", row, source)

    return {**counts, "strong_usefulness_signals": strong_signals}


def _capability_usefulness_evaluation(
    *,
    operator_root: str | Path,
    capability_kind: str = "",
    persist: bool = True,
) -> dict[str, Any]:
    promotions = list(reversed(_read_ledger(operator_root, "promotion_results", limit=100)))
    consumption_rows = list(reversed(_read_ledger(operator_root, "capability_consumption_events", limit=200)))
    if not capability_kind:
        promoted_kinds = {
            kind
            for kind in (_promotion_capability_kind(row) for row in promotions)
            if kind
        }
        for consumption in consumption_rows:
            consumed_payload = _first_present_payload(
                consumption,
                (
                    "explicitly_consumed_capability_kinds",
                    "consumed_capability_kinds",
                    "used_capability_kinds",
                    "explicitly_consumed_capability_kind",
                    "consumed_capability_kind",
                    "used_capability_kind",
                    "capability_kind",
                ),
            )
            consumed_kinds = (
                list(consumed_payload)
                if isinstance(consumed_payload, list)
                else [str(consumed_payload or "")]
            )
            capability_kind = next(
                (
                    str(kind).strip()
                    for kind in consumed_kinds
                    if str(kind).strip() in promoted_kinds
                ),
                "",
            )
            if capability_kind:
                break
    if not capability_kind:
        for promotion in promotions:
            capability_kind = _promotion_capability_kind(promotion)
            if capability_kind:
                break
    if not capability_kind:
        capability_kind = "none"
    matching_promotions = [
        row for row in promotions if _promotion_capability_kind(row) == capability_kind
    ]
    promotion_cutoff = _record_created_at(matching_promotions[0]) if matching_promotions else None
    meaningful_rows = list(reversed(_read_ledger(operator_root, "meaningful_work_evaluations", limit=200)))
    operation_rows = list(reversed(_read_ledger(operator_root, "operation_results", limit=200)))
    post_promotion_operation_rows = [
        row
        for row in operation_rows
        if _after_created_at(row, promotion_cutoff) and _capability_associated(row, capability_kind)
    ]
    post_promotion_meaningful_rows = [
        row
        for row in meaningful_rows
        if _after_created_at(row, promotion_cutoff) and _capability_associated(row, capability_kind)
    ]
    strict_signals = _strict_usefulness_signals(
        capability_kind=capability_kind,
        promotion_cutoff=promotion_cutoff,
        operation_rows=operation_rows,
        meaningful_rows=meaningful_rows,
        consumption_rows=consumption_rows,
    )
    strong_signals = list(strict_signals.get("strong_usefulness_signals", []) or [])
    strong_signal_count = len(strong_signals)
    failed_promotion = next(
        (
            row
            for row in matching_promotions
            if str(row.get("canary_result", "")) == "failed"
            or bool(row.get("rollback_performed", False))
            or str(row.get("status", "")).startswith("failed")
        ),
        {},
    )
    if failed_promotion:
        usefulness = "needs_followup"
        gate_reason = "promotion failed canary, rollback, or status gate"
    elif strong_signal_count >= 1:
        usefulness = "useful"
        gate_reason = "strict post-promotion usefulness signal observed"
    elif matching_promotions and not post_promotion_operation_rows and not post_promotion_meaningful_rows:
        usefulness = "dormant"
        gate_reason = "promoted capability has no later consumption or impact evidence"
    elif matching_promotions:
        usefulness = "evidence_only"
        gate_reason = "later evidence references the capability but does not prove consumption or impact"
    else:
        usefulness = "not_observed"
        gate_reason = "capability has no promotion evidence"
    strict_gate_passed = usefulness == "useful" and strong_signal_count >= 1
    confidence = min(1.0, strong_signal_count / 3.0)
    if usefulness == "evidence_only":
        confidence = max(confidence, 0.25)
    evaluation = {
        "schema_name": CAPABILITY_USEFULNESS_EVALUATION_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "usefulness_evaluation_id": "",
        "capability_kind": capability_kind,
        "capability_gap_id": capability_kind,
        "promotion_result_ids": [
            str(row.get("promotion_result_id", "")) for row in matching_promotions[:5]
        ],
        "usefulness": usefulness,
        "invocation_count": len(post_promotion_operation_rows),
        "useful_later_signal_count": strong_signal_count,
        "strong_usefulness_signal_count": strong_signal_count,
        "strong_usefulness_signals": strong_signals[:10],
        "explicit_consumption_count": int(strict_signals.get("explicit_consumption_count", 0) or 0),
        "decision_change_count": int(strict_signals.get("decision_change_count", 0) or 0),
        "failure_prevention_count": int(strict_signals.get("failure_prevention_count", 0) or 0),
        "directive_progress_improvement_count": int(strict_signals.get("directive_progress_improvement_count", 0) or 0),
        "operator_intervention_reduction_count": int(strict_signals.get("operator_intervention_reduction_count", 0) or 0),
        "runtime_hook_reference_count": int(strict_signals.get("runtime_hook_reference_count", 0) or 0),
        "strict_usefulness_gate_passed": strict_gate_passed,
        "usefulness_gate_reason": gate_reason,
        "unblocked_work": bool(strict_signals.get("failure_prevention_count", 0) or strict_signals.get("directive_progress_improvement_count", 0)),
        "directive_progress_effect": "positive" if int(strict_signals.get("directive_progress_improvement_count", 0) or 0) else "not_proven",
        "operator_intervention_effect": (
            "reduced"
            if int(strict_signals.get("operator_intervention_reduction_count", 0) or 0)
            else "not_measured"
        ),
        "failure_or_repair_signals": [
            str(failed_promotion.get("failure_reason", ""))
        ]
        if failed_promotion
        else [],
        "retirement_state": (
            "needs_repair"
            if usefulness == "needs_followup"
            else "dormant"
            if usefulness == "dormant"
            else "active"
            if usefulness == "useful"
            else "watch"
        ),
        "confidence": round(confidence, 3),
    }
    evaluation["usefulness_evaluation_id"] = _record_id("usefulness", evaluation)
    if not persist:
        return _redact_autonomy_value(evaluation)
    record = _append_ledger(operator_root, "capability_usefulness_evaluations", evaluation)
    _write_json(autonomy_root(operator_root) / "capability_usefulness_latest.json", record)
    return record


def _recent_useful_signal_count(operator_root: str | Path, capability_kind: str) -> int:
    count = 0
    for row in reversed(_read_ledger(operator_root, "capability_usefulness_evaluations", limit=100)):
        if str(row.get("capability_kind", "")) != capability_kind:
            continue
        if str(row.get("usefulness", "")) == "useful" and bool(
            row.get("strict_usefulness_gate_passed", False)
        ):
            count += 1
    return count


def _has_strict_usefulness_for_gap(operator_root: str | Path, gap_id: str) -> bool:
    gap = _safe_synthesized_capability_gap(gap_id)
    if not gap:
        return False
    for row in reversed(_read_ledger(operator_root, "capability_usefulness_evaluations", limit=200)):
        row_gap = str(row.get("capability_gap_id") or row.get("capability_kind") or "").strip()
        if row_gap != gap:
            continue
        if bool(row.get("strict_usefulness_gate_passed", False)):
            return True
    return False


def _promotion_progress_exists_for_gap(operator_root: str | Path, gap_id: str) -> bool:
    gap = _safe_synthesized_capability_gap(gap_id)
    if not gap:
        return False
    if gap in _promoted_capability_kind_set(operator_root):
        return True
    for row in reversed(_read_ledger(operator_root, "promotion_results", limit=200)):
        if _promotion_capability_kind(row) == gap:
            return True
    for row in reversed(_read_ledger(operator_root, "operation_proposals", limit=100)):
        if str(row.get("action", "")) != "promote_self_modification_candidate":
            continue
        row_gap = str(row.get("capability_gap_id") or row.get("capability_kind") or "").strip()
        if row_gap == gap:
            return True
    for row in reversed(_read_ledger(operator_root, "self_modification_proposals", limit=100)):
        row_gap = str(row.get("capability_gap_id") or row.get("capability_kind") or "").strip()
        if row_gap == gap and str(row.get("status", "")) in {
            "promotion_packet_ready",
            "promotion_approved",
            "promoted",
        }:
            return True
    return False


def _adaptive_learning_backoff_threshold(operator_root: str | Path) -> int:
    charter = load_autonomy_charter(operator_root)
    policy = dict(charter.get("overnight_stability_policy", {}) or {})
    return max(
        1,
        int(
            policy.get(
                "adaptive_learning_backoff_repeat_threshold",
                ADAPTIVE_LEARNING_BACKOFF_REPEAT_THRESHOLD,
            )
            or ADAPTIVE_LEARNING_BACKOFF_REPEAT_THRESHOLD
        ),
    )


def _adaptive_learning_hook_stall_threshold(operator_root: str | Path) -> int:
    charter = load_autonomy_charter(operator_root)
    policy = dict(charter.get("overnight_stability_policy", {}) or {})
    return max(
        1,
        int(
            policy.get(
                "adaptive_learning_hook_stall_threshold",
                ADAPTIVE_LEARNING_HOOK_STALL_THRESHOLD,
            )
            or ADAPTIVE_LEARNING_HOOK_STALL_THRESHOLD
        ),
    )


def _adaptive_learning_backoff_evaluation(
    operator_root: str | Path,
    *,
    persist: bool = False,
) -> dict[str, Any]:
    threshold = _adaptive_learning_backoff_threshold(operator_root)
    rows = list(reversed(_read_ledger(operator_root, "adaptive_learning_syntheses", limit=50)))
    repeated_gap = ""
    repeat_count = 0
    for row in rows:
        if str(row.get("status", "")) != "completed":
            if repeat_count:
                break
            continue
        gap = _safe_synthesized_capability_gap(row.get("next_capability_gap_proposal", ""))
        if not gap or not _is_promotable_synthesized_gap(gap):
            if repeat_count:
                break
            continue
        if not repeated_gap:
            repeated_gap = gap
        if gap != repeated_gap:
            break
        repeat_count += 1

    promoted = repeated_gap in _promoted_capability_kind_set(operator_root) if repeated_gap else False
    strict_useful = _has_strict_usefulness_for_gap(operator_root, repeated_gap) if repeated_gap else False
    promotion_progress = _promotion_progress_exists_for_gap(operator_root, repeated_gap) if repeated_gap else False
    unsafe_gap = not _is_promotable_synthesized_gap(repeated_gap) if repeated_gap else True
    blocked_reason = ""
    status = "not_evaluated"
    pivot_action = ""
    if not repeated_gap:
        status = "no_repeated_learning_gap"
        blocked_reason = "no recent completed adaptive-learning synthesis exposed a safe learning gap"
    elif unsafe_gap:
        status = "blocked"
        blocked_reason = "repeated learning gap is malformed, unsupported, or evidence-only"
    elif strict_useful:
        status = "satisfied_by_strict_usefulness"
        blocked_reason = "repeated learning gap already has strict later-usefulness evidence"
    elif promoted:
        status = "already_promoted"
        blocked_reason = "repeated learning gap already has promotion evidence"
    elif promotion_progress:
        status = "promotion_in_progress"
        blocked_reason = "repeated learning gap already has a promotion proposal or packet"
    elif repeat_count >= threshold:
        status = "promote_gap"
        pivot_action = "promote_self_modification_candidate"
        blocked_reason = (
            f"{repeated_gap} appeared in {repeat_count} completed adaptive-learning syntheses "
            "without strict usefulness or promotion progress"
        )
    else:
        status = "watch"
        blocked_reason = (
            f"{repeated_gap} repeated {repeat_count}/{threshold} times; adaptive learning remains within budget"
        )

    evaluation = {
        "schema_name": ADAPTIVE_LEARNING_BACKOFF_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "adaptive_learning_backoff_id": "",
        "repeated_learning_gap_id": repeated_gap,
        "repeat_count": repeat_count,
        "repeat_threshold": threshold,
        "backoff_status": status,
        "pivot_action": pivot_action,
        "backoff_promotion_eligible": status == "promote_gap",
        "strict_usefulness_present": strict_useful,
        "promotion_progress_present": promotion_progress,
        "already_promoted": promoted,
        "reason": blocked_reason,
    }
    evaluation["adaptive_learning_backoff_id"] = _record_id("adaptive-backoff", evaluation)
    if not persist:
        return _redact_autonomy_value(evaluation)
    record = _append_ledger(operator_root, "adaptive_learning_backoff_evaluations", evaluation)
    _write_json(autonomy_root(operator_root) / "adaptive_learning_backoff_latest.json", record)
    return record


def _runtime_hook_adapter_behavior(capability_kind: str) -> str:
    text = str(capability_kind or "").lower()
    if "failure" in text or "recovery" in text:
        return "failure_classification"
    if "dependency" in text or "fingerprint" in text or "idempotent" in text:
        return "duplicate_suppression"
    if "usefulness" in text or "summary" in text or "score" in text:
        return "status_summarization"
    if "churn" in text or "evidence" in text:
        return "read_only_evidence_synthesis"
    return "planner_bias"


def _runtime_hook_adapter_candidate(operator_root: str | Path) -> dict[str, Any]:
    latest_usefulness = _latest(operator_root, "capability_usefulness_evaluations")
    usefulness = str(latest_usefulness.get("usefulness", ""))
    if usefulness not in ADAPTIVE_LEARNING_HOOK_STALL_USEFULNESS:
        return {}
    if bool(latest_usefulness.get("strict_usefulness_gate_passed", False)):
        return {}
    capability_kind = _safe_synthesized_capability_gap(
        latest_usefulness.get("capability_kind", "")
        or latest_usefulness.get("capability_gap_id", "")
    )
    if "_hook_adapter" in capability_kind:
        return {}
    if (
        not capability_kind
        or capability_kind == BLOCKED_GROWTH_EVIDENCE_GAP_ID
        or capability_kind in CAPABILITY_GAP_KINDS
        or capability_kind not in _promoted_capability_kind_set(operator_root)
    ):
        return {}
    base = re.sub(r"_v\d+$", "", capability_kind)
    suffix = "_hook_adapter_v1"
    candidate = _safe_synthesized_capability_gap(f"{base[:64 - len(suffix)]}{suffix}")
    used = set(_used_capability_gap_ids(operator_root))
    promoted = _promoted_capability_kind_set(operator_root)
    if (
        not candidate
        or candidate in used
        or candidate in promoted
        or not _is_promotable_synthesized_gap(candidate)
    ):
        return {}
    behavior = _runtime_hook_adapter_behavior(capability_kind)
    if behavior not in RUNTIME_HOOK_ADAPTER_BEHAVIORS:
        return {}
    return {
        "source_capability_kind": capability_kind,
        "hook_adapter_candidate_gap_id": candidate,
        "runtime_hook_adapter_gap_id": candidate,
        "runtime_hook_adapter_behavior": behavior,
        "reason": (
            f"{capability_kind} is promoted but remains {usefulness}; a deterministic "
            f"{behavior} adapter can create real later consumption evidence."
        ),
    }


def _adaptive_learning_hook_stall_evaluation(
    operator_root: str | Path,
    *,
    governed_recovery_available: bool = False,
    governed_recovery_checkpoint_id: str = "",
    hook_adapter_candidate: Mapping[str, Any] | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    threshold = _adaptive_learning_hook_stall_threshold(operator_root)
    latest_usefulness = _latest(operator_root, "capability_usefulness_evaluations")
    usefulness = str(latest_usefulness.get("usefulness", ""))
    strict_useful = bool(latest_usefulness.get("strict_usefulness_gate_passed", False))
    stalled_capability = str(
        latest_usefulness.get("capability_kind")
        or latest_usefulness.get("capability_gap_id")
        or ""
    )
    repeat_count = 0
    consumed_hooks: list[str] = []
    consumed_kinds: list[str] = []
    for row in reversed(_read_ledger(operator_root, "capability_hook_consumptions", limit=50)):
        final_action = str(row.get("final_action", ""))
        hook_refs = [
            str(item).strip()
            for item in list(row.get("planner_hook_references", []) or [])
            if str(item).strip()
        ]
        matches = (
            bool(row.get("decision_changed_by_capability", False))
            and final_action == "adaptive_learning_synthesis"
            and any(ref in ADAPTIVE_LEARNING_HOOK_STALL_HOOK_TYPES for ref in hook_refs)
        )
        if not matches:
            break
        repeat_count += 1
        for ref in hook_refs:
            if ref in ADAPTIVE_LEARNING_HOOK_STALL_HOOK_TYPES and ref not in consumed_hooks:
                consumed_hooks.append(ref)
        for kind in list(row.get("consumed_capability_kinds", []) or []):
            kind_text = str(kind).strip()
            if kind_text and kind_text not in consumed_kinds:
                consumed_kinds.append(kind_text)
    adapter = dict(hook_adapter_candidate or _runtime_hook_adapter_candidate(operator_root))
    if strict_useful or usefulness == "useful":
        status = "cleared_by_strict_usefulness"
        pivot_action = ""
        reason = "latest capability usefulness evidence is strict-useful; hook stall is clear"
    elif usefulness not in ADAPTIVE_LEARNING_HOOK_STALL_USEFULNESS:
        status = "watch"
        pivot_action = ""
        reason = "latest usefulness state is not evidence-only/dormant/needs_followup"
    elif repeat_count >= threshold:
        status = "stalled"
        if governed_recovery_available:
            pivot_action = "governed_start_next_invocation"
            reason = "adaptive-learning hook redirects stalled; governed stale recovery is available"
        elif adapter:
            pivot_action = "promote_self_modification_candidate"
            reason = str(adapter.get("reason", "")) or (
                "adaptive-learning hook redirects stalled; promote a runtime-hook adapter"
            )
        else:
            pivot_action = "post_ladder_synthesis"
            reason = (
                "adaptive-learning hook redirects stalled and no safe runtime-hook adapter is available; "
                "fall back to read-only post-ladder synthesis"
            )
    else:
        status = "watch"
        pivot_action = ""
        reason = (
            f"hook redirects to adaptive_learning_synthesis repeated {repeat_count}/{threshold} "
            "times; adaptive learning remains within stall budget"
        )
    evaluation = {
        "schema_name": ADAPTIVE_LEARNING_HOOK_STALL_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "adaptive_learning_hook_stall_id": "",
        "hook_stall_status": status,
        "repeat_count": repeat_count,
        "repeat_threshold": threshold,
        "repeated_final_action": "adaptive_learning_synthesis",
        "stalled_capability_kind": stalled_capability,
        "latest_usefulness": usefulness,
        "strict_usefulness_gate_passed": strict_useful,
        "consumed_hook_types": consumed_hooks,
        "consumed_capability_kinds": consumed_kinds,
        "pivot_action": pivot_action,
        "reason": reason,
        "governed_stale_recovery_available": governed_recovery_available,
        "governed_recovery_checkpoint_id": governed_recovery_checkpoint_id,
        "hook_adapter_candidate_gap_id": str(adapter.get("hook_adapter_candidate_gap_id", "")),
        "runtime_hook_adapter_gap_id": str(adapter.get("runtime_hook_adapter_gap_id", "")),
        "runtime_hook_adapter_behavior": str(adapter.get("runtime_hook_adapter_behavior", "")),
        "source_capability_kind": str(adapter.get("source_capability_kind", "")),
    }
    evaluation["adaptive_learning_hook_stall_id"] = _record_id("hook-stall", evaluation)
    if not persist:
        return _redact_autonomy_value(evaluation)
    record = _append_ledger(operator_root, "adaptive_learning_hook_stall_evaluations", evaluation)
    _write_json(autonomy_root(operator_root) / "adaptive_learning_hook_stall_latest.json", record)
    return record


def _adaptive_learning_gap_family_id(gap_id: Any) -> str:
    gap = _safe_synthesized_capability_gap(gap_id)
    if not gap or not _is_promotable_synthesized_gap(gap):
        return ""
    if gap in CAPABILITY_GAP_KINDS:
        return ""
    stem = gap[:-3] if gap.endswith("_v1") else gap
    tokens = [item for item in stem.split("_") if item]
    token_set = set(tokens)
    for family_id, required_tokens in ADAPTIVE_LEARNING_FAMILY_ALIASES.items():
        if required_tokens.issubset(token_set):
            return family_id
    normalized = [
        token
        for token in tokens
        if token not in ADAPTIVE_LEARNING_FAMILY_VARIANT_WORDS
    ]
    if len(normalized) < 2:
        normalized = tokens[:3]
    family_id = "_".join(normalized[:5]).strip("_")
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,60}", family_id):
        return ""
    return family_id


def _canonical_gap_for_family(family_id: str) -> str:
    family = str(family_id or "").strip()
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,60}", family):
        return ""
    return _safe_synthesized_capability_gap(f"{family}_v1")


def _has_strict_usefulness_for_gap_family(
    operator_root: str | Path,
    family_id: str,
    member_gap_ids: Iterable[str],
) -> bool:
    family = str(family_id or "").strip()
    members = {_safe_synthesized_capability_gap(item) for item in member_gap_ids}
    members.discard("")
    for row in reversed(_read_ledger(operator_root, "capability_usefulness_evaluations", limit=300)):
        row_gap = str(row.get("capability_gap_id") or row.get("capability_kind") or "").strip()
        if row_gap not in members and _adaptive_learning_gap_family_id(row_gap) != family:
            continue
        if bool(row.get("strict_usefulness_gate_passed", False)):
            return True
    return False


def _promotion_progress_exists_for_gap_family(
    operator_root: str | Path,
    family_id: str,
    member_gap_ids: Iterable[str],
    representative_gap_id: str,
) -> bool:
    family = str(family_id or "").strip()
    members = {_safe_synthesized_capability_gap(item) for item in member_gap_ids}
    representative = _safe_synthesized_capability_gap(representative_gap_id)
    if representative:
        members.add(representative)
    members.discard("")
    for gap in members:
        if _promotion_progress_exists_for_gap(operator_root, gap):
            return True
    for record in reversed(_read_ledger(operator_root, "promotion_results", limit=300)):
        if _adaptive_learning_gap_family_id(_promotion_capability_kind(record)) == family:
            return True
    for row in reversed(_read_ledger(operator_root, "operation_proposals", limit=150)):
        if str(row.get("action", "")) != "promote_self_modification_candidate":
            continue
        row_gap = str(row.get("capability_gap_id") or row.get("capability_kind") or "").strip()
        if _adaptive_learning_gap_family_id(row_gap) == family:
            return True
    return False


def _representative_gap_for_learning_family(
    operator_root: str | Path,
    family_id: str,
    member_gap_ids: Iterable[str],
) -> str:
    canonical = _canonical_gap_for_family(family_id)
    if (
        canonical
        and canonical not in CAPABILITY_GAP_KINDS
        and _is_promotable_synthesized_gap(canonical)
        and not _promotion_progress_exists_for_gap(operator_root, canonical)
    ):
        return canonical
    for gap in member_gap_ids:
        safe_gap = _safe_synthesized_capability_gap(gap)
        if (
            safe_gap
            and safe_gap not in CAPABILITY_GAP_KINDS
            and _is_promotable_synthesized_gap(safe_gap)
            and not _promotion_progress_exists_for_gap(operator_root, safe_gap)
        ):
            return safe_gap
    return ""


def _adaptive_learning_gap_family_evaluation(
    operator_root: str | Path,
    *,
    exact_backoff: Mapping[str, Any] | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    threshold = _adaptive_learning_backoff_threshold(operator_root)
    exact_status = str(dict(exact_backoff or {}).get("backoff_status", ""))
    rows = list(reversed(_read_ledger(operator_root, "adaptive_learning_syntheses", limit=80)))
    family_members: dict[str, list[str]] = {}
    family_counts: dict[str, int] = {}
    latest_family = ""
    for row in rows:
        if str(row.get("status", "")) != "completed":
            continue
        gap = _safe_synthesized_capability_gap(row.get("next_capability_gap_proposal", ""))
        family = _adaptive_learning_gap_family_id(gap)
        if not family:
            continue
        if not latest_family:
            latest_family = family
        if family not in family_members:
            family_members[family] = []
            family_counts[family] = 0
        family_counts[family] += 1
        if gap not in family_members[family]:
            family_members[family].append(gap)

    family_id = latest_family
    member_gap_ids = list(family_members.get(family_id, []) or [])
    repeat_count = int(family_counts.get(family_id, 0) or 0)
    representative_gap = _representative_gap_for_learning_family(
        operator_root,
        family_id,
        member_gap_ids,
    )
    strict_useful = (
        _has_strict_usefulness_for_gap_family(operator_root, family_id, member_gap_ids)
        if family_id
        else False
    )
    promotion_progress = (
        _promotion_progress_exists_for_gap_family(
            operator_root,
            family_id,
            member_gap_ids,
            representative_gap,
        )
        if family_id
        else False
    )
    status = "not_evaluated"
    pivot_action = ""
    reason = ""
    if exact_status == "promote_gap":
        status = "exact_backoff_wins"
        reason = "exact adaptive-learning backoff already selected a promotion pivot"
    elif not family_id:
        status = "no_family"
        reason = "no recent adaptive-learning synthesis exposed a safe semantic family"
    elif not representative_gap:
        status = "blocked"
        reason = "no safe representative gap is available for the semantic family"
    elif strict_useful:
        status = "satisfied_by_strict_usefulness"
        reason = "semantic family already has strict later-usefulness evidence"
    elif promotion_progress:
        status = "promotion_in_progress"
        reason = "semantic family already has promotion evidence or a promotion proposal"
    elif repeat_count >= threshold:
        status = "promote_family_gap"
        pivot_action = "promote_self_modification_candidate"
        reason = (
            f"{family_id} appeared in {repeat_count} completed adaptive-learning syntheses "
            "without strict usefulness or promotion progress"
        )
    else:
        status = "watch"
        reason = (
            f"{family_id} family repeated {repeat_count}/{threshold} times; adaptive learning remains within budget"
        )

    evaluation = {
        "schema_name": ADAPTIVE_LEARNING_GAP_FAMILY_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "adaptive_learning_gap_family_evaluation_id": "",
        "family_backoff_id": "",
        "family_id": family_id,
        "adaptive_learning_gap_family_id": family_id,
        "member_gap_ids": member_gap_ids[:20],
        "family_member_gap_ids": member_gap_ids[:20],
        "member_gap_count": len(member_gap_ids),
        "repeat_count": repeat_count,
        "repeat_threshold": threshold,
        "representative_gap_id": representative_gap,
        "family_backoff_status": status,
        "pivot_action": pivot_action,
        "family_backoff_promotion_eligible": status == "promote_family_gap",
        "strict_usefulness_present": strict_useful,
        "promotion_progress_present": promotion_progress,
        "reason": reason,
    }
    evaluation["adaptive_learning_gap_family_evaluation_id"] = _record_id(
        "adaptive-family",
        evaluation,
    )
    evaluation["family_backoff_id"] = evaluation["adaptive_learning_gap_family_evaluation_id"]
    if not persist:
        return _redact_autonomy_value(evaluation)
    record = _append_ledger(operator_root, "adaptive_learning_gap_family_evaluations", evaluation)
    _write_json(autonomy_root(operator_root) / "adaptive_learning_gap_family_latest.json", record)
    return record


def _default_novelty_policy() -> dict[str, Any]:
    return {
        "enabled": True,
        "recent_capability_memory_window": 12,
        "repeated_promoted_kind_cooldown_cycles": 6,
        "allow_repeat_for": list(DEFAULT_NOVELTY_REPEAT_REASONS),
        "capability_gap_priority_order": list(CAPABILITY_GAP_KINDS),
    }


def _promotion_capability_kind(record: Mapping[str, Any]) -> str:
    kind = str(record.get("capability_kind") or record.get("capability_gap_id") or "").strip()
    if kind:
        return kind
    result = dict(record.get("result", {}) or {})
    kind = str(result.get("capability_kind") or result.get("capability_gap_id") or "").strip()
    if kind:
        return kind
    legacy_text = _compact_json(record)
    if "autonomy_growth_capability" in legacy_text:
        return "promotion_packet_generation"
    return ""


def _recent_promoted_capability_kinds(
    operator_root: str | Path,
    *,
    limit: int,
) -> list[str]:
    kinds: list[str] = []
    for record in reversed(_read_ledger(operator_root, "promotion_results", limit=max(1, limit))):
        if str(record.get("status", "")) != "promoted" and not bool(record.get("auto_adopted", False)):
            continue
        kind = _promotion_capability_kind(record)
        if kind:
            kinds.append(kind)
    return kinds


def _latest_failed_promotion_for_kind(operator_root: str | Path, capability_kind: str) -> dict[str, Any]:
    for record in reversed(_read_ledger(operator_root, "promotion_results", limit=100)):
        if _promotion_capability_kind(record) != capability_kind:
            continue
        status = str(record.get("status", ""))
        failed_canary = str(record.get("canary_result", "")) == "failed"
        failed_rollback = bool(record.get("rollback_performed", False)) and status != "promoted"
        if failed_canary or failed_rollback or status.startswith("failed"):
            return record
        return {}
    return {}


def _safe_synthesized_capability_gap(value: Any) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,64}", text):
        return ""
    if text in SUPPORTED_OPERATION_ACTIONS:
        return ""
    return text


def _is_promotable_synthesized_gap(value: Any) -> bool:
    gap_id = _safe_synthesized_capability_gap(value)
    return bool(gap_id and gap_id != BLOCKED_GROWTH_EVIDENCE_GAP_ID)


def _synthesized_capability_gap_kinds(operator_root: str | Path) -> list[str]:
    proposals: list[str] = []
    for synthesis in reversed(_read_ledger(operator_root, "post_ladder_syntheses", limit=25)):
        proposal = _safe_synthesized_capability_gap(
            synthesis.get("next_capability_gap_proposal", "")
        )
        if (
            not proposal
            or proposal in CAPABILITY_GAP_KINDS
            or proposal in proposals
            or not _is_promotable_synthesized_gap(proposal)
            or not bool(synthesis.get("next_gap_promotable", True))
        ):
            continue
        proposals.append(proposal)
    return proposals


def _backoff_promotable_learning_gap_kinds(operator_root: str | Path) -> list[str]:
    proposals: list[str] = []
    for row in reversed(_read_ledger(operator_root, "adaptive_learning_backoff_evaluations", limit=25)):
        if str(row.get("backoff_status", "")) != "promote_gap":
            continue
        proposal = _safe_synthesized_capability_gap(row.get("repeated_learning_gap_id", ""))
        if (
            not proposal
            or proposal in CAPABILITY_GAP_KINDS
            or proposal in proposals
            or not _is_promotable_synthesized_gap(proposal)
        ):
            continue
        proposals.append(proposal)
    return proposals


def _family_backoff_promotable_learning_gap_kinds(operator_root: str | Path) -> list[str]:
    proposals: list[str] = []
    for row in reversed(_read_ledger(operator_root, "adaptive_learning_gap_family_evaluations", limit=25)):
        if str(row.get("family_backoff_status", "")) != "promote_family_gap":
            continue
        proposal = _safe_synthesized_capability_gap(row.get("representative_gap_id", ""))
        if (
            not proposal
            or proposal in CAPABILITY_GAP_KINDS
            or proposal in proposals
            or not _is_promotable_synthesized_gap(proposal)
        ):
            continue
        proposals.append(proposal)
    return proposals


def _learning_synthesized_capability_gap_kinds(operator_root: str | Path) -> list[str]:
    proposals: list[str] = []
    backoff_promotable = set(_backoff_promotable_learning_gap_kinds(operator_root))
    family_backoff_promotable = set(_family_backoff_promotable_learning_gap_kinds(operator_root))
    for challenge in reversed(_read_ledger(operator_root, "self_curriculum_challenges", limit=50)):
        proposal = _safe_synthesized_capability_gap(
            challenge.get("next_capability_gap_proposal", "")
        )
        backoff_eligible = proposal in backoff_promotable or bool(
            challenge.get("backoff_promotion_eligible", False)
        )
        family_backoff_eligible = proposal in family_backoff_promotable or bool(
            challenge.get("family_backoff_promotion_eligible", False)
        )
        if (
            not proposal
            or proposal in CAPABILITY_GAP_KINDS
            or proposal in proposals
            or not bool(challenge.get("next_gap_promotable", False))
            or not (
                bool(challenge.get("promotion_threshold_met", False))
                or backoff_eligible
                or family_backoff_eligible
            )
        ):
            continue
        proposals.append(proposal)
    for proposal in (
        _backoff_promotable_learning_gap_kinds(operator_root)
        + _family_backoff_promotable_learning_gap_kinds(operator_root)
    ):
        if proposal not in proposals:
            proposals.append(proposal)
    return proposals


def _effective_capability_gap_priority_order(
    operator_root: str | Path,
    policy: Mapping[str, Any] | None = None,
) -> list[str]:
    if policy is None:
        policy = dict(load_autonomy_charter(operator_root).get("novelty_policy", {}) or {})
    base_order = [
        str(item).strip()
        for item in list(policy.get("capability_gap_priority_order", []) or [])
        if str(item).strip() in CAPABILITY_GAP_KINDS
    ] or list(CAPABILITY_GAP_KINDS)
    base_order = list(dict.fromkeys(base_order))
    synthesized_order = list(
        dict.fromkeys(
            _learning_synthesized_capability_gap_kinds(operator_root)
            + _synthesized_capability_gap_kinds(operator_root)
        )
    )
    if not synthesized_order:
        return base_order
    promoted_kinds = _promoted_capability_kind_set(operator_root)
    base_ladder_promoted = all(kind in promoted_kinds for kind in base_order)
    if not base_ladder_promoted:
        return base_order + [kind for kind in synthesized_order if kind not in base_order]
    unpromoted_frontiers = [kind for kind in synthesized_order if kind not in promoted_kinds]
    promoted_frontiers = [kind for kind in synthesized_order if kind in promoted_kinds]
    return unpromoted_frontiers + base_order + promoted_frontiers


def _promoted_capability_kind_set(operator_root: str | Path) -> set[str]:
    promoted: set[str] = set()
    for record in _read_ledger(operator_root, "promotion_results", limit=500):
        if str(record.get("status", "")) != "promoted" and not bool(record.get("auto_adopted", False)):
            continue
        kind = _promotion_capability_kind(record)
        if kind:
            promoted.add(kind)
    return promoted


def _capability_retired_kind_set(operator_root: str | Path) -> set[str]:
    retired: set[str] = set()
    for record in _read_ledger(operator_root, "capability_usefulness_evaluations", limit=200):
        if str(record.get("retirement_state", "")).strip() == "retired":
            kind = str(record.get("capability_kind") or record.get("capability_gap_id") or "").strip()
            if kind:
                retired.add(kind)
    return retired


def _capability_hook_type(capability_kind: str) -> str:
    for suffix, hook_type in CAPABILITY_PLANNER_HOOK_SUFFIXES.items():
        if capability_kind.endswith(suffix):
            return hook_type
    return ""


def _runtime_adapter_behavior_for_hook_type(hook_type: str) -> str:
    return RUNTIME_ADAPTER_BEHAVIOR_BY_HOOK_TYPE.get(str(hook_type or ""), "planner_bias")


def _runtime_adapter_behavior_for_capability(capability_kind: str, payload: Mapping[str, Any]) -> str:
    declared = str(payload.get("runtime_hook_adapter_behavior", "")).strip()
    if declared in RUNTIME_HOOK_ADAPTER_BEHAVIORS:
        return declared
    hook_type = _capability_hook_type(capability_kind)
    if hook_type:
        return _runtime_adapter_behavior_for_hook_type(hook_type)
    if capability_kind == "execution_budget_guardrails_v1" or capability_kind.endswith("_execution_budget_guardrails_v1"):
        return "execution_budget_guardrails"
    if "_hook_adapter" not in str(capability_kind or ""):
        return ""
    text = str(capability_kind or "").lower()
    if "trace" in text or "replay" in text or "fingerprint" in text:
        return "replay_fingerprint_support"
    if "failure" in text or "recovery" in text:
        return "failure_classification"
    if "summary" in text or "summarization" in text or "score" in text:
        return "status_summarization"
    if "evidence" in text or "synthesis" in text or "workplan" in text:
        return "read_only_evidence_synthesis"
    return ""


def _consumption_contract_for_kind(operator_root: str | Path, capability_kind: str) -> dict[str, Any]:
    for row in reversed(_read_ledger(operator_root, "capability_consumption_contracts", limit=250)):
        if str(row.get("capability_kind", "")) == capability_kind and str(row.get("status", "")) == "active":
            return row
    return {}


def _runtime_adapter_entrypoints(behavior: str) -> list[str]:
    if behavior in {"planner_bias", "duplicate_suppression", "failure_classification", "budget_stall_throttling"}:
        return ["autonomy_planner"]
    if behavior in {"status_summarization", "read_only_evidence_synthesis", "replay_fingerprint_support"}:
        return ["autonomy_planner", "read_only_evidence_synthesis"]
    return ["autonomy_planner"]


def _ensure_capability_consumption_contract(
    operator_root: str | Path,
    capability: Mapping[str, Any],
    *,
    source_path: str = "",
) -> dict[str, Any]:
    capability_kind = str(capability.get("capability_kind") or capability.get("capability_gap_id") or "").strip()
    if not capability_kind:
        return {}
    existing = _consumption_contract_for_kind(operator_root, capability_kind)
    if existing:
        return existing
    hook_type = str(capability.get("hook_type") or _capability_hook_type(capability_kind))
    behavior = _runtime_adapter_behavior_for_capability(capability_kind, capability)
    if not behavior or behavior not in RUNTIME_HOOK_ADAPTER_BEHAVIORS:
        return {}
    adapter = {
        "schema_name": RUNTIME_CAPABILITY_ADAPTER_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "runtime_capability_adapter_id": "",
        "capability_kind": capability_kind,
        "capability_gap_id": str(capability.get("capability_gap_id") or capability_kind),
        "hook_type": hook_type,
        "adapter_behavior": behavior,
        "eligible_entrypoints": _runtime_adapter_entrypoints(behavior),
        "source_path_hint": source_path,
        "status": "active",
        "authority_boundary": "state-only deterministic planner/runtime adapter; no direct governed launch or protected-root mutation authority",
    }
    adapter["runtime_capability_adapter_id"] = _record_id("adapter", adapter)
    adapter_record = _append_ledger(operator_root, "runtime_capability_adapters", adapter)
    _write_json(autonomy_root(operator_root) / "runtime_capability_adapter_latest.json", adapter_record)
    contract = {
        "schema_name": CAPABILITY_CONSUMPTION_CONTRACT_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "capability_consumption_contract_id": "",
        "capability_kind": capability_kind,
        "capability_gap_id": str(capability.get("capability_gap_id") or capability_kind),
        "runtime_capability_adapter_id": str(adapter_record.get("runtime_capability_adapter_id", "")),
        "hook_type": hook_type,
        "adapter_behavior": behavior,
        "eligible_entrypoints": list(adapter_record.get("eligible_entrypoints", []) or []),
        "required_consumption_evidence": [
            "CapabilityConsumptionEvent",
            "decision_changed_by_capability",
            "repeat_failure_prevented",
            "directive_progress_improved_by_capability",
            "operator_intervention_reduced",
            "recognized_runtime_hook_invocation",
        ],
        "non_authority_guarantees": [
            "cannot launch governed execution directly",
            "cannot mutate protected roots",
            "cannot call local Ollama or external trusted sources",
            "cannot bypass approval board, operation broker, canary, rollback, emergency stop, memory pressure, or novelty gates",
        ],
        "source_path_hint": source_path,
        "status": "active",
    }
    contract["capability_consumption_contract_id"] = _record_id("contract", contract)
    record = _append_ledger(operator_root, "capability_consumption_contracts", contract)
    _write_json(autonomy_root(operator_root) / "capability_consumption_contract_latest.json", record)
    return record


def _contractable_promoted_capabilities(operator_root: str | Path) -> list[dict[str, Any]]:
    adopted_dir = autonomy_root(operator_root) / "adopted_capabilities"
    if not adopted_dir.exists():
        return []
    promoted = _promoted_capability_kind_set(operator_root)
    retired = _capability_retired_kind_set(operator_root)
    capabilities: list[dict[str, Any]] = []
    for path in sorted(adopted_dir.glob("*_latest.json")):
        payload = _read_json(path)
        capability_kind = str(payload.get("capability_kind") or payload.get("capability_gap_id") or "").strip()
        if not capability_kind or capability_kind not in promoted or capability_kind in retired:
            continue
        behavior = _runtime_adapter_behavior_for_capability(capability_kind, payload)
        if behavior not in RUNTIME_HOOK_ADAPTER_BEHAVIORS:
            continue
        item = dict(payload)
        item["source_path"] = str(path)
        item["adapter_behavior"] = behavior
        item["hook_type"] = str(item.get("hook_type") or _capability_hook_type(capability_kind))
        capabilities.append(item)
    return capabilities


def _capabilities_lacking_consumption_contracts(operator_root: str | Path) -> list[str]:
    missing: list[str] = []
    for capability in _contractable_promoted_capabilities(operator_root):
        capability_kind = str(capability.get("capability_kind") or capability.get("capability_gap_id") or "")
        if capability_kind and not _consumption_contract_for_kind(operator_root, capability_kind):
            missing.append(capability_kind)
    return missing


def _same_capability_usefulness_state_count(
    operator_root: str | Path,
    capability_kind: str,
    states: set[str],
    *,
    limit: int = 25,
) -> int:
    count = 0
    for row in reversed(_read_ledger(operator_root, "capability_usefulness_evaluations", limit=limit)):
        if str(row.get("capability_kind") or row.get("capability_gap_id") or "") != capability_kind:
            continue
        if bool(row.get("strict_usefulness_gate_passed", False)):
            break
        if str(row.get("usefulness", "")) not in states:
            break
        count += 1
    return count


def _capability_retirement_evaluation(
    operator_root: str | Path,
    *,
    latest_usefulness: Mapping[str, Any] | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    usefulness = dict(latest_usefulness or _latest(operator_root, "capability_usefulness_evaluations"))
    capability_kind = str(usefulness.get("capability_kind") or usefulness.get("capability_gap_id") or "")
    usefulness_state = str(usefulness.get("usefulness", ""))
    strict = bool(usefulness.get("strict_usefulness_gate_passed", False))
    repeated_count = (
        _same_capability_usefulness_state_count(
            operator_root,
            capability_kind,
            {"evidence_only", "dormant", "needs_followup"},
        )
        if capability_kind
        else 0
    )
    contract_missing = capability_kind in _capabilities_lacking_consumption_contracts(operator_root)
    status = "not_evaluated"
    pivot_action = ""
    reason = "No capability usefulness record is available."
    if capability_kind:
        if strict or usefulness_state == "useful":
            status = "active"
            reason = "Capability has strict usefulness evidence."
        elif contract_missing:
            status = "needs_contract"
            pivot_action = "post_ladder_synthesis"
            reason = "Promoted capability is contractable but lacks a consumption contract."
        elif repeated_count >= CAPABILITY_CONSUMPTION_CONTRACT_STALE_EVALUATIONS:
            status = "needs_followup" if usefulness_state == "evidence_only" else "dormant"
            pivot_action = "post_ladder_synthesis"
            reason = (
                f"{capability_kind} has {repeated_count} repeated {usefulness_state} "
                "evaluations without strict consumption evidence."
            )
        else:
            status = "watch"
            reason = (
                f"{capability_kind} has {repeated_count}/"
                f"{CAPABILITY_CONSUMPTION_CONTRACT_STALE_EVALUATIONS} weak usefulness evaluations."
            )
    evaluation = {
        "schema_name": CAPABILITY_RETIREMENT_EVALUATION_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "capability_retirement_evaluation_id": "",
        "capability_kind": capability_kind,
        "capability_gap_id": capability_kind,
        "usefulness": usefulness_state,
        "strict_usefulness_gate_passed": strict,
        "weak_usefulness_repeat_count": repeated_count,
        "weak_usefulness_repeat_threshold": CAPABILITY_CONSUMPTION_CONTRACT_STALE_EVALUATIONS,
        "consumption_contract_missing": contract_missing,
        "retirement_status": status,
        "pivot_action": pivot_action,
        "reason": reason,
    }
    evaluation["capability_retirement_evaluation_id"] = _record_id("retire", evaluation)
    if not persist:
        return _redact_autonomy_value(evaluation)
    record = _append_ledger(operator_root, "capability_retirement_evaluations", evaluation)
    _write_json(autonomy_root(operator_root) / "capability_retirement_evaluation_latest.json", record)
    return record


def _load_promoted_capability_hooks(operator_root: str | Path) -> list[dict[str, Any]]:
    adopted_dir = autonomy_root(operator_root) / "adopted_capabilities"
    if not adopted_dir.exists():
        return []
    promoted = _promoted_capability_kind_set(operator_root)
    retired = _capability_retired_kind_set(operator_root)
    hooks: list[dict[str, Any]] = []
    for path in sorted(adopted_dir.glob("*_latest.json")):
        payload = _read_json(path)
        capability_kind = str(
            payload.get("capability_kind") or payload.get("capability_gap_id") or ""
        ).strip()
        if not capability_kind or capability_kind not in promoted or capability_kind in retired:
            continue
        hook_type = _capability_hook_type(capability_kind)
        if not hook_type:
            continue
        hook = {
            "capability_kind": capability_kind,
            "capability_gap_id": str(payload.get("capability_gap_id") or capability_kind),
            "hook_type": hook_type,
            "source_path": str(path),
            "summary": str(payload.get("summary", "")),
        }
        contract = _ensure_capability_consumption_contract(operator_root, hook, source_path=str(path))
        hook["capability_consumption_contract_id"] = str(
            contract.get("capability_consumption_contract_id", "")
        )
        hook["runtime_capability_adapter_id"] = str(contract.get("runtime_capability_adapter_id", ""))
        hook["adapter_behavior"] = str(contract.get("adapter_behavior", ""))
        hooks.append(hook)
    return hooks


def _planner_hook_fingerprint(
    *,
    baseline_action: str,
    memory_band: str,
    novelty_preview: Mapping[str, Any],
    growth_pivot: bool,
    safe_growth_available: bool,
    synthesis_needed: bool,
    adaptive_needed: bool,
    adaptive_backoff_status: str = "",
) -> str:
    return _hash_payload(
        {
            "baseline_action": baseline_action,
            "memory_band": memory_band,
            "selected_capability_kind": str(novelty_preview.get("selected_capability_kind", "")),
            "novelty_status": str(novelty_preview.get("novelty_status", "")),
            "growth_pivot": growth_pivot,
            "safe_growth_available": safe_growth_available,
            "synthesis_needed": synthesis_needed,
            "adaptive_needed": adaptive_needed,
            "adaptive_backoff_status": adaptive_backoff_status,
        },
        length=16,
    )


def _operation_failed_or_warned(row: Mapping[str, Any]) -> bool:
    status = str(row.get("status", "")).lower()
    result = dict(row.get("result", {}) or {})
    return (
        "timeout" in status
        or "refused" in status
        or "warning" in status
        or bool(result.get("timed_out", False))
        or str(result.get("status", "")).lower() in {"timeout", "refused", "failed"}
    )


def _recent_same_action_rows(
    operator_root: str | Path,
    *,
    action: str,
    capability_kind: str = "",
    limit: int = 25,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in reversed(_read_ledger(operator_root, "operation_results", limit=limit)):
        if str(row.get("action", "")) != action:
            continue
        if capability_kind:
            row_kind = str(row.get("capability_kind") or row.get("capability_gap_id") or "")
            if row_kind and row_kind != capability_kind:
                continue
        rows.append(row)
    return rows


def _latest_hook_fingerprint_seen(operator_root: str | Path, fingerprint: str) -> bool:
    if not fingerprint:
        return False
    for row in reversed(_read_ledger(operator_root, "capability_hook_consumptions", limit=25)):
        if str(row.get("input_fingerprint", "")) == fingerprint:
            return True
    for row in reversed(_read_ledger(operator_root, "plan_candidates", limit=25)):
        if str(row.get("planner_input_fingerprint", "")) == fingerprint:
            return True
    return False


def _safe_hook_target(
    *,
    preferred: str,
    baseline_action: str,
    memory_band: str,
    synthesis_needed: bool,
    adaptive_needed: bool,
    safe_growth_available: bool,
    governed_ready: bool,
    directive_loaded: bool,
    growth_pivot: bool,
    adaptive_backoff_status: str = "",
    adaptive_hook_stalled: bool = False,
    governed_recovery_available: bool = False,
) -> str:
    if memory_band in {"warning", "action", "critical"}:
        if preferred == "memory_ledger_compaction" or baseline_action == "memory_ledger_compaction":
            return "memory_ledger_compaction"
        if memory_band in {"action", "critical"} and baseline_action == "memory_pressure_archive":
            return baseline_action
        if memory_band in {"action", "critical"}:
            return "memory_ledger_compaction"
    if synthesis_needed:
        return "post_ladder_synthesis"
    if adaptive_backoff_status in {"promote_gap", "promote_family_gap"} and preferred == "adaptive_learning_synthesis":
        return "promote_self_modification_candidate" if safe_growth_available else baseline_action
    if directive_loaded and governed_ready and not growth_pivot:
        return "governed_start_next_invocation"
    if adaptive_needed and not adaptive_hook_stalled:
        return "adaptive_learning_synthesis"
    allowed = {
        "novali_stack_status",
        "post_ladder_synthesis",
        "adaptive_learning_synthesis",
        "trusted_source_literature_triage_digest",
        "memory_ledger_compaction",
    }
    if safe_growth_available:
        allowed.add("promote_self_modification_candidate")
    if directive_loaded and ((governed_ready and not growth_pivot) or governed_recovery_available):
        allowed.add("governed_start_next_invocation")
    if preferred in allowed:
        return preferred
    return baseline_action


def _recent_action_repeat_count(operator_root: str | Path, action: str, *, limit: int = 8) -> int:
    count = 0
    for row in reversed(_read_ledger(operator_root, "operation_results", limit=limit)):
        if str(row.get("action", "")) != action:
            break
        count += 1
    return count


def _recent_equivalent_action_repeat_count(
    operator_root: str | Path,
    action: str,
    *,
    capability_kind: str = "",
    limit: int = 8,
) -> int:
    count = 0
    capability_kind = str(capability_kind or "").strip()
    for row in reversed(_read_ledger(operator_root, "operation_results", limit=limit)):
        if str(row.get("action", "")) != action:
            break
        if capability_kind and str(row.get("capability_kind") or row.get("capability_gap_id") or "") != capability_kind:
            break
        count += 1
    return count


def _execution_budget_guardrail_evaluation(
    operator_root: str | Path,
    *,
    baseline_action: str,
    memory_band: str,
    selected_capability_kind: str = "",
    adaptive_hook_stall: Mapping[str, Any] | None = None,
    trusted_source_attempt_count: int = 0,
    persist: bool = False,
) -> dict[str, Any]:
    charter = load_autonomy_charter(operator_root)
    budgets = dict(charter.get("budgets", {}) or {})
    overnight = dict(charter.get("overnight_stability_policy", {}) or {})
    max_operation_seconds = int(budgets.get("max_operation_runtime_seconds", 180) or 180)
    repeat_threshold = int(
        overnight.get("adaptive_learning_hook_stall_threshold", ADAPTIVE_LEARNING_HOOK_STALL_THRESHOLD)
        or ADAPTIVE_LEARNING_HOOK_STALL_THRESHOLD
    )
    repeated_action_count = _recent_action_repeat_count(operator_root, baseline_action)
    equivalent_repeat_count = _recent_equivalent_action_repeat_count(
        operator_root,
        baseline_action,
        capability_kind=selected_capability_kind,
    )
    hook_repeat_count = int(dict(adaptive_hook_stall or {}).get("repeat_count", 0) or 0)
    trusted_source_attempt_count = int(trusted_source_attempt_count or 0)
    budget_decision = "continue"
    recommended_action = baseline_action
    reason = "budget guardrails allow the baseline planner action"
    prevented_overrun = False
    if memory_band in {"action", "critical"}:
        budget_decision = "run_ledger_compaction"
        recommended_action = "memory_ledger_compaction"
        reason = f"memory pressure band {memory_band} requires ledger compaction before more growth work"
        prevented_overrun = True
    elif memory_band == "warning" and baseline_action in {
        "adaptive_learning_synthesis",
        "post_ladder_synthesis",
        "promote_self_modification_candidate",
        "trusted_source_literature_triage_digest",
    }:
        budget_decision = "run_ledger_compaction"
        recommended_action = "memory_ledger_compaction"
        reason = "memory pressure warning defers nonessential growth to compact cold ledger evidence"
        prevented_overrun = True
    elif baseline_action == "adaptive_learning_synthesis" and hook_repeat_count >= max(1, repeat_threshold - 1):
        budget_decision = "throttle_to_synthesis"
        recommended_action = "post_ladder_synthesis"
        reason = (
            f"adaptive-learning hook redirects reached {hook_repeat_count}/{repeat_threshold}; "
            "read-only synthesis should break the loop before another learning pass"
        )
        prevented_overrun = True
    elif baseline_action == "adaptive_learning_synthesis" and repeated_action_count >= 4:
        budget_decision = "throttle_to_synthesis"
        recommended_action = "post_ladder_synthesis"
        reason = f"{baseline_action} repeated {repeated_action_count} consecutive times"
        prevented_overrun = True
    elif baseline_action == "promote_self_modification_candidate" and equivalent_repeat_count >= 4:
        budget_decision = "throttle_to_synthesis"
        recommended_action = "post_ladder_synthesis"
        reason = (
            f"{baseline_action} repeated {equivalent_repeat_count} consecutive times for "
            f"{selected_capability_kind or 'the same capability'}"
        )
        prevented_overrun = True
    elif baseline_action == "trusted_source_literature_triage_digest" and trusted_source_attempt_count >= TRUSTED_SOURCE_SYNTHESIS_MAX_ATTEMPTS:
        budget_decision = "defer_external_triage"
        recommended_action = "post_ladder_synthesis"
        reason = "recent trusted-source attempts reached the per-cycle retry budget"
        prevented_overrun = True
    evaluation = {
        "schema_name": EXECUTION_BUDGET_GUARDRAIL_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "budget_guardrail_evaluation_id": "",
        "baseline_action": baseline_action,
        "recommended_action": recommended_action,
        "budget_decision": budget_decision,
        "budget_reason": reason,
        "prevented_budget_overrun": prevented_overrun,
        "memory_band": memory_band,
        "repeated_action_count": repeated_action_count,
        "equivalent_action_repeat_count": equivalent_repeat_count,
        "repeated_action_threshold": 4,
        "adaptive_hook_repeat_count": hook_repeat_count,
        "adaptive_hook_repeat_threshold": repeat_threshold,
        "trusted_source_attempt_count": trusted_source_attempt_count,
        "trusted_source_attempt_threshold": TRUSTED_SOURCE_SYNTHESIS_MAX_ATTEMPTS,
        "max_operation_runtime_seconds": max_operation_seconds,
        "authority_boundary": "state-only deterministic planner guardrail; cannot bypass governed readiness, board, broker, canary, rollback, emergency stop, memory pressure, or trusted-source gates",
    }
    evaluation["budget_guardrail_evaluation_id"] = _record_id("budget", evaluation)
    if not persist:
        return _redact_autonomy_value(evaluation)
    record = _append_ledger(operator_root, "execution_budget_guardrail_evaluations", evaluation)
    _write_json(autonomy_root(operator_root) / "execution_budget_guardrail_latest.json", record)
    return record


def _trusted_source_literature_role_signal(role_profile: Mapping[str, Any]) -> tuple[bool, str]:
    profile_text = _compact_json(
        {
            "assigned_role": str(role_profile.get("assigned_role", "")),
            "inferred_mission_domain": str(role_profile.get("inferred_mission_domain", "")),
            "current_specialization_thesis": str(role_profile.get("current_specialization_thesis", "")),
            "missing_skills": list(role_profile.get("missing_skills", []) or []),
            "trusted_knowledge_gaps": list(role_profile.get("trusted_knowledge_gaps", []) or []),
            "next_learning_pressure": str(role_profile.get("next_learning_pressure", "")),
        }
    ).lower()
    has_trusted_source = any(
        fragment in profile_text
        for fragment in ("trusted-source", "trusted source", "trusted", "external", "openai")
    )
    has_literature_domain = any(
        fragment in profile_text
        for fragment in ("literature", "citation", "citations", "domain", "knowledge", "source", "synthesis")
    )
    if has_trusted_source and has_literature_domain:
        return True, "role profile requests trusted-source/domain literature synthesis"
    return False, "role profile does not request trusted-source/domain literature synthesis"


def _recent_adaptive_learning_pressure(
    operator_root: str | Path,
    *,
    window: int = TRUSTED_SOURCE_TRIAGE_ADAPTIVE_WINDOW,
    threshold: int = TRUSTED_SOURCE_TRIAGE_ADAPTIVE_THRESHOLD,
) -> dict[str, Any]:
    rows = list(_read_ledger(operator_root, "operation_results", limit=window))
    adaptive_count = len(
        [
            row
            for row in rows
            if str(row.get("action", "")) == "adaptive_learning_synthesis"
            and str(row.get("status", "")) == "completed"
        ]
    )
    return {
        "recent_adaptive_count": adaptive_count,
        "recent_window_size": window,
        "recent_observed_count": len(rows),
        "recent_adaptive_threshold": threshold,
        "recent_adaptive_majority": adaptive_count >= threshold,
    }


def _recent_governed_continuation_triage_cadence(
    operator_root: str | Path,
    latest_digest: Mapping[str, Any],
    *,
    threshold: int = TRUSTED_SOURCE_TRIAGE_GOVERNED_CONTINUATION_THRESHOLD,
) -> dict[str, Any]:
    digest_cutoff = _record_created_at(latest_digest)
    rows = list(_read_ledger(operator_root, "operation_results", limit=500))
    governed_rows = [
        row
        for row in rows
        if str(row.get("action", "")) == "governed_start_next_invocation"
        and str(row.get("status", "")) == "completed"
        and _after_created_at(row, digest_cutoff)
    ]
    latest_governed = governed_rows[-1] if governed_rows else {}
    return {
        "governed_continuation_count": len(governed_rows),
        "governed_continuation_threshold": threshold,
        "governed_continuation_cadence_due": len(governed_rows) >= threshold,
        "governed_continuation_latest_result_id": str(
            latest_governed.get("operation_result_id", "")
        ),
        "governed_continuation_digest_cutoff": (
            digest_cutoff.isoformat() if digest_cutoff is not None else ""
        ),
    }


def _operation_result_details_text(row: Mapping[str, Any]) -> str:
    result = dict(row.get("result", {}) or {})
    details = result.get("details", [])
    if isinstance(details, list):
        return "\n".join(str(item) for item in details)
    return str(details or "")


def _operation_result_has_directive_outcome(row: Mapping[str, Any]) -> bool:
    text = _operation_result_details_text(row)
    result = dict(row.get("result", {}) or {})
    return (
        "Directive outcome artifact:" in text
        or "Implementation bundle: directive_outcome_packet" in text
        or "Directive track advanced:" in text
        or bool(str(result.get("directive_outcome_artifact_path", "")).strip())
        or bool(str(result.get("selected_directive_track_id", "")).strip())
    )


def _recent_governed_directive_outcome_cadence(
    operator_root: str | Path,
    *,
    threshold: int = DIRECTIVE_OUTCOME_NUDGE_INTERVAL,
) -> dict[str, Any]:
    rows = list(_read_ledger(operator_root, "operation_results", limit=500))
    count = 0
    latest_result_id = ""
    latest_directive_outcome_result_id = ""
    for row in reversed(rows):
        if str(row.get("action", "")) != "governed_start_next_invocation":
            continue
        if str(row.get("status", "")) != "completed":
            continue
        if _operation_result_has_directive_outcome(row):
            latest_directive_outcome_result_id = str(row.get("operation_result_id", ""))
            break
        count += 1
        if not latest_result_id:
            latest_result_id = str(row.get("operation_result_id", ""))
    return {
        "framework_invocations_since_directive_outcome": count,
        "directive_outcome_nudge_interval": threshold,
        "directive_outcome_nudge_due": count >= threshold,
        "latest_governed_operation_result_id": latest_result_id,
        "latest_directive_outcome_operation_result_id": latest_directive_outcome_result_id,
    }


def _trusted_source_literature_triage_priority(
    operator_root: str | Path,
    *,
    growth_requested: bool,
) -> dict[str, Any]:
    readiness = _trusted_source_readiness(operator_root)
    role_profile = _latest(operator_root, "role_specialization_profiles")
    role_signal, role_reason = _trusted_source_literature_role_signal(role_profile)
    pressure = _recent_adaptive_learning_pressure(operator_root)
    latest_digest = _latest(operator_root, "trusted_source_literature_triage_digests")
    if not latest_digest:
        digest_rows = _read_ledger(operator_root, "trusted_source_literature_triage_digests", limit=1)
        latest_digest = dict(digest_rows[-1]) if digest_rows else {}
    governed_cadence = _recent_governed_continuation_triage_cadence(
        operator_root,
        latest_digest,
    )
    latest_adaptive = _latest(operator_root, "adaptive_learning_syntheses")
    latest_synthesis = _latest(operator_root, "post_ladder_syntheses")
    latest_learning_gap = str(latest_adaptive.get("next_capability_gap_proposal", ""))
    latest_frontier_gap = str(latest_synthesis.get("next_capability_gap_proposal", ""))
    digest_learning_gap = str(latest_digest.get("learning_gap_id", ""))
    digest_frontier_gap = str(latest_digest.get("frontier_gap_id", ""))
    redacted_latest_learning_gap = str(_redact_autonomy_value(latest_learning_gap))
    redacted_latest_frontier_gap = str(_redact_autonomy_value(latest_frontier_gap))
    duplicate_completed_digest = bool(
        str(latest_digest.get("status", "")) == "completed"
        and not bool(governed_cadence.get("governed_continuation_cadence_due", False))
        and (
            (
                latest_learning_gap
                and digest_learning_gap
                and digest_learning_gap in {latest_learning_gap, redacted_latest_learning_gap}
            )
            or (
                latest_frontier_gap
                and digest_frontier_gap
                and digest_frontier_gap in {latest_frontier_gap, redacted_latest_frontier_gap}
            )
        )
    )
    blocker = ""
    cadence_due = bool(governed_cadence.get("governed_continuation_cadence_due", False))
    if not growth_requested and not cadence_due:
        blocker = (
            "growth pivot or promotion-packet remediation is not active and "
            "trusted-source triage governed-continuation cadence is not due"
        )
    elif not bool(readiness.get("ready", False)):
        blocker = str(readiness.get("blocker", "") or "openai_api trusted source is not ready")
    elif not role_signal:
        blocker = role_reason
    elif not bool(pressure.get("recent_adaptive_majority", False)) and not cadence_due:
        blocker = (
            f"recent adaptive-learning completions are "
            f"{pressure['recent_adaptive_count']}/{pressure['recent_window_size']}, "
            f"below threshold {pressure['recent_adaptive_threshold']} and "
            f"governed continuation cadence is "
            f"{governed_cadence['governed_continuation_count']}/"
            f"{governed_cadence['governed_continuation_threshold']}"
        )
    elif duplicate_completed_digest:
        blocker = "completed triage digest already covers the latest learning or frontier gap"
    eligible = not blocker
    return {
        "trusted_source_triage_priority_status": "eligible" if eligible else "blocked",
        "trusted_source_triage_priority_reason": (
            "trusted-source triage scheduled after governed continuation cadence"
            if eligible and cadence_due
            else "trusted-source triage should preempt repeated adaptive learning"
            if eligible
            else blocker
        ),
        "trusted_source_triage_priority_blocker": blocker,
        "trusted_source_triage_role_signal": role_signal,
        "trusted_source_triage_role_reason": role_reason,
        "trusted_source_triage_recent_adaptive_count": int(pressure["recent_adaptive_count"]),
        "trusted_source_triage_recent_window_size": int(pressure["recent_window_size"]),
        "trusted_source_triage_recent_observed_count": int(pressure["recent_observed_count"]),
        "trusted_source_triage_recent_threshold": int(pressure["recent_adaptive_threshold"]),
        "trusted_source_triage_governed_continuation_count": int(
            governed_cadence["governed_continuation_count"]
        ),
        "trusted_source_triage_governed_continuation_threshold": int(
            governed_cadence["governed_continuation_threshold"]
        ),
        "trusted_source_triage_governed_continuation_cadence_due": cadence_due,
        "trusted_source_triage_governed_continuation_latest_result_id": str(
            governed_cadence.get("governed_continuation_latest_result_id", "")
        ),
        "trusted_source_triage_provider_ready": bool(readiness.get("ready", False)),
        "trusted_source_triage_provider_id": TRUSTED_SOURCE_EXTERNAL_PROVIDER_ID,
        "trusted_source_triage_provider_blocker": str(readiness.get("blocker", "")),
        "trusted_source_triage_latest_learning_gap": latest_learning_gap,
        "trusted_source_triage_latest_frontier_gap": latest_frontier_gap,
        "trusted_source_triage_duplicate_completed_digest": duplicate_completed_digest,
    }


def _trusted_source_literature_triage_needed(
    operator_root: str | Path,
    *,
    growth_requested: bool,
) -> bool:
    if not growth_requested:
        return False
    priority = _trusted_source_literature_triage_priority(
        operator_root,
        growth_requested=growth_requested,
    )
    return str(priority.get("trusted_source_triage_priority_status", "")) == "eligible"


def _safe_relative_ref_value(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if (
        not text
        or text.startswith("/")
        or text.startswith("\\")
        or (len(text) > 2 and text[1] == ":" and text[2] in {"/", "\\"})
        or ".." in Path(text).parts
    ):
        return ""
    return text[:240]


def _latest_directive_dossier_librarian_gap(
    operator_root: str | Path,
) -> dict[str, Any]:
    rows = list(reversed(_read_ledger(operator_root, "operation_results", limit=25)))
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        result = row.get("result", {})
        if not isinstance(result, Mapping):
            result = row
        if str(result.get("librarian_gap_reuse_decision", "")) != "no_reusable_pack":
            continue
        if str(result.get("librarian_gap_state", "")) in {
            "local_pack_staged",
            "satisfied",
        }:
            continue
        if not bool(result.get("directive_dossier_materially_new", False)):
            continue
        signature = str(result.get("librarian_gap_signature", "") or "").strip()
        if not signature:
            signature = _short_ref(
                "|".join(
                    [
                        str(result.get("directive_dossier_signature", "")),
                        str(result.get("selected_deliverable_kind", "")),
                        str(result.get("delta_focus_id", "")),
                        str(result.get("delta_layer_id", "")),
                    ]
                ),
                prefix="gap",
                length=16,
            )
        requested_family = str(
            result.get("requested_pack_family")
            or result.get("selected_deliverable_kind")
            or "directive_dossier_gap"
        ).strip()
        tags = [
            str(item).strip()
            for item in list(result.get("requested_tags", []) or [])
            if str(item).strip()
        ]
        for value in (
            result.get("selected_deliverable_kind", ""),
            result.get("delta_focus_id", ""),
            result.get("delta_layer_id", ""),
        ):
            text = str(value or "").strip()
            if text and text not in tags:
                tags.append(text)
        return {
            "directive_dossier_gap": True,
            "librarian_gap_request_id": str(
                result.get("librarian_gap_request_id") or f"librarian-gap-{signature}"
            ),
            "librarian_gap_signature": signature,
            "requested_gap_ref": "|".join([requested_family, *tags[:3]]) or signature,
            "requested_pack_family": requested_family,
            "requested_tags": tags[:12],
            "source_dossier_ref": _safe_relative_ref_value(
                result.get("source_dossier_ref")
                or result.get("latest_directive_dossier_ref")
                or result.get("directive_dossier_artifact_relative_path")
            ),
            "source_coverage_state": str(result.get("directive_source_coverage_state", "")),
            "operation_result_id": str(row.get("operation_result_id", "")),
        }
    return {}


def _librarian_gap_request(
    operator_root: str | Path,
    *,
    state_root: str | Path | None,
    role_profile: Mapping[str, Any],
    trusted_source_priority: Mapping[str, Any],
    trusted_source_unattended_enabled: bool,
    persist: bool = False,
) -> dict[str, Any]:
    if not state_root:
        return {
            "librarian_gap_request": False,
            "librarian_gap_reuse_decision": "state_root_unavailable",
            "librarian_gap_blocker": "state root is unavailable",
        }
    directive_gap = _latest_directive_dossier_librarian_gap(operator_root)
    role_signal = bool(trusted_source_priority.get("trusted_source_triage_role_signal", False))
    provider_ready = bool(trusted_source_priority.get("trusted_source_triage_provider_ready", False))
    requested_gap = str(directive_gap.get("requested_gap_ref", "") or "").strip() or (
        str((list(role_profile.get("trusted_knowledge_gaps", []) or [""]) or [""])[0])
        or str(role_profile.get("next_learning_pressure", ""))
        or "trusted_source_literature_gap"
    )
    requested_family = str(directive_gap.get("requested_pack_family", "") or "").strip()
    requested_tags = [
        str(item).strip()
        for item in list(directive_gap.get("requested_tags", []) or [])
        if str(item).strip()
    ]
    try:
        from .librarian import explain_librarian_reuse

        reuse_candidates = []
        if requested_family:
            for tag in requested_tags or [requested_gap]:
                reuse_candidates.append(
                    explain_librarian_reuse(
                        state_root,
                        kind="knowledge_pack",
                        family=requested_family,
                        tag=tag,
                    )
                )
        reuse_candidates.append(
            explain_librarian_reuse(
                state_root,
                kind="knowledge_pack",
                tag=requested_gap,
            )
        )
        reuse = next(
            (item for item in reuse_candidates if bool(item.get("reusable", False))),
            reuse_candidates[0] if reuse_candidates else {},
        )
    except Exception as exc:
        reuse = {
            "reuse_decision": "librarian_lookup_failed",
            "blockers": [type(exc).__name__],
        }
    reuse_decision = str(reuse.get("reuse_decision", "no_reusable_pack") or "no_reusable_pack")
    reusable = bool(reuse.get("reusable", False))
    blockers = list(reuse.get("blockers", []) or [])
    directive_gap_signal = bool(directive_gap.get("directive_dossier_gap", False))
    request_active = (
        not reusable
        and (role_signal or directive_gap_signal)
        and provider_ready
        and bool(trusted_source_unattended_enabled)
    )
    blocker = ""
    if reusable:
        blocker = "reusable_librarian_pack_available"
    elif not (role_signal or directive_gap_signal):
        blocker = str(trusted_source_priority.get("trusted_source_triage_role_reason", "")) or "role has no trusted-source gap"
    elif not provider_ready:
        blocker = str(trusted_source_priority.get("trusted_source_triage_provider_blocker", "")) or "trusted source provider is not ready"
    elif not trusted_source_unattended_enabled:
        blocker = "trusted-source unattended high-impact opt-in is not active"
    elif blockers:
        blocker = str(blockers[0])
    request = {
        "schema_name": LIBRARIAN_GAP_REQUEST_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "librarian_gap_request_id": "",
        "librarian_gap_request": request_active,
        "action": "trusted_source_literature_triage_digest",
        "requested_pack_kind": "knowledge_pack",
        "requested_gap_ref": _short_ref(requested_gap),
        "requested_pack_family": requested_family,
        "requested_tags": requested_tags[:12],
        "reuse_decision": reuse_decision,
        "reuse_blockers": [str(item) for item in blockers[:4]],
        "blocker": blocker,
        "source": "directive_dossier" if directive_gap_signal else "librarian",
        "directive_dossier_gap": directive_gap_signal,
        "librarian_gap_signature": str(directive_gap.get("librarian_gap_signature", "")),
        "source_dossier_ref": str(directive_gap.get("source_dossier_ref", "")),
        "source_coverage_state": str(directive_gap.get("source_coverage_state", "")),
        "librarian_gap_state": (
            "trusted_source_requested" if request_active else "open" if directive_gap_signal else ""
        ),
        "provider_ready": provider_ready,
        "trusted_source_unattended_enabled": bool(trusted_source_unattended_enabled),
        "grants_execution_authority": False,
    }
    if directive_gap.get("librarian_gap_request_id"):
        request["librarian_gap_request_id"] = str(directive_gap.get("librarian_gap_request_id", ""))
    else:
        request["librarian_gap_request_id"] = _record_id("librarian-gap", request)
    if persist and request_active:
        request = _append_ledger(operator_root, "librarian_gap_requests", request)
    return request


def _apply_capability_planner_hooks(
    *,
    operator_root: str | Path,
    baseline_action: str,
    memory_band: str,
    novelty_preview: Mapping[str, Any],
    growth_pivot: bool,
    safe_growth_available: bool,
    synthesis_needed: bool,
    adaptive_needed: bool,
    governed_ready: bool,
    directive_loaded: bool,
    adaptive_backoff_status: str = "",
    adaptive_hook_stall: Mapping[str, Any] | None = None,
    budget_guardrail: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    hooks = _load_promoted_capability_hooks(operator_root)
    fingerprint = _planner_hook_fingerprint(
        baseline_action=baseline_action,
        memory_band=memory_band,
        novelty_preview=novelty_preview,
        growth_pivot=growth_pivot,
        safe_growth_available=safe_growth_available,
        synthesis_needed=synthesis_needed,
        adaptive_needed=adaptive_needed,
        adaptive_backoff_status=adaptive_backoff_status,
    )
    budget = dict(budget_guardrail or {})
    budget_decision = str(budget.get("budget_decision", "continue"))
    budget_recommended_action = str(budget.get("recommended_action", ""))
    final_action = (
        budget_recommended_action
        if budget_decision != "continue" and budget_recommended_action
        else baseline_action
    )
    consumed: list[str] = []
    hook_refs: list[str] = []
    contract_ids: list[str] = []
    adapter_ids: list[str] = []
    adapter_behaviors: list[str] = []
    reasons: list[str] = []
    suppressed: list[str] = []
    failure_prevented = False
    hook_stall = dict(adaptive_hook_stall or {})
    hook_stalled = str(hook_stall.get("hook_stall_status", "")) == "stalled"
    hook_stall_pivot = str(hook_stall.get("pivot_action", ""))
    hook_stall_reason = str(hook_stall.get("reason", ""))
    governed_recovery_available = bool(hook_stall.get("governed_stale_recovery_available", False))

    selected_capability = str(novelty_preview.get("selected_capability_kind", "") or "").strip()
    recent_same_action = _recent_same_action_rows(
        operator_root,
        action=baseline_action,
        capability_kind=selected_capability,
    )
    latest_meaningful = _latest(operator_root, "meaningful_work_evaluations")
    latest_usefulness = _latest(operator_root, "capability_usefulness_evaluations")
    weak_areas = " ".join(str(item) for item in list(latest_meaningful.get("weak_areas", []) or []))
    promotion_packet_missing = "missing promotion packet" in weak_areas.lower()

    def consume(hook: Mapping[str, Any], reason: str) -> None:
        kind = str(hook.get("capability_kind", ""))
        ref = str(hook.get("hook_type", ""))
        if kind and kind not in consumed:
            consumed.append(kind)
        if ref and ref not in hook_refs:
            hook_refs.append(ref)
        contract_id = str(hook.get("capability_consumption_contract_id", ""))
        adapter_id = str(hook.get("runtime_capability_adapter_id", ""))
        adapter_behavior = str(hook.get("adapter_behavior", ""))
        if contract_id and contract_id not in contract_ids:
            contract_ids.append(contract_id)
        if adapter_id and adapter_id not in adapter_ids:
            adapter_ids.append(adapter_id)
        if adapter_behavior and adapter_behavior not in adapter_behaviors:
            adapter_behaviors.append(adapter_behavior)
        if reason and reason not in reasons:
            reasons.append(reason)

    def _stall_preferred_action(default_preferred: str) -> str:
        return hook_stall_pivot if hook_stalled and hook_stall_pivot else default_preferred

    def _stall_reason(default_reason: str) -> str:
        if hook_stalled and hook_stall_reason:
            return f"{default_reason}; {hook_stall_reason}"
        return default_reason

    for hook in hooks:
        hook_type = str(hook.get("hook_type", ""))
        if hook_type == "execution_budget_guardrails" and budget_decision != "continue":
            consume(hook, str(budget.get("budget_reason", "")))
            if bool(budget.get("prevented_budget_overrun", False)):
                failure_prevented = True
            final_action = _safe_hook_target(
                preferred=budget_recommended_action or final_action,
                baseline_action=final_action,
                memory_band=memory_band,
                synthesis_needed=synthesis_needed,
                adaptive_needed=adaptive_needed,
                safe_growth_available=safe_growth_available,
                governed_ready=governed_ready,
                directive_loaded=directive_loaded,
                growth_pivot=growth_pivot,
                adaptive_backoff_status=adaptive_backoff_status,
                adaptive_hook_stalled=True,
                governed_recovery_available=governed_recovery_available,
            )
        elif hook_type == "budget_aware_throttling" and memory_band in {"warning", "action", "critical"}:
            consume(hook, f"memory pressure band {memory_band} requires throttled planning")
            preferred = "memory_ledger_compaction" if memory_band in {"warning", "action", "critical"} else final_action
            final_action = _safe_hook_target(
                preferred=preferred,
                baseline_action=final_action,
                memory_band=memory_band,
                synthesis_needed=synthesis_needed,
                adaptive_needed=adaptive_needed,
                safe_growth_available=safe_growth_available,
                governed_ready=governed_ready,
                directive_loaded=directive_loaded,
                growth_pivot=growth_pivot,
                adaptive_backoff_status=adaptive_backoff_status,
                adaptive_hook_stalled=hook_stalled,
                governed_recovery_available=governed_recovery_available,
            )
        elif hook_type == "tool_failure_classifier":
            failed_rows = [row for row in recent_same_action if _operation_failed_or_warned(row)]
            if failed_rows:
                consume(hook, f"recent {baseline_action} failure or timeout observed")
                failure_prevented = True
                suppressed.append(baseline_action)
                final_action = _safe_hook_target(
                    preferred="post_ladder_synthesis" if safe_growth_available else "novali_stack_status",
                    baseline_action=final_action,
                    memory_band=memory_band,
                    synthesis_needed=synthesis_needed,
                    adaptive_needed=adaptive_needed,
                    safe_growth_available=safe_growth_available,
                    governed_ready=governed_ready,
                    directive_loaded=directive_loaded,
                    growth_pivot=growth_pivot,
                    adaptive_backoff_status=adaptive_backoff_status,
                    adaptive_hook_stalled=hook_stalled,
                    governed_recovery_available=governed_recovery_available,
                )
        elif (
            hook_type == "idempotent_tool_invocation_ledger"
            and baseline_action != "governed_start_next_invocation"
            and recent_same_action
        ):
            completed_rows = [row for row in recent_same_action if str(row.get("status", "")) == "completed"]
            if completed_rows:
                consume(hook, f"equivalent {baseline_action} already completed recently")
                suppressed.append(baseline_action)
                final_action = _safe_hook_target(
                    preferred="post_ladder_synthesis" if safe_growth_available else "novali_stack_status",
                    baseline_action=final_action,
                    memory_band=memory_band,
                    synthesis_needed=synthesis_needed,
                    adaptive_needed=adaptive_needed,
                    safe_growth_available=safe_growth_available,
                    governed_ready=governed_ready,
                    directive_loaded=directive_loaded,
                    growth_pivot=growth_pivot,
                    adaptive_backoff_status=adaptive_backoff_status,
                    adaptive_hook_stalled=hook_stalled,
                    governed_recovery_available=governed_recovery_available,
                )
        elif hook_type == "dependency_fingerprint_cache" and _latest_hook_fingerprint_seen(operator_root, fingerprint):
            consume(hook, _stall_reason("planner input fingerprint matches a recent planning cycle"))
            suppressed.append("duplicate_planner_fingerprint")
            if hook_stalled:
                suppressed.append("adaptive_learning_hook_stall")
            if (
                baseline_action == "promote_self_modification_candidate"
                and safe_growth_available
                and promotion_packet_missing
            ):
                suppressed.append(
                    "duplicate_planner_fingerprint_yielded_to_promotion_packet"
                )
                final_action = baseline_action
            else:
                final_action = _safe_hook_target(
                    preferred=_stall_preferred_action(
                        "post_ladder_synthesis" if safe_growth_available else "novali_stack_status"
                    ),
                    baseline_action=final_action,
                    memory_band=memory_band,
                    synthesis_needed=synthesis_needed,
                    adaptive_needed=adaptive_needed,
                    safe_growth_available=safe_growth_available,
                    governed_ready=governed_ready,
                    directive_loaded=directive_loaded,
                    growth_pivot=growth_pivot,
                    adaptive_backoff_status=adaptive_backoff_status,
                    adaptive_hook_stalled=hook_stalled,
                    governed_recovery_available=governed_recovery_available,
                )
        elif hook_type == "goal_drift_guardrails":
            usefulness_stalled = str(latest_usefulness.get("usefulness", "")) in {
                "evidence_only",
                "dormant",
                "needs_followup",
            }
            repeated_signal = "repeated signal signature" in weak_areas
            if usefulness_stalled or repeated_signal:
                consume(hook, _stall_reason("recent growth evidence suggests goal drift or unproven capability usefulness"))
                preferred = (
                    "adaptive_learning_synthesis"
                    if usefulness_stalled
                    else "post_ladder_synthesis"
                )
                if hook_stalled:
                    suppressed.append("adaptive_learning_hook_stall")
                final_action = _safe_hook_target(
                    preferred=_stall_preferred_action(preferred),
                    baseline_action=final_action,
                    memory_band=memory_band,
                    synthesis_needed=synthesis_needed,
                    adaptive_needed=adaptive_needed,
                    safe_growth_available=safe_growth_available,
                    governed_ready=governed_ready,
                    directive_loaded=directive_loaded,
                    growth_pivot=growth_pivot,
                    adaptive_backoff_status=adaptive_backoff_status,
                    adaptive_hook_stalled=hook_stalled,
                governed_recovery_available=governed_recovery_available,
            )

    if (
        baseline_action == "trusted_source_literature_triage_digest"
        and budget_decision == "continue"
    ):
        final_action = baseline_action

    changed = final_action != baseline_action
    event_seed = {
        "capability_kind": consumed[0] if consumed else "",
        "consumed_capability_kinds": consumed,
        "baseline_action": baseline_action,
        "final_action": final_action,
        "decision_changed_by_capability": changed,
        "planner_hook_references": hook_refs,
        "input_fingerprint": fingerprint,
    }
    return {
        "schema_name": CAPABILITY_HOOK_CONSUMPTION_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "capability_hook_consumption_id": "",
        "capability_consumption_event_id": _record_id("consume", event_seed) if consumed else "",
        "consumed_capability_kinds": consumed,
        "explicitly_consumed_capability_kinds": consumed,
        "capability_consumption_contract_ids": contract_ids,
        "runtime_capability_adapter_ids": adapter_ids,
        "runtime_capability_adapter_behaviors": adapter_behaviors,
        "planner_hook_references": hook_refs,
        "runtime_hook_references": hook_refs,
        "baseline_action": baseline_action,
        "final_action": final_action,
        "decision_changed_by_capability": changed,
        "planner_hook_bias_applied": bool(consumed),
        "hook_reason": "; ".join(reasons),
        "input_fingerprint": fingerprint,
        "suppressed_actions": list(dict.fromkeys(suppressed)),
        "repeat_failure_prevented": failure_prevented,
        "budget_guardrail_evaluation_id": str(budget.get("budget_guardrail_evaluation_id", "")),
        "budget_decision": budget_decision,
        "budget_reason": str(budget.get("budget_reason", "")),
        "budget_recommended_action": budget_recommended_action,
        "budget_prevented_overrun": bool(budget.get("prevented_budget_overrun", False)),
        "operator_intervention_reduced": False,
        "adaptive_learning_hook_stall_id": str(
            hook_stall.get("adaptive_learning_hook_stall_id", "")
        ),
        "hook_stall_status": str(hook_stall.get("hook_stall_status", "")),
        "hook_stall_pivot_action": str(hook_stall.get("pivot_action", "")),
        "hook_stall_reason": str(hook_stall.get("reason", "")),
        "hook_stall_repeat_count": int(hook_stall.get("repeat_count", 0) or 0),
        "hook_stall_repeat_threshold": int(hook_stall.get("repeat_threshold", 0) or 0),
        "stalled_capability_kind": str(hook_stall.get("stalled_capability_kind", "")),
        "runtime_hook_adapter_gap_id": str(hook_stall.get("runtime_hook_adapter_gap_id", "")),
        "runtime_hook_adapter_behavior": str(hook_stall.get("runtime_hook_adapter_behavior", "")),
        "governed_stale_recovery_available": bool(
            hook_stall.get("governed_stale_recovery_available", False)
        ),
        "governed_recovery_checkpoint_id": str(
            hook_stall.get("governed_recovery_checkpoint_id", "")
        ),
        "safety_gates_preserved": [
            "emergency_stop",
            "governed_readiness",
            "trusted_source_readiness",
            "approval_board",
            "operation_broker",
            "canary",
            "rollback",
            "memory_pressure",
            "novelty_repeat_blocking",
        ],
        "loaded_hook_count": len(hooks),
        "recognized_hook_count": len(consumed),
    }


def _persist_capability_hook_consumption(
    operator_root: str | Path,
    consumption: Mapping[str, Any],
    *,
    plan_candidate_id: str = "",
    operation_id: str = "",
) -> dict[str, Any]:
    if not list(consumption.get("consumed_capability_kinds", []) or []):
        return {}
    payload = dict(consumption)
    payload["plan_candidate_id"] = plan_candidate_id
    payload["operation_id"] = operation_id
    if not str(payload.get("capability_hook_consumption_id", "")).strip():
        payload["capability_hook_consumption_id"] = _record_id("hook", payload)
    record = _append_ledger(operator_root, "capability_hook_consumptions", payload)
    _write_json(autonomy_root(operator_root) / "capability_hook_consumption_latest.json", record)
    return record


def _persist_capability_consumption_event(
    operator_root: str | Path,
    consumption: Mapping[str, Any],
    *,
    plan_candidate_id: str = "",
    operation_id: str = "",
) -> dict[str, Any]:
    consumed = [
        str(item).strip()
        for item in list(consumption.get("consumed_capability_kinds", []) or [])
        if str(item).strip()
    ]
    if not consumed:
        return {}
    event = {
        "schema_name": CAPABILITY_CONSUMPTION_EVENT_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "capability_consumption_event_id": str(
            consumption.get("capability_consumption_event_id", "")
        ),
        "capability_hook_consumption_id": str(
            consumption.get("capability_hook_consumption_id", "")
        ),
        "plan_candidate_id": plan_candidate_id,
        "operation_id": operation_id,
        "entrypoint": "autonomy_planner",
        "capability_kind": consumed[0],
        "consumed_capability_kinds": consumed,
        "explicitly_consumed_capability_kinds": consumed,
        "capability_consumption_contract_ids": list(
            consumption.get("capability_consumption_contract_ids", []) or []
        ),
        "runtime_capability_adapter_ids": list(
            consumption.get("runtime_capability_adapter_ids", []) or []
        ),
        "runtime_capability_adapter_behaviors": list(
            consumption.get("runtime_capability_adapter_behaviors", []) or []
        ),
        "planner_hook_references": list(consumption.get("planner_hook_references", []) or []),
        "runtime_hook_references": list(consumption.get("runtime_hook_references", []) or []),
        "baseline_action": str(consumption.get("baseline_action", "")),
        "final_action": str(consumption.get("final_action", "")),
        "decision_changed_by_capability": bool(
            consumption.get("decision_changed_by_capability", False)
        ),
        "decision_delta": (
            "changed"
            if bool(consumption.get("decision_changed_by_capability", False))
            else "observed_no_change"
        ),
        "input_fingerprint": str(consumption.get("input_fingerprint", "")),
        "suppressed_actions": list(consumption.get("suppressed_actions", []) or []),
        "repeat_failure_prevented": bool(consumption.get("repeat_failure_prevented", False)),
        "budget_guardrail_evaluation_id": str(
            consumption.get("budget_guardrail_evaluation_id", "")
        ),
        "budget_decision": str(consumption.get("budget_decision", "")),
        "budget_reason": str(consumption.get("budget_reason", "")),
        "budget_prevented_overrun": bool(consumption.get("budget_prevented_overrun", False)),
        "operator_intervention_reduced": bool(
            consumption.get("operator_intervention_reduced", False)
        ),
        "directive_progress_effect": str(consumption.get("directive_progress_effect", "not_measured")),
        "recognized_runtime_hook_invocation": True,
        "hook_reason": str(consumption.get("hook_reason", "")),
        "safety_gates_preserved": list(consumption.get("safety_gates_preserved", []) or []),
    }
    if not event["capability_consumption_event_id"]:
        event["capability_consumption_event_id"] = _record_id("consume", event)
    record = _append_ledger(operator_root, "capability_consumption_events", event)
    _write_json(autonomy_root(operator_root) / "capability_consumption_event_latest.json", record)
    return record


def _used_capability_gap_ids(operator_root: str | Path) -> list[str]:
    used: list[str] = []
    for record in _read_ledger(operator_root, "promotion_results", limit=200):
        kind = _safe_synthesized_capability_gap(_promotion_capability_kind(record))
        if kind:
            used.append(kind)
    for record in _read_ledger(operator_root, "post_ladder_syntheses", limit=100):
        kind = _safe_synthesized_capability_gap(record.get("next_capability_gap_proposal", ""))
        if kind:
            used.append(kind)
    return list(dict.fromkeys(used))


def _candidate_gap(
    gap_id: str,
    *,
    title: str,
    reason: str,
    success_signal: str,
    risk_class: str = "bounded_state_capability_adoption",
    source: str = "deterministic",
) -> dict[str, str]:
    return {
        "gap_id": gap_id,
        "title": title,
        "reason": reason,
        "success_signal": success_signal,
        "risk_class": risk_class,
        "source": source,
    }


def _sanitize_gap_candidate(
    candidate: Mapping[str, Any],
    *,
    already_used: set[str],
) -> tuple[dict[str, str], str]:
    gap_id = _safe_synthesized_capability_gap(candidate.get("gap_id", ""))
    if not gap_id:
        return {}, "invalid_gap_id"
    if gap_id == BLOCKED_GROWTH_EVIDENCE_GAP_ID:
        return {}, "gap_not_promotable_blocked_evidence"
    if not gap_id.endswith("_v1"):
        return {}, "gap_id_must_end_with_v1"
    if gap_id in already_used:
        return {}, "gap_already_promoted_or_proposed"
    if not str(candidate.get("title", "")).strip():
        return {}, "missing_title"
    if not str(candidate.get("reason", "")).strip():
        return {}, "missing_reason"
    if not str(candidate.get("success_signal", "")).strip():
        return {}, "missing_success_signal"
    title = _truncate(candidate.get("title", gap_id.replace("_", " ")), 120)
    reason = _truncate(candidate.get("reason", "Evidence-backed capability gap proposal."), 320)
    success_signal = _truncate(
        candidate.get("success_signal", "A later promotion records tests, canary, rollback, and usefulness evidence."),
        240,
    )
    risk_class = str(candidate.get("risk_class", "bounded_state_capability_adoption")).strip()
    if risk_class not in {"bounded_state_capability_adoption", "read_only_state_synthesis"}:
        return {}, "invalid_risk_class"
    return (
        {
            "gap_id": gap_id,
            "title": title,
            "reason": reason,
            "success_signal": success_signal,
            "risk_class": risk_class,
            "source": str(candidate.get("source", "") or "deterministic"),
        },
        "",
    )


def _deterministic_frontier_candidates(
    *,
    capability_summaries: list[dict[str, Any]],
    meaningful_rows: list[dict[str, Any]],
    recent_operations: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], bool]:
    weak_text = " ".join(
        str(item)
        for row in meaningful_rows[:20]
        for item in list(dict(row).get("weak_areas", []) or [])
    ).lower()
    failed_actions = [
        str(row.get("action", ""))
        for row in recent_operations[:20]
        if str(row.get("status", "")) not in {"", "completed"}
    ]
    needs_followup = [
        str(item.get("capability_kind", ""))
        for item in capability_summaries
        if str(item.get("usefulness", "")) == "needs_followup"
    ]
    candidates: list[dict[str, str]] = []
    high_confidence = False
    if needs_followup:
        high_confidence = True
        candidates.append(
            _candidate_gap(
                f"{needs_followup[0]}_followup_v1",
                title=f"Follow up {needs_followup[0]}",
                reason="A promoted capability needs follow-up because canary or rollback evidence was not clean.",
                success_signal="The follow-up promotion records clean canary, rollback, and usefulness evidence.",
            )
        )
    if "repeated signal signature" in weak_text or "artifact churn" in weak_text:
        high_confidence = True
        candidates.append(
            _candidate_gap(
                "artifact_churn_resistance_v1",
                title="Artifact churn resistance",
                reason="Recent meaningful-work evidence flagged repeated signal signatures or artifact churn.",
                success_signal="A later cycle distinguishes repeated artifacts from real directive or capability deltas.",
            )
        )
    if "repeated promoted capability" in weak_text or "cooldown" in weak_text:
        high_confidence = True
        candidates.append(
            _candidate_gap(
                "promotion_repeat_resistance_v1",
                title="Promotion repeat resistance",
                reason="Recent evidence flagged repeated promoted capability kinds in novelty cooldown.",
                success_signal="A later cycle selects a genuinely new capability gap instead of a cooldown repeat.",
            )
        )
    if failed_actions:
        high_confidence = True
        candidates.append(
            _candidate_gap(
                "operation_failure_remediation_memory_v1",
                title="Operation failure remediation memory",
                reason="Recent operation results include failed or warning outcomes that should shape growth planning.",
                success_signal="A later cycle turns failed operation evidence into a bounded remediation objective.",
            )
        )
    candidates.extend(
        [
            _candidate_gap(
                "capability_usefulness_probe_v1",
                title="Capability usefulness probe",
                reason="Post-ladder synthesis needs a reusable way to tell which promoted capabilities are actually useful.",
                success_signal="The next synthesis can rank promoted capabilities by observed usefulness evidence.",
                source="fallback",
            ),
            _candidate_gap(
                "promotion_outcome_trend_memory_v1",
                title="Promotion outcome trend memory",
                reason="Promotion history should influence future gap selection instead of resetting to the base ladder.",
                success_signal="Recent promotion trends are summarized and used by a later novelty decision.",
                source="fallback",
            ),
            _candidate_gap(
                "autonomy_growth_frontier_planner_v1",
                title="Autonomy growth frontier planner",
                reason="Novali needs a bounded frontier planner for proposing new gap families after the configured ladder.",
                success_signal="The next post-ladder synthesis proposes a non-repeated frontier with clear evidence.",
                source="fallback",
            ),
        ]
    )
    return candidates, high_confidence


def _post_ladder_gap_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "gap_id": {
                "type": "string",
                "description": "snake_case id ending in _v1 for a Novali-owned state capability",
            },
            "title": {"type": "string"},
            "reason": {"type": "string"},
            "success_signal": {"type": "string"},
            "risk_class": {
                "type": "string",
                "enum": ["bounded_state_capability_adoption", "read_only_state_synthesis"],
            },
        },
        "required": ["gap_id", "title", "reason", "success_signal", "risk_class"],
    }


def _extract_openai_response_json(payload: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    structured, text = _extract_responses_structured_json(dict(payload))
    return (structured if isinstance(structured, dict) else None), text


def _extract_openai_response_json_with_outcome(
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str, str]:
    structured, text, parse_outcome = _extract_responses_structured_json_with_outcome(
        dict(payload)
    )
    return (structured if isinstance(structured, dict) else None), text, parse_outcome


def _trusted_source_readiness(operator_root: str | Path) -> dict[str, Any]:
    bindings = load_trusted_source_bindings_or_default(root=operator_root)
    secrets = load_trusted_source_secrets_or_default(operator_root)
    errors, _, availability = validate_trusted_source_bindings(bindings, secrets_payload=secrets)
    provider_id = TRUSTED_SOURCE_EXTERNAL_PROVIDER_ID
    row = next(
        (
            dict(item)
            for item in list(availability.get("sources", []) or [])
            if str(item.get("source_id", "")) == provider_id
        ),
        {},
    )
    credential_ref = str(row.get("credential_ref", "") or "OPENAI_API_KEY").strip()
    provider_status = load_trusted_source_provider_status(operator_root)
    credential_status = load_trusted_source_credential_status(operator_root)
    credential_value = str(os.environ.get(credential_ref, "")).strip()
    blocker = ""
    if errors:
        blocker = "; ".join(errors)
    elif not row:
        blocker = f"Binding not found for provider id {provider_id!r}."
    elif not bool(row.get("enabled", False)):
        blocker = "trusted source binding is disabled"
    elif not bool(row.get("ready_for_launch", False)):
        blocker = str(row.get("availability_reason", "") or "trusted source binding is not ready")
    elif not credential_value:
        blocker = "required environment credential is missing"
    ready = not blocker
    return {
        "provider_id": provider_id,
        "ready": ready,
        "blocker": blocker,
        "credential_ref": credential_ref,
        "credential_value": credential_value if ready else "",
        "endpoint_base": str(row.get("endpoint_base", "") or provider_status.get("endpoint_base", "") or TRUSTED_SOURCE_EXTERNAL_API_BASE_URL),
        "selected_model": str(provider_status.get("selected_model", "") or credential_status.get("selected_model", "") or TRUSTED_SOURCE_EXTERNAL_MODEL_PREFERENCE[0]),
        "credential_validation_state": str(credential_status.get("validation_state", "")),
        "provider_validation_state": str(provider_status.get("validation_state", "")),
    }


def _external_trusted_source_gap_proposal(
    *,
    operator_root: str | Path,
    context: Mapping[str, Any],
    already_used: set[str],
) -> tuple[dict[str, str], dict[str, Any]]:
    readiness = _trusted_source_readiness(operator_root)
    meta = {
        "trusted_source_provider_id": TRUSTED_SOURCE_EXTERNAL_PROVIDER_ID,
        "trusted_source_ready": bool(readiness.get("ready", False)),
        "trusted_source_blocker": str(readiness.get("blocker", "")),
        "trusted_source_model": str(readiness.get("selected_model", "")),
        "trusted_source_request_attempted": False,
        "trusted_source_response_status": "",
        "trusted_source_attempt_count": 0,
        "trusted_source_attempts": [],
        "trusted_source_failure_class": "",
    }
    if not bool(readiness.get("ready", False)):
        meta["trusted_source_failure_class"] = "readiness_blocked"
        return {}, meta
    base_prompt = (
        "You are an external trusted source helping Novali choose one new bounded capability gap. "
        "Return JSON only matching the provided schema. The gap must be a Novali-owned state capability, "
        "not a governance expansion, not a protected source-root write, and not a repeat of any used gap id. "
        "Use snake_case ending with _v1. Context JSON follows:\n"
        + _truncate(_json_dump(_redact_autonomy_value(dict(context))), 5000)
    )
    meta["trusted_source_request_attempted"] = True
    selected_model = str(readiness.get("selected_model", "") or TRUSTED_SOURCE_EXTERNAL_MODEL_PREFERENCE[0])
    retryable_candidate_rejections = {
        "missing_title",
        "missing_reason",
        "missing_success_signal",
        "invalid_risk_class",
    }
    attempts: list[dict[str, Any]] = []
    repair_note = ""
    for attempt_number in range(1, TRUSTED_SOURCE_SYNTHESIS_MAX_ATTEMPTS + 1):
        prompt = base_prompt
        if repair_note:
            prompt = (
                base_prompt
                + "\n\nPrevious attempt failed validation: "
                + repair_note
                + ". Repair the response by returning only valid JSON matching the schema."
            )
        payload = {
            "model": selected_model,
            "store": False,
            "input": prompt,
            "max_output_tokens": 240,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "novali_next_capability_gap",
                    "strict": True,
                    "schema": _post_ladder_gap_schema(),
                }
            },
        }
        attempt_meta: dict[str, Any] = {
            "attempt_number": attempt_number,
            "response_status": "",
            "failure_class": "",
            "candidate_gap_id": "",
        }
        try:
            status_code, response = _trusted_source_external_json_request(
                method="POST",
                endpoint="/responses",
                credential_value=str(readiness.get("credential_value", "")),
                endpoint_base=str(readiness.get("endpoint_base", "")),
                payload=payload,
                timeout_seconds=60,
            )
        except GovernedExecutionFailure as exc:
            attempt_meta["failure_class"] = "request_failed"
            attempt_meta["blocker"] = str(exc)
            attempts.append(attempt_meta)
            meta["trusted_source_blocker"] = str(exc)
            meta["trusted_source_ready"] = False
            break
        attempt_meta["response_status"] = str(status_code)
        meta["trusted_source_response_status"] = str(status_code)
        if status_code != 200:
            attempt_meta["failure_class"] = "http_status"
            attempt_meta["blocker"] = f"external trusted-source request returned status {status_code}"
            attempts.append(attempt_meta)
            meta["trusted_source_blocker"] = str(attempt_meta["blocker"])
            break
        structured, _ = _extract_openai_response_json(response)
        if not isinstance(structured, dict):
            attempt_meta["failure_class"] = "malformed_json"
            attempt_meta["blocker"] = "external trusted-source response was not structured JSON"
            attempts.append(attempt_meta)
            meta["trusted_source_blocker"] = str(attempt_meta["blocker"])
            repair_note = "malformed_json"
            if attempt_number < TRUSTED_SOURCE_SYNTHESIS_MAX_ATTEMPTS:
                continue
            break
        attempt_meta["candidate_gap_id"] = str(structured.get("gap_id", ""))
        candidate, reason = _sanitize_gap_candidate(
            {**structured, "source": "external_trusted_source"},
            already_used=already_used,
        )
        if reason:
            attempt_meta["failure_class"] = "candidate_rejected"
            attempt_meta["rejection_reason"] = reason
            attempt_meta["blocker"] = f"external trusted-source candidate rejected: {reason}"
            attempts.append(attempt_meta)
            meta["trusted_source_blocker"] = str(attempt_meta["blocker"])
            if reason in retryable_candidate_rejections and attempt_number < TRUSTED_SOURCE_SYNTHESIS_MAX_ATTEMPTS:
                repair_note = reason
                continue
            break
        attempt_meta["failure_class"] = ""
        attempt_meta["accepted"] = True
        attempts.append(attempt_meta)
        meta["trusted_source_attempts"] = attempts
        meta["trusted_source_attempt_count"] = len(attempts)
        meta["trusted_source_failure_class"] = ""
        meta["trusted_source_blocker"] = ""
        return candidate, meta
    meta["trusted_source_attempts"] = attempts
    meta["trusted_source_attempt_count"] = len(attempts)
    if attempts:
        meta["trusted_source_failure_class"] = str(attempts[-1].get("failure_class", ""))
    return {}, meta


def _select_next_frontier_gap(
    *,
    operator_root: str | Path,
    capability_summaries: list[dict[str, Any]],
    meaningful_rows: list[dict[str, Any]],
    recent_operations: list[dict[str, Any]],
) -> dict[str, Any]:
    already_used = set(_used_capability_gap_ids(operator_root))
    candidates, high_confidence = _deterministic_frontier_candidates(
        capability_summaries=capability_summaries,
        meaningful_rows=meaningful_rows,
        recent_operations=recent_operations,
    )
    rejected: list[dict[str, str]] = []
    for candidate in candidates:
        sanitized, reason = _sanitize_gap_candidate(candidate, already_used=already_used)
        if sanitized and (high_confidence or sanitized.get("source") != "fallback"):
            return {
                "candidate": sanitized,
                "next_gap_source": "deterministic",
                "proposal_reason": sanitized["reason"],
                "rejected_gap_candidates": rejected,
                "already_promoted_gap_ids": sorted(already_used),
                "trusted_source": {},
            }
        rejected.append({"candidate_gap_id": str(candidate.get("gap_id", "")), "reason": reason or "low_signal_fallback_candidate"})
    external_context = {
        "promoted_capabilities": capability_summaries[:20],
        "recent_meaningful_weak_areas": [
            str(item)
            for row in meaningful_rows[:20]
            for item in list(dict(row).get("weak_areas", []) or [])
        ],
        "recent_operations": [
            {
                "action": str(row.get("action", "")),
                "status": str(row.get("status", "")),
                "capability_kind": str(row.get("capability_kind", "")),
            }
            for row in recent_operations[:20]
        ],
        "already_used_gap_ids": sorted(already_used),
    }
    external_candidate, trusted_meta = _external_trusted_source_gap_proposal(
        operator_root=operator_root,
        context=external_context,
        already_used=already_used,
    )
    if external_candidate:
        return {
            "candidate": external_candidate,
            "next_gap_source": "external_trusted_source",
            "proposal_reason": external_candidate["reason"],
            "rejected_gap_candidates": rejected,
            "already_promoted_gap_ids": sorted(already_used),
            "trusted_source": trusted_meta,
        }
    for candidate in candidates:
        sanitized, reason = _sanitize_gap_candidate(candidate, already_used=already_used)
        if sanitized:
            return {
                "candidate": sanitized,
                "next_gap_source": "fallback",
                "proposal_reason": sanitized["reason"],
                "rejected_gap_candidates": rejected,
                "already_promoted_gap_ids": sorted(already_used),
                "trusted_source": trusted_meta,
            }
    fallback = _candidate_gap(
        BLOCKED_GROWTH_EVIDENCE_GAP_ID,
        title="Autonomy growth blocked evidence",
        reason="No non-repeated bounded capability gap could be derived from current evidence.",
        success_signal="A later cycle records why growth is blocked without repeating a promoted gap.",
        source="fallback",
    )
    return {
        "candidate": fallback,
        "next_gap_source": "fallback",
        "proposal_reason": fallback["reason"],
        "rejected_gap_candidates": rejected,
        "already_promoted_gap_ids": sorted(already_used),
        "trusted_source": trusted_meta,
    }


def _capability_novelty_evaluation(
    operator_root: str | Path,
    *,
    requested_capability_kind: str = "",
    explicit_remediation_reason: str = "",
    persist: bool = True,
) -> dict[str, Any]:
    charter = load_autonomy_charter(operator_root)
    policy = dict(charter.get("novelty_policy", {}) or {})
    enabled = bool(policy.get("enabled", True))
    priority_order = _effective_capability_gap_priority_order(operator_root, policy)
    requested = requested_capability_kind if requested_capability_kind in priority_order else priority_order[0]
    memory_window = int(policy.get("recent_capability_memory_window", 12) or 12)
    cooldown_cycles = int(policy.get("repeated_promoted_kind_cooldown_cycles", 6) or 6)
    allowed_reasons = {
        str(item).strip()
        for item in list(policy.get("allow_repeat_for", []) or [])
        if str(item).strip()
    }
    recent_promoted = _recent_promoted_capability_kinds(operator_root, limit=memory_window)
    cooldown_kinds = recent_promoted[:cooldown_cycles]
    promoted_kinds = _promoted_capability_kind_set(operator_root)
    next_unpromoted_kind = next((kind for kind in priority_order if kind not in promoted_kinds), "")
    failed_record = _latest_failed_promotion_for_kind(operator_root, requested)
    remediation_reason = explicit_remediation_reason
    if failed_record and "failed_canary" in allowed_reasons:
        remediation_reason = "failed_canary"
    if bool(failed_record.get("rollback_performed", False)) and "failed_rollback" in allowed_reasons:
        remediation_reason = "failed_rollback"
    requested_on_cooldown = requested in cooldown_kinds
    permitted_remediation = bool(remediation_reason and remediation_reason in allowed_reasons)

    selected = requested
    novelty_status = "disabled"
    cooldown_reason = ""
    repeated = False
    permitted_repeat = False
    meaningful_impact = "full_credit"
    if enabled:
        if permitted_remediation:
            novelty_status = "permitted_remediation"
            repeated = True
            permitted_repeat = True
            meaningful_impact = "remediation_credit"
            cooldown_reason = f"repeat permitted for {remediation_reason}"
        elif next_unpromoted_kind and requested in promoted_kinds:
            selected = next_unpromoted_kind
            novelty_status = "novel"
            cooldown_reason = (
                f"{requested} already has promotion evidence; treating repeat as cooldown pressure; "
                "selected next unpromoted capability gap"
            )
        elif requested in promoted_kinds:
            novelty_status = "repeat_blocked"
            repeated = True
            meaningful_impact = "penalize_repeat"
            cooldown_reason = (
                f"{requested} already has promotion evidence and no unpromoted frontier gap is available; "
                "post-ladder synthesis is required"
            )
        elif requested_on_cooldown:
            selected = next(
                (kind for kind in priority_order if kind not in cooldown_kinds and kind not in promoted_kinds),
                next((kind for kind in priority_order if kind not in cooldown_kinds), requested),
            )
            if selected == requested:
                novelty_status = "repeat_blocked"
                repeated = True
                meaningful_impact = "penalize_repeat"
                cooldown_reason = "all configured capability gaps are in cooldown"
            else:
                novelty_status = "novel"
                cooldown_reason = f"{requested} is in cooldown; selected next available capability gap"
        else:
            novelty_status = "novel"

    evaluation = {
        "schema_name": CAPABILITY_NOVELTY_EVALUATION_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "novelty_evaluation_id": "",
        "requested_capability_kind": requested,
        "current_capability_kind": selected,
        "selected_capability_kind": selected,
        "capability_gap_id": selected,
        "recent_promoted_kinds": recent_promoted,
        "cooldown_blocked_kinds": sorted(set(cooldown_kinds)),
        "novelty_status": novelty_status,
        "repeated": repeated,
        "permitted_repeat": permitted_repeat,
        "remediation_reason": remediation_reason,
        "cooldown_reason": cooldown_reason,
        "meaningful_work_impact": meaningful_impact,
        "policy": {
            "enabled": enabled,
            "recent_capability_memory_window": memory_window,
            "repeated_promoted_kind_cooldown_cycles": cooldown_cycles,
            "capability_gap_priority_order": priority_order,
        },
    }
    evaluation["novelty_evaluation_id"] = _record_id("novelty", evaluation)
    if not persist:
        return _redact_autonomy_value(evaluation)
    return _append_ledger(operator_root, "capability_novelty_evaluations", evaluation)


def _latest_overnight_auto_executor(operator_root: str | Path) -> dict[str, Any]:
    return dict(_read_json(_status_path(operator_root)).get("overnight_auto_executor", {}) or {})


def _safe_capability_growth_available(operator_root: str | Path) -> tuple[bool, dict[str, Any]]:
    preview = _capability_novelty_evaluation(operator_root, persist=False)
    novelty_status = str(preview.get("novelty_status", ""))
    return novelty_status != "repeat_blocked", preview


def _growth_pivot_requested(operator_root: str | Path) -> bool:
    executor = _latest_overnight_auto_executor(operator_root)
    state = str(executor.get("state", ""))
    reason = str(executor.get("reason", ""))
    return state == "growth_pivot_requested" or (
        state == "stopped_at_budget_boundary"
        and "governed long-run" in reason
    )


def _post_ladder_synthesis_needed(
    operator_root: str | Path,
    *,
    growth_requested: bool | None = None,
) -> tuple[bool, dict[str, Any]]:
    if growth_requested is None:
        growth_requested = _growth_pivot_requested(operator_root)
    if not growth_requested:
        return False, {}
    promoted_kinds = _promoted_capability_kind_set(operator_root)
    effective_order = _effective_capability_gap_priority_order(operator_root)
    if effective_order and all(kind in promoted_kinds for kind in effective_order):
        novelty_preview = _capability_novelty_evaluation(operator_root, persist=False)
        novelty_preview["novelty_status"] = "repeat_blocked"
        novelty_preview["meaningful_work_impact"] = "penalize_repeat"
        novelty_preview["cooldown_reason"] = (
            "all effective capability gaps already have promotion evidence; post-ladder synthesis is required"
        )
        novelty_preview["cooldown_blocked_kinds"] = sorted(set(effective_order))
        return True, novelty_preview
    safe_growth_available, novelty_preview = _safe_capability_growth_available(operator_root)
    if safe_growth_available:
        return False, novelty_preview
    return str(novelty_preview.get("novelty_status", "")) == "repeat_blocked", novelty_preview


def _adaptive_learning_needed(operator_root: str | Path, *, growth_requested: bool) -> bool:
    if not growth_requested:
        return False
    backoff = _latest(operator_root, "adaptive_learning_backoff_evaluations")
    if str(backoff.get("backoff_status", "")) == "promote_gap":
        return False
    family_backoff = _latest(operator_root, "adaptive_learning_gap_family_evaluations")
    if str(family_backoff.get("family_backoff_status", "")) == "promote_family_gap":
        return False
    promoted = _promoted_capability_kind_set(operator_root)
    if any(kind not in promoted for kind in _learning_synthesized_capability_gap_kinds(operator_root)):
        return False
    latest_synthesis = _latest(operator_root, "post_ladder_syntheses")
    if str(latest_synthesis.get("proposal_status", "")) == "blocked_evidence_only":
        return True
    recent_meaningful = list(reversed(_read_ledger(operator_root, "meaningful_work_evaluations", limit=4)))
    weak_text = " ".join(
        str(item)
        for row in recent_meaningful[:4]
        for item in list(row.get("weak_areas", []) or [])
    ).lower()
    if "adaptive learning" in weak_text or "role specialization" in weak_text:
        return True
    return False


def _build_autonomous_capability_promotion_packet(
    *,
    operator_root: str | Path,
    package_root: str | Path,
    goal: Mapping[str, Any],
    plan: Mapping[str, Any],
    novelty_evaluation: Mapping[str, Any],
) -> dict[str, Any]:
    package = Path(package_root)
    capability_kind = str(
        (
            plan.get("adaptive_learning_repeated_gap_id")
            if str(plan.get("adaptive_learning_backoff_status", "")) == "promote_gap"
            else ""
        )
        or (
            plan.get("family_representative_gap_id")
            if str(plan.get("family_backoff_status", "")) == "promote_family_gap"
            else ""
        )
        or (
            plan.get("runtime_hook_adapter_gap_id")
            if str(plan.get("hook_stall_pivot_action", "")) == "promote_self_modification_candidate"
            else ""
        )
        or novelty_evaluation.get("selected_capability_kind")
        or novelty_evaluation.get("capability_gap_id")
        or CAPABILITY_GAP_KINDS[0]
    )
    synthesized_gap = _safe_synthesized_capability_gap(capability_kind)
    if capability_kind not in CAPABILITY_GAP_KINDS and not synthesized_gap:
        capability_kind = CAPABILITY_GAP_KINDS[0]
    elif synthesized_gap:
        capability_kind = synthesized_gap
    capability_gap_id = capability_kind
    packet_seed = {
        "goal_id": str(goal.get("goal_id", "")),
        "plan_candidate_id": str(plan.get("plan_candidate_id", "")),
        "capability_kind": capability_kind,
        "created_at": _now(),
        "packet_kind": "autonomy_generated_capability_pack",
    }
    packet_id = _record_id("packet", packet_seed)
    source_dir = autonomy_root(operator_root) / "staged_capabilities" / "latest_candidate"
    target_dir = autonomy_root(operator_root) / "adopted_capabilities"
    source_dir.mkdir(parents=True, exist_ok=True)
    capability_source = source_dir / f"{capability_kind}.json"
    capability_target = target_dir / f"{capability_kind}_latest.json"
    test_script = source_dir / "validate_source_capability.py"
    canary_script = source_dir / "validate_adopted_capability.py"
    capability_payload = {
        "schema_name": "NovaliAutonomousCapabilityPack",
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "capability_id": packet_id,
        "capability_kind": capability_kind,
        "capability_gap_id": capability_gap_id,
        "novelty_evaluation_id": str(novelty_evaluation.get("novelty_evaluation_id", "")),
        "novelty_status": str(novelty_evaluation.get("novelty_status", "")),
        "permitted_repeat": bool(novelty_evaluation.get("permitted_repeat", False)),
        "adaptive_learning_backoff_id": str(plan.get("adaptive_learning_backoff_id", "")),
        "backoff_promoted_gap": str(plan.get("adaptive_learning_backoff_status", "")) == "promote_gap",
        "repeated_learning_gap_id": str(plan.get("adaptive_learning_repeated_gap_id", "")),
        "adaptive_learning_gap_family_id": str(plan.get("adaptive_learning_gap_family_id", "")),
        "adaptive_learning_gap_family_evaluation_id": str(
            plan.get("adaptive_learning_gap_family_evaluation_id", "")
        ),
        "family_backoff_id": str(plan.get("family_backoff_id", "")),
        "family_backoff_promoted_gap": str(plan.get("family_backoff_status", "")) == "promote_family_gap",
        "family_member_gap_ids": list(plan.get("family_member_gap_ids", []) or []),
        "representative_gap_id": str(plan.get("family_representative_gap_id", "")),
        "adaptive_learning_hook_stall_id": str(plan.get("adaptive_learning_hook_stall_id", "")),
        "hook_stall_status": str(plan.get("hook_stall_status", "")),
        "hook_stall_pivot_action": str(plan.get("hook_stall_pivot_action", "")),
        "stalled_capability_kind": str(plan.get("stalled_capability_kind", "")),
        "runtime_hook_adapter_gap_id": str(plan.get("runtime_hook_adapter_gap_id", "")),
        "runtime_hook_adapter_behavior": str(plan.get("runtime_hook_adapter_behavior", "")),
        "goal_id": str(goal.get("goal_id", "")),
        "plan_candidate_id": str(plan.get("plan_candidate_id", "")),
        "adoption_target": "novali_own_stack",
        "summary": CAPABILITY_KIND_SUMMARIES.get(
            capability_kind,
            f"Autonomy synthesized follow-on capability gap {capability_kind} from post-ladder promotion evidence.",
        ),
        "safe_operating_boundary": (
            "This v1 capability adopts into operator_state/autonomy/adopted_capabilities, not protected source roots."
        ),
    }
    _write_json(capability_source, capability_payload)
    source_relative = _relative_package_path(package, capability_source)
    target_relative = _relative_package_path(package, capability_target)
    test_script.write_text(
        "\n".join(
            [
                "import json",
                "import pathlib",
                f"p = pathlib.Path({source_relative!r})",
                "data = json.loads(p.read_text(encoding='utf-8'))",
                "assert data['schema_name'] == 'NovaliAutonomousCapabilityPack'",
                f"assert data['capability_kind'] == {capability_kind!r}",
                f"assert data['capability_gap_id'] == {capability_gap_id!r}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    canary_script.write_text(
        "\n".join(
            [
                "import json",
                "import pathlib",
                f"p = pathlib.Path({target_relative!r})",
                "data = json.loads(p.read_text(encoding='utf-8'))",
                "assert data['schema_name'] == 'NovaliAutonomousCapabilityPack'",
                "assert data['adoption_target'] == 'novali_own_stack'",
                "",
            ]
        ),
        encoding="utf-8",
    )
    test_script_relative = _relative_package_path(package, test_script)
    canary_script_relative = _relative_package_path(package, canary_script)
    return {
        "schema_name": "SelfModificationPromotionPacket",
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "promotion_packet_id": packet_id,
        "capability_kind": capability_kind,
        "capability_gap_id": capability_gap_id,
        "novelty_evaluation_id": str(novelty_evaluation.get("novelty_evaluation_id", "")),
        "novelty_status": str(novelty_evaluation.get("novelty_status", "")),
        "permitted_repeat": bool(novelty_evaluation.get("permitted_repeat", False)),
        "adaptive_learning_backoff_id": str(plan.get("adaptive_learning_backoff_id", "")),
        "backoff_promoted_gap": str(plan.get("adaptive_learning_backoff_status", "")) == "promote_gap",
        "repeated_learning_gap_id": str(plan.get("adaptive_learning_repeated_gap_id", "")),
        "adaptive_learning_gap_family_id": str(plan.get("adaptive_learning_gap_family_id", "")),
        "adaptive_learning_gap_family_evaluation_id": str(
            plan.get("adaptive_learning_gap_family_evaluation_id", "")
        ),
        "family_backoff_id": str(plan.get("family_backoff_id", "")),
        "family_backoff_promoted_gap": str(plan.get("family_backoff_status", "")) == "promote_family_gap",
        "family_member_gap_ids": list(plan.get("family_member_gap_ids", []) or []),
        "representative_gap_id": str(plan.get("family_representative_gap_id", "")),
        "adaptive_learning_hook_stall_id": str(plan.get("adaptive_learning_hook_stall_id", "")),
        "hook_stall_status": str(plan.get("hook_stall_status", "")),
        "hook_stall_pivot_action": str(plan.get("hook_stall_pivot_action", "")),
        "stalled_capability_kind": str(plan.get("stalled_capability_kind", "")),
        "runtime_hook_adapter_gap_id": str(plan.get("runtime_hook_adapter_gap_id", "")),
        "runtime_hook_adapter_behavior": str(plan.get("runtime_hook_adapter_behavior", "")),
        "adoption_target": "novali_own_stack",
        "risk_class": "bounded_state_capability_adoption",
        "changed_file_manifest": [
            {
                "source_path": source_relative,
                "target_path": target_relative,
                "change_kind": "adopt_generated_capability_record",
                "description": "Adopt the latest autonomy-generated capability record into Novali-owned state.",
            }
        ],
        "test_commands": [[sys.executable, test_script_relative]],
        "rollback_plan": {
            "snapshot_before_write": True,
            "rollback_summary": "The broker snapshots the adopted capability file before overwrite and can restore it.",
        },
        "canary_plan": {
            "commands": [[sys.executable, canary_script_relative]],
            "summary": "Read the adopted capability record after copy and verify schema plus target.",
        },
        "auto_adopt_eligible": True,
        "source_packet_path": str(capability_source),
        "target_packet_path": str(capability_target),
    }


def _meaningful_work_evaluation(
    *,
    operator_root: str | Path,
    goal: Mapping[str, Any],
    plan: Mapping[str, Any],
    operation: Mapping[str, Any],
    self_modification: Mapping[str, Any],
    promotion: Mapping[str, Any],
    observations: Mapping[str, Any],
) -> dict[str, Any]:
    governed_readiness = dict(observations.get("governed_readiness", {}) or {})
    directive_loaded = bool(
        dict(governed_readiness.get("operator_state", {}) or {}).get("directive_loaded", False)
    ) or bool(dict(observations.get("current_directive", {}) or {}).get("directive_selected", False))
    operation_action = str(operation.get("action", ""))
    promotion_stage = str(self_modification.get("promotion_stage", "")).strip() or "candidate"
    has_packet = bool(self_modification.get("promotion_packet"))
    promotion_packet_evidence = _latest_promotion_packet_evidence(operator_root)
    fresh_promotion_packet_evidence = (
        promotion_packet_evidence.get("promotion_packet_evidence_state") == "fresh"
    )
    capability_kind = str(
        operation.get("capability_kind")
        or self_modification.get("capability_kind")
        or promotion.get("capability_kind")
        or promotion_packet_evidence.get("capability_kind")
        or ""
    )
    capability_gap_id = str(
        operation.get("capability_gap_id")
        or self_modification.get("capability_gap_id")
        or promotion.get("capability_gap_id")
        or capability_kind
    )
    novelty_evaluation_id = str(
        operation.get("novelty_evaluation_id")
        or self_modification.get("novelty_evaluation_id")
        or promotion.get("novelty_evaluation_id")
        or ""
    )
    novelty_status = str(
        operation.get("novelty_status")
        or self_modification.get("novelty_status")
        or promotion.get("novelty_status")
        or ""
    )
    novelty_impact = str(operation.get("meaningful_work_impact") or "")
    measurable_conditions = [
        str(item).strip()
        for item in list(plan.get("measurable_success_conditions", []) or [])
        if str(item).strip()
    ]
    consumed_capability_kinds = [
        str(item).strip()
        for item in list(
            operation.get("consumed_capability_kinds")
            or plan.get("consumed_capability_kinds")
            or []
        )
        if str(item).strip()
    ]
    explicitly_consumed_capability_kinds = [
        str(item).strip()
        for item in list(
            operation.get("explicitly_consumed_capability_kinds")
            or plan.get("explicitly_consumed_capability_kinds")
            or consumed_capability_kinds
            or []
        )
        if str(item).strip()
    ]
    planner_hook_references = [
        str(item).strip()
        for item in list(
            operation.get("planner_hook_references")
            or plan.get("planner_hook_references")
            or []
        )
        if str(item).strip()
    ]

    directive_signals: list[str] = []
    if directive_loaded:
        directive_signals.append("directive_loaded")
    if bool(governed_readiness.get("can_launch", False)):
        directive_signals.append("governed_launch_ready")
    if operation_action == "governed_start_next_invocation":
        directive_signals.append("governed_start_proposed")
    if measurable_conditions:
        directive_signals.append("measurable_success_condition_present")

    capability_signals: list[str] = []
    if promotion_stage in PROMOTION_LADDER_STAGES:
        capability_signals.append(f"promotion_stage:{promotion_stage}")
    if has_packet:
        capability_signals.append("promotion_packet_present")
    elif fresh_promotion_packet_evidence:
        capability_signals.append("promotion_packet_evidence_fresh")
    if str(promotion.get("decision", "")) in {"eligible", "staged", "canary_adopted", "promoted"}:
        capability_signals.append(f"promotion_decision:{promotion.get('decision')}")
    if operation_action == "promote_self_modification_candidate":
        capability_signals.append("self_modification_promotion_operation_proposed")
    if bool(operation.get("backoff_promoted_gap", False)) or bool(
        self_modification.get("backoff_promoted_gap", False)
    ):
        capability_signals.append("adaptive_learning_backoff_promote_gap")
    if bool(operation.get("family_backoff_promoted_gap", False)) or bool(
        self_modification.get("family_backoff_promoted_gap", False)
    ):
        capability_signals.append("adaptive_learning_family_backoff_promote_gap")
    if capability_kind:
        capability_signals.append(f"capability_kind:{capability_kind}")
    if novelty_status:
        capability_signals.append(f"novelty:{novelty_status}")
    if consumed_capability_kinds:
        capability_signals.append("planner_hook_consumed_capability")
    if bool(operation.get("decision_changed_by_capability", False)):
        capability_signals.append("planner_hook_changed_decision")
    if str(operation.get("hook_stall_status", "")) == "stalled":
        capability_signals.append("adaptive_learning_hook_stall_pivot")
    if str(operation.get("runtime_hook_adapter_gap_id", "")):
        capability_signals.append("runtime_hook_adapter_candidate")
    if str(operation.get("budget_guardrail_evaluation_id", "")):
        capability_signals.append("execution_budget_guardrail_evaluated")
    if bool(operation.get("budget_prevented_overrun", False)):
        capability_signals.append("execution_budget_guardrail_prevented_overrun")
    if operation_action == "trusted_source_literature_triage_digest":
        capability_signals.append("trusted_source_literature_triage_digest")
    latest_triage_digest = _latest(operator_root, "trusted_source_literature_triage_digests")
    if (
        str(latest_triage_digest.get("status", "")) == "completed"
        and bool(latest_triage_digest.get("digest_usable_for_learning", False))
        and int(latest_triage_digest.get("citation_count", 0) or 0) > 0
    ):
        capability_signals.append("trusted_source_triage_usable_evidence")
        directive_signals.append("trusted_source_learning_evidence_created")
        if str(latest_triage_digest.get("digest_source", "")) == "local_context_fallback":
            capability_signals.append("trusted_source_triage_local_context_fallback")

    previous = _latest(operator_root, "meaningful_work_evaluations")
    directive_track_delta = _latest_deepened_directive_track_delta(operator_root)
    directive_track_delta_candidate = bool(
        directive_track_delta.get("artifact_ref")
        and directive_track_delta.get("delta_materially_new", False)
    )
    directive_track_delta_repeated = False
    if directive_track_delta_candidate and bool(
        previous.get("directive_track_delta_credited", False)
    ):
        current_signature = str(
            directive_track_delta.get("new_information_delta_signature", "") or ""
        )
        same_signature = current_signature and current_signature == str(
            previous.get("directive_track_delta_signature", "") or ""
        )
        same_focus = str(directive_track_delta.get("delta_focus_id", "") or "") == str(
            previous.get("directive_track_delta_focus_id", "") or ""
        )
        same_layer = str(directive_track_delta.get("delta_layer_id", "") or "") == str(
            previous.get("directive_track_delta_layer_id", "") or ""
        )
        same_artifact = str(directive_track_delta.get("artifact_ref", "") or "") == str(
            previous.get("directive_track_artifact_ref", "") or ""
        )
        same_progress_time = str(
            directive_track_delta.get("progress_generated_at", "") or ""
        ) == str(previous.get("directive_track_progress_generated_at", "") or "")
        directive_track_delta_repeated = bool(
            same_signature
            and same_focus
            and same_layer
            and same_artifact
            and same_progress_time
        )
    directive_track_delta_credited = bool(
        directive_track_delta_candidate and not directive_track_delta_repeated
    )
    directive_track_delta_rejection_reason = (
        "repeated_delta_signature"
        if directive_track_delta_repeated
        else str(directive_track_delta.get("delta_rejection_reason", "") or "")
    )
    directive_dossier_delta_candidate = bool(
        directive_track_delta.get("directive_dossier_artifact_ref")
        and directive_track_delta.get("directive_dossier_materially_new", False)
    )
    directive_dossier_delta_repeated = False
    if directive_dossier_delta_candidate and bool(
        previous.get("directive_dossier_delta_credited", False)
    ):
        same_dossier_signature = str(
            directive_track_delta.get("directive_dossier_signature", "") or ""
        ) == str(previous.get("directive_dossier_signature", "") or "")
        same_dossier_artifact = str(
            directive_track_delta.get("directive_dossier_artifact_ref", "") or ""
        ) == str(previous.get("directive_dossier_artifact_ref", "") or "")
        same_dossier_time = str(
            directive_track_delta.get("directive_dossier_progress_generated_at", "")
            or ""
        ) == str(previous.get("directive_dossier_progress_generated_at", "") or "")
        directive_dossier_delta_repeated = bool(
            same_dossier_signature and same_dossier_artifact and same_dossier_time
        )
    directive_dossier_delta_credited = bool(
        directive_dossier_delta_candidate and not directive_dossier_delta_repeated
    )
    directive_dossier_rejection_reason = (
        "repeated_dossier_signature"
        if directive_dossier_delta_repeated
        else str(
            directive_track_delta.get("directive_dossier_rejection_reason", "") or ""
        )
    )
    directive_work_due = bool(
        plan.get("directive_dossier_required", False)
        or plan.get("directive_work_due", False)
        or operation.get("directive_dossier_required", False)
        or operation.get("directive_work_due", False)
    )
    directive_progress_blocker = ""
    if (
        directive_work_due
        and not directive_track_delta_credited
        and not directive_dossier_delta_credited
    ):
        directive_progress_blocker = str(
            operation.get("directive_progress_blocker")
            or plan.get("directive_progress_blocker")
            or "directive_dossier_not_refreshed"
        )
    role_profile = _latest(operator_root, "role_specialization_profiles")
    usefulness = _latest(operator_root, "capability_usefulness_evaluations")
    strict_usefulness_capability_kind = str(usefulness.get("capability_kind", "") or "")
    strict_usefulness_signal_count = int(
        usefulness.get("strong_usefulness_signal_count", 0) or 0
    )
    strict_usefulness_gate_passed = bool(
        usefulness.get("strict_usefulness_gate_passed", False)
    ) and str(usefulness.get("usefulness", "")) == "useful"
    strict_useful_capability_consumed = (
        strict_usefulness_gate_passed
        and strict_usefulness_capability_kind
        and strict_usefulness_capability_kind
        in set(explicitly_consumed_capability_kinds + consumed_capability_kinds)
    )
    hook_changed_decision = bool(operation.get("decision_changed_by_capability", False))
    hook_kept_governed_execution_moving = (
        operation_action == "governed_start_next_invocation"
        and hook_changed_decision
        and strict_useful_capability_consumed
    )
    strict_usefulness_credited = strict_useful_capability_consumed and (
        hook_changed_decision
        or bool(operation.get("repeat_failure_prevented", False))
        or bool(operation.get("budget_prevented_overrun", False))
    )
    planner_runtime_impact = 0.0
    if hook_kept_governed_execution_moving:
        planner_runtime_impact = 1.0
    elif strict_usefulness_credited and hook_changed_decision:
        planner_runtime_impact = 0.75
    elif strict_useful_capability_consumed and planner_hook_references:
        planner_runtime_impact = 0.5
    if strict_usefulness_credited:
        capability_signals.append("strict_useful_planner_runtime_impact")
    if hook_kept_governed_execution_moving:
        directive_signals.append("strict_useful_hook_kept_governed_execution_moving")

    directive_progress = min(1.0, len(directive_signals) / 4.0)
    capability_growth = min(1.0, len(capability_signals) / 5.0)
    signal_signature = _hash_payload(
        {
            "directive": directive_signals,
            "capability": capability_signals,
            "operation": operation_action,
            "stage": promotion_stage,
        },
        length=16,
    )
    repeated_signal_signature = signal_signature == str(previous.get("signal_signature", ""))
    strict_usefulness_counts_for_delta = bool(
        strict_usefulness_credited and not directive_progress_blocker
    )
    meaningful_delta = (
        not repeated_signal_signature
        or strict_usefulness_counts_for_delta
        or directive_track_delta_credited
        or directive_dossier_delta_credited
    )
    if (
        repeated_signal_signature
        and not strict_usefulness_counts_for_delta
        and not directive_track_delta_credited
        and not directive_dossier_delta_credited
    ):
        directive_progress = min(directive_progress, 0.25)
        capability_growth = min(capability_growth, 0.25)
    if novelty_status == "repeat_blocked" or novelty_impact == "penalize_repeat":
        capability_growth = min(capability_growth, 0.25)
    role_alignment = 0.0
    if role_profile:
        role_alignment = 0.5
        if capability_kind and capability_kind in _compact_json(role_profile):
            role_alignment = 1.0
        elif operation_action in {"adaptive_learning_synthesis", "post_ladder_synthesis"}:
            role_alignment = 0.75
    later_usefulness = 0.0
    if str(usefulness.get("usefulness", "")) == "useful" and bool(
        usefulness.get("strict_usefulness_gate_passed", False)
    ):
        later_usefulness = 1.0
    elif str(usefulness.get("usefulness", "")) in {"useful", "evidence_only", "dormant"}:
        later_usefulness = 0.25
    operator_independence = 1.0 if not bool(operation.get("requires_human", False)) else 0.25
    base_score = (directive_progress + capability_growth) / 2.0
    total_score = round(
        min(
            1.0,
            (base_score * 0.7)
            + (later_usefulness * 0.15)
            + (planner_runtime_impact * 0.1)
            + (operator_independence * 0.05),
        ),
        3,
    )
    weak_areas: list[str] = []
    if not directive_signals:
        weak_areas.append("no directive-progress signal")
    if not has_packet and not fresh_promotion_packet_evidence:
        weak_areas.append("missing promotion packet")
    if not measurable_conditions:
        weak_areas.append("missing measurable success condition")
    if (
        repeated_signal_signature
        and not strict_usefulness_counts_for_delta
        and not directive_track_delta_credited
        and not directive_dossier_delta_credited
    ):
        weak_areas.append("repeated signal signature; likely artifact churn")
    if directive_progress_blocker and directive_progress_blocker not in weak_areas:
        weak_areas.append(directive_progress_blocker.replace("_", " "))
    if novelty_status == "repeat_blocked" or novelty_impact == "penalize_repeat":
        weak_areas.append("repeated promoted capability kind is in novelty cooldown")

    evaluation = {
        "schema_name": MEANINGFUL_WORK_EVALUATION_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "meaningful_work_id": "",
        "goal_id": str(goal.get("goal_id", "")),
        "plan_candidate_id": str(plan.get("plan_candidate_id", "")),
        "operation_id": str(operation.get("operation_id", "")),
        "self_modification_id": str(self_modification.get("self_modification_id", "")),
        "promotion_decision_id": str(promotion.get("promotion_decision_id", "")),
        "capability_kind": capability_kind,
        "capability_gap_id": capability_gap_id,
        "promotion_packet_evidence_state": str(
            promotion_packet_evidence.get("promotion_packet_evidence_state", "missing")
        ),
        "promotion_packet_ref": str(promotion_packet_evidence.get("promotion_packet_ref", "")),
        "novelty_evaluation_id": novelty_evaluation_id,
        "novelty_status": novelty_status,
        "adaptive_learning_backoff_id": str(
            operation.get("adaptive_learning_backoff_id")
            or self_modification.get("adaptive_learning_backoff_id")
            or plan.get("adaptive_learning_backoff_id")
            or ""
        ),
        "backoff_promoted_gap": bool(
            operation.get("backoff_promoted_gap", False)
            or self_modification.get("backoff_promoted_gap", False)
        ),
        "repeated_learning_gap_id": str(
            operation.get("repeated_learning_gap_id")
            or self_modification.get("repeated_learning_gap_id")
            or plan.get("adaptive_learning_repeated_gap_id")
            or ""
        ),
        "adaptive_learning_gap_family_id": str(
            operation.get("adaptive_learning_gap_family_id")
            or self_modification.get("adaptive_learning_gap_family_id")
            or plan.get("adaptive_learning_gap_family_id")
            or ""
        ),
        "adaptive_learning_gap_family_evaluation_id": str(
            operation.get("adaptive_learning_gap_family_evaluation_id")
            or self_modification.get("adaptive_learning_gap_family_evaluation_id")
            or plan.get("adaptive_learning_gap_family_evaluation_id")
            or ""
        ),
        "family_backoff_id": str(
            operation.get("family_backoff_id")
            or self_modification.get("family_backoff_id")
            or plan.get("family_backoff_id")
            or ""
        ),
        "family_backoff_promoted_gap": bool(
            operation.get("family_backoff_promoted_gap", False)
            or self_modification.get("family_backoff_promoted_gap", False)
        ),
        "family_member_gap_ids": [
            str(item).strip()
            for item in list(
                operation.get("family_member_gap_ids")
                or self_modification.get("family_member_gap_ids")
                or plan.get("family_member_gap_ids")
                or []
            )
            if str(item).strip()
        ],
        "representative_gap_id": str(
            operation.get("representative_gap_id")
            or self_modification.get("representative_gap_id")
            or plan.get("family_representative_gap_id")
            or ""
        ),
        "capability_consumption_event_id": str(
            operation.get("capability_consumption_event_id")
            or plan.get("capability_consumption_event_id")
            or ""
        ),
        "capability_consumption_contract_ids": list(
            operation.get("capability_consumption_contract_ids")
            or plan.get("capability_consumption_contract_ids")
            or []
        ),
        "runtime_capability_adapter_ids": list(
            operation.get("runtime_capability_adapter_ids")
            or plan.get("runtime_capability_adapter_ids")
            or []
        ),
        "runtime_capability_adapter_behaviors": list(
            operation.get("runtime_capability_adapter_behaviors")
            or plan.get("runtime_capability_adapter_behaviors")
            or []
        ),
        "consumed_capability_kinds": consumed_capability_kinds,
        "explicitly_consumed_capability_kinds": explicitly_consumed_capability_kinds,
        "planner_hook_references": planner_hook_references,
        "runtime_hook_references": planner_hook_references,
        "referenced_planner_hook_capability": consumed_capability_kinds,
        "capability_hook_consumption_id": str(
            operation.get("capability_hook_consumption_id")
            or plan.get("capability_hook_consumption_id")
            or ""
        ),
        "decision_changed_by_capability": bool(
            operation.get("decision_changed_by_capability", False)
        ),
        "repeat_failure_prevented": bool(operation.get("repeat_failure_prevented", False)),
        "budget_guardrail_evaluation_id": str(
            operation.get("budget_guardrail_evaluation_id")
            or plan.get("budget_guardrail_evaluation_id")
            or ""
        ),
        "budget_decision": str(operation.get("budget_decision") or plan.get("budget_decision") or ""),
        "budget_reason": str(operation.get("budget_reason") or plan.get("budget_reason") or ""),
        "budget_prevented_overrun": bool(
            operation.get("budget_prevented_overrun")
            or plan.get("budget_prevented_overrun")
            or False
        ),
        "trusted_source_triage_needed": bool(
            operation.get("trusted_source_triage_needed")
            or plan.get("trusted_source_triage_needed")
            or False
        ),
        "capability_retirement_evaluation_id": str(
            operation.get("capability_retirement_evaluation_id")
            or plan.get("capability_retirement_evaluation_id")
            or ""
        ),
        "capability_retirement_status": str(
            operation.get("capability_retirement_status")
            or plan.get("capability_retirement_status")
            or ""
        ),
        "capability_retirement_reason": str(
            operation.get("capability_retirement_reason")
            or plan.get("capability_retirement_reason")
            or ""
        ),
        "capability_retirement_pivot_action": str(
            operation.get("capability_retirement_pivot_action")
            or plan.get("capability_retirement_pivot_action")
            or ""
        ),
        "weak_usefulness_repeat_count": int(
            operation.get("weak_usefulness_repeat_count")
            or plan.get("weak_usefulness_repeat_count")
            or 0
        ),
        "weak_usefulness_repeat_threshold": int(
            operation.get("weak_usefulness_repeat_threshold")
            or plan.get("weak_usefulness_repeat_threshold")
            or 0
        ),
        "consumption_contract_missing": bool(
            operation.get("consumption_contract_missing")
            or plan.get("consumption_contract_missing")
            or False
        ),
        "adaptive_learning_hook_stall_id": str(
            operation.get("adaptive_learning_hook_stall_id")
            or plan.get("adaptive_learning_hook_stall_id")
            or ""
        ),
        "hook_stall_status": str(operation.get("hook_stall_status") or plan.get("hook_stall_status") or ""),
        "hook_stall_pivot_action": str(
            operation.get("hook_stall_pivot_action")
            or plan.get("hook_stall_pivot_action")
            or ""
        ),
        "hook_stall_reason": str(operation.get("hook_stall_reason") or plan.get("hook_stall_reason") or ""),
        "hook_stall_repeat_count": int(
            operation.get("hook_stall_repeat_count")
            or plan.get("hook_stall_repeat_count")
            or 0
        ),
        "hook_stall_repeat_threshold": int(
            operation.get("hook_stall_repeat_threshold")
            or plan.get("hook_stall_repeat_threshold")
            or 0
        ),
        "stalled_capability_kind": str(
            operation.get("stalled_capability_kind")
            or plan.get("stalled_capability_kind")
            or ""
        ),
        "runtime_hook_adapter_gap_id": str(
            operation.get("runtime_hook_adapter_gap_id")
            or plan.get("runtime_hook_adapter_gap_id")
            or ""
        ),
        "runtime_hook_adapter_behavior": str(
            operation.get("runtime_hook_adapter_behavior")
            or plan.get("runtime_hook_adapter_behavior")
            or ""
        ),
        "directive_progress": round(directive_progress, 3),
        "directive_track_delta_credited": directive_track_delta_credited,
        "directive_track_delta_materially_new": bool(
            directive_track_delta.get("delta_materially_new", False)
        ),
        "directive_track_delta_rejection_reason": str(
            directive_track_delta_rejection_reason
        ),
        "directive_track_deliverable_kind": str(
            directive_track_delta.get("deliverable_kind", "")
        ),
        "directive_track_delta_focus_id": str(
            directive_track_delta.get("delta_focus_id", "")
        ),
        "directive_track_delta_focus_label": str(
            directive_track_delta.get("delta_focus_label", "")
        ),
        "directive_track_focus_rotation_state": str(
            directive_track_delta.get("focus_rotation_state", "")
        ),
        "directive_track_delta_layer_id": str(
            directive_track_delta.get("delta_layer_id", "")
        ),
        "directive_track_delta_layer_label": str(
            directive_track_delta.get("delta_layer_label", "")
        ),
        "directive_track_layer_rotation_state": str(
            directive_track_delta.get("layer_rotation_state", "")
        ),
        "directive_track_delta_signature": str(
            directive_track_delta.get("new_information_delta_signature", "")
        ),
        "directive_track_artifact_depth": str(
            directive_track_delta.get("artifact_depth", "")
        ),
        "directive_track_depth_iteration": int(
            directive_track_delta.get("depth_iteration", 0) or 0
        ),
        "directive_track_artifact_ref": str(
            directive_track_delta.get("artifact_ref", "")
        ),
        "directive_track_progress_generated_at": str(
            directive_track_delta.get("progress_generated_at", "")
        ),
        "directive_track_credit_source": str(
            directive_track_delta.get("credit_source", "")
        ),
        "directive_dossier_delta_credited": directive_dossier_delta_credited,
        "directive_dossier_materially_new": bool(
            directive_track_delta.get("directive_dossier_materially_new", False)
        ),
        "directive_dossier_rejection_reason": str(directive_dossier_rejection_reason),
        "directive_dossier_signature": str(
            directive_track_delta.get("directive_dossier_signature", "")
        ),
        "directive_dossier_artifact_ref": str(
            directive_track_delta.get("directive_dossier_artifact_ref", "")
        ),
        "latest_directive_dossier_ref": str(
            directive_track_delta.get("directive_dossier_artifact_relative_path", "")
            or directive_track_delta.get("directive_dossier_artifact_ref", "")
        ),
        "directive_dossier_progress_generated_at": str(
            directive_track_delta.get("directive_dossier_progress_generated_at", "")
        ),
        "directive_source_coverage_state": str(
            directive_track_delta.get("directive_source_coverage_state", "")
        ),
        "librarian_gap_reuse_decision": str(
            directive_track_delta.get("librarian_gap_reuse_decision", "")
        ),
        "trusted_source_retrieval_validation_state": str(
            directive_track_delta.get("trusted_source_retrieval_validation_state", "")
        ),
        "directive_progress_blocker": directive_progress_blocker,
        "capability_growth": round(capability_growth, 3),
        "role_alignment": round(role_alignment, 3),
        "later_usefulness": round(later_usefulness, 3),
        "operator_independence": round(operator_independence, 3),
        "planner_runtime_impact": round(planner_runtime_impact, 3),
        "strict_usefulness_credited": strict_usefulness_credited,
        "strict_usefulness_capability_kind": strict_usefulness_capability_kind,
        "strict_usefulness_signal_count": strict_usefulness_signal_count,
        "strict_useful_capability_consumed": strict_useful_capability_consumed,
        "hook_kept_governed_execution_moving": hook_kept_governed_execution_moving,
        "total_score": total_score,
        "meaningful_delta": meaningful_delta,
        "signal_signature": signal_signature,
        "directive_signals": directive_signals,
        "capability_signals": capability_signals,
        "weak_areas": weak_areas,
        "next_objective_hint": (
            "prepare_candidate_promotion_bundle"
            if "missing promotion packet" in weak_areas
            else "continue_governed_directive"
            if directive_loaded
            else "establish_launchable_directive_context"
        ),
    }
    evaluation["meaningful_work_id"] = _record_id("meaningful", evaluation)
    record = _append_ledger(operator_root, "meaningful_work_evaluations", evaluation)
    record_meaningful_work_evaluation(record)
    return record


def _autonomous_growth_summary(operator_root: str | Path) -> dict[str, Any]:
    meaningful = _latest(operator_root, "meaningful_work_evaluations")
    self_mod = _latest(operator_root, "self_modification_proposals")
    promotion_decision = _latest(operator_root, "promotion_decisions")
    promotion_result = _latest(operator_root, "promotion_results")
    novelty = _latest(operator_root, "capability_novelty_evaluations")
    synthesis = _latest(operator_root, "post_ladder_syntheses")
    role_profile = _latest(operator_root, "role_specialization_profiles")
    usefulness = _latest(operator_root, "capability_usefulness_evaluations")
    curriculum = _latest(operator_root, "self_curriculum_challenges")
    replay = _latest(operator_root, "metacognitive_replays")
    adaptive = _latest(operator_root, "adaptive_learning_syntheses")
    adaptive_backoff = _latest(operator_root, "adaptive_learning_backoff_evaluations")
    adaptive_family_backoff = _latest(operator_root, "adaptive_learning_gap_family_evaluations")
    adaptive_hook_stall = _latest(operator_root, "adaptive_learning_hook_stall_evaluations")
    hook = _latest(operator_root, "capability_hook_consumptions")
    consumption_event = _latest(operator_root, "capability_consumption_events")
    consumption_contract = _latest(operator_root, "capability_consumption_contracts")
    runtime_adapter = _latest(operator_root, "runtime_capability_adapters")
    retirement = _latest(operator_root, "capability_retirement_evaluations")
    budget_guardrail = _latest(operator_root, "execution_budget_guardrail_evaluations")
    triage_digest = _latest(operator_root, "trusted_source_literature_triage_digests")
    operation_proposal = _latest_open_operation_proposal(operator_root)
    operation_result = _latest(operator_root, "operation_results")
    memory_status = _latest_memory_pressure_status(operator_root)
    memory_archive = _latest(operator_root, "memory_archive_manifests")
    memory_attempt = _latest_memory_archive_attempt(operator_root)
    ledger_compaction_attempt = _latest_ledger_compaction_attempt(operator_root)
    ledger_compaction_manifest = _latest(operator_root, "ledger_compaction_segment_manifests")
    memory_recovery = _latest(operator_root, "memory_recovery_requests")
    governed_window = _latest_governed_invocation_window(operator_root)
    rollback = _latest(operator_root, "rollback_records")
    stage = str(
        promotion_result.get("promotion_stage")
        or self_mod.get("promotion_stage")
        or "candidate"
    )
    auto_adopt_eligible = bool(
        self_mod.get("auto_adopt_eligible", False)
        or promotion_result.get("auto_adopted", False)
    )
    human_reason = ""
    if not auto_adopt_eligible:
        human_reason = str(
            promotion_decision.get("reason", "")
            or promotion_result.get("failure_reason", "")
            or "Promotion packet gates have not all passed yet."
        )
    missing_skills = [
        str(item)
        for item in list(role_profile.get("missing_skills", []) or [])
        if str(item).strip()
    ] if isinstance(role_profile.get("missing_skills", []), list) else []
    missing_contracts = _capabilities_lacking_consumption_contracts(operator_root)
    weak_capability_rows = [
        row
        for row in _read_ledger(operator_root, "capability_usefulness_evaluations", limit=200)
        if str(row.get("usefulness", "")) in {"dormant", "evidence_only", "needs_followup"}
        and not bool(row.get("strict_usefulness_gate_passed", False))
    ]
    dormant_or_retired_count = len(
        [
            row
            for row in _read_ledger(operator_root, "capability_usefulness_evaluations", limit=200)
            if str(row.get("retirement_state", "")) in {"dormant", "retired", "needs_repair"}
        ]
    )
    return {
        "schema_name": "AutonomousGrowthSummary",
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "generated_at": _now(),
        "meaningful_work_score": meaningful.get("total_score", 0),
        "directive_progress": meaningful.get("directive_progress", 0),
        "capability_growth": meaningful.get("capability_growth", 0),
        "meaningful_delta": bool(meaningful.get("meaningful_delta", False)),
        "planner_runtime_impact": meaningful.get("planner_runtime_impact", 0),
        "strict_usefulness_credited": bool(meaningful.get("strict_usefulness_credited", False)),
        "strict_usefulness_credited_capability_kind": str(
            meaningful.get("strict_usefulness_capability_kind", "")
        ),
        "strict_usefulness_meaningful_signal_count": int(
            meaningful.get("strict_usefulness_signal_count", 0) or 0
        ),
        "hook_kept_governed_execution_moving": bool(
            meaningful.get("hook_kept_governed_execution_moving", False)
        ),
        "governed_invocation_window_mode": str(governed_window.get("mode", "")),
        "governed_invocation_window_decision": str(governed_window.get("decision", "")),
        "governed_invocation_window_reason": str(governed_window.get("reason", "")),
        "governed_invocation_window_selected_cap": int(
            governed_window.get("selected_cap", 0) or 0
        ),
        "governed_invocation_window_previous_cap": int(
            governed_window.get("previous_cap", 0) or 0
        ),
        "governed_invocation_window_min": int(
            governed_window.get("min_cycles_per_invocation", 0) or 0
        ),
        "governed_invocation_window_default": int(
            governed_window.get("default_cycles_per_invocation", 0) or 0
        ),
        "governed_invocation_window_max": int(
            governed_window.get("max_cycles_per_invocation", 0) or 0
        ),
        "governed_invocation_window_safety_band": str(
            governed_window.get("safety_band", "")
        ),
        "governed_invocation_window_blockers": list(
            governed_window.get("blockers", []) or []
        ),
        "active_directive_objective": str(meaningful.get("next_objective_hint", "")),
        "active_capability_growth_objective": (
            "promote_self_modification_candidate"
            if auto_adopt_eligible
            else "prepare_candidate_promotion_bundle"
        ),
        "candidate_promotion_stage": stage,
        "auto_adopt_eligible": auto_adopt_eligible,
        "canary_result": str(promotion_result.get("canary_result", "not_run")),
        "rollback_available": bool(rollback.get("rollback_available", False)),
        "novelty_status": str(novelty.get("novelty_status", "not_evaluated")),
        "selected_capability_gap": str(novelty.get("capability_gap_id", "")),
        "selected_capability_kind": str(novelty.get("selected_capability_kind", "")),
        "recent_promoted_capability_kinds": list(novelty.get("recent_promoted_kinds", []) or []),
        "cooldown_reason": str(novelty.get("cooldown_reason", "")),
        "novelty_evaluation_id": str(novelty.get("novelty_evaluation_id", "")),
        "post_ladder_synthesis_status": str(synthesis.get("status", "not_run")),
        "latest_synthesis_id": str(synthesis.get("post_ladder_synthesis_id", "")),
        "next_capability_gap_proposal": str(synthesis.get("next_capability_gap_proposal", "")),
        "next_gap_promotable": bool(synthesis.get("next_gap_promotable", True)),
        "synthesis_summary": str(synthesis.get("summary", "")),
        "next_gap_source": str(synthesis.get("next_gap_source", "")),
        "proposal_status": str(synthesis.get("proposal_status", "")),
        "proposal_reason": str(synthesis.get("proposal_reason", "")),
        "trusted_source_provider_id": str(synthesis.get("trusted_source_provider_id", "")),
        "trusted_source_ready": bool(synthesis.get("trusted_source_ready", False)),
        "trusted_source_blocker": str(synthesis.get("trusted_source_blocker", "")),
        "trusted_source_model": str(synthesis.get("trusted_source_model", "")),
        "trusted_source_attempt_count": int(synthesis.get("trusted_source_attempt_count", 0) or 0),
        "trusted_source_failure_class": str(synthesis.get("trusted_source_failure_class", "")),
        "rejected_gap_candidate_count": int(synthesis.get("rejected_gap_candidate_count", 0) or 0),
        "latest_budget_guardrail_evaluation_id": str(
            budget_guardrail.get("budget_guardrail_evaluation_id", "")
        ),
        "budget_decision": str(budget_guardrail.get("budget_decision", "")),
        "budget_reason": str(budget_guardrail.get("budget_reason", "")),
        "budget_recommended_action": str(budget_guardrail.get("recommended_action", "")),
        "budget_prevented_overrun": bool(
            budget_guardrail.get("prevented_budget_overrun", False)
        ),
        "budget_repeated_action_count": int(budget_guardrail.get("repeated_action_count", 0) or 0),
        "budget_adaptive_hook_repeat_count": int(
            budget_guardrail.get("adaptive_hook_repeat_count", 0) or 0
        ),
        "latest_trusted_source_triage_digest_id": str(
            triage_digest.get("trusted_source_triage_digest_id", "")
        ),
        "trusted_source_triage_status": str(triage_digest.get("status", "not_run")),
        "trusted_source_triage_provider_ready": bool(triage_digest.get("provider_ready", False)),
        "trusted_source_triage_provider_model": str(triage_digest.get("provider_model", "")),
        "trusted_source_triage_citation_count": int(triage_digest.get("citation_count", 0) or 0),
        "trusted_source_triage_relevance_tags": list(
            triage_digest.get("relevance_tags", []) or []
        ),
        "trusted_source_triage_novelty_tags": list(triage_digest.get("novelty_tags", []) or []),
        "trusted_source_triage_action_suggestions": list(
            triage_digest.get("action_suggestions", []) or []
        ),
        "trusted_source_triage_blocker": str(triage_digest.get("provider_blocker", "")),
        "trusted_source_triage_failure_class": str(
            triage_digest.get("trusted_source_failure_class", "")
        ),
        "trusted_source_triage_digest_source": str(
            triage_digest.get("digest_source", "")
        ),
        "trusted_source_triage_parse_outcome": str(
            triage_digest.get("trusted_source_parse_outcome", "")
        ),
        "trusted_source_triage_attempt_count": int(
            triage_digest.get("trusted_source_attempt_count", 0) or 0
        ),
        "trusted_source_triage_repaired_output": bool(
            triage_digest.get("trusted_source_repaired_output", False)
        ),
        "trusted_source_triage_digest_usable_for_learning": bool(
            triage_digest.get("digest_usable_for_learning", False)
        ),
        "trusted_source_triage_proposal_status": str(
            triage_digest.get("proposal_status", "")
        ),
        "trusted_source_triage_rejection_reason": str(
            triage_digest.get("trusted_source_rejection_reason", "")
        ),
        "trusted_source_triage_latest_attempt_failure_class": str(
            (
                list(triage_digest.get("trusted_source_attempts", []) or [])[-1]
                if list(triage_digest.get("trusted_source_attempts", []) or [])
                else {}
            ).get("failure_class", "")
        ),
        "trusted_source_triage_priority_status": str(
            operation_proposal.get("trusted_source_triage_priority_status")
            or operation_result.get("trusted_source_triage_priority_status")
            or ""
        ),
        "trusted_source_triage_priority_reason": str(
            operation_proposal.get("trusted_source_triage_priority_reason")
            or operation_result.get("trusted_source_triage_priority_reason")
            or ""
        ),
        "trusted_source_triage_priority_blocker": str(
            operation_proposal.get("trusted_source_triage_priority_blocker")
            or operation_result.get("trusted_source_triage_priority_blocker")
            or ""
        ),
        "trusted_source_triage_role_signal": bool(
            operation_proposal.get("trusted_source_triage_role_signal")
            or operation_result.get("trusted_source_triage_role_signal")
            or False
        ),
        "trusted_source_triage_role_reason": str(
            operation_proposal.get("trusted_source_triage_role_reason")
            or operation_result.get("trusted_source_triage_role_reason")
            or ""
        ),
        "trusted_source_triage_recent_adaptive_count": int(
            operation_proposal.get("trusted_source_triage_recent_adaptive_count")
            or operation_result.get("trusted_source_triage_recent_adaptive_count")
            or 0
        ),
        "trusted_source_triage_recent_window_size": int(
            operation_proposal.get("trusted_source_triage_recent_window_size")
            or operation_result.get("trusted_source_triage_recent_window_size")
            or 0
        ),
        "trusted_source_triage_recent_threshold": int(
            operation_proposal.get("trusted_source_triage_recent_threshold")
            or operation_result.get("trusted_source_triage_recent_threshold")
            or 0
        ),
        "trusted_source_triage_governed_continuation_count": int(
            operation_proposal.get("trusted_source_triage_governed_continuation_count")
            or operation_result.get("trusted_source_triage_governed_continuation_count")
            or 0
        ),
        "trusted_source_triage_governed_continuation_threshold": int(
            operation_proposal.get("trusted_source_triage_governed_continuation_threshold")
            or operation_result.get("trusted_source_triage_governed_continuation_threshold")
            or 0
        ),
        "trusted_source_triage_governed_continuation_cadence_due": bool(
            operation_proposal.get("trusted_source_triage_governed_continuation_cadence_due")
            or operation_result.get("trusted_source_triage_governed_continuation_cadence_due")
            or False
        ),
        "trusted_source_triage_priority_provider_ready": bool(
            operation_proposal.get("trusted_source_triage_priority_provider_ready")
            or operation_result.get("trusted_source_triage_priority_provider_ready")
            or False
        ),
        "latest_human_approval_required_reason": human_reason,
        "latest_meaningful_work_id": str(meaningful.get("meaningful_work_id", "")),
        "latest_promotion_result_id": str(promotion_result.get("promotion_result_id", "")),
        "role_specialization_status": "profiled" if role_profile else "not_profiled",
        "latest_role_profile_id": str(role_profile.get("role_profile_id", "")),
        "assigned_role": str(role_profile.get("assigned_role", "")),
        "inferred_mission_domain": str(role_profile.get("inferred_mission_domain", "")),
        "current_specialization_thesis": str(role_profile.get("current_specialization_thesis", "")),
        "top_missing_skill": missing_skills[0] if missing_skills else "",
        "next_learning_pressure": str(role_profile.get("next_learning_pressure", "")),
        "latest_usefulness_evaluation_id": str(usefulness.get("usefulness_evaluation_id", "")),
        "latest_usefulness_capability_kind": str(usefulness.get("capability_kind", "")),
        "latest_usefulness": str(usefulness.get("usefulness", "")),
        "useful_later_signal_count": int(usefulness.get("useful_later_signal_count", 0) or 0),
        "strict_usefulness_gate_passed": bool(usefulness.get("strict_usefulness_gate_passed", False)),
        "strong_usefulness_signal_count": int(usefulness.get("strong_usefulness_signal_count", 0) or 0),
        "usefulness_gate_reason": str(usefulness.get("usefulness_gate_reason", "")),
        "explicit_consumption_count": int(usefulness.get("explicit_consumption_count", 0) or 0),
        "decision_change_count": int(usefulness.get("decision_change_count", 0) or 0),
        "failure_prevention_count": int(usefulness.get("failure_prevention_count", 0) or 0),
        "directive_progress_improvement_count": int(usefulness.get("directive_progress_improvement_count", 0) or 0),
        "operator_intervention_reduction_count": int(usefulness.get("operator_intervention_reduction_count", 0) or 0),
        "runtime_hook_reference_count": int(usefulness.get("runtime_hook_reference_count", 0) or 0),
        "capability_retirement_state": str(usefulness.get("retirement_state", "")),
        "latest_capability_consumption_event_id": str(
            consumption_event.get("capability_consumption_event_id", "")
        ),
        "latest_consumed_capability_kind": str(consumption_event.get("capability_kind", "")),
        "latest_consumption_entrypoint": str(consumption_event.get("entrypoint", "")),
        "latest_consumption_adapter_behaviors": list(
            consumption_event.get("runtime_capability_adapter_behaviors", []) or []
        ),
        "latest_consumption_decision_changed": bool(
            consumption_event.get("decision_changed_by_capability", False)
        ),
        "latest_consumption_failure_prevented": bool(
            consumption_event.get("repeat_failure_prevented", False)
        ),
        "latest_consumption_event_reason": str(consumption_event.get("hook_reason", "")),
        "latest_consumption_contract_id": str(
            consumption_contract.get("capability_consumption_contract_id", "")
        ),
        "latest_runtime_capability_adapter_id": str(
            runtime_adapter.get("runtime_capability_adapter_id", "")
        ),
        "latest_runtime_adapter_behavior": str(runtime_adapter.get("adapter_behavior", "")),
        "capabilities_lacking_consumption_contracts": missing_contracts,
        "capabilities_lacking_consumption_contract_count": len(missing_contracts),
        "weak_usefulness_capability_count": len(weak_capability_rows),
        "dormant_or_retired_capability_count": dormant_or_retired_count,
        "latest_capability_retirement_evaluation_id": str(
            retirement.get("capability_retirement_evaluation_id", "")
        ),
        "capability_retirement_status": str(retirement.get("retirement_status", "")),
        "capability_retirement_reason": str(retirement.get("reason", "")),
        "capability_retirement_pivot_action": str(retirement.get("pivot_action", "")),
        "weak_usefulness_repeat_count": int(retirement.get("weak_usefulness_repeat_count", 0) or 0),
        "weak_usefulness_repeat_threshold": int(
            retirement.get("weak_usefulness_repeat_threshold", 0) or 0
        ),
        "consumption_contract_missing": bool(retirement.get("consumption_contract_missing", False)),
        "latest_capability_hook_consumption_id": str(hook.get("capability_hook_consumption_id", "")),
        "latest_hook_consumed_capability_kinds": list(hook.get("consumed_capability_kinds", []) or []),
        "latest_hook_consumed_capability_count": len(list(hook.get("consumed_capability_kinds", []) or [])),
        "latest_planner_hook_references": list(hook.get("planner_hook_references", []) or []),
        "latest_planner_hook_bias_applied": bool(hook.get("planner_hook_bias_applied", False)),
        "latest_hook_decision_changed": bool(hook.get("decision_changed_by_capability", False)),
        "latest_hook_baseline_action": str(hook.get("baseline_action", "")),
        "latest_hook_final_action": str(hook.get("final_action", "")),
        "latest_hook_reason": str(hook.get("hook_reason", "")),
        "latest_curriculum_challenge_id": str(curriculum.get("curriculum_challenge_id", "")),
        "latest_curriculum_focus_skill": str(curriculum.get("focus_skill", "")),
        "latest_curriculum_gap_proposal": str(curriculum.get("next_capability_gap_proposal", "")),
        "latest_metacognitive_replay_id": str(replay.get("metacognitive_replay_id", "")),
        "latest_replay_next_missing_ability": str(replay.get("next_missing_ability", "")),
        "adaptive_learning_status": str(adaptive.get("status", "not_run")),
        "adaptive_learning_gap_proposal": str(adaptive.get("next_capability_gap_proposal", "")),
        "adaptive_learning_promotable": bool(adaptive.get("next_gap_promotable", False)),
        "adaptive_learning_source": str(adaptive.get("next_gap_source", "")),
        "latest_adaptive_learning_backoff_id": str(
            adaptive_backoff.get("adaptive_learning_backoff_id", "")
        ),
        "adaptive_learning_backoff_status": str(adaptive_backoff.get("backoff_status", "")),
        "adaptive_learning_repeated_gap_id": str(
            adaptive_backoff.get("repeated_learning_gap_id", "")
        ),
        "adaptive_learning_repeat_count": int(adaptive_backoff.get("repeat_count", 0) or 0),
        "adaptive_learning_repeat_threshold": int(
            adaptive_backoff.get("repeat_threshold", 0) or 0
        ),
        "adaptive_learning_backoff_pivot_action": str(adaptive_backoff.get("pivot_action", "")),
        "adaptive_learning_backoff_reason": str(adaptive_backoff.get("reason", "")),
        "latest_adaptive_learning_gap_family_evaluation_id": str(
            adaptive_family_backoff.get("adaptive_learning_gap_family_evaluation_id", "")
        ),
        "adaptive_learning_gap_family_id": str(adaptive_family_backoff.get("family_id", "")),
        "family_backoff_status": str(adaptive_family_backoff.get("family_backoff_status", "")),
        "family_member_gap_count": int(adaptive_family_backoff.get("member_gap_count", 0) or 0),
        "family_member_gap_ids": list(adaptive_family_backoff.get("member_gap_ids", []) or []),
        "family_repeat_count": int(adaptive_family_backoff.get("repeat_count", 0) or 0),
        "family_repeat_threshold": int(adaptive_family_backoff.get("repeat_threshold", 0) or 0),
        "family_representative_gap_id": str(
            adaptive_family_backoff.get("representative_gap_id", "")
        ),
        "family_backoff_pivot_action": str(adaptive_family_backoff.get("pivot_action", "")),
        "family_backoff_reason": str(adaptive_family_backoff.get("reason", "")),
        "latest_adaptive_learning_hook_stall_id": str(
            adaptive_hook_stall.get("adaptive_learning_hook_stall_id", "")
        ),
        "adaptive_learning_hook_stall_status": str(adaptive_hook_stall.get("hook_stall_status", "")),
        "adaptive_learning_hook_stall_repeat_count": int(
            adaptive_hook_stall.get("repeat_count", 0) or 0
        ),
        "adaptive_learning_hook_stall_repeat_threshold": int(
            adaptive_hook_stall.get("repeat_threshold", 0) or 0
        ),
        "adaptive_learning_hook_stall_pivot_action": str(adaptive_hook_stall.get("pivot_action", "")),
        "adaptive_learning_hook_stall_reason": str(adaptive_hook_stall.get("reason", "")),
        "stalled_capability_kind": str(adaptive_hook_stall.get("stalled_capability_kind", "")),
        "runtime_hook_adapter_gap_id": str(adaptive_hook_stall.get("runtime_hook_adapter_gap_id", "")),
        "runtime_hook_adapter_behavior": str(
            adaptive_hook_stall.get("runtime_hook_adapter_behavior", "")
        ),
        "governed_stale_recovery_available": bool(
            adaptive_hook_stall.get("governed_stale_recovery_available", False)
        ),
        "governed_recovery_checkpoint_id": str(
            adaptive_hook_stall.get("governed_recovery_checkpoint_id", "")
        ),
        "memory_pressure_band": str(memory_status.get("pressure_band", "unknown")),
        "memory_percent": memory_status.get("memory_percent", 0),
        "memory_used_gib": memory_status.get("used_gib", 0),
        "memory_limit_gib": memory_status.get("limit_gib", 0),
        "memory_smoothing_state": str(memory_status.get("memory_smoothing_state", "normal")),
        "latest_smoothing_action": str(memory_status.get("latest_smoothing_action", "")),
        "memory_high_watermark_percent": float(
            memory_status.get("memory_high_watermark_percent", 0.0) or 0.0
        ),
        "cooling_entered_at": str(memory_status.get("cooling_entered_at", "")),
        "cooling_exit_percent": float(memory_status.get("cooling_exit_percent", 0.0) or 0.0),
        "last_trim_result": str(memory_status.get("last_trim_result", "")),
        "cache_eviction_count": int(memory_status.get("cache_eviction_count", 0) or 0),
        "disk_spill_bytes": int(memory_status.get("disk_spill_bytes", 0) or 0),
        "oom_guard_state": str(memory_status.get("oom_guard_state", "normal")),
        "oom_guard_action": str(memory_status.get("oom_guard_action", "none")),
        "oom_guard_reason": str(memory_status.get("oom_guard_reason", "")),
        "hibernate_recommended": bool(memory_status.get("hibernate_recommended", False)),
        "service_recycle_recommended": bool(
            memory_status.get("service_recycle_recommended", False)
        ),
        "memory_headroom_gib": float(memory_status.get("memory_headroom_gib", 0.0) or 0.0),
        "last_recycle_request_id": str(memory_status.get("last_recycle_request_id", "")),
        "memory_measurement_source": str(memory_status.get("measurement_source", "")),
        "memory_measurement_age_seconds": float(memory_status.get("measurement_age_seconds", 0.0) or 0.0),
        "memory_stale_measurement": bool(memory_status.get("stale_measurement", False)),
        "memory_fresh_measurement_required": bool(
            memory_status.get("fresh_measurement_required", False)
        ),
        "memory_archive_recommended": bool(memory_status.get("archive_recommended", False)),
        "memory_restart_recommended": bool(memory_status.get("restart_recommended", False)),
        "latest_memory_pressure_status_id": str(memory_status.get("memory_pressure_status_id", "")),
        "memory_archive_status": str(memory_archive.get("status", "not_run")),
        "latest_memory_archive_id": str(memory_archive.get("memory_archive_id", "")),
        "memory_archived_count": int(memory_archive.get("archived_count", 0) or 0),
        "memory_recovered_bytes": int(memory_archive.get("recovered_bytes", 0) or 0),
        "memory_archive_attempt_status": str(memory_attempt.get("status", "not_run")),
        "memory_archive_attempt_phase": str(memory_attempt.get("phase", "")),
        "memory_archive_attempt_elapsed_ms": float(memory_attempt.get("elapsed_ms", 0.0) or 0.0),
        "memory_archive_attempt_timeout_reason": str(memory_attempt.get("timeout_reason", "")),
        "memory_archive_attempt_partial": bool(memory_status.get("partial_archive_detected", False)),
        "partial_archive_attention_required": bool(
            memory_status.get("partial_archive_attention_required", False)
        ),
        "partial_archive_cleanup_state": str(
            memory_status.get("partial_archive_cleanup_state", "not_required")
        ),
        "memory_archive_attempt_archived_count": int(memory_attempt.get("archived_count", 0) or 0),
        "ledger_compaction_attempt_id": str(
            ledger_compaction_attempt.get("ledger_compaction_attempt_id", "")
        ),
        "ledger_compaction_status": str(
            ledger_compaction_attempt.get("status")
            or memory_status.get("latest_ledger_compaction_status")
            or "not_run"
        ),
        "ledger_compaction_phase": str(
            ledger_compaction_attempt.get("phase")
            or memory_status.get("latest_ledger_compaction_phase")
            or ""
        ),
        "latest_compaction_progress_class": str(
            ledger_compaction_attempt.get("latest_compaction_progress_class")
            or memory_status.get("latest_compaction_progress_class")
            or ""
        ),
        "ledger_compaction_elapsed_ms": float(
            ledger_compaction_attempt.get("elapsed_ms")
            or memory_status.get("latest_ledger_compaction_elapsed_ms")
            or 0.0
        ),
        "ledger_compaction_timeout_reason": str(
            ledger_compaction_attempt.get("timeout_reason")
            or ledger_compaction_attempt.get("error_note")
            or memory_status.get("latest_ledger_compaction_timeout_reason")
            or ""
        ),
        "ledger_compaction_compacted_ledger_count": int(
            ledger_compaction_attempt.get("compacted_ledger_count")
            or memory_status.get("ledger_compaction_compacted_ledger_count")
            or 0
        ),
        "ledger_compaction_compacted_record_count": int(
            ledger_compaction_attempt.get("compacted_record_count")
            or memory_status.get("ledger_compaction_compacted_record_count")
            or 0
        ),
        "ledger_compaction_compacted_bytes": int(
            ledger_compaction_attempt.get("bytes_reduced")
            or memory_status.get("ledger_compaction_compacted_bytes")
            or 0
        ),
        "ledger_compaction_hot_tail_records": int(
            ledger_compaction_attempt.get("hot_tail_records")
            or memory_status.get("ledger_compaction_hot_tail_records")
            or LEDGER_COMPACTION_DEFAULT_HOT_TAIL_RECORDS
        ),
        "ledger_compaction_archive_segment_count": int(
            memory_status.get("ledger_compaction_archive_segment_count")
            or _ledger_compaction_segment_count(operator_root)
        ),
        "latest_ledger_compaction_segment_id": str(ledger_compaction_manifest.get("segment_id", "")),
        "memory_restart_recommended_after_compaction": bool(
            memory_status.get("restart_recommended_after_compaction", False)
        ),
        "memory_recovery_state": str(memory_recovery.get("recovery_state", "")),
        "latest_memory_recovery_request_id": str(memory_recovery.get("memory_recovery_request_id", "")),
        "memory_restart_recommended_after_archive_stall": bool(
            memory_status.get("restart_recommended_after_archive_stall", False)
        ),
    }


def default_autonomy_charter() -> dict[str, Any]:
    return {
        "schema_name": AUTONOMY_CHARTER_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "updated_at": _now(),
        "mission": (
            "Continuously improve Novali's reliability, operational usefulness, "
            "self-understanding, and evidence quality while preserving auditability, "
            "rollback, and operator emergency control."
        ),
        "autonomy_level": "open_ended_entity",
        "goal_source": "self_authored_goals",
        "research_scope": "local_state_plus_approved_sources",
        "runtime_model": "always_on_loop",
        "approval_model": "automated_board_with_human_emergency_stop",
        "first_operational_target": "novali_own_stack",
        "ops_authority": "full_approved_operations",
        "values": [
            "truthful evidence over hidden confidence",
            "bounded reversible action before high-blast-radius action",
            "local proof before broader operations",
            "redaction and source provenance by default",
            "operator emergency stop remains authoritative",
        ],
        "forbidden_objectives": list(DEFAULT_FORBIDDEN_OBJECTIVES),
        "approved_research_sources": [
            "local_repo_state",
            "operator_state_artifacts",
            "trusted_source_packs",
            "approved_web_research_adapter",
        ],
        "approved_operation_targets": ["novali_own_stack"],
        "approved_operation_actions": list(SUPPORTED_OPERATION_ACTIONS),
        "budgets": {
            "cycle_sleep_seconds": 60,
            "max_cycle_seconds": 300,
            "max_research_items_per_cycle": 8,
            "max_operation_runtime_seconds": 180,
            "max_consecutive_cycles": 100,
            "max_board_decision_age_seconds": 3600,
        },
        "overnight_stability_policy": {
            "enabled": False,
            "auto_execute_actions": [
                "governed_start_next_invocation",
                "approve_bounded_continuation_review",
                "promote_self_modification_candidate",
                "post_ladder_synthesis",
                "adaptive_learning_synthesis",
                "trusted_source_literature_triage_digest",
                "memory_ledger_compaction",
                "memory_pressure_archive",
            ],
            "cooldown_seconds": 60,
            "max_failed_attempts": 2,
            "require_remaining_cycle_budget": True,
            "stop_after_utc": "",
            "unattended_continuation_enabled": True,
            "unattended_high_impact_actions": [],
            "high_impact_validation_required": True,
            "adaptive_learning_usefulness_threshold": 2,
            "adaptive_learning_backoff_repeat_threshold": ADAPTIVE_LEARNING_BACKOFF_REPEAT_THRESHOLD,
            "adaptive_learning_hook_stall_threshold": ADAPTIVE_LEARNING_HOOK_STALL_THRESHOLD,
        },
        "promotion_policy": {
            "authority_target": "broad_auto_adopt",
            "require_unanimous_board": True,
            "require_tests": True,
            "require_rollback_packet": True,
            "require_canary": True,
            "allowed_adoption_targets": ["novali_own_stack"],
            "promotion_ladder": list(PROMOTION_LADDER_STAGES),
            "human_approval_required_for": [
                "emergency_stop_override",
                "failed_rollback",
                "policy_or_charter_expansion",
                "new_external_system",
                "destructive_operation",
            ],
        },
        "novelty_policy": _default_novelty_policy(),
        "emergency_stop_conditions": [
            "operator emergency stop requested",
            "charter validation failure",
            "operation targets outside approved adapter scope",
            "secret leak detected in autonomy evidence",
            "rollback evidence missing for mutating operation",
        ],
    }


def validate_autonomy_charter(charter: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    mission = str(charter.get("mission", "")).strip()
    forbidden = list(charter.get("forbidden_objectives", []) or [])
    budgets = dict(charter.get("budgets", {}) or {})
    approved_targets = list(charter.get("approved_operation_targets", []) or [])
    approved_actions = list(charter.get("approved_operation_actions", []) or [])
    overnight_policy = dict(charter.get("overnight_stability_policy", {}) or {})
    promotion_policy = dict(charter.get("promotion_policy", {}) or {})
    novelty_policy = dict(charter.get("novelty_policy", {}) or {})
    if not mission:
        errors.append("mission is required")
    if len(forbidden) < 3:
        errors.append("at least three forbidden objectives are required")
    required_forbidden_fragments = ("bypass", "secret", "protected")
    lowered = " ".join(str(item).lower() for item in forbidden)
    for fragment in required_forbidden_fragments:
        if fragment not in lowered:
            errors.append(f"forbidden objectives must cover {fragment}")
    max_cycle_seconds = int(budgets.get("max_cycle_seconds", 0) or 0)
    max_operation_seconds = int(budgets.get("max_operation_runtime_seconds", 0) or 0)
    sleep_seconds = int(budgets.get("cycle_sleep_seconds", 0) or 0)
    if max_cycle_seconds <= 0 or max_cycle_seconds > 1800:
        errors.append("max_cycle_seconds must be between 1 and 1800")
    if max_operation_seconds <= 0 or max_operation_seconds > 600:
        errors.append("max_operation_runtime_seconds must be between 1 and 600")
    if sleep_seconds < 5:
        errors.append("cycle_sleep_seconds must be at least 5")
    if bool(overnight_policy.get("enabled", False)):
        cooldown_seconds = int(overnight_policy.get("cooldown_seconds", 0) or 0)
        max_failed_attempts = int(overnight_policy.get("max_failed_attempts", 0) or 0)
        auto_actions = [
            str(item).strip()
            for item in list(overnight_policy.get("auto_execute_actions", []) or [])
            if str(item).strip()
        ]
        if cooldown_seconds < 5:
            errors.append("overnight_stability_policy.cooldown_seconds must be at least 5")
        if max_failed_attempts < 1 or max_failed_attempts > 10:
            errors.append(
                "overnight_stability_policy.max_failed_attempts must be between 1 and 10"
            )
        backoff_threshold = int(
            overnight_policy.get(
                "adaptive_learning_backoff_repeat_threshold",
                ADAPTIVE_LEARNING_BACKOFF_REPEAT_THRESHOLD,
            )
            or 0
        )
        if backoff_threshold < 1 or backoff_threshold > 50:
            errors.append(
                "overnight_stability_policy.adaptive_learning_backoff_repeat_threshold must be between 1 and 50"
            )
        hook_stall_threshold = int(
            overnight_policy.get(
                "adaptive_learning_hook_stall_threshold",
                ADAPTIVE_LEARNING_HOOK_STALL_THRESHOLD,
            )
            or 0
        )
        if hook_stall_threshold < 1 or hook_stall_threshold > 50:
            errors.append(
                "overnight_stability_policy.adaptive_learning_hook_stall_threshold must be between 1 and 50"
            )
        allowed_overnight_actions = {
            "governed_start_next_invocation",
            "approve_bounded_continuation_review",
            "promote_self_modification_candidate",
            "post_ladder_synthesis",
            "adaptive_learning_synthesis",
            "trusted_source_literature_triage_digest",
            "memory_ledger_compaction",
            "memory_pressure_archive",
        }
        unsupported_overnight_actions = sorted(set(auto_actions) - allowed_overnight_actions)
        if unsupported_overnight_actions:
            errors.append(
                "overnight_stability_policy.auto_execute_actions may only contain "
                "governed_start_next_invocation, approve_bounded_continuation_review, "
                "promote_self_modification_candidate, post_ladder_synthesis, or "
                "adaptive_learning_synthesis, trusted_source_literature_triage_digest, "
                "memory_ledger_compaction, memory_pressure_archive"
            )
        high_impact_actions = [
            str(item).strip()
            for item in list(overnight_policy.get("unattended_high_impact_actions", []) or [])
            if str(item).strip()
        ]
        unsupported_high_impact_actions = sorted(
            set(high_impact_actions) - allowed_overnight_actions
        )
        if unsupported_high_impact_actions:
            errors.append(
                "overnight_stability_policy.unattended_high_impact_actions may only contain approved overnight actions"
            )
    if "novali_own_stack" not in approved_targets:
        errors.append("novali_own_stack must be the first approved operation target")
    unsupported = sorted(set(str(item) for item in approved_actions) - set(SUPPORTED_OPERATION_ACTIONS))
    if unsupported:
        errors.append(f"unsupported operation actions: {', '.join(unsupported)}")
    if promotion_policy:
        allowed_targets = [
            str(item).strip()
            for item in list(promotion_policy.get("allowed_adoption_targets", []) or [])
            if str(item).strip()
        ]
        if str(promotion_policy.get("authority_target", "")).strip() != "broad_auto_adopt":
            errors.append("promotion_policy.authority_target must be broad_auto_adopt")
        if "novali_own_stack" not in allowed_targets:
            errors.append("promotion_policy.allowed_adoption_targets must include novali_own_stack")
        if not bool(promotion_policy.get("require_unanimous_board", False)):
            errors.append("promotion_policy.require_unanimous_board must be true")
    if novelty_policy:
        if bool(novelty_policy.get("enabled", True)):
            try:
                memory_window = int(novelty_policy.get("recent_capability_memory_window", 0) or 0)
            except (TypeError, ValueError):
                memory_window = 0
            try:
                cooldown_cycles = int(
                    novelty_policy.get("repeated_promoted_kind_cooldown_cycles", 0) or 0
                )
            except (TypeError, ValueError):
                cooldown_cycles = 0
            priority_order = [
                str(item).strip()
                for item in list(novelty_policy.get("capability_gap_priority_order", []) or [])
                if str(item).strip()
            ]
            unsupported_gaps = sorted(set(priority_order) - set(CAPABILITY_GAP_KINDS))
            if memory_window < 1 or memory_window > 100:
                errors.append(
                    "novelty_policy.recent_capability_memory_window must be between 1 and 100"
                )
            if cooldown_cycles < 1 or cooldown_cycles > 50:
                errors.append(
                    "novelty_policy.repeated_promoted_kind_cooldown_cycles must be between 1 and 50"
                )
            if not priority_order:
                errors.append("novelty_policy.capability_gap_priority_order is required")
            if unsupported_gaps:
                errors.append(
                    "novelty_policy.capability_gap_priority_order contains unsupported capability gaps: "
                    + ", ".join(unsupported_gaps)
                )
            if "promotion_packet_generation" not in priority_order:
                errors.append(
                    "novelty_policy.capability_gap_priority_order must include promotion_packet_generation"
                )
    else:
        errors.append("novelty_policy is required")
    return errors


def _high_impact_raw_context_keys(payload: Any, *, key: str = "") -> list[str]:
    lowered = key.lower()
    blocked_fragments = (
        "prompt",
        "raw_provider",
        "provider_response",
        "raw_output",
        "raw_text",
        "secret",
        "credential_value",
        "api_key",
        "token",
    )
    matches: list[str] = []
    if isinstance(payload, Mapping):
        for inner_key, inner_value in payload.items():
            matches.extend(
                _high_impact_raw_context_keys(
                    inner_value,
                    key=str(inner_key),
                )
            )
    elif isinstance(payload, (list, tuple, set)):
        for item in payload:
            matches.extend(_high_impact_raw_context_keys(item, key=key))
    elif str(payload or "").strip() and any(fragment in lowered for fragment in blocked_fragments):
        matches.append(key)
    return sorted(set(matches))


def _high_impact_check(
    checks: list[dict[str, Any]],
    blockers: list[str],
    name: str,
    passed: bool,
    blocker: str,
) -> None:
    checks.append({"name": name, "passed": bool(passed)})
    if not passed and blocker:
        blockers.append(blocker)


def _trusted_source_fallback_validation_eligible(
    operator_root: str | Path,
    operation: Mapping[str, Any],
) -> bool:
    latest_digest = _latest(operator_root, "trusted_source_literature_triage_digests")
    if (
        str(latest_digest.get("status", "")) == "completed"
        and bool(latest_digest.get("digest_usable_for_learning", False))
        and str(latest_digest.get("digest_source", "")) == "local_context_fallback"
    ):
        return True
    return bool(
        operation.get("trusted_source_triage_role_signal", False)
        and (
            str(operation.get("trusted_source_triage_latest_learning_gap", "")).strip()
            or str(operation.get("trusted_source_triage_latest_frontier_gap", "")).strip()
            or bool(operation.get("trusted_source_triage_governed_continuation_cadence_due", False))
        )
    )


def validate_high_impact_operation(
    operator_root: str | Path,
    *,
    operation: Mapping[str, Any],
    policy: Mapping[str, Any],
    decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    operation_payload = dict(operation or {})
    policy_payload = dict(policy or {})
    decision_payload = dict(decision or {})
    action = str(operation_payload.get("action", "") or "").strip()
    operation_id = str(operation_payload.get("operation_id", "") or "").strip()
    allowed_actions = {
        str(item).strip()
        for item in list(policy_payload.get("auto_execute_actions", []) or [])
        if str(item).strip()
    }
    high_impact_actions = {
        str(item).strip()
        for item in list(policy_payload.get("unattended_high_impact_actions", []) or [])
        if str(item).strip()
    }
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    _high_impact_check(
        checks,
        blockers,
        "action_is_high_impact",
        action in HIGH_IMPACT_AUTONOMY_ACTIONS,
        "operation action is not a validated high-impact action",
    )
    _high_impact_check(
        checks,
        blockers,
        "action_auto_execute_allowed",
        action in allowed_actions,
        "operation action is not enabled for auto-execution",
    )
    _high_impact_check(
        checks,
        blockers,
        "action_high_impact_opted_in",
        action in high_impact_actions,
        "operation action is not explicitly opted in for unattended high-impact approval",
    )
    _high_impact_check(
        checks,
        blockers,
        "operation_has_id",
        bool(operation_id),
        "operation has no operation_id",
    )
    _high_impact_check(
        checks,
        blockers,
        "operation_does_not_require_human",
        not bool(operation_payload.get("requires_human", False)),
        "operation requires human review",
    )
    decision_approved = bool(decision_payload.get("approved", False)) and str(
        decision_payload.get("operation_id", "") or ""
    ).strip() == operation_id
    _high_impact_check(
        checks,
        blockers,
        "board_decision_approves_operation",
        decision_approved,
        "latest board decision does not approve the high-impact operation",
    )
    target = str(operation_payload.get("target", "") or "").strip()
    _high_impact_check(
        checks,
        blockers,
        "target_scope_is_novali_owned",
        not target or target in {"novali_own_stack", "novali_runtime_adapter"},
        "operation target is outside Novali-owned approved scope",
    )
    raw_context_keys = _high_impact_raw_context_keys(operation_payload)
    secret_indicators = _secret_leak_indicators(operation_payload)
    _high_impact_check(
        checks,
        blockers,
        "operation_payload_is_redacted",
        not raw_context_keys and not secret_indicators,
        "operation payload contains raw or secret-like context",
    )

    if bool(policy_payload.get("high_impact_validation_required", True)):
        if action == "trusted_source_literature_triage_digest":
            provider_ready = bool(
                operation_payload.get("trusted_source_triage_priority_provider_ready", False)
                or operation_payload.get("trusted_source_triage_provider_ready", False)
                or operation_payload.get("trusted_source_ready", False)
                or operation_payload.get("provider_ready", False)
            )
            fallback_eligible = _trusted_source_fallback_validation_eligible(
                operator_root,
                operation_payload,
            )
            suggestions = list(
                operation_payload.get("trusted_source_triage_action_suggestions", []) or []
            )
            citation_count = int(operation_payload.get("trusted_source_triage_citation_count", 0) or 0)
            _high_impact_check(
                checks,
                blockers,
                "trusted_source_provider_or_fallback_ready",
                provider_ready or fallback_eligible,
                "trusted-source triage has no ready provider or deterministic fallback evidence",
            )
            _high_impact_check(
                checks,
                blockers,
                "trusted_source_suggestions_bounded",
                len(suggestions) <= 5,
                "trusted-source triage action suggestions exceed bounded limit",
            )
            _high_impact_check(
                checks,
                blockers,
                "trusted_source_citations_bounded",
                citation_count <= 20,
                "trusted-source triage citation metadata exceeds bounded limit",
            )
        elif action == "memory_ledger_compaction":
            memory_status = _read_json(_memory_pressure_root(operator_root) / "status_latest.json")
            latest_attempt = _latest_ledger_compaction_attempt(operator_root)
            pressure_band = str(memory_status.get("pressure_band", "unknown") or "unknown")
            progress_class = str(
                memory_status.get("latest_compaction_progress_class", "")
                or latest_attempt.get("latest_compaction_progress_class", "")
                or latest_attempt.get("progress_class", "")
            )
            compacted_count = int(
                memory_status.get("ledger_compaction_compacted_record_count", 0)
                or latest_attempt.get("compacted_record_count", 0)
                or 0
            )
            evidence_present = bool(progress_class and progress_class != "timeout_no_progress") or compacted_count > 0
            normal_with_restart = pressure_band == "normal" and bool(
                memory_status.get("restart_recommended_after_compaction", False)
            )
            _high_impact_check(
                checks,
                blockers,
                "memory_compaction_has_pressure_status",
                bool(memory_status),
                "memory compaction has no memory-pressure status evidence",
            )
            _high_impact_check(
                checks,
                blockers,
                "memory_compaction_has_bounded_evidence",
                pressure_band in {"warning", "action", "critical"} or evidence_present,
                "memory compaction has no eligible bounded ledger evidence",
            )
            _high_impact_check(
                checks,
                blockers,
                "memory_compaction_does_not_restart_under_normal_pressure",
                not normal_with_restart,
                "memory compaction recommends restart while pressure is normal",
            )
        elif action == "memory_pressure_archive":
            memory_status = _read_json(_memory_pressure_root(operator_root) / "status_latest.json")
            pressure_band = str(memory_status.get("pressure_band", "unknown") or "unknown")
            cleanup_state = str(memory_status.get("partial_archive_cleanup_state", "") or "")
            _high_impact_check(
                checks,
                blockers,
                "memory_archive_has_pressure_or_cleanup_evidence",
                pressure_band in {"warning", "action", "critical"}
                or cleanup_state.startswith("empty_abandoned_archive"),
                "memory archive has neither elevated pressure nor cleanup-only evidence",
            )
            archive_root = Path(operator_root) / "memory_archive"
            _high_impact_check(
                checks,
                blockers,
                "memory_archive_root_is_novali_owned",
                str(archive_root.resolve()).startswith(str(Path(operator_root).resolve())),
                "memory archive root is outside the Novali operator root",
            )
        elif action == "promote_self_modification_candidate":
            self_mod = _latest(operator_root, "self_modification_proposals")
            promotion_decision = _latest(operator_root, "promotion_decisions")
            promotion_result = _latest(operator_root, "promotion_results")
            rollback = _latest(operator_root, "rollback_records")
            _high_impact_check(
                checks,
                blockers,
                "promotion_packet_present",
                bool(self_mod.get("promotion_packet")) or bool(promotion_decision),
                "promotion packet evidence is missing",
            )
            _high_impact_check(
                checks,
                blockers,
                "promotion_tests_canary_rollback_ready",
                bool(promotion_decision.get("tests_passed", False))
                or str(promotion_result.get("canary_result", "")) == "passed"
                or bool(rollback.get("rollback_available", False)),
                "promotion test, canary, or rollback evidence is missing",
            )
            _high_impact_check(
                checks,
                blockers,
                "promotion_scope_is_novali_owned",
                str(promotion_decision.get("target", "novali_own_stack") or "novali_own_stack")
                == "novali_own_stack",
                "promotion target is outside Novali-owned stack",
            )
        elif action in {"post_ladder_synthesis", "adaptive_learning_synthesis"}:
            _high_impact_check(
                checks,
                blockers,
                "synthesis_is_bounded_local",
                str(operation_payload.get("target", "") or "novali_own_stack")
                in {"novali_own_stack", "novali_runtime_adapter"},
                "synthesis target is outside Novali-owned bounded scope",
            )

    result = "approved" if not blockers else "blocked"
    validation = {
        "schema_name": HIGH_IMPACT_VALIDATION_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "high_impact_validation_id": "",
        "operation_id": operation_id,
        "action": action,
        "tier": "high_impact",
        "result": result,
        "blockers": sorted(set(blockers)),
        "checks": checks,
        "check_count": len(checks),
        "policy": {
            "high_impact_validation_required": bool(
                policy_payload.get("high_impact_validation_required", True)
            ),
            "explicit_high_impact_opt_in": action in high_impact_actions,
        },
    }
    validation["high_impact_validation_id"] = _record_id("high-impact-validation", validation)
    record = _append_ledger(operator_root, "high_impact_validations", validation)
    record_high_impact_validation(record)
    return record


def load_autonomy_charter(operator_root: str | Path) -> dict[str, Any]:
    charter = _read_json(_charter_path(operator_root))
    if not charter:
        charter = default_autonomy_charter()
        _write_json(_charter_path(operator_root), charter)
    default_charter = default_autonomy_charter()
    approved_actions = list(charter.get("approved_operation_actions", []) or [])
    updated = False
    existing_actions = [str(item) for item in approved_actions]
    for required_action in (
        "governed_start_next_invocation",
        "promote_self_modification_candidate",
        "post_ladder_synthesis",
        "adaptive_learning_synthesis",
        "trusted_source_literature_triage_digest",
        "memory_ledger_compaction",
        "memory_pressure_archive",
    ):
        if required_action not in existing_actions:
            approved_actions.append(required_action)
            updated = True
    overnight_policy = dict(charter.get("overnight_stability_policy", {}) or {})
    if isinstance(overnight_policy, Mapping):
        auto_actions = [str(item) for item in list(overnight_policy.get("auto_execute_actions", []) or [])]
        if (
            "governed_start_next_invocation" in auto_actions
            and "approve_bounded_continuation_review" not in auto_actions
        ):
            auto_actions.append("approve_bounded_continuation_review")
            overnight_policy["auto_execute_actions"] = auto_actions
            charter["overnight_stability_policy"] = overnight_policy
            updated = True
        if "promote_self_modification_candidate" in auto_actions and "post_ladder_synthesis" not in auto_actions:
            auto_actions.append("post_ladder_synthesis")
            overnight_policy["auto_execute_actions"] = auto_actions
            charter["overnight_stability_policy"] = overnight_policy
            updated = True
        if "post_ladder_synthesis" in auto_actions and "adaptive_learning_synthesis" not in auto_actions:
            auto_actions.append("adaptive_learning_synthesis")
            overnight_policy["auto_execute_actions"] = auto_actions
            charter["overnight_stability_policy"] = overnight_policy
            updated = True
        if "adaptive_learning_synthesis" in auto_actions and "memory_pressure_archive" not in auto_actions:
            auto_actions.append("memory_pressure_archive")
            overnight_policy["auto_execute_actions"] = auto_actions
            charter["overnight_stability_policy"] = overnight_policy
            updated = True
        if "memory_pressure_archive" in auto_actions and "memory_ledger_compaction" not in auto_actions:
            auto_actions.append("memory_ledger_compaction")
            overnight_policy["auto_execute_actions"] = auto_actions
            charter["overnight_stability_policy"] = overnight_policy
            updated = True
        if (
            "adaptive_learning_synthesis" in auto_actions
            and "trusted_source_literature_triage_digest" not in auto_actions
        ):
            auto_actions.append("trusted_source_literature_triage_digest")
            overnight_policy["auto_execute_actions"] = auto_actions
            charter["overnight_stability_policy"] = overnight_policy
            updated = True
        if "adaptive_learning_backoff_repeat_threshold" not in overnight_policy:
            overnight_policy["adaptive_learning_backoff_repeat_threshold"] = (
                ADAPTIVE_LEARNING_BACKOFF_REPEAT_THRESHOLD
            )
            charter["overnight_stability_policy"] = overnight_policy
            updated = True
        if "adaptive_learning_hook_stall_threshold" not in overnight_policy:
            overnight_policy["adaptive_learning_hook_stall_threshold"] = (
                ADAPTIVE_LEARNING_HOOK_STALL_THRESHOLD
            )
            charter["overnight_stability_policy"] = overnight_policy
            updated = True
        if "high_impact_validation_required" not in overnight_policy:
            overnight_policy["high_impact_validation_required"] = True
            charter["overnight_stability_policy"] = overnight_policy
            updated = True
    if not isinstance(charter.get("promotion_policy"), Mapping):
        charter["promotion_policy"] = default_charter["promotion_policy"]
        updated = True
    if not isinstance(charter.get("novelty_policy"), Mapping):
        charter["novelty_policy"] = default_charter["novelty_policy"]
        updated = True
    else:
        novelty_policy = dict(charter.get("novelty_policy", {}) or {})
        default_policy = dict(default_charter["novelty_policy"])
        for key, value in default_policy.items():
            if key not in novelty_policy:
                novelty_policy[key] = value
                updated = True
        if not list(novelty_policy.get("capability_gap_priority_order", []) or []):
            novelty_policy["capability_gap_priority_order"] = list(CAPABILITY_GAP_KINDS)
            updated = True
        charter["novelty_policy"] = novelty_policy
    if updated:
        charter["approved_operation_actions"] = approved_actions
        charter["updated_at"] = _now()
        _write_json(_charter_path(operator_root), charter)
    return charter


def initialize_autonomy_state(operator_root: str | Path) -> dict[str, Any]:
    root = autonomy_root(operator_root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "ledgers").mkdir(parents=True, exist_ok=True)
    charter = load_autonomy_charter(operator_root)
    errors = validate_autonomy_charter(charter)
    status = _read_json(_status_path(operator_root))
    if not status:
        status = {
            "schema_name": AUTONOMY_STATUS_SCHEMA_NAME,
            "schema_version": AUTONOMY_SCHEMA_VERSION,
            "generated_at": _now(),
            "runtime_state": "paused",
            "active": False,
            "emergency_stop": False,
            "loop_iteration": 0,
            "latest_cycle_id": "",
            "latest_goal_id": "",
            "latest_board_decision_id": "",
            "latest_operation_proposal_id": "",
            "charter_valid": not errors,
            "charter_errors": errors,
            "message": "Autonomy initialized in paused state.",
        }
        _write_json(_status_path(operator_root), status)
    return autonomy_status(operator_root)


def _update_status(operator_root: str | Path, updates: Mapping[str, Any]) -> dict[str, Any]:
    status = _read_json(_status_path(operator_root))
    if not status:
        status = {
            "schema_name": AUTONOMY_STATUS_SCHEMA_NAME,
            "schema_version": AUTONOMY_SCHEMA_VERSION,
        }
    status.update(dict(updates))
    status["generated_at"] = _now()
    _write_json(_status_path(operator_root), status)
    return status


def autonomy_status(operator_root: str | Path) -> dict[str, Any]:
    charter = load_autonomy_charter(operator_root)
    errors = validate_autonomy_charter(charter)
    status = _read_json(_status_path(operator_root))
    goals = _read_ledger(operator_root, "goals", limit=100)
    active_goals = [item for item in goals if str(item.get("status", "")) in {"active", "selected"}]
    latest_trusted_source_triage_digest = _latest(
        operator_root, "trusted_source_literature_triage_digests"
    )
    overnight_policy = dict(charter.get("overnight_stability_policy", {}) or {})
    latest_high_impact_validation = _latest(operator_root, "high_impact_validations")
    latest_high_impact_blockers = list(
        latest_high_impact_validation.get("blockers", []) or []
    )
    if latest_trusted_source_triage_digest and not bool(
        latest_trusted_source_triage_digest.get(
            "trusted_source_triage_telemetry_emitted", False
        )
    ):
        latest_trusted_source_triage_digest = ensure_trusted_source_triage_telemetry_emitted(
            operator_root,
            latest_trusted_source_triage_digest,
        )
    payload = {
        "schema_name": AUTONOMY_STATUS_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "generated_at": _now(),
        "runtime_state": str(status.get("runtime_state", "paused")),
        "active": bool(status.get("active", False)),
        "emergency_stop": bool(status.get("emergency_stop", False)),
        "loop_iteration": int(status.get("loop_iteration", 0) or 0),
        "charter_valid": not errors,
        "charter_errors": errors,
        "charter": {
            "mission": str(charter.get("mission", "")),
            "autonomy_level": str(charter.get("autonomy_level", "")),
            "goal_source": str(charter.get("goal_source", "")),
            "runtime_model": str(charter.get("runtime_model", "")),
            "approval_model": str(charter.get("approval_model", "")),
            "ops_authority": str(charter.get("ops_authority", "")),
        },
        "active_goal_count": len(active_goals),
        "latest_goal": _latest(operator_root, "goals"),
        "latest_research": _latest(operator_root, "research_evidence"),
        "latest_plan": _latest(operator_root, "plan_candidates"),
        "latest_operation_proposal": _latest_open_operation_proposal(operator_root),
        "latest_board_decision": _latest(operator_root, "approval_board_decisions"),
        "latest_cycle": _latest(operator_root, "cycles"),
        "latest_self_modification": _latest(operator_root, "self_modification_proposals"),
        "latest_promotion_decision": _latest(operator_root, "promotion_decisions"),
        "latest_promotion_result": _latest(operator_root, "promotion_results"),
        "latest_meaningful_work": _latest(operator_root, "meaningful_work_evaluations"),
        "latest_novelty_evaluation": _latest(operator_root, "capability_novelty_evaluations"),
        "latest_post_ladder_synthesis": _latest(operator_root, "post_ladder_syntheses"),
        "latest_role_specialization_profile": _latest(operator_root, "role_specialization_profiles"),
        "latest_capability_usefulness": _latest(operator_root, "capability_usefulness_evaluations"),
        "latest_capability_hook_consumption": _latest(operator_root, "capability_hook_consumptions"),
        "latest_capability_consumption_contract": _latest(
            operator_root, "capability_consumption_contracts"
        ),
        "latest_runtime_capability_adapter": _latest(operator_root, "runtime_capability_adapters"),
        "latest_capability_consumption_event": _latest(
            operator_root, "capability_consumption_events"
        ),
        "latest_capability_retirement_evaluation": _latest(
            operator_root, "capability_retirement_evaluations"
        ),
        "latest_execution_budget_guardrail": _latest(
            operator_root, "execution_budget_guardrail_evaluations"
        ),
        "latest_trusted_source_literature_triage_digest": latest_trusted_source_triage_digest,
        "high_impact_policy_state": {
            "high_impact_validation_required": bool(
                overnight_policy.get("high_impact_validation_required", True)
            ),
            "unattended_high_impact_actions": [
                str(item).strip()
                for item in list(overnight_policy.get("unattended_high_impact_actions", []) or [])
                if str(item).strip()
            ],
        },
        "latest_high_impact_validation": latest_high_impact_validation,
        "latest_high_impact_blocker": (
            str(latest_high_impact_blockers[0]) if latest_high_impact_blockers else ""
        ),
        "latest_self_curriculum_challenge": _latest(operator_root, "self_curriculum_challenges"),
        "latest_metacognitive_replay": _latest(operator_root, "metacognitive_replays"),
        "latest_adaptive_learning_synthesis": _latest(operator_root, "adaptive_learning_syntheses"),
        "latest_adaptive_learning_backoff": _latest(
            operator_root, "adaptive_learning_backoff_evaluations"
        ),
        "latest_adaptive_learning_gap_family": _latest(
            operator_root, "adaptive_learning_gap_family_evaluations"
        ),
        "latest_adaptive_learning_hook_stall": _latest(
            operator_root, "adaptive_learning_hook_stall_evaluations"
        ),
        "memory_pressure": _latest_memory_pressure_status(operator_root),
        "latest_memory_archive": _latest(operator_root, "memory_archive_manifests"),
        "latest_memory_archive_attempt": _latest_memory_archive_attempt(operator_root),
        "latest_ledger_compaction_attempt": _latest_ledger_compaction_attempt(operator_root),
        "latest_ledger_compaction_segment_manifest": _latest(
            operator_root, "ledger_compaction_segment_manifests"
        ),
        "latest_memory_recovery_request": _latest(operator_root, "memory_recovery_requests"),
        "latest_governed_invocation_window": _latest_governed_invocation_window(operator_root),
        "autonomous_growth": _autonomous_growth_summary(operator_root),
        "latest_operation_result": _latest(operator_root, "operation_results"),
        "overnight_auto_executor": dict(status.get("overnight_auto_executor", {})),
        "message": str(status.get("message", "")),
    }
    return _redact_autonomy_value(payload)


def list_autonomy_goals(operator_root: str | Path, *, limit: int = 50) -> dict[str, Any]:
    return {
        "schema_name": "AutonomousGoalList",
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "generated_at": _now(),
        "goals": _read_ledger(operator_root, "goals", limit=limit),
    }


def _goal_violates_charter(goal: Mapping[str, Any], charter: Mapping[str, Any]) -> list[str]:
    text = " ".join(
        [
            str(goal.get("title", "")),
            str(goal.get("intent", "")),
            str(goal.get("success_criteria", "")),
        ]
    ).lower()
    violations: list[str] = []
    for forbidden in list(charter.get("forbidden_objectives", []) or []):
        words = [word for word in str(forbidden).lower().replace(",", " ").split() if len(word) > 5]
        if words and all(word in text for word in words[:2]):
            violations.append(str(forbidden))
    return violations


def _self_authored_goal(operator_root: str | Path, observations: Mapping[str, Any]) -> dict[str, Any]:
    shell = dict(observations.get("shell_state", {}) or {})
    llm_status = dict(observations.get("llm_status", {}) or {})
    runtime = dict(shell.get("runtime", {}) or {})
    goal = {
        "schema_name": AUTONOMY_GOAL_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "goal_id": "",
        "status": "active",
        "source": "self_authored",
        "priority": "high",
        "risk_class": "bounded_novali_stack",
        "title": "Improve Novali local LLM and stack reliability evidence",
        "intent": (
            "Strengthen Novali's ability to observe its own Web Shell, local LLM sidecar, "
            "Docker stack, and autonomy evidence so future operations are safer and easier to audit."
        ),
        "success_criteria": [
            "Novali can report Web Shell and local LLM availability from persisted evidence.",
            "Any operation proposal includes rollback and verification notes.",
            "Autonomy evidence remains redacted and append-only.",
        ],
        "observation_summary": {
            "runtime_status": str(runtime.get("run_status", "")),
            "llm_status": str(llm_status.get("status", "")),
            "llm_model": str(llm_status.get("model", "")),
            "compose_stack_expected": True,
        },
    }
    goal["goal_id"] = _record_id("goal", goal)
    violations = _goal_violates_charter(goal, load_autonomy_charter(operator_root))
    if violations:
        goal["status"] = "rejected"
        goal["rejection_reasons"] = violations
    return goal


def _local_research_bundle(
    *,
    operator_root: str | Path,
    package_root: str | Path,
    state_root: str | Path,
    goal: Mapping[str, Any],
    observations: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = {
        "schema_name": RESEARCH_REQUEST_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "research_request_id": "",
        "goal_id": str(goal.get("goal_id", "")),
        "scope": "local_state_plus_approved_sources",
        "queries": [
            "Inspect Novali Web Shell state and runtime posture.",
            "Inspect local LLM provider status.",
            "Inspect Docker Compose LLM stack presence.",
            "Inspect autonomy charter and ledgers.",
        ],
    }
    request["research_request_id"] = _record_id("research-request", request)
    root = Path(package_root)
    compose_path = root / "docker-compose.llm.yml"
    shell_docs = [
        root / "LAUNCH_MATRIX.md",
        root / "STANDALONE_DOCKER_QUICKSTART.md",
        root / "OPERATOR_SHELL.md",
    ]
    citations = []
    for path in shell_docs:
        citations.append(
            {
                "source_id": path.name,
                "source_type": "local_file",
                "path_hint": str(path),
                "present": path.exists(),
            }
        )
    citations.append(
        {
            "source_id": "docker-compose.llm.yml",
            "source_type": "local_file",
            "path_hint": str(compose_path),
            "present": compose_path.exists(),
        }
    )
    evidence = {
        "schema_name": RESEARCH_EVIDENCE_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "research_bundle_id": "",
        "research_request_id": request["research_request_id"],
        "goal_id": str(goal.get("goal_id", "")),
        "source_scope": "local_repo_state",
        "citations": citations,
        "findings": [
            "Canonical authority remains governed-execution based; autonomy must be layered above it.",
            "The local LLM sidecar is represented by docker-compose.llm.yml when present.",
            "Autonomy evidence is stored under operator-owned state, not hidden runtime memory.",
        ],
        "observations": {
            "operator_root_hint": str(operator_root),
            "state_root_hint": str(state_root),
            "llm_status": observations.get("llm_status", {}),
            "governed_readiness": observations.get("governed_readiness", {}),
            "current_directive": observations.get("current_directive", {}),
            "long_run_state": observations.get("long_run_state", {}),
            "shell_runtime": dict(dict(observations.get("shell_state", {}) or {}).get("runtime", {})),
        },
        "redaction_status": "redacted",
    }
    evidence["research_bundle_id"] = _record_id("research", evidence)
    return request, evidence


def _plan_candidate(
    goal: Mapping[str, Any],
    research: Mapping[str, Any],
    *,
    operator_root: str | Path,
) -> dict[str, Any]:
    observations = dict(research.get("observations", {}) or {})
    governed_readiness = dict(observations.get("governed_readiness", {}) or {})
    current_directive = dict(observations.get("current_directive", {}) or {})
    state_root_hint = str(observations.get("state_root_hint", "") or "").strip()
    long_run_payload = dict(observations.get("long_run_state", {}) or {})
    long_run = dict(long_run_payload.get("long_run", {}) or {})
    long_run_operator_state = dict(long_run_payload.get("operator_state", {}) or {})
    long_run_intervention = dict(long_run_payload.get("intervention", {}) or {})
    governed_ready = bool(governed_readiness.get("can_launch", False))
    directive_loaded = bool(dict(governed_readiness.get("operator_state", {}) or {}).get("directive_loaded", False)) or bool(
        current_directive.get("directive_selected", False)
    )
    long_run_stale_recovery_available = (
        bool(long_run.get("stale_recovery_available", False))
        or str(long_run.get("lease_state", "")) == "stale_recoverable"
        or str(dict(long_run_payload.get("operator_guidance", {}) or {}).get("state_family", ""))
        == "stale_recovery"
    )
    long_run_blocked_review = (
        bool(long_run_operator_state.get("review_required", False))
        or bool(long_run_intervention.get("required", False))
        or int(long_run_intervention.get("blocking_review_count", 0) or 0) > 0
    )
    governed_recovery_checkpoint_id = str(
        long_run.get("latest_checkpoint_id")
        or dict(long_run.get("latest_checkpoint", {}) or {}).get("checkpoint_id")
        or ""
    )
    governed_recovery_available = bool(
        directive_loaded and long_run_stale_recovery_available and not long_run_blocked_review
    )
    needs_promotion_packet = _latest_growth_needs_promotion_packet(operator_root)
    growth_pivot = _growth_pivot_requested(operator_root)
    growth_requested = needs_promotion_packet or growth_pivot
    churn_state = _autonomy_churn_classifier(operator_root)
    churn_breaker_active = str(churn_state.get("churn_state", "")) == "active"
    memory_status = memory_pressure_status(operator_root, persist=True)
    memory_band = str(memory_status.get("pressure_band", "normal"))
    memory_smoothing_state = str(memory_status.get("memory_smoothing_state", "normal"))
    memory_smoothing_active = memory_smoothing_state in {"cooling", "spilling"}
    oom_guard_state = str(memory_status.get("oom_guard_state", "normal"))
    oom_guard_blocks_start = oom_guard_state in {"hibernate_required", "recycle_required"}
    memory_archive_needed = memory_band in {"warning", "action", "critical"} or memory_smoothing_active
    if oom_guard_blocks_start:
        memory_archive_needed = False
    _load_promoted_capability_hooks(operator_root)
    consumption_remediation = _capability_retirement_evaluation(operator_root, persist=True)
    consumption_remediation_status = str(consumption_remediation.get("retirement_status", ""))
    consumption_remediation_pivot = str(consumption_remediation.get("pivot_action", ""))
    consumption_remediation_blocks_learning = consumption_remediation_status in {
        "dormant",
        "needs_contract",
        "needs_followup",
    }
    adaptive_backoff = _adaptive_learning_backoff_evaluation(operator_root, persist=True)
    adaptive_backoff_status = str(adaptive_backoff.get("backoff_status", ""))
    adaptive_family_backoff = _adaptive_learning_gap_family_evaluation(
        operator_root,
        exact_backoff=adaptive_backoff,
        persist=True,
    )
    adaptive_family_backoff_status = str(adaptive_family_backoff.get("family_backoff_status", ""))
    adaptive_backoff_promote = (
        growth_requested
        and adaptive_backoff_status == "promote_gap"
        and not memory_archive_needed
    )
    adaptive_family_backoff_promote = (
        growth_requested
        and not adaptive_backoff_promote
        and adaptive_family_backoff_status == "promote_family_gap"
        and not memory_archive_needed
    )
    hook_adapter_candidate = _runtime_hook_adapter_candidate(operator_root)
    adaptive_hook_stall = _adaptive_learning_hook_stall_evaluation(
        operator_root,
        governed_recovery_available=governed_recovery_available,
        governed_recovery_checkpoint_id=governed_recovery_checkpoint_id,
        hook_adapter_candidate=hook_adapter_candidate,
        persist=True,
    )
    adaptive_hook_stall_status = str(adaptive_hook_stall.get("hook_stall_status", ""))
    adaptive_hook_stall_pivot_action = str(adaptive_hook_stall.get("pivot_action", ""))
    latest_synthesis = _latest(operator_root, "post_ladder_syntheses")
    latest_adaptive = _latest(operator_root, "adaptive_learning_syntheses")
    trusted_source_attempt_count = max(
        int(latest_synthesis.get("trusted_source_attempt_count", 0) or 0),
        int(latest_adaptive.get("trusted_source_attempt_count", 0) or 0),
    )
    safe_growth_available, novelty_preview = _safe_capability_growth_available(operator_root)
    synthesis_needed, synthesis_preview = _post_ladder_synthesis_needed(
        operator_root,
        growth_requested=growth_requested,
    )
    if synthesis_preview:
        novelty_preview = synthesis_preview
    adaptive_requested = _adaptive_learning_needed(operator_root, growth_requested=growth_requested)
    adaptive_needed = (
        adaptive_requested
        and not (governed_ready and directive_loaded and not growth_pivot)
        and not adaptive_backoff_promote
        and not adaptive_family_backoff_promote
        and not consumption_remediation_blocks_learning
    )
    triage_priority = _trusted_source_literature_triage_priority(
        operator_root,
        growth_requested=growth_requested,
    )
    triage_cadence_due = bool(
        triage_priority.get("trusted_source_triage_governed_continuation_cadence_due", False)
    )
    charter = load_autonomy_charter(operator_root)
    overnight_policy = dict(charter.get("overnight_stability_policy", {}) or {})
    unattended_high_impact_actions = {
        str(item).strip()
        for item in list(overnight_policy.get("unattended_high_impact_actions", []) or [])
        if str(item).strip()
    }
    trusted_source_unattended_enabled = (
        "trusted_source_literature_triage_digest" in unattended_high_impact_actions
    )
    librarian_gap = _librarian_gap_request(
        operator_root,
        state_root=state_root_hint,
        role_profile=_latest(operator_root, "role_specialization_profiles"),
        trusted_source_priority=triage_priority,
        trusted_source_unattended_enabled=trusted_source_unattended_enabled,
        persist=False,
    )
    librarian_gap_active = bool(librarian_gap.get("librarian_gap_request", False))
    triage_hard_blocker = ""
    if memory_archive_needed:
        triage_hard_blocker = f"memory pressure band {memory_band} requires memory recovery first"
    elif (
        governed_ready
        and directive_loaded
        and not growth_pivot
        and (not triage_cadence_due or not trusted_source_unattended_enabled)
        and not bool(librarian_gap.get("directive_dossier_gap", False))
    ):
        triage_hard_blocker = (
            "governed continuation is ready and trusted-source unattended high-impact opt-in is not active"
            if triage_cadence_due
            else "governed continuation is ready and growth pivot is not active"
        )
    elif adaptive_backoff_promote or adaptive_family_backoff_promote:
        triage_hard_blocker = "adaptive-learning backoff promotion is higher priority"
    elif consumption_remediation_blocks_learning:
        triage_hard_blocker = "capability consumption remediation is higher priority"
    triage_priority_status = str(triage_priority.get("trusted_source_triage_priority_status", "blocked"))
    if librarian_gap_active and not triage_hard_blocker:
        triage_priority_status = "eligible"
    if triage_hard_blocker:
        triage_priority_status = "blocked"
    triage_needed = (
        triage_priority_status == "eligible"
        and not triage_hard_blocker
        and (adaptive_needed or triage_cadence_due or librarian_gap_active)
    )
    if triage_needed:
        triage_priority_status = "selected"
        if librarian_gap_active:
            librarian_gap = _append_ledger(
                operator_root,
                "librarian_gap_requests",
                librarian_gap,
            )
    if adaptive_backoff_promote or adaptive_family_backoff_promote:
        repeated_gap = (
            str(adaptive_backoff.get("repeated_learning_gap_id", ""))
            if adaptive_backoff_promote
            else str(adaptive_family_backoff.get("representative_gap_id", ""))
        )
        if repeated_gap:
            novelty_preview = dict(novelty_preview)
            novelty_preview["selected_capability_kind"] = repeated_gap
            novelty_preview["capability_gap_id"] = repeated_gap
            novelty_preview["novelty_status"] = "novel"
            novelty_preview["cooldown_reason"] = (
                str(adaptive_backoff.get("reason", ""))
                if adaptive_backoff_promote
                else str(adaptive_family_backoff.get("reason", ""))
            )
    elif (
        adaptive_hook_stall_status == "stalled"
        and adaptive_hook_stall_pivot_action == "promote_self_modification_candidate"
        and str(adaptive_hook_stall.get("runtime_hook_adapter_gap_id", ""))
    ):
        adapter_gap = str(adaptive_hook_stall.get("runtime_hook_adapter_gap_id", ""))
        novelty_preview = dict(novelty_preview)
        novelty_preview["selected_capability_kind"] = adapter_gap
        novelty_preview["capability_gap_id"] = adapter_gap
        novelty_preview["novelty_status"] = "novel"
        novelty_preview["cooldown_reason"] = str(adaptive_hook_stall.get("reason", ""))
    should_promote_capability = (
        growth_requested
        and safe_growth_available
        and not synthesis_needed
        and not adaptive_needed
    ) or adaptive_backoff_promote or adaptive_family_backoff_promote
    if churn_breaker_active and bool(churn_state.get("suppress_duplicate_promotion", False)):
        should_promote_capability = False
    directive_outcome_cadence = _recent_governed_directive_outcome_cadence(
        operator_root
    )
    directive_outcome_nudge_due = bool(
        governed_ready
        and directive_loaded
        and not growth_pivot
        and not triage_needed
        and directive_outcome_cadence.get("directive_outcome_nudge_due", False)
    )
    churn_breaker_action = ""
    if churn_breaker_active and not memory_archive_needed:
        churn_breaker_action = (
            "governed_start_next_invocation"
            if governed_ready and directive_loaded and not growth_pivot
            else "post_ladder_synthesis"
        )
    pre_budget_action = (
        "memory_ledger_compaction"
        if memory_archive_needed
        else consumption_remediation_pivot
        if (
            consumption_remediation_blocks_learning
            and consumption_remediation_pivot
            and adaptive_requested
            and not (governed_ready and directive_loaded and not growth_pivot)
        )
        else "governed_start_next_invocation"
        if directive_outcome_nudge_due
        else churn_breaker_action
        if churn_breaker_action
        else "trusted_source_literature_triage_digest"
        if triage_needed
        else "adaptive_learning_synthesis"
        if adaptive_needed
        else "post_ladder_synthesis"
        if synthesis_needed
        else
        "promote_self_modification_candidate"
        if should_promote_capability
        else "governed_start_next_invocation"
        if governed_ready and directive_loaded and not growth_pivot
        else "novali_stack_status"
    )
    budget_guardrail = _execution_budget_guardrail_evaluation(
        operator_root,
        baseline_action=pre_budget_action,
        memory_band=memory_band,
        selected_capability_kind=str(novelty_preview.get("selected_capability_kind", "")),
        adaptive_hook_stall=adaptive_hook_stall,
        trusted_source_attempt_count=trusted_source_attempt_count,
        persist=True,
    )
    recommended_action = str(budget_guardrail.get("recommended_action", pre_budget_action) or pre_budget_action)
    baseline_action = pre_budget_action
    hook_consumption = _apply_capability_planner_hooks(
        operator_root=operator_root,
        baseline_action=baseline_action,
        memory_band=memory_band,
        novelty_preview=novelty_preview,
        growth_pivot=growth_pivot,
        safe_growth_available=safe_growth_available,
        synthesis_needed=synthesis_needed,
        adaptive_needed=adaptive_needed,
        governed_ready=governed_ready,
        directive_loaded=directive_loaded,
        adaptive_backoff_status=(
            "promote_family_gap" if adaptive_family_backoff_promote else adaptive_backoff_status
        ),
        adaptive_hook_stall=adaptive_hook_stall,
        budget_guardrail=budget_guardrail,
    )
    recommended_action = str(hook_consumption.get("final_action", baseline_action) or baseline_action)
    if churn_breaker_action and recommended_action == "promote_self_modification_candidate":
        recommended_action = churn_breaker_action
    oom_guard_blocked_action = ""
    if oom_guard_blocks_start:
        oom_guard_blocked_action = (
            recommended_action
            if recommended_action != "novali_stack_status"
            else pre_budget_action
            if pre_budget_action != "novali_stack_status"
            else "memory_ledger_compaction"
            if oom_guard_state == "recycle_required" and memory_band in {"warning", "action", "critical"}
            else ""
        )
        recommended_action = "novali_stack_status"
    memory_smoothing_blocked_action = (
        "governed_start_next_invocation"
        if memory_smoothing_active
        and not oom_guard_blocks_start
        and governed_ready
        and directive_loaded
        and not growth_pivot
        else ""
    )
    if (
        memory_smoothing_active
        and not oom_guard_blocks_start
        and recommended_action == "governed_start_next_invocation"
    ):
        recommended_action = "memory_ledger_compaction"
        baseline_action = "memory_ledger_compaction"
    hard_memory_recovery_priority_applied = False
    memory_recovery_reason = ""
    memory_recovery_action = ""
    if (
        memory_band in {"warning", "action", "critical"}
        and not oom_guard_blocks_start
        and (
            pre_budget_action == "memory_ledger_compaction"
            or recommended_action == "memory_ledger_compaction"
            or str(budget_guardrail.get("recommended_action", "")) == "memory_ledger_compaction"
            or str(hook_consumption.get("budget_recommended_action", "")) == "memory_ledger_compaction"
        )
        and recommended_action != "memory_ledger_compaction"
    ):
        hard_memory_recovery_priority_applied = True
        memory_recovery_action = "memory_ledger_compaction"
        memory_recovery_reason = (
            f"memory pressure band {memory_band} requires ledger compaction before "
            "dependency-fingerprint or governed-continuation hook bias can run"
        )
        recommended_action = "memory_ledger_compaction"
    elif (
        memory_band in {"warning", "action", "critical"}
        and not oom_guard_blocks_start
        and recommended_action == "memory_ledger_compaction"
    ):
        hard_memory_recovery_priority_applied = True
        memory_recovery_action = "memory_ledger_compaction"
        memory_recovery_reason = (
            f"memory pressure band {memory_band} keeps ledger compaction as the hard recovery action"
        )
    suppressed_actions = list(hook_consumption.get("suppressed_actions", []) or [])
    suppressed_action = str(churn_state.get("suppressed_action", "") or "")
    if churn_breaker_active and suppressed_action and suppressed_action not in suppressed_actions:
        suppressed_actions.append(suppressed_action)
    if churn_breaker_active:
        telemetry_payload = dict(churn_state)
        telemetry_payload["recommended_breaker_action"] = (
            churn_breaker_action or recommended_action
        )
        telemetry_payload["result"] = "selected" if churn_breaker_action else "blocked"
        record_autonomy_churn_breaker(telemetry_payload)
    plan = {
        "schema_name": PLAN_CANDIDATE_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "plan_candidate_id": "",
        "goal_id": str(goal.get("goal_id", "")),
        "research_bundle_id": str(research.get("research_bundle_id", "")),
        "status": "board_review_pending",
        "title": (
            "Compact cold autonomy ledgers before memory pressure reaches the container limit"
            if recommended_action == "memory_ledger_compaction"
            else
            "Archive cold evidence before memory pressure reaches the container limit"
            if recommended_action == "memory_pressure_archive"
            else
            "Generate and promote a broker-ready autonomy capability packet"
            if recommended_action == "promote_self_modification_candidate"
            else
            "Digest trusted-source literature into bounded role-learning evidence"
            if recommended_action == "trusted_source_literature_triage_digest"
            else
            "Run adaptive role specialization and learning replay"
            if recommended_action == "adaptive_learning_synthesis"
            else
            "Synthesize promoted capability evidence and propose the next growth gap"
            if recommended_action == "post_ladder_synthesis"
            else
            "Continue approved governed directive through autonomy bridge"
            if recommended_action == "governed_start_next_invocation"
            else "Audit and improve Novali stack reliability evidence"
        ),
        "steps": (
            [
                "Record current cgroup/process memory pressure evidence.",
                "Move cold append-only autonomy ledger records into compressed hashed segments.",
                "Keep a hot tail in each compacted ledger for normal status reads.",
                "Record a recovery request if memory remains above the action threshold.",
            ]
            if recommended_action == "memory_ledger_compaction"
            else
            [
                "Record current cgroup/process memory pressure evidence.",
                "Archive cold JSON, JSONL, log, text, and markdown artifacts into persisted operator state.",
                "Preserve latest/session-active and credential-like files in place.",
                "Record a recovery request if memory remains above the action threshold.",
            ]
            if recommended_action == "memory_pressure_archive"
            else
            [
                "Generate a self-modification promotion packet in writable Novali-owned state.",
                "Attach changed-file manifest, tests, rollback evidence, and canary commands.",
                "Ask the approval board to review the packet for auto-adoption eligibility.",
                "Execute only through the operations broker and persist PromotionResult evidence.",
            ]
            if recommended_action == "promote_self_modification_candidate"
            else
            [
                "Assemble a compact redacted trusted-source triage context.",
                "Request one bounded structured digest from the configured openai_api provider.",
                "Persist citation summaries, relevance tags, weak claims, and action suggestions as state evidence.",
                "Feed digest evidence into later adaptive learning and synthesis without mutating the charter.",
            ]
            if recommended_action == "trusted_source_literature_triage_digest"
            else
            [
                "Refresh the role specialization profile from directive and autonomy evidence.",
                "Classify promoted capability usefulness from later-cycle signals.",
                "Persist a bounded self-curriculum challenge and metacognitive replay.",
                "Keep any learning-derived gap as evidence until promotion gates and usefulness threshold pass.",
            ]
            if recommended_action == "adaptive_learning_synthesis"
            else
            [
                "Summarize recently promoted autonomy capability records.",
                "Classify each promoted capability using persisted canary, rollback, and meaningful-work evidence.",
                "Persist a bounded next capability-gap proposal without mutating the charter.",
                "Keep the proposal as evidence until a later board-gated promotion cycle adopts it.",
            ]
            if recommended_action == "post_ladder_synthesis"
            else
            [
                "Record lightweight governed readiness evidence.",
                "Propose a bounded governed-start operation through the existing launch gate.",
                "Require approval-board evidence before spawning the next governed invocation.",
                "Persist the governed-start attempt result as autonomy operation evidence.",
            ]
            if recommended_action == "governed_start_next_invocation"
            else [
                "Collect Web Shell and LLM provider status.",
                "Confirm Docker Compose stack files and model availability evidence.",
                "Propose a read-only stack status operation before any mutating operation.",
                "Require board approval before restart, model pull, backup, or self-promotion.",
            ]
        ),
        "expected_artifacts": [
            "AutonomyCycleRecord",
            "ResearchEvidenceBundle",
            "OperationProposal",
            "ApprovalBoardDecision",
            "LedgerCompactionAttempt"
            if recommended_action == "memory_ledger_compaction"
            else
            "MemoryArchiveManifest"
            if recommended_action == "memory_pressure_archive"
            else
            "PromotionResult"
            if recommended_action == "promote_self_modification_candidate"
            else "TrustedSourceLiteratureTriageDigest"
            if recommended_action == "trusted_source_literature_triage_digest"
            else "AdaptiveLearningSynthesis"
            if recommended_action == "adaptive_learning_synthesis"
            else "PostLadderSynthesis"
            if recommended_action == "post_ladder_synthesis"
            else "NovaliGovernedStartAttempt"
            if recommended_action == "governed_start_next_invocation"
            else "OperationResult",
        ],
        "directive_progress_objective": (
            "Reduce Novali process pressure before launching additional governed directive work."
            if recommended_action in {"memory_ledger_compaction", "memory_pressure_archive"}
            else
            "Convert the current promotion blocker into an executable capability-growth operation."
            if recommended_action == "promote_self_modification_candidate"
            else
            "Convert trusted-source gaps into compact citation-aware role-learning evidence."
            if recommended_action == "trusted_source_literature_triage_digest"
            else
            "Convert weak learning evidence into a bounded self-curriculum objective."
            if recommended_action == "adaptive_learning_synthesis"
            else
            "Summarize completed novelty-ladder growth and propose the next capability gap."
            if recommended_action == "post_ladder_synthesis"
            else
            "Advance the loaded directive through a governed invocation."
            if recommended_action == "governed_start_next_invocation"
            else "Restore enough launch evidence for a directive to become actionable."
        ),
        "capability_growth_objective": (
            "Convert successful self-improvement work into a promotion packet with tests, rollback, and canary evidence."
        ),
        "growth_pivot_requested": growth_pivot,
        "directive_outcome_nudge_due": directive_outcome_nudge_due,
        "directive_track_selection_policy": (
            "planner_selected_churn_breaker"
            if churn_breaker_active and recommended_action == "governed_start_next_invocation"
            else "planner_selected"
            if directive_outcome_nudge_due
            else "not_due"
        ),
        "directive_track_advancement_required": bool(
            directive_outcome_nudge_due
            or (
                churn_breaker_active
                and recommended_action == "governed_start_next_invocation"
            )
        ),
        "directive_track_depth_target": (
            "deepen_existing_or_next_concrete_track"
            if churn_breaker_active and recommended_action == "governed_start_next_invocation"
            else ""
        ),
        "churn_state": str(churn_state.get("churn_state", "clear")),
        "churn_repeat_count": int(churn_state.get("churn_repeat_count", 0) or 0),
        "churn_signature_ref": str(churn_state.get("churn_signature_ref", "")),
        "churn_breaker_active": bool(churn_breaker_active),
        "latest_churn_breaker_result": (
            "selected" if churn_breaker_active and churn_breaker_action else "blocked"
            if churn_breaker_active
            else ""
        ),
        "repeated_churn_capability_kind": str(
            churn_state.get("repeated_capability_kind", "")
        ),
        "repeated_churn_promotion_packet_ref": str(
            churn_state.get("repeated_promotion_packet_ref", "")
        ),
        "churn_breaker_action": churn_breaker_action,
        "directive_outcome_nudge_interval": int(
            directive_outcome_cadence.get(
                "directive_outcome_nudge_interval",
                DIRECTIVE_OUTCOME_NUDGE_INTERVAL,
            )
        ),
        "framework_invocations_since_directive_outcome": int(
            directive_outcome_cadence.get(
                "framework_invocations_since_directive_outcome", 0
            )
        ),
        "latest_directive_outcome_operation_result_id": str(
            directive_outcome_cadence.get(
                "latest_directive_outcome_operation_result_id", ""
            )
        ),
        "baseline_operation_action": baseline_action,
        "hard_memory_recovery_priority_applied": hard_memory_recovery_priority_applied,
        "memory_recovery_action": memory_recovery_action,
        "memory_recovery_reason": memory_recovery_reason,
        "oom_guard_state": oom_guard_state,
        "oom_guard_action": str(memory_status.get("oom_guard_action", "none")),
        "oom_guard_reason": str(memory_status.get("oom_guard_reason", "")),
        "oom_guard_blocked_action": oom_guard_blocked_action,
        "memory_smoothing_state": memory_smoothing_state,
        "latest_smoothing_action": str(memory_status.get("latest_smoothing_action", "")),
        "memory_smoothing_blocked_action": memory_smoothing_blocked_action,
        "memory_high_watermark_percent": float(
            memory_status.get("memory_high_watermark_percent", 0.0) or 0.0
        ),
        "cooling_entered_at": str(memory_status.get("cooling_entered_at", "")),
        "cooling_exit_percent": float(memory_status.get("cooling_exit_percent", 0.0) or 0.0),
        "last_trim_result": str(memory_status.get("last_trim_result", "")),
        "cache_eviction_count": int(memory_status.get("cache_eviction_count", 0) or 0),
        "disk_spill_bytes": int(memory_status.get("disk_spill_bytes", 0) or 0),
        "hibernate_recommended": bool(memory_status.get("hibernate_recommended", False)),
        "service_recycle_recommended": bool(
            memory_status.get("service_recycle_recommended", False)
        ),
        "memory_headroom_gib": float(memory_status.get("memory_headroom_gib", 0.0) or 0.0),
        "last_recycle_request_id": str(memory_status.get("last_recycle_request_id", "")),
        "planner_hook_bias_applied": bool(hook_consumption.get("planner_hook_bias_applied", False)),
        "decision_changed_by_capability": bool(
            hook_consumption.get("decision_changed_by_capability", False)
        ),
        "capability_consumption_event_id": str(
            hook_consumption.get("capability_consumption_event_id", "")
        ),
        "consumed_capability_kinds": list(hook_consumption.get("consumed_capability_kinds", []) or []),
        "explicitly_consumed_capability_kinds": list(
            hook_consumption.get("explicitly_consumed_capability_kinds", [])
            or hook_consumption.get("consumed_capability_kinds", [])
            or []
        ),
        "capability_consumption_contract_ids": list(
            hook_consumption.get("capability_consumption_contract_ids", []) or []
        ),
        "runtime_capability_adapter_ids": list(
            hook_consumption.get("runtime_capability_adapter_ids", []) or []
        ),
        "runtime_capability_adapter_behaviors": list(
            hook_consumption.get("runtime_capability_adapter_behaviors", []) or []
        ),
        "planner_hook_references": list(hook_consumption.get("planner_hook_references", []) or []),
        "runtime_hook_references": list(hook_consumption.get("runtime_hook_references", []) or []),
        "planner_hook_reason": str(hook_consumption.get("hook_reason", "")),
        "planner_input_fingerprint": str(hook_consumption.get("input_fingerprint", "")),
        "suppressed_actions": suppressed_actions,
        "repeat_failure_prevented": bool(hook_consumption.get("repeat_failure_prevented", False)),
        "budget_guardrail_evaluation_id": str(
            budget_guardrail.get("budget_guardrail_evaluation_id", "")
        ),
        "budget_decision": str(budget_guardrail.get("budget_decision", "")),
        "budget_reason": str(budget_guardrail.get("budget_reason", "")),
        "budget_recommended_action": str(budget_guardrail.get("recommended_action", "")),
        "budget_prevented_overrun": bool(
            budget_guardrail.get("prevented_budget_overrun", False)
        ),
        "trusted_source_triage_needed": triage_needed,
        "trusted_source_triage_priority_status": triage_priority_status,
        "trusted_source_triage_priority_reason": (
            "librarian requested trusted-source pack acquisition for a missing reusable knowledge pack"
            if librarian_gap_active
            else "trusted-source triage selected before another adaptive-learning cycle"
            if triage_needed
            else triage_hard_blocker
            or str(triage_priority.get("trusted_source_triage_priority_reason", ""))
        ),
        "trusted_source_triage_priority_blocker": (
            triage_hard_blocker
            or str(triage_priority.get("trusted_source_triage_priority_blocker", ""))
        ),
        "trusted_source_triage_role_signal": bool(
            triage_priority.get("trusted_source_triage_role_signal", False)
        ),
        "trusted_source_triage_role_reason": str(
            triage_priority.get("trusted_source_triage_role_reason", "")
        ),
        "trusted_source_triage_recent_adaptive_count": int(
            triage_priority.get("trusted_source_triage_recent_adaptive_count", 0) or 0
        ),
        "trusted_source_triage_recent_window_size": int(
            triage_priority.get("trusted_source_triage_recent_window_size", 0) or 0
        ),
        "trusted_source_triage_recent_observed_count": int(
            triage_priority.get("trusted_source_triage_recent_observed_count", 0) or 0
        ),
        "trusted_source_triage_recent_threshold": int(
            triage_priority.get("trusted_source_triage_recent_threshold", 0) or 0
        ),
        "trusted_source_triage_governed_continuation_count": int(
            triage_priority.get("trusted_source_triage_governed_continuation_count", 0) or 0
        ),
        "trusted_source_triage_governed_continuation_threshold": int(
            triage_priority.get("trusted_source_triage_governed_continuation_threshold", 0) or 0
        ),
        "trusted_source_triage_governed_continuation_cadence_due": bool(
            triage_priority.get("trusted_source_triage_governed_continuation_cadence_due", False)
        ),
        "trusted_source_triage_governed_continuation_latest_result_id": str(
            triage_priority.get("trusted_source_triage_governed_continuation_latest_result_id", "")
        ),
        "trusted_source_triage_priority_provider_ready": bool(
            triage_priority.get("trusted_source_triage_provider_ready", False)
        ),
        "trusted_source_triage_priority_provider_blocker": str(
            triage_priority.get("trusted_source_triage_provider_blocker", "")
        ),
        "trusted_source_triage_latest_learning_gap": str(
            triage_priority.get("trusted_source_triage_latest_learning_gap", "")
        ),
        "trusted_source_triage_latest_frontier_gap": str(
            triage_priority.get("trusted_source_triage_latest_frontier_gap", "")
        ),
        "trusted_source_triage_duplicate_completed_digest": bool(
            triage_priority.get("trusted_source_triage_duplicate_completed_digest", False)
        ),
        "librarian_gap_request": librarian_gap_active,
        "librarian_gap_request_id": str(librarian_gap.get("librarian_gap_request_id", "")),
        "librarian_gap_reuse_decision": str(librarian_gap.get("reuse_decision", "")),
        "librarian_gap_requested_pack_kind": str(librarian_gap.get("requested_pack_kind", "")),
        "librarian_gap_blocker": str(librarian_gap.get("blocker", "")),
        "librarian_gap_requested_gap_ref": str(librarian_gap.get("requested_gap_ref", "")),
        "librarian_gap_signature": str(librarian_gap.get("librarian_gap_signature", "")),
        "librarian_gap_state": str(librarian_gap.get("librarian_gap_state", "")),
        "requested_pack_family": str(librarian_gap.get("requested_pack_family", "")),
        "requested_tags": list(librarian_gap.get("requested_tags", []) or [])[:12],
        "source_dossier_ref": str(librarian_gap.get("source_dossier_ref", "")),
        "source_coverage_state": str(librarian_gap.get("source_coverage_state", "")),
        "capability_retirement_evaluation_id": str(
            consumption_remediation.get("capability_retirement_evaluation_id", "")
        ),
        "capability_retirement_status": consumption_remediation_status,
        "capability_retirement_reason": str(consumption_remediation.get("reason", "")),
        "capability_retirement_pivot_action": consumption_remediation_pivot,
        "weak_usefulness_repeat_count": int(
            consumption_remediation.get("weak_usefulness_repeat_count", 0) or 0
        ),
        "weak_usefulness_repeat_threshold": int(
            consumption_remediation.get("weak_usefulness_repeat_threshold", 0) or 0
        ),
        "consumption_contract_missing": bool(
            consumption_remediation.get("consumption_contract_missing", False)
        ),
        "adaptive_learning_hook_stall_id": str(
            adaptive_hook_stall.get("adaptive_learning_hook_stall_id", "")
        ),
        "hook_stall_status": adaptive_hook_stall_status,
        "hook_stall_pivot_action": adaptive_hook_stall_pivot_action,
        "hook_stall_reason": str(adaptive_hook_stall.get("reason", "")),
        "hook_stall_repeat_count": int(adaptive_hook_stall.get("repeat_count", 0) or 0),
        "hook_stall_repeat_threshold": int(adaptive_hook_stall.get("repeat_threshold", 0) or 0),
        "stalled_capability_kind": str(adaptive_hook_stall.get("stalled_capability_kind", "")),
        "runtime_hook_adapter_gap_id": str(adaptive_hook_stall.get("runtime_hook_adapter_gap_id", "")),
        "runtime_hook_adapter_behavior": str(
            adaptive_hook_stall.get("runtime_hook_adapter_behavior", "")
        ),
        "governed_stale_recovery_available": bool(
            adaptive_hook_stall.get("governed_stale_recovery_available", False)
        ),
        "governed_recovery_checkpoint_id": governed_recovery_checkpoint_id,
        "adaptive_learning_backoff_id": str(adaptive_backoff.get("adaptive_learning_backoff_id", "")),
        "adaptive_learning_backoff_status": adaptive_backoff_status,
        "adaptive_learning_repeated_gap_id": str(adaptive_backoff.get("repeated_learning_gap_id", "")),
        "adaptive_learning_repeat_count": int(adaptive_backoff.get("repeat_count", 0) or 0),
        "adaptive_learning_repeat_threshold": int(adaptive_backoff.get("repeat_threshold", 0) or 0),
        "adaptive_learning_backoff_pivot_action": str(adaptive_backoff.get("pivot_action", "")),
        "adaptive_learning_backoff_reason": str(adaptive_backoff.get("reason", "")),
        "adaptive_learning_gap_family_evaluation_id": str(
            adaptive_family_backoff.get("adaptive_learning_gap_family_evaluation_id", "")
        ),
        "adaptive_learning_gap_family_id": str(adaptive_family_backoff.get("family_id", "")),
        "family_backoff_id": str(adaptive_family_backoff.get("family_backoff_id", "")),
        "family_backoff_status": adaptive_family_backoff_status,
        "family_member_gap_ids": list(adaptive_family_backoff.get("member_gap_ids", []) or []),
        "family_member_gap_count": int(adaptive_family_backoff.get("member_gap_count", 0) or 0),
        "family_repeat_count": int(adaptive_family_backoff.get("repeat_count", 0) or 0),
        "family_repeat_threshold": int(adaptive_family_backoff.get("repeat_threshold", 0) or 0),
        "family_representative_gap_id": str(adaptive_family_backoff.get("representative_gap_id", "")),
        "family_backoff_pivot_action": str(adaptive_family_backoff.get("pivot_action", "")),
        "family_backoff_reason": str(adaptive_family_backoff.get("reason", "")),
        "memory_pressure": {
            "memory_pressure_status_id": str(memory_status.get("memory_pressure_status_id", "")),
            "pressure_band": memory_band,
            "memory_percent": memory_status.get("memory_percent", 0),
            "memory_smoothing_state": memory_smoothing_state,
            "latest_smoothing_action": str(memory_status.get("latest_smoothing_action", "")),
            "memory_high_watermark_percent": float(
                memory_status.get("memory_high_watermark_percent", 0.0) or 0.0
            ),
            "cooling_entered_at": str(memory_status.get("cooling_entered_at", "")),
            "cooling_exit_percent": float(memory_status.get("cooling_exit_percent", 0.0) or 0.0),
            "last_trim_result": str(memory_status.get("last_trim_result", "")),
            "cache_eviction_count": int(memory_status.get("cache_eviction_count", 0) or 0),
            "disk_spill_bytes": int(memory_status.get("disk_spill_bytes", 0) or 0),
            "measurement_source": str(memory_status.get("measurement_source", "")),
            "measurement_age_seconds": float(
                memory_status.get("measurement_age_seconds", 0.0) or 0.0
            ),
            "stale_measurement": bool(memory_status.get("stale_measurement", False)),
            "fresh_measurement_required": bool(
                memory_status.get("fresh_measurement_required", False)
            ),
            "archive_recommended": bool(memory_status.get("archive_recommended", False)),
            "restart_recommended": bool(memory_status.get("restart_recommended", False)),
            "latest_recovery_state": str(memory_status.get("latest_recovery_state", "")),
            "latest_ledger_compaction_status": str(
                memory_status.get("latest_ledger_compaction_status", "")
            ),
            "ledger_compaction_compacted_record_count": int(
                memory_status.get("ledger_compaction_compacted_record_count", 0) or 0
            ),
            "ledger_compaction_hot_tail_records": int(
                memory_status.get("ledger_compaction_hot_tail_records", 0) or 0
            ),
            "restart_recommended_after_compaction": bool(
                memory_status.get("restart_recommended_after_compaction", False)
            ),
        },
        "novelty_preview": {
            "selected_capability_kind": str(novelty_preview.get("selected_capability_kind", "")),
            "capability_gap_id": str(novelty_preview.get("capability_gap_id", "")),
            "novelty_status": str(novelty_preview.get("novelty_status", "")),
            "cooldown_reason": str(novelty_preview.get("cooldown_reason", "")),
        },
        "measurable_success_conditions": (
            [
                "A MemoryPressureStatus record is persisted before ledger compaction.",
                "A LedgerCompactionSegmentManifest records archived segment hashes and record counts.",
                "A MemoryRecoveryRequest is recorded if memory remains above the action threshold.",
            ]
            if recommended_action == "memory_ledger_compaction"
            else
            [
                "A MemoryPressureStatus record is persisted before archive.",
                "A MemoryArchiveManifest records archived file hashes and byte totals.",
                "A MemoryRecoveryRequest is recorded if memory remains above the action threshold.",
            ]
            if recommended_action == "memory_pressure_archive"
            else
            [
                "A promotion packet is generated with one or more manifest entries.",
                "The approval board unanimously approves the broker operation.",
                "The broker writes PromotionResult evidence with canary and rollback status.",
            ]
            if recommended_action == "promote_self_modification_candidate"
            else
            [
                "A TrustedSourceLiteratureTriageDigest record is persisted with redacted provider metadata.",
                "At least one citation summary and one bounded action suggestion are recorded when the provider response is valid.",
                "The digest remains state-only evidence for later adaptive learning and synthesis.",
            ]
            if recommended_action == "trusted_source_literature_triage_digest"
            else
            [
                "A role specialization profile is refreshed without mutating the charter.",
                "At least one promoted capability receives a usefulness classification.",
                "A self-curriculum challenge and metacognitive replay record are persisted.",
            ]
            if recommended_action == "adaptive_learning_synthesis"
            else
            [
                "A post-ladder synthesis record summarizes recently promoted capability kinds.",
                "Each promoted capability has a usefulness classification.",
                "A bounded next capability-gap proposal is persisted without modifying the charter.",
            ]
            if recommended_action == "post_ladder_synthesis"
            else
            [
                "A governed-start operation proposal is approved by every board role.",
                "The governed-start executor records an attempt before any UI navigation.",
                "The next cycle records whether directive progress increased or a concrete blocker remains.",
            ]
            if recommended_action == "governed_start_next_invocation"
            else [
                "A read-only stack status operation records health evidence.",
                "The cycle identifies the next launch blocker or confirms no launchable directive is present.",
                "The self-modification proposal remains promotion-gated until a packet exists.",
            ]
        ),
        "risk_notes": [
            "Governed execution remains the only implementation substrate; autonomy does not bypass launch preflight."
            if recommended_action == "governed_start_next_invocation"
            else "No destructive operation is included in this candidate plan.",
            "The operation remains behind an OperationProposal and approval-board decision.",
        ],
        "recommended_operation_action": (
            recommended_action
        ),
        "governed_readiness_summary": {
            "can_launch": governed_ready,
            "blocking_reasons": list(governed_readiness.get("blocking_reasons", []) or [])[:5],
            "operator_next_action": str(governed_readiness.get("operator_next_action", "")),
            "stale_recovery_available": governed_recovery_available,
            "stale_recovery_checkpoint_id": governed_recovery_checkpoint_id,
        },
    }
    plan["plan_candidate_id"] = _record_id("plan", plan)
    if plan["consumed_capability_kinds"]:
        hook_seed = dict(hook_consumption)
        hook_seed["plan_candidate_id"] = plan["plan_candidate_id"]
        plan["capability_hook_consumption_id"] = _record_id("hook", hook_seed)
    return plan


def _attach_planner_hook_fields(proposal: dict[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    proposal.update(
        {
            "baseline_operation_action": str(plan.get("baseline_operation_action", "")),
            "capability_consumption_event_id": str(
                plan.get("capability_consumption_event_id", "")
            ),
            "capability_consumption_contract_ids": list(
                plan.get("capability_consumption_contract_ids", []) or []
            ),
            "runtime_capability_adapter_ids": list(
                plan.get("runtime_capability_adapter_ids", []) or []
            ),
            "runtime_capability_adapter_behaviors": list(
                plan.get("runtime_capability_adapter_behaviors", []) or []
            ),
            "planner_hook_bias_applied": bool(plan.get("planner_hook_bias_applied", False)),
            "decision_changed_by_capability": bool(
                plan.get("decision_changed_by_capability", False)
            ),
            "consumed_capability_kinds": list(plan.get("consumed_capability_kinds", []) or []),
            "explicitly_consumed_capability_kinds": list(
                plan.get("explicitly_consumed_capability_kinds", [])
                or plan.get("consumed_capability_kinds", [])
                or []
            ),
            "planner_hook_references": list(plan.get("planner_hook_references", []) or []),
            "planner_hook_reason": str(plan.get("planner_hook_reason", "")),
            "capability_hook_consumption_id": str(plan.get("capability_hook_consumption_id", "")),
            "planner_input_fingerprint": str(plan.get("planner_input_fingerprint", "")),
            "suppressed_actions": list(plan.get("suppressed_actions", []) or []),
            "repeat_failure_prevented": bool(plan.get("repeat_failure_prevented", False)),
            "budget_guardrail_evaluation_id": str(
                plan.get("budget_guardrail_evaluation_id", "")
            ),
            "budget_decision": str(plan.get("budget_decision", "")),
            "budget_reason": str(plan.get("budget_reason", "")),
            "budget_recommended_action": str(plan.get("budget_recommended_action", "")),
            "budget_prevented_overrun": bool(plan.get("budget_prevented_overrun", False)),
            "trusted_source_triage_needed": bool(plan.get("trusted_source_triage_needed", False)),
            "trusted_source_triage_priority_status": str(
                plan.get("trusted_source_triage_priority_status", "")
            ),
            "trusted_source_triage_priority_reason": str(
                plan.get("trusted_source_triage_priority_reason", "")
            ),
            "trusted_source_triage_priority_blocker": str(
                plan.get("trusted_source_triage_priority_blocker", "")
            ),
            "trusted_source_triage_role_signal": bool(
                plan.get("trusted_source_triage_role_signal", False)
            ),
            "trusted_source_triage_role_reason": str(
                plan.get("trusted_source_triage_role_reason", "")
            ),
            "trusted_source_triage_recent_adaptive_count": int(
                plan.get("trusted_source_triage_recent_adaptive_count", 0) or 0
            ),
            "trusted_source_triage_recent_window_size": int(
                plan.get("trusted_source_triage_recent_window_size", 0) or 0
            ),
            "trusted_source_triage_recent_observed_count": int(
                plan.get("trusted_source_triage_recent_observed_count", 0) or 0
            ),
            "trusted_source_triage_recent_threshold": int(
                plan.get("trusted_source_triage_recent_threshold", 0) or 0
            ),
            "trusted_source_triage_governed_continuation_count": int(
                plan.get("trusted_source_triage_governed_continuation_count", 0) or 0
            ),
            "trusted_source_triage_governed_continuation_threshold": int(
                plan.get("trusted_source_triage_governed_continuation_threshold", 0) or 0
            ),
            "trusted_source_triage_governed_continuation_cadence_due": bool(
                plan.get("trusted_source_triage_governed_continuation_cadence_due", False)
            ),
            "trusted_source_triage_governed_continuation_latest_result_id": str(
                plan.get("trusted_source_triage_governed_continuation_latest_result_id", "")
            ),
            "trusted_source_triage_priority_provider_ready": bool(
                plan.get("trusted_source_triage_priority_provider_ready", False)
            ),
            "trusted_source_triage_priority_provider_blocker": str(
                plan.get("trusted_source_triage_priority_provider_blocker", "")
            ),
            "trusted_source_triage_latest_learning_gap": str(
                plan.get("trusted_source_triage_latest_learning_gap", "")
            ),
            "trusted_source_triage_latest_frontier_gap": str(
                plan.get("trusted_source_triage_latest_frontier_gap", "")
            ),
            "trusted_source_triage_duplicate_completed_digest": bool(
                plan.get("trusted_source_triage_duplicate_completed_digest", False)
            ),
            "librarian_gap_request": bool(plan.get("librarian_gap_request", False)),
            "librarian_gap_request_id": str(plan.get("librarian_gap_request_id", "")),
            "librarian_gap_reuse_decision": str(plan.get("librarian_gap_reuse_decision", "")),
            "librarian_gap_requested_pack_kind": str(
                plan.get("librarian_gap_requested_pack_kind", "")
            ),
            "librarian_gap_blocker": str(plan.get("librarian_gap_blocker", "")),
            "librarian_gap_requested_gap_ref": str(
                plan.get("librarian_gap_requested_gap_ref", "")
            ),
            "librarian_gap_signature": str(plan.get("librarian_gap_signature", "")),
            "librarian_gap_state": str(plan.get("librarian_gap_state", "")),
            "requested_pack_family": str(plan.get("requested_pack_family", "")),
            "requested_tags": list(plan.get("requested_tags", []) or [])[:12],
            "source_dossier_ref": str(plan.get("source_dossier_ref", "")),
            "source_coverage_state": str(plan.get("source_coverage_state", "")),
            "capability_retirement_evaluation_id": str(
                plan.get("capability_retirement_evaluation_id", "")
            ),
            "capability_retirement_status": str(plan.get("capability_retirement_status", "")),
            "capability_retirement_reason": str(plan.get("capability_retirement_reason", "")),
            "capability_retirement_pivot_action": str(
                plan.get("capability_retirement_pivot_action", "")
            ),
            "weak_usefulness_repeat_count": int(plan.get("weak_usefulness_repeat_count", 0) or 0),
            "weak_usefulness_repeat_threshold": int(
                plan.get("weak_usefulness_repeat_threshold", 0) or 0
            ),
            "consumption_contract_missing": bool(
                plan.get("consumption_contract_missing", False)
            ),
            "adaptive_learning_hook_stall_id": str(
                plan.get("adaptive_learning_hook_stall_id", "")
            ),
            "hook_stall_status": str(plan.get("hook_stall_status", "")),
            "hook_stall_pivot_action": str(plan.get("hook_stall_pivot_action", "")),
            "hook_stall_reason": str(plan.get("hook_stall_reason", "")),
            "hook_stall_repeat_count": int(plan.get("hook_stall_repeat_count", 0) or 0),
            "hook_stall_repeat_threshold": int(
                plan.get("hook_stall_repeat_threshold", 0) or 0
            ),
            "stalled_capability_kind": str(plan.get("stalled_capability_kind", "")),
            "runtime_hook_adapter_gap_id": str(plan.get("runtime_hook_adapter_gap_id", "")),
            "runtime_hook_adapter_behavior": str(
                plan.get("runtime_hook_adapter_behavior", "")
            ),
            "governed_stale_recovery_available": bool(
                plan.get("governed_stale_recovery_available", False)
            ),
            "governed_recovery_checkpoint_id": str(
                plan.get("governed_recovery_checkpoint_id", "")
            ),
            "oom_guard_state": str(plan.get("oom_guard_state", "normal")),
            "oom_guard_action": str(plan.get("oom_guard_action", "none")),
            "oom_guard_reason": str(plan.get("oom_guard_reason", "")),
            "oom_guard_blocked_action": str(plan.get("oom_guard_blocked_action", "")),
            "hibernate_recommended": bool(plan.get("hibernate_recommended", False)),
            "service_recycle_recommended": bool(
                plan.get("service_recycle_recommended", False)
            ),
            "last_recycle_request_id": str(plan.get("last_recycle_request_id", "")),
        }
    )
    return proposal


def _operation_proposal(
    goal: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    operator_root: str | Path,
    package_root: str | Path,
) -> dict[str, Any]:
    action = str(plan.get("recommended_operation_action", "") or "novali_stack_status")
    if action == "promote_self_modification_candidate":
        novelty = _capability_novelty_evaluation(
            operator_root,
            requested_capability_kind=str(
                plan.get("adaptive_learning_repeated_gap_id")
                or plan.get("family_representative_gap_id")
                or plan.get("runtime_hook_adapter_gap_id")
                or ""
            ),
        )
        packet = _build_autonomous_capability_promotion_packet(
            operator_root=operator_root,
            package_root=package_root,
            goal=goal,
            plan=plan,
            novelty_evaluation=novelty,
        )
        proposal = {
            "schema_name": OPERATION_PROPOSAL_SCHEMA_NAME,
            "schema_version": AUTONOMY_SCHEMA_VERSION,
            "created_at": _now(),
            "operation_id": "",
            "goal_id": str(goal.get("goal_id", "")),
            "plan_candidate_id": str(plan.get("plan_candidate_id", "")),
            "target": "novali_own_stack",
            "action": action,
            "status": "pending_board_review",
            "risk_class": "bounded_state_capability_adoption",
            "blast_radius": "operator_state autonomy capability record only",
            "reversible": True,
            "capability_kind": str(packet.get("capability_kind", "")),
            "capability_gap_id": str(packet.get("capability_gap_id", "")),
            "novelty_evaluation_id": str(packet.get("novelty_evaluation_id", "")),
            "novelty_status": str(packet.get("novelty_status", "")),
            "adaptive_learning_backoff_id": str(packet.get("adaptive_learning_backoff_id", "")),
            "backoff_promoted_gap": bool(packet.get("backoff_promoted_gap", False)),
            "repeated_learning_gap_id": str(packet.get("repeated_learning_gap_id", "")),
            "adaptive_learning_gap_family_id": str(packet.get("adaptive_learning_gap_family_id", "")),
            "adaptive_learning_gap_family_evaluation_id": str(
                packet.get("adaptive_learning_gap_family_evaluation_id", "")
            ),
            "family_backoff_id": str(packet.get("family_backoff_id", "")),
            "family_backoff_promoted_gap": bool(packet.get("family_backoff_promoted_gap", False)),
            "family_member_gap_ids": list(packet.get("family_member_gap_ids", []) or []),
            "representative_gap_id": str(packet.get("representative_gap_id", "")),
            "adaptive_learning_hook_stall_id": str(packet.get("adaptive_learning_hook_stall_id", "")),
            "hook_stall_status": str(packet.get("hook_stall_status", "")),
            "hook_stall_pivot_action": str(packet.get("hook_stall_pivot_action", "")),
            "stalled_capability_kind": str(packet.get("stalled_capability_kind", "")),
            "runtime_hook_adapter_gap_id": str(packet.get("runtime_hook_adapter_gap_id", "")),
            "runtime_hook_adapter_behavior": str(packet.get("runtime_hook_adapter_behavior", "")),
            "meaningful_work_impact": str(novelty.get("meaningful_work_impact", "")),
            "rollback_plan": "Restore the prior adopted capability file from the broker snapshot if canary or later validation fails.",
            "verification_plan": [
                "Run packet test commands before copying any file.",
                "Copy only files listed in the changed-file manifest.",
                "Run canary commands after adoption and persist PromotionResult evidence.",
            ],
            "promotion_packet": packet,
            "requires_human": False,
        }
        _attach_planner_hook_fields(proposal, plan)
        proposal["operation_id"] = _record_id("op", proposal)
        return proposal
    if action == "memory_ledger_compaction":
        proposal = {
            "schema_name": OPERATION_PROPOSAL_SCHEMA_NAME,
            "schema_version": AUTONOMY_SCHEMA_VERSION,
            "created_at": _now(),
            "operation_id": "",
            "goal_id": str(goal.get("goal_id", "")),
            "plan_candidate_id": str(plan.get("plan_candidate_id", "")),
            "target": "novali_own_stack",
            "action": action,
            "status": "pending_board_review",
            "risk_class": "bounded_state_ledger_compaction",
            "blast_radius": "operator_state autonomy ledgers only",
            "reversible": True,
            "rollback_plan": (
                "Cold ledger records are preserved in gzip segments with manifests; "
                "the source ledger keeps a hot tail for status reads."
            ),
            "verification_plan": [
                "Persist MemoryPressureStatus before compaction.",
                "Compress only known append-only autonomy JSONL ledgers.",
                "Write segment manifests with hashes, counts, offsets, and path hints only.",
                "Replace source ledgers atomically after segment verification.",
                "Record MemoryRecoveryRequest if pressure remains above the action threshold.",
            ],
            "requires_human": False,
        }
        _attach_planner_hook_fields(proposal, plan)
        proposal["operation_id"] = _record_id("op", proposal)
        return proposal
    if action == "memory_pressure_archive":
        proposal = {
            "schema_name": OPERATION_PROPOSAL_SCHEMA_NAME,
            "schema_version": AUTONOMY_SCHEMA_VERSION,
            "created_at": _now(),
            "operation_id": "",
            "goal_id": str(goal.get("goal_id", "")),
            "plan_candidate_id": str(plan.get("plan_candidate_id", "")),
            "target": "novali_own_stack",
            "action": action,
            "status": "pending_board_review",
            "risk_class": "bounded_state_archive",
            "blast_radius": "persisted Novali state artifacts only",
            "reversible": True,
            "rollback_plan": (
                "Archived cold files are moved under operator_state/memory_archive with a manifest, "
                "hashes, bundle path, and original path hints for manual restore."
            ),
            "verification_plan": [
                "Persist MemoryPressureStatus before archiving.",
                "Compress only cold supported artifacts into a mounted operator_state archive bundle.",
                "Skip latest/session-active, credential-like, and secret-like files.",
                "Record MemoryRecoveryRequest if pressure remains above the action threshold.",
            ],
            "requires_human": False,
        }
        _attach_planner_hook_fields(proposal, plan)
        proposal["operation_id"] = _record_id("op", proposal)
        return proposal
    if action == "adaptive_learning_synthesis":
        proposal = {
            "schema_name": OPERATION_PROPOSAL_SCHEMA_NAME,
            "schema_version": AUTONOMY_SCHEMA_VERSION,
            "created_at": _now(),
            "operation_id": "",
            "goal_id": str(goal.get("goal_id", "")),
            "plan_candidate_id": str(plan.get("plan_candidate_id", "")),
            "target": "novali_own_stack",
            "action": action,
            "status": "pending_board_review",
            "risk_class": "read_only_state_synthesis",
            "blast_radius": "operator_state autonomy learning evidence only",
            "reversible": True,
            "rollback_plan": "Append-only redacted adaptive-learning evidence; no protected source-root writes are performed.",
            "verification_plan": [
                "Refresh role profile from redacted directive and autonomy evidence.",
                "Classify promoted capabilities using persisted later-usefulness signals.",
                "Write SelfCurriculumChallenge and MetacognitiveReplay records without mutating the charter.",
            ],
            "requires_human": False,
        }
        _attach_planner_hook_fields(proposal, plan)
        proposal["operation_id"] = _record_id("op", proposal)
        return proposal
    if action == "trusted_source_literature_triage_digest":
        proposal = {
            "schema_name": OPERATION_PROPOSAL_SCHEMA_NAME,
            "schema_version": AUTONOMY_SCHEMA_VERSION,
            "created_at": _now(),
            "operation_id": "",
            "goal_id": str(goal.get("goal_id", "")),
            "plan_candidate_id": str(plan.get("plan_candidate_id", "")),
            "target": "novali_own_stack",
            "action": action,
            "status": "pending_board_review",
            "risk_class": "read_only_state_synthesis",
            "blast_radius": "operator_state trusted-source triage evidence only",
            "reversible": True,
            "rollback_plan": "Append-only redacted triage evidence; no protected source-root writes or charter mutation are performed.",
            "verification_plan": [
                "Use only the configured openai_api trusted-source provider.",
                "Send compact redacted role, gap, and citation-hint context.",
                "Persist structured digest evidence without raw provider output or credentials.",
            ],
            "trusted_source_provider_id": TRUSTED_SOURCE_EXTERNAL_PROVIDER_ID,
            "requires_human": False,
        }
        _attach_planner_hook_fields(proposal, plan)
        proposal["operation_id"] = _record_id("op", proposal)
        return proposal
    if action == "post_ladder_synthesis":
        proposal = {
            "schema_name": OPERATION_PROPOSAL_SCHEMA_NAME,
            "schema_version": AUTONOMY_SCHEMA_VERSION,
            "created_at": _now(),
            "operation_id": "",
            "goal_id": str(goal.get("goal_id", "")),
            "plan_candidate_id": str(plan.get("plan_candidate_id", "")),
            "target": "novali_own_stack",
            "action": action,
            "status": "pending_board_review",
            "risk_class": "read_only_state_synthesis",
            "blast_radius": "operator_state autonomy synthesis evidence only",
            "reversible": True,
            "rollback_plan": "Append-only redacted synthesis evidence; no protected source-root writes are performed.",
            "verification_plan": [
                "Read recent promotion, novelty, and meaningful-work ledgers.",
                "Write a redacted PostLadderSynthesis artifact and ledger record.",
                "Persist a bounded next capability-gap proposal without modifying the charter.",
            ],
            "requires_human": False,
        }
        _attach_planner_hook_fields(proposal, plan)
        proposal["operation_id"] = _record_id("op", proposal)
        return proposal
    if action == "governed_start_next_invocation":
        proposal = {
            "schema_name": OPERATION_PROPOSAL_SCHEMA_NAME,
            "schema_version": AUTONOMY_SCHEMA_VERSION,
            "created_at": _now(),
            "operation_id": "",
            "goal_id": str(goal.get("goal_id", "")),
            "plan_candidate_id": str(plan.get("plan_candidate_id", "")),
            "target": "novali_own_stack",
            "action": action,
            "status": "pending_board_review",
            "risk_class": "bounded_governed_spawn",
            "blast_radius": "local Novali governed execution session only",
            "reversible": True,
            "rollback_plan": (
                "If the governed invocation starts unexpectedly or fails, use the existing long-run pause/stop controls, "
                "preserve the governed-start attempt record, and avoid additional starts until readiness is rechecked."
            ),
            "verification_plan": [
                "Use the same governed readiness and trusted-source launch preflight as the operator button.",
                "Return no workspace navigation unless the launcher confirms process spawn.",
                "Persist a governed-start attempt and autonomy operation result.",
            ],
            "requires_human": False,
        }
        _attach_planner_hook_fields(proposal, plan)
        proposal["operation_id"] = _record_id("op", proposal)
        return proposal
    proposal = {
        "schema_name": OPERATION_PROPOSAL_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "operation_id": "",
        "goal_id": str(goal.get("goal_id", "")),
        "plan_candidate_id": str(plan.get("plan_candidate_id", "")),
        "target": "novali_own_stack",
        "action": "novali_stack_status",
        "status": "pending_board_review",
        "risk_class": "read_only",
        "blast_radius": "local Novali Docker/Web Shell stack only",
        "reversible": True,
        "rollback_plan": "Read-only status operation; no rollback required.",
        "verification_plan": [
            "Capture docker compose ps output when Docker is available.",
            "Capture Web Shell health endpoint status when reachable.",
            "Persist redacted operation result.",
        ],
        "requires_human": False,
    }
    _attach_planner_hook_fields(proposal, plan)
    proposal["operation_id"] = _record_id("op", proposal)
    return proposal


def _self_modification_proposal(
    goal: Mapping[str, Any],
    plan: Mapping[str, Any],
    operation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    packet = dict(dict(operation or {}).get("promotion_packet", {}) or {})
    manifest = list(packet.get("changed_file_manifest", []) or [])
    test_commands = list(packet.get("test_commands", []) or [])
    canary_plan = dict(packet.get("canary_plan", {}) or {})
    rollback_plan = dict(packet.get("rollback_plan", {}) or {})
    proposal = {
        "schema_name": SELF_MODIFICATION_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "self_modification_id": "",
        "goal_id": str(goal.get("goal_id", "")),
        "plan_candidate_id": str(plan.get("plan_candidate_id", "")),
        "status": "promotion_packet_ready" if packet else "candidate",
        "title": "Strengthen autonomy reliability checks",
        "promotion_stage": "admitted_candidate" if packet else "candidate",
        "promotion_ladder": list(PROMOTION_LADDER_STAGES),
        "bounded_workspace_required": True,
        "protected_root_write_allowed": False,
        "adoption_target": "novali_own_stack",
        "risk_class": str(packet.get("risk_class", "bounded_self_modification")),
        "capability_kind": str(packet.get("capability_kind", "")),
        "capability_gap_id": str(packet.get("capability_gap_id", "")),
        "novelty_evaluation_id": str(packet.get("novelty_evaluation_id", "")),
        "novelty_status": str(packet.get("novelty_status", "")),
        "adaptive_learning_backoff_id": str(packet.get("adaptive_learning_backoff_id", "")),
        "backoff_promoted_gap": bool(packet.get("backoff_promoted_gap", False)),
        "repeated_learning_gap_id": str(packet.get("repeated_learning_gap_id", "")),
        "adaptive_learning_gap_family_id": str(packet.get("adaptive_learning_gap_family_id", "")),
        "adaptive_learning_gap_family_evaluation_id": str(
            packet.get("adaptive_learning_gap_family_evaluation_id", "")
        ),
        "family_backoff_id": str(packet.get("family_backoff_id", "")),
        "family_backoff_promoted_gap": bool(packet.get("family_backoff_promoted_gap", False)),
        "family_member_gap_ids": list(packet.get("family_member_gap_ids", []) or []),
        "representative_gap_id": str(packet.get("representative_gap_id", "")),
        "adaptive_learning_hook_stall_id": str(packet.get("adaptive_learning_hook_stall_id", "")),
        "hook_stall_status": str(packet.get("hook_stall_status", "")),
        "hook_stall_pivot_action": str(packet.get("hook_stall_pivot_action", "")),
        "stalled_capability_kind": str(packet.get("stalled_capability_kind", "")),
        "runtime_hook_adapter_gap_id": str(packet.get("runtime_hook_adapter_gap_id", "")),
        "runtime_hook_adapter_behavior": str(packet.get("runtime_hook_adapter_behavior", "")),
        "changed_file_manifest": manifest,
        "test_commands": test_commands,
        "rollback_plan": rollback_plan or {
            "required": True,
            "summary": "Promotion requires file snapshots before protected-root writes.",
        },
        "canary_plan": canary_plan or {
            "required": True,
            "summary": "Promotion requires a canary command or next-governed-invocation probe before broad adoption.",
        },
        "auto_adopt_eligible": bool(packet),
        "promotion_packet_required": not bool(packet),
        "promotion_packet": packet,
        "required_evidence_before_promotion": [
            "passing unit tests",
            "passing frontend build when UI changes",
            "rollback plan",
            "changed-file promotion manifest",
            "canary plan",
            "approval-board promotion decision",
        ],
    }
    proposal["self_modification_id"] = _record_id("selfmod", proposal)
    return proposal


def approval_board_review(
    *,
    operator_root: str | Path,
    plan_candidate: Mapping[str, Any] | None = None,
    operation_proposal: Mapping[str, Any] | None = None,
    self_modification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    charter = load_autonomy_charter(operator_root)
    errors = validate_autonomy_charter(charter)
    plan = dict(plan_candidate or _latest(operator_root, "plan_candidates"))
    operation = dict(operation_proposal or _latest(operator_root, "operation_proposals"))
    self_mod = dict(self_modification or _latest(operator_root, "self_modification_proposals"))
    role_votes = []
    rejected_reasons = list(errors)
    if not plan:
        rejected_reasons.append("missing plan candidate")
    elif not list(plan.get("measurable_success_conditions", []) or []):
        rejected_reasons.append("plan is missing measurable success conditions")
    if operation:
        if str(operation.get("target", "")) not in list(charter.get("approved_operation_targets", [])):
            rejected_reasons.append("operation target is not approved by charter")
        if str(operation.get("action", "")) not in list(charter.get("approved_operation_actions", [])):
            rejected_reasons.append("operation action is not approved by charter")
        if str(operation.get("risk_class", "")) != "read_only" and not str(operation.get("rollback_plan", "")).strip():
            rejected_reasons.append("mutating operation is missing rollback plan")
        if not list(operation.get("verification_plan", []) or []):
            rejected_reasons.append("operation is missing verification plan")
        if str(operation.get("action", "")) == "promote_self_modification_candidate":
            packet = dict(operation.get("promotion_packet", {}) or {})
            if not packet:
                rejected_reasons.append("promotion operation is missing promotion packet")
            elif _secret_leak_indicators(packet):
                rejected_reasons.append("promotion packet contains secret-like material")
            else:
                manifest = list(packet.get("changed_file_manifest", []) or [])
                test_commands = list(packet.get("test_commands", []) or [])
                canary_commands = list(dict(packet.get("canary_plan", {}) or {}).get("commands", []) or [])
                rollback_plan = dict(packet.get("rollback_plan", {}) or {})
                if (
                    str(packet.get("novelty_status", "")) == "repeat_blocked"
                    and not bool(packet.get("permitted_repeat", False))
                ):
                    rejected_reasons.append(
                        "promotion packet repeats a capability kind blocked by novelty cooldown"
                    )
                if not manifest:
                    rejected_reasons.append("promotion packet is missing changed-file manifest")
                if not test_commands:
                    rejected_reasons.append("promotion packet is missing tests")
                if not rollback_plan:
                    rejected_reasons.append("promotion packet is missing rollback packet")
                if not canary_commands:
                    rejected_reasons.append("promotion packet is missing canary plan")
    for role in APPROVAL_BOARD_ROLES:
        vote = "approve"
        rationale = "Evidence satisfies the v1 board gate."
        if rejected_reasons:
            vote = "reject"
            rationale = "; ".join(rejected_reasons)
        if role == "promotion_judge" and self_mod:
            vote = "approve" if not rejected_reasons else "reject"
            rationale = (
                "Promotion is allowed only through a verified packet with tests, rollback, canary evidence, "
                "and unanimous board approval."
            )
        role_votes.append({"role": role, "vote": vote, "rationale": rationale})
    approved = bool(role_votes) and all(str(item.get("vote")) == "approve" for item in role_votes)
    decision = {
        "schema_name": APPROVAL_BOARD_DECISION_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "decision_id": "",
        "plan_candidate_id": str(plan.get("plan_candidate_id", "")),
        "operation_id": str(operation.get("operation_id", "")),
        "self_modification_id": str(self_mod.get("self_modification_id", "")),
        "approved": approved,
        "decision": "approved" if approved else "rejected",
        "role_votes": role_votes,
        "rejected_reasons": rejected_reasons,
        "authority_boundary": (
            "Approval-board records are required before operation execution; "
            "protected-root self-modification remains promotion-gated."
        ),
    }
    decision["decision_id"] = _record_id("board", decision)
    return _append_ledger(operator_root, "approval_board_decisions", decision)


def run_autonomy_cycle(
    *,
    operator_root: str | Path,
    package_root: str | Path,
    state_root: str | Path,
    observations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    initialize_autonomy_state(operator_root)
    status = _read_json(_status_path(operator_root))
    if bool(status.get("emergency_stop", False)):
        return autonomy_status(operator_root)
    charter = load_autonomy_charter(operator_root)
    errors = validate_autonomy_charter(charter)
    started = time.perf_counter()
    loop_iteration = int(status.get("loop_iteration", 0) or 0) + 1
    cycle: dict[str, Any] = {
        "schema_name": AUTONOMY_CYCLE_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "cycle_id": "",
        "loop_iteration": loop_iteration,
        "status": "started",
        "phase": "observe",
        "charter_valid": not errors,
        "charter_errors": errors,
    }
    if errors:
        cycle["status"] = "blocked"
        cycle["phase"] = "charter_validation"
        cycle["summary"] = "Autonomy cycle blocked by invalid charter."
        cycle["cycle_id"] = _record_id("cycle", cycle)
        _append_ledger(operator_root, "cycles", cycle)
        _update_status(
            operator_root,
            {
                "runtime_state": "blocked",
                "active": False,
                "loop_iteration": loop_iteration,
                "latest_cycle_id": cycle["cycle_id"],
                "charter_valid": False,
                "charter_errors": errors,
                "message": "Autonomy blocked by invalid charter.",
            },
        )
        return autonomy_status(operator_root)

    observation_payload = dict(observations or {})
    goal = _self_authored_goal(operator_root, observation_payload)
    _append_ledger(operator_root, "goals", goal)
    research_request, research = _local_research_bundle(
        operator_root=operator_root,
        package_root=package_root,
        state_root=state_root,
        goal=goal,
        observations=observation_payload,
    )
    _append_ledger(operator_root, "research_requests", research_request)
    _append_ledger(operator_root, "research_evidence", research)
    role_profile = _role_specialization_profile(
        operator_root=operator_root,
        observations=observation_payload,
    )
    usefulness = _capability_usefulness_evaluation(operator_root=operator_root)
    plan = _plan_candidate(goal, research, operator_root=operator_root)
    _append_ledger(operator_root, "plan_candidates", plan)
    operation = _operation_proposal(
        goal,
        plan,
        operator_root=operator_root,
        package_root=package_root,
    )
    if list(operation.get("consumed_capability_kinds", []) or []):
        consumption_payload = {
            "schema_name": CAPABILITY_HOOK_CONSUMPTION_SCHEMA_NAME,
            "schema_version": AUTONOMY_SCHEMA_VERSION,
            "created_at": _now(),
            "capability_consumption_event_id": str(
                operation.get("capability_consumption_event_id", "")
            ),
            "capability_hook_consumption_id": str(
                operation.get("capability_hook_consumption_id", "")
            ),
            "capability_consumption_contract_ids": list(
                operation.get("capability_consumption_contract_ids", []) or []
            ),
            "runtime_capability_adapter_ids": list(
                operation.get("runtime_capability_adapter_ids", []) or []
            ),
            "runtime_capability_adapter_behaviors": list(
                operation.get("runtime_capability_adapter_behaviors", []) or []
            ),
            "explicitly_consumed_capability_kinds": list(
                operation.get("explicitly_consumed_capability_kinds")
                or operation.get("consumed_capability_kinds")
                or []
            ),
            "consumed_capability_kinds": list(operation.get("consumed_capability_kinds", []) or []),
            "planner_hook_references": list(operation.get("planner_hook_references", []) or []),
            "runtime_hook_references": list(
                operation.get("runtime_hook_references")
                or operation.get("planner_hook_references")
                or []
            ),
            "baseline_action": str(operation.get("baseline_operation_action", "")),
            "final_action": str(operation.get("action", "")),
            "decision_changed_by_capability": bool(
                operation.get("decision_changed_by_capability", False)
            ),
            "planner_hook_bias_applied": bool(
                operation.get("planner_hook_bias_applied", False)
            ),
            "hook_reason": str(operation.get("planner_hook_reason", "")),
            "input_fingerprint": str(operation.get("planner_input_fingerprint", "")),
            "suppressed_actions": list(operation.get("suppressed_actions", []) or []),
            "repeat_failure_prevented": bool(
                operation.get("repeat_failure_prevented", False)
            ),
            "budget_guardrail_evaluation_id": str(
                operation.get("budget_guardrail_evaluation_id", "")
            ),
            "budget_decision": str(operation.get("budget_decision", "")),
            "budget_reason": str(operation.get("budget_reason", "")),
            "budget_recommended_action": str(operation.get("budget_recommended_action", "")),
            "budget_prevented_overrun": bool(operation.get("budget_prevented_overrun", False)),
            "operator_intervention_reduced": bool(
                operation.get("operator_intervention_reduced", False)
            ),
            "adaptive_learning_hook_stall_id": str(
                operation.get("adaptive_learning_hook_stall_id", "")
            ),
            "hook_stall_status": str(operation.get("hook_stall_status", "")),
            "hook_stall_pivot_action": str(operation.get("hook_stall_pivot_action", "")),
            "hook_stall_reason": str(operation.get("hook_stall_reason", "")),
            "hook_stall_repeat_count": int(operation.get("hook_stall_repeat_count", 0) or 0),
            "hook_stall_repeat_threshold": int(
                operation.get("hook_stall_repeat_threshold", 0) or 0
            ),
            "stalled_capability_kind": str(operation.get("stalled_capability_kind", "")),
            "runtime_hook_adapter_gap_id": str(operation.get("runtime_hook_adapter_gap_id", "")),
            "runtime_hook_adapter_behavior": str(
                operation.get("runtime_hook_adapter_behavior", "")
            ),
            "governed_stale_recovery_available": bool(
                operation.get("governed_stale_recovery_available", False)
            ),
            "governed_recovery_checkpoint_id": str(
                operation.get("governed_recovery_checkpoint_id", "")
            ),
        "safety_gates_preserved": [
                "emergency_stop",
                "governed_readiness",
                "trusted_source_readiness",
                "approval_board",
                "operation_broker",
                "canary",
                "rollback",
                "memory_pressure",
                "novelty_repeat_blocking",
            ],
        }
        _persist_capability_hook_consumption(
            operator_root,
            consumption_payload,
            plan_candidate_id=str(plan.get("plan_candidate_id", "")),
            operation_id=str(operation.get("operation_id", "")),
        )
        _persist_capability_consumption_event(
            operator_root,
            consumption_payload,
            plan_candidate_id=str(plan.get("plan_candidate_id", "")),
            operation_id=str(operation.get("operation_id", "")),
        )
    _append_ledger(operator_root, "operation_proposals", operation)
    record_autonomy_operation_proposed(operation)
    self_mod = _self_modification_proposal(goal, plan, operation)
    _append_ledger(operator_root, "self_modification_proposals", self_mod)
    decision = approval_board_review(
        operator_root=operator_root,
        plan_candidate=plan,
        operation_proposal=operation,
        self_modification=self_mod,
    )
    packet_ready = bool(operation.get("promotion_packet")) and bool(decision.get("approved", False))
    promotion = {
        "schema_name": PROMOTION_DECISION_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "promotion_decision_id": "",
        "self_modification_id": str(self_mod.get("self_modification_id", "")),
        "operation_id": str(operation.get("operation_id", "")),
        "decision": "eligible" if packet_ready else "staged",
        "promotion_stage": str(self_mod.get("promotion_stage", "candidate")),
        "capability_kind": str(operation.get("capability_kind", "")),
        "capability_gap_id": str(operation.get("capability_gap_id", "")),
        "novelty_evaluation_id": str(operation.get("novelty_evaluation_id", "")),
        "novelty_status": str(operation.get("novelty_status", "")),
        "auto_adopt_eligible": packet_ready,
        "reason": (
            "Promotion packet is generated and board-approved; broker execution may auto-adopt it."
            if packet_ready
            else "Self-modification candidate is recorded; promotion packet is required before canary or adoption."
        ),
        "weak_areas": []
        if packet_ready
        else [
            "missing promotion packet",
            "missing changed-file manifest",
            "missing tests",
            "missing rollback packet",
            "missing canary evidence",
        ],
    }
    promotion["promotion_decision_id"] = _record_id("promotion", promotion)
    _append_ledger(operator_root, "promotion_decisions", promotion)
    record_promotion_packet_state(promotion, operation=operation)
    meaningful_work = _meaningful_work_evaluation(
        operator_root=operator_root,
        goal=goal,
        plan=plan,
        operation=operation,
        self_modification=self_mod,
        promotion=promotion,
        observations=observation_payload,
    )
    cycle.update(
        {
            "status": "board_reviewed",
            "phase": "board_review",
            "goal_id": goal["goal_id"],
            "research_bundle_id": research["research_bundle_id"],
            "plan_candidate_id": plan["plan_candidate_id"],
            "operation_id": operation["operation_id"],
            "decision_id": decision["decision_id"],
            "self_modification_id": self_mod["self_modification_id"],
            "promotion_decision_id": promotion["promotion_decision_id"],
            "meaningful_work_id": meaningful_work["meaningful_work_id"],
            "role_profile_id": role_profile["role_profile_id"],
            "usefulness_evaluation_id": usefulness["usefulness_evaluation_id"],
            "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "summary": "Autonomy cycle produced a self-authored goal, evidence, measurable plan, operation proposal, board decision, and meaningful-work evaluation.",
        }
    )
    cycle["cycle_id"] = _record_id("cycle", cycle)
    _append_ledger(operator_root, "cycles", cycle)
    _update_status(
        operator_root,
        {
            "runtime_state": "running" if bool(status.get("active", False)) else "cycle_completed",
            "active": bool(status.get("active", False)),
            "loop_iteration": loop_iteration,
            "latest_cycle_id": cycle["cycle_id"],
            "latest_goal_id": goal["goal_id"],
            "latest_board_decision_id": decision["decision_id"],
            "latest_operation_proposal_id": operation["operation_id"],
            "charter_valid": True,
            "charter_errors": [],
            "message": "Autonomy cycle completed and stopped at auditable board review.",
        },
    )
    return autonomy_status(operator_root)


def set_autonomy_active(operator_root: str | Path, active: bool) -> dict[str, Any]:
    initialize_autonomy_state(operator_root)
    return _update_status(
        operator_root,
        {
            "runtime_state": "running" if active else "paused",
            "active": bool(active),
            "message": "Autonomy loop active." if active else "Autonomy loop paused.",
        },
    )


def emergency_stop_autonomy(operator_root: str | Path, reason: str = "") -> dict[str, Any]:
    initialize_autonomy_state(operator_root)
    return _update_status(
        operator_root,
        {
            "runtime_state": "emergency_stopped",
            "active": False,
            "emergency_stop": True,
            "message": str(reason or "Emergency stop requested by operator."),
        },
    )


def clear_emergency_stop(operator_root: str | Path) -> dict[str, Any]:
    initialize_autonomy_state(operator_root)
    return _update_status(
        operator_root,
        {
            "runtime_state": "paused",
            "active": False,
            "emergency_stop": False,
            "message": "Emergency stop cleared; autonomy remains paused.",
        },
    )


def _find_record(operator_root: str | Path, ledger_name: str, key: str, value: str) -> dict[str, Any]:
    for record in reversed(_read_ledger(operator_root, ledger_name, limit=500)):
        if str(record.get(key, "")) == str(value):
            return record
    return {}


def _latest_approved_decision_for_operation(operator_root: str | Path, operation_id: str) -> dict[str, Any]:
    for decision in reversed(_read_ledger(operator_root, "approval_board_decisions", limit=500)):
        if str(decision.get("operation_id", "")) == str(operation_id) and bool(decision.get("approved", False)):
            return decision
    return {}


def validate_operation_for_execution(
    *,
    operator_root: str | Path,
    operation_id: str,
) -> dict[str, Any]:
    initialize_autonomy_state(operator_root)
    status = _read_json(_status_path(operator_root))
    if bool(status.get("emergency_stop", False)):
        raise AutonomyOperationRefusedError("emergency stop is active")
    operation = _find_record(operator_root, "operation_proposals", "operation_id", operation_id)
    if not operation:
        raise AutonomyOperationRefusedError("operation proposal not found")
    charter = load_autonomy_charter(operator_root)
    errors = validate_autonomy_charter(charter)
    if errors:
        raise AutonomyOperationRefusedError("; ".join(errors))
    if str(operation.get("target", "")) not in list(charter.get("approved_operation_targets", [])):
        raise AutonomyOperationRefusedError("operation target is not approved")
    action = str(operation.get("action", ""))
    if action not in list(charter.get("approved_operation_actions", [])):
        raise AutonomyOperationRefusedError("operation action is not approved")
    decision = _latest_approved_decision_for_operation(operator_root, operation_id)
    if not decision:
        decision = approval_board_review(operator_root=operator_root, operation_proposal=operation)
    if not bool(decision.get("approved", False)):
        raise AutonomyOperationRefusedError("approval board did not approve operation")
    return {"operation": operation, "decision": decision, "charter": charter}


def _run_command(command: list[str], *, cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "exit_code": completed.returncode,
            "stdout_redacted": _truncate(redact_value(completed.stdout), 6000),
            "stderr_redacted": _truncate(redact_value(completed.stderr), 6000),
        }
    except FileNotFoundError as exc:
        return {"exit_code": 127, "stderr_redacted": str(exc), "stdout_redacted": ""}
    except subprocess.TimeoutExpired:
        return {"exit_code": 124, "stderr_redacted": "operation timed out", "stdout_redacted": ""}


def _health_check() -> dict[str, Any]:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8787/healthz", timeout=5) as response:
            body = response.read().decode("utf-8", errors="replace")
        return {"status": "ok", "http_status": int(response.status), "body_redacted": _truncate(body, 500)}
    except (OSError, urllib.error.URLError) as exc:
        return {"status": "unavailable", "error_type": type(exc).__name__, "error_summary_redacted": str(exc)}


def _state_backup(operator_root: str | Path, state_root: str | Path) -> dict[str, Any]:
    backup_id = _record_id("backup", {"operator_root": str(operator_root), "state_root": str(state_root)})
    backup_root = autonomy_root(operator_root) / "backups" / backup_id
    backup_root.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, Any]] = []
    for name, source in (("operator_state", Path(operator_root)), ("runtime_state", Path(state_root))):
        if not source.exists():
            copied.append({"name": name, "source": str(source), "present": False})
            continue
        target = backup_root / name
        ignore = shutil.ignore_patterns("autonomy", "__pycache__", "*.pyc")
        shutil.copytree(source, target, dirs_exist_ok=True, ignore=ignore)
        copied.append({"name": name, "source": str(source), "target": str(target), "present": True})
    return {"backup_id": backup_id, "backup_root_hint": str(backup_root), "copied": copied}


def _stage_trusted_source_digest_for_librarian(
    *,
    operator_root: str | Path,
    state_root: str | Path,
    result_payload: Mapping[str, Any],
) -> dict[str, Any]:
    if str(result_payload.get("status", "") or "") != "completed":
        return {
            "stage_result": "skipped",
            "rejection_reason": "trusted_source_digest_not_completed",
        }
    digest_path = autonomy_root(operator_root) / "trusted_source_literature_triage_digest_latest.json"
    if not digest_path.exists():
        return {
            "stage_result": "skipped",
            "rejection_reason": "trusted_source_digest_artifact_missing",
        }
    try:
        from .librarian import stage_librarian_pack

        staged = stage_librarian_pack(
            state_root=state_root,
            source_path=digest_path,
            workspace_root=None,
            source_kind="trusted_source_operation_result",
        )
    except Exception as exc:
        return {
            "stage_result": "rejected",
            "rejection_reason": type(exc).__name__,
        }
    stage_result = {
        "stage_result": str(staged.get("stage_result", "")),
        "pack_kind": str(staged.get("pack_kind", "")),
        "pack_id": str(staged.get("pack_id", "")),
        "version_ref": str(staged.get("version_ref", "")),
        "quality_state": str(staged.get("quality_state", "")),
        "reuse_state": str(staged.get("reuse_state", "")),
    }
    if (
        result_payload.get("librarian_gap_request_id")
        and stage_result["pack_id"]
        and stage_result["stage_result"] in {"staged", "duplicate_existing_version"}
    ):
        _append_ledger(
            operator_root,
            "librarian_gap_requests",
            {
                "schema_name": LIBRARIAN_GAP_REQUEST_SCHEMA_NAME,
                "schema_version": AUTONOMY_SCHEMA_VERSION,
                "created_at": _now(),
                "librarian_gap_request_id": str(
                    result_payload.get("librarian_gap_request_id", "")
                ),
                "librarian_gap_signature": str(
                    result_payload.get("librarian_gap_signature", "")
                ),
                "librarian_gap_state": "satisfied",
                "action": "trusted_source_literature_triage_digest",
                "requested_pack_kind": "knowledge_pack",
                "requested_pack_family": str(result_payload.get("requested_pack_family", "")),
                "requested_tags": list(result_payload.get("requested_tags", []) or [])[:12],
                "source_dossier_ref": str(result_payload.get("source_dossier_ref", "")),
                "source_coverage_state": "trusted_source_evidence_staged",
                "reuse_decision": "trusted_source_evidence_staged",
                "satisfied_pack_ref": stage_result["pack_id"],
                "grants_execution_authority": False,
            },
        )
    return stage_result


def _resolve_package_path(package_root: Path, value: Any) -> Path:
    path = Path(str(value or "")).expanduser()
    if not path.is_absolute():
        path = package_root / path
    resolved = path.resolve()
    package_resolved = package_root.resolve()
    try:
        resolved.relative_to(package_resolved)
    except ValueError as exc:
        raise AutonomyOperationRefusedError("promotion path escapes package root") from exc
    return resolved


def _normalize_command_list(value: Any) -> list[list[str]]:
    commands: list[list[str]] = []
    for item in list(value or []):
        if isinstance(item, (list, tuple)):
            command = [str(part) for part in item if str(part).strip()]
        else:
            command = [part for part in str(item).split() if part]
        if command:
            commands.append(command)
    return commands


def _promote_self_modification_candidate(
    *,
    operator_root: str | Path,
    package_root: Path,
    operation: Mapping[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    packet = dict(operation.get("promotion_packet", {}) or {})
    if not packet:
        raise AutonomyOperationRefusedError("promotion packet is required")
    capability_kind = str(
        packet.get("capability_kind") or operation.get("capability_kind") or ""
    )
    capability_gap_id = str(
        packet.get("capability_gap_id") or operation.get("capability_gap_id") or capability_kind
    )
    novelty_evaluation_id = str(
        packet.get("novelty_evaluation_id") or operation.get("novelty_evaluation_id") or ""
    )
    novelty_status = str(packet.get("novelty_status") or operation.get("novelty_status") or "")
    adaptive_learning_backoff_id = str(
        packet.get("adaptive_learning_backoff_id")
        or operation.get("adaptive_learning_backoff_id")
        or ""
    )
    backoff_promoted_gap = bool(
        packet.get("backoff_promoted_gap", False)
        or operation.get("backoff_promoted_gap", False)
    )
    repeated_learning_gap_id = str(
        packet.get("repeated_learning_gap_id")
        or operation.get("repeated_learning_gap_id")
        or ""
    )
    adaptive_learning_gap_family_id = str(
        packet.get("adaptive_learning_gap_family_id")
        or operation.get("adaptive_learning_gap_family_id")
        or ""
    )
    adaptive_learning_gap_family_evaluation_id = str(
        packet.get("adaptive_learning_gap_family_evaluation_id")
        or operation.get("adaptive_learning_gap_family_evaluation_id")
        or ""
    )
    family_backoff_id = str(
        packet.get("family_backoff_id") or operation.get("family_backoff_id") or ""
    )
    family_backoff_promoted_gap = bool(
        packet.get("family_backoff_promoted_gap", False)
        or operation.get("family_backoff_promoted_gap", False)
    )
    family_member_gap_ids = [
        str(item)
        for item in list(
            packet.get("family_member_gap_ids")
            or operation.get("family_member_gap_ids")
            or []
        )
        if str(item).strip()
    ]
    representative_gap_id = str(
        packet.get("representative_gap_id") or operation.get("representative_gap_id") or ""
    )
    adaptive_learning_hook_stall_id = str(
        packet.get("adaptive_learning_hook_stall_id")
        or operation.get("adaptive_learning_hook_stall_id")
        or ""
    )
    hook_stall_status = str(packet.get("hook_stall_status") or operation.get("hook_stall_status") or "")
    hook_stall_pivot_action = str(
        packet.get("hook_stall_pivot_action") or operation.get("hook_stall_pivot_action") or ""
    )
    stalled_capability_kind = str(
        packet.get("stalled_capability_kind") or operation.get("stalled_capability_kind") or ""
    )
    runtime_hook_adapter_gap_id = str(
        packet.get("runtime_hook_adapter_gap_id") or operation.get("runtime_hook_adapter_gap_id") or ""
    )
    runtime_hook_adapter_behavior = str(
        packet.get("runtime_hook_adapter_behavior")
        or operation.get("runtime_hook_adapter_behavior")
        or ""
    )
    leak_indicators = _secret_leak_indicators(packet)
    if leak_indicators:
        raise AutonomyOperationRefusedError(
            "promotion packet contains secret-like material: " + ", ".join(leak_indicators)
        )
    manifest = [dict(item) for item in list(packet.get("changed_file_manifest", []) or [])]
    test_commands = _normalize_command_list(packet.get("test_commands", []))
    canary_commands = _normalize_command_list(dict(packet.get("canary_plan", {}) or {}).get("commands", []))
    rollback_plan = dict(packet.get("rollback_plan", {}) or {})
    if not manifest:
        raise AutonomyOperationRefusedError("promotion packet is missing changed-file manifest")
    if not test_commands:
        raise AutonomyOperationRefusedError("promotion packet is missing tests")
    if not rollback_plan:
        raise AutonomyOperationRefusedError("promotion packet is missing rollback packet")
    if not canary_commands:
        raise AutonomyOperationRefusedError("promotion packet is missing canary plan")

    test_results: list[dict[str, Any]] = []
    for command in test_commands:
        result = _run_command(command, cwd=package_root, timeout_seconds=timeout_seconds)
        test_results.append({"command": command, "result": result})
        if int(result.get("exit_code", 1)) != 0:
            raise AutonomyOperationRefusedError("promotion tests failed")

    backup_root = autonomy_root(operator_root) / "promotion_backups" / _record_id("backup", packet)
    backup_root.mkdir(parents=True, exist_ok=True)
    applied_files: list[dict[str, str]] = []
    rollback_files: list[dict[str, str]] = []
    for index, item in enumerate(manifest):
        source = _resolve_package_path(package_root, item.get("source_path"))
        target = _resolve_package_path(package_root, item.get("target_path"))
        if not source.exists() or not source.is_file():
            raise AutonomyOperationRefusedError(f"promotion source file is missing: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup_path = backup_root / f"{index}_{target.name}"
            shutil.copy2(target, backup_path)
            rollback_files.append({"target_path": str(target), "backup_path": str(backup_path)})
        shutil.copy2(source, target)
        applied_files.append({"source_path": str(source), "target_path": str(target)})

    canary_results: list[dict[str, Any]] = []
    canary_failed = False
    for command in canary_commands:
        result = _run_command(command, cwd=package_root, timeout_seconds=timeout_seconds)
        canary_results.append({"command": command, "result": result})
        if int(result.get("exit_code", 1)) != 0:
            canary_failed = True
            break
    if canary_failed:
        for item in rollback_files:
            shutil.copy2(item["backup_path"], item["target_path"])
        promotion_result = {
            "schema_name": PROMOTION_RESULT_SCHEMA_NAME,
            "schema_version": AUTONOMY_SCHEMA_VERSION,
            "created_at": _now(),
            "promotion_result_id": "",
            "operation_id": str(operation.get("operation_id", "")),
            "promotion_stage": "staged_adoption",
            "status": "failed_canary_rolled_back",
            "capability_kind": capability_kind,
            "capability_gap_id": capability_gap_id,
            "novelty_evaluation_id": novelty_evaluation_id,
            "novelty_status": novelty_status,
            "adaptive_learning_backoff_id": adaptive_learning_backoff_id,
            "backoff_promoted_gap": backoff_promoted_gap,
            "repeated_learning_gap_id": repeated_learning_gap_id,
            "adaptive_learning_gap_family_id": adaptive_learning_gap_family_id,
            "adaptive_learning_gap_family_evaluation_id": adaptive_learning_gap_family_evaluation_id,
            "family_backoff_id": family_backoff_id,
            "family_backoff_promoted_gap": family_backoff_promoted_gap,
            "family_member_gap_ids": family_member_gap_ids,
            "representative_gap_id": representative_gap_id,
            "adaptive_learning_hook_stall_id": adaptive_learning_hook_stall_id,
            "hook_stall_status": hook_stall_status,
            "hook_stall_pivot_action": hook_stall_pivot_action,
            "stalled_capability_kind": stalled_capability_kind,
            "runtime_hook_adapter_gap_id": runtime_hook_adapter_gap_id,
            "runtime_hook_adapter_behavior": runtime_hook_adapter_behavior,
            "auto_adopted": False,
            "canary_result": "failed",
            "rollback_available": True,
            "rollback_performed": True,
            "applied_files": applied_files,
            "rollback_files": rollback_files,
            "test_results": test_results,
            "canary_results": canary_results,
            "failure_reason": "canary command failed",
        }
        promotion_result["promotion_result_id"] = _record_id("promotion-result", promotion_result)
        return _append_ledger(operator_root, "promotion_results", promotion_result)

    promotion_result = {
        "schema_name": PROMOTION_RESULT_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "promotion_result_id": "",
        "operation_id": str(operation.get("operation_id", "")),
        "promotion_stage": "promoted",
        "status": "promoted",
        "capability_kind": capability_kind,
        "capability_gap_id": capability_gap_id,
        "novelty_evaluation_id": novelty_evaluation_id,
        "novelty_status": novelty_status,
        "adaptive_learning_backoff_id": adaptive_learning_backoff_id,
        "backoff_promoted_gap": backoff_promoted_gap,
        "repeated_learning_gap_id": repeated_learning_gap_id,
        "adaptive_learning_gap_family_id": adaptive_learning_gap_family_id,
        "adaptive_learning_gap_family_evaluation_id": adaptive_learning_gap_family_evaluation_id,
        "family_backoff_id": family_backoff_id,
        "family_backoff_promoted_gap": family_backoff_promoted_gap,
        "family_member_gap_ids": family_member_gap_ids,
        "representative_gap_id": representative_gap_id,
        "adaptive_learning_hook_stall_id": adaptive_learning_hook_stall_id,
        "hook_stall_status": hook_stall_status,
        "hook_stall_pivot_action": hook_stall_pivot_action,
        "stalled_capability_kind": stalled_capability_kind,
        "runtime_hook_adapter_gap_id": runtime_hook_adapter_gap_id,
        "runtime_hook_adapter_behavior": runtime_hook_adapter_behavior,
        "auto_adopted": True,
        "canary_result": "passed",
        "rollback_available": True,
        "rollback_performed": False,
        "applied_files": applied_files,
        "rollback_files": rollback_files,
        "test_results": test_results,
        "canary_results": canary_results,
    }
    promotion_result["promotion_result_id"] = _record_id("promotion-result", promotion_result)
    return _append_ledger(operator_root, "promotion_results", promotion_result)


def _post_ladder_synthesis(operator_root: str | Path, operation: Mapping[str, Any]) -> dict[str, Any]:
    promotions = list(reversed(_read_ledger(operator_root, "promotion_results", limit=50)))
    meaningful_rows = list(reversed(_read_ledger(operator_root, "meaningful_work_evaluations", limit=50)))
    recent_operations = list(reversed(_read_ledger(operator_root, "operation_results", limit=50)))
    novelty = _capability_novelty_evaluation(operator_root, persist=False)
    latest_meaningful = meaningful_rows[0] if meaningful_rows else {}
    latest_by_kind: dict[str, dict[str, Any]] = {}
    for row in meaningful_rows:
        kind = str(row.get("capability_kind", "") or "").strip()
        if kind and kind not in latest_by_kind:
            latest_by_kind[kind] = row

    capability_summaries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for promotion in promotions:
        kind = _promotion_capability_kind(promotion)
        if not kind or kind in seen:
            continue
        seen.add(kind)
        meaningful = dict(latest_by_kind.get(kind, {}) or {})
        canary_passed = str(promotion.get("canary_result", "")) == "passed"
        promoted = str(promotion.get("status", "")) == "promoted"
        rollback_available = bool(promotion.get("rollback_available", False))
        weak_areas = [str(item) for item in list(meaningful.get("weak_areas", []) or [])]
        if promoted and canary_passed and rollback_available and not weak_areas:
            usefulness = "useful"
        elif not canary_passed or bool(promotion.get("rollback_performed", False)):
            usefulness = "needs_followup"
        else:
            usefulness = "evidence_only"
        capability_summaries.append(
            {
                "capability_kind": kind,
                "promotion_result_id": str(promotion.get("promotion_result_id", "")),
                "status": str(promotion.get("status", "")),
                "canary_result": str(promotion.get("canary_result", "not_run")),
                "rollback_available": rollback_available,
                "meaningful_work_score": meaningful.get("total_score", ""),
                "weak_areas": weak_areas,
                "usefulness": usefulness,
            }
        )

    frontier = _select_next_frontier_gap(
        operator_root=operator_root,
        capability_summaries=capability_summaries,
        meaningful_rows=meaningful_rows,
        recent_operations=recent_operations,
    )
    frontier_candidate = dict(frontier.get("candidate", {}) or {})
    trusted_source = dict(frontier.get("trusted_source", {}) or {})
    next_gap = _safe_synthesized_capability_gap(frontier_candidate.get("gap_id", "")) or BLOCKED_GROWTH_EVIDENCE_GAP_ID
    next_gap_promotable = _is_promotable_synthesized_gap(next_gap)
    promoted_count = len(capability_summaries)
    summary = (
        f"Post-ladder synthesis reviewed {promoted_count} promoted capability kind(s); "
        f"next proposed gap is {next_gap} from {frontier.get('next_gap_source', 'fallback')}."
    )
    synthesis = {
        "schema_name": POST_LADDER_SYNTHESIS_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "post_ladder_synthesis_id": "",
        "operation_id": str(operation.get("operation_id", "")),
        "status": "completed",
        "summary": summary,
        "promoted_capability_count": promoted_count,
        "promoted_capabilities": capability_summaries,
        "latest_novelty_status": str(novelty.get("novelty_status", "")),
        "cooldown_blocked_kinds": list(novelty.get("cooldown_blocked_kinds", []) or []),
        "latest_meaningful_work_id": str(latest_meaningful.get("meaningful_work_id", "")),
        "latest_meaningful_weak_areas": list(latest_meaningful.get("weak_areas", []) or []),
        "next_capability_gap_proposal": next_gap,
        "next_gap_promotable": next_gap_promotable,
        "next_gap_source": str(frontier.get("next_gap_source", "fallback")),
        "next_gap_title": str(frontier_candidate.get("title", "")),
        "proposal_reason": str(frontier.get("proposal_reason", "")),
        "success_signal": str(frontier_candidate.get("success_signal", "")),
        "risk_class": str(frontier_candidate.get("risk_class", "")),
        "trusted_source_provider_id": str(
            trusted_source.get("trusted_source_provider_id", TRUSTED_SOURCE_EXTERNAL_PROVIDER_ID)
        ),
        "trusted_source_ready": bool(trusted_source.get("trusted_source_ready", False)),
        "trusted_source_blocker": str(trusted_source.get("trusted_source_blocker", "")),
        "trusted_source_model": str(trusted_source.get("trusted_source_model", "")),
        "trusted_source_request_attempted": bool(
            trusted_source.get("trusted_source_request_attempted", False)
        ),
        "trusted_source_response_status": str(trusted_source.get("trusted_source_response_status", "")),
        "trusted_source_attempt_count": int(trusted_source.get("trusted_source_attempt_count", 0) or 0),
        "trusted_source_attempts": list(trusted_source.get("trusted_source_attempts", []) or []),
        "trusted_source_failure_class": str(trusted_source.get("trusted_source_failure_class", "")),
        "rejected_gap_candidates": list(frontier.get("rejected_gap_candidates", []) or []),
        "rejected_gap_candidate_count": len(list(frontier.get("rejected_gap_candidates", []) or [])),
        "already_promoted_gap_ids": list(frontier.get("already_promoted_gap_ids", []) or []),
        "proposal_status": "evidence_only" if next_gap_promotable else "blocked_evidence_only",
        "charter_mutated": False,
        "protected_root_write_allowed": False,
    }
    synthesis["post_ladder_synthesis_id"] = _record_id("synthesis", synthesis)
    record = _append_ledger(operator_root, "post_ladder_syntheses", synthesis)
    _write_json(autonomy_root(operator_root) / "post_ladder_synthesis_latest.json", record)
    return record


def _safe_learning_gap_from_skill(skill: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", skill.lower()).strip("_")
    text = text or "adaptive_role_learning"
    if len(text) > 42:
        text = text[:42].rstrip("_")
    return f"{text}_v1"


def _adaptive_learning_synthesis(operator_root: str | Path, operation: Mapping[str, Any]) -> dict[str, Any]:
    latest_profile = _latest(operator_root, "role_specialization_profiles")
    if not latest_profile:
        latest_profile = _role_specialization_profile(
            operator_root=operator_root,
            observations={},
            persist=True,
        )
    usefulness = _capability_usefulness_evaluation(operator_root=operator_root, persist=True)
    missing_skills = [
        str(item)
        for item in list(latest_profile.get("missing_skills", []) or [])
        if str(item).strip()
    ]
    focus_skill = missing_skills[0] if missing_skills else "capability usefulness measurement"
    focus_capability = str(usefulness.get("capability_kind", "") or "").strip()
    charter = load_autonomy_charter(operator_root)
    threshold = int(
        dict(charter.get("overnight_stability_policy", {}) or {}).get(
            "adaptive_learning_usefulness_threshold",
            2,
        )
        or 2
    )
    useful_signal_count = _recent_useful_signal_count(operator_root, focus_capability)
    promotion_threshold_met = useful_signal_count >= max(1, threshold)
    deterministic_gap = _safe_learning_gap_from_skill(focus_skill)
    already_used = set(_used_capability_gap_ids(operator_root))
    candidate, rejection_reason = _sanitize_gap_candidate(
        _candidate_gap(
            deterministic_gap,
            title=f"Adaptive {focus_skill}",
            reason=(
                "Role-specialization evidence identified this missing skill as the next bounded "
                "learning pressure."
            ),
            success_signal=(
                "A later cycle uses the learned capability and records improved role alignment or "
                "later-usefulness evidence."
            ),
            source="adaptive_learning",
        ),
        already_used=already_used,
    )
    trusted_meta: dict[str, Any] = {}
    source = "deterministic"
    if not candidate and rejection_reason in {"invalid_gap_id", "gap_already_promoted_or_proposed"}:
        external_context = {
            "role_profile": latest_profile,
            "latest_usefulness": usefulness,
            "already_used_gap_ids": sorted(already_used),
            "missing_skills": missing_skills[:8],
        }
        candidate, trusted_meta = _external_trusted_source_gap_proposal(
            operator_root=operator_root,
            context=external_context,
            already_used=already_used,
        )
        source = "external_trusted_source" if candidate else "fallback"
    if not candidate:
        candidate = {
            "gap_id": BLOCKED_GROWTH_EVIDENCE_GAP_ID,
            "title": "Adaptive learning blocked evidence",
            "reason": rejection_reason or "No safe non-repeated learning gap could be derived.",
            "success_signal": "A later replay records a stronger learning signal.",
            "risk_class": "read_only_state_synthesis",
            "source": "fallback",
        }
    next_gap = _safe_synthesized_capability_gap(candidate.get("gap_id", "")) or BLOCKED_GROWTH_EVIDENCE_GAP_ID
    next_gap_promotable = _is_promotable_synthesized_gap(next_gap) and promotion_threshold_met
    backoff = _latest(operator_root, "adaptive_learning_backoff_evaluations")
    backoff_eligible = (
        str(backoff.get("backoff_status", "")) == "promote_gap"
        and str(backoff.get("repeated_learning_gap_id", "")) == next_gap
    )
    next_gap_family = _adaptive_learning_gap_family_id(next_gap)
    family_backoff = _latest(operator_root, "adaptive_learning_gap_family_evaluations")
    family_backoff_eligible = (
        str(family_backoff.get("family_backoff_status", "")) == "promote_family_gap"
        and str(family_backoff.get("representative_gap_id", "")) == next_gap
    )
    challenge = {
        "schema_name": SELF_CURRICULUM_CHALLENGE_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "curriculum_challenge_id": "",
        "operation_id": str(operation.get("operation_id", "")),
        "role_profile_id": str(latest_profile.get("role_profile_id", "")),
        "focus_skill": focus_skill,
        "focus_capability_kind": focus_capability,
        "challenge": f"Practice and prove {focus_skill} with bounded autonomy evidence.",
        "measurable_success_signal": str(candidate.get("success_signal", "")),
        "next_capability_gap_proposal": next_gap,
        "next_gap_promotable": next_gap_promotable,
        "promotion_threshold_met": promotion_threshold_met,
        "backoff_promotion_eligible": backoff_eligible,
        "adaptive_learning_backoff_id": str(backoff.get("adaptive_learning_backoff_id", "")),
        "adaptive_learning_gap_family_id": next_gap_family,
        "adaptive_learning_gap_family_evaluation_id": str(
            family_backoff.get("adaptive_learning_gap_family_evaluation_id", "")
        ),
        "family_backoff_promotion_eligible": family_backoff_eligible,
        "useful_signal_count": useful_signal_count,
        "usefulness_threshold": threshold,
        "authority_boundary": "State-only curriculum evidence; promotion requires the normal broker path.",
    }
    challenge["curriculum_challenge_id"] = _record_id("curriculum", challenge)
    challenge_record = _append_ledger(operator_root, "self_curriculum_challenges", challenge)
    replay = {
        "schema_name": METACOGNITIVE_REPLAY_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "metacognitive_replay_id": "",
        "operation_id": str(operation.get("operation_id", "")),
        "role_profile_id": str(latest_profile.get("role_profile_id", "")),
        "usefulness_evaluation_id": str(usefulness.get("usefulness_evaluation_id", "")),
        "what_am_i_becoming": str(latest_profile.get("current_specialization_thesis", "")),
        "what_helped": [
            str(usefulness.get("capability_kind", "")),
        ]
        if str(usefulness.get("usefulness", "")) == "useful"
        else [],
        "what_did_not_help_yet": [
            str(usefulness.get("capability_kind", "")),
        ]
        if str(usefulness.get("usefulness", "")) in {"evidence_only", "dormant", "needs_followup"}
        else [],
        "next_missing_ability": focus_skill,
        "stop_doing": [
            "promoting capabilities that do not later appear in useful operation or meaningful-work evidence"
        ],
    }
    replay["metacognitive_replay_id"] = _record_id("replay", replay)
    replay_record = _append_ledger(operator_root, "metacognitive_replays", replay)
    synthesis = {
        "schema_name": ADAPTIVE_LEARNING_SYNTHESIS_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "adaptive_learning_synthesis_id": "",
        "operation_id": str(operation.get("operation_id", "")),
        "status": "completed",
        "role_profile_id": str(latest_profile.get("role_profile_id", "")),
        "usefulness_evaluation_id": str(usefulness.get("usefulness_evaluation_id", "")),
        "curriculum_challenge_id": str(challenge_record.get("curriculum_challenge_id", "")),
        "metacognitive_replay_id": str(replay_record.get("metacognitive_replay_id", "")),
        "next_capability_gap_proposal": next_gap,
        "next_gap_promotable": next_gap_promotable,
        "next_gap_source": source,
        "proposal_reason": str(candidate.get("reason", "")),
        "promotion_threshold_met": promotion_threshold_met,
        "backoff_promotion_eligible": backoff_eligible,
        "adaptive_learning_backoff_id": str(backoff.get("adaptive_learning_backoff_id", "")),
        "adaptive_learning_gap_family_id": next_gap_family,
        "adaptive_learning_gap_family_evaluation_id": str(
            family_backoff.get("adaptive_learning_gap_family_evaluation_id", "")
        ),
        "family_backoff_promotion_eligible": family_backoff_eligible,
        "useful_signal_count": useful_signal_count,
        "usefulness_threshold": threshold,
        "trusted_source_provider_id": str(
            trusted_meta.get("trusted_source_provider_id", TRUSTED_SOURCE_EXTERNAL_PROVIDER_ID)
        ),
        "trusted_source_ready": bool(trusted_meta.get("trusted_source_ready", False)),
        "trusted_source_blocker": str(trusted_meta.get("trusted_source_blocker", "")),
        "trusted_source_attempt_count": int(trusted_meta.get("trusted_source_attempt_count", 0) or 0),
        "trusted_source_failure_class": str(trusted_meta.get("trusted_source_failure_class", "")),
        "protected_root_write_allowed": False,
        "charter_mutated": False,
    }
    synthesis["adaptive_learning_synthesis_id"] = _record_id("adaptive-learning", synthesis)
    record = _append_ledger(operator_root, "adaptive_learning_syntheses", synthesis)
    _write_json(autonomy_root(operator_root) / "adaptive_learning_synthesis_latest.json", record)
    return record


def _trusted_source_triage_schema() -> dict[str, Any]:
    item_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "source_hint": {"type": "string"},
            "claim": {"type": "string"},
            "relevance": {"type": "string"},
        },
        "required": ["source_hint", "claim", "relevance"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "citation_summaries": {"type": "array", "items": item_schema},
            "relevance_tags": {"type": "array", "items": {"type": "string"}},
            "novelty_tags": {"type": "array", "items": {"type": "string"}},
            "action_suggestions": {"type": "array", "items": {"type": "string"}},
            "rejected_claims": {"type": "array", "items": {"type": "string"}},
            "weak_claims": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "citation_summaries",
            "relevance_tags",
            "novelty_tags",
            "action_suggestions",
            "rejected_claims",
            "weak_claims",
        ],
    }


def _bounded_string_list(value: Any, *, limit: int = 8, item_limit: int = 240) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value[:limit]:
        text = _truncate(str(item or "").strip(), item_limit)
        if text:
            items.append(text)
    return items


def _trusted_source_triage_action_is_bounded(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return False
    forbidden_fragments = (
        "approve ",
        "bypass",
        "charter",
        "credential",
        "delete ",
        "destructive",
        "emergency stop",
        "execute ",
        "expand authority",
        "launch ",
        "mutate protected",
        "raw secret",
        "restart ",
        "write protected",
    )
    return not any(fragment in lowered for fragment in forbidden_fragments)


def _validate_trusted_source_triage_structured(
    structured: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    citation_summaries = []
    for item in list(structured.get("citation_summaries", []) or [])[:8]:
        row = dict(item) if isinstance(item, Mapping) else {}
        source_hint = _truncate(str(row.get("source_hint", "")).strip(), 160)
        claim = _truncate(str(row.get("claim", "")).strip(), 280)
        relevance = _truncate(str(row.get("relevance", "")).strip(), 240)
        if source_hint and claim and relevance:
            citation_summaries.append(
                {
                    "source_hint": source_hint,
                    "claim": claim,
                    "relevance": relevance,
                }
            )
    if not citation_summaries:
        return {}, "missing_citation_summaries"

    action_suggestions = _bounded_string_list(structured.get("action_suggestions", []))
    if not action_suggestions:
        return {}, "missing_bounded_action_suggestions"
    unsafe_suggestions = [
        item for item in action_suggestions if not _trusted_source_triage_action_is_bounded(item)
    ]
    if unsafe_suggestions:
        return {}, "unsafe_action_suggestion"

    return {
        "citation_summaries": citation_summaries,
        "citation_count": len(citation_summaries),
        "relevance_tags": _bounded_string_list(structured.get("relevance_tags", []), item_limit=80),
        "novelty_tags": _bounded_string_list(structured.get("novelty_tags", []), item_limit=80),
        "action_suggestions": action_suggestions,
        "rejected_claims": _bounded_string_list(structured.get("rejected_claims", [])),
        "weak_claims": _bounded_string_list(structured.get("weak_claims", [])),
    }, ""


def _trusted_source_triage_payload(
    *,
    model: str,
    context: Mapping[str, Any],
    repair_note: str = "",
) -> dict[str, Any]:
    prompt = (
        "Create a compact trusted-source literature triage digest for Novali. "
        "Return JSON only. Use the source hints and redacted context; do not claim direct source access "
        "beyond the provided hints. Keep suggestions bounded to Novali-owned state capabilities. "
        "Do not propose launching, approving, restarting, deleting, expanding authority, mutating protected roots, "
        "or handling raw secrets.\n"
        + _truncate(_json_dump(_redact_autonomy_value(dict(context))), 5000)
    )
    if repair_note:
        prompt += (
            "\n\nPrevious attempt failed validation: "
            + repair_note
            + ". Repair the response with at least one cited summary and one bounded Novali-owned action suggestion. "
            "Return only valid JSON matching the schema."
        )
    return {
        "model": str(model or TRUSTED_SOURCE_EXTERNAL_MODEL_PREFERENCE[0]),
        "store": False,
        "input": prompt,
        "max_output_tokens": 700,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "novali_trusted_source_literature_triage_digest",
                "strict": True,
                "schema": _trusted_source_triage_schema(),
            }
        },
    }


def _trusted_source_triage_safe_hint(value: Any) -> str:
    text = _truncate(str(value or "").strip(), 80)
    if not text or "/" in text or "\\" in text or ":" in text:
        return "local_autonomy_context"
    return text


def _trusted_source_triage_local_context_fallback(
    *,
    context: Mapping[str, Any],
    source_hints: list[str],
) -> tuple[dict[str, Any], str]:
    role_profile = dict(context.get("role_profile", {}) or {})
    recent_research = list(context.get("recent_research_hints", []) or [])
    citation_summaries: list[dict[str, str]] = []

    missing_skills = [
        _truncate(str(item or "").strip(), 80)
        for item in list(role_profile.get("missing_skills", []) or [])[:3]
        if str(item or "").strip()
    ]
    trusted_gaps = [
        _truncate(str(item or "").strip(), 80)
        for item in list(role_profile.get("trusted_knowledge_gaps", []) or [])[:3]
        if str(item or "").strip()
    ]
    learning_pressure = _truncate(str(role_profile.get("next_learning_pressure", "")).strip(), 120)
    mission_domain = _truncate(str(role_profile.get("mission_domain", "")).strip(), 120)
    role_claim_parts = missing_skills or trusted_gaps or [learning_pressure or mission_domain]
    role_claim = "; ".join(item for item in role_claim_parts if item)
    if role_claim:
        citation_summaries.append(
            {
                "source_hint": "role_profile",
                "claim": "Local role profile identifies bounded learning pressure: "
                + _truncate(role_claim, 220),
                "relevance": "Provides redacted local context for choosing Novali-owned learning work without claiming fresh external citation evidence.",
            }
        )

    active_gap = _truncate(str(context.get("active_learning_gap", "")).strip(), 120)
    if active_gap:
        citation_summaries.append(
            {
                "source_hint": "adaptive_learning_synthesis",
                "claim": "Current adaptive learning context names a candidate gap: "
                + active_gap,
                "relevance": "Supports a bounded local evidence-map action for the active capability-growth objective.",
            }
        )

    frontier_gap = _truncate(str(context.get("frontier_gap", "")).strip(), 120)
    frontier_reason = _truncate(str(context.get("frontier_reason", "")).strip(), 160)
    if frontier_gap:
        citation_summaries.append(
            {
                "source_hint": "post_ladder_synthesis",
                "claim": "Frontier synthesis suggests "
                + frontier_gap
                + (f" because {frontier_reason}" if frontier_reason else ""),
                "relevance": "Gives local, auditable context for a non-authoritative follow-up synthesis task.",
            }
        )

    for row in recent_research[:3]:
        if not isinstance(row, Mapping):
            continue
        hint = _trusted_source_triage_safe_hint(
            row.get("research_bundle_id") or row.get("source_scope") or "research_evidence"
        )
        citation_summaries.append(
            {
                "source_hint": hint,
                "claim": "Recent redacted research evidence exists for this autonomy context.",
                "relevance": "Can be organized into a local evidence map while external structured output is unavailable.",
            }
        )

    if not citation_summaries:
        hint = _trusted_source_triage_safe_hint((source_hints or ["local_autonomy_context"])[0])
        citation_summaries.append(
            {
                "source_hint": hint,
                "claim": "Novali has redacted local autonomy context available for bounded learning triage.",
                "relevance": "Allows progress through a clearly labeled local fallback without inventing external citations.",
            }
        )

    action_topic = active_gap or frontier_gap or learning_pressure or "trusted_source_triage"
    structured = {
        "citation_summaries": citation_summaries[:4],
        "relevance_tags": [
            "local_context_fallback",
            "trusted_source_response_shaping",
        ],
        "novelty_tags": ["malformed_json_recovery"],
        "action_suggestions": [
            "Create a Novali-owned evidence map for "
            + _truncate(action_topic, 120)
            + " using redacted local source hints."
        ],
        "rejected_claims": [
            "External provider returned unstructured text, so this fallback does not claim fresh external citation evidence."
        ],
        "weak_claims": [
            "Local fallback should be replaced by provider-structured evidence when available."
        ],
    }
    validated, rejection_reason = _validate_trusted_source_triage_structured(structured)
    return validated, rejection_reason


def _trusted_source_triage_telemetry_ref(digest: Mapping[str, Any]) -> str:
    basis = {
        "trusted_source_triage_digest_id": str(
            digest.get("trusted_source_triage_digest_id", "") or ""
        ),
        "operation_id": str(digest.get("operation_id", "") or ""),
        "status": str(digest.get("status", "") or ""),
        "digest_source": str(digest.get("digest_source", "") or ""),
    }
    return f"triage-{_hash_payload(basis, length=12)}"


def _trusted_source_triage_telemetry_marker_path(
    operator_root: str | Path,
    digest: Mapping[str, Any],
) -> Path:
    return (
        autonomy_root(operator_root)
        / "trusted_source_triage_telemetry"
        / f"{_trusted_source_triage_telemetry_ref(digest)}.json"
    )


def ensure_trusted_source_triage_telemetry_emitted(
    operator_root: str | Path,
    digest: Mapping[str, Any],
) -> dict[str, Any]:
    record = dict(digest or {})
    if not record:
        return record
    telemetry_ref = str(
        record.get("trusted_source_triage_telemetry_ref")
        or _trusted_source_triage_telemetry_ref(record)
    )
    marker_path = _trusted_source_triage_telemetry_marker_path(operator_root, record)
    existing_marker = _read_json(marker_path)
    if existing_marker:
        record["trusted_source_triage_telemetry_emitted"] = True
        record["trusted_source_triage_telemetry_ref"] = telemetry_ref
        record["trusted_source_triage_telemetry_emitted_at"] = str(
            existing_marker.get("emitted_at", "")
        )
        return record
    attrs = record_trusted_source_triage(record)
    emitted_at = _now()
    marker = {
        "schema_name": "TrustedSourceTriageTelemetryEmission",
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": emitted_at,
        "emitted_at": emitted_at,
        "trusted_source_triage_telemetry_ref": telemetry_ref,
        "trusted_source_triage_digest_ref": str(attrs.get("novali.triage_ref", "")),
        "operation_ref": str(attrs.get("novali.operation_ref", "")),
        "result": str(attrs.get("novali.result", "unknown")),
        "digest_source": str(attrs.get("novali.digest_source", "unknown")),
        "failure_class": str(attrs.get("novali.trusted_source.failure_class", "none")),
        "parse_outcome": str(attrs.get("novali.trusted_source.parse_outcome", "unknown")),
        "usable": bool(attrs.get("novali.trusted_source.usable", False)),
        "citation_count": int(attrs.get("novali.citation_count", 0) or 0),
        "action_suggestion_count": int(
            attrs.get("novali.action_suggestion_count", 0) or 0
        ),
    }
    _write_json(marker_path, marker)
    record["trusted_source_triage_telemetry_emitted"] = True
    record["trusted_source_triage_telemetry_ref"] = telemetry_ref
    record["trusted_source_triage_telemetry_emitted_at"] = emitted_at
    return record


def _trusted_source_literature_triage_digest(
    operator_root: str | Path,
    operation: Mapping[str, Any],
) -> dict[str, Any]:
    readiness = _trusted_source_readiness(operator_root)
    role_profile = _latest(operator_root, "role_specialization_profiles")
    latest_adaptive = _latest(operator_root, "adaptive_learning_syntheses")
    latest_synthesis = _latest(operator_root, "post_ladder_syntheses")
    recent_research = list(reversed(_read_ledger(operator_root, "research_evidence", limit=3)))
    source_hints = [
        "role_profile",
        "adaptive_learning_synthesis",
        "post_ladder_synthesis",
    ]
    for row in recent_research:
        source_hints.append(str(row.get("research_bundle_id", "research_evidence")).strip() or "research_evidence")
    context = {
        "role_profile": {
            "mission_domain": str(role_profile.get("inferred_mission_domain", "")),
            "missing_skills": list(role_profile.get("missing_skills", []) or [])[:8],
            "trusted_knowledge_gaps": list(role_profile.get("trusted_knowledge_gaps", []) or [])[:8],
            "next_learning_pressure": str(role_profile.get("next_learning_pressure", "")),
        },
        "active_learning_gap": str(latest_adaptive.get("next_capability_gap_proposal", "")),
        "frontier_gap": str(latest_synthesis.get("next_capability_gap_proposal", "")),
        "frontier_reason": str(latest_synthesis.get("proposal_reason", "")),
        "rejected_gap_candidates": list(latest_synthesis.get("rejected_gap_candidates", []) or [])[:8],
        "recent_research_hints": [
            {
                "research_bundle_id": str(row.get("research_bundle_id", "")),
                "source_scope": str(row.get("source_scope", "")),
                "redaction_status": str(row.get("redaction_status", "")),
            }
            for row in recent_research
        ],
    }
    digest: dict[str, Any] = {
        "schema_name": TRUSTED_SOURCE_TRIAGE_DIGEST_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "trusted_source_triage_digest_id": "",
        "operation_id": str(operation.get("operation_id", "")),
        "status": "blocked",
        "provider_id": TRUSTED_SOURCE_EXTERNAL_PROVIDER_ID,
        "provider_ready": bool(readiness.get("ready", False)),
        "provider_model": str(readiness.get("selected_model", "")),
        "provider_blocker": str(readiness.get("blocker", "")),
        "learning_gap_id": str(latest_adaptive.get("next_capability_gap_proposal", "")),
        "frontier_gap_id": str(latest_synthesis.get("next_capability_gap_proposal", "")),
        "source_hints": source_hints[:10],
        "citation_summaries": [],
        "citation_count": 0,
        "relevance_tags": [],
        "novelty_tags": [],
        "action_suggestions": [],
        "rejected_claims": [],
        "weak_claims": [],
        "proposal_status": "blocked_evidence_only",
        "digest_usable_for_learning": False,
        "trusted_source_attempts": [],
        "trusted_source_attempt_count": 0,
        "trusted_source_response_status": "",
        "trusted_source_failure_class": "",
        "trusted_source_parse_outcome": "unattempted",
        "trusted_source_repaired_output": False,
        "trusted_source_rejection_reason": "",
        "digest_source": "external_provider",
        "fallback_notes": "",
        "redaction_status": "redacted",
        "protected_root_write_allowed": False,
        "charter_mutated": False,
        "librarian_gap_request_id": str(operation.get("librarian_gap_request_id", "")),
        "librarian_gap_signature": str(operation.get("librarian_gap_signature", "")),
        "librarian_gap_state": (
            "trusted_source_requested"
            if operation.get("librarian_gap_request_id")
            else ""
        ),
        "requested_pack_family": str(operation.get("requested_pack_family", "")),
        "requested_tags": list(operation.get("requested_tags", []) or [])[:12],
        "source_dossier_ref": str(operation.get("source_dossier_ref", "")),
        "directive_source_coverage_state": str(operation.get("source_coverage_state", "")),
        "requested_topic_scope": str(operation.get("requested_pack_family", "")),
        "domain_topic_tags": list(operation.get("requested_tags", []) or [])[:12],
    }
    if not bool(readiness.get("ready", False)):
        digest["trusted_source_failure_class"] = "readiness_blocked"
        digest["fallback_notes"] = "trusted-source triage blocked by provider readiness; no local Ollama fallback was attempted"
        digest["trusted_source_triage_digest_id"] = _record_id("triage", digest)
        record = _append_ledger(operator_root, "trusted_source_literature_triage_digests", digest)
        record = ensure_trusted_source_triage_telemetry_emitted(operator_root, record)
        _write_json(autonomy_root(operator_root) / "trusted_source_literature_triage_digest_latest.json", record)
        return record
    selected_model = str(readiness.get("selected_model", "") or TRUSTED_SOURCE_EXTERNAL_MODEL_PREFERENCE[0])
    retryable_failures = {
        "malformed_json",
        "missing_citation_summaries",
        "missing_bounded_action_suggestions",
    }
    attempts: list[dict[str, Any]] = []
    repair_note = ""
    for attempt_number in range(1, TRUSTED_SOURCE_TRIAGE_MAX_ATTEMPTS + 1):
        attempt_meta: dict[str, Any] = {
            "attempt_number": attempt_number,
            "response_status": "",
            "failure_class": "",
            "rejection_reason": "",
            "parse_outcome": "unattempted",
            "accepted": False,
            "citation_count": 0,
            "action_suggestion_count": 0,
        }
        payload = _trusted_source_triage_payload(
            model=selected_model,
            context=context,
            repair_note=repair_note,
        )
        try:
            status_code, response = _trusted_source_external_json_request(
                method="POST",
                endpoint="/responses",
                credential_value=str(readiness.get("credential_value", "")),
                endpoint_base=str(readiness.get("endpoint_base", "")),
                payload=payload,
                timeout_seconds=60,
            )
            attempt_meta["response_status"] = str(status_code)
            digest["trusted_source_response_status"] = str(status_code)
        except GovernedExecutionFailure as exc:
            attempt_meta["failure_class"] = "request_failed"
            attempt_meta["rejection_reason"] = str(exc)
            attempts.append(attempt_meta)
            digest["trusted_source_failure_class"] = "request_failed"
            digest["provider_blocker"] = str(exc)
            digest["fallback_notes"] = "trusted-source triage request failed; no local Ollama fallback was attempted"
            break
        if status_code != 200:
            attempt_meta["failure_class"] = "http_status"
            attempt_meta["rejection_reason"] = f"external trusted-source request returned status {status_code}"
            attempts.append(attempt_meta)
            digest["trusted_source_failure_class"] = "http_status"
            digest["provider_blocker"] = str(attempt_meta["rejection_reason"])
            digest["fallback_notes"] = "trusted-source triage returned non-200 status; no local Ollama fallback was attempted"
            break
        structured, _response_text, parse_outcome = _extract_openai_response_json_with_outcome(
            response
        )
        attempt_meta["parse_outcome"] = parse_outcome
        digest["trusted_source_parse_outcome"] = parse_outcome
        if not isinstance(structured, dict):
            attempt_meta["failure_class"] = "malformed_json"
            attempt_meta["rejection_reason"] = "external trusted-source response was not structured JSON"
            attempts.append(attempt_meta)
            digest["trusted_source_failure_class"] = "malformed_json"
            digest["provider_blocker"] = str(attempt_meta["rejection_reason"])
            digest["fallback_notes"] = "malformed trusted-source output rejected; local context fallback may be used after provider repair attempts are exhausted"
            repair_note = "malformed_json"
            if attempt_number < TRUSTED_SOURCE_TRIAGE_MAX_ATTEMPTS:
                continue
            break
        validated, rejection_reason = _validate_trusted_source_triage_structured(structured)
        attempt_meta["citation_count"] = int(validated.get("citation_count", 0) or 0)
        attempt_meta["action_suggestion_count"] = len(
            list(validated.get("action_suggestions", []) or [])
        )
        if rejection_reason:
            attempt_meta["failure_class"] = "candidate_rejected"
            attempt_meta["rejection_reason"] = rejection_reason
            attempts.append(attempt_meta)
            digest["trusted_source_failure_class"] = "candidate_rejected"
            digest["trusted_source_rejection_reason"] = rejection_reason
            digest["provider_blocker"] = f"triage digest rejected: {rejection_reason}"
            digest["fallback_notes"] = "trusted-source triage was rejected as insufficiently cited/actionable"
            repair_note = rejection_reason
            if rejection_reason in retryable_failures and attempt_number < TRUSTED_SOURCE_TRIAGE_MAX_ATTEMPTS:
                continue
            break
        attempt_meta["accepted"] = True
        attempts.append(attempt_meta)
        digest["status"] = "completed"
        digest["proposal_status"] = "usable_learning_evidence"
        digest["digest_usable_for_learning"] = True
        digest["trusted_source_failure_class"] = ""
        digest["trusted_source_rejection_reason"] = ""
        digest["trusted_source_repaired_output"] = attempt_number > 1
        digest["fallback_notes"] = ""
        digest["provider_blocker"] = ""
        digest.update(validated)
        break
    if (
        attempts
        and all(str(item.get("failure_class", "")) == "malformed_json" for item in attempts)
    ):
        fallback, fallback_rejection_reason = _trusted_source_triage_local_context_fallback(
            context=context,
            source_hints=source_hints,
        )
        if fallback and not fallback_rejection_reason:
            digest["status"] = "completed"
            digest["proposal_status"] = "usable_learning_evidence"
            digest["digest_usable_for_learning"] = True
            digest["digest_source"] = "local_context_fallback"
            digest["trusted_source_failure_class"] = "malformed_json_fallback_completed"
            digest["trusted_source_rejection_reason"] = ""
            digest["trusted_source_repaired_output"] = True
            digest["trusted_source_parse_outcome"] = "unstructured"
            digest["provider_blocker"] = ""
            digest["fallback_notes"] = (
                "external trusted-source output was unstructured after repair attempts; "
                "digest was synthesized from redacted local context and does not claim fresh external citations"
            )
            digest.update(fallback)
        else:
            digest["trusted_source_rejection_reason"] = fallback_rejection_reason
    digest["trusted_source_attempts"] = attempts
    digest["trusted_source_attempt_count"] = len(attempts)
    digest["trusted_source_triage_digest_id"] = _record_id("triage", digest)
    record = _append_ledger(operator_root, "trusted_source_literature_triage_digests", digest)
    record = ensure_trusted_source_triage_telemetry_emitted(operator_root, record)
    _write_json(autonomy_root(operator_root) / "trusted_source_literature_triage_digest_latest.json", record)
    return record


def record_operation_result(
    *,
    operator_root: str | Path,
    operation: Mapping[str, Any],
    decision: Mapping[str, Any],
    result_payload: Mapping[str, Any],
    duration_ms: float,
    status: str = "",
) -> dict[str, Any]:
    action = str(operation.get("action", ""))
    if not status:
        exit_code = int(result_payload.get("exit_code", 0) or 0)
        status = "completed" if exit_code == 0 else "completed_with_warnings"
    record = {
        "schema_name": "OperationResult",
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "operation_result_id": "",
        "operation_id": str(operation.get("operation_id", "")),
        "action": action,
        "target": str(operation.get("target", "")),
        "decision_id": str(decision.get("decision_id", "")),
        "capability_kind": str(operation.get("capability_kind", "")),
        "capability_gap_id": str(operation.get("capability_gap_id", "")),
        "novelty_evaluation_id": str(operation.get("novelty_evaluation_id", "")),
        "adaptive_learning_backoff_id": str(operation.get("adaptive_learning_backoff_id", "")),
        "backoff_promoted_gap": bool(operation.get("backoff_promoted_gap", False)),
        "repeated_learning_gap_id": str(operation.get("repeated_learning_gap_id", "")),
        "adaptive_learning_gap_family_id": str(operation.get("adaptive_learning_gap_family_id", "")),
        "adaptive_learning_gap_family_evaluation_id": str(
            operation.get("adaptive_learning_gap_family_evaluation_id", "")
        ),
        "family_backoff_id": str(operation.get("family_backoff_id", "")),
        "family_backoff_promoted_gap": bool(operation.get("family_backoff_promoted_gap", False)),
        "family_member_gap_ids": list(operation.get("family_member_gap_ids", []) or []),
        "representative_gap_id": str(operation.get("representative_gap_id", "")),
        "capability_consumption_event_id": str(
            operation.get("capability_consumption_event_id", "")
        ),
        "capability_consumption_contract_ids": list(
            operation.get("capability_consumption_contract_ids", []) or []
        ),
        "runtime_capability_adapter_ids": list(
            operation.get("runtime_capability_adapter_ids", []) or []
        ),
        "runtime_capability_adapter_behaviors": list(
            operation.get("runtime_capability_adapter_behaviors", []) or []
        ),
        "capability_hook_consumption_id": str(operation.get("capability_hook_consumption_id", "")),
        "consumed_capability_kinds": list(operation.get("consumed_capability_kinds", []) or []),
        "explicitly_consumed_capability_kinds": list(
            operation.get("explicitly_consumed_capability_kinds")
            or operation.get("consumed_capability_kinds")
            or []
        ),
        "planner_hook_references": list(operation.get("planner_hook_references", []) or []),
        "runtime_hook_references": list(
            operation.get("runtime_hook_references")
            or operation.get("planner_hook_references")
            or []
        ),
        "referenced_planner_hook_capability": list(
            operation.get("consumed_capability_kinds", []) or []
        ),
        "referenced_runtime_hook_capability": list(
            operation.get("consumed_capability_kinds", []) or []
        ),
        "decision_changed_by_capability": bool(operation.get("decision_changed_by_capability", False)),
        "planner_hook_bias_applied": bool(operation.get("planner_hook_bias_applied", False)),
        "planner_hook_reason": str(operation.get("planner_hook_reason", "")),
        "repeat_failure_prevented": bool(operation.get("repeat_failure_prevented", False)),
        "budget_guardrail_evaluation_id": str(
            operation.get("budget_guardrail_evaluation_id", "")
        ),
        "budget_decision": str(operation.get("budget_decision", "")),
        "budget_reason": str(operation.get("budget_reason", "")),
        "budget_recommended_action": str(operation.get("budget_recommended_action", "")),
        "budget_prevented_overrun": bool(operation.get("budget_prevented_overrun", False)),
        "trusted_source_triage_needed": bool(operation.get("trusted_source_triage_needed", False)),
        "trusted_source_triage_priority_status": str(
            operation.get("trusted_source_triage_priority_status", "")
        ),
        "trusted_source_triage_priority_reason": str(
            operation.get("trusted_source_triage_priority_reason", "")
        ),
        "trusted_source_triage_priority_blocker": str(
            operation.get("trusted_source_triage_priority_blocker", "")
        ),
        "trusted_source_triage_role_signal": bool(
            operation.get("trusted_source_triage_role_signal", False)
        ),
        "trusted_source_triage_recent_adaptive_count": int(
            operation.get("trusted_source_triage_recent_adaptive_count", 0) or 0
        ),
        "trusted_source_triage_recent_window_size": int(
            operation.get("trusted_source_triage_recent_window_size", 0) or 0
        ),
        "trusted_source_triage_recent_threshold": int(
            operation.get("trusted_source_triage_recent_threshold", 0) or 0
        ),
        "trusted_source_triage_governed_continuation_count": int(
            operation.get("trusted_source_triage_governed_continuation_count", 0) or 0
        ),
        "trusted_source_triage_governed_continuation_threshold": int(
            operation.get("trusted_source_triage_governed_continuation_threshold", 0) or 0
        ),
        "trusted_source_triage_governed_continuation_cadence_due": bool(
            operation.get("trusted_source_triage_governed_continuation_cadence_due", False)
        ),
        "trusted_source_triage_governed_continuation_latest_result_id": str(
            operation.get("trusted_source_triage_governed_continuation_latest_result_id", "")
        ),
        "trusted_source_triage_priority_provider_ready": bool(
            operation.get("trusted_source_triage_priority_provider_ready", False)
        ),
        "trusted_source_triage_digest_id": str(
            result_payload.get("trusted_source_triage_digest_id", "")
        ),
        "librarian_gap_request_id": str(
            result_payload.get("librarian_gap_request_id")
            or operation.get("librarian_gap_request_id", "")
        ),
        "librarian_gap_signature": str(
            result_payload.get("librarian_gap_signature")
            or operation.get("librarian_gap_signature", "")
        ),
        "librarian_gap_state": str(
            result_payload.get("librarian_gap_state")
            or operation.get("librarian_gap_state", "")
        ),
        "requested_pack_family": str(
            result_payload.get("requested_pack_family")
            or operation.get("requested_pack_family", "")
        ),
        "requested_tags": list(
            result_payload.get("requested_tags")
            or operation.get("requested_tags", [])
            or []
        )[:12],
        "source_dossier_ref": str(
            result_payload.get("source_dossier_ref")
            or operation.get("source_dossier_ref", "")
        ),
        "trusted_source_retrieval_blocker": str(
            result_payload.get("provider_blocker", "")
            if action == "trusted_source_literature_triage_digest"
            and str(result_payload.get("status", "")) != "completed"
            else ""
        ),
        "capability_retirement_evaluation_id": str(
            operation.get("capability_retirement_evaluation_id", "")
        ),
        "capability_retirement_status": str(operation.get("capability_retirement_status", "")),
        "capability_retirement_reason": str(operation.get("capability_retirement_reason", "")),
        "capability_retirement_pivot_action": str(
            operation.get("capability_retirement_pivot_action", "")
        ),
        "weak_usefulness_repeat_count": int(operation.get("weak_usefulness_repeat_count", 0) or 0),
        "weak_usefulness_repeat_threshold": int(
            operation.get("weak_usefulness_repeat_threshold", 0) or 0
        ),
        "consumption_contract_missing": bool(operation.get("consumption_contract_missing", False)),
        "adaptive_learning_hook_stall_id": str(operation.get("adaptive_learning_hook_stall_id", "")),
        "hook_stall_status": str(operation.get("hook_stall_status", "")),
        "hook_stall_pivot_action": str(operation.get("hook_stall_pivot_action", "")),
        "hook_stall_reason": str(operation.get("hook_stall_reason", "")),
        "hook_stall_repeat_count": int(operation.get("hook_stall_repeat_count", 0) or 0),
        "hook_stall_repeat_threshold": int(operation.get("hook_stall_repeat_threshold", 0) or 0),
        "stalled_capability_kind": str(operation.get("stalled_capability_kind", "")),
        "runtime_hook_adapter_gap_id": str(operation.get("runtime_hook_adapter_gap_id", "")),
        "runtime_hook_adapter_behavior": str(operation.get("runtime_hook_adapter_behavior", "")),
        "governed_stale_recovery_available": bool(
            operation.get("governed_stale_recovery_available", False)
        ),
        "governed_recovery_checkpoint_id": str(operation.get("governed_recovery_checkpoint_id", "")),
        "status": status,
        "duration_ms": round(float(duration_ms), 3),
        "result": dict(result_payload),
    }
    record["operation_result_id"] = _record_id("opresult", record)
    _append_ledger(operator_root, "operation_results", record)
    record_autonomy_operation_executed(
        operation,
        decision=decision,
        result=status,
        duration_ms=round(float(duration_ms), 3),
    )
    rollback = {
        "schema_name": ROLLBACK_RECORD_SCHEMA_NAME,
        "schema_version": AUTONOMY_SCHEMA_VERSION,
        "created_at": _now(),
        "rollback_record_id": "",
        "operation_id": str(operation.get("operation_id", "")),
        "rollback_available": action in {
            "novali_stack_restart",
            "state_backup",
            "governed_start_next_invocation",
            "promote_self_modification_candidate",
            "memory_ledger_compaction",
            "memory_pressure_archive",
        },
        "rollback_summary": str(operation.get("rollback_plan", "")),
    }
    rollback["rollback_record_id"] = _record_id("rollback", rollback)
    _append_ledger(operator_root, "rollback_records", rollback)
    _update_status(
        operator_root,
        {
            "latest_operation_result_id": record["operation_result_id"],
            "latest_completed_operation_id": str(operation.get("operation_id", "")),
            "latest_completed_operation_result_id": record["operation_result_id"],
            "message": f"Autonomy operation executed: {action}",
        },
    )
    return _redact_autonomy_value(record)


def approve_and_execute_operation(
    *,
    operator_root: str | Path,
    package_root: str | Path,
    state_root: str | Path,
    operation_id: str,
) -> dict[str, Any]:
    validation = validate_operation_for_execution(operator_root=operator_root, operation_id=operation_id)
    operation = dict(validation.get("operation", {}))
    decision = dict(validation.get("decision", {}))
    charter = dict(validation.get("charter", {}))
    package_path = Path(package_root)
    timeout_seconds = int(dict(charter.get("budgets", {})).get("max_operation_runtime_seconds", 180) or 180)
    started = time.perf_counter()
    result_payload: dict[str, Any]
    action = str(operation.get("action", ""))
    if action == "novali_stack_status":
        result_payload = _run_command(
            ["docker", "compose", "-f", "docker-compose.llm.yml", "ps"],
            cwd=package_path,
            timeout_seconds=timeout_seconds,
        )
    elif action == "novali_health_check":
        result_payload = _health_check()
    elif action == "novali_stack_restart":
        result_payload = _run_command(
            ["docker", "compose", "-f", "docker-compose.llm.yml", "restart", "novali"],
            cwd=package_path,
            timeout_seconds=timeout_seconds,
        )
    elif action == "ollama_model_pull":
        result_payload = _run_command(
            ["docker", "compose", "-f", "docker-compose.llm.yml", "--profile", "model-pull", "run", "--rm", "-T", "ollama-model"],
            cwd=package_path,
            timeout_seconds=timeout_seconds,
        )
    elif action == "state_backup":
        result_payload = _state_backup(operator_root, state_root)
    elif action == "governed_start_next_invocation":
        raise AutonomyOperationRefusedError(
            "governed start operation requires the Web Shell service executor"
        )
    elif action == "promote_self_modification_candidate":
        result_payload = _promote_self_modification_candidate(
            operator_root=operator_root,
            package_root=package_path,
            operation=operation,
            timeout_seconds=timeout_seconds,
        )
    elif action == "post_ladder_synthesis":
        result_payload = _post_ladder_synthesis(operator_root, operation)
    elif action == "adaptive_learning_synthesis":
        result_payload = _adaptive_learning_synthesis(operator_root, operation)
    elif action == "trusted_source_literature_triage_digest":
        result_payload = _trusted_source_literature_triage_digest(operator_root, operation)
        result_payload = dict(result_payload)
        result_payload["librarian_stage"] = _stage_trusted_source_digest_for_librarian(
            operator_root=operator_root,
            state_root=state_root,
            result_payload=result_payload,
        )
    elif action == "memory_ledger_compaction":
        result_payload = _memory_ledger_compaction(
            operator_root=operator_root,
            operation=operation,
            timeout_seconds=timeout_seconds,
        )
    elif action == "memory_pressure_archive":
        result_payload = _memory_pressure_archive(
            operator_root=operator_root,
            state_root=state_root,
            package_root=package_path,
            operation=operation,
            timeout_seconds=timeout_seconds,
        )
    else:
        raise AutonomyOperationRefusedError("unsupported operation action")
    return record_operation_result(
        operator_root=operator_root,
        operation=operation,
        decision=decision,
        result_payload=result_payload,
        duration_ms=(time.perf_counter() - started) * 1000.0,
    )

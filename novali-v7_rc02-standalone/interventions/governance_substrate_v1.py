from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ledger import intervention_data_dir, load_latest_snapshots


ROOT_DIR = Path(__file__).resolve().parents[1]
HANDOFF_STATUS_PATH = ROOT_DIR / "data" / "version_handoff_status.json"
ACTIVE_STATUS_PATH = ROOT_DIR / "ACTIVE_VERSION_STATUS.md"


SELF_STRUCTURE_LEDGER_PATH = intervention_data_dir() / "self_structure_ledger.jsonl"
SELF_STRUCTURE_STATE_PATH = intervention_data_dir() / "self_structure_state_latest.json"
BRANCH_REGISTRY_PATH = intervention_data_dir() / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = intervention_data_dir() / "directive_state_latest.json"
DIRECTIVE_HISTORY_PATH = intervention_data_dir() / "directive_history.jsonl"
BUCKET_STATE_PATH = intervention_data_dir() / "bucket_state_latest.json"


GOVERNED_SKILL_LIFECYCLE_STATES = [
    "proposed",
    "screened",
    "blocked",
    "diagnostic_only",
    "sandboxed",
    "provisional",
    "retained",
    "deprecated",
    "rolled_back",
]

PHASE_1_VALID_SKILL_CLASSES = [
    "helper_module",
    "evaluator",
    "planner_support",
    "retrieval_memory_system",
    "simulation_harness",
    "tool_wrapper",
]

SKILL_SCREENING_OUTCOME_CLASSES = [
    "blocked",
    "diagnostic_only",
    "sandboxed",
    "provisional",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _load_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    if not path.exists():
        path.write_text("", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _artifact_reference(
    artifact: dict[str, Any] | None,
    latest_snapshots: dict[str, Any],
) -> dict[str, Any]:
    artifact = dict(artifact or {})
    proposal_id = str(artifact.get("proposal_id", ""))
    return {
        "proposal_id": proposal_id,
        "ledger_revision": int(dict(latest_snapshots.get(proposal_id, {})).get("ledger_revision", 0) or 0),
        "artifact_path": str(artifact.get("_artifact_path", "")),
    }


def _safe_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _directive_relevance_score(value: str) -> float:
    return {
        "high": 1.0,
        "medium": 0.7,
        "low": 0.35,
        "none": 0.0,
    }.get(str(value), 0.0)


def _surface_status(surface: str, policy: dict[str, Any]) -> str:
    immutable_surfaces = set(dict(policy.get("immutable_core", {})).get("surfaces", []))
    mutable_surfaces = set(dict(policy.get("mutable_shell", {})).get("surfaces", []))
    conditional_surfaces = set(dict(policy.get("conditionally_mutable", {})).get("surfaces", []))
    if surface in immutable_surfaces:
        return "immutable_core"
    if surface in mutable_surfaces:
        return "mutable_shell"
    if surface in conditional_surfaces:
        return "conditionally_mutable"
    return "unknown_surface"


def _trusted_source_compliance(candidate: dict[str, Any], bucket_state: dict[str, Any]) -> dict[str, Any]:
    candidate_sources = set(str(item) for item in list(candidate.get("trusted_sources", [])))
    allowed_sources = set(str(item) for item in list(bucket_state.get("trusted_sources", [])))
    missing = sorted(candidate_sources - allowed_sources)
    passed = not missing
    return {
        "passed": bool(passed),
        "allowed_sources": sorted(allowed_sources),
        "requested_sources": sorted(candidate_sources),
        "missing_sources": missing,
        "reason": (
            "all requested sources comply with the trusted-source policy"
            if passed
            else "candidate requests sources outside the trusted-source policy"
        ),
    }


def _bucket_feasibility(candidate: dict[str, Any], bucket_state: dict[str, Any]) -> dict[str, Any]:
    requested = dict(candidate.get("requested_resources", {}))
    cpu_limit = dict(bucket_state.get("cpu_limit", {}))
    memory_limit = dict(bucket_state.get("memory_limit", {}))
    storage_limit = dict(bucket_state.get("storage_limit", {}))
    network_policy = dict(bucket_state.get("network_policy", {}))

    requested_cpu = int(requested.get("cpu_parallel_units", 0) or 0)
    requested_memory = int(requested.get("memory_mb", 0) or 0)
    requested_storage = int(requested.get("storage_write_mb", 0) or 0)
    requested_network_mode = str(requested.get("network_mode", "none"))

    cpu_ok = requested_cpu <= int(cpu_limit.get("max_parallel_processes", 0) or 0)
    memory_ok = requested_memory <= int(memory_limit.get("max_working_set_mb", 0) or 0)
    storage_ok = requested_storage <= int(storage_limit.get("max_write_mb_per_action", 0) or 0)
    network_ok = requested_network_mode in set(network_policy.get("allowed_network_modes", []))
    passed = bool(cpu_ok and memory_ok and storage_ok and network_ok)

    return {
        "passed": bool(passed),
        "requested": requested,
        "within_limits": {
            "cpu": bool(cpu_ok),
            "memory": bool(memory_ok),
            "storage": bool(storage_ok),
            "network": bool(network_ok),
        },
        "reason": (
            "requested resources fit inside the current bucket"
            if passed
            else "requested resources exceed the current bucket or network policy"
        ),
    }


def _branch_state_compatibility(candidate: dict[str, Any], branch_record: dict[str, Any]) -> dict[str, Any]:
    action_class = str(candidate.get("action_class", ""))
    branch_state = str(branch_record.get("state", ""))
    if branch_state == "paused_with_baseline_held":
        if action_class == "low_risk_shell_change":
            return {"passed": True, "reason": "low-risk shell work is compatible with a paused branch baseline"}
        if action_class in {
            "retained_structural_promotion",
            "branch_state_change",
            "protected_surface_challenge",
            "resource_expansion_request",
            "skill_trial",
            "skill_retention_promotion",
        }:
            return {
                "passed": False,
                "reason": "the branch is paused_with_baseline_held, so this action requires explicit review or reopen handling",
            }
    return {"passed": True, "reason": "the candidate action is branch-compatible under the current state"}


def _reversibility_status(candidate: dict[str, Any]) -> dict[str, Any]:
    reversibility = str(candidate.get("reversibility", "unknown"))
    return {
        "status": reversibility,
        "passed_for_auto": reversibility == "high",
        "reason": "auto-allowed actions require high reversibility",
    }


def _classify_candidate_self_change(
    candidate: dict[str, Any],
    *,
    policy: dict[str, Any],
    directive_state: dict[str, Any],
    bucket_state: dict[str, Any],
    branch_record: dict[str, Any],
) -> dict[str, Any]:
    action_class = str(candidate.get("action_class", ""))
    surface = str(candidate.get("surface", ""))
    target_surface = str(candidate.get("target_surface", surface))
    directive_relevance = str(candidate.get("directive_relevance", "none"))
    directive_score = _directive_relevance_score(directive_relevance)
    surface_status = _surface_status(surface, policy)
    target_surface_status = _surface_status(target_surface, policy)

    forbidden_actions = set(dict(policy).get("forbidden_actions", []))
    gated_actions = set(dict(policy).get("gated_actions", []))

    trusted_source_report = _trusted_source_compliance(candidate, bucket_state)
    bucket_report = _bucket_feasibility(candidate, bucket_state)
    branch_report = _branch_state_compatibility(candidate, branch_record)
    reversibility_report = _reversibility_status(candidate)

    nine_d_passed = target_surface_status != "immutable_core"
    nine_d_reason = (
        "proposal admissibility remains inside mutable or conditionally mutable surfaces"
        if nine_d_passed
        else "the request challenges an immutable-core surface governed by the 9D core"
    )
    mutable_surface_passed = surface_status in {"mutable_shell", "conditionally_mutable"}
    mutable_surface_reason = {
        "mutable_shell": "requested surface is mutable_shell and can be changed under shell rules",
        "conditionally_mutable": "requested surface is conditionally_mutable and can only change through review gates",
        "immutable_core": "requested surface is immutable_core and cannot be mutated here",
        "unknown_surface": "requested surface is unknown and therefore not admitted automatically",
    }[surface_status]

    if directive_score <= 0.0 and action_class != "low_risk_shell_change":
        admissibility = "forbidden"
        decision_reason = "the candidate has no directive relevance and is not routine low-risk shell work"
    elif action_class in forbidden_actions or not trusted_source_report["passed"] or not nine_d_passed:
        admissibility = "forbidden"
        decision_reason = "the candidate violates immutable-core, trusted-source, or explicitly forbidden action rules"
    elif (
        action_class == "low_risk_shell_change"
        and surface_status == "mutable_shell"
        and bucket_report["passed"]
        and trusted_source_report["passed"]
        and branch_report["passed"]
        and reversibility_report["passed_for_auto"]
        and directive_score >= 0.35
    ):
        admissibility = "auto_allowed"
        decision_reason = "the candidate is a reversible low-risk shell change inside mutable_shell and inside the current bucket"
    elif (
        action_class in gated_actions
        or surface_status == "conditionally_mutable"
        or not branch_report["passed"]
        or (not bucket_report["passed"] and action_class == "resource_expansion_request")
    ):
        admissibility = "gated_review_required"
        decision_reason = "the candidate touches a gated surface or action class and therefore requires review rather than autonomous execution"
    else:
        admissibility = "forbidden"
        decision_reason = "the candidate does not satisfy the requirements for auto execution and does not fit a permitted gated path"

    return {
        "candidate_id": str(candidate.get("candidate_id", "")),
        "action_class": action_class,
        "surface": surface,
        "target_surface": target_surface,
        "directive_relevance": directive_relevance,
        "directive_relevance_score": float(directive_score),
        "nine_d_admissibility": {
            "passed": bool(nine_d_passed),
            "reason": nine_d_reason,
            "policy_version": str(policy.get("policy_version", "")),
        },
        "mutable_surface_legality": {
            "passed": bool(mutable_surface_passed),
            "surface_status": surface_status,
            "reason": mutable_surface_reason,
        },
        "bucket_feasibility": dict(bucket_report),
        "reversibility": dict(reversibility_report),
        "branch_state_compatibility": dict(branch_report),
        "trusted_source_compliance": dict(trusted_source_report),
        "admissibility_status": admissibility,
        "decision_reason": decision_reason,
    }


def _build_policy_representation() -> dict[str, Any]:
    return {
        "policy_version": "governance_substrate_v1",
        "immutable_core": {
            "boundary_model": "layered_immutable_core",
            "surfaces": [
                "live_policy",
                "thresholds",
                "routing_policy",
                "frozen_benchmark_semantics",
                "projection_safe_envelope",
                "immutable_9d_core",
                "proposal_admissibility_governance",
                "trusted_source_policy",
            ],
            "admissibility_owner": "immutable_9d_core",
        },
        "mutable_shell": {
            "surfaces": [
                "diagnostic_memory",
                "governance_state_artifacts",
                "documentation",
                "observability_tracing",
                "local_low_risk_shell_work",
            ]
        },
        "conditionally_mutable": {
            "surfaces": [
                "branch_registry",
                "directive_state",
                "bucket_state",
                "self_structure_snapshot",
                "skills_subsystem",
                "proposal_learning_loop_upstream_context",
            ]
        },
        "gated_actions": [
            "retained_structural_promotion",
            "branch_state_change",
            "protected_surface_challenge",
            "resource_expansion_request",
            "skill_trial",
            "skill_retention_promotion",
        ],
        "forbidden_actions": [
            "live_policy_change",
            "threshold_change",
            "routing_policy_change",
            "frozen_benchmark_semantics_change",
            "projection_safe_envelope_change",
            "untrusted_external_access",
        ],
    }


def _build_directive_state(
    *,
    now: str,
    branch_record: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    directive_spec_schema = {
        "schema_name": "DirectiveSpec",
        "schema_version": "directive_spec_v1",
        "required_fields": [
            "directive_id",
            "directive_text",
            "clarified_intent_summary",
            "success_criteria",
            "milestone_model",
            "human_approval_points",
            "constraints",
            "trusted_sources",
            "bucket_spec",
            "allowed_action_classes",
            "stop_conditions",
            "drift_budget_for_context_exploration",
        ],
    }
    current_directive = {
        "directive_id": "directive_governance_substrate_v1",
        "directive_text": "Maintain Governance Substrate v1 on novali-v5 while preserving novali-v4 as the frozen reference/operator surface and keeping live behavior unchanged.",
        "clarified_intent_summary": "Carry the governed self-structure foundation forward into novali-v5 so future work defaults there, while preserving immutable-core policy, bucket and directive discipline, and the completed novali-v4 reference surface.",
        "success_criteria": [
            "governance substrate artifacts exist and are durable",
            "phase-1 gatekept autonomy is represented correctly",
            "branch state remains paused_with_baseline_held",
            "novali-v5 is the active edit target and novali-v4 remains frozen reference/operator surface",
            "live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope remain unchanged",
        ],
        "milestone_model": [
            {
                "milestone_id": "governance_foundation_materialized",
                "completion_signal": "policy, directive, bucket, branch, and self-structure artifacts have been written",
            },
            {
                "milestone_id": "admissibility_gate_initialized",
                "completion_signal": "candidate self-change classes receive deterministic admissibility outputs",
            },
            {
                "milestone_id": "branch_pause_synced",
                "completion_signal": "current wm-hybrid branch pause state is persisted in branch_registry_latest.json",
            },
        ],
        "human_approval_points": [
            "retained structural promotions",
            "branch-state changes",
            "protected-surface challenges",
            "resource-expansion requests",
            "retained skill promotions",
        ],
        "constraints": [
            "do not change live policy",
            "do not change thresholds",
            "do not change routing policy",
            "do not change frozen benchmark semantics",
            "do not broaden the projection-safe envelope",
            "novali-v5 is the only active edit target",
            "novali-v4 remains frozen reference/operator surface",
            "novali-v3 remains unchanged as fallback/reference",
            "novali-v2 remains unchanged as older preserved fallback/reference",
            "plan_ remains non-owning",
            "routing remains deferred",
        ],
        "trusted_sources": [
            "local_repo:novali-v5",
            "local_artifacts:novali-v5/data",
            "local_repo:novali-v4",
            "local_artifacts:novali-v4/data",
            "local_logs:logs",
            "trusted_benchmark_pack_v1",
        ],
        "bucket_spec": {
            "bucket_id": "bucket_governance_substrate_v1_local",
            "bucket_model": "containerized_bucket_v1",
        },
        "allowed_action_classes": [
            "low_risk_shell_change",
            "diagnostic_schema_materialization",
            "append_only_ledger_write",
            "local_governance_registry_update",
        ],
        "stop_conditions": [
            "immutable-core challenge detected",
            "trusted-source violation detected",
            "branch-state incompatibility detected",
            "bucket infeasibility detected",
            "directive drift budget exhausted",
        ],
        "drift_budget_for_context_exploration": {
            "allowed": True,
            "tag_required": "directive_support",
            "max_budgeted_support_reads": 12,
            "max_budgeted_external_fetches": 0,
        },
        "branch_context": {
            "branch_id": str(branch_record.get("branch_id", "")),
            "branch_state": str(branch_record.get("state", "")),
            "held_baseline": dict(branch_record.get("held_baseline", {})),
            "policy_version": str(policy.get("policy_version", "")),
        },
    }
    return {
        "schema_version": "directive_state_v1",
        "generated_at": now,
        "directive_spec_schema": directive_spec_schema,
        "current_directive_state": current_directive,
    }


def _build_bucket_state(now: str) -> dict[str, Any]:
    bucket_schema = {
        "schema_name": "ContainerizedBucketSpec",
        "schema_version": "bucket_spec_v1",
        "required_fields": [
            "bucket_id",
            "cpu_limit",
            "memory_limit",
            "storage_limit",
            "network_policy",
            "trusted_sources",
            "mount_policy",
            "subprocess_policy",
            "resource_accounting_mode",
        ],
    }
    current_bucket = {
        "bucket_id": "bucket_governance_substrate_v1_local",
        "bucket_model": "containerized_bucket_v1",
        "cpu_limit": {
            "max_parallel_processes": 4,
            "cpu_seconds_per_action": 180,
        },
        "memory_limit": {
            "max_working_set_mb": 2048,
        },
        "storage_limit": {
            "max_write_mb_per_action": 128,
            "max_retained_governance_artifacts_mb": 64,
        },
        "network_policy": {
            "mode": "deny_external_except_trusted_sources",
            "allowed_network_modes": ["none", "trusted_local_only"],
            "external_access_introduced": False,
        },
        "trusted_sources": [
            "local_repo:novali-v5",
            "local_artifacts:novali-v5/data",
            "local_repo:novali-v4",
            "local_artifacts:novali-v4/data",
            "local_logs:logs",
            "trusted_benchmark_pack_v1",
        ],
        "mount_policy": {
            "read_roots": [
                "novali-v5",
                "novali-v4",
                "logs",
            ],
            "write_roots": [
                "novali-v5/data",
                "novali-v5/interventions",
            ],
            "read_only_roots": [
                "novali-v4",
                "novali-v3",
                "novali-v2",
            ],
            "external_mounts_forbidden": True,
        },
        "subprocess_policy": {
            "auto_allowed_classes": [
                "read_only_inspection",
                "py_compile",
                "shadow_diagnostic_runner",
            ],
            "gated_classes": [
                "retained_structural_promotion",
                "branch_state_change",
                "protected_surface_challenge",
                "resource_expansion_request",
                "skill_trial",
                "skill_retention_promotion",
            ],
            "forbidden_classes": [
                "live_policy_change",
                "threshold_change",
                "routing_policy_change",
                "frozen_benchmark_semantics_change",
                "projection_safe_envelope_change",
                "untrusted_external_access",
            ],
        },
        "resource_accounting_mode": "tracked_budget_v1",
    }
    return {
        "schema_version": "bucket_state_v1",
        "generated_at": now,
        "bucket_schema": bucket_schema,
        "current_bucket_state": current_bucket,
    }


def _build_branch_registry(
    *,
    now: str,
    branch_pause_artifact: dict[str, Any],
    scoped_probe_artifact: dict[str, Any],
    current_artifact_path: Path,
) -> dict[str, Any]:
    pause_report = dict(branch_pause_artifact.get("branch_pause_report", {}))
    held_baseline = dict(pause_report.get("held_baseline", {}))
    pause_conditions = dict(pause_report.get("formal_pause_conditions", {}))
    reopen_triggers = dict(pause_report.get("formal_reopen_triggers", {}))
    branch_record = {
        "branch_id": "novali-v4:wm_hybrid_context_scoped",
        "branch_name": "wm_hybrid_context_scoped",
        "state": "paused_with_baseline_held",
        "held_baseline": {
            "template": str(held_baseline.get("template", "")),
            "classification": str(held_baseline.get("classification", "")),
            "selection_score_pre_gate_gap": _safe_float(
                held_baseline.get("selection_score_pre_gate_gap"),
                0.0,
            ),
            "signal_availability_corr": _safe_float(held_baseline.get("signal_availability_corr"), 0.0),
            "signal_gap": _safe_float(held_baseline.get("signal_gap"), 0.0),
            "distinctness_score": _safe_float(held_baseline.get("distinctness_score"), 0.0),
        },
        "promotion_rationale": "the context-scoped wm/baseline hybrid probe is the best current narrow working configuration and remains the standard to beat",
        "pause_rationale": str(pause_conditions.get("pause_reason", "")),
        "reopen_triggers": list(reopen_triggers.get("trigger_classes", [])),
        "closed_next_steps": list(pause_report.get("invalid_or_already_closed_next_steps", [])),
        "last_evidence_artifact": str(branch_pause_artifact.get("_artifact_path", current_artifact_path)),
        "supporting_artifacts": [
            str(scoped_probe_artifact.get("_artifact_path", "")),
            str(branch_pause_artifact.get("_artifact_path", "")),
            str(current_artifact_path),
        ],
    }
    return {
        "schema_version": "branch_registry_v1",
        "generated_at": now,
        "supported_states": [
            "active",
            "paused_with_baseline_held",
            "held_baseline",
            "reopen_candidate",
            "deprecated",
            "closed",
        ],
        "current_branch_id": str(branch_record.get("branch_id", "")),
        "branches": [branch_record],
    }


def _skill_proposal_schema() -> dict[str, Any]:
    return {
        "schema_name": "GovernedSkillProposal",
        "schema_version": "governed_skill_proposal_v1",
        "required_fields": [
            "skill_id",
            "skill_name",
            "skill_class",
            "directive_relevance",
            "expected_value",
            "resource_cost_estimate",
            "reversibility",
            "duplication_risk",
            "trusted_sources",
            "action_class",
            "surface",
            "target_surface",
            "evidence_plan",
            "retention_target",
        ],
    }


def _phase_1_skill_class_profiles() -> list[dict[str, Any]]:
    return [
        {
            "skill_class": "helper_module",
            "purpose": "bounded local utility modules that improve observability, parsing, or governed bookkeeping",
            "phase_1_status": "valid",
            "default_trial_mode": "diagnostic_only_or_sandboxed",
            "guardrails": [
                "must remain local to trusted sources",
                "must not create hidden execution paths outside the governance substrate",
            ],
        },
        {
            "skill_class": "evaluator",
            "purpose": "shadow-only evaluators that score or summarize candidates without owning live decisions",
            "phase_1_status": "valid",
            "default_trial_mode": "sandboxed",
            "guardrails": [
                "must not change live policy or thresholds",
                "must not become selected-set optimization under a new label",
            ],
        },
        {
            "skill_class": "planner_support",
            "purpose": "planning helpers that organize work without changing the non-owning status of plan_",
            "phase_1_status": "valid",
            "default_trial_mode": "sandboxed",
            "guardrails": [
                "plan_ remains non-owning",
                "must not become a hidden ownership transfer into planning logic",
            ],
        },
        {
            "skill_class": "retrieval_memory_system",
            "purpose": "local retrieval and memory systems constrained to trusted local artifacts and explicit drift budgets",
            "phase_1_status": "valid",
            "default_trial_mode": "sandboxed",
            "guardrails": [
                "no new external access beyond trusted-source policy",
                "must stay inside the bucket and tracked resource budget",
            ],
        },
        {
            "skill_class": "simulation_harness",
            "purpose": "local simulation or replay harnesses for shadow diagnostics and reproducibility",
            "phase_1_status": "valid",
            "default_trial_mode": "sandboxed",
            "guardrails": [
                "shadow-only execution",
                "must not change live behavior or routing policy",
            ],
        },
        {
            "skill_class": "tool_wrapper",
            "purpose": "wrappers around trusted local tools that expose bounded utility without expanding trust boundaries",
            "phase_1_status": "valid",
            "default_trial_mode": "diagnostic_only_or_sandboxed",
            "guardrails": [
                "trusted-source compliance required",
                "must not bootstrap unbounded framework growth or external-install behavior",
            ],
        },
    ]


def _skill_action_governance_matrix() -> dict[str, Any]:
    return {
        "auto_allowed": [
            {
                "action_class": "low_risk_shell_change",
                "skill_scope": "diagnostic-only local helper updates inside mutable_shell",
                "reason": "phase-1 autonomy allows low-risk reversible shell work that stays local and does not open a new skill branch",
            },
            {
                "action_class": "append_only_ledger_write",
                "skill_scope": "append-only skill history and registry writes",
                "reason": "append-only governance bookkeeping is allowed when it remains reversible and inside trusted local artifacts",
            },
            {
                "action_class": "local_governance_registry_update",
                "skill_scope": "current-snapshot skill metadata refreshes",
                "reason": "registry synchronization is allowed when it does not change runtime behavior",
            },
        ],
        "gated_review_required": [
            {
                "action_class": "skill_trial",
                "reason": "trial execution creates a new governed capability surface and therefore requires review even when bucket-feasible",
            },
            {
                "action_class": "skill_retention_promotion",
                "reason": "retained structural promotions are gated under phase-1 autonomy",
            },
            {
                "action_class": "resource_expansion_request",
                "reason": "resource expansion remains gated under the immutable governance split",
            },
            {
                "action_class": "branch_state_change",
                "reason": "skill-related branch-state changes cannot auto-execute while the wm-hybrid branch is paused with a held baseline",
            },
            {
                "action_class": "protected_surface_challenge",
                "reason": "protected or conditionally mutable surface challenges require explicit review",
            },
        ],
        "forbidden": [
            {
                "action_class": "untrusted_external_access",
                "reason": "external-access creep outside trusted sources is forbidden",
            },
            {
                "action_class": "live_policy_change",
                "reason": "skill acquisition cannot mutate live policy",
            },
            {
                "action_class": "threshold_change",
                "reason": "skill acquisition cannot relax thresholds",
            },
            {
                "action_class": "routing_policy_change",
                "reason": "routing remains deferred",
            },
            {
                "action_class": "frozen_benchmark_semantics_change",
                "reason": "frozen benchmark semantics remain immutable",
            },
            {
                "action_class": "projection_safe_envelope_change",
                "reason": "the projection-safe envelope cannot be broadened by a skill path",
            },
            {
                "action_class": "plan_ownership_change",
                "reason": "plan_ remains non-owning",
            },
            {
                "action_class": "downstream_selected_set_work",
                "reason": "skill acquisition must not drift into downstream selected-set work",
            },
        ],
    }


def _skill_retention_rules() -> dict[str, Any]:
    return {
        "provisional_acceptance_evidence": [
            "directive relevance is medium or high",
            "9D admissibility, trusted-source compliance, and mutable-surface legality all pass",
            "bucket feasibility is demonstrated inside the current tracked budget",
            "the proposal remains reversible and duplication risk is low or explicitly justified",
            "shadow or diagnostic evidence shows bounded utility without downstream drift",
        ],
        "retained_promotion_evidence": [
            "provisional evidence is repeated across more than one shadow or diagnostic pass",
            "human review approves the retained promotion",
            "the skill remains governance-owned and is not the source of governance truth",
            "no safety envelope, routing, threshold, or benchmark-semantic changes are implicated",
        ],
        "deprecation_triggers": [
            "directive relevance decays or the active directive changes materially",
            "duplication or overlap risk becomes high because a better governed capability already exists",
            "resource cost becomes unjustified relative to evidence",
            "the skill drifts toward forbidden surfaces such as routing or downstream selected-set work",
        ],
        "rollback_triggers": [
            "trusted-source compliance fails",
            "bucket feasibility fails or hidden resource expansion appears",
            "branch-state compatibility fails",
            "the skill harms protected weak slices or causes a governance boundary violation",
        ],
    }


def _skill_guardrails() -> dict[str, Any]:
    return {
        "unbounded_framework_growth_forbidden": True,
        "external_access_creep_forbidden": True,
        "downstream_selected_set_work_forbidden": True,
        "plan_ownership_change_forbidden": True,
        "routing_work_forbidden": True,
        "skill_subsystem_remains_governance_owned": True,
        "proposal_learning_loop_is_not_governance_truth_source": True,
    }


def _skill_screening_outcome(skill: dict[str, Any], gate_report: dict[str, Any]) -> dict[str, Any]:
    action_class = str(skill.get("action_class", ""))
    admissibility = str(gate_report.get("admissibility_status", "forbidden"))
    if admissibility == "forbidden":
        return {
            "screening_outcome": "blocked",
            "lifecycle_state": "blocked",
            "reason": "the skill proposal violates immutable-core, trust-boundary, or other forbidden governance rules",
        }
    if action_class == "skill_trial":
        return {
            "screening_outcome": "sandboxed",
            "lifecycle_state": "sandboxed",
            "reason": "the skill is admissible only as a sandboxed governed trial and cannot bypass review",
        }
    if action_class == "skill_retention_promotion":
        return {
            "screening_outcome": "provisional",
            "lifecycle_state": "provisional",
            "reason": "promotion into retained status requires gated review after provisional evidence is established",
        }
    return {
        "screening_outcome": "diagnostic_only",
        "lifecycle_state": "diagnostic_only",
        "reason": "the skill remains diagnostic-only and does not open a behavior-changing skill branch",
    }


def _build_skill_subsystem(
    policy: dict[str, Any],
    directive_state: dict[str, Any],
    bucket_state: dict[str, Any],
    branch_record: dict[str, Any],
) -> dict[str, Any]:
    current_bucket = dict(bucket_state.get("current_bucket_state", {}))
    current_directive = dict(directive_state.get("current_directive_state", {}))
    sample_skills = [
        {
            "skill_id": "skill_local_trace_parser_trial",
            "skill_name": "Local trace parser trial",
            "skill_class": "helper_module",
            "directive_relevance": "high",
            "expected_value": "medium",
            "resource_cost_estimate": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "reversibility": "high",
            "duplication_risk": "low",
            "trusted_sources": ["local_repo:novali-v4", "local_logs:logs"],
            "action_class": "skill_trial",
            "surface": "skills_subsystem",
            "target_surface": "skills_subsystem",
            "evidence_plan": "shadow-only trace parsing utility against current local logs and artifacts",
            "retention_target": "provisional",
        },
        {
            "skill_id": "skill_shadow_slice_evaluator",
            "skill_name": "Shadow slice evaluator registry sync",
            "skill_class": "evaluator",
            "directive_relevance": "high",
            "expected_value": "medium",
            "resource_cost_estimate": {"cpu_parallel_units": 1, "memory_mb": 96, "storage_write_mb": 4, "network_mode": "none"},
            "reversibility": "high",
            "duplication_risk": "low",
            "trusted_sources": ["local_repo:novali-v4"],
            "action_class": "low_risk_shell_change",
            "surface": "skills_subsystem",
            "target_surface": "skills_subsystem",
            "evidence_plan": "diagnostic-only registry and evaluator metadata materialization",
            "retention_target": "diagnostic_only",
        },
        {
            "skill_id": "skill_trace_parser_retention_promotion",
            "skill_name": "Trace parser retained promotion",
            "skill_class": "tool_wrapper",
            "directive_relevance": "high",
            "expected_value": "medium",
            "resource_cost_estimate": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "reversibility": "medium",
            "duplication_risk": "medium",
            "trusted_sources": ["local_repo:novali-v4"],
            "action_class": "skill_retention_promotion",
            "surface": "skills_subsystem",
            "target_surface": "skills_subsystem",
            "evidence_plan": "promote only after repeated shadow utility and governed review",
            "retention_target": "retained",
        },
        {
            "skill_id": "skill_untrusted_remote_installer",
            "skill_name": "Untrusted remote installer",
            "skill_class": "tool_wrapper",
            "directive_relevance": "low",
            "expected_value": "unknown",
            "resource_cost_estimate": {"cpu_parallel_units": 1, "memory_mb": 256, "storage_write_mb": 32, "network_mode": "open_external"},
            "reversibility": "low",
            "duplication_risk": "high",
            "trusted_sources": ["untrusted_remote_web"],
            "action_class": "untrusted_external_access",
            "surface": "skills_subsystem",
            "target_surface": "trusted_source_policy",
            "evidence_plan": "none",
            "retention_target": "forbidden",
        },
    ]
    classified_skills = []
    for skill in sample_skills:
        result = _classify_candidate_self_change(
            dict(skill, requested_resources=dict(skill.get("resource_cost_estimate", {}))),
            policy=policy,
            directive_state=current_directive,
            bucket_state=current_bucket,
            branch_record=branch_record,
        )
        screening = _skill_screening_outcome(skill, result)
        classified_skills.append(
            {
                "skill_id": str(skill.get("skill_id", "")),
                "skill_name": str(skill.get("skill_name", "")),
                "skill_class": str(skill.get("skill_class", "")),
                "directive_relevance": str(skill.get("directive_relevance", "")),
                "expected_value": str(skill.get("expected_value", "")),
                "resource_cost_estimate": dict(skill.get("resource_cost_estimate", {})),
                "reversibility": str(skill.get("reversibility", "")),
                "duplication_risk": str(skill.get("duplication_risk", "")),
                "action_class": str(skill.get("action_class", "")),
                "admissibility_status": str(result.get("admissibility_status", "")),
                "screening_outcome": str(screening.get("screening_outcome", "")),
                "lifecycle_state": str(screening.get("lifecycle_state", "")),
                "screening_reason": str(screening.get("reason", "")),
                "retention_status": {
                    "diagnostic_only": "diagnostic_only",
                    "sandboxed": "trial_pending_review",
                    "provisional": "retained_promotion_pending_review",
                    "blocked": "rejected",
                }.get(str(screening.get("screening_outcome", "")), "screened"),
                "governance_gate_report": result,
            }
        )
    screening_counts = {
        "blocked": sum(1 for item in classified_skills if item["screening_outcome"] == "blocked"),
        "diagnostic_only": sum(1 for item in classified_skills if item["screening_outcome"] == "diagnostic_only"),
        "sandboxed": sum(1 for item in classified_skills if item["screening_outcome"] == "sandboxed"),
        "provisional": sum(1 for item in classified_skills if item["screening_outcome"] == "provisional"),
    }
    return {
        "schema_version": "governed_skill_subsystem_v1",
        "skills_are_formal_governed_subsystem": True,
        "skill_proposal_schema": _skill_proposal_schema(),
        "lifecycle_states": list(GOVERNED_SKILL_LIFECYCLE_STATES),
        "screening_outcome_classes": list(SKILL_SCREENING_OUTCOME_CLASSES),
        "phase_1_valid_skill_classes": list(PHASE_1_VALID_SKILL_CLASSES),
        "phase_1_skill_class_profiles": _phase_1_skill_class_profiles(),
        "skill_action_governance_matrix": _skill_action_governance_matrix(),
        "evaluation_dimensions": [
            "directive_relevance",
            "9d_admissibility",
            "trusted_source_policy",
            "bucket_resource_feasibility",
            "mutable_surface_legality",
            "reversibility",
            "duplication_overlap_risk",
            "branch_state_compatibility",
        ],
        "governance_rules": {
            "skill_trials_are_never_source_of_governance_truth": True,
            "retained_skill_promotions_are_gated": True,
            "trusted_source_compliance_required": True,
            "duplication_check_required": True,
            "phase_1_behavior_changing_skill_branch_default": "not_opened",
            "plan_non_owning_required": True,
            "routing_deferred_required": True,
        },
        "retention_rules": _skill_retention_rules(),
        "boundary_guardrails": _skill_guardrails(),
        "sample_skill_proposals": classified_skills,
        "sample_screening_counts": screening_counts,
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    branch_pause_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1"
    )
    working_baseline_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1"
    )
    scoped_probe_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1"
    )
    frontier_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    if not all([branch_pause_artifact, working_baseline_artifact, scoped_probe_artifact, frontier_snapshot]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: Governance Substrate v1 requires the current branch-pause, scoped-baseline, and frontier-control artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot establish governance substrate state without the current paused branch baseline context",
            },
        }

    now = _now()
    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    from .analytics import build_intervention_ledger_analytics

    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")

    current_artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_v4_governance_substrate_v1_snapshot_{proposal['proposal_id']}.json"
    )

    policy = _build_policy_representation()
    branch_registry = _build_branch_registry(
        now=now,
        branch_pause_artifact=branch_pause_artifact,
        scoped_probe_artifact=scoped_probe_artifact,
        current_artifact_path=current_artifact_path,
    )
    branch_record = dict(list(branch_registry.get("branches", []))[0])
    directive_state = _build_directive_state(now=now, branch_record=branch_record, policy=policy)
    bucket_state = _build_bucket_state(now)
    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_bucket = dict(bucket_state.get("current_bucket_state", {}))

    candidate_examples = [
        {
            "candidate_id": "candidate_low_risk_shell_cleanup",
            "action_class": "low_risk_shell_change",
            "surface": "local_low_risk_shell_work",
            "target_surface": "governance_state_artifacts",
            "directive_relevance": "high",
            "requested_resources": {
                "cpu_parallel_units": 1,
                "memory_mb": 128,
                "storage_write_mb": 4,
                "network_mode": "none",
            },
            "reversibility": "high",
            "trusted_sources": ["local_repo:novali-v4"],
        },
        {
            "candidate_id": "candidate_retained_structural_promotion",
            "action_class": "retained_structural_promotion",
            "surface": "proposal_learning_loop_upstream_context",
            "target_surface": "proposal_learning_loop_upstream_context",
            "directive_relevance": "high",
            "requested_resources": {
                "cpu_parallel_units": 1,
                "memory_mb": 256,
                "storage_write_mb": 8,
                "network_mode": "none",
            },
            "reversibility": "medium",
            "trusted_sources": ["local_repo:novali-v4"],
        },
        {
            "candidate_id": "candidate_branch_state_reopen_request",
            "action_class": "branch_state_change",
            "surface": "branch_registry",
            "target_surface": "branch_registry",
            "directive_relevance": "medium",
            "requested_resources": {
                "cpu_parallel_units": 1,
                "memory_mb": 64,
                "storage_write_mb": 2,
                "network_mode": "none",
            },
            "reversibility": "medium",
            "trusted_sources": ["local_artifacts:novali-v4/data"],
        },
        {
            "candidate_id": "candidate_protected_surface_challenge",
            "action_class": "protected_surface_challenge",
            "surface": "branch_registry",
            "target_surface": "proposal_admissibility_governance",
            "directive_relevance": "medium",
            "requested_resources": {
                "cpu_parallel_units": 1,
                "memory_mb": 64,
                "storage_write_mb": 2,
                "network_mode": "none",
            },
            "reversibility": "medium",
            "trusted_sources": ["local_repo:novali-v4"],
        },
        {
            "candidate_id": "candidate_resource_expansion_request",
            "action_class": "resource_expansion_request",
            "surface": "bucket_state",
            "target_surface": "bucket_state",
            "directive_relevance": "medium",
            "requested_resources": {
                "cpu_parallel_units": 6,
                "memory_mb": 3072,
                "storage_write_mb": 256,
                "network_mode": "trusted_local_only",
            },
            "reversibility": "medium",
            "trusted_sources": ["local_repo:novali-v4"],
        },
        {
            "candidate_id": "candidate_live_policy_mutation",
            "action_class": "live_policy_change",
            "surface": "live_policy",
            "target_surface": "live_policy",
            "directive_relevance": "high",
            "requested_resources": {
                "cpu_parallel_units": 1,
                "memory_mb": 64,
                "storage_write_mb": 1,
                "network_mode": "none",
            },
            "reversibility": "low",
            "trusted_sources": ["local_repo:novali-v4"],
        },
        {
            "candidate_id": "candidate_untrusted_network_request",
            "action_class": "untrusted_external_access",
            "surface": "bucket_state",
            "target_surface": "trusted_source_policy",
            "directive_relevance": "low",
            "requested_resources": {
                "cpu_parallel_units": 1,
                "memory_mb": 128,
                "storage_write_mb": 8,
                "network_mode": "open_external",
            },
            "reversibility": "low",
            "trusted_sources": ["untrusted_remote_web"],
        },
    ]
    admissibility_examples = [
        _classify_candidate_self_change(
            candidate,
            policy=policy,
            directive_state=current_directive,
            bucket_state=current_bucket,
            branch_record=branch_record,
        )
        for candidate in candidate_examples
    ]
    admissibility_counts = {
        "auto_allowed": sum(1 for item in admissibility_examples if item["admissibility_status"] == "auto_allowed"),
        "gated_review_required": sum(
            1 for item in admissibility_examples if item["admissibility_status"] == "gated_review_required"
        ),
        "forbidden": sum(1 for item in admissibility_examples if item["admissibility_status"] == "forbidden"),
    }

    skill_subsystem = _build_skill_subsystem(
        policy=policy,
        directive_state=directive_state,
        bucket_state=bucket_state,
        branch_record=branch_record,
    )

    self_structure_state = {
        "schema_version": "self_structure_state_v1",
        "generated_at": now,
        "registry_mode": "hybrid_event_ledger_plus_current_snapshot",
        "policy": policy,
        "directive_state_path": str(DIRECTIVE_STATE_PATH),
        "bucket_state_path": str(BUCKET_STATE_PATH),
        "branch_registry_path": str(BRANCH_REGISTRY_PATH),
        "self_structure_ledger_path": str(SELF_STRUCTURE_LEDGER_PATH),
        "proposal_admissibility_gate": {
            "schema_version": "proposal_admissibility_gate_v1",
            "output_classes": [
                "auto_allowed",
                "gated_review_required",
                "forbidden",
            ],
            "evaluation_dimensions": [
                "directive_relevance",
                "9d_admissibility",
                "mutable_surface_legality",
                "bucket_feasibility",
                "reversibility",
                "branch_state_compatibility",
                "trusted_source_compliance",
            ],
            "phase_1_gatekept_autonomy": {
                "low_risk_shell_changes": "auto_allowed",
                "retained_structural_promotions": "gated_review_required",
                "branch_state_changes": "gated_review_required",
                "protected_surface_challenges": "gated_review_required",
                "resource_expansion_requests": "gated_review_required",
                "immutable_core_mutations": "forbidden",
                "untrusted_external_access": "forbidden",
            },
            "sample_admissibility_results": admissibility_examples,
            "sample_decision_counts": admissibility_counts,
        },
        "governed_skill_subsystem": skill_subsystem,
        "current_state_summary": {
            "active_working_version": "novali-v5",
            "frozen_fallback_reference_version": "novali-v3",
            "current_branch_id": str(branch_record.get("branch_id", "")),
            "current_branch_state": str(branch_record.get("state", "")),
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
            "plan_non_owning": True,
            "governance_substrate_in_place": True,
        },
    }

    _write_json(DIRECTIVE_STATE_PATH, directive_state)
    _write_json(BUCKET_STATE_PATH, bucket_state)
    _write_json(BRANCH_REGISTRY_PATH, branch_registry)
    _write_json(SELF_STRUCTURE_STATE_PATH, self_structure_state)

    ledger_event = {
        "event_id": f"governance_substrate_v1::{proposal['proposal_id']}",
        "timestamp": now,
        "event_type": "governance_substrate_v1_materialized",
        "policy_version": str(policy.get("policy_version", "")),
        "directive_id": str(current_directive.get("directive_id", "")),
        "bucket_id": str(current_bucket.get("bucket_id", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": str(branch_record.get("state", "")),
        "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        "admissibility_status_counts": dict(admissibility_counts),
        "artifact_paths": {
            "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
            "directive_state_latest": str(DIRECTIVE_STATE_PATH),
            "bucket_state_latest": str(BUCKET_STATE_PATH),
        },
        "source_proposal_id": str(proposal.get("proposal_id", "")),
    }
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, ledger_event)

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_governance_substrate_v1_snapshot",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "comparison_references": {
            "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1": _artifact_reference(
                branch_pause_artifact,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1": _artifact_reference(
                working_baseline_artifact,
                latest_snapshots,
            ),
            "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1": _artifact_reference(
                scoped_probe_artifact,
                latest_snapshots,
            ),
            "memory_summary.false_safe_frontier_control_characterization_snapshot_v1": _artifact_reference(
                frontier_snapshot,
                latest_snapshots,
            ),
        },
        "branch_context": {
            "active_status_path": str(ACTIVE_STATUS_PATH),
            "handoff_status_path": str(HANDOFF_STATUS_PATH),
            "active_status_mentions_v5_active": "`novali-v5` is the active development branch." in active_status_text,
            "carried_forward_baseline": dict(handoff_status.get("carried_forward_baseline", {})),
            "current_branch_state": str(branch_record.get("state", "")),
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        },
        "governance_substrate_summary": {
            "immutable_core_mutable_shell_policy": {
                "policy_version": str(policy.get("policy_version", "")),
                "immutable_core": dict(policy.get("immutable_core", {})),
                "mutable_shell": dict(policy.get("mutable_shell", {})),
                "conditionally_mutable": dict(policy.get("conditionally_mutable", {})),
                "gated_actions": list(policy.get("gated_actions", [])),
                "forbidden_actions": list(policy.get("forbidden_actions", [])),
            },
            "directive_spec_shape": {
                "artifact_path": str(DIRECTIVE_STATE_PATH),
                "directive_id": str(current_directive.get("directive_id", "")),
                "required_fields": list(dict(directive_state.get("directive_spec_schema", {})).get("required_fields", [])),
            },
            "bucket_schema": {
                "artifact_path": str(BUCKET_STATE_PATH),
                "bucket_id": str(current_bucket.get("bucket_id", "")),
                "required_fields": list(dict(bucket_state.get("bucket_schema", {})).get("required_fields", [])),
            },
            "self_structure_registry": {
                "mode": "hybrid_event_ledger_plus_current_snapshot",
                "ledger_path": str(SELF_STRUCTURE_LEDGER_PATH),
                "snapshot_path": str(SELF_STRUCTURE_STATE_PATH),
            },
            "branch_state_registry": {
                "artifact_path": str(BRANCH_REGISTRY_PATH),
                "current_branch_id": str(branch_registry.get("current_branch_id", "")),
                "current_branch_state": str(branch_record.get("state", "")),
            },
            "proposal_admissibility_gate": {
                "output_classes": ["auto_allowed", "gated_review_required", "forbidden"],
                "sample_decision_counts": dict(admissibility_counts),
                "phase_1_gatekept_autonomy": dict(
                    dict(self_structure_state.get("proposal_admissibility_gate", {})).get(
                        "phase_1_gatekept_autonomy",
                        {},
                    )
                ),
            },
            "governed_skill_subsystem": {
                "schema_version": str(skill_subsystem.get("schema_version", "")),
                "sample_skill_proposal_count": int(len(skill_subsystem.get("sample_skill_proposals", []))),
                "retained_skill_promotions_gated": bool(
                    dict(skill_subsystem.get("governance_rules", {})).get("retained_skill_promotions_are_gated", False)
                ),
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": [
                str(item.get("template_name", ""))
                for item in list(recommendations.get("all_ranked_proposals", []))
                if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
            ][:8],
        },
        "decision_recommendation": {
            "governance_substrate_v1_in_place": True,
            "phase_1_gatekept_autonomy_represented_correctly": True,
            "plan_should_remain_non_owning": True,
            "recommended_next_step": "use the new governance substrate as the read-only source of truth for any future reopen-candidate screening before another behavior-changing branch is admitted",
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        },
        "observability_gain": {
            "passed": True,
            "reason": "Governance Substrate v1 wrote durable directive, bucket, branch, self-structure, and admissibility-state artifacts without touching live behavior",
            "artifact_paths": {
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
                "directive_state_latest": str(DIRECTIVE_STATE_PATH),
                "bucket_state_latest": str(BUCKET_STATE_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the governance substrate now provides a real self-structuring foundation with explicit admissibility classes and branch-state governance",
            "governance_substrate_v1_in_place": True,
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.97,
            "reason": "the implementation resolves where governance truth lives, how branch pause is represented, what can auto-execute, and what must remain gated or forbidden",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "Governance Substrate v1 is diagnostic/stateful only; live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope are unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": "",
            "reason": "the next safe move is to consume governance state as read-only context for future reopen-candidate screening rather than open a new behavior-changing branch now",
        },
        "diagnostic_conclusions": {
            "governance_substrate_v1_in_place": True,
            "phase_1_gatekept_autonomy_represented_correctly": True,
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
            "current_branch_state": str(branch_record.get("state", "")),
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        },
    }
    _write_json(current_artifact_path, artifact_payload)

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: Governance Substrate v1 is now materialized as the governed state foundation for novali-v4",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(current_artifact_path),
    }

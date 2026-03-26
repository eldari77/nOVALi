from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DIRECTIVE_FILE_SCHEMA_NAME = "NOVALIDirectiveBootstrapFile"
DIRECTIVE_FILE_SCHEMA_VERSION = "novali_directive_bootstrap_file_v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str, *, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    return token or fallback


def _load_current_bootstrap_context(package_root: Path) -> dict[str, Any]:
    for directive_name in (
        "novali_v6_bootstrap_directive_v1.json",
        "novali_v5_bootstrap_directive_v1.json",
    ):
        directive_path = package_root / "directives" / directive_name
        if directive_path.exists():
            try:
                payload = json.loads(directive_path.read_text(encoding="utf-8"))
                bootstrap_context = dict(payload.get("bootstrap_context", {}))
                if bootstrap_context:
                    return bootstrap_context
            except (OSError, json.JSONDecodeError):
                pass
    return {
        "active_branch": "novali-v6",
        "completed_reference_branch": "novali-v5",
        "reference_operator_surface_branch": "novali-v5",
        "frozen_fallback_reference_version": "novali-v4",
        "additional_reference_versions": ["novali-v3", "novali-v2"],
        "older_reference_version": "novali-v2",
        "branch_name": "wm_hybrid_context_scoped",
        "branch_state": "paused_with_baseline_held",
        "current_operating_stance": "hold_and_consolidate",
        "held_baseline_template": "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
        "held_baseline": {
            "template": "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
        },
        "routing_status": "routing_deferred",
        "branch_transition_reason": (
            "novali-v5 is frozen as the reference/operator surface baseline while novali-v6 becomes the active "
            "development branch under the same held baseline and directive-first bootstrap model."
        ),
        "branch_transition_status": "novali_v5_frozen_reference_novali_v6_active",
        "branch_transition_timestamp": _now(),
        "branch_transition_id": "branch_transition::novali_v5_to_novali_v6::standalone_handoff",
        "governed_work_loop_status": "hold_position_closed_out_v1",
        "selector_frontier_read": "serial_budget_then_ordering",
        "plan_non_owning": True,
        "projection_safety_primary": True,
        "carried_forward_safe_trio_reference": {
            "baseline_name": "swap_C",
            "selected_ids": ["recovery_02", "recovery_03", "recovery_12"],
        },
    }


def build_standalone_directive_payload(
    *,
    package_root: str | Path,
    directive_id: str,
    directive_text: str,
    clarified_intent_summary: str,
    bucket_id: str | None = None,
    bucket_model: str = "containerized_bucket_v1",
    trusted_sources: list[str] | None = None,
    success_criteria: list[str] | None = None,
    milestone_model: list[dict[str, str]] | None = None,
    human_approval_points: list[str] | None = None,
    stop_conditions: list[str] | None = None,
) -> dict[str, Any]:
    package_root_path = Path(package_root).resolve()
    bootstrap_context = deepcopy(_load_current_bootstrap_context(package_root_path))
    directive_token = _slug(directive_id, fallback="novali_v6_standalone_directive")
    normalized_bucket_id = str(bucket_id or f"bucket_{directive_token}").strip() or f"bucket_{directive_token}"

    payload = {
        "schema_name": DIRECTIVE_FILE_SCHEMA_NAME,
        "schema_version": DIRECTIVE_FILE_SCHEMA_VERSION,
        "bootstrap_context": bootstrap_context,
        "directive_spec": {
            "directive_id": str(directive_id).strip(),
            "directive_text": str(directive_text).strip(),
            "clarified_intent_summary": str(clarified_intent_summary).strip(),
            "success_criteria": list(
                success_criteria
                or [
                    "directive-first bootstrap completes with canonical governance artifacts materialized",
                    "governed execution reads authority from persisted artifacts after bootstrap",
                    "operator runtime constraints remain frozen outside agent-owned self-structure",
                ]
            ),
            "milestone_model": list(
                milestone_model
                or [
                    {
                        "milestone_id": "directive_wrapper_ready",
                        "completion_signal": "the formal directive wrapper validates before activation",
                    },
                    {
                        "milestone_id": "canonical_bootstrap_ready",
                        "completion_signal": "canonical governance artifacts are loaded or materialized deterministically",
                    },
                    {
                        "milestone_id": "governed_execution_ready",
                        "completion_signal": "the canonical execution handoff becomes execution-ready after bootstrap",
                    },
                ]
            ),
            "human_approval_points": list(
                human_approval_points
                or [
                    "branch-state changes",
                    "protected-surface challenges",
                    "resource-expansion requests",
                ]
            ),
            "constraints": [
                "do not change routing logic",
                "do not change thresholds",
                "do not change live policy",
                "do not change frozen benchmark semantics",
                "do not modify nined_core.py",
                "routing remains deferred",
                "hold_and_consolidate posture remains in force",
            ],
            "trusted_sources": list(
                trusted_sources
                or [
                    "local_repo:novali-v5",
                    "local_artifacts:novali-v5/data",
                    "local_repo:novali-v4",
                    "local_artifacts:novali-v4/data",
                    "local_logs:logs",
                    "trusted_benchmark_pack_v1",
                ]
            ),
            "bucket_spec": {
                "bucket_id": normalized_bucket_id,
                "bucket_model": str(bucket_model).strip() or "containerized_bucket_v1",
            },
            "allowed_action_classes": [
                "low_risk_shell_change",
                "diagnostic_schema_materialization",
                "append_only_ledger_write",
                "local_governance_registry_update",
            ],
            "stop_conditions": list(
                stop_conditions
                or [
                    "directive validation fails",
                    "clarification remains unresolved",
                    "canonical governance artifacts are inconsistent",
                ]
            ),
            "drift_budget_for_context_exploration": {
                "allowed": True,
                "tag_required": "standalone_operator_support",
                "max_budgeted_support_reads": 4,
                "max_budgeted_external_fetches": 0,
            },
        },
    }
    return payload


def write_standalone_directive(
    *,
    output_path: str | Path,
    package_root: str | Path,
    directive_id: str,
    directive_text: str,
    clarified_intent_summary: str,
    bucket_id: str | None = None,
    bucket_model: str = "containerized_bucket_v1",
    trusted_sources: list[str] | None = None,
) -> Path:
    payload = build_standalone_directive_payload(
        package_root=package_root,
        directive_id=directive_id,
        directive_text=directive_text,
        clarified_intent_summary=clarified_intent_summary,
        bucket_id=bucket_id,
        bucket_model=bucket_model,
        trusted_sources=trusted_sources,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a formal NOVALIDirectiveBootstrapFile scaffold for the current standalone NOVALI operator path. "
            "This helper writes a formal directive wrapper; it does not replace DirectiveSpec bootstrap."
        )
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to the directive JSON file to write.",
    )
    parser.add_argument(
        "--directive-id",
        required=True,
        help="Stable directive identifier for the new formal directive.",
    )
    parser.add_argument(
        "--directive-text",
        required=True,
        help="Short operator-readable directive text.",
    )
    parser.add_argument(
        "--clarified-intent-summary",
        required=True,
        help="Clarified intent summary used before activation.",
    )
    parser.add_argument(
        "--bucket-id",
        default="",
        help="Optional bucket id override. Defaults to a slug derived from the directive id.",
    )
    parser.add_argument(
        "--bucket-model",
        default="containerized_bucket_v1",
        help="Bucket model to include in bucket_spec. Defaults to containerized_bucket_v1.",
    )
    parser.add_argument(
        "--trusted-source",
        action="append",
        default=[],
        help="Repeat to override the default trusted-source list.",
    )
    args = parser.parse_args()

    package_root = Path(__file__).resolve().parents[1]
    output = write_standalone_directive(
        output_path=args.output,
        package_root=package_root,
        directive_id=args.directive_id,
        directive_text=args.directive_text,
        clarified_intent_summary=args.clarified_intent_summary,
        bucket_id=str(args.bucket_id).strip() or None,
        bucket_model=args.bucket_model,
        trusted_sources=list(args.trusted_source) or None,
    )
    print(str(output))


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.autonomy import (  # noqa: E402
    _append_ledger,
    _nine_d_capability_maturity_scorecard,
    initialize_autonomy_state,
)


def _meaningful(operator_root: Path, scenario: str, *, strict: bool = False) -> None:
    _append_ledger(
        operator_root,
        "meaningful_work_evaluations",
        {
            "schema_name": "MeaningfulWorkEvaluation",
            "schema_version": "novali_autonomy_v1",
            "created_at": "2026-07-02T00:00:00Z",
            "meaningful_work_id": f"meaningful-{scenario}",
            "meaningful_delta": True,
            "directive_progress": 1.0,
            "capability_growth": 1.0,
            "total_score": 0.95,
            "capability_kind": "test_gap_detector_v1" if scenario == "missing_tests" else "next_action_selector_v1",
            "strict_usefulness_credited": strict,
            "strict_useful_capability_consumed": strict,
            "weak_areas": [] if strict else [scenario.replace("_", " ")],
        },
    )


def _promoted(operator_root: Path, capability_kind: str) -> None:
    _append_ledger(
        operator_root,
        "promotion_results",
        {
            "schema_name": "PromotionResult",
            "schema_version": "novali_autonomy_v1",
            "created_at": "2026-07-02T00:00:01Z",
            "promotion_result_id": f"promotion-{capability_kind}",
            "status": "promoted",
            "promotion_stage": "promoted",
            "capability_kind": capability_kind,
            "capability_gap_id": capability_kind,
            "auto_adopted": True,
            "canary_result": "passed",
        },
    )


def _consumed(operator_root: Path, capability_kind: str) -> None:
    _append_ledger(
        operator_root,
        "capability_consumption_events",
        {
            "schema_name": "CapabilityConsumptionEvent",
            "schema_version": "novali_autonomy_v1",
            "created_at": "2026-07-02T00:00:02Z",
            "capability_consumption_event_id": f"consume-{capability_kind}",
            "capability_kind": capability_kind,
            "consumed_capability_kinds": [capability_kind],
            "explicitly_consumed_capability_kinds": [capability_kind],
            "planner_hook_references": ["next_action_selector"],
            "baseline_action": "governed_start_next_invocation",
            "final_action": "post_ladder_synthesis",
            "decision_changed_by_capability": True,
            "recognized_runtime_hook_invocation": True,
        },
    )


def _operation(operator_root: Path, scenario: str, action: str, status: str = "completed") -> None:
    _append_ledger(
        operator_root,
        "operation_results",
        {
            "schema_name": "OperationResult",
            "schema_version": "novali_autonomy_v1",
            "created_at": "2026-07-02T00:00:03Z",
            "operation_result_id": f"opresult-{scenario}",
            "operation_id": f"op-{scenario}",
            "action": action,
            "status": status,
            "budget_decision": "continue",
        },
    )


def _run_scenario(name: str, *, strict_consumption: bool = False) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        operator_root = Path(tmp) / "operator"
        initialize_autonomy_state(operator_root)
        capability_kind = "next_action_selector_v1"
        if name == "missing_tests":
            capability_kind = "test_gap_detector_v1"
        elif name == "failed_command_recovery":
            capability_kind = "tool_failure_classifier_v1"
        elif name == "blocker_summary":
            capability_kind = "directive_progress_scorer_v1"
        _promoted(operator_root, capability_kind)
        _meaningful(operator_root, name, strict=strict_consumption)
        if strict_consumption:
            _consumed(operator_root, capability_kind)
        if name == "patch_plan_choice":
            _operation(operator_root, name, "post_ladder_synthesis")
        elif name == "verification_command_choice":
            _operation(operator_root, name, "novali_stack_status")
        elif name == "failed_command_recovery":
            _operation(operator_root, f"{name}-failed", "governed_start_next_invocation", "failed")
            _operation(operator_root, name, "adaptive_learning_synthesis")
        elif name == "blocker_summary":
            _operation(operator_root, name, "adaptive_learning_synthesis")
        elif name == "reused_promoted_capability":
            _operation(operator_root, name, "post_ladder_synthesis")
        scorecard = _nine_d_capability_maturity_scorecard(operator_root, persist=False)
        return {
            "scenario": name,
            "maturity_band": scorecard["maturity_band"],
            "criticality_score": scorecard["criticality_score"],
            "criticality_threshold_met": scorecard["criticality_threshold_met"],
            "strict_consumption_gate_passed": scorecard["strict_consumption_gate_passed"],
            "threshold_blockers": scorecard["threshold_blockers"],
        }


def main() -> int:
    scenarios = [
        ("missing_tests", False),
        ("patch_plan_choice", False),
        ("verification_command_choice", False),
        ("failed_command_recovery", False),
        ("blocker_summary", False),
        ("reused_promoted_capability", True),
    ]
    results = [_run_scenario(name, strict_consumption=strict) for name, strict in scenarios]
    failures = [
        row
        for row in results
        if row["criticality_threshold_met"] and not row["strict_consumption_gate_passed"]
    ]
    print(json.dumps({"results": results, "failure_count": len(failures)}, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

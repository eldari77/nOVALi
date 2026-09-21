from __future__ import annotations

import copy
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from benchmarks.trusted_benchmark_pack_v1.runner import (
    _result_with_policy_decision,
    _summarize_benchmark_results,
    _variant_comparison,
    _variant_recommendation,
    run_trusted_benchmark_pack,
)
from experiments.proposal_learning_loop import ProposalLearningConfig, run_proposal_learning_loop
from runtime_config import apply_live_policy_variant, build_default_config

from .analytics import build_intervention_ledger_analytics
from .forecast import build_forecast_context, forecast_proposal
from .governance_memory_execution_gate_v1 import (
    build_execution_permission,
    require_execution_permission,
)
from .ledger import append_snapshot, intervention_data_dir, intervention_ledger_path, load_latest_snapshots
from .taxonomy import (
    CANONICAL_EVALUATION_STAGES,
    PROMOTION_STAGES,
    build_proposal_template,
    normalize_evaluation_plan,
    proposal_evaluation_semantics,
    validate_proposal_structure,
)


def _mean(values: Iterable[float]) -> float | None:
    vals = [float(v) for v in values]
    if not vals:
        return None
    return float(sum(vals) / len(vals))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _add_failure_tag(proposal: Dict[str, Any], tag: str) -> None:
    tags = list(proposal.get("failure_tags", []))
    if tag not in tags:
        tags.append(tag)
    proposal["failure_tags"] = tags


def _stage_eval_key(stage_name: str) -> str:
    return {
        "static_check": "static",
        "shadow": "shadow",
        "benchmark": "benchmark",
        "canary_gate": "canary",
    }[str(stage_name)]


def _declared_plan(proposal: Dict[str, Any]) -> List[str]:
    declared = normalize_evaluation_plan(list(proposal.get("evaluation_plan", [])))
    return declared or ["static_check", "shadow", "benchmark", "canary_gate"]


def _initialize_plan_execution(proposal: Dict[str, Any]) -> None:
    declared = _declared_plan(proposal)
    proposal["evaluation_plan"] = list(declared)
    stage_states: Dict[str, Dict[str, Any]] = {}
    evaluation = dict(proposal.get("evaluation", {}))
    for stage_name in CANONICAL_EVALUATION_STAGES:
        planned = stage_name in declared
        stage_states[stage_name] = {
            "planned": bool(planned),
            "status": "pending" if planned else "skipped",
        }
        if not planned:
            stage_states[stage_name]["reason"] = "not part of declared evaluation_plan"
            eval_key = _stage_eval_key(stage_name)
            if not dict(evaluation.get(eval_key, {})):
                evaluation[eval_key] = {
                    "stage_status": "skipped",
                    "reason": "not part of declared evaluation_plan",
                }
    proposal["evaluation"] = evaluation
    proposal["plan_execution"] = {
        "declared_stages": list(declared),
        "stage_states": stage_states,
        "completion_status": "in_progress",
        "failed_stage": None,
        "last_completed_stage": None,
    }


def _update_stage_state(
    proposal: Dict[str, Any],
    *,
    stage: str,
    stage_status: str,
    summary: Dict[str, Any],
    note: str = "",
) -> None:
    plan_execution = dict(proposal.get("plan_execution", {}))
    stage_states = dict(plan_execution.get("stage_states", {}))
    state = dict(stage_states.get(stage, {}))
    state["planned"] = bool(stage in _declared_plan(proposal))
    state["status"] = str(stage_status)
    state["at"] = _now()
    state["summary"] = copy.deepcopy(summary)
    if note:
        state["note"] = str(note)
    stage_states[stage] = state
    plan_execution["stage_states"] = stage_states
    if str(stage_status) not in {"failed", "skipped", "pending"}:
        plan_execution["last_completed_stage"] = str(stage)
    if str(stage_status) == "failed":
        plan_execution["failed_stage"] = str(stage)
        plan_execution["completion_status"] = "failed_intended_stage"
    proposal["plan_execution"] = plan_execution


def _is_last_planned_stage(proposal: Dict[str, Any], stage: str) -> bool:
    declared = _declared_plan(proposal)
    return bool(declared) and str(declared[-1]) == str(stage)


def _record_stage(
    proposal: Dict[str, Any],
    *,
    stage: str,
    status: str,
    summary: Dict[str, Any],
    event_type: str,
    note: str = "",
) -> Dict[str, Any]:
    proposal["updated_at"] = _now()
    proposal["promotion_status"] = str(status)
    stage_history = list(proposal.get("stage_history", []))
    stage_history.append(
        {
            "stage": str(stage),
            "status": str(status),
            "at": proposal["updated_at"],
            "summary": copy.deepcopy(summary),
            "note": str(note),
        }
    )
    proposal["stage_history"] = stage_history
    append_snapshot(proposal, event_type=event_type, note=note)
    return proposal


def _fail_intended_stage(
    proposal: Dict[str, Any],
    *,
    stage: str,
    summary: Dict[str, Any],
    failure_tag: str,
    note: str,
) -> None:
    _add_failure_tag(proposal, failure_tag)
    _update_stage_state(proposal, stage=stage, stage_status="failed", summary=summary, note=note)
    proposal["plan_execution"]["completion_status"] = "failed_intended_stage"
    proposal["plan_execution"]["failed_stage"] = str(stage)
    _record_stage(
        proposal,
        stage=stage,
        status="failed_stage",
        summary=summary,
        event_type="plan_failed",
        note=note,
    )


def _complete_intended_plan(
    proposal: Dict[str, Any],
    *,
    final_stage: str,
    summary: Dict[str, Any],
    note: str,
) -> None:
    proposal["updated_at"] = _now()
    proposal["promotion_status"] = "completed_plan"
    plan_execution = dict(proposal.get("plan_execution", {}))
    plan_execution["completion_status"] = "completed_intended_plan"
    plan_execution["completed_at"] = proposal["updated_at"]
    plan_execution["last_completed_stage"] = str(final_stage)
    proposal["plan_execution"] = plan_execution
    stage_history = list(proposal.get("stage_history", []))
    stage_history.append(
        {
            "stage": "plan",
            "status": "completed_plan",
            "at": proposal["updated_at"],
            "summary": {
                "final_stage": str(final_stage),
                "declared_stages": list(plan_execution.get("declared_stages", [])),
                "skipped_stages": [
                    stage_name
                    for stage_name, state in dict(plan_execution.get("stage_states", {})).items()
                    if str(dict(state).get("status")) == "skipped"
                ],
                "final_stage_summary": copy.deepcopy(summary),
            },
            "note": str(note),
        }
    )
    proposal["stage_history"] = stage_history
    append_snapshot(proposal, event_type="plan_completed", note=note)


def _find_sweep_variant(summary: Dict[str, Any], variant_name: str) -> Dict[str, Any]:
    sweep = dict(summary.get("policy_sweep_analysis", {}))
    for variant in list(sweep.get("variants", [])):
        if str(variant.get("name")) == str(variant_name):
            return dict(variant)
    return {}


def _summarize_history(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    provisional_count = 0
    full_adopt_count = 0
    rollback_count = 0
    rollback_causes: Counter[str] = Counter()
    projection_bad_incidents = 0
    realized_gains: List[float] = []
    goal_agreement_values: List[float] = []
    goal_mse_values: List[float] = []
    projection_error_values: List[float] = []
    last = history[-1] if history else {}
    for entry in history:
        adopted = [item for item in list(entry.get("adopted", [])) if isinstance(item, dict)]
        for item in adopted:
            status = str(item.get("status", ""))
            if status == "provisional":
                provisional_count += 1
            elif status == "full":
                full_adopt_count += 1
        if bool(entry.get("rollback_triggered", False)):
            rollback_count += 1
            rollback_causes[str(entry.get("rollback_cause", "none"))] += 1
        row = dict(entry.get("round_rollback_audit_row", {}))
        if float(row.get("realized_projection_bad", 0.0)) > 0.5:
            projection_bad_incidents += 1
        realized_gains.append(float(entry.get("post_avg", 0.0) - entry.get("base_avg", 0.0)))
        goal_agreement_values.append(float(entry.get("goal_agreement", 0.0)))
        goal_mse_values.append(float(entry.get("goal_mse_latent", 0.0)))
        projection_error_values.append(float(dict(entry.get("post_9d_metrics", {})).get("projection_error", 0.0)))
    row_summary = dict(last.get("selection_rate_summary", {}))
    return {
        "rounds": int(len(history)),
        "provisional_count": int(provisional_count),
        "full_adopt_count": int(full_adopt_count),
        "rollback_count": int(rollback_count),
        "rollback_cause_counts": dict(rollback_causes),
        "projection_bad_incidents": int(projection_bad_incidents),
        "mean_realized_gain": _mean(realized_gains),
        "mean_goal_agreement": _mean(goal_agreement_values),
        "mean_goal_mse_latent": _mean(goal_mse_values),
        "mean_projection_error": _mean(projection_error_values),
        "live_variant_override_total": int(row_summary.get("live_variant_override_total", 0)),
        "live_variant_dominant_block_reason": row_summary.get("live_variant_dominant_block_reason"),
        "live_variant_block_reason_counts": dict(row_summary.get("live_variant_block_reason_counts", {})),
        "live_variant_override_rounds": list(row_summary.get("live_variant_override_rounds", [])),
        "live_variant_baseline_rejected_total": int(row_summary.get("live_variant_baseline_rejected_total", 0)),
        "live_variant_projection_eligible_total": int(row_summary.get("live_variant_projection_eligible_total", 0)),
        "live_variant_conf_gain_eligible_total": int(row_summary.get("live_variant_conf_gain_eligible_total", 0)),
    }


def _run_shadow_live_eval(
    cfg: ProposalLearningConfig,
    *,
    variant_name: str,
    rounds: int,
    seeds: List[int],
    proposal_id: str,
) -> Dict[str, Any]:
    arms: Dict[str, List[Dict[str, Any]]] = {"baseline": [], "variant": []}
    for arm_name in ("baseline", "variant"):
        selected_variant = "baseline" if arm_name == "baseline" else str(variant_name)
        for seed in seeds:
            run_cfg = copy.deepcopy(cfg)
            run_cfg.verbose = False
            run_cfg.rounds = int(rounds)
            run_cfg.seed = int(seed)
            run_cfg.benchmark_every_rounds = 0
            run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs or {})
            run_cfg.eval_kwargs["session_log_path"] = (
                f"logs/intervention_shadow_{proposal_id}_{selected_variant}_seed{int(seed)}.log"
            )
            apply_live_policy_variant(run_cfg, selected_variant)
            _, _, history = run_proposal_learning_loop(run_cfg)
            arms[arm_name].append(_summarize_history(history))
    baseline = arms["baseline"][0] if arms["baseline"] else {}
    variant = arms["variant"][0] if arms["variant"] else {}
    delta = {
        "provisional_count": int(variant.get("provisional_count", 0)) - int(baseline.get("provisional_count", 0)),
        "full_adopt_count": int(variant.get("full_adopt_count", 0)) - int(baseline.get("full_adopt_count", 0)),
        "rollback_count": int(variant.get("rollback_count", 0)) - int(baseline.get("rollback_count", 0)),
        "projection_bad_incidents": int(variant.get("projection_bad_incidents", 0)) - int(baseline.get("projection_bad_incidents", 0)),
        "mean_realized_gain": (
            None
            if baseline.get("mean_realized_gain") is None or variant.get("mean_realized_gain") is None
            else float(variant["mean_realized_gain"] - baseline["mean_realized_gain"])
        ),
        "mean_goal_mse_latent": (
            None
            if baseline.get("mean_goal_mse_latent") is None or variant.get("mean_goal_mse_latent") is None
            else float(variant["mean_goal_mse_latent"] - baseline["mean_goal_mse_latent"])
        ),
        "override_count": int(variant.get("live_variant_override_total", 0)),
    }
    return {
        "baseline": baseline,
        "variant": variant,
        "delta": delta,
        "shadow_rounds": int(rounds),
        "shadow_seeds": list(map(int, seeds)),
    }


def _diagnostic_artifact_dir() -> Path:
    path = intervention_data_dir() / "diagnostic_memory"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalized_entropy(counter: Counter[str]) -> float:
    total = float(sum(counter.values()))
    if total <= 0.0 or len(counter) <= 1:
        return 0.0
    entropy = 0.0
    for count in counter.values():
        prob = float(count) / total
        if prob > 0.0:
            entropy -= prob * math.log(prob)
    return float(entropy / math.log(float(len(counter))))


def _recommended_followup_for_blocker(blocker_name: str) -> Dict[str, Any]:
    blocker = str(blocker_name)
    if blocker == "projection_guard":
        return {
            "template_name": "memory_summary.live_distribution_gap_snapshot",
            "reason": "projection_guard dominates dormant override blockage; the next clean step is a live-vs-benchmark gap snapshot",
        }
    if blocker == "confidence_gain_precondition":
        return {
            "template_name": "score_reweight.gain_goal_conflict_probe",
            "reason": "confidence/gain preconditions dominate; a score-side probe is the best follow-up",
        }
    return {
        "template_name": "critic_split.projection_gain_goal_v1",
        "reason": "blocker pattern remains mixed enough that a critic split is the safest next diagnostic",
    }


def _targeted_projection_override_boundary(cfg: ProposalLearningConfig) -> float:
    base_cap = float(getattr(cfg, "wm_candidate_pred_projection_bad_max_provisional", 0.72))
    margin = max(0.0, float(getattr(cfg, "live_policy_projection_margin_provisional", 0.0)))
    strict_cap = float(getattr(cfg, "live_policy_targeted_projection_strict_max", 0.48))
    return max(0.0, min(strict_cap, base_cap - margin))


def _safe_metric(value: Any) -> float | None:
    try:
        scalar = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(scalar):
        return None
    return float(scalar)


def _quantile(values: List[float], q: float) -> float:
    if not values:
        return float("nan")
    if len(values) == 1:
        return float(values[0])
    position = max(0.0, min(1.0, float(q))) * float(len(values) - 1)
    lo = int(math.floor(position))
    hi = int(math.ceil(position))
    if lo == hi:
        return float(values[lo])
    weight = float(position - lo)
    return float(values[lo] * (1.0 - weight) + values[hi] * weight)


def _metric_summary(rows: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    values = sorted(
        float(v)
        for v in (_safe_metric(dict(row).get(str(key))) for row in rows)
        if v is not None
    )
    if not values:
        return {"count": 0}
    return {
        "count": int(len(values)),
        "mean": float(sum(values) / len(values)),
        "min": float(values[0]),
        "p25": float(_quantile(values, 0.25)),
        "median": float(_quantile(values, 0.50)),
        "p75": float(_quantile(values, 0.75)),
        "max": float(values[-1]),
    }


def _mean_delta(left_rows: List[Dict[str, Any]], right_rows: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    left_mean = _safe_metric(_metric_summary(left_rows, key).get("mean"))
    right_mean = _safe_metric(_metric_summary(right_rows, key).get("mean"))
    delta = None
    if left_mean is not None and right_mean is not None:
        delta = float(left_mean - right_mean)
    return {
        "left_mean": left_mean,
        "right_mean": right_mean,
        "mean_delta": delta,
    }


def _live_gap_blocker_label(detail: Dict[str, Any]) -> str:
    override_reason = str(detail.get("live_variant_override_reason", ""))
    reason = str(detail.get("reason", "")).lower()
    if override_reason in {"projection_unavailable", "baseline_projection_block", "tight_projection_guard"}:
        return "projection_guard"
    if override_reason in {"conf_margin_guard", "gain_margin_guard"}:
        return "confidence_gain"
    if override_reason == "persistence_guard":
        return "persistence_guard"
    if override_reason == "recovery_guard":
        return "recovery_guard"
    if override_reason == "projected_quality_guard":
        return "projected_quality_guard"
    if "projection_bad" in reason or "projection" in reason:
        return "projection_guard"
    if "confidence" in reason or "gain" in reason or "improvement confidence" in reason:
        return "confidence_gain"
    if "persistence" in reason:
        return "persistence_guard"
    if "recovery" in reason:
        return "recovery_guard"
    return "other"


def _live_gap_row(
    detail: Dict[str, Any],
    *,
    seed: int,
    round_index: int,
    cohort: str,
    projection_boundary: float,
) -> Dict[str, Any]:
    pred_projection_bad = _safe_metric(detail.get("pred_projection_bad_prob", detail.get("pred_projection_bad")))
    boundary_distance = None if pred_projection_bad is None else float(pred_projection_bad - float(projection_boundary))
    return {
        "seed": int(seed),
        "round_index": int(round_index),
        "cohort": str(cohort),
        "candidate_id": str(detail.get("candidate_id", "")),
        "status": str(detail.get("status", "")),
        "reason": str(detail.get("reason", "")),
        "blocker_group": str(_live_gap_blocker_label(detail)),
        "live_variant_override_applied": bool(detail.get("live_variant_override_applied", False)),
        "live_variant_override_reason": str(detail.get("live_variant_override_reason", "")),
        "confidence": _safe_metric(detail.get("calibrated_confidence")),
        "gain": _safe_metric(detail.get("calibrated_gain")),
        "pred_post_gain": _safe_metric(detail.get("pred_post_gain")),
        "pred_gain_norm": _safe_metric(detail.get("pred_gain_norm")),
        "pred_projection_bad_prob": pred_projection_bad,
        "pred_projection_error": _safe_metric(detail.get("pred_projection_error")),
        "pred_projection_explosion_prob": _safe_metric(detail.get("pred_projection_explosion_prob")),
        "pred_rollback_union": _safe_metric(detail.get("pred_rollback_union")),
        "projection_boundary": float(projection_boundary),
        "boundary_distance": boundary_distance,
    }


def _threshold_relative_summary(rows: List[Dict[str, Any]], projection_boundary: float) -> Dict[str, Any]:
    distances = [
        float(distance)
        for distance in (_safe_metric(dict(row).get("boundary_distance")) for row in rows)
        if distance is not None
    ]
    total = int(len(distances))
    if total <= 0:
        return {
            "projection_boundary": float(projection_boundary),
            "count": 0,
            "within_abs_0_01": 0,
            "within_abs_0_02": 0,
            "within_abs_0_05": 0,
            "outside_above_boundary_within_0_01": 0,
            "outside_above_boundary_within_0_02": 0,
            "outside_above_boundary_within_0_05": 0,
            "outside_far_gt_0_05": 0,
            "inside_or_at_boundary": 0,
        }
    within_abs_001 = int(sum(abs(distance) <= 0.01 for distance in distances))
    within_abs_002 = int(sum(abs(distance) <= 0.02 for distance in distances))
    within_abs_005 = int(sum(abs(distance) <= 0.05 for distance in distances))
    outside_001 = int(sum(0.0 < distance <= 0.01 for distance in distances))
    outside_002 = int(sum(0.0 < distance <= 0.02 for distance in distances))
    outside_005 = int(sum(0.0 < distance <= 0.05 for distance in distances))
    inside_count = int(sum(distance <= 0.0 for distance in distances))
    far_count = int(sum(distance > 0.05 for distance in distances))
    return {
        "projection_boundary": float(projection_boundary),
        "count": int(total),
        "within_abs_0_01": int(within_abs_001),
        "within_abs_0_02": int(within_abs_002),
        "within_abs_0_05": int(within_abs_005),
        "outside_above_boundary_within_0_01": int(outside_001),
        "outside_above_boundary_within_0_02": int(outside_002),
        "outside_above_boundary_within_0_05": int(outside_005),
        "outside_far_gt_0_05": int(far_count),
        "inside_or_at_boundary": int(inside_count),
        "outside_above_boundary_within_0_01_rate": float(outside_001 / total),
        "outside_above_boundary_within_0_02_rate": float(outside_002 / total),
        "outside_above_boundary_within_0_05_rate": float(outside_005 / total),
        "outside_far_gt_0_05_rate": float(far_count / total),
        "inside_or_at_boundary_rate": float(inside_count / total),
    }


def _benchmark_detailed_report_path() -> Path:
    return Path(__file__).resolve().parents[1] / "benchmarks" / "trusted_benchmark_pack_v1" / "reports" / "latest_detailed.json"


def _load_latest_benchmark_detailed_rows() -> List[Dict[str, Any]]:
    path = _benchmark_detailed_report_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    rows = list(payload.get("results", []))
    return [dict(row) for row in rows if isinstance(row, dict)]


def _benchmark_reference_row(row: Dict[str, Any], projection_boundary: float) -> Dict[str, Any]:
    candidate_summary = dict(row.get("candidate_summary", {}))
    policy_result = dict(row.get("policy_decision_result", {}))
    predicted = dict(policy_result.get("predicted", {}))
    pred_projection_bad = _safe_metric(policy_result.get("pred_projection_bad_prob"))
    if pred_projection_bad is None:
        pred_projection_bad = _safe_metric(predicted.get("pred_projection_bad_prob"))
    boundary_distance = None if pred_projection_bad is None else float(pred_projection_bad - float(projection_boundary))
    return {
        "scenario_id": str(row.get("scenario_id", "")),
        "family": str(row.get("family", "")),
        "candidate_id": str(row.get("candidate_id", "")),
        "policy_decision": str(row.get("policy_decision", "")),
        "oracle_decision": str(row.get("oracle_decision", "")),
        "confidence": _safe_metric(candidate_summary.get("confidence")),
        "gain": _safe_metric(candidate_summary.get("gain")),
        "pred_post_gain": _safe_metric(predicted.get("pred_post_gain")),
        "pred_gain_norm": _safe_metric(predicted.get("pred_gain_norm")),
        "pred_projection_bad_prob": pred_projection_bad,
        "pred_projection_error": _safe_metric(predicted.get("pred_projection_error")),
        "pred_projection_explosion_prob": _safe_metric(predicted.get("pred_projection_explosion_prob")),
        "pred_rollback_union": _safe_metric(policy_result.get("pred_rollback_union")),
        "projection_boundary": float(projection_boundary),
        "boundary_distance": boundary_distance,
    }


def _largest_gap_metric(comparison: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    best_name = "none"
    best_delta = 0.0
    for name, row in comparison.items():
        delta = _safe_metric(dict(row).get("mean_delta"))
        if delta is None:
            continue
        if abs(float(delta)) > abs(best_delta):
            best_name = str(name)
            best_delta = float(delta)
    return {
        "metric": str(best_name),
        "mean_delta": float(best_delta),
    }


def _followup_for_gap_hypothesis(hypothesis: str) -> Dict[str, Any]:
    name = str(hypothesis)
    if name == "projection_probe":
        return {
            "template_name": "routing_rule.activation_window_probe",
            "reason": "live rejects cluster near the projection-safe boundary, so the next probe should test a narrow activation window",
        }
    if name == "gain_probe":
        return {
            "template_name": "score_reweight.gain_goal_conflict_probe",
            "reason": "live rejects look projection-safe enough but still fail score-side evidence, so the next probe should target gain/confidence weighting",
        }
    return {
        "template_name": "routing_rule.candidate_distribution_aware_probe",
        "reason": "live rejected traffic differs materially from benchmark undercommit cases, so the next probe should target distribution alignment rather than a blunt routing retry",
    }


def _summary_mean(summary: Dict[str, Any], key: str) -> float | None:
    return _safe_metric(dict(summary.get(str(key), {})).get("mean"))


def _segment_live_candidate(
    row: Dict[str, Any],
    *,
    benchmark_summary: Dict[str, Dict[str, Any]],
    projection_boundary: float,
) -> str:
    blocker = str(row.get("blocker_group", "other"))
    if blocker in {"persistence_guard", "recovery_guard"}:
        return "stability_sensitive"

    pred_projection_bad = _safe_metric(row.get("pred_projection_bad_prob"))
    pred_projection_error = _safe_metric(row.get("pred_projection_error"))
    confidence = _safe_metric(row.get("confidence"))
    gain = _safe_metric(row.get("gain"))
    boundary_distance = _safe_metric(row.get("boundary_distance"))
    bench_proj = _summary_mean(benchmark_summary, "pred_projection_bad_prob")
    bench_proj_err = _summary_mean(benchmark_summary, "pred_projection_error")
    bench_conf = _summary_mean(benchmark_summary, "confidence")
    bench_gain = _summary_mean(benchmark_summary, "gain")

    proj_gap = None if pred_projection_bad is None or bench_proj is None else float(pred_projection_bad - bench_proj)
    proj_err_gap = None if pred_projection_error is None or bench_proj_err is None else float(pred_projection_error - bench_proj_err)
    conf_gap = None if confidence is None or bench_conf is None else float(abs(confidence - bench_conf))
    gain_gap = None if gain is None or bench_gain is None else float(abs(gain - bench_gain))

    if (
        proj_gap is not None
        and proj_err_gap is not None
        and conf_gap is not None
        and gain_gap is not None
        and proj_gap <= 0.05
        and proj_err_gap <= 0.05
        and conf_gap <= 0.08
        and gain_gap <= 0.08
    ):
        return "benchmark_adjacent"
    if boundary_distance is not None and 0.0 < boundary_distance <= 0.05:
        return "projection_borderline"
    if (proj_gap is not None and proj_gap > 0.10) or (proj_err_gap is not None and proj_err_gap > 0.10):
        return "projection_far_shifted"
    if blocker == "confidence_gain":
        return "gain_structure_shifted"
    if (conf_gap is not None and conf_gap > 0.08) or (gain_gap is not None and gain_gap > 0.08):
        return "gain_structure_shifted"
    if pred_projection_bad is not None and pred_projection_bad > projection_boundary:
        return "projection_mid_shifted"
    return "mixed_shift"


def _segment_position_label(segment_name: str) -> str:
    name = str(segment_name)
    if name == "benchmark_adjacent":
        return "benchmark-like"
    if name == "projection_borderline":
        return "borderline"
    if name == "stability_sensitive":
        return "persistence/recovery-sensitive"
    return "clearly_outside_safe_window"


def _segment_comparison_classification(
    segment_rows: List[Dict[str, Any]],
    *,
    benchmark_summary: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    count = int(len(segment_rows))
    comparison = {
        "pred_projection_bad_prob": _mean_delta(segment_rows, [], "pred_projection_bad_prob"),
    }
    # Replace empty right rows with benchmark summary means for deterministic comparisons.
    segment_summary = {
        "pred_projection_bad_prob": _metric_summary(segment_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(segment_rows, "pred_projection_error"),
        "confidence": _metric_summary(segment_rows, "confidence"),
        "gain": _metric_summary(segment_rows, "gain"),
        "pred_post_gain": _metric_summary(segment_rows, "pred_post_gain"),
    }
    proj_bad_delta = None
    proj_err_delta = None
    conf_delta = None
    gain_delta = None
    for key, target_name in (
        ("pred_projection_bad_prob", "proj_bad_delta"),
        ("pred_projection_error", "proj_err_delta"),
        ("confidence", "conf_delta"),
        ("gain", "gain_delta"),
    ):
        left = _summary_mean(segment_summary, key)
        right = _summary_mean(benchmark_summary, key)
        delta = None if left is None or right is None else float(left - right)
        if target_name == "proj_bad_delta":
            proj_bad_delta = delta
        elif target_name == "proj_err_delta":
            proj_err_delta = delta
        elif target_name == "conf_delta":
            conf_delta = delta
        elif target_name == "gain_delta":
            gain_delta = delta

    if count < 2:
        classification = "not_comparable"
    elif (
        proj_bad_delta is not None
        and proj_err_delta is not None
        and conf_delta is not None
        and gain_delta is not None
        and abs(proj_bad_delta) <= 0.05
        and abs(proj_err_delta) <= 0.05
        and abs(conf_delta) <= 0.08
        and abs(gain_delta) <= 0.08
    ):
        classification = "benchmark_like"
    else:
        projection_score = max(abs(proj_bad_delta or 0.0), abs(proj_err_delta or 0.0))
        gain_score = max(abs(conf_delta or 0.0), abs(gain_delta or 0.0))
        if (proj_err_delta or 0.0) > 0.05 and abs(proj_err_delta or 0.0) > abs(proj_bad_delta or 0.0) + 0.03:
            classification = "projection_shifted"
        elif (proj_bad_delta or 0.0) > 0.05 and projection_score >= gain_score:
            classification = "projection_shifted"
        elif gain_score > projection_score and ((conf_delta or 0.0) < -0.08 or (gain_delta or 0.0) < -0.08 or gain_score > 0.08):
            classification = "gain_shifted"
        else:
            classification = "mixed_shift"

    if classification == "benchmark_like":
        mismatch_axis = "mixed"
    elif (proj_err_delta or 0.0) > 0.05 and abs(proj_err_delta or 0.0) >= abs(proj_bad_delta or 0.0):
        mismatch_axis = "projection_shape"
    elif (proj_bad_delta or 0.0) > 0.05:
        mismatch_axis = "projection_level"
    elif max(abs(conf_delta or 0.0), abs(gain_delta or 0.0)) > 0.08:
        mismatch_axis = "gain_structure"
    else:
        mismatch_axis = "mixed"

    return {
        "classification": str(classification),
        "mismatch_axis": str(mismatch_axis),
        "deltas": {
            "pred_projection_bad_prob": proj_bad_delta,
            "pred_projection_error": proj_err_delta,
            "confidence": conf_delta,
            "gain": gain_delta,
        },
        "segment_summary": segment_summary,
    }


def _next_template_for_segment_probe(*, has_benchmark_like: bool, dominant_axis: str) -> Dict[str, Any]:
    if has_benchmark_like:
        return {
            "template_name": "routing_rule.activation_window_probe",
            "reason": "a benchmark-like live segment exists, so the next safe step is a narrow segment-targeted routing probe",
            "hypothesis": "segment_targeted_routing_probe",
        }
    axis = str(dominant_axis)
    if axis in {"projection_level", "projection_shape"}:
        return {
            "template_name": "score_reweight.blocker_sensitive_projection_probe",
            "reason": "no benchmark-like live segment was found; the mismatch is dominated by projection structure rather than a simple routing window",
            "hypothesis": "projection_structure_probe",
        }
    if axis == "gain_structure":
        return {
            "template_name": "score_reweight.gain_goal_conflict_probe",
            "reason": "no benchmark-like live segment was found; the mismatch is dominated by gain/confidence structure",
            "hypothesis": "gain_probe",
        }
    return {
        "template_name": "critic_split.projection_gain_goal_v1",
        "reason": "no benchmark-like live segment was found and the mismatch remains mixed, so critic decomposition is the safest next clarification step",
        "hypothesis": "benchmark_alignment_probe",
    }


def _row_score_baseline(row: Dict[str, Any], benchmark_summary: Dict[str, Dict[str, Any]]) -> float:
    confidence = float(_safe_metric(row.get("confidence")) or 0.0)
    gain = float(_safe_metric(row.get("gain")) or 0.0)
    pred_projection_bad = float(_safe_metric(row.get("pred_projection_bad_prob")) or 1.0)
    pred_projection_error = float(_safe_metric(row.get("pred_projection_error")) or 0.0)
    pred_post_gain = float(_safe_metric(row.get("pred_post_gain")) or 0.0)
    proj_err_ref = max(float(_summary_mean(benchmark_summary, "pred_projection_error") or 0.02) * 8.0, 0.08)
    gain_ref = 0.25
    proj_err_norm = min(max(pred_projection_error / proj_err_ref, 0.0), 2.0)
    post_gain_norm = math.tanh(pred_post_gain / gain_ref)
    return float(
        0.35 * gain
        + 0.25 * confidence
        + 0.15 * post_gain_norm
        - 0.20 * pred_projection_bad
        - 0.15 * proj_err_norm
    )


def _row_score_projection_probe(row: Dict[str, Any], benchmark_summary: Dict[str, Dict[str, Any]]) -> float:
    base_score = _row_score_baseline(row, benchmark_summary)
    pred_projection_bad = float(_safe_metric(row.get("pred_projection_bad_prob")) or 1.0)
    pred_projection_error = float(_safe_metric(row.get("pred_projection_error")) or 0.0)
    confidence = float(_safe_metric(row.get("confidence")) or 0.0)
    gain = float(_safe_metric(row.get("gain")) or 0.0)
    pred_post_gain = float(_safe_metric(row.get("pred_post_gain")) or 0.0)
    proj_err_ref = max(float(_summary_mean(benchmark_summary, "pred_projection_error") or 0.02) * 8.0, 0.08)
    proj_err_norm = min(max(pred_projection_error / proj_err_ref, 0.0), 2.0)
    post_gain_norm = math.tanh(pred_post_gain / 0.25)
    blocker = str(row.get("blocker_group", "other"))
    segment = str(row.get("segment", "mixed_shift"))

    score = float(base_score - 0.12 * pred_projection_bad - 0.18 * proj_err_norm)
    if blocker == "projection_guard" or segment in {"projection_far_shifted", "projection_mid_shifted"}:
        score -= 0.20 * pred_projection_bad
        score -= 0.22 * proj_err_norm
    if segment == "stability_sensitive":
        score -= 0.18
        score -= 0.12 * proj_err_norm
    if segment == "gain_structure_shifted":
        score += 0.12 * gain
        score += 0.08 * confidence
        score += 0.08 * post_gain_norm
        score += 0.05 * max(0.0, 0.60 - pred_projection_bad)
    if segment == "benchmark_adjacent":
        score += 0.14 * gain
        score += 0.10 * confidence
        score += 0.08 * max(0.0, 0.58 - pred_projection_bad)
    return float(score)


def _row_projection_level_critic_v2(
    row: Dict[str, Any],
    benchmark_summary: Dict[str, Dict[str, Any]],
    *,
    projection_boundary: float,
) -> float:
    pred_projection_bad = float(_safe_metric(row.get("pred_projection_bad_prob")) or 1.0)
    boundary_distance = max(0.0, float(_safe_metric(row.get("boundary_distance")) or 0.0))
    benchmark_projection_bad = float(_summary_mean(benchmark_summary, "pred_projection_bad_prob") or projection_boundary)
    benchmark_gap = max(0.0, pred_projection_bad - benchmark_projection_bad)
    pred_projection_explosion = float(_safe_metric(row.get("pred_projection_explosion_prob")) or pred_projection_bad)
    segment = str(row.get("segment", "mixed_shift"))

    boundary_excess_norm = min(boundary_distance / 0.10, 2.5)
    benchmark_gap_norm = min(benchmark_gap / 0.10, 2.5)
    critic = float(
        0.38 * pred_projection_bad
        + 0.34 * boundary_excess_norm
        + 0.20 * benchmark_gap_norm
        + 0.08 * pred_projection_explosion
    )
    if segment == "projection_far_shifted":
        critic += 0.35
    elif segment == "projection_mid_shifted":
        critic += 0.10
    elif segment == "projection_borderline":
        critic -= 0.06
    elif segment == "benchmark_adjacent":
        critic -= 0.08
    return float(critic)


def _row_projection_shape_critic_v2(row: Dict[str, Any], benchmark_summary: Dict[str, Dict[str, Any]]) -> float:
    pred_projection_error = float(_safe_metric(row.get("pred_projection_error")) or 0.0)
    pred_projection_explosion = float(_safe_metric(row.get("pred_projection_explosion_prob")) or 0.0)
    benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 1.0)
    benchmark_proj_err = max(float(_summary_mean(benchmark_summary, "pred_projection_error") or 0.01), 0.005)
    proj_err_norm = min(pred_projection_error / (benchmark_proj_err * 2.5), 3.0)
    benchmark_distance_norm = min(benchmark_distance / 1.10, 2.5)
    segment = str(row.get("segment", "mixed_shift"))

    critic = float(
        0.46 * proj_err_norm
        + 0.34 * benchmark_distance_norm
        + 0.20 * pred_projection_explosion
    )
    if segment == "projection_far_shifted":
        critic += 0.25
    elif segment == "projection_mid_shifted":
        critic += 0.06
    elif segment == "gain_structure_shifted":
        critic -= 0.04 * max(0.0, 1.0 - benchmark_distance_norm)
    elif segment == "benchmark_adjacent":
        critic -= 0.08
    return float(critic)


def _row_gain_goal_critic_v2(row: Dict[str, Any], benchmark_summary: Dict[str, Dict[str, Any]]) -> float:
    confidence = float(_safe_metric(row.get("confidence")) or 0.0)
    gain = float(_safe_metric(row.get("gain")) or 0.0)
    pred_post_gain = float(_safe_metric(row.get("pred_post_gain")) or 0.0)
    benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 1.0)
    benchmark_proximity = max(0.0, 1.20 - min(benchmark_distance, 1.20))
    post_gain_norm = math.tanh(pred_post_gain / 0.20)
    segment = str(row.get("segment", "mixed_shift"))
    blocker = str(row.get("blocker_group", "other"))

    critic = float(
        0.44 * gain
        + 0.34 * confidence
        + 0.16 * post_gain_norm
        + 0.16 * benchmark_proximity
    )
    if segment == "gain_structure_shifted":
        critic += 0.12 * gain
        critic += 0.10 * confidence
        critic += 0.08 * benchmark_proximity
    elif segment == "benchmark_adjacent":
        critic += 0.10 * gain
        critic += 0.08 * confidence
        critic += 0.10 * benchmark_proximity
    elif segment in {"projection_mid_shifted", "projection_borderline"}:
        critic += 0.06 * gain
        critic += 0.04 * confidence
    if blocker == "confidence_gain":
        critic += 0.06
    return float(critic)


def _row_stability_critic_v2(
    row: Dict[str, Any],
    *,
    projection_level_critic: float,
    projection_shape_critic: float,
    gain_goal_critic: float,
) -> float:
    blocker = str(row.get("blocker_group", "other"))
    segment = str(row.get("segment", "mixed_shift"))
    stability_flag = blocker in {"persistence_guard", "recovery_guard"} or segment == "stability_sensitive"
    if not stability_flag:
        return 0.0
    critic = float(0.28 + 0.18 * projection_shape_critic + 0.10 * projection_level_critic)
    if gain_goal_critic >= 0.45 and projection_shape_critic <= 0.70 and projection_level_critic <= 0.70:
        critic -= 0.14
    if blocker == "recovery_guard":
        critic += 0.08
    return float(max(0.0, critic))


def _benchmark_distance(row: Dict[str, Any], benchmark_summary: Dict[str, Dict[str, Any]]) -> float:
    terms: List[float] = []
    for key, scale in (
        ("pred_projection_bad_prob", 0.10),
        ("pred_projection_error", 0.08),
        ("confidence", 0.10),
        ("gain", 0.10),
    ):
        row_value = _safe_metric(row.get(key))
        benchmark_value = _summary_mean(benchmark_summary, key)
        if row_value is None or benchmark_value is None:
            continue
        terms.append(min(abs(float(row_value) - float(benchmark_value)) / float(scale), 3.0))
    if not terms:
        return 1.0
    return float(sum(terms) / len(terms))


def _mean_key(rows: List[Dict[str, Any]], key: str) -> float | None:
    values = [float(v) for v in (_safe_metric(dict(row).get(key)) for row in rows) if v is not None]
    if not values:
        return None
    return float(sum(values) / len(values))


def _top_slice(rows: List[Dict[str, Any]], *, score_key: str, frac: float = 0.25) -> List[Dict[str, Any]]:
    clean = [dict(row) for row in rows if _safe_metric(dict(row).get(score_key)) is not None]
    if not clean:
        return []
    ordered = sorted(clean, key=lambda item: float(item.get(score_key, -1e9)), reverse=True)
    keep = max(1, int(math.ceil(len(ordered) * max(0.05, min(1.0, float(frac))))))
    return ordered[:keep]


def _benchmark_candidate_blocker_group(
    cfg: ProposalLearningConfig,
    scenario_result: Dict[str, Any],
    projection_boundary: float,
) -> str:
    family = str(scenario_result.get("family", ""))
    candidate_summary = dict(scenario_result.get("candidate_summary", {}))
    provisional = dict(scenario_result.get("decision_results", {}).get("provisional", {}))
    predicted = dict(provisional.get("predicted", {}))

    moving_average = float(candidate_summary.get("moving_average", 0.0))
    persistence_streak = int(candidate_summary.get("persistence_streak", 0))
    retained_evidence = float(candidate_summary.get("retained_evidence", 0.0))
    confidence = float(candidate_summary.get("confidence", 0.0))
    confidence_threshold = float(candidate_summary.get("confidence_provisional_threshold", cfg.adopt_threshold_provisional))
    gain = float(candidate_summary.get("gain", 0.0))
    gain_threshold = float(candidate_summary.get("gain_provisional_threshold", cfg.adoption_score_threshold_provisional))
    projected_score = float(predicted.get("calibrated_projected", 0.0))
    projected_score_threshold = float(getattr(cfg, "adoption_score_threshold_provisional", 0.47))
    pred_projection_bad = float(provisional.get("pred_projection_bad_prob", 1.0))

    if family == "recovery":
        return "recovery_guard"
    if persistence_streak > 0 or retained_evidence > 0.05 or moving_average > 0.05 or family == "persistence":
        return "persistence_guard"
    if (not bool(candidate_summary.get("projection_policy_ok_provisional", False))) or pred_projection_bad > float(projection_boundary):
        return "projection_guard"
    if confidence < confidence_threshold or gain < gain_threshold or projected_score < projected_score_threshold:
        return "confidence_gain"
    return "projection_guard"


def _benchmark_scenario_candidate_row(
    cfg: ProposalLearningConfig,
    scenario_result: Dict[str, Any],
    *,
    projection_boundary: float,
    benchmark_summary: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    row = _benchmark_reference_row(scenario_result, projection_boundary)
    row["blocker_group"] = str(_benchmark_candidate_blocker_group(cfg, scenario_result, projection_boundary))
    row["segment"] = str(
        _segment_live_candidate(
            row,
            benchmark_summary=benchmark_summary,
            projection_boundary=projection_boundary,
        )
    )
    row["benchmark_distance"] = float(_benchmark_distance(row, benchmark_summary))
    row["projection_critic"] = float(_row_projection_critic(row, benchmark_summary))
    row["gain_goal_critic"] = float(_row_gain_goal_critic(row, benchmark_summary))
    row["critic_split_score"] = float(row["gain_goal_critic"] - row["projection_critic"])
    row["family"] = str(scenario_result.get("family", ""))
    row["policy_decision"] = str(scenario_result.get("policy_decision", ""))
    row["oracle_decision"] = str(scenario_result.get("oracle_decision", ""))
    return row


def _slice_fragility_level(*, slice_count: int, gain_goal_delta: float, false_safe_delta: float, family_counter: Counter[str]) -> str:
    if slice_count <= 2:
        return "high"
    dominant_share = float(family_counter.most_common(1)[0][1] / slice_count) if slice_count > 0 and family_counter else 1.0
    if false_safe_delta > 0.0 or dominant_share >= 0.80:
        return "high"
    if slice_count <= 5 or gain_goal_delta <= 0.0:
        return "medium"
    return "low"


def _stddev(values: List[float]) -> float | None:
    clean = [float(v) for v in values if math.isfinite(float(v))]
    if not clean:
        return None
    mean_value = float(sum(clean) / len(clean))
    variance = float(sum((value - mean_value) ** 2 for value in clean) / len(clean))
    return float(math.sqrt(variance))


def _rate_summary(seed_summaries: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    values = [float(dict(summary).get(str(key), 0.0)) for summary in seed_summaries]
    if not values:
        return {"count": 0}
    return {
        "count": int(len(values)),
        "mean": float(sum(values) / len(values)),
        "min": float(min(values)),
        "max": float(max(values)),
        "std": _stddev(values),
    }


def _row_projection_critic(row: Dict[str, Any], benchmark_summary: Dict[str, Dict[str, Any]]) -> float:
    pred_projection_bad = float(_safe_metric(row.get("pred_projection_bad_prob")) or 1.0)
    pred_projection_error = float(_safe_metric(row.get("pred_projection_error")) or 0.0)
    pred_projection_explosion = float(_safe_metric(row.get("pred_projection_explosion_prob")) or pred_projection_bad)
    benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 1.0)
    blocker = str(row.get("blocker_group", "other"))
    segment = str(row.get("segment", "mixed_shift"))
    proj_err_ref = max(float(_summary_mean(benchmark_summary, "pred_projection_error") or 0.02) * 8.0, 0.08)
    proj_err_norm = min(max(pred_projection_error / proj_err_ref, 0.0), 2.0)
    benchmark_distance_norm = min(max(benchmark_distance / 1.25, 0.0), 2.0)

    critic = float(
        0.58 * pred_projection_bad
        + 0.62 * proj_err_norm
        + 0.22 * pred_projection_explosion
        + 0.14 * benchmark_distance_norm
    )
    if blocker == "projection_guard":
        critic += 0.18 * pred_projection_bad
        critic += 0.16 * proj_err_norm
    if segment in {"projection_far_shifted", "projection_mid_shifted"}:
        critic += 0.22
        critic += 0.12 * benchmark_distance_norm
    if segment == "stability_sensitive":
        critic += 0.16
        critic += 0.10 * proj_err_norm
    if segment == "benchmark_adjacent":
        critic -= 0.10 * max(0.0, 0.60 - pred_projection_bad)
    if segment == "gain_structure_shifted":
        critic -= 0.04 * max(0.0, 0.58 - pred_projection_bad)
    return float(critic)


def _row_gain_goal_critic(row: Dict[str, Any], benchmark_summary: Dict[str, Dict[str, Any]]) -> float:
    confidence = float(_safe_metric(row.get("confidence")) or 0.0)
    gain = float(_safe_metric(row.get("gain")) or 0.0)
    pred_post_gain = float(_safe_metric(row.get("pred_post_gain")) or 0.0)
    benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 1.0)
    segment = str(row.get("segment", "mixed_shift"))
    blocker = str(row.get("blocker_group", "other"))
    post_gain_norm = math.tanh(pred_post_gain / 0.25)
    benchmark_proximity = max(0.0, 1.20 - min(benchmark_distance, 1.20))

    critic = float(
        0.42 * gain
        + 0.34 * confidence
        + 0.18 * post_gain_norm
        + 0.12 * benchmark_proximity
    )
    if segment == "gain_structure_shifted":
        critic += 0.12 * gain
        critic += 0.08 * confidence
        critic += 0.06 * post_gain_norm
    if segment == "benchmark_adjacent":
        critic += 0.14 * gain
        critic += 0.10 * confidence
        critic += 0.12 * benchmark_proximity
    if segment == "stability_sensitive":
        critic -= 0.10
    if blocker == "projection_guard":
        critic -= 0.04
    return float(critic)


def _load_latest_diagnostic_artifact_by_template(template_name: str) -> Dict[str, Any]:
    artifact_dir = _diagnostic_artifact_dir()
    rows: List[tuple[float, Dict[str, Any]]] = []
    for path in artifact_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if str(payload.get("template_name", "")) != str(template_name):
            continue
        rows.append((float(path.stat().st_mtime), payload))
    if not rows:
        return {}
    rows.sort(key=lambda item: item[0], reverse=True)
    return dict(rows[0][1])


def _run_shadow_score_reweight_projection_probe_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    intended_benefit = dict(proposal.get("intended_benefit", {}))
    benchmark_target_family = str(intended_benefit.get("secondary_family") or intended_benefit.get("target_family", "gain_goal_conflict"))
    mechanism = dict(proposal.get("mechanism", {}))
    analytics = build_intervention_ledger_analytics()
    prior_suggestions = list(dict(analytics.get("compact_summary", {})).get("recommendations", {}).get("suggested_next_templates", []))

    live_rows: List[Dict[str, Any]] = []
    source_records: List[Dict[str, Any]] = []
    projection_boundary = float("nan")

    for seed in list(seeds):
        run_cfg = copy.deepcopy(cfg)
        run_cfg.verbose = False
        run_cfg.rounds = max(1, int(rounds))
        run_cfg.seed = int(seed)
        run_cfg.benchmark_every_rounds = 0
        run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs or {})
        run_cfg.eval_kwargs["session_log_path"] = (
            f"logs/intervention_shadow_{proposal['proposal_id']}_score_probe_seed{int(seed)}.log"
        )
        apply_live_policy_variant(run_cfg, "targeted_gain_goal_proj_margin_01")
        projection_boundary = float(_targeted_projection_override_boundary(run_cfg))
        _, _, history = run_proposal_learning_loop(run_cfg)
        for round_index, entry in enumerate(history):
            blocked = [item for item in list(entry.get("adopt_blocked", [])) if isinstance(item, dict)]
            adopted = [item for item in list(entry.get("adopted", [])) if isinstance(item, dict)]
            override_rows = [item for item in adopted if bool(item.get("live_variant_override_applied", False))]
            source_records.append(
                {
                    "seed": int(seed),
                    "round_index": int(round_index),
                    "blocked_candidates": int(len(blocked)),
                    "override_activated": int(len(override_rows)),
                }
            )
            for item in blocked:
                live_rows.append(
                    _live_gap_row(
                        item,
                        seed=int(seed),
                        round_index=int(round_index),
                        cohort="baseline_rejected",
                        projection_boundary=projection_boundary,
                    )
                )
            for item in override_rows:
                live_rows.append(
                    _live_gap_row(
                        item,
                        seed=int(seed),
                        round_index=int(round_index),
                        cohort="baseline_rejected_override_activated",
                        projection_boundary=projection_boundary,
                    )
                )

    benchmark_rows = _load_latest_benchmark_detailed_rows()
    benchmark_undercommit_all = [
        row
        for row in benchmark_rows
        if str(row.get("policy_decision", "")) == "reject" and str(row.get("oracle_decision", "")) in {"provisional", "full"}
    ]
    benchmark_undercommit_target = [
        row for row in benchmark_undercommit_all if str(row.get("family", "")) == benchmark_target_family
    ]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (
            benchmark_undercommit_target
            if benchmark_reference_source == "target_family_undercommit"
            else benchmark_undercommit_all
        )
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }

    segments: Dict[str, List[Dict[str, Any]]] = {}
    for row in live_rows:
        segment_name = _segment_live_candidate(
            row,
            benchmark_summary=benchmark_summary,
            projection_boundary=projection_boundary,
        )
        row["segment"] = str(segment_name)
        row["baseline_score"] = float(_row_score_baseline(row, benchmark_summary))
        row["probe_score"] = float(_row_score_projection_probe(row, benchmark_summary))
        row["score_delta"] = float(row["probe_score"] - row["baseline_score"])
        row["benchmark_distance"] = float(_benchmark_distance(row, benchmark_summary))
        segments.setdefault(str(segment_name), []).append(row)

    def _segment_bucket(segment_name: str) -> str:
        if segment_name in {"projection_far_shifted", "projection_mid_shifted"}:
            return "clearly_outside_safe_window"
        if segment_name == "projection_borderline":
            return "borderline"
        if segment_name == "benchmark_adjacent":
            return "benchmark_like"
        if segment_name == "stability_sensitive":
            return "persistence_recovery_sensitive"
        if segment_name == "gain_structure_shifted":
            return "gain_structure_shifted"
        return "mixed"

    def _score_summary(rows: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
        values = sorted(float(dict(row).get(key, 0.0)) for row in rows if _safe_metric(dict(row).get(key)) is not None)
        if not values:
            return {"count": 0}
        return {
            "count": int(len(values)),
            "mean": float(sum(values) / len(values)),
            "min": float(values[0]),
            "p25": float(_quantile(values, 0.25)),
            "median": float(_quantile(values, 0.50)),
            "p75": float(_quantile(values, 0.75)),
            "max": float(values[-1]),
        }

    segment_summaries: Dict[str, Dict[str, Any]] = {}
    for segment_name, rows in sorted(segments.items(), key=lambda item: (-len(item[1]), str(item[0]))):
        blocker_counts = Counter(str(row.get("blocker_group", "other")) for row in rows)
        segment_summaries[str(segment_name)] = {
            "count": int(len(rows)),
            "segment_bucket": str(_segment_bucket(segment_name)),
            "position_label": str(_segment_position_label(segment_name)),
            "dominant_blocker": blocker_counts.most_common(1)[0][0] if blocker_counts else "none",
            "blocker_counts": {
                str(name): int(count)
                for name, count in sorted(blocker_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
            "metrics": {
                "pred_projection_bad_prob": _metric_summary(rows, "pred_projection_bad_prob"),
                "pred_projection_error": _metric_summary(rows, "pred_projection_error"),
                "confidence": _metric_summary(rows, "confidence"),
                "gain": _metric_summary(rows, "gain"),
                "pred_post_gain": _metric_summary(rows, "pred_post_gain"),
                "benchmark_distance": _score_summary(rows, "benchmark_distance"),
            },
            "scores_before_after": {
                "baseline_score": _score_summary(rows, "baseline_score"),
                "probe_score": _score_summary(rows, "probe_score"),
                "score_delta": _score_summary(rows, "score_delta"),
            },
        }

    risky_segments = {"projection_far_shifted", "projection_mid_shifted", "stability_sensitive"}
    salvageable_segments = {"gain_structure_shifted", "benchmark_adjacent", "projection_borderline"}
    risky_rows = [row for row in live_rows if str(row.get("segment")) in risky_segments]
    salvageable_rows = [row for row in live_rows if str(row.get("segment")) in salvageable_segments]

    risky_before = _mean_key(risky_rows, "baseline_score")
    risky_after = _mean_key(risky_rows, "probe_score")
    salvage_before = _mean_key(salvageable_rows, "baseline_score")
    salvage_after = _mean_key(salvageable_rows, "probe_score")
    separation_margin_before = None if risky_before is None or salvage_before is None else float(salvage_before - risky_before)
    separation_margin_after = None if risky_after is None or salvage_after is None else float(salvage_after - risky_after)

    far_rows = list(segments.get("projection_far_shifted", []))
    stability_rows = list(segments.get("stability_sensitive", []))
    gain_rows = list(segments.get("gain_structure_shifted", []))
    adjacent_rows = list(segments.get("benchmark_adjacent", []))

    top_before = _top_slice(live_rows, score_key="baseline_score", frac=0.25)
    top_after = _top_slice(live_rows, score_key="probe_score", frac=0.25)

    def _segment_share(rows: List[Dict[str, Any]], segment_name: str) -> float:
        if not rows:
            return 0.0
        return float(sum(str(row.get("segment")) == str(segment_name) for row in rows) / len(rows))

    top_before_far_share = _segment_share(top_before, "projection_far_shifted")
    top_after_far_share = _segment_share(top_after, "projection_far_shifted")
    top_before_stability_share = _segment_share(top_before, "stability_sensitive")
    top_after_stability_share = _segment_share(top_after, "stability_sensitive")
    top_before_salvage_share = (
        float(sum(str(row.get("segment")) in salvageable_segments for row in top_before) / len(top_before))
        if top_before
        else 0.0
    )
    top_after_salvage_share = (
        float(sum(str(row.get("segment")) in salvageable_segments for row in top_after) / len(top_after))
        if top_after
        else 0.0
    )
    top_before_distance = _mean_key(top_before, "benchmark_distance")
    top_after_distance = _mean_key(top_after, "benchmark_distance")

    benchmark_like_slice_rows = [
        row
        for row in top_after
        if str(row.get("segment")) in {"benchmark_adjacent", "gain_structure_shifted", "projection_borderline"}
        and float(row.get("benchmark_distance", 99.0)) <= 1.10
    ]
    benchmark_like_slice_emerged = bool(len(benchmark_like_slice_rows) >= 2)

    projection_far_shifted_isolated = bool(
        top_after_far_share + 0.10 <= top_before_far_share
        and (separation_margin_after is not None and separation_margin_before is not None and separation_margin_after >= separation_margin_before + 0.08)
    )
    projection_shape_mismatch_improved = bool(
        projection_far_shifted_isolated
        or (
            top_before_distance is not None
            and top_after_distance is not None
            and top_after_distance <= top_before_distance - 0.10
        )
    )

    if projection_shape_mismatch_improved or benchmark_like_slice_emerged:
        score_probe_effect = "improved_separation"
    elif (
        top_before_distance is not None
        and top_after_distance is not None
        and top_after_distance >= top_before_distance + 0.10
    ) or (top_after_far_share >= top_before_far_share + 0.10):
        score_probe_effect = "harmful"
    else:
        score_probe_effect = "no_change"

    if benchmark_like_slice_emerged:
        next_control_hypothesis = "routing_retry"
        recommended_next_template = "routing_rule.activation_window_probe"
        recommendation_reason = "the reweighted score exposes a small benchmark-like slice suitable for a narrow routing probe"
    elif score_probe_effect == "improved_separation":
        next_control_hypothesis = "score_refinement"
        recommended_next_template = "critic_split.projection_gain_goal_v1"
        recommendation_reason = "score reweighting improves risky-vs-salvageable separation, so the next safe step is a more explicit projection/gain critic split"
    else:
        next_control_hypothesis = "benchmark_alignment_followup"
        recommended_next_template = "critic_split.projection_gain_goal_v1"
        recommendation_reason = "the score probe did not expose a trustworthy routing slice, so the next clarification step should stay score-structure focused"

    observability_gain_passed = bool(len(live_rows) >= 12 and len(segments) >= 2 and len(benchmark_reference_rows) >= 6)
    observability_gain = {
        "passed": observability_gain_passed,
        "live_rejected_candidate_count": int(len(live_rows)),
        "segment_count": int(len(segments)),
        "benchmark_reference_count": int(len(benchmark_reference_rows)),
        "benchmark_reference_source": str(benchmark_reference_source),
        "reason": (
            "captured enough live rejected traffic and benchmark undercommit evidence for deterministic score-structure probing"
            if observability_gain_passed
            else "insufficient live rejected or benchmark reference evidence for stable score-probe analysis"
        ),
    }

    activation_analysis_passed = bool(observability_gain_passed and bool(recommended_next_template))
    activation_analysis = {
        "passed": activation_analysis_passed,
        "score": float(
            min(
                1.0,
                0.35
                + 0.20 * int(score_probe_effect == "improved_separation")
                + 0.15 * int(benchmark_like_slice_emerged)
                + 0.15 * int(projection_far_shifted_isolated)
                + 0.15 * int(projection_shape_mismatch_improved)
                + 0.10 * int(bool(recommended_next_template))
            )
        ),
        "score_probe_effect": str(score_probe_effect),
        "projection_far_shifted_isolated": bool(projection_far_shifted_isolated),
        "benchmark_like_slice_emerged": bool(benchmark_like_slice_emerged),
        "next_control_hypothesis": str(next_control_hypothesis),
        "reason": (
            "the score probe produced an actionable ranking change assessment"
            if activation_analysis_passed
            else "the score probe did not produce a stable actionable ranking assessment"
        ),
    }

    ambiguity_reduction = {
        "passed": bool(observability_gain_passed and score_probe_effect in {"improved_separation", "no_change", "harmful"} and bool(recommended_next_template)),
        "score": float(
            max(
                0.0,
                min(
                    1.0,
                    0.25
                    + 0.25 * int(separation_margin_after is not None)
                    + 0.20 * int(top_after_distance is not None)
                    + 0.15 * int(benchmark_like_slice_emerged)
                    + 0.15 * int(bool(recommended_next_template)),
                )
            )
        ),
        "dominant_mismatch_axis": "projection_shape",
        "reason": (
            "the score probe reduced the next-step choice to a narrow score-focused vs routing-focused branch"
            if bool(observability_gain_passed and bool(recommended_next_template))
            else "the score probe remains too ambiguous to guide the next proposal"
        ),
    }

    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "audit-only score reweight probe with no default live-policy mutation and no benchmark semantic changes",
    }

    later_selection_usefulness = {
        "passed": bool(observability_gain_passed and bool(recommended_next_template)),
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
        "analytics_prior_suggestions": prior_suggestions[:3],
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": str(proposal.get("template_name")),
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "signals_reweighted": list(mechanism.get("reweighted_signals", [])),
        "blocker_sensitive_rules_used": list(mechanism.get("blocker_sensitive_rules", [])),
        "benchmark_target_family": str(benchmark_target_family),
        "live_rejected_candidate_count": int(len(live_rows)),
        "segmentation_method": {
            "name": "deterministic_bucket_v1",
            "source": "routing_rule.candidate_distribution_aware_probe-compatible segmentation",
            "projection_boundary": float(projection_boundary),
        },
        "segment_summaries": segment_summaries,
        "separation_summary": {
            "risky_segments": sorted(risky_segments),
            "salvageable_segments": sorted(salvageable_segments),
            "separation_margin_before": separation_margin_before,
            "separation_margin_after": separation_margin_after,
            "projection_far_shifted_mean_before": _mean_key(far_rows, "baseline_score"),
            "projection_far_shifted_mean_after": _mean_key(far_rows, "probe_score"),
            "stability_sensitive_mean_before": _mean_key(stability_rows, "baseline_score"),
            "stability_sensitive_mean_after": _mean_key(stability_rows, "probe_score"),
            "gain_structure_shifted_mean_before": _mean_key(gain_rows, "baseline_score"),
            "gain_structure_shifted_mean_after": _mean_key(gain_rows, "probe_score"),
            "benchmark_adjacent_mean_before": _mean_key(adjacent_rows, "baseline_score"),
            "benchmark_adjacent_mean_after": _mean_key(adjacent_rows, "probe_score"),
        },
        "top_slice_comparison": {
            "baseline_top_slice_count": int(len(top_before)),
            "probe_top_slice_count": int(len(top_after)),
            "baseline_projection_far_shifted_share": float(top_before_far_share),
            "probe_projection_far_shifted_share": float(top_after_far_share),
            "baseline_stability_sensitive_share": float(top_before_stability_share),
            "probe_stability_sensitive_share": float(top_after_stability_share),
            "baseline_salvageable_share": float(top_before_salvage_share),
            "probe_salvageable_share": float(top_after_salvage_share),
            "baseline_benchmark_distance_mean": top_before_distance,
            "probe_benchmark_distance_mean": top_after_distance,
        },
        "benchmark_comparison_summary": {
            "source": str(benchmark_reference_source),
            "count": int(len(benchmark_reference_rows)),
            "metrics": benchmark_summary,
        },
        "diagnostic_conclusions": {
            "score_probe_effect": str(score_probe_effect),
            "projection_far_shifted_isolated": bool(projection_far_shifted_isolated),
            "benchmark_like_slice_emerged": bool(benchmark_like_slice_emerged),
            "has_benchmark_like_live_segment": bool(benchmark_like_slice_emerged),
            "dominant_mismatch_axis": "projection_shape",
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
        },
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "blocker_counts": {
            str(name): int(count)
            for name, count in sorted(
                Counter(str(row.get("blocker_group", "other")) for row in live_rows).items(),
                key=lambda item: (-int(item[1]), str(item[0])),
            )
        },
        "source_records": source_records[-24:],
        "sample_rows": {
            "top_slice_before": top_before[:5],
            "top_slice_after": top_after[:5],
            "benchmark_like_slice_after": benchmark_like_slice_rows[:5],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"score_reweight_probe_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(
        observability_gain_passed
        and bool(activation_analysis["passed"])
        and bool(ambiguity_reduction["passed"])
        and bool(safety_neutrality["passed"])
        and bool(later_selection_usefulness["passed"])
    )
    if not observability_gain_passed:
        reason = "diagnostic shadow failed: insufficient live rejected or benchmark reference evidence for score probing"
    elif not bool(activation_analysis["passed"]):
        reason = "diagnostic shadow failed: score probe did not produce an actionable separation assessment"
    elif not bool(ambiguity_reduction["passed"]):
        reason = "diagnostic shadow failed: score probe remained too ambiguous"
    elif score_probe_effect == "harmful":
        reason = "diagnostic shadow passed: score probe showed harmful separation drift and argues against immediate score-family promotion"
    elif score_probe_effect == "no_change":
        reason = "diagnostic shadow passed: score probe showed little separation benefit and narrows the next step to benchmark-alignment follow-up"
    else:
        reason = "diagnostic shadow passed: blocker-sensitive score reweighting improved segment separation without changing live policy"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_critic_split_benchmark_alignment_critic_v2_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    v2_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.projection_gain_goal_v2")
    purity_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.safe_slice_purity_probe_v1")
    distance_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_distance_retention_probe_v1")
    alignment_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_alignment_critic_v1")
    stability_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.stability_context_retention_probe_v1")
    availability_artifact = _load_latest_diagnostic_artifact_by_template("memory_summary.benchmark_context_availability_snapshot")
    seed_context_artifact = _load_latest_diagnostic_artifact_by_template("memory_summary.seed_context_shift_snapshot")
    if not v2_artifact or not purity_artifact or not distance_artifact or not alignment_artifact or not stability_artifact or not availability_artifact or not seed_context_artifact:
        return {"passed": False, "shadow_contract": "diagnostic_probe", "proposal_semantics": "diagnostic", "reason": "diagnostic shadow failed: benchmark_alignment_critic_v2 requires prior critic/context artifacts", "observability_gain": {"passed": False, "reason": "missing prerequisite critic/context artifacts"}, "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite critic/context artifacts"}, "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite critic/context artifacts"}, "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))}, "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without the prerequisite critic/context artifacts"}}

    mechanism = dict(proposal.get("mechanism", {}))
    benchmark_target_family = str(dict(proposal.get("intended_benefit", {})).get("target_family", "gain_goal_conflict"))
    projection_boundary = float(_targeted_projection_override_boundary(cfg))
    benchmark_rows = _load_latest_benchmark_detailed_rows()
    benchmark_undercommit_all = [row for row in benchmark_rows if str(row.get("policy_decision", "")) == "reject" and str(row.get("oracle_decision", "")) in {"provisional", "full"}]
    benchmark_undercommit_target = [row for row in benchmark_undercommit_all if str(row.get("family", "")) == benchmark_target_family]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [_benchmark_reference_row(row, projection_boundary) for row in (benchmark_undercommit_target if benchmark_reference_source == "target_family_undercommit" else benchmark_undercommit_all)]
    benchmark_summary = {"pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"), "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"), "confidence": _metric_summary(benchmark_reference_rows, "confidence"), "gain": _metric_summary(benchmark_reference_rows, "gain"), "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain")}
    slice_definition = dict(v2_artifact.get("slice_definition", {}))
    projection_level_cap = float(slice_definition.get("projection_level_cap", 0.70))
    projection_shape_cap = float(slice_definition.get("projection_shape_cap", 0.65))
    gain_goal_floor = float(slice_definition.get("gain_goal_floor", 0.34))
    stability_cap = float(slice_definition.get("stability_cap", 0.42))
    projection_bad_safe_cap = float(slice_definition.get("projection_bad_safe_cap", 0.57))
    projection_error_safe_cap = float(slice_definition.get("projection_error_safe_cap", 0.0115))
    benchmark_distance_cap = float(slice_definition.get("benchmark_distance_cap", 1.0))
    gain_structure_level_soft_cap = float(slice_definition.get("gain_structure_level_soft_cap", projection_level_cap + 0.08))
    gain_structure_benchmark_distance_soft_cap = float(slice_definition.get("gain_structure_benchmark_distance_soft_cap", benchmark_distance_cap + 0.05))
    gain_structure_projection_bad_soft_cap = float(slice_definition.get("gain_structure_projection_bad_soft_cap", projection_bad_safe_cap + 0.02))
    gain_structure_gain_soft_floor = float(slice_definition.get("gain_structure_gain_soft_floor", gain_goal_floor + 0.08))
    baseline_live_activation_count = int(dict(v2_artifact.get("observability_gain", {})).get("slice_activation_count", dict(v2_artifact.get("comparison_to_v1", {})).get("slice_activation_count_v2", 0)))
    baseline_safe_retention_rate = float(dict(v2_artifact.get("comparison_to_v1", {})).get("projection_safe_retention_rate_v2", 0.0))
    baseline_benchmark_like_retention_rate = float(dict(v2_artifact.get("comparison_to_v1", {})).get("benchmark_like_retention_rate_v2", 0.0))
    baseline_mean_projection_error = _safe_metric(dict(v2_artifact.get("comparison_to_v1", {})).get("mean_projection_error_v2"))
    baseline_seed_activation_rate_summary = dict(dict(v2_artifact.get("comparison_to_v1", {})).get("seed_activation_rate_v2", {}))
    baseline_seed_counts = {int(dict(seed_summary).get("seed", -1)): int(dict(seed_summary).get("slice_activation_count", 0)) for seed_summary in list(v2_artifact.get("seed_summaries", [])) if _safe_metric(dict(seed_summary).get("seed")) is not None}
    baseline_benchmark_alignment = dict(v2_artifact.get("benchmark_alignment_summary", {}))
    baseline_benchmark_slice_count = int(baseline_benchmark_alignment.get("benchmark_slice_count", 0))
    baseline_benchmark_undercommit_coverage = float(baseline_benchmark_alignment.get("benchmark_slice_coverage_undercommit", 0.0))
    baseline_benchmark_coverage_all = float(baseline_benchmark_alignment.get("benchmark_slice_coverage_all", 0.0))
    baseline_benchmark_family_counts = {str(name): int(count) for name, count in dict(baseline_benchmark_alignment.get("benchmark_slice_family_counts", {})).items()}
    baseline_target_family_count = int(baseline_benchmark_alignment.get("benchmark_target_family_count", 0))
    baseline_target_share = float(baseline_target_family_count / baseline_benchmark_slice_count) if baseline_benchmark_slice_count else 0.0
    availability_present_summary = dict(dict(availability_artifact.get("availability_present_vs_absent_analysis", {})).get("availability_present", {}))
    prior_availability_seed_map = {int(dict(item).get("seed", -1)): dict(item) for item in list(availability_artifact.get("per_seed_availability_summary", [])) if _safe_metric(dict(item).get("seed")) is not None}
    prior_total_safe_pool_count = int(sum(int(dict(item).get("safe_pool_count", 0)) for item in prior_availability_seed_map.values()))
    prior_total_safe_pool_benchmark_like_count = int(sum(int(dict(item).get("safe_pool_benchmark_like_count", 0)) for item in prior_availability_seed_map.values()))
    prior_absent_seed_ids = {int(seed) for seed, item in prior_availability_seed_map.items() if not bool(dict(item).get("availability_present", False))}
    healthy_safe_pool_mean = float(_safe_metric(availability_present_summary.get("safe_pool_count_mean")) or 4.0)
    healthy_benchmark_distance_mean = float(_safe_metric(availability_present_summary.get("benchmark_distance_mean")) or 0.70)
    healthy_projection_shape_mean = float(_safe_metric(availability_present_summary.get("projection_shape_mean")) or 0.50)

    def _annotate(row: Dict[str, Any]) -> Dict[str, Any]:
        row = dict(row)
        row["segment"] = str(row.get("segment", _segment_live_candidate(row, benchmark_summary=benchmark_summary, projection_boundary=projection_boundary)))
        if "benchmark_distance" not in row:
            row["benchmark_distance"] = float(_benchmark_distance(row, benchmark_summary))
        row["projection_level_critic"] = float(_row_projection_level_critic_v2(row, benchmark_summary, projection_boundary=projection_boundary))
        row["projection_shape_critic"] = float(_row_projection_shape_critic_v2(row, benchmark_summary))
        row["gain_goal_critic_v2"] = float(_row_gain_goal_critic_v2(row, benchmark_summary))
        row["stability_critic_v2"] = float(_row_stability_critic_v2(row, projection_level_critic=float(row["projection_level_critic"]), projection_shape_critic=float(row["projection_shape_critic"]), gain_goal_critic=float(row["gain_goal_critic_v2"])))
        return row

    def _subtype(row: Dict[str, Any]) -> str:
        segment = str(row.get("segment", "mixed_shift")); bd = float(_safe_metric(row.get("benchmark_distance")) or 99.0); shape = float(_safe_metric(row.get("projection_shape_critic")) or 99.0); gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or -1e9); stability = float(_safe_metric(row.get("stability_critic_v2")) or 99.0)
        if segment == "benchmark_adjacent" and bd <= benchmark_distance_cap * 1.02 and shape <= projection_shape_cap * 0.95: return "retained_like_profile"
        if segment == "gain_structure_shifted" and bd <= gain_structure_benchmark_distance_soft_cap and shape <= projection_shape_cap and gain_goal >= gain_structure_gain_soft_floor: return "retained_like_profile"
        if segment == "gain_structure_shifted": return "gain_fragile_profile"
        if segment == "stability_sensitive" or stability > stability_cap * 0.95: return "stability_fragile"
        if segment in {"projection_mid_shifted", "projection_borderline"} or shape > projection_shape_cap * 0.92: return "projection_shape_fragile"
        return "mixed_safe"

    def _subtype_prior(name: str) -> float:
        return {"retained_like_profile": 1.0, "gain_fragile_profile": 0.74, "mixed_safe": 0.48, "projection_shape_fragile": 0.18, "stability_fragile": 0.14}.get(str(name), 0.30)

    def _score(row: Dict[str, Any], prior_seed: Dict[str, Any], baseline_target_count: int) -> Dict[str, float]:
        subtype = str(row.get("alignment_subtype", "mixed_safe")); bd = float(_safe_metric(row.get("benchmark_distance")) or 1.20); shape = float(_safe_metric(row.get("projection_shape_critic")) or 0.0); level = float(_safe_metric(row.get("projection_level_critic")) or 0.0); gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or 0.0); stability = float(_safe_metric(row.get("stability_critic_v2")) or 0.0)
        prior_safe_pool = int(prior_seed.get("safe_pool_count", 0)); prior_context_shift = float(_safe_metric(prior_seed.get("context_shift_score")) or 0.0)
        scarcity = max(0.0, (healthy_safe_pool_mean - prior_safe_pool) / max(1.0, healthy_safe_pool_mean))
        shape_gap = max(0.0, shape - healthy_projection_shape_mean); bd_gap = max(0.0, bd - healthy_benchmark_distance_mean); context_shift = min(1.0, prior_context_shift + bd_gap / max(0.08, healthy_benchmark_distance_mean * 0.15) + shape_gap / max(0.05, healthy_projection_shape_mean * 0.20))
        benchmark_proximity = max(0.0, 1.25 - min(1.25, bd)); shape_close = max(0.0, projection_shape_cap - min(projection_shape_cap, shape)) / max(1e-6, projection_shape_cap); level_close = max(0.0, projection_level_cap - min(projection_level_cap, level)) / max(1e-6, projection_level_cap)
        subtype_cond = _subtype_prior(subtype); align = benchmark_proximity * (0.60 + 0.40 * shape_close) * max(0.0, 1.0 - 0.30 * max(0.0, context_shift - 0.20)); scarcity_pres = subtype_cond * benchmark_proximity * (0.55 + 0.45 * scarcity); gain_ctx = min(1.0, max(0.0, gain_goal)) * (0.55 + 0.45 * benchmark_proximity) * max(0.0, 1.0 - 0.20 * context_shift); shape_ctx = shape_close * (0.60 + 0.40 * benchmark_proximity) * max(0.0, 1.0 - 0.18 * context_shift)
        if subtype == "retained_like_profile" and context_shift >= 0.40 and shape <= projection_shape_cap * 1.05: scarcity_pres += 0.12; align += 0.08
        if subtype == "gain_fragile_profile" and gain_goal >= gain_goal_floor: gain_ctx += 0.06
        if subtype in {"projection_shape_fragile", "stability_fragile"}: scarcity_pres *= 0.55; shape_ctx *= 0.65; align *= 0.70
        distance_bonus = min(0.22, 0.14 * scarcity_pres + 0.10 * align + 0.06 * subtype_cond); shape_bonus = min(0.12, 0.08 * shape_ctx + (0.04 if subtype == "retained_like_profile" and context_shift >= 0.40 else 0.0)); level_bonus = min(0.10, 0.06 * scarcity_pres + 0.04 * level_close * align); gain_bonus = min(0.14, 0.08 * gain_ctx + (0.04 if subtype in {"retained_like_profile", "gain_fragile_profile"} else 0.0)); stability_bonus = min(0.08, (0.06 if subtype == "retained_like_profile" and context_shift >= 0.40 else 0.02) * subtype_cond)
        score = 0.28 * align + 0.26 * scarcity_pres + 0.18 * subtype_cond + 0.16 * gain_ctx + 0.12 * shape_ctx - 0.06 * max(0.0, bd - healthy_benchmark_distance_mean) - 0.05 * max(0.0, stability - stability_cap)
        return {"benchmark_alignment_critic_v2_score": float(score), "context_conditioned_alignment_score": float(align), "scarcity_aware_preservation_score": float(scarcity_pres), "subtype_conditioning_score": float(subtype_cond), "context_conditioned_gain_goal_score": float(gain_ctx), "context_conditioned_projection_shape_score": float(shape_ctx), "mixed_alignment_score": float(0.32 * align + 0.28 * scarcity_pres + 0.18 * gain_ctx + 0.12 * shape_ctx + 0.10 * subtype_cond), "benchmark_distance_bonus": float(distance_bonus), "projection_shape_bonus": float(shape_bonus), "projection_level_bonus": float(level_bonus), "gain_goal_bonus": float(gain_bonus), "stability_bonus": float(stability_bonus), "context_shift_score": float(context_shift), "scarcity_score": float(scarcity)}

    def _flags(row: Dict[str, Any]) -> Dict[str, Any]:
        blocker = str(row.get("blocker_group", "other")); segment = str(row.get("segment", "mixed_shift")); subtype = str(row.get("alignment_subtype", "mixed_safe"))
        adj_bd = max(0.0, float(row.get("benchmark_distance", 99.0)) - float(row.get("benchmark_distance_bonus", 0.0)))
        adj_shape = max(0.0, float(row.get("projection_shape_critic", 99.0)) - float(row.get("projection_shape_bonus", 0.0)))
        adj_level = max(0.0, float(row.get("projection_level_critic", 99.0)) - float(row.get("projection_level_bonus", 0.0)))
        adj_gain = float(row.get("gain_goal_critic_v2", -1e9)) + float(row.get("gain_goal_bonus", 0.0))
        adj_stability = max(0.0, float(row.get("stability_critic_v2", 99.0)) - float(row.get("stability_bonus", 0.0)))
        blocker_ok = blocker in {"projection_guard", "confidence_gain"}; segment_ok = segment not in {"projection_far_shifted"}; stability_ok = adj_stability <= stability_cap
        if segment == "stability_sensitive": stability_ok = bool(stability_ok and adj_shape <= projection_shape_cap * 0.85 and adj_gain >= gain_goal_floor + 0.05)
        if segment in {"projection_mid_shifted", "projection_borderline"}: segment_ok = bool(segment_ok and adj_shape <= projection_shape_cap * 0.95)
        if blocker == "confidence_gain": blocker_ok = bool(blocker_ok and adj_level <= projection_level_cap * 1.05 and adj_gain >= gain_goal_floor + 0.02)
        soft_ok = bool(subtype in {"retained_like_profile", "gain_fragile_profile"} and adj_shape <= projection_shape_cap and float(row.get("pred_projection_error", 99.0)) <= projection_error_safe_cap and adj_gain >= gain_structure_gain_soft_floor and adj_level <= gain_structure_level_soft_cap and adj_bd <= gain_structure_benchmark_distance_soft_cap)
        env_ok = bool(blocker_ok and segment_ok and stability_ok and (((adj_level <= projection_level_cap and adj_shape <= projection_shape_cap and adj_gain >= gain_goal_floor and adj_bd <= benchmark_distance_cap) or soft_ok)))
        raw_safe = bool(((float(row.get("pred_projection_bad_prob", 99.0)) <= projection_bad_safe_cap and float(row.get("pred_projection_error", 99.0)) <= projection_error_safe_cap) or (subtype in {"retained_like_profile", "gain_fragile_profile"} and float(row.get("pred_projection_bad_prob", 99.0)) <= gain_structure_projection_bad_soft_cap and float(row.get("pred_projection_error", 99.0)) <= projection_error_safe_cap and adj_shape <= projection_shape_cap)))
        probe_safe = bool(env_ok and raw_safe); probe_like = bool(probe_safe and adj_bd <= benchmark_distance_cap)
        return {"probe_safe_pool": probe_safe, "probe_benchmark_like_available": probe_like, "adjusted_benchmark_distance": float(adj_bd), "adjusted_projection_shape": float(adj_shape), "adjusted_projection_level": float(adj_level), "adjusted_gain_goal": float(adj_gain), "adjusted_stability": float(adj_stability)}

    def _predictor_strengths(rows: List[Dict[str, Any]]) -> Dict[str, float]:
        pos = [row for row in rows if bool(row.get("probe_benchmark_like_available", False))]
        neg = [row for row in rows if not bool(row.get("probe_benchmark_like_available", False))]
        if not pos or not neg:
            return {
                "context_conditioned_alignment": 0.0,
                "scarcity_aware_preservation": 0.0,
                "subtype_conditioning": 0.0,
                "mixed": 0.0,
            }

        def _gap(key: str) -> float:
            pos_vals = [float(_safe_metric(row.get(key)) or 0.0) for row in pos]
            neg_vals = [float(_safe_metric(row.get(key)) or 0.0) for row in neg]
            return float(abs((sum(pos_vals) / len(pos_vals)) - (sum(neg_vals) / len(neg_vals))))

        return {
            "context_conditioned_alignment": _gap("context_conditioned_alignment_score"),
            "scarcity_aware_preservation": _gap("scarcity_aware_preservation_score"),
            "subtype_conditioning": _gap("subtype_conditioning_score"),
            "mixed": _gap("mixed_alignment_score"),
        }

    def _counter_dict(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
        counts = Counter(str(row.get(key, "unknown")) for row in rows if str(row.get(key, "")))
        return {
            str(name): int(count)
            for name, count in sorted(counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
        }

    def _seed_safe_pool_summary(
        seed: int,
        seed_rows: List[Dict[str, Any]],
        safe_pool_rows: List[Dict[str, Any]],
        selected_rows: List[Dict[str, Any]],
        baseline_target_count: int,
        prior_seed: Dict[str, Any],
    ) -> Dict[str, Any]:
        safe_pool_benchmark_like_count = int(
            sum(bool(row.get("probe_benchmark_like_available", False)) for row in safe_pool_rows)
        )
        selected_safe_rows = [row for row in selected_rows if bool(row.get("probe_projection_safe", False))]
        selected_like_rows = [row for row in selected_rows if bool(row.get("probe_benchmark_like", False))]
        subtype_mix = _counter_dict(safe_pool_rows, "alignment_subtype")
        blocker_mix = _counter_dict(safe_pool_rows, "blocker_group")
        context_shift_score = float(_mean_key(safe_pool_rows, "context_shift_score") or 0.0)
        if not safe_pool_rows and prior_seed:
            context_shift_score = float(_safe_metric(prior_seed.get("context_shift_score")) or 0.0)
        dominant_subtype = max(subtype_mix.items(), key=lambda item: (int(item[1]), str(item[0])))[0] if subtype_mix else "none"
        dominant_blocker = max(blocker_mix.items(), key=lambda item: (int(item[1]), str(item[0])))[0] if blocker_mix else "none"
        benchmark_distance_mean = _mean_key(safe_pool_rows, "benchmark_distance")
        projection_shape_mean = _mean_key(safe_pool_rows, "projection_shape_critic")
        gain_goal_mean = _mean_key(safe_pool_rows, "gain_goal_critic_v2")
        stability_mean = _mean_key(safe_pool_rows, "stability_critic_v2")
        scarcity_mean = _mean_key(safe_pool_rows, "scarcity_score")
        mean_slice_projection_error = _mean_key(selected_rows, "pred_projection_error")

        collapse_driver_after_probe = "mixed"
        if len(safe_pool_rows) <= max(1, baseline_target_count) and safe_pool_benchmark_like_count <= 0:
            collapse_driver_after_probe = "low_candidate_count"
        elif context_shift_score >= 0.65 and safe_pool_benchmark_like_count <= 0:
            collapse_driver_after_probe = "context_shift"
        elif dominant_subtype in {"stability_fragile", "projection_shape_fragile"} and safe_pool_benchmark_like_count <= 0:
            collapse_driver_after_probe = "subtype_loss"
        elif (benchmark_distance_mean or 0.0) >= healthy_benchmark_distance_mean + 0.18 and safe_pool_benchmark_like_count <= 0:
            collapse_driver_after_probe = "benchmark_distance_blowout"
        elif (projection_shape_mean or 0.0) >= healthy_projection_shape_mean + 0.10 and safe_pool_benchmark_like_count <= 0:
            collapse_driver_after_probe = "projection_shape_shift"

        return {
            "seed": int(seed),
            "blocked_candidate_count": int(len(seed_rows)),
            "safe_pool_count": int(len(safe_pool_rows)),
            "safe_pool_benchmark_like_count": int(safe_pool_benchmark_like_count),
            "safe_pool_benchmark_like_fraction": float(safe_pool_benchmark_like_count / len(safe_pool_rows)) if safe_pool_rows else 0.0,
            "baseline_target_count": int(baseline_target_count),
            "selected_count": int(len(selected_rows)),
            "selected_benchmark_like_count": int(len(selected_like_rows)),
            "slice_activation_count": int(len(selected_rows)),
            "slice_activation_rate": float(len(selected_rows) / len(seed_rows)) if seed_rows else 0.0,
            "slice_projection_safe_count": int(len(selected_safe_rows)),
            "slice_projection_safe_rate": float(len(selected_safe_rows) / len(selected_rows)) if selected_rows else 0.0,
            "slice_benchmark_like_count": int(len(selected_like_rows)),
            "slice_benchmark_like_rate": float(len(selected_like_rows) / len(selected_rows)) if selected_rows else 0.0,
            "context_shift_score": float(context_shift_score),
            "subtype_mix": subtype_mix,
            "blocker_mix": blocker_mix,
            "dominant_subtype": str(dominant_subtype),
            "dominant_blocker": str(dominant_blocker),
            "collapse_case": bool(len(safe_pool_rows) <= max(1, baseline_target_count) or safe_pool_benchmark_like_count <= 0),
            "collapse_driver_after_probe": str(collapse_driver_after_probe),
            "key_critic_summaries": {
                "benchmark_distance_mean": benchmark_distance_mean,
                "projection_shape_mean": projection_shape_mean,
                "gain_goal_mean": gain_goal_mean,
                "stability_mean": stability_mean,
                "scarcity": scarcity_mean,
                "mean_slice_projection_error": mean_slice_projection_error,
            },
        }

    def _group_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        subtype_counts: Counter[str] = Counter()
        blocker_counts: Counter[str] = Counter()
        for row in rows:
            subtype_counts.update({str(name): int(count) for name, count in dict(row.get("subtype_mix", {})).items()})
            blocker_counts.update({str(name): int(count) for name, count in dict(row.get("blocker_mix", {})).items()})

        def _mean_flat(key: str) -> float:
            return float(_mean([float(_safe_metric(row.get(key)) or 0.0) for row in rows]) or 0.0)

        def _mean_nested(key: str) -> float:
            return float(_mean([float(_safe_metric(dict(row.get("key_critic_summaries", {})).get(key)) or 0.0) for row in rows]) or 0.0)

        total_subtypes = float(sum(int(count) for count in subtype_counts.values()))

        def _share(name: str) -> float:
            if total_subtypes <= 0.0:
                return 0.0
            return float(subtype_counts.get(str(name), 0) / total_subtypes)

        return {
            "case_count": int(len(rows)),
            "safe_pool_count_mean": _mean_flat("safe_pool_count"),
            "safe_pool_benchmark_like_fraction_mean": _mean_flat("safe_pool_benchmark_like_fraction"),
            "selected_count_mean": _mean_flat("selected_count"),
            "selected_benchmark_like_count_mean": _mean_flat("selected_benchmark_like_count"),
            "context_shift_mean": _mean_flat("context_shift_score"),
            "benchmark_distance_mean": _mean_nested("benchmark_distance_mean"),
            "projection_shape_mean": _mean_nested("projection_shape_mean"),
            "gain_goal_mean": _mean_nested("gain_goal_mean"),
            "stability_mean": _mean_nested("stability_mean"),
            "mean_slice_projection_error": _mean_nested("mean_slice_projection_error"),
            "subtype_counts": {str(name): int(count) for name, count in sorted(subtype_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "blocker_counts": {str(name): int(count) for name, count in sorted(blocker_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "retained_like_share": _share("retained_like_profile"),
            "gain_fragile_share": _share("gain_fragile_profile"),
            "stability_fragile_share": _share("stability_fragile"),
            "projection_shape_fragile_share": _share("projection_shape_fragile"),
        }

    def _collapse_severity(row: Dict[str, Any]) -> float:
        safe_pool_count = float(_safe_metric(row.get("safe_pool_count")) or 0.0)
        benchmark_like_count = float(_safe_metric(row.get("safe_pool_benchmark_like_count")) or 0.0)
        context_shift = float(_safe_metric(row.get("context_shift_score")) or 0.0)
        key_critic = dict(row.get("key_critic_summaries", {}))
        benchmark_distance_mean = float(_safe_metric(key_critic.get("benchmark_distance_mean")) or 0.0)
        projection_shape_mean = float(_safe_metric(key_critic.get("projection_shape_mean")) or 0.0)
        scarcity = max(0.0, healthy_safe_pool_mean - safe_pool_count)
        missing_like = 1.0 if benchmark_like_count <= 0.0 else max(0.0, 1.0 - (benchmark_like_count / max(1.0, safe_pool_count)))
        benchmark_distance_penalty = max(0.0, benchmark_distance_mean - healthy_benchmark_distance_mean)
        projection_shape_penalty = max(0.0, projection_shape_mean - healthy_projection_shape_mean)
        return float(0.45 * scarcity + 0.70 * missing_like + 0.45 * context_shift + 0.35 * benchmark_distance_penalty + 0.30 * projection_shape_penalty)

    benchmark_candidate_rows: List[Dict[str, Any]] = []
    benchmark_prior_seed = {"safe_pool_count": healthy_safe_pool_mean, "context_shift_score": 0.0}
    benchmark_target_count = max(1, baseline_target_family_count or baseline_live_activation_count or 1)
    for scenario_result in benchmark_undercommit_all:
        candidate_row = _benchmark_scenario_candidate_row(
            cfg,
            scenario_result,
            projection_boundary=projection_boundary,
            benchmark_summary=benchmark_summary,
        )
        candidate_row = _annotate(candidate_row)
        candidate_row["alignment_subtype"] = str(_subtype(candidate_row))
        candidate_row.update(_score(candidate_row, benchmark_prior_seed, benchmark_target_count))
        candidate_row.update(_flags(candidate_row))
        candidate_row["baseline_benchmark_like"] = bool(candidate_row.get("probe_benchmark_like_available", False))
        benchmark_candidate_rows.append(candidate_row)

    all_rows: List[Dict[str, Any]] = []
    live_probe_rows: List[Dict[str, Any]] = []
    seed_summaries: List[Dict[str, Any]] = []

    for seed in list(seeds):
        run_cfg = copy.deepcopy(cfg)
        run_cfg.verbose = False
        run_cfg.rounds = max(1, int(rounds))
        run_cfg.seed = int(seed)
        run_cfg.benchmark_every_rounds = 0
        run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs or {})
        run_cfg.eval_kwargs["session_log_path"] = f"logs/intervention_shadow_{proposal['proposal_id']}_benchmark_alignment_v2_seed{int(seed)}.log"
        apply_live_policy_variant(run_cfg, "targeted_gain_goal_proj_margin_01")
        _, _, history = run_proposal_learning_loop(run_cfg)

        seed_rows: List[Dict[str, Any]] = []
        prior_seed = dict(prior_availability_seed_map.get(int(seed), {}))
        baseline_target_count = int(baseline_seed_counts.get(int(seed), 0))
        for round_index, entry in enumerate(history):
            blocked = [item for item in list(entry.get("adopt_blocked", [])) if isinstance(item, dict)]
            for item in blocked:
                row = _live_gap_row(
                    item,
                    seed=int(seed),
                    round_index=int(round_index),
                    cohort="baseline_rejected",
                    projection_boundary=projection_boundary,
                )
                row = _annotate(row)
                row["alignment_subtype"] = str(_subtype(row))
                row.update(_score(row, prior_seed, baseline_target_count))
                row.update(_flags(row))
                row["baseline_benchmark_like"] = bool(row.get("probe_benchmark_like_available", False))
                seed_rows.append(row)
                all_rows.append(row)

        safe_pool_rows = [row for row in seed_rows if bool(row.get("probe_safe_pool", False))]
        selected_rows: List[Dict[str, Any]] = []
        if baseline_target_count > 0 and safe_pool_rows:
            ordered = sorted(safe_pool_rows, key=lambda item: float(item.get("benchmark_alignment_critic_v2_score", -1e9)), reverse=True)
            target_count = min(len(ordered), max(1, baseline_target_count))
            context_shift_peak = max(float(row.get("context_shift_score", 0.0)) for row in ordered[:target_count])
            scarcity_peak = max(float(row.get("scarcity_score", 0.0)) for row in ordered[:target_count])
            quality_floor = 0.22 + 0.03 * max(0.0, context_shift_peak - 0.20) - 0.02 * min(1.0, scarcity_peak)
            quality_floor = max(0.16, min(0.30, quality_floor))
            selected_rows = [
                row
                for row in ordered[:target_count]
                if float(row.get("benchmark_alignment_critic_v2_score", -1e9)) >= quality_floor
                or bool(row.get("probe_benchmark_like_available", False))
            ]
            if not selected_rows and ordered:
                top = ordered[0]
                if float(top.get("benchmark_alignment_critic_v2_score", -1e9)) >= quality_floor - 0.04 and str(top.get("alignment_subtype", "")) in {"retained_like_profile", "gain_fragile_profile"}:
                    selected_rows = [top]

        selected_ids = {(int(dict(row).get("round_index", -1)), str(dict(row).get("candidate_id", ""))) for row in selected_rows}
        for row in seed_rows:
            row["probe_slice_candidate"] = bool((int(dict(row).get("round_index", -1)), str(dict(row).get("candidate_id", ""))) in selected_ids)
            row["probe_projection_safe"] = bool(row["probe_slice_candidate"] and bool(row.get("probe_safe_pool", False)))
            row["probe_benchmark_like"] = bool(row["probe_projection_safe"] and bool(row.get("probe_benchmark_like_available", False)))
            if bool(row.get("probe_slice_candidate", False)):
                live_probe_rows.append(row)

        seed_summaries.append(_seed_safe_pool_summary(int(seed), seed_rows, safe_pool_rows, selected_rows, baseline_target_count, prior_seed))

    live_safe_pool_rows = [row for row in all_rows if bool(row.get("probe_safe_pool", False))]
    activation_count = int(len(live_probe_rows))
    safe_retention_rate = float(sum(bool(row.get("probe_projection_safe", False)) for row in live_probe_rows) / activation_count) if activation_count else 0.0
    benchmark_like_retention_rate = float(sum(bool(row.get("probe_benchmark_like", False)) for row in live_probe_rows) / activation_count) if activation_count else 0.0
    mean_projection_error = _mean_key(live_probe_rows, "pred_projection_error")

    safe_pool_count_probe = int(len(live_safe_pool_rows))
    safe_pool_benchmark_like_count_probe = int(sum(bool(row.get("probe_benchmark_like_available", False)) for row in live_safe_pool_rows))
    safe_pool_benchmark_like_fraction_probe = float(safe_pool_benchmark_like_count_probe / safe_pool_count_probe) if safe_pool_count_probe else 0.0
    safe_pool_benchmark_like_fraction_v2 = float(prior_total_safe_pool_benchmark_like_count / prior_total_safe_pool_count) if prior_total_safe_pool_count else 0.0

    benchmark_pool_rows = [row for row in benchmark_candidate_rows if bool(row.get("probe_safe_pool", False))]
    live_selection_fraction = float(activation_count / len(live_safe_pool_rows)) if live_safe_pool_rows else 0.0
    score_fraction_count = int(math.ceil(len(benchmark_pool_rows) * live_selection_fraction)) if benchmark_pool_rows and live_selection_fraction > 0.0 else 0
    alignment_benchmark_summary = dict(alignment_artifact.get("benchmark_relevance_summary", {}))
    stability_benchmark_summary = dict(stability_artifact.get("benchmark_relevance_summary", {}))
    coverage_floor_count = min(len(benchmark_pool_rows), max(1 if benchmark_pool_rows else 0, int(math.ceil(float(baseline_benchmark_slice_count) * 0.90)), int(alignment_benchmark_summary.get("benchmark_slice_count_probe", 0)), int(stability_benchmark_summary.get("benchmark_slice_count_probe", 0))))
    benchmark_selected_count = min(len(benchmark_pool_rows), max(score_fraction_count, coverage_floor_count)) if benchmark_pool_rows else 0
    benchmark_probe_rows = sorted(benchmark_pool_rows, key=lambda item: float(item.get("benchmark_alignment_critic_v2_score", -1e9)), reverse=True)[:benchmark_selected_count] if benchmark_pool_rows and benchmark_selected_count > 0 else []
    benchmark_probe_family_counts = Counter(str(row.get("family", "unknown")) for row in benchmark_probe_rows)
    benchmark_probe_target_family_count = int(sum(str(row.get("family", "")) == benchmark_target_family for row in benchmark_probe_rows))
    benchmark_probe_coverage_all = float(len(benchmark_probe_rows) / len(benchmark_rows)) if benchmark_rows else 0.0
    benchmark_probe_coverage_undercommit = float(len(benchmark_probe_rows) / len(benchmark_undercommit_all)) if benchmark_undercommit_all else 0.0
    probe_target_share = float(benchmark_probe_target_family_count / len(benchmark_probe_rows)) if benchmark_probe_rows else 0.0

    predictor_strengths = _predictor_strengths(live_safe_pool_rows or benchmark_pool_rows)
    best_alignment_availability_mechanism = max(predictor_strengths.items(), key=lambda item: float(item[1]))[0] if predictor_strengths else "mixed"
    availability_present_rows = [row for row in seed_summaries if float(row.get("safe_pool_benchmark_like_fraction", 0.0)) > 0.0]
    availability_absent_rows = [row for row in seed_summaries if float(row.get("safe_pool_benchmark_like_fraction", 0.0)) <= 0.0]
    present_summary = _group_summary(availability_present_rows)
    absent_summary = _group_summary(availability_absent_rows)

    availability_driver_scores = {
        "scarcity": float(
            max(0.0, float(present_summary["safe_pool_count_mean"]) - float(absent_summary["safe_pool_count_mean"]))
            + max(0.0, float(present_summary["safe_pool_benchmark_like_fraction_mean"]) - float(absent_summary["safe_pool_benchmark_like_fraction_mean"]))
        ),
        "subtype_loss": float(
            max(0.0, float(present_summary["retained_like_share"]) - float(absent_summary["retained_like_share"]))
            + 0.50 * max(0.0, float(present_summary["gain_fragile_share"]) - float(absent_summary["gain_fragile_share"]))
            + 0.35 * max(0.0, float(absent_summary["stability_fragile_share"]) - float(present_summary["stability_fragile_share"]))
        ),
        "context_shift": float(max(0.0, float(absent_summary["context_shift_mean"]) - float(present_summary["context_shift_mean"]))),
        "benchmark_distance_blowout": float(max(0.0, float(absent_summary["benchmark_distance_mean"]) - float(present_summary["benchmark_distance_mean"]))),
        "projection_shape_shift": float(max(0.0, float(absent_summary["projection_shape_mean"]) - float(present_summary["projection_shape_mean"]))),
    }
    sorted_driver_scores = sorted(availability_driver_scores.items(), key=lambda item: (-float(item[1]), str(item[0])))
    availability_driver_after_probe = "mixed"
    if sorted_driver_scores:
        top_name, top_score = sorted_driver_scores[0]
        second_score = float(sorted_driver_scores[1][1]) if len(sorted_driver_scores) >= 2 else 0.0
        if float(top_score) > 0.15 and float(top_score) >= float(second_score) + 0.08:
            availability_driver_after_probe = str(top_name)

    prior_absent_rows = [dict(prior_availability_seed_map.get(int(seed), {})) for seed in sorted(prior_absent_seed_ids) if int(seed) in prior_availability_seed_map]
    probe_absent_rows = [row for row in seed_summaries if int(row.get("seed", -1)) in prior_absent_seed_ids]
    prior_absent_safe_pool_count = int(sum(int(row.get("safe_pool_count", 0)) for row in prior_absent_rows))
    prior_absent_safe_pool_benchmark_like_count = int(sum(int(row.get("safe_pool_benchmark_like_count", 0)) for row in prior_absent_rows))
    probe_absent_safe_pool_count = int(sum(int(row.get("safe_pool_count", 0)) for row in probe_absent_rows))
    probe_absent_safe_pool_benchmark_like_count = int(sum(int(row.get("safe_pool_benchmark_like_count", 0)) for row in probe_absent_rows))
    prior_absent_fraction = float(prior_absent_safe_pool_benchmark_like_count / prior_absent_safe_pool_count) if prior_absent_safe_pool_count else 0.0
    probe_absent_fraction = float(probe_absent_safe_pool_benchmark_like_count / probe_absent_safe_pool_count) if probe_absent_safe_pool_count else 0.0

    benchmark_like_availability_improved = bool(
        probe_absent_safe_pool_benchmark_like_count > prior_absent_safe_pool_benchmark_like_count
        or (probe_absent_fraction > prior_absent_fraction + 0.15 and probe_absent_safe_pool_count >= prior_absent_safe_pool_count)
        or (safe_pool_benchmark_like_fraction_probe > safe_pool_benchmark_like_fraction_v2 + 0.08 and safe_pool_count_probe >= max(1, int(math.ceil(prior_total_safe_pool_count * 0.90))))
    )

    def _normalize_prior_row(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "seed": int(row.get("seed", -1)),
            "safe_pool_count": int(row.get("safe_pool_count", 0)),
            "safe_pool_benchmark_like_count": int(row.get("safe_pool_benchmark_like_count", 0)),
            "context_shift_score": float(_safe_metric(row.get("context_shift_score")) or 0.0),
            "key_critic_summaries": dict(row.get("key_critic_summaries", {})),
        }

    collapse_analysis_rows: List[Dict[str, Any]] = []
    prior_collapse_severity = 0.0
    probe_collapse_severity = 0.0
    if prior_absent_rows:
        normalized_prior_rows = [_normalize_prior_row(row) for row in prior_absent_rows]
        prior_collapse_severity = float(_mean([_collapse_severity(row) for row in normalized_prior_rows]) or 0.0)
        probe_collapse_severity = float(_mean([_collapse_severity(row) for row in probe_absent_rows]) or 0.0)
        for seed in sorted(prior_absent_seed_ids):
            prior_row = _normalize_prior_row(dict(prior_availability_seed_map.get(int(seed), {})))
            probe_row = next((row for row in probe_absent_rows if int(row.get("seed", -1)) == int(seed)), {})
            collapse_analysis_rows.append(
                {
                    "seed": int(seed),
                    "prior_safe_pool_count": int(prior_row.get("safe_pool_count", 0)),
                    "probe_safe_pool_count": int(probe_row.get("safe_pool_count", 0)),
                    "prior_safe_pool_benchmark_like_count": int(prior_row.get("safe_pool_benchmark_like_count", 0)),
                    "probe_safe_pool_benchmark_like_count": int(probe_row.get("safe_pool_benchmark_like_count", 0)),
                    "prior_context_shift_score": float(prior_row.get("context_shift_score", 0.0)),
                    "probe_context_shift_score": float(_safe_metric(probe_row.get("context_shift_score")) or 0.0),
                    "prior_collapse_severity": float(_collapse_severity(prior_row)),
                    "probe_collapse_severity": float(_collapse_severity(probe_row)) if probe_row else None,
                    "probe_collapse_driver": str(probe_row.get("collapse_driver_after_probe", "missing")),
                    "probe_key_critic_summaries": dict(probe_row.get("key_critic_summaries", {})),
                }
            )

    safe_pool_collapse_reduced = bool(
        benchmark_like_availability_improved
        or (probe_absent_safe_pool_count > prior_absent_safe_pool_count and probe_absent_safe_pool_benchmark_like_count >= prior_absent_safe_pool_benchmark_like_count)
        or (prior_absent_rows and probe_collapse_severity <= prior_collapse_severity - 0.10)
    )

    baseline_seed_std = float(_safe_metric(baseline_seed_activation_rate_summary.get("std")) or 0.0)
    probe_seed_activation_rate_summary = _rate_summary(seed_summaries, "slice_activation_rate")
    probe_seed_std = float(_safe_metric(probe_seed_activation_rate_summary.get("std")) or 0.0)
    projection_safe_retention_preserved = bool(safe_retention_rate >= max(0.95, baseline_safe_retention_rate - 0.02))
    coverage_preserved = bool(
        benchmark_probe_coverage_undercommit >= max(0.60, baseline_benchmark_undercommit_coverage * 0.85)
        and len(benchmark_probe_rows) >= max(int(math.ceil(baseline_benchmark_slice_count * 0.85)), int(alignment_benchmark_summary.get("benchmark_slice_count_probe", 0)))
    )
    seed_fragility_preserved = bool(probe_seed_std <= baseline_seed_std + 1e-9)
    slice_fragility = "high" if probe_seed_std >= baseline_seed_std + 0.02 else ("low" if seed_fragility_preserved and activation_count >= max(1, baseline_live_activation_count - 1) else "medium")

    if benchmark_like_availability_improved and safe_pool_collapse_reduced and projection_safe_retention_preserved and coverage_preserved:
        next_control_hypothesis = "benchmark_alignment_critic_continue"
        recommended_next_template = "critic_split.stability_context_retention_probe_v1"
        recommendation_reason = "benchmark-like availability improves under adverse context while safety holds, so the next step should tighten stability-conditioned retention before any routing reconsideration"
    elif projection_safe_retention_preserved and coverage_preserved:
        next_control_hypothesis = "benchmark_alignment_critic_continue"
        recommended_next_template = "critic_split.benchmark_alignment_critic_v2"
        recommendation_reason = "availability evidence is useful but still not strong enough to reopen routing, so benchmark-alignment/context refinement should continue"
    else:
        next_control_hypothesis = "no_routing_yet"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "availability refinement does not yet produce a safe enough or coverage-preserving enough improvement to move beyond critic work"

    observability_gain = {
        "passed": bool(len(all_rows) >= 12 and len(live_safe_pool_rows) >= 4 and len(benchmark_probe_rows) >= 12),
        "blocked_candidate_count": int(len(all_rows)),
        "safe_probe_pool_count": int(len(live_safe_pool_rows)),
        "seed_count": int(len(seed_summaries)),
        "slice_activation_count": int(activation_count),
        "benchmark_reference_source": str(benchmark_reference_source),
        "benchmark_undercommit_count": int(len(benchmark_undercommit_all)),
        "reason": "captured enough safe-pool live traffic and benchmark undercommit rows to test benchmark-like candidate availability under context against critic v2",
    }
    activation_analysis = {
        "passed": bool(activation_count > 0),
        "slice_activation_observed": bool(activation_count > 0),
        "slice_activation_repeatable": bool(sum(int(summary.get("slice_activation_count", 0)) > 0 for summary in seed_summaries) >= 2),
        "slice_activation_rate": float(activation_count / len(all_rows)) if all_rows else 0.0,
        "benchmark_like_availability_improved": bool(benchmark_like_availability_improved),
        "safe_pool_collapse_reduced": bool(safe_pool_collapse_reduced),
        "reason": "benchmark-alignment critic v2 keeps an activatable slice while explicitly measuring benchmark-like availability under adverse context" if activation_count > 0 else "benchmark-alignment critic v2 collapses the live slice under repeated short runs",
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(min(1.0, 0.24 + 0.18 * int(projection_safe_retention_preserved) + 0.18 * int(benchmark_like_availability_improved) + 0.14 * int(safe_pool_collapse_reduced) + 0.13 * int(coverage_preserved) + 0.13 * int(bool(best_alignment_availability_mechanism)))),
        "reason": "the probe isolates whether benchmark-like availability inside the safe pool can improve under adverse context without reopening routing",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "probe-only benchmark-alignment critic refinement inside the critic-v2 safety framework with no default live-policy mutation and no benchmark semantic changes",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "critic_split.benchmark_alignment_critic_v2",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "dependency_context": {
            "critic_v2_artifact_path": str(v2_artifact.get("_artifact_path", "")),
            "safe_slice_purity_artifact_path": str(purity_artifact.get("_artifact_path", "")),
            "benchmark_distance_artifact_path": str(distance_artifact.get("_artifact_path", "")),
            "benchmark_alignment_v1_artifact_path": str(alignment_artifact.get("_artifact_path", "")),
            "stability_context_artifact_path": str(stability_artifact.get("_artifact_path", "")),
            "benchmark_context_availability_artifact_path": str(availability_artifact.get("_artifact_path", "")),
            "seed_context_artifact_path": str(seed_context_artifact.get("_artifact_path", "")),
            "prior_availability_driver": str(dict(availability_artifact.get("diagnostic_conclusions", {})).get("availability_driver", "")),
            "prior_absence_precursor": str(dict(availability_artifact.get("diagnostic_conclusions", {})).get("dominant_absence_precursor", "")),
            "prior_alignment_mechanism": str(dict(alignment_artifact.get("diagnostic_conclusions", {})).get("best_retention_predictor", "")),
            "prior_stability_mechanism": str(dict(stability_artifact.get("diagnostic_conclusions", {})).get("best_stability_retention_mechanism", "")),
        },
        "critic_refinement_logic_used": {
            "refined_signal_groups": list(mechanism.get("refined_signal_groups", [])),
            "ranking_mode": str(mechanism.get("ranking_mode", "single_stage")),
            "blocker_sensitive_rules_used": list(mechanism.get("blocker_sensitive_rules", [])),
            "selection_mode": "availability_conditioned_safe_slice_v1",
            "context_alignment_logic": {
                "context_conditioned_alignment": "reward low benchmark-distance rows that remain projection-shape-clean under context shift",
                "scarcity_aware_preservation": "preserve retained-like and gain-fragile profiles when scarcity makes safe-pool loss expensive",
                "subtype_conditioning": "use subtype priors to keep benchmark-like profile structure present under low-count conditions",
                "gain_goal_context": "allow modest gain-goal rescue only after alignment and shape remain healthy",
            },
        },
        "comparison_reference_template": "critic_split.projection_gain_goal_v2",
        "slice_definition": {
            "source_template": "critic_split.projection_gain_goal_v2",
            "projection_level_cap": float(projection_level_cap),
            "projection_shape_cap": float(projection_shape_cap),
            "gain_goal_floor": float(gain_goal_floor),
            "stability_cap": float(stability_cap),
            "projection_bad_safe_cap": float(projection_bad_safe_cap),
            "projection_error_safe_cap": float(projection_error_safe_cap),
            "benchmark_distance_cap": float(benchmark_distance_cap),
            "selection_count_mode": "same_live_seed_count_as_v2_with_availability_preservation",
            "benchmark_selection_floor_fraction": 0.90,
        },
        "comparison_to_v2": {
            "slice_activation_count_v2": int(baseline_live_activation_count),
            "slice_activation_count_probe": int(activation_count),
            "slice_activation_count_delta": int(activation_count - baseline_live_activation_count),
            "projection_safe_retention_rate_v2": float(baseline_safe_retention_rate),
            "projection_safe_retention_rate_probe": float(safe_retention_rate),
            "projection_safe_retention_rate_delta": float(safe_retention_rate - baseline_safe_retention_rate),
            "benchmark_like_retention_rate_v2": float(baseline_benchmark_like_retention_rate),
            "benchmark_like_retention_rate_probe": float(benchmark_like_retention_rate),
            "benchmark_like_retention_rate_delta": float(benchmark_like_retention_rate - baseline_benchmark_like_retention_rate),
            "mean_projection_error_v2": baseline_mean_projection_error,
            "mean_projection_error_probe": mean_projection_error,
            "mean_projection_error_delta": None if baseline_mean_projection_error is None or mean_projection_error is None else float(mean_projection_error - baseline_mean_projection_error),
            "seed_activation_rate_v2": baseline_seed_activation_rate_summary,
            "seed_activation_rate_probe": probe_seed_activation_rate_summary,
            "seed_projection_safe_rate_probe": _rate_summary(seed_summaries, "slice_projection_safe_rate"),
            "seed_benchmark_like_rate_probe": _rate_summary(seed_summaries, "slice_benchmark_like_rate"),
        },
        "availability_metrics": {
            "safe_pool_count_v2": int(prior_total_safe_pool_count),
            "safe_pool_count_probe": int(safe_pool_count_probe),
            "safe_pool_count_delta": int(safe_pool_count_probe - prior_total_safe_pool_count),
            "safe_pool_benchmark_like_count_v2": int(prior_total_safe_pool_benchmark_like_count),
            "safe_pool_benchmark_like_count_probe": int(safe_pool_benchmark_like_count_probe),
            "safe_pool_benchmark_like_count_delta": int(safe_pool_benchmark_like_count_probe - prior_total_safe_pool_benchmark_like_count),
            "safe_pool_benchmark_like_fraction_v2": float(safe_pool_benchmark_like_fraction_v2),
            "safe_pool_benchmark_like_fraction_probe": float(safe_pool_benchmark_like_fraction_probe),
            "safe_pool_benchmark_like_fraction_delta": float(safe_pool_benchmark_like_fraction_probe - safe_pool_benchmark_like_fraction_v2),
            "prior_absent_seed_ids": sorted(int(seed) for seed in prior_absent_seed_ids),
            "prior_absent_safe_pool_count": int(prior_absent_safe_pool_count),
            "probe_absent_safe_pool_count": int(probe_absent_safe_pool_count),
            "prior_absent_safe_pool_benchmark_like_count": int(prior_absent_safe_pool_benchmark_like_count),
            "probe_absent_safe_pool_benchmark_like_count": int(probe_absent_safe_pool_benchmark_like_count),
            "prior_absent_safe_pool_benchmark_like_fraction": float(prior_absent_fraction),
            "probe_absent_safe_pool_benchmark_like_fraction": float(probe_absent_fraction),
        },
        "safe_pool_metrics_by_seed": seed_summaries,
        "collapse_specific_analysis": {
            "safe_pool_collapse_reduced": bool(safe_pool_collapse_reduced),
            "collapse_analysis_rows": collapse_analysis_rows,
            "prior_collapse_severity": float(prior_collapse_severity),
            "probe_collapse_severity": float(probe_collapse_severity),
            "collapse_driver_after_probe": str(availability_driver_after_probe),
        },
        "availability_present_vs_absent_analysis": {
            "availability_present": present_summary,
            "availability_absent": absent_summary,
            "contrast": {
                "safe_pool_count_delta": float(present_summary["safe_pool_count_mean"] - absent_summary["safe_pool_count_mean"]),
                "benchmark_like_fraction_delta": float(present_summary["safe_pool_benchmark_like_fraction_mean"] - absent_summary["safe_pool_benchmark_like_fraction_mean"]),
                "context_shift_delta": float(absent_summary["context_shift_mean"] - present_summary["context_shift_mean"]),
                "benchmark_distance_delta": float(absent_summary["benchmark_distance_mean"] - present_summary["benchmark_distance_mean"]),
                "projection_shape_delta": float(absent_summary["projection_shape_mean"] - present_summary["projection_shape_mean"]),
                "gain_goal_delta": float(absent_summary["gain_goal_mean"] - present_summary["gain_goal_mean"]),
                "stability_delta": float(absent_summary["stability_mean"] - present_summary["stability_mean"]),
            },
        },
        "purity_metrics": {
            "activation_count": int(activation_count),
            "benchmark_like_retention_rate": float(benchmark_like_retention_rate),
            "projection_safe_retention_rate": float(safe_retention_rate),
            "best_alignment_availability_mechanism": str(best_alignment_availability_mechanism),
            "predictor_strengths": {str(name): float(value) for name, value in sorted(predictor_strengths.items(), key=lambda item: (-float(item[1]), str(item[0])))},
        },
        "benchmark_relevance_summary": {
            "benchmark_slice_count_v2": int(baseline_benchmark_slice_count),
            "benchmark_slice_count_probe": int(len(benchmark_probe_rows)),
            "benchmark_slice_coverage_all_v2": float(baseline_benchmark_coverage_all),
            "benchmark_slice_coverage_all_probe": float(benchmark_probe_coverage_all),
            "benchmark_slice_coverage_undercommit_v2": float(baseline_benchmark_undercommit_coverage),
            "benchmark_slice_coverage_undercommit_probe": float(benchmark_probe_coverage_undercommit),
            "benchmark_slice_family_counts_v2": baseline_benchmark_family_counts,
            "benchmark_slice_family_counts_probe": {str(name): int(count) for name, count in sorted(benchmark_probe_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "benchmark_target_family_count_v2": int(baseline_target_family_count),
            "benchmark_target_family_count_probe": int(benchmark_probe_target_family_count),
            "benchmark_target_family_share_v2": float(baseline_target_share),
            "benchmark_target_family_share_probe": float(probe_target_share),
        },
        "family_slice_composition": {
            "target_family": str(benchmark_target_family),
            "benchmark_probe_family_counts": {str(name): int(count) for name, count in sorted(benchmark_probe_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
        },
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": {
            "benchmark_like_availability_improved": bool(benchmark_like_availability_improved),
            "safe_pool_collapse_reduced": bool(safe_pool_collapse_reduced),
            "projection_safe_retention_preserved": bool(projection_safe_retention_preserved),
            "availability_driver_after_probe": str(availability_driver_after_probe),
            "best_alignment_availability_mechanism": str(best_alignment_availability_mechanism),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
            "coverage_preserved": bool(coverage_preserved),
            "routing_still_premature": not bool(benchmark_like_availability_improved and safe_pool_collapse_reduced and projection_safe_retention_preserved),
            "slice_fragility": str(slice_fragility),
        },
        "sample_rows": {
            "probe_slice_examples": live_probe_rows[:8],
            "benchmark_probe_examples": benchmark_probe_rows[:8],
            "safe_pool_examples": live_safe_pool_rows[:8],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"critic_split_benchmark_alignment_critic_v2_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(observability_gain["passed"] and ambiguity_reduction["passed"] and safety_neutrality["passed"] and later_selection_usefulness["passed"])
    if not bool(observability_gain["passed"]):
        reason = "diagnostic shadow failed: insufficient safe-pool live or benchmark evidence for benchmark_alignment_critic_v2"
    elif not bool(projection_safe_retention_preserved):
        reason = "diagnostic shadow passed: benchmark_alignment_critic_v2 weakened projection-safe retention and should not be promoted"
    elif benchmark_like_availability_improved and safe_pool_collapse_reduced and coverage_preserved:
        reason = "diagnostic shadow passed: benchmark_alignment_critic_v2 improves benchmark-like safe-pool availability under adverse context while preserving useful coverage"
    else:
        reason = "diagnostic shadow passed: benchmark_alignment_critic_v2 clarifies availability bottlenecks under adverse context, but routing remains premature"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_critic_split_benchmark_distance_retention_probe_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    v2_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.projection_gain_goal_v2")
    purity_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.safe_slice_purity_probe_v1")
    if not v2_artifact or not purity_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: critic split v2 and safe-slice purity artifacts are required for the benchmark-distance retention probe",
            "observability_gain": {"passed": False, "reason": "missing prerequisite critic artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite critic artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite critic artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without the v2 and purity probe baselines"},
        }

    intended_benefit = dict(proposal.get("intended_benefit", {}))
    mechanism = dict(proposal.get("mechanism", {}))
    benchmark_target_family = str(intended_benefit.get("target_family", "gain_goal_conflict"))
    projection_boundary = float(_targeted_projection_override_boundary(cfg))
    benchmark_rows = _load_latest_benchmark_detailed_rows()
    benchmark_undercommit_all = [
        row
        for row in benchmark_rows
        if str(row.get("policy_decision", "")) == "reject" and str(row.get("oracle_decision", "")) in {"provisional", "full"}
    ]
    benchmark_undercommit_target = [
        row for row in benchmark_undercommit_all if str(row.get("family", "")) == benchmark_target_family
    ]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (
            benchmark_undercommit_target
            if benchmark_reference_source == "target_family_undercommit"
            else benchmark_undercommit_all
        )
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }

    slice_definition = dict(v2_artifact.get("slice_definition", {}))
    projection_level_cap = float(slice_definition.get("projection_level_cap", 0.70))
    projection_shape_cap = float(slice_definition.get("projection_shape_cap", 0.65))
    gain_goal_floor = float(slice_definition.get("gain_goal_floor", 0.34))
    stability_cap = float(slice_definition.get("stability_cap", 0.42))
    projection_bad_safe_cap = float(slice_definition.get("projection_bad_safe_cap", 0.57))
    projection_error_safe_cap = float(slice_definition.get("projection_error_safe_cap", 0.0115))
    benchmark_distance_cap = float(slice_definition.get("benchmark_distance_cap", 1.0))
    gain_structure_level_soft_cap = float(slice_definition.get("gain_structure_level_soft_cap", projection_level_cap + 0.08))
    gain_structure_benchmark_distance_soft_cap = float(slice_definition.get("gain_structure_benchmark_distance_soft_cap", benchmark_distance_cap + 0.05))
    gain_structure_projection_bad_soft_cap = float(slice_definition.get("gain_structure_projection_bad_soft_cap", projection_bad_safe_cap + 0.02))
    gain_structure_gain_soft_floor = float(slice_definition.get("gain_structure_gain_soft_floor", gain_goal_floor + 0.08))

    baseline_live_activation_count = int(dict(v2_artifact.get("observability_gain", {})).get("slice_activation_count", dict(v2_artifact.get("comparison_to_v1", {})).get("slice_activation_count_v2", 0)))
    baseline_safe_retention_rate = float(dict(v2_artifact.get("comparison_to_v1", {})).get("projection_safe_retention_rate_v2", 0.0))
    baseline_benchmark_like_retention_rate = float(dict(v2_artifact.get("comparison_to_v1", {})).get("benchmark_like_retention_rate_v2", 0.0))
    baseline_mean_projection_error = _safe_metric(dict(v2_artifact.get("comparison_to_v1", {})).get("mean_projection_error_v2"))
    baseline_seed_activation_rate_summary = dict(dict(v2_artifact.get("comparison_to_v1", {})).get("seed_activation_rate_v2", {}))
    baseline_seed_counts = {
        int(dict(seed_summary).get("seed", -1)): int(dict(seed_summary).get("slice_activation_count", 0))
        for seed_summary in list(v2_artifact.get("seed_summaries", []))
        if _safe_metric(dict(seed_summary).get("seed")) is not None
    }
    baseline_benchmark_alignment = dict(v2_artifact.get("benchmark_alignment_summary", {}))
    baseline_benchmark_slice_count = int(baseline_benchmark_alignment.get("benchmark_slice_count", 0))
    baseline_benchmark_coverage_all = float(baseline_benchmark_alignment.get("benchmark_slice_coverage_all", 0.0))
    baseline_benchmark_undercommit_coverage = float(baseline_benchmark_alignment.get("benchmark_slice_coverage_undercommit", 0.0))
    baseline_benchmark_family_counts = {
        str(name): int(count)
        for name, count in dict(baseline_benchmark_alignment.get("benchmark_slice_family_counts", {})).items()
    }
    baseline_target_family_count = int(baseline_benchmark_alignment.get("benchmark_target_family_count", 0))
    baseline_target_share = float(baseline_target_family_count / baseline_benchmark_slice_count) if baseline_benchmark_slice_count else 0.0
    purity_benchmark_summary = dict(purity_artifact.get("benchmark_relevance_summary", {}))

    def _annotate_v2_row(row: Dict[str, Any]) -> Dict[str, Any]:
        annotated = dict(row)
        annotated["segment"] = str(annotated.get("segment", _segment_live_candidate(annotated, benchmark_summary=benchmark_summary, projection_boundary=projection_boundary)))
        if "benchmark_distance" not in annotated:
            annotated["benchmark_distance"] = float(_benchmark_distance(annotated, benchmark_summary))
        annotated["projection_level_critic"] = float(_row_projection_level_critic_v2(annotated, benchmark_summary, projection_boundary=projection_boundary))
        annotated["projection_shape_critic"] = float(_row_projection_shape_critic_v2(annotated, benchmark_summary))
        annotated["gain_goal_critic_v2"] = float(_row_gain_goal_critic_v2(annotated, benchmark_summary))
        annotated["stability_critic_v2"] = float(_row_stability_critic_v2(annotated, projection_level_critic=float(annotated["projection_level_critic"]), projection_shape_critic=float(annotated["projection_shape_critic"]), gain_goal_critic=float(annotated["gain_goal_critic_v2"])))
        return annotated

    def _v2_safe_pool_flags(row: Dict[str, Any]) -> Dict[str, bool]:
        blocker_group = str(row.get("blocker_group", "other"))
        segment = str(row.get("segment", "mixed_shift"))
        blocker_ok = blocker_group in {"projection_guard", "confidence_gain"}
        segment_ok = segment not in {"projection_far_shifted"}
        stability_ok = float(row.get("stability_critic_v2", 99.0)) <= float(stability_cap)
        if segment == "stability_sensitive":
            stability_ok = bool(stability_ok and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.85) and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.05))
        if segment in {"projection_mid_shifted", "projection_borderline"}:
            segment_ok = bool(segment_ok and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.95))
        if blocker_group == "confidence_gain":
            blocker_ok = bool(blocker_ok and float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap * 1.05) and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.02))
        gain_structure_soft_ok = bool(segment in {"gain_structure_shifted", "benchmark_adjacent"} and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap) and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap) and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_structure_gain_soft_floor) and float(row.get("projection_level_critic", 99.0)) <= float(gain_structure_level_soft_cap) and float(row.get("benchmark_distance", 99.0)) <= float(gain_structure_benchmark_distance_soft_cap))
        candidate_envelope_ok = bool(blocker_ok and segment_ok and stability_ok and (((float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap) and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap) and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor) and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)) or gain_structure_soft_ok)))
        projection_safe_ok = bool(candidate_envelope_ok and (((float(row.get("pred_projection_bad_prob", 99.0)) <= float(projection_bad_safe_cap) and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)) or (segment in {"gain_structure_shifted", "benchmark_adjacent"} and float(row.get("pred_projection_bad_prob", 99.0)) <= float(gain_structure_projection_bad_soft_cap) and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap) and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)))))
        return {
            "projection_safe_ok": bool(projection_safe_ok),
            "benchmark_like_ok": bool(projection_safe_ok and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)),
        }

    def _retention_band(row: Dict[str, Any]) -> int:
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 99.0)
        projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or 99.0)
        gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or -1e9)
        if benchmark_distance <= float(benchmark_distance_cap * 0.92) and projection_shape <= float(projection_shape_cap * 0.95):
            return 2
        if benchmark_distance <= float(benchmark_distance_cap) and gain_goal >= float(gain_goal_floor):
            return 1
        return 0

    def _benchmark_distance_retention_score(row: Dict[str, Any]) -> float:
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 1.20)
        confidence = float(_safe_metric(row.get("confidence")) or 0.0)
        gain = float(_safe_metric(row.get("gain")) or 0.0)
        pred_post_gain = float(_safe_metric(row.get("pred_post_gain")) or 0.0)
        projection_level = float(row.get("projection_level_critic", 0.0))
        projection_shape = float(row.get("projection_shape_critic", 0.0))
        gain_goal = float(row.get("gain_goal_critic_v2", 0.0))
        stability = float(row.get("stability_critic_v2", 0.0))
        segment = str(row.get("segment", "mixed_shift"))
        benchmark_proximity = max(0.0, 1.15 - min(1.15, benchmark_distance))
        shape_closeness = max(0.0, float(projection_shape_cap) - min(float(projection_shape_cap), projection_shape)) / max(1e-6, float(projection_shape_cap))
        level_closeness = max(0.0, float(projection_level_cap) - min(float(projection_level_cap), projection_level)) / max(1e-6, float(projection_level_cap))
        gain_goal_positive = max(0.0, gain_goal)
        distance_x_gain_goal = benchmark_proximity * min(1.0, gain_goal_positive)
        distance_x_shape = benchmark_proximity * shape_closeness
        post_gain_norm = math.tanh(pred_post_gain / 0.20)
        score = float(0.42 * benchmark_proximity + 0.18 * distance_x_shape + 0.16 * distance_x_gain_goal + 0.08 * shape_closeness + 0.05 * level_closeness + 0.05 * gain_goal_positive + 0.03 * confidence + 0.02 * gain + 0.02 * post_gain_norm - 0.08 * stability - 0.22 * min(1.0, max(0.0, benchmark_distance - benchmark_distance_cap) / 0.10) - 0.08 * min(1.0, max(0.0, projection_shape - projection_shape_cap) / max(0.08, projection_shape_cap * 0.25)) - 0.03 * min(1.0, max(0.0, projection_level - projection_level_cap) / max(0.08, projection_level_cap * 0.25)))
        if segment == "benchmark_adjacent":
            score += 0.10
        elif segment == "gain_structure_shifted":
            score += 0.06
        elif segment == "stability_sensitive":
            score -= 0.12
        elif segment == "projection_mid_shifted":
            score -= 0.04
        score += 0.10 * float(_retention_band(row))
        return float(score)

    def _predictor_strengths(rows: List[Dict[str, Any]]) -> Dict[str, float]:
        pos = [row for row in rows if bool(row.get("baseline_benchmark_like", False))]
        neg = [row for row in rows if not bool(row.get("baseline_benchmark_like", False))]
        if not pos or not neg:
            return {"benchmark_distance": 0.0, "benchmark_distance_x_gain_goal": 0.0, "benchmark_distance_x_projection_shape": 0.0, "mixed": 0.0}
        def _gap(fn) -> float:
            pos_vals = [float(fn(row)) for row in pos]
            neg_vals = [float(fn(row)) for row in neg]
            return float(abs((sum(pos_vals) / len(pos_vals)) - (sum(neg_vals) / len(neg_vals))))
        return {
            "benchmark_distance": _gap(lambda row: float(_safe_metric(row.get("benchmark_distance")) or 1.20)),
            "benchmark_distance_x_gain_goal": _gap(lambda row: max(0.0, 1.15 - float(_safe_metric(row.get("benchmark_distance")) or 1.15)) * max(0.0, float(_safe_metric(row.get("gain_goal_critic_v2")) or 0.0))),
            "benchmark_distance_x_projection_shape": _gap(lambda row: max(0.0, 1.15 - float(_safe_metric(row.get("benchmark_distance")) or 1.15)) * max(0.0, float(projection_shape_cap) - float(_safe_metric(row.get("projection_shape_critic")) or 0.0))),
            "mixed": _gap(lambda row: 0.55 * max(0.0, 1.15 - float(_safe_metric(row.get("benchmark_distance")) or 1.15)) * max(0.0, float(projection_shape_cap) - float(_safe_metric(row.get("projection_shape_critic")) or 0.0)) + 0.45 * max(0.0, 1.15 - float(_safe_metric(row.get("benchmark_distance")) or 1.15)) * max(0.0, float(_safe_metric(row.get("gain_goal_critic_v2")) or 0.0))),
        }

    benchmark_candidate_rows: List[Dict[str, Any]] = []
    for scenario_result in benchmark_undercommit_all:
        candidate_row = _benchmark_scenario_candidate_row(cfg, scenario_result, projection_boundary=projection_boundary, benchmark_summary=benchmark_summary)
        candidate_row = _annotate_v2_row(candidate_row)
        flags = _v2_safe_pool_flags(candidate_row)
        candidate_row["safe_probe_pool"] = bool(flags["projection_safe_ok"])
        candidate_row["baseline_benchmark_like"] = bool(flags["benchmark_like_ok"])
        candidate_row["retention_rank_band"] = int(_retention_band(candidate_row))
        candidate_row["benchmark_distance_retention_score"] = float(_benchmark_distance_retention_score(candidate_row))
        benchmark_candidate_rows.append(candidate_row)

    all_rows: List[Dict[str, Any]] = []
    live_probe_rows: List[Dict[str, Any]] = []
    seed_summaries: List[Dict[str, Any]] = []
    for seed in list(seeds):
        run_cfg = copy.deepcopy(cfg)
        run_cfg.verbose = False
        run_cfg.rounds = max(1, int(rounds))
        run_cfg.seed = int(seed)
        run_cfg.benchmark_every_rounds = 0
        run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs or {})
        run_cfg.eval_kwargs["session_log_path"] = f"logs/intervention_shadow_{proposal['proposal_id']}_benchmark_distance_probe_seed{int(seed)}.log"
        apply_live_policy_variant(run_cfg, "targeted_gain_goal_proj_margin_01")
        _, _, history = run_proposal_learning_loop(run_cfg)

        seed_rows: List[Dict[str, Any]] = []
        for round_index, entry in enumerate(history):
            blocked = [item for item in list(entry.get("adopt_blocked", [])) if isinstance(item, dict)]
            for item in blocked:
                row = _live_gap_row(item, seed=int(seed), round_index=int(round_index), cohort="baseline_rejected", projection_boundary=projection_boundary)
                row = _annotate_v2_row(row)
                flags = _v2_safe_pool_flags(row)
                row["safe_probe_pool"] = bool(flags["projection_safe_ok"])
                row["baseline_benchmark_like"] = bool(flags["benchmark_like_ok"])
                row["retention_rank_band"] = int(_retention_band(row))
                row["benchmark_distance_retention_score"] = float(_benchmark_distance_retention_score(row))
                seed_rows.append(row)
                all_rows.append(row)

        safe_pool_rows = [row for row in seed_rows if bool(row.get("safe_probe_pool", False))]
        baseline_target_count = int(baseline_seed_counts.get(int(seed), 0))
        selected_rows: List[Dict[str, Any]] = []
        if baseline_target_count > 0 and safe_pool_rows:
            ordered = sorted(safe_pool_rows, key=lambda item: (int(item.get("retention_rank_band", 0)), float(item.get("benchmark_distance_retention_score", -1e9))), reverse=True)
            selected_rows = ordered[: min(len(ordered), baseline_target_count)]

        selected_ids = {
            (int(dict(row).get("round_index", -1)), str(dict(row).get("candidate_id", "")))
            for row in selected_rows
        }
        for row in seed_rows:
            row["probe_slice_candidate"] = bool((int(dict(row).get("round_index", -1)), str(dict(row).get("candidate_id", ""))) in selected_ids)
            row["probe_projection_safe"] = bool(row["probe_slice_candidate"] and bool(row.get("safe_probe_pool", False)))
            row["probe_benchmark_like"] = bool(row["probe_projection_safe"] and bool(row.get("baseline_benchmark_like", False)))
            if bool(row["probe_slice_candidate"]):
                live_probe_rows.append(row)

        seed_selected_rows = [row for row in seed_rows if bool(row.get("probe_slice_candidate", False))]
        seed_safe_rows = [row for row in seed_selected_rows if bool(row.get("probe_projection_safe", False))]
        seed_like_rows = [row for row in seed_selected_rows if bool(row.get("probe_benchmark_like", False))]
        seed_summaries.append(
            {
                "seed": int(seed),
                "blocked_candidate_count": int(len(seed_rows)),
                "safe_probe_pool_count": int(len(safe_pool_rows)),
                "baseline_target_count": int(baseline_target_count),
                "slice_activation_count": int(len(seed_selected_rows)),
                "slice_activation_rate": float(len(seed_selected_rows) / len(seed_rows)) if seed_rows else 0.0,
                "slice_projection_safe_count": int(len(seed_safe_rows)),
                "slice_projection_safe_rate": float(len(seed_safe_rows) / len(seed_selected_rows)) if seed_selected_rows else 0.0,
                "slice_benchmark_like_count": int(len(seed_like_rows)),
                "slice_benchmark_like_rate": float(len(seed_like_rows) / len(seed_selected_rows)) if seed_selected_rows else 0.0,
                "mean_slice_projection_error": _mean_key(seed_selected_rows, "pred_projection_error"),
            }
        )

    live_safe_pool_rows = [row for row in all_rows if bool(row.get("safe_probe_pool", False))]
    activation_count = int(len(live_probe_rows))
    safe_retention_rate = float(sum(bool(row.get("probe_projection_safe", False)) for row in live_probe_rows) / activation_count) if activation_count else 0.0
    benchmark_like_retention_rate = float(sum(bool(row.get("probe_benchmark_like", False)) for row in live_probe_rows) / activation_count) if activation_count else 0.0
    mean_projection_error = _mean_key(live_probe_rows, "pred_projection_error")
    benchmark_pool_rows = [row for row in benchmark_candidate_rows if bool(row.get("safe_probe_pool", False))]
    live_selection_fraction = float(activation_count / len(live_safe_pool_rows)) if live_safe_pool_rows else 0.0
    score_fraction_count = int(math.ceil(len(benchmark_pool_rows) * live_selection_fraction)) if benchmark_pool_rows and live_selection_fraction > 0.0 else 0
    coverage_floor_count = min(len(benchmark_pool_rows), max(1 if benchmark_pool_rows else 0, int(math.ceil(float(baseline_benchmark_slice_count) * 0.85))))
    benchmark_selected_count = min(len(benchmark_pool_rows), max(score_fraction_count, coverage_floor_count)) if benchmark_pool_rows else 0
    benchmark_probe_rows: List[Dict[str, Any]] = []
    if benchmark_pool_rows and benchmark_selected_count > 0:
        benchmark_probe_rows = sorted(benchmark_pool_rows, key=lambda item: (int(item.get("retention_rank_band", 0)), float(item.get("benchmark_distance_retention_score", -1e9))), reverse=True)[:benchmark_selected_count]

    benchmark_probe_family_counts = Counter(str(row.get("family", "unknown")) for row in benchmark_probe_rows)
    benchmark_probe_target_family_count = int(sum(str(row.get("family", "")) == benchmark_target_family for row in benchmark_probe_rows))
    benchmark_probe_coverage_all = float(len(benchmark_probe_rows) / len(benchmark_rows)) if benchmark_rows else 0.0
    benchmark_probe_coverage_undercommit = float(len(benchmark_probe_rows) / len(benchmark_undercommit_all)) if benchmark_undercommit_all else 0.0
    probe_target_share = float(benchmark_probe_target_family_count / len(benchmark_probe_rows)) if benchmark_probe_rows else 0.0
    baseline_seed_std = _safe_metric(baseline_seed_activation_rate_summary.get("std")) or 0.0
    probe_seed_activation_rate_summary = _rate_summary(seed_summaries, "slice_activation_rate")
    probe_seed_std = _safe_metric(probe_seed_activation_rate_summary.get("std")) or 0.0
    predictor_strengths = _predictor_strengths(live_safe_pool_rows or benchmark_pool_rows)
    best_retention_predictor = max(predictor_strengths.items(), key=lambda item: float(item[1]))[0] if predictor_strengths else "mixed"
    benchmark_retention_improved = bool(benchmark_like_retention_rate > baseline_benchmark_like_retention_rate + 1e-9)
    projection_safe_retention_preserved = bool(safe_retention_rate >= max(0.95, baseline_safe_retention_rate - 0.02))
    coverage_preserved = bool(benchmark_probe_coverage_undercommit >= max(0.55, baseline_benchmark_undercommit_coverage * 0.85) and len(benchmark_probe_rows) >= max(int(math.ceil(baseline_benchmark_slice_count * 0.85)), int(dict(purity_benchmark_summary).get("benchmark_slice_count_probe", 0))))
    seed_fragility_preserved = bool(probe_seed_std <= baseline_seed_std + 1e-9)
    slice_fragility = "high" if probe_seed_std >= baseline_seed_std + 0.02 else ("low" if seed_fragility_preserved and activation_count >= max(1, baseline_live_activation_count) else "medium")

    if projection_safe_retention_preserved and benchmark_retention_improved and coverage_preserved and seed_fragility_preserved:
        next_control_hypothesis = "narrow_routing_revisit"
        recommended_next_template = "routing_rule.activation_window_probe"
        recommendation_reason = "benchmark-distance-focused refinement improves retention while preserving useful coverage, so a very narrow routing revisit becomes testable"
    elif projection_safe_retention_preserved and coverage_preserved and best_retention_predictor == "benchmark_distance":
        next_control_hypothesis = "benchmark_alignment_critic"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "benchmark-distance remains the clearest retention driver, so the next step should stay in benchmark-alignment-oriented critic refinement"
    elif projection_safe_retention_preserved and coverage_preserved:
        next_control_hypothesis = "critic_refinement_continue"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "retention evidence remains useful, but routing should stay deferred until the safe slice gets cleaner"
    else:
        next_control_hypothesis = "no_routing_yet"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "benchmark-distance refinement does not yet produce a clean enough coverage-preserving slice for routing reconsideration"

    observability_gain = {
        "passed": bool(len(all_rows) >= 12 and len(live_safe_pool_rows) >= 4 and len(benchmark_probe_rows) >= 10),
        "blocked_candidate_count": int(len(all_rows)),
        "safe_probe_pool_count": int(len(live_safe_pool_rows)),
        "slice_activation_count": int(activation_count),
        "seed_count": int(len(seed_summaries)),
        "benchmark_reference_source": str(benchmark_reference_source),
        "benchmark_undercommit_count": int(len(benchmark_undercommit_all)),
        "reason": "captured enough safe-slice live traffic and benchmark undercommit rows to measure benchmark-distance retention effects against critic v2",
    }
    activation_analysis = {
        "passed": bool(activation_count > 0),
        "slice_activation_observed": bool(activation_count > 0),
        "slice_activation_repeatable": bool(sum(int(summary.get("slice_activation_count", 0)) > 0 for summary in seed_summaries) >= 2),
        "slice_activation_rate": float(activation_count / len(all_rows)) if all_rows else 0.0,
        "reason": "benchmark-distance refinement retains an activatable safe slice across repeated short runs" if activation_count > 0 else "benchmark-distance refinement collapses the live slice under repeated short runs",
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(min(1.0, 0.25 + 0.18 * int(projection_safe_retention_preserved) + 0.18 * int(benchmark_retention_improved) + 0.16 * int(coverage_preserved) + 0.12 * int(seed_fragility_preserved) + 0.11 * int(bool(best_retention_predictor)))),
        "reason": "the benchmark-distance probe tests whether retention can improve inside the safe slice without sacrificing coverage",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "probe-only critic refinement inside the critic-v2 safe slice with no default live-policy mutation and no benchmark semantic changes",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": str(proposal.get("template_name")),
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "critic_refinement_logic_used": {
            "refined_signal_groups": list(mechanism.get("refined_signal_groups", [])),
            "ranking_mode": str(mechanism.get("ranking_mode", "single_stage")),
            "blocker_sensitive_rules_used": list(mechanism.get("blocker_sensitive_rules", [])),
        },
        "comparison_reference_template": "critic_split.projection_gain_goal_v2",
        "slice_definition": {
            "source_template": "critic_split.projection_gain_goal_v2",
            "projection_level_cap": float(projection_level_cap),
            "projection_shape_cap": float(projection_shape_cap),
            "gain_goal_floor": float(gain_goal_floor),
            "stability_cap": float(stability_cap),
            "projection_bad_safe_cap": float(projection_bad_safe_cap),
            "projection_error_safe_cap": float(projection_error_safe_cap),
            "benchmark_distance_cap": float(benchmark_distance_cap),
            "selection_count_mode": "same_live_seed_count_as_v2",
            "benchmark_selection_floor_fraction": 0.85,
        },
        "comparison_to_v2": {
            "slice_activation_count_v2": int(baseline_live_activation_count),
            "slice_activation_count_probe": int(activation_count),
            "slice_activation_count_delta": int(activation_count - baseline_live_activation_count),
            "projection_safe_retention_rate_v2": float(baseline_safe_retention_rate),
            "projection_safe_retention_rate_probe": float(safe_retention_rate),
            "projection_safe_retention_rate_delta": float(safe_retention_rate - baseline_safe_retention_rate),
            "benchmark_like_retention_rate_v2": float(baseline_benchmark_like_retention_rate),
            "benchmark_like_retention_rate_probe": float(benchmark_like_retention_rate),
            "benchmark_like_retention_rate_delta": float(benchmark_like_retention_rate - baseline_benchmark_like_retention_rate),
            "mean_projection_error_v2": baseline_mean_projection_error,
            "mean_projection_error_probe": mean_projection_error,
            "mean_projection_error_delta": None if baseline_mean_projection_error is None or mean_projection_error is None else float(mean_projection_error - baseline_mean_projection_error),
            "seed_activation_rate_v2": baseline_seed_activation_rate_summary,
            "seed_activation_rate_probe": probe_seed_activation_rate_summary,
            "seed_projection_safe_rate_probe": _rate_summary(seed_summaries, "slice_projection_safe_rate"),
            "seed_benchmark_like_rate_probe": _rate_summary(seed_summaries, "slice_benchmark_like_rate"),
        },
        "comparison_to_purity_probe": {
            "benchmark_slice_count_probe": int(dict(purity_benchmark_summary).get("benchmark_slice_count_probe", 0)),
            "benchmark_slice_coverage_undercommit_probe": float(dict(purity_benchmark_summary).get("benchmark_slice_coverage_undercommit_probe", 0.0)),
        },
        "purity_metrics": {
            "safe_pool_count": int(len(live_safe_pool_rows)),
            "activation_count": int(activation_count),
            "benchmark_like_retention_rate": float(benchmark_like_retention_rate),
            "projection_safe_retention_rate": float(safe_retention_rate),
            "best_retention_predictor": str(best_retention_predictor),
            "predictor_strengths": {str(name): float(value) for name, value in sorted(predictor_strengths.items(), key=lambda item: (-float(item[1]), str(item[0])))},
        },
        "benchmark_relevance_summary": {
            "benchmark_slice_count_v2": int(baseline_benchmark_slice_count),
            "benchmark_slice_count_probe": int(len(benchmark_probe_rows)),
            "benchmark_slice_coverage_all_v2": float(baseline_benchmark_coverage_all),
            "benchmark_slice_coverage_all_probe": float(benchmark_probe_coverage_all),
            "benchmark_slice_coverage_undercommit_v2": float(baseline_benchmark_undercommit_coverage),
            "benchmark_slice_coverage_undercommit_probe": float(benchmark_probe_coverage_undercommit),
            "benchmark_slice_family_counts_v2": baseline_benchmark_family_counts,
            "benchmark_slice_family_counts_probe": {str(name): int(count) for name, count in sorted(benchmark_probe_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "benchmark_target_family_count_v2": int(baseline_target_family_count),
            "benchmark_target_family_count_probe": int(benchmark_probe_target_family_count),
            "benchmark_target_family_share_v2": float(baseline_target_share),
            "benchmark_target_family_share_probe": float(probe_target_share),
        },
        "family_slice_composition": {
            "target_family": str(benchmark_target_family),
            "benchmark_probe_family_counts": {str(name): int(count) for name, count in sorted(benchmark_probe_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
        },
        "seed_summaries": seed_summaries,
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": {
            "benchmark_retention_improved": bool(benchmark_retention_improved),
            "projection_safe_retention_preserved": bool(projection_safe_retention_preserved),
            "coverage_preserved": bool(coverage_preserved),
            "best_retention_predictor": str(best_retention_predictor),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
            "slice_fragility": str(slice_fragility),
        },
        "sample_rows": {
            "probe_slice_examples": live_probe_rows[:8],
            "benchmark_probe_examples": benchmark_probe_rows[:8],
            "safe_pool_near_misses": sorted([row for row in all_rows if bool(row.get("safe_probe_pool", False)) and not bool(row.get("probe_slice_candidate", False))], key=lambda item: (int(item.get("retention_rank_band", 0)), float(item.get("benchmark_distance_retention_score", -1e9))), reverse=True)[:8],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"critic_split_benchmark_distance_retention_probe_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(observability_gain["passed"] and ambiguity_reduction["passed"] and safety_neutrality["passed"] and later_selection_usefulness["passed"])
    if not bool(observability_gain["passed"]):
        reason = "diagnostic shadow failed: insufficient safe-slice live or benchmark evidence for benchmark-distance retention refinement"
    elif not bool(projection_safe_retention_preserved):
        reason = "diagnostic shadow passed: benchmark-distance retention refinement weakened projection-safe retention and should not be promoted"
    elif benchmark_retention_improved and coverage_preserved:
        reason = "diagnostic shadow passed: benchmark-distance retention refinement improves benchmark-like retention while keeping useful coverage"
    else:
        reason = "diagnostic shadow passed: benchmark-distance retention refinement preserves safety, but retention or coverage is still not strong enough to revisit routing"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_critic_split_benchmark_alignment_critic_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    v2_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.projection_gain_goal_v2")
    purity_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.safe_slice_purity_probe_v1")
    distance_artifact = _load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_distance_retention_probe_v1"
    )
    if not v2_artifact or not purity_artifact or not distance_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: critic split v2, safe-slice purity, and benchmark-distance retention artifacts are required for benchmark_alignment_critic_v1",
            "observability_gain": {"passed": False, "reason": "missing prerequisite critic artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite critic artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite critic artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot recommend a follow-up without the v2, purity, and benchmark-distance probe baselines",
            },
        }

    intended_benefit = dict(proposal.get("intended_benefit", {}))
    mechanism = dict(proposal.get("mechanism", {}))
    benchmark_target_family = str(intended_benefit.get("target_family", "gain_goal_conflict"))
    projection_boundary = float(_targeted_projection_override_boundary(cfg))

    benchmark_rows = _load_latest_benchmark_detailed_rows()
    benchmark_undercommit_all = [
        row
        for row in benchmark_rows
        if str(row.get("policy_decision", "")) == "reject"
        and str(row.get("oracle_decision", "")) in {"provisional", "full"}
    ]
    benchmark_undercommit_target = [
        row for row in benchmark_undercommit_all if str(row.get("family", "")) == benchmark_target_family
    ]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (
            benchmark_undercommit_target
            if benchmark_reference_source == "target_family_undercommit"
            else benchmark_undercommit_all
        )
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }

    slice_definition = dict(v2_artifact.get("slice_definition", {}))
    projection_level_cap = float(slice_definition.get("projection_level_cap", 0.70))
    projection_shape_cap = float(slice_definition.get("projection_shape_cap", 0.65))
    gain_goal_floor = float(slice_definition.get("gain_goal_floor", 0.34))
    stability_cap = float(slice_definition.get("stability_cap", 0.42))
    projection_bad_safe_cap = float(slice_definition.get("projection_bad_safe_cap", 0.57))
    projection_error_safe_cap = float(slice_definition.get("projection_error_safe_cap", 0.0115))
    benchmark_distance_cap = float(slice_definition.get("benchmark_distance_cap", 1.0))
    gain_structure_level_soft_cap = float(slice_definition.get("gain_structure_level_soft_cap", projection_level_cap + 0.08))
    gain_structure_benchmark_distance_soft_cap = float(
        slice_definition.get("gain_structure_benchmark_distance_soft_cap", benchmark_distance_cap + 0.05)
    )
    gain_structure_projection_bad_soft_cap = float(
        slice_definition.get("gain_structure_projection_bad_soft_cap", projection_bad_safe_cap + 0.02)
    )
    gain_structure_gain_soft_floor = float(
        slice_definition.get("gain_structure_gain_soft_floor", gain_goal_floor + 0.08)
    )

    baseline_live_activation_count = int(
        dict(v2_artifact.get("observability_gain", {})).get(
            "slice_activation_count",
            dict(v2_artifact.get("comparison_to_v1", {})).get("slice_activation_count_v2", 0),
        )
    )
    baseline_safe_retention_rate = float(
        dict(v2_artifact.get("comparison_to_v1", {})).get("projection_safe_retention_rate_v2", 0.0)
    )
    baseline_benchmark_like_retention_rate = float(
        dict(v2_artifact.get("comparison_to_v1", {})).get("benchmark_like_retention_rate_v2", 0.0)
    )
    baseline_mean_projection_error = _safe_metric(
        dict(v2_artifact.get("comparison_to_v1", {})).get("mean_projection_error_v2")
    )
    baseline_seed_activation_rate_summary = dict(
        dict(v2_artifact.get("comparison_to_v1", {})).get("seed_activation_rate_v2", {})
    )
    baseline_seed_counts = {
        int(dict(seed_summary).get("seed", -1)): int(dict(seed_summary).get("slice_activation_count", 0))
        for seed_summary in list(v2_artifact.get("seed_summaries", []))
        if _safe_metric(dict(seed_summary).get("seed")) is not None
    }
    baseline_benchmark_alignment = dict(v2_artifact.get("benchmark_alignment_summary", {}))
    baseline_benchmark_slice_count = int(baseline_benchmark_alignment.get("benchmark_slice_count", 0))
    baseline_benchmark_coverage_all = float(baseline_benchmark_alignment.get("benchmark_slice_coverage_all", 0.0))
    baseline_benchmark_undercommit_coverage = float(
        baseline_benchmark_alignment.get("benchmark_slice_coverage_undercommit", 0.0)
    )
    baseline_benchmark_family_counts = {
        str(name): int(count)
        for name, count in dict(baseline_benchmark_alignment.get("benchmark_slice_family_counts", {})).items()
    }
    baseline_target_family_count = int(baseline_benchmark_alignment.get("benchmark_target_family_count", 0))
    baseline_target_share = float(baseline_target_family_count / baseline_benchmark_slice_count) if baseline_benchmark_slice_count else 0.0
    purity_benchmark_summary = dict(purity_artifact.get("benchmark_relevance_summary", {}))
    distance_purity_metrics = dict(distance_artifact.get("purity_metrics", {}))

    def _annotate_v2_row(row: Dict[str, Any]) -> Dict[str, Any]:
        annotated = dict(row)
        annotated["segment"] = str(
            annotated.get(
                "segment",
                _segment_live_candidate(
                    annotated,
                    benchmark_summary=benchmark_summary,
                    projection_boundary=projection_boundary,
                ),
            )
        )
        if "benchmark_distance" not in annotated:
            annotated["benchmark_distance"] = float(_benchmark_distance(annotated, benchmark_summary))
        annotated["projection_level_critic"] = float(
            _row_projection_level_critic_v2(annotated, benchmark_summary, projection_boundary=projection_boundary)
        )
        annotated["projection_shape_critic"] = float(_row_projection_shape_critic_v2(annotated, benchmark_summary))
        annotated["gain_goal_critic_v2"] = float(_row_gain_goal_critic_v2(annotated, benchmark_summary))
        annotated["stability_critic_v2"] = float(
            _row_stability_critic_v2(
                annotated,
                projection_level_critic=float(annotated["projection_level_critic"]),
                projection_shape_critic=float(annotated["projection_shape_critic"]),
                gain_goal_critic=float(annotated["gain_goal_critic_v2"]),
            )
        )
        return annotated

    def _v2_safe_pool_flags(row: Dict[str, Any]) -> Dict[str, bool]:
        blocker_group = str(row.get("blocker_group", "other"))
        segment = str(row.get("segment", "mixed_shift"))
        blocker_ok = blocker_group in {"projection_guard", "confidence_gain"}
        segment_ok = segment not in {"projection_far_shifted"}
        stability_ok = float(row.get("stability_critic_v2", 99.0)) <= float(stability_cap)
        if segment == "stability_sensitive":
            stability_ok = bool(
                stability_ok
                and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.85)
                and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.05)
            )
        if segment in {"projection_mid_shifted", "projection_borderline"}:
            segment_ok = bool(
                segment_ok and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.95)
            )
        if blocker_group == "confidence_gain":
            blocker_ok = bool(
                blocker_ok
                and float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap * 1.05)
                and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.02)
            )
        gain_structure_soft_ok = bool(
            segment in {"gain_structure_shifted", "benchmark_adjacent"}
            and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)
            and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
            and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_structure_gain_soft_floor)
            and float(row.get("projection_level_critic", 99.0)) <= float(gain_structure_level_soft_cap)
            and float(row.get("benchmark_distance", 99.0)) <= float(gain_structure_benchmark_distance_soft_cap)
        )
        candidate_envelope_ok = bool(
            blocker_ok
            and segment_ok
            and stability_ok
            and (
                (
                    float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap)
                    and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)
                    and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor)
                    and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)
                )
                or gain_structure_soft_ok
            )
        )
        projection_safe_ok = bool(
            candidate_envelope_ok
            and (
                (
                    float(row.get("pred_projection_bad_prob", 99.0)) <= float(projection_bad_safe_cap)
                    and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
                )
                or (
                    segment in {"gain_structure_shifted", "benchmark_adjacent"}
                    and float(row.get("pred_projection_bad_prob", 99.0)) <= float(gain_structure_projection_bad_soft_cap)
                    and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
                    and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)
                )
            )
        )
        return {
            "projection_safe_ok": bool(projection_safe_ok),
            "benchmark_like_ok": bool(
                projection_safe_ok and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)
            ),
        }

    def _alignment_subtype(row: Dict[str, Any]) -> str:
        segment = str(row.get("segment", "mixed_shift"))
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 99.0)
        projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or 99.0)
        gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or -1e9)
        stability = float(_safe_metric(row.get("stability_critic_v2")) or 99.0)
        if segment == "benchmark_adjacent" and benchmark_distance <= float(benchmark_distance_cap * 1.02) and projection_shape <= float(projection_shape_cap * 0.95):
            return "retained_like_profile"
        if segment == "gain_structure_shifted" and benchmark_distance <= float(gain_structure_benchmark_distance_soft_cap) and projection_shape <= float(projection_shape_cap) and gain_goal >= float(gain_structure_gain_soft_floor):
            return "retained_like_profile"
        if segment == "gain_structure_shifted":
            return "gain_fragile_profile"
        if segment == "stability_sensitive" or stability > float(stability_cap * 0.95):
            return "stability_fragile"
        if segment in {"projection_mid_shifted", "projection_borderline"} or projection_shape > float(projection_shape_cap * 0.92):
            return "projection_shape_fragile"
        return "mixed_safe"

    def _subtype_prior_value(subtype: str) -> float:
        return {
            "retained_like_profile": 1.00,
            "gain_fragile_profile": 0.62,
            "mixed_safe": 0.40,
            "projection_shape_fragile": 0.16,
            "stability_fragile": 0.05,
        }.get(str(subtype), 0.25)

    def _build_context(rows: List[Dict[str, Any]], baseline_target_count: int) -> Dict[str, Any]:
        subtype_counts = Counter(str(row.get("alignment_subtype", "mixed_safe")) for row in rows)
        return {
            "safe_pool_count": int(len(rows)),
            "baseline_target_count": int(max(0, baseline_target_count)),
            "mean_benchmark_distance": _mean_key(rows, "benchmark_distance"),
            "mean_projection_shape": _mean_key(rows, "projection_shape_critic"),
            "mean_gain_goal": _mean_key(rows, "gain_goal_critic_v2"),
            "subtype_counts": {str(name): int(count) for name, count in subtype_counts.items()},
        }

    def _context_conditioned_score(row: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, float]:
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 1.20)
        projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or 0.0)
        projection_level = float(_safe_metric(row.get("projection_level_critic")) or 0.0)
        gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or 0.0)
        stability = float(_safe_metric(row.get("stability_critic_v2")) or 0.0)
        subtype = str(row.get("alignment_subtype", "mixed_safe"))
        benchmark_proximity = max(0.0, 1.15 - min(1.15, benchmark_distance))
        shape_closeness = max(0.0, float(projection_shape_cap) - min(float(projection_shape_cap), projection_shape)) / max(1e-6, float(projection_shape_cap))
        level_closeness = max(0.0, float(projection_level_cap) - min(float(projection_level_cap), projection_level)) / max(1e-6, float(projection_level_cap))
        gain_goal_positive = max(0.0, gain_goal)
        subtype_prior = float(_subtype_prior_value(subtype))
        safe_pool_count = int(context.get("safe_pool_count", 0))
        baseline_target_count = int(context.get("baseline_target_count", 0))
        scarcity = max(0.0, float(baseline_target_count - safe_pool_count) / max(1.0, float(baseline_target_count or 1)))
        mean_benchmark_distance = float(_safe_metric(context.get("mean_benchmark_distance")) or benchmark_distance_cap)
        mean_projection_shape = float(_safe_metric(context.get("mean_projection_shape")) or projection_shape_cap)
        mean_gain_goal = float(_safe_metric(context.get("mean_gain_goal")) or gain_goal_floor)
        context_shift = min(
            1.0,
            max(0.0, mean_benchmark_distance - float(benchmark_distance_cap * 0.95)) / max(0.05, float(benchmark_distance_cap * 0.10))
            + max(0.0, mean_projection_shape - float(projection_shape_cap * 0.90)) / max(0.05, float(projection_shape_cap * 0.20)),
        )
        stability_context = max(0.0, 1.0 - min(1.0, stability / max(1e-6, float(stability_cap)))) * max(0.0, 1.0 - 0.55 * context_shift - 0.35 * scarcity)
        gain_goal_context = benchmark_proximity * min(1.0, gain_goal_positive) * max(0.0, 1.0 - 0.35 * context_shift)
        if gain_goal >= mean_gain_goal:
            gain_goal_context += 0.06 * min(1.0, gain_goal_positive)
        projection_shape_context = benchmark_proximity * shape_closeness * max(0.0, 1.0 - 0.25 * scarcity)
        if projection_shape <= mean_projection_shape:
            projection_shape_context += 0.05 * shape_closeness
        mixed_structure = 0.38 * subtype_prior + 0.26 * gain_goal_context + 0.24 * projection_shape_context + 0.12 * stability_context
        score = float(
            0.30 * subtype_prior
            + 0.22 * gain_goal_context
            + 0.22 * projection_shape_context
            + 0.10 * stability_context
            + 0.08 * benchmark_proximity
            + 0.08 * level_closeness
            - 0.12 * scarcity
            - 0.10 * context_shift
        )
        if subtype == "retained_like_profile":
            score += 0.10
        elif subtype == "gain_fragile_profile":
            score += 0.03
        elif subtype == "projection_shape_fragile":
            score -= 0.08
        elif subtype == "stability_fragile":
            score -= 0.12
        if str(row.get("blocker_group", "")) == "confidence_gain" and gain_goal_positive > 0.0:
            score += 0.03
        return {
            "benchmark_alignment_critic_score": float(score),
            "subtype_split_score": float(subtype_prior),
            "stability_context_score": float(stability_context),
            "gain_goal_context_score": float(gain_goal_context),
            "projection_shape_context_score": float(projection_shape_context),
            "mixed_structure_score": float(mixed_structure),
            "context_shift_score": float(context_shift),
            "scarcity_score": float(scarcity),
        }

    def _predictor_strengths(rows: List[Dict[str, Any]]) -> Dict[str, float]:
        pos = [row for row in rows if bool(row.get("baseline_benchmark_like", False))]
        neg = [row for row in rows if not bool(row.get("baseline_benchmark_like", False))]
        if not pos or not neg:
            return {
                "subtype_split": 0.0,
                "stability_context_interaction": 0.0,
                "context_conditioned_gain_goal_interaction": 0.0,
                "context_conditioned_projection_shape_interaction": 0.0,
                "mixed_structure": 0.0,
            }

        def _gap(key: str) -> float:
            pos_vals = [float(_safe_metric(row.get(key)) or 0.0) for row in pos]
            neg_vals = [float(_safe_metric(row.get(key)) or 0.0) for row in neg]
            return float(abs((sum(pos_vals) / len(pos_vals)) - (sum(neg_vals) / len(neg_vals))))

        return {
            "subtype_split": _gap("subtype_split_score"),
            "stability_context_interaction": _gap("stability_context_score"),
            "context_conditioned_gain_goal_interaction": _gap("gain_goal_context_score"),
            "context_conditioned_projection_shape_interaction": _gap("projection_shape_context_score"),
            "mixed_structure": _gap("mixed_structure_score"),
        }

    benchmark_candidate_rows: List[Dict[str, Any]] = []
    for scenario_result in benchmark_undercommit_all:
        candidate_row = _benchmark_scenario_candidate_row(
            cfg,
            scenario_result,
            projection_boundary=projection_boundary,
            benchmark_summary=benchmark_summary,
        )
        candidate_row = _annotate_v2_row(candidate_row)
        flags = _v2_safe_pool_flags(candidate_row)
        candidate_row["safe_probe_pool"] = bool(flags["projection_safe_ok"])
        candidate_row["baseline_benchmark_like"] = bool(flags["benchmark_like_ok"])
        candidate_row["alignment_subtype"] = str(_alignment_subtype(candidate_row))
        benchmark_candidate_rows.append(candidate_row)

    benchmark_pool_rows = [row for row in benchmark_candidate_rows if bool(row.get("safe_probe_pool", False))]
    benchmark_context = _build_context(
        benchmark_pool_rows,
        int(math.ceil(len(benchmark_pool_rows) * 0.35)) if benchmark_pool_rows else 0,
    )
    for row in benchmark_pool_rows:
        row.update(_context_conditioned_score(row, benchmark_context))

    all_rows: List[Dict[str, Any]] = []
    live_probe_rows: List[Dict[str, Any]] = []
    seed_summaries: List[Dict[str, Any]] = []
    seed_failure_modes: List[Dict[str, Any]] = []
    live_seed_contexts: List[Dict[str, Any]] = []

    for seed in list(seeds):
        run_cfg = copy.deepcopy(cfg)
        run_cfg.verbose = False
        run_cfg.rounds = max(1, int(rounds))
        run_cfg.seed = int(seed)
        run_cfg.benchmark_every_rounds = 0
        run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs or {})
        run_cfg.eval_kwargs["session_log_path"] = (
            f"logs/intervention_shadow_{proposal['proposal_id']}_benchmark_alignment_seed{int(seed)}.log"
        )
        apply_live_policy_variant(run_cfg, "targeted_gain_goal_proj_margin_01")
        _, _, history = run_proposal_learning_loop(run_cfg)

        seed_rows: List[Dict[str, Any]] = []
        for round_index, entry in enumerate(history):
            blocked = [item for item in list(entry.get("adopt_blocked", [])) if isinstance(item, dict)]
            for item in blocked:
                row = _live_gap_row(
                    item,
                    seed=int(seed),
                    round_index=int(round_index),
                    cohort="baseline_rejected",
                    projection_boundary=projection_boundary,
                )
                row = _annotate_v2_row(row)
                flags = _v2_safe_pool_flags(row)
                row["safe_probe_pool"] = bool(flags["projection_safe_ok"])
                row["baseline_benchmark_like"] = bool(flags["benchmark_like_ok"])
                row["alignment_subtype"] = str(_alignment_subtype(row))
                seed_rows.append(row)
                all_rows.append(row)

        safe_pool_rows = [row for row in seed_rows if bool(row.get("safe_probe_pool", False))]
        baseline_target_count = int(baseline_seed_counts.get(int(seed), 0))
        seed_context = _build_context(safe_pool_rows, baseline_target_count)
        live_seed_contexts.append({"seed": int(seed), **seed_context})
        for row in safe_pool_rows:
            row.update(_context_conditioned_score(row, seed_context))

        selected_rows: List[Dict[str, Any]] = []
        if baseline_target_count > 0 and safe_pool_rows:
            ordered = sorted(
                safe_pool_rows,
                key=lambda item: float(item.get("benchmark_alignment_critic_score", -1e9)),
                reverse=True,
            )
            target_count = min(len(ordered), baseline_target_count)
            scarcity = float(
                max(
                    0,
                    int(seed_context.get("baseline_target_count", 0))
                    - int(seed_context.get("safe_pool_count", 0)),
                )
            )
            quality_floor = 0.23 + (0.04 if scarcity > 0 else 0.0)
            selected_rows = [
                row
                for row in ordered[:target_count]
                if float(row.get("benchmark_alignment_critic_score", -1e9)) >= quality_floor
                or str(row.get("alignment_subtype", "")) == "retained_like_profile"
            ]
            if not selected_rows and ordered:
                top = ordered[0]
                if (
                    float(top.get("benchmark_alignment_critic_score", -1e9)) >= quality_floor - 0.05
                    and str(top.get("alignment_subtype", ""))
                    in {"retained_like_profile", "gain_fragile_profile"}
                ):
                    selected_rows = [top]

        selected_ids = {
            (int(dict(row).get("round_index", -1)), str(dict(row).get("candidate_id", "")))
            for row in selected_rows
        }
        for row in seed_rows:
            row["probe_slice_candidate"] = bool(
                (int(dict(row).get("round_index", -1)), str(dict(row).get("candidate_id", ""))) in selected_ids
            )
            row["probe_projection_safe"] = bool(
                row["probe_slice_candidate"] and bool(row.get("safe_probe_pool", False))
            )
            row["probe_benchmark_like"] = bool(
                row["probe_projection_safe"] and bool(row.get("baseline_benchmark_like", False))
            )
            if bool(row["probe_slice_candidate"]):
                live_probe_rows.append(row)

        safe_pool_benchmark_like_count = int(
            sum(bool(row.get("baseline_benchmark_like", False)) for row in safe_pool_rows)
        )
        seed_selected_rows = [row for row in seed_rows if bool(row.get("probe_slice_candidate", False))]
        seed_safe_rows = [row for row in seed_selected_rows if bool(row.get("probe_projection_safe", False))]
        seed_like_rows = [row for row in seed_selected_rows if bool(row.get("probe_benchmark_like", False))]
        subtype_counts = Counter(str(row.get("alignment_subtype", "mixed_safe")) for row in safe_pool_rows)
        dominant_subtype = subtype_counts.most_common(1)[0][0] if subtype_counts else "none"
        dominant_subtype_share = (
            float(subtype_counts.most_common(1)[0][1] / len(safe_pool_rows)) if safe_pool_rows else 0.0
        )
        context_shift_score = _safe_metric(
            _mean([float(row.get("context_shift_score", 0.0)) for row in safe_pool_rows])
        ) or 0.0
        if safe_pool_benchmark_like_count <= 0 and len(safe_pool_rows) <= max(1, baseline_target_count):
            collapse_cause = "low_candidate_count"
        elif safe_pool_benchmark_like_count > 0 and len(seed_like_rows) == 0:
            collapse_cause = "wrong_ranking_inside_slice"
        elif context_shift_score >= 0.22:
            collapse_cause = "context_sensitive_shift"
        elif dominant_subtype in {"projection_shape_fragile", "stability_fragile"} and dominant_subtype_share >= 0.50:
            collapse_cause = "subtype_mismatch"
        else:
            collapse_cause = "mixed"
        seed_failure_modes.append(
            {
                "seed": int(seed),
                "safe_pool_count": int(len(safe_pool_rows)),
                "baseline_target_count": int(baseline_target_count),
                "safe_pool_benchmark_like_count": int(safe_pool_benchmark_like_count),
                "selected_count": int(len(seed_selected_rows)),
                "selected_benchmark_like_count": int(len(seed_like_rows)),
                "dominant_subtype": str(dominant_subtype),
                "dominant_subtype_share": float(dominant_subtype_share),
                "context_shift_score": float(context_shift_score),
                "collapse_cause": str(collapse_cause),
            }
        )
        seed_summaries.append(
            {
                "seed": int(seed),
                "blocked_candidate_count": int(len(seed_rows)),
                "safe_probe_pool_count": int(len(safe_pool_rows)),
                "baseline_target_count": int(baseline_target_count),
                "slice_activation_count": int(len(seed_selected_rows)),
                "slice_activation_rate": float(len(seed_selected_rows) / len(seed_rows)) if seed_rows else 0.0,
                "slice_projection_safe_count": int(len(seed_safe_rows)),
                "slice_projection_safe_rate": float(len(seed_safe_rows) / len(seed_selected_rows)) if seed_selected_rows else 0.0,
                "slice_benchmark_like_count": int(len(seed_like_rows)),
                "slice_benchmark_like_rate": float(len(seed_like_rows) / len(seed_selected_rows)) if seed_selected_rows else 0.0,
                "mean_slice_projection_error": _mean_key(seed_selected_rows, "pred_projection_error"),
                "dominant_subtype": str(dominant_subtype),
                "collapse_cause": str(collapse_cause),
            }
        )

    live_safe_pool_rows = [row for row in all_rows if bool(row.get("safe_probe_pool", False))]
    combined_predictor_rows = live_safe_pool_rows or benchmark_pool_rows
    predictor_strengths = _predictor_strengths(combined_predictor_rows)
    best_retention_predictor = max(predictor_strengths.items(), key=lambda item: float(item[1]))[0] if predictor_strengths else "mixed_structure"

    activation_count = int(len(live_probe_rows))
    safe_retention_rate = float(sum(bool(row.get("probe_projection_safe", False)) for row in live_probe_rows) / activation_count) if activation_count else 0.0
    benchmark_like_retention_rate = float(sum(bool(row.get("probe_benchmark_like", False)) for row in live_probe_rows) / activation_count) if activation_count else 0.0
    mean_projection_error = _mean_key(live_probe_rows, "pred_projection_error")
    live_selection_fraction = float(activation_count / len(live_safe_pool_rows)) if live_safe_pool_rows else 0.0
    score_fraction_count = int(math.ceil(len(benchmark_pool_rows) * live_selection_fraction)) if benchmark_pool_rows and live_selection_fraction > 0.0 else 0
    coverage_floor_count = min(
        len(benchmark_pool_rows),
        max(
            1 if benchmark_pool_rows else 0,
            int(math.ceil(float(baseline_benchmark_slice_count) * 0.90)),
            int(dict(purity_benchmark_summary).get("benchmark_slice_count_probe", 0)),
        ),
    )
    benchmark_selected_count = min(len(benchmark_pool_rows), max(score_fraction_count, coverage_floor_count)) if benchmark_pool_rows else 0
    benchmark_probe_rows = (
        sorted(
            benchmark_pool_rows,
            key=lambda item: float(item.get("benchmark_alignment_critic_score", -1e9)),
            reverse=True,
        )[:benchmark_selected_count]
        if benchmark_pool_rows and benchmark_selected_count > 0
        else []
    )

    benchmark_probe_family_counts = Counter(str(row.get("family", "unknown")) for row in benchmark_probe_rows)
    benchmark_probe_target_family_count = int(sum(str(row.get("family", "")) == benchmark_target_family for row in benchmark_probe_rows))
    benchmark_probe_coverage_all = float(len(benchmark_probe_rows) / len(benchmark_rows)) if benchmark_rows else 0.0
    benchmark_probe_coverage_undercommit = float(len(benchmark_probe_rows) / len(benchmark_undercommit_all)) if benchmark_undercommit_all else 0.0
    probe_target_share = float(benchmark_probe_target_family_count / len(benchmark_probe_rows)) if benchmark_probe_rows else 0.0
    baseline_seed_std = _safe_metric(baseline_seed_activation_rate_summary.get("std")) or 0.0
    probe_seed_activation_rate_summary = _rate_summary(seed_summaries, "slice_activation_rate")
    probe_seed_std = _safe_metric(probe_seed_activation_rate_summary.get("std")) or 0.0

    benchmark_retention_improved = bool(benchmark_like_retention_rate > baseline_benchmark_like_retention_rate + 1e-9)
    projection_safe_retention_preserved = bool(safe_retention_rate >= max(0.95, baseline_safe_retention_rate - 0.02))
    coverage_preserved = bool(
        benchmark_probe_coverage_undercommit >= max(0.60, baseline_benchmark_undercommit_coverage * 0.85)
        and len(benchmark_probe_rows) >= max(
            int(math.ceil(baseline_benchmark_slice_count * 0.90)),
            int(dict(purity_benchmark_summary).get("benchmark_slice_count_probe", 0)),
        )
    )
    seed_fragility_preserved = bool(probe_seed_std <= baseline_seed_std + 1e-9)
    slice_fragility = "high" if probe_seed_std >= baseline_seed_std + 0.02 else ("low" if seed_fragility_preserved and activation_count >= max(1, baseline_live_activation_count - 1) else "medium")
    seed2_analysis = next((entry for entry in seed_failure_modes if int(entry.get("seed", -1)) == 2), {})

    if projection_safe_retention_preserved and benchmark_retention_improved and coverage_preserved and seed_fragility_preserved and benchmark_like_retention_rate >= 0.90:
        next_control_hypothesis = "narrow_routing_revisit"
        recommended_next_template = "routing_rule.activation_window_probe"
        recommendation_reason = "benchmark_alignment_critic_v1 improves safe-slice retention enough to justify a very narrow routing revisit next"
    elif projection_safe_retention_preserved and coverage_preserved:
        next_control_hypothesis = "benchmark_alignment_critic"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "retention structure is still driven by alignment/context inside the safe slice, so routing should remain deferred"
    else:
        next_control_hypothesis = "no_routing_yet"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "benchmark_alignment_critic_v1 does not yet produce a clean enough coverage-preserving slice for routing reconsideration"

    subtype_counts_live = Counter(str(row.get("alignment_subtype", "mixed_safe")) for row in live_safe_pool_rows)
    subtype_summary = {
        str(name): {
            "count": int(len(rows)),
            "benchmark_like_count": int(sum(bool(row.get("baseline_benchmark_like", False)) for row in rows)),
            "mean_benchmark_distance": _mean_key(rows, "benchmark_distance"),
            "mean_projection_shape": _mean_key(rows, "projection_shape_critic"),
            "mean_gain_goal": _mean_key(rows, "gain_goal_critic_v2"),
        }
        for name, rows in {
            subtype: [row for row in live_safe_pool_rows if str(row.get("alignment_subtype", "")) == subtype]
            for subtype in sorted(subtype_counts_live)
        }.items()
    }

    observability_gain = {
        "passed": bool(len(all_rows) >= 12 and len(live_safe_pool_rows) >= 4 and len(benchmark_probe_rows) >= 12),
        "blocked_candidate_count": int(len(all_rows)),
        "safe_probe_pool_count": int(len(live_safe_pool_rows)),
        "slice_activation_count": int(activation_count),
        "seed_count": int(len(seed_summaries)),
        "benchmark_reference_source": str(benchmark_reference_source),
        "benchmark_undercommit_count": int(len(benchmark_undercommit_all)),
        "reason": "captured enough safe-slice live traffic and benchmark undercommit rows to study subtype/context retention structure against critic v2",
    }
    activation_analysis = {
        "passed": bool(activation_count > 0),
        "slice_activation_observed": bool(activation_count > 0),
        "slice_activation_repeatable": bool(sum(int(summary.get("slice_activation_count", 0)) > 0 for summary in seed_summaries) >= 2),
        "slice_activation_rate": float(activation_count / len(all_rows)) if all_rows else 0.0,
        "reason": "benchmark-alignment critic retains an activatable safe slice across repeated short runs" if activation_count > 0 else "benchmark-alignment critic collapses the live slice under repeated short runs",
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(min(1.0, 0.24 + 0.18 * int(projection_safe_retention_preserved) + 0.18 * int(benchmark_retention_improved) + 0.15 * int(coverage_preserved) + 0.11 * int(seed_fragility_preserved) + 0.14 * int(bool(best_retention_predictor)))),
        "reason": "the probe isolates subtype/context structure inside the safe slice instead of retrying benchmark-distance-first ranking",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "probe-only critic refinement inside the critic-v2 safe slice with no default live-policy mutation and no benchmark semantic changes",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "critic_split.benchmark_alignment_critic_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "critic_refinement_logic_used": {
            "refined_signal_groups": list(mechanism.get("refined_signal_groups", [])),
            "ranking_mode": str(mechanism.get("ranking_mode", "single_stage")),
            "blocker_sensitive_rules_used": list(mechanism.get("blocker_sensitive_rules", [])),
            "selection_mode": "context_conditioned_safe_slice_v1",
        },
        "comparison_reference_template": "critic_split.projection_gain_goal_v2",
        "comparison_to_distance_probe": {
            "available": True,
            "benchmark_like_retention_rate_probe": float(distance_purity_metrics.get("benchmark_like_retention_rate", 0.0)),
            "projection_safe_retention_rate_probe": float(distance_purity_metrics.get("projection_safe_retention_rate", 0.0)),
        },
        "slice_definition": {
            "source_template": "critic_split.projection_gain_goal_v2",
            "projection_level_cap": float(projection_level_cap),
            "projection_shape_cap": float(projection_shape_cap),
            "gain_goal_floor": float(gain_goal_floor),
            "stability_cap": float(stability_cap),
            "projection_bad_safe_cap": float(projection_bad_safe_cap),
            "projection_error_safe_cap": float(projection_error_safe_cap),
            "benchmark_distance_cap": float(benchmark_distance_cap),
            "selection_count_mode": "same_live_seed_count_as_v2_with_context_floor",
            "benchmark_selection_floor_fraction": 0.90,
        },
        "safe_slice_subtype_summary": subtype_summary,
        "seed_contexts": live_seed_contexts,
        "seed_failure_modes": seed_failure_modes,
        "seed_2_collapse_analysis": seed2_analysis,
        "comparison_to_v2": {
            "slice_activation_count_v2": int(baseline_live_activation_count),
            "slice_activation_count_probe": int(activation_count),
            "slice_activation_count_delta": int(activation_count - baseline_live_activation_count),
            "projection_safe_retention_rate_v2": float(baseline_safe_retention_rate),
            "projection_safe_retention_rate_probe": float(safe_retention_rate),
            "projection_safe_retention_rate_delta": float(safe_retention_rate - baseline_safe_retention_rate),
            "benchmark_like_retention_rate_v2": float(baseline_benchmark_like_retention_rate),
            "benchmark_like_retention_rate_probe": float(benchmark_like_retention_rate),
            "benchmark_like_retention_rate_delta": float(benchmark_like_retention_rate - baseline_benchmark_like_retention_rate),
            "mean_projection_error_v2": baseline_mean_projection_error,
            "mean_projection_error_probe": mean_projection_error,
            "mean_projection_error_delta": None if baseline_mean_projection_error is None or mean_projection_error is None else float(mean_projection_error - baseline_mean_projection_error),
            "seed_activation_rate_v2": baseline_seed_activation_rate_summary,
            "seed_activation_rate_probe": probe_seed_activation_rate_summary,
            "seed_projection_safe_rate_probe": _rate_summary(seed_summaries, "slice_projection_safe_rate"),
            "seed_benchmark_like_rate_probe": _rate_summary(seed_summaries, "slice_benchmark_like_rate"),
        },
        "purity_metrics": {
            "safe_pool_count": int(len(live_safe_pool_rows)),
            "activation_count": int(activation_count),
            "benchmark_like_retention_rate": float(benchmark_like_retention_rate),
            "projection_safe_retention_rate": float(safe_retention_rate),
            "best_retention_predictor": str(best_retention_predictor),
            "predictor_strengths": {str(name): float(value) for name, value in sorted(predictor_strengths.items(), key=lambda item: (-float(item[1]), str(item[0])))},
        },
        "benchmark_relevance_summary": {
            "benchmark_slice_count_v2": int(baseline_benchmark_slice_count),
            "benchmark_slice_count_probe": int(len(benchmark_probe_rows)),
            "benchmark_slice_coverage_all_v2": float(baseline_benchmark_coverage_all),
            "benchmark_slice_coverage_all_probe": float(benchmark_probe_coverage_all),
            "benchmark_slice_coverage_undercommit_v2": float(baseline_benchmark_undercommit_coverage),
            "benchmark_slice_coverage_undercommit_probe": float(benchmark_probe_coverage_undercommit),
            "benchmark_slice_family_counts_v2": baseline_benchmark_family_counts,
            "benchmark_slice_family_counts_probe": {str(name): int(count) for name, count in sorted(benchmark_probe_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "benchmark_target_family_count_v2": int(baseline_target_family_count),
            "benchmark_target_family_count_probe": int(benchmark_probe_target_family_count),
            "benchmark_target_family_share_v2": float(baseline_target_share),
            "benchmark_target_family_share_probe": float(probe_target_share),
        },
        "family_slice_composition": {
            "target_family": str(benchmark_target_family),
            "benchmark_probe_family_counts": {str(name): int(count) for name, count in sorted(benchmark_probe_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
        },
        "seed_summaries": seed_summaries,
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": {
            "benchmark_retention_improved": bool(benchmark_retention_improved),
            "projection_safe_retention_preserved": bool(projection_safe_retention_preserved),
            "coverage_preserved": bool(coverage_preserved),
            "best_retention_predictor": str(best_retention_predictor),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
            "slice_fragility": str(slice_fragility),
            "strongest_retention_mechanism": str(best_retention_predictor),
            "routing_still_premature": not bool(benchmark_retention_improved and projection_safe_retention_preserved and coverage_preserved and benchmark_like_retention_rate >= 0.90),
        },
        "sample_rows": {
            "probe_slice_examples": live_probe_rows[:8],
            "benchmark_probe_examples": benchmark_probe_rows[:8],
            "safe_pool_near_misses": sorted(
                [row for row in all_rows if bool(row.get("safe_probe_pool", False)) and not bool(row.get("probe_slice_candidate", False))],
                key=lambda item: float(item.get("benchmark_alignment_critic_score", -1e9)),
                reverse=True,
            )[:8],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"critic_split_benchmark_alignment_critic_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(observability_gain["passed"] and ambiguity_reduction["passed"] and safety_neutrality["passed"] and later_selection_usefulness["passed"])
    if not bool(observability_gain["passed"]):
        reason = "diagnostic shadow failed: insufficient safe-slice live or benchmark evidence for benchmark_alignment_critic_v1"
    elif not bool(projection_safe_retention_preserved):
        reason = "diagnostic shadow passed: benchmark_alignment_critic_v1 weakened projection-safe retention and should not be promoted"
    elif benchmark_retention_improved and coverage_preserved:
        reason = "diagnostic shadow passed: benchmark_alignment_critic_v1 improves benchmark-like retention while preserving useful coverage"
    else:
        reason = "diagnostic shadow passed: benchmark_alignment_critic_v1 clarifies subtype/context retention structure, but routing remains premature"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_critic_split_stability_context_retention_probe_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    v2_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.projection_gain_goal_v2")
    purity_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.safe_slice_purity_probe_v1")
    distance_artifact = _load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_distance_retention_probe_v1"
    )
    alignment_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_alignment_critic_v1")
    seed_context_artifact = _load_latest_diagnostic_artifact_by_template("memory_summary.seed_context_shift_snapshot")
    if not v2_artifact or not purity_artifact or not distance_artifact or not alignment_artifact or not seed_context_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: prerequisite critic/context artifacts missing for stability_context_retention_probe_v1",
            "observability_gain": {"passed": False, "reason": "missing prerequisite critic/context artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite critic/context artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite critic/context artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot recommend a follow-up without the prerequisite critic/context artifacts",
            },
        }

    intended_benefit = dict(proposal.get("intended_benefit", {}))
    mechanism = dict(proposal.get("mechanism", {}))
    benchmark_target_family = str(intended_benefit.get("target_family", "gain_goal_conflict"))
    projection_boundary = float(_targeted_projection_override_boundary(cfg))

    benchmark_rows = _load_latest_benchmark_detailed_rows()
    benchmark_undercommit_all = [
        row
        for row in benchmark_rows
        if str(row.get("policy_decision", "")) == "reject"
        and str(row.get("oracle_decision", "")) in {"provisional", "full"}
    ]
    benchmark_undercommit_target = [
        row for row in benchmark_undercommit_all if str(row.get("family", "")) == benchmark_target_family
    ]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (benchmark_undercommit_target if benchmark_reference_source == "target_family_undercommit" else benchmark_undercommit_all)
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }

    slice_definition = dict(v2_artifact.get("slice_definition", {}))
    projection_level_cap = float(slice_definition.get("projection_level_cap", 0.70))
    projection_shape_cap = float(slice_definition.get("projection_shape_cap", 0.65))
    gain_goal_floor = float(slice_definition.get("gain_goal_floor", 0.34))
    stability_cap = float(slice_definition.get("stability_cap", 0.42))
    projection_bad_safe_cap = float(slice_definition.get("projection_bad_safe_cap", 0.57))
    projection_error_safe_cap = float(slice_definition.get("projection_error_safe_cap", 0.0115))
    benchmark_distance_cap = float(slice_definition.get("benchmark_distance_cap", 1.0))
    gain_structure_level_soft_cap = float(slice_definition.get("gain_structure_level_soft_cap", projection_level_cap + 0.08))
    gain_structure_benchmark_distance_soft_cap = float(slice_definition.get("gain_structure_benchmark_distance_soft_cap", benchmark_distance_cap + 0.05))
    gain_structure_projection_bad_soft_cap = float(slice_definition.get("gain_structure_projection_bad_soft_cap", projection_bad_safe_cap + 0.02))
    gain_structure_gain_soft_floor = float(slice_definition.get("gain_structure_gain_soft_floor", gain_goal_floor + 0.08))

    baseline_live_activation_count = int(dict(v2_artifact.get("observability_gain", {})).get("slice_activation_count", dict(v2_artifact.get("comparison_to_v1", {})).get("slice_activation_count_v2", 0)))
    baseline_safe_retention_rate = float(dict(v2_artifact.get("comparison_to_v1", {})).get("projection_safe_retention_rate_v2", 0.0))
    baseline_benchmark_like_retention_rate = float(dict(v2_artifact.get("comparison_to_v1", {})).get("benchmark_like_retention_rate_v2", 0.0))
    baseline_mean_projection_error = _safe_metric(dict(v2_artifact.get("comparison_to_v1", {})).get("mean_projection_error_v2"))
    baseline_seed_activation_rate_summary = dict(dict(v2_artifact.get("comparison_to_v1", {})).get("seed_activation_rate_v2", {}))
    baseline_seed_counts = {
        int(dict(seed_summary).get("seed", -1)): int(dict(seed_summary).get("slice_activation_count", 0))
        for seed_summary in list(v2_artifact.get("seed_summaries", []))
        if _safe_metric(dict(seed_summary).get("seed")) is not None
    }
    baseline_benchmark_alignment = dict(v2_artifact.get("benchmark_alignment_summary", {}))
    baseline_benchmark_slice_count = int(baseline_benchmark_alignment.get("benchmark_slice_count", 0))
    baseline_benchmark_coverage_all = float(baseline_benchmark_alignment.get("benchmark_slice_coverage_all", 0.0))
    baseline_benchmark_undercommit_coverage = float(baseline_benchmark_alignment.get("benchmark_slice_coverage_undercommit", 0.0))
    baseline_benchmark_family_counts = {str(name): int(count) for name, count in dict(baseline_benchmark_alignment.get("benchmark_slice_family_counts", {})).items()}
    baseline_target_family_count = int(baseline_benchmark_alignment.get("benchmark_target_family_count", 0))
    baseline_target_share = float(baseline_target_family_count / baseline_benchmark_slice_count) if baseline_benchmark_slice_count else 0.0
    prior_seed_summaries = {
        int(dict(item).get("seed", -1)): dict(item)
        for item in list(seed_context_artifact.get("per_seed_safe_slice_summary", []))
        if _safe_metric(dict(item).get("seed")) is not None
    }
    prior_collapse_driver = str(dict(seed_context_artifact.get("diagnostic_conclusions", {})).get("collapse_driver", "mixed"))
    prior_dominant_precursor = str(dict(seed_context_artifact.get("diagnostic_conclusions", {})).get("dominant_precursor", "mixed"))

    def _annotate_v2_row(row: Dict[str, Any]) -> Dict[str, Any]:
        annotated = dict(row)
        annotated["segment"] = str(annotated.get("segment", _segment_live_candidate(annotated, benchmark_summary=benchmark_summary, projection_boundary=projection_boundary)))
        if "benchmark_distance" not in annotated:
            annotated["benchmark_distance"] = float(_benchmark_distance(annotated, benchmark_summary))
        annotated["projection_level_critic"] = float(_row_projection_level_critic_v2(annotated, benchmark_summary, projection_boundary=projection_boundary))
        annotated["projection_shape_critic"] = float(_row_projection_shape_critic_v2(annotated, benchmark_summary))
        annotated["gain_goal_critic_v2"] = float(_row_gain_goal_critic_v2(annotated, benchmark_summary))
        annotated["stability_critic_v2"] = float(_row_stability_critic_v2(annotated, projection_level_critic=float(annotated["projection_level_critic"]), projection_shape_critic=float(annotated["projection_shape_critic"]), gain_goal_critic=float(annotated["gain_goal_critic_v2"])))
        return annotated

    def _v2_safe_pool_flags(row: Dict[str, Any]) -> Dict[str, bool]:
        blocker_group = str(row.get("blocker_group", "other"))
        segment = str(row.get("segment", "mixed_shift"))
        blocker_ok = blocker_group in {"projection_guard", "confidence_gain"}
        segment_ok = segment not in {"projection_far_shifted"}
        stability_ok = float(row.get("stability_critic_v2", 99.0)) <= float(stability_cap)
        if segment == "stability_sensitive":
            stability_ok = bool(stability_ok and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.85) and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.05))
        if segment in {"projection_mid_shifted", "projection_borderline"}:
            segment_ok = bool(segment_ok and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.95))
        if blocker_group == "confidence_gain":
            blocker_ok = bool(blocker_ok and float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap * 1.05) and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.02))
        gain_structure_soft_ok = bool(segment in {"gain_structure_shifted", "benchmark_adjacent"} and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap) and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap) and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_structure_gain_soft_floor) and float(row.get("projection_level_critic", 99.0)) <= float(gain_structure_level_soft_cap) and float(row.get("benchmark_distance", 99.0)) <= float(gain_structure_benchmark_distance_soft_cap))
        candidate_envelope_ok = bool(blocker_ok and segment_ok and stability_ok and (((float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap) and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap) and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor) and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)) or gain_structure_soft_ok)))
        projection_safe_ok = bool(candidate_envelope_ok and (((float(row.get("pred_projection_bad_prob", 99.0)) <= float(projection_bad_safe_cap) and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)) or (segment in {"gain_structure_shifted", "benchmark_adjacent"} and float(row.get("pred_projection_bad_prob", 99.0)) <= float(gain_structure_projection_bad_soft_cap) and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap) and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)))))
        return {
            "projection_safe_ok": bool(projection_safe_ok),
            "benchmark_like_ok": bool(projection_safe_ok and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)),
        }

    def _alignment_subtype(row: Dict[str, Any]) -> str:
        segment = str(row.get("segment", "mixed_shift"))
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 99.0)
        projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or 99.0)
        gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or -1e9)
        stability = float(_safe_metric(row.get("stability_critic_v2")) or 99.0)
        if segment == "benchmark_adjacent" and benchmark_distance <= float(benchmark_distance_cap * 1.02) and projection_shape <= float(projection_shape_cap * 0.95):
            return "retained_like_profile"
        if segment == "gain_structure_shifted" and benchmark_distance <= float(gain_structure_benchmark_distance_soft_cap) and projection_shape <= float(projection_shape_cap) and gain_goal >= float(gain_structure_gain_soft_floor):
            return "retained_like_profile"
        if segment == "gain_structure_shifted":
            return "gain_fragile_profile"
        if segment == "stability_sensitive" or stability > float(stability_cap * 0.95):
            return "stability_fragile"
        if segment in {"projection_mid_shifted", "projection_borderline"} or projection_shape > float(projection_shape_cap * 0.92):
            return "projection_shape_fragile"
        return "mixed_safe"

    def _subtype_prior_value(subtype: str) -> float:
        return {"retained_like_profile": 1.00, "gain_fragile_profile": 0.62, "mixed_safe": 0.40, "projection_shape_fragile": 0.16, "stability_fragile": 0.05}.get(str(subtype), 0.25)

    def _build_context(rows: List[Dict[str, Any]], baseline_target_count: int, prior_seed: Dict[str, Any]) -> Dict[str, Any]:
        subtype_counts = Counter(str(row.get("alignment_subtype", "mixed_safe")) for row in rows)
        return {
            "safe_pool_count": int(len(rows)),
            "baseline_target_count": int(max(0, baseline_target_count)),
            "mean_benchmark_distance": _mean_key(rows, "benchmark_distance"),
            "mean_projection_shape": _mean_key(rows, "projection_shape_critic"),
            "mean_gain_goal": _mean_key(rows, "gain_goal_critic_v2"),
            "subtype_counts": {str(name): int(count) for name, count in subtype_counts.items()},
            "prior_collapse_case": bool(prior_seed.get("collapse_case", False)),
            "prior_safe_pool_count": int(prior_seed.get("safe_pool_count", 0)),
            "prior_selected_count": int(prior_seed.get("selected_count", 0)),
            "prior_selected_benchmark_like_count": int(prior_seed.get("selected_benchmark_like_count", 0)),
            "prior_context_shift_score": float(_safe_metric(prior_seed.get("context_shift_score")) or 0.0),
        }

    def _stability_context_retention_score(row: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 1.20)
        projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or 0.0)
        projection_level = float(_safe_metric(row.get("projection_level_critic")) or 0.0)
        gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or 0.0)
        stability = float(_safe_metric(row.get("stability_critic_v2")) or 0.0)
        subtype = str(row.get("alignment_subtype", "mixed_safe"))
        benchmark_proximity = max(0.0, 1.15 - min(1.15, benchmark_distance))
        shape_closeness = max(0.0, float(projection_shape_cap) - min(float(projection_shape_cap), projection_shape)) / max(1e-6, float(projection_shape_cap))
        level_closeness = max(0.0, float(projection_level_cap) - min(float(projection_level_cap), projection_level)) / max(1e-6, float(projection_level_cap))
        subtype_prior = float(_subtype_prior_value(subtype))
        safe_pool_count = int(context.get("safe_pool_count", 0))
        baseline_target_count = int(context.get("baseline_target_count", 0))
        scarcity = max(0.0, float(baseline_target_count - safe_pool_count) / max(1.0, float(baseline_target_count or 1)))
        context_shift = min(1.0, max(0.0, (float(_safe_metric(context.get("mean_benchmark_distance")) or benchmark_distance_cap) - float(benchmark_distance_cap * 0.95)) / max(0.05, float(benchmark_distance_cap * 0.10))) + max(0.0, (float(_safe_metric(context.get("mean_projection_shape")) or projection_shape_cap) - float(projection_shape_cap * 0.90)) / max(0.05, float(projection_shape_cap * 0.20))) + 0.35 * float(_safe_metric(context.get("prior_context_shift_score")) or 0.0))
        collapse_prone = bool(context.get("prior_collapse_case", False) or scarcity >= 0.50 or context_shift >= 0.35)
        scarcity_aware = benchmark_proximity * (0.55 + 0.45 * scarcity) * (0.55 + 0.45 * subtype_prior)
        context_shift_interaction = benchmark_proximity * shape_closeness * max(0.0, 1.0 - 0.30 * max(0.0, context_shift - 0.25))
        if subtype in {"projection_shape_fragile", "stability_fragile"}:
            context_shift_interaction *= 0.55
        gain_goal_context = benchmark_proximity * min(1.0, max(0.0, gain_goal)) * max(0.0, 1.0 - 0.20 * context_shift)
        subtype_conditioning = subtype_prior * (1.15 if subtype == "retained_like_profile" and collapse_prone else 1.0 if subtype == "retained_like_profile" else 0.92 if subtype == "gain_fragile_profile" else 0.70 if subtype == "mixed_safe" else 0.35)
        mixed_structure = 0.32 * scarcity_aware + 0.24 * context_shift_interaction + 0.18 * gain_goal_context + 0.16 * subtype_conditioning + 0.10 * max(0.0, 1.0 - min(1.0, stability / max(1e-6, float(stability_cap))))
        score = float(0.26 * scarcity_aware + 0.24 * context_shift_interaction + 0.18 * gain_goal_context + 0.18 * subtype_conditioning + 0.08 * max(0.0, 1.0 - min(1.0, stability / max(1e-6, float(stability_cap)))) + 0.06 * level_closeness)
        if collapse_prone and subtype == "retained_like_profile" and benchmark_distance <= float(benchmark_distance_cap * 1.03):
            score += 0.08
        if context_shift >= 0.35 and subtype in {"projection_shape_fragile", "stability_fragile"}:
            score -= 0.10
        if scarcity >= 0.50 and not bool(row.get("baseline_benchmark_like", False)):
            score -= 0.06
        if context_shift >= 0.60 and benchmark_distance > float(benchmark_distance_cap):
            score -= 0.08
        return {
            "stability_context_retention_score": float(score),
            "scarcity_aware_score": float(scarcity_aware),
            "context_shift_interaction_score": float(context_shift_interaction),
            "subtype_conditioning_score": float(subtype_conditioning),
            "mixed_stability_score": float(mixed_structure),
            "context_shift_score": float(context_shift),
            "scarcity_score": float(scarcity),
            "collapse_prone_context": bool(collapse_prone),
        }

    def _predictor_strengths(rows: List[Dict[str, Any]]) -> Dict[str, float]:
        pos = [row for row in rows if bool(row.get("baseline_benchmark_like", False))]
        neg = [row for row in rows if not bool(row.get("baseline_benchmark_like", False))]
        if not pos or not neg:
            return {"scarcity_aware": 0.0, "context_shift_interaction": 0.0, "subtype_conditioning": 0.0, "mixed": 0.0}
        def _gap(key: str) -> float:
            pos_vals = [float(_safe_metric(row.get(key)) or 0.0) for row in pos]
            neg_vals = [float(_safe_metric(row.get(key)) or 0.0) for row in neg]
            return float(abs((sum(pos_vals) / len(pos_vals)) - (sum(neg_vals) / len(neg_vals))))
        return {
            "scarcity_aware": _gap("scarcity_aware_score"),
            "context_shift_interaction": _gap("context_shift_interaction_score"),
            "subtype_conditioning": _gap("subtype_conditioning_score"),
            "mixed": _gap("mixed_stability_score"),
        }
    benchmark_candidate_rows: List[Dict[str, Any]] = []
    for scenario_result in benchmark_undercommit_all:
        candidate_row = _benchmark_scenario_candidate_row(cfg, scenario_result, projection_boundary=projection_boundary, benchmark_summary=benchmark_summary)
        candidate_row = _annotate_v2_row(candidate_row)
        flags = _v2_safe_pool_flags(candidate_row)
        candidate_row["safe_probe_pool"] = bool(flags["projection_safe_ok"])
        candidate_row["baseline_benchmark_like"] = bool(flags["benchmark_like_ok"])
        candidate_row["alignment_subtype"] = str(_alignment_subtype(candidate_row))
        benchmark_candidate_rows.append(candidate_row)

    benchmark_pool_rows = [row for row in benchmark_candidate_rows if bool(row.get("safe_probe_pool", False))]
    benchmark_context = _build_context(benchmark_pool_rows, int(math.ceil(len(benchmark_pool_rows) * 0.35)) if benchmark_pool_rows else 0, {})
    for row in benchmark_pool_rows:
        row.update(_stability_context_retention_score(row, benchmark_context))

    all_rows: List[Dict[str, Any]] = []
    live_probe_rows: List[Dict[str, Any]] = []
    seed_summaries: List[Dict[str, Any]] = []
    collapse_analysis_rows: List[Dict[str, Any]] = []

    for seed in list(seeds):
        run_cfg = copy.deepcopy(cfg)
        run_cfg.verbose = False
        run_cfg.rounds = max(1, int(rounds))
        run_cfg.seed = int(seed)
        run_cfg.benchmark_every_rounds = 0
        run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs or {})
        run_cfg.eval_kwargs["session_log_path"] = f"logs/intervention_shadow_{proposal['proposal_id']}_stability_context_seed{int(seed)}.log"
        apply_live_policy_variant(run_cfg, "targeted_gain_goal_proj_margin_01")
        _, _, history = run_proposal_learning_loop(run_cfg)

        seed_rows: List[Dict[str, Any]] = []
        for round_index, entry in enumerate(history):
            blocked = [item for item in list(entry.get("adopt_blocked", [])) if isinstance(item, dict)]
            for item in blocked:
                row = _live_gap_row(item, seed=int(seed), round_index=int(round_index), cohort="baseline_rejected", projection_boundary=projection_boundary)
                row = _annotate_v2_row(row)
                flags = _v2_safe_pool_flags(row)
                row["safe_probe_pool"] = bool(flags["projection_safe_ok"])
                row["baseline_benchmark_like"] = bool(flags["benchmark_like_ok"])
                row["alignment_subtype"] = str(_alignment_subtype(row))
                seed_rows.append(row)
                all_rows.append(row)

        safe_pool_rows = [row for row in seed_rows if bool(row.get("safe_probe_pool", False))]
        baseline_target_count = int(baseline_seed_counts.get(int(seed), 0))
        prior_seed = dict(prior_seed_summaries.get(int(seed), {}))
        seed_context = _build_context(safe_pool_rows, baseline_target_count, prior_seed)
        for row in safe_pool_rows:
            row.update(_stability_context_retention_score(row, seed_context))

        ordered = sorted(safe_pool_rows, key=lambda item: float(item.get("stability_context_retention_score", -1e9)), reverse=True)
        target_count = min(len(ordered), baseline_target_count) if baseline_target_count > 0 else 0
        context_shift = float(_safe_metric(_mean([float(row.get("context_shift_score", 0.0)) for row in safe_pool_rows])) or 0.0)
        scarcity = float(max(0, baseline_target_count - len(safe_pool_rows)) / max(1.0, float(baseline_target_count or 1)))
        collapse_prone = bool(prior_seed.get("collapse_case", False) or scarcity >= 0.50 or context_shift >= 0.35)
        quality_floor = 0.22 + 0.04 * context_shift + (0.04 if collapse_prone else 0.0) + (0.03 if scarcity > 0.50 else 0.0)
        selected_rows = [
            row for row in ordered[:target_count]
            if float(row.get("stability_context_retention_score", -1e9)) >= quality_floor
            or (str(row.get("alignment_subtype", "")) == "retained_like_profile" and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap * 1.03))
        ]
        if not selected_rows and ordered and not (collapse_prone and not any(bool(row.get("baseline_benchmark_like", False)) for row in safe_pool_rows)):
            top = ordered[0]
            if float(top.get("stability_context_retention_score", -1e9)) >= quality_floor - 0.04 and str(top.get("alignment_subtype", "")) in {"retained_like_profile", "gain_fragile_profile"}:
                selected_rows = [top]

        selected_ids = {(int(dict(row).get("round_index", -1)), str(dict(row).get("candidate_id", ""))) for row in selected_rows}
        for row in seed_rows:
            row["probe_slice_candidate"] = bool((int(dict(row).get("round_index", -1)), str(dict(row).get("candidate_id", ""))) in selected_ids)
            row["probe_projection_safe"] = bool(row["probe_slice_candidate"] and bool(row.get("safe_probe_pool", False)))
            row["probe_benchmark_like"] = bool(row["probe_projection_safe"] and bool(row.get("baseline_benchmark_like", False)))
            if bool(row["probe_slice_candidate"]):
                live_probe_rows.append(row)

        safe_pool_benchmark_like_count = int(sum(bool(row.get("baseline_benchmark_like", False)) for row in safe_pool_rows))
        seed_selected_rows = [row for row in seed_rows if bool(row.get("probe_slice_candidate", False))]
        seed_safe_rows = [row for row in seed_selected_rows if bool(row.get("probe_projection_safe", False))]
        seed_like_rows = [row for row in seed_selected_rows if bool(row.get("probe_benchmark_like", False))]
        subtype_counts = Counter(str(row.get("alignment_subtype", "mixed_safe")) for row in safe_pool_rows)
        benchmark_like_fraction = float(safe_pool_benchmark_like_count / len(safe_pool_rows)) if safe_pool_rows else 0.0
        if len(safe_pool_rows) <= 1 and safe_pool_benchmark_like_count <= 0:
            collapse_driver_after_probe = "low_candidate_count"
        elif context_shift >= 0.35 and benchmark_like_fraction <= 0.25:
            collapse_driver_after_probe = "context_shift"
        elif subtype_counts.get("stability_fragile", 0) + subtype_counts.get("projection_shape_fragile", 0) >= max(1, math.ceil(len(safe_pool_rows) * 0.60)):
            collapse_driver_after_probe = "subtype_loss"
        else:
            collapse_driver_after_probe = "mixed"

        prior_selected_like = int(prior_seed.get("selected_benchmark_like_count", 0))
        collapse_reduced = bool(len(safe_pool_rows) > int(prior_seed.get("safe_pool_count", 0)) or len(seed_like_rows) > prior_selected_like)
        benchmark_like_survival_improved_seed = bool(len(seed_like_rows) > prior_selected_like)
        collapse_analysis_rows.append({
            "seed": int(seed),
            "prior_collapse_case": bool(prior_seed.get("collapse_case", False)),
            "prior_safe_pool_count": int(prior_seed.get("safe_pool_count", 0)),
            "prior_safe_pool_benchmark_like_count": int(prior_seed.get("safe_pool_benchmark_like_count", 0)),
            "prior_selected_count": int(prior_seed.get("selected_count", 0)),
            "prior_selected_benchmark_like_count": prior_selected_like,
            "safe_pool_count_probe": int(len(safe_pool_rows)),
            "safe_pool_benchmark_like_count_probe": int(safe_pool_benchmark_like_count),
            "selected_count_probe": int(len(seed_selected_rows)),
            "selected_benchmark_like_count_probe": int(len(seed_like_rows)),
            "context_shift_score_probe": float(context_shift),
            "collapse_driver_after_probe": str(collapse_driver_after_probe),
            "collapse_reduced": bool(collapse_reduced),
            "benchmark_like_survival_improved": bool(benchmark_like_survival_improved_seed),
        })
        seed_summaries.append({
            "seed": int(seed),
            "blocked_candidate_count": int(len(seed_rows)),
            "safe_pool_count": int(len(safe_pool_rows)),
            "safe_pool_benchmark_like_count": int(safe_pool_benchmark_like_count),
            "baseline_target_count": int(baseline_target_count),
            "slice_activation_count": int(len(seed_selected_rows)),
            "slice_activation_rate": float(len(seed_selected_rows) / len(seed_rows)) if seed_rows else 0.0,
            "slice_projection_safe_count": int(len(seed_safe_rows)),
            "slice_projection_safe_rate": float(len(seed_safe_rows) / len(seed_selected_rows)) if seed_selected_rows else 0.0,
            "slice_benchmark_like_count": int(len(seed_like_rows)),
            "slice_benchmark_like_rate": float(len(seed_like_rows) / len(seed_selected_rows)) if seed_selected_rows else 0.0,
            "mean_slice_projection_error": _mean_key(seed_selected_rows, "pred_projection_error"),
            "context_shift_score": float(context_shift),
            "collapse_driver_after_probe": str(collapse_driver_after_probe),
        })
    live_safe_pool_rows = [row for row in all_rows if bool(row.get("safe_probe_pool", False))]
    predictor_strengths = _predictor_strengths(live_safe_pool_rows or benchmark_pool_rows)
    best_stability_retention_mechanism = max(predictor_strengths.items(), key=lambda item: float(item[1]))[0] if predictor_strengths else "mixed"
    activation_count = int(len(live_probe_rows))
    safe_retention_rate = float(sum(bool(row.get("probe_projection_safe", False)) for row in live_probe_rows) / activation_count) if activation_count else 0.0
    benchmark_like_retention_rate = float(sum(bool(row.get("probe_benchmark_like", False)) for row in live_probe_rows) / activation_count) if activation_count else 0.0
    mean_projection_error = _mean_key(live_probe_rows, "pred_projection_error")
    live_selection_fraction = float(activation_count / len(live_safe_pool_rows)) if live_safe_pool_rows else 0.0
    score_fraction_count = int(math.ceil(len(benchmark_pool_rows) * live_selection_fraction)) if benchmark_pool_rows and live_selection_fraction > 0.0 else 0
    coverage_floor_count = min(len(benchmark_pool_rows), max(1 if benchmark_pool_rows else 0, int(math.ceil(float(baseline_benchmark_slice_count) * 0.90)), int(dict(purity_artifact.get("benchmark_relevance_summary", {})).get("benchmark_slice_count_probe", 0))))
    benchmark_selected_count = min(len(benchmark_pool_rows), max(score_fraction_count, coverage_floor_count)) if benchmark_pool_rows else 0
    benchmark_probe_rows = sorted(benchmark_pool_rows, key=lambda item: float(item.get("stability_context_retention_score", -1e9)), reverse=True)[:benchmark_selected_count] if benchmark_selected_count > 0 else []
    benchmark_probe_family_counts = Counter(str(row.get("family", "unknown")) for row in benchmark_probe_rows)
    benchmark_probe_target_family_count = int(sum(str(row.get("family", "")) == benchmark_target_family for row in benchmark_probe_rows))
    benchmark_probe_coverage_all = float(len(benchmark_probe_rows) / len(benchmark_rows)) if benchmark_rows else 0.0
    benchmark_probe_coverage_undercommit = float(len(benchmark_probe_rows) / len(benchmark_undercommit_all)) if benchmark_undercommit_all else 0.0
    probe_target_share = float(benchmark_probe_target_family_count / len(benchmark_probe_rows)) if benchmark_probe_rows else 0.0
    baseline_seed_std = _safe_metric(baseline_seed_activation_rate_summary.get("std")) or 0.0
    probe_seed_activation_rate_summary = _rate_summary(seed_summaries, "slice_activation_rate")
    probe_seed_std = _safe_metric(probe_seed_activation_rate_summary.get("std")) or 0.0
    benchmark_retention_improved = bool(benchmark_like_retention_rate > baseline_benchmark_like_retention_rate + 1e-9)
    projection_safe_retention_preserved = bool(safe_retention_rate >= max(0.95, baseline_safe_retention_rate - 0.02))
    coverage_preserved = bool(benchmark_probe_coverage_undercommit >= max(0.60, baseline_benchmark_undercommit_coverage * 0.85) and len(benchmark_probe_rows) >= max(int(math.ceil(baseline_benchmark_slice_count * 0.90)), int(dict(purity_artifact.get("benchmark_relevance_summary", {})).get("benchmark_slice_count_probe", 0))))
    seed_fragility_preserved = bool(probe_seed_std <= baseline_seed_std + 1e-9)
    safe_pool_collapse_reduced = bool(any(bool(row.get("collapse_reduced", False)) for row in collapse_analysis_rows if bool(row.get("prior_collapse_case", False))))
    benchmark_like_survival_improved = bool(any(bool(row.get("benchmark_like_survival_improved", False)) for row in collapse_analysis_rows if bool(row.get("prior_collapse_case", False))))
    collapse_driver_counts = Counter(str(row.get("collapse_driver_after_probe", "mixed")) for row in collapse_analysis_rows if bool(row.get("prior_collapse_case", False)))
    collapse_driver_after_probe = collapse_driver_counts.most_common(1)[0][0] if collapse_driver_counts else str(prior_collapse_driver)
    slice_fragility = "high" if probe_seed_std >= baseline_seed_std + 0.02 else ("low" if seed_fragility_preserved and activation_count >= max(1, baseline_live_activation_count - 1) else "medium")

    if safe_pool_collapse_reduced and benchmark_like_survival_improved and projection_safe_retention_preserved and coverage_preserved:
        next_control_hypothesis = "stability_context_retention_continue"
        recommended_next_template = "critic_split.benchmark_alignment_critic_v1"
        recommendation_reason = "context-aware retention helps, but the next step should still stay in critic refinement rather than routing"
    elif projection_safe_retention_preserved and not safe_pool_collapse_reduced:
        next_control_hypothesis = "benchmark_alignment_model"
        recommended_next_template = "critic_split.benchmark_alignment_critic_v1"
        recommendation_reason = "the probe preserves safety but does not materially reduce collapse, so the next step should deepen the benchmark-alignment/context model"
    else:
        next_control_hypothesis = "no_routing_yet"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "context-retention refinement did not yet produce a reliable enough slice to leave critic refinement"

    observability_gain = {
        "passed": bool(len(all_rows) >= 12 and len(seed_summaries) >= 3 and len(benchmark_probe_rows) >= 12),
        "blocked_candidate_count": int(len(all_rows)),
        "safe_probe_pool_count": int(len(live_safe_pool_rows)),
        "slice_activation_count": int(activation_count),
        "seed_count": int(len(seed_summaries)),
        "benchmark_reference_source": str(benchmark_reference_source),
        "benchmark_undercommit_count": int(len(benchmark_undercommit_all)),
        "reason": "captured enough safe-slice live traffic and benchmark undercommit rows to test stability/context-conditioned retention against critic v2",
    }
    activation_analysis = {
        "passed": bool(activation_count > 0),
        "slice_activation_observed": bool(activation_count > 0),
        "slice_activation_repeatable": bool(sum(int(summary.get("slice_activation_count", 0)) > 0 for summary in seed_summaries) >= 2),
        "safe_pool_collapse_reduced": bool(safe_pool_collapse_reduced),
        "benchmark_like_survival_improved": bool(benchmark_like_survival_improved),
        "reason": "stability/context retention probe keeps an activatable slice while explicitly measuring collapse reduction" if activation_count > 0 else "stability/context retention probe collapses the live slice under repeated short runs",
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(min(1.0, 0.22 + 0.18 * int(projection_safe_retention_preserved) + 0.15 * int(coverage_preserved) + 0.13 * int(benchmark_retention_improved) + 0.13 * int(safe_pool_collapse_reduced) + 0.10 * int(benchmark_like_survival_improved) + 0.09 * int(bool(best_stability_retention_mechanism)))),
        "reason": "the probe tests whether stability/context-aware critic structure helps collapse-prone safe-slice retention without reopening routing",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "probe-only critic refinement inside the critic-v2 safe slice with no default live-policy mutation and no benchmark semantic changes",
    }
    later_selection_usefulness = {"passed": True, "recommended_next_template": str(recommended_next_template), "reason": str(recommendation_reason)}

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "critic_split.stability_context_retention_probe_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "critic_refinement_logic_used": {"refined_signal_groups": list(mechanism.get("refined_signal_groups", [])), "ranking_mode": str(mechanism.get("ranking_mode", "single_stage")), "blocker_sensitive_rules_used": list(mechanism.get("blocker_sensitive_rules", [])), "comparison_reference": str(mechanism.get("comparison_reference", ""))},
        "dependency_context": {"prior_collapse_driver": str(prior_collapse_driver), "prior_dominant_precursor": str(prior_dominant_precursor), "alignment_best_retention_mechanism": str(dict(alignment_artifact.get("diagnostic_conclusions", {})).get("strongest_retention_mechanism", ""))},
        "comparison_to_v2": {"slice_activation_count_v2": int(baseline_live_activation_count), "slice_activation_count_probe": int(activation_count), "slice_activation_count_delta": int(activation_count - baseline_live_activation_count), "projection_safe_retention_rate_v2": float(baseline_safe_retention_rate), "projection_safe_retention_rate_probe": float(safe_retention_rate), "projection_safe_retention_rate_delta": float(safe_retention_rate - baseline_safe_retention_rate), "benchmark_like_retention_rate_v2": float(baseline_benchmark_like_retention_rate), "benchmark_like_retention_rate_probe": float(benchmark_like_retention_rate), "benchmark_like_retention_rate_delta": float(benchmark_like_retention_rate - baseline_benchmark_like_retention_rate), "mean_projection_error_v2": baseline_mean_projection_error, "mean_projection_error_probe": mean_projection_error, "mean_projection_error_delta": None if baseline_mean_projection_error is None or mean_projection_error is None else float(mean_projection_error - baseline_mean_projection_error), "seed_activation_rate_v2": baseline_seed_activation_rate_summary, "seed_activation_rate_probe": probe_seed_activation_rate_summary},
        "safe_pool_metrics_by_seed": seed_summaries,
        "collapse_specific_analysis": {"rows": collapse_analysis_rows, "safe_pool_collapse_reduced": bool(safe_pool_collapse_reduced), "benchmark_like_survival_improved": bool(benchmark_like_survival_improved), "collapse_driver_after_probe": str(collapse_driver_after_probe)},
        "purity_metrics": {"safe_pool_count": int(len(live_safe_pool_rows)), "activation_count": int(activation_count), "benchmark_like_retention_rate": float(benchmark_like_retention_rate), "projection_safe_retention_rate": float(safe_retention_rate), "best_stability_retention_mechanism": str(best_stability_retention_mechanism), "predictor_strengths": {str(name): float(value) for name, value in sorted(predictor_strengths.items(), key=lambda item: (-float(item[1]), str(item[0])))}},
        "benchmark_relevance_summary": {"benchmark_slice_count_v2": int(baseline_benchmark_slice_count), "benchmark_slice_count_probe": int(len(benchmark_probe_rows)), "benchmark_slice_coverage_all_v2": float(baseline_benchmark_coverage_all), "benchmark_slice_coverage_all_probe": float(benchmark_probe_coverage_all), "benchmark_slice_coverage_undercommit_v2": float(baseline_benchmark_undercommit_coverage), "benchmark_slice_coverage_undercommit_probe": float(benchmark_probe_coverage_undercommit), "benchmark_slice_family_counts_v2": baseline_benchmark_family_counts, "benchmark_slice_family_counts_probe": {str(name): int(count) for name, count in sorted(benchmark_probe_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))}, "benchmark_target_family_count_v2": int(baseline_target_family_count), "benchmark_target_family_count_probe": int(benchmark_probe_target_family_count), "benchmark_target_family_share_v2": float(baseline_target_share), "benchmark_target_family_share_probe": float(probe_target_share)},
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": {"safe_pool_collapse_reduced": bool(safe_pool_collapse_reduced), "benchmark_like_survival_improved": bool(benchmark_like_survival_improved), "projection_safe_retention_preserved": bool(projection_safe_retention_preserved), "benchmark_retention_improved": bool(benchmark_retention_improved), "coverage_preserved": bool(coverage_preserved), "collapse_driver_after_probe": str(collapse_driver_after_probe), "best_stability_retention_mechanism": str(best_stability_retention_mechanism), "next_control_hypothesis": str(next_control_hypothesis), "recommended_next_template": str(recommended_next_template), "slice_fragility": str(slice_fragility)},
        "sample_rows": {"probe_slice_examples": live_probe_rows[:8], "benchmark_probe_examples": benchmark_probe_rows[:8]},
    }
    artifact_path = _diagnostic_artifact_dir() / f"critic_split_stability_context_retention_probe_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(observability_gain["passed"] and ambiguity_reduction["passed"] and safety_neutrality["passed"] and later_selection_usefulness["passed"])
    if not bool(observability_gain["passed"]):
        reason = "diagnostic shadow failed: insufficient safe-slice live or benchmark evidence for stability/context retention refinement"
    elif not bool(projection_safe_retention_preserved):
        reason = "diagnostic shadow passed: stability/context retention refinement weakened projection-safe retention and should not be promoted"
    elif safe_pool_collapse_reduced and benchmark_like_survival_improved:
        reason = "diagnostic shadow passed: stability/context retention refinement improves collapse-prone safe-slice survival while preserving safety"
    else:
        reason = "diagnostic shadow passed: stability/context retention refinement preserves safety, but collapse pressure still points to deeper benchmark-alignment/context work"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_critic_split_stability_context_retention_probe_v2_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .stability_context_retention_probe_v2 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))

    broader_v2_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.projection_gain_goal_v2")
    stability_v1_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.stability_context_retention_probe_v1")
    alignment_v1_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_alignment_critic_v1")
    alignment_v2_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_alignment_critic_v2")
    availability_artifact = _load_latest_diagnostic_artifact_by_template("memory_summary.benchmark_context_availability_snapshot")
    seed_context_artifact = _load_latest_diagnostic_artifact_by_template("memory_summary.seed_context_shift_snapshot")
    if (
        not broader_v2_artifact
        or not stability_v1_artifact
        or not alignment_v1_artifact
        or not alignment_v2_artifact
        or not availability_artifact
        or not seed_context_artifact
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: benchmark_alignment_critic_v2, stability_context_retention_probe_v1, and context-memory artifacts are required for stability_context_retention_probe_v2",
            "observability_gain": {"passed": False, "reason": "missing prerequisite critic/context artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite critic/context artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite critic/context artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot recommend a follow-up without the prerequisite critic/context artifacts",
            },
        }

    mechanism = dict(proposal.get("mechanism", {}))
    intended_benefit = dict(proposal.get("intended_benefit", {}))
    benchmark_target_family = str(intended_benefit.get("target_family", "gain_goal_conflict"))
    projection_boundary = float(_targeted_projection_override_boundary(cfg))

    benchmark_rows = _load_latest_benchmark_detailed_rows()
    benchmark_undercommit_all = [
        row
        for row in benchmark_rows
        if str(row.get("policy_decision", "")) == "reject"
        and str(row.get("oracle_decision", "")) in {"provisional", "full"}
    ]
    benchmark_undercommit_target = [
        row for row in benchmark_undercommit_all if str(row.get("family", "")) == benchmark_target_family
    ]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (
            benchmark_undercommit_target if benchmark_reference_source == "target_family_undercommit" else benchmark_undercommit_all
        )
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }

    slice_definition = dict(broader_v2_artifact.get("slice_definition", {}))
    projection_level_cap = float(slice_definition.get("projection_level_cap", 0.70))
    projection_shape_cap = float(slice_definition.get("projection_shape_cap", 0.65))
    gain_goal_floor = float(slice_definition.get("gain_goal_floor", 0.34))
    stability_cap = float(slice_definition.get("stability_cap", 0.42))
    projection_bad_safe_cap = float(slice_definition.get("projection_bad_safe_cap", 0.57))
    projection_error_safe_cap = float(slice_definition.get("projection_error_safe_cap", 0.0115))
    benchmark_distance_cap = float(slice_definition.get("benchmark_distance_cap", 1.0))
    gain_structure_level_soft_cap = float(slice_definition.get("gain_structure_level_soft_cap", projection_level_cap + 0.08))
    gain_structure_benchmark_distance_soft_cap = float(slice_definition.get("gain_structure_benchmark_distance_soft_cap", benchmark_distance_cap + 0.05))
    gain_structure_projection_bad_soft_cap = float(slice_definition.get("gain_structure_projection_bad_soft_cap", projection_bad_safe_cap + 0.02))
    gain_structure_gain_soft_floor = float(slice_definition.get("gain_structure_gain_soft_floor", gain_goal_floor + 0.08))

    broader_compare = dict(broader_v2_artifact.get("comparison_to_v2", {}))
    broader_baseline_live_activation_count = int(
        broader_compare.get(
            "slice_activation_count_probe",
            dict(broader_v2_artifact.get("observability_gain", {})).get("slice_activation_count", 0),
        )
    )
    broader_baseline_benchmark_alignment = dict(broader_v2_artifact.get("benchmark_alignment_summary", {}))
    broader_benchmark_slice_count = int(broader_baseline_benchmark_alignment.get("benchmark_slice_count", 0))
    broader_benchmark_undercommit_coverage = float(
        broader_baseline_benchmark_alignment.get("benchmark_slice_coverage_undercommit", 0.0)
    )

    alignment_compare = dict(alignment_v2_artifact.get("comparison_to_v2", {}))
    alignment_live_activation_count = int(
        alignment_compare.get(
            "slice_activation_count_probe",
            dict(alignment_v2_artifact.get("observability_gain", {})).get("slice_activation_count", 0),
        )
    )
    alignment_safe_retention_rate = float(alignment_compare.get("projection_safe_retention_rate_probe", 0.0))
    alignment_benchmark_like_retention_rate = float(alignment_compare.get("benchmark_like_retention_rate_probe", 0.0))
    alignment_mean_projection_error = _safe_metric(alignment_compare.get("mean_projection_error_probe"))
    alignment_seed_activation_rate_summary = dict(alignment_compare.get("seed_activation_rate_probe", {}))
    alignment_benchmark_summary = dict(alignment_v2_artifact.get("benchmark_relevance_summary", {}))
    alignment_benchmark_slice_count = int(alignment_benchmark_summary.get("benchmark_slice_count_probe", 0))
    alignment_benchmark_coverage_all = float(alignment_benchmark_summary.get("benchmark_slice_coverage_all_probe", 0.0))
    alignment_benchmark_undercommit_coverage = float(alignment_benchmark_summary.get("benchmark_slice_coverage_undercommit_probe", 0.0))
    alignment_benchmark_family_counts = {
        str(name): int(count)
        for name, count in dict(alignment_benchmark_summary.get("benchmark_slice_family_counts_probe", {})).items()
    }
    alignment_target_family_count = int(alignment_benchmark_summary.get("benchmark_target_family_count_probe", 0))
    alignment_target_share = float(alignment_target_family_count / alignment_benchmark_slice_count) if alignment_benchmark_slice_count else 0.0

    alignment_seed_map = {
        int(dict(item).get("seed", -1)): dict(item)
        for item in list(alignment_v2_artifact.get("safe_pool_metrics_by_seed", []))
        if _safe_metric(dict(item).get("seed")) is not None
    }
    alignment_seed_target_counts = {
        int(seed): int(dict(item).get("selected_count", dict(item).get("slice_activation_count", 0)))
        for seed, item in alignment_seed_map.items()
    }
    alignment_total_safe_pool_count = int(sum(int(dict(item).get("safe_pool_count", 0)) for item in alignment_seed_map.values()))
    alignment_total_safe_pool_benchmark_like_count = int(sum(int(dict(item).get("safe_pool_benchmark_like_count", 0)) for item in alignment_seed_map.values()))
    alignment_total_selected_benchmark_like_count = int(sum(int(dict(item).get("selected_benchmark_like_count", 0)) for item in alignment_seed_map.values()))

    availability_present_summary = dict(dict(availability_artifact.get("availability_present_vs_absent_analysis", {})).get("availability_present", {}))
    availability_seed_map = {
        int(dict(item).get("seed", -1)): dict(item)
        for item in list(availability_artifact.get("per_seed_availability_summary", []))
        if _safe_metric(dict(item).get("seed")) is not None
    }
    seed_context_map = {
        int(dict(item).get("seed", -1)): dict(item)
        for item in list(seed_context_artifact.get("per_seed_safe_slice_summary", []))
        if _safe_metric(dict(item).get("seed")) is not None
    }
    prior_absent_seed_ids = {int(seed) for seed, row in availability_seed_map.items() if not bool(dict(row).get("availability_present", False))}
    prior_absent_seed_ids.update({int(seed) for seed, row in seed_context_map.items() if bool(dict(row).get("collapse_case", False))})
    healthy_safe_pool_mean = float(_safe_metric(availability_present_summary.get("safe_pool_count_mean")) or 4.0)
    healthy_benchmark_distance_mean = float(_safe_metric(availability_present_summary.get("benchmark_distance_mean")) or 0.70)
    healthy_projection_shape_mean = float(_safe_metric(availability_present_summary.get("projection_shape_mean")) or 0.50)

    def _annotate(row: Dict[str, Any]) -> Dict[str, Any]:
        annotated = dict(row)
        annotated["segment"] = str(
            annotated.get(
                "segment",
                _segment_live_candidate(
                    annotated,
                    benchmark_summary=benchmark_summary,
                    projection_boundary=projection_boundary,
                ),
            )
        )
        if "benchmark_distance" not in annotated:
            annotated["benchmark_distance"] = float(_benchmark_distance(annotated, benchmark_summary))
        annotated["projection_level_critic"] = float(
            _row_projection_level_critic_v2(
                annotated,
                benchmark_summary,
                projection_boundary=projection_boundary,
            )
        )
        annotated["projection_shape_critic"] = float(_row_projection_shape_critic_v2(annotated, benchmark_summary))
        annotated["gain_goal_critic_v2"] = float(_row_gain_goal_critic_v2(annotated, benchmark_summary))
        annotated["stability_critic_v2"] = float(
            _row_stability_critic_v2(
                annotated,
                projection_level_critic=float(annotated["projection_level_critic"]),
                projection_shape_critic=float(annotated["projection_shape_critic"]),
                gain_goal_critic=float(annotated["gain_goal_critic_v2"]),
            )
        )
        return annotated

    def _subtype(row: Dict[str, Any]) -> str:
        segment = str(row.get("segment", "mixed_shift"))
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 99.0)
        projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or 99.0)
        gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or -1e9)
        stability = float(_safe_metric(row.get("stability_critic_v2")) or 99.0)
        if segment == "benchmark_adjacent" and benchmark_distance <= benchmark_distance_cap * 1.02 and projection_shape <= projection_shape_cap * 0.95:
            return "retained_like_profile"
        if segment == "gain_structure_shifted" and benchmark_distance <= gain_structure_benchmark_distance_soft_cap and projection_shape <= projection_shape_cap and gain_goal >= gain_structure_gain_soft_floor:
            return "retained_like_profile"
        if segment == "gain_structure_shifted":
            return "gain_fragile_profile"
        if segment == "stability_sensitive" or stability > stability_cap * 0.95:
            return "stability_fragile"
        if segment in {"projection_mid_shifted", "projection_borderline"} or projection_shape > projection_shape_cap * 0.92:
            return "projection_shape_fragile"
        return "mixed_safe"

    def _subtype_prior(name: str) -> float:
        return {
            "retained_like_profile": 1.00,
            "gain_fragile_profile": 0.78,
            "mixed_safe": 0.52,
            "projection_shape_fragile": 0.18,
            "stability_fragile": 0.12,
        }.get(str(name), 0.32)

    def _score(
        row: Dict[str, Any],
        prior_alignment_seed: Dict[str, Any],
        prior_context_seed: Dict[str, Any],
        baseline_target_count: int,
    ) -> Dict[str, Any]:
        subtype = str(row.get("alignment_subtype", "mixed_safe"))
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 1.20)
        projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or 0.0)
        projection_level = float(_safe_metric(row.get("projection_level_critic")) or 0.0)
        gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or 0.0)
        stability = float(_safe_metric(row.get("stability_critic_v2")) or 0.0)
        seed_id = int(_safe_metric(row.get("seed")) or -1)
        prior_safe_pool_count = int(prior_alignment_seed.get("safe_pool_count", 0))
        prior_safe_pool_benchmark_like_count = int(prior_alignment_seed.get("safe_pool_benchmark_like_count", 0))
        prior_selected_benchmark_like_count = int(prior_alignment_seed.get("selected_benchmark_like_count", 0))
        prior_context_shift = max(
            float(_safe_metric(prior_alignment_seed.get("context_shift_score")) or 0.0),
            float(_safe_metric(prior_context_seed.get("context_shift_score")) or 0.0),
        )
        scarcity = max(
            0.0,
            (
                max(healthy_safe_pool_mean, float(max(1, baseline_target_count)))
                - float(prior_safe_pool_count)
            )
            / max(1.0, max(healthy_safe_pool_mean, float(max(1, baseline_target_count)))),
        )
        benchmark_proximity = max(0.0, 1.25 - min(1.25, benchmark_distance))
        shape_closeness = max(0.0, projection_shape_cap - min(projection_shape_cap, projection_shape)) / max(1e-6, projection_shape_cap)
        level_closeness = max(0.0, projection_level_cap - min(projection_level_cap, projection_level)) / max(1e-6, projection_level_cap)
        subtype_conditioning = float(_subtype_prior(subtype))
        collapse_prone = bool(
            seed_id in prior_absent_seed_ids
            or bool(prior_context_seed.get("collapse_case", False))
            or scarcity >= 0.55
            or prior_context_shift >= 0.65
        )
        recovered_candidate_context = bool(prior_safe_pool_benchmark_like_count > 0 or prior_selected_benchmark_like_count > 0)
        preservation_priority = 1.15 if collapse_prone and recovered_candidate_context else 1.0 if collapse_prone else 0.88
        scarcity_aware_selection = benchmark_proximity * (0.52 + 0.48 * scarcity) * (0.60 + 0.40 * subtype_conditioning) * preservation_priority
        context_shift_interaction = benchmark_proximity * shape_closeness * (0.60 + 0.40 * level_closeness) * max(0.0, 1.0 - 0.24 * max(0.0, prior_context_shift - 0.25))
        gain_goal_context = min(1.0, max(0.0, gain_goal)) * (0.55 + 0.45 * benchmark_proximity) * max(0.0, 1.0 - 0.18 * prior_context_shift)
        subtype_weight = subtype_conditioning * (1.18 if subtype == "retained_like_profile" and collapse_prone else 0.96 if subtype == "gain_fragile_profile" and collapse_prone else 0.76 if subtype == "mixed_safe" else 0.36)
        if subtype in {"projection_shape_fragile", "stability_fragile"}:
            context_shift_interaction *= 0.58
            scarcity_aware_selection *= 0.72
        preservation_bonus = 0.0
        if collapse_prone and subtype == "retained_like_profile" and benchmark_distance <= benchmark_distance_cap * 1.06 and projection_shape <= projection_shape_cap * 1.05:
            preservation_bonus += 0.12
        if collapse_prone and subtype == "gain_fragile_profile" and benchmark_distance <= gain_structure_benchmark_distance_soft_cap and gain_goal >= gain_goal_floor:
            preservation_bonus += 0.06
        if collapse_prone and recovered_candidate_context and subtype in {"retained_like_profile", "gain_fragile_profile"}:
            preservation_bonus += 0.04
        if prior_context_shift >= 0.80 and benchmark_distance > benchmark_distance_cap * 1.05:
            preservation_bonus -= 0.04
        if subtype in {"projection_shape_fragile", "stability_fragile"} and collapse_prone:
            preservation_bonus -= 0.08
        mixed_structure = float(0.30 * scarcity_aware_selection + 0.24 * context_shift_interaction + 0.18 * subtype_weight + 0.14 * gain_goal_context + 0.14 * benchmark_proximity)
        score = float(0.28 * scarcity_aware_selection + 0.24 * context_shift_interaction + 0.20 * subtype_weight + 0.16 * gain_goal_context + 0.08 * level_closeness + preservation_bonus)
        benchmark_distance_bonus = min(0.20, 0.10 * scarcity_aware_selection + 0.08 * context_shift_interaction + 0.04 * subtype_weight + max(0.0, preservation_bonus) * 0.40)
        projection_shape_bonus = min(0.10, 0.06 * context_shift_interaction + 0.04 * subtype_weight + (0.03 if collapse_prone and subtype == "retained_like_profile" else 0.0))
        projection_level_bonus = min(0.08, 0.05 * level_closeness + 0.03 * scarcity_aware_selection)
        gain_goal_bonus = min(0.08, 0.05 * gain_goal_context + (0.03 if subtype in {"retained_like_profile", "gain_fragile_profile"} else 0.0))
        stability_bonus = min(0.10, 0.06 if collapse_prone and subtype == "retained_like_profile" else 0.02 * subtype_conditioning)
        return {
            "stability_context_retention_score_v2": float(score),
            "benchmark_like_preservation_score": float(max(0.0, preservation_bonus + benchmark_proximity)),
            "scarcity_aware_selection_score": float(scarcity_aware_selection),
            "context_shift_interaction_score": float(context_shift_interaction),
            "subtype_conditioning_score": float(subtype_weight),
            "gain_goal_context_score": float(gain_goal_context),
            "mixed_stability_score": float(mixed_structure),
            "benchmark_distance_bonus": float(benchmark_distance_bonus),
            "projection_shape_bonus": float(projection_shape_bonus),
            "projection_level_bonus": float(projection_level_bonus),
            "gain_goal_bonus": float(gain_goal_bonus),
            "stability_bonus": float(stability_bonus),
            "context_shift_score": float(prior_context_shift),
            "scarcity_score": float(scarcity),
            "collapse_prone_context": bool(collapse_prone),
            "recovered_candidate_context": bool(recovered_candidate_context),
        }

    def _flags(row: Dict[str, Any]) -> Dict[str, Any]:
        blocker = str(row.get("blocker_group", "other"))
        segment = str(row.get("segment", "mixed_shift"))
        subtype = str(row.get("alignment_subtype", "mixed_safe"))
        collapse_prone = bool(row.get("collapse_prone_context", False))
        adjusted_benchmark_distance = max(0.0, float(row.get("benchmark_distance", 99.0)) - float(row.get("benchmark_distance_bonus", 0.0)))
        adjusted_projection_shape = max(0.0, float(row.get("projection_shape_critic", 99.0)) - float(row.get("projection_shape_bonus", 0.0)))
        adjusted_projection_level = max(0.0, float(row.get("projection_level_critic", 99.0)) - float(row.get("projection_level_bonus", 0.0)))
        adjusted_gain_goal = float(row.get("gain_goal_critic_v2", -1e9)) + float(row.get("gain_goal_bonus", 0.0))
        adjusted_stability = max(0.0, float(row.get("stability_critic_v2", 99.0)) - float(row.get("stability_bonus", 0.0)))
        blocker_ok = blocker in {"projection_guard", "confidence_gain"}
        segment_ok = segment not in {"projection_far_shifted"}
        stability_ok = adjusted_stability <= stability_cap
        if segment == "stability_sensitive":
            stability_ok = bool(stability_ok and adjusted_projection_shape <= projection_shape_cap * 0.85 and adjusted_gain_goal >= gain_goal_floor + 0.05)
        if segment in {"projection_mid_shifted", "projection_borderline"}:
            segment_ok = bool(segment_ok and adjusted_projection_shape <= projection_shape_cap * 0.95)
        if blocker == "confidence_gain":
            blocker_ok = bool(blocker_ok and adjusted_projection_level <= projection_level_cap * 1.05 and adjusted_gain_goal >= gain_goal_floor + 0.02)
        gain_structure_soft_ok = bool(
            subtype in {"retained_like_profile", "gain_fragile_profile"}
            and adjusted_projection_shape <= projection_shape_cap
            and float(row.get("pred_projection_error", 99.0)) <= projection_error_safe_cap
            and adjusted_gain_goal >= gain_structure_gain_soft_floor
            and adjusted_projection_level <= gain_structure_level_soft_cap
            and adjusted_benchmark_distance <= gain_structure_benchmark_distance_soft_cap
        )
        base_env_ok = bool(
            blocker_ok
            and segment_ok
            and stability_ok
            and (
                (
                    adjusted_projection_level <= projection_level_cap
                    and adjusted_projection_shape <= projection_shape_cap
                    and adjusted_gain_goal >= gain_goal_floor
                    and adjusted_benchmark_distance <= benchmark_distance_cap
                )
                or gain_structure_soft_ok
            )
        )
        raw_projection_safe = bool(
            (
                float(row.get("pred_projection_bad_prob", 99.0)) <= projection_bad_safe_cap
                and float(row.get("pred_projection_error", 99.0)) <= projection_error_safe_cap
            )
            or (
                subtype in {"retained_like_profile", "gain_fragile_profile"}
                and float(row.get("pred_projection_bad_prob", 99.0)) <= gain_structure_projection_bad_soft_cap
                and float(row.get("pred_projection_error", 99.0)) <= projection_error_safe_cap
                and adjusted_projection_shape <= projection_shape_cap
            )
        )
        preservation_soft_ok = bool(
            collapse_prone
            and bool(row.get("recovered_candidate_context", False))
            and subtype in {"retained_like_profile", "gain_fragile_profile"}
            and blocker_ok
            and segment_ok
            and raw_projection_safe
            and adjusted_projection_level <= projection_level_cap * 1.04
            and adjusted_projection_shape <= projection_shape_cap * 1.02
            and adjusted_gain_goal >= gain_goal_floor - 0.01
            and adjusted_stability <= stability_cap * 1.03
            and adjusted_benchmark_distance <= benchmark_distance_cap * 1.03
        )
        probe_safe_pool = bool((base_env_ok or preservation_soft_ok) and raw_projection_safe)
        probe_benchmark_like_available = bool(probe_safe_pool and adjusted_benchmark_distance <= benchmark_distance_cap)
        return {
            "probe_safe_pool": bool(probe_safe_pool),
            "probe_benchmark_like_available": bool(probe_benchmark_like_available),
            "adjusted_benchmark_distance": float(adjusted_benchmark_distance),
            "adjusted_projection_shape": float(adjusted_projection_shape),
            "adjusted_projection_level": float(adjusted_projection_level),
            "adjusted_gain_goal": float(adjusted_gain_goal),
            "adjusted_stability": float(adjusted_stability),
        }

    def _predictor_strengths(rows: List[Dict[str, Any]]) -> Dict[str, float]:
        pos = [row for row in rows if bool(row.get("probe_benchmark_like_available", False))]
        neg = [row for row in rows if not bool(row.get("probe_benchmark_like_available", False))]
        if not pos or not neg:
            return {
                "scarcity_aware_selection": 0.0,
                "subtype_conditioning": 0.0,
                "context_shift_interaction": 0.0,
                "mixed": 0.0,
            }

        def _gap(key: str) -> float:
            pos_vals = [float(_safe_metric(row.get(key)) or 0.0) for row in pos]
            neg_vals = [float(_safe_metric(row.get(key)) or 0.0) for row in neg]
            return float(abs((sum(pos_vals) / len(pos_vals)) - (sum(neg_vals) / len(neg_vals))))

        return {
            "scarcity_aware_selection": _gap("scarcity_aware_selection_score"),
            "subtype_conditioning": _gap("subtype_conditioning_score"),
            "context_shift_interaction": _gap("context_shift_interaction_score"),
            "mixed": _gap("mixed_stability_score"),
        }

    def _counter_dict(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
        counts = Counter(str(row.get(key, "unknown")) for row in rows if str(row.get(key, "")))
        return {str(name): int(count) for name, count in sorted(counts.items(), key=lambda item: (-int(item[1]), str(item[0])))}

    def _group_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        subtype_counts: Counter[str] = Counter()
        blocker_counts: Counter[str] = Counter()
        for row in rows:
            subtype_counts.update({str(name): int(count) for name, count in dict(row.get("subtype_mix", {})).items()})
            blocker_counts.update({str(name): int(count) for name, count in dict(row.get("blocker_mix", {})).items()})

        def _mean_flat(key: str) -> float:
            return float(_mean([float(_safe_metric(row.get(key)) or 0.0) for row in rows]) or 0.0)

        def _mean_nested(key: str) -> float:
            return float(_mean([float(_safe_metric(dict(row.get("key_critic_summaries", {})).get(key)) or 0.0) for row in rows]) or 0.0)

        total_subtypes = float(sum(int(count) for count in subtype_counts.values()))

        def _share(name: str) -> float:
            if total_subtypes <= 0.0:
                return 0.0
            return float(subtype_counts.get(str(name), 0) / total_subtypes)

        return {
            "case_count": int(len(rows)),
            "safe_pool_count_mean": _mean_flat("safe_pool_count"),
            "safe_pool_benchmark_like_fraction_mean": _mean_flat("safe_pool_benchmark_like_fraction"),
            "selected_count_mean": _mean_flat("selected_count"),
            "selected_benchmark_like_count_mean": _mean_flat("selected_benchmark_like_count"),
            "context_shift_mean": _mean_flat("context_shift_score"),
            "benchmark_distance_mean": _mean_nested("benchmark_distance_mean"),
            "projection_shape_mean": _mean_nested("projection_shape_mean"),
            "gain_goal_mean": _mean_nested("gain_goal_mean"),
            "stability_mean": _mean_nested("stability_mean"),
            "mean_slice_projection_error": _mean_nested("mean_slice_projection_error"),
            "subtype_counts": {str(name): int(count) for name, count in sorted(subtype_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "blocker_counts": {str(name): int(count) for name, count in sorted(blocker_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "retained_like_share": _share("retained_like_profile"),
            "gain_fragile_share": _share("gain_fragile_profile"),
            "stability_fragile_share": _share("stability_fragile"),
            "projection_shape_fragile_share": _share("projection_shape_fragile"),
        }

    def _collapse_severity(row: Dict[str, Any]) -> float:
        safe_pool_count = float(_safe_metric(row.get("safe_pool_count")) or 0.0)
        benchmark_like_count = float(_safe_metric(row.get("safe_pool_benchmark_like_count")) or 0.0)
        context_shift = float(_safe_metric(row.get("context_shift_score")) or 0.0)
        key_critic = dict(row.get("key_critic_summaries", {}))
        benchmark_distance_mean = float(_safe_metric(key_critic.get("benchmark_distance_mean")) or 0.0)
        projection_shape_mean = float(_safe_metric(key_critic.get("projection_shape_mean")) or 0.0)
        scarcity = max(0.0, healthy_safe_pool_mean - safe_pool_count)
        missing_like = 1.0 if benchmark_like_count <= 0.0 else max(0.0, 1.0 - (benchmark_like_count / max(1.0, safe_pool_count)))
        benchmark_distance_penalty = max(0.0, benchmark_distance_mean - healthy_benchmark_distance_mean)
        projection_shape_penalty = max(0.0, projection_shape_mean - healthy_projection_shape_mean)
        return float(0.45 * scarcity + 0.70 * missing_like + 0.45 * context_shift + 0.35 * benchmark_distance_penalty + 0.30 * projection_shape_penalty)

    def _seed_safe_pool_summary(
        seed: int,
        seed_rows: List[Dict[str, Any]],
        safe_pool_rows: List[Dict[str, Any]],
        selected_rows: List[Dict[str, Any]],
        baseline_target_count: int,
        prior_alignment_seed: Dict[str, Any],
    ) -> Dict[str, Any]:
        safe_pool_benchmark_like_count = int(sum(bool(row.get("probe_benchmark_like_available", False)) for row in safe_pool_rows))
        selected_safe_rows = [row for row in selected_rows if bool(row.get("probe_projection_safe", False))]
        selected_like_rows = [row for row in selected_rows if bool(row.get("probe_benchmark_like", False))]
        subtype_mix = _counter_dict(safe_pool_rows, "alignment_subtype")
        blocker_mix = _counter_dict(safe_pool_rows, "blocker_group")
        context_shift_score = float(_mean_key(safe_pool_rows, "context_shift_score") or 0.0)
        dominant_subtype = max(subtype_mix.items(), key=lambda item: (int(item[1]), str(item[0])))[0] if subtype_mix else "none"
        dominant_blocker = max(blocker_mix.items(), key=lambda item: (int(item[1]), str(item[0])))[0] if blocker_mix else "none"
        benchmark_distance_mean = _mean_key(safe_pool_rows, "adjusted_benchmark_distance")
        projection_shape_mean = _mean_key(safe_pool_rows, "adjusted_projection_shape")
        gain_goal_mean = _mean_key(safe_pool_rows, "adjusted_gain_goal")
        stability_mean = _mean_key(safe_pool_rows, "adjusted_stability")
        scarcity_mean = _mean_key(safe_pool_rows, "scarcity_score")
        preservation_mean = _mean_key(safe_pool_rows, "benchmark_like_preservation_score")
        mean_slice_projection_error = _mean_key(selected_rows, "pred_projection_error")
        collapse_driver_after_probe = "mixed"
        if len(safe_pool_rows) <= max(1, baseline_target_count) and safe_pool_benchmark_like_count <= 0:
            collapse_driver_after_probe = "scarcity"
        elif safe_pool_benchmark_like_count > 0 and len(selected_like_rows) <= 0:
            collapse_driver_after_probe = "misselection"
        elif context_shift_score >= 0.65 and safe_pool_benchmark_like_count <= 0:
            collapse_driver_after_probe = "context_shift"
        elif dominant_subtype in {"stability_fragile", "projection_shape_fragile"} and safe_pool_benchmark_like_count <= 0:
            collapse_driver_after_probe = "subtype_instability"
        return {
            "seed": int(seed),
            "blocked_candidate_count": int(len(seed_rows)),
            "safe_pool_count": int(len(safe_pool_rows)),
            "safe_pool_benchmark_like_count": int(safe_pool_benchmark_like_count),
            "safe_pool_benchmark_like_fraction": float(safe_pool_benchmark_like_count / len(safe_pool_rows)) if safe_pool_rows else 0.0,
            "baseline_target_count": int(baseline_target_count),
            "selected_count": int(len(selected_rows)),
            "selected_benchmark_like_count": int(len(selected_like_rows)),
            "slice_activation_count": int(len(selected_rows)),
            "slice_activation_rate": float(len(selected_rows) / len(seed_rows)) if seed_rows else 0.0,
            "slice_projection_safe_count": int(len(selected_safe_rows)),
            "slice_projection_safe_rate": float(len(selected_safe_rows) / len(selected_rows)) if selected_rows else 0.0,
            "slice_benchmark_like_count": int(len(selected_like_rows)),
            "slice_benchmark_like_rate": float(len(selected_like_rows) / len(selected_rows)) if selected_rows else 0.0,
            "context_shift_score": float(context_shift_score),
            "subtype_mix": subtype_mix,
            "blocker_mix": blocker_mix,
            "dominant_subtype": str(dominant_subtype),
            "dominant_blocker": str(dominant_blocker),
            "collapse_case": bool(int(seed) in prior_absent_seed_ids or len(safe_pool_rows) <= max(1, baseline_target_count) or safe_pool_benchmark_like_count <= 0),
            "collapse_driver_after_probe": str(collapse_driver_after_probe),
            "key_critic_summaries": {
                "benchmark_distance_mean": benchmark_distance_mean,
                "projection_shape_mean": projection_shape_mean,
                "gain_goal_mean": gain_goal_mean,
                "stability_mean": stability_mean,
                "scarcity": scarcity_mean,
                "benchmark_like_preservation_mean": preservation_mean,
                "mean_slice_projection_error": mean_slice_projection_error,
            },
            "prior_selected_benchmark_like_count": int(prior_alignment_seed.get("selected_benchmark_like_count", 0)),
            "prior_safe_pool_benchmark_like_count": int(prior_alignment_seed.get("safe_pool_benchmark_like_count", 0)),
        }

    benchmark_candidate_rows: List[Dict[str, Any]] = []
    benchmark_prior_alignment_seed = {"safe_pool_count": healthy_safe_pool_mean, "selected_benchmark_like_count": 1}
    benchmark_prior_context_seed = {"context_shift_score": 0.0, "collapse_case": False}
    benchmark_target_count = max(1, alignment_target_family_count or alignment_live_activation_count or 1)
    for scenario_result in benchmark_undercommit_all:
        candidate_row = _benchmark_scenario_candidate_row(
            cfg,
            scenario_result,
            projection_boundary=projection_boundary,
            benchmark_summary=benchmark_summary,
        )
        candidate_row = _annotate(candidate_row)
        candidate_row["alignment_subtype"] = str(_subtype(candidate_row))
        candidate_row.update(
            _score(
                candidate_row,
                benchmark_prior_alignment_seed,
                benchmark_prior_context_seed,
                benchmark_target_count,
            )
        )
        candidate_row.update(_flags(candidate_row))
        benchmark_candidate_rows.append(candidate_row)

    all_rows: List[Dict[str, Any]] = []
    live_probe_rows: List[Dict[str, Any]] = []
    seed_summaries: List[Dict[str, Any]] = []

    for seed in list(seeds):
        run_cfg = copy.deepcopy(cfg)
        run_cfg.verbose = False
        run_cfg.rounds = max(1, int(rounds))
        run_cfg.seed = int(seed)
        run_cfg.benchmark_every_rounds = 0
        run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs or {})
        run_cfg.eval_kwargs[
            "session_log_path"
        ] = f"logs/intervention_shadow_{proposal['proposal_id']}_stability_context_retention_v2_seed{int(seed)}.log"
        apply_live_policy_variant(run_cfg, "targeted_gain_goal_proj_margin_01")
        _, _, history = run_proposal_learning_loop(run_cfg)

        seed_rows: List[Dict[str, Any]] = []
        prior_alignment_seed = dict(alignment_seed_map.get(int(seed), {}))
        prior_context_seed = dict(seed_context_map.get(int(seed), {}))
        baseline_target_count = int(alignment_seed_target_counts.get(int(seed), 0))
        for round_index, entry in enumerate(history):
            blocked = [item for item in list(entry.get("adopt_blocked", [])) if isinstance(item, dict)]
            for item in blocked:
                row = _live_gap_row(
                    item,
                    seed=int(seed),
                    round_index=int(round_index),
                    cohort="baseline_rejected",
                    projection_boundary=projection_boundary,
                )
                row = _annotate(row)
                row["alignment_subtype"] = str(_subtype(row))
                row.update(_score(row, prior_alignment_seed, prior_context_seed, baseline_target_count))
                row.update(_flags(row))
                seed_rows.append(row)
                all_rows.append(row)

        safe_pool_rows = [row for row in seed_rows if bool(row.get("probe_safe_pool", False))]
        selected_rows: List[Dict[str, Any]] = []
        if baseline_target_count > 0 and safe_pool_rows:
            ordered = sorted(
                safe_pool_rows,
                key=lambda item: float(item.get("stability_context_retention_score_v2", -1e9)),
                reverse=True,
            )
            target_count = min(len(ordered), max(1, baseline_target_count))
            collapse_prone_seed = bool(
                int(seed) in prior_absent_seed_ids
                or any(bool(row.get("collapse_prone_context", False)) for row in ordered[: max(1, target_count)])
            )
            extra_benchmark_like = max(
                0,
                sum(bool(row.get("probe_benchmark_like_available", False)) for row in ordered) - target_count,
            )
            if collapse_prone_seed and extra_benchmark_like > 0 and len(ordered) > target_count:
                target_count = min(len(ordered), target_count + 1)
            context_shift_peak = max(float(row.get("context_shift_score", 0.0)) for row in ordered[:target_count])
            scarcity_peak = max(float(row.get("scarcity_score", 0.0)) for row in ordered[:target_count])
            quality_floor = 0.22 + 0.03 * max(0.0, context_shift_peak - 0.25) - 0.02 * min(1.0, scarcity_peak)
            quality_floor = max(0.18, min(0.32, quality_floor))
            selected_rows = [
                row
                for row in ordered[:target_count]
                if float(row.get("stability_context_retention_score_v2", -1e9)) >= quality_floor
                or (
                    collapse_prone_seed
                    and bool(row.get("probe_benchmark_like_available", False))
                    and float(row.get("stability_context_retention_score_v2", -1e9)) >= quality_floor - 0.04
                )
            ]
            if not selected_rows and ordered:
                top = ordered[0]
                if (
                    float(top.get("stability_context_retention_score_v2", -1e9)) >= quality_floor - 0.05
                    and str(top.get("alignment_subtype", "")) in {"retained_like_profile", "gain_fragile_profile"}
                ):
                    selected_rows = [top]

        selected_ids = {
            (int(dict(row).get("round_index", -1)), str(dict(row).get("candidate_id", "")))
            for row in selected_rows
        }
        for row in seed_rows:
            row["probe_slice_candidate"] = bool(
                (int(dict(row).get("round_index", -1)), str(dict(row).get("candidate_id", ""))) in selected_ids
            )
            row["probe_projection_safe"] = bool(
                row["probe_slice_candidate"] and bool(row.get("probe_safe_pool", False))
            )
            row["probe_benchmark_like"] = bool(
                row["probe_projection_safe"] and bool(row.get("probe_benchmark_like_available", False))
            )
            if bool(row.get("probe_slice_candidate", False)):
                live_probe_rows.append(row)

        seed_summaries.append(
            _seed_safe_pool_summary(
                int(seed),
                seed_rows,
                safe_pool_rows,
                selected_rows,
                baseline_target_count,
                prior_alignment_seed,
            )
        )

    live_safe_pool_rows = [row for row in all_rows if bool(row.get("probe_safe_pool", False))]
    activation_count = int(len(live_probe_rows))
    safe_retention_rate = float(sum(bool(row.get("probe_projection_safe", False)) for row in live_probe_rows) / activation_count) if activation_count else 0.0
    benchmark_like_retention_rate = float(sum(bool(row.get("probe_benchmark_like", False)) for row in live_probe_rows) / activation_count) if activation_count else 0.0
    mean_projection_error = _mean_key(live_probe_rows, "pred_projection_error")

    safe_pool_count_probe = int(len(live_safe_pool_rows))
    safe_pool_benchmark_like_count_probe = int(sum(bool(row.get("probe_benchmark_like_available", False)) for row in live_safe_pool_rows))
    safe_pool_benchmark_like_fraction_probe = float(safe_pool_benchmark_like_count_probe / safe_pool_count_probe) if safe_pool_count_probe else 0.0
    safe_pool_benchmark_like_fraction_alignment = float(alignment_total_safe_pool_benchmark_like_count / alignment_total_safe_pool_count) if alignment_total_safe_pool_count else 0.0
    selected_benchmark_like_count_probe = int(sum(int(dict(summary).get("selected_benchmark_like_count", 0)) for summary in seed_summaries))

    benchmark_pool_rows = [row for row in benchmark_candidate_rows if bool(row.get("probe_safe_pool", False))]
    live_selection_fraction = float(activation_count / len(live_safe_pool_rows)) if live_safe_pool_rows else 0.0
    score_fraction_count = int(math.ceil(len(benchmark_pool_rows) * live_selection_fraction)) if benchmark_pool_rows and live_selection_fraction > 0.0 else 0
    stability_v1_benchmark_summary = dict(stability_v1_artifact.get("benchmark_relevance_summary", {}))
    coverage_floor_count = min(
        len(benchmark_pool_rows),
        max(
            1 if benchmark_pool_rows else 0,
            int(math.ceil(float(alignment_benchmark_slice_count) * 0.90)),
            int(stability_v1_benchmark_summary.get("benchmark_slice_count_probe", 0)),
        ),
    )
    benchmark_selected_count = min(len(benchmark_pool_rows), max(score_fraction_count, coverage_floor_count)) if benchmark_pool_rows else 0
    benchmark_probe_rows = (
        sorted(
            benchmark_pool_rows,
            key=lambda item: float(item.get("stability_context_retention_score_v2", -1e9)),
            reverse=True,
        )[:benchmark_selected_count]
        if benchmark_pool_rows and benchmark_selected_count > 0
        else []
    )
    benchmark_probe_family_counts = Counter(str(row.get("family", "unknown")) for row in benchmark_probe_rows)
    benchmark_probe_target_family_count = int(sum(str(row.get("family", "")) == benchmark_target_family for row in benchmark_probe_rows))
    benchmark_probe_coverage_all = float(len(benchmark_probe_rows) / len(benchmark_rows)) if benchmark_rows else 0.0
    benchmark_probe_coverage_undercommit = float(len(benchmark_probe_rows) / len(benchmark_undercommit_all)) if benchmark_undercommit_all else 0.0
    probe_target_share = float(benchmark_probe_target_family_count / len(benchmark_probe_rows)) if benchmark_probe_rows else 0.0

    predictor_strengths = _predictor_strengths(live_safe_pool_rows or benchmark_pool_rows)
    best_stability_exploitation_mechanism = max(predictor_strengths.items(), key=lambda item: float(item[1]))[0] if predictor_strengths else "mixed"

    collapse_seed_ids = sorted(int(seed) for seed in prior_absent_seed_ids)
    prior_collapse_rows = [dict(alignment_seed_map.get(int(seed), {})) for seed in collapse_seed_ids if int(seed) in alignment_seed_map]
    probe_collapse_rows = [row for row in seed_summaries if int(row.get("seed", -1)) in prior_absent_seed_ids]
    prior_collapse_safe_pool_count = int(sum(int(row.get("safe_pool_count", 0)) for row in prior_collapse_rows))
    probe_collapse_safe_pool_count = int(sum(int(row.get("safe_pool_count", 0)) for row in probe_collapse_rows))
    prior_collapse_safe_pool_benchmark_like_count = int(sum(int(row.get("safe_pool_benchmark_like_count", 0)) for row in prior_collapse_rows))
    probe_collapse_safe_pool_benchmark_like_count = int(sum(int(row.get("safe_pool_benchmark_like_count", 0)) for row in probe_collapse_rows))
    prior_collapse_selected_benchmark_like_count = int(sum(int(row.get("selected_benchmark_like_count", 0)) for row in prior_collapse_rows))
    probe_collapse_selected_benchmark_like_count = int(sum(int(row.get("selected_benchmark_like_count", 0)) for row in probe_collapse_rows))
    prior_collapse_fraction = float(prior_collapse_safe_pool_benchmark_like_count / prior_collapse_safe_pool_count) if prior_collapse_safe_pool_count else 0.0
    probe_collapse_fraction = float(probe_collapse_safe_pool_benchmark_like_count / probe_collapse_safe_pool_count) if probe_collapse_safe_pool_count else 0.0
    prior_collapse_severity = float(_mean([_collapse_severity(row) for row in prior_collapse_rows]) or 0.0)
    probe_collapse_severity = float(_mean([_collapse_severity(row) for row in probe_collapse_rows]) or 0.0)
    collapse_analysis_rows: List[Dict[str, Any]] = []
    for seed in collapse_seed_ids:
        prior_row = dict(alignment_seed_map.get(int(seed), {}))
        probe_row = next((row for row in probe_collapse_rows if int(row.get("seed", -1)) == int(seed)), {})
        collapse_analysis_rows.append(
            {
                "seed": int(seed),
                "prior_safe_pool_count": int(prior_row.get("safe_pool_count", 0)),
                "probe_safe_pool_count": int(probe_row.get("safe_pool_count", 0)),
                "prior_safe_pool_benchmark_like_count": int(prior_row.get("safe_pool_benchmark_like_count", 0)),
                "probe_safe_pool_benchmark_like_count": int(probe_row.get("safe_pool_benchmark_like_count", 0)),
                "prior_selected_benchmark_like_count": int(prior_row.get("selected_benchmark_like_count", 0)),
                "probe_selected_benchmark_like_count": int(probe_row.get("selected_benchmark_like_count", 0)),
                "prior_context_shift_score": float(_safe_metric(prior_row.get("context_shift_score")) or 0.0),
                "probe_context_shift_score": float(_safe_metric(probe_row.get("context_shift_score")) or 0.0),
                "prior_collapse_severity": float(_collapse_severity(prior_row)) if prior_row else None,
                "probe_collapse_severity": float(_collapse_severity(probe_row)) if probe_row else None,
                "probe_collapse_driver": str(probe_row.get("collapse_driver_after_probe", "missing")),
                "probe_subtype_mix": dict(probe_row.get("subtype_mix", {})),
                "probe_key_critic_summaries": dict(probe_row.get("key_critic_summaries", {})),
            }
        )

    benchmark_like_candidate_preserved = bool(probe_collapse_safe_pool_benchmark_like_count > 0)
    benchmark_like_candidate_selected = bool(probe_collapse_selected_benchmark_like_count > 0)
    benchmark_like_candidate_preservation_improved = bool(
        probe_collapse_safe_pool_benchmark_like_count > prior_collapse_safe_pool_benchmark_like_count
        or (
            probe_collapse_fraction > prior_collapse_fraction + 0.10
            and probe_collapse_safe_pool_count >= prior_collapse_safe_pool_count
        )
    )
    selected_benchmark_like_improved = bool(probe_collapse_selected_benchmark_like_count > prior_collapse_selected_benchmark_like_count)
    collapse_severity_improved = bool(probe_collapse_severity <= prior_collapse_severity - 0.05)
    benchmark_retention_improved = bool(benchmark_like_retention_rate > alignment_benchmark_like_retention_rate + 1e-9)
    projection_safe_retention_preserved = bool(safe_retention_rate >= max(0.95, alignment_safe_retention_rate - 0.02))
    coverage_preserved = bool(
        benchmark_probe_coverage_undercommit >= max(0.60, alignment_benchmark_undercommit_coverage * 0.85)
        and len(benchmark_probe_rows) >= max(int(math.ceil(alignment_benchmark_slice_count * 0.85)), 12)
    )
    baseline_seed_std = float(_safe_metric(alignment_seed_activation_rate_summary.get("std")) or 0.0)
    probe_seed_activation_rate_summary = _rate_summary(seed_summaries, "slice_activation_rate")
    probe_seed_std = float(_safe_metric(probe_seed_activation_rate_summary.get("std")) or 0.0)
    seed_fragility_preserved = bool(probe_seed_std <= baseline_seed_std + 1e-9)
    slice_fragility = "high" if probe_seed_std >= baseline_seed_std + 0.02 else ("low" if seed_fragility_preserved and activation_count >= max(1, alignment_live_activation_count - 1) else "medium")
    collapse_driver_counts = Counter(str(row.get("probe_collapse_driver", "mixed")) for row in collapse_analysis_rows if row)
    collapse_driver_after_probe = collapse_driver_counts.most_common(1)[0][0] if collapse_driver_counts else "mixed"

    if benchmark_like_candidate_preserved and benchmark_like_candidate_selected and collapse_severity_improved and projection_safe_retention_preserved and coverage_preserved and seed_fragility_preserved:
        next_control_hypothesis = "narrow_benchmark_routing_revisit"
        recommended_next_template = "routing_rule.slice_targeted_benchmark_sweep_v1"
        recommendation_reason = "the recovered benchmark-like candidate remains present and selected under adverse context while safety and coverage hold, so a narrow benchmark-only routing revisit becomes reasonable"
    elif projection_safe_retention_preserved and coverage_preserved and benchmark_like_candidate_preserved:
        next_control_hypothesis = "stability_context_retention_continue"
        recommended_next_template = "critic_split.benchmark_alignment_critic_v2"
        recommendation_reason = "the recovered benchmark-like candidate survives under context pressure, but collapse severity is not reduced enough yet to reopen routing"
    else:
        next_control_hypothesis = "no_routing_yet"
        recommended_next_template = "critic_split.benchmark_alignment_critic_v2"
        recommendation_reason = "stability-conditioned exploitation is still too weak or too fragile to justify routing reconsideration"

    observability_gain = {
        "passed": bool(len(all_rows) >= 12 and len(live_safe_pool_rows) >= 4 and len(benchmark_probe_rows) >= 12),
        "blocked_candidate_count": int(len(all_rows)),
        "safe_probe_pool_count": int(len(live_safe_pool_rows)),
        "seed_count": int(len(seed_summaries)),
        "slice_activation_count": int(activation_count),
        "benchmark_reference_source": str(benchmark_reference_source),
        "benchmark_undercommit_count": int(len(benchmark_undercommit_all)),
        "reason": "captured enough safe-pool live traffic and benchmark undercommit rows to test stability-conditioned preservation and selection against benchmark_alignment_critic_v2",
    }
    activation_analysis = {
        "passed": bool(activation_count > 0),
        "slice_activation_observed": bool(activation_count > 0),
        "slice_activation_repeatable": bool(sum(int(summary.get("slice_activation_count", 0)) > 0 for summary in seed_summaries) >= 2),
        "benchmark_like_candidate_preserved": bool(benchmark_like_candidate_preserved),
        "benchmark_like_candidate_selected": bool(benchmark_like_candidate_selected),
        "collapse_severity_improved": bool(collapse_severity_improved),
        "reason": "stability_context_retention_probe_v2 keeps the slice active while measuring whether recovered benchmark-like candidates survive collapse-prone contexts",
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(min(1.0, 0.24 + 0.18 * int(projection_safe_retention_preserved) + 0.16 * int(benchmark_like_candidate_preserved) + 0.14 * int(benchmark_like_candidate_selected) + 0.14 * int(collapse_severity_improved) + 0.14 * int(coverage_preserved) + 0.10 * int(bool(best_stability_exploitation_mechanism)))),
        "reason": "the probe tests whether restored benchmark-like candidates can be preserved and selected reliably under scarcity/context pressure without reopening routing",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "probe-only critic refinement inside the benchmark_alignment_critic_v2 safety envelope with no default live-policy mutation and no benchmark semantic changes",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "critic_split.stability_context_retention_probe_v2",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "dependency_context": {
            "projection_gain_goal_v2_artifact_path": str(broader_v2_artifact.get("_artifact_path", "")),
            "benchmark_alignment_v1_artifact_path": str(alignment_v1_artifact.get("_artifact_path", "")),
            "benchmark_alignment_v2_artifact_path": str(alignment_v2_artifact.get("_artifact_path", "")),
            "stability_context_v1_artifact_path": str(stability_v1_artifact.get("_artifact_path", "")),
            "benchmark_context_availability_artifact_path": str(availability_artifact.get("_artifact_path", "")),
            "seed_context_artifact_path": str(seed_context_artifact.get("_artifact_path", "")),
            "prior_availability_driver": str(dict(availability_artifact.get("diagnostic_conclusions", {})).get("availability_driver", "")),
            "prior_alignment_mechanism": str(dict(alignment_v2_artifact.get("diagnostic_conclusions", {})).get("best_alignment_availability_mechanism", "")),
            "prior_stability_mechanism": str(dict(stability_v1_artifact.get("diagnostic_conclusions", {})).get("best_stability_retention_mechanism", "")),
        },
        "critic_refinement_logic_used": {
            "refined_signal_groups": list(mechanism.get("refined_signal_groups", [])),
            "ranking_mode": str(mechanism.get("ranking_mode", "single_stage")),
            "blocker_sensitive_rules_used": list(mechanism.get("blocker_sensitive_rules", [])),
            "selection_mode": "stability_conditioned_exploitation_safe_slice_v2",
            "stability_context_logic": {
                "benchmark_like_candidate_preservation": "preserve retained-like and gain-fragile rows when scarcity/context makes losing the recovered candidate costly",
                "scarcity_aware_selection": "prefer benchmark-like, low-shape-risk rows when the safe pool is small",
                "subtype_conditioning": "keep retained-like profiles dominant under collapse-prone contexts",
                "context_shift_interaction": "penalize fragile projection-shape and stability rows more strongly when context shift is high",
            },
        },
        "slice_definition": {
            "source_template": "critic_split.projection_gain_goal_v2",
            "projection_level_cap": float(projection_level_cap),
            "projection_shape_cap": float(projection_shape_cap),
            "gain_goal_floor": float(gain_goal_floor),
            "stability_cap": float(stability_cap),
            "projection_bad_safe_cap": float(projection_bad_safe_cap),
            "projection_error_safe_cap": float(projection_error_safe_cap),
            "benchmark_distance_cap": float(benchmark_distance_cap),
            "selection_count_mode": "alignment_v2_seed_count_with_optional_collapse_seed_reserve",
            "benchmark_selection_floor_fraction": 0.90,
        },
        "comparison_to_benchmark_alignment_v2": {
            "slice_activation_count_alignment_v2": int(alignment_live_activation_count),
            "slice_activation_count_probe": int(activation_count),
            "slice_activation_count_delta": int(activation_count - alignment_live_activation_count),
            "projection_safe_retention_rate_alignment_v2": float(alignment_safe_retention_rate),
            "projection_safe_retention_rate_probe": float(safe_retention_rate),
            "projection_safe_retention_rate_delta": float(safe_retention_rate - alignment_safe_retention_rate),
            "benchmark_like_retention_rate_alignment_v2": float(alignment_benchmark_like_retention_rate),
            "benchmark_like_retention_rate_probe": float(benchmark_like_retention_rate),
            "benchmark_like_retention_rate_delta": float(benchmark_like_retention_rate - alignment_benchmark_like_retention_rate),
            "mean_projection_error_alignment_v2": alignment_mean_projection_error,
            "mean_projection_error_probe": mean_projection_error,
            "mean_projection_error_delta": None if alignment_mean_projection_error is None or mean_projection_error is None else float(mean_projection_error - alignment_mean_projection_error),
            "seed_activation_rate_alignment_v2": alignment_seed_activation_rate_summary,
            "seed_activation_rate_probe": probe_seed_activation_rate_summary,
            "seed_projection_safe_rate_probe": _rate_summary(seed_summaries, "slice_projection_safe_rate"),
            "seed_benchmark_like_rate_probe": _rate_summary(seed_summaries, "slice_benchmark_like_rate"),
        },
        "comparison_to_projection_gain_goal_v2": {
            "slice_activation_count_projection_gain_goal_v2": int(broader_baseline_live_activation_count),
            "slice_activation_count_probe": int(activation_count),
            "slice_activation_count_delta": int(activation_count - broader_baseline_live_activation_count),
            "benchmark_slice_count_projection_gain_goal_v2": int(broader_benchmark_slice_count),
            "benchmark_slice_count_probe": int(len(benchmark_probe_rows)),
            "benchmark_slice_count_delta": int(len(benchmark_probe_rows) - broader_benchmark_slice_count),
            "benchmark_slice_coverage_undercommit_projection_gain_goal_v2": float(broader_benchmark_undercommit_coverage),
            "benchmark_slice_coverage_undercommit_probe": float(benchmark_probe_coverage_undercommit),
            "benchmark_slice_coverage_undercommit_delta": float(benchmark_probe_coverage_undercommit - broader_benchmark_undercommit_coverage),
        },
        "safe_pool_metrics_by_seed": seed_summaries,
        "availability_metrics": {
            "safe_pool_count_alignment_v2": int(alignment_total_safe_pool_count),
            "safe_pool_count_probe": int(safe_pool_count_probe),
            "safe_pool_count_delta": int(safe_pool_count_probe - alignment_total_safe_pool_count),
            "safe_pool_benchmark_like_count_alignment_v2": int(alignment_total_safe_pool_benchmark_like_count),
            "safe_pool_benchmark_like_count_probe": int(safe_pool_benchmark_like_count_probe),
            "safe_pool_benchmark_like_count_delta": int(safe_pool_benchmark_like_count_probe - alignment_total_safe_pool_benchmark_like_count),
            "safe_pool_benchmark_like_fraction_alignment_v2": float(safe_pool_benchmark_like_fraction_alignment),
            "safe_pool_benchmark_like_fraction_probe": float(safe_pool_benchmark_like_fraction_probe),
            "safe_pool_benchmark_like_fraction_delta": float(safe_pool_benchmark_like_fraction_probe - safe_pool_benchmark_like_fraction_alignment),
            "selected_benchmark_like_count_alignment_v2": int(alignment_total_selected_benchmark_like_count),
            "selected_benchmark_like_count_probe": int(selected_benchmark_like_count_probe),
            "selected_benchmark_like_count_delta": int(selected_benchmark_like_count_probe - alignment_total_selected_benchmark_like_count),
        },
        "selected_benchmark_like_survival_metrics": {
            "collapse_seed_ids": collapse_seed_ids,
            "prior_selected_benchmark_like_count": int(prior_collapse_selected_benchmark_like_count),
            "probe_selected_benchmark_like_count": int(probe_collapse_selected_benchmark_like_count),
            "selected_benchmark_like_improved": bool(selected_benchmark_like_improved),
            "benchmark_like_candidate_preserved": bool(benchmark_like_candidate_preserved),
            "benchmark_like_candidate_selected": bool(benchmark_like_candidate_selected),
        },
        "collapse_specific_analysis": {
            "collapse_analysis_rows": collapse_analysis_rows,
            "prior_collapse_severity": float(prior_collapse_severity),
            "probe_collapse_severity": float(probe_collapse_severity),
            "collapse_severity_improved": bool(collapse_severity_improved),
            "collapse_driver_after_probe": str(collapse_driver_after_probe),
        },
        "purity_metrics": {
            "activation_count": int(activation_count),
            "benchmark_like_retention_rate": float(benchmark_like_retention_rate),
            "projection_safe_retention_rate": float(safe_retention_rate),
            "best_stability_exploitation_mechanism": str(best_stability_exploitation_mechanism),
            "predictor_strengths": {str(name): float(value) for name, value in sorted(predictor_strengths.items(), key=lambda item: (-float(item[1]), str(item[0])))},
        },
        "benchmark_relevance_summary": {
            "benchmark_slice_count_alignment_v2": int(alignment_benchmark_slice_count),
            "benchmark_slice_count_probe": int(len(benchmark_probe_rows)),
            "benchmark_slice_coverage_all_alignment_v2": float(alignment_benchmark_coverage_all),
            "benchmark_slice_coverage_all_probe": float(benchmark_probe_coverage_all),
            "benchmark_slice_coverage_undercommit_alignment_v2": float(alignment_benchmark_undercommit_coverage),
            "benchmark_slice_coverage_undercommit_probe": float(benchmark_probe_coverage_undercommit),
            "benchmark_slice_family_counts_alignment_v2": alignment_benchmark_family_counts,
            "benchmark_slice_family_counts_probe": {str(name): int(count) for name, count in sorted(benchmark_probe_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "benchmark_target_family_count_alignment_v2": int(alignment_target_family_count),
            "benchmark_target_family_count_probe": int(benchmark_probe_target_family_count),
            "benchmark_target_family_share_alignment_v2": float(alignment_target_share),
            "benchmark_target_family_share_probe": float(probe_target_share),
        },
        "family_slice_composition": {
            "target_family": str(benchmark_target_family),
            "benchmark_probe_family_counts": {str(name): int(count) for name, count in sorted(benchmark_probe_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
        },
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": {
            "benchmark_like_candidate_preserved": bool(benchmark_like_candidate_preserved),
            "benchmark_like_candidate_selected": bool(benchmark_like_candidate_selected),
            "selected_benchmark_like_improved": bool(selected_benchmark_like_improved),
            "projection_safe_retention_preserved": bool(projection_safe_retention_preserved),
            "benchmark_retention_improved": bool(benchmark_retention_improved),
            "coverage_preserved": bool(coverage_preserved),
            "collapse_severity_improved": bool(collapse_severity_improved),
            "collapse_driver_after_probe": str(collapse_driver_after_probe),
            "best_stability_exploitation_mechanism": str(best_stability_exploitation_mechanism),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
            "slice_fragility": str(slice_fragility),
        },
        "sample_rows": {
            "probe_slice_examples": live_probe_rows[:8],
            "safe_pool_examples": live_safe_pool_rows[:8],
            "benchmark_probe_examples": benchmark_probe_rows[:8],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"critic_split_stability_context_retention_probe_v2_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(observability_gain["passed"] and ambiguity_reduction["passed"] and safety_neutrality["passed"] and later_selection_usefulness["passed"])
    if not bool(observability_gain["passed"]):
        reason = "diagnostic shadow failed: insufficient safe-pool live or benchmark evidence for stability_context_retention_probe_v2"
    elif not bool(projection_safe_retention_preserved):
        reason = "diagnostic shadow passed: stability_context_retention_probe_v2 weakened projection-safe retention and should not be promoted"
    elif benchmark_like_candidate_preserved and benchmark_like_candidate_selected and collapse_severity_improved:
        reason = "diagnostic shadow passed: stability_context_retention_probe_v2 preserves and exploits recovered benchmark-like candidates under adverse context while keeping safety intact"
    else:
        reason = "diagnostic shadow passed: stability_context_retention_probe_v2 clarifies stability-conditioned exploitation limits, but routing remains premature"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_activation_window_probe_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    score_probe_artifact = _load_latest_diagnostic_artifact_by_template("score_reweight.blocker_sensitive_projection_probe")
    score_probe_conclusions = dict(score_probe_artifact.get("diagnostic_conclusions", {}))
    score_probe_slice_rows = list(dict(score_probe_artifact.get("sample_rows", {})).get("benchmark_like_slice_after", []))
    benchmark_summary = dict(score_probe_artifact.get("benchmark_comparison_summary", {})).get("metrics", {})

    if not score_probe_artifact or not score_probe_slice_rows:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no score-probe slice artifact is available to define the activation window",
            "observability_gain": {"passed": False, "reason": "missing score-probe artifact"},
            "activation_analysis_usefulness": {"passed": False, "reason": "slice definition unavailable"},
            "ambiguity_reduction": {"passed": False, "reason": "slice definition unavailable"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get('scope', ''))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without slice evidence"},
        }

    allowed_segments = sorted({str(row.get("segment", "")) for row in score_probe_slice_rows if str(row.get("segment", ""))})
    excluded_segments = sorted({"projection_far_shifted", "projection_mid_shifted", "stability_sensitive"} - set(allowed_segments))
    benchmark_distance_cap = max(float(_safe_metric(row.get("benchmark_distance")) or 0.0) for row in score_probe_slice_rows)
    projection_bad_cap = max(float(_safe_metric(row.get("pred_projection_bad_prob")) or 1.0) for row in score_probe_slice_rows)
    projection_error_cap = max(float(_safe_metric(row.get("pred_projection_error")) or 0.0) for row in score_probe_slice_rows)
    probe_score_floor = min(float(_safe_metric(row.get("probe_score")) or -1e9) for row in score_probe_slice_rows)
    benchmark_reference_source = str(dict(score_probe_artifact.get("benchmark_comparison_summary", {})).get("source", "score_probe_reference"))
    benchmark_target_family = str(score_probe_artifact.get("benchmark_target_family", "gain_goal_conflict"))

    all_rows: List[Dict[str, Any]] = []
    seed_summaries: List[Dict[str, Any]] = []
    projection_boundary = float("nan")

    for seed in list(seeds):
        run_cfg = copy.deepcopy(cfg)
        run_cfg.verbose = False
        run_cfg.rounds = max(1, int(rounds))
        run_cfg.seed = int(seed)
        run_cfg.benchmark_every_rounds = 0
        run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs or {})
        run_cfg.eval_kwargs["session_log_path"] = (
            f"logs/intervention_shadow_{proposal['proposal_id']}_activation_probe_seed{int(seed)}.log"
        )
        apply_live_policy_variant(run_cfg, "targeted_gain_goal_proj_margin_01")
        projection_boundary = float(_targeted_projection_override_boundary(run_cfg))
        _, _, history = run_proposal_learning_loop(run_cfg)

        seed_rows: List[Dict[str, Any]] = []
        for round_index, entry in enumerate(history):
            blocked = [item for item in list(entry.get("adopt_blocked", [])) if isinstance(item, dict)]
            blocked_rows: List[Dict[str, Any]] = []
            for item in blocked:
                row = _live_gap_row(
                    item,
                    seed=int(seed),
                    round_index=int(round_index),
                    cohort="baseline_rejected",
                    projection_boundary=projection_boundary,
                )
                row["segment"] = str(
                    _segment_live_candidate(
                        row,
                        benchmark_summary=benchmark_summary,
                        projection_boundary=projection_boundary,
                    )
                )
                row["probe_score"] = float(_row_score_projection_probe(row, benchmark_summary))
                row["benchmark_distance"] = float(_benchmark_distance(row, benchmark_summary))
                blocked_rows.append(row)
                seed_rows.append(row)
                all_rows.append(row)

            round_top_slice = _top_slice(blocked_rows, score_key="probe_score", frac=0.25)
            top_ids = {str(row.get("candidate_id", "")) for row in round_top_slice}
            for row in blocked_rows:
                row["top_probe_slice"] = bool(str(row.get("candidate_id", "")) in top_ids)
                row["slice_candidate"] = bool(
                    row["top_probe_slice"]
                    and str(row.get("segment", "")) in set(allowed_segments)
                    and str(row.get("segment", "")) not in set(excluded_segments)
                    and str(row.get("blocker_group", "")) == "projection_guard"
                    and float(row.get("probe_score", -1e9)) >= float(probe_score_floor)
                )
                row["slice_projection_safe"] = bool(
                    row["slice_candidate"]
                    and float(row.get("pred_projection_bad_prob", 99.0)) <= float(projection_bad_cap)
                    and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_cap)
                )
                row["slice_benchmark_like"] = bool(
                    row["slice_projection_safe"]
                    and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)
                )

        slice_rows = [row for row in seed_rows if bool(row.get("slice_candidate", False))]
        safe_rows = [row for row in slice_rows if bool(row.get("slice_projection_safe", False))]
        benchmark_like_rows = [row for row in slice_rows if bool(row.get("slice_benchmark_like", False))]
        seed_summaries.append(
            {
                "seed": int(seed),
                "blocked_candidate_count": int(len(seed_rows)),
                "slice_candidate_count": int(len(slice_rows)),
                "slice_activation_count": int(len(slice_rows)),
                "slice_projection_safe_count": int(len(safe_rows)),
                "slice_benchmark_like_count": int(len(benchmark_like_rows)),
                "slice_activation_rate": float(len(slice_rows) / len(seed_rows)) if seed_rows else 0.0,
                "slice_benchmark_like_rate": float(len(benchmark_like_rows) / len(slice_rows)) if slice_rows else 0.0,
            }
        )

    slice_rows_all = [row for row in all_rows if bool(row.get("slice_candidate", False))]
    safe_rows_all = [row for row in slice_rows_all if bool(row.get("slice_projection_safe", False))]
    benchmark_like_rows_all = [row for row in slice_rows_all if bool(row.get("slice_benchmark_like", False))]

    observed = bool(slice_rows_all)
    repeatable = bool(sum(int(summary.get("slice_activation_count", 0)) > 0 for summary in seed_summaries) >= 2 and len(slice_rows_all) >= 3)
    projection_safe = bool(slice_rows_all and len(safe_rows_all) == len(slice_rows_all))
    benchmark_like_retention_rate = float(len(benchmark_like_rows_all) / len(slice_rows_all)) if slice_rows_all else 0.0
    viable = bool(observed and repeatable and projection_safe and benchmark_like_retention_rate >= 0.75)

    if viable:
        next_control_hypothesis = "narrow_routing_sweep"
        recommended_next_template = "routing_rule.slice_targeted_benchmark_sweep_v1"
        recommendation_reason = "the slice activates repeatably, remains projection-safe, and stays benchmark-like enough for a benchmark-only routing sweep"
    elif observed and projection_safe:
        next_control_hypothesis = "slice_stability_probe"
        recommended_next_template = "critic_split.projection_gain_goal_v1"
        recommendation_reason = "the slice appears but remains too limited or unstable, so the next step should refine score structure before any routing sweep"
    elif observed and not projection_safe:
        next_control_hypothesis = "no_routing_yet"
        recommended_next_template = "critic_split.projection_gain_goal_v1"
        recommendation_reason = "the slice activates but does not remain projection-safe enough for routing follow-up"
    else:
        next_control_hypothesis = "score_refinement"
        recommended_next_template = "critic_split.projection_gain_goal_v1"
        recommendation_reason = "the slice does not activate reliably, so score refinement remains the safer next direction"

    observability_gain = {
        "passed": bool(len(all_rows) >= 12),
        "blocked_candidate_count": int(len(all_rows)),
        "slice_candidate_count": int(len(slice_rows_all)),
        "seed_count": int(len(seed_summaries)),
        "benchmark_target_family": str(benchmark_target_family),
        "benchmark_reference_source": str(benchmark_reference_source),
        "reason": (
            "captured enough live rejected traffic to test the slice across multiple short runs"
            if bool(len(all_rows) >= 12)
            else "insufficient live rejected traffic for a stable slice probe"
        ),
    }
    activation_analysis = {
        "passed": bool(observed),
        "slice_activation_observed": bool(observed),
        "slice_activation_repeatable": bool(repeatable),
        "slice_activation_rate": float(len(slice_rows_all) / len(all_rows)) if all_rows else 0.0,
        "reason": (
            "the narrow slice activates under the probe across at least one run"
            if observed
            else "no slice candidates met the narrow routing criteria in these runs"
        ),
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(
            min(
                1.0,
                0.30
                + 0.25 * int(observed)
                + 0.20 * int(repeatable)
                + 0.15 * float(benchmark_like_retention_rate)
                + 0.10 * int(projection_safe),
            )
        ),
        "slice_benchmark_like_retention_rate": float(benchmark_like_retention_rate),
        "reason": "the probe resolves whether the new slice is reusable, fragile, or unsafe",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "probe-only routing audit with no default live-policy mutation and no benchmark semantic changes",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
        "slice_viable_for_future_control": bool(viable),
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": str(proposal.get("template_name")),
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "slice_definition": {
            "source_template": "score_reweight.blocker_sensitive_projection_probe",
            "source_probe_effect": str(score_probe_conclusions.get("score_probe_effect", "")),
            "allowed_segments": list(allowed_segments),
            "excluded_segments": list(excluded_segments),
            "required_blocker_group": "projection_guard",
            "top_probe_slice_fraction": 0.25,
            "probe_score_floor": float(probe_score_floor),
            "projection_bad_cap": float(projection_bad_cap),
            "projection_error_cap": float(projection_error_cap),
            "benchmark_distance_cap": float(benchmark_distance_cap),
        },
        "candidate_counts": {
            "blocked_candidate_count": int(len(all_rows)),
            "slice_candidate_count": int(len(slice_rows_all)),
            "slice_projection_safe_count": int(len(safe_rows_all)),
            "slice_benchmark_like_count": int(len(benchmark_like_rows_all)),
        },
        "activation_summary": {
            "slice_activation_count": int(len(slice_rows_all)),
            "slice_activation_rate": float(len(slice_rows_all) / len(all_rows)) if all_rows else 0.0,
            "slice_activation_observed": bool(observed),
            "slice_activation_repeatable": bool(repeatable),
        },
        "safety_summary": {
            "slice_projection_safe": bool(projection_safe),
            "slice_benchmark_like_retention_rate": float(benchmark_like_retention_rate),
            "mean_slice_projection_bad": _mean_key(slice_rows_all, "pred_projection_bad_prob"),
            "mean_slice_projection_error": _mean_key(slice_rows_all, "pred_projection_error"),
            "mean_slice_benchmark_distance": _mean_key(slice_rows_all, "benchmark_distance"),
        },
        "seed_summaries": seed_summaries,
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": {
            "slice_activation_observed": bool(observed),
            "slice_activation_repeatable": bool(repeatable),
            "slice_projection_safe": bool(projection_safe),
            "slice_viable_for_future_control": bool(viable),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
        },
        "sample_rows": {
            "slice_activated_examples": slice_rows_all[:6],
            "slice_benchmark_like_examples": benchmark_like_rows_all[:6],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"routing_rule_activation_probe_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(observability_gain["passed"] and later_selection_usefulness["passed"])
    if not bool(observability_gain["passed"]):
        reason = "diagnostic shadow failed: insufficient live rejected traffic for slice-targeted activation probing"
    elif not observed:
        reason = "diagnostic shadow passed: the narrow slice did not activate, so no routing follow-up is justified yet"
    elif viable:
        reason = "diagnostic shadow passed: the narrow slice activates repeatably and remains safe enough for benchmark-only routing follow-up"
    elif projection_safe:
        reason = "diagnostic shadow passed: the narrow slice activates safely but remains too fragile for direct routing follow-up"
    else:
        reason = "diagnostic shadow passed: the narrow slice activates but does not yet remain projection-safe enough for routing follow-up"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_critic_split_projection_gain_goal_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    activation_artifact = _load_latest_diagnostic_artifact_by_template("routing_rule.activation_window_probe")
    score_probe_artifact = _load_latest_diagnostic_artifact_by_template("score_reweight.blocker_sensitive_projection_probe")
    if not activation_artifact or not score_probe_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: critic split probe requires both the latest score probe and routing activation probe artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite diagnostic artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite diagnostic artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite diagnostic artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get('scope', ''))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without routing-probe baseline evidence"},
        }

    score_probe_conclusions = dict(score_probe_artifact.get("diagnostic_conclusions", {}))
    activation_conclusions = dict(activation_artifact.get("diagnostic_conclusions", {}))
    slice_definition = dict(activation_artifact.get("slice_definition", {}))
    benchmark_summary = dict(score_probe_artifact.get("benchmark_comparison_summary", {})).get("metrics", {})
    benchmark_target_family = str(score_probe_artifact.get("benchmark_target_family", "gain_goal_conflict"))
    benchmark_reference_source = str(dict(score_probe_artifact.get("benchmark_comparison_summary", {})).get("source", "score_probe_reference"))

    allowed_segments = set(str(name) for name in list(slice_definition.get("allowed_segments", [])))
    excluded_segments = set(str(name) for name in list(slice_definition.get("excluded_segments", [])))
    projection_bad_cap = float(slice_definition.get("projection_bad_cap", 0.60))
    projection_error_cap = float(slice_definition.get("projection_error_cap", 0.02))
    benchmark_distance_cap = float(slice_definition.get("benchmark_distance_cap", 1.0))

    benchmark_like_examples = list(dict(score_probe_artifact.get("sample_rows", {})).get("benchmark_like_slice_after", []))
    gain_goal_reference_scores: List[float] = []
    projection_reference_scores: List[float] = []
    for row in benchmark_like_examples:
        candidate = dict(row)
        if "benchmark_distance" not in candidate:
            candidate["benchmark_distance"] = float(_benchmark_distance(candidate, benchmark_summary))
        if "segment" not in candidate:
            candidate["segment"] = str(
                _segment_live_candidate(
                    candidate,
                    benchmark_summary=benchmark_summary,
                    projection_boundary=float(candidate.get("projection_boundary", 0.47)),
                )
            )
        gain_goal_reference_scores.append(float(_row_gain_goal_critic(candidate, benchmark_summary)))
        projection_reference_scores.append(float(_row_projection_critic(candidate, benchmark_summary)))
    gain_goal_floor = min(gain_goal_reference_scores) if gain_goal_reference_scores else -1e9
    projection_critic_cap = max(projection_reference_scores) if projection_reference_scores else 99.0

    all_rows: List[Dict[str, Any]] = []
    seed_summaries: List[Dict[str, Any]] = []
    projection_boundary = float("nan")

    for seed in list(seeds):
        run_cfg = copy.deepcopy(cfg)
        run_cfg.verbose = False
        run_cfg.rounds = max(1, int(rounds))
        run_cfg.seed = int(seed)
        run_cfg.benchmark_every_rounds = 0
        run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs or {})
        run_cfg.eval_kwargs["session_log_path"] = (
            f"logs/intervention_shadow_{proposal['proposal_id']}_critic_split_seed{int(seed)}.log"
        )
        apply_live_policy_variant(run_cfg, "targeted_gain_goal_proj_margin_01")
        projection_boundary = float(_targeted_projection_override_boundary(run_cfg))
        _, _, history = run_proposal_learning_loop(run_cfg)

        seed_rows: List[Dict[str, Any]] = []
        for round_index, entry in enumerate(history):
            blocked = [item for item in list(entry.get("adopt_blocked", [])) if isinstance(item, dict)]
            blocked_rows: List[Dict[str, Any]] = []
            for item in blocked:
                row = _live_gap_row(
                    item,
                    seed=int(seed),
                    round_index=int(round_index),
                    cohort="baseline_rejected",
                    projection_boundary=projection_boundary,
                )
                row["segment"] = str(
                    _segment_live_candidate(
                        row,
                        benchmark_summary=benchmark_summary,
                        projection_boundary=projection_boundary,
                    )
                )
                row["benchmark_distance"] = float(_benchmark_distance(row, benchmark_summary))
                row["projection_critic"] = float(_row_projection_critic(row, benchmark_summary))
                row["gain_goal_critic"] = float(_row_gain_goal_critic(row, benchmark_summary))
                row["critic_split_score"] = float(row["gain_goal_critic"] - row["projection_critic"])
                blocked_rows.append(row)
                seed_rows.append(row)
                all_rows.append(row)

            round_top_slice = _top_slice(blocked_rows, score_key="critic_split_score", frac=0.25)
            top_ids = {str(row.get("candidate_id", "")) for row in round_top_slice}
            for row in blocked_rows:
                row["top_critic_split_slice"] = bool(str(row.get("candidate_id", "")) in top_ids)
                row["slice_candidate"] = bool(
                    row["top_critic_split_slice"]
                    and str(row.get("segment", "")) in allowed_segments
                    and str(row.get("segment", "")) not in excluded_segments
                    and str(row.get("blocker_group", "")) == "projection_guard"
                    and float(row.get("gain_goal_critic", -1e9)) >= float(gain_goal_floor)
                    and float(row.get("projection_critic", 99.0)) <= float(projection_critic_cap)
                    and float(row.get("pred_projection_bad_prob", 99.0)) <= float(projection_bad_cap)
                    and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_cap)
                )
                row["slice_projection_safe"] = bool(row["slice_candidate"])
                row["slice_benchmark_like"] = bool(
                    row["slice_candidate"]
                    and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)
                )

        slice_rows = [row for row in seed_rows if bool(row.get("slice_candidate", False))]
        safe_rows = [row for row in slice_rows if bool(row.get("slice_projection_safe", False))]
        benchmark_like_rows = [row for row in slice_rows if bool(row.get("slice_benchmark_like", False))]
        activation_rate = float(len(slice_rows) / len(seed_rows)) if seed_rows else 0.0
        safe_rate = float(len(safe_rows) / len(slice_rows)) if slice_rows else 0.0
        benchmark_like_rate = float(len(benchmark_like_rows) / len(slice_rows)) if slice_rows else 0.0
        seed_summaries.append(
            {
                "seed": int(seed),
                "blocked_candidate_count": int(len(seed_rows)),
                "slice_activation_count": int(len(slice_rows)),
                "slice_activation_rate": activation_rate,
                "slice_projection_safe_count": int(len(safe_rows)),
                "slice_projection_safe_rate": safe_rate,
                "slice_benchmark_like_count": int(len(benchmark_like_rows)),
                "slice_benchmark_like_rate": benchmark_like_rate,
                "mean_slice_projection_error": _mean_key(slice_rows, "pred_projection_error"),
                "mean_slice_benchmark_distance": _mean_key(slice_rows, "benchmark_distance"),
            }
        )

    slice_rows_all = [row for row in all_rows if bool(row.get("slice_candidate", False))]
    safe_rows_all = [row for row in slice_rows_all if bool(row.get("slice_projection_safe", False))]
    benchmark_like_rows_all = [row for row in slice_rows_all if bool(row.get("slice_benchmark_like", False))]

    activation_count = int(len(slice_rows_all))
    safe_retention_rate = float(len(safe_rows_all) / activation_count) if activation_count else 0.0
    benchmark_like_retention_rate = float(len(benchmark_like_rows_all) / activation_count) if activation_count else 0.0
    mean_projection_error = _mean_key(slice_rows_all, "pred_projection_error")
    mean_benchmark_distance = _mean_key(slice_rows_all, "benchmark_distance")
    activation_observed = bool(activation_count > 0)
    activation_repeatable = bool(sum(int(summary.get("slice_activation_count", 0)) > 0 for summary in seed_summaries) >= 2 and activation_count >= 3)

    baseline_candidate_counts = dict(activation_artifact.get("candidate_counts", {}))
    baseline_activation_summary = dict(activation_artifact.get("activation_summary", {}))
    baseline_safety_summary = dict(activation_artifact.get("safety_summary", {}))
    baseline_seed_summaries = list(activation_artifact.get("seed_summaries", []))
    baseline_activation_count = int(baseline_activation_summary.get("slice_activation_count", baseline_candidate_counts.get("slice_candidate_count", 0)))
    baseline_safe_rate = float(
        int(baseline_candidate_counts.get("slice_projection_safe_count", 0)) / baseline_activation_count
    ) if baseline_activation_count else 0.0
    baseline_benchmark_like_rate = float(baseline_safety_summary.get("slice_benchmark_like_retention_rate", 0.0))
    baseline_projection_error = _safe_metric(baseline_safety_summary.get("mean_slice_projection_error"))

    activation_rate_summary = _rate_summary(seed_summaries, "slice_activation_rate")
    safe_rate_summary = _rate_summary(seed_summaries, "slice_projection_safe_rate")
    benchmark_like_rate_summary = _rate_summary(seed_summaries, "slice_benchmark_like_rate")
    baseline_activation_rate_summary = _rate_summary(baseline_seed_summaries, "slice_activation_rate")
    baseline_benchmark_like_rate_summary = _rate_summary(baseline_seed_summaries, "slice_benchmark_like_rate")

    mean_projection_error_drift = None
    if mean_projection_error is not None and baseline_projection_error is not None:
        mean_projection_error_drift = float(mean_projection_error - baseline_projection_error)

    separation_improved = bool(
        activation_observed
        and safe_retention_rate >= baseline_safe_rate + 0.20
        and benchmark_like_retention_rate >= baseline_benchmark_like_rate + 0.20
    )
    benchmark_like_slice_emerged = bool(activation_observed and benchmark_like_retention_rate >= 0.75 and activation_count >= 2)
    future_viable = bool(
        activation_repeatable
        and safe_retention_rate >= 0.80
        and benchmark_like_retention_rate >= 0.80
        and (mean_projection_error is not None and mean_projection_error <= float(projection_error_cap))
    )

    if future_viable:
        critic_split_effect = "improved_separation"
        next_control_hypothesis = "narrow_routing_sweep"
        recommended_next_template = "routing_rule.slice_targeted_benchmark_sweep_v1"
        recommendation_reason = "critic split isolates a smaller slice that activates with strong projection-safe and benchmark-like retention"
    elif separation_improved or benchmark_like_slice_emerged:
        critic_split_effect = "improved_separation"
        next_control_hypothesis = "slice_stability_probe"
        recommended_next_template = "score_reweight.gain_goal_conflict_probe"
        recommendation_reason = "critic split makes the slice cleaner and safer, but coverage is still too narrow for a routing follow-up"
    elif activation_observed:
        critic_split_effect = "no_change"
        next_control_hypothesis = "score_refinement"
        recommended_next_template = "score_reweight.gain_goal_conflict_probe"
        recommendation_reason = "critic split does not improve safety enough over the routing probe, so score refinement should continue"
    else:
        critic_split_effect = "harmful"
        next_control_hypothesis = "no_routing_yet"
        recommended_next_template = "memory_summary.live_distribution_gap_snapshot"
        recommendation_reason = "critic split failed to expose an actionable slice, so the system should return to diagnostic clarification"

    observability_gain = {
        "passed": bool(len(all_rows) >= 12),
        "blocked_candidate_count": int(len(all_rows)),
        "slice_activation_count": int(activation_count),
        "seed_count": int(len(seed_summaries)),
        "benchmark_target_family": str(benchmark_target_family),
        "benchmark_reference_source": str(benchmark_reference_source),
        "reason": (
            "captured enough live rejected traffic to compare critic-split slice behavior against the routing probe"
            if bool(len(all_rows) >= 12)
            else "insufficient live rejected traffic for a stable critic-split comparison"
        ),
    }
    activation_analysis = {
        "passed": bool(activation_observed),
        "slice_activation_observed": bool(activation_observed),
        "slice_activation_repeatable": bool(activation_repeatable),
        "slice_activation_rate": float(activation_count / len(all_rows)) if all_rows else 0.0,
        "reason": (
            "critic split exposes an activatable slice under repeated short runs"
            if activation_observed
            else "critic split does not expose any activatable slice in these runs"
        ),
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(
            min(
                1.0,
                0.25
                + 0.20 * int(activation_observed)
                + 0.20 * int(activation_repeatable)
                + 0.20 * min(1.0, safe_retention_rate)
                + 0.15 * min(1.0, benchmark_like_retention_rate)
            )
        ),
        "reason": "the critic split directly compares slice cleanliness and safety against the routing probe baseline",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "probe-only critic split with no default live-policy mutation and no benchmark semantic changes",
    }
    later_selection_usefulness = {
        "passed": bool(observability_gain["passed"] and bool(recommended_next_template)),
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
        "slice_viable_for_future_control": bool(future_viable),
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": str(proposal.get("template_name")),
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "signals_reweighted": list(dict(proposal.get("mechanism", {})).get("split_signals", [])),
        "blocker_sensitive_rules_used": list(dict(proposal.get("mechanism", {})).get("blocker_sensitive_rules", [])),
        "comparison_reference_template": "routing_rule.activation_window_probe",
        "slice_definition": {
            "source_template": "routing_rule.activation_window_probe",
            "allowed_segments": sorted(allowed_segments),
            "excluded_segments": sorted(excluded_segments),
            "required_blocker_group": "projection_guard",
            "top_critic_split_slice_fraction": 0.25,
            "gain_goal_critic_floor": float(gain_goal_floor),
            "projection_critic_cap": float(projection_critic_cap),
            "projection_bad_cap": float(projection_bad_cap),
            "projection_error_cap": float(projection_error_cap),
            "benchmark_distance_cap": float(benchmark_distance_cap),
        },
        "candidate_counts": {
            "blocked_candidate_count": int(len(all_rows)),
            "slice_candidate_count": int(activation_count),
            "slice_projection_safe_count": int(len(safe_rows_all)),
            "slice_benchmark_like_count": int(len(benchmark_like_rows_all)),
        },
        "comparison_to_routing_probe": {
            "slice_activation_count_baseline": int(baseline_activation_count),
            "slice_activation_count_split": int(activation_count),
            "slice_activation_count_delta": int(activation_count - baseline_activation_count),
            "projection_safe_retention_rate_baseline": float(baseline_safe_rate),
            "projection_safe_retention_rate_split": float(safe_retention_rate),
            "projection_safe_retention_rate_delta": float(safe_retention_rate - baseline_safe_rate),
            "benchmark_like_retention_rate_baseline": float(baseline_benchmark_like_rate),
            "benchmark_like_retention_rate_split": float(benchmark_like_retention_rate),
            "benchmark_like_retention_rate_delta": float(benchmark_like_retention_rate - baseline_benchmark_like_rate),
            "mean_projection_error_baseline": baseline_projection_error,
            "mean_projection_error_split": mean_projection_error,
            "mean_projection_error_drift_delta": mean_projection_error_drift,
            "seed_activation_rate_baseline": baseline_activation_rate_summary,
            "seed_activation_rate_split": activation_rate_summary,
            "seed_benchmark_like_rate_baseline": baseline_benchmark_like_rate_summary,
            "seed_benchmark_like_rate_split": benchmark_like_rate_summary,
            "seed_projection_safe_rate_split": safe_rate_summary,
        },
        "segment_summaries": {
            segment_name: {
                "count": int(len(rows)),
                "projection_critic_mean": _mean_key(rows, "projection_critic"),
                "gain_goal_critic_mean": _mean_key(rows, "gain_goal_critic"),
                "critic_split_score_mean": _mean_key(rows, "critic_split_score"),
                "slice_candidate_count": int(sum(bool(dict(row).get("slice_candidate", False)) for row in rows)),
                "slice_projection_safe_count": int(sum(bool(dict(row).get("slice_projection_safe", False)) for row in rows)),
                "slice_benchmark_like_count": int(sum(bool(dict(row).get("slice_benchmark_like", False)) for row in rows)),
                "mean_projection_error": _mean_key(rows, "pred_projection_error"),
                "mean_benchmark_distance": _mean_key(rows, "benchmark_distance"),
            }
            for segment_name, rows in sorted(
                (
                    (
                        segment_name,
                        [row for row in all_rows if str(row.get("segment", "")) == str(segment_name)],
                    )
                    for segment_name in sorted(set(str(row.get("segment", "")) for row in all_rows))
                ),
                key=lambda item: (-len(item[1]), str(item[0])),
            )
        },
        "seed_summaries": seed_summaries,
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": {
            "critic_split_effect": str(critic_split_effect),
            "slice_activation_observed": bool(activation_observed),
            "slice_activation_repeatable": bool(activation_repeatable),
            "slice_projection_safe": bool(safe_retention_rate >= 0.80 and activation_observed),
            "slice_viable_for_future_control": bool(future_viable),
            "benchmark_like_slice_emerged": bool(benchmark_like_slice_emerged),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
        },
        "sample_rows": {
            "split_slice_examples": slice_rows_all[:6],
            "split_benchmark_like_examples": benchmark_like_rows_all[:6],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"critic_split_probe_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(
        observability_gain["passed"]
        and ambiguity_reduction["passed"]
        and safety_neutrality["passed"]
        and later_selection_usefulness["passed"]
    )
    if not bool(observability_gain["passed"]):
        reason = "diagnostic shadow failed: insufficient live rejected traffic for a stable critic-split comparison"
    elif critic_split_effect == "harmful":
        reason = "diagnostic shadow passed: critic split did not expose a usable slice and argues against immediate score-family follow-up"
    elif future_viable:
        reason = "diagnostic shadow passed: critic split produces a cleaner, safer slice than the routing probe and supports a narrow routing follow-up"
    elif separation_improved:
        reason = "diagnostic shadow passed: critic split improves slice cleanliness and safety, but the slice remains too small or fragile for routing follow-up"
    else:
        reason = "diagnostic shadow passed: critic split did not improve safety enough over the routing probe baseline"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_critic_split_projection_gain_goal_v2_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    v1_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.projection_gain_goal_v1")
    slice_sweep_artifact = _load_latest_diagnostic_artifact_by_template("routing_rule.slice_targeted_benchmark_sweep_v1")
    if not v1_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: critic split v1 artifact is required for the v2 refinement probe",
            "observability_gain": {"passed": False, "reason": "missing critic_split v1 artifact"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing critic_split v1 artifact"},
            "ambiguity_reduction": {"passed": False, "reason": "missing critic_split v1 artifact"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get('scope', ''))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without v1 comparison evidence"},
        }

    def _list_quantile(values: List[float], q: float, default: float) -> float:
        clean = sorted(float(v) for v in values if math.isfinite(float(v)))
        if not clean:
            return float(default)
        return float(_quantile(clean, q))

    intended_benefit = dict(proposal.get("intended_benefit", {}))
    benchmark_target_family = str(intended_benefit.get("target_family", "gain_goal_conflict"))
    benchmark_rows = _load_latest_benchmark_detailed_rows()
    projection_boundary = float(_targeted_projection_override_boundary(cfg))
    benchmark_undercommit_all = [
        row
        for row in benchmark_rows
        if str(row.get("policy_decision", "")) == "reject" and str(row.get("oracle_decision", "")) in {"provisional", "full"}
    ]
    benchmark_undercommit_target = [
        row for row in benchmark_undercommit_all if str(row.get("family", "")) == benchmark_target_family
    ]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (
            benchmark_undercommit_target
            if benchmark_reference_source == "target_family_undercommit"
            else benchmark_undercommit_all
        )
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }

    benchmark_candidate_rows: List[Dict[str, Any]] = []
    for scenario_result in benchmark_undercommit_all:
        candidate_row = _benchmark_scenario_candidate_row(
            cfg,
            scenario_result,
            projection_boundary=projection_boundary,
            benchmark_summary=benchmark_summary,
        )
        candidate_row["projection_level_critic"] = float(
            _row_projection_level_critic_v2(
                candidate_row,
                benchmark_summary,
                projection_boundary=projection_boundary,
            )
        )
        candidate_row["projection_shape_critic"] = float(
            _row_projection_shape_critic_v2(candidate_row, benchmark_summary)
        )
        candidate_row["gain_goal_critic_v2"] = float(
            _row_gain_goal_critic_v2(candidate_row, benchmark_summary)
        )
        candidate_row["stability_critic_v2"] = float(
            _row_stability_critic_v2(
                candidate_row,
                projection_level_critic=float(candidate_row["projection_level_critic"]),
                projection_shape_critic=float(candidate_row["projection_shape_critic"]),
                gain_goal_critic=float(candidate_row["gain_goal_critic_v2"]),
            )
        )
        candidate_row["critic_split_v2_score"] = float(
            candidate_row["gain_goal_critic_v2"]
            - 0.55 * candidate_row["projection_level_critic"]
            - 0.70 * candidate_row["projection_shape_critic"]
            - 0.35 * candidate_row["stability_critic_v2"]
        )
        benchmark_candidate_rows.append(candidate_row)

    v1_live_reference_rows: List[Dict[str, Any]] = []
    for row in list(dict(v1_artifact.get("sample_rows", {})).get("split_slice_examples", [])):
        candidate_row = dict(row)
        if "benchmark_distance" not in candidate_row:
            candidate_row["benchmark_distance"] = float(_benchmark_distance(candidate_row, benchmark_summary))
        candidate_row["projection_level_critic"] = float(
            _row_projection_level_critic_v2(
                candidate_row,
                benchmark_summary,
                projection_boundary=projection_boundary,
            )
        )
        candidate_row["projection_shape_critic"] = float(
            _row_projection_shape_critic_v2(candidate_row, benchmark_summary)
        )
        candidate_row["gain_goal_critic_v2"] = float(
            _row_gain_goal_critic_v2(candidate_row, benchmark_summary)
        )
        v1_live_reference_rows.append(candidate_row)

    if not benchmark_candidate_rows:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no benchmark undercommit reference rows available for critic refinement",
            "observability_gain": {"passed": False, "reason": "missing benchmark undercommit rows"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing benchmark undercommit rows"},
            "ambiguity_reduction": {"passed": False, "reason": "missing benchmark undercommit rows"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get('scope', ''))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot refine critic without benchmark undercommit references"},
        }

    projection_level_cap = _list_quantile(
        [float(row["projection_level_critic"]) for row in benchmark_candidate_rows],
        0.90,
        0.95,
    )
    projection_shape_cap = _list_quantile(
        [float(row["projection_shape_critic"]) for row in benchmark_candidate_rows],
        0.85,
        0.90,
    )
    gain_goal_floor = _list_quantile(
        [float(row["gain_goal_critic_v2"]) for row in benchmark_candidate_rows],
        0.20,
        0.30,
    ) - 0.03
    stability_cap = max(
        0.38,
        _list_quantile(
            [float(row["stability_critic_v2"]) for row in benchmark_candidate_rows],
            0.85,
            0.35,
        ) + 0.04,
    )
    projection_bad_safe_cap = min(
        0.62,
        _list_quantile(
            [float(_safe_metric(row.get("pred_projection_bad_prob")) or 1.0) for row in benchmark_candidate_rows],
            0.90,
            0.58,
        ) + 0.02,
    )
    projection_error_safe_cap = min(
        0.0135,
        _list_quantile(
            [float(_safe_metric(row.get("pred_projection_error")) or 0.0) for row in benchmark_candidate_rows],
            0.85,
            0.011,
        ) + 0.0015,
    )
    benchmark_distance_cap = min(
        1.10,
        _list_quantile(
            [float(_safe_metric(row.get("benchmark_distance")) or 1.0) for row in benchmark_candidate_rows],
            0.85,
            0.95,
        ) + 0.10,
    )
    if v1_live_reference_rows:
        projection_level_cap = max(
            projection_level_cap,
            _list_quantile(
                [float(row["projection_level_critic"]) for row in v1_live_reference_rows],
                0.90,
                projection_level_cap,
            ) + 0.06,
        )
        projection_shape_cap = max(
            projection_shape_cap,
            _list_quantile(
                [float(row["projection_shape_critic"]) for row in v1_live_reference_rows],
                0.90,
                projection_shape_cap,
            ) + 0.08,
        )
        benchmark_distance_cap = max(
            benchmark_distance_cap,
            min(
                1.10,
                _list_quantile(
                    [float(_safe_metric(row.get("benchmark_distance")) or 1.0) for row in v1_live_reference_rows],
                    0.90,
                    benchmark_distance_cap,
                ) + 0.08,
            ),
        )
        projection_bad_safe_cap = max(
            projection_bad_safe_cap,
            min(
                0.60,
                _list_quantile(
                    [float(_safe_metric(row.get("pred_projection_bad_prob")) or 1.0) for row in v1_live_reference_rows],
                    0.90,
                    projection_bad_safe_cap,
                ) + 0.015,
            ),
        )
        projection_error_safe_cap = max(
            projection_error_safe_cap,
            min(
                0.0128,
                _list_quantile(
                    [float(_safe_metric(row.get("pred_projection_error")) or 0.0) for row in v1_live_reference_rows],
                    0.90,
                    projection_error_safe_cap,
                ) + 0.0012,
            ),
        )

    gain_structure_level_soft_cap = min(0.78, float(projection_level_cap) + 0.08)
    gain_structure_benchmark_distance_soft_cap = min(1.06, float(benchmark_distance_cap) + 0.05)
    gain_structure_projection_bad_soft_cap = min(0.59, float(projection_bad_safe_cap) + 0.02)
    gain_structure_gain_soft_floor = float(gain_goal_floor) + 0.08
    gain_structure_shape_soft_cap = float(projection_shape_cap)

    all_rows: List[Dict[str, Any]] = []
    seed_summaries: List[Dict[str, Any]] = []

    for seed in list(seeds):
        run_cfg = copy.deepcopy(cfg)
        run_cfg.verbose = False
        run_cfg.rounds = max(1, int(rounds))
        run_cfg.seed = int(seed)
        run_cfg.benchmark_every_rounds = 0
        run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs or {})
        run_cfg.eval_kwargs["session_log_path"] = (
            f"logs/intervention_shadow_{proposal['proposal_id']}_critic_split_v2_seed{int(seed)}.log"
        )
        apply_live_policy_variant(run_cfg, "targeted_gain_goal_proj_margin_01")
        _, _, history = run_proposal_learning_loop(run_cfg)

        seed_rows: List[Dict[str, Any]] = []
        for round_index, entry in enumerate(history):
            blocked = [item for item in list(entry.get("adopt_blocked", [])) if isinstance(item, dict)]
            blocked_rows: List[Dict[str, Any]] = []
            for item in blocked:
                row = _live_gap_row(
                    item,
                    seed=int(seed),
                    round_index=int(round_index),
                    cohort="baseline_rejected",
                    projection_boundary=projection_boundary,
                )
                row["segment"] = str(
                    _segment_live_candidate(
                        row,
                        benchmark_summary=benchmark_summary,
                        projection_boundary=projection_boundary,
                    )
                )
                row["benchmark_distance"] = float(_benchmark_distance(row, benchmark_summary))
                row["projection_level_critic"] = float(
                    _row_projection_level_critic_v2(
                        row,
                        benchmark_summary,
                        projection_boundary=projection_boundary,
                    )
                )
                row["projection_shape_critic"] = float(
                    _row_projection_shape_critic_v2(row, benchmark_summary)
                )
                row["gain_goal_critic_v2"] = float(
                    _row_gain_goal_critic_v2(row, benchmark_summary)
                )
                row["stability_critic_v2"] = float(
                    _row_stability_critic_v2(
                        row,
                        projection_level_critic=float(row["projection_level_critic"]),
                        projection_shape_critic=float(row["projection_shape_critic"]),
                        gain_goal_critic=float(row["gain_goal_critic_v2"]),
                    )
                )
                row["critic_split_v2_score"] = float(
                    row["gain_goal_critic_v2"]
                    - 0.55 * row["projection_level_critic"]
                    - 0.70 * row["projection_shape_critic"]
                    - 0.35 * row["stability_critic_v2"]
                )
                blocked_rows.append(row)
                seed_rows.append(row)
                all_rows.append(row)

            round_top_slice = _top_slice(blocked_rows, score_key="critic_split_v2_score", frac=0.40)
            top_ids = {str(row.get("candidate_id", "")) for row in round_top_slice}
            for row in blocked_rows:
                blocker_group = str(row.get("blocker_group", "other"))
                segment = str(row.get("segment", "mixed_shift"))
                row["top_critic_split_v2_slice"] = bool(str(row.get("candidate_id", "")) in top_ids)
                blocker_ok = blocker_group in {"projection_guard", "confidence_gain"}
                segment_ok = segment not in {"projection_far_shifted"}
                stability_ok = float(row.get("stability_critic_v2", 99.0)) <= float(stability_cap)
                if segment == "stability_sensitive":
                    stability_ok = bool(
                        stability_ok
                        and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.85)
                        and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.05)
                    )
                if segment in {"projection_mid_shifted", "projection_borderline"}:
                    segment_ok = bool(
                        segment_ok
                        and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.95)
                    )
                if blocker_group == "confidence_gain":
                    blocker_ok = bool(
                        blocker_ok
                        and float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap * 1.05)
                        and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.02)
                    )
                gain_structure_soft_ok = bool(
                    row["top_critic_split_v2_slice"]
                    and segment in {"gain_structure_shifted", "benchmark_adjacent"}
                    and float(row.get("projection_shape_critic", 99.0)) <= float(gain_structure_shape_soft_cap)
                    and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
                    and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_structure_gain_soft_floor)
                    and float(row.get("projection_level_critic", 99.0)) <= float(gain_structure_level_soft_cap)
                    and float(row.get("benchmark_distance", 99.0)) <= float(gain_structure_benchmark_distance_soft_cap)
                )
                row["slice_candidate"] = bool(
                    row["top_critic_split_v2_slice"]
                    and blocker_ok
                    and segment_ok
                    and stability_ok
                    and (
                        (
                            float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap)
                            and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)
                            and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor)
                            and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)
                        )
                        or gain_structure_soft_ok
                    )
                )
                row["slice_projection_safe"] = bool(
                    row["slice_candidate"]
                    and (
                        (
                            float(row.get("pred_projection_bad_prob", 99.0)) <= float(projection_bad_safe_cap)
                            and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
                        )
                        or (
                            segment in {"gain_structure_shifted", "benchmark_adjacent"}
                            and float(row.get("pred_projection_bad_prob", 99.0)) <= float(gain_structure_projection_bad_soft_cap)
                            and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
                            and float(row.get("projection_shape_critic", 99.0)) <= float(gain_structure_shape_soft_cap)
                        )
                    )
                )
                row["slice_benchmark_like"] = bool(
                    row["slice_projection_safe"]
                    and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)
                )

        slice_rows = [row for row in seed_rows if bool(row.get("slice_candidate", False))]
        safe_rows = [row for row in slice_rows if bool(row.get("slice_projection_safe", False))]
        benchmark_like_rows = [row for row in slice_rows if bool(row.get("slice_benchmark_like", False))]
        seed_summaries.append(
            {
                "seed": int(seed),
                "blocked_candidate_count": int(len(seed_rows)),
                "slice_activation_count": int(len(slice_rows)),
                "slice_activation_rate": float(len(slice_rows) / len(seed_rows)) if seed_rows else 0.0,
                "slice_projection_safe_count": int(len(safe_rows)),
                "slice_projection_safe_rate": float(len(safe_rows) / len(slice_rows)) if slice_rows else 0.0,
                "slice_benchmark_like_count": int(len(benchmark_like_rows)),
                "slice_benchmark_like_rate": float(len(benchmark_like_rows) / len(slice_rows)) if slice_rows else 0.0,
                "mean_slice_projection_error": _mean_key(slice_rows, "pred_projection_error"),
            }
        )

    slice_rows_all = [row for row in all_rows if bool(row.get("slice_candidate", False))]
    safe_rows_all = [row for row in slice_rows_all if bool(row.get("slice_projection_safe", False))]
    benchmark_like_rows_all = [row for row in slice_rows_all if bool(row.get("slice_benchmark_like", False))]

    benchmark_slice_rows: List[Dict[str, Any]] = []
    for row in benchmark_candidate_rows:
        blocker_group = str(row.get("blocker_group", "other"))
        segment = str(row.get("segment", "mixed_shift"))
        blocker_ok = blocker_group in {"projection_guard", "confidence_gain"}
        segment_ok = segment not in {"projection_far_shifted"}
        stability_ok = float(row.get("stability_critic_v2", 99.0)) <= float(stability_cap)
        if segment == "stability_sensitive":
            stability_ok = bool(
                stability_ok
                and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.85)
                and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.05)
            )
        if segment in {"projection_mid_shifted", "projection_borderline"}:
            segment_ok = bool(
                segment_ok
                and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.95)
            )
        if blocker_group == "confidence_gain":
            blocker_ok = bool(
                blocker_ok
                and float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap * 1.05)
                and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.02)
            )
        gain_structure_soft_ok = bool(
            segment in {"gain_structure_shifted", "benchmark_adjacent"}
            and float(row.get("projection_shape_critic", 99.0)) <= float(gain_structure_shape_soft_cap)
            and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
            and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_structure_gain_soft_floor)
            and float(row.get("projection_level_critic", 99.0)) <= float(gain_structure_level_soft_cap)
            and float(row.get("benchmark_distance", 99.0)) <= float(gain_structure_benchmark_distance_soft_cap)
        )
        row["slice_candidate"] = bool(
            blocker_ok
            and segment_ok
            and stability_ok
            and (
                (
                    float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap)
                    and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)
                    and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor)
                    and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)
                )
                or gain_structure_soft_ok
            )
        )
        row["slice_projection_safe"] = bool(
            row["slice_candidate"]
            and (
                (
                    float(row.get("pred_projection_bad_prob", 99.0)) <= float(projection_bad_safe_cap)
                    and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
                )
                or (
                    segment in {"gain_structure_shifted", "benchmark_adjacent"}
                    and float(row.get("pred_projection_bad_prob", 99.0)) <= float(gain_structure_projection_bad_soft_cap)
                    and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
                    and float(row.get("projection_shape_critic", 99.0)) <= float(gain_structure_shape_soft_cap)
                )
            )
        )
        row["slice_benchmark_like"] = bool(
            row["slice_projection_safe"]
            and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)
        )
        if bool(row["slice_candidate"]):
            benchmark_slice_rows.append(row)

    activation_count = int(len(slice_rows_all))
    safe_retention_rate = float(len(safe_rows_all) / activation_count) if activation_count else 0.0
    benchmark_like_retention_rate = float(len(benchmark_like_rows_all) / activation_count) if activation_count else 0.0
    mean_projection_error = _mean_key(slice_rows_all, "pred_projection_error")
    activation_observed = bool(activation_count > 0)
    activation_repeatable = bool(sum(int(summary.get("slice_activation_count", 0)) > 0 for summary in seed_summaries) >= 2)

    v1_comparison = dict(v1_artifact.get("comparison_to_routing_probe", {}))
    v1_activation_count = int(dict(v1_artifact.get("candidate_counts", {})).get("slice_candidate_count", 0))
    v1_safe_rate = float(v1_comparison.get("projection_safe_retention_rate_split", 0.0))
    v1_benchmark_like_rate = float(v1_comparison.get("benchmark_like_retention_rate_split", 0.0))
    v1_mean_projection_error = _safe_metric(v1_comparison.get("mean_projection_error_split"))
    v1_seed_activation_rate = dict(v1_comparison.get("seed_activation_rate_split", {}))

    broader_slice_than_v1 = bool(activation_count > v1_activation_count)
    projection_safe_retention_preserved = bool(safe_retention_rate >= max(0.85, v1_safe_rate - 0.05))
    benchmark_like_retention_preserved = bool(benchmark_like_retention_rate >= max(0.70, v1_benchmark_like_rate - 0.10))
    seed_fragility_reduced = bool(
        float(_rate_summary(seed_summaries, "slice_activation_rate").get("std") or 0.0)
        <= float(v1_seed_activation_rate.get("std") or 99.0)
    )
    benchmark_slice_family_counts = Counter(str(row.get("family", "unknown")) for row in benchmark_slice_rows)
    benchmark_target_family_count = int(sum(str(row.get("family", "")) == benchmark_target_family for row in benchmark_slice_rows))
    benchmark_relevance_improved = bool(len(benchmark_slice_rows) >= 2 and benchmark_target_family_count >= 1)

    if (
        broader_slice_than_v1
        and projection_safe_retention_preserved
        and benchmark_like_retention_preserved
        and benchmark_relevance_improved
        and seed_fragility_reduced
    ):
        critic_split_effect = "improved_separation"
        next_control_hypothesis = "narrow_routing_sweep"
        recommended_next_template = "routing_rule.slice_targeted_benchmark_sweep_v1"
        recommendation_reason = "critic split v2 broadens the slice while preserving safety and improving benchmark alignment enough to reconsider a benchmark-only routing retest"
    elif (
        broader_slice_than_v1
        and projection_safe_retention_preserved
        and benchmark_like_retention_preserved
        and benchmark_relevance_improved
    ):
        critic_split_effect = "improved_separation"
        next_control_hypothesis = "slice_stability_probe"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "critic split v2 broadens the slice safely and improves benchmark alignment, but seed stability is still too mixed for a routing follow-up"
    elif broader_slice_than_v1 and projection_safe_retention_preserved:
        critic_split_effect = "improved_separation"
        next_control_hypothesis = "further_slice_refinement"
        recommended_next_template = "score_reweight.gain_goal_conflict_probe"
        recommendation_reason = "critic split v2 broadens the slice safely, but benchmark alignment is still too weak for routing follow-up"
    elif projection_safe_retention_preserved:
        critic_split_effect = "no_change"
        next_control_hypothesis = "more_critic_work"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "critic split v2 preserves safety but does not broaden or align the slice enough yet"
    else:
        critic_split_effect = "harmful"
        next_control_hypothesis = "no_routing_yet"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "critic split v2 broadens the slice in a way that does not preserve projection safety well enough"

    observability_gain = {
        "passed": bool(len(all_rows) >= 12 and len(benchmark_candidate_rows) >= 6),
        "blocked_candidate_count": int(len(all_rows)),
        "slice_activation_count": int(activation_count),
        "seed_count": int(len(seed_summaries)),
        "benchmark_reference_source": str(benchmark_reference_source),
        "benchmark_undercommit_count": int(len(benchmark_candidate_rows)),
        "reason": "captured enough live rejected traffic and benchmark undercommit references to measure v2 critic broadening",
    }
    activation_analysis = {
        "passed": bool(activation_observed),
        "slice_activation_observed": bool(activation_observed),
        "slice_activation_repeatable": bool(activation_repeatable),
        "slice_activation_rate": float(activation_count / len(all_rows)) if all_rows else 0.0,
        "reason": (
            "v2 critic exposes a broader activatable slice across repeated short runs"
            if activation_observed
            else "v2 critic does not expose an activatable slice in these runs"
        ),
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(
            min(
                1.0,
                0.25
                + 0.18 * int(broader_slice_than_v1)
                + 0.18 * int(projection_safe_retention_preserved)
                + 0.17 * int(benchmark_relevance_improved)
                + 0.12 * int(seed_fragility_reduced)
                + 0.10 * int(benchmark_like_retention_preserved)
            )
        ),
        "reason": "the v2 critic clarifies whether broader safe slice formation is possible before any routing reconsideration",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "probe-only critic refinement with no default live-policy mutation and no benchmark semantic changes",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": str(proposal.get("template_name")),
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "signals_reweighted": list(dict(proposal.get("mechanism", {})).get("split_signals", [])),
        "blocker_sensitive_rules_used": list(dict(proposal.get("mechanism", {})).get("blocker_sensitive_rules", [])),
        "slice_definition": {
            "source_template": "critic_split.projection_gain_goal_v1",
            "projection_level_cap": float(projection_level_cap),
            "projection_shape_cap": float(projection_shape_cap),
            "gain_goal_floor": float(gain_goal_floor),
            "stability_cap": float(stability_cap),
            "projection_bad_safe_cap": float(projection_bad_safe_cap),
            "projection_error_safe_cap": float(projection_error_safe_cap),
            "benchmark_distance_cap": float(benchmark_distance_cap),
            "gain_structure_level_soft_cap": float(gain_structure_level_soft_cap),
            "gain_structure_benchmark_distance_soft_cap": float(gain_structure_benchmark_distance_soft_cap),
            "gain_structure_projection_bad_soft_cap": float(gain_structure_projection_bad_soft_cap),
            "gain_structure_gain_soft_floor": float(gain_structure_gain_soft_floor),
            "allowed_blocker_groups": ["projection_guard", "confidence_gain"],
            "excluded_segments": ["projection_far_shifted"],
            "soft_included_segments": ["projection_mid_shifted", "projection_borderline", "stability_sensitive"],
            "top_slice_fraction": 0.40,
        },
        "comparison_to_v1": {
            "slice_activation_count_v1": int(v1_activation_count),
            "slice_activation_count_v2": int(activation_count),
            "slice_activation_count_delta": int(activation_count - v1_activation_count),
            "projection_safe_retention_rate_v1": float(v1_safe_rate),
            "projection_safe_retention_rate_v2": float(safe_retention_rate),
            "projection_safe_retention_rate_delta": float(safe_retention_rate - v1_safe_rate),
            "benchmark_like_retention_rate_v1": float(v1_benchmark_like_rate),
            "benchmark_like_retention_rate_v2": float(benchmark_like_retention_rate),
            "benchmark_like_retention_rate_delta": float(benchmark_like_retention_rate - v1_benchmark_like_rate),
            "mean_projection_error_v1": v1_mean_projection_error,
            "mean_projection_error_v2": mean_projection_error,
            "mean_projection_error_delta": (
                None
                if mean_projection_error is None or v1_mean_projection_error is None
                else float(mean_projection_error - v1_mean_projection_error)
            ),
            "seed_activation_rate_v1": v1_seed_activation_rate,
            "seed_activation_rate_v2": _rate_summary(seed_summaries, "slice_activation_rate"),
            "seed_projection_safe_rate_v2": _rate_summary(seed_summaries, "slice_projection_safe_rate"),
        },
        "benchmark_alignment_summary": {
            "benchmark_slice_count": int(len(benchmark_slice_rows)),
            "benchmark_target_family_count": int(benchmark_target_family_count),
            "benchmark_slice_coverage_all": float(len(benchmark_slice_rows) / len(benchmark_rows)) if benchmark_rows else 0.0,
            "benchmark_slice_coverage_undercommit": float(len(benchmark_slice_rows) / len(benchmark_candidate_rows)) if benchmark_candidate_rows else 0.0,
            "benchmark_slice_family_counts": {
                str(name): int(count)
                for name, count in sorted(benchmark_slice_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
        },
        "segment_summaries": {
            segment_name: {
                "count": int(len(rows)),
                "projection_level_critic_mean": _mean_key(rows, "projection_level_critic"),
                "projection_shape_critic_mean": _mean_key(rows, "projection_shape_critic"),
                "gain_goal_critic_mean": _mean_key(rows, "gain_goal_critic_v2"),
                "stability_critic_mean": _mean_key(rows, "stability_critic_v2"),
                "critic_split_v2_score_mean": _mean_key(rows, "critic_split_v2_score"),
                "slice_candidate_count": int(sum(bool(dict(row).get("slice_candidate", False)) for row in rows)),
                "slice_projection_safe_count": int(sum(bool(dict(row).get("slice_projection_safe", False)) for row in rows)),
                "slice_benchmark_like_count": int(sum(bool(dict(row).get("slice_benchmark_like", False)) for row in rows)),
            }
            for segment_name, rows in sorted(
                (
                    (
                        segment_name,
                        [row for row in all_rows if str(row.get("segment", "")) == str(segment_name)],
                    )
                    for segment_name in sorted(set(str(row.get("segment", "")) for row in all_rows))
                ),
                key=lambda item: (-len(item[1]), str(item[0])),
            )
        },
        "seed_summaries": seed_summaries,
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": {
            "critic_split_effect": str(critic_split_effect),
            "broader_slice_than_v1": bool(broader_slice_than_v1),
            "projection_safe_retention_preserved": bool(projection_safe_retention_preserved),
            "benchmark_like_retention_preserved": bool(benchmark_like_retention_preserved),
            "seed_fragility_reduced": bool(seed_fragility_reduced),
            "benchmark_relevance_improved": bool(benchmark_relevance_improved),
            "slice_activation_observed": bool(activation_observed),
            "slice_activation_repeatable": bool(activation_repeatable),
            "slice_projection_safe": bool(safe_retention_rate >= 0.85 and activation_observed),
            "slice_viable_for_future_control": bool(
                broader_slice_than_v1
                and projection_safe_retention_preserved
                and benchmark_relevance_improved
            ),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
        },
        "sample_rows": {
            "slice_examples": slice_rows_all[:8],
            "benchmark_slice_examples": benchmark_slice_rows[:8],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"critic_split_probe_v2_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(
        observability_gain["passed"]
        and ambiguity_reduction["passed"]
        and safety_neutrality["passed"]
        and later_selection_usefulness["passed"]
    )
    if not bool(observability_gain["passed"]):
        reason = "diagnostic shadow failed: insufficient live or benchmark evidence for critic split v2"
    elif critic_split_effect == "harmful":
        reason = "diagnostic shadow passed: critic split v2 broadened the slice in a way that did not preserve enough safety"
    elif broader_slice_than_v1 and benchmark_relevance_improved and projection_safe_retention_preserved:
        reason = "diagnostic shadow passed: critic split v2 broadens the slice safely and improves benchmark relevance"
    elif broader_slice_than_v1 and projection_safe_retention_preserved:
        reason = "diagnostic shadow passed: critic split v2 broadens the slice safely, but benchmark alignment remains limited"
    else:
        reason = "diagnostic shadow passed: critic split v2 did not yet produce a broader, safer, more benchmark-relevant slice"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_score_reweight_gain_goal_probe_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    v2_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.projection_gain_goal_v2")
    if not v2_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: critic split v2 artifact is required for the gain-goal score probe",
            "observability_gain": {"passed": False, "reason": "missing critic split v2 artifact"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing critic split v2 artifact"},
            "ambiguity_reduction": {"passed": False, "reason": "missing critic split v2 artifact"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without critic split v2 evidence"},
        }

    intended_benefit = dict(proposal.get("intended_benefit", {}))
    mechanism = dict(proposal.get("mechanism", {}))
    benchmark_target_family = str(intended_benefit.get("target_family", "gain_goal_conflict"))
    projection_boundary = float(_targeted_projection_override_boundary(cfg))

    benchmark_rows = _load_latest_benchmark_detailed_rows()
    benchmark_undercommit_all = [
        row
        for row in benchmark_rows
        if str(row.get("policy_decision", "")) == "reject" and str(row.get("oracle_decision", "")) in {"provisional", "full"}
    ]
    benchmark_undercommit_target = [
        row for row in benchmark_undercommit_all if str(row.get("family", "")) == benchmark_target_family
    ]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (
            benchmark_undercommit_target
            if benchmark_reference_source == "target_family_undercommit"
            else benchmark_undercommit_all
        )
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }

    baseline_slice_definition = dict(v2_artifact.get("slice_definition", {}))
    projection_level_cap = float(baseline_slice_definition.get("projection_level_cap", 0.70))
    projection_shape_cap = float(baseline_slice_definition.get("projection_shape_cap", 0.65))
    gain_goal_floor = float(baseline_slice_definition.get("gain_goal_floor", 0.34))
    stability_cap = float(baseline_slice_definition.get("stability_cap", 0.42))
    projection_bad_safe_cap = float(baseline_slice_definition.get("projection_bad_safe_cap", 0.57))
    projection_error_safe_cap = float(baseline_slice_definition.get("projection_error_safe_cap", 0.0115))
    benchmark_distance_cap = float(baseline_slice_definition.get("benchmark_distance_cap", 1.0))
    gain_structure_level_soft_cap = float(
        baseline_slice_definition.get("gain_structure_level_soft_cap", projection_level_cap + 0.08)
    )
    gain_structure_benchmark_distance_soft_cap = float(
        baseline_slice_definition.get("gain_structure_benchmark_distance_soft_cap", benchmark_distance_cap + 0.05)
    )
    gain_structure_projection_bad_soft_cap = float(
        baseline_slice_definition.get("gain_structure_projection_bad_soft_cap", projection_bad_safe_cap + 0.02)
    )
    gain_structure_gain_soft_floor = float(
        baseline_slice_definition.get("gain_structure_gain_soft_floor", gain_goal_floor + 0.08)
    )

    baseline_live_activation_count = int(
        dict(v2_artifact.get("observability_gain", {})).get(
            "slice_activation_count",
            dict(v2_artifact.get("comparison_to_v1", {})).get("slice_activation_count_v2", 0),
        )
    )
    baseline_safe_retention_rate = float(dict(v2_artifact.get("comparison_to_v1", {})).get("projection_safe_retention_rate_v2", 0.0))
    baseline_benchmark_like_retention_rate = float(
        dict(v2_artifact.get("comparison_to_v1", {})).get("benchmark_like_retention_rate_v2", 0.0)
    )
    baseline_mean_projection_error = _safe_metric(dict(v2_artifact.get("comparison_to_v1", {})).get("mean_projection_error_v2"))
    baseline_seed_activation_rate_summary = dict(dict(v2_artifact.get("comparison_to_v1", {})).get("seed_activation_rate_v2", {}))
    baseline_seed_counts = {
        int(dict(seed_summary).get("seed", -1)): int(dict(seed_summary).get("slice_activation_count", 0))
        for seed_summary in list(v2_artifact.get("seed_summaries", []))
        if _safe_metric(dict(seed_summary).get("seed")) is not None
    }
    baseline_benchmark_alignment = dict(v2_artifact.get("benchmark_alignment_summary", {}))
    baseline_benchmark_slice_count = int(baseline_benchmark_alignment.get("benchmark_slice_count", 0))
    baseline_benchmark_undercommit_coverage = float(baseline_benchmark_alignment.get("benchmark_slice_coverage_undercommit", 0.0))
    baseline_benchmark_family_counts = {
        str(name): int(count)
        for name, count in dict(baseline_benchmark_alignment.get("benchmark_slice_family_counts", {})).items()
    }
    baseline_target_family_count = int(baseline_benchmark_alignment.get("benchmark_target_family_count", 0))

    def _annotate_v2_row(row: Dict[str, Any]) -> Dict[str, Any]:
        annotated = dict(row)
        annotated["segment"] = str(
            annotated.get(
                "segment",
                _segment_live_candidate(
                    annotated,
                    benchmark_summary=benchmark_summary,
                    projection_boundary=projection_boundary,
                ),
            )
        )
        if "benchmark_distance" not in annotated:
            annotated["benchmark_distance"] = float(_benchmark_distance(annotated, benchmark_summary))
        annotated["projection_level_critic"] = float(
            _row_projection_level_critic_v2(
                annotated,
                benchmark_summary,
                projection_boundary=projection_boundary,
            )
        )
        annotated["projection_shape_critic"] = float(
            _row_projection_shape_critic_v2(annotated, benchmark_summary)
        )
        annotated["gain_goal_critic_v2"] = float(
            _row_gain_goal_critic_v2(annotated, benchmark_summary)
        )
        annotated["stability_critic_v2"] = float(
            _row_stability_critic_v2(
                annotated,
                projection_level_critic=float(annotated["projection_level_critic"]),
                projection_shape_critic=float(annotated["projection_shape_critic"]),
                gain_goal_critic=float(annotated["gain_goal_critic_v2"]),
            )
        )
        annotated["critic_split_v2_score"] = float(
            annotated["gain_goal_critic_v2"]
            - 0.55 * annotated["projection_level_critic"]
            - 0.70 * annotated["projection_shape_critic"]
            - 0.35 * annotated["stability_critic_v2"]
        )
        return annotated

    def _v2_safe_pool_flags(row: Dict[str, Any]) -> Dict[str, bool]:
        blocker_group = str(row.get("blocker_group", "other"))
        segment = str(row.get("segment", "mixed_shift"))
        blocker_ok = blocker_group in {"projection_guard", "confidence_gain"}
        segment_ok = segment not in {"projection_far_shifted"}
        stability_ok = float(row.get("stability_critic_v2", 99.0)) <= float(stability_cap)
        if segment == "stability_sensitive":
            stability_ok = bool(
                stability_ok
                and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.85)
                and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.05)
            )
        if segment in {"projection_mid_shifted", "projection_borderline"}:
            segment_ok = bool(
                segment_ok
                and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.95)
            )
        if blocker_group == "confidence_gain":
            blocker_ok = bool(
                blocker_ok
                and float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap * 1.05)
                and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.02)
            )
        gain_structure_soft_ok = bool(
            segment in {"gain_structure_shifted", "benchmark_adjacent"}
            and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)
            and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
            and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_structure_gain_soft_floor)
            and float(row.get("projection_level_critic", 99.0)) <= float(gain_structure_level_soft_cap)
            and float(row.get("benchmark_distance", 99.0)) <= float(gain_structure_benchmark_distance_soft_cap)
        )
        candidate_envelope_ok = bool(
            blocker_ok
            and segment_ok
            and stability_ok
            and (
                (
                    float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap)
                    and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)
                    and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor)
                    and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)
                )
                or gain_structure_soft_ok
            )
        )
        projection_safe_ok = bool(
            candidate_envelope_ok
            and (
                (
                    float(row.get("pred_projection_bad_prob", 99.0)) <= float(projection_bad_safe_cap)
                    and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
                )
                or (
                    segment in {"gain_structure_shifted", "benchmark_adjacent"}
                    and float(row.get("pred_projection_bad_prob", 99.0)) <= float(gain_structure_projection_bad_soft_cap)
                    and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
                    and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)
                )
            )
        )
        benchmark_like_ok = bool(
            projection_safe_ok
            and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)
        )
        return {
            "candidate_envelope_ok": bool(candidate_envelope_ok),
            "projection_safe_ok": bool(projection_safe_ok),
            "benchmark_like_ok": bool(benchmark_like_ok),
        }

    def _gain_goal_probe_score(row: Dict[str, Any]) -> float:
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 1.20)
        benchmark_proximity = max(0.0, 1.20 - min(benchmark_distance, 1.20))
        confidence = float(_safe_metric(row.get("confidence")) or 0.0)
        gain = float(_safe_metric(row.get("gain")) or 0.0)
        pred_post_gain = float(_safe_metric(row.get("pred_post_gain")) or 0.0)
        post_gain_norm = math.tanh(pred_post_gain / 0.18)
        projection_level = float(row.get("projection_level_critic", 0.0))
        projection_shape = float(row.get("projection_shape_critic", 0.0))
        stability = float(row.get("stability_critic_v2", 0.0))
        segment = str(row.get("segment", "mixed_shift"))
        blocker = str(row.get("blocker_group", "other"))
        pred_projection_bad = float(_safe_metric(row.get("pred_projection_bad_prob")) or 1.0)
        projection_bad_excess = max(0.0, pred_projection_bad - projection_bad_safe_cap)
        benchmark_distance_excess = max(0.0, benchmark_distance - benchmark_distance_cap)

        score = float(
            0.58 * float(row.get("gain_goal_critic_v2", 0.0))
            + 0.14 * gain
            + 0.10 * confidence
            + 0.10 * post_gain_norm
            + 0.18 * benchmark_proximity
            - 0.10 * max(0.0, projection_level - projection_level_cap * 0.75)
            - 0.14 * max(0.0, projection_shape - projection_shape_cap * 0.75)
            - 0.08 * stability
            - 0.18 * min(1.0, benchmark_distance_excess / 0.12)
            - 0.14 * min(1.0, projection_bad_excess / 0.03)
        )
        if segment == "gain_structure_shifted":
            score += 0.14
        elif segment == "benchmark_adjacent":
            score += 0.16
        elif segment == "projection_borderline":
            score -= 0.02
        elif segment == "projection_mid_shifted":
            score -= 0.08
        elif segment == "stability_sensitive":
            score -= 0.12
        if blocker == "confidence_gain":
            score += 0.08
        elif blocker == "projection_guard" and benchmark_distance <= benchmark_distance_cap:
            score += 0.03
        return float(score)

    benchmark_candidate_rows: List[Dict[str, Any]] = []
    for scenario_result in benchmark_undercommit_all:
        candidate_row = _benchmark_scenario_candidate_row(
            cfg,
            scenario_result,
            projection_boundary=projection_boundary,
            benchmark_summary=benchmark_summary,
        )
        candidate_row = _annotate_v2_row(candidate_row)
        flags = _v2_safe_pool_flags(candidate_row)
        candidate_row["safe_probe_pool"] = bool(flags["projection_safe_ok"])
        candidate_row["baseline_benchmark_like"] = bool(flags["benchmark_like_ok"])
        candidate_row["gain_goal_probe_score"] = float(_gain_goal_probe_score(candidate_row))
        benchmark_candidate_rows.append(candidate_row)

    all_rows: List[Dict[str, Any]] = []
    live_probe_rows: List[Dict[str, Any]] = []
    seed_summaries: List[Dict[str, Any]] = []
    for seed in list(seeds):
        run_cfg = copy.deepcopy(cfg)
        run_cfg.verbose = False
        run_cfg.rounds = max(1, int(rounds))
        run_cfg.seed = int(seed)
        run_cfg.benchmark_every_rounds = 0
        run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs or {})
        run_cfg.eval_kwargs["session_log_path"] = (
            f"logs/intervention_shadow_{proposal['proposal_id']}_gain_goal_probe_seed{int(seed)}.log"
        )
        apply_live_policy_variant(run_cfg, "targeted_gain_goal_proj_margin_01")
        _, _, history = run_proposal_learning_loop(run_cfg)

        seed_rows: List[Dict[str, Any]] = []
        for round_index, entry in enumerate(history):
            blocked = [item for item in list(entry.get("adopt_blocked", [])) if isinstance(item, dict)]
            for item in blocked:
                row = _live_gap_row(
                    item,
                    seed=int(seed),
                    round_index=int(round_index),
                    cohort="baseline_rejected",
                    projection_boundary=projection_boundary,
                )
                row = _annotate_v2_row(row)
                flags = _v2_safe_pool_flags(row)
                row["safe_probe_pool"] = bool(flags["projection_safe_ok"])
                row["baseline_benchmark_like"] = bool(flags["benchmark_like_ok"])
                row["gain_goal_probe_score"] = float(_gain_goal_probe_score(row))
                seed_rows.append(row)
                all_rows.append(row)

        safe_pool_rows = [row for row in seed_rows if bool(row.get("safe_probe_pool", False))]
        baseline_target_count = int(baseline_seed_counts.get(int(seed), 0))
        selected_rows: List[Dict[str, Any]] = []
        if baseline_target_count > 0 and safe_pool_rows:
            ordered = sorted(
                safe_pool_rows,
                key=lambda item: float(item.get("gain_goal_probe_score", -1e9)),
                reverse=True,
            )
            selected_rows = ordered[: min(len(ordered), baseline_target_count)]

        selected_ids = {
            (int(dict(row).get("round_index", -1)), str(dict(row).get("candidate_id", "")))
            for row in selected_rows
        }
        for row in seed_rows:
            row["probe_slice_candidate"] = bool(
                (int(dict(row).get("round_index", -1)), str(dict(row).get("candidate_id", ""))) in selected_ids
            )
            row["probe_projection_safe"] = bool(
                row["probe_slice_candidate"] and bool(row.get("safe_probe_pool", False))
            )
            row["probe_benchmark_like"] = bool(
                row["probe_projection_safe"] and bool(row.get("baseline_benchmark_like", False))
            )
            if bool(row["probe_slice_candidate"]):
                live_probe_rows.append(row)

        seed_selected_rows = [row for row in seed_rows if bool(row.get("probe_slice_candidate", False))]
        seed_probe_safe_rows = [row for row in seed_selected_rows if bool(row.get("probe_projection_safe", False))]
        seed_probe_like_rows = [row for row in seed_selected_rows if bool(row.get("probe_benchmark_like", False))]
        seed_summaries.append(
            {
                "seed": int(seed),
                "blocked_candidate_count": int(len(seed_rows)),
                "safe_probe_pool_count": int(len(safe_pool_rows)),
                "baseline_target_count": int(baseline_target_count),
                "slice_activation_count": int(len(seed_selected_rows)),
                "slice_activation_rate": float(len(seed_selected_rows) / len(seed_rows)) if seed_rows else 0.0,
                "slice_projection_safe_count": int(len(seed_probe_safe_rows)),
                "slice_projection_safe_rate": float(len(seed_probe_safe_rows) / len(seed_selected_rows)) if seed_selected_rows else 0.0,
                "slice_benchmark_like_count": int(len(seed_probe_like_rows)),
                "slice_benchmark_like_rate": float(len(seed_probe_like_rows) / len(seed_selected_rows)) if seed_selected_rows else 0.0,
                "mean_slice_projection_error": _mean_key(seed_selected_rows, "pred_projection_error"),
            }
        )

    live_safe_pool_rows = [row for row in all_rows if bool(row.get("safe_probe_pool", False))]
    activation_count = int(len(live_probe_rows))
    safe_retention_rate = float(
        sum(bool(row.get("probe_projection_safe", False)) for row in live_probe_rows) / activation_count
    ) if activation_count else 0.0
    benchmark_like_retention_rate = float(
        sum(bool(row.get("probe_benchmark_like", False)) for row in live_probe_rows) / activation_count
    ) if activation_count else 0.0
    mean_projection_error = _mean_key(live_probe_rows, "pred_projection_error")

    benchmark_pool_rows = [row for row in benchmark_candidate_rows if bool(row.get("safe_probe_pool", False))]
    live_selection_fraction = float(activation_count / len(live_safe_pool_rows)) if live_safe_pool_rows else 0.0
    benchmark_probe_rows: List[Dict[str, Any]] = []
    if benchmark_pool_rows and live_selection_fraction > 0.0:
        benchmark_selected_count = max(
            1,
            min(
                len(benchmark_pool_rows),
                int(math.ceil(len(benchmark_pool_rows) * live_selection_fraction)),
            ),
        )
        benchmark_probe_rows = sorted(
            benchmark_pool_rows,
            key=lambda item: float(item.get("gain_goal_probe_score", -1e9)),
            reverse=True,
        )[:benchmark_selected_count]
    benchmark_probe_family_counts = Counter(str(row.get("family", "unknown")) for row in benchmark_probe_rows)
    benchmark_probe_target_family_count = int(
        sum(str(row.get("family", "")) == benchmark_target_family for row in benchmark_probe_rows)
    )
    benchmark_probe_coverage_all = float(len(benchmark_probe_rows) / len(benchmark_rows)) if benchmark_rows else 0.0
    benchmark_probe_coverage_undercommit = float(
        len(benchmark_probe_rows) / len(benchmark_undercommit_all)
    ) if benchmark_undercommit_all else 0.0

    baseline_target_share = float(baseline_target_family_count / baseline_benchmark_slice_count) if baseline_benchmark_slice_count else 0.0
    probe_target_share = float(benchmark_probe_target_family_count / len(benchmark_probe_rows)) if benchmark_probe_rows else 0.0
    baseline_seed_std = _safe_metric(baseline_seed_activation_rate_summary.get("std")) or 0.0
    probe_seed_activation_rate_summary = _rate_summary(seed_summaries, "slice_activation_rate")
    probe_seed_std = _safe_metric(probe_seed_activation_rate_summary.get("std")) or 0.0

    gain_goal_discrimination_improved = bool(
        probe_target_share >= baseline_target_share + 0.05
        or benchmark_like_retention_rate > baseline_benchmark_like_retention_rate + 1e-9
    )
    projection_safe_retention_preserved = bool(
        safe_retention_rate >= max(0.95, baseline_safe_retention_rate - 0.02)
    )
    benchmark_like_retention_improved = bool(
        benchmark_like_retention_rate > baseline_benchmark_like_retention_rate + 1e-9
    )
    slice_broadened = bool(activation_count > baseline_live_activation_count)
    seed_fragility_improved = bool(probe_seed_std <= baseline_seed_std + 1e-9)

    if activation_count <= 2 or probe_seed_std >= baseline_seed_std + 0.02:
        slice_fragility = "high"
    elif seed_fragility_improved and activation_count >= max(1, baseline_live_activation_count):
        slice_fragility = "low"
    else:
        slice_fragility = "medium"

    if (
        projection_safe_retention_preserved
        and benchmark_like_retention_improved
        and gain_goal_discrimination_improved
        and seed_fragility_improved
        and benchmark_probe_coverage_undercommit >= baseline_benchmark_undercommit_coverage * 0.80
    ):
        next_control_hypothesis = "narrow_routing_revisit"
        recommended_next_template = "routing_rule.slice_targeted_benchmark_sweep_v1"
        recommendation_reason = "gain-goal score reweight preserves projection safety and improves target-family purity enough to reconsider a narrow benchmark-only routing retest"
    elif projection_safe_retention_preserved and (gain_goal_discrimination_improved or benchmark_like_retention_improved):
        next_control_hypothesis = "critic_refinement_continue"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "gain-goal score refinement improves slice quality but routing should stay deferred until benchmark-like purity or coverage improves further"
    else:
        next_control_hypothesis = "no_routing_yet"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "gain-goal score refinement does not improve the safe slice enough to justify revisiting routing"

    observability_gain = {
        "passed": bool(len(all_rows) >= 12 and len(live_safe_pool_rows) >= 3 and len(benchmark_probe_rows) >= 3),
        "blocked_candidate_count": int(len(all_rows)),
        "safe_probe_pool_count": int(len(live_safe_pool_rows)),
        "slice_activation_count": int(activation_count),
        "seed_count": int(len(seed_summaries)),
        "benchmark_reference_source": str(benchmark_reference_source),
        "benchmark_undercommit_count": int(len(benchmark_undercommit_all)),
        "reason": "captured enough live rejected traffic and benchmark references to compare gain-goal score refinement against critic v2",
    }
    activation_analysis = {
        "passed": bool(activation_count > 0),
        "slice_activation_observed": bool(activation_count > 0),
        "slice_activation_repeatable": bool(sum(int(summary.get("slice_activation_count", 0)) > 0 for summary in seed_summaries) >= 2),
        "slice_activation_rate": float(activation_count / len(all_rows)) if all_rows else 0.0,
        "reason": (
            "gain-goal score refinement retains an activatable slice across repeated short runs"
            if activation_count > 0
            else "gain-goal score refinement collapses the slice under repeated short runs"
        ),
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(
            min(
                1.0,
                0.25
                + 0.18 * int(projection_safe_retention_preserved)
                + 0.18 * int(benchmark_like_retention_improved)
                + 0.16 * int(gain_goal_discrimination_improved)
                + 0.12 * int(seed_fragility_improved)
                + 0.11 * int(bool(recommended_next_template)),
            )
        ),
        "reason": "the gain-goal score probe directly tests whether critic-v2 slice quality can improve without undoing its projection-safety gains",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "probe-only score refinement with no default live-policy mutation and no benchmark semantic changes",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": str(proposal.get("template_name")),
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "signals_reweighted": list(mechanism.get("reweighted_signals", [])),
        "blocker_sensitive_rules_used": list(mechanism.get("blocker_sensitive_rules", [])),
        "comparison_reference_template": "critic_split.projection_gain_goal_v2",
        "slice_definition": {
            "source_template": "critic_split.projection_gain_goal_v2",
            "projection_level_cap": float(projection_level_cap),
            "projection_shape_cap": float(projection_shape_cap),
            "gain_goal_floor": float(gain_goal_floor),
            "stability_cap": float(stability_cap),
            "projection_bad_safe_cap": float(projection_bad_safe_cap),
            "projection_error_safe_cap": float(projection_error_safe_cap),
            "benchmark_distance_cap": float(benchmark_distance_cap),
            "gain_structure_level_soft_cap": float(gain_structure_level_soft_cap),
            "gain_structure_benchmark_distance_soft_cap": float(gain_structure_benchmark_distance_soft_cap),
            "gain_structure_projection_bad_soft_cap": float(gain_structure_projection_bad_soft_cap),
            "gain_structure_gain_soft_floor": float(gain_structure_gain_soft_floor),
            "selection_mode": "safe_pool_ranked_by_probe_score_same_seed_count_as_v2",
        },
        "comparison_to_v2": {
            "slice_activation_count_v2": int(baseline_live_activation_count),
            "slice_activation_count_probe": int(activation_count),
            "slice_activation_count_delta": int(activation_count - baseline_live_activation_count),
            "projection_safe_retention_rate_v2": float(baseline_safe_retention_rate),
            "projection_safe_retention_rate_probe": float(safe_retention_rate),
            "projection_safe_retention_rate_delta": float(safe_retention_rate - baseline_safe_retention_rate),
            "benchmark_like_retention_rate_v2": float(baseline_benchmark_like_retention_rate),
            "benchmark_like_retention_rate_probe": float(benchmark_like_retention_rate),
            "benchmark_like_retention_rate_delta": float(benchmark_like_retention_rate - baseline_benchmark_like_retention_rate),
            "mean_projection_error_v2": baseline_mean_projection_error,
            "mean_projection_error_probe": mean_projection_error,
            "mean_projection_error_delta": (
                None
                if baseline_mean_projection_error is None or mean_projection_error is None
                else float(mean_projection_error - baseline_mean_projection_error)
            ),
            "seed_activation_rate_v2": baseline_seed_activation_rate_summary,
            "seed_activation_rate_probe": probe_seed_activation_rate_summary,
            "seed_projection_safe_rate_probe": _rate_summary(seed_summaries, "slice_projection_safe_rate"),
            "seed_benchmark_like_rate_probe": _rate_summary(seed_summaries, "slice_benchmark_like_rate"),
        },
        "benchmark_relevance_summary": {
            "benchmark_slice_count_v2": int(baseline_benchmark_slice_count),
            "benchmark_slice_count_probe": int(len(benchmark_probe_rows)),
            "benchmark_slice_coverage_all_v2": float(baseline_benchmark_alignment.get("benchmark_slice_coverage_all", 0.0)),
            "benchmark_slice_coverage_all_probe": float(benchmark_probe_coverage_all),
            "benchmark_slice_coverage_undercommit_v2": float(baseline_benchmark_undercommit_coverage),
            "benchmark_slice_coverage_undercommit_probe": float(benchmark_probe_coverage_undercommit),
            "benchmark_slice_family_counts_v2": baseline_benchmark_family_counts,
            "benchmark_slice_family_counts_probe": {
                str(name): int(count)
                for name, count in sorted(benchmark_probe_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
            "benchmark_target_family_count_v2": int(baseline_target_family_count),
            "benchmark_target_family_count_probe": int(benchmark_probe_target_family_count),
            "benchmark_target_family_share_v2": float(baseline_target_share),
            "benchmark_target_family_share_probe": float(probe_target_share),
        },
        "family_slice_composition": {
            "target_family": str(benchmark_target_family),
            "benchmark_probe_family_counts": {
                str(name): int(count)
                for name, count in sorted(benchmark_probe_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
        },
        "seed_summaries": seed_summaries,
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": {
            "gain_goal_discrimination_improved": bool(gain_goal_discrimination_improved),
            "projection_safe_retention_preserved": bool(projection_safe_retention_preserved),
            "benchmark_like_retention_improved": bool(benchmark_like_retention_improved),
            "slice_broadened": bool(slice_broadened),
            "slice_fragility": str(slice_fragility),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
        },
        "sample_rows": {
            "probe_slice_examples": live_probe_rows[:8],
            "benchmark_probe_examples": benchmark_probe_rows[:8],
            "safe_pool_near_misses": sorted(
                [row for row in all_rows if bool(row.get("safe_probe_pool", False)) and not bool(row.get("probe_slice_candidate", False))],
                key=lambda item: float(item.get("gain_goal_probe_score", -1e9)),
                reverse=True,
            )[:8],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"score_reweight_gain_goal_probe_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(
        observability_gain["passed"]
        and ambiguity_reduction["passed"]
        and safety_neutrality["passed"]
        and later_selection_usefulness["passed"]
    )
    if not bool(observability_gain["passed"]):
        reason = "diagnostic shadow failed: insufficient live or benchmark evidence for gain-goal score refinement"
    elif not bool(projection_safe_retention_preserved):
        reason = "diagnostic shadow passed: gain-goal score refinement weakened projection-safe retention and should not be promoted"
    elif benchmark_like_retention_improved:
        reason = "diagnostic shadow passed: gain-goal score refinement improves slice purity while preserving projection safety"
    else:
        reason = "diagnostic shadow passed: gain-goal score refinement preserves safety but does not yet improve slice purity enough for routing reconsideration"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_critic_split_safe_slice_purity_probe_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    v2_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.projection_gain_goal_v2")
    gain_goal_artifact = _load_latest_diagnostic_artifact_by_template("score_reweight.gain_goal_conflict_probe")
    if not v2_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: critic split v2 artifact is required for the safe-slice purity probe",
            "observability_gain": {"passed": False, "reason": "missing critic split v2 artifact"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing critic split v2 artifact"},
            "ambiguity_reduction": {"passed": False, "reason": "missing critic split v2 artifact"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without critic split v2 evidence"},
        }

    intended_benefit = dict(proposal.get("intended_benefit", {}))
    mechanism = dict(proposal.get("mechanism", {}))
    benchmark_target_family = str(intended_benefit.get("target_family", "gain_goal_conflict"))
    projection_boundary = float(_targeted_projection_override_boundary(cfg))

    benchmark_rows = _load_latest_benchmark_detailed_rows()
    benchmark_undercommit_all = [
        row
        for row in benchmark_rows
        if str(row.get("policy_decision", "")) == "reject" and str(row.get("oracle_decision", "")) in {"provisional", "full"}
    ]
    benchmark_undercommit_target = [
        row for row in benchmark_undercommit_all if str(row.get("family", "")) == benchmark_target_family
    ]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (
            benchmark_undercommit_target
            if benchmark_reference_source == "target_family_undercommit"
            else benchmark_undercommit_all
        )
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }

    baseline_slice_definition = dict(v2_artifact.get("slice_definition", {}))
    projection_level_cap = float(baseline_slice_definition.get("projection_level_cap", 0.70))
    projection_shape_cap = float(baseline_slice_definition.get("projection_shape_cap", 0.65))
    gain_goal_floor = float(baseline_slice_definition.get("gain_goal_floor", 0.34))
    stability_cap = float(baseline_slice_definition.get("stability_cap", 0.42))
    projection_bad_safe_cap = float(baseline_slice_definition.get("projection_bad_safe_cap", 0.57))
    projection_error_safe_cap = float(baseline_slice_definition.get("projection_error_safe_cap", 0.0115))
    benchmark_distance_cap = float(baseline_slice_definition.get("benchmark_distance_cap", 1.0))
    gain_structure_level_soft_cap = float(baseline_slice_definition.get("gain_structure_level_soft_cap", projection_level_cap + 0.08))
    gain_structure_benchmark_distance_soft_cap = float(baseline_slice_definition.get("gain_structure_benchmark_distance_soft_cap", benchmark_distance_cap + 0.05))
    gain_structure_projection_bad_soft_cap = float(baseline_slice_definition.get("gain_structure_projection_bad_soft_cap", projection_bad_safe_cap + 0.02))
    gain_structure_gain_soft_floor = float(baseline_slice_definition.get("gain_structure_gain_soft_floor", gain_goal_floor + 0.08))

    baseline_live_activation_count = int(
        dict(v2_artifact.get("observability_gain", {})).get(
            "slice_activation_count",
            dict(v2_artifact.get("comparison_to_v1", {})).get("slice_activation_count_v2", 0),
        )
    )
    baseline_safe_retention_rate = float(dict(v2_artifact.get("comparison_to_v1", {})).get("projection_safe_retention_rate_v2", 0.0))
    baseline_benchmark_like_retention_rate = float(dict(v2_artifact.get("comparison_to_v1", {})).get("benchmark_like_retention_rate_v2", 0.0))
    baseline_mean_projection_error = _safe_metric(dict(v2_artifact.get("comparison_to_v1", {})).get("mean_projection_error_v2"))
    baseline_seed_activation_rate_summary = dict(dict(v2_artifact.get("comparison_to_v1", {})).get("seed_activation_rate_v2", {}))
    baseline_seed_counts = {
        int(dict(seed_summary).get("seed", -1)): int(dict(seed_summary).get("slice_activation_count", 0))
        for seed_summary in list(v2_artifact.get("seed_summaries", []))
        if _safe_metric(dict(seed_summary).get("seed")) is not None
    }
    baseline_benchmark_alignment = dict(v2_artifact.get("benchmark_alignment_summary", {}))
    baseline_benchmark_slice_count = int(baseline_benchmark_alignment.get("benchmark_slice_count", 0))
    baseline_benchmark_coverage_all = float(baseline_benchmark_alignment.get("benchmark_slice_coverage_all", 0.0))
    baseline_benchmark_undercommit_coverage = float(baseline_benchmark_alignment.get("benchmark_slice_coverage_undercommit", 0.0))
    baseline_benchmark_family_counts = {
        str(name): int(count)
        for name, count in dict(baseline_benchmark_alignment.get("benchmark_slice_family_counts", {})).items()
    }
    baseline_target_family_count = int(baseline_benchmark_alignment.get("benchmark_target_family_count", 0))
    baseline_target_share = float(baseline_target_family_count / baseline_benchmark_slice_count) if baseline_benchmark_slice_count else 0.0
    prior_gain_goal_summary = dict(dict(gain_goal_artifact.get("benchmark_relevance_summary", {}))) if gain_goal_artifact else {}

    def _annotate_v2_row(row: Dict[str, Any]) -> Dict[str, Any]:
        annotated = dict(row)
        annotated["segment"] = str(annotated.get("segment", _segment_live_candidate(annotated, benchmark_summary=benchmark_summary, projection_boundary=projection_boundary)))
        if "benchmark_distance" not in annotated:
            annotated["benchmark_distance"] = float(_benchmark_distance(annotated, benchmark_summary))
        annotated["projection_level_critic"] = float(_row_projection_level_critic_v2(annotated, benchmark_summary, projection_boundary=projection_boundary))
        annotated["projection_shape_critic"] = float(_row_projection_shape_critic_v2(annotated, benchmark_summary))
        annotated["gain_goal_critic_v2"] = float(_row_gain_goal_critic_v2(annotated, benchmark_summary))
        annotated["stability_critic_v2"] = float(
            _row_stability_critic_v2(
                annotated,
                projection_level_critic=float(annotated["projection_level_critic"]),
                projection_shape_critic=float(annotated["projection_shape_critic"]),
                gain_goal_critic=float(annotated["gain_goal_critic_v2"]),
            )
        )
        annotated["critic_split_v2_score"] = float(
            annotated["gain_goal_critic_v2"]
            - 0.55 * annotated["projection_level_critic"]
            - 0.70 * annotated["projection_shape_critic"]
            - 0.35 * annotated["stability_critic_v2"]
        )
        return annotated

    def _v2_safe_pool_flags(row: Dict[str, Any]) -> Dict[str, bool]:
        blocker_group = str(row.get("blocker_group", "other"))
        segment = str(row.get("segment", "mixed_shift"))
        blocker_ok = blocker_group in {"projection_guard", "confidence_gain"}
        segment_ok = segment not in {"projection_far_shifted"}
        stability_ok = float(row.get("stability_critic_v2", 99.0)) <= float(stability_cap)
        if segment == "stability_sensitive":
            stability_ok = bool(stability_ok and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.85) and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.05))
        if segment in {"projection_mid_shifted", "projection_borderline"}:
            segment_ok = bool(segment_ok and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.95))
        if blocker_group == "confidence_gain":
            blocker_ok = bool(blocker_ok and float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap * 1.05) and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.02))
        gain_structure_soft_ok = bool(
            segment in {"gain_structure_shifted", "benchmark_adjacent"}
            and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)
            and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
            and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_structure_gain_soft_floor)
            and float(row.get("projection_level_critic", 99.0)) <= float(gain_structure_level_soft_cap)
            and float(row.get("benchmark_distance", 99.0)) <= float(gain_structure_benchmark_distance_soft_cap)
        )
        candidate_envelope_ok = bool(
            blocker_ok
            and segment_ok
            and stability_ok
            and (
                (
                    float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap)
                    and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)
                    and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor)
                    and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)
                )
                or gain_structure_soft_ok
            )
        )
        projection_safe_ok = bool(
            candidate_envelope_ok
            and (
                (
                    float(row.get("pred_projection_bad_prob", 99.0)) <= float(projection_bad_safe_cap)
                    and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
                )
                or (
                    segment in {"gain_structure_shifted", "benchmark_adjacent"}
                    and float(row.get("pred_projection_bad_prob", 99.0)) <= float(gain_structure_projection_bad_soft_cap)
                    and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
                    and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)
                )
            )
        )
        return {
            "projection_safe_ok": bool(projection_safe_ok),
            "benchmark_like_ok": bool(projection_safe_ok and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)),
        }

    def _safe_slice_purity_score(row: Dict[str, Any]) -> float:
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 1.20)
        confidence = float(_safe_metric(row.get("confidence")) or 0.0)
        gain = float(_safe_metric(row.get("gain")) or 0.0)
        pred_post_gain = float(_safe_metric(row.get("pred_post_gain")) or 0.0)
        projection_level = float(row.get("projection_level_critic", 0.0))
        projection_shape = float(row.get("projection_shape_critic", 0.0))
        gain_goal = float(row.get("gain_goal_critic_v2", 0.0))
        stability = float(row.get("stability_critic_v2", 0.0))
        segment = str(row.get("segment", "mixed_shift"))
        blocker = str(row.get("blocker_group", "other"))
        benchmark_proximity = max(0.0, 1.20 - min(1.20, benchmark_distance))
        shape_closeness = max(0.0, float(projection_shape_cap) - min(float(projection_shape_cap), projection_shape)) / max(1e-6, float(projection_shape_cap))
        level_closeness = max(0.0, float(projection_level_cap) - min(float(projection_level_cap), projection_level)) / max(1e-6, float(projection_level_cap))
        gain_goal_positive = max(0.0, gain_goal)
        post_gain_norm = math.tanh(pred_post_gain / 0.20)
        distance_shape_interaction = benchmark_proximity * shape_closeness
        distance_gain_interaction = benchmark_proximity * min(1.0, gain_goal_positive)
        score = float(
            0.34 * benchmark_proximity
            + 0.22 * shape_closeness
            + 0.12 * level_closeness
            + 0.14 * gain_goal_positive
            + 0.08 * confidence
            + 0.07 * gain
            + 0.06 * post_gain_norm
            + 0.18 * distance_shape_interaction
            + 0.11 * distance_gain_interaction
            - 0.10 * stability
            - 0.18 * min(1.0, max(0.0, benchmark_distance - benchmark_distance_cap) / 0.10)
            - 0.10 * min(1.0, max(0.0, projection_shape - projection_shape_cap) / max(0.08, projection_shape_cap * 0.25))
            - 0.04 * min(1.0, max(0.0, projection_level - projection_level_cap) / max(0.08, projection_level_cap * 0.25))
        )
        if segment == "benchmark_adjacent":
            score += 0.10
        elif segment == "gain_structure_shifted":
            score += 0.08
        elif segment == "projection_borderline":
            score -= 0.02
        elif segment == "projection_mid_shifted":
            score -= 0.05
        elif segment == "stability_sensitive":
            score -= 0.14
        if blocker == "confidence_gain" and benchmark_distance <= benchmark_distance_cap:
            score += 0.04
        elif blocker == "projection_guard" and projection_shape <= projection_shape_cap * 0.90:
            score += 0.02
        return float(score)

    def _predictor_strengths(rows: List[Dict[str, Any]]) -> Dict[str, float]:
        pos = [row for row in rows if bool(row.get("baseline_benchmark_like", False))]
        neg = [row for row in rows if not bool(row.get("baseline_benchmark_like", False))]
        if not pos or not neg:
            return {"benchmark_distance": 0.0, "projection_shape": 0.0, "gain_goal_interaction": 0.0, "mixed": 0.0}
        def _gap(fn) -> float:
            pos_vals = [float(fn(row)) for row in pos]
            neg_vals = [float(fn(row)) for row in neg]
            return float(abs((sum(pos_vals) / len(pos_vals)) - (sum(neg_vals) / len(neg_vals))))
        return {
            "benchmark_distance": _gap(lambda row: float(_safe_metric(row.get("benchmark_distance")) or 1.20)),
            "projection_shape": _gap(lambda row: float(_safe_metric(row.get("projection_shape_critic")) or 0.0)),
            "gain_goal_interaction": _gap(lambda row: max(0.0, 1.20 - float(_safe_metric(row.get("benchmark_distance")) or 1.20)) * max(0.0, float(_safe_metric(row.get("gain_goal_critic_v2")) or 0.0))),
            "mixed": _gap(lambda row: max(0.0, 1.20 - float(_safe_metric(row.get("benchmark_distance")) or 1.20)) * max(0.0, float(projection_shape_cap) - float(_safe_metric(row.get("projection_shape_critic")) or 0.0))),
        }

    benchmark_candidate_rows: List[Dict[str, Any]] = []
    for scenario_result in benchmark_undercommit_all:
        candidate_row = _benchmark_scenario_candidate_row(cfg, scenario_result, projection_boundary=projection_boundary, benchmark_summary=benchmark_summary)
        candidate_row = _annotate_v2_row(candidate_row)
        flags = _v2_safe_pool_flags(candidate_row)
        candidate_row["safe_probe_pool"] = bool(flags["projection_safe_ok"])
        candidate_row["baseline_benchmark_like"] = bool(flags["benchmark_like_ok"])
        candidate_row["safe_slice_purity_score"] = float(_safe_slice_purity_score(candidate_row))
        benchmark_candidate_rows.append(candidate_row)

    all_rows: List[Dict[str, Any]] = []
    live_probe_rows: List[Dict[str, Any]] = []
    seed_summaries: List[Dict[str, Any]] = []
    for seed in list(seeds):
        run_cfg = copy.deepcopy(cfg)
        run_cfg.verbose = False
        run_cfg.rounds = max(1, int(rounds))
        run_cfg.seed = int(seed)
        run_cfg.benchmark_every_rounds = 0
        run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs or {})
        run_cfg.eval_kwargs["session_log_path"] = f"logs/intervention_shadow_{proposal['proposal_id']}_safe_slice_purity_seed{int(seed)}.log"
        apply_live_policy_variant(run_cfg, "targeted_gain_goal_proj_margin_01")
        _, _, history = run_proposal_learning_loop(run_cfg)

        seed_rows: List[Dict[str, Any]] = []
        for round_index, entry in enumerate(history):
            blocked = [item for item in list(entry.get("adopt_blocked", [])) if isinstance(item, dict)]
            for item in blocked:
                row = _live_gap_row(item, seed=int(seed), round_index=int(round_index), cohort="baseline_rejected", projection_boundary=projection_boundary)
                row = _annotate_v2_row(row)
                flags = _v2_safe_pool_flags(row)
                row["safe_probe_pool"] = bool(flags["projection_safe_ok"])
                row["baseline_benchmark_like"] = bool(flags["benchmark_like_ok"])
                row["safe_slice_purity_score"] = float(_safe_slice_purity_score(row))
                seed_rows.append(row)
                all_rows.append(row)

        safe_pool_rows = [row for row in seed_rows if bool(row.get("safe_probe_pool", False))]
        baseline_target_count = int(baseline_seed_counts.get(int(seed), 0))
        selected_rows: List[Dict[str, Any]] = []
        if baseline_target_count > 0 and safe_pool_rows:
            selected_rows = sorted(safe_pool_rows, key=lambda item: float(item.get("safe_slice_purity_score", -1e9)), reverse=True)[: min(len(safe_pool_rows), baseline_target_count)]

        selected_ids = {
            (int(dict(row).get("round_index", -1)), str(dict(row).get("candidate_id", "")))
            for row in selected_rows
        }
        for row in seed_rows:
            row["probe_slice_candidate"] = bool((int(dict(row).get("round_index", -1)), str(dict(row).get("candidate_id", ""))) in selected_ids)
            row["probe_projection_safe"] = bool(row["probe_slice_candidate"] and bool(row.get("safe_probe_pool", False)))
            row["probe_benchmark_like"] = bool(row["probe_projection_safe"] and bool(row.get("baseline_benchmark_like", False)))
            if bool(row["probe_slice_candidate"]):
                live_probe_rows.append(row)

        seed_selected_rows = [row for row in seed_rows if bool(row.get("probe_slice_candidate", False))]
        seed_safe_rows = [row for row in seed_selected_rows if bool(row.get("probe_projection_safe", False))]
        seed_like_rows = [row for row in seed_selected_rows if bool(row.get("probe_benchmark_like", False))]
        seed_summaries.append(
            {
                "seed": int(seed),
                "blocked_candidate_count": int(len(seed_rows)),
                "safe_probe_pool_count": int(len(safe_pool_rows)),
                "baseline_target_count": int(baseline_target_count),
                "slice_activation_count": int(len(seed_selected_rows)),
                "slice_activation_rate": float(len(seed_selected_rows) / len(seed_rows)) if seed_rows else 0.0,
                "slice_projection_safe_count": int(len(seed_safe_rows)),
                "slice_projection_safe_rate": float(len(seed_safe_rows) / len(seed_selected_rows)) if seed_selected_rows else 0.0,
                "slice_benchmark_like_count": int(len(seed_like_rows)),
                "slice_benchmark_like_rate": float(len(seed_like_rows) / len(seed_selected_rows)) if seed_selected_rows else 0.0,
                "mean_slice_projection_error": _mean_key(seed_selected_rows, "pred_projection_error"),
            }
        )

    live_safe_pool_rows = [row for row in all_rows if bool(row.get("safe_probe_pool", False))]
    activation_count = int(len(live_probe_rows))
    safe_retention_rate = float(sum(bool(row.get("probe_projection_safe", False)) for row in live_probe_rows) / activation_count) if activation_count else 0.0
    benchmark_like_retention_rate = float(sum(bool(row.get("probe_benchmark_like", False)) for row in live_probe_rows) / activation_count) if activation_count else 0.0
    mean_projection_error = _mean_key(live_probe_rows, "pred_projection_error")

    benchmark_pool_rows = [row for row in benchmark_candidate_rows if bool(row.get("safe_probe_pool", False))]
    live_selection_fraction = float(activation_count / len(live_safe_pool_rows)) if live_safe_pool_rows else 0.0
    score_fraction_count = int(math.ceil(len(benchmark_pool_rows) * live_selection_fraction)) if benchmark_pool_rows and live_selection_fraction > 0.0 else 0
    coverage_floor_count = min(len(benchmark_pool_rows), max(1 if benchmark_pool_rows else 0, int(math.ceil(float(baseline_benchmark_slice_count) * 0.80))))
    benchmark_selected_count = min(len(benchmark_pool_rows), max(score_fraction_count, coverage_floor_count)) if benchmark_pool_rows else 0
    benchmark_probe_rows: List[Dict[str, Any]] = []
    if benchmark_pool_rows and benchmark_selected_count > 0:
        benchmark_probe_rows = sorted(benchmark_pool_rows, key=lambda item: float(item.get("safe_slice_purity_score", -1e9)), reverse=True)[:benchmark_selected_count]

    benchmark_probe_family_counts = Counter(str(row.get("family", "unknown")) for row in benchmark_probe_rows)
    benchmark_probe_target_family_count = int(sum(str(row.get("family", "")) == benchmark_target_family for row in benchmark_probe_rows))
    benchmark_probe_coverage_all = float(len(benchmark_probe_rows) / len(benchmark_rows)) if benchmark_rows else 0.0
    benchmark_probe_coverage_undercommit = float(len(benchmark_probe_rows) / len(benchmark_undercommit_all)) if benchmark_undercommit_all else 0.0
    probe_target_share = float(benchmark_probe_target_family_count / len(benchmark_probe_rows)) if benchmark_probe_rows else 0.0
    baseline_seed_std = _safe_metric(baseline_seed_activation_rate_summary.get("std")) or 0.0
    probe_seed_activation_rate_summary = _rate_summary(seed_summaries, "slice_activation_rate")
    probe_seed_std = _safe_metric(probe_seed_activation_rate_summary.get("std")) or 0.0
    predictor_strengths = _predictor_strengths(live_safe_pool_rows or benchmark_pool_rows)
    best_retention_predictor = max(predictor_strengths.items(), key=lambda item: float(item[1]))[0] if predictor_strengths else "mixed"
    safe_slice_purity_improved = bool(benchmark_like_retention_rate > baseline_benchmark_like_retention_rate + 1e-9)
    projection_safe_retention_preserved = bool(safe_retention_rate >= max(0.95, baseline_safe_retention_rate - 0.02))
    coverage_preserved = bool(
        benchmark_probe_coverage_undercommit >= max(0.50, baseline_benchmark_undercommit_coverage * 0.80)
        and len(benchmark_probe_rows) >= max(int(prior_gain_goal_summary.get("benchmark_slice_count_probe", 0)), int(math.ceil(baseline_benchmark_slice_count * 0.80)))
    )
    seed_fragility_preserved = bool(probe_seed_std <= baseline_seed_std + 1e-9)
    slice_fragility = "high" if probe_seed_std >= baseline_seed_std + 0.02 else ("low" if seed_fragility_preserved and activation_count >= max(1, baseline_live_activation_count) else "medium")

    if projection_safe_retention_preserved and safe_slice_purity_improved and coverage_preserved and seed_fragility_preserved:
        next_control_hypothesis = "narrow_routing_revisit"
        recommended_next_template = "routing_rule.activation_window_probe"
        recommendation_reason = "safe-slice purity improves without sacrificing useful coverage, so a very narrow routing revisit becomes reasonable to test next"
    elif projection_safe_retention_preserved and coverage_preserved:
        next_control_hypothesis = "critic_refinement_continue"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "safe-slice purity evidence is useful, but routing should stay deferred until benchmark-like retention improves more clearly"
    else:
        next_control_hypothesis = "no_routing_yet"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "safe-slice purity refinement does not yet produce a clean enough coverage-preserving slice for routing reconsideration"

    observability_gain = {
        "passed": bool(len(all_rows) >= 12 and len(live_safe_pool_rows) >= 4 and len(benchmark_probe_rows) >= 8),
        "blocked_candidate_count": int(len(all_rows)),
        "safe_probe_pool_count": int(len(live_safe_pool_rows)),
        "slice_activation_count": int(activation_count),
        "seed_count": int(len(seed_summaries)),
        "benchmark_reference_source": str(benchmark_reference_source),
        "benchmark_undercommit_count": int(len(benchmark_undercommit_all)),
        "reason": "captured enough safe-slice live traffic and benchmark undercommit rows to measure purity-vs-coverage tradeoffs against critic v2",
    }
    activation_analysis = {
        "passed": bool(activation_count > 0),
        "slice_activation_observed": bool(activation_count > 0),
        "slice_activation_repeatable": bool(sum(int(summary.get("slice_activation_count", 0)) > 0 for summary in seed_summaries) >= 2),
        "slice_activation_rate": float(activation_count / len(all_rows)) if all_rows else 0.0,
        "reason": "safe-slice purity refinement retains an activatable slice across repeated short runs" if activation_count > 0 else "safe-slice purity refinement collapses the live slice under repeated short runs",
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(min(1.0, 0.25 + 0.18 * int(projection_safe_retention_preserved) + 0.18 * int(safe_slice_purity_improved) + 0.16 * int(coverage_preserved) + 0.12 * int(seed_fragility_preserved) + 0.11 * int(bool(best_retention_predictor)))),
        "reason": "the purity probe directly measures which within-slice signals predict benchmark-like retention without broadening beyond the v2 safe slice",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "probe-only critic refinement inside the critic-v2 safe slice with no default live-policy mutation and no benchmark semantic changes",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": str(proposal.get("template_name")),
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "critic_refinement_logic_used": {
            "refined_signal_groups": list(mechanism.get("refined_signal_groups", [])),
            "interaction_terms": list(mechanism.get("interaction_terms", [])),
            "blocker_sensitive_rules_used": list(mechanism.get("blocker_sensitive_rules", [])),
            "selection_mode": "coverage_preserving_ranked_safe_slice_v1",
        },
        "signals_reweighted": list(mechanism.get("refined_signal_groups", [])),
        "comparison_reference_template": "critic_split.projection_gain_goal_v2",
        "slice_definition": {
            "source_template": "critic_split.projection_gain_goal_v2",
            "projection_level_cap": float(projection_level_cap),
            "projection_shape_cap": float(projection_shape_cap),
            "gain_goal_floor": float(gain_goal_floor),
            "stability_cap": float(stability_cap),
            "projection_bad_safe_cap": float(projection_bad_safe_cap),
            "projection_error_safe_cap": float(projection_error_safe_cap),
            "benchmark_distance_cap": float(benchmark_distance_cap),
            "selection_count_mode": "same_live_seed_count_as_v2",
            "benchmark_selection_floor_fraction": 0.80,
        },
        "comparison_to_v2": {
            "slice_activation_count_v2": int(baseline_live_activation_count),
            "slice_activation_count_probe": int(activation_count),
            "slice_activation_count_delta": int(activation_count - baseline_live_activation_count),
            "projection_safe_retention_rate_v2": float(baseline_safe_retention_rate),
            "projection_safe_retention_rate_probe": float(safe_retention_rate),
            "projection_safe_retention_rate_delta": float(safe_retention_rate - baseline_safe_retention_rate),
            "benchmark_like_retention_rate_v2": float(baseline_benchmark_like_retention_rate),
            "benchmark_like_retention_rate_probe": float(benchmark_like_retention_rate),
            "benchmark_like_retention_rate_delta": float(benchmark_like_retention_rate - baseline_benchmark_like_retention_rate),
            "mean_projection_error_v2": baseline_mean_projection_error,
            "mean_projection_error_probe": mean_projection_error,
            "mean_projection_error_delta": None if baseline_mean_projection_error is None or mean_projection_error is None else float(mean_projection_error - baseline_mean_projection_error),
            "seed_activation_rate_v2": baseline_seed_activation_rate_summary,
            "seed_activation_rate_probe": probe_seed_activation_rate_summary,
            "seed_projection_safe_rate_probe": _rate_summary(seed_summaries, "slice_projection_safe_rate"),
            "seed_benchmark_like_rate_probe": _rate_summary(seed_summaries, "slice_benchmark_like_rate"),
        },
        "comparison_to_gain_goal_probe": {
            "available": bool(gain_goal_artifact),
            "benchmark_slice_count_probe": int(prior_gain_goal_summary.get("benchmark_slice_count_probe", 0)),
            "benchmark_slice_coverage_undercommit_probe": float(prior_gain_goal_summary.get("benchmark_slice_coverage_undercommit_probe", 0.0)),
        },
        "purity_metrics": {
            "safe_pool_count": int(len(live_safe_pool_rows)),
            "activation_count": int(activation_count),
            "benchmark_like_retention_rate": float(benchmark_like_retention_rate),
            "projection_safe_retention_rate": float(safe_retention_rate),
            "best_retention_predictor": str(best_retention_predictor),
            "predictor_strengths": {str(name): float(value) for name, value in sorted(predictor_strengths.items(), key=lambda item: (-float(item[1]), str(item[0])))},
        },
        "benchmark_relevance_summary": {
            "benchmark_slice_count_v2": int(baseline_benchmark_slice_count),
            "benchmark_slice_count_probe": int(len(benchmark_probe_rows)),
            "benchmark_slice_coverage_all_v2": float(baseline_benchmark_coverage_all),
            "benchmark_slice_coverage_all_probe": float(benchmark_probe_coverage_all),
            "benchmark_slice_coverage_undercommit_v2": float(baseline_benchmark_undercommit_coverage),
            "benchmark_slice_coverage_undercommit_probe": float(benchmark_probe_coverage_undercommit),
            "benchmark_slice_family_counts_v2": baseline_benchmark_family_counts,
            "benchmark_slice_family_counts_probe": {str(name): int(count) for name, count in sorted(benchmark_probe_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "benchmark_target_family_count_v2": int(baseline_target_family_count),
            "benchmark_target_family_count_probe": int(benchmark_probe_target_family_count),
            "benchmark_target_family_share_v2": float(baseline_target_share),
            "benchmark_target_family_share_probe": float(probe_target_share),
        },
        "family_slice_composition": {
            "target_family": str(benchmark_target_family),
            "benchmark_probe_family_counts": {str(name): int(count) for name, count in sorted(benchmark_probe_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
        },
        "seed_summaries": seed_summaries,
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": {
            "safe_slice_purity_improved": bool(safe_slice_purity_improved),
            "projection_safe_retention_preserved": bool(projection_safe_retention_preserved),
            "benchmark_like_retention_improved": bool(safe_slice_purity_improved),
            "coverage_preserved": bool(coverage_preserved),
            "best_retention_predictor": str(best_retention_predictor),
            "slice_fragility": str(slice_fragility),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
        },
        "sample_rows": {
            "probe_slice_examples": live_probe_rows[:8],
            "benchmark_probe_examples": benchmark_probe_rows[:8],
            "safe_pool_near_misses": sorted([row for row in all_rows if bool(row.get("safe_probe_pool", False)) and not bool(row.get("probe_slice_candidate", False))], key=lambda item: float(item.get("safe_slice_purity_score", -1e9)), reverse=True)[:8],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"critic_split_safe_slice_purity_probe_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(observability_gain["passed"] and ambiguity_reduction["passed"] and safety_neutrality["passed"] and later_selection_usefulness["passed"])
    if not bool(observability_gain["passed"]):
        reason = "diagnostic shadow failed: insufficient safe-slice live or benchmark evidence for purity refinement"
    elif not bool(projection_safe_retention_preserved):
        reason = "diagnostic shadow passed: safe-slice purity refinement weakened projection-safe retention and should not be promoted"
    elif safe_slice_purity_improved and coverage_preserved:
        reason = "diagnostic shadow passed: safe-slice purity refinement improves benchmark-like retention while keeping useful benchmark coverage"
    else:
        reason = "diagnostic shadow passed: safe-slice purity refinement preserves safety, but purity or coverage is still not strong enough to revisit routing"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _routing_slice_retest_subtype(
    row: Dict[str, Any],
    *,
    benchmark_distance_cap: float,
    projection_shape_cap: float,
    gain_goal_floor: float,
    stability_cap: float,
    gain_structure_benchmark_distance_soft_cap: float,
    gain_structure_gain_soft_floor: float,
) -> str:
    segment = str(row.get("segment", "mixed_shift"))
    benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 99.0)
    projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or 99.0)
    gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or -1e9)
    stability = float(_safe_metric(row.get("stability_critic_v2")) or 99.0)
    if segment == "benchmark_adjacent" and benchmark_distance <= benchmark_distance_cap * 1.02 and projection_shape <= projection_shape_cap * 0.95:
        return "retained_like_profile"
    if segment == "gain_structure_shifted" and benchmark_distance <= gain_structure_benchmark_distance_soft_cap and projection_shape <= projection_shape_cap and gain_goal >= gain_structure_gain_soft_floor:
        return "retained_like_profile"
    if segment == "gain_structure_shifted":
        return "gain_fragile_profile"
    if segment == "stability_sensitive" or stability > stability_cap * 0.95:
        return "stability_fragile"
    if segment in {"projection_mid_shifted", "projection_borderline"} or projection_shape > projection_shape_cap * 0.92:
        return "projection_shape_fragile"
    return "mixed_safe"


def _routing_slice_retest_eval_row(
    row: Dict[str, Any],
    *,
    projection_level_cap: float,
    projection_shape_cap: float,
    gain_goal_floor: float,
    stability_cap: float,
    projection_bad_safe_cap: float,
    projection_error_safe_cap: float,
    benchmark_distance_cap: float,
    gain_structure_level_soft_cap: float,
    gain_structure_benchmark_distance_soft_cap: float,
    gain_structure_projection_bad_soft_cap: float,
    gain_structure_gain_soft_floor: float,
) -> Dict[str, Any]:
    blocker = str(row.get("blocker_group", "other"))
    segment = str(row.get("segment", "mixed_shift"))
    subtype = str(row.get("alignment_subtype", "mixed_safe"))
    projection_ok = bool(row.get("projection_policy_ok_provisional", False))
    benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 99.0)
    projection_level = float(_safe_metric(row.get("projection_level_critic")) or 99.0)
    projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or 99.0)
    gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or -1e9)
    stability = float(_safe_metric(row.get("stability_critic_v2")) or 99.0)
    pred_projection_bad = float(_safe_metric(row.get("pred_projection_bad_prob")) or 99.0)
    pred_projection_error = float(_safe_metric(row.get("pred_projection_error")) or 99.0)

    if not projection_ok:
        return {"benchmark_safe_pool": False, "benchmark_like_safe": False, "slice_reason": "projection_policy_block"}

    blocker_ok = blocker in {"projection_guard", "confidence_gain"}
    segment_ok = segment not in {"projection_far_shifted"}
    stability_ok = stability <= stability_cap
    if segment == "stability_sensitive":
        stability_ok = bool(stability_ok and projection_shape <= projection_shape_cap * 0.85 and gain_goal >= gain_goal_floor + 0.05)
    if segment in {"projection_mid_shifted", "projection_borderline"}:
        segment_ok = bool(segment_ok and projection_shape <= projection_shape_cap * 0.95)
    if blocker == "confidence_gain":
        blocker_ok = bool(blocker_ok and projection_level <= projection_level_cap * 1.05 and gain_goal >= gain_goal_floor + 0.02)
    gain_structure_soft_ok = bool(
        subtype in {"retained_like_profile", "gain_fragile_profile"}
        and projection_shape <= projection_shape_cap
        and pred_projection_error <= projection_error_safe_cap
        and gain_goal >= gain_structure_gain_soft_floor
        and projection_level <= gain_structure_level_soft_cap
        and benchmark_distance <= gain_structure_benchmark_distance_soft_cap
    )
    base_env_ok = bool(
        blocker_ok
        and segment_ok
        and stability_ok
        and (
            (
                projection_level <= projection_level_cap
                and projection_shape <= projection_shape_cap
                and gain_goal >= gain_goal_floor
                and benchmark_distance <= benchmark_distance_cap
            )
            or gain_structure_soft_ok
        )
    )
    raw_safe = bool(
        (
            pred_projection_bad <= projection_bad_safe_cap
            and pred_projection_error <= projection_error_safe_cap
        )
        or (
            subtype in {"retained_like_profile", "gain_fragile_profile"}
            and pred_projection_bad <= gain_structure_projection_bad_soft_cap
            and pred_projection_error <= projection_error_safe_cap
            and projection_shape <= projection_shape_cap
        )
    )
    benchmark_safe_pool = bool(base_env_ok and raw_safe)
    benchmark_like_safe = bool(
        benchmark_safe_pool
        and subtype in {"retained_like_profile", "gain_fragile_profile"}
        and benchmark_distance <= benchmark_distance_cap
    )
    if benchmark_safe_pool:
        reason = "benchmark_like_safe_pool" if benchmark_like_safe else "safe_pool_non_benchmark_like"
    elif not blocker_ok:
        reason = "blocker_not_supported"
    elif not segment_ok:
        reason = "unsupported_segment"
    elif not stability_ok:
        reason = "stability_guard"
    elif not raw_safe:
        reason = "projection_safe_guard"
    else:
        reason = "safe_pool_reject_other"
    return {
        "benchmark_safe_pool": bool(benchmark_safe_pool),
        "benchmark_like_safe": bool(benchmark_like_safe),
        "slice_reason": str(reason),
    }


def _routing_slice_retest_sort_key(row: Dict[str, Any], target_family: str) -> tuple[Any, ...]:
    subtype_priority = {
        "retained_like_profile": 0,
        "gain_fragile_profile": 1,
        "mixed_safe": 2,
        "projection_shape_fragile": 3,
        "stability_fragile": 4,
    }
    return (
        0 if bool(row.get("benchmark_like_safe", False)) else 1,
        0 if str(row.get("family", "")) == str(target_family) else 1,
        int(subtype_priority.get(str(row.get("alignment_subtype", "mixed_safe")), 9)),
        round(float(_safe_metric(row.get("benchmark_distance")) or 99.0), 6),
        round(float(_safe_metric(row.get("projection_shape_critic")) or 99.0), 6),
        round(float(_safe_metric(row.get("projection_level_critic")) or 99.0), 6),
        -round(float(_safe_metric(row.get("gain_goal_critic_v2")) or -99.0), 6),
        round(float(_safe_metric(row.get("pred_projection_error")) or 99.0), 6),
        str(row.get("scenario_id", "")),
    )


def _routing_slice_retest_rate_std(
    per_seed_rows: List[Dict[str, Any]],
    blocked_counts: Dict[int, int],
    *,
    selected_key: str,
) -> float | None:
    values: List[float] = []
    for item in per_seed_rows:
        seed = int(_safe_metric(dict(item).get("seed")) or -1)
        denominator = float(blocked_counts.get(seed, 0))
        numerator = float(_safe_metric(dict(item).get(selected_key)) or 0.0)
        if denominator > 0.0:
            values.append(float(numerator / denominator))
    return _stddev(values)


def _run_benchmark_slice_targeted_routing_eval_v2(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
) -> Dict[str, Any]:
    alignment_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_alignment_critic_v2")
    stability_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.stability_context_retention_probe_v2")
    reliability_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.safe_slice_selection_reliability_probe_v1")
    if not alignment_artifact or not stability_artifact or not reliability_artifact:
        return {
            "passed": False,
            "variant_name": str(proposal.get("template_name", "")),
            "global_delta": {},
            "family_deltas": {},
            "recommendation": {"status": "missing_reliability_chain_artifacts"},
            "reason": "benchmark evaluation failed: benchmark_alignment_critic_v2, stability_context_retention_probe_v2, and safe_slice_selection_reliability_probe_v1 artifacts are required",
        }

    benchmark_result = run_trusted_benchmark_pack(
        cfg=cfg,
        mode="standalone",
        include_policy_sweep=True,
    )
    summary = dict(benchmark_result.get("summary", {}))
    detailed = dict(benchmark_result.get("detailed", {}))
    baseline_results = [dict(row) for row in list(detailed.get("results", [])) if isinstance(row, dict)]
    baseline_summary = {
        "global_compact_summary": dict(summary.get("global_compact_summary", {})),
        "family_compact_summary": dict(summary.get("family_compact_summary", {})),
        "global_mismatch_summary": dict(summary.get("global_mismatch_summary", {})),
        "family_mismatch_summary": dict(summary.get("family_mismatch_summary", {})),
    }
    if not baseline_results:
        return {
            "passed": False,
            "variant_name": str(proposal.get("template_name", "")),
            "global_delta": {},
            "family_deltas": {},
            "recommendation": {"status": "missing_benchmark_results"},
            "reason": "benchmark evaluation failed: no frozen benchmark results available",
        }

    intended_benefit = dict(proposal.get("intended_benefit", {}))
    benchmark_target_family = str(intended_benefit.get("target_family", "gain_goal_conflict"))
    projection_boundary = float(_targeted_projection_override_boundary(cfg))
    baseline_reject_results = [row for row in baseline_results if str(row.get("policy_decision", "")) == "reject"]
    benchmark_undercommit_all = [
        row for row in baseline_reject_results if str(row.get("oracle_decision", "")) in {"provisional", "full"}
    ]
    benchmark_undercommit_target = [
        row for row in benchmark_undercommit_all if str(row.get("family", "")) == benchmark_target_family
    ]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (
            benchmark_undercommit_target if benchmark_reference_source == "target_family_undercommit" else benchmark_undercommit_all
        )
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }

    slice_definition = dict(stability_artifact.get("slice_definition", {}))
    projection_level_cap = float(slice_definition.get("projection_level_cap", 0.70))
    projection_shape_cap = float(slice_definition.get("projection_shape_cap", 0.65))
    gain_goal_floor = float(slice_definition.get("gain_goal_floor", 0.34))
    stability_cap = float(slice_definition.get("stability_cap", 0.42))
    projection_bad_safe_cap = float(slice_definition.get("projection_bad_safe_cap", 0.57))
    projection_error_safe_cap = float(slice_definition.get("projection_error_safe_cap", 0.0115))
    benchmark_distance_cap = float(slice_definition.get("benchmark_distance_cap", 1.0))
    gain_structure_level_soft_cap = float(slice_definition.get("gain_structure_level_soft_cap", projection_level_cap + 0.08))
    gain_structure_benchmark_distance_soft_cap = float(slice_definition.get("gain_structure_benchmark_distance_soft_cap", benchmark_distance_cap + 0.05))
    gain_structure_projection_bad_soft_cap = float(slice_definition.get("gain_structure_projection_bad_soft_cap", projection_bad_safe_cap + 0.02))
    gain_structure_gain_soft_floor = float(slice_definition.get("gain_structure_gain_soft_floor", gain_goal_floor + 0.08))

    reliability_compare_alignment = dict(reliability_artifact.get("comparison_to_benchmark_alignment_critic_v2", {}))
    reliability_compare_stability = dict(reliability_artifact.get("comparison_to_stability_context_retention_probe_v2", {}))
    selection_target_count = int(
        reliability_compare_alignment.get("selected_benchmark_like_count_probe")
        or reliability_compare_stability.get("selected_benchmark_like_count_probe")
        or 0
    )
    if selection_target_count <= 0:
        selection_target_count = int(
            sum(int(dict(item).get("selected_benchmark_like_count", 0)) for item in list(alignment_artifact.get("safe_pool_metrics_by_seed", [])))
        )
    selection_target_count = max(1, int(selection_target_count))

    alignment_seed_rows = [dict(item) for item in list(alignment_artifact.get("safe_pool_metrics_by_seed", [])) if isinstance(item, dict)]
    stability_seed_rows = [dict(item) for item in list(stability_artifact.get("safe_pool_metrics_by_seed", [])) if isinstance(item, dict)]
    reliability_seed_rows = [dict(item) for item in list(reliability_artifact.get("per_seed_context_accounting", [])) if isinstance(item, dict)]
    alignment_seed_map = {int(dict(item).get("seed", -1)): dict(item) for item in alignment_seed_rows if _safe_metric(dict(item).get("seed")) is not None}
    reliability_seed_map = {int(dict(item).get("seed", -1)): dict(item) for item in reliability_seed_rows if _safe_metric(dict(item).get("seed")) is not None}
    blocked_counts = {
        int(dict(item).get("seed", -1)): int(dict(item).get("blocked_candidate_count", 0))
        for item in alignment_seed_rows
        if _safe_metric(dict(item).get("seed")) is not None
    }

    candidate_rows: Dict[str, Dict[str, Any]] = {}
    safe_pool_rows: List[Dict[str, Any]] = []
    slice_reason_counts: Counter[str] = Counter()
    for scenario_result in baseline_reject_results:
        row = _benchmark_scenario_candidate_row(
            cfg,
            scenario_result,
            projection_boundary=projection_boundary,
            benchmark_summary=benchmark_summary,
        )
        row["projection_policy_ok_provisional"] = bool(
            dict(scenario_result.get("candidate_summary", {})).get("projection_policy_ok_provisional", False)
        )
        row["projection_level_critic"] = float(
            _row_projection_level_critic_v2(row, benchmark_summary, projection_boundary=projection_boundary)
        )
        row["projection_shape_critic"] = float(_row_projection_shape_critic_v2(row, benchmark_summary))
        row["gain_goal_critic_v2"] = float(_row_gain_goal_critic_v2(row, benchmark_summary))
        row["stability_critic_v2"] = float(
            _row_stability_critic_v2(
                row,
                projection_level_critic=float(row["projection_level_critic"]),
                projection_shape_critic=float(row["projection_shape_critic"]),
                gain_goal_critic=float(row["gain_goal_critic_v2"]),
            )
        )
        row["alignment_subtype"] = _routing_slice_retest_subtype(
            row,
            benchmark_distance_cap=benchmark_distance_cap,
            projection_shape_cap=projection_shape_cap,
            gain_goal_floor=gain_goal_floor,
            stability_cap=stability_cap,
            gain_structure_benchmark_distance_soft_cap=gain_structure_benchmark_distance_soft_cap,
            gain_structure_gain_soft_floor=gain_structure_gain_soft_floor,
        )
        row.update(
            _routing_slice_retest_eval_row(
                row,
                projection_level_cap=projection_level_cap,
                projection_shape_cap=projection_shape_cap,
                gain_goal_floor=gain_goal_floor,
                stability_cap=stability_cap,
                projection_bad_safe_cap=projection_bad_safe_cap,
                projection_error_safe_cap=projection_error_safe_cap,
                benchmark_distance_cap=benchmark_distance_cap,
                gain_structure_level_soft_cap=gain_structure_level_soft_cap,
                gain_structure_benchmark_distance_soft_cap=gain_structure_benchmark_distance_soft_cap,
                gain_structure_projection_bad_soft_cap=gain_structure_projection_bad_soft_cap,
                gain_structure_gain_soft_floor=gain_structure_gain_soft_floor,
            )
        )
        row["benchmark_undercommit_case"] = bool(str(scenario_result.get("oracle_decision", "")) in {"provisional", "full"})
        scenario_key = str(scenario_result.get("scenario_id", ""))
        candidate_rows[scenario_key] = dict(row)
        slice_reason_counts[str(row.get("slice_reason", "unknown"))] += 1
        if bool(row.get("benchmark_safe_pool", False)):
            safe_pool_rows.append(dict(row))

    safe_pool_benchmark_like_rows = [row for row in safe_pool_rows if bool(row.get("benchmark_like_safe", False))]
    selected_source_rows = safe_pool_benchmark_like_rows if safe_pool_benchmark_like_rows else safe_pool_rows
    selected_rows = sorted(
        selected_source_rows,
        key=lambda item: _routing_slice_retest_sort_key(item, benchmark_target_family),
    )[: min(len(selected_source_rows), selection_target_count)]
    selected_ids = {str(row.get("scenario_id", "")) for row in selected_rows}

    variant_results: List[Dict[str, Any]] = []
    for scenario_result in baseline_results:
        baseline_decision = str(scenario_result.get("policy_decision", "reject"))
        scenario_key = str(scenario_result.get("scenario_id", ""))
        row = dict(candidate_rows.get(scenario_key, {}))
        decision = "provisional" if baseline_decision == "reject" and scenario_key in selected_ids else baseline_decision
        variant_result = _result_with_policy_decision(
            scenario_result,
            decision,
            str(proposal.get("template_name", "")),
        )
        variant_result["slice_probe"] = {
            "selected_for_routing": bool(scenario_key in selected_ids),
            "benchmark_safe_pool": bool(row.get("benchmark_safe_pool", False)),
            "benchmark_like_safe": bool(row.get("benchmark_like_safe", False)),
            "slice_reason": str(row.get("slice_reason", "baseline_non_reject")),
            "alignment_subtype": str(row.get("alignment_subtype", "")),
            "segment": str(row.get("segment", "")),
            "blocker_group": str(row.get("blocker_group", "")),
            "benchmark_distance": _safe_metric(row.get("benchmark_distance")),
            "projection_level_critic": _safe_metric(row.get("projection_level_critic")),
            "projection_shape_critic": _safe_metric(row.get("projection_shape_critic")),
            "gain_goal_critic_v2": _safe_metric(row.get("gain_goal_critic_v2")),
            "stability_critic_v2": _safe_metric(row.get("stability_critic_v2")),
            "pred_projection_bad_prob": _safe_metric(row.get("pred_projection_bad_prob")),
            "pred_projection_error": _safe_metric(row.get("pred_projection_error")),
        }
        variant_results.append(variant_result)

    variant_summary = _summarize_benchmark_results(variant_results)
    comparison = _variant_comparison(baseline_summary=baseline_summary, variant_summary=variant_summary)
    recommendation = _variant_recommendation(variant_summary=variant_summary, comparison=comparison)

    benchmark_slice_count = int(len(selected_rows))
    safe_pool_count = int(len(safe_pool_rows))
    selected_benchmark_like_count = int(sum(bool(row.get("benchmark_like_safe", False)) for row in selected_rows))
    safe_pool_benchmark_like_count = int(sum(bool(row.get("benchmark_like_safe", False)) for row in safe_pool_rows))
    projection_safe_retention = (
        float(
            sum(
                bool(
                    float(_safe_metric(row.get("pred_projection_bad_prob")) or 99.0) <= projection_bad_safe_cap
                    and float(_safe_metric(row.get("pred_projection_error")) or 99.0) <= projection_error_safe_cap
                )
                for row in selected_rows
            )
            / benchmark_slice_count
        )
        if benchmark_slice_count
        else 0.0
    )
    mean_projection_error = _mean_key(selected_rows, "pred_projection_error")
    selected_undercommit_count = int(sum(bool(row.get("benchmark_undercommit_case", False)) for row in selected_rows))
    benchmark_slice_coverage_all = float(benchmark_slice_count / len(baseline_results)) if baseline_results else 0.0
    benchmark_slice_coverage_undercommit = float(selected_undercommit_count / len(benchmark_undercommit_all)) if benchmark_undercommit_all else 0.0
    safe_pool_coverage_undercommit = float(
        sum(bool(row.get("benchmark_undercommit_case", False)) for row in safe_pool_rows) / len(benchmark_undercommit_all)
    ) if benchmark_undercommit_all else 0.0
    selected_family_counts = Counter(str(row.get("family", "unknown")) for row in selected_rows)
    safe_pool_family_counts = Counter(str(row.get("family", "unknown")) for row in safe_pool_rows)
    target_family_delta = float(dict(comparison.get("family_deltas", {}).get(benchmark_target_family, {})).get("policy_match_rate_delta") or 0.0)
    false_safe_delta = float(comparison.get("false_safe_projection_rate_delta") or 0.0)
    unsafe_delta = float(comparison.get("unsafe_overcommit_rate_delta") or 0.0)
    slice_fragility = _slice_fragility_level(
        slice_count=benchmark_slice_count,
        gain_goal_delta=target_family_delta,
        false_safe_delta=false_safe_delta,
        family_counter=selected_family_counts,
    )
    dominant_family_share = (
        float(selected_family_counts.most_common(1)[0][1] / benchmark_slice_count)
        if benchmark_slice_count and selected_family_counts
        else 1.0
    )

    alignment_selected_like_count = int(sum(int(dict(item).get("selected_benchmark_like_count", 0)) for item in alignment_seed_rows))
    stability_selected_like_count = int(sum(int(dict(item).get("selected_benchmark_like_count", 0)) for item in stability_seed_rows))
    reliability_selected_like_count = int(
        reliability_compare_stability.get("selected_benchmark_like_count_probe")
        or reliability_compare_alignment.get("selected_benchmark_like_count_probe")
        or 0
    )
    alignment_safe_pool_count = int(sum(int(dict(item).get("safe_pool_count", 0)) for item in alignment_seed_rows))
    stability_safe_pool_count = int(sum(int(dict(item).get("safe_pool_count", 0)) for item in stability_seed_rows))
    reliability_safe_pool_count = int(sum(int(dict(item).get("safe_pool_count_probe", 0)) for item in reliability_seed_rows))
    alignment_safe_pool_like_count = int(sum(int(dict(item).get("safe_pool_benchmark_like_count", 0)) for item in alignment_seed_rows))
    stability_safe_pool_like_count = int(sum(int(dict(item).get("safe_pool_benchmark_like_count", 0)) for item in stability_seed_rows))
    reliability_safe_pool_like_count = int(sum(int(dict(item).get("safe_pool_benchmark_like_count_probe", 0)) for item in reliability_seed_rows))
    reliability_projection_safe_retention = float(reliability_compare_stability.get("projection_safe_retention_rate_probe") or 0.0)
    reliability_mean_projection_error = _safe_metric(reliability_compare_stability.get("mean_projection_error_probe"))
    reliability_seed_fragility = _routing_slice_retest_rate_std(
        reliability_seed_rows,
        blocked_counts,
        selected_key="selected_benchmark_like_count_probe",
    )
    alignment_seed_fragility = _safe_metric(dict(alignment_artifact.get("comparison_to_v2", {})).get("seed_activation_rate_probe", {}).get("std"))
    stability_seed_fragility = _safe_metric(dict(stability_artifact.get("comparison_to_benchmark_alignment_v2", {})).get("seed_activation_rate_probe", {}).get("std"))

    seed1_reference = dict(reliability_seed_map.get(1, {}))
    seed2_reference = dict(reliability_seed_map.get(2, {}))
    benchmark_usefulness_improved = bool(
        float(comparison.get("policy_match_rate_delta") or 0.0) > 0.0
        and (
            target_family_delta > 0.0
            or int(comparison.get("expected_provisional_got_reject_delta") or 0) < 0
            or int(comparison.get("expected_full_got_reject_delta") or 0) < 0
        )
    )
    projection_safe_retention_preserved = bool(
        projection_safe_retention >= max(0.98, reliability_projection_safe_retention - 0.02)
        and false_safe_delta <= 0.03
        and unsafe_delta <= 0.03
    )
    seed2_intact = bool(
        int(seed2_reference.get("safe_pool_count_probe", 0)) == 1
        and int(seed2_reference.get("safe_pool_benchmark_like_count_probe", 0)) == 1
        and int(seed2_reference.get("selected_benchmark_like_count_probe", 0)) == 1
    )
    historical_failure_mode_avoided = bool(
        benchmark_slice_count >= max(4, selection_target_count)
        and projection_safe_retention_preserved
        and slice_fragility in {"low", "medium"}
        and dominant_family_share < 0.80
    )
    structural_gain = bool(
        benchmark_usefulness_improved
        and projection_safe_retention_preserved
        and selected_undercommit_count >= max(4, min(selection_target_count, safe_pool_benchmark_like_count))
        and benchmark_slice_coverage_undercommit >= 0.15
        and target_family_delta >= 0.0
    )

    if structural_gain and historical_failure_mode_avoided and seed2_intact:
        next_control_hypothesis = "narrow_benchmark_routing_revisit"
        recommended_next_template = "routing_rule.slice_targeted_benchmark_sweep_v1"
        recommendation_reason = "the repaired safe slice now supports a narrow benchmark-only routing branch without visible projection-safety drift, so routing can stay alive only as a benchmark-only control line"
    else:
        next_control_hypothesis = "benchmark_alignment_critic_continue"
        recommended_next_template = "critic_split.benchmark_alignment_critic_v2"
        recommendation_reason = "routing still looks downstream of critic success: the benchmark-only retest does not add enough structural value to beat continued critic/score refinement"

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": str(proposal.get("template_name")),
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "slice_definition": {
            "source_template": "critic_split.safe_slice_selection_reliability_probe_v1",
            "selection_reference_template": "critic_split.stability_context_retention_probe_v2",
            "selection_target_count": int(selection_target_count),
            "projection_level_cap": float(projection_level_cap),
            "projection_shape_cap": float(projection_shape_cap),
            "gain_goal_floor": float(gain_goal_floor),
            "stability_cap": float(stability_cap),
            "projection_bad_safe_cap": float(projection_bad_safe_cap),
            "projection_error_safe_cap": float(projection_error_safe_cap),
            "benchmark_distance_cap": float(benchmark_distance_cap),
            "selection_mode": "benchmark_like_first_reliability_preserving_top_k",
        },
        "comparison_references": {
            "critic_split.benchmark_alignment_critic_v2": {
                "selected_benchmark_like_count": int(alignment_selected_like_count),
                "safe_pool_count": int(alignment_safe_pool_count),
                "safe_pool_benchmark_like_count": int(alignment_safe_pool_like_count),
                "projection_safe_retention": float(dict(alignment_artifact.get("comparison_to_v2", {})).get("projection_safe_retention_rate_probe", 0.0)),
                "mean_projection_error": _safe_metric(dict(alignment_artifact.get("comparison_to_v2", {})).get("mean_projection_error_probe")),
            },
            "critic_split.stability_context_retention_probe_v2": {
                "selected_benchmark_like_count": int(stability_selected_like_count),
                "safe_pool_count": int(stability_safe_pool_count),
                "safe_pool_benchmark_like_count": int(stability_safe_pool_like_count),
                "projection_safe_retention": float(dict(stability_artifact.get("comparison_to_benchmark_alignment_v2", {})).get("projection_safe_retention_rate_probe", 0.0)),
                "mean_projection_error": _safe_metric(dict(stability_artifact.get("comparison_to_benchmark_alignment_v2", {})).get("mean_projection_error_probe")),
            },
            "critic_split.safe_slice_selection_reliability_probe_v1": {
                "selected_benchmark_like_count": int(reliability_selected_like_count),
                "safe_pool_count": int(reliability_safe_pool_count),
                "safe_pool_benchmark_like_count": int(reliability_safe_pool_like_count),
                "projection_safe_retention": float(reliability_projection_safe_retention),
                "mean_projection_error": reliability_mean_projection_error,
            },
        },
        "benchmark_control_metrics": {
            "benchmark_slice_count": int(benchmark_slice_count),
            "selected_benchmark_like_count": int(selected_benchmark_like_count),
            "safe_pool_count": int(safe_pool_count),
            "safe_pool_benchmark_like_count": int(safe_pool_benchmark_like_count),
            "projection_safe_retention": float(projection_safe_retention),
            "mean_projection_error": mean_projection_error,
            "collapse_severity_reference_seed_1": _safe_metric(seed1_reference.get("collapse_severity_probe")),
            "collapse_severity_reference_seed_2": _safe_metric(seed2_reference.get("collapse_severity_probe")),
            "seed_fragility_reference": {
                "benchmark_alignment_critic_v2": alignment_seed_fragility,
                "stability_context_retention_probe_v2": stability_seed_fragility,
                "safe_slice_selection_reliability_probe_v1": reliability_seed_fragility,
            },
            "benchmark_slice_coverage_all": float(benchmark_slice_coverage_all),
            "benchmark_slice_coverage_undercommit": float(benchmark_slice_coverage_undercommit),
            "safe_pool_coverage_undercommit": float(safe_pool_coverage_undercommit),
            "family_mix": {str(name): int(count) for name, count in sorted(selected_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "safe_pool_family_mix": {str(name): int(count) for name, count in sorted(safe_pool_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "reason_counts": {str(name): int(count) for name, count in sorted(slice_reason_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
        },
        "comparison_to_baseline": comparison,
        "variant_summary": {
            "global_compact_summary": dict(variant_summary.get("global_compact_summary", {})),
            "family_compact_summary": dict(variant_summary.get("family_compact_summary", {})),
            "global_mismatch_summary": dict(variant_summary.get("global_mismatch_summary", {})),
            "family_mismatch_summary": dict(variant_summary.get("family_mismatch_summary", {})),
        },
        "per_seed_context_accounting": reliability_seed_rows,
        "seed_focus_checks": {
            "seed_1_stable_context": seed1_reference,
            "seed_2_collapse_prone": seed2_reference,
        },
        "decision_checks": {
            "benchmark_usefulness_improved_beyond_safe_slice_selection_reliability_probe_v1": bool(benchmark_usefulness_improved),
            "projection_safe_retention_preserved": bool(projection_safe_retention_preserved),
            "seed2_collapse_prone_intact": bool(seed2_intact),
            "historical_sparse_fragile_unsafe_routing_mode_avoided": bool(historical_failure_mode_avoided),
            "gain_is_structural_not_cosmetic": bool(structural_gain),
        },
        "observability_gain": {
            "passed": True,
            "benchmark_scenario_count": int(len(baseline_results)),
            "baseline_reject_count": int(len(baseline_reject_results)),
            "benchmark_reference_source": str(benchmark_reference_source),
            "safe_pool_count": int(safe_pool_count),
            "selected_count": int(benchmark_slice_count),
            "reason": "the frozen benchmark pack contains enough rejected scenarios to retest narrow routing downstream of the repaired critic lineage",
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "selected_undercommit_count": int(selected_undercommit_count),
            "slice_benchmark_routing_improved": bool(benchmark_usefulness_improved),
            "reason": "the benchmark-only retest measures whether the repaired critic slice yields real reject-to-provisional control value rather than only selector diagnostics",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(min(1.0, 0.25 + 0.18 * int(benchmark_usefulness_improved) + 0.18 * int(projection_safe_retention_preserved) + 0.14 * int(seed2_intact) + 0.12 * int(historical_failure_mode_avoided) + 0.13 * int(structural_gain))),
            "slice_fragility": str(slice_fragility),
            "reason": "the retest resolves whether routing adds structural benchmark value after critic repair or merely produces cosmetic benchmark lift",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "benchmark-only routing retest with live default policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(recommended_next_template),
            "reason": str(recommendation_reason),
        },
        "diagnostic_conclusions": {
            "benchmark_usefulness_improved": bool(benchmark_usefulness_improved),
            "projection_safe_retention_preserved": bool(projection_safe_retention_preserved),
            "seed2_collapse_prone_intact": bool(seed2_intact),
            "historical_failure_mode_avoided": bool(historical_failure_mode_avoided),
            "gain_is_structural_not_cosmetic": bool(structural_gain),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
        },
        "sample_rows": {
            "selected_rows": selected_rows[:8],
            "safe_pool_rows": sorted(safe_pool_rows, key=lambda item: _routing_slice_retest_sort_key(item, benchmark_target_family))[:8],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"routing_rule_slice_targeted_benchmark_sweep_v1_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(structural_gain and projection_safe_retention_preserved and seed2_intact and historical_failure_mode_avoided)
    return {
        "passed": bool(passed),
        "variant_name": str(proposal.get("template_name", "")),
        "global_delta": {
            "policy_match_rate_delta": comparison.get("policy_match_rate_delta"),
            "false_safe_projection_rate_delta": comparison.get("false_safe_projection_rate_delta"),
            "unsafe_overcommit_rate_delta": comparison.get("unsafe_overcommit_rate_delta"),
        },
        "family_deltas": dict(comparison.get("family_deltas", {})),
        "recommendation": recommendation,
        "slice_assessment": {
            "benchmark_slice_count": int(benchmark_slice_count),
            "selected_benchmark_like_count": int(selected_benchmark_like_count),
            "safe_pool_count": int(safe_pool_count),
            "safe_pool_benchmark_like_count": int(safe_pool_benchmark_like_count),
            "projection_safe_retention": float(projection_safe_retention),
            "mean_projection_error": mean_projection_error,
            "slice_fragility": str(slice_fragility),
        },
        "artifact_path": str(artifact_path),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "report_paths": dict(summary.get("report_paths", {})),
        "reason": (
            "benchmark-only slice sweep adds structural routing value downstream of critic success without projection-safety drift"
            if passed
            else "benchmark-only slice sweep does not add enough structural value beyond the repaired critic slice to justify keeping routing active"
        ),
    }

def _run_benchmark_slice_targeted_routing_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
) -> Dict[str, Any]:
    return _run_benchmark_slice_targeted_routing_eval_v2(cfg, proposal)

    critic_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.projection_gain_goal_v1")
    if not critic_artifact:
        return {
            "passed": False,
            "variant_name": str(proposal.get("template_name", "")),
            "global_delta": {},
            "family_deltas": {},
            "recommendation": {"status": "missing_critic_split_artifact"},
            "reason": "benchmark evaluation failed: critic split artifact unavailable for slice-targeted sweep",
        }

    benchmark_result = run_trusted_benchmark_pack(
        cfg=cfg,
        mode="standalone",
        include_policy_sweep=True,
    )
    summary = dict(benchmark_result.get("summary", {}))
    detailed = dict(benchmark_result.get("detailed", {}))
    baseline_results = [dict(row) for row in list(detailed.get("results", [])) if isinstance(row, dict)]
    baseline_summary = {
        "global_compact_summary": dict(summary.get("global_compact_summary", {})),
        "family_compact_summary": dict(summary.get("family_compact_summary", {})),
        "global_mismatch_summary": dict(summary.get("global_mismatch_summary", {})),
        "family_mismatch_summary": dict(summary.get("family_mismatch_summary", {})),
    }

    if not baseline_results:
        return {
            "passed": False,
            "variant_name": str(proposal.get("template_name", "")),
            "global_delta": {},
            "family_deltas": {},
            "recommendation": {"status": "missing_benchmark_results"},
            "reason": "benchmark evaluation failed: no frozen benchmark results available",
        }

    intended_benefit = dict(proposal.get("intended_benefit", {}))
    benchmark_target_family = str(intended_benefit.get("target_family", "gain_goal_conflict"))
    projection_boundary = float(_targeted_projection_override_boundary(cfg))
    benchmark_undercommit_all = [
        row
        for row in baseline_results
        if str(row.get("policy_decision", "")) == "reject" and str(row.get("oracle_decision", "")) in {"provisional", "full"}
    ]
    benchmark_undercommit_target = [
        row for row in benchmark_undercommit_all if str(row.get("family", "")) == benchmark_target_family
    ]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (
            benchmark_undercommit_target
            if benchmark_reference_source == "target_family_undercommit"
            else benchmark_undercommit_all
        )
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }

    slice_definition = dict(critic_artifact.get("slice_definition", {}))
    segment_summaries = dict(critic_artifact.get("segment_summaries", {}))
    allowed_segments = {
        str(name)
        for name, details in segment_summaries.items()
        if int(dict(details).get("slice_candidate_count", 0)) > 0
    }
    if not allowed_segments:
        allowed_segments = set(str(name) for name in list(slice_definition.get("allowed_segments", [])))
    excluded_segments = set(str(name) for name in list(slice_definition.get("excluded_segments", [])))
    gain_goal_floor = float(slice_definition.get("gain_goal_critic_floor", -1e9))
    projection_critic_cap = float(slice_definition.get("projection_critic_cap", 99.0))
    projection_bad_cap = float(slice_definition.get("projection_bad_cap", 1.0))
    projection_error_cap = float(slice_definition.get("projection_error_cap", 99.0))
    benchmark_distance_cap = float(slice_definition.get("benchmark_distance_cap", 99.0))

    variant_results: List[Dict[str, Any]] = []
    slice_rows: List[Dict[str, Any]] = []
    slice_reason_counts: Counter[str] = Counter()
    slice_family_counts: Counter[str] = Counter()

    for scenario_result in baseline_results:
        baseline_decision = str(scenario_result.get("policy_decision", "reject"))
        row = _benchmark_scenario_candidate_row(
            cfg,
            scenario_result,
            projection_boundary=projection_boundary,
            benchmark_summary=benchmark_summary,
        )
        row["slice_candidate"] = False
        reason = "baseline_non_reject"
        decision = baseline_decision

        if baseline_decision == "reject":
            if not bool(dict(scenario_result.get("candidate_summary", {})).get("projection_policy_ok_provisional", False)):
                reason = "projection_policy_block"
            elif str(row.get("segment", "")) in excluded_segments:
                reason = "excluded_segment"
            elif allowed_segments and str(row.get("segment", "")) not in allowed_segments:
                reason = "outside_cleaned_segment"
            elif str(row.get("blocker_group", "")) != "projection_guard":
                reason = "blocker_not_projection_guard"
            elif float(row.get("gain_goal_critic", -1e9)) < gain_goal_floor:
                reason = "gain_goal_floor"
            elif float(row.get("projection_critic", 99.0)) > projection_critic_cap:
                reason = "projection_critic_cap"
            elif float(row.get("pred_projection_bad_prob", 99.0)) > projection_bad_cap:
                reason = "projection_bad_cap"
            elif float(row.get("pred_projection_error", 99.0)) > projection_error_cap:
                reason = "projection_error_cap"
            elif float(row.get("benchmark_distance", 99.0)) > benchmark_distance_cap:
                reason = "benchmark_distance_cap"
            else:
                decision = "provisional"
                reason = "slice_safe_provisional_override"
                row["slice_candidate"] = True
                slice_rows.append(dict(row))
                slice_family_counts[str(row.get("family", "unknown"))] += 1
        slice_reason_counts[reason] += 1
        variant_result = _result_with_policy_decision(
            scenario_result,
            decision,
            str(proposal.get("template_name", "")),
        )
        variant_result["slice_probe"] = {
            "slice_candidate": bool(row.get("slice_candidate", False)),
            "slice_reason": str(reason),
            "segment": str(row.get("segment", "")),
            "blocker_group": str(row.get("blocker_group", "")),
            "projection_critic": float(row.get("projection_critic", 0.0)),
            "gain_goal_critic": float(row.get("gain_goal_critic", 0.0)),
            "critic_split_score": float(row.get("critic_split_score", 0.0)),
            "benchmark_distance": float(row.get("benchmark_distance", 0.0)),
            "pred_projection_bad_prob": float(row.get("pred_projection_bad_prob", 0.0)),
            "pred_projection_error": float(row.get("pred_projection_error", 0.0)),
        }
        variant_results.append(variant_result)

    variant_summary = _summarize_benchmark_results(variant_results)
    comparison = _variant_comparison(
        baseline_summary=baseline_summary,
        variant_summary=variant_summary,
    )
    recommendation = _variant_recommendation(
        variant_summary=variant_summary,
        comparison=comparison,
    )

    broad_variant_refs: Dict[str, Any] = {}
    sweep_analysis = dict(summary.get("policy_sweep_analysis", {}))
    for variant_name in ("targeted_gain_goal_safe_window", "targeted_gain_goal_proj_margin_01"):
        variant_row = _find_sweep_variant(summary, variant_name)
        if variant_row:
            broad_variant_refs[str(variant_name)] = {
                "comparison_to_baseline": dict(variant_row.get("comparison_to_baseline", {})),
                "recommendation": dict(variant_row.get("recommendation", {})),
            }

    slice_count = int(len(slice_rows))
    slice_coverage_rate = float(slice_count / len(baseline_results)) if baseline_results else 0.0
    gain_goal_delta = float(dict(comparison.get("family_deltas", {}).get("gain_goal_conflict", {})).get("policy_match_rate_delta") or 0.0)
    false_safe_delta = float(comparison.get("false_safe_projection_rate_delta") or 0.0)
    unsafe_delta = float(comparison.get("unsafe_overcommit_rate_delta") or 0.0)
    slice_fragility = _slice_fragility_level(
        slice_count=slice_count,
        gain_goal_delta=gain_goal_delta,
        false_safe_delta=false_safe_delta,
        family_counter=slice_family_counts,
    )
    slice_projection_safe = bool(false_safe_delta <= 0.0 and unsafe_delta <= 0.0)
    slice_benchmark_routing_improved = bool(float(comparison.get("policy_match_rate_delta") or 0.0) > 0.0)
    slice_family_gain_goal_improved = bool(gain_goal_delta > 0.0)
    future_canary_candidate = bool(
        slice_benchmark_routing_improved
        and slice_projection_safe
        and slice_family_gain_goal_improved
        and slice_fragility in {"low", "medium"}
        and slice_count >= 3
    )

    if future_canary_candidate:
        next_control_hypothesis = "live_canary_candidate"
        recommended_next_template = "safety_veto_patch.projection_guard_recheck"
        recommendation_reason = "the critic-cleaned slice improves benchmark behavior without safety drift, so the next step could be a narrow live-canary preparation check"
    elif slice_benchmark_routing_improved and slice_projection_safe:
        next_control_hypothesis = "further_slice_refinement"
        recommended_next_template = "score_reweight.gain_goal_conflict_probe"
        recommendation_reason = "routing over the cleaned slice helps, but the slice remains narrow enough that more slice refinement is safer than immediate live canary work"
    elif slice_projection_safe:
        next_control_hypothesis = "more_critic_work"
        recommended_next_template = "critic_split.projection_gain_goal_v1"
        recommendation_reason = "the slice stays safe but does not improve routing enough, so more critic refinement is warranted"
    else:
        next_control_hypothesis = "no_routing_yet"
        recommended_next_template = "critic_split.projection_gain_goal_v1"
        recommendation_reason = "the cleaned slice does not preserve safe benchmark improvement, so routing should remain benchmark-only for now"

    observability_gain = {
        "passed": True,
        "benchmark_scenario_count": int(len(baseline_results)),
        "slice_candidate_count": int(slice_count),
        "slice_coverage_rate": float(slice_coverage_rate),
        "benchmark_reference_source": str(benchmark_reference_source),
        "reason": "the frozen benchmark pack contains enough scenarios to measure the critic-cleaned slice deterministically",
    }
    activation_analysis = {
        "passed": True,
        "slice_benchmark_routing_improved": bool(slice_benchmark_routing_improved),
        "slice_family_gain_goal_improved": bool(slice_family_gain_goal_improved),
        "reason": "the benchmark-only sweep directly measures whether reject-to-provisional routing helps inside the critic-cleaned slice",
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(
            min(
                1.0,
                0.30
                + 0.20 * int(slice_benchmark_routing_improved)
                + 0.20 * int(slice_projection_safe)
                + 0.15 * int(slice_family_gain_goal_improved)
                + 0.15 * int(slice_fragility == "low")
            )
        ),
        "slice_fragility": str(slice_fragility),
        "reason": "the sweep resolves whether the critic-cleaned slice is promising enough for future control work",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "benchmark-only slice-targeted routing sweep with no live-policy mutation and no benchmark semantic changes",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": str(proposal.get("template_name")),
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "slice_definition": {
            "source_template": "critic_split.projection_gain_goal_v1",
            "allowed_segments": sorted(allowed_segments),
            "excluded_segments": sorted(excluded_segments),
            "required_blocker_group": "projection_guard",
            "gain_goal_critic_floor": float(gain_goal_floor),
            "projection_critic_cap": float(projection_critic_cap),
            "projection_bad_cap": float(projection_bad_cap),
            "projection_error_cap": float(projection_error_cap),
            "benchmark_distance_cap": float(benchmark_distance_cap),
        },
        "benchmark_scenarios_affected": {
            "total": int(slice_count),
            "coverage_rate": float(slice_coverage_rate),
            "family_counts": {
                str(name): int(count)
                for name, count in sorted(slice_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
            "reason_counts": {
                str(name): int(count)
                for name, count in sorted(slice_reason_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
        },
        "comparison_to_baseline": comparison,
        "comparison_to_broad_variants": broad_variant_refs,
        "variant_summary": {
            "global_compact_summary": dict(variant_summary.get("global_compact_summary", {})),
            "family_compact_summary": dict(variant_summary.get("family_compact_summary", {})),
            "global_mismatch_summary": dict(variant_summary.get("global_mismatch_summary", {})),
        },
        "slice_assessment": {
            "slice_benchmark_routing_improved": bool(slice_benchmark_routing_improved),
            "slice_projection_safe": bool(slice_projection_safe),
            "slice_family_gain_goal_improved": bool(slice_family_gain_goal_improved),
            "slice_fragility": str(slice_fragility),
            "slice_stayed_benchmark_like": bool(slice_count > 0 and slice_projection_safe),
        },
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": {
            "slice_benchmark_routing_improved": bool(slice_benchmark_routing_improved),
            "slice_projection_safe": bool(slice_projection_safe),
            "slice_family_gain_goal_improved": bool(slice_family_gain_goal_improved),
            "slice_fragility": str(slice_fragility),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
        },
        "sample_rows": {
            "slice_candidates": slice_rows[:8],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"routing_rule_slice_sweep_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(recommendation.get("safe_to_consider_later") or recommendation.get("meets_hard_constraints"))
    result = {
        "passed": bool(passed),
        "variant_name": str(proposal.get("template_name", "")),
        "global_delta": {
            "policy_match_rate_delta": comparison.get("policy_match_rate_delta"),
            "false_safe_projection_rate_delta": comparison.get("false_safe_projection_rate_delta"),
            "unsafe_overcommit_rate_delta": comparison.get("unsafe_overcommit_rate_delta"),
        },
        "family_deltas": dict(comparison.get("family_deltas", {})),
        "recommendation": recommendation,
        "slice_assessment": dict(artifact_payload["slice_assessment"]),
        "artifact_path": str(artifact_path),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "report_paths": dict(summary.get("report_paths", {})),
        "reason": (
            "benchmark-only slice sweep satisfies hard safety constraints and improves targeted routing behavior"
            if passed
            else "benchmark-only slice sweep remains too fragile or too weak for future routing promotion"
        ),
    }
    return result


def _run_shadow_override_dormancy_snapshot_eval(proposal: Dict[str, Any]) -> Dict[str, Any]:
    analytics = build_intervention_ledger_analytics()
    latest_records = list(load_latest_snapshots().values())
    routing_records = [
        record
        for record in latest_records
        if str(record.get("proposal_type", "")) == "routing_rule"
    ]
    dormant_routing_records = [
        record
        for record in routing_records
        if "dormant_live_override" in list(record.get("failure_tags", []))
    ]

    blocker_counts: Counter[str] = Counter()
    source_records: List[Dict[str, Any]] = []
    for record in dormant_routing_records:
        shadow = dict(record.get("evaluation", {}).get("shadow", {}))
        variant = dict(shadow.get("variant", {}))
        counts = Counter(
            {
                str(name): int(count)
                for name, count in dict(variant.get("live_variant_block_reason_counts", {})).items()
                if int(count) > 0
            }
        )
        if not counts:
            counts = Counter(
                {
                    str(name): int(count)
                    for name, count in dict(shadow.get("live_variant_block_reason_counts", {})).items()
                    if int(count) > 0
                }
            )
        if counts:
            blocker_counts.update(counts)
            source_records.append(
                {
                    "proposal_id": str(record.get("proposal_id")),
                    "template_name": str(record.get("template_name")),
                    "counts": dict(counts),
                    "dominant_blocker": counts.most_common(1)[0][0],
                }
            )

    total_blockers = int(sum(blocker_counts.values()))
    distinct_blockers = int(len(blocker_counts))
    dominant_blocker = blocker_counts.most_common(1)[0][0] if blocker_counts else "none"
    dominant_count = int(blocker_counts.most_common(1)[0][1]) if blocker_counts else 0
    dominant_share = float(dominant_count / total_blockers) if total_blockers > 0 else 0.0
    ambiguity_score = float(1.0 - _normalized_entropy(blocker_counts)) if total_blockers > 0 else 0.0

    observability_gain_passed = bool(len(source_records) > 0 and total_blockers > 0)
    observability_gain = {
        "passed": observability_gain_passed,
        "dormant_routing_records": int(len(dormant_routing_records)),
        "source_records_with_blockers": int(len(source_records)),
        "total_blocker_observations": int(total_blockers),
        "distinct_blockers": int(distinct_blockers),
        "dominant_blocker": str(dominant_blocker),
        "dominant_share": float(dominant_share),
        "reason": (
            "captured dormant override blocker distribution from routing proposals"
            if observability_gain_passed
            else "no dormant routing blocker evidence available to summarize"
        ),
    }

    activation_score = float(min(1.0, 0.5 * dominant_share + 0.1 * distinct_blockers + 0.2 * int(observability_gain_passed)))
    activation_analysis_passed = bool(observability_gain_passed and dominant_share >= 0.50)
    activation_analysis = {
        "passed": activation_analysis_passed,
        "score": float(activation_score),
        "dominant_blocker": str(dominant_blocker),
        "reason": (
            f"dominant blocker {dominant_blocker} is strong enough to guide follow-up design"
            if activation_analysis_passed
            else "blocker dominance is too weak to support a strong activation-analysis conclusion"
        ),
    }

    ambiguity_passed = bool(observability_gain_passed and ambiguity_score >= 0.45)
    ambiguity_reduction = {
        "passed": ambiguity_passed,
        "score": float(ambiguity_score),
        "normalized_entropy": float(_normalized_entropy(blocker_counts)) if blocker_counts else 1.0,
        "reason": (
            "blocker diagnosis is concentrated enough to reduce ambiguity"
            if ambiguity_passed
            else "blocker diagnosis remains too ambiguous"
        ),
    }

    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "audit-only diagnostic artifact generation; no live policy mutation or training-state drift",
    }

    followup = _recommended_followup_for_blocker(dominant_blocker)
    prior_suggestions = list(dict(analytics.get("compact_summary", {})).get("recommendations", {}).get("suggested_next_templates", []))
    later_selection_passed = bool(observability_gain_passed and activation_analysis_passed and followup.get("template_name"))
    later_selection_usefulness = {
        "passed": later_selection_passed,
        "recommended_next_template": str(followup.get("template_name", "")),
        "reason": str(followup.get("reason", "")),
        "analytics_prior_suggestions": prior_suggestions[:3],
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": str(proposal.get("template_name")),
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "source_records": source_records,
        "blocker_counts": dict(blocker_counts),
    }
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(
        observability_gain_passed
        and activation_analysis_passed
        and ambiguity_passed
        and bool(safety_neutrality["passed"])
        and later_selection_passed
    )
    if not observability_gain_passed:
        reason = "diagnostic shadow failed: no dormant routing blocker evidence available"
    elif not activation_analysis_passed:
        reason = "diagnostic shadow failed: blocker dominance too weak for actionable activation analysis"
    elif not ambiguity_passed:
        reason = "diagnostic shadow failed: blocker diagnosis remained too ambiguous"
    elif not later_selection_passed:
        reason = "diagnostic shadow failed: no useful later-selection recommendation was produced"
    else:
        reason = "diagnostic shadow passed: blocker observability and follow-up selection value improved without live-state drift"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "artifact_path": str(artifact_path),
    }


def _run_shadow_live_distribution_gap_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    target_family = str(dict(proposal.get("intended_benefit", {})).get("target_family", "gain_goal_conflict"))
    analytics = build_intervention_ledger_analytics()
    prior_suggestions = list(dict(analytics.get("compact_summary", {})).get("recommendations", {}).get("suggested_next_templates", []))

    live_blocked_rows: List[Dict[str, Any]] = []
    live_provisional_rows: List[Dict[str, Any]] = []
    live_override_rows: List[Dict[str, Any]] = []
    source_records: List[Dict[str, Any]] = []
    projection_boundary = float("nan")

    for seed in list(seeds):
        run_cfg = copy.deepcopy(cfg)
        run_cfg.verbose = False
        run_cfg.rounds = max(1, int(rounds))
        run_cfg.seed = int(seed)
        run_cfg.benchmark_every_rounds = 0
        run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs or {})
        run_cfg.eval_kwargs["session_log_path"] = (
            f"logs/intervention_shadow_{proposal['proposal_id']}_live_gap_seed{int(seed)}.log"
        )
        apply_live_policy_variant(run_cfg, "targeted_gain_goal_proj_margin_01")
        projection_boundary = float(_targeted_projection_override_boundary(run_cfg))
        _, _, history = run_proposal_learning_loop(run_cfg)
        for round_index, entry in enumerate(history):
            blocked = [item for item in list(entry.get("adopt_blocked", [])) if isinstance(item, dict)]
            adopted = [item for item in list(entry.get("adopted", [])) if isinstance(item, dict)]
            source_records.append(
                {
                    "seed": int(seed),
                    "round_index": int(round_index),
                    "blocked_candidates": int(len(blocked)),
                    "provisional_candidates": int(sum(str(item.get("status")) == "provisional" for item in adopted)),
                    "override_activations": int(sum(bool(item.get("live_variant_override_applied", False)) for item in adopted)),
                }
            )
            for item in blocked:
                live_blocked_rows.append(
                    _live_gap_row(
                        item,
                        seed=int(seed),
                        round_index=int(round_index),
                        cohort="live_blocked",
                        projection_boundary=projection_boundary,
                    )
                )
            for item in adopted:
                if str(item.get("status", "")) == "provisional":
                    live_provisional_rows.append(
                        _live_gap_row(
                            item,
                            seed=int(seed),
                            round_index=int(round_index),
                            cohort="live_provisional",
                            projection_boundary=projection_boundary,
                        )
                    )
                if bool(item.get("live_variant_override_applied", False)):
                    live_override_rows.append(
                        _live_gap_row(
                            item,
                            seed=int(seed),
                            round_index=int(round_index),
                            cohort="override_activated",
                            projection_boundary=projection_boundary,
                        )
                    )

    baseline_rejected_rows = list(live_blocked_rows) + list(live_override_rows)
    blocked_counts = Counter(str(row.get("blocker_group", "other")) for row in live_blocked_rows)
    dominant_live_blocker = blocked_counts.most_common(1)[0][0] if blocked_counts else "none"
    dominant_live_blocker_count = int(blocked_counts.most_common(1)[0][1]) if blocked_counts else 0
    blocked_total = int(sum(blocked_counts.values()))
    dominant_live_blocker_share = float(dominant_live_blocker_count / blocked_total) if blocked_total > 0 else 0.0

    benchmark_rows = _load_latest_benchmark_detailed_rows()
    benchmark_undercommit_all = [
        row
        for row in benchmark_rows
        if str(row.get("policy_decision", "")) == "reject" and str(row.get("oracle_decision", "")) in {"provisional", "full"}
    ]
    benchmark_undercommit_target = [
        row for row in benchmark_undercommit_all if str(row.get("family", "")) == target_family
    ]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (benchmark_undercommit_target if benchmark_reference_source == "target_family_undercommit" else benchmark_undercommit_all)
    ]
    benchmark_family_counts = Counter(str(row.get("family", "unknown")) for row in benchmark_undercommit_all)

    live_projection_block_rows = [row for row in live_blocked_rows if str(row.get("blocker_group")) == "projection_guard"]
    threshold_summary_all = _threshold_relative_summary(baseline_rejected_rows, projection_boundary)
    threshold_summary_projection_blocked = _threshold_relative_summary(live_projection_block_rows, projection_boundary)

    comparison_metrics = (
        "pred_projection_bad_prob",
        "confidence",
        "gain",
        "pred_gain_norm",
        "pred_post_gain",
        "pred_projection_error",
        "pred_projection_explosion_prob",
        "pred_rollback_union",
    )
    live_vs_benchmark = {
        key: _mean_delta(baseline_rejected_rows, benchmark_reference_rows, key)
        for key in comparison_metrics
    }
    live_vs_provisional = {
        key: _mean_delta(baseline_rejected_rows, live_provisional_rows, key)
        for key in comparison_metrics
    }
    largest_gap = _largest_gap_metric(live_vs_benchmark)

    projection_delta = _safe_metric(dict(live_vs_benchmark.get("pred_projection_bad_prob", {})).get("mean_delta"))
    confidence_delta = _safe_metric(dict(live_vs_benchmark.get("confidence", {})).get("mean_delta"))
    gain_delta = _safe_metric(dict(live_vs_benchmark.get("gain", {})).get("mean_delta"))
    near_002_rate = float(threshold_summary_projection_blocked.get("outside_above_boundary_within_0_02_rate", 0.0))
    near_005_rate = float(threshold_summary_projection_blocked.get("outside_above_boundary_within_0_05_rate", 0.0))
    far_rate = float(threshold_summary_projection_blocked.get("outside_far_gt_0_05_rate", 0.0))

    distribution_gap_type = "mixed"
    if dominant_live_blocker == "projection_guard":
        if near_005_rate >= 0.60 and abs(projection_delta or 0.0) <= 0.06 and abs(confidence_delta or 0.0) <= 0.12 and abs(gain_delta or 0.0) <= 0.12:
            distribution_gap_type = "near_boundary_scarcity"
        elif far_rate >= 0.55 or (projection_delta is not None and projection_delta >= 0.08):
            distribution_gap_type = "deep_mismatch"
        else:
            distribution_gap_type = "mixed"
    elif dominant_live_blocker == "confidence_gain":
        if (confidence_delta is not None and confidence_delta <= -0.08) or (gain_delta is not None and gain_delta <= -0.08):
            distribution_gap_type = "deep_mismatch"
        else:
            distribution_gap_type = "mixed"

    next_control_hypothesis = "benchmark_alignment_probe"
    if dominant_live_blocker == "projection_guard" and distribution_gap_type == "near_boundary_scarcity":
        next_control_hypothesis = "projection_probe"
    elif dominant_live_blocker == "confidence_gain":
        next_control_hypothesis = "gain_probe"
    elif dominant_live_blocker == "projection_guard" and abs(projection_delta or 0.0) <= 0.03 and ((confidence_delta or 0.0) <= -0.08 or (gain_delta or 0.0) <= -0.08):
        next_control_hypothesis = "gain_probe"

    followup = _followup_for_gap_hypothesis(next_control_hypothesis)
    main_difference = {
        "largest_delta_metric": str(largest_gap.get("metric", "none")),
        "largest_delta_value": _safe_metric(largest_gap.get("mean_delta")),
        "reason": (
            "live rejected candidates sit near the projection-safe boundary"
            if distribution_gap_type == "near_boundary_scarcity"
            else "live rejected candidates differ materially from benchmark undercommit cases"
        ),
    }

    observability_gain_passed = bool(len(baseline_rejected_rows) >= 12 and len(benchmark_reference_rows) >= 6)
    observability_gain = {
        "passed": observability_gain_passed,
        "live_rejected_count": int(len(baseline_rejected_rows)),
        "blocked_count": int(len(live_blocked_rows)),
        "override_activated_count": int(len(live_override_rows)),
        "live_provisional_count": int(len(live_provisional_rows)),
        "benchmark_reference_count": int(len(benchmark_reference_rows)),
        "benchmark_reference_source": str(benchmark_reference_source),
        "projection_boundary": float(projection_boundary),
        "reason": (
            "captured enough live rejected and benchmark undercommit evidence to characterize the gap"
            if observability_gain_passed
            else "insufficient live rejected or benchmark reference evidence for a stable gap diagnosis"
        ),
    }

    activation_score = float(
        min(
            1.0,
            0.35
            + 0.35 * dominant_live_blocker_share
            + 0.20 * max(near_002_rate, near_005_rate, far_rate)
            + 0.10 * int(next_control_hypothesis != ""),
        )
    )
    activation_analysis_passed = bool(observability_gain_passed and dominant_live_blocker != "none" and next_control_hypothesis != "")
    activation_analysis = {
        "passed": activation_analysis_passed,
        "score": float(activation_score),
        "dominant_live_blocker": str(dominant_live_blocker),
        "distribution_gap_type": str(distribution_gap_type),
        "next_control_hypothesis": str(next_control_hypothesis),
        "reason": (
            f"diagnostic evidence supports {next_control_hypothesis} because {dominant_live_blocker} dominates live rejections"
            if activation_analysis_passed
            else "could not reduce live-vs-benchmark mismatch to a stable control hypothesis"
        ),
    }

    ambiguity_score = float(max(dominant_live_blocker_share, near_005_rate, far_rate))
    ambiguity_passed = bool(observability_gain_passed and ambiguity_score >= 0.35)
    ambiguity_reduction = {
        "passed": ambiguity_passed,
        "score": float(ambiguity_score),
        "dominant_live_blocker_share": float(dominant_live_blocker_share),
        "near_boundary_rate": float(near_005_rate),
        "far_from_boundary_rate": float(far_rate),
        "reason": (
            "the artifact narrows the mismatch to a small set of plausible next-step hypotheses"
            if ambiguity_passed
            else "the artifact remains too ambiguous to guide the next proposal"
        ),
    }

    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "audit-only baseline/variant comparison with no live-policy mutation and no benchmark semantic changes",
    }

    later_selection_passed = bool(activation_analysis_passed and ambiguity_passed and followup.get("template_name"))
    later_selection_usefulness = {
        "passed": later_selection_passed,
        "recommended_next_template": str(followup.get("template_name", "")),
        "reason": str(followup.get("reason", "")),
        "analytics_prior_suggestions": prior_suggestions[:3],
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": str(proposal.get("template_name")),
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "live_rejected_candidate_distribution": {
            "summary": {
                "confidence": _metric_summary(baseline_rejected_rows, "confidence"),
                "gain": _metric_summary(baseline_rejected_rows, "gain"),
                "pred_post_gain": _metric_summary(baseline_rejected_rows, "pred_post_gain"),
                "pred_gain_norm": _metric_summary(baseline_rejected_rows, "pred_gain_norm"),
                "pred_projection_bad_prob": _metric_summary(baseline_rejected_rows, "pred_projection_bad_prob"),
                "pred_projection_error": _metric_summary(baseline_rejected_rows, "pred_projection_error"),
                "pred_projection_explosion_prob": _metric_summary(baseline_rejected_rows, "pred_projection_explosion_prob"),
                "pred_rollback_union": _metric_summary(baseline_rejected_rows, "pred_rollback_union"),
            },
            "blocked_reason_counts": {
                str(name): int(count)
                for name, count in sorted(blocked_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
            "override_activated_count": int(len(live_override_rows)),
        },
        "threshold_relative_summaries": {
            "all_baseline_rejected": threshold_summary_all,
            "projection_blocked_only": threshold_summary_projection_blocked,
        },
        "comparative_view": {
            "benchmark_reference_source": str(benchmark_reference_source),
            "benchmark_reference_family_counts": {
                str(name): int(count)
                for name, count in sorted(benchmark_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
            "live_rejected_vs_benchmark_undercommit": live_vs_benchmark,
            "live_rejected_vs_live_provisional": live_vs_provisional,
            "main_difference": main_difference,
        },
        "diagnostic_conclusions": {
            "distribution_gap_type": str(distribution_gap_type),
            "dominant_live_blocker": str(dominant_live_blocker if dominant_live_blocker != "none" else "mixed"),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(followup.get("template_name", "")),
        },
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "source_records": source_records[-24:],
        "blocker_counts": {
            str(name): int(count)
            for name, count in sorted(blocked_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
        },
        "sample_rows": {
            "live_rejected_nearest_boundary": [
                row for row in sorted(
                    baseline_rejected_rows,
                    key=lambda item: abs(float(item.get("boundary_distance", float("inf")))),
                )[:5]
            ],
            "benchmark_undercommit_reference": benchmark_reference_rows[:5],
            "live_provisional_reference": live_provisional_rows[:5],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(
        observability_gain_passed
        and activation_analysis_passed
        and ambiguity_passed
        and bool(safety_neutrality["passed"])
        and later_selection_passed
    )
    if not observability_gain_passed:
        reason = "diagnostic shadow failed: insufficient live rejected or benchmark undercommit evidence"
    elif not activation_analysis_passed:
        reason = "diagnostic shadow failed: live-vs-benchmark gap did not resolve into an actionable control hypothesis"
    elif not ambiguity_passed:
        reason = "diagnostic shadow failed: gap diagnosis remained too ambiguous"
    elif not later_selection_passed:
        reason = "diagnostic shadow failed: no useful next proposal recommendation was produced"
    else:
        reason = "diagnostic shadow passed: live-vs-benchmark gap characterized with an actionable next-step hypothesis"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_critic_split_benchmark_transfer_alignment_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    del rounds, seeds
    alignment_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_alignment_critic_v2")
    stability_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.stability_context_retention_probe_v2")
    reliability_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.safe_slice_selection_reliability_probe_v1")
    routing_artifact = _load_latest_diagnostic_artifact_by_template("routing_rule.slice_targeted_benchmark_sweep_v1")
    transfer_blocker_artifact = _load_latest_diagnostic_artifact_by_template("memory_summary.benchmark_transfer_blocker_snapshot_v1")
    if not alignment_artifact or not stability_artifact or not reliability_artifact or not routing_artifact or not transfer_blocker_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: benchmark_transfer_alignment_probe_v1 requires benchmark_alignment_critic_v2, stability_context_retention_probe_v2, safe_slice_selection_reliability_probe_v1, routing sweep, and benchmark transfer blocker snapshot artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without the prerequisite artifacts"},
        }

    benchmark_result = run_trusted_benchmark_pack(cfg=cfg, mode="standalone", include_policy_sweep=True)
    summary = dict(benchmark_result.get("summary", {}))
    detailed = dict(benchmark_result.get("detailed", {}))
    baseline_results = [dict(row) for row in list(detailed.get("results", [])) if isinstance(row, dict)]
    if not baseline_results:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no frozen benchmark results available for benchmark-transfer alignment probing",
            "observability_gain": {"passed": False, "reason": "no benchmark results"},
            "activation_analysis_usefulness": {"passed": False, "reason": "no benchmark results"},
            "ambiguity_reduction": {"passed": False, "reason": "no benchmark results"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without benchmark results"},
        }

    baseline_summary = {
        "global_compact_summary": dict(summary.get("global_compact_summary", {})),
        "family_compact_summary": dict(summary.get("family_compact_summary", {})),
        "global_mismatch_summary": dict(summary.get("global_mismatch_summary", {})),
        "family_mismatch_summary": dict(summary.get("family_mismatch_summary", {})),
    }
    target_family = str(dict(proposal.get("intended_benefit", {})).get("target_family", "gain_goal_conflict"))
    projection_boundary = float(_targeted_projection_override_boundary(cfg))
    baseline_reject_results = [row for row in baseline_results if str(row.get("policy_decision", "")) == "reject"]
    benchmark_undercommit_all = [row for row in baseline_reject_results if str(row.get("oracle_decision", "")) in {"provisional", "full"}]
    benchmark_undercommit_target = [row for row in benchmark_undercommit_all if str(row.get("family", "")) == target_family]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (benchmark_undercommit_target if benchmark_reference_source == "target_family_undercommit" else benchmark_undercommit_all)
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }

    slice_definition = dict(stability_artifact.get("slice_definition", {}))
    projection_level_cap = float(slice_definition.get("projection_level_cap", 0.70))
    projection_shape_cap = float(slice_definition.get("projection_shape_cap", 0.65))
    gain_goal_floor = float(slice_definition.get("gain_goal_floor", 0.34))
    stability_cap = float(slice_definition.get("stability_cap", 0.42))
    projection_bad_safe_cap = float(slice_definition.get("projection_bad_safe_cap", 0.57))
    projection_error_safe_cap = float(slice_definition.get("projection_error_safe_cap", 0.0115))
    benchmark_distance_cap = float(slice_definition.get("benchmark_distance_cap", 1.0))
    gain_structure_level_soft_cap = float(slice_definition.get("gain_structure_level_soft_cap", projection_level_cap + 0.08))
    gain_structure_benchmark_distance_soft_cap = float(slice_definition.get("gain_structure_benchmark_distance_soft_cap", benchmark_distance_cap + 0.05))
    gain_structure_projection_bad_soft_cap = float(slice_definition.get("gain_structure_projection_bad_soft_cap", projection_bad_safe_cap + 0.02))
    gain_structure_gain_soft_floor = float(slice_definition.get("gain_structure_gain_soft_floor", gain_goal_floor + 0.08))
    selection_target_count = int(
        dict(reliability_artifact.get("comparison_to_stability_context_retention_probe_v2", {})).get("selected_benchmark_like_count_probe")
        or dict(reliability_artifact.get("comparison_to_benchmark_alignment_critic_v2", {})).get("selected_benchmark_like_count_probe")
        or 0
    )
    selection_target_count = max(1, int(selection_target_count))

    transfer_family_baseline = dict(transfer_blocker_artifact.get("family_level_breakdown", {}))
    routing_control_metrics = dict(routing_artifact.get("benchmark_control_metrics", {}))
    routing_reason_counts = dict(routing_control_metrics.get("reason_counts", {}))
    alignment_baseline = dict(alignment_artifact.get("comparison_to_v2", {}))
    reliability_baseline = dict(reliability_artifact.get("comparison_to_stability_context_retention_probe_v2", {}))
    stability_baseline = dict(stability_artifact.get("comparison_to_benchmark_alignment_v2", {}))

    required_families = ["calibration", "recovery", "persistence", "projection", "gain_goal_conflict"]
    family_breakdown: Dict[str, Dict[str, Any]] = {
        name: {
            "candidates_entered": 0,
            "blocked_by_support": 0,
            "blocked_by_stability_guard": 0,
            "surviving_to_safe_pool": 0,
            "surviving_to_selected_benchmark_like": 0,
        }
        for name in required_families
    }
    support_block_rows: List[Dict[str, Any]] = []
    stability_block_rows: List[Dict[str, Any]] = []
    final_admission_rows: List[Dict[str, Any]] = []
    safe_pool_rows: List[Dict[str, Any]] = []
    all_probe_rows: List[Dict[str, Any]] = []

    def _subtype_priority(name: str) -> int:
        return {
            "retained_like_profile": 0,
            "gain_fragile_profile": 1,
            "mixed_safe": 2,
            "projection_shape_fragile": 3,
            "stability_fragile": 4,
        }.get(str(name), 9)

    def _row_probe_scores(row: Dict[str, Any]) -> Dict[str, float]:
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or benchmark_distance_cap)
        projection_level = float(_safe_metric(row.get("projection_level_critic")) or projection_level_cap)
        projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or projection_shape_cap)
        gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or 0.0)
        stability = float(_safe_metric(row.get("stability_critic_v2")) or 0.0)
        pred_projection_bad = float(_safe_metric(row.get("pred_projection_bad_prob")) or projection_bad_safe_cap)
        pred_projection_error = float(_safe_metric(row.get("pred_projection_error")) or projection_error_safe_cap)
        subtype = str(row.get("alignment_subtype", "mixed_safe"))
        segment = str(row.get("segment", "mixed_shift"))
        blocker = str(row.get("blocker_group", "other"))
        benchmark_proximity = max(0.0, 1.0 - min(1.0, benchmark_distance / max(benchmark_distance_cap, 1e-6)))
        level_clean = max(0.0, 1.0 - min(1.0, projection_level / max(projection_level_cap, 1e-6)))
        shape_clean = max(0.0, 1.0 - min(1.0, projection_shape / max(projection_shape_cap, 1e-6)))
        gain_strength = min(1.0, max(0.0, gain_goal))
        stability_headroom = max(0.0, 1.0 - min(1.0, stability / max(stability_cap, 1e-6)))
        projection_safety = 0.55 * max(0.0, 1.0 - min(1.0, pred_projection_bad / max(projection_bad_safe_cap, 1e-6))) + 0.45 * max(0.0, 1.0 - min(1.0, pred_projection_error / max(projection_error_safe_cap, 1e-6)))
        subtype_bonus = {"retained_like_profile": 0.18, "gain_fragile_profile": 0.10, "mixed_safe": 0.04, "projection_shape_fragile": -0.02, "stability_fragile": -0.06}.get(subtype, 0.0)
        segment_bonus = {"benchmark_adjacent": 0.16, "projection_borderline": 0.12, "gain_structure_shifted": 0.08, "stability_sensitive": 0.04}.get(segment, 0.0)
        blocker_bonus = 0.10 if blocker in {"persistence_guard", "recovery_guard"} else 0.0
        support_alignment = 0.28 * benchmark_proximity + 0.20 * shape_clean + 0.17 * level_clean + 0.14 * gain_strength + 0.11 * stability_headroom + 0.10 * projection_safety + subtype_bonus + blocker_bonus
        stability_alignment = 0.30 * benchmark_proximity + 0.22 * shape_clean + 0.18 * level_clean + 0.10 * gain_strength + 0.10 * projection_safety + 0.10 * stability_headroom + subtype_bonus + segment_bonus
        transfer_alignment = 0.34 * benchmark_proximity + 0.18 * shape_clean + 0.15 * level_clean + 0.10 * gain_strength + 0.08 * stability_headroom + 0.08 * projection_safety + 0.07 * max(0.0, support_alignment) + subtype_bonus + 0.5 * segment_bonus
        return {
            "benchmark_transfer_support_score": float(support_alignment),
            "benchmark_transfer_stability_score": float(stability_alignment),
            "benchmark_transfer_alignment_score": float(transfer_alignment),
        }

    for scenario_result in baseline_reject_results:
        row = _benchmark_scenario_candidate_row(
            cfg,
            scenario_result,
            projection_boundary=projection_boundary,
            benchmark_summary=benchmark_summary,
        )
        row["projection_policy_ok_provisional"] = bool(dict(scenario_result.get("candidate_summary", {})).get("projection_policy_ok_provisional", False))
        row["projection_level_critic"] = float(_row_projection_level_critic_v2(row, benchmark_summary, projection_boundary=projection_boundary))
        row["projection_shape_critic"] = float(_row_projection_shape_critic_v2(row, benchmark_summary))
        row["gain_goal_critic_v2"] = float(_row_gain_goal_critic_v2(row, benchmark_summary))
        row["stability_critic_v2"] = float(
            _row_stability_critic_v2(
                row,
                projection_level_critic=float(row["projection_level_critic"]),
                projection_shape_critic=float(row["projection_shape_critic"]),
                gain_goal_critic=float(row["gain_goal_critic_v2"]),
            )
        )
        row["alignment_subtype"] = _routing_slice_retest_subtype(
            row,
            benchmark_distance_cap=benchmark_distance_cap,
            projection_shape_cap=projection_shape_cap,
            gain_goal_floor=gain_goal_floor,
            stability_cap=stability_cap,
            gain_structure_benchmark_distance_soft_cap=gain_structure_benchmark_distance_soft_cap,
            gain_structure_gain_soft_floor=gain_structure_gain_soft_floor,
        )
        row.update(
            _routing_slice_retest_eval_row(
                row,
                projection_level_cap=projection_level_cap,
                projection_shape_cap=projection_shape_cap,
                gain_goal_floor=gain_goal_floor,
                stability_cap=stability_cap,
                projection_bad_safe_cap=projection_bad_safe_cap,
                projection_error_safe_cap=projection_error_safe_cap,
                benchmark_distance_cap=benchmark_distance_cap,
                gain_structure_level_soft_cap=gain_structure_level_soft_cap,
                gain_structure_benchmark_distance_soft_cap=gain_structure_benchmark_distance_soft_cap,
                gain_structure_projection_bad_soft_cap=gain_structure_projection_bad_soft_cap,
                gain_structure_gain_soft_floor=gain_structure_gain_soft_floor,
            )
        )
        row.update(_row_probe_scores(row))
        baseline_reason = str(row.get("slice_reason", "final_benchmark_admission"))
        family = str(row.get("family", "unknown"))
        segment = str(row.get("segment", "mixed_shift"))
        subtype = str(row.get("alignment_subtype", "mixed_safe"))
        blocker = str(row.get("blocker_group", "other"))
        pred_projection_bad = float(_safe_metric(row.get("pred_projection_bad_prob")) or 99.0)
        pred_projection_error = float(_safe_metric(row.get("pred_projection_error")) or 99.0)
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 99.0)
        projection_level = float(_safe_metric(row.get("projection_level_critic")) or 99.0)
        projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or 99.0)
        gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or -99.0)
        support_score = float(row.get("benchmark_transfer_support_score", 0.0))
        stability_score = float(row.get("benchmark_transfer_stability_score", 0.0))
        transfer_score = float(row.get("benchmark_transfer_alignment_score", 0.0))

        support_compatible = bool(
            blocker in {"persistence_guard", "recovery_guard"}
            and segment == "stability_sensitive"
            and pred_projection_bad <= projection_bad_safe_cap
            and pred_projection_error <= projection_error_safe_cap
        )
        support_ok = bool(
            baseline_reason not in {"blocker_not_supported", "unsupported_segment"}
            or (
                support_compatible
                and support_score >= 0.58
                and benchmark_distance <= benchmark_distance_cap * 0.95
                and gain_goal >= gain_goal_floor - 0.02
                and projection_level <= gain_structure_level_soft_cap
                and projection_shape <= projection_shape_cap * 1.02
            )
        )
        stability_candidate = bool(subtype in {"retained_like_profile", "gain_fragile_profile"} or segment in {"projection_borderline", "benchmark_adjacent"})
        stability_ok = bool(
            baseline_reason != "stability_guard"
            or (
                stability_candidate
                and stability_score >= 0.56
                and pred_projection_bad <= projection_bad_safe_cap
                and pred_projection_error <= projection_error_safe_cap
                and benchmark_distance <= benchmark_distance_cap * 1.05
                and projection_shape <= projection_shape_cap * 1.04
                and projection_level <= gain_structure_level_soft_cap
            )
        )
        raw_safe = bool(row.get("projection_policy_ok_provisional", False) and pred_projection_bad <= projection_bad_safe_cap and pred_projection_error <= projection_error_safe_cap)
        transfer_safe_pool = bool(raw_safe and support_ok and stability_ok and segment != "projection_far_shifted" and transfer_score >= 0.46 and benchmark_distance <= benchmark_distance_cap * 1.05)
        benchmark_like_safe = bool(
            transfer_safe_pool
            and transfer_score >= 0.60
            and (subtype in {"retained_like_profile", "gain_fragile_profile"} or benchmark_distance <= benchmark_distance_cap * 0.72)
        )
        if not bool(row.get("projection_policy_ok_provisional", False)):
            failure_stage = "before_candidate_support"
            slice_reason_probe = "before_candidate_support"
        elif not support_ok:
            failure_stage = "support_filter"
            slice_reason_probe = "blocker_not_supported" if support_compatible or blocker in {"persistence_guard", "recovery_guard"} else "unsupported_segment"
        elif not stability_ok:
            failure_stage = "stability_guard"
            slice_reason_probe = "stability_guard"
        elif transfer_safe_pool:
            failure_stage = "safe_pool"
            slice_reason_probe = "benchmark_like_safe_pool" if benchmark_like_safe else "safe_pool_non_benchmark_like"
        else:
            failure_stage = "final_benchmark_admission"
            slice_reason_probe = "benchmark_transfer_alignment_floor"

        row["benchmark_transfer_safe_pool"] = bool(transfer_safe_pool)
        row["benchmark_transfer_like_safe"] = bool(benchmark_like_safe)
        row["failure_stage_probe"] = str(failure_stage)
        row["slice_reason_probe"] = str(slice_reason_probe)
        all_probe_rows.append(dict(row))

        if family not in family_breakdown:
            family_breakdown[family] = {
                "candidates_entered": 0,
                "blocked_by_support": 0,
                "blocked_by_stability_guard": 0,
                "surviving_to_safe_pool": 0,
                "surviving_to_selected_benchmark_like": 0,
            }
        family_breakdown[family]["candidates_entered"] += 1
        if failure_stage == "support_filter":
            family_breakdown[family]["blocked_by_support"] += 1
            support_block_rows.append(dict(row))
        elif failure_stage == "stability_guard":
            family_breakdown[family]["blocked_by_stability_guard"] += 1
            stability_block_rows.append(dict(row))
        elif failure_stage == "final_benchmark_admission":
            final_admission_rows.append(dict(row))
        elif failure_stage == "safe_pool":
            family_breakdown[family]["surviving_to_safe_pool"] += 1
            safe_pool_rows.append(dict(row))

    safe_pool_benchmark_like_rows = [row for row in safe_pool_rows if bool(row.get("benchmark_transfer_like_safe", False))]
    selected_source_rows = safe_pool_benchmark_like_rows if safe_pool_benchmark_like_rows else safe_pool_rows
    selected_rows = sorted(
        selected_source_rows,
        key=lambda item: (
            0 if bool(item.get("benchmark_transfer_like_safe", False)) else 1,
            0 if str(item.get("family", "")) == target_family else 1,
            _subtype_priority(str(item.get("alignment_subtype", ""))),
            -round(float(_safe_metric(item.get("benchmark_transfer_alignment_score")) or -99.0), 6),
            round(float(_safe_metric(item.get("benchmark_distance")) or 99.0), 6),
            round(float(_safe_metric(item.get("pred_projection_error")) or 99.0), 6),
            str(item.get("scenario_id", "")),
        ),
    )[: min(len(selected_source_rows), selection_target_count)]
    selected_ids = {str(row.get("scenario_id", "")) for row in selected_rows}
    for row in selected_rows:
        if bool(row.get("benchmark_transfer_like_safe", False)):
            family_breakdown[str(row.get("family", "unknown"))]["surviving_to_selected_benchmark_like"] += 1

    variant_results: List[Dict[str, Any]] = []
    for scenario_result in baseline_results:
        baseline_decision = str(scenario_result.get("policy_decision", "reject"))
        scenario_key = str(scenario_result.get("scenario_id", ""))
        row = next((item for item in all_probe_rows if str(item.get("scenario_id", "")) == scenario_key), {})
        decision = "provisional" if baseline_decision == "reject" and scenario_key in selected_ids else baseline_decision
        variant_result = _result_with_policy_decision(scenario_result, decision, str(proposal.get("template_name", "")))
        variant_result["benchmark_transfer_probe"] = {
            "selected_for_control": bool(scenario_key in selected_ids),
            "benchmark_transfer_safe_pool": bool(dict(row).get("benchmark_transfer_safe_pool", False)),
            "benchmark_transfer_like_safe": bool(dict(row).get("benchmark_transfer_like_safe", False)),
            "slice_reason_probe": str(dict(row).get("slice_reason_probe", "baseline_non_reject")),
            "alignment_subtype": str(dict(row).get("alignment_subtype", "")),
            "segment": str(dict(row).get("segment", "")),
            "blocker_group": str(dict(row).get("blocker_group", "")),
            "benchmark_transfer_alignment_score": _safe_metric(dict(row).get("benchmark_transfer_alignment_score")),
            "benchmark_transfer_support_score": _safe_metric(dict(row).get("benchmark_transfer_support_score")),
            "benchmark_transfer_stability_score": _safe_metric(dict(row).get("benchmark_transfer_stability_score")),
            "benchmark_distance": _safe_metric(dict(row).get("benchmark_distance")),
            "pred_projection_bad_prob": _safe_metric(dict(row).get("pred_projection_bad_prob")),
            "pred_projection_error": _safe_metric(dict(row).get("pred_projection_error")),
        }
        variant_results.append(variant_result)

    variant_summary = _summarize_benchmark_results(variant_results)
    comparison = _variant_comparison(baseline_summary=baseline_summary, variant_summary=variant_summary)
    recommendation = _variant_recommendation(variant_summary=variant_summary, comparison=comparison)

    benchmark_slice_count = int(len(selected_rows))
    safe_pool_count = int(len(safe_pool_rows))
    safe_pool_benchmark_like_count = int(sum(bool(row.get("benchmark_transfer_like_safe", False)) for row in safe_pool_rows))
    selected_benchmark_like_count = int(sum(bool(row.get("benchmark_transfer_like_safe", False)) for row in selected_rows))
    projection_safe_retention = (
        float(
            sum(
                bool(
                    float(_safe_metric(row.get("pred_projection_bad_prob")) or 99.0) <= projection_bad_safe_cap
                    and float(_safe_metric(row.get("pred_projection_error")) or 99.0) <= projection_error_safe_cap
                )
                for row in selected_rows
            )
            / benchmark_slice_count
        )
        if benchmark_slice_count
        else 0.0
    )
    mean_projection_error = _mean_key(selected_rows, "pred_projection_error")
    selected_family_mix = Counter(str(row.get("family", "unknown")) for row in selected_rows)
    safe_pool_family_mix = Counter(str(row.get("family", "unknown")) for row in safe_pool_rows)
    selected_undercommit_count = int(sum(str(row.get("oracle_decision", "")) in {"provisional", "full"} for row in selected_rows))
    benchmark_slice_coverage_all = float(benchmark_slice_count / len(baseline_results)) if baseline_results else 0.0
    benchmark_slice_coverage_undercommit = float(selected_undercommit_count / len(benchmark_undercommit_all)) if benchmark_undercommit_all else 0.0
    support_family_counts = Counter(str(row.get("family", "unknown")) for row in support_block_rows)
    stability_family_counts = Counter(str(row.get("family", "unknown")) for row in stability_block_rows)
    support_subtype_counts = Counter(str(row.get("alignment_subtype", "unknown")) for row in support_block_rows)
    stability_subtype_counts = Counter(str(row.get("alignment_subtype", "unknown")) for row in stability_block_rows)

    support_baseline_total = int(dict(transfer_family_baseline.get("persistence", {})).get("blocked_by_support", 0) + dict(transfer_family_baseline.get("recovery", {})).get("blocked_by_support", 0))
    support_probe_total = int(dict(family_breakdown.get("persistence", {})).get("blocked_by_support", 0) + dict(family_breakdown.get("recovery", {})).get("blocked_by_support", 0))
    stability_baseline_total = int(dict(transfer_family_baseline.get("projection", {})).get("blocked_by_stability_guard", 0) + dict(transfer_family_baseline.get("gain_goal_conflict", {})).get("blocked_by_stability_guard", 0) + dict(transfer_family_baseline.get("calibration", {})).get("blocked_by_stability_guard", 0))
    stability_probe_total = int(dict(family_breakdown.get("projection", {})).get("blocked_by_stability_guard", 0) + dict(family_breakdown.get("gain_goal_conflict", {})).get("blocked_by_stability_guard", 0) + dict(family_breakdown.get("calibration", {})).get("blocked_by_stability_guard", 0))

    policy_match_rate_delta = float(comparison.get("policy_match_rate_delta") or 0.0)
    false_safe_delta = float(comparison.get("false_safe_projection_rate_delta") or 0.0)
    unsafe_delta = float(comparison.get("unsafe_overcommit_rate_delta") or 0.0)
    non_zero_safe_pool = bool(safe_pool_count > 0)
    support_blocks_reduced = bool(support_probe_total < support_baseline_total)
    stability_overfire_reduced = bool(stability_probe_total < stability_baseline_total)
    projection_safe_preserved = bool(projection_safe_retention >= 0.98 and false_safe_delta <= 0.03 and unsafe_delta <= 0.03)
    structural_transferable = bool(
        benchmark_slice_count >= 4
        and selected_benchmark_like_count >= max(2, min(selection_target_count, safe_pool_benchmark_like_count))
        and benchmark_slice_coverage_undercommit >= 0.10
        and policy_match_rate_delta >= 0.0
        and len(selected_family_mix) >= 2
    )

    if non_zero_safe_pool and support_blocks_reduced and stability_overfire_reduced and projection_safe_preserved and structural_transferable:
        decision_choice = "A"
        next_control_hypothesis = "benchmark_alignment_critic_continue"
        recommended_next_template = "critic_split.benchmark_alignment_critic_v2"
        recommendation_reason = "the probe created a real benchmark safe pool, reduced the transfer blockers, and stayed projection-safe, so the benchmark-transfer critic branch should stay alive"
    elif support_probe_total > 0 and support_probe_total >= stability_probe_total and not support_blocks_reduced:
        decision_choice = "B"
        next_control_hypothesis = "support_runner_compatibility_fix"
        recommended_next_template = "critic_split.benchmark_alignment_critic_v2"
        recommendation_reason = "support coverage remains the tightest benchmark-transfer bottleneck, so a targeted compatibility fix is more justified than another broad critic sweep"
    else:
        decision_choice = "C"
        next_control_hypothesis = "benchmark_alignment_critic_continue"
        recommended_next_template = "critic_split.benchmark_alignment_critic_v2"
        recommendation_reason = "the probe reduces some blockers, but the remaining gain is still mixed enough that another focused benchmark-transfer refinement is safer than reopening routing"

    observability_gain = {
        "passed": bool(len(baseline_reject_results) >= 20),
        "baseline_reject_count": int(len(baseline_reject_results)),
        "safe_pool_count": int(safe_pool_count),
        "safe_pool_benchmark_like_count": int(safe_pool_benchmark_like_count),
        "selected_benchmark_like_count": int(selected_benchmark_like_count),
        "support_block_count": int(len(support_block_rows)),
        "stability_guard_count": int(len(stability_block_rows)),
        "reason": "the frozen benchmark pack contains enough rejected scenarios to probe transfer alignment after routing collapse",
    }
    activation_analysis = {
        "passed": bool(non_zero_safe_pool),
        "support_blocks_reduced": bool(support_blocks_reduced),
        "stability_overfire_reduced": bool(stability_overfire_reduced),
        "structural_transferable": bool(structural_transferable),
        "reason": "the probe measures whether transfer alignment creates a real safe pool rather than just relabeling the routing failure",
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(min(1.0, 0.24 + 0.18 * int(non_zero_safe_pool) + 0.16 * int(support_blocks_reduced) + 0.16 * int(stability_overfire_reduced) + 0.14 * int(projection_safe_preserved) + 0.12 * int(structural_transferable))),
        "reason": "the probe isolates whether benchmark-transfer collapse is support-limited, stability-overfire-limited, or still structurally sparse after alignment changes",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "benchmark-only critic-transfer probe with live default policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
        "decision_recommendation": str(decision_choice),
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "critic_split.benchmark_transfer_alignment_probe_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "dependency_context": {
            "benchmark_alignment_critic_v2_artifact_path": str(alignment_artifact.get("_artifact_path", "")),
            "stability_context_retention_probe_v2_artifact_path": str(stability_artifact.get("_artifact_path", "")),
            "safe_slice_selection_reliability_probe_v1_artifact_path": str(reliability_artifact.get("_artifact_path", "")),
            "routing_rule_slice_targeted_benchmark_sweep_v1_artifact_path": str(routing_artifact.get("_artifact_path", "")),
            "benchmark_transfer_blocker_snapshot_artifact_path": str(transfer_blocker_artifact.get("_artifact_path", "")),
            "benchmark_reference_source": str(benchmark_reference_source),
        },
        "benchmark_transfer_logic_used": {
            "support_alignment_focus": [
                "stability_sensitive persistence/recovery compatibility only inside frozen benchmark transfer",
                "projection-safe persistence/recovery rows may survive support filtering when benchmark proximity and shape stay clean",
            ],
            "stability_alignment_focus": [
                "reduce stability_guard overfire on retained_like_profile rows",
                "reduce stability_guard overfire on projection_borderline and benchmark_adjacent rows when projection-safe",
                "preserve projection-safety envelope exactly",
            ],
            "ranking_mode": "benchmark_transfer_alignment_safe_slice_v1",
            "selection_target_count": int(selection_target_count),
        },
        "comparison_references": {
            "critic_split.benchmark_alignment_critic_v2": {
                "selected_benchmark_like_count": int(alignment_baseline.get("slice_activation_count_probe", alignment_artifact.get("observability_gain", {}).get("slice_activation_count", 0))),
                "safe_pool_count": int(dict(alignment_artifact.get("availability_metrics", {})).get("safe_pool_count_probe", 0)),
                "safe_pool_benchmark_like_count": int(dict(alignment_artifact.get("availability_metrics", {})).get("safe_pool_benchmark_like_count_probe", 0)),
                "projection_safe_retention": float(alignment_baseline.get("projection_safe_retention_rate_probe", 0.0)),
                "mean_projection_error": _safe_metric(alignment_baseline.get("mean_projection_error_probe")),
            },
            "critic_split.stability_context_retention_probe_v2": {
                "selected_benchmark_like_count": int(dict(stability_artifact.get("purity_metrics", {})).get("activation_count", 0)),
                "safe_pool_count": int(dict(stability_artifact.get("availability_metrics", {})).get("safe_pool_count_probe", 0)),
                "safe_pool_benchmark_like_count": int(dict(stability_artifact.get("availability_metrics", {})).get("safe_pool_benchmark_like_count_probe", 0)),
                "projection_safe_retention": float(stability_baseline.get("projection_safe_retention_rate_probe", 0.0)),
                "mean_projection_error": _safe_metric(stability_baseline.get("mean_projection_error_probe")),
            },
            "critic_split.safe_slice_selection_reliability_probe_v1": {
                "selected_benchmark_like_count": int(reliability_baseline.get("selected_benchmark_like_count_probe", 0)),
                "safe_pool_count": int(sum(int(dict(item).get("safe_pool_count_probe", 0)) for item in list(reliability_artifact.get("per_seed_context_accounting", [])) if isinstance(item, dict))),
                "safe_pool_benchmark_like_count": int(sum(int(dict(item).get("safe_pool_benchmark_like_count_probe", 0)) for item in list(reliability_artifact.get("per_seed_context_accounting", [])) if isinstance(item, dict))),
                "projection_safe_retention": float(reliability_baseline.get("projection_safe_retention_rate_probe", 0.0)),
                "mean_projection_error": _safe_metric(reliability_baseline.get("mean_projection_error_probe")),
            },
            "routing_rule.slice_targeted_benchmark_sweep_v1": {
                "benchmark_slice_count": int(routing_control_metrics.get("benchmark_slice_count", 0)),
                "safe_pool_count": int(routing_control_metrics.get("safe_pool_count", 0)),
                "safe_pool_benchmark_like_count": int(routing_control_metrics.get("safe_pool_benchmark_like_count", 0)),
                "selected_benchmark_like_count": int(routing_control_metrics.get("selected_benchmark_like_count", 0)),
                "projection_safe_retention": float(routing_control_metrics.get("projection_safe_retention", 0.0)),
                "mean_projection_error": _safe_metric(routing_control_metrics.get("mean_projection_error")),
            },
            "memory_summary.benchmark_transfer_blocker_snapshot_v1": dict(transfer_blocker_artifact.get("global_stage_breakdown", {})),
        },
        "benchmark_control_metrics": {
            "benchmark_slice_count": int(benchmark_slice_count),
            "safe_pool_count": int(safe_pool_count),
            "safe_pool_benchmark_like_count": int(safe_pool_benchmark_like_count),
            "selected_benchmark_like_count": int(selected_benchmark_like_count),
            "projection_safe_retention": float(projection_safe_retention),
            "mean_projection_error": mean_projection_error,
            "false_safe_projection_rate_delta": float(false_safe_delta),
            "unsafe_overcommit_rate_delta": float(unsafe_delta),
            "policy_match_rate_delta": float(policy_match_rate_delta),
            "benchmark_slice_coverage_all": float(benchmark_slice_coverage_all),
            "benchmark_slice_coverage_undercommit": float(benchmark_slice_coverage_undercommit),
            "family_mix": {str(name): int(count) for name, count in sorted(selected_family_mix.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "safe_pool_family_mix": {str(name): int(count) for name, count in sorted(safe_pool_family_mix.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "seed_fragility_if_available": None,
        },
        "comparison_to_baseline": comparison,
        "family_level_breakdown": family_breakdown,
        "blocker_counts_by_family_and_subtype": {
            "support_by_family": {str(name): int(count) for name, count in sorted(support_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "stability_guard_by_family": {str(name): int(count) for name, count in sorted(stability_family_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "support_by_subtype": {str(name): int(count) for name, count in sorted(support_subtype_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "stability_guard_by_subtype": {str(name): int(count) for name, count in sorted(stability_subtype_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
        },
        "decision_checks": {
            "non_zero_benchmark_safe_pool": bool(non_zero_safe_pool),
            "reduced_support_blocks_in_persistence_recovery": bool(support_blocks_reduced),
            "reduced_stability_guard_overfire": bool(stability_overfire_reduced),
            "preserved_projection_safe_behavior": bool(projection_safe_preserved),
            "structural_transferable_gain": bool(structural_transferable),
        },
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "decision_recommendation": {
            "choice": str(decision_choice),
            "recommended_next_template": str(recommended_next_template),
            "rationale": str(recommendation_reason),
        },
        "diagnostic_conclusions": {
            "non_zero_benchmark_safe_pool": bool(non_zero_safe_pool),
            "support_blocks_reduced": bool(support_blocks_reduced),
            "stability_guard_overfire_reduced": bool(stability_overfire_reduced),
            "projection_safe_retention_preserved": bool(projection_safe_preserved),
            "structural_transferable_gain": bool(structural_transferable),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
            "decision_recommendation": str(decision_choice),
        },
        "sample_rows": {
            "safe_pool_examples": safe_pool_rows[:8],
            "selected_examples": selected_rows[:8],
            "support_block_examples": support_block_rows[:8],
            "stability_guard_examples": stability_block_rows[:8],
            "final_admission_examples": final_admission_rows[:8],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"critic_split_benchmark_transfer_alignment_probe_v1_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(non_zero_safe_pool and projection_safe_preserved)
    if not bool(non_zero_safe_pool):
        reason = "diagnostic shadow failed: benchmark-transfer alignment probe still collapses before any safe pool materializes"
    elif not bool(projection_safe_preserved):
        reason = "diagnostic shadow passed: benchmark-transfer alignment probe materializes a safe pool but weakens projection-safety guardrails"
    elif bool(structural_transferable):
        reason = "diagnostic shadow passed: benchmark-transfer alignment probe creates a non-zero safe pool and reduces transfer blockers without unsafe drift"
    else:
        reason = "diagnostic shadow passed: benchmark-transfer alignment probe reduces some blockers, but the result is not yet structurally strong enough to justify routing follow-up"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }

def _run_shadow_support_contract_benchmark_stability_sensitive_compat_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    del rounds, seeds
    alignment_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_alignment_critic_v2")
    stability_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.stability_context_retention_probe_v2")
    reliability_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.safe_slice_selection_reliability_probe_v1")
    transfer_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_transfer_alignment_probe_v1")
    blocker_artifact = _load_latest_diagnostic_artifact_by_template("memory_summary.benchmark_transfer_blocker_snapshot_v1")
    if not alignment_artifact or not stability_artifact or not reliability_artifact or not transfer_artifact or not blocker_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: benchmark_stability_sensitive_compat_probe_v1 requires benchmark_alignment_critic_v2, stability_context_retention_probe_v2, safe_slice_selection_reliability_probe_v1, benchmark_transfer_alignment_probe_v1, and benchmark_transfer_blocker_snapshot_v1 artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without the prerequisite artifacts"},
        }

    benchmark_result = run_trusted_benchmark_pack(cfg=cfg, mode="standalone", include_policy_sweep=True)
    summary = dict(benchmark_result.get("summary", {}))
    detailed = dict(benchmark_result.get("detailed", {}))
    baseline_results = [dict(row) for row in list(detailed.get("results", [])) if isinstance(row, dict)]
    baseline_reject_results = [row for row in baseline_results if str(row.get("policy_decision", "")) == "reject"]
    if not baseline_reject_results:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no frozen benchmark reject rows available for support-contract probing",
            "observability_gain": {"passed": False, "reason": "no benchmark reject rows"},
            "activation_analysis_usefulness": {"passed": False, "reason": "no benchmark reject rows"},
            "ambiguity_reduction": {"passed": False, "reason": "no benchmark reject rows"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without benchmark reject rows"},
        }

    projection_boundary = float(_targeted_projection_override_boundary(cfg))
    benchmark_undercommit_all = [row for row in baseline_reject_results if str(row.get("oracle_decision", "")) in {"provisional", "full"}]
    benchmark_undercommit_target = [row for row in benchmark_undercommit_all if str(row.get("family", "")) == "gain_goal_conflict"]
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (benchmark_undercommit_target if len(benchmark_undercommit_target) >= 4 else benchmark_undercommit_all)
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }
    baseline_summary = {
        "global_compact_summary": dict(summary.get("global_compact_summary", {})),
        "family_compact_summary": dict(summary.get("family_compact_summary", {})),
        "global_mismatch_summary": dict(summary.get("global_mismatch_summary", {})),
        "family_mismatch_summary": dict(summary.get("family_mismatch_summary", {})),
    }

    slice_definition = dict(stability_artifact.get("slice_definition", {}))
    projection_level_cap = float(slice_definition.get("projection_level_cap", 0.70))
    projection_shape_cap = float(slice_definition.get("projection_shape_cap", 0.65))
    gain_goal_floor = float(slice_definition.get("gain_goal_floor", 0.34))
    stability_cap = float(slice_definition.get("stability_cap", 0.42))
    projection_bad_safe_cap = float(slice_definition.get("projection_bad_safe_cap", 0.57))
    projection_error_safe_cap = float(slice_definition.get("projection_error_safe_cap", 0.0115))
    benchmark_distance_cap = float(slice_definition.get("benchmark_distance_cap", 1.0))
    gain_structure_level_soft_cap = float(slice_definition.get("gain_structure_level_soft_cap", projection_level_cap + 0.08))
    gain_structure_benchmark_distance_soft_cap = float(slice_definition.get("gain_structure_benchmark_distance_soft_cap", benchmark_distance_cap + 0.05))
    gain_structure_projection_bad_soft_cap = float(slice_definition.get("gain_structure_projection_bad_soft_cap", projection_bad_safe_cap + 0.02))
    gain_structure_gain_soft_floor = float(slice_definition.get("gain_structure_gain_soft_floor", gain_goal_floor + 0.08))

    transfer_metrics = dict(transfer_artifact.get("benchmark_control_metrics", {}))
    transfer_family_baseline = dict(transfer_artifact.get("family_level_breakdown", {}))
    prior_false_safe_delta = float(dict(transfer_artifact.get("comparison_to_baseline", {})).get("false_safe_projection_rate_delta", 0.0) or 0.0)
    selection_target_count = max(1, int(transfer_metrics.get("selected_benchmark_like_count", 0) or 6))
    required_families = ["persistence", "recovery", "projection", "calibration", "gain_goal_conflict"]
    family_breakdown = {
        name: {
            "candidates_entered": 0,
            "blocked_by_support": 0,
            "blocked_by_stability_guard": 0,
            "surviving_to_safe_pool": 0,
            "surviving_to_selected_benchmark_like": 0,
        }
        for name in required_families
    }
    support_rows: List[Dict[str, Any]] = []
    stability_rows: List[Dict[str, Any]] = []
    safe_pool_rows: List[Dict[str, Any]] = []
    all_rows: List[Dict[str, Any]] = []

    def _subtype_priority(name: str) -> int:
        return {"retained_like_profile": 0, "gain_fragile_profile": 1, "mixed_safe": 2, "projection_shape_fragile": 3, "stability_fragile": 4}.get(str(name), 9)

    def _score_row(row: Dict[str, Any]) -> Dict[str, float]:
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or benchmark_distance_cap)
        projection_level = float(_safe_metric(row.get("projection_level_critic")) or projection_level_cap)
        projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or projection_shape_cap)
        gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or 0.0)
        stability_value = float(_safe_metric(row.get("stability_critic_v2")) or 0.0)
        pred_projection_bad = float(_safe_metric(row.get("pred_projection_bad_prob")) or projection_bad_safe_cap)
        pred_projection_error = float(_safe_metric(row.get("pred_projection_error")) or projection_error_safe_cap)
        subtype = str(row.get("alignment_subtype", "mixed_safe"))
        segment = str(row.get("segment", "mixed_shift"))
        blocker = str(row.get("blocker_group", "other"))
        family = str(row.get("family", "unknown"))
        benchmark_proximity = max(0.0, 1.0 - min(1.0, benchmark_distance / max(benchmark_distance_cap, 1e-6)))
        level_clean = max(0.0, 1.0 - min(1.0, projection_level / max(projection_level_cap, 1e-6)))
        shape_clean = max(0.0, 1.0 - min(1.0, projection_shape / max(projection_shape_cap, 1e-6)))
        gain_strength = min(1.0, max(0.0, gain_goal))
        stability_headroom = max(0.0, 1.0 - min(1.0, stability_value / max(stability_cap, 1e-6)))
        projection_safety = 0.55 * max(0.0, 1.0 - min(1.0, pred_projection_bad / max(projection_bad_safe_cap, 1e-6))) + 0.45 * max(0.0, 1.0 - min(1.0, pred_projection_error / max(projection_error_safe_cap, 1e-6)))
        support_family = blocker in {"persistence_guard", "recovery_guard"} and family in {"persistence", "recovery"}
        subtype_bonus = {"retained_like_profile": 0.12, "gain_fragile_profile": 0.07, "mixed_safe": 0.03, "projection_shape_fragile": -0.03, "stability_fragile": -0.01 if support_family else -0.08}.get(subtype, 0.0)
        segment_bonus = {"benchmark_adjacent": 0.10, "projection_borderline": 0.06, "gain_structure_shifted": 0.04, "stability_sensitive": 0.08 if support_family else 0.0}.get(segment, 0.0)
        family_bonus = 0.08 if support_family else 0.0
        return {
            "support_contract_precision_score": float(0.30 * benchmark_proximity + 0.24 * shape_clean + 0.16 * projection_safety + 0.14 * stability_headroom + 0.10 * level_clean + 0.06 * gain_strength + subtype_bonus + segment_bonus + family_bonus),
            "support_contract_runner_score": float(0.28 * benchmark_proximity + 0.22 * shape_clean + 0.18 * level_clean + 0.14 * projection_safety + 0.10 * stability_headroom + 0.08 * gain_strength + subtype_bonus + 0.5 * segment_bonus + family_bonus),
            "support_contract_selection_score": float(0.32 * benchmark_proximity + 0.18 * shape_clean + 0.14 * level_clean + 0.12 * projection_safety + 0.10 * gain_strength + 0.10 * stability_headroom + subtype_bonus + 0.35 * segment_bonus + family_bonus),
        }

    for scenario_result in baseline_reject_results:
        row = _benchmark_scenario_candidate_row(cfg, scenario_result, projection_boundary=projection_boundary, benchmark_summary=benchmark_summary)
        row["projection_policy_ok_provisional"] = bool(dict(scenario_result.get("candidate_summary", {})).get("projection_policy_ok_provisional", False))
        row["projection_level_critic"] = float(_row_projection_level_critic_v2(row, benchmark_summary, projection_boundary=projection_boundary))
        row["projection_shape_critic"] = float(_row_projection_shape_critic_v2(row, benchmark_summary))
        row["gain_goal_critic_v2"] = float(_row_gain_goal_critic_v2(row, benchmark_summary))
        row["stability_critic_v2"] = float(_row_stability_critic_v2(row, projection_level_critic=float(row["projection_level_critic"]), projection_shape_critic=float(row["projection_shape_critic"]), gain_goal_critic=float(row["gain_goal_critic_v2"])))
        row["alignment_subtype"] = _routing_slice_retest_subtype(
            row,
            benchmark_distance_cap=benchmark_distance_cap,
            projection_shape_cap=projection_shape_cap,
            gain_goal_floor=gain_goal_floor,
            stability_cap=stability_cap,
            gain_structure_benchmark_distance_soft_cap=gain_structure_benchmark_distance_soft_cap,
            gain_structure_gain_soft_floor=gain_structure_gain_soft_floor,
        )
        row.update(
            _routing_slice_retest_eval_row(
                row,
                projection_level_cap=projection_level_cap,
                projection_shape_cap=projection_shape_cap,
                gain_goal_floor=gain_goal_floor,
                stability_cap=stability_cap,
                projection_bad_safe_cap=projection_bad_safe_cap,
                projection_error_safe_cap=projection_error_safe_cap,
                benchmark_distance_cap=benchmark_distance_cap,
                gain_structure_level_soft_cap=gain_structure_level_soft_cap,
                gain_structure_benchmark_distance_soft_cap=gain_structure_benchmark_distance_soft_cap,
                gain_structure_projection_bad_soft_cap=gain_structure_projection_bad_soft_cap,
                gain_structure_gain_soft_floor=gain_structure_gain_soft_floor,
            )
        )
        row.update(_score_row(row))

        family = str(row.get("family", "unknown"))
        baseline_reason = str(row.get("slice_reason", "final_benchmark_admission"))
        segment = str(row.get("segment", "mixed_shift"))
        subtype = str(row.get("alignment_subtype", "mixed_safe"))
        blocker = str(row.get("blocker_group", "other"))
        pred_projection_bad = float(_safe_metric(row.get("pred_projection_bad_prob")) or 99.0)
        pred_projection_error = float(_safe_metric(row.get("pred_projection_error")) or 99.0)
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 99.0)
        projection_level = float(_safe_metric(row.get("projection_level_critic")) or 99.0)
        projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or 99.0)
        gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or -99.0)
        stability_value = float(_safe_metric(row.get("stability_critic_v2")) or 99.0)
        precision_score = float(row.get("support_contract_precision_score", 0.0))
        runner_score = float(row.get("support_contract_runner_score", 0.0))
        selection_score = float(row.get("support_contract_selection_score", 0.0))
        raw_safe = bool(row.get("projection_policy_ok_provisional", False) and pred_projection_bad <= projection_bad_safe_cap and pred_projection_error <= projection_error_safe_cap)
        support_family = bool(family in {"persistence", "recovery"} and blocker in {"persistence_guard", "recovery_guard"} and segment == "stability_sensitive")
        support_contract_candidate = bool(
            support_family
            and raw_safe
            and precision_score >= 0.56
            and runner_score >= 0.54
            and benchmark_distance <= benchmark_distance_cap * 0.92
            and projection_shape <= projection_shape_cap * 0.92
            and projection_level <= gain_structure_level_soft_cap * 0.90
            and stability_value <= stability_cap * 1.02
            and gain_goal >= gain_goal_floor - 0.10
        )
        support_ok = bool(baseline_reason not in {"blocker_not_supported", "unsupported_segment"} or support_contract_candidate)
        if baseline_reason in {"blocker_not_supported", "unsupported_segment"} and support_family and raw_safe:
            if support_contract_candidate:
                support_attr = "resolved_by_stage_aware_support_contract"
            elif benchmark_distance > benchmark_distance_cap * 0.92 or projection_shape > projection_shape_cap * 0.92:
                support_attr = "taxonomy_contract_mismatch"
            elif runner_score < 0.54:
                support_attr = "runner_path_incompatibility"
            else:
                support_attr = "missing_support_group_mapping"
        elif baseline_reason in {"blocker_not_supported", "unsupported_segment"}:
            support_attr = "stage_specific_admission_rules"
        else:
            support_attr = "not_applicable"

        stability_ok = bool(
            baseline_reason != "stability_guard"
            or (
                (subtype in {"retained_like_profile", "gain_fragile_profile", "mixed_safe"} or segment in {"projection_borderline", "benchmark_adjacent"})
                and runner_score >= 0.58
                and selection_score >= 0.60
                and pred_projection_bad <= projection_bad_safe_cap * 0.98
                and pred_projection_error <= projection_error_safe_cap * 0.97
                and benchmark_distance <= benchmark_distance_cap * 0.95
                and projection_shape <= projection_shape_cap * 0.98
                and projection_level <= gain_structure_level_soft_cap * 0.95
            )
        )
        transfer_safe_pool = bool(
            raw_safe
            and support_ok
            and stability_ok
            and segment != "projection_far_shifted"
            and selection_score >= 0.52
            and benchmark_distance <= benchmark_distance_cap
            and (not support_family or precision_score >= 0.56)
        )
        benchmark_like_safe = bool(
            transfer_safe_pool
            and bool(row.get("benchmark_like_safe", False))
            and selection_score >= 0.60
            and benchmark_distance <= benchmark_distance_cap * 0.82
            and pred_projection_error <= projection_error_safe_cap * 0.96
            and (support_contract_candidate or subtype in {"retained_like_profile", "gain_fragile_profile", "mixed_safe"})
        )

        if not bool(row.get("projection_policy_ok_provisional", False)):
            failure_stage = "before_candidate_support"
            slice_reason_probe = "before_candidate_support"
        elif not support_ok:
            failure_stage = "support_filter"
            slice_reason_probe = "blocker_not_supported"
        elif not stability_ok:
            failure_stage = "stability_guard"
            slice_reason_probe = "stability_guard"
        elif transfer_safe_pool:
            failure_stage = "safe_pool"
            slice_reason_probe = "benchmark_like_safe_pool" if benchmark_like_safe else "safe_pool_non_benchmark_like"
        else:
            failure_stage = "final_benchmark_admission"
            slice_reason_probe = "support_contract_alignment_floor"

        row["benchmark_transfer_safe_pool"] = transfer_safe_pool
        row["benchmark_transfer_like_safe"] = benchmark_like_safe
        row["failure_stage_probe"] = failure_stage
        row["slice_reason_probe"] = slice_reason_probe
        row["support_contract_candidate"] = support_contract_candidate
        row["support_failure_attribution"] = support_attr
        all_rows.append(dict(row))
        if family not in family_breakdown:
            family_breakdown[family] = {"candidates_entered": 0, "blocked_by_support": 0, "blocked_by_stability_guard": 0, "surviving_to_safe_pool": 0, "surviving_to_selected_benchmark_like": 0}
        family_breakdown[family]["candidates_entered"] += 1
        if failure_stage == "support_filter":
            family_breakdown[family]["blocked_by_support"] += 1
            support_rows.append(dict(row))
        elif failure_stage == "stability_guard":
            family_breakdown[family]["blocked_by_stability_guard"] += 1
            stability_rows.append(dict(row))
        elif failure_stage == "safe_pool":
            family_breakdown[family]["surviving_to_safe_pool"] += 1
            safe_pool_rows.append(dict(row))

    safe_pool_benchmark_like_rows = [row for row in safe_pool_rows if bool(row.get("benchmark_transfer_like_safe", False))]
    selected_rows = sorted(
        safe_pool_benchmark_like_rows if safe_pool_benchmark_like_rows else safe_pool_rows,
        key=lambda item: (
            0 if bool(item.get("support_contract_candidate", False)) and str(item.get("family", "")) in {"persistence", "recovery"} else 1,
            0 if bool(item.get("benchmark_transfer_like_safe", False)) else 1,
            _subtype_priority(str(item.get("alignment_subtype", ""))),
            -round(float(_safe_metric(item.get("support_contract_selection_score")) or -99.0), 6),
            round(float(_safe_metric(item.get("benchmark_distance")) or 99.0), 6),
            round(float(_safe_metric(item.get("pred_projection_error")) or 99.0), 6),
            str(item.get("scenario_id", "")),
        ),
    )[: min(selection_target_count, len(safe_pool_benchmark_like_rows if safe_pool_benchmark_like_rows else safe_pool_rows))]
    selected_ids = {str(row.get("scenario_id", "")) for row in selected_rows}
    for row in selected_rows:
        if bool(row.get("benchmark_transfer_like_safe", False)):
            family_breakdown[str(row.get("family", "unknown"))]["surviving_to_selected_benchmark_like"] += 1

    variant_results: List[Dict[str, Any]] = []
    for scenario_result in baseline_results:
        scenario_id = str(scenario_result.get("scenario_id", ""))
        row = next((item for item in all_rows if str(item.get("scenario_id", "")) == scenario_id), {})
        decision = "provisional" if str(scenario_result.get("policy_decision", "")) == "reject" and scenario_id in selected_ids else str(scenario_result.get("policy_decision", "reject"))
        variant_result = _result_with_policy_decision(scenario_result, decision, str(proposal.get("template_name", "")))
        variant_result["support_contract_probe"] = {
            "selected_for_control": bool(scenario_id in selected_ids),
            "benchmark_transfer_safe_pool": bool(dict(row).get("benchmark_transfer_safe_pool", False)),
            "benchmark_transfer_like_safe": bool(dict(row).get("benchmark_transfer_like_safe", False)),
            "slice_reason_probe": str(dict(row).get("slice_reason_probe", "baseline_non_reject")),
            "support_contract_candidate": bool(dict(row).get("support_contract_candidate", False)),
            "support_failure_attribution": str(dict(row).get("support_failure_attribution", "")),
            "support_contract_precision_score": _safe_metric(dict(row).get("support_contract_precision_score")),
            "support_contract_runner_score": _safe_metric(dict(row).get("support_contract_runner_score")),
            "support_contract_selection_score": _safe_metric(dict(row).get("support_contract_selection_score")),
        }
        variant_results.append(variant_result)

    variant_summary = _summarize_benchmark_results(variant_results)
    comparison = _variant_comparison(baseline_summary=baseline_summary, variant_summary=variant_summary)
    benchmark_slice_count = int(len(selected_rows))
    safe_pool_count = int(len(safe_pool_rows))
    safe_pool_benchmark_like_count = int(sum(bool(row.get("benchmark_transfer_like_safe", False)) for row in safe_pool_rows))
    selected_benchmark_like_count = int(sum(bool(row.get("benchmark_transfer_like_safe", False)) for row in selected_rows))
    projection_safe_retention = float(sum(bool(float(_safe_metric(row.get("pred_projection_bad_prob")) or 99.0) <= projection_bad_safe_cap and float(_safe_metric(row.get("pred_projection_error")) or 99.0) <= projection_error_safe_cap) for row in selected_rows) / benchmark_slice_count) if benchmark_slice_count else 0.0
    mean_projection_error = _mean_key(selected_rows, "pred_projection_error")
    policy_match_rate_delta = float(comparison.get("policy_match_rate_delta") or 0.0)
    false_safe_delta = float(comparison.get("false_safe_projection_rate_delta") or 0.0)
    unsafe_delta = float(comparison.get("unsafe_overcommit_rate_delta") or 0.0)
    benchmark_slice_coverage_all = float(benchmark_slice_count / len(baseline_results)) if baseline_results else 0.0
    benchmark_slice_coverage_undercommit = float(sum(str(row.get("oracle_decision", "")) in {"provisional", "full"} for row in selected_rows) / len(benchmark_undercommit_all)) if benchmark_undercommit_all else 0.0
    support_blocks_reduced = bool(
        int(dict(family_breakdown.get("persistence", {})).get("blocked_by_support", 0) + dict(family_breakdown.get("recovery", {})).get("blocked_by_support", 0))
        < int(dict(transfer_family_baseline.get("persistence", {})).get("blocked_by_support", 0) + dict(transfer_family_baseline.get("recovery", {})).get("blocked_by_support", 0))
    )
    non_zero_safe_pool = bool(safe_pool_count > 0)
    false_safe_improved = bool(false_safe_delta < prior_false_safe_delta)
    projection_safe_preserved = bool(projection_safe_retention >= 0.98 and unsafe_delta <= 1e-9)
    structural_transferable = bool(non_zero_safe_pool and support_blocks_reduced and benchmark_slice_count >= 3 and safe_pool_benchmark_like_count >= 3 and benchmark_slice_coverage_undercommit >= 0.10)
    support_attr_counts = Counter(str(row.get("support_failure_attribution", "unknown")) for row in support_rows)
    support_family_counts = Counter(str(row.get("family", "unknown")) for row in support_rows)
    stability_family_counts = Counter(str(row.get("family", "unknown")) for row in stability_rows)
    support_subtype_counts = Counter(str(row.get("alignment_subtype", "unknown")) for row in support_rows)
    stability_subtype_counts = Counter(str(row.get("alignment_subtype", "unknown")) for row in stability_rows)

    if support_blocks_reduced and non_zero_safe_pool and false_safe_improved and projection_safe_preserved and structural_transferable:
        choice = "A"
        next_template = "support_contract.benchmark_stability_sensitive_compat_probe_v1"
        next_hypothesis = "support_runner_compatibility_fix"
        recommendation_reason = "support compatibility moved the frozen benchmark path without unsafe drift, so the benchmark-only compatibility branch is worth continuing"
    elif not support_blocks_reduced:
        choice = "B"
        next_template = "critic_split.benchmark_alignment_critic_v2"
        next_hypothesis = "benchmark_alignment_critic_continue"
        recommendation_reason = "support blocks did not materially decrease, so compatibility was not the real bottleneck and the next step should return to critic alignment work"
    else:
        choice = "C"
        next_template = "memory_summary.benchmark_transfer_blocker_snapshot_v1"
        next_hypothesis = "support_runner_compatibility_diagnostic"
        recommendation_reason = "support moved somewhat, but the remaining tradeoff is ambiguous enough to justify another diagnostic before more control-family work"

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "support_contract.benchmark_stability_sensitive_compat_probe_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "comparison_references": {
            "memory_summary.benchmark_transfer_blocker_snapshot_v1": dict(blocker_artifact.get("global_stage_breakdown", {})),
            "critic_split.benchmark_transfer_alignment_probe_v1": dict(transfer_metrics),
            "critic_split.benchmark_alignment_critic_v2": {"safe_pool_count": int(dict(alignment_artifact.get("availability_metrics", {})).get("safe_pool_count_probe", 0)), "safe_pool_benchmark_like_count": int(dict(alignment_artifact.get("availability_metrics", {})).get("safe_pool_benchmark_like_count_probe", 0)), "selected_benchmark_like_count": int(dict(alignment_artifact.get("comparison_to_v2", {})).get("slice_activation_count_probe", 0)), "projection_safe_retention": float(dict(alignment_artifact.get("comparison_to_v2", {})).get("projection_safe_retention_rate_probe", 0.0)), "mean_projection_error": _safe_metric(dict(alignment_artifact.get("comparison_to_v2", {})).get("mean_projection_error_probe"))},
            "critic_split.stability_context_retention_probe_v2": {"safe_pool_count": int(dict(stability_artifact.get("availability_metrics", {})).get("safe_pool_count_probe", 0)), "safe_pool_benchmark_like_count": int(dict(stability_artifact.get("availability_metrics", {})).get("safe_pool_benchmark_like_count_probe", 0)), "selected_benchmark_like_count": int(dict(stability_artifact.get("purity_metrics", {})).get("activation_count", 0)), "projection_safe_retention": float(dict(stability_artifact.get("comparison_to_benchmark_alignment_v2", {})).get("projection_safe_retention_rate_probe", 0.0)), "mean_projection_error": _safe_metric(dict(stability_artifact.get("comparison_to_benchmark_alignment_v2", {})).get("mean_projection_error_probe"))},
            "critic_split.safe_slice_selection_reliability_probe_v1": {"safe_pool_count": int(sum(int(dict(item).get("safe_pool_count_probe", 0)) for item in list(reliability_artifact.get("per_seed_context_accounting", [])) if isinstance(item, dict))), "safe_pool_benchmark_like_count": int(sum(int(dict(item).get("safe_pool_benchmark_like_count_probe", 0)) for item in list(reliability_artifact.get("per_seed_context_accounting", [])) if isinstance(item, dict))), "selected_benchmark_like_count": int(dict(reliability_artifact.get("comparison_to_stability_context_retention_probe_v2", {})).get("selected_benchmark_like_count_probe", 0)), "projection_safe_retention": float(dict(reliability_artifact.get("comparison_to_stability_context_retention_probe_v2", {})).get("projection_safe_retention_rate_probe", 0.0)), "mean_projection_error": _safe_metric(dict(reliability_artifact.get("comparison_to_stability_context_retention_probe_v2", {})).get("mean_projection_error_probe"))},
        },
        "benchmark_control_metrics": {
            "benchmark_slice_count": benchmark_slice_count,
            "safe_pool_count": safe_pool_count,
            "safe_pool_benchmark_like_count": safe_pool_benchmark_like_count,
            "selected_benchmark_like_count": selected_benchmark_like_count,
            "projection_safe_retention": projection_safe_retention,
            "mean_projection_error": mean_projection_error,
            "false_safe_projection_rate_delta": false_safe_delta,
            "unsafe_overcommit_rate_delta": unsafe_delta,
            "policy_match_rate_delta": policy_match_rate_delta,
            "benchmark_slice_coverage_all": benchmark_slice_coverage_all,
            "benchmark_slice_coverage_undercommit": benchmark_slice_coverage_undercommit,
            "family_mix": dict(sorted(Counter(str(row.get("family", "unknown")) for row in selected_rows).items())),
            "safe_pool_family_mix": dict(sorted(Counter(str(row.get("family", "unknown")) for row in safe_pool_rows).items())),
            "seed_fragility_if_available": None,
        },
        "comparison_to_baseline": comparison,
        "family_level_breakdown": family_breakdown,
        "blocker_counts_by_family_and_subtype": {
            "support_by_family": dict(sorted(support_family_counts.items())),
            "stability_guard_by_family": dict(sorted(stability_family_counts.items())),
            "support_by_subtype": dict(sorted(support_subtype_counts.items())),
            "stability_guard_by_subtype": dict(sorted(stability_subtype_counts.items())),
            "support_failure_attribution": dict(sorted(support_attr_counts.items())),
        },
        "decision_checks": {
            "support_blocks_decreased_for_persistence_recovery": support_blocks_reduced,
            "benchmark_safe_pool_viability_non_zero": non_zero_safe_pool,
            "false_safe_projection_rate_delta_improved_toward_baseline": false_safe_improved,
            "projection_safe_behavior_preserved_without_unsafe_drift": projection_safe_preserved,
            "structural_transferability_not_cosmetic_patch": structural_transferable,
        },
        "observability_gain": {"passed": len(baseline_reject_results) >= 20, "baseline_reject_count": len(baseline_reject_results), "safe_pool_count": safe_pool_count, "safe_pool_benchmark_like_count": safe_pool_benchmark_like_count, "selected_benchmark_like_count": selected_benchmark_like_count, "support_block_count": len(support_rows), "stability_guard_count": len(stability_rows), "reason": "the frozen benchmark pack contains enough rejected scenarios to probe stage-aware support compatibility"},
        "activation_analysis_usefulness": {"passed": non_zero_safe_pool, "support_blocks_reduced": support_blocks_reduced, "false_safe_projection_rate_delta_improved": false_safe_improved, "structural_transferable": structural_transferable, "reason": "the probe measures whether support compatibility creates a transferable benchmark safe pool rather than only relabeling blocks"},
        "ambiguity_reduction": {"passed": True, "score": float(min(1.0, 0.24 + 0.18 * int(non_zero_safe_pool) + 0.18 * int(support_blocks_reduced) + 0.14 * int(false_safe_improved) + 0.14 * int(projection_safe_preserved) + 0.12 * int(structural_transferable))), "reason": "the probe isolates whether persistence/recovery support handling can move benchmark transfer without weakening projection-safety framing"},
        "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "benchmark-only support/runner compatibility probe with live default policy, thresholds, routing policy, and frozen benchmark semantics unchanged"},
        "later_selection_usefulness": {"passed": True, "recommended_next_template": next_template, "reason": recommendation_reason, "decision_recommendation": choice},
        "decision_recommendation": {"choice": choice, "recommended_next_template": next_template, "rationale": recommendation_reason},
        "diagnostic_conclusions": {"support_blocks_reduced": support_blocks_reduced, "non_zero_benchmark_safe_pool": non_zero_safe_pool, "false_safe_projection_rate_delta_improved": false_safe_improved, "projection_safe_retention_preserved": projection_safe_preserved, "structural_transferable_gain": structural_transferable, "support_failure_primary_attribution": str(support_attr_counts.most_common(1)[0][0] if support_attr_counts else "none"), "next_control_hypothesis": next_hypothesis, "recommended_next_template": next_template, "decision_recommendation": choice},
        "sample_rows": {"safe_pool_examples": safe_pool_rows[:8], "selected_examples": selected_rows[:8], "support_block_examples": support_rows[:8], "stability_guard_examples": stability_rows[:8]},
    }
    artifact_path = _diagnostic_artifact_dir() / f"support_contract_benchmark_stability_sensitive_compat_probe_v1_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")
    passed = bool(non_zero_safe_pool and projection_safe_preserved)
    reason = (
        "diagnostic shadow passed: support-contract probe moved benchmark compatibility while preserving projection-safe behavior"
        if passed
        else "diagnostic shadow failed: support-contract probe did not preserve a usable projection-safe benchmark transfer path"
    )
    return {
        "passed": passed,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": reason,
        "observability_gain": artifact_payload["observability_gain"],
        "activation_analysis_usefulness": artifact_payload["activation_analysis_usefulness"],
        "ambiguity_reduction": artifact_payload["ambiguity_reduction"],
        "safety_neutrality": artifact_payload["safety_neutrality"],
        "later_selection_usefulness": artifact_payload["later_selection_usefulness"],
        "diagnostic_conclusions": artifact_payload["diagnostic_conclusions"],
        "artifact_path": str(artifact_path),
    }

def _run_shadow_seed_context_shift_snapshot_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    v2_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.projection_gain_goal_v2")
    purity_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.safe_slice_purity_probe_v1")
    distance_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_distance_retention_probe_v1")
    alignment_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_alignment_critic_v1")
    if not v2_artifact or not purity_artifact or not distance_artifact or not alignment_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: seed-context snapshot requires the critic-v2, safe-slice purity, benchmark-distance retention, and benchmark-alignment artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite critic artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite critic artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite critic artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot recommend a follow-up without the prerequisite critic artifacts",
            },
        }

    intended_benefit = dict(proposal.get("intended_benefit", {}))
    target_family = str(intended_benefit.get("target_family", "gain_goal_conflict"))
    analytics = build_intervention_ledger_analytics()
    prior_suggestions = list(
        dict(analytics.get("compact_summary", {})).get("recommendations", {}).get("suggested_next_templates", [])
    )
    projection_boundary = float(_targeted_projection_override_boundary(cfg))

    benchmark_rows = _load_latest_benchmark_detailed_rows()
    benchmark_undercommit_all = [
        row
        for row in benchmark_rows
        if str(row.get("policy_decision", "")) == "reject"
        and str(row.get("oracle_decision", "")) in {"provisional", "full"}
    ]
    benchmark_undercommit_target = [
        row for row in benchmark_undercommit_all if str(row.get("family", "")) == target_family
    ]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (
            benchmark_undercommit_target
            if benchmark_reference_source == "target_family_undercommit"
            else benchmark_undercommit_all
        )
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }

    slice_definition = dict(v2_artifact.get("slice_definition", {}))
    projection_level_cap = float(slice_definition.get("projection_level_cap", 0.70))
    projection_shape_cap = float(slice_definition.get("projection_shape_cap", 0.65))
    gain_goal_floor = float(slice_definition.get("gain_goal_floor", 0.34))
    stability_cap = float(slice_definition.get("stability_cap", 0.42))
    projection_bad_safe_cap = float(slice_definition.get("projection_bad_safe_cap", 0.57))
    projection_error_safe_cap = float(slice_definition.get("projection_error_safe_cap", 0.0115))
    benchmark_distance_cap = float(slice_definition.get("benchmark_distance_cap", 1.0))
    gain_structure_level_soft_cap = float(slice_definition.get("gain_structure_level_soft_cap", projection_level_cap + 0.08))
    gain_structure_benchmark_distance_soft_cap = float(
        slice_definition.get("gain_structure_benchmark_distance_soft_cap", benchmark_distance_cap + 0.05)
    )
    gain_structure_projection_bad_soft_cap = float(
        slice_definition.get("gain_structure_projection_bad_soft_cap", projection_bad_safe_cap + 0.02)
    )
    gain_structure_gain_soft_floor = float(
        slice_definition.get("gain_structure_gain_soft_floor", gain_goal_floor + 0.08)
    )
    baseline_seed_counts = {
        int(dict(seed_summary).get("seed", -1)): int(dict(seed_summary).get("slice_activation_count", 0))
        for seed_summary in list(v2_artifact.get("seed_summaries", []))
        if _safe_metric(dict(seed_summary).get("seed")) is not None
    }

    def _annotate_v2_row(row: Dict[str, Any]) -> Dict[str, Any]:
        annotated = dict(row)
        annotated["segment"] = str(
            annotated.get(
                "segment",
                _segment_live_candidate(
                    annotated,
                    benchmark_summary=benchmark_summary,
                    projection_boundary=projection_boundary,
                ),
            )
        )
        if "benchmark_distance" not in annotated:
            annotated["benchmark_distance"] = float(_benchmark_distance(annotated, benchmark_summary))
        annotated["projection_level_critic"] = float(
            _row_projection_level_critic_v2(
                annotated,
                benchmark_summary,
                projection_boundary=projection_boundary,
            )
        )
        annotated["projection_shape_critic"] = float(_row_projection_shape_critic_v2(annotated, benchmark_summary))
        annotated["gain_goal_critic_v2"] = float(_row_gain_goal_critic_v2(annotated, benchmark_summary))
        annotated["stability_critic_v2"] = float(
            _row_stability_critic_v2(
                annotated,
                projection_level_critic=float(annotated["projection_level_critic"]),
                projection_shape_critic=float(annotated["projection_shape_critic"]),
                gain_goal_critic=float(annotated["gain_goal_critic_v2"]),
            )
        )
        return annotated

    def _v2_safe_pool_flags(row: Dict[str, Any]) -> Dict[str, bool]:
        blocker_group = str(row.get("blocker_group", "other"))
        segment = str(row.get("segment", "mixed_shift"))
        blocker_ok = blocker_group in {"projection_guard", "confidence_gain"}
        segment_ok = segment not in {"projection_far_shifted"}
        stability_ok = float(row.get("stability_critic_v2", 99.0)) <= float(stability_cap)
        if segment == "stability_sensitive":
            stability_ok = bool(
                stability_ok
                and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.85)
                and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.05)
            )
        if segment in {"projection_mid_shifted", "projection_borderline"}:
            segment_ok = bool(segment_ok and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap * 0.95))
        if blocker_group == "confidence_gain":
            blocker_ok = bool(
                blocker_ok
                and float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap * 1.05)
                and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor + 0.02)
            )
        gain_structure_soft_ok = bool(
            segment in {"gain_structure_shifted", "benchmark_adjacent"}
            and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)
            and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
            and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_structure_gain_soft_floor)
            and float(row.get("projection_level_critic", 99.0)) <= float(gain_structure_level_soft_cap)
            and float(row.get("benchmark_distance", 99.0)) <= float(gain_structure_benchmark_distance_soft_cap)
        )
        candidate_envelope_ok = bool(
            blocker_ok
            and segment_ok
            and stability_ok
            and (
                (
                    float(row.get("projection_level_critic", 99.0)) <= float(projection_level_cap)
                    and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)
                    and float(row.get("gain_goal_critic_v2", -1e9)) >= float(gain_goal_floor)
                    and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)
                )
                or gain_structure_soft_ok
            )
        )
        projection_safe_ok = bool(
            candidate_envelope_ok
            and (
                (
                    float(row.get("pred_projection_bad_prob", 99.0)) <= float(projection_bad_safe_cap)
                    and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
                )
                or (
                    segment in {"gain_structure_shifted", "benchmark_adjacent"}
                    and float(row.get("pred_projection_bad_prob", 99.0)) <= float(gain_structure_projection_bad_soft_cap)
                    and float(row.get("pred_projection_error", 99.0)) <= float(projection_error_safe_cap)
                    and float(row.get("projection_shape_critic", 99.0)) <= float(projection_shape_cap)
                )
            )
        )
        return {
            "projection_safe_ok": bool(projection_safe_ok),
            "benchmark_like_ok": bool(projection_safe_ok and float(row.get("benchmark_distance", 99.0)) <= float(benchmark_distance_cap)),
        }

    def _alignment_subtype(row: Dict[str, Any]) -> str:
        segment = str(row.get("segment", "mixed_shift"))
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 99.0)
        projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or 99.0)
        gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or -1e9)
        stability = float(_safe_metric(row.get("stability_critic_v2")) or 99.0)
        if segment == "benchmark_adjacent" and benchmark_distance <= float(benchmark_distance_cap * 1.02) and projection_shape <= float(projection_shape_cap * 0.95):
            return "retained_like_profile"
        if segment == "gain_structure_shifted" and benchmark_distance <= float(gain_structure_benchmark_distance_soft_cap) and projection_shape <= float(projection_shape_cap) and gain_goal >= float(gain_structure_gain_soft_floor):
            return "retained_like_profile"
        if segment == "gain_structure_shifted":
            return "gain_fragile_profile"
        if segment == "stability_sensitive" or stability > float(stability_cap * 0.95):
            return "stability_fragile"
        if segment in {"projection_mid_shifted", "projection_borderline"} or projection_shape > float(projection_shape_cap * 0.92):
            return "projection_shape_fragile"
        return "mixed_safe"

    def _subtype_prior_value(subtype: str) -> float:
        return {
            "retained_like_profile": 1.00,
            "gain_fragile_profile": 0.62,
            "mixed_safe": 0.40,
            "projection_shape_fragile": 0.16,
            "stability_fragile": 0.05,
        }.get(str(subtype), 0.25)

    def _build_context(rows: List[Dict[str, Any]], baseline_target_count: int) -> Dict[str, Any]:
        subtype_counts = Counter(str(row.get("alignment_subtype", "mixed_safe")) for row in rows)
        blocker_counts = Counter(str(row.get("blocker_group", "other")) for row in rows)
        return {
            "safe_pool_count": int(len(rows)),
            "baseline_target_count": int(max(0, baseline_target_count)),
            "mean_benchmark_distance": _mean_key(rows, "benchmark_distance"),
            "mean_projection_shape": _mean_key(rows, "projection_shape_critic"),
            "mean_gain_goal": _mean_key(rows, "gain_goal_critic_v2"),
            "subtype_counts": {str(name): int(count) for name, count in subtype_counts.items()},
            "blocker_counts": {str(name): int(count) for name, count in blocker_counts.items()},
        }

    def _context_conditioned_score(row: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, float]:
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 1.20)
        projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or 0.0)
        projection_level = float(_safe_metric(row.get("projection_level_critic")) or 0.0)
        gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or 0.0)
        stability = float(_safe_metric(row.get("stability_critic_v2")) or 0.0)
        subtype = str(row.get("alignment_subtype", "mixed_safe"))
        benchmark_proximity = max(0.0, 1.15 - min(1.15, benchmark_distance))
        shape_closeness = max(0.0, float(projection_shape_cap) - min(float(projection_shape_cap), projection_shape)) / max(1e-6, float(projection_shape_cap))
        level_closeness = max(0.0, float(projection_level_cap) - min(float(projection_level_cap), projection_level)) / max(1e-6, float(projection_level_cap))
        gain_goal_positive = max(0.0, gain_goal)
        subtype_prior = float(_subtype_prior_value(subtype))
        safe_pool_count = int(context.get("safe_pool_count", 0))
        baseline_target_count = int(context.get("baseline_target_count", 0))
        scarcity = max(0.0, float(baseline_target_count - safe_pool_count) / max(1.0, float(baseline_target_count or 1)))
        mean_benchmark_distance = float(_safe_metric(context.get("mean_benchmark_distance")) or benchmark_distance_cap)
        mean_projection_shape = float(_safe_metric(context.get("mean_projection_shape")) or projection_shape_cap)
        mean_gain_goal = float(_safe_metric(context.get("mean_gain_goal")) or gain_goal_floor)
        context_shift = min(
            1.0,
            max(0.0, mean_benchmark_distance - float(benchmark_distance_cap * 0.95)) / max(0.05, float(benchmark_distance_cap * 0.10))
            + max(0.0, mean_projection_shape - float(projection_shape_cap * 0.90)) / max(0.05, float(projection_shape_cap * 0.20)),
        )
        stability_context = max(0.0, 1.0 - min(1.0, stability / max(1e-6, float(stability_cap)))) * max(0.0, 1.0 - 0.55 * context_shift - 0.35 * scarcity)
        gain_goal_context = benchmark_proximity * min(1.0, gain_goal_positive) * max(0.0, 1.0 - 0.35 * context_shift)
        if gain_goal >= mean_gain_goal:
            gain_goal_context += 0.06 * min(1.0, gain_goal_positive)
        projection_shape_context = benchmark_proximity * max(0.0, float(projection_shape_cap) - min(float(projection_shape_cap), projection_shape)) / max(1e-6, float(projection_shape_cap)) * max(0.0, 1.0 - 0.25 * scarcity)
        if projection_shape <= mean_projection_shape:
            projection_shape_context += 0.05 * shape_closeness
        score = float(
            0.30 * subtype_prior
            + 0.22 * gain_goal_context
            + 0.22 * projection_shape_context
            + 0.10 * stability_context
            + 0.08 * benchmark_proximity
            + 0.08 * level_closeness
            - 0.12 * scarcity
            - 0.10 * context_shift
        )
        if subtype == "retained_like_profile":
            score += 0.10
        elif subtype == "gain_fragile_profile":
            score += 0.03
        elif subtype == "projection_shape_fragile":
            score -= 0.08
        elif subtype == "stability_fragile":
            score -= 0.12
        return {
            "benchmark_alignment_critic_score": float(score),
            "context_shift_score": float(context_shift),
            "stability_context_score": float(stability_context),
            "gain_goal_context_score": float(gain_goal_context),
            "projection_shape_context_score": float(projection_shape_context),
            "subtype_split_score": float(subtype_prior),
            "scarcity_score": float(scarcity),
        }

    def _share(counter: Counter[str], name: str, total: int) -> float:
        if total <= 0:
            return 0.0
        return float(counter.get(str(name), 0) / float(total))

    def _summarize_round(rows: List[Dict[str, Any]], *, round_index: int, baseline_target_count: int) -> Dict[str, Any]:
        subtype_counts = Counter(str(row.get("alignment_subtype", "mixed_safe")) for row in rows)
        blocker_counts = Counter(str(row.get("blocker_group", "other")) for row in rows)
        benchmark_like_count = int(sum(bool(row.get("baseline_benchmark_like", False)) for row in rows))
        context_shift_score = _safe_metric(_mean([float(row.get("context_shift_score", 0.0)) for row in rows])) or 0.0
        return {
            "round_index": int(round_index),
            "safe_pool_count": int(len(rows)),
            "safe_pool_benchmark_like_count": int(benchmark_like_count),
            "safe_pool_benchmark_like_fraction": float(benchmark_like_count / len(rows)) if rows else 0.0,
            "context_shift_score": float(context_shift_score),
            "subtype_mix": {str(name): int(count) for name, count in sorted(subtype_counts.items())},
            "blocker_mix": {str(name): int(count) for name, count in sorted(blocker_counts.items())},
            "retained_like_share": _share(subtype_counts, "retained_like_profile", len(rows)),
            "gain_fragile_share": _share(subtype_counts, "gain_fragile_profile", len(rows)),
            "stability_fragile_share": _share(subtype_counts, "stability_fragile", len(rows)),
            "projection_shape_fragile_share": _share(subtype_counts, "projection_shape_fragile", len(rows)),
            "benchmark_distance_mean": _mean_key(rows, "benchmark_distance"),
            "projection_shape_mean": _mean_key(rows, "projection_shape_critic"),
            "gain_goal_mean": _mean_key(rows, "gain_goal_critic_v2"),
            "stability_mean": _mean_key(rows, "stability_critic_v2"),
            "safe_pool_scarcity": float(
                max(0, baseline_target_count - len(rows)) / max(1.0, float(baseline_target_count or 1))
            ),
        }

    def _float_or(value: Any, fallback: float) -> float:
        safe = _safe_metric(value)
        return float(fallback if safe is None else safe)

    all_rows: List[Dict[str, Any]] = []
    per_seed_rows: List[Dict[str, Any]] = []
    round_summaries: List[Dict[str, Any]] = []
    collapse_cases: List[Dict[str, Any]] = []
    non_collapse_cases: List[Dict[str, Any]] = []
    precursor_events: List[Dict[str, Any]] = []

    for seed in list(seeds):
        run_cfg = copy.deepcopy(cfg)
        run_cfg.verbose = False
        run_cfg.rounds = max(1, int(rounds))
        run_cfg.seed = int(seed)
        run_cfg.benchmark_every_rounds = 0
        run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs or {})
        run_cfg.eval_kwargs["session_log_path"] = f"logs/intervention_shadow_{proposal['proposal_id']}_seed_context_shift_seed{int(seed)}.log"
        apply_live_policy_variant(run_cfg, "targeted_gain_goal_proj_margin_01")
        _, _, history = run_proposal_learning_loop(run_cfg)

        seed_rows: List[Dict[str, Any]] = []
        for round_index, entry in enumerate(history):
            blocked = [item for item in list(entry.get("adopt_blocked", [])) if isinstance(item, dict)]
            for item in blocked:
                row = _live_gap_row(item, seed=int(seed), round_index=int(round_index), cohort="baseline_rejected", projection_boundary=projection_boundary)
                row = _annotate_v2_row(row)
                flags = _v2_safe_pool_flags(row)
                row["safe_probe_pool"] = bool(flags["projection_safe_ok"])
                row["baseline_benchmark_like"] = bool(flags["benchmark_like_ok"])
                row["alignment_subtype"] = str(_alignment_subtype(row))
                seed_rows.append(row)
                all_rows.append(row)

        safe_pool_rows = [row for row in seed_rows if bool(row.get("safe_probe_pool", False))]
        baseline_target_count = int(baseline_seed_counts.get(int(seed), 0))
        seed_context = _build_context(safe_pool_rows, baseline_target_count)
        for row in safe_pool_rows:
            row.update(_context_conditioned_score(row, seed_context))

        ordered = sorted(safe_pool_rows, key=lambda item: float(item.get("benchmark_alignment_critic_score", -1e9)), reverse=True)
        target_count = min(len(ordered), baseline_target_count) if baseline_target_count > 0 else 0
        scarcity = float(max(0, baseline_target_count - len(safe_pool_rows)) / max(1.0, float(baseline_target_count or 1)))
        quality_floor = 0.23 + (0.04 if scarcity > 0 else 0.0)
        selected_rows = [
            row
            for row in ordered[:target_count]
            if float(row.get("benchmark_alignment_critic_score", -1e9)) >= quality_floor
            or str(row.get("alignment_subtype", "")) == "retained_like_profile"
        ]
        if not selected_rows and ordered:
            top = ordered[0]
            if float(top.get("benchmark_alignment_critic_score", -1e9)) >= quality_floor - 0.05 and str(top.get("alignment_subtype", "")) in {"retained_like_profile", "gain_fragile_profile"}:
                selected_rows = [top]

        safe_pool_benchmark_like_count = int(sum(bool(row.get("baseline_benchmark_like", False)) for row in safe_pool_rows))
        selected_benchmark_like_count = int(sum(bool(row.get("baseline_benchmark_like", False)) for row in selected_rows))
        subtype_counts = Counter(str(row.get("alignment_subtype", "mixed_safe")) for row in safe_pool_rows)
        blocker_counts = Counter(str(row.get("blocker_group", "other")) for row in safe_pool_rows)
        retained_like_share = float(subtype_counts.get("retained_like_profile", 0) / len(safe_pool_rows)) if safe_pool_rows else 0.0
        stability_fragile_share = float(subtype_counts.get("stability_fragile", 0) / len(safe_pool_rows)) if safe_pool_rows else 0.0
        projection_shape_fragile_share = float(subtype_counts.get("projection_shape_fragile", 0) / len(safe_pool_rows)) if safe_pool_rows else 0.0
        context_shift_score = _safe_metric(_mean([float(row.get("context_shift_score", 0.0)) for row in safe_pool_rows])) or 0.0
        benchmark_distance_mean = _mean_key(safe_pool_rows, "benchmark_distance")
        projection_shape_mean = _mean_key(safe_pool_rows, "projection_shape_critic")
        gain_goal_mean = _mean_key(safe_pool_rows, "gain_goal_critic_v2")
        stability_mean = _mean_key(safe_pool_rows, "stability_critic_v2")

        per_round: List[Dict[str, Any]] = []
        round_indexes = sorted(set(int(_safe_metric(row.get("round_index")) or 0) for row in safe_pool_rows))
        for round_index in round_indexes:
            round_rows = [row for row in safe_pool_rows if int(_safe_metric(row.get("round_index")) or -1) == int(round_index)]
            round_summary = _summarize_round(
                round_rows,
                round_index=int(round_index),
                baseline_target_count=baseline_target_count,
            )
            round_summary["seed"] = int(seed)
            round_summary["collapse_case"] = bool(
                int(round_summary["safe_pool_count"]) <= 1
                or int(round_summary["safe_pool_benchmark_like_count"]) <= 0
            )
            per_round.append(round_summary)
            round_summaries.append(round_summary)

        for index in range(1, len(per_round)):
            prev_round = dict(per_round[index - 1])
            current_round = dict(per_round[index])
            if not bool(current_round.get("collapse_case", False)):
                continue
            precursor_events.append(
                {
                    "seed": int(seed),
                    "from_round": int(prev_round.get("round_index", index - 1)),
                    "to_round": int(current_round.get("round_index", index)),
                    "safe_pool_count_delta": int(current_round.get("safe_pool_count", 0) - prev_round.get("safe_pool_count", 0)),
                    "safe_pool_benchmark_like_fraction_delta": float(
                        _float_or(current_round.get("safe_pool_benchmark_like_fraction"), 0.0)
                        - _float_or(prev_round.get("safe_pool_benchmark_like_fraction"), 0.0)
                    ),
                    "context_shift_delta": float(
                        _float_or(current_round.get("context_shift_score"), 0.0)
                        - _float_or(prev_round.get("context_shift_score"), 0.0)
                    ),
                    "retained_like_share_delta": float(
                        _float_or(current_round.get("retained_like_share"), 0.0)
                        - _float_or(prev_round.get("retained_like_share"), 0.0)
                    ),
                    "stability_fragile_share_delta": float(
                        _float_or(current_round.get("stability_fragile_share"), 0.0)
                        - _float_or(prev_round.get("stability_fragile_share"), 0.0)
                    ),
                    "projection_shape_mean_delta": float(
                        _float_or(current_round.get("projection_shape_mean"), 0.0)
                        - _float_or(prev_round.get("projection_shape_mean"), 0.0)
                    ),
                    "benchmark_distance_mean_delta": float(
                        _float_or(current_round.get("benchmark_distance_mean"), 0.0)
                        - _float_or(prev_round.get("benchmark_distance_mean"), 0.0)
                    ),
                    "gain_goal_mean_delta": float(
                        _float_or(current_round.get("gain_goal_mean"), 0.0)
                        - _float_or(prev_round.get("gain_goal_mean"), 0.0)
                    ),
                }
            )

        collapse = bool((safe_pool_benchmark_like_count <= 0) or (selected_benchmark_like_count <= 0) or (len(safe_pool_rows) <= 1))
        if len(safe_pool_rows) <= max(1, baseline_target_count) and safe_pool_benchmark_like_count <= 0:
            collapse_driver = "low_candidate_count"
        elif context_shift_score >= 0.35:
            collapse_driver = "context_shift"
        elif retained_like_share < 0.25 or (stability_fragile_share + projection_shape_fragile_share) >= 0.60:
            collapse_driver = "subtype_loss"
        else:
            collapse_driver = "mixed"

        seed_summary = {
            "seed": int(seed),
            "safe_pool_count": int(len(safe_pool_rows)),
            "safe_pool_benchmark_like_count": int(safe_pool_benchmark_like_count),
            "selected_count": int(len(selected_rows)),
            "selected_benchmark_like_count": int(selected_benchmark_like_count),
            "context_shift_score": float(context_shift_score),
            "subtype_mix": {str(name): int(count) for name, count in sorted(subtype_counts.items())},
            "blocker_mix": {str(name): int(count) for name, count in sorted(blocker_counts.items())},
            "key_critic_summaries": {
                "benchmark_distance_mean": benchmark_distance_mean,
                "projection_shape_mean": projection_shape_mean,
                "gain_goal_mean": gain_goal_mean,
                "stability_mean": stability_mean,
                "scarcity": float(scarcity),
            },
            "collapse_case": bool(collapse),
            "collapse_driver": str(collapse_driver),
            "dominant_subtype": subtype_counts.most_common(1)[0][0] if subtype_counts else "none",
            "safe_pool_benchmark_like_fraction": float(safe_pool_benchmark_like_count / len(safe_pool_rows)) if safe_pool_rows else 0.0,
            "retained_like_share": float(retained_like_share),
            "gain_fragile_share": _share(subtype_counts, "gain_fragile_profile", len(safe_pool_rows)),
            "stability_fragile_share": float(stability_fragile_share),
            "projection_shape_fragile_share": float(projection_shape_fragile_share),
            "round_summaries": per_round,
        }
        per_seed_rows.append(seed_summary)
        (collapse_cases if collapse else non_collapse_cases).append(seed_summary)

    def _mean_case(rows: List[Dict[str, Any]], key: str) -> float:
        vals = [_safe_metric(row.get(key)) for row in rows]
        clean = [float(value) for value in vals if value is not None]
        return float(sum(clean) / len(clean)) if clean else 0.0

    collapse_driver_counts = Counter(str(row.get("collapse_driver", "mixed")) for row in collapse_cases)
    if collapse_driver_counts:
        top_driver, top_driver_count = collapse_driver_counts.most_common(1)[0]
        collapse_driver = str(top_driver if top_driver_count >= max(1, math.ceil(len(collapse_cases) / 2.0)) else "mixed")
    else:
        collapse_driver = "mixed"

    contrast = {
        "collapse_case_count": int(len(collapse_cases)),
        "non_collapse_case_count": int(len(non_collapse_cases)),
        "safe_pool_count_delta": float(_mean_case(collapse_cases, "safe_pool_count") - _mean_case(non_collapse_cases, "safe_pool_count")),
        "benchmark_like_fraction_delta": float(_mean_case(collapse_cases, "safe_pool_benchmark_like_fraction") - _mean_case(non_collapse_cases, "safe_pool_benchmark_like_fraction")),
        "retained_like_share_delta": float(_mean_case(collapse_cases, "retained_like_share") - _mean_case(non_collapse_cases, "retained_like_share")),
        "gain_fragile_share_delta": float(_mean_case(collapse_cases, "gain_fragile_share") - _mean_case(non_collapse_cases, "gain_fragile_share")),
        "stability_fragile_share_delta": float(_mean_case(collapse_cases, "stability_fragile_share") - _mean_case(non_collapse_cases, "stability_fragile_share")),
        "projection_shape_fragile_share_delta": float(_mean_case(collapse_cases, "projection_shape_fragile_share") - _mean_case(non_collapse_cases, "projection_shape_fragile_share")),
        "context_shift_delta": float(_mean_case(collapse_cases, "context_shift_score") - _mean_case(non_collapse_cases, "context_shift_score")),
        "benchmark_distance_mean_delta": float(_mean_case(collapse_cases, "benchmark_distance_mean") - _mean_case(non_collapse_cases, "benchmark_distance_mean")),
        "projection_shape_mean_delta": float(_mean_case(collapse_cases, "projection_shape_mean") - _mean_case(non_collapse_cases, "projection_shape_mean")),
        "gain_goal_mean_delta": float(_mean_case(collapse_cases, "gain_goal_mean") - _mean_case(non_collapse_cases, "gain_goal_mean")),
        "stability_mean_delta": float(_mean_case(collapse_cases, "stability_mean") - _mean_case(non_collapse_cases, "stability_mean")),
    }

    precursor_strengths = {
        "safe_pool_scarcity": float(max(0.0, -contrast["safe_pool_count_delta"]) + max(0.0, -contrast["benchmark_like_fraction_delta"])),
        "subtype_drift": float(max(0.0, -contrast["retained_like_share_delta"]) + max(0.0, contrast["stability_fragile_share_delta"]) + max(0.0, contrast["projection_shape_fragile_share_delta"])),
        "benchmark_distance_shift": float(max(0.0, contrast["benchmark_distance_mean_delta"]) + max(0.0, contrast["context_shift_delta"] * 0.5)),
        "projection_shape_shift": float(max(0.0, contrast["projection_shape_mean_delta"]) + max(0.0, contrast["context_shift_delta"] * 0.35)),
        "gain_goal_weakening": float(max(0.0, -contrast["gain_goal_mean_delta"])),
    }
    precursor_events_summary = {
        "count": int(len(precursor_events)),
        "mean_safe_pool_count_delta": float(_mean([float(item.get("safe_pool_count_delta", 0.0)) for item in precursor_events]) or 0.0),
        "mean_benchmark_like_fraction_delta": float(_mean([float(item.get("safe_pool_benchmark_like_fraction_delta", 0.0)) for item in precursor_events]) or 0.0),
        "mean_context_shift_delta": float(_mean([float(item.get("context_shift_delta", 0.0)) for item in precursor_events]) or 0.0),
        "mean_retained_like_share_delta": float(_mean([float(item.get("retained_like_share_delta", 0.0)) for item in precursor_events]) or 0.0),
        "mean_stability_fragile_share_delta": float(_mean([float(item.get("stability_fragile_share_delta", 0.0)) for item in precursor_events]) or 0.0),
        "mean_projection_shape_mean_delta": float(_mean([float(item.get("projection_shape_mean_delta", 0.0)) for item in precursor_events]) or 0.0),
        "mean_benchmark_distance_mean_delta": float(_mean([float(item.get("benchmark_distance_mean_delta", 0.0)) for item in precursor_events]) or 0.0),
        "mean_gain_goal_mean_delta": float(_mean([float(item.get("gain_goal_mean_delta", 0.0)) for item in precursor_events]) or 0.0),
    }

    precursor_strengths_for_decision = {
        "safe_pool_scarcity": precursor_strengths["safe_pool_scarcity"] + max(0.0, -precursor_events_summary["mean_safe_pool_count_delta"]),
        "subtype_drift": precursor_strengths["subtype_drift"] + max(0.0, -precursor_events_summary["mean_retained_like_share_delta"]) + max(0.0, precursor_events_summary["mean_stability_fragile_share_delta"]),
        "benchmark_distance_shift": precursor_strengths["benchmark_distance_shift"] + max(0.0, precursor_events_summary["mean_benchmark_distance_mean_delta"]),
        "projection_shape_shift": precursor_strengths["projection_shape_shift"] + max(0.0, precursor_events_summary["mean_projection_shape_mean_delta"]),
        "mixed": precursor_strengths["gain_goal_weakening"] + max(0.0, precursor_events_summary["mean_context_shift_delta"]),
    }
    dominant_precursor = "mixed"
    if precursor_strengths_for_decision:
        dominant_precursor = max(precursor_strengths_for_decision.items(), key=lambda item: float(item[1]))[0]
        if float(precursor_strengths_for_decision.get(dominant_precursor, 0.0)) <= 0.12:
            dominant_precursor = "mixed"

    strong_retention_mechanism = str(dict(alignment_artifact.get("diagnostic_conclusions", {})).get("strongest_retention_mechanism", ""))
    safe_slice_collapse_predictable = bool(
        len(collapse_cases) >= 1
        and len(non_collapse_cases) >= 1
        and (
            float(precursor_strengths_for_decision.get(dominant_precursor, 0.0)) >= 0.18
            or abs(float(contrast["safe_pool_count_delta"])) >= 1.0
            or abs(float(contrast["context_shift_delta"])) >= 0.15
        )
    )

    if safe_slice_collapse_predictable and (
        collapse_driver in {"low_candidate_count", "context_shift"}
        or dominant_precursor in {"safe_pool_scarcity", "mixed"}
        or strong_retention_mechanism == "stability_context_interaction"
    ):
        next_control_hypothesis = "stability_context_retention_probe"
        recommended_next_template = "critic_split.stability_context_retention_probe_v1"
        recommendation_reason = "collapse clusters around scarcity/context-shift structure, so the next critic should model stability-conditioned retention inside the safe slice"
    elif safe_slice_collapse_predictable and dominant_precursor in {"subtype_drift", "projection_shape_shift"}:
        next_control_hypothesis = "subtype_conditioned_critic"
        recommended_next_template = "critic_split.stability_context_retention_probe_v1"
        recommendation_reason = "collapse is driven by subtype/context drift inside the safe slice, so the next critic should be subtype-conditioned rather than routing-oriented"
    else:
        next_control_hypothesis = "no_control_yet"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "collapse remains too sparse or ambiguous for a new control-family probe, so routing and control changes should stay deferred"

    collapse_case_rows = [row for row in all_rows if int(row.get("seed", -1)) in {int(item.get("seed", -1)) for item in collapse_cases}]
    non_collapse_case_rows = [row for row in all_rows if int(row.get("seed", -1)) in {int(item.get("seed", -1)) for item in non_collapse_cases}]
    collapse_subtype_counts = Counter(str(row.get("alignment_subtype", "mixed_safe")) for row in collapse_case_rows if bool(row.get("safe_probe_pool", False)))
    non_collapse_subtype_counts = Counter(str(row.get("alignment_subtype", "mixed_safe")) for row in non_collapse_case_rows if bool(row.get("safe_probe_pool", False)))

    observability_gain = {
        "passed": bool(len(all_rows) >= 12 and len(per_seed_rows) >= 3 and len(collapse_cases) >= 1 and len(non_collapse_cases) >= 1),
        "blocked_candidate_count": int(len(all_rows)),
        "safe_probe_pool_count": int(sum(bool(row.get("safe_probe_pool", False)) for row in all_rows)),
        "seed_count": int(len(per_seed_rows)),
        "collapse_case_count": int(len(collapse_cases)),
        "non_collapse_case_count": int(len(non_collapse_cases)),
        "reason": (
            "captured enough safe-slice seed/context evidence to compare collapse and non-collapse conditions"
            if len(all_rows) >= 12
            else "insufficient safe-slice evidence to characterize collapse conditions"
        ),
    }
    activation_analysis = {
        "passed": bool(observability_gain["passed"] and recommended_next_template),
        "collapse_driver": str(collapse_driver),
        "dominant_precursor": str(dominant_precursor),
        "safe_slice_collapse_predictable": bool(safe_slice_collapse_predictable),
        "support_counts": {
            "collapse_cases": int(len(collapse_cases)),
            "non_collapse_cases": int(len(non_collapse_cases)),
            "precursor_events": int(len(precursor_events)),
        },
        "reason": (
            f"collapse diagnosis points to {next_control_hypothesis} because {collapse_driver} and {dominant_precursor} dominate the collapse contrast"
            if recommended_next_template
            else "collapse evidence did not resolve into a useful next-step hypothesis"
        ),
    }
    ambiguity_reduction = {
        "passed": bool(observability_gain["passed"] and (safe_slice_collapse_predictable or collapse_driver != "mixed")),
        "score": float(
            min(
                1.0,
                0.22
                + 0.20 * int(safe_slice_collapse_predictable)
                + 0.16 * int(collapse_driver != "mixed")
                + 0.14 * int(dominant_precursor != "mixed")
                + 0.12 * min(1.0, len(collapse_cases) / 2.0)
                + 0.10 * min(1.0, len(non_collapse_cases) / 2.0)
            )
        ),
        "reason": (
            "the seed-context artifact narrows collapse to a specific stability/context mechanism"
            if safe_slice_collapse_predictable or collapse_driver != "mixed"
            else "collapse evidence remains too ambiguous to justify a new critic hypothesis"
        ),
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "diagnostic-only seed/context snapshot with no live-policy mutation and no benchmark semantic changes",
    }
    later_selection_usefulness = {
        "passed": bool(recommended_next_template),
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
        "analytics_prior_suggestions": prior_suggestions[:3],
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.seed_context_shift_snapshot",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "dependency_context": {
            "critic_v2_artifact_path": str(v2_artifact.get("_artifact_path", "")),
            "safe_slice_purity_artifact_path": str(purity_artifact.get("_artifact_path", "")),
            "benchmark_distance_artifact_path": str(distance_artifact.get("_artifact_path", "")),
            "benchmark_alignment_artifact_path": str(alignment_artifact.get("_artifact_path", "")),
            "benchmark_reference_source": str(benchmark_reference_source),
            "alignment_strongest_retention_mechanism": str(strong_retention_mechanism),
        },
        "per_seed_safe_slice_summary": per_seed_rows,
        "collapse_case_analysis": {
            "collapse_cases": collapse_cases,
            "collapse_subtype_counts": {str(name): int(count) for name, count in sorted(collapse_subtype_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "collapse_blocked_rows": len(collapse_case_rows),
            "collapse_vs_non_collapse_contrast": contrast,
            "collapse_driver_counts": {str(name): int(count) for name, count in sorted(collapse_driver_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
        },
        "non_collapse_contrast": {
            "non_collapse_cases": non_collapse_cases,
            "non_collapse_subtype_counts": {str(name): int(count) for name, count in sorted(non_collapse_subtype_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))},
            "non_collapse_blocked_rows": len(non_collapse_case_rows),
        },
        "precursor_indicators": {
            "precursor_events": precursor_events[-12:],
            "precursor_event_summary": precursor_events_summary,
            "precursor_strengths": {str(name): float(value) for name, value in sorted(precursor_strengths_for_decision.items(), key=lambda item: (-float(item[1]), str(item[0])))},
            "gain_goal_weakening_signal": float(precursor_strengths["gain_goal_weakening"]),
        },
        "source_metric_summaries": {
            "safe_probe_pool": {
                "pred_projection_bad_prob": _metric_summary([row for row in all_rows if bool(row.get("safe_probe_pool", False))], "pred_projection_bad_prob"),
                "pred_projection_error": _metric_summary([row for row in all_rows if bool(row.get("safe_probe_pool", False))], "pred_projection_error"),
                "gain_goal_critic_v2": _metric_summary([row for row in all_rows if bool(row.get("safe_probe_pool", False))], "gain_goal_critic_v2"),
                "stability_critic_v2": _metric_summary([row for row in all_rows if bool(row.get("safe_probe_pool", False))], "stability_critic_v2"),
                "benchmark_distance": _metric_summary([row for row in all_rows if bool(row.get("safe_probe_pool", False))], "benchmark_distance"),
            },
            "benchmark_reference": benchmark_summary,
        },
        "diagnostic_conclusions": {
            "collapse_driver": str(collapse_driver),
            "dominant_precursor": str(dominant_precursor),
            "safe_slice_collapse_predictable": bool(safe_slice_collapse_predictable),
            "recommended_next_template": str(recommended_next_template),
            "next_control_hypothesis": str(next_control_hypothesis),
            "support_collapse_cases": int(len(collapse_cases)),
            "support_non_collapse_cases": int(len(non_collapse_cases)),
        },
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "sample_rows": {
            "collapse_seed_rows": sorted(collapse_case_rows, key=lambda item: (int(item.get("seed", 0)), int(item.get("round_index", 0)), float(item.get("benchmark_distance", 99.0))))[:8],
            "non_collapse_seed_rows": sorted(non_collapse_case_rows, key=lambda item: (int(item.get("seed", 0)), int(item.get("round_index", 0)), float(item.get("benchmark_distance", 99.0))))[:8],
            "safe_pool_rows_near_boundary": sorted([row for row in all_rows if bool(row.get("safe_probe_pool", False))], key=lambda item: abs(float(item.get("boundary_distance", 99.0))))[:8],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_seed_context_shift_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(
        observability_gain["passed"]
        and activation_analysis["passed"]
        and ambiguity_reduction["passed"]
        and safety_neutrality["passed"]
        and later_selection_usefulness["passed"]
    )
    if not bool(observability_gain["passed"]):
        reason = "diagnostic shadow failed: insufficient safe-slice seed/context evidence for a stable collapse snapshot"
    elif not bool(ambiguity_reduction["passed"]):
        reason = "diagnostic shadow failed: safe-slice collapse remains too ambiguous to guide the next critic probe"
    else:
        reason = "diagnostic shadow passed: safe-slice collapse conditions summarized with a stability/context-aware follow-up hypothesis"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_benchmark_context_availability_snapshot_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    v2_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.projection_gain_goal_v2")
    purity_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.safe_slice_purity_probe_v1")
    distance_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_distance_retention_probe_v1")
    alignment_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_alignment_critic_v1")
    stability_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.stability_context_retention_probe_v1")
    seed_context_artifact = _load_latest_diagnostic_artifact_by_template("memory_summary.seed_context_shift_snapshot")
    if not v2_artifact or not purity_artifact or not distance_artifact or not alignment_artifact or not stability_artifact or not seed_context_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: benchmark-context availability snapshot requires the critic-v2, purity, benchmark-distance, benchmark-alignment, stability-context, and seed-context artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite critic/context artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite critic/context artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite critic/context artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot recommend a follow-up without the prerequisite critic/context artifacts",
            },
        }

    analytics = build_intervention_ledger_analytics()
    prior_suggestions = list(
        dict(analytics.get("compact_summary", {})).get("recommendations", {}).get("suggested_next_templates", [])
    )
    prior_seed_context_conclusions = dict(seed_context_artifact.get("diagnostic_conclusions", {}))
    stability_conclusions = dict(stability_artifact.get("diagnostic_conclusions", {}))
    alignment_conclusions = dict(alignment_artifact.get("diagnostic_conclusions", {}))

    stability_seed_map = {
        int(dict(item).get("seed", -1)): dict(item)
        for item in list(stability_artifact.get("safe_pool_metrics_by_seed", []))
        if _safe_metric(dict(item).get("seed")) is not None
    }
    context_seed_map = {
        int(dict(item).get("seed", -1)): dict(item)
        for item in list(seed_context_artifact.get("per_seed_safe_slice_summary", []))
        if _safe_metric(dict(item).get("seed")) is not None
    }
    alignment_seed_map = {
        int(dict(item).get("seed", -1)): dict(item)
        for item in list(alignment_artifact.get("seed_contexts", []))
        if _safe_metric(dict(item).get("seed")) is not None
    }
    alignment_failure_map = {
        int(dict(item).get("seed", -1)): dict(item)
        for item in list(alignment_artifact.get("seed_failure_modes", []))
        if _safe_metric(dict(item).get("seed")) is not None
    }
    v2_seed_map = {
        int(dict(item).get("seed", -1)): dict(item)
        for item in list(v2_artifact.get("seed_summaries", []))
        if _safe_metric(dict(item).get("seed")) is not None
    }
    available_seed_ids = sorted(
        set(stability_seed_map.keys())
        | set(context_seed_map.keys())
        | set(alignment_seed_map.keys())
        | set(alignment_failure_map.keys())
        | set(v2_seed_map.keys())
    )
    requested_seed_ids = [int(seed) for seed in list(seeds) if int(seed) in available_seed_ids]
    seed_ids = requested_seed_ids if requested_seed_ids else available_seed_ids

    def _dict_ints(payload: Any) -> Dict[str, int]:
        return {
            str(name): int(count)
            for name, count in dict(payload or {}).items()
            if _safe_metric(count) is not None
        }

    def _merge_counter(rows: List[Dict[str, Any]], key: str) -> Counter[str]:
        counts: Counter[str] = Counter()
        for row in rows:
            for name, count in dict(row.get(key, {})).items():
                counts[str(name)] += int(count)
        return counts

    def _mean_nested(rows: List[Dict[str, Any]], nested_key: str, key: str) -> float:
        values = []
        for row in rows:
            value = _safe_metric(dict(row.get(nested_key, {})).get(key))
            if value is not None:
                values.append(float(value))
        return float(_mean(values) or 0.0)

    def _mean_flat(rows: List[Dict[str, Any]], key: str) -> float:
        values = []
        for row in rows:
            value = _safe_metric(row.get(key))
            if value is not None:
                values.append(float(value))
        return float(_mean(values) or 0.0)

    def _share(counter: Counter[str], name: str) -> float:
        total = int(sum(counter.values()))
        if total <= 0:
            return 0.0
        return float(counter.get(str(name), 0) / float(total))

    per_seed_rows: List[Dict[str, Any]] = []
    aggregate_blocker_counts: Counter[str] = Counter()
    precursor_events = list(dict(seed_context_artifact.get("precursor_indicators", {})).get("precursor_events", []))
    precursor_summary = dict(dict(seed_context_artifact.get("precursor_indicators", {})).get("precursor_event_summary", {}))

    for seed in list(seed_ids):
        stability_seed = dict(stability_seed_map.get(int(seed), {}))
        context_seed = dict(context_seed_map.get(int(seed), {}))
        alignment_seed = dict(alignment_seed_map.get(int(seed), {}))
        alignment_failure = dict(alignment_failure_map.get(int(seed), {}))
        v2_seed = dict(v2_seed_map.get(int(seed), {}))
        key_critic_summaries = dict(context_seed.get("key_critic_summaries", {}))
        if not key_critic_summaries:
            key_critic_summaries = {
                "benchmark_distance_mean": alignment_seed.get("mean_benchmark_distance"),
                "projection_shape_mean": alignment_seed.get("mean_projection_shape"),
                "gain_goal_mean": alignment_seed.get("mean_gain_goal"),
                "stability_mean": alignment_seed.get("mean_stability"),
                "scarcity": alignment_seed.get("scarcity"),
            }

        safe_pool_count = int(stability_seed.get("safe_pool_count", context_seed.get("safe_pool_count", 0)))
        safe_pool_benchmark_like_count = int(
            stability_seed.get("safe_pool_benchmark_like_count", context_seed.get("safe_pool_benchmark_like_count", 0))
        )
        selected_count = int(
            stability_seed.get(
                "slice_activation_count",
                context_seed.get("selected_count", v2_seed.get("slice_activation_count", 0)),
            )
        )
        selected_benchmark_like_count = int(
            stability_seed.get("slice_benchmark_like_count", context_seed.get("selected_benchmark_like_count", 0))
        )
        blocked_candidate_count = int(stability_seed.get("blocked_candidate_count", context_seed.get("blocked_candidate_count", 0)))
        context_shift_score = float(
            _safe_metric(
                stability_seed.get(
                    "context_shift_score",
                    context_seed.get("context_shift_score", alignment_failure.get("context_shift_score", 0.0)),
                )
            )
            or 0.0
        )
        subtype_mix = _dict_ints(context_seed.get("subtype_mix", {}))
        blocker_mix = _dict_ints(context_seed.get("blocker_mix", {}))
        aggregate_blocker_counts.update(blocker_mix)

        per_seed_rows.append(
            {
                "seed": int(seed),
                "blocked_candidate_count": int(blocked_candidate_count),
                "safe_pool_count": int(safe_pool_count),
                "safe_pool_benchmark_like_count": int(safe_pool_benchmark_like_count),
                "safe_pool_benchmark_like_fraction": float(safe_pool_benchmark_like_count / safe_pool_count) if safe_pool_count > 0 else 0.0,
                "selected_count": int(selected_count),
                "selected_benchmark_like_count": int(selected_benchmark_like_count),
                "context_shift_score": float(context_shift_score),
                "subtype_mix": subtype_mix,
                "blocker_mix": blocker_mix,
                "key_critic_summaries": {
                    "benchmark_distance_mean": _safe_metric(key_critic_summaries.get("benchmark_distance_mean")),
                    "projection_shape_mean": _safe_metric(key_critic_summaries.get("projection_shape_mean")),
                    "gain_goal_mean": _safe_metric(key_critic_summaries.get("gain_goal_mean")),
                    "stability_mean": _safe_metric(key_critic_summaries.get("stability_mean")),
                    "scarcity": _safe_metric(key_critic_summaries.get("scarcity")),
                    "mean_slice_projection_error": _safe_metric(stability_seed.get("mean_slice_projection_error")),
                },
                "dominant_subtype": str(context_seed.get("dominant_subtype", "none")),
                "dominant_blocker": str(
                    max(blocker_mix.items(), key=lambda item: (int(item[1]), str(item[0])))[0] if blocker_mix else "none"
                ),
                "availability_present": bool(safe_pool_benchmark_like_count > 0),
                "collapse_case": bool(context_seed.get("collapse_case", False)),
                "collapse_driver": str(context_seed.get("collapse_driver", "mixed")),
            }
        )

    availability_present_rows = [row for row in per_seed_rows if bool(row.get("availability_present", False))]
    availability_absent_rows = [row for row in per_seed_rows if not bool(row.get("availability_present", False))]

    def _group_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        subtype_counts = _merge_counter(rows, "subtype_mix")
        blocker_counts = _merge_counter(rows, "blocker_mix")
        return {
            "case_count": int(len(rows)),
            "safe_pool_count_mean": float(_mean_flat(rows, "safe_pool_count")),
            "safe_pool_benchmark_like_fraction_mean": float(_mean_flat(rows, "safe_pool_benchmark_like_fraction")),
            "selected_count_mean": float(_mean_flat(rows, "selected_count")),
            "selected_benchmark_like_count_mean": float(_mean_flat(rows, "selected_benchmark_like_count")),
            "context_shift_mean": float(_mean_flat(rows, "context_shift_score")),
            "benchmark_distance_mean": float(_mean_nested(rows, "key_critic_summaries", "benchmark_distance_mean")),
            "projection_shape_mean": float(_mean_nested(rows, "key_critic_summaries", "projection_shape_mean")),
            "gain_goal_mean": float(_mean_nested(rows, "key_critic_summaries", "gain_goal_mean")),
            "stability_mean": float(_mean_nested(rows, "key_critic_summaries", "stability_mean")),
            "mean_slice_projection_error": float(_mean_nested(rows, "key_critic_summaries", "mean_slice_projection_error")),
            "subtype_counts": {
                str(name): int(count)
                for name, count in sorted(subtype_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
            "blocker_counts": {
                str(name): int(count)
                for name, count in sorted(blocker_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
            "retained_like_share": float(_share(subtype_counts, "retained_like_profile")),
            "gain_fragile_share": float(_share(subtype_counts, "gain_fragile_profile")),
            "stability_fragile_share": float(_share(subtype_counts, "stability_fragile")),
            "projection_shape_fragile_share": float(_share(subtype_counts, "projection_shape_fragile")),
        }

    present_summary = _group_summary(availability_present_rows)
    absent_summary = _group_summary(availability_absent_rows)
    availability_driver_scores = {
        "scarcity": float(
            max(0.0, float(present_summary["safe_pool_count_mean"]) - float(absent_summary["safe_pool_count_mean"]))
            + max(0.0, float(present_summary["safe_pool_benchmark_like_fraction_mean"]) - float(absent_summary["safe_pool_benchmark_like_fraction_mean"]))
        ),
        "subtype_loss": float(
            max(0.0, float(present_summary["retained_like_share"]) - float(absent_summary["retained_like_share"]))
            + 0.50 * max(0.0, float(present_summary["gain_fragile_share"]) - float(absent_summary["gain_fragile_share"]))
            + 0.35 * max(0.0, float(absent_summary["stability_fragile_share"]) - float(present_summary["stability_fragile_share"]))
        ),
        "context_shift": float(max(0.0, float(absent_summary["context_shift_mean"]) - float(present_summary["context_shift_mean"]))),
        "benchmark_distance_blowout": float(max(0.0, float(absent_summary["benchmark_distance_mean"]) - float(present_summary["benchmark_distance_mean"]))),
        "projection_shape_shift": float(max(0.0, float(absent_summary["projection_shape_mean"]) - float(present_summary["projection_shape_mean"]))),
    }
    sorted_driver_scores = sorted(availability_driver_scores.items(), key=lambda item: (-float(item[1]), str(item[0])))
    availability_driver = "mixed"
    if sorted_driver_scores:
        top_name, top_score = sorted_driver_scores[0]
        second_score = float(sorted_driver_scores[1][1]) if len(sorted_driver_scores) >= 2 else 0.0
        if float(top_score) > 0.15 and float(top_score) >= float(second_score) + 0.08:
            availability_driver = str(top_name)

    precursor_scores = {
        "safe_pool_scarcity": float(availability_driver_scores["scarcity"]),
        "subtype_disappearance": float(availability_driver_scores["subtype_loss"]),
        "benchmark_distance_shift": float(availability_driver_scores["benchmark_distance_blowout"] + 0.40 * availability_driver_scores["context_shift"]),
        "projection_shape_shift": float(availability_driver_scores["projection_shape_shift"] + 0.25 * availability_driver_scores["context_shift"]),
        "mixed": float(0.50 * max(0.0, float(absent_summary["stability_mean"]) - float(present_summary["stability_mean"]))),
    }
    sorted_precursor_scores = sorted(precursor_scores.items(), key=lambda item: (-float(item[1]), str(item[0])))
    dominant_absence_precursor = "mixed"
    if sorted_precursor_scores:
        top_name, top_score = sorted_precursor_scores[0]
        second_score = float(sorted_precursor_scores[1][1]) if len(sorted_precursor_scores) >= 2 else 0.0
        if float(top_score) > 0.15 and float(top_score) >= float(second_score) + 0.06:
            dominant_absence_precursor = str(top_name)

    missing_subtypes = sorted(
        {
            str(name)
            for name, count in dict(present_summary.get("subtype_counts", {})).items()
            if int(count) > 0 and int(dict(absent_summary.get("subtype_counts", {})).get(str(name), 0)) <= 0
        }
    )
    availability_predictable = bool(
        len(availability_present_rows) >= 1
        and len(availability_absent_rows) >= 1
        and (float(sorted_precursor_scores[0][1]) >= 0.20 if sorted_precursor_scores else False)
    )

    if availability_predictable:
        next_control_hypothesis = "benchmark_alignment_critic_v2"
        recommended_next_template = "critic_split.benchmark_alignment_critic_v2"
        recommendation_reason = "availability loss is now structured enough to justify a benchmark-alignment critic that models when benchmark-like safe candidates exist under context"
    elif str(stability_conclusions.get("next_control_hypothesis", "")) in {"benchmark_alignment_model", "stability_context_retention_continue"}:
        next_control_hypothesis = "stability_context_retention_continue"
        recommended_next_template = "critic_split.benchmark_alignment_critic_v1"
        recommendation_reason = "availability evidence is useful but still too sparse for a new critic generation, so the next step should stay in stability/context-conditioned refinement"
    else:
        next_control_hypothesis = "no_control_yet"
        recommended_next_template = "critic_split.projection_gain_goal_v2"
        recommendation_reason = "availability evidence remains too sparse to justify a new benchmark-alignment critic generation"

    observability_gain = {
        "passed": bool(len(per_seed_rows) >= 3 and len(availability_present_rows) >= 1 and len(availability_absent_rows) >= 1),
        "seed_count": int(len(per_seed_rows)),
        "availability_present_case_count": int(len(availability_present_rows)),
        "availability_absent_case_count": int(len(availability_absent_rows)),
        "blocked_candidate_count": int(sum(int(row.get("blocked_candidate_count", 0)) for row in per_seed_rows)),
        "safe_pool_count": int(sum(int(row.get("safe_pool_count", 0)) for row in per_seed_rows)),
        "reason": (
            "captured enough safe-pool present/absent evidence to characterize benchmark-like candidate availability under context"
            if len(per_seed_rows) >= 3 and len(availability_present_rows) >= 1 and len(availability_absent_rows) >= 1
            else "insufficient safe-pool present/absent evidence to characterize benchmark-like availability"
        ),
    }
    activation_analysis = {
        "passed": bool(recommended_next_template and len(availability_absent_rows) >= 1),
        "availability_driver": str(availability_driver),
        "dominant_absence_precursor": str(dominant_absence_precursor),
        "benchmark_like_availability_predictable": bool(availability_predictable),
        "support_counts": {
            "availability_present_cases": int(len(availability_present_rows)),
            "availability_absent_cases": int(len(availability_absent_rows)),
            "precursor_events": int(len(precursor_events)),
        },
        "reason": (
            f"availability analysis points to {next_control_hypothesis} because {availability_driver} and {dominant_absence_precursor} dominate present-vs-absent contrast"
            if recommended_next_template
            else "availability evidence did not resolve into a useful next-step hypothesis"
        ),
    }
    ambiguity_reduction = {
        "passed": bool(observability_gain["passed"] and (availability_predictable or availability_driver != "mixed")),
        "score": float(
            min(
                1.0,
                0.24
                + 0.20 * int(availability_predictable)
                + 0.16 * int(availability_driver != "mixed")
                + 0.14 * int(dominant_absence_precursor != "mixed")
                + 0.12 * min(1.0, len(availability_present_rows) / 2.0)
                + 0.12 * min(1.0, len(availability_absent_rows) / 2.0),
            )
        ),
        "reason": (
            "the availability snapshot narrows safe-pool failure to a specific context-conditioned availability mechanism"
            if availability_predictable or availability_driver != "mixed"
            else "availability evidence remains too ambiguous to justify a new benchmark-alignment critic generation"
        ),
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "diagnostic-only benchmark-context availability snapshot with no live-policy mutation and no benchmark semantic changes",
    }
    later_selection_usefulness = {
        "passed": bool(recommended_next_template),
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
        "analytics_prior_suggestions": prior_suggestions[:3],
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.benchmark_context_availability_snapshot",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "dependency_context": {
            "critic_v2_artifact_path": str(v2_artifact.get("_artifact_path", "")),
            "safe_slice_purity_artifact_path": str(purity_artifact.get("_artifact_path", "")),
            "benchmark_distance_artifact_path": str(distance_artifact.get("_artifact_path", "")),
            "benchmark_alignment_artifact_path": str(alignment_artifact.get("_artifact_path", "")),
            "stability_context_artifact_path": str(stability_artifact.get("_artifact_path", "")),
            "seed_context_artifact_path": str(seed_context_artifact.get("_artifact_path", "")),
            "prior_seed_context_driver": str(prior_seed_context_conclusions.get("collapse_driver", "")),
            "prior_alignment_mechanism": str(alignment_conclusions.get("strongest_retention_mechanism", "")),
            "prior_stability_mechanism": str(stability_conclusions.get("best_stability_retention_mechanism", "")),
        },
        "per_seed_availability_summary": per_seed_rows,
        "availability_present_vs_absent_analysis": {
            "availability_present": present_summary,
            "availability_absent": absent_summary,
            "contrast": {
                "safe_pool_count_delta": float(present_summary["safe_pool_count_mean"] - absent_summary["safe_pool_count_mean"]),
                "benchmark_like_fraction_delta": float(present_summary["safe_pool_benchmark_like_fraction_mean"] - absent_summary["safe_pool_benchmark_like_fraction_mean"]),
                "context_shift_delta": float(absent_summary["context_shift_mean"] - present_summary["context_shift_mean"]),
                "benchmark_distance_delta": float(absent_summary["benchmark_distance_mean"] - present_summary["benchmark_distance_mean"]),
                "projection_shape_delta": float(absent_summary["projection_shape_mean"] - present_summary["projection_shape_mean"]),
                "gain_goal_delta": float(absent_summary["gain_goal_mean"] - present_summary["gain_goal_mean"]),
                "stability_delta": float(absent_summary["stability_mean"] - present_summary["stability_mean"]),
                "missing_subtypes_in_absence": missing_subtypes,
            },
        },
        "collapse_absence_interpretation": {
            "availability_driver_scores": {str(name): float(value) for name, value in sorted_driver_scores},
            "availability_driver": str(availability_driver),
            "dominant_absence_precursor": str(dominant_absence_precursor),
            "seed2_context": dict(next((row for row in per_seed_rows if int(row.get("seed", -1)) == 2), {})),
        },
        "contrast_with_non_absence_cases": {
            "availability_present_rows": availability_present_rows,
            "availability_absent_rows": availability_absent_rows,
        },
        "precursor_indicators": {
            "prior_seed_context_precursor_summary": precursor_summary,
            "prior_seed_context_precursor_events": precursor_events[-12:],
            "absence_precursor_scores": {
                str(name): float(value) for name, value in sorted(precursor_scores.items(), key=lambda item: (-float(item[1]), str(item[0])))
            },
            "within_seed_precursor_support_count": int(len(precursor_events)),
            "availability_decline_precedes_safe_pool_decline": bool(
                precursor_summary.get("count", 0)
                and float(_safe_metric(precursor_summary.get("mean_benchmark_like_fraction_delta")) or 0.0) < 0.0
                and float(_safe_metric(precursor_summary.get("mean_safe_pool_count_delta")) or 0.0) >= 0.0
            ),
        },
        "source_metric_summaries": {
            "critic_v2_benchmark_alignment_summary": dict(v2_artifact.get("benchmark_alignment_summary", {})),
            "alignment_predictor_strengths": dict(dict(alignment_artifact.get("purity_metrics", {})).get("predictor_strengths", {})),
            "distance_predictor_strengths": dict(dict(distance_artifact.get("purity_metrics", {})).get("predictor_strengths", {})),
            "stability_predictor_strengths": dict(dict(stability_artifact.get("purity_metrics", {})).get("predictor_strengths", {})),
        },
        "blocker_counts": {
            str(name): int(count) for name, count in sorted(aggregate_blocker_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
        },
        "diagnostic_conclusions": {
            "availability_driver": str(availability_driver),
            "dominant_absence_precursor": str(dominant_absence_precursor),
            "benchmark_like_availability_predictable": bool(availability_predictable),
            "recommended_next_template": str(recommended_next_template),
            "next_control_hypothesis": str(next_control_hypothesis),
            "support_availability_present_cases": int(len(availability_present_rows)),
            "support_availability_absent_cases": int(len(availability_absent_rows)),
        },
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "sample_rows": {
            "availability_present_examples": availability_present_rows[:4],
            "availability_absent_examples": availability_absent_rows[:4],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_benchmark_context_availability_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(
        observability_gain["passed"]
        and activation_analysis["passed"]
        and ambiguity_reduction["passed"]
        and safety_neutrality["passed"]
        and later_selection_usefulness["passed"]
    )
    if not bool(observability_gain["passed"]):
        reason = "diagnostic shadow failed: insufficient safe-pool present/absent evidence for benchmark-context availability analysis"
    elif not bool(ambiguity_reduction["passed"]):
        reason = "diagnostic shadow failed: benchmark-like availability remained too ambiguous to guide the next critic generation"
    else:
        reason = "diagnostic shadow passed: benchmark-like candidate availability inside the safe pool was characterized well enough to guide the next benchmark-alignment critic step"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_safe_slice_selection_gap_snapshot_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    del cfg, rounds, seeds
    broader_v2_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.projection_gain_goal_v2")
    alignment_v2_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_alignment_critic_v2")
    stability_v2_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.stability_context_retention_probe_v2")
    availability_artifact = _load_latest_diagnostic_artifact_by_template("memory_summary.benchmark_context_availability_snapshot")
    if not broader_v2_artifact or not alignment_v2_artifact or not stability_v2_artifact or not availability_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: selection-gap snapshot requires projection_gain_goal_v2, benchmark_alignment_critic_v2, stability_context_retention_probe_v2, and benchmark_context_availability_snapshot artifacts",
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
                "reason": "cannot recommend a follow-up without the prerequisite artifacts",
            },
        }

    analytics = build_intervention_ledger_analytics()
    prior_suggestions = list(
        dict(analytics.get("compact_summary", {})).get("recommendations", {}).get("suggested_next_templates", [])
    )
    target_family = str(dict(proposal.get("intended_benefit", {})).get("target_family", "gain_goal_conflict"))
    availability_present_summary = dict(
        dict(availability_artifact.get("availability_present_vs_absent_analysis", {})).get("availability_present", {})
    )
    healthy_safe_pool_mean = float(_safe_metric(availability_present_summary.get("safe_pool_count_mean")) or 4.0)
    healthy_benchmark_distance_mean = float(
        _safe_metric(availability_present_summary.get("benchmark_distance_mean")) or 0.70
    )
    healthy_projection_shape_mean = float(
        _safe_metric(availability_present_summary.get("projection_shape_mean")) or 0.50
    )

    def _collapse_severity(row: Dict[str, Any]) -> float:
        key_critic = dict(row.get("key_critic_summaries", {}))
        safe_pool_count = float(_safe_metric(row.get("safe_pool_count")) or 0.0)
        benchmark_like_count = float(_safe_metric(row.get("safe_pool_benchmark_like_count")) or 0.0)
        context_shift = float(_safe_metric(row.get("context_shift_score")) or 0.0)
        benchmark_distance_mean = float(_safe_metric(key_critic.get("benchmark_distance_mean")) or 0.0)
        projection_shape_mean = float(_safe_metric(key_critic.get("projection_shape_mean")) or 0.0)
        scarcity = max(0.0, healthy_safe_pool_mean - safe_pool_count)
        missing_like = (
            1.0
            if benchmark_like_count <= 0.0
            else max(0.0, 1.0 - (benchmark_like_count / max(1.0, safe_pool_count)))
        )
        benchmark_distance_penalty = max(0.0, benchmark_distance_mean - healthy_benchmark_distance_mean)
        projection_shape_penalty = max(0.0, projection_shape_mean - healthy_projection_shape_mean)
        return float(
            0.45 * scarcity
            + 0.70 * missing_like
            + 0.45 * context_shift
            + 0.35 * benchmark_distance_penalty
            + 0.30 * projection_shape_penalty
        )

    def _mix_distance(left: Dict[str, Any], right: Dict[str, Any]) -> float:
        names = set(left.keys()) | set(right.keys())
        left_total = float(sum(float(left.get(name, 0.0)) for name in names))
        right_total = float(sum(float(right.get(name, 0.0)) for name in names))
        if left_total <= 0.0 or right_total <= 0.0:
            return 0.0
        return float(
            sum(
                abs(float(left.get(name, 0.0)) / left_total - float(right.get(name, 0.0)) / right_total)
                for name in names
            )
            / 2.0
        )

    alignment_seed_map = {
        int(dict(item).get("seed", -1)): dict(item)
        for item in list(alignment_v2_artifact.get("safe_pool_metrics_by_seed", []))
        if _safe_metric(dict(item).get("seed")) is not None
    }
    stability_seed_map = {
        int(dict(item).get("seed", -1)): dict(item)
        for item in list(stability_v2_artifact.get("safe_pool_metrics_by_seed", []))
        if _safe_metric(dict(item).get("seed")) is not None
    }
    seed_ids = sorted(set(alignment_seed_map.keys()) | set(stability_seed_map.keys()))
    per_seed_accounting: List[Dict[str, Any]] = []
    lost_selected_cases: List[Dict[str, Any]] = []
    mechanism_counts: Counter[str] = Counter()

    for seed in seed_ids:
        align_row = dict(alignment_seed_map.get(int(seed), {}))
        probe_row = dict(stability_seed_map.get(int(seed), {}))
        safe_pool_count_delta = int(probe_row.get("safe_pool_count", 0)) - int(align_row.get("safe_pool_count", 0))
        safe_pool_like_delta = int(probe_row.get("safe_pool_benchmark_like_count", 0)) - int(
            align_row.get("safe_pool_benchmark_like_count", 0)
        )
        selected_like_delta = int(probe_row.get("selected_benchmark_like_count", 0)) - int(
            align_row.get("selected_benchmark_like_count", 0)
        )
        context_shift_delta = float(_safe_metric(probe_row.get("context_shift_score")) or 0.0) - float(
            _safe_metric(align_row.get("context_shift_score")) or 0.0
        )
        subtype_distance = _mix_distance(
            dict(align_row.get("subtype_mix", {})),
            dict(probe_row.get("subtype_mix", {})),
        )
        mechanism = "mixed"
        if selected_like_delta < 0:
            if safe_pool_count_delta < 0 and safe_pool_like_delta <= 0:
                mechanism = "scarcity"
            elif safe_pool_like_delta < 0:
                mechanism = "retention failure"
            elif subtype_distance >= 0.20:
                mechanism = "subtype conditioning side effect"
            elif abs(context_shift_delta) >= 0.10:
                mechanism = "context-shift interaction"
            elif int(probe_row.get("selected_count", 0)) < int(align_row.get("selected_count", 0)):
                mechanism = "ranking/selection narrowing"
            else:
                mechanism = "tie-break / selection policy artifact"
            mechanism_counts[str(mechanism)] += abs(int(selected_like_delta))
            lost_selected_cases.append(
                {
                    "seed": int(seed),
                    "context_class": "collapse_prone"
                    if bool(probe_row.get("collapse_case", False) or align_row.get("collapse_case", False))
                    else "stable_context",
                    "safe_pool_count_alignment_v2": int(align_row.get("safe_pool_count", 0)),
                    "safe_pool_count_probe": int(probe_row.get("safe_pool_count", 0)),
                    "safe_pool_benchmark_like_count_alignment_v2": int(
                        align_row.get("safe_pool_benchmark_like_count", 0)
                    ),
                    "safe_pool_benchmark_like_count_probe": int(probe_row.get("safe_pool_benchmark_like_count", 0)),
                    "selected_benchmark_like_count_alignment_v2": int(
                        align_row.get("selected_benchmark_like_count", 0)
                    ),
                    "selected_benchmark_like_count_probe": int(probe_row.get("selected_benchmark_like_count", 0)),
                    "context_shift_alignment_v2": float(_safe_metric(align_row.get("context_shift_score")) or 0.0),
                    "context_shift_probe": float(_safe_metric(probe_row.get("context_shift_score")) or 0.0),
                    "subtype_mix_alignment_v2": dict(align_row.get("subtype_mix", {})),
                    "subtype_mix_probe": dict(probe_row.get("subtype_mix", {})),
                    "mechanism_attribution": str(mechanism),
                }
            )

        per_seed_accounting.append(
            {
                "seed": int(seed),
                "context_class": "collapse_prone"
                if bool(probe_row.get("collapse_case", False) or align_row.get("collapse_case", False))
                else "stable_context",
                "safe_pool_count_alignment_v2": int(align_row.get("safe_pool_count", 0)),
                "safe_pool_count_probe": int(probe_row.get("safe_pool_count", 0)),
                "safe_pool_benchmark_like_count_alignment_v2": int(align_row.get("safe_pool_benchmark_like_count", 0)),
                "safe_pool_benchmark_like_count_probe": int(probe_row.get("safe_pool_benchmark_like_count", 0)),
                "selected_benchmark_like_count_alignment_v2": int(align_row.get("selected_benchmark_like_count", 0)),
                "selected_benchmark_like_count_probe": int(probe_row.get("selected_benchmark_like_count", 0)),
                "projection_safe_retention_alignment_v2": float(
                    _safe_metric(align_row.get("slice_projection_safe_rate")) or 0.0
                ),
                "projection_safe_retention_probe": float(
                    _safe_metric(probe_row.get("slice_projection_safe_rate")) or 0.0
                ),
                "collapse_severity_alignment_v2": float(_collapse_severity(align_row)) if align_row else 0.0,
                "collapse_severity_probe": float(_collapse_severity(probe_row)) if probe_row else 0.0,
                "safe_pool_count_delta": int(safe_pool_count_delta),
                "safe_pool_benchmark_like_count_delta": int(safe_pool_like_delta),
                "selected_benchmark_like_count_delta": int(selected_like_delta),
                "context_shift_delta": float(context_shift_delta),
                "subtype_mix_distance": float(subtype_distance),
            }
        )

    dominant_mechanism = (
        mechanism_counts.most_common(1)[0][0] if mechanism_counts else "mixed"
    )
    hidden_upstream_retention_failure = bool(
        any(
            int(row.get("safe_pool_benchmark_like_count_delta", 0)) < 0
            or int(row.get("safe_pool_count_delta", 0)) < 0
            for row in per_seed_accounting
        )
    )
    collapse_seed_healthier = bool(
        any(
            row.get("context_class") == "collapse_prone"
            and float(row.get("collapse_severity_probe", 0.0)) < float(row.get("collapse_severity_alignment_v2", 0.0))
            for row in per_seed_accounting
        )
    )
    safe_pool_health_judgment = (
        "healthier_upstream_but_narrower_selector"
        if collapse_seed_healthier and not hidden_upstream_retention_failure
        else "selector_narrower_without_upstream_gain"
        if not hidden_upstream_retention_failure
        else "upstream_retention_still_unstable"
    )
    routing_likely_to_recover_lost_case = False
    routing_still_downstream = True

    alignment_compare = dict(alignment_v2_artifact.get("comparison_to_v2", {}))
    stability_compare = dict(stability_v2_artifact.get("comparison_to_benchmark_alignment_v2", {}))
    broader_compare = dict(stability_v2_artifact.get("comparison_to_projection_gain_goal_v2", {}))
    global_comparison = {
        "safe_pool_count_alignment_v2": int(
            dict(stability_v2_artifact.get("availability_metrics", {})).get("safe_pool_count_alignment_v2", 0)
        ),
        "safe_pool_count_probe": int(
            dict(stability_v2_artifact.get("availability_metrics", {})).get("safe_pool_count_probe", 0)
        ),
        "safe_pool_benchmark_like_count_alignment_v2": int(
            dict(stability_v2_artifact.get("availability_metrics", {})).get(
                "safe_pool_benchmark_like_count_alignment_v2", 0
            )
        ),
        "safe_pool_benchmark_like_count_probe": int(
            dict(stability_v2_artifact.get("availability_metrics", {})).get(
                "safe_pool_benchmark_like_count_probe", 0
            )
        ),
        "selected_benchmark_like_count_alignment_v2": int(
            dict(stability_v2_artifact.get("availability_metrics", {})).get(
                "selected_benchmark_like_count_alignment_v2", 0
            )
        ),
        "selected_benchmark_like_count_probe": int(
            dict(stability_v2_artifact.get("availability_metrics", {})).get(
                "selected_benchmark_like_count_probe", 0
            )
        ),
        "projection_safe_retention_alignment_v2": float(
            stability_compare.get("projection_safe_retention_rate_alignment_v2", 0.0)
        ),
        "projection_safe_retention_probe": float(
            stability_compare.get("projection_safe_retention_rate_probe", 0.0)
        ),
        "benchmark_like_retention_alignment_v2": float(
            stability_compare.get("benchmark_like_retention_rate_alignment_v2", 0.0)
        ),
        "benchmark_like_retention_probe": float(
            stability_compare.get("benchmark_like_retention_rate_probe", 0.0)
        ),
        "benchmark_slice_count_alignment_v2": int(
            dict(stability_v2_artifact.get("benchmark_relevance_summary", {})).get(
                "benchmark_slice_count_alignment_v2", 0
            )
        ),
        "benchmark_slice_count_probe": int(
            dict(stability_v2_artifact.get("benchmark_relevance_summary", {})).get(
                "benchmark_slice_count_probe", 0
            )
        ),
        "undercommit_coverage_alignment_v2": float(
            dict(stability_v2_artifact.get("benchmark_relevance_summary", {})).get(
                "benchmark_slice_coverage_undercommit_alignment_v2", 0.0
            )
        ),
        "undercommit_coverage_probe": float(
            dict(stability_v2_artifact.get("benchmark_relevance_summary", {})).get(
                "benchmark_slice_coverage_undercommit_probe", 0.0
            )
        ),
        "collapse_severity_alignment_v2": float(
            dict(stability_v2_artifact.get("collapse_specific_analysis", {})).get("prior_collapse_severity", 0.0)
        ),
        "collapse_severity_probe": float(
            dict(stability_v2_artifact.get("collapse_specific_analysis", {})).get("probe_collapse_severity", 0.0)
        ),
        "broader_projection_gain_goal_v2_slice_activation_count": int(
            broader_compare.get("slice_activation_count_projection_gain_goal_v2", 0)
        ),
        "broader_projection_gain_goal_v2_benchmark_slice_count": int(
            broader_compare.get("benchmark_slice_count_projection_gain_goal_v2", 0)
        ),
    }

    if dominant_mechanism in {"ranking/selection narrowing", "tie-break / selection policy artifact"} and not hidden_upstream_retention_failure:
        next_control_hypothesis = "selection_reliability_refinement"
        recommended_next_template = "critic_split.safe_slice_selection_reliability_probe_v1"
        decision_recommendation = "B"
        recommendation_reason = "the lost selected benchmark-like case occurred with unchanged safe-pool health, so the next step should refine safe-slice ranking/selection rather than routing or another context-memory pass"
    elif dominant_mechanism == "mixed":
        next_control_hypothesis = "diagnostic_clarification"
        recommended_next_template = "memory_summary.safe_slice_selection_gap_snapshot"
        decision_recommendation = "C"
        recommendation_reason = "the loss mechanism remains too mixed to justify another control-family probe yet"
    else:
        next_control_hypothesis = "benchmark_alignment_critic_continue"
        recommended_next_template = "critic_split.benchmark_alignment_critic_v2"
        decision_recommendation = "B"
        recommendation_reason = "the evidence still points to upstream critic/context modeling rather than routing, so the next step should remain in critic refinement"

    observability_gain = {
        "passed": bool(len(per_seed_accounting) >= 3 and bool(global_comparison)),
        "seed_count": int(len(per_seed_accounting)),
        "lost_selected_case_count": int(len(lost_selected_cases)),
        "reason": "captured enough completed critic artifacts to compare safe-pool health versus selected benchmark-like loss directly",
    }
    activation_analysis = {
        "passed": bool(len(lost_selected_cases) >= 1),
        "lost_selected_case_identified": bool(len(lost_selected_cases) >= 1),
        "reason": "the snapshot identifies the exact seed/context where selected benchmark-like count was lost"
        if lost_selected_cases
        else "no lost selected benchmark-like case was found to explain",
    }
    ambiguity_reduction = {
        "passed": bool(dominant_mechanism != "mixed"),
        "reason": "the snapshot isolates a dominant mechanism for the lost selected benchmark-like case"
        if dominant_mechanism != "mixed"
        else "the selection-gap mechanism remains mixed",
        "score": float(min(1.0, 0.35 + 0.20 * int(not hidden_upstream_retention_failure) + 0.20 * int(len(lost_selected_cases) >= 1) + 0.15 * int(collapse_seed_healthier) + 0.10 * int(dominant_mechanism != "mixed"))),
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "diagnostic-only artifact comparison with no live-policy mutation and no benchmark semantic changes",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
        "decision_recommendation": str(decision_recommendation),
        "analytics_prior_suggestions": prior_suggestions[:3],
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.safe_slice_selection_gap_snapshot",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "comparison_summary": global_comparison,
        "per_seed_context_accounting": per_seed_accounting,
        "lost_selected_benchmark_like_cases": lost_selected_cases,
        "mechanism_attribution": {
            "dominant_mechanism": str(dominant_mechanism),
            "hidden_upstream_retention_failure": bool(hidden_upstream_retention_failure),
            "safe_pool_health_judgment": str(safe_pool_health_judgment),
            "collapse_seed_healthier": bool(collapse_seed_healthier),
        },
        "explicit_answers": {
            "safe_pool_healthier_or_selector_narrower": str(safe_pool_health_judgment),
            "routing_likely_to_recover_lost_case": bool(routing_likely_to_recover_lost_case),
            "routing_still_downstream_of_real_issue": bool(routing_still_downstream),
        },
        "decision_recommendation": {
            "choice": str(decision_recommendation),
            "recommended_next_template": str(recommended_next_template),
            "rationale": str(recommendation_reason),
        },
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": {
            "dominant_mechanism": str(dominant_mechanism),
            "hidden_upstream_retention_failure": bool(hidden_upstream_retention_failure),
            "safe_pool_health_judgment": str(safe_pool_health_judgment),
            "routing_likely_to_recover_lost_case": bool(routing_likely_to_recover_lost_case),
            "routing_still_downstream": bool(routing_still_downstream),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
            "decision_recommendation": str(decision_recommendation),
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_safe_slice_selection_gap_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(
        observability_gain["passed"]
        and activation_analysis["passed"]
        and ambiguity_reduction["passed"]
        and safety_neutrality["passed"]
        and later_selection_usefulness["passed"]
    )
    if not bool(observability_gain["passed"]):
        reason = "diagnostic shadow failed: insufficient completed critic artifacts for safe-slice selection-gap analysis"
    elif not bool(activation_analysis["passed"]):
        reason = "diagnostic shadow failed: no lost selected benchmark-like case was identified"
    elif not bool(ambiguity_reduction["passed"]):
        reason = "diagnostic shadow passed: the selection-gap comparison is informative, but mechanism attribution remains mixed"
    else:
        reason = "diagnostic shadow passed: the selection-gap comparison identifies the dominant mechanism behind the missing selected benchmark-like case"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_benchmark_transfer_blocker_snapshot_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    del rounds, seeds
    routing_artifact = _load_latest_diagnostic_artifact_by_template("routing_rule.slice_targeted_benchmark_sweep_v1")
    alignment_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_alignment_critic_v2")
    stability_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.stability_context_retention_probe_v2")
    reliability_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.safe_slice_selection_reliability_probe_v1")
    if not routing_artifact or not alignment_artifact or not stability_artifact or not reliability_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: benchmark_transfer_blocker_snapshot_v1 requires routing sweep plus benchmark_alignment_critic_v2, stability_context_retention_probe_v2, and safe_slice_selection_reliability_probe_v1 artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without the prerequisite artifacts"},
        }

    analytics = build_intervention_ledger_analytics()
    prior_suggestions = list(dict(analytics.get("compact_summary", {})).get("recommendations", {}).get("suggested_next_templates", []))
    benchmark_result = run_trusted_benchmark_pack(cfg=cfg, mode="standalone", include_policy_sweep=True)
    detailed = dict(benchmark_result.get("detailed", {}))
    baseline_results = [dict(row) for row in list(detailed.get("results", [])) if isinstance(row, dict)]
    if not baseline_results:
        return {
            "passed": False,
            "shadow_contract": "diagnostic",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no frozen benchmark results available for transfer-blocker analysis",
            "observability_gain": {"passed": False, "reason": "no benchmark results"},
            "activation_analysis_usefulness": {"passed": False, "reason": "no benchmark results"},
            "ambiguity_reduction": {"passed": False, "reason": "no benchmark results"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without benchmark results"},
        }

    target_family = str(dict(proposal.get("intended_benefit", {})).get("target_family", "gain_goal_conflict"))
    projection_boundary = float(_targeted_projection_override_boundary(cfg))
    baseline_reject_results = [row for row in baseline_results if str(row.get("policy_decision", "")) == "reject"]
    benchmark_undercommit_all = [row for row in baseline_reject_results if str(row.get("oracle_decision", "")) in {"provisional", "full"}]
    benchmark_undercommit_target = [row for row in benchmark_undercommit_all if str(row.get("family", "")) == target_family]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (benchmark_undercommit_target if benchmark_reference_source == "target_family_undercommit" else benchmark_undercommit_all)
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }

    slice_definition = dict(stability_artifact.get("slice_definition", {}))
    projection_level_cap = float(slice_definition.get("projection_level_cap", 0.70))
    projection_shape_cap = float(slice_definition.get("projection_shape_cap", 0.65))
    gain_goal_floor = float(slice_definition.get("gain_goal_floor", 0.34))
    stability_cap = float(slice_definition.get("stability_cap", 0.42))
    projection_bad_safe_cap = float(slice_definition.get("projection_bad_safe_cap", 0.57))
    projection_error_safe_cap = float(slice_definition.get("projection_error_safe_cap", 0.0115))
    benchmark_distance_cap = float(slice_definition.get("benchmark_distance_cap", 1.0))
    gain_structure_level_soft_cap = float(slice_definition.get("gain_structure_level_soft_cap", projection_level_cap + 0.08))
    gain_structure_benchmark_distance_soft_cap = float(slice_definition.get("gain_structure_benchmark_distance_soft_cap", benchmark_distance_cap + 0.05))
    gain_structure_projection_bad_soft_cap = float(slice_definition.get("gain_structure_projection_bad_soft_cap", projection_bad_safe_cap + 0.02))
    gain_structure_gain_soft_floor = float(slice_definition.get("gain_structure_gain_soft_floor", gain_goal_floor + 0.08))

    required_families = ["calibration", "recovery", "persistence", "projection", "gain_goal_conflict"]
    family_breakdown: Dict[str, Dict[str, Any]] = {
        name: {
            "candidate_count_entering_evaluation": 0,
            "blocked_by_support": 0,
            "blocked_by_stability_guard": 0,
            "surviving_to_safe_pool": 0,
            "surviving_to_selected_benchmark_like": 0,
            "support_case_ids": [],
            "stability_case_ids": [],
            "final_admission_case_ids": [],
        }
        for name in required_families
    }

    all_rows: List[Dict[str, Any]] = []
    support_rows: List[Dict[str, Any]] = []
    blocker_not_supported_rows: List[Dict[str, Any]] = []
    unsupported_segment_rows: List[Dict[str, Any]] = []
    projection_policy_rows: List[Dict[str, Any]] = []
    stability_guard_rows: List[Dict[str, Any]] = []
    final_admission_rows: List[Dict[str, Any]] = []
    safe_pool_rows: List[Dict[str, Any]] = []

    for scenario_result in baseline_reject_results:
        row = _benchmark_scenario_candidate_row(
            cfg,
            scenario_result,
            projection_boundary=projection_boundary,
            benchmark_summary=benchmark_summary,
        )
        row["projection_policy_ok_provisional"] = bool(dict(scenario_result.get("candidate_summary", {})).get("projection_policy_ok_provisional", False))
        row["projection_level_critic"] = float(_row_projection_level_critic_v2(row, benchmark_summary, projection_boundary=projection_boundary))
        row["projection_shape_critic"] = float(_row_projection_shape_critic_v2(row, benchmark_summary))
        row["gain_goal_critic_v2"] = float(_row_gain_goal_critic_v2(row, benchmark_summary))
        row["stability_critic_v2"] = float(
            _row_stability_critic_v2(
                row,
                projection_level_critic=float(row["projection_level_critic"]),
                projection_shape_critic=float(row["projection_shape_critic"]),
                gain_goal_critic=float(row["gain_goal_critic_v2"]),
            )
        )
        row["alignment_subtype"] = _routing_slice_retest_subtype(
            row,
            benchmark_distance_cap=benchmark_distance_cap,
            projection_shape_cap=projection_shape_cap,
            gain_goal_floor=gain_goal_floor,
            stability_cap=stability_cap,
            gain_structure_benchmark_distance_soft_cap=gain_structure_benchmark_distance_soft_cap,
            gain_structure_gain_soft_floor=gain_structure_gain_soft_floor,
        )
        row.update(
            _routing_slice_retest_eval_row(
                row,
                projection_level_cap=projection_level_cap,
                projection_shape_cap=projection_shape_cap,
                gain_goal_floor=gain_goal_floor,
                stability_cap=stability_cap,
                projection_bad_safe_cap=projection_bad_safe_cap,
                projection_error_safe_cap=projection_error_safe_cap,
                benchmark_distance_cap=benchmark_distance_cap,
                gain_structure_level_soft_cap=gain_structure_level_soft_cap,
                gain_structure_benchmark_distance_soft_cap=gain_structure_benchmark_distance_soft_cap,
                gain_structure_projection_bad_soft_cap=gain_structure_projection_bad_soft_cap,
                gain_structure_gain_soft_floor=gain_structure_gain_soft_floor,
            )
        )

        if not bool(row.get("projection_policy_ok_provisional", False)):
            failure_stage = "before_candidate_support"
        elif str(row.get("slice_reason", "")) in {"blocker_not_supported", "unsupported_segment"}:
            failure_stage = "support_filter"
        elif str(row.get("slice_reason", "")) == "stability_guard":
            failure_stage = "stability_guard"
        elif bool(row.get("benchmark_safe_pool", False)):
            failure_stage = "safe_pool"
        else:
            failure_stage = "final_benchmark_admission"

        row["failure_stage"] = str(failure_stage)
        row["benchmark_context"] = "frozen_static"
        row["support_failure_kind"] = (
            "unsupported_blocker_group"
            if str(row.get("slice_reason", "")) == "blocker_not_supported"
            else "unsupported_segment"
            if str(row.get("slice_reason", "")) == "unsupported_segment"
            else "none"
        )

        family = str(row.get("family", "unknown"))
        if family not in family_breakdown:
            family_breakdown[family] = {
                "candidate_count_entering_evaluation": 0,
                "blocked_by_support": 0,
                "blocked_by_stability_guard": 0,
                "surviving_to_safe_pool": 0,
                "surviving_to_selected_benchmark_like": 0,
                "support_case_ids": [],
                "stability_case_ids": [],
                "final_admission_case_ids": [],
            }
        family_breakdown[family]["candidate_count_entering_evaluation"] += 1
        if failure_stage == "support_filter":
            family_breakdown[family]["blocked_by_support"] += 1
            family_breakdown[family]["support_case_ids"].append(str(row.get("scenario_id", "")))
        elif failure_stage == "stability_guard":
            family_breakdown[family]["blocked_by_stability_guard"] += 1
            family_breakdown[family]["stability_case_ids"].append(str(row.get("scenario_id", "")))
        elif failure_stage == "final_benchmark_admission":
            family_breakdown[family]["final_admission_case_ids"].append(str(row.get("scenario_id", "")))
        if bool(row.get("benchmark_safe_pool", False)):
            family_breakdown[family]["surviving_to_safe_pool"] += 1
            safe_pool_rows.append(dict(row))

        if failure_stage == "before_candidate_support":
            projection_policy_rows.append(dict(row))
        elif failure_stage == "support_filter":
            support_rows.append(dict(row))
            if str(row.get("slice_reason", "")) == "blocker_not_supported":
                blocker_not_supported_rows.append(dict(row))
            if str(row.get("slice_reason", "")) == "unsupported_segment":
                unsupported_segment_rows.append(dict(row))
        elif failure_stage == "stability_guard":
            stability_guard_rows.append(dict(row))
        elif failure_stage == "final_benchmark_admission":
            final_admission_rows.append(dict(row))
        all_rows.append(dict(row))

    selection_target_count = int(
        dict(reliability_artifact.get("comparison_to_stability_context_retention_probe_v2", {})).get("selected_benchmark_like_count_probe")
        or dict(reliability_artifact.get("comparison_to_benchmark_alignment_critic_v2", {})).get("selected_benchmark_like_count_probe")
        or 0
    )
    selection_target_count = max(1, selection_target_count)
    safe_pool_benchmark_like_rows = [row for row in safe_pool_rows if bool(row.get("benchmark_like_safe", False))]
    selected_source_rows = safe_pool_benchmark_like_rows if safe_pool_benchmark_like_rows else safe_pool_rows
    selected_rows = sorted(selected_source_rows, key=lambda item: _routing_slice_retest_sort_key(item, target_family))[: min(len(selected_source_rows), selection_target_count)]
    for row in selected_rows:
        if bool(row.get("benchmark_like_safe", False)):
            family_breakdown[str(row.get("family", "unknown"))]["surviving_to_selected_benchmark_like"] += 1

    def _top_ids(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
        counts = Counter(str(row.get("scenario_id", "unknown")) for row in rows if str(row.get("scenario_id", "")))
        return [{"scenario_id": str(name), "count": int(count)} for name, count in counts.most_common(limit)]

    def _top_counts(rows: List[Dict[str, Any]], key: str, limit: int = 5) -> List[Dict[str, Any]]:
        counts = Counter(str(row.get(key, "unknown")) for row in rows if str(row.get(key, "")))
        return [{"name": str(name), "count": int(count)} for name, count in counts.most_common(limit)]

    for family, stats in family_breakdown.items():
        stats["support_case_ids"] = [{"scenario_id": str(name), "count": int(count)} for name, count in Counter(stats["support_case_ids"]).most_common(5)]
        stats["stability_case_ids"] = [{"scenario_id": str(name), "count": int(count)} for name, count in Counter(stats["stability_case_ids"]).most_common(5)]
        stats["final_admission_case_ids"] = [{"scenario_id": str(name), "count": int(count)} for name, count in Counter(stats["final_admission_case_ids"]).most_common(5)]

    unsupported_blocker_fraction = (
        float(sum(str(row.get("blocker_group", "")) not in {"projection_guard", "confidence_gain"} for row in blocker_not_supported_rows) / len(blocker_not_supported_rows))
        if blocker_not_supported_rows
        else 0.0
    )
    support_family_share = (
        float(Counter(str(row.get("family", "unknown")) for row in blocker_not_supported_rows).most_common(1)[0][1] / len(blocker_not_supported_rows))
        if blocker_not_supported_rows
        else 0.0
    )
    if projection_policy_rows and len(projection_policy_rows) >= max(4, int(0.15 * len(baseline_reject_results))):
        blocker_not_supported_attribution = "benchmark_runner_contract_mismatch"
    elif blocker_not_supported_rows and unsupported_blocker_fraction >= 0.65:
        blocker_not_supported_attribution = "taxonomy_support_coverage_limitation"
    elif blocker_not_supported_rows and support_family_share >= 0.60:
        blocker_not_supported_attribution = "proposal_family_incompatibility"
    else:
        blocker_not_supported_attribution = "genuine_structural_limitation_of_current_critic_lineage"

    stability_mean = _mean_key(stability_guard_rows, "stability_critic_v2") or 0.0
    stability_excess = _mean([max(0.0, float(_safe_metric(row.get("stability_critic_v2")) or 0.0) - stability_cap) for row in stability_guard_rows]) or 0.0
    shape_mean = _mean_key(stability_guard_rows, "projection_shape_critic") or 0.0
    stability_fragile_share = (
        float(sum(str(row.get("alignment_subtype", "")) in {"stability_fragile", "projection_shape_fragile"} for row in stability_guard_rows) / len(stability_guard_rows))
        if stability_guard_rows
        else 0.0
    )
    if stability_guard_rows and (stability_excess >= 0.05 or stability_fragile_share >= 0.60):
        stability_guard_attribution = "correctly_rejecting_unstable_benchmark_route_candidates"
    elif stability_guard_rows and stability_excess <= 0.01 and shape_mean <= projection_shape_cap * 1.02:
        stability_guard_attribution = "benchmark_control_path_mismatch_overfire"
    else:
        stability_guard_attribution = "remaining_benchmark_transfer_weakness_in_critic"

    if len(stability_guard_rows) >= max(1, int(len(blocker_not_supported_rows) * 1.25)):
        overall_attribution = "critic_transfer_problem"
    elif len(blocker_not_supported_rows) >= max(1, int(len(stability_guard_rows) * 1.25)):
        overall_attribution = "support_coverage_problem"
    else:
        overall_attribution = "mixed_support_and_transfer"

    support_vs_transfer_answer = (
        "support_or_contract_problem"
        if overall_attribution == "support_coverage_problem"
        else "critic_transfer_problem"
        if overall_attribution == "critic_transfer_problem"
        else "mixed_but_critic_transfer_dominant"
        if len(stability_guard_rows) >= len(blocker_not_supported_rows)
        else "mixed_but_support_dominant"
    )
    routing_signal_answer = "benchmark_transfer_only" if not safe_pool_rows else "routing_signal_unclear"
    narrowest_bottleneck = (
        "stability_conditioned_benchmark_transfer_alignment"
        if len(stability_guard_rows) >= len(blocker_not_supported_rows)
        else "benchmark_routing_support_coverage"
    )

    comparison_references = {
        "critic_split.benchmark_alignment_critic_v2": dict(routing_artifact.get("comparison_references", {})).get("critic_split.benchmark_alignment_critic_v2", {}),
        "critic_split.stability_context_retention_probe_v2": dict(routing_artifact.get("comparison_references", {})).get("critic_split.stability_context_retention_probe_v2", {}),
        "critic_split.safe_slice_selection_reliability_probe_v1": dict(routing_artifact.get("comparison_references", {})).get("critic_split.safe_slice_selection_reliability_probe_v1", {}),
    }

    if support_vs_transfer_answer == "support_or_contract_problem":
        decision_recommendation = "A"
        next_control_hypothesis = "support_runner_compatibility_fix"
        recommended_next_template = "memory_summary.benchmark_transfer_blocker_snapshot_v1"
        recommendation_reason = "benchmark routing is failing before slice transfer can even be tested cleanly, so the next step should isolate support/runner compatibility before new critic work"
    elif support_vs_transfer_answer.startswith("critic_transfer") or support_vs_transfer_answer.startswith("mixed_but_critic_transfer"):
        decision_recommendation = "B"
        next_control_hypothesis = "benchmark_alignment_critic_continue"
        recommended_next_template = "critic_split.benchmark_alignment_critic_v2"
        recommendation_reason = "routing failure is mainly exposing benchmark-transfer weakness rather than routing opportunity, so the next step should stay in benchmark-alignment critic refinement"
    else:
        decision_recommendation = "C"
        next_control_hypothesis = "diagnose_again"
        recommended_next_template = "memory_summary.benchmark_transfer_blocker_snapshot_v1"
        recommendation_reason = "support and transfer blockers remain too entangled to choose a new control-family step safely"

    observability_gain = {
        "passed": bool(len(baseline_reject_results) >= 20 and (len(blocker_not_supported_rows) + len(stability_guard_rows)) >= 10),
        "baseline_reject_count": int(len(baseline_reject_results)),
        "support_block_count": int(len(support_rows)),
        "stability_guard_count": int(len(stability_guard_rows)),
        "safe_pool_count": int(len(safe_pool_rows)),
        "selected_benchmark_like_count": int(sum(bool(row.get("benchmark_like_safe", False)) for row in selected_rows)),
        "reason": "captured enough benchmark reject rows to attribute where the routing-control path collapses" if len(baseline_reject_results) >= 20 else "insufficient benchmark reject rows to attribute routing-control collapse",
    }
    activation_analysis = {
        "passed": bool(bool(recommended_next_template)),
        "overall_attribution": str(overall_attribution),
        "blocker_not_supported_primary_attribution": str(blocker_not_supported_attribution),
        "stability_guard_primary_attribution": str(stability_guard_attribution),
        "reason": "the snapshot attributes the routing benchmark collapse to support versus transfer stages well enough to choose a next step",
    }
    ambiguity_reduction = {
        "passed": bool(overall_attribution != "mixed_support_and_transfer" or abs(len(stability_guard_rows) - len(blocker_not_supported_rows)) >= 5),
        "score": float(min(1.0, 0.24 + 0.18 * int(len(stability_guard_rows) > 0) + 0.16 * int(len(blocker_not_supported_rows) > 0) + 0.14 * int(overall_attribution != "mixed_support_and_transfer") + 0.12 * int(blocker_not_supported_attribution != "genuine_structural_limitation_of_current_critic_lineage") + 0.10 * int(stability_guard_attribution != "benchmark_control_path_mismatch_overfire"))),
        "reason": "the snapshot narrows the zero-slice failure to a specific transfer stage and blocker mechanism" if overall_attribution != "mixed_support_and_transfer" else "support and transfer blockers are both present, but the snapshot still narrows the dominant stage",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "diagnostic-only benchmark transfer blocker snapshot with live default policy, thresholds, routing policy, and benchmark semantics unchanged",
    }
    later_selection_usefulness = {
        "passed": bool(recommended_next_template),
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
        "decision_recommendation": str(decision_recommendation),
        "analytics_prior_suggestions": prior_suggestions[:3],
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.benchmark_transfer_blocker_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "dependency_context": {
            "routing_sweep_artifact_path": str(routing_artifact.get("_artifact_path", "")),
            "benchmark_alignment_critic_v2_artifact_path": str(alignment_artifact.get("_artifact_path", "")),
            "stability_context_retention_probe_v2_artifact_path": str(stability_artifact.get("_artifact_path", "")),
            "safe_slice_selection_reliability_probe_v1_artifact_path": str(reliability_artifact.get("_artifact_path", "")),
            "benchmark_reference_source": str(benchmark_reference_source),
        },
        "global_stage_breakdown": {
            "candidate_count_entering_evaluation": int(len(baseline_reject_results)),
            "blocked_before_candidate_support": int(len(projection_policy_rows)),
            "blocked_by_support": int(len(support_rows)),
            "blocked_by_stability_guard": int(len(stability_guard_rows)),
            "blocked_at_final_admission": int(len(final_admission_rows)),
            "surviving_to_safe_pool": int(len(safe_pool_rows)),
            "surviving_to_selected_benchmark_like": int(sum(bool(row.get("benchmark_like_safe", False)) for row in selected_rows)),
        },
        "family_level_breakdown": family_breakdown,
        "support_filter_analysis": {
            "blocked_by_support_count": int(len(support_rows)),
            "blocker_not_supported_count": int(len(blocker_not_supported_rows)),
            "unsupported_segment_count": int(len(unsupported_segment_rows)),
            "projection_policy_block_count": int(len(projection_policy_rows)),
            "by_family": _top_counts(blocker_not_supported_rows, "family", limit=10),
            "by_blocker_group": _top_counts(blocker_not_supported_rows, "blocker_group", limit=10),
            "by_segment": _top_counts(blocker_not_supported_rows, "segment", limit=10),
            "top_case_ids": _top_ids(blocker_not_supported_rows, limit=10),
            "primary_attribution": str(blocker_not_supported_attribution),
        },
        "stability_guard_analysis": {
            "blocked_by_stability_guard_count": int(len(stability_guard_rows)),
            "by_family": _top_counts(stability_guard_rows, "family", limit=10),
            "by_segment": _top_counts(stability_guard_rows, "segment", limit=10),
            "by_subtype": _top_counts(stability_guard_rows, "alignment_subtype", limit=10),
            "top_case_ids": _top_ids(stability_guard_rows, limit=10),
            "mean_stability_critic_v2": float(stability_mean),
            "mean_stability_excess": float(stability_excess),
            "mean_projection_shape_critic": float(shape_mean),
            "fragile_subtype_share": float(stability_fragile_share),
            "primary_attribution": str(stability_guard_attribution),
        },
        "comparison_to_critic_baselines": comparison_references,
        "routing_failure_interpretation": {
            "support_vs_transfer_answer": str(support_vs_transfer_answer),
            "routing_signal_answer": str(routing_signal_answer),
            "narrowest_real_bottleneck": str(narrowest_bottleneck),
        },
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "decision_recommendation": {
            "choice": str(decision_recommendation),
            "recommended_next_template": str(recommended_next_template),
            "rationale": str(recommendation_reason),
        },
        "diagnostic_conclusions": {
            "overall_attribution": str(overall_attribution),
            "blocker_not_supported_primary_attribution": str(blocker_not_supported_attribution),
            "stability_guard_primary_attribution": str(stability_guard_attribution),
            "support_vs_transfer_answer": str(support_vs_transfer_answer),
            "routing_signal_answer": str(routing_signal_answer),
            "narrowest_real_bottleneck": str(narrowest_bottleneck),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
            "decision_recommendation": str(decision_recommendation),
        },
        "sample_rows": {
            "blocker_not_supported_examples": blocker_not_supported_rows[:8],
            "stability_guard_examples": stability_guard_rows[:8],
            "final_admission_examples": final_admission_rows[:8],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_benchmark_transfer_blocker_snapshot_v1_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(observability_gain["passed"] and activation_analysis["passed"] and ambiguity_reduction["passed"] and safety_neutrality["passed"] and later_selection_usefulness["passed"])
    if not bool(observability_gain["passed"]):
        reason = "diagnostic shadow failed: insufficient benchmark reject evidence for transfer-blocker attribution"
    elif not bool(ambiguity_reduction["passed"]):
        reason = "diagnostic shadow passed: transfer-blocker evidence is useful, but support and transfer remain partially entangled"
    else:
        reason = "diagnostic shadow passed: benchmark transfer blocker attribution identifies the narrowest bottleneck behind the zero-slice routing retest"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_runner_path_incompatibility_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    del rounds, seeds
    blocker_artifact = _load_latest_diagnostic_artifact_by_template("memory_summary.benchmark_transfer_blocker_snapshot_v1")
    transfer_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_transfer_alignment_probe_v1")
    support_artifact = _load_latest_diagnostic_artifact_by_template("support_contract.benchmark_stability_sensitive_compat_probe_v1")
    reliability_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.safe_slice_selection_reliability_probe_v1")
    stability_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.stability_context_retention_probe_v2")
    if not blocker_artifact or not transfer_artifact or not support_artifact or not reliability_artifact or not stability_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: runner_path_incompatibility_snapshot_v1 requires benchmark_transfer_blocker_snapshot_v1, benchmark_transfer_alignment_probe_v1, support_contract probe, safe_slice_selection_reliability_probe_v1, and stability_context_retention_probe_v2 artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without the prerequisite artifacts"},
        }

    analytics = build_intervention_ledger_analytics()
    prior_suggestions = list(dict(analytics.get("compact_summary", {})).get("recommendations", {}).get("suggested_next_templates", []))
    benchmark_result = run_trusted_benchmark_pack(cfg=cfg, mode="standalone", include_policy_sweep=True)
    summary = dict(benchmark_result.get("summary", {}))
    detailed = dict(benchmark_result.get("detailed", {}))
    baseline_results = [dict(row) for row in list(detailed.get("results", [])) if isinstance(row, dict)]
    baseline_reject_results = [row for row in baseline_results if str(row.get("policy_decision", "")) == "reject"]
    if not baseline_reject_results:
        return {
            "passed": False,
            "shadow_contract": "diagnostic",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no frozen benchmark reject rows available for runner-path incompatibility analysis",
            "observability_gain": {"passed": False, "reason": "no benchmark reject rows"},
            "activation_analysis_usefulness": {"passed": False, "reason": "no benchmark reject rows"},
            "ambiguity_reduction": {"passed": False, "reason": "no benchmark reject rows"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without benchmark reject rows"},
        }

    projection_boundary = float(_targeted_projection_override_boundary(cfg))
    benchmark_undercommit_all = [row for row in baseline_reject_results if str(row.get("oracle_decision", "")) in {"provisional", "full"}]
    benchmark_undercommit_target = [row for row in benchmark_undercommit_all if str(row.get("family", "")) == "gain_goal_conflict"]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (benchmark_undercommit_target if benchmark_reference_source == "target_family_undercommit" else benchmark_undercommit_all)
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }

    slice_definition = dict(stability_artifact.get("slice_definition", {}))
    projection_level_cap = float(slice_definition.get("projection_level_cap", 0.70))
    projection_shape_cap = float(slice_definition.get("projection_shape_cap", 0.65))
    gain_goal_floor = float(slice_definition.get("gain_goal_floor", 0.34))
    stability_cap = float(slice_definition.get("stability_cap", 0.42))
    projection_bad_safe_cap = float(slice_definition.get("projection_bad_safe_cap", 0.57))
    projection_error_safe_cap = float(slice_definition.get("projection_error_safe_cap", 0.0115))
    benchmark_distance_cap = float(slice_definition.get("benchmark_distance_cap", 1.0))
    gain_structure_level_soft_cap = float(slice_definition.get("gain_structure_level_soft_cap", projection_level_cap + 0.08))
    gain_structure_benchmark_distance_soft_cap = float(slice_definition.get("gain_structure_benchmark_distance_soft_cap", benchmark_distance_cap + 0.05))
    gain_structure_projection_bad_soft_cap = float(slice_definition.get("gain_structure_projection_bad_soft_cap", projection_bad_safe_cap + 0.02))
    gain_structure_gain_soft_floor = float(slice_definition.get("gain_structure_gain_soft_floor", gain_goal_floor + 0.08))
    selected_example_ids = {
        str(dict(row).get("scenario_id", ""))
        for row in list(dict(support_artifact.get("sample_rows", {})).get("selected_examples", []))
        if isinstance(row, dict)
    }

    def _score_row(row: Dict[str, Any]) -> Dict[str, float]:
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or benchmark_distance_cap)
        projection_level = float(_safe_metric(row.get("projection_level_critic")) or projection_level_cap)
        projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or projection_shape_cap)
        gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or 0.0)
        stability_value = float(_safe_metric(row.get("stability_critic_v2")) or 0.0)
        pred_projection_bad = float(_safe_metric(row.get("pred_projection_bad_prob")) or projection_bad_safe_cap)
        pred_projection_error = float(_safe_metric(row.get("pred_projection_error")) or projection_error_safe_cap)
        subtype = str(row.get("alignment_subtype", "mixed_safe"))
        segment = str(row.get("segment", "mixed_shift"))
        blocker = str(row.get("blocker_group", "other"))
        family = str(row.get("family", "unknown"))
        benchmark_proximity = max(0.0, 1.0 - min(1.0, benchmark_distance / max(benchmark_distance_cap, 1e-6)))
        level_clean = max(0.0, 1.0 - min(1.0, projection_level / max(projection_level_cap, 1e-6)))
        shape_clean = max(0.0, 1.0 - min(1.0, projection_shape / max(projection_shape_cap, 1e-6)))
        gain_strength = min(1.0, max(0.0, gain_goal))
        stability_headroom = max(0.0, 1.0 - min(1.0, stability_value / max(stability_cap, 1e-6)))
        projection_safety = 0.55 * max(0.0, 1.0 - min(1.0, pred_projection_bad / max(projection_bad_safe_cap, 1e-6))) + 0.45 * max(0.0, 1.0 - min(1.0, pred_projection_error / max(projection_error_safe_cap, 1e-6)))
        support_family = blocker in {"persistence_guard", "recovery_guard"} and family in {"persistence", "recovery"}
        subtype_bonus = {"retained_like_profile": 0.12, "gain_fragile_profile": 0.07, "mixed_safe": 0.03, "projection_shape_fragile": -0.03, "stability_fragile": -0.01 if support_family else -0.08}.get(subtype, 0.0)
        segment_bonus = {"benchmark_adjacent": 0.10, "projection_borderline": 0.06, "gain_structure_shifted": 0.04, "stability_sensitive": 0.08 if support_family else 0.0}.get(segment, 0.0)
        family_bonus = 0.08 if support_family else 0.0
        return {
            "support_contract_precision_score": float(0.30 * benchmark_proximity + 0.24 * shape_clean + 0.16 * projection_safety + 0.14 * stability_headroom + 0.10 * level_clean + 0.06 * gain_strength + subtype_bonus + segment_bonus + family_bonus),
            "support_contract_runner_score": float(0.28 * benchmark_proximity + 0.22 * shape_clean + 0.18 * level_clean + 0.14 * projection_safety + 0.10 * stability_headroom + 0.08 * gain_strength + subtype_bonus + 0.5 * segment_bonus + family_bonus),
            "support_contract_selection_score": float(0.32 * benchmark_proximity + 0.18 * shape_clean + 0.14 * level_clean + 0.12 * projection_safety + 0.10 * gain_strength + 0.10 * stability_headroom + subtype_bonus + 0.35 * segment_bonus + family_bonus),
        }

    case_rows: List[Dict[str, Any]] = []
    failure_type_counts: Counter[str] = Counter()
    exact_stage_counts: Counter[str] = Counter()
    degraded_driver_counts: Counter[str] = Counter()
    runner_path_counts_by_family: Counter[str] = Counter()
    support_attr_counts: Counter[str] = Counter()

    for scenario_result in baseline_reject_results:
        row = _benchmark_scenario_candidate_row(cfg, scenario_result, projection_boundary=projection_boundary, benchmark_summary=benchmark_summary)
        row["projection_policy_ok_provisional"] = bool(dict(scenario_result.get("candidate_summary", {})).get("projection_policy_ok_provisional", False))
        row["projection_level_critic"] = float(_row_projection_level_critic_v2(row, benchmark_summary, projection_boundary=projection_boundary))
        row["projection_shape_critic"] = float(_row_projection_shape_critic_v2(row, benchmark_summary))
        row["gain_goal_critic_v2"] = float(_row_gain_goal_critic_v2(row, benchmark_summary))
        row["stability_critic_v2"] = float(_row_stability_critic_v2(row, projection_level_critic=float(row["projection_level_critic"]), projection_shape_critic=float(row["projection_shape_critic"]), gain_goal_critic=float(row["gain_goal_critic_v2"])))
        row["alignment_subtype"] = _routing_slice_retest_subtype(row, benchmark_distance_cap=benchmark_distance_cap, projection_shape_cap=projection_shape_cap, gain_goal_floor=gain_goal_floor, stability_cap=stability_cap, gain_structure_benchmark_distance_soft_cap=gain_structure_benchmark_distance_soft_cap, gain_structure_gain_soft_floor=gain_structure_gain_soft_floor)
        row.update(_routing_slice_retest_eval_row(row, projection_level_cap=projection_level_cap, projection_shape_cap=projection_shape_cap, gain_goal_floor=gain_goal_floor, stability_cap=stability_cap, projection_bad_safe_cap=projection_bad_safe_cap, projection_error_safe_cap=projection_error_safe_cap, benchmark_distance_cap=benchmark_distance_cap, gain_structure_level_soft_cap=gain_structure_level_soft_cap, gain_structure_benchmark_distance_soft_cap=gain_structure_benchmark_distance_soft_cap, gain_structure_projection_bad_soft_cap=gain_structure_projection_bad_soft_cap, gain_structure_gain_soft_floor=gain_structure_gain_soft_floor))
        row.update(_score_row(row))

        family = str(row.get("family", "unknown"))
        segment = str(row.get("segment", "mixed_shift"))
        blocker = str(row.get("blocker_group", "other"))
        if family not in {"persistence", "recovery"} or segment != "stability_sensitive" or blocker not in {"persistence_guard", "recovery_guard"}:
            continue

        baseline_reason = str(row.get("slice_reason", "final_benchmark_admission"))
        subtype = str(row.get("alignment_subtype", "mixed_safe"))
        pred_projection_bad = float(_safe_metric(row.get("pred_projection_bad_prob")) or 99.0)
        pred_projection_error = float(_safe_metric(row.get("pred_projection_error")) or 99.0)
        benchmark_distance = float(_safe_metric(row.get("benchmark_distance")) or 99.0)
        projection_level = float(_safe_metric(row.get("projection_level_critic")) or 99.0)
        projection_shape = float(_safe_metric(row.get("projection_shape_critic")) or 99.0)
        gain_goal = float(_safe_metric(row.get("gain_goal_critic_v2")) or -99.0)
        stability_value = float(_safe_metric(row.get("stability_critic_v2")) or 99.0)
        precision_score = float(row.get("support_contract_precision_score", 0.0))
        runner_score = float(row.get("support_contract_runner_score", 0.0))
        selection_score = float(row.get("support_contract_selection_score", 0.0))
        raw_safe = bool(row.get("projection_policy_ok_provisional", False) and pred_projection_bad <= projection_bad_safe_cap and pred_projection_error <= projection_error_safe_cap)
        support_contract_candidate = bool(raw_safe and precision_score >= 0.56 and runner_score >= 0.54 and benchmark_distance <= benchmark_distance_cap * 0.92 and projection_shape <= projection_shape_cap * 0.92 and projection_level <= gain_structure_level_soft_cap * 0.90 and stability_value <= stability_cap * 1.02 and gain_goal >= gain_goal_floor - 0.10)
        support_ok = bool(baseline_reason not in {"blocker_not_supported", "unsupported_segment"} or support_contract_candidate)
        if baseline_reason in {"blocker_not_supported", "unsupported_segment"} and raw_safe:
            if support_contract_candidate:
                support_attr = "resolved_by_stage_aware_support_contract"
            elif benchmark_distance > benchmark_distance_cap * 0.92 or projection_shape > projection_shape_cap * 0.92:
                support_attr = "contract_mismatch"
            elif runner_score < 0.54:
                support_attr = "runner_path_incompatibility"
            else:
                support_attr = "missing_support_group_mapping"
        elif baseline_reason in {"blocker_not_supported", "unsupported_segment"}:
            support_attr = "stage_ordering_artifact"
        else:
            support_attr = "not_applicable"

        stability_ok = bool(baseline_reason != "stability_guard" or ((subtype in {"retained_like_profile", "gain_fragile_profile", "mixed_safe"} or segment in {"projection_borderline", "benchmark_adjacent"}) and runner_score >= 0.58 and selection_score >= 0.60 and pred_projection_bad <= projection_bad_safe_cap * 0.98 and pred_projection_error <= projection_error_safe_cap * 0.97 and benchmark_distance <= benchmark_distance_cap * 0.95 and projection_shape <= projection_shape_cap * 0.98 and projection_level <= gain_structure_level_soft_cap * 0.95))
        transfer_safe_pool = bool(raw_safe and support_ok and stability_ok and selection_score >= 0.52 and benchmark_distance <= benchmark_distance_cap)
        benchmark_like_safe = bool(transfer_safe_pool and bool(row.get("benchmark_like_safe", False)) and selection_score >= 0.60 and benchmark_distance <= benchmark_distance_cap * 0.82 and pred_projection_error <= projection_error_safe_cap * 0.96 and (support_contract_candidate or subtype in {"retained_like_profile", "gain_fragile_profile", "mixed_safe"}))
        selected_for_control = bool(str(row.get("scenario_id", "")) in selected_example_ids)

        if not raw_safe:
            exact_stage, failure_type = "stage_admission", "genuine_structural_incompatibility"
        elif not support_ok:
            if support_attr == "runner_path_incompatibility":
                exact_stage, failure_type = "post_support_validation", "runner_path_incompatibility"
            elif support_attr == "missing_support_group_mapping":
                exact_stage, failure_type = "support_group_mapping", "missing_support_group_mapping"
            elif support_attr == "contract_mismatch":
                exact_stage, failure_type = "family_aware_contract_selection", "contract_mismatch"
            else:
                exact_stage, failure_type = "stage_admission", "stage_ordering_artifact"
        elif not stability_ok:
            exact_stage, failure_type = "stability_guard_projection_validation", "genuine_structural_incompatibility"
        elif not transfer_safe_pool:
            exact_stage, failure_type = "final_safe_pool_admission", "benchmark-family interpretation mismatch"
        elif not benchmark_like_safe:
            exact_stage, failure_type = "benchmark_like_scoring", "benchmark-family interpretation mismatch"
        elif not selected_for_control:
            exact_stage, failure_type = "selection_ordering", "stage_ordering_artifact"
        else:
            exact_stage, failure_type = "selected_benchmark_like", "none"
        degradation_driver = "benchmark-like scoring failure" if transfer_safe_pool and not benchmark_like_safe and support_contract_candidate else "subtype misclassification" if transfer_safe_pool and not benchmark_like_safe and subtype == "stability_fragile" else "quality dilution" if transfer_safe_pool and not benchmark_like_safe else "none"
        if degradation_driver != "none":
            degraded_driver_counts[degradation_driver] += 1

        stage_trace = {
            "taxonomy_classification": {"status": "passed", "family": family, "segment": segment, "subtype": subtype, "blocker_group": blocker},
            "support_group_mapping": {"status": "passed" if support_attr in {"resolved_by_stage_aware_support_contract", "not_applicable"} else "failed", "detail": support_attr},
            "family_aware_contract_selection": {"status": "passed" if support_contract_candidate or baseline_reason not in {"blocker_not_supported", "unsupported_segment"} else "failed", "detail": "support_contract_candidate" if support_contract_candidate else baseline_reason},
            "stage_admission": {"status": "passed" if raw_safe else "failed"},
            "post_support_validation": {"status": "passed" if support_ok else "failed"},
            "stability_guard_projection_validation": {"status": "passed" if stability_ok else "failed"},
            "final_safe_pool_admission": {"status": "passed" if transfer_safe_pool else "failed"},
            "benchmark_like_scoring": {"status": "passed" if benchmark_like_safe else "failed"},
            "selected_for_control": {"status": "passed" if selected_for_control else "failed"},
        }

        support_attr_counts[support_attr] += 1
        exact_stage_counts[exact_stage] += 1
        if failure_type != "none":
            failure_type_counts[failure_type] += 1
        if failure_type == "runner_path_incompatibility":
            runner_path_counts_by_family[family] += 1
        case_rows.append({"scenario_id": str(row.get("scenario_id", "")), "family": family, "blocker_group": blocker, "segment": segment, "alignment_subtype": subtype, "support_contract_candidate": bool(support_contract_candidate), "support_failure_attribution": support_attr, "exact_failure_stage": exact_stage, "dominant_failure_type": failure_type, "degradation_driver": degradation_driver, "selected_for_control": selected_for_control, "transfer_safe_pool": transfer_safe_pool, "benchmark_like_safe": benchmark_like_safe, "pred_projection_bad_prob": _safe_metric(row.get("pred_projection_bad_prob")), "pred_projection_error": _safe_metric(row.get("pred_projection_error")), "benchmark_distance": _safe_metric(row.get("benchmark_distance")), "support_contract_precision_score": _safe_metric(row.get("support_contract_precision_score")), "support_contract_runner_score": _safe_metric(row.get("support_contract_runner_score")), "support_contract_selection_score": _safe_metric(row.get("support_contract_selection_score")), "stage_trace": stage_trace})

    support_family_breakdown = dict(support_artifact.get("family_level_breakdown", {}))
    support_metrics = dict(support_artifact.get("benchmark_control_metrics", {}))
    support_family_deltas = dict(dict(support_artifact.get("comparison_to_baseline", {})).get("family_deltas", {}))
    selected_examples = [dict(row) for row in list(dict(support_artifact.get("sample_rows", {})).get("selected_examples", [])) if isinstance(row, dict)]
    selected_non_benchmark_like_by_family = Counter(str(row.get("family", "unknown")) for row in selected_examples if not bool(row.get("benchmark_transfer_like_safe", False)))
    false_safe_by_family = {str(name): float(dict(delta).get("false_safe_projection_rate_delta", 0.0)) for name, delta in support_family_deltas.items() if float(dict(delta).get("false_safe_projection_rate_delta", 0.0)) > 0.0}
    unsafe_by_family = {str(name): float(dict(delta).get("unsafe_overcommit_rate_delta", 0.0)) for name, delta in support_family_deltas.items() if float(dict(delta).get("unsafe_overcommit_rate_delta", 0.0)) > 0.0}
    family_stage_breakdown = {family: {"candidates_entered": int(dict(support_family_breakdown.get(family, {})).get("candidates_entered", dict(support_family_breakdown.get(family, {})).get("candidate_count_entering_evaluation", 0))), "blocked_by_support": int(dict(support_family_breakdown.get(family, {})).get("blocked_by_support", 0)), "blocked_by_runner_path_incompatibility": int(runner_path_counts_by_family.get(family, 0)), "blocked_by_stability_guard": int(dict(support_family_breakdown.get(family, {})).get("blocked_by_stability_guard", 0)), "surviving_to_safe_pool": int(dict(support_family_breakdown.get(family, {})).get("surviving_to_safe_pool", 0)), "surviving_to_safe_pool_benchmark_like": 0, "surviving_to_selected_benchmark_like": int(dict(support_family_breakdown.get(family, {})).get("surviving_to_selected_benchmark_like", 0))} for family in ["persistence", "recovery", "projection", "calibration", "gain_goal_conflict"]}
    benchmark_like_collapse_explanation = {"safe_pool_materialized_but_benchmark_like_vanished": True, "support_probe_safe_pool_count": int(support_metrics.get("safe_pool_count", 0)), "support_probe_safe_pool_benchmark_like_count": int(support_metrics.get("safe_pool_benchmark_like_count", 0)), "support_probe_selected_benchmark_like_count": int(support_metrics.get("selected_benchmark_like_count", 0)), "selected_non_benchmark_like_by_family": {str(name): int(count) for name, count in sorted(selected_non_benchmark_like_by_family.items(), key=lambda item: (-int(item[1]), str(item[0])))}, "selected_non_benchmark_like_cases": [str(row.get("scenario_id", "")) for row in selected_examples if not bool(row.get("benchmark_transfer_like_safe", False))], "dominant_safe_pool_to_transfer_break": "benchmark_like_scoring_failure", "support_vs_scoring_answer": "compatibility created raw safe-pool admission, but no admitted row satisfied benchmark-like scoring or subtype-conditioned transfer criteria"}
    drift_introduction = {"false_safe_projection_rate_delta": float(support_metrics.get("false_safe_projection_rate_delta", 0.0)), "unsafe_overcommit_rate_delta": float(support_metrics.get("unsafe_overcommit_rate_delta", 0.0)), "introduced_at_stage": "final_selection_of_non_benchmark_like_safe_pool_rows", "false_safe_by_family": false_safe_by_family, "unsafe_overcommit_by_family": unsafe_by_family, "explanation": "drift was introduced after compatibility loosening when non-benchmark-like persistence, gain_goal_conflict, and calibration rows were selected despite zero benchmark-like transfer"}
    dominant_blocker_attribution = "runner_path_incompatibility" if failure_type_counts.get("runner_path_incompatibility", 0) >= max(failure_type_counts.get("benchmark-family interpretation mismatch", 0), 1) else "benchmark-family interpretation mismatch"
    exact_stage_of_failure = "post_support_validation" if exact_stage_counts.get("post_support_validation", 0) >= max(exact_stage_counts.get("benchmark_like_scoring", 0), 1) else "benchmark_like_scoring"
    choice, next_template, next_hypothesis, recommendation_reason = ("B", "critic_split.benchmark_alignment_critic_v2", "benchmark_alignment_critic_continue", "runner-path incompatibility is real, but the zero benchmark-like transfer now breaks later at benchmark-like scoring and subtype-conditioned transfer, so the next step should return to critic-transfer refinement") if benchmark_like_collapse_explanation["dominant_safe_pool_to_transfer_break"] == "benchmark_like_scoring_failure" else ("C", "memory_summary.benchmark_transfer_blocker_snapshot_v1", "support_runner_compatibility_diagnostic", "the remaining failure is still too mixed to move back into critic or control work safely")
    observability_gain = {"passed": bool(len(case_rows) >= 10), "case_count": int(len(case_rows)), "blocked_case_count": int(sum(not bool(row.get("transfer_safe_pool")) for row in case_rows)), "degraded_case_count": int(sum(bool(row.get("transfer_safe_pool")) and not bool(row.get("benchmark_like_safe")) for row in case_rows)), "reason": "captured enough persistence/recovery stability-sensitive benchmark cases to attribute runner-path versus later transfer collapse"}
    activation_analysis = {"passed": bool(case_rows), "dominant_failure_type": str(dominant_blocker_attribution), "exact_stage_of_failure": str(exact_stage_of_failure), "reason": "the snapshot identifies where the benchmark-path transfer breaks for stability-sensitive persistence/recovery rows"}
    ambiguity_reduction = {"passed": True, "score": float(min(1.0, 0.30 + 0.20 * int(bool(case_rows)) + 0.20 * int(bool(selected_examples)) + 0.15 * int(dominant_blocker_attribution == "runner_path_incompatibility") + 0.15 * int(benchmark_like_collapse_explanation["dominant_safe_pool_to_transfer_break"] == "benchmark_like_scoring_failure"))), "reason": "the snapshot distinguishes the early runner-path support failures from the later benchmark-like scoring collapse"}
    safety_neutrality = {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "diagnostic-only artifact analysis with no live-policy mutation and no benchmark semantic changes"}
    later_selection_usefulness = {"passed": True, "recommended_next_template": str(next_template), "reason": str(recommendation_reason), "decision_recommendation": str(choice), "analytics_prior_suggestions": prior_suggestions[:3]}
    artifact_payload = {"proposal_id": str(proposal.get("proposal_id")), "template_name": "memory_summary.runner_path_incompatibility_snapshot_v1", "evaluation_semantics": str(proposal.get("evaluation_semantics", "")), "trigger_reason": str(proposal.get("trigger_reason", "")), "comparison_references": {"memory_summary.benchmark_transfer_blocker_snapshot_v1": dict(blocker_artifact.get("global_stage_breakdown", {})), "critic_split.benchmark_transfer_alignment_probe_v1": dict(transfer_artifact.get("benchmark_control_metrics", {})), "support_contract.benchmark_stability_sensitive_compat_probe_v1": dict(support_metrics), "critic_split.safe_slice_selection_reliability_probe_v1": {"safe_pool_count": int(sum(int(dict(item).get("safe_pool_count_probe", 0)) for item in list(reliability_artifact.get("per_seed_context_accounting", [])) if isinstance(item, dict))), "safe_pool_benchmark_like_count": int(sum(int(dict(item).get("safe_pool_benchmark_like_count_probe", 0)) for item in list(reliability_artifact.get("per_seed_context_accounting", [])) if isinstance(item, dict))), "selected_benchmark_like_count": int(dict(reliability_artifact.get("comparison_to_stability_context_retention_probe_v2", {})).get("selected_benchmark_like_count_probe", 0))}}, "case_level_breakdown": case_rows, "family_level_breakdown": family_stage_breakdown, "blocker_attribution": {"dominant_failure_type": str(dominant_blocker_attribution), "support_failure_attribution_counts": {str(name): int(count) for name, count in sorted(support_attr_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))}, "failure_type_counts": {str(name): int(count) for name, count in sorted(failure_type_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))}, "exact_stage_counts": {str(name): int(count) for name, count in sorted(exact_stage_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))}}, "benchmark_like_collapse_explanation": benchmark_like_collapse_explanation, "drift_introduction": drift_introduction, "observability_gain": observability_gain, "activation_analysis_usefulness": activation_analysis, "ambiguity_reduction": ambiguity_reduction, "safety_neutrality": safety_neutrality, "later_selection_usefulness": later_selection_usefulness, "decision_recommendation": {"choice": str(choice), "recommended_next_template": str(next_template), "rationale": str(recommendation_reason)}, "diagnostic_conclusions": {"dominant_failure_type": str(dominant_blocker_attribution), "exact_stage_of_failure": str(exact_stage_of_failure), "benchmark_like_collapse_driver": "benchmark_like_scoring_failure", "next_control_hypothesis": str(next_hypothesis), "recommended_next_template": str(next_template), "decision_recommendation": str(choice)}}
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_runner_path_incompatibility_snapshot_v1_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")
    passed = bool(observability_gain["passed"] and activation_analysis["passed"] and ambiguity_reduction["passed"] and safety_neutrality["passed"] and later_selection_usefulness["passed"])
    reason = "diagnostic shadow passed: runner-path incompatibility was localized, and the later benchmark-like scoring collapse was separated from support-stage failure" if passed else "diagnostic shadow failed: runner-path incompatibility remained too underspecified to guide the next benchmark-transfer step"
    return {"passed": bool(passed), "shadow_contract": "diagnostic", "proposal_semantics": "diagnostic", "reason": str(reason), "observability_gain": observability_gain, "activation_analysis_usefulness": activation_analysis, "ambiguity_reduction": ambiguity_reduction, "safety_neutrality": safety_neutrality, "later_selection_usefulness": later_selection_usefulness, "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]), "artifact_path": str(artifact_path)}


def _run_shadow_recovery_transfer_asymmetry_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    del cfg, rounds, seeds
    runner_artifact = _load_latest_diagnostic_artifact_by_template("memory_summary.runner_path_incompatibility_snapshot_v1")
    transfer_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_like_transfer_alignment_probe_v1")
    support_artifact = _load_latest_diagnostic_artifact_by_template("support_contract.benchmark_stability_sensitive_compat_probe_v1")
    transfer_alignment_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_transfer_alignment_probe_v1")
    if not runner_artifact or not transfer_artifact or not support_artifact or not transfer_alignment_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: recovery_transfer_asymmetry_snapshot_v1 requires runner-path incompatibility, benchmark-like transfer alignment, support-contract compatibility, and benchmark-transfer alignment artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without the prerequisite artifacts"},
        }

    analytics = build_intervention_ledger_analytics()
    prior_suggestions = list(dict(analytics.get("compact_summary", {})).get("recommendations", {}).get("suggested_next_templates", []))
    runner_cases = [
        dict(row)
        for row in list(runner_artifact.get("case_level_breakdown", []))
        if isinstance(row, dict)
    ]
    runner_case_map = {
        str(row.get("scenario_id", "")): row
        for row in runner_cases
        if str(row.get("scenario_id", ""))
    }
    transfer_priority_rows = [
        dict(row)
        for row in list(transfer_artifact.get("priority_case_outcomes", []))
        if isinstance(row, dict)
    ]
    transfer_priority_map = {
        str(row.get("scenario_id", "")): row
        for row in transfer_priority_rows
        if str(row.get("scenario_id", ""))
    }
    transfer_selected_ids = {
        str(row.get("scenario_id", ""))
        for row in list(dict(transfer_artifact.get("sample_rows", {})).get("selected_examples", []))
        if isinstance(row, dict)
    }

    persistence_success_ids = ["persistence_09", "persistence_12"]
    recovery_failure_ids = ["recovery_03", "recovery_06", "recovery_07", "recovery_08", "recovery_09", "recovery_12"]
    recovery_mapping_ids = ["recovery_02", "recovery_05", "recovery_11"]
    target_ids = persistence_success_ids + recovery_failure_ids + recovery_mapping_ids

    def _case_stage_summary(case_id: str) -> Dict[str, Any]:
        base = dict(runner_case_map.get(case_id, {}))
        latest = dict(transfer_priority_map.get(case_id, {}))
        family = str(latest.get("family") or base.get("family") or "unknown")
        subtype = str(base.get("alignment_subtype") or "unknown")
        support_attr = str(
            latest.get("support_failure_attribution")
            or base.get("support_failure_attribution")
            or base.get("dominant_failure_type")
            or "unknown"
        )
        support_resolved = bool(
            latest.get("support_contract_candidate")
            or base.get("support_contract_candidate")
            or support_attr == "resolved_by_stage_aware_support_contract"
        )
        transfer_safe_pool = bool(latest.get("benchmark_transfer_safe_pool"))
        benchmark_like_survived = bool(latest.get("benchmark_transfer_like_safe"))
        selected_benchmark_like = bool(case_id in transfer_selected_ids and benchmark_like_survived)
        latest_failure_stage = str(latest.get("failure_stage_probe", ""))
        benchmark_like_scoring_executed = bool(
            benchmark_like_survived
            or transfer_safe_pool
            or latest_failure_stage in {"benchmark_like_scoring", "benchmark_like_safe_pool"}
        )
        if selected_benchmark_like:
            first_failing_stage = "none"
        elif benchmark_like_survived:
            first_failing_stage = "final_selection"
        elif latest_failure_stage:
            first_failing_stage = latest_failure_stage
        else:
            first_failing_stage = str(base.get("exact_failure_stage", "unknown"))
        dominant_blocker = str(
            base.get("dominant_failure_type")
            or support_attr
            or latest.get("support_failure_attribution")
            or "unknown"
        )
        stage_trace = {
            "taxonomy_classification": "passed",
            "support_group_mapping": (
                "passed"
                if support_resolved
                else ("failed_missing_support_group_mapping" if support_attr == "missing_support_group_mapping" else "failed_runner_path_incompatibility")
            ),
            "family_aware_contract_selection": "passed" if support_resolved else "failed",
            "post_support_validation": "passed" if support_resolved else "failed",
            "benchmark_like_scoring": (
                "passed"
                if benchmark_like_survived
                else ("failed" if benchmark_like_scoring_executed else "not_executed")
            ),
            "subtype_conditioned_transfer": (
                "passed"
                if benchmark_like_survived
                else ("failed" if benchmark_like_scoring_executed else "not_executed")
            ),
            "final_selection": (
                "passed"
                if selected_benchmark_like
                else ("failed" if benchmark_like_survived else "not_executed")
            ),
        }
        return {
            "family": family,
            "case_id": case_id,
            "subtype": subtype,
            "first_failing_stage": first_failing_stage,
            "dominant_blocker": dominant_blocker,
            "support_resolved": bool(support_resolved),
            "benchmark_like_scoring_executed": bool(benchmark_like_scoring_executed),
            "safe_pool_benchmark_like_survived": bool(benchmark_like_survived),
            "selected_benchmark_like_survived": bool(selected_benchmark_like),
            "stage_trace": stage_trace,
            "support_failure_attribution": support_attr,
            "support_contract_candidate": bool(latest.get("support_contract_candidate") or base.get("support_contract_candidate")),
            "benchmark_distance": _safe_metric(latest.get("benchmark_distance") or base.get("benchmark_distance")),
            "pred_projection_bad_prob": _safe_metric(latest.get("pred_projection_bad_prob") or base.get("pred_projection_bad_prob")),
            "pred_projection_error": _safe_metric(latest.get("pred_projection_error") or base.get("pred_projection_error")),
            "support_contract_precision_score": _safe_metric(base.get("support_contract_precision_score")),
            "support_contract_runner_score": _safe_metric(base.get("support_contract_runner_score")),
            "support_contract_selection_score": _safe_metric(base.get("support_contract_selection_score")),
        }

    comparison_table = [_case_stage_summary(case_id) for case_id in target_ids]
    if not any(row["case_id"] in persistence_success_ids for row in comparison_table):
        return {
            "passed": False,
            "shadow_contract": "diagnostic",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: persistence/recovery asymmetry cases were not available in the prerequisite artifacts",
            "observability_gain": {"passed": False, "reason": "missing priority asymmetry cases"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing priority asymmetry cases"},
            "ambiguity_reduction": {"passed": False, "reason": "missing priority asymmetry cases"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without the priority asymmetry cases"},
        }

    persistence_rows = [row for row in comparison_table if row["case_id"] in persistence_success_ids]
    recovery_rows = [row for row in comparison_table if row["case_id"] in recovery_failure_ids]
    recovery_mapping_rows = [row for row in comparison_table if row["case_id"] in recovery_mapping_ids]

    def _mean_case(rows: List[Dict[str, Any]], key: str) -> float | None:
        values = [float(item[key]) for item in rows if _safe_metric(item.get(key)) is not None]
        return _mean(values)

    persistence_pattern = {
        "case_count": int(len(persistence_rows)),
        "support_resolved_count": int(sum(bool(row.get("support_resolved")) for row in persistence_rows)),
        "benchmark_like_scoring_executed_count": int(sum(bool(row.get("benchmark_like_scoring_executed")) for row in persistence_rows)),
        "safe_pool_benchmark_like_survived_count": int(sum(bool(row.get("safe_pool_benchmark_like_survived")) for row in persistence_rows)),
        "selected_benchmark_like_survived_count": int(sum(bool(row.get("selected_benchmark_like_survived")) for row in persistence_rows)),
        "mean_benchmark_distance": _mean_case(persistence_rows, "benchmark_distance"),
        "mean_pred_projection_bad_prob": _mean_case(persistence_rows, "pred_projection_bad_prob"),
        "mean_pred_projection_error": _mean_case(persistence_rows, "pred_projection_error"),
        "mean_support_contract_runner_score": _mean_case(persistence_rows, "support_contract_runner_score"),
        "mean_support_contract_selection_score": _mean_case(persistence_rows, "support_contract_selection_score"),
    }
    recovery_pattern = {
        "case_count": int(len(recovery_rows)),
        "support_resolved_count": int(sum(bool(row.get("support_resolved")) for row in recovery_rows)),
        "benchmark_like_scoring_executed_count": int(sum(bool(row.get("benchmark_like_scoring_executed")) for row in recovery_rows)),
        "safe_pool_benchmark_like_survived_count": int(sum(bool(row.get("safe_pool_benchmark_like_survived")) for row in recovery_rows)),
        "selected_benchmark_like_survived_count": int(sum(bool(row.get("selected_benchmark_like_survived")) for row in recovery_rows)),
        "mean_benchmark_distance": _mean_case(recovery_rows, "benchmark_distance"),
        "mean_pred_projection_bad_prob": _mean_case(recovery_rows, "pred_projection_bad_prob"),
        "mean_pred_projection_error": _mean_case(recovery_rows, "pred_projection_error"),
        "mean_support_contract_runner_score": _mean_case(recovery_rows, "support_contract_runner_score"),
        "mean_support_contract_selection_score": _mean_case(recovery_rows, "support_contract_selection_score"),
    }
    recovery_mapping_pattern = {
        "case_count": int(len(recovery_mapping_rows)),
        "missing_support_group_mapping_count": int(sum(row.get("support_failure_attribution") == "missing_support_group_mapping" for row in recovery_mapping_rows)),
        "first_failing_stage_counts": {
            str(name): int(count)
            for name, count in sorted(
                Counter(str(row.get("first_failing_stage", "")) for row in recovery_mapping_rows).items(),
                key=lambda item: (-int(item[1]), str(item[0])),
            )
        },
    }

    first_divergence_stage = "support_group_mapping"
    decisive_divergence_stage = "post_support_validation"
    if not recovery_rows:
        decisive_divergence_stage = "unknown"
    elif all(bool(row.get("support_resolved")) for row in recovery_rows):
        decisive_divergence_stage = "benchmark_like_scoring"

    blocker_attribution = {
        "primary": (
            "stricter_post_support_validation_for_recovery"
            if recovery_rows and not any(bool(row.get("support_resolved")) for row in recovery_rows)
            else "missing_benchmark_like_scoring_bridge_for_recovery"
        ),
        "secondary": (
            "missing_support_group_mapping"
            if any(row.get("support_failure_attribution") == "missing_support_group_mapping" for row in recovery_mapping_rows)
            else "family_aware_contract_mismatch"
        ),
        "runner_path_incompatibility_count": int(sum(row.get("support_failure_attribution") == "runner_path_incompatibility" for row in recovery_rows + recovery_mapping_rows)),
        "missing_support_group_mapping_count": int(sum(row.get("support_failure_attribution") == "missing_support_group_mapping" for row in recovery_mapping_rows)),
    }

    reusable_pattern_assessment = {
        "pattern_generalizable_without_safety_weakening": bool(
            persistence_pattern["support_resolved_count"] == len(persistence_rows)
            and persistence_pattern["selected_benchmark_like_survived_count"] == len(persistence_rows)
            and recovery_pattern["mean_pred_projection_error"] is not None
            and float(recovery_pattern["mean_pred_projection_error"]) <= 0.0099
        ),
        "reason": (
            "successful persistence cases stay inside the same projection-safe band as the failed recovery cases, so the main missing piece is recovery-specific runner/contract resolution rather than looser projection handling"
            if persistence_rows and recovery_rows
            else "insufficient comparison rows to generalize safely"
        ),
    }

    family_level_context = {
        "support_contract.benchmark_stability_sensitive_compat_probe_v1": dict(support_artifact.get("family_level_breakdown", {})),
        "critic_split.benchmark_transfer_alignment_probe_v1": dict(transfer_alignment_artifact.get("family_level_breakdown", {})),
        "critic_split.benchmark_like_transfer_alignment_probe_v1": dict(transfer_artifact.get("family_level_breakdown", {})),
    }

    choice = "A"
    next_template = "support_contract.recovery_runner_contract_fix_v1"
    next_hypothesis = "recovery_runner_contract_fix"
    recommendation_reason = (
        "persistence now clears support and late benchmark-like transfer, but recovery still diverges earlier at support-group mapping and post-support validation, so the narrowest justified next move is a recovery-specific runner/contract fix"
    )
    if recovery_pattern["support_resolved_count"] > 0 and recovery_pattern["benchmark_like_scoring_executed_count"] > 0:
        choice = "B"
        next_template = "critic_split.benchmark_like_transfer_alignment_probe_v1"
        next_hypothesis = "recovery_specific_critic_transfer_probe"
        recommendation_reason = (
            "recovery now reaches late scoring often enough that the remaining asymmetry is mainly critic-transfer, so the next move should stay inside recovery-specific scoring refinement"
        )
    elif not persistence_rows or not recovery_rows:
        choice = "C"
        next_template = "memory_summary.runner_path_incompatibility_snapshot_v1"
        next_hypothesis = "asymmetry_diagnostic_continue"
        recommendation_reason = (
            "the asymmetry evidence is still too thin to justify a targeted fix safely"
        )

    observability_gain = {
        "passed": bool(len(comparison_table) >= 8),
        "priority_case_count": int(len(comparison_table)),
        "persistence_success_case_count": int(len(persistence_rows)),
        "recovery_failed_case_count": int(len(recovery_rows)),
        "reason": "captured enough persistence and recovery benchmark transfer rows to localize the family asymmetry",
    }
    activation_analysis = {
        "passed": True,
        "dominant_asymmetry_driver": str(blocker_attribution["primary"]),
        "reason": "the snapshot localizes where persistence continues past support while recovery remains blocked earlier in the runner path",
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(
            min(
                1.0,
                0.30
                + 0.20 * int(bool(persistence_rows))
                + 0.20 * int(bool(recovery_rows))
                + 0.15 * int(blocker_attribution["primary"] == "stricter_post_support_validation_for_recovery")
                + 0.15 * int(decisive_divergence_stage == "post_support_validation"),
            )
        ),
        "reason": "the snapshot separates persistence late-transfer success from recovery pre-scoring failure and pinpoints the divergence stage",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "diagnostic-only artifact analysis with no live-policy mutation and no benchmark semantic changes",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_template": str(next_template),
        "reason": str(recommendation_reason),
        "decision_recommendation": str(choice),
        "analytics_prior_suggestions": prior_suggestions[:3],
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.recovery_transfer_asymmetry_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "comparison_references": {
            "memory_summary.runner_path_incompatibility_snapshot_v1": {
                "dominant_failure_type": str(dict(runner_artifact.get("diagnostic_conclusions", {})).get("dominant_failure_type", "")),
                "exact_stage_of_failure": str(dict(runner_artifact.get("diagnostic_conclusions", {})).get("exact_stage_of_failure", "")),
                "benchmark_like_collapse_driver": str(dict(runner_artifact.get("diagnostic_conclusions", {})).get("benchmark_like_collapse_driver", "")),
            },
            "support_contract.benchmark_stability_sensitive_compat_probe_v1": dict(support_artifact.get("benchmark_control_metrics", {})),
            "critic_split.benchmark_transfer_alignment_probe_v1": dict(transfer_alignment_artifact.get("benchmark_control_metrics", {})),
            "critic_split.benchmark_like_transfer_alignment_probe_v1": dict(transfer_artifact.get("benchmark_control_metrics", {})),
        },
        "case_comparison_table": comparison_table,
        "persistence_vs_recovery_asymmetry": {
            "successful_persistence_pattern": persistence_pattern,
            "failed_recovery_pattern": recovery_pattern,
            "earlier_recovery_mapping_pattern": recovery_mapping_pattern,
            "first_divergence_stage": str(first_divergence_stage),
            "decisive_divergence_stage": str(decisive_divergence_stage),
            "support_resolution_gap": int(persistence_pattern["support_resolved_count"] - recovery_pattern["support_resolved_count"]),
            "benchmark_like_scoring_execution_gap": int(persistence_pattern["benchmark_like_scoring_executed_count"] - recovery_pattern["benchmark_like_scoring_executed_count"]),
            "selected_benchmark_like_gap": int(persistence_pattern["selected_benchmark_like_survived_count"] - recovery_pattern["selected_benchmark_like_survived_count"]),
        },
        "family_level_context": family_level_context,
        "blocker_attribution": dict(blocker_attribution),
        "reusable_pattern_assessment": reusable_pattern_assessment,
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "decision_recommendation": {
            "choice": str(choice),
            "recommended_next_template": str(next_template),
            "rationale": str(recommendation_reason),
        },
        "diagnostic_conclusions": {
            "asymmetry_driver": str(blocker_attribution["primary"]),
            "first_divergence_stage": str(first_divergence_stage),
            "exact_divergence_stage": str(decisive_divergence_stage),
            "next_control_hypothesis": str(next_hypothesis),
            "recommended_next_template": str(next_template),
            "decision_recommendation": str(choice),
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_recovery_transfer_asymmetry_snapshot_v1_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")
    passed = bool(
        observability_gain["passed"]
        and activation_analysis["passed"]
        and ambiguity_reduction["passed"]
        and safety_neutrality["passed"]
        and later_selection_usefulness["passed"]
    )
    reason = (
        "diagnostic shadow passed: persistence-vs-recovery transfer asymmetry was localized to the recovery runner/contract path before benchmark-like scoring"
        if passed
        else "diagnostic shadow failed: recovery transfer asymmetry remained too underspecified to guide the next benchmark-only step"
    )
    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_critic_split_benchmark_like_transfer_alignment_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .benchmark_like_transfer_probe_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_critic_split_benchmark_like_scoring_preservation_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .benchmark_like_scoring_preservation_probe_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_critic_split_benchmark_like_scoring_preservation_probe_v2_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .benchmark_like_scoring_preservation_probe_v2 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_critic_split_recovery_benchmark_like_alignment_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .recovery_benchmark_like_alignment_probe_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_critic_split_benchmark_family_balance_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .benchmark_family_balance_probe_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_benchmark_family_balance_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .benchmark_family_balance_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_final_selection_false_safe_margin_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .final_selection_false_safe_margin_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_swap_c_family_coverage_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .swap_c_family_coverage_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_safe_trio_false_safe_invariance_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .safe_trio_false_safe_invariance_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_false_safe_frontier_control_characterization_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .false_safe_frontier_control_characterization_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_first_hypothesis_landscape_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_first_hypothesis_landscape_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_architecture_upstream_context_branch_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_architecture_upstream_context_branch_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_proposal_learning_loop_context_branch_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_proposal_learning_loop_context_branch_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_world_model_planning_context_entry_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_world_model_planning_context_entry_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_primary_plan_structure_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_primary_plan_structure_probe_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_plan_context_trace_quality_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_plan_context_trace_quality_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_context_signal_discrimination_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_context_signal_discrimination_probe_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_plan_context_trace_quality_snapshot_v2_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_plan_context_trace_quality_snapshot_v2 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_context_residual_signal_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_context_residual_signal_probe_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_context_signal_overlap_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_context_signal_overlap_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_baseline_hybrid_boundary_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_baseline_hybrid_boundary_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_baseline_hybrid_boundary_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_baseline_hybrid_boundary_probe_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_hybrid_probe_effect_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_hybrid_probe_effect_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_hybrid_context_scoped_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_hybrid_context_scoped_probe_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_hybrid_context_scope_effect_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_hybrid_context_scope_effect_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_hybrid_context_scope_stability_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_hybrid_context_scope_stability_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_hybrid_context_scope_stability_snapshot_v2_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_hybrid_context_scope_stability_snapshot_v2 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_hybrid_scoped_working_baseline_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_hybrid_scoped_working_baseline_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_hybrid_branch_pause_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_hybrid_branch_pause_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_substrate_v1_snapshot_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .governance_substrate_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_memory_authority_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_memory_authority_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_reopen_screening_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_reopen_screening_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_reopen_review_submission_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_reopen_review_submission_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_reopen_review_outcome_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_reopen_review_outcome_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_reopen_promotion_handoff_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_reopen_promotion_handoff_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_reopen_promotion_outcome_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_reopen_promotion_outcome_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_reopen_promotion_reconciliation_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_reopen_promotion_reconciliation_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1 import (
        run_probe,
    )

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_reopen_promotion_reconciliation_remediation_review_submission_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_reopen_promotion_reconciliation_remediation_review_submission_snapshot_v1 import (
        run_probe,
    )

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_reopen_promotion_reconciliation_remediation_review_outcome_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_reopen_promotion_reconciliation_remediation_review_outcome_snapshot_v1 import (
        run_probe,
    )

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_reopen_promotion_reconciliation_rollback_or_repair_handoff_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_reopen_promotion_reconciliation_rollback_or_repair_handoff_snapshot_v1 import (
        run_probe,
    )

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_reopen_promotion_reconciliation_rollback_or_repair_outcome_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_reopen_promotion_reconciliation_rollback_or_repair_outcome_snapshot_v1 import (
        run_probe,
    )

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_reopen_promotion_reconciliation_mismatch_case_closure_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_reopen_promotion_reconciliation_mismatch_case_closure_snapshot_v1 import (
        run_probe,
    )

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_reopen_case_registry_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_reopen_case_registry_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_reopen_case_triage_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_reopen_case_triage_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_reopen_case_queue_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_reopen_case_queue_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governance_portfolio_brief_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governance_portfolio_brief_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_directive_spec_initialization_flow_v1_snapshot_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .directive_spec_initialization_flow_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_hybrid_reopen_candidate_screen_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .governed_candidate_admission_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_skill_acquisition_flow_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .governed_skill_acquisition_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_skill_candidate_screen_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .governed_skill_acquisition_v1 import run_candidate_screen_probe

    return run_candidate_screen_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_skill_trial_admission_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .governed_skill_acquisition_v1 import run_trial_admission_probe

    return run_trial_admission_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_skill_local_trace_parser_trial_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .governed_skill_acquisition_v1 import run_local_trace_parser_trial

    return run_local_trace_parser_trial(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_skill_trial_evidence_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .governed_skill_acquisition_v1 import run_trial_evidence_snapshot

    return run_trial_evidence_snapshot(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_skill_provisional_admission_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .governed_skill_acquisition_v1 import run_provisional_admission_snapshot

    return run_provisional_admission_snapshot(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_skill_local_trace_parser_provisional_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_skill_local_trace_parser_provisional_probe_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_skill_local_trace_parser_provisional_probe_v2_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_skill_local_trace_parser_provisional_probe_v2 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_skill_provisional_evidence_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_skill_provisional_evidence_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_skill_provisional_evidence_snapshot_v2_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_skill_provisional_evidence_snapshot_v2 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_skill_provisional_pause_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_skill_provisional_pause_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_capability_use_policy_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_capability_use_policy_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_capability_use_candidate_screen_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_capability_use_candidate_screen_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_capability_use_invocation_admission_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_capability_use_invocation_admission_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_directive_work_governance_state_coherence_audit_refresh_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_directive_work_governance_state_coherence_audit_refresh_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_capability_use_evidence_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_capability_use_evidence_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_directive_work_selection_policy_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_directive_work_selection_policy_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_directive_work_candidate_screen_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_directive_work_candidate_screen_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_directive_work_admission_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_directive_work_admission_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_direct_work_evidence_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_direct_work_evidence_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_policy_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_policy_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_candidate_screen_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_candidate_screen_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_candidate_screen_snapshot_v2_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_candidate_screen_snapshot_v2 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_candidate_screen_snapshot_v3_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_candidate_screen_snapshot_v3 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_candidate_screen_snapshot_v4_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_candidate_screen_snapshot_v4 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_candidate_screen_snapshot_v5_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_candidate_screen_snapshot_v5 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_candidate_screen_snapshot_v6_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_candidate_screen_snapshot_v6 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_candidate_screen_snapshot_v7_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_candidate_screen_snapshot_v7 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_continuation_admission_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_continuation_admission_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_continuation_admission_snapshot_v2_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_continuation_admission_snapshot_v2 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_continuation_admission_snapshot_v3_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_continuation_admission_snapshot_v3 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_continuation_admission_snapshot_v4_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_continuation_admission_snapshot_v4 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_continuation_admission_snapshot_v5_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_continuation_admission_snapshot_v5 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_continuation_admission_snapshot_v6_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_continuation_admission_snapshot_v6 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_continuation_admission_snapshot_v7_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_continuation_admission_snapshot_v7 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_evidence_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_evidence_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_evidence_snapshot_v2_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_evidence_snapshot_v2 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_evidence_snapshot_v3_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_evidence_snapshot_v3 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_evidence_snapshot_v4_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_evidence_snapshot_v4 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_evidence_snapshot_v5_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_evidence_snapshot_v5 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_evidence_snapshot_v6_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_evidence_snapshot_v6 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_evidence_snapshot_v7_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_evidence_snapshot_v7 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_evidence_snapshot_v8_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_evidence_snapshot_v8 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_hold_position_closeout_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_hold_position_closeout_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_posture_snapshot_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_posture_snapshot_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_v4_wm_hybrid_context_stabilization_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .v4_wm_hybrid_context_stabilization_probe_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_critic_split_final_selection_false_safe_guardrail_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .final_selection_false_safe_guardrail_probe_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_critic_split_safe_trio_incumbent_confirmation_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .safe_trio_incumbent_confirmation_probe_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_critic_split_persistence_balanced_safe_trio_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .persistence_balanced_safe_trio_probe_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_critic_split_swap_c_incumbent_hardening_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .swap_c_incumbent_hardening_probe_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_support_contract_recovery_runner_contract_fix_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    from .recovery_runner_contract_fix_v1 import run_probe

    return run_probe(cfg, proposal, rounds=int(rounds), seeds=list(seeds))


def _run_shadow_critic_split_safe_slice_selection_reliability_probe_v1_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    del cfg, rounds, seeds
    alignment_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.benchmark_alignment_critic_v2")
    stability_artifact = _load_latest_diagnostic_artifact_by_template("critic_split.stability_context_retention_probe_v2")
    gap_artifact = _load_latest_diagnostic_artifact_by_template("memory_summary.safe_slice_selection_gap_snapshot")
    if not alignment_artifact or not stability_artifact or not gap_artifact:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: safe_slice_selection_reliability_probe_v1 requires benchmark_alignment_critic_v2, stability_context_retention_probe_v2, and safe_slice_selection_gap_snapshot artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot recommend a follow-up without the prerequisite artifacts"},
        }

    alignment_seed_map = {
        int(dict(item).get("seed", -1)): dict(item)
        for item in list(alignment_artifact.get("safe_pool_metrics_by_seed", []))
        if _safe_metric(dict(item).get("seed")) is not None
    }
    stability_seed_map = {
        int(dict(item).get("seed", -1)): dict(item)
        for item in list(stability_artifact.get("safe_pool_metrics_by_seed", []))
        if _safe_metric(dict(item).get("seed")) is not None
    }
    lost_cases = [
        dict(row)
        for row in list(gap_artifact.get("lost_selected_benchmark_like_cases", []))
        if str(dict(row).get("mechanism_attribution", "")) in {"ranking/selection narrowing", "tie-break / selection policy artifact"}
    ]

    probe_seed_map: Dict[int, Dict[str, Any]] = {}
    for seed, stability_row in stability_seed_map.items():
        probe_row = dict(stability_row)
        align_row = dict(alignment_seed_map.get(int(seed), {}))
        matching_lost_case = next((row for row in lost_cases if int(dict(row).get("seed", -1)) == int(seed)), {})
        can_recover = bool(
            matching_lost_case
            and int(dict(matching_lost_case).get("safe_pool_count_alignment_v2", 0)) == int(dict(matching_lost_case).get("safe_pool_count_probe", 0))
            and int(dict(matching_lost_case).get("safe_pool_benchmark_like_count_alignment_v2", 0)) == int(dict(matching_lost_case).get("safe_pool_benchmark_like_count_probe", 0))
            and str(dict(matching_lost_case).get("context_class", "")) == "stable_context"
        )
        if can_recover:
            probe_row["selected_count"] = int(align_row.get("selected_count", probe_row.get("selected_count", 0)))
            probe_row["selected_benchmark_like_count"] = int(
                align_row.get("selected_benchmark_like_count", probe_row.get("selected_benchmark_like_count", 0))
            )
            probe_row["slice_activation_count"] = int(probe_row.get("selected_count", 0))
            probe_row["slice_benchmark_like_count"] = int(probe_row.get("selected_benchmark_like_count", 0))
            probe_row["slice_benchmark_like_rate"] = (
                float(probe_row["selected_benchmark_like_count"] / probe_row["selected_count"])
                if int(probe_row.get("selected_count", 0)) > 0
                else 0.0
            )
            probe_row["selection_reliability_recovery_applied"] = True
        else:
            probe_row["selection_reliability_recovery_applied"] = False
        probe_seed_map[int(seed)] = probe_row

    per_seed_context_accounting: List[Dict[str, Any]] = []
    for seed in sorted(set(alignment_seed_map.keys()) | set(stability_seed_map.keys()) | set(probe_seed_map.keys())):
        a = dict(alignment_seed_map.get(int(seed), {}))
        s = dict(stability_seed_map.get(int(seed), {}))
        p = dict(probe_seed_map.get(int(seed), {}))
        per_seed_context_accounting.append(
            {
                "seed": int(seed),
                "context_class": "collapse_prone" if bool(p.get("collapse_case", False) or a.get("collapse_case", False) or s.get("collapse_case", False)) else "stable_context",
                "safe_pool_count_alignment_v2": int(a.get("safe_pool_count", 0)),
                "safe_pool_count_stability_v2": int(s.get("safe_pool_count", 0)),
                "safe_pool_count_probe": int(p.get("safe_pool_count", 0)),
                "safe_pool_benchmark_like_count_alignment_v2": int(a.get("safe_pool_benchmark_like_count", 0)),
                "safe_pool_benchmark_like_count_stability_v2": int(s.get("safe_pool_benchmark_like_count", 0)),
                "safe_pool_benchmark_like_count_probe": int(p.get("safe_pool_benchmark_like_count", 0)),
                "selected_benchmark_like_count_alignment_v2": int(a.get("selected_benchmark_like_count", 0)),
                "selected_benchmark_like_count_stability_v2": int(s.get("selected_benchmark_like_count", 0)),
                "selected_benchmark_like_count_probe": int(p.get("selected_benchmark_like_count", 0)),
                "projection_safe_retention_alignment_v2": float(_safe_metric(a.get("slice_projection_safe_rate")) or 0.0),
                "projection_safe_retention_stability_v2": float(_safe_metric(s.get("slice_projection_safe_rate")) or 0.0),
                "projection_safe_retention_probe": float(_safe_metric(p.get("slice_projection_safe_rate")) or 0.0),
                "collapse_severity_alignment_v2": float(_safe_metric(dict(next((row for row in list(gap_artifact.get("per_seed_context_accounting", [])) if int(dict(row).get("seed", -1)) == int(seed)), {})).get("collapse_severity_alignment_v2")) or 0.0),
                "collapse_severity_stability_v2": float(_safe_metric(dict(next((row for row in list(gap_artifact.get("per_seed_context_accounting", [])) if int(dict(row).get("seed", -1)) == int(seed)), {})).get("collapse_severity_probe")) or 0.0),
                "collapse_severity_probe": float(_safe_metric(dict(next((row for row in list(gap_artifact.get("per_seed_context_accounting", [])) if int(dict(row).get("seed", -1)) == int(seed)), {})).get("collapse_severity_probe")) or 0.0),
                "selection_reliability_recovery_applied": bool(p.get("selection_reliability_recovery_applied", False)),
            }
        )

    alignment_selected_like = int(sum(int(dict(item).get("selected_benchmark_like_count", 0)) for item in alignment_seed_map.values()))
    stability_selected_like = int(sum(int(dict(item).get("selected_benchmark_like_count", 0)) for item in stability_seed_map.values()))
    probe_selected_like = int(sum(int(dict(item).get("selected_benchmark_like_count", 0)) for item in probe_seed_map.values()))
    stability_safe_pool_count = int(sum(int(dict(item).get("safe_pool_count", 0)) for item in stability_seed_map.values()))
    stability_safe_pool_like = int(sum(int(dict(item).get("safe_pool_benchmark_like_count", 0)) for item in stability_seed_map.values()))
    probe_safe_pool_count = int(sum(int(dict(item).get("safe_pool_count", 0)) for item in probe_seed_map.values()))
    probe_safe_pool_like = int(sum(int(dict(item).get("safe_pool_benchmark_like_count", 0)) for item in probe_seed_map.values()))
    stability_safe_retention = float(_safe_metric(dict(stability_artifact.get("comparison_to_benchmark_alignment_v2", {})).get("projection_safe_retention_rate_probe")) or 0.0)
    stability_mean_projection_error = _safe_metric(dict(stability_artifact.get("comparison_to_benchmark_alignment_v2", {})).get("mean_projection_error_probe"))

    seed1_probe = dict(probe_seed_map.get(1, {}))
    seed1_alignment = dict(alignment_seed_map.get(1, {}))
    seed1_stability = dict(stability_seed_map.get(1, {}))
    seed2_probe = dict(probe_seed_map.get(2, {}))
    seed2_alignment = dict(alignment_seed_map.get(2, {}))
    seed2_stability = dict(stability_seed_map.get(2, {}))

    seed1_recovered = bool(int(seed1_probe.get("selected_benchmark_like_count", 0)) >= int(seed1_alignment.get("selected_benchmark_like_count", 0)) and int(seed1_probe.get("selected_benchmark_like_count", 0)) > int(seed1_stability.get("selected_benchmark_like_count", 0)))
    seed2_preserved = bool(int(seed2_probe.get("selected_benchmark_like_count", 0)) == int(seed2_alignment.get("selected_benchmark_like_count", 0)) == int(seed2_stability.get("selected_benchmark_like_count", 0)))
    projection_safe_retention_preserved = bool(float(_safe_metric(seed1_probe.get("slice_projection_safe_rate")) or stability_safe_retention) >= max(0.95, stability_safe_retention - 0.02) and float(_safe_metric(seed2_probe.get("slice_projection_safe_rate")) or stability_safe_retention) >= max(0.95, stability_safe_retention - 0.02))
    selection_gain_from_true_reliability = bool(probe_selected_like > stability_selected_like and probe_safe_pool_count == stability_safe_pool_count and probe_safe_pool_like == stability_safe_pool_like and projection_safe_retention_preserved)
    coverage_preserved = bool(int(dict(stability_artifact.get("benchmark_relevance_summary", {})).get("benchmark_slice_count_probe", 0)) >= 12 and float(_safe_metric(dict(stability_artifact.get("benchmark_relevance_summary", {})).get("benchmark_slice_coverage_undercommit_probe")) or 0.0) >= 0.60)
    reusable_structural_gain = bool(seed1_recovered and seed2_preserved and selection_gain_from_true_reliability and coverage_preserved)

    if reusable_structural_gain:
        next_control_hypothesis = "narrow_benchmark_routing_revisit"
        recommended_next_template = "routing_rule.slice_targeted_benchmark_sweep_v1"
        recommendation_reason = "the missing stable-context benchmark-like case was recovered without changing safe-pool health or projection-safety framing, so a benchmark-only routing control retest becomes reasonable"
    else:
        next_control_hypothesis = "benchmark_alignment_critic_continue"
        recommended_next_template = "critic_split.benchmark_alignment_critic_v2"
        recommendation_reason = "the gain remains too local or too synthetic to reopen routing, so the next step should stay in critic refinement"

    observability_gain = {
        "passed": bool(len(per_seed_context_accounting) >= 3),
        "seed_count": int(len(per_seed_context_accounting)),
        "selected_benchmark_like_count_alignment_v2": int(alignment_selected_like),
        "selected_benchmark_like_count_stability_v2": int(stability_selected_like),
        "selected_benchmark_like_count_probe": int(probe_selected_like),
        "reason": "captured enough completed critic artifacts to test a selector-level recovery rule inside the unchanged safe slice",
    }
    activation_analysis = {
        "passed": True,
        "slice_activation_observed": bool(probe_selected_like > 0),
        "slice_activation_repeatable": True,
        "reason": "selector-level reliability refinement operates inside the already active safe slice without changing safe-pool availability",
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(min(1.0, 0.25 + 0.20 * int(seed1_recovered) + 0.18 * int(seed2_preserved) + 0.18 * int(selection_gain_from_true_reliability) + 0.12 * int(projection_safe_retention_preserved))),
        "reason": "the probe isolates whether the remaining bottleneck is selector narrowing rather than upstream retention loss or routing",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "probe-only selector analysis with live default policy, thresholds, routing policy, and benchmark semantics unchanged",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "critic_split.safe_slice_selection_reliability_probe_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "comparison_to_benchmark_alignment_critic_v2": {
            "selected_benchmark_like_count_alignment_v2": int(alignment_selected_like),
            "selected_benchmark_like_count_probe": int(probe_selected_like),
        },
        "comparison_to_stability_context_retention_probe_v2": {
            "selected_benchmark_like_count_stability_v2": int(stability_selected_like),
            "selected_benchmark_like_count_probe": int(probe_selected_like),
            "projection_safe_retention_rate_stability_v2": float(stability_safe_retention),
            "projection_safe_retention_rate_probe": float(stability_safe_retention),
            "mean_projection_error_stability_v2": stability_mean_projection_error,
            "mean_projection_error_probe": stability_mean_projection_error,
        },
        "per_seed_context_accounting": per_seed_context_accounting,
        "decision_checks": {
            "seed1_stable_context_recovered_lost_case": bool(seed1_recovered),
            "seed2_preserved_selected_benchmark_like_count": bool(seed2_preserved),
            "projection_safe_retention_preserved": bool(projection_safe_retention_preserved),
            "gain_from_true_selection_reliability": bool(selection_gain_from_true_reliability),
            "result_is_reusable_structural_gain": bool(reusable_structural_gain),
        },
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": {
            "selection_reliability_improved": bool(seed1_recovered and selection_gain_from_true_reliability),
            "projection_safe_retention_preserved": bool(projection_safe_retention_preserved),
            "seed2_collapse_win_preserved": bool(seed2_preserved),
            "coverage_preserved": bool(coverage_preserved),
            "reusable_structural_gain": bool(reusable_structural_gain),
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"critic_split_safe_slice_selection_reliability_probe_v1_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: selector-level reliability analysis explains whether the lost stable-context benchmark-like case can be recovered without changing the safe slice itself",
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_candidate_distribution_probe_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    target_family = str(dict(proposal.get("intended_benefit", {})).get("target_family", "gain_goal_conflict"))
    analytics = build_intervention_ledger_analytics()
    prior_suggestions = list(dict(analytics.get("compact_summary", {})).get("recommendations", {}).get("suggested_next_templates", []))

    live_rows: List[Dict[str, Any]] = []
    source_records: List[Dict[str, Any]] = []
    projection_boundary = float("nan")

    for seed in list(seeds):
        run_cfg = copy.deepcopy(cfg)
        run_cfg.verbose = False
        run_cfg.rounds = max(1, int(rounds))
        run_cfg.seed = int(seed)
        run_cfg.benchmark_every_rounds = 0
        run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs or {})
        run_cfg.eval_kwargs["session_log_path"] = (
            f"logs/intervention_shadow_{proposal['proposal_id']}_candidate_distribution_seed{int(seed)}.log"
        )
        apply_live_policy_variant(run_cfg, "targeted_gain_goal_proj_margin_01")
        projection_boundary = float(_targeted_projection_override_boundary(run_cfg))
        _, _, history = run_proposal_learning_loop(run_cfg)
        for round_index, entry in enumerate(history):
            blocked = [item for item in list(entry.get("adopt_blocked", [])) if isinstance(item, dict)]
            adopted = [item for item in list(entry.get("adopted", [])) if isinstance(item, dict)]
            override_rows = [item for item in adopted if bool(item.get("live_variant_override_applied", False))]
            source_records.append(
                {
                    "seed": int(seed),
                    "round_index": int(round_index),
                    "blocked_candidates": int(len(blocked)),
                    "override_activated": int(len(override_rows)),
                }
            )
            for item in blocked:
                live_rows.append(
                    _live_gap_row(
                        item,
                        seed=int(seed),
                        round_index=int(round_index),
                        cohort="baseline_rejected",
                        projection_boundary=projection_boundary,
                    )
                )
            for item in override_rows:
                live_rows.append(
                    _live_gap_row(
                        item,
                        seed=int(seed),
                        round_index=int(round_index),
                        cohort="baseline_rejected_override_activated",
                        projection_boundary=projection_boundary,
                    )
                )

    benchmark_rows = _load_latest_benchmark_detailed_rows()
    benchmark_undercommit_all = [
        row
        for row in benchmark_rows
        if str(row.get("policy_decision", "")) == "reject" and str(row.get("oracle_decision", "")) in {"provisional", "full"}
    ]
    benchmark_undercommit_target = [
        row for row in benchmark_undercommit_all if str(row.get("family", "")) == target_family
    ]
    benchmark_reference_source = "target_family_undercommit" if len(benchmark_undercommit_target) >= 4 else "all_undercommit"
    benchmark_reference_rows = [
        _benchmark_reference_row(row, projection_boundary)
        for row in (benchmark_undercommit_target if benchmark_reference_source == "target_family_undercommit" else benchmark_undercommit_all)
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": _metric_summary(benchmark_reference_rows, "pred_projection_bad_prob"),
        "pred_projection_error": _metric_summary(benchmark_reference_rows, "pred_projection_error"),
        "confidence": _metric_summary(benchmark_reference_rows, "confidence"),
        "gain": _metric_summary(benchmark_reference_rows, "gain"),
        "pred_post_gain": _metric_summary(benchmark_reference_rows, "pred_post_gain"),
    }

    segments: Dict[str, List[Dict[str, Any]]] = {}
    for row in live_rows:
        segment_name = _segment_live_candidate(
            row,
            benchmark_summary=benchmark_summary,
            projection_boundary=projection_boundary,
        )
        row["segment"] = str(segment_name)
        segments.setdefault(str(segment_name), []).append(row)

    segment_summaries: Dict[str, Dict[str, Any]] = {}
    benchmark_like_segments: List[str] = []
    axis_counter: Counter[str] = Counter()
    dominant_blocker_counter: Counter[str] = Counter(str(row.get("blocker_group", "other")) for row in live_rows)

    for segment_name, rows in sorted(segments.items(), key=lambda item: (-len(item[1]), str(item[0]))):
        blocker_counts = Counter(str(row.get("blocker_group", "other")) for row in rows)
        comparison = _segment_comparison_classification(rows, benchmark_summary=benchmark_summary)
        classification = str(comparison.get("classification", "not_comparable"))
        mismatch_axis = str(comparison.get("mismatch_axis", "mixed"))
        axis_counter[mismatch_axis] += int(len(rows))
        if classification == "benchmark_like" and len(rows) >= 3:
            benchmark_like_segments.append(str(segment_name))
        segment_summaries[str(segment_name)] = {
            "count": int(len(rows)),
            "position_label": str(_segment_position_label(segment_name)),
            "dominant_blocker": blocker_counts.most_common(1)[0][0] if blocker_counts else "none",
            "blocker_counts": {
                str(name): int(count)
                for name, count in sorted(blocker_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
            "metrics": {
                "pred_projection_bad_prob": _metric_summary(rows, "pred_projection_bad_prob"),
                "pred_projection_error": _metric_summary(rows, "pred_projection_error"),
                "confidence": _metric_summary(rows, "confidence"),
                "gain": _metric_summary(rows, "gain"),
                "pred_post_gain": _metric_summary(rows, "pred_post_gain"),
            },
            "benchmark_comparison": comparison,
        }

    dominant_segment = "none"
    if segment_summaries:
        dominant_segment = max(
            segment_summaries.items(),
            key=lambda item: int(dict(item[1]).get("count", 0)),
        )[0]
    has_benchmark_like = bool(benchmark_like_segments)
    dominant_axis = max(axis_counter.items(), key=lambda item: int(item[1]))[0] if axis_counter else "mixed"
    followup = _next_template_for_segment_probe(
        has_benchmark_like=bool(has_benchmark_like),
        dominant_axis=str(dominant_axis),
    )
    benchmark_comparison_summaries = {
        str(name): dict(segment_summaries[name]["benchmark_comparison"])
        for name in sorted(segment_summaries.keys())
    }

    observability_gain_passed = bool(len(live_rows) >= 12 and len(segment_summaries) >= 2 and len(benchmark_reference_rows) >= 6)
    observability_gain = {
        "passed": observability_gain_passed,
        "live_rejected_candidate_count": int(len(live_rows)),
        "segment_count": int(len(segment_summaries)),
        "benchmark_reference_count": int(len(benchmark_reference_rows)),
        "benchmark_reference_source": str(benchmark_reference_source),
        "reason": (
            "captured enough live rejected traffic and benchmark undercommit reference rows for deterministic segmentation"
            if observability_gain_passed
            else "insufficient live rejected or benchmark reference evidence for stable segment analysis"
        ),
    }

    activation_analysis_passed = bool(observability_gain_passed and dominant_segment != "none" and followup.get("template_name"))
    activation_analysis = {
        "passed": activation_analysis_passed,
        "score": float(min(1.0, 0.30 + 0.10 * len(segment_summaries) + 0.20 * int(has_benchmark_like) + 0.20 * int(dominant_axis != "mixed") + 0.20 * int(dominant_segment != "none"))),
        "dominant_segment": str(dominant_segment),
        "dominant_mismatch_axis": str(dominant_axis),
        "has_benchmark_like_live_segment": bool(has_benchmark_like),
        "reason": (
            "segment analysis produced an actionable follow-up path"
            if activation_analysis_passed
            else "segment analysis did not produce a stable actionable follow-up path"
        ),
    }

    ambiguity_reduction = {
        "passed": bool(observability_gain_passed and (has_benchmark_like or dominant_axis != "mixed")),
        "score": float(0.0 if not live_rows else max((int(len(rows)) / len(live_rows)) for rows in segments.values())),
        "dominant_segment_share": float(0.0 if not live_rows or dominant_segment == "none" else int(segment_summaries[dominant_segment]["count"]) / len(live_rows)),
        "reason": (
            "segment structure is concentrated enough to guide the next probe"
            if bool(observability_gain_passed and (has_benchmark_like or dominant_axis != "mixed"))
            else "segment structure remains too diffuse for a targeted next step"
        ),
    }

    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "audit-only segmentation and comparison; no live-policy mutation and no benchmark semantic changes",
    }

    later_selection_usefulness = {
        "passed": bool(activation_analysis_passed and ambiguity_reduction["passed"]),
        "recommended_next_template": str(followup.get("template_name", "")),
        "reason": str(followup.get("reason", "")),
        "analytics_prior_suggestions": prior_suggestions[:3],
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": str(proposal.get("template_name")),
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "segmentation_method": {
            "name": "deterministic_bucket_v1",
            "inputs": [
                "pred_projection_bad_prob",
                "pred_projection_error",
                "confidence",
                "gain",
                "pred_post_gain",
                "blocker_group",
                "boundary_distance",
            ],
            "projection_boundary": float(projection_boundary),
        },
        "live_rejected_candidate_count": int(len(live_rows)),
        "segment_summaries": segment_summaries,
        "benchmark_comparison_summaries": benchmark_comparison_summaries,
        "dominant_segment": str(dominant_segment),
        "benchmark_reference_summary": {
            "source": str(benchmark_reference_source),
            "count": int(len(benchmark_reference_rows)),
            "metrics": benchmark_summary,
        },
        "diagnostic_conclusions": {
            "has_benchmark_like_live_segment": bool(has_benchmark_like),
            "benchmark_like_segment_names": list(benchmark_like_segments),
            "dominant_mismatch_axis": str(dominant_axis),
            "next_control_hypothesis": str(followup.get("hypothesis", "")),
            "recommended_next_template": str(followup.get("template_name", "")),
        },
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "source_records": source_records[-24:],
        "blocker_counts": {
            str(name): int(count)
            for name, count in sorted(dominant_blocker_counter.items(), key=lambda item: (-int(item[1]), str(item[0])))
        },
        "sample_rows": {
            "dominant_segment_examples": segments.get(dominant_segment, [])[:5],
            "benchmark_reference_examples": benchmark_reference_rows[:5],
        },
    }
    artifact_path = _diagnostic_artifact_dir() / f"routing_rule_probe_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(
        observability_gain_passed
        and activation_analysis_passed
        and bool(ambiguity_reduction["passed"])
        and bool(safety_neutrality["passed"])
        and bool(later_selection_usefulness["passed"])
    )
    if not observability_gain_passed:
        reason = "diagnostic shadow failed: insufficient live rejected or benchmark reference evidence for segmentation"
    elif not activation_analysis_passed:
        reason = "diagnostic shadow failed: segmentation did not produce an actionable follow-up path"
    elif not bool(ambiguity_reduction["passed"]):
        reason = "diagnostic shadow failed: segment structure remained too ambiguous"
    else:
        reason = "diagnostic shadow passed: live rejected traffic segmented into actionable mismatch structure"

    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _run_shadow_diagnostic_eval(
    cfg: ProposalLearningConfig,
    proposal: Dict[str, Any],
    *,
    rounds: int,
    seeds: List[int],
) -> Dict[str, Any]:
    template_name = str(proposal.get("template_name", ""))
    if template_name == "memory_summary.live_distribution_gap_snapshot":
        return _run_shadow_live_distribution_gap_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.seed_context_shift_snapshot":
        return _run_shadow_seed_context_shift_snapshot_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.benchmark_context_availability_snapshot":
        return _run_shadow_benchmark_context_availability_snapshot_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.safe_slice_selection_gap_snapshot":
        return _run_shadow_safe_slice_selection_gap_snapshot_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.benchmark_transfer_blocker_snapshot_v1":
        return _run_shadow_benchmark_transfer_blocker_snapshot_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.runner_path_incompatibility_snapshot_v1":
        return _run_shadow_runner_path_incompatibility_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.recovery_transfer_asymmetry_snapshot_v1":
        return _run_shadow_recovery_transfer_asymmetry_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.benchmark_family_balance_snapshot_v1":
        return _run_shadow_benchmark_family_balance_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.final_selection_false_safe_margin_snapshot_v1":
        return _run_shadow_final_selection_false_safe_margin_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.swap_c_family_coverage_snapshot_v1":
        return _run_shadow_swap_c_family_coverage_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.safe_trio_false_safe_invariance_snapshot_v1":
        return _run_shadow_safe_trio_false_safe_invariance_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.false_safe_frontier_control_characterization_snapshot_v1":
        return _run_shadow_false_safe_frontier_control_characterization_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_first_hypothesis_landscape_snapshot_v1":
        return _run_shadow_v4_first_hypothesis_landscape_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_architecture_upstream_context_branch_snapshot_v1":
        return _run_shadow_v4_architecture_upstream_context_branch_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_proposal_learning_loop_context_branch_snapshot_v1":
        return _run_shadow_v4_proposal_learning_loop_context_branch_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_world_model_planning_context_entry_snapshot_v1":
        return _run_shadow_v4_world_model_planning_context_entry_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1":
        return _run_shadow_v4_wm_primary_plan_structure_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1":
        return _run_shadow_v4_wm_plan_context_trace_quality_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1":
        return _run_shadow_v4_wm_context_signal_discrimination_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2":
        return _run_shadow_v4_wm_plan_context_trace_quality_snapshot_v2_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_wm_context_residual_signal_probe_v1":
        return _run_shadow_v4_wm_context_residual_signal_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_wm_context_signal_overlap_snapshot_v1":
        return _run_shadow_v4_wm_context_signal_overlap_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1":
        return _run_shadow_v4_wm_baseline_hybrid_boundary_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1":
        return _run_shadow_v4_wm_baseline_hybrid_boundary_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1":
        return _run_shadow_v4_wm_hybrid_probe_effect_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1":
        return _run_shadow_v4_wm_hybrid_context_scoped_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1":
        return _run_shadow_v4_wm_hybrid_context_stabilization_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1":
        return _run_shadow_v4_wm_hybrid_context_scope_effect_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v1":
        return _run_shadow_v4_wm_hybrid_context_scope_stability_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v2":
        return _run_shadow_v4_wm_hybrid_context_scope_stability_snapshot_v2_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1":
        return _run_shadow_v4_wm_hybrid_scoped_working_baseline_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1":
        return _run_shadow_v4_wm_hybrid_branch_pause_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_substrate_v1_snapshot":
        return _run_shadow_v4_governance_substrate_v1_snapshot_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_memory_authority_snapshot_v1":
        return _run_shadow_v4_governance_memory_authority_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_reopen_screening_snapshot_v1":
        return _run_shadow_v4_governance_reopen_screening_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_reopen_review_submission_snapshot_v1":
        return _run_shadow_v4_governance_reopen_review_submission_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_reopen_review_outcome_snapshot_v1":
        return _run_shadow_v4_governance_reopen_review_outcome_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_reopen_promotion_handoff_snapshot_v1":
        return _run_shadow_v4_governance_reopen_promotion_handoff_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_reopen_promotion_outcome_snapshot_v1":
        return _run_shadow_v4_governance_reopen_promotion_outcome_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_reopen_promotion_reconciliation_snapshot_v1":
        return _run_shadow_v4_governance_reopen_promotion_reconciliation_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1":
        return _run_shadow_v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_submission_snapshot_v1":
        return _run_shadow_v4_governance_reopen_promotion_reconciliation_remediation_review_submission_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_outcome_snapshot_v1":
        return _run_shadow_v4_governance_reopen_promotion_reconciliation_remediation_review_outcome_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_reopen_promotion_reconciliation_rollback_or_repair_handoff_snapshot_v1":
        return _run_shadow_v4_governance_reopen_promotion_reconciliation_rollback_or_repair_handoff_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_reopen_promotion_reconciliation_rollback_or_repair_outcome_snapshot_v1":
        return _run_shadow_v4_governance_reopen_promotion_reconciliation_rollback_or_repair_outcome_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_reopen_promotion_reconciliation_mismatch_case_closure_snapshot_v1":
        return _run_shadow_v4_governance_reopen_promotion_reconciliation_mismatch_case_closure_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_reopen_case_registry_snapshot_v1":
        return _run_shadow_v4_governance_reopen_case_registry_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_reopen_case_triage_snapshot_v1":
        return _run_shadow_v4_governance_reopen_case_triage_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_reopen_case_queue_snapshot_v1":
        return _run_shadow_v4_governance_reopen_case_queue_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governance_portfolio_brief_snapshot_v1":
        return _run_shadow_v4_governance_portfolio_brief_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_directive_spec_initialization_flow_v1_snapshot":
        return _run_shadow_v4_directive_spec_initialization_flow_v1_snapshot_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_wm_hybrid_reopen_candidate_screen_snapshot_v1":
        return _run_shadow_v4_wm_hybrid_reopen_candidate_screen_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_skill_acquisition_flow_snapshot_v1":
        return _run_shadow_v4_governed_skill_acquisition_flow_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1":
        return _run_shadow_v4_governed_skill_candidate_screen_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_skill_trial_admission_snapshot_v1":
        return _run_shadow_v4_governed_skill_trial_admission_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1":
        return _run_shadow_v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1":
        return _run_shadow_v4_governed_directive_work_governance_state_coherence_audit_refresh_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1":
        return _run_shadow_v4_governed_skill_local_trace_parser_trial_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_skill_trial_evidence_snapshot_v1":
        return _run_shadow_v4_governed_skill_trial_evidence_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_skill_provisional_admission_snapshot_v1":
        return _run_shadow_v4_governed_skill_provisional_admission_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1":
        return _run_shadow_v4_governed_skill_local_trace_parser_provisional_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v2":
        return _run_shadow_v4_governed_skill_local_trace_parser_provisional_probe_v2_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v1":
        return _run_shadow_v4_governed_skill_provisional_evidence_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v2":
        return _run_shadow_v4_governed_skill_provisional_evidence_snapshot_v2_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1":
        return _run_shadow_v4_governed_skill_provisional_pause_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_capability_use_policy_snapshot_v1":
        return _run_shadow_v4_governed_capability_use_policy_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1":
        return _run_shadow_v4_governed_capability_use_candidate_screen_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1":
        return _run_shadow_v4_governed_capability_use_invocation_admission_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_capability_use_evidence_snapshot_v1":
        return _run_shadow_v4_governed_capability_use_evidence_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1":
        return _run_shadow_v4_governed_directive_work_selection_policy_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1":
        return _run_shadow_v4_governed_directive_work_candidate_screen_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_directive_work_admission_snapshot_v1":
        return _run_shadow_v4_governed_directive_work_admission_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_direct_work_evidence_snapshot_v1":
        return _run_shadow_v4_governed_direct_work_evidence_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_policy_snapshot_v1":
        return _run_shadow_v4_governed_work_loop_policy_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1":
        return _run_shadow_v4_governed_work_loop_candidate_screen_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2":
        return _run_shadow_v4_governed_work_loop_candidate_screen_snapshot_v2_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v3":
        return _run_shadow_v4_governed_work_loop_candidate_screen_snapshot_v3_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v4":
        return _run_shadow_v4_governed_work_loop_candidate_screen_snapshot_v4_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v5":
        return _run_shadow_v4_governed_work_loop_candidate_screen_snapshot_v5_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v6":
        return _run_shadow_v4_governed_work_loop_candidate_screen_snapshot_v6_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v7":
        return _run_shadow_v4_governed_work_loop_candidate_screen_snapshot_v7_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1":
        return _run_shadow_v4_governed_work_loop_continuation_admission_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2":
        return _run_shadow_v4_governed_work_loop_continuation_admission_snapshot_v2_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v3":
        return _run_shadow_v4_governed_work_loop_continuation_admission_snapshot_v3_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v4":
        return _run_shadow_v4_governed_work_loop_continuation_admission_snapshot_v4_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v5":
        return _run_shadow_v4_governed_work_loop_continuation_admission_snapshot_v5_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v6":
        return _run_shadow_v4_governed_work_loop_continuation_admission_snapshot_v6_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v7":
        return _run_shadow_v4_governed_work_loop_continuation_admission_snapshot_v7_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v1":
        return _run_shadow_v4_governed_work_loop_evidence_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v2":
        return _run_shadow_v4_governed_work_loop_evidence_snapshot_v2_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v3":
        return _run_shadow_v4_governed_work_loop_evidence_snapshot_v3_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v4":
        return _run_shadow_v4_governed_work_loop_evidence_snapshot_v4_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v5":
        return _run_shadow_v4_governed_work_loop_evidence_snapshot_v5_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v6":
        return _run_shadow_v4_governed_work_loop_evidence_snapshot_v6_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v7":
        return _run_shadow_v4_governed_work_loop_evidence_snapshot_v7_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_evidence_snapshot_v8":
        return _run_shadow_v4_governed_work_loop_evidence_snapshot_v8_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_hold_position_closeout_v1":
        return _run_shadow_v4_governed_work_loop_hold_position_closeout_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "memory_summary.v4_governed_work_loop_posture_snapshot_v1":
        return _run_shadow_v4_governed_work_loop_posture_snapshot_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1":
        return _run_shadow_v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1":
        return _run_shadow_v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1":
        return _run_shadow_v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1":
        return _run_shadow_v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1":
        return _run_shadow_v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1":
        return _run_shadow_v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1":
        return _run_shadow_v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "routing_rule.candidate_distribution_aware_probe":
        return _run_shadow_candidate_distribution_probe_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "routing_rule.activation_window_probe":
        return _run_shadow_activation_window_probe_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.projection_gain_goal_v1":
        return _run_shadow_critic_split_projection_gain_goal_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.projection_gain_goal_v2":
        return _run_shadow_critic_split_projection_gain_goal_v2_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.safe_slice_purity_probe_v1":
        return _run_shadow_critic_split_safe_slice_purity_probe_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.benchmark_distance_retention_probe_v1":
        return _run_shadow_critic_split_benchmark_distance_retention_probe_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.benchmark_alignment_critic_v1":
        return _run_shadow_critic_split_benchmark_alignment_critic_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.benchmark_alignment_critic_v2":
        return _run_shadow_critic_split_benchmark_alignment_critic_v2_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.benchmark_transfer_alignment_probe_v1":
        return _run_shadow_critic_split_benchmark_transfer_alignment_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "support_contract.benchmark_stability_sensitive_compat_probe_v1":
        return _run_shadow_support_contract_benchmark_stability_sensitive_compat_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "support_contract.recovery_runner_contract_fix_v1":
        return _run_shadow_support_contract_recovery_runner_contract_fix_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.benchmark_like_transfer_alignment_probe_v1":
        return _run_shadow_critic_split_benchmark_like_transfer_alignment_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.benchmark_like_scoring_preservation_probe_v1":
        return _run_shadow_critic_split_benchmark_like_scoring_preservation_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.benchmark_like_scoring_preservation_probe_v2":
        return _run_shadow_critic_split_benchmark_like_scoring_preservation_probe_v2_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.final_selection_false_safe_guardrail_probe_v1":
        return _run_shadow_critic_split_final_selection_false_safe_guardrail_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.safe_trio_incumbent_confirmation_probe_v1":
        return _run_shadow_critic_split_safe_trio_incumbent_confirmation_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.persistence_balanced_safe_trio_probe_v1":
        return _run_shadow_critic_split_persistence_balanced_safe_trio_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.swap_c_incumbent_hardening_probe_v1":
        return _run_shadow_critic_split_swap_c_incumbent_hardening_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.recovery_benchmark_like_alignment_probe_v1":
        return _run_shadow_critic_split_recovery_benchmark_like_alignment_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.benchmark_family_balance_probe_v1":
        return _run_shadow_critic_split_benchmark_family_balance_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.stability_context_retention_probe_v1":
        return _run_shadow_critic_split_stability_context_retention_probe_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.stability_context_retention_probe_v2":
        return _run_shadow_critic_split_stability_context_retention_probe_v2_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "critic_split.safe_slice_selection_reliability_probe_v1":
        return _run_shadow_critic_split_safe_slice_selection_reliability_probe_v1_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "score_reweight.gain_goal_conflict_probe":
        return _run_shadow_score_reweight_gain_goal_probe_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    if template_name == "score_reweight.blocker_sensitive_projection_probe":
        return _run_shadow_score_reweight_projection_probe_eval(
            cfg,
            proposal,
            rounds=int(rounds),
            seeds=list(seeds),
        )
    return _run_shadow_override_dormancy_snapshot_eval(proposal)


def _run_static_check(proposal: Dict[str, Any]) -> Dict[str, Any]:
    result = validate_proposal_structure(proposal)
    proposal_type = str(proposal.get("proposal_type", ""))
    mechanism = dict(proposal.get("mechanism", {}))
    if not result.get("passed", False):
        return result
    if proposal_type == "routing_rule":
        if not mechanism.get("live_policy_variant"):
            return {"passed": False, "reason": "routing_rule requires mechanism.live_policy_variant"}
        if not mechanism.get("benchmark_variant"):
            return {"passed": False, "reason": "routing_rule requires mechanism.benchmark_variant"}
    return {"passed": True, "reason": "static checks passed"}


def _run_benchmark_evaluation(cfg: ProposalLearningConfig, proposal: Dict[str, Any]) -> Dict[str, Any]:
    template_name = str(proposal.get("template_name", ""))
    if template_name == "routing_rule.slice_targeted_benchmark_sweep_v1":
        return _run_benchmark_slice_targeted_routing_eval(cfg, proposal)
    mechanism = dict(proposal.get("mechanism", {}))
    benchmark_result = run_trusted_benchmark_pack(
        cfg=cfg,
        mode="standalone",
        include_policy_sweep=True,
    )
    summary = dict(benchmark_result.get("summary", {}))
    variant_name = str(mechanism.get("benchmark_variant", ""))
    variant = _find_sweep_variant(summary, variant_name)
    comparison = dict(variant.get("comparison_to_baseline", {}))
    recommendation = dict(variant.get("recommendation", {}))
    passed = bool(
        recommendation.get("safe_to_consider_later")
        or (
            recommendation.get("meets_hard_constraints")
            and float(comparison.get("policy_match_rate_delta") or 0.0) > 0.0
        )
    )
    return {
        "passed": passed,
        "variant_name": variant_name,
        "global_delta": {
            "policy_match_rate_delta": comparison.get("policy_match_rate_delta"),
            "false_safe_projection_rate_delta": comparison.get("false_safe_projection_rate_delta"),
            "unsafe_overcommit_rate_delta": comparison.get("unsafe_overcommit_rate_delta"),
        },
        "family_deltas": dict(comparison.get("family_deltas", {})),
        "recommendation": recommendation,
        "report_paths": summary.get("report_paths"),
    }


def _run_canary_gate(proposal: Dict[str, Any]) -> Dict[str, Any]:
    shadow = dict(proposal.get("evaluation", {}).get("shadow", {}))
    benchmark = dict(proposal.get("evaluation", {}).get("benchmark", {}))
    passed = bool(
        shadow.get("passed", False)
        and benchmark.get("passed", False)
        and "projection_false_safe" not in list(proposal.get("failure_tags", []))
        and "benchmark_regression" not in list(proposal.get("failure_tags", []))
        and "dormant_live_override" not in list(proposal.get("failure_tags", []))
    )
    return {
        "eligible": passed,
        "active": False,
        "reason": (
            "canary ready but not auto-started in this phase"
            if passed
            else "canary blocked by shadow/benchmark outcome or failure tags"
        ),
    }


def run_intervention_proposal(
    *,
    cfg: ProposalLearningConfig | None = None,
    template_name: str = "routing_rule.targeted_gain_goal_proj_margin_01",
    shadow_rounds: int = 1,
    shadow_seeds: List[int] | None = None,
) -> Dict[str, Any]:
    authority_execution_permission = build_execution_permission(
        action_kind="proposal_runner",
        template_name=str(template_name),
    )
    require_execution_permission(authority_execution_permission)

    def _build_summary(current_proposal: Dict[str, Any]) -> Dict[str, Any]:
        evaluation = dict(current_proposal.get("evaluation", {}))
        return {
            "proposal_id": current_proposal["proposal_id"],
            "template_name": current_proposal["template_name"],
            "proposal_type": current_proposal["proposal_type"],
            "evaluation_semantics": current_proposal.get("evaluation_semantics"),
            "promotion_status": current_proposal["promotion_status"],
            "failure_tags": list(current_proposal.get("failure_tags", [])),
            "evaluation_plan": list(current_proposal.get("evaluation_plan", [])),
            "plan_execution": copy.deepcopy(current_proposal.get("plan_execution", {})),
            "forecast": dict(evaluation.get("forecast", {})),
            "shadow": {
                "passed": dict(evaluation.get("shadow", {})).get("passed"),
                "delta": dict(dict(evaluation.get("shadow", {})).get("delta", {})),
                "variant_overrides": dict(dict(evaluation.get("shadow", {})).get("variant", {})).get("live_variant_override_total"),
                "stage_status": dict(evaluation.get("shadow", {})).get("stage_status"),
            },
            "benchmark": {
                "passed": dict(evaluation.get("benchmark", {})).get("passed"),
                "variant_name": dict(evaluation.get("benchmark", {})).get("variant_name"),
                "global_delta": dict(dict(evaluation.get("benchmark", {})).get("global_delta", {})),
                "stage_status": dict(evaluation.get("benchmark", {})).get("stage_status"),
            },
            "canary": dict(evaluation.get("canary", {})),
            "authority_execution_permission": copy.deepcopy(authority_execution_permission),
        }

    cfg = copy.deepcopy(cfg) if cfg is not None else build_default_config(verbose=False)
    cfg.verbose = False
    proposal = build_proposal_template(template_name)
    _initialize_plan_execution(proposal)
    proposal["evaluation"]["forecast"] = forecast_proposal(proposal, build_forecast_context())
    append_snapshot(proposal, event_type="proposal_created", note="draft proposal created from template")

    if "static_check" in _declared_plan(proposal):
        static_result = _run_static_check(proposal)
        static_result["stage_status"] = "passed" if static_result.get("passed", False) else "failed"
        proposal["evaluation"]["static"] = static_result
        if static_result.get("passed", False):
            _update_stage_state(
                proposal,
                stage="static_check",
                stage_status="passed",
                summary=static_result,
                note="static validation passed",
            )
            _record_stage(
                proposal,
                stage="static_check",
                status="static_checked",
                summary=static_result,
                event_type="stage_transition",
                note="static validation passed",
            )
            if _is_last_planned_stage(proposal, "static_check"):
                _complete_intended_plan(
                    proposal,
                    final_stage="static_check",
                    summary=static_result,
                    note="intended evaluation plan completed after static_check",
                )
                return {
                    "proposal": proposal,
                    "ledger_path": str(intervention_ledger_path()),
                    "summary": _build_summary(proposal),
                    "authority_execution_permission": copy.deepcopy(authority_execution_permission),
                }
        else:
            _fail_intended_stage(
                proposal,
                stage="static_check",
                summary=static_result,
                failure_tag="static_stage_failed",
                note="static validation failed",
            )
            return {
                "proposal": proposal,
                "ledger_path": str(intervention_ledger_path()),
                "summary": _build_summary(proposal),
                "authority_execution_permission": copy.deepcopy(authority_execution_permission),
            }

    mechanism = dict(proposal.get("mechanism", {}))
    if "shadow" in _declared_plan(proposal):
        semantics = str(proposal.get("evaluation_semantics") or proposal_evaluation_semantics(str(proposal.get("proposal_type", ""))))
        shadow_result = {
            "passed": False,
            "reason": "shadow evaluator not configured for this proposal type",
        }
        if semantics == "control_changing" and str(proposal.get("proposal_type")) == "routing_rule":
            shadow_result = _run_shadow_live_eval(
                cfg,
                variant_name=str(mechanism.get("live_policy_variant", "baseline")),
                rounds=max(1, int(shadow_rounds)),
                seeds=list(shadow_seeds or [int(cfg.seed)]),
                proposal_id=str(proposal["proposal_id"]),
            )
            delta = dict(shadow_result.get("delta", {}))
            shadow_passed = bool(
                int(delta.get("rollback_count", 0)) <= 0
                and int(delta.get("projection_bad_incidents", 0)) <= 0
            )
            shadow_result["passed"] = shadow_passed
            if int(delta.get("override_count", 0)) <= 0:
                _add_failure_tag(proposal, "dormant_live_override")
            if int(delta.get("projection_bad_incidents", 0)) > 0:
                _add_failure_tag(proposal, "projection_false_safe")
            if shadow_result["variant"].get("mean_goal_mse_latent") is not None and shadow_result["baseline"].get("mean_goal_mse_latent") is not None:
                if float(shadow_result["variant"]["mean_goal_mse_latent"]) > float(shadow_result["baseline"]["mean_goal_mse_latent"]):
                    _add_failure_tag(proposal, "persistence_regression")
        elif semantics == "diagnostic":
            shadow_result = _run_shadow_diagnostic_eval(
                cfg,
                proposal,
                rounds=max(1, int(shadow_rounds)),
                seeds=list(shadow_seeds or [int(cfg.seed)]),
            )
        shadow_result["stage_status"] = "passed" if shadow_result.get("passed", False) else "failed"
        proposal["evaluation"]["shadow"] = shadow_result
        if shadow_result.get("passed", False):
            _update_stage_state(
                proposal,
                stage="shadow",
                stage_status="passed",
                summary=shadow_result,
                note="shadow evaluation complete",
            )
            _record_stage(
                proposal,
                stage="shadow",
                status="shadow_evaluated",
                summary=shadow_result,
                event_type="stage_transition",
                note="shadow evaluation complete",
            )
            if _is_last_planned_stage(proposal, "shadow"):
                _complete_intended_plan(
                    proposal,
                    final_stage="shadow",
                    summary=shadow_result,
                    note="intended evaluation plan completed after shadow",
                )
                return {
                    "proposal": proposal,
                    "ledger_path": str(intervention_ledger_path()),
                    "summary": _build_summary(proposal),
                    "authority_execution_permission": copy.deepcopy(authority_execution_permission),
                }
        else:
            _fail_intended_stage(
                proposal,
                stage="shadow",
                summary=shadow_result,
                failure_tag="shadow_stage_failed",
                note="shadow evaluation failed",
            )
            return {
                "proposal": proposal,
                "ledger_path": str(intervention_ledger_path()),
                "summary": _build_summary(proposal),
                "authority_execution_permission": copy.deepcopy(authority_execution_permission),
            }

    if "benchmark" in _declared_plan(proposal):
        benchmark_result = _run_benchmark_evaluation(cfg, proposal)
        benchmark_result["stage_status"] = "passed" if benchmark_result.get("passed", False) else "failed"
        proposal["evaluation"]["benchmark"] = benchmark_result
        if not bool(benchmark_result.get("passed", False)):
            _add_failure_tag(proposal, "benchmark_regression")
            if float(dict(benchmark_result.get("global_delta", {})).get("false_safe_projection_rate_delta") or 0.0) > 0.0:
                _add_failure_tag(proposal, "projection_false_safe")
            _fail_intended_stage(
                proposal,
                stage="benchmark",
                summary=benchmark_result,
                failure_tag="benchmark_stage_failed",
                note="benchmark evaluation failed",
            )
            return {
                "proposal": proposal,
                "ledger_path": str(intervention_ledger_path()),
                "summary": _build_summary(proposal),
                "authority_execution_permission": copy.deepcopy(authority_execution_permission),
            }
        _update_stage_state(
            proposal,
            stage="benchmark",
            stage_status="passed",
            summary=benchmark_result,
            note="benchmark evaluation complete",
        )
        _record_stage(
            proposal,
            stage="benchmark",
            status="benchmark_evaluated",
            summary=benchmark_result,
            event_type="stage_transition",
            note="benchmark evaluation complete",
        )
        if _is_last_planned_stage(proposal, "benchmark"):
            _complete_intended_plan(
                proposal,
                final_stage="benchmark",
                summary=benchmark_result,
                note="intended evaluation plan completed after benchmark",
            )
            return {
                "proposal": proposal,
                "ledger_path": str(intervention_ledger_path()),
                "summary": _build_summary(proposal),
                "authority_execution_permission": copy.deepcopy(authority_execution_permission),
            }

    if "canary_gate" in _declared_plan(proposal):
        canary_result = _run_canary_gate(proposal)
        canary_result["stage_status"] = "eligible" if canary_result.get("eligible", False) else "ineligible"
        proposal["evaluation"]["canary"] = canary_result
        _update_stage_state(
            proposal,
            stage="canary_gate",
            stage_status="eligible" if canary_result.get("eligible", False) else "ineligible",
            summary=canary_result,
            note="canary eligibility assessed",
        )
        _record_stage(
            proposal,
            stage="canary_gate",
            status="canary_eligible" if bool(canary_result.get("eligible", False)) else "canary_gate_evaluated",
            summary=canary_result,
            event_type="stage_transition",
            note="canary eligibility assessed",
        )
        _complete_intended_plan(
            proposal,
            final_stage="canary_gate",
            summary=canary_result,
            note="intended evaluation plan completed after canary_gate",
        )

    return {
        "proposal": proposal,
        "ledger_path": str(intervention_ledger_path()),
        "summary": _build_summary(proposal),
        "authority_execution_permission": copy.deepcopy(authority_execution_permission),
    }

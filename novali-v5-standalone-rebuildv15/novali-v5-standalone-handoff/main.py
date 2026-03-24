from __future__ import annotations

import argparse
import math
import os
from collections import Counter
from copy import deepcopy
from typing import Any, Iterable

from operator_shell.common import OperatorConstraintViolationError
from operator_shell.runtime_guard import install_runtime_guard_from_environment

_OPERATOR_GUARD_INSTALL_ERROR: OperatorConstraintViolationError | None = None
try:
    install_runtime_guard_from_environment()
except OperatorConstraintViolationError as exc:
    _OPERATOR_GUARD_INSTALL_ERROR = exc


def _fmt_float(value) -> str:
    if value is None:
        return "None"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _mean_or_none(values: Iterable[Any]) -> float | None:
    clean = []
    for value in values:
        try:
            scalar = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(scalar):
            clean.append(scalar)
    if not clean:
        return None
    return float(sum(clean) / len(clean))


def _parse_seed_list(seed_text: str | None, fallback_seed: int) -> list[int]:
    if not seed_text:
        return [int(fallback_seed)]
    seeds: list[int] = []
    seen = set()
    for chunk in str(seed_text).split(","):
        piece = chunk.strip()
        if not piece:
            continue
        seed = int(piece)
        if seed in seen:
            continue
        seen.add(seed)
        seeds.append(seed)
    return seeds or [int(fallback_seed)]


def _mean_abs_signal(signal: Any) -> float | None:
    if signal is None:
        return None
    try:
        values = [abs(float(item)) for item in list(signal)]
    except TypeError:
        return None
    if not values:
        return None
    return float(sum(values) / len(values))


def _summarize_live_histories(
    *,
    histories: list[list[dict]],
    policy_name: str,
    seeds: list[int],
    baseline_projection_cap: float,
    override_projection_cap: float | None,
) -> dict:
    provisional_count = 0
    full_adopt_count = 0
    rounds_with_selection = 0
    rollback_count = 0
    rollback_cause_counts: Counter[str] = Counter()
    projection_bad_incidents = 0
    selected_gain_bad_incidents = 0
    selected_goal_bad_incidents = 0
    selected_projection_bad_incidents = 0
    base_avg_values: list[float] = []
    post_avg_values: list[float] = []
    realized_gain_values: list[float] = []
    goal_agreement_values: list[float] = []
    goal_mse_values: list[float] = []
    projection_error_values: list[float] = []
    recurrence_values: list[float] = []
    persistence_signal_values: list[float] = []
    variant_override_counts = 0
    variant_persistence_guards = 0
    variant_recovery_guards = 0
    variant_projection_guards = 0
    variant_projected_quality_guards = 0
    variant_baseline_rejected_total = 0
    variant_projection_eligible_total = 0
    variant_conf_gain_eligible_total = 0
    variant_persistence_eligible_total = 0
    variant_recovery_eligible_total = 0
    variant_quality_eligible_total = 0
    variant_other_block_total = 0
    variant_override_rounds: list[dict[str, Any]] = []
    per_seed: list[dict[str, Any]] = []
    total_rounds = 0

    for seed, history in zip(seeds, histories):
        seed_provisional = 0
        seed_full = 0
        seed_rollbacks = 0
        seed_projection_bad = 0
        seed_selected_rounds = 0
        seed_cause_counts: Counter[str] = Counter()
        seed_override_rounds: list[int] = []
        for entry in history:
            total_rounds += 1
            adopted = [item for item in list(entry.get("adopted", [])) if isinstance(item, dict)]
            if adopted:
                rounds_with_selection += 1
                seed_selected_rounds += 1
            for item in adopted:
                status = str(item.get("status", ""))
                if status == "provisional":
                    provisional_count += 1
                    seed_provisional += 1
                elif status == "full":
                    full_adopt_count += 1
                    seed_full += 1
            if bool(entry.get("rollback_triggered", False)):
                rollback_count += 1
                seed_rollbacks += 1
                rollback_cause = str(entry.get("rollback_cause", "none"))
                rollback_cause_counts[rollback_cause] += 1
                seed_cause_counts[rollback_cause] += 1

            rollback_row = dict(entry.get("round_rollback_audit_row", {}))
            if float(rollback_row.get("realized_projection_bad", 0.0)) > 0.5:
                projection_bad_incidents += 1
                seed_projection_bad += 1
            if float(rollback_row.get("realized_gain_bad", 0.0)) > 0.5:
                selected_gain_bad_incidents += 1
            if float(rollback_row.get("realized_goal_bad", 0.0)) > 0.5:
                selected_goal_bad_incidents += 1
            if float(rollback_row.get("realized_projection_bad", 0.0)) > 0.5:
                selected_projection_bad_incidents += 1

            base_avg = float(entry.get("base_avg", 0.0))
            post_avg = float(entry.get("post_avg", 0.0))
            base_avg_values.append(base_avg)
            post_avg_values.append(post_avg)
            realized_gain_values.append(post_avg - base_avg)
            goal_agreement_values.append(float(entry.get("goal_agreement", 0.0)))
            goal_mse_values.append(float(entry.get("goal_mse_latent", 0.0)))

            post_9d = dict(entry.get("post_9d_metrics", {}))
            projection_error = post_9d.get("projection_error")
            if projection_error is not None and math.isfinite(float(projection_error)):
                projection_error_values.append(float(projection_error))

            recurrence = entry.get("self_recurrence_global")
            if recurrence is not None and math.isfinite(float(recurrence)):
                recurrence_values.append(float(recurrence))

            persistence_signal = _mean_abs_signal(entry.get("self_persistence_signals"))
            if persistence_signal is not None:
                persistence_signal_values.append(float(persistence_signal))
            diagnostics = dict(entry.get("selection_rate_diagnostics", {}))
            variant_override_counts += int(diagnostics.get("live_variant_override_count", 0))
            variant_persistence_guards += int(diagnostics.get("live_variant_persistence_guard", 0))
            variant_recovery_guards += int(diagnostics.get("live_variant_recovery_guard", 0))
            variant_projection_guards += int(diagnostics.get("live_variant_projection_guard", 0))
            variant_projected_quality_guards += int(diagnostics.get("live_variant_projected_quality_guard", 0))
            variant_baseline_rejected_total += int(diagnostics.get("live_variant_baseline_rejected_candidates", 0))
            variant_projection_eligible_total += int(diagnostics.get("live_variant_projection_eligible_candidates", 0))
            variant_conf_gain_eligible_total += int(diagnostics.get("live_variant_conf_gain_eligible_candidates", 0))
            variant_persistence_eligible_total += int(diagnostics.get("live_variant_persistence_eligible_candidates", 0))
            variant_recovery_eligible_total += int(diagnostics.get("live_variant_recovery_eligible_candidates", 0))
            variant_quality_eligible_total += int(diagnostics.get("live_variant_quality_eligible_candidates", 0))
            variant_other_block_total += int(diagnostics.get("live_variant_block_other", 0))
            if int(diagnostics.get("live_variant_override_count", 0)) > 0:
                round_idx = int(entry.get("round", 0))
                seed_override_rounds.append(round_idx)
                variant_override_rounds.append(
                    {
                        "seed": int(seed),
                        "round": int(round_idx),
                        "override_count": int(diagnostics.get("live_variant_override_count", 0)),
                    }
                )

        per_seed.append(
            {
                "seed": int(seed),
                "rounds": int(len(history)),
                "provisional_count": int(seed_provisional),
                "full_adopt_count": int(seed_full),
                "rounds_with_selection": int(seed_selected_rounds),
                "rollback_count": int(seed_rollbacks),
                "rollback_cause_counts": dict(seed_cause_counts),
                "projection_bad_incidents": int(seed_projection_bad),
                "override_rounds": seed_override_rounds,
            }
        )

    variant_block_reason_counts = {
        "projection_guard": int(variant_projection_guards),
        "persistence_guard": int(variant_persistence_guards),
        "recovery_guard": int(variant_recovery_guards),
        "confidence_gain_precondition": int(
            max(0, int(variant_projection_eligible_total) - int(variant_conf_gain_eligible_total))
        ),
        "other_eligibility_failure": int(variant_projected_quality_guards + variant_other_block_total),
    }
    dominant_variant_block_reason = "none"
    dominant_variant_block_count = max(variant_block_reason_counts.values()) if variant_block_reason_counts else 0
    if dominant_variant_block_count > 0:
        dominant_variant_block_reason = max(variant_block_reason_counts.items(), key=lambda item: int(item[1]))[0]

    return {
        "policy_name": str(policy_name),
        "seeds": list(map(int, seeds)),
        "run_count": int(len(histories)),
        "rounds_total": int(total_rounds),
        "baseline_projection_bad_max_provisional": float(baseline_projection_cap),
        "override_projection_bad_max_provisional": (
            None if override_projection_cap is None else float(override_projection_cap)
        ),
        "provisional_count": int(provisional_count),
        "full_adopt_count": int(full_adopt_count),
        "rounds_with_selection": int(rounds_with_selection),
        "selection_round_rate_pct": float(100.0 * rounds_with_selection / max(total_rounds, 1)),
        "rollback_count": int(rollback_count),
        "rollback_cause_counts": dict(rollback_cause_counts),
        "projection_bad_incidents": int(projection_bad_incidents),
        "selected_gain_bad_incidents": int(selected_gain_bad_incidents),
        "selected_goal_bad_incidents": int(selected_goal_bad_incidents),
        "selected_projection_bad_incidents": int(selected_projection_bad_incidents),
        "mean_base_avg": _mean_or_none(base_avg_values),
        "mean_post_avg": _mean_or_none(post_avg_values),
        "mean_realized_gain": _mean_or_none(realized_gain_values),
        "mean_goal_agreement": _mean_or_none(goal_agreement_values),
        "mean_goal_mse_latent": _mean_or_none(goal_mse_values),
        "mean_projection_error": _mean_or_none(projection_error_values),
        "mean_self_recurrence_global": _mean_or_none(recurrence_values),
        "final_self_recurrence_global": recurrence_values[-1] if recurrence_values else None,
        "mean_abs_self_persistence_signal": _mean_or_none(persistence_signal_values),
        "live_variant_override_count": int(variant_override_counts),
        "live_variant_persistence_guard": int(variant_persistence_guards),
        "live_variant_recovery_guard": int(variant_recovery_guards),
        "live_variant_projection_guard": int(variant_projection_guards),
        "live_variant_projected_quality_guard": int(variant_projected_quality_guards),
        "live_variant_baseline_rejected_total": int(variant_baseline_rejected_total),
        "live_variant_projection_eligible_total": int(variant_projection_eligible_total),
        "live_variant_conf_gain_eligible_total": int(variant_conf_gain_eligible_total),
        "live_variant_persistence_eligible_total": int(variant_persistence_eligible_total),
        "live_variant_recovery_eligible_total": int(variant_recovery_eligible_total),
        "live_variant_quality_eligible_total": int(variant_quality_eligible_total),
        "live_variant_block_reason_counts": dict(variant_block_reason_counts),
        "live_variant_dominant_block_reason": str(dominant_variant_block_reason),
        "live_variant_dominant_block_count": int(dominant_variant_block_count),
        "live_variant_override_rounds": variant_override_rounds[:32],
        "per_seed": per_seed,
    }


def _diff_counters(left: dict[str, Any], right: dict[str, Any]) -> dict[str, int]:
    keys = set(left.keys()) | set(right.keys())
    return {
        str(key): int(right.get(key, 0)) - int(left.get(key, 0))
        for key in sorted(keys)
    }


def _build_live_ab_summary(baseline: dict, variant: dict) -> dict:
    return {
        "baseline": dict(baseline),
        "variant": dict(variant),
        "delta": {
            "provisional_count": int(variant.get("provisional_count", 0)) - int(baseline.get("provisional_count", 0)),
            "full_adopt_count": int(variant.get("full_adopt_count", 0)) - int(baseline.get("full_adopt_count", 0)),
            "rounds_with_selection": int(variant.get("rounds_with_selection", 0)) - int(baseline.get("rounds_with_selection", 0)),
            "rollback_count": int(variant.get("rollback_count", 0)) - int(baseline.get("rollback_count", 0)),
            "projection_bad_incidents": int(variant.get("projection_bad_incidents", 0)) - int(baseline.get("projection_bad_incidents", 0)),
            "selected_gain_bad_incidents": int(variant.get("selected_gain_bad_incidents", 0)) - int(baseline.get("selected_gain_bad_incidents", 0)),
            "selected_goal_bad_incidents": int(variant.get("selected_goal_bad_incidents", 0)) - int(baseline.get("selected_goal_bad_incidents", 0)),
            "live_variant_override_count": int(variant.get("live_variant_override_count", 0)) - int(baseline.get("live_variant_override_count", 0)),
            "mean_realized_gain": (
                None
                if baseline.get("mean_realized_gain") is None or variant.get("mean_realized_gain") is None
                else float(variant["mean_realized_gain"] - baseline["mean_realized_gain"])
            ),
            "mean_goal_agreement": (
                None
                if baseline.get("mean_goal_agreement") is None or variant.get("mean_goal_agreement") is None
                else float(variant["mean_goal_agreement"] - baseline["mean_goal_agreement"])
            ),
            "mean_goal_mse_latent": (
                None
                if baseline.get("mean_goal_mse_latent") is None or variant.get("mean_goal_mse_latent") is None
                else float(variant["mean_goal_mse_latent"] - baseline["mean_goal_mse_latent"])
            ),
            "mean_projection_error": (
                None
                if baseline.get("mean_projection_error") is None or variant.get("mean_projection_error") is None
                else float(variant["mean_projection_error"] - baseline["mean_projection_error"])
            ),
            "mean_self_recurrence_global": (
                None
                if baseline.get("mean_self_recurrence_global") is None or variant.get("mean_self_recurrence_global") is None
                else float(variant["mean_self_recurrence_global"] - baseline["mean_self_recurrence_global"])
            ),
            "mean_abs_self_persistence_signal": (
                None
                if baseline.get("mean_abs_self_persistence_signal") is None or variant.get("mean_abs_self_persistence_signal") is None
                else float(variant["mean_abs_self_persistence_signal"] - baseline["mean_abs_self_persistence_signal"])
            ),
            "rollback_cause_counts": _diff_counters(
                dict(baseline.get("rollback_cause_counts", {})),
                dict(variant.get("rollback_cause_counts", {})),
            ),
        },
    }


def _run_live_policy_ab(
    *,
    base_cfg,
    variant_name: str,
    seeds: list[int],
) -> dict:
    from experiments.proposal_learning_loop import run_proposal_learning_loop
    from runtime_config import apply_live_policy_variant

    policy_names = ["baseline", str(variant_name)]
    summaries: dict[str, dict] = {}
    for policy_name in policy_names:
        histories: list[list[dict]] = []
        for seed in seeds:
            run_cfg = deepcopy(base_cfg)
            run_cfg.seed = int(seed)
            run_cfg.benchmark_every_rounds = 0
            apply_live_policy_variant(run_cfg, policy_name)
            run_cfg.eval_kwargs = dict(run_cfg.eval_kwargs)
            safe_policy_name = str(policy_name).replace("/", "_").replace("\\", "_")
            run_cfg.eval_kwargs["session_log_path"] = f"logs/live_ab_{safe_policy_name}_seed{int(seed)}.log"
            _, _, history = run_proposal_learning_loop(run_cfg)
            histories.append(history)
        summaries[policy_name] = _summarize_live_histories(
            histories=histories,
            policy_name=policy_name,
            seeds=seeds,
            baseline_projection_cap=float(getattr(run_cfg, "wm_candidate_pred_projection_bad_max_provisional", 0.0)),
            override_projection_cap=(
                max(
                    0.0,
                    min(
                        float(getattr(run_cfg, "live_policy_targeted_projection_strict_max", 0.48)),
                        float(getattr(run_cfg, "wm_candidate_pred_projection_bad_max_provisional", 0.0))
                        - float(getattr(run_cfg, "live_policy_projection_margin_provisional", 0.0)),
                    ),
                )
                if str(policy_name) == "targeted_gain_goal_proj_margin_01"
                else None
            ),
        )
    return _build_live_ab_summary(
        baseline=summaries["baseline"],
        variant=summaries[str(variant_name)],
    )


def _print_live_ab_summary(summary: dict) -> None:
    baseline = dict(summary.get("baseline", {}))
    variant = dict(summary.get("variant", {}))
    delta = dict(summary.get("delta", {}))
    print("\n=== Live Policy A/B Comparison ===")
    print(f"Seeds          : {baseline.get('seeds')}")
    print(f"Rounds total   : {baseline.get('rounds_total')}")
    for label, block in (("baseline", baseline), ("variant", variant)):
        print(
            f"{label:<14}: {block.get('policy_name')} "
            f"(base_proj_cap={_fmt_float(block.get('baseline_projection_bad_max_provisional'))}, "
            f"override_proj_cap={_fmt_float(block.get('override_projection_bad_max_provisional'))})"
        )
        print(
            f"  selected={block.get('rounds_with_selection')} "
            f"({ _fmt_float(block.get('selection_round_rate_pct')) }%) "
            f"provisional={block.get('provisional_count')} "
            f"full={block.get('full_adopt_count')}"
        )
        print(
            f"  rollbacks={block.get('rollback_count')} "
            f"causes={block.get('rollback_cause_counts')} "
            f"projection_bad={block.get('projection_bad_incidents')}"
        )
        print(
            f"  gain_mean={_fmt_float(block.get('mean_realized_gain'))} "
            f"goal_agree={_fmt_float(block.get('mean_goal_agreement'))} "
            f"goal_mse={_fmt_float(block.get('mean_goal_mse_latent'))} "
            f"proj_err={_fmt_float(block.get('mean_projection_error'))}"
        )
        print(
            f"  persistence: recur_mean={_fmt_float(block.get('mean_self_recurrence_global'))} "
            f"recur_final={_fmt_float(block.get('final_self_recurrence_global'))} "
            f"signal_abs={_fmt_float(block.get('mean_abs_self_persistence_signal'))}"
        )
        print(
            f"  variant_ctl: overrides={block.get('live_variant_override_count')} "
            f"persist_guard={block.get('live_variant_persistence_guard')} "
            f"recovery_guard={block.get('live_variant_recovery_guard')} "
            f"proj_guard={block.get('live_variant_projection_guard')} "
            f"quality_guard={block.get('live_variant_projected_quality_guard')}"
        )
        print(
            f"  variant_audit: rejected={block.get('live_variant_baseline_rejected_total')} "
            f"proj_ok={block.get('live_variant_projection_eligible_total')} "
            f"conf_gain_ok={block.get('live_variant_conf_gain_eligible_total')} "
            f"persist_ok={block.get('live_variant_persistence_eligible_total')} "
            f"recovery_ok={block.get('live_variant_recovery_eligible_total')} "
            f"quality_ok={block.get('live_variant_quality_eligible_total')} "
            f"dominant={block.get('live_variant_dominant_block_reason')}"
        )
        print(
            f"  recovery_px: gain_bad={block.get('selected_gain_bad_incidents')} "
            f"goal_bad={block.get('selected_goal_bad_incidents')} "
            f"projection_bad={block.get('selected_projection_bad_incidents')}"
        )
    print("delta         :")
    print(
        f"  provisional={delta.get('provisional_count')} "
        f"full={delta.get('full_adopt_count')} "
        f"selected={delta.get('rounds_with_selection')}"
    )
    print(
        f"  rollbacks={delta.get('rollback_count')} "
        f"projection_bad={delta.get('projection_bad_incidents')} "
        f"causes={delta.get('rollback_cause_counts')}"
    )
    print(
        f"  gain_mean={_fmt_float(delta.get('mean_realized_gain'))} "
        f"goal_agree={_fmt_float(delta.get('mean_goal_agreement'))} "
        f"goal_mse={_fmt_float(delta.get('mean_goal_mse_latent'))} "
        f"proj_err={_fmt_float(delta.get('mean_projection_error'))}"
    )
    print(
        f"  persistence: recur_mean={_fmt_float(delta.get('mean_self_recurrence_global'))} "
        f"signal_abs={_fmt_float(delta.get('mean_abs_self_persistence_signal'))}"
    )
    print(f"  variant_overrides={delta.get('live_variant_override_count')}")


def _print_benchmark_compact(summary: dict, indent: str = "") -> None:
    global_compact = dict(summary.get("global_compact_summary", {}))
    if global_compact:
        print(f"{indent}match        : {_fmt_float(global_compact.get('policy_match_rate'))}")
        print(f"{indent}proj_brier   : {_fmt_float(global_compact.get('projection_bad_brier'))}")
        print(f"{indent}gain_brier   : {_fmt_float(global_compact.get('gain_bad_brier'))}")
        print(f"{indent}goal_brier   : {_fmt_float(global_compact.get('goal_bad_brier'))}")
        print(f"{indent}expected_act : {global_compact.get('expected_action_distribution')}")
        print(f"{indent}policy_act   : {global_compact.get('policy_action_distribution')}")
        print(f"{indent}confusion    : {global_compact.get('preferred_action_confusion')}")
        print(f"{indent}false_safe   : {_fmt_float(global_compact.get('false_safe_projection_rate'))}")
        print(f"{indent}false_full   : {_fmt_float(global_compact.get('false_full_adopt_rate'))}")
        print(f"{indent}dominant_miss: {global_compact.get('dominant_mismatch')}")
        print(f"{indent}policy_bias  : {global_compact.get('policy_bias')}")
        print(f"{indent}reject_over  : {_fmt_float(global_compact.get('reject_overuse_rate'))}")
        print(f"{indent}missed_safe  : {_fmt_float(global_compact.get('missed_safe_opportunity_rate'))}")
        print(f"{indent}undercommit  : {_fmt_float(global_compact.get('undercommitment_score'))}")
        print(f"{indent}diagnosis    : {global_compact.get('alignment_diagnosis')}")
    family_compact = dict(summary.get("family_compact_summary", {}))
    family_mismatch = dict(summary.get("family_mismatch_summary", {}))
    if family_compact:
        worst_under = max(
            family_mismatch.items(),
            key=lambda item: float((dict(item[1]).get("undercommitment_score") or -1.0)),
        )[0]
        worst_unsafe = max(
            family_mismatch.items(),
            key=lambda item: float((dict(item[1]).get("unsafe_overcommit_rate") or -1.0)),
        )[0]
        print(f"{indent}worst_under : {worst_under}")
        print(f"{indent}worst_unsafe: {worst_unsafe}")
        print(f"{indent}by_family    :")
        for family in sorted(family_compact.keys()):
            family_summary = dict(family_compact.get(family, {}))
            mismatch = dict(family_mismatch.get(family, {}))
            print(
                f"{indent}  {family}: "
                f"match={_fmt_float(family_summary.get('policy_match_rate'))} "
                f"proj_brier={_fmt_float(family_summary.get('projection_bad_brier'))} "
                f"gain_brier={_fmt_float(family_summary.get('gain_bad_brier'))} "
                f"goal_brier={_fmt_float(family_summary.get('goal_bad_brier'))} "
                f"actions={family_summary.get('policy_action_distribution')} "
                f"expected={family_summary.get('expected_action_distribution')} "
                f"miss={family_summary.get('dominant_mismatch')} "
                f"diag={dict(mismatch.get('alignment_diagnosis', {})).get('primary')} "
                f"under={_fmt_float(mismatch.get('undercommitment_score'))} "
                f"false_safe={_fmt_float(family_summary.get('false_safe_projection_rate'))} "
                f"false_full={_fmt_float(family_summary.get('false_full_adopt_rate'))}"
            )


def _print_policy_sweep_summary(summary: dict, indent: str = "") -> None:
    sweep = dict(summary.get("policy_sweep_analysis", {}))
    if not sweep:
        return
    variants = list(sweep.get("variants", []))
    reference_name = sweep.get("reference_variant")
    best_name = sweep.get("best_safe_variant") or sweep.get("best_overall_variant")
    chosen = None
    for variant in variants:
        if str(variant.get("name")) == str(best_name):
            chosen = dict(variant)
            break
    if chosen is None and variants:
        chosen = dict(variants[0])
    print(f"{indent}sweep       :")
    print(f"{indent}  reference    : {reference_name}")
    print(f"{indent}  best_variant : {best_name}")
    print(f"{indent}  smallest_ok  : {sweep.get('smallest_change_acceptable_variant')}")
    print(f"{indent}  recommendation: {sweep.get('recommendation')}")
    if chosen:
        comp = dict(chosen.get("comparison_to_baseline", {}))
        ref_comp = dict(chosen.get("comparison_to_targeted_gain_goal_safe_window", {}))
        rec = dict(chosen.get("recommendation", {}))
        print(f"{indent}  delta_match  : {_fmt_float(comp.get('policy_match_rate_delta'))}")
        print(f"{indent}  delta_prov_rj: {comp.get('expected_provisional_got_reject_delta')}")
        print(f"{indent}  delta_full_rj: {comp.get('expected_full_got_reject_delta')}")
        print(f"{indent}  delta_unsafe : {_fmt_float(comp.get('unsafe_overcommit_rate_delta'))}")
        print(f"{indent}  delta_false_s: {_fmt_float(comp.get('false_safe_projection_rate_delta'))}")
        print(f"{indent}  vs_ref_match : {_fmt_float(ref_comp.get('policy_match_rate_delta'))}")
        print(f"{indent}  vs_ref_false : {_fmt_float(ref_comp.get('false_safe_projection_rate_delta'))}")
        print(f"{indent}  gain_goal_d  : {_fmt_float(rec.get('gain_goal_match_delta'))}")
        print(f"{indent}  persist_d    : {_fmt_float(rec.get('persistence_match_delta'))}")
        print(f"{indent}  hard_caps_ok : {rec.get('meets_hard_constraints')}")
        print(f"{indent}  safe_later   : {rec.get('safe_to_consider_later')}")
        family_deltas = dict(comp.get("family_deltas", {}))
        for family in ("gain_goal_conflict", "recovery", "projection", "persistence"):
            family_delta = dict(family_deltas.get(family, {}))
            if not family_delta:
                continue
            print(
                f"{indent}  {family}: "
                f"match={_fmt_float(family_delta.get('policy_match_rate_delta'))} "
                f"prov_rj={family_delta.get('expected_provisional_got_reject_delta')} "
                f"full_rj={family_delta.get('expected_full_got_reject_delta')} "
                f"unsafe={_fmt_float(family_delta.get('unsafe_overcommit_rate_delta'))}"
            )


def _print_training_summary(last: dict, cfg) -> None:
    if last.get("runtime_marker"):
        print(f"Runtime Marker: {last.get('runtime_marker')}")
    if last.get("live_policy_variant"):
        print(
            "Live Policy  : "
            f"{last.get('live_policy_variant')} "
            f"(base_proj_cap={_fmt_float(last.get('live_policy_projection_bad_max_provisional_baseline'))}, "
            f"override_proj_cap={_fmt_float(last.get('live_policy_targeted_override_projection_bad_max'))})"
        )
    print("\nFinal Metrics:")
    print(f"  base_avg      : {last['base_avg']:.3f}")
    print(f"  post_avg      : {last['post_avg']:.3f}")
    print(f"  wm_loss       : {last.get('wm_loss')}")
    print(f"  curiosity     : {last.get('curiosity')}")
    print(f"  goal_agreement: {last.get('goal_agreement')}")
    print(f"  goal_mse      : {last.get('goal_mse_latent')}")
    if last.get("adopt_candidate_counts"):
        print(f"  adopt_counts  : {last.get('adopt_candidate_counts')}")
    if last.get("shadow_candidate_counts"):
        print(f"  shadow_counts : {last.get('shadow_candidate_counts')}")
    row_summary = last.get("selection_rate_summary", {})
    if row_summary:
        print("  row_summary   :")
        print(
            f"    live={row_summary.get('live_row_count')}/{row_summary.get('rounds_total')} "
            f"({row_summary.get('live_row_rate_pct'):.1f}%)"
        )
        print(
            f"    shadow={row_summary.get('shadow_row_count')}/{row_summary.get('rounds_total')} "
            f"({row_summary.get('shadow_row_rate_pct'):.1f}%)"
        )
        print(
            f"    combined={row_summary.get('combined_row_count')}/{row_summary.get('rounds_total')} "
            f"({row_summary.get('combined_row_rate_pct'):.1f}%)"
        )
        if last.get("live_policy_variant") == "targeted_gain_goal_proj_margin_01":
            print("  override_audit:")
            print(
                f"    baseline_rejected={row_summary.get('live_variant_baseline_rejected_total')} "
                f"proj_ok={row_summary.get('live_variant_projection_eligible_total')} "
                f"conf_gain_ok={row_summary.get('live_variant_conf_gain_eligible_total')} "
                f"persist_ok={row_summary.get('live_variant_persistence_eligible_total')} "
                f"recovery_ok={row_summary.get('live_variant_recovery_eligible_total')} "
                f"quality_ok={row_summary.get('live_variant_quality_eligible_total')} "
                f"overrides={row_summary.get('live_variant_override_total')}"
            )
            print(
                f"    dominant_block={row_summary.get('live_variant_dominant_block_reason')} "
                f"counts={row_summary.get('live_variant_block_reason_counts')}"
            )
            print(
                f"    override_rounds={row_summary.get('live_variant_override_round_count')}/"
                f"{row_summary.get('rounds_total')} "
                f"({row_summary.get('live_variant_override_round_rate_pct'):.1f}%)"
            )
            print(f"    override_round_ids={row_summary.get('live_variant_override_rounds')}")
    proj_cal = last.get("projection_calibration_metrics", {})
    if proj_cal:
        print("  real forecast :")
        print(f"    corr(pred_gain)    : {proj_cal.get('corr_pred_gain_realized_gain')}")
        print(f"    corr(pred_proj_bad): {proj_cal.get('corr_pred_projection_bad_realized_projection_bad')}")
        print(f"    corr(pred_union)   : {proj_cal.get('corr_pred_union_realized_rollback')}")
    rollback_metrics = last.get("rollback_round_metrics", {})
    if rollback_metrics:
        rows = rollback_metrics.get("selected_round_rows", rollback_metrics.get("round_rows"))
        min_rows = rollback_metrics.get("audit_min_rows_for_recommendation")
        print("  real rollback :")
        print(f"    proj_bad_best : {rollback_metrics.get('best_projection_bad_aggregation')}")
        print(f"    gain_bad_best : {rollback_metrics.get('best_gain_bad_aggregation')}")
        print(f"    goal_bad_best : {rollback_metrics.get('best_goal_bad_aggregation')}")
        if rollback_metrics.get("audit_rows_sufficient"):
            print(f"    rollback_plan : {rollback_metrics.get('rollback_label_recommendation')}")
        else:
            print(f"    rollback_plan : deferred ({rows}/{min_rows} audit rows)")
    benchmark_summary = last.get("benchmark_summary", {})
    if benchmark_summary:
        print("  benchmark     :")
        if benchmark_summary.get("error"):
            print(f"    error        : {benchmark_summary.get('error')}")
        else:
            print(f"    scenarios    : {benchmark_summary.get('scenario_count')}")
            _print_benchmark_compact(benchmark_summary, indent="    ")
            _print_policy_sweep_summary(benchmark_summary, indent="    ")
            print(f"    reports      : {benchmark_summary.get('report_paths')}")
    print(f"  session_log   : {cfg.eval_kwargs['session_log_path']}")


def _print_benchmark_summary(summary: dict) -> None:
    print("\n=== Trusted Benchmark Complete ===")
    print(f"Pack           : {summary.get('benchmark_pack')} v{summary.get('version')}")
    print(f"Scenarios      : {summary.get('scenario_count')}")
    _print_benchmark_compact(summary)
    _print_policy_sweep_summary(summary)
    print(f"Reports        : {summary.get('report_paths')}")


def _print_intervention_summary(result: dict) -> None:
    proposal = dict(result.get("proposal", {}))
    summary = dict(result.get("summary", {}))
    permission = dict(result.get("authority_execution_permission", {}))
    print("\n=== Intervention Runner Complete ===")
    if permission:
        print(f"Execution Mode : {permission.get('permission_state')}")
        print(f"Governance     : {permission.get('reason')}")
    print(f"Proposal ID    : {proposal.get('proposal_id')}")
    print(f"Template       : {proposal.get('template_name')}")
    print(f"Type           : {proposal.get('proposal_type')}")
    print(f"Scope          : {proposal.get('scope')}")
    print(f"Ledger         : {result.get('ledger_path')}")
    print(f"Status         : {proposal.get('promotion_status')}")
    print(f"Trigger        : {proposal.get('trigger_reason')}")
    print(f"Mechanism      : {proposal.get('mechanism')}")
    print(f"Forecast       : {dict(summary.get('forecast', {}))}")
    print(f"Static         : {dict(proposal.get('evaluation', {}).get('static', {}))}")
    print(f"Shadow         : {dict(summary.get('shadow', {}))}")
    print(f"Benchmark      : {dict(summary.get('benchmark', {}))}")
    print(f"Canary         : {dict(summary.get('canary', {}))}")
    print(f"Failure Tags   : {summary.get('failure_tags')}")


def _print_intervention_analytics_summary(summary: dict) -> None:
    compact = dict(summary.get("compact_summary", {}))
    recommendations = dict(compact.get("recommendations", {}))
    permission = dict(summary.get("governance_execution_contract", {}))
    print("\n=== Intervention Ledger Analytics ===")
    if permission:
        print(f"Execution Mode : {permission.get('permission_state')}")
        print(f"Governance     : {permission.get('reason')}")
    print(f"Ledger         : {summary.get('ledger_path')}")
    print(f"Report         : {summary.get('report_path')}")
    print(f"Proposals      : {summary.get('proposal_count')}")
    print("By type        :")
    counts = dict(summary.get("proposal_counts_by_type", {}))
    shadow_rates = dict(summary.get("shadow_pass_rate_by_type", {}))
    benchmark_rates = dict(summary.get("benchmark_pass_rate_by_type", {}))
    canary_rates = dict(summary.get("canary_eligible_rate_by_type", {}))
    mismatch_counts = dict(summary.get("contract_mismatch_counts_by_type", {}))
    final_status_counts = dict(summary.get("final_status_counts_by_type", {}))
    for proposal_type in sorted(counts.keys()):
        print(
            f"  {proposal_type}: n={counts.get(proposal_type)} "
            f"shadow_pass={_fmt_float(shadow_rates.get(proposal_type))} "
            f"bench_pass={_fmt_float(benchmark_rates.get(proposal_type))} "
            f"canary_ok={_fmt_float(canary_rates.get(proposal_type))} "
            f"legacy_mismatch={mismatch_counts.get(proposal_type)} "
            f"final={final_status_counts.get(proposal_type)}"
        )
    dormant = dict(summary.get("dormant_live_override", {}))
    print(
        "Dormancy       : "
        f"count={dormant.get('count')} "
        f"rate={_fmt_float(dormant.get('rate'))} "
        f"types={dormant.get('proposal_type_counts')}"
    )
    print(f"Top failure tags: {summary.get('top_failure_tags')}")
    print(f"Top archive    : {summary.get('top_archive_reasons')}")
    print(f"Top revert     : {summary.get('top_revert_reasons')}")
    print(f"Best families  : {compact.get('best_performing_proposal_families')}")
    print(f"Most dormant   : {compact.get('most_dormant_proposal_families')}")
    print(f"Failure clusters: {compact.get('most_common_failure_clusters')}")
    print(f"Suggest next   : {recommendations.get('suggested_next_templates')}")
    print(f"Deprioritize   : {recommendations.get('deprioritized_templates')}")


def _print_proposal_recommendation_summary(report: dict) -> None:
    memory_index = dict(report.get("memory_index", {}))
    global_summary = dict(report.get("global_summary", {}))
    suggested = list(report.get("suggested_proposals", []))
    deprioritized = list(report.get("deprioritized_proposals", []))
    dominant_blocker = dict(global_summary.get("dominant_blocker", {}))
    permission = dict(report.get("governance_execution_contract", {}))
    print("\n=== Proposal Recommendations ===")
    if permission:
        print(f"Execution Mode : {permission.get('permission_state')}")
        print(f"Governance     : {permission.get('reason')}")
    print(f"Report         : {report.get('report_path', 'generated in-memory')}")
    print(f"Dominant block : {dominant_blocker}")
    print(f"Failure mode   : {global_summary.get('dominant_failure_mode')}")
    print(f"Under-served   : {global_summary.get('dominant_under_served_family')}")
    print(f"Drivers        : {global_summary.get('recommendation_drivers')}")
    print(f"Dormant safe   : {memory_index.get('benchmark_safe_but_dormant')}")
    if suggested:
        print("Suggested next :")
        for row in suggested[:3]:
            print(
                f"  {row.get('template_name')}: "
                f"type={row.get('proposal_type')} "
                f"family={row.get('target_family')} "
                f"score={_fmt_float(row.get('recommended_priority'))} "
                f"driver={row.get('primary_driver')} "
                f"reason={row.get('reason_summary')}"
            )
    if deprioritized:
        print("Deprioritized  :")
        for row in deprioritized[:3]:
            print(
                f"  {row.get('template_name')}: "
                f"type={row.get('proposal_type')} "
                f"family={row.get('target_family')} "
                f"score={_fmt_float(row.get('recommended_priority'))} "
                f"driver={row.get('primary_driver')} "
                f"reason={row.get('reason_summary')}"
            )


def _print_governed_execution_summary(summary: dict[str, Any]) -> None:
    print("\n=== Governed Execution Result ===")
    print(f"Directive ID    : {summary.get('directive_id')}")
    print(f"Execution Mode  : {summary.get('launch_kind')}")
    print(f"Execution Prof. : {summary.get('execution_profile')}")
    print(f"Workspace ID    : {summary.get('workspace_id')}")
    print(f"Workspace Root  : {summary.get('workspace_root')}")
    print(f"Working Dir     : {summary.get('working_directory')}")
    print(f"Generated Root  : {summary.get('generated_output_root')}")
    print(f"Runtime Log     : {summary.get('runtime_event_log_path')}")
    print(f"Session Artifact: {summary.get('session_artifact_path')}")
    print(f"Brief           : {summary.get('brief_path')}")
    print(f"Work Summary    : {summary.get('work_summary_path', '')}")
    print(f"Controller      : {summary.get('controller_artifact_path', '')}")
    print(f"Status          : {summary.get('status')}")
    print(f"Reason          : {summary.get('reason')}")
    controller = dict(summary.get("governed_execution_controller", {}))
    if controller:
        if str(controller.get("controller_mode", "")).strip():
            print(f"Controller Mode : {controller.get('controller_mode', '')}")
        if str(controller.get("invocation_model", "")).strip():
            print(f"Cycle Model     : {controller.get('invocation_model', '')}")
        if controller.get("cycles_completed") not in {None, ""}:
            print(f"Cycles Completed: {controller.get('cycles_completed')}")
        if controller.get("latest_cycle_index") not in {None, ""}:
            print(f"Latest Cycle    : {controller.get('latest_cycle_index')}")
        if str(controller.get("stop_reason", "")).strip():
            print(f"Stop Reason     : {controller.get('stop_reason', '')}")
        completion = dict(controller.get("directive_completion_evaluation", {}))
        if completion:
            print(f"Directive Done  : {completion.get('completed', False)}")
            if str(completion.get("reason", "")).strip():
                print(f"Completion Note : {completion.get('reason', '')}")
    work_cycle = dict(summary.get("work_cycle", {}))
    if work_cycle:
        print(f"Work Item       : {work_cycle.get('work_item_id', '')}")
        if str(work_cycle.get("cycle_kind", "")).strip():
            print(f"Cycle Kind      : {work_cycle.get('cycle_kind', '')}")
        if work_cycle.get("cycle_index") not in {None, ""}:
            print(f"Cycle Index     : {work_cycle.get('cycle_index')}")
        if str(work_cycle.get("implementation_bundle_kind", "")).strip():
            print(f"Impl. Bundle    : {work_cycle.get('implementation_bundle_kind', '')}")
        output_paths = list(work_cycle.get("output_artifact_paths", []))
        if output_paths:
            print(f"Output Count    : {len(output_paths)}")
            for item in output_paths[:6]:
                print(f"  - {item}")
        new_paths = list(work_cycle.get("newly_created_paths", []))
        if new_paths:
            print(f"New Files       : {len(new_paths)}")
            for item in new_paths[:6]:
                print(f"  + {item}")
        if str(work_cycle.get("next_recommended_cycle", "")).strip():
            print(f"Next Cycle      : {work_cycle.get('next_recommended_cycle', '')}")


def main() -> None:
    if _OPERATOR_GUARD_INSTALL_ERROR is not None:
        raise _OPERATOR_GUARD_INSTALL_ERROR

    parser = argparse.ArgumentParser(
        description="Non-canonical developer/test runtime entrypoint for novali-v5. Canonical human-facing local launch is the operator shell."
    )
    parser.add_argument(
        "--directive-file",
        type=str,
        default="",
        help="Formal NOVALI directive bootstrap JSON file. Required for fresh initialization; optional on restart from persisted state.",
    )
    parser.add_argument(
        "--clarification-file",
        type=str,
        default="",
        help="Optional JSON mapping of clarification responses for missing or ambiguous DirectiveSpec fields.",
    )
    parser.add_argument(
        "--bootstrap-only",
        action="store_true",
        help="Materialize or validate canonical governance state and exit before governed execution.",
    )
    parser.add_argument(
        "--governed-execution",
        action="store_true",
        help="Proceed from directive/bootstrap initialization into the canonical governed execution path instead of exiting after bootstrap.",
    )
    parser.add_argument(
        "--state-root",
        type=str,
        default="",
        help="Optional alternate canonical state directory for bootstrap/restart and testing.",
    )
    parser.add_argument("--rounds", type=int, default=None, help="Override training rounds.")
    parser.add_argument("--seed", type=int, default=None, help="Override the base training seed.")
    parser.add_argument("--quiet", action="store_true", help="Reduce training verbosity.")
    parser.add_argument("--benchmark-only", action="store_true", help="Run the frozen benchmark pack without training.")
    parser.add_argument("--benchmark-every", type=int, default=0, help="Run the benchmark pack every N training rounds.")
    parser.add_argument("--benchmark-sweep", action="store_true", help="Run offline benchmark-only provisional policy sweep analysis.")
    parser.add_argument("--proposal-runner", action="store_true", help="Run the structured intervention proposal pipeline.")
    parser.add_argument(
        "--proposal-analytics",
        action="store_true",
        help="Analyze the intervention ledger and write an action-oriented summary report.",
    )
    parser.add_argument(
        "--proposal-recommend",
        action="store_true",
        help="Generate memory-informed next-proposal recommendations from ledger analytics and diagnostic artifacts.",
    )
    parser.add_argument(
        "--proposal-template",
        default="routing_rule.targeted_gain_goal_proj_margin_01",
        help="Intervention proposal template to instantiate.",
    )
    parser.add_argument("--proposal-shadow-rounds", type=int, default=1, help="Shadow rounds for intervention evaluation.")
    parser.add_argument("--proposal-shadow-seeds", type=str, default="", help="Comma-separated seeds for intervention shadow eval.")
    parser.add_argument(
        "--live-policy",
        default="baseline",
        help="Select the live policy variant for training runs.",
    )
    parser.add_argument(
        "--compare-live-ab",
        action="store_true",
        help="Run a matched-seed live A/B comparison between baseline and the selected live-policy variant.",
    )
    parser.add_argument(
        "--ab-seeds",
        type=str,
        default="0,1",
        help="Comma-separated seeds for live A/B comparison.",
    )
    args = parser.parse_args()
    if str(args.state_root).strip():
        os.environ["NOVALI_STATE_ROOT"] = os.path.abspath(str(args.state_root).strip())

    from bootstrap import (
        CanonicalStateConsistencyError,
        ClarificationRequiredError,
        DirectiveBootstrapError,
        DirectiveFileValidationError,
        _print_bootstrap_summary,
        bootstrap_runtime,
    )

    try:
        bootstrap_summary = bootstrap_runtime(
            directive_file=str(args.directive_file) or None,
            clarification_file=str(args.clarification_file) or None,
            state_root=str(args.state_root) or None,
        )
    except ClarificationRequiredError as exc:
        print("\nDirective Clarification Required")
        print(f"Reason          : {exc}")
        for question in exc.questions:
            print(f"  - {question.get('field')}: {question.get('question')}")
        raise SystemExit(2)
    except (DirectiveFileValidationError, CanonicalStateConsistencyError, DirectiveBootstrapError) as exc:
        print("\nNOVALI Bootstrap Failed")
        print(f"Reason          : {exc}")
        for item in list(getattr(exc, "errors", [])):
            print(f"  - {item}")
        raise SystemExit(2)

    explicit_runtime_action_selected = any(
        [
            bool(args.benchmark_only),
            bool(args.proposal_runner),
            bool(args.proposal_analytics),
            bool(args.proposal_recommend),
            bool(args.compare_live_ab),
            bool(args.governed_execution),
        ]
    )
    bootstrap_only_mode = bool(args.bootstrap_only) or (bool(args.directive_file) and not explicit_runtime_action_selected)
    if bool(args.directive_file) or bool(args.bootstrap_only):
        _print_bootstrap_summary(bootstrap_summary)
        if bootstrap_only_mode:
            return

    if args.governed_execution:
        from interventions.governance_memory_execution_gate_v1 import (
            GovernanceExecutionBlockedError,
            build_execution_permission,
            format_execution_permission,
            require_execution_permission,
        )
        from operator_shell.governed_execution import (
            GovernedExecutionFailure,
            run_bounded_governed_execution,
        )

        try:
            permission = build_execution_permission(action_kind="governed_execution")
            require_execution_permission(permission)
            print(f"Governance Preflight: {format_execution_permission(permission)}")
            summary = run_bounded_governed_execution(bootstrap_summary=bootstrap_summary)
            _print_governed_execution_summary(summary)
            return
        except GovernanceExecutionBlockedError as exc:
            print(f"\nGovernance Blocked: {format_execution_permission(exc.permission)}")
            if exc.intake_record:
                print(f"Reopen Intake  : {exc.intake_record.get('artifact_path')}")
                print(
                    "Review State   : "
                    f"{exc.intake_record.get('intake_state')} / "
                    f"{exc.intake_record.get('screening_state')} / "
                    f"{exc.intake_record.get('governance_review_state')}"
                )
            if exc.intake_error:
                print(f"Intake Error   : {exc.intake_error}")
            raise SystemExit(2)
        except GovernedExecutionFailure as exc:
            print("\nGoverned Execution Failed")
            print(f"Reason          : {exc}")
            if exc.session_artifact_path:
                print(f"Session Artifact: {exc.session_artifact_path}")
            if exc.summary_artifact_path:
                print(f"Work Summary    : {exc.summary_artifact_path}")
            raise SystemExit(2)

    import torch

    from interventions.governance_memory_execution_gate_v1 import (
        GovernanceExecutionBlockedError,
        build_execution_permission,
        format_execution_permission,
        require_execution_permission,
    )
    from runtime_config import apply_live_policy_variant, available_live_policy_variants, build_default_config

    torch.set_printoptions(precision=4, sci_mode=False)

    available_live_policies = set(available_live_policy_variants())
    if str(args.live_policy) not in available_live_policies:
        print("\nNOVALI Runtime Configuration Failed")
        print(
            "Reason          : "
            f"--live-policy must be one of {sorted(available_live_policies)}"
        )
        raise SystemExit(2)

    os.makedirs("logs", exist_ok=True)
    cfg = build_default_config(verbose=not args.quiet)
    if args.rounds is not None and args.rounds > 0:
        cfg.rounds = int(args.rounds)
    if args.seed is not None:
        cfg.seed = int(args.seed)
    if int(args.benchmark_every) > 0:
        cfg.benchmark_every_rounds = int(args.benchmark_every)
    apply_live_policy_variant(cfg, str(args.live_policy))

    try:
        if args.benchmark_only:
            permission = build_execution_permission(action_kind="benchmark_only")
            require_execution_permission(permission)
            print(f"Governance Preflight: {format_execution_permission(permission)}")
            from benchmarks.trusted_benchmark_pack_v1.runner import run_trusted_benchmark_pack

            result = run_trusted_benchmark_pack(cfg=cfg, mode="standalone", include_policy_sweep=bool(args.benchmark_sweep))
            _print_benchmark_summary(result["summary"])
            return

        if args.proposal_runner:
            permission = build_execution_permission(
                action_kind="proposal_runner",
                template_name=str(args.proposal_template),
            )
            require_execution_permission(permission)
            print(f"Governance Preflight: {format_execution_permission(permission)}")
            from interventions.runner import run_intervention_proposal

            shadow_seeds = _parse_seed_list(args.proposal_shadow_seeds, cfg.seed)
            result = run_intervention_proposal(
                cfg=cfg,
                template_name=str(args.proposal_template),
                shadow_rounds=max(1, int(args.proposal_shadow_rounds)),
                shadow_seeds=shadow_seeds,
            )
            _print_intervention_summary(result)
            return

        if args.proposal_analytics:
            permission = build_execution_permission(action_kind="proposal_analytics")
            require_execution_permission(permission)
            print(f"Governance Preflight: {format_execution_permission(permission)}")
            from interventions.analytics import write_intervention_ledger_analytics_report

            summary = write_intervention_ledger_analytics_report()
            _print_intervention_analytics_summary(summary)
            return

        if args.proposal_recommend:
            permission = build_execution_permission(action_kind="proposal_recommend")
            require_execution_permission(permission)
            print(f"Governance Preflight: {format_execution_permission(permission)}")
            from interventions.recommendations import write_proposal_recommendations_report

            report = write_proposal_recommendations_report()
            _print_proposal_recommendation_summary(report)
            return

        if args.compare_live_ab:
            permission = build_execution_permission(action_kind="compare_live_ab")
            require_execution_permission(permission)
            print(f"Governance Preflight: {format_execution_permission(permission)}")
            variant_name = str(args.live_policy)
            if variant_name == "baseline":
                variant_name = "targeted_gain_goal_proj_margin_01"
            seeds = _parse_seed_list(args.ab_seeds, cfg.seed)
            summary = _run_live_policy_ab(
                base_cfg=cfg,
                variant_name=variant_name,
                seeds=seeds,
            )
            _print_live_ab_summary(summary)
            return

        permission = build_execution_permission(action_kind="training_loop")
        require_execution_permission(permission)
        print(f"Governance Preflight: {format_execution_permission(permission)}")
        print("\n=== Starting Consciousness Lab Simulation (9D core build) ===\n")
        from experiments.proposal_learning_loop import run_proposal_learning_loop

        triad, pops, history = run_proposal_learning_loop(cfg)
        _ = (triad, pops)
        print("\n=== Simulation Complete ===")

        if history:
            _print_training_summary(history[-1], cfg)
        print("\n")
    except GovernanceExecutionBlockedError as exc:
        print(f"\nGovernance Blocked: {format_execution_permission(exc.permission)}")
        if exc.intake_record:
            print(f"Reopen Intake  : {exc.intake_record.get('artifact_path')}")
            print(
                "Review State   : "
                f"{exc.intake_record.get('intake_state')} / "
                f"{exc.intake_record.get('screening_state')} / "
                f"{exc.intake_record.get('governance_review_state')}"
            )
        if exc.intake_error:
            print(f"Intake Error   : {exc.intake_error}")
        raise SystemExit(2)


if __name__ == "__main__":
    try:
        main()
    except OperatorConstraintViolationError as exc:
        print(f"\nOperator Constraint Blocked: {exc}")
        print(f"Constraint ID  : {exc.constraint_id}")
        print(f"Enforcement    : {exc.enforcement_class}")
        raise SystemExit(2)

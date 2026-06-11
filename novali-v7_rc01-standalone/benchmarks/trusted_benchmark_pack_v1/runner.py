from __future__ import annotations

import argparse
import copy
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch

from agents.world_model import RSSMWorldModel
from evolution.multi_agent_eval_comms import evaluate_group_with_comms
from evolution.triad_propose_personal_dummies import summarize_logs, triad_propose_test_personal_dummies
from experiments.proposal_learning_loop import (
    ProposalLearningConfig,
    SimpleTriadEnv,
    _build_forecast_context,
    _compute_goal_pressure,
    _compute_projected_outcome_signal,
    _compute_social_confidence,
    _compute_social_improvement_signal,
    _default_eval_kwargs,
    _extract_env_reset_obs,
    _extract_explicit_9d_metrics,
    _last_metric,
    _make_metrics_dict,
    _normalize_gain_target,
    _rollback_cause_label,
    _safe_adopt_patch,
    _safe_mean_arr,
    _scale_patch,
    _seed_all,
    _world_model_shadow_rollout,
    build_triad,
    clone_personal_dummies,
    make_proposal_population,
)
from interventions.governance_memory_execution_gate_v1 import (
    GovernanceExecutionBlockedError,
    build_execution_permission,
    format_execution_permission,
    require_execution_permission,
)
from runtime_config import build_default_config

from .scenario_factory import PACK_NAME, PACK_VERSION, build_frozen_scenarios, write_frozen_pack
from .rubrics.score_gain_goal import score_gain_goal_family
from .rubrics.score_persistence import score_persistence_family
from .rubrics.score_projection import score_projection_family


def _pack_dir() -> Path:
    return Path(__file__).resolve().parent


def _reports_dir() -> Path:
    path = _pack_dir() / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _session_log_path() -> str:
    return str(_reports_dir() / "benchmark_session.log")


def _to_jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (str, bool)) or obj is None:
        return obj
    if isinstance(obj, (np.floating, float)):
        val = float(obj)
        return val if math.isfinite(val) else None
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return _to_jsonable(obj.tolist())
    if torch.is_tensor(obj):
        return _to_jsonable(obj.detach().cpu().tolist())
    return obj


def _coerce_avg(score_obj: Any) -> float:
    if isinstance(score_obj, (list, tuple, np.ndarray)):
        arr = np.asarray(score_obj, dtype=np.float32)
        if arr.size == 0:
            return 0.0
        return float(np.nanmean(arr))
    return float(score_obj)


def _clone_world_model(cfg: ProposalLearningConfig, world_model: Optional[RSSMWorldModel]) -> Optional[RSSMWorldModel]:
    if world_model is None:
        return None
    device = torch.device(cfg.device)
    clone = RSSMWorldModel(
        state_dim=cfg.state_dim,
        action_dim=cfg.state_dim,
        latent_dim=cfg.wm_latent_dim,
        hidden_dim=cfg.wm_hidden_dim,
    ).to(device)
    clone.load_state_dict(world_model.state_dict(), strict=False)
    if hasattr(world_model, "snapshot_internal_state") and hasattr(clone, "restore_internal_state"):
        clone.restore_internal_state(world_model.snapshot_internal_state())
    clone.eval()
    return clone


def _clone_triad(cfg: ProposalLearningConfig, triad: Sequence[Any]) -> List[Any]:
    clone = build_triad(cfg)
    device = torch.device(cfg.device)
    for dst, src in zip(clone, triad):
        dst.load_state_dict(src.state_dict(), strict=False)
        dst.to(device)
        dst.eval()
    return clone


def _clone_pops(cfg: ProposalLearningConfig, triad: Sequence[Any], pops: Sequence[Sequence[Any]]) -> List[List[Any]]:
    patch_template = triad[0].get_patch_state()
    pop_clones = [make_proposal_population(cfg, patch_template) for _ in range(len(pops))]
    device = torch.device(cfg.device)
    for dst_group, src_group in zip(pop_clones, pops):
        for dst, src in zip(dst_group, src_group):
            dst.load_state_dict(src.state_dict(), strict=False)
            dst.to(device)
            dst.eval()
    return pop_clones


def _build_fresh_runtime(cfg: ProposalLearningConfig) -> Tuple[List[Any], List[List[Any]], Optional[RSSMWorldModel]]:
    _seed_all(int(cfg.seed))
    triad = build_triad(cfg)
    device = torch.device(cfg.device)
    for agent in triad:
        agent.to(device)
        agent.eval()
    world_model: Optional[RSSMWorldModel] = None
    if cfg.use_world_model:
        world_model = RSSMWorldModel(
            state_dim=cfg.state_dim,
            action_dim=cfg.state_dim,
            latent_dim=cfg.wm_latent_dim,
            hidden_dim=cfg.wm_hidden_dim,
        ).to(device)
        world_model.eval()
    patch_template = triad[0].get_patch_state()
    pops = [make_proposal_population(cfg, patch_template) for _ in range(3)]
    for proposer_pop in pops:
        for net in proposer_pop:
            net.to(device)
            net.eval()
    return triad, pops, world_model


def _benchmark_eval_group(
    *,
    agents: Sequence[Any],
    cfg: ProposalLearningConfig,
    env: SimpleTriadEnv,
    world_model: Optional[RSSMWorldModel],
    steps: int,
    eval_kwargs: Dict[str, Any],
) -> Tuple[Any, Dict[str, Any]]:
    replay: List[Tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = []
    return evaluate_group_with_comms(
        agents=agents,
        env=env,
        steps=int(steps),
        critical_entropy=cfg.critical_entropy,
        world_model=world_model,
        wm_optimizer=None,
        wm_replay=replay,
        wm_train_every=cfg.wm_train_every,
        wm_batch_size=cfg.wm_batch_size,
        wm_min_replay=cfg.wm_min_replay,
        wm_beta_kl=cfg.wm_beta_kl,
        plan_horizon=cfg.plan_horizon,
        plan_candidates=cfg.plan_candidates,
        plan_noise_std=cfg.plan_noise_std,
        plan_action_clip=cfg.plan_action_clip,
        use_planning=cfg.use_planning,
        cfg=cfg,
        **eval_kwargs,
    )


def _default_runtime_context() -> Dict[str, Any]:
    return {
        "round_index": 0,
        "proposer_credit": [0.0, 0.0, 0.0],
        "proposer_cooldown": [0, 0, 0],
        "proposer_recent_realized": [0.0, 0.0, 0.0],
        "proposer_recent_goal": [0.0, 0.0, 0.0],
        "proposer_rollback_rate": [0.0, 0.0, 0.0],
        "instability_state": [0.0, 0.0, 0.0],
        "self_best_streak": [0, 0, 0],
        "self_score_history": [[], [], []],
        "provisional_owner": [-1, -1, -1],
        "provisional_evidence": [0.0, 0.0, 0.0],
        "provisional_rounds": [0, 0, 0],
        "realized_gain_history": [],
    }


def _ctx_list(ctx: Dict[str, Any], key: str, length: int, default: float) -> List[float]:
    values = list(ctx.get(key, [default] * length))
    if len(values) < length:
        values.extend([default] * (length - len(values)))
    return values[:length]


def _make_benchmark_eval_kwargs(cfg: ProposalLearningConfig, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    merged = _default_eval_kwargs()
    merged.update(cfg.eval_kwargs or {})
    if overrides:
        merged.update(overrides)
    merged["debug_nan"] = False
    merged["log_telemetry"] = False
    merged["session_log_path"] = _session_log_path()
    return merged


def _make_benchmark_env(cfg: ProposalLearningConfig, *, seed: int, steps: int, noise_scale: float, horizon_pad: int) -> SimpleTriadEnv:
    return SimpleTriadEnv(
        state_dim=cfg.state_dim,
        seed=int(seed),
        noise_scale=float(noise_scale),
        horizon=max(int(steps), int(cfg.steps_dummy), int(cfg.steps_baseline)) + int(horizon_pad),
    )


def _build_candidate_bank(
    *,
    cfg: ProposalLearningConfig,
    triad: Sequence[Any],
    pops: Sequence[Sequence[Any]],
    world_model: Optional[RSSMWorldModel],
    runtime_context: Dict[str, Any],
) -> Dict[str, Any]:
    eval_kwargs = _make_benchmark_eval_kwargs(cfg)
    base_noise = float(eval_kwargs.get("noise_scale", 0.01))
    base_seed = int(cfg.seed + 500_000 + 17 * int(runtime_context.get("round_index", 0)))
    baseline_env = _make_benchmark_env(
        cfg,
        seed=base_seed,
        steps=int(cfg.steps_baseline),
        noise_scale=base_noise,
        horizon_pad=8,
    )
    baseline_score, baseline_logs = _benchmark_eval_group(
        agents=triad,
        cfg=cfg,
        env=baseline_env,
        world_model=_clone_world_model(cfg, world_model),
        steps=int(cfg.steps_baseline),
        eval_kwargs=eval_kwargs,
    )
    base_avg = _coerce_avg(baseline_score)
    metrics = _make_metrics_dict(baseline_logs)
    baseline_9d_metrics = _extract_explicit_9d_metrics(baseline_logs)
    base_goal_mse = _last_metric(baseline_logs, "goal_mse_latent", 0.0)
    goal_pressure = _compute_goal_pressure(
        base_goal_mse,
        soft=float(cfg.adaptive_patch_goal_mse_soft),
        hard=float(cfg.adaptive_patch_goal_mse_hard),
    )

    rng = np.random.default_rng(int(base_seed + 91))
    proposals: List[Dict[str, torch.Tensor]] = []
    for proposer_idx in range(3):
        sample_k = max(1, int(getattr(cfg, "sample_k", 1)))
        idxs = rng.integers(0, cfg.pop_size, size=sample_k)
        deltas_list = [pops[proposer_idx][int(j)](metrics) for j in idxs]
        avg_delta: Dict[str, torch.Tensor] = {}
        for key in deltas_list[0].keys():
            avg_delta[key] = sum(delta[key] for delta in deltas_list) / float(sample_k)
        proposals.append(avg_delta)

    personal_dummies = clone_personal_dummies(list(triad))
    for dummy in personal_dummies:
        dummy.to(torch.device(cfg.device))
    _, _, proposals_out, improvements, patch_sizes, dummy_logs = triad_propose_test_personal_dummies(
        triad_agents=list(triad),
        personal_dummies=personal_dummies,
        proposals=proposals,
        world_model=_clone_world_model(cfg, world_model),
        wm_optimizer=None,
        wm_replay=[],
        cfg=cfg,
        eval_kwargs=eval_kwargs,
    )
    improvements = np.asarray(improvements, dtype=np.float32)
    patch_sizes = np.asarray(patch_sizes, dtype=np.float32)
    local_scores = np.asarray(dummy_logs.get("score_matrix", np.zeros((3, 3), dtype=np.float32)), dtype=np.float32)

    shadow_env = _make_benchmark_env(
        cfg,
        seed=int(base_seed + 777),
        steps=int(cfg.steps_dummy),
        noise_scale=base_noise,
        horizon_pad=8,
    )
    shadow_start_obs = _extract_env_reset_obs(shadow_env, n_agents=len(triad), state_dim=cfg.state_dim)
    forecast_horizon = int(cfg.steps_dummy if cfg.wm_candidate_projection_match_post_horizon else cfg.wm_candidate_projection_horizon)
    baseline_shadow = _world_model_shadow_rollout(
        agents=list(triad),
        world_model=_clone_world_model(cfg, world_model),
        start_obs=shadow_start_obs,
        horizon=forecast_horizon,
        samples=int(cfg.wm_candidate_projection_samples),
        gamma=float(cfg.wm_candidate_projection_gamma),
        seed_base=int(base_seed + 1555),
    )

    candidates: Dict[str, Dict[str, Any]] = {}
    for target in range(3):
        for proposer in range(3):
            candidate_id = f"A{target}<=P{proposer}"
            candidates[candidate_id] = {
                "candidate_id": candidate_id,
                "target_agent": int(target),
                "proposer": int(proposer),
                "dummy_improvement": float(improvements[target, proposer]),
                "local_score": float(local_scores[target, proposer]),
                "patch_size": float(patch_sizes[target, proposer]),
                "patch": {k: v.detach().cpu().clone() for k, v in proposals_out[proposer].items()},
            }

    return {
        "base_avg": float(base_avg),
        "baseline_logs": dict(baseline_logs),
        "baseline_9d_metrics": dict(baseline_9d_metrics),
        "base_goal_mse": float(base_goal_mse),
        "goal_pressure": float(goal_pressure),
        "proposals_out": proposals_out,
        "improvements": improvements.copy(),
        "patch_sizes": patch_sizes.copy(),
        "local_scores": local_scores.copy(),
        "baseline_shadow": dict(baseline_shadow),
        "shadow_start_obs": None if shadow_start_obs is None else np.asarray(shadow_start_obs, dtype=np.float32).copy(),
        "candidates": candidates,
    }


def _compute_adaptive_scale(
    *,
    cfg: ProposalLearningConfig,
    goal_pressure: float,
    proposer_credit: float,
    proposer_cooldown: int,
    instability: float,
) -> float:
    scale = float(cfg.adaptive_patch_scale_max)
    scale *= (1.0 - float(cfg.adaptive_patch_instability_weight) * float(np.clip(instability, 0.0, 1.0)))
    scale *= (1.0 - 0.55 * float(goal_pressure))
    scale *= (1.0 + float(cfg.adaptive_patch_credit_weight) * float(np.tanh(proposer_credit)))
    if int(proposer_cooldown) > 0:
        scale = min(scale, float(cfg.adaptive_patch_cooldown_floor))
    return float(np.clip(scale, float(cfg.adaptive_patch_scale_min), float(cfg.adaptive_patch_scale_max)))


def _scenario_seed(scenario: Dict[str, Any], salt: int) -> int:
    return int(scenario.get("seed", 0)) + int(salt)


def _scenario_thresholds(cfg: ProposalLearningConfig, scenario: Dict[str, Any]) -> Dict[str, float]:
    return {
        "gain_threshold": float(getattr(cfg, "rollback_min_gain", -0.5)),
        "goal_threshold": float(getattr(cfg, "rollback_max_goal_mse_increase", 0.10)),
        "projection_threshold": float(cfg.adoption_full_projection_error_max),
    }


def _scenario_runtime_features(
    *,
    cfg: ProposalLearningConfig,
    scenario: Dict[str, Any],
    candidate: Dict[str, Any],
    candidate_bank: Dict[str, Any],
    runtime_context: Dict[str, Any],
) -> Dict[str, Any]:
    proposer = int(candidate["proposer"])
    target = int(candidate["target_agent"])
    overrides = dict(scenario.get("context_overrides", {}))
    candidate_overrides = dict(scenario.get("candidate_overrides", {}))

    proposer_credit = float(_ctx_list(runtime_context, "proposer_credit", 3, 0.0)[proposer])
    proposer_cooldown = int(_ctx_list(runtime_context, "proposer_cooldown", 3, 0.0)[proposer])
    proposer_recent_realized = float(_ctx_list(runtime_context, "proposer_recent_realized", 3, 0.0)[proposer])
    proposer_rollback_rate = float(_ctx_list(runtime_context, "proposer_rollback_rate", 3, 0.0)[proposer])
    instability = float(_ctx_list(runtime_context, "instability_state", 3, 0.0)[proposer])
    self_best_streak = int(_ctx_list(runtime_context, "self_best_streak", 3, 0.0)[proposer])
    self_score_history = runtime_context.get("self_score_history", [[], [], []])
    moving_average = _safe_mean_arr(self_score_history[proposer][-4:] if proposer < len(self_score_history) else [], default=0.0)
    provisional_owner = [int(v) for v in _ctx_list(runtime_context, "provisional_owner", 3, -1.0)]
    provisional_evidence = _ctx_list(runtime_context, "provisional_evidence", 3, 0.0)
    provisional_rounds = [int(v) for v in _ctx_list(runtime_context, "provisional_rounds", 3, 0.0)]
    retained_evidence = float(provisional_evidence[target]) if provisional_owner[target] == proposer else 0.0
    retained_rounds = int(provisional_rounds[target]) if provisional_owner[target] == proposer else 0

    moving_average += float(overrides.get("moving_average_bias", 0.0))
    self_best_streak = max(0, self_best_streak + int(overrides.get("persistence_streak_delta", 0)))
    retained_evidence = float(np.clip(retained_evidence + float(overrides.get("retained_evidence_bias", 0.0)), 0.0, 1.0))
    retained_rounds = max(0, retained_rounds + int(overrides.get("retained_rounds_delta", 0)))
    proposer_recent_realized += float(overrides.get("recent_realized_bias", 0.0))
    proposer_rollback_rate = float(np.clip(proposer_rollback_rate + float(overrides.get("rollback_rate_bias", 0.0)), 0.0, 1.0))
    instability = float(np.clip(instability + float(overrides.get("instability_bias", 0.0)), 0.0, 1.0))

    dummy_improvement = float(candidate["dummy_improvement"]) + float(candidate_overrides.get("dummy_improvement_bias", 0.0))
    local_score = float(candidate["local_score"]) + float(candidate_overrides.get("local_score_bias", 0.0))
    patch_size = max(0.0, float(candidate["patch_size"]) + float(candidate_overrides.get("patch_size_bias", 0.0)))
    goal_pressure = float(np.clip(candidate_bank["goal_pressure"] + float(overrides.get("goal_pressure_bias", 0.0)), 0.0, 1.5))
    projection_error = max(
        0.0,
        float(candidate_bank["baseline_9d_metrics"].get("projection_error", 0.0)) + float(candidate_overrides.get("projection_error_bias", 0.0)),
    )

    confidence = _compute_social_confidence(
        cfg=cfg,
        local_score=local_score,
        moving_average=moving_average,
        persistence_streak=self_best_streak,
        c2_strength=float(candidate_bank["baseline_9d_metrics"].get("C2_self_model_strength", 0.0) + float(overrides.get("c2_recent_bias", 0.0))),
        c3_stability=float(candidate_bank["baseline_9d_metrics"].get("C3_perspective_stability", 0.0) + float(overrides.get("c3_recent_bias", 0.0))),
        patch_size=patch_size,
        retained_evidence=retained_evidence,
    )
    gain_signal = _compute_social_improvement_signal(
        cfg=cfg,
        dummy_improvement=dummy_improvement,
        local_score=local_score,
        recent_realized=proposer_recent_realized,
        proposer_credit=proposer_credit,
        rollback_rate=proposer_rollback_rate,
        projection_error=projection_error,
        goal_pressure=goal_pressure,
        instability=instability,
        patch_size=patch_size,
    )
    adaptive_scale = _compute_adaptive_scale(
        cfg=cfg,
        goal_pressure=goal_pressure,
        proposer_credit=proposer_credit,
        proposer_cooldown=proposer_cooldown,
        instability=instability,
    )
    forecast_context = _build_forecast_context(
        cfg=cfg,
        baseline_logs=candidate_bank["baseline_logs"],
        baseline_9d_metrics=candidate_bank["baseline_9d_metrics"],
        proposer_recent_realized=proposer_recent_realized,
        proposer_rollback_rate=proposer_rollback_rate,
        retained_evidence=retained_evidence,
        retained_rounds=retained_rounds,
        realized_gain_history=list(runtime_context.get("realized_gain_history", [])),
    )
    for key, field in (
        ("t2_recent_bias", "t2_recent"),
        ("t3_recent_bias", "t3_recent"),
        ("c1_recent_bias", "c1_recent"),
        ("c2_recent_bias", "c2_recent"),
        ("c3_recent_bias", "c3_recent"),
        ("projection_recent_bias", "projection_recent"),
        ("projection_trend_bias", "projection_trend"),
        ("wm_quality_penalty_bias", "wm_quality_penalty"),
    ):
        forecast_context[field] = float(forecast_context.get(field, 0.0) + float(overrides.get(key, 0.0)))
    forecast_context["dummy_improvement"] = float(dummy_improvement)
    forecast_context["gain_cal"] = float(gain_signal["calibrated_gain"])
    forecast_context["coherence_cal"] = float(confidence["calibrated_confidence"])
    forecast_context["goal_pressure"] = float(goal_pressure)

    return {
        "dummy_improvement": float(dummy_improvement),
        "local_score": float(local_score),
        "patch_size": float(patch_size),
        "goal_pressure": float(goal_pressure),
        "projection_error": float(projection_error),
        "moving_average": float(moving_average),
        "persistence_streak": int(self_best_streak),
        "retained_evidence": float(retained_evidence),
        "retained_rounds": int(retained_rounds),
        "confidence": confidence,
        "gain_signal": gain_signal,
        "adaptive_scale": float(adaptive_scale),
        "forecast_context": forecast_context,
    }


def _make_scenario_shadow_start_obs(cfg: ProposalLearningConfig, scenario: Dict[str, Any], eval_kwargs: Dict[str, Any]) -> np.ndarray:
    env_cfg = dict(scenario.get("env", {}))
    noise_scale = float(env_cfg.get("noise_scale", eval_kwargs.get("noise_scale", 0.01)))
    steps = int(env_cfg.get("steps", cfg.steps_dummy))
    horizon_pad = int(env_cfg.get("horizon_pad", 8))
    env = _make_benchmark_env(
        cfg,
        seed=_scenario_seed(scenario, 771),
        steps=steps,
        noise_scale=noise_scale,
        horizon_pad=horizon_pad,
    )
    obs = _extract_env_reset_obs(env, n_agents=3, state_dim=cfg.state_dim)
    if obs is None:
        return np.zeros((3, cfg.state_dim), dtype=np.float32)
    return np.asarray(obs, dtype=np.float32)


def _run_projected_signal_for_scale(
    *,
    cfg: ProposalLearningConfig,
    scenario: Dict[str, Any],
    triad: Sequence[Any],
    world_model: Optional[RSSMWorldModel],
    candidate: Dict[str, Any],
    patch_scale: float,
    scenario_start_obs: np.ndarray,
    baseline_shadow: Dict[str, Any],
    forecast_context: Dict[str, Any],
) -> Dict[str, Any]:
    if world_model is None:
        return {"available": False}
    scenario_agents = _clone_triad(cfg, triad)
    if float(patch_scale) > 0.0:
        _safe_adopt_patch(
            scenario_agents[int(candidate["target_agent"])],
            _scale_patch(candidate["patch"], float(patch_scale)),
        )
    candidate_shadow = _world_model_shadow_rollout(
        agents=scenario_agents,
        world_model=_clone_world_model(cfg, world_model),
        start_obs=scenario_start_obs,
        horizon=int(cfg.steps_dummy if cfg.wm_candidate_projection_match_post_horizon else cfg.wm_candidate_projection_horizon),
        samples=int(cfg.wm_candidate_projection_samples),
        gamma=float(cfg.wm_candidate_projection_gamma),
        seed_base=_scenario_seed(scenario, 1900 + int(candidate["target_agent"]) * 17 + int(candidate["proposer"]) * 7),
    )
    return _compute_projected_outcome_signal(
        cfg=cfg,
        baseline_shadow=baseline_shadow,
        candidate_shadow=candidate_shadow,
        forecast_context=forecast_context,
    )


def _run_decision_eval(
    *,
    cfg: ProposalLearningConfig,
    scenario: Dict[str, Any],
    triad: Sequence[Any],
    world_model: Optional[RSSMWorldModel],
    candidate: Dict[str, Any],
    eval_kwargs: Dict[str, Any],
    decision_status: str,
    patch_scale: float,
) -> Dict[str, Any]:
    env_cfg = dict(scenario.get("env", {}))
    steps = int(env_cfg.get("steps", cfg.steps_dummy))
    noise_scale = float(env_cfg.get("noise_scale", eval_kwargs.get("noise_scale", 0.01)))
    horizon_pad = int(env_cfg.get("horizon_pad", 8))
    env = _make_benchmark_env(
        cfg,
        seed=_scenario_seed(scenario, 2048),
        steps=steps,
        noise_scale=noise_scale,
        horizon_pad=horizon_pad,
    )
    agents = _clone_triad(cfg, triad)
    if decision_status != "reject" and float(patch_scale) > 0.0:
        _safe_adopt_patch(
            agents[int(candidate["target_agent"])],
            _scale_patch(candidate["patch"], float(patch_scale)),
        )
    score_obj, logs = _benchmark_eval_group(
        agents=agents,
        cfg=cfg,
        env=env,
        world_model=_clone_world_model(cfg, world_model),
        steps=steps,
        eval_kwargs=eval_kwargs,
    )
    avg = _coerce_avg(score_obj)
    summary = summarize_logs(logs)
    metrics_9d = _extract_explicit_9d_metrics(logs)
    return {
        "status": decision_status,
        "patch_scale": float(patch_scale),
        "score_avg": float(avg),
        "goal_mse": float(_last_metric(logs, "goal_mse_latent", 0.0)),
        "goal_agreement": float(_last_metric(logs, "goal_agreement", 0.0)),
        "projection_error": float(metrics_9d.get("projection_error", 0.0)),
        "summary": summary,
        "metrics_9d": metrics_9d,
    }


def _decision_utility(
    *,
    cfg: ProposalLearningConfig,
    scenario: Dict[str, Any],
    decision_result: Dict[str, Any],
    thresholds: Dict[str, float],
    gain_history: List[float],
) -> float:
    weights = dict(scenario.get("decision_scoring", {}))
    gain_norm = _normalize_gain_target(float(decision_result["realized_gain"]), gain_history)
    projection_margin = float(thresholds["projection_threshold"] - float(decision_result["projection_error"]))
    goal_margin = float(thresholds["goal_threshold"] - float(decision_result["realized_goal_delta"]))
    projection_margin_norm = float(np.tanh(projection_margin / max(float(thresholds["projection_threshold"]), 1e-6)))
    goal_margin_norm = float(np.tanh(goal_margin / max(float(thresholds["goal_threshold"]), 1e-6)))
    utility = (
        float(weights.get("gain_weight", 1.0)) * gain_norm
        + float(weights.get("projection_margin_weight", 1.0)) * projection_margin_norm
        + float(weights.get("goal_margin_weight", 1.0)) * goal_margin_norm
    )
    utility -= float(weights.get("projection_bad_penalty", 1.0)) * float(decision_result["projection_bad"])
    utility -= float(weights.get("gain_bad_penalty", 1.0)) * float(decision_result["gain_bad"])
    utility -= float(weights.get("goal_bad_penalty", 1.0)) * float(decision_result["goal_bad"])
    utility += float(weights.get(f"status_bonus_{decision_result['status']}", 0.0))
    return float(utility)


def _evaluate_scenario(
    *,
    cfg: ProposalLearningConfig,
    triad: Sequence[Any],
    world_model: Optional[RSSMWorldModel],
    candidate_bank: Dict[str, Any],
    scenario: Dict[str, Any],
    runtime_context: Dict[str, Any],
) -> Dict[str, Any]:
    candidate_id = f"A{int(scenario['target_agent'])}<=P{int(scenario['proposer'])}"
    candidate = dict(candidate_bank["candidates"][candidate_id])
    eval_kwargs = _make_benchmark_eval_kwargs(cfg, overrides=dict(scenario.get("eval_overrides", {})))
    thresholds = _scenario_thresholds(cfg, scenario)
    runtime_features = _scenario_runtime_features(
        cfg=cfg,
        scenario=scenario,
        candidate=candidate,
        candidate_bank=candidate_bank,
        runtime_context=runtime_context,
    )
    scenario_start_obs = _make_scenario_shadow_start_obs(cfg, scenario, eval_kwargs)
    baseline_shadow = _world_model_shadow_rollout(
        agents=list(triad),
        world_model=_clone_world_model(cfg, world_model),
        start_obs=scenario_start_obs,
        horizon=int(cfg.steps_dummy if cfg.wm_candidate_projection_match_post_horizon else cfg.wm_candidate_projection_horizon),
        samples=int(cfg.wm_candidate_projection_samples),
        gamma=float(cfg.wm_candidate_projection_gamma),
        seed_base=_scenario_seed(scenario, 1666),
    )
    projected_reject = _compute_projected_outcome_signal(
        cfg=cfg,
        baseline_shadow=baseline_shadow,
        candidate_shadow=baseline_shadow,
        forecast_context=runtime_features["forecast_context"],
    )
    projected_full = _run_projected_signal_for_scale(
        cfg=cfg,
        scenario=scenario,
        triad=triad,
        world_model=world_model,
        candidate=candidate,
        patch_scale=float(runtime_features["adaptive_scale"]),
        scenario_start_obs=scenario_start_obs,
        baseline_shadow=baseline_shadow,
        forecast_context=runtime_features["forecast_context"],
    )
    projected_provisional = _run_projected_signal_for_scale(
        cfg=cfg,
        scenario=scenario,
        triad=triad,
        world_model=world_model,
        candidate=candidate,
        patch_scale=float(runtime_features["adaptive_scale"]) * float(cfg.social_conf_provisional_patch_scale),
        scenario_start_obs=scenario_start_obs,
        baseline_shadow=baseline_shadow,
        forecast_context=runtime_features["forecast_context"],
    )

    confidence = runtime_features["confidence"]
    gain_signal = runtime_features["gain_signal"]
    dummy_improvement = float(runtime_features["dummy_improvement"])
    local_score = float(runtime_features["local_score"])
    passed_conf_stage = bool(
        float(confidence["calibrated_confidence"]) >= float(confidence["provisional_threshold"])
        and local_score >= float(cfg.social_conf_min_local_score)
    )
    passed_gain_stage = bool(
        passed_conf_stage
        and float(gain_signal["calibrated_gain"]) >= float(gain_signal["provisional_threshold"])
        and dummy_improvement > 0.0
    )
    projection_ok_provisional = bool(
        (not bool(projected_full.get("available", False)))
        or float(projected_full.get("pred_projection_bad_prob", 1.0)) <= float(cfg.wm_candidate_pred_projection_bad_max_provisional)
    )
    projection_ok_full = bool(
        bool(projected_full.get("available", False))
        and float(projected_full.get("pred_projection_bad_prob", 1.0)) <= float(cfg.wm_candidate_pred_projection_bad_max_full)
    )
    rollback_union_ok_full = bool(
        bool(projected_full.get("available", False))
        and float(projected_full.get("pred_rollback_union", 1.0)) <= float(cfg.wm_candidate_pred_rollback_union_max_full)
    )
    full_ready = bool(
        passed_gain_stage
        and float(confidence["calibrated_confidence"]) >= float(confidence["full_threshold"])
        and float(gain_signal["calibrated_gain"]) >= float(gain_signal["full_threshold"])
        and dummy_improvement >= float(cfg.social_conf_full_improvement_min)
        and local_score >= float(cfg.social_conf_full_local_min)
        and bool(gain_signal.get("projection_ok_full", False))
        and projection_ok_full
        and rollback_union_ok_full
        and float(projected_full.get("calibrated_projected", 0.0)) >= float(cfg.wm_candidate_pred_score_threshold_full)
        and float(projected_full.get("pred_gain_sign_prob", 0.0)) >= float(cfg.wm_candidate_pred_gain_sign_min_full)
    )
    if not passed_gain_stage or not projection_ok_provisional:
        policy_decision = "reject"
    elif full_ready:
        policy_decision = "full"
    else:
        policy_decision = "provisional"

    reject_result = _run_decision_eval(
        cfg=cfg,
        scenario=scenario,
        triad=triad,
        world_model=world_model,
        candidate=candidate,
        eval_kwargs=eval_kwargs,
        decision_status="reject",
        patch_scale=0.0,
    )
    base_avg = float(reject_result["score_avg"])
    base_goal_mse = float(reject_result["goal_mse"])

    decision_results: Dict[str, Dict[str, Any]] = {"reject": dict(reject_result)}
    for status, scale, predicted in (
        ("provisional", float(runtime_features["adaptive_scale"]) * float(cfg.social_conf_provisional_patch_scale), projected_provisional),
        ("full", float(runtime_features["adaptive_scale"]), projected_full),
    ):
        result = _run_decision_eval(
            cfg=cfg,
            scenario=scenario,
            triad=triad,
            world_model=world_model,
            candidate=candidate,
            eval_kwargs=eval_kwargs,
            decision_status=status,
            patch_scale=scale,
        )
        result["predicted"] = predicted
        decision_results[status] = result

    decision_results["reject"]["predicted"] = projected_reject
    gain_history = list(runtime_context.get("realized_gain_history", []))
    if not gain_history:
        gain_history = [0.0]
    for result in decision_results.values():
        result["realized_gain"] = float(result["score_avg"] - base_avg)
        result["realized_goal_delta"] = float(result["goal_mse"] - base_goal_mse)
        result["gain_bad"] = bool(result["realized_gain"] < float(thresholds["gain_threshold"]))
        result["goal_bad"] = bool(result["realized_goal_delta"] > float(thresholds["goal_threshold"]))
        result["projection_bad"] = bool(float(result["projection_error"]) > float(thresholds["projection_threshold"]))
        result["rollback_union"] = bool(result["gain_bad"] or result["goal_bad"] or result["projection_bad"])
        result["rollback_cause"] = _rollback_cause_label(
            bool(result["gain_bad"]),
            bool(result["goal_bad"]),
            bool(result["projection_bad"]),
        )
        predicted = dict(result.get("predicted", {}))
        result["pred_gain_sign_prob"] = float(predicted.get("pred_gain_sign_prob", 0.5))
        result["pred_gain_bad_prob"] = float(predicted.get("pred_gain_bad_prob", 0.5))
        result["pred_goal_bad_prob"] = float(predicted.get("pred_goal_bad_prob", 0.5))
        result["pred_projection_bad_prob"] = float(predicted.get("pred_projection_bad_prob", 0.5))
        result["pred_rollback_union"] = float(predicted.get("pred_rollback_union", 0.5))
        result["forecast_gain_sign_target"] = 1.0 if float(result["realized_gain"]) > 0.0 else 0.0
        result["utility"] = _decision_utility(
            cfg=cfg,
            scenario=scenario,
            decision_result=result,
            thresholds=thresholds,
            gain_history=gain_history,
        )

    oracle_decision = max(decision_results.values(), key=lambda item: float(item["utility"]))["status"]
    policy_result = dict(decision_results[policy_decision])
    oracle_result = dict(decision_results[oracle_decision])
    selection_quality = {
        "policy_match_oracle": bool(policy_decision == oracle_decision),
        "policy_utility": float(policy_result["utility"]),
        "oracle_utility": float(oracle_result["utility"]),
        "utility_regret": float(oracle_result["utility"] - policy_result["utility"]),
    }
    return {
        "scenario_id": str(scenario["id"]),
        "family": str(scenario["family"]),
        "version": int(scenario["version"]),
        "candidate_id": candidate_id,
        "policy_decision": str(policy_decision),
        "oracle_decision": str(oracle_decision),
        "selection_quality": selection_quality,
        "policy_decision_result": policy_result,
        "oracle_decision_result": oracle_result,
        "decision_results": decision_results,
        "candidate_summary": {
            "dummy_improvement": float(dummy_improvement),
            "local_score": float(local_score),
            "patch_size": float(runtime_features["patch_size"]),
            "adaptive_scale": float(runtime_features["adaptive_scale"]),
            "moving_average": float(runtime_features["moving_average"]),
            "persistence_streak": int(runtime_features["persistence_streak"]),
            "retained_evidence": float(runtime_features["retained_evidence"]),
            "retained_rounds": int(runtime_features["retained_rounds"]),
            "confidence": float(confidence["calibrated_confidence"]),
            "confidence_provisional_threshold": float(confidence["provisional_threshold"]),
            "confidence_full_threshold": float(confidence["full_threshold"]),
            "gain": float(gain_signal["calibrated_gain"]),
            "gain_provisional_threshold": float(gain_signal["provisional_threshold"]),
            "gain_full_threshold": float(gain_signal["full_threshold"]),
            "projection_policy_ok_provisional": bool(projection_ok_provisional),
            "full_ready": bool(full_ready),
        },
    }


def _brier(preds: List[float], targets: List[float]) -> Optional[float]:
    if not preds or len(preds) != len(targets):
        return None
    arr_p = np.asarray(preds, dtype=np.float64)
    arr_t = np.asarray(targets, dtype=np.float64)
    return float(np.mean((arr_p - arr_t) ** 2))


def _safe_rate(numerator: float, denominator: float) -> Optional[float]:
    if denominator <= 0:
        return None
    return float(numerator / denominator)


def _action_rate_map(counter: Counter[str], total: int) -> Dict[str, Optional[float]]:
    return {
        "reject": _safe_rate(float(counter.get("reject", 0)), float(total)),
        "provisional": _safe_rate(float(counter.get("provisional", 0)), float(total)),
        "full": _safe_rate(float(counter.get("full", 0)), float(total)),
    }


def _action_mismatch_matrix(confusion: Dict[str, Dict[str, int]], total: int) -> Dict[str, Dict[str, Dict[str, Optional[float]]]]:
    counts: Dict[str, Dict[str, int]] = {}
    rate_total: Dict[str, Dict[str, Optional[float]]] = {}
    rate_expected: Dict[str, Dict[str, Optional[float]]] = {}
    for expected in ("reject", "provisional", "full"):
        expected_counts = dict(confusion.get(expected, {}))
        expected_total = sum(int(expected_counts.get(policy, 0)) for policy in ("reject", "provisional", "full"))
        counts[expected] = {}
        rate_total[expected] = {}
        rate_expected[expected] = {}
        for policy in ("reject", "provisional", "full"):
            count = int(expected_counts.get(policy, 0))
            counts[expected][policy] = count
            rate_total[expected][policy] = _safe_rate(float(count), float(total))
            rate_expected[expected][policy] = _safe_rate(float(count), float(expected_total))
    return {
        "counts": counts,
        "rate_total": rate_total,
        "rate_expected": rate_expected,
    }


def _mismatch_bucket(
    *,
    matrix: Dict[str, Dict[str, Dict[str, Optional[float]]]],
    expected: str,
    policy: str,
) -> Dict[str, Optional[float]]:
    return {
        "count": int(matrix["counts"][expected][policy]),
        "rate_total": matrix["rate_total"][expected][policy],
        "rate_expected": matrix["rate_expected"][expected][policy],
    }


def _policy_bias(policy_rates: Dict[str, Optional[float]], expected_rates: Dict[str, Optional[float]]) -> str:
    deltas = {
        "reject_biased": float((policy_rates.get("reject") or 0.0) - (expected_rates.get("reject") or 0.0)),
        "provisional_biased": float((policy_rates.get("provisional") or 0.0) - (expected_rates.get("provisional") or 0.0)),
        "full_biased": float((policy_rates.get("full") or 0.0) - (expected_rates.get("full") or 0.0)),
    }
    best_label = max(deltas, key=deltas.get)
    if deltas[best_label] <= 0.05:
        return "balanced"
    return best_label


def _dominant_mismatch_label(mismatch_summary: Dict[str, Any]) -> str:
    keys = (
        "expected_provisional_got_reject",
        "expected_full_got_reject",
        "expected_full_got_provisional",
        "expected_reject_got_provisional",
        "expected_reject_got_full",
    )
    best_key = "well_aligned"
    best_count = 0
    for key in keys:
        count = int(dict(mismatch_summary.get(key, {})).get("count", 0))
        if count > best_count:
            best_count = count
            best_key = key
    return best_key


def _alignment_diagnosis(
    *,
    policy_match_rate: Optional[float],
    reject_overuse_rate: Optional[float],
    unsafe_overcommit_rate: Optional[float],
    false_full_adopt_rate: Optional[float],
    dominant_mismatch: str,
) -> Dict[str, Any]:
    flags: List[str] = []
    unsafe_dominant = dominant_mismatch in {"expected_reject_got_provisional", "expected_reject_got_full"}
    if (unsafe_overcommit_rate or 0.0) >= 0.15 or (false_full_adopt_rate or 0.0) >= 0.05 or unsafe_dominant:
        flags.append("unsafe_overcommit")
    if (reject_overuse_rate or 0.0) >= 0.10:
        flags.append("reject_biased")
    if dominant_mismatch == "expected_provisional_got_reject":
        flags.append("provisional_underused")
    if dominant_mismatch in {"expected_full_got_reject", "expected_full_got_provisional"}:
        flags.append("full_underused")
    if not flags and (policy_match_rate or 0.0) >= 0.65:
        flags.append("well_aligned")
    if not flags:
        flags.append("mixed")

    if "unsafe_overcommit" in flags:
        primary = "unsafe_overcommit"
    elif dominant_mismatch in {"expected_full_got_reject", "expected_full_got_provisional"}:
        primary = "full_underused"
    elif dominant_mismatch == "expected_provisional_got_reject":
        primary = "provisional_underused"
    elif "reject_biased" in flags:
        primary = "reject_biased"
    elif "well_aligned" in flags:
        primary = "well_aligned"
    else:
        primary = flags[0]

    return {
        "primary": primary,
        "flags": flags,
    }


def _scenario_group_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    policy_counter: Counter[str] = Counter()
    oracle_counter: Counter[str] = Counter()
    regrets: List[float] = []
    matches: List[float] = []
    policy_projection_bad: List[float] = []
    policy_gain_bad: List[float] = []
    policy_goal_bad: List[float] = []
    policy_projection_error: List[float] = []
    cal_gain_sign_p: List[float] = []
    cal_gain_sign_t: List[float] = []
    cal_proj_bad_p: List[float] = []
    cal_proj_bad_t: List[float] = []
    cal_gain_bad_p: List[float] = []
    cal_gain_bad_t: List[float] = []
    cal_goal_bad_p: List[float] = []
    cal_goal_bad_t: List[float] = []
    confusion = {
        "reject": {"reject": 0, "provisional": 0, "full": 0},
        "provisional": {"reject": 0, "provisional": 0, "full": 0},
        "full": {"reject": 0, "provisional": 0, "full": 0},
    }
    projection_bad_scenarios = 0
    false_safe_projection_count = 0
    preferred_not_full_count = 0
    false_full_adopt_count = 0
    for scenario in results:
        policy_decision = str(scenario["policy_decision"])
        oracle_decision = str(scenario["oracle_decision"])
        policy_counter[policy_decision] += 1
        oracle_counter[oracle_decision] += 1
        confusion.setdefault(oracle_decision, {}).setdefault(policy_decision, 0)
        confusion[oracle_decision][policy_decision] += 1
        regrets.append(float(scenario["selection_quality"]["utility_regret"]))
        matches.append(1.0 if bool(scenario["selection_quality"]["policy_match_oracle"]) else 0.0)
        policy = dict(scenario["policy_decision_result"])
        policy_projection_bad.append(1.0 if bool(policy["projection_bad"]) else 0.0)
        policy_gain_bad.append(1.0 if bool(policy["gain_bad"]) else 0.0)
        policy_goal_bad.append(1.0 if bool(policy["goal_bad"]) else 0.0)
        policy_projection_error.append(float(policy["projection_error"]))
        if bool(policy["projection_bad"]):
            projection_bad_scenarios += 1
            if policy_decision != "reject":
                false_safe_projection_count += 1
        if oracle_decision in {"reject", "provisional"}:
            preferred_not_full_count += 1
            if policy_decision == "full":
                false_full_adopt_count += 1
        for status in ("provisional", "full"):
            decision = dict(scenario["decision_results"][status])
            cal_gain_sign_p.append(float(decision["pred_gain_sign_prob"]))
            cal_gain_sign_t.append(float(decision["forecast_gain_sign_target"]))
            cal_proj_bad_p.append(float(decision["pred_projection_bad_prob"]))
            cal_proj_bad_t.append(1.0 if bool(decision["projection_bad"]) else 0.0)
            cal_gain_bad_p.append(float(decision["pred_gain_bad_prob"]))
            cal_gain_bad_t.append(1.0 if bool(decision["gain_bad"]) else 0.0)
            cal_goal_bad_p.append(float(decision["pred_goal_bad_prob"]))
            cal_goal_bad_t.append(1.0 if bool(decision["goal_bad"]) else 0.0)
    total = int(len(results))
    action_matrix = _action_mismatch_matrix(confusion, total)
    mismatch_summary = {
        "expected_provisional_got_reject": _mismatch_bucket(
            matrix=action_matrix,
            expected="provisional",
            policy="reject",
        ),
        "expected_full_got_reject": _mismatch_bucket(
            matrix=action_matrix,
            expected="full",
            policy="reject",
        ),
        "expected_full_got_provisional": _mismatch_bucket(
            matrix=action_matrix,
            expected="full",
            policy="provisional",
        ),
        "expected_reject_got_provisional": _mismatch_bucket(
            matrix=action_matrix,
            expected="reject",
            policy="provisional",
        ),
        "expected_reject_got_full": _mismatch_bucket(
            matrix=action_matrix,
            expected="reject",
            policy="full",
        ),
    }
    expected_rates = _action_rate_map(oracle_counter, total)
    policy_rates = _action_rate_map(policy_counter, total)
    reject_overuse_rate = float((policy_rates.get("reject") or 0.0) - (expected_rates.get("reject") or 0.0))
    missed_safe_opportunity_rate = _safe_rate(
        float(
            mismatch_summary["expected_provisional_got_reject"]["count"]
            + mismatch_summary["expected_full_got_reject"]["count"]
        ),
        float(total),
    )
    unsafe_overcommit_rate = _safe_rate(
        float(
            mismatch_summary["expected_reject_got_provisional"]["count"]
            + mismatch_summary["expected_reject_got_full"]["count"]
        ),
        float(total),
    )
    undercommitment_score = _safe_rate(
        float(
            mismatch_summary["expected_provisional_got_reject"]["count"]
            + 2 * mismatch_summary["expected_full_got_reject"]["count"]
            + mismatch_summary["expected_full_got_provisional"]["count"]
        ),
        float(total),
    )
    dominant_mismatch = _dominant_mismatch_label(mismatch_summary)
    diagnosis = _alignment_diagnosis(
        policy_match_rate=float(np.mean(np.asarray(matches, dtype=np.float64))) if matches else None,
        reject_overuse_rate=reject_overuse_rate,
        unsafe_overcommit_rate=unsafe_overcommit_rate,
        false_full_adopt_rate=(
            float(false_full_adopt_count / preferred_not_full_count) if preferred_not_full_count > 0 else None
        ),
        dominant_mismatch=dominant_mismatch,
    )
    return {
        "scenario_count": total,
        "policy_match_rate": float(np.mean(np.asarray(matches, dtype=np.float64))) if matches else None,
        "mean_regret": float(np.mean(np.asarray(regrets, dtype=np.float64))) if regrets else None,
        "policy_decision_counts": dict(policy_counter),
        "oracle_decision_counts": dict(oracle_counter),
        "policy_decision_rates": policy_rates,
        "oracle_decision_rates": expected_rates,
        "policy_projection_bad_rate": float(np.mean(np.asarray(policy_projection_bad, dtype=np.float64))) if policy_projection_bad else None,
        "policy_gain_bad_rate": float(np.mean(np.asarray(policy_gain_bad, dtype=np.float64))) if policy_gain_bad else None,
        "policy_goal_bad_rate": float(np.mean(np.asarray(policy_goal_bad, dtype=np.float64))) if policy_goal_bad else None,
        "policy_projection_error_mean": float(np.mean(np.asarray(policy_projection_error, dtype=np.float64))) if policy_projection_error else None,
        "forecast_gain_sign_brier": _brier(cal_gain_sign_p, cal_gain_sign_t),
        "forecast_projection_bad_brier": _brier(cal_proj_bad_p, cal_proj_bad_t),
        "forecast_gain_bad_brier": _brier(cal_gain_bad_p, cal_gain_bad_t),
        "forecast_goal_bad_brier": _brier(cal_goal_bad_p, cal_goal_bad_t),
        "preferred_action_confusion": confusion,
        "action_mismatch_matrix": action_matrix,
        "mismatch_summary": mismatch_summary,
        "dominant_mismatch": dominant_mismatch,
        "policy_bias": _policy_bias(policy_rates, expected_rates),
        "reject_overuse_rate": reject_overuse_rate,
        "missed_safe_opportunity_rate": missed_safe_opportunity_rate,
        "unsafe_overcommit_rate": unsafe_overcommit_rate,
        "undercommitment_score": undercommitment_score,
        "alignment_diagnosis": diagnosis,
        "preferred_action_expected_counts": dict(oracle_counter),
        "preferred_action_policy_counts": dict(policy_counter),
        "projection_bad_scenarios": int(projection_bad_scenarios),
        "false_safe_projection_count": int(false_safe_projection_count),
        "false_safe_projection_rate": (
            float(false_safe_projection_count / projection_bad_scenarios) if projection_bad_scenarios > 0 else None
        ),
        "preferred_not_full_count": int(preferred_not_full_count),
        "false_full_adopt_count": int(false_full_adopt_count),
        "false_full_adopt_rate": (
            float(false_full_adopt_count / preferred_not_full_count) if preferred_not_full_count > 0 else None
        ),
    }


def _compact_summary_block(section: Dict[str, Any]) -> Dict[str, Any]:
    selection = dict(section.get("selection", {}))
    gain_goal = dict(section.get("gain_goal", {}))
    return {
        "policy_match_rate": selection.get("policy_match_rate"),
        "projection_bad_brier": selection.get("forecast_projection_bad_brier"),
        "gain_bad_brier": selection.get("forecast_gain_bad_brier"),
        "goal_bad_brier": selection.get("forecast_goal_bad_brier"),
        "policy_action_distribution": dict(selection.get("policy_decision_counts", {})),
        "expected_action_distribution": dict(selection.get("oracle_decision_counts", {})),
        "preferred_action_confusion": dict(selection.get("preferred_action_confusion", {})),
        "dominant_mismatch": selection.get("dominant_mismatch"),
        "policy_bias": selection.get("policy_bias"),
        "reject_overuse_rate": selection.get("reject_overuse_rate"),
        "missed_safe_opportunity_rate": selection.get("missed_safe_opportunity_rate"),
        "unsafe_overcommit_rate": selection.get("unsafe_overcommit_rate"),
        "undercommitment_score": selection.get("undercommitment_score"),
        "alignment_diagnosis": dict(selection.get("alignment_diagnosis", {})),
        "mismatch_summary": dict(selection.get("mismatch_summary", {})),
        "false_safe_projection_rate": selection.get("false_safe_projection_rate"),
        "false_full_adopt_rate": selection.get("false_full_adopt_rate"),
        "policy_gain_bad_rate": gain_goal.get("policy_gain_bad_rate"),
        "policy_goal_bad_rate": gain_goal.get("policy_goal_bad_rate"),
    }


POLICY_SWEEP_VARIANTS: List[Dict[str, Any]] = [
    {
        "name": "targeted_gain_goal_safe_window",
        "allowed_families": ["gain_goal_conflict", "calibration", "projection"],
        "blocked_families": ["recovery"],
        "conf_margin": 0.14,
        "gain_margin": 0.14,
        "strict_projection_max": 0.48,
        "min_pred_gain_sign_prob": 0.20,
        "max_pred_gain_bad_prob": 0.62,
        "min_projected_score": 0.32,
        "max_persistence_streak": 0,
        "max_retained_evidence": 0.05,
        "max_moving_average": 0.05,
        "min_live_projection_margin": 0.24,
        "near_projection_band": 0.00,
        "near_projection_extra_projected_score": 0.00,
        "near_projection_extra_confidence": 0.00,
        "near_projection_extra_gain_sign_prob": 0.00,
    },
    {
        "name": "targeted_gain_goal_proj_margin_01",
        "allowed_families": ["gain_goal_conflict", "calibration", "projection"],
        "blocked_families": ["recovery"],
        "conf_margin": 0.14,
        "gain_margin": 0.14,
        "strict_projection_max": 0.48,
        "min_pred_gain_sign_prob": 0.20,
        "max_pred_gain_bad_prob": 0.62,
        "min_projected_score": 0.32,
        "max_persistence_streak": 0,
        "max_retained_evidence": 0.05,
        "max_moving_average": 0.05,
        "min_live_projection_margin": 0.25,
        "near_projection_band": 0.00,
        "near_projection_extra_projected_score": 0.00,
        "near_projection_extra_confidence": 0.00,
        "near_projection_extra_gain_sign_prob": 0.00,
    },
    {
        "name": "targeted_gain_goal_proj_margin_02",
        "allowed_families": ["gain_goal_conflict", "calibration", "projection"],
        "blocked_families": ["recovery"],
        "conf_margin": 0.14,
        "gain_margin": 0.14,
        "strict_projection_max": 0.48,
        "min_pred_gain_sign_prob": 0.20,
        "max_pred_gain_bad_prob": 0.62,
        "min_projected_score": 0.32,
        "max_persistence_streak": 0,
        "max_retained_evidence": 0.05,
        "max_moving_average": 0.05,
        "min_live_projection_margin": 0.26,
        "near_projection_band": 0.00,
        "near_projection_extra_projected_score": 0.00,
        "near_projection_extra_confidence": 0.00,
        "near_projection_extra_gain_sign_prob": 0.00,
    },
    {
        "name": "targeted_gain_goal_near_boundary_gain_boost",
        "allowed_families": ["gain_goal_conflict", "calibration", "projection"],
        "blocked_families": ["recovery"],
        "conf_margin": 0.14,
        "gain_margin": 0.14,
        "strict_projection_max": 0.48,
        "min_pred_gain_sign_prob": 0.20,
        "max_pred_gain_bad_prob": 0.62,
        "min_projected_score": 0.32,
        "max_persistence_streak": 0,
        "max_retained_evidence": 0.05,
        "max_moving_average": 0.05,
        "min_live_projection_margin": 0.24,
        "near_projection_band": 0.02,
        "near_projection_extra_projected_score": 0.02,
        "near_projection_extra_confidence": 0.00,
        "near_projection_extra_gain_sign_prob": 0.04,
    },
    {
        "name": "targeted_gain_goal_near_boundary_conf_boost",
        "allowed_families": ["gain_goal_conflict", "calibration", "projection"],
        "blocked_families": ["recovery"],
        "conf_margin": 0.14,
        "gain_margin": 0.14,
        "strict_projection_max": 0.48,
        "min_pred_gain_sign_prob": 0.20,
        "max_pred_gain_bad_prob": 0.62,
        "min_projected_score": 0.32,
        "max_persistence_streak": 0,
        "max_retained_evidence": 0.05,
        "max_moving_average": 0.05,
        "min_live_projection_margin": 0.24,
        "near_projection_band": 0.02,
        "near_projection_extra_projected_score": 0.00,
        "near_projection_extra_confidence": 0.02,
        "near_projection_extra_gain_sign_prob": 0.00,
    },
    {
        "name": "targeted_gain_goal_margin_01_plus_boundary_boost",
        "allowed_families": ["gain_goal_conflict", "calibration", "projection"],
        "blocked_families": ["recovery"],
        "conf_margin": 0.14,
        "gain_margin": 0.14,
        "strict_projection_max": 0.48,
        "min_pred_gain_sign_prob": 0.20,
        "max_pred_gain_bad_prob": 0.62,
        "min_projected_score": 0.32,
        "max_persistence_streak": 0,
        "max_retained_evidence": 0.05,
        "max_moving_average": 0.05,
        "min_live_projection_margin": 0.25,
        "near_projection_band": 0.02,
        "near_projection_extra_projected_score": 0.02,
        "near_projection_extra_confidence": 0.00,
        "near_projection_extra_gain_sign_prob": 0.04,
    },
]


def _summarize_benchmark_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_family: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for scenario_result in results:
        by_family[str(scenario_result["family"])].append(scenario_result)

    family_metrics: Dict[str, Any] = {}
    for family, family_results in by_family.items():
        family_metrics[family] = {
            "selection": _scenario_group_metrics(family_results),
            "projection": score_projection_family(family_results),
            "gain_goal": score_gain_goal_family(family_results),
            "persistence": score_persistence_family(family_results),
        }

    global_metrics = {
        "selection": _scenario_group_metrics(results),
        "projection": score_projection_family(results),
        "gain_goal": score_gain_goal_family(results),
        "persistence": score_persistence_family(results),
    }
    family_compact_summary = {
        family: _compact_summary_block(metrics)
        for family, metrics in family_metrics.items()
    }
    global_compact_summary = _compact_summary_block(global_metrics)
    family_action_mismatch = {
        family: dict(metrics.get("selection", {}).get("action_mismatch_matrix", {}).get("counts", {}))
        for family, metrics in family_metrics.items()
    }
    family_mismatch_summary = {
        family: {
            "dominant_mismatch": metrics.get("selection", {}).get("dominant_mismatch"),
            "policy_bias": metrics.get("selection", {}).get("policy_bias"),
            "reject_overuse_rate": metrics.get("selection", {}).get("reject_overuse_rate"),
            "missed_safe_opportunity_rate": metrics.get("selection", {}).get("missed_safe_opportunity_rate"),
            "unsafe_overcommit_rate": metrics.get("selection", {}).get("unsafe_overcommit_rate"),
            "undercommitment_score": metrics.get("selection", {}).get("undercommitment_score"),
            "alignment_diagnosis": dict(metrics.get("selection", {}).get("alignment_diagnosis", {})),
            "mismatch_summary": dict(metrics.get("selection", {}).get("mismatch_summary", {})),
        }
        for family, metrics in family_metrics.items()
    }
    global_action_mismatch = dict(global_metrics.get("selection", {}).get("action_mismatch_matrix", {}).get("counts", {}))
    global_mismatch_summary = {
        "dominant_mismatch": global_metrics.get("selection", {}).get("dominant_mismatch"),
        "policy_bias": global_metrics.get("selection", {}).get("policy_bias"),
        "reject_overuse_rate": global_metrics.get("selection", {}).get("reject_overuse_rate"),
        "missed_safe_opportunity_rate": global_metrics.get("selection", {}).get("missed_safe_opportunity_rate"),
        "unsafe_overcommit_rate": global_metrics.get("selection", {}).get("unsafe_overcommit_rate"),
        "undercommitment_score": global_metrics.get("selection", {}).get("undercommitment_score"),
        "alignment_diagnosis": dict(global_metrics.get("selection", {}).get("alignment_diagnosis", {})),
        "mismatch_summary": dict(global_metrics.get("selection", {}).get("mismatch_summary", {})),
    }
    return {
        "scenario_count": int(len(results)),
        "family_metrics": family_metrics,
        "family_compact_summary": family_compact_summary,
        "family_action_mismatch": family_action_mismatch,
        "family_mismatch_summary": family_mismatch_summary,
        "global_metrics": global_metrics,
        "global_compact_summary": global_compact_summary,
        "global_action_mismatch": global_action_mismatch,
        "global_mismatch_summary": global_mismatch_summary,
    }


def _result_with_policy_decision(
    scenario_result: Dict[str, Any],
    policy_decision: str,
    variant_name: str,
) -> Dict[str, Any]:
    result = copy.deepcopy(scenario_result)
    policy_result = dict(result["decision_results"][policy_decision])
    oracle_decision = str(result["oracle_decision"])
    oracle_result = dict(result["decision_results"][oracle_decision])
    result["policy_decision"] = str(policy_decision)
    result["policy_decision_result"] = policy_result
    result["selection_quality"] = {
        "policy_match_oracle": bool(policy_decision == oracle_decision),
        "policy_utility": float(policy_result["utility"]),
        "oracle_utility": float(oracle_result["utility"]),
        "utility_regret": float(oracle_result["utility"] - policy_result["utility"]),
    }
    result["policy_variant"] = str(variant_name)
    return result


def _variant_policy_decision(
    *,
    cfg: ProposalLearningConfig,
    scenario_result: Dict[str, Any],
    variant: Dict[str, Any],
) -> Tuple[str, str]:
    baseline_decision = str(scenario_result["policy_decision"])
    if baseline_decision != "reject":
        return baseline_decision, "baseline_non_reject"
    allowed_families = {str(v) for v in list(variant.get("allowed_families", []))}
    if allowed_families and str(scenario_result.get("family")) not in allowed_families:
        return "reject", "family_not_targeted"
    if str(scenario_result.get("family")) in set(str(v) for v in list(variant.get("blocked_families", []))):
        return "reject", "family_block"

    candidate_summary = dict(scenario_result.get("candidate_summary", {}))
    provisional = dict(scenario_result.get("decision_results", {}).get("provisional", {}))
    predicted = dict(provisional.get("predicted", {}))
    if not bool(candidate_summary.get("projection_policy_ok_provisional", False)):
        return "reject", "projection_policy_block"

    conf = float(candidate_summary.get("confidence", 0.0))
    conf_threshold = float(candidate_summary.get("confidence_provisional_threshold", cfg.adopt_threshold_provisional))
    gain = float(candidate_summary.get("gain", 0.0))
    gain_threshold = float(candidate_summary.get("gain_provisional_threshold", cfg.adoption_score_threshold_provisional))
    moving_average = float(candidate_summary.get("moving_average", 0.0))
    persistence_streak = int(candidate_summary.get("persistence_streak", 0))
    retained_evidence = float(candidate_summary.get("retained_evidence", 0.0))
    pred_projection_bad = float(provisional.get("pred_projection_bad_prob", 1.0))
    pred_gain_sign = float(provisional.get("pred_gain_sign_prob", 0.0))
    pred_gain_bad = float(provisional.get("pred_gain_bad_prob", 1.0))
    projected_score = float(predicted.get("calibrated_projected", 0.0))

    live_projection_veto = float(getattr(cfg, "wm_candidate_pred_projection_bad_max_provisional", 1.0))
    effective_projection_max = min(
        float(variant["strict_projection_max"]),
        live_projection_veto - float(variant.get("min_live_projection_margin", 0.0)),
    )
    safe_projection = pred_projection_bad <= effective_projection_max
    conf_ok = conf >= (conf_threshold - float(variant["conf_margin"]))
    gain_ok = gain >= (gain_threshold - float(variant["gain_margin"]))
    near_projection_boundary = bool(
        float(variant.get("near_projection_band", 0.0)) > 0.0
        and pred_projection_bad >= (effective_projection_max - float(variant.get("near_projection_band", 0.0)))
    )
    required_projected_score = float(variant["min_projected_score"])
    required_gain_sign = float(variant["min_pred_gain_sign_prob"])
    required_conf = float(conf_threshold - float(variant["conf_margin"]))
    if near_projection_boundary:
        required_projected_score += float(variant.get("near_projection_extra_projected_score", 0.0))
        required_gain_sign += float(variant.get("near_projection_extra_gain_sign_prob", 0.0))
        required_conf += float(variant.get("near_projection_extra_confidence", 0.0))
    projected_ok = (
        pred_gain_sign >= required_gain_sign
        and pred_gain_bad <= float(variant["max_pred_gain_bad_prob"])
        and projected_score >= required_projected_score
    )
    conf_ok = conf_ok and conf >= required_conf
    persistence_risk_low = (
        persistence_streak <= int(variant.get("max_persistence_streak", 0))
        and retained_evidence <= float(variant.get("max_retained_evidence", 0.0))
        and moving_average <= float(variant.get("max_moving_average", 0.0))
    )
    if safe_projection and conf_ok and gain_ok and projected_ok and persistence_risk_low:
        return "provisional", "safe_provisional_override"
    if not persistence_risk_low:
        return "reject", "persistence_guard"
    return "reject", "remain_reject"


def _delta_metric(current: Optional[float], baseline: Optional[float]) -> Optional[float]:
    if current is None or baseline is None:
        return None
    return float(current - baseline)


def _variant_comparison(
    *,
    baseline_summary: Dict[str, Any],
    variant_summary: Dict[str, Any],
) -> Dict[str, Any]:
    baseline_global = dict(baseline_summary.get("global_compact_summary", {}))
    variant_global = dict(variant_summary.get("global_compact_summary", {}))
    baseline_mismatch = dict(baseline_summary.get("global_mismatch_summary", {})).get("mismatch_summary", {})
    variant_mismatch = dict(variant_summary.get("global_mismatch_summary", {})).get("mismatch_summary", {})
    family_deltas: Dict[str, Any] = {}
    for family, family_compact in dict(variant_summary.get("family_compact_summary", {})).items():
        baseline_family_compact = dict(baseline_summary.get("family_compact_summary", {}).get(family, {}))
        baseline_family_mismatch = dict(baseline_summary.get("family_mismatch_summary", {}).get(family, {})).get("mismatch_summary", {})
        variant_family_mismatch = dict(variant_summary.get("family_mismatch_summary", {}).get(family, {})).get("mismatch_summary", {})
        family_deltas[family] = {
            "policy_match_rate_delta": _delta_metric(
                family_compact.get("policy_match_rate"),
                baseline_family_compact.get("policy_match_rate"),
            ),
            "expected_provisional_got_reject_delta": int(
                dict(variant_family_mismatch.get("expected_provisional_got_reject", {})).get("count", 0)
                - dict(baseline_family_mismatch.get("expected_provisional_got_reject", {})).get("count", 0)
            ),
            "expected_full_got_reject_delta": int(
                dict(variant_family_mismatch.get("expected_full_got_reject", {})).get("count", 0)
                - dict(baseline_family_mismatch.get("expected_full_got_reject", {})).get("count", 0)
            ),
            "unsafe_overcommit_rate_delta": _delta_metric(
                dict(variant_summary.get("family_mismatch_summary", {}).get(family, {})).get("unsafe_overcommit_rate"),
                dict(baseline_summary.get("family_mismatch_summary", {}).get(family, {})).get("unsafe_overcommit_rate"),
            ),
            "false_safe_projection_rate_delta": _delta_metric(
                family_compact.get("false_safe_projection_rate"),
                baseline_family_compact.get("false_safe_projection_rate"),
            ),
        }
    return {
        "policy_match_rate_delta": _delta_metric(
            variant_global.get("policy_match_rate"),
            baseline_global.get("policy_match_rate"),
        ),
        "expected_provisional_got_reject_delta": int(
            dict(variant_mismatch.get("expected_provisional_got_reject", {})).get("count", 0)
            - dict(baseline_mismatch.get("expected_provisional_got_reject", {})).get("count", 0)
        ),
        "expected_full_got_reject_delta": int(
            dict(variant_mismatch.get("expected_full_got_reject", {})).get("count", 0)
            - dict(baseline_mismatch.get("expected_full_got_reject", {})).get("count", 0)
        ),
        "unsafe_overcommit_rate_delta": _delta_metric(
            dict(variant_summary.get("global_mismatch_summary", {})).get("unsafe_overcommit_rate"),
            dict(baseline_summary.get("global_mismatch_summary", {})).get("unsafe_overcommit_rate"),
        ),
        "false_safe_projection_rate_delta": _delta_metric(
            variant_global.get("false_safe_projection_rate"),
            baseline_global.get("false_safe_projection_rate"),
        ),
        "family_deltas": family_deltas,
    }


def _variant_projection_distance(variant: Dict[str, Any], reference: Dict[str, Any]) -> float:
    return float(
        abs(float(variant.get("strict_projection_max", 0.0)) - float(reference.get("strict_projection_max", 0.0)))
        + abs(float(variant.get("min_live_projection_margin", 0.0)) - float(reference.get("min_live_projection_margin", 0.0)))
        + abs(float(variant.get("near_projection_band", 0.0)) - float(reference.get("near_projection_band", 0.0)))
        + abs(
            float(variant.get("near_projection_extra_projected_score", 0.0))
            - float(reference.get("near_projection_extra_projected_score", 0.0))
        )
        + abs(
            float(variant.get("near_projection_extra_confidence", 0.0))
            - float(reference.get("near_projection_extra_confidence", 0.0))
        )
        + abs(
            float(variant.get("near_projection_extra_gain_sign_prob", 0.0))
            - float(reference.get("near_projection_extra_gain_sign_prob", 0.0))
        )
    )


def _variant_recommendation(
    *,
    variant_summary: Dict[str, Any],
    comparison: Dict[str, Any],
) -> Dict[str, Any]:
    max_false_safe_cap = 0.03
    max_unsafe_cap = 0.03
    persistence_match_tolerance = -0.05
    delta_match = float(comparison.get("policy_match_rate_delta") or 0.0)
    delta_prov_reject = int(comparison.get("expected_provisional_got_reject_delta") or 0)
    delta_full_reject = int(comparison.get("expected_full_got_reject_delta") or 0)
    delta_unsafe = float(comparison.get("unsafe_overcommit_rate_delta") or 0.0)
    delta_false_safe = float(comparison.get("false_safe_projection_rate_delta") or 0.0)
    gain_goal_delta = float(dict(comparison.get("family_deltas", {}).get("gain_goal_conflict", {})).get("policy_match_rate_delta") or 0.0)
    persistence_match_delta = float(dict(comparison.get("family_deltas", {}).get("persistence", {})).get("policy_match_rate_delta") or 0.0)
    projection_delta = float(dict(comparison.get("family_deltas", {}).get("projection", {})).get("false_safe_projection_rate_delta") or 0.0)
    recovery_delta = float(dict(comparison.get("family_deltas", {}).get("recovery", {})).get("false_safe_projection_rate_delta") or 0.0)
    meets_hard_constraints = bool(
        delta_false_safe <= max_false_safe_cap
        and delta_unsafe <= max_unsafe_cap
        and persistence_match_delta >= persistence_match_tolerance
        and projection_delta <= max_false_safe_cap
        and recovery_delta <= max_false_safe_cap
    )
    safe_to_consider = bool(
        meets_hard_constraints
        and gain_goal_delta > 0.0
        and delta_prov_reject < 0
        and delta_full_reject <= 0
    )
    if safe_to_consider:
        status = "safe_to_consider_later"
    elif gain_goal_delta > 0.0 and meets_hard_constraints:
        status = "targeted_gain_goal_improvement"
    elif delta_match > 0.0 and gain_goal_delta >= 0.0:
        status = "promising_but_watch_safety"
    else:
        status = "not_safe_enough_yet"
    return {
        "status": status,
        "safe_to_consider_later": safe_to_consider,
        "meets_hard_constraints": meets_hard_constraints,
        "max_false_safe_cap": max_false_safe_cap,
        "max_unsafe_cap": max_unsafe_cap,
        "persistence_match_tolerance": persistence_match_tolerance,
        "gain_goal_match_delta": gain_goal_delta,
        "persistence_match_delta": persistence_match_delta,
        "projection_family_guard_delta": projection_delta,
        "recovery_family_guard_delta": recovery_delta,
        "global_diagnosis": dict(variant_summary.get("global_mismatch_summary", {})).get("alignment_diagnosis", {}),
    }


def _run_policy_sweep(
    *,
    cfg: ProposalLearningConfig,
    baseline_results: List[Dict[str, Any]],
    baseline_summary: Dict[str, Any],
) -> Dict[str, Any]:
    reference_variant_name = "targeted_gain_goal_safe_window"
    reference_settings = next(
        dict(variant) for variant in POLICY_SWEEP_VARIANTS if str(variant.get("name")) == reference_variant_name
    )
    variants_out: List[Dict[str, Any]] = []
    best_safe: Optional[Dict[str, Any]] = None
    best_overall: Optional[Dict[str, Any]] = None
    smallest_change_acceptable: Optional[Dict[str, Any]] = None
    for variant in POLICY_SWEEP_VARIANTS:
        variant_results: List[Dict[str, Any]] = []
        change_count = 0
        override_reasons: Counter[str] = Counter()
        for scenario_result in baseline_results:
            decision, reason = _variant_policy_decision(cfg=cfg, scenario_result=scenario_result, variant=variant)
            override_reasons[reason] += 1
            if decision != str(scenario_result["policy_decision"]):
                change_count += 1
            variant_results.append(_result_with_policy_decision(scenario_result, decision, str(variant["name"])))
        variant_summary = _summarize_benchmark_results(variant_results)
        comparison = _variant_comparison(baseline_summary=baseline_summary, variant_summary=variant_summary)
        recommendation = _variant_recommendation(variant_summary=variant_summary, comparison=comparison)
        variant_out = {
            "name": str(variant["name"]),
            "settings": dict(variant),
            "changed_policy_count": int(change_count),
            "override_reason_counts": dict(override_reasons),
            "summary": variant_summary,
            "comparison_to_baseline": comparison,
            "recommendation": recommendation,
        }
        variants_out.append(variant_out)
        gain_goal_delta = float(recommendation.get("gain_goal_match_delta") or 0.0)
        global_match_delta = float(variant_out["comparison_to_baseline"].get("policy_match_rate_delta") or 0.0)
        if recommendation["safe_to_consider_later"]:
            if str(variant_out["name"]) != reference_variant_name:
                if best_safe is None or (
                    gain_goal_delta,
                    global_match_delta,
                ) > (
                    float(best_safe["recommendation"].get("gain_goal_match_delta") or -1.0),
                    float(best_safe["comparison_to_baseline"].get("policy_match_rate_delta") or -1.0),
                ):
                    best_safe = variant_out
                if smallest_change_acceptable is None:
                    smallest_change_acceptable = variant_out
                else:
                    current_distance = _variant_projection_distance(
                        dict(variant_out.get("settings", {})),
                        reference_settings,
                    )
                    best_distance = _variant_projection_distance(
                        dict(smallest_change_acceptable.get("settings", {})),
                        reference_settings,
                    )
                    if (current_distance, -global_match_delta) < (best_distance, -float(smallest_change_acceptable["comparison_to_baseline"].get("policy_match_rate_delta") or 0.0)):
                        smallest_change_acceptable = variant_out
        if str(variant_out["name"]) != reference_variant_name:
            if best_overall is None or (
                gain_goal_delta,
                global_match_delta,
            ) > (
                float(best_overall["recommendation"].get("gain_goal_match_delta") or -1.0),
                float(best_overall["comparison_to_baseline"].get("policy_match_rate_delta") or -1.0),
            ):
                best_overall = variant_out
    reference_variant = next((variant for variant in variants_out if str(variant.get("name")) == reference_variant_name), None)
    if reference_variant is not None:
        reference_summary = dict(reference_variant.get("summary", {}))
        for variant in variants_out:
            variant["comparison_to_targeted_gain_goal_safe_window"] = _variant_comparison(
                baseline_summary=reference_summary,
                variant_summary=dict(variant.get("summary", {})),
            )
    recommendation = {
        "status": "no_safe_adjustment_yet",
        "variant": None,
    }
    if best_safe is not None:
        recommendation = {
            "status": "consider_benchmark_only_followup",
            "variant": str(best_safe["name"]),
        }
    elif best_overall is not None:
        recommendation = {
            "status": str(best_overall["recommendation"].get("status", "observe_best_variant_only")),
            "variant": str(best_overall["name"]),
        }
    return {
        "reference_variant": reference_variant_name,
        "baseline_global_compact_summary": dict(baseline_summary.get("global_compact_summary", {})),
        "baseline_family_compact_summary": dict(baseline_summary.get("family_compact_summary", {})),
        "variants": variants_out,
        "best_safe_variant": None if best_safe is None else str(best_safe["name"]),
        "best_overall_variant": None if best_overall is None else str(best_overall["name"]),
        "smallest_change_acceptable_variant": None if smallest_change_acceptable is None else str(smallest_change_acceptable["name"]),
        "recommendation": recommendation,
    }


def _write_reports(*, summary: Dict[str, Any], detailed: Dict[str, Any]) -> Dict[str, str]:
    reports_dir = _reports_dir()
    summary_path = reports_dir / "latest_summary.json"
    detailed_path = reports_dir / "latest_detailed.json"
    summary_path.write_text(json.dumps(_to_jsonable(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    detailed_path.write_text(json.dumps(_to_jsonable(detailed), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"summary": str(summary_path), "detailed": str(detailed_path)}


def run_trusted_benchmark_pack(
    *,
    cfg: Optional[ProposalLearningConfig] = None,
    triad: Optional[Sequence[Any]] = None,
    pops: Optional[Sequence[Sequence[Any]]] = None,
    world_model: Optional[RSSMWorldModel] = None,
    runtime_context: Optional[Dict[str, Any]] = None,
    training_round: int = 0,
    mode: str = "standalone",
    include_policy_sweep: bool = False,
) -> Dict[str, Any]:
    cfg = copy.deepcopy(cfg) if cfg is not None else build_default_config(verbose=False)
    cfg.verbose = False
    write_frozen_pack(_pack_dir())
    runtime_context = copy.deepcopy(runtime_context) if runtime_context is not None else _default_runtime_context()
    _seed_all(int(cfg.seed) + 900_000 + int(training_round))

    if triad is None or pops is None:
        triad_clone, pops_clone, world_model_clone = _build_fresh_runtime(cfg)
    else:
        triad_clone = _clone_triad(cfg, triad)
        pops_clone = _clone_pops(cfg, triad_clone, pops)
        world_model_clone = _clone_world_model(cfg, world_model)

    candidate_bank = _build_candidate_bank(
        cfg=cfg,
        triad=triad_clone,
        pops=pops_clone,
        world_model=world_model_clone,
        runtime_context=runtime_context,
    )
    scenarios = build_frozen_scenarios()
    results: List[Dict[str, Any]] = []
    for scenario in scenarios:
        scenario_result = _evaluate_scenario(
            cfg=cfg,
            triad=triad_clone,
            world_model=world_model_clone,
            candidate_bank=candidate_bank,
            scenario=scenario,
            runtime_context=runtime_context,
        )
        results.append(scenario_result)
    baseline_summary_fields = _summarize_benchmark_results(results)
    policy_sweep_analysis = _run_policy_sweep(
        cfg=cfg,
        baseline_results=results,
        baseline_summary=baseline_summary_fields,
    ) if include_policy_sweep else None
    generated_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "benchmark_pack": PACK_NAME,
        "version": PACK_VERSION,
        "generated_at": generated_at,
        "mode": str(mode),
        "training_round": int(training_round),
        **baseline_summary_fields,
    }
    if policy_sweep_analysis is not None:
        summary["policy_sweep_analysis"] = policy_sweep_analysis
    detailed = {
        "benchmark_pack": PACK_NAME,
        "version": PACK_VERSION,
        "generated_at": generated_at,
        "mode": str(mode),
        "training_round": int(training_round),
        "candidate_bank_summary": {
            "base_avg": float(candidate_bank["base_avg"]),
            "goal_pressure": float(candidate_bank["goal_pressure"]),
            "projection_error": float(candidate_bank["baseline_9d_metrics"].get("projection_error", 0.0)),
        },
        "results": results,
    }
    if policy_sweep_analysis is not None:
        detailed["policy_sweep_analysis"] = policy_sweep_analysis
    report_paths = _write_reports(summary=summary, detailed=detailed)
    summary["report_paths"] = report_paths
    return {"summary": summary, "detailed": detailed, "report_paths": report_paths}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen novali-v3 trusted benchmark pack.")
    parser.add_argument("--mode", default="standalone", choices=["standalone"], help="Benchmark mode.")
    parser.add_argument("--policy-sweep", action="store_true", help="Run offline provisional policy sweep analysis.")
    args = parser.parse_args()
    permission = build_execution_permission(action_kind="trusted_benchmark_pack_cli")
    require_execution_permission(permission)
    print(f"Governance Preflight: {format_execution_permission(permission)}")
    result = run_trusted_benchmark_pack(mode=args.mode, include_policy_sweep=bool(args.policy_sweep))
    summary = result["summary"]
    compact = dict(summary.get("global_compact_summary", {}))
    family_mismatch = dict(summary.get("family_mismatch_summary", {}))
    print(f"Benchmark Pack : {summary['benchmark_pack']} v{summary['version']}")
    print(f"Mode           : {summary['mode']}")
    print(f"Scenarios      : {summary['scenario_count']}")
    print(f"Policy Match   : {compact.get('policy_match_rate')}")
    print(f"Projection Brier: {compact.get('projection_bad_brier')}")
    print(f"Expected Action: {compact.get('expected_action_distribution')}")
    print(f"Policy Action  : {compact.get('policy_action_distribution')}")
    print(f"False Safe     : {compact.get('false_safe_projection_rate')}")
    print(f"False Full     : {compact.get('false_full_adopt_rate')}")
    print(f"Dominant Miss  : {compact.get('dominant_mismatch')}")
    print(f"Policy Bias    : {compact.get('policy_bias')}")
    print(f"Reject Overuse : {compact.get('reject_overuse_rate')}")
    print(f"Missed Safe    : {compact.get('missed_safe_opportunity_rate')}")
    print(f"Undercommit    : {compact.get('undercommitment_score')}")
    if family_mismatch:
        worst_under = max(
            family_mismatch.items(),
            key=lambda item: float((dict(item[1]).get("undercommitment_score") or -1.0)),
        )[0]
        worst_unsafe = max(
            family_mismatch.items(),
            key=lambda item: float((dict(item[1]).get("unsafe_overcommit_rate") or -1.0)),
        )[0]
        print(f"Worst Under    : {worst_under}")
        print(f"Worst Unsafe   : {worst_unsafe}")
    sweep = dict(summary.get("policy_sweep_analysis", {}))
    if sweep:
        print(f"Sweep Best     : {sweep.get('best_safe_variant') or sweep.get('best_overall_variant')}")
        print(f"Sweep Rec      : {sweep.get('recommendation')}")
    print(f"Reports        : {summary['report_paths']}")


if __name__ == "__main__":
    try:
        main()
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

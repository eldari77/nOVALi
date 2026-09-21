from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Optional

import numpy as np
import torch

from agents.memory_agent import MemoryConsciousAgent
from agents.proposal_net import ProposalNet, ProposalNetConfig
from agents.self_improvement import SelfImprovementConfig
from agents.world_model import RSSMWorldModel
from theory.nined_core import NineDLayout

from evolution.multi_agent_eval_comms import evaluate_group_with_comms
from evolution.triad_propose_personal_dummies import (
    triad_propose_test_personal_dummies,
    summarize_logs,
    adopt_patch as _adopt_patch_raw,
)


# -------------------------
# Simple built-in env
# -------------------------
class SimpleTriadEnv:
    """
    Minimal multi-agent env:
    - state: R^{state_dim}
    - action: list of 3 actions, each R^{state_dim}
    - next_state = state + 0.05 * sum(actions) + noise
    - reward = -||state||^2 (bounded-ish)
    """

    def __init__(self, state_dim: int, seed: int = 0, noise_scale: float = 0.01, horizon: int = 200):
        self.state_dim = int(state_dim)
        self.action_dim = int(state_dim)
        self.noise_scale = float(noise_scale)
        self.horizon = int(horizon)
        self._rng = np.random.default_rng(int(seed))
        self._t = 0
        self._state = np.zeros((self.state_dim,), dtype=np.float32)

    def reset(self):
        self._t = 0
        self._state = self._rng.normal(0.0, 1.0, size=(self.state_dim,)).astype(np.float32)
        return self._state.copy()

    def step(self, action):
        self._t += 1

        if action is None:
            acts = [np.zeros((self.action_dim,), dtype=np.float32) for _ in range(3)]
        elif isinstance(action, (list, tuple)):
            acts = []
            for a in action:
                if a is None:
                    acts.append(np.zeros((self.action_dim,), dtype=np.float32))
                    continue
                a = np.asarray(a, dtype=np.float32)
                if a.ndim == 2 and a.shape[0] == 1:
                    a = a.squeeze(0)
                if a.ndim > 1:
                    a = a.reshape(-1)
                if a.shape[0] < self.action_dim:
                    pad = np.zeros((self.action_dim - a.shape[0],), dtype=np.float32)
                    a = np.concatenate([a, pad], axis=0)
                elif a.shape[0] > self.action_dim:
                    a = a[: self.action_dim]
                a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32, copy=False)
                acts.append(a)
            while len(acts) < 3:
                acts.append(np.zeros((self.action_dim,), dtype=np.float32))
            acts = acts[:3]
        else:
            a0 = np.asarray(action, dtype=np.float32)
            if a0.ndim == 2 and a0.shape[0] == 1:
                a0 = a0.squeeze(0)
            if a0.ndim > 1:
                a0 = a0.reshape(-1)
            if a0.shape[0] < self.action_dim:
                pad = np.zeros((self.action_dim - a0.shape[0],), dtype=np.float32)
                a0 = np.concatenate([a0, pad], axis=0)
            elif a0.shape[0] > self.action_dim:
                a0 = a0[: self.action_dim]
            a0 = np.nan_to_num(a0, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32, copy=False)
            acts = [a0, np.zeros((self.action_dim,), dtype=np.float32), np.zeros((self.action_dim,), dtype=np.float32)]

        total = acts[0] + acts[1] + acts[2]
        noise = self._rng.normal(0.0, self.noise_scale, size=(self.state_dim,)).astype(np.float32)
        self._state = (self._state + 0.05 * total + noise).astype(np.float32)

        reward = -float(np.dot(self._state, self._state))
        done = bool(self._t >= self.horizon)
        info = {"t": self._t}
        return self._state.copy(), reward, done, info


@dataclass
class ProposalLearningConfig:
    seed: int = 0
    device: str = "cpu"
    state_dim: int = 12
    comm_vocab_size: int = 8

    rounds: int = 60

    steps_baseline: int = 150
    steps_dummy: int = 120

    critical_entropy: float = 2.0

    adapter_rank: int = 4
    adapter_alpha: float = 0.5

    use_world_model: bool = True
    wm_latent_dim: int = 16
    wm_hidden_dim: int = 64
    wm_lr: float = 3e-4
    wm_train_every: int = 10
    wm_batch_size: int = 128
    wm_min_replay: int = 1024
    wm_beta_kl: float = 0.25

    use_planning: bool = True
    plan_horizon: int = 4
    plan_candidates: int = 24
    plan_noise_std: float = 0.6
    plan_action_clip: float = 3.0

    pop_size: int = 6

    proposal_pop: int = 0
    sample_k: int = 1
    elites: int = 0
    mutation_std: float = 0.0
    immigrants: int = 0

    metrics_dim: int = 32
    proposal_hidden: int = 128
    proposal_scale: float = 0.05

    enable_self_improvement: bool = True
    self_improve_metrics_dim: int = 32
    self_improve_hidden: int = 96
    self_improve_proposal_scale: float = 0.04
    self_improve_proposal_noise_std: float = 0.05
    self_improve_min_pressure: float = 0.16
    self_improve_adopt_threshold: float = 0.08
    self_improve_patch_scale_min: float = 0.15
    self_improve_patch_scale_max: float = 0.75
    self_improve_cooldown_rounds: int = 1
    self_improve_outcome_decay: float = 0.85
    self_improve_target_c1: float = 0.60
    self_improve_target_c2: float = 0.60
    self_improve_target_c3: float = 0.60
    self_improve_target_t2: float = 0.35
    self_improve_target_goal_agreement: float = 0.75
    self_improve_max_patch_value: float = 0.20
    self_improve_patch_l2_soft: float = 0.40
    self_improve_patch_l2_hard: float = 0.55
    self_improve_patch_l2_penalty_scale: float = 0.20
    self_improve_persistence_floor: float = 0.02
    self_improve_cooldown_bypass_streak: int = 2

    adopt_threshold: float = 0.60
    adopt_threshold_persistent: float = 0.55
    adopt_threshold_provisional: float = 0.50
    adopt_patch_l2_cost: float = 0.0
    social_conf_activation: str = "sigmoid"
    social_conf_activation_scale: float = 1.25
    social_conf_center: float = 0.28
    social_conf_weight_local: float = 0.42
    social_conf_weight_ma: float = 0.18
    social_conf_weight_streak: float = 0.14
    social_conf_weight_c2: float = 0.10
    social_conf_weight_c3: float = 0.06
    social_conf_weight_retained: float = 0.14
    social_conf_weight_sz: float = 0.14
    social_conf_local_ref: float = 0.20
    social_conf_ma_ref: float = 0.25
    social_conf_streak_ref: float = 3.0
    social_conf_c2_ref: float = 1.0
    social_conf_c3_ref: float = 1.0
    social_conf_include_c2: bool = True
    social_conf_include_c3: bool = True
    social_conf_provisional_patch_scale: float = 0.35
    social_conf_provisional_decay: float = 0.80
    social_conf_provisional_release: float = 0.20
    social_conf_persistent_streak: int = 2
    social_conf_min_local_score: float = 0.0
    social_conf_full_local_min: float = 0.10
    social_conf_full_improvement_min: float = 0.04

    adoption_score_threshold_provisional: float = 0.47
    adoption_score_threshold_full: float = 0.58
    adoption_score_activation: str = "sigmoid"
    adoption_score_activation_scale: float = 1.4
    adoption_score_center: float = 0.18
    adoption_score_improve_weight: float = 0.78
    adoption_score_local_weight: float = 0.18
    adoption_score_projection_weight: float = 0.06
    adoption_score_projection_penalty_weight: float = 0.34
    adoption_score_recent_weight: float = 0.12
    adoption_score_credit_weight: float = 0.08
    adoption_score_patch_cost: float = 0.08
    adoption_score_goal_mse_weight: float = 0.08
    adoption_score_goal_agreement_weight: float = 0.02
    adoption_score_history_weight: float = 0.24
    adoption_score_instability_weight: float = 0.12
    adoption_score_improve_ref: float = 0.15
    adoption_score_local_ref: float = 0.25
    adoption_score_recent_ref: float = 80.0
    adoption_score_credit_ref: float = 20.0
    adoption_score_projection_ref: float = 1.0
    adoption_score_projection_soft: float = 1.0
    adoption_score_projection_hard: float = 2.5
    adoption_score_selection_conf_weight: float = 0.45
    adoption_score_selection_gain_weight: float = 0.55
    adoption_full_projection_error_max: float = 1.35

    wm_candidate_projection_enabled: bool = True
    wm_candidate_projection_horizon: int = 5
    wm_candidate_projection_samples: int = 3
    wm_candidate_projection_gamma: float = 0.97
    wm_candidate_projection_match_post_horizon: bool = True
    wm_candidate_projection_context_window: int = 8
    wm_candidate_projection_selection_weight: float = 0.25
    wm_candidate_pred_activation: str = "sigmoid"
    wm_candidate_pred_activation_scale: float = 1.6
    wm_candidate_pred_center: float = 0.04
    wm_candidate_pred_gain_weight: float = 0.28
    wm_candidate_pred_projection_weight: float = 0.22
    wm_candidate_pred_instability_weight: float = 0.10
    wm_candidate_pred_risk_weight: float = 0.20
    wm_candidate_pred_uncertainty_weight: float = 0.06
    wm_candidate_pred_context_weight: float = 0.14
    wm_candidate_pred_gain_sign_scale: float = 1.35
    wm_candidate_pred_projection_risk_scale: float = 1.35
    wm_candidate_pred_rollback_risk_scale: float = 1.25
    wm_candidate_pred_gain_ref: float = 2.0
    wm_candidate_pred_projection_ref: float = 0.35
    wm_candidate_pred_instability_ref: float = 0.30
    wm_candidate_pred_uncertainty_ref: float = 0.75
    wm_candidate_pred_score_threshold_full: float = 0.55
    wm_candidate_pred_score_threshold_selection: float = 0.50
    wm_candidate_pred_gain_min_full: float = 0.10
    wm_candidate_pred_gain_sign_min_full: float = 0.58
    wm_candidate_pred_projection_bad_max_provisional: float = 0.72
    wm_candidate_pred_projection_bad_max_full: float = 0.44
    wm_candidate_pred_projection_explosion_max_provisional: float = 0.72
    wm_candidate_pred_projection_explosion_max_full: float = 0.44
    wm_candidate_pred_rollback_risk_max_full: float = 0.62
    wm_candidate_pred_rollback_union_max_full: float = 0.82
    wm_candidate_pred_rollback_union_max_provisional: float = 0.90
    v4_wm_primary_plan_structure_probe_enabled: bool = False
    v4_wm_plan_context_trace_enabled: bool = False
    v4_wm_context_signal_discrimination_probe_enabled: bool = False
    v4_wm_context_signal_discrimination_weight: float = 0.32
    v4_wm_context_signal_discrimination_center: float = 0.34
    v4_wm_context_residual_signal_probe_enabled: bool = False
    v4_wm_context_residual_signal_weight: float = 0.40
    v4_wm_context_residual_signal_center: float = 0.20
    v4_wm_baseline_hybrid_boundary_probe_enabled: bool = False
    v4_wm_baseline_hybrid_boundary_weight: float = 0.24
    v4_wm_baseline_hybrid_boundary_center: float = 0.23
    v4_wm_hybrid_context_scoped_probe_enabled: bool = False
    v4_wm_hybrid_context_scoped_context_cut: float = -0.195592984061394
    v4_wm_hybrid_context_scoped_risk_cut: float = 0.562661166774877
    v4_wm_hybrid_context_scoped_context_scale: float = 0.12
    v4_wm_hybrid_context_scoped_risk_scale: float = 0.06
    v4_wm_hybrid_context_scoped_floor: float = 0.14
    v4_wm_hybrid_context_scoped_peak_boost: float = 0.10
    v4_wm_hybrid_context_stabilization_probe_enabled: bool = False
    v4_wm_hybrid_context_stabilization_context_margin: float = 0.18
    v4_wm_hybrid_context_stabilization_risk_margin: float = 0.06
    v4_wm_hybrid_context_stabilization_context_scale: float = 0.08
    v4_wm_hybrid_context_stabilization_risk_scale: float = 0.05
    v4_wm_hybrid_context_stabilization_strong_boost: float = 0.03
    v4_wm_hybrid_context_stabilization_mixed_boost: float = 0.12
    v4_wm_hybrid_context_stabilization_weak_edge_boost: float = 0.60
    v4_wm_hybrid_context_stabilization_weak_cap: float = 0.26

    adoption_realized_reward_decay: float = 0.85
    adoption_negative_cooldown_trigger: float = -150.0
    adoption_cooldown_rounds: int = 1

    adaptive_patch_scale_min: float = 0.15
    adaptive_patch_scale_max: float = 0.85
    adaptive_patch_goal_mse_soft: float = 1.25
    adaptive_patch_goal_mse_hard: float = 2.00
    adaptive_patch_credit_weight: float = 0.15
    adaptive_patch_instability_weight: float = 0.20
    adaptive_patch_cooldown_floor: float = 0.38
    fallback_improve_trigger: float = 3.0
    fallback_goal_pressure_max: float = 0.85
    rollback_on_harm: bool = True
    rollback_min_gain: float = -0.5
    rollback_max_goal_mse_increase: float = 0.10
    rollback_audit_min_rows_for_recommendation: int = 20
    shadow_audit_enabled: bool = True
    shadow_audit_conf_margin: float = 0.08
    shadow_audit_gain_margin: float = 0.08
    shadow_audit_gain_wide_margin: float = 0.25
    shadow_audit_projection_bad_max: float = 0.58
    shadow_audit_patch_scale: float = 0.35
    shadow_audit_eval_salt: int = 777

    eval_kwargs: Dict[str, Any] = field(default_factory=dict)
    benchmark_every_rounds: int = 0
    benchmark_pack_name: str = "trusted_benchmark_pack_v1"
    live_policy_variant: str = "baseline"
    live_policy_projection_margin_provisional: float = 0.0
    live_policy_targeted_projection_strict_max: float = 0.48
    live_policy_targeted_conf_margin: float = 0.14
    live_policy_targeted_gain_margin: float = 0.14
    live_policy_targeted_min_pred_gain_sign_prob: float = 0.20
    live_policy_targeted_max_pred_gain_bad_prob: float = 0.62
    live_policy_targeted_min_projected_score: float = 0.32
    live_policy_targeted_max_persistence_streak: int = 0
    live_policy_targeted_max_retained_evidence: float = 0.05
    live_policy_targeted_max_moving_average: float = 0.05
    live_policy_targeted_max_rollback_rate: float = 0.10
    live_policy_targeted_max_instability: float = 0.25
    verbose: bool = True

    def __post_init__(self):
        if isinstance(self.proposal_pop, int) and self.proposal_pop > 0:
            self.pop_size = int(self.proposal_pop)


def _seed_all(seed: int):
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _default_eval_kwargs() -> Dict[str, Any]:
    return dict(
        self_gain=0.05,
        social_gain=0.02,
        noise_scale=0.01,
        msg_temp=1.0,
        w_comm_entropy=0.8,
        w_comm_pe=0.6,
        speak_conf_threshold=0.55,
        message_cost_per_send=0.02,
        message_entropy_cost=0.02,
        w_familiarity=1.0,
        w_group_dev=1.0,
        w_pred_error=1.0,
        curiosity_weight=0.05,
        curiosity_clip=5.0,
        goal_weight=0.10,
        goal_clip=10.0,
    )


def build_triad(cfg: ProposalLearningConfig) -> List[MemoryConsciousAgent]:
    self_cfg = SelfImprovementConfig(
        metrics_dim=int(cfg.self_improve_metrics_dim),
        hidden_dim=int(cfg.self_improve_hidden),
        proposal_scale=float(cfg.self_improve_proposal_scale),
        proposal_noise_std=float(cfg.self_improve_proposal_noise_std),
        min_pressure=float(cfg.self_improve_min_pressure),
        adopt_threshold=float(cfg.self_improve_adopt_threshold),
        patch_scale_min=float(cfg.self_improve_patch_scale_min),
        patch_scale_max=float(cfg.self_improve_patch_scale_max),
        cooldown_rounds=int(cfg.self_improve_cooldown_rounds),
        outcome_decay=float(cfg.self_improve_outcome_decay),
        target_c1=float(cfg.self_improve_target_c1),
        target_c2=float(cfg.self_improve_target_c2),
        target_c3=float(cfg.self_improve_target_c3),
        target_t2=float(cfg.self_improve_target_t2),
        target_goal_agreement=float(cfg.self_improve_target_goal_agreement),
        critical_entropy=float(cfg.critical_entropy),
        max_patch_value=float(cfg.self_improve_max_patch_value),
        preferred_patch_l2_soft=float(cfg.self_improve_patch_l2_soft),
        preferred_patch_l2_hard=float(cfg.self_improve_patch_l2_hard),
        patch_l2_penalty_scale=float(cfg.self_improve_patch_l2_penalty_scale),
        persistence_floor=float(cfg.self_improve_persistence_floor),
        cooldown_bypass_streak=int(cfg.self_improve_cooldown_bypass_streak),
    )
    triad: List[MemoryConsciousAgent] = []
    for _ in range(3):
        triad.append(
            MemoryConsciousAgent(
                state_dim=cfg.state_dim,
                comm_vocab_size=cfg.comm_vocab_size,
                adapter_rank=cfg.adapter_rank,
                adapter_alpha=cfg.adapter_alpha,
                goal_latent_dim=cfg.wm_latent_dim,
                use_self_improvement=cfg.enable_self_improvement,
                self_improvement_config=self_cfg,
            )
        )
    return triad


def clone_personal_dummies(triad: List[MemoryConsciousAgent]) -> List[MemoryConsciousAgent]:
    dummies: List[MemoryConsciousAgent] = []
    for a in triad:
        d = MemoryConsciousAgent(
            state_dim=a.state_dim,
            comm_vocab_size=a.comm_vocab_size,
            adapter_rank=getattr(a.policy_adapter, "rank", 4),
            adapter_alpha=getattr(a.policy_adapter, "alpha", 0.5),
            goal_latent_dim=getattr(a, "goal_latent_dim", 16),
        )
        d.load_state_dict(a.state_dict(), strict=False)
        dummies.append(d)
    return dummies


def make_proposal_population(cfg: ProposalLearningConfig, patch_template: Dict[str, torch.Tensor]) -> List[ProposalNet]:
    pop: List[ProposalNet] = []
    p_cfg = ProposalNetConfig(
        metrics_dim=cfg.metrics_dim,
        hidden_dim=cfg.proposal_hidden,
        patch_scale=cfg.proposal_scale,
    )
    for _ in range(cfg.pop_size):
        pop.append(ProposalNet(p_cfg, patch_template))
    return pop


def _make_metrics_dict(baseline_logs: Dict[str, List[float]]) -> Dict[str, float]:
    s = summarize_logs(baseline_logs)
    return dict(
        group_dev_last=s.get("group_dev_last", 0.0),
        mean_pe_last=s.get("mean_pe_last", 0.0),
        msg_entropy_last=s.get("msg_entropy_last", 0.0),
        send_rate_last=s.get("send_rate_last", 0.0),
        curiosity_last=s.get("curiosity_last", 0.0),
        goal_agreement_last=s.get("goal_agreement_last", 0.0),
        goal_mse_latent_last=s.get("goal_mse_latent_last", 0.0),
        wm_loss_last=s.get("wm_loss_last", 0.0),
        wm_recon_last=s.get("wm_recon_last", 0.0),
        wm_kl_last=s.get("wm_kl_last", 0.0),
        wm_trained_steps_last=s.get("wm_trained_steps_last", 0.0),
    )


def _safe_float(x) -> float:
    try:
        if x is None:
            return float("nan")
        v = float(x)
        if not np.isfinite(v):
            return float("nan")
        return v
    except Exception:
        return float("nan")


def _last_metric(logs: Dict[str, Any], key: str, default: float = 0.0) -> float:
    v = logs.get(key, default)
    if isinstance(v, list):
        if len(v) == 0:
            return float(default)
        return _safe_float(v[-1])
    return _safe_float(v)


def _clip01(x: float) -> float:
    return float(np.clip(float(x), 0.0, 1.0))


def _scale_patch(patch: Dict[str, torch.Tensor], scale: float) -> Dict[str, torch.Tensor]:
    out: Dict[str, torch.Tensor] = {}
    s = float(scale)
    for k, v in patch.items():
        if torch.is_tensor(v):
            out[k] = torch.nan_to_num(v.detach(), nan=0.0, posinf=0.0, neginf=0.0) * s
    return out


def _safe_adopt_patch(agent: Any, patch: Dict[str, torch.Tensor]) -> float:
    clean: Dict[str, torch.Tensor] = {}
    for k, v in patch.items():
        if not torch.is_tensor(v):
            continue
        vv = v.detach()
        vv = torch.nan_to_num(vv, nan=0.0, posinf=0.0, neginf=0.0)
        clean[k] = vv

    try:
        sz = _adopt_patch_raw(agent, clean)
        szf = _safe_float(sz)
        return szf if np.isfinite(szf) else 0.0
    except Exception:
        return 0.0


def _compute_goal_pressure(goal_mse: float, soft: float, hard: float) -> float:
    if not np.isfinite(goal_mse):
        return 0.0
    if goal_mse <= soft:
        return 0.0
    if goal_mse >= hard:
        return 1.0
    return _clip01((goal_mse - soft) / max(1e-6, hard - soft))


def _safe_mean_arr(values: Any, default: float = 0.0) -> float:
    try:
        arr = np.asarray(values, dtype=np.float64)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            return float(default)
        return float(np.mean(arr))
    except Exception:
        return float(default)


def _safe_var_arr(values: Any, default: float = 0.0) -> float:
    try:
        arr = np.asarray(values, dtype=np.float64)
        arr = arr[np.isfinite(arr)]
        if arr.size <= 1:
            return float(default)
        return float(np.var(arr))
    except Exception:
        return float(default)


def _safe_corr(xs: Any, ys: Any, default: float = float("nan")) -> float:
    try:
        x = np.asarray(xs, dtype=np.float64).reshape(-1)
        y = np.asarray(ys, dtype=np.float64).reshape(-1)
        n = min(x.size, y.size)
        if n < 2:
            return float(default)
        x = x[:n]
        y = y[:n]
        mask = np.isfinite(x) & np.isfinite(y)
        if np.sum(mask) < 2:
            return float(default)
        x = x[mask]
        y = y[mask]
        if float(np.std(x)) < 1e-8 or float(np.std(y)) < 1e-8:
            return float(default)
        return float(np.corrcoef(x, y)[0, 1])
    except Exception:
        return float(default)


def _extract_explicit_9d_metrics(logs: Dict[str, Any]) -> Dict[str, float]:
    t2_drift = _last_metric(logs, "nine_d_delta_t2_abs_mean", _last_metric(logs, "nine_d_entropy_proxy_t2", 0.0))
    t3_phase = _last_metric(logs, "nine_d_phase_proxy_t3", 0.0)
    t3_delta = _last_metric(logs, "nine_d_delta_t3_abs_mean", 0.0)
    c1 = _last_metric(logs, "nine_d_c1_complexity", 0.0)
    c2 = _last_metric(logs, "nine_d_c2_self_model", 0.0)
    c3 = _last_metric(logs, "nine_d_c3_observer_stability", 0.0)
    proj_err = _last_metric(logs, "nine_d_projection_mse_4d", _last_metric(logs, "wm_projection_mse_4d", 0.0))
    t3_coherence = 1.0 / (1.0 + max(0.0, float(t3_phase)) + max(0.0, float(t3_delta)))
    return {
        "T2_drift": float(t2_drift),
        "T3_coherence": float(t3_coherence),
        "C1_integration": float(c1),
        "C2_self_model_strength": float(c2),
        "C3_perspective_stability": float(c3),
        "projection_error": float(proj_err),
    }


def _tail_values(logs: Dict[str, Any], key: str, window: int) -> List[float]:
    values = logs.get(key, [])
    if not isinstance(values, list):
        return []
    out: List[float] = []
    for value in values[-max(int(window), 1):]:
        vf = _safe_float(value)
        if np.isfinite(vf):
            out.append(float(vf))
    return out


def _tail_mean(logs: Dict[str, Any], key: str, window: int, default: float = 0.0) -> float:
    return _safe_mean_arr(_tail_values(logs, key, window), default=default)


def _tail_delta(logs: Dict[str, Any], key: str, window: int, default: float = 0.0) -> float:
    values = _tail_values(logs, key, window)
    if len(values) < 2:
        return float(default)
    return float(values[-1] - values[0])


def _norm_tanh(value: float, ref: float) -> float:
    return float(np.tanh(float(value) / max(float(ref), 1e-6)))


def _centered_sigmoid(value: float, ref: float) -> float:
    scaled = float(value) / max(float(ref), 1e-6)
    return float(2.0 / (1.0 + np.exp(-scaled)) - 1.0)


def _inverse_centered(value: float, ref: float) -> float:
    ratio = max(0.0, float(value)) / max(float(ref), 1e-6)
    stable = 1.0 / (1.0 + ratio)
    return float(2.0 * stable - 1.0)


def _confidence_activation(x: float, mode: str, scale: float, center: float = 0.0) -> float:
    z = float(scale) * (float(x) - float(center))
    if str(mode).lower() == "tanh":
        return float(0.5 * (np.tanh(z) + 1.0))
    return float(1.0 / (1.0 + np.exp(-z)))


def _compute_social_confidence(
    *,
    cfg: ProposalLearningConfig,
    local_score: float,
    moving_average: float,
    persistence_streak: int,
    c2_strength: float,
    c3_stability: float,
    patch_size: float,
    retained_evidence: float,
) -> Dict[str, Any]:
    local_norm = _norm_tanh(local_score, float(cfg.social_conf_local_ref))
    ma_norm = _norm_tanh(moving_average, float(cfg.social_conf_ma_ref))
    streak_norm = float(np.clip(float(persistence_streak) / max(float(cfg.social_conf_streak_ref), 1e-6), 0.0, 1.0))
    c2_norm = _centered_sigmoid(c2_strength, float(cfg.social_conf_c2_ref)) if bool(cfg.social_conf_include_c2) else 0.0
    c3_norm = _centered_sigmoid(c3_stability, float(cfg.social_conf_c3_ref)) if bool(cfg.social_conf_include_c3) else 0.0
    retained_norm = float(np.clip(float(retained_evidence), 0.0, 1.0))
    sz_penalty = 0.0
    if float(patch_size) > float(cfg.self_improve_patch_l2_soft):
        sz_penalty = float(
            np.clip(
                (float(patch_size) - float(cfg.self_improve_patch_l2_soft))
                / max(float(cfg.self_improve_patch_l2_hard) - float(cfg.self_improve_patch_l2_soft), 1e-6),
                0.0,
                1.5,
            )
        )
    components = {
        "local": float(cfg.social_conf_weight_local) * local_norm,
        "moving_average": float(cfg.social_conf_weight_ma) * ma_norm,
        "streak": float(cfg.social_conf_weight_streak) * streak_norm,
        "c2": float(cfg.social_conf_weight_c2) * c2_norm,
        "c3": float(cfg.social_conf_weight_c3) * c3_norm,
        "retained": float(cfg.social_conf_weight_retained) * retained_norm,
        "sz_penalty": float(cfg.social_conf_weight_sz) * sz_penalty,
    }
    raw = (
        components["local"]
        + components["moving_average"]
        + components["streak"]
        + components["c2"]
        + components["c3"]
        + components["retained"]
        - components["sz_penalty"]
    )
    calibrated = _confidence_activation(raw, str(cfg.social_conf_activation), float(cfg.social_conf_activation_scale), float(cfg.social_conf_center))
    persistent = bool(
        int(persistence_streak) >= int(cfg.social_conf_persistent_streak)
        or float(retained_evidence) >= float(cfg.adopt_threshold_provisional)
    )
    full_threshold = float(cfg.adopt_threshold_persistent if persistent else cfg.adopt_threshold)
    provisional_threshold = float(min(cfg.adopt_threshold_provisional, full_threshold))
    return {
        "raw_confidence": float(raw),
        "calibrated_confidence": float(calibrated),
        "full_threshold": float(full_threshold),
        "provisional_threshold": float(provisional_threshold),
        "threshold_mode": "persistent" if persistent else "base",
        "components": components,
    }


def _compute_social_improvement_signal(
    *,
    cfg: ProposalLearningConfig,
    dummy_improvement: float,
    local_score: float,
    recent_realized: float,
    proposer_credit: float,
    rollback_rate: float,
    projection_error: float,
    goal_pressure: float,
    instability: float,
    patch_size: float,
) -> Dict[str, Any]:
    improve_norm = _norm_tanh(dummy_improvement, float(cfg.adoption_score_improve_ref))
    local_norm = _norm_tanh(local_score, float(cfg.adoption_score_local_ref))
    recent_norm = _norm_tanh(recent_realized, float(cfg.adoption_score_recent_ref))
    credit_norm = _norm_tanh(proposer_credit, float(cfg.adoption_score_credit_ref))
    projection_quality = float(
        np.clip(
            1.0 - float(projection_error) / max(float(cfg.adoption_score_projection_ref), 1e-6),
            -1.0,
            1.0,
        )
    )
    projection_penalty = 0.0
    if float(projection_error) > float(cfg.adoption_score_projection_soft):
        projection_penalty = float(
            np.clip(
                (float(projection_error) - float(cfg.adoption_score_projection_soft))
                / max(float(cfg.adoption_score_projection_hard) - float(cfg.adoption_score_projection_soft), 1e-6),
                0.0,
                2.0,
            )
        )
    sz_penalty = 0.0
    if float(patch_size) > float(cfg.self_improve_patch_l2_soft):
        sz_penalty = float(
            np.clip(
                (float(patch_size) - float(cfg.self_improve_patch_l2_soft))
                / max(float(cfg.self_improve_patch_l2_hard) - float(cfg.self_improve_patch_l2_soft), 1e-6),
                0.0,
                1.5,
            )
        )
    rollback_penalty = float(np.clip(float(rollback_rate), 0.0, 1.0) ** 1.15)
    components = {
        "improve": float(cfg.adoption_score_improve_weight) * improve_norm,
        "local": float(cfg.adoption_score_local_weight) * local_norm,
        "projection": float(cfg.adoption_score_projection_weight) * projection_quality,
        "recent": float(cfg.adoption_score_recent_weight) * recent_norm,
        "credit": float(cfg.adoption_score_credit_weight) * credit_norm,
        "projection_penalty": -float(cfg.adoption_score_projection_penalty_weight) * projection_penalty,
        "rollback_penalty": -float(cfg.adoption_score_history_weight) * rollback_penalty,
        "goal_penalty": -float(cfg.adoption_score_goal_mse_weight) * _clip01(goal_pressure),
        "instability_penalty": -float(cfg.adoption_score_instability_weight) * _clip01(instability),
        "sz_penalty": -float(cfg.adoption_score_patch_cost) * sz_penalty,
    }
    raw = float(sum(components.values()))
    calibrated = _confidence_activation(raw, str(cfg.adoption_score_activation), float(cfg.adoption_score_activation_scale), float(cfg.adoption_score_center))
    return {
        "raw_gain": float(raw),
        "calibrated_gain": float(calibrated),
        "provisional_threshold": float(cfg.adoption_score_threshold_provisional),
        "full_threshold": float(cfg.adoption_score_threshold_full),
        "components": components,
        "projection_error": float(projection_error),
        "rollback_rate": float(rollback_rate),
        "goal_pressure": float(_clip01(goal_pressure)),
        "projection_ok_full": bool(float(projection_error) <= float(cfg.adoption_full_projection_error_max)),
    }


def _format_confidence_components(components: Dict[str, float]) -> str:
    return (
        f"[local={components.get('local', 0.0):+.3f} "
        f"ma={components.get('moving_average', 0.0):+.3f} "
        f"streak={components.get('streak', 0.0):+.3f} "
        f"c2={components.get('c2', 0.0):+.3f} "
        f"c3={components.get('c3', 0.0):+.3f} "
        f"retained={components.get('retained', 0.0):+.3f} "
        f"sz_penalty={components.get('sz_penalty', 0.0):+.3f}]"
    )


def _format_improvement_components(components: Dict[str, float]) -> str:
    return (
        f"[gain={components.get('improve', 0.0):+.3f} "
        f"local={components.get('local', 0.0):+.3f} "
        f"proj={components.get('projection', 0.0):+.3f} "
        f"proj_penalty={components.get('projection_penalty', 0.0):+.3f} "
        f"recent={components.get('recent', 0.0):+.3f} "
        f"credit={components.get('credit', 0.0):+.3f} "
        f"rollback={components.get('rollback_penalty', 0.0):+.3f} "
        f"goal={components.get('goal_penalty', 0.0):+.3f} "
        f"instability={components.get('instability_penalty', 0.0):+.3f} "
        f"sz_penalty={components.get('sz_penalty', 0.0):+.3f}]"
    )


def _extract_env_reset_obs(env: Any, n_agents: int, state_dim: int) -> Optional[np.ndarray]:
    if env is None:
        return None
    try:
        obs = env.reset()
    except Exception:
        return None
    if isinstance(obs, tuple) and len(obs) > 0:
        obs = obs[0]
    arr = np.asarray(obs, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.shape[1] < int(state_dim):
        arr = np.concatenate([arr, np.zeros((arr.shape[0], int(state_dim) - arr.shape[1]), dtype=np.float32)], axis=1)
    elif arr.shape[1] > int(state_dim):
        arr = arr[:, : int(state_dim)]
    if arr.shape[0] == 1:
        arr = np.repeat(arr, int(n_agents), axis=0)
    elif arr.shape[0] < int(n_agents):
        reps = int(np.ceil(float(n_agents) / float(max(arr.shape[0], 1))))
        arr = np.tile(arr, (reps, 1))[: int(n_agents)]
    elif arr.shape[0] > int(n_agents):
        arr = arr[: int(n_agents)]
    return np.nan_to_num(arr.astype(np.float32, copy=False), nan=0.0, posinf=0.0, neginf=0.0)


def _shadow_reward_proxy(
    shared_state: torch.Tensor,
    *,
    layout: Optional[NineDLayout],
    action: Optional[torch.Tensor] = None,
    state_batch: Optional[torch.Tensor] = None,
    instability: float = 0.0,
) -> float:
    shared_state = torch.nan_to_num(shared_state.detach().float(), nan=0.0, posinf=0.0, neginf=0.0)
    if layout is not None:
        metrics = layout.state_metrics(shared_state, action=action)
        return float(
            metrics.get("nine_d_c1_complexity", 0.0)
            + 0.25 * metrics.get("nine_d_c2_self_model", 0.0)
            + 0.25 * metrics.get("nine_d_c3_observer_stability", 0.0)
            - 0.10 * metrics.get("nine_d_entropy_proxy_t2", 0.0)
            - 0.10 * float(instability)
        )
    if state_batch is not None:
        per_agent_energy = torch.sum(state_batch * state_batch, dim=-1)
        return -float(per_agent_energy.mean().detach().cpu().item()) - 0.50 * float(instability)
    return -float(torch.dot(shared_state, shared_state).detach().cpu().item())


@torch.no_grad()
def _world_model_shadow_rollout(
    *,
    agents: List[MemoryConsciousAgent],
    world_model: Optional[RSSMWorldModel],
    start_obs: Optional[np.ndarray],
    horizon: int,
    samples: int,
    gamma: float,
    seed_base: int,
) -> Dict[str, Any]:
    if world_model is None or start_obs is None or int(horizon) <= 0 or int(samples) <= 0 or len(agents) == 0:
        return {
            "available": False,
            "pred_return_mean": 0.0,
            "pred_return_std": 0.0,
            "pred_projection_error_mean": 0.0,
            "pred_projection_error_std": 0.0,
            "pred_projection_error_peak_mean": 0.0,
            "pred_instability_mean": 0.0,
            "pred_instability_std": 0.0,
            "pred_instability_peak_mean": 0.0,
            "pred_entropy_mean": 0.0,
            "pred_c1_mean": 0.0,
            "pred_c2_mean": 0.0,
            "pred_t3_mean": 0.0,
            "pred_c3_mean": 0.0,
        }

    device = next(world_model.parameters()).device
    start_batch = torch.as_tensor(start_obs, dtype=torch.float32, device=device)
    if start_batch.ndim == 1:
        start_batch = start_batch.unsqueeze(0)
    if start_batch.shape[0] != len(agents):
        start_batch = start_batch[:1].repeat(len(agents), 1)
    start_batch = torch.nan_to_num(start_batch, nan=0.0, posinf=0.0, neginf=0.0)
    layout = NineDLayout(total_state_dim=int(start_batch.shape[-1])) if int(start_batch.shape[-1]) >= 9 else None
    if layout is not None:
        layout.validate()

    prev_mode = bool(world_model.training)
    prev_state = world_model.snapshot_internal_state() if hasattr(world_model, "snapshot_internal_state") else None
    prev_rng = torch.random.get_rng_state()
    sample_returns: List[float] = []
    sample_projection: List[float] = []
    sample_projection_peaks: List[float] = []
    sample_instability: List[float] = []
    sample_instability_peaks: List[float] = []
    sample_entropy: List[float] = []
    sample_c1: List[float] = []
    sample_c2: List[float] = []
    sample_t3: List[float] = []
    sample_c3: List[float] = []
    try:
        world_model.eval()
        for sample_idx in range(int(samples)):
            torch.manual_seed(int(seed_base) + int(sample_idx))
            world_model.reset(batch_size=len(agents), device=device)
            current_batch = start_batch.clone()
            discount = 1.0
            total_return = 0.0
            projection_trace: List[float] = []
            instability_trace: List[float] = []
            entropy_trace: List[float] = []
            c1_trace: List[float] = []
            c2_trace: List[float] = []
            t3_trace: List[float] = []
            c3_trace: List[float] = []
            for _ in range(int(horizon)):
                actions: List[torch.Tensor] = []
                for idx, agent in enumerate(agents):
                    try:
                        out = agent(current_batch[idx], comm_in=None)
                    except TypeError:
                        out = agent(current_batch[idx])
                    action = out[0] if isinstance(out, (tuple, list)) else out
                    action = torch.as_tensor(action, dtype=torch.float32, device=device).reshape(-1)
                    if action.numel() < current_batch.shape[-1]:
                        action = torch.cat([action, torch.zeros(current_batch.shape[-1] - action.numel(), device=device)], dim=0)
                    elif action.numel() > current_batch.shape[-1]:
                        action = action[: current_batch.shape[-1]]
                    actions.append(torch.nan_to_num(action, nan=0.0, posinf=0.0, neginf=0.0))
                action_batch = torch.stack(actions, dim=0)
                pred_next_batch, _ = world_model.step(current_batch, action_batch, use_posterior=True)
                pred_next_batch = torch.nan_to_num(pred_next_batch.detach(), nan=0.0, posinf=0.0, neginf=0.0)
                instability = float(pred_next_batch.std(dim=0).mean().detach().cpu().item())
                shared_state = pred_next_batch.mean(dim=0)
                if layout is not None:
                    pred_next_batch = layout.clamp_core(pred_next_batch)
                    shared_state = pred_next_batch.mean(dim=0)
                    reward = _shadow_reward_proxy(shared_state, layout=layout, action=action_batch.mean(dim=0), state_batch=pred_next_batch, instability=instability)
                    proj_batch = layout.project_to_4d(pred_next_batch)
                    proj_mean = proj_batch.mean(dim=0, keepdim=True)
                    projection_error = float(torch.mean((proj_batch - proj_mean) ** 2).detach().cpu().item())
                    metrics = layout.state_metrics(shared_state, action=action_batch.mean(dim=0))
                    entropy = float(metrics.get("nine_d_entropy_proxy_t2", 0.0))
                    c1_value = float(metrics.get("nine_d_c1_complexity", 0.0))
                    c2_value = float(metrics.get("nine_d_c2_self_model", 0.0))
                    t3_value = float(metrics.get("nine_d_phase_proxy_t3", 0.0))
                    c3_value = float(metrics.get("nine_d_c3_observer_stability", 0.0))
                else:
                    reward = _shadow_reward_proxy(shared_state, layout=None, state_batch=pred_next_batch, instability=instability)
                    projection_error = float(instability)
                    entropy = 0.0
                    c1_value = 0.0
                    c2_value = 0.0
                    t3_value = 0.0
                    c3_value = 0.0
                total_return += discount * float(reward)
                discount *= float(gamma)
                projection_trace.append(float(projection_error))
                instability_trace.append(float(instability))
                entropy_trace.append(float(entropy))
                c1_trace.append(float(c1_value))
                c2_trace.append(float(c2_value))
                t3_trace.append(float(t3_value))
                c3_trace.append(float(c3_value))
                current_batch = pred_next_batch
            sample_returns.append(float(total_return))
            sample_projection.append(float(_safe_mean_arr(projection_trace, default=0.0)))
            sample_projection_peaks.append(float(np.max(np.asarray(projection_trace, dtype=np.float64))) if projection_trace else 0.0)
            sample_instability.append(float(_safe_mean_arr(instability_trace, default=0.0)))
            sample_instability_peaks.append(float(np.max(np.asarray(instability_trace, dtype=np.float64))) if instability_trace else 0.0)
            sample_entropy.append(float(_safe_mean_arr(entropy_trace, default=0.0)))
            sample_c1.append(float(_safe_mean_arr(c1_trace, default=0.0)))
            sample_c2.append(float(_safe_mean_arr(c2_trace, default=0.0)))
            sample_t3.append(float(_safe_mean_arr(t3_trace, default=0.0)))
            sample_c3.append(float(_safe_mean_arr(c3_trace, default=0.0)))
    finally:
        if hasattr(world_model, "restore_internal_state"):
            world_model.restore_internal_state(prev_state)
        torch.random.set_rng_state(prev_rng)
        world_model.train(prev_mode)
    return {
        "available": True,
        "pred_return_mean": float(_safe_mean_arr(sample_returns, default=0.0)),
        "pred_return_std": float(np.std(np.asarray(sample_returns, dtype=np.float64))) if sample_returns else 0.0,
        "pred_projection_error_mean": float(_safe_mean_arr(sample_projection, default=0.0)),
        "pred_projection_error_std": float(np.std(np.asarray(sample_projection, dtype=np.float64))) if sample_projection else 0.0,
        "pred_projection_error_peak_mean": float(_safe_mean_arr(sample_projection_peaks, default=0.0)),
        "pred_instability_mean": float(_safe_mean_arr(sample_instability, default=0.0)),
        "pred_instability_std": float(np.std(np.asarray(sample_instability, dtype=np.float64))) if sample_instability else 0.0,
        "pred_instability_peak_mean": float(_safe_mean_arr(sample_instability_peaks, default=0.0)),
        "pred_entropy_mean": float(_safe_mean_arr(sample_entropy, default=0.0)),
        "pred_c1_mean": float(_safe_mean_arr(sample_c1, default=0.0)),
        "pred_c2_mean": float(_safe_mean_arr(sample_c2, default=0.0)),
        "pred_t3_mean": float(_safe_mean_arr(sample_t3, default=0.0)),
        "pred_c3_mean": float(_safe_mean_arr(sample_c3, default=0.0)),
    }


def _build_forecast_context(
    *,
    cfg: ProposalLearningConfig,
    baseline_logs: Dict[str, Any],
    baseline_9d_metrics: Dict[str, float],
    proposer_recent_realized: float,
    proposer_rollback_rate: float,
    retained_evidence: float,
    retained_rounds: int,
    realized_gain_history: List[float],
) -> Dict[str, float]:
    window = max(int(cfg.wm_candidate_projection_context_window), 1)
    wm_loss_recent = _tail_mean(baseline_logs, "wm_loss", window, default=0.0)
    wm_recon_recent = _tail_mean(baseline_logs, "wm_recon", window, default=0.0)
    wm_kl_recent = _tail_mean(baseline_logs, "wm_kl", window, default=0.0)
    return {
        "t2_recent": float(_tail_mean(baseline_logs, "nine_d_entropy_proxy_t2", window, default=float(baseline_9d_metrics.get("T2_drift", 0.0)))),
        "t3_recent": float(_tail_mean(baseline_logs, "nine_d_phase_proxy_t3", window, default=max(0.0, 1.0 - float(baseline_9d_metrics.get("T3_coherence", 0.0))))),
        "c1_recent": float(_tail_mean(baseline_logs, "nine_d_c1_complexity", window, default=float(baseline_9d_metrics.get("C1_integration", 0.0)))),
        "c2_recent": float(_tail_mean(baseline_logs, "nine_d_c2_self_model", window, default=float(baseline_9d_metrics.get("C2_self_model_strength", 0.0)))),
        "c3_recent": float(_tail_mean(baseline_logs, "nine_d_c3_observer_stability", window, default=float(baseline_9d_metrics.get("C3_perspective_stability", 0.0)))),
        "projection_recent": float(_tail_mean(baseline_logs, "nine_d_projection_mse_4d", window, default=float(baseline_9d_metrics.get("projection_error", 0.0)))),
        "projection_trend": float(_tail_delta(baseline_logs, "nine_d_projection_mse_4d", window, default=0.0)),
        "wm_quality_penalty": float(np.clip(wm_loss_recent + 0.5 * wm_recon_recent + 0.25 * wm_kl_recent, 0.0, 4.0)),
        "proposer_rollback_rate": float(np.clip(proposer_rollback_rate, 0.0, 1.0)),
        "retained_evidence": float(np.clip(retained_evidence, 0.0, 1.0)),
        "retained_rounds": float(max(0, int(retained_rounds))),
        "recent_realized": float(proposer_recent_realized),
        "recent_gain_scale": float(max(1.0, _safe_mean_arr(np.abs(np.asarray(realized_gain_history[-window:], dtype=np.float64)), default=0.0))),
    }


def _sigmoid_prob(x: float, scale: float = 1.0, center: float = 0.0) -> float:
    z = float(scale) * (float(x) - float(center))
    return float(1.0 / (1.0 + np.exp(-z)))


def _compute_projected_outcome_signal(
    *,
    cfg: ProposalLearningConfig,
    baseline_shadow: Dict[str, Any],
    candidate_shadow: Dict[str, Any],
    forecast_context: Dict[str, float],
) -> Dict[str, Any]:
    if not bool(candidate_shadow.get("available", False)) or not bool(baseline_shadow.get("available", False)):
        return {
            "available": False,
            "pred_post_gain": 0.0,
            "pred_gain_norm": 0.0,
            "pred_gain_sign_prob": 0.0,
            "pred_gain_bad_prob": 1.0,
            "pred_goal_bad_prob": 1.0,
            "pred_projection_error": 0.0,
            "pred_projection_peak": 0.0,
            "pred_projection_delta": 0.0,
            "pred_projection_explosion_prob": 1.0,
            "pred_projection_bad_prob": 1.0,
            "pred_instability": 0.0,
            "pred_instability_delta": 0.0,
            "pred_rollback_risk": 1.0,
            "pred_rollback_union": 1.0,
            "pred_uncertainty": 0.0,
            "pred_context_score": 0.0,
            "pred_c1": 0.0,
            "pred_c2": 0.0,
            "pred_t3": 0.0,
            "pred_c3": 0.0,
            "raw_projected": 0.0,
            "calibrated_projected": 0.0,
            "components": {},
        }

    pred_post_gain = float(candidate_shadow.get("pred_return_mean", 0.0) - baseline_shadow.get("pred_return_mean", 0.0))
    pred_projection_error = float(candidate_shadow.get("pred_projection_error_mean", 0.0))
    pred_projection_peak = float(candidate_shadow.get("pred_projection_error_peak_mean", pred_projection_error))
    pred_projection_delta = float(candidate_shadow.get("pred_projection_error_mean", 0.0) - baseline_shadow.get("pred_projection_error_mean", 0.0))
    pred_instability = float(candidate_shadow.get("pred_instability_mean", 0.0))
    pred_instability_delta = float(candidate_shadow.get("pred_instability_mean", 0.0) - baseline_shadow.get("pred_instability_mean", 0.0))
    pred_c1_delta = float(candidate_shadow.get("pred_c1_mean", 0.0) - baseline_shadow.get("pred_c1_mean", 0.0))
    pred_c2_delta = float(candidate_shadow.get("pred_c2_mean", 0.0) - baseline_shadow.get("pred_c2_mean", 0.0))
    pred_t3_delta = float(candidate_shadow.get("pred_t3_mean", 0.0) - baseline_shadow.get("pred_t3_mean", 0.0))
    pred_c3_delta = float(candidate_shadow.get("pred_c3_mean", 0.0) - baseline_shadow.get("pred_c3_mean", 0.0))
    gain_ref = max(float(cfg.wm_candidate_pred_gain_ref), float(candidate_shadow.get("pred_return_std", 0.0)) + float(baseline_shadow.get("pred_return_std", 0.0)), 1e-6)
    proj_ref = max(float(cfg.wm_candidate_pred_projection_ref), float(candidate_shadow.get("pred_projection_error_std", 0.0)) + float(baseline_shadow.get("pred_projection_error_std", 0.0)), 1e-6)
    inst_ref = max(float(cfg.wm_candidate_pred_instability_ref), float(candidate_shadow.get("pred_instability_std", 0.0)) + float(baseline_shadow.get("pred_instability_std", 0.0)), 1e-6)
    pred_gain_norm = _norm_tanh(pred_post_gain, gain_ref)
    pred_uncertainty = float(candidate_shadow.get("pred_return_std", 0.0) + candidate_shadow.get("pred_projection_error_std", 0.0) + 0.50 * candidate_shadow.get("pred_instability_std", 0.0))
    proj_delta_norm = _norm_tanh(max(0.0, pred_projection_delta), proj_ref)
    proj_level_norm = _norm_tanh(pred_projection_error - float(cfg.adoption_full_projection_error_max), proj_ref)
    proj_peak_norm = _norm_tanh(pred_projection_peak - float(cfg.adoption_full_projection_error_max), proj_ref)
    inst_norm = _norm_tanh(max(0.0, pred_instability_delta), inst_ref)
    c1_norm = _norm_tanh(pred_c1_delta, 0.25)
    c2_norm = _norm_tanh(pred_c2_delta, 0.25)
    c3_norm = _norm_tanh(pred_c3_delta, 0.25)
    t3_support_delta = -_norm_tanh(pred_t3_delta, 0.25)

    t2_pressure = float(np.clip(float(forecast_context.get("t2_recent", 0.0)) / max(float(cfg.critical_entropy), 1e-6), 0.0, 2.0))
    t3_support = _inverse_centered(float(forecast_context.get("t3_recent", 0.0)), 1.0)
    c2_support = _centered_sigmoid(float(forecast_context.get("c2_recent", 0.0)), 1.0)
    c3_support = _centered_sigmoid(float(forecast_context.get("c3_recent", 0.0)), 1.0)
    projection_context = float(np.clip(float(forecast_context.get("projection_recent", 0.0)) / max(float(cfg.adoption_full_projection_error_max), 1e-6), 0.0, 2.0))
    projection_trend = _norm_tanh(float(forecast_context.get("projection_trend", 0.0)), proj_ref)
    wm_penalty = float(np.clip(float(forecast_context.get("wm_quality_penalty", 0.0)) / 2.0, 0.0, 1.5))
    rollback_history = float(np.clip(float(forecast_context.get("proposer_rollback_rate", 0.0)), 0.0, 1.0))
    retained_norm = float(np.clip(float(forecast_context.get("retained_evidence", 0.0)), 0.0, 1.0))
    retained_rounds_norm = float(np.clip(float(forecast_context.get("retained_rounds", 0.0)) / max(float(cfg.social_conf_streak_ref), 1e-6), 0.0, 1.0))
    recent_realized_norm = _norm_tanh(float(forecast_context.get("recent_realized", 0.0)), max(25.0, 0.25 * float(forecast_context.get("recent_gain_scale", 1.0))))
    local_gain_support = _norm_tanh(float(forecast_context.get("dummy_improvement", 0.0)), max(float(cfg.adoption_score_improve_ref), 1e-6))
    goal_pressure = _goal_bad_prob(float(forecast_context.get("goal_pressure", 0.0)))
    gain_conf_support = float(2.0 * np.clip(float(forecast_context.get("gain_cal", 0.5)), 0.0, 1.0) - 1.0)
    coherence_support = float(2.0 * np.clip(float(forecast_context.get("coherence_cal", 0.5)), 0.0, 1.0) - 1.0)
    context_support = float(
        0.22 * c2_support
        + 0.22 * c3_support
        + 0.12 * t3_support
        + 0.08 * retained_norm
        + 0.06 * retained_rounds_norm
        + 0.08 * recent_realized_norm
        + 0.08 * local_gain_support
        + 0.06 * gain_conf_support
        + 0.04 * coherence_support
        - 0.12 * projection_context
        - 0.06 * max(0.0, projection_trend)
        - 0.08 * wm_penalty
        - 0.08 * rollback_history
        - 0.06 * t2_pressure
    )
    gain_logit = float(
        1.10 * pred_gain_norm
        + 0.20 * c1_norm
        + 0.30 * c2_norm
        + 0.28 * c3_norm
        + 0.22 * t3_support_delta
        + 0.35 * context_support
        + 0.45 * local_gain_support
        + 0.22 * gain_conf_support
        + 0.10 * coherence_support
        - 0.55 * max(0.0, proj_delta_norm)
        - 0.42 * max(0.0, inst_norm)
    )
    pred_gain_sign_prob = _sigmoid_prob(gain_logit, float(cfg.wm_candidate_pred_gain_sign_scale), 0.10)
    explosion_logit = float(
        0.95 * max(0.0, proj_level_norm)
        + 0.85 * max(0.0, proj_peak_norm)
        + 0.60 * max(0.0, proj_delta_norm)
        + 0.35 * max(0.0, inst_norm)
        + 0.22 * projection_context
        + 0.16 * max(0.0, projection_trend)
        + 0.16 * wm_penalty
        + 0.10 * t2_pressure
        + 0.08 * rollback_history
        + 0.14 * max(0.0, -local_gain_support)
        - 0.18 * c3_norm
        - 0.14 * t3_support_delta
        - 0.10 * retained_rounds_norm
        - 0.10 * max(0.0, local_gain_support)
    )
    pred_projection_explosion_prob = _sigmoid_prob(
        explosion_logit,
        0.85 * float(cfg.wm_candidate_pred_projection_risk_scale),
        0.28,
    )
    rollback_logit = float(
        0.82 * (2.0 * pred_projection_explosion_prob - 1.0)
        + 0.60 * max(0.0, -pred_gain_norm)
        + 0.38 * max(0.0, inst_norm)
        + 0.24 * rollback_history
        + 0.22 * wm_penalty
        + 0.12 * projection_context
        + 0.08 * t2_pressure
        + 0.20 * max(0.0, -local_gain_support)
        - 0.14 * c3_support
        - 0.10 * retained_norm
        - 0.16 * max(0.0, local_gain_support)
        - 0.12 * gain_conf_support
    )
    pred_rollback_risk = _sigmoid_prob(
        rollback_logit,
        0.80 * float(cfg.wm_candidate_pred_rollback_risk_scale),
        0.32,
    )
    pred_gain_bad_prob = _gain_bad_prob(pred_gain_norm, pred_gain_sign_prob)
    pred_goal_bad_prob = float(goal_pressure)
    pred_projection_bad_prob = float(np.clip(pred_projection_explosion_prob, 0.0, 1.0))
    pred_rollback_union = _probabilistic_union(pred_projection_bad_prob, pred_gain_bad_prob, pred_goal_bad_prob)
    components = {
        "pred_gain": float(cfg.wm_candidate_pred_gain_weight) * (0.65 * (2.0 * pred_gain_sign_prob - 1.0) + 0.35 * pred_gain_norm),
        "pred_projection": -float(cfg.wm_candidate_pred_projection_weight) * float(np.clip(pred_projection_bad_prob, 0.0, 1.0)),
        "pred_instability": -float(cfg.wm_candidate_pred_instability_weight) * float(np.clip(max(0.0, inst_norm), 0.0, 1.0)),
        "pred_union": -0.35 * float(cfg.wm_candidate_pred_risk_weight) * float(np.clip(pred_rollback_union, 0.0, 1.0)),
        "pred_uncertainty": -float(cfg.wm_candidate_pred_uncertainty_weight) * float(np.clip(pred_uncertainty / max(float(cfg.wm_candidate_pred_uncertainty_ref), 1e-6), 0.0, 2.0)),
        "pred_context": float(cfg.wm_candidate_pred_context_weight) * float(np.clip(context_support, -1.0, 1.0)),
    }
    raw = float(sum(components.values()))
    calibrated = _confidence_activation(raw, str(cfg.wm_candidate_pred_activation), float(cfg.wm_candidate_pred_activation_scale), float(cfg.wm_candidate_pred_center))
    return {
        "available": True,
        "pred_post_gain": float(pred_post_gain),
        "pred_gain_norm": float(pred_gain_norm),
        "pred_gain_sign_prob": float(pred_gain_sign_prob),
        "pred_gain_bad_prob": float(pred_gain_bad_prob),
        "pred_goal_bad_prob": float(pred_goal_bad_prob),
        "pred_projection_error": float(pred_projection_error),
        "pred_projection_peak": float(pred_projection_peak),
        "pred_projection_delta": float(pred_projection_delta),
        "pred_projection_explosion_prob": float(pred_projection_explosion_prob),
        "pred_projection_bad_prob": float(pred_projection_bad_prob),
        "pred_instability": float(pred_instability),
        "pred_instability_delta": float(pred_instability_delta),
        "pred_rollback_risk": float(pred_rollback_risk),
        "pred_rollback_union": float(pred_rollback_union),
        "pred_uncertainty": float(pred_uncertainty),
        "pred_context_score": float(context_support),
        "pred_c1": float(candidate_shadow.get("pred_c1_mean", 0.0)),
        "pred_c2": float(candidate_shadow.get("pred_c2_mean", 0.0)),
        "pred_t3": float(candidate_shadow.get("pred_t3_mean", 0.0)),
        "pred_c3": float(candidate_shadow.get("pred_c3_mean", 0.0)),
        "raw_projected": float(raw),
        "calibrated_projected": float(calibrated),
        "components": components,
    }


def _format_projected_components(components: Dict[str, float]) -> str:
    discr = ""
    if "v4_wm_context_discrimination" in components:
        discr = f" v4_discr={components.get('v4_wm_context_discrimination', 0.0):+.3f}"
    residual = ""
    if "v4_wm_context_residual_signal" in components:
        residual = f" v4_resid={components.get('v4_wm_context_residual_signal', 0.0):+.3f}"
    hybrid = ""
    if "v4_wm_baseline_hybrid_boundary" in components:
        hybrid = f" v4_hybrid={components.get('v4_wm_baseline_hybrid_boundary', 0.0):+.3f}"
    return (
        f"[pred_gain={components.get('pred_gain', 0.0):+.3f} "
        f"pred_proj={components.get('pred_projection', 0.0):+.3f} "
        f"pred_instability={components.get('pred_instability', 0.0):+.3f} "
        f"pred_union={components.get('pred_union', 0.0):+.3f} "
        f"pred_uncertainty={components.get('pred_uncertainty', 0.0):+.3f} "
        f"pred_context={components.get('pred_context', 0.0):+.3f}{discr}{residual}{hybrid}]"
    )


def _compute_wm_context_supply_score(
    *,
    cfg: ProposalLearningConfig,
    forecast_context: Dict[str, Any],
    projected_signal: Dict[str, Any],
) -> float:
    pred_context_score = float(projected_signal.get("pred_context_score", 0.0))
    pred_gain_norm = float(projected_signal.get("pred_gain_norm", 0.0))
    pred_gain_sign_prob = float(projected_signal.get("pred_gain_sign_prob", 0.0))
    pred_projection_bad_prob = float(projected_signal.get("pred_projection_bad_prob", 1.0))
    pred_uncertainty = float(projected_signal.get("pred_uncertainty", 0.0))
    calibrated_projected = float(projected_signal.get("calibrated_projected", 0.0))
    wm_quality_penalty = float(forecast_context.get("wm_quality_penalty", 0.0))
    projection_recent = float(forecast_context.get("projection_recent", 0.0))
    projection_trend = float(forecast_context.get("projection_trend", 0.0))
    retained_evidence = float(forecast_context.get("retained_evidence", 0.0))
    retained_rounds = float(forecast_context.get("retained_rounds", 0.0))
    uncertainty_norm = float(
        np.clip(
            pred_uncertainty / max(float(cfg.wm_candidate_pred_uncertainty_ref), 1e-6),
            0.0,
            1.5,
        )
    )
    return float(
        np.clip(
            0.30 * float(np.clip(0.5 * (pred_context_score + 1.0), 0.0, 1.0))
            + 0.20 * float(np.clip(pred_gain_norm, 0.0, 1.0))
            + 0.18 * float(np.clip(pred_gain_sign_prob, 0.0, 1.0))
            + 0.12 * float(np.clip(calibrated_projected, 0.0, 1.0))
            + 0.08 * float(np.clip(projection_recent, 0.0, 1.0))
            + 0.06 * float(np.clip(projection_trend, -1.0, 1.0))
            + 0.06 * float(np.clip(retained_evidence, 0.0, 1.0))
            + 0.04 * float(np.clip(retained_rounds / 4.0, 0.0, 1.0))
            - 0.18 * float(np.clip(pred_projection_bad_prob, 0.0, 1.0))
            - 0.10 * uncertainty_norm
            - 0.08 * float(np.clip(wm_quality_penalty / 2.0, 0.0, 1.5)),
            0.0,
            1.0,
        )
    )


def _compute_v4_wm_context_signal_discrimination(
    *,
    cfg: ProposalLearningConfig,
    forecast_context: Dict[str, Any],
    projected_signal: Dict[str, Any],
) -> Dict[str, Any]:
    if not bool(cfg.v4_wm_context_signal_discrimination_probe_enabled):
        return {
            "applied": False,
            "wm_context_supply_score": _compute_wm_context_supply_score(
                cfg=cfg,
                forecast_context=forecast_context,
                projected_signal=projected_signal,
            ),
            "discrimination_score": 0.0,
            "raw_delta": 0.0,
            "calibrated_projected": float(projected_signal.get("calibrated_projected", 0.0)),
            "raw_projected": float(projected_signal.get("raw_projected", 0.0)),
            "components": {},
        }
    wm_context_supply_score = _compute_wm_context_supply_score(
        cfg=cfg,
        forecast_context=forecast_context,
        projected_signal=projected_signal,
    )
    pred_context_support = float(np.clip(0.5 * (float(projected_signal.get("pred_context_score", 0.0)) + 1.0), 0.0, 1.0))
    pred_gain_sign_prob = float(np.clip(float(projected_signal.get("pred_gain_sign_prob", 0.0)), 0.0, 1.0))
    projected_quality = float(np.clip(1.0 - float(projected_signal.get("pred_projection_bad_prob", 1.0)), 0.0, 1.0))
    calibrated_projected = float(np.clip(float(projected_signal.get("calibrated_projected", 0.0)), 0.0, 1.0))
    uncertainty_norm = float(
        np.clip(
            float(projected_signal.get("pred_uncertainty", 0.0)) / max(float(cfg.wm_candidate_pred_uncertainty_ref), 1e-6),
            0.0,
            1.5,
        )
    )
    projection_recent_quality = float(
        1.0 - np.clip(float(forecast_context.get("projection_recent", 0.0)), 0.0, 1.5) / 1.5
    )
    wm_penalty_norm = float(np.clip(float(forecast_context.get("wm_quality_penalty", 0.0)) / 2.0, 0.0, 1.0))
    discrimination_score = float(
        np.clip(
            0.38 * wm_context_supply_score
            + 0.18 * pred_gain_sign_prob
            + 0.16 * calibrated_projected
            + 0.14 * pred_context_support
            + 0.08 * projected_quality
            + 0.06 * projection_recent_quality
            - 0.08 * uncertainty_norm
            - 0.06 * wm_penalty_norm,
            0.0,
            1.0,
        )
    )
    centered = float(discrimination_score - float(cfg.v4_wm_context_signal_discrimination_center))
    raw_delta = float(
        np.clip(
            centered * float(cfg.v4_wm_context_signal_discrimination_weight),
            -0.12,
            0.12,
        )
    )
    adjusted_raw = float(projected_signal.get("raw_projected", 0.0)) + raw_delta
    adjusted_calibrated = _confidence_activation(
        adjusted_raw,
        str(cfg.wm_candidate_pred_activation),
        float(cfg.wm_candidate_pred_activation_scale),
        float(cfg.wm_candidate_pred_center),
    )
    return {
        "applied": True,
        "wm_context_supply_score": float(wm_context_supply_score),
        "discrimination_score": float(discrimination_score),
        "raw_delta": float(raw_delta),
        "raw_projected": float(adjusted_raw),
        "calibrated_projected": float(adjusted_calibrated),
        "components": {
            "wm_context_supply": float(wm_context_supply_score),
            "pred_context_support": float(pred_context_support),
            "pred_gain_sign_prob": float(pred_gain_sign_prob),
            "projected_quality": float(projected_quality),
            "projection_recent_quality": float(projection_recent_quality),
            "uncertainty_penalty": -float(uncertainty_norm),
            "wm_penalty": -float(wm_penalty_norm),
            "raw_delta": float(raw_delta),
        },
    }


def _compute_v4_wm_context_residual_signal_discrimination(
    *,
    cfg: ProposalLearningConfig,
    forecast_context: Dict[str, Any],
    projected_signal: Dict[str, Any],
) -> Dict[str, Any]:
    if not bool(cfg.v4_wm_context_residual_signal_probe_enabled):
        return {
            "applied": False,
            "wm_context_supply_score": _compute_wm_context_supply_score(
                cfg=cfg,
                forecast_context=forecast_context,
                projected_signal=projected_signal,
            ),
            "residual_score": 0.0,
            "raw_delta": 0.0,
            "calibrated_projected": float(projected_signal.get("calibrated_projected", 0.0)),
            "raw_projected": float(projected_signal.get("raw_projected", 0.0)),
            "components": {},
        }
    wm_context_supply_score = _compute_wm_context_supply_score(
        cfg=cfg,
        forecast_context=forecast_context,
        projected_signal=projected_signal,
    )
    pred_context_support = float(
        np.clip(0.5 * (float(projected_signal.get("pred_context_score", 0.0)) + 1.0), 0.0, 1.0)
    )
    projected_quality = float(
        np.clip(1.0 - float(projected_signal.get("pred_projection_bad_prob", 1.0)), 0.0, 1.0)
    )
    projection_recent_quality = float(
        1.0 - np.clip(float(forecast_context.get("projection_recent", 0.0)), 0.0, 1.5) / 1.5
    )
    baseline_overlap = float(
        np.clip(
            0.52 * float(np.clip(float(projected_signal.get("pred_gain_sign_prob", 0.0)), 0.0, 1.0))
            + 0.48 * float(np.clip(float(projected_signal.get("calibrated_projected", 0.0)), 0.0, 1.0)),
            0.0,
            1.0,
        )
    )
    uncertainty_norm = float(
        np.clip(
            float(projected_signal.get("pred_uncertainty", 0.0)) / max(float(cfg.wm_candidate_pred_uncertainty_ref), 1e-6),
            0.0,
            1.5,
        )
    )
    wm_penalty_norm = float(np.clip(float(forecast_context.get("wm_quality_penalty", 0.0)) / 2.0, 0.0, 1.0))
    wm_residual_core = float(np.clip(wm_context_supply_score - 0.42 * baseline_overlap, 0.0, 1.0))
    residual_score = float(
        np.clip(
            0.34 * wm_residual_core
            + 0.28 * pred_context_support
            + 0.22 * projected_quality
            + 0.16 * projection_recent_quality
            - 0.08 * uncertainty_norm
            - 0.06 * wm_penalty_norm,
            0.0,
            1.0,
        )
    )
    centered = float(residual_score - float(cfg.v4_wm_context_residual_signal_center))
    raw_delta = float(
        np.clip(
            centered * float(cfg.v4_wm_context_residual_signal_weight),
            -0.10,
            0.10,
        )
    )
    adjusted_raw = float(projected_signal.get("raw_projected", 0.0)) + raw_delta
    adjusted_calibrated = _confidence_activation(
        adjusted_raw,
        str(cfg.wm_candidate_pred_activation),
        float(cfg.wm_candidate_pred_activation_scale),
        float(cfg.wm_candidate_pred_center),
    )
    return {
        "applied": True,
        "wm_context_supply_score": float(wm_context_supply_score),
        "residual_score": float(residual_score),
        "raw_delta": float(raw_delta),
        "raw_projected": float(adjusted_raw),
        "calibrated_projected": float(adjusted_calibrated),
        "components": {
            "wm_context_supply": float(wm_context_supply_score),
            "wm_residual_core": float(wm_residual_core),
            "pred_context_support": float(pred_context_support),
            "projected_quality": float(projected_quality),
            "projection_recent_quality": float(projection_recent_quality),
            "baseline_overlap_penalty": -float(baseline_overlap),
            "uncertainty_penalty": -float(uncertainty_norm),
            "wm_penalty": -float(wm_penalty_norm),
            "raw_delta": float(raw_delta),
        },
    }


def _compute_v4_wm_baseline_hybrid_boundary(
    *,
    cfg: ProposalLearningConfig,
    forecast_context: Dict[str, Any],
    projected_signal: Dict[str, Any],
) -> Dict[str, Any]:
    if not bool(cfg.v4_wm_baseline_hybrid_boundary_probe_enabled):
        return {
            "applied": False,
            "wm_context_supply_score": _compute_wm_context_supply_score(
                cfg=cfg,
                forecast_context=forecast_context,
                projected_signal=projected_signal,
            ),
            "hybrid_score": 0.0,
            "contextual_remainder": 0.0,
            "boundary_gate": 0.0,
            "raw_delta": 0.0,
            "calibrated_projected": float(projected_signal.get("calibrated_projected", 0.0)),
            "raw_projected": float(projected_signal.get("raw_projected", 0.0)),
            "components": {},
        }
    wm_context_supply_score = _compute_wm_context_supply_score(
        cfg=cfg,
        forecast_context=forecast_context,
        projected_signal=projected_signal,
    )
    pred_context_support = float(
        np.clip(0.5 * (float(projected_signal.get("pred_context_score", 0.0)) + 1.0), 0.0, 1.0)
    )
    pred_gain_sign_prob = float(np.clip(float(projected_signal.get("pred_gain_sign_prob", 0.0)), 0.0, 1.0))
    calibrated_projected = float(np.clip(float(projected_signal.get("calibrated_projected", 0.0)), 0.0, 1.0))
    pred_projection_bad_prob = float(
        np.clip(float(projected_signal.get("pred_projection_bad_prob", 1.0)), 0.0, 1.0)
    )
    uncertainty_norm = float(
        np.clip(
            float(projected_signal.get("pred_uncertainty", 0.0))
            / max(float(cfg.wm_candidate_pred_uncertainty_ref), 1e-6),
            0.0,
            1.5,
        )
    )
    wm_penalty_norm = float(np.clip(float(forecast_context.get("wm_quality_penalty", 0.0)) / 2.0, 0.0, 1.0))
    projection_recent_quality = float(
        1.0 - np.clip(float(forecast_context.get("projection_recent", 0.0)), 0.0, 1.5) / 1.5
    )
    baseline_overlap = float(
        np.clip(
            0.55 * pred_gain_sign_prob
            + 0.45 * calibrated_projected,
            0.0,
            1.0,
        )
    )
    overlap_excess = float(np.clip(baseline_overlap - 0.58, 0.0, 1.0))
    contextual_remainder = float(
        np.clip(
            wm_context_supply_score - 0.18 * overlap_excess,
            0.0,
            1.0,
        )
    )
    context_core = float(
        np.clip(
            0.52 * pred_context_support
            + 0.34 * contextual_remainder
            + 0.14 * projection_recent_quality,
            0.0,
            1.0,
        )
    )
    boundary_gate = float(
        np.clip(
            1.0
            - 0.55 * pred_projection_bad_prob
            - 0.20 * float(np.clip(uncertainty_norm / 1.5, 0.0, 1.0))
            - 0.15 * wm_penalty_norm,
            0.0,
            1.0,
        )
    )
    hybrid_score = float(
        np.clip(
            context_core * (0.72 + 0.28 * boundary_gate),
            0.0,
            1.0,
        )
    )
    centered = float(hybrid_score - float(cfg.v4_wm_baseline_hybrid_boundary_center))
    raw_delta = float(
        np.clip(
            centered * float(cfg.v4_wm_baseline_hybrid_boundary_weight),
            -0.08,
            0.08,
        )
    )
    adjusted_raw = float(projected_signal.get("raw_projected", 0.0)) + raw_delta
    adjusted_calibrated = _confidence_activation(
        adjusted_raw,
        str(cfg.wm_candidate_pred_activation),
        float(cfg.wm_candidate_pred_activation_scale),
        float(cfg.wm_candidate_pred_center),
    )
    return {
        "applied": True,
        "wm_context_supply_score": float(wm_context_supply_score),
        "hybrid_score": float(hybrid_score),
        "contextual_remainder": float(contextual_remainder),
        "boundary_gate": float(boundary_gate),
        "raw_delta": float(raw_delta),
        "raw_projected": float(adjusted_raw),
        "calibrated_projected": float(adjusted_calibrated),
        "components": {
            "pred_context_support": float(pred_context_support),
            "contextual_remainder": float(contextual_remainder),
            "projection_recent_quality": float(projection_recent_quality),
            "boundary_gate": float(boundary_gate),
            "baseline_overlap_excess_penalty": -float(overlap_excess),
            "uncertainty_boundary_penalty": -float(uncertainty_norm),
            "wm_penalty": -float(wm_penalty_norm),
            "raw_delta": float(raw_delta),
        },
    }


def _sigmoid_gate(value: float, scale: float) -> float:
    scale = max(float(scale), 1e-6)
    normalized = float(np.clip(float(value) / scale, -8.0, 8.0))
    return float(1.0 / (1.0 + np.exp(-normalized)))


def _compute_v4_wm_hybrid_context_scoped_boundary(
    *,
    cfg: ProposalLearningConfig,
    forecast_context: Dict[str, Any],
    projected_signal: Dict[str, Any],
    hybrid_boundary: Dict[str, Any],
) -> Dict[str, Any]:
    if not bool(cfg.v4_wm_hybrid_context_scoped_probe_enabled):
        return {
            "applied": False,
            "scoped_score": 0.0,
            "scope_gate": 0.0,
            "scope_multiplier": 0.0,
            "scope_label": "inactive",
            "raw_delta": 0.0,
            "base_raw_delta": float(hybrid_boundary.get("raw_delta", 0.0)),
            "calibrated_projected": float(projected_signal.get("calibrated_projected", 0.0)),
            "raw_projected": float(projected_signal.get("raw_projected", 0.0)),
            "components": {},
        }
    if not bool(hybrid_boundary.get("applied", False)):
        return {
            "applied": False,
            "scoped_score": 0.0,
            "scope_gate": 0.0,
            "scope_multiplier": 0.0,
            "scope_label": "inactive",
            "raw_delta": 0.0,
            "base_raw_delta": 0.0,
            "calibrated_projected": float(projected_signal.get("calibrated_projected", 0.0)),
            "raw_projected": float(projected_signal.get("raw_projected", 0.0)),
            "components": {},
        }

    pred_context_score = float(projected_signal.get("pred_context_score", 0.0))
    pred_projection_bad_prob = float(
        np.clip(float(projected_signal.get("pred_projection_bad_prob", 1.0)), 0.0, 1.0)
    )
    projection_recent_quality = float(
        1.0 - np.clip(float(forecast_context.get("projection_recent", 0.0)), 0.0, 1.5) / 1.5
    )
    context_gate = _sigmoid_gate(
        pred_context_score - float(cfg.v4_wm_hybrid_context_scoped_context_cut),
        float(cfg.v4_wm_hybrid_context_scoped_context_scale),
    )
    low_risk_gate = _sigmoid_gate(
        float(cfg.v4_wm_hybrid_context_scoped_risk_cut) - pred_projection_bad_prob,
        float(cfg.v4_wm_hybrid_context_scoped_risk_scale),
    )
    scope_gate = float(np.clip(context_gate * low_risk_gate, 0.0, 1.0))
    floor = float(np.clip(float(cfg.v4_wm_hybrid_context_scoped_floor), 0.0, 0.95))
    peak_boost = float(np.clip(float(cfg.v4_wm_hybrid_context_scoped_peak_boost), 0.0, 0.25))

    scope_label = "mixed"
    if pred_context_score >= float(cfg.v4_wm_hybrid_context_scoped_context_cut) and pred_projection_bad_prob <= float(
        cfg.v4_wm_hybrid_context_scoped_risk_cut
    ):
        scope_label = "high_context_low_risk"
    elif pred_context_score < float(cfg.v4_wm_hybrid_context_scoped_context_cut) and pred_projection_bad_prob > float(
        cfg.v4_wm_hybrid_context_scoped_risk_cut
    ):
        scope_label = "low_context_high_risk"

    if scope_label == "high_context_low_risk":
        scope_multiplier = float(
            np.clip(
                1.0 + peak_boost * (0.40 + 0.60 * scope_gate),
                1.0,
                1.0 + peak_boost,
            )
        )
    elif scope_label == "low_context_high_risk":
        scope_multiplier = float(
            np.clip(
                floor + 0.18 * scope_gate,
                floor,
                max(floor + 0.18, 0.32),
            )
        )
    else:
        scope_multiplier = float(
            np.clip(
                0.55 + 0.22 * scope_gate + 0.04 * projection_recent_quality,
                0.50,
                0.85,
            )
        )

    base_raw_delta = float(hybrid_boundary.get("raw_delta", 0.0))
    raw_delta = float(np.clip(base_raw_delta * scope_multiplier, -0.08, 0.08))
    adjusted_raw = float(projected_signal.get("raw_projected", 0.0)) + raw_delta
    adjusted_calibrated = _confidence_activation(
        adjusted_raw,
        str(cfg.wm_candidate_pred_activation),
        float(cfg.wm_candidate_pred_activation_scale),
        float(cfg.wm_candidate_pred_center),
    )
    scoped_score = float(
        np.clip(
            float(hybrid_boundary.get("hybrid_score", 0.0))
            * (0.55 + 0.45 * scope_gate)
            * (0.92 + 0.08 * projection_recent_quality),
            0.0,
            1.0,
        )
    )
    return {
        "applied": True,
        "scoped_score": float(scoped_score),
        "scope_gate": float(scope_gate),
        "scope_multiplier": float(scope_multiplier),
        "scope_label": str(scope_label),
        "raw_delta": float(raw_delta),
        "base_raw_delta": float(base_raw_delta),
        "calibrated_projected": float(adjusted_calibrated),
        "raw_projected": float(adjusted_raw),
        "components": {
            "context_gate": float(context_gate),
            "low_risk_gate": float(low_risk_gate),
            "scope_gate": float(scope_gate),
            "scope_multiplier": float(scope_multiplier),
            "projection_recent_quality": float(projection_recent_quality),
            "base_raw_delta": float(base_raw_delta),
            "raw_delta": float(raw_delta),
        },
    }


def _compute_v4_wm_hybrid_context_stabilization(
    *,
    cfg: ProposalLearningConfig,
    forecast_context: Dict[str, Any],
    projected_signal: Dict[str, Any],
    hybrid_boundary: Dict[str, Any],
    context_scoped: Dict[str, Any],
) -> Dict[str, Any]:
    if not bool(cfg.v4_wm_hybrid_context_stabilization_probe_enabled):
        return {
            "applied": False,
            "stabilized_score": 0.0,
            "scope_gate": 0.0,
            "base_scope_multiplier": float(context_scoped.get("scope_multiplier", 0.0)),
            "stabilization_multiplier": 0.0,
            "final_scope_multiplier": 0.0,
            "scope_label": "inactive",
            "raw_delta": 0.0,
            "base_raw_delta": float(context_scoped.get("raw_delta", hybrid_boundary.get("raw_delta", 0.0))),
            "calibrated_projected": float(projected_signal.get("calibrated_projected", 0.0)),
            "raw_projected": float(projected_signal.get("raw_projected", 0.0)),
            "components": {},
        }
    if not bool(hybrid_boundary.get("applied", False)) or not bool(context_scoped.get("applied", False)):
        return {
            "applied": False,
            "stabilized_score": 0.0,
            "scope_gate": 0.0,
            "base_scope_multiplier": float(context_scoped.get("scope_multiplier", 0.0)),
            "stabilization_multiplier": 0.0,
            "final_scope_multiplier": 0.0,
            "scope_label": "inactive",
            "raw_delta": 0.0,
            "base_raw_delta": float(context_scoped.get("raw_delta", hybrid_boundary.get("raw_delta", 0.0))),
            "calibrated_projected": float(projected_signal.get("calibrated_projected", 0.0)),
            "raw_projected": float(projected_signal.get("raw_projected", 0.0)),
            "components": {},
        }

    pred_context_score = float(projected_signal.get("pred_context_score", 0.0))
    pred_projection_bad_prob = float(
        np.clip(float(projected_signal.get("pred_projection_bad_prob", 1.0)), 0.0, 1.0)
    )
    projection_recent_quality = float(
        1.0 - np.clip(float(forecast_context.get("projection_recent", 0.0)), 0.0, 1.5) / 1.5
    )
    contextual_remainder = float(np.clip(float(hybrid_boundary.get("contextual_remainder", 0.0)), 0.0, 1.0))
    boundary_gate = float(np.clip(float(hybrid_boundary.get("boundary_gate", 0.0)), 0.0, 1.0))
    scope_gate = float(np.clip(float(context_scoped.get("scope_gate", 0.0)), 0.0, 1.0))
    scoped_score = float(np.clip(float(context_scoped.get("scoped_score", 0.0)), 0.0, 1.0))
    base_scope_multiplier = float(np.clip(float(context_scoped.get("scope_multiplier", 0.0)), 0.0, 2.0))
    scope_label = str(context_scoped.get("scope_label", "mixed"))

    context_edge = _sigmoid_gate(
        pred_context_score - (float(cfg.v4_wm_hybrid_context_scoped_context_cut) - float(cfg.v4_wm_hybrid_context_stabilization_context_margin)),
        float(cfg.v4_wm_hybrid_context_stabilization_context_scale),
    )
    risk_edge = _sigmoid_gate(
        (float(cfg.v4_wm_hybrid_context_scoped_risk_cut) + float(cfg.v4_wm_hybrid_context_stabilization_risk_margin))
        - pred_projection_bad_prob,
        float(cfg.v4_wm_hybrid_context_stabilization_risk_scale),
    )
    stabilization_support = float(
        np.clip(
            0.35 * boundary_gate
            + 0.25 * contextual_remainder
            + 0.20 * projection_recent_quality
            + 0.10 * scope_gate,
            0.0,
            1.0,
        )
    )
    stabilization_support = float(
        np.clip(
            stabilization_support + 0.10 * scoped_score,
            0.0,
            1.0,
        )
    )
    weak_edge_support = float(
        np.clip(
            context_edge * risk_edge * stabilization_support * (0.50 + 0.50 * scoped_score),
            0.0,
            1.0,
        )
    )

    if scope_label == "high_context_low_risk":
        stabilization_multiplier = float(
            np.clip(
                1.0
                + float(cfg.v4_wm_hybrid_context_stabilization_strong_boost)
                * max(0.0, stabilization_support - 0.45),
                1.0,
                1.0 + float(cfg.v4_wm_hybrid_context_stabilization_strong_boost),
            )
        )
        final_scope_multiplier = float(
            np.clip(
                max(base_scope_multiplier, base_scope_multiplier * stabilization_multiplier),
                1.0,
                1.0 + float(cfg.v4_wm_hybrid_context_scoped_peak_boost) + 0.05,
            )
        )
    elif scope_label == "low_context_high_risk":
        stabilization_multiplier = float(
            np.clip(
                1.0 + float(cfg.v4_wm_hybrid_context_stabilization_weak_edge_boost) * weak_edge_support,
                1.0,
                1.0 + float(cfg.v4_wm_hybrid_context_stabilization_weak_edge_boost),
            )
        )
        final_scope_multiplier = float(
            np.clip(
                max(base_scope_multiplier, base_scope_multiplier * stabilization_multiplier),
                base_scope_multiplier,
                float(cfg.v4_wm_hybrid_context_stabilization_weak_cap),
            )
        )
    else:
        stabilization_multiplier = float(
            np.clip(
                1.0
                + float(cfg.v4_wm_hybrid_context_stabilization_mixed_boost)
                * stabilization_support
                * (0.45 + 0.55 * context_edge)
                * (0.60 + 0.40 * scoped_score),
                1.0,
                1.0 + float(cfg.v4_wm_hybrid_context_stabilization_mixed_boost),
            )
        )
        final_scope_multiplier = float(
            np.clip(
                max(base_scope_multiplier, base_scope_multiplier * stabilization_multiplier),
                base_scope_multiplier,
                0.90,
            )
        )

    base_raw_delta = float(hybrid_boundary.get("raw_delta", 0.0))
    raw_delta = float(np.clip(base_raw_delta * final_scope_multiplier, -0.08, 0.08))
    adjusted_raw = float(projected_signal.get("raw_projected", 0.0)) + raw_delta
    adjusted_calibrated = _confidence_activation(
        adjusted_raw,
        str(cfg.wm_candidate_pred_activation),
        float(cfg.wm_candidate_pred_activation_scale),
        float(cfg.wm_candidate_pred_center),
    )
    stabilized_score = float(
        np.clip(
            float(context_scoped.get("scoped_score", 0.0))
            * (0.94 + 0.04 * stabilization_support + 0.02 * scoped_score)
            * (final_scope_multiplier / max(base_scope_multiplier, 1e-6)),
            0.0,
            1.0,
        )
    )
    return {
        "applied": True,
        "stabilized_score": float(stabilized_score),
        "scope_gate": float(scope_gate),
        "base_scope_multiplier": float(base_scope_multiplier),
        "stabilization_multiplier": float(stabilization_multiplier),
        "final_scope_multiplier": float(final_scope_multiplier),
        "scope_label": str(scope_label),
        "raw_delta": float(raw_delta),
        "base_raw_delta": float(base_raw_delta),
        "calibrated_projected": float(adjusted_calibrated),
        "raw_projected": float(adjusted_raw),
        "components": {
            "context_edge": float(context_edge),
            "risk_edge": float(risk_edge),
            "stabilization_support": float(stabilization_support),
            "weak_edge_support": float(weak_edge_support),
            "base_scope_multiplier": float(base_scope_multiplier),
            "stabilization_multiplier": float(stabilization_multiplier),
            "final_scope_multiplier": float(final_scope_multiplier),
            "raw_delta": float(raw_delta),
        },
    }


def _build_wm_plan_context_trace_row(
    *,
    cfg: ProposalLearningConfig,
    round_index: int,
    agent_i: int,
    proposer_j: int,
    forecast_context: Dict[str, Any],
    projected_signal: Dict[str, Any],
    pre_gate_selection_score: float,
    pre_gate_selection_score_raw: float,
    shadow_priority: float,
    status: str,
) -> Dict[str, Any]:
    world_model_active = bool(cfg.use_world_model and cfg.wm_candidate_projection_enabled)
    planning_active = bool(cfg.use_planning)
    projected_available = bool(projected_signal.get("available", False))
    pred_context_score = float(projected_signal.get("pred_context_score", 0.0))
    pred_gain_norm = float(projected_signal.get("pred_gain_norm", 0.0))
    pred_gain_sign_prob = float(projected_signal.get("pred_gain_sign_prob", 0.0))
    pred_projection_bad_prob = float(projected_signal.get("pred_projection_bad_prob", 1.0))
    pred_uncertainty = float(projected_signal.get("pred_uncertainty", 0.0))
    calibrated_projected = float(projected_signal.get("calibrated_projected", 0.0))
    wm_quality_penalty = float(forecast_context.get("wm_quality_penalty", 0.0))
    projection_recent = float(forecast_context.get("projection_recent", 0.0))
    projection_trend = float(forecast_context.get("projection_trend", 0.0))
    retained_evidence = float(forecast_context.get("retained_evidence", 0.0))
    retained_rounds = float(forecast_context.get("retained_rounds", 0.0))
    plan_horizon_norm = float(np.clip(float(cfg.plan_horizon) / 8.0, 0.0, 1.0))
    plan_candidates_norm = float(np.clip(float(cfg.plan_candidates) / 32.0, 0.0, 1.0))
    uncertainty_norm = float(
        np.clip(
            pred_uncertainty / max(float(cfg.wm_candidate_pred_uncertainty_ref), 1e-6),
            0.0,
            1.5,
        )
    )
    wm_context_supply_score = _compute_wm_context_supply_score(
        cfg=cfg,
        forecast_context=forecast_context,
        projected_signal=projected_signal,
    )
    discrimination = dict(projected_signal.get("v4_wm_context_discrimination", {}))
    residual_signal = dict(projected_signal.get("v4_wm_context_residual_signal", {}))
    hybrid_boundary = dict(projected_signal.get("v4_wm_baseline_hybrid_boundary", {}))
    context_scoped = dict(projected_signal.get("v4_wm_hybrid_context_scoped", {}))
    stabilization = dict(projected_signal.get("v4_wm_hybrid_context_stabilization", {}))
    planning_handoff_score = float(
        np.clip(
            (0.55 * wm_context_supply_score + 0.20 * plan_horizon_norm + 0.15 * plan_candidates_norm + 0.10 * float(np.clip(calibrated_projected, 0.0, 1.0)))
            * (1.0 if planning_active else 0.0),
            0.0,
            1.0,
        )
    )
    return {
        "round": int(round_index),
        "agent": int(agent_i),
        "proposer": int(proposer_j),
        "candidate_id": f"A{int(agent_i)}<=P{int(proposer_j)}",
        "world_model_active": bool(world_model_active),
        "planning_active": bool(planning_active),
        "projected_available": bool(projected_available),
        "plan_horizon": int(cfg.plan_horizon),
        "plan_candidates": int(cfg.plan_candidates),
        "pred_context_score": float(pred_context_score),
        "pred_gain_norm": float(pred_gain_norm),
        "pred_gain_sign_prob": float(pred_gain_sign_prob),
        "pred_projection_bad_prob": float(pred_projection_bad_prob),
        "pred_uncertainty": float(pred_uncertainty),
        "calibrated_projected": float(calibrated_projected),
        "selection_score_pre_gate": float(pre_gate_selection_score),
        "selection_score_raw_pre_gate": float(pre_gate_selection_score_raw),
        "shadow_priority": float(shadow_priority),
        "status": str(status),
        "wm_context_supply_score": float(wm_context_supply_score),
        "planning_handoff_score": float(planning_handoff_score),
        "projection_recent": float(projection_recent),
        "projection_trend": float(projection_trend),
        "wm_quality_penalty": float(wm_quality_penalty),
        "retained_evidence": float(retained_evidence),
        "retained_rounds": float(retained_rounds),
        "v4_wm_discrimination_applied": bool(discrimination.get("applied", False)),
        "v4_wm_discrimination_score": float(discrimination.get("discrimination_score", 0.0)),
        "v4_wm_discrimination_delta": float(discrimination.get("raw_delta", 0.0)),
        "v4_wm_residual_signal_applied": bool(residual_signal.get("applied", False)),
        "v4_wm_residual_signal_score": float(residual_signal.get("residual_score", 0.0)),
        "v4_wm_residual_signal_delta": float(residual_signal.get("raw_delta", 0.0)),
        "v4_wm_hybrid_boundary_applied": bool(hybrid_boundary.get("applied", False)),
        "v4_wm_hybrid_boundary_score": float(hybrid_boundary.get("hybrid_score", 0.0)),
        "v4_wm_hybrid_boundary_delta": float(hybrid_boundary.get("raw_delta", 0.0)),
        "v4_wm_hybrid_contextual_remainder": float(hybrid_boundary.get("contextual_remainder", 0.0)),
        "v4_wm_hybrid_boundary_gate": float(hybrid_boundary.get("boundary_gate", 0.0)),
        "v4_wm_hybrid_context_scoped_applied": bool(context_scoped.get("applied", False)),
        "v4_wm_hybrid_context_scoped_score": float(context_scoped.get("scoped_score", 0.0)),
        "v4_wm_hybrid_context_scoped_delta": float(context_scoped.get("raw_delta", 0.0)),
        "v4_wm_hybrid_context_scope_gate": float(context_scoped.get("scope_gate", 0.0)),
        "v4_wm_hybrid_context_scope_multiplier": float(context_scoped.get("scope_multiplier", 0.0)),
        "v4_wm_hybrid_context_scope_label": str(context_scoped.get("scope_label", "inactive")),
        "v4_wm_hybrid_context_stabilization_applied": bool(stabilization.get("applied", False)),
        "v4_wm_hybrid_context_stabilization_score": float(stabilization.get("stabilized_score", 0.0)),
        "v4_wm_hybrid_context_stabilization_delta": float(stabilization.get("raw_delta", 0.0)),
        "v4_wm_hybrid_context_stabilization_multiplier": float(stabilization.get("stabilization_multiplier", 0.0)),
        "v4_wm_hybrid_context_final_scope_multiplier": float(stabilization.get("final_scope_multiplier", 0.0)),
    }


def _aggregate_wm_plan_context_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {
            "trace_visible": False,
            "row_count": 0,
            "projected_available_count": 0,
            "world_model_active_count": 0,
            "planning_active_count": 0,
            "joint_handoff_visible": False,
            "mean_wm_context_supply_score": 0.0,
            "mean_planning_handoff_score": 0.0,
            "mean_pred_context_score": 0.0,
            "mean_pred_uncertainty": 0.0,
            "mean_selection_score_pre_gate": 0.0,
            "mean_v4_wm_discrimination_score": 0.0,
            "mean_v4_wm_discrimination_delta": 0.0,
            "mean_v4_wm_residual_signal_score": 0.0,
            "mean_v4_wm_residual_signal_delta": 0.0,
            "mean_v4_wm_hybrid_boundary_score": 0.0,
            "mean_v4_wm_hybrid_boundary_delta": 0.0,
            "mean_v4_wm_hybrid_contextual_remainder": 0.0,
            "mean_v4_wm_hybrid_boundary_gate": 0.0,
            "mean_v4_wm_hybrid_context_scoped_score": 0.0,
            "mean_v4_wm_hybrid_context_scoped_delta": 0.0,
            "mean_v4_wm_hybrid_context_scope_gate": 0.0,
            "mean_v4_wm_hybrid_context_scope_multiplier": 0.0,
            "mean_v4_wm_hybrid_context_stabilization_score": 0.0,
            "mean_v4_wm_hybrid_context_stabilization_delta": 0.0,
            "mean_v4_wm_hybrid_context_stabilization_multiplier": 0.0,
            "mean_v4_wm_hybrid_context_final_scope_multiplier": 0.0,
            "status_counts": {},
        }
    wm_scores = [float(row.get("wm_context_supply_score", 0.0)) for row in rows]
    handoff_scores = [float(row.get("planning_handoff_score", 0.0)) for row in rows]
    pred_context = [float(row.get("pred_context_score", 0.0)) for row in rows]
    pred_uncertainty = [float(row.get("pred_uncertainty", 0.0)) for row in rows]
    selection_scores = [float(row.get("selection_score_pre_gate", 0.0)) for row in rows]
    discrimination_scores = [float(row.get("v4_wm_discrimination_score", 0.0)) for row in rows]
    discrimination_deltas = [float(row.get("v4_wm_discrimination_delta", 0.0)) for row in rows]
    residual_scores = [float(row.get("v4_wm_residual_signal_score", 0.0)) for row in rows]
    residual_deltas = [float(row.get("v4_wm_residual_signal_delta", 0.0)) for row in rows]
    hybrid_scores = [float(row.get("v4_wm_hybrid_boundary_score", 0.0)) for row in rows]
    hybrid_deltas = [float(row.get("v4_wm_hybrid_boundary_delta", 0.0)) for row in rows]
    hybrid_remainders = [float(row.get("v4_wm_hybrid_contextual_remainder", 0.0)) for row in rows]
    hybrid_gates = [float(row.get("v4_wm_hybrid_boundary_gate", 0.0)) for row in rows]
    scoped_scores = [float(row.get("v4_wm_hybrid_context_scoped_score", 0.0)) for row in rows]
    scoped_deltas = [float(row.get("v4_wm_hybrid_context_scoped_delta", 0.0)) for row in rows]
    scoped_gates = [float(row.get("v4_wm_hybrid_context_scope_gate", 0.0)) for row in rows]
    scoped_multipliers = [float(row.get("v4_wm_hybrid_context_scope_multiplier", 0.0)) for row in rows]
    stabilization_scores = [float(row.get("v4_wm_hybrid_context_stabilization_score", 0.0)) for row in rows]
    stabilization_deltas = [float(row.get("v4_wm_hybrid_context_stabilization_delta", 0.0)) for row in rows]
    stabilization_multipliers = [
        float(row.get("v4_wm_hybrid_context_stabilization_multiplier", 0.0)) for row in rows
    ]
    final_scope_multipliers = [
        float(row.get("v4_wm_hybrid_context_final_scope_multiplier", 0.0)) for row in rows
    ]
    status_counts: Counter[str] = Counter(str(row.get("status", "unknown")) for row in rows)
    return {
        "trace_visible": True,
        "row_count": int(len(rows)),
        "projected_available_count": int(sum(1 for row in rows if bool(row.get("projected_available", False)))),
        "world_model_active_count": int(sum(1 for row in rows if bool(row.get("world_model_active", False)))),
        "planning_active_count": int(sum(1 for row in rows if bool(row.get("planning_active", False)))),
        "joint_handoff_visible": bool(
            any(
                bool(row.get("world_model_active", False))
                and bool(row.get("planning_active", False))
                and bool(row.get("projected_available", False))
                for row in rows
            )
        ),
        "mean_wm_context_supply_score": _safe_mean_arr(wm_scores, default=0.0),
        "mean_planning_handoff_score": _safe_mean_arr(handoff_scores, default=0.0),
        "mean_pred_context_score": _safe_mean_arr(pred_context, default=0.0),
        "mean_pred_uncertainty": _safe_mean_arr(pred_uncertainty, default=0.0),
        "mean_selection_score_pre_gate": _safe_mean_arr(selection_scores, default=0.0),
        "mean_v4_wm_discrimination_score": _safe_mean_arr(discrimination_scores, default=0.0),
        "mean_v4_wm_discrimination_delta": _safe_mean_arr(discrimination_deltas, default=0.0),
        "mean_v4_wm_residual_signal_score": _safe_mean_arr(residual_scores, default=0.0),
        "mean_v4_wm_residual_signal_delta": _safe_mean_arr(residual_deltas, default=0.0),
        "mean_v4_wm_hybrid_boundary_score": _safe_mean_arr(hybrid_scores, default=0.0),
        "mean_v4_wm_hybrid_boundary_delta": _safe_mean_arr(hybrid_deltas, default=0.0),
        "mean_v4_wm_hybrid_contextual_remainder": _safe_mean_arr(hybrid_remainders, default=0.0),
        "mean_v4_wm_hybrid_boundary_gate": _safe_mean_arr(hybrid_gates, default=0.0),
        "mean_v4_wm_hybrid_context_scoped_score": _safe_mean_arr(scoped_scores, default=0.0),
        "mean_v4_wm_hybrid_context_scoped_delta": _safe_mean_arr(scoped_deltas, default=0.0),
        "mean_v4_wm_hybrid_context_scope_gate": _safe_mean_arr(scoped_gates, default=0.0),
        "mean_v4_wm_hybrid_context_scope_multiplier": _safe_mean_arr(scoped_multipliers, default=0.0),
        "mean_v4_wm_hybrid_context_stabilization_score": _safe_mean_arr(stabilization_scores, default=0.0),
        "mean_v4_wm_hybrid_context_stabilization_delta": _safe_mean_arr(stabilization_deltas, default=0.0),
        "mean_v4_wm_hybrid_context_stabilization_multiplier": _safe_mean_arr(
            stabilization_multipliers,
            default=0.0,
        ),
        "mean_v4_wm_hybrid_context_final_scope_multiplier": _safe_mean_arr(
            final_scope_multipliers,
            default=0.0,
        ),
        "status_counts": dict(status_counts),
    }


def _aggregate_round_projection_forecast(adopted: List[Dict[str, Any]]) -> Dict[str, float]:
    projected = [a for a in adopted if np.isfinite(float(a.get("pred_gain_sign_prob", float("nan"))))]
    if not projected:
        return {
            "pred_gain_mean": float("nan"),
            "pred_gain_norm_mean": float("nan"),
            "pred_gain_sign_prob": float("nan"),
            "pred_gain_bad_prob": float("nan"),
            "pred_goal_bad_prob": float("nan"),
            "pred_projection_error_mean": float("nan"),
            "pred_projection_peak_mean": float("nan"),
            "pred_projection_delta_mean": float("nan"),
            "pred_projection_explosion_prob": float("nan"),
            "pred_projection_bad_prob": float("nan"),
            "pred_instability_mean": float("nan"),
            "pred_rollback_risk_mean": float("nan"),
            "pred_uncertainty_mean": float("nan"),
            "pred_context_score_mean": float("nan"),
            "pred_rollback_union": float("nan"),
        }
    weights = np.asarray([max(0.05, float(a.get("scale", 1.0))) for a in projected], dtype=np.float64)
    weights = weights / max(float(np.sum(weights)), 1e-6)

    def wmean(key: str, default: float = 0.0) -> float:
        values = np.asarray([float(a.get(key, default)) for a in projected], dtype=np.float64)
        mask = np.isfinite(values)
        if not np.any(mask):
            return float(default)
        w = weights[mask]
        w = w / max(float(np.sum(w)), 1e-6)
        return float(np.sum(values[mask] * w))

    def vmax(key: str, default: float = 0.0) -> float:
        values = np.asarray([float(a.get(key, default)) for a in projected], dtype=np.float64)
        values = values[np.isfinite(values)]
        if values.size == 0:
            return float(default)
        return float(np.max(values))

    pred_gain_norm_mean = wmean("pred_gain_norm", default=0.0)

    pred_gain_sign_prob = _sigmoid_prob(pred_gain_norm_mean, scale=2.5, center=0.0)
    pred_gain_bad_prob = wmean("pred_gain_bad_prob", default=_gain_bad_prob(pred_gain_norm_mean, pred_gain_sign_prob))
    pred_goal_bad_prob = wmean("pred_goal_bad_prob", default=0.0)
    pred_rollback_risk_mean = wmean("pred_rollback_risk", default=1.0)
    pred_rollback_risk_max = vmax("pred_rollback_risk", default=1.0)
    pred_projection_explosion_prob = wmean("pred_projection_explosion_prob", default=1.0)
    pred_projection_bad_prob = wmean("pred_projection_bad_prob", default=pred_projection_explosion_prob)
    pred_rollback_union = _probabilistic_union(pred_projection_bad_prob, pred_gain_bad_prob, pred_goal_bad_prob)
    # Derived rollback union is more trustworthy than the direct rollback head in current v3 audits.
    pred_rollback_risk_blend = float(pred_rollback_union)

    return {
        "pred_gain_mean": wmean("pred_post_gain", default=0.0),
        "pred_gain_norm_mean": pred_gain_norm_mean,
        "pred_gain_sign_prob": pred_gain_sign_prob,
        "pred_gain_bad_prob": pred_gain_bad_prob,
        "pred_goal_bad_prob": pred_goal_bad_prob,
        "pred_projection_error_mean": wmean("pred_projection_error", default=0.0),
        "pred_projection_peak_mean": wmean("pred_projection_peak", default=0.0),
        "pred_projection_delta_mean": wmean("pred_projection_delta", default=0.0),
        "pred_projection_explosion_prob": pred_projection_explosion_prob,
        "pred_projection_bad_prob": pred_projection_bad_prob,
        "pred_instability_mean": wmean("pred_instability", default=0.0),
        "pred_rollback_risk_mean": pred_rollback_risk_mean,
        "pred_rollback_risk_max": pred_rollback_risk_max,
        "pred_rollback_risk_blend": pred_rollback_risk_blend,
        "pred_uncertainty_mean": wmean("pred_uncertainty", default=0.0),
        "pred_context_score_mean": wmean("pred_context_score", default=0.0),
        "pred_rollback_union": pred_rollback_union,
    }


def _normalize_gain_target(value: float, history: List[float], default_ref: float = 25.0) -> float:
    recent = np.asarray(history[-8:], dtype=np.float64) if history else np.zeros((0,), dtype=np.float64)
    scale = max(float(default_ref), _safe_mean_arr(np.abs(recent), default=0.0), float(np.std(recent)) if recent.size > 0 else 0.0, 1e-6)
    return _norm_tanh(value, scale)


RUNTIME_MARKER = "NOVALI_V3_PROJECTION_SAFETY_POLICY_ACTIVE"


def _targeted_live_projection_bad_override_max(cfg: ProposalLearningConfig) -> float:
    base_cap = float(cfg.wm_candidate_pred_projection_bad_max_provisional)
    margin = max(0.0, float(getattr(cfg, "live_policy_projection_margin_provisional", 0.0)))
    strict_cap = float(getattr(cfg, "live_policy_targeted_projection_strict_max", 0.48))
    return max(0.0, min(strict_cap, base_cap - margin))


def _evaluate_live_policy_targeted_override(
    *,
    cfg: ProposalLearningConfig,
    projected_available: bool,
    baseline_projection_ok_provisional: bool,
    coherence_cal: float,
    gain_cal: float,
    confidence: Dict[str, Any],
    gain_signal: Dict[str, Any],
    pred_projection_bad_prob: float,
    pred_gain_sign_prob: float,
    pred_gain_bad_prob: float,
    projected_score: float,
    moving_average: float,
    persistence_streak: int,
    retained_evidence: float,
    rollback_rate: float,
    instability: float,
) -> Dict[str, Any]:
    variant_name = str(getattr(cfg, "live_policy_variant", "baseline"))
    if variant_name != "targeted_gain_goal_proj_margin_01":
        return {"apply": False, "reason": "variant_inactive"}
    if not projected_available:
        return {"apply": False, "reason": "projection_unavailable"}
    if not baseline_projection_ok_provisional:
        return {"apply": False, "reason": "baseline_projection_block"}

    projection_max = _targeted_live_projection_bad_override_max(cfg)
    conf_threshold = max(
        0.0,
        float(confidence["provisional_threshold"]) - float(getattr(cfg, "live_policy_targeted_conf_margin", 0.14)),
    )
    gain_threshold = max(
        0.0,
        float(gain_signal["provisional_threshold"]) - float(getattr(cfg, "live_policy_targeted_gain_margin", 0.14)),
    )
    safe_projection = bool(pred_projection_bad_prob <= projection_max)
    conf_ok = bool(coherence_cal >= conf_threshold)
    gain_ok = bool(gain_cal >= gain_threshold)
    projected_ok = bool(
        pred_gain_sign_prob >= float(getattr(cfg, "live_policy_targeted_min_pred_gain_sign_prob", 0.20))
        and pred_gain_bad_prob <= float(getattr(cfg, "live_policy_targeted_max_pred_gain_bad_prob", 0.62))
        and projected_score >= float(getattr(cfg, "live_policy_targeted_min_projected_score", 0.32))
    )
    persistence_ok = bool(
        int(persistence_streak) <= int(getattr(cfg, "live_policy_targeted_max_persistence_streak", 0))
        and float(retained_evidence) <= float(getattr(cfg, "live_policy_targeted_max_retained_evidence", 0.05))
        and float(moving_average) <= float(getattr(cfg, "live_policy_targeted_max_moving_average", 0.05))
    )
    recovery_ok = bool(
        float(rollback_rate) <= float(getattr(cfg, "live_policy_targeted_max_rollback_rate", 0.10))
        and float(instability) <= float(getattr(cfg, "live_policy_targeted_max_instability", 0.25))
    )
    apply = bool(safe_projection and conf_ok and gain_ok and projected_ok and persistence_ok and recovery_ok)
    if apply:
        reason = "safe_provisional_override"
    elif not persistence_ok:
        reason = "persistence_guard"
    elif not recovery_ok:
        reason = "recovery_guard"
    elif not safe_projection:
        reason = "tight_projection_guard"
    elif not projected_ok:
        reason = "projected_quality_guard"
    elif not conf_ok:
        reason = "conf_margin_guard"
    elif not gain_ok:
        reason = "gain_margin_guard"
    else:
        reason = "remain_reject"
    return {
        "apply": apply,
        "reason": str(reason),
        "projection_max": float(projection_max),
        "conf_threshold": float(conf_threshold),
        "gain_threshold": float(gain_threshold),
        "safe_projection": bool(safe_projection),
        "conf_ok": bool(conf_ok),
        "gain_ok": bool(gain_ok),
        "projected_ok": bool(projected_ok),
        "persistence_ok": bool(persistence_ok),
        "recovery_ok": bool(recovery_ok),
    }


def _rollback_cause_label(gain_bad: bool, goal_bad: bool, projection_bad: bool = False) -> str:
    parts: List[str] = []
    if gain_bad:
        parts.append("gain")
    if goal_bad:
        parts.append("goal")
    if projection_bad:
        parts.append("projection")
    if parts:
        return "+".join(parts)
    return "none"


def _rollback_blend(pred_projection_bad_prob: float, pred_gain_bad_prob: float, pred_goal_bad_prob: float) -> float:
    return _probabilistic_union(pred_projection_bad_prob, pred_gain_bad_prob, pred_goal_bad_prob)


def _probabilistic_union(*probs: float) -> float:
    union_keep = 1.0
    for prob in probs:
        p = float(np.clip(float(prob), 0.0, 1.0))
        union_keep *= (1.0 - p)
    return float(np.clip(1.0 - union_keep, 0.0, 1.0))


def _gain_bad_prob(pred_gain_norm: float, pred_gain_sign_prob: float) -> float:
    norm_bad = float(np.clip(0.5 * (1.0 - float(pred_gain_norm)), 0.0, 1.0))
    sign_bad = float(np.clip(1.0 - float(pred_gain_sign_prob), 0.0, 1.0))
    return float(np.clip(0.55 * sign_bad + 0.45 * norm_bad, 0.0, 1.0))


def _goal_bad_prob(goal_pressure: float) -> float:
    return float(np.clip(float(goal_pressure), 0.0, 1.0))


def _format_rollback_audit_rows(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "none"
    return "; ".join(
        f"{row['candidate_id']}[{row['status']}] p_proj_bad={row.get('pred_projection_bad', float('nan')):.3f} "
        f"p_union={row.get('pred_rollback_union', float('nan')):.3f} risk_diag={row['pred_risk']:.3f} "
        f"realized={int(row['realized_rollback'])} cause={row['rollback_cause']}"
        for row in rows
    )


def _safe_binary_auc(scores: Any, labels: Any, default: float = float("nan")) -> float:
    try:
        s = np.asarray(scores, dtype=np.float64).reshape(-1)
        y = np.asarray(labels, dtype=np.float64).reshape(-1)
        n = min(s.size, y.size)
        if n < 2:
            return float(default)
        s = s[:n]
        y = y[:n]
        mask = np.isfinite(s) & np.isfinite(y)
        if np.sum(mask) < 2:
            return float(default)
        s = s[mask]
        y = y[mask]
        pos = s[y > 0.5]
        neg = s[y <= 0.5]
        if pos.size == 0 or neg.size == 0:
            return float(default)
        wins = 0.0
        total = float(pos.size * neg.size)
        for p in pos:
            wins += float(np.sum(p > neg))
            wins += 0.5 * float(np.sum(p == neg))
        return float(wins / max(total, 1e-6))
    except Exception:
        return float(default)


def _top_risk_hit_rate(scores: Any, labels: Any, top_frac: float = 0.33, default: float = float("nan")) -> float:
    try:
        s = np.asarray(scores, dtype=np.float64).reshape(-1)
        y = np.asarray(labels, dtype=np.float64).reshape(-1)
        n = min(s.size, y.size)
        if n <= 0:
            return float(default)
        s = s[:n]
        y = y[:n]
        mask = np.isfinite(s) & np.isfinite(y)
        if np.sum(mask) == 0:
            return float(default)
        s = s[mask]
        y = y[mask]
        k = max(1, int(np.ceil(float(top_frac) * float(s.size))))
        idx = np.argsort(-s)[:k]
        return float(np.mean(y[idx]))
    except Exception:
        return float(default)


def _selected_set_mode(selected: List[Dict[str, Any]]) -> str:
    if not selected:
        return "none"
    statuses = {str(item.get("status", "blocked")) for item in selected}
    if statuses == {"provisional"}:
        return "provisional-only"
    if statuses == {"full"}:
        return "full-only"
    if statuses == {"shadow"}:
        return "shadow-only"
    return "mixed"


def _selection_weighted_mean(selected: List[Dict[str, Any]], key: str, weight_key: str = "selection_score", default: float = float("nan")) -> float:
    try:
        values = np.asarray([float(item.get(key, float("nan"))) for item in selected], dtype=np.float64)
        weights = np.asarray([float(item.get(weight_key, 0.0)) for item in selected], dtype=np.float64)
        mask = np.isfinite(values) & np.isfinite(weights)
        if not np.any(mask):
            return float(default)
        values = values[mask]
        weights = weights[mask]
        weights = weights - float(np.min(weights)) + 1e-6
        total = float(np.sum(weights))
        if total <= 1e-6:
            return float(np.mean(values))
        return float(np.sum(values * weights) / total)
    except Exception:
        return float(default)


def _build_round_rollback_audit_row(
    *,
    round_idx: int,
    selected: List[Dict[str, Any]],
    runtime_rollback_triggered: bool,
    rollback_gain_bad: bool,
    rollback_goal_bad: bool,
    rollback_projection_bad: bool,
    rollback_cause: str,
    realized_gain: float,
    realized_goal_delta: float,
    realized_projection_error: float,
    gain_threshold: float,
    goal_threshold: float,
    projection_threshold: float,
    horizon_steps: int,
) -> Dict[str, Any]:
    selected_count = int(len(selected))
    pred_risk_values = [float(item.get("pred_rollback_risk", float("nan"))) for item in selected]
    pred_gain_bad_values = [float(item.get("pred_gain_bad_prob", float("nan"))) for item in selected]
    pred_goal_bad_values = [float(item.get("pred_goal_bad_prob", float("nan"))) for item in selected]
    pred_proj_risk_values = [float(item.get("pred_projection_explosion_prob", float("nan"))) for item in selected]
    pred_proj_bad_values = [float(item.get("pred_projection_bad_prob", float("nan"))) for item in selected]
    pred_gain_norm_values = [float(item.get("pred_gain_norm", float("nan"))) for item in selected]
    pred_gain_sign_values = [float(item.get("pred_gain_sign_prob", float("nan"))) for item in selected]

    risk_max = float(np.nanmax(np.asarray(pred_risk_values, dtype=np.float64))) if selected_count > 0 else float("nan")
    risk_mean = _safe_mean_arr(pred_risk_values, default=float("nan"))
    risk_sel_weighted_mean = _selection_weighted_mean(selected, "pred_rollback_risk", default=float("nan"))
    gain_norm_mean = _safe_mean_arr(pred_gain_norm_values, default=float("nan"))
    gain_sign_prob_mean = _safe_mean_arr(pred_gain_sign_values, default=float("nan"))
    gain_bad_mean = _safe_mean_arr(pred_gain_bad_values, default=float("nan"))
    gain_bad_sel_weighted_mean = _selection_weighted_mean(selected, "pred_gain_bad_prob", default=float("nan"))
    gain_bad_score = float(
        np.clip(
            0.60 * float(gain_bad_mean if np.isfinite(gain_bad_mean) else 0.0)
            + 0.40 * float(gain_bad_sel_weighted_mean if np.isfinite(gain_bad_sel_weighted_mean) else 0.0),
            0.0,
            1.0,
        )
    )
    goal_bad_mean = _safe_mean_arr(pred_goal_bad_values, default=float("nan"))
    goal_bad_sel_weighted_mean = _selection_weighted_mean(selected, "pred_goal_bad_prob", default=float("nan"))
    goal_bad_score = float(
        np.clip(
            0.60 * float(goal_bad_mean if np.isfinite(goal_bad_mean) else 0.0)
            + 0.40 * float(goal_bad_sel_weighted_mean if np.isfinite(goal_bad_sel_weighted_mean) else 0.0),
            0.0,
            1.0,
        )
    )
    proj_risk_max = float(np.nanmax(np.asarray(pred_proj_risk_values, dtype=np.float64))) if selected_count > 0 else float("nan")
    proj_risk_mean = _safe_mean_arr(pred_proj_risk_values, default=float("nan"))
    proj_risk_sel_weighted_mean = _selection_weighted_mean(selected, "pred_projection_explosion_prob", default=float("nan"))
    proj_bad_mean = _safe_mean_arr(pred_proj_bad_values, default=float("nan"))
    proj_bad_sel_weighted_mean = _selection_weighted_mean(selected, "pred_projection_bad_prob", default=float("nan"))
    proj_bad_score = float(
        np.clip(
            0.30 * float(proj_risk_max if np.isfinite(proj_risk_max) else 0.0)
            + 0.20 * float(proj_risk_mean if np.isfinite(proj_risk_mean) else 0.0)
            + 0.20 * float(proj_risk_sel_weighted_mean if np.isfinite(proj_risk_sel_weighted_mean) else 0.0)
            + 0.15 * float(proj_bad_mean if np.isfinite(proj_bad_mean) else 0.0)
            + 0.15 * float(proj_bad_sel_weighted_mean if np.isfinite(proj_bad_sel_weighted_mean) else 0.0),
            0.0,
            1.0,
        )
    )
    rollback_union = _probabilistic_union(proj_bad_score, gain_bad_score, goal_bad_score)
    risk_blend = float(
        np.clip(
            0.25 * float(risk_max if np.isfinite(risk_max) else 0.0)
            + 0.20 * float(risk_mean if np.isfinite(risk_mean) else 0.0)
            + 0.15 * float(risk_sel_weighted_mean if np.isfinite(risk_sel_weighted_mean) else 0.0)
            + 0.20 * float(proj_risk_max if np.isfinite(proj_risk_max) else 0.0)
            + 0.10 * float(proj_risk_mean if np.isfinite(proj_risk_mean) else 0.0)
            + 0.10 * (1.0 - float(gain_sign_prob_mean if np.isfinite(gain_sign_prob_mean) else 0.5)),
            0.0,
            1.0,
        )
    )
    derived_rollback = bool(rollback_gain_bad or rollback_goal_bad or rollback_projection_bad)
    gain_margin = float(realized_gain - gain_threshold)
    goal_margin = float(goal_threshold - realized_goal_delta)
    projection_margin = float(projection_threshold - realized_projection_error)

    return {
        "round": int(round_idx),
        "selected_candidate_count": selected_count,
        "selected_pred_risk_max": float(risk_max),
        "selected_pred_risk_mean": float(risk_mean),
        "selected_pred_risk_sel_weighted_mean": float(risk_sel_weighted_mean),
        "selected_pred_risk_blend": float(risk_blend),
        "selected_pred_gain_norm_mean": float(gain_norm_mean),
        "selected_pred_gain_sign_prob_mean": float(gain_sign_prob_mean),
        "selected_pred_gain_bad_score": float(gain_bad_score),
        "selected_pred_goal_bad_score": float(goal_bad_score),
        "selected_pred_projection_explosion_prob_max": float(proj_risk_max),
        "selected_pred_projection_explosion_prob_mean": float(proj_risk_mean),
        "selected_pred_projection_explosion_prob_sel_weighted_mean": float(proj_risk_sel_weighted_mean),
        "selected_pred_projection_bad_score": float(proj_bad_score),
        "selected_p_gain_bad": float(gain_bad_score),
        "selected_p_goal_bad": float(goal_bad_score),
        "selected_p_projection_bad": float(proj_bad_score),
        "selected_p_rollback_union": float(rollback_union),
        "realized_runtime_rollback": 1.0 if runtime_rollback_triggered else 0.0,
        "realized_rollback": 1.0 if derived_rollback else 0.0,
        "realized_gain_bad": 1.0 if rollback_gain_bad else 0.0,
        "realized_goal_bad": 1.0 if rollback_goal_bad else 0.0,
        "realized_projection_bad": 1.0 if rollback_projection_bad else 0.0,
        "gain_margin": float(gain_margin),
        "goal_margin": float(goal_margin),
        "projection_margin": float(projection_margin),
        "cause_label": str(rollback_cause),
        "selected_set_mode": _selected_set_mode(selected),
        "label_scope": "round_selected_set",
        "label_horizon_steps": int(horizon_steps),
    }


def _best_metric_entry(metric_values: Dict[str, float]) -> Tuple[str, float]:
    finite = [(key, float(val)) for key, val in metric_values.items() if np.isfinite(float(val))]
    if not finite:
        return "none", float("nan")
    positive = [item for item in finite if item[1] > 0.0]
    if positive:
        return max(positive, key=lambda item: item[1])
    return max(finite, key=lambda item: item[1])


def _compute_round_rollback_metrics(round_rows: List[Dict[str, Any]], min_rows_for_recommendation: int = 20) -> Dict[str, Any]:
    if not round_rows:
        return {"round_rows": 0}
    selected_rows = [row for row in round_rows if int(row.get("selected_candidate_count", 0)) > 0]
    if not selected_rows:
        return {
            "round_rows": int(len(round_rows)),
            "selected_round_rows": 0,
            "audit_min_rows_for_recommendation": int(min_rows_for_recommendation),
            "audit_rows_sufficient": False,
            "best_rollback_aggregation": "none",
            "best_risk_aggregation": "none",
            "best_gain_bad_aggregation": "none",
            "best_goal_bad_aggregation": "none",
            "best_projection_bad_aggregation": "none",
            "best_rollback_corr": float("nan"),
            "best_risk_corr": float("nan"),
            "best_gain_bad_corr": float("nan"),
            "best_goal_bad_corr": float("nan"),
            "best_projection_bad_corr": float("nan"),
            "easier_target": "no_selected_rows",
            "easier_target_corr": float("nan"),
            "policy_primary_target": "defer",
            "rollback_label_recommendation": "audit_rows_insufficient",
            "rollback_cause_counts": {},
        }

    targets = {
        "realized_rollback": np.asarray([float(row.get("realized_rollback", 0.0)) for row in selected_rows], dtype=np.float64),
        "realized_runtime_rollback": np.asarray([float(row.get("realized_runtime_rollback", 0.0)) for row in selected_rows], dtype=np.float64),
        "realized_gain_bad": np.asarray([float(row.get("realized_gain_bad", 0.0)) for row in selected_rows], dtype=np.float64),
        "realized_goal_bad": np.asarray([float(row.get("realized_goal_bad", 0.0)) for row in selected_rows], dtype=np.float64),
        "realized_projection_bad": np.asarray([float(row.get("realized_projection_bad", 0.0)) for row in selected_rows], dtype=np.float64),
    }
    score_features = {
        "selected_pred_risk_max": np.asarray([float(row.get("selected_pred_risk_max", float("nan"))) for row in selected_rows], dtype=np.float64),
        "selected_pred_risk_mean": np.asarray([float(row.get("selected_pred_risk_mean", float("nan"))) for row in selected_rows], dtype=np.float64),
        "selected_pred_risk_sel_weighted_mean": np.asarray([float(row.get("selected_pred_risk_sel_weighted_mean", float("nan"))) for row in selected_rows], dtype=np.float64),
        "selected_pred_risk_blend": np.asarray([float(row.get("selected_pred_risk_blend", float("nan"))) for row in selected_rows], dtype=np.float64),
        "selected_pred_gain_bad_score": np.asarray([float(row.get("selected_pred_gain_bad_score", float("nan"))) for row in selected_rows], dtype=np.float64),
        "selected_pred_goal_bad_score": np.asarray([float(row.get("selected_pred_goal_bad_score", float("nan"))) for row in selected_rows], dtype=np.float64),
        "selected_pred_projection_bad_score": np.asarray([float(row.get("selected_pred_projection_bad_score", float("nan"))) for row in selected_rows], dtype=np.float64),
        "selected_pred_projection_explosion_prob_max": np.asarray([float(row.get("selected_pred_projection_explosion_prob_max", float("nan"))) for row in selected_rows], dtype=np.float64),
        "selected_pred_projection_explosion_prob_mean": np.asarray([float(row.get("selected_pred_projection_explosion_prob_mean", float("nan"))) for row in selected_rows], dtype=np.float64),
        "selected_p_gain_bad": np.asarray([float(row.get("selected_p_gain_bad", float("nan"))) for row in selected_rows], dtype=np.float64),
        "selected_p_goal_bad": np.asarray([float(row.get("selected_p_goal_bad", float("nan"))) for row in selected_rows], dtype=np.float64),
        "selected_p_projection_bad": np.asarray([float(row.get("selected_p_projection_bad", float("nan"))) for row in selected_rows], dtype=np.float64),
        "selected_p_rollback_union": np.asarray([float(row.get("selected_p_rollback_union", float("nan"))) for row in selected_rows], dtype=np.float64),
    }
    margin_targets = {
        "gain_margin_badness": np.asarray([max(0.0, -float(row.get("gain_margin", 0.0))) for row in selected_rows], dtype=np.float64),
        "goal_margin_badness": np.asarray([max(0.0, -float(row.get("goal_margin", 0.0))) for row in selected_rows], dtype=np.float64),
        "projection_margin_badness": np.asarray([max(0.0, -float(row.get("projection_margin", 0.0))) for row in selected_rows], dtype=np.float64),
    }

    metrics: Dict[str, Any] = {"round_rows": int(len(round_rows)), "selected_round_rows": int(len(selected_rows))}
    for agg_name, scores in score_features.items():
        for target_name, labels in targets.items():
            metrics[f"corr_{agg_name}_{target_name}"] = _safe_corr(scores, labels)
            metrics[f"auc_{agg_name}_{target_name}"] = _safe_binary_auc(scores, labels)
            metrics[f"top_hit_rate_{agg_name}_{target_name}"] = _top_risk_hit_rate(scores, labels)
        for margin_name, margin_values in margin_targets.items():
            metrics[f"corr_{agg_name}_{margin_name}"] = _safe_corr(scores, margin_values)

    rollback_best = {
        agg_name: float(metrics[f"corr_{agg_name}_realized_rollback"])
        for agg_name in score_features
    }
    gain_bad_best = {
        agg_name: float(metrics[f"corr_{agg_name}_realized_gain_bad"])
        for agg_name in score_features
    }
    goal_bad_best = {
        agg_name: float(metrics[f"corr_{agg_name}_realized_goal_bad"])
        for agg_name in score_features
    }
    projection_bad_best = {
        agg_name: float(metrics[f"corr_{agg_name}_realized_projection_bad"])
        for agg_name in score_features
    }
    risk_family = {
        agg_name: score
        for agg_name, score in rollback_best.items()
        if agg_name.startswith("selected_pred_risk_")
    }

    best_rollback_name, best_rollback_corr = _best_metric_entry(rollback_best)
    best_gain_bad_name, best_gain_bad_corr = _best_metric_entry(gain_bad_best)
    best_goal_bad_name, best_goal_bad_corr = _best_metric_entry(goal_bad_best)
    best_projection_bad_name, best_projection_bad_corr = _best_metric_entry(projection_bad_best)
    best_risk_name, best_risk_corr = _best_metric_entry(risk_family)

    target_compare = {
        "rollback": float(best_rollback_corr),
        "gain_bad": float(best_gain_bad_corr),
        "goal_bad": float(best_goal_bad_corr),
        "projection_bad": float(best_projection_bad_corr),
    }
    easier_target_name, easier_target_corr = _best_metric_entry(target_compare)
    recommendation = "keep_single_label"
    enough_rows = int(len(selected_rows)) >= int(max(1, min_rows_for_recommendation))
    if not np.isfinite(easier_target_corr) or easier_target_corr <= 0.05:
        easier_target_name = "none_positive"
        recommendation = "target_mismatch_unresolved"
    elif np.isfinite(best_rollback_corr) and easier_target_name in {"gain_bad", "goal_bad", "projection_bad"}:
        if easier_target_corr > best_rollback_corr + 0.05:
            recommendation = "decompose_rollback_label"
    if not enough_rows:
        recommendation = "audit_rows_insufficient"
    policy_primary_target = "projection_bad" if np.isfinite(best_projection_bad_corr) and best_projection_bad_corr > 0.05 else "defer"

    cause_counts = Counter(str(row.get("cause_label", "none")) for row in selected_rows)
    metrics.update(
        {
            "audit_min_rows_for_recommendation": int(min_rows_for_recommendation),
            "audit_rows_sufficient": bool(enough_rows),
            "best_rollback_aggregation": best_rollback_name,
            "best_rollback_corr": float(best_rollback_corr),
            "best_risk_aggregation": best_risk_name,
            "best_risk_corr": float(best_risk_corr),
            "best_gain_bad_aggregation": best_gain_bad_name,
            "best_gain_bad_corr": float(best_gain_bad_corr),
            "best_goal_bad_aggregation": best_goal_bad_name,
            "best_goal_bad_corr": float(best_goal_bad_corr),
            "best_projection_bad_aggregation": best_projection_bad_name,
            "best_projection_bad_corr": float(best_projection_bad_corr),
            "easier_target": easier_target_name,
            "easier_target_corr": float(easier_target_corr),
            "policy_primary_target": policy_primary_target,
            "rollback_label_recommendation": recommendation,
            "rollback_cause_counts": dict(cause_counts),
        }
    )
    return metrics


def _compute_projection_calibration_metrics_from_histories(
    *,
    predicted_gain: List[float],
    predicted_gain_sign: List[float],
    predicted_projection: List[float],
    predicted_projection_risk: List[float],
    predicted_risk_diag: List[float],
    predicted_union: List[float],
    realized_gain_norm: List[float],
    realized_gain_sign: List[float],
    realized_projection: List[float],
    realized_projection_explosion: List[float],
    realized_rollback: List[float],
) -> Dict[str, Any]:
    return {
        "corr_pred_gain_realized_gain": _safe_corr(predicted_gain, realized_gain_norm),
        "corr_pred_gain_sign_realized_gain_sign": _safe_corr(predicted_gain_sign, realized_gain_sign),
        "corr_pred_projection_realized_projection": _safe_corr(predicted_projection, realized_projection),
        "corr_pred_projection_risk_realized_projection_explosion": _safe_corr(
            predicted_projection_risk,
            realized_projection_explosion,
        ),
        "corr_pred_risk_realized_rollback": _safe_corr(predicted_risk_diag, realized_rollback),
        "corr_pred_union_realized_rollback": _safe_corr(predicted_union, realized_rollback),
        "forecast_samples": int(len(predicted_gain)),
    }


def run_proposal_learning_loop(cfg: ProposalLearningConfig):
    _seed_all(cfg.seed)
    device = torch.device(cfg.device)

    if not cfg.eval_kwargs:
        cfg.eval_kwargs = _default_eval_kwargs()
    else:
        merged = _default_eval_kwargs()
        merged.update(cfg.eval_kwargs)
        cfg.eval_kwargs = merged

    noise_scale = float(cfg.eval_kwargs.get("noise_scale", 0.01))

    def make_env_for(round_idx: int, salt: int) -> SimpleTriadEnv:
        return SimpleTriadEnv(
            state_dim=cfg.state_dim,
            seed=int(cfg.seed + 1000 * round_idx + salt),
            noise_scale=noise_scale,
            horizon=max(cfg.steps_baseline, cfg.steps_dummy) + 5,
        )

    triad = build_triad(cfg)
    for a in triad:
        a.to(device)

    world_model = None
    wm_optimizer = None
    wm_replay: List[Tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = []

    if cfg.use_world_model:
        world_model = RSSMWorldModel(
            state_dim=cfg.state_dim,
            action_dim=cfg.state_dim,
            latent_dim=cfg.wm_latent_dim,
            hidden_dim=cfg.wm_hidden_dim,
        ).to(device)
        wm_optimizer = torch.optim.Adam(world_model.parameters(), lr=cfg.wm_lr)

    patch_template = triad[0].get_patch_state()
    pops = [make_proposal_population(cfg, patch_template) for _ in range(3)]
    for p in range(3):
        for net in pops[p]:
            net.to(device)

    # proposer health / reputation state
    proposer_credit = np.zeros((3,), dtype=np.float32)
    proposer_cooldown = np.zeros((3,), dtype=np.int32)
    proposer_recent_realized = np.zeros((3,), dtype=np.float32)
    proposer_recent_goal = np.zeros((3,), dtype=np.float32)
    instability_state = np.zeros((3,), dtype=np.float32)

    history: List[Dict[str, Any]] = []

    for r in range(cfg.rounds):
        proposer_cooldown = np.maximum(proposer_cooldown - 1, 0)

        base_env = make_env_for(r, salt=0)
        baseline_score, baseline_logs = evaluate_group_with_comms(
            agents=triad,
            env=base_env,
            steps=cfg.steps_baseline,
            critical_entropy=cfg.critical_entropy,
            world_model=world_model,
            wm_optimizer=wm_optimizer,
            wm_replay=wm_replay,
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
            **cfg.eval_kwargs,
        )

        if isinstance(baseline_score, (list, tuple, np.ndarray)):
            base_avg = float(np.mean(np.asarray(baseline_score, dtype=np.float32)))
        else:
            base_avg = float(baseline_score)

        metrics = _make_metrics_dict(baseline_logs)
        base_goal_mse = _last_metric(baseline_logs, "goal_mse_latent", metrics.get("goal_mse_latent_last", 0.0))
        base_goal_agreement = _last_metric(baseline_logs, "goal_agreement", metrics.get("goal_agreement_last", 0.0))
        goal_pressure = _compute_goal_pressure(
            base_goal_mse,
            soft=float(cfg.adaptive_patch_goal_mse_soft),
            hard=float(cfg.adaptive_patch_goal_mse_hard),
        )

        proposals: List[Dict[str, torch.Tensor]] = []
        for i in range(3):
            k = max(1, int(getattr(cfg, "sample_k", 1)))
            idxs = np.random.randint(0, cfg.pop_size, size=k)
            deltas_list = [pops[i][int(j)](metrics) for j in idxs]

            avg_delta: Dict[str, torch.Tensor] = {}
            keys = deltas_list[0].keys()
            for key in keys:
                avg_delta[key] = sum(d[key] for d in deltas_list) / float(k)
            proposals.append(avg_delta)

        mut = float(getattr(cfg, "mutation_std", 0.0))
        if mut > 0.0:
            for p in range(3):
                for k, v in list(proposals[p].items()):
                    if torch.is_tensor(v):
                        proposals[p][k] = v + mut * torch.randn_like(v)

        personal_dummies = clone_personal_dummies(triad)
        for d in personal_dummies:
            d.to(device)

        _bs2, _bl2, proposals_out, improvements, patch_sizes, _dummy_logs = triad_propose_test_personal_dummies(
            triad_agents=triad,
            personal_dummies=personal_dummies,
            proposals=proposals,
            world_model=world_model,
            wm_optimizer=wm_optimizer,
            wm_replay=wm_replay,
            cfg=cfg,
            eval_kwargs=cfg.eval_kwargs,
        )

        improvements = np.asarray(improvements, dtype=np.float32)
        patch_sizes = np.asarray(patch_sizes, dtype=np.float32)

        score_matrix = np.full((3, 3), -1e9, dtype=np.float32)
        scale_matrix = np.full((3, 3), float(cfg.adaptive_patch_scale_min), dtype=np.float32)

        for agent_i in range(3):
            for proposer_j in range(3):
                imp = float(improvements[agent_i, proposer_j])
                psz = float(patch_sizes[agent_i, proposer_j])

                if not np.isfinite(imp):
                    imp = -1e6
                if not np.isfinite(psz):
                    psz = 1e6

                # Proposer memory / merit (bounded so it cannot explode)
                hist_bonus = float(cfg.adoption_score_history_weight) * float(np.tanh(float(proposer_credit[proposer_j]) / 25.0))
                recent_bonus = 0.25 * float(np.tanh(float(proposer_recent_realized[proposer_j]) / 25.0))
                cooldown_penalty = 0.35 if proposer_cooldown[proposer_j] > 0 else 0.0
                instability_penalty = float(cfg.adoption_score_instability_weight) * float(np.clip(instability_state[proposer_j], 0.0, 1.0))

                # Goal calibration pressure
                goal_penalty = float(cfg.adoption_score_goal_mse_weight) * max(0.0, base_goal_mse - 1.0)
                agreement_bonus = float(cfg.adoption_score_goal_agreement_weight) * max(0.0, base_goal_agreement - 0.5)

                # Use a squashed improvement term so proposer history cannot dominate raw local benefit.
                improve_term = float(cfg.adoption_score_improve_weight) * float(np.tanh(imp / 8.0)) * 2.0

                candidate_score = (
                    improve_term
                    - float(cfg.adoption_score_patch_cost) * psz
                    - goal_penalty
                    - instability_penalty
                    - cooldown_penalty
                    + agreement_bonus
                    + hist_bonus
                    + recent_bonus
                )

                # Adaptive patch scale
                scale = float(cfg.adaptive_patch_scale_max)
                scale *= (1.0 - float(cfg.adaptive_patch_instability_weight) * _clip01(instability_state[proposer_j]))
                scale *= (1.0 - 0.55 * goal_pressure)
                scale *= (1.0 + float(cfg.adaptive_patch_credit_weight) * np.tanh(float(proposer_credit[proposer_j])))

                if proposer_cooldown[proposer_j] > 0:
                    scale = min(scale, float(cfg.adaptive_patch_cooldown_floor))

                scale = float(np.clip(scale, float(cfg.adaptive_patch_scale_min), float(cfg.adaptive_patch_scale_max)))

                # Conservative gate, but allow a fallback when local improvement is clearly strong.
                fallback_ok = (
                    imp >= float(getattr(cfg, "fallback_improve_trigger", 3.0))
                    and proposer_cooldown[proposer_j] <= 0
                    and goal_pressure <= float(getattr(cfg, "fallback_goal_pressure_max", 0.85))
                )

                if (candidate_score < float(cfg.adopt_threshold)) and (not fallback_ok):
                    candidate_score = -1e9
                elif fallback_ok:
                    candidate_score = max(candidate_score, float(cfg.adopt_threshold) + 0.01)

                score_matrix[agent_i, proposer_j] = candidate_score
                scale_matrix[agent_i, proposer_j] = scale

        pre_adopt_state_dicts = [
            {k: v.detach().cpu().clone() for k, v in a.state_dict().items()}
            for a in triad
        ]

        adopted = []
        adopted_meta: List[Tuple[int, int, float, float, float, float]] = []

        for agent_i in range(3):
            row = score_matrix[agent_i]
            proposer_j = int(np.argmax(row))
            choice_score = float(row[proposer_j])

            if not np.isfinite(choice_score) or choice_score <= -1e8:
                adopted.append(None)
                continue

            scale = float(scale_matrix[agent_i, proposer_j])
            scaled_patch = _scale_patch(proposals_out[proposer_j], scale)
            sz = _safe_adopt_patch(triad[agent_i], scaled_patch)

            imp = float(improvements[agent_i, proposer_j])
            adopted.append((agent_i, proposer_j, imp, float(sz), float(choice_score), float(scale)))
            adopted_meta.append((agent_i, proposer_j, imp, float(sz), float(choice_score), float(scale)))

        post_env = make_env_for(r, salt=777)
        post_score, post_logs = evaluate_group_with_comms(
            agents=triad,
            env=post_env,
            steps=cfg.steps_dummy,
            critical_entropy=cfg.critical_entropy,
            world_model=world_model,
            wm_optimizer=wm_optimizer,
            wm_replay=wm_replay,
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
            **cfg.eval_kwargs,
        )

        if isinstance(post_score, (list, tuple, np.ndarray)):
            post_avg = float(np.mean(np.asarray(post_score, dtype=np.float32)))
        else:
            post_avg = float(post_score)

        post_goal_mse = _last_metric(post_logs, "goal_mse_latent", 0.0)
        realized_gain = float(post_avg - base_avg)
        realized_goal_delta = float(post_goal_mse - base_goal_mse) if np.isfinite(post_goal_mse) and np.isfinite(base_goal_mse) else 0.0

        rollback_triggered = False
        if bool(getattr(cfg, "rollback_on_harm", True)) and adopted_meta:
            rollback_gain_bad = realized_gain < float(getattr(cfg, "rollback_min_gain", -0.5))
            rollback_goal_bad = realized_goal_delta > float(getattr(cfg, "rollback_max_goal_mse_increase", 0.10))
            if rollback_gain_bad or rollback_goal_bad:
                rollback_triggered = True
                for a, sd in zip(triad, pre_adopt_state_dicts):
                    a.load_state_dict(sd)

                restore_env = make_env_for(r, salt=777)
                restored_score, restored_logs = evaluate_group_with_comms(
                    agents=triad,
                    env=restore_env,
                    steps=cfg.steps_dummy,
                    critical_entropy=cfg.critical_entropy,
                    world_model=world_model,
                    wm_optimizer=wm_optimizer,
                    wm_replay=wm_replay,
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
                    **cfg.eval_kwargs,
                )

                if isinstance(restored_score, (list, tuple, np.ndarray)):
                    post_avg = float(np.mean(np.asarray(restored_score, dtype=np.float32)))
                else:
                    post_avg = float(restored_score)

                post_logs = restored_logs
                post_goal_mse = _last_metric(post_logs, "goal_mse_latent", 0.0)
                realized_gain = float(post_avg - base_avg)
                realized_goal_delta = (
                    float(post_goal_mse - base_goal_mse)
                    if np.isfinite(post_goal_mse) and np.isfinite(base_goal_mse)
                    else 0.0
                )

                realized_gain = min(realized_gain, float(getattr(cfg, "rollback_min_gain", -0.5)) - 0.5)
                realized_goal_delta = max(
                    realized_goal_delta,
                    float(getattr(cfg, "rollback_max_goal_mse_increase", 0.10)),
                )

        wm_loss = _safe_float(post_logs.get("wm_loss", [float("nan")])[-1] if isinstance(post_logs.get("wm_loss"), list) else post_logs.get("wm_loss"))
        wm_recon = _safe_float(post_logs.get("wm_recon", [float("nan")])[-1] if isinstance(post_logs.get("wm_recon"), list) else post_logs.get("wm_recon"))
        wm_kl = _safe_float(post_logs.get("wm_kl", [float("nan")])[-1] if isinstance(post_logs.get("wm_kl"), list) else post_logs.get("wm_kl"))

        # Update proposer reputation only from realized outcomes of adopted proposers.
        touched = set()
        for _ai, pj, _imp, _sz, _cs, _scl in adopted_meta:
            touched.add(int(pj))

        for pj in range(3):
            proposer_recent_realized[pj] *= 0.90
            proposer_recent_goal[pj] *= 0.90
            instability_state[pj] *= 0.85

            if pj not in touched:
                continue

            reward = realized_gain - 0.35 * max(0.0, realized_goal_delta)
            proposer_recent_realized[pj] = 0.75 * proposer_recent_realized[pj] + 0.25 * reward
            proposer_recent_goal[pj] = 0.75 * proposer_recent_goal[pj] + 0.25 * realized_goal_delta
            proposer_credit[pj] = (
                float(cfg.adoption_realized_reward_decay) * proposer_credit[pj]
                + (1.0 - float(cfg.adoption_realized_reward_decay)) * reward
            )
            proposer_credit[pj] = float(np.clip(proposer_credit[pj], -50.0, 50.0))

            if reward < 0.0:
                instability_state[pj] = min(1.0, instability_state[pj] + 0.25)

            if reward <= float(cfg.adoption_negative_cooldown_trigger):
                proposer_cooldown[pj] = max(proposer_cooldown[pj], int(cfg.adoption_cooldown_rounds))

        if cfg.verbose:
            adopt_strs = []
            for a in adopted:
                if a is None:
                    continue
                ai, pj, imp, sz, cs, scl = a
                adopt_strs.append(
                    f"A{ai}<=P{pj}(Δ={imp:+.3f}, sz={sz:.4f}, score={cs:+.3f}, scl={scl:.2f})"
                )
            adopt_str = ", ".join(adopt_strs) if adopt_strs else "none"
            if rollback_triggered and adopt_str != "none":
                adopt_str = "ROLLBACK[" + adopt_str + "]"

            print(
                f"Round {r:03d} | base_avg={base_avg:.3f} post_avg={post_avg:.3f} | "
                f"wm(loss={wm_loss:.4f}, recon={wm_recon:.4f}, kl={wm_kl:.4f}) | adopt: {adopt_str}"
            )

        history.append(
            dict(
                round=r,
                base_avg=base_avg,
                post_avg=post_avg,
                wm_loss=float(wm_loss) if wm_loss is not None else float("nan"),
                wm_recon=float(wm_recon) if wm_recon is not None else float("nan"),
                wm_kl=float(wm_kl) if wm_kl is not None else float("nan"),
                curiosity=float(post_logs.get("curiosity", 0.0)) if not isinstance(post_logs.get("curiosity", 0.0), list)
                        else float(post_logs.get("curiosity", [0.0])[-1]),
                goal_agreement=float(post_logs.get("goal_agreement", 0.0)) if not isinstance(post_logs.get("goal_agreement", 0.0), list)
                            else float(post_logs.get("goal_agreement", [0.0])[-1]),
                goal_mse_latent=float(post_logs.get("goal_mse_latent", 0.0)) if not isinstance(post_logs.get("goal_mse_latent", 0.0), list)
                                else float(post_logs.get("goal_mse_latent", [0.0])[-1]),
                improvements=improvements.copy(),
                patch_sizes=patch_sizes.copy(),
                score_matrix=score_matrix.copy(),
                scale_matrix=scale_matrix.copy(),
                proposer_credit=proposer_credit.copy(),
                proposer_cooldown=proposer_cooldown.copy(),
                instability_state=instability_state.copy(),
                adopted=adopted,
            )
        )

    return triad, pops, history


def run_proposal_learning_loop_v2(cfg: ProposalLearningConfig):
    _seed_all(cfg.seed)
    device = torch.device(cfg.device)
    live_policy_variant_name = str(getattr(cfg, "live_policy_variant", "baseline"))
    live_projection_bad_max_provisional = float(cfg.wm_candidate_pred_projection_bad_max_provisional)
    targeted_override_projection_bad_max = _targeted_live_projection_bad_override_max(cfg)
    active_targeted_override_projection_bad_max = (
        float(targeted_override_projection_bad_max)
        if live_policy_variant_name == "targeted_gain_goal_proj_margin_01"
        else None
    )
    print(f"[RUNTIME MARKER] proposal_learning_loop.py :: {RUNTIME_MARKER}")
    print(
        "[ROLLBACK TARGET] pred_risk higher means more likely round rollback | "
        f"label_scope=round_selected_set | horizon={int(cfg.steps_dummy)} steps"
    )
    print(
        "[LIVE POLICY] "
        f"variant={live_policy_variant_name} | "
        f"baseline_projection_bad_max_provisional={live_projection_bad_max_provisional:.3f} | "
        f"targeted_override_projection_bad_max={active_targeted_override_projection_bad_max if active_targeted_override_projection_bad_max is not None else 'n/a'}"
    )

    if not cfg.eval_kwargs:
        cfg.eval_kwargs = _default_eval_kwargs()
    else:
        merged = _default_eval_kwargs()
        merged.update(cfg.eval_kwargs)
        cfg.eval_kwargs = merged

    noise_scale = float(cfg.eval_kwargs.get("noise_scale", 0.01))

    def make_env_for(round_idx: int, salt: int) -> SimpleTriadEnv:
        return SimpleTriadEnv(
            state_dim=cfg.state_dim,
            seed=int(cfg.seed + 1000 * round_idx + salt),
            noise_scale=noise_scale,
            horizon=max(cfg.steps_baseline, cfg.steps_dummy) + 5,
        )

    def eval_group(agents: List[MemoryConsciousAgent], env: SimpleTriadEnv, steps: int):
        return evaluate_group_with_comms(
            agents=agents,
            env=env,
            steps=steps,
            critical_entropy=cfg.critical_entropy,
            world_model=world_model,
            wm_optimizer=wm_optimizer,
            wm_replay=wm_replay,
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
            **cfg.eval_kwargs,
        )

    def eval_group_shadow(agents: List[MemoryConsciousAgent], env: SimpleTriadEnv, steps: int):
        shadow_replay: List[Tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = []
        return evaluate_group_with_comms(
            agents=agents,
            env=env,
            steps=steps,
            critical_entropy=cfg.critical_entropy,
            world_model=world_model,
            wm_optimizer=None,
            wm_replay=shadow_replay,
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
            **cfg.eval_kwargs,
        )

    def coerce_avg(score_obj: Any) -> float:
        if isinstance(score_obj, (list, tuple, np.ndarray)):
            return float(np.mean(np.asarray(score_obj, dtype=np.float32)))
        return float(score_obj)

    triad = build_triad(cfg)
    for agent in triad:
        agent.to(device)

    world_model = None
    wm_optimizer = None
    wm_replay: List[Tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = []
    if cfg.use_world_model:
        world_model = RSSMWorldModel(
            state_dim=cfg.state_dim,
            action_dim=cfg.state_dim,
            latent_dim=cfg.wm_latent_dim,
            hidden_dim=cfg.wm_hidden_dim,
        ).to(device)
        wm_optimizer = torch.optim.Adam(world_model.parameters(), lr=cfg.wm_lr)

    patch_template = triad[0].get_patch_state()
    empty_patch = {k: torch.zeros_like(v) for k, v in patch_template.items()}
    pops = [make_proposal_population(cfg, patch_template) for _ in range(3)]
    for proposer_pop in pops:
        for net in proposer_pop:
            net.to(device)

    proposer_credit = np.zeros((3,), dtype=np.float32)
    proposer_cooldown = np.zeros((3,), dtype=np.int32)
    proposer_recent_realized = np.zeros((3,), dtype=np.float32)
    proposer_recent_goal = np.zeros((3,), dtype=np.float32)
    proposer_rollback_trials = np.zeros((3,), dtype=np.float32)
    proposer_rollback_hits = np.zeros((3,), dtype=np.float32)
    proposer_rollback_rate = np.zeros((3,), dtype=np.float32)
    instability_state = np.zeros((3,), dtype=np.float32)

    self_score_history: List[List[float]] = [[] for _ in range(3)]
    self_best_streak = np.zeros((3,), dtype=np.int32)
    self_best_count = np.zeros((3,), dtype=np.int32)
    self_same_agent_recurrence_hits = np.zeros((3,), dtype=np.int32)
    self_same_agent_recurrence_trials = np.zeros((3,), dtype=np.int32)
    self_event_any_history: List[float] = []
    self_adopted_any_history: List[float] = []
    self_best_score_history: List[float] = []
    self_best_pressure_history: List[float] = []
    self_best_patch_size_history: List[float] = []
    self_event_gain_history: List[float] = []
    realized_gain_history: List[float] = []

    projected_gain_history: List[float] = []
    projected_gain_sign_history: List[float] = []
    projected_projection_history: List[float] = []
    projected_projection_risk_history: List[float] = []
    projected_risk_history: List[float] = []
    projected_union_history: List[float] = []
    realized_gain_norm_history: List[float] = []
    realized_gain_sign_history: List[float] = []
    realized_projection_history: List[float] = []
    realized_projection_explosion_history: List[float] = []
    realized_rollback_history: List[float] = []

    shadow_projected_gain_history: List[float] = []
    shadow_projected_gain_sign_history: List[float] = []
    shadow_projected_projection_history: List[float] = []
    shadow_projected_projection_risk_history: List[float] = []
    shadow_projected_risk_history: List[float] = []
    shadow_projected_union_history: List[float] = []
    shadow_realized_gain_norm_history: List[float] = []
    shadow_realized_gain_sign_history: List[float] = []
    shadow_realized_projection_history: List[float] = []
    shadow_realized_projection_explosion_history: List[float] = []
    shadow_realized_rollback_history: List[float] = []

    live_selected_round_flags: List[float] = []
    shadow_selected_round_flags: List[float] = []
    combined_selected_round_flags: List[float] = []
    shadow_available_round_flags: List[float] = []
    near_threshold_blocked_history: List[float] = []
    blocked_projection_veto_history: List[float] = []
    blocked_confidence_gate_history: List[float] = []
    blocked_gain_gate_history: List[float] = []
    live_variant_baseline_rejected_history: List[float] = []
    live_variant_projection_eligible_history: List[float] = []
    live_variant_conf_gain_eligible_history: List[float] = []
    live_variant_persistence_eligible_history: List[float] = []
    live_variant_recovery_eligible_history: List[float] = []
    live_variant_quality_eligible_history: List[float] = []
    live_variant_override_history: List[float] = []
    live_variant_block_projection_history: List[float] = []
    live_variant_block_persistence_history: List[float] = []
    live_variant_block_recovery_history: List[float] = []
    live_variant_block_conf_gain_history: List[float] = []
    live_variant_projected_quality_guard_history: List[float] = []
    live_variant_block_other_history: List[float] = []
    safe_gain_blocked_narrow_history: List[float] = []
    safe_gain_blocked_wide_history: List[float] = []
    wider_gain_band_only_history: List[float] = []
    shadow_rows_from_gain_band_history: List[float] = []
    shadow_rows_from_wider_gain_band_history: List[float] = []

    provisional_owner = np.full((3,), -1, dtype=np.int32)
    provisional_evidence = np.zeros((3,), dtype=np.float32)
    provisional_rounds = np.zeros((3,), dtype=np.int32)

    history: List[Dict[str, Any]] = []
    rollback_audit_log: List[Dict[str, Any]] = []
    rollback_round_audit_log: List[Dict[str, Any]] = []
    shadow_rollback_audit_log: List[Dict[str, Any]] = []
    shadow_rollback_round_audit_log: List[Dict[str, Any]] = []
    prev_self_best_agent: Optional[int] = None
    live_variant_override_rounds: List[int] = []

    for r in range(cfg.rounds):
        proposer_cooldown = np.maximum(proposer_cooldown - 1, 0)

        baseline_score, baseline_logs = eval_group(triad, make_env_for(r, 0), cfg.steps_baseline)
        base_avg = coerce_avg(baseline_score)
        metrics = _make_metrics_dict(baseline_logs)
        baseline_9d_metrics = _extract_explicit_9d_metrics(baseline_logs)
        base_goal_mse = _last_metric(baseline_logs, "goal_mse_latent", metrics.get("goal_mse_latent_last", 0.0))
        base_goal_agreement = _last_metric(baseline_logs, "goal_agreement", metrics.get("goal_agreement_last", 0.0))
        goal_pressure = _compute_goal_pressure(
            base_goal_mse,
            soft=float(cfg.adaptive_patch_goal_mse_soft),
            hard=float(cfg.adaptive_patch_goal_mse_hard),
        )

        self_phase_metrics = dict(baseline_logs)
        self_phase_metrics.update(metrics)
        self_phase_metrics["critical_entropy"] = float(cfg.critical_entropy)
        self_phase_metrics["base_avg"] = float(base_avg)
        self_phase_metrics["goal_mse_latent"] = float(base_goal_mse)
        self_phase_metrics["goal_agreement"] = float(base_goal_agreement)

        self_adopted: List[Tuple[int, float, float, float, float, float]] = []
        self_blocked: List[Tuple[int, str, float, float, float, float]] = []
        self_diag_pressures = np.zeros((3,), dtype=np.float32)
        self_diag_scores = np.zeros((3,), dtype=np.float32)
        self_diag_improvements = np.zeros((3,), dtype=np.float32)
        self_diag_patch_sizes = np.zeros((3,), dtype=np.float32)
        self_adopt_scores = np.zeros((3,), dtype=np.float32)
        self_persistence_signals = np.zeros((3,), dtype=np.float32)
        self_primary_reasons = ["no self event" for _ in range(3)]
        self_reason_counter: Counter[str] = Counter()
        self_candidate_counts = {
            "self_candidates_raw": 0,
            "self_candidates_after_sz": 0,
            "self_candidates_after_conf": 0,
            "self_candidates_after_persistence": 0,
        }

        self_proposals: List[Dict[str, torch.Tensor]] = []
        self_diagnostics: List[Dict[str, float]] = []
        for idx, agent in enumerate(triad):
            patch, diagnostic = agent.propose_self_patch(
                self_phase_metrics,
                persistence_streak=int(self_best_streak[idx]),
            )
            self_proposals.append(patch if patch else dict(empty_patch))
            self_diagnostics.append(diagnostic)

        self_dummies = clone_personal_dummies(triad)
        for dummy in self_dummies:
            dummy.to(device)

        _sbs, _sbl, self_proposals_out, self_improvements, self_patch_sizes, self_dummy_logs = triad_propose_test_personal_dummies(
            triad_agents=triad,
            personal_dummies=self_dummies,
            proposals=self_proposals,
            world_model=world_model,
            wm_optimizer=wm_optimizer,
            wm_replay=wm_replay,
            cfg=cfg,
            eval_kwargs=cfg.eval_kwargs,
        )
        self_improvements = np.asarray(self_improvements, dtype=np.float32)
        self_patch_sizes = np.asarray(self_patch_sizes, dtype=np.float32)
        self_score_matrix = np.asarray(self_dummy_logs.get("score_matrix", np.zeros((3, 3), dtype=np.float32)), dtype=np.float32)

        for idx, agent in enumerate(triad):
            diag = self_diagnostics[idx]
            improvement = float(self_improvements[idx, idx])
            score = float(self_score_matrix[idx, idx])
            patch_size = float(self_patch_sizes[idx, idx])
            decision = agent.decide_self_patch_adoption(
                improvement=improvement,
                score=score,
                patch_size=patch_size,
                diagnostic=diag,
            )
            self_diag_pressures[idx] = float(diag.get("pressure", 0.0))
            self_diag_scores[idx] = float(score)
            self_diag_improvements[idx] = float(improvement)
            self_diag_patch_sizes[idx] = float(patch_size)
            self_adopt_scores[idx] = float(decision.get("adopt_score", 0.0))
            self_persistence_signals[idx] = float(decision.get("persistence_signal", 0.0))
            self_primary_reasons[idx] = str(decision.get("primary_reason", "self adoption blocked"))
            self_reason_counter[self_primary_reasons[idx]] += 1

            has_real_patch = patch_size > 0.0 and any(torch.count_nonzero(v).item() > 0 for v in self_proposals_out[idx].values())
            if has_real_patch:
                self_candidate_counts["self_candidates_raw"] += 1
                if patch_size <= float(cfg.self_improve_patch_l2_hard):
                    self_candidate_counts["self_candidates_after_sz"] += 1
                if float(decision.get("adopt_score", 0.0)) >= float(cfg.self_improve_adopt_threshold):
                    self_candidate_counts["self_candidates_after_conf"] += 1
                if float(decision.get("persistence_signal", 0.0)) >= float(cfg.self_improve_persistence_floor):
                    self_candidate_counts["self_candidates_after_persistence"] += 1

            adopted_self = bool(float(decision.get("adopt", 0.0)) >= 0.5)
            applied_size = 0.0
            if adopted_self:
                applied_size = _safe_adopt_patch(triad[idx], self_proposals_out[idx])
                self_adopted.append(
                    (
                        idx,
                        float(improvement),
                        float(score),
                        float(applied_size),
                        float(decision.get("adopt_score", 0.0)),
                        float(diag.get("pressure", 0.0)),
                    )
                )
            else:
                self_blocked.append(
                    (
                        idx,
                        self_primary_reasons[idx],
                        float(improvement),
                        float(score),
                        float(patch_size),
                        float(diag.get("pressure", 0.0)),
                    )
                )
            agent.record_self_improvement_outcome(
                dummy_improvement=float(improvement),
                dummy_score=float(score),
                adopted=adopted_self,
                patch_size=float(applied_size if adopted_self else patch_size),
            )

        shadow_start_obs = _extract_env_reset_obs(
            make_env_for(r, 777),
            n_agents=len(triad),
            state_dim=cfg.state_dim,
        )
        forecast_horizon = int(cfg.steps_dummy if cfg.wm_candidate_projection_match_post_horizon else cfg.wm_candidate_projection_horizon)
        baseline_shadow = _world_model_shadow_rollout(
            agents=triad,
            world_model=world_model,
            start_obs=shadow_start_obs,
            horizon=forecast_horizon,
            samples=int(cfg.wm_candidate_projection_samples),
            gamma=float(cfg.wm_candidate_projection_gamma),
            seed_base=int(cfg.seed + 10000 * r + 17),
        )

        proposals: List[Dict[str, torch.Tensor]] = []
        for proposer_idx in range(3):
            sample_k = max(1, int(getattr(cfg, "sample_k", 1)))
            idxs = np.random.randint(0, cfg.pop_size, size=sample_k)
            deltas_list = [pops[proposer_idx][int(j)](metrics) for j in idxs]
            avg_delta: Dict[str, torch.Tensor] = {}
            for key in deltas_list[0].keys():
                avg_delta[key] = sum(delta[key] for delta in deltas_list) / float(sample_k)
            proposals.append(avg_delta)

        mut = float(getattr(cfg, "mutation_std", 0.0))
        if mut > 0.0:
            for proposer_idx in range(3):
                for key, value in list(proposals[proposer_idx].items()):
                    if torch.is_tensor(value):
                        proposals[proposer_idx][key] = value + mut * torch.randn_like(value)

        personal_dummies = clone_personal_dummies(triad)
        for dummy in personal_dummies:
            dummy.to(device)

        _bs2, _bl2, proposals_out, improvements, patch_sizes, dummy_logs = triad_propose_test_personal_dummies(
            triad_agents=triad,
            personal_dummies=personal_dummies,
            proposals=proposals,
            world_model=world_model,
            wm_optimizer=wm_optimizer,
            wm_replay=wm_replay,
            cfg=cfg,
            eval_kwargs=cfg.eval_kwargs,
        )
        improvements = np.asarray(improvements, dtype=np.float32)
        patch_sizes = np.asarray(patch_sizes, dtype=np.float32)
        social_local_scores = np.asarray(dummy_logs.get("score_matrix", np.zeros((3, 3), dtype=np.float32)), dtype=np.float32)

        score_matrix = np.full((3, 3), -1e9, dtype=np.float32)
        raw_score_matrix = np.full((3, 3), float("nan"), dtype=np.float32)
        cal_conf_matrix = np.full((3, 3), float("nan"), dtype=np.float32)
        gain_score_matrix = np.full((3, 3), float("nan"), dtype=np.float32)
        projected_score_matrix = np.full((3, 3), float("nan"), dtype=np.float32)
        scale_matrix = np.full((3, 3), float(cfg.adaptive_patch_scale_min), dtype=np.float32)

        adopt_blocked: List[Dict[str, Any]] = []
        social_details: List[Dict[str, Any]] = []
        adopt_candidate_counts = {
            "adopt_candidates_raw": 0,
            "adopt_candidates_after_post": 0,
            "adopt_candidates_after_conf": 0,
            "adopt_candidates_after_gain": 0,
            "adopt_candidates_provisional": 0,
            "adopt_candidates_after_gate": 0,
            "adopt_candidates_final_adopt": 0,
        }
        shadow_candidate_counts = {
            "shadow_candidates_eligible": 0,
            "shadow_candidates_conf_margin": 0,
            "shadow_candidates_gain_margin": 0,
            "shadow_candidates_gain_margin_narrow": 0,
            "shadow_candidates_gain_margin_wide_only": 0,
            "shadow_candidates_alt_live": 0,
            "shadow_candidates_gain_band_selected": 0,
            "shadow_candidates_gain_band_wide_selected": 0,
            "shadow_candidates_selected": 0,
            "shadow_round_selected": 0,
        }
        selection_rate_diagnostics = {
            "live_selected_set_present": 0,
            "shadow_candidate_available": 0,
            "near_threshold_blocked_candidates": 0,
            "blocked_by_projection_veto": 0,
            "blocked_by_confidence_gate": 0,
            "blocked_by_gain_gate": 0,
            "blocked_by_conf_or_gain": 0,
            "live_variant_override_count": 0,
            "live_variant_persistence_guard": 0,
            "live_variant_recovery_guard": 0,
            "live_variant_projection_guard": 0,
            "live_variant_projected_quality_guard": 0,
            "live_variant_baseline_rejected_candidates": 0,
            "live_variant_projection_eligible_candidates": 0,
            "live_variant_conf_gain_eligible_candidates": 0,
            "live_variant_persistence_eligible_candidates": 0,
            "live_variant_recovery_eligible_candidates": 0,
            "live_variant_quality_eligible_candidates": 0,
            "live_variant_block_conf_gain": 0,
            "live_variant_block_other": 0,
            "safe_gain_blocked_narrow": 0,
            "safe_gain_blocked_wide": 0,
            "would_qualify_wider_gain_band": 0,
            "shadow_rows_from_gain_band": 0,
            "shadow_rows_from_wider_gain_band": 0,
        }
        wm_plan_context_rows: List[Dict[str, Any]] = []

        for agent_i in range(3):
            for proposer_j in range(3):
                imp = float(improvements[agent_i, proposer_j])
                psz = float(patch_sizes[agent_i, proposer_j])
                local_score = float(social_local_scores[agent_i, proposer_j])
                if not np.isfinite(imp):
                    imp = -1e6
                if not np.isfinite(psz):
                    psz = 1e6
                if not np.isfinite(local_score):
                    local_score = -1e6

                adopt_candidate_counts["adopt_candidates_raw"] += 1
                if imp > 0.0:
                    adopt_candidate_counts["adopt_candidates_after_post"] += 1

                moving_average = _safe_mean_arr(self_score_history[proposer_j][-4:], default=0.0)
                retained_evidence = float(provisional_evidence[agent_i]) if int(provisional_owner[agent_i]) == proposer_j else 0.0
                retained_rounds = int(provisional_rounds[agent_i]) if int(provisional_owner[agent_i]) == proposer_j else 0

                confidence = _compute_social_confidence(
                    cfg=cfg,
                    local_score=local_score,
                    moving_average=moving_average,
                    persistence_streak=int(self_best_streak[proposer_j]),
                    c2_strength=float(baseline_9d_metrics.get("C2_self_model_strength", 0.0)),
                    c3_stability=float(baseline_9d_metrics.get("C3_perspective_stability", 0.0)),
                    patch_size=psz,
                    retained_evidence=retained_evidence,
                )
                gain_signal = _compute_social_improvement_signal(
                    cfg=cfg,
                    dummy_improvement=imp,
                    local_score=local_score,
                    recent_realized=float(proposer_recent_realized[proposer_j]),
                    proposer_credit=float(proposer_credit[proposer_j]),
                    rollback_rate=float(proposer_rollback_rate[proposer_j]),
                    projection_error=float(baseline_9d_metrics.get("projection_error", 0.0)),
                    goal_pressure=float(goal_pressure),
                    instability=float(instability_state[proposer_j]),
                    patch_size=psz,
                )

                coherence_raw = float(confidence["raw_confidence"])
                coherence_cal = float(confidence["calibrated_confidence"])
                gain_raw = float(gain_signal["raw_gain"])
                gain_cal = float(gain_signal["calibrated_gain"])
                selection_score_raw = (
                    float(cfg.adoption_score_selection_conf_weight) * coherence_raw
                    + float(cfg.adoption_score_selection_gain_weight) * gain_raw
                )
                selection_score = (
                    float(cfg.adoption_score_selection_conf_weight) * coherence_cal
                    + float(cfg.adoption_score_selection_gain_weight) * gain_cal
                )

                scale = float(cfg.adaptive_patch_scale_max)
                scale *= (1.0 - float(cfg.adaptive_patch_instability_weight) * _clip01(float(instability_state[proposer_j])))
                scale *= (1.0 - 0.55 * float(goal_pressure))
                scale *= (1.0 + float(cfg.adaptive_patch_credit_weight) * np.tanh(float(proposer_credit[proposer_j])))
                if proposer_cooldown[proposer_j] > 0:
                    scale = min(scale, float(cfg.adaptive_patch_cooldown_floor))
                scale = float(np.clip(scale, float(cfg.adaptive_patch_scale_min), float(cfg.adaptive_patch_scale_max)))

                forecast_context = _build_forecast_context(
                    cfg=cfg,
                    baseline_logs=baseline_logs,
                    baseline_9d_metrics=baseline_9d_metrics,
                    proposer_recent_realized=float(proposer_recent_realized[proposer_j]),
                    proposer_rollback_rate=float(proposer_rollback_rate[proposer_j]),
                    retained_evidence=retained_evidence,
                    retained_rounds=retained_rounds,
                    realized_gain_history=realized_gain_history,
                )
                forecast_context["dummy_improvement"] = float(imp)
                forecast_context["gain_cal"] = float(gain_cal)
                forecast_context["coherence_cal"] = float(coherence_cal)
                forecast_context["goal_pressure"] = float(goal_pressure)

                projected_signal: Dict[str, Any] = {"available": False, "components": {}}
                if bool(cfg.wm_candidate_projection_enabled) and baseline_shadow.get("available", False) and shadow_start_obs is not None:
                    shadow_agents = clone_personal_dummies(triad)
                    for shadow_agent in shadow_agents:
                        shadow_agent.to(device)
                    _safe_adopt_patch(shadow_agents[agent_i], _scale_patch(proposals_out[proposer_j], scale))
                    candidate_shadow = _world_model_shadow_rollout(
                        agents=shadow_agents,
                        world_model=world_model,
                        start_obs=shadow_start_obs,
                        horizon=forecast_horizon,
                        samples=int(cfg.wm_candidate_projection_samples),
                        gamma=float(cfg.wm_candidate_projection_gamma),
                        seed_base=int(cfg.seed + 10000 * r + 101 * agent_i + 13 * proposer_j + 503),
                    )
                    projected_signal = _compute_projected_outcome_signal(
                        cfg=cfg,
                        baseline_shadow=baseline_shadow,
                        candidate_shadow=candidate_shadow,
                        forecast_context=forecast_context,
                    )
                    v4_wm_discrimination = _compute_v4_wm_context_signal_discrimination(
                        cfg=cfg,
                        forecast_context=forecast_context,
                        projected_signal=projected_signal,
                    )
                    projected_signal["v4_wm_context_discrimination"] = dict(v4_wm_discrimination)
                    if bool(v4_wm_discrimination.get("applied", False)):
                        projected_signal["raw_projected"] = float(v4_wm_discrimination.get("raw_projected", projected_signal.get("raw_projected", 0.0)))
                        projected_signal["calibrated_projected"] = float(
                            v4_wm_discrimination.get("calibrated_projected", projected_signal.get("calibrated_projected", 0.0))
                        )
                        projected_components = dict(projected_signal.get("components", {}))
                        projected_components["v4_wm_context_discrimination"] = float(v4_wm_discrimination.get("raw_delta", 0.0))
                        projected_signal["components"] = projected_components
                    v4_wm_residual_signal = _compute_v4_wm_context_residual_signal_discrimination(
                        cfg=cfg,
                        forecast_context=forecast_context,
                        projected_signal=projected_signal,
                    )
                    projected_signal["v4_wm_context_residual_signal"] = dict(v4_wm_residual_signal)
                    if bool(v4_wm_residual_signal.get("applied", False)):
                        projected_signal["raw_projected"] = float(
                            v4_wm_residual_signal.get("raw_projected", projected_signal.get("raw_projected", 0.0))
                        )
                        projected_signal["calibrated_projected"] = float(
                            v4_wm_residual_signal.get("calibrated_projected", projected_signal.get("calibrated_projected", 0.0))
                        )
                        projected_components = dict(projected_signal.get("components", {}))
                        projected_components["v4_wm_context_residual_signal"] = float(
                            v4_wm_residual_signal.get("raw_delta", 0.0)
                        )
                        projected_signal["components"] = projected_components
                    v4_wm_hybrid_boundary = _compute_v4_wm_baseline_hybrid_boundary(
                        cfg=cfg,
                        forecast_context=forecast_context,
                        projected_signal=projected_signal,
                    )
                    projected_signal["v4_wm_baseline_hybrid_boundary"] = dict(v4_wm_hybrid_boundary)
                    v4_wm_hybrid_context_scoped = _compute_v4_wm_hybrid_context_scoped_boundary(
                        cfg=cfg,
                        forecast_context=forecast_context,
                        projected_signal=projected_signal,
                        hybrid_boundary=v4_wm_hybrid_boundary,
                    )
                    projected_signal["v4_wm_hybrid_context_scoped"] = dict(v4_wm_hybrid_context_scoped)
                    v4_wm_hybrid_context_stabilization = _compute_v4_wm_hybrid_context_stabilization(
                        cfg=cfg,
                        forecast_context=forecast_context,
                        projected_signal=projected_signal,
                        hybrid_boundary=v4_wm_hybrid_boundary,
                        context_scoped=v4_wm_hybrid_context_scoped,
                    )
                    projected_signal["v4_wm_hybrid_context_stabilization"] = dict(v4_wm_hybrid_context_stabilization)
                    if bool(v4_wm_hybrid_context_stabilization.get("applied", False)):
                        projected_signal["raw_projected"] = float(
                            v4_wm_hybrid_context_stabilization.get(
                                "raw_projected",
                                projected_signal.get("raw_projected", 0.0),
                            )
                        )
                        projected_signal["calibrated_projected"] = float(
                            v4_wm_hybrid_context_stabilization.get(
                                "calibrated_projected",
                                projected_signal.get("calibrated_projected", 0.0),
                            )
                        )
                        projected_components = dict(projected_signal.get("components", {}))
                        projected_components["v4_wm_hybrid_context_stabilization"] = float(
                            v4_wm_hybrid_context_stabilization.get("raw_delta", 0.0)
                        )
                        projected_signal["components"] = projected_components
                    elif bool(v4_wm_hybrid_context_scoped.get("applied", False)):
                        projected_signal["raw_projected"] = float(
                            v4_wm_hybrid_context_scoped.get("raw_projected", projected_signal.get("raw_projected", 0.0))
                        )
                        projected_signal["calibrated_projected"] = float(
                            v4_wm_hybrid_context_scoped.get("calibrated_projected", projected_signal.get("calibrated_projected", 0.0))
                        )
                        projected_components = dict(projected_signal.get("components", {}))
                        projected_components["v4_wm_hybrid_context_scoped"] = float(
                            v4_wm_hybrid_context_scoped.get("raw_delta", 0.0)
                        )
                        projected_signal["components"] = projected_components
                    elif bool(v4_wm_hybrid_boundary.get("applied", False)):
                        projected_signal["raw_projected"] = float(
                            v4_wm_hybrid_boundary.get("raw_projected", projected_signal.get("raw_projected", 0.0))
                        )
                        projected_signal["calibrated_projected"] = float(
                            v4_wm_hybrid_boundary.get("calibrated_projected", projected_signal.get("calibrated_projected", 0.0))
                        )
                        projected_components = dict(projected_signal.get("components", {}))
                        projected_components["v4_wm_baseline_hybrid_boundary"] = float(
                            v4_wm_hybrid_boundary.get("raw_delta", 0.0)
                        )
                        projected_signal["components"] = projected_components
                    sel_w = float(np.clip(float(cfg.wm_candidate_projection_selection_weight), 0.0, 1.0))
                    selection_score_raw = (1.0 - sel_w) * selection_score_raw + sel_w * float(projected_signal.get("raw_projected", 0.0))
                    selection_score = (1.0 - sel_w) * selection_score + sel_w * float(projected_signal.get("calibrated_projected", 0.0))

                projected_available = bool(projected_signal.get("available", False))
                pred_projection_bad_prob = float(projected_signal.get("pred_projection_bad_prob", 1.0))
                pred_gain_bad_prob = float(projected_signal.get("pred_gain_bad_prob", 1.0))
                pred_goal_bad_prob = float(projected_signal.get("pred_goal_bad_prob", 1.0))
                pred_rollback_union = float(projected_signal.get("pred_rollback_union", 1.0))
                projection_policy_ok_provisional = bool(
                    (not projected_available)
                    or pred_projection_bad_prob <= float(live_projection_bad_max_provisional)
                )
                projection_policy_ok_full = bool(
                    projected_available
                    and pred_projection_bad_prob <= float(cfg.wm_candidate_pred_projection_bad_max_full)
                )
                rollback_union_ok_full = bool(
                    projected_available
                    and pred_rollback_union <= float(cfg.wm_candidate_pred_rollback_union_max_full)
                )

                passed_conf_stage = bool(
                    coherence_cal >= float(confidence["provisional_threshold"])
                    and local_score >= float(cfg.social_conf_min_local_score)
                )
                passed_gain_stage = bool(
                    passed_conf_stage
                    and gain_cal >= float(gain_signal["provisional_threshold"])
                    and imp > 0.0
                )
                if passed_conf_stage:
                    adopt_candidate_counts["adopt_candidates_after_conf"] += 1
                if passed_gain_stage:
                    adopt_candidate_counts["adopt_candidates_after_gain"] += 1

                status = "blocked"
                threshold_used = float(max(confidence["provisional_threshold"], gain_signal["provisional_threshold"]))
                threshold_mode = "base"
                reasons: List[str] = []
                if imp <= 0.0:
                    reasons.append(f"post_avg below threshold (dummy d={imp:+.3f})")
                blocked_by_confidence = bool(not passed_conf_stage)
                blocked_by_gain = bool((not blocked_by_confidence) and (not passed_gain_stage))
                blocked_by_projection = bool((not blocked_by_confidence) and (not blocked_by_gain) and (not projection_policy_ok_provisional))
                if blocked_by_confidence:
                    reasons.append(
                        f"social confidence too low (conf={coherence_cal:.3f} < provisional={float(confidence['provisional_threshold']):.3f})"
                    )
                elif blocked_by_gain:
                    reasons.append(
                        f"improvement confidence too low (gain={gain_cal:.3f} < provisional={float(gain_signal['provisional_threshold']):.3f})"
                    )
                elif blocked_by_projection:
                    if projected_available and pred_projection_bad_prob > float(live_projection_bad_max_provisional):
                        reasons.append(
                            f"projected projection_bad high (p={pred_projection_bad_prob:.3f} > provisional={float(live_projection_bad_max_provisional):.3f})"
                        )
                    else:
                        reasons.append("projection safety unavailable for provisional policy")
                else:
                    status = "provisional"
                    threshold_mode = f"{confidence['threshold_mode']}/provisional"
                    adopt_candidate_counts["adopt_candidates_provisional"] += 1
                    adopt_candidate_counts["adopt_candidates_after_gate"] += 1

                    # Direct rollback risk stayed misaligned in audit, so v3 policy now trusts decomposed
                    # projection safety first and only uses the derived union as a secondary bound.
                    full_ready = bool(
                        coherence_cal >= float(confidence["full_threshold"])
                        and gain_cal >= float(gain_signal["full_threshold"])
                        and imp >= float(cfg.social_conf_full_improvement_min)
                        and local_score >= float(cfg.social_conf_full_local_min)
                        and bool(gain_signal.get("projection_ok_full", False))
                        and projection_policy_ok_full
                        and rollback_union_ok_full
                        and float(projected_signal.get("calibrated_projected", 0.0)) >= float(cfg.wm_candidate_pred_score_threshold_full)
                        and float(projected_signal.get("pred_gain_sign_prob", 0.0)) >= float(cfg.wm_candidate_pred_gain_sign_min_full)
                    )
                    if full_ready:
                        status = "full"
                        threshold_mode = f"{confidence['threshold_mode']}/full"
                        threshold_used = float(
                            max(
                                confidence["full_threshold"],
                                gain_signal["full_threshold"],
                                float(cfg.wm_candidate_pred_score_threshold_full),
                            )
                        )
                        adopt_candidate_counts["adopt_candidates_final_adopt"] += 1
                    else:
                        if float(projected_signal.get("pred_gain_sign_prob", 0.0)) < float(cfg.wm_candidate_pred_gain_sign_min_full):
                            reasons.append(
                                f"projected gain weak (prob={float(projected_signal.get('pred_gain_sign_prob', 0.0)):.3f})"
                            )
                        if pred_projection_bad_prob > float(cfg.wm_candidate_pred_projection_bad_max_full):
                            reasons.append(
                                f"projected projection_bad elevated (p={pred_projection_bad_prob:.3f})"
                            )
                        if pred_rollback_union > float(cfg.wm_candidate_pred_rollback_union_max_full):
                            reasons.append(
                                f"derived rollback_union high (p={pred_rollback_union:.3f})"
                            )

                live_variant_override = _evaluate_live_policy_targeted_override(
                    cfg=cfg,
                    projected_available=projected_available,
                    baseline_projection_ok_provisional=projection_policy_ok_provisional,
                    coherence_cal=coherence_cal,
                    gain_cal=gain_cal,
                    confidence=confidence,
                    gain_signal=gain_signal,
                    pred_projection_bad_prob=pred_projection_bad_prob,
                    pred_gain_sign_prob=float(projected_signal.get("pred_gain_sign_prob", 0.0)),
                    pred_gain_bad_prob=pred_gain_bad_prob,
                    projected_score=float(projected_signal.get("calibrated_projected", 0.0)),
                    moving_average=moving_average,
                    persistence_streak=int(self_best_streak[proposer_j]),
                    retained_evidence=retained_evidence,
                    rollback_rate=float(proposer_rollback_rate[proposer_j]),
                    instability=float(instability_state[proposer_j]),
                )
                live_variant_override_applied = False
                if status == "blocked" and not blocked_by_projection and bool(live_variant_override.get("apply", False)):
                    status = "provisional"
                    threshold_mode = "variant/safe_provisional_override"
                    threshold_used = float(
                        max(
                            float(live_variant_override.get("conf_threshold", confidence["provisional_threshold"])),
                            float(live_variant_override.get("gain_threshold", gain_signal["provisional_threshold"])),
                        )
                    )
                    reasons = [
                        (
                            "benchmark-approved reject->provisional override "
                            f"(p_proj_bad<={float(live_variant_override.get('projection_max', targeted_override_projection_bad_max)):.3f})"
                        )
                    ]
                    adopt_candidate_counts["adopt_candidates_provisional"] += 1
                    adopt_candidate_counts["adopt_candidates_after_gate"] += 1
                    selection_rate_diagnostics["live_variant_override_count"] += 1
                    live_variant_override_applied = True

                if status == "blocked":
                    selection_rate_diagnostics["live_variant_baseline_rejected_candidates"] += 1
                    if bool(live_variant_override.get("safe_projection", False)):
                        selection_rate_diagnostics["live_variant_projection_eligible_candidates"] += 1
                    if bool(live_variant_override.get("safe_projection", False)) and bool(live_variant_override.get("conf_ok", False)) and bool(live_variant_override.get("gain_ok", False)):
                        selection_rate_diagnostics["live_variant_conf_gain_eligible_candidates"] += 1
                    if (
                        bool(live_variant_override.get("safe_projection", False))
                        and bool(live_variant_override.get("conf_ok", False))
                        and bool(live_variant_override.get("gain_ok", False))
                        and bool(live_variant_override.get("persistence_ok", False))
                    ):
                        selection_rate_diagnostics["live_variant_persistence_eligible_candidates"] += 1
                    if (
                        bool(live_variant_override.get("safe_projection", False))
                        and bool(live_variant_override.get("conf_ok", False))
                        and bool(live_variant_override.get("gain_ok", False))
                        and bool(live_variant_override.get("persistence_ok", False))
                        and bool(live_variant_override.get("recovery_ok", False))
                    ):
                        selection_rate_diagnostics["live_variant_recovery_eligible_candidates"] += 1
                    if (
                        bool(live_variant_override.get("safe_projection", False))
                        and bool(live_variant_override.get("conf_ok", False))
                        and bool(live_variant_override.get("gain_ok", False))
                        and bool(live_variant_override.get("persistence_ok", False))
                        and bool(live_variant_override.get("recovery_ok", False))
                        and bool(live_variant_override.get("projected_ok", False))
                    ):
                        selection_rate_diagnostics["live_variant_quality_eligible_candidates"] += 1
                    if blocked_by_confidence:
                        selection_rate_diagnostics["blocked_by_confidence_gate"] += 1
                    elif blocked_by_gain:
                        selection_rate_diagnostics["blocked_by_gain_gate"] += 1
                    elif blocked_by_projection:
                        selection_rate_diagnostics["blocked_by_projection_veto"] += 1
                    override_reason = str(live_variant_override.get("reason", "variant_inactive"))
                    if blocked_by_projection or override_reason in {"projection_unavailable", "baseline_projection_block", "tight_projection_guard"}:
                        selection_rate_diagnostics["live_variant_projection_guard"] += 1
                    elif blocked_by_confidence or blocked_by_gain or override_reason in {"conf_margin_guard", "gain_margin_guard"}:
                        selection_rate_diagnostics["live_variant_block_conf_gain"] += 1
                    elif override_reason == "persistence_guard":
                        selection_rate_diagnostics["live_variant_persistence_guard"] += 1
                    elif override_reason == "recovery_guard":
                        selection_rate_diagnostics["live_variant_recovery_guard"] += 1
                    elif override_reason == "projected_quality_guard":
                        selection_rate_diagnostics["live_variant_projected_quality_guard"] += 1
                    else:
                        selection_rate_diagnostics["live_variant_block_other"] += 1

                pre_gate_selection_score = float(selection_score)
                pre_gate_selection_score_raw = float(selection_score_raw)
                conf_gap = max(0.0, float(confidence["provisional_threshold"]) - coherence_cal)
                gain_gap = max(0.0, float(gain_signal["provisional_threshold"]) - gain_cal)
                shadow_projection_safe = bool(
                    bool(cfg.shadow_audit_enabled)
                    and status == "blocked"
                    and imp > 0.0
                    and projected_available
                    and pred_projection_bad_prob <= float(cfg.shadow_audit_projection_bad_max)
                )
                shadow_eligible_conf = bool(
                    shadow_projection_safe
                    and (not passed_conf_stage)
                    and conf_gap <= float(cfg.shadow_audit_conf_margin)
                )
                safe_gain_blocked = bool(
                    shadow_projection_safe
                    and passed_conf_stage
                    and (not passed_gain_stage)
                )
                shadow_gain_band_narrow = bool(
                    safe_gain_blocked
                    and gain_gap <= float(cfg.shadow_audit_gain_margin)
                )
                shadow_gain_band_wide = bool(
                    safe_gain_blocked
                    and gain_gap <= float(cfg.shadow_audit_gain_wide_margin)
                )
                shadow_gain_band_wide_only = bool(shadow_gain_band_wide and not shadow_gain_band_narrow)
                shadow_eligible_gain = bool(shadow_gain_band_wide)
                shadow_eligible = bool(shadow_eligible_conf or shadow_eligible_gain)
                shadow_reason = "none"
                if shadow_eligible_conf:
                    shadow_reason = "conf_margin"
                elif shadow_gain_band_narrow:
                    shadow_reason = "gain_band_narrow"
                elif shadow_gain_band_wide_only:
                    shadow_reason = "gain_band_wide"
                shadow_priority = float(pre_gate_selection_score - 0.35 * conf_gap - 0.35 * gain_gap)
                if shadow_gain_band_narrow:
                    selection_rate_diagnostics["safe_gain_blocked_narrow"] += 1
                if shadow_gain_band_wide:
                    selection_rate_diagnostics["safe_gain_blocked_wide"] += 1
                if shadow_gain_band_wide_only:
                    selection_rate_diagnostics["would_qualify_wider_gain_band"] += 1
                if shadow_eligible:
                    shadow_candidate_counts["shadow_candidates_eligible"] += 1
                    if shadow_eligible_conf:
                        selection_rate_diagnostics["near_threshold_blocked_candidates"] += 1
                        shadow_candidate_counts["shadow_candidates_conf_margin"] += 1
                    if shadow_eligible_gain:
                        shadow_candidate_counts["shadow_candidates_gain_margin"] += 1
                    if shadow_gain_band_narrow:
                        selection_rate_diagnostics["near_threshold_blocked_candidates"] += 1
                        shadow_candidate_counts["shadow_candidates_gain_margin_narrow"] += 1
                    if shadow_gain_band_wide_only:
                        shadow_candidate_counts["shadow_candidates_gain_margin_wide_only"] += 1

                if status == "blocked":
                    selection_score = -1e9
                    selection_score_raw = -1e9

                raw_score_matrix[agent_i, proposer_j] = float(selection_score_raw)
                score_matrix[agent_i, proposer_j] = float(selection_score)
                cal_conf_matrix[agent_i, proposer_j] = float(coherence_cal)
                gain_score_matrix[agent_i, proposer_j] = float(gain_cal)
                projected_score_matrix[agent_i, proposer_j] = float(projected_signal.get("calibrated_projected", float("nan")))
                scale_matrix[agent_i, proposer_j] = float(scale)

                detail = {
                    "agent": int(agent_i),
                    "proposer": int(proposer_j),
                    "candidate_id": f"A{int(agent_i)}<=P{int(proposer_j)}",
                    "improvement": float(imp),
                    "local_score": float(local_score),
                    "patch_size": float(psz),
                    "raw_confidence": float(coherence_raw),
                    "calibrated_confidence": float(coherence_cal),
                    "raw_gain": float(gain_raw),
                    "calibrated_gain": float(gain_cal),
                    "raw_projected": float(projected_signal.get("raw_projected", 0.0)),
                    "calibrated_projected": float(projected_signal.get("calibrated_projected", 0.0)),
                    "pred_post_gain": float(projected_signal.get("pred_post_gain", 0.0)),
                    "pred_gain_norm": float(projected_signal.get("pred_gain_norm", 0.0)),
                    "pred_gain_sign_prob": float(projected_signal.get("pred_gain_sign_prob", 0.0)),
                    "pred_gain_bad_prob": float(pred_gain_bad_prob),
                    "pred_goal_bad_prob": float(pred_goal_bad_prob),
                    "pred_projection_error": float(projected_signal.get("pred_projection_error", 0.0)),
                    "pred_projection_explosion_prob": float(projected_signal.get("pred_projection_explosion_prob", 1.0)),
                    "pred_projection_bad_prob": float(pred_projection_bad_prob),
                    "pred_projection_delta": float(projected_signal.get("pred_projection_delta", 0.0)),
                    "pred_instability": float(projected_signal.get("pred_instability", 0.0)),
                    "pred_rollback_risk": float(projected_signal.get("pred_rollback_risk", 1.0)),
                    "pred_rollback_union": float(pred_rollback_union),
                    "pred_rollback_risk_blend": _rollback_blend(
                        float(pred_projection_bad_prob),
                        float(pred_gain_bad_prob),
                        float(pred_goal_bad_prob),
                    ),
                    "pred_uncertainty": float(projected_signal.get("pred_uncertainty", 0.0)),
                    "selection_score_pre_gate": float(pre_gate_selection_score),
                    "selection_score_raw_pre_gate": float(pre_gate_selection_score_raw),
                    "selection_score": float(selection_score),
                    "threshold_used": float(threshold_used),
                    "threshold_mode": str(threshold_mode),
                    "projection_error": float(gain_signal["projection_error"]),
                    "rollback_rate": float(gain_signal["rollback_rate"]),
                    "pred_risk_higher_means_more_dangerous": True,
                    "pred_rollback_union_role": "policy_primary_derived_label",
                    "pred_rollback_risk_role": "diagnostic_only",
                    "rollback_metric_role": "candidate_diagnostic_only",
                    "live_variant_override_applied": bool(live_variant_override_applied),
                    "live_variant_override_reason": str(live_variant_override.get("reason", "variant_inactive")),
                    "live_variant_override_projection_max": float(
                        live_variant_override.get("projection_max", targeted_override_projection_bad_max)
                    ),
                    "shadow_eligible": bool(shadow_eligible),
                    "shadow_reason": str(shadow_reason),
                    "shadow_priority": float(shadow_priority),
                    "shadow_projection_safe": bool(shadow_projection_safe),
                    "shadow_eligible_gain_narrow": bool(shadow_gain_band_narrow),
                    "shadow_eligible_gain_wide": bool(shadow_gain_band_wide),
                    "shadow_conf_gap": float(conf_gap),
                    "shadow_gain_gap": float(gain_gap),
                    "scale": float(scale),
                    "status": status,
                    "reason": reasons[0] if reasons else "candidate admissible",
                    "confidence_components": _format_confidence_components(confidence["components"]),
                    "improvement_components": _format_improvement_components(gain_signal["components"]),
                    "projected_components": _format_projected_components(projected_signal.get("components", {})),
                }
                if bool(cfg.v4_wm_plan_context_trace_enabled):
                    wm_plan_context_rows.append(
                        _build_wm_plan_context_trace_row(
                            cfg=cfg,
                            round_index=int(r),
                            agent_i=int(agent_i),
                            proposer_j=int(proposer_j),
                            forecast_context=forecast_context,
                            projected_signal=projected_signal,
                            pre_gate_selection_score=float(pre_gate_selection_score),
                            pre_gate_selection_score_raw=float(pre_gate_selection_score_raw),
                            shadow_priority=float(shadow_priority),
                            status=str(status),
                        )
                    )
                social_details.append(detail)
                if status == "blocked":
                    adopt_blocked.append(detail)

        pre_adopt_state_dicts = [
            {k: v.detach().cpu().clone() for k, v in agent.state_dict().items()}
            for agent in triad
        ]
        adopted: List[Optional[Dict[str, Any]]] = [None, None, None]
        adopted_meta: List[Dict[str, Any]] = []
        for agent_i in range(3):
            row = [d for d in social_details if d["agent"] == agent_i and d["status"] in {"provisional", "full"}]
            if not row:
                continue
            choice = max(row, key=lambda d: float(d["selection_score"]))
            if not np.isfinite(float(choice["selection_score"])) or float(choice["selection_score"]) <= -1e8:
                continue
            applied_scale = float(choice["scale"]) * (float(cfg.social_conf_provisional_patch_scale) if choice["status"] == "provisional" else 1.0)
            applied_size = _safe_adopt_patch(triad[agent_i], _scale_patch(proposals_out[int(choice["proposer"])], applied_scale))
            choice = dict(choice)
            choice["scale_applied"] = float(applied_scale)
            choice["applied_size"] = float(applied_size)
            adopted[agent_i] = choice
            adopted_meta.append(choice)

        shadow_selected_meta: List[Dict[str, Any]] = []
        for agent_i in range(3):
            blocked_row = [d for d in social_details if d["agent"] == agent_i and bool(d.get("shadow_eligible", False))]
            live_alt_row: List[Dict[str, Any]] = []
            for d in social_details:
                if d["agent"] != agent_i or d["status"] not in {"provisional", "full"}:
                    continue
                if adopted[agent_i] is not None and d["candidate_id"] == adopted[agent_i]["candidate_id"]:
                    continue
                live_alt_row.append(d)
            if blocked_row:
                choice = max(blocked_row, key=lambda d: float(d.get("shadow_priority", d.get("selection_score_pre_gate", -1e9))))
            elif live_alt_row:
                choice = max(live_alt_row, key=lambda d: float(d.get("selection_score", -1e9)))
                shadow_candidate_counts["shadow_candidates_alt_live"] += 1
            else:
                continue
            choice = dict(choice)
            source_shadow_reason = str(choice.get("shadow_reason", "none"))
            choice["live_status"] = str(choice.get("status", "blocked"))
            choice["status"] = "shadow"
            choice["audit_source"] = "shadow"
            if choice["live_status"] == "full":
                choice["scale_applied"] = float(choice["scale"])
                choice["shadow_reason"] = "alt_live_candidate_full"
            elif choice["live_status"] == "provisional":
                choice["scale_applied"] = float(choice["scale"]) * float(cfg.social_conf_provisional_patch_scale)
                choice["shadow_reason"] = "alt_live_candidate_provisional"
            else:
                choice["scale_applied"] = float(choice["scale"]) * float(cfg.shadow_audit_patch_scale)
                if source_shadow_reason in {"gain_band_narrow", "gain_band_wide"}:
                    shadow_candidate_counts["shadow_candidates_gain_band_selected"] += 1
                    selection_rate_diagnostics["shadow_rows_from_gain_band"] += 1
                    if source_shadow_reason == "gain_band_wide":
                        shadow_candidate_counts["shadow_candidates_gain_band_wide_selected"] += 1
                        selection_rate_diagnostics["shadow_rows_from_wider_gain_band"] += 1
            shadow_selected_meta.append(choice)
        shadow_candidate_counts["shadow_candidates_selected"] = int(len(shadow_selected_meta))
        shadow_candidate_counts["shadow_round_selected"] = 1 if shadow_selected_meta else 0
        selection_rate_diagnostics["live_selected_set_present"] = 1 if adopted_meta else 0
        selection_rate_diagnostics["shadow_candidate_available"] = 1 if shadow_selected_meta else 0
        selection_rate_diagnostics["blocked_by_conf_or_gain"] = int(
            selection_rate_diagnostics["blocked_by_confidence_gate"] + selection_rate_diagnostics["blocked_by_gain_gate"]
        )
        if int(selection_rate_diagnostics["live_variant_override_count"]) > 0:
            live_variant_override_rounds.append(int(r))

        shadow_post_avg = float("nan")
        shadow_realized_gain = float("nan")
        shadow_realized_goal_delta = float("nan")
        shadow_realized_projection_error = float("nan")
        shadow_rollback_runtime = False
        shadow_rollback_gain_bad = False
        shadow_rollback_goal_bad = False
        shadow_rollback_projection_bad = False
        shadow_rollback_cause = "none"
        shadow_post_9d_metrics: Dict[str, Any] = {}
        shadow_post_logs: Dict[str, Any] = {}
        if shadow_selected_meta:
            shadow_agents = clone_personal_dummies(triad)
            for shadow_agent in shadow_agents:
                shadow_agent.to(device)
            for choice in shadow_selected_meta:
                agent_i = int(choice["agent"])
                proposer_j = int(choice["proposer"])
                applied_size = _safe_adopt_patch(
                    shadow_agents[agent_i],
                    _scale_patch(proposals_out[proposer_j], float(choice["scale_applied"])),
                )
                choice["applied_size"] = float(applied_size)

            shadow_post_score, shadow_post_logs = eval_group_shadow(
                shadow_agents,
                make_env_for(r, int(cfg.shadow_audit_eval_salt)),
                cfg.steps_dummy,
            )
            shadow_post_avg = coerce_avg(shadow_post_score)
            shadow_post_goal_mse = _last_metric(shadow_post_logs, "goal_mse_latent", 0.0)
            shadow_realized_gain = float(shadow_post_avg - base_avg)
            shadow_realized_goal_delta = (
                float(shadow_post_goal_mse - base_goal_mse)
                if np.isfinite(shadow_post_goal_mse) and np.isfinite(base_goal_mse)
                else 0.0
            )
            shadow_post_9d_metrics = _extract_explicit_9d_metrics(shadow_post_logs)
            shadow_realized_projection_error = float(shadow_post_9d_metrics.get("projection_error", 0.0))
            shadow_rollback_gain_bad = shadow_realized_gain < float(getattr(cfg, "rollback_min_gain", -0.5))
            shadow_rollback_goal_bad = shadow_realized_goal_delta > float(getattr(cfg, "rollback_max_goal_mse_increase", 0.10))
            shadow_rollback_projection_bad = bool(shadow_realized_projection_error > float(cfg.adoption_full_projection_error_max))
            shadow_rollback_runtime = bool(shadow_rollback_gain_bad or shadow_rollback_goal_bad)
            shadow_rollback_cause = _rollback_cause_label(
                shadow_rollback_gain_bad,
                shadow_rollback_goal_bad,
                shadow_rollback_projection_bad,
            )

        post_score, post_logs = eval_group(triad, make_env_for(r, 777), cfg.steps_dummy)
        post_avg = coerce_avg(post_score)
        post_goal_mse = _last_metric(post_logs, "goal_mse_latent", 0.0)
        realized_gain = float(post_avg - base_avg)
        realized_goal_delta = float(post_goal_mse - base_goal_mse) if np.isfinite(post_goal_mse) and np.isfinite(base_goal_mse) else 0.0

        rollback_triggered = False
        rollback_gain_bad = False
        rollback_goal_bad = False
        rollback_pre_restore_gain = float(realized_gain)
        rollback_pre_restore_goal_delta = float(realized_goal_delta)
        if bool(getattr(cfg, "rollback_on_harm", True)) and adopted_meta:
            rollback_gain_bad = realized_gain < float(getattr(cfg, "rollback_min_gain", -0.5))
            rollback_goal_bad = realized_goal_delta > float(getattr(cfg, "rollback_max_goal_mse_increase", 0.10))
            if rollback_gain_bad or rollback_goal_bad:
                rollback_triggered = True
                for agent, state_dict in zip(triad, pre_adopt_state_dicts):
                    agent.load_state_dict(state_dict)
                post_score, post_logs = eval_group(triad, make_env_for(r, 777), cfg.steps_dummy)
                post_avg = coerce_avg(post_score)
                post_goal_mse = _last_metric(post_logs, "goal_mse_latent", 0.0)
                realized_gain = float(post_avg - base_avg)
                realized_goal_delta = float(post_goal_mse - base_goal_mse) if np.isfinite(post_goal_mse) and np.isfinite(base_goal_mse) else 0.0
                realized_gain = min(realized_gain, float(getattr(cfg, "rollback_min_gain", -0.5)) - 0.5)
                realized_goal_delta = max(realized_goal_delta, float(getattr(cfg, "rollback_max_goal_mse_increase", 0.10)))

        post_9d_metrics = _extract_explicit_9d_metrics(post_logs)
        realized_projection_error = float(post_9d_metrics.get("projection_error", 0.0))
        rollback_projection_bad = bool(realized_projection_error > float(cfg.adoption_full_projection_error_max))
        rollback_cause = _rollback_cause_label(rollback_gain_bad, rollback_goal_bad, rollback_projection_bad)
        rollback_target_semantics = {
            "runtime_marker": RUNTIME_MARKER,
            "label_name": "round_selected_set_rollback",
            "label_scope": "round",
            "label_scope_detail": "selected candidate set only",
            "label_horizon_steps": int(cfg.steps_dummy),
            "label_value_meaning": "1 means the selected candidate set crossed one or more cause-specific safety limits after post-run evaluation",
            "pred_risk_higher_means_more_dangerous": True,
            "policy_primary_safety_target": "projection_bad",
            "policy_secondary_safety_target": "rollback_union_derived_from_causes",
            "candidate_to_label_mapping": "candidate-level predicted risk is audited against the round-level rollback label of the selected set",
            "candidate_rows_role": "diagnostic_only",
            "primary_rollback_metric_scope": "round_selected_set_aggregates",
            "rollback_gain_threshold": float(getattr(cfg, "rollback_min_gain", -0.5)),
            "rollback_goal_mse_threshold": float(getattr(cfg, "rollback_max_goal_mse_increase", 0.10)),
            "rollback_projection_threshold": float(cfg.adoption_full_projection_error_max),
        }
        rollback_diagnostic_rows: List[Dict[str, Any]] = []
        for item in adopted_meta:
            row = {
                "round": int(r),
                "candidate_id": str(item["candidate_id"]),
                "agent": int(item["agent"]),
                "proposer": int(item["proposer"]),
                "status": str(item["status"]),
                "selected": True,
                "pred_risk": float(item.get("pred_rollback_risk", 1.0)),
                "pred_risk_blend": float(item.get("pred_rollback_risk_blend", 1.0)),
                "pred_rollback_union": float(item.get("pred_rollback_union", 1.0)),
                "pred_projection_risk": float(item.get("pred_projection_explosion_prob", 1.0)),
                "pred_projection_bad": float(item.get("pred_projection_bad_prob", 1.0)),
                "pred_gain_bad": float(item.get("pred_gain_bad_prob", 1.0)),
                "pred_goal_bad": float(item.get("pred_goal_bad_prob", 1.0)),
                "pred_gain_sign_prob": float(item.get("pred_gain_sign_prob", 0.0)),
                "realized_runtime_rollback": 1.0 if rollback_triggered else 0.0,
                "realized_rollback": 1.0 if (rollback_gain_bad or rollback_goal_bad or rollback_projection_bad) else 0.0,
                "rollback_cause": rollback_cause,
                "rollback_gain_bad": 1.0 if rollback_gain_bad else 0.0,
                "rollback_goal_bad": 1.0 if rollback_goal_bad else 0.0,
                "rollback_projection_bad": 1.0 if rollback_projection_bad else 0.0,
                "rollback_pre_restore_gain": float(rollback_pre_restore_gain),
                "rollback_pre_restore_goal_delta": float(rollback_pre_restore_goal_delta),
                "rollback_label_scope": "round",
                "rollback_label_horizon": int(cfg.steps_dummy),
                "pred_risk_higher_means_more_dangerous": True,
                "rollback_metric_role": "candidate_diagnostic_only",
                "audit_source": "real",
            }
            rollback_diagnostic_rows.append(row)
            rollback_audit_log.append(dict(row))

        round_rollback_audit_row = _build_round_rollback_audit_row(
            round_idx=int(r),
            selected=adopted_meta,
            runtime_rollback_triggered=bool(rollback_triggered),
            rollback_gain_bad=bool(rollback_gain_bad),
            rollback_goal_bad=bool(rollback_goal_bad),
            rollback_projection_bad=bool(rollback_projection_bad),
            rollback_cause=str(rollback_cause),
            realized_gain=float(realized_gain),
            realized_goal_delta=float(realized_goal_delta),
            realized_projection_error=float(realized_projection_error),
            gain_threshold=float(getattr(cfg, "rollback_min_gain", -0.5)),
            goal_threshold=float(getattr(cfg, "rollback_max_goal_mse_increase", 0.10)),
            projection_threshold=float(cfg.adoption_full_projection_error_max),
            horizon_steps=int(cfg.steps_dummy),
        )
        round_rollback_audit_row["audit_source"] = "real"
        rollback_round_audit_log.append(dict(round_rollback_audit_row))

        shadow_target_semantics = dict(rollback_target_semantics)
        shadow_target_semantics["label_name"] = "shadow_selected_set_rollback"
        shadow_target_semantics["label_scope_detail"] = "counterfactual selected candidate set only"
        shadow_target_semantics["audit_source"] = "shadow"
        shadow_target_semantics["world_model_training_effect"] = "disabled_during_shadow_eval"

        shadow_rollback_diagnostic_rows: List[Dict[str, Any]] = []
        for item in shadow_selected_meta:
            row = {
                "round": int(r),
                "candidate_id": str(item["candidate_id"]),
                "agent": int(item["agent"]),
                "proposer": int(item["proposer"]),
                "status": str(item["status"]),
                "selected": True,
                "pred_risk": float(item.get("pred_rollback_risk", 1.0)),
                "pred_risk_blend": float(item.get("pred_rollback_risk_blend", 1.0)),
                "pred_rollback_union": float(item.get("pred_rollback_union", 1.0)),
                "pred_projection_risk": float(item.get("pred_projection_explosion_prob", 1.0)),
                "pred_projection_bad": float(item.get("pred_projection_bad_prob", 1.0)),
                "pred_gain_bad": float(item.get("pred_gain_bad_prob", 1.0)),
                "pred_goal_bad": float(item.get("pred_goal_bad_prob", 1.0)),
                "pred_gain_sign_prob": float(item.get("pred_gain_sign_prob", 0.0)),
                "realized_runtime_rollback": 1.0 if shadow_rollback_runtime else 0.0,
                "realized_rollback": 1.0 if (shadow_rollback_gain_bad or shadow_rollback_goal_bad or shadow_rollback_projection_bad) else 0.0,
                "rollback_cause": str(shadow_rollback_cause),
                "rollback_gain_bad": 1.0 if shadow_rollback_gain_bad else 0.0,
                "rollback_goal_bad": 1.0 if shadow_rollback_goal_bad else 0.0,
                "rollback_projection_bad": 1.0 if shadow_rollback_projection_bad else 0.0,
                "rollback_pre_restore_gain": float(shadow_realized_gain),
                "rollback_pre_restore_goal_delta": float(shadow_realized_goal_delta),
                "rollback_label_scope": "round",
                "rollback_label_horizon": int(cfg.steps_dummy),
                "pred_risk_higher_means_more_dangerous": True,
                "rollback_metric_role": "candidate_diagnostic_only",
                "audit_source": "shadow",
            }
            shadow_rollback_diagnostic_rows.append(row)
            shadow_rollback_audit_log.append(dict(row))

        shadow_round_rollback_audit_row = _build_round_rollback_audit_row(
            round_idx=int(r),
            selected=shadow_selected_meta,
            runtime_rollback_triggered=bool(shadow_rollback_runtime),
            rollback_gain_bad=bool(shadow_rollback_gain_bad),
            rollback_goal_bad=bool(shadow_rollback_goal_bad),
            rollback_projection_bad=bool(shadow_rollback_projection_bad),
            rollback_cause=str(shadow_rollback_cause),
            realized_gain=float(shadow_realized_gain if np.isfinite(shadow_realized_gain) else 0.0),
            realized_goal_delta=float(shadow_realized_goal_delta if np.isfinite(shadow_realized_goal_delta) else 0.0),
            realized_projection_error=float(shadow_realized_projection_error if np.isfinite(shadow_realized_projection_error) else 0.0),
            gain_threshold=float(getattr(cfg, "rollback_min_gain", -0.5)),
            goal_threshold=float(getattr(cfg, "rollback_max_goal_mse_increase", 0.10)),
            projection_threshold=float(cfg.adoption_full_projection_error_max),
            horizon_steps=int(cfg.steps_dummy),
        )
        shadow_round_rollback_audit_row["audit_source"] = "shadow"
        shadow_round_rollback_audit_row["counterfactual"] = True
        shadow_rollback_round_audit_log.append(dict(shadow_round_rollback_audit_row))

        round_projection_calibration = _aggregate_round_projection_forecast(adopted_meta)
        round_projection_calibration["realized_gain"] = float(realized_gain)
        round_projection_calibration["realized_gain_norm"] = float(_normalize_gain_target(realized_gain, realized_gain_history))
        round_projection_calibration["realized_gain_sign"] = 1.0 if realized_gain > 0.0 else 0.0
        round_projection_calibration["realized_projection_error"] = float(realized_projection_error)
        round_projection_calibration["realized_projection_explosion"] = 1.0 if rollback_projection_bad else 0.0
        round_projection_calibration["rollback_triggered"] = 1.0 if rollback_triggered else 0.0
        round_projection_calibration["pred_projection_bad_prob"] = float(round_projection_calibration.get("pred_projection_bad_prob", float("nan")))
        round_projection_calibration["pred_rollback_union"] = float(round_projection_calibration.get("pred_rollback_union", float("nan")))
        round_projection_calibration["selected_pred_risk_max"] = float(round_rollback_audit_row.get("selected_pred_risk_max", float("nan")))
        round_projection_calibration["selected_pred_risk_mean"] = float(round_rollback_audit_row.get("selected_pred_risk_mean", float("nan")))
        round_projection_calibration["selected_pred_risk_sel_weighted_mean"] = float(round_rollback_audit_row.get("selected_pred_risk_sel_weighted_mean", float("nan")))
        round_projection_calibration["selected_pred_risk_blend"] = float(round_rollback_audit_row.get("selected_pred_risk_blend", float("nan")))
        round_projection_calibration["selected_pred_gain_bad_score"] = float(round_rollback_audit_row.get("selected_pred_gain_bad_score", float("nan")))
        round_projection_calibration["selected_pred_projection_bad_score"] = float(round_rollback_audit_row.get("selected_pred_projection_bad_score", float("nan")))

        shadow_round_projection_calibration = _aggregate_round_projection_forecast(shadow_selected_meta)
        shadow_round_projection_calibration["realized_gain"] = float(shadow_realized_gain)
        shadow_round_projection_calibration["realized_gain_norm"] = float(_normalize_gain_target(shadow_realized_gain, realized_gain_history))
        shadow_round_projection_calibration["realized_gain_sign"] = 1.0 if shadow_realized_gain > 0.0 else 0.0
        shadow_round_projection_calibration["realized_projection_error"] = float(shadow_realized_projection_error)
        shadow_round_projection_calibration["realized_projection_explosion"] = 1.0 if shadow_rollback_projection_bad else 0.0
        shadow_round_projection_calibration["rollback_triggered"] = 1.0 if shadow_rollback_runtime else 0.0
        shadow_round_projection_calibration["pred_projection_bad_prob"] = float(shadow_round_projection_calibration.get("pred_projection_bad_prob", float("nan")))
        shadow_round_projection_calibration["pred_rollback_union"] = float(shadow_round_projection_calibration.get("pred_rollback_union", float("nan")))
        shadow_round_projection_calibration["selected_pred_risk_max"] = float(shadow_round_rollback_audit_row.get("selected_pred_risk_max", float("nan")))
        shadow_round_projection_calibration["selected_pred_risk_mean"] = float(shadow_round_rollback_audit_row.get("selected_pred_risk_mean", float("nan")))
        shadow_round_projection_calibration["selected_pred_risk_sel_weighted_mean"] = float(shadow_round_rollback_audit_row.get("selected_pred_risk_sel_weighted_mean", float("nan")))
        shadow_round_projection_calibration["selected_pred_risk_blend"] = float(shadow_round_rollback_audit_row.get("selected_pred_risk_blend", float("nan")))
        shadow_round_projection_calibration["selected_pred_gain_bad_score"] = float(shadow_round_rollback_audit_row.get("selected_pred_gain_bad_score", float("nan")))
        shadow_round_projection_calibration["selected_pred_projection_bad_score"] = float(shadow_round_rollback_audit_row.get("selected_pred_projection_bad_score", float("nan")))

        if np.isfinite(float(round_projection_calibration.get("pred_gain_norm_mean", float("nan")))):
            projected_gain_history.append(float(round_projection_calibration.get("pred_gain_norm_mean", 0.0)))
            projected_gain_sign_history.append(float(round_projection_calibration.get("pred_gain_sign_prob", 0.0)))
            projected_projection_history.append(float(round_projection_calibration.get("pred_projection_error_mean", 0.0)))
            projected_projection_risk_history.append(float(round_projection_calibration.get("pred_projection_explosion_prob", 0.0)))
            projected_risk_history.append(float(round_projection_calibration.get("pred_rollback_risk_blend", 0.0)))
            projected_union_history.append(float(round_projection_calibration.get("pred_rollback_union", 0.0)))
            realized_gain_norm_history.append(float(round_projection_calibration["realized_gain_norm"]))
            realized_gain_sign_history.append(float(round_projection_calibration["realized_gain_sign"]))
            realized_projection_history.append(float(round_projection_calibration["realized_projection_error"]))
            realized_projection_explosion_history.append(float(round_projection_calibration["realized_projection_explosion"]))
            realized_rollback_history.append(float(round_projection_calibration["rollback_triggered"]))

        if np.isfinite(float(shadow_round_projection_calibration.get("pred_gain_norm_mean", float("nan")))):
            shadow_projected_gain_history.append(float(shadow_round_projection_calibration.get("pred_gain_norm_mean", 0.0)))
            shadow_projected_gain_sign_history.append(float(shadow_round_projection_calibration.get("pred_gain_sign_prob", 0.0)))
            shadow_projected_projection_history.append(float(shadow_round_projection_calibration.get("pred_projection_error_mean", 0.0)))
            shadow_projected_projection_risk_history.append(float(shadow_round_projection_calibration.get("pred_projection_explosion_prob", 0.0)))
            shadow_projected_risk_history.append(float(shadow_round_projection_calibration.get("pred_rollback_risk_blend", 0.0)))
            shadow_projected_union_history.append(float(shadow_round_projection_calibration.get("pred_rollback_union", 0.0)))
            shadow_realized_gain_norm_history.append(float(shadow_round_projection_calibration["realized_gain_norm"]))
            shadow_realized_gain_sign_history.append(float(shadow_round_projection_calibration["realized_gain_sign"]))
            shadow_realized_projection_history.append(float(shadow_round_projection_calibration["realized_projection_error"]))
            shadow_realized_projection_explosion_history.append(float(shadow_round_projection_calibration["realized_projection_explosion"]))
            shadow_realized_rollback_history.append(float(shadow_round_projection_calibration["rollback_triggered"]))

        projection_calibration_metrics = _compute_projection_calibration_metrics_from_histories(
            predicted_gain=projected_gain_history,
            predicted_gain_sign=projected_gain_sign_history,
            predicted_projection=projected_projection_history,
            predicted_projection_risk=projected_projection_risk_history,
            predicted_risk_diag=projected_risk_history,
            predicted_union=projected_union_history,
            realized_gain_norm=realized_gain_norm_history,
            realized_gain_sign=realized_gain_sign_history,
            realized_projection=realized_projection_history,
            realized_projection_explosion=realized_projection_explosion_history,
            realized_rollback=realized_rollback_history,
        )
        rollback_round_metrics = _compute_round_rollback_metrics(rollback_round_audit_log)
        projection_calibration_metrics["corr_pred_risk_realized_rollback"] = float(
            rollback_round_metrics.get("corr_selected_pred_risk_blend_realized_rollback", float("nan"))
        )
        projection_calibration_metrics["corr_pred_union_realized_rollback"] = float(
            rollback_round_metrics.get("corr_selected_p_rollback_union_realized_rollback", float("nan"))
        )
        projection_calibration_metrics["corr_pred_projection_bad_realized_projection_bad"] = float(
            rollback_round_metrics.get("corr_selected_p_projection_bad_realized_projection_bad", float("nan"))
        )

        shadow_projection_calibration_metrics = _compute_projection_calibration_metrics_from_histories(
            predicted_gain=shadow_projected_gain_history,
            predicted_gain_sign=shadow_projected_gain_sign_history,
            predicted_projection=shadow_projected_projection_history,
            predicted_projection_risk=shadow_projected_projection_risk_history,
            predicted_risk_diag=shadow_projected_risk_history,
            predicted_union=shadow_projected_union_history,
            realized_gain_norm=shadow_realized_gain_norm_history,
            realized_gain_sign=shadow_realized_gain_sign_history,
            realized_projection=shadow_realized_projection_history,
            realized_projection_explosion=shadow_realized_projection_explosion_history,
            realized_rollback=shadow_realized_rollback_history,
        )
        shadow_rollback_round_metrics = _compute_round_rollback_metrics(shadow_rollback_round_audit_log)
        shadow_projection_calibration_metrics["corr_pred_risk_realized_rollback"] = float(
            shadow_rollback_round_metrics.get("corr_selected_pred_risk_blend_realized_rollback", float("nan"))
        )
        shadow_projection_calibration_metrics["corr_pred_union_realized_rollback"] = float(
            shadow_rollback_round_metrics.get("corr_selected_p_rollback_union_realized_rollback", float("nan"))
        )
        shadow_projection_calibration_metrics["corr_pred_projection_bad_realized_projection_bad"] = float(
            shadow_rollback_round_metrics.get("corr_selected_p_projection_bad_realized_projection_bad", float("nan"))
        )

        exploratory_projection_calibration_metrics = _compute_projection_calibration_metrics_from_histories(
            predicted_gain=projected_gain_history + shadow_projected_gain_history,
            predicted_gain_sign=projected_gain_sign_history + shadow_projected_gain_sign_history,
            predicted_projection=projected_projection_history + shadow_projected_projection_history,
            predicted_projection_risk=projected_projection_risk_history + shadow_projected_projection_risk_history,
            predicted_risk_diag=projected_risk_history + shadow_projected_risk_history,
            predicted_union=projected_union_history + shadow_projected_union_history,
            realized_gain_norm=realized_gain_norm_history + shadow_realized_gain_norm_history,
            realized_gain_sign=realized_gain_sign_history + shadow_realized_gain_sign_history,
            realized_projection=realized_projection_history + shadow_realized_projection_history,
            realized_projection_explosion=realized_projection_explosion_history + shadow_realized_projection_explosion_history,
            realized_rollback=realized_rollback_history + shadow_realized_rollback_history,
        )
        exploratory_rollback_round_metrics = _compute_round_rollback_metrics(
            list(rollback_round_audit_log) + list(shadow_rollback_round_audit_log)
        )
        exploratory_projection_calibration_metrics["corr_pred_risk_realized_rollback"] = float(
            exploratory_rollback_round_metrics.get("corr_selected_pred_risk_blend_realized_rollback", float("nan"))
        )
        exploratory_projection_calibration_metrics["corr_pred_union_realized_rollback"] = float(
            exploratory_rollback_round_metrics.get("corr_selected_p_rollback_union_realized_rollback", float("nan"))
        )
        exploratory_projection_calibration_metrics["corr_pred_projection_bad_realized_projection_bad"] = float(
            exploratory_rollback_round_metrics.get("corr_selected_p_projection_bad_realized_projection_bad", float("nan"))
        )

        live_selected_round_flags.append(float(selection_rate_diagnostics["live_selected_set_present"]))
        shadow_selected_round_flags.append(float(shadow_candidate_counts["shadow_round_selected"]))
        combined_selected_round_flags.append(
            1.0 if (selection_rate_diagnostics["live_selected_set_present"] or shadow_candidate_counts["shadow_round_selected"]) else 0.0
        )
        shadow_available_round_flags.append(float(selection_rate_diagnostics["shadow_candidate_available"]))
        near_threshold_blocked_history.append(float(selection_rate_diagnostics["near_threshold_blocked_candidates"]))
        blocked_projection_veto_history.append(float(selection_rate_diagnostics["blocked_by_projection_veto"]))
        blocked_confidence_gate_history.append(float(selection_rate_diagnostics["blocked_by_confidence_gate"]))
        blocked_gain_gate_history.append(float(selection_rate_diagnostics["blocked_by_gain_gate"]))
        live_variant_baseline_rejected_history.append(float(selection_rate_diagnostics["live_variant_baseline_rejected_candidates"]))
        live_variant_projection_eligible_history.append(float(selection_rate_diagnostics["live_variant_projection_eligible_candidates"]))
        live_variant_conf_gain_eligible_history.append(float(selection_rate_diagnostics["live_variant_conf_gain_eligible_candidates"]))
        live_variant_persistence_eligible_history.append(float(selection_rate_diagnostics["live_variant_persistence_eligible_candidates"]))
        live_variant_recovery_eligible_history.append(float(selection_rate_diagnostics["live_variant_recovery_eligible_candidates"]))
        live_variant_quality_eligible_history.append(float(selection_rate_diagnostics["live_variant_quality_eligible_candidates"]))
        live_variant_override_history.append(float(selection_rate_diagnostics["live_variant_override_count"]))
        live_variant_block_projection_history.append(float(selection_rate_diagnostics["live_variant_projection_guard"]))
        live_variant_block_persistence_history.append(float(selection_rate_diagnostics["live_variant_persistence_guard"]))
        live_variant_block_recovery_history.append(float(selection_rate_diagnostics["live_variant_recovery_guard"]))
        live_variant_block_conf_gain_history.append(float(selection_rate_diagnostics["live_variant_block_conf_gain"]))
        live_variant_projected_quality_guard_history.append(float(selection_rate_diagnostics["live_variant_projected_quality_guard"]))
        live_variant_block_other_history.append(float(selection_rate_diagnostics["live_variant_block_other"]))
        safe_gain_blocked_narrow_history.append(float(selection_rate_diagnostics["safe_gain_blocked_narrow"]))
        safe_gain_blocked_wide_history.append(float(selection_rate_diagnostics["safe_gain_blocked_wide"]))
        wider_gain_band_only_history.append(float(selection_rate_diagnostics["would_qualify_wider_gain_band"]))
        shadow_rows_from_gain_band_history.append(float(selection_rate_diagnostics["shadow_rows_from_gain_band"]))
        shadow_rows_from_wider_gain_band_history.append(float(selection_rate_diagnostics["shadow_rows_from_wider_gain_band"]))

        rounds_seen = max(1, len(live_selected_round_flags))
        safe_gain_blocked_narrow_arr = np.asarray(safe_gain_blocked_narrow_history, dtype=np.float64)
        safe_gain_blocked_wide_arr = np.asarray(safe_gain_blocked_wide_history, dtype=np.float64)
        wider_gain_band_only_arr = np.asarray(wider_gain_band_only_history, dtype=np.float64)
        shadow_rows_from_gain_band_arr = np.asarray(shadow_rows_from_gain_band_history, dtype=np.float64)
        shadow_rows_from_wider_gain_band_arr = np.asarray(shadow_rows_from_wider_gain_band_history, dtype=np.float64)
        live_variant_baseline_rejected_arr = np.asarray(live_variant_baseline_rejected_history, dtype=np.float64)
        live_variant_projection_eligible_arr = np.asarray(live_variant_projection_eligible_history, dtype=np.float64)
        live_variant_conf_gain_eligible_arr = np.asarray(live_variant_conf_gain_eligible_history, dtype=np.float64)
        live_variant_persistence_eligible_arr = np.asarray(live_variant_persistence_eligible_history, dtype=np.float64)
        live_variant_recovery_eligible_arr = np.asarray(live_variant_recovery_eligible_history, dtype=np.float64)
        live_variant_quality_eligible_arr = np.asarray(live_variant_quality_eligible_history, dtype=np.float64)
        live_variant_override_arr = np.asarray(live_variant_override_history, dtype=np.float64)
        live_variant_block_projection_arr = np.asarray(live_variant_block_projection_history, dtype=np.float64)
        live_variant_block_persistence_arr = np.asarray(live_variant_block_persistence_history, dtype=np.float64)
        live_variant_block_recovery_arr = np.asarray(live_variant_block_recovery_history, dtype=np.float64)
        live_variant_block_conf_gain_arr = np.asarray(live_variant_block_conf_gain_history, dtype=np.float64)
        live_variant_projected_quality_arr = np.asarray(live_variant_projected_quality_guard_history, dtype=np.float64)
        live_variant_block_other_arr = np.asarray(live_variant_block_other_history, dtype=np.float64)
        live_variant_block_reason_counts = {
            "projection_guard": int(np.sum(live_variant_block_projection_arr)),
            "persistence_guard": int(np.sum(live_variant_block_persistence_arr)),
            "recovery_guard": int(np.sum(live_variant_block_recovery_arr)),
            "confidence_gain_precondition": int(np.sum(live_variant_block_conf_gain_arr)),
            "other_eligibility_failure": int(np.sum(live_variant_projected_quality_arr) + np.sum(live_variant_block_other_arr)),
        }
        dominant_override_block_reason = "none"
        dominant_override_block_count = max(live_variant_block_reason_counts.values()) if live_variant_block_reason_counts else 0
        if dominant_override_block_count > 0:
            dominant_override_block_reason = max(
                live_variant_block_reason_counts.items(),
                key=lambda item: int(item[1]),
            )[0]
        selection_rate_summary = {
            "rounds_total": int(rounds_seen),
            "live_row_count": int(np.sum(np.asarray(live_selected_round_flags, dtype=np.float64))),
            "shadow_row_count": int(np.sum(np.asarray(shadow_selected_round_flags, dtype=np.float64))),
            "combined_row_count": int(np.sum(np.asarray(combined_selected_round_flags, dtype=np.float64))),
            "shadow_candidate_available_count": int(np.sum(np.asarray(shadow_available_round_flags, dtype=np.float64))),
            "live_row_rate_pct": float(100.0 * np.mean(np.asarray(live_selected_round_flags, dtype=np.float64))),
            "shadow_row_rate_pct": float(100.0 * np.mean(np.asarray(shadow_selected_round_flags, dtype=np.float64))),
            "combined_row_rate_pct": float(100.0 * np.mean(np.asarray(combined_selected_round_flags, dtype=np.float64))),
            "shadow_candidate_available_rate_pct": float(100.0 * np.mean(np.asarray(shadow_available_round_flags, dtype=np.float64))),
            "avg_near_threshold_blocked": float(np.mean(np.asarray(near_threshold_blocked_history, dtype=np.float64))),
            "avg_blocked_by_projection_veto": float(np.mean(np.asarray(blocked_projection_veto_history, dtype=np.float64))),
            "avg_blocked_by_confidence_gate": float(np.mean(np.asarray(blocked_confidence_gate_history, dtype=np.float64))),
            "avg_blocked_by_gain_gate": float(np.mean(np.asarray(blocked_gain_gate_history, dtype=np.float64))),
            "live_variant_baseline_rejected_total": int(np.sum(live_variant_baseline_rejected_arr)),
            "live_variant_projection_eligible_total": int(np.sum(live_variant_projection_eligible_arr)),
            "live_variant_conf_gain_eligible_total": int(np.sum(live_variant_conf_gain_eligible_arr)),
            "live_variant_persistence_eligible_total": int(np.sum(live_variant_persistence_eligible_arr)),
            "live_variant_recovery_eligible_total": int(np.sum(live_variant_recovery_eligible_arr)),
            "live_variant_quality_eligible_total": int(np.sum(live_variant_quality_eligible_arr)),
            "live_variant_override_total": int(np.sum(live_variant_override_arr)),
            "live_variant_block_reason_counts": dict(live_variant_block_reason_counts),
            "live_variant_dominant_block_reason": str(dominant_override_block_reason),
            "live_variant_dominant_block_count": int(dominant_override_block_count),
            "avg_live_variant_baseline_rejected": float(np.mean(live_variant_baseline_rejected_arr)),
            "avg_live_variant_projection_eligible": float(np.mean(live_variant_projection_eligible_arr)),
            "avg_live_variant_conf_gain_eligible": float(np.mean(live_variant_conf_gain_eligible_arr)),
            "avg_live_variant_persistence_eligible": float(np.mean(live_variant_persistence_eligible_arr)),
            "avg_live_variant_recovery_eligible": float(np.mean(live_variant_recovery_eligible_arr)),
            "avg_live_variant_quality_eligible": float(np.mean(live_variant_quality_eligible_arr)),
            "avg_live_variant_override": float(np.mean(live_variant_override_arr)),
            "live_variant_override_round_count": int(np.sum((live_variant_override_arr > 0.0).astype(np.float64))),
            "live_variant_override_round_rate_pct": float(100.0 * np.mean((live_variant_override_arr > 0.0).astype(np.float64))),
            "live_variant_override_rounds": list(live_variant_override_rounds[-32:]),
            "safe_gain_blocked_narrow_total": int(np.sum(safe_gain_blocked_narrow_arr)),
            "safe_gain_blocked_wide_total": int(np.sum(safe_gain_blocked_wide_arr)),
            "would_qualify_wider_gain_band_total": int(np.sum(wider_gain_band_only_arr)),
            "shadow_rows_from_gain_band_total": int(np.sum(shadow_rows_from_gain_band_arr)),
            "shadow_rows_from_wider_gain_band_total": int(np.sum(shadow_rows_from_wider_gain_band_arr)),
            "avg_safe_gain_blocked_narrow": float(np.mean(safe_gain_blocked_narrow_arr)),
            "avg_safe_gain_blocked_wide": float(np.mean(safe_gain_blocked_wide_arr)),
            "avg_would_qualify_wider_gain_band": float(np.mean(wider_gain_band_only_arr)),
            "avg_shadow_rows_from_gain_band": float(np.mean(shadow_rows_from_gain_band_arr)),
            "avg_shadow_rows_from_wider_gain_band": float(np.mean(shadow_rows_from_wider_gain_band_arr)),
            "safe_gain_blocked_narrow_round_count": int(np.sum((safe_gain_blocked_narrow_arr > 0.0).astype(np.float64))),
            "safe_gain_blocked_wide_round_count": int(np.sum((safe_gain_blocked_wide_arr > 0.0).astype(np.float64))),
            "would_qualify_wider_gain_band_round_count": int(np.sum((wider_gain_band_only_arr > 0.0).astype(np.float64))),
            "shadow_rows_from_gain_band_round_count": int(np.sum((shadow_rows_from_gain_band_arr > 0.0).astype(np.float64))),
            "shadow_rows_from_wider_gain_band_round_count": int(np.sum((shadow_rows_from_wider_gain_band_arr > 0.0).astype(np.float64))),
            "safe_gain_blocked_narrow_round_rate_pct": float(100.0 * np.mean((safe_gain_blocked_narrow_arr > 0.0).astype(np.float64))),
            "safe_gain_blocked_wide_round_rate_pct": float(100.0 * np.mean((safe_gain_blocked_wide_arr > 0.0).astype(np.float64))),
            "would_qualify_wider_gain_band_round_rate_pct": float(100.0 * np.mean((wider_gain_band_only_arr > 0.0).astype(np.float64))),
            "shadow_rows_from_gain_band_round_rate_pct": float(100.0 * np.mean((shadow_rows_from_gain_band_arr > 0.0).astype(np.float64))),
            "shadow_rows_from_wider_gain_band_round_rate_pct": float(100.0 * np.mean((shadow_rows_from_wider_gain_band_arr > 0.0).astype(np.float64))),
        }

        touched = {int(item["proposer"]) for item in adopted_meta}
        for proposer_j in range(3):
            proposer_recent_realized[proposer_j] *= 0.90
            proposer_recent_goal[proposer_j] *= 0.90
            instability_state[proposer_j] *= 0.85
            if proposer_j not in touched:
                continue
            proposer_rollback_trials[proposer_j] += 1.0
            if rollback_triggered:
                proposer_rollback_hits[proposer_j] += 1.0
            proposer_rollback_rate[proposer_j] = float(
                proposer_rollback_hits[proposer_j] / max(proposer_rollback_trials[proposer_j], 1.0)
            )
            reward = float(realized_gain - 0.35 * max(0.0, realized_goal_delta))
            proposer_recent_realized[proposer_j] = 0.75 * proposer_recent_realized[proposer_j] + 0.25 * reward
            proposer_recent_goal[proposer_j] = 0.75 * proposer_recent_goal[proposer_j] + 0.25 * realized_goal_delta
            proposer_credit[proposer_j] = (
                float(cfg.adoption_realized_reward_decay) * proposer_credit[proposer_j]
                + (1.0 - float(cfg.adoption_realized_reward_decay)) * reward
            )
            proposer_credit[proposer_j] = float(np.clip(proposer_credit[proposer_j], -50.0, 50.0))
            if reward < 0.0:
                instability_state[proposer_j] = min(1.0, instability_state[proposer_j] + 0.25)
            if reward <= float(cfg.adoption_negative_cooldown_trigger):
                proposer_cooldown[proposer_j] = max(proposer_cooldown[proposer_j], int(cfg.adoption_cooldown_rounds))

        for agent_i in range(3):
            choice = adopted[agent_i]
            if choice is None or rollback_triggered:
                provisional_evidence[agent_i] *= float(cfg.social_conf_provisional_decay)
                if provisional_evidence[agent_i] < float(cfg.social_conf_provisional_release):
                    provisional_owner[agent_i] = -1
                    provisional_rounds[agent_i] = 0
                    provisional_evidence[agent_i] = 0.0
                continue
            if choice["status"] == "provisional":
                proposer_j = int(choice["proposer"])
                if int(provisional_owner[agent_i]) == proposer_j:
                    provisional_rounds[agent_i] += 1
                else:
                    provisional_owner[agent_i] = proposer_j
                    provisional_rounds[agent_i] = 1
                provisional_evidence[agent_i] = float(
                    np.clip(
                        float(cfg.social_conf_provisional_decay) * float(provisional_evidence[agent_i])
                        + 0.35 * float(choice["calibrated_confidence"])
                        + 0.25 * float(choice["calibrated_gain"])
                        + 0.20 * float(choice.get("pred_gain_sign_prob", 0.0))
                        - 0.20 * float(choice.get("pred_projection_bad_prob", 0.0))
                        - 0.10 * float(choice.get("pred_rollback_union", 0.0)),
                        0.0,
                        1.0,
                    )
                )
            else:
                provisional_owner[agent_i] = -1
                provisional_rounds[agent_i] = 0
                provisional_evidence[agent_i] = 0.0

        realized_gain_history.append(float(realized_gain))
        finite_self_scores = np.nan_to_num(self_diag_scores.astype(np.float64), nan=-1e9, posinf=-1e9, neginf=-1e9)
        self_best_agent = int(np.argmax(finite_self_scores)) if finite_self_scores.size > 0 else -1
        self_event_any = bool(np.any(self_diag_patch_sizes > 0.0))
        self_adopted_any = bool(len(self_adopted) > 0)

        for idx in range(3):
            self_score_history[idx].append(float(self_diag_scores[idx]))
            if self_event_any and self_best_agent == idx:
                self_best_streak[idx] += 1
                self_best_count[idx] += 1
            else:
                self_best_streak[idx] = 0

        if prev_self_best_agent is not None and self_best_agent >= 0:
            self_same_agent_recurrence_trials[self_best_agent] += 1
            if self_best_agent == prev_self_best_agent:
                self_same_agent_recurrence_hits[self_best_agent] += 1
        if self_best_agent >= 0:
            prev_self_best_agent = self_best_agent
            self_best_score_history.append(float(self_diag_scores[self_best_agent]))
            self_best_pressure_history.append(float(self_diag_pressures[self_best_agent]))
            self_best_patch_size_history.append(float(self_diag_patch_sizes[self_best_agent]))
            if self_event_any:
                self_event_gain_history.append(float(realized_gain))

        self_event_any_history.append(1.0 if self_event_any else 0.0)
        self_adopted_any_history.append(1.0 if self_adopted_any else 0.0)
        self_score_mavg = np.asarray([_safe_mean_arr(self_score_history[i][-4:], default=0.0) for i in range(3)], dtype=np.float32)
        self_score_var = np.asarray([_safe_var_arr(self_score_history[i][-8:], default=0.0) for i in range(3)], dtype=np.float32)
        self_recurrence_rate = np.asarray(
            [
                float(self_same_agent_recurrence_hits[i]) / max(float(self_same_agent_recurrence_trials[i]), 1.0)
                for i in range(3)
            ],
            dtype=np.float32,
        )
        self_recurrence_global = float(np.sum(self_same_agent_recurrence_hits) / max(float(np.sum(self_same_agent_recurrence_trials)), 1.0))

        gains_arr = np.asarray(realized_gain_history, dtype=np.float64)
        adopted_mask = np.asarray(self_adopted_any_history, dtype=np.float64)
        signal_mask = np.asarray(self_event_any_history, dtype=np.float64)
        self_event_correlations = {
            "mean_gain_when_self": _safe_mean_arr(gains_arr[adopted_mask > 0.5], default=float("nan")) if gains_arr.size > 0 else float("nan"),
            "mean_gain_without_self": _safe_mean_arr(gains_arr[adopted_mask <= 0.5], default=float("nan")) if gains_arr.size > 0 else float("nan"),
            "mean_gain_when_self_signal": _safe_mean_arr(gains_arr[signal_mask > 0.5], default=float("nan")) if gains_arr.size > 0 else float("nan"),
            "mean_gain_without_self_signal": _safe_mean_arr(gains_arr[signal_mask <= 0.5], default=float("nan")) if gains_arr.size > 0 else float("nan"),
            "corr_self_score_gain": _safe_corr(self_best_score_history, self_event_gain_history),
            "corr_self_pressure_gain": _safe_corr(self_best_pressure_history, self_event_gain_history),
            "corr_self_patch_size_gain": _safe_corr(self_best_patch_size_history, self_event_gain_history),
            "corr_self_adopted_gain": _safe_corr(self_adopted_any_history, realized_gain_history),
        }

        wm_loss = _safe_float(_last_metric(post_logs, "wm_loss", float("nan")))
        wm_recon = _safe_float(_last_metric(post_logs, "wm_recon", float("nan")))
        wm_kl = _safe_float(_last_metric(post_logs, "wm_kl", float("nan")))

        adopted_self_agents = {item[0] for item in self_adopted}
        for idx, agent in enumerate(triad):
            agent.record_self_improvement_outcome(
                dummy_improvement=float(self_diag_improvements[idx]),
                dummy_score=float(self_diag_scores[idx]),
                adopted=bool(idx in adopted_self_agents),
                patch_size=float(self_diag_patch_sizes[idx]),
                realized_gain=float(realized_gain),
                rolled_back=bool(rollback_triggered),
            )

        if cfg.verbose:
            self_str = ", ".join(
                f"A{idx}(d={imp:+.3f}, score={score:+.3f}, sz={psz:.4f}, p={pressure:.2f})"
                for idx, imp, score, psz, _adopt_score, pressure in self_adopted
            ) or "none"
            self_block_str = "; ".join(
                f"A{idx}: {reason} (d={imp:+.3f}, score={score:+.3f}, sz={psz:.4f}, p={pressure:.2f})"
                for idx, reason, imp, score, psz, pressure in self_blocked
            ) or "none"
            adopt_str = "; ".join(
                f"A{item['agent']}<=P{item['proposer']}: conf_raw={item['raw_confidence']:+.3f} conf_cal={item['calibrated_confidence']:.3f} "
                f"gain_raw={item['raw_gain']:+.3f} gain_cal={item['calibrated_gain']:.3f} proj_raw={item['raw_projected']:+.3f} "
                f"proj_cal={item['calibrated_projected']:.3f} sel={item['selection_score']:.3f} thresh={item['threshold_used']:.3f} "
                f"mode={item['threshold_mode']} proj_err={item['projection_error']:.3f} rollback_hist={item['rollback_rate']:.2f} "
                f"pred_gain={item['pred_post_gain']:+.3f} pred_proj={item['pred_projection_error']:.3f} "
                f"p_proj_bad={item['pred_projection_bad_prob']:.3f} p_union={item['pred_rollback_union']:.3f} "
                f"risk_diag={item['pred_rollback_risk']:.3f} "
                f"{item['confidence_components']} {item['improvement_components']} {item['projected_components']} => {item['status']}"
                for item in adopted_meta
            ) or "none"
            if rollback_triggered and adopt_str != "none":
                adopt_str = "ROLLBACK[" + adopt_str + "]"
            adopt_block_str = "; ".join(
                f"A{item['agent']}<=P{item['proposer']}: {item['reason']} "
                f"(conf={item['calibrated_confidence']:.3f}, gain={item['calibrated_gain']:.3f}, proj={item['calibrated_projected']:.3f})"
                for item in adopt_blocked
            ) or "none"
            print(
                f"Round {r:03d} | base_avg={base_avg:.3f} post_avg={post_avg:.3f} | "
                f"wm(loss={wm_loss:.4f}, recon={wm_recon:.4f}, kl={wm_kl:.4f}) | self: {self_str} | adopt: {adopt_str}"
            )
            print(f"  self blocked: {self_block_str}")
            print(f"  adopt blocked: {adopt_block_str}")
            print(
                f"  self persistence: streak={self_best_streak.tolist()} ma={np.round(self_score_mavg, 3).tolist()} "
                f"var={np.round(self_score_var, 4).tolist()} recur={np.round(self_recurrence_rate, 3).tolist()} recur_global={self_recurrence_global:.3f}"
            )
            print(
                f"  gate counts: self(raw={self_candidate_counts['self_candidates_raw']}, after_sz={self_candidate_counts['self_candidates_after_sz']}, "
                f"after_conf={self_candidate_counts['self_candidates_after_conf']}, after_persist={self_candidate_counts['self_candidates_after_persistence']}) "
                f"adopt(raw={adopt_candidate_counts['adopt_candidates_raw']}, after_post={adopt_candidate_counts['adopt_candidates_after_post']}, "
                f"after_conf={adopt_candidate_counts['adopt_candidates_after_conf']}, after_gain={adopt_candidate_counts['adopt_candidates_after_gain']}, "
                f"provisional={adopt_candidate_counts['adopt_candidates_provisional']}, after_gate={adopt_candidate_counts['adopt_candidates_after_gate']}, "
                f"final_adopt={adopt_candidate_counts['adopt_candidates_final_adopt']}) "
                f"shadow(eligible={shadow_candidate_counts['shadow_candidates_eligible']}, selected={shadow_candidate_counts['shadow_candidates_selected']}, "
                f"gain_selected={shadow_candidate_counts['shadow_candidates_gain_band_selected']})"
            )
            print(
                f"  row yield: live={selection_rate_diagnostics['live_selected_set_present']} "
                f"shadow={selection_rate_diagnostics['shadow_candidate_available']} "
                f"near_threshold={selection_rate_diagnostics['near_threshold_blocked_candidates']} "
                f"variant(overrides={selection_rate_diagnostics['live_variant_override_count']}, "
                f"persist={selection_rate_diagnostics['live_variant_persistence_guard']}, "
                f"recovery={selection_rate_diagnostics['live_variant_recovery_guard']}, "
                f"projection={selection_rate_diagnostics['live_variant_projection_guard']}, "
                f"quality={selection_rate_diagnostics['live_variant_projected_quality_guard']}) "
                f"gain_band(narrow={selection_rate_diagnostics['safe_gain_blocked_narrow']}, "
                f"wide_extra={selection_rate_diagnostics['would_qualify_wider_gain_band']}, "
                f"shadow={selection_rate_diagnostics['shadow_rows_from_gain_band']}) "
                f"blocked(conf={selection_rate_diagnostics['blocked_by_confidence_gate']}, "
                f"gain={selection_rate_diagnostics['blocked_by_gain_gate']}, "
                f"projection={selection_rate_diagnostics['blocked_by_projection_veto']})"
            )
            print(
                f"  self correlation: with_self={self_event_correlations['mean_gain_when_self']:+.3f} "
                f"without_self={self_event_correlations['mean_gain_without_self']:+.3f} "
                f"signal={self_event_correlations['mean_gain_when_self_signal']:+.3f} "
                f"corr(score)={self_event_correlations['corr_self_score_gain']:+.3f}"
            )
            print(
                f"  projection calibration: pred_gain={float(round_projection_calibration.get('pred_gain_mean', float('nan'))):+.3f} "
                f"pred_proj={float(round_projection_calibration.get('pred_projection_error_mean', float('nan'))):.3f} "
                f"p_proj_bad={float(round_projection_calibration.get('pred_projection_bad_prob', float('nan'))):.3f} "
                f"p_union={float(round_projection_calibration.get('pred_rollback_union', float('nan'))):.3f} "
                f"risk_diag={float(round_projection_calibration.get('pred_rollback_risk_mean', float('nan'))):.3f} "
                f"realized_gain={realized_gain:+.3f} rollback={1.0 if rollback_triggered else 0.0:.0f}"
            )
            print(
                f"  rollback audit: label=round scope=selected_set mode={round_rollback_audit_row.get('selected_set_mode')} "
                f"n={int(round_rollback_audit_row.get('selected_candidate_count', 0))} cause={rollback_cause} "
                f"gain_bad={int(rollback_gain_bad)} goal_bad={int(rollback_goal_bad)} "
                f"risk(max={float(round_rollback_audit_row.get('selected_pred_risk_max', float('nan'))):.3f}, "
                f"mean={float(round_rollback_audit_row.get('selected_pred_risk_mean', float('nan'))):.3f}, "
                f"sel={float(round_rollback_audit_row.get('selected_pred_risk_sel_weighted_mean', float('nan'))):.3f}, "
                f"blend={float(round_rollback_audit_row.get('selected_pred_risk_blend', float('nan'))):.3f}) | "
                f"{_format_rollback_audit_rows(rollback_diagnostic_rows)}"
            )
            if shadow_selected_meta:
                print(
                    f"  shadow audit: label=round scope=selected_set mode={shadow_round_rollback_audit_row.get('selected_set_mode')} "
                    f"n={int(shadow_round_rollback_audit_row.get('selected_candidate_count', 0))} cause={shadow_rollback_cause} "
                    f"gain_bad={int(shadow_rollback_gain_bad)} goal_bad={int(shadow_rollback_goal_bad)} "
                    f"risk(max={float(shadow_round_rollback_audit_row.get('selected_pred_risk_max', float('nan'))):.3f}, "
                    f"mean={float(shadow_round_rollback_audit_row.get('selected_pred_risk_mean', float('nan'))):.3f}, "
                    f"sel={float(shadow_round_rollback_audit_row.get('selected_pred_risk_sel_weighted_mean', float('nan'))):.3f}, "
                    f"blend={float(shadow_round_rollback_audit_row.get('selected_pred_risk_blend', float('nan'))):.3f}) | "
                    f"{_format_rollback_audit_rows(shadow_rollback_diagnostic_rows)}"
                )
            print(
                f"  rollback summary: rows={int(rollback_round_metrics.get('round_rows', 0))} "
                f"best={rollback_round_metrics.get('best_rollback_aggregation')} "
                f"easier={rollback_round_metrics.get('easier_target')} "
                f"recommend={rollback_round_metrics.get('rollback_label_recommendation')}"
            )
            print(
                f"  9D post: T2={float(post_9d_metrics.get('T2_drift', 0.0)):.3f} "
                f"T3={float(post_9d_metrics.get('T3_coherence', 0.0)):.3f} "
                f"C1={float(post_9d_metrics.get('C1_integration', 0.0)):.3f} "
                f"C2={float(post_9d_metrics.get('C2_self_model_strength', 0.0)):.3f} "
                f"C3={float(post_9d_metrics.get('C3_perspective_stability', 0.0)):.3f} "
                f"proj={float(post_9d_metrics.get('projection_error', 0.0)):.3f}"
            )

        benchmark_summary: Dict[str, Any] = {}
        if int(getattr(cfg, "benchmark_every_rounds", 0)) > 0 and ((int(r) + 1) % int(cfg.benchmark_every_rounds) == 0):
            try:
                from benchmarks.trusted_benchmark_pack_v1.runner import run_trusted_benchmark_pack

                benchmark_runtime_context = {
                    "round_index": int(r),
                    "proposer_credit": proposer_credit.astype(np.float32).tolist(),
                    "proposer_cooldown": proposer_cooldown.astype(np.int32).tolist(),
                    "proposer_recent_realized": proposer_recent_realized.astype(np.float32).tolist(),
                    "proposer_recent_goal": proposer_recent_goal.astype(np.float32).tolist(),
                    "proposer_rollback_rate": proposer_rollback_rate.astype(np.float32).tolist(),
                    "instability_state": instability_state.astype(np.float32).tolist(),
                    "self_best_streak": self_best_streak.astype(np.int32).tolist(),
                    "self_score_history": [list(map(float, xs)) for xs in self_score_history],
                    "provisional_owner": provisional_owner.astype(np.int32).tolist(),
                    "provisional_evidence": provisional_evidence.astype(np.float32).tolist(),
                    "provisional_rounds": provisional_rounds.astype(np.int32).tolist(),
                    "realized_gain_history": list(map(float, realized_gain_history)),
                }
                benchmark_result = run_trusted_benchmark_pack(
                    cfg=cfg,
                    triad=triad,
                    pops=pops,
                    world_model=world_model,
                    runtime_context=benchmark_runtime_context,
                    training_round=int(r + 1),
                    mode="scheduled",
                )
                benchmark_summary = dict(benchmark_result.get("summary", {}))
            except Exception as exc:
                benchmark_summary = {"error": repr(exc), "training_round": int(r + 1)}

        history.append(
            {
                "round": int(r),
                "base_avg": float(base_avg),
                "post_avg": float(post_avg),
                "wm_loss": float(wm_loss) if np.isfinite(wm_loss) else float("nan"),
                "wm_recon": float(wm_recon) if np.isfinite(wm_recon) else float("nan"),
                "wm_kl": float(wm_kl) if np.isfinite(wm_kl) else float("nan"),
                "curiosity": float(_last_metric(post_logs, "curiosity", 0.0)),
                "goal_agreement": float(_last_metric(post_logs, "goal_agreement", 0.0)),
                "goal_mse_latent": float(_last_metric(post_logs, "goal_mse_latent", 0.0)),
                "improvements": improvements.copy(),
                "patch_sizes": patch_sizes.copy(),
                "score_matrix": score_matrix.copy(),
                "raw_score_matrix": raw_score_matrix.copy(),
                "cal_conf_matrix": cal_conf_matrix.copy(),
                "gain_score_matrix": gain_score_matrix.copy(),
                "projected_score_matrix": projected_score_matrix.copy(),
                "scale_matrix": scale_matrix.copy(),
                "proposer_credit": proposer_credit.copy(),
                "proposer_cooldown": proposer_cooldown.copy(),
                "proposer_recent_realized": proposer_recent_realized.copy(),
                "proposer_rollback_rate": proposer_rollback_rate.copy(),
                "instability_state": instability_state.copy(),
                "adopted": adopted,
                "adopt_blocked": adopt_blocked,
                "self_adopted": self_adopted,
                "self_blocked": self_blocked,
                "self_diag_pressures": self_diag_pressures.copy(),
                "self_diag_scores": self_diag_scores.copy(),
                "self_diag_improvements": self_diag_improvements.copy(),
                "self_diag_patch_sizes": self_diag_patch_sizes.copy(),
                "self_adopt_scores": self_adopt_scores.copy(),
                "self_persistence_signals": self_persistence_signals.copy(),
                "self_reason_counts": dict(self_reason_counter),
                "self_primary_reasons": list(self_primary_reasons),
                "self_candidate_counts": dict(self_candidate_counts),
                "adopt_candidate_counts": dict(adopt_candidate_counts),
                "shadow_candidate_counts": dict(shadow_candidate_counts),
                "selection_rate_diagnostics": dict(selection_rate_diagnostics),
                "selection_rate_summary": dict(selection_rate_summary),
                "self_recurrence_rate": self_recurrence_rate.copy(),
                "self_recurrence_global": float(self_recurrence_global),
                "self_event_correlations": dict(self_event_correlations),
                "baseline_9d_metrics": dict(baseline_9d_metrics),
                "post_9d_metrics": dict(post_9d_metrics),
                "shadow_post_9d_metrics": dict(shadow_post_9d_metrics),
                "baseline_shadow": dict(baseline_shadow),
                "real_projection_calibration_metrics": dict(projection_calibration_metrics),
                "round_projection_calibration": dict(round_projection_calibration),
                "projection_calibration_metrics": dict(projection_calibration_metrics),
                "shadow_round_projection_calibration": dict(shadow_round_projection_calibration),
                "shadow_projection_calibration_metrics": dict(shadow_projection_calibration_metrics),
                "exploratory_projection_calibration_metrics": dict(exploratory_projection_calibration_metrics),
                "round_rollback_audit_row": dict(round_rollback_audit_row),
                "real_rollback_round_metrics": dict(rollback_round_metrics),
                "rollback_round_metrics": dict(rollback_round_metrics),
                "rollback_round_audit_recent": list(rollback_round_audit_log[-20:]),
                "shadow_round_rollback_audit_row": dict(shadow_round_rollback_audit_row),
                "shadow_rollback_round_metrics": dict(shadow_rollback_round_metrics),
                "shadow_rollback_round_audit_recent": list(shadow_rollback_round_audit_log[-20:]),
                "exploratory_rollback_round_metrics": dict(exploratory_rollback_round_metrics),
                "runtime_marker": RUNTIME_MARKER,
                "live_policy_variant": live_policy_variant_name,
                "live_policy_projection_bad_max_provisional_baseline": float(live_projection_bad_max_provisional),
                "live_policy_targeted_override_projection_bad_max": active_targeted_override_projection_bad_max,
                "rollback_cause": str(rollback_cause),
                "rollback_target_semantics": dict(rollback_target_semantics),
                "shadow_rollback_target_semantics": dict(shadow_target_semantics),
                "rollback_diagnostic_rows": list(rollback_diagnostic_rows),
                "rollback_diagnostic_recent": list(rollback_audit_log[-20:]),
                "shadow_rollback_diagnostic_rows": list(shadow_rollback_diagnostic_rows),
                "shadow_rollback_diagnostic_recent": list(shadow_rollback_audit_log[-20:]),
                "rollback_triggered": bool(rollback_triggered),
                "benchmark_summary": dict(benchmark_summary),
                "v4_wm_primary_plan_structure_probe_enabled": bool(cfg.v4_wm_primary_plan_structure_probe_enabled),
                "v4_wm_plan_context_trace_enabled": bool(cfg.v4_wm_plan_context_trace_enabled),
                "wm_plan_context_rows": list(wm_plan_context_rows),
                "wm_plan_round_summary": _aggregate_wm_plan_context_rows(wm_plan_context_rows),
            }
        )

    return triad, pops, history


run_proposal_learning_loop = run_proposal_learning_loop_v2

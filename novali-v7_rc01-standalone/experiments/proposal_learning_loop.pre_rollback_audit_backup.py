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
    wm_candidate_pred_projection_explosion_max_full: float = 0.44
    wm_candidate_pred_rollback_risk_max_full: float = 0.62

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

    eval_kwargs: Dict[str, Any] = field(default_factory=dict)
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
            "pred_projection_error": 0.0,
            "pred_projection_peak": 0.0,
            "pred_projection_delta": 0.0,
            "pred_projection_explosion_prob": 1.0,
            "pred_instability": 0.0,
            "pred_instability_delta": 0.0,
            "pred_rollback_risk": 1.0,
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
    components = {
        "pred_gain": float(cfg.wm_candidate_pred_gain_weight) * (0.65 * (2.0 * pred_gain_sign_prob - 1.0) + 0.35 * pred_gain_norm),
        "pred_projection": -float(cfg.wm_candidate_pred_projection_weight) * float(np.clip(pred_projection_explosion_prob, 0.0, 1.0)),
        "pred_instability": -float(cfg.wm_candidate_pred_instability_weight) * float(np.clip(max(0.0, inst_norm), 0.0, 1.0)),
        "pred_risk": -float(cfg.wm_candidate_pred_risk_weight) * float(np.clip(pred_rollback_risk, 0.0, 1.0)),
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
        "pred_projection_error": float(pred_projection_error),
        "pred_projection_peak": float(pred_projection_peak),
        "pred_projection_delta": float(pred_projection_delta),
        "pred_projection_explosion_prob": float(pred_projection_explosion_prob),
        "pred_instability": float(pred_instability),
        "pred_instability_delta": float(pred_instability_delta),
        "pred_rollback_risk": float(pred_rollback_risk),
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
    return (
        f"[pred_gain={components.get('pred_gain', 0.0):+.3f} "
        f"pred_proj={components.get('pred_projection', 0.0):+.3f} "
        f"pred_instability={components.get('pred_instability', 0.0):+.3f} "
        f"pred_risk={components.get('pred_risk', 0.0):+.3f} "
        f"pred_uncertainty={components.get('pred_uncertainty', 0.0):+.3f} "
        f"pred_context={components.get('pred_context', 0.0):+.3f}]"
    )


def _aggregate_round_projection_forecast(adopted: List[Dict[str, Any]]) -> Dict[str, float]:
    projected = [a for a in adopted if np.isfinite(float(a.get("pred_gain_sign_prob", float("nan"))))]
    if not projected:
        return {
            "pred_gain_mean": float("nan"),
            "pred_gain_norm_mean": float("nan"),
            "pred_gain_sign_prob": float("nan"),
            "pred_projection_error_mean": float("nan"),
            "pred_projection_peak_mean": float("nan"),
            "pred_projection_delta_mean": float("nan"),
            "pred_projection_explosion_prob": float("nan"),
            "pred_instability_mean": float("nan"),
            "pred_rollback_risk_mean": float("nan"),
            "pred_uncertainty_mean": float("nan"),
            "pred_context_score_mean": float("nan"),
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
    pred_rollback_risk_mean = wmean("pred_rollback_risk", default=1.0)
    pred_rollback_risk_max = vmax("pred_rollback_risk", default=1.0)
    pred_projection_explosion_prob = wmean("pred_projection_explosion_prob", default=1.0)
    pred_rollback_risk_blend = float(
        np.clip(
            0.45 * pred_rollback_risk_max
            + 0.35 * pred_projection_explosion_prob
            + 0.20 * (1.0 - pred_gain_sign_prob),
            0.0,
            1.0,
        )
    )

    return {
        "pred_gain_mean": wmean("pred_post_gain", default=0.0),
        "pred_gain_norm_mean": pred_gain_norm_mean,
        "pred_gain_sign_prob": pred_gain_sign_prob,
        "pred_projection_error_mean": wmean("pred_projection_error", default=0.0),
        "pred_projection_peak_mean": wmean("pred_projection_peak", default=0.0),
        "pred_projection_delta_mean": wmean("pred_projection_delta", default=0.0),
        "pred_projection_explosion_prob": pred_projection_explosion_prob,
        "pred_instability_mean": wmean("pred_instability", default=0.0),
        "pred_rollback_risk_mean": pred_rollback_risk_mean,
        "pred_rollback_risk_max": pred_rollback_risk_max,
        "pred_rollback_risk_blend": pred_rollback_risk_blend,
        "pred_uncertainty_mean": wmean("pred_uncertainty", default=0.0),
        "pred_context_score_mean": wmean("pred_context_score", default=0.0),
    }


def _normalize_gain_target(value: float, history: List[float], default_ref: float = 25.0) -> float:
    recent = np.asarray(history[-8:], dtype=np.float64) if history else np.zeros((0,), dtype=np.float64)
    scale = max(float(default_ref), _safe_mean_arr(np.abs(recent), default=0.0), float(np.std(recent)) if recent.size > 0 else 0.0, 1e-6)
    return _norm_tanh(value, scale)


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
    realized_gain_norm_history: List[float] = []
    realized_gain_sign_history: List[float] = []
    realized_projection_history: List[float] = []
    realized_projection_explosion_history: List[float] = []
    realized_rollback_history: List[float] = []

    provisional_owner = np.full((3,), -1, dtype=np.int32)
    provisional_evidence = np.zeros((3,), dtype=np.float32)
    provisional_rounds = np.zeros((3,), dtype=np.int32)

    history: List[Dict[str, Any]] = []
    prev_self_best_agent: Optional[int] = None

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
                    sel_w = float(np.clip(float(cfg.wm_candidate_projection_selection_weight), 0.0, 1.0))
                    selection_score_raw = (1.0 - sel_w) * selection_score_raw + sel_w * float(projected_signal.get("raw_projected", 0.0))
                    selection_score = (1.0 - sel_w) * selection_score + sel_w * float(projected_signal.get("calibrated_projected", 0.0))

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
                if not passed_conf_stage:
                    reasons.append(
                        f"social confidence too low (conf={coherence_cal:.3f} < provisional={float(confidence['provisional_threshold']):.3f})"
                    )
                elif not passed_gain_stage:
                    reasons.append(
                        f"improvement confidence too low (gain={gain_cal:.3f} < provisional={float(gain_signal['provisional_threshold']):.3f})"
                    )
                else:
                    status = "provisional"
                    threshold_mode = f"{confidence['threshold_mode']}/provisional"
                    adopt_candidate_counts["adopt_candidates_provisional"] += 1
                    adopt_candidate_counts["adopt_candidates_after_gate"] += 1

                    full_ready = bool(
                        coherence_cal >= float(confidence["full_threshold"])
                        and gain_cal >= float(gain_signal["full_threshold"])
                        and imp >= float(cfg.social_conf_full_improvement_min)
                        and local_score >= float(cfg.social_conf_full_local_min)
                        and bool(gain_signal.get("projection_ok_full", False))
                        and bool(projected_signal.get("available", False))
                        and float(projected_signal.get("calibrated_projected", 0.0)) >= float(cfg.wm_candidate_pred_score_threshold_full)
                        and float(projected_signal.get("pred_gain_sign_prob", 0.0)) >= float(cfg.wm_candidate_pred_gain_sign_min_full)
                        and float(projected_signal.get("pred_projection_explosion_prob", 1.0)) <= float(cfg.wm_candidate_pred_projection_explosion_max_full)
                        and float(projected_signal.get("pred_rollback_risk", 1.0)) <= float(cfg.wm_candidate_pred_rollback_risk_max_full)
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
                        if float(projected_signal.get("pred_projection_explosion_prob", 1.0)) > float(cfg.wm_candidate_pred_projection_explosion_max_full):
                            reasons.append(
                                f"projected projection risk elevated (prob={float(projected_signal.get('pred_projection_explosion_prob', 1.0)):.3f})"
                            )
                        if float(projected_signal.get("pred_rollback_risk", 0.0)) > float(cfg.wm_candidate_pred_rollback_risk_max_full):
                            reasons.append(
                                f"predicted rollback risk high (risk={float(projected_signal.get('pred_rollback_risk', 0.0)):.3f})"
                            )

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
                    "pred_projection_error": float(projected_signal.get("pred_projection_error", 0.0)),
                    "pred_projection_explosion_prob": float(projected_signal.get("pred_projection_explosion_prob", 1.0)),
                    "pred_projection_delta": float(projected_signal.get("pred_projection_delta", 0.0)),
                    "pred_instability": float(projected_signal.get("pred_instability", 0.0)),
                    "pred_rollback_risk": float(projected_signal.get("pred_rollback_risk", 1.0)),
                    "pred_uncertainty": float(projected_signal.get("pred_uncertainty", 0.0)),
                    "selection_score": float(selection_score),
                    "threshold_used": float(threshold_used),
                    "threshold_mode": str(threshold_mode),
                    "projection_error": float(gain_signal["projection_error"]),
                    "rollback_rate": float(gain_signal["rollback_rate"]),
                    "scale": float(scale),
                    "status": status,
                    "reason": reasons[0] if reasons else "candidate admissible",
                    "confidence_components": _format_confidence_components(confidence["components"]),
                    "improvement_components": _format_improvement_components(gain_signal["components"]),
                    "projected_components": _format_projected_components(projected_signal.get("components", {})),
                }
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

        post_score, post_logs = eval_group(triad, make_env_for(r, 777), cfg.steps_dummy)
        post_avg = coerce_avg(post_score)
        post_goal_mse = _last_metric(post_logs, "goal_mse_latent", 0.0)
        realized_gain = float(post_avg - base_avg)
        realized_goal_delta = float(post_goal_mse - base_goal_mse) if np.isfinite(post_goal_mse) and np.isfinite(base_goal_mse) else 0.0

        rollback_triggered = False
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
        round_projection_calibration = _aggregate_round_projection_forecast(adopted_meta)
        round_projection_calibration["realized_gain"] = float(realized_gain)
        round_projection_calibration["realized_gain_norm"] = float(_normalize_gain_target(realized_gain, realized_gain_history))
        round_projection_calibration["realized_gain_sign"] = 1.0 if realized_gain > 0.0 else 0.0
        round_projection_calibration["realized_projection_error"] = float(post_9d_metrics.get("projection_error", 0.0))
        round_projection_calibration["realized_projection_explosion"] = (
            1.0 if float(post_9d_metrics.get("projection_error", 0.0)) > float(cfg.adoption_full_projection_error_max) else 0.0
        )
        round_projection_calibration["rollback_triggered"] = 1.0 if rollback_triggered else 0.0

        if np.isfinite(float(round_projection_calibration.get("pred_gain_norm_mean", float("nan")))):
            projected_gain_history.append(float(round_projection_calibration.get("pred_gain_norm_mean", 0.0)))
            projected_gain_sign_history.append(float(round_projection_calibration.get("pred_gain_sign_prob", 0.0)))
            projected_projection_history.append(float(round_projection_calibration.get("pred_projection_error_mean", 0.0)))
            projected_projection_risk_history.append(float(round_projection_calibration.get("pred_projection_explosion_prob", 0.0)))
            projected_risk_history.append(float(round_projection_calibration.get("pred_rollback_risk_blend", 0.0)))
            realized_gain_norm_history.append(float(round_projection_calibration["realized_gain_norm"]))
            realized_gain_sign_history.append(float(round_projection_calibration["realized_gain_sign"]))
            realized_projection_history.append(float(round_projection_calibration["realized_projection_error"]))
            realized_projection_explosion_history.append(float(round_projection_calibration["realized_projection_explosion"]))
            realized_rollback_history.append(float(round_projection_calibration["rollback_triggered"]))

        projection_calibration_metrics = {
            "corr_pred_gain_realized_gain": _safe_corr(projected_gain_history, realized_gain_norm_history),
            "corr_pred_gain_sign_realized_gain_sign": _safe_corr(projected_gain_sign_history, realized_gain_sign_history),
            "corr_pred_projection_realized_projection": _safe_corr(projected_projection_history, realized_projection_history),
            "corr_pred_projection_risk_realized_projection_explosion": _safe_corr(
                projected_projection_risk_history,
                realized_projection_explosion_history,
            ),
            "corr_pred_risk_realized_rollback": _safe_corr(projected_risk_history, realized_rollback_history),
            "forecast_samples": int(len(projected_gain_history)),
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
                        - 0.20 * float(choice.get("pred_rollback_risk", 0.0)),
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
                f"mode={item['threshold_mode']} proj_err={item['projection_error']:.3f} rollback={item['rollback_rate']:.2f} "
                f"pred_gain={item['pred_post_gain']:+.3f} pred_proj={item['pred_projection_error']:.3f} pred_risk={item['pred_rollback_risk']:.3f} "
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
                f"final_adopt={adopt_candidate_counts['adopt_candidates_final_adopt']})"
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
                f"pred_risk={float(round_projection_calibration.get('pred_rollback_risk_mean', float('nan'))):.3f} "
                f"realized_gain={realized_gain:+.3f} rollback={1.0 if rollback_triggered else 0.0:.0f}"
            )
            print(
                f"  9D post: T2={float(post_9d_metrics.get('T2_drift', 0.0)):.3f} "
                f"T3={float(post_9d_metrics.get('T3_coherence', 0.0)):.3f} "
                f"C1={float(post_9d_metrics.get('C1_integration', 0.0)):.3f} "
                f"C2={float(post_9d_metrics.get('C2_self_model_strength', 0.0)):.3f} "
                f"C3={float(post_9d_metrics.get('C3_perspective_stability', 0.0)):.3f} "
                f"proj={float(post_9d_metrics.get('projection_error', 0.0)):.3f}"
            )

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
                "self_recurrence_rate": self_recurrence_rate.copy(),
                "self_recurrence_global": float(self_recurrence_global),
                "self_event_correlations": dict(self_event_correlations),
                "baseline_9d_metrics": dict(baseline_9d_metrics),
                "post_9d_metrics": dict(post_9d_metrics),
                "baseline_shadow": dict(baseline_shadow),
                "round_projection_calibration": dict(round_projection_calibration),
                "projection_calibration_metrics": dict(projection_calibration_metrics),
                "rollback_triggered": bool(rollback_triggered),
            }
        )

    return triad, pops, history


run_proposal_learning_loop = run_proposal_learning_loop_v2

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import torch
import torch.nn as nn

from agents.proposal_net import ProposalNet, ProposalNetConfig


@dataclass(frozen=True)
class SelfImprovementConfig:
    metrics_dim: int = 32
    hidden_dim: int = 96
    proposal_scale: float = 0.04
    proposal_noise_std: float = 0.05
    min_pressure: float = 0.16
    adopt_threshold: float = 0.08
    patch_scale_min: float = 0.15
    patch_scale_max: float = 0.75
    cooldown_rounds: int = 1
    outcome_decay: float = 0.85
    target_c1: float = 0.60
    target_c2: float = 0.60
    target_c3: float = 0.60
    target_t2: float = 0.35
    target_goal_agreement: float = 0.75
    critical_entropy: float = 2.0
    max_patch_value: float = 0.20
    preferred_patch_l2_soft: float = 0.40
    preferred_patch_l2_hard: float = 0.55
    patch_l2_penalty_scale: float = 0.20
    persistence_floor: float = 0.02
    cooldown_bypass_streak: int = 2


class SelfImprovementController(nn.Module):
    """
    Agent-owned phase-1 self-improvement controller.

    The controller:
      - reads explicit 9D and task metrics
      - diagnoses self-improvement pressure
      - proposes a bounded adapter patch for its own agent
      - keeps a small internal memory of recent success / failure / cooldown
    """

    FEATURE_KEYS = (
        "nine_d_c1_complexity",
        "nine_d_c2_self_model",
        "nine_d_c3_observer_stability",
        "nine_d_entropy_proxy_t2",
        "nine_d_phase_proxy_t3",
        "nine_d_delta_t2_abs_mean",
        "nine_d_delta_t3_abs_mean",
        "nine_d_delta_c1_abs_mean",
        "nine_d_delta_c2_abs_mean",
        "nine_d_delta_c3_abs_mean",
        "nine_d_projection_mse_4d",
        "nine_d_observed_motion",
        "goal_agreement",
        "goal_mse_latent",
        "mean_pe",
        "group_dev",
        "msg_entropy",
        "send_rate",
        "curiosity",
        "wm_loss",
        "wm_recon",
        "wm_kl",
    )

    def __init__(
        self,
        cfg: SelfImprovementConfig,
        patch_template: Dict[str, torch.Tensor],
    ):
        super().__init__()
        self.cfg = cfg
        self.proposal_net = ProposalNet(
            ProposalNetConfig(
                metrics_dim=int(cfg.metrics_dim),
                hidden_dim=int(cfg.hidden_dim),
                patch_scale=float(cfg.proposal_scale),
                noise_std=float(cfg.proposal_noise_std),
                max_patch_value=float(cfg.max_patch_value),
            ),
            patch_template=patch_template,
        )

        self.cooldown = 0
        self.success_ema = 0.0
        self.failure_ema = 0.0
        self.last_diagnostic: Dict[str, float] = {}
        self.last_outcome: Dict[str, float] = {}

    @staticmethod
    def _safe_float(x: Any, default: float = 0.0) -> float:
        try:
            if x is None:
                return float(default)
            if isinstance(x, (list, tuple)):
                if len(x) == 0:
                    return float(default)
                return SelfImprovementController._safe_float(x[-1], default=default)
            if torch.is_tensor(x):
                if x.numel() == 0:
                    return float(default)
                x = float(torch.nanmean(x.detach().float()).cpu().item())
            else:
                x = float(x)
            if not torch.isfinite(torch.tensor(x)):
                return float(default)
            return float(x)
        except Exception:
            return float(default)

    def _metric(self, metrics: Dict[str, Any], key: str, default: float = 0.0) -> float:
        return self._safe_float(metrics.get(key, default), default=default)

    @staticmethod
    def _clip01(x: float) -> float:
        return float(max(0.0, min(1.0, float(x))))

    def diagnose(self, metrics: Dict[str, Any], persistence_streak: int = 0) -> Dict[str, float]:
        c1 = self._metric(metrics, "nine_d_c1_complexity", self._metric(metrics, "nine_d_c1_mean", 0.5))
        c2 = self._metric(metrics, "nine_d_c2_self_model", self._metric(metrics, "nine_d_c2_mean", 0.5))
        c3 = self._metric(metrics, "nine_d_c3_observer_stability", self._metric(metrics, "nine_d_c3_mean", 0.5))
        t2 = self._metric(metrics, "nine_d_entropy_proxy_t2", self._metric(metrics, "nine_d_t2_abs_mean", 0.0))
        mean_pe = self._metric(metrics, "mean_pe", self._metric(metrics, "goal_mse_latent", 0.0))
        goal_agreement = self._metric(metrics, "goal_agreement", 0.0)
        msg_entropy = self._metric(metrics, "msg_entropy", self._metric(metrics, "nine_d_comm_entropy_proxy", 0.0))
        wm_loss = self._metric(metrics, "wm_loss", self._metric(metrics, "wm_state_mse", 0.0))
        delta_t2 = self._metric(metrics, "nine_d_delta_t2_abs_mean", 0.0)
        delta_c2 = self._metric(metrics, "nine_d_delta_c2_abs_mean", 0.0)
        critical_entropy = self._metric(metrics, "critical_entropy", float(self.cfg.critical_entropy))

        complexity_deficit = max(0.0, float(self.cfg.target_c1) - c1)
        complexity_deficit += 0.20 * max(0.0, float(self.cfg.target_goal_agreement) - goal_agreement)

        self_model_deficit = max(0.0, float(self.cfg.target_c2) - c2)
        self_model_deficit += 0.35 * max(0.0, mean_pe)
        self_model_deficit += 0.15 * max(0.0, wm_loss)

        observer_deficit = max(0.0, float(self.cfg.target_c3) - c3)
        observer_deficit += 0.12 * abs(msg_entropy - critical_entropy)
        observer_deficit += 0.10 * delta_c2

        entropy_pressure = max(0.0, t2 - float(self.cfg.target_t2))
        entropy_pressure += 0.35 * delta_t2
        entropy_pressure += 0.08 * abs(msg_entropy - critical_entropy)

        pressure = (
            0.30 * complexity_deficit
            + 0.36 * self_model_deficit
            + 0.24 * observer_deficit
            + 0.28 * entropy_pressure
            + 0.12 * self.failure_ema
            - 0.08 * self.success_ema
        )
        pressure = float(max(0.0, min(1.5, pressure)))

        policy_pressure = complexity_deficit + 0.50 * observer_deficit + 0.25 * entropy_pressure
        other_pressure = self_model_deficit + 0.25 * complexity_deficit
        goal_pressure = observer_deficit + 0.75 * self_model_deficit + 0.25 * entropy_pressure
        total_pressure = max(1e-6, policy_pressure + other_pressure + goal_pressure)

        policy_weight = float(policy_pressure / total_pressure)
        other_weight = float(other_pressure / total_pressure)
        goal_weight = float(goal_pressure / total_pressure)

        patch_scale = float(self.cfg.patch_scale_min)
        patch_scale += (float(self.cfg.patch_scale_max) - float(self.cfg.patch_scale_min)) * min(1.0, pressure)
        patch_scale += 0.10 * self.failure_ema
        patch_scale -= 0.05 * self.success_ema
        patch_scale = float(max(float(self.cfg.patch_scale_min), min(float(self.cfg.patch_scale_max), patch_scale)))

        cooldown_bypassed = bool(int(persistence_streak) >= int(self.cfg.cooldown_bypass_streak) and self.cooldown > 0)
        should_propose = bool(pressure >= float(self.cfg.min_pressure) and (self.cooldown <= 0 or cooldown_bypassed))

        diagnostic = {
            "pressure": pressure,
            "complexity_deficit": float(complexity_deficit),
            "self_model_deficit": float(self_model_deficit),
            "observer_deficit": float(observer_deficit),
            "entropy_pressure": float(entropy_pressure),
            "policy_weight": float(policy_weight),
            "other_weight": float(other_weight),
            "goal_weight": float(goal_weight),
            "patch_scale": float(patch_scale),
            "cooldown": float(self.cooldown),
            "persistence_streak": float(persistence_streak),
            "cooldown_bypassed": 1.0 if cooldown_bypassed else 0.0,
            "success_ema": float(self.success_ema),
            "failure_ema": float(self.failure_ema),
            "should_propose": 1.0 if should_propose else 0.0,
        }
        self.last_diagnostic = dict(diagnostic)
        return diagnostic

    def build_feature_tensor(
        self,
        metrics: Dict[str, Any],
        diagnostic: Dict[str, float],
    ) -> torch.Tensor:
        vals = [self._metric(metrics, k, 0.0) for k in self.FEATURE_KEYS]
        vals.extend(
            [
                float(diagnostic.get("pressure", 0.0)),
                float(diagnostic.get("complexity_deficit", 0.0)),
                float(diagnostic.get("self_model_deficit", 0.0)),
                float(diagnostic.get("observer_deficit", 0.0)),
                float(diagnostic.get("entropy_pressure", 0.0)),
                float(diagnostic.get("policy_weight", 0.0)),
                float(diagnostic.get("other_weight", 0.0)),
                float(diagnostic.get("goal_weight", 0.0)),
                float(self.success_ema),
                float(self.failure_ema),
            ]
        )

        device = next(self.proposal_net.parameters()).device
        x = torch.tensor(vals, dtype=torch.float32, device=device)
        dim = int(self.cfg.metrics_dim)
        if x.numel() < dim:
            x = torch.cat([x, torch.zeros(dim - x.numel(), device=device, dtype=x.dtype)], dim=0)
        elif x.numel() > dim:
            x = x[:dim]
        return x

    @staticmethod
    def _patch_group(key: str) -> str:
        raw_key = key[2:] if key.startswith("d_") else key
        if raw_key.startswith("policy_adapter"):
            return "policy"
        if raw_key.startswith("other_adapter"):
            return "other"
        return "goal"

    def propose_patch(
        self,
        metrics: Dict[str, Any],
        current_patch_state: Dict[str, torch.Tensor],
        persistence_streak: int = 0,
    ) -> Tuple[Dict[str, torch.Tensor], Dict[str, float]]:
        diagnostic = self.diagnose(metrics, persistence_streak=persistence_streak)
        if diagnostic.get("should_propose", 0.0) < 0.5:
            return {}, diagnostic

        x = self.build_feature_tensor(metrics, diagnostic)
        prev_mode = self.proposal_net.training
        self.proposal_net.train()
        patch = self.proposal_net(x)
        self.proposal_net.train(prev_mode)

        scale = float(diagnostic.get("patch_scale", self.cfg.patch_scale_min))
        max_patch_value = float(self.cfg.max_patch_value)

        out: Dict[str, torch.Tensor] = {}
        for key, value in patch.items():
            if not torch.is_tensor(value):
                continue

            group = self._patch_group(key)
            group_weight = float(diagnostic.get(f"{group}_weight", 1.0 / 3.0))
            gain = 0.50 + group_weight

            vv = torch.nan_to_num(value.detach(), nan=0.0, posinf=0.0, neginf=0.0)
            vv = vv * scale * gain

            ref_key = key[2:] if key.startswith("d_") else key
            ref = current_patch_state.get(ref_key, None)
            if ref is not None and torch.is_tensor(ref):
                ref_v = torch.tanh(ref.detach().to(device=vv.device, dtype=vv.dtype))
                vv = vv + 0.05 * float(diagnostic.get("pressure", 0.0)) * gain * ref_v

            out[key] = vv.clamp(min=-max_patch_value, max=max_patch_value)

        return out, diagnostic

    def decide_adoption(
        self,
        improvement: float,
        score: float,
        patch_size: float,
        diagnostic: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        diagnostic = diagnostic or self.last_diagnostic
        pressure = float(diagnostic.get("pressure", 0.0))
        should_propose = float(diagnostic.get("should_propose", 0.0)) >= 0.5
        persistence_signal = float(self.success_ema - 0.50 * self.failure_ema)
        size_penalty = 0.0
        if float(patch_size) > float(self.cfg.preferred_patch_l2_soft):
            size_penalty = float(self.cfg.patch_l2_penalty_scale) * (
                float(patch_size) - float(self.cfg.preferred_patch_l2_soft)
            )
        adopt_score = (
            float(score)
            + 0.35 * float(improvement)
            + 0.20 * pressure
            + 0.10 * persistence_signal
            - 0.03 * float(patch_size)
            - size_penalty
        )
        reasons: list[str] = []

        if not should_propose:
            if int(self.cooldown) > 0 and float(diagnostic.get("cooldown_bypassed", 0.0)) < 0.5:
                reasons.append(f"cooldown active ({int(self.cooldown)} rounds remaining)")
            else:
                reasons.append(
                    f"self confidence too low (pressure={pressure:.3f} < min={float(self.cfg.min_pressure):.3f})"
                )

        if float(patch_size) <= 1e-8:
            reasons.append("no self patch candidate generated")

        if float(patch_size) > float(self.cfg.preferred_patch_l2_hard):
            reasons.append(
                f"sz out of band (l2={float(patch_size):.3f} > {float(self.cfg.preferred_patch_l2_hard):.3f})"
            )
        elif float(patch_size) > float(self.cfg.preferred_patch_l2_soft):
            reasons.append(
                f"sz above preferred band (l2={float(patch_size):.3f} > {float(self.cfg.preferred_patch_l2_soft):.3f})"
            )

        if float(improvement) <= 0.0:
            reasons.append(f"post_avg below threshold (dummy d={float(improvement):+.3f})")

        if persistence_signal < float(self.cfg.persistence_floor):
            reasons.append(
                f"persistence requirement unmet (signal={persistence_signal:.3f} < {float(self.cfg.persistence_floor):.3f})"
            )

        if float(score) < float(self.cfg.adopt_threshold):
            reasons.append(
                f"self confidence too low (score={float(score):.3f} < adopt={float(self.cfg.adopt_threshold):.3f})"
            )

        if adopt_score < float(self.cfg.adopt_threshold):
            reasons.append(
                f"adopt score below threshold ({float(adopt_score):.3f} < {float(self.cfg.adopt_threshold):.3f})"
            )

        hard_blocked = (
            (not should_propose)
            or float(patch_size) <= 1e-8
            or float(patch_size) > float(self.cfg.preferred_patch_l2_hard)
        )
        adopt = bool(
            (not hard_blocked)
            and float(improvement) > 0.0
            and adopt_score >= float(self.cfg.adopt_threshold)
        )
        if adopt:
            reasons = []
            primary_reason = "adopted"
        else:
            primary_reason = reasons[0] if reasons else "self adoption blocked"
        return {
            "adopt": 1.0 if adopt else 0.0,
            "adopt_score": float(adopt_score),
            "persistence_signal": float(persistence_signal),
            "primary_reason": primary_reason,
            "reason_count": float(len(reasons)),
            "reasons": tuple(reasons),
        }

    def record_outcome(
        self,
        *,
        dummy_improvement: float,
        dummy_score: float,
        adopted: bool,
        patch_size: float,
        realized_gain: Optional[float] = None,
        rolled_back: bool = False,
    ) -> None:
        realized = float(dummy_score)
        if realized_gain is not None:
            realized = 0.50 * realized + 0.50 * float(realized_gain)

        positive = max(0.0, realized)
        negative = max(0.0, -realized)
        decay = float(self.cfg.outcome_decay)
        self.success_ema = decay * self.success_ema + (1.0 - decay) * positive
        self.failure_ema = decay * self.failure_ema + (1.0 - decay) * negative

        if self.cooldown > 0:
            self.cooldown -= 1

        if (not adopted) and patch_size > 0.0 and dummy_improvement < 0.0:
            self.cooldown = max(self.cooldown, int(self.cfg.cooldown_rounds))

        if rolled_back or realized < 0.0:
            self.cooldown = max(self.cooldown, int(self.cfg.cooldown_rounds))

        self.last_outcome = {
            "dummy_improvement": float(dummy_improvement),
            "dummy_score": float(dummy_score),
            "adopted": 1.0 if adopted else 0.0,
            "patch_size": float(patch_size),
            "realized_gain": float(realized_gain) if realized_gain is not None else float(dummy_score),
            "rolled_back": 1.0 if rolled_back else 0.0,
            "success_ema": float(self.success_ema),
            "failure_ema": float(self.failure_ema),
            "cooldown": float(self.cooldown),
        }

    def snapshot(self) -> Dict[str, float]:
        out = dict(self.last_diagnostic)
        out.update({f"outcome_{k}": float(v) for k, v in self.last_outcome.items()})
        out["cooldown"] = float(self.cooldown)
        out["success_ema"] = float(self.success_ema)
        out["failure_ema"] = float(self.failure_ema)
        return out

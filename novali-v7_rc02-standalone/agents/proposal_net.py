from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import torch
import torch.nn as nn


@dataclass
class ProposalNetConfig:
    metrics_dim: int = 32
    hidden_dim: int = 128
    patch_scale: float = 0.05
    noise_std: float = 0.03
    use_layernorm: bool = True
    min_effective_scale: float = 0.20
    goal_bias: float = 1.20
    policy_bias: float = 1.00
    other_bias: float = 0.90
    max_patch_value: float = 0.25


class ProposalNet(nn.Module):
    """
    Metrics -> structured low-rank patch generator.

    Balanced 9D version:
      - emits policy_adapter.*, other_adapter.*, and goal_adapter.* deltas
      - keeps proposals bounded and non-degenerate
      - slightly favors goal_adapter targets so the proposal mechanism can steer
        the 9D latent-goal pathway without overwhelming policy/action control
    """

    VALID_TARGETS = {
        "policy_adapter.A",
        "policy_adapter.B",
        "other_adapter.A",
        "other_adapter.B",
        "goal_adapter.A",
        "goal_adapter.B",
    }

    def __init__(self, cfg: ProposalNetConfig, patch_template: Dict[str, torch.Tensor]):
        super().__init__()
        self.cfg = cfg
        self.patch_scale = float(cfg.patch_scale)
        self.noise_std = float(cfg.noise_std)
        self.min_effective_scale = float(cfg.min_effective_scale)
        self.max_patch_value = float(cfg.max_patch_value)

        self.patch_keys: List[str] = []
        self.patch_shapes: Dict[str, torch.Size] = {}
        self.patch_sizes: Dict[str, int] = {}
        self.patch_group_bias: Dict[str, float] = {}

        total_out = 0
        for k, v in patch_template.items():
            if k not in self.VALID_TARGETS or not torch.is_tensor(v):
                continue
            self.patch_keys.append(k)
            self.patch_shapes[k] = v.shape
            self.patch_sizes[k] = int(v.numel())
            self.patch_group_bias[k] = self._group_bias(k)
            total_out += int(v.numel())

        if total_out <= 0:
            raise ValueError(
                "ProposalNet found no valid patch targets. "
                f"Expected one of {sorted(self.VALID_TARGETS)}, got keys={list(patch_template.keys())}"
            )

        self.fc1 = nn.Linear(cfg.metrics_dim, cfg.hidden_dim)
        self.fc2 = nn.Linear(cfg.hidden_dim, cfg.hidden_dim)
        self.fc3 = nn.Linear(cfg.hidden_dim, total_out)
        self.ln1 = nn.LayerNorm(cfg.hidden_dim) if cfg.use_layernorm else nn.Identity()
        self.ln2 = nn.LayerNorm(cfg.hidden_dim) if cfg.use_layernorm else nn.Identity()
        self.act = nn.Tanh()

        self._init_weights()

    def _group_bias(self, key: str) -> float:
        if key.startswith("goal_adapter"):
            return float(self.cfg.goal_bias)
        if key.startswith("policy_adapter"):
            return float(self.cfg.policy_bias)
        if key.startswith("other_adapter"):
            return float(self.cfg.other_bias)
        return 1.0

    def _init_weights(self) -> None:
        nn.init.xavier_uniform_(self.fc1.weight, gain=0.9)
        nn.init.zeros_(self.fc1.bias)
        nn.init.xavier_uniform_(self.fc2.weight, gain=0.9)
        nn.init.zeros_(self.fc2.bias)
        nn.init.xavier_uniform_(self.fc3.weight, gain=0.45)
        nn.init.zeros_(self.fc3.bias)

    def _flatten_metrics(self, metrics) -> torch.Tensor:
        if isinstance(metrics, dict):
            vals = []
            for k in sorted(metrics.keys()):
                try:
                    vals.append(float(metrics[k]))
                except Exception:
                    vals.append(0.0)
            x = torch.tensor(vals, dtype=torch.float32)
        elif torch.is_tensor(metrics):
            x = metrics.detach().float().reshape(-1)
        else:
            try:
                x = torch.tensor(list(metrics), dtype=torch.float32).reshape(-1)
            except Exception:
                x = torch.zeros(self.cfg.metrics_dim, dtype=torch.float32)

        x = torch.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        d = int(self.cfg.metrics_dim)
        if x.numel() < d:
            x = torch.cat([x, torch.zeros(d - x.numel(), dtype=x.dtype, device=x.device)], dim=0)
        elif x.numel() > d:
            x = x[:d]
        return x

    def _forward_backbone(self, x: torch.Tensor) -> torch.Tensor:
        h = self.act(self.fc1(x))
        h = self.ln1(h)
        h = self.act(self.fc2(h))
        h = self.ln2(h)
        return self.fc3(h)

    def _scale_and_chunk(self, z: torch.Tensor) -> Dict[str, torch.Tensor]:
        raw = torch.tanh(z) * self.patch_scale
        mean_abs = raw.abs().mean()
        min_scale = self.patch_scale * self.min_effective_scale
        if torch.isfinite(mean_abs) and mean_abs.item() > 1e-12 and mean_abs.item() < min_scale:
            raw = raw * (min_scale / mean_abs.clamp_min(1e-12))

        out: Dict[str, torch.Tensor] = {}
        idx = 0
        for k in self.patch_keys:
            n = self.patch_sizes[k]
            shape = self.patch_shapes[k]
            chunk = raw[idx: idx + n]
            idx += n
            chunk = chunk * self.patch_group_bias[k]
            chunk = chunk.clamp(min=-self.max_patch_value, max=self.max_patch_value)
            out[f"d_{k}"] = chunk.reshape(shape)
        return out

    def forward(self, metrics) -> Dict[str, torch.Tensor]:
        x = self._flatten_metrics(metrics)
        if x.ndim == 1:
            x = x.unsqueeze(0)
        if self.training and self.noise_std > 0.0:
            x = x + torch.randn_like(x) * self.noise_std
        z = self._forward_backbone(x).squeeze(0)
        return self._scale_and_chunk(z)

    @torch.no_grad()
    def patch_l2(self, metrics) -> float:
        patch = self.forward(metrics)
        total = 0.0
        for v in patch.values():
            total += float((v.float() ** 2).sum().item())
        return float(total ** 0.5)

    @torch.no_grad()
    def patch_mean_abs(self, metrics) -> float:
        patch = self.forward(metrics)
        vals = [float(v.abs().mean().item()) for v in patch.values()]
        return float(sum(vals) / max(1, len(vals)))

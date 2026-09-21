from __future__ import annotations

from typing import Dict, Optional

import torch
import torch.nn as nn

from agents.adapter_layers import LowRankAdapter
from agents.self_improvement import SelfImprovementConfig, SelfImprovementController


class PatchableConsciousAgent(nn.Module):
    """
    Patchable agent with LoRA-style adapters on:
      - policy head
      - other-model head
      - goal generator head (RSSM latent goal)

    Patch API expected by evolution loops:
      - get_patch_state()
      - set_patch_state(patch_state)
      - apply_patch_delta(delta_patch)
    """

    def __init__(
        self,
        state_dim: int,
        comm_vocab_size: int = 8,
        comm_embed_dim: int = 8,
        adapter_rank: int = 4,
        adapter_alpha: float = 0.5,
        goal_latent_dim: int = 16,
        use_self_improvement: bool = True,
        self_improvement_config: Optional[SelfImprovementConfig] = None,
    ):
        super().__init__()

        self.state_dim = int(state_dim)
        self.comm_vocab_size = int(comm_vocab_size)
        self.comm_embed_dim = int(comm_embed_dim)
        self.goal_latent_dim = int(goal_latent_dim)
        self.use_self_improvement = bool(use_self_improvement)
        self.self_improvement_config = self_improvement_config or SelfImprovementConfig()

        self.encoder = nn.Sequential(
            nn.Linear(self.state_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
        )

        self.policy = nn.Linear(64, self.state_dim)
        self.policy_adapter = LowRankAdapter(64, self.state_dim, rank=adapter_rank, alpha=adapter_alpha)

        self.other_model = nn.Linear(64, self.state_dim)
        self.other_adapter = LowRankAdapter(64, self.state_dim, rank=adapter_rank, alpha=adapter_alpha)

        self.fam_head = nn.Linear(64, 1)
        self.comm_head = nn.Linear(64 + self.comm_vocab_size, self.comm_vocab_size)

        self.goal_net = nn.Sequential(
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, self.goal_latent_dim),
        )
        self.goal_adapter = LowRankAdapter(64, self.goal_latent_dim, rank=adapter_rank, alpha=adapter_alpha)

        self.last_goal_latent = torch.zeros(self.goal_latent_dim)
        self.self_improver: Optional[SelfImprovementController] = None
        if self.use_self_improvement:
            self.self_improver = SelfImprovementController(
                cfg=self.self_improvement_config,
                patch_template=self.get_patch_state(),
            )

    def forward(self, state: torch.Tensor, comm_in: torch.Tensor = None):
        if state.dim() == 2:
            state = state.squeeze(0)

        encoded = self.encoder(state)

        action = self.policy(encoded) + self.policy_adapter(encoded)
        familiarity = torch.sigmoid(self.fam_head(encoded))
        pred_other = self.other_model(encoded) + self.other_adapter(encoded)

        if comm_in is None:
            comm_in = torch.zeros(self.comm_vocab_size, device=encoded.device)
        comm_logits = self.comm_head(torch.cat([encoded, comm_in], dim=-1))

        goal_latent = self.goal_net(encoded) + self.goal_adapter(encoded)
        self.last_goal_latent = goal_latent.detach()

        return action, familiarity, pred_other, comm_logits

    def _adapter_param_names(self):
        return [
            "policy_adapter.A",
            "policy_adapter.B",
            "other_adapter.A",
            "other_adapter.B",
            "goal_adapter.A",
            "goal_adapter.B",
        ]

    def get_patch_state(self) -> Dict[str, torch.Tensor]:
        sd = self.state_dict()
        out: Dict[str, torch.Tensor] = {}
        for k in self._adapter_param_names():
            if k in sd:
                out[k] = sd[k].detach().clone()
        return out

    def set_patch_state(self, patch_state: Dict[str, torch.Tensor]) -> None:
        with torch.no_grad():
            for k, v in patch_state.items():
                if k not in self._adapter_param_names():
                    continue
                module_name, param_name = k.split(".")
                module = getattr(self, module_name, None)
                if module is None:
                    continue
                p = getattr(module, param_name, None)
                if p is None:
                    continue
                vv = torch.nan_to_num(v.to(p.device).to(p.dtype), nan=0.0, posinf=0.0, neginf=0.0)
                p.copy_(vv)

    @staticmethod
    def scaled_patch(
        delta_patch: Dict[str, torch.Tensor],
        scale: float = 1.0,
        max_abs_value: Optional[float] = None,
    ) -> Dict[str, torch.Tensor]:
        out: Dict[str, torch.Tensor] = {}
        s = float(scale)
        clipv = None if max_abs_value is None else float(max_abs_value)
        for k, dv in delta_patch.items():
            if not torch.is_tensor(dv):
                continue
            vv = torch.nan_to_num(dv.detach(), nan=0.0, posinf=0.0, neginf=0.0).float() * s
            if clipv is not None:
                vv = vv.clamp(min=-clipv, max=clipv)
            out[k] = vv
        return out

    def apply_patch_delta(
        self,
        delta_patch: Dict[str, torch.Tensor],
        scale: float = 1.0,
        max_abs_value: Optional[float] = None,
    ) -> None:
        s = float(scale)
        clipv = None if max_abs_value is None else float(max_abs_value)
        with torch.no_grad():
            for k, dv in delta_patch.items():
                if k not in self._adapter_param_names():
                    continue
                module_name, param_name = k.split(".")
                module = getattr(self, module_name, None)
                if module is None:
                    continue
                p = getattr(module, param_name, None)
                if p is None:
                    continue
                vv = torch.nan_to_num(dv.to(p.device).to(p.dtype), nan=0.0, posinf=0.0, neginf=0.0)
                vv = vv * s
                if clipv is not None:
                    vv = vv.clamp(min=-clipv, max=clipv)
                p.add_(vv)

    @staticmethod
    def patch_l2(delta_patch: Dict[str, torch.Tensor]) -> float:
        tot = 0.0
        for _, v in delta_patch.items():
            tot += float((v.detach().float() ** 2).sum().item())
        return float(tot ** 0.5)

    def propose_self_patch(self, metrics: Dict[str, float], persistence_streak: int = 0):
        if not self.use_self_improvement or self.self_improver is None:
            return {}, {"should_propose": 0.0, "pressure": 0.0}
        return self.self_improver.propose_patch(
            metrics,
            self.get_patch_state(),
            persistence_streak=persistence_streak,
        )

    def decide_self_patch_adoption(
        self,
        improvement: float,
        score: float,
        patch_size: float,
        diagnostic: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        if not self.use_self_improvement or self.self_improver is None:
            return {"adopt": 0.0, "adopt_score": 0.0}
        return self.self_improver.decide_adoption(
            improvement=improvement,
            score=score,
            patch_size=patch_size,
            diagnostic=diagnostic,
        )

    def record_self_improvement_outcome(
        self,
        *,
        dummy_improvement: float,
        dummy_score: float,
        adopted: bool,
        patch_size: float,
        realized_gain: Optional[float] = None,
        rolled_back: bool = False,
    ) -> None:
        if not self.use_self_improvement or self.self_improver is None:
            return
        self.self_improver.record_outcome(
            dummy_improvement=dummy_improvement,
            dummy_score=dummy_score,
            adopted=adopted,
            patch_size=patch_size,
            realized_gain=realized_gain,
            rolled_back=rolled_back,
        )

    def self_improvement_snapshot(self) -> Dict[str, float]:
        if not self.use_self_improvement or self.self_improver is None:
            return {}
        return self.self_improver.snapshot()

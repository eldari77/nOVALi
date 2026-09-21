# agents/memory_agent.py
from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn

from memory.episodic_memory import EpisodicMemory
from agents.patchable_agent import PatchableConsciousAgent
from agents.self_improvement import SelfImprovementConfig


class MemoryConsciousAgent(PatchableConsciousAgent):
    """
    Patchable conscious agent with episodic memory.

    Compatibility with the current project:
      - memory stores (state, action, msg)
      - memory.summarize(state) returns a fixed-size vector
      - state and memory summary are concatenated, then projected back to state_dim
      - forward() delegates to PatchableConsciousAgent after memory augmentation

    9D alignment:
      The memory module can weight recall with a 9D subspace projection when the state
      contains at least 9 dimensions, while still remaining backward-compatible with
      the current 12D simulation.
    """

    def __init__(
        self,
        state_dim: int,
        comm_vocab_size: int = 8,
        comm_embed_dim: int = 8,
        adapter_rank: int = 4,
        adapter_alpha: float = 0.5,
        goal_latent_dim: int = 16,
        memory_size: int = 256,
        memory_k: int = 8,
        memory_embed_dim: int = 32,
        memory_temporal_decay: float = 0.0,
        use_9d_memory: bool = True,
        use_self_improvement: bool = True,
        self_improvement_config: SelfImprovementConfig | None = None,
    ):
        super().__init__(
            state_dim=state_dim,
            comm_vocab_size=comm_vocab_size,
            comm_embed_dim=comm_embed_dim,
            adapter_rank=adapter_rank,
            adapter_alpha=adapter_alpha,
            goal_latent_dim=goal_latent_dim,
            use_self_improvement=use_self_improvement,
            self_improvement_config=self_improvement_config,
        )

        self.memory = EpisodicMemory(
            state_dim=state_dim,
            action_dim=state_dim,
            msg_dim=comm_vocab_size,
            capacity=memory_size,
            k=memory_k,
            embed_dim=memory_embed_dim,
            use_9d_projection=use_9d_memory,
            temporal_decay=memory_temporal_decay,
        )

        mem_dim = int(getattr(self.memory, "summary_dim", state_dim))
        self.state_proj = nn.Linear(state_dim + mem_dim, state_dim)

    def _prepare_state(self, state: torch.Tensor) -> torch.Tensor:
        if not torch.is_tensor(state):
            state = torch.as_tensor(state, dtype=torch.float32)

        state = state.float()

        if state.dim() == 2 and state.shape[0] == 1:
            state = state.squeeze(0)

        if state.dim() != 1:
            state = state.reshape(-1)

        if state.numel() < self.state_dim:
            pad = torch.zeros(
                self.state_dim - state.numel(),
                dtype=state.dtype,
                device=state.device,
            )
            state = torch.cat([state, pad], dim=0)
        elif state.numel() > self.state_dim:
            state = state[: self.state_dim]

        return torch.nan_to_num(state, nan=0.0, posinf=0.0, neginf=0.0)

    def _prepare_action(self, action: torch.Tensor) -> torch.Tensor:
        if not torch.is_tensor(action):
            action = torch.as_tensor(action, dtype=torch.float32)

        action = action.float()

        if action.dim() == 2 and action.shape[0] == 1:
            action = action.squeeze(0)

        action = action.reshape(-1)

        if action.numel() < self.state_dim:
            pad = torch.zeros(
                self.state_dim - action.numel(),
                dtype=action.dtype,
                device=action.device,
            )
            action = torch.cat([action, pad], dim=0)
        elif action.numel() > self.state_dim:
            action = action[: self.state_dim]

        return torch.nan_to_num(action, nan=0.0, posinf=0.0, neginf=0.0)

    def _prepare_msg(self, msg: Optional[torch.Tensor], device: torch.device) -> torch.Tensor:
        if msg is None:
            msg = torch.zeros(self.comm_vocab_size, device=device, dtype=torch.float32)
        elif not torch.is_tensor(msg):
            msg = torch.as_tensor(msg, dtype=torch.float32, device=device)
        else:
            msg = msg.to(device=device, dtype=torch.float32)

        if msg.dim() == 2 and msg.shape[0] == 1:
            msg = msg.squeeze(0)

        msg = msg.reshape(-1)

        if msg.numel() < self.comm_vocab_size:
            pad = torch.zeros(
                self.comm_vocab_size - msg.numel(),
                dtype=msg.dtype,
                device=msg.device,
            )
            msg = torch.cat([msg, pad], dim=0)
        elif msg.numel() > self.comm_vocab_size:
            msg = msg[: self.comm_vocab_size]

        return torch.nan_to_num(msg, nan=0.0, posinf=0.0, neginf=0.0)

    def memory_summary(self, state: torch.Tensor) -> torch.Tensor:
        state = self._prepare_state(state)
        mem_summary = self.memory.summarize(state)
        return torch.nan_to_num(mem_summary, nan=0.0, posinf=0.0, neginf=0.0)

    def forward(self, state: torch.Tensor, comm_in: torch.Tensor = None):
        state = self._prepare_state(state)

        mem_summary = self.memory_summary(state).to(state.device)
        state_aug = torch.cat([state, mem_summary], dim=-1)
        state_proj = self.state_proj(state_aug)
        state_proj = torch.nan_to_num(state_proj, nan=0.0, posinf=0.0, neginf=0.0)

        return super().forward(state_proj, comm_in=comm_in)

    @torch.no_grad()
    def remember(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
        msg: Optional[torch.Tensor],
        *,
        salience: float = 1.0,
    ) -> None:
        state_v = self._prepare_state(state)
        action_v = self._prepare_action(action)
        msg_v = self._prepare_msg(msg, device=state_v.device)

        self.memory.add(
            state_v.detach(),
            action_v.detach(),
            msg_v.detach(),
            salience=salience,
        )

    @torch.no_grad()
    def reset_memory(self) -> None:
        self.memory.clear()

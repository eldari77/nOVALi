# memory/episodic_memory.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class MemoryItem:
    state: torch.Tensor
    action: torch.Tensor
    msg: torch.Tensor
    salience: float = 1.0
    t: int = 0


class EpisodicMemory(nn.Module):
    """
    Episodic memory for the 9D simulation.

    Compatibility goals:
      - supports add(state, action, msg)
      - supports summarize(query_state) -> fixed-size summary vector
      - accepts k as alias for top_k
      - keeps summary_dim == state_dim by default

    9D note:
      The project currently runs with state_dim=12, but this module is written so a
      future 9D-centered projection can be layered in without breaking the existing API.
      For now, "9D-aware" behavior is expressed as:
        - content-based recall
        - temporal decay support
        - salience weighting
        - optional learned projection of the first 9 dimensions if present
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        msg_dim: int,
        capacity: int = 256,
        k: Optional[int] = None,
        top_k: Optional[int] = None,
        embed_dim: int = 32,
        use_9d_projection: bool = True,
        temporal_decay: float = 0.0,
        eps: float = 1e-8,
    ):
        super().__init__()

        self.state_dim = int(state_dim)
        self.action_dim = int(action_dim)
        self.msg_dim = int(msg_dim)
        self.capacity = int(capacity)
        self.embed_dim = int(embed_dim)
        self.temporal_decay = float(max(0.0, temporal_decay))
        self.eps = float(eps)

        if top_k is None and k is None:
            self.top_k = 8
        elif top_k is None:
            self.top_k = int(k)
        else:
            self.top_k = int(top_k)

        # Current simulation commonly uses 12 dims; the first 9 are treated as the
        # theory-aligned subspace when available.
        self.nine_d_dim = min(9, self.state_dim)
        self.use_9d_projection = bool(use_9d_projection and self.nine_d_dim > 0)

        self.state_embed = nn.Linear(self.state_dim, self.embed_dim)

        if self.use_9d_projection:
            self.nine_d_proj = nn.Sequential(
                nn.Linear(self.nine_d_dim, self.embed_dim),
                nn.Tanh(),
                nn.Linear(self.embed_dim, self.embed_dim),
            )
        else:
            self.nine_d_proj = None

        self.summary_proj = nn.Sequential(
            nn.Linear(self.state_dim + self.action_dim + self.msg_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, self.state_dim),
        )
        self.summary_dim = self.state_dim

        self._items: list[MemoryItem] = []
        self._clock: int = 0

    def __len__(self) -> int:
        return len(self._items)

    def clear(self) -> None:
        self._items.clear()
        self._clock = 0

    def _prepare_vector(
        self,
        x: torch.Tensor,
        expected_dim: int,
        *,
        name: str,
        device: Optional[torch.device] = None,
    ) -> torch.Tensor:
        if x is None:
            raise ValueError(f"{name} cannot be None")

        if not torch.is_tensor(x):
            x = torch.as_tensor(x, dtype=torch.float32)

        x = x.detach().float().reshape(-1)

        if x.numel() < expected_dim:
            pad = torch.zeros(expected_dim - x.numel(), dtype=x.dtype, device=x.device)
            x = torch.cat([x, pad], dim=0)
        elif x.numel() > expected_dim:
            x = x[:expected_dim]

        x = torch.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)

        if device is not None:
            x = x.to(device)

        return x

    @torch.no_grad()
    def add(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
        msg: torch.Tensor,
        *,
        salience: float = 1.0,
    ) -> None:
        state_v = self._prepare_vector(state, self.state_dim, name="state").cpu()
        action_v = self._prepare_vector(action, self.action_dim, name="action").cpu()
        msg_v = self._prepare_vector(msg, self.msg_dim, name="msg").cpu()

        safe_salience = float(salience)
        if not torch.isfinite(torch.tensor(safe_salience)):
            safe_salience = 1.0
        safe_salience = max(0.0, safe_salience)

        self._items.append(
            MemoryItem(
                state=state_v,
                action=action_v,
                msg=msg_v,
                salience=safe_salience,
                t=self._clock,
            )
        )
        self._clock += 1

        if len(self._items) > self.capacity:
            self._items.pop(0)

    def _content_scores(self, query_state: torch.Tensor, states: torch.Tensor) -> torch.Tensor:
        q = self.state_embed(query_state.view(1, -1))
        k = self.state_embed(states)
        sims = (k @ q.t()).squeeze(-1)

        if self.use_9d_projection and self.nine_d_proj is not None:
            q9 = self.nine_d_proj(query_state[: self.nine_d_dim].view(1, -1))
            k9 = self.nine_d_proj(states[:, : self.nine_d_dim])
            sims_9d = (k9 @ q9.t()).squeeze(-1)
            sims = 0.5 * sims + 0.5 * sims_9d

        return sims

    def summarize(self, query_state: torch.Tensor) -> torch.Tensor:
        device = query_state.device if torch.is_tensor(query_state) else torch.device("cpu")
        query_state = self._prepare_vector(
            query_state,
            self.state_dim,
            name="query_state",
            device=device,
        )

        if len(self._items) == 0:
            return torch.zeros(self.summary_dim, device=device)

        states = torch.stack([it.state for it in self._items], dim=0).to(device)
        actions = torch.stack([it.action for it in self._items], dim=0).to(device)
        msgs = torch.stack([it.msg for it in self._items], dim=0).to(device)

        sims = self._content_scores(query_state, states)

        salience = torch.tensor(
            [max(0.0, float(it.salience)) for it in self._items],
            dtype=torch.float32,
            device=device,
        )
        sims = sims + torch.log(salience + self.eps)

        if self.temporal_decay > 0.0:
            ages = torch.tensor(
                [max(0, self._clock - 1 - int(it.t)) for it in self._items],
                dtype=torch.float32,
                device=device,
            )
            sims = sims - self.temporal_decay * ages

        sims = torch.nan_to_num(sims, nan=0.0, posinf=0.0, neginf=0.0)

        kk = max(1, min(self.top_k, sims.numel()))
        topv, topi = torch.topk(sims, k=kk, largest=True)

        sel_s = states[topi]
        sel_a = actions[topi]
        sel_m = msgs[topi]

        w = torch.softmax(topv, dim=0).view(-1, 1)
        w = torch.nan_to_num(w, nan=0.0, posinf=0.0, neginf=0.0)

        mean_s = (w * sel_s).sum(dim=0)
        mean_a = (w * sel_a).sum(dim=0)
        mean_m = (w * sel_m).sum(dim=0)

        summary_in = torch.cat([mean_s, mean_a, mean_m], dim=-1)
        out = self.summary_proj(summary_in)
        out = torch.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)
        return out
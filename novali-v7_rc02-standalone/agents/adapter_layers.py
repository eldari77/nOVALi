# agents/adapter_layers.py
from __future__ import annotations

import math
import torch
import torch.nn as nn


class LowRankAdapter(nn.Module):
    """
    LoRA-style low-rank adapter that produces an output delta:

        delta = alpha * (x @ A @ B)

    Shapes:
      x: (..., in_dim)
      A: (in_dim, rank)
      B: (rank, out_dim)
      delta: (..., out_dim)

    NOTE:
      This module returns ONLY the delta.
      If you want a residual, add it at the call site:
          y = base(x) + adapter(x)
    """

    def __init__(self, in_dim: int, out_dim: int, rank: int = 4, alpha: float = 0.5):
        super().__init__()
        self.in_dim = int(in_dim)
        self.out_dim = int(out_dim)
        self.rank = int(rank)
        self.alpha = float(alpha)

        # LoRA init: A small, B zero so delta starts near 0
        self.A = nn.Parameter(torch.zeros(self.in_dim, self.rank))
        self.B = nn.Parameter(torch.zeros(self.rank, self.out_dim))

        nn.init.kaiming_uniform_(self.A, a=math.sqrt(5))
        nn.init.zeros_(self.B)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x2 = x.view(-1, self.in_dim)                 # [N, in_dim]
        delta = (x2 @ self.A @ self.B) * self.alpha # [N, out_dim]
        return delta.view(*x.shape[:-1], self.out_dim)
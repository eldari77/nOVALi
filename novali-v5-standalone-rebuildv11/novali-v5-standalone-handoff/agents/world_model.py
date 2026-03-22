
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from theory.nined_core import NineDLayout


@dataclass
class RSSMState:
    z: torch.Tensor
    h: torch.Tensor


class RSSMWorldModel(nn.Module):
    """
    Lightweight RSSM-style world model for continuous state spaces.

    The first 9 state dimensions are treated as the 9D core manifold:
      - 3 spatial
      - 3 temporal
      - 3 consciousness

    The model exposes:
      - reset()
      - step()
      - compute_loss()
      - encode_state_to_latent()
      - get_latent()
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        latent_dim: int = 16,
        hidden_dim: int = 64,
    ):
        super().__init__()
        self.state_dim = int(state_dim)
        self.action_dim = int(action_dim)
        self.latent_dim = int(latent_dim)
        self.hidden_dim = int(hidden_dim)
        self.layout = NineDLayout(total_state_dim=self.state_dim)
        self.layout.validate()

        self.post_net = nn.Sequential(
            nn.Linear(hidden_dim + state_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, 2 * latent_dim),
        )

        self.prior_net = nn.Sequential(
            nn.Linear(hidden_dim + action_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, 2 * latent_dim),
        )

        self.rnn = nn.GRUCell(latent_dim + action_dim, hidden_dim)

        self.dec_net = nn.Sequential(
            nn.Linear(hidden_dim + latent_dim + action_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, state_dim),
        )

        self._state: Optional[RSSMState] = None
        self._last_debug: Dict[str, float] = {}

    def last_debug_metrics(self) -> Dict[str, float]:
        return dict(self._last_debug)

    def snapshot_internal_state(self) -> Optional[RSSMState]:
        if self._state is None:
            return None
        return RSSMState(
            z=self._state.z.detach().clone(),
            h=self._state.h.detach().clone(),
        )

    def restore_internal_state(self, state: Optional[RSSMState]) -> None:
        if state is None:
            self._state = None
            return
        self._state = RSSMState(
            z=state.z.detach().clone(),
            h=state.h.detach().clone(),
        )

    def reset(self, batch_size: int = 1, device: Optional[torch.device] = None):
        device = device or next(self.parameters()).device
        z = torch.zeros(batch_size, self.latent_dim, device=device)
        h = torch.zeros(batch_size, self.hidden_dim, device=device)
        self._state = RSSMState(z=z, h=h)

    def get_latent(self) -> torch.Tensor:
        if self._state is None:
            self.reset(batch_size=1)
        return self._state.z

    @staticmethod
    def _rsample(mean: torch.Tensor, logvar: torch.Tensor) -> torch.Tensor:
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mean + eps * std

    @staticmethod
    def _kl_diag_gauss(mq, lvq, mp, lvp) -> torch.Tensor:
        vq = torch.exp(lvq)
        vp = torch.exp(lvp)
        kl = 0.5 * (lvp - lvq + (vq + (mq - mp) ** 2) / (vp + 1e-8) - 1.0)
        return kl.sum(dim=-1)

    def step(
        self,
        obs_state: torch.Tensor,
        action: torch.Tensor,
        *,
        use_posterior: bool = True,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        if obs_state.dim() == 1:
            obs_state = obs_state.unsqueeze(0)
        if action.dim() == 1:
            action = action.unsqueeze(0)

        B = obs_state.shape[0]
        device = obs_state.device

        if self._state is None or self._state.z.shape[0] != B:
            self.reset(batch_size=B, device=device)

        h_prev = self._state.h

        prior_params = self.prior_net(torch.cat([h_prev, action], dim=-1))
        p_mean, p_logvar = torch.chunk(prior_params, 2, dim=-1)

        kl = torch.zeros(B, device=device)
        if use_posterior:
            post_params = self.post_net(torch.cat([h_prev, obs_state], dim=-1))
            q_mean, q_logvar = torch.chunk(post_params, 2, dim=-1)
            z = self._rsample(q_mean, q_logvar)
            kl = self._kl_diag_gauss(q_mean, q_logvar, p_mean, p_logvar)
        else:
            z = self._rsample(p_mean, p_logvar)

        h = self.rnn(torch.cat([z, action], dim=-1), h_prev)
        pred_next = self.dec_net(torch.cat([h, z, action], dim=-1))

        self._state = RSSMState(z=z, h=h)
        return pred_next, kl

    def compute_loss(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        next_states: torch.Tensor,
        beta_kl: float = 0.25,
    ):
        if states.dim() == 1:
            states = states.unsqueeze(0)
        if actions.dim() == 1:
            actions = actions.unsqueeze(0)
        if next_states.dim() == 1:
            next_states = next_states.unsqueeze(0)

        B = states.shape[0]
        device = states.device
        self.reset(batch_size=B, device=device)

        pred_next, kl = self.step(states, actions, use_posterior=True)
        recon_per = torch.mean((pred_next - next_states) ** 2, dim=-1)
        recon = recon_per.mean()
        kl_mean = kl.mean()
        loss = recon + float(beta_kl) * kl_mean

        self._last_debug = {
            "wm_state_mse": float(recon.detach().cpu().item()),
            "wm_kl_mean": float(kl_mean.detach().cpu().item()),
        }
        self._last_debug.update(self.layout.state_metrics(pred_next.mean(dim=0), action=actions.mean(dim=0)))
        self._last_debug.update(
            self.layout.transition_metrics(states.mean(dim=0), next_states.mean(dim=0), predicted_next=pred_next.mean(dim=0))
        )
        self._last_debug["wm_projection_mse_4d"] = self._last_debug.get("nine_d_projection_mse_4d", 0.0)

        return loss, recon, kl_mean

    @torch.no_grad()
    def encode_state_to_latent(self, obs_state: torch.Tensor) -> torch.Tensor:
        if obs_state.dim() == 1:
            obs_state = obs_state.unsqueeze(0)

        device = obs_state.device
        B = obs_state.shape[0]
        h0 = torch.zeros(B, self.hidden_dim, device=device)
        post_params = self.post_net(torch.cat([h0, obs_state], dim=-1))
        q_mean, q_logvar = torch.chunk(post_params, 2, dim=-1)
        z = self._rsample(q_mean, q_logvar)
        return z

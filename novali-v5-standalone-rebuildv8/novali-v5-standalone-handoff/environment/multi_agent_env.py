from __future__ import annotations

from typing import Optional

import numpy as np
import torch

from theory.nined_core import (
    IDX_C1,
    IDX_C2,
    IDX_C3,
    IDX_T1,
    IDX_T2,
    IDX_T3,
    IDX_X,
    IDX_Z,
    NineDLayout,
)


class MultiAgentEnvironment:
    """
    Explicit 9D-core multi-agent environment.

    The world always carries a named 9D core:
      [x, y, z, t1, t2, t3, c1, c2, c3]

    Any remaining coordinates are treated as auxiliary channels so the current
    experiment flow can keep using state_dim=12 without losing the theory core.
    """

    def __init__(
        self,
        state_dim: int,
        n_agents: int,
        device: Optional[torch.device] = None,
        dtype: torch.dtype = torch.float32,
        **kwargs,
    ):
        self.state_dim = int(state_dim)
        self.n_agents = int(n_agents)
        self.device = device if device is not None else torch.device("cpu")
        self.dtype = dtype

        self.layout = NineDLayout(total_state_dim=self.state_dim)
        self.layout.validate()

        self.self_gain = float(kwargs.get("self_gain", 0.05))
        self.social_gain = float(kwargs.get("social_gain", 0.02))
        self.noise_scale = float(kwargs.get("noise_scale", 0.01))

        self.world_noise_scale = float(kwargs.get("world_noise_scale", self.noise_scale))
        self.obs_noise_scale = float(kwargs.get("obs_noise_scale", self.noise_scale * 0.5))
        self.agent_drift_scale = float(kwargs.get("agent_drift_scale", self.noise_scale * 0.25))
        self.core_coupling = float(kwargs.get("core_coupling", 0.08))
        self.world_decay = float(kwargs.get("world_decay", 0.01))
        self.entropy_gain = float(kwargs.get("entropy_gain", 0.08))
        self.phase_gain = float(kwargs.get("phase_gain", 0.06))
        self.consciousness_gain = float(kwargs.get("consciousness_gain", 0.10))

        self.return_legacy_step_tuple = bool(kwargs.get("return_legacy_step_tuple", True))

        self.world = torch.zeros(self.state_dim, device=self.device, dtype=self.dtype)
        self.agent_bias = torch.zeros(self.n_agents, self.state_dim, device=self.device, dtype=self.dtype)
        self.obs = torch.zeros(self.n_agents, self.state_dim, device=self.device, dtype=self.dtype)
        self.t = 0

        self.reset()

    def reset(self) -> torch.Tensor:
        self.t = 0
        self.world = self.layout.init_state(batch_size=1, device=self.device, dtype=self.dtype).squeeze(0)
        self.agent_bias = 0.05 * torch.randn(
            self.n_agents, self.state_dim, device=self.device, dtype=self.dtype
        )
        self.obs = self._world_to_obs(self.world)
        return self.obs

    def step(self, actions):
        self.t += 1
        a = self._coerce_actions(actions)

        mean_action = a.mean(dim=0)
        centered_action = a - mean_action.unsqueeze(0)

        world_noise = self.world_noise_scale * torch.randn(
            self.state_dim, device=self.device, dtype=self.dtype
        )
        aux_noise = self.world_noise_scale * torch.randn(
            self.n_agents, self.state_dim, device=self.device, dtype=self.dtype
        )

        self.world = (1.0 - self.world_decay) * self.world + self.social_gain * mean_action + world_noise
        self._update_explicit_9d_core(mean_action)

        self.agent_bias = self.agent_bias + self.self_gain * centered_action + self.agent_drift_scale * aux_noise
        if self.state_dim > self.layout.core_dim:
            self.agent_bias[:, self.layout.core_dim:] = torch.tanh(self.agent_bias[:, self.layout.core_dim:])
        self.agent_bias[:, : self.layout.core_dim] = 0.5 * torch.tanh(self.agent_bias[:, : self.layout.core_dim])

        self.obs = self._world_to_obs(self.world)

        if not self.return_legacy_step_tuple:
            return self.obs

        metrics = self.layout.state_metrics(self.world)
        reward = float(
            metrics["nine_d_c1_complexity"]
            + 0.25 * metrics["nine_d_c2_self_model"]
            + 0.25 * metrics["nine_d_c3_observer_stability"]
            - 0.10 * metrics["nine_d_entropy_proxy_t2"]
        )
        done = False
        info = {
            "t": self.t,
            "world_norm": float(self.world.norm().item()),
            "projection_4d": self.layout.project_to_4d(self.world).squeeze(0).detach().cpu().tolist(),
            "explicit_9d_metrics": metrics,
        }
        return self.obs, reward, done, info

    def _update_explicit_9d_core(self, mean_action: torch.Tensor) -> None:
        prev_world = self.world.clone()
        spatial_prev = prev_world[IDX_X:IDX_Z + 1]
        spatial_action = mean_action[IDX_X:IDX_Z + 1]
        spatial_motion = spatial_action + self.core_coupling * torch.tanh(
            torch.tensor(
                [prev_world[IDX_C1], prev_world[IDX_C2], prev_world[IDX_C3]],
                device=self.device,
                dtype=self.dtype,
            )
        )
        spatial_noise = self.noise_scale * torch.randn(3, device=self.device, dtype=self.dtype)
        spatial_next = spatial_prev + self.social_gain * spatial_motion + spatial_noise
        self.world[IDX_X:IDX_Z + 1] = torch.tanh(spatial_next)

        motion_mag = torch.linalg.norm(self.world[IDX_X:IDX_Z + 1] - spatial_prev)
        action_core_energy = torch.mean(mean_action[: self.layout.core_dim] ** 2)
        aux_energy = (
            torch.mean(prev_world[self.layout.core_dim:] ** 2) if self.state_dim > self.layout.core_dim else torch.tensor(0.0, device=self.device, dtype=self.dtype)
        )

        t1_next = prev_world[IDX_T1] + 1.0
        t2_drive = motion_mag + 0.50 * action_core_energy + 0.25 * aux_energy - 0.15 * prev_world[IDX_C3]
        t2_next = prev_world[IDX_T2] + self.entropy_gain * t2_drive + self.noise_scale * torch.randn((), device=self.device, dtype=self.dtype)
        phase_source = prev_world[IDX_T3] + self.phase_gain * (
            mean_action[IDX_T3] + 0.50 * prev_world[IDX_T2] + 0.30 * prev_world[IDX_C2]
        )
        t3_next = torch.tanh(phase_source + self.noise_scale * torch.randn((), device=self.device, dtype=self.dtype))

        group_alignment = 1.0 / (1.0 + motion_mag)
        c1_next = torch.sigmoid(
            2.0 * self.consciousness_gain * (spatial_next.norm() + group_alignment + 0.25 * prev_world[IDX_C3])
        )
        c2_next = torch.sigmoid(
            2.0 * self.consciousness_gain * (1.0 / (1.0 + torch.abs(t2_next)) + 0.50 * torch.cos(t3_next) + 0.25 * prev_world[IDX_C1])
        )
        c3_next = torch.sigmoid(
            2.0 * self.consciousness_gain * (0.60 * c2_next + 0.40 * c1_next - 0.20 * torch.abs(t2_next) + 0.20 * torch.cos(t3_next))
        )

        self.world[IDX_T1] = t1_next
        self.world[IDX_T2] = torch.tanh(t2_next)
        self.world[IDX_T3] = t3_next
        self.world[IDX_C1] = c1_next
        self.world[IDX_C2] = c2_next
        self.world[IDX_C3] = c3_next

        if self.state_dim > self.layout.core_dim:
            aux_prev = prev_world[self.layout.core_dim:]
            aux_action = mean_action[self.layout.core_dim:]
            aux_next = aux_prev + self.social_gain * aux_action + self.noise_scale * torch.randn_like(aux_prev)
            self.world[self.layout.core_dim:] = torch.tanh(aux_next)

        self.world = self.layout.clamp_core(self.world)

    def _world_to_obs(self, world_vec: torch.Tensor) -> torch.Tensor:
        base = world_vec.unsqueeze(0).repeat(self.n_agents, 1)
        obs_noise = self.obs_noise_scale * torch.randn_like(base)
        obs = base + self.agent_bias + obs_noise

        core = self.layout.project_to_4d(base)
        obs[:, IDX_X] = core[:, 0]
        obs[:, IDX_X + 1] = core[:, 1]
        obs[:, IDX_X + 2] = core[:, 2]
        obs[:, IDX_T1] = core[:, 3]
        obs[:, IDX_T2] = torch.tanh(obs[:, IDX_T2])
        obs[:, IDX_T3] = torch.tanh(obs[:, IDX_T3])
        obs[:, IDX_C1:IDX_C3 + 1] = torch.sigmoid(obs[:, IDX_C1:IDX_C3 + 1])

        if self.state_dim > self.layout.core_dim:
            obs[:, self.layout.core_dim:] = torch.tanh(obs[:, self.layout.core_dim:])

        return obs

    def _coerce_actions(self, actions) -> torch.Tensor:
        if isinstance(actions, (list, tuple)):
            a = torch.stack([self._ensure_vec(x) for x in actions], dim=0)
        elif isinstance(actions, np.ndarray):
            if actions.ndim == 1 and actions.shape[0] == self.state_dim:
                a = torch.as_tensor(actions, device=self.device, dtype=self.dtype).unsqueeze(0).repeat(self.n_agents, 1)
            elif actions.ndim == 2 and actions.shape == (self.n_agents, self.state_dim):
                a = torch.as_tensor(actions, device=self.device, dtype=self.dtype)
            else:
                raise ValueError(
                    f"numpy action array has unexpected shape {actions.shape}; expected ({self.state_dim},) or ({self.n_agents}, {self.state_dim})"
                )
        elif torch.is_tensor(actions):
            if actions.dim() == 1 and actions.numel() == self.state_dim:
                a = actions.unsqueeze(0).repeat(self.n_agents, 1)
            elif actions.dim() == 2 and tuple(actions.shape) == (self.n_agents, self.state_dim):
                a = actions
            else:
                raise ValueError(
                    f"actions tensor has unexpected shape {tuple(actions.shape)}; expected [{self.state_dim}] or [{self.n_agents}, {self.state_dim}]"
                )
        else:
            raise TypeError(f"actions must be list/tuple, numpy.ndarray, or torch.Tensor, got {type(actions)}")

        return a.to(device=self.device, dtype=self.dtype)

    def _ensure_vec(self, x) -> torch.Tensor:
        if isinstance(x, np.ndarray):
            if x.ndim != 1 or x.shape[0] != self.state_dim:
                raise ValueError(f"numpy action must have shape ({self.state_dim},), got {x.shape}")
            return torch.as_tensor(x, device=self.device, dtype=self.dtype)

        if torch.is_tensor(x):
            if x.dim() != 1 or x.numel() != self.state_dim:
                raise ValueError(f"action tensor must have shape [{self.state_dim}], got {tuple(x.shape)}")
            return x.to(device=self.device, dtype=self.dtype)

        raise TypeError(f"action must be a torch.Tensor or numpy.ndarray, got {type(x)}")

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import torch


IDX_X = 0
IDX_Y = 1
IDX_Z = 2
IDX_T1 = 3
IDX_T2 = 4
IDX_T3 = 5
IDX_C1 = 6
IDX_C2 = 7
IDX_C3 = 8

CORE_AXIS_NAMES = ("x", "y", "z", "t1", "t2", "t3", "c1", "c2", "c3")
OBSERVED_AXIS_NAMES = ("x_obs", "y_obs", "z_obs", "t_obs")


@dataclass(frozen=True)
class NineDLayout:
    """
    Explicit 9D theory layout shared across environment, metrics, and models.

    The first nine coordinates are always interpreted as:
      [x, y, z, t1, t2, t3, c1, c2, c3]

    Any extra coordinates remain available as auxiliary channels so the current
    experiment pipeline can keep using 12D state vectors.
    """

    total_state_dim: int

    @property
    def core_dim(self) -> int:
        return 9

    @property
    def aux_dim(self) -> int:
        return max(0, int(self.total_state_dim) - self.core_dim)

    @property
    def axis_names(self) -> tuple[str, ...]:
        return CORE_AXIS_NAMES

    def validate(self) -> None:
        if int(self.total_state_dim) < self.core_dim:
            raise ValueError(
                f"NineDLayout requires total_state_dim >= {self.core_dim}, got {self.total_state_dim}."
            )

    def _ensure_batch(self, state: torch.Tensor) -> torch.Tensor:
        if state.ndim == 1:
            state = state.unsqueeze(0)
        return state

    def split_state(self, state: torch.Tensor) -> Dict[str, torch.Tensor]:
        self.validate()
        state = self._ensure_batch(state)
        spatial = state[..., IDX_X:IDX_Z + 1]
        temporal = state[..., IDX_T1:IDX_T3 + 1]
        consciousness = state[..., IDX_C1:IDX_C3 + 1]
        aux = state[..., self.core_dim:] if self.aux_dim > 0 else state[..., :0]
        return {
            "spatial": spatial,
            "temporal": temporal,
            "consciousness": consciousness,
            "aux": aux,
        }

    def named_state(self, state: torch.Tensor) -> Dict[str, torch.Tensor]:
        self.validate()
        state = self._ensure_batch(state)
        return {name: state[..., idx] for idx, name in enumerate(self.axis_names)}

    def init_state(
        self,
        batch_size: int = 1,
        *,
        device: Optional[torch.device] = None,
        dtype: torch.dtype = torch.float32,
    ) -> torch.Tensor:
        self.validate()
        state = torch.zeros(batch_size, self.total_state_dim, device=device, dtype=dtype)
        state[:, IDX_X:IDX_Z + 1] = 0.35 * torch.randn(batch_size, 3, device=device, dtype=dtype)
        state[:, IDX_T1] = 0.0
        state[:, IDX_T2] = 0.05 * torch.randn(batch_size, device=device, dtype=dtype)
        state[:, IDX_T3] = 0.10 * torch.randn(batch_size, device=device, dtype=dtype)
        state[:, IDX_C1] = 0.15 + 0.05 * torch.randn(batch_size, device=device, dtype=dtype)
        state[:, IDX_C2] = 0.05 * torch.randn(batch_size, device=device, dtype=dtype)
        state[:, IDX_C3] = 0.05 * torch.randn(batch_size, device=device, dtype=dtype)
        if self.aux_dim > 0:
            state[:, self.core_dim:] = 0.10 * torch.randn(batch_size, self.aux_dim, device=device, dtype=dtype)
        return state

    def clamp_core(self, state: torch.Tensor) -> torch.Tensor:
        self.validate()
        out = state.clone()
        out[..., IDX_X:IDX_Z + 1] = torch.tanh(out[..., IDX_X:IDX_Z + 1])
        out[..., IDX_T2] = torch.tanh(out[..., IDX_T2])
        out[..., IDX_T3] = torch.tanh(out[..., IDX_T3])
        out[..., IDX_C1:IDX_C3 + 1] = torch.sigmoid(out[..., IDX_C1:IDX_C3 + 1])
        return out

    def project_to_4d(self, state: torch.Tensor) -> torch.Tensor:
        """
        Observable 4D projection of the explicit 9D state.

        x/y/z stay visible. Observed time is linear time with hidden-axis influence.
        """
        self.validate()
        state = self._ensure_batch(state)
        projected = torch.zeros(state.shape[0], 4, device=state.device, dtype=state.dtype)
        projected[:, 0] = state[:, IDX_X] + 0.05 * torch.tanh(state[:, IDX_C3])
        projected[:, 1] = state[:, IDX_Y]
        projected[:, 2] = state[:, IDX_Z] + 0.05 * torch.tanh(state[:, IDX_T3])
        projected[:, 3] = state[:, IDX_T1] + 0.10 * torch.tanh(state[:, IDX_T2]) + 0.05 * torch.tanh(state[:, IDX_C2])
        return projected

    def observed_dict(self, state: torch.Tensor) -> Dict[str, torch.Tensor]:
        projected = self.project_to_4d(state)
        return {name: projected[..., idx] for idx, name in enumerate(OBSERVED_AXIS_NAMES)}

    def state_metrics(
        self,
        state: torch.Tensor,
        *,
        action: Optional[torch.Tensor] = None,
        comm: Optional[torch.Tensor] = None,
    ) -> Dict[str, float]:
        self.validate()
        state = self._ensure_batch(state)
        named = self.named_state(state)
        projected = self.project_to_4d(state)

        out: Dict[str, float] = {}
        for axis_name, axis_value in named.items():
            out[f"nine_d_{axis_name}_mean"] = float(axis_value.detach().float().mean().cpu().item())
            out[f"nine_d_{axis_name}_abs_mean"] = float(axis_value.detach().float().abs().mean().cpu().item())

        parts = self.split_state(state)
        out["nine_d_spatial_energy"] = float(torch.mean(parts["spatial"] ** 2).detach().cpu().item())
        out["nine_d_temporal_energy"] = float(torch.mean(parts["temporal"] ** 2).detach().cpu().item())
        out["nine_d_consciousness_energy"] = float(torch.mean(parts["consciousness"] ** 2).detach().cpu().item())
        out["nine_d_projection_spatial_energy"] = float(torch.mean(projected[:, :3] ** 2).detach().cpu().item())
        out["nine_d_projection_time_mean"] = float(projected[:, 3].detach().float().mean().cpu().item())

        spatial_norm = torch.linalg.norm(parts["spatial"], dim=-1)
        out["nine_d_entropy_proxy_t2"] = float(
            torch.mean(torch.abs(named["t2"]) + 0.25 * spatial_norm).detach().cpu().item()
        )
        out["nine_d_phase_proxy_t3"] = float(torch.mean(torch.abs(named["t3"])).detach().cpu().item())
        out["nine_d_c1_complexity"] = float(torch.mean(named["c1"]).detach().cpu().item())
        out["nine_d_c2_self_model"] = float(torch.mean(named["c2"]).detach().cpu().item())
        out["nine_d_c3_observer_stability"] = float(torch.mean(named["c3"]).detach().cpu().item())

        if action is not None:
            action = self._ensure_batch(action)
            out["nine_d_action_core_energy"] = float(
                torch.mean(action[..., : self.core_dim] ** 2).detach().cpu().item()
            )
            for idx, axis_name in enumerate(self.axis_names):
                out[f"nine_d_action_{axis_name}_abs_mean"] = float(
                    action[..., idx].detach().float().abs().mean().cpu().item()
                )

        if comm is not None:
            comm = self._ensure_batch(comm)
            out["nine_d_comm_energy"] = float(torch.mean(comm ** 2).detach().cpu().item())
            out["nine_d_comm_entropy_proxy"] = float(torch.mean(torch.abs(comm)).detach().cpu().item())

        return out

    def transition_metrics(
        self,
        prev_state: torch.Tensor,
        next_state: torch.Tensor,
        *,
        predicted_next: Optional[torch.Tensor] = None,
    ) -> Dict[str, float]:
        self.validate()
        prev_state = self._ensure_batch(prev_state)
        next_state = self._ensure_batch(next_state)
        delta = next_state - prev_state

        out: Dict[str, float] = {}
        for idx, axis_name in enumerate(self.axis_names):
            out[f"nine_d_delta_{axis_name}_mean"] = float(delta[..., idx].detach().float().mean().cpu().item())
            out[f"nine_d_delta_{axis_name}_abs_mean"] = float(delta[..., idx].detach().float().abs().mean().cpu().item())

        observed_prev = self.project_to_4d(prev_state)
        observed_next = self.project_to_4d(next_state)
        observed_delta = observed_next - observed_prev
        out["nine_d_observed_motion"] = float(
            torch.linalg.norm(observed_delta[:, :3], dim=-1).mean().detach().cpu().item()
        )
        out["nine_d_observed_time_delta"] = float(observed_delta[:, 3].detach().float().mean().cpu().item())

        if predicted_next is not None:
            predicted_next = self._ensure_batch(predicted_next)
            pred_err = (predicted_next[..., : self.core_dim] - next_state[..., : self.core_dim]) ** 2
            for idx, axis_name in enumerate(self.axis_names):
                out[f"nine_d_pred_mse_{axis_name}"] = float(pred_err[..., idx].detach().float().mean().cpu().item())
            proj_pred = self.project_to_4d(predicted_next)
            proj_mse = torch.mean((proj_pred - observed_next) ** 2)
            out["nine_d_projection_mse_4d"] = float(proj_mse.detach().cpu().item())

        return out

    def project_for_metrics(
        self,
        state: torch.Tensor,
        action: Optional[torch.Tensor] = None,
        comm: Optional[torch.Tensor] = None,
    ) -> Dict[str, float]:
        return self.state_metrics(state, action=action, comm=comm)


@dataclass(frozen=True)
class NineDWorldModelConfig:
    state_dim: int
    latent_dim: int
    hidden_dim: int

    def build_layout(self) -> NineDLayout:
        layout = NineDLayout(total_state_dim=self.state_dim)
        layout.validate()
        return layout

    def latent_partition(self) -> Dict[str, int]:
        base = max(1, self.latent_dim // 3)
        spatial = base
        temporal = base
        consciousness = self.latent_dim - spatial - temporal
        return {
            "spatial": spatial,
            "temporal": temporal,
            "consciousness": consciousness,
        }

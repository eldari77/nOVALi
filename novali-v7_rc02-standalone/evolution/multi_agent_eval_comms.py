
from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import torch

try:
    from theory.nined_core import NineDLayout
except Exception:
    NineDLayout = None  # optional

print("[LOAD CHECK] multi_agent_eval_comms.py :: DROPIN_A")


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (float, int, np.floating, np.integer)):
            v = float(x)
        elif isinstance(x, torch.Tensor):
            if x.numel() == 0:
                return None
            v = float(torch.nanmean(x.detach().float()).cpu().item())
        elif isinstance(x, (list, tuple)) and len(x) > 0:
            return _to_float(x[0])
        else:
            v = float(x)
        if not math.isfinite(v):
            return None
        return v
    except Exception:
        return None


def _nanmean(xs: Iterable[Any], default: float = float("nan")) -> float:
    vals: List[float] = []
    for x in xs:
        v = _to_float(x)
        if v is not None:
            vals.append(v)
    if not vals:
        return float(default)
    return float(sum(vals) / len(vals))


def _safe_tensor(x: Any, device: torch.device, dtype: torch.dtype = torch.float32) -> Optional[torch.Tensor]:
    try:
        if x is None:
            return None
        if isinstance(x, torch.Tensor):
            return x.detach().to(device=device, dtype=dtype)
        arr = np.asarray(x, dtype=np.float32)
        return torch.from_numpy(arr).to(device=device, dtype=dtype)
    except Exception:
        return None


def _extract_action(agent_out: Any) -> Any:
    if isinstance(agent_out, (tuple, list)):
        return agent_out[0] if len(agent_out) > 0 else None
    return agent_out


def _extract_comm(agent_out: Any, comm_dim: int, device: torch.device) -> torch.Tensor:
    if comm_dim <= 0:
        return torch.zeros((0,), device=device, dtype=torch.float32)
    if isinstance(agent_out, (tuple, list)):
        candidate = None
        if len(agent_out) > 3 and torch.is_tensor(agent_out[3]):
            candidate = agent_out[3]
        elif len(agent_out) > 1 and torch.is_tensor(agent_out[1]) and agent_out[1].numel() > 1:
            candidate = agent_out[1]
        if candidate is not None:
            c = candidate.detach().reshape(-1).to(device=device, dtype=torch.float32)
            if c.numel() < comm_dim:
                c = torch.cat([c, torch.zeros(comm_dim - c.numel(), device=device)], dim=0)
            elif c.numel() > comm_dim:
                c = c[:comm_dim]
            return torch.nan_to_num(c, nan=0.0, posinf=0.0, neginf=0.0)
    return torch.zeros((comm_dim,), device=device, dtype=torch.float32)


def _env_reset(env: Any) -> Any:
    out = env.reset()
    if isinstance(out, tuple) and len(out) >= 1:
        return out[0]
    return out


def _env_step(env: Any, action: Any) -> Tuple[Any, float, bool, Dict[str, Any]]:
    out = env.step(action)
    if not isinstance(out, tuple):
        return out, 0.0, False, {}
    if len(out) == 5:
        obs, reward, terminated, truncated, info = out
        return obs, float(reward), bool(terminated) or bool(truncated), (info or {})
    if len(out) == 4:
        obs, reward, done, info = out
        return obs, float(reward), bool(done), (info or {})
    obs = out[0] if len(out) > 0 else None
    reward = out[1] if len(out) > 1 else 0.0
    done = out[2] if len(out) > 2 else False
    info = out[3] if len(out) > 3 else {}
    return obs, float(reward), bool(done), (info or {})


def _make_env_from_kwargs(**kwargs) -> Any:
    make_env = kwargs.get("make_env", None)
    if callable(make_env):
        return make_env()

    cfg = kwargs.get("cfg", None)
    try:
        from envs import make_env as _mk  # type: ignore
        return _mk(cfg) if cfg is not None else _mk()
    except Exception:
        pass

    try:
        from envs.simple_env import SimpleEnv  # type: ignore
        return SimpleEnv()
    except Exception:
        pass

    raise TypeError(
        "evaluate_group_with_comms() was called without env=... and no env factory was found."
    )


def _obs_to_agent_states(obs: Any, n_agents: int, device: torch.device) -> List[torch.Tensor]:
    obs_t = _safe_tensor(obs, device=device)
    if obs_t is None:
        raise ValueError(f"Could not convert obs to tensor: {type(obs)}")
    if obs_t.ndim == 1:
        return [obs_t for _ in range(n_agents)]
    if obs_t.ndim == 2:
        if obs_t.shape[0] == n_agents:
            return [obs_t[i] for i in range(n_agents)]
        if obs_t.shape[0] == 1:
            row = obs_t[0]
            return [row for _ in range(n_agents)]
    flat = obs_t.reshape(-1)
    return [flat for _ in range(n_agents)]


def _action_to_tensor(a: Any, action_dim: Optional[int], device: torch.device) -> torch.Tensor:
    if a is None:
        d = int(action_dim) if action_dim is not None else 1
        return torch.zeros(d, device=device, dtype=torch.float32)
    try:
        if isinstance(a, torch.Tensor):
            t = a.detach().to(device=device, dtype=torch.float32)
        else:
            t = torch.as_tensor(a, device=device, dtype=torch.float32)
    except Exception:
        d = int(action_dim) if action_dim is not None else 1
        return torch.zeros(d, device=device, dtype=torch.float32)

    if t.ndim == 2 and t.shape[0] == 1:
        t = t.squeeze(0)
    if t.ndim > 1:
        t = t.reshape(-1)

    t = torch.nan_to_num(t, nan=0.0, posinf=0.0, neginf=0.0)

    if action_dim is not None:
        d = int(action_dim)
        if t.shape[0] < d:
            t = torch.cat([t, torch.zeros(d - t.shape[0], device=device)], dim=0)
        elif t.shape[0] > d:
            t = t[:d]
    return t


@dataclass
class EvalTelemetry:
    steps: int = 0
    agent_exceptions: int = 0
    wm_train_attempts: int = 0
    wm_train_successes: int = 0
    wm_train_exceptions: int = 0
    nan_rewards: int = 0
    nan_actions: int = 0
    nan_states: int = 0
    started_at: float = 0.0
    ended_at: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "steps": self.steps,
            "agent_exceptions": self.agent_exceptions,
            "wm_train_attempts": self.wm_train_attempts,
            "wm_train_successes": self.wm_train_successes,
            "wm_train_exceptions": self.wm_train_exceptions,
            "nan_rewards": self.nan_rewards,
            "nan_actions": self.nan_actions,
            "nan_states": self.nan_states,
            "wall_s": (self.ended_at - self.started_at) if (self.started_at and self.ended_at) else None,
        }


def _append_session_log(path: Optional[str], line: str) -> None:
    if not path:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


def _sample_replay_batch(replay: List[Tuple[torch.Tensor, torch.Tensor, torch.Tensor]], batch_size: int):
    idx = np.random.choice(len(replay), size=batch_size, replace=False)
    states, actions, next_states = zip(*(replay[i] for i in idx))
    return torch.stack(states, dim=0), torch.stack(actions, dim=0), torch.stack(next_states, dim=0)


def _append_metric(logs: Dict[str, List[float]], key: str, value: Any) -> None:
    v = _to_float(value)
    if v is None:
        return
    logs.setdefault(key, []).append(float(v))


def _train_world_model(
    world_model: Any,
    optimizer: Any,
    replay: List[Tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    batch_size: int,
    beta_kl: float,
) -> Tuple[Optional[float], Optional[float], Optional[float], Dict[str, float]]:
    if world_model is None or optimizer is None or len(replay) == 0:
        return None, None, None, {}

    states, actions, next_states = _sample_replay_batch(replay, batch_size)
    device = next(world_model.parameters()).device
    states = states.to(device)
    actions = actions.to(device)
    next_states = next_states.to(device)

    world_model.train()
    optimizer.zero_grad(set_to_none=True)

    loss_t, recon_t, kl_t = world_model.compute_loss(states, actions, next_states, beta_kl=beta_kl)

    loss_scalar = loss_t if isinstance(loss_t, torch.Tensor) and loss_t.ndim == 0 else torch.nanmean(loss_t)
    recon_scalar = recon_t if isinstance(recon_t, torch.Tensor) and recon_t.ndim == 0 else torch.nanmean(recon_t)
    kl_scalar = kl_t if isinstance(kl_t, torch.Tensor) and kl_t.ndim == 0 else torch.nanmean(kl_t)

    if not torch.isfinite(loss_scalar):
        optimizer.zero_grad(set_to_none=True)
        world_model.eval()
        return None, None, None, {"wm_nonfinite": 1.0}

    loss_scalar.backward()
    torch.nn.utils.clip_grad_norm_(world_model.parameters(), max_norm=10.0)
    optimizer.step()
    world_model.eval()

    debug = {}
    if hasattr(world_model, "last_debug_metrics"):
        try:
            debug = world_model.last_debug_metrics()
        except Exception:
            debug = {}

    return (
        float(loss_scalar.detach().cpu().item()),
        float(recon_scalar.detach().cpu().item()),
        float(kl_scalar.detach().cpu().item()),
        debug,
    )


def evaluate_group_with_comms(
    agents: Sequence[Any],
    env: Any = None,
    steps: int = 120,
    gamma: float = 0.99,
    comm_dim: int = 0,
    comm_scale: float = 1.0,
    curiosity_weight: float = 0.0,
    consensus_goal_weight: float = 0.0,
    debug_nan: bool = False,
    log_telemetry: bool = False,
    critical_entropy: Optional[float] = None,
    world_model: Any = None,
    wm_optimizer: Any = None,
    wm_replay: Optional[List[Tuple[torch.Tensor, torch.Tensor, torch.Tensor]]] = None,
    wm_train_every: int = 10,
    wm_batch_size: int = 128,
    wm_min_replay: int = 1024,
    wm_beta_kl: float = 0.25,
    session_log_path: Optional[str] = None,
    **_extra,
) -> Tuple[List[float], Dict[str, Any]]:
    if env is None:
        env = _make_env_from_kwargs(**_extra)

    tel = EvalTelemetry(started_at=time.time())
    n = len(agents)
    if n == 0:
        tel.ended_at = time.time()
        return [float("nan")] * 3, {"error": "no agents", "telemetry": tel.as_dict()}

    device = torch.device("cpu")
    try:
        for p in agents[0].parameters():
            device = p.device
            break
    except Exception:
        pass

    action_dim: Optional[int] = None
    for key in ("action_dim", "state_dim"):
        if hasattr(env, key):
            try:
                action_dim = int(getattr(env, key))
                break
            except Exception:
                pass
    if action_dim is None:
        action_dim = 1

    obs = _env_reset(env)
    if obs is None:
        tel.ended_at = time.time()
        return [float("nan")] * n, {"error": "env reset returned None", "telemetry": tel.as_dict()}

    layout = None
    if NineDLayout is not None:
        try:
            state_dim_guess = int(getattr(env, "state_dim", 0))
            if state_dim_guess >= 9:
                layout = NineDLayout(total_state_dim=state_dim_guess)
                layout.validate()
        except Exception:
            layout = None

    score_per_agent = [0.0 for _ in range(n)]
    discount = 1.0
    logs: Dict[str, List[float]] = {
        "group_dev": [],
        "mean_pe": [],
        "msg_entropy": [],
        "send_rate": [],
        "curiosity": [],
        "goal_agreement": [],
        "goal_mse_latent": [],
        "wm_loss": [],
        "wm_recon": [],
        "wm_kl": [],
        "wm_trained_steps": [],
    }
    per_step_logs: List[Dict[str, Any]] = []
    wm_trained_steps = 0.0

    if wm_replay is None:
        wm_replay = []

    for t in range(int(steps)):
        tel.steps = t + 1
        state_list = _obs_to_agent_states(obs, n_agents=n, device=device)
        if any(torch.isnan(s).any() or torch.isinf(s).any() for s in state_list):
            tel.nan_states += 1
            state_list = [torch.nan_to_num(s, nan=0.0, posinf=0.0, neginf=0.0) for s in state_list]

        actions_raw: List[Any] = []
        action_tensors: List[torch.Tensor] = []
        comm_outs: List[torch.Tensor] = []

        with torch.no_grad():
            for i, agent in enumerate(agents):
                s_i = state_list[i]
                try:
                    try:
                        out = agent(s_i.unsqueeze(0), comm_in=None)
                    except TypeError:
                        out = agent(s_i.unsqueeze(0))
                    a = _extract_action(out)
                    comm_out = _extract_comm(out, comm_dim=comm_dim, device=device)
                except Exception as e:
                    tel.agent_exceptions += 1
                    if debug_nan or log_telemetry:
                        _append_session_log(session_log_path, f"[Eval] agent {i} exception at step {t}: {repr(e)}")
                    a = None
                    comm_out = torch.zeros((comm_dim,), device=device, dtype=torch.float32) if comm_dim > 0 else torch.zeros((0,), device=device)

                a_t = _action_to_tensor(a, action_dim=action_dim, device=device)
                if torch.isnan(a_t).any() or torch.isinf(a_t).any():
                    tel.nan_actions += 1
                    a_t = torch.nan_to_num(a_t, nan=0.0, posinf=0.0, neginf=0.0)

                actions_raw.append(a_t.detach().cpu().numpy())
                action_tensors.append(a_t)
                comm_outs.append(comm_out)

        if comm_dim > 0:
            avg_comm = torch.stack(
                [c if c.numel() == comm_dim else torch.zeros(comm_dim, device=device) for c in comm_outs],
                dim=0,
            ).mean(dim=0)
            avg_comm = comm_scale * avg_comm
            comm_ins = [avg_comm for _ in range(n)]
            msg_entropy = float(torch.mean(torch.abs(avg_comm)).detach().cpu().item())
            send_rate = float((torch.abs(avg_comm) > 1e-6).float().mean().detach().cpu().item())
        else:
            comm_ins = [torch.zeros((0,), device=device) for _ in range(n)]
            msg_entropy = 0.0
            send_rate = 0.0

        next_obs, reward, done, info = _env_step(env, actions_raw)
        if not math.isfinite(float(reward)):
            tel.nan_rewards += 1
            reward = 0.0

        reward_f = float(reward)
        for i in range(n):
            score_per_agent[i] += discount * reward_f
        discount *= float(gamma)

        next_state_list = _obs_to_agent_states(next_obs, n_agents=n, device=device)
        state_batch = torch.stack(state_list, dim=0).float()
        next_state_batch = torch.stack(next_state_list, dim=0).float()
        action_batch = torch.stack(action_tensors, dim=0).float()
        group_dev = float(next_state_batch.std(dim=0).mean().detach().cpu().item())

        pred_errors: List[float] = []
        pred_next_batch: List[torch.Tensor] = []
        if world_model is not None:
            try:
                for i in range(n):
                    pred_next, _ = world_model.step(state_list[i], action_tensors[i], use_posterior=True)
                    pred_error = torch.mean((pred_next.squeeze(0) - next_state_list[i]) ** 2)
                    pred_errors.append(float(pred_error.detach().cpu().item()))
                    pred_next_batch.append(pred_next.squeeze(0).detach())
                    wm_replay.append((
                        state_list[i].detach().cpu(),
                        action_tensors[i].detach().cpu(),
                        next_state_list[i].detach().cpu(),
                    ))
            except Exception as e:
                tel.wm_train_exceptions += 1
                if debug_nan or log_telemetry:
                    _append_session_log(session_log_path, f"[WM] rollout exception at step {t}: {repr(e)}")
        mean_pe = _nanmean(pred_errors, default=0.0)

        wm_loss_v = None
        wm_recon_v = None
        wm_kl_v = None
        wm_debug: Dict[str, float] = {}
        if world_model is not None and wm_optimizer is not None and len(wm_replay) >= int(wm_min_replay):
            if (t + 1) % max(1, int(wm_train_every)) == 0:
                tel.wm_train_attempts += 1
                try:
                    wm_loss_v, wm_recon_v, wm_kl_v, wm_debug = _train_world_model(
                        world_model=world_model,
                        optimizer=wm_optimizer,
                        replay=wm_replay,
                        batch_size=min(int(wm_batch_size), len(wm_replay)),
                        beta_kl=float(wm_beta_kl),
                    )
                    if wm_loss_v is not None:
                        tel.wm_train_successes += 1
                        wm_trained_steps += 1.0
                except Exception as e:
                    tel.wm_train_exceptions += 1
                    if debug_nan or log_telemetry:
                        _append_session_log(session_log_path, f"[WM] train exception at step {t}: {repr(e)}")

        curiosity = float(curiosity_weight) * float(max(0.0, mean_pe))
        goal_agreement = max(0.0, 1.0 - group_dev)
        goal_mse_latent = mean_pe

        logs["group_dev"].append(float(group_dev))
        logs["mean_pe"].append(float(mean_pe))
        logs["msg_entropy"].append(float(msg_entropy))
        logs["send_rate"].append(float(send_rate))
        logs["curiosity"].append(float(curiosity))
        logs["goal_agreement"].append(float(goal_agreement))
        logs["goal_mse_latent"].append(float(goal_mse_latent))
        logs["wm_loss"].append(float(wm_loss_v) if wm_loss_v is not None else 0.0)
        logs["wm_recon"].append(float(wm_recon_v) if wm_recon_v is not None else 0.0)
        logs["wm_kl"].append(float(wm_kl_v) if wm_kl_v is not None else 0.0)
        logs["wm_trained_steps"].append(float(wm_trained_steps))

        step_log: Dict[str, Any] = {
            "t": int(t),
            "reward": float(reward_f),
            "done": bool(done),
            "group_dev": float(group_dev),
            "mean_pe": float(mean_pe),
            "msg_entropy": float(msg_entropy),
            "send_rate": float(send_rate),
            "wm_loss": float(wm_loss_v) if wm_loss_v is not None else None,
            "wm_recon": float(wm_recon_v) if wm_recon_v is not None else None,
            "wm_kl": float(wm_kl_v) if wm_kl_v is not None else None,
        }
        if layout is not None:
            try:
                state_metrics = layout.state_metrics(
                    next_state_batch.mean(dim=0),
                    action=action_batch.mean(dim=0),
                    comm=comm_ins[0] if comm_ins else None,
                )
                step_log.update(state_metrics)
                for key, value in state_metrics.items():
                    _append_metric(logs, key, value)

                predicted_ref = None
                if pred_next_batch:
                    predicted_ref = torch.stack(pred_next_batch, dim=0).mean(dim=0)
                transition_metrics = layout.transition_metrics(
                    state_batch.mean(dim=0),
                    next_state_batch.mean(dim=0),
                    predicted_next=predicted_ref,
                )
                step_log.update(transition_metrics)
                for key, value in transition_metrics.items():
                    _append_metric(logs, key, value)
            except Exception:
                pass
        if wm_debug:
            step_log.update(wm_debug)

        if log_telemetry:
            per_step_logs.append(step_log)
        if session_log_path and (log_telemetry or debug_nan):
            _append_session_log(session_log_path, str(step_log))

        obs = next_obs
        if done:
            break

    tel.ended_at = time.time()
    score_mean = float(_nanmean(score_per_agent, default=0.0))
    out: Dict[str, Any] = {k: list(v) for k, v in logs.items()}
    out["return"] = score_mean
    out["score_mean"] = score_mean
    out["score_per_agent"] = [float(s) for s in score_per_agent]
    out["telemetry"] = tel.as_dict()
    out["wm_enabled"] = bool(world_model is not None)
    out["wm_replay_size"] = int(len(wm_replay))
    out["critical_entropy"] = float(critical_entropy) if critical_entropy is not None else None
    if log_telemetry:
        out["steps"] = per_step_logs

    return [float(s) for s in score_per_agent], out

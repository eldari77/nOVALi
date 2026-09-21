
from __future__ import annotations

import copy
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import torch

from evolution.multi_agent_eval_comms import evaluate_group_with_comms


def _append_session_log(path: Optional[str], line: str) -> None:
    if not path:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


def summarize_logs(logs: Dict[str, List[float]]) -> Dict[str, float]:
    def last(key: str, default: float = 0.0) -> float:
        xs = logs.get(key, None)
        if not xs:
            return float(default)
        try:
            v = float(xs[-1])
            return v if np.isfinite(v) else float(default)
        except Exception:
            return float(default)

    def mean_last_n(key: str, n: int = 10, default: float = 0.0) -> float:
        xs = logs.get(key, None)
        if not xs:
            return float(default)
        try:
            arr = np.asarray(xs[-n:], dtype=np.float64)
            v = float(np.nanmean(arr))
            return v if np.isfinite(v) else float(default)
        except Exception:
            return float(default)

    return {
        "group_dev_last": last("group_dev"),
        "mean_pe_last": last("mean_pe"),
        "msg_entropy_last": last("msg_entropy"),
        "send_rate_last": last("send_rate"),
        "curiosity_last": last("curiosity"),
        "goal_agreement_last": last("goal_agreement"),
        "goal_mse_latent_last": last("goal_mse_latent"),
        "wm_loss_last": last("wm_loss", default=0.0),
        "wm_recon_last": last("wm_recon", default=0.0),
        "wm_kl_last": last("wm_kl", default=0.0),
        "wm_trained_steps_last": last("wm_trained_steps", default=0.0),
        "group_dev_mean10": mean_last_n("group_dev", 10, 0.0),
        "mean_pe_mean10": mean_last_n("mean_pe", 10, 0.0),
        "msg_entropy_mean10": mean_last_n("msg_entropy", 10, 0.0),
    }


def _resolve_make_env(cfg: Any, eval_kwargs: Dict[str, Any]) -> Callable[[], Any]:
    if "make_env" in eval_kwargs and callable(eval_kwargs["make_env"]):
        return eval_kwargs["make_env"]
    if "env" in eval_kwargs and eval_kwargs["env"] is not None:
        env_obj = eval_kwargs["env"]
        return lambda: env_obj

    import_errors: List[str] = []

    MultiAgentEnvironment = None
    for modpath in (
        "environment.multi_agent_env",
        "multi_agent_env",
        "experiments.multi_agent_env",
    ):
        try:
            mod = __import__(modpath, fromlist=["MultiAgentEnvironment"])
            MultiAgentEnvironment = getattr(mod, "MultiAgentEnvironment", None)
            if MultiAgentEnvironment is not None:
                break
        except Exception as e:
            import_errors.append(f"  - {modpath}.MultiAgentEnvironment: {e}")

    if MultiAgentEnvironment is None:
        msg = (
            "Could not resolve an environment factory.\n"
            "Tried:\n" + "\n".join(import_errors) + "\n\n"
            "Fix: pass make_env=<callable> in eval_kwargs or pass env=<instance>."
        )
        raise ImportError(msg)

    def make_env() -> Any:
        try:
            return MultiAgentEnvironment(
                state_dim=cfg.state_dim,
                n_agents=3,
                noise_scale=float(eval_kwargs.get("noise_scale", 0.01)),
                self_gain=float(eval_kwargs.get("self_gain", 0.05)),
                social_gain=float(eval_kwargs.get("social_gain", 0.02)),
            )
        except TypeError:
            return MultiAgentEnvironment(cfg.state_dim, 3)

    return make_env


def adopt_patch(
    agent,
    patch: Dict[str, torch.Tensor],
    session_log_path: Optional[str] = None,
    verbose: bool = False,
) -> float:
    with torch.no_grad():
        sd = agent.state_dict()
        applied = []
        total_sq = 0.0

        for src_key, delta in patch.items():
            if not torch.is_tensor(delta):
                continue
            dst_key = src_key[2:] if src_key.startswith("d_") else src_key
            if dst_key not in sd:
                continue
            target = sd[dst_key]
            if target.shape != delta.shape:
                _append_session_log(
                    session_log_path,
                    f"[adopt_patch] shape mismatch: {src_key}->{dst_key} patch={tuple(delta.shape)} agent={tuple(target.shape)}",
                )
                continue
            d = torch.nan_to_num(
                delta.detach().to(device=target.device, dtype=target.dtype),
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            )
            target.add_(d)
            total_sq += float((d * d).sum().item())
            applied.append((src_key, dst_key, float(d.abs().mean().item())))

        if applied:
            _append_session_log(session_log_path, f"[adopt_patch] Applied: {applied}")
            if verbose:
                print(f"[adopt_patch] Applied: {applied}")
        return total_sq ** 0.5


def _coerce_avg_score(score_obj: Any) -> float:
    try:
        if torch.is_tensor(score_obj):
            arr = score_obj.detach().float().cpu().numpy()
            if arr.ndim == 0:
                v = float(arr.item())
            else:
                v = float(np.nanmean(arr))
            return v if np.isfinite(v) else 0.0

        if isinstance(score_obj, np.ndarray):
            if score_obj.ndim == 0:
                v = float(score_obj.item())
            else:
                v = float(np.nanmean(score_obj.astype(np.float64)))
            return v if np.isfinite(v) else 0.0

        if isinstance(score_obj, (list, tuple)):
            arr = np.asarray(score_obj, dtype=np.float64)
            if arr.size == 0:
                return 0.0
            v = float(np.nanmean(arr))
            return v if np.isfinite(v) else 0.0

        v = float(score_obj)
        return v if np.isfinite(v) else 0.0
    except Exception:
        return 0.0


def _safe_div(num: float, den: float, eps: float = 1e-6) -> float:
    den = float(den)
    if abs(den) < eps:
        den = eps if den >= 0 else -eps
    return float(num / den)


def _score_entropy_alignment(msg_entropy_last: float, critical_entropy: float) -> float:
    return -abs(float(msg_entropy_last) - float(critical_entropy))


def _score_stability(last_val: float, mean10_val: float) -> float:
    return -abs(float(last_val) - float(mean10_val))


def _persistence_features(parts: Dict[str, float]) -> Tuple[float, float]:
    tracked = [
        float(parts["norm_improvement"]),
        float(parts["group_dev_gain"]),
        float(parts["goal_agreement_gain"]),
        float(parts["goal_mse_gain"]),
        float(parts["pred_error_gain"]),
        float(parts["entropy_alignment_gain"]),
        float(parts["entropy_stability_gain"]),
    ]
    positives = sum(1 for x in tracked if x > 0.0)
    persistence_bonus = positives / float(len(tracked))

    abs_tracked = np.abs(np.asarray(tracked, dtype=np.float64))
    total = float(np.sum(abs_tracked))
    if total <= 1e-8:
        balance_bonus = 0.0
    else:
        dominant = float(np.max(abs_tracked) / total)
        balance_bonus = 1.0 - dominant

    return float(persistence_bonus), float(balance_bonus)


def _score_eval_summary(
    triad_base_avg: float,
    target_base_avg: float,
    patched_avg: float,
    target_base_summary: Dict[str, float],
    patched_summary: Dict[str, float],
    patch_size: float,
    cfg: Any,
) -> Tuple[float, Dict[str, float]]:
    raw_improvement = float(patched_avg - target_base_avg)
    improvement_scale = max(1.0, abs(target_base_avg), abs(triad_base_avg))
    norm_improvement = _safe_div(raw_improvement, improvement_scale)

    base_group_dev = float(target_base_summary.get("group_dev_last", 0.0))
    post_group_dev = float(patched_summary.get("group_dev_last", 0.0))
    group_dev_gain = _safe_div(post_group_dev - base_group_dev, max(1.0, abs(base_group_dev)))

    base_goal_agreement = float(target_base_summary.get("goal_agreement_last", 0.0))
    post_goal_agreement = float(patched_summary.get("goal_agreement_last", 0.0))
    goal_agreement_gain = post_goal_agreement - base_goal_agreement

    base_goal_mse = float(target_base_summary.get("goal_mse_latent_last", 0.0))
    post_goal_mse = float(patched_summary.get("goal_mse_latent_last", 0.0))
    goal_mse_gain = -(post_goal_mse - base_goal_mse)

    base_mean_pe = float(target_base_summary.get("mean_pe_last", 0.0))
    post_mean_pe = float(patched_summary.get("mean_pe_last", 0.0))
    pred_error_gain = -(post_mean_pe - base_mean_pe) / max(1.0, abs(base_mean_pe))

    critical_entropy = float(getattr(cfg, "critical_entropy", 2.0))
    base_entropy_align = _score_entropy_alignment(
        target_base_summary.get("msg_entropy_last", 0.0),
        critical_entropy,
    )
    post_entropy_align = _score_entropy_alignment(
        patched_summary.get("msg_entropy_last", 0.0),
        critical_entropy,
    )
    entropy_alignment_gain = post_entropy_align - base_entropy_align

    base_entropy_stability = _score_stability(
        target_base_summary.get("msg_entropy_last", 0.0),
        target_base_summary.get("msg_entropy_mean10", 0.0),
    )
    post_entropy_stability = _score_stability(
        patched_summary.get("msg_entropy_last", 0.0),
        patched_summary.get("msg_entropy_mean10", 0.0),
    )
    entropy_stability_gain = post_entropy_stability - base_entropy_stability

    base_curiosity = float(target_base_summary.get("curiosity_last", 0.0))
    post_curiosity = float(patched_summary.get("curiosity_last", 0.0))
    curiosity_gain = post_curiosity - base_curiosity

    transfer_gap = abs(float(target_base_avg) - float(triad_base_avg)) / improvement_scale
    transfer_confidence = max(0.0, 1.0 - transfer_gap)

    parts = {
        "raw_improvement": float(raw_improvement),
        "norm_improvement": float(norm_improvement),
        "group_dev_gain": float(group_dev_gain),
        "goal_agreement_gain": float(goal_agreement_gain),
        "goal_mse_gain": float(goal_mse_gain),
        "pred_error_gain": float(pred_error_gain),
        "entropy_alignment_gain": float(entropy_alignment_gain),
        "entropy_stability_gain": float(entropy_stability_gain),
        "curiosity_gain": float(curiosity_gain),
        "transfer_gap": float(transfer_gap),
        "transfer_confidence": float(transfer_confidence),
    }

    persistence_bonus, balance_bonus = _persistence_features(parts)
    parts["persistence_bonus"] = float(persistence_bonus)
    parts["balance_bonus"] = float(balance_bonus)
    parts["patch_penalty"] = float(getattr(cfg, "score_w_patch_penalty", 0.03)) * float(patch_size)

    score = (
        float(getattr(cfg, "score_w_improvement", 0.70)) * norm_improvement
        + float(getattr(cfg, "score_w_group_dev", 0.55)) * group_dev_gain
        + float(getattr(cfg, "score_w_goal_agreement", 0.20)) * goal_agreement_gain
        + float(getattr(cfg, "score_w_goal_mse", 0.50)) * goal_mse_gain
        + float(getattr(cfg, "score_w_entropy_alignment", 0.85)) * entropy_alignment_gain
        + float(getattr(cfg, "score_w_entropy_stability", 0.40)) * entropy_stability_gain
        + float(getattr(cfg, "score_w_pred_error", 0.50)) * pred_error_gain
        + float(getattr(cfg, "score_w_curiosity", 0.20)) * curiosity_gain
        + float(getattr(cfg, "score_w_transfer_confidence", 0.20)) * transfer_confidence
        + float(getattr(cfg, "score_w_persistence", 0.16)) * persistence_bonus
        + float(getattr(cfg, "score_w_balance", 0.12)) * balance_bonus
        - float(getattr(cfg, "score_w_transfer_gap", 0.22)) * transfer_gap
        - float(getattr(cfg, "score_w_patch_penalty", 0.03)) * float(patch_size)
    )
    parts["score"] = float(score)
    return float(score), parts


def _run_eval(
    agents: List[Any],
    cfg: Any,
    eval_kwargs_local: Dict[str, Any],
    world_model: Any,
    wm_optimizer: Any,
    wm_replay: Any,
    steps: int,
):
    return evaluate_group_with_comms(
        agents=agents,
        steps=int(steps),
        critical_entropy=float(getattr(cfg, "critical_entropy", 2.0) if cfg is not None else 2.0),
        world_model=world_model,
        wm_optimizer=wm_optimizer,
        wm_replay=wm_replay,
        wm_train_every=int(getattr(cfg, "wm_train_every", 10) if cfg is not None else 10),
        wm_batch_size=int(getattr(cfg, "wm_batch_size", 128) if cfg is not None else 128),
        wm_min_replay=int(getattr(cfg, "wm_min_replay", 1024) if cfg is not None else 1024),
        wm_beta_kl=float(getattr(cfg, "wm_beta_kl", 0.25) if cfg is not None else 0.25),
        plan_horizon=int(getattr(cfg, "plan_horizon", 4) if cfg is not None else 4),
        plan_candidates=int(getattr(cfg, "plan_candidates", 24) if cfg is not None else 24),
        plan_noise_std=float(getattr(cfg, "plan_noise_std", 0.6) if cfg is not None else 0.6),
        plan_action_clip=float(getattr(cfg, "plan_action_clip", 3.0) if cfg is not None else 3.0),
        use_planning=bool(getattr(cfg, "use_planning", False) if cfg is not None else False),
        cfg=cfg,
        **eval_kwargs_local,
    )


def _safe_clone_agent(src: Any, fallback: Any) -> Any:
    try:
        fresh = copy.deepcopy(src)
        try:
            fresh.load_state_dict(src.state_dict(), strict=False)
        except Exception:
            pass
        return fresh
    except Exception:
        fresh = fallback
        try:
            fresh.load_state_dict(src.state_dict(), strict=False)
        except Exception:
            pass
        return fresh


def _compute_proposer_coherence(improvements: np.ndarray, cfg: Any) -> np.ndarray:
    coherence = np.zeros((3,), dtype=np.float32)
    scale = max(1.0, float(np.nanmean(np.abs(improvements))) + 1e-6)
    for proposer in range(3):
        col = np.asarray(improvements[:, proposer], dtype=np.float64)
        finite = col[np.isfinite(col)]
        if finite.size == 0:
            coherence[proposer] = 0.0
            continue
        mean_gain = float(np.mean(finite)) / scale
        std_gain = float(np.std(finite)) / scale
        coherence[proposer] = (
            float(getattr(cfg, "score_w_cross_agent_mean", 0.10)) * mean_gain
            - float(getattr(cfg, "score_w_cross_agent_std", 0.16)) * std_gain
        )
    return coherence


@torch.no_grad()
def triad_propose_test_personal_dummies(
    triad_agents: List[Any],
    personal_dummies: List[Any],
    proposals: List[Dict[str, torch.Tensor]],
    world_model: Any = None,
    wm_optimizer: Any = None,
    wm_replay: Any = None,
    cfg: Any = None,
    eval_kwargs: Dict[str, Any] | None = None,
) -> Tuple[
    Any, Dict[str, List[float]],
    List[Dict[str, torch.Tensor]],
    np.ndarray, np.ndarray,
    Dict[str, Any],
]:
    if eval_kwargs is None:
        eval_kwargs = {}

    eval_kwargs_local = dict(eval_kwargs)
    if cfg is not None and "env" not in eval_kwargs_local and "make_env" not in eval_kwargs_local:
        eval_kwargs_local["make_env"] = _resolve_make_env(cfg, eval_kwargs_local)

    session_log_path = eval_kwargs_local.get("session_log_path", None)
    verbose = bool(getattr(cfg, "verbose", False))
    _append_session_log(session_log_path, f"=== triad_propose_test_personal_dummies start {datetime.utcnow().isoformat()}Z ===")

    baseline_score_obj, baseline_logs = _run_eval(
        agents=triad_agents,
        cfg=cfg,
        eval_kwargs_local=eval_kwargs_local,
        world_model=world_model,
        wm_optimizer=wm_optimizer,
        wm_replay=wm_replay,
        steps=int(getattr(cfg, "steps_baseline", 150) if cfg is not None else 150),
    )
    triad_base_avg = _coerce_avg_score(baseline_score_obj)
    baseline_summary = summarize_logs(baseline_logs)

    proposals_out: List[Dict[str, torch.Tensor]] = []
    for p in proposals:
        out: Dict[str, torch.Tensor] = {}
        for k, v in p.items():
            if torch.is_tensor(v):
                out[k] = torch.nan_to_num(v.detach().to("cpu"), nan=0.0, posinf=0.0, neginf=0.0)
        proposals_out.append(out)

    improvements = np.zeros((3, 3), dtype=np.float32)
    patch_sizes = np.zeros((3, 3), dtype=np.float32)
    score_matrix = np.zeros((3, 3), dtype=np.float32)

    dummy_logs: Dict[str, Any] = {
        "per_eval": [],
        "baseline_summary": baseline_summary,
        "baseline_avg": float(triad_base_avg),
        "session_log_path": session_log_path,
        "target_baselines": [],
        "score_matrix": score_matrix,
        "proposer_coherence": np.zeros((3,), dtype=np.float32),
    }

    steps_dummy = int(getattr(cfg, "steps_dummy", 120) if cfg is not None else 120)

    for target in range(3):
        base_group = [
            _safe_clone_agent(triad_agents[target], personal_dummies[target]),
            _safe_clone_agent(personal_dummies[(target + 1) % 3], personal_dummies[(target + 1) % 3]),
            _safe_clone_agent(personal_dummies[(target + 2) % 3], personal_dummies[(target + 2) % 3]),
        ]

        base_scores_obj, base_logs = _run_eval(
            agents=base_group,
            cfg=cfg,
            eval_kwargs_local=eval_kwargs_local,
            world_model=world_model,
            wm_optimizer=wm_optimizer,
            wm_replay=wm_replay,
            steps=steps_dummy,
        )
        target_base_avg = _coerce_avg_score(base_scores_obj)
        target_base_summary = summarize_logs(base_logs)

        dummy_logs["target_baselines"].append(
            {
                "target": int(target),
                "target_base_avg": float(target_base_avg),
                "summary": target_base_summary,
            }
        )

        for proposer in range(3):
            group = [
                _safe_clone_agent(triad_agents[target], personal_dummies[target]),
                _safe_clone_agent(personal_dummies[(target + 1) % 3], personal_dummies[(target + 1) % 3]),
                _safe_clone_agent(personal_dummies[(target + 2) % 3], personal_dummies[(target + 2) % 3]),
            ]

            sz = adopt_patch(
                group[0],
                proposals_out[proposer],
                session_log_path=session_log_path,
                verbose=False,
            )
            patch_sizes[target, proposer] = float(sz)

            patched_scores_obj, logs = _run_eval(
                agents=group,
                cfg=cfg,
                eval_kwargs_local=eval_kwargs_local,
                world_model=world_model,
                wm_optimizer=wm_optimizer,
                wm_replay=wm_replay,
                steps=steps_dummy,
            )

            patched_avg = _coerce_avg_score(patched_scores_obj)
            patched_summary = summarize_logs(logs)
            improvement = float(patched_avg - target_base_avg)
            improvements[target, proposer] = improvement

            score, score_parts = _score_eval_summary(
                triad_base_avg=triad_base_avg,
                target_base_avg=target_base_avg,
                patched_avg=patched_avg,
                target_base_summary=target_base_summary,
                patched_summary=patched_summary,
                patch_size=float(sz),
                cfg=cfg,
            )
            score_matrix[target, proposer] = float(score)

            record = {
                "target": int(target),
                "proposer": int(proposer),
                "triad_base_avg": float(triad_base_avg),
                "target_base_avg": float(target_base_avg),
                "patched_avg": float(patched_avg),
                "improvement": float(improvement),
                "patch_size": float(sz),
                "score": float(score),
                "score_parts": score_parts,
                "summary": patched_summary,
            }
            dummy_logs["per_eval"].append(record)
            _append_session_log(session_log_path, f"[dummy_eval] {record}")

    proposer_coherence = _compute_proposer_coherence(improvements, cfg)
    dummy_logs["proposer_coherence"] = proposer_coherence.copy()
    for proposer in range(3):
        score_matrix[:, proposer] += float(getattr(cfg, "score_w_cross_agent_coherence", 0.20)) * float(proposer_coherence[proposer])
    dummy_logs["score_matrix"] = score_matrix.copy()

    if verbose:
        row_parts = []
        for target in range(3):
            best_p = int(np.argmax(score_matrix[target]))
            best_imp = float(improvements[target, best_p])
            best_score = float(score_matrix[target, best_p])
            best_psz = float(patch_sizes[target, best_p])
            row_parts.append(
                f"T{target}<=P{best_p}(d={best_imp:+.4f}, score={best_score:+.4f}, sz={best_psz:.4f})"
            )
        print(f"[dummy_eval] triad_baseline_avg={triad_base_avg:.3f} | " + ", ".join(row_parts))

    _append_session_log(session_log_path, f"=== triad_propose_test_personal_dummies end {datetime.utcnow().isoformat()}Z ===")
    return baseline_score_obj, baseline_logs, proposals_out, improvements, patch_sizes, dummy_logs

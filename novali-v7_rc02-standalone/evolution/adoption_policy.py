from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np


def _safe_percentile(values: np.ndarray, q: float, default: float = 0.0) -> float:
    try:
        arr = np.asarray(values, dtype=np.float64)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            return float(default)
        return float(np.percentile(arr, q))
    except Exception:
        return float(default)


def _safe_mean(values: np.ndarray, default: float = 0.0) -> float:
    try:
        arr = np.asarray(values, dtype=np.float64)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            return float(default)
        return float(np.mean(arr))
    except Exception:
        return float(default)


def compute_adaptive_patch_scale(
    adopt_score: float,
    improvement: float,
    *,
    min_scale: float = 0.35,
    max_scale: float = 1.0,
    score_ref: float = 0.30,
    strong_improvement_ref: float = 8.0,
    persistence_penalty: float = 0.0,
    cooldown_penalty: float = 0.0,
    instability_penalty: float = 0.0,
    success_boost: float = 0.0,
    blend_floor: float = 0.0,
) -> float:
    """
    Convert adoption confidence into a partial-strength patch application scale.

    Intended behavior:
    - weak but admissible proposals land softly
    - strong proposals can still approach full strength
    - recent instability / persistence debt pushes scale downward
    - recent good transfer can lift the floor modestly
    """
    score = max(0.0, float(adopt_score))
    impr = max(0.0, float(improvement))

    score_term = score / max(float(score_ref), 1e-6)
    improvement_term = impr / max(float(strong_improvement_ref), 1e-6)

    confidence = 0.72 * min(1.0, score_term) + 0.28 * min(1.0, improvement_term)
    span = max(float(max_scale) - float(min_scale), 0.0)
    base_scale = float(min_scale) + span * confidence

    penalty = float(persistence_penalty) + float(cooldown_penalty) + float(instability_penalty)
    scale = base_scale - penalty + float(success_boost)
    scale = max(scale, float(blend_floor))
    scale = max(float(min_scale), min(float(max_scale), scale))
    return float(scale)


def choose_best_proposal_per_agent(
    improvements: np.ndarray,
    patch_sizes: np.ndarray,
    adopt_threshold: float,
    adopt_patch_l2_cost: float,
    score_matrix: Optional[np.ndarray] = None,
    use_adaptive_threshold: bool = True,
    adaptive_threshold_mix: float = 0.45,
    min_adopt_score: float = 0.03,
    min_improvement_floor: float = 0.0,
    min_score_margin: float = 0.01,
    min_transfer_score: float = 0.05,
    strong_positive_improvement: float = 0.25,
    per_agent_threshold_add: Optional[np.ndarray] = None,
    per_agent_margin_add: Optional[np.ndarray] = None,
) -> List[Tuple[int, Optional[int], float, float, float]]:
    """
    improvements[target, proposer]
    patch_sizes[target, proposer]
    score_matrix[target, proposer] optional 9D-aware composite score

    Returns one tuple per target agent:
      (agent_idx, chosen_proposal_idx or None, improvement, adopt_score, patch_size)
    """

    improvements = np.asarray(improvements, dtype=np.float32)
    patch_sizes = np.asarray(patch_sizes, dtype=np.float32)

    if improvements.shape != (3, 3):
        raise ValueError("improvements must have shape (3, 3)")
    if patch_sizes.shape != (3, 3):
        raise ValueError("patch_sizes must have shape (3, 3)")

    if score_matrix is None:
        score_matrix = improvements - float(adopt_patch_l2_cost) * patch_sizes
    else:
        score_matrix = np.asarray(score_matrix, dtype=np.float32)
        if score_matrix.shape != (3, 3):
            raise ValueError("score_matrix must have shape (3, 3)")

    if per_agent_threshold_add is None:
        per_agent_threshold_add = np.zeros((3,), dtype=np.float32)
    else:
        per_agent_threshold_add = np.asarray(per_agent_threshold_add, dtype=np.float32).reshape(3)

    if per_agent_margin_add is None:
        per_agent_margin_add = np.zeros((3,), dtype=np.float32)
    else:
        per_agent_margin_add = np.asarray(per_agent_margin_add, dtype=np.float32).reshape(3)

    actions: List[Tuple[int, Optional[int], float, float, float]] = []

    for agent_idx in range(3):
        local_scores = np.asarray(score_matrix[agent_idx], dtype=np.float64)
        finite_scores = local_scores[np.isfinite(local_scores)]
        positive_scores = finite_scores[finite_scores > 0.0]

        adaptive_gate = float(min_adopt_score)
        if use_adaptive_threshold:
            if positive_scores.size > 0:
                p50 = _safe_percentile(positive_scores, 50.0, default=min_adopt_score)
                p75 = _safe_percentile(positive_scores, 75.0, default=p50)
                mean_pos = _safe_mean(positive_scores, default=min_adopt_score)
                adaptive_gate = max(
                    float(min_adopt_score),
                    float(adaptive_threshold_mix) * p50
                    + (1.0 - float(adaptive_threshold_mix)) * mean_pos,
                )
                adaptive_gate = min(adaptive_gate, p75)
            else:
                adaptive_gate = float(min_adopt_score)

        score_gate = max(
            float(adopt_threshold),
            float(adaptive_gate),
            float(min_adopt_score),
        ) + float(per_agent_threshold_add[agent_idx])

        soft_score_gate = max(float(min_transfer_score), 0.70 * score_gate)
        improvement_gate = float(min_improvement_floor)

        candidates = []
        for proposer_idx in range(3):
            impr = float(improvements[agent_idx, proposer_idx])
            psz = float(patch_sizes[agent_idx, proposer_idx])
            score = float(score_matrix[agent_idx, proposer_idx])

            if not np.isfinite(impr) or not np.isfinite(score) or not np.isfinite(psz):
                continue
            if impr < improvement_gate:
                continue

            passed_standard_gate = score >= score_gate
            passed_soft_lane = (impr >= strong_positive_improvement) and (score >= soft_score_gate)
            passed_safe_lane = (impr >= 0.05) and (score >= min_transfer_score)

            if not (passed_standard_gate or passed_soft_lane or passed_safe_lane):
                continue

            candidates.append((score, impr, proposer_idx, psz))

        if not candidates:
            actions.append((agent_idx, None, 0.0, 0.0, 0.0))
            continue

        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        best_score, best_impr, best_p, best_psz = candidates[0]
        second_score = candidates[1][0] if len(candidates) > 1 else -np.inf
        margin = float(best_score - second_score) if np.isfinite(second_score) else float(best_score)

        relaxed_margin = float(min_score_margin) + float(per_agent_margin_add[agent_idx])
        if best_impr >= strong_positive_improvement:
            relaxed_margin *= 0.5

        if len(candidates) > 1 and margin < relaxed_margin and best_impr < strong_positive_improvement:
            actions.append((agent_idx, None, 0.0, 0.0, 0.0))
            continue

        if best_score < min_transfer_score and best_impr < strong_positive_improvement:
            actions.append((agent_idx, None, 0.0, 0.0, 0.0))
            continue

        actions.append((agent_idx, int(best_p), float(best_impr), float(best_score), float(best_psz)))

    return actions

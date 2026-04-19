from __future__ import annotations

from typing import Any, Dict, List

import numpy as np


def score_gain_goal_family(results: List[Dict[str, Any]]) -> Dict[str, float | None]:
    policy_gain_bad: List[float] = []
    policy_goal_bad: List[float] = []
    goal_margins: List[float] = []
    gain_bad_probs: List[float] = []
    gain_bad_targets: List[float] = []
    goal_bad_probs: List[float] = []
    goal_bad_targets: List[float] = []
    for result in results:
        policy = dict(result.get("policy_decision_result", {}))
        if policy:
            policy_gain_bad.append(1.0 if bool(policy.get("gain_bad", False)) else 0.0)
            policy_goal_bad.append(1.0 if bool(policy.get("goal_bad", False)) else 0.0)
            goal_margins.append(float(policy.get("realized_goal_delta", 0.0)))
        for status in ("provisional", "full"):
            decision = dict(result.get("decision_results", {}).get(status, {}))
            if decision:
                gain_bad_probs.append(float(decision.get("pred_gain_bad_prob", 0.5)))
                gain_bad_targets.append(1.0 if bool(decision.get("gain_bad", False)) else 0.0)
                goal_bad_probs.append(float(decision.get("pred_goal_bad_prob", 0.5)))
                goal_bad_targets.append(1.0 if bool(decision.get("goal_bad", False)) else 0.0)
    gain_bad_brier = None
    goal_bad_brier = None
    if gain_bad_probs and len(gain_bad_probs) == len(gain_bad_targets):
        gain_bad_brier = float(np.mean((np.asarray(gain_bad_probs, dtype=np.float64) - np.asarray(gain_bad_targets, dtype=np.float64)) ** 2))
    if goal_bad_probs and len(goal_bad_probs) == len(goal_bad_targets):
        goal_bad_brier = float(np.mean((np.asarray(goal_bad_probs, dtype=np.float64) - np.asarray(goal_bad_targets, dtype=np.float64)) ** 2))
    return {
        "policy_gain_bad_rate": float(np.mean(np.asarray(policy_gain_bad, dtype=np.float64))) if policy_gain_bad else None,
        "policy_goal_bad_rate": float(np.mean(np.asarray(policy_goal_bad, dtype=np.float64))) if policy_goal_bad else None,
        "goal_delta_mean": float(np.mean(np.asarray(goal_margins, dtype=np.float64))) if goal_margins else None,
        "gain_bad_brier": gain_bad_brier,
        "goal_bad_brier": goal_bad_brier,
    }

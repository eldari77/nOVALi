from __future__ import annotations

from typing import Any, Dict, List

import numpy as np


def score_projection_family(results: List[Dict[str, Any]]) -> Dict[str, float | None]:
    policy_projection_bad: List[float] = []
    policy_projection_error: List[float] = []
    pred_projection_bad: List[float] = []
    realized_projection_bad: List[float] = []
    for result in results:
        policy = dict(result.get("policy_decision_result", {}))
        if policy:
            policy_projection_bad.append(1.0 if bool(policy.get("projection_bad", False)) else 0.0)
            policy_projection_error.append(float(policy.get("projection_error", 0.0)))
        for status in ("provisional", "full"):
            decision = dict(result.get("decision_results", {}).get(status, {}))
            if decision:
                pred_projection_bad.append(float(decision.get("pred_projection_bad_prob", 0.5)))
                realized_projection_bad.append(1.0 if bool(decision.get("projection_bad", False)) else 0.0)
    brier = None
    if pred_projection_bad and len(pred_projection_bad) == len(realized_projection_bad):
        arr_p = np.asarray(pred_projection_bad, dtype=np.float64)
        arr_t = np.asarray(realized_projection_bad, dtype=np.float64)
        brier = float(np.mean((arr_p - arr_t) ** 2))
    return {
        "policy_projection_bad_rate": float(np.mean(np.asarray(policy_projection_bad, dtype=np.float64))) if policy_projection_bad else None,
        "policy_projection_error_mean": float(np.mean(np.asarray(policy_projection_error, dtype=np.float64))) if policy_projection_error else None,
        "projection_bad_brier": brier,
    }

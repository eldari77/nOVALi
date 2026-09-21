from __future__ import annotations

from collections import Counter
from typing import Dict, List

import numpy as np


def score_persistence_family(results: List[Dict[str, Any]]) -> Dict[str, float | Dict[str, int] | None]:
    policy_decisions = Counter()
    oracle_decisions = Counter()
    matches: List[float] = []
    for result in results:
        policy_decisions[str(result.get("policy_decision", "reject"))] += 1
        oracle_decisions[str(result.get("oracle_decision", "reject"))] += 1
        matches.append(1.0 if bool(result.get("selection_quality", {}).get("policy_match_oracle", False)) else 0.0)
    return {
        "policy_decision_counts": dict(policy_decisions),
        "oracle_decision_counts": dict(oracle_decisions),
        "policy_match_rate": float(np.mean(np.asarray(matches, dtype=np.float64))) if matches else None,
    }

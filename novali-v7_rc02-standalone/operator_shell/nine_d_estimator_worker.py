"""Fixed estimator deserializer; accepts bounded numeric data, not programs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from operator_shell.nine_d_testing import observation_names
from operator_shell.research_tools import evaluate_expression


def main() -> int:
    import numpy as np
    payload = json.loads(sys.stdin.buffer.read(150001))
    estimator, inputs = payload["estimator"], np.asarray(payload["inputs"], dtype=float)
    names = observation_names(estimator["observation"])
    if inputs.shape != (64, len(names)) or not np.isfinite(inputs).all() or len(estimator["features"]) != 9:
        raise ValueError("bounded_transfer_inputs_required")
    features = np.array([[evaluate_expression(expression, dict(zip(names, row))) for expression in estimator["features"]] for row in inputs])
    center, scale, weights = (np.asarray(estimator[key], dtype=float) for key in ("feature_center", "feature_scale", "coefficients"))
    if center.shape != (9,) or scale.shape != (9,) or weights.shape != (10, 4) or not (scale > 0).all():
        raise ValueError("bounded_estimator_required")
    prediction = np.column_stack((np.ones(len(inputs)), (features - center) / scale)) @ weights
    print(json.dumps(prediction.tolist(), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

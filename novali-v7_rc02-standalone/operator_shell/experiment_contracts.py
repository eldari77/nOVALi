"""Small domain-independent contracts for bounded, falsifiable experiments."""
from __future__ import annotations

import math
from typing import Any, Mapping

COMPLEMENTS = {">": "<=", ">=": "<", "<": ">=", "<=": ">", "==": "!="}


def fields(value: Any, names: set[str], path: str) -> None:
    if not isinstance(value, Mapping) or set(value) != names:
        raise ValueError(path + ": exact fields required: " + ", ".join(sorted(names)))


def number(value: Any, low: float, high: float, path: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(path + ": finite number in [" + str(low) + ", " + str(high) + "] required")
    return float(value)


def integer(value: Any, low: int, high: int, path: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(path + ": bounded integer required")
    return value


def validate_hypothesis(value: Any) -> None:
    fields(value, {"statement", "prediction", "falsifier"}, "hypothesis")
    if not isinstance(value["statement"], str) or not 8 <= len(value["statement"].strip()) <= 1000:
        raise ValueError("hypothesis.statement: bounded descriptive statement required")
    for key in ("prediction", "falsifier"):
        fields(value[key], {"relation", "value"}, "hypothesis." + key)
        number(value[key]["value"], -1e6, 1e6, "hypothesis." + key + ".value")
    prediction, falsifier = value["prediction"], value["falsifier"]
    if (prediction["relation"] not in COMPLEMENTS
            or falsifier["relation"] != COMPLEMENTS[prediction["relation"]]
            or falsifier["value"] != prediction["value"]):
        raise ValueError("hypothesis.falsifier: exact complement of prediction required")


def interval_outcome(prediction: Mapping[str, Any], lower: float, upper: float) -> str:
    """Logical interval test; no statistical confidence is implied by an interval."""
    if not all(math.isfinite(x) for x in (lower, upper)) or lower > upper:
        return "inconclusive"
    relation, value = prediction["relation"], prediction["value"]
    supported, refuted = {
        ">": (lower > value, upper <= value), ">=": (lower >= value, upper < value),
        "<": (upper < value, lower >= value), "<=": (upper <= value, lower > value),
        "==": (lower == upper == value, value < lower or value > upper),
    }[relation]
    return "supported" if supported else "refuted" if refuted else "inconclusive"

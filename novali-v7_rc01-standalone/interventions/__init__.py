from __future__ import annotations

from importlib import import_module
from typing import Any


__all__ = [
    "build_intervention_ledger_analytics",
    "build_proposal_recommendations",
    "run_intervention_proposal",
    "write_intervention_ledger_analytics_report",
    "write_proposal_recommendations_report",
]


def __getattr__(name: str) -> Any:
    if name in {"build_intervention_ledger_analytics", "write_intervention_ledger_analytics_report"}:
        module = import_module(".analytics", __name__)
        return getattr(module, name)
    if name in {"build_proposal_recommendations", "write_proposal_recommendations_report"}:
        module = import_module(".recommendations", __name__)
        return getattr(module, name)
    if name == "run_intervention_proposal":
        module = import_module(".runner", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

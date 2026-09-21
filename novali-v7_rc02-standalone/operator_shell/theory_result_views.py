"""Bounded views of immutable scientific results; outside evaluator semantics."""
from __future__ import annotations

import json
from typing import Any, Mapping

from .research_tools import digest

SECTIONS = {"variants": ("variants", "analytical_diagnostics", "analytical_diagnostic_scope", "paired_block_gain_lower_margin"),
    "counterexamples": ("counterexamples", "discovery_observations", "fidelity"),
    "costs": ("arm_costs", "phase_costs", "representation_costs", "elapsed_seconds", "steps_executed"),
    "provenance": ("provenance", "information_contract", "partition_commitments", "partitions", "noise_control"),
    "retained_estimator": ("retained_estimator", "estimator_restart_verified", "restart_scope"),
    "hypothesis": ("hypothesis_outcome", "metrics", "interval_rule", "observable", "observation"),
    "specification": ()}


def compact(record: Mapping[str, Any]) -> dict[str, Any] | None:
    assessment = record.get("assessment", {})
    if not isinstance(assessment, Mapping) or "baseline_fidelity_verified" not in assessment:
        return None
    keys = ("validity", "baseline_fidelity_verified", "hypothesis_outcome", "metrics", "checks", "revision_eligible",
        "observation", "observable", "scope", "interval_rule", "method_adoption", "allowance_added",
        "prose_statement_verified", "nine_d_advantage_established", "growth_credit", "estimator_restart_verified", "restart_scope")
    result = {key: record[key] for key in ("id", "snapshot_id", "evaluated_revision_id", "prediction_results") if key in record}
    result["assessment"] = {key: assessment[key] for key in keys if key in assessment}
    result["record_views"] = {"command": "inspect_record", "arguments": {"kind": "evaluations", "id": record.get("id"), "section": "choose a named section", "offset_chars": 0}, "sections": list(SECTIONS)}
    result["full_record_retained"] = True
    result["grants_execution_authority"] = False
    return result


def section(record: Mapping[str, Any], name: str, offset: int) -> dict[str, Any]:
    if name not in SECTIONS or type(offset) is not int or offset < 0 or compact(record) is None:
        raise ValueError("registered_evaluation_section_and_offset_required")
    assessment = record["assessment"]
    data = record["model_spec"] if name == "specification" else {key: assessment[key] for key in SECTIONS[name] if key in assessment}
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if offset > len(encoded):
        raise ValueError("evaluation_section_offset_out_of_range")
    end = min(len(encoded), offset + 4000)
    return {"id": record["id"], "section": name, "text": encoded[offset:end],
        "offset_chars": offset, "next_offset_chars": end, "total_chars": len(encoded),
        "complete": end == len(encoded), "section_sha256": digest(data), "grants_execution_authority": False}

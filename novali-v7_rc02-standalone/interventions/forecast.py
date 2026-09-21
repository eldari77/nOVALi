from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .analytics import build_intervention_ledger_analytics
from .ledger import load_latest_snapshots


def _benchmark_summary_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "benchmarks"
        / "trusted_benchmark_pack_v1"
        / "reports"
        / "latest_summary.json"
    )


def load_latest_benchmark_summary() -> Dict[str, Any]:
    path = _benchmark_summary_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_forecast_context() -> Dict[str, Any]:
    ledger_latest = list(load_latest_snapshots().values())
    proposal_type_counts: Dict[str, int] = {}
    recent_failure_tags: Dict[str, int] = {}
    for record in ledger_latest[-20:]:
        proposal_type = str(record.get("proposal_type", "unknown"))
        proposal_type_counts[proposal_type] = int(proposal_type_counts.get(proposal_type, 0)) + 1
        for tag in list(record.get("failure_tags", [])):
            recent_failure_tags[str(tag)] = int(recent_failure_tags.get(str(tag), 0)) + 1
    analytics = build_intervention_ledger_analytics()
    compact_summary = dict(analytics.get("compact_summary", {}))
    recommendations = dict(compact_summary.get("recommendations", {}))
    return {
        "benchmark_summary": load_latest_benchmark_summary(),
        "recent_proposal_type_counts": proposal_type_counts,
        "recent_failure_tags": recent_failure_tags,
        "intervention_analytics": {
            "proposal_count": int(analytics.get("proposal_count", 0)),
            "best_performing_proposal_families": list(compact_summary.get("best_performing_proposal_families", [])),
            "most_dormant_proposal_families": list(compact_summary.get("most_dormant_proposal_families", [])),
            "suggested_next_templates": list(recommendations.get("suggested_next_templates", [])),
            "deprioritized_templates": list(recommendations.get("deprioritized_templates", [])),
        },
    }


def _find_benchmark_variant(summary: Dict[str, Any], variant_name: str) -> Dict[str, Any]:
    sweep = dict(summary.get("policy_sweep_analysis", {}))
    for variant in list(sweep.get("variants", [])):
        if str(variant.get("name")) == str(variant_name):
            return dict(variant)
    return {}


def forecast_proposal(proposal: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    benchmark_summary = dict(context.get("benchmark_summary", {}))
    mechanism = dict(proposal.get("mechanism", {}))
    proposal_type = str(proposal.get("proposal_type", ""))
    template_name = str(proposal.get("template_name", ""))
    analytics = dict(context.get("intervention_analytics", {}))
    forecast = {
        "predicted_benchmark_improvement_sign": "unknown",
        "predicted_projection_safety_effect_sign": "unknown",
        "predicted_live_activation_likelihood": "unknown",
        "predicted_target_family_usefulness": "unknown",
        "confidence": 0.25,
        "uncertainty": 0.75,
        "inputs_used": {
            "has_benchmark_summary": bool(benchmark_summary),
            "recent_proposal_type_counts": dict(context.get("recent_proposal_type_counts", {})),
            "recent_failure_tags": dict(context.get("recent_failure_tags", {})),
            "has_intervention_analytics": bool(analytics),
        },
    }
    if proposal_type == "routing_rule":
        variant_name = str(mechanism.get("benchmark_variant", ""))
        variant = _find_benchmark_variant(benchmark_summary, variant_name)
        comparison = dict(variant.get("comparison_to_baseline", {}))
        recommendation = dict(variant.get("recommendation", {}))
        delta_match = float(comparison.get("policy_match_rate_delta") or 0.0)
        delta_false_safe = float(comparison.get("false_safe_projection_rate_delta") or 0.0)
        gain_goal_delta = float(recommendation.get("gain_goal_match_delta") or 0.0)
        if delta_match > 0.0:
            forecast["predicted_benchmark_improvement_sign"] = "positive"
        elif delta_match < 0.0:
            forecast["predicted_benchmark_improvement_sign"] = "negative"
        else:
            forecast["predicted_benchmark_improvement_sign"] = "neutral"
        if delta_false_safe <= 0.0:
            forecast["predicted_projection_safety_effect_sign"] = "neutral_or_better"
        elif delta_false_safe <= 0.03:
            forecast["predicted_projection_safety_effect_sign"] = "slightly_negative"
        else:
            forecast["predicted_projection_safety_effect_sign"] = "negative"
        forecast["predicted_target_family_usefulness"] = "positive" if gain_goal_delta > 0.0 else "uncertain"
        if str(context.get("recent_failure_tags", {}).get("dormant_live_override", "")):
            forecast["predicted_live_activation_likelihood"] = "low"
        else:
            forecast["predicted_live_activation_likelihood"] = "low"
        forecast["confidence"] = 0.70 if variant else 0.45
        forecast["uncertainty"] = 1.0 - float(forecast["confidence"])
        forecast["benchmark_variant"] = variant_name
        forecast["benchmark_support"] = {
            "policy_match_rate_delta": comparison.get("policy_match_rate_delta"),
            "false_safe_projection_rate_delta": comparison.get("false_safe_projection_rate_delta"),
            "gain_goal_match_delta": recommendation.get("gain_goal_match_delta"),
            "safe_to_consider_later": recommendation.get("safe_to_consider_later"),
        }
    suggested_templates = {
        str(item.get("template_name")): dict(item)
        for item in list(analytics.get("suggested_next_templates", []))
        if isinstance(item, dict)
    }
    deprioritized_templates = {
        str(item.get("template_name")): dict(item)
        for item in list(analytics.get("deprioritized_templates", []))
        if isinstance(item, dict)
    }
    if template_name in suggested_templates:
        forecast["history_prior"] = {
            "status": "recommended",
            "reason": str(suggested_templates[template_name].get("reason", "positive proposal history")),
        }
        forecast["confidence"] = min(0.9, float(forecast["confidence"]) + 0.05)
        forecast["uncertainty"] = 1.0 - float(forecast["confidence"])
    elif template_name in deprioritized_templates:
        forecast["history_prior"] = {
            "status": "deprioritized",
            "reason": str(deprioritized_templates[template_name].get("reason", "negative proposal history")),
        }
        forecast["confidence"] = max(0.2, float(forecast["confidence"]) - 0.15)
        forecast["uncertainty"] = 1.0 - float(forecast["confidence"])
    return forecast

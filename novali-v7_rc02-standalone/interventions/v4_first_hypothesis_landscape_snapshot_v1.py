from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .analytics import build_intervention_ledger_analytics
from .ledger import intervention_data_dir, load_latest_snapshots


ROOT_DIR = Path(__file__).resolve().parents[1]
HANDOFF_STATUS_PATH = ROOT_DIR / "data" / "version_handoff_status.json"
ACTIVE_STATUS_PATH = ROOT_DIR / "ACTIVE_VERSION_STATUS.md"
PROPOSAL_LOOP_PATH = ROOT_DIR / "experiments" / "proposal_learning_loop.py"
BENCHMARK_PACK_ROOT = ROOT_DIR / "benchmarks" / "trusted_benchmark_pack_v1"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _load_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _count_config_prefixes(source_text: str) -> dict[str, Any]:
    field_names = re.findall(
        r"^\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*[A-Za-z_][A-Za-z0-9_\[\], ]*\s*=",
        source_text,
        flags=re.MULTILINE,
    )
    prefixes = {
        "wm_": 0,
        "plan_": 0,
        "self_improve_": 0,
        "adoption_": 0,
        "social_conf_": 0,
        "proposal_": 0,
    }
    for field_name in field_names:
        for prefix in prefixes:
            if str(field_name).startswith(prefix):
                prefixes[prefix] += 1
    toggles = {
        "use_world_model": "use_world_model" in source_text,
        "use_planning": "use_planning" in source_text,
        "enable_self_improvement": "enable_self_improvement" in source_text,
    }
    return {
        "config_field_count": int(len(field_names)),
        "prefix_counts": prefixes,
        "toggles": toggles,
        "architecture_surface_present": bool(
            prefixes["wm_"] > 0
            and prefixes["plan_"] > 0
            and prefixes["self_improve_"] > 0
            and toggles["use_world_model"]
            and toggles["use_planning"]
            and toggles["enable_self_improvement"]
        ),
    }


def _benchmark_pack_summary(pack_root: Path) -> dict[str, Any]:
    scenario_root = pack_root / "scenarios"
    family_counts: dict[str, int] = {}
    if scenario_root.exists():
        for family_dir in sorted(item for item in scenario_root.iterdir() if item.is_dir()):
            family_counts[family_dir.name] = int(len(list(family_dir.glob("*.json"))))
    return {
        "pack_exists": pack_root.exists(),
        "scenario_family_count": int(len(family_counts)),
        "scenario_counts_by_family": family_counts,
        "total_scenarios": int(sum(family_counts.values())),
        "has_runner": bool((pack_root / "runner.py").exists()),
        "has_manifest": bool((pack_root / "manifest.json").exists()),
    }


def _projected_score(branch_state: str, value: float, risk: float, reversibility: float) -> float:
    openness_bonus = 0.12 if branch_state == "open" else (-0.18 if branch_state == "closed" else 0.0)
    return round(float(value - risk * 0.35 + reversibility * 0.15 + openness_bonus), 3)


def run_probe(cfg, proposal, *, rounds, seeds):
    del cfg, rounds, seeds
    from . import runner as r

    hardening_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.swap_c_incumbent_hardening_probe_v1"
    )
    frontier_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    invariance_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.safe_trio_false_safe_invariance_snapshot_v1"
    )
    coverage_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.swap_c_family_coverage_snapshot_v1"
    )
    seed_context_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.seed_context_shift_snapshot"
    )
    benchmark_context_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.benchmark_context_availability_snapshot"
    )
    routing_artifact = r._load_latest_diagnostic_artifact_by_template(
        "routing_rule.slice_targeted_benchmark_sweep_v1"
    )
    if not all(
        [
            hardening_artifact,
            frontier_artifact,
            invariance_artifact,
            coverage_artifact,
            seed_context_artifact,
            benchmark_context_artifact,
            routing_artifact,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: v4 landscape snapshot requires the carried-forward hardening, frontier, invariance, family-coverage, context-availability, and routing-control artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot rank the first v4 hypothesis without the carried-forward diagnostic set",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    benchmark_pack = _benchmark_pack_summary(BENCHMARK_PACK_ROOT)
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)
    architecture_surface = _count_config_prefixes(proposal_loop_text)

    hardening_conclusions = dict(hardening_artifact.get("diagnostic_conclusions", {}))
    frontier_conclusions = dict(frontier_artifact.get("diagnostic_conclusions", {}))
    coverage_conclusions = dict(coverage_artifact.get("diagnostic_conclusions", {}))
    routing_conclusions = dict(routing_artifact.get("diagnostic_conclusions", {}))
    seed_context_conclusions = dict(seed_context_artifact.get("diagnostic_conclusions", {}))
    benchmark_context_conclusions = dict(benchmark_context_artifact.get("diagnostic_conclusions", {}))

    carried_forward_baseline = dict(handoff_status.get("carried_forward_baseline", {}))
    persistence_family = dict(dict(coverage_artifact.get("family_coverage_report", {})).get("persistence", {}))
    under_cap_critic_exhausted = not bool(hardening_conclusions.get("productive_under_cap_critic_work_left", True))
    hard_discrete_frontier = str(frontier_conclusions.get("frontier_classification", "")) == "hard_discrete_accounting_boundary"
    no_control_headroom = not bool(frontier_conclusions.get("benchmark_only_control_headroom_exists", True))
    routing_deferred = bool(frontier_conclusions.get("routing_deferred", False))
    availability_context_open = bool(
        str(seed_context_conclusions.get("collapse_driver", "")) == "low_candidate_count"
        and str(benchmark_context_conclusions.get("availability_driver", "")) == "scarcity"
    )
    architecture_branch_open = bool(
        under_cap_critic_exhausted
        and hard_discrete_frontier
        and no_control_headroom
        and architecture_surface.get("architecture_surface_present", False)
    )
    persistence_upstream_healthy = bool(int(persistence_family.get("safe_pool_benchmark_like_count", 0) or 0) > 0)
    persistence_excluded_at_selection = str(persistence_family.get("absence_stage", "")) == "absent_only_at_selection"

    candidate_rows = [
        {
            "rank": 1,
            "candidate_branch": "architecture/branch-structure branch",
            "state": "open" if architecture_branch_open else "closed",
            "why_open_or_closed": (
                "open because novali-v3 exhausted under-cap critic refinement, the false-safe frontier is hard discrete, benchmark-only control headroom is not evidenced, and proposal_learning_loop exposes world-model, planning, self-improvement, proposal, and adoption architecture surface"
                if architecture_branch_open
                else "closed because the repo does not yet support a clean architecture opening beyond the carried-forward baseline"
            ),
            "dependency_on_novali_v3_conclusions": [
                "swap_C is stable and carried forward",
                "productive under-cap critic_split work is exhausted",
                "false-safe frontier is hard discrete",
                "benchmark-only control headroom is not evidenced",
            ],
            "projected_value": {"label": "high", "score": 0.93},
            "projected_risk": {"label": "medium", "score": 0.48},
            "reversibility": {"label": "high", "score": 0.87},
            "ownership_note": "No dedicated architecture proposal family exists yet in taxonomy, so the first ownable v4 move should be a memory_summary branch-design snapshot.",
            "projected_priority": _projected_score("open" if architecture_branch_open else "closed", 0.93, 0.48, 0.87),
        },
        {
            "rank": 2,
            "candidate_branch": "upstream availability/context branch",
            "state": "open_secondary" if availability_context_open else "closed",
            "why_open_or_closed": (
                "still open as a secondary hypothesis because earlier diagnostics tied collapse to scarcity and context shift, but it is not the immediate bottleneck under swap_C because persistence candidates are healthy upstream and only compressed at final selection"
                if availability_context_open
                else "closed because current evidence no longer shows upstream availability/context as the active bottleneck"
            ),
            "dependency_on_novali_v3_conclusions": [
                "seed_context_shift_snapshot localized collapse to low_candidate_count and safe_pool_scarcity",
                "benchmark_context_availability_snapshot localized absence to scarcity",
                "swap_c_family_coverage_snapshot showed persistence healthy upstream under the carried-forward baseline",
            ],
            "projected_value": {"label": "medium", "score": 0.67},
            "projected_risk": {"label": "medium_high", "score": 0.62},
            "reversibility": {"label": "medium", "score": 0.64},
            "ownership_note": "Best treated as a sub-hypothesis inside a larger v4 architecture/context-formation branch, not as a direct continuation of v3 tuning.",
            "projected_priority": _projected_score("open" if availability_context_open else "closed", 0.67, 0.62, 0.64),
        },
        {
            "rank": 3,
            "candidate_branch": "diagnostic/memory/governance branch",
            "state": "open",
            "why_open_or_closed": "open because v4 needs a safe way to formalize a new branch outside the exhausted v3 line, and memory_summary remains the most reversible currently ownable family in the repo",
            "dependency_on_novali_v3_conclusions": [
                "branch pause and carry-forward baseline are already formalized",
                "current recommendations are still dominated by legacy v3 template history rather than v4-specific branch design",
            ],
            "projected_value": {"label": "medium", "score": 0.71},
            "projected_risk": {"label": "low", "score": 0.18},
            "reversibility": {"label": "high", "score": 0.97},
            "ownership_note": "This is the safest immediate owner family for the first v4 move, even if the substantive hypothesis it serves is architecture-level.",
            "projected_priority": _projected_score("open", 0.71, 0.18, 0.97),
        },
        {
            "rank": 4,
            "candidate_branch": "benchmark/control characterization branch",
            "state": "closed",
            "why_open_or_closed": "closed because the carried-forward control characterization found no benchmark-only control headroom and the last routing/control retest produced zero safe pool, zero benchmark slice, and zero policy-match gain",
            "dependency_on_novali_v3_conclusions": [
                "false_safe_frontier_control_characterization_snapshot_v1 found benchmark_only_control_headroom_exists = false",
                "slice_targeted_benchmark_sweep_v1 collapsed to a zero benchmark slice",
            ],
            "projected_value": {"label": "low", "score": 0.16},
            "projected_risk": {"label": "medium", "score": 0.57},
            "reversibility": {"label": "high", "score": 0.9},
            "ownership_note": "This line is explicitly ruled out as the first v4 move unless new evidence changes the frontier diagnosis.",
            "projected_priority": _projected_score("closed", 0.16, 0.57, 0.9),
        },
        {
            "rank": 5,
            "candidate_branch": "continued under-cap critic_split line",
            "state": "closed",
            "why_open_or_closed": "closed because swap_C hardening found no productive under-cap critic work left and the frontier remains flat at trio size 3",
            "dependency_on_novali_v3_conclusions": [
                "swap_c_incumbent_hardening_probe_v1 found productive_under_cap_critic_work_left = false",
                "false_safe_frontier_control_characterization_snapshot_v1 found no safe benchmark-only control headroom either",
            ],
            "projected_value": {"label": "low", "score": 0.09},
            "projected_risk": {"label": "medium", "score": 0.52},
            "reversibility": {"label": "high", "score": 0.88},
            "ownership_note": "This is the exhausted novali-v3 line and should not own the first substantive v4 move.",
            "projected_priority": _projected_score("closed", 0.09, 0.52, 0.88),
        },
    ]

    best_first_hypothesis = "architecture-level upstream/context branch design outside the exhausted v3 under-cap critic line"
    recommended_next_family = "memory_summary"
    recommended_next_template = "memory_summary.v4_architecture_upstream_context_branch_snapshot_v1"
    recommended_next_rationale = (
        "the best open hypothesis is architecture-level and context-formation oriented, but the repo does not yet expose a dedicated architecture proposal family, so the narrowest safe first v4 move is a memory_summary design snapshot that formalizes that branch before any new intervention family is introduced"
    )

    branch_context = {
        "active_status_path": str(ACTIVE_STATUS_PATH),
        "handoff_status_path": str(HANDOFF_STATUS_PATH),
        "active_status_mentions_v4_active": "`novali-v4` is the active working version." in active_status_text,
        "handoff_active_version": str(handoff_status.get("active_working_version", "")),
        "handoff_frozen_version": str(handoff_status.get("frozen_fallback_reference_version", "")),
        "carried_forward_baseline": carried_forward_baseline,
    }
    benchmark_context = {
        "benchmark_pack_summary": benchmark_pack,
        "proposal_learning_loop_architecture_surface": architecture_surface,
        "available_proposal_families": [
            "score_reweight",
            "critic_split",
            "routing_rule",
            "memory_summary",
            "support_contract",
            "safety_veto_patch",
        ],
        "architecture_family_present_in_taxonomy": False,
    }
    recommendation_alignment = {
        "current_recommendation_top_templates": [
            str(item.get("template_name", ""))
            for item in list(recommendations.get("all_ranked_proposals", []))
            if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
        ][:8],
        "alignment_note": "the current recommender remains dominated by legacy v3 template history and does not yet express the v4 branch-pause / architecture-opening conclusion cleanly",
    }

    latest_snapshot_refs = {}
    for artifact in [
        hardening_artifact,
        frontier_artifact,
        invariance_artifact,
        coverage_artifact,
        seed_context_artifact,
        benchmark_context_artifact,
        routing_artifact,
    ]:
        proposal_id = str(artifact.get("proposal_id", ""))
        latest_snapshot_refs[str(artifact.get("template_name", ""))] = {
            "proposal_id": proposal_id,
            "ledger_revision": int(dict(latest_snapshots.get(proposal_id, {})).get("ledger_revision", 0) or 0),
        }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_first_hypothesis_landscape_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": branch_context,
        "benchmark_context": benchmark_context,
        "comparison_references": {
            "critic_split.swap_c_incumbent_hardening_probe_v1": {
                "diagnostic_conclusions": hardening_conclusions,
                "incumbent_robustness_report": dict(hardening_artifact.get("incumbent_robustness_report", {})),
            },
            "memory_summary.false_safe_frontier_control_characterization_snapshot_v1": {
                "diagnostic_conclusions": frontier_conclusions,
            },
            "memory_summary.safe_trio_false_safe_invariance_snapshot_v1": {
                "diagnostic_conclusions": dict(invariance_artifact.get("diagnostic_conclusions", {})),
            },
            "memory_summary.swap_c_family_coverage_snapshot_v1": {
                "diagnostic_conclusions": coverage_conclusions,
                "family_coverage_report": dict(coverage_artifact.get("family_coverage_report", {})),
            },
            "memory_summary.seed_context_shift_snapshot": {
                "diagnostic_conclusions": seed_context_conclusions,
            },
            "memory_summary.benchmark_context_availability_snapshot": {
                "diagnostic_conclusions": benchmark_context_conclusions,
            },
            "routing_rule.slice_targeted_benchmark_sweep_v1": {
                "diagnostic_conclusions": routing_conclusions,
                "benchmark_control_metrics": dict(routing_artifact.get("benchmark_control_metrics", {})),
            },
        },
        "recommendation_alignment": recommendation_alignment,
        "ranked_hypothesis_landscape": candidate_rows,
        "decision_recommendation": {
            "best_first_hypothesis": str(best_first_hypothesis),
            "recommended_next_family": str(recommended_next_family),
            "recommended_next_template": str(recommended_next_template),
            "rationale": str(recommended_next_rationale),
        },
        "branch_snapshot_refs": latest_snapshot_refs,
        "observability_gain": {
            "passed": True,
            "reason": "the snapshot combines v4 handoff state, carried-forward frontier diagnostics, old upstream context artifacts, current recommendations, and the proposal-loop architecture surface to rank only v4-relevant next directions",
            "candidate_branch_count": int(len(candidate_rows)),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot identifies which branch directions remain open after the v3 pause instead of assuming the analytics recommender still points at the right family",
            "under_cap_critic_exhausted": bool(under_cap_critic_exhausted),
            "benchmark_only_control_headroom_exists": bool(not no_control_headroom),
            "architecture_branch_open": bool(architecture_branch_open),
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.38
                    + 0.18 * int(under_cap_critic_exhausted)
                    + 0.16 * int(hard_discrete_frontier)
                    + 0.12 * int(no_control_headroom)
                    + 0.08 * int(persistence_upstream_healthy and persistence_excluded_at_selection)
                    + 0.08 * int(architecture_surface.get("architecture_surface_present", False))
                )
            ),
            "reason": "the snapshot cleanly separates closed v3 continuation lines from the first still-open v4 hypothesis space",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "diagnostic-only v4 hypothesis landscape snapshot with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(recommended_next_template),
            "reason": str(recommended_next_rationale),
        },
        "diagnostic_conclusions": {
            "best_first_hypothesis": str(best_first_hypothesis),
            "upstream_availability_context_branch_open": bool(availability_context_open),
            "diagnostic_memory_branch_open": True,
            "architecture_branch_open": bool(architecture_branch_open),
            "benchmark_control_characterization_branch_open": False,
            "continued_under_cap_critic_split_open": False,
            "recommended_next_family": str(recommended_next_family),
            "recommended_next_template": str(recommended_next_template),
            "routing_deferred": bool(routing_deferred),
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_v4_first_hypothesis_landscape_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the first v4 hypothesis landscape was ranked outside the exhausted v3 under-cap critic line",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }

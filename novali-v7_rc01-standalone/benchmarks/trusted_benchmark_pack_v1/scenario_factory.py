from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


PACK_NAME = "trusted_benchmark_pack_v1"
PACK_VERSION = "1.0.0"
SCHEMA_VERSION = 1
SCENARIOS_PER_FAMILY = 12
FAMILIES = [
    "projection",
    "gain_goal_conflict",
    "persistence",
    "recovery",
    "calibration",
]


def _decision_scoring(
    *,
    gain_weight: float,
    projection_margin_weight: float,
    goal_margin_weight: float,
    projection_bad_penalty: float,
    gain_bad_penalty: float,
    goal_bad_penalty: float,
    reject_bonus: float = 0.0,
    provisional_bonus: float = 0.0,
    full_bonus: float = 0.0,
) -> Dict[str, float]:
    return {
        "gain_weight": gain_weight,
        "projection_margin_weight": projection_margin_weight,
        "goal_margin_weight": goal_margin_weight,
        "projection_bad_penalty": projection_bad_penalty,
        "gain_bad_penalty": gain_bad_penalty,
        "goal_bad_penalty": goal_bad_penalty,
        "status_bonus_reject": reject_bonus,
        "status_bonus_provisional": provisional_bonus,
        "status_bonus_full": full_bonus,
    }


FAMILY_VARIANTS: Dict[str, List[Dict[str, Any]]] = {
    "projection": [
        {
            "name": "mild_projection_watch",
            "proposer_offset": 0,
            "env": {"noise_scale": 0.012, "steps": 72, "horizon_pad": 8},
            "candidate_overrides": {"projection_error_bias": 0.10},
            "context_overrides": {"projection_recent_bias": 0.10, "projection_trend_bias": 0.04},
            "decision_scoring": _decision_scoring(
                gain_weight=0.90,
                projection_margin_weight=1.30,
                goal_margin_weight=0.40,
                projection_bad_penalty=2.50,
                gain_bad_penalty=1.10,
                goal_bad_penalty=1.00,
            ),
        },
        {
            "name": "projection_edge",
            "proposer_offset": 1,
            "env": {"noise_scale": 0.016, "steps": 80, "horizon_pad": 10},
            "candidate_overrides": {"projection_error_bias": 0.18, "dummy_improvement_bias": -0.03},
            "context_overrides": {"projection_recent_bias": 0.18, "projection_trend_bias": 0.08, "instability_bias": 0.08},
            "decision_scoring": _decision_scoring(
                gain_weight=0.80,
                projection_margin_weight=1.45,
                goal_margin_weight=0.35,
                projection_bad_penalty=2.75,
                gain_bad_penalty=1.00,
                goal_bad_penalty=0.95,
            ),
        },
        {
            "name": "projection_shock",
            "proposer_offset": 2,
            "env": {"noise_scale": 0.020, "steps": 88, "horizon_pad": 12},
            "candidate_overrides": {"projection_error_bias": 0.24, "local_score_bias": -0.02},
            "context_overrides": {"projection_recent_bias": 0.24, "projection_trend_bias": 0.10, "t2_recent_bias": 0.10},
            "decision_scoring": _decision_scoring(
                gain_weight=0.75,
                projection_margin_weight=1.60,
                goal_margin_weight=0.30,
                projection_bad_penalty=3.00,
                gain_bad_penalty=1.05,
                goal_bad_penalty=1.00,
            ),
        },
        {
            "name": "projection_rebound",
            "proposer_offset": 0,
            "env": {"noise_scale": 0.014, "steps": 76, "horizon_pad": 10},
            "candidate_overrides": {"projection_error_bias": 0.14, "dummy_improvement_bias": 0.02},
            "context_overrides": {"projection_recent_bias": 0.14, "c3_recent_bias": 0.06, "t3_recent_bias": 0.04},
            "decision_scoring": _decision_scoring(
                gain_weight=0.95,
                projection_margin_weight=1.35,
                goal_margin_weight=0.40,
                projection_bad_penalty=2.55,
                gain_bad_penalty=1.00,
                goal_bad_penalty=0.95,
                provisional_bonus=0.05,
            ),
        },
    ],
    "gain_goal_conflict": [
        {
            "name": "goal_fragile",
            "proposer_offset": 1,
            "env": {"noise_scale": 0.011, "steps": 74, "horizon_pad": 8},
            "candidate_overrides": {"dummy_improvement_bias": 0.06, "local_score_bias": 0.02},
            "context_overrides": {"goal_pressure_bias": 0.18},
            "eval_overrides": {"goal_weight": 0.18, "social_gain": 0.025},
            "decision_scoring": _decision_scoring(
                gain_weight=1.00,
                projection_margin_weight=0.60,
                goal_margin_weight=1.20,
                projection_bad_penalty=1.40,
                gain_bad_penalty=1.60,
                goal_bad_penalty=2.20,
            ),
        },
        {
            "name": "gain_temptation",
            "proposer_offset": 2,
            "env": {"noise_scale": 0.012, "steps": 78, "horizon_pad": 8},
            "candidate_overrides": {"dummy_improvement_bias": 0.10, "local_score_bias": 0.04},
            "context_overrides": {"goal_pressure_bias": 0.14, "recent_realized_bias": 10.0},
            "eval_overrides": {"goal_weight": 0.20, "social_gain": 0.030},
            "decision_scoring": _decision_scoring(
                gain_weight=1.10,
                projection_margin_weight=0.55,
                goal_margin_weight=1.15,
                projection_bad_penalty=1.35,
                gain_bad_penalty=1.75,
                goal_bad_penalty=2.35,
                provisional_bonus=0.04,
            ),
        },
        {
            "name": "conflict_balanced",
            "proposer_offset": 0,
            "env": {"noise_scale": 0.013, "steps": 82, "horizon_pad": 10},
            "candidate_overrides": {"dummy_improvement_bias": 0.04, "local_score_bias": -0.01},
            "context_overrides": {"goal_pressure_bias": 0.22, "instability_bias": 0.05},
            "eval_overrides": {"goal_weight": 0.22, "social_gain": 0.020},
            "decision_scoring": _decision_scoring(
                gain_weight=1.00,
                projection_margin_weight=0.60,
                goal_margin_weight=1.30,
                projection_bad_penalty=1.45,
                gain_bad_penalty=1.80,
                goal_bad_penalty=2.40,
            ),
        },
        {
            "name": "goal_priority",
            "proposer_offset": 1,
            "env": {"noise_scale": 0.010, "steps": 76, "horizon_pad": 8},
            "candidate_overrides": {"dummy_improvement_bias": 0.02, "local_score_bias": 0.01},
            "context_overrides": {"goal_pressure_bias": 0.28, "c2_recent_bias": 0.05},
            "eval_overrides": {"goal_weight": 0.24, "social_gain": 0.018},
            "decision_scoring": _decision_scoring(
                gain_weight=0.95,
                projection_margin_weight=0.55,
                goal_margin_weight=1.40,
                projection_bad_penalty=1.35,
                gain_bad_penalty=1.55,
                goal_bad_penalty=2.55,
                reject_bonus=0.03,
            ),
        },
    ],
    "persistence": [
        {
            "name": "weak_identity_seed",
            "proposer_offset": 0,
            "env": {"noise_scale": 0.010, "steps": 70, "horizon_pad": 8},
            "context_overrides": {"moving_average_bias": 0.08, "persistence_streak_delta": 1, "retained_evidence_bias": 0.10},
            "decision_scoring": _decision_scoring(
                gain_weight=0.95,
                projection_margin_weight=0.80,
                goal_margin_weight=0.75,
                projection_bad_penalty=1.80,
                gain_bad_penalty=1.25,
                goal_bad_penalty=1.20,
                provisional_bonus=0.10,
                full_bonus=0.05,
            ),
        },
        {
            "name": "streak_consolidation",
            "proposer_offset": 0,
            "env": {"noise_scale": 0.011, "steps": 74, "horizon_pad": 8},
            "context_overrides": {"moving_average_bias": 0.12, "persistence_streak_delta": 2, "retained_evidence_bias": 0.18, "retained_rounds_delta": 1},
            "decision_scoring": _decision_scoring(
                gain_weight=0.95,
                projection_margin_weight=0.78,
                goal_margin_weight=0.75,
                projection_bad_penalty=1.85,
                gain_bad_penalty=1.20,
                goal_bad_penalty=1.20,
                provisional_bonus=0.14,
                full_bonus=0.06,
            ),
        },
        {
            "name": "persistent_low_gain",
            "proposer_offset": 1,
            "env": {"noise_scale": 0.010, "steps": 78, "horizon_pad": 8},
            "candidate_overrides": {"dummy_improvement_bias": -0.02},
            "context_overrides": {"moving_average_bias": 0.15, "persistence_streak_delta": 3, "retained_evidence_bias": 0.24, "retained_rounds_delta": 2},
            "decision_scoring": _decision_scoring(
                gain_weight=0.90,
                projection_margin_weight=0.82,
                goal_margin_weight=0.78,
                projection_bad_penalty=1.90,
                gain_bad_penalty=1.22,
                goal_bad_penalty=1.25,
                provisional_bonus=0.16,
                full_bonus=0.05,
            ),
        },
        {
            "name": "identity_reaffirmation",
            "proposer_offset": 2,
            "env": {"noise_scale": 0.010, "steps": 80, "horizon_pad": 10},
            "candidate_overrides": {"dummy_improvement_bias": 0.03, "local_score_bias": 0.02},
            "context_overrides": {"moving_average_bias": 0.18, "persistence_streak_delta": 2, "retained_evidence_bias": 0.20, "retained_rounds_delta": 2, "c3_recent_bias": 0.08},
            "decision_scoring": _decision_scoring(
                gain_weight=0.98,
                projection_margin_weight=0.80,
                goal_margin_weight=0.80,
                projection_bad_penalty=1.85,
                gain_bad_penalty=1.18,
                goal_bad_penalty=1.20,
                provisional_bonus=0.12,
                full_bonus=0.08,
            ),
        },
    ],
    "recovery": [
        {
            "name": "rollback_scar_tight",
            "proposer_offset": 2,
            "env": {"noise_scale": 0.013, "steps": 76, "horizon_pad": 10},
            "candidate_overrides": {"dummy_improvement_bias": -0.04},
            "context_overrides": {"recent_realized_bias": -20.0, "rollback_rate_bias": 0.22, "instability_bias": 0.08},
            "decision_scoring": _decision_scoring(
                gain_weight=0.92,
                projection_margin_weight=0.95,
                goal_margin_weight=0.82,
                projection_bad_penalty=2.10,
                gain_bad_penalty=1.55,
                goal_bad_penalty=1.40,
                reject_bonus=0.10,
            ),
        },
        {
            "name": "recovery_probe",
            "proposer_offset": 1,
            "env": {"noise_scale": 0.012, "steps": 74, "horizon_pad": 8},
            "candidate_overrides": {"dummy_improvement_bias": 0.01},
            "context_overrides": {"recent_realized_bias": -12.0, "rollback_rate_bias": 0.16, "instability_bias": 0.06, "retained_evidence_bias": 0.08},
            "decision_scoring": _decision_scoring(
                gain_weight=0.95,
                projection_margin_weight=0.92,
                goal_margin_weight=0.80,
                projection_bad_penalty=2.00,
                gain_bad_penalty=1.45,
                goal_bad_penalty=1.35,
                provisional_bonus=0.06,
                reject_bonus=0.05,
            ),
        },
        {
            "name": "cautious_reengage",
            "proposer_offset": 0,
            "env": {"noise_scale": 0.011, "steps": 78, "horizon_pad": 8},
            "candidate_overrides": {"dummy_improvement_bias": 0.02, "local_score_bias": 0.01},
            "context_overrides": {"recent_realized_bias": -8.0, "rollback_rate_bias": 0.12, "instability_bias": 0.04, "c2_recent_bias": 0.05},
            "decision_scoring": _decision_scoring(
                gain_weight=0.98,
                projection_margin_weight=0.90,
                goal_margin_weight=0.82,
                projection_bad_penalty=1.95,
                gain_bad_penalty=1.38,
                goal_bad_penalty=1.30,
                provisional_bonus=0.08,
                reject_bonus=0.04,
            ),
        },
        {
            "name": "recovery_stability",
            "proposer_offset": 2,
            "env": {"noise_scale": 0.012, "steps": 82, "horizon_pad": 10},
            "candidate_overrides": {"dummy_improvement_bias": -0.01},
            "context_overrides": {"recent_realized_bias": -14.0, "rollback_rate_bias": 0.18, "instability_bias": 0.05, "c3_recent_bias": 0.07},
            "decision_scoring": _decision_scoring(
                gain_weight=0.94,
                projection_margin_weight=0.98,
                goal_margin_weight=0.84,
                projection_bad_penalty=2.05,
                gain_bad_penalty=1.48,
                goal_bad_penalty=1.32,
                provisional_bonus=0.07,
                reject_bonus=0.06,
            ),
        },
    ],
    "calibration": [
        {
            "name": "forecast_gain_check",
            "proposer_offset": 1,
            "env": {"noise_scale": 0.011, "steps": 72, "horizon_pad": 8},
            "candidate_overrides": {"dummy_improvement_bias": 0.05},
            "context_overrides": {"wm_quality_penalty_bias": 0.10, "projection_recent_bias": 0.04},
            "decision_scoring": _decision_scoring(
                gain_weight=1.00,
                projection_margin_weight=0.85,
                goal_margin_weight=0.70,
                projection_bad_penalty=1.75,
                gain_bad_penalty=1.40,
                goal_bad_penalty=1.25,
                provisional_bonus=0.04,
            ),
        },
        {
            "name": "forecast_projection_check",
            "proposer_offset": 1,
            "env": {"noise_scale": 0.013, "steps": 76, "horizon_pad": 10},
            "candidate_overrides": {"projection_error_bias": 0.12},
            "context_overrides": {"wm_quality_penalty_bias": 0.14, "projection_recent_bias": 0.12, "projection_trend_bias": 0.05},
            "decision_scoring": _decision_scoring(
                gain_weight=0.96,
                projection_margin_weight=1.05,
                goal_margin_weight=0.72,
                projection_bad_penalty=2.10,
                gain_bad_penalty=1.28,
                goal_bad_penalty=1.22,
            ),
        },
        {
            "name": "forecast_uncertainty_check",
            "proposer_offset": 2,
            "env": {"noise_scale": 0.014, "steps": 80, "horizon_pad": 10},
            "candidate_overrides": {"dummy_improvement_bias": 0.01, "projection_error_bias": 0.08},
            "context_overrides": {"wm_quality_penalty_bias": 0.18, "rollback_rate_bias": 0.10, "instability_bias": 0.05},
            "decision_scoring": _decision_scoring(
                gain_weight=0.96,
                projection_margin_weight=0.95,
                goal_margin_weight=0.72,
                projection_bad_penalty=1.95,
                gain_bad_penalty=1.35,
                goal_bad_penalty=1.25,
            ),
        },
        {
            "name": "forecast_balance_check",
            "proposer_offset": 0,
            "env": {"noise_scale": 0.012, "steps": 78, "horizon_pad": 10},
            "candidate_overrides": {"dummy_improvement_bias": 0.03, "local_score_bias": 0.01},
            "context_overrides": {"wm_quality_penalty_bias": 0.12, "c2_recent_bias": 0.05, "c3_recent_bias": 0.05},
            "decision_scoring": _decision_scoring(
                gain_weight=0.98,
                projection_margin_weight=0.90,
                goal_margin_weight=0.75,
                projection_bad_penalty=1.85,
                gain_bad_penalty=1.32,
                goal_bad_penalty=1.22,
                provisional_bonus=0.04,
            ),
        },
    ],
}


def build_frozen_scenarios() -> List[Dict[str, Any]]:
    scenarios: List[Dict[str, Any]] = []
    base_seed = 41000
    for family_idx, family in enumerate(FAMILIES):
        variants = FAMILY_VARIANTS[family]
        for variant_idx, variant in enumerate(variants):
            for target in range(3):
                proposer = int((target + int(variant["proposer_offset"])) % 3)
                scenario_idx = len([s for s in scenarios if s["family"] == family]) + 1
                scenario_id = f"{family}_{scenario_idx:02d}"
                seed = int(base_seed + 1000 * family_idx + 100 * variant_idx + 7 * target + proposer)
                scenarios.append(
                    {
                        "id": scenario_id,
                        "version": SCHEMA_VERSION,
                        "pack_version": PACK_VERSION,
                        "family": family,
                        "description": f"{family} scenario {scenario_idx:02d}: {variant['name']} target={target} proposer={proposer}",
                        "target_agent": int(target),
                        "proposer": int(proposer),
                        "seed": seed,
                        "variant_name": str(variant["name"]),
                        "env": dict(variant.get("env", {})),
                        "eval_overrides": dict(variant.get("eval_overrides", {})),
                        "candidate_overrides": dict(variant.get("candidate_overrides", {})),
                        "context_overrides": dict(variant.get("context_overrides", {})),
                        "decision_scoring": dict(variant["decision_scoring"]),
                        "tags": [family, str(variant["name"])],
                    }
                )
    return scenarios


def build_manifest() -> Dict[str, Any]:
    return {
        "name": PACK_NAME,
        "version": PACK_VERSION,
        "schema_version": SCHEMA_VERSION,
        "frozen": True,
        "deterministic_seed_base": 41000,
        "scenario_count_total": len(build_frozen_scenarios()),
        "scenario_count_per_family": {family: SCENARIOS_PER_FAMILY for family in FAMILIES},
        "families": list(FAMILIES),
        "runner_entrypoint": "python -m benchmarks.trusted_benchmark_pack_v1.runner",
        "rubrics": [
            "rubrics/score_projection.py",
            "rubrics/score_gain_goal.py",
            "rubrics/score_persistence.py",
        ],
        "reports": {
            "summary": "reports/latest_summary.json",
            "detailed": "reports/latest_detailed.json",
        },
    }


def write_frozen_pack(pack_dir: Path) -> None:
    pack_dir.mkdir(parents=True, exist_ok=True)
    scenarios_dir = pack_dir / "scenarios"
    reports_dir = pack_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    for family in FAMILIES:
        (scenarios_dir / family).mkdir(parents=True, exist_ok=True)

    manifest_path = pack_dir / "manifest.json"
    manifest_path.write_text(json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    scenarios = build_frozen_scenarios()
    for scenario in scenarios:
        family = str(scenario["family"])
        scenario_path = scenarios_dir / family / f"{scenario['id']}.json"
        scenario_path.write_text(json.dumps(scenario, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary_path = reports_dir / "latest_summary.json"
    if not summary_path.exists():
        summary_path.write_text(
            json.dumps(
                {
                    "benchmark_pack": PACK_NAME,
                    "version": PACK_VERSION,
                    "status": "not_run",
                    "generated_at": None,
                    "summary": {},
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    detailed_path = reports_dir / "latest_detailed.json"
    if not detailed_path.exists():
        detailed_path.write_text(
            json.dumps(
                {
                    "benchmark_pack": PACK_NAME,
                    "version": PACK_VERSION,
                    "status": "not_run",
                    "generated_at": None,
                    "results": [],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    write_frozen_pack(Path(__file__).resolve().parent)

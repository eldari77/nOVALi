"""A bounded feedback-repair episode with fresh-process retention checks.

This evaluates controller behavior, not autonomous authorship or general skill
transfer. It never writes live autonomy state or grants promotion authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import torch

from agents.self_improvement import SelfImprovementConfig, SelfImprovementController


def _controller() -> SelfImprovementController:
    return SelfImprovementController(SelfImprovementConfig(), {"policy_adapter.A": torch.zeros(2, 2)})


def _verify_checkpoint(path: Path, expected_hash: str) -> dict[str, Any]:
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
        raise ValueError("checkpoint content hash mismatch")
    restored = _controller()
    restored.load_state_dict(torch.load(path, map_location="cpu", weights_only=True), strict=True)
    # These observations were withheld from the episode's feedback update.
    withheld = {"mean_pe": 5.0, "goal_agreement": 0.1, "wm_loss": 0.8}
    restored_decision = restored.diagnose(withheld)
    neutral_decision = _controller().diagnose(withheld)
    retained = restored.failure_ema > 0 and restored.cooldown > 0 and restored.success_ema == 0
    later_decision_changed = (
        restored_decision["should_propose"] == 0
        and neutral_decision["should_propose"] == 1
    )
    before = (restored.success_ema, restored.failure_ema)
    # Task B: a group's gain cannot be attributed to an unapplied self patch.
    restored.record_outcome(dummy_improvement=0.4, dummy_score=0.95, adopted=False,
                            patch_size=0.05, realized_gain=0.7)
    unadopted_credited = restored.success_ema != before[0]
    original_failure_retained = restored.failure_ema == before[1]
    # Return to A's failure family with new magnitudes after B and restart.
    success_before = restored.success_ema
    restored.record_outcome(dummy_improvement=0.3, dummy_score=0.99, adopted=True,
                            patch_size=0.08, realized_gain=-0.1)
    original_rule_preserved = restored.success_ema <= success_before and restored.failure_ema > 0
    return {
        "fresh_process": True,
        "retained": retained,
        "later_decision_changed": later_decision_changed,
        "withheld_unadopted_gain_rejected": not unadopted_credited,
        "original_failure_retained_after_task_b": original_failure_retained,
        "original_regression_rule_preserved": original_rule_preserved,
        "retained_should_propose": restored_decision["should_propose"],
        "neutral_should_propose": neutral_decision["should_propose"],
        "passed": all((retained, later_decision_changed, not unadopted_credited,
                       original_failure_retained, original_rule_preserved)),
    }


def run_episode(output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = output.with_suffix(".pt")
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(71)
        controller = _controller()
        controller.record_outcome(dummy_improvement=0.5, dummy_score=0.9,
                                  adopted=True, patch_size=0.1, realized_gain=-0.2)
        repair_passed = controller.success_ema == 0 and controller.failure_ema > 0 and controller.cooldown > 0
        torch.save(controller.state_dict(), checkpoint)
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    process = subprocess.run(
        [sys.executable, "-B", "-m", "benchmarks.self_improvement_episode",
         "--resume", str(checkpoint.resolve()), "--expected-hash", checkpoint_hash],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
        timeout=45, check=True,
    )
    retention = json.loads(process.stdout)
    report = {
        "schema_name": "SelfImprovementRepairEpisode", "schema_version": 1,
        "scope": "software feedback repair and transfer of retained controller history",
        "autonomous_authorship_demonstrated": False,
        "grants_execution_authority": False,
        "baseline_bug": "optimistic trial score credited success despite a negative realized outcome",
        "baseline_success_credit": 0.0525,
        "baseline_provenance": "observed pre-repair red regression test; not re-executed by this runner",
        "candidate_success_credit": controller.success_ema,
        "candidate_failure_history": controller.failure_ema,
        "repair_passed": repair_passed,
        "checkpoint_file": checkpoint.name,
        "checkpoint_sha256": checkpoint_hash,
        "controller_source_sha256": hashlib.sha256(
            (Path(__file__).resolve().parents[1] / "agents/self_improvement.py").read_bytes()
        ).hexdigest(),
        "python_version": sys.version.split()[0], "torch_version": str(torch.__version__),
        "retention_and_transfer": retention,
        "passed": repair_passed and retention["passed"],
    }
    output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--expected-hash")
    args = parser.parse_args()
    if args.resume:
        if not args.expected_hash or args.output:
            parser.error("resume requires expected-hash and excludes output")
        report = _verify_checkpoint(args.resume, args.expected_hash)
    else:
        if not args.output:
            parser.error("output is required for a new episode")
        report = run_episode(args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

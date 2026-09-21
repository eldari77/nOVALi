"""Offline A -> B -> A reuse of acquired source facts across a fresh process.

This is a functional knowledge-reuse check, not an independently authored 9D
learning benchmark. It never grants authority or writes to live operator state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from operator_shell.source_evidence import _key, read_cached_evidence


def verify(root: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    from operator_shell import autonomy
    autonomy.initialize_autonomy_state(root)
    original = read_cached_evidence(root, [candidate])["rows"][0]
    target = {**candidate, "source_candidate_id": "official-withheld-task-b", "requested_row_id": "withheld-task-b"}
    required = ["manufacturer", "mpn", "unit_cost"]
    request = {"support_request_id": "support-withheld-b", "target_artifact": "bill_of_materials.json",
               "requested_rows": [{"requested_row_id": "withheld-task-b", "target_artifact": "bill_of_materials.json",
                                   "required_fields": required}], "uncovered_requested_row_ids": ["withheld-task-b"]}
    context = {**request, "direct_url_source_candidates": [target]}
    worker = autonomy._trusted_knowledge_retrieval_worker(root, context=context, provider_field_lane_request=request)
    reused = read_cached_evidence(root, [target])["rows"][0]
    returned = read_cached_evidence(root, [candidate])["rows"][0]
    # The unseen contract extension must remain blocked even with valid facts.
    request["requested_rows"][0]["required_fields"] = required + ["validation_fixture_ref"]
    strict = autonomy._trusted_knowledge_retrieval_worker(root, context=context, provider_field_lane_request=request)
    predicates = {
        "fresh_process": True,
        "withheld_task_b_accepted": worker["accepted_requested_row_ids"] == ["withheld-task-b"],
        "source_hash_retained": reused["source_content_sha256"] == original["source_content_sha256"],
        "source_age_preserved": reused["retrieved_at"] == original["retrieved_at"],
        "task_a_retained": returned == original,
        "unsupported_design_field_rejected": strict["accepted_requested_row_ids"] == [],
        "missing_design_field_still_uncovered": strict["uncovered_after_cheap_sources"] == ["withheld-task-b"],
    }
    return {**predicates, "passed": all(predicates.values()), "network_requests": 0,
            "source_content_sha256": original["source_content_sha256"], "source_candidate_id": candidate["source_candidate_id"]}


def run(root: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    original = read_cached_evidence(root, [candidate])["rows"][0]
    with tempfile.TemporaryDirectory() as tmp:
        isolated = Path(tmp)
        source_dir = root / "conveyor/source_evidence_cache"
        target_dir = isolated / "conveyor/source_evidence_cache"
        target_dir.mkdir(parents=True)
        receipt = source_dir / f"{_key(candidate)}.json"
        shutil.copyfile(receipt, target_dir / receipt.name)
        content = source_dir / f"{original['source_content_sha256']}.html"
        if not content.exists():
            content = source_dir / f"{_key(candidate)}.html"
        shutil.copyfile(content, target_dir / content.name)
        candidate_file = isolated / "candidate.json"
        candidate_file.write_text(json.dumps(candidate), encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "benchmarks.source_evidence_transfer", "--resume", str(isolated),
             "--candidate", str(candidate_file)],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=45, check=True,
        )
        report = json.loads(completed.stdout)
    return {"schema_name": "SourceEvidenceTransferEpisode", "schema_version": 1,
            "scope": "retained factual evidence reused by the normal acquisition worker on a new contract",
            "general_9d_learning_demonstrated": False, "grants_execution_authority": False,
            "python_version": sys.version.split()[0], "verification": report, "passed": report["passed"],
            "extractor_source_sha256": hashlib.sha256((Path(__file__).resolve().parents[1] / "operator_shell/source_evidence.py").read_bytes()).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-root", type=Path)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--candidate", type=Path)
    args = parser.parse_args()
    if args.resume:
        report = verify(args.resume, json.loads(args.candidate.read_text(encoding="utf-8")))
    else:
        if not all((args.operator_root, args.adapter, args.output)):
            parser.error("operator-root, adapter and output are required")
        config = json.loads(args.adapter.read_text(encoding="utf-8"))
        candidates = config.get("source_candidates", [])
        if len(candidates) != 1:
            parser.error("episode adapter must bind exactly one candidate")
        report = run(args.operator_root, candidates[0])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

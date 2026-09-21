from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .governance_memory_execution_gate_v1 import build_execution_permission
from .ledger import intervention_data_dir, intervention_ledger_path, load_latest_snapshots
from .taxonomy import normalize_evaluation_plan, proposal_evaluation_semantics


HARMFUL_FAILURE_TAGS = {
    "projection_false_safe",
    "benchmark_regression",
    "persistence_regression",
}


def intervention_analytics_report_path() -> Path:
    return intervention_data_dir() / "intervention_analytics_latest.json"


def _safe_float(value: Any) -> float | None:
    try:
        scalar = float(value)
    except (TypeError, ValueError):
        return None
    return scalar


def _mean(values: Iterable[Any]) -> float | None:
    clean: List[float] = []
    for value in values:
        scalar = _safe_float(value)
        if scalar is None:
            continue
        clean.append(float(scalar))
    if not clean:
        return None
    return float(sum(clean) / len(clean))


def _rate(numerator: int, denominator: int) -> float | None:
    if int(denominator) <= 0:
        return None
    return float(int(numerator) / int(denominator))


def _sorted_counter(counter: Counter[str], *, limit: int | None = None) -> List[Dict[str, Any]]:
    rows = [
        {"name": str(name), "count": int(count)}
        for name, count in sorted(counter.items(), key=lambda item: (-int(item[1]), str(item[0])))
    ]
    if limit is not None:
        return rows[: int(limit)]
    return rows


def _sorted_nested_counter(counter: Dict[str, Counter[str]]) -> Dict[str, Dict[str, int]]:
    return {
        str(key): {
            str(name): int(count)
            for name, count in sorted(value.items(), key=lambda item: (-int(item[1]), str(item[0])))
        }
        for key, value in sorted(counter.items(), key=lambda item: str(item[0]))
    }


def _declared_plan(record: Dict[str, Any]) -> List[str]:
    return normalize_evaluation_plan(list(record.get("evaluation_plan", [])))


def _proposal_semantics(record: Dict[str, Any]) -> str:
    value = str(record.get("evaluation_semantics", "")).strip()
    if value:
        return value
    return proposal_evaluation_semantics(str(record.get("proposal_type", "")))


def _stage_state(record: Dict[str, Any], stage_name: str) -> str:
    stage_states = dict(dict(record.get("plan_execution", {})).get("stage_states", {}))
    state = dict(stage_states.get(str(stage_name), {}))
    status = str(state.get("status", "")).strip()
    if status:
        return status
    declared = _declared_plan(record)
    if str(stage_name) not in declared:
        return "skipped"
    evaluation = dict(record.get("evaluation", {}))
    stage_key = {
        "static_check": "static",
        "shadow": "shadow",
        "benchmark": "benchmark",
        "canary_gate": "canary",
    }[str(stage_name)]
    stage_block = dict(evaluation.get(stage_key, {}))
    if str(stage_name) == "canary_gate":
        if isinstance(stage_block.get("eligible"), bool):
            return "eligible" if bool(stage_block.get("eligible")) else "ineligible"
        return "pending"
    if isinstance(stage_block.get("passed"), bool):
        return "passed" if bool(stage_block.get("passed")) else "failed"
    return "pending"


def _is_legacy_contract_mismatch(record: Dict[str, Any]) -> bool:
    if _proposal_semantics(record) != "diagnostic":
        return False
    if _stage_state(record, "shadow") != "failed":
        return False
    return _stage_reason(record, "shadow") == "shadow evaluator not configured for this proposal type"


def _failed_stage(record: Dict[str, Any]) -> str | None:
    for stage_name in _declared_plan(record):
        if _stage_state(record, stage_name) == "failed":
            return str(stage_name)
    return None


def _plan_completion_status(record: Dict[str, Any]) -> str:
    plan_execution = dict(record.get("plan_execution", {}))
    completion_status = str(plan_execution.get("completion_status", "")).strip()
    if completion_status in {"completed_intended_plan", "failed_intended_stage"}:
        return completion_status
    if _failed_stage(record):
        return "failed_intended_stage"
    declared = _declared_plan(record)
    if declared and all(_stage_state(record, stage_name) in {"passed", "eligible", "ineligible"} for stage_name in declared):
        return "completed_intended_plan"
    return "in_progress"


def _effective_final_status(record: Dict[str, Any]) -> str:
    if _is_legacy_contract_mismatch(record):
        return "contract_mismatch_legacy"
    completion_status = _plan_completion_status(record)
    if completion_status == "completed_intended_plan":
        return "completed_plan"
    if completion_status == "failed_intended_stage":
        return "failed_stage"
    return str(record.get("promotion_status", "unknown"))


def _stage_reason(record: Dict[str, Any], stage_name: str) -> str:
    stage_states = dict(dict(record.get("plan_execution", {})).get("stage_states", {}))
    state = dict(stage_states.get(str(stage_name), {}))
    summary_reason = str(dict(state.get("summary", {})).get("reason", "")).strip()
    if summary_reason:
        return summary_reason
    note = str(state.get("note", "")).strip()
    if note:
        return note
    evaluation = dict(record.get("evaluation", {}))
    stage_key = {
        "static_check": "static",
        "shadow": "shadow",
        "benchmark": "benchmark",
        "canary_gate": "canary",
    }[str(stage_name)]
    stage_block = dict(evaluation.get(stage_key, {}))
    for key in ("reason", "stage_status"):
        text = str(stage_block.get(key, "")).strip()
        if text:
            return text
    return ""


def _effective_failure_tags(record: Dict[str, Any]) -> List[str]:
    declared = _declared_plan(record)
    if _is_legacy_contract_mismatch(record):
        return ["contract_mismatch_legacy"]
    tags = {str(tag) for tag in list(record.get("failure_tags", [])) if str(tag)}
    if "benchmark" not in declared:
        tags.discard("benchmark_regression")
    failed_stage_name = _failed_stage(record)
    if failed_stage_name == "static_check":
        tags.add("static_stage_failed")
    elif failed_stage_name == "shadow":
        tags.add("shadow_stage_failed")
    elif failed_stage_name == "benchmark":
        tags.add("benchmark_stage_failed")
    return sorted(tags)


def _final_reason(record: Dict[str, Any]) -> str:
    failed_stage_name = _failed_stage(record)
    if failed_stage_name:
        stage_reason = _stage_reason(record, failed_stage_name)
        if stage_reason:
            return stage_reason
    failure_tags = _effective_failure_tags(record)
    if failure_tags:
        return "+".join(sorted(failure_tags))
    canary_reason = ""
    if "canary_gate" in _declared_plan(record):
        canary_reason = str(dict(record.get("evaluation", {}).get("canary", {})).get("reason", "")).strip()
    if canary_reason:
        return canary_reason
    stage_history = [item for item in list(record.get("stage_history", [])) if isinstance(item, dict)]
    if stage_history:
        last_stage = dict(stage_history[-1])
        summary_reason = str(dict(last_stage.get("summary", {})).get("reason", "")).strip()
        if summary_reason:
            return summary_reason
        note = str(last_stage.get("note", "")).strip()
        if note:
            return note
    return str(record.get("promotion_status", "unknown"))


def _target_family(record: Dict[str, Any]) -> str:
    intended = dict(record.get("intended_benefit", {}))
    return str(intended.get("target_family", "unknown") or "unknown")


def _target_metric(record: Dict[str, Any]) -> str:
    intended = dict(record.get("intended_benefit", {}))
    return str(intended.get("target_metric", "unknown") or "unknown")


def _extract_benchmark_family_delta(record: Dict[str, Any], family: str, metric: str) -> float | None:
    benchmark = dict(record.get("evaluation", {}).get("benchmark", {}))
    family_deltas = dict(benchmark.get("family_deltas", {}))
    family_block = dict(family_deltas.get(str(family), {}))
    return _safe_float(family_block.get(str(metric)))


def _extract_target_metric_delta(record: Dict[str, Any]) -> float | None:
    family = _target_family(record)
    metric = _target_metric(record)
    metric_delta = _extract_benchmark_family_delta(record, family, metric)
    if metric_delta is None and not str(metric).endswith("_delta"):
        metric_delta = _extract_benchmark_family_delta(record, family, f"{metric}_delta")
    if metric_delta is not None:
        return metric_delta
    benchmark = dict(record.get("evaluation", {}).get("benchmark", {}))
    global_delta = dict(benchmark.get("global_delta", {}))
    scalar = _safe_float(global_delta.get(metric))
    if scalar is None and not str(metric).endswith("_delta"):
        scalar = _safe_float(global_delta.get(f"{metric}_delta"))
    return scalar


def _metric_improvement(metric_name: str, delta: float | None) -> float | None:
    if delta is None:
        return None
    name = str(metric_name)
    lower_is_better_tokens = (
        "got_reject",
        "false_safe",
        "unsafe_overcommit",
        "projection_bad",
        "goal_bad",
        "gain_bad",
        "brier",
        "goal_mse",
        "rollback_count",
    )
    if any(token in name for token in lower_is_better_tokens):
        return float(-delta)
    return float(delta)


def _build_type_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_type[str(record.get("proposal_type", "unknown"))].append(record)

    proposal_counts_by_type: Dict[str, int] = {}
    shadow_pass_rate_by_type: Dict[str, float | None] = {}
    benchmark_pass_rate_by_type: Dict[str, float | None] = {}
    canary_eligible_rate_by_type: Dict[str, float | None] = {}
    final_status_counts_by_type: Dict[str, Dict[str, int]] = {}
    type_template_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    contract_mismatch_counts_by_type: Dict[str, int] = {}

    for proposal_type, rows in sorted(by_type.items(), key=lambda item: str(item[0])):
        proposal_counts_by_type[proposal_type] = int(len(rows))
        status_counter: Counter[str] = Counter()
        shadow_eval_count = 0
        shadow_pass_count = 0
        benchmark_eval_count = 0
        benchmark_pass_count = 0
        canary_eval_count = 0
        canary_eligible_count = 0
        contract_mismatch_count = 0
        for row in rows:
            status_counter[_effective_final_status(row)] += 1
            type_template_counts[proposal_type][str(row.get("template_name", "unknown"))] += 1
            if _is_legacy_contract_mismatch(row):
                contract_mismatch_count += 1
            elif "shadow" in _declared_plan(row):
                shadow_state = _stage_state(row, "shadow")
                if shadow_state in {"passed", "failed"}:
                    shadow_eval_count += 1
                    shadow_pass_count += int(shadow_state == "passed")
            benchmark = dict(row.get("evaluation", {}).get("benchmark", {}))
            if "benchmark" in _declared_plan(row) and isinstance(benchmark.get("passed"), bool):
                benchmark_eval_count += 1
                benchmark_pass_count += int(bool(benchmark.get("passed")))
            canary = dict(row.get("evaluation", {}).get("canary", {}))
            if "canary_gate" in _declared_plan(row) and isinstance(canary.get("eligible"), bool):
                canary_eval_count += 1
                canary_eligible_count += int(bool(canary.get("eligible")))
        shadow_pass_rate_by_type[proposal_type] = _rate(shadow_pass_count, shadow_eval_count)
        benchmark_pass_rate_by_type[proposal_type] = _rate(benchmark_pass_count, benchmark_eval_count)
        canary_eligible_rate_by_type[proposal_type] = _rate(canary_eligible_count, canary_eval_count)
        contract_mismatch_counts_by_type[proposal_type] = int(contract_mismatch_count)
        final_status_counts_by_type[proposal_type] = {
            str(name): int(count)
            for name, count in sorted(status_counter.items(), key=lambda item: (-int(item[1]), str(item[0])))
        }

    return {
        "proposal_counts_by_type": proposal_counts_by_type,
        "shadow_pass_rate_by_type": shadow_pass_rate_by_type,
        "benchmark_pass_rate_by_type": benchmark_pass_rate_by_type,
        "canary_eligible_rate_by_type": canary_eligible_rate_by_type,
        "contract_mismatch_counts_by_type": contract_mismatch_counts_by_type,
        "final_status_counts_by_type": final_status_counts_by_type,
        "template_counts_by_type": _sorted_nested_counter(type_template_counts),
    }


def _build_family_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_family: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_family[_target_family(record)].append(record)

    summary: Dict[str, Dict[str, Any]] = {}
    for family, rows in sorted(by_family.items(), key=lambda item: str(item[0])):
        shadow_eval_count = 0
        shadow_pass_count = 0
        benchmark_eval_count = 0
        benchmark_pass_count = 0
        canary_eval_count = 0
        canary_eligible_count = 0
        dormant_count = 0
        harmful_count = 0
        contract_mismatch_count = 0
        status_counter: Counter[str] = Counter()
        type_counter: Counter[str] = Counter()
        template_counter: Counter[str] = Counter()
        metric_deltas: List[float] = []
        metric_improvements: List[float] = []
        family_match_deltas: List[float] = []
        family_false_safe_deltas: List[float] = []
        family_unsafe_deltas: List[float] = []
        global_match_deltas: List[float] = []
        global_false_safe_deltas: List[float] = []
        shadow_override_deltas: List[float] = []
        shadow_rollback_deltas: List[float] = []
        shadow_projection_bad_deltas: List[float] = []
        shadow_gain_deltas: List[float] = []

        for row in rows:
            type_counter[str(row.get("proposal_type", "unknown"))] += 1
            template_counter[str(row.get("template_name", "unknown"))] += 1
            status_counter[_effective_final_status(row)] += 1
            contract_mismatch_count += int(_is_legacy_contract_mismatch(row))
            failure_tags = _effective_failure_tags(row)
            dormant_count += int("dormant_live_override" in failure_tags)
            harmful_count += int(bool(set(failure_tags) & HARMFUL_FAILURE_TAGS))

            if not _is_legacy_contract_mismatch(row) and "shadow" in _declared_plan(row):
                shadow_state = _stage_state(row, "shadow")
                if shadow_state in {"passed", "failed"}:
                    shadow_eval_count += 1
                    shadow_pass_count += int(shadow_state == "passed")
            benchmark = dict(row.get("evaluation", {}).get("benchmark", {}))
            if "benchmark" in _declared_plan(row) and isinstance(benchmark.get("passed"), bool):
                benchmark_eval_count += 1
                benchmark_pass_count += int(bool(benchmark.get("passed")))
            canary = dict(row.get("evaluation", {}).get("canary", {}))
            if "canary_gate" in _declared_plan(row) and isinstance(canary.get("eligible"), bool):
                canary_eval_count += 1
                canary_eligible_count += int(bool(canary.get("eligible")))

            metric_delta = _extract_target_metric_delta(row)
            if metric_delta is not None:
                metric_deltas.append(float(metric_delta))
                metric_improvement = _metric_improvement(_target_metric(row), metric_delta)
                if metric_improvement is not None:
                    metric_improvements.append(float(metric_improvement))
            family_match_delta = _extract_benchmark_family_delta(row, family, "policy_match_rate_delta")
            if family_match_delta is not None:
                family_match_deltas.append(float(family_match_delta))
            family_false_safe_delta = _extract_benchmark_family_delta(row, family, "false_safe_projection_rate_delta")
            if family_false_safe_delta is not None:
                family_false_safe_deltas.append(float(family_false_safe_delta))
            family_unsafe_delta = _extract_benchmark_family_delta(row, family, "unsafe_overcommit_rate_delta")
            if family_unsafe_delta is not None:
                family_unsafe_deltas.append(float(family_unsafe_delta))

            global_delta = dict(benchmark.get("global_delta", {}))
            global_match_delta = _safe_float(global_delta.get("policy_match_rate_delta"))
            if global_match_delta is not None:
                global_match_deltas.append(float(global_match_delta))
            global_false_safe_delta = _safe_float(global_delta.get("false_safe_projection_rate_delta"))
            if global_false_safe_delta is not None:
                global_false_safe_deltas.append(float(global_false_safe_delta))

            shadow_delta = dict(dict(row.get("evaluation", {}).get("shadow", {})).get("delta", {}))
            for values, key in (
                (shadow_override_deltas, "override_count"),
                (shadow_rollback_deltas, "rollback_count"),
                (shadow_projection_bad_deltas, "projection_bad_incidents"),
                (shadow_gain_deltas, "mean_realized_gain"),
            ):
                scalar = _safe_float(shadow_delta.get(key))
                if scalar is not None:
                    values.append(float(scalar))

        summary[family] = {
            "proposal_count": int(len(rows)),
            "proposal_type_counts": {
                str(name): int(count)
                for name, count in sorted(type_counter.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
            "template_counts": {
                str(name): int(count)
                for name, count in sorted(template_counter.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
            "shadow_pass_rate": _rate(shadow_pass_count, shadow_eval_count),
            "benchmark_pass_rate": _rate(benchmark_pass_count, benchmark_eval_count),
            "canary_eligible_rate": _rate(canary_eligible_count, canary_eval_count),
            "contract_mismatch_count": int(contract_mismatch_count),
            "final_status_counts": {
                str(name): int(count)
                for name, count in sorted(status_counter.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
            "dormant_live_override_rate": _rate(dormant_count, len(rows)),
            "harmful_failure_rate": _rate(harmful_count, len(rows)),
            "target_metric": _target_metric(rows[0]),
            "mean_target_metric_delta": _mean(metric_deltas),
            "mean_target_metric_improvement": _mean(metric_improvements),
            "mean_target_family_policy_match_rate_delta": _mean(family_match_deltas),
            "mean_target_family_false_safe_projection_rate_delta": _mean(family_false_safe_deltas),
            "mean_target_family_unsafe_overcommit_rate_delta": _mean(family_unsafe_deltas),
            "mean_global_policy_match_rate_delta": _mean(global_match_deltas),
            "mean_global_false_safe_projection_rate_delta": _mean(global_false_safe_deltas),
            "mean_shadow_override_delta": _mean(shadow_override_deltas),
            "mean_shadow_rollback_delta": _mean(shadow_rollback_deltas),
            "mean_shadow_projection_bad_delta": _mean(shadow_projection_bad_deltas),
            "mean_shadow_realized_gain_delta": _mean(shadow_gain_deltas),
        }
    return summary


def _build_template_summary(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    by_template: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_template[str(record.get("template_name", "unknown"))].append(record)

    summary: Dict[str, Dict[str, Any]] = {}
    for template_name, rows in sorted(by_template.items(), key=lambda item: str(item[0])):
        shadow_eval_count = 0
        shadow_pass_count = 0
        benchmark_eval_count = 0
        benchmark_pass_count = 0
        canary_eval_count = 0
        canary_eligible_count = 0
        dormant_count = 0
        harmful_count = 0
        archived_count = 0
        contract_mismatch_count = 0
        status_counter: Counter[str] = Counter()
        failure_counter: Counter[str] = Counter()
        target_family_counter: Counter[str] = Counter()
        target_metric_deltas: List[float] = []
        target_metric_improvements: List[float] = []
        shadow_override_deltas: List[float] = []

        for row in rows:
            status = _effective_final_status(row)
            status_counter[status] += 1
            archived_count += int(status == "archived")
            contract_mismatch_count += int(_is_legacy_contract_mismatch(row))
            target_family_counter[_target_family(row)] += 1
            failure_tags = _effective_failure_tags(row)
            dormant_count += int("dormant_live_override" in failure_tags)
            harmful_count += int(bool(set(failure_tags) & HARMFUL_FAILURE_TAGS))
            for tag in failure_tags:
                failure_counter[str(tag)] += 1

            if not _is_legacy_contract_mismatch(row) and "shadow" in _declared_plan(row):
                shadow_state = _stage_state(row, "shadow")
                if shadow_state in {"passed", "failed"}:
                    shadow_eval_count += 1
                    shadow_pass_count += int(shadow_state == "passed")
            benchmark = dict(row.get("evaluation", {}).get("benchmark", {}))
            if "benchmark" in _declared_plan(row) and isinstance(benchmark.get("passed"), bool):
                benchmark_eval_count += 1
                benchmark_pass_count += int(bool(benchmark.get("passed")))
            canary = dict(row.get("evaluation", {}).get("canary", {}))
            if "canary_gate" in _declared_plan(row) and isinstance(canary.get("eligible"), bool):
                canary_eval_count += 1
                canary_eligible_count += int(bool(canary.get("eligible")))

            metric_delta = _extract_target_metric_delta(row)
            if metric_delta is not None:
                target_metric_deltas.append(float(metric_delta))
                metric_improvement = _metric_improvement(_target_metric(row), metric_delta)
                if metric_improvement is not None:
                    target_metric_improvements.append(float(metric_improvement))
            shadow_delta = dict(dict(row.get("evaluation", {}).get("shadow", {})).get("delta", {}))
            override_delta = _safe_float(shadow_delta.get("override_count"))
            if override_delta is not None:
                shadow_override_deltas.append(float(override_delta))

        benchmark_pass_rate = _rate(benchmark_pass_count, benchmark_eval_count)
        canary_eligible_rate = _rate(canary_eligible_count, canary_eval_count)
        dormant_rate = _rate(dormant_count, len(rows))
        harmful_rate = _rate(harmful_count, len(rows))
        archived_rate = _rate(archived_count, len(rows))
        mean_target_metric_delta = _mean(target_metric_deltas)
        mean_target_metric_improvement = _mean(target_metric_improvements)
        score = 0.0
        score += 1.5 * float(_rate(shadow_pass_count, shadow_eval_count) or 0.0)
        score += 2.0 * float(benchmark_pass_rate or 0.0)
        score += 2.5 * float(canary_eligible_rate or 0.0)
        score += float(mean_target_metric_improvement or 0.0)
        score -= 1.5 * float(dormant_rate or 0.0)
        score -= 2.0 * float(harmful_rate or 0.0)
        score -= 0.5 * float(archived_rate or 0.0)

        summary[template_name] = {
            "proposal_count": int(len(rows)),
            "proposal_type": str(rows[0].get("proposal_type", "unknown")),
            "evaluation_semantics": _proposal_semantics(rows[0]),
            "primary_target_family": target_family_counter.most_common(1)[0][0] if target_family_counter else "unknown",
            "shadow_pass_rate": _rate(shadow_pass_count, shadow_eval_count),
            "benchmark_pass_rate": benchmark_pass_rate,
            "canary_eligible_rate": canary_eligible_rate,
            "contract_mismatch_count": int(contract_mismatch_count),
            "dormant_live_override_rate": dormant_rate,
            "harmful_failure_rate": harmful_rate,
            "archived_rate": archived_rate,
            "mean_target_metric_delta": mean_target_metric_delta,
            "mean_target_metric_improvement": mean_target_metric_improvement,
            "mean_shadow_override_delta": _mean(shadow_override_deltas),
            "final_status_counts": {
                str(name): int(count)
                for name, count in sorted(status_counter.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
            "failure_tag_counts": {
                str(name): int(count)
                for name, count in sorted(failure_counter.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
            "score": float(score),
        }
    return summary


def _build_failure_and_reason_summaries(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    failure_tags: Counter[str] = Counter()
    archive_reasons: Counter[str] = Counter()
    revert_reasons: Counter[str] = Counter()
    failure_clusters: Counter[str] = Counter()
    dormant_types: Counter[str] = Counter()
    dormant_templates: Counter[str] = Counter()
    dormant_families: Counter[str] = Counter()

    for record in records:
        proposal_type = str(record.get("proposal_type", "unknown"))
        template_name = str(record.get("template_name", "unknown"))
        target_family = _target_family(record)
        tags = tuple(_effective_failure_tags(record))
        if tags:
            for tag in tags:
                failure_tags[str(tag)] += 1
            failure_clusters["+".join(tags)] += 1
        else:
            failure_clusters["none"] += 1
        if "dormant_live_override" in tags:
            dormant_types[proposal_type] += 1
            dormant_templates[template_name] += 1
            dormant_families[target_family] += 1

        status = _effective_final_status(record)
        reason = _final_reason(record)
        if status == "archived":
            archive_reasons[reason] += 1
        elif status == "reverted":
            revert_reasons[reason] += 1

    dormant_total = int(failure_tags.get("dormant_live_override", 0))
    return {
        "top_failure_tags": _sorted_counter(failure_tags, limit=10),
        "top_archive_reasons": _sorted_counter(archive_reasons, limit=10),
        "top_revert_reasons": _sorted_counter(revert_reasons, limit=10),
        "failure_clusters": _sorted_counter(failure_clusters, limit=10),
        "dormant_live_override": {
            "count": dormant_total,
            "rate": _rate(dormant_total, len(records)),
            "proposal_type_counts": {
                str(name): int(count)
                for name, count in sorted(dormant_types.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
            "template_counts": {
                str(name): int(count)
                for name, count in sorted(dormant_templates.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
            "target_family_counts": {
                str(name): int(count)
                for name, count in sorted(dormant_families.items(), key=lambda item: (-int(item[1]), str(item[0])))
            },
        },
    }


def _family_performance_score(summary: Dict[str, Any]) -> float:
    return float(
        1.5 * float(summary.get("shadow_pass_rate") or 0.0)
        + 2.0 * float(summary.get("canary_eligible_rate") or 0.0)
        + 1.5 * float(summary.get("benchmark_pass_rate") or 0.0)
        + float(summary.get("mean_target_metric_improvement") or 0.0)
        - 1.0 * float(summary.get("dormant_live_override_rate") or 0.0)
        - 1.5 * float(summary.get("harmful_failure_rate") or 0.0)
    )


def _build_compact_summary(
    *,
    family_summary: Dict[str, Dict[str, Any]],
    template_summary: Dict[str, Dict[str, Any]],
    failure_summary: Dict[str, Any],
) -> Dict[str, Any]:
    family_rows = [
        {
            "target_family": family,
            "score": _family_performance_score(summary),
            "proposal_count": int(summary.get("proposal_count", 0)),
            "shadow_pass_rate": summary.get("shadow_pass_rate"),
            "benchmark_pass_rate": summary.get("benchmark_pass_rate"),
            "canary_eligible_rate": summary.get("canary_eligible_rate"),
            "mean_target_metric_delta": summary.get("mean_target_metric_delta"),
            "mean_target_metric_improvement": summary.get("mean_target_metric_improvement"),
            "dormant_live_override_rate": summary.get("dormant_live_override_rate"),
            "harmful_failure_rate": summary.get("harmful_failure_rate"),
        }
        for family, summary in family_summary.items()
    ]
    best_families = sorted(
        family_rows,
        key=lambda item: (
            -float(item.get("score", 0.0)),
            -int(item.get("proposal_count", 0)),
            str(item.get("target_family")),
        ),
    )[:3]
    most_dormant_families = sorted(
        family_rows,
        key=lambda item: (
            -float(item.get("dormant_live_override_rate") or 0.0),
            -int(item.get("proposal_count", 0)),
            str(item.get("target_family")),
        ),
    )[:3]

    template_rows = [
        {
            "template_name": template_name,
            **summary,
        }
        for template_name, summary in template_summary.items()
    ]
    suggested: List[Dict[str, Any]] = []
    deprioritized: List[Dict[str, Any]] = []
    for row in sorted(
        template_rows,
        key=lambda item: (-float(item.get("score", 0.0)), -int(item.get("proposal_count", 0)), str(item.get("template_name"))),
    ):
        reason_bits: List[str] = []
        if float(row.get("benchmark_pass_rate") or 0.0) > 0.0:
            reason_bits.append("benchmark passes")
        if float(row.get("canary_eligible_rate") or 0.0) > 0.0:
            reason_bits.append("canary eligible")
        if float(row.get("mean_target_metric_delta") or 0.0) > 0.0:
            reason_bits.append("positive target-metric delta")
        if (
            float(row.get("score", 0.0)) > 0.0
            and float(row.get("dormant_live_override_rate") or 0.0) < 0.5
            and float(row.get("harmful_failure_rate") or 0.0) <= 0.0
        ):
            suggested.append(
                {
                    "template_name": str(row.get("template_name")),
                    "proposal_type": str(row.get("proposal_type")),
                    "score": float(row.get("score", 0.0)),
                    "reason": ", ".join(reason_bits) or "best observed intervention history",
                }
            )
        if (
            float(row.get("dormant_live_override_rate") or 0.0) >= 0.5
            or float(row.get("harmful_failure_rate") or 0.0) > 0.0
            or float(row.get("archived_rate") or 0.0) >= 0.5
        ):
            tag_counts = dict(row.get("failure_tag_counts", {}))
            top_tag = next(iter(tag_counts.keys()), "archived")
            deprioritized.append(
                {
                    "template_name": str(row.get("template_name")),
                    "proposal_type": str(row.get("proposal_type")),
                    "score": float(row.get("score", 0.0)),
                    "reason": f"repeated {top_tag}" if top_tag else "repeated archive outcome",
                }
            )

    if not suggested:
        top_failure_tags = [item.get("name") for item in list(failure_summary.get("top_failure_tags", []))]
        if "dormant_live_override" in top_failure_tags:
            suggested.append(
                {
                    "template_name": "memory_summary.override_dormancy_snapshot",
                    "proposal_type": "memory_summary",
                    "score": 0.25,
                    "reason": "dominant dormant_live_override suggests capturing blocker memory before another routing change",
                }
            )
        elif "projection_false_safe" in top_failure_tags:
            suggested.append(
                {
                    "template_name": "safety_veto_patch.projection_guard_recheck",
                    "proposal_type": "safety_veto_patch",
                    "score": 0.20,
                    "reason": "projection safety regressions suggest rechecking the trusted veto before more exploratory proposals",
                }
            )
        else:
            suggested.append(
                {
                    "template_name": "critic_split.projection_gain_goal_v1",
                    "proposal_type": "critic_split",
                    "score": 0.15,
                    "reason": "diagnostic critic split is the safest next probe when proposal history is sparse",
                }
            )

    return {
        "best_performing_proposal_families": best_families,
        "most_dormant_proposal_families": most_dormant_families,
        "most_common_failure_clusters": list(failure_summary.get("failure_clusters", []))[:5],
        "recommendations": {
            "suggested_next_templates": suggested[:3],
            "deprioritized_templates": deprioritized[:5],
        },
    }


def build_intervention_ledger_analytics() -> Dict[str, Any]:
    governance_execution_contract = build_execution_permission(action_kind="proposal_analytics")
    latest_records = list(load_latest_snapshots().values())
    latest_records.sort(
        key=lambda record: (
            str(record.get("created_at", "")),
            str(record.get("proposal_id", "")),
            int(record.get("ledger_revision", 0)),
        )
    )

    type_summary = _build_type_summary(latest_records)
    family_summary = _build_family_summary(latest_records)
    template_summary = _build_template_summary(latest_records)
    failure_summary = _build_failure_and_reason_summaries(latest_records)
    compact_summary = _build_compact_summary(
        family_summary=family_summary,
        template_summary=template_summary,
        failure_summary=failure_summary,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ledger_path": str(intervention_ledger_path()),
        "report_path": str(intervention_analytics_report_path()),
        "proposal_count": int(len(latest_records)),
        "governance_execution_contract": governance_execution_contract,
        **type_summary,
        "target_family_outcome_summary": family_summary,
        "template_outcome_summary": template_summary,
        **failure_summary,
        "compact_summary": compact_summary,
    }


def write_intervention_ledger_analytics_report() -> Dict[str, Any]:
    analytics = build_intervention_ledger_analytics()
    path = intervention_analytics_report_path()
    path.write_text(json.dumps(analytics, indent=2, sort_keys=True), encoding="utf-8")
    return analytics

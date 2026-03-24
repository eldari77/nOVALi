from __future__ import annotations

import argparse
import html
import json
import os
import re
import threading
import urllib.parse
from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import default as email_policy
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .acceptance import (
    build_manual_acceptance_evidence,
    render_manual_acceptance_markdown,
    write_manual_acceptance_report,
)
from .bounded_workspace_work import (
    AUTO_CONTINUE_OBJECTIVE_CLASSES,
    load_successor_auto_continue_decision,
    load_successor_auto_continue_policy,
    load_successor_auto_continue_state,
    materialize_successor_baseline_admission_decision,
    materialize_successor_reseed_decision,
    save_successor_auto_continue_policy,
    successor_auto_continue_policy_path,
)
from .directive_scaffold import build_standalone_directive_payload
from .envelope import (
    BACKEND_LOCAL_DOCKER,
    BACKEND_LOCAL_GUARDED,
    build_default_operator_runtime_envelope_spec,
    operator_runtime_envelope_spec_path,
    validate_operator_runtime_envelope_spec,
)
from .gui_presenter import (
    build_launch_readiness,
    build_launch_refusal_summary,
    build_launch_result_summary,
    inspect_directive_wrapper,
    render_constraints_summary,
    render_dashboard_summary,
    render_launch_readiness,
    render_trusted_sources_summary,
)
from .launcher import (
    OperatorLaunchRefusedError,
    build_operator_dashboard_snapshot,
    launch_novali_main,
)
from .policy import (
    EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
    EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING,
    GOVERNED_EXECUTION_MODE_MULTI_CYCLE,
    GOVERNED_EXECUTION_MODE_SINGLE_CYCLE,
    build_runtime_constraints_for_profile,
    default_operator_root,
    initialize_operator_policy_files,
    load_runtime_envelope_spec_or_default,
    load_runtime_constraints_or_default,
    load_trusted_source_bindings_or_default,
    operator_runtime_constraints_path,
    read_operator_status_snapshot,
    save_runtime_envelope_spec,
    save_runtime_constraints,
    validate_runtime_constraints,
)


WEB_PROFILE_SCHEMA_NAME = "OperatorWebProfile"
WEB_PROFILE_SCHEMA_VERSION = "operator_web_profile_v1"
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_CONTAINER_HOST = "0.0.0.0"
DEFAULT_WEB_PORT = 8787
PREVIEW_MAX_BYTES = 64 * 1024
PREVIEWABLE_SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".py", ".log"}
WORKSPACE_ARTIFACT_CATEGORIES = ("plans", "docs", "src", "tests", "artifacts")
KEY_WORKSPACE_ARTIFACTS = {
    "plans/bounded_work_cycle_plan.md",
    "plans/successor_continuation_gap_analysis.md",
    "docs/mutable_shell_successor_design_note.md",
    "docs/successor_package_readiness_note.md",
    "artifacts/bounded_work_summary_latest.json",
    "artifacts/implementation_bundle_summary_latest.json",
    "artifacts/workspace_artifact_index_latest.json",
    "artifacts/trusted_planning_evidence_latest.json",
    "artifacts/missing_deliverables_latest.json",
    "artifacts/next_step_derivation_latest.json",
    "artifacts/completion_evaluation_latest.json",
    "artifacts/successor_readiness_evaluation_latest.json",
    "artifacts/successor_delivery_manifest_latest.json",
    "artifacts/successor_review_summary_latest.json",
    "artifacts/successor_promotion_recommendation_latest.json",
    "artifacts/successor_next_objective_proposal_latest.json",
    "artifacts/successor_reseed_request_latest.json",
    "artifacts/successor_reseed_decision_latest.json",
    "artifacts/successor_continuation_lineage_latest.json",
    "artifacts/successor_effective_next_objective_latest.json",
    "artifacts/successor_auto_continue_state_latest.json",
    "artifacts/successor_auto_continue_decision_latest.json",
    "artifacts/successor_candidate_promotion_bundle_latest.json",
    "artifacts/successor_baseline_admission_review_latest.json",
    "artifacts/successor_baseline_admission_recommendation_latest.json",
    "artifacts/successor_baseline_admission_decision_latest.json",
    "artifacts/successor_baseline_remediation_proposal_latest.json",
    "artifacts/successor_admitted_candidate_latest.json",
    "artifacts/successor_admitted_candidate_handoff_latest.json",
    "artifacts/successor_baseline_comparison_latest.json",
    "artifacts/successor_reference_target_latest.json",
    "artifacts/successor_reference_target_consumption_latest.json",
    "artifacts/successor_revised_candidate_bundle_latest.json",
    "artifacts/successor_revised_candidate_handoff_latest.json",
    "artifacts/successor_revised_candidate_comparison_latest.json",
    "artifacts/successor_revised_candidate_promotion_summary_latest.json",
    "artifacts/successor_skill_pack_invocation_latest.json",
    "artifacts/successor_skill_pack_result_latest.json",
    "artifacts/successor_quality_gap_summary_latest.json",
    "artifacts/successor_quality_improvement_summary_latest.json",
    "artifacts/successor_quality_roadmap_latest.json",
    "artifacts/successor_quality_priority_matrix_latest.json",
    "artifacts/successor_quality_composite_evaluation_latest.json",
    "artifacts/successor_quality_next_pack_plan_latest.json",
    "artifacts/successor_quality_chain_reentry_latest.json",
    "artifacts/successor_generation_history_latest.json",
    "artifacts/successor_generation_delta_latest.json",
    "artifacts/successor_progress_governance_latest.json",
    "artifacts/successor_progress_recommendation_latest.json",
    "artifacts/successor_strategy_selection_latest.json",
    "artifacts/successor_strategy_rationale_latest.json",
    "artifacts/successor_strategy_follow_on_plan_latest.json",
    "artifacts/successor_strategy_decision_support_latest.json",
    "artifacts/successor_campaign_history_latest.json",
    "artifacts/successor_campaign_delta_latest.json",
    "artifacts/successor_campaign_governance_latest.json",
    "artifacts/successor_campaign_recommendation_latest.json",
    "artifacts/successor_campaign_wave_plan_latest.json",
    "artifacts/successor_campaign_cycle_history_latest.json",
    "artifacts/successor_campaign_cycle_delta_latest.json",
    "artifacts/successor_campaign_cycle_governance_latest.json",
    "artifacts/successor_campaign_cycle_recommendation_latest.json",
    "artifacts/successor_campaign_cycle_follow_on_plan_latest.json",
    "artifacts/successor_loop_history_latest.json",
    "artifacts/successor_loop_delta_latest.json",
    "artifacts/successor_loop_governance_latest.json",
    "artifacts/successor_loop_recommendation_latest.json",
    "artifacts/successor_loop_follow_on_plan_latest.json",
    "artifacts/successor_artifact_index_consistency_latest.json",
    "src/successor_shell/workspace_contract.py",
    "src/successor_shell/successor_manifest.py",
    "tests/test_workspace_contract.py",
    "tests/test_successor_manifest.py",
    "docs/successor_promotion_bundle_note.md",
    "docs/successor_docs_readiness_review.md",
    "docs/successor_handoff_completeness_note.md",
}
EVENT_LABELS = {
    "operator_runtime_guard_installed": "Runtime guard installed",
    "governed_execution_entered": "Governed execution entered",
    "governed_execution_controller_started": "Governed execution controller started",
    "governed_execution_cycle_started": "Governed execution cycle started",
    "governed_execution_cycle_completed": "Governed execution cycle completed",
    "governed_execution_controller_stopped": "Governed execution controller stopped",
    "governed_execution_planning_started": "Governed execution planning started",
    "directive_stop_condition_evaluated": "Directive stop condition evaluated",
    "trusted_planning_evidence_consulted": "Trusted planning evidence consulted",
    "missing_deliverables_identified": "Missing deliverables identified",
    "next_cycle_derived": "Next cycle derived",
    "completion_evaluation_recorded": "Completion evaluation recorded",
    "successor_review_started": "Successor review started",
    "successor_review_completed": "Successor review completed",
    "promotion_recommendation_recorded": "Promotion recommendation recorded",
    "next_objective_proposed": "Next objective proposed",
    "successor_reseed_request_materialized": "Successor reseed request materialized",
    "successor_reseed_decision_recorded": "Successor reseed decision recorded",
    "successor_effective_next_objective_materialized": "Successor effective next objective materialized",
    "successor_auto_continue_evaluated": "Successor auto-continue evaluated",
    "successor_auto_continue_cycle_started": "Successor auto-continue cycle started",
    "successor_baseline_admission_review_started": "Baseline admission review started",
    "successor_baseline_admission_recommendation_recorded": "Baseline admission recommendation recorded",
    "successor_baseline_remediation_proposal_materialized": "Baseline remediation proposal materialized",
    "successor_baseline_admission_review_completed": "Baseline admission review completed",
    "successor_baseline_admission_decision_recorded": "Baseline admission decision recorded",
    "successor_admitted_candidate_recorded": "Admitted candidate recorded",
    "successor_baseline_comparison_completed": "Baseline comparison completed",
    "successor_reference_target_recorded": "Reference target recorded",
    "successor_revised_candidate_bundle_materialized": "Revised candidate bundle materialized",
    "successor_revised_candidate_comparison_recorded": "Revised candidate comparison recorded",
    "reference_target_consumed": "Reference target consumed",
    "reference_target_fallback": "Reference target fallback",
    "successor_quality_gap_identified": "Successor quality gap identified",
    "successor_skill_pack_selected": "Successor skill pack selected",
    "successor_skill_pack_completed": "Successor skill pack completed",
    "successor_quality_improvement_recorded": "Successor quality improvement recorded",
    "successor_quality_roadmap_recorded": "Successor quality roadmap recorded",
    "successor_quality_chain_reentry_recorded": "Successor quality-chain reentry recorded",
    "successor_generation_progress_recorded": "Successor generation progress recorded",
    "successor_strategy_selection_recorded": "Successor strategy selection recorded",
    "successor_campaign_governance_recorded": "Successor campaign governance recorded",
    "successor_campaign_cycle_governance_recorded": "Successor campaign-cycle governance recorded",
    "successor_loop_governance_recorded": "Successor loop governance recorded",
    "successor_campaign_follow_on_materialized": "Successor campaign follow-on materialized",
    "implementation_planning_started": "Implementation planning started",
    "work_item_selected": "Work item selected",
    "implementation_item_selected": "Implementation item selected",
    "work_item_skipped": "Work item skipped",
    "file_write_planned": "File write planned",
    "file_write_completed": "File write completed",
    "test_scaffold_created": "Test scaffold created",
    "implementation_bundle_completed": "Implementation bundle completed",
    "implementation_bundle_deferred": "Implementation bundle deferred",
    "no_admissible_bounded_work": "No admissible bounded work",
    "bounded_work_failure": "Bounded work failure",
    "work_loop_completed": "Work loop completed",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _normalize_path(value: Any) -> str:
    if value in {None, ""}:
        return ""
    try:
        return str(Path(str(value)).resolve())
    except OSError:
        return str(value)


def _slug(value: str, *, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    return token or fallback


def _is_under_path(candidate: str | Path, root: str | Path) -> bool:
    try:
        Path(str(candidate)).resolve().relative_to(Path(str(root)).resolve())
        return True
    except ValueError:
        return False


def _read_json_file(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _directive_id_from_wrapper(path: str | Path | None) -> str:
    payload = _read_json_file(path)
    return str(dict(payload.get("directive_spec", {})).get("directive_id", "")).strip()


def _read_jsonl_file(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    try:
        rows: list[dict[str, Any]] = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = str(line).strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
        return rows
    except OSError:
        return []


def _read_workspace_runtime_events(
    primary_path: str | Path | None,
    *,
    workspace_id: str = "",
    session_id: str = "",
    directive_id: str = "",
) -> list[dict[str, Any]]:
    candidate_paths: list[Path] = []
    seen_paths: set[str] = set()
    primary = Path(primary_path).resolve() if primary_path else None
    if primary is not None and primary.exists():
        seen_paths.add(str(primary))
        candidate_paths.append(primary)
        if primary.parent.exists():
            for item in sorted(primary.parent.glob("*.jsonl")):
                resolved = item.resolve()
                if str(resolved) in seen_paths:
                    continue
                seen_paths.add(str(resolved))
                candidate_paths.append(resolved)

    rows: list[dict[str, Any]] = []
    seen_rows: set[str] = set()
    for path in candidate_paths:
        for payload in _read_jsonl_file(path):
            payload_workspace_id = str(payload.get("workspace_id", "")).strip()
            payload_session_id = str(payload.get("session_id", "")).strip()
            payload_directive_id = str(payload.get("directive_id", "")).strip()
            keep = False
            if workspace_id and payload_workspace_id == workspace_id:
                keep = True
            elif session_id and payload_session_id == session_id:
                keep = True
            elif directive_id and payload_directive_id == directive_id and payload_workspace_id == workspace_id:
                keep = True
            elif not workspace_id and not session_id and not directive_id:
                keep = True
            if not keep:
                continue
            row_key = json.dumps(payload, sort_keys=True)
            if row_key in seen_rows:
                continue
            seen_rows.add(row_key)
            rows.append(payload)
    rows.sort(
        key=lambda item: (
            str(item.get("timestamp", "")),
            str(item.get("session_id", "")),
            str(item.get("event_type", "")),
        )
    )
    return rows


def _format_bytes(size_bytes: int | float | None) -> str:
    if size_bytes in {None, ""}:
        return ""
    value = float(size_bytes)
    units = ["B", "KB", "MB", "GB"]
    unit = units[0]
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            break
        value /= 1024.0
    return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"


def _format_timestamp(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    except ValueError:
        return text


def _preview_href(path: str | Path) -> str:
    return "/preview?path=" + urllib.parse.quote(str(path), safe="")


def _html_list(items: list[str]) -> str:
    if not items:
        return "<p class='muted'>None recorded.</p>"
    return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def _shared_page_style() -> str:
    return """<style>
    :root {
      color-scheme: dark;
      --bg: #090b12;
      --bg-accent: #140f1f;
      --surface: #101521;
      --surface-elevated: #151c2b;
      --surface-tertiary: #1b1330;
      --border: #2c3450;
      --border-strong: #3b275d;
      --text: #ecf2f8;
      --muted: #9eb0bc;
      --heading: #f4f7fb;
      --green: #3ecf74;
      --green-strong: #1f8b4d;
      --green-soft: rgba(62, 207, 116, 0.14);
      --purple: #4a2b6b;
      --purple-soft: rgba(74, 43, 107, 0.34);
      --purple-strong: #6a42a0;
      --pre: #0e1320;
      --code: #161022;
      --shadow: rgba(0, 0, 0, 0.28);
      --shadow-glow: rgba(29, 199, 108, 0.16);
      --panel-glow: rgba(101, 67, 160, 0.18);
      --critical: #ff6b81;
      --warning: #f4c96b;
      --info: #68b5ff;
    }
    * { box-sizing: border-box; }
    body {
      font-family: Aptos, "Segoe UI Variable", "Trebuchet MS", sans-serif;
      margin: 0;
      padding: 24px;
      background:
        radial-gradient(circle at 15% 12%, rgba(74, 43, 107, 0.34), transparent 28%),
        radial-gradient(circle at 82% 8%, rgba(62, 207, 116, 0.14), transparent 24%),
        radial-gradient(circle at 50% 100%, rgba(62, 207, 116, 0.08), transparent 34%),
        linear-gradient(180deg, #120d1f 0%, var(--bg) 42%, #05070c 100%);
      color: var(--text);
      line-height: 1.5;
      min-height: 100vh;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.018) 1px, transparent 1px);
      background-size: 36px 36px;
      mask-image: radial-gradient(circle at center, black 52%, transparent 92%);
      opacity: 0.22;
    }
    h1, h2, h3 {
      color: var(--heading);
      margin-bottom: 0.4rem;
    }
    h2 {
      border-left: 4px solid var(--purple-strong);
      padding-left: 10px;
    }
    h3 {
      margin-top: 0.8rem;
    }
    a {
      color: var(--green);
    }
    a:hover {
      color: #7cf0a3;
    }
    strong {
      color: var(--heading);
    }
    .state-pill strong,
    .eyebrow,
    .page-kicker {
      color: inherit;
    }
    .muted {
      color: var(--muted);
    }
    .page-shell {
      max-width: 1480px;
      margin: 0 auto;
      position: relative;
      z-index: 1;
    }
    .page-header {
      position: relative;
      overflow: hidden;
      margin-bottom: 18px;
      padding: 24px 26px 20px 26px;
      border-radius: 28px;
      border: 1px solid rgba(106, 66, 160, 0.32);
      background:
        linear-gradient(135deg, rgba(18, 13, 31, 0.96), rgba(11, 16, 26, 0.96)),
        radial-gradient(circle at top right, rgba(62, 207, 116, 0.18), transparent 38%);
      box-shadow:
        0 22px 48px rgba(0, 0, 0, 0.34),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }
    .page-header::before {
      content: "";
      position: absolute;
      inset: -40% auto auto -20%;
      width: 340px;
      height: 340px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(106, 66, 160, 0.18), transparent 68%);
      pointer-events: none;
    }
    .page-header::after {
      content: "";
      position: absolute;
      right: -80px;
      top: -50px;
      width: 260px;
      height: 260px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(62, 207, 116, 0.18), transparent 72%);
      pointer-events: none;
    }
    .page-kicker,
    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(74, 43, 107, 0.28);
      border: 1px solid rgba(106, 66, 160, 0.28);
      color: #d5c4ff;
      font-size: 0.78rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .page-subtitle {
      max-width: 72ch;
      margin-top: 10px;
      color: var(--muted);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
    }
    .card {
      position: relative;
      overflow: hidden;
      background: linear-gradient(180deg, rgba(21, 28, 43, 0.98), rgba(16, 21, 33, 0.98));
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 14px 32px var(--shadow);
      backdrop-filter: blur(10px);
    }
    .card::before {
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      background: linear-gradient(135deg, rgba(255, 255, 255, 0.04), transparent 26%, transparent 74%, rgba(62, 207, 116, 0.04));
      opacity: 0.7;
    }
    .notice.card {
      border-color: var(--green-strong);
      background:
        linear-gradient(180deg, rgba(21, 28, 43, 0.98), rgba(16, 21, 33, 0.98)),
        linear-gradient(90deg, var(--green-soft), var(--purple-soft));
      box-shadow: 0 16px 38px rgba(9, 16, 14, 0.38);
    }
    .hero-panel,
    .wide-card {
      grid-column: 1 / -1;
    }
    .hero-panel {
      padding: 0;
    }
    .hero-layout {
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.95fr);
      gap: 22px;
      padding: 24px;
    }
    .hero-copy h2 {
      font-size: clamp(1.85rem, 2vw, 2.6rem);
      margin-top: 10px;
      margin-bottom: 10px;
      border: 0;
      padding-left: 0;
    }
    .hero-copy p {
      margin-top: 0;
      max-width: 70ch;
    }
    .hero-copy .muted {
      max-width: 68ch;
    }
    .pill-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 14px 0 18px 0;
    }
    .state-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 11px;
      border-radius: 999px;
      border: 1px solid rgba(106, 66, 160, 0.28);
      background: rgba(17, 23, 35, 0.72);
      color: var(--text);
      font-size: 0.9rem;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
    }
    .state-pill.success,
    .tone-success {
      border-color: rgba(62, 207, 116, 0.34);
      background: rgba(62, 207, 116, 0.12);
      color: #dafbe7;
    }
    .state-pill.warning,
    .tone-warning {
      border-color: rgba(244, 201, 107, 0.34);
      background: rgba(244, 201, 107, 0.12);
      color: #fff0c7;
    }
    .state-pill.critical,
    .tone-critical {
      border-color: rgba(255, 107, 129, 0.34);
      background: rgba(255, 107, 129, 0.12);
      color: #ffd8de;
    }
    .state-pill.info,
    .tone-info {
      border-color: rgba(104, 181, 255, 0.34);
      background: rgba(104, 181, 255, 0.12);
      color: #dceeff;
    }
    .state-pill.muted,
    .tone-muted {
      border-color: rgba(158, 176, 188, 0.22);
      background: rgba(158, 176, 188, 0.08);
      color: #c8d3da;
    }
    .signal-grid {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    }
    .metric-card {
      position: relative;
      padding: 14px;
      border-radius: 16px;
      border: 1px solid rgba(106, 66, 160, 0.22);
      background: linear-gradient(180deg, rgba(16, 20, 32, 0.94), rgba(12, 16, 27, 0.96));
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
      min-height: 122px;
    }
    .metric-kicker {
      display: block;
      color: var(--muted);
      font-size: 0.78rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .metric-value {
      display: block;
      margin-top: 8px;
      font-size: 1.08rem;
      color: var(--heading);
      word-break: break-word;
    }
    .metric-detail {
      display: block;
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.92rem;
    }
    .directive-core-shell {
      display: grid;
      gap: 14px;
      align-content: start;
    }
    .directive-core-visual {
      position: relative;
      min-height: 290px;
      border-radius: 24px;
      overflow: hidden;
      border: 1px solid rgba(106, 66, 160, 0.28);
      background:
        radial-gradient(circle at center, rgba(62, 207, 116, 0.08), transparent 40%),
        radial-gradient(circle at 50% 18%, rgba(106, 66, 160, 0.18), transparent 34%),
        linear-gradient(180deg, rgba(12, 16, 27, 0.98), rgba(18, 13, 31, 0.98));
      box-shadow:
        inset 0 0 0 1px rgba(255, 255, 255, 0.03),
        0 16px 36px rgba(0, 0, 0, 0.26);
    }
    .directive-core-visual::before {
      content: "";
      position: absolute;
      inset: 16px;
      border-radius: 20px;
      border: 1px solid rgba(106, 66, 160, 0.18);
      background:
        linear-gradient(135deg, rgba(62, 207, 116, 0.04), transparent 34%),
        linear-gradient(315deg, rgba(106, 66, 160, 0.06), transparent 40%);
    }
    .core-ring {
      position: absolute;
      inset: 50%;
      width: 230px;
      height: 230px;
      margin-left: -115px;
      margin-top: -115px;
      border-radius: 50%;
      border: 1px solid rgba(62, 207, 116, 0.18);
      box-shadow:
        0 0 0 18px rgba(62, 207, 116, 0.03),
        0 0 0 42px rgba(106, 66, 160, 0.03),
        0 0 48px rgba(62, 207, 116, 0.12);
      animation: slow-pulse 6s ease-in-out infinite;
    }
    .core-node {
      position: absolute;
      inset: 50%;
      width: min(68%, 290px);
      transform: translate(-50%, -50%);
      padding: 18px 18px 16px 18px;
      border-radius: 18px;
      border: 1px solid rgba(62, 207, 116, 0.32);
      background: linear-gradient(180deg, rgba(18, 25, 37, 0.96), rgba(11, 15, 24, 0.98));
      box-shadow:
        0 0 24px rgba(62, 207, 116, 0.14),
        0 0 0 1px rgba(255, 255, 255, 0.02);
      text-align: center;
    }
    .core-node .core-label {
      display: block;
      color: var(--muted);
      font-size: 0.78rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .core-node .core-title {
      display: block;
      margin-top: 8px;
      font-size: 1.05rem;
      color: var(--heading);
      word-break: break-word;
    }
    .core-node .core-detail {
      display: block;
      margin-top: 8px;
      color: #b6ecca;
      font-size: 0.92rem;
    }
    .core-sigil {
      position: absolute;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 44px;
      height: 44px;
      border-radius: 50%;
      border: 1px solid rgba(106, 66, 160, 0.26);
      background: rgba(11, 15, 24, 0.88);
      color: #ceb9ff;
      box-shadow: 0 0 18px rgba(106, 66, 160, 0.12);
      font-size: 1.05rem;
    }
    .core-sigil.sigil-a { top: 38px; left: 44px; }
    .core-sigil.sigil-b { right: 48px; top: 56px; }
    .core-sigil.sigil-c { bottom: 42px; left: 62px; }
    .core-sigil.sigil-d { right: 54px; bottom: 50px; }
    .stage-rail {
      display: grid;
      gap: 12px;
      margin-top: 14px;
    }
    .stage-step {
      display: grid;
      grid-template-columns: 40px minmax(0, 1fr);
      gap: 12px;
      align-items: start;
      padding: 14px;
      border-radius: 16px;
      border: 1px solid rgba(106, 66, 160, 0.18);
      background: rgba(12, 16, 27, 0.86);
    }
    .stage-step.complete {
      border-color: rgba(62, 207, 116, 0.28);
      box-shadow: inset 0 0 0 1px rgba(62, 207, 116, 0.08);
    }
    .stage-step.active {
      border-color: rgba(104, 181, 255, 0.3);
      box-shadow: inset 0 0 0 1px rgba(104, 181, 255, 0.08);
    }
    .stage-step.blocked {
      border-color: rgba(244, 201, 107, 0.3);
      box-shadow: inset 0 0 0 1px rgba(244, 201, 107, 0.08);
    }
    .stage-index {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      border-radius: 50%;
      border: 1px solid rgba(106, 66, 160, 0.28);
      background: rgba(74, 43, 107, 0.18);
      color: var(--heading);
      font-weight: 700;
    }
    .stage-step.complete .stage-index {
      border-color: rgba(62, 207, 116, 0.34);
      background: rgba(62, 207, 116, 0.14);
      color: #dcfce8;
    }
    .stage-step.active .stage-index {
      border-color: rgba(104, 181, 255, 0.34);
      background: rgba(104, 181, 255, 0.12);
      color: #e4f2ff;
    }
    .stage-step.blocked .stage-index {
      border-color: rgba(244, 201, 107, 0.34);
      background: rgba(244, 201, 107, 0.12);
      color: #fff4d4;
    }
    .stage-title {
      display: block;
      color: var(--heading);
      font-weight: 700;
    }
    .stage-detail {
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 0.94rem;
    }
    .stage-state {
      display: inline-block;
      margin-top: 8px;
      color: #b6ecca;
      font-size: 0.84rem;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    .stage-step.blocked .stage-state {
      color: #ffe5a7;
    }
    .dual-grid {
      display: grid;
      gap: 16px;
      grid-template-columns: minmax(0, 1.15fr) minmax(300px, 0.85fr);
    }
    .section-heading {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }
    .section-heading h2,
    .section-heading h3 {
      margin: 0;
    }
    .story-grid {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }
    .story-card {
      padding: 14px;
      border-radius: 16px;
      border: 1px solid rgba(106, 66, 160, 0.18);
      background: rgba(12, 16, 27, 0.78);
      min-height: 110px;
    }
    .story-card .label {
      display: block;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.78rem;
    }
    .story-card .value {
      display: block;
      margin-top: 8px;
      color: var(--heading);
      font-size: 1rem;
      word-break: break-word;
    }
    .story-card .detail {
      display: block;
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.92rem;
    }
    .summary-stack {
      display: grid;
      gap: 10px;
    }
    .summary-row {
      display: grid;
      gap: 8px;
      grid-template-columns: minmax(120px, 180px) minmax(0, 1fr);
      padding-bottom: 10px;
      border-bottom: 1px solid rgba(44, 52, 80, 0.6);
    }
    .summary-row:last-child {
      border-bottom: 0;
      padding-bottom: 0;
    }
    .summary-row .label {
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      font-size: 0.78rem;
    }
    .summary-row .value {
      color: var(--heading);
      word-break: break-word;
    }
    .module-grid {
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      align-items: start;
    }
    .operator-note {
      padding: 14px 16px;
      border-radius: 16px;
      border: 1px solid rgba(62, 207, 116, 0.24);
      background: linear-gradient(180deg, rgba(20, 37, 28, 0.42), rgba(12, 17, 23, 0.9));
      color: #dff7e8;
    }
    .operator-note.warning {
      border-color: rgba(244, 201, 107, 0.28);
      background: linear-gradient(180deg, rgba(53, 39, 15, 0.35), rgba(12, 17, 23, 0.9));
      color: #fff0c7;
    }
    .operator-note.info {
      border-color: rgba(104, 181, 255, 0.28);
      background: linear-gradient(180deg, rgba(17, 34, 55, 0.34), rgba(12, 17, 23, 0.9));
      color: #deefff;
    }
    .inline-form {
      display: inline-block;
      margin: 4px 8px 4px 0;
    }
    label {
      display: block;
      font-weight: 600;
      margin-top: 8px;
      color: var(--heading);
    }
    input[type=text],
    input[type=number],
    input[type=file],
    textarea,
    select {
      width: 100%;
      padding: 10px 12px;
      box-sizing: border-box;
      background: var(--surface-tertiary);
      color: var(--text);
      border: 1px solid var(--border-strong);
      border-radius: 10px;
      outline: none;
    }
    input[type=text]:focus,
    input[type=number]:focus,
    input[type=file]:focus,
    textarea:focus,
    select:focus {
      border-color: var(--green);
      box-shadow: 0 0 0 3px var(--green-soft);
    }
    textarea {
      min-height: 88px;
      resize: vertical;
    }
    pre {
      width: 100%;
      box-sizing: border-box;
      white-space: pre-wrap;
      background: var(--pre);
      color: var(--text);
      padding: 12px;
      border-radius: 10px;
      border: 1px solid var(--border);
      overflow-x: auto;
    }
    button {
      padding: 9px 14px;
      margin-top: 10px;
      border: 1px solid var(--green-strong);
      border-radius: 10px;
      background: linear-gradient(180deg, #215b3a, #173f2a);
      color: var(--heading);
      font-weight: 600;
      cursor: pointer;
      transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
      box-shadow: 0 8px 18px rgba(15, 43, 27, 0.28);
    }
    button:hover {
      transform: translateY(-1px);
      background: linear-gradient(180deg, #297346, #1a4d31);
      box-shadow: 0 12px 24px rgba(16, 52, 32, 0.34);
    }
    button:active {
      transform: translateY(0);
    }
    .inline-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }
    .inline-actions button {
      margin-top: 0;
    }
    code {
      background: var(--code);
      color: #d7c4ff;
      padding: 2px 6px;
      border-radius: 6px;
      border: 1px solid rgba(106, 66, 160, 0.28);
    }
    ol, ul {
      padding-left: 20px;
    }
    li {
      margin-bottom: 6px;
    }
    .path {
      word-break: break-all;
      color: #c2f3d3;
    }
    .topnav {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 16px 0 0 0;
    }
    .topnav a {
      display: inline-block;
      padding: 8px 12px;
      border-radius: 999px;
      text-decoration: none;
      background: rgba(74, 43, 107, 0.28);
      border: 1px solid rgba(106, 66, 160, 0.32);
      color: var(--text);
    }
    .topnav a.current {
      background: rgba(62, 207, 116, 0.18);
      border-color: rgba(62, 207, 116, 0.52);
      color: var(--heading);
    }
    .stats-grid {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }
    .stat-card {
      padding: 12px;
      border-radius: 16px;
      border: 1px solid rgba(106, 66, 160, 0.24);
      background: linear-gradient(180deg, rgba(27, 19, 48, 0.95), rgba(13, 19, 30, 0.96));
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
    }
    .stat-card .label {
      display: block;
      font-size: 0.86rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .stat-card .value {
      display: block;
      margin-top: 6px;
      font-size: 1rem;
      color: var(--heading);
      word-break: break-word;
    }
    .badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      background: rgba(62, 207, 116, 0.16);
      border: 1px solid rgba(62, 207, 116, 0.36);
      color: var(--heading);
      font-size: 0.84rem;
      margin-right: 8px;
      margin-bottom: 6px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
    }
    th, td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
      text-align: left;
    }
    th {
      color: var(--heading);
      font-size: 0.92rem;
    }
    .timeline {
      list-style: none;
      padding-left: 0;
    }
    .timeline li {
      list-style: none;
      padding: 12px 0 12px 18px;
      border-left: 2px solid rgba(62, 207, 116, 0.28);
      margin-left: 6px;
      position: relative;
    }
    .timeline li::before {
      content: "";
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--green);
      position: absolute;
      left: -6px;
      top: 18px;
      box-shadow: 0 0 0 4px rgba(62, 207, 116, 0.14);
    }
    .timeline .timestamp {
      color: var(--muted);
      font-size: 0.9rem;
    }
    .timeline .event-title {
      color: var(--heading);
      font-weight: 600;
      margin-top: 2px;
      margin-bottom: 4px;
    }
    .event-meta {
      margin-top: 6px;
      color: var(--muted);
    }
    .section-links a {
      margin-right: 14px;
    }
    .preview-note {
      color: var(--muted);
      font-size: 0.92rem;
    }
    .section-links {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 16px;
      margin-top: 12px;
    }
    .section-links a {
      margin-right: 0;
    }
    @keyframes slow-pulse {
      0%, 100% { transform: scale(1); opacity: 0.9; }
      50% { transform: scale(1.04); opacity: 1; }
    }
    @media (max-width: 1080px) {
      .hero-layout,
      .dual-grid {
        grid-template-columns: 1fr;
      }
      .directive-core-visual {
        min-height: 260px;
      }
    }
    @media (max-width: 720px) {
      body {
        padding: 16px;
      }
      .page-header,
      .hero-layout,
      .card {
        padding-left: 16px;
        padding-right: 16px;
      }
      .summary-row {
        grid-template-columns: 1fr;
      }
      .core-ring {
        width: 190px;
        height: 190px;
        margin-left: -95px;
        margin-top: -95px;
      }
      .core-sigil {
        width: 38px;
        height: 38px;
      }
    }
  </style>"""


def _page_navigation(current_path: str) -> str:
    links = [
        ("/", "Home"),
        ("/observability", "Observability"),
        ("/workspace", "Workspace"),
        ("/timeline", "Timeline"),
        ("/cycle", "Latest Cycle"),
    ]
    rendered = []
    for href, label in links:
        class_name = "current" if current_path == href else ""
        rendered.append(f"<a href=\"{href}\" class=\"{class_name}\">{html.escape(label)}</a>")
    return "<nav class='topnav'>" + "".join(rendered) + "</nav>"


def _render_page(*, title: str, subtitle: str, body: str, current_path: str) -> str:
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\" />"
        f"<title>{html.escape(title)}</title>"
        f"{_shared_page_style()}"
        "</head><body>"
        "<div class='page-shell'>"
        "<header class='page-header'>"
        "<span class='page-kicker'>Operator Surface</span>"
        f"<h1>{html.escape(title)}</h1>"
        f"<p class='page-subtitle'>{subtitle}</p>"
        f"{_page_navigation(current_path)}"
        "</header>"
        f"{body}"
        "</div>"
        "</body></html>"
    )


def _display_text(value: Any, *, fallback: str = "<none>") -> str:
    text = str(value or "").strip()
    return text or fallback


def _status_tone(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text or text in {"<none>", "<none yet>", "false", "0"}:
        return "muted"
    if text in {"true", "yes"}:
        return "success"
    critical_tokens = (
        "fail",
        "refus",
        "reject",
        "regress",
        "invalid",
        "error",
        "blocked",
        "missing",
    )
    if any(token in text for token in critical_tokens):
        return "critical"
    warning_tokens = ("review", "pause", "defer", "pending", "attention", "waiting")
    if any(token in text for token in warning_tokens):
        return "warning"
    success_tokens = (
        "ready",
        "active",
        "online",
        "complete",
        "completed",
        "approved",
        "enabled",
        "admitted",
        "resolved",
        "continue",
        "stable",
        "loaded",
        "valid",
        "materialized",
    )
    if any(token in text for token in success_tokens):
        return "success"
    if "hold" in text:
        return "info"
    return "info"


def _render_state_pill(label: str, value: Any, *, tone: str | None = None) -> str:
    resolved_tone = tone or _status_tone(value)
    return (
        f"<span class='state-pill {html.escape(resolved_tone)}'>"
        f"<strong>{html.escape(label)}</strong> {html.escape(_display_text(value))}"
        "</span>"
    )


def _render_metric_card(
    label: str,
    value: Any,
    detail: str = "",
    *,
    tone: str | None = None,
) -> str:
    resolved_tone = tone or _status_tone(value)
    detail_html = (
        f"<span class='metric-detail'>{html.escape(detail)}</span>"
        if str(detail).strip()
        else ""
    )
    return (
        f"<div class='metric-card tone-{html.escape(resolved_tone)}'>"
        f"<span class='metric-kicker'>{html.escape(label)}</span>"
        f"<span class='metric-value'>{html.escape(_display_text(value))}</span>"
        f"{detail_html}"
        "</div>"
    )


def _render_stage_step(index: int, title: str, detail: str, *, state: str) -> str:
    state_label = {
        "complete": "Complete",
        "active": "Current step",
        "blocked": "Blocked",
        "pending": "Pending",
    }.get(state, "Pending")
    return (
        f"<div class='stage-step {html.escape(state)}'>"
        f"<span class='stage-index'>{index}</span>"
        "<div>"
        f"<span class='stage-title'>{html.escape(title)}</span>"
        f"<span class='stage-detail'>{html.escape(detail)}</span>"
        f"<span class='stage-state'>{html.escape(state_label)}</span>"
        "</div>"
        "</div>"
    )


def _render_summary_rows(rows: list[tuple[str, str]]) -> str:
    return (
        "<div class='summary-stack'>"
        + "".join(
            "<div class='summary-row'>"
            f"<span class='label'>{html.escape(label)}</span>"
            f"<span class='value'>{value}</span>"
            "</div>"
            for label, value in rows
        )
        + "</div>"
    )


def _build_home_workflow_summary(
    *,
    resume_mode: str,
    launch_action: str,
    directive_valid: bool,
    bootstrap_ready: bool,
    governed_ready: bool,
    review_required: bool,
    continuation_authorized: bool,
    runtime_defaults: dict[str, Any],
    readiness: dict[str, Any],
    observability: dict[str, Any],
    last_action_summary: dict[str, Any],
) -> dict[str, Any]:
    execution_profile = str(runtime_defaults.get("execution_profile", "") or "").strip()
    governed_profile_selected = (
        execution_profile == EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING
    )
    bootstrap_profile_selected = (
        execution_profile == EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION
    )
    selected_launch = f"{resume_mode or '<missing>'} + {launch_action or '<missing>'}"
    expected_execution_profile = str(readiness.get("expected_execution_profile", "") or "").strip()
    profile_alignment_label = str(readiness.get("profile_alignment_label", "") or "").strip()
    profile_alignment_detail = str(readiness.get("profile_alignment_detail", "") or "").strip()
    run_status = str(observability.get("run_status", "") or "").strip()
    review_status = str(observability.get("review_status", "") or "").strip()
    hold_state = (
        str(observability.get("loop_recommendation_state", "") or "").strip()
        or str(observability.get("campaign_cycle_recommendation_state", "") or "").strip()
        or str(observability.get("campaign_recommendation_state", "") or "").strip()
        or str(observability.get("next_recommended_cycle", "") or "").strip()
    )
    recent_change = str(last_action_summary.get("headline", "") or "").strip()
    if not recent_change or recent_change == "No action yet.":
        recent_change = run_status or review_status or "No bounded action recorded yet."
    recent_change_detail = (
        str(observability.get("stop_reason", "") or "").strip()
        or str(observability.get("quality_improvement_state", "") or "").strip()
        or str(last_action_summary.get("summary", "") or "").strip()
        or "The browser is still waiting for canonical operator work to begin."
    )

    step_one_state = "complete" if directive_valid else "blocked"
    step_two_state = "pending"
    step_three_state = "pending"
    step_four_state = "pending"
    workflow_state = "Directive not ready"
    workflow_detail = "NOVALI cannot start canonical bootstrap until a formal directive wrapper is loaded."
    next_action_label = "Select a directive to begin"
    next_action_detail = (
        "Use the Directive section, then keep runtime policy on "
        "bootstrap_only_initialization before the first launch."
    )
    waiting_on = "A valid directive wrapper"

    if directive_valid:
        step_one_state = "complete"
        if not bootstrap_ready:
            step_two_state = "active" if bootstrap_profile_selected else "blocked"
            workflow_state = "Ready for bootstrap-only initialization"
            workflow_detail = (
                "The directive core is loaded, but canonical frozen bootstrap state does not exist yet."
            )
            if bootstrap_profile_selected:
                next_action_label = "Run bootstrap-only initialization"
                next_action_detail = (
                    "Launch new_bootstrap + bootstrap_only to create canonical frozen state."
                )
                waiting_on = "Canonical frozen bootstrap state"
            else:
                next_action_label = "Save bootstrap-only runtime policy"
                next_action_detail = (
                    "Runtime Constraints And Envelope should be saved with "
                    "bootstrap_only_initialization before new_bootstrap + bootstrap_only."
                )
                waiting_on = "Saved bootstrap-only runtime policy"
        elif not governed_profile_selected:
            step_two_state = "complete"
            step_three_state = "blocked"
            workflow_state = "Bootstrap complete; switch back to governed execution"
            workflow_detail = (
                "Canonical bootstrap state exists. The next bounded lane is governed execution, "
                "but the saved runtime policy is not yet on the governed coding profile."
            )
            next_action_label = "Now switch back to bounded governed execution"
            next_action_detail = (
                "Save Runtime Constraints And Envelope with bounded_active_workspace_coding, "
                "then launch resume_existing + governed_execution."
            )
            waiting_on = "Saved governed runtime policy"
        elif not governed_ready:
            step_two_state = "complete"
            step_three_state = "active"
            workflow_state = "Governed execution is ready"
            workflow_detail = (
                "Canonical bootstrap completed and the governed profile is selected. NOVALI is waiting "
                "for the first governed bounded cycle."
            )
            next_action_label = "Resume governed execution"
            next_action_detail = (
                "Launch resume_existing + governed_execution. Use single_cycle for one bounded pass or "
                "multi_cycle for conservative continuation under the selected cap."
            )
            waiting_on = "First governed bounded cycle"
        else:
            step_two_state = "complete"
            step_three_state = "complete"
            step_four_state = "active"
            if review_required and not continuation_authorized:
                workflow_state = "Review required before continuing"
                workflow_detail = (
                    "NOVALI has completed bounded work and is waiting for an explicit operator decision."
                )
                next_action_label = "Review the current bounded proposal"
                next_action_detail = (
                    "Use Review, Reseed, And Continuation or Candidate Admission based on the current artifact-backed state."
                )
                waiting_on = "Operator review"
            elif "hold" in hold_state.lower():
                workflow_state = "Stable / held"
                workflow_detail = (
                    "The current bounded target is held. NOVALI is not asking for an immediate new launch."
                )
                next_action_label = "No action needed; current target is held"
                next_action_detail = (
                    "Use Observability, Workspace, Timeline, or Cycle if you want to inspect why the current target is held."
                )
                waiting_on = "No immediate operator action"
            else:
                workflow_state = "Runtime / operator workflow active"
                workflow_detail = (
                    "NOVALI is online inside the bounded operator workflow with artifact-backed observability."
                )
                next_action_label = "Inspect the latest cycle and choose the next bounded move"
                next_action_detail = (
                    "Use Observability, Workspace, Timeline, and the review modules to continue, admit, or hold."
                )
                waiting_on = "Operator interpretation of the latest bounded state"

    policy_tone = (
        "warning"
        if expected_execution_profile and not readiness.get("profile_matches_selected_action", True)
        else "info"
    )
    waiting_on_tone = _status_tone(waiting_on)
    return {
        "selected_launch": selected_launch,
        "selected_execution_profile": execution_profile or "<missing>",
        "expected_execution_profile": expected_execution_profile or "<none>",
        "profile_alignment_label": profile_alignment_label or "Runtime policy visible",
        "profile_alignment_detail": profile_alignment_detail or "The saved runtime policy is shown so the operator can confirm the next lane before launch.",
        "policy_tone": policy_tone,
        "workflow_state": workflow_state,
        "workflow_detail": workflow_detail,
        "next_action_label": next_action_label,
        "next_action_detail": next_action_detail,
        "waiting_on": waiting_on,
        "waiting_on_tone": waiting_on_tone,
        "recent_change": recent_change,
        "recent_change_detail": recent_change_detail,
        "step_one_state": step_one_state,
        "step_two_state": step_two_state,
        "step_three_state": step_three_state,
        "step_four_state": step_four_state,
    }


def default_web_bind_host(*, container_mode: bool = False) -> str:
    return DEFAULT_CONTAINER_HOST if container_mode else DEFAULT_WEB_HOST


def default_web_state_root(package_root: str | Path) -> Path:
    package_root_path = Path(package_root)
    runtime_state = package_root_path / "runtime_data" / "state"
    return runtime_state if runtime_state.parent.exists() else package_root_path / "data"


def directive_input_root(package_root: str | Path, operator_root: str | Path) -> Path:
    package_root_path = Path(package_root)
    operator_root_path = Path(operator_root)
    candidate = package_root_path / "directive_inputs"
    return candidate if candidate.exists() else operator_root_path / "directive_inputs"


def acceptance_evidence_root(package_root: str | Path, state_root: str | Path) -> Path:
    package_root_path = Path(package_root)
    state_root_path = Path(state_root)
    candidate = package_root_path / "runtime_data" / "acceptance_evidence"
    if candidate.parent.exists():
        return candidate
    return state_root_path / "acceptance_evidence"


def sample_directive_paths(package_root: str | Path) -> list[dict[str, str]]:
    package_root_path = Path(package_root)
    candidates = [
        package_root_path / "samples" / "directives",
        package_root_path / "manual_acceptance_samples",
    ]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for directory in candidates:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            normalized = _normalize_path(path)
            if normalized in seen:
                continue
            seen.add(normalized)
            label = path.name
            if "incomplete" in path.name:
                label = f"{path.name} (refusal sample)"
            elif "valid" in path.name:
                label = f"{path.name} (valid sample)"
            rows.append({"label": label, "path": normalized})
    return rows


def operator_web_profile_path(root: str | Path) -> Path:
    return Path(root) / "operator_web_profile.local.json"


def build_default_operator_web_profile(
    *,
    package_root: str | Path,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    package_root_path = Path(package_root)
    state_root_path = Path(state_root) if state_root is not None else default_web_state_root(package_root_path)
    default_directive = ""
    if not (package_root_path / "directive_inputs").exists():
        bootstrap_directive = package_root_path / "directives" / "novali_v5_bootstrap_directive_v1.json"
        default_directive = _normalize_path(bootstrap_directive) if bootstrap_directive.exists() else ""
    return {
        "schema_name": WEB_PROFILE_SCHEMA_NAME,
        "schema_version": WEB_PROFILE_SCHEMA_VERSION,
        "updated_at": "",
        "recent_directive_file": default_directive,
        "recent_state_root": _normalize_path(state_root_path),
        "recent_resume_mode": "new_bootstrap",
        "recent_launch_action": "bootstrap_only",
    }


def sanitize_operator_web_profile(
    payload: dict[str, Any] | None,
    *,
    package_root: str | Path,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    defaults = build_default_operator_web_profile(package_root=package_root, state_root=state_root)
    source = dict(payload or {})
    resume_mode = str(source.get("recent_resume_mode", defaults["recent_resume_mode"])).strip()
    launch_action = str(source.get("recent_launch_action", defaults["recent_launch_action"])).strip()
    return {
        "schema_name": WEB_PROFILE_SCHEMA_NAME,
        "schema_version": WEB_PROFILE_SCHEMA_VERSION,
        "updated_at": str(source.get("updated_at", "")),
        "recent_directive_file": str(source.get("recent_directive_file", defaults["recent_directive_file"])),
        "recent_state_root": str(source.get("recent_state_root", defaults["recent_state_root"])),
        "recent_resume_mode": resume_mode if resume_mode in {"new_bootstrap", "resume_existing"} else defaults["recent_resume_mode"],
        "recent_launch_action": (
            launch_action
            if launch_action in {"bootstrap_only", "governed_execution", "proposal_analytics", "proposal_recommend"}
            else defaults["recent_launch_action"]
        ),
    }


def load_operator_web_profile(
    *,
    root: str | Path,
    package_root: str | Path,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    path = operator_web_profile_path(root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        payload = {}
    return sanitize_operator_web_profile(payload, package_root=package_root, state_root=state_root)


def save_operator_web_profile(
    payload: dict[str, Any],
    *,
    root: str | Path,
    package_root: str | Path,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    cleaned = sanitize_operator_web_profile(payload, package_root=package_root, state_root=state_root)
    cleaned["updated_at"] = _now()
    path = operator_web_profile_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dump(cleaned), encoding="utf-8")
    return cleaned


class OperatorWebService:
    def __init__(
        self,
        *,
        package_root: str | Path | None = None,
        operator_root: str | Path | None = None,
        state_root: str | Path | None = None,
    ) -> None:
        self.package_root = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
        self.operator_root = Path(operator_root) if operator_root is not None else default_operator_root()
        self.state_root = Path(state_root) if state_root is not None else default_web_state_root(self.package_root)
        self.directive_root = directive_input_root(self.package_root, self.operator_root)
        self.evidence_root = acceptance_evidence_root(self.package_root, self.state_root)
        self._lock = threading.Lock()
        self.last_action_summary: dict[str, Any] = {
            "headline": "No launch attempt has been made from the web operator yet.",
            "details": [],
            "summary": "No launch attempt has been made from the web operator yet.",
        }
        self.last_export_path = ""
        self.last_export_json_path = ""
        initialize_operator_policy_files(root=self.operator_root, package_root=self.package_root)
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.directive_root.mkdir(parents=True, exist_ok=True)
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self.profile = load_operator_web_profile(
            root=self.operator_root,
            package_root=self.package_root,
            state_root=self.state_root,
        )

    @property
    def directive_file(self) -> str:
        return str(self.profile.get("recent_directive_file", "")).strip()

    @property
    def resume_mode(self) -> str:
        return str(self.profile.get("recent_resume_mode", "new_bootstrap")).strip()

    @property
    def launch_action(self) -> str:
        return str(self.profile.get("recent_launch_action", "bootstrap_only")).strip()

    def _persist_profile(self) -> None:
        self.profile = save_operator_web_profile(
            {
                "recent_directive_file": self.directive_file,
                "recent_state_root": _normalize_path(self.state_root),
                "recent_resume_mode": self.resume_mode,
                "recent_launch_action": self.launch_action,
            },
            root=self.operator_root,
            package_root=self.package_root,
            state_root=self.state_root,
        )

    def update_profile(
        self,
        *,
        directive_file: str | None = None,
        state_root: str | None = None,
        resume_mode: str | None = None,
        launch_action: str | None = None,
    ) -> None:
        if directive_file is not None:
            self.profile["recent_directive_file"] = str(directive_file).strip()
        if state_root is not None:
            self.state_root = Path(str(state_root).strip() or self.state_root)
            self.state_root.mkdir(parents=True, exist_ok=True)
            self.evidence_root = acceptance_evidence_root(self.package_root, self.state_root)
            self.evidence_root.mkdir(parents=True, exist_ok=True)
            self.profile["recent_state_root"] = _normalize_path(self.state_root)
        if resume_mode is not None:
            self.profile["recent_resume_mode"] = str(resume_mode).strip()
        if launch_action is not None:
            self.profile["recent_launch_action"] = str(launch_action).strip()
        self._persist_profile()

    def current_operator_snapshot(self) -> dict[str, Any]:
        return read_operator_status_snapshot(root=self.operator_root, package_root=self.package_root)

    def is_packaged_handoff_context(self) -> bool:
        return bool((self.package_root / "handoff_layout_manifest.json").exists())

    def current_dashboard_snapshot(self) -> dict[str, Any]:
        return build_operator_dashboard_snapshot(
            package_root=self.package_root,
            operator_root=self.operator_root,
            state_root=self.state_root,
        )

    def current_directive_summary(self) -> dict[str, Any]:
        return inspect_directive_wrapper(self.directive_file, resume_mode=self.resume_mode)

    def current_launch_readiness(self) -> dict[str, Any]:
        return build_launch_readiness(
            resume_mode=self.resume_mode,
            launch_action=self.launch_action,
            state_root=_normalize_path(self.state_root),
            directive_summary=self.current_directive_summary(),
            operator_status_snapshot=self.current_operator_snapshot(),
            constraints_dirty=False,
        )

    def _preview_link_for_path(self, path: str) -> str:
        normalized = str(path or "").strip()
        if not normalized:
            return ""
        if Path(normalized).suffix.lower() not in PREVIEWABLE_SUFFIXES:
            return ""
        return _preview_href(normalized)

    def _render_path_html(self, path: str) -> str:
        normalized = str(path or "").strip()
        if not normalized:
            return "<span class='muted'>&lt;none&gt;</span>"
        preview_href = self._preview_link_for_path(normalized)
        preview_html = f" <a href=\"{preview_href}\">Preview</a>" if preview_href else ""
        return f"<span class='path'>{html.escape(normalized)}</span>{preview_html}"

    def _observability_snapshot(self) -> dict[str, Any]:
        dashboard = self.current_dashboard_snapshot()
        operator_snapshot = self.current_operator_snapshot()
        launch_context = dict(dashboard.get("launch_context", {}))
        runtime_constraints = dict(dashboard.get("runtime_constraints", {}))
        runtime_envelope = dict(dashboard.get("runtime_envelope", {}))
        governed = dict(dashboard.get("governed_execution", {}))
        governed_controller = dict(governed.get("controller", {}))
        effective_session = dict(launch_context.get("effective_operator_session", {}))
        last_launch_event = dict(launch_context.get("last_launch_event", {}))
        last_launch_plan = dict(launch_context.get("last_launch_plan", {}))
        workspace_policy = dict(runtime_constraints.get("workspace_policy", {}))

        workspace_id = (
            str(governed.get("workspace_id", "")).strip()
            or str(effective_session.get("workspace_id", "")).strip()
            or str(workspace_policy.get("workspace_id", "")).strip()
            or str(last_launch_plan.get("workspace_id", "")).strip()
        )
        workspace_root = (
            str(governed.get("workspace_root", "")).strip()
            or str(effective_session.get("workspace_root", "")).strip()
            or str(workspace_policy.get("workspace_root", "")).strip()
            or str(last_launch_plan.get("workspace_root", "")).strip()
        )
        workspace_root_path = Path(workspace_root) if workspace_root else None

        session_artifact_path = (
            str(governed.get("session_artifact_path", "")).strip()
            or (
                str(workspace_root_path / "artifacts" / "governed_execution_session_latest.json")
                if workspace_root_path
                else ""
            )
        )
        session_summary = _read_json_file(session_artifact_path)
        work_cycle = dict(governed.get("work_cycle", {}))
        session_work_cycle = dict(session_summary.get("work_cycle", {}))
        controller_summary = governed_controller
        controller_artifact_path = (
            str(workspace_root_path / "artifacts" / "governed_execution_controller_latest.json")
            if workspace_root_path
            else ""
        )
        if not controller_summary and workspace_root_path:
            controller_summary = _read_json_file(controller_artifact_path)

        summary_artifact_path = (
            str(session_work_cycle.get("summary_artifact_path", "")).strip()
            or str(work_cycle.get("summary_artifact_path", "")).strip()
            or (
                str(workspace_root_path / "artifacts" / "bounded_work_summary_latest.json")
                if workspace_root_path and (workspace_root_path / "artifacts" / "bounded_work_summary_latest.json").exists()
                else ""
            )
        )
        implementation_summary_path = (
            str(workspace_root_path / "artifacts" / "implementation_bundle_summary_latest.json")
            if workspace_root_path
            else ""
        )
        artifact_index_path = (
            str(workspace_root_path / "artifacts" / "workspace_artifact_index_latest.json")
            if workspace_root_path
            else ""
        )
        trusted_planning_evidence_path = (
            str(controller_summary.get("latest_trusted_planning_evidence_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "trusted_planning_evidence_latest.json") if workspace_root_path else "")
        )
        missing_deliverables_path = (
            str(controller_summary.get("latest_missing_deliverables_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "missing_deliverables_latest.json") if workspace_root_path else "")
        )
        next_step_derivation_path = (
            str(controller_summary.get("latest_next_step_derivation_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "next_step_derivation_latest.json") if workspace_root_path else "")
        )
        completion_evaluation_path = (
            str(controller_summary.get("latest_completion_evaluation_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "completion_evaluation_latest.json") if workspace_root_path else "")
        )
        review_summary_path = (
            str(controller_summary.get("latest_successor_review_summary_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_review_summary_latest.json") if workspace_root_path else "")
        )
        promotion_recommendation_path = (
            str(controller_summary.get("latest_successor_promotion_recommendation_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_promotion_recommendation_latest.json") if workspace_root_path else "")
        )
        next_objective_proposal_path = (
            str(controller_summary.get("latest_successor_next_objective_proposal_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_next_objective_proposal_latest.json") if workspace_root_path else "")
        )
        reseed_request_path = (
            str(controller_summary.get("latest_successor_reseed_request_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_reseed_request_latest.json") if workspace_root_path else "")
        )
        reseed_decision_path = (
            str(controller_summary.get("latest_successor_reseed_decision_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_reseed_decision_latest.json") if workspace_root_path else "")
        )
        continuation_lineage_path = (
            str(controller_summary.get("latest_successor_continuation_lineage_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_continuation_lineage_latest.json") if workspace_root_path else "")
        )
        effective_next_objective_path = (
            str(controller_summary.get("latest_successor_effective_next_objective_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_effective_next_objective_latest.json") if workspace_root_path else "")
        )
        baseline_admission_review_path = (
            str(controller_summary.get("latest_successor_baseline_admission_review_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_baseline_admission_review_latest.json") if workspace_root_path else "")
        )
        baseline_admission_recommendation_path = (
            str(controller_summary.get("latest_successor_baseline_admission_recommendation_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_baseline_admission_recommendation_latest.json") if workspace_root_path else "")
        )
        baseline_admission_decision_path = (
            str(controller_summary.get("latest_successor_baseline_admission_decision_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_baseline_admission_decision_latest.json") if workspace_root_path else "")
        )
        baseline_remediation_proposal_path = (
            str(controller_summary.get("latest_successor_baseline_remediation_proposal_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_baseline_remediation_proposal_latest.json") if workspace_root_path else "")
        )
        admitted_candidate_path = (
            str(controller_summary.get("latest_successor_admitted_candidate_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_admitted_candidate_latest.json") if workspace_root_path else "")
        )
        admitted_candidate_handoff_path = (
            str(controller_summary.get("latest_successor_admitted_candidate_handoff_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_admitted_candidate_handoff_latest.json") if workspace_root_path else "")
        )
        baseline_comparison_path = (
            str(controller_summary.get("latest_successor_baseline_comparison_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_baseline_comparison_latest.json") if workspace_root_path else "")
        )
        reference_target_path = (
            str(controller_summary.get("latest_successor_reference_target_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_reference_target_latest.json") if workspace_root_path else "")
        )
        revised_candidate_bundle_path = (
            str(
                controller_summary.get(
                    "latest_successor_revised_candidate_bundle_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_revised_candidate_bundle_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        revised_candidate_handoff_path = (
            str(
                controller_summary.get(
                    "latest_successor_revised_candidate_handoff_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_revised_candidate_handoff_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        revised_candidate_comparison_path = (
            str(
                controller_summary.get(
                    "latest_successor_revised_candidate_comparison_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_revised_candidate_comparison_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        revised_candidate_promotion_summary_path = (
            str(
                controller_summary.get(
                    "latest_successor_revised_candidate_promotion_summary_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_revised_candidate_promotion_summary_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        reference_target_consumption_path = (
            str(
                controller_summary.get(
                    "latest_successor_reference_target_consumption_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_reference_target_consumption_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        skill_pack_invocation_path = (
            str(
                controller_summary.get(
                    "latest_successor_skill_pack_invocation_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_skill_pack_invocation_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        skill_pack_result_path = (
            str(
                controller_summary.get(
                    "latest_successor_skill_pack_result_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_skill_pack_result_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        quality_gap_summary_path = (
            str(
                controller_summary.get(
                    "latest_successor_quality_gap_summary_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_quality_gap_summary_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        quality_improvement_summary_path = (
            str(
                controller_summary.get(
                    "latest_successor_quality_improvement_summary_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_quality_improvement_summary_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        quality_roadmap_path = (
            str(
                controller_summary.get(
                    "latest_successor_quality_roadmap_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_quality_roadmap_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        quality_priority_matrix_path = (
            str(
                controller_summary.get(
                    "latest_successor_quality_priority_matrix_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_quality_priority_matrix_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        quality_composite_evaluation_path = (
            str(
                controller_summary.get(
                    "latest_successor_quality_composite_evaluation_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_quality_composite_evaluation_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        quality_next_pack_plan_path = (
            str(
                controller_summary.get(
                    "latest_successor_quality_next_pack_plan_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_quality_next_pack_plan_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        quality_chain_reentry_path = (
            str(
                controller_summary.get(
                    "latest_successor_quality_chain_reentry_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_quality_chain_reentry_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        generation_history_path = (
            str(
                controller_summary.get(
                    "latest_successor_generation_history_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_generation_history_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        generation_delta_path = (
            str(
                controller_summary.get(
                    "latest_successor_generation_delta_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_generation_delta_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        progress_governance_path = (
            str(
                controller_summary.get(
                    "latest_successor_progress_governance_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_progress_governance_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        progress_recommendation_path = (
            str(
                controller_summary.get(
                    "latest_successor_progress_recommendation_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_progress_recommendation_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        strategy_selection_path = (
            str(
                controller_summary.get(
                    "latest_successor_strategy_selection_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_strategy_selection_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        strategy_rationale_path = (
            str(
                controller_summary.get(
                    "latest_successor_strategy_rationale_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_strategy_rationale_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        strategy_follow_on_plan_path = (
            str(
                controller_summary.get(
                    "latest_successor_strategy_follow_on_plan_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_strategy_follow_on_plan_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        strategy_decision_support_path = (
            str(
                controller_summary.get(
                    "latest_successor_strategy_decision_support_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_strategy_decision_support_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        campaign_history_path = (
            str(
                controller_summary.get(
                    "latest_successor_campaign_history_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_campaign_history_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        campaign_delta_path = (
            str(
                controller_summary.get(
                    "latest_successor_campaign_delta_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_campaign_delta_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        campaign_governance_path = (
            str(
                controller_summary.get(
                    "latest_successor_campaign_governance_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_campaign_governance_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        campaign_recommendation_path = (
            str(
                controller_summary.get(
                    "latest_successor_campaign_recommendation_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_campaign_recommendation_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        campaign_wave_plan_path = (
            str(
                controller_summary.get(
                    "latest_successor_campaign_wave_plan_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_campaign_wave_plan_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        campaign_cycle_history_path = (
            str(
                controller_summary.get(
                    "latest_successor_campaign_cycle_history_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_campaign_cycle_history_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        campaign_cycle_delta_path = (
            str(
                controller_summary.get(
                    "latest_successor_campaign_cycle_delta_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_campaign_cycle_delta_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        campaign_cycle_governance_path = (
            str(
                controller_summary.get(
                    "latest_successor_campaign_cycle_governance_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_campaign_cycle_governance_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        campaign_cycle_recommendation_path = (
            str(
                controller_summary.get(
                    "latest_successor_campaign_cycle_recommendation_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_campaign_cycle_recommendation_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        campaign_cycle_follow_on_plan_path = (
            str(
                controller_summary.get(
                    "latest_successor_campaign_cycle_follow_on_plan_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_campaign_cycle_follow_on_plan_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        loop_history_path = (
            str(
                controller_summary.get(
                    "latest_successor_loop_history_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_loop_history_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        loop_delta_path = (
            str(
                controller_summary.get(
                    "latest_successor_loop_delta_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_loop_delta_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        loop_governance_path = (
            str(
                controller_summary.get(
                    "latest_successor_loop_governance_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_loop_governance_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        loop_recommendation_path = (
            str(
                controller_summary.get(
                    "latest_successor_loop_recommendation_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_loop_recommendation_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        loop_follow_on_plan_path = (
            str(
                controller_summary.get(
                    "latest_successor_loop_follow_on_plan_path",
                    "",
                )
            ).strip()
            or (
                str(
                    workspace_root_path
                    / "artifacts"
                    / "successor_loop_follow_on_plan_latest.json"
                )
                if workspace_root_path
                else ""
            )
        )
        auto_continue_policy_path = str(successor_auto_continue_policy_path(self.operator_root))
        auto_continue_state_path = (
            str(controller_summary.get("latest_successor_auto_continue_state_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_auto_continue_state_latest.json") if workspace_root_path else "")
        )
        auto_continue_decision_path = (
            str(controller_summary.get("latest_successor_auto_continue_decision_path", "")).strip()
            or (str(workspace_root_path / "artifacts" / "successor_auto_continue_decision_latest.json") if workspace_root_path else "")
        )
        auto_continue_transition_path = str(
            controller_summary.get("latest_auto_continue_transition_path", "")
        ).strip()
        runtime_event_log_path = (
            str(effective_session.get("runtime_event_log_path", "")).strip()
            or str(session_summary.get("runtime_event_log_path", "")).strip()
        )

        work_summary = _read_json_file(summary_artifact_path)
        implementation_summary = _read_json_file(implementation_summary_path)
        artifact_index = _read_json_file(artifact_index_path)
        trusted_planning_evidence = _read_json_file(trusted_planning_evidence_path)
        missing_deliverables_summary = _read_json_file(missing_deliverables_path)
        next_step_derivation = _read_json_file(next_step_derivation_path)
        completion_evaluation = _read_json_file(completion_evaluation_path)
        review_summary = _read_json_file(review_summary_path)
        promotion_recommendation = _read_json_file(promotion_recommendation_path)
        next_objective_proposal = _read_json_file(next_objective_proposal_path)
        reseed_request = _read_json_file(reseed_request_path)
        reseed_decision = _read_json_file(reseed_decision_path)
        continuation_lineage = _read_json_file(continuation_lineage_path)
        effective_next_objective = _read_json_file(effective_next_objective_path)
        baseline_admission_review = _read_json_file(baseline_admission_review_path)
        baseline_admission_recommendation = _read_json_file(
            baseline_admission_recommendation_path
        )
        baseline_admission_decision = _read_json_file(baseline_admission_decision_path)
        baseline_remediation_proposal = _read_json_file(
            baseline_remediation_proposal_path
        )
        admitted_candidate = _read_json_file(admitted_candidate_path)
        admitted_candidate_handoff = _read_json_file(admitted_candidate_handoff_path)
        baseline_comparison = _read_json_file(baseline_comparison_path)
        reference_target = _read_json_file(reference_target_path)
        revised_candidate_bundle = _read_json_file(revised_candidate_bundle_path)
        revised_candidate_handoff = _read_json_file(revised_candidate_handoff_path)
        revised_candidate_comparison = _read_json_file(revised_candidate_comparison_path)
        revised_candidate_promotion_summary = _read_json_file(
            revised_candidate_promotion_summary_path
        )
        reference_target_consumption = _read_json_file(reference_target_consumption_path)
        skill_pack_invocation = _read_json_file(skill_pack_invocation_path)
        skill_pack_result = _read_json_file(skill_pack_result_path)
        quality_gap_summary = _read_json_file(quality_gap_summary_path)
        quality_improvement_summary = _read_json_file(quality_improvement_summary_path)
        quality_roadmap = _read_json_file(quality_roadmap_path)
        quality_priority_matrix = _read_json_file(quality_priority_matrix_path)
        quality_composite_evaluation = _read_json_file(
            quality_composite_evaluation_path
        )
        quality_next_pack_plan = _read_json_file(quality_next_pack_plan_path)
        quality_chain_reentry = _read_json_file(quality_chain_reentry_path)
        generation_history = _read_json_file(generation_history_path)
        generation_delta = _read_json_file(generation_delta_path)
        progress_governance = _read_json_file(progress_governance_path)
        progress_recommendation = _read_json_file(progress_recommendation_path)
        strategy_selection = _read_json_file(strategy_selection_path)
        strategy_rationale = _read_json_file(strategy_rationale_path)
        strategy_follow_on_plan = _read_json_file(strategy_follow_on_plan_path)
        strategy_decision_support = _read_json_file(strategy_decision_support_path)
        campaign_history = _read_json_file(campaign_history_path)
        campaign_delta = _read_json_file(campaign_delta_path)
        campaign_governance = _read_json_file(campaign_governance_path)
        campaign_recommendation = _read_json_file(campaign_recommendation_path)
        campaign_wave_plan = _read_json_file(campaign_wave_plan_path)
        campaign_cycle_history = _read_json_file(campaign_cycle_history_path)
        campaign_cycle_delta = _read_json_file(campaign_cycle_delta_path)
        campaign_cycle_governance = _read_json_file(campaign_cycle_governance_path)
        campaign_cycle_recommendation = _read_json_file(
            campaign_cycle_recommendation_path
        )
        campaign_cycle_follow_on_plan = _read_json_file(
            campaign_cycle_follow_on_plan_path
        )
        loop_history = _read_json_file(loop_history_path)
        loop_delta = _read_json_file(loop_delta_path)
        loop_governance = _read_json_file(loop_governance_path)
        loop_recommendation = _read_json_file(loop_recommendation_path)
        loop_follow_on_plan = _read_json_file(loop_follow_on_plan_path)
        auto_continue_policy = load_successor_auto_continue_policy(self.operator_root)
        auto_continue_state = load_successor_auto_continue_state(workspace_root)
        auto_continue_decision = load_successor_auto_continue_decision(workspace_root)
        auto_continue_transition = _read_json_file(auto_continue_transition_path)
        selected_directive_id = (
            _directive_id_from_wrapper(str(effective_session.get("directive_file", "")).strip())
            or _directive_id_from_wrapper(str(last_launch_event.get("directive_file", "")).strip())
            or _directive_id_from_wrapper(self.directive_file)
        )
        directive_id = (
            str(work_summary.get("directive_id", "")).strip()
            or str(implementation_summary.get("directive_id", "")).strip()
            or str(session_summary.get("directive_id", "")).strip()
            or str(dict(dashboard.get("canonical_posture", {})).get("active_directive_id", "")).strip()
            or selected_directive_id
        )
        latest_session_id = (
            str(effective_session.get("session_id", "")).strip()
            or str(session_summary.get("session_id", "")).strip()
        )
        runtime_events = _read_workspace_runtime_events(
            runtime_event_log_path,
            workspace_id=workspace_id,
            session_id=latest_session_id,
            directive_id=directive_id,
        )
        cycle_kind = (
            str(work_summary.get("cycle_kind", "")).strip()
            or str(implementation_summary.get("cycle_kind", "")).strip()
            or str(session_work_cycle.get("cycle_kind", "")).strip()
            or str(work_cycle.get("cycle_kind", "")).strip()
        )
        invocation_model = (
            str(controller_summary.get("invocation_model", "")).strip()
            or str(work_cycle.get("invocation_model", "")).strip()
            or str(work_summary.get("invocation_model", "")).strip()
            or str(implementation_summary.get("invocation_model", "")).strip()
            or str(session_work_cycle.get("invocation_model", "")).strip()
            or "single_cycle_per_governed_execution_invocation"
        )
        next_recommended_cycle = (
            str(controller_summary.get("next_recommended_cycle", "")).strip()
            or str(work_summary.get("next_recommended_cycle", "")).strip()
            or str(implementation_summary.get("next_recommended_cycle", "")).strip()
            or str(artifact_index.get("next_recommended_cycle", "")).strip()
            or str(session_work_cycle.get("next_recommended_cycle", "")).strip()
        )
        output_artifact_paths = list(work_summary.get("output_artifact_paths", []))
        if not output_artifact_paths:
            output_artifact_paths = list(session_work_cycle.get("output_artifact_paths", []))
        if not output_artifact_paths and implementation_summary:
            output_artifact_paths = list(implementation_summary.get("created_files", []))
        newly_created_paths = list(work_summary.get("newly_created_paths", []))
        if not newly_created_paths and implementation_summary:
            newly_created_paths = list(implementation_summary.get("created_files", []))
        skipped_items = list(work_summary.get("skipped_work_items", [])) or list(session_work_cycle.get("skipped_work_items", []))
        deferred_items = list(work_summary.get("deferred_items", [])) or list(implementation_summary.get("deferred_items", []))
        if effective_next_objective:
            resolved_reseed_state = str(effective_next_objective.get("reseed_state", "")).strip()
            if not resolved_reseed_state:
                resolved_reseed_state = str(reseed_request.get("reseed_state", "")).strip()
            if not resolved_reseed_state:
                resolved_reseed_state = str(controller_summary.get("reseed_state", "")).strip()
            resolved_continuation_authorized = bool(
                effective_next_objective.get("continuation_authorized", False)
            )
            resolved_effective_next_objective_id = str(
                effective_next_objective.get("objective_id", "")
            ).strip()
        elif reseed_request:
            resolved_reseed_state = str(reseed_request.get("reseed_state", "")).strip() or str(
                controller_summary.get("reseed_state", "")
            ).strip()
            resolved_continuation_authorized = bool(
                reseed_request.get("continuation_authorized", False)
            )
            resolved_effective_next_objective_id = ""
        else:
            resolved_reseed_state = str(controller_summary.get("reseed_state", "")).strip()
            resolved_continuation_authorized = bool(
                controller_summary.get("continuation_authorized", False)
            )
            resolved_effective_next_objective_id = str(
                controller_summary.get("effective_next_objective_id", "")
            ).strip()

        last_launch_event_type = str(last_launch_event.get("event_type", "")).strip()
        last_launch_kind = str(last_launch_event.get("launch_kind", "")).strip()
        last_launch_failure_reason = str(last_launch_event.get("failure_reason", "")).strip()
        if not last_launch_failure_reason:
            launch_errors = [str(item).strip() for item in list(last_launch_event.get("errors", [])) if str(item).strip()]
            if launch_errors:
                last_launch_failure_reason = "; ".join(launch_errors)
        latest_cycle_materialized = any(
            (
                work_summary,
                implementation_summary,
                artifact_index,
                review_summary,
                session_summary,
                controller_summary,
            )
        )
        cycle_materialization_status = "cycle_summary_available" if latest_cycle_materialized else "no_cycle_summary_available"
        cycle_failure_stage = ""
        cycle_failure_reason = ""
        if not latest_cycle_materialized:
            launch_failed = (
                last_launch_event_type == "launch_refused_preflight"
                or (
                    last_launch_event_type == "launch_completed"
                    and int(last_launch_event.get("exit_code", 0) or 0) != 0
                )
            )
            if launch_failed:
                cycle_materialization_status = "cycle_summary_unavailable_due_to_launch_failure"
                cycle_failure_reason = last_launch_failure_reason or "latest launch failed before cycle artifacts were materialized"
                cycle_failure_stage = "before_cycle_entry"
                if session_summary:
                    cycle_failure_stage = "during_cycle_initialization"
            elif workspace_root:
                cycle_failure_stage = "awaiting_first_cycle_artifacts"

        return {
            "dashboard": dashboard,
            "operator_snapshot": operator_snapshot,
            "directive_id": directive_id,
            "workspace_id": workspace_id,
            "workspace_root": workspace_root,
            "launch_type": str(launch_context.get("current_launch_mode", "")).strip() or str(last_launch_event.get("startup_mode", "")).strip(),
            "execution_mode": str(effective_session.get("launch_kind", "")).strip() or str(last_launch_event.get("launch_kind", "")).strip() or self.launch_action,
            "execution_profile": str(effective_session.get("execution_profile", "")).strip() or str(runtime_constraints.get("execution_profile", "")).strip() or str(operator_snapshot.get("execution_profile", "")).strip(),
            "backend_kind": str(last_launch_plan.get("backend_kind", "")).strip() or str(dict(runtime_envelope.get("effective_envelope", {})).get("backend_kind", "")).strip() or str(dict(operator_snapshot.get("runtime_envelope_spec", {})).get("backend_kind", "")).strip(),
            "cycle_kind": cycle_kind,
            "run_status": str(session_summary.get("status", "")).strip() or str(governed.get("status", "")).strip() or str(last_launch_event.get("status", "")).strip(),
            "run_reason": str(session_summary.get("reason", "")).strip() or str(governed.get("reason", "")).strip(),
            "next_recommended_cycle": next_recommended_cycle,
            "active_workspace_root": workspace_root,
            "controller_mode": str(controller_summary.get("controller_mode", "")).strip() or GOVERNED_EXECUTION_MODE_SINGLE_CYCLE,
            "max_cycles_per_invocation": int(controller_summary.get("max_cycles_per_invocation", 1) or 1),
            "cycles_completed": int(controller_summary.get("cycles_completed", 0) or 0),
            "latest_cycle_index": int(controller_summary.get("latest_cycle_index", 0) or 0),
            "stop_reason": str(controller_summary.get("stop_reason", "")).strip(),
            "stop_detail": str(controller_summary.get("stop_detail", "")).strip(),
            "directive_completion_evaluation": (
                dict(controller_summary.get("directive_completion_evaluation", {}))
                or completion_evaluation
            ),
            "review_status": str(controller_summary.get("review_status", "")).strip()
            or str(review_summary.get("review_status", "")).strip(),
            "promotion_recommendation_state": str(
                controller_summary.get("promotion_recommendation_state", "")
            ).strip()
            or str(promotion_recommendation.get("promotion_recommendation_state", "")).strip(),
            "next_objective_state": str(controller_summary.get("next_objective_state", "")).strip()
            or str(next_objective_proposal.get("proposal_state", "")).strip(),
            "next_objective_id": str(controller_summary.get("next_objective_id", "")).strip()
            or str(next_objective_proposal.get("objective_id", "")).strip(),
            "current_objective_source_kind": str(
                controller_summary.get("current_objective_source_kind", "")
            ).strip()
            or str(directive_id and "directive_objective"),
            "current_objective_id": str(controller_summary.get("current_objective_id", "")).strip()
            or str(directive_id),
            "last_launch_event_type": last_launch_event_type,
            "last_launch_kind": last_launch_kind,
            "last_launch_failure_reason": last_launch_failure_reason,
            "cycle_materialization_status": cycle_materialization_status,
            "cycle_failure_stage": cycle_failure_stage,
            "cycle_failure_reason": cycle_failure_reason,
            "reseed_state": resolved_reseed_state,
            "continuation_authorized": resolved_continuation_authorized,
            "effective_next_objective_id": resolved_effective_next_objective_id,
            "effective_next_objective_class": str(
                effective_next_objective.get("objective_class", "")
            ).strip()
            or str(controller_summary.get("effective_next_objective_class", "")).strip(),
            "baseline_admission_review_state": str(
                baseline_admission_review.get("admission_review_state", "")
            ).strip()
            or str(controller_summary.get("baseline_admission_review_state", "")).strip(),
            "baseline_admission_recommendation_state": str(
                baseline_admission_recommendation.get("admission_recommendation_state", "")
            ).strip()
            or str(controller_summary.get("baseline_admission_recommendation_state", "")).strip(),
            "baseline_admission_decision_state": str(
                baseline_admission_decision.get("admission_decision_state", "")
            ).strip()
            or str(controller_summary.get("baseline_admission_decision_state", "")).strip(),
            "baseline_candidate_admitted": bool(
                baseline_admission_decision.get(
                    "admitted_bounded_baseline_candidate",
                    controller_summary.get(
                        "baseline_candidate_admitted",
                        False,
                    ),
                )
            ),
            "baseline_remediation_objective_id": str(
                baseline_remediation_proposal.get("objective_id", "")
            ).strip()
            or str(controller_summary.get("baseline_remediation_objective_id", "")).strip(),
            "admitted_candidate_state": str(
                admitted_candidate.get("admitted_candidate_state", "")
            ).strip()
            or str(controller_summary.get("admitted_candidate_state", "")).strip(),
            "admitted_candidate_handoff_state": str(
                admitted_candidate_handoff.get("handoff_state", "")
            ).strip()
            or str(controller_summary.get("admitted_candidate_handoff_state", "")).strip(),
            "admitted_candidate_handoff_ready": bool(
                admitted_candidate_handoff.get(
                    "handoff_ready",
                    controller_summary.get("admitted_candidate_handoff_ready", False),
                )
            ),
            "baseline_comparison_state": str(
                baseline_comparison.get("comparison_state", "")
            ).strip()
            or str(controller_summary.get("baseline_comparison_state", "")).strip(),
            "baseline_comparison_result_state": str(
                baseline_comparison.get("comparison_result_state", "")
            ).strip()
            or str(controller_summary.get("baseline_comparison_result_state", "")).strip(),
            "stronger_than_current_bounded_baseline": bool(
                baseline_comparison.get(
                    "stronger_than_current_bounded_baseline",
                    controller_summary.get(
                        "stronger_than_current_bounded_baseline",
                        False,
                    ),
                )
            ),
            "future_reference_target_state": str(
                reference_target.get("reference_target_state", "")
            ).strip()
            or str(controller_summary.get("future_reference_target_state", "")).strip(),
            "future_reference_target_eligible": bool(
                reference_target.get(
                    "eligible_as_future_reference_target",
                    controller_summary.get("future_reference_target_eligible", False),
                )
            ),
            "future_reference_target_id": str(
                reference_target.get("preferred_reference_target_id", "")
            ).strip()
            or str(controller_summary.get("future_reference_target_id", "")).strip(),
            "revised_candidate_state": str(
                revised_candidate_bundle.get("revised_candidate_state", "")
            ).strip()
            or str(controller_summary.get("revised_candidate_state", "")).strip(),
            "revised_candidate_id": str(
                revised_candidate_bundle.get("revised_candidate_id", "")
            ).strip()
            or str(controller_summary.get("revised_candidate_id", "")).strip(),
            "revised_candidate_prior_admitted_candidate_id": str(
                revised_candidate_bundle.get("prior_admitted_candidate_id", "")
            ).strip()
            or str(
                controller_summary.get("revised_candidate_prior_admitted_candidate_id", "")
            ).strip(),
            "revised_candidate_materially_stronger_in_aggregate": bool(
                controller_summary.get(
                    "revised_candidate_materially_stronger_in_aggregate",
                    revised_candidate_comparison.get(
                        "materially_stronger_than_prior_admitted_candidate_in_aggregate",
                        False,
                    ),
                )
            ),
            "revised_candidate_reference_rollover_state": str(
                revised_candidate_promotion_summary.get("reference_target_rollover_state", "")
            ).strip()
            or str(
                controller_summary.get("revised_candidate_reference_rollover_state", "")
            ).strip(),
            "reference_target_consumption_state": str(
                reference_target_consumption.get("consumption_state", "")
            ).strip()
            or str(
                controller_summary.get("reference_target_consumption_state", "")
            ).strip(),
            "reference_target_fallback_reason": str(
                reference_target_consumption.get("fallback_reason", "")
            ).strip()
            or str(
                controller_summary.get("reference_target_fallback_reason", "")
            ).strip(),
            "active_bounded_reference_target_id": str(
                reference_target_consumption.get("active_bounded_reference_target_id", "")
            ).strip()
            or str(
                controller_summary.get("active_bounded_reference_target_id", "")
            ).strip()
            or str(reference_target.get("preferred_reference_target_id", "")).strip(),
            "active_bounded_reference_target_source_kind": str(
                reference_target_consumption.get(
                    "active_bounded_reference_target_source_kind",
                    "",
                )
            ).strip()
            or str(
                controller_summary.get(
                    "active_bounded_reference_target_source_kind",
                    "",
                )
            ).strip(),
            "active_bounded_reference_target_title": str(
                reference_target_consumption.get(
                    "active_bounded_reference_target_title",
                    "",
                )
            ).strip()
            or str(
                controller_summary.get("active_bounded_reference_target_title", "")
            ).strip(),
            "active_bounded_reference_target_path": str(
                reference_target_consumption.get("active_bounded_reference_target_path", "")
            ).strip()
            or str(
                controller_summary.get("active_bounded_reference_target_path", "")
            ).strip(),
            "protected_live_baseline_reference_id": str(
                reference_target_consumption.get(
                    "protected_live_baseline_reference_id",
                    "",
                )
            ).strip()
            or str(
                controller_summary.get(
                    "protected_live_baseline_reference_id",
                    "",
                )
            ).strip()
            or str(
                reference_target.get("protected_live_baseline_reference_id", "")
            ).strip()
            or "current_bounded_baseline_expectations_v1",
            "protected_live_baseline_source_kind": str(
                reference_target_consumption.get(
                    "protected_live_baseline_source_kind",
                    "",
                )
            ).strip()
            or str(
                controller_summary.get(
                    "protected_live_baseline_source_kind",
                    "",
                )
            ).strip()
            or str(
                reference_target.get("protected_live_baseline_source_kind", "")
            ).strip(),
            "protected_live_baseline_title": str(
                reference_target_consumption.get("protected_live_baseline_title", "")
            ).strip()
            or str(
                controller_summary.get("protected_live_baseline_title", "")
            ).strip()
            or str(reference_target.get("protected_live_baseline_title", "")).strip(),
            "protected_live_baseline_path_hint": str(
                reference_target_consumption.get(
                    "protected_live_baseline_path_hint",
                    "",
                )
            ).strip()
            or str(
                controller_summary.get("protected_live_baseline_path_hint", "")
            ).strip()
            or str(
                reference_target.get("protected_live_baseline_path_hint", "")
            ).strip(),
            "reference_target_comparison_basis": str(
                reference_target_consumption.get("comparison_basis", "")
            ).strip()
            or str(
                controller_summary.get("reference_target_comparison_basis", "")
            ).strip(),
            "selected_skill_pack_id": str(
                skill_pack_invocation.get("selected_skill_pack_id", "")
            ).strip()
            or str(controller_summary.get("selected_skill_pack_id", "")).strip(),
            "selected_skill_pack_title": str(
                skill_pack_invocation.get("selected_skill_pack_title", "")
            ).strip()
            or str(controller_summary.get("selected_skill_pack_title", "")).strip(),
            "selected_skill_pack_reason": str(
                skill_pack_invocation.get("selected_reason", "")
            ).strip()
            or str(controller_summary.get("selected_skill_pack_reason", "")).strip(),
            "skill_pack_result_state": str(
                skill_pack_result.get("result_state", "")
            ).strip()
            or str(controller_summary.get("skill_pack_result_state", "")).strip(),
            "quality_gap_id": str(quality_gap_summary.get("quality_gap_id", "")).strip()
            or str(controller_summary.get("quality_gap_id", "")).strip(),
            "quality_gap_title": str(
                quality_gap_summary.get("quality_gap_title", "")
            ).strip()
            or str(controller_summary.get("quality_gap_title", "")).strip(),
            "quality_improvement_state": str(
                quality_improvement_summary.get("improvement_state", "")
            ).strip()
            or str(controller_summary.get("quality_improvement_state", "")).strip(),
            "quality_dimension_id": str(
                quality_improvement_summary.get("quality_dimension_id", "")
            ).strip()
            or str(controller_summary.get("quality_dimension_id", "")).strip(),
            "quality_dimension_title": str(
                quality_improvement_summary.get("quality_dimension_title", "")
            ).strip()
            or str(controller_summary.get("quality_dimension_title", "")).strip(),
            "quality_composite_state": str(
                quality_composite_evaluation.get("composite_quality_state", "")
            ).strip()
            or str(controller_summary.get("quality_composite_state", "")).strip(),
            "materially_stronger_than_reference_target_in_aggregate": bool(
                controller_summary.get(
                    "materially_stronger_than_reference_target_in_aggregate",
                    quality_composite_evaluation.get(
                        "materially_stronger_than_reference_target_in_aggregate",
                        False,
                    ),
                )
            ),
            "quality_weakest_dimension_id": str(
                quality_priority_matrix.get("weakest_dimension_id", "")
            ).strip()
            or str(controller_summary.get("quality_weakest_dimension_id", "")).strip(),
            "quality_weakest_dimension_title": str(
                quality_priority_matrix.get("weakest_dimension_title", "")
            ).strip()
            or str(
                controller_summary.get("quality_weakest_dimension_title", "")
            ).strip(),
            "quality_next_pack_id": str(
                quality_next_pack_plan.get("selected_skill_pack_id", "")
            ).strip()
            or str(controller_summary.get("quality_next_pack_id", "")).strip(),
            "quality_next_objective_id": str(
                quality_next_pack_plan.get("selected_objective_id", "")
            ).strip()
            or str(controller_summary.get("quality_next_objective_id", "")).strip(),
            "quality_next_dimension_id": str(
                quality_next_pack_plan.get("selected_dimension_id", "")
            ).strip()
            or str(controller_summary.get("quality_next_dimension_id", "")).strip(),
            "quality_chain_reentry_state": str(
                quality_chain_reentry.get("reentry_state", "")
            ).strip()
            or str(controller_summary.get("quality_chain_reentry_state", "")).strip(),
            "quality_chain_reentry_reason": str(
                quality_chain_reentry.get("reentry_reason", "")
            ).strip()
            or str(controller_summary.get("quality_chain_reentry_reason", "")).strip(),
            "quality_chain_reentry_action": str(
                quality_chain_reentry.get("recommended_action", "")
            ).strip()
            or str(controller_summary.get("quality_chain_reentry_action", "")).strip(),
            "quality_chain_next_objective_id": str(
                quality_chain_reentry.get("next_quality_objective_id", "")
            ).strip()
            or str(controller_summary.get("quality_chain_next_objective_id", "")).strip(),
            "quality_chain_next_objective_class": str(
                quality_chain_reentry.get("next_quality_objective_class", "")
            ).strip()
            or str(controller_summary.get("quality_chain_next_objective_class", "")).strip(),
            "quality_chain_next_objective_compact": bool(
                quality_chain_reentry.get(
                    "next_quality_objective_compact",
                    controller_summary.get("quality_chain_next_objective_compact", False),
                )
            ),
            "generation_index": int(
                generation_history.get(
                    "current_generation_index",
                    controller_summary.get("generation_index", 0),
                )
                or 0
            ),
            "prior_generation_index": int(
                generation_delta.get(
                    "prior_generation_index",
                    controller_summary.get("prior_generation_index", 0),
                )
                or 0
            ),
            "generation_current_candidate_id": str(
                generation_delta.get("current_admitted_candidate_id", "")
            ).strip()
            or str(controller_summary.get("generation_current_candidate_id", "")).strip(),
            "generation_prior_candidate_id": str(
                generation_delta.get("prior_admitted_candidate_id", "")
            ).strip()
            or str(controller_summary.get("generation_prior_candidate_id", "")).strip(),
            "generation_progress_state": str(
                progress_governance.get("progress_state", "")
            ).strip()
            or str(controller_summary.get("generation_progress_state", "")).strip(),
            "generation_progress_recommendation_state": str(
                progress_recommendation.get("recommendation_state", "")
            ).strip()
            or str(
                controller_summary.get("generation_progress_recommendation_state", "")
            ).strip(),
            "generation_additional_improvement_justified": bool(
                progress_governance.get(
                    "additional_bounded_improvement_justified",
                    controller_summary.get(
                        "generation_additional_improvement_justified", False
                    ),
                )
            ),
            "generation_remediation_objective_id": str(
                progress_recommendation.get("recommended_objective_id", "")
            ).strip()
            or str(controller_summary.get("generation_remediation_objective_id", "")).strip(),
            "strategy_selection_state": str(
                strategy_selection.get("selected_strategy_state", "")
            ).strip()
            or str(controller_summary.get("strategy_selection_state", "")).strip(),
            "strategy_follow_on_family": str(
                strategy_follow_on_plan.get("follow_on_family", "")
            ).strip()
            or str(controller_summary.get("strategy_follow_on_family", "")).strip(),
            "strategy_operator_review_recommended": bool(
                strategy_follow_on_plan.get(
                    "operator_review_recommended_before_execution",
                    controller_summary.get(
                        "strategy_operator_review_recommended", False
                    ),
                )
            ),
            "strategy_selected_objective_id": str(
                strategy_follow_on_plan.get("recommended_objective_id", "")
            ).strip()
            or str(controller_summary.get("strategy_selected_objective_id", "")).strip(),
            "strategy_selected_objective_class": str(
                strategy_follow_on_plan.get("recommended_objective_class", "")
            ).strip()
            or str(
                controller_summary.get("strategy_selected_objective_class", "")
            ).strip(),
            "strategy_selected_skill_pack_id": str(
                strategy_follow_on_plan.get("recommended_skill_pack_id", "")
            ).strip()
            or str(controller_summary.get("strategy_selected_skill_pack_id", "")).strip(),
            "strategy_selected_dimension_id": str(
                strategy_follow_on_plan.get("recommended_dimension_id", "")
            ).strip()
            or str(controller_summary.get("strategy_selected_dimension_id", "")).strip(),
            "strategy_rationale_summary": str(
                strategy_rationale.get("selected_strategy_rationale", "")
            ).strip()
            or str(controller_summary.get("strategy_rationale_summary", "")).strip(),
            "campaign_id": str(
                campaign_history.get("current_campaign_id", "")
            ).strip()
            or str(controller_summary.get("campaign_id", "")).strip(),
            "campaign_wave_count": int(
                campaign_history.get(
                    "current_campaign_wave_count",
                    controller_summary.get("campaign_wave_count", 0),
                )
                or 0
            ),
            "campaign_progress_state": str(
                campaign_governance.get("campaign_progress_state", "")
            ).strip()
            or str(controller_summary.get("campaign_progress_state", "")).strip(),
            "campaign_state": str(
                campaign_governance.get("campaign_state", "")
            ).strip()
            or str(controller_summary.get("campaign_state", "")).strip(),
            "campaign_recommendation_state": str(
                campaign_recommendation.get("recommendation_state", "")
            ).strip()
            or str(controller_summary.get("campaign_recommendation_state", "")).strip(),
            "campaign_follow_on_family": str(
                campaign_wave_plan.get("recommended_follow_on_family", "")
            ).strip()
            or str(controller_summary.get("campaign_follow_on_family", "")).strip(),
            "campaign_refresh_revised_candidate_ready": bool(
                campaign_governance.get(
                    "refresh_revised_candidate_justified",
                    controller_summary.get(
                        "campaign_refresh_revised_candidate_ready",
                        False,
                    ),
                )
            ),
            "campaign_last_wave_strategy_state": str(
                campaign_delta.get("last_wave_strategy_state", "")
            ).strip()
            or str(controller_summary.get("campaign_last_wave_strategy_state", "")).strip(),
            "campaign_last_wave_skill_pack_id": str(
                campaign_delta.get("last_wave_skill_pack_id", "")
            ).strip()
            or str(controller_summary.get("campaign_last_wave_skill_pack_id", "")).strip(),
            "campaign_accumulated_improved_dimension_ids": list(
                campaign_governance.get(
                    "accumulated_improved_dimension_ids",
                    controller_summary.get(
                        "campaign_accumulated_improved_dimension_ids",
                        [],
                    ),
                )
            ),
            "campaign_remaining_weak_dimension_ids": list(
                campaign_governance.get(
                    "remaining_weak_dimension_ids",
                    controller_summary.get(
                        "campaign_remaining_weak_dimension_ids",
                        [],
                    ),
                )
            ),
            "campaign_cycle_id": str(
                campaign_cycle_history.get("current_campaign_cycle_id", "")
            ).strip()
            or str(controller_summary.get("campaign_cycle_id", "")).strip(),
            "campaign_cycle_index": int(
                campaign_cycle_history.get(
                    "current_campaign_cycle_index",
                    controller_summary.get("campaign_cycle_index", 0),
                )
                or 0
            ),
            "prior_campaign_cycle_index": int(
                campaign_cycle_delta.get(
                    "prior_campaign_cycle_index",
                    controller_summary.get("prior_campaign_cycle_index", 0),
                )
                or 0
            ),
            "campaign_cycle_progress_state": str(
                campaign_cycle_governance.get("campaign_cycle_progress_state", "")
            ).strip()
            or str(controller_summary.get("campaign_cycle_progress_state", "")).strip(),
            "campaign_cycle_state": str(
                campaign_cycle_governance.get("campaign_cycle_state", "")
            ).strip()
            or str(controller_summary.get("campaign_cycle_state", "")).strip(),
            "campaign_cycle_recommendation_state": str(
                campaign_cycle_recommendation.get("recommendation_state", "")
            ).strip()
            or str(
                controller_summary.get("campaign_cycle_recommendation_state", "")
            ).strip(),
            "campaign_cycle_follow_on_family": str(
                campaign_cycle_follow_on_plan.get("recommended_follow_on_family", "")
            ).strip()
            or str(controller_summary.get("campaign_cycle_follow_on_family", "")).strip(),
            "campaign_cycle_current_reference_target_id": str(
                campaign_cycle_delta.get("current_reference_target_id", "")
            ).strip()
            or str(
                controller_summary.get(
                    "campaign_cycle_current_reference_target_id", ""
                )
            ).strip(),
            "campaign_cycle_prior_reference_target_id": str(
                campaign_cycle_delta.get("prior_reference_target_id", "")
            ).strip()
            or str(
                controller_summary.get("campaign_cycle_prior_reference_target_id", "")
            ).strip(),
            "campaign_cycle_source_campaign_id": str(
                campaign_cycle_delta.get("source_campaign_id", "")
            ).strip()
            or str(controller_summary.get("campaign_cycle_source_campaign_id", "")).strip(),
            "campaign_cycle_new_dimension_ids": list(
                campaign_cycle_governance.get(
                    "new_dimension_ids_vs_prior_cycle",
                    controller_summary.get("campaign_cycle_new_dimension_ids", []),
                )
            ),
            "campaign_cycle_remaining_weak_dimension_ids": list(
                campaign_cycle_governance.get(
                    "remaining_weak_dimension_ids",
                    controller_summary.get(
                        "campaign_cycle_remaining_weak_dimension_ids",
                        [],
                    ),
                )
            ),
            "loop_id": str(loop_history.get("current_loop_id", "")).strip()
            or str(controller_summary.get("loop_id", "")).strip(),
            "loop_index": int(
                loop_history.get(
                    "current_loop_index",
                    controller_summary.get("loop_index", 0),
                )
                or 0
            ),
            "prior_loop_index": int(
                loop_delta.get(
                    "prior_loop_index",
                    controller_summary.get("prior_loop_index", 0),
                )
                or 0
            ),
            "loop_progress_state": str(
                loop_governance.get("loop_progress_state", "")
            ).strip()
            or str(controller_summary.get("loop_progress_state", "")).strip(),
            "loop_state": str(loop_governance.get("loop_state", "")).strip()
            or str(controller_summary.get("loop_state", "")).strip(),
            "loop_recommendation_state": str(
                loop_recommendation.get("recommendation_state", "")
            ).strip()
            or str(controller_summary.get("loop_recommendation_state", "")).strip(),
            "loop_follow_on_family": str(
                loop_follow_on_plan.get("recommended_follow_on_family", "")
            ).strip()
            or str(controller_summary.get("loop_follow_on_family", "")).strip(),
            "loop_current_reference_target_id": str(
                loop_delta.get("current_reference_target_id", "")
            ).strip()
            or str(controller_summary.get("loop_current_reference_target_id", "")).strip(),
            "loop_prior_reference_target_id": str(
                loop_delta.get("prior_reference_target_id", "")
            ).strip()
            or str(controller_summary.get("loop_prior_reference_target_id", "")).strip(),
            "loop_source_campaign_cycle_id": str(
                loop_delta.get("source_campaign_cycle_id", "")
            ).strip()
            or str(controller_summary.get("loop_source_campaign_cycle_id", "")).strip(),
            "loop_new_dimension_ids": list(
                loop_governance.get(
                    "new_dimension_ids_vs_prior_loop",
                    controller_summary.get("loop_new_dimension_ids", []),
                )
            ),
            "loop_remaining_weak_dimension_ids": list(
                loop_governance.get(
                    "remaining_weak_dimension_ids",
                    controller_summary.get("loop_remaining_weak_dimension_ids", []),
                )
            ),
            "comparison_remediation_objective_id": str(
                dict(baseline_comparison.get("remediation_proposal", {})).get(
                    "objective_id", ""
                )
            ).strip()
            or str(controller_summary.get("comparison_remediation_objective_id", "")).strip(),
            "effective_next_objective_authorization_origin": str(
                effective_next_objective.get("authorization_origin", "")
            ).strip()
            or str(controller_summary.get("effective_next_objective_authorization_origin", "")).strip(),
            "operator_review_required": bool(
                controller_summary.get("operator_review_required", review_summary.get("operator_review_required", False))
            ),
            "auto_continue_policy_path": auto_continue_policy_path,
            "auto_continue_state_path": auto_continue_state_path,
            "auto_continue_decision_path": auto_continue_decision_path,
            "auto_continue_enabled": bool(
                controller_summary.get("auto_continue_enabled", auto_continue_policy.get("enabled", False))
            ),
            "auto_continue_allowed_objective_classes": list(
                controller_summary.get(
                    "auto_continue_allowed_objective_classes",
                    auto_continue_policy.get("allowed_objective_classes", []),
                )
            ),
            "auto_continue_chain_count": int(
                controller_summary.get(
                    "auto_continue_chain_count",
                    auto_continue_state.get("current_chain_count", 0),
                )
                or 0
            ),
            "auto_continue_chain_cap": int(
                controller_summary.get(
                    "auto_continue_chain_cap",
                    auto_continue_policy.get("max_auto_continue_chain_length", 1),
                )
                or 1
            ),
            "staged_compact_follow_on_count": int(
                controller_summary.get("staged_compact_follow_on_count", 0) or 0
            ),
            "total_executed_objective_rows": int(
                controller_summary.get(
                    "total_executed_objective_rows",
                    controller_summary.get("cycles_completed", 0),
                )
                or 0
            ),
            "remaining_counted_cycle_budget": int(
                controller_summary.get(
                    "remaining_counted_cycle_budget",
                    auto_continue_decision.get(
                        "remaining_counted_cycle_budget",
                        auto_continue_state.get("remaining_counted_cycle_budget", 0),
                    ),
                )
                or 0
            ),
            "auto_continue_last_reason": str(
                controller_summary.get(
                    "auto_continue_last_reason",
                    auto_continue_decision.get("decision_reason", ""),
                )
            ).strip(),
            "auto_continue_last_origin": str(
                controller_summary.get(
                    "auto_continue_last_origin",
                    auto_continue_decision.get("authorization_origin", ""),
                )
            ).strip(),
            "budget_staging_decision": str(
                controller_summary.get(
                    "budget_staging_decision",
                    auto_continue_decision.get(
                        "staging_decision",
                        auto_continue_state.get(
                            "staging_decision",
                            auto_continue_transition.get("staging_decision", ""),
                        ),
                    ),
                )
            ).strip(),
            "budget_staging_rationale": str(
                controller_summary.get(
                    "budget_staging_rationale",
                    auto_continue_decision.get(
                        "staging_rationale",
                        auto_continue_state.get(
                            "staging_rationale",
                            auto_continue_transition.get("staging_rationale", ""),
                        ),
                    ),
                )
            ).strip(),
            "budget_staging_objective_id": str(
                controller_summary.get(
                    "budget_staging_objective_id",
                    auto_continue_decision.get(
                        "effective_objective_id",
                        auto_continue_transition.get("effective_objective_id", ""),
                    ),
                )
            ).strip(),
            "budget_staging_objective_class": str(
                controller_summary.get(
                    "budget_staging_objective_class",
                    auto_continue_decision.get(
                        "effective_objective_class",
                        auto_continue_transition.get("effective_objective_class", ""),
                    ),
                )
            ).strip(),
            "auto_continue_transition_state": str(
                controller_summary.get(
                    "auto_continue_transition_state",
                    auto_continue_transition.get("transition_state", ""),
                )
            ).strip(),
            "auto_continue_transition_executed_in_session": bool(
                controller_summary.get(
                    "auto_continue_transition_executed_in_session",
                    auto_continue_transition.get("transition_state", "") == "same_session_cycle_started",
                )
            ),
            "auto_continue_transition_from_objective_id": str(
                controller_summary.get(
                    "auto_continue_transition_from_objective_id",
                    auto_continue_transition.get("completed_objective_id", ""),
                )
            ).strip(),
            "auto_continue_transition_to_objective_id": str(
                controller_summary.get(
                    "auto_continue_transition_to_objective_id",
                    auto_continue_transition.get("effective_objective_id", ""),
                )
            ).strip(),
            "auto_continue_transition_cycle_index": int(
                controller_summary.get(
                    "auto_continue_transition_cycle_index",
                    auto_continue_transition.get("next_cycle_index", 0),
                )
                or 0
            ),
            "auto_continue_require_manual_approval_for_first_entry": bool(
                auto_continue_policy.get("require_manual_approval_for_first_entry", True)
            ),
            "auto_continue_require_review_supported_proposals": bool(
                auto_continue_policy.get("require_review_supported_proposals", True)
            ),
            "controller_artifact_path": controller_artifact_path,
            "latest_summary_artifact_path": summary_artifact_path,
            "latest_cycle_summary_archive_path": str(controller_summary.get("latest_cycle_summary_archive_path", "")).strip(),
            "implementation_summary_path": implementation_summary_path,
            "artifact_index_path": artifact_index_path,
            "trusted_planning_evidence_path": trusted_planning_evidence_path,
            "missing_deliverables_path": missing_deliverables_path,
            "next_step_derivation_path": next_step_derivation_path,
            "completion_evaluation_path": completion_evaluation_path,
            "review_summary_path": review_summary_path,
            "promotion_recommendation_path": promotion_recommendation_path,
            "next_objective_proposal_path": next_objective_proposal_path,
            "reseed_request_path": reseed_request_path,
            "reseed_decision_path": reseed_decision_path,
            "continuation_lineage_path": continuation_lineage_path,
            "effective_next_objective_path": effective_next_objective_path,
            "baseline_admission_review_path": baseline_admission_review_path,
            "baseline_admission_recommendation_path": baseline_admission_recommendation_path,
            "baseline_admission_decision_path": baseline_admission_decision_path,
            "baseline_remediation_proposal_path": baseline_remediation_proposal_path,
            "admitted_candidate_path": admitted_candidate_path,
            "admitted_candidate_handoff_path": admitted_candidate_handoff_path,
            "baseline_comparison_path": baseline_comparison_path,
            "reference_target_path": reference_target_path,
            "revised_candidate_bundle_path": revised_candidate_bundle_path,
            "revised_candidate_handoff_path": revised_candidate_handoff_path,
            "revised_candidate_comparison_path": revised_candidate_comparison_path,
            "revised_candidate_promotion_summary_path": revised_candidate_promotion_summary_path,
            "reference_target_consumption_path": reference_target_consumption_path,
            "skill_pack_invocation_path": skill_pack_invocation_path,
            "skill_pack_result_path": skill_pack_result_path,
            "quality_gap_summary_path": quality_gap_summary_path,
            "quality_improvement_summary_path": quality_improvement_summary_path,
            "quality_roadmap_path": quality_roadmap_path,
            "quality_priority_matrix_path": quality_priority_matrix_path,
            "quality_composite_evaluation_path": quality_composite_evaluation_path,
            "quality_next_pack_plan_path": quality_next_pack_plan_path,
            "quality_chain_reentry_path": quality_chain_reentry_path,
            "generation_history_path": generation_history_path,
            "generation_delta_path": generation_delta_path,
            "progress_governance_path": progress_governance_path,
            "progress_recommendation_path": progress_recommendation_path,
            "strategy_selection_path": strategy_selection_path,
            "strategy_rationale_path": strategy_rationale_path,
            "strategy_follow_on_plan_path": strategy_follow_on_plan_path,
            "strategy_decision_support_path": strategy_decision_support_path,
            "campaign_history_path": campaign_history_path,
            "campaign_delta_path": campaign_delta_path,
            "campaign_governance_path": campaign_governance_path,
            "campaign_recommendation_path": campaign_recommendation_path,
            "campaign_wave_plan_path": campaign_wave_plan_path,
            "campaign_cycle_history_path": campaign_cycle_history_path,
            "campaign_cycle_delta_path": campaign_cycle_delta_path,
            "campaign_cycle_governance_path": campaign_cycle_governance_path,
            "campaign_cycle_recommendation_path": campaign_cycle_recommendation_path,
            "campaign_cycle_follow_on_plan_path": campaign_cycle_follow_on_plan_path,
            "loop_history_path": loop_history_path,
            "loop_delta_path": loop_delta_path,
            "loop_governance_path": loop_governance_path,
            "loop_recommendation_path": loop_recommendation_path,
            "loop_follow_on_plan_path": loop_follow_on_plan_path,
            "auto_continue_policy_path": auto_continue_policy_path,
            "auto_continue_state_path": auto_continue_state_path,
            "auto_continue_decision_path": auto_continue_decision_path,
            "auto_continue_transition_path": auto_continue_transition_path,
            "runtime_event_log_path": runtime_event_log_path,
            "launch_plan_path": str(
                launch_context.get("operator_runtime_launch_plan_path", "")
                or dict(dashboard.get("operator_paths", {})).get("operator_runtime_launch_plan_path", "")
                or str(operator_snapshot.get("operator_runtime_launch_plan_path", ""))
            ).strip(),
            "session_artifact_path": session_artifact_path,
            "invocation_model": invocation_model,
            "controller_summary": controller_summary,
            "cycle_rows": list(controller_summary.get("cycle_rows", [])),
            "work_summary": work_summary,
            "implementation_summary": implementation_summary,
            "artifact_index": artifact_index,
            "trusted_planning_evidence": trusted_planning_evidence,
            "missing_deliverables_summary": missing_deliverables_summary,
            "next_step_derivation": next_step_derivation,
            "completion_evaluation": completion_evaluation,
            "review_summary": review_summary,
            "promotion_recommendation": promotion_recommendation,
            "next_objective_proposal": next_objective_proposal,
            "reseed_request": reseed_request,
            "reseed_decision": reseed_decision,
            "continuation_lineage": continuation_lineage,
            "effective_next_objective": effective_next_objective,
            "baseline_admission_review": baseline_admission_review,
            "baseline_admission_recommendation": baseline_admission_recommendation,
            "baseline_admission_decision": baseline_admission_decision,
            "baseline_remediation_proposal": baseline_remediation_proposal,
            "admitted_candidate": admitted_candidate,
            "admitted_candidate_handoff": admitted_candidate_handoff,
            "baseline_comparison": baseline_comparison,
            "reference_target": reference_target,
            "successor_revised_candidate_bundle": revised_candidate_bundle,
            "successor_revised_candidate_handoff": revised_candidate_handoff,
            "successor_revised_candidate_comparison": revised_candidate_comparison,
            "successor_revised_candidate_promotion_summary": revised_candidate_promotion_summary,
            "reference_target_consumption": reference_target_consumption,
            "successor_skill_pack_invocation": skill_pack_invocation,
            "successor_skill_pack_result": skill_pack_result,
            "successor_quality_gap_summary": quality_gap_summary,
            "successor_quality_improvement_summary": quality_improvement_summary,
            "successor_quality_roadmap": quality_roadmap,
            "successor_quality_priority_matrix": quality_priority_matrix,
            "successor_quality_composite_evaluation": quality_composite_evaluation,
            "successor_quality_next_pack_plan": quality_next_pack_plan,
            "successor_quality_chain_reentry": quality_chain_reentry,
            "successor_generation_history": generation_history,
            "successor_generation_delta": generation_delta,
            "successor_progress_governance": progress_governance,
            "successor_progress_recommendation": progress_recommendation,
            "successor_strategy_selection": strategy_selection,
            "successor_strategy_rationale": strategy_rationale,
            "successor_strategy_follow_on_plan": strategy_follow_on_plan,
            "successor_strategy_decision_support": strategy_decision_support,
            "successor_campaign_history": campaign_history,
            "successor_campaign_delta": campaign_delta,
            "successor_campaign_governance": campaign_governance,
            "successor_campaign_recommendation": campaign_recommendation,
            "successor_campaign_wave_plan": campaign_wave_plan,
            "successor_campaign_cycle_history": campaign_cycle_history,
            "successor_campaign_cycle_delta": campaign_cycle_delta,
            "successor_campaign_cycle_governance": campaign_cycle_governance,
            "successor_campaign_cycle_recommendation": campaign_cycle_recommendation,
            "successor_campaign_cycle_follow_on_plan": campaign_cycle_follow_on_plan,
            "successor_loop_history": loop_history,
            "successor_loop_delta": loop_delta,
            "successor_loop_governance": loop_governance,
            "successor_loop_recommendation": loop_recommendation,
            "successor_loop_follow_on_plan": loop_follow_on_plan,
            "auto_continue_policy": auto_continue_policy,
            "auto_continue_state": auto_continue_state,
            "auto_continue_decision": auto_continue_decision,
            "auto_continue_transition": auto_continue_transition,
            "session_summary": session_summary,
            "runtime_events": runtime_events,
            "output_artifact_paths": output_artifact_paths,
            "newly_created_paths": newly_created_paths,
            "skipped_items": skipped_items,
            "deferred_items": deferred_items,
        }

    def _workspace_artifact_groups(self, snapshot: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        workspace_root = str(snapshot.get("workspace_root", "")).strip()
        if not workspace_root:
            return {category: [] for category in WORKSPACE_ARTIFACT_CATEGORIES}
        workspace_root_path = Path(workspace_root)
        index = dict(snapshot.get("artifact_index", {}))
        records = []
        for item in list(index.get("artifacts", [])):
            relative_path = str(item.get("relative_path", "")).strip()
            if not relative_path:
                continue
            records.append(
                {
                    "relative_path": relative_path,
                    "category": str(item.get("category", "")).strip() or _slug(Path(relative_path).parts[0], fallback="other"),
                }
            )
        if not records:
            for path in sorted(workspace_root_path.rglob("*")):
                if not path.is_file():
                    continue
                relative_path = path.relative_to(workspace_root_path).as_posix()
                category = Path(relative_path).parts[0] if Path(relative_path).parts else "other"
                records.append({"relative_path": relative_path, "category": category})

        groups: dict[str, list[dict[str, Any]]] = {category: [] for category in WORKSPACE_ARTIFACT_CATEGORIES}
        for record in records:
            category = str(record.get("category", "")).strip()
            if category not in groups:
                continue
            relative_path = str(record.get("relative_path", "")).strip()
            absolute_path = workspace_root_path / Path(relative_path)
            if not absolute_path.exists() or not absolute_path.is_file():
                continue
            stat = absolute_path.stat()
            groups[category].append(
                {
                    "category": category,
                    "relative_path": relative_path,
                    "absolute_path": str(absolute_path),
                    "modified_at": _format_timestamp(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()),
                    "size_display": _format_bytes(stat.st_size),
                    "size_bytes": int(stat.st_size),
                    "is_key_artifact": relative_path in KEY_WORKSPACE_ARTIFACTS,
                    "preview_href": self._preview_link_for_path(str(absolute_path)),
                }
            )
        for category in groups:
            groups[category].sort(
                key=lambda item: (
                    0 if item.get("is_key_artifact") else 1,
                    str(item.get("relative_path", "")).lower(),
                )
            )
        return groups

    def _preview_allowed_roots(self, snapshot: dict[str, Any]) -> list[Path]:
        roots = [
            self.package_root,
            self.operator_root,
            self.state_root,
            self.evidence_root,
            self.directive_root,
        ]
        workspace_root = str(snapshot.get("workspace_root", "")).strip()
        if workspace_root:
            roots.append(Path(workspace_root))
        unique: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            normalized = _normalize_path(root)
            if normalized in seen:
                continue
            seen.add(normalized)
            unique.append(Path(normalized))
        return unique

    def _resolve_preview_path(self, requested_path: str) -> Path | None:
        normalized = str(requested_path or "").strip()
        if not normalized:
            return None
        try:
            candidate = Path(normalized).resolve()
        except OSError:
            return None
        if candidate.suffix.lower() not in PREVIEWABLE_SUFFIXES:
            return None
        if not candidate.exists() or not candidate.is_file():
            return None
        snapshot = self._observability_snapshot()
        if not any(_is_under_path(candidate, root) for root in self._preview_allowed_roots(snapshot)):
            return None
        return candidate

    def _event_detail_lines(self, event: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        if event.get("cycle_index") not in {None, ""}:
            lines.append(f"Cycle index: <code>{html.escape(str(event['cycle_index']))}</code>")
        if event.get("completed_cycle_index") not in {None, ""}:
            lines.append(
                f"Completed cycle: <code>{html.escape(str(event['completed_cycle_index']))}</code>"
            )
        if event.get("next_cycle_index") not in {None, ""}:
            lines.append(f"Next cycle: <code>{html.escape(str(event['next_cycle_index']))}</code>")
        if str(event.get("controller_mode", "")).strip():
            lines.append(f"Controller mode: <code>{html.escape(str(event['controller_mode']))}</code>")
        if str(event.get("stage_id", "")).strip():
            lines.append(f"Stage: <code>{html.escape(str(event['stage_id']))}</code>")
        if str(event.get("work_item_id", "")).strip():
            lines.append(f"Work item: <code>{html.escape(str(event['work_item_id']))}</code>")
        if str(event.get("cycle_kind", "")).strip():
            lines.append(f"Cycle kind: <code>{html.escape(str(event['cycle_kind']))}</code>")
        if str(event.get("status", "")).strip():
            lines.append(f"Status: <code>{html.escape(str(event['status']))}</code>")
        if str(event.get("stop_reason", "")).strip():
            lines.append(f"Stop reason: <code>{html.escape(str(event['stop_reason']))}</code>")
        if event.get("missing_required_deliverable_count") not in {None, ""}:
            lines.append(
                f"Missing deliverables: <code>{html.escape(str(event['missing_required_deliverable_count']))}</code>"
            )
        if str(event.get("next_recommended_cycle", "")).strip():
            lines.append(
                f"Next recommended cycle: <code>{html.escape(str(event['next_recommended_cycle']))}</code>"
            )
        if str(event.get("review_status", "")).strip():
            lines.append(f"Review status: <code>{html.escape(str(event['review_status']))}</code>")
        if str(event.get("promotion_recommendation_state", "")).strip():
            lines.append(
                "Promotion recommendation: "
                f"<code>{html.escape(str(event['promotion_recommendation_state']))}</code>"
            )
        if str(event.get("admission_review_state", "")).strip():
            lines.append(
                f"Admission review: <code>{html.escape(str(event['admission_review_state']))}</code>"
            )
        if str(event.get("admission_recommendation_state", "")).strip():
            lines.append(
                "Admission recommendation: "
                f"<code>{html.escape(str(event['admission_recommendation_state']))}</code>"
            )
        if str(event.get("admission_decision_state", "")).strip():
            lines.append(
                f"Admission decision: <code>{html.escape(str(event['admission_decision_state']))}</code>"
            )
        if event.get("admitted_bounded_baseline_candidate") not in {None, ""}:
            lines.append(
                "Admitted bounded baseline candidate: "
                f"<code>{html.escape('yes' if bool(event.get('admitted_bounded_baseline_candidate', False)) else 'no')}</code>"
            )
        if str(event.get("admitted_candidate_state", "")).strip():
            lines.append(
                f"Admitted candidate state: <code>{html.escape(str(event['admitted_candidate_state']))}</code>"
            )
        if str(event.get("revised_candidate_state", "")).strip():
            lines.append(
                f"Revised candidate state: <code>{html.escape(str(event['revised_candidate_state']))}</code>"
            )
        if str(event.get("revised_candidate_id", "")).strip():
            lines.append(
                f"Revised candidate id: <code>{html.escape(str(event['revised_candidate_id']))}</code>"
            )
        if str(event.get("revised_candidate_prior_admitted_candidate_id", "")).strip():
            lines.append(
                "Prior admitted candidate: "
                f"<code>{html.escape(str(event['revised_candidate_prior_admitted_candidate_id']))}</code>"
            )
        if str(event.get("reference_target_rollover_state", "")).strip():
            lines.append(
                "Reference target rollover: "
                f"<code>{html.escape(str(event['reference_target_rollover_state']))}</code>"
            )
        if str(event.get("future_reference_target_state", "")).strip():
            lines.append(
                "Future reference target: "
                f"<code>{html.escape(str(event['future_reference_target_state']))}</code>"
            )
        if event.get("future_reference_target_eligible") not in {None, ""}:
            lines.append(
                "Future reference eligible: "
                f"<code>{html.escape('yes' if bool(event.get('future_reference_target_eligible', False)) else 'no')}</code>"
            )
        if event.get("stronger_than_current_bounded_baseline") not in {None, ""}:
            lines.append(
                "Stronger than current bounded baseline: "
                f"<code>{html.escape('yes' if bool(event.get('stronger_than_current_bounded_baseline', False)) else 'no')}</code>"
            )
        if str(event.get("preferred_reference_target_id", "")).strip():
            lines.append(
                "Preferred reference target: "
                f"<code>{html.escape(str(event['preferred_reference_target_id']))}</code>"
            )
        if str(event.get("reference_target_consumption_state", "")).strip():
            lines.append(
                "Reference target consumption: "
                f"<code>{html.escape(str(event['reference_target_consumption_state']))}</code>"
            )
        if str(event.get("active_bounded_reference_target_id", "")).strip():
            lines.append(
                "Active bounded reference target: "
                f"<code>{html.escape(str(event['active_bounded_reference_target_id']))}</code>"
            )
        if str(event.get("protected_live_baseline_reference_id", "")).strip():
            lines.append(
                "Protected live baseline: "
                f"<code>{html.escape(str(event['protected_live_baseline_reference_id']))}</code>"
            )
        if str(event.get("comparison_basis", "")).strip():
            lines.append(
                f"Comparison basis: <code>{html.escape(str(event['comparison_basis']))}</code>"
            )
        if event.get("generation_index") not in {None, ""}:
            lines.append(
                f"Generation index: <code>{html.escape(str(event['generation_index']))}</code>"
            )
        if str(event.get("current_admitted_candidate_id", "")).strip():
            lines.append(
                "Current admitted candidate: "
                f"<code>{html.escape(str(event['current_admitted_candidate_id']))}</code>"
            )
        if str(event.get("prior_admitted_candidate_id", "")).strip():
            lines.append(
                "Prior admitted candidate: "
                f"<code>{html.escape(str(event['prior_admitted_candidate_id']))}</code>"
            )
        if str(event.get("progress_state", "")).strip():
            lines.append(
                f"Progress state: <code>{html.escape(str(event['progress_state']))}</code>"
            )
        if str(event.get("progress_recommendation_state", "")).strip():
            lines.append(
                "Progress recommendation: "
                f"<code>{html.escape(str(event['progress_recommendation_state']))}</code>"
            )
        if str(event.get("strategy_state", "")).strip():
            lines.append(
                f"Strategy selection: <code>{html.escape(str(event['strategy_state']))}</code>"
            )
        if str(event.get("follow_on_family", "")).strip():
            lines.append(
                f"Strategy follow-on family: <code>{html.escape(str(event['follow_on_family']))}</code>"
            )
        if str(event.get("follow_on_objective_id", "")).strip():
            lines.append(
                f"Strategy follow-on objective: <code>{html.escape(str(event['follow_on_objective_id']))}</code>"
            )
        if event.get("operator_review_recommended") not in {None, ""}:
            lines.append(
                "Operator review recommended: "
                f"<code>{html.escape('yes' if bool(event.get('operator_review_recommended', False)) else 'no')}</code>"
            )
        if str(event.get("campaign_id", "")).strip():
            lines.append(
                f"Campaign id: <code>{html.escape(str(event['campaign_id']))}</code>"
            )
        if event.get("campaign_wave_count") not in {None, ""}:
            lines.append(
                f"Campaign wave count: <code>{html.escape(str(event['campaign_wave_count']))}</code>"
            )
        if str(event.get("campaign_progress_state", "")).strip():
            lines.append(
                "Campaign progress: "
                f"<code>{html.escape(str(event['campaign_progress_state']))}</code>"
            )
        if str(event.get("campaign_recommendation_state", "")).strip():
            lines.append(
                "Campaign recommendation: "
                f"<code>{html.escape(str(event['campaign_recommendation_state']))}</code>"
            )
        if str(event.get("campaign_follow_on_family", "")).strip():
            lines.append(
                "Campaign follow-on family: "
                f"<code>{html.escape(str(event['campaign_follow_on_family']))}</code>"
            )
        if event.get("refresh_revised_candidate_justified") not in {None, ""}:
            lines.append(
                "Campaign refresh justified: "
                f"<code>{html.escape('yes' if bool(event.get('refresh_revised_candidate_justified', False)) else 'no')}</code>"
            )
        if str(event.get("fallback_reason", "")).strip():
            lines.append(
                f"Fallback reason: {html.escape(str(event['fallback_reason']))}"
            )
        if event.get("remediation_required") not in {None, ""}:
            lines.append(
                "Remediation required: "
                f"<code>{html.escape('yes' if bool(event.get('remediation_required', False)) else 'no')}</code>"
            )
        if str(event.get("remediation_objective_id", "")).strip():
            lines.append(
                f"Remediation objective: <code>{html.escape(str(event['remediation_objective_id']))}</code>"
            )
        if str(event.get("proposed_objective_id", "")).strip():
            lines.append(
                f"Proposed objective: <code>{html.escape(str(event['proposed_objective_id']))}</code>"
            )
        if str(event.get("objective_class", "")).strip():
            lines.append(
                f"Objective class: <code>{html.escape(str(event['objective_class']))}</code>"
            )
        if str(event.get("effective_objective_id", "")).strip():
            lines.append(
                f"Effective objective: <code>{html.escape(str(event['effective_objective_id']))}</code>"
            )
        if str(event.get("operator_decision", "")).strip():
            lines.append(
                f"Operator decision: <code>{html.escape(str(event['operator_decision']))}</code>"
            )
        if str(event.get("reseed_state", "")).strip():
            lines.append(f"Reseed state: <code>{html.escape(str(event['reseed_state']))}</code>")
        if event.get("continuation_authorized") not in {None, ""}:
            lines.append(
                "Continuation authorized: "
                f"<code>{html.escape('yes' if bool(event.get('continuation_authorized', False)) else 'no')}</code>"
            )
        if str(event.get("authorization_origin", "")).strip():
            lines.append(
                f"Continuation origin: <code>{html.escape(str(event['authorization_origin']))}</code>"
            )
        if str(event.get("transition_state", "")).strip():
            lines.append(
                f"Transition state: <code>{html.escape(str(event['transition_state']))}</code>"
            )
        if str(event.get("auto_continue_reason", "")).strip():
            lines.append(
                f"Auto-continue reason: <code>{html.escape(str(event['auto_continue_reason']))}</code>"
            )
        if event.get("auto_continue_chain_count") not in {None, ""}:
            lines.append(
                "Auto-continue chain: "
                f"<code>{html.escape(str(event.get('auto_continue_chain_count')))}</code>"
                "/"
                f"<code>{html.escape(str(event.get('max_auto_continue_chain_length', '')))}</code>"
            )
        if str(event.get("staging_decision", "")).strip():
            lines.append(
                "Budget staging decision: "
                f"<code>{html.escape(str(event.get('staging_decision', '')))}</code>"
            )
        if str(event.get("staging_rationale", "")).strip():
            lines.append(
                f"Budget staging rationale: {html.escape(str(event.get('staging_rationale', '')))}"
            )
        if event.get("remaining_counted_cycle_budget") not in {None, ""}:
            lines.append(
                "Remaining counted cycle budget: "
                f"<code>{html.escape(str(event.get('remaining_counted_cycle_budget')))}</code>"
            )
        if event.get("counts_toward_cycle_cap") not in {None, ""}:
            lines.append(
                "Counts toward cycle cap: "
                f"<code>{html.escape('yes' if bool(event.get('counts_toward_cycle_cap', False)) else 'no')}</code>"
            )
        if str(event.get("completion_evaluation_path", "")).strip():
            lines.append(
                f"Completion evaluation: {self._render_path_html(str(event['completion_evaluation_path']))}"
            )
        if str(event.get("next_step_derivation_path", "")).strip():
            lines.append(
                f"Next-step derivation: {self._render_path_html(str(event['next_step_derivation_path']))}"
            )
        if str(event.get("recommendation_path", "")).strip():
            lines.append(
                f"Promotion recommendation: {self._render_path_html(str(event['recommendation_path']))}"
            )
        if str(event.get("next_objective_proposal_path", "")).strip():
            lines.append(
                f"Next-objective proposal: {self._render_path_html(str(event['next_objective_proposal_path']))}"
            )
        if str(event.get("review_summary_path", "")).strip():
            lines.append(
                f"Review summary: {self._render_path_html(str(event['review_summary_path']))}"
            )
        if str(event.get("admission_review_path", "")).strip():
            lines.append(
                f"Admission review: {self._render_path_html(str(event['admission_review_path']))}"
            )
        if str(event.get("admission_decision_path", "")).strip():
            lines.append(
                f"Admission decision: {self._render_path_html(str(event['admission_decision_path']))}"
            )
        if str(event.get("remediation_proposal_path", "")).strip():
            lines.append(
                "Remediation proposal: "
                f"{self._render_path_html(str(event['remediation_proposal_path']))}"
            )
        if str(event.get("admitted_candidate_path", "")).strip():
            lines.append(
                "Admitted candidate: "
                f"{self._render_path_html(str(event['admitted_candidate_path']))}"
            )
        if str(event.get("handoff_path", "")).strip():
            lines.append(
                "Candidate handoff: "
                f"{self._render_path_html(str(event['handoff_path']))}"
            )
        if str(event.get("comparison_path", "")).strip():
            lines.append(
                "Baseline comparison: "
                f"{self._render_path_html(str(event['comparison_path']))}"
            )
        if str(event.get("reference_target_path", "")).strip():
            lines.append(
                "Reference target: "
                f"{self._render_path_html(str(event['reference_target_path']))}"
            )
        if str(event.get("revised_candidate_bundle_path", "")).strip():
            lines.append(
                "Revised candidate bundle: "
                f"{self._render_path_html(str(event['revised_candidate_bundle_path']))}"
            )
        if str(event.get("revised_candidate_handoff_path", "")).strip():
            lines.append(
                "Revised candidate handoff: "
                f"{self._render_path_html(str(event['revised_candidate_handoff_path']))}"
            )
        if str(event.get("revised_candidate_comparison_path", "")).strip():
            lines.append(
                "Revised candidate comparison: "
                f"{self._render_path_html(str(event['revised_candidate_comparison_path']))}"
            )
        if str(event.get("revised_candidate_promotion_summary_path", "")).strip():
            lines.append(
                "Revised candidate promotion summary: "
                f"{self._render_path_html(str(event['revised_candidate_promotion_summary_path']))}"
            )
        if str(event.get("reference_target_consumption_path", "")).strip():
            lines.append(
                "Reference target consumption: "
                f"{self._render_path_html(str(event['reference_target_consumption_path']))}"
            )
        if str(event.get("selected_skill_pack_id", "")).strip():
            lines.append(
                f"Selected skill pack: <code>{html.escape(str(event['selected_skill_pack_id']))}</code>"
            )
        if str(event.get("skill_pack_result_state", "")).strip():
            lines.append(
                f"Skill-pack result: <code>{html.escape(str(event['skill_pack_result_state']))}</code>"
            )
        if str(event.get("quality_gap_id", "")).strip():
            lines.append(
                f"Quality gap: <code>{html.escape(str(event['quality_gap_id']))}</code>"
            )
        if str(event.get("skill_pack_invocation_path", "")).strip():
            lines.append(
                "Skill-pack invocation: "
                f"{self._render_path_html(str(event['skill_pack_invocation_path']))}"
            )
        if str(event.get("skill_pack_result_path", "")).strip():
            lines.append(
                "Skill-pack result: "
                f"{self._render_path_html(str(event['skill_pack_result_path']))}"
            )
        if str(event.get("quality_gap_summary_path", "")).strip():
            lines.append(
                "Quality gap summary: "
                f"{self._render_path_html(str(event['quality_gap_summary_path']))}"
            )
        if str(event.get("quality_improvement_summary_path", "")).strip():
            lines.append(
                "Quality improvement summary: "
                f"{self._render_path_html(str(event['quality_improvement_summary_path']))}"
            )
        if str(event.get("quality_dimension_id", "")).strip():
            lines.append(
                f"Quality dimension: <code>{html.escape(str(event['quality_dimension_id']))}</code>"
            )
        if str(event.get("quality_composite_state", "")).strip():
            lines.append(
                f"Quality composite state: <code>{html.escape(str(event['quality_composite_state']))}</code>"
            )
        if str(event.get("quality_roadmap_path", "")).strip():
            lines.append(
                "Quality roadmap: "
                f"{self._render_path_html(str(event['quality_roadmap_path']))}"
            )
        if str(event.get("quality_next_pack_plan_path", "")).strip():
            lines.append(
                "Quality next-pack plan: "
                f"{self._render_path_html(str(event['quality_next_pack_plan_path']))}"
            )
        if str(event.get("reentry_state", "")).strip():
            lines.append(
                f"Quality-chain reentry state: <code>{html.escape(str(event['reentry_state']))}</code>"
            )
        if str(event.get("recommended_action", "")).strip():
            lines.append(
                f"Recommended action: <code>{html.escape(str(event['recommended_action']))}</code>"
            )
        if str(event.get("quality_chain_reentry_path", "")).strip():
            lines.append(
                "Quality-chain reentry artifact: "
                f"{self._render_path_html(str(event['quality_chain_reentry_path']))}"
            )
        if str(event.get("generation_history_path", "")).strip():
            lines.append(
                "Generation history: "
                f"{self._render_path_html(str(event['generation_history_path']))}"
            )
        if str(event.get("generation_delta_path", "")).strip():
            lines.append(
                "Generation delta: "
                f"{self._render_path_html(str(event['generation_delta_path']))}"
            )
        if str(event.get("progress_governance_path", "")).strip():
            lines.append(
                "Progress governance: "
                f"{self._render_path_html(str(event['progress_governance_path']))}"
            )
        if str(event.get("progress_recommendation_path", "")).strip():
            lines.append(
                "Progress recommendation: "
                f"{self._render_path_html(str(event['progress_recommendation_path']))}"
            )
        if str(event.get("strategy_selection_path", "")).strip():
            lines.append(
                "Strategy selection: "
                f"{self._render_path_html(str(event['strategy_selection_path']))}"
            )
        if str(event.get("strategy_follow_on_plan_path", "")).strip():
            lines.append(
                "Strategy follow-on plan: "
                f"{self._render_path_html(str(event['strategy_follow_on_plan_path']))}"
            )
        if str(event.get("campaign_history_path", "")).strip():
            lines.append(
                "Campaign history: "
                f"{self._render_path_html(str(event['campaign_history_path']))}"
            )
        if str(event.get("campaign_delta_path", "")).strip():
            lines.append(
                "Campaign delta: "
                f"{self._render_path_html(str(event['campaign_delta_path']))}"
            )
        if str(event.get("campaign_governance_path", "")).strip():
            lines.append(
                "Campaign governance: "
                f"{self._render_path_html(str(event['campaign_governance_path']))}"
            )
        if str(event.get("campaign_recommendation_path", "")).strip():
            lines.append(
                "Campaign recommendation: "
                f"{self._render_path_html(str(event['campaign_recommendation_path']))}"
            )
        if str(event.get("campaign_wave_plan_path", "")).strip():
            lines.append(
                "Campaign wave plan: "
                f"{self._render_path_html(str(event['campaign_wave_plan_path']))}"
            )
        if str(event.get("campaign_cycle_progress_state", "")).strip():
            lines.append(
                "Campaign-cycle progress state: "
                f"<code>{html.escape(str(event['campaign_cycle_progress_state']))}</code>"
            )
        if str(event.get("campaign_cycle_recommendation_state", "")).strip():
            lines.append(
                "Campaign-cycle recommendation: "
                f"<code>{html.escape(str(event['campaign_cycle_recommendation_state']))}</code>"
            )
        if str(event.get("campaign_cycle_follow_on_family", "")).strip():
            lines.append(
                "Campaign-cycle follow-on family: "
                f"<code>{html.escape(str(event['campaign_cycle_follow_on_family']))}</code>"
            )
        if str(event.get("campaign_cycle_history_path", "")).strip():
            lines.append(
                "Campaign-cycle history: "
                f"{self._render_path_html(str(event['campaign_cycle_history_path']))}"
            )
        if str(event.get("campaign_cycle_delta_path", "")).strip():
            lines.append(
                "Campaign-cycle delta: "
                f"{self._render_path_html(str(event['campaign_cycle_delta_path']))}"
            )
        if str(event.get("campaign_cycle_governance_path", "")).strip():
            lines.append(
                "Campaign-cycle governance: "
                f"{self._render_path_html(str(event['campaign_cycle_governance_path']))}"
            )
        if str(event.get("campaign_cycle_recommendation_path", "")).strip():
            lines.append(
                "Campaign-cycle recommendation artifact: "
                f"{self._render_path_html(str(event['campaign_cycle_recommendation_path']))}"
            )
        if str(event.get("campaign_cycle_follow_on_plan_path", "")).strip():
            lines.append(
                "Campaign-cycle follow-on plan: "
                f"{self._render_path_html(str(event['campaign_cycle_follow_on_plan_path']))}"
            )
        if str(event.get("loop_progress_state", "")).strip():
            lines.append(
                "Loop progress state: "
                f"<code>{html.escape(str(event['loop_progress_state']))}</code>"
            )
        if str(event.get("loop_recommendation_state", "")).strip():
            lines.append(
                "Loop recommendation: "
                f"<code>{html.escape(str(event['loop_recommendation_state']))}</code>"
            )
        if str(event.get("loop_follow_on_family", "")).strip():
            lines.append(
                "Loop follow-on family: "
                f"<code>{html.escape(str(event['loop_follow_on_family']))}</code>"
            )
        if str(event.get("loop_history_path", "")).strip():
            lines.append(
                "Loop history: "
                f"{self._render_path_html(str(event['loop_history_path']))}"
            )
        if str(event.get("loop_delta_path", "")).strip():
            lines.append(
                "Loop delta: "
                f"{self._render_path_html(str(event['loop_delta_path']))}"
            )
        if str(event.get("loop_governance_path", "")).strip():
            lines.append(
                "Loop governance: "
                f"{self._render_path_html(str(event['loop_governance_path']))}"
            )
        if str(event.get("loop_recommendation_path", "")).strip():
            lines.append(
                "Loop recommendation artifact: "
                f"{self._render_path_html(str(event['loop_recommendation_path']))}"
            )
        if str(event.get("loop_follow_on_plan_path", "")).strip():
            lines.append(
                "Loop follow-on plan: "
                f"{self._render_path_html(str(event['loop_follow_on_plan_path']))}"
            )
        if str(event.get("reseed_request_path", "")).strip():
            lines.append(
                f"Reseed request: {self._render_path_html(str(event['reseed_request_path']))}"
            )
        if str(event.get("reseed_decision_path", "")).strip():
            lines.append(
                f"Reseed decision: {self._render_path_html(str(event['reseed_decision_path']))}"
            )
        if str(event.get("effective_next_objective_path", "")).strip():
            lines.append(
                "Effective next objective: "
                f"{self._render_path_html(str(event['effective_next_objective_path']))}"
            )
        if str(event.get("auto_continue_policy_path", "")).strip():
            lines.append(
                "Auto-continue policy: "
                f"{self._render_path_html(str(event['auto_continue_policy_path']))}"
            )
        if str(event.get("auto_continue_state_path", "")).strip():
            lines.append(
                "Auto-continue state: "
                f"{self._render_path_html(str(event['auto_continue_state_path']))}"
            )
        if str(event.get("auto_continue_decision_path", "")).strip():
            lines.append(
                "Auto-continue decision: "
                f"{self._render_path_html(str(event['auto_continue_decision_path']))}"
            )
        if str(event.get("continuation_transition_path", "")).strip():
            lines.append(
                "Auto-continue transition: "
                f"{self._render_path_html(str(event['continuation_transition_path']))}"
            )
        consulted_sources = list(event.get("consulted_sources", []))
        if consulted_sources:
            lines.append(
                "Consulted sources: " + ", ".join(f"<code>{html.escape(str(item))}</code>" for item in consulted_sources)
            )
        if str(event.get("implementation_bundle_kind", "")).strip():
            lines.append(
                f"Implementation bundle: <code>{html.escape(str(event['implementation_bundle_kind']))}</code>"
            )
        if str(event.get("reason", "")).strip():
            lines.append(f"Reason: {html.escape(str(event['reason']))}")
        if str(event.get("path", "")).strip():
            lines.append(f"Path: {self._render_path_html(str(event['path']))}")
        if str(event.get("summary_artifact_path", "")).strip():
            lines.append(f"Summary: {self._render_path_html(str(event['summary_artifact_path']))}")
        if str(event.get("session_artifact_path", "")).strip():
            lines.append(f"Session artifact: {self._render_path_html(str(event['session_artifact_path']))}")
        created_files = list(event.get("created_files", []))
        if created_files:
            lines.append(f"Created files: {len(created_files)}")
        output_artifact_paths = list(event.get("output_artifact_paths", []))
        if output_artifact_paths:
            lines.append(f"Output artifacts: {len(output_artifact_paths)}")
        return lines

    def render_observability_page(self) -> str:
        snapshot = self._observability_snapshot()
        latest_cycle_links = "".join(
            [
                "<div class='section-links'>",
                "<a href='/workspace'>Browse workspace artifacts</a>",
                "<a href='/timeline'>Open runtime timeline</a>",
                "<a href='/cycle'>Open latest cycle summary</a>",
                "</div>",
            ]
        )
        stats = [
            ("Directive ID", snapshot.get("directive_id", "") or "<none yet>"),
            ("Workspace ID", snapshot.get("workspace_id", "") or "<none>"),
            ("Launch Type", snapshot.get("launch_type", "") or "<none>"),
            ("Execution Mode", snapshot.get("execution_mode", "") or "<none>"),
            ("Execution Profile", snapshot.get("execution_profile", "") or "<none>"),
            ("Backend", snapshot.get("backend_kind", "") or "<none>"),
            ("Controller Mode", snapshot.get("controller_mode", "") or "<none>"),
            ("Cycles Completed", snapshot.get("cycles_completed", 0) or 0),
            (
                "Staged Compact Follow-Ons",
                snapshot.get("staged_compact_follow_on_count", 0) or 0,
            ),
            (
                "Remaining Counted Cycle Budget",
                snapshot.get("remaining_counted_cycle_budget", 0) or 0,
            ),
            ("Cycle Kind", snapshot.get("cycle_kind", "") or "<none>"),
            ("Run Status", snapshot.get("run_status", "") or "<none>"),
            ("Stop Reason", snapshot.get("stop_reason", "") or "<none>"),
            (
                "Missing Deliverables",
                int(dict(snapshot.get("missing_deliverables_summary", {})).get("missing_required_deliverable_count", 0) or 0),
            ),
            (
                "Directive Complete",
                "yes" if bool(dict(snapshot.get("directive_completion_evaluation", {})).get("completed", False)) else "no",
            ),
            ("Current Objective Source", snapshot.get("current_objective_source_kind", "") or "<none>"),
            ("Current Objective", snapshot.get("current_objective_id", "") or "<none>"),
            ("Review Status", snapshot.get("review_status", "") or "<none>"),
            ("Promotion Recommendation", snapshot.get("promotion_recommendation_state", "") or "<none>"),
            ("Admission Recommendation", snapshot.get("baseline_admission_recommendation_state", "") or "<none>"),
            ("Admission Decision", snapshot.get("baseline_admission_decision_state", "") or "<none>"),
            ("Admitted Candidate", snapshot.get("admitted_candidate_state", "") or "<none>"),
            ("Candidate Handoff", snapshot.get("admitted_candidate_handoff_state", "") or "<none>"),
            (
                "Baseline Comparison",
                snapshot.get("baseline_comparison_result_state", "") or "<none>",
            ),
            (
                "Future Reference Target",
                snapshot.get("future_reference_target_state", "") or "<none>",
            ),
            (
                "Reference Target Consumption",
                snapshot.get("reference_target_consumption_state", "") or "<none>",
            ),
            (
                "Active Bounded Reference",
                snapshot.get("active_bounded_reference_target_id", "") or "<none>",
            ),
            ("Selected Skill Pack", snapshot.get("selected_skill_pack_id", "") or "<none>"),
            ("Skill-Pack Result", snapshot.get("skill_pack_result_state", "") or "<none>"),
            ("Quality Gap", snapshot.get("quality_gap_id", "") or "<none>"),
            (
                "Quality Improvement",
                snapshot.get("quality_improvement_state", "") or "<none>",
            ),
            (
                "Quality Composite",
                snapshot.get("quality_composite_state", "") or "<none>",
            ),
            (
                "Weakest Dimension",
                snapshot.get("quality_weakest_dimension_id", "") or "<none>",
            ),
            (
                "Next Pack",
                snapshot.get("quality_next_pack_id", "") or "<none>",
            ),
            (
                "Quality Reentry",
                snapshot.get("quality_chain_reentry_state", "") or "<none>",
            ),
            (
                "Quality Reentry Action",
                snapshot.get("quality_chain_reentry_action", "") or "<none>",
            ),
            (
                "Generation Index",
                snapshot.get("generation_index", 0) or 0,
            ),
            (
                "Generation Progress",
                snapshot.get("generation_progress_state", "") or "<none>",
            ),
            (
                "Progress Recommendation",
                snapshot.get("generation_progress_recommendation_state", "") or "<none>",
            ),
            (
                "Strategy Selection",
                snapshot.get("strategy_selection_state", "") or "<none>",
            ),
            (
                "Strategy Follow-On",
                snapshot.get("strategy_follow_on_family", "") or "<none>",
            ),
            (
                "Strategy Review Advice",
                "yes"
                if bool(snapshot.get("strategy_operator_review_recommended", False))
                else "no",
            ),
            ("Campaign ID", snapshot.get("campaign_id", "") or "<none>"),
            (
                "Campaign Waves",
                snapshot.get("campaign_wave_count", 0) or 0,
            ),
            (
                "Campaign Progress",
                snapshot.get("campaign_progress_state", "") or "<none>",
            ),
            (
                "Campaign Recommendation",
                snapshot.get("campaign_recommendation_state", "") or "<none>",
            ),
            (
                "Campaign Follow-On",
                snapshot.get("campaign_follow_on_family", "") or "<none>",
            ),
            (
                "Campaign Refresh Ready",
                "yes"
                if bool(snapshot.get("campaign_refresh_revised_candidate_ready", False))
                else "no",
            ),
            (
                "Protected Live Baseline",
                snapshot.get("protected_live_baseline_reference_id", "") or "<none>",
            ),
            ("Next Objective", snapshot.get("next_objective_id", "") or "<none>"),
            ("Reseed State", snapshot.get("reseed_state", "") or "<none>"),
            ("Continuation Authorized", "yes" if bool(snapshot.get("continuation_authorized", False)) else "no"),
            ("Effective Next Objective", snapshot.get("effective_next_objective_id", "") or "<none>"),
            ("Auto-Continue Enabled", "yes" if bool(snapshot.get("auto_continue_enabled", False)) else "no"),
            (
                "Auto-Continue Chain",
                f"{int(snapshot.get('auto_continue_chain_count', 0) or 0)}/{int(snapshot.get('auto_continue_chain_cap', 1) or 1)}",
            ),
            ("Auto-Continue Reason", snapshot.get("auto_continue_last_reason", "") or "<none>"),
            (
                "Auto-Continue Transition",
                snapshot.get("auto_continue_transition_state", "") or "<none>",
            ),
            ("Next Recommended Cycle", snapshot.get("next_recommended_cycle", "") or "<none>"),
            ("Active Workspace Root", snapshot.get("active_workspace_root", "") or "<none>"),
        ]
        stat_cards = "".join(
            f"<div class='stat-card'><span class='label'>{html.escape(label)}</span><span class='value'>{html.escape(str(value))}</span></div>"
            for label, value in stats
        )
        output_lines = [f"<code>{html.escape(str(path))}</code>" for path in list(snapshot.get("output_artifact_paths", []))]
        deferred_lines = [
            f"<code>{html.escape(str(item.get('item', '')))}</code>: {html.escape(str(item.get('reason', '')))}"
            for item in list(snapshot.get("deferred_items", []))
        ]
        missing_lines = [
            f"<code>{html.escape(str(item.get('deliverable_id', '')))}</code>: "
            + html.escape(", ".join(str(path) for path in list(item.get("missing_evidence_relative_paths", []))) or "missing")
            for item in list(dict(snapshot.get("missing_deliverables_summary", {})).get("missing_required_deliverables", []))
        ]
        skipped_lines = [
            f"<code>{html.escape(str(item.get('work_item_id', '')))}</code>: {html.escape(str(item.get('reason', '')))}"
            for item in list(snapshot.get("skipped_items", []))
        ]
        cycle_row_lines = [
            (
                f"Cycle {int(item.get('cycle_index', 0))}: "
                f"<code>{html.escape(str(item.get('cycle_kind', '')))}</code> -> "
                f"<code>{html.escape(str(item.get('summary_artifact_path', '')))}</code>"
            )
            for item in list(snapshot.get("cycle_rows", []))
        ]
        knowledge_pack_lines = [
            (
                f"<code>{html.escape(str(item.get('source_id', '')))}</code>: "
                f"{html.escape(str(item.get('load_status', '')))} "
                f"({html.escape(str(item.get('path_hint', '')) or '<none>')})"
            )
            for item in list(dict(snapshot.get("trusted_planning_evidence", {})).get("knowledge_packs", []))
        ]
        review_summary = dict(snapshot.get("review_summary", {}))
        promotion_recommendation = dict(snapshot.get("promotion_recommendation", {}))
        next_objective_proposal = dict(snapshot.get("next_objective_proposal", {}))
        reseed_request = dict(snapshot.get("reseed_request", {}))
        reseed_decision = dict(snapshot.get("reseed_decision", {}))
        continuation_lineage = dict(snapshot.get("continuation_lineage", {}))
        effective_next_objective = dict(snapshot.get("effective_next_objective", {}))
        baseline_admission_review = dict(snapshot.get("baseline_admission_review", {}))
        baseline_admission_recommendation = dict(
            snapshot.get("baseline_admission_recommendation", {})
        )
        baseline_admission_decision = dict(snapshot.get("baseline_admission_decision", {}))
        baseline_remediation_proposal = dict(
            snapshot.get("baseline_remediation_proposal", {})
        )
        weak_area_lines = [
            f"<code>{html.escape(str(item.get('check_id', '')))}</code>: {html.escape(str(item.get('details', '')))}"
            for item in list(review_summary.get("missing_or_weak_areas", []))
        ]
        strategy_rejected_lines = [
            f"<code>{html.escape(str(item.get('strategy_state', '')))}</code>: {html.escape(str(item.get('rejected_reason', '')))}"
            for item in list(
                dict(snapshot.get("successor_strategy_rationale", {})).get(
                    "rejected_alternative_strategies", []
                )
            )
        ]
        next_step = dict(snapshot.get("next_step_derivation", {}))
        selected_stage = dict(next_step.get("selected_stage", {}))
        review_required = bool(snapshot.get("operator_review_required", False))
        continuation_authorized = bool(snapshot.get("continuation_authorized", False))
        next_operator_move = (
            "Review the current proposal before NOVALI continues."
            if review_required and not continuation_authorized
            else (
                "Resume governed execution when you are ready for the next bounded cycle."
                if continuation_authorized
                else (
                    "Inspect the last bounded cycle and decide whether to hold, refresh, or launch another governed pass."
                    if str(snapshot.get("run_status", "")).strip()
                    else "Complete the first canonical launch to populate artifact-backed observability."
                )
            )
        )
        recent_outcome_detail = (
            snapshot.get("quality_improvement_state", "")
            or snapshot.get("promotion_recommendation_state", "")
            or snapshot.get("run_status", "")
            or "<none>"
        )
        hero_pills = "".join(
            [
                _render_state_pill("Run", snapshot.get("run_status", "") or "idle"),
                _render_state_pill("Mode", snapshot.get("execution_mode", "") or "uninitialized", tone="info"),
                _render_state_pill("Review", snapshot.get("review_status", "") or "none"),
                _render_state_pill("Loop", snapshot.get("loop_recommendation_state", "") or "not_started"),
            ]
        )
        hero_metrics = "".join(
            [
                _render_metric_card(
                    "Current Objective",
                    snapshot.get("current_objective_id", "") or snapshot.get("effective_next_objective_id", "") or "<none>",
                    detail=snapshot.get("current_objective_source_kind", "") or "No active bounded objective recorded.",
                ),
                _render_metric_card(
                    "What Just Happened",
                    snapshot.get("run_reason", "") or snapshot.get("skill_pack_result_state", "") or "<none>",
                    detail=f"Outcome state: {recent_outcome_detail}",
                    tone=_status_tone(recent_outcome_detail),
                ),
                _render_metric_card(
                    "Next Operator Move",
                    snapshot.get("next_recommended_cycle", "") or snapshot.get("campaign_follow_on_family", "") or "observe",
                    detail=next_operator_move,
                    tone="info",
                ),
                _render_metric_card(
                    "Stable Reference",
                    snapshot.get("active_bounded_reference_target_id", "") or "<none>",
                    detail="Protected live baseline remains separate and unchanged.",
                    tone="success",
                ),
            ]
        )
        hero_story = (
            "<section class='card hero-panel'>"
            "<div class='hero-layout'>"
            "<div class='hero-copy'>"
            "<span class='eyebrow'>Read-Only Operator Story</span>"
            "<h2>Observability built from the same persisted artifacts the packaged flow writes</h2>"
            "<p>This dashboard stays truthful to workspace state, frozen session state, controller artifacts, and runtime events. Nothing here invents hidden state or bypasses the canonical operator path.</p>"
            f"<div class='pill-row'>{hero_pills}</div>"
            f"<div class='signal-grid'>{hero_metrics}</div>"
            "</div>"
            "<div class='directive-core-shell'>"
            "<div class='operator-note info'>"
            "<strong>Operator shortcut</strong><br/>"
            "Use this page to orient quickly, then drop into workspace, timeline, or latest-cycle views for the deeper audit trail."
            f"{latest_cycle_links}"
            "</div>"
            "<div class='story-grid'>"
            f"<div class='story-card'><span class='label'>Launch posture</span><span class='value'>{html.escape(_display_text(snapshot.get('launch_type', '') or '<none>'))}</span><span class='detail'>{html.escape(_display_text(snapshot.get('execution_profile', '') or '<none>'))}</span></div>"
            f"<div class='story-card'><span class='label'>Quality lane</span><span class='value'>{html.escape(_display_text(snapshot.get('quality_composite_state', '') or '<none>'))}</span><span class='detail'>{html.escape(_display_text(snapshot.get('quality_weakest_dimension_id', '') or '<none>'))}</span></div>"
            f"<div class='story-card'><span class='label'>Campaign stack</span><span class='value'>{html.escape(_display_text(snapshot.get('campaign_recommendation_state', '') or '<none>'))}</span><span class='detail'>{html.escape(_display_text(snapshot.get('campaign_cycle_recommendation_state', '') or snapshot.get('loop_recommendation_state', '') or '<none>'))}</span></div>"
            "</div>"
            "</div>"
            "</div>"
            "</section>"
        )
        body = (
            f"{hero_story}"
            "<div class='grid'>"
            "<section class='card'>"
            "<h2>Latest Run Overview</h2>"
            "<p>This dashboard is read-only and built from the same persisted workspace, launch plan, session summary, and runtime event artifacts the packaged standalone flow already writes.</p>"
            f"<div class='stats-grid'>{stat_cards}</div>"
            f"<p><strong>Latest summary artifact:</strong> {self._render_path_html(str(snapshot.get('latest_summary_artifact_path', '')))}</p>"
            f"<p><strong>Implementation summary:</strong> {self._render_path_html(str(snapshot.get('implementation_summary_path', '')))}</p>"
            f"<p><strong>Artifact index:</strong> {self._render_path_html(str(snapshot.get('artifact_index_path', '')))}</p>"
            f"<p><strong>Controller artifact:</strong> {self._render_path_html(str(snapshot.get('controller_artifact_path', '')))}</p>"
            f"<p><strong>Trusted planning evidence:</strong> {self._render_path_html(str(snapshot.get('trusted_planning_evidence_path', '')))}</p>"
            f"<p><strong>Missing deliverables summary:</strong> {self._render_path_html(str(snapshot.get('missing_deliverables_path', '')))}</p>"
            f"<p><strong>Next-step derivation:</strong> {self._render_path_html(str(snapshot.get('next_step_derivation_path', '')))}</p>"
            f"<p><strong>Completion evaluation:</strong> {self._render_path_html(str(snapshot.get('completion_evaluation_path', '')))}</p>"
            f"<p><strong>Review summary:</strong> {self._render_path_html(str(snapshot.get('review_summary_path', '')))}</p>"
            f"<p><strong>Promotion recommendation:</strong> {self._render_path_html(str(snapshot.get('promotion_recommendation_path', '')))}</p>"
            f"<p><strong>Next-objective proposal:</strong> {self._render_path_html(str(snapshot.get('next_objective_proposal_path', '')))}</p>"
            f"<p><strong>Reseed request:</strong> {self._render_path_html(str(snapshot.get('reseed_request_path', '')))}</p>"
            f"<p><strong>Reseed decision:</strong> {self._render_path_html(str(snapshot.get('reseed_decision_path', '')))}</p>"
            f"<p><strong>Continuation lineage:</strong> {self._render_path_html(str(snapshot.get('continuation_lineage_path', '')))}</p>"
            f"<p><strong>Effective next objective:</strong> {self._render_path_html(str(snapshot.get('effective_next_objective_path', '')))}</p>"
            f"<p><strong>Baseline admission review:</strong> {self._render_path_html(str(snapshot.get('baseline_admission_review_path', '')))}</p>"
            f"<p><strong>Baseline admission recommendation:</strong> {self._render_path_html(str(snapshot.get('baseline_admission_recommendation_path', '')))}</p>"
            f"<p><strong>Baseline admission decision:</strong> {self._render_path_html(str(snapshot.get('baseline_admission_decision_path', '')))}</p>"
            f"<p><strong>Baseline remediation proposal:</strong> {self._render_path_html(str(snapshot.get('baseline_remediation_proposal_path', '')))}</p>"
            f"<p><strong>Admitted candidate:</strong> {self._render_path_html(str(snapshot.get('admitted_candidate_path', '')))}</p>"
            f"<p><strong>Candidate handoff:</strong> {self._render_path_html(str(snapshot.get('admitted_candidate_handoff_path', '')))}</p>"
            f"<p><strong>Baseline comparison:</strong> {self._render_path_html(str(snapshot.get('baseline_comparison_path', '')))}</p>"
            f"<p><strong>Reference target:</strong> {self._render_path_html(str(snapshot.get('reference_target_path', '')))}</p>"
            f"<p><strong>Reference target consumption:</strong> {self._render_path_html(str(snapshot.get('reference_target_consumption_path', '')))}</p>"
            f"<p><strong>Skill-pack invocation:</strong> {self._render_path_html(str(snapshot.get('skill_pack_invocation_path', '')))}</p>"
            f"<p><strong>Skill-pack result:</strong> {self._render_path_html(str(snapshot.get('skill_pack_result_path', '')))}</p>"
            f"<p><strong>Quality gap summary:</strong> {self._render_path_html(str(snapshot.get('quality_gap_summary_path', '')))}</p>"
            f"<p><strong>Quality improvement summary:</strong> {self._render_path_html(str(snapshot.get('quality_improvement_summary_path', '')))}</p>"
            f"<p><strong>Quality roadmap:</strong> {self._render_path_html(str(snapshot.get('quality_roadmap_path', '')))}</p>"
            f"<p><strong>Quality priority matrix:</strong> {self._render_path_html(str(snapshot.get('quality_priority_matrix_path', '')))}</p>"
            f"<p><strong>Quality composite evaluation:</strong> {self._render_path_html(str(snapshot.get('quality_composite_evaluation_path', '')))}</p>"
            f"<p><strong>Quality next-pack plan:</strong> {self._render_path_html(str(snapshot.get('quality_next_pack_plan_path', '')))}</p>"
            f"<p><strong>Generation history:</strong> {self._render_path_html(str(snapshot.get('generation_history_path', '')))}</p>"
            f"<p><strong>Generation delta:</strong> {self._render_path_html(str(snapshot.get('generation_delta_path', '')))}</p>"
            f"<p><strong>Progress governance:</strong> {self._render_path_html(str(snapshot.get('progress_governance_path', '')))}</p>"
            f"<p><strong>Progress recommendation:</strong> {self._render_path_html(str(snapshot.get('progress_recommendation_path', '')))}</p>"
            f"<p><strong>Runtime event log:</strong> {self._render_path_html(str(snapshot.get('runtime_event_log_path', '')))}</p>"
            f"<p><strong>Session artifact:</strong> {self._render_path_html(str(snapshot.get('session_artifact_path', '')))}</p>"
            "</section>"
            "<section class='card'>"
            "<h2>Cycle Model</h2>"
            f"<p><span class='badge'>{html.escape(str(snapshot.get('invocation_model', 'single_cycle_per_governed_execution_invocation')))}</span><span class='badge'>{html.escape(str(snapshot.get('controller_mode', 'single_cycle')))}</span> Single-cycle mode performs one bounded cycle and returns control. Multi-cycle mode may continue through several bounded cycles until directive completion, no admissible work, failure, or the operator-selected cap.</p>"
            f"<p><strong>Run reason:</strong> {html.escape(str(snapshot.get('run_reason', '') or '<none recorded>'))}</p>"
            f"<p><strong>Stop detail:</strong> {html.escape(str(snapshot.get('stop_detail', '') or '<none recorded>'))}</p>"
            "<h3>Latest output artifacts</h3>"
            f"{_html_list(output_lines)}"
            "<h3>Skipped work items</h3>"
            f"{_html_list(skipped_lines)}"
            "<h3>Deferred items</h3>"
            f"{_html_list(deferred_lines)}"
            "<h3>Per-cycle summaries</h3>"
            f"{_html_list(cycle_row_lines)}"
            "</section>"
            "<section class='card'>"
            "<h2>Trusted Planning Evidence</h2>"
            f"<p><strong>Selected stage:</strong> <code>{html.escape(str(selected_stage.get('stage_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Stage rationale:</strong> {html.escape(str(next_step.get('reason', '') or '<none recorded>'))}</p>"
            f"<p><strong>Directive completion note:</strong> {html.escape(str(dict(snapshot.get('directive_completion_evaluation', {})).get('reason', '') or '<none recorded>'))}</p>"
            "<h3>Knowledge packs consulted</h3>"
            f"{_html_list(knowledge_pack_lines)}"
            "<h3>Missing required deliverables</h3>"
            f"{_html_list(missing_lines)}"
            "</section>"
            "<section class='card'>"
            "<h2>Skill-Pack Quality Improvement</h2>"
            f"<p><strong>Selected skill pack:</strong> <code>{html.escape(str(snapshot.get('selected_skill_pack_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Skill-pack title:</strong> {html.escape(str(snapshot.get('selected_skill_pack_title', '') or '<none recorded>'))}</p>"
            f"<p><strong>Selected reason:</strong> {html.escape(str(snapshot.get('selected_skill_pack_reason', '') or '<none recorded>'))}</p>"
            f"<p><strong>Quality gap:</strong> <code>{html.escape(str(snapshot.get('quality_gap_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Quality gap title:</strong> {html.escape(str(snapshot.get('quality_gap_title', '') or '<none recorded>'))}</p>"
            f"<p><strong>Skill-pack result:</strong> <code>{html.escape(str(snapshot.get('skill_pack_result_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Quality improvement state:</strong> <code>{html.escape(str(snapshot.get('quality_improvement_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Reference target used:</strong> <code>{html.escape(str(dict(snapshot.get('successor_quality_improvement_summary', {})).get('active_bounded_reference_target_id', '') or snapshot.get('active_bounded_reference_target_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Improved relative to reference target:</strong> {html.escape('yes' if bool(dict(snapshot.get('successor_quality_improvement_summary', {})).get('improved_relative_to_reference_target', False)) else 'no')}</p>"
            f"<p><strong>Skill-pack invocation artifact:</strong> {self._render_path_html(str(snapshot.get('skill_pack_invocation_path', '')))}</p>"
            f"<p><strong>Skill-pack result artifact:</strong> {self._render_path_html(str(snapshot.get('skill_pack_result_path', '')))}</p>"
            f"<p><strong>Quality gap artifact:</strong> {self._render_path_html(str(snapshot.get('quality_gap_summary_path', '')))}</p>"
            f"<p><strong>Quality improvement artifact:</strong> {self._render_path_html(str(snapshot.get('quality_improvement_summary_path', '')))}</p>"
            "</section>"
            "<section class='card'>"
            "<h2>Successor Quality Roadmap</h2>"
            f"<p><strong>Composite quality state:</strong> <code>{html.escape(str(snapshot.get('quality_composite_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Materially stronger than reference target in aggregate:</strong> {html.escape('yes' if bool(snapshot.get('materially_stronger_than_reference_target_in_aggregate', False)) else 'no')}</p>"
            f"<p><strong>Weakest dimension:</strong> <code>{html.escape(str(snapshot.get('quality_weakest_dimension_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Weakest dimension title:</strong> {html.escape(str(snapshot.get('quality_weakest_dimension_title', '') or '<none recorded>'))}</p>"
            f"<p><strong>Next recommended skill pack:</strong> <code>{html.escape(str(snapshot.get('quality_next_pack_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Next recommended objective:</strong> <code>{html.escape(str(snapshot.get('quality_next_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Next dimension:</strong> <code>{html.escape(str(snapshot.get('quality_next_dimension_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Roadmap artifact:</strong> {self._render_path_html(str(snapshot.get('quality_roadmap_path', '')))}</p>"
            f"<p><strong>Priority matrix:</strong> {self._render_path_html(str(snapshot.get('quality_priority_matrix_path', '')))}</p>"
            f"<p><strong>Composite evaluation:</strong> {self._render_path_html(str(snapshot.get('quality_composite_evaluation_path', '')))}</p>"
            f"<p><strong>Next-pack plan:</strong> {self._render_path_html(str(snapshot.get('quality_next_pack_plan_path', '')))}</p>"
            "</section>"
            "<section class='card'>"
            "<h2>Quality-Chain Reentry</h2>"
            f"<p><strong>Reentry state:</strong> <code>{html.escape(str(snapshot.get('quality_chain_reentry_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Recommended action:</strong> <code>{html.escape(str(snapshot.get('quality_chain_reentry_action', '') or '<none>'))}</code></p>"
            f"<p><strong>Reentry rationale:</strong> {html.escape(str(snapshot.get('quality_chain_reentry_reason', '') or '<none recorded>'))}</p>"
            f"<p><strong>Next quality objective:</strong> <code>{html.escape(str(snapshot.get('quality_chain_next_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Next quality objective class:</strong> <code>{html.escape(str(snapshot.get('quality_chain_next_objective_class', '') or '<none>'))}</code></p>"
            f"<p><strong>Compact follow-on:</strong> {html.escape('yes' if bool(snapshot.get('quality_chain_next_objective_compact', False)) else 'no')}</p>"
            f"<p><strong>Reentry artifact:</strong> {self._render_path_html(str(snapshot.get('quality_chain_reentry_path', '')))}</p>"
            "</section>"
            "<section class='card'>"
            "<h2>Review And Promotion</h2>"
            f"<p><strong>Review status:</strong> <code>{html.escape(str(snapshot.get('review_status', '') or '<none>'))}</code></p>"
            f"<p><strong>Promotion recommendation:</strong> <code>{html.escape(str(snapshot.get('promotion_recommendation_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Recommendation rationale:</strong> {html.escape(str(promotion_recommendation.get('rationale', '') or '<none recorded>'))}</p>"
            f"<p><strong>Next bounded objective:</strong> <code>{html.escape(str(snapshot.get('next_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Next-objective rationale:</strong> {html.escape(str(next_objective_proposal.get('rationale', '') or '<none recorded>'))}</p>"
            f"<p><strong>Operator review required:</strong> {html.escape('yes' if bool(snapshot.get('operator_review_required', False)) else 'no')}</p>"
            f"<p><strong>Reseed state:</strong> <code>{html.escape(str(snapshot.get('reseed_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Latest decision:</strong> <code>{html.escape(str(reseed_decision.get('operator_decision', '') or '<none>'))}</code></p>"
            f"<p><strong>Continuation authorized:</strong> {html.escape('yes' if bool(snapshot.get('continuation_authorized', False)) else 'no')}</p>"
            f"<p><strong>Effective next objective:</strong> <code>{html.escape(str(snapshot.get('effective_next_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Effective objective origin:</strong> <code>{html.escape(str(snapshot.get('effective_next_objective_authorization_origin', '') or '<none>'))}</code></p>"
            f"<p><strong>Auto-continue transition:</strong> <code>{html.escape(str(snapshot.get('auto_continue_transition_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Same-session cycle started:</strong> {html.escape('yes' if bool(snapshot.get('auto_continue_transition_executed_in_session', False)) else 'no')}</p>"
            f"<p><strong>Transition lineage:</strong> <code>{html.escape(str(snapshot.get('auto_continue_transition_from_objective_id', '') or '<none>'))}</code> -> <code>{html.escape(str(snapshot.get('auto_continue_transition_to_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Request rationale:</strong> {html.escape(str(reseed_request.get('rationale', '') or '<none recorded>'))}</p>"
            f"<p><strong>Decision note:</strong> {html.escape(str(reseed_decision.get('operator_note', '') or '<none recorded>'))}</p>"
            f"<p><strong>Lineage completed objective:</strong> <code>{html.escape(str(continuation_lineage.get('completed_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Effective-objective rationale:</strong> {html.escape(str(effective_next_objective.get('rationale', '') or '<none recorded>'))}</p>"
            "<h3>Missing Or Weak Areas</h3>"
            f"{_html_list(weak_area_lines)}"
            "</section>"
            "<section class='card'>"
            "<h2>Baseline Admission</h2>"
            f"<p><strong>Admission review:</strong> <code>{html.escape(str(snapshot.get('baseline_admission_review_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Admission recommendation:</strong> <code>{html.escape(str(snapshot.get('baseline_admission_recommendation_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Admission decision:</strong> <code>{html.escape(str(snapshot.get('baseline_admission_decision_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Admitted bounded baseline candidate:</strong> {html.escape('yes' if bool(snapshot.get('baseline_candidate_admitted', False)) else 'no')}</p>"
            f"<p><strong>Remediation objective:</strong> <code>{html.escape(str(snapshot.get('baseline_remediation_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Admission review artifact:</strong> {self._render_path_html(str(snapshot.get('baseline_admission_review_path', '')))}</p>"
            f"<p><strong>Admission recommendation artifact:</strong> {self._render_path_html(str(snapshot.get('baseline_admission_recommendation_path', '')))}</p>"
            f"<p><strong>Admission decision artifact:</strong> {self._render_path_html(str(snapshot.get('baseline_admission_decision_path', '')))}</p>"
            f"<p><strong>Baseline remediation artifact:</strong> {self._render_path_html(str(snapshot.get('baseline_remediation_proposal_path', '')))}</p>"
            "</section>"
            "<section class='card'>"
            "<h2>Admitted Candidate Lifecycle</h2>"
            f"<p><strong>Admitted candidate state:</strong> <code>{html.escape(str(snapshot.get('admitted_candidate_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Candidate handoff state:</strong> <code>{html.escape(str(snapshot.get('admitted_candidate_handoff_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Handoff ready:</strong> {html.escape('yes' if bool(snapshot.get('admitted_candidate_handoff_ready', False)) else 'no')}</p>"
            f"<p><strong>Baseline comparison result:</strong> <code>{html.escape(str(snapshot.get('baseline_comparison_result_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Stronger than current bounded baseline:</strong> {html.escape('yes' if bool(snapshot.get('stronger_than_current_bounded_baseline', False)) else 'no')}</p>"
            f"<p><strong>Future reference target:</strong> <code>{html.escape(str(snapshot.get('future_reference_target_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Future reference eligible:</strong> {html.escape('yes' if bool(snapshot.get('future_reference_target_eligible', False)) else 'no')}</p>"
            f"<p><strong>Preferred reference target:</strong> <code>{html.escape(str(snapshot.get('future_reference_target_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Revised candidate state:</strong> <code>{html.escape(str(snapshot.get('revised_candidate_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Revised candidate id:</strong> <code>{html.escape(str(snapshot.get('revised_candidate_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Prior admitted candidate:</strong> <code>{html.escape(str(snapshot.get('revised_candidate_prior_admitted_candidate_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Revised candidate materially stronger in aggregate:</strong> {html.escape('yes' if bool(snapshot.get('revised_candidate_materially_stronger_in_aggregate', False)) else 'no')}</p>"
            f"<p><strong>Reference target rollover:</strong> <code>{html.escape(str(snapshot.get('revised_candidate_reference_rollover_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Reference target consumption:</strong> <code>{html.escape(str(snapshot.get('reference_target_consumption_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Active bounded reference target:</strong> <code>{html.escape(str(snapshot.get('active_bounded_reference_target_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Protected live baseline:</strong> <code>{html.escape(str(snapshot.get('protected_live_baseline_reference_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Comparison basis:</strong> <code>{html.escape(str(snapshot.get('reference_target_comparison_basis', '') or '<none>'))}</code></p>"
            f"<p><strong>Fallback reason:</strong> {html.escape(str(snapshot.get('reference_target_fallback_reason', '') or '<none recorded>'))}</p>"
            f"<p><strong>Comparison remediation objective:</strong> <code>{html.escape(str(snapshot.get('comparison_remediation_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Comparison rationale:</strong> {html.escape(str(dict(snapshot.get('baseline_comparison', {})).get('comparison_rationale', '') or '<none recorded>'))}</p>"
            f"<p><strong>Admitted candidate artifact:</strong> {self._render_path_html(str(snapshot.get('admitted_candidate_path', '')))}</p>"
            f"<p><strong>Candidate handoff artifact:</strong> {self._render_path_html(str(snapshot.get('admitted_candidate_handoff_path', '')))}</p>"
            f"<p><strong>Baseline comparison artifact:</strong> {self._render_path_html(str(snapshot.get('baseline_comparison_path', '')))}</p>"
            f"<p><strong>Revised candidate bundle artifact:</strong> {self._render_path_html(str(snapshot.get('revised_candidate_bundle_path', '')))}</p>"
            f"<p><strong>Revised candidate handoff artifact:</strong> {self._render_path_html(str(snapshot.get('revised_candidate_handoff_path', '')))}</p>"
            f"<p><strong>Revised candidate comparison artifact:</strong> {self._render_path_html(str(snapshot.get('revised_candidate_comparison_path', '')))}</p>"
            f"<p><strong>Revised candidate promotion summary artifact:</strong> {self._render_path_html(str(snapshot.get('revised_candidate_promotion_summary_path', '')))}</p>"
            f"<p><strong>Reference target artifact:</strong> {self._render_path_html(str(snapshot.get('reference_target_path', '')))}</p>"
            f"<p><strong>Reference target consumption artifact:</strong> {self._render_path_html(str(snapshot.get('reference_target_consumption_path', '')))}</p>"
            "</section>"
            "<section class='card'>"
            "<h2>Generation Progress Governance</h2>"
            f"<p><strong>Generation index:</strong> <code>{html.escape(str(snapshot.get('generation_index', 0) or 0))}</code></p>"
            f"<p><strong>Prior generation index:</strong> <code>{html.escape(str(snapshot.get('prior_generation_index', 0) or 0))}</code></p>"
            f"<p><strong>Current admitted candidate:</strong> <code>{html.escape(str(snapshot.get('generation_current_candidate_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Prior admitted candidate:</strong> <code>{html.escape(str(snapshot.get('generation_prior_candidate_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Progress state:</strong> <code>{html.escape(str(snapshot.get('generation_progress_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Progress recommendation:</strong> <code>{html.escape(str(snapshot.get('generation_progress_recommendation_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Additional bounded improvement justified:</strong> {html.escape('yes' if bool(snapshot.get('generation_additional_improvement_justified', False)) else 'no')}</p>"
            f"<p><strong>Recommended remediation objective:</strong> <code>{html.escape(str(snapshot.get('generation_remediation_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Generation history artifact:</strong> {self._render_path_html(str(snapshot.get('generation_history_path', '')))}</p>"
            f"<p><strong>Generation delta artifact:</strong> {self._render_path_html(str(snapshot.get('generation_delta_path', '')))}</p>"
            f"<p><strong>Progress governance artifact:</strong> {self._render_path_html(str(snapshot.get('progress_governance_path', '')))}</p>"
            f"<p><strong>Progress recommendation artifact:</strong> {self._render_path_html(str(snapshot.get('progress_recommendation_path', '')))}</p>"
            "</section>"
            "<section class='card'>"
            "<h2>Bounded Strategy Selection</h2>"
            f"<p><strong>Selected strategy:</strong> <code>{html.escape(str(snapshot.get('strategy_selection_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Follow-on family:</strong> <code>{html.escape(str(snapshot.get('strategy_follow_on_family', '') or '<none>'))}</code></p>"
            f"<p><strong>Operator review recommended before execution:</strong> {html.escape('yes' if bool(snapshot.get('strategy_operator_review_recommended', False)) else 'no')}</p>"
            f"<p><strong>Recommended follow-on objective:</strong> <code>{html.escape(str(snapshot.get('strategy_selected_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Recommended follow-on skill pack:</strong> <code>{html.escape(str(snapshot.get('strategy_selected_skill_pack_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Recommended dimension:</strong> <code>{html.escape(str(snapshot.get('strategy_selected_dimension_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Strategy rationale:</strong> {html.escape(str(snapshot.get('strategy_rationale_summary', '') or '<none recorded>'))}</p>"
            "<h3>Rejected alternatives</h3>"
            f"{_html_list(strategy_rejected_lines)}"
            f"<p><strong>Strategy selection artifact:</strong> {self._render_path_html(str(snapshot.get('strategy_selection_path', '')))}</p>"
            f"<p><strong>Strategy rationale artifact:</strong> {self._render_path_html(str(snapshot.get('strategy_rationale_path', '')))}</p>"
            f"<p><strong>Strategy follow-on plan artifact:</strong> {self._render_path_html(str(snapshot.get('strategy_follow_on_plan_path', '')))}</p>"
            f"<p><strong>Strategy decision-support artifact:</strong> {self._render_path_html(str(snapshot.get('strategy_decision_support_path', '')))}</p>"
            "</section>"
            "<section class='card'>"
            "<h2>Campaign Governance</h2>"
            f"<p><strong>Campaign id:</strong> <code>{html.escape(str(snapshot.get('campaign_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign wave count:</strong> <code>{html.escape(str(snapshot.get('campaign_wave_count', 0) or 0))}</code></p>"
            f"<p><strong>Campaign progress state:</strong> <code>{html.escape(str(snapshot.get('campaign_progress_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign state:</strong> <code>{html.escape(str(snapshot.get('campaign_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign recommendation:</strong> <code>{html.escape(str(snapshot.get('campaign_recommendation_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign follow-on family:</strong> <code>{html.escape(str(snapshot.get('campaign_follow_on_family', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign refresh ready:</strong> {html.escape('yes' if bool(snapshot.get('campaign_refresh_revised_candidate_ready', False)) else 'no')}</p>"
            f"<p><strong>Last wave strategy:</strong> <code>{html.escape(str(snapshot.get('campaign_last_wave_strategy_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Last wave skill pack:</strong> <code>{html.escape(str(snapshot.get('campaign_last_wave_skill_pack_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Accumulated improved dimensions:</strong> {html.escape(', '.join(list(snapshot.get('campaign_accumulated_improved_dimension_ids', []))) or '<none>')}</p>"
            f"<p><strong>Remaining weak dimensions:</strong> {html.escape(', '.join(list(snapshot.get('campaign_remaining_weak_dimension_ids', []))) or '<none>')}</p>"
            f"<p><strong>Campaign history artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_history_path', '')))}</p>"
            f"<p><strong>Campaign delta artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_delta_path', '')))}</p>"
            f"<p><strong>Campaign governance artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_governance_path', '')))}</p>"
            f"<p><strong>Campaign recommendation artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_recommendation_path', '')))}</p>"
            f"<p><strong>Campaign wave plan artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_wave_plan_path', '')))}</p>"
            "</section>"
            "<section class='card'>"
            "<h2>Campaign-Cycle Governance</h2>"
            f"<p><strong>Campaign-cycle id:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign-cycle index:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_index', 0) or 0))}</code></p>"
            f"<p><strong>Prior campaign-cycle index:</strong> <code>{html.escape(str(snapshot.get('prior_campaign_cycle_index', 0) or 0))}</code></p>"
            f"<p><strong>Campaign-cycle progress state:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_progress_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign-cycle state:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign-cycle recommendation:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_recommendation_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign-cycle follow-on family:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_follow_on_family', '') or '<none>'))}</code></p>"
            f"<p><strong>Current rolled reference target:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_current_reference_target_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Prior rolled reference target:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_prior_reference_target_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Source campaign id:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_source_campaign_id', '') or '<none>'))}</code></p>"
            f"<p><strong>New dimensions vs prior cycle:</strong> {html.escape(', '.join(list(snapshot.get('campaign_cycle_new_dimension_ids', []))) or '<none>')}</p>"
            f"<p><strong>Remaining weak dimensions:</strong> {html.escape(', '.join(list(snapshot.get('campaign_cycle_remaining_weak_dimension_ids', []))) or '<none>')}</p>"
            f"<p><strong>Campaign-cycle history artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_cycle_history_path', '')))}</p>"
            f"<p><strong>Campaign-cycle delta artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_cycle_delta_path', '')))}</p>"
            f"<p><strong>Campaign-cycle governance artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_cycle_governance_path', '')))}</p>"
            f"<p><strong>Campaign-cycle recommendation artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_cycle_recommendation_path', '')))}</p>"
            f"<p><strong>Campaign-cycle follow-on plan artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_cycle_follow_on_plan_path', '')))}</p>"
            "</section>"
            "<section class='card'>"
            "<h2>Loop Governance</h2>"
            f"<p><strong>Loop id:</strong> <code>{html.escape(str(snapshot.get('loop_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Loop index:</strong> <code>{html.escape(str(snapshot.get('loop_index', 0) or 0))}</code></p>"
            f"<p><strong>Prior loop index:</strong> <code>{html.escape(str(snapshot.get('prior_loop_index', 0) or 0))}</code></p>"
            f"<p><strong>Loop progress state:</strong> <code>{html.escape(str(snapshot.get('loop_progress_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Loop state:</strong> <code>{html.escape(str(snapshot.get('loop_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Loop recommendation:</strong> <code>{html.escape(str(snapshot.get('loop_recommendation_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Loop follow-on family:</strong> <code>{html.escape(str(snapshot.get('loop_follow_on_family', '') or '<none>'))}</code></p>"
            f"<p><strong>Current loop target:</strong> <code>{html.escape(str(snapshot.get('loop_current_reference_target_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Prior loop target:</strong> <code>{html.escape(str(snapshot.get('loop_prior_reference_target_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Source campaign-cycle id:</strong> <code>{html.escape(str(snapshot.get('loop_source_campaign_cycle_id', '') or '<none>'))}</code></p>"
            f"<p><strong>New dimensions vs prior loop:</strong> {html.escape(', '.join(list(snapshot.get('loop_new_dimension_ids', []))) or '<none>')}</p>"
            f"<p><strong>Remaining weak dimensions:</strong> {html.escape(', '.join(list(snapshot.get('loop_remaining_weak_dimension_ids', []))) or '<none>')}</p>"
            f"<p><strong>Loop history artifact:</strong> {self._render_path_html(str(snapshot.get('loop_history_path', '')))}</p>"
            f"<p><strong>Loop delta artifact:</strong> {self._render_path_html(str(snapshot.get('loop_delta_path', '')))}</p>"
            f"<p><strong>Loop governance artifact:</strong> {self._render_path_html(str(snapshot.get('loop_governance_path', '')))}</p>"
            f"<p><strong>Loop recommendation artifact:</strong> {self._render_path_html(str(snapshot.get('loop_recommendation_path', '')))}</p>"
            f"<p><strong>Loop follow-on plan artifact:</strong> {self._render_path_html(str(snapshot.get('loop_follow_on_plan_path', '')))}</p>"
            "</section>"
            "<section class='card'>"
            "<h2>Auto-Continue Policy</h2>"
            f"<p><strong>Enabled:</strong> {html.escape('yes' if bool(snapshot.get('auto_continue_enabled', False)) else 'no')}</p>"
            f"<p><strong>Allowed objective classes:</strong> {html.escape(', '.join(list(snapshot.get('auto_continue_allowed_objective_classes', []))) or '<none>')}</p>"
            f"<p><strong>Chain count / cap:</strong> <code>{html.escape(str(int(snapshot.get('auto_continue_chain_count', 0) or 0)))}/{html.escape(str(int(snapshot.get('auto_continue_chain_cap', 1) or 1)))}</code></p>"
            f"<p><strong>Last reason:</strong> <code>{html.escape(str(snapshot.get('auto_continue_last_reason', '') or '<none>'))}</code></p>"
            f"<p><strong>Last origin:</strong> <code>{html.escape(str(snapshot.get('auto_continue_last_origin', '') or '<none>'))}</code></p>"
            f"<p><strong>Budget staging decision:</strong> <code>{html.escape(str(snapshot.get('budget_staging_decision', '') or '<none>'))}</code></p>"
            f"<p><strong>Budget staging rationale:</strong> {html.escape(str(snapshot.get('budget_staging_rationale', '') or '<none recorded>'))}</p>"
            f"<p><strong>Budget staging objective:</strong> <code>{html.escape(str(snapshot.get('budget_staging_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Budget staging objective class:</strong> <code>{html.escape(str(snapshot.get('budget_staging_objective_class', '') or '<none>'))}</code></p>"
            f"<p><strong>Remaining counted cycle budget:</strong> <code>{html.escape(str(int(snapshot.get('remaining_counted_cycle_budget', 0) or 0)))}</code></p>"
            f"<p><strong>Total executed objective rows:</strong> <code>{html.escape(str(int(snapshot.get('total_executed_objective_rows', 0) or 0)))}</code></p>"
            f"<p><strong>Transition state:</strong> <code>{html.escape(str(snapshot.get('auto_continue_transition_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Same-session cycle started:</strong> {html.escape('yes' if bool(snapshot.get('auto_continue_transition_executed_in_session', False)) else 'no')}</p>"
            f"<p><strong>Transition lineage:</strong> <code>{html.escape(str(snapshot.get('auto_continue_transition_from_objective_id', '') or '<none>'))}</code> -> <code>{html.escape(str(snapshot.get('auto_continue_transition_to_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Transition next cycle index:</strong> <code>{html.escape(str(int(snapshot.get('auto_continue_transition_cycle_index', 0) or 0) or '<none>'))}</code></p>"
            f"<p><strong>Manual approval for first entry:</strong> {html.escape('yes' if bool(snapshot.get('auto_continue_require_manual_approval_for_first_entry', True)) else 'no')}</p>"
            f"<p><strong>Review-supported proposals required:</strong> {html.escape('yes' if bool(snapshot.get('auto_continue_require_review_supported_proposals', True)) else 'no')}</p>"
            f"<p><strong>Policy artifact:</strong> {self._render_path_html(str(snapshot.get('auto_continue_policy_path', '')))}</p>"
            f"<p><strong>State artifact:</strong> {self._render_path_html(str(snapshot.get('auto_continue_state_path', '')))}</p>"
            f"<p><strong>Decision artifact:</strong> {self._render_path_html(str(snapshot.get('auto_continue_decision_path', '')))}</p>"
            f"<p><strong>Transition artifact:</strong> {self._render_path_html(str(snapshot.get('auto_continue_transition_path', '')))}</p>"
            "</section>"
            "</div>"
        )
        return _render_page(
            title="NOVALI Observability Dashboard",
            subtitle="Read-only console for latest run state, workspace outputs, and runtime evidence.",
            body=body,
            current_path="/observability",
        )

    def render_workspace_page(self) -> str:
        snapshot = self._observability_snapshot()
        groups = self._workspace_artifact_groups(snapshot)
        sections: list[str] = []
        for category in WORKSPACE_ARTIFACT_CATEGORIES:
            rows = groups.get(category, [])
            if rows:
                table_rows = "".join(
                    "<tr>"
                    f"<td><code>{html.escape(str(row['relative_path']))}</code>{' <span class=\"badge\">key</span>' if row.get('is_key_artifact') else ''}</td>"
                    f"<td>{html.escape(str(row['modified_at']))}</td>"
                    f"<td>{html.escape(str(row['size_display']))}</td>"
                    f"<td>{('<a href=\"' + html.escape(str(row['preview_href'])) + '\">Preview</a>') if row.get('preview_href') else '<span class=\"muted\">Preview unavailable</span>'}</td>"
                    "</tr>"
                    for row in rows
                )
                content = (
                    "<table><thead><tr><th>Path</th><th>Modified</th><th>Size</th><th>Preview</th></tr></thead>"
                    f"<tbody>{table_rows}</tbody></table>"
                )
            else:
                content = "<p class='muted'>No files recorded in this category yet.</p>"
            sections.append(f"<section class='card'><h2>{html.escape(category.title())}</h2>{content}</section>")
        body = (
            "<div class='grid'>"
            "<section class='card'>"
            "<h2>Workspace Artifact Overview</h2>"
            f"<p><strong>Workspace root:</strong> {self._render_path_html(str(snapshot.get('workspace_root', '')))}</p>"
            "<p>Use this page to spot-check the host-visible workspace without manually hunting through package folders. Key planning, implementation, and summary artifacts are grouped by category and previewable when they are text-based.</p>"
            "</section>"
            + "".join(sections)
            + "</div>"
        )
        return _render_page(
            title="NOVALI Workspace Artifacts",
            subtitle="Read-only listing of the active workspace grouped by plans, docs, source, tests, and artifacts.",
            body=body,
            current_path="/workspace",
        )

    def render_timeline_page(self) -> str:
        snapshot = self._observability_snapshot()
        runtime_events = list(snapshot.get("runtime_events", []))
        items = []
        for event in runtime_events[-80:]:
            event_type = str(event.get("event_type", "")).strip()
            event_title = EVENT_LABELS.get(event_type, event_type or "runtime event")
            detail_lines = self._event_detail_lines(event)
            items.append(
                "<li>"
                f"<div class='timestamp'>{html.escape(_format_timestamp(event.get('timestamp', '')))}</div>"
                f"<div class='event-title'>{html.escape(event_title)}</div>"
                f"<div class='muted'>Session: <code>{html.escape(str(event.get('session_id', '')))}</code></div>"
                + (f"<ul class='event-meta'>{''.join(f'<li>{line}</li>' for line in detail_lines)}</ul>" if detail_lines else "")
                + "</li>"
            )
        timeline_html = "<ul class='timeline'>" + "".join(items) + "</ul>" if items else "<p class='muted'>No runtime events recorded yet.</p>"
        body = (
            "<div class='grid'>"
            "<section class='card'>"
            "<h2>Runtime Event Timeline</h2>"
            f"<p><strong>Runtime event log:</strong> {self._render_path_html(str(snapshot.get('runtime_event_log_path', '')))}</p>"
            "<p>This timeline is rendered from the persisted JSONL runtime event ledgers for the current workspace lineage. It shows observable actions and artifact paths only, not hidden reasoning.</p>"
            "</section>"
            f"<section class='card'>{timeline_html}</section>"
            "</div>"
        )
        return _render_page(
            title="NOVALI Runtime Timeline",
            subtitle="Operator-readable timeline of structured runtime events from the current workspace and session.",
            body=body,
            current_path="/timeline",
        )

    def render_cycle_summary_page(self) -> str:
        snapshot = self._observability_snapshot()
        work_summary = dict(snapshot.get("work_summary", {}))
        implementation_summary = dict(snapshot.get("implementation_summary", {}))
        artifact_index = dict(snapshot.get("artifact_index", {}))
        trusted_planning_evidence = dict(snapshot.get("trusted_planning_evidence", {}))
        next_step_derivation = dict(snapshot.get("next_step_derivation", {}))
        completion_evaluation = dict(snapshot.get("directive_completion_evaluation", {})) or dict(
            snapshot.get("completion_evaluation", {})
        )
        review_summary = dict(snapshot.get("review_summary", {}))
        promotion_recommendation = dict(snapshot.get("promotion_recommendation", {}))
        next_objective_proposal = dict(snapshot.get("next_objective_proposal", {}))
        reseed_request = dict(snapshot.get("reseed_request", {}))
        reseed_decision = dict(snapshot.get("reseed_decision", {}))
        continuation_lineage = dict(snapshot.get("continuation_lineage", {}))
        effective_next_objective = dict(snapshot.get("effective_next_objective", {}))
        baseline_admission_review = dict(snapshot.get("baseline_admission_review", {}))
        baseline_admission_recommendation = dict(
            snapshot.get("baseline_admission_recommendation", {})
        )
        baseline_admission_decision = dict(snapshot.get("baseline_admission_decision", {}))
        baseline_remediation_proposal = dict(
            snapshot.get("baseline_remediation_proposal", {})
        )
        output_lines = [f"<code>{html.escape(str(path))}</code>" for path in list(snapshot.get("output_artifact_paths", []))]
        created_lines = [f"<code>{html.escape(str(path))}</code>" for path in list(snapshot.get("newly_created_paths", []))]
        skipped_lines = [
            f"<code>{html.escape(str(item.get('work_item_id', '')))}</code>: {html.escape(str(item.get('reason', '')))}"
            for item in list(snapshot.get("skipped_items", []))
        ]
        deferred_lines = [
            f"<code>{html.escape(str(item.get('item', '')))}</code>: {html.escape(str(item.get('reason', '')))}"
            for item in list(snapshot.get("deferred_items", []))
        ]
        missing_lines = [
            f"<code>{html.escape(str(item.get('deliverable_id', '')))}</code>: "
            + html.escape(", ".join(str(path) for path in list(item.get("missing_evidence_relative_paths", []))) or "missing")
            for item in list(dict(snapshot.get("missing_deliverables_summary", {})).get("missing_required_deliverables", []))
        ]
        knowledge_pack_lines = [
            (
                f"<code>{html.escape(str(item.get('source_id', '')))}</code>: "
                f"{html.escape(str(item.get('load_status', '')))}"
            )
            for item in list(trusted_planning_evidence.get("knowledge_packs", []))
        ]
        strategy_rejected_lines = [
            f"<code>{html.escape(str(item.get('strategy_state', '')))}</code>: {html.escape(str(item.get('rejected_reason', '')))}"
            for item in list(
                dict(snapshot.get("successor_strategy_rationale", {})).get(
                    "rejected_alternative_strategies", []
                )
            )
        ]
        cycle_status_payload = (
            review_summary
            or work_summary
            or implementation_summary
            or artifact_index
            or {
                "status": str(snapshot.get("cycle_materialization_status", "") or "no_cycle_summary_available"),
                "directive_id": str(snapshot.get("directive_id", "")).strip(),
                "workspace_id": str(snapshot.get("workspace_id", "")).strip(),
                "workspace_root": str(snapshot.get("workspace_root", "")).strip(),
                "last_launch_kind": str(snapshot.get("last_launch_kind", "")).strip(),
                "failure_stage": str(snapshot.get("cycle_failure_stage", "")).strip(),
                "failure_reason": str(snapshot.get("cycle_failure_reason", "")).strip()
                or str(snapshot.get("last_launch_failure_reason", "")).strip(),
                "launch_plan_path": str(snapshot.get("launch_plan_path", "")).strip(),
                "runtime_event_log_path": str(snapshot.get("runtime_event_log_path", "")).strip(),
            }
        )
        cycle_materialization_note = ""
        if str(snapshot.get("cycle_materialization_status", "")).strip() != "cycle_summary_available":
            cycle_materialization_note = (
                "<p><strong>Cycle materialization state:</strong> "
                f"<code>{html.escape(str(snapshot.get('cycle_materialization_status', '') or '<none>'))}</code></p>"
                f"<p><strong>Failure stage:</strong> <code>{html.escape(str(snapshot.get('cycle_failure_stage', '') or '<none>'))}</code></p>"
                f"<p><strong>Failure reason:</strong> {html.escape(str(snapshot.get('cycle_failure_reason', '') or snapshot.get('last_launch_failure_reason', '') or '<none recorded>'))}</p>"
                f"<p><strong>Latest launch kind:</strong> <code>{html.escape(str(snapshot.get('last_launch_kind', '') or '<none>'))}</code></p>"
                f"<p><strong>Launch plan:</strong> {self._render_path_html(str(snapshot.get('launch_plan_path', '')))}</p>"
                f"<p><strong>Runtime event log:</strong> {self._render_path_html(str(snapshot.get('runtime_event_log_path', '')))}</p>"
            )
        body = (
            "<div class='grid'>"
            "<section class='card'>"
            "<h2>Latest Cycle Summary</h2>"
            f"<p><span class='badge'>{html.escape(str(snapshot.get('cycle_kind', '') or '<none>'))}</span><span class='badge'>{html.escape(str(snapshot.get('run_status', '') or '<none>'))}</span><span class='badge'>{html.escape(str(snapshot.get('next_recommended_cycle', '') or '<none>'))}</span><span class='badge'>{html.escape(str(snapshot.get('stop_reason', '') or '<none>'))}</span></p>"
            f"<p><strong>Summary artifact:</strong> {self._render_path_html(str(snapshot.get('latest_summary_artifact_path', '')))}</p>"
            f"<p><strong>Controller artifact:</strong> {self._render_path_html(str(snapshot.get('controller_artifact_path', '')))}</p>"
            f"<p><strong>Implementation bundle summary:</strong> {self._render_path_html(str(snapshot.get('implementation_summary_path', '')))}</p>"
            f"<p><strong>Workspace artifact index:</strong> {self._render_path_html(str(snapshot.get('artifact_index_path', '')))}</p>"
            f"<p><strong>Trusted planning evidence:</strong> {self._render_path_html(str(snapshot.get('trusted_planning_evidence_path', '')))}</p>"
            f"<p><strong>Missing deliverables summary:</strong> {self._render_path_html(str(snapshot.get('missing_deliverables_path', '')))}</p>"
            f"<p><strong>Next-step derivation:</strong> {self._render_path_html(str(snapshot.get('next_step_derivation_path', '')))}</p>"
            f"<p><strong>Completion evaluation:</strong> {self._render_path_html(str(snapshot.get('completion_evaluation_path', '')))}</p>"
            f"<p><strong>Review summary:</strong> {self._render_path_html(str(snapshot.get('review_summary_path', '')))}</p>"
            f"<p><strong>Promotion recommendation:</strong> {self._render_path_html(str(snapshot.get('promotion_recommendation_path', '')))}</p>"
            f"<p><strong>Next-objective proposal:</strong> {self._render_path_html(str(snapshot.get('next_objective_proposal_path', '')))}</p>"
            f"<p><strong>Reseed request:</strong> {self._render_path_html(str(snapshot.get('reseed_request_path', '')))}</p>"
            f"<p><strong>Reseed decision:</strong> {self._render_path_html(str(snapshot.get('reseed_decision_path', '')))}</p>"
            f"<p><strong>Continuation lineage:</strong> {self._render_path_html(str(snapshot.get('continuation_lineage_path', '')))}</p>"
            f"<p><strong>Effective next objective:</strong> {self._render_path_html(str(snapshot.get('effective_next_objective_path', '')))}</p>"
            f"<p><strong>Admitted candidate:</strong> {self._render_path_html(str(snapshot.get('admitted_candidate_path', '')))}</p>"
            f"<p><strong>Candidate handoff:</strong> {self._render_path_html(str(snapshot.get('admitted_candidate_handoff_path', '')))}</p>"
            f"<p><strong>Baseline comparison:</strong> {self._render_path_html(str(snapshot.get('baseline_comparison_path', '')))}</p>"
            f"<p><strong>Reference target:</strong> {self._render_path_html(str(snapshot.get('reference_target_path', '')))}</p>"
            f"<p><strong>Reference target consumption:</strong> {self._render_path_html(str(snapshot.get('reference_target_consumption_path', '')))}</p>"
            f"<p><strong>Skill-pack invocation:</strong> {self._render_path_html(str(snapshot.get('skill_pack_invocation_path', '')))}</p>"
            f"<p><strong>Skill-pack result:</strong> {self._render_path_html(str(snapshot.get('skill_pack_result_path', '')))}</p>"
            f"<p><strong>Quality gap summary:</strong> {self._render_path_html(str(snapshot.get('quality_gap_summary_path', '')))}</p>"
            f"<p><strong>Quality improvement summary:</strong> {self._render_path_html(str(snapshot.get('quality_improvement_summary_path', '')))}</p>"
            f"<p><strong>Quality roadmap:</strong> {self._render_path_html(str(snapshot.get('quality_roadmap_path', '')))}</p>"
            f"<p><strong>Quality priority matrix:</strong> {self._render_path_html(str(snapshot.get('quality_priority_matrix_path', '')))}</p>"
            f"<p><strong>Quality composite evaluation:</strong> {self._render_path_html(str(snapshot.get('quality_composite_evaluation_path', '')))}</p>"
            f"<p><strong>Quality next-pack plan:</strong> {self._render_path_html(str(snapshot.get('quality_next_pack_plan_path', '')))}</p>"
            f"<p><strong>Generation history:</strong> {self._render_path_html(str(snapshot.get('generation_history_path', '')))}</p>"
            f"<p><strong>Generation delta:</strong> {self._render_path_html(str(snapshot.get('generation_delta_path', '')))}</p>"
            f"<p><strong>Progress governance:</strong> {self._render_path_html(str(snapshot.get('progress_governance_path', '')))}</p>"
            f"<p><strong>Progress recommendation:</strong> {self._render_path_html(str(snapshot.get('progress_recommendation_path', '')))}</p>"
            f"<p><strong>Strategy selection:</strong> {self._render_path_html(str(snapshot.get('strategy_selection_path', '')))}</p>"
            f"<p><strong>Strategy rationale:</strong> {self._render_path_html(str(snapshot.get('strategy_rationale_path', '')))}</p>"
            f"<p><strong>Strategy follow-on plan:</strong> {self._render_path_html(str(snapshot.get('strategy_follow_on_plan_path', '')))}</p>"
            f"<p><strong>Strategy decision support:</strong> {self._render_path_html(str(snapshot.get('strategy_decision_support_path', '')))}</p>"
            f"<p><strong>Directive ID:</strong> {html.escape(str(snapshot.get('directive_id', '') or '<none>'))}</p>"
            f"<p><strong>Controller mode:</strong> <code>{html.escape(str(snapshot.get('controller_mode', '') or '<none>'))}</code> / cycles completed: <code>{html.escape(str(snapshot.get('cycles_completed', 0)))}</code></p>"
            f"<p><strong>Staged compact follow-ons:</strong> <code>{html.escape(str(snapshot.get('staged_compact_follow_on_count', 0)))}</code></p>"
            f"<p><strong>Remaining counted cycle budget:</strong> <code>{html.escape(str(snapshot.get('remaining_counted_cycle_budget', 0)))}</code></p>"
            f"<p><strong>Current objective source:</strong> <code>{html.escape(str(snapshot.get('current_objective_source_kind', '') or '<none>'))}</code></p>"
            f"<p><strong>Current objective:</strong> <code>{html.escape(str(snapshot.get('current_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Selected work item:</strong> <code>{html.escape(str(dict(work_summary.get('selected_work_item', {})).get('work_item_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Cycle reason:</strong> {html.escape(str(work_summary.get('reason', '') or snapshot.get('run_reason', '') or '<none recorded>'))}</p>"
            f"{cycle_materialization_note}"
            "</section>"
            "<section class='card'><h2>Created Output Files</h2>"
            f"{_html_list(created_lines or output_lines)}"
            "</section>"
            "<section class='card'><h2>Skipped Work</h2>"
            f"{_html_list(skipped_lines)}"
            "<h3>Deferred Items</h3>"
            f"{_html_list(deferred_lines)}"
            "</section>"
            "<section class='card'><h2>Trusted Evidence And Completion</h2>"
            f"<p><strong>Selected stage:</strong> <code>{html.escape(str(dict(next_step_derivation.get('selected_stage', {})).get('stage_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Next-step rationale:</strong> {html.escape(str(next_step_derivation.get('reason', '') or '<none recorded>'))}</p>"
            f"<p><strong>Completion note:</strong> {html.escape(str(completion_evaluation.get('reason', '') or '<none recorded>'))}</p>"
            "<h3>Knowledge packs</h3>"
            f"{_html_list(knowledge_pack_lines)}"
            "<h3>Missing required deliverables</h3>"
            f"{_html_list(missing_lines)}"
            "</section>"
            "<section class='card'><h2>Skill-Pack Quality Improvement</h2>"
            f"<p><strong>Selected skill pack:</strong> <code>{html.escape(str(snapshot.get('selected_skill_pack_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Skill-pack title:</strong> {html.escape(str(snapshot.get('selected_skill_pack_title', '') or '<none recorded>'))}</p>"
            f"<p><strong>Selected reason:</strong> {html.escape(str(snapshot.get('selected_skill_pack_reason', '') or '<none recorded>'))}</p>"
            f"<p><strong>Quality gap:</strong> <code>{html.escape(str(snapshot.get('quality_gap_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Quality gap title:</strong> {html.escape(str(snapshot.get('quality_gap_title', '') or '<none recorded>'))}</p>"
            f"<p><strong>Skill-pack result:</strong> <code>{html.escape(str(snapshot.get('skill_pack_result_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Quality improvement state:</strong> <code>{html.escape(str(snapshot.get('quality_improvement_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Reference target used:</strong> <code>{html.escape(str(dict(snapshot.get('successor_quality_improvement_summary', {})).get('active_bounded_reference_target_id', '') or snapshot.get('active_bounded_reference_target_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Improved relative to reference target:</strong> {html.escape('yes' if bool(dict(snapshot.get('successor_quality_improvement_summary', {})).get('improved_relative_to_reference_target', False)) else 'no')}</p>"
            f"<p><strong>Skill-pack invocation artifact:</strong> {self._render_path_html(str(snapshot.get('skill_pack_invocation_path', '')))}</p>"
            f"<p><strong>Skill-pack result artifact:</strong> {self._render_path_html(str(snapshot.get('skill_pack_result_path', '')))}</p>"
            f"<p><strong>Quality gap artifact:</strong> {self._render_path_html(str(snapshot.get('quality_gap_summary_path', '')))}</p>"
            f"<p><strong>Quality improvement artifact:</strong> {self._render_path_html(str(snapshot.get('quality_improvement_summary_path', '')))}</p>"
            "</section>"
            "<section class='card'><h2>Successor Quality Roadmap</h2>"
            f"<p><strong>Composite quality state:</strong> <code>{html.escape(str(snapshot.get('quality_composite_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Materially stronger than reference target in aggregate:</strong> {html.escape('yes' if bool(snapshot.get('materially_stronger_than_reference_target_in_aggregate', False)) else 'no')}</p>"
            f"<p><strong>Weakest dimension:</strong> <code>{html.escape(str(snapshot.get('quality_weakest_dimension_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Weakest dimension title:</strong> {html.escape(str(snapshot.get('quality_weakest_dimension_title', '') or '<none recorded>'))}</p>"
            f"<p><strong>Next recommended skill pack:</strong> <code>{html.escape(str(snapshot.get('quality_next_pack_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Next recommended objective:</strong> <code>{html.escape(str(snapshot.get('quality_next_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Roadmap artifact:</strong> {self._render_path_html(str(snapshot.get('quality_roadmap_path', '')))}</p>"
            f"<p><strong>Priority matrix:</strong> {self._render_path_html(str(snapshot.get('quality_priority_matrix_path', '')))}</p>"
            f"<p><strong>Composite evaluation:</strong> {self._render_path_html(str(snapshot.get('quality_composite_evaluation_path', '')))}</p>"
            f"<p><strong>Next-pack plan:</strong> {self._render_path_html(str(snapshot.get('quality_next_pack_plan_path', '')))}</p>"
            "</section>"
            "<section class='card'><h2>Generation Progress Governance</h2>"
            f"<p><strong>Generation index:</strong> <code>{html.escape(str(snapshot.get('generation_index', 0) or 0))}</code></p>"
            f"<p><strong>Prior generation index:</strong> <code>{html.escape(str(snapshot.get('prior_generation_index', 0) or 0))}</code></p>"
            f"<p><strong>Current admitted candidate:</strong> <code>{html.escape(str(snapshot.get('generation_current_candidate_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Prior admitted candidate:</strong> <code>{html.escape(str(snapshot.get('generation_prior_candidate_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Progress state:</strong> <code>{html.escape(str(snapshot.get('generation_progress_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Progress recommendation:</strong> <code>{html.escape(str(snapshot.get('generation_progress_recommendation_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Additional bounded improvement justified:</strong> {html.escape('yes' if bool(snapshot.get('generation_additional_improvement_justified', False)) else 'no')}</p>"
            f"<p><strong>Recommended remediation objective:</strong> <code>{html.escape(str(snapshot.get('generation_remediation_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Generation history artifact:</strong> {self._render_path_html(str(snapshot.get('generation_history_path', '')))}</p>"
            f"<p><strong>Generation delta artifact:</strong> {self._render_path_html(str(snapshot.get('generation_delta_path', '')))}</p>"
            f"<p><strong>Progress governance artifact:</strong> {self._render_path_html(str(snapshot.get('progress_governance_path', '')))}</p>"
            f"<p><strong>Progress recommendation artifact:</strong> {self._render_path_html(str(snapshot.get('progress_recommendation_path', '')))}</p>"
            "</section>"
            "<section class='card'><h2>Bounded Strategy Selection</h2>"
            f"<p><strong>Selected strategy:</strong> <code>{html.escape(str(snapshot.get('strategy_selection_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Follow-on family:</strong> <code>{html.escape(str(snapshot.get('strategy_follow_on_family', '') or '<none>'))}</code></p>"
            f"<p><strong>Operator review recommended before execution:</strong> {html.escape('yes' if bool(snapshot.get('strategy_operator_review_recommended', False)) else 'no')}</p>"
            f"<p><strong>Recommended follow-on objective:</strong> <code>{html.escape(str(snapshot.get('strategy_selected_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Recommended follow-on skill pack:</strong> <code>{html.escape(str(snapshot.get('strategy_selected_skill_pack_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Recommended dimension:</strong> <code>{html.escape(str(snapshot.get('strategy_selected_dimension_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Strategy rationale:</strong> {html.escape(str(snapshot.get('strategy_rationale_summary', '') or '<none recorded>'))}</p>"
            "<h3>Rejected alternatives</h3>"
            f"{_html_list(strategy_rejected_lines)}"
            f"<p><strong>Strategy selection artifact:</strong> {self._render_path_html(str(snapshot.get('strategy_selection_path', '')))}</p>"
            f"<p><strong>Strategy rationale artifact:</strong> {self._render_path_html(str(snapshot.get('strategy_rationale_path', '')))}</p>"
            f"<p><strong>Strategy follow-on plan artifact:</strong> {self._render_path_html(str(snapshot.get('strategy_follow_on_plan_path', '')))}</p>"
            f"<p><strong>Strategy decision-support artifact:</strong> {self._render_path_html(str(snapshot.get('strategy_decision_support_path', '')))}</p>"
            "</section>"
            "<section class='card'><h2>Campaign Governance</h2>"
            f"<p><strong>Campaign id:</strong> <code>{html.escape(str(snapshot.get('campaign_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign wave count:</strong> <code>{html.escape(str(snapshot.get('campaign_wave_count', 0) or 0))}</code></p>"
            f"<p><strong>Campaign progress state:</strong> <code>{html.escape(str(snapshot.get('campaign_progress_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign state:</strong> <code>{html.escape(str(snapshot.get('campaign_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign recommendation:</strong> <code>{html.escape(str(snapshot.get('campaign_recommendation_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign follow-on family:</strong> <code>{html.escape(str(snapshot.get('campaign_follow_on_family', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign refresh ready:</strong> {html.escape('yes' if bool(snapshot.get('campaign_refresh_revised_candidate_ready', False)) else 'no')}</p>"
            f"<p><strong>Last wave strategy:</strong> <code>{html.escape(str(snapshot.get('campaign_last_wave_strategy_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Last wave skill pack:</strong> <code>{html.escape(str(snapshot.get('campaign_last_wave_skill_pack_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Accumulated improved dimensions:</strong> {html.escape(', '.join(list(snapshot.get('campaign_accumulated_improved_dimension_ids', []))) or '<none>')}</p>"
            f"<p><strong>Remaining weak dimensions:</strong> {html.escape(', '.join(list(snapshot.get('campaign_remaining_weak_dimension_ids', []))) or '<none>')}</p>"
            f"<p><strong>Campaign history artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_history_path', '')))}</p>"
            f"<p><strong>Campaign delta artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_delta_path', '')))}</p>"
            f"<p><strong>Campaign governance artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_governance_path', '')))}</p>"
            f"<p><strong>Campaign recommendation artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_recommendation_path', '')))}</p>"
            f"<p><strong>Campaign wave plan artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_wave_plan_path', '')))}</p>"
            "</section>"
            "<section class='card'><h2>Campaign-Cycle Governance</h2>"
            f"<p><strong>Campaign-cycle id:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign-cycle index:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_index', 0) or 0))}</code></p>"
            f"<p><strong>Prior campaign-cycle index:</strong> <code>{html.escape(str(snapshot.get('prior_campaign_cycle_index', 0) or 0))}</code></p>"
            f"<p><strong>Campaign-cycle progress state:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_progress_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign-cycle state:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign-cycle recommendation:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_recommendation_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Campaign-cycle follow-on family:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_follow_on_family', '') or '<none>'))}</code></p>"
            f"<p><strong>Current rolled reference target:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_current_reference_target_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Prior rolled reference target:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_prior_reference_target_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Source campaign id:</strong> <code>{html.escape(str(snapshot.get('campaign_cycle_source_campaign_id', '') or '<none>'))}</code></p>"
            f"<p><strong>New dimensions vs prior cycle:</strong> {html.escape(', '.join(list(snapshot.get('campaign_cycle_new_dimension_ids', []))) or '<none>')}</p>"
            f"<p><strong>Remaining weak dimensions:</strong> {html.escape(', '.join(list(snapshot.get('campaign_cycle_remaining_weak_dimension_ids', []))) or '<none>')}</p>"
            f"<p><strong>Campaign-cycle history artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_cycle_history_path', '')))}</p>"
            f"<p><strong>Campaign-cycle delta artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_cycle_delta_path', '')))}</p>"
            f"<p><strong>Campaign-cycle governance artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_cycle_governance_path', '')))}</p>"
            f"<p><strong>Campaign-cycle recommendation artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_cycle_recommendation_path', '')))}</p>"
            f"<p><strong>Campaign-cycle follow-on plan artifact:</strong> {self._render_path_html(str(snapshot.get('campaign_cycle_follow_on_plan_path', '')))}</p>"
            "</section>"
            "<section class='card'><h2>Loop Governance</h2>"
            f"<p><strong>Loop id:</strong> <code>{html.escape(str(snapshot.get('loop_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Loop index:</strong> <code>{html.escape(str(snapshot.get('loop_index', 0) or 0))}</code></p>"
            f"<p><strong>Prior loop index:</strong> <code>{html.escape(str(snapshot.get('prior_loop_index', 0) or 0))}</code></p>"
            f"<p><strong>Loop progress state:</strong> <code>{html.escape(str(snapshot.get('loop_progress_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Loop state:</strong> <code>{html.escape(str(snapshot.get('loop_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Loop recommendation:</strong> <code>{html.escape(str(snapshot.get('loop_recommendation_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Loop follow-on family:</strong> <code>{html.escape(str(snapshot.get('loop_follow_on_family', '') or '<none>'))}</code></p>"
            f"<p><strong>Current loop target:</strong> <code>{html.escape(str(snapshot.get('loop_current_reference_target_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Prior loop target:</strong> <code>{html.escape(str(snapshot.get('loop_prior_reference_target_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Source campaign-cycle id:</strong> <code>{html.escape(str(snapshot.get('loop_source_campaign_cycle_id', '') or '<none>'))}</code></p>"
            f"<p><strong>New dimensions vs prior loop:</strong> {html.escape(', '.join(list(snapshot.get('loop_new_dimension_ids', []))) or '<none>')}</p>"
            f"<p><strong>Remaining weak dimensions:</strong> {html.escape(', '.join(list(snapshot.get('loop_remaining_weak_dimension_ids', []))) or '<none>')}</p>"
            f"<p><strong>Loop history artifact:</strong> {self._render_path_html(str(snapshot.get('loop_history_path', '')))}</p>"
            f"<p><strong>Loop delta artifact:</strong> {self._render_path_html(str(snapshot.get('loop_delta_path', '')))}</p>"
            f"<p><strong>Loop governance artifact:</strong> {self._render_path_html(str(snapshot.get('loop_governance_path', '')))}</p>"
            f"<p><strong>Loop recommendation artifact:</strong> {self._render_path_html(str(snapshot.get('loop_recommendation_path', '')))}</p>"
            f"<p><strong>Loop follow-on plan artifact:</strong> {self._render_path_html(str(snapshot.get('loop_follow_on_plan_path', '')))}</p>"
            "</section>"
            "<section class='card'><h2>Quality-Chain Reentry</h2>"
            f"<p><strong>Reentry state:</strong> <code>{html.escape(str(snapshot.get('quality_chain_reentry_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Recommended action:</strong> <code>{html.escape(str(snapshot.get('quality_chain_reentry_action', '') or '<none>'))}</code></p>"
            f"<p><strong>Reentry rationale:</strong> {html.escape(str(snapshot.get('quality_chain_reentry_reason', '') or '<none recorded>'))}</p>"
            f"<p><strong>Next quality objective:</strong> <code>{html.escape(str(snapshot.get('quality_chain_next_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Next quality objective class:</strong> <code>{html.escape(str(snapshot.get('quality_chain_next_objective_class', '') or '<none>'))}</code></p>"
            f"<p><strong>Compact follow-on:</strong> {html.escape('yes' if bool(snapshot.get('quality_chain_next_objective_compact', False)) else 'no')}</p>"
            f"<p><strong>Reentry artifact:</strong> {self._render_path_html(str(snapshot.get('quality_chain_reentry_path', '')))}</p>"
            "</section>"
            "<section class='card'><h2>Review And Promotion</h2>"
            f"<p><strong>Review status:</strong> <code>{html.escape(str(review_summary.get('review_status', '') or '<none>'))}</code></p>"
            f"<p><strong>Promotion recommendation:</strong> <code>{html.escape(str(promotion_recommendation.get('promotion_recommendation_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Recommendation rationale:</strong> {html.escape(str(promotion_recommendation.get('rationale', '') or '<none recorded>'))}</p>"
            f"<p><strong>Next bounded objective:</strong> <code>{html.escape(str(next_objective_proposal.get('objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Next-objective rationale:</strong> {html.escape(str(next_objective_proposal.get('rationale', '') or '<none recorded>'))}</p>"
            f"<p><strong>Operator review required:</strong> {html.escape('yes' if bool(review_summary.get('operator_review_required', False)) else 'no')}</p>"
            f"<p><strong>Reseed state:</strong> <code>{html.escape(str(snapshot.get('reseed_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Latest decision:</strong> <code>{html.escape(str(reseed_decision.get('operator_decision', '') or '<none>'))}</code></p>"
            f"<p><strong>Continuation authorized:</strong> {html.escape('yes' if bool(snapshot.get('continuation_authorized', False)) else 'no')}</p>"
            f"<p><strong>Effective next objective:</strong> <code>{html.escape(str(snapshot.get('effective_next_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Effective objective origin:</strong> <code>{html.escape(str(snapshot.get('effective_next_objective_authorization_origin', '') or '<none>'))}</code></p>"
            f"<p><strong>Auto-continue transition:</strong> <code>{html.escape(str(snapshot.get('auto_continue_transition_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Same-session cycle started:</strong> {html.escape('yes' if bool(snapshot.get('auto_continue_transition_executed_in_session', False)) else 'no')}</p>"
            f"<p><strong>Transition lineage:</strong> <code>{html.escape(str(snapshot.get('auto_continue_transition_from_objective_id', '') or '<none>'))}</code> -> <code>{html.escape(str(snapshot.get('auto_continue_transition_to_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Request rationale:</strong> {html.escape(str(reseed_request.get('rationale', '') or '<none recorded>'))}</p>"
            f"<p><strong>Decision note:</strong> {html.escape(str(reseed_decision.get('operator_note', '') or '<none recorded>'))}</p>"
            f"<p><strong>Lineage completed objective:</strong> <code>{html.escape(str(continuation_lineage.get('completed_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Effective-objective rationale:</strong> {html.escape(str(effective_next_objective.get('rationale', '') or '<none recorded>'))}</p>"
            "</section>"
            "<section class='card'><h2>Baseline Admission</h2>"
            f"<p><strong>Admission review:</strong> <code>{html.escape(str(snapshot.get('baseline_admission_review_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Admission recommendation:</strong> <code>{html.escape(str(snapshot.get('baseline_admission_recommendation_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Admission decision:</strong> <code>{html.escape(str(snapshot.get('baseline_admission_decision_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Admitted bounded baseline candidate:</strong> {html.escape('yes' if bool(snapshot.get('baseline_candidate_admitted', False)) else 'no')}</p>"
            f"<p><strong>Recommendation rationale:</strong> {html.escape(str(baseline_admission_recommendation.get('rationale', '') or '<none recorded>'))}</p>"
            f"<p><strong>Decision note:</strong> {html.escape(str(baseline_admission_decision.get('operator_note', '') or '<none recorded>'))}</p>"
            f"<p><strong>Remediation objective:</strong> <code>{html.escape(str(snapshot.get('baseline_remediation_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Remediation rationale:</strong> {html.escape(str(baseline_remediation_proposal.get('rationale', '') or '<none recorded>'))}</p>"
            f"<p><strong>Admission review artifact:</strong> {self._render_path_html(str(snapshot.get('baseline_admission_review_path', '')))}</p>"
            f"<p><strong>Admission recommendation artifact:</strong> {self._render_path_html(str(snapshot.get('baseline_admission_recommendation_path', '')))}</p>"
            f"<p><strong>Admission decision artifact:</strong> {self._render_path_html(str(snapshot.get('baseline_admission_decision_path', '')))}</p>"
            f"<p><strong>Remediation proposal artifact:</strong> {self._render_path_html(str(snapshot.get('baseline_remediation_proposal_path', '')))}</p>"
            f"<p><strong>Candidate bundle identity:</strong> <code>{html.escape(str(baseline_admission_review.get('candidate_bundle_identity', '') or '<none>'))}</code></p>"
            "</section>"
            "<section class='card'><h2>Admitted Candidate Lifecycle</h2>"
            f"<p><strong>Admitted candidate state:</strong> <code>{html.escape(str(snapshot.get('admitted_candidate_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Candidate handoff state:</strong> <code>{html.escape(str(snapshot.get('admitted_candidate_handoff_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Handoff ready:</strong> {html.escape('yes' if bool(snapshot.get('admitted_candidate_handoff_ready', False)) else 'no')}</p>"
            f"<p><strong>Baseline comparison state:</strong> <code>{html.escape(str(snapshot.get('baseline_comparison_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Baseline comparison result:</strong> <code>{html.escape(str(snapshot.get('baseline_comparison_result_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Stronger than current bounded baseline:</strong> {html.escape('yes' if bool(snapshot.get('stronger_than_current_bounded_baseline', False)) else 'no')}</p>"
            f"<p><strong>Future reference target:</strong> <code>{html.escape(str(snapshot.get('future_reference_target_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Future reference eligible:</strong> {html.escape('yes' if bool(snapshot.get('future_reference_target_eligible', False)) else 'no')}</p>"
            f"<p><strong>Preferred reference target:</strong> <code>{html.escape(str(snapshot.get('future_reference_target_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Revised candidate state:</strong> <code>{html.escape(str(snapshot.get('revised_candidate_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Revised candidate id:</strong> <code>{html.escape(str(snapshot.get('revised_candidate_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Prior admitted candidate:</strong> <code>{html.escape(str(snapshot.get('revised_candidate_prior_admitted_candidate_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Revised candidate materially stronger in aggregate:</strong> {html.escape('yes' if bool(snapshot.get('revised_candidate_materially_stronger_in_aggregate', False)) else 'no')}</p>"
            f"<p><strong>Reference target rollover:</strong> <code>{html.escape(str(snapshot.get('revised_candidate_reference_rollover_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Reference target consumption:</strong> <code>{html.escape(str(snapshot.get('reference_target_consumption_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Active bounded reference target:</strong> <code>{html.escape(str(snapshot.get('active_bounded_reference_target_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Protected live baseline:</strong> <code>{html.escape(str(snapshot.get('protected_live_baseline_reference_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Comparison basis:</strong> <code>{html.escape(str(snapshot.get('reference_target_comparison_basis', '') or '<none>'))}</code></p>"
            f"<p><strong>Fallback reason:</strong> {html.escape(str(snapshot.get('reference_target_fallback_reason', '') or '<none recorded>'))}</p>"
            f"<p><strong>Comparison remediation objective:</strong> <code>{html.escape(str(snapshot.get('comparison_remediation_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Comparison rationale:</strong> {html.escape(str(dict(snapshot.get('baseline_comparison', {})).get('comparison_rationale', '') or '<none recorded>'))}</p>"
            f"<p><strong>Admitted candidate artifact:</strong> {self._render_path_html(str(snapshot.get('admitted_candidate_path', '')))}</p>"
            f"<p><strong>Candidate handoff artifact:</strong> {self._render_path_html(str(snapshot.get('admitted_candidate_handoff_path', '')))}</p>"
            f"<p><strong>Baseline comparison artifact:</strong> {self._render_path_html(str(snapshot.get('baseline_comparison_path', '')))}</p>"
            f"<p><strong>Revised candidate bundle artifact:</strong> {self._render_path_html(str(snapshot.get('revised_candidate_bundle_path', '')))}</p>"
            f"<p><strong>Revised candidate handoff artifact:</strong> {self._render_path_html(str(snapshot.get('revised_candidate_handoff_path', '')))}</p>"
            f"<p><strong>Revised candidate comparison artifact:</strong> {self._render_path_html(str(snapshot.get('revised_candidate_comparison_path', '')))}</p>"
            f"<p><strong>Revised candidate promotion summary artifact:</strong> {self._render_path_html(str(snapshot.get('revised_candidate_promotion_summary_path', '')))}</p>"
            f"<p><strong>Reference target artifact:</strong> {self._render_path_html(str(snapshot.get('reference_target_path', '')))}</p>"
            f"<p><strong>Reference target consumption artifact:</strong> {self._render_path_html(str(snapshot.get('reference_target_consumption_path', '')))}</p>"
            "</section>"
            "<section class='card'><h2>Auto-Continue</h2>"
            f"<p><strong>Enabled:</strong> {html.escape('yes' if bool(snapshot.get('auto_continue_enabled', False)) else 'no')}</p>"
            f"<p><strong>Allowed classes:</strong> {html.escape(', '.join(list(snapshot.get('auto_continue_allowed_objective_classes', []))) or '<none>')}</p>"
            f"<p><strong>Chain count / cap:</strong> <code>{html.escape(str(int(snapshot.get('auto_continue_chain_count', 0) or 0)))}/{html.escape(str(int(snapshot.get('auto_continue_chain_cap', 1) or 1)))}</code></p>"
            f"<p><strong>Last reason:</strong> <code>{html.escape(str(snapshot.get('auto_continue_last_reason', '') or '<none>'))}</code></p>"
            f"<p><strong>Last origin:</strong> <code>{html.escape(str(snapshot.get('auto_continue_last_origin', '') or '<none>'))}</code></p>"
            f"<p><strong>Budget staging decision:</strong> <code>{html.escape(str(snapshot.get('budget_staging_decision', '') or '<none>'))}</code></p>"
            f"<p><strong>Budget staging rationale:</strong> {html.escape(str(snapshot.get('budget_staging_rationale', '') or '<none recorded>'))}</p>"
            f"<p><strong>Budget staging objective:</strong> <code>{html.escape(str(snapshot.get('budget_staging_objective_id', '') or '<none>'))}</code></p>"
            f"<p><strong>Budget staging objective class:</strong> <code>{html.escape(str(snapshot.get('budget_staging_objective_class', '') or '<none>'))}</code></p>"
            f"<p><strong>Remaining counted cycle budget:</strong> <code>{html.escape(str(int(snapshot.get('remaining_counted_cycle_budget', 0) or 0)))}</code></p>"
            f"<p><strong>Staged compact follow-ons:</strong> <code>{html.escape(str(int(snapshot.get('staged_compact_follow_on_count', 0) or 0)))}</code></p>"
            f"<p><strong>Transition state:</strong> <code>{html.escape(str(snapshot.get('auto_continue_transition_state', '') or '<none>'))}</code></p>"
            f"<p><strong>Transition artifact:</strong> {self._render_path_html(str(snapshot.get('auto_continue_transition_path', '')))}</p>"
            f"<p><strong>Policy artifact:</strong> {self._render_path_html(str(snapshot.get('auto_continue_policy_path', '')))}</p>"
            f"<p><strong>State artifact:</strong> {self._render_path_html(str(snapshot.get('auto_continue_state_path', '')))}</p>"
            f"<p><strong>Decision artifact:</strong> {self._render_path_html(str(snapshot.get('auto_continue_decision_path', '')))}</p>"
            "</section>"
            "<section class='card'><h2>Artifact Summary Cross-Check</h2>"
            f"<pre>{html.escape(_json_dump(cycle_status_payload))}</pre>"
            "</section>"
            "</div>"
        )
        return _render_page(
            title="NOVALI Latest Cycle Summary",
            subtitle="Read-only view of what the latest bounded cycle created, skipped, and deferred.",
            body=body,
            current_path="/cycle",
        )

    def render_preview_page(self, requested_path: str) -> str:
        path = self._resolve_preview_path(requested_path)
        if path is None:
            body = (
                "<div class='grid'><section class='card'>"
                "<h2>Preview Unavailable</h2>"
                "<p>The requested preview path was missing, outside the packaged operator roots, or not a supported text/json/python/log artifact.</p>"
                f"<p><strong>Requested path:</strong> <code>{html.escape(str(requested_path or ''))}</code></p>"
                "</section></div>"
            )
            return _render_page(
                title="NOVALI Artifact Preview",
                subtitle="Read-only preview of supported workspace and runtime text artifacts.",
                body=body,
                current_path="",
            )

        raw = path.read_bytes()
        truncated = len(raw) > PREVIEW_MAX_BYTES
        preview_bytes = raw[:PREVIEW_MAX_BYTES]
        text = preview_bytes.decode("utf-8", errors="replace")
        note = (
            f"Preview truncated to {PREVIEW_MAX_BYTES} bytes."
            if truncated
            else "Read-only text preview."
        )
        body = (
            "<div class='grid'>"
            "<section class='card'>"
            "<h2>Artifact Preview</h2>"
            f"<p><strong>Path:</strong> {self._render_path_html(str(path))}</p>"
            f"<p><strong>Modified:</strong> {html.escape(_format_timestamp(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()))}</p>"
            f"<p><strong>Size:</strong> {html.escape(_format_bytes(path.stat().st_size))}</p>"
            f"<p class='preview-note'>{html.escape(note)}</p>"
            f"<pre>{html.escape(text)}</pre>"
            "</section>"
            "</div>"
        )
        return _render_page(
            title="NOVALI Artifact Preview",
            subtitle="Read-only preview of supported workspace and runtime text artifacts.",
            body=body,
            current_path="",
        )

    def sample_directives(self) -> list[dict[str, str]]:
        return sample_directive_paths(self.package_root)

    def select_sample_directive(self, sample_path: str) -> None:
        self.update_profile(directive_file=sample_path, resume_mode="new_bootstrap")

    def save_uploaded_directive(self, *, filename: str, payload: bytes) -> Path:
        safe_name = _slug(Path(filename or "uploaded_directive.json").name, fallback="uploaded_directive")
        if not safe_name.lower().endswith(".json"):
            safe_name = f"{safe_name}.json"
        target = self.directive_root / safe_name
        target.write_bytes(payload)
        self.update_profile(directive_file=_normalize_path(target), resume_mode="new_bootstrap")
        return target

    def _runtime_payload_from_form(self, form_data: dict[str, str]) -> dict[str, Any]:
        execution_profile = (
            str(
                form_data.get(
                    "execution_profile",
                    EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
                )
            ).strip()
            or EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION
        )
        workspace_id = str(form_data.get("workspace_id", "")).strip()
        payload = build_runtime_constraints_for_profile(
            self.package_root,
            operator_root=self.operator_root,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            governed_execution_mode=str(
                form_data.get("governed_execution_mode", GOVERNED_EXECUTION_MODE_SINGLE_CYCLE)
            ).strip()
            or GOVERNED_EXECUTION_MODE_SINGLE_CYCLE,
            max_cycles_per_invocation=str(form_data.get("max_cycles_per_invocation", "")).strip(),
        )
        payload["constraints"].update(
            {
                "max_memory_mb": int(form_data.get("max_memory_mb", "").strip()),
                "max_python_threads": int(form_data.get("max_python_threads", "").strip()),
                "max_child_processes": int(form_data.get("max_child_processes", "").strip()),
                "subprocess_mode": str(form_data.get("subprocess_mode", "disabled")).strip() or "disabled",
                "session_time_limit_seconds": int(form_data.get("session_time_limit_seconds", "").strip()),
            }
        )
        return payload

    def _envelope_payload_from_form(self, form_data: dict[str, str]) -> dict[str, Any]:
        payload = build_default_operator_runtime_envelope_spec(self.package_root)
        payload["backend_kind"] = str(form_data.get("backend_kind", BACKEND_LOCAL_GUARDED)).strip() or BACKEND_LOCAL_GUARDED
        intents = dict(payload.get("constraint_intents", {}))
        cpu_limit_cpus = str(form_data.get("cpu_limit_cpus", "")).strip()
        intents["cpu_limit_cpus"] = None if not cpu_limit_cpus else float(cpu_limit_cpus)
        intents["network_policy_intent"] = (
            str(form_data.get("network_policy_intent", "deny_all")).strip() or "deny_all"
        )
        payload["constraint_intents"] = intents
        docker_settings = dict(payload.get("backend_settings", {}).get(BACKEND_LOCAL_DOCKER, {}))
        docker_settings["image"] = (
            str(form_data.get("docker_image", docker_settings.get("image", "python:3.12-slim"))).strip()
            or str(docker_settings.get("image", "python:3.12-slim"))
        )
        payload["backend_settings"][BACKEND_LOCAL_DOCKER] = docker_settings
        return payload

    def _runtime_form_defaults_from_payloads(
        self,
        *,
        runtime_payload: dict[str, Any],
        runtime_envelope: dict[str, Any],
    ) -> dict[str, str]:
        constraints = dict(runtime_payload.get("constraints", {}))
        execution_profile = str(
            runtime_payload.get(
                "execution_profile",
                EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
            )
        )
        governed_execution_policy = dict(runtime_payload.get("governed_execution", {}))
        workspace_policy = dict(runtime_payload.get("workspace_policy", {}))
        suggested_workspace_id = str(workspace_policy.get("workspace_id", "")).strip()
        if not suggested_workspace_id and self.directive_file:
            suggested_workspace_id = _slug(Path(self.directive_file).stem, fallback="workspace_default")
        intents = dict(runtime_envelope.get("constraint_intents", {}))
        docker_settings = dict(dict(runtime_envelope.get("backend_settings", {})).get(BACKEND_LOCAL_DOCKER, {}))
        cpu_value = intents.get("cpu_limit_cpus")
        return {
            "execution_profile": execution_profile,
            "workspace_id": suggested_workspace_id,
            "workspace_root": str(workspace_policy.get("workspace_root", "")),
            "generated_output_root": str(workspace_policy.get("generated_output_root", "")),
            "protected_root_hints": ";".join(list(workspace_policy.get("protected_root_hints", []))),
            "max_memory_mb": str(constraints.get("max_memory_mb", "")),
            "max_python_threads": str(constraints.get("max_python_threads", "")),
            "max_child_processes": str(constraints.get("max_child_processes", "")),
            "subprocess_mode": str(constraints.get("subprocess_mode", "disabled")),
            "working_directory": str(constraints.get("working_directory", "")),
            "allowed_write_roots": ";".join(list(constraints.get("allowed_write_roots", []))),
            "session_time_limit_seconds": str(constraints.get("session_time_limit_seconds", "")),
            "backend_kind": str(runtime_envelope.get("backend_kind", BACKEND_LOCAL_GUARDED)),
            "governed_execution_mode": str(
                governed_execution_policy.get("mode", GOVERNED_EXECUTION_MODE_SINGLE_CYCLE)
            ),
            "max_cycles_per_invocation": str(
                governed_execution_policy.get("max_cycles_per_invocation", 1)
            ),
            "cpu_limit_cpus": "" if cpu_value in {None, ""} else str(cpu_value),
            "docker_image": str(docker_settings.get("image", "python:3.12-slim")),
            "network_policy_intent": str(intents.get("network_policy_intent", "deny_all")),
        }

    def runtime_form_defaults(self) -> dict[str, str]:
        runtime_payload = load_runtime_constraints_or_default(root=self.operator_root, package_root=self.package_root)
        runtime_envelope = load_runtime_envelope_spec_or_default(root=self.operator_root, package_root=self.package_root)
        return self._runtime_form_defaults_from_payloads(
            runtime_payload=runtime_payload,
            runtime_envelope=runtime_envelope,
        )

    def auto_continue_policy_defaults(self) -> dict[str, str]:
        payload = load_successor_auto_continue_policy(self.operator_root)
        return {
            "enabled": "true" if bool(payload.get("enabled", False)) else "false",
            "allowed_objective_classes": ";".join(
                list(payload.get("allowed_objective_classes", []))
            ),
            "max_auto_continue_chain_length": str(
                payload.get("max_auto_continue_chain_length", 1) or 1
            ),
            "require_manual_approval_for_first_entry": (
                "true"
                if bool(payload.get("require_manual_approval_for_first_entry", True))
                else "false"
            ),
            "require_review_supported_proposals": (
                "true"
                if bool(payload.get("require_review_supported_proposals", True))
                else "false"
            ),
        }

    def save_auto_continue_policy(self, form_data: dict[str, str]) -> dict[str, Any]:
        allowed_raw = str(form_data.get("allowed_objective_classes", "")).replace("\r", "\n")
        requested_classes = [
            str(item).strip()
            for chunk in allowed_raw.replace(",", "\n").replace(";", "\n").splitlines()
            for item in [chunk]
            if str(item).strip()
        ]
        invalid_classes = [
            item for item in requested_classes if item not in AUTO_CONTINUE_OBJECTIVE_CLASSES
        ]
        if invalid_classes:
            return {
                "ok": False,
                "headline": "Auto-continue policy was not saved.",
                "details": [
                    "Unknown objective classes were requested for auto-continue.",
                    *[str(item) for item in invalid_classes],
                ],
            }
        try:
            saved = save_successor_auto_continue_policy(
                {
                    "enabled": str(form_data.get("enabled", "false")),
                    "allowed_objective_classes": requested_classes,
                    "max_auto_continue_chain_length": str(
                        form_data.get("max_auto_continue_chain_length", "1")
                    ),
                    "require_manual_approval_for_first_entry": str(
                        form_data.get("require_manual_approval_for_first_entry", "true")
                    ),
                    "require_review_supported_proposals": str(
                        form_data.get("require_review_supported_proposals", "true")
                    ),
                },
                root=self.operator_root,
            )
        except Exception as exc:
            return {
                "ok": False,
                "headline": "Auto-continue policy was not saved.",
                "details": [str(exc)],
            }
        return {
            "ok": True,
            "headline": "Auto-continue policy saved.",
            "details": [
                f"Enabled: {bool(saved.get('enabled', False))}",
                "Allowed classes: "
                + (", ".join(list(saved.get("allowed_objective_classes", []))) or "<none>"),
                "Chain cap: "
                + str(saved.get("max_auto_continue_chain_length", 1) or 1),
                "Manual approval for first entry: "
                + (
                    "yes"
                    if bool(saved.get("require_manual_approval_for_first_entry", True))
                    else "no"
                ),
                "Require review-supported proposals: "
                + (
                    "yes"
                    if bool(saved.get("require_review_supported_proposals", True))
                    else "no"
                ),
                f"Policy artifact: {successor_auto_continue_policy_path(self.operator_root)}",
            ],
        }

    def _render_runtime_policy_preview(self, runtime_defaults: dict[str, str]) -> str:
        lines = [
            "Attempted Runtime Policy",
            "",
            f"- execution profile: {runtime_defaults.get('execution_profile', '') or '<missing>'}",
            f"- workspace id: {runtime_defaults.get('workspace_id', '') or '<none>'}",
            f"- active workspace root: {runtime_defaults.get('workspace_root', '') or '<not required>'}",
            f"- generated output root: {runtime_defaults.get('generated_output_root', '') or '<missing>'}",
            f"- governed execution mode: {runtime_defaults.get('governed_execution_mode', '') or '<missing>'}",
            f"- max cycles per invocation: {runtime_defaults.get('max_cycles_per_invocation', '') or '<missing>'}",
            f"- backend: {runtime_defaults.get('backend_kind', '') or '<missing>'}",
            f"- docker image: {runtime_defaults.get('docker_image', '') or '<n/a>'}",
            f"- session time limit: {runtime_defaults.get('session_time_limit_seconds', '') or '<missing>'}",
            f"- allowed write roots: {runtime_defaults.get('allowed_write_roots', '') or '<missing>'}",
        ]
        return "\n".join(lines)

    def save_runtime_policy(self, form_data: dict[str, str]) -> dict[str, Any]:
        try:
            runtime_payload = self._runtime_payload_from_form(form_data)
            envelope_payload = self._envelope_payload_from_form(form_data)
        except Exception as exc:
            return {
                "ok": False,
                "headline": "Runtime policy parsing failed.",
                "details": [str(exc)],
            }

        operator_snapshot = self.current_operator_snapshot()
        runtime_errors, normalized_runtime, _ = validate_runtime_constraints(
            runtime_payload,
            package_root=self.package_root,
            operator_root=self.operator_root,
        )
        envelope_errors, normalized_envelope, _ = validate_operator_runtime_envelope_spec(
            envelope_payload,
            runtime_constraints=normalized_runtime,
            trusted_source_bindings=load_trusted_source_bindings_or_default(
                root=self.operator_root,
                package_root=self.package_root,
            ),
            backend_probe=dict(operator_snapshot.get("runtime_backend_probe", {})),
            enforce_backend_availability=True,
        )
        errors = list(runtime_errors) + list(envelope_errors)
        if errors:
            attempted_defaults = self._runtime_form_defaults_from_payloads(
                runtime_payload=normalized_runtime or runtime_payload,
                runtime_envelope=normalized_envelope or envelope_payload,
            )
            details = list(errors)
            if (
                self.is_packaged_handoff_context()
                and str(form_data.get("backend_kind", "")).strip() == BACKEND_LOCAL_DOCKER
                and any(
                    "selected runtime backend is unavailable: local_docker" in str(item)
                    for item in errors
                )
            ):
                details.append(
                    "Standalone package hint: keep backend local_guarded in the packaged browser UI. "
                    "The current container already provides the Docker execution envelope, so nested "
                    "local_docker launches are not available in this slice."
                )
            details.append("Authoritative runtime policy remains unchanged because the requested values were not saved.")
            return {
                "ok": False,
                "headline": "Runtime policy was not saved.",
                "details": details,
                "runtime_form_override": attempted_defaults,
                "attempted_runtime_summary": self._render_runtime_policy_preview(attempted_defaults),
            }

        save_runtime_constraints(normalized_runtime, root=self.operator_root)
        save_runtime_envelope_spec(normalized_envelope, root=self.operator_root)
        workspace_policy = dict(normalized_runtime.get("workspace_policy", {}))
        return {
            "ok": True,
            "headline": "Runtime policy saved and applied for future launches.",
            "details": [
                f"Execution profile: {normalized_runtime.get('execution_profile', '')}",
                (
                    "Governed execution controller: "
                    f"{dict(normalized_runtime.get('governed_execution', {})).get('mode', '')} / "
                    f"max_cycles={dict(normalized_runtime.get('governed_execution', {})).get('max_cycles_per_invocation', '')}"
                ),
                (
                    "Active workspace: "
                    f"{workspace_policy.get('workspace_id', '')} -> {workspace_policy.get('workspace_root', '')}"
                    if str(workspace_policy.get("workspace_root", "")).strip()
                    else "Active workspace: <not required for this profile>"
                ),
                f"Runtime constraints source: {operator_runtime_constraints_path(self.operator_root)}",
                f"Runtime envelope source: {operator_runtime_envelope_spec_path(self.operator_root)}",
            ],
        }

    def decide_reseed(
        self,
        *,
        operator_decision: str,
        operator_note: str = "",
        continue_after_approval: bool = False,
    ) -> dict[str, Any]:
        snapshot = self._observability_snapshot()
        workspace_root = str(snapshot.get("workspace_root", "")).strip()
        if not workspace_root:
            return {
                "ok": False,
                "headline": "No active workspace is available for reseed review.",
                "details": [
                    "Complete a bounded governed run before attempting review-based continuation.",
                ],
            }
        try:
            result = materialize_successor_reseed_decision(
                workspace_root=workspace_root,
                operator_decision=operator_decision,
                operator_note=operator_note,
                operator_root=self.operator_root,
            )
        except Exception as exc:
            return {
                "ok": False,
                "headline": "Reseed decision could not be recorded.",
                "details": [str(exc)],
            }

        decision_payload = dict(result.get("decision", {}))
        effective_payload = dict(result.get("effective_next_objective", {}))
        self.update_profile(resume_mode="resume_existing", launch_action="governed_execution")
        details = [
            f"Decision: {decision_payload.get('operator_decision', '')}",
            f"Reseed state: {decision_payload.get('reseed_state', '')}",
            f"Continuation authorized: {bool(effective_payload.get('continuation_authorized', False))}",
            f"Effective next objective id: {effective_payload.get('objective_id', '') or '<none>'}",
            f"Reseed request: {result.get('reseed_request_path', '')}",
            f"Reseed decision: {result.get('reseed_decision_path', '')}",
            f"Lineage: {result.get('continuation_lineage_path', '')}",
            f"Effective next objective: {result.get('effective_next_objective_path', '')}",
        ]
        notice = {
            "ok": True,
            "headline": "Reseed decision recorded.",
            "details": details,
        }
        if continue_after_approval and str(operator_decision).strip().lower() == "approve":
            launch_result = self.launch(
                resume_mode="resume_existing",
                launch_action="governed_execution",
                state_root=str(self.state_root),
            )
            launch_details = list(launch_result.get("details", []))
            notice["headline"] = "Reseed approved and governed continuation launched."
            notice["ok"] = bool(launch_result.get("ok", False))
            notice["details"] = details + launch_details
            if str(launch_result.get("summary", "")).strip():
                notice["summary"] = str(launch_result.get("summary", ""))
        return notice

    def decide_baseline_admission(
        self,
        *,
        operator_decision: str,
        operator_note: str = "",
    ) -> dict[str, Any]:
        snapshot = self._observability_snapshot()
        workspace_root = str(snapshot.get("workspace_root", "")).strip()
        if not workspace_root:
            return {
                "ok": False,
                "headline": "No active workspace is available for candidate admission review.",
                "details": [
                    "Complete a bounded promotion-bundle objective before attempting baseline admission review.",
                ],
            }
        try:
            result = materialize_successor_baseline_admission_decision(
                workspace_root=workspace_root,
                operator_decision=operator_decision,
                operator_note=operator_note,
            )
        except Exception as exc:
            return {
                "ok": False,
                "headline": "Baseline admission decision could not be recorded.",
                "details": [str(exc)],
            }

        decision_payload = dict(result.get("decision", {}))
        remediation_payload = dict(result.get("remediation_proposal", {}))
        admitted_candidate_payload = dict(result.get("admitted_candidate", {}))
        comparison_payload = dict(result.get("baseline_comparison", {}))
        reference_target_payload = dict(result.get("reference_target", {}))
        revised_candidate_bundle = dict(result.get("revised_candidate_bundle", {}))
        revised_candidate_comparison = dict(
            result.get("revised_candidate_comparison", {})
        )
        revised_candidate_promotion_summary = dict(
            result.get("revised_candidate_promotion_summary", {})
        )
        reference_target_consumption_payload = dict(
            result.get("reference_target_consumption", {})
        )
        next_objective_payload = dict(result.get("next_objective_proposal", {}))
        quality_roadmap_outputs = dict(result.get("quality_roadmap_outputs", {}))
        next_pack_plan = dict(quality_roadmap_outputs.get("next_pack_plan", {}))
        return {
            "ok": True,
            "headline": "Baseline admission decision recorded.",
            "details": [
                f"Decision: {decision_payload.get('operator_decision', '')}",
                f"Admission state: {decision_payload.get('admission_decision_state', '')}",
                "Admitted bounded baseline candidate: "
                + str(
                    bool(
                        decision_payload.get(
                            "admitted_bounded_baseline_candidate",
                            False,
                        )
                    )
                ),
                f"Recommendation state: {decision_payload.get('admission_recommendation_state', '')}",
                f"Remediation required: {bool(decision_payload.get('remediation_required', False))}",
                f"Admission review: {snapshot.get('baseline_admission_review_path', '') or '<none>'}",
                f"Admission decision: {result.get('decision_path', '')}",
                "Remediation proposal: "
                + str(
                    result.get("remediation_proposal_path", "")
                    or remediation_payload.get("objective_id", "")
                    or "<none>"
                ),
                "Admitted candidate state: "
                + str(admitted_candidate_payload.get("admitted_candidate_state", "") or "<none>"),
                "Baseline comparison: "
                + str(comparison_payload.get("comparison_result_state", "") or "<none>"),
                "Reference target: "
                + str(reference_target_payload.get("reference_target_state", "") or "<none>"),
                "Revised candidate state: "
                + str(revised_candidate_bundle.get("revised_candidate_state", "") or "<none>"),
                "Revised candidate id: "
                + str(revised_candidate_bundle.get("revised_candidate_id", "") or "<none>"),
                "Revised candidate stronger than prior admitted candidate in aggregate: "
                + str(
                    bool(
                        revised_candidate_comparison.get(
                            "materially_stronger_than_prior_admitted_candidate_in_aggregate",
                            False,
                        )
                    )
                ),
                "Reference target rollover: "
                + str(
                    revised_candidate_promotion_summary.get(
                        "reference_target_rollover_state",
                        "",
                    )
                    or "<none>"
                ),
                "Reference target consumption: "
                + str(
                    reference_target_consumption_payload.get("consumption_state", "")
                    or "<none>"
                ),
                "Next quality objective: "
                + str(next_objective_payload.get("objective_id", "") or "<none>"),
                "Next recommended skill pack: "
                + str(next_pack_plan.get("selected_skill_pack_id", "") or "<none>"),
            ],
        }

    def export_acceptance_evidence(self) -> dict[str, str]:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        markdown_path = self.evidence_root / f"web_acceptance_snapshot_{timestamp}.md"
        json_path = self.evidence_root / f"web_acceptance_snapshot_{timestamp}.json"
        evidence = build_manual_acceptance_evidence(
            package_root=self.package_root,
            operator_root=self.operator_root,
            state_root=self.state_root,
            directive_file=self.directive_file or None,
        )
        write_manual_acceptance_report(output_path=markdown_path, evidence=evidence)
        json_path.write_text(_json_dump(evidence), encoding="utf-8")
        self.last_export_path = str(markdown_path)
        self.last_export_json_path = str(json_path)
        return {
            "markdown_path": str(markdown_path),
            "json_path": str(json_path),
            "markdown": render_manual_acceptance_markdown(evidence),
        }

    def launch(self, *, resume_mode: str, launch_action: str, state_root: str) -> dict[str, Any]:
        self.update_profile(
            state_root=state_root,
            resume_mode=resume_mode,
            launch_action=launch_action,
        )
        directive_file = self.directive_file if self.resume_mode == "new_bootstrap" else None
        try:
            result = launch_novali_main(
                package_root=self.package_root,
                operator_root=self.operator_root,
                directive_file=directive_file,
                state_root=self.state_root,
                launch_action=self.launch_action,
            )
            summary = build_launch_result_summary(result)
            self.last_action_summary = summary
            return {
                "ok": int(result.get("exit_code", 0) or 0) == 0,
                "headline": summary.get("headline", ""),
                "details": list(summary.get("details", [])),
                "summary": summary.get("summary", ""),
            }
        except OperatorLaunchRefusedError as exc:
            summary = build_launch_refusal_summary(str(exc), list(exc.errors))
            self.last_action_summary = summary
            return {
                "ok": False,
                "headline": summary.get("headline", ""),
                "details": list(summary.get("details", [])),
                "summary": summary.get("summary", ""),
            }

    def scaffold_download_payload(self) -> tuple[str, bytes]:
        payload = build_standalone_directive_payload(
            package_root=self.package_root,
            directive_id="directive_browser_template_v1",
            directive_text="Initialize NOVALI from the localhost browser operator surface.",
            clarified_intent_summary=(
                "Bootstrap novali-v5 through the canonical operator flow and preserve artifact-backed "
                "governance authority before execution."
            ),
        )
        text = _json_dump(payload)
        return ("novali_browser_directive_template.json", text.encode("utf-8"))

    def render_home_page(self, *, notice: dict[str, Any] | None = None) -> str:
        dashboard = self.current_dashboard_snapshot()
        operator_snapshot = self.current_operator_snapshot()
        readiness = self.current_launch_readiness()
        directive_summary = self.current_directive_summary()
        trusted_summary = render_trusted_sources_summary(dashboard)
        constraints_summary = render_constraints_summary(operator_snapshot)
        dashboard_summary = render_dashboard_summary(dashboard)
        sample_rows = self.sample_directives()
        runtime_defaults = dict(notice.get("runtime_form_override", {})) if notice else {}
        if not runtime_defaults:
            runtime_defaults = self.runtime_form_defaults()
        auto_continue_defaults = self.auto_continue_policy_defaults()
        attempted_runtime_summary = str(notice.get("attempted_runtime_summary", "")).strip() if notice else ""
        observability = self._observability_snapshot()
        observability_summary = "\n".join(
            [
                f"Directive ID: {observability.get('directive_id', '') or '<none>'}",
                f"Workspace ID: {observability.get('workspace_id', '') or '<none>'}",
                f"Current objective source: {observability.get('current_objective_source_kind', '') or '<none>'}",
                f"Current objective id: {observability.get('current_objective_id', '') or '<none>'}",
                f"Execution mode: {observability.get('execution_mode', '') or '<none>'}",
                f"Execution profile: {observability.get('execution_profile', '') or '<none>'}",
                f"Backend: {observability.get('backend_kind', '') or '<none>'}",
                f"Controller mode: {observability.get('controller_mode', '') or '<none>'}",
                f"Cycles completed: {observability.get('cycles_completed', 0)}",
                f"Cycle kind: {observability.get('cycle_kind', '') or '<none>'}",
                f"Run status: {observability.get('run_status', '') or '<none>'}",
                f"Stop reason: {observability.get('stop_reason', '') or '<none>'}",
                f"Next recommended cycle: {observability.get('next_recommended_cycle', '') or '<none>'}",
                "Reference target consumption: "
                + str(
                    observability.get("reference_target_consumption_state", "")
                    or "<none>"
                ),
                "Active bounded reference target: "
                + str(
                    observability.get("active_bounded_reference_target_id", "")
                    or "<none>"
                ),
                "Protected live baseline: "
                + str(
                    observability.get("protected_live_baseline_reference_id", "")
                    or "<none>"
                ),
                "Quality composite state: "
                + str(observability.get("quality_composite_state", "") or "<none>"),
                "Weakest dimension: "
                + str(observability.get("quality_weakest_dimension_id", "") or "<none>"),
                "Next recommended pack: "
                + str(observability.get("quality_next_pack_id", "") or "<none>"),
                f"Reseed state: {observability.get('reseed_state', '') or '<none>'}",
                f"Continuation authorized: {bool(observability.get('continuation_authorized', False))}",
                f"Effective next objective: {observability.get('effective_next_objective_id', '') or '<none>'}",
                f"Auto-continue enabled: {bool(observability.get('auto_continue_enabled', False))}",
                f"Auto-continue chain: {int(observability.get('auto_continue_chain_count', 0) or 0)}/{int(observability.get('auto_continue_chain_cap', 1) or 1)}",
                f"Auto-continue last reason: {observability.get('auto_continue_last_reason', '') or '<none>'}",
                f"Auto-continue transition: {observability.get('auto_continue_transition_state', '') or '<none>'}",
                f"Workspace root: {observability.get('workspace_root', '') or '<none>'}",
            ]
        )
        continuation_summary = "\n".join(
            [
                f"Review status: {observability.get('review_status', '') or '<none>'}",
                f"Promotion recommendation: {observability.get('promotion_recommendation_state', '') or '<none>'}",
                f"Next objective proposal: {observability.get('next_objective_id', '') or '<none>'}",
                f"Reseed state: {observability.get('reseed_state', '') or '<none>'}",
                f"Continuation authorized: {bool(observability.get('continuation_authorized', False))}",
                f"Effective next objective: {observability.get('effective_next_objective_id', '') or '<none>'}",
                f"Reseed request artifact: {observability.get('reseed_request_path', '') or '<none>'}",
                f"Reseed decision artifact: {observability.get('reseed_decision_path', '') or '<none>'}",
                f"Continuation lineage artifact: {observability.get('continuation_lineage_path', '') or '<none>'}",
                f"Effective objective artifact: {observability.get('effective_next_objective_path', '') or '<none>'}",
                f"Auto-continue enabled: {bool(observability.get('auto_continue_enabled', False))}",
                f"Auto-continue allowed classes: {', '.join(list(observability.get('auto_continue_allowed_objective_classes', []))) or '<none>'}",
                f"Auto-continue chain count/cap: {int(observability.get('auto_continue_chain_count', 0) or 0)}/{int(observability.get('auto_continue_chain_cap', 1) or 1)}",
                f"Auto-continue reason: {observability.get('auto_continue_last_reason', '') or '<none>'}",
                f"Auto-continue origin: {observability.get('auto_continue_last_origin', '') or '<none>'}",
                f"Auto-continue transition: {observability.get('auto_continue_transition_state', '') or '<none>'}",
                f"Same-session cycle started: {bool(observability.get('auto_continue_transition_executed_in_session', False))}",
                f"Transition lineage: {observability.get('auto_continue_transition_from_objective_id', '') or '<none>'} -> {observability.get('auto_continue_transition_to_objective_id', '') or '<none>'}",
                f"Auto-continue transition artifact: {observability.get('auto_continue_transition_path', '') or '<none>'}",
                f"Auto-continue state artifact: {observability.get('auto_continue_state_path', '') or '<none>'}",
                f"Auto-continue decision artifact: {observability.get('auto_continue_decision_path', '') or '<none>'}",
            ]
        )
        baseline_admission_summary = "\n".join(
            [
                f"Admission review: {observability.get('baseline_admission_review_state', '') or '<none>'}",
                "Admission recommendation: "
                + str(
                    observability.get("baseline_admission_recommendation_state", "") or "<none>"
                ),
                f"Admission decision: {observability.get('baseline_admission_decision_state', '') or '<none>'}",
                "Admitted bounded baseline candidate: "
                + str(bool(observability.get("baseline_candidate_admitted", False))),
                "Remediation objective: "
                + str(observability.get("baseline_remediation_objective_id", "") or "<none>"),
                "Admission review artifact: "
                + str(observability.get("baseline_admission_review_path", "") or "<none>"),
                "Admission recommendation artifact: "
                + str(
                    observability.get("baseline_admission_recommendation_path", "")
                    or "<none>"
                ),
                "Admission decision artifact: "
                + str(observability.get("baseline_admission_decision_path", "") or "<none>"),
                "Remediation proposal artifact: "
                + str(
                    observability.get("baseline_remediation_proposal_path", "")
                    or "<none>"
                ),
            ]
        )
        admitted_candidate_summary = "\n".join(
            [
                "Admitted candidate state: "
                + str(observability.get("admitted_candidate_state", "") or "<none>"),
                "Candidate handoff state: "
                + str(
                    observability.get("admitted_candidate_handoff_state", "") or "<none>"
                ),
                "Handoff ready: "
                + str(bool(observability.get("admitted_candidate_handoff_ready", False))),
                "Baseline comparison: "
                + str(
                    observability.get("baseline_comparison_result_state", "")
                    or "<none>"
                ),
                "Stronger than current bounded baseline: "
                + str(
                    bool(
                        observability.get(
                            "stronger_than_current_bounded_baseline",
                            False,
                        )
                    )
                ),
                "Future reference target: "
                + str(
                    observability.get("future_reference_target_state", "")
                    or "<none>"
                ),
                "Reference target consumption: "
                + str(
                    observability.get("reference_target_consumption_state", "")
                    or "<none>"
                ),
                "Active bounded reference target: "
                + str(
                    observability.get("active_bounded_reference_target_id", "")
                    or "<none>"
                ),
                "Protected live baseline: "
                + str(
                    observability.get("protected_live_baseline_reference_id", "")
                    or "<none>"
                ),
                "Fallback reason: "
                + str(
                    observability.get("reference_target_fallback_reason", "")
                    or "<none>"
                ),
                "Preferred reference target: "
                + str(observability.get("future_reference_target_id", "") or "<none>"),
                "Revised candidate state: "
                + str(observability.get("revised_candidate_state", "") or "<none>"),
                "Revised candidate id: "
                + str(observability.get("revised_candidate_id", "") or "<none>"),
                "Revised candidate prior admitted candidate: "
                + str(
                    observability.get(
                        "revised_candidate_prior_admitted_candidate_id",
                        "",
                    )
                    or "<none>"
                ),
                "Revised candidate materially stronger in aggregate: "
                + str(
                    bool(
                        observability.get(
                            "revised_candidate_materially_stronger_in_aggregate",
                            False,
                        )
                    )
                ),
                "Reference target rollover: "
                + str(
                    observability.get("revised_candidate_reference_rollover_state", "")
                    or "<none>"
                ),
                "Comparison remediation objective: "
                + str(
                    observability.get("comparison_remediation_objective_id", "")
                    or "<none>"
                ),
                "Admitted candidate artifact: "
                + str(observability.get("admitted_candidate_path", "") or "<none>"),
                "Candidate handoff artifact: "
                + str(
                    observability.get("admitted_candidate_handoff_path", "")
                    or "<none>"
                ),
                "Baseline comparison artifact: "
                + str(observability.get("baseline_comparison_path", "") or "<none>"),
                "Revised candidate bundle artifact: "
                + str(observability.get("revised_candidate_bundle_path", "") or "<none>"),
                "Revised candidate handoff artifact: "
                + str(observability.get("revised_candidate_handoff_path", "") or "<none>"),
                "Revised candidate comparison artifact: "
                + str(
                    observability.get("revised_candidate_comparison_path", "")
                    or "<none>"
                ),
                "Revised candidate promotion summary artifact: "
                + str(
                    observability.get(
                        "revised_candidate_promotion_summary_path",
                        "",
                    )
                    or "<none>"
                ),
                "Reference target artifact: "
                + str(observability.get("reference_target_path", "") or "<none>"),
                "Reference target consumption artifact: "
                + str(
                    observability.get("reference_target_consumption_path", "")
                    or "<none>"
                ),
            ]
        )
        quality_roadmap_summary = "\n".join(
            [
                "Composite quality state: "
                + str(observability.get("quality_composite_state", "") or "<none>"),
                "Materially stronger than reference target in aggregate: "
                + str(
                    bool(
                        observability.get(
                            "materially_stronger_than_reference_target_in_aggregate",
                            False,
                        )
                    )
                ),
                "Weakest dimension: "
                + str(observability.get("quality_weakest_dimension_id", "") or "<none>"),
                "Weakest dimension title: "
                + str(
                    observability.get("quality_weakest_dimension_title", "")
                    or "<none>"
                ),
                "Next recommended skill pack: "
                + str(observability.get("quality_next_pack_id", "") or "<none>"),
                "Next recommended objective: "
                + str(observability.get("quality_next_objective_id", "") or "<none>"),
                "Next dimension: "
                + str(observability.get("quality_next_dimension_id", "") or "<none>"),
                "Roadmap artifact: "
                + str(observability.get("quality_roadmap_path", "") or "<none>"),
                "Priority matrix: "
                + str(
                    observability.get("quality_priority_matrix_path", "") or "<none>"
                ),
                "Composite evaluation: "
                + str(
                    observability.get("quality_composite_evaluation_path", "")
                    or "<none>"
                ),
                "Next-pack plan: "
                + str(
                    observability.get("quality_next_pack_plan_path", "") or "<none>"
                ),
            ]
        )
        handoff_manifest_path = _normalize_path(self.package_root / "handoff_layout_manifest.json")
        image_manifest_path = _normalize_path(self.package_root / "image" / "image_archive_manifest.json")
        packaged_handoff_context = self.is_packaged_handoff_context()
        packaged_backend_guidance = (
            "Open Runtime Constraints And Envelope, keep backend <code>local_guarded</code> for the packaged "
            "single-container handoff, choose the execution profile you intend to use, then save runtime policy."
            if packaged_handoff_context
            else "Open <a href=\"#runtime-section\">Runtime Constraints And Envelope</a>, keep backend "
            "<code>local_docker</code> for the packaged Docker path, choose the execution profile you intend to use, "
            "then save runtime policy."
        )
        runtime_section_guidance = (
            "Launch uses the saved operator runtime policy only. In the packaged single-container handoff, "
            "keep backend <code>local_guarded</code> because the current container already provides the Docker "
            "execution envelope. Use <code>local_docker</code> only from an operator environment with direct Docker "
            "access. Unsupported controls remain unsupported and are shown for honesty only. The coding profile "
            "enables writes only inside <code>novali-active_workspace</code> plus approved generated/log roots; it "
            "does not grant broad repo mutation."
            if packaged_handoff_context
            else "Launch uses the saved operator runtime policy only. For the packaged Docker path, keep backend "
            "<code>local_docker</code>, keep the packaged image tag unless you have a deliberate replacement, and "
            "save this form before launching if you change any values. Unsupported controls remain unsupported and "
            "are shown for honesty only. The coding profile enables writes only inside "
            "<code>novali-active_workspace</code> plus approved generated/log roots; it does not grant broad repo "
            "mutation."
        )
        notice_block = ""
        if notice:
            headline = html.escape(str(notice.get("headline", "")))
            details = list(notice.get("details", []))
            notice_block = (
                "<section class='notice card'>"
                f"<h2>{headline}</h2>"
                + ("<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in details) + "</ul>" if details else "")
                + "</section>"
            )
        sample_buttons = "".join(
            "<form method='post' action='/directive/sample' class='inline-form'>"
            f"<input type='hidden' name='sample_path' value='{html.escape(row['path'])}' />"
            f"<button type='submit'>{html.escape(row['label'])}</button>"
            "</form>"
            for row in sample_rows
        ) or "<p>No packaged sample directives were found.</p>"
        directive_valid = bool(directive_summary.get("is_valid", False)) or self.resume_mode == "resume_existing"
        artifact_presence = dict(dashboard.get("artifact_presence", {}))
        launch_context = dict(dashboard.get("launch_context", {}))
        bootstrap_ready = bool(
            artifact_presence.get("canonical_state_available", False)
            or launch_context.get("effective_operator_session_valid", False)
        )
        governed_ready = bool(
            int(observability.get("cycles_completed", 0) or 0) > 0
            or str(observability.get("execution_mode", "")).strip()
            in {
                GOVERNED_EXECUTION_MODE_SINGLE_CYCLE,
                GOVERNED_EXECUTION_MODE_MULTI_CYCLE,
                "governed_execution",
            }
        )
        review_required = bool(observability.get("operator_review_required", False))
        directive_name = Path(self.directive_file).name if str(self.directive_file).strip() else "No directive loaded"
        directive_path_html = self._render_path_html(self.directive_file)
        workflow = _build_home_workflow_summary(
            resume_mode=self.resume_mode,
            launch_action=self.launch_action,
            directive_valid=directive_valid,
            bootstrap_ready=bootstrap_ready,
            governed_ready=governed_ready,
            review_required=review_required,
            continuation_authorized=bool(observability.get("continuation_authorized", False)),
            runtime_defaults=runtime_defaults,
            readiness=readiness,
            observability=observability,
            last_action_summary=self.last_action_summary,
        )
        hero_pills = "".join(
            [
                _render_state_pill("Startup mode", self.resume_mode, tone="info"),
                _render_state_pill("Launch action", self.launch_action, tone="info"),
                _render_state_pill("Execution profile", runtime_defaults.get("execution_profile", "") or "<none>"),
                _render_state_pill("Run status", observability.get("run_status", "") or "idle"),
                _render_state_pill("Review", observability.get("review_status", "") or "not_required"),
            ]
        )
        hero_metrics = "".join(
            [
                _render_metric_card(
                    "Current Workflow State",
                    workflow["workflow_state"],
                    detail=str(workflow["workflow_detail"]),
                    tone="info",
                ),
                _render_metric_card(
                    "What Changed",
                    workflow["recent_change"],
                    detail=str(workflow["recent_change_detail"]),
                    tone=_status_tone(workflow["recent_change"]),
                ),
                _render_metric_card(
                    "What To Do Next",
                    workflow["next_action_label"],
                    detail=str(workflow["next_action_detail"]),
                    tone="success" if readiness.get("can_launch", False) else "warning",
                ),
                _render_metric_card(
                    "Current Objective",
                    observability.get("current_objective_id", "") or observability.get("effective_next_objective_id", "") or "<none>",
                    detail=observability.get("current_objective_source_kind", "") or "No active bounded objective recorded.",
                ),
            ]
        )
        workflow_story_cards = "".join(
            [
                (
                    "<div class='story-card'>"
                    "<span class='label'>Waiting On</span>"
                    f"<span class='value'>{html.escape(_display_text(workflow['waiting_on']))}</span>"
                    f"<span class='detail'>{html.escape(_display_text(observability.get('run_status', '') or observability.get('review_status', '') or 'No bounded run recorded yet.'))}</span>"
                    "</div>"
                ),
                (
                    "<div class='story-card'>"
                    "<span class='label'>Selected Launch</span>"
                    f"<span class='value'>{html.escape(_display_text(workflow['selected_launch']))}</span>"
                    f"<span class='detail'>Saved execution profile: {html.escape(_display_text(workflow['selected_execution_profile']))}</span>"
                    "</div>"
                ),
                (
                    "<div class='story-card'>"
                    "<span class='label'>Runtime Policy Check</span>"
                    f"<span class='value'>{html.escape(_display_text(workflow['profile_alignment_label']))}</span>"
                    f"<span class='detail'>{html.escape(_display_text(workflow['profile_alignment_detail']))}</span>"
                    "</div>"
                ),
                (
                    "<div class='story-card'>"
                    "<span class='label'>Stable Reference</span>"
                    f"<span class='value'>{html.escape(_display_text(observability.get('active_bounded_reference_target_id', '') or '<none>'))}</span>"
                    "<span class='detail'>Protected live baseline remains unchanged.</span>"
                    "</div>"
                ),
            ]
        )
        directive_core_summary = _render_summary_rows(
            [
                ("Directive file", directive_path_html),
                ("Core state", html.escape(str(directive_summary.get("summary", "No directive selected.")))),
                (
                    "Runtime lane",
                    html.escape(
                        "bootstrap_only_initialization -> bounded_active_workspace_coding"
                        if packaged_handoff_context
                        else "local_docker or local_guarded with explicit saved runtime policy"
                    ),
                ),
                (
                    "Canonical chain",
                    "<code>operator shell -&gt; launcher -&gt; frozen session -&gt; bootstrap -&gt; governed execution</code>",
                ),
            ]
        )
        initialization_story = "".join(
            [
                _render_stage_step(
                    1,
                    "Directive selection / insertion",
                    "Use a formal directive wrapper. In resume mode, frozen session state can carry the prior directive forward.",
                    state=str(workflow["step_one_state"]),
                ),
                _render_stage_step(
                    2,
                    "Bootstrap-only initialization",
                    "First-time initialization is a separate step. Keep execution profile on bootstrap_only_initialization for new_bootstrap + bootstrap_only.",
                    state=str(workflow["step_two_state"]),
                ),
                _render_stage_step(
                    3,
                    "Transition to governed execution",
                    "After canonical state exists, restore bounded_active_workspace_coding before resume_existing + governed_execution.",
                    state=str(workflow["step_three_state"]),
                ),
                _render_stage_step(
                    4,
                    "Runtime / operator workflow",
                    "Review, admission, quality improvement, and observability all remain artifact-backed inside the same browser-first operator path.",
                    state=str(workflow["step_four_state"]),
                ),
            ]
        )
        launch_summary_rows = _render_summary_rows(
            [
                ("Selected launch", html.escape(str(workflow["selected_launch"]))),
                ("Launch readiness", html.escape(str(readiness.get("headline", "")))),
                ("Runtime policy check", html.escape(str(workflow["profile_alignment_label"]))),
                ("Operator next move", html.escape(str(workflow["next_action_label"]))),
                ("Waiting on", html.escape(str(workflow["waiting_on"]))),
                ("Blocking reasons", html.escape(", ".join(list(readiness.get("blocking_reasons", []))) or "<none>")),
                ("State root", html.escape(_normalize_path(self.state_root))),
            ]
        )
        observability_story_cards = "".join(
            [
                f"<div class='story-card'><span class='label'>Runtime mode</span><span class='value'>{html.escape(_display_text(observability.get('execution_mode', '') or '<none>'))}</span><span class='detail'>{html.escape(_display_text(observability.get('controller_mode', '') or '<none>'))}</span></div>",
                f"<div class='story-card'><span class='label'>What just happened</span><span class='value'>{html.escape(_display_text(observability.get('run_status', '') or '<none>'))}</span><span class='detail'>{html.escape(_display_text(observability.get('stop_reason', '') or observability.get('quality_improvement_state', '') or '<none>'))}</span></div>",
                f"<div class='story-card'><span class='label'>Campaign / cycle / loop</span><span class='value'>{html.escape(_display_text(observability.get('campaign_recommendation_state', '') or '<none>'))}</span><span class='detail'>{html.escape(_display_text(observability.get('campaign_cycle_recommendation_state', '') or observability.get('loop_recommendation_state', '') or '<none>'))}</span></div>",
                f"<div class='story-card'><span class='label'>Next recommendation</span><span class='value'>{html.escape(_display_text(observability.get('next_recommended_cycle', '') or '<none>'))}</span><span class='detail'>{html.escape(_display_text(observability.get('quality_next_pack_id', '') or observability.get('next_objective_id', '') or '<none>'))}</span></div>",
            ]
        )
        runtime_guidance_note = (
            "Packaged single-container note: the canonical flow may require saving "
            "bootstrap_only_initialization for new_bootstrap + bootstrap_only, then restoring "
            "bounded_active_workspace_coding before governed_execution."
            if packaged_handoff_context
            else "Operator note: save runtime policy before launch whenever you switch between bootstrap-only and governed execution."
        )
        workflow_guidance_note = (
            str(workflow["profile_alignment_detail"])
            if str(workflow["profile_alignment_detail"]).strip()
            else runtime_guidance_note
        )
        workflow_guidance_note_html = (
            runtime_guidance_note
            if workflow_guidance_note == runtime_guidance_note
            else html.escape(workflow_guidance_note)
        )
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>NOVALI Localhost Web Operator</title>
  {_shared_page_style()}
</head>
<body>
  <div class="page-shell">
    <header class="page-header">
      <span class="page-kicker">Operator Product Surface</span>
      <h1>NOVALI Localhost Web Operator</h1>
      <p class="page-subtitle">Local single-operator surface only. Default host launch binds to <code>127.0.0.1:{DEFAULT_WEB_PORT}</code>. Container wrappers may bind to <code>0.0.0.0</code> inside the container, but host exposure should stay mapped to localhost.</p>
      <p class="page-subtitle">Canonical authority remains unchanged: <code>operator shell -&gt; launcher -&gt; frozen session -&gt; bootstrap -&gt; governed execution</code>. This browser UI only drives that same path.</p>
      {_page_navigation("/")}
    </header>
    {notice_block}
    <section class="card hero-panel">
      <div class="hero-layout">
        <div class="hero-copy">
          <span class="eyebrow">Initialization Story</span>
          <h2>Directive core first, bounded operator workflow second</h2>
          <p>The interface now mirrors the real NOVALI startup model: directive selection, bootstrap-only initialization, transition to governed execution, then artifact-backed operator review and observability. Product polish changes the framing, not the authority model.</p>
          <div class="pill-row">{hero_pills}</div>
          <div class="signal-grid">{hero_metrics}</div>
        </div>
        <div class="directive-core-shell">
          <div class="directive-core-visual">
            <div class="core-ring"></div>
            <span class="core-sigil sigil-a">[]</span>
            <span class="core-sigil sigil-b">//</span>
            <span class="core-sigil sigil-c">::</span>
            <span class="core-sigil sigil-d">++</span>
            <div class="core-node">
              <span class="core-label">Directive Core</span>
              <span class="core-title">{html.escape(directive_name)}</span>
              <span class="core-detail">{html.escape("Core validated and ready." if directive_valid else "Insert a formal wrapper to bring NOVALI online.")}</span>
            </div>
          </div>
          {directive_core_summary}
        </div>
      </div>
    </section>
    <section class="card wide-card">
      <div class="dual-grid">
        <div>
          <div class="section-heading">
            <h2>First Run</h2>
            {_render_state_pill("Launch readiness", readiness.get("headline", "") or "unknown", tone="success" if readiness.get("can_launch", False) else "warning")}
          </div>
          <p>If you are using the packaged standalone handoff, start here. Initialize first with <code>new_bootstrap</code> plus launch action <code>bootstrap_only</code>. After canonical state exists, bounded coding runs should use <code>resume_existing</code> plus <code>governed_execution</code> with the <code>bounded_active_workspace_coding</code> profile. In <code>single_cycle</code> mode one invocation performs one bounded cycle and returns control. In <code>multi_cycle</code> mode one invocation may continue across several bounded cycles until a conservative directive-derived stop condition or cycle cap is reached.</p>
          <div class="stage-rail">{initialization_story}</div>
        </div>
        <div>
          <div class="section-heading">
            <h3>Workflow Guide</h3>
            {_render_state_pill("Waiting on", workflow["waiting_on"], tone=str(workflow["waiting_on_tone"]))}
          </div>
          <div class="operator-note {html.escape(str(workflow['policy_tone']))}"><strong>Operator guidance</strong><br/>{workflow_guidance_note_html}</div>
          <div class="story-grid" style="margin-top: 12px;">{workflow_story_cards}</div>
          <div class="operator-note info" style="margin-top: 12px;"><strong>Flow reminder</strong><br/>{runtime_guidance_note}</div>
          <div class="story-grid" style="margin-top: 12px;">
            <div class="story-card">
              <span class="label">Happy-path sample</span>
              <span class="value"><code>samples/directives/standalone_valid_directive.example.json</code></span>
              <span class="detail">Use the incomplete sample only when you want a clarification/refusal test.</span>
            </div>
            <div class="story-card">
              <span class="label">Package manifests</span>
              <span class="value"><code>handoff_layout_manifest.json</code></span>
              <span class="detail"><code>image_archive_manifest.json</code> ships alongside the packaged image bundle.</span>
            </div>
            <div class="story-card">
              <span class="label">Writable roots</span>
              <span class="value"><code>novali-active_workspace</code></span>
              <span class="detail">Writes stay bounded to the active workspace plus approved generated/log roots.</span>
            </div>
            <div class="story-card">
              <span class="label">Evidence capture</span>
              <span class="value"><code>runtime_data/acceptance_evidence/</code></span>
              <span class="detail">Use exports for packaged proof without creating a second authority path.</span>
            </div>
          </div>
          <div style="margin-top: 14px;">{launch_summary_rows}</div>
          <ol>
            <li>Select a directive to begin, or reuse a prior frozen session only when you intentionally resume an existing packaged state.</li>
            <li>{packaged_backend_guidance}</li>
            <li>If the selected action and saved runtime policy do not match, save Runtime Constraints And Envelope before you launch.</li>
            <li>Use <code>new_bootstrap + bootstrap_only</code> for canonical initialization, then switch back to <code>bounded_active_workspace_coding</code> before <code>resume_existing + governed_execution</code>.</li>
            <li>After launch, use Observability, Workspace, Timeline, and Cycle to confirm what changed and what the operator should do next.</li>
          </ol>
        </div>
      </div>
    </section>
    <div class="module-grid">
      <section class="card" id="status-section">
        <h2>Status</h2>
        <p><strong>Last action:</strong> {html.escape(str(self.last_action_summary.get('headline', 'No action yet.')))}</p>
        <pre>{html.escape(str(self.last_action_summary.get('summary', 'No action yet.')))}</pre>
        <p><strong>Package root:</strong> <span class="path">{html.escape(_normalize_path(self.package_root))}</span></p>
        <p><strong>State root:</strong> <span class="path">{html.escape(_normalize_path(self.state_root))}</span></p>
        <p><strong>Operator root:</strong> <span class="path">{html.escape(_normalize_path(self.operator_root))}</span></p>
        <p><strong>Acceptance evidence root:</strong> <span class="path">{html.escape(_normalize_path(self.evidence_root))}</span></p>
        <p><strong>Directive input root:</strong> <span class="path">{html.escape(_normalize_path(self.directive_root))}</span></p>
        <pre>{html.escape(dashboard_summary)}</pre>
      </section>
      <section class="card wide-card" id="observability-section">
        <div class="section-heading">
          <h2>Observability And Spot Check</h2>
          {_render_state_pill("Cycles completed", observability.get("cycles_completed", 0) or 0, tone="info")}
        </div>
        <p>The browser can now surface the latest cycle, workspace artifacts, and runtime timeline directly from persisted files. This remains read-only and artifact-backed.</p>
        <div class="section-links">
          <a href="/observability">Latest run overview</a>
          <a href="/workspace">Workspace artifacts</a>
          <a href="/timeline">Runtime timeline</a>
          <a href="/cycle">Latest cycle summary</a>
        </div>
        <p><strong>Current model:</strong> controller mode and stop reason are shown below. <code>single_cycle</code> runs one bounded cycle per invocation; <code>multi_cycle</code> may continue through several bounded cycles until completion, no-work, failure, or cap.</p>
        <div class="story-grid">{observability_story_cards}</div>
        <pre>{html.escape(observability_summary)}</pre>
      </section>
    <section class="card" id="continuation-section">
      <h2>Review, Reseed, And Continuation</h2>
      <p>When bounded successor work completes, NOVALI writes a reviewed next-objective proposal. Manual approve, defer, and reject remain available. If you explicitly enable auto-continue policy for an already-approved objective class, the system may materialize the next bounded objective without another approval click, but it still records explicit lineage, caps, and stop reasons.</p>
      <p><strong>Current continuation state</strong></p>
      <pre>{html.escape(continuation_summary)}</pre>
      <form method="post" action="/reseed/decision">
        <label for="operator_note">Operator note (optional)</label>
        <textarea id="operator_note" name="operator_note" rows="3" placeholder="Short review note or rationale"></textarea>
        <div class="inline-actions">
          <button type="submit" name="decision" value="approve">Approve Proposal</button>
          <button type="submit" name="decision" value="approve_and_continue">Approve And Continue</button>
          <button type="submit" name="decision" value="defer">Defer</button>
          <button type="submit" name="decision" value="reject">Reject</button>
        </div>
      </form>
      <p class="muted">This is not a second authority path. It records an operator-reviewed decision into bounded workspace artifacts, and any continuation launch still goes through the existing launcher, frozen session, and governed execution chain.</p>
    </section>
    <section class="card" id="baseline-admission-section">
      <h2>Candidate Admission</h2>
      <p>When a candidate promotion bundle exists, NOVALI now writes a conservative baseline-admission review. This pass does not mutate any live baseline or protected surface. It only records whether the candidate is review-required, recommended, deferred, rejected for remediation, or marked as an admitted bounded baseline candidate.</p>
      <p><strong>Current admission state</strong></p>
      <pre>{html.escape(baseline_admission_summary)}</pre>
      <form method="post" action="/admission/decision">
        <label for="admission_operator_note">Operator note (optional)</label>
        <textarea id="admission_operator_note" name="operator_note" rows="3" placeholder="Short admission rationale or remediation note"></textarea>
        <div class="inline-actions">
          <button type="submit" name="decision" value="approve">Approve Baseline Candidate</button>
          <button type="submit" name="decision" value="defer">Defer</button>
          <button type="submit" name="decision" value="reject">Reject / Require Remediation</button>
        </div>
      </form>
      <p class="muted">Approval here only marks an admitted bounded baseline candidate in artifact-backed review state. It does not replace the live baseline, mutate protected surfaces, or bypass operator governance.</p>
    </section>
    <section class="card" id="candidate-lifecycle-section">
      <h2>Admitted Candidate Lifecycle</h2>
      <p>Once admission is approved, NOVALI preserves the candidate as a bounded handoff artifact, compares it against the current bounded baseline rubric, and records whether it is safe to use as a future bounded reference target. This still does not replace the live or protected baseline.</p>
      <pre>{html.escape(admitted_candidate_summary)}</pre>
    </section>
    <section class="card" id="quality-roadmap-section">
      <h2>Successor Quality Roadmap</h2>
      <p>NOVALI now records a bounded roadmap, priority matrix, composite evaluation, and next-pack plan so multi-pack quality improvement stays explicit and operator-auditable.</p>
      <pre>{html.escape(quality_roadmap_summary)}</pre>
    </section>
    <section class="card" id="auto-continue-section">
      <h2>Auto-Continue Policy</h2>
      <p>This is operator-owned friction reduction only. It never enables endless continuity, it never expands permissions, and it only applies to whitelisted objective classes inside the existing bounded workspace model. If a proposal is ineligible, NOVALI falls back to explicit review.</p>
      <form method="post" action="/auto-continue/save">
        <label>Enabled</label>
        <select name="enabled">
          <option value="false"{" selected" if auto_continue_defaults["enabled"] == "false" else ""}>false</option>
          <option value="true"{" selected" if auto_continue_defaults["enabled"] == "true" else ""}>true</option>
        </select>
        <label>Allowed objective classes (; separated)</label>
        <input type="text" name="allowed_objective_classes" value="{html.escape(auto_continue_defaults['allowed_objective_classes'])}" />
        <label>Max auto-continue chain length</label>
        <input type="number" name="max_auto_continue_chain_length" value="{html.escape(auto_continue_defaults['max_auto_continue_chain_length'])}" />
        <label>Manual approval required for first entry into a class</label>
        <select name="require_manual_approval_for_first_entry">
          <option value="true"{" selected" if auto_continue_defaults["require_manual_approval_for_first_entry"] == "true" else ""}>true</option>
          <option value="false"{" selected" if auto_continue_defaults["require_manual_approval_for_first_entry"] == "false" else ""}>false</option>
        </select>
        <label>Require review-supported proposals</label>
        <select name="require_review_supported_proposals">
          <option value="true"{" selected" if auto_continue_defaults["require_review_supported_proposals"] == "true" else ""}>true</option>
          <option value="false"{" selected" if auto_continue_defaults["require_review_supported_proposals"] == "false" else ""}>false</option>
        </select>
        <button type="submit">Save Auto-Continue Policy</button>
      </form>
      <p><strong>Available objective classes</strong></p>
      <pre>{html.escape(chr(10).join(AUTO_CONTINUE_OBJECTIVE_CLASSES))}</pre>
    </section>
    <section class="card" id="directive-section">
      <h2>Directive</h2>
      <p>Use a formal directive wrapper only. For a first packaged validation run, start with the valid sample below or download a scaffold. Guide: <code>DIRECTIVE_AUTHORING_GUIDE.md</code>. Template download: <a href="/directive/download-scaffold">novali_browser_directive_template.json</a></p>
      <form method="post" action="/directive/select">
        <label for="directive_path">Selected directive file</label>
        <input id="directive_path" type="text" name="directive_path" value="{html.escape(self.directive_file)}" />
        <button type="submit">Use Directive Path</button>
      </form>
      <form method="post" action="/directive/upload" enctype="multipart/form-data">
        <label for="directive_upload">Upload directive JSON</label>
        <input id="directive_upload" type="file" name="directive_upload" accept=".json,application/json" />
        <button type="submit">Upload Directive</button>
      </form>
      <div><label>Packaged samples</label>{sample_buttons}</div>
      <pre>{html.escape(str(directive_summary.get('summary', 'No directive selected.')))}</pre>
    </section>
    <section class="card" id="trusted-sources-section">
      <h2>Trusted Sources</h2>
      <p>Bindings and secrets remain outside directive authority. For packaged standalone validation, prefer placeholder or disabled network bindings unless you intentionally provide local credentials. This slice shows the persisted summary and safe guidance only; it does not add a second secret-authoring path.</p>
      <p>Bindings file: <code>{html.escape(str(operator_snapshot.get('trusted_source_bindings_path', '')))}</code><br/>Local secrets file: <code>{html.escape(str(operator_snapshot.get('trusted_source_secrets_path', '')))}</code><br/>Environment template: <code>standalone_docker/standalone.env.template</code></p>
      <pre>{html.escape(trusted_summary)}</pre>
    </section>
    <section class="card" id="runtime-section">
      <h2>Runtime Constraints And Envelope</h2>
      <p>{runtime_section_guidance}</p>
      <div class="operator-note {html.escape(str(workflow['policy_tone']))}"><strong>Runtime policy check</strong><br/>{html.escape(str(workflow['profile_alignment_label']))} {html.escape(str(workflow['profile_alignment_detail']))}</div>
      <form method="post" action="/runtime/save">
        <label>Execution profile</label>
        <select name="execution_profile">
          <option value="{EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION}"{" selected" if runtime_defaults["execution_profile"] == EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION else ""}>{EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION}</option>
          <option value="{EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING}"{" selected" if runtime_defaults["execution_profile"] == EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING else ""}>{EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING}</option>
        </select>
        <label>Workspace id</label><input type="text" name="workspace_id" value="{html.escape(runtime_defaults['workspace_id'])}" />
        <label>Active workspace root</label><input type="text" name="workspace_root" value="{html.escape(runtime_defaults['workspace_root'])}" readonly />
        <label>Generated output root</label><input type="text" name="generated_output_root" value="{html.escape(runtime_defaults['generated_output_root'])}" readonly />
        <label>Protected roots (summary)</label><input type="text" name="protected_root_hints" value="{html.escape(runtime_defaults['protected_root_hints'])}" readonly />
        <label>Max memory (MB)</label><input type="number" name="max_memory_mb" value="{html.escape(runtime_defaults['max_memory_mb'])}" />
        <label>Max Python threads</label><input type="number" name="max_python_threads" value="{html.escape(runtime_defaults['max_python_threads'])}" />
        <label>Max child processes</label><input type="number" name="max_child_processes" value="{html.escape(runtime_defaults['max_child_processes'])}" />
        <label>Subprocess mode</label>
        <select name="subprocess_mode">
          <option value="disabled"{" selected" if runtime_defaults["subprocess_mode"] == "disabled" else ""}>disabled</option>
          <option value="bounded"{" selected" if runtime_defaults["subprocess_mode"] == "bounded" else ""}>bounded</option>
          <option value="allow"{" selected" if runtime_defaults["subprocess_mode"] == "allow" else ""}>allow</option>
        </select>
        <label>Working directory</label><input type="text" name="working_directory" value="{html.escape(runtime_defaults['working_directory'])}" readonly />
        <label>Allowed write roots (; separated)</label><input type="text" name="allowed_write_roots" value="{html.escape(runtime_defaults['allowed_write_roots'])}" readonly />
        <label>Session time limit (seconds)</label><input type="number" name="session_time_limit_seconds" value="{html.escape(runtime_defaults['session_time_limit_seconds'])}" />
        <label>Governed execution mode</label>
        <select name="governed_execution_mode">
          <option value="{GOVERNED_EXECUTION_MODE_SINGLE_CYCLE}"{" selected" if runtime_defaults["governed_execution_mode"] == GOVERNED_EXECUTION_MODE_SINGLE_CYCLE else ""}>{GOVERNED_EXECUTION_MODE_SINGLE_CYCLE}</option>
          <option value="{GOVERNED_EXECUTION_MODE_MULTI_CYCLE}"{" selected" if runtime_defaults["governed_execution_mode"] == GOVERNED_EXECUTION_MODE_MULTI_CYCLE else ""}>{GOVERNED_EXECUTION_MODE_MULTI_CYCLE}</option>
        </select>
        <label>Max cycles per invocation</label><input type="number" name="max_cycles_per_invocation" value="{html.escape(runtime_defaults['max_cycles_per_invocation'])}" />
        <label>Runtime backend</label>
        <select name="backend_kind">
          <option value="{BACKEND_LOCAL_GUARDED}"{" selected" if runtime_defaults["backend_kind"] == BACKEND_LOCAL_GUARDED else ""}>{BACKEND_LOCAL_GUARDED}</option>
          <option value="{BACKEND_LOCAL_DOCKER}"{" selected" if runtime_defaults["backend_kind"] == BACKEND_LOCAL_DOCKER else ""}>{BACKEND_LOCAL_DOCKER}</option>
        </select>
        <label>Docker CPU limit (cpus)</label><input type="text" name="cpu_limit_cpus" value="{html.escape(runtime_defaults['cpu_limit_cpus'])}" />
        <label>Docker image</label><input type="text" name="docker_image" value="{html.escape(runtime_defaults['docker_image'])}" />
        <label>Network policy intent</label>
        <select name="network_policy_intent">
          <option value="deny_all"{" selected" if runtime_defaults["network_policy_intent"] == "deny_all" else ""}>deny_all</option>
        </select>
        <button type="submit">Save Runtime Policy</button>
      </form>
      {("<p><strong>Attempted runtime policy (not saved)</strong></p><pre>" + html.escape(attempted_runtime_summary) + "</pre>") if attempted_runtime_summary else ""}
      <p><strong>Persisted runtime policy summary</strong></p>
      <pre>{html.escape(constraints_summary)}</pre>
    </section>
    <section class="card" id="launch-section">
      <h2>Launch / Resume</h2>
      <p>Recommended first launch: <code>new_bootstrap</code> + <code>bootstrap_only</code>. Use <code>resume_existing</code> only after a successful prior launch created persisted state and a frozen operator session. Use <code>governed_execution</code> when you want post-bootstrap governed work; the bounded coding profile is intended for that path. In <code>single_cycle</code> mode, a planning-only cycle requires a later <code>governed_execution</code> invocation to advance. In <code>multi_cycle</code> mode, the controller may continue through several bounded cycles until a conservative stop reason is reached.</p>
      <div class="operator-note {html.escape(str(workflow['policy_tone']))}"><strong>Before you launch</strong><br/>{html.escape(str(workflow['next_action_label']))}: {html.escape(str(workflow['next_action_detail']))}</div>
      <form method="post" action="/launch">
        <label>State root</label><input type="text" name="state_root" value="{html.escape(_normalize_path(self.state_root))}" />
        <label>Startup mode</label>
        <select name="resume_mode">
          <option value="new_bootstrap"{" selected" if self.resume_mode == "new_bootstrap" else ""}>new_bootstrap</option>
          <option value="resume_existing"{" selected" if self.resume_mode == "resume_existing" else ""}>resume_existing</option>
        </select>
        <label>Launch action</label>
        <select name="launch_action">
          <option value="bootstrap_only"{" selected" if self.launch_action == "bootstrap_only" else ""}>bootstrap_only</option>
          <option value="governed_execution"{" selected" if self.launch_action == "governed_execution" else ""}>governed_execution</option>
          <option value="proposal_analytics"{" selected" if self.launch_action == "proposal_analytics" else ""}>proposal_analytics</option>
          <option value="proposal_recommend"{" selected" if self.launch_action == "proposal_recommend" else ""}>proposal_recommend</option>
        </select>
        <button type="submit">Run Selected Launch Action</button>
      </form>
      <pre>{html.escape(render_launch_readiness(readiness=readiness))}</pre>
    </section>
    <section class="card" id="evidence-section">
      <h2>Acceptance Evidence</h2>
      <p>Exports remain non-authoritative and are written under the operator-visible evidence root. Use them to capture the packaged happy path, refusal path, and any restart evidence without creating a second authority path.</p>
      <form method="post" action="/export"><button type="submit">Export Acceptance Snapshot</button></form>
      <p><strong>Last markdown export:</strong> <span class="path">{html.escape(self.last_export_path or '<none>')}</span></p>
      <p><strong>Last JSON export:</strong> <span class="path">{html.escape(self.last_export_json_path or '<none>')}</span></p>
      <p><strong>Package manifest:</strong> <span class="path">{html.escape(handoff_manifest_path)}</span></p>
      <p><strong>Image manifest:</strong> <span class="path">{html.escape(image_manifest_path)}</span></p>
    </section>
  </div>
  </div>
</body>
</html>"""


def _html_response(handler: BaseHTTPRequestHandler, body: str, *, status: HTTPStatus = HTTPStatus.OK) -> None:
    payload = body.encode("utf-8")
    handler.send_response(int(status))
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _download_response(
    handler: BaseHTTPRequestHandler,
    *,
    filename: str,
    content_type: str,
    payload: bytes,
) -> None:
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _parse_urlencoded(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length).decode("utf-8")
    parsed = urllib.parse.parse_qs(raw, keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _parse_multipart(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    content_type = str(handler.headers.get("Content-Type", ""))
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length)
    if not raw or "multipart/form-data" not in content_type.lower():
        return {}
    header_block = (
        f"Content-Type: {content_type}\r\n"
        "MIME-Version: 1.0\r\n"
        "\r\n"
    ).encode("utf-8")
    form = BytesParser(policy=email_policy).parsebytes(header_block + raw)
    parsed: dict[str, Any] = {}
    if form.is_multipart():
        for field in form.iter_parts():
            field_name = str(field.get_param("name", header="content-disposition") or "").strip()
            if not field_name:
                continue
            filename = field.get_filename()
            payload = field.get_payload(decode=True) or b""
            if filename:
                parsed[field_name] = {
                    "filename": str(filename),
                    "value": payload,
                }
            else:
                charset = field.get_content_charset() or "utf-8"
                parsed[field_name] = payload.decode(charset, errors="replace")
    return parsed


def build_operator_web_app(
    *,
    package_root: str | Path | None = None,
    operator_root: str | Path | None = None,
    state_root: str | Path | None = None,
) -> OperatorWebService:
    return OperatorWebService(package_root=package_root, operator_root=operator_root, state_root=state_root)


def make_operator_web_handler(service: OperatorWebService) -> type[BaseHTTPRequestHandler]:
    class OperatorWebHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urllib.parse.urlsplit(self.path)
            route = parsed.path or "/"
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            if route == "/":
                _html_response(self, service.render_home_page())
                return
            if route == "/observability":
                _html_response(self, service.render_observability_page())
                return
            if route == "/workspace":
                _html_response(self, service.render_workspace_page())
                return
            if route == "/timeline":
                _html_response(self, service.render_timeline_page())
                return
            if route == "/cycle":
                _html_response(self, service.render_cycle_summary_page())
                return
            if route == "/preview":
                _html_response(
                    self,
                    service.render_preview_page(
                        str(query.get("path", [""])[-1] if query.get("path") else "")
                    ),
                )
                return
            if route == "/healthz":
                _download_response(
                    self,
                    filename="healthz.txt",
                    content_type="text/plain; charset=utf-8",
                    payload=b"ok\n",
                )
                return
            if route == "/directive/download-scaffold":
                filename, payload = service.scaffold_download_payload()
                _download_response(
                    self,
                    filename=filename,
                    content_type="application/json; charset=utf-8",
                    payload=payload,
                )
                return
            _html_response(
                self,
                service.render_home_page(
                    notice={
                        "headline": "Requested page was not found.",
                        "details": [self.path],
                    }
                ),
                status=HTTPStatus.NOT_FOUND,
            )

        def do_POST(self) -> None:
            path = self.path
            with service._lock:
                if path == "/directive/select":
                    form = _parse_urlencoded(self)
                    service.update_profile(directive_file=str(form.get("directive_path", "")), resume_mode="new_bootstrap")
                    _html_response(
                        self,
                        service.render_home_page(
                            notice={
                                "headline": "Directive selection updated.",
                                "details": [str(service.current_directive_summary().get("summary", ""))],
                            }
                        ),
                    )
                    return
                if path == "/directive/sample":
                    form = _parse_urlencoded(self)
                    sample_path = str(form.get("sample_path", "")).strip()
                    service.select_sample_directive(sample_path)
                    _html_response(
                        self,
                        service.render_home_page(
                            notice={
                                "headline": "Sample directive selected.",
                                "details": [sample_path],
                            }
                        ),
                    )
                    return
                if path == "/directive/upload":
                    form = _parse_multipart(self)
                    upload = dict(form.get("directive_upload", {}))
                    if not upload:
                        notice = {
                            "headline": "No directive file was uploaded.",
                            "details": ["Choose a JSON file before submitting the upload form."],
                        }
                    else:
                        target = service.save_uploaded_directive(
                            filename=str(upload.get("filename", "")),
                            payload=bytes(upload.get("value", b"")),
                        )
                        notice = {
                            "headline": "Directive uploaded.",
                            "details": [str(target)],
                        }
                    _html_response(self, service.render_home_page(notice=notice))
                    return
                if path == "/runtime/save":
                    form = _parse_urlencoded(self)
                    result = service.save_runtime_policy(form)
                    _html_response(self, service.render_home_page(notice=result))
                    return
                if path == "/auto-continue/save":
                    form = _parse_urlencoded(self)
                    result = service.save_auto_continue_policy(form)
                    _html_response(self, service.render_home_page(notice=result))
                    return
                if path == "/reseed/decision":
                    form = _parse_urlencoded(self)
                    raw_decision = str(form.get("decision", "")).strip().lower()
                    continue_after_approval = raw_decision == "approve_and_continue"
                    decision = "approve" if continue_after_approval else raw_decision
                    result = service.decide_reseed(
                        operator_decision=decision,
                        operator_note=str(form.get("operator_note", "")),
                        continue_after_approval=continue_after_approval,
                    )
                    _html_response(self, service.render_home_page(notice=result))
                    return
                if path == "/admission/decision":
                    form = _parse_urlencoded(self)
                    result = service.decide_baseline_admission(
                        operator_decision=str(form.get("decision", "")),
                        operator_note=str(form.get("operator_note", "")),
                    )
                    _html_response(self, service.render_home_page(notice=result))
                    return
                if path == "/launch":
                    form = _parse_urlencoded(self)
                    result = service.launch(
                        resume_mode=str(form.get("resume_mode", "new_bootstrap")),
                        launch_action=str(form.get("launch_action", "bootstrap_only")),
                        state_root=str(form.get("state_root", _normalize_path(service.state_root))),
                    )
                    _html_response(self, service.render_home_page(notice=result))
                    return
                if path == "/export":
                    exported = service.export_acceptance_evidence()
                    _download_response(
                        self,
                        filename=Path(exported["markdown_path"]).name,
                        content_type="text/markdown; charset=utf-8",
                        payload=exported["markdown"].encode("utf-8"),
                    )
                    return
            _html_response(
                self,
                service.render_home_page(
                    notice={
                        "headline": "Requested action was not found.",
                        "details": [path],
                    }
                ),
                status=HTTPStatus.NOT_FOUND,
            )

    return OperatorWebHandler


def make_operator_web_server(
    *,
    service: OperatorWebService,
    host: str,
    port: int,
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, int(port)), make_operator_web_handler(service))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Localhost browser-based operator surface for novali-v5. "
            "This server remains a thin surface over the existing launcher/frozen-session/bootstrap flow."
        )
    )
    parser.add_argument("--host", default=os.environ.get("NOVALI_WEB_HOST", DEFAULT_WEB_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("NOVALI_WEB_PORT", str(DEFAULT_WEB_PORT))))
    parser.add_argument("--package-root", default=os.environ.get("NOVALI_PACKAGE_ROOT", ""))
    parser.add_argument("--operator-root", default=os.environ.get("NOVALI_OPERATOR_ROOT", ""))
    parser.add_argument("--state-root", default=os.environ.get("NOVALI_STATE_ROOT", ""))
    args = parser.parse_args()

    package_root = Path(str(args.package_root).strip()) if str(args.package_root).strip() else Path(__file__).resolve().parents[1]
    operator_root = Path(str(args.operator_root).strip()) if str(args.operator_root).strip() else default_operator_root()
    state_root = Path(str(args.state_root).strip()) if str(args.state_root).strip() else default_web_state_root(package_root)

    service = build_operator_web_app(
        package_root=package_root,
        operator_root=operator_root,
        state_root=state_root,
    )
    server = make_operator_web_server(service=service, host=str(args.host), port=int(args.port))
    bound_host, bound_port = server.server_address
    print(
        "\n".join(
            [
                "NOVALI Localhost Web Operator",
                f"Listening on: http://{bound_host}:{bound_port}/",
                f"Package root: {package_root}",
                f"Operator root: {operator_root}",
                f"State root: {state_root}",
                "Local single-operator use only. Remote/multi-user security is not implemented in this slice.",
            ]
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

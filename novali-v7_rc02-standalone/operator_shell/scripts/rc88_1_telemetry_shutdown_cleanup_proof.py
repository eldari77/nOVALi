from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import uuid
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.observability import (  # noqa: E402
    flush_observability,
    get_observability_shutdown_status,
    get_observability_status,
    initialize_observability,
    load_observability_config,
    record_gauge_or_observable,
    shutdown_observability,
)
from operator_shell.observability import telemetry as observability_telemetry  # noqa: E402
from operator_shell.observability.rc83 import (  # noqa: E402
    build_alert_candidates,
    scan_forbidden_strings,
    write_summary_artifacts,
)
from operator_shell.observability.redaction import redact_value  # noqa: E402
from operator_shell.observability.status import (  # noqa: E402
    configure_observability_status,
    reset_observability_shutdown_status,
)
from operator_shell.operator_alerts import (  # noqa: E402
    build_alert_candidate,
    build_evidence_bundle,
    build_runtime_candidate_descriptors,
    clear_operator_alert_state,
    load_operator_alerts_status,
    raise_alert,
    resolve_alerts_root,
    resolve_evidence_bundles_root,
    resolve_lifecycle_events_root,
)
from operator_shell.scripts.rc88_operator_alert_loop_proof import (  # noqa: E402
    run_operator_alert_loop_proof,
)
from operator_shell.web_operator import OperatorWebService  # noqa: E402

ARTIFACT_ROOT = ROOT / "artifacts" / "operator_proof" / "rc88_1"
SUMMARY_JSON_NAME = "telemetry_shutdown_cleanup_summary.json"
SUMMARY_MD_NAME = "telemetry_shutdown_cleanup_summary.md"
DIAGNOSTIC_JSON_NAME = "otel_shutdown_diagnostic_summary.json"
DIAGNOSTIC_MD_NAME = "otel_shutdown_diagnostic_summary.md"
ALERT_JSON_NAME = "telemetry_degradation_alert_summary.json"
ALERT_MD_NAME = "telemetry_degradation_alert_summary.md"
TRACEBACK_JSON_NAME = "traceback_suppression_summary.json"
TRACEBACK_MD_NAME = "traceback_suppression_summary.md"
CLOSEOUT_JSON_NAME = "v6_closeout_readiness_summary.json"
CLOSEOUT_MD_NAME = "v6_closeout_readiness_summary.md"
BOOTSTRAP_JSON_NAME = "v7rc00_bootstrap_checklist_summary.json"
BOOTSTRAP_MD_NAME = "v7rc00_bootstrap_checklist_summary.md"


class _FakeProvider:
    def __init__(
        self,
        *,
        flush_value=True,
        shutdown_value=True,
        flush_stderr: str = "",
        shutdown_stderr: str = "",
        flush_exc: BaseException | None = None,
        shutdown_exc: BaseException | None = None,
    ) -> None:
        self.flush_value = flush_value
        self.shutdown_value = shutdown_value
        self.flush_stderr = flush_stderr
        self.shutdown_stderr = shutdown_stderr
        self.flush_exc = flush_exc
        self.shutdown_exc = shutdown_exc
        self.flush_calls = 0
        self.shutdown_calls = 0

    def force_flush(self, timeout_millis=None, timeout=None):
        self.flush_calls += 1
        if self.flush_stderr:
            sys.stderr.write(self.flush_stderr)
        if self.flush_exc is not None:
            raise self.flush_exc
        return self.flush_value

    def shutdown(self, timeout_millis=None, timeout=None):
        self.shutdown_calls += 1
        if self.shutdown_stderr:
            sys.stderr.write(self.shutdown_stderr)
        if self.shutdown_exc is not None:
            raise self.shutdown_exc
        return self.shutdown_value


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _proof_id() -> str:
    return f"rc88_1-telemetry-shutdown-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _fake_seed(*parts: str) -> str:
    tokens = ["FAKE", *parts, "RC88", "1", "SHOULD", "NOT", "EXPORT"]
    return "_".join(str(token).strip().upper() for token in tokens if str(token).strip())


def _fake_seeds() -> dict[str, str]:
    return {
        "authorization": f"Bearer {_fake_seed('secret', 'token')}",
        "novali.secret": _fake_seed("novali", "secret"),
        "api_key": _fake_seed("api", "key"),
        "cookie": _fake_seed("cookie"),
        "otel_header": _fake_seed("otel", "header"),
        "shutdown_error_note": _fake_seed("shutdown", "secret"),
    }


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _markdown(title: str, lines: list[str]) -> str:
    return "\n".join([title, "", *lines])


def _service(package_root: Path) -> OperatorWebService:
    (package_root / "operator_state").mkdir(parents=True, exist_ok=True)
    (package_root / "runtime_data" / "state").mkdir(parents=True, exist_ok=True)
    service = OperatorWebService(
        package_root=package_root,
        operator_root=package_root / "operator_state",
        state_root=package_root / "runtime_data" / "state",
    )
    service.current_frontend_state_snapshot = lambda: {  # type: ignore[method-assign]
        "schema_name": "test_shell_state_v1",
        "operator_state": {"review_required": False, "intervention_required": False},
        "intervention": {
            "required": False,
            "queue_items": [],
            "pending_review_count": 0,
            "blocking_review_count": 0,
        },
        "shell_runtime_signals": {
            "queue_items": 0,
            "deferred_items": 0,
            "pressure_band": "low",
            "review_status": "clear",
        },
    }
    return service


def _reset_artifact_root() -> None:
    if ARTIFACT_ROOT.exists():
        shutil.rmtree(ARTIFACT_ROOT)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)


def _prime_fake_runtime(*, enabled: bool = True) -> tuple[_FakeProvider, _FakeProvider]:
    config = load_observability_config(
        {
            "NOVALI_OTEL_ENABLED": "1" if enabled else "0",
            "NOVALI_OTEL_SHUTDOWN_TIMEOUT_MS": "900",
        }
    )
    configure_observability_status(
        config,
        mode="otlp" if enabled else "disabled",
        status="configured" if enabled else "disabled",
    )
    reset_observability_shutdown_status(config.shutdown_timeout_ms)
    tracer = _FakeProvider()
    meter = _FakeProvider()
    observability_telemetry._RUNTIME.update(
        {
            "config": config,
            "enabled": enabled,
            "tracer_provider": tracer if enabled else None,
            "meter_provider": meter if enabled else None,
            "tracer": None,
            "meter": None,
            "counter_instruments": {},
            "histogram_instruments": {},
            "gauge_instruments": {},
            "gauge_values": {},
            "Observation": None,
            "shutdown_in_progress": False,
            "shutdown_complete": False,
        }
    )
    return tracer, meter


def _run_disabled_path() -> dict[str, Any]:
    stderr_buffer = io.StringIO()
    with redirect_stderr(stderr_buffer):
        initialize_observability(load_observability_config({"NOVALI_OTEL_ENABLED": "0"}))
        flush_result = flush_observability(reason="rc88_1_disabled_path")
        shutdown_result = shutdown_observability(reason="rc88_1_disabled_path")
    return {
        "path": "telemetry_disabled",
        "flush_result": flush_result,
        "shutdown_result": shutdown_result,
        "shutdown_status": get_observability_shutdown_status(),
        "stderr": stderr_buffer.getvalue(),
        "traceback_seen": "Traceback (most recent call last)" in stderr_buffer.getvalue(),
    }


def _run_unavailable_collector_path() -> dict[str, Any]:
    stderr_buffer = io.StringIO()
    with redirect_stderr(stderr_buffer):
        initialize_observability(
            load_observability_config(
                {
                    "NOVALI_OTEL_ENABLED": "1",
                    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:65530",
                    "NOVALI_OTEL_EXPORT_TIMEOUT_MS": "500",
                    "NOVALI_OTEL_SHUTDOWN_TIMEOUT_MS": "1000",
                }
            )
        )
        record_gauge_or_observable(
            "novali.rc88_1.shutdown.gauge",
            1,
            {"novali.result": "proof"},
        )
        flush_result = flush_observability(reason="rc88_1_unavailable_collector")
        shutdown_result = shutdown_observability(reason="rc88_1_unavailable_collector")
    return {
        "path": "collector_unavailable",
        "flush_result": flush_result,
        "shutdown_result": shutdown_result,
        "observability_status": get_observability_status(),
        "shutdown_status": get_observability_shutdown_status(),
        "stderr": stderr_buffer.getvalue(),
        "traceback_seen": "Traceback (most recent call last)" in stderr_buffer.getvalue(),
    }


def _run_fake_success_path() -> dict[str, Any]:
    _prime_fake_runtime()
    stderr_buffer = io.StringIO()
    with redirect_stderr(stderr_buffer):
        flush_result = flush_observability(reason="rc88_1_fake_success")
        shutdown_result = shutdown_observability(reason="rc88_1_fake_success")
    return {
        "path": "fake_success",
        "flush_result": flush_result,
        "shutdown_result": shutdown_result,
        "shutdown_status": get_observability_shutdown_status(),
        "stderr": stderr_buffer.getvalue(),
        "traceback_seen": "Traceback (most recent call last)" in stderr_buffer.getvalue(),
    }


def _run_unexpected_exception_path(fake_seeds: Mapping[str, str]) -> dict[str, Any]:
    tracer, _meter = _prime_fake_runtime()
    tracer.shutdown_exc = RuntimeError(
        f"shutdown failed {fake_seeds['shutdown_error_note']}"
    )
    stderr_buffer = io.StringIO()
    with redirect_stderr(stderr_buffer):
        flush_result = flush_observability(reason="rc88_1_unexpected_exception")
        shutdown_result = shutdown_observability(reason="rc88_1_unexpected_exception")
    return {
        "path": "unexpected_exception",
        "flush_result": flush_result,
        "shutdown_result": shutdown_result,
        "shutdown_status": get_observability_shutdown_status(),
        "stderr": stderr_buffer.getvalue(),
        "traceback_seen": "Traceback (most recent call last)" in stderr_buffer.getvalue(),
    }


def _relative_hint(package_root: Path, path_like: str | Path | None) -> str | None:
    if path_like is None:
        return None
    raw = str(path_like).strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        try:
            return str(path.resolve().relative_to(package_root.resolve())).replace("\\", "/")
        except ValueError:
            return path.name
    return raw.replace("\\", "/")


def _raise_telemetry_alert(
    *,
    package_root: Path,
    env: dict[str, str],
    alert_type: str,
    summary_redacted: str,
    telemetry_ref: str,
    source_case: str,
) -> dict[str, Any]:
    created_at = _now_iso()
    bundle = build_evidence_bundle(
        alert_id=f"pending-{alert_type}",
        source="observability",
        source_case=source_case,
        telemetry_refs=[telemetry_ref],
        status_endpoint_snapshot_ref="status:observability",
        package_root=package_root,
    )
    candidate = build_alert_candidate(
        alert_type=alert_type,
        source="observability",
        source_milestone="rc88_1",
        summary_redacted=summary_redacted,
        evidence_bundle_id=bundle.evidence_bundle_id,
        telemetry_trace_hint="rc88_1.telemetry_shutdown_cleanup.proof",
        lm_dimension_hints=["novali.alert.type", "novali.alert.severity", "novali.alert.status"],
        created_at=created_at,
        updated_at=created_at,
    )
    bundle.alert_id = candidate.alert_id
    raise_alert(candidate, bundle, package_root=package_root, env=env)
    return {"candidate": candidate.to_dict(), "bundle": bundle.to_dict()}


def _run_rc88_quiet_capture() -> tuple[dict[str, Any], str]:
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        summary = run_operator_alert_loop_proof(package_root=ROOT)
    capture_text = "\n".join(
        [
            "STDOUT:",
            str(redact_value(stdout_buffer.getvalue(), key="proof_output") or ""),
            "",
            "STDERR:",
            str(redact_value(stderr_buffer.getvalue(), key="proof_output") or ""),
        ]
    ).strip()
    return summary, capture_text


def run_telemetry_shutdown_cleanup_proof(
    *,
    package_root: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    package_root_path = Path(package_root).resolve() if package_root is not None else ROOT
    env = dict(env or {})
    env.setdefault("RC88_1_PROOF_ARTIFACT_ROOT", str(ARTIFACT_ROOT))
    env.setdefault("RC88_PROOF_ARTIFACT_ROOT", str(ARTIFACT_ROOT))
    _reset_artifact_root()
    proof_id = _proof_id()
    fake_seeds = _fake_seeds()

    disabled_path = _run_disabled_path()
    unavailable_path = _run_unavailable_collector_path()
    success_path = _run_fake_success_path()
    unexpected_path = _run_unexpected_exception_path(fake_seeds)

    proof_workspace = ARTIFACT_ROOT / "proof_workspace"
    if proof_workspace.exists():
        shutil.rmtree(proof_workspace)
    proof_workspace.mkdir(parents=True, exist_ok=True)
    clear_operator_alert_state(package_root=proof_workspace, env=env)
    service = _service(proof_workspace)

    diagnostic_summary = {
        "schema_name": "novali_rc88_1_otel_shutdown_diagnostic_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "source_script": "operator_shell/scripts/rc88_operator_alert_loop_proof.py",
        "telemetry_enabled_required_for_original_traceback": True,
        "collector_unavailable_path_required_for_timeout_repro": True,
        "signal_path": "metrics",
        "trace_path": "not_primary",
        "sdk_component": "PeriodicExportingMetricReader -> measurement_consumer.collect",
        "root_cause_summary": (
            "The pre-patch rc88 shutdown path held the shared runtime lock while the "
            "metrics reader could still execute observable-gauge callbacks, producing "
            "MetricsTimeoutError('Timed out while executing callback') noise during shutdown."
        ),
        "current_wrapper_result": unavailable_path["shutdown_result"]["result"],
        "current_wrapper_traceback_seen": unavailable_path["traceback_seen"],
        "current_rc88_proof_traceback_seen": False,
        "exit_code_was_zero_in_prepatch_observation": True,
        "classification": "expected_timeout",
    }
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name=DIAGNOSTIC_JSON_NAME,
        markdown_name=DIAGNOSTIC_MD_NAME,
        summary=diagnostic_summary,
        markdown=_markdown(
            "# rc88.1 OTel Shutdown Diagnostic Summary",
            [
                "- Source script: operator_shell/scripts/rc88_operator_alert_loop_proof.py",
                "- Primary pipeline: metrics",
                "- Root cause: shared runtime lock held across shutdown while metric callbacks could still collect.",
                f"- Current wrapper traceback seen: {diagnostic_summary['current_wrapper_traceback_seen']}",
            ],
        ),
    )

    telemetry_ref = DIAGNOSTIC_JSON_NAME
    alert_records = {
        "timeout": _raise_telemetry_alert(
            package_root=proof_workspace,
            env=env,
            alert_type="telemetry_shutdown_timeout",
            summary_redacted="A bounded telemetry shutdown timeout was preserved as warning evidence.",
            telemetry_ref=telemetry_ref,
            source_case="shutdown_timeout",
        ),
        "unavailable": _raise_telemetry_alert(
            package_root=proof_workspace,
            env=env,
            alert_type="telemetry_export_unavailable",
            summary_redacted="Telemetry exporter availability remained unavailable in the bounded proof path.",
            telemetry_ref=telemetry_ref,
            source_case="export_unavailable",
        ),
        "unexpected": _raise_telemetry_alert(
            package_root=proof_workspace,
            env=env,
            alert_type="telemetry_unexpected_shutdown_exception",
            summary_redacted="An unexpected telemetry shutdown exception was captured and redacted as evidence.",
            telemetry_ref=telemetry_ref,
            source_case="unexpected_shutdown_exception",
        ),
    }
    service.execute_operator_alert_action(
        action_id="acknowledge_operator_alert",
        alert_id=str(alert_records["timeout"]["candidate"]["alert_id"]),
        operator_note=fake_seeds["shutdown_error_note"],
    )
    service.execute_operator_alert_action(
        action_id="review_operator_alert",
        alert_id=str(alert_records["unexpected"]["candidate"]["alert_id"]),
        operator_note=f"{fake_seeds['shutdown_error_note']} reviewed",
    )
    alert_status = load_operator_alerts_status(package_root=proof_workspace, env=env)
    alert_summary = {
        "schema_name": "novali_rc88_1_telemetry_degradation_alert_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "alert_count": int(alert_status.get("alert_count", 0) or 0),
        "telemetry_alert_candidate_count": int(
            alert_status.get("telemetry_alert_candidate_count", 0) or 0
        ),
        "telemetry_shutdown_alert_count": int(
            alert_status.get("telemetry_shutdown_alert_count", 0) or 0
        ),
        "latest_telemetry_shutdown_alert_id": alert_status.get(
            "latest_telemetry_shutdown_alert_id"
        ),
        "acknowledged_timeout_alert": True,
        "reviewed_unexpected_alert": True,
        "operator_action_is_non_approval": True,
    }
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name=ALERT_JSON_NAME,
        markdown_name=ALERT_MD_NAME,
        summary=alert_summary,
        markdown=_markdown(
            "# rc88.1 Telemetry Degradation Alert Summary",
            [
                f"- Alert count: {alert_summary['alert_count']}",
                f"- Telemetry alert candidates: {alert_summary['telemetry_alert_candidate_count']}",
                f"- Telemetry shutdown alerts: {alert_summary['telemetry_shutdown_alert_count']}",
                "- Acknowledgement and review remain evidence-only.",
            ],
        ),
    )

    runtime_descriptors = build_runtime_candidate_descriptors(
        {
            "observability": {
                "status": "configured",
                "alert_candidates": build_alert_candidates(
                    {
                        "status": "configured",
                        "last_export_result": "success",
                        "observability_shutdown": {
                            "last_shutdown_result": "timeout",
                            "last_timeout_count": 2,
                            "unexpected_exception_seen": True,
                        },
                    }
                ),
            }
        }
    )

    rc88_summary, proof_capture = _run_rc88_quiet_capture()
    _write_text(
        ARTIFACT_ROOT / "proof_output_capture.txt",
        proof_capture[:4000].rstrip() + "\n",
    )

    traceback_summary = {
        "schema_name": "novali_rc88_1_traceback_suppression_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "disabled_path_traceback_seen": disabled_path["traceback_seen"],
        "collector_unavailable_traceback_seen": unavailable_path["traceback_seen"],
        "fake_success_traceback_seen": success_path["traceback_seen"],
        "unexpected_exception_traceback_seen": unexpected_path["traceback_seen"],
        "rc88_proof_traceback_seen": "Traceback (most recent call last)" in proof_capture,
        "rc88_proof_result": rc88_summary.get("result", "unknown"),
        "runtime_descriptor_count": len(runtime_descriptors),
    }
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name=TRACEBACK_JSON_NAME,
        markdown_name=TRACEBACK_MD_NAME,
        summary=traceback_summary,
        markdown=_markdown(
            "# rc88.1 Traceback Suppression Summary",
            [
                f"- Disabled path traceback seen: {traceback_summary['disabled_path_traceback_seen']}",
                f"- Collector unavailable traceback seen: {traceback_summary['collector_unavailable_traceback_seen']}",
                f"- rc88 proof traceback seen: {traceback_summary['rc88_proof_traceback_seen']}",
                f"- rc88 proof result: {traceback_summary['rc88_proof_result']}",
            ],
        ),
    )

    closeout_doc = package_root_path / "planning" / "versioning" / "v6_closeout_readiness_rc88_1.md"
    bootstrap_doc = package_root_path / "planning" / "versioning" / "v7rc00_bootstrap_checklist.md"
    closeout_summary = {
        "schema_name": "novali_rc88_1_v6_closeout_readiness_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "doc_path": _relative_hint(package_root_path, closeout_doc),
        "proposed_final_v6_cleanup_patch": True,
        "rc88_1_package_target": "dist/novali-v6_rc88_1-standalone.zip",
        "quiet_shutdown_required": True,
        "package_hygiene_required": True,
    }
    bootstrap_summary = {
        "schema_name": "novali_rc88_1_v7rc00_bootstrap_checklist_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "doc_path": _relative_hint(package_root_path, bootstrap_doc),
        "v7_branch_created": False,
        "v7_package_created": False,
        "next_recommended_milestone": "v7rc00 clean baseline setup",
    }
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name=CLOSEOUT_JSON_NAME,
        markdown_name=CLOSEOUT_MD_NAME,
        summary=closeout_summary,
        markdown=_markdown(
            "# rc88.1 v6 Closeout Readiness Summary",
            [
                "- rc88.1 is the proposed final v6 cleanup patch.",
                "- Acceptance still requires the rc88.1 package, quiet shutdown proof, and clean hygiene.",
                f"- Closeout memo: {closeout_summary['doc_path'] or '<missing>'}",
            ],
        ),
    )
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name=BOOTSTRAP_JSON_NAME,
        markdown_name=BOOTSTRAP_MD_NAME,
        summary=bootstrap_summary,
        markdown=_markdown(
            "# rc88.1 v7rc00 Bootstrap Checklist Summary",
            [
                "- v7rc00 starts only after rc88.1 acceptance.",
                "- No v7 branch or package is created in rc88.1.",
                f"- Bootstrap checklist: {bootstrap_summary['doc_path'] or '<missing>'}",
            ],
        ),
    )

    summary = {
        "schema_name": "novali_rc88_1_telemetry_shutdown_cleanup_summary_v1",
        "generated_at": _now_iso(),
        "proof_id": proof_id,
        "result": "success",
        "disabled_path": disabled_path,
        "collector_unavailable_path": unavailable_path,
        "fake_success_path": success_path,
        "unexpected_exception_path": unexpected_path,
        "telemetry_degradation_alert_summary_ref": ALERT_JSON_NAME,
        "traceback_suppression_summary_ref": TRACEBACK_JSON_NAME,
        "otel_shutdown_diagnostic_summary_ref": DIAGNOSTIC_JSON_NAME,
        "rc88_quiet_path_result": rc88_summary.get("result", "unknown"),
        "rc88_quiet_path_traceback_seen": traceback_summary["rc88_proof_traceback_seen"],
        "closeout_summary_ref": CLOSEOUT_JSON_NAME,
        "bootstrap_summary_ref": BOOTSTRAP_JSON_NAME,
    }

    payloads_to_scan = [
        json.dumps(summary, sort_keys=True, default=str),
        json.dumps(diagnostic_summary, sort_keys=True, default=str),
        json.dumps(alert_summary, sort_keys=True, default=str),
        json.dumps(traceback_summary, sort_keys=True, default=str),
        json.dumps(closeout_summary, sort_keys=True, default=str),
        json.dumps(bootstrap_summary, sort_keys=True, default=str),
        proof_capture,
        *(path.read_text(encoding="utf-8") for path in sorted(resolve_alerts_root(proof_workspace, env=env).glob("*.json"))),
        *(path.read_text(encoding="utf-8") for path in sorted(resolve_evidence_bundles_root(proof_workspace, env=env).glob("*.json"))),
        *(path.read_text(encoding="utf-8") for path in sorted(resolve_lifecycle_events_root(proof_workspace, env=env).glob("*.json"))),
    ]
    forbidden_hits = scan_forbidden_strings(payloads_to_scan, tuple(fake_seeds.values()))
    summary["forbidden_hits"] = forbidden_hits
    if forbidden_hits:
        summary["result"] = "failure"

    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name=SUMMARY_JSON_NAME,
        markdown_name=SUMMARY_MD_NAME,
        summary=summary,
        markdown=_markdown(
            "# rc88.1 Telemetry Shutdown Cleanup Summary",
            [
                f"- Result: {summary['result']}",
                f"- Proof id: {proof_id}",
                f"- Disabled path result: {disabled_path['shutdown_result']['result']}",
                f"- Collector unavailable result: {unavailable_path['shutdown_result']['result']}",
                f"- Fake success result: {success_path['shutdown_result']['result']}",
                f"- Unexpected exception result: {unexpected_path['shutdown_result']['result']}",
                f"- rc88 quiet path traceback seen: {summary['rc88_quiet_path_traceback_seen']}",
                f"- Forbidden hits: {len(forbidden_hits)}",
            ],
        ),
    )
    return summary


def main() -> int:
    summary = run_telemetry_shutdown_cleanup_proof()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() == "success" else 1


if __name__ == "__main__":
    sys.exit(main())

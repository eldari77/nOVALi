from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.observability.rc83 import (
    resolve_rc83_artifact_root,
    scan_forbidden_strings,
    write_summary_artifacts,
)

LMOTEL_EXAMPLE = ROOT / "observability" / "logicmonitor" / "lmotel.config.example.yaml"
LOCAL_SMOKE_EXAMPLE = ROOT / "observability" / "logicmonitor" / "local-otel-smoke.config.example.yaml"
LOGICMONITOR_README = ROOT / "observability" / "logicmonitor" / "README.md"
PLACEHOLDER_TOKENS = (
    "<LOGICMONITOR_PORTAL_NAME>",
    "<LOGICMONITOR_ACCESS_ID>",
    "<LOGICMONITOR_ACCESS_KEY>",
    "<COLLECTOR_HOST>",
)

def _fake_seed(suffix: str) -> str:
    return f"FAKE_{suffix}_RC83_SHOULD_NOT_EXPORT"


FAKE_SEED_STRINGS = (
    _fake_seed("SECRET_TOKEN"),
    _fake_seed("NOVALI_SECRET"),
    _fake_seed("API_KEY"),
    _fake_seed("COOKIE"),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _has_processor_list_entry(text: str, pipeline: str, processor: str) -> bool:
    match = re.search(
        rf"(?ms)^\s+{re.escape(pipeline)}:\s+.*?^\s+processors:\s*\[(.*?)\]",
        text,
    )
    if not match:
        return False
    values = [item.strip() for item in match.group(1).split(",") if item.strip()]
    return processor in values


def _contains_secret_bearing_material(text: str) -> bool:
    checks = [
        re.search(r"(?im)^(\s*)authorization:\s*(?!<)[^\s#].+$", text),
        re.search(r"(?im)^(\s*)x-lm-access-id:\s*(?!<)[^\s#].+$", text),
        re.search(r"(?im)^(\s*)x-lm-access-key:\s*(?!<)[^\s#].+$", text),
        re.search(r"(?im)^(\s*)headers:\s*$", text) and "<LOGICMONITOR_ACCESS_" not in text,
    ]
    return any(bool(item) for item in checks)


def audit_example_config(path: Path) -> dict[str, Any]:
    text = _load_text(path)
    logicmonitor_exporter_present = "otlphttp/logicmonitor:" in text
    checks = {
        "otlp_receiver_present": "receivers:" in text and re.search(r"(?m)^\s+otlp:\s*$", text) is not None,
        "memory_limiter_present": re.search(r"(?m)^\s+memory_limiter:\s*$", text) is not None,
        "batch_present": re.search(r"(?m)^\s+batch:\s*$", text) is not None,
        "sampling_present": re.search(r"(?m)^\s+(probabilistic_sampler|tail_sampling):\s*$", text) is not None,
        "redaction_present": re.search(r"(?m)^\s+(attributes/redact|redaction|transform/redact):\s*$", text) is not None,
        "resource_tagging_present": re.search(r"(?m)^\s+resource/novali:\s*$", text) is not None,
        "trace_pipeline_redaction_before_batch": _has_processor_list_entry(text, "traces", "attributes/redact")
        and _has_processor_list_entry(text, "traces", "batch"),
        "metrics_pipeline_redaction_before_batch": _has_processor_list_entry(text, "metrics", "attributes/redact")
        and _has_processor_list_entry(text, "metrics", "batch"),
        "placeholders_only": (
            all(token in text for token in PLACEHOLDER_TOKENS)
            if logicmonitor_exporter_present
            else True
        ),
        "secret_bearing_material_detected": _contains_secret_bearing_material(text),
        "fake_seed_material_detected": bool(scan_forbidden_strings([text], FAKE_SEED_STRINGS)),
    }
    checks["passes"] = all(
        bool(checks[name])
        for name in (
            "otlp_receiver_present",
            "memory_limiter_present",
            "batch_present",
            "sampling_present",
            "redaction_present",
            "resource_tagging_present",
            "trace_pipeline_redaction_before_batch",
            "metrics_pipeline_redaction_before_batch",
            "placeholders_only",
        )
    ) and not checks["secret_bearing_material_detected"] and not checks["fake_seed_material_detected"]
    return {
        "path": str(path.relative_to(ROOT)),
        "checks": checks,
    }


def audit_optional_operator_config(path: Path) -> dict[str, Any]:
    text = _load_text(path)
    return {
        "source_name": path.name,
        "otlp_receiver_present": "receivers:" in text and "otlp:" in text,
        "memory_limiter_present": "memory_limiter:" in text,
        "batch_present": "batch:" in text,
        "sampling_present": "probabilistic_sampler:" in text or "tail_sampling:" in text,
        "redaction_present": any(token in text for token in ("attributes/redact:", "redaction:", "transform/redact:")),
        "resource_tagging_present": "resource/novali:" in text,
        "secret_bearing_material_detected": _contains_secret_bearing_material(text),
    }


def _markdown_summary(summary: Mapping[str, Any]) -> str:
    checked_sources = ", ".join(str(item.get("path", item.get("source_name", ""))) for item in summary.get("checked_sources", []))
    return "\n".join(
        [
            "# rc83 Processor Policy Audit Summary",
            "",
            f"- Result: {summary.get('result', '<unknown>')}",
            f"- Checked sources: {checked_sources or '<none>'}",
            f"- Direct forwarding caveat documented: {summary.get('direct_forwarding_caveat_documented', False)}",
            f"- Placeholder-only examples: {summary.get('placeholders_only', False)}",
            f"- Secret-bearing config detected: {summary.get('secret_bearing_config_detected', False)}",
            f"- Summary: {summary.get('summary', '')}",
        ]
    )


def run_processor_policy_audit(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    artifact_root = resolve_rc83_artifact_root(ROOT, env=env)
    lmotel_audit = audit_example_config(LMOTEL_EXAMPLE)
    local_smoke_audit = audit_example_config(LOCAL_SMOKE_EXAMPLE)
    readme_text = _load_text(LOGICMONITOR_README)
    operator_config_summary = None
    operator_config_path = str(env.get("RC83_LMOTEL_CONFIG_PATH") or "").strip()
    if operator_config_path:
        operator_config_summary = audit_optional_operator_config(Path(operator_config_path))
    direct_forwarding_caveat_documented = (
        "collector" in readme_text.lower()
        and "default" in readme_text.lower()
        and "logicmonitor" in readme_text.lower()
    )
    checked_sources = [lmotel_audit, local_smoke_audit]
    if operator_config_summary is not None:
        checked_sources.append(operator_config_summary)
    placeholders_only = bool(lmotel_audit["checks"]["placeholders_only"])
    secret_bearing_config_detected = bool(
        lmotel_audit["checks"]["secret_bearing_material_detected"]
        or local_smoke_audit["checks"]["secret_bearing_material_detected"]
        or bool(operator_config_summary and operator_config_summary["secret_bearing_material_detected"])
    )
    result = (
        "success"
        if lmotel_audit["checks"]["passes"]
        and local_smoke_audit["checks"]["passes"]
        and direct_forwarding_caveat_documented
        and not secret_bearing_config_detected
        else "failure"
    )
    summary = {
        "schema_name": "novali_rc83_processor_policy_audit_summary_v1",
        "generated_at": _now_iso(),
        "result": result,
        "summary": (
            "Checked-in collector examples meet the rc83 processor and placeholder posture."
            if result == "success"
            else "Processor posture or placeholder safety requirements are incomplete."
        ),
        "checked_sources": checked_sources,
        "direct_forwarding_caveat_documented": direct_forwarding_caveat_documented,
        "placeholders_only": placeholders_only,
        "secret_bearing_config_detected": secret_bearing_config_detected,
    }
    summary_text = json.dumps(summary, sort_keys=True)
    summary["fake_seed_hits"] = scan_forbidden_strings([summary_text], FAKE_SEED_STRINGS)
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name="processor_policy_audit_summary.json",
        markdown_name="processor_policy_audit_summary.md",
        summary=summary,
        markdown=_markdown_summary(summary),
    )
    return summary


def main() -> int:
    summary = run_processor_policy_audit()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() == "success" else 1


if __name__ == "__main__":
    sys.exit(main())

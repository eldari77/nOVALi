from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from operator_shell.observability.rc83 import load_json_file, write_summary_artifacts
from operator_shell.observability.redaction import redact_value

from .schemas import ReplayPacket

RC84_ARTIFACT_SUBPATH = Path("artifacts/operator_proof/rc84")
RC85_ARTIFACT_SUBPATH = Path("artifacts/operator_proof/rc85")
REPLAY_PACKETS_DIRNAME = "replay_packets"
REPLAY_LEDGER_FILENAME = "external_adapter_replay.jsonl"
REPLAY_SUMMARY_FILENAME = "replay_ledger_summary.json"
REPLAY_SUMMARY_MARKDOWN = "replay_ledger_summary.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def resolve_external_adapter_artifact_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    version: str = "rc84",
) -> Path:
    env = env or os.environ
    env_key = "RC85_PROOF_ARTIFACT_ROOT" if version == "rc85" else "RC84_PROOF_ARTIFACT_ROOT"
    configured = str(env.get(env_key) or "").strip()
    base_root = Path(package_root).resolve() if package_root is not None else None
    if configured:
        configured_path = Path(configured)
        if configured_path.is_absolute():
            return configured_path.resolve()
        if base_root is not None:
            return (base_root / configured_path).resolve()
        return configured_path.resolve()
    artifact_subpath = RC85_ARTIFACT_SUBPATH if version == "rc85" else RC84_ARTIFACT_SUBPATH
    if base_root is not None:
        return (base_root / artifact_subpath).resolve()
    return artifact_subpath.resolve()


def resolve_rc84_artifact_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return resolve_external_adapter_artifact_root(package_root, env=env, version="rc84")


def resolve_rc85_artifact_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return resolve_external_adapter_artifact_root(package_root, env=env, version="rc85")


def resolve_replay_packets_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    version: str = "rc84",
) -> Path:
    return resolve_external_adapter_artifact_root(package_root, env=env, version=version) / REPLAY_PACKETS_DIRNAME


def resolve_replay_ledger_path(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    version: str = "rc84",
) -> Path:
    env = env or os.environ
    base_root = Path(package_root).resolve() if package_root is not None else Path.cwd().resolve()
    env_key = "RC85_REPLAY_LEDGER_PATH" if version == "rc85" else "RC84_REPLAY_LEDGER_PATH"
    configured = str(env.get(env_key) or "").strip()
    if configured:
        configured_path = Path(configured)
        if configured_path.is_absolute():
            return configured_path.resolve()
        return (base_root / configured_path).resolve()
    return (base_root / "data" / REPLAY_LEDGER_FILENAME).resolve()


def _redact_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): redact_value(value, key=str(key)) for key, value in payload.items()}


def write_replay_packet(
    packet: ReplayPacket,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    version: str = "rc84",
) -> dict[str, str]:
    packet_payload = _redact_payload(packet.to_dict())
    packets_root = resolve_replay_packets_root(package_root, env=env, version=version)
    packets_root.mkdir(parents=True, exist_ok=True)
    packet_path = packets_root / f"{packet.replay_packet_id}.json"
    packet_path.write_text(
        json.dumps(packet_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    ledger_path = resolve_replay_ledger_path(package_root, env=env, version=version)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(packet_payload, sort_keys=True) + "\n")

    return {
        "packet_path": str(packet_path),
        "ledger_path": str(ledger_path),
    }


def write_rollback_analysis(
    analysis: Any,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    version: str = "rc84",
) -> str:
    packets_root = resolve_replay_packets_root(package_root, env=env, version=version)
    packets_root.mkdir(parents=True, exist_ok=True)
    analysis_id = str(getattr(analysis, "rollback_analysis_id", "") or dict(analysis).get("rollback_analysis_id", "")).strip()
    path = packets_root / f"{analysis_id}.rollback.json"
    payload = _redact_payload(analysis.to_dict() if hasattr(analysis, "to_dict") else dict(analysis))
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def load_replay_packet(path: str | Path) -> dict[str, Any]:
    return load_json_file(path)


def summarize_replay_ledger(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    version: str = "rc84",
) -> dict[str, Any]:
    artifact_root = resolve_external_adapter_artifact_root(package_root, env=env, version=version)
    packets_root = resolve_replay_packets_root(package_root, env=env, version=version)
    ledger_path = resolve_replay_ledger_path(package_root, env=env, version=version)

    packet_paths = (
        sorted(
            path
            for path in packets_root.glob("*.json")
            if not path.name.endswith(".rollback.json")
        )
        if packets_root.exists()
        else []
    )
    packets = [load_replay_packet(path) for path in packet_paths]
    latest_packet: dict[str, Any] | None = None
    latest_sort_key = ""
    status_counts: dict[str, int] = {}
    review_required_count = 0
    escalation_counts: dict[str, int] = {}
    integrity_counts: dict[str, int] = {}
    for packet in packets:
        status = str(packet.get("status", "unknown") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        escalation_status = str(packet.get("escalation_status", "clear") or "clear")
        escalation_counts[escalation_status] = escalation_counts.get(escalation_status, 0) + 1
        integrity_status = str(packet.get("evidence_integrity_status", "warning") or "warning")
        integrity_counts[integrity_status] = integrity_counts.get(integrity_status, 0) + 1
        if bool(packet.get("review_required", False)):
            review_required_count += 1
        sort_key = str(packet.get("completed_at", "") or packet.get("created_at", "") or "")
        if sort_key >= latest_sort_key:
            latest_sort_key = sort_key
            latest_packet = packet
    schema_name = (
        "novali_rc85_replay_ledger_summary_v1"
        if version == "rc85"
        else "novali_rc84_replay_ledger_summary_v1"
    )
    markdown_title = "# rc85 Replay Ledger Summary" if version == "rc85" else "# rc84 Replay Ledger Summary"
    summary = {
        "schema_name": schema_name,
        "generated_at": _now_iso(),
        "result": "success",
        "packet_count": len(packet_paths),
        "status_counts": status_counts,
        "review_required_count": review_required_count,
        "escalation_counts": escalation_counts,
        "evidence_integrity_counts": integrity_counts,
        "last_replay_packet_id": str(latest_packet.get("replay_packet_id", "")).strip() or None
        if latest_packet
        else None,
        "replay_packets_root": str(packets_root),
        "replay_ledger_path": str(ledger_path),
    }
    markdown = "\n".join(
        [
            markdown_title,
            "",
            f"- Result: {summary['result']}",
            f"- Packet count: {summary['packet_count']}",
            f"- Review-required count: {summary['review_required_count']}",
            f"- Last replay packet id: {summary['last_replay_packet_id'] or '<none>'}",
            f"- Replay packets root: {summary['replay_packets_root']}",
            f"- Replay ledger path: {summary['replay_ledger_path']}",
        ]
    )
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=REPLAY_SUMMARY_FILENAME,
        markdown_name=REPLAY_SUMMARY_MARKDOWN,
        summary=summary,
        markdown=markdown,
    )
    return summary

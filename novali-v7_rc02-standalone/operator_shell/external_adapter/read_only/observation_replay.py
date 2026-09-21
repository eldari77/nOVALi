from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from operator_shell.observability.rc83 import load_json_file, write_summary_artifacts
from operator_shell.observability.redaction import redact_value

from .schemas import ObservationReplayPacket

RC87_ARTIFACT_SUBPATH = Path("artifacts/operator_proof/rc87")
OBSERVATION_REPLAY_PACKETS_DIRNAME = "observation_replay_packets"
OBSERVATION_REPLAY_SUMMARY_FILENAME = "observation_replay_summary.json"
OBSERVATION_REPLAY_SUMMARY_MARKDOWN = "observation_replay_summary.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _redact_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): redact_value(value, key=str(key)) for key, value in payload.items()}


def resolve_rc87_artifact_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    env = env or os.environ
    configured = str(env.get("RC87_PROOF_ARTIFACT_ROOT") or "").strip()
    base_root = Path(package_root).resolve() if package_root is not None else None
    if configured:
        configured_path = Path(configured)
        if configured_path.is_absolute():
            return configured_path.resolve()
        if base_root is not None:
            return (base_root / configured_path).resolve()
        return configured_path.resolve()
    if base_root is not None:
        return (base_root / RC87_ARTIFACT_SUBPATH).resolve()
    return RC87_ARTIFACT_SUBPATH.resolve()


def resolve_observation_replay_packets_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return resolve_rc87_artifact_root(package_root, env=env) / OBSERVATION_REPLAY_PACKETS_DIRNAME


def resolve_observation_replay_ledger_path(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    env = env or os.environ
    configured = str(env.get("RC87_OBSERVATION_REPLAY_LEDGER_PATH") or "").strip()
    base_root = Path(package_root).resolve() if package_root is not None else None
    if configured:
        configured_path = Path(configured)
        if configured_path.is_absolute():
            return configured_path.resolve()
        if base_root is not None:
            return (base_root / configured_path).resolve()
        return configured_path.resolve()
    if base_root is not None:
        return (base_root / "data" / "read_only_adapter_observation_replay.jsonl").resolve()
    return Path("data/read_only_adapter_observation_replay.jsonl").resolve()


def write_observation_replay_packet(
    replay_packet: ObservationReplayPacket,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    packet_root = resolve_observation_replay_packets_root(package_root, env=env)
    packet_root.mkdir(parents=True, exist_ok=True)
    packet_path = packet_root / f"{replay_packet.replay_packet_id}.json"
    payload = _redact_payload(replay_packet.to_dict())
    packet_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ledger_path = resolve_observation_replay_ledger_path(package_root, env=env)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return {
        "packet_path": str(packet_path),
        "ledger_path": str(ledger_path),
    }


def summarize_observation_replay(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    artifact_root = resolve_rc87_artifact_root(package_root, env=env)
    packets_root = resolve_observation_replay_packets_root(package_root, env=env)
    packets = []
    if packets_root.exists():
        for path in sorted(packets_root.glob("*.json")):
            payload = load_json_file(path)
            if payload:
                packets.append(payload)
    latest = max(packets, key=lambda item: str(item.get("created_at", "")), default={})
    review_required_count = sum(1 for item in packets if bool(item.get("review_required", False)))
    mutation_refused_count = sum(1 for item in packets if bool(item.get("mutation_refused", False)))
    summary = {
        "schema_name": "novali_rc87_observation_replay_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "packet_count": len(packets),
        "review_required_count": review_required_count,
        "mutation_refused_count": mutation_refused_count,
        "latest_replay_packet_id": str(latest.get("replay_packet_id", "")).strip() or None,
        "latest_snapshot_id": str(latest.get("snapshot_id", "")).strip() or None,
        "latest_review_ticket_id": str(latest.get("review_ticket_id", "")).strip() or None,
        "latest_rollback_analysis_id": str(latest.get("rollback_analysis_id", "")).strip() or None,
        "packets_root": str(packets_root),
        "ledger_path": str(resolve_observation_replay_ledger_path(package_root, env=env)),
    }
    markdown = "\n".join(
        [
            "# rc87 Observation Replay Summary",
            "",
            f"- Packet count: {summary['packet_count']}",
            f"- Review-required packet count: {summary['review_required_count']}",
            f"- Mutation-refused packet count: {summary['mutation_refused_count']}",
            f"- Latest replay packet id: {summary['latest_replay_packet_id'] or '<none>'}",
        ]
    )
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=OBSERVATION_REPLAY_SUMMARY_FILENAME,
        markdown_name=OBSERVATION_REPLAY_SUMMARY_MARKDOWN,
        summary=summary,
        markdown=markdown,
    )
    return summary

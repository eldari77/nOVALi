from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


LEDGER_INDEX_SCHEMA_VERSION = "novali_ledger_index_v1"
MATERIALIZED_VIEW_SCHEMA_VERSION = "novali_materialized_view_v1"
DATA_AT_REST_CATALOG_SCHEMA_VERSION = "novali_data_at_rest_catalog_v1"
SPILL_POINTER_SCHEMA_VERSION = "novali_spill_pointer_v1"
RUNTIME_LOG_SEGMENT_INDEX_SCHEMA_VERSION = "novali_runtime_log_segment_index_v1"
RUNTIME_LOG_BUNDLE_INDEX_SCHEMA_VERSION = "novali_runtime_log_bundle_index_v1"
COLD_ARTIFACT_MANIFEST_SCHEMA_VERSION = "novali_cold_artifact_manifest_v1"
SPILL_SWEEPER_SCHEMA_VERSION = "novali_spill_sweeper_v1"
COLD_ARTIFACT_BACKLOG_SCHEMA_VERSION = "novali_cold_artifact_backlog_v1"
DEFAULT_RECENT_OFFSET_LIMIT = 1000
CATALOG_MAX_RESULTS = 200
SAFE_TEXT_MAX_CHARS = 240
DEFAULT_RUNTIME_LOG_SEGMENT_BYTES = 8 * 1024 * 1024
DEFAULT_RUNTIME_LOG_COLD_AGE_SECONDS = 20 * 60
DEFAULT_COLD_ARTIFACT_BYTES = 512 * 1024
DEFAULT_SPILL_SWEEPER_CADENCE_SECONDS = 5 * 60
DEFAULT_SPILL_SWEEPER_BUDGET_BYTES = 32 * 1024 * 1024
DEFAULT_SPILL_SWEEPER_MAX_RUNTIME_SEGMENTS = 4
DEFAULT_SPILL_SWEEPER_MAX_COLD_ARTIFACTS = 24
DEFAULT_SPILL_SWEEPER_SCAN_LIMIT = 300
DEFAULT_SPILL_SWEEPER_STALE_SECONDS = 2 * 60
DEFAULT_RUNTIME_LOG_BUNDLE_MAX_FILES = 256
DEFAULT_RUNTIME_LOG_BUNDLE_MAX_BYTES = 24 * 1024 * 1024

RAW_FIELD_DENYLIST = {
    "details",
    "prompt",
    "raw_prompt",
    "raw_provider_output",
    "provider_output",
    "artifact_body",
    "body",
    "content",
    "new_information_delta",
    "directive_text",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_dump(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, indent=2, ensure_ascii=False)


def _ledger_path(operator_root: str | Path, name: str) -> Path:
    return Path(operator_root) / "autonomy" / "ledgers" / f"{name}.jsonl"


def _index_path(operator_root: str | Path, name: str) -> Path:
    configured_spill = str(os.environ.get("NOVALI_DISK_SPILL_ROOT", "") or "").strip()
    if configured_spill:
        return Path(configured_spill) / "ledger_indexes" / f"{name}.index.json"
    return Path(operator_root) / "autonomy" / "ledger_indexes" / f"{name}.index.json"


def spill_root(state_root: str | Path) -> Path:
    configured = str(os.environ.get("NOVALI_DISK_SPILL_ROOT", "") or "").strip()
    if configured:
        return Path(configured)
    return Path(state_root) / "cache"


def materialized_views_root(state_root: str | Path) -> Path:
    return spill_root(state_root) / "views"


def data_at_rest_catalog_path(state_root: str | Path) -> Path:
    return spill_root(state_root) / "data_at_rest_catalog_latest.json"


def spill_sweeper_state_path(state_root: str | Path) -> Path:
    return spill_root(state_root) / "spill_sweeper_latest.json"


def cold_artifact_backlog_path(state_root: str | Path) -> Path:
    return spill_root(state_root) / "cold_artifact_backlog_latest.json"


def runtime_log_spill_root(state_root: str | Path) -> Path:
    return spill_root(state_root) / "runtime_logs"


def runtime_log_bundle_index_path(state_root: str | Path) -> Path:
    return runtime_log_spill_root(state_root) / "bundles" / "runtime_log_bundle_index_latest.json"


def workspace_artifact_spill_root(state_root: str | Path) -> Path:
    return spill_root(state_root) / "workspace_artifacts"


def spill_pointer_path_for(path: str | Path) -> Path:
    source = Path(path)
    return source.with_name(f"{source.name}.novali_spill_pointer.json")


def _safe_read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dump(payload) + "\n", encoding="utf-8")


def _short_ref(value: Any, *, prefix: str = "ref") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _source_signature(path: Path) -> dict[str, int]:
    try:
        stat = path.stat()
    except OSError:
        return {"source_size": 0, "source_mtime_ns": 0}
    return {
        "source_size": int(stat.st_size),
        "source_mtime_ns": int(getattr(stat, "st_mtime_ns", 0)),
    }


def _content_hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _relative_to_spill(state_root: str | Path, path: str | Path) -> str:
    try:
        return Path(path).resolve().relative_to(spill_root(state_root).resolve()).as_posix()
    except (OSError, ValueError):
        return ""


def _safe_source_relative_path(root: str | Path | None, path: str | Path | None) -> str:
    relative = _relative_path(root, path)
    return relative if relative and not _looks_absolute_path(relative) else ""


def _relative_path(root: str | Path | None, path: str | Path | None) -> str:
    if not root or not path:
        return ""
    try:
        root_path = Path(root).resolve()
        path_value = Path(path)
        if not path_value.is_absolute():
            return str(path_value).replace("\\", "/")
        return str(path_value.resolve().relative_to(root_path)).replace("\\", "/")
    except (OSError, ValueError):
        return ""


def _looks_absolute_path(value: str) -> bool:
    text = str(value or "")
    return bool(
        text.startswith("/")
        or text.startswith("\\")
        or (len(text) > 2 and text[1] == ":" and text[2] in {"\\", "/"})
    )


def _safe_text(value: Any, *, max_chars: int = SAFE_TEXT_MAX_CHARS) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    if not text:
        return ""
    if _looks_absolute_path(text):
        return _short_ref(text, prefix="path")
    if len(text) > max_chars:
        return text[: max(0, max_chars - 1)].rstrip() + "..."
    return text


def _safe_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    safe_keys = {
        "operation_id",
        "proposal_id",
        "action",
        "status",
        "result",
        "created_at",
        "generated_at",
        "completed_at",
        "selected_directive_track_id",
        "selected_deliverable_kind",
        "artifact_depth",
        "depth_iteration",
        "delta_focus_id",
        "delta_layer_id",
        "focus_rotation_state",
        "layer_rotation_state",
        "delta_materially_new",
        "delta_rejection_reason",
        "new_information_delta_signature",
        "directive_track_artifact_relative_path",
        "directive_track_progress_generated_at",
        "directive_work_program_state",
        "directive_dossier_required",
        "latest_directive_dossier_ref",
        "directive_dossier_artifact_relative_path",
        "directive_dossier_signature",
        "directive_dossier_materially_new",
        "directive_dossier_rejection_reason",
        "directive_dossier_progress_generated_at",
        "directive_source_coverage_state",
        "librarian_gap_reuse_decision",
        "librarian_gap_request_id",
        "librarian_gap_signature",
        "librarian_gap_state",
        "requested_pack_family",
        "source_dossier_ref",
        "local_pack_stage_result",
        "trusted_source_retrieval_blocker",
        "trusted_source_retrieval_validation_state",
        "capability_kind",
        "promotion_packet_ref",
        "meaningful_delta",
        "score",
        "pressure_band",
        "memory_smoothing_state",
        "oom_guard_state",
        "trusted_source_failure_class",
        "digest_source",
        "parse_outcome",
    }
    payload: dict[str, Any] = {}
    for key in safe_keys:
        if key in row:
            value = row.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                if isinstance(value, str) and _looks_absolute_path(value):
                    continue
                payload[key] = _safe_text(value) if isinstance(value, str) else value
    return payload


def _runtime_segment_index_path(state_root: str | Path, session_ref: str) -> Path:
    return runtime_log_spill_root(state_root) / str(session_ref or "session_unknown") / "runtime_log_segment_index_latest.json"


def _cold_artifact_manifest_path(state_root: str | Path, workspace_ref: str) -> Path:
    return workspace_artifact_spill_root(state_root) / str(workspace_ref or "workspace_unknown") / "cold_artifact_manifest_latest.json"


def _append_segment_index(
    *,
    state_root: str | Path,
    session_ref: str,
    entry: Mapping[str, Any],
) -> dict[str, Any]:
    path = _runtime_segment_index_path(state_root, session_ref)
    index = _safe_read_json(path)
    segments = [
        dict(item)
        for item in index.get("segments", [])
        if isinstance(item, Mapping)
    ]
    segments = [
        item
        for item in segments
        if str(item.get("segment_ref", "")) != str(entry.get("segment_ref", ""))
    ]
    segments.append(dict(entry))
    segments.sort(key=lambda item: str(item.get("created_at", "")))
    payload = {
        "schema_name": "NovaliRuntimeLogSegmentIndex",
        "schema_version": RUNTIME_LOG_SEGMENT_INDEX_SCHEMA_VERSION,
        "generated_at": _now(),
        "session_ref": session_ref,
        "segment_count": len(segments),
        "segments": segments,
    }
    _write_json(path, payload)
    return payload


def _append_runtime_log_bundle_index(
    *,
    state_root: str | Path,
    entry: Mapping[str, Any],
) -> dict[str, Any]:
    path = runtime_log_bundle_index_path(state_root)
    index = _safe_read_json(path)
    bundles = [
        dict(item)
        for item in index.get("bundles", [])
        if isinstance(item, Mapping)
    ]
    bundles.append(dict(entry))
    payload = {
        "schema_name": "NovaliRuntimeLogBundleIndex",
        "schema_version": RUNTIME_LOG_BUNDLE_INDEX_SCHEMA_VERSION,
        "generated_at": _now(),
        "bundle_count": len(bundles),
        "bundles": bundles[-500:],
    }
    _write_json(path, payload)
    return payload


def _append_cold_artifact_manifest(
    *,
    state_root: str | Path,
    workspace_ref: str,
    entry: Mapping[str, Any],
) -> dict[str, Any]:
    path = _cold_artifact_manifest_path(state_root, workspace_ref)
    manifest = _safe_read_json(path)
    artifacts = [
        dict(item)
        for item in manifest.get("artifacts", [])
        if isinstance(item, Mapping)
    ]
    artifacts = [
        item
        for item in artifacts
        if str(item.get("artifact_ref", "")) != str(entry.get("artifact_ref", ""))
    ]
    artifacts.append(dict(entry))
    artifacts.sort(key=lambda item: str(item.get("moved_at", "")), reverse=True)
    payload = {
        "schema_name": "NovaliColdArtifactManifest",
        "schema_version": COLD_ARTIFACT_MANIFEST_SCHEMA_VERSION,
        "generated_at": _now(),
        "workspace_ref": workspace_ref,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    _write_json(path, payload)
    return payload


def _write_spill_pointer(
    *,
    pointer_path: Path,
    source_kind: str,
    source_relative_path: str,
    spill_relative_path: str,
    content_hash: str,
    byte_count: int,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_name": "NovaliSpillPointer",
        "schema_version": SPILL_POINTER_SCHEMA_VERSION,
        "created_at": _now(),
        "source_kind": _safe_text(source_kind, max_chars=80),
        "source_relative_path": _safe_text(source_relative_path, max_chars=240),
        "spill_relative_path": _safe_text(spill_relative_path, max_chars=240),
        "content_hash": _safe_text(content_hash, max_chars=80),
        "byte_count": max(0, int(byte_count or 0)),
        "restore_status": "moved_to_spill",
        "read_status": "available",
    }
    if extra:
        for key, value in dict(extra).items():
            if key in RAW_FIELD_DENYLIST:
                continue
            if isinstance(value, str):
                payload[key] = _safe_text(value, max_chars=160)
            elif isinstance(value, (int, float, bool)) or value is None:
                payload[key] = value
    _write_json(pointer_path, payload)
    return payload


def _resolve_spill_relative_path(
    *,
    state_root: str | Path | None,
    spill_relative_path: str,
) -> Path:
    state_value = state_root or os.environ.get("NOVALI_STATE_ROOT", "") or "."
    return spill_root(state_value) / Path(str(spill_relative_path or ""))


def resolve_spill_pointer_path(
    pointer_path: str | Path,
    *,
    state_root: str | Path | None = None,
) -> Path | None:
    payload = _safe_read_json(Path(pointer_path))
    if payload.get("schema_version") != SPILL_POINTER_SCHEMA_VERSION:
        return None
    relative = str(payload.get("spill_relative_path", "") or "").strip()
    if not relative or _looks_absolute_path(relative):
        return None
    target = _resolve_spill_relative_path(
        state_root=state_root,
        spill_relative_path=relative,
    )
    return target if target.exists() else None


def _emit_spill_event(event_name: str, payload: Mapping[str, Any]) -> None:
    try:
        from .observability import enrichment

        if event_name == "runtime_log_segment_moved":
            enrichment.record_runtime_log_segment_moved(payload)
        elif event_name == "workspace_artifact_cold_moved":
            enrichment.record_workspace_artifact_cold_moved(payload)
    except Exception:
        return


def move_cold_runtime_log_segment(
    log_path: str | Path,
    *,
    state_root: str | Path,
    session_id: str = "",
    force: bool = False,
    max_bytes: int = DEFAULT_RUNTIME_LOG_SEGMENT_BYTES,
    cold_age_seconds: int = DEFAULT_RUNTIME_LOG_COLD_AGE_SECONDS,
    keep_active_tail: bool = False,
) -> dict[str, Any]:
    source = Path(log_path)
    if not source.exists() or not source.is_file():
        return {"ok": False, "result": "missing_source", "source_kind": "runtime_log_segment"}
    try:
        stat = source.stat()
    except OSError:
        return {"ok": False, "result": "stat_failed", "source_kind": "runtime_log_segment"}
    age_seconds = max(0.0, (datetime.now(timezone.utc).timestamp() - float(stat.st_mtime)))
    if not force and int(stat.st_size) < int(max_bytes or DEFAULT_RUNTIME_LOG_SEGMENT_BYTES) and age_seconds < int(cold_age_seconds or DEFAULT_RUNTIME_LOG_COLD_AGE_SECONDS):
        return {"ok": True, "result": "skipped_hot", "source_kind": "runtime_log_segment"}
    session_ref = _short_ref(session_id or source.stem, prefix="session") or "session_unknown"
    segment_ref = _short_ref(
        f"{source.name}|{stat.st_size}|{getattr(stat, 'st_mtime_ns', 0)}",
        prefix="logseg",
    )
    target = runtime_log_spill_root(state_root) / session_ref / "segments" / f"{segment_ref}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    content_hash = _content_hash_file(source)
    shutil.move(str(source), str(target))
    if keep_active_tail:
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("", encoding="utf-8")
    pointer_path = spill_pointer_path_for(source)
    pointer_payload = _write_spill_pointer(
        pointer_path=pointer_path,
        source_kind="runtime_log_segment",
        source_relative_path=source.name,
        spill_relative_path=_relative_to_spill(state_root, target),
        content_hash=content_hash,
        byte_count=int(stat.st_size),
        extra={
            "session_ref": session_ref,
            "segment_ref": segment_ref,
            "storage_state": "moved_to_spill",
        },
    )
    segment_entry = {
        "segment_ref": segment_ref,
        "session_ref": session_ref,
        "created_at": pointer_payload["created_at"],
        "spill_relative_path": pointer_payload["spill_relative_path"],
        "pointer_ref": _short_ref(str(pointer_path), prefix="ptr"),
        "byte_count": int(stat.st_size),
        "content_hash": content_hash,
        "storage_state": "moved_to_spill",
    }
    _append_segment_index(state_root=state_root, session_ref=session_ref, entry=segment_entry)
    result = {
        "ok": True,
        "result": "moved",
        "source_kind": "runtime_log_segment",
        "session_ref": session_ref,
        "segment_ref": segment_ref,
        "spill_relative_path": pointer_payload["spill_relative_path"],
        "pointer_manifest_path": str(pointer_path),
        "byte_count": int(stat.st_size),
        "storage_state": "moved_to_spill",
    }
    _emit_spill_event("runtime_log_segment_moved", result)
    return result


def bundle_small_runtime_logs(
    log_paths: list[Path],
    *,
    state_root: str | Path,
    runtime_event_log_path: str | Path | None = None,
    max_files: int = DEFAULT_RUNTIME_LOG_BUNDLE_MAX_FILES,
    max_bytes: int = DEFAULT_RUNTIME_LOG_BUNDLE_MAX_BYTES,
    segment_bytes: int = DEFAULT_RUNTIME_LOG_SEGMENT_BYTES,
    cold_age_seconds: int = DEFAULT_RUNTIME_LOG_COLD_AGE_SECONDS,
) -> dict[str, Any]:
    active_key = ""
    if runtime_event_log_path:
        try:
            active_key = str(Path(runtime_event_log_path).resolve())
        except OSError:
            active_key = str(runtime_event_log_path)
    selected: list[Path] = []
    selected_bytes = 0
    now_ts = datetime.now(timezone.utc).timestamp()
    for path in sorted(log_paths, key=lambda item: (item.stat().st_mtime if item.exists() else 0, item.name)):
        if len(selected) >= max(1, int(max_files or 1)):
            break
        try:
            resolved = path.resolve()
            stat = resolved.stat()
        except OSError:
            continue
        if str(resolved) == active_key:
            continue
        if not resolved.is_file() or resolved.suffix != ".jsonl":
            continue
        byte_count = int(stat.st_size)
        if byte_count <= 0 or byte_count >= int(segment_bytes or DEFAULT_RUNTIME_LOG_SEGMENT_BYTES):
            continue
        age_seconds = max(0.0, now_ts - float(stat.st_mtime))
        if age_seconds < int(cold_age_seconds or 0):
            continue
        if selected_bytes + byte_count > max(1, int(max_bytes or 1)):
            continue
        selected.append(resolved)
        selected_bytes += byte_count
    if not selected:
        return {
            "ok": True,
            "result": "no_eligible_data",
            "source_kind": "runtime_log_bundle",
            "runtime_log_bundle_count": 0,
            "runtime_log_bundle_file_count": 0,
            "byte_count": 0,
        }
    bundle_ref = _short_ref(
        "|".join(f"{path.name}:{path.stat().st_size}" for path in selected),
        prefix="logbundle",
    )
    target = runtime_log_spill_root(state_root) / "bundles" / f"{bundle_ref}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    sources: list[dict[str, Any]] = []
    row_count_total = 0
    with target.open("wb") as output:
        for source in selected:
            try:
                stat = source.stat()
                content = source.read_bytes()
            except OSError:
                continue
            offset_start = output.tell()
            output.write(content)
            if content and not content.endswith(b"\n"):
                output.write(b"\n")
            offset_end = output.tell()
            content_hash = hashlib.sha256(content).hexdigest()
            session_ref = _short_ref(source.stem, prefix="session") or "session_unknown"
            try:
                row_count = sum(1 for line in content.splitlines() if line.strip())
            except Exception:
                row_count = 0
            row_count_total += row_count
            pointer_path = spill_pointer_path_for(source)
            pointer_payload = _write_spill_pointer(
                pointer_path=pointer_path,
                source_kind="runtime_log_bundle",
                source_relative_path=source.name,
                spill_relative_path=_relative_to_spill(state_root, target),
                content_hash=content_hash,
                byte_count=int(stat.st_size),
                extra={
                    "session_ref": session_ref,
                    "bundle_ref": bundle_ref,
                    "offset_start": offset_start,
                    "offset_end": offset_end,
                    "row_count": row_count,
                    "storage_state": "bundled_to_spill",
                },
            )
            sources.append(
                {
                    "source_name": source.name,
                    "session_ref": session_ref,
                    "bundle_ref": bundle_ref,
                    "offset_start": offset_start,
                    "offset_end": offset_end,
                    "byte_count": int(stat.st_size),
                    "content_hash": content_hash,
                    "row_count": row_count,
                    "pointer_ref": _short_ref(str(pointer_path), prefix="ptr"),
                    "spill_relative_path": pointer_payload["spill_relative_path"],
                }
            )
            try:
                source.unlink()
            except OSError:
                pass
    bundle_bytes = int(target.stat().st_size) if target.exists() else selected_bytes
    bundle_entry = {
        "bundle_ref": bundle_ref,
        "created_at": _now(),
        "spill_relative_path": _relative_to_spill(state_root, target),
        "byte_count": bundle_bytes,
        "file_count": len(sources),
        "row_count": row_count_total,
        "storage_state": "bundled_to_spill",
        "sources": sources,
    }
    _append_runtime_log_bundle_index(state_root=state_root, entry=bundle_entry)
    result = {
        "ok": True,
        "result": "moved",
        "source_kind": "runtime_log_bundle",
        "runtime_log_bundle_count": 1,
        "runtime_log_bundle_file_count": len(sources),
        "bundle_ref": bundle_ref,
        "spill_relative_path": bundle_entry["spill_relative_path"],
        "byte_count": bundle_bytes,
        "row_count": row_count_total,
    }
    return result


def _read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)
    except OSError:
        return []
    return rows


def read_runtime_events_with_spill(
    primary_path: str | Path | None,
    *,
    state_root: str | Path | None = None,
    workspace_id: str = "",
    session_id: str = "",
    directive_id: str = "",
) -> list[dict[str, Any]]:
    candidate_paths: list[Path] = []
    seen_paths: set[str] = set()

    def _add(path: Path | None) -> None:
        if path is None:
            return
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        key = str(resolved)
        if key in seen_paths:
            return
        if resolved.exists() and resolved.is_file():
            seen_paths.add(key)
            candidate_paths.append(resolved)

    primary = Path(primary_path) if primary_path else None
    _add(primary)
    if primary is not None:
        _add(resolve_spill_pointer_path(spill_pointer_path_for(primary), state_root=state_root))
        if primary.parent.exists():
            for pointer in sorted(primary.parent.glob("*.novali_spill_pointer.json")):
                _add(resolve_spill_pointer_path(pointer, state_root=state_root))
    if session_id:
        session_ref = _short_ref(session_id, prefix="session")
        index = _safe_read_json(_runtime_segment_index_path(state_root or os.environ.get("NOVALI_STATE_ROOT", "") or ".", session_ref))
        for item in index.get("segments", []) if isinstance(index.get("segments", []), list) else []:
            if not isinstance(item, Mapping):
                continue
            relative = str(item.get("spill_relative_path", "") or "")
            if relative and not _looks_absolute_path(relative):
                _add(_resolve_spill_relative_path(state_root=state_root, spill_relative_path=relative))
        bundle_index = _safe_read_json(
            runtime_log_bundle_index_path(state_root or os.environ.get("NOVALI_STATE_ROOT", "") or ".")
        )
        for bundle in bundle_index.get("bundles", []) if isinstance(bundle_index.get("bundles", []), list) else []:
            if not isinstance(bundle, Mapping):
                continue
            sources = bundle.get("sources", [])
            if not isinstance(sources, list):
                continue
            if not any(
                isinstance(source, Mapping)
                and str(source.get("session_ref", "") or "") == session_ref
                for source in sources
            ):
                continue
            relative = str(bundle.get("spill_relative_path", "") or "")
            if relative and not _looks_absolute_path(relative):
                _add(_resolve_spill_relative_path(state_root=state_root, spill_relative_path=relative))

    rows: list[dict[str, Any]] = []
    seen_rows: set[str] = set()
    for path in candidate_paths:
        for payload in _read_jsonl_rows(path):
            payload_workspace_id = str(payload.get("workspace_id", "")).strip()
            payload_session_id = str(payload.get("session_id", "")).strip()
            payload_directive_id = str(payload.get("directive_id", "")).strip()
            keep = False
            if workspace_id and payload_workspace_id == workspace_id:
                keep = True
            elif session_id and payload_session_id == session_id:
                keep = True
            elif directive_id and payload_directive_id == directive_id and (
                not workspace_id or payload_workspace_id == workspace_id
            ):
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


def _is_protected_workspace_artifact(relative_path: str) -> bool:
    rel = str(relative_path or "").replace("\\", "/").strip().strip("/")
    if not rel:
        return True
    parts = set(part.lower() for part in Path(rel).parts)
    name = Path(rel).name.lower()
    if name.endswith(".novali_spill_pointer.json"):
        return True
    if parts.intersection({"src", "tests", ".git", "__pycache__"}):
        return True
    if name.endswith("_latest.json") or name in {
        "governed_execution_session_latest.json",
        "governed_execution_controller_latest.json",
    }:
        return True
    if "checkpoint" in name or "controller" in name or "session_latest" in name:
        return True
    return False


def move_cold_workspace_artifact(
    *,
    workspace_root: str | Path,
    relative_path: str,
    state_root: str | Path,
    force: bool = False,
    min_bytes: int = DEFAULT_COLD_ARTIFACT_BYTES,
    cold_age_seconds: int = DEFAULT_RUNTIME_LOG_COLD_AGE_SECONDS,
) -> dict[str, Any]:
    workspace = Path(workspace_root)
    rel = str(relative_path or "").replace("\\", "/").strip().strip("/")
    if _looks_absolute_path(rel) or _is_protected_workspace_artifact(rel):
        return {"ok": True, "result": "skipped_protected", "source_kind": "cold_workspace_artifact"}
    source = workspace / Path(rel)
    try:
        resolved_workspace = workspace.resolve()
        resolved_source = source.resolve()
        resolved_source.relative_to(resolved_workspace)
    except (OSError, ValueError):
        return {"ok": False, "result": "outside_workspace_root", "source_kind": "cold_workspace_artifact"}
    if not resolved_source.exists() or not resolved_source.is_file():
        return {"ok": False, "result": "missing_source", "source_kind": "cold_workspace_artifact"}
    stat = resolved_source.stat()
    age_seconds = max(0.0, (datetime.now(timezone.utc).timestamp() - float(stat.st_mtime)))
    if not force and int(stat.st_size) < int(min_bytes or DEFAULT_COLD_ARTIFACT_BYTES) and age_seconds < int(cold_age_seconds or DEFAULT_RUNTIME_LOG_COLD_AGE_SECONDS):
        return {"ok": True, "result": "skipped_hot", "source_kind": "cold_workspace_artifact"}
    workspace_ref = _short_ref(workspace.name or str(workspace), prefix="workspace") or "workspace_unknown"
    artifact_ref = _short_ref(f"{workspace_ref}|{rel}|{stat.st_size}|{getattr(stat, 'st_mtime_ns', 0)}", prefix="artifact")
    target = workspace_artifact_spill_root(state_root) / workspace_ref / artifact_ref / Path(rel).name
    target.parent.mkdir(parents=True, exist_ok=True)
    content_hash = _content_hash_file(resolved_source)
    shutil.move(str(resolved_source), str(target))
    pointer_path = spill_pointer_path_for(resolved_source)
    pointer_payload = _write_spill_pointer(
        pointer_path=pointer_path,
        source_kind="cold_workspace_artifact",
        source_relative_path=rel,
        spill_relative_path=_relative_to_spill(state_root, target),
        content_hash=content_hash,
        byte_count=int(stat.st_size),
        extra={
            "workspace_ref": workspace_ref,
            "artifact_ref": artifact_ref,
            "storage_state": "moved_to_spill",
        },
    )
    entry = {
        "artifact_ref": artifact_ref,
        "workspace_ref": workspace_ref,
        "moved_at": pointer_payload["created_at"],
        "title": _safe_text(Path(rel).stem.replace("_", " "), max_chars=120),
        "source_relative_path": rel,
        "spill_relative_path": pointer_payload["spill_relative_path"],
        "pointer_ref": _short_ref(str(pointer_path), prefix="ptr"),
        "byte_count": int(stat.st_size),
        "content_hash": content_hash,
        "storage_state": "moved_to_spill",
    }
    _append_cold_artifact_manifest(state_root=state_root, workspace_ref=workspace_ref, entry=entry)
    result = {
        "ok": True,
        "result": "moved",
        "source_kind": "cold_workspace_artifact",
        "workspace_ref": workspace_ref,
        "artifact_ref": artifact_ref,
        "spill_relative_path": pointer_payload["spill_relative_path"],
        "pointer_manifest_path": str(pointer_path),
        "byte_count": int(stat.st_size),
        "storage_state": "moved_to_spill",
    }
    _emit_spill_event("workspace_artifact_cold_moved", result)
    return result


def perform_cold_storage_maintenance(
    *,
    state_root: str | Path,
    package_root: str | Path | None = None,
    operator_root: str | Path | None = None,
    workspace_root: str | Path | None = None,
    runtime_event_log_path: str | Path | None = None,
    max_artifacts: int = 12,
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    moved_bytes = 0
    runtime_result: dict[str, Any] = {}
    if runtime_event_log_path:
        runtime_result = move_cold_runtime_log_segment(
            runtime_event_log_path,
            state_root=state_root,
            session_id=Path(runtime_event_log_path).stem,
            keep_active_tail=True,
        )
        if runtime_result.get("result") == "moved":
            moved_bytes += int(runtime_result.get("byte_count", 0) or 0)
            actions.append(
                {
                    "source_kind": "runtime_log_segment",
                    "result": runtime_result.get("result"),
                    "byte_count": int(runtime_result.get("byte_count", 0) or 0),
                    "ref": _safe_text(runtime_result.get("segment_ref", "")),
                }
            )
    artifact_moves = 0
    artifact_skips = 0
    if workspace_root:
        workspace = Path(workspace_root)
        if workspace.exists():
            candidate_roots = [
                workspace / "artifacts" / "history",
                workspace / "artifacts" / "cycles",
                workspace / "artifacts" / "operator_proof",
                workspace / "docs",
                workspace / "plans",
                workspace / "artifacts",
            ]
            seen_candidates: set[str] = set()
            for candidate_root in candidate_roots:
                if artifact_moves >= max(0, int(max_artifacts or 0)):
                    break
                if not candidate_root.exists():
                    continue
                try:
                    iterator = candidate_root.rglob("*")
                    for path in iterator:
                        if artifact_moves >= max(0, int(max_artifacts or 0)):
                            break
                        if not path.is_file():
                            continue
                        try:
                            key = str(path.resolve())
                        except OSError:
                            key = str(path)
                        if key in seen_candidates:
                            continue
                        seen_candidates.add(key)
                        rel = _safe_source_relative_path(workspace, path)
                        if not rel or _is_protected_workspace_artifact(rel):
                            continue
                        result = move_cold_workspace_artifact(
                            workspace_root=workspace,
                            relative_path=rel,
                            state_root=state_root,
                        )
                        if result.get("result") == "moved":
                            artifact_moves += 1
                            moved_bytes += int(result.get("byte_count", 0) or 0)
                            actions.append(
                                {
                                    "source_kind": "cold_workspace_artifact",
                                    "result": result.get("result"),
                                    "byte_count": int(result.get("byte_count", 0) or 0),
                                    "ref": _safe_text(result.get("artifact_ref", "")),
                                }
                            )
                        elif str(result.get("result", "")).startswith("skipped"):
                            artifact_skips += 1
                except OSError:
                    continue
    status = spill_status(state_root)
    catalog_refresh_result = "not_requested"
    if actions and package_root and operator_root:
        try:
            build_data_at_rest_catalog(
                package_root=package_root,
                operator_root=operator_root,
                state_root=state_root,
                workspace_root=workspace_root,
            )
            catalog_refresh_result = "refreshed"
        except Exception:
            catalog_refresh_result = "refresh_failed"
    payload = {
        "schema_name": "NovaliColdStorageMaintenance",
        "schema_version": "novali_cold_storage_maintenance_v1",
        "generated_at": _now(),
        "result": "moved" if actions else "no_eligible_cold_data",
        "spill_mode": "move_cold",
        "moved_action_count": len(actions),
        "moved_bytes": moved_bytes,
        "runtime_log_result": str(runtime_result.get("result", "not_checked") or "not_checked"),
        "artifact_move_count": artifact_moves,
        "artifact_skip_count": artifact_skips,
        "catalog_refresh_result": catalog_refresh_result,
        "actions": actions,
        **{
            key: status.get(key)
            for key in (
                "runtime_log_spill_bytes",
                "cold_artifact_spill_bytes",
                "disk_spill_bytes",
                "spill_volume_bytes",
                "spill_pointer_count",
                "spill_backlog_count",
                "latest_spill_result",
            )
        },
    }
    try:
        _write_json(spill_root(state_root) / "cold_storage_maintenance_latest.json", payload)
    except Exception:
        pass
    return payload


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _seconds_until(value: Any) -> float:
    parsed = _parse_time(value)
    if parsed is None:
        return 0.0
    return (parsed - datetime.now(timezone.utc)).total_seconds()


def _seconds_since(value: Any) -> float:
    parsed = _parse_time(value)
    if parsed is None:
        return 0.0
    return (datetime.now(timezone.utc) - parsed).total_seconds()


def spill_sweeper_due(state_root: str | Path) -> bool:
    payload = _safe_read_json(spill_sweeper_state_path(state_root))
    state = str(payload.get("spill_sweeper_state", "") or "")
    if state == "active":
        stale_after = int(
            os.environ.get(
                "NOVALI_SPILL_SWEEPER_STALE_SECONDS",
                str(DEFAULT_SPILL_SWEEPER_STALE_SECONDS),
            )
            or DEFAULT_SPILL_SWEEPER_STALE_SECONDS
        )
        return _seconds_since(payload.get("last_spill_started_at")) > max(1, stale_after)
    return _seconds_until(payload.get("next_spill_due_at")) <= 0


def record_spill_sweeper_failed(
    state_root: str | Path,
    *,
    reason: str,
    cadence_seconds: int = DEFAULT_SPILL_SWEEPER_CADENCE_SECONDS,
) -> dict[str, Any]:
    previous = _safe_read_json(spill_sweeper_state_path(state_root))
    payload = {
        "schema_name": "NovaliSpillSweeperState",
        "schema_version": SPILL_SWEEPER_SCHEMA_VERSION,
        "generated_at": _now(),
        "spill_sweeper_state": "idle",
        "spill_activity_state": "failed",
        "result": "failed",
        "failure_reason": _safe_text(reason, max_chars=80),
        "last_spill_started_at": str(previous.get("last_spill_started_at", "") or ""),
        "last_spill_finished_at": _now(),
        "next_spill_due_at": _iso_after(cadence_seconds),
        "spill_budget_bytes": int(previous.get("spill_budget_bytes", DEFAULT_SPILL_SWEEPER_BUDGET_BYTES) or 0),
        "spill_budget_used_bytes": int(previous.get("spill_budget_used_bytes", 0) or 0),
    }
    _write_json(spill_sweeper_state_path(state_root), payload)
    _emit_sweeper_pass(payload)
    return payload


def _iso_after(seconds: int) -> str:
    now = datetime.now(timezone.utc)
    return datetime.fromtimestamp(now.timestamp() + max(1, int(seconds or 1)), timezone.utc).isoformat().replace("+00:00", "Z")


def _runtime_log_candidates(
    *,
    package_root: str | Path | None = None,
    runtime_event_log_path: str | Path | None = None,
    max_candidates: int = 128,
) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        if len(candidates) >= max(1, int(max_candidates or 1)):
            return
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        key = str(resolved)
        if key in seen:
            return
        if resolved.exists() and resolved.is_file() and resolved.suffix == ".jsonl":
            seen.add(key)
            candidates.append(resolved)

    if runtime_event_log_path:
        _add(Path(runtime_event_log_path))
    if package_root:
        root = Path(package_root) / "runtime_data" / "logs" / "runtime_events"
        try:
            for path in sorted(root.glob("*.jsonl")):
                _add(path)
                if len(candidates) >= max(1, int(max_candidates or 1)):
                    break
        except OSError:
            pass
    candidates.sort(
        key=lambda path: (
            -int(path.stat().st_size if path.exists() else 0),
            path.name,
        )
    )
    return candidates


def _candidate_is_cold(path: Path, *, min_bytes: int, cold_age_seconds: int) -> bool:
    try:
        stat = path.stat()
    except OSError:
        return False
    age_seconds = max(0.0, datetime.now(timezone.utc).timestamp() - float(stat.st_mtime))
    return int(stat.st_size) >= int(min_bytes or 0) or age_seconds >= int(cold_age_seconds or 0)


def _bounded_file_scan(roots: list[Path], *, max_entries: int) -> tuple[list[Path], int, bool]:
    files: list[Path] = []
    queue: deque[Path] = deque(path for path in roots if path.exists())
    scanned = 0
    limit = max(1, int(max_entries or 1))
    while queue and scanned < limit:
        current = queue.popleft()
        try:
            children = sorted(current.iterdir(), key=lambda path: path.name)
        except OSError:
            continue
        for child in children:
            scanned += 1
            if scanned > limit:
                return files, scanned, True
            try:
                if child.is_dir():
                    queue.append(child)
                elif child.is_file():
                    files.append(child)
            except OSError:
                continue
    return files, scanned, bool(queue)


def refresh_cold_artifact_backlog(
    *,
    state_root: str | Path,
    workspace_root: str | Path | None = None,
    min_bytes: int = DEFAULT_COLD_ARTIFACT_BYTES,
    cold_age_seconds: int = DEFAULT_RUNTIME_LOG_COLD_AGE_SECONDS,
    max_scan: int = DEFAULT_SPILL_SWEEPER_SCAN_LIMIT,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    scanned = 0
    scan_limited = False
    workspace = Path(workspace_root) if workspace_root else None
    if workspace and workspace.exists():
        candidate_roots = [
            workspace / "artifacts" / "history",
            workspace / "artifacts" / "cycles",
            workspace / "artifacts" / "operator_proof",
            workspace / "docs",
            workspace / "plans",
            workspace / "artifacts",
        ]
        seen: set[str] = set()
        paths, scanned, scan_limited = _bounded_file_scan(
            candidate_roots,
            max_entries=max_scan,
        )
        for path in paths:
            try:
                rel = _safe_source_relative_path(workspace, path)
                if not rel or _is_protected_workspace_artifact(rel):
                    continue
                key = str(path.resolve())
                stat = path.stat()
            except OSError:
                continue
            if key in seen:
                continue
            seen.add(key)
            age_seconds = max(0.0, datetime.now(timezone.utc).timestamp() - float(stat.st_mtime))
            if int(stat.st_size) < int(min_bytes or 0) and age_seconds < int(cold_age_seconds or 0):
                continue
            entries.append(
                {
                    "artifact_ref": _short_ref(
                        f"{workspace.name}|{rel}|{stat.st_size}|{getattr(stat, 'st_mtime_ns', 0)}",
                        prefix="artifact",
                    ),
                    "workspace_ref": _short_ref(workspace.name or str(workspace), prefix="workspace"),
                    "source_relative_path": rel,
                    "byte_count": int(stat.st_size),
                    "source_mtime_ns": int(getattr(stat, "st_mtime_ns", 0)),
                    "eligibility_reason": "size" if int(stat.st_size) >= int(min_bytes or 0) else "age",
                }
            )
    entries.sort(key=lambda item: (-int(item.get("byte_count", 0) or 0), str(item.get("source_relative_path", ""))))
    payload = {
        "schema_name": "NovaliColdArtifactBacklog",
        "schema_version": COLD_ARTIFACT_BACKLOG_SCHEMA_VERSION,
        "generated_at": _now(),
        "workspace_ref": _short_ref(workspace.name if workspace else "", prefix="workspace") if workspace else "",
        "backlog_count": len(entries),
        "backlog_bytes": sum(int(item.get("byte_count", 0) or 0) for item in entries),
        "scan_limited": scan_limited,
        "scanned_file_count": scanned,
        "entries": entries,
    }
    _write_json(cold_artifact_backlog_path(state_root), payload)
    return payload


def _load_cold_artifact_backlog(state_root: str | Path) -> dict[str, Any]:
    payload = _safe_read_json(cold_artifact_backlog_path(state_root))
    if payload.get("schema_version") != COLD_ARTIFACT_BACKLOG_SCHEMA_VERSION:
        return {}
    return payload


def _write_cold_artifact_backlog(
    *,
    state_root: str | Path,
    workspace_ref: str = "",
    entries: list[Mapping[str, Any]],
    scan_limited: bool = False,
    scanned_file_count: int = 0,
) -> dict[str, Any]:
    clean_entries = [dict(item) for item in entries if isinstance(item, Mapping)]
    payload = {
        "schema_name": "NovaliColdArtifactBacklog",
        "schema_version": COLD_ARTIFACT_BACKLOG_SCHEMA_VERSION,
        "generated_at": _now(),
        "workspace_ref": _safe_text(workspace_ref),
        "backlog_count": len(clean_entries),
        "backlog_bytes": sum(int(item.get("byte_count", 0) or 0) for item in clean_entries),
        "scan_limited": bool(scan_limited),
        "scanned_file_count": int(scanned_file_count or 0),
        "entries": clean_entries,
    }
    _write_json(cold_artifact_backlog_path(state_root), payload)
    return payload


def _backlog_entries(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        return []
    return [dict(item) for item in entries if isinstance(item, Mapping)]


def _emit_sweeper_pass(payload: Mapping[str, Any]) -> None:
    try:
        from .observability import enrichment

        enrichment.record_spill_sweeper_pass(payload)
    except Exception:
        return


def run_active_spill_sweeper(
    *,
    state_root: str | Path,
    package_root: str | Path | None = None,
    operator_root: str | Path | None = None,
    workspace_root: str | Path | None = None,
    runtime_event_log_path: str | Path | None = None,
    force: bool = False,
    enabled: bool | None = None,
    cadence_seconds: int = DEFAULT_SPILL_SWEEPER_CADENCE_SECONDS,
    spill_budget_bytes: int = DEFAULT_SPILL_SWEEPER_BUDGET_BYTES,
    runtime_log_segment_bytes: int = DEFAULT_RUNTIME_LOG_SEGMENT_BYTES,
    cold_artifact_min_bytes: int = DEFAULT_COLD_ARTIFACT_BYTES,
    cold_age_seconds: int = DEFAULT_RUNTIME_LOG_COLD_AGE_SECONDS,
    max_runtime_segments: int = DEFAULT_SPILL_SWEEPER_MAX_RUNTIME_SEGMENTS,
    max_artifacts: int = DEFAULT_SPILL_SWEEPER_MAX_COLD_ARTIFACTS,
) -> dict[str, Any]:
    if enabled is None:
        enabled = str(os.environ.get("NOVALI_ACTIVE_SPILL_SWEEPER_ENABLED", "true")).strip().lower() not in {"0", "false", "no", "off"}
    state_path = spill_sweeper_state_path(state_root)
    previous = _safe_read_json(state_path)
    if not enabled:
        payload = {
            "schema_name": "NovaliSpillSweeperState",
            "schema_version": SPILL_SWEEPER_SCHEMA_VERSION,
            "generated_at": _now(),
            "spill_sweeper_state": "disabled",
            "spill_activity_state": "idle",
            "next_spill_due_at": _iso_after(cadence_seconds),
            "spill_budget_bytes": int(spill_budget_bytes or 0),
            "spill_budget_used_bytes": 0,
        }
        _write_json(state_path, payload)
        return {**spill_status(state_root), **payload}
    if not force and previous and _seconds_until(previous.get("next_spill_due_at")) > 0:
        state = str(previous.get("spill_sweeper_state", "") or "")
        if state != "active" or not spill_sweeper_due(state_root):
            return {
                **spill_status(state_root),
                **previous,
                "spill_sweeper_state": "idle",
                "spill_activity_state": "idle"
                if str(previous.get("spill_activity_state", "") or "") == "active"
                else str(previous.get("spill_activity_state", "idle") or "idle"),
            }

    started_at = _now()
    active_payload = {
        "schema_name": "NovaliSpillSweeperState",
        "schema_version": SPILL_SWEEPER_SCHEMA_VERSION,
        "generated_at": started_at,
        "spill_sweeper_state": "active",
        "spill_activity_state": "active",
        "last_spill_started_at": started_at,
        "next_spill_due_at": _iso_after(cadence_seconds),
        "spill_budget_bytes": int(spill_budget_bytes or 0),
        "spill_budget_used_bytes": 0,
    }
    _write_json(state_path, active_payload)

    actions: list[dict[str, Any]] = []
    used_bytes = 0
    runtime_moves = 0
    runtime_bundle_count = 0
    runtime_bundle_file_count = 0
    runtime_bundle_bytes = 0
    artifact_moves = 0
    budget = max(0, int(spill_budget_bytes or 0))
    runtime_log_active_tail_bytes = 0

    runtime_candidates = _runtime_log_candidates(
        package_root=package_root,
        runtime_event_log_path=runtime_event_log_path,
    )
    for log_path in runtime_candidates:
        try:
            runtime_log_active_tail_bytes += int(log_path.stat().st_size)
        except OSError:
            continue
    for log_path in runtime_candidates:
        if runtime_moves >= max(0, int(max_runtime_segments or 0)):
            break
        try:
            byte_count = int(log_path.stat().st_size)
        except OSError:
            continue
        if budget and used_bytes + byte_count > budget:
            continue
        if not _candidate_is_cold(
            log_path,
            min_bytes=runtime_log_segment_bytes,
            cold_age_seconds=cold_age_seconds,
        ):
            continue
        result = move_cold_runtime_log_segment(
            log_path,
            state_root=state_root,
            session_id=log_path.stem,
            max_bytes=runtime_log_segment_bytes,
            cold_age_seconds=cold_age_seconds,
            keep_active_tail=True,
        )
        if result.get("result") == "moved":
            runtime_moves += 1
            moved_bytes = int(result.get("byte_count", 0) or 0)
            used_bytes += moved_bytes
            actions.append(
                {
                    "source_kind": "runtime_log_segment",
                    "result": "moved",
                    "byte_count": moved_bytes,
                    "ref": _safe_text(result.get("segment_ref", "")),
                }
            )

    active_runtime_key = ""
    if runtime_event_log_path:
        try:
            active_runtime_key = str(Path(runtime_event_log_path).resolve())
        except OSError:
            active_runtime_key = str(runtime_event_log_path)
    small_file_backlog_count = 0
    for candidate in runtime_candidates:
        try:
            resolved_candidate = candidate.resolve()
            candidate_size = int(resolved_candidate.stat().st_size)
        except OSError:
            continue
        if str(resolved_candidate) == active_runtime_key:
            continue
        if 0 < candidate_size < int(runtime_log_segment_bytes or DEFAULT_RUNTIME_LOG_SEGMENT_BYTES) and _candidate_is_cold(
            resolved_candidate,
            min_bytes=runtime_log_segment_bytes,
            cold_age_seconds=cold_age_seconds,
        ):
            small_file_backlog_count += 1

    bundle_budget = (
        max(0, min(DEFAULT_RUNTIME_LOG_BUNDLE_MAX_BYTES, budget - used_bytes))
        if budget
        else DEFAULT_RUNTIME_LOG_BUNDLE_MAX_BYTES
    )
    if bundle_budget > 0:
        bundle_result = bundle_small_runtime_logs(
            runtime_candidates,
            state_root=state_root,
            runtime_event_log_path=runtime_event_log_path,
            max_files=int(
                os.environ.get(
                    "NOVALI_RUNTIME_LOG_BUNDLE_MAX_FILES",
                    str(DEFAULT_RUNTIME_LOG_BUNDLE_MAX_FILES),
                )
                or DEFAULT_RUNTIME_LOG_BUNDLE_MAX_FILES
            ),
            max_bytes=bundle_budget,
            segment_bytes=runtime_log_segment_bytes,
            cold_age_seconds=cold_age_seconds,
        )
        if bundle_result.get("result") == "moved":
            runtime_bundle_count = int(bundle_result.get("runtime_log_bundle_count", 0) or 0)
            runtime_bundle_file_count = int(bundle_result.get("runtime_log_bundle_file_count", 0) or 0)
            runtime_bundle_bytes = int(bundle_result.get("byte_count", 0) or 0)
            used_bytes += runtime_bundle_bytes
            actions.append(
                {
                    "source_kind": "runtime_log_bundle",
                    "result": "moved",
                    "byte_count": runtime_bundle_bytes,
                    "ref": _safe_text(bundle_result.get("bundle_ref", "")),
                }
            )

    backlog = _load_cold_artifact_backlog(state_root)
    if not _backlog_entries(backlog):
        backlog = refresh_cold_artifact_backlog(
            state_root=state_root,
            workspace_root=workspace_root,
            min_bytes=cold_artifact_min_bytes,
            cold_age_seconds=cold_age_seconds,
            max_scan=int(
                os.environ.get(
                    "NOVALI_SPILL_SWEEPER_BACKLOG_SCAN_LIMIT",
                    str(DEFAULT_SPILL_SWEEPER_SCAN_LIMIT),
                )
                or DEFAULT_SPILL_SWEEPER_SCAN_LIMIT
            ),
        )
    workspace = Path(workspace_root) if workspace_root else None
    moved_relative_paths: set[str] = set()
    for entry in _backlog_entries(backlog):
        if artifact_moves >= max(0, int(max_artifacts or 0)):
            break
        if not workspace:
            break
        byte_count = int(dict(entry).get("byte_count", 0) or 0)
        if budget and used_bytes + byte_count > budget:
            continue
        rel = str(dict(entry).get("source_relative_path", "") or "")
        result = move_cold_workspace_artifact(
            workspace_root=workspace,
            relative_path=rel,
            state_root=state_root,
            min_bytes=cold_artifact_min_bytes,
            cold_age_seconds=cold_age_seconds,
        )
        if result.get("result") == "moved":
            artifact_moves += 1
            moved_bytes = int(result.get("byte_count", 0) or 0)
            used_bytes += moved_bytes
            moved_relative_paths.add(rel)
            actions.append(
                {
                    "source_kind": "cold_workspace_artifact",
                    "result": "moved",
                    "byte_count": moved_bytes,
                    "ref": _safe_text(result.get("artifact_ref", "")),
                }
            )

    remaining_backlog_entries = [
        entry
        for entry in _backlog_entries(backlog)
        if str(entry.get("source_relative_path", "") or "") not in moved_relative_paths
    ]
    backlog_after = _write_cold_artifact_backlog(
        state_root=state_root,
        workspace_ref=str(backlog.get("workspace_ref", "") or ""),
        entries=remaining_backlog_entries,
        scan_limited=bool(backlog.get("scan_limited", False)),
        scanned_file_count=int(backlog.get("scanned_file_count", 0) or 0),
    )
    status = spill_status(state_root)
    activity = (
        "idle"
        if actions or int(backlog_after.get("backlog_count", 0) or 0) > 0
        else "no_eligible_data"
    )
    finished_at = _now()
    payload = {
        "schema_name": "NovaliSpillSweeperState",
        "schema_version": SPILL_SWEEPER_SCHEMA_VERSION,
        "generated_at": finished_at,
        "spill_sweeper_state": "idle",
        "spill_activity_state": activity,
        "last_spill_started_at": started_at,
        "last_spill_finished_at": finished_at,
        "next_spill_due_at": _iso_after(cadence_seconds),
        "runtime_log_segment_move_count": runtime_moves,
        "runtime_log_bundle_count": runtime_bundle_count,
        "runtime_log_bundle_file_count": runtime_bundle_file_count,
        "runtime_log_bundle_latest_result": "moved" if runtime_bundle_count else "no_eligible_data",
        "runtime_log_small_file_backlog_count": max(0, small_file_backlog_count - runtime_bundle_file_count),
        "cold_artifact_move_count": artifact_moves,
        "moved_action_count": len(actions),
        "moved_bytes": used_bytes,
        "spill_budget_bytes": budget,
        "spill_budget_used_bytes": used_bytes,
        "cold_artifact_backlog_count": int(backlog_after.get("backlog_count", 0) or 0),
        "cold_artifact_backlog_bytes": int(backlog_after.get("backlog_bytes", 0) or 0),
        "runtime_log_bundle_bytes": runtime_bundle_bytes,
        "runtime_log_active_tail_bytes": runtime_log_active_tail_bytes,
        "catalog_refresh_result": "deferred" if actions else "not_requested",
        "result": "moved" if actions else "no_eligible_data",
        "actions": actions,
        **{
            key: status.get(key)
            for key in (
                "spill_mode",
                "runtime_log_spill_bytes",
                "cold_artifact_spill_bytes",
                "disk_spill_bytes",
                "spill_volume_bytes",
                "spill_pointer_count",
                "runtime_log_segment_count",
                "runtime_log_active_tail_bytes",
            )
        },
    }
    _write_json(state_path, payload)
    _emit_sweeper_pass(payload)
    if actions and package_root and operator_root:
        try:
            build_data_at_rest_catalog(
                package_root=package_root,
                operator_root=operator_root,
                state_root=state_root,
                workspace_root=workspace_root,
            )
            payload["catalog_refresh_result"] = "refreshed"
        except Exception:
            payload["catalog_refresh_result"] = "refresh_failed"
        try:
            _write_json(state_path, payload)
        except Exception:
            pass
    return payload


def _walk_spill_entries(root: Path, pattern: str) -> list[Path]:
    try:
        return [path for path in root.glob(pattern) if path.is_file()]
    except OSError:
        return []


def spill_status(state_root: str | Path, *, include_live_scan: bool = True) -> dict[str, Any]:
    root = spill_root(state_root)
    bundle_index = _safe_read_json(runtime_log_bundle_index_path(state_root))
    sweeper = _safe_read_json(spill_sweeper_state_path(state_root))
    backlog = _safe_read_json(cold_artifact_backlog_path(state_root))
    runtime_bytes = 0
    bundle_bytes = 0
    artifact_bytes = 0
    pointer_count = 0
    runtime_segment_count = 0
    runtime_bundle_count = 0
    runtime_bundle_file_count = 0
    if include_live_scan:
        runtime_indexes = _walk_spill_entries(runtime_log_spill_root(state_root), "*/runtime_log_segment_index_latest.json")
        artifact_manifests = _walk_spill_entries(workspace_artifact_spill_root(state_root), "*/cold_artifact_manifest_latest.json")
        for index_path in runtime_indexes:
            index = _safe_read_json(index_path)
            for item in index.get("segments", []) if isinstance(index.get("segments", []), list) else []:
                if isinstance(item, Mapping):
                    runtime_bytes += int(item.get("byte_count", 0) or 0)
                    pointer_count += 1
                    runtime_segment_count += 1
    else:
        runtime_bytes = int(sweeper.get("runtime_log_spill_bytes", 0) or 0)
        runtime_segment_count = int(sweeper.get("runtime_log_segment_count", 0) or 0)
    for item in bundle_index.get("bundles", []) if isinstance(bundle_index.get("bundles", []), list) else []:
        if isinstance(item, Mapping):
            bundle_bytes += int(item.get("byte_count", 0) or 0)
            runtime_bundle_count += 1
            runtime_bundle_file_count += int(item.get("file_count", 0) or 0)
            pointer_count += int(item.get("file_count", 0) or 0)
    if include_live_scan:
        for manifest_path in artifact_manifests:
            manifest = _safe_read_json(manifest_path)
            for item in manifest.get("artifacts", []) if isinstance(manifest.get("artifacts", []), list) else []:
                if isinstance(item, Mapping):
                    artifact_bytes += int(item.get("byte_count", 0) or 0)
                    pointer_count += 1
    else:
        artifact_bytes = int(sweeper.get("cold_artifact_spill_bytes", 0) or 0)
        pointer_count += int(sweeper.get("spill_pointer_count", 0) or 0)
    total_bytes = runtime_bytes + bundle_bytes + artifact_bytes
    if include_live_scan:
        try:
            spill_volume_bytes = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
        except OSError:
            spill_volume_bytes = total_bytes
    else:
        spill_volume_bytes = int(sweeper.get("spill_volume_bytes", total_bytes) or total_bytes)
    runtime_active_tail_bytes = 0
    try:
        for pointer in root.glob("runtime_logs/*/segments/*.jsonl"):
            # Keep this loop intentionally narrow; active tails live on the bind mount
            # and are accounted by the sweeper during discovery.
            _ = pointer
    except OSError:
        pass
    latest_spill_result = str(sweeper.get("result", "") or "")
    if not latest_spill_result:
        latest_spill_result = "ready" if pointer_count else "empty"
    sweeper_state = str(sweeper.get("spill_sweeper_state", "idle") or "idle")
    spill_activity_state = str(
        sweeper.get("spill_activity_state", "idle" if pointer_count else "no_eligible_data")
        or "idle"
    )
    if sweeper_state == "active":
        stale_after = int(
            os.environ.get(
                "NOVALI_SPILL_SWEEPER_STALE_SECONDS",
                str(DEFAULT_SPILL_SWEEPER_STALE_SECONDS),
            )
            or DEFAULT_SPILL_SWEEPER_STALE_SECONDS
        )
        if _seconds_since(sweeper.get("last_spill_started_at")) > max(1, stale_after):
            sweeper_state = "idle"
            spill_activity_state = "failed"
            latest_spill_result = latest_spill_result or "stale_active_recovered"
    if sweeper_state != "active" and spill_activity_state == "active":
        spill_activity_state = "idle"
    return {
        "schema_name": "NovaliDiskSpillStatus",
        "schema_version": "novali_disk_spill_status_v1",
        "generated_at": _now(),
        "spill_mode": "move_cold",
        "spill_root_ref": _short_ref(str(root), prefix="spill"),
        "spill_sweeper_state": sweeper_state,
        "spill_activity_state": spill_activity_state,
        "next_spill_due_at": str(sweeper.get("next_spill_due_at", "") or ""),
        "last_spill_started_at": str(sweeper.get("last_spill_started_at", "") or ""),
        "last_spill_finished_at": str(sweeper.get("last_spill_finished_at", "") or ""),
        "runtime_log_spill_bytes": runtime_bytes,
        "runtime_log_segment_count": runtime_segment_count,
        "runtime_log_bundle_count": runtime_bundle_count,
        "runtime_log_bundle_file_count": runtime_bundle_file_count,
        "runtime_log_bundle_bytes": bundle_bytes,
        "runtime_log_small_file_backlog_count": int(sweeper.get("runtime_log_small_file_backlog_count", 0) or 0),
        "runtime_log_bundle_latest_result": str(sweeper.get("runtime_log_bundle_latest_result", "") or ""),
        "runtime_log_active_tail_bytes": int(sweeper.get("runtime_log_active_tail_bytes", runtime_active_tail_bytes) or 0),
        "cold_artifact_spill_bytes": artifact_bytes,
        "disk_spill_bytes": total_bytes,
        "spill_volume_bytes": int(spill_volume_bytes or 0),
        "spill_pointer_count": pointer_count,
        "spill_backlog_count": int(backlog.get("backlog_count", sweeper.get("cold_artifact_backlog_count", 0)) or 0),
        "cold_artifact_backlog_count": int(backlog.get("backlog_count", sweeper.get("cold_artifact_backlog_count", 0)) or 0),
        "cold_artifact_backlog_bytes": int(backlog.get("backlog_bytes", sweeper.get("cold_artifact_backlog_bytes", 0)) or 0),
        "spill_budget_bytes": int(sweeper.get("spill_budget_bytes", DEFAULT_SPILL_SWEEPER_BUDGET_BYTES) or 0),
        "spill_budget_used_bytes": int(sweeper.get("spill_budget_used_bytes", 0) or 0),
        "latest_spill_result": latest_spill_result,
    }


def _read_row_at_offset(path: Path, offset: int) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            handle.seek(max(0, int(offset or 0)))
            line = handle.readline()
    except OSError:
        return {}
    if not line:
        return {}
    try:
        payload = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def rebuild_ledger_index(
    operator_root: str | Path,
    name: str,
    *,
    recent_limit: int = DEFAULT_RECENT_OFFSET_LIMIT,
) -> dict[str, Any]:
    path = _ledger_path(operator_root, name)
    recent_offsets: deque[int] = deque(maxlen=max(1, int(recent_limit or 1)))
    operation_id_offsets: dict[str, int] = {}
    action_offsets: dict[str, int] = {}
    status_offsets: dict[str, int] = {}
    created_at_buckets: dict[str, int] = {}
    line_count = 0
    latest_offset = 0
    if path.exists():
        try:
            with path.open("rb") as handle:
                while True:
                    offset = handle.tell()
                    line = handle.readline()
                    if not line:
                        break
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        row = json.loads(stripped.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    if not isinstance(row, dict):
                        continue
                    line_count += 1
                    latest_offset = offset
                    recent_offsets.append(offset)
                    operation_id = str(row.get("operation_id", "") or "").strip()
                    if operation_id:
                        operation_id_offsets[operation_id] = offset
                    action = str(row.get("action", "") or "").strip()
                    if action:
                        action_offsets[action] = offset
                    status = str(row.get("status", "") or row.get("result", "") or "").strip()
                    if status:
                        status_offsets[status] = offset
                    created_at = str(row.get("created_at", "") or row.get("generated_at", "") or "").strip()
                    if len(created_at) >= 10:
                        created_at_buckets[created_at[:10]] = offset
        except OSError:
            pass
    signature = _source_signature(path)
    index = {
        "schema_name": "NovaliLedgerIndex",
        "schema_version": LEDGER_INDEX_SCHEMA_VERSION,
        "generated_at": _now(),
        "ledger_name": str(name),
        "line_count": line_count,
        "latest_offset": latest_offset,
        "recent_offsets": list(recent_offsets),
        "operation_id_offsets": operation_id_offsets,
        "action_offsets": action_offsets,
        "status_offsets": status_offsets,
        "created_at_bucket_offsets": created_at_buckets,
        "recent_offset_limit": max(1, int(recent_limit or 1)),
        **signature,
    }
    _write_json(_index_path(operator_root, name), index)
    return index


def ensure_ledger_index(operator_root: str | Path, name: str) -> dict[str, Any]:
    path = _ledger_path(operator_root, name)
    index_path = _index_path(operator_root, name)
    current = _source_signature(path)
    index = _safe_read_json(index_path)
    if (
        index.get("schema_version") == LEDGER_INDEX_SCHEMA_VERSION
        and int(index.get("source_size", -1) or -1) == int(current.get("source_size", 0))
        and int(index.get("source_mtime_ns", -1) or -1) == int(current.get("source_mtime_ns", 0))
    ):
        return index
    return rebuild_ledger_index(operator_root, name)


def update_ledger_index_after_append(
    operator_root: str | Path,
    name: str,
    offset: int,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    path = _ledger_path(operator_root, name)
    index = _safe_read_json(_index_path(operator_root, name))
    if index.get("schema_version") != LEDGER_INDEX_SCHEMA_VERSION:
        return rebuild_ledger_index(operator_root, name)
    previous_size = int(index.get("source_size", 0) or 0)
    if int(offset or 0) < previous_size:
        return rebuild_ledger_index(operator_root, name)
    recent_limit = int(index.get("recent_offset_limit", DEFAULT_RECENT_OFFSET_LIMIT) or DEFAULT_RECENT_OFFSET_LIMIT)
    recent_offsets = deque(
        [int(value) for value in index.get("recent_offsets", []) if isinstance(value, int)],
        maxlen=max(1, recent_limit),
    )
    recent_offsets.append(int(offset or 0))
    operation_id_offsets = dict(index.get("operation_id_offsets", {}) or {})
    action_offsets = dict(index.get("action_offsets", {}) or {})
    status_offsets = dict(index.get("status_offsets", {}) or {})
    created_at_buckets = dict(index.get("created_at_bucket_offsets", {}) or {})
    operation_id = str(row.get("operation_id", "") or "").strip()
    if operation_id:
        operation_id_offsets[operation_id] = int(offset or 0)
    action = str(row.get("action", "") or "").strip()
    if action:
        action_offsets[action] = int(offset or 0)
    status = str(row.get("status", "") or row.get("result", "") or "").strip()
    if status:
        status_offsets[status] = int(offset or 0)
    created_at = str(row.get("created_at", "") or row.get("generated_at", "") or "").strip()
    if len(created_at) >= 10:
        created_at_buckets[created_at[:10]] = int(offset or 0)
    signature = _source_signature(path)
    updated = {
        **index,
        "generated_at": _now(),
        "line_count": int(index.get("line_count", 0) or 0) + 1,
        "latest_offset": int(offset or 0),
        "recent_offsets": list(recent_offsets),
        "operation_id_offsets": operation_id_offsets,
        "action_offsets": action_offsets,
        "status_offsets": status_offsets,
        "created_at_bucket_offsets": created_at_buckets,
        **signature,
    }
    _write_json(_index_path(operator_root, name), updated)
    return updated


def read_ledger_tail_indexed(
    operator_root: str | Path,
    name: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    limit_value = max(1, int(limit or 1))
    path = _ledger_path(operator_root, name)
    if not path.exists():
        return []
    index = ensure_ledger_index(operator_root, name)
    offsets = [int(value) for value in index.get("recent_offsets", []) if isinstance(value, int)]
    rows = [
        _read_row_at_offset(path, offset)
        for offset in offsets[-limit_value:]
    ]
    return [row for row in rows if row]


def latest_ledger_entry(operator_root: str | Path, name: str) -> dict[str, Any]:
    path = _ledger_path(operator_root, name)
    if not path.exists():
        return {}
    index = ensure_ledger_index(operator_root, name)
    return _read_row_at_offset(path, int(index.get("latest_offset", 0) or 0))


def lookup_ledger_by_operation_id(
    operator_root: str | Path,
    operation_id: str,
    *,
    ledger_name: str = "operation_results",
) -> dict[str, Any]:
    operation_id = str(operation_id or "").strip()
    if not operation_id:
        return {}
    path = _ledger_path(operator_root, ledger_name)
    if not path.exists():
        return {}
    index = ensure_ledger_index(operator_root, ledger_name)
    offsets = dict(index.get("operation_id_offsets", {}) or {})
    if operation_id not in offsets:
        return {}
    return _read_row_at_offset(path, int(offsets.get(operation_id, 0) or 0))


def _view_payload(name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "NovaliMaterializedView",
        "schema_version": MATERIALIZED_VIEW_SCHEMA_VERSION,
        "generated_at": _now(),
        "view_name": name,
        "payload": dict(payload),
    }


def _latest_directive_track_progress(workspace_root: str | Path | None) -> dict[str, Any]:
    if not workspace_root:
        return {}
    path = Path(workspace_root) / "artifacts" / "directive_outcome_track_progress_latest.json"
    payload = _safe_read_json(path)
    if not payload:
        return {}
    result = _safe_metadata(payload)
    artifact_rel = str(
        payload.get("latest_artifact_path", "")
        or payload.get("directive_track_artifact_relative_path", "")
        or payload.get("selected_track_artifact_path", "")
        or ""
    )
    if artifact_rel and not _looks_absolute_path(artifact_rel):
        result["directive_track_artifact_relative_path"] = artifact_rel.replace("\\", "/")
    for key in (
        "track_id",
        "track_title",
        "deliverable_kind",
        "progress_state",
        "source_excerpt",
        "bounded_next_step",
        "review_gate",
        "generated_at",
    ):
        if key in payload and key not in RAW_FIELD_DENYLIST:
            value = payload.get(key)
            if isinstance(value, str):
                result[key] = _safe_text(value)
            elif isinstance(value, (int, float, bool)) or value is None:
                result[key] = value
    if "selected_deliverable_kind" not in result and "deliverable_kind" in result:
        result["selected_deliverable_kind"] = result.get("deliverable_kind")
    if "selected_directive_track_id" not in result and "track_id" in result:
        result["selected_directive_track_id"] = result.get("track_id")
    requested_tags = payload.get("requested_tags")
    if isinstance(requested_tags, list):
        result["requested_tags"] = [
            _safe_text(item, max_chars=80)
            for item in requested_tags
            if isinstance(item, str) and item.strip()
        ][:12]
    return result


def _latest_directive_dossier_progress(workspace_root: str | Path | None) -> dict[str, Any]:
    if not workspace_root:
        return {}
    path = Path(workspace_root) / "artifacts" / "directive_dossier_progress_latest.json"
    payload = _safe_read_json(path)
    if not payload:
        return {}
    result = _safe_metadata(payload)
    relative_path = str(
        payload.get("directive_dossier_artifact_relative_path", "")
        or payload.get("latest_directive_dossier_ref", "")
        or ""
    )
    if relative_path and not _looks_absolute_path(relative_path):
        result["directive_dossier_artifact_relative_path"] = relative_path.replace("\\", "/")
        result["latest_directive_dossier_ref"] = relative_path.replace("\\", "/")
    for key in (
        "directive_id",
        "workspace_id",
        "selected_directive_track_id",
        "track_id",
        "track_title",
        "selected_deliverable_kind",
        "deliverable_kind",
        "directive_work_program_state",
        "directive_source_coverage_state",
        "librarian_gap_reuse_decision",
        "trusted_source_retrieval_validation_state",
        "directive_dossier_progress_generated_at",
        "generated_at",
    ):
        if key in payload and key not in RAW_FIELD_DENYLIST:
            value = payload.get(key)
            if isinstance(value, str):
                result[key] = _safe_text(value)
            elif isinstance(value, (int, float, bool)) or value is None:
                result[key] = value
    if "selected_deliverable_kind" not in result and "deliverable_kind" in result:
        result["selected_deliverable_kind"] = result.get("deliverable_kind")
    if "selected_directive_track_id" not in result and "track_id" in result:
        result["selected_directive_track_id"] = result.get("track_id")
    return result


def refresh_materialized_views(
    operator_root: str | Path,
    state_root: str | Path,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    views_root = materialized_views_root(state_root)
    latest_operation = _safe_metadata(latest_ledger_entry(operator_root, "operation_results"))
    recent_operations = [
        _safe_metadata(row)
        for row in read_ledger_tail_indexed(operator_root, "operation_results", limit=20)
    ]
    meaningful = _safe_metadata(latest_ledger_entry(operator_root, "meaningful_work_evaluations"))
    directive_track = _latest_directive_track_progress(workspace_root)
    directive_dossier = _latest_directive_dossier_progress(workspace_root)
    memory = _safe_read_json(Path(operator_root) / "memory_pressure" / "status_latest.json")
    trusted = _safe_metadata(latest_ledger_entry(operator_root, "trusted_source_triage_digests"))
    views = {
        "latest_operation_result": latest_operation,
        "recent_operations_tail": recent_operations,
        "meaningful_work_latest": meaningful,
        "directive_track_latest": directive_track,
        "directive_dossier_latest": directive_dossier,
        "memory_pressure_latest": _safe_metadata(memory),
        "trusted_source_latest": trusted,
    }
    for name, payload in views.items():
        _write_json(views_root / f"{name}.json", _view_payload(name, payload if isinstance(payload, Mapping) else {"items": payload}))
    return views


def _catalog_entry_from_operation(row: Mapping[str, Any]) -> dict[str, Any]:
    action = _safe_text(row.get("action", "operation"))
    operation_id = _safe_text(row.get("operation_id", ""))
    title = " ".join(part for part in [action, operation_id] if part).strip()
    return {
        "kind": "operation_summary",
        "title": title or "operation summary",
        "operation_id": operation_id,
        "action": action,
        "status": _safe_text(row.get("status", "") or row.get("result", "")),
        "created_at": _safe_text(row.get("created_at", "") or row.get("generated_at", "")),
        "ref": _short_ref(operation_id or title, prefix="op"),
    }


def _catalog_entry_from_directive_track(
    payload: Mapping[str, Any],
    *,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    relative_path = str(payload.get("directive_track_artifact_relative_path", "") or "")
    if not relative_path and payload.get("latest_artifact_path"):
        relative_path = _relative_path(workspace_root, payload.get("latest_artifact_path"))
    return {
        "kind": "directive_track",
        "title": _safe_text(payload.get("track_title", "") or payload.get("selected_directive_track_id", "") or "directive track"),
        "directive_id": _safe_text(payload.get("directive_id", "")),
        "workspace_id": _safe_text(payload.get("workspace_id", "")),
        "track_id": _safe_text(payload.get("selected_directive_track_id", "") or payload.get("track_id", "")),
        "deliverable_kind": _safe_text(payload.get("selected_deliverable_kind", "") or payload.get("deliverable_kind", "")),
        "artifact_depth": _safe_text(payload.get("artifact_depth", "")),
        "delta_focus_id": _safe_text(payload.get("delta_focus_id", "")),
        "delta_layer_id": _safe_text(payload.get("delta_layer_id", "")),
        "delta_materially_new": bool(payload.get("delta_materially_new", False)),
        "created_at": _safe_text(payload.get("generated_at", "") or payload.get("directive_track_progress_generated_at", "")),
        "relative_path": relative_path if relative_path and not _looks_absolute_path(relative_path) else "",
        "ref": _short_ref(
            "|".join(
                str(payload.get(key, "") or "")
                for key in ("track_id", "selected_directive_track_id", "new_information_delta_signature", "generated_at")
            ),
            prefix="track",
        ),
    }


def _catalog_entry_from_directive_dossier(
    payload: Mapping[str, Any],
    *,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    relative_path = str(
        payload.get("directive_dossier_artifact_relative_path", "")
        or payload.get("latest_directive_dossier_ref", "")
        or ""
    )
    if relative_path and _looks_absolute_path(relative_path):
        relative_path = _relative_path(workspace_root, relative_path)
    deliverable_kind = _safe_text(
        payload.get("selected_deliverable_kind", "") or payload.get("deliverable_kind", "")
    )
    track_id = _safe_text(
        payload.get("selected_directive_track_id", "") or payload.get("track_id", "")
    )
    title = " ".join(
        part
        for part in (
            deliverable_kind.replace("_", " ").strip(),
            "directive dossier",
        )
        if part
    ).strip()
    return {
        "kind": "directive_dossier",
        "title": _safe_text(title or track_id or "directive dossier"),
        "directive_id": _safe_text(payload.get("directive_id", "")),
        "workspace_id": _safe_text(payload.get("workspace_id", "")),
        "track_id": track_id,
        "deliverable_kind": deliverable_kind,
        "directive_work_program_state": _safe_text(payload.get("directive_work_program_state", "")),
        "directive_source_coverage_state": _safe_text(payload.get("directive_source_coverage_state", "")),
        "librarian_gap_reuse_decision": _safe_text(payload.get("librarian_gap_reuse_decision", "")),
        "librarian_gap_request_id": _safe_text(payload.get("librarian_gap_request_id", "")),
        "librarian_gap_signature": _safe_text(payload.get("librarian_gap_signature", "")),
        "librarian_gap_state": _safe_text(payload.get("librarian_gap_state", "")),
        "requested_pack_family": _safe_text(payload.get("requested_pack_family", "")),
        "requested_tags": [
            _safe_text(item, max_chars=80)
            for item in list(payload.get("requested_tags", []) or [])
            if isinstance(item, str) and item.strip()
        ][:12],
        "source_dossier_ref": _safe_text(payload.get("source_dossier_ref", "")),
        "local_pack_stage_result": _safe_text(payload.get("local_pack_stage_result", "")),
        "trusted_source_retrieval_blocker": _safe_text(
            payload.get("trusted_source_retrieval_blocker", "")
        ),
        "trusted_source_retrieval_validation_state": _safe_text(
            payload.get("trusted_source_retrieval_validation_state", "")
        ),
        "directive_dossier_materially_new": bool(
            payload.get("directive_dossier_materially_new", False)
        ),
        "directive_dossier_rejection_reason": _safe_text(
            payload.get("directive_dossier_rejection_reason", "")
        ),
        "created_at": _safe_text(
            payload.get("directive_dossier_progress_generated_at", "")
            or payload.get("generated_at", "")
        ),
        "relative_path": relative_path if relative_path and not _looks_absolute_path(relative_path) else "",
        "ref": _short_ref(
            "|".join(
                str(payload.get(key, "") or "")
                for key in (
                    "selected_directive_track_id",
                    "track_id",
                    "directive_dossier_signature",
                    "directive_dossier_progress_generated_at",
                    "latest_directive_dossier_ref",
                )
            ),
            prefix="dossier",
        ),
    }


def _catalog_entries_from_librarian(state_root: str | Path) -> list[dict[str, Any]]:
    try:
        from .librarian import search_librarian_catalog

        result = search_librarian_catalog(state_root, limit=50)
    except Exception:
        return []
    entries: list[dict[str, Any]] = []
    for item in result.get("results", []) if isinstance(result.get("results", []), list) else []:
        if not isinstance(item, Mapping):
            continue
        entries.append(
            {
                "kind": "librarian_pack",
                "title": _safe_text(item.get("family", "") or item.get("pack_id", "") or "librarian pack"),
                "pack_kind": _safe_text(item.get("kind", "")),
                "pack_id": _safe_text(item.get("pack_id", "")),
                "family": _safe_text(item.get("family", "")),
                "version_ref": _safe_text(item.get("version_ref", "")),
                "quality_state": _safe_text(item.get("quality_state", "")),
                "reuse_state": _safe_text(item.get("reuse_state", "")),
                "source_kind": _safe_text(item.get("source_kind", "")),
                "relative_path": _safe_text(item.get("pack_path", "")),
                "ref": _short_ref(item.get("pack_id", "") or item.get("family", ""), prefix="lib"),
            }
        )
    return entries


def _catalog_entries_from_runtime_log_segments(state_root: str | Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index_path in _walk_spill_entries(runtime_log_spill_root(state_root), "*/runtime_log_segment_index_latest.json"):
        index = _safe_read_json(index_path)
        for item in index.get("segments", []) if isinstance(index.get("segments", []), list) else []:
            if not isinstance(item, Mapping):
                continue
            entries.append(
                {
                    "kind": "runtime_log_segment",
                    "title": "runtime log segment",
                    "session_ref": _safe_text(item.get("session_ref", "")),
                    "segment_ref": _safe_text(item.get("segment_ref", "")),
                    "storage_state": _safe_text(item.get("storage_state", "moved_to_spill")),
                    "created_at": _safe_text(item.get("created_at", "")),
                    "byte_count": int(item.get("byte_count", 0) or 0),
                    "relative_path": _safe_text(item.get("spill_relative_path", "")),
                    "ref": _safe_text(item.get("segment_ref", "")) or _short_ref(
                        json.dumps(item, sort_keys=True, default=str),
                        prefix="logseg",
                    ),
                }
            )
    return entries


def _catalog_entries_from_runtime_log_bundles(state_root: str | Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    index = _safe_read_json(runtime_log_bundle_index_path(state_root))
    for item in index.get("bundles", []) if isinstance(index.get("bundles", []), list) else []:
        if not isinstance(item, Mapping):
            continue
        entries.append(
            {
                "kind": "runtime_log_bundle",
                "title": "runtime log bundle",
                "bundle_ref": _safe_text(item.get("bundle_ref", "")),
                "storage_state": _safe_text(item.get("storage_state", "bundled_to_spill")),
                "created_at": _safe_text(item.get("created_at", "")),
                "byte_count": int(item.get("byte_count", 0) or 0),
                "file_count": int(item.get("file_count", 0) or 0),
                "row_count": int(item.get("row_count", 0) or 0),
                "relative_path": _safe_text(item.get("spill_relative_path", "")),
                "ref": _safe_text(item.get("bundle_ref", "")) or _short_ref(
                    json.dumps(item, sort_keys=True, default=str),
                    prefix="logbundle",
                ),
            }
        )
    return entries


def _catalog_entries_from_cold_workspace_artifacts(state_root: str | Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for manifest_path in _walk_spill_entries(workspace_artifact_spill_root(state_root), "*/cold_artifact_manifest_latest.json"):
        manifest = _safe_read_json(manifest_path)
        for item in manifest.get("artifacts", []) if isinstance(manifest.get("artifacts", []), list) else []:
            if not isinstance(item, Mapping):
                continue
            entries.append(
                {
                    "kind": "cold_workspace_artifact",
                    "title": _safe_text(item.get("title", "") or item.get("source_relative_path", "") or "cold artifact"),
                    "workspace_ref": _safe_text(item.get("workspace_ref", "")),
                    "artifact_ref": _safe_text(item.get("artifact_ref", "")),
                    "storage_state": _safe_text(item.get("storage_state", "moved_to_spill")),
                    "created_at": _safe_text(item.get("moved_at", "")),
                    "byte_count": int(item.get("byte_count", 0) or 0),
                    "source_relative_path": _safe_text(item.get("source_relative_path", "")),
                    "relative_path": _safe_text(item.get("spill_relative_path", "")),
                    "ref": _safe_text(item.get("artifact_ref", "")) or _short_ref(
                        json.dumps(item, sort_keys=True, default=str),
                        prefix="artifact",
                    ),
                }
            )
    return entries


def build_data_at_rest_catalog(
    *,
    package_root: str | Path,
    operator_root: str | Path,
    state_root: str | Path,
    workspace_root: str | Path | None = None,
    limit: int = CATALOG_MAX_RESULTS,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    views = refresh_materialized_views(operator_root, state_root, workspace_root)
    directive_track = views.get("directive_track_latest", {})
    if isinstance(directive_track, Mapping) and directive_track:
        entries.append(_catalog_entry_from_directive_track(directive_track, workspace_root=workspace_root))
    directive_dossier = views.get("directive_dossier_latest", {})
    if isinstance(directive_dossier, Mapping) and directive_dossier:
        entries.append(_catalog_entry_from_directive_dossier(directive_dossier, workspace_root=workspace_root))
    entries.extend(_catalog_entries_from_librarian(state_root))
    entries.extend(_catalog_entries_from_runtime_log_segments(state_root))
    entries.extend(_catalog_entries_from_runtime_log_bundles(state_root))
    entries.extend(_catalog_entries_from_cold_workspace_artifacts(state_root))
    for row in views.get("recent_operations_tail", []) if isinstance(views.get("recent_operations_tail"), list) else []:
        if isinstance(row, Mapping):
            entries.append(_catalog_entry_from_operation(row))
    meaningful = views.get("meaningful_work_latest", {})
    if isinstance(meaningful, Mapping) and meaningful:
        entries.append(
            {
                "kind": "meaningful_work",
                "title": "meaningful work latest",
                "created_at": _safe_text(meaningful.get("created_at", "") or meaningful.get("generated_at", "")),
                "meaningful_delta": bool(meaningful.get("meaningful_delta", False)),
                "score": meaningful.get("score", ""),
                "ref": _short_ref(json.dumps(meaningful, sort_keys=True, default=str), prefix="mw"),
            }
        )
    bounded = entries[: max(1, min(CATALOG_MAX_RESULTS, int(limit or CATALOG_MAX_RESULTS)))]
    catalog = {
        "schema_name": "NovaliDataAtRestCatalog",
        "schema_version": DATA_AT_REST_CATALOG_SCHEMA_VERSION,
        "generated_at": _now(),
        "package_ref": _short_ref(Path(package_root).name, prefix="pkg"),
        "entry_count": len(bounded),
        "entries": bounded,
    }
    _write_json(data_at_rest_catalog_path(state_root), catalog)
    return catalog


def search_data_at_rest_catalog(
    state_root: str | Path,
    *,
    query: str = "",
    kind: str = "",
    limit: int = 20,
    include_live_entries: bool = False,
) -> dict[str, Any]:
    catalog = _safe_read_json(data_at_rest_catalog_path(state_root))
    entries = catalog.get("entries", []) if isinstance(catalog.get("entries", []), list) else []
    live_entries: list[dict[str, Any]] = []
    if include_live_entries:
        if not kind or str(kind).strip().lower() in {"runtime_log_segment", "all"}:
            live_entries.extend(_catalog_entries_from_runtime_log_segments(state_root))
        if not kind or str(kind).strip().lower() in {"runtime_log_bundle", "all"}:
            live_entries.extend(_catalog_entries_from_runtime_log_bundles(state_root))
        if not kind or str(kind).strip().lower() in {"cold_workspace_artifact", "all"}:
            live_entries.extend(_catalog_entries_from_cold_workspace_artifacts(state_root))
    if live_entries:
        seen_refs = {
            str(entry.get("kind", "")) + "|" + str(entry.get("ref", ""))
            for entry in entries
            if isinstance(entry, Mapping)
        }
        merged_entries = list(entries)
        for entry in live_entries:
            key = str(entry.get("kind", "")) + "|" + str(entry.get("ref", ""))
            if key in seen_refs:
                continue
            seen_refs.add(key)
            merged_entries.append(entry)
        entries = merged_entries
    query_text = str(query or "").strip().lower()
    kind_text = str(kind or "").strip().lower()
    matches: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        if kind_text and str(entry.get("kind", "")).lower() != kind_text:
            continue
        haystack = " ".join(
            str(entry.get(key, "") or "")
            for key in (
                "kind",
                "title",
                "pack_kind",
                "pack_id",
                "family",
                "version_ref",
                "quality_state",
                "reuse_state",
                "action",
                "status",
                "deliverable_kind",
                "artifact_depth",
                "delta_focus_id",
                "delta_layer_id",
                "directive_work_program_state",
                "directive_source_coverage_state",
                "librarian_gap_reuse_decision",
                "trusted_source_retrieval_validation_state",
                "directive_dossier_rejection_reason",
                "relative_path",
                "source_relative_path",
                "storage_state",
                "session_ref",
                "segment_ref",
                "bundle_ref",
                "workspace_ref",
                "artifact_ref",
                "ref",
            )
        ).lower()
        if query_text and query_text not in haystack:
            continue
        matches.append(dict(entry))
        if len(matches) >= max(1, int(limit or 1)):
            break
    return {
        "ok": True,
        "schema_name": "NovaliDataAtRestSearch",
        "schema_version": DATA_AT_REST_CATALOG_SCHEMA_VERSION,
        "generated_at": _now(),
        "query": _safe_text(query_text, max_chars=80),
        "kind": _safe_text(kind_text, max_chars=80),
        "result_count": len(matches),
        "results": matches,
        "catalog_generated_at": _safe_text(catalog.get("generated_at", "")),
    }

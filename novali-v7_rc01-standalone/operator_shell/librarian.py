from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .disk_spill import spill_root


LIBRARIAN_SCHEMA_VERSION = "novali_librarian_pack_v1"
LIBRARIAN_CATALOG_SCHEMA_VERSION = "novali_librarian_catalog_v1"
LIBRARIAN_HEALTH_SCHEMA_VERSION = "novali_librarian_health_v1"
LIBRARIAN_SEARCH_SCHEMA_VERSION = "novali_librarian_search_v1"

SAFE_TEXT_MAX_CHARS = 240
CATALOG_LIMIT = 500

SUPPORTED_SCHEMA_KINDS = {
    "GovernedExecutionTrustedSourceKnowledgePack": "knowledge_pack",
    "TrustedSourceLiteratureTriageDigest": "knowledge_pack",
    "NovaliSuccessorCompletionKnowledgePack": "knowledge_pack",
    "NovaliWorkspaceContinuationKnowledgePack": "knowledge_pack",
    "NovaliSuccessorPromotionReviewKnowledgePack": "knowledge_pack",
    "NovaliSuccessorBaselineAdmissionKnowledgePack": "knowledge_pack",
    "NovaliSuccessorAdmittedCandidateComparisonKnowledgePack": "knowledge_pack",
    "GovernedExecutionSuccessorSkillPackResult": "skill_pack",
    "NovaliBoundedSkillPackManifest": "skill_pack",
}

RAW_FIELD_DENYLIST = {
    "prompt",
    "raw_prompt",
    "raw_provider_output",
    "provider_output",
    "provider_response",
    "absolute_path",
    "workspace_root",
    "copied_into_workspace_root",
    "evidence_bundle_path",
    "provenance_path",
    "payload",
    "content",
    "body",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_dump(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, indent=2, ensure_ascii=False)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dump(payload) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(payload), sort_keys=True, ensure_ascii=False) + "\n")


def _short_hash(value: Any, *, length: int = 16) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[: max(8, int(length or 16))]


def _slug(value: Any, *, fallback: str = "pack") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_.-]+", "_", text).strip("._-")
    return text[:120] or fallback


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
        return f"path_ref_{_short_hash(text, length=12)}"
    if len(text) > max_chars:
        return text[: max(0, max_chars - 1)].rstrip() + "..."
    return text


def librarian_root(state_root: str | Path) -> Path:
    return spill_root(state_root) / "librarian"


def librarian_catalog_path(state_root: str | Path) -> Path:
    return librarian_root(state_root) / "indexes" / "librarian_catalog_latest.json"


def librarian_health_path(state_root: str | Path) -> Path:
    return librarian_root(state_root) / "manifests" / "librarian_health_latest.json"


def librarian_events_path(state_root: str | Path) -> Path:
    return librarian_root(state_root) / "ledgers" / "librarian_events.jsonl"


def _relative_to_workspace(workspace_root: str | Path | None, path: Path) -> str:
    if not workspace_root:
        return ""
    try:
        return str(path.resolve().relative_to(Path(workspace_root).resolve())).replace("\\", "/")
    except (OSError, ValueError):
        return ""


def _pack_kind(payload: Mapping[str, Any]) -> str:
    schema_name = str(payload.get("schema_name", "") or "").strip()
    if schema_name in SUPPORTED_SCHEMA_KINDS:
        return SUPPORTED_SCHEMA_KINDS[schema_name]
    if payload.get("knowledge_pack_id") or payload.get("knowledge_id"):
        return "knowledge_pack"
    if payload.get("selected_skill_pack_id") or payload.get("skill_pack_id"):
        return "skill_pack"
    return ""


def _pack_family(payload: Mapping[str, Any], kind: str) -> str:
    if kind == "knowledge_pack":
        if str(payload.get("schema_name", "") or "") == "TrustedSourceLiteratureTriageDigest":
            if payload.get("requested_pack_family"):
                return _safe_text(payload.get("requested_pack_family"))
            return _safe_text(
                "trusted_source_triage::"
                + str(
                    payload.get("learning_gap_id")
                    or payload.get("frontier_gap_id")
                    or payload.get("operation_id")
                    or "general"
                )
            )
        return _safe_text(
            payload.get("knowledge_pack_id")
            or payload.get("pack_id")
            or payload.get("knowledge_id")
            or payload.get("requested_topic_scope")
            or payload.get("schema_name")
        )
    if kind == "skill_pack":
        return _safe_text(
            payload.get("selected_skill_pack_id")
            or payload.get("skill_pack_id")
            or payload.get("pack_id")
            or payload.get("schema_name")
        )
    return _safe_text(payload.get("schema_name") or "unknown_pack")


def _tags(payload: Mapping[str, Any], kind: str) -> list[str]:
    values: list[str] = [kind]
    for key in (
        "requested_topic_scope",
        "capability_id",
        "capability_kind",
        "directive_id",
        "provider_id",
        "freshness_policy",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            values.append(_safe_text(value, max_chars=80))
    for item in payload.get("domain_topic_tags", []) if isinstance(payload.get("domain_topic_tags"), list) else []:
        if isinstance(item, str) and item.strip():
            values.append(_safe_text(item, max_chars=80))
    for item in payload.get("requested_tags", []) if isinstance(payload.get("requested_tags"), list) else []:
        if isinstance(item, str) and item.strip():
            values.append(_safe_text(item, max_chars=80))
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result[:16]


def _summary_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "schema_name",
        "schema_version",
        "knowledge_pack_id",
        "knowledge_id",
        "selected_skill_pack_id",
        "skill_pack_id",
        "result_state",
        "requested_topic_scope",
        "capability_id",
        "capability_kind",
        "directive_id",
        "provider_id",
        "freshness_policy",
        "generated_at",
        "acquired_at",
        "quality_state",
        "validation_state",
        "status",
        "proposal_status",
        "digest_source",
        "learning_gap_id",
        "frontier_gap_id",
        "redaction_status",
    }
    summary: dict[str, Any] = {}
    for key in allowed:
        if key in payload:
            value = payload.get(key)
            if isinstance(value, str):
                summary[key] = _safe_text(value)
            elif isinstance(value, (int, float, bool)) or value is None:
                summary[key] = value
    guidance = payload.get("implementation_guidance")
    if isinstance(guidance, list):
        summary["implementation_guidance_preview"] = [
            _safe_text(item, max_chars=180)
            for item in guidance
            if isinstance(item, str) and item.strip()
        ][:5]
    caveats = payload.get("caveats")
    if isinstance(caveats, list):
        summary["caveat_count"] = len(caveats)
        summary["caveat_preview"] = [
            _safe_text(item, max_chars=180)
            for item in caveats
            if isinstance(item, str) and item.strip()
        ][:5]
    citations = payload.get("citation_summaries")
    if isinstance(citations, list):
        summary["citation_count"] = len(citations)
    claims = payload.get("claims")
    if isinstance(claims, list):
        summary["claim_preview"] = [
            _safe_text(item, max_chars=180)
            for item in claims
            if isinstance(item, str) and item.strip()
        ][:5]
    suggestions = payload.get("action_suggestions")
    if isinstance(suggestions, list):
        summary["action_suggestion_count"] = len(suggestions)
        summary["action_suggestions_preview"] = [
            _safe_text(item, max_chars=180)
            for item in suggestions
            if isinstance(item, str) and item.strip()
        ][:5]
    return summary


def _canonical_content(payload: Mapping[str, Any]) -> str:
    safe_payload = {
        key: value
        for key, value in payload.items()
        if key not in RAW_FIELD_DENYLIST
    }
    return json.dumps(safe_payload, sort_keys=True, ensure_ascii=False, default=str)


def _catalog_entries(state_root: str | Path) -> list[dict[str, Any]]:
    catalog = _read_json(librarian_catalog_path(state_root))
    entries = catalog.get("entries", [])
    return [dict(item) for item in entries if isinstance(item, dict)] if isinstance(entries, list) else []


def _latest_for_family(state_root: str | Path, kind: str, family: str) -> dict[str, Any]:
    path = (
        librarian_root(state_root)
        / "latest"
        / _slug(kind, fallback="pack")
        / f"{_slug(family, fallback='family')}.json"
    )
    return _read_json(path)


def _event(state_root: str | Path, action: str, payload: Mapping[str, Any]) -> None:
    row = {
        "schema_name": "NovaliLibrarianEvent",
        "schema_version": LIBRARIAN_SCHEMA_VERSION,
        "created_at": _now(),
        "action": action,
        **{
            key: value
            for key, value in dict(payload).items()
            if key
            in {
                "pack_id",
                "pack_kind",
                "pack_family",
                "stage_result",
                "rejection_reason",
                "quality_state",
                "reuse_state",
                "source_kind",
            }
        },
    }
    _append_jsonl(librarian_events_path(state_root), row)


def _catalog_entry(envelope: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": str(envelope.get("pack_kind", "")),
        "pack_id": str(envelope.get("pack_id", "")),
        "family": str(envelope.get("pack_family", "")),
        "version_ref": str(envelope.get("version_ref", "")),
        "created_at": str(envelope.get("created_at", "")),
        "quality_state": str(envelope.get("quality_state", "")),
        "reuse_state": str(envelope.get("reuse_state", "")),
        "source_kind": str(envelope.get("source_kind", "")),
        "source_ref": str(envelope.get("source_ref", "")),
        "source_workspace_ref": str(envelope.get("source_workspace_ref", "")),
        "source_artifact_relative_path": str(envelope.get("source_artifact_relative_path", "")),
        "tags": list(envelope.get("tags", []))[:16] if isinstance(envelope.get("tags"), list) else [],
        "capability_kind": str(envelope.get("capability_kind", "")),
        "directive_ref": str(envelope.get("directive_ref", "")),
        "content_hash": str(envelope.get("content_hash", "")),
        "pack_path": str(envelope.get("pack_path", "")),
        "latest_path": str(envelope.get("latest_path", "")),
    }


def _write_catalog(state_root: str | Path) -> dict[str, Any]:
    root = librarian_root(state_root)
    entries: list[dict[str, Any]] = []
    for path in sorted((root / "packs").glob("*/*/*.json")):
        envelope = _read_json(path)
        if envelope:
            entries.append(_catalog_entry(envelope))
    entries = sorted(
        entries,
        key=lambda item: (str(item.get("family", "")), str(item.get("created_at", ""))),
        reverse=True,
    )[:CATALOG_LIMIT]
    reusable_count = sum(1 for item in entries if item.get("reuse_state") == "reusable")
    catalog = {
        "schema_name": "NovaliLibrarianCatalog",
        "schema_version": LIBRARIAN_CATALOG_SCHEMA_VERSION,
        "generated_at": _now(),
        "pack_count": len(entries),
        "reusable_count": reusable_count,
        "entries": entries,
    }
    _write_json(librarian_catalog_path(state_root), catalog)
    _write_health(
        state_root,
        state="ready",
        latest_action="catalog_refresh",
        latest_blocker="",
        pack_count=len(entries),
        reusable_count=reusable_count,
    )
    return catalog


def _write_health(
    state_root: str | Path,
    *,
    state: str,
    latest_action: str,
    latest_blocker: str,
    pack_count: int,
    reusable_count: int,
) -> dict[str, Any]:
    health = {
        "ok": True,
        "schema_name": "NovaliLibrarianHealth",
        "schema_version": LIBRARIAN_HEALTH_SCHEMA_VERSION,
        "generated_at": _now(),
        "librarian_state": state,
        "librarian_pack_count": int(pack_count or 0),
        "librarian_reusable_count": int(reusable_count or 0),
        "latest_librarian_action": latest_action,
        "latest_librarian_blocker": latest_blocker,
    }
    _write_json(librarian_health_path(state_root), health)
    return health


def _rejection(
    *,
    state_root: str | Path,
    reason: str,
    source_path: str | Path,
    source_kind: str,
    pack_kind: str = "",
) -> dict[str, Any]:
    result = {
        "ok": False,
        "schema_name": "NovaliLibrarianStageResult",
        "schema_version": LIBRARIAN_SCHEMA_VERSION,
        "generated_at": _now(),
        "stage_result": "rejected",
        "rejection_reason": reason,
        "pack_kind": pack_kind,
        "source_kind": _safe_text(source_kind, max_chars=80),
        "source_ref": f"source_{_short_hash(source_path, length=12)}",
    }
    _event(state_root, "pack_rejected", result)
    try:
        from .observability.enrichment import record_librarian_pack_rejected

        record_librarian_pack_rejected(result)
    except Exception:
        pass
    catalog = _write_catalog(state_root)
    _write_health(
        state_root,
        state="ready",
        latest_action="pack_rejected",
        latest_blocker=reason,
        pack_count=int(catalog.get("pack_count", 0) or 0),
        reusable_count=int(catalog.get("reusable_count", 0) or 0),
    )
    return result


def stage_librarian_pack(
    *,
    state_root: str | Path,
    source_path: str | Path,
    workspace_root: str | Path | None = None,
    source_kind: str = "workspace_artifact",
) -> dict[str, Any]:
    source = Path(source_path)
    payload = _read_json(source)
    if not payload:
        return _rejection(
            state_root=state_root,
            reason="missing_or_unreadable",
            source_path=source,
            source_kind=source_kind,
        )
    kind = _pack_kind(payload)
    if not kind:
        return _rejection(
            state_root=state_root,
            reason="unsupported_schema",
            source_path=source,
            source_kind=source_kind,
        )
    family = _pack_family(payload, kind)
    if not family:
        return _rejection(
            state_root=state_root,
            reason="missing_pack_family",
            source_path=source,
            source_kind=source_kind,
            pack_kind=kind,
        )
    content = _canonical_content(payload)
    content_hash = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
    existing_entries = _catalog_entries(state_root)
    duplicate = next(
        (
            item
            for item in existing_entries
            if item.get("kind") == kind
            and item.get("family") == family
            and item.get("content_hash") == content_hash
        ),
        None,
    )
    if duplicate:
        existing_path = librarian_root(state_root) / str(duplicate.get("pack_path", ""))
        existing = _read_json(existing_path)
        if existing:
            existing["stage_result"] = "duplicate_existing_version"
            return existing
    latest = _latest_for_family(state_root, kind, family)
    version_ref = f"v_{_short_hash(content_hash, length=16)}"
    pack_id = f"{kind}:{_slug(family, fallback='family')}:{version_ref}"
    kind_slug = _slug(kind, fallback="pack")
    family_slug = _slug(family, fallback="family")
    relative_pack_path = f"packs/{kind_slug}/{family_slug}/{version_ref}.json"
    relative_latest_path = f"latest/{kind_slug}/{family_slug}.json"
    source_artifact_relative_path = _relative_to_workspace(workspace_root, source)
    supersedes = [str(latest.get("pack_id", ""))] if latest.get("pack_id") else []
    envelope = {
        "ok": True,
        "schema_name": "NovaliLibrarianPack",
        "schema_version": LIBRARIAN_SCHEMA_VERSION,
        "stage_result": "staged",
        "pack_id": pack_id,
        "pack_kind": kind,
        "pack_family": family,
        "version_ref": version_ref,
        "created_at": _now(),
        "source_kind": _safe_text(source_kind, max_chars=80),
        "source_ref": f"source_{_short_hash(source, length=12)}",
        "source_workspace_ref": f"workspace_{_short_hash(workspace_root, length=12)}" if workspace_root else "",
        "source_artifact_relative_path": source_artifact_relative_path,
        "content_hash": content_hash,
        "quality_state": "validated",
        "reuse_state": "reusable",
        "supersedes": supersedes,
        "superseded_by": "",
        "tags": _tags(payload, kind),
        "capability_kind": _safe_text(payload.get("capability_kind") or payload.get("capability_id"), max_chars=120),
        "directive_ref": f"directive_{_short_hash(payload.get('directive_id'), length=12)}"
        if payload.get("directive_id")
        else "",
        "payload_ref": f"payload_{_short_hash(content_hash, length=12)}",
        "payload_summary": _summary_payload(payload),
        "pack_path": relative_pack_path,
        "latest_path": relative_latest_path,
        "grants_execution_authority": False,
    }
    root = librarian_root(state_root)
    _write_json(root / relative_pack_path, envelope)
    _write_json(root / relative_latest_path, envelope)
    if latest.get("pack_path"):
        prior_path = root / str(latest.get("pack_path", ""))
        prior = _read_json(prior_path)
        if prior:
            prior["superseded_by"] = pack_id
            _write_json(prior_path, prior)
    _event(state_root, "pack_staged", envelope)
    catalog = _write_catalog(state_root)
    try:
        from .observability.enrichment import record_librarian_pack_staged

        record_librarian_pack_staged(envelope)
    except Exception:
        pass
    _write_health(
        state_root,
        state="ready",
        latest_action="pack_staged",
        latest_blocker="",
        pack_count=int(catalog.get("pack_count", 0) or 0),
        reusable_count=int(catalog.get("reusable_count", 0) or 0),
    )
    return envelope


def _candidate_paths(
    *,
    package_root: str | Path | None = None,
    workspace_root: str | Path | None = None,
) -> Iterable[tuple[Path, str, Path | None]]:
    if package_root:
        package = Path(package_root)
        for root in (package / "trusted_sources" / "knowledge_packs", package / "trusted_sources" / "skill_packs"):
            if root.exists():
                for path in sorted(root.glob("*.json")):
                    yield path, "packaged_seed", None
    if workspace_root:
        workspace = Path(workspace_root)
        for name in (
            "trusted_source_knowledge_pack_latest.json",
            "successor_skill_pack_result_latest.json",
            "successor_skill_pack_invocation_latest.json",
            "directive_outcome_track_progress_latest.json",
            "promotion_packet_latest.json",
        ):
            path = workspace / "artifacts" / name
            if path.exists():
                yield path, "workspace_artifact", workspace


def refresh_librarian_catalog(
    *,
    state_root: str | Path,
    package_root: str | Path | None = None,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    discovered = 0
    staged = 0
    rejected = 0
    for path, source_kind, source_workspace in _candidate_paths(
        package_root=package_root,
        workspace_root=workspace_root,
    ):
        discovered += 1
        result = stage_librarian_pack(
            state_root=state_root,
            source_path=path,
            workspace_root=source_workspace,
            source_kind=source_kind,
        )
        if str(result.get("stage_result", "")) in {"staged", "duplicate_existing_version"}:
            staged += 1
        else:
            rejected += 1
    catalog = _write_catalog(state_root)
    payload = {
        **catalog,
        "ok": True,
        "discovered_count": discovered,
        "staged_or_duplicate_count": staged,
        "rejected_count": rejected,
    }
    try:
        from .observability.enrichment import record_librarian_catalog_refresh

        record_librarian_catalog_refresh(
            {
                "result": "completed",
                "pack_count": int(catalog.get("pack_count", 0) or 0),
                "reusable_count": int(catalog.get("reusable_count", 0) or 0),
            }
        )
    except Exception:
        pass
    return payload


def librarian_status(state_root: str | Path) -> dict[str, Any]:
    catalog = _read_json(librarian_catalog_path(state_root))
    if not catalog:
        catalog = _write_catalog(state_root)
    health = _read_json(librarian_health_path(state_root))
    entries = [
        dict(item)
        for item in catalog.get("entries", [])
        if isinstance(item, Mapping)
    ] if isinstance(catalog.get("entries", []), list) else []
    kind_counts: dict[str, int] = {}
    for entry in entries:
        kind = str(entry.get("kind", "") or "unknown")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    latest_pack = max(
        entries,
        key=lambda item: str(item.get("created_at", "") or ""),
        default={},
    )
    latest_pack_summary = {
        "pack_id": _safe_text(latest_pack.get("pack_id", "")),
        "pack_kind": _safe_text(latest_pack.get("kind", "")),
        "pack_family": _safe_text(latest_pack.get("family", "")),
        "version_ref": _safe_text(latest_pack.get("version_ref", "")),
        "quality_state": _safe_text(latest_pack.get("quality_state", "")),
        "reuse_state": _safe_text(latest_pack.get("reuse_state", "")),
        "source_kind": _safe_text(latest_pack.get("source_kind", "")),
        "created_at": _safe_text(latest_pack.get("created_at", "")),
    }
    generated_at = str(catalog.get("generated_at", "") or "")
    age_seconds = 0.0
    if generated_at:
        try:
            created = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            age_seconds = max(
                0.0,
                round((datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds(), 3),
            )
        except ValueError:
            age_seconds = 0.0
    return {
        "ok": True,
        "schema_name": "NovaliLibrarianStatus",
        "schema_version": LIBRARIAN_HEALTH_SCHEMA_VERSION,
        "generated_at": _now(),
        "librarian_state": str(health.get("librarian_state", "ready") or "ready"),
        "librarian_pack_count": int(catalog.get("pack_count", 0) or 0),
        "librarian_reusable_count": int(catalog.get("reusable_count", 0) or 0),
        "librarian_kind_counts": kind_counts,
        "librarian_index_age_seconds": age_seconds,
        "latest_librarian_pack": latest_pack_summary,
        "latest_librarian_action": str(health.get("latest_librarian_action", "catalog_refresh") or "catalog_refresh"),
        "latest_librarian_blocker": str(health.get("latest_librarian_blocker", "") or ""),
    }


def search_librarian_catalog(
    state_root: str | Path,
    *,
    query: str = "",
    kind: str = "",
    family: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    catalog = _read_json(librarian_catalog_path(state_root))
    if not catalog:
        catalog = _write_catalog(state_root)
    entries = catalog.get("entries", [])
    query_text = str(query or "").strip().lower()
    kind_text = str(kind or "").strip().lower()
    family_text = str(family or "").strip().lower()
    results: list[dict[str, Any]] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, Mapping):
            continue
        if kind_text and str(entry.get("kind", "")).lower() != kind_text:
            continue
        if family_text and family_text not in str(entry.get("family", "")).lower():
            continue
        haystack = " ".join(
            str(entry.get(key, "") or "")
            for key in (
                "kind",
                "pack_id",
                "family",
                "quality_state",
                "reuse_state",
                "source_kind",
                "source_artifact_relative_path",
                "capability_kind",
                "directive_ref",
            )
        ).lower()
        tags = entry.get("tags", [])
        if isinstance(tags, list):
            haystack += " " + " ".join(str(item) for item in tags).lower()
        if query_text and query_text not in haystack:
            continue
        results.append(
            {
                "kind": str(entry.get("kind", "")),
                "pack_id": str(entry.get("pack_id", "")),
                "family": str(entry.get("family", "")),
                "version_ref": str(entry.get("version_ref", "")),
                "quality_state": str(entry.get("quality_state", "")),
                "reuse_state": str(entry.get("reuse_state", "")),
                "source_kind": str(entry.get("source_kind", "")),
                "source_ref": str(entry.get("source_ref", "")),
                "source_workspace_ref": str(entry.get("source_workspace_ref", "")),
                "source_artifact_relative_path": str(entry.get("source_artifact_relative_path", "")),
                "tags": list(entry.get("tags", []))[:16] if isinstance(entry.get("tags"), list) else [],
                "capability_kind": str(entry.get("capability_kind", "")),
                "directive_ref": str(entry.get("directive_ref", "")),
                "pack_path": str(entry.get("pack_path", "")),
            }
        )
        if len(results) >= max(1, int(limit or 1)):
            break
    return {
        "ok": True,
        "schema_name": "NovaliLibrarianSearch",
        "schema_version": LIBRARIAN_SEARCH_SCHEMA_VERSION,
        "generated_at": _now(),
        "query": _safe_text(query_text, max_chars=80),
        "kind": _safe_text(kind_text, max_chars=80),
        "family": _safe_text(family_text, max_chars=80),
        "result_count": len(results),
        "results": results,
        "catalog_generated_at": str(catalog.get("generated_at", "")),
    }


def _entry_matches_reuse_filters(
    entry: Mapping[str, Any],
    *,
    kind: str = "",
    family: str = "",
    tag: str = "",
    capability_kind: str = "",
    directive_ref: str = "",
) -> tuple[bool, str]:
    if str(entry.get("reuse_state", "") or "") != "reusable":
        return False, "reuse_state_not_reusable"
    if kind and str(entry.get("kind", "") or "").lower() != str(kind).strip().lower():
        return False, "pack_kind_filter_no_match"
    if family and str(family).strip().lower() not in str(entry.get("family", "") or "").lower():
        return False, "pack_family_filter_no_match"
    if capability_kind and str(entry.get("capability_kind", "") or "").lower() != str(capability_kind).strip().lower():
        return False, "capability_kind_filter_no_match"
    if directive_ref and str(entry.get("directive_ref", "") or "").lower() != str(directive_ref).strip().lower():
        return False, "directive_filter_no_match"
    if tag:
        tags = entry.get("tags", [])
        haystack = " ".join(str(item) for item in tags if isinstance(item, str)).lower()
        if str(tag).strip().lower() not in haystack:
            return False, "tag_filter_no_match"
    return True, ""


def _reuse_result_from_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "reusable": True,
        "reuse_decision": "reusable_pack_selected",
        "selection_reason": "latest_reusable_version",
        "pack_id": str(entry.get("pack_id", "")),
        "pack_kind": str(entry.get("kind", "")),
        "pack_family": str(entry.get("family", "")),
        "version_ref": str(entry.get("version_ref", "")),
        "quality_state": str(entry.get("quality_state", "")),
        "reuse_state": str(entry.get("reuse_state", "")),
        "source_kind": str(entry.get("source_kind", "")),
        "source_ref": str(entry.get("source_ref", "")),
        "source_workspace_ref": str(entry.get("source_workspace_ref", "")),
        "source_artifact_relative_path": str(entry.get("source_artifact_relative_path", "")),
        "tags": list(entry.get("tags", []))[:16] if isinstance(entry.get("tags"), list) else [],
        "capability_kind": str(entry.get("capability_kind", "")),
        "directive_ref": str(entry.get("directive_ref", "")),
        "pack_path": str(entry.get("pack_path", "")),
        "grants_execution_authority": False,
    }


def latest_reusable_librarian_pack(
    state_root: str | Path,
    *,
    kind: str = "",
    family: str = "",
    tag: str = "",
    capability_kind: str = "",
    directive_ref: str = "",
) -> dict[str, Any]:
    catalog = _read_json(librarian_catalog_path(state_root))
    if not catalog:
        catalog = _write_catalog(state_root)
    entries = catalog.get("entries", [])
    blockers: list[str] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, Mapping):
            continue
        matched, blocker = _entry_matches_reuse_filters(
            entry,
            kind=kind,
            family=family,
            tag=tag,
            capability_kind=capability_kind,
            directive_ref=directive_ref,
        )
        if matched:
            result = _reuse_result_from_entry(entry)
            try:
                from .observability.enrichment import record_librarian_pack_reused

                record_librarian_pack_reused(result)
            except Exception:
                pass
            return result
        if blocker and blocker not in blockers:
            blockers.append(blocker)
    return {
        "ok": True,
        "reusable": False,
        "reuse_decision": "no_reusable_pack",
        "selection_reason": "",
        "blockers": blockers or ["catalog_empty"],
        "pack_kind": _safe_text(kind, max_chars=80),
        "pack_family": _safe_text(family, max_chars=120),
        "capability_kind": _safe_text(capability_kind, max_chars=120),
        "directive_ref": _safe_text(directive_ref, max_chars=80),
        "grants_execution_authority": False,
    }


def librarian_pack_summaries_by_refs(
    state_root: str | Path,
    pack_refs: Iterable[str],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    catalog = _read_json(librarian_catalog_path(state_root))
    entries = catalog.get("entries", [])
    wanted: list[str] = []
    seen: set[str] = set()
    for ref in pack_refs:
        text = str(ref or "").strip()
        if text and text not in seen:
            seen.add(text)
            wanted.append(text)
        if len(wanted) >= max(1, int(limit or 1)):
            break
    if not wanted or not isinstance(entries, list):
        return []
    by_id = {
        str(entry.get("pack_id", "") or ""): dict(entry)
        for entry in entries
        if isinstance(entry, Mapping)
    }
    summaries: list[dict[str, Any]] = []
    root = librarian_root(state_root)
    for pack_id in wanted:
        entry = by_id.get(pack_id)
        if not entry:
            continue
        envelope = _read_json(root / str(entry.get("pack_path", "") or ""))
        payload_summary = (
            dict(envelope.get("payload_summary", {}) or {})
            if isinstance(envelope.get("payload_summary", {}), Mapping)
            else {}
        )
        summaries.append(
            {
                "pack_id": _safe_text(pack_id, max_chars=180),
                "pack_kind": _safe_text(entry.get("kind", ""), max_chars=80),
                "pack_family": _safe_text(entry.get("family", ""), max_chars=120),
                "quality_state": _safe_text(entry.get("quality_state", ""), max_chars=80),
                "reuse_state": _safe_text(entry.get("reuse_state", ""), max_chars=80),
                "source_kind": _safe_text(entry.get("source_kind", ""), max_chars=80),
                "source_artifact_relative_path": _safe_text(
                    entry.get("source_artifact_relative_path", ""),
                    max_chars=180,
                ),
                "tags": [
                    _safe_text(item, max_chars=80)
                    for item in list(entry.get("tags", []) or [])
                    if isinstance(item, str) and item.strip()
                ][:16],
                "payload_summary": payload_summary,
                "grants_execution_authority": False,
            }
        )
    return summaries


def explain_librarian_reuse(
    state_root: str | Path,
    *,
    kind: str = "",
    family: str = "",
    tag: str = "",
    capability_kind: str = "",
    directive_ref: str = "",
) -> dict[str, Any]:
    result = latest_reusable_librarian_pack(
        state_root,
        kind=kind,
        family=family,
        tag=tag,
        capability_kind=capability_kind,
        directive_ref=directive_ref,
    )
    return {
        "ok": True,
        "schema_name": "NovaliLibrarianReuseExplanation",
        "schema_version": LIBRARIAN_SEARCH_SCHEMA_VERSION,
        "generated_at": _now(),
        **result,
    }

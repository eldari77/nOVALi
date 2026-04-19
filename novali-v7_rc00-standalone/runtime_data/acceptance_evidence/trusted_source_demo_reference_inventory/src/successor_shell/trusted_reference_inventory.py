from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_ROLES = (
    "v5_status_surface",
    "v5_handoff_readme",
    "v5_operator_guide",
    "v5_web_ui_guide",
    "v5_branch_transition_status",
    "v5_version_handoff_status",
    "v5_handoff_layout_manifest",
    "v5_standalone_zip",
)


def build_reference_inventory(
    *,
    capability_id: str,
    workspace_root: str | Path,
    evidence_items: list[dict[str, Any]],
    knowledge_pack: dict[str, Any],
    request: dict[str, Any],
    active_bounded_reference_target_id: str,
) -> dict[str, Any]:
    evidence_by_role = {
        str(item.get("role_id", "")).strip(): dict(item)
        for item in list(evidence_items)
        if str(item.get("role_id", "")).strip()
    }
    role_rows: list[dict[str, Any]] = []
    present_role_ids: list[str] = []
    for role_id in REQUIRED_ROLES:
        evidence = dict(evidence_by_role.get(role_id, {}))
        present = bool(evidence.get("present", False))
        if present:
            present_role_ids.append(role_id)
        role_rows.append(
            {
                "role_id": role_id,
                "title": str(evidence.get("title", role_id)),
                "source_id": str(evidence.get("source_id", "")),
                "absolute_path": str(evidence.get("absolute_path", "")),
                "relative_path": str(evidence.get("relative_path", "")),
                "present": present,
                "sha256": str(evidence.get("sha256", "")),
                "size_bytes": int(evidence.get("size_bytes", 0) or 0),
                "why_relevant": str(evidence.get("why_relevant", "")),
            }
        )
    missing_role_ids = [
        role_id for role_id in REQUIRED_ROLES if role_id not in present_role_ids
    ]
    workspace_root_path = Path(workspace_root)
    return {
        "schema_name": "GovernedExecutionTrustedSourceReferenceInventory",
        "schema_version": "governed_execution_trusted_source_reference_inventory_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "capability_id": capability_id,
        "workspace_root": str(workspace_root_path),
        "knowledge_pack_id": str(knowledge_pack.get("knowledge_pack_id", "")),
        "request_id": str(request.get("request_id", "")),
        "active_bounded_reference_target_id": active_bounded_reference_target_id,
        "required_role_ids": list(REQUIRED_ROLES),
        "present_role_ids": present_role_ids,
        "missing_role_ids": missing_role_ids,
        "required_roles_satisfied": not missing_role_ids,
        "role_rows": role_rows,
    }

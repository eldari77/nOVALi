"""Stable input identity for bounded support retries; no execution authority."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


RETRY_LIMIT = 2
_VOLATILE = {
    "created_at", "updated_at", "generated_at", "retrieved_at", "retrieval_timestamp",
    "source_plan_id", "provider_field_lane_request_id", "configured_adapter_path",
}
_SET_FIELDS = {"required_fields", "missing_fields", "uncovered_requested_row_ids",
               "accepted_requested_row_ids", "requested_rows", "source_candidates"}


def _semantic(value: Any, key: str = "") -> Any:
    if isinstance(value, Mapping):
        return {str(k): _semantic(v, str(k)) for k, v in value.items() if k not in _VOLATILE}
    if isinstance(value, (list, tuple)):
        items = [_semantic(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True)) if key in _SET_FIELDS else items
    return value


def support_input_fingerprint(support: Mapping[str, Any], *, source_plan: Mapping[str, Any],
                              adapters: Mapping[str, Any]) -> str:
    """Include evidence/contract/review changes while ignoring observation churn."""
    fields = (
        "support_request_id", "directive_id", "target_artifact", "requested_rows",
        "required_fields", "missing_fields", "uncovered_requested_row_ids", "accepted_requested_row_ids",
        "operator_seed_pack_policy", "operator_review_decision", "review_decision",
        "review_revision", "reviewed_at", "evidence_revision", "source_candidates",
        "support_synthesis_contract_fingerprint",
        "operator_review_required", "accepted_field_lane_rows", "support_evidence_contract_passed",
        "support_synthesis_backoff_expired_at",
    )
    payload = {
        "retry_policy_version": 1,
        "support": {key: support[key] for key in fields if key in support},
        "source_candidates": list(source_plan.get("source_candidates", []) or []),
        "adapters": dict(adapters),
    }
    return hashlib.sha256(json.dumps(_semantic(payload), sort_keys=True, allow_nan=False).encode()).hexdigest()

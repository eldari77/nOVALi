"""Operator-issued semantic reviews and immutable, planner-authored responses.

Publishing and approving reviews are deliberately absent from the planner tools.
Filesystem write authority is the same operator boundary as existing governance.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .research_tools import digest, identifier, read_json, write_json
from .theory_workspace import text
from .research_semantics import LESSONS, validate_measurement_contract

VERSION = "research_feedback_v1"


def _store(root: Path, kind: str, body: Mapping[str, Any]) -> dict[str, Any]:
    payload = {"version": VERSION, **dict(body), "grants_execution_authority": False,
        "scientific_progress_credited": False}
    key = kind.rstrip("s") + "-" + digest(payload)[:24]
    record = {"id": key, **payload}
    path = root / "research_feedback" / kind / (key + ".json")
    if path.exists():
        if read_json(path) != record:
            raise ValueError("immutable_review_record_integrity_failure")
    else:
        write_json(path, record)
    return record


def _read(root: Path, kind: str, key: str) -> dict[str, Any]:
    identifier(key)
    record = read_json(root / "research_feedback" / kind / (key + ".json"))
    body = {k: v for k, v in record.items() if k != "id"}
    if not record or record.get("id") != key or key != kind.rstrip("s") + "-" + digest(body)[:24]:
        raise ValueError("immutable_review_record_integrity_failure")
    return record


def _target(root: Path, path: Path) -> dict[str, Any]:
    root = root.resolve(); path = path.resolve()
    if not path.is_relative_to(root) or path.suffix != ".json":
        raise ValueError("review_target_path_rejected")
    parts = path.relative_to(root).parts
    record = read_json(path)
    if len(parts) == 5 and parts[:2] == ("theory", "subjects") and parts[3] in {"claims", "capability_requests"}:
        scope = Path(*parts[:3]).as_posix()
        snapshot = read_json(root / scope / "snapshot.json")
        if record.get("snapshot_id") != snapshot.get("snapshot_id"):
            raise ValueError("review_target_snapshot_changed")
        key = record.get("id", "")
        if key != path.stem or key != key.rsplit("-", 1)[0] + "-" + digest({k:v for k,v in record.items() if k != "id"})[:24]:
            raise ValueError("review_target_integrity_failure")
    elif parts[:3] == ("conveyor", "research", "capability_requests") and len(parts) == 4:
        episode = identifier(record.get("episode_id"))
        scope = "conveyor/research/episodes/" + episode
        contract = read_json(root / scope / "contract.json")
        if not contract or record.get("contract_sha256") != digest(contract):
            raise ValueError("review_target_contract_changed")
        if "id" in record and (record["id"] != path.stem or record["id"] != "capability-" + digest({k:v for k,v in record.items() if k != "id"})[:24]):
            raise ValueError("review_target_integrity_failure")
    elif len(parts) == 3 and parts[:2] == ("research_methods", "requests"):
        from .research_procedures import read as read_method
        from .method_learning import origin
        record = read_method(root, "requests", path.stem)
        scope, snapshot_id = origin(root, record)
        return {"scope_path": scope, "record_path": path.relative_to(root).as_posix(),
            "record_id": record["id"], "record_sha256": digest(record), "snapshot_id": snapshot_id, "record": record}
    else:
        raise ValueError("review_target_kind_rejected")
    if not record:
        raise ValueError("review_target_missing")
    return {"scope_path": scope, "record_path": path.relative_to(root).as_posix(),
        "record_id": record.get("id", record.get("episode_id")), "record_sha256": digest(record),
        "snapshot_id": record.get("snapshot_id", record.get("contract_sha256")), "record": record}


def publish_review(root: Path, target_path: Path, *, reviewer: str, authority_reference: str,
                   findings: list[dict[str, str]], verdict: str = "revise", supersedes: str = "",
                   verified_codes: list[str] | None = None) -> dict[str, Any]:
    """Operator entry point. Review readiness grants neither tools nor budgets."""
    target = _target(root, target_path)
    if target["record_path"].startswith("research_methods/") and verdict in {"specification_ready", "correction_verified"}:
        from .method_learning import validate_revision
        from .research_procedures import read as read_method
        record = target["record"]
        original = read_method(root, "requests", record.get("root_request_id", record["id"]))
        validate_revision(root, original, record.get("proposal", {}))
    text(reviewer, "reviewer", 200); text(authority_reference, "authority_reference", 500)
    if verdict not in {"revise", "reject", "specification_ready", "correction_verified"}:
        raise ValueError("explicit_review_verdict_required")
    if not isinstance(findings, list) or not 0 <= len(findings) <= 6 or (verdict in {"revise", "reject"} and not findings):
        raise ValueError("bounded_review_findings_required")
    codes = []
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {"code", "requirement"}:
            raise ValueError("typed_review_finding_required")
        codes.append(identifier(finding["code"]))
        text(finding["requirement"], "review_requirement", 500)
    if len(set(codes)) != len(codes):
        raise ValueError("duplicate_review_finding")
    if verified_codes is not None and (verdict != "correction_verified" or not isinstance(verified_codes,list)
            or not verified_codes or len(verified_codes)!=len(set(verified_codes))
            or any(code not in LESSONS for code in verified_codes) or set(codes)&set(verified_codes)):
        raise ValueError("explicit_disjoint_verified_finding_codes_required")
    if verdict == "specification_ready" and "/capability_requests/" in target["record_path"]:
        request = target["record"].get("request", target["record"])
        if not validate_measurement_contract(request.get("measurement_contract"))["specification_complete"]:
            raise ValueError("unresolved_specification_cannot_be_accepted")
    if verdict == "correction_verified":
        if findings and verified_codes is None:
            raise ValueError("verified_correction_requires_all_prior_findings_resolved")
        matches = [_read(root, "responses", p.stem) for p in (root / "research_feedback/responses").glob("*.json")]
        matches = [r for r in matches if r["revised_record_sha256"] == target["record_sha256"] and r["revised_record_path"] == target["record_path"]]
        if not matches:
            raise ValueError("linked_correction_required_for_procedural_review")
        if verified_codes is not None:
            prior_codes={f['code'] for r in matches for f in _read(root,'reviews',r['review_id'])['findings']}
            if not set(verified_codes)<=prior_codes or not prior_codes-set(verified_codes)<=set(codes):
                raise ValueError("verified_codes_must_match_prior_findings_and_keep_unresolved_findings_open")
        if "/capability_requests/" in target["record_path"]:
            validate_measurement_contract(target["record"].get("request",target["record"]).get("measurement_contract"))
    body = {"target": {k:v for k,v in target.items() if k != "record"},
        "reviewer": reviewer, "authority_reference": authority_reference, "verdict": verdict,
        "findings": findings, "supersedes": supersedes}
    if verified_codes is not None: body['verified_codes']=sorted(verified_codes)
    active = [r for r in _active_reviews(root) if r["target"] == body["target"]]
    if active:
        current = active[0]
        if all(current.get(k) == v for k,v in body.items()):
            return current
        if supersedes != current["id"]:
            raise ValueError("explicit_current_review_supersession_required")
    elif supersedes:
        raise ValueError("current_review_to_supersede_required")
    review = _store(root, "reviews", body)
    if verdict in {"specification_ready", "correction_verified"}:
        # A lesson requires an independently reviewed correction, not just a
        # request, model self-assessment, or existence of a prior rejection.
        for path in sorted((root / "research_feedback/responses").glob("*.json"))[-512:]:
            response = _read(root, "responses", path.stem)
            if (response["revised_record_sha256"] != target["record_sha256"]
                    or response["revised_record_path"] != target["record_path"]):
                continue
            parent = _read(root, "reviews", response["review_id"])
            for finding in parent["findings"]:
                if finding["code"] in LESSONS and (verified_codes is None or finding['code'] in verified_codes):
                    _store(root, "lessons", {"code": finding["code"], "procedure": LESSONS[finding["code"]],
                        "review_id": review["id"], "response_id": response["id"],
                        "evidence_scope": "independently_reviewed_procedural_correction_transfer_unproven"})
    return review


def _active_reviews(root: Path) -> list[dict[str, Any]]:
    reviews = [_read(root, "reviews", p.stem) for p in (root / "research_feedback/reviews").glob("*.json")]
    by_id = {r["id"]: r for r in reviews}
    superseded = set()
    for review in reviews:
        prior = review.get("supersedes")
        if prior:
            if prior not in by_id or by_id[prior]["target"] != review["target"] or prior in superseded:
                raise ValueError("review_supersession_integrity_failure")
            superseded.add(prior)
    return [r for r in reviews if r["id"] not in superseded]


def feedback_context(root: Path, scope_path: Path) -> dict[str, Any]:
    scope = scope_path.resolve().relative_to(root.resolve()).as_posix()
    responses = [_read(root, "responses", p.stem) for p in sorted((root / "research_feedback/responses").glob("*.json"))[-512:]]
    answered = {r["review_id"] for r in responses}
    pending = []
    active = _active_reviews(root)
    active_ids = {r["id"] for r in active}
    for review in active:
        if (review["target"]["scope_path"] != scope or review["verdict"] not in {"revise", "correction_verified"}
                or not review['findings'] or review["id"] in answered):
            continue
        try:
            target = _target(root, root / review["target"]["record_path"])
        except ValueError as exc:
            if str(exc) in {"review_target_snapshot_changed", "review_target_contract_changed"}:
                continue
            raise
        if target["record_sha256"] != review["target"]["record_sha256"]:
            raise ValueError("review_target_integrity_failure")
        pending.append({**review, "target_record": target["record"]})
    lessons = []
    for path in sorted((root / "research_feedback/lessons").glob("*.json"))[-64:]:
        lesson = _read(root, "lessons", path.stem)
        reviewed = _read(root, "reviews", lesson["review_id"])
        response = _read(root, "responses", lesson["response_id"])
        parent = _read(root, "reviews", response["review_id"])
        revised = read_json(root / response["revised_record_path"])
        if (reviewed["verdict"] not in {"specification_ready", "correction_verified"}
                or reviewed["target"]["record_sha256"] != response["revised_record_sha256"]
                or digest(revised) != response["revised_record_sha256"]
                or lesson["code"] not in {f["code"] for f in parent["findings"]}
                or ('verified_codes' in reviewed and lesson['code'] not in reviewed['verified_codes'])
                or lesson["procedure"] != LESSONS.get(lesson["code"])):
            raise ValueError("reviewed_lesson_integrity_failure")
        if reviewed["id"] not in active_ids or parent["id"] not in active_ids:
            continue
        if lesson["code"] not in {x["code"] for x in lessons}:
            lessons.append({k:lesson[k] for k in ("id", "code", "procedure", "evidence_scope")})
    from .research_procedures import context as procedure_context
    from .method_learning import corrections_context
    return {"version": VERSION, "pending_reviews": pending[-2:], "procedural_lessons": lessons[-6:],
        "adopted_procedures": procedure_context(root),
        "reviewed_method_corrections": corrections_context(root),
        "review_is_not_execution_authority": True, "review_does_not_renew_budget": True}


def validate_response(root: Path, scope_path: Path, review_id: str,
                      resolutions: Mapping[str, str]) -> dict[str, Any]:
    pending = feedback_context(root, scope_path)["pending_reviews"]
    review = next((r for r in pending if r["id"] == review_id), None)
    if review is None:
        raise ValueError("current_unanswered_review_required")
    if not isinstance(resolutions, dict) or set(resolutions) != {f["code"] for f in review["findings"]}:
        raise ValueError("address_every_review_finding")
    for resolution in resolutions.values():
        text(resolution, "review_resolution", 500)
    return review


def record_response(root: Path, review: Mapping[str, Any], revised_path: Path,
                    resolutions: Mapping[str, str]) -> dict[str, Any]:
    original = validate_response(root, root / review["target"]["scope_path"], review["id"], resolutions)
    revised = _target(root, revised_path)
    if revised["scope_path"] != original["target"]["scope_path"] or revised["snapshot_id"] != original["target"]["snapshot_id"]:
        raise ValueError("review_response_scope_mismatch")
    if revised["record_sha256"] == original["target"]["record_sha256"]:
        raise ValueError("review_response_requires_changed_proposal")
    return _store(root, "responses", {"review_id": review["id"], "parent_record_id": original["target"]["record_id"],
        "parent_record_sha256": original["target"]["record_sha256"], "revised_record_id": revised["record_id"],
        "revised_record_path": revised["record_path"], "revised_record_sha256": revised["record_sha256"],
        "resolutions": dict(resolutions), "status": "awaiting_independent_reassessment"})


def resume_reviewed_work(root: Path, scope: Path, state: dict[str, Any], limit: int, *, enabled: bool = True) -> dict[str, Any]:
    """A changed review may wake existing allowance once; it never supplies calls."""
    status = read_json(root / "autonomy/status.json")
    if (not enabled or status.get("emergency_stop") or status.get("active") is False
            or not state or state.get("inflight") or not state.get("state", "").startswith("waiting_")
            or state["usage"]["model_calls"] >= limit
            or any(word in state.get("feedback", "") for word in ("integrity", "private", "interrupted", "outcome_unknown"))):
        return state
    if any(state["usage"][key] >= value for key,value in state.get("work", {}).get("limits", {}).items()
           if key in {"tool_calls", "compute_seconds"}):
        return state
    reviews = feedback_context(root, scope)["pending_reviews"]
    attempted = {*state.get("reviews_woken", []), *state.get("preflight_blocked_reviews", [])}
    fresh = [r["id"] for r in reviews if r["id"] not in attempted]
    if fresh:
        state.update(state="ready" if "work" in state else "planning",
            feedback="A relevant independent review is available. Address its findings using retained evidence and the existing budget.",
            reviews_woken=[*state.get("reviews_woken", []), *fresh])
    return state

"""Small, bounded research tools. Observations never confer execution authority.

Numerical experiments interpret an arithmetic expression tree; they do not run
model-authored Python, import modules, open files, or access the network.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import operator
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote, urlsplit

from .source_evidence import MAX_BYTES, ProductTables, cache_source, fetch_public_html

MAX_ARTIFACT_BYTES = 250_000
TOOLS = {"inspect_artifact", "compare_artifacts", "fetch_source", "search_sources", "simulate"}
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Pow: operator.pow}
FUNCTIONS = {"abs": abs, "min": min, "max": max, "sqrt": math.sqrt,
             "sin": math.sin, "cos": math.cos, "exp": math.exp, "log": math.log, "tanh": math.tanh}


def normalize_action(action: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(action, Mapping):
        raise ValueError("research_action_object_required")
    arguments = action.get("arguments", {})
    if not isinstance(arguments, Mapping) or set(arguments) & {"id", "tool", "arguments"}:
        raise ValueError("invalid_research_tool_arguments")
    flat = {key: value for key, value in action.items() if key != "arguments"}
    if any(key in flat and flat[key] != value for key, value in arguments.items()):
        raise ValueError("conflicting_research_tool_arguments")
    return {**flat, **arguments}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(",", ":")).encode()).hexdigest()


def read_json(path: Path, limit: int = 1_000_000) -> dict[str, Any]:
    if not path.is_file():
        return {}
    if path.stat().st_size > limit:
        raise ValueError("research_record_size_limit")
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("research_object_required")
    return result


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    import os
    import uuid

    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if len(payload.encode()) > 1_000_000:
        raise ValueError("research_record_size_limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def identifier(value: Any) -> str:
    value = str(value)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}", value):
        raise ValueError("invalid_research_identifier")
    return value


def artifact_path(root: Path, directive_id: str, reference: str) -> Path:
    campaigns = (root / "conveyor/campaigns").resolve()
    base = (campaigns / identifier(directive_id)).resolve()
    if not base.is_relative_to(campaigns):
        raise ValueError("research_campaign_path_rejected")
    relative = Path(reference.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 2:
        raise ValueError("research_artifact_path_rejected")
    if relative.parts[0] not in {"canonical", "drafts"} or relative.suffix not in {".json", ".md"}:
        raise ValueError("research_artifact_path_rejected")
    path = base / relative
    if path.is_symlink() or not path.resolve().is_relative_to(base):
        raise ValueError("research_artifact_path_rejected")
    return path


def artifact_inventory(root: Path, directive_id: str) -> dict[str, Any]:
    base = root / "conveyor/campaigns" / identifier(directive_id)
    inventory: dict[str, Any] = {}
    for lane in ("canonical", "drafts"):
        directory = base / lane
        # Fixed file/count/byte limits keep hot-loop work bounded.
        if not directory.is_dir():
            continue
        paths = sorted(directory.iterdir())
        if len(paths) > 64:
            raise ValueError("research_artifact_inventory_limit")
        for path in paths:
            if path.suffix not in {".json", ".md"} or not path.is_file():
                continue
            reference = f"{lane}/{path.name}"
            path = artifact_path(root, directive_id, reference)
            if path.stat().st_size > MAX_ARTIFACT_BYTES:
                inventory[reference] = {"unavailable": "artifact_size_limit"}
                continue
            body = path.read_bytes()
            inventory[reference] = {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    return inventory


def inspect_artifact(root: Path, task: Mapping[str, Any], reference: str, *, offset_chars: int = 0) -> dict[str, Any]:
    if type(offset_chars) is not int or not 0 <= offset_chars <= MAX_ARTIFACT_BYTES:
        raise ValueError("invalid_artifact_excerpt_offset")
    expected = task["artifacts"].get(reference, {})
    if not expected.get("sha256"):
        raise ValueError("artifact_not_in_frozen_inventory")
    path = artifact_path(root, task["directive_id"], reference)
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("artifact_size_limit")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != expected["sha256"]:
        raise ValueError("artifact_revision_changed")
    text = body.decode("utf-8", errors="replace")
    return {"artifact_ref": reference, "sha256": expected["sha256"], "text": text[offset_chars:offset_chars + 12000],
            "offset_chars": offset_chars, "next_offset_chars": min(len(text), offset_chars + 4000),
            "text_truncated": offset_chars > 0 or len(text) > offset_chars + 12000,
            "metrics": {"bytes": len(body), "numeric_token_count": len(re.findall(r"\b\d+(?:\.\d+)?\b", text))},
            "scope": "artifact_content_only"}


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite_numeric_value_required")
    if abs(value) > 1e12:
        raise ValueError("numeric_magnitude_limit")
    return float(value)


def evaluate_expression(expression: str, variables: Mapping[str, float]) -> float:
    if not isinstance(expression, str) or len(expression) > 500:
        raise ValueError("expression_size_limit")
    tree = ast.parse(expression, mode="eval")
    if len(list(ast.walk(tree))) > 80:
        raise ValueError("expression_complexity_limit")

    def visit(node: ast.AST, depth: int = 0) -> float:
        if depth > 16:
            raise ValueError("expression_depth_limit")
        if isinstance(node, ast.Constant):
            return _number(node.value)
        if isinstance(node, ast.Name) and node.id in variables:
            return _number(variables[node.id])
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return _number((-1 if isinstance(node.op, ast.USub) else 1) * visit(node.operand, depth + 1))
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            left, right = visit(node.left, depth + 1), visit(node.right, depth + 1)
            if isinstance(node.op, ast.Pow) and abs(right) > 8:
                raise ValueError("exponent_limit")
            return _number(OPS[type(node.op)](left, right))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in FUNCTIONS and not node.keywords and 1 <= len(node.args) <= 3):
            return _number(FUNCTIONS[node.func.id](*(visit(arg, depth + 1) for arg in node.args)))
        raise ValueError("expression_operation_rejected")

    return visit(tree.body)


def simulate(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate matched arithmetic models on identical, frozen input cases."""
    cases, variants = spec.get("cases", []), spec.get("variants", {})
    if not isinstance(cases, list) or not 2 <= len(cases) <= 32:
        raise ValueError("simulation_case_limit")
    if not isinstance(variants, dict) or not 2 <= len(variants) <= 4 or "baseline" not in variants:
        raise ValueError("matched_baseline_required")
    outputs: dict[str, Any] = {}
    for name, expression in variants.items():
        identifier(name)
        values, errors = [], []
        for case in cases:
            if not isinstance(case, dict) or not isinstance(case.get("inputs"), dict) or len(case["inputs"]) > 12:
                raise ValueError("simulation_input_limit")
            inputs = {identifier(key): _number(value) for key, value in case["inputs"].items()}
            value = evaluate_expression(expression, inputs)
            values.append(value)
            errors.append((value - _number(case["expected"])) ** 2)
        outputs[name] = {"values": values, "mse": sum(errors) / len(errors), "case_count": len(cases)}
    metrics = {f"{name}_mse": result["mse"] for name, result in outputs.items()}
    if "candidate" in outputs:
        metrics["candidate_gain"] = outputs["baseline"]["mse"] - outputs["candidate"]["mse"]
    return {"variants": outputs, "metrics": metrics, "cases_sha256": digest(cases),
            "scope": "exploratory_model_consistency_only", "independent_holdout": False,
            "real_world_validation": False, "growth_demonstrated": False}


def _fetch_document(root: Path, action: Mapping[str, Any], task: Mapping[str, Any]) -> dict[str, Any]:
    url = str(action.get("url", ""))
    # Sources are public documents. Query-bearing source URLs are not necessary
    # for this tool and would allow a planner to transmit contextual text.
    if urlsplit(url).query:
        raise ValueError("source_query_not_allowed_use_search_tool")
    body = fetch_public_html(url)
    parser = ProductTables()
    parser.feed(body.decode("utf-8", errors="replace"))
    visible = " ".join(" ".join(parser.text).split())
    if not visible:
        raise ValueError("source_visible_content_missing")
    content_hash = hashlib.sha256(body).hexdigest()
    directory = root / "conveyor/research/documents"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{content_hash}.html").write_bytes(body)
    receipt = {"url": url, "sha256": content_hash, "retrieved_at": datetime.now(timezone.utc).isoformat(),
               "evidence_kind": "source_document", "grants_execution_authority": False}
    write_json(directory / f"{digest(url)}.json", receipt)
    result = {**receipt, "text": visible[:12000], "text_truncated": len(visible) > 12000,
              "metrics": {"bytes": len(body), "visible_chars": len(visible)}, "scope": "source_text_only"}
    # Exact product facts also enter the existing, independently validated cache.
    if action.get("expected_mpn"):
        row_id = action.get("requested_row_id")
        if row_id not in {row.get("requested_row_id") for row in task["requested_rows"]}:
            raise ValueError("source_requested_row_binding_required")
        candidate = {"source_candidate_id": "source-research-" + digest([url, row_id])[:16],
                     "source_url": url, "requested_row_id": row_id, "target_artifact": task["target_artifact"],
                     "expected_mpn": action["expected_mpn"], "expected_manufacturer": action.get("expected_manufacturer", "")}
        cached = cache_source(root, candidate, body, final_url=url)
        result["product_fields"] = cached["fields"]
        result["source_candidate"] = candidate
    return result


def run_tool(root: Path, task: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any]:
    action = normalize_action(action)
    tool = action.get("tool")
    if tool == "inspect_artifact":
        return inspect_artifact(root, task, str(action.get("artifact_ref", "")), offset_chars=action.get("offset_chars", 0))
    if tool == "compare_artifacts":
        before = inspect_artifact(root, task, str(action.get("before_ref", "")))
        after = inspect_artifact(root, task, str(action.get("after_ref", "")))
        changed = before["sha256"] != after["sha256"]
        return {"before": before, "after": after, "metrics": {"content_changed": int(changed)},
                "scope": "content_difference_only_not_scientific_novelty"}
    if tool == "fetch_source":
        return _fetch_document(root, action, task)
    if tool == "search_sources":
        # Public bibliographic discovery only. The query is explicit and logged;
        # documents returned by search still need a separate source fetch.
        from .source_evidence import fetch_public_response
        query = str(action.get("query", "")).strip()
        if not 3 <= len(query) <= 240 or re.search(r"[\r\n]|sk-|api[_ -]?key|password|token=", query, re.I):
            raise ValueError("public_research_query_required")
        body = fetch_public_response("https://api.crossref.org/works?rows=5&query.bibliographic=" + quote(query),
                                     content_types=("application/json",))
        payload = json.loads(body)
        entries = [{"title": str((row.get("title") or [""])[0])[:400], "doi": str(row.get("DOI", "")),
                    "url": str(row.get("URL", "")), "publisher": str(row.get("publisher", ""))[:200]}
                   for row in payload.get("message", {}).get("items", [])[:5]]
        return {"query": query, "entries": entries, "metrics": {"result_count": len(entries)},
                "sha256": hashlib.sha256(body).hexdigest(), "scope": "bibliographic_discovery_only"}
    if tool == "simulate":
        return simulate(action.get("spec", {}))
    raise ValueError("research_tool_not_allowed")

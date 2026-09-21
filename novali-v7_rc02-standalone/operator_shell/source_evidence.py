"""Bounded, explicit public-source retrieval and repeatable table extraction.

The parent or budgeted research coordinator can fetch; ordinary support reads
consume the cache without network calls.
Product facts are partial evidence, never substitutes for project design fields.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

MAX_BYTES = 2_000_000
IDENTITY_FIELDS = ("source_candidate_id", "source_url", "requested_row_id", "target_artifact")
HEADERS = {
    "output frequency sine": "sine_frequency", "output frequency square": "square_frequency",
    "channels": "channels", "arbitrary waveform length": "arbitrary_waveform_length",
    "sample rate": "sample_rate", "price": "unit_cost", "unit price": "unit_cost",
}


class ProductTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[list[str], list[str]]] = []
        self.text: list[str] = []
        self.header: list[str] = []
        self.row: list[str] = []
        self.cell: list[str] | None = None
        self.skip = False
        self.heading = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip = True
        if self.skip:
            return
        if tag == "table":
            self.header = []
        if tag == "tr":
            self.row, self.heading = [], False
        if tag in {"th", "td"}:
            self.cell = []
            self.heading = self.heading or tag == "th"

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)
            if self.cell is not None:
                self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = False
        if self.skip:
            return
        if tag in {"td", "th"} and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        if tag == "tr":
            if self.heading:
                self.header = list(self.row)
            elif self.row:
                self.rows.append((list(self.header), list(self.row)))


def extract_product_fields(html: str, candidate: Mapping[str, Any]) -> dict[str, str]:
    mpn = str(candidate.get("expected_mpn", "")).strip()
    if not mpn:
        raise ValueError("expected_mpn_required")
    parser = ProductTables()
    parser.feed(html)
    matches = [(head, row) for head, row in parser.rows if row and row[0] == mpn]
    if not matches:
        raise ValueError("exact_product_row_missing")
    observations: dict[str, set[str]] = {"mpn": {mpn}}
    for head, row in matches:
        for label, value in zip(head, row):
            key = HEADERS.get(" ".join(re.sub(r"[^a-z0-9 ]", " ", label.lower()).split()))
            if not key or not value:
                continue
            if key == "unit_cost":
                price = re.search(r"(?:USD|EUR|GBP|[$€£])\s*[0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2})?", value)
                if not price:
                    continue
                value = price.group(0)  # Preserve the stated currency; never infer USD from '$'.
            observations.setdefault(key, set()).add(value)
    if any(len(values) != 1 for values in observations.values()):
        raise ValueError("conflicting_product_rows")
    fields = {key: next(iter(values)) for key, values in observations.items()}
    manufacturer = str(candidate.get("expected_manufacturer", "")).strip()
    visible = " ".join(" ".join(parser.text).split())
    if manufacturer and re.search(r"\b" + re.escape(manufacturer) + r"\b", visible, re.I):
        fields["manufacturer"] = manufacturer
    return fields


def validate_source_url(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.fragment):
        raise ValueError("public_https_source_required")
    host = parsed.hostname
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if host.lower() == "localhost" or host.lower().endswith((".localhost", ".local")):
            raise ValueError("nonpublic_source_rejected")
    else:
        if not address.is_global:
            raise ValueError("nonpublic_source_rejected")
    return host


def fetch_public_html(url: str) -> bytes:
    return fetch_public_response(url, content_types=("text/html",))


def fetch_public_response(url: str, *, content_types: tuple[str, ...]) -> bytes:
    host = validate_source_url(url)
    addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError("nonpublic_source_rejected")
    # Pin the checked destination while keeping certificate/SNI validation for
    # the original hostname. Redirects require a separately configured source.
    address = sorted(addresses, key=lambda ip: (":" in ip, ip))[0]
    connection = http.client.HTTPSConnection(host, timeout=20)
    connection._create_connection = lambda ignored, timeout, source_address=None: socket.create_connection(
        (address, 443), timeout=timeout, source_address=source_address,
    )
    parsed = urlsplit(url)
    target = parsed.path or "/"
    if parsed.query:
        target += "?" + parsed.query
    try:
        connection.request("GET", target, headers={"User-Agent": "Novali-Evidence/1.0", "Accept": ", ".join(content_types)})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f"source_http_status_{response.status}")
        if not any(kind in response.getheader("Content-Type", "").lower() for kind in content_types):
            raise ValueError("html_source_required" if content_types == ("text/html",) else "source_content_type_rejected")
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("source_size_limit")
        return body
    finally:
        connection.close()


def _key(candidate: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps({key: candidate.get(key, "") for key in IDENTITY_FIELDS}, sort_keys=True).encode()).hexdigest()


def cache_source(root: Path, candidate: Mapping[str, Any], body: bytes, *, final_url: str) -> dict[str, Any]:
    if len(body) > MAX_BYTES or any(not candidate.get(key) for key in IDENTITY_FIELDS):
        raise ValueError("invalid_source_binding_or_size")
    validate_source_url(final_url)
    if final_url != candidate["source_url"]:
        raise ValueError("source_url_mismatch")
    fields = extract_product_fields(body.decode("utf-8", errors="replace"), candidate)
    directory = root / "conveyor/source_evidence_cache"
    directory.mkdir(parents=True, exist_ok=True)
    key = _key(candidate)
    receipt = {**{field: candidate[field] for field in IDENTITY_FIELDS},
               "expected_mpn": candidate["expected_mpn"], "expected_manufacturer": candidate.get("expected_manufacturer", ""),
               "source_content_sha256": hashlib.sha256(body).hexdigest(),
               "retrieved_at": datetime.now(timezone.utc).isoformat(), "fields": fields,
               "grants_execution_authority": False}
    (directory / f"{receipt['source_content_sha256']}.html").write_bytes(body)
    (directory / f"{key}.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def read_cached_evidence(root: Path, candidates: list[Mapping[str, Any]]) -> dict[str, Any]:
    directory = root / "conveyor/source_evidence_cache"
    rows, rejected = [], []
    for candidate in candidates[:40]:
        key = _key(candidate)
        path = directory / f"{key}.json"
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > 32768:
                raise ValueError("source_receipt_size_limit")
            receipt = json.loads(path.read_text(encoding="utf-8"))
            if any(receipt.get(k) != candidate.get(k) for k in IDENTITY_FIELDS):
                raise ValueError("source_binding_mismatch")
            if receipt.get("grants_execution_authority") is not False:
                raise ValueError("source_authority_rejected")
            if any(candidate.get(k) and candidate[k] != receipt.get(k) for k in ("expected_mpn", "expected_manufacturer")):
                raise ValueError("source_product_binding_mismatch")
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(receipt["retrieved_at"])).total_seconds()
            if age < -60 or age > 86400:
                raise ValueError("source_refresh_required")
            content_hash = str(receipt.get("source_content_sha256", ""))
            if not re.fullmatch(r"[0-9a-f]{64}", content_hash):
                raise ValueError("invalid_source_content_hash")
            body_path = directory / f"{content_hash}.html"
            if not body_path.is_file():
                body_path = directory / f"{key}.html"  # Original cache layout; still hash-verified.
            if body_path.stat().st_size > MAX_BYTES:
                raise ValueError("source_size_limit")
            body = body_path.read_bytes()
            if hashlib.sha256(body).hexdigest() != receipt.get("source_content_sha256"):
                raise ValueError("source_content_hash_mismatch")
            fields = extract_product_fields(body.decode("utf-8", errors="replace"), receipt)
            rows.append({**fields, **{k: receipt[k] for k in IDENTITY_FIELDS},
                         "row_id": "source-" + key[:16], "covered_fields": list(fields),
                         "spec_values": [f"{field}={value}" for field, value in fields.items()],
                         "claim": "Product table observations; project design and suitability remain to be validated.",
                         "source_content_sha256": receipt["source_content_sha256"],
                         "retrieved_at": receipt["retrieved_at"], "evidence_ref": "source-cache:" + key,
                         "grants_execution_authority": False})
        except (ValueError, OSError, KeyError, TypeError) as exc:
            rejected.append({"source_candidate_id": candidate.get("source_candidate_id", ""), "reason": str(exc)})
    return {"rows": rows, "rejected": rejected, "grants_execution_authority": False}


def reuse_cached_source(root: Path, source: Mapping[str, Any], target: Mapping[str, Any]) -> dict[str, Any]:
    """Bind fresh, verified facts about the same product to another requested row."""
    checked = read_cached_evidence(root, [source])
    if not checked["rows"]:
        raise ValueError("reusable_source_unavailable")
    original = checked["rows"][0]
    if target.get("source_url") != source.get("source_url") or target.get("expected_mpn") != original["mpn"]:
        raise ValueError("reuse_product_binding_mismatch")
    directory = root / "conveyor/source_evidence_cache"
    content_hash = original["source_content_sha256"]
    body_path = directory / f"{content_hash}.html"
    if not body_path.is_file():
        body_path = directory / f"{_key(source)}.html"
    receipt = cache_source(root, target, body_path.read_bytes(), final_url=target["source_url"])
    receipt["reused_at"] = receipt["retrieved_at"]
    receipt["retrieved_at"] = original["retrieved_at"]
    receipt["reused_from_source_candidate_id"] = source["source_candidate_id"]
    (directory / f"{_key(target)}.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def reuse_available_sources(root: Path, candidates: list[Mapping[str, Any]]) -> None:
    directory = root / "conveyor/source_evidence_cache"
    paths = sorted(directory.glob("*.json"))
    if len(paths) > 40:
        return
    for candidate in candidates[:40]:
        if not candidate.get("expected_mpn") or (directory / f"{_key(candidate)}.json").is_file():
            continue
        for path in paths:
            try:
                if path.stat().st_size > 32768:
                    continue
                source = json.loads(path.read_text(encoding="utf-8"))
                if source.get("source_url") == candidate.get("source_url") and source.get("expected_mpn") == candidate["expected_mpn"]:
                    reuse_cached_source(root, source, candidate)
                    break
            except (ValueError, OSError, KeyError, TypeError):
                continue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-root", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    adapter_root = (args.operator_root / "conveyor/trusted_knowledge_source_adapters").resolve()
    path = args.adapter.resolve()
    if not path.is_relative_to(adapter_root):
        parser.error("adapter must belong to this operator's configured source adapters")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("enabled") is False:
        parser.error("adapter is disabled")
    matches = [row for row in config.get("source_candidates", []) if row.get("source_candidate_id") == args.candidate_id]
    if len(matches) != 1:
        parser.error("one exact configured candidate is required")
    if args.fetch:
        candidate = matches[0]
        cache_source(args.operator_root, candidate, fetch_public_html(candidate["source_url"]), final_url=candidate["source_url"])
    result = read_cached_evidence(args.operator_root, matches)
    print(json.dumps(result, indent=2))
    return 0 if result["rows"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

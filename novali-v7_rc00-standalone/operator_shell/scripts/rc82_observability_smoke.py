from __future__ import annotations

import json
import os
import socket
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from operator_shell.observability import (
    get_observability_status,
    initialize_observability,
    record_counter,
    record_event,
    shutdown_observability,
    trace_span,
)

FAKE_SECRETS = {
    "authorization": "Bearer FAKE_SECRET_TOKEN_RC82_SHOULD_NOT_EXPORT",
    "novali.secret": "FAKE_NOVALI_SECRET_RC82_SHOULD_NOT_EXPORT",
    "api_key": "FAKE_API_KEY_RC82_SHOULD_NOT_EXPORT",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> None:
    proof_root = Path("artifacts/operator_proof/rc82")
    captured_requests: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or 0)
            body = self.rfile.read(length)
            captured_requests.append(
                {
                    "path": self.path,
                    "headers": {key: value for key, value in self.headers.items()},
                    "body_utf8": body.decode("utf-8", errors="ignore"),
                    "body_latin1": body.decode("latin-1", errors="ignore"),
                }
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")

    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    previous_env = {
        "NOVALI_OTEL_ENABLED": os.environ.get("NOVALI_OTEL_ENABLED"),
        "OTEL_EXPORTER_OTLP_ENDPOINT": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
        "OTEL_SERVICE_NAME": os.environ.get("OTEL_SERVICE_NAME"),
        "NOVALI_OTEL_REDACTION_MODE": os.environ.get("NOVALI_OTEL_REDACTION_MODE"),
    }
    os.environ["NOVALI_OTEL_ENABLED"] = "true"
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://127.0.0.1:{port}"
    os.environ["OTEL_SERVICE_NAME"] = "novali-operator-shell"
    os.environ["NOVALI_OTEL_REDACTION_MODE"] = "strict"

    try:
        initialize_observability()
        with trace_span("novali.runtime.startup", FAKE_SECRETS | {"novali.result": "success"}):
            record_event("rc82_smoke_span_event", FAKE_SECRETS)
            record_counter("novali.runtime.start.count", 1, {"novali.result": "success"})
            record_event("novali.policy_conflict", FAKE_SECRETS | {"detail": "rc82 smoke"})
    finally:
        shutdown_observability()
        status_payload = get_observability_status()
        server.shutdown()
        server.server_close()
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    flattened = [json.dumps(status_payload, sort_keys=True)]
    for request in captured_requests:
        flattened.append(json.dumps(request.get("headers", {}), sort_keys=True))
        flattened.append(request.get("body_utf8", ""))
        flattened.append(request.get("body_latin1", ""))
    flat_text = "\n".join(flattened)
    leaked = [secret for secret in FAKE_SECRETS.values() if secret in flat_text]
    if leaked:
        raise SystemExit(f"Secret leakage detected in rc82 smoke proof: {leaked}")
    paths = sorted({request["path"] for request in captured_requests})
    summary = {
        "generated_at": _now(),
        "otel_endpoint": f"http://127.0.0.1:{port}",
        "request_count": len(captured_requests),
        "captured_paths": paths,
        "status": status_payload,
        "fake_secrets_redacted": True,
        "secret_leakage_detected": False,
    }
    _write_json(proof_root / "observability_smoke_summary.json", summary)
    _write_markdown(
        proof_root / "observability_smoke_summary.md",
        [
            "# rc82 observability smoke summary",
            "",
            f"- generated_at: `{summary['generated_at']}`",
            f"- request_count: `{summary['request_count']}`",
            f"- captured_paths: `{', '.join(paths) if paths else 'none'}`",
            f"- observability_status: `{status_payload.get('status', 'unknown')}`",
            "- fake_secret_leakage: `false`",
        ],
    )


if __name__ == "__main__":
    main()

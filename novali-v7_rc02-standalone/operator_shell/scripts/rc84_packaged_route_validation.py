from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.external_adapter import resolve_rc84_artifact_root
from operator_shell.observability.rc83 import write_summary_artifacts


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _markdown_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# rc84 Packaged Route Validation",
        "",
        f"- Result: {summary.get('result', '<unknown>')}",
        f"- Package root: {summary.get('package_root', '<none>')}",
    ]
    for entry in summary.get("routes", []):
        lines.append(
            f"- {entry.get('path', '<path>')} -> {entry.get('status', '<status>')} {entry.get('location', '')}".rstrip()
        )
    return "\n".join(lines)


def run_packaged_route_validation(
    *,
    package_root: Path,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    env = dict(env or os.environ)
    sys.path.insert(0, str(package_root))
    try:
        from operator_shell.web_operator import build_operator_web_app, make_operator_web_server
    finally:
        sys.path.pop(0)

    operator_root = package_root / "operator_state"
    state_root = package_root / "runtime_data" / "state"
    service = build_operator_web_app(
        package_root=package_root,
        operator_root=operator_root,
        state_root=state_root,
    )
    server = make_operator_web_server(service=service, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        routes: list[dict[str, Any]] = []
        for path in (
            "/healthz",
            "/",
            "/shell",
            "/workspace",
            "/shell/workspace",
            "/shell/api/operator-state",
            "/shell/api/intervention-state",
            "/shell/api/long-run-state",
        ):
            connection = http.client.HTTPConnection(host, port, timeout=10)
            connection.request("GET", path)
            response = connection.getresponse()
            response.read()
            routes.append(
                {
                    "path": path,
                    "status": int(response.status),
                    "location": response.getheader("Location") or "",
                }
            )
            connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    expected = {
        "/healthz": (200, ""),
        "/": (307, "/shell"),
        "/shell": (200, ""),
        "/workspace": (307, "/shell/workspace"),
        "/shell/workspace": (200, ""),
        "/shell/api/operator-state": (200, ""),
        "/shell/api/intervention-state": (200, ""),
        "/shell/api/long-run-state": (200, ""),
    }
    ok = True
    for route in routes:
        expected_status, expected_location = expected[route["path"]]
        ok = ok and route["status"] == expected_status
        if expected_location:
            ok = ok and str(route["location"]).startswith(expected_location)
    summary = {
        "schema_name": "novali_rc84_packaged_route_validation_summary_v1",
        "generated_at": _now_iso(),
        "result": "success" if ok else "failure",
        "package_root": str(package_root),
        "routes": routes,
    }
    artifact_root = resolve_rc84_artifact_root(ROOT, env=env)
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name="packaged_route_validation.json",
        markdown_name="packaged_route_validation.md",
        summary=summary,
        markdown=_markdown_summary(summary),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--package-root",
        default=str(ROOT / "dist" / "novali-v6_rc84-standalone"),
    )
    args = parser.parse_args()
    summary = run_packaged_route_validation(package_root=Path(args.package_root).resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() == "success" else 1


if __name__ == "__main__":
    sys.exit(main())

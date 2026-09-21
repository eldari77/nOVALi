from __future__ import annotations

import argparse
import http.client
import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.observability.rc83 import write_summary_artifacts

ARTIFACT_ROOT = ROOT / "artifacts" / "operator_proof" / "v7rc00"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _markdown_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# v7rc00 Packaged Route Validation",
        "",
        f"- Result: {summary.get('result', '<unknown>')}",
        f"- Package root: {summary.get('package_root', '<none>')}",
        f"- Version identity result: {summary.get('version_identity_result', '<unknown>')}",
        f"- Operator-state result: {summary.get('operator_state_result', '<unknown>')}",
    ]
    for entry in summary.get("routes", []):
        lines.append(
            f"- {entry.get('path', '<path>')} -> {entry.get('status', '<status>')} {entry.get('location', '')}".rstrip()
        )
    return "\n".join(lines)


def run_packaged_route_validation(*, package_root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(package_root))
    try:
        from operator_shell.web_operator import build_operator_web_app, make_operator_web_server
    finally:
        sys.path.pop(0)

    service = build_operator_web_app(
        package_root=package_root,
        operator_root=package_root / "operator_state",
        state_root=package_root / "runtime_data" / "state",
    )
    server = make_operator_web_server(service=service, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    route_bodies: dict[str, Any] = {}
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
            payload = response.read()
            routes.append(
                {
                    "path": path,
                    "status": int(response.status),
                    "location": response.getheader("Location") or "",
                }
            )
            if "application/json" in str(response.getheader("Content-Type") or ""):
                route_bodies[path] = json.loads(payload.decode("utf-8"))
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
    routes_ok = True
    for route in routes:
        expected_status, expected_location = expected[route["path"]]
        routes_ok = routes_ok and route["status"] == expected_status
        if expected_location:
            routes_ok = routes_ok and str(route["location"]).startswith(expected_location)

    operator_state = dict(route_bodies.get("/shell/api/operator-state", {}))
    version_identity = dict(operator_state.get("version_identity", {}))
    observability = dict(operator_state.get("observability", {}))
    observability_shutdown = dict(observability.get("observability_shutdown", {}))
    operator_alerts = dict(operator_state.get("operator_alerts", {}))
    read_only_adapter = dict(operator_state.get("read_only_adapter", {}))
    controller_isolation = dict(operator_state.get("controller_isolation", {}))
    lanes = [lane for lane in controller_isolation.get("lanes", []) if isinstance(lane, dict)]
    observability_service_version = observability.get("resource_summary", {}).get("service.version")
    observability_service_version_ok = observability_service_version in {None, "novali-v7_rc00"}

    version_identity_result = all(
        (
            version_identity.get("active_line") == "novali-v7",
            version_identity.get("active_milestone") == "v7rc00",
            version_identity.get("service_version") == "novali-v7_rc00",
            version_identity.get("package_name") == "novali-v7_rc00-standalone",
        )
    )
    operator_state_result = all(
        (
            observability_service_version_ok,
            observability_shutdown.get("last_shutdown_result") in {
                "unknown",
                "success",
                "disabled",
                "unavailable",
                "timeout",
                "degraded",
                "failed",
            },
            "OTEL_EXPORTER_OTLP_HEADERS" not in json.dumps(observability, sort_keys=True),
            operator_alerts.get("mode") == "local_evidence_only",
            read_only_adapter.get("mutation_allowed") is False,
            all(not bool(lane.get("active", True)) and str(lane.get("mode", "")).strip() == "mock_only" for lane in lanes),
        )
    )

    summary = {
        "schema_name": "novali_v7rc00_packaged_route_validation_summary",
        "schema_version": "v7rc00.v1",
        "generated_at": _now_iso(),
        "result": "success" if routes_ok and version_identity_result and operator_state_result else "failure",
        "package_root": str(package_root),
        "routes": routes,
        "version_identity_result": "success" if version_identity_result else "failure",
        "operator_state_result": "success" if operator_state_result else "failure",
        "operator_state_checks": {
            "active_line": version_identity.get("active_line"),
            "active_milestone": version_identity.get("active_milestone"),
            "service_version": version_identity.get("service_version"),
            "package_name": version_identity.get("package_name"),
            "observability_service_version": observability_service_version,
            "observability_service_version_ok": observability_service_version_ok,
            "observability_shutdown_result": observability_shutdown.get("last_shutdown_result"),
            "operator_alerts_mode": operator_alerts.get("mode"),
            "read_only_mutation_allowed": read_only_adapter.get("mutation_allowed"),
            "controller_isolation_lane_count": len(lanes),
            "controller_isolation_all_mock_only": all(
                not bool(lane.get("active", True)) and str(lane.get("mode", "")).strip() == "mock_only"
                for lane in lanes
            ),
        },
    }
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
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
        default=str(ROOT / "dist" / "novali-v7_rc00-standalone"),
    )
    args = parser.parse_args()
    summary = run_packaged_route_validation(package_root=Path(args.package_root).resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() == "success" else 1


if __name__ == "__main__":
    sys.exit(main())

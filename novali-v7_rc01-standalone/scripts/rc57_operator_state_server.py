import argparse
import json
import signal
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from operator_shell.web_operator import DEFAULT_WEB_HOST, build_operator_web_app, make_operator_web_server


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--operator-root", required=True)
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--artifacts-dir", required=True)
    args = parser.parse_args()

    package_root = Path(args.package_root).resolve()
    operator_root = Path(args.operator_root).resolve()
    state_root = Path(args.state_root).resolve()
    artifacts_dir = Path(args.artifacts_dir).resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    service = build_operator_web_app(
        package_root=package_root,
        operator_root=operator_root,
        state_root=state_root,
    )
    server = make_operator_web_server(service=service, host=DEFAULT_WEB_HOST, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address
    payload = {
        "package_root": str(package_root),
        "operator_root": str(operator_root),
        "state_root": str(state_root),
        "base_url": f"http://{host}:{port}",
    }
    (artifacts_dir / "server_manifest.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    print("RC57_SERVER_READY " + json.dumps(payload), flush=True)

    stop_requested = False

    def _request_stop(_signum: int, _frame: object) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    try:
        while not stop_requested:
            time.sleep(0.2)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

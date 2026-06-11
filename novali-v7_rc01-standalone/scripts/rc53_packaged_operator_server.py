import argparse
import json
import shutil
import signal
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from operator_shell.web_operator import DEFAULT_WEB_HOST, build_operator_web_app, make_operator_web_server
from tests.test_operator_web import _materialize_packaged_review_action_service


ROOT = Path(__file__).resolve().parents[1]
CONFIRMED_TEMPLATE_SOURCE = (
    ROOT
    / "manual_acceptance_samples"
    / "successor_package_readiness_review_decision_template.json"
)


def _copy_current_benchmark_truth(*, target_operator_root: Path, target_package_root: Path) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []
    for source in (ROOT / "operator_state").glob("controller_real_work_benchmark*_latest.json"):
        target = target_operator_root / source.name
        shutil.copy2(source, target)
        copied.append(
            {
                "source": str(source),
                "target": str(target),
            }
        )

    target_template = target_package_root / "manual_acceptance_samples" / CONFIRMED_TEMPLATE_SOURCE.name
    target_template.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONFIRMED_TEMPLATE_SOURCE, target_template)
    copied.append(
        {
            "source": str(CONFIRMED_TEMPLATE_SOURCE),
            "target": str(target_template),
        }
    )
    return copied


def _prepare_fresh(package_root: Path) -> tuple[Path, Path, Path, dict[str, object]]:
    temp_root = Path(tempfile.mkdtemp(prefix="rc53_operator_proof_fresh_"))
    operator_root = temp_root / "operator_state"
    state_root = temp_root / "runtime_data" / "state"
    operator_root.mkdir(parents=True, exist_ok=True)
    state_root.mkdir(parents=True, exist_ok=True)
    info: dict[str, object] = {
        "scenario": "fresh",
        "operator_root": str(operator_root),
        "state_root": str(state_root),
        "sample_directive_path": str(
            package_root / "samples" / "directives" / "standalone_valid_directive.example.json"
        ),
        "seed_sources": [],
    }
    return package_root, operator_root, state_root, info


def _prepare_seeded(package_root: Path) -> tuple[Path, Path, Path, dict[str, object]]:
    temp_root = Path(tempfile.mkdtemp(prefix="rc53_operator_proof_seeded_"))
    proof_package_root = temp_root / package_root.name
    shutil.copytree(package_root, proof_package_root)
    _service, fixture = _materialize_packaged_review_action_service(proof_package_root)
    operator_root = Path(str(fixture["operator_root"]))
    state_root = Path(str(fixture["state_root"]))
    copied_sources = _copy_current_benchmark_truth(
        target_operator_root=operator_root,
        target_package_root=proof_package_root,
    )
    info = {
        "scenario": "seeded",
        "canonical_package_root": str(package_root),
        "proof_package_root": str(proof_package_root),
        "operator_root": str(operator_root),
        "state_root": str(state_root),
        "directive_path": str(fixture.get("directive_path", "")),
        "workspace_root": str(fixture.get("workspace_root", "")),
        "runtime_event_log_path": str(fixture.get("runtime_event_log_path", "")),
        "seed_sources": copied_sources,
    }
    return proof_package_root, operator_root, state_root, info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--scenario", choices=("fresh", "seeded"), required=True)
    parser.add_argument("--artifacts-dir", required=True)
    args = parser.parse_args()

    package_root = Path(args.package_root).resolve()
    artifacts_dir = Path(args.artifacts_dir).resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    if args.scenario == "fresh":
        served_package_root, operator_root, state_root, info = _prepare_fresh(package_root)
    else:
        served_package_root, operator_root, state_root, info = _prepare_seeded(package_root)

    service = build_operator_web_app(
        package_root=served_package_root,
        operator_root=operator_root,
        state_root=state_root,
    )
    server = make_operator_web_server(service=service, host=DEFAULT_WEB_HOST, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address
    ready_payload = {
        "scenario": args.scenario,
        "package_root": str(served_package_root),
        "base_url": f"http://{host}:{port}",
        **info,
    }

    (artifacts_dir / "server_manifest.json").write_text(
        json.dumps(ready_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    print("RC53_SERVER_READY " + json.dumps(ready_payload), flush=True)

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

"""One registered evaluation per clean subprocess; no model-authored code execution."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# The path is fixed by the installed worker, never supplied by the candidate.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from operator_shell.theory_evaluators import evaluate_registered, evaluator_fingerprint


def main() -> int:
    try:
        payload=json.loads(sys.stdin.buffer.read(100001))
        evaluator=payload["model_spec"]["evaluator_id"]
        if payload["evaluator_sha256"]!=evaluator_fingerprint(evaluator):
            raise ValueError("evaluator_revision_changed")
        if sys.platform!="win32":
            import resource
            resource.setrlimit(resource.RLIMIT_CPU,(40,40))
            resource.setrlimit(resource.RLIMIT_FSIZE,(1_000_000,1_000_000))
        result=evaluate_registered(payload["model_spec"],payload["seed"])
        encoded=json.dumps(result,allow_nan=False)
        if len(encoded)>200000: raise ValueError("evaluation_result_size_limit")
        print(encoded)
        return 0
    except Exception as exc:
        print(json.dumps({"error_class":type(exc).__name__,"error":str(exc)[:300]}))
        return 1


if __name__=="__main__": raise SystemExit(main())

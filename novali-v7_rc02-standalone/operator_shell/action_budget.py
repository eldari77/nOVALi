"""One monotonic deadline, with time reserved for local validation and storage."""
from __future__ import annotations

import math
import time
from collections.abc import Callable


class ActionBudget:
    def __init__(self, seconds: float, *, reserve_seconds: float = 2.0,
                 clock: Callable[[], float] | None = None) -> None:
        if not math.isfinite(seconds) or seconds <= 0 or not 0 <= reserve_seconds < seconds:
            raise ValueError('invalid_action_deadline')
        self.clock = clock or time.monotonic
        self.started = self.clock()
        self.deadline = self.started + seconds
        self.reserve_seconds = reserve_seconds

    def remaining(self) -> float:
        return max(0.0, self.deadline - self.clock())

    def provider_seconds(self) -> float:
        seconds = self.remaining() - self.reserve_seconds
        if seconds < 1:
            raise ValueError('action_deadline_insufficient_provider_time')
        return seconds

    def require(self, stage: str) -> None:
        if self.remaining() <= 0:
            raise ValueError('action_deadline_exceeded_before_' + stage)

    def run_evaluator(self, contract, seed: int):
        """Bound worker transport without changing the scientific evaluator files.

        Payload, environment and result checks match TheoryWorkspace._run_evaluator;
        the contract test verifies this seam. Only the timeout is more restrictive.
        """
        import json
        import os
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        from .theory_evaluators import REGISTRY
        self.require('evaluator')
        timeout=min(REGISTRY[contract['evaluator_id']]['wall_seconds'],self.remaining()-1.0)
        if timeout<=0:raise ValueError('action_deadline_insufficient_evaluator_time')
        env={'PATH':os.defpath,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1',
             'OPENBLAS_NUM_THREADS':'1'}
        for key in ('SYSTEMROOT','WINDIR','TEMP','TMP'):
            if key in os.environ:env[key]=os.environ[key]
        payload={'model_spec':contract['model_spec'],'seed':seed,'evaluator_sha256':contract['evaluator_sha256']}
        with tempfile.TemporaryDirectory(prefix='novali-theory-eval-') as working:
            result=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('theory_worker.py'))],
                input=json.dumps(payload),text=True,capture_output=True,cwd=working,env=env,timeout=timeout)
        if len(result.stdout)>200000:raise ValueError('evaluator_output_size_limit')
        parsed=json.loads(result.stdout)
        if result.returncode or parsed.get('error_class'):
            raise ValueError('registered_evaluator_failed: '+str(parsed.get('error','worker failed'))[:300])
        return parsed

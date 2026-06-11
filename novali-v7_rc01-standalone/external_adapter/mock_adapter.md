# rc85 Mock Adapter

`MockExternalWorldAdapter` remains the only adapter implementation in rc85.

Supported mock action types:

- `noop.observe`
- `noop.annotate`
- `noop.simulate_success`
- `noop.simulate_failure`
- `noop.simulate_uncertain`
- `noop.trigger_review`
- `noop.kill_switch_test`

Behavior:

- captures a mock world snapshot
- proposes bounded mock actions
- validates preconditions
- refuses live-mutation-style action requests in rc85
- executes mock success/failure/uncertain outcomes without touching a real external world
- emits replay packets for success, failure, uncertain, review-required, and kill-switch paths
- creates rc85 review items for unknown, forbidden, unsafe, uncertain, evidence-missing, and rollback-ambiguous cases
- creates rollback-analysis artifacts linked to replay packets and checkpoint refs without restoring any real state
- triggers a mock-only kill switch that does not stop NOVALI, Docker, or the collector

Deferred to rc86+:

- real adapters
- live mutation
- automatic rollback restore
- approval paths for any non-noop external action

# novali-v7

`novali-v7` is the active Novali development and operator root.

This root may preserve historical evidence that mentions older Novali lines, but current runtime policy, local LLM directive promotion, and operator launch preparation should use `novali-v7` as the active package, source, and trusted-local reference surface. Older Novali versions are historical references only and should not be treated as runtime or trusted-source dependencies for new v7 work.

## What This Root Is

- the active working directory for current `novali-v7` mission work
- the local Web Shell and Docker Compose LLM stack root
- the place where new bounded implementation, operator evidence, and v7 directive work should start

## What This Root Is Not

- not a reason to reopen older Novali roots by default
- not authorization for governance expansion, baseline replacement, or runtime broadening
- not a bypass around directive-first bootstrap, review gates, or governed execution controls

## Current Operator Direction

The local operator surface includes:

- a local Ollama-backed Ask Novali interface
- a review-gated Ask Novali promotion path that turns completed `draft_directive` chat evidence into pending directive candidates without selecting, approving, or launching them
- a Docker Compose Novali + Ollama stack
- an autonomy kernel for self-authored goals, local approved-source research, automated board review, Novali-stack operation proposals, emergency-stop behavior, and a bounded governed-start bridge that still uses the existing launch preflight

See `AUTONOMY_KERNEL.md` and `STANDALONE_DOCKER_QUICKSTART.md` for the current operator-facing details.

## Active Safety Boundary

LLM output is explain-and-draft evidence only. A promoted LLM draft becomes a pending directive candidate under `directive_inputs/pending_llm/`, with matching redacted evidence under `operator_state/llm_pending_directives/`. It is not active until the operator selects it through the existing directive controls, and it cannot launch bootstrap or governed execution by itself.

Current v7 local directive candidates should use:

- `local_repo:novali-v7`
- `local_artifacts:novali-v7/data`
- `local_logs:logs`
- `trusted_benchmark_pack_v1`

Older-version source ids should remain out of new v7 directive candidates unless a future operator-approved migration explicitly reintroduces them for a bounded historical audit.

## Runtime Policy

For the Docker LLM stack, authoritative runtime paths should be container-local, rooted at `/workspace/novali`. Stale host paths or older-version roots should be refreshed before launch readiness is trusted.

Governed launch readiness rechecks enabled trusted-source bindings against the live container environment. A session-only credential entered through the Web Shell is intentionally not persisted as a raw secret, so restarting the `novali` container requires either re-validating the provider in the UI or supplying `OPENAI_API_KEY` to the container environment before launch.

Governed start requests are bounded before process spawn. `/shell/api/governed/start` now records redacted attempt evidence under `operator_state/governed_start_attempt_latest.json` and `operator_state/governed_start_attempts/`, returns `409` for concurrent starts, `400` for explicit readiness/refusal blockers, `504` for pre-spawn timeout, and navigates to the workspace only after a spawn is confirmed.

The autonomy kernel may now propose `governed_start_next_invocation` when lightweight governed readiness is launchable and a directive is selected. That proposal still requires an approval-board record and execution through the Web Shell operations broker; it calls the same `/shell/api/governed/start` path and records the governed-start attempt instead of creating a separate autonomous launch path.

Autonomy evidence remains redacted before it is persisted or returned through the shell. Audit identifiers such as `operation_id`, `decision_id`, `cycle_id`, and `attempt_id` are intentionally preserved because the Web Shell needs them to execute the exact approved proposal; API keys, bearer strings, passwords, credential-shaped values, and fake-secret fixtures remain redacted.

For unattended soak runs, use `overnight_stability_policy` in `operator_state/autonomy/charter.json` and keep each governed invocation bounded. Set governed `max_total_cycles` to `0` only when you intentionally want an uncapped rolling directive run; per-invocation cycle, wall-clock, readiness, emergency-stop, and failure-limit gates still apply. When enabled, the autonomy loop may auto-execute only explicitly listed low-touch actions such as the latest board-approved `governed_start_next_invocation` and, when `approve_bounded_continuation_review` is listed, the narrow bounded-continuation review packet created by an invocation checkpoint. It stops instead of retrying indefinitely when the emergency stop is set, launch readiness is blocked, a finite long-run cycle budget is exhausted, the wall-clock stop is reached, or the configured failure limit is hit.

Governed invocation size can now be adaptive. New long-run / low-touch runtime policies carry `governed_execution.invocation_window` with `mode=adaptive`, a default effective window of 8 cycles, a minimum of 2, and a maximum of 24. Before each governed launch, the Web Shell writes `GovernedInvocationWindowEvaluation` evidence under `operator_state/governed_invocation_window_latest.json` and `operator_state/governed_invocation_windows/`, then freezes the selected `effective_max_cycles_per_invocation` into the child runtime session. Stable recent governed continuations with meaningful or strict-useful progress grow the window by 2; memory warning/action, trusted-source launch failures, non-bounded reviews, stale recovery, repeated launch failures, or operation timeouts shrink it toward 2. Critical memory or emergency stop refuses governed launch instead of selecting a larger cap.

Governed long-run budget exhaustion is a launch boundary, not a blanket growth boundary. If `promote_self_modification_candidate` is also enabled for overnight auto-execution, a blocked `governed_start_next_invocation` records `growth_pivot_requested`, keeps autonomy active, and lets the next cycle pursue a safe Novali-owned capability gap through novelty, board, broker, canary, rollback, and emergency-stop gates. If promotion auto-execution is not enabled, the loop still pauses at `stopped_at_budget_boundary`.

Autonomous growth is now tracked separately from artifact churn. Each autonomy cycle writes a `MeaningfulWorkEvaluation` with equal directive-progress and capability-growth scoring, and the Web Shell exposes it in the Autonomous Growth panel. Self-modification can move past a draft only through a promotion packet with a changed-file manifest, tests, rollback evidence, canary commands, and unanimous board approval; low-risk Novali-own-stack promotions can then auto-adopt through the operations broker while emergency stop, rollback, redaction, and audit records stay mandatory.

Strict-useful planner/runtime impact now contributes to meaningful-work credit when it keeps governed directive execution moving. If a later cycle explicitly consumes a promoted capability, changes the planner decision into `governed_start_next_invocation`, prevents a repeat failure, or avoids a budget overrun, the resulting `MeaningfulWorkEvaluation` records `planner_runtime_impact` and `strict_usefulness_credited` instead of treating the repeated signature as artifact churn. Passive references and promotion-only evidence still remain low-credit `evidence_only` work.

When a prior cycle records the weak area `missing promotion packet`, the autonomy kernel can now generate a real broker-ready packet for a conservative Novali-owned capability record. V1 adopts that generated capability under `operator_state/autonomy/adopted_capabilities/`, not protected source roots, so overnight growth can prove manifest/test/rollback/canary promotion behavior before broader source-code promotion is enabled.

Autonomous promotion now has a novelty policy in `operator_state/autonomy/charter.json`. By default, Novali remembers the last 12 promoted capability kinds and keeps a successfully promoted kind on a 6-cycle cooldown, so repeated `promotion_packet_generation` packets are replaced by the next configured capability gap unless the repeat is an explicit remediation for failed canary, failed rollback, missing evidence repair, or directive need. Each such choice writes a `CapabilityNoveltyEvaluation` and the Autonomous Growth panel shows the selected gap, recent promoted kinds, novelty status, and cooldown reason.

When all configured novelty gaps are promoted and the growth pivot is still active, Novali now proposes `post_ladder_synthesis` instead of falling back to repeated stack-status checks. This is a read-only/state-only broker action that writes a redacted `PostLadderSynthesis` record under `operator_state/autonomy/`, classifies promoted capabilities by usefulness, and records a bounded next capability-gap proposal without mutating the charter or launching governed execution. If local evidence is too weak to choose a fresh non-repeated gap, synthesis may ask the configured external trusted source `openai_api` for one bounded JSON proposal through the existing `OPENAI_API_KEY` readiness path; local Ollama is not used for this autonomy-growth decision.

Adaptive role specialization is evidence-guided, not an authority expansion or consciousness claim. Each autonomy cycle can refresh a `RoleSpecializationProfile` and `CapabilityUsefulnessEvaluation` from the active directive, recent ledgers, promoted capabilities, blockers, and trusted-source synthesis evidence. When growth evidence flattens or a capability is not proving useful, the safe `adaptive_learning_synthesis` operation writes state-only `SelfCurriculumChallenge` and `MetacognitiveReplay` records. Learning-derived gaps become promotable after repeated later-usefulness evidence meets the configured threshold, after the same safe gap appears in five completed adaptive-learning syntheses with no strict usefulness and no promotion progress, or after five recent syntheses in the same semantic gap family point to one canonical safe representative. In all cases the gap still passes through the normal novelty, board, broker, canary, rollback, and emergency-stop gates under `operator_state/autonomy/adopted_capabilities/`.

Capability usefulness is strict by default. Promotion, canary, or matching later evidence alone is classified as `evidence_only` or `dormant`; a capability counts as `useful` only after a later cycle explicitly consumes it, changes a planner/runtime decision, prevents a repeat failure, improves directive progress, reduces operator intervention, or references it through a runtime/planner hook. The Autonomous Growth panel surfaces the strict gate result, signal count, and gate reason so long runs can distinguish substantive capability use from safe but shallow artifact production.

Promoted Novali-owned state capabilities can now become deterministic planner hooks after adoption under `operator_state/autonomy/adopted_capabilities/`. V1 hook behavior is active but bounded: recognized hooks may bias the next plan among already-supported safe actions, record `CapabilityHookConsumption` evidence, and attach consumed capability and planner-hook fields to plan/proposal/result records. Hooks cannot bypass governed readiness, trusted-source checks, emergency stop, board approval, broker execution, canary, rollback, memory-pressure handling, or novelty repeat blocking. Unknown adopted capability records remain visible evidence only until a deterministic hook adapter exists.

Strict usefulness now requires explicit consumption evidence. Recognized promoted hooks receive a `CapabilityConsumptionContract` and `RuntimeCapabilityAdapter` record before use, and every real planner/runtime invocation writes a `CapabilityConsumptionEvent` with the consumed capability, baseline/final action, decision delta, adapter behavior, and preserved safety gates. Passive post-promotion references remain `evidence_only`; repeated weak usefulness records write a `CapabilityRetirementEvaluation` so Novali pivots to follow-up synthesis or adapter repair instead of repeating adaptive-learning evidence.

Adaptive-learning hook stalls are bounded. If `goal_drift_guardrails` or `dependency_fingerprint_cache` repeatedly redirect the planner into `adaptive_learning_synthesis` while recent usefulness remains `evidence_only`, Novali records `AdaptiveLearningHookStallEvaluation` evidence and pivots to governed stale recovery when available, a broker-gated runtime-hook adapter capability when safe, or read-only post-ladder synthesis as the fallback.

Execution budget guardrails are now a deterministic planner/runtime hook instead of a passive promoted record. `execution_budget_guardrails_v1` evaluates repeated action loops, adaptive-learning hook stalls, trusted-source attempt counts, operation runtime budgets, and memory pressure before nonessential growth work. When it changes a planner decision or prevents a budget overrun, Novali writes `ExecutionBudgetGuardrailEvaluation` plus explicit capability-consumption evidence so strict usefulness can be earned by real planner impact rather than later references.

Trusted-source literature triage is a safe state-only operation for domain-aware learning. `trusted_source_literature_triage_digest` uses only the configured `openai_api` trusted-source binding and `OPENAI_API_KEY` readiness path; local Ollama is not used. It sends compact redacted role/directive/gap context, persists a `TrustedSourceLiteratureTriageDigest` with citation summaries, relevance and novelty tags, weak/rejected claims, and bounded action suggestions, then feeds that evidence into later adaptive learning and synthesis without mutating the charter or protected roots.

Trusted-source triage is also the preferred escape hatch from repeated adaptive-learning loops when the role profile is asking for trusted-source, literature, citation, or domain synthesis. If `openai_api` is ready and at least five of the latest eight completed operations are `adaptive_learning_synthesis`, the planner should choose `trusted_source_literature_triage_digest` before another adaptive-learning pass unless memory recovery, backoff promotion, or consumption-contract remediation has priority. To prevent governed continuation from starving domain-aware learning, the planner also opens one bounded triage slot after every seven completed `governed_start_next_invocation` results since the latest triage digest; below that cadence, ready governed continuation still wins.

Long-running autonomy also records `MemoryPressureStatus` under `operator_state/memory_pressure/` using cgroup memory files first, then `/proc/self/status` fallbacks. At 75% memory it can auto-execute the board-approved `memory_ledger_compaction` action when listed in `overnight_stability_policy.auto_execute_actions`; at 85% and above it prefers compaction before new governed launches and writes a `MemoryRecoveryRequest` if pressure remains high. Ledger compaction targets only known append-only autonomy JSONL ledgers under `operator_state/autonomy/ledgers`, keeps the newest hot tail in place for normal status reads, and moves older records into gzip segments under `operator_state/autonomy/ledger_archive/` with manifests containing hashes, counts, offsets, timestamps, and path hints. The legacy `memory_pressure_archive` action remains as a compatibility wrapper and invokes ledger compaction first under warning/action/critical pressure rather than recursively scanning broad state trees.

Memory recovery attempts are bounded and evidence-first. `memory_ledger_compaction` writes a `LedgerCompactionAttempt` before candidate discovery, compacts at most a small configured slice per pass, atomically replaces each source ledger only after segment verification, and records timeout or no-progress evidence without corrupting the hot ledger tail. Compaction protects persisted evidence and reduces future status/archive cost; it may not reclaim Python process RSS immediately, so repeated warning/action pressure after compaction can still recommend a Novali service restart through the existing operator-controlled path.

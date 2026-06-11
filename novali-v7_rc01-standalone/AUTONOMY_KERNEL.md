# Novali Autonomy Kernel

This document describes the first implementation slice for the Novali autonomous entity direction.

The autonomy kernel is a goal-directed layer above the existing operator chain. It does not replace:

`operator shell -> launcher -> frozen session -> bootstrap -> governed execution`

## What V1 Does

- Creates an operator-owned `AutonomyCharter` under `operator_state/autonomy/`.
- Persists append-only autonomy evidence ledgers for goals, research, plan candidates, operation proposals, board decisions, cycles, rollback records, self-modification proposals, and promotion decisions.
- Provides an always-on loop controller through the Web Shell API.
- Generates a first self-authored goal focused on Novali stack and local LLM reliability.
- Performs local approved-source research against current Novali state, local docs, and configured stack hints.
- Produces a plan candidate and either a read-only `novali_stack_status` operation proposal or, when governed readiness is already launchable with a selected directive, a bounded `governed_start_next_invocation` proposal.
- Runs an automated approval board with Planner, Research Verifier, Safety/Ops Judge, Implementation Verifier, and Promotion Judge roles.
- Keeps self-modification draft-only until a dedicated promotion packet carries tests, rollback evidence, and board approval.
- Provides an operations broker for approved Novali-stack operations.

## Boundaries

- The first approved operation target is only `novali_own_stack`.
- Emergency stop blocks the loop and operation broker.
- Operation execution requires an `OperationProposal` and an approving `ApprovalBoardDecision`.
- `governed_start_next_invocation` is only a bridge back into the existing governed-start API; it does not bypass trusted-source readiness, launch locking, pre-spawn timeout evidence, or operator emergency stop.
- Protected-root self-modification is not performed directly by the autonomy loop.
- All autonomy records are redacted through the existing redaction helper before persistence.

## Web Shell API

- `GET /shell/api/autonomy/status`
- `GET /shell/api/autonomy/goals`
- `POST /shell/api/autonomy/start`
- `POST /shell/api/autonomy/pause`
- `POST /shell/api/autonomy/emergency-stop`
- `POST /shell/api/autonomy/board/review`
- `POST /shell/api/autonomy/ops/approve`

## V1 Operations

The operations broker recognizes:

- `novali_stack_status`
- `novali_health_check`
- `novali_stack_restart`
- `ollama_model_pull`
- `state_backup`
- `governed_start_next_invocation`

The autonomy loop proposes read-only stack status when governed execution is not ready. If lightweight governed readiness is launchable and a directive is selected, it may propose `governed_start_next_invocation`; execution still goes through the operations broker and the same bounded governed-start path used by the Web Shell button. Mutating operations require explicit proposals with rollback and verification evidence before the board can approve them.

## Manual Acceptance

1. Start the Novali Web Shell.
2. Open `/shell`.
3. Inspect the `Autonomy Kernel` panel.
4. Start the loop and confirm a goal, cycle, operation proposal, and board decision appear.
5. Execute the approved read-only or governed-start operation and confirm an operation result is persisted.
6. Press emergency stop and confirm the loop and operation broker refuse further work.

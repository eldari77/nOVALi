# NOVALI v7 rc02 Public Handoff

This package is a source-first, local-evaluation handoff for the current NOVALI v7 implementation.

## Start here

1. From the repository root, run `./launch/00_first_run_wizard.ps1`.
2. The wizard builds `novali-v7-standalone:local` from this package when needed.
3. Open `http://127.0.0.1:8787/shell`.
4. Create your own local directive with `standalone_docker/generate_directive_scaffold.ps1`.
5. Bootstrap and use governed execution only through the Operator Shell.

## Public boundary

No authored, acceptance, or test directive is bundled. No active workspace, runtime ledger, provider response, credential, telemetry capture, or prebuilt image archive is bundled either. `directive_inputs/`, `operator_state/`, and `runtime_data/` are local operator-owned locations; keep their contents out of source control.

## Governance boundary

NOVALI is not self-authorizing. LLM output, trusted-source results, dashboards, and evidence packs are advisory inputs. The policy, approval board, operations broker, runtime constraints, rollback evidence, redaction rules, and emergency-stop controls remain binding.

For the detailed local workflow, see `docs/STANDALONE_DOCKER_QUICKSTART.md`, `docs/STANDALONE_OPERATOR_GUIDE.md`, and `docs/OPERATOR_SHELL.md`.

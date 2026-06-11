# Standalone Operator Guide

## First Run

1. Start Docker Desktop.
2. Run `launch/00_first_run_wizard.ps1` from the repository root.
3. Open the Operator Shell.
4. Generate or load a generic directive.
5. Bootstrap the run.
6. Start governed continuation only when the shell reports a safe state.

## Safety Controls

- Pause stops forward progress without deleting state.
- Emergency stop is the hard operator stop.
- High-impact actions require explicit policy and validation.
- Librarian packs are reusable evidence, not execution authority.

## Autonomy

Autonomy remains bounded, checkpointed, governed, and resumable. Use the Autonomy + Runtime tab to inspect memory guard state, spill state, approval gates, and trusted-source validation.


# Public Handoff Acceptance

Perform these checks without adding any fixture or test directive to the package.

1. Run `./launch/00_first_run_wizard.ps1` from the repository root.
2. Confirm the Web Operator opens at `http://127.0.0.1:8787/shell`.
3. Generate a new local directive outside source control with the scaffold helper.
4. Load it, complete bootstrap, and confirm the shell displays the expected governed status.
5. Confirm review, pause, and emergency-stop controls remain available.
6. Confirm the public package contains no directive JSON, active workspace, live state, raw provider output, or credentials.

The goal is an honest local operator path, not a pre-seeded demonstration run.

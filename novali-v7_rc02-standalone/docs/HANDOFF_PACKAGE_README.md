# NOVALI v7 rc02 Package

`novali-v7_rc02-standalone` is the current public, source-first handoff. It packages the current v7 application, Operator Shell, Docker configuration, and launch helpers while deliberately omitting all development, acceptance, and test directive files.

Run the repository-level `launch/00_first_run_wizard.ps1` to build and start it. The normal operator path is:

`Operator Shell -> launcher -> frozen session -> bootstrap -> governed execution`

Use the scaffold helper to create a local directive after launch. That operator-owned file and all state it generates stay out of public source control.

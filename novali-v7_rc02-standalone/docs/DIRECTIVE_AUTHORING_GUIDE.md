# Local Directive Authoring

The public package intentionally contains no directive fixtures. Each operator must create and review their own local input before bootstrap.

From the package root, generate a formal directive wrapper:

```powershell
.\standalone_docker\generate_directive_scaffold.ps1 `
  --output .\directive_inputs\my_first_directive.json `
  --directive-id directive_my_first_run_v1 `
  --directive-text "Plan a bounded local research task with reviewable outputs." `
  --clarified-intent-summary "Keep execution governed and stop for operator review."
```

The scaffold creates the expected `NOVALIDirectiveBootstrapFile` structure. Before loading it, the operator is responsible for making the identifier, requested work, deliverables, and stop conditions specific and reviewable.

Save the result only in your local `directive_inputs/` folder. Do not commit it, a generated dossier, or any derived runtime evidence to the public repository.

Bootstrap remains directive-first: freeform text, local LLM drafts, trusted-source results, and UI state do not replace the formal operator-selected input or the existing governance gates.

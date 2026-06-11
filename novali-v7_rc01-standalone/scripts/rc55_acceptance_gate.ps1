$ErrorActionPreference = "Stop"

$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machinePath;$userPath"

$repoRoot = Split-Path -Parent $PSScriptRoot
$proofPackageRoot = Join-Path $repoRoot "dist\novali-v6_rc55-standalone"
$proofArtifactsRoot = Join-Path $repoRoot "artifacts\operator_proof\rc55"

Write-Host "RC55 acceptance gate preflight"
Get-Command node
Get-Command npm
Get-Command npx
node -v
npm -v
npx -v

Write-Host ""
Write-Host "Running packaged operator proof against $proofPackageRoot"
node (Join-Path $repoRoot "operator_shell\web_ui\scripts\rc53_operator_proof.mjs") $proofPackageRoot $proofArtifactsRoot

Write-Host ""
Write-Host "Running focused operator regression slice"
python -m unittest `
  tests.test_operator_shell.OperatorShellTests.test_launch_python_entrypoint_non_blocking_redirects_stdio_and_tracks_child `
  tests.test_operator_web.OperatorWebTests.test_http_server_shell_root_html_uses_shell_prefixed_asset_paths `
  tests.test_operator_web.OperatorWebTests.test_http_server_shell_governed_start_success_path_contract `
  tests.test_operator_web.OperatorWebTests.test_http_server_shell_operator_state_reflects_confirmed_review_truth `
  tests.test_operator_web.OperatorWebTests.test_http_server_shell_runtime_events_heartbeat `
  tests.test_operator_web.OperatorWebTests.test_controller_real_work_benchmark_review_confirmation_surfaces_on_home_observability_and_workspace

Write-Host ""
Write-Host "Acceptance proof artifacts:"
Write-Host "  $proofArtifactsRoot\\packaged_walkthrough_summary.json"
Write-Host "  $proofArtifactsRoot\\operator_acceptance_checklist.json"
Write-Host "  $proofArtifactsRoot\\operator_acceptance_checklist.md"
Write-Host "  $proofArtifactsRoot\\screens\\01_landing_before_directive_load.png"
Write-Host "  $proofArtifactsRoot\\screens\\02_landing_directive_modal.png"
Write-Host "  $proofArtifactsRoot\\screens\\03_landing_stage_gates.png"
Write-Host "  $proofArtifactsRoot\\screens\\04_workspace_after_governed_redirect.png"
Write-Host "  $proofArtifactsRoot\\screens\\05_workspace_review_summary.png"
Write-Host "  $proofArtifactsRoot\\screens\\06_workspace_live_feed.png"

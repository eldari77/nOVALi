import fs from "fs";
import path from "path";
import { chromium } from "playwright";

function readArg(name, fallback = "") {
  const index = process.argv.indexOf(name);
  if (index >= 0 && index + 1 < process.argv.length) {
    return String(process.argv[index + 1] || "").trim();
  }
  return fallback;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForCondition(fn, timeoutMs, message) {
  const started = Date.now();
  let lastError = null;
  while (Date.now() - started < timeoutMs) {
    try {
      const result = await fn();
      if (result) {
        return result;
      }
    } catch (error) {
      lastError = error;
    }
    await delay(1200);
  }
  throw new Error(message + (lastError ? ` Last error: ${lastError.message}` : ""));
}

async function fetchJson(request, route, baseUrl) {
  const response = await request.get(`${baseUrl}/shell/api${route}`);
  const text = await response.text();
  let json = {};
  try {
    json = JSON.parse(text || "{}");
  } catch {
    json = { parse_error: true, raw: text };
  }
  return { status: response.status(), ok: response.ok(), text, json };
}

async function postJson(request, route, baseUrl, payload = {}, options = {}) {
  const response = await request.post(`${baseUrl}/shell/api${route}`, {
    data: payload,
    headers: { "Content-Type": "application/json" },
    timeout: Number(options.timeout || 30000),
  });
  const text = await response.text();
  let json = {};
  try {
    json = JSON.parse(text || "{}");
  } catch {
    json = { parse_error: true, raw: text };
  }
  return { status: response.status(), ok: response.ok(), text, json };
}

function writeJson(targetPath, payload) {
  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
  fs.writeFileSync(targetPath, JSON.stringify(payload, null, 2));
}

function writeText(targetPath, content) {
  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
  fs.writeFileSync(targetPath, content);
}

async function waitForShell(page, baseUrl) {
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 180000 });
  await page.waitForURL("**/shell", { timeout: 180000 });
  await page.getByRole("button", { name: "Load Directive" }).waitFor({ timeout: 120000 });
}

async function startSeededWorkspaceViaApi(page, request, baseUrl, directivePath, options = {}) {
  const settleAfterStart = options?.settleAfterStart !== false;
  const directiveSelection = await postJson(request, "/directive/select", baseUrl, {
    directive_path: directivePath,
  });
  if (!directiveSelection.ok || directiveSelection.json?.ok !== true) {
    throw new Error(`Directive select failed for ${directivePath}`);
  }
  const workspaceId =
    String(directiveSelection.json?.state?.directive?.selected_workspace_id || "").trim() ||
    path.basename(directivePath, ".json");

  const bootstrapProfileSave = await request.post(`${baseUrl}/runtime/save`, {
    form: {
      execution_profile: "bootstrap_only_initialization",
      workspace_id: workspaceId,
      max_memory_mb: "2048",
      max_python_threads: "8",
      max_child_processes: "0",
      subprocess_mode: "disabled",
      session_time_limit_seconds: "600",
      governed_execution_mode: "single_cycle",
      max_cycles_per_invocation: "1",
      max_total_cycles: "1",
      backend_kind: "local_guarded",
      cpu_limit_cpus: "",
      docker_image: "python:3.12-slim",
      network_policy_intent: "deny_all",
    },
  });
  if (!bootstrapProfileSave.ok()) {
    throw new Error(`Runtime bootstrap-profile save failed for ${directivePath}`);
  }

  await waitForCondition(async () => {
    const operatorState = await fetchJson(request, "/operator-state", baseUrl);
    return operatorState.json?.launch_readiness?.bootstrap?.can_launch ? operatorState.json : null;
  }, 180000, "Timed out waiting for bootstrap initialization to become launch-ready.");

  const bootstrap = await postJson(
    request,
    "/bootstrap/start",
    baseUrl,
    { directive_path: directivePath },
    { timeout: 240000 },
  );
  if (!bootstrap.ok || bootstrap.json?.ok !== true) {
    throw new Error(`Bootstrap start failed for ${directivePath}`);
  }

  const prepare = await postJson(
    request,
    "/governed/prepare",
    baseUrl,
    { directive_path: directivePath },
    { timeout: 240000 },
  );
  if (!prepare.ok || prepare.json?.ok !== true) {
    throw new Error(`Governed prepare failed for ${directivePath}`);
  }

  if (options?.overrideGovernedProfile) {
    const governedProfileSave = await request.post(`${baseUrl}/runtime/save`, {
      form: {
        execution_profile: "bounded_active_workspace_coding",
        workspace_id: workspaceId,
        max_memory_mb: "2048",
        max_python_threads: "8",
        max_child_processes: "0",
        subprocess_mode: "disabled",
        session_time_limit_seconds: "600",
        governed_execution_mode: String(options.overrideGovernedProfile.governed_execution_mode || "multi_cycle"),
        max_cycles_per_invocation: String(options.overrideGovernedProfile.max_cycles_per_invocation || "2"),
        max_total_cycles: String(options.overrideGovernedProfile.max_total_cycles || "4"),
        backend_kind: "local_guarded",
        cpu_limit_cpus: "",
        docker_image: "python:3.12-slim",
        network_policy_intent: "deny_all",
      },
    });
    if (!governedProfileSave.ok()) {
      throw new Error(`Runtime governed-profile save failed for ${directivePath}`);
    }
    await waitForCondition(async () => {
      const operatorState = await fetchJson(request, "/operator-state", baseUrl);
      return operatorState.json?.launch_readiness?.governed?.can_launch ? operatorState.json : null;
    }, 180000, "Timed out waiting for governed runtime profile to become launch-ready.");
  }

  const governedStart = await postJson(
    request,
    "/governed/start",
    baseUrl,
    { directive_path: directivePath },
    { timeout: 420000 },
  );
  if (!governedStart.ok || governedStart.json?.ok !== true) {
    throw new Error(`Governed start failed for ${directivePath}`);
  }

  await page.goto(`${baseUrl}/shell/workspace`, { waitUntil: "domcontentloaded", timeout: 180000 });
  await page.getByRole("heading", { name: "Operator Workspace" }).waitFor({ timeout: 120000 });

  const longRunState = await waitForCondition(async () => {
    const result = await fetchJson(request, "/long-run-state", baseUrl);
    const sessionId = String(result.json?.long_run?.session_id || "").trim();
    return result.status === 200 && sessionId ? result.json : null;
  }, 180000, "Timed out waiting for long-run state after governed start.");

  let settledLongRunState = null;
  if (settleAfterStart) {
    settledLongRunState = await waitForCondition(async () => {
      const result = await fetchJson(request, "/long-run-state", baseUrl);
      const sessionId = String(result.json?.long_run?.session_id || "").trim();
      const activeProcessId = Number(result.json?.long_run?.active_process_id || 0);
      const lifecycleState = String(result.json?.long_run?.lifecycle_state || "").trim();
      if (sessionId && activeProcessId === 0 && lifecycleState) {
        return result.json;
      }
      return null;
    }, 300000, "Timed out waiting for governed execution to settle after start.");
  }

  return {
    directive_selection: directiveSelection,
    bootstrap,
    governed_prepare: prepare,
    governed_start: governedStart,
    long_run_state: settledLongRunState || longRunState,
  };
}

async function ensureBlockingCurrentSession(page, request, baseUrl) {
  let currentState = await fetchJson(request, "/long-run-state", baseUrl);
  const currentBucket = String(currentState.json?.operator_guidance?.attention_signal?.severity || "");
  const primaryLabel = String(currentState.json?.operator_guidance?.primary_cta?.label || "");
  const blockingCount = Number(currentState.json?.operator_guidance?.attention_inbox?.blocking_count || 0);
  if (blockingCount > 0 || /approve|review|resolve/i.test(primaryLabel) || currentBucket === "blocking") {
    return currentState.json;
  }

  const beforeCycle = Number(currentState.json?.long_run?.current_cycle || 0);
  const continueButton = page.locator('[data-testid="long-run-primary-cta"]');
  await continueButton.waitFor({ timeout: 120000 });
  await continueButton.click();

  return await waitForCondition(async () => {
    const latest = await fetchJson(request, "/long-run-state", baseUrl);
    const latestBlocking = Number(latest.json?.operator_guidance?.attention_inbox?.blocking_count || 0);
    const latestLabel = String(latest.json?.operator_guidance?.primary_cta?.label || "");
    const latestCycle = Number(latest.json?.long_run?.current_cycle || 0);
    if (latestBlocking > 0 || /approve|review|resolve/i.test(latestLabel) || latestCycle > beforeCycle) {
      return latest.json;
    }
    return null;
  }, 240000, "Timed out waiting for a blocking or advanced session state after continuation.");
}

function preferredReviewActionFromState(state) {
  const primaryCta = state?.operator_guidance?.primary_cta || {};
  const actionId = String(primaryCta?.preferred_review_action_id || "").trim();
  const reviewItemId = String(primaryCta?.preferred_review_item_id || "").trim();
  return actionId && reviewItemId ? { action_id: actionId, review_item_id: reviewItemId } : null;
}

async function approveCurrentReviewAction(request, baseUrl) {
  const beforeState = await fetchJson(request, "/long-run-state", baseUrl);
  const preferredAction = preferredReviewActionFromState(beforeState.json);
  const beforeLabel = String(beforeState.json?.operator_guidance?.primary_cta?.label || "").trim();
  const beforeLifecycle = String(beforeState.json?.long_run?.lifecycle_state || "").trim();
  const beforeResolvedCount = Number(beforeState.json?.intervention_summary?.resolved_review_item_count || 0);
  const beforePendingCount = Number(beforeState.json?.intervention_summary?.pending_review_count || 0);
  if (!preferredAction) {
    throw new Error("Current session did not expose a preferred review action/item for approval.");
  }
  const approval = await postJson(
    request,
    "/review/action",
    baseUrl,
    {
      action_id: preferredAction.action_id,
      review_item_id: preferredAction.review_item_id,
      operator_note: "rc73 packaged proof approval",
    },
    { timeout: 180000 },
  );
  if (!approval.ok || approval.json?.ok !== true) {
    throw new Error(
      `Review approval failed for ${preferredAction.review_item_id} via ${preferredAction.action_id}.`,
    );
  }
  return await waitForCondition(async () => {
    const latest = await fetchJson(request, "/long-run-state", baseUrl);
    const latestPreferredAction = preferredReviewActionFromState(latest.json);
    const latestLabel = String(latest.json?.operator_guidance?.primary_cta?.label || "").trim();
    const latestLifecycle = String(latest.json?.long_run?.lifecycle_state || "").trim();
    const latestResolvedCount = Number(latest.json?.intervention_summary?.resolved_review_item_count || 0);
    const latestPendingCount = Number(latest.json?.intervention_summary?.pending_review_count || 0);
    if (
      !latestPreferredAction ||
      latestPreferredAction.action_id !== preferredAction.action_id ||
      latestPreferredAction.review_item_id !== preferredAction.review_item_id ||
      latestLabel !== beforeLabel ||
      latestLifecycle !== beforeLifecycle ||
      latestResolvedCount !== beforeResolvedCount ||
      latestPendingCount !== beforePendingCount
    ) {
      return latest.json;
    }
    return null;
  }, 300000, "Timed out waiting for long-run state to move past the approved review item.");
}

async function continueSameSession(request, baseUrl, beforeState) {
  const beforeSessionId = String(beforeState?.long_run?.session_id || "").trim();
  const beforeCycle = Number(beforeState?.long_run?.current_cycle || 0);
  const beforeCheckpointCount = Number(beforeState?.long_run?.checkpoint_count || 0);
  const continuation = await postJson(request, "/long-run/continue", baseUrl, {}, { timeout: 240000 });
  if (!continuation.ok || continuation.json?.ok !== true) {
    throw new Error(
      `Continue request was not accepted truthfully: ${continuation.json?.message || continuation.text || "unknown error"}`,
    );
  }
  return await waitForCondition(async () => {
    const latest = await fetchJson(request, "/long-run-state", baseUrl);
    const latestSessionId = String(latest.json?.long_run?.session_id || "").trim();
    const latestCycle = Number(latest.json?.long_run?.current_cycle || 0);
    const latestCheckpointCount = Number(latest.json?.long_run?.checkpoint_count || 0);
    const activeProcessId = Number(latest.json?.long_run?.active_process_id || 0);
    if (
      latestSessionId === beforeSessionId &&
      activeProcessId === 0 &&
      (latestCycle > beforeCycle || latestCheckpointCount > beforeCheckpointCount)
    ) {
      return latest.json;
    }
    return null;
  }, 300000, "Timed out waiting for same-session continuation to settle after request.");
}

async function advanceCurrentSessionToCompletedHistory(page, request, baseUrl) {
  const before = await fetchJson(request, "/long-run-state", baseUrl);
  const beforeSessionId = String(before.json?.long_run?.session_id || "");
  const beforeCycle = Number(before.json?.long_run?.current_cycle || 0);
  const beforeLifecycle = String(before.json?.long_run?.lifecycle_state || "").toLowerCase();
  const beforeLabel = String(before.json?.operator_guidance?.primary_cta?.label || "");
  if (
    beforeLifecycle.includes("halt") ||
    beforeLifecycle.includes("completed") ||
    /review results/i.test(beforeLabel)
  ) {
    return before.json;
  }
  const afterApproval = await approveCurrentReviewAction(request, baseUrl);
  const afterApprovalLabel = String(afterApproval?.operator_guidance?.primary_cta?.label || "");
  if (/continue/i.test(afterApprovalLabel)) {
    await continueSameSession(request, baseUrl, afterApproval);
  }
  return await waitForCondition(async () => {
    const latest = await fetchJson(request, "/long-run-state", baseUrl);
    const sessionId = String(latest.json?.long_run?.session_id || "");
    const lifecycle = String(latest.json?.long_run?.lifecycle_state || "").toLowerCase();
    const completionState = String(latest.json?.long_run?.completion_state || "").toLowerCase();
    const label = String(latest.json?.operator_guidance?.primary_cta?.label || "");
    const cycle = Number(latest.json?.long_run?.current_cycle || 0);
    return sessionId === beforeSessionId &&
      cycle >= beforeCycle + 1 &&
      (
        lifecycle.includes("halt") ||
        lifecycle.includes("completed") ||
        completionState.includes("completed") ||
        /review results/i.test(label)
      )
      ? latest.json
      : null;
  }, 300000, "Timed out waiting for session A to settle into completed/halted history.");
}

async function waitForPortfolio(page) {
  await page.waitForURL("**/shell**", { timeout: 180000 });
  await page
    .locator('[data-testid="session-portfolio-lifecycle-section"]')
    .first()
    .waitFor({ timeout: 120000 });
  return await waitForCondition(
    async () => {
      const cards = await readPortfolioCards(page);
      return cards.length >= 2 && cards.some((card) => card.current_session) ? cards : null;
    },
    180000,
    "Timed out waiting for a populated portfolio queue with a marked current session.",
  );
}

async function readPortfolioCards(page) {
  return await page.locator('[data-testid="session-portfolio-card"]').evaluateAll((nodes) =>
    nodes.map((node) => ({
      session_id: node.getAttribute("data-session-id") || "",
      queue_bucket: node.getAttribute("data-queue-bucket") || "",
      lifecycle_section: node.getAttribute("data-lifecycle-section") || "",
      pinned: node.getAttribute("data-pinned") === "true",
      archived: node.getAttribute("data-archived") === "true",
      current_session: node.getAttribute("data-current-session") === "true",
      text: (node.textContent || "").trim(),
    })),
  );
}

function currentBlockingBucket(queueBucket) {
  return [
    "new_blocking_now",
    "stale_escalated_blocking",
    "seen_unresolved_blocking",
    "acknowledged_unresolved_blocking",
  ].includes(String(queueBucket || "").trim());
}

async function pinSessionCard(page, sessionId) {
  const card = page.locator(`[data-testid="session-portfolio-card"][data-session-id="${sessionId}"]`);
  await card.locator('[data-testid="session-portfolio-card-pin"]').click();
  await waitForCondition(async () => {
    return (await card.getAttribute("data-pinned")) === "true" &&
      (await card.getAttribute("data-lifecycle-section")) === "pinned"
      ? true
      : null;
  }, 120000, `Timed out waiting for session ${sessionId} to become pinned.`);
}

async function archiveSessionCard(page, sessionId) {
  const card = page.locator(`[data-testid="session-portfolio-card"][data-session-id="${sessionId}"]`);
  await card.locator('[data-testid="session-portfolio-card-archive"]').click();
  await waitForCondition(async () => {
    return (await card.getAttribute("data-archived")) === "true" &&
      (await card.getAttribute("data-lifecycle-section")) === "archived"
      ? true
      : null;
  }, 120000, `Timed out waiting for session ${sessionId} to move into the archive.`);
}

async function setBatchSelection(page, sessionId, selected) {
  const card = page.locator(`[data-testid="session-portfolio-card"][data-session-id="${sessionId}"]`);
  const targetValue = selected ? "true" : "false";
  const currentValue = await card.getAttribute("data-batch-selected");
  if (currentValue === targetValue) {
    return;
  }
  await card.locator('[data-testid="session-portfolio-card-select"]').click();
  await waitForCondition(async () => {
    return (await card.getAttribute("data-batch-selected")) === targetValue ? true : null;
  }, 120000, `Timed out waiting for session ${sessionId} batch-selected=${targetValue}.`);
}

async function runBatchAction(page, actionTestId) {
  const toolbar = page.locator('[data-testid="session-portfolio-batch-toolbar"]');
  await toolbar.waitFor({ timeout: 120000 });
  await toolbar.locator(`[data-testid="${actionTestId}"]`).click();
}

async function readGroupedCounts(page) {
  const groups = [
    "all",
    "blocking_now",
    "stale_escalated",
    "acknowledged_unresolved",
    "resumable",
    "running_waiting",
    "completed_halted",
    "archived",
    "shortlisted",
    "informational_recent",
  ];
  const counts = {};
  for (const key of groups) {
    const locator = page.locator(`[data-testid="session-portfolio-group-filter-${key}"]`);
    if ((await locator.count()) === 0) {
      continue;
    }
    const text = String((await locator.innerText()) || "").trim();
    const match = text.match(/\((\d+)\)\s*$/);
    counts[key] = {
      text,
      count: Number(match?.[1] || 0),
    };
  }
  return counts;
}

async function readManagerDashboard(page) {
  const dashboard = page.locator('[data-testid="session-portfolio-manager-dashboard"]');
  await dashboard.waitFor({ timeout: 120000 });
  const dominantAction = dashboard.locator(
    '[data-testid="session-portfolio-manager-dominant-action"] button',
  );
  const dominantActionCount = await dominantAction.count();
  return {
    headline: String(
      (await page.locator('[data-testid="session-portfolio-manager-headline"]').innerText()) ||
        "",
    ).trim(),
    dominant_action_label:
      dominantActionCount > 0 ? String((await dominantAction.innerText()) || "").trim() : "",
    grouped_counts: await readGroupedCounts(page),
    visible_summary_actions: await dashboard
      .locator('[data-testid^="session-portfolio-summary-action-"]')
      .evaluateAll((nodes) =>
        nodes.map((node) => ({
          test_id: node.getAttribute("data-testid") || "",
          text: (node.textContent || "").trim(),
        })),
      ),
  };
}

async function useGroupedFilter(page, key) {
  const locator = page.locator(`[data-testid="session-portfolio-group-filter-${key}"]`);
  await locator.waitFor({ timeout: 120000 });
  await locator.click();
}

async function clickSummaryAction(page, key) {
  const locator = page.locator(`[data-testid="session-portfolio-summary-action-${key}"]`);
  await locator.waitFor({ timeout: 120000 });
  const label = String((await locator.innerText()) || "").trim();
  await locator.click();
  return label;
}

const artifactRoot = readArg("--artifact-root");
const baseUrl = readArg("--base-url", "http://127.0.0.1:8787");
const directivePath = readArg("--directive-path");

if (!artifactRoot || !directivePath) {
  throw new Error("Missing required args. Expected --artifact-root and --directive-path.");
}

const benchmarkDirectivePath = path.join(
  path.resolve(path.dirname(directivePath), ".."),
  "manual_acceptance_samples",
  "successor_package_readiness_benchmark_directive.json",
);
const screensDir = path.join(artifactRoot, "screens");
fs.mkdirSync(screensDir, { recursive: true });

const runSummaryPath = path.join(artifactRoot, "rc73_operator_journey.json");
const runMarkdownPath = path.join(artifactRoot, "rc73_operator_journey.md");
const managerDashboardSummaryJsonPath = path.join(artifactRoot, "manager_dashboard_summary.json");
const managerDashboardSummaryMdPath = path.join(artifactRoot, "manager_dashboard_summary.md");
const portfolioSummaryActionsJsonPath = path.join(artifactRoot, "portfolio_summary_actions.json");
const portfolioSummaryActionsMdPath = path.join(artifactRoot, "portfolio_summary_actions.md");
const groupedQueueCountsPath = path.join(artifactRoot, "grouped_queue_counts.json");
const nextActionRecommendationSummaryPath = path.join(
  artifactRoot,
  "next_action_recommendation_summary.json",
);
const sameSessionPortfolioIdentityPath = path.join(artifactRoot, "same_session_portfolio_identity.json");
const packagedRouteValidationPath = path.join(artifactRoot, "packaged_route_validation.json");

const summary = {
  success: false,
  base_url: baseUrl,
  directive_path_used: directivePath,
  benchmark_directive_path_used: benchmarkDirectivePath,
  session_a: {},
  session_b: {},
  portfolio_before_actions: [],
  portfolio_after_summary_action: [],
  portfolio_filtered_view: [],
  portfolio_after_return: [],
  manager_dashboard_before: {},
  manager_dashboard_after_return: {},
  grouped_counts_before: {},
  grouped_counts_after_action: {},
  grouped_counts_after_return: {},
  summary_actions: {
    archive_completed_history_label: "",
    archive_completed_history_worked: false,
    open_blocking_leader_label: "",
    open_blocking_leader_worked: false,
  },
  grouped_views: {
    filter_used: "",
    filter_worked: false,
  },
  queue_focus: {
    before_visible_count: 0,
    after_summary_action_visible_count: 0,
    archived_count_after_action: 0,
  },
  same_session_preserved: false,
  cycle_delta: 0,
  checkpoint_delta: 0,
  route_validation: {},
  failures: [],
  timeline: [],
};

function pushStep(step, extra = {}) {
  summary.timeline.push({ at: new Date().toISOString(), step, ...extra });
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await context.newPage();
const request = context.request;

try {
  await waitForShell(page, baseUrl);

  const sessionASeed = await startSeededWorkspaceViaApi(page, request, baseUrl, benchmarkDirectivePath);
  const sessionACompleted = await advanceCurrentSessionToCompletedHistory(page, request, baseUrl);
  summary.session_a = {
    session_id: String(sessionACompleted?.long_run?.session_id || sessionASeed.long_run_state?.long_run?.session_id || ""),
    directive_id: String(sessionACompleted?.long_run?.directive_id || sessionASeed.long_run_state?.long_run?.directive_id || ""),
    workspace_id: String(sessionACompleted?.long_run?.workspace_id || sessionASeed.long_run_state?.long_run?.workspace_id || ""),
    workspace_root: String(sessionACompleted?.long_run?.workspace_root || sessionASeed.long_run_state?.long_run?.workspace_root || ""),
    lifecycle_state: String(sessionACompleted?.long_run?.lifecycle_state || sessionASeed.long_run_state?.long_run?.lifecycle_state || ""),
    current_cycle: Number(sessionACompleted?.long_run?.current_cycle || sessionASeed.long_run_state?.long_run?.current_cycle || 0),
    checkpoint_count: Number(sessionACompleted?.long_run?.checkpoint_count || sessionASeed.long_run_state?.long_run?.checkpoint_count || 0),
    primary_cta: String(sessionACompleted?.operator_guidance?.primary_cta?.label || sessionASeed.long_run_state?.operator_guidance?.primary_cta?.label || ""),
  };
  pushStep("session_a_completed_history", summary.session_a);

  await page.goto(`${baseUrl}/shell`, { waitUntil: "domcontentloaded", timeout: 180000 });

  const sessionBSeed = await startSeededWorkspaceViaApi(page, request, baseUrl, directivePath, {
    settleAfterStart: false,
    overrideGovernedProfile: {
      governed_execution_mode: "multi_cycle",
      max_cycles_per_invocation: "2",
      max_total_cycles: "4",
    },
  });
  const sessionBBlocking = await ensureBlockingCurrentSession(page, request, baseUrl);
  summary.session_b = {
    session_id: String(sessionBBlocking?.long_run?.session_id || ""),
    directive_id: String(sessionBBlocking?.long_run?.directive_id || ""),
    workspace_id: String(sessionBBlocking?.long_run?.workspace_id || ""),
    workspace_root: String(sessionBBlocking?.long_run?.workspace_root || ""),
    lifecycle_state: String(sessionBBlocking?.long_run?.lifecycle_state || ""),
    current_cycle: Number(sessionBBlocking?.long_run?.current_cycle || 0),
    checkpoint_count: Number(sessionBBlocking?.long_run?.checkpoint_count || 0),
    primary_cta: String(sessionBBlocking?.operator_guidance?.primary_cta?.label || ""),
    blocking_count: Number(sessionBBlocking?.operator_guidance?.attention_inbox?.blocking_count || 0),
    directive_select_status: Number(sessionBSeed.directive_selection?.status || 0),
    bootstrap_status: Number(sessionBSeed.bootstrap?.status || 0),
    governed_prepare_status: Number(sessionBSeed.governed_prepare?.status || 0),
    governed_start_status: Number(sessionBSeed.governed_start?.status || 0),
  };
  pushStep("session_b_blocking_ready", summary.session_b);

  if (summary.session_a.session_id === summary.session_b.session_id) {
    throw new Error("Portfolio lifecycle proof did not produce two distinct session ids.");
  }

  await page.goto(`${baseUrl}/shell`, { waitUntil: "domcontentloaded", timeout: 180000 });
  summary.portfolio_before_actions = await waitForPortfolio(page);
  summary.queue_focus.before_visible_count = summary.portfolio_before_actions.length;
  summary.manager_dashboard_before = await readManagerDashboard(page);
  summary.grouped_counts_before = summary.manager_dashboard_before.grouped_counts;
  await page.screenshot({
    path: path.join(screensDir, "rc73_01_shell_grouped_dashboard.png"),
    fullPage: true,
  });

  const currentBlockingCard = summary.portfolio_before_actions.find(
    (card) => card.session_id === summary.session_b.session_id,
  );
  const closeoutCard = summary.portfolio_before_actions.find(
    (card) => card.session_id === summary.session_a.session_id,
  );
  if (!currentBlockingCard || !closeoutCard) {
    throw new Error("Portfolio did not expose both the blocking session and the completed/recent session.");
  }
  if (!currentBlockingBucket(currentBlockingCard.queue_bucket)) {
    throw new Error(`Current blocking session did not lead the actionable queue. Saw ${currentBlockingCard.queue_bucket}.`);
  }
  if (Number(summary.grouped_counts_before?.blocking_now?.count || 0) < 1) {
    throw new Error("Manager dashboard did not surface a truthful blocking-now count.");
  }
  if (Number(summary.grouped_counts_before?.completed_halted?.count || 0) < 1) {
    throw new Error("Manager dashboard did not surface a truthful completed/halted count.");
  }

  summary.summary_actions.archive_completed_history_label = await clickSummaryAction(
    page,
    "archive_completed_history",
  );
  summary.portfolio_after_summary_action = await waitForCondition(
    async () => {
      const cards = await readPortfolioCards(page);
      const archivedSession = cards.find(
        (card) => card.session_id === summary.session_a.session_id,
      );
      return archivedSession?.archived ? cards : null;
    },
    180000,
    "Timed out waiting for the manager summary archive action to move the completed session into archive.",
  );
  summary.summary_actions.archive_completed_history_worked = true;
  summary.queue_focus.after_summary_action_visible_count =
    summary.portfolio_after_summary_action.length;
  summary.queue_focus.archived_count_after_action =
    summary.portfolio_after_summary_action.filter((card) => card.archived).length;
  summary.grouped_counts_after_action = await readGroupedCounts(page);
  await page.screenshot({
    path: path.join(screensDir, "rc73_02_manager_summary_action_archive.png"),
    fullPage: true,
  });

  const archivedSessionA = summary.portfolio_after_summary_action.find(
    (card) => card.session_id === summary.session_a.session_id,
  );
  const currentSessionBAfterArchive = summary.portfolio_after_summary_action.find(
    (card) => card.session_id === summary.session_b.session_id,
  );
  if (!archivedSessionA || archivedSessionA.lifecycle_section !== "archived") {
    throw new Error("Summary archive action did not move the completed session into the archived lifecycle section.");
  }
  if (!currentSessionBAfterArchive || currentBlockingBucket(currentSessionBAfterArchive.queue_bucket) !== true) {
    throw new Error("Current blocking session did not remain the actionable queue leader after summary archive.");
  }

  await useGroupedFilter(page, "archived");
  summary.portfolio_filtered_view = await waitForCondition(
    async () => {
      const cards = await readPortfolioCards(page);
      return cards.length > 0 && cards.every((card) => card.archived) ? cards : null;
    },
    180000,
    "Timed out waiting for the archived group filter to focus archived sessions.",
  );
  summary.grouped_views.filter_used = "archived";
  summary.grouped_views.filter_worked = summary.portfolio_filtered_view.some(
    (card) => card.session_id === summary.session_a.session_id,
  );
  await page.screenshot({
    path: path.join(screensDir, "rc73_03_group_filter_archived.png"),
    fullPage: true,
  });
  if (!summary.grouped_views.filter_worked) {
    throw new Error("Archived grouped bucket view did not expose the archived session history truthfully.");
  }

  await useGroupedFilter(page, "blocking_now");
  await waitForCondition(
    async () => {
      const cards = await readPortfolioCards(page);
      return cards.some((card) => card.session_id === summary.session_b.session_id)
        ? cards
        : null;
    },
    180000,
    "Timed out waiting for the blocking bucket view to refocus the current blocking session.",
  );
  summary.summary_actions.open_blocking_leader_label = await clickSummaryAction(
    page,
    "open_blocking_leader",
  );
  await page.waitForURL("**/shell/workspace**", { timeout: 180000 });
  await waitForCondition(async () => {
    const focusedBlocking = await page.locator('[data-testid="blocking-attention-item"][data-focused-target="true"]').count();
    const focusedPacket = await page.locator('[data-testid="attention-packet"][data-focused-target="true"]').count();
    return focusedBlocking > 0 || focusedPacket > 0;
  }, 180000, "Timed out waiting for the blocking queue jump to focus the exact packet/action.");
  summary.summary_actions.open_blocking_leader_worked = true;
  await page.screenshot({
    path: path.join(screensDir, "rc73_04_dashboard_to_blocker.png"),
    fullPage: true,
  });

  const beforeQueueAction = await fetchJson(request, "/long-run-state", baseUrl);
  const postQueueApproval = await approveCurrentReviewAction(request, baseUrl);
  const afterQueueAction = await continueSameSession(request, baseUrl, postQueueApproval);
  summary.same_session_preserved =
    String(beforeQueueAction.json?.long_run?.session_id || "") ===
    String(afterQueueAction?.long_run?.session_id || "");
  summary.cycle_delta =
    Number(afterQueueAction?.long_run?.current_cycle || 0) -
    Number(beforeQueueAction.json?.long_run?.current_cycle || 0);
  summary.checkpoint_delta =
    Number(afterQueueAction?.long_run?.checkpoint_count || 0) -
    Number(beforeQueueAction.json?.long_run?.checkpoint_count || 0);
  await page.screenshot({
    path: path.join(screensDir, "rc73_05_selected_session_after_continue.png"),
    fullPage: true,
  });

  await page.goto(`${baseUrl}/shell`, { waitUntil: "domcontentloaded", timeout: 180000 });
  summary.portfolio_after_return = await waitForPortfolio(page);
  summary.manager_dashboard_after_return = await readManagerDashboard(page);
  summary.grouped_counts_after_return = summary.manager_dashboard_after_return.grouped_counts;
  await page.screenshot({
    path: path.join(screensDir, "rc73_06_shell_after_return.png"),
    fullPage: true,
  });

  const routeValidation = {};
  for (const route of ["/healthz", "/", "/shell", "/workspace", "/shell/workspace"]) {
    const response = await context.request.get(`${baseUrl}${route}`, { maxRedirects: 0 });
    routeValidation[route] = {
      status: response.status(),
      location: response.headers()["location"] || "",
    };
  }
  for (const route of ["/operator-state", "/intervention-state", "/long-run-state"]) {
    const response = await fetchJson(request, route, baseUrl);
    routeValidation[`/shell/api${route}`] = {
      status: response.status,
      ok: response.ok,
    };
  }
  summary.route_validation = routeValidation;

  writeJson(managerDashboardSummaryJsonPath, {
    session_a: summary.session_a,
    session_b: summary.session_b,
    manager_dashboard_before: summary.manager_dashboard_before,
    manager_dashboard_after_return: summary.manager_dashboard_after_return,
    grouped_counts_before: summary.grouped_counts_before,
    grouped_counts_after_return: summary.grouped_counts_after_return,
  });
  writeText(
    managerDashboardSummaryMdPath,
    [
      "# manager dashboard summary",
      "",
      `- dominant headline before actions: \`${summary.manager_dashboard_before?.headline || "<none>"}\``,
      `- dominant action before actions: \`${summary.manager_dashboard_before?.dominant_action_label || "<none>"}\``,
      `- dominant headline after return: \`${summary.manager_dashboard_after_return?.headline || "<none>"}\``,
      `- grouped blocking count before actions: \`${summary.grouped_counts_before?.blocking_now?.count || 0}\``,
      `- grouped completed/halted count before actions: \`${summary.grouped_counts_before?.completed_halted?.count || 0}\``,
      "",
    ].join("\n"),
  );
  writeJson(portfolioSummaryActionsJsonPath, {
    summary_actions: summary.summary_actions,
    portfolio_before_actions: summary.portfolio_before_actions,
    portfolio_after_summary_action: summary.portfolio_after_summary_action,
    portfolio_filtered_view: summary.portfolio_filtered_view,
    queue_focus: summary.queue_focus,
  });
  writeText(
    portfolioSummaryActionsMdPath,
    [
      "# portfolio summary actions",
      "",
      `- archive completed history label: \`${summary.summary_actions.archive_completed_history_label || "<none>"}\``,
      `- archive completed history worked: \`${summary.summary_actions.archive_completed_history_worked}\``,
      `- open blocking leader label: \`${summary.summary_actions.open_blocking_leader_label || "<none>"}\``,
      `- open blocking leader worked: \`${summary.summary_actions.open_blocking_leader_worked}\``,
      `- grouped filter used: \`${summary.grouped_views.filter_used || "<none>"}\``,
      `- grouped filter worked: \`${summary.grouped_views.filter_worked}\``,
      "",
    ].join("\n"),
  );
  writeJson(groupedQueueCountsPath, {
    before_actions: summary.grouped_counts_before,
    after_summary_action: summary.grouped_counts_after_action,
    after_return: summary.grouped_counts_after_return,
    queue_focus: summary.queue_focus,
  });
  writeJson(nextActionRecommendationSummaryPath, {
    before_actions: {
      headline: summary.manager_dashboard_before?.headline || "",
      dominant_action_label: summary.manager_dashboard_before?.dominant_action_label || "",
      visible_summary_actions: summary.manager_dashboard_before?.visible_summary_actions || [],
    },
    after_return: {
      headline: summary.manager_dashboard_after_return?.headline || "",
      dominant_action_label: summary.manager_dashboard_after_return?.dominant_action_label || "",
      visible_summary_actions: summary.manager_dashboard_after_return?.visible_summary_actions || [],
    },
  });
  writeJson(sameSessionPortfolioIdentityPath, {
    session_id_before_queue_action: String(beforeQueueAction.json?.long_run?.session_id || ""),
    session_id_after_queue_action: String(afterQueueAction?.long_run?.session_id || ""),
    same_session_preserved: summary.same_session_preserved,
    cycle_delta: summary.cycle_delta,
    checkpoint_delta: summary.checkpoint_delta,
  });
  writeJson(packagedRouteValidationPath, routeValidation);

  summary.success = true;
} catch (error) {
  summary.failures.push(error?.message || String(error));
  pushStep("failure", { message: error?.message || String(error) });
  try {
    await page.screenshot({
      path: path.join(screensDir, "rc73_zz_failure.png"),
      fullPage: true,
    });
  } catch {
    // Keep failure reporting intact.
  }
} finally {
  writeJson(runSummaryPath, summary);
  writeText(
    runMarkdownPath,
    [
      "# rc73 operator journey",
      "",
      `- success: \`${summary.success}\``,
      `- blocking session: \`${summary.session_b.session_id || "<none>"}\``,
      `- archived session: \`${summary.session_a.session_id || "<none>"}\``,
      `- archive completed history worked: \`${summary.summary_actions.archive_completed_history_worked}\``,
      `- grouped filter worked: \`${summary.grouped_views.filter_worked}\``,
      `- open blocking leader worked: \`${summary.summary_actions.open_blocking_leader_worked}\``,
      `- same-session preserved: \`${summary.same_session_preserved}\``,
      `- cycle delta after queue action: \`${summary.cycle_delta}\``,
      `- checkpoint delta after queue action: \`${summary.checkpoint_delta}\``,
      summary.failures.length ? `- failures: ${summary.failures.join(" | ")}` : "- failures: none",
      "",
    ].join("\n"),
  );
  process.exitCode = summary.success ? 0 : 1;
  await browser.close();
}

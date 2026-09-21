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
      operator_note: "rc71 packaged proof approval",
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
  await page.locator('[data-testid="session-portfolio-section"]').waitFor({ timeout: 120000 });
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

const runSummaryPath = path.join(artifactRoot, "rc72_operator_journey.json");
const runMarkdownPath = path.join(artifactRoot, "rc72_operator_journey.md");
const portfolioShortcutSummaryJsonPath = path.join(artifactRoot, "portfolio_action_shortcuts_summary.json");
const portfolioShortcutSummaryMdPath = path.join(artifactRoot, "portfolio_action_shortcuts_summary.md");
const batchTriageSummaryJsonPath = path.join(artifactRoot, "bounded_batch_triage_summary.json");
const batchTriageSummaryMdPath = path.join(artifactRoot, "bounded_batch_triage_summary.md");
const queueFocusAfterActionsPath = path.join(artifactRoot, "queue_focus_after_shortcuts_and_batch.json");
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
  portfolio_after_batch_pin: [],
  portfolio_after_batch_archive: [],
  portfolio_after_return: [],
  shortcut_actions: {
    blocker_shortcut_label: "",
    blocker_shortcut_worked: false,
  },
  batch_actions: {
    batch_pin_worked: false,
    batch_archive_worked: false,
  },
  queue_focus: {
    before_non_archived_count: 0,
    after_archive_non_archived_count: 0,
    archived_count_after_archive: 0,
  },
  actionable_jump_worked: false,
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
  summary.queue_focus.before_non_archived_count = summary.portfolio_before_actions.filter(
    (card) => !card.archived,
  ).length;
  await page.screenshot({
    path: path.join(screensDir, "rc72_01_portfolio_before_shortcuts.png"),
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

  await setBatchSelection(page, summary.session_a.session_id, true);
  await setBatchSelection(page, summary.session_b.session_id, true);
  await runBatchAction(page, "session-portfolio-batch-pin");
  summary.batch_actions.batch_pin_worked = true;
  summary.portfolio_after_batch_pin = await readPortfolioCards(page);
  await page.screenshot({
    path: path.join(screensDir, "rc72_02_batch_pin_selection.png"),
    fullPage: true,
  });

  const pinnedSessionA = summary.portfolio_after_batch_pin.find(
    (card) => card.session_id === summary.session_a.session_id,
  );
  const pinnedSessionB = summary.portfolio_after_batch_pin.find(
    (card) => card.session_id === summary.session_b.session_id,
  );
  if (!pinnedSessionA?.pinned || !pinnedSessionB?.pinned) {
    throw new Error("Batch pin did not apply to the selected portfolio sessions.");
  }

  await setBatchSelection(page, summary.session_a.session_id, true);
  await runBatchAction(page, "session-portfolio-batch-archive");
  summary.batch_actions.batch_archive_worked = true;
  summary.portfolio_after_batch_archive = await readPortfolioCards(page);
  summary.queue_focus.after_archive_non_archived_count = summary.portfolio_after_batch_archive.filter(
    (card) => !card.archived,
  ).length;
  summary.queue_focus.archived_count_after_archive = summary.portfolio_after_batch_archive.filter(
    (card) => card.archived,
  ).length;
  await page.screenshot({
    path: path.join(screensDir, "rc72_03_batch_archive_history.png"),
    fullPage: true,
  });

  const archivedSessionA = summary.portfolio_after_batch_archive.find(
    (card) => card.session_id === summary.session_a.session_id,
  );
  const currentSessionBAfterArchive = summary.portfolio_after_batch_archive.find(
    (card) => card.session_id === summary.session_b.session_id,
  );
  if (!archivedSessionA || archivedSessionA.lifecycle_section !== "archived") {
    throw new Error("Completed session did not move into the archived lifecycle section.");
  }
  if (!currentSessionBAfterArchive || currentSessionBAfterArchive.lifecycle_section !== "active") {
    throw new Error("Current blocking session did not remain in the active queue after archive.");
  }

  const currentBlockingLocator = page.locator(
    `[data-testid="session-portfolio-card"][data-session-id="${summary.session_b.session_id}"]`,
  );
  summary.shortcut_actions.blocker_shortcut_label = String(
    (await currentBlockingLocator.locator('[data-testid="session-portfolio-card-open"]').innerText()) || "",
  ).trim();
  await currentBlockingLocator.locator('[data-testid="session-portfolio-card-open"]').click();
  await page.waitForURL("**/shell/workspace**", { timeout: 180000 });
  await waitForCondition(async () => {
    const focusedBlocking = await page.locator('[data-testid="blocking-attention-item"][data-focused-target="true"]').count();
    const focusedPacket = await page.locator('[data-testid="attention-packet"][data-focused-target="true"]').count();
    return focusedBlocking > 0 || focusedPacket > 0;
  }, 180000, "Timed out waiting for the blocking queue jump to focus the exact packet/action.");
  summary.shortcut_actions.blocker_shortcut_worked = true;
  await page.screenshot({
    path: path.join(screensDir, "rc72_04_queue_shortcut_to_blocker.png"),
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
    path: path.join(screensDir, "rc72_05_session_after_continue.png"),
    fullPage: true,
  });

  await page.goto(`${baseUrl}/shell`, { waitUntil: "domcontentloaded", timeout: 180000 });
  summary.portfolio_after_return = await waitForPortfolio(page);
  await page.screenshot({
    path: path.join(screensDir, "rc72_06_portfolio_after_return.png"),
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

  writeJson(portfolioShortcutSummaryJsonPath, {
    session_a: summary.session_a,
    session_b: summary.session_b,
    portfolio_before_actions: summary.portfolio_before_actions,
    portfolio_after_batch_pin: summary.portfolio_after_batch_pin,
    portfolio_after_batch_archive: summary.portfolio_after_batch_archive,
    portfolio_after_return: summary.portfolio_after_return,
    shortcut_actions: summary.shortcut_actions,
  });
  writeText(
    portfolioShortcutSummaryMdPath,
    [
      "# portfolio action shortcuts summary",
      "",
      `- blocking session: \`${summary.session_b.session_id || "<none>"}\``,
      `- direct shortcut label: \`${summary.shortcut_actions.blocker_shortcut_label || "<none>"}\``,
      `- blocker shortcut worked: \`${summary.shortcut_actions.blocker_shortcut_worked}\``,
      `- same-session preserved after queue action: \`${summary.same_session_preserved}\``,
      "",
    ].join("\n"),
  );
  writeJson(batchTriageSummaryJsonPath, {
    batch_pin_selection: summary.portfolio_after_batch_pin,
    batch_archive_selection: summary.portfolio_after_batch_archive,
    batch_actions: summary.batch_actions,
    archived_entry: archivedSessionA,
    queue_focus: summary.queue_focus,
  });
  writeText(
    batchTriageSummaryMdPath,
    [
      "# bounded batch triage summary",
      "",
      `- batch pin worked: \`${summary.batch_actions.batch_pin_worked}\``,
      `- batch archive worked: \`${summary.batch_actions.batch_archive_worked}\``,
      `- archived after batch archive: \`${archivedSessionA?.archived || false}\``,
      `- active queue count before archive: \`${summary.queue_focus.before_non_archived_count}\``,
      `- non-archived queue count after archive: \`${summary.queue_focus.after_archive_non_archived_count}\``,
      "",
    ].join("\n"),
  );
  writeJson(queueFocusAfterActionsPath, {
    before_actions: summary.portfolio_before_actions,
    after_batch_pin: summary.portfolio_after_batch_pin,
    after_batch_archive: summary.portfolio_after_batch_archive,
    after_return: summary.portfolio_after_return,
    queue_focus: summary.queue_focus,
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
      path: path.join(screensDir, "rc72_zz_failure.png"),
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
      "# rc72 operator journey",
      "",
      `- success: \`${summary.success}\``,
      `- blocking session: \`${summary.session_b.session_id || "<none>"}\``,
      `- archived session: \`${summary.session_a.session_id || "<none>"}\``,
      `- batch pin worked: \`${summary.batch_actions.batch_pin_worked}\``,
      `- batch archive worked: \`${summary.batch_actions.batch_archive_worked}\``,
      `- blocker shortcut worked: \`${summary.shortcut_actions.blocker_shortcut_worked}\``,
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

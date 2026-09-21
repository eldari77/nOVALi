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

function loadJsonFile(targetPath, fallback = null) {
  try {
    return JSON.parse(fs.readFileSync(targetPath, "utf8"));
  } catch (error) {
    if (error?.code === "ENOENT") {
      return fallback;
    }
    throw error;
  }
}

async function safeResponseJson(response) {
  try {
    const text = await response.text();
    return JSON.parse(text || "{}");
  } catch {
    return {};
  }
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

async function openDirectiveModal(page) {
  await page.getByRole("button", { name: "Load Directive" }).click();
  await page.getByRole("heading", { name: "Directive and trusted-source load" }).waitFor({ timeout: 60000 });
}

async function validateTrustedSource(page, key) {
  await page.getByLabel("API credential").fill(key);
  const validateResponsePromise = page.waitForResponse(
    (resp) => resp.url().includes("/shell/api/trusted-source/validate") && resp.request().method() === "POST",
    { timeout: 180000 },
  );
  await page.getByRole("button", { name: "Validate Trusted Source" }).click();
  const validateResponse = await validateResponsePromise;
  const validatePayload = await safeResponseJson(validateResponse);
  await page.getByLabel("API credential").fill("");
  return {
    status: validateResponse.status(),
    ok: validatePayload.ok === true,
    headline: String(validatePayload.headline || validatePayload.message || ""),
  };
}

async function selectDirective(page, directivePath) {
  await page.getByLabel("Directive path").fill(directivePath);
  const responsePromise = page.waitForResponse(
    (resp) => resp.url().includes("/shell/api/directive/select") && resp.request().method() === "POST",
    { timeout: 180000 },
  );
  await page.getByRole("button", { name: "Select directive" }).click();
  const response = await responsePromise;
  return {
    status: response.status(),
    payload: await safeResponseJson(response),
  };
}

async function startSeededWorkspace(page, request, baseUrl, directivePath, { validateKey = "" } = {}) {
  await waitForShell(page, baseUrl);
  await openDirectiveModal(page);
  let validation = null;
  if (validateKey) {
    validation = await validateTrustedSource(page, validateKey);
  }
  const directiveSelection = await selectDirective(page, directivePath);
  await page.getByRole("button", { name: "Close" }).click();

  await waitForCondition(
    async () => page.getByRole("button", { name: "Bootstrap Initialization" }).isEnabled(),
    120000,
    "Timed out waiting for Bootstrap Initialization to become enabled.",
  );
  const bootstrapResponsePromise = page.waitForResponse(
    (resp) => resp.url().includes("/shell/api/bootstrap/start") && resp.request().method() === "POST",
    { timeout: 240000 },
  );
  await page.getByRole("button", { name: "Bootstrap Initialization" }).click();
  const bootstrapResponse = await bootstrapResponsePromise;
  const bootstrapPayload = await safeResponseJson(bootstrapResponse);

  const prepareButton = page.getByRole("button", { name: "Prepare governed execution" });
  if ((await prepareButton.count()) > 0 && (await prepareButton.isVisible().catch(() => false))) {
    const prepareResponsePromise = page.waitForResponse(
      (resp) => resp.url().includes("/shell/api/governed/prepare") && resp.request().method() === "POST",
      { timeout: 240000 },
    );
    await prepareButton.click();
    await safeResponseJson(await prepareResponsePromise);
  }

  await waitForCondition(
    async () => page.getByRole("button", { name: "Governed Execution Run" }).isEnabled(),
    180000,
    "Timed out waiting for Governed Execution Run to become enabled.",
  );
  const governedResponsePromise = page.waitForResponse(
    (resp) => resp.url().includes("/shell/api/governed/start") && resp.request().method() === "POST",
    { timeout: 420000 },
  );
  await page.getByRole("button", { name: "Governed Execution Run" }).click();
  const governedResponse = await governedResponsePromise;
  const governedPayload = await safeResponseJson(governedResponse);
  await page.waitForURL("**/shell/workspace**", { timeout: 480000 });
  await page.getByRole("heading", { name: "Operator Workspace" }).waitFor({ timeout: 120000 });

  const longRunState = await waitForCondition(async () => {
    const result = await fetchJson(request, "/long-run-state", baseUrl);
    const sessionId = String(result.json?.long_run?.session_id || "").trim();
    return result.status === 200 && sessionId ? result.json : null;
  }, 180000, "Timed out waiting for long-run state after governed start.");

  return {
    validation,
    directive_selection: directiveSelection,
    bootstrap: { status: bootstrapResponse.status(), ok: bootstrapPayload.ok === true },
    governed_start: { status: governedResponse.status(), ok: governedPayload.ok === true },
    long_run_state: longRunState,
  };
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
  }, 180000, "Timed out waiting for bootstrap initialization to become launch-ready after directive selection.");

  const bootstrap = await postJson(request, "/bootstrap/start", baseUrl, {
    directive_path: directivePath,
  }, { timeout: 240000 });
  if (!bootstrap.ok || bootstrap.json?.ok !== true) {
    throw new Error(`Bootstrap start failed for ${directivePath}`);
  }

  const prepare = await postJson(request, "/governed/prepare", baseUrl, {
    directive_path: directivePath,
  }, { timeout: 240000 });
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

  const governedStart = await postJson(request, "/governed/start", baseUrl, {
    directive_path: directivePath,
  }, { timeout: 420000 });
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

function currentBlockingBucket(queueBucket) {
  return [
    "new_blocking_now",
    "stale_escalated_blocking",
    "seen_unresolved_blocking",
    "acknowledged_unresolved_blocking",
  ].includes(String(queueBucket || "").trim());
}

async function readPortfolioCards(page) {
  return await page.locator('[data-testid="session-portfolio-card"]').evaluateAll((nodes) =>
    nodes.map((node) => ({
      session_id: node.getAttribute("data-session-id") || "",
      queue_bucket: node.getAttribute("data-queue-bucket") || "",
      current_session: node.getAttribute("data-current-session") === "true",
      text: (node.textContent || "").trim(),
    })),
  );
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

async function clickPrimaryAction(page) {
  const button = page.locator('[data-testid="long-run-primary-cta"]');
  await button.waitFor({ timeout: 120000 });
  await button.click();
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
      operator_note: "rc70 packaged proof approval",
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

const artifactRoot = readArg("--artifact-root");
const baseUrl = readArg("--base-url", "http://127.0.0.1:8787");
const directivePath = readArg("--directive-path");
const keyFile = readArg("--key-file");

if (!artifactRoot || !directivePath) {
  throw new Error("Missing required args. Expected --artifact-root and --directive-path.");
}

const screensDir = path.join(artifactRoot, "screens");
fs.mkdirSync(screensDir, { recursive: true });

const key = keyFile && fs.existsSync(keyFile) ? fs.readFileSync(keyFile, "utf8").trim() : "";
const clonedDirectivePath = path.join(
  path.dirname(directivePath),
  `${path.basename(directivePath, ".json")}_rc70_clone.json`,
);
const benchmarkDirectivePath = path.join(
  path.resolve(path.dirname(directivePath), ".."),
  "manual_acceptance_samples",
  "successor_package_readiness_benchmark_directive.json",
);
const baseDirectivePayload = loadJsonFile(directivePath, {});
const clonedDirectivePayload =
  baseDirectivePayload && typeof baseDirectivePayload === "object"
    ? JSON.parse(JSON.stringify(baseDirectivePayload))
    : {};
const originalDirectiveId = String(clonedDirectivePayload?.directive_spec?.directive_id || "").trim();
if (clonedDirectivePayload?.directive_spec && originalDirectiveId) {
  clonedDirectivePayload.directive_spec.directive_id = `${originalDirectiveId}_rc70_clone`;
  const originalBucketId = String(clonedDirectivePayload?.directive_spec?.bucket_spec?.bucket_id || "").trim();
  if (originalBucketId) {
    clonedDirectivePayload.directive_spec.bucket_spec.bucket_id = `${originalBucketId}_rc70_clone`;
  }
}
writeJson(clonedDirectivePath, clonedDirectivePayload);

const runSummaryPath = path.join(artifactRoot, "rc70_operator_journey.json");
const runMarkdownPath = path.join(artifactRoot, "rc70_operator_journey.md");
const sessionPortfolioSummaryJsonPath = path.join(artifactRoot, "session_portfolio_summary.json");
const sessionPortfolioSummaryMdPath = path.join(artifactRoot, "session_portfolio_summary.md");
const crossSessionQueueSummaryJsonPath = path.join(artifactRoot, "cross_session_queue_summary.json");
const crossSessionQueueSummaryMdPath = path.join(artifactRoot, "cross_session_queue_summary.md");
const portfolioPriorityMatrixPath = path.join(artifactRoot, "portfolio_priority_matrix.json");
const actionableSessionJumpSummaryPath = path.join(artifactRoot, "actionable_session_jump_summary.json");
const sameSessionPortfolioIdentityPath = path.join(artifactRoot, "same_session_portfolio_identity.json");
const packagedRouteValidationPath = path.join(artifactRoot, "packaged_route_validation.json");
const sessionLineageAuditJsonPath = path.join(artifactRoot, "session_lineage_audit.json");
const sessionLineageAuditMdPath = path.join(artifactRoot, "session_lineage_audit.md");
const portfolioMaterializationSummaryJsonPath = path.join(
  artifactRoot,
  "portfolio_materialization_summary.json",
);
const portfolioMaterializationSummaryMdPath = path.join(
  artifactRoot,
  "portfolio_materialization_summary.md",
);
const sessionIdentityMatrixPath = path.join(artifactRoot, "session_identity_matrix.json");
const queuePriorityAfterSelectionPath = path.join(
  artifactRoot,
  "queue_priority_after_selection.json",
);

const summary = {
  success: false,
  base_url: baseUrl,
  directive_path_used: directivePath,
  cloned_directive_path_used: clonedDirectivePath,
  validation: null,
  session_a: {},
  session_b: {},
  portfolio_before_action: [],
  portfolio_after_action: [],
  portfolio_recommendation_text: "",
  portfolio_queue_visible: false,
  portfolio_actionable_jump_worked: false,
  portfolio_current_vs_historical_clear: false,
  session_b_same_session_preserved: false,
  session_b_cycle_delta: 0,
  session_b_checkpoint_delta: 0,
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
  const sessionA = await startSeededWorkspaceViaApi(page, request, baseUrl, benchmarkDirectivePath);
  const sessionACompleted = await advanceCurrentSessionToCompletedHistory(page, request, baseUrl);
  summary.validation = key ? { skipped: true, reason: "rc70 proof did not require trusted-source validation." } : null;
  summary.session_a = {
    session_id: String(sessionACompleted?.long_run?.session_id || sessionA.long_run_state?.long_run?.session_id || ""),
    directive_id: String(sessionACompleted?.long_run?.directive_id || sessionA.long_run_state?.long_run?.directive_id || ""),
    workspace_id: String(sessionACompleted?.long_run?.workspace_id || sessionA.long_run_state?.long_run?.workspace_id || ""),
    workspace_root: String(sessionACompleted?.long_run?.workspace_root || sessionA.long_run_state?.long_run?.workspace_root || ""),
    lifecycle_state: String(sessionACompleted?.long_run?.lifecycle_state || sessionA.long_run_state?.long_run?.lifecycle_state || ""),
    current_cycle: Number(sessionACompleted?.long_run?.current_cycle || sessionA.long_run_state?.long_run?.current_cycle || 0),
    checkpoint_count: Number(sessionACompleted?.long_run?.checkpoint_count || sessionA.long_run_state?.long_run?.checkpoint_count || 0),
    primary_cta: String(sessionACompleted?.operator_guidance?.primary_cta?.label || sessionA.long_run_state?.operator_guidance?.primary_cta?.label || ""),
    queue_bucket_hint: String(sessionACompleted?.operator_guidance?.attention_signal?.severity || sessionA.long_run_state?.operator_guidance?.attention_signal?.severity || ""),
  };
  pushStep("session_a_seeded", summary.session_a);
  await page.screenshot({
    path: path.join(screensDir, "rc70_01_session_a_workspace.png"),
    fullPage: true,
  });

  await page.goto(`${baseUrl}/shell`, { waitUntil: "domcontentloaded", timeout: 180000 });

  const sessionBSeed = await startSeededWorkspaceViaApi(page, request, baseUrl, directivePath, {
    settleAfterStart: false,
    overrideGovernedProfile: {
      governed_execution_mode: "multi_cycle",
      max_cycles_per_invocation: "2",
      max_total_cycles: "4",
    },
  });
  const sessionBInitialState = await ensureBlockingCurrentSession(page, request, baseUrl);
  summary.session_b = {
    session_id: String(sessionBInitialState?.long_run?.session_id || ""),
    directive_id: String(sessionBInitialState?.long_run?.directive_id || ""),
    workspace_id: String(sessionBInitialState?.long_run?.workspace_id || ""),
    workspace_root: String(sessionBInitialState?.long_run?.workspace_root || ""),
    lifecycle_state: String(sessionBInitialState?.long_run?.lifecycle_state || ""),
    current_cycle: Number(sessionBInitialState?.long_run?.current_cycle || 0),
    checkpoint_count: Number(sessionBInitialState?.long_run?.checkpoint_count || 0),
    primary_cta: String(sessionBInitialState?.operator_guidance?.primary_cta?.label || ""),
    blocking_count: Number(sessionBInitialState?.operator_guidance?.attention_inbox?.blocking_count || 0),
    directive_select_status: Number(sessionBSeed.directive_selection?.status || 0),
    bootstrap_status: Number(sessionBSeed.bootstrap?.status || 0),
    governed_prepare_status: Number(sessionBSeed.governed_prepare?.status || 0),
    governed_start_status: Number(sessionBSeed.governed_start?.status || 0),
  };
  pushStep("session_b_blocking_ready", summary.session_b);
  if (summary.session_a.session_id === summary.session_b.session_id) {
    throw new Error("Session portfolio proof did not create a second distinct session id.");
  }
  await page.screenshot({
    path: path.join(screensDir, "rc70_02_session_b_workspace_before_queue.png"),
    fullPage: true,
  });

  await page.goto(`${baseUrl}/shell`, { waitUntil: "domcontentloaded", timeout: 180000 });
  const portfolioCards = await waitForPortfolio(page);
  summary.portfolio_queue_visible = true;
  summary.portfolio_before_action = portfolioCards;
  summary.portfolio_current_vs_historical_clear =
    portfolioCards.some((card) => card.current_session) &&
    portfolioCards.some((card) => !card.current_session);
  summary.portfolio_recommendation_text = await page
    .locator('[data-testid="session-portfolio-recommendation"]')
    .textContent()
    .catch(() => "");
  await page.screenshot({
    path: path.join(screensDir, "rc70_03_portfolio_queue.png"),
    fullPage: true,
  });

  const topCard = portfolioCards[0];
  const secondCard = portfolioCards[1] || null;
  if (!currentBlockingBucket(topCard.queue_bucket)) {
    throw new Error(`Top portfolio card was not blocking. Saw ${topCard.queue_bucket || "<none>"}.`);
  }
  if (!secondCard || currentBlockingBucket(secondCard.queue_bucket)) {
    throw new Error("Portfolio queue did not surface a distinct second recent/active session state.");
  }

  const topCardLocator = page
    .locator('[data-testid="session-portfolio-card"]')
    .filter({ has: page.locator(`[data-testid="session-portfolio-card-open"]`) })
    .first();
  await topCardLocator.locator('[data-testid="session-portfolio-card-open"]').click();
  await page.waitForURL("**/shell/workspace**", { timeout: 180000 });

  await waitForCondition(async () => {
    const focusedBlocking = await page.locator('[data-testid="blocking-attention-item"][data-focused-target="true"]').count();
    const focusedPacket = await page.locator('[data-testid="attention-packet"][data-focused-target="true"]').count();
    return focusedBlocking > 0 || focusedPacket > 0;
  }, 180000, "Timed out waiting for queue jump to focus the current blocking packet/action.");
  summary.portfolio_actionable_jump_worked = true;
  await page.screenshot({
    path: path.join(screensDir, "rc70_04_queue_jump_to_blocker.png"),
    fullPage: true,
  });

  const beforeQueueAction = await fetchJson(request, "/long-run-state", baseUrl);
  const postQueueApproval = await approveCurrentReviewAction(request, baseUrl);
  const afterQueueAction = await continueSameSession(request, baseUrl, postQueueApproval);

  summary.session_b_same_session_preserved =
    String(beforeQueueAction.json?.long_run?.session_id || "") ===
    String(afterQueueAction?.long_run?.session_id || "");
  summary.session_b_cycle_delta =
    Number(afterQueueAction?.long_run?.current_cycle || 0) -
    Number(beforeQueueAction.json?.long_run?.current_cycle || 0);
  summary.session_b_checkpoint_delta =
    Number(afterQueueAction?.long_run?.checkpoint_count || 0) -
    Number(beforeQueueAction.json?.long_run?.checkpoint_count || 0);
  await page.screenshot({
    path: path.join(screensDir, "rc70_05_session_b_after_continue.png"),
    fullPage: true,
  });

  await page.goto(`${baseUrl}/shell`, { waitUntil: "domcontentloaded", timeout: 180000 });
  summary.portfolio_after_action = await waitForPortfolio(page);
  await page.screenshot({
    path: path.join(screensDir, "rc70_06_portfolio_after_action.png"),
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

  writeJson(sessionPortfolioSummaryJsonPath, {
    session_a: summary.session_a,
    session_b: summary.session_b,
    queue_visible: summary.portfolio_queue_visible,
    recommendation: summary.portfolio_recommendation_text,
    portfolio_before_action: summary.portfolio_before_action,
    portfolio_after_action: summary.portfolio_after_action,
  });
  writeText(
    sessionPortfolioSummaryMdPath,
    [
      "# session portfolio summary",
      "",
      `- session A: \`${summary.session_a.session_id || "<none>"}\``,
      `- session B: \`${summary.session_b.session_id || "<none>"}\``,
      `- queue visible: \`${summary.portfolio_queue_visible}\``,
      `- current vs historical clear: \`${summary.portfolio_current_vs_historical_clear}\``,
      `- recommendation: ${summary.portfolio_recommendation_text || "<none>"}`,
      "",
    ].join("\n"),
  );
  writeJson(crossSessionQueueSummaryJsonPath, {
    cards_before_action: summary.portfolio_before_action,
    cards_after_action: summary.portfolio_after_action,
    actionable_jump_worked: summary.portfolio_actionable_jump_worked,
  });
  writeText(
    crossSessionQueueSummaryMdPath,
    [
      "# cross-session queue summary",
      "",
      `- top-priority bucket before action: \`${summary.portfolio_before_action[0]?.queue_bucket || "<none>"}\``,
      `- second session bucket before action: \`${summary.portfolio_before_action[1]?.queue_bucket || "<none>"}\``,
      `- actionable jump worked: \`${summary.portfolio_actionable_jump_worked}\``,
      "",
    ].join("\n"),
  );
  writeJson(portfolioPriorityMatrixPath, {
    before_action: summary.portfolio_before_action,
    after_action: summary.portfolio_after_action,
  });
  writeJson(sessionLineageAuditJsonPath, {
    directive_path_used: directivePath,
    benchmark_directive_path_used: benchmarkDirectivePath,
    session_a: summary.session_a,
    session_b: summary.session_b,
    distinct_session_ids:
      String(summary.session_a.session_id || "") !== String(summary.session_b.session_id || ""),
    same_workspace_lineage:
      String(summary.session_a.workspace_id || "") === String(summary.session_b.workspace_id || "") &&
      String(summary.session_a.workspace_root || "") === String(summary.session_b.workspace_root || ""),
  });
  writeText(
    sessionLineageAuditMdPath,
    [
      "# session lineage audit",
      "",
      `- session A id: \`${summary.session_a.session_id || "<none>"}\``,
      `- session A workspace: \`${summary.session_a.workspace_id || "<none>"} -> ${summary.session_a.workspace_root || "<none>"}\``,
      `- session B id: \`${summary.session_b.session_id || "<none>"}\``,
      `- session B workspace: \`${summary.session_b.workspace_id || "<none>"} -> ${summary.session_b.workspace_root || "<none>"}\``,
      `- distinct session ids: \`${String(summary.session_a.session_id || "") !== String(summary.session_b.session_id || "")}\``,
      "",
    ].join("\n"),
  );
  writeJson(portfolioMaterializationSummaryJsonPath, {
    queue_visible: summary.portfolio_queue_visible,
    recommendation: summary.portfolio_recommendation_text,
    cards_before_action: summary.portfolio_before_action,
    cards_after_action: summary.portfolio_after_action,
    actionable_jump_worked: summary.portfolio_actionable_jump_worked,
    current_vs_historical_clear: summary.portfolio_current_vs_historical_clear,
  });
  writeText(
    portfolioMaterializationSummaryMdPath,
    [
      "# portfolio materialization summary",
      "",
      `- queue visible: \`${summary.portfolio_queue_visible}\``,
      `- recommendation: ${summary.portfolio_recommendation_text || "<none>"}`,
      `- top bucket before action: \`${summary.portfolio_before_action[0]?.queue_bucket || "<none>"}\``,
      `- second bucket before action: \`${summary.portfolio_before_action[1]?.queue_bucket || "<none>"}\``,
      `- actionable jump worked: \`${summary.portfolio_actionable_jump_worked}\``,
      "",
    ].join("\n"),
  );
  writeJson(sessionIdentityMatrixPath, {
    session_a: summary.session_a,
    session_b: summary.session_b,
    distinct_session_ids:
      String(summary.session_a.session_id || "") !== String(summary.session_b.session_id || ""),
    distinct_workspace_ids:
      String(summary.session_a.workspace_id || "") !== String(summary.session_b.workspace_id || ""),
  });
  writeJson(queuePriorityAfterSelectionPath, {
    before_action: summary.portfolio_before_action,
    after_action: summary.portfolio_after_action,
    recommendation: summary.portfolio_recommendation_text,
  });
  writeJson(actionableSessionJumpSummaryPath, {
    top_priority_session_id: summary.portfolio_before_action[0]?.session_id || "",
    top_priority_bucket: summary.portfolio_before_action[0]?.queue_bucket || "",
    actionable_jump_worked: summary.portfolio_actionable_jump_worked,
    focused_target_kind: "current_blocker",
  });
  writeJson(sameSessionPortfolioIdentityPath, {
    session_id_before_queue_action: String(beforeQueueAction.json?.long_run?.session_id || ""),
    session_id_after_queue_action: String(afterQueueAction?.long_run?.session_id || ""),
    same_session_preserved: summary.session_b_same_session_preserved,
    cycle_delta: summary.session_b_cycle_delta,
    checkpoint_delta: summary.session_b_checkpoint_delta,
  });
  writeJson(packagedRouteValidationPath, routeValidation);

  summary.success = true;
} catch (error) {
  summary.failures.push(error?.message || String(error));
  pushStep("failure", { message: error?.message || String(error) });
  try {
    await page.screenshot({
      path: path.join(screensDir, "rc70_zz_failure.png"),
      fullPage: true,
    });
  } catch {
    // Preserve failure reporting even if screenshot capture also fails.
  }
} finally {
  writeJson(runSummaryPath, summary);
  writeText(
    runMarkdownPath,
    [
      "# rc70 operator journey",
      "",
      `- success: \`${summary.success}\``,
      `- session A: \`${summary.session_a.session_id || "<none>"}\``,
      `- session B: \`${summary.session_b.session_id || "<none>"}\``,
      `- portfolio queue visible: \`${summary.portfolio_queue_visible}\``,
      `- actionable jump worked: \`${summary.portfolio_actionable_jump_worked}\``,
      `- same-session preserved after queue action: \`${summary.session_b_same_session_preserved}\``,
      `- cycle delta after queue action: \`${summary.session_b_cycle_delta}\``,
      `- checkpoint delta after queue action: \`${summary.session_b_checkpoint_delta}\``,
      summary.failures.length ? `- failures: ${summary.failures.join(" | ")}` : "- failures: none",
      "",
    ].join("\n"),
  );
  process.exitCode = summary.success ? 0 : 1;
  await browser.close();
}

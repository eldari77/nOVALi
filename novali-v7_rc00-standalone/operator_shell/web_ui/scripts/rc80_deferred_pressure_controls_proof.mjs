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

function firstNumber(text) {
  const match = String(text || "").match(/(\d+)/);
  return match ? Number(match[1]) : 0;
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
      operator_note: "rc76 packaged proof approval",
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
    return !latestPreferredAction ||
      latestPreferredAction.action_id !== preferredAction.action_id ||
      latestPreferredAction.review_item_id !== preferredAction.review_item_id
      ? latest.json
      : null;
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
  await page.locator('[data-testid="manager-digest-panel"]').waitFor({ timeout: 120000 });
  await page.locator('[data-testid="operator-queue-panel"]').waitFor({ timeout: 120000 });
  return await waitForCondition(
    async () => {
      const cards = await readPortfolioCards(page);
      return cards.length >= 3 && cards.some((card) => card.current_session) ? cards : null;
    },
    180000,
    "Timed out waiting for a populated portfolio queue with at least three truthful session cards and a marked current session.",
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

async function readManagerDigest(page) {
  const panel = page.locator('[data-testid="manager-digest-panel"]');
  await panel.waitFor({ timeout: 120000 });
  const counters = await panel.locator('[data-testid^="manager-digest-counter-"]').evaluateAll((nodes) =>
    nodes.map((node) => ({
      test_id: node.getAttribute("data-testid") || "",
      text: (node.textContent || "").trim(),
    })),
  );
  const progressItems = await panel.locator('[data-testid="manager-digest-progress-item"]').evaluateAll((nodes) =>
    nodes.map((node) => ({
      session_id: node.getAttribute("data-session-id") || "",
      text: (node.textContent || "").trim(),
    })),
  );
  return {
    headline: String((await page.locator('[data-testid="manager-digest-headline"]').innerText()) || "").trim(),
    anchor: String((await page.locator('[data-testid="manager-digest-anchor"]').innerText()) || "").trim(),
    recommended_action_label: String(
      (await page.locator('[data-testid="manager-digest-recommended-action"]').innerText()) || "",
    ).trim(),
    counters,
    progressItems,
  };
}

async function readDeferredWorkloadDigest(page) {
  const panel = page.locator('[data-testid="deferred-workload-digest-panel"]');
  await panel.waitFor({ timeout: 120000 });
  const counters = await panel.locator('[data-testid^="deferred-workload-counter-"]').evaluateAll((nodes) =>
    nodes.map((node) => ({
      test_id: node.getAttribute("data-testid") || "",
      text: (node.textContent || "").trim(),
    })),
  );
  const returnBasisItems = await panel.locator('[data-testid="deferred-workload-return-basis-item"]').evaluateAll((nodes) =>
    nodes.map((node) => ({
      basis_key: node.getAttribute("data-basis-key") || "",
      text: (node.textContent || "").trim(),
    })),
  );
  const responseItems = await panel.locator('[data-testid="deferred-workload-response-item"]').evaluateAll((nodes) =>
    nodes.map((node) => ({
      response_key: node.getAttribute("data-response-key") || "",
      text: (node.textContent || "").trim(),
    })),
  );
  return {
    headline: String((await page.locator('[data-testid="deferred-workload-digest-headline"]').innerText()) || "").trim(),
    anchor: String((await page.locator('[data-testid="deferred-workload-digest-anchor"]').innerText()) || "").trim(),
    pressure_band: String((await page.locator('[data-testid="deferred-workload-pressure-band"]').innerText()) || "").trim(),
    pressure_trend: String((await page.locator('[data-testid="deferred-workload-pressure-trend"]').innerText()) || "").trim(),
    pressure_band_detail: String((await page.locator('[data-testid="deferred-workload-pressure-band-detail"]').innerText()) || "").trim(),
    response_primary: String((await page.locator('[data-testid="deferred-workload-response-primary"]').innerText()) || "").trim(),
    response_detail: String((await page.locator('[data-testid="deferred-workload-response-detail"]').innerText()) || "").trim(),
    pressure: String((await page.locator('[data-testid="deferred-workload-digest-pressure"]').innerText()) || "").trim(),
    current_reason: String((await page.locator('[data-testid="deferred-workload-digest-current"]').innerText()) || "").trim(),
    counters,
    return_basis_items: returnBasisItems,
    response_items: responseItems,
  };
}

async function readManagerAgenda(page) {
  const panel = page.locator('[data-testid="manager-agenda-panel"]');
  await panel.waitFor({ timeout: 120000 });
  const currentAction = panel.locator('[data-testid="manager-agenda-current-action"]');
  const currentDeferNextCheck = panel.locator('[data-testid="manager-agenda-current-defer-next-check"]');
  const currentDeferUntilReopen = panel.locator('[data-testid="manager-agenda-current-defer-until-reopen"]');
  const nextAction = panel.locator('[data-testid="manager-agenda-next-action"]');
  const nextDeferNextCheck = panel.locator('[data-testid="manager-agenda-next-defer-next-check"]');
  const nextDeferUntilReopen = panel.locator('[data-testid="manager-agenda-next-defer-until-reopen"]');
  const deferredReopen = panel.locator('[data-testid="manager-agenda-deferred-reopen"]');
  const throughput = panel.locator('[data-testid="manager-agenda-throughput"]');
  const deferredQueueItems = await panel.locator('[data-testid="manager-deferred-queue-item"]').evaluateAll((nodes) =>
    nodes.map((node) => ({
      session_id: node.getAttribute("data-session-id") || "",
      text: (node.textContent || "").trim(),
    })),
  );
  const dueQueueItems = await panel.locator('[data-testid="manager-due-queue-item"]').evaluateAll((nodes) =>
    nodes.map((node) => ({
      session_id: node.getAttribute("data-session-id") || "",
      text: (node.textContent || "").trim(),
    })),
  );
  const reopenedQueueItems = await panel
    .locator('[data-testid="manager-reopened-queue-item"]')
    .evaluateAll((nodes) =>
      nodes.map((node) => ({
        session_id: node.getAttribute("data-session-id") || "",
        text: (node.textContent || "").trim(),
      })),
    );
  return {
    anchor: String((await page.locator('[data-testid="manager-agenda-anchor"]').innerText()) || "").trim(),
    current: String((await page.locator('[data-testid="manager-agenda-current"]').innerText()) || "").trim(),
    next: String((await page.locator('[data-testid="manager-agenda-next"]').innerText()) || "").trim(),
    completed: String((await page.locator('[data-testid="manager-agenda-completed"]').innerText()) || "").trim(),
    overdue: String((await page.locator('[data-testid="manager-agenda-overdue"]').innerText()) || "").trim(),
    due: String((await page.locator('[data-testid="manager-agenda-due"]').innerText()) || "").trim(),
    deferred: String((await page.locator('[data-testid="manager-agenda-deferred"]').innerText()) || "").trim(),
    reopened: String((await page.locator('[data-testid="manager-agenda-reopened"]').innerText()) || "").trim(),
    throughput:
      (await throughput.count()) > 0 ? String((await throughput.innerText()) || "").trim() : "",
    deferred_queue_items: deferredQueueItems,
    due_queue_items: dueQueueItems,
    reopened_queue_items: reopenedQueueItems,
    current_action_label:
      (await currentAction.count()) > 0
        ? String((await currentAction.first().innerText()) || "").trim()
        : "",
    current_defer_next_check_label:
      (await currentDeferNextCheck.count()) > 0
        ? String((await currentDeferNextCheck.first().innerText()) || "").trim()
        : "",
    current_defer_until_reopen_label:
      (await currentDeferUntilReopen.count()) > 0
        ? String((await currentDeferUntilReopen.first().innerText()) || "").trim()
        : "",
    next_action_label:
      (await nextAction.count()) > 0
        ? String((await nextAction.first().innerText()) || "").trim()
        : "",
    next_defer_next_check_label:
      (await nextDeferNextCheck.count()) > 0
        ? String((await nextDeferNextCheck.first().innerText()) || "").trim()
        : "",
    next_defer_until_reopen_label:
      (await nextDeferUntilReopen.count()) > 0
        ? String((await nextDeferUntilReopen.first().innerText()) || "").trim()
        : "",
    deferred_reopen_label:
      (await deferredReopen.count()) > 0
        ? String((await deferredReopen.first().innerText()) || "").trim()
        : "",
    counts: {
      new_since_last_check: String((await page.locator('[data-testid="manager-agenda-count-new_since_last_check"]').innerText()) || "").trim(),
      still_pending_from_before_last_check: String((await page.locator('[data-testid="manager-agenda-count-still_pending_from_before_last_check"]').innerText()) || "").trim(),
      overdue_manager_items: String((await page.locator('[data-testid="manager-agenda-count-overdue_manager_items"]').innerText()) || "").trim(),
      completed_since_last_check: String((await page.locator('[data-testid="manager-agenda-count-completed_since_last_check"]').innerText()) || "").trim(),
      due_now: String((await page.locator('[data-testid="manager-agenda-count-due_now"]').innerText()) || "").trim(),
      reopened_items: String((await page.locator('[data-testid="manager-agenda-count-reopened_items"]').innerText()) || "").trim(),
      deferred_items: String((await page.locator('[data-testid="manager-agenda-count-deferred_items"]').innerText()) || "").trim(),
      due_returned_since_last_check: String((await page.locator('[data-testid="manager-agenda-count-due_returned_since_last_check"]').innerText()) || "").trim(),
      reopened_since_last_check: String((await page.locator('[data-testid="manager-agenda-count-reopened_since_last_check"]').innerText()) || "").trim(),
    },
  };
}

async function readOperatorQueue(page) {
  const panel = page.locator('[data-testid="operator-queue-panel"]');
  await panel.waitFor({ timeout: 120000 });
  const sections = await panel.locator('[data-testid="operator-queue-section"]').evaluateAll((nodes) =>
    nodes.map((node) => ({
      key: node.getAttribute("data-queue-group") || "",
      text: (node.textContent || "").trim(),
    })),
  );
  const cards = await panel.locator('[data-testid="operator-queue-card"]').evaluateAll((nodes) =>
    nodes.map((node) => ({
      session_id: node.getAttribute("data-session-id") || "",
      queue_group: node.getAttribute("data-queue-group") || "",
      text: (node.textContent || "").trim(),
    })),
  );
  return { sections, cards };
}

async function clickQueueAction(page, sessionId) {
  const card = page.locator(`[data-testid="operator-queue-card"][data-session-id="${sessionId}"]`);
  await card.waitFor({ timeout: 120000 });
  const button = card.locator('[data-testid="operator-queue-card-action"]');
  await button.waitFor({ timeout: 120000 });
  const label = String((await button.innerText()) || "").trim();
  await button.click();
  return label;
}

async function clickManagerAgendaCurrentAction(page) {
  const button = page.locator('[data-testid="manager-agenda-current-action"]');
  await button.waitFor({ timeout: 120000 });
  const label = String((await button.innerText()) || "").trim();
  await button.click();
  return label;
}

async function clickManagerAgendaCurrentDefer(page, basis = "next_manager_check") {
  const testId =
    basis === "until_reopen"
      ? "manager-agenda-current-defer-until-reopen"
      : "manager-agenda-current-defer-next-check";
  const button = page.locator(`[data-testid="${testId}"]`);
  await button.waitFor({ timeout: 120000 });
  const label = String((await button.innerText()) || "").trim();
  await button.click();
  return label;
}

async function clickManagerAgendaNextDefer(page, basis = "next_manager_check") {
  const testId =
    basis === "until_reopen"
      ? "manager-agenda-next-defer-until-reopen"
      : "manager-agenda-next-defer-next-check";
  const button = page.locator(`[data-testid="${testId}"]`);
  await button.waitFor({ timeout: 120000 });
  const label = String((await button.innerText()) || "").trim();
  await button.click();
  return label;
}

async function clickManagerAgendaDeferredReopen(page, sessionId) {
  const scope = sessionId
    ? page.locator(`[data-testid="manager-deferred-queue-item"][data-session-id="${sessionId}"]`)
    : page.locator('[data-testid="manager-deferred-queue-item"]').first();
  const button = scope.locator('[data-testid="manager-agenda-deferred-reopen"]');
  await button.waitFor({ timeout: 120000 });
  const label = String((await button.innerText()) || "").trim();
  await button.click();
  return label;
}

async function markDigestChecked(page) {
  const button = page.locator('[data-testid="manager-digest-mark-checked"]');
  await button.waitFor({ timeout: 120000 });
  await button.click();
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
const secondaryBenchmarkDirectivePath = path.join(
  path.resolve(path.dirname(directivePath), ".."),
  "manual_acceptance_samples",
  "rc80_secondary_successor_package_readiness_benchmark_directive.json",
);
if (!fs.existsSync(secondaryBenchmarkDirectivePath)) {
  const benchmarkDirective = JSON.parse(fs.readFileSync(benchmarkDirectivePath, "utf-8"));
  benchmarkDirective.directive_spec = benchmarkDirective.directive_spec || {};
  benchmarkDirective.directive_spec.directive_id =
    "directive_novali_v6_successor_package_readiness_benchmark_v1_rc80_secondary";
  benchmarkDirective.directive_spec.bucket_spec = benchmarkDirective.directive_spec.bucket_spec || {};
  benchmarkDirective.directive_spec.bucket_spec.bucket_id =
    "bucket_novali_v6_successor_package_readiness_benchmark_v1_rc80_secondary";
  fs.writeFileSync(
    secondaryBenchmarkDirectivePath,
    JSON.stringify(benchmarkDirective, null, 2),
  );
}
const screensDir = path.join(artifactRoot, "screens");
fs.mkdirSync(screensDir, { recursive: true });

const runSummaryPath = path.join(artifactRoot, "rc80_operator_journey.json");
const runMarkdownPath = path.join(artifactRoot, "rc80_operator_journey.md");
const managerDigestAckSummaryJsonPath = path.join(artifactRoot, "deferred_pressure_controls_summary.json");
const managerDigestAckSummaryMdPath = path.join(artifactRoot, "deferred_pressure_controls_summary.md");
const operatorAgendaSummaryJsonPath = path.join(artifactRoot, "manager_response_policy_summary.json");
const operatorAgendaSummaryMdPath = path.join(artifactRoot, "manager_response_policy_summary.md");
const sinceLastManagerCheckDeltaPath = path.join(artifactRoot, "since_last_manager_check_delta.json");
const agendaProgressionAfterActionPath = path.join(
  artifactRoot,
  "agenda_progression_after_pressure_change.json",
);
const sameSessionPortfolioIdentityPath = path.join(artifactRoot, "same_session_portfolio_identity.json");
const packagedRouteValidationPath = path.join(artifactRoot, "packaged_route_validation.json");

const summary = {
  success: false,
  base_url: baseUrl,
  directive_path_used: directivePath,
  benchmark_directive_path_used: benchmarkDirectivePath,
  secondary_benchmark_directive_path_used: secondaryBenchmarkDirectivePath,
  session_a: {},
  session_b: {},
  session_c: {},
  portfolio_before_action: [],
  portfolio_after_return: [],
  manager_digest_before: {},
  manager_digest_checked: {},
  deferred_workload_before: {},
  deferred_workload_after_second_defer: {},
  deferred_workload_after_return: {},
  deferred_workload_after_due_return: {},
  deferred_workload_after_manual_reopen: {},
  manager_agenda_after_first_defer: {},
  manager_agenda_after_second_defer: {},
  manager_digest_after_return: {},
  manager_digest_after_due_return: {},
  manager_agenda_before: {},
  manager_agenda_after_return: {},
  manager_agenda_after_due_return: {},
  manager_agenda_after_manual_reopen: {},
  operator_queue_before: {},
  operator_queue_after_return: {},
  queue_counts_before: {},
  queue_counts_after_return: {},
  first_defer_action: {
    label: "",
    worked: false,
  },
  second_defer_action: {
    label: "",
    worked: false,
  },
  agenda_action: {
    label: "",
    worked: false,
  },
  reopen_action: {
    label: "",
    worked: false,
  },
  first_deferred_session_id: "",
  second_deferred_session_id: "",
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

  const sessionASeed = await startSeededWorkspaceViaApi(page, request, baseUrl, benchmarkDirectivePath, {
    settleAfterStart: false,
    overrideGovernedProfile: {
      governed_execution_mode: "multi_cycle",
      max_cycles_per_invocation: "2",
      max_total_cycles: "4",
    },
  });
  const sessionABlocking = await ensureBlockingCurrentSession(page, request, baseUrl);
  summary.session_a = {
    session_id: String(sessionABlocking?.long_run?.session_id || sessionASeed.long_run_state?.long_run?.session_id || ""),
    directive_id: String(sessionABlocking?.long_run?.directive_id || sessionASeed.long_run_state?.long_run?.directive_id || ""),
    workspace_id: String(sessionABlocking?.long_run?.workspace_id || sessionASeed.long_run_state?.long_run?.workspace_id || ""),
    workspace_root: String(sessionABlocking?.long_run?.workspace_root || sessionASeed.long_run_state?.long_run?.workspace_root || ""),
    lifecycle_state: String(sessionABlocking?.long_run?.lifecycle_state || sessionASeed.long_run_state?.long_run?.lifecycle_state || ""),
    current_cycle: Number(sessionABlocking?.long_run?.current_cycle || sessionASeed.long_run_state?.long_run?.current_cycle || 0),
    checkpoint_count: Number(sessionABlocking?.long_run?.checkpoint_count || sessionASeed.long_run_state?.long_run?.checkpoint_count || 0),
    primary_cta: String(sessionABlocking?.operator_guidance?.primary_cta?.label || ""),
    blocking_count: Number(sessionABlocking?.operator_guidance?.attention_inbox?.blocking_count || 0),
  };
  pushStep("session_a_blocking_ready", summary.session_a);

  await page.goto(`${baseUrl}/shell`, { waitUntil: "domcontentloaded", timeout: 180000 });

  const sessionBSeed = await startSeededWorkspaceViaApi(page, request, baseUrl, secondaryBenchmarkDirectivePath, {
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

  await page.goto(`${baseUrl}/shell`, { waitUntil: "domcontentloaded", timeout: 180000 });

  const sessionCSeed = await startSeededWorkspaceViaApi(page, request, baseUrl, directivePath, {
    settleAfterStart: false,
    overrideGovernedProfile: {
      governed_execution_mode: "multi_cycle",
      max_cycles_per_invocation: "2",
      max_total_cycles: "4",
    },
  });
  const sessionCBlocking = await ensureBlockingCurrentSession(page, request, baseUrl);
  summary.session_c = {
    session_id: String(sessionCBlocking?.long_run?.session_id || ""),
    directive_id: String(sessionCBlocking?.long_run?.directive_id || ""),
    workspace_id: String(sessionCBlocking?.long_run?.workspace_id || ""),
    workspace_root: String(sessionCBlocking?.long_run?.workspace_root || ""),
    lifecycle_state: String(sessionCBlocking?.long_run?.lifecycle_state || ""),
    current_cycle: Number(sessionCBlocking?.long_run?.current_cycle || 0),
    checkpoint_count: Number(sessionCBlocking?.long_run?.checkpoint_count || 0),
    primary_cta: String(sessionCBlocking?.operator_guidance?.primary_cta?.label || ""),
    blocking_count: Number(sessionCBlocking?.operator_guidance?.attention_inbox?.blocking_count || 0),
    directive_select_status: Number(sessionCSeed.directive_selection?.status || 0),
    bootstrap_status: Number(sessionCSeed.bootstrap?.status || 0),
    governed_prepare_status: Number(sessionCSeed.governed_prepare?.status || 0),
    governed_start_status: Number(sessionCSeed.governed_start?.status || 0),
  };
  pushStep("session_c_blocking_ready", summary.session_c);

  if (
    new Set([
      summary.session_a.session_id,
      summary.session_b.session_id,
      summary.session_c.session_id,
    ]).size !== 3
  ) {
    throw new Error("Deferred-queue proof did not produce three distinct truthful session ids.");
  }

  await page.goto(`${baseUrl}/shell`, { waitUntil: "domcontentloaded", timeout: 180000 });
  summary.portfolio_before_action = await waitForPortfolio(page);
  summary.manager_digest_before = await readManagerDigest(page);
  summary.deferred_workload_before = await readDeferredWorkloadDigest(page);
  summary.manager_agenda_before = await readManagerAgenda(page);
  summary.operator_queue_before = await readOperatorQueue(page);
  summary.queue_counts_before = {
    digest_counter_count: summary.manager_digest_before.counters.length,
    deferred_workload_counter_count: summary.deferred_workload_before.counters.length,
    deferred_return_basis_count: summary.deferred_workload_before.return_basis_items.length,
    operator_queue_section_count: summary.operator_queue_before.sections.length,
    operator_queue_card_count: summary.operator_queue_before.cards.length,
  };
  await page.screenshot({
    path: path.join(screensDir, "rc80_01_shell_digest_queue_and_deferred_workload.png"),
    fullPage: true,
  });

  const currentBlockingCard = summary.portfolio_before_action.find(
    (card) => card.session_id === summary.session_c.session_id,
  );
  const recentSecondCard = summary.portfolio_before_action.find(
    (card) => card.session_id === summary.session_a.session_id,
  );
  const recentThirdCard = summary.portfolio_before_action.find(
    (card) => card.session_id === summary.session_b.session_id,
  );
  if (!currentBlockingCard || !recentSecondCard || !recentThirdCard) {
    throw new Error("Portfolio did not expose three truthful session entries before defer ordering proof.");
  }
  if (!currentBlockingBucket(currentBlockingCard.queue_bucket)) {
    throw new Error(`Current blocking session did not lead the actionable queue. Saw ${currentBlockingCard.queue_bucket}.`);
  }
  if (!summary.manager_digest_before.headline) {
    throw new Error("Manager digest did not render a headline.");
  }
  if (!summary.deferred_workload_before.headline) {
    throw new Error("Deferred workload digest did not render a headline.");
  }
  if (!summary.manager_agenda_before.current) {
    throw new Error("Manager agenda did not render the current item summary.");
  }
  if (!summary.manager_agenda_before.throughput) {
    throw new Error("Manager agenda did not render the throughput summary.");
  }
  if (!summary.operator_queue_before.cards.some((card) => card.session_id === summary.session_c.session_id)) {
    throw new Error("Operator queue did not surface the current blocking session.");
  }

  await markDigestChecked(page);
  summary.manager_digest_checked = await readManagerDigest(page);
  await page.screenshot({
    path: path.join(screensDir, "rc80_02_digest_anchor_recorded.png"),
    fullPage: true,
  });

  summary.first_defer_action.label = await clickManagerAgendaCurrentDefer(page, "next_manager_check");
  summary.first_defer_action.worked = true;
  await waitForCondition(async () => {
    const agenda = await readManagerAgenda(page);
    return agenda.deferred_queue_items.length === 1 ? agenda : null;
  }, 180000, "Manager agenda did not show the first deferred item in the deferred queue.");
  summary.manager_agenda_after_first_defer = await readManagerAgenda(page);
  summary.first_deferred_session_id =
    summary.manager_agenda_after_first_defer.deferred_queue_items?.[0]?.session_id || "";

  summary.second_defer_action.label = await clickManagerAgendaCurrentDefer(page, "until_reopen");
  summary.second_defer_action.worked = true;
  await waitForCondition(async () => {
    const agenda = await readManagerAgenda(page);
    return (
      agenda.deferred_queue_items.length >= 2 &&
      agenda.deferred_queue_items.some((item) => /next manager check/i.test(item.text)) &&
      agenda.deferred_queue_items.some((item) => /until reopened/i.test(item.text)) &&
      String(agenda.current || "").includes(summary.session_c.session_id)
    );
  }, 180000, "Manager agenda did not show two deferred items with distinct return conditions while keeping the live session current.");
  summary.manager_agenda_after_second_defer = await readManagerAgenda(page);
  summary.deferred_workload_after_second_defer = await readDeferredWorkloadDigest(page);
  summary.second_deferred_session_id =
    (summary.manager_agenda_after_second_defer.deferred_queue_items || [])
      .map((item) => item.session_id)
      .find((sessionId) => sessionId && sessionId !== summary.first_deferred_session_id) || "";
  if (summary.deferred_workload_after_second_defer.return_basis_items.length < 2) {
    throw new Error("Deferred workload digest did not surface both return-basis categories after two defers.");
  }
  if (!/low deferred pressure/i.test(summary.deferred_workload_after_second_defer.pressure_band || "")) {
    throw new Error("Deferred workload digest did not classify the parked deferred backlog as low pressure.");
  }
  if (!/continue current work/i.test(summary.deferred_workload_after_second_defer.response_primary || "")) {
    throw new Error("Deferred workload digest did not recommend continuing current work while deferred pressure stayed low.");
  }
  if (!/Deferred pressure increased/i.test(summary.deferred_workload_after_second_defer.pressure || "")) {
    throw new Error("Deferred workload digest did not explain that deferred pressure increased after two defers.");
  }
  await page.screenshot({
    path: path.join(screensDir, "rc80_03_two_deferred_items.png"),
    fullPage: true,
  });

  summary.agenda_action.label = await clickManagerAgendaCurrentAction(page);
  await page.waitForURL("**/shell/workspace**", { timeout: 180000 });
  await waitForCondition(async () => {
    const focusedBlocking = await page.locator('[data-testid="blocking-attention-item"][data-focused-target="true"]').count();
    const focusedPacket = await page.locator('[data-testid="attention-packet"][data-focused-target="true"]').count();
    return focusedBlocking > 0 || focusedPacket > 0;
  }, 180000, "Timed out waiting for the operator queue jump to focus the exact packet/action.");
  summary.agenda_action.worked = true;
  await page.screenshot({
    path: path.join(screensDir, "rc80_04_queue_to_blocker.png"),
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
    path: path.join(screensDir, "rc80_05_selected_session_after_continue.png"),
    fullPage: true,
  });

  await page.goto(`${baseUrl}/shell`, { waitUntil: "domcontentloaded", timeout: 180000 });
  summary.portfolio_after_return = await waitForPortfolio(page);
  summary.manager_digest_after_return = await readManagerDigest(page);
  summary.deferred_workload_after_return = await readDeferredWorkloadDigest(page);
  summary.manager_agenda_after_return = await readManagerAgenda(page);
  summary.operator_queue_after_return = await readOperatorQueue(page);
  summary.queue_counts_after_return = {
    digest_counter_count: summary.manager_digest_after_return.counters.length,
    deferred_workload_counter_count: summary.deferred_workload_after_return.counters.length,
    deferred_return_basis_count: summary.deferred_workload_after_return.return_basis_items.length,
    operator_queue_section_count: summary.operator_queue_after_return.sections.length,
    operator_queue_card_count: summary.operator_queue_after_return.cards.length,
  };
  if (firstNumber(summary.manager_agenda_after_return.counts.deferred_items) < 2) {
    throw new Error("Manager agenda did not keep both deferred items visible after returning to /shell.");
  }
  if (firstNumber(summary.manager_agenda_after_return.counts.completed_since_last_check) < 1) {
    throw new Error("Manager agenda did not report a completed item after the queue-guided action.");
  }
  if (/No agenda item has been completed/i.test(summary.manager_agenda_after_return.completed || "")) {
    throw new Error("Manager agenda completed panel did not capture the handled item after returning to /shell.");
  }
  if (!/Deferred pressure increased/i.test(summary.deferred_workload_after_return.pressure || "")) {
    throw new Error("Deferred workload digest did not explain why deferred pressure changed after returning from the handled item.");
  }
  await page.screenshot({
    path: path.join(screensDir, "rc80_06_shell_after_action_return.png"),
    fullPage: true,
  });

  await markDigestChecked(page);
  await waitForCondition(async () => {
    const agenda = await readManagerAgenda(page);
    return (
      firstNumber(agenda.counts.due_now) >= 1 &&
      agenda.due_queue_items.some((item) => item.session_id === summary.first_deferred_session_id) &&
      agenda.deferred_queue_items.some((item) => item.session_id === summary.second_deferred_session_id)
    );
  }, 180000, "Deferred queue did not return the due-next-manager-check item while keeping the manual-reopen item deferred.");
  summary.manager_digest_after_due_return = await readManagerDigest(page);
  summary.deferred_workload_after_due_return = await readDeferredWorkloadDigest(page);
  summary.manager_agenda_after_due_return = await readManagerAgenda(page);
  if (!/rising deferred pressure/i.test(summary.deferred_workload_after_due_return.pressure_band || "")) {
    throw new Error("Deferred workload digest did not classify the due-next-manager-check return as rising pressure.");
  }
  if (!/clear due-now items first/i.test(summary.deferred_workload_after_due_return.response_primary || "")) {
    throw new Error("Deferred workload digest did not recommend clearing due-now items first when deferred pressure rose.");
  }
  if (!/became due/i.test(summary.deferred_workload_after_due_return.pressure || "")) {
    throw new Error("Deferred workload digest did not explain that a deferred item became due after the latest manager check.");
  }
  await page.screenshot({
    path: path.join(screensDir, "rc80_07_due_item_current.png"),
    fullPage: true,
  });

  summary.reopen_action.label = await clickManagerAgendaDeferredReopen(
    page,
    summary.second_deferred_session_id,
  );
  summary.reopen_action.worked = true;
  await waitForCondition(async () => {
    const agenda = await readManagerAgenda(page);
    return (
      !agenda.deferred_queue_items.some((item) => item.session_id === summary.second_deferred_session_id) &&
      agenda.reopened_queue_items.some((item) => item.session_id === summary.second_deferred_session_id)
    );
  }, 180000, "Deferred manual-reopen item did not return to the active agenda after explicit reopen.");
  summary.manager_agenda_after_manual_reopen = await readManagerAgenda(page);
  summary.deferred_workload_after_manual_reopen = await readDeferredWorkloadDigest(page);
  if (!/rising|high/i.test(summary.deferred_workload_after_manual_reopen.pressure_band || "")) {
    throw new Error("Deferred workload digest did not keep a meaningful pressure band after manual reopen.");
  }
  if (!/manual reopen/i.test(summary.deferred_workload_after_manual_reopen.response_detail || "")) {
    throw new Error("Deferred workload digest did not explain the manual-reopen contribution to the response mix.");
  }
  if (!/manual reopen/i.test(summary.deferred_workload_after_manual_reopen.pressure || "")) {
    throw new Error("Deferred workload digest did not explain the manual reopen contribution to deferred pressure.");
  }
  await page.screenshot({
    path: path.join(screensDir, "rc80_08_manual_reopen.png"),
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

  writeJson(managerDigestAckSummaryJsonPath, {
    session_a: summary.session_a,
    session_b: summary.session_b,
    session_c: summary.session_c,
    deferred_workload_before: summary.deferred_workload_before,
    deferred_workload_after_second_defer: summary.deferred_workload_after_second_defer,
    deferred_workload_after_return: summary.deferred_workload_after_return,
    deferred_workload_after_due_return: summary.deferred_workload_after_due_return,
    deferred_workload_after_manual_reopen: summary.deferred_workload_after_manual_reopen,
    manager_agenda_before: summary.manager_agenda_before,
    manager_agenda_after_first_defer: summary.manager_agenda_after_first_defer,
    manager_agenda_after_second_defer: summary.manager_agenda_after_second_defer,
    manager_agenda_after_return: summary.manager_agenda_after_return,
    manager_agenda_after_due_return: summary.manager_agenda_after_due_return,
    manager_agenda_after_manual_reopen: summary.manager_agenda_after_manual_reopen,
    first_defer_action: summary.first_defer_action,
    second_defer_action: summary.second_defer_action,
    agenda_action: summary.agenda_action,
    reopen_action: summary.reopen_action,
  });
  writeText(
    managerDigestAckSummaryMdPath,
    [
      "# deferred pressure controls summary",
      "",
      `- deferred workload before action: \`${summary.deferred_workload_before?.headline || "<none>"}\``,
      `- deferred workload after second defer: \`${summary.deferred_workload_after_second_defer?.headline || "<none>"}\``,
      `- pressure band after second defer: \`${summary.deferred_workload_after_second_defer?.pressure_band || "<none>"}\``,
      `- response after second defer: \`${summary.deferred_workload_after_second_defer?.response_primary || "<none>"}\``,
      `- deferred pressure after second defer: \`${summary.deferred_workload_after_second_defer?.pressure || "<none>"}\``,
      `- deferred workload after action return: \`${summary.deferred_workload_after_return?.headline || "<none>"}\``,
      `- deferred workload after due return: \`${summary.deferred_workload_after_due_return?.headline || "<none>"}\``,
      `- pressure band after due return: \`${summary.deferred_workload_after_due_return?.pressure_band || "<none>"}\``,
      `- response after due return: \`${summary.deferred_workload_after_due_return?.response_primary || "<none>"}\``,
      `- deferred workload after manual reopen: \`${summary.deferred_workload_after_manual_reopen?.headline || "<none>"}\``,
      `- pressure band after manual reopen: \`${summary.deferred_workload_after_manual_reopen?.pressure_band || "<none>"}\``,
      `- response after manual reopen: \`${summary.deferred_workload_after_manual_reopen?.response_primary || "<none>"}\``,
      `- first defer action used: \`${summary.first_defer_action?.label || "<none>"}\``,
      `- second defer action used: \`${summary.second_defer_action?.label || "<none>"}\``,
      `- handled action used: \`${summary.agenda_action?.label || "<none>"}\``,
      `- reopen action used: \`${summary.reopen_action?.label || "<none>"}\``,
      "",
    ].join("\n"),
  );
  writeJson(operatorAgendaSummaryJsonPath, {
    manager_digest_before: summary.manager_digest_before,
    manager_digest_checked: summary.manager_digest_checked,
    deferred_workload_before: summary.deferred_workload_before,
    deferred_workload_after_second_defer: summary.deferred_workload_after_second_defer,
    deferred_workload_after_return: summary.deferred_workload_after_return,
    deferred_workload_after_due_return: summary.deferred_workload_after_due_return,
    deferred_workload_after_manual_reopen: summary.deferred_workload_after_manual_reopen,
    manager_digest_after_return: summary.manager_digest_after_return,
    manager_digest_after_due_return: summary.manager_digest_after_due_return,
    manager_agenda_before: summary.manager_agenda_before,
    manager_agenda_after_first_defer: summary.manager_agenda_after_first_defer,
    manager_agenda_after_second_defer: summary.manager_agenda_after_second_defer,
    manager_agenda_after_return: summary.manager_agenda_after_return,
    manager_agenda_after_due_return: summary.manager_agenda_after_due_return,
    manager_agenda_after_manual_reopen: summary.manager_agenda_after_manual_reopen,
    queue_counts_before: summary.queue_counts_before,
    queue_counts_after_return: summary.queue_counts_after_return,
  });
  writeText(
    operatorAgendaSummaryMdPath,
    [
      "# manager response policy summary",
      "",
      `- return-basis summary before action: \`${summary.deferred_workload_before?.return_basis_items?.map((item) => item.text).join(" | ") || "<none>"}\``,
      `- response band after second defer: \`${summary.deferred_workload_after_second_defer?.pressure_band || "<none>"}\``,
      `- response guidance after second defer: \`${summary.deferred_workload_after_second_defer?.response_primary || "<none>"}\``,
      `- deferred pressure after second defer: \`${summary.deferred_workload_after_second_defer?.pressure || "<none>"}\``,
      `- deferred pressure after action return: \`${summary.deferred_workload_after_return?.pressure || "<none>"}\``,
      `- response band after due return: \`${summary.deferred_workload_after_due_return?.pressure_band || "<none>"}\``,
      `- response guidance after due return: \`${summary.deferred_workload_after_due_return?.response_primary || "<none>"}\``,
      `- deferred pressure after due return: \`${summary.deferred_workload_after_due_return?.pressure || "<none>"}\``,
      `- response band after manual reopen: \`${summary.deferred_workload_after_manual_reopen?.pressure_band || "<none>"}\``,
      `- response guidance after manual reopen: \`${summary.deferred_workload_after_manual_reopen?.response_primary || "<none>"}\``,
      `- deferred pressure after manual reopen: \`${summary.deferred_workload_after_manual_reopen?.pressure || "<none>"}\``,
      `- current reason after due return: \`${summary.deferred_workload_after_due_return?.current_reason || "<none>"}\``,
      `- current reason after manual reopen: \`${summary.deferred_workload_after_manual_reopen?.current_reason || "<none>"}\``,
      "",
    ].join("\n"),
  );
  writeJson(sinceLastManagerCheckDeltaPath, {
    digest_before: summary.manager_digest_before,
    digest_checked: summary.manager_digest_checked,
    deferred_workload_before: summary.deferred_workload_before,
    deferred_workload_after_second_defer: summary.deferred_workload_after_second_defer,
    deferred_workload_after_return: summary.deferred_workload_after_return,
    deferred_workload_after_due_return: summary.deferred_workload_after_due_return,
    deferred_workload_after_manual_reopen: summary.deferred_workload_after_manual_reopen,
    digest_after_return: summary.manager_digest_after_return,
    digest_after_due_return: summary.manager_digest_after_due_return,
    agenda_after_first_defer: summary.manager_agenda_after_first_defer,
    agenda_after_second_defer: summary.manager_agenda_after_second_defer,
    agenda_after_due_return: summary.manager_agenda_after_due_return,
    agenda_after_manual_reopen: summary.manager_agenda_after_manual_reopen,
    queue_counts_before: summary.queue_counts_before,
    queue_counts_after_return: summary.queue_counts_after_return,
  });
  writeJson(agendaProgressionAfterActionPath, {
    before: {
      digest_recommended_action: summary.manager_digest_before?.recommended_action_label || "",
      deferred_headline: summary.deferred_workload_before?.headline || "",
      deferred_pressure_band: summary.deferred_workload_before?.pressure_band || "",
      deferred_response_primary: summary.deferred_workload_before?.response_primary || "",
      deferred_pressure: summary.deferred_workload_before?.pressure || "",
      agenda_current: summary.manager_agenda_before?.current || "",
      agenda_next: summary.manager_agenda_before?.next || "",
      agenda_throughput: summary.manager_agenda_before?.throughput || "",
      queue_section_count: summary.operator_queue_before.sections.length,
    },
    after_first_defer: {
      agenda_current: summary.manager_agenda_after_first_defer?.current || "",
      agenda_next: summary.manager_agenda_after_first_defer?.next || "",
      agenda_deferred: summary.manager_agenda_after_first_defer?.deferred || "",
      agenda_throughput: summary.manager_agenda_after_first_defer?.throughput || "",
    },
    after_second_defer: {
      deferred_headline: summary.deferred_workload_after_second_defer?.headline || "",
      deferred_pressure_band: summary.deferred_workload_after_second_defer?.pressure_band || "",
      deferred_response_primary: summary.deferred_workload_after_second_defer?.response_primary || "",
      deferred_response_detail: summary.deferred_workload_after_second_defer?.response_detail || "",
      deferred_pressure: summary.deferred_workload_after_second_defer?.pressure || "",
      return_basis_summary:
        summary.deferred_workload_after_second_defer?.return_basis_items?.map((item) => item.text) || [],
      agenda_current: summary.manager_agenda_after_second_defer?.current || "",
      agenda_next: summary.manager_agenda_after_second_defer?.next || "",
      agenda_deferred: summary.manager_agenda_after_second_defer?.deferred || "",
      agenda_throughput: summary.manager_agenda_after_second_defer?.throughput || "",
    },
    after_return: {
      digest_recommended_action: summary.manager_digest_after_return?.recommended_action_label || "",
      deferred_headline: summary.deferred_workload_after_return?.headline || "",
      deferred_pressure_band: summary.deferred_workload_after_return?.pressure_band || "",
      deferred_response_primary: summary.deferred_workload_after_return?.response_primary || "",
      deferred_pressure: summary.deferred_workload_after_return?.pressure || "",
      agenda_current: summary.manager_agenda_after_return?.current || "",
      agenda_next: summary.manager_agenda_after_return?.next || "",
      agenda_completed: summary.manager_agenda_after_return?.completed || "",
      agenda_overdue: summary.manager_agenda_after_return?.overdue || "",
      agenda_deferred: summary.manager_agenda_after_return?.deferred || "",
      agenda_throughput: summary.manager_agenda_after_return?.throughput || "",
      queue_section_count: summary.operator_queue_after_return.sections.length,
    },
    after_due_return: {
      digest_recommended_action: summary.manager_digest_after_due_return?.recommended_action_label || "",
      deferred_headline: summary.deferred_workload_after_due_return?.headline || "",
      deferred_pressure_band: summary.deferred_workload_after_due_return?.pressure_band || "",
      deferred_response_primary: summary.deferred_workload_after_due_return?.response_primary || "",
      deferred_response_detail: summary.deferred_workload_after_due_return?.response_detail || "",
      deferred_pressure: summary.deferred_workload_after_due_return?.pressure || "",
      deferred_current_reason: summary.deferred_workload_after_due_return?.current_reason || "",
      agenda_current: summary.manager_agenda_after_due_return?.current || "",
      agenda_next: summary.manager_agenda_after_due_return?.next || "",
      agenda_due: summary.manager_agenda_after_due_return?.due || "",
      agenda_deferred: summary.manager_agenda_after_due_return?.deferred || "",
      agenda_throughput: summary.manager_agenda_after_due_return?.throughput || "",
    },
    after_manual_reopen: {
      deferred_headline: summary.deferred_workload_after_manual_reopen?.headline || "",
      deferred_pressure_band: summary.deferred_workload_after_manual_reopen?.pressure_band || "",
      deferred_response_primary: summary.deferred_workload_after_manual_reopen?.response_primary || "",
      deferred_response_detail: summary.deferred_workload_after_manual_reopen?.response_detail || "",
      deferred_pressure: summary.deferred_workload_after_manual_reopen?.pressure || "",
      deferred_current_reason: summary.deferred_workload_after_manual_reopen?.current_reason || "",
      agenda_current: summary.manager_agenda_after_manual_reopen?.current || "",
      agenda_next: summary.manager_agenda_after_manual_reopen?.next || "",
      agenda_due: summary.manager_agenda_after_manual_reopen?.due || "",
      agenda_deferred: summary.manager_agenda_after_manual_reopen?.deferred || "",
      agenda_reopened: summary.manager_agenda_after_manual_reopen?.reopened || "",
      agenda_throughput: summary.manager_agenda_after_manual_reopen?.throughput || "",
    },
    first_defer_action: summary.first_defer_action,
    second_defer_action: summary.second_defer_action,
    agenda_action: summary.agenda_action,
    reopen_action: summary.reopen_action,
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
      path: path.join(screensDir, "rc80_zz_failure.png"),
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
      "# rc80 operator journey",
      "",
      `- success: \`${summary.success}\``,
      `- live current session: \`${summary.session_c.session_id || "<none>"}\``,
      `- deferred session A: \`${summary.first_deferred_session_id || "<none>"}\``,
      `- deferred session B: \`${summary.second_deferred_session_id || "<none>"}\``,
      `- first defer action worked: \`${summary.first_defer_action.worked}\``,
      `- second defer action worked: \`${summary.second_defer_action.worked}\``,
      `- handled action worked: \`${summary.agenda_action.worked}\``,
      `- reopen action worked: \`${summary.reopen_action.worked}\``,
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



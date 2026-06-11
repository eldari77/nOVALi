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
    await delay(1500);
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

async function safeResponseJson(response) {
  try {
    const text = await response.text();
    return JSON.parse(text || "{}");
  } catch {
    return {};
  }
}

async function readGovernedStartCapture(page) {
  try {
    return await page.evaluate(() => {
      const fromMemory = globalThis.__novaliCapturedGovernedStart || null;
      if (fromMemory) {
        return fromMemory;
      }
      try {
        const raw = window.sessionStorage.getItem("__novaliCapturedGovernedStart");
        return raw ? JSON.parse(raw) : null;
      } catch {
        return null;
      }
    });
  } catch {
    return null;
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

const artifactRoot = readArg("--artifact-root");
const baseUrl = readArg("--base-url", "http://127.0.0.1:8787");
const directivePath = readArg("--directive-path");
const keyFile = readArg("--key-file");
const phase = readArg("--phase", "rc61");

if (!artifactRoot || !directivePath || !keyFile) {
  throw new Error("Missing required args. Expected --artifact-root, --directive-path, and --key-file.");
}

const screensDir = path.join(artifactRoot, "screens");
fs.mkdirSync(screensDir, { recursive: true });

const key = fs.readFileSync(keyFile, "utf8").trim();
const runSummaryPath = path.join(artifactRoot, `${phase}_operator_journey.json`);
const runMarkdownPath = path.join(artifactRoot, `${phase}_operator_journey.md`);
const routeValidationPath = path.join(artifactRoot, `${phase}_packaged_route_validation.json`);
const stateMappingPath = path.join(artifactRoot, `${phase}_long_run_state_mapping.json`);
const handoffSummaryJsonPath = path.join(artifactRoot, "approve_continue_handoff_summary.json");
const handoffSummaryMdPath = path.join(artifactRoot, "approve_continue_handoff_summary.md");
const requestSequencePath = path.join(artifactRoot, "approve_continue_request_sequence.json");
const beforeStatePath = path.join(artifactRoot, "long_run_state_before_approve_continue.json");
const afterApprovalStatePath = path.join(artifactRoot, "long_run_state_after_approval.json");
const afterContinuationStatePath = path.join(artifactRoot, "long_run_state_after_continuation.json");
const identityCheckPath = path.join(artifactRoot, "continuation_session_identity_check.json");
const packagedRouteValidationPath = path.join(artifactRoot, "packaged_route_validation.json");
const governedStartSummaryJsonPath = path.join(artifactRoot, "governed_start_contract_summary.json");
const governedStartSummaryMdPath = path.join(artifactRoot, "governed_start_contract_summary.md");
const longRunClaritySummaryJsonPath = path.join(artifactRoot, "long_run_control_clarity_summary.json");
const longRunClaritySummaryMdPath = path.join(artifactRoot, "long_run_control_clarity_summary.md");
const operatorJourneyNotePath = path.join(artifactRoot, "operator_journey_friction_note.md");
const policyBeforeAfterJsonPath = path.join(artifactRoot, "long_run_policy_before_after.json");
const policyBeforeAfterMdPath = path.join(artifactRoot, "long_run_policy_before_after.md");
const lowTouchSummaryJsonPath = path.join(artifactRoot, "low_touch_continuation_summary.json");
const lowTouchSummaryMdPath = path.join(artifactRoot, "low_touch_continuation_summary.md");
const policyRoundtripSummaryPath = path.join(artifactRoot, "operator_policy_roundtrip_summary.json");
const interventionLoopSummaryJsonPath = path.join(artifactRoot, "intervention_loop_summary.json");
const interventionLoopSummaryMdPath = path.join(artifactRoot, "intervention_loop_summary.md");
const interventionBeforeResolutionPath = path.join(artifactRoot, "intervention_state_before_resolution.json");
const interventionAfterResolutionPath = path.join(artifactRoot, "intervention_state_after_resolution.json");
const postInterventionIdentityPath = path.join(artifactRoot, "same_session_resume_after_intervention.json");
const operatorInterventionJourneyPath = path.join(artifactRoot, "operator_intervention_journey.md");
const campaignLoopSummaryJsonPath = path.join(artifactRoot, "campaign_loop_summary.json");
const campaignLoopSummaryMdPath = path.join(artifactRoot, "campaign_loop_summary.md");
const attentionInboxBeforeResolutionPath = path.join(artifactRoot, "attention_inbox_state_before_resolution.json");
const attentionInboxAfterResolutionPath = path.join(artifactRoot, "attention_inbox_state_after_resolution.json");
const batchReviewPacketSummaryPath = path.join(artifactRoot, "batch_review_packet_summary.json");
const sameSessionCampaignIdentityPath = path.join(artifactRoot, "same_session_campaign_identity.json");
const budgetBoundarySummaryPath = path.join(artifactRoot, "budget_boundary_summary.json");
const operatorAttentionJourneyPath = path.join(artifactRoot, "operator_attention_journey.md");
const campaignHandoffSummaryJsonPath = path.join(artifactRoot, "campaign_handoff_summary.json");
const campaignHandoffSummaryMdPath = path.join(artifactRoot, "campaign_handoff_summary.md");
const attentionEscalationSummaryJsonPath = path.join(artifactRoot, "attention_escalation_summary.json");
const attentionEscalationSummaryMdPath = path.join(artifactRoot, "attention_escalation_summary.md");
const deltaSinceLastTouchSummaryPath = path.join(artifactRoot, "delta_since_last_touch_summary.json");
const operatorReentryJourneyPath = path.join(artifactRoot, "operator_reentry_journey.md");
const localAttentionDeliverySummaryJsonPath = path.join(artifactRoot, "local_attention_delivery_summary.json");
const localAttentionDeliverySummaryMdPath = path.join(artifactRoot, "local_attention_delivery_summary.md");
const durableHandoffMemorySummaryJsonPath = path.join(artifactRoot, "durable_handoff_memory_summary.json");
const durableHandoffMemorySummaryMdPath = path.join(artifactRoot, "durable_handoff_memory_summary.md");
const attentionStateTransitionMatrixPath = path.join(artifactRoot, "attention_state_transition_matrix.json");
const operatorReentryAfterRefreshSummaryPath = path.join(artifactRoot, "operator_reentry_after_refresh_summary.md");
const actionableAttentionSummaryJsonPath = path.join(artifactRoot, "actionable_attention_summary.json");
const actionableAttentionSummaryMdPath = path.join(artifactRoot, "actionable_attention_summary.md");
const handoffArchiveNavigationSummaryJsonPath = path.join(
  artifactRoot,
  "handoff_archive_navigation_summary.json",
);
const handoffArchiveNavigationSummaryMdPath = path.join(
  artifactRoot,
  "handoff_archive_navigation_summary.md",
);
const attentionClickToPacketSequencePath = path.join(
  artifactRoot,
  "attention_click_to_packet_sequence.json",
);
const operatorReentryWithArchiveSummaryPath = path.join(
  artifactRoot,
  "operator_reentry_with_archive_summary.md",
);
const staleAttentionEscalationSummaryJsonPath = path.join(
  artifactRoot,
  "stale_attention_escalation_summary.json",
);
const staleAttentionEscalationSummaryMdPath = path.join(
  artifactRoot,
  "stale_attention_escalation_summary.md",
);
const archiveTriageNavigationSummaryJsonPath = path.join(
  artifactRoot,
  "archive_triage_navigation_summary.json",
);
const archiveTriageNavigationSummaryMdPath = path.join(
  artifactRoot,
  "archive_triage_navigation_summary.md",
);
const operatorReentryWithStaleAttentionSummaryPath = path.join(
  artifactRoot,
  "operator_reentry_with_stale_attention_summary.md",
);
const runInterventionLoop = /^(rc64|rc65|rc66|rc67|rc68|rc69)/i.test(phase);
const requirePostInterventionBridge = /^rc64a/i.test(phase);
const runCampaignLoop = /^(rc65|rc66|rc67|rc68|rc69)/i.test(phase);
const runCampaignHandoff = /^(rc66|rc67|rc68|rc69)/i.test(phase);
const runLocalAttentionDelivery = /^(rc67|rc68|rc69)/i.test(phase);
const runActionableAttentionDelivery = /^(rc68|rc69)/i.test(phase);
const runStaleAttentionEscalation = /^rc69/i.test(phase);
const staleAttentionEscalationWaitMs = runStaleAttentionEscalation ? 16000 : 0;

const summary = {
  success: false,
  phase,
  base_url: baseUrl,
  directive_path_used: directivePath,
  workspace_actions: [],
  workspace_action_count: 0,
  workspace_surfaces_used: ["/shell/workspace"],
  hidden_state_inference_points: 0,
  inline_blocking_reason_visible: false,
  next_action_obvious_on_first_view: false,
  primary_cta_present: false,
  primary_cta_label: "",
  review_gate_visible: false,
  attention_inbox_visible: false,
  attention_packet_visible: false,
  attention_badge_visible: false,
  attention_banner_visible: false,
  campaign_handoff_visible: false,
  since_last_touch_visible: false,
  durable_handoff_memory_visible: false,
  notification_permission: "",
  local_attention_delivery_mode: "",
  local_attention_state_before: "",
  local_attention_state_after_seen: "",
  local_attention_state_after_acknowledged: "",
  local_attention_state_after_refresh: "",
  attention_signal_click_actionable: false,
  attention_focus_target_kind: "",
  attention_focus_target_id: "",
  attention_focus_target_label: "",
  archive_navigation_visible: false,
  archive_navigation_distinction_visible: false,
  archive_navigation_worked: false,
  stale_attention_visible: false,
  stale_attention_state_after_refresh: "",
  stale_archive_filter_worked: false,
  headroom_visible: false,
  settings_visible: false,
  session_handle_visible: false,
  long_run_before: {},
  policy_before: {},
  policy_target: {},
  policy_after_save: {},
  long_run_after_approval: {},
  long_run_after: {},
  cycle_delta: 0,
  checkpoint_delta: 0,
  multi_boundary_advance: false,
  budget_boundary_proven: false,
  route_validation: {},
  timeline: [],
  failures: [],
};

const requestSequence = [];

const pushStep = (step, extra = {}) => {
  summary.timeline.push({ at: new Date().toISOString(), step, ...extra });
};

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
if (runLocalAttentionDelivery) {
  await context.grantPermissions(["notifications"], { origin: new URL(baseUrl).origin });
}
await context.addInitScript(() => {
  const originalFetch = window.fetch.bind(window);
  globalThis.__novaliCapturedGovernedStart = null;
  window.fetch = async (...args) => {
    const response = await originalFetch(...args);
    try {
      const input = args[0];
      const init = args[1] || {};
      const rawUrl = typeof input === "string" ? input : String(input?.url || "");
      const method = String(init?.method || input?.method || "GET").toUpperCase();
      if (rawUrl.includes("/shell/api/governed/start") && method === "POST") {
        const clone = response.clone();
        const text = await clone.text();
        let json = {};
        try {
          json = JSON.parse(text || "{}");
        } catch {
          json = {};
        }
        const captured = {
          url: rawUrl,
          status: response.status,
          transport_ok: response.ok,
          text,
          json,
        };
        globalThis.__novaliCapturedGovernedStart = captured;
        try {
          window.sessionStorage.setItem("__novaliCapturedGovernedStart", JSON.stringify(captured));
        } catch {
          // Preserve proof flow if sessionStorage is unavailable.
        }
      }
    } catch {
      // Preserve the operator flow even if proof capture fails.
    }
    return response;
  };
});
const page = await context.newPage();
const request = context.request;

try {
  summary.route_validation.root = await context.request.get(baseUrl, { maxRedirects: 0 }).then(async (response) => ({
    status: response.status(),
    location: response.headers()["location"] || "",
  }));

  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 180000 });
  await page.waitForURL("**/shell", { timeout: 180000 });
  await page.getByRole("button", { name: "Load Directive" }).waitFor({ timeout: 120000 });
  pushStep("landing_loaded");
  await page.screenshot({
    path: path.join(screensDir, `${phase}_01_shell_landing.png`),
    fullPage: true,
  });

  await page.getByRole("button", { name: "Load Directive" }).click();
  await page.getByRole("heading", { name: "Directive and trusted-source load" }).waitFor({ timeout: 60000 });
  await page.screenshot({
    path: path.join(screensDir, `${phase}_02_directive_trusted_source_modal.png`),
    fullPage: true,
  });
  pushStep("directive_modal_open");

  await page.getByLabel("API credential").fill(key);
  const validateResponsePromise = page.waitForResponse(
    (resp) => resp.url().includes("/shell/api/trusted-source/validate") && resp.request().method() === "POST",
    { timeout: 180000 },
  );
  await page.getByRole("button", { name: "Validate Trusted Source" }).click();
  const validateResponse = await validateResponsePromise;
  const validatePayload = await safeResponseJson(validateResponse);
  summary.trusted_source_validation = {
    status: validateResponse.status(),
    ok: validatePayload.ok === true,
    headline: String(validatePayload.headline || validatePayload.message || ""),
  };
  pushStep("trusted_source_validated", {
    status: validateResponse.status(),
    ok: validatePayload.ok === true,
  });
  await waitForCondition(async () => {
    const notices = await page.locator(".notice").allTextContents();
    return notices.some((item) => /validated|accepted/i.test(item));
  }, 120000, "Timed out waiting for trusted-source validation notice.");
  await page.getByLabel("API credential").fill("");

  await page.getByLabel("Directive path").fill(directivePath);
  const directiveResponsePromise = page.waitForResponse(
    (resp) => resp.url().includes("/shell/api/directive/select") && resp.request().method() === "POST",
    { timeout: 180000 },
  );
  await page.getByRole("button", { name: "Select directive" }).click();
  const directiveResponse = await directiveResponsePromise;
  summary.directive_selection = { status: directiveResponse.status() };
  pushStep("directive_selected", { status: directiveResponse.status() });
  await waitForCondition(async () => {
    const text = await page.locator(".path").first().textContent().catch(() => "");
    return String(text || "").includes("directive_build_advanced_successor_v3.json");
  }, 120000, "Timed out waiting for directive selection to appear.");
  await page.getByRole("button", { name: "Close" }).click();
  await waitForCondition(
    async () => page.getByRole("button", { name: "Bootstrap Initialization" }).isEnabled(),
    120000,
    "Timed out waiting for Bootstrap Initialization to become enabled after directive selection.",
  );

  const bootstrapResponsePromise = page.waitForResponse(
    (resp) => resp.url().includes("/shell/api/bootstrap/start") && resp.request().method() === "POST",
    { timeout: 240000 },
  );
  await page.getByRole("button", { name: "Bootstrap Initialization" }).click();
  const bootstrapResponse = await bootstrapResponsePromise;
  const bootstrapPayload = await safeResponseJson(bootstrapResponse);
  summary.bootstrap = { status: bootstrapResponse.status(), ok: bootstrapPayload.ok === true };
  pushStep("bootstrap_completed", summary.bootstrap);
  await waitForCondition(async () => {
    const governed = await fetchJson(request, "/governed/status", baseUrl);
    const nextAction = String(governed.json?.operator_next_action || "");
    return /governed/i.test(nextAction) || governed.json?.can_launch === true;
  }, 240000, "Timed out waiting for governed readiness after bootstrap.");
  await page.screenshot({
    path: path.join(screensDir, `${phase}_03_post_bootstrap_pre_governed.png`),
    fullPage: true,
  });

  const prepareButton = page.getByRole("button", { name: "Prepare governed execution" });
  if ((await prepareButton.count()) > 0 && (await prepareButton.isVisible().catch(() => false))) {
    const prepareResponsePromise = page.waitForResponse(
      (resp) => resp.url().includes("/shell/api/governed/prepare") && resp.request().method() === "POST",
      { timeout: 240000 },
    );
    await prepareButton.click();
    const prepareResponse = await prepareResponsePromise;
    const preparePayload = await safeResponseJson(prepareResponse);
    summary.governed_prepare = { status: prepareResponse.status(), ok: preparePayload.ok === true };
    pushStep("governed_prepare_completed", summary.governed_prepare);
  }

  await waitForCondition(async () => {
    const governed = await fetchJson(request, "/governed/status", baseUrl);
    return governed.json?.can_launch === true;
  }, 240000, "Timed out waiting for governed launch readiness.");
  await waitForCondition(
    async () => page.getByRole("button", { name: "Governed Execution Run" }).isEnabled(),
    120000,
    "Timed out waiting for Governed Execution Run to become enabled.",
  );

  const governedStartPromise = page.waitForResponse(
    (resp) => resp.url().includes("/shell/api/governed/start") && resp.request().method() === "POST",
    { timeout: 420000 },
  );
  await page.getByRole("button", { name: "Governed Execution Run" }).click();
  const governedStartResponse = await governedStartPromise;
  let governedStartPayload = await safeResponseJson(governedStartResponse);
  const governedStartCapture = await waitForCondition(
    async () => {
      const captured = await readGovernedStartCapture(page);
      return captured?.status ? captured : null;
    },
    15000,
    "Timed out waiting for governed-start capture.",
  );
  if ((!governedStartPayload || Object.keys(governedStartPayload).length === 0) && governedStartCapture?.json) {
    governedStartPayload = governedStartCapture.json;
  }
  summary.governed_start = {
    status: Number(governedStartCapture?.status || governedStartResponse.status()),
    ok: governedStartPayload.ok === true,
    next_path: String(governedStartPayload.next_path || ""),
  };
  requestSequence.push({
    step: "governed_start",
    response_status: Number(governedStartCapture?.status || governedStartResponse.status()),
    response_payload: governedStartPayload,
    raw_capture: governedStartCapture,
  });
  pushStep("governed_start_response", summary.governed_start);
  await page.waitForURL("**/shell/workspace", { timeout: 480000 });
  await page.getByRole("heading", { name: "Operator Workspace" }).waitFor({ timeout: 120000 });
  await page.screenshot({
    path: path.join(screensDir, `${phase}_04_workspace_after_first_redirect.png`),
    fullPage: true,
  });

  const beforeLongRun = await waitForCondition(async () => {
    const result = await fetchJson(request, "/long-run-state", baseUrl);
    const longRun = result.json?.long_run || {};
    if (result.status === 200 && longRun.session_id && Number(longRun.checkpoint_count || 0) >= 1) {
      return result.json;
    }
    return null;
  }, 480000, "Timed out waiting for a materialized long-run session after first governed execution.");
  summary.long_run_before = beforeLongRun.long_run;
  summary.policy_before = beforeLongRun.effective_policy || {};
  pushStep("workspace_ready_for_continuation", {
    session_id: beforeLongRun.long_run.session_id,
    checkpoint_count: beforeLongRun.long_run.checkpoint_count,
    current_cycle: beforeLongRun.long_run.current_cycle,
    lifecycle_state: beforeLongRun.long_run.lifecycle_state,
  });
  const expectedPrimaryLabel = String(beforeLongRun.operator_guidance?.primary_cta?.label || "").trim();
  const expectedSessionHandle = String(beforeLongRun.operator_guidance?.session_handle || "").trim();
  await waitForCondition(async () => {
    const panelText = await page.locator("#bounded-continuation").textContent().catch(() => "");
    const ctaText = await page.locator('[data-testid="long-run-primary-cta"]').textContent().catch(() => "");
    if (expectedPrimaryLabel && String(ctaText || "").includes(expectedPrimaryLabel)) {
      return true;
    }
    if (expectedSessionHandle && String(panelText || "").includes(expectedSessionHandle)) {
      return true;
    }
    return String(panelText || "").includes(String(beforeLongRun.long_run.session_id || ""));
  }, 45000, "Timed out waiting for the workspace long-run panel to reflect the latest continuation guidance.");

  summary.primary_cta_present = (await page.locator('[data-testid="long-run-primary-cta"]').count()) > 0;
  if (summary.primary_cta_present) {
    summary.primary_cta_label = String(
      (await page.locator('[data-testid="long-run-primary-cta"]').textContent()) || "",
    ).trim();
  }
  summary.review_gate_visible = await page.locator("#continuation-review-gate").isVisible().catch(() => false);
  summary.attention_inbox_visible = await page.locator('[data-testid="attention-inbox"]').isVisible().catch(() => false);
  summary.attention_packet_visible = await page.locator('[data-testid="attention-packet"]').isVisible().catch(() => false);
  summary.inline_blocking_reason_visible = (await page.locator("text=Blocking reason:").count()) > 0;
  summary.headroom_visible = (await page.locator("text=Headroom").count()) > 0;
  summary.settings_visible = (await page.locator("text=Bounded settings").count()) > 0;
  summary.session_handle_visible = (await page.locator("text=Session").count()) > 0;
  summary.next_action_obvious_on_first_view = summary.primary_cta_present && (
    !expectedPrimaryLabel || summary.primary_cta_label === expectedPrimaryLabel
  );
  summary.hidden_state_inference_points =
    (summary.primary_cta_present ? 0 : 1) +
    (summary.attention_inbox_visible ? 0 : 1) +
    (summary.inline_blocking_reason_visible ? 0 : 1) +
    (summary.headroom_visible ? 0 : 1);
  await page.screenshot({
    path: path.join(screensDir, `${phase}_05_long_run_before_continuation.png`),
    fullPage: true,
  });
  const targetPolicy = {
    continuation_strategy: "until_bounded_stop",
    max_total_cycles: String(
      Math.max(
        Number(beforeLongRun.effective_policy?.max_total_cycles || 0),
        Number(beforeLongRun.long_run?.current_cycle || 0) +
          (runInterventionLoop ? 4 : 2),
        runInterventionLoop ? 6 : 4,
      ),
    ),
    max_cycles_per_invocation: "2",
  };
  summary.policy_target = targetPolicy;
  await page.getByLabel("Continuation strategy").selectOption(targetPolicy.continuation_strategy);
  await page.getByLabel("Max total cycles").fill(targetPolicy.max_total_cycles);
  await page.getByLabel("Max cycles per invocation").fill(targetPolicy.max_cycles_per_invocation);
  const policySaveResponsePromise = page.waitForResponse(
    (resp) => resp.url().includes("/shell/api/long-run/policy") && resp.request().method() === "POST",
    { timeout: 180000 },
  );
  await page.getByRole("button", { name: "Save long-run policy" }).click();
  const policySaveResponse = await policySaveResponsePromise;
  const policySavePayload = await safeResponseJson(policySaveResponse);
  summary.workspace_actions.push("Save long-run policy");
  requestSequence.push({
    step: "save_long_run_policy",
    response_status: policySaveResponse.status(),
    response_payload: policySavePayload,
    target_policy: targetPolicy,
  });
  pushStep("policy_saved", {
    status: policySaveResponse.status(),
    ok: policySavePayload.ok === true,
    target_policy: targetPolicy,
  });
  const afterPolicySave = await waitForCondition(async () => {
    const result = await fetchJson(request, "/long-run-state", baseUrl);
    const effectivePolicy = result.json?.effective_policy || {};
    if (
      String(effectivePolicy.continuation_strategy || "").trim() === targetPolicy.continuation_strategy &&
      Number(effectivePolicy.max_total_cycles || 0) >= Number(targetPolicy.max_total_cycles || 0) &&
      Number(effectivePolicy.max_cycles_per_invocation || 0) >= Number(targetPolicy.max_cycles_per_invocation || 0)
    ) {
      return result.json;
    }
    return null;
  }, 180000, "Timed out waiting for the saved long-run policy to become effective.");
  summary.policy_after_save = afterPolicySave.effective_policy || {};
  await page.screenshot({
    path: path.join(screensDir, `${phase}_06_policy_after_save.png`),
    fullPage: true,
  });
  if (summary.review_gate_visible) {
    await page.screenshot({
      path: path.join(screensDir, `${phase}_07_long_run_review_gate.png`),
      fullPage: true,
    });
  }

  let pauseResumeEvidence = null;
  if (await page.getByRole("button", { name: "Pause" }).isEnabled().catch(() => false)) {
    await page.getByRole("button", { name: "Pause" }).click();
    const pausedState = await waitForCondition(async () => {
      const result = await fetchJson(request, "/long-run-state", baseUrl);
      const payload = result.json || {};
      if (payload.long_run?.operator_pause_requested || payload.long_run?.lifecycle_state === "paused_by_operator") {
        return payload;
      }
      return null;
    }, 120000, "Timed out waiting for pause to become visible in long-run state.");
    requestSequence.push({
      step: "pause_control",
      state_after_pause: pausedState,
    });
    await page.goto(`${baseUrl}/shell/workspace`, {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    await page.waitForTimeout(1500);
    await waitForCondition(
      async () => page.getByRole("button", { name: "Resume" }).isEnabled(),
      45000,
      "Timed out waiting for the Resume control to become enabled after pause.",
    );
    await page.getByRole("button", { name: "Resume" }).click();
    const resumedState = await waitForCondition(async () => {
      const result = await fetchJson(request, "/long-run-state", baseUrl);
      const payload = result.json || {};
      if (!payload.long_run?.operator_pause_requested && payload.long_run?.checkpoint_count) {
        return payload;
      }
      return null;
    }, 120000, "Timed out waiting for resume to clear the operator pause.");
    requestSequence.push({
      step: "resume_control",
      state_after_resume: resumedState,
    });
    pauseResumeEvidence = {
      paused: pausedState.long_run || {},
      resumed: resumedState.long_run || {},
    };
    await page.goto(`${baseUrl}/shell/workspace`, {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    await page.waitForTimeout(1500);
  }

  const interventionBefore = await fetchJson(request, "/intervention-state", baseUrl);
  const reviewRequired = Boolean(interventionBefore.json?.review_required);
  if (reviewRequired && expectedPrimaryLabel.toLowerCase().includes("approve and continue") && summary.primary_cta_label.toLowerCase().includes("approve and continue")) {
    summary.workspace_actions.push(summary.primary_cta_label);
    await page.locator('[data-testid="long-run-primary-cta"]').click();
    await page.screenshot({
      path: path.join(screensDir, `${phase}_08_during_continuation.png`),
      fullPage: true,
    });
  } else {
    if (reviewRequired) {
      const reviewLabel = "Approve bounded continuation";
      summary.workspace_actions.push(reviewLabel);
      await page.getByRole("button", { name: reviewLabel }).click();
      const approvalCleared = await waitForCondition(async () => {
        const result = await fetchJson(request, "/intervention-state", baseUrl);
        const payload = result.json || {};
        if (!payload.review_required && !payload.intervention?.required) {
          return payload;
        }
        return null;
      }, 180000, "Timed out waiting for the approval step to clear the review gate.");
      const afterApprovalLongRun = await fetchJson(request, "/long-run-state", baseUrl);
      summary.long_run_after_approval = afterApprovalLongRun.json?.long_run || {};
      requestSequence.push({
        step: "approve_review_item",
        action_label: reviewLabel,
        intervention_state_after_approval: approvalCleared,
        long_run_state_after_approval: afterApprovalLongRun.json || {},
      });
      try {
        await page.waitForLoadState("domcontentloaded", { timeout: 15000 });
      } catch {}
      await page.goto(`${baseUrl}/shell/workspace`, {
        waitUntil: "domcontentloaded",
        timeout: 60000,
      });
      await page.waitForTimeout(1500);
    }
    const readyForContinue = await waitForCondition(async () => {
      const result = await fetchJson(request, "/long-run-state", baseUrl);
      const payload = result.json || {};
      const primaryLabel = String(payload.operator_guidance?.primary_cta?.label || "").trim();
      const primaryAction = String(payload.operator_guidance?.primary_cta?.action_id || "").trim();
      if (/continue|resume/i.test(primaryLabel) || primaryAction === "continue") {
        return { mode: "primary", label: primaryLabel || "Continue bounded session" };
      }
      try {
        if (await page.getByRole("button", { name: "Continue" }).isEnabled()) {
          return { mode: "secondary", label: "Continue" };
        }
      } catch {}
      return null;
    }, 120000, "Timed out waiting for continuation control to enable.");
    summary.workspace_actions.push(readyForContinue.label);
    if (readyForContinue.mode === "primary") {
      await waitForCondition(
        async () => page.locator('[data-testid="long-run-primary-cta"]').isEnabled(),
        120000,
        "Timed out waiting for the promoted primary continuation CTA to enable.",
      );
      await page.locator('[data-testid="long-run-primary-cta"]').click();
      requestSequence.push({
        step: "continue_bounded_session",
        control_mode: "primary",
        control_label: readyForContinue.label,
      });
    } else {
      await page.getByRole("button", { name: "Continue" }).click();
      requestSequence.push({
        step: "continue_bounded_session",
        control_mode: "secondary",
        control_label: readyForContinue.label,
      });
    }
    await page.screenshot({
      path: path.join(screensDir, `${phase}_08_during_continuation.png`),
      fullPage: true,
    });
  }

  const afterLongRun = await waitForCondition(async () => {
    const result = await fetchJson(request, "/long-run-state", baseUrl);
    const longRun = result.json?.long_run || {};
    if (!longRun.session_id || longRun.session_id !== beforeLongRun.long_run.session_id) {
      return null;
    }
    const requiredDelta = runInterventionLoop || requirePostInterventionBridge ? 1 : 2;
    const cycleAdvanced =
      Number(longRun.current_cycle || 0) >=
      Number(beforeLongRun.long_run.current_cycle || 0) + requiredDelta;
    const checkpointAdvanced =
      Number(longRun.checkpoint_count || 0) >=
      Number(beforeLongRun.long_run.checkpoint_count || 0) + requiredDelta;
    if (cycleAdvanced || checkpointAdvanced) {
      return result.json;
    }
    return null;
  }, 600000, runInterventionLoop || requirePostInterventionBridge
    ? "Timed out waiting for same-session low-touch continuation to reach the first post-seed bounded stop boundary."
    : "Timed out waiting for same-session low-touch continuation to advance across more than one additional boundary.");

  summary.workspace_action_count = summary.workspace_actions.length;
  summary.long_run_after = afterLongRun.long_run;
  summary.cycle_delta =
    Number(afterLongRun.long_run.current_cycle || 0) - Number(beforeLongRun.long_run.current_cycle || 0);
  summary.checkpoint_delta =
    Number(afterLongRun.long_run.checkpoint_count || 0) - Number(beforeLongRun.long_run.checkpoint_count || 0);
  summary.multi_boundary_advance = summary.cycle_delta > 1 || summary.checkpoint_delta > 1;
  pushStep("continuation_advanced", {
    session_id: afterLongRun.long_run.session_id,
    checkpoint_count: afterLongRun.long_run.checkpoint_count,
    current_cycle: afterLongRun.long_run.current_cycle,
    lifecycle_state: afterLongRun.long_run.lifecycle_state,
    cycle_delta: summary.cycle_delta,
    checkpoint_delta: summary.checkpoint_delta,
  });
  await page.screenshot({
    path: path.join(screensDir, `${phase}_09_workspace_after_continuation.png`),
    fullPage: true,
  });

  let postInterventionSummary = null;
  let campaignLoopSummary = null;
  let budgetBoundarySummary = null;
  if (runInterventionLoop) {
    const resolveAttentionBoundary = async ({
      boundaryScreenshotName,
      resolutionScreenshotName,
      stepPrefix,
    }) => {
      const boundaryIntervention = await fetchJson(request, "/intervention-state", baseUrl);
      await page.goto(`${baseUrl}/shell/workspace`, {
        waitUntil: "domcontentloaded",
        timeout: 60000,
      });
      await page.waitForTimeout(1500);
      await page.screenshot({
        path: path.join(screensDir, boundaryScreenshotName),
        fullPage: true,
      });

      const actions = [];
      let resolvedIntervention = null;
      for (let attempt = 0; attempt < 6; attempt += 1) {
        const currentIntervention = await fetchJson(request, "/intervention-state", baseUrl);
        const currentLongRun = await fetchJson(request, "/long-run-state", baseUrl);
        const currentQueue = Array.isArray(currentIntervention.json?.intervention?.queue_items)
          ? currentIntervention.json.intervention.queue_items
          : [];
        const currentPrimaryReviewItemId = String(
          currentIntervention.json?.intervention?.current_primary_review_item_id ||
            currentQueue[0]?.review_item_id ||
            "",
        ).trim();
        const currentPrimaryTitle = String(
          currentIntervention.json?.intervention?.current_primary_review_title ||
            currentQueue[0]?.title ||
            currentQueue[0]?.reason_summary ||
            currentPrimaryReviewItemId,
        ).trim();
        const currentPrimaryAction = String(
          currentLongRun.json?.operator_guidance?.primary_cta?.action_id || "",
        ).trim();
        const currentPrimaryLabel = String(
          currentLongRun.json?.operator_guidance?.primary_cta?.label || "",
        ).trim();

        if (!currentIntervention.json?.review_required && !currentIntervention.json?.intervention_required) {
          resolvedIntervention = {
            intervention: currentIntervention.json,
            long_run: currentLongRun.json,
            actions,
          };
          break;
        }
        if (currentPrimaryAction !== "approve_review_item") {
          throw new Error(
            `Expected intervention resolution to surface approve_review_item, but saw ${currentPrimaryAction || "<none>"}.`,
          );
        }

        await page.goto(`${baseUrl}/shell/workspace`, {
          waitUntil: "domcontentloaded",
          timeout: 60000,
        });
        await page.waitForTimeout(1500);
        await waitForCondition(
          async () => {
            const text = await page.locator('[data-testid="long-run-primary-cta"]').textContent().catch(() => "");
            return String(text || "").includes(currentPrimaryLabel || "Approve");
          },
          45000,
          "Timed out waiting for the primary intervention CTA to render in the workspace panel.",
        );
        const reviewResponsePromise = page.waitForResponse(
          (resp) => resp.url().includes("/shell/api/review/action") && resp.request().method() === "POST",
          { timeout: 180000 },
        );
        await page.locator('[data-testid="long-run-primary-cta"]').click();
        const reviewResponse = await reviewResponsePromise;
        const reviewPayload = await safeResponseJson(reviewResponse);
        summary.workspace_actions.push(currentPrimaryLabel || "Approve review item");
        actions.push({
          review_item_id: currentPrimaryReviewItemId,
          review_item_title: currentPrimaryTitle,
          action_id: currentPrimaryAction,
          action_label: currentPrimaryLabel || "Approve review item",
          response_status: reviewResponse.status(),
          response_payload: reviewPayload,
        });
        requestSequence.push({
          step: `${stepPrefix}_review_action`,
          review_item_id: currentPrimaryReviewItemId,
          review_item_title: currentPrimaryTitle,
          action_label: currentPrimaryLabel || "Approve review item",
          response_status: reviewResponse.status(),
          response_payload: reviewPayload,
        });
        pushStep(`${stepPrefix}_review_action_recorded`, {
          review_item_id: currentPrimaryReviewItemId,
          review_item_title: currentPrimaryTitle,
          action_label: currentPrimaryLabel || "Approve review item",
        });

        await waitForCondition(
          async () => {
            const refreshed = await fetchJson(request, "/intervention-state", baseUrl);
            const refreshedQueue = Array.isArray(refreshed.json?.intervention?.queue_items)
              ? refreshed.json.intervention.queue_items
              : [];
            const refreshedPrimaryReviewItemId = String(
              refreshed.json?.intervention?.current_primary_review_item_id ||
                refreshedQueue[0]?.review_item_id ||
                "",
            ).trim();
            if (!refreshed.json?.review_required && !refreshed.json?.intervention_required) {
              return refreshed.json;
            }
            if (refreshedPrimaryReviewItemId && refreshedPrimaryReviewItemId !== currentPrimaryReviewItemId) {
              return refreshed.json;
            }
            return null;
          },
          180000,
          "Timed out waiting for the intervention queue to progress after a recorded review action.",
        );
      }

      if (!resolvedIntervention) {
        const finalInterventionAttempt = await fetchJson(request, "/intervention-state", baseUrl);
        const finalLongRunAttempt = await fetchJson(request, "/long-run-state", baseUrl);
        if (!finalInterventionAttempt.json?.review_required && !finalInterventionAttempt.json?.intervention_required) {
          resolvedIntervention = {
            intervention: finalInterventionAttempt.json,
            long_run: finalLongRunAttempt.json,
            actions,
          };
        }
      }
      if (!resolvedIntervention) {
        throw new Error("Timed out waiting for the intervention queue to clear into a same-session resumable state.");
      }

      await page.goto(`${baseUrl}/shell/workspace`, {
        waitUntil: "domcontentloaded",
        timeout: 60000,
      });
      await page.waitForTimeout(1500);
      await page.screenshot({
        path: path.join(screensDir, resolutionScreenshotName),
        fullPage: true,
      });

      return {
        boundaryIntervention,
        resolvedIntervention,
        actions,
      };
    };

    const interventionBoundaryState = afterLongRun;
    const interventionBoundaryIntervention = await fetchJson(request, "/intervention-state", baseUrl);
    const interventionBoundaryRequired =
      interventionBoundaryState.long_run?.halt_reason === "intervention_required" ||
      interventionBoundaryState.long_run?.watchdog_state === "intervention_required" ||
      interventionBoundaryIntervention.json?.intervention_required ||
      interventionBoundaryIntervention.json?.review_required;
    if (!interventionBoundaryRequired) {
      throw new Error("Expected a real intervention_required boundary after low-touch continuation, but the packaged state did not enter intervention review.");
    }
    writeJson(interventionBeforeResolutionPath, interventionBoundaryIntervention.json || interventionBoundaryIntervention);
    writeJson(
      attentionInboxBeforeResolutionPath,
      interventionBoundaryState.operator_guidance?.attention_inbox ||
        interventionBoundaryIntervention.json?.attention_inbox ||
        {},
    );
    writeJson(
      batchReviewPacketSummaryPath,
      interventionBoundaryState.operator_guidance?.attention_inbox?.current_packet || {},
    );
    if (runCampaignHandoff) {
      await page.goto(`${baseUrl}/shell`, {
        waitUntil: "domcontentloaded",
        timeout: 60000,
      });
      await page.goto(`${baseUrl}/shell/workspace`, {
        waitUntil: "domcontentloaded",
        timeout: 60000,
      });
      await waitForCondition(
        async () => page.locator('[data-testid="campaign-handoff-summary"]').isVisible(),
        45000,
        "Timed out waiting for the campaign handoff summary to render after workspace re-entry.",
      );
      summary.attention_badge_visible = await page
        .locator('[data-testid="attention-required-badge"]')
        .isVisible()
        .catch(() => false);
      summary.attention_banner_visible = await page
        .locator('[data-testid="attention-signal-banner"]')
        .isVisible()
        .catch(() => false);
      summary.campaign_handoff_visible = await page
        .locator('[data-testid="campaign-handoff-summary"]')
        .isVisible()
        .catch(() => false);
      summary.since_last_touch_visible = await page
        .locator('[data-testid="since-last-touch-summary"]')
        .isVisible()
        .catch(() => false);
      const reentryLongRun = await fetchJson(request, "/long-run-state", baseUrl);
      const handoffSummary = reentryLongRun.json?.operator_guidance?.campaign_handoff_summary || {};
      const attentionSignal = reentryLongRun.json?.operator_guidance?.attention_signal || {};
      const deltaSinceLastResume = reentryLongRun.json?.operator_guidance?.delta_since_last_resume || {};
      summary.durable_handoff_memory_visible = await page
        .locator('[data-testid="durable-handoff-history"]')
        .isVisible()
        .catch(() => false);
      summary.archive_navigation_visible = summary.durable_handoff_memory_visible;
      summary.notification_permission = await page.evaluate(() =>
        typeof Notification === "undefined" ? "unsupported" : Notification.permission,
      );
      const deliveryPanelText = await page
        .locator('[data-testid="attention-delivery-panel"]')
        .textContent()
        .catch(() => "");
      summary.local_attention_delivery_mode = /browser \+ in-app/i.test(String(deliveryPanelText || ""))
        ? "browser"
        : "in_app_only";
      const bannerText = await page
        .locator('[data-testid="attention-signal-banner"]')
        .textContent()
        .catch(() => "");
      const handoffText = await page
        .locator('[data-testid="campaign-handoff-summary"]')
        .textContent()
        .catch(() => "");
      const sinceLastTouchText = await page
        .locator('[data-testid="since-last-touch-summary"]')
        .textContent()
        .catch(() => "");
      summary.local_attention_state_before = String(
        (await page
          .locator('[data-testid="current-attention-local-state"]')
          .textContent()
          .catch(() => "")) || "",
      ).trim();
      const localTouchMarker = await page.evaluate(() => {
        try {
          const raw = window.localStorage.getItem("novali.workspace.lastOperatorTouch");
          return raw ? JSON.parse(raw) : null;
        } catch {
          return null;
        }
      });
      let attentionMemorySnapshotBefore = {};
      let attentionMemorySnapshotAfterRefresh = {};
      let localAttentionNoticeText = "";
      let attentionClickSequence = {};
      let archiveNavigationSummary = {};
      let staleAttentionSummary = {};
      let staleArchiveSummary = {};
      if (runLocalAttentionDelivery) {
        if (runActionableAttentionDelivery) {
          await page.locator('[data-testid="attention-signal-banner"]').click();
          const focusedTarget = await waitForCondition(async () => {
            const blockingItem = page
              .locator('[data-testid="blocking-attention-item"][data-focused-target="true"]')
              .first();
            if ((await blockingItem.count()) > 0) {
              const label = String((await blockingItem.textContent().catch(() => "")) || "").trim();
              if (label) {
                return {
                  kind: "blocking_item",
                  target_id: String((await blockingItem.getAttribute("id").catch(() => "")) || "").trim(),
                  label,
                };
              }
            }
            const packet = page
              .locator('[data-testid="attention-packet"][data-focused-target="true"]')
              .first();
            if ((await packet.count()) > 0) {
              const label = String((await packet.textContent().catch(() => "")) || "").trim();
              if (label) {
                return {
                  kind: "packet",
                  target_id: String((await packet.getAttribute("id").catch(() => "")) || "").trim(),
                  label,
                };
              }
            }
            return null;
          }, 15000, "Timed out waiting for the attention signal click to focus the blocking packet.");
          summary.attention_signal_click_actionable = true;
          summary.attention_focus_target_kind = focusedTarget.kind;
          summary.attention_focus_target_id = focusedTarget.target_id;
          summary.attention_focus_target_label = focusedTarget.label;
          summary.workspace_actions.push("Open current blocking packet");
          attentionClickSequence = {
            clicked_signal: "attention-signal-banner",
            attention_signal: attentionSignal,
            focus_result: focusedTarget,
          };
          await page.screenshot({
            path: path.join(screensDir, `${phase}_10_attention_click_to_packet.png`),
            fullPage: true,
          });
        }
        attentionMemorySnapshotBefore = await page.evaluate(() => {
          try {
            return JSON.parse(window.localStorage.getItem("novali.workspace.attentionMemory") || "{}");
          } catch {
            return {};
          }
        });
        await page.getByTestId("mark-attention-seen").click();
        await waitForCondition(async () => {
          const stateText = await page
            .locator('[data-testid="current-attention-local-state"]')
            .textContent()
            .catch(() => "");
          return /seen/i.test(String(stateText || ""));
        }, 15000, "Timed out waiting for local attention state to become seen.");
        summary.workspace_actions.push("Mark attention seen");
        summary.local_attention_state_after_seen = String(
          (await page
            .locator('[data-testid="current-attention-local-state"]')
            .textContent()
            .catch(() => "")) || "",
        ).trim();
        await page.screenshot({
          path: path.join(screensDir, `${phase}_10_attention_marked_seen.png`),
          fullPage: true,
        });
        await page.getByTestId("acknowledge-attention").click();
        await waitForCondition(async () => {
          const stateText = await page
            .locator('[data-testid="current-attention-local-state"]')
            .textContent()
            .catch(() => "");
          return /acknowledged/i.test(String(stateText || ""));
        }, 15000, "Timed out waiting for local attention state to become acknowledged.");
        summary.workspace_actions.push("Acknowledge locally");
        summary.local_attention_state_after_acknowledged = String(
          (await page
            .locator('[data-testid="current-attention-local-state"]')
            .textContent()
            .catch(() => "")) || "",
        ).trim();
        localAttentionNoticeText = String(
          (await page.locator('[data-testid="local-attention-notice"]').textContent().catch(() => "")) || "",
        ).trim();
        await page.screenshot({
          path: path.join(screensDir, `${phase}_10a_attention_acknowledged.png`),
          fullPage: true,
        });
        if (staleAttentionEscalationWaitMs > 0) {
          await page.waitForTimeout(staleAttentionEscalationWaitMs);
        }
        await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
        await waitForCondition(
          async () =>
            page
              .locator('[data-testid="current-attention-local-state"]')
              .isVisible()
              .catch(() => false),
          30000,
          "Timed out waiting for durable local attention state after workspace refresh.",
        );
        summary.local_attention_state_after_refresh = String(
          (await page
            .locator('[data-testid="current-attention-local-state"]')
            .textContent()
            .catch(() => "")) || "",
        ).trim();
        attentionMemorySnapshotAfterRefresh = await page.evaluate(() => {
          try {
            return JSON.parse(window.localStorage.getItem("novali.workspace.attentionMemory") || "{}");
          } catch {
            return {};
          }
        });
        if (runStaleAttentionEscalation) {
          await waitForCondition(async () => {
            const staleBannerVisible = await page
              .locator('[data-testid="stale-attention-banner"]')
              .isVisible()
              .catch(() => false);
            if (staleBannerVisible) {
              return true;
            }
            const currentArchiveState = await page
              .locator('[data-testid="handoff-archive-entry"][data-current-entry="true"]')
              .first()
              .getAttribute("data-archive-entry-state")
              .catch(() => "");
            return /stale_escalated_blocking/i.test(String(currentArchiveState || ""));
          }, 15000, "Timed out waiting for stale unresolved attention to escalate locally.");
          summary.stale_attention_visible = true;
          summary.stale_attention_state_after_refresh = String(
            (await page
              .locator('[data-testid="handoff-archive-entry"][data-current-entry="true"]')
              .first()
              .getAttribute("data-archive-entry-state")
              .catch(() => "")) || "",
          ).trim();
          await page.screenshot({
            path: path.join(screensDir, `${phase}_10b_attention_stale_escalated.png`),
            fullPage: true,
          });
          await page.getByTestId("archive-filter-stale").click();
          await waitForCondition(async () => {
            const staleEntries = page.locator(
              '[data-testid="handoff-archive-entry"][data-archive-entry-state="stale_escalated_blocking"]',
            );
            return (await staleEntries.count()) > 0;
          }, 15000, "Timed out waiting for archive triage to isolate stale unresolved entries.");
          const staleEntryCount = await page
            .locator(
              '[data-testid="handoff-archive-entry"][data-archive-entry-state="stale_escalated_blocking"]',
            )
            .count();
          await page
            .locator(
              '[data-testid="handoff-archive-entry"][data-archive-entry-state="stale_escalated_blocking"] [data-testid="open-handoff-archive-entry"]',
            )
            .first()
            .click();
          await waitForCondition(async () => {
            const focusedBlocking = page
              .locator('[data-testid="blocking-attention-item"][data-focused-target="true"]')
              .first();
            return (await focusedBlocking.count()) > 0;
          }, 15000, "Timed out waiting for stale archive triage to focus the exact blocking packet.");
          summary.stale_archive_filter_worked = true;
          summary.workspace_actions.push("Filter stale blockers");
          summary.workspace_actions.push("Open stale archive entry");
          staleAttentionSummary = {
            stale_rule_wait_ms: staleAttentionEscalationWaitMs,
            stale_attention_visible: summary.stale_attention_visible,
            stale_attention_state_after_refresh: summary.stale_attention_state_after_refresh,
            local_attention_state_after_acknowledged: summary.local_attention_state_after_acknowledged,
            local_attention_state_after_refresh: summary.local_attention_state_after_refresh,
          };
          staleArchiveSummary = {
            stale_filter_entry_count: staleEntryCount,
            stale_archive_filter_worked: summary.stale_archive_filter_worked,
            current_entry_state: summary.stale_attention_state_after_refresh,
          };
          await page.screenshot({
            path: path.join(screensDir, `${phase}_10c_archive_stale_triage.png`),
            fullPage: true,
          });
        }
        if (runActionableAttentionDelivery) {
          const archiveEntries = page.locator('[data-testid="handoff-archive-entry"]');
          const archiveEntryCount = await archiveEntries.count();
          summary.archive_navigation_visible = archiveEntryCount > 0;
          const currentArchiveVisible = await page
            .locator('[data-testid="handoff-archive-entry"][data-current-entry="true"]')
            .first()
            .isVisible()
            .catch(() => false);
          const historicalArchiveVisible = await page
            .locator('[data-testid="handoff-archive-entry"][data-current-entry="false"]')
            .first()
            .isVisible()
            .catch(() => false);
          summary.archive_navigation_distinction_visible =
            currentArchiveVisible && historicalArchiveVisible;
          if (historicalArchiveVisible) {
            await page.locator('[data-testid="open-handoff-archive-entry"]').nth(1).click();
            await waitForCondition(async () => {
              return page
                .locator(
                  '[data-testid="handoff-archive-entry"][data-selected-entry="true"][data-current-entry="false"]',
                )
                .first()
                .isVisible()
                .catch(() => false);
            }, 15000, "Timed out waiting for archive selection to focus a historical handoff entry.");
            summary.archive_navigation_worked = true;
            summary.workspace_actions.push("Open archive entry");
          }
          archiveNavigationSummary = {
            archive_entry_count: archiveEntryCount,
            current_archive_visible: currentArchiveVisible,
            historical_archive_visible: historicalArchiveVisible,
            archive_navigation_worked: summary.archive_navigation_worked,
            current_entry_state: String(
              (await page
                .locator('[data-testid="handoff-archive-entry"][data-current-entry="true"]')
                .first()
                .getAttribute("data-archive-entry-state")
                .catch(() => "")) || "",
            ).trim(),
            historical_entry_state: String(
              (await page
                .locator('[data-testid="handoff-archive-entry"][data-current-entry="false"]')
                .first()
                .getAttribute("data-archive-entry-state")
                .catch(() => "")) || "",
            ).trim(),
          };
          await page.screenshot({
            path: path.join(screensDir, `${phase}_10c_handoff_archive_navigation.png`),
            fullPage: true,
          });
        }
        await page.screenshot({
          path: path.join(screensDir, `${phase}_10b_attention_after_refresh.png`),
          fullPage: true,
        });
      }
      writeJson(campaignHandoffSummaryJsonPath, handoffSummary);
      writeText(
        campaignHandoffSummaryMdPath,
        [
          "# campaign handoff summary",
          "",
          `- session handle: \`${handoffSummary.session_handle || "<none>"}\``,
          `- state label: \`${handoffSummary.state_label || "<none>"}\``,
          `- what changed: \`${handoffSummary.what_changed_summary || "<none>"}\``,
          `- blocker: \`${handoffSummary.current_blocker || "<none>"}\``,
          `- next action: \`${handoffSummary.recommended_next_action_label || "<none>"}\``,
          `- next stop: \`${handoffSummary.next_stop_boundary_label || "<none>"}\``,
          "",
        ].join("\n"),
      );
      writeJson(attentionEscalationSummaryJsonPath, {
        attention_signal: attentionSignal,
        attention_banner_visible: summary.attention_banner_visible,
        attention_badge_visible: summary.attention_badge_visible,
        banner_text: bannerText,
        handoff_summary_text: handoffText,
        blocking_count: handoffSummary.attention_blocking_count || 0,
        informational_count: handoffSummary.attention_informational_count || 0,
      });
      writeText(
        attentionEscalationSummaryMdPath,
        [
          "# attention escalation summary",
          "",
          `- severity: \`${attentionSignal.severity || "<none>"}\``,
          `- label: \`${attentionSignal.label || "<none>"}\``,
          `- blocking attention count: \`${attentionSignal.blocking_count ?? "<none>"}\``,
          `- informational attention count: \`${attentionSignal.informational_count ?? "<none>"}\``,
          `- badge visible on re-entry: \`${summary.attention_badge_visible}\``,
          `- banner visible on re-entry: \`${summary.attention_banner_visible}\``,
          "",
        ].join("\n"),
      );
      writeJson(deltaSinceLastTouchSummaryPath, {
        local_touch_marker: localTouchMarker,
        delta_since_last_resume: deltaSinceLastResume,
        visible_summary_text: sinceLastTouchText,
        campaign_handoff_text: handoffText,
      });
      writeText(
        operatorReentryJourneyPath,
        [
          "# operator re-entry journey",
          "",
          "- operator left the workspace after a blocking attention boundary and returned to the same session view.",
          `- attention badge visible: \`${summary.attention_badge_visible}\``,
          `- attention banner visible: \`${summary.attention_banner_visible}\``,
          `- handoff summary visible: \`${summary.campaign_handoff_visible}\``,
          `- since-last-touch summary visible: \`${summary.since_last_touch_visible}\``,
          `- handoff summary text: ${handoffText || "<none>"}`,
          `- local delta text: ${sinceLastTouchText || "<none>"}`,
          "",
        ].join("\n"),
      );
      if (runLocalAttentionDelivery) {
        writeJson(localAttentionDeliverySummaryJsonPath, {
          notification_permission: summary.notification_permission,
          local_attention_delivery_mode: summary.local_attention_delivery_mode,
          attention_signal: attentionSignal,
          local_attention_state_before: summary.local_attention_state_before,
          local_attention_state_after_seen: summary.local_attention_state_after_seen,
          local_attention_state_after_acknowledged: summary.local_attention_state_after_acknowledged,
          local_attention_state_after_refresh: summary.local_attention_state_after_refresh,
          local_attention_notice: localAttentionNoticeText,
          attention_badge_visible: summary.attention_badge_visible,
          attention_banner_visible: summary.attention_banner_visible,
          delivery_panel_text: deliveryPanelText,
        });
        writeText(
          localAttentionDeliverySummaryMdPath,
          [
            "# local attention delivery summary",
            "",
            `- notification permission: \`${summary.notification_permission || "unknown"}\``,
            `- delivery mode: \`${summary.local_attention_delivery_mode || "unknown"}\``,
            `- local state before action: \`${summary.local_attention_state_before || "<none>"}\``,
            `- local state after seen: \`${summary.local_attention_state_after_seen || "<none>"}\``,
            `- local state after acknowledged: \`${summary.local_attention_state_after_acknowledged || "<none>"}\``,
            `- local state after refresh: \`${summary.local_attention_state_after_refresh || "<none>"}\``,
            `- attention badge visible: \`${summary.attention_badge_visible}\``,
            `- attention banner visible: \`${summary.attention_banner_visible}\``,
            "",
          ].join("\n"),
        );
        writeJson(durableHandoffMemorySummaryJsonPath, {
          current_session_id: reentryLongRun.json?.long_run?.session_id || "",
          durable_handoff_memory_visible: summary.durable_handoff_memory_visible,
          local_state_after_refresh: summary.local_attention_state_after_refresh,
          handoff_summary: handoffSummary,
          delta_since_last_resume: deltaSinceLastResume,
          attention_memory_before: attentionMemorySnapshotBefore,
          attention_memory_after_refresh: attentionMemorySnapshotAfterRefresh,
        });
        writeText(
          durableHandoffMemorySummaryMdPath,
          [
            "# durable handoff memory summary",
            "",
            `- durable history visible: \`${summary.durable_handoff_memory_visible}\``,
            `- session handle: \`${handoffSummary.session_handle || "<none>"}\``,
            `- local state after refresh: \`${summary.local_attention_state_after_refresh || "<none>"}\``,
            `- what changed summary: \`${handoffSummary.what_changed_summary || "<none>"}\``,
            `- blocker: \`${handoffSummary.current_blocker || "<none>"}\``,
            `- next action: \`${handoffSummary.recommended_next_action_label || "<none>"}\``,
            "",
          ].join("\n"),
        );
        writeJson(attentionStateTransitionMatrixPath, {
          session_id: reentryLongRun.json?.long_run?.session_id || "",
          transitions: [
            { state: "new", observed_label: summary.local_attention_state_before || "new" },
            { state: "seen", observed_label: summary.local_attention_state_after_seen || "" },
            { state: "acknowledged", observed_label: summary.local_attention_state_after_acknowledged || "" },
            { state: "acknowledged_after_refresh", observed_label: summary.local_attention_state_after_refresh || "" },
          ],
        });
        writeText(
          operatorReentryAfterRefreshSummaryPath,
          [
            "# operator re-entry after refresh summary",
            "",
            `- workspace re-opened on same session: \`${reentryLongRun.json?.long_run?.session_id || "<none>"}\``,
            `- notification permission: \`${summary.notification_permission || "unknown"}\``,
            `- delivery mode on re-entry: \`${summary.local_attention_delivery_mode || "unknown"}\``,
            `- local state before refresh: \`${summary.local_attention_state_after_acknowledged || "<none>"}\``,
            `- local state after refresh: \`${summary.local_attention_state_after_refresh || "<none>"}\``,
            `- handoff summary text: ${handoffText || "<none>"}`,
            "",
          ].join("\n"),
        );
        if (runActionableAttentionDelivery) {
          writeJson(actionableAttentionSummaryJsonPath, {
            attention_signal: attentionSignal,
            clicked_signal: "attention-signal-banner",
            focus_actionable: summary.attention_signal_click_actionable,
            focus_target_kind: summary.attention_focus_target_kind,
            focus_target_id: summary.attention_focus_target_id,
            focus_target_label: summary.attention_focus_target_label,
            local_attention_state_after_seen: summary.local_attention_state_after_seen,
            local_attention_state_after_acknowledged: summary.local_attention_state_after_acknowledged,
          });
          writeText(
            actionableAttentionSummaryMdPath,
            [
              "# actionable attention summary",
              "",
              `- attention signal clickable: \`${summary.attention_signal_click_actionable}\``,
              `- focus target kind: \`${summary.attention_focus_target_kind || "<none>"}\``,
              `- focus target id: \`${summary.attention_focus_target_id || "<none>"}\``,
              `- focus target label: ${summary.attention_focus_target_label || "<none>"}`,
              "",
            ].join("\n"),
          );
          writeJson(attentionClickToPacketSequencePath, attentionClickSequence);
          writeJson(handoffArchiveNavigationSummaryJsonPath, archiveNavigationSummary);
          writeText(
            handoffArchiveNavigationSummaryMdPath,
            [
              "# handoff archive navigation summary",
              "",
              `- archive visible: \`${summary.archive_navigation_visible}\``,
              `- current vs historical distinction visible: \`${summary.archive_navigation_distinction_visible}\``,
              `- archive navigation worked: \`${summary.archive_navigation_worked}\``,
              `- current archive state: \`${archiveNavigationSummary.current_entry_state || "<none>"}\``,
              `- historical archive state: \`${archiveNavigationSummary.historical_entry_state || "<none>"}\``,
              "",
            ].join("\n"),
          );
          writeText(
            operatorReentryWithArchiveSummaryPath,
            [
              "# operator re-entry with archive summary",
              "",
              `- same session on re-entry: \`${reentryLongRun.json?.long_run?.session_id || "<none>"}\``,
              `- current attention state after refresh: \`${summary.local_attention_state_after_refresh || "<none>"}\``,
              `- archive current entry state: \`${archiveNavigationSummary.current_entry_state || "<none>"}\``,
              `- archive historical entry state: \`${archiveNavigationSummary.historical_entry_state || "<none>"}\``,
              `- archive navigation worked: \`${summary.archive_navigation_worked}\``,
              "",
            ].join("\n"),
          );
        }
        if (runStaleAttentionEscalation) {
          writeJson(staleAttentionEscalationSummaryJsonPath, staleAttentionSummary);
          writeText(
            staleAttentionEscalationSummaryMdPath,
            [
              "# stale attention escalation summary",
              "",
              `- stale attention visible: \`${summary.stale_attention_visible}\``,
              `- stale archive state after refresh: \`${summary.stale_attention_state_after_refresh || "<none>"}\``,
              `- local state after acknowledgment: \`${summary.local_attention_state_after_acknowledged || "<none>"}\``,
              `- local state after refresh: \`${summary.local_attention_state_after_refresh || "<none>"}\``,
              "",
            ].join("\n"),
          );
          writeJson(archiveTriageNavigationSummaryJsonPath, staleArchiveSummary);
          writeText(
            archiveTriageNavigationSummaryMdPath,
            [
              "# archive triage navigation summary",
              "",
              `- stale filter worked: \`${summary.stale_archive_filter_worked}\``,
              `- stale entry count: \`${staleArchiveSummary.stale_filter_entry_count || 0}\``,
              `- current stale archive state: \`${summary.stale_attention_state_after_refresh || "<none>"}\``,
              "",
            ].join("\n"),
          );
          writeText(
            operatorReentryWithStaleAttentionSummaryPath,
            [
              "# operator re-entry with stale attention summary",
              "",
              `- same session on re-entry: \`${reentryLongRun.json?.long_run?.session_id || "<none>"}\``,
              `- stale unresolved blocker visible: \`${summary.stale_attention_visible}\``,
              `- stale archive filter worked: \`${summary.stale_archive_filter_worked}\``,
              "",
            ].join("\n"),
          );
        }
      }
      await page.screenshot({
        path: path.join(screensDir, `${phase}_10_reentry_handoff.png`),
        fullPage: true,
      });
      pushStep("campaign_handoff_reentry_verified", {
        attention_badge_visible: summary.attention_badge_visible,
        attention_banner_visible: summary.attention_banner_visible,
        campaign_handoff_visible: summary.campaign_handoff_visible,
      });
    }

    const firstResolution = await resolveAttentionBoundary({
      boundaryScreenshotName: `${phase}_11_intervention_required.png`,
      resolutionScreenshotName: `${phase}_12_intervention_resolution.png`,
      stepPrefix: "intervention",
    });
    const resolvedIntervention = firstResolution.resolvedIntervention;
    const interventionActions = firstResolution.actions;

    writeJson(interventionAfterResolutionPath, resolvedIntervention.intervention || {});
    writeJson(
      attentionInboxAfterResolutionPath,
      resolvedIntervention.long_run?.operator_guidance?.attention_inbox ||
        resolvedIntervention.intervention?.attention_inbox ||
        {},
    );

    if (runCampaignLoop) {
      const initialBudgetGuidance = beforeLongRun.operator_guidance || {};
      const initialBudgetSignal = `${String(initialBudgetGuidance.next_stop_boundary_label || "")} ${String(initialBudgetGuidance.next_stop_boundary_summary || "")} ${String(initialBudgetGuidance.blocking_reason || "")}`.toLowerCase();
      const initialBudgetBoundary =
        /budget/.test(String(beforeLongRun.long_run?.halt_reason || "").toLowerCase()) ||
        /budget|headroom|cycle/.test(initialBudgetSignal);
      if (initialBudgetBoundary) {
        budgetBoundarySummary = {
          session_id: beforeLongRun.long_run?.session_id || "",
          lifecycle_state: beforeLongRun.long_run?.lifecycle_state || "",
          halt_reason:
            beforeLongRun.long_run?.halt_reason ||
            beforeLongRun.long_run?.completion_state ||
            "",
          current_cycle: Number(beforeLongRun.long_run?.current_cycle || 0),
          checkpoint_count: Number(beforeLongRun.long_run?.checkpoint_count || 0),
          max_total_cycles: Number(beforeLongRun.effective_policy?.max_total_cycles || 0),
          cycles_remaining: Number(
            beforeLongRun.effective_policy?.cycles_remaining ??
              beforeLongRun.long_run?.budget_remaining?.remaining_cycles ??
              -1,
          ),
          next_stop_boundary_label: String(initialBudgetGuidance.next_stop_boundary_label || ""),
          next_stop_boundary_summary: String(initialBudgetGuidance.next_stop_boundary_summary || ""),
          blocking_reason: String(
            initialBudgetGuidance.primary_cta?.blocked_reason || initialBudgetGuidance.blocking_reason || "",
          ),
          primary_cta_label: String(initialBudgetGuidance.primary_cta?.label || ""),
          primary_cta_action_id: String(initialBudgetGuidance.primary_cta?.action_id || ""),
          budget_boundary_proven: true,
          boundary_stage: "initial_workspace_budget_boundary",
        };
        summary.budget_boundary_proven = true;
        writeJson(budgetBoundarySummaryPath, budgetBoundarySummary);
      }
    }

    const postInterventionReady = await waitForCondition(async () => {
      const result = await fetchJson(request, "/long-run-state", baseUrl);
      const primaryAction = String(result.json?.operator_guidance?.primary_cta?.action_id || "").trim();
      const primaryLabel = String(result.json?.operator_guidance?.primary_cta?.label || "").trim();
      if (primaryAction === "continue" || /continue|resume/i.test(primaryLabel)) {
        return result.json;
      }
      return null;
    }, 180000, "Timed out waiting for same-session continuation to become available after intervention resolution.");

    const postInterventionBeforeResume = postInterventionReady.long_run || {};
    const postInterventionContinueLabel = String(
      postInterventionReady.operator_guidance?.primary_cta?.label || "Continue bounded session",
    ).trim();
    summary.workspace_actions.push(postInterventionContinueLabel);
    await waitForCondition(
      async () => page.locator('[data-testid="long-run-primary-cta"]').isEnabled(),
      120000,
      "Timed out waiting for the post-intervention continuation CTA to enable.",
    );
    const postInterventionContinueResponsePromise = page.waitForResponse(
      (resp) => resp.url().includes("/shell/api/long-run/continue") && resp.request().method() === "POST",
      { timeout: 180000 },
    );
    await page.locator('[data-testid="long-run-primary-cta"]').click();
    const postInterventionContinueResponse = await postInterventionContinueResponsePromise;
    const postInterventionContinuePayload = await safeResponseJson(postInterventionContinueResponse);
    requestSequence.push({
      step: "continue_after_intervention",
      control_label: postInterventionContinueLabel,
      response_status: postInterventionContinueResponse.status(),
      response_payload: postInterventionContinuePayload,
    });
    await page.screenshot({
      path: path.join(screensDir, `${phase}_13_during_post_intervention_resume.png`),
      fullPage: true,
    });

    const afterPostIntervention = await waitForCondition(async () => {
      const result = await fetchJson(request, "/long-run-state", baseUrl);
      const longRun = result.json?.long_run || {};
      if (!longRun.session_id || longRun.session_id !== beforeLongRun.long_run.session_id) {
        return null;
      }
      const cycleAdvanced =
        Number(longRun.current_cycle || 0) >= Number(postInterventionBeforeResume.current_cycle || 0) + 1;
      const checkpointAdvanced =
        Number(longRun.checkpoint_count || 0) >= Number(postInterventionBeforeResume.checkpoint_count || 0) + 1;
      if (cycleAdvanced || checkpointAdvanced) {
        return result.json;
      }
      return null;
    }, 600000, "Timed out waiting for the same session to advance again after intervention resolution.");

    await page.screenshot({
      path: path.join(screensDir, `${phase}_14_workspace_after_post_intervention_resume.png`),
      fullPage: true,
    });
    postInterventionSummary = {
      session_id_before_intervention: interventionBoundaryState.long_run?.session_id || "",
      session_id_after_intervention: afterPostIntervention.long_run?.session_id || "",
      same_session_preserved:
        String(interventionBoundaryState.long_run?.session_id || "") ===
        String(afterPostIntervention.long_run?.session_id || ""),
      checkpoint_count_before_intervention: Number(interventionBoundaryState.long_run?.checkpoint_count || 0),
      checkpoint_count_before_resume: Number(postInterventionBeforeResume.checkpoint_count || 0),
      checkpoint_count_after_resume: Number(afterPostIntervention.long_run?.checkpoint_count || 0),
      current_cycle_before_intervention: Number(interventionBoundaryState.long_run?.current_cycle || 0),
      current_cycle_before_resume: Number(postInterventionBeforeResume.current_cycle || 0),
      current_cycle_after_resume: Number(afterPostIntervention.long_run?.current_cycle || 0),
      checkpoint_delta_after_resume:
        Number(afterPostIntervention.long_run?.checkpoint_count || 0) -
        Number(postInterventionBeforeResume.checkpoint_count || 0),
      cycle_delta_after_resume:
        Number(afterPostIntervention.long_run?.current_cycle || 0) -
        Number(postInterventionBeforeResume.current_cycle || 0),
      resume_from_checkpoint_id_after_resume: afterPostIntervention.long_run?.resume_from_checkpoint_id || "",
      latest_checkpoint_id_after_resume: afterPostIntervention.long_run?.latest_checkpoint_id || "",
      halt_reason_after_resume:
        afterPostIntervention.long_run?.halt_reason || afterPostIntervention.long_run?.completion_state || "",
      intervention_actions: interventionActions,
      intervention_state_before_resolution: interventionBoundaryIntervention.json || {},
      intervention_state_after_resolution: resolvedIntervention.intervention || {},
      long_run_before_resume: postInterventionReady.long_run || {},
      long_run_after_resume: afterPostIntervention.long_run || {},
    };
    writeJson(postInterventionIdentityPath, postInterventionSummary);

    let secondBoundaryActions = [];
    let secondBoundarySummary = null;
    let finalCampaignState = afterPostIntervention;
    if (runCampaignLoop) {
      const secondBoundaryIntervention = await fetchJson(request, "/intervention-state", baseUrl);
      const secondBoundaryRequiresAttention =
        afterPostIntervention.long_run?.halt_reason === "intervention_required" ||
        afterPostIntervention.long_run?.watchdog_state === "intervention_required" ||
        secondBoundaryIntervention.json?.intervention_required ||
        secondBoundaryIntervention.json?.review_required;
      if (secondBoundaryRequiresAttention) {
        const secondResolution = await resolveAttentionBoundary({
          boundaryScreenshotName: `${phase}_15_second_attention_boundary.png`,
          resolutionScreenshotName: `${phase}_16_second_attention_resolution.png`,
          stepPrefix: "second_attention",
        });
        secondBoundaryActions = secondResolution.actions;
        secondBoundarySummary = {
          type: "intervention",
          halt_reason:
            afterPostIntervention.long_run?.halt_reason ||
            afterPostIntervention.long_run?.completion_state ||
            "",
          current_cycle: Number(afterPostIntervention.long_run?.current_cycle || 0),
          checkpoint_count: Number(afterPostIntervention.long_run?.checkpoint_count || 0),
          intervention_state_before_resolution: secondResolution.boundaryIntervention.json || {},
          intervention_state_after_resolution: secondResolution.resolvedIntervention.intervention || {},
          actions: secondBoundaryActions,
        };
        finalCampaignState = secondResolution.resolvedIntervention.long_run || afterPostIntervention;
      } else {
        const secondBoundaryGuidance = afterPostIntervention.operator_guidance || {};
        const secondBoundarySignal = `${String(secondBoundaryGuidance.next_stop_boundary_label || "")} ${String(secondBoundaryGuidance.next_stop_boundary_summary || "")} ${String(secondBoundaryGuidance.blocking_reason || "")} ${String(secondBoundaryGuidance.primary_cta?.blocked_reason || "")}`.toLowerCase();
        const secondBoundaryBudget =
          /budget/.test(String(afterPostIntervention.long_run?.halt_reason || "").toLowerCase()) ||
          /budget|headroom|cycle/.test(secondBoundarySignal);
        if (!secondBoundaryBudget) {
          throw new Error("Timed out waiting for the repeat campaign loop to surface a second explicit attention or budget boundary.");
        }
        secondBoundarySummary = {
          type: "budget_headroom",
          halt_reason:
            afterPostIntervention.long_run?.halt_reason ||
            afterPostIntervention.long_run?.completion_state ||
            "",
          current_cycle: Number(afterPostIntervention.long_run?.current_cycle || 0),
          checkpoint_count: Number(afterPostIntervention.long_run?.checkpoint_count || 0),
        };
        if (!budgetBoundarySummary) {
          budgetBoundarySummary = {
            session_id: afterPostIntervention.long_run?.session_id || "",
            lifecycle_state: afterPostIntervention.long_run?.lifecycle_state || "",
            halt_reason:
              afterPostIntervention.long_run?.halt_reason ||
              afterPostIntervention.long_run?.completion_state ||
              "",
            current_cycle: Number(afterPostIntervention.long_run?.current_cycle || 0),
            checkpoint_count: Number(afterPostIntervention.long_run?.checkpoint_count || 0),
            max_total_cycles: Number(afterPostIntervention.effective_policy?.max_total_cycles || 0),
            cycles_remaining: Number(
              afterPostIntervention.effective_policy?.cycles_remaining ??
                afterPostIntervention.long_run?.budget_remaining?.remaining_cycles ??
                -1,
            ),
            next_stop_boundary_label: String(secondBoundaryGuidance.next_stop_boundary_label || ""),
            next_stop_boundary_summary: String(secondBoundaryGuidance.next_stop_boundary_summary || ""),
            blocking_reason: String(
              secondBoundaryGuidance.primary_cta?.blocked_reason || secondBoundaryGuidance.blocking_reason || "",
            ),
            primary_cta_label: String(secondBoundaryGuidance.primary_cta?.label || ""),
            primary_cta_action_id: String(secondBoundaryGuidance.primary_cta?.action_id || ""),
            budget_boundary_proven: true,
            boundary_stage: "post_intervention_campaign_boundary",
          };
          summary.budget_boundary_proven = true;
          writeJson(budgetBoundarySummaryPath, budgetBoundarySummary);
        }
      }
      campaignLoopSummary = {
        phase,
        session_id: beforeLongRun.long_run.session_id,
        same_session_preserved:
          String(beforeLongRun.long_run.session_id || "") ===
            String(afterPostIntervention.long_run?.session_id || "") &&
          (!secondBoundarySummary ||
            String(beforeLongRun.long_run.session_id || "") ===
              String(finalCampaignState.long_run?.session_id || "")),
        workspace_actions: summary.workspace_actions,
        first_boundary: {
          type: "intervention",
          halt_reason:
            interventionBoundaryState.long_run?.halt_reason ||
            interventionBoundaryState.long_run?.completion_state ||
            "",
          current_cycle: Number(interventionBoundaryState.long_run?.current_cycle || 0),
          checkpoint_count: Number(interventionBoundaryState.long_run?.checkpoint_count || 0),
          attention_inbox:
            interventionBoundaryState.operator_guidance?.attention_inbox ||
            interventionBoundaryIntervention.json?.attention_inbox ||
            {},
          actions: interventionActions,
        },
        second_boundary: secondBoundarySummary
          ? {
              type: secondBoundarySummary.type,
              halt_reason: secondBoundarySummary.halt_reason || "",
              current_cycle: Number(secondBoundarySummary.current_cycle || 0),
              checkpoint_count: Number(secondBoundarySummary.checkpoint_count || 0),
              actions: secondBoundaryActions,
              after_resolution: secondBoundarySummary.intervention_state_after_resolution,
            }
          : {
              type: "budget_headroom",
              halt_reason:
                afterPostIntervention.long_run?.halt_reason ||
                afterPostIntervention.long_run?.completion_state ||
                "",
              current_cycle: Number(afterPostIntervention.long_run?.current_cycle || 0),
              checkpoint_count: Number(afterPostIntervention.long_run?.checkpoint_count || 0),
            },
        post_intervention_resume: postInterventionSummary,
        budget_boundary: budgetBoundarySummary,
      };
      writeJson(sameSessionCampaignIdentityPath, {
        session_id_before: beforeLongRun.long_run.session_id,
        session_id_after_first_resume: afterPostIntervention.long_run?.session_id || "",
        session_id_final: finalCampaignState.long_run?.session_id || "",
        same_session_preserved: campaignLoopSummary.same_session_preserved,
        current_cycle_before: Number(beforeLongRun.long_run.current_cycle || 0),
        current_cycle_after_first_resume: Number(afterPostIntervention.long_run?.current_cycle || 0),
        current_cycle_final: Number(finalCampaignState.long_run?.current_cycle || 0),
        checkpoint_count_before: Number(beforeLongRun.long_run.checkpoint_count || 0),
        checkpoint_count_after_first_resume: Number(afterPostIntervention.long_run?.checkpoint_count || 0),
        checkpoint_count_final: Number(finalCampaignState.long_run?.checkpoint_count || 0),
      });
      writeJson(campaignLoopSummaryJsonPath, campaignLoopSummary);
      writeText(
        campaignLoopSummaryMdPath,
        [
          "# campaign loop summary",
          "",
          `- same session preserved: \`${campaignLoopSummary.same_session_preserved}\``,
          `- workspace actions: ${summary.workspace_actions.join(" -> ") || "<none>"}`,
          `- first boundary: \`${campaignLoopSummary.first_boundary.type}\` at cycle \`${campaignLoopSummary.first_boundary.current_cycle}\` / checkpoint \`${campaignLoopSummary.first_boundary.checkpoint_count}\``,
          `- second boundary: \`${campaignLoopSummary.second_boundary.type}\` at cycle \`${campaignLoopSummary.second_boundary.current_cycle}\` / checkpoint \`${campaignLoopSummary.second_boundary.checkpoint_count}\``,
          `- budget/headroom boundary: \`${budgetBoundarySummary.next_stop_boundary_label || "<none>"}\``,
          `- budget/headroom detail: \`${budgetBoundarySummary.next_stop_boundary_summary || "<none>"}\``,
          "",
        ].join("\n"),
      );
      writeText(
        operatorAttentionJourneyPath,
        [
          "# operator attention journey",
          "",
          `- first intervention boundary: \`${interventionBoundaryState.long_run?.halt_reason || interventionBoundaryState.long_run?.completion_state || "<none>"}\``,
          `- first packet actions: ${interventionActions.map((item) => `${item.action_label} (${item.review_item_title})`).join(" -> ") || "<none>"}`,
          `- second continuation action: \`${postInterventionContinueLabel || "<none>"}\``,
          `- second boundary: \`${campaignLoopSummary.second_boundary.type}\``,
          `- second packet actions: ${secondBoundaryActions.map((item) => `${item.action_label} (${item.review_item_title})`).join(" -> ") || "<none>"}`,
          `- final budget/headroom boundary: \`${budgetBoundarySummary.next_stop_boundary_label || "<none>"}\``,
          "",
        ].join("\n"),
      );
    }

    writeJson(interventionLoopSummaryJsonPath, {
      phase,
      intervention_actions: interventionActions,
      intervention_state_before_resolution: interventionBoundaryIntervention.json || {},
      intervention_state_after_resolution: resolvedIntervention.intervention || {},
      same_session_resume_after_intervention: postInterventionSummary,
      second_boundary: secondBoundarySummary,
      budget_boundary: budgetBoundarySummary,
    });
    writeText(
      interventionLoopSummaryMdPath,
      [
        "# intervention loop summary",
        "",
        `- same session preserved after intervention: \`${postInterventionSummary.same_session_preserved}\``,
        `- intervention actions: ${interventionActions.map((item) => item.action_label).join(" -> ") || "<none>"}`,
        `- cycle delta after post-intervention resume: \`${postInterventionSummary.cycle_delta_after_resume}\``,
        `- checkpoint delta after post-intervention resume: \`${postInterventionSummary.checkpoint_delta_after_resume}\``,
        `- halt/completion reason after post-intervention resume: \`${postInterventionSummary.halt_reason_after_resume || "<none>"}\``,
        budgetBoundarySummary
          ? `- explicit budget/headroom boundary: \`${budgetBoundarySummary.next_stop_boundary_label || "<none>"}\``
          : "- explicit budget/headroom boundary: <not requested in this phase>",
        "",
      ].join("\n"),
    );
    writeText(
      operatorInterventionJourneyPath,
      [
        "# operator intervention journey",
        "",
        `- session id before intervention: \`${postInterventionSummary.session_id_before_intervention || "<none>"}\``,
        `- first intervention boundary: \`${interventionBoundaryState.long_run?.halt_reason || interventionBoundaryState.long_run?.completion_state || "<none>"}\``,
        `- intervention actions taken in workspace: ${interventionActions.map((item) => `${item.action_label} (${item.review_item_title})`).join(" -> ") || "<none>"}`,
        `- post-intervention continuation action: \`${postInterventionContinueLabel || "<none>"}\``,
        `- session id after post-intervention resume: \`${postInterventionSummary.session_id_after_intervention || "<none>"}\``,
        `- cycle delta after resume: \`${postInterventionSummary.cycle_delta_after_resume}\``,
        `- checkpoint delta after resume: \`${postInterventionSummary.checkpoint_delta_after_resume}\``,
        `- final halt/completion reason: \`${postInterventionSummary.halt_reason_after_resume || "<none>"}\``,
        "",
      ].join("\n"),
    );
    pushStep("intervention_loop_completed", {
      session_id: postInterventionSummary.session_id_after_intervention,
      cycle_delta_after_resume: postInterventionSummary.cycle_delta_after_resume,
      checkpoint_delta_after_resume: postInterventionSummary.checkpoint_delta_after_resume,
      budget_boundary_proven: summary.budget_boundary_proven,
    });
  }

  const routesToCheck = ["/healthz", "/", "/shell", "/workspace", "/shell/workspace"];
  const routeValidation = {};
  for (const route of routesToCheck) {
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
  summary.workspace_action_count = summary.workspace_actions.length;

  writeJson(routeValidationPath, routeValidation);
  writeJson(packagedRouteValidationPath, routeValidation);
  writeJson(stateMappingPath, {
    phase,
    session_id_before: beforeLongRun.long_run.session_id,
    session_id_after: afterLongRun.long_run.session_id,
    same_session_preserved: beforeLongRun.long_run.session_id === afterLongRun.long_run.session_id,
    before: {
      lifecycle_state: beforeLongRun.long_run.lifecycle_state,
      checkpoint_count: beforeLongRun.long_run.checkpoint_count,
      current_cycle: beforeLongRun.long_run.current_cycle,
      resume_available: beforeLongRun.long_run.resume_available,
      primary_cta: beforeLongRun.operator_guidance?.primary_cta || {},
    },
    after: {
      lifecycle_state: afterLongRun.long_run.lifecycle_state,
      checkpoint_count: afterLongRun.long_run.checkpoint_count,
      current_cycle: afterLongRun.long_run.current_cycle,
      resume_available: afterLongRun.long_run.resume_available,
      primary_cta: afterLongRun.operator_guidance?.primary_cta || {},
    },
  });
  writeJson(beforeStatePath, beforeLongRun.json || beforeLongRun);
  writeJson(afterApprovalStatePath, summary.long_run_after_approval || {});
  writeJson(afterContinuationStatePath, afterLongRun.json || afterLongRun);
  writeJson(requestSequencePath, requestSequence);
  writeJson(identityCheckPath, {
    session_id_before: beforeLongRun.long_run.session_id,
    session_id_after: afterLongRun.long_run.session_id,
    same_session_preserved: beforeLongRun.long_run.session_id === afterLongRun.long_run.session_id,
    checkpoint_count_before: beforeLongRun.long_run.checkpoint_count,
    checkpoint_count_after: afterLongRun.long_run.checkpoint_count,
    current_cycle_before: beforeLongRun.long_run.current_cycle,
    current_cycle_after: afterLongRun.long_run.current_cycle,
    latest_checkpoint_before: beforeLongRun.long_run.latest_checkpoint_id,
    latest_checkpoint_after: afterLongRun.long_run.latest_checkpoint_id,
    resume_from_checkpoint_id_after: afterLongRun.long_run.resume_from_checkpoint_id,
  });
  writeJson(policyBeforeAfterJsonPath, {
    phase,
    session_id: beforeLongRun.long_run.session_id,
    before_policy: summary.policy_before,
    target_policy: summary.policy_target,
    effective_policy_after_save: summary.policy_after_save,
    long_run_before: summary.long_run_before,
    long_run_after: summary.long_run_after,
  });
  writeText(
    policyBeforeAfterMdPath,
    [
      "# long-run policy before/after",
      "",
      `- session id: \`${beforeLongRun.long_run.session_id || "<none>"}\``,
      `- before strategy: \`${summary.policy_before?.continuation_strategy_label || summary.policy_before?.continuation_strategy || "<none>"}\``,
      `- target strategy: \`${summary.policy_target?.continuation_strategy || "<none>"}\``,
      `- target max total cycles: \`${summary.policy_target?.max_total_cycles || "<none>"}\``,
      `- target max cycles per invocation: \`${summary.policy_target?.max_cycles_per_invocation || "<none>"}\``,
      `- effective after save strategy: \`${summary.policy_after_save?.continuation_strategy_label || summary.policy_after_save?.continuation_strategy || "<none>"}\``,
      `- effective after save max total cycles: \`${summary.policy_after_save?.max_total_cycles || "<none>"}\``,
      `- effective after save max cycles per invocation: \`${summary.policy_after_save?.max_cycles_per_invocation || "<none>"}\``,
      "",
    ].join("\n"),
  );
  writeJson(policyRoundtripSummaryPath, {
    phase,
    before_policy: summary.policy_before,
    target_policy: summary.policy_target,
    after_save_policy: summary.policy_after_save,
    roundtrip_ok:
      String(summary.policy_after_save?.continuation_strategy || "").trim() ===
        String(summary.policy_target?.continuation_strategy || "").trim() &&
      Number(summary.policy_after_save?.max_total_cycles || 0) >=
        Number(summary.policy_target?.max_total_cycles || 0) &&
      Number(summary.policy_after_save?.max_cycles_per_invocation || 0) >=
        Number(summary.policy_target?.max_cycles_per_invocation || 0),
  });
  writeJson(lowTouchSummaryJsonPath, {
    phase,
    session_id_before: beforeLongRun.long_run.session_id,
    session_id_after: afterLongRun.long_run.session_id,
    same_session_preserved: beforeLongRun.long_run.session_id === afterLongRun.long_run.session_id,
    workspace_actions: summary.workspace_actions,
    workspace_action_count: summary.workspace_action_count,
    cycle_delta: summary.cycle_delta,
    checkpoint_delta: summary.checkpoint_delta,
    multi_boundary_advance: summary.multi_boundary_advance,
    before_lifecycle_state: beforeLongRun.long_run.lifecycle_state,
    after_lifecycle_state: afterLongRun.long_run.lifecycle_state,
    final_halt_reason: afterLongRun.long_run.halt_reason || afterLongRun.long_run.completion_state || "",
    policy_after_save: summary.policy_after_save,
  });
  writeText(
    lowTouchSummaryMdPath,
    [
      "# low-touch continuation summary",
      "",
      `- same session preserved: \`${beforeLongRun.long_run.session_id === afterLongRun.long_run.session_id}\``,
      `- workspace actions: ${summary.workspace_actions.join(" -> ") || "<none>"}`,
      `- cycle delta: \`${summary.cycle_delta}\``,
      `- checkpoint delta: \`${summary.checkpoint_delta}\``,
      `- multi-boundary advance proven: \`${summary.multi_boundary_advance}\``,
      `- final stop/completion reason: \`${afterLongRun.long_run.halt_reason || afterLongRun.long_run.completion_state || "<none>"}\``,
      "",
    ].join("\n"),
  );
  writeJson(governedStartSummaryJsonPath, {
    phase,
    governed_start: summary.governed_start || {},
    request_sequence_entry: requestSequence.find((item) => item.step === "governed_start") || null,
  });
  writeText(
    governedStartSummaryMdPath,
    [
      "# governed start contract summary",
      "",
      `- status: \`${summary.governed_start?.status ?? "n/a"}\``,
      `- ok: \`${summary.governed_start?.ok === true}\``,
      `- next_path: \`${summary.governed_start?.next_path || ""}\``,
      "",
    ].join("\n"),
  );
  writeJson(longRunClaritySummaryJsonPath, {
    phase,
    primary_cta_label: summary.primary_cta_label,
    review_gate_visible: summary.review_gate_visible,
    inline_blocking_reason_visible: summary.inline_blocking_reason_visible,
    headroom_visible: summary.headroom_visible,
    settings_visible: summary.settings_visible,
    session_handle_visible: summary.session_handle_visible,
    workspace_action_count: summary.workspace_action_count,
    workspace_actions: summary.workspace_actions,
    pause_resume_evidence: pauseResumeEvidence,
    policy_before: summary.policy_before,
    policy_after_save: summary.policy_after_save,
    long_run_before: summary.long_run_before,
    long_run_after: summary.long_run_after,
  });
  writeText(
    longRunClaritySummaryMdPath,
    [
      "# long-run control clarity summary",
      "",
      `- primary CTA: \`${summary.primary_cta_label || "n/a"}\``,
      `- inline blocking reason visible: \`${summary.inline_blocking_reason_visible}\``,
      `- headroom visible: \`${summary.headroom_visible}\``,
      `- settings visible: \`${summary.settings_visible}\``,
      `- effective policy after save: \`${summary.policy_after_save?.continuation_strategy_label || summary.policy_after_save?.continuation_strategy || "<none>"}\``,
      `- workspace actions: ${summary.workspace_actions.join(" -> ") || "<none>"}`,
      "",
    ].join("\n"),
  );
  writeText(
    operatorJourneyNotePath,
    [
      "# operator journey friction note",
      "",
      `- Workspace actions from first arrival to successful same-session continuation: ${summary.workspace_action_count}`,
      `- Actions used: ${summary.workspace_actions.join(" -> ") || "<none>"}`,
      `- Inline blocking reason visible: ${summary.inline_blocking_reason_visible}`,
      `- Headroom visible: ${summary.headroom_visible}`,
      `- Settings visible: ${summary.settings_visible}`,
      `- Policy edited from workspace: ${!!summary.policy_after_save?.continuation_strategy}`,
      "",
    ].join("\n"),
  );

  summary.success = true;
} catch (error) {
  summary.failures.push(error?.message || String(error));
  pushStep("failure", { message: error?.message || String(error) });
  try {
    await page.screenshot({
      path: path.join(screensDir, `${phase}_zz_failure.png`),
      fullPage: true,
    });
  } catch {}
} finally {
  summary.workspace_action_count = summary.workspace_actions.length;
  writeJson(runSummaryPath, summary);
  writeText(
    runMarkdownPath,
    [
      `# ${phase} operator journey`,
      "",
      `- success: \`${summary.success}\``,
      `- directive path: \`${summary.directive_path_used}\``,
      `- workspace action count: \`${summary.workspace_action_count}\``,
      `- workspace actions: ${summary.workspace_actions.join(" -> ") || "<none>"}`,
      `- primary CTA visible: \`${summary.primary_cta_present}\``,
      `- primary CTA label: \`${summary.primary_cta_label || "<none>"}\``,
      `- inline blocking reason visible: \`${summary.inline_blocking_reason_visible}\``,
      `- headroom visible: \`${summary.headroom_visible}\``,
      `- settings visible: \`${summary.settings_visible}\``,
      `- hidden inference points: \`${summary.hidden_state_inference_points}\``,
      `- policy after save: \`${summary.policy_after_save?.continuation_strategy_label || summary.policy_after_save?.continuation_strategy || "<none>"}\``,
      `- cycle delta: \`${summary.cycle_delta}\``,
      `- checkpoint delta: \`${summary.checkpoint_delta}\``,
      `- multi-boundary advance: \`${summary.multi_boundary_advance}\``,
      `- before session id: \`${summary.long_run_before?.session_id || "<none>"}\``,
      `- after session id: \`${summary.long_run_after?.session_id || "<none>"}\``,
      `- before cycle/checkpoints: \`${summary.long_run_before?.current_cycle || 0}\` / \`${summary.long_run_before?.checkpoint_count || 0}\``,
      `- after cycle/checkpoints: \`${summary.long_run_after?.current_cycle || 0}\` / \`${summary.long_run_after?.checkpoint_count || 0}\``,
      summary.failures.length ? `- failures: ${summary.failures.join(" | ")}` : "- failures: none",
      "",
    ].join("\n"),
  );
  writeJson(handoffSummaryJsonPath, summary);
  writeText(
    handoffSummaryMdPath,
    [
      "# approve and continue handoff summary",
      "",
      `- success: \`${summary.success}\``,
      `- workspace actions: ${summary.workspace_actions.join(" -> ") || "<none>"}`,
      `- before session id: \`${summary.long_run_before?.session_id || "<none>"}\``,
      `- after approval session id: \`${summary.long_run_after_approval?.session_id || summary.long_run_before?.session_id || "<none>"}\``,
      `- after continuation session id: \`${summary.long_run_after?.session_id || "<none>"}\``,
      `- policy after save: \`${summary.policy_after_save?.continuation_strategy_label || summary.policy_after_save?.continuation_strategy || "<none>"}\``,
      `- cycle delta: \`${summary.cycle_delta}\``,
      `- checkpoint delta: \`${summary.checkpoint_delta}\``,
      `- before cycle/checkpoints: \`${summary.long_run_before?.current_cycle || 0}\` / \`${summary.long_run_before?.checkpoint_count || 0}\``,
      `- after continuation cycle/checkpoints: \`${summary.long_run_after?.current_cycle || 0}\` / \`${summary.long_run_after?.checkpoint_count || 0}\``,
      `- failures: ${summary.failures.length ? summary.failures.join("; ") : "<none>"}`,
    ].join("\n"),
  );
  await browser.close();
}

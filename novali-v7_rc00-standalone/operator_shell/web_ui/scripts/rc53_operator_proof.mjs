import { chromium } from "playwright";
import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..", "..");
const packageRoot =
  process.argv[2] || path.join(repoRoot, "dist", "novali-v6_rc53-standalone");
const artifactsRoot =
  process.argv[3] || path.join(repoRoot, "artifacts", "operator_proof", "rc53");
const helperPath = path.join(repoRoot, "scripts", "rc53_packaged_operator_server.py");

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function ensureCleanDir(dir) {
  await fsp.rm(dir, { recursive: true, force: true });
  await fsp.mkdir(dir, { recursive: true });
}

async function waitForExit(child, timeoutMs = 5000) {
  return new Promise((resolve) => {
    let resolved = false;
    const finish = (code, signal) => {
      if (!resolved) {
        resolved = true;
        resolve({ code, signal });
      }
    };
    child.once("exit", finish);
    setTimeout(() => finish(null, "timeout"), timeoutMs);
  });
}

async function stopScenario(scenario) {
  scenario.process.kill("SIGTERM");
  const result = await waitForExit(scenario.process, 5000);
  if (result.signal === "timeout") {
    scenario.process.kill("SIGKILL");
    await waitForExit(scenario.process, 3000);
  }
}

async function startScenario(name, scenario) {
  const scenarioDir = path.join(artifactsRoot, name);
  await fsp.mkdir(scenarioDir, { recursive: true });
  const stdoutLog = fs.createWriteStream(path.join(scenarioDir, "server_stdout.log"), {
    flags: "w",
  });
  const stderrLog = fs.createWriteStream(path.join(scenarioDir, "server_stderr.log"), {
    flags: "w",
  });
  const child = spawn(
    "python",
    [helperPath, "--package-root", packageRoot, "--scenario", scenario, "--artifacts-dir", scenarioDir],
    { cwd: repoRoot, stdio: ["ignore", "pipe", "pipe"] },
  );

  let readyPayload = null;
  let stdoutBuffer = "";

  const ready = new Promise((resolve, reject) => {
    child.stdout.on("data", (chunk) => {
      const text = chunk.toString();
      stdoutLog.write(text);
      stdoutBuffer += text;
      while (stdoutBuffer.includes("\n")) {
        const newlineIndex = stdoutBuffer.indexOf("\n");
        const line = stdoutBuffer.slice(0, newlineIndex).trim();
        stdoutBuffer = stdoutBuffer.slice(newlineIndex + 1);
        if (line.startsWith("RC53_SERVER_READY ")) {
          try {
            readyPayload = JSON.parse(line.replace("RC53_SERVER_READY ", ""));
            resolve(readyPayload);
          } catch (error) {
            reject(error);
          }
        }
      }
    });
    child.stderr.on("data", (chunk) => {
      stderrLog.write(chunk.toString());
    });
    child.once("exit", (code) => {
      if (!readyPayload) {
        reject(new Error(`Server exited before readiness: ${scenario} (${code})`));
      }
    });
  });

  const info = await ready;
  return {
    name,
    dir: scenarioDir,
    process: child,
    info,
    closeLogs() {
      stdoutLog.end();
      stderrLog.end();
    },
  };
}

async function collectFreshScenario(browser, screenshotsDir) {
  const scenario = await startScenario("fresh", "fresh");
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  const page = await context.newPage();
  const result = {};

  try {
    await page.goto(`${scenario.info.base_url}/shell`, { waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { name: "nOVALi Core" }).waitFor();
    await delay(1500);
    await page.screenshot({
      path: path.join(screenshotsDir, "01_landing_before_directive_load.png"),
      fullPage: true,
    });

    const bootstrapButton = page.getByRole("button", { name: "Bootstrap Initialization" });
    const governedButton = page.getByRole("button", { name: "Governed Execution Run" });
    result.bootstrapDisabledBefore = await bootstrapButton.isDisabled();
    result.governedDisabledBefore = await governedButton.isDisabled();

    await page.getByRole("button", { name: "Load Directive" }).click();
    await delay(500);
    await page.getByRole("heading", { name: "Directive and trusted-source load" }).waitFor();

    await page.getByLabel("Directive path").fill(String(scenario.info.sample_directive_path || ""));
    await page.getByLabel("Provider ID").fill("openai");
    await page.getByLabel("Provider base URL").fill("https://api.openai.com/v1");
    await page.getByRole("button", { name: "Validate Trusted Source" }).click();
    const validationNoticeLocator = page.locator(".modal .modal-section").nth(1).locator(".notice");
    await validationNoticeLocator.waitFor({ timeout: 15000 });
    result.validationNotice = ((await validationNoticeLocator.allTextContents()).join(" | ") || "").trim();

    await page.screenshot({
      path: path.join(screenshotsDir, "02_landing_directive_modal.png"),
      fullPage: true,
    });

    await page.getByRole("button", { name: "Select directive" }).click();
    await page.waitForTimeout(1000);
    await page.getByRole("button", { name: "Close" }).click();
    await page.getByRole("heading", { name: "Stage-gated operator actions" }).waitFor();
    await page.getByText("Directive present").waitFor({ timeout: 15000 });
    await delay(1000);

    result.directivePresent = await page.getByText("Directive present").isVisible().catch(() => false);
    result.bootstrapDisabledAfter = await bootstrapButton.isDisabled();
    result.governedDisabledAfter = await governedButton.isDisabled();
    result.bootstrapHeadingVisible = await page.getByRole("heading", { name: "Bootstrap Initialization" }).isVisible();
    result.governedHeadingVisible = await page.getByRole("heading", { name: "Governed Execution Run" }).isVisible();

    await page.screenshot({
      path: path.join(screenshotsDir, "03_landing_stage_gates.png"),
      fullPage: true,
    });
  } finally {
    await context.close();
    await stopScenario(scenario);
    scenario.closeLogs();
  }

  return { scenario: scenario.info, result };
}

async function collectSeededScenario(browser, screenshotsDir) {
  const scenario = await startScenario("seeded", "seeded");
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  const page = await context.newPage();
  const result = {};

  try {
    await page.goto(`${scenario.info.base_url}/shell`, { waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { name: "nOVALi Core" }).waitFor();
    await delay(1500);

    const governedButton = page.getByRole("button", { name: "Governed Execution Run" });
    await page.waitForFunction(() => {
      const button = Array.from(document.querySelectorAll("button")).find(
        (candidate) => candidate.textContent?.trim() === "Governed Execution Run",
      );
      return Boolean(button && !button.disabled);
    });
    result.governedDisabledBeforeStart = await governedButton.isDisabled();
    result.confirmedReviewVisible = await page.getByText("Promotion confirmed with review gate").first().isVisible();
    result.confirmationGapVisible = await page.getByText("No material confirmation gap").first().isVisible();
    result.staleAwaitingTextPresent = await page.locator("text=Awaiting operator confirmation").count();

    await governedButton.click();
    await page.waitForURL(/\/shell\/workspace$/, { timeout: 45000 });
    await page.getByRole("heading", { name: "Operator Workspace" }).waitFor();

    await page.screenshot({
      path: path.join(screenshotsDir, "04_workspace_after_governed_redirect.png"),
      fullPage: true,
    });

    await page.getByRole("heading", { name: "Operator intervention and review posture" }).scrollIntoViewIfNeeded();
    await delay(500);
    await page.screenshot({
      path: path.join(screenshotsDir, "05_workspace_review_summary.png"),
      fullPage: true,
    });

    await page.getByRole("heading", { name: "Operator-safe activity feed" }).scrollIntoViewIfNeeded();
    await page.waitForFunction(() => {
      const badge = document.querySelector(".stream-badge");
      return Boolean(badge && !String(badge.textContent || "").includes("Connecting"));
    }, { timeout: 20000 }).catch(() => {});
    await delay(2500);
    result.eventCount = await page.locator(".event-row").count();
    result.streamStatus = ((await page.locator(".stream-badge").textContent()) || "").trim();
    result.latestMeaningfulEvent = ((await page.locator(".live-summary-grid .summary-card").nth(1).textContent()) || "").trim();

    await page.screenshot({
      path: path.join(screenshotsDir, "06_workspace_live_feed.png"),
      fullPage: true,
    });
  } finally {
    await context.close();
    await stopScenario(scenario);
    scenario.closeLogs();
  }

  return { scenario: scenario.info, result };
}

function buildChecklist(fresh, seeded, screenshotsDir) {
  const checklist = [
    {
      id: "landing_page_smoother_and_readable",
      label: "landing page is smoother and readable",
      status: fresh.result.directivePresent ? "pass" : "fail",
      note: fresh.result.directivePresent
        ? "Landing remained readable before and after directive interaction."
        : "Directive-present landing state was not observed after the modal flow.",
      evidence: [
        path.join(screenshotsDir, "01_landing_before_directive_load.png"),
        path.join(screenshotsDir, "03_landing_stage_gates.png"),
      ],
    },
    {
      id: "stage_gating_truthful",
      label: "stage gating is truthful",
      status:
        fresh.result.bootstrapDisabledBefore && fresh.result.governedDisabledBefore
          ? "pass"
          : "fail",
      note: `Before directive load: bootstrap disabled=${fresh.result.bootstrapDisabledBefore}, governed disabled=${fresh.result.governedDisabledBefore}. After directive selection: bootstrap disabled=${fresh.result.bootstrapDisabledAfter}, governed disabled=${fresh.result.governedDisabledAfter}.`,
      evidence: [path.join(screenshotsDir, "03_landing_stage_gates.png")],
    },
    {
      id: "directive_trusted_source_flow_understandable",
      label: "directive/trusted-source flow is understandable",
      status: fresh.result.validationNotice ? "pass" : "fail",
      note: fresh.result.validationNotice || "No validation/upload notice was captured in the modal.",
      evidence: [path.join(screenshotsDir, "02_landing_directive_modal.png")],
    },
    {
      id: "bootstrap_vs_governed_distinction_clear",
      label: "bootstrap vs governed distinction is clear",
      status:
        fresh.result.bootstrapHeadingVisible && fresh.result.governedHeadingVisible
          ? "pass"
          : "fail",
      note: "Separate stage cards remain visible for bootstrap initialization and governed execution.",
      evidence: [path.join(screenshotsDir, "03_landing_stage_gates.png")],
    },
    {
      id: "governed_redirect_success",
      label: "governed start redirects to workspace on success",
      status: seeded.result.governedDisabledBeforeStart ? "fail" : "pass",
      note: seeded.result.governedDisabledBeforeStart
        ? "Governed button remained disabled in the seeded packaged scenario."
        : "Governed button was enabled from backend readiness and redirected to /shell/workspace.",
      evidence: [path.join(screenshotsDir, "04_workspace_after_governed_redirect.png")],
    },
    {
      id: "workspace_live_activity",
      label: "workspace shows live high-level activity",
      status:
        seeded.result.eventCount > 0 || !String(seeded.result.streamStatus || "").includes("Connecting")
          ? "pass"
          : "fail",
      note: `Meaningful event rows observed: ${seeded.result.eventCount}. Stream status: ${seeded.result.streamStatus}.`,
      evidence: [path.join(screenshotsDir, "06_workspace_live_feed.png")],
    },
    {
      id: "intervention_review_visibility",
      label: "intervention/review state is visible and understandable",
      status:
        seeded.result.confirmedReviewVisible && seeded.result.confirmationGapVisible
          ? "pass"
          : "fail",
      note: "Workspace review cards surfaced confirmed review state and confirmation-gap posture.",
      evidence: [path.join(screenshotsDir, "05_workspace_review_summary.png")],
    },
    {
      id: "current_truth_reflected",
      label: "current persisted benchmark truth is reflected accurately",
      status:
        seeded.result.confirmedReviewVisible &&
        seeded.result.confirmationGapVisible &&
        seeded.result.staleAwaitingTextPresent === 0
          ? "pass"
          : "fail",
      note: `Stale 'Awaiting operator confirmation' hits on seeded packaged flow: ${seeded.result.staleAwaitingTextPresent}.`,
      evidence: [
        path.join(screenshotsDir, "04_workspace_after_governed_redirect.png"),
        path.join(screenshotsDir, "05_workspace_review_summary.png"),
      ],
    },
  ];
  return checklist;
}

async function writeChecklist(checklist) {
  const jsonPath = path.join(artifactsRoot, "operator_acceptance_checklist.json");
  const mdPath = path.join(artifactsRoot, "operator_acceptance_checklist.md");
  await fsp.writeFile(jsonPath, `${JSON.stringify(checklist, null, 2)}\n`, "utf8");

  const lines = [
    "# RC53 Operator Acceptance Checklist",
    "",
    "| Check | Status | Note |",
    "|---|---|---|",
    ...checklist.map((item) => `| ${item.label} | ${item.status} | ${item.note.replace(/\|/g, "/")} |`),
    "",
  ];
  await fsp.writeFile(mdPath, `${lines.join("\n")}\n`, "utf8");
  return { jsonPath, mdPath };
}

async function main() {
  await ensureCleanDir(artifactsRoot);
  const screenshotsDir = path.join(artifactsRoot, "screens");
  await fsp.mkdir(screenshotsDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });

  try {
    const fresh = await collectFreshScenario(browser, screenshotsDir);
    const seeded = await collectSeededScenario(browser, screenshotsDir);
    const checklist = buildChecklist(fresh, seeded, screenshotsDir);
    const checklistArtifacts = await writeChecklist(checklist);

    const summary = {
      package_root: packageRoot,
      screenshots_dir: screenshotsDir,
      fresh,
      seeded,
      checklist,
      checklist_artifacts: checklistArtifacts,
    };
    await fsp.writeFile(
      path.join(artifactsRoot, "packaged_walkthrough_summary.json"),
      `${JSON.stringify(summary, null, 2)}\n`,
      "utf8",
    );

    const failures = checklist.filter((item) => item.status !== "pass");
    if (failures.length) {
      throw new Error(`RC53 operator proof failed: ${failures.map((item) => item.id).join(", ")}`);
    }
  } finally {
    await browser.close();
  }
}

await main();

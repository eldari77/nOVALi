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
  process.argv[2] || path.join(repoRoot, "dist", "novali-v6_rc59-standalone");
const artifactsRoot =
  process.argv[3] || path.join(repoRoot, "artifacts", "operator_proof", "rc59");
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
    await page.goto(`${scenario.info.base_url}/`, { waitUntil: "domcontentloaded" });
    await page.waitForURL(/\/shell$/, { timeout: 20000 });
    await page.getByRole("heading", { name: "nOVALi Core" }).waitFor();
    await delay(1500);
    result.baseFinalUrl = page.url();
    result.baseMarkersVisible = {
      loadDirective: await page.getByRole("button", { name: "Load Directive" }).isVisible(),
      bootstrapInitialization: await page
        .getByRole("button", { name: "Bootstrap Initialization" })
        .isVisible(),
      governedExecutionRun: await page
        .getByRole("button", { name: "Governed Execution Run" })
        .isVisible(),
    };
    await page.screenshot({
      path: path.join(screenshotsDir, "01_base_url_redirected_shell.png"),
      fullPage: true,
    });

    await page.goto(`${scenario.info.base_url}/shell`, { waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { name: "nOVALi Core" }).waitFor();
    await delay(1000);
    result.shellFinalUrl = page.url();
    await page.screenshot({
      path: path.join(screenshotsDir, "02_shell_landing_direct.png"),
      fullPage: true,
    });

    await page.getByRole("button", { name: "Load Directive" }).click();
    await page.getByRole("heading", { name: "Directive and trusted-source load" }).waitFor();
    await delay(500);
    await page.screenshot({
      path: path.join(screenshotsDir, "03_shell_directive_modal.png"),
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
    await page.goto(`${scenario.info.base_url}/shell/workspace`, { waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { name: "Operator Workspace" }).waitFor();
    await delay(1500);
    result.workspaceFinalUrl = page.url();
    await page.screenshot({
      path: path.join(screenshotsDir, "04_shell_workspace_direct.png"),
      fullPage: true,
    });
  } finally {
    await context.close();
    await stopScenario(scenario);
    scenario.closeLogs();
  }

  return { scenario: scenario.info, result };
}

async function main() {
  const screenshotsDir = path.join(artifactsRoot, "screens");
  await ensureCleanDir(screenshotsDir);

  const browser = await chromium.launch({ headless: true });
  try {
    const fresh = await collectFreshScenario(browser, screenshotsDir);
    const seeded = await collectSeededScenario(browser, screenshotsDir);
    const summary = {
      generated_at: new Date().toISOString(),
      package_root: packageRoot,
      screenshots_dir: screenshotsDir,
      fresh,
      seeded,
      screenshots: [
        path.join(screenshotsDir, "01_base_url_redirected_shell.png"),
        path.join(screenshotsDir, "02_shell_landing_direct.png"),
        path.join(screenshotsDir, "03_shell_directive_modal.png"),
        path.join(screenshotsDir, "04_shell_workspace_direct.png"),
      ],
    };
    await fsp.mkdir(artifactsRoot, { recursive: true });
    await fsp.writeFile(
      path.join(artifactsRoot, "default_entry_proof_summary.json"),
      JSON.stringify(summary, null, 2) + "\n",
      "utf-8",
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

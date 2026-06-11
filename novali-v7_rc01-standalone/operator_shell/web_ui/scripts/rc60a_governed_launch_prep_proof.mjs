import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const baseUrl = process.argv[2] || "http://127.0.0.1:8787";
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const artifactsDir = process.argv[3]
  || path.resolve(scriptDir, "..", "..", "..", "artifacts", "operator_proof", "rc60a");
const screensDir = path.join(artifactsDir, "screens");

await fs.mkdir(screensDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1120 } });

const summary = {
  base_url: baseUrl,
  directive_path: "",
  prep_button_visible_before_launch: false,
  prep_message: "",
  governed_button_enabled_after_prep: false,
  final_url: "",
  screenshots: {},
};

try {
  await page.goto(`${baseUrl}/`, { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Load Directive" }).waitFor({ timeout: 60000 });
  await page.getByRole("button", { name: "Load Directive" }).click();

  const directivePath = "/workspace/novali/samples/directives/standalone_valid_directive.example.json";
  summary.directive_path = directivePath;
  await page.getByPlaceholder("/absolute/path/for/your/directive.json").fill(directivePath);
  await page.getByRole("button", { name: "Select directive" }).click();
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Close" }).click();

  await page.waitForFunction(() => {
    const button = Array.from(document.querySelectorAll("button"))
      .find((item) => (item.textContent || "").trim() === "Bootstrap Initialization");
    return !!button && !button.hasAttribute("disabled");
  }, undefined, { timeout: 60000 });
  await page.getByRole("button", { name: "Bootstrap Initialization" }).click();
  await page.waitForSelector("[data-testid='governed-readiness-panel']");
  await page.waitForFunction(() => {
    const prep = document.querySelector("[data-testid='governed-prepare-button']");
    const launch = document.querySelector("[data-testid='governed-start-button']");
    const prepReady = !!prep && !prep.hasAttribute("disabled");
    const launchReady = !!launch && !launch.hasAttribute("disabled");
    return prepReady || launchReady;
  }, undefined, { timeout: 120000 });
  await page.waitForTimeout(1200);

  const shot1 = path.join(screensDir, "01_landing_before_governed_click.png");
  await page.screenshot({ path: shot1, fullPage: true });
  summary.screenshots.before_governed_click = shot1;

  const prepButton = page.getByTestId("governed-prepare-button");
  summary.prep_button_visible_before_launch = await prepButton.isVisible().catch(() => false);
  if (summary.prep_button_visible_before_launch) {
    await prepButton.click();
    await page.waitForTimeout(1500);
  }

  const notice = page.locator(".notice").first();
  if (await notice.isVisible().catch(() => false)) {
    summary.prep_message = (await notice.textContent())?.trim() || "";
  }

  const shot2 = path.join(screensDir, "02_landing_governed_prep_state.png");
  await page.screenshot({ path: shot2, fullPage: true });
  summary.screenshots.governed_prep_state = shot2;

  const governedButton = page.getByTestId("governed-start-button");
  await page.waitForFunction(() => {
    const button = document.querySelector("[data-testid='governed-start-button']");
    return !!button && !button.hasAttribute("disabled");
  }, undefined, { timeout: 120000 });
  summary.governed_button_enabled_after_prep = true;
  await governedButton.click();

  await page.waitForURL(/\/shell\/workspace(?:\?|$)/, { timeout: 120000 });
  summary.final_url = page.url();

  const shot3 = path.join(screensDir, "03_workspace_after_governed_redirect.png");
  await page.screenshot({ path: shot3, fullPage: true });
  summary.screenshots.workspace_redirect = shot3;
} finally {
  await browser.close();
}

const summaryPath = path.join(artifactsDir, "governed_launch_prep_summary.json");
await fs.writeFile(summaryPath, `${JSON.stringify(summary, null, 2)}\n`, "utf8");

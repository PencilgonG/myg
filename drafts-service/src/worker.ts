import { Queue, Job } from "bull";
import { chromium } from "playwright";
import fs from "fs";
import path from "path";
import { DraftJobData } from "./types";

const DEBUG_DIR = "/app/debug";
if (!fs.existsSync(DEBUG_DIR)) {
  fs.mkdirSync(DEBUG_DIR, { recursive: true });
}

export async function processDraftJob(job: Job<DraftJobData>) {
  const { blueName, redName, matchName } = job.data;
  const browser = await chromium.launch({
    headless: process.env.HEADFUL ? false : true,
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // Aller sur lolprodraft
    await page.goto("https://lolprodraft.com/", {
      waitUntil: "domcontentloaded",
      timeout: 30000,
    });

    // Remplir Blue + Red (les deux inputs visibles)
    const inputs = await page.locator("input").all();
    if (inputs.length < 2) {
      throw new Error("Impossible de trouver les champs de saisie");
    }

    await inputs[0].fill(blueName);
    await inputs[1].fill(redName);

    // Cliquer sur "Create draft"
    await page.locator("button:has-text('Create draft')").click();

    // Attendre que les liens apparaissent
    await page.waitForSelector("a", { timeout: 15000 });

    // Récupérer tous les liens
    const links = await page.locator("a").all();
    let blueUrl: string | null = null;
    let redUrl: string | null = null;
    let specUrl: string | null = null;

    for (const link of links) {
      const href = await link.getAttribute("href");
      const text = (await link.innerText()).toLowerCase();
      if (!href) continue;

      if (text.includes("blue")) blueUrl = href;
      else if (text.includes("red")) redUrl = href;
      else if (text.includes("spec")) specUrl = href;
    }

    if (!blueUrl || !redUrl || !specUrl) {
      // Sauvegarde debug
      const ts = new Date().toISOString().replace(/[:.]/g, "-");
      const shot = path.join(DEBUG_DIR, `shot-${ts}.png`);
      const html = path.join(DEBUG_DIR, `page-${ts}.html`);
      await page.screenshot({ path: shot });
      fs.writeFileSync(html, await page.content());

      throw new Error(
        `Impossible d’identifier les liens Blue/Red/Spec sur la page. Debug: ${shot}`
      );
    }

    return {
      status: "ready",
      matchName,
      blue: blueUrl,
      red: redUrl,
      spec: specUrl,
    };
  } catch (err: any) {
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    const shot = path.join(DEBUG_DIR, `error-${ts}.png`);
    const html = path.join(DEBUG_DIR, `error-${ts}.html`);
    await page.screenshot({ path: shot });
    fs.writeFileSync(html, await page.content());

    return {
      status: "error",
      message: err.message || String(err),
      debug: { shot, html },
    };
  } finally {
    await browser.close();
  }
}

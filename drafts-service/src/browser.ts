// ===== [drafts-service/src/browser.ts] =====
import { chromium, type Page } from 'playwright';
import type { DraftLinks } from './types.js';

const CHROME_ARGS = ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'];

async function readLinks(page: Page): Promise<DraftLinks | null> {
  try {
    await page.waitForSelector('input[type="text"]', { timeout: 20000 });
    const vals = await page.$$eval('input[type="text"]', els =>
      els.slice(0, 12).map(e => (e as HTMLInputElement).value || '')
    );
    const pick = (re: RegExp) => vals.find(u => re.test(u)) || '';
    const blue = pick(/\/(b|blue)(\/|$|\?)/i);
    const red  = pick(/\/(r|red)(\/|$|\?)/i);
    const spec = pick(/\/(s|spectator|spec)(\/|$|\?)/i);
    if (blue && red && spec) return { blue, red, spec };
  } catch {}
  return null;
}

export async function createLinks(blueName: string, redName: string): Promise<DraftLinks> {
  const browser = await chromium.launch({ headless: true, args: CHROME_ARGS });
  try {
    const ctx = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
    });
    const page = await ctx.newPage();
    await page.route('**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}', r => r.abort());

    // A) /draft → Remake → lire
    await page.goto('https://lolprodraft.com/draft', { waitUntil: 'domcontentloaded', timeout: 45000 });
    const remake = page.locator('button:has-text("Remake"), button:has-text("Remake draft links"), button:has-text("Generate")');
    if (await remake.count().catch(() => 0)) await remake.first().click().catch(() => {});
    const a = await readLinks(page);
    if (a) return a;

    // B) /create → renseigner noms → submit → /draft → lire
    await page.goto('https://lolprodraft.com/create', { waitUntil: 'domcontentloaded', timeout: 45000 });
    const inputs = await page.$$('input[type="text"]');
    if (inputs.length >= 2) {
      await inputs[0].fill(blueName).catch(() => {});
      await inputs[1].fill(redName).catch(() => {});
    } else {
      await page.fill('input[placeholder*="Blue" i],input[aria-label*="Blue" i]', blueName).catch(() => {});
      await page.fill('input[placeholder*="Red" i], input[aria-label*="Red" i]',  redName).catch(() => {});
    }
    const submit = page.locator('button:has-text("Create"), button:has-text("Start"), button:has-text("Generate"), button[type="submit"]');
    await submit.first().click({ timeout: 8000 }).catch(() => {});
    await page.waitForURL(/\/draft\//, { timeout: 25000 }).catch(() => {});
    const b = await readLinks(page);
    if (b) return b;

    throw new Error('No links found');
  } finally {
    await browser.close().catch(() => {});
  }
}

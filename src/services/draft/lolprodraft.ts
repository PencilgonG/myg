// ==========================================
// path: src/services/draft/lolprodraft.ts
// ==========================================
import { chromium, type Browser, type Page } from 'playwright';

export class DraftCreationError extends Error {
  constructor(msg = 'Unable to create lolprodraft links') { super(msg); }
}

export type DraftLinks = { blue: string; red: string; spec: string };
const CHROME_ARGS = ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'];

async function grabLinksFromDraftPage(page: Page): Promise<DraftLinks | null> {
  // La page /draft affiche généralement 4 inputs texte: blue, red, coach, spectator
  try {
    await page.waitForSelector('input[type="text"]', { timeout: 20000 });
    const vals = await page.$$eval('input[type="text"]', els =>
      els.slice(0, 8).map(e => (e as HTMLInputElement).value || '')
    );

    const pick = (re: RegExp) => vals.find(u => re.test(u)) || '';
    // Beaucoup de variantes possibles, on élargit la détection
    const blue = pick(/\/(b|blue)(\/|$|\?)/i);
    const red  = pick(/\/(r|red)(\/|$|\?)/i);
    const spec = pick(/\/(s|spectator|spec)(\/|$|\?)/i);

    if (blue && red && spec) return { blue, red, spec };
  } catch { /* ignore */ }
  return null;
}

export async function createLolProDraft(blueName: string, redName: string): Promise<DraftLinks> {
  let browser: Browser | null = null;
  try {
    browser = await chromium.launch({ headless: true, args: CHROME_ARGS });
    const page = await browser.newPage();

    // A) Page qui génère directement un draft et affiche les liens
    await page.goto('https://lolprodraft.com/draft', { waitUntil: 'domcontentloaded', timeout: 45000 });
    const fromDraft = await grabLinksFromDraftPage(page);
    if (fromDraft) return fromDraft;

    // B) Flow "create"
    await page.goto('https://lolprodraft.com/create', { waitUntil: 'domcontentloaded', timeout: 45000 });

    // Sélecteurs tolérants (la page n'a pas d'attributs stables)
    const blueSel = 'input[name="blueName"], input[placeholder*="Blue" i], input[aria-label*="Blue" i], input[type="text"]';
    const redSel  = 'input[name="redName"], input[placeholder*="Red" i],  input[aria-label*="Red" i],  input[type="text"]';

    // On tente de repérer les 2 premiers inputs si besoin
    const textInputs = await page.$$('input[type="text"]');
    if (textInputs.length >= 2) {
      await textInputs[0].fill(blueName).catch(() => {});
      await textInputs[1].fill(redName).catch(() => {});
    } else {
      await page.fill(blueSel, blueName).catch(() => {});
      await page.fill(redSel, redName).catch(() => {});
    }

    const submit = page.locator('button:has-text("Create"), button:has-text("Start"), button:has-text("Generate"), button[type="submit"]');
    await submit.first().click({ timeout: 8000 }).catch(() => {});
    await page.waitForURL(/\/draft\//, { timeout: 20000 }).catch(() => {});

    const fromCreate = await grabLinksFromDraftPage(page);
    if (fromCreate) return fromCreate;

    throw new DraftCreationError();
  } catch (e) {
    throw new DraftCreationError((e as Error)?.message);
  } finally {
    await browser?.close().catch(() => {});
  }
}
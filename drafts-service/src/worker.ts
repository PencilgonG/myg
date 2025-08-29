// ===== [drafts-service/src/worker.ts] =====
import type { DraftLinks } from './types.js';
import { createLinks } from './browser.js';

export async function createLolProLinks(blueName: string, redName: string): Promise<DraftLinks> {
  return createLinks(blueName, redName);
}

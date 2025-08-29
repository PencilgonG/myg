// ===== [BOT] src/services/draft/client.ts =====
export type DraftLinks = { blue: string; red: string; spec: string };

const API = process.env.DRAFT_API_URL || 'http://localhost:4005';
const KEY = process.env.DRAFT_API_KEY || 'CHANGE_ME_SECRET';

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { 'x-api-key': KEY, 'content-type': 'application/json', ...(init?.headers || {}) }
  });
  if (res.status === 202) return { status: 'pending' } as any;
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export async function requestDraft(blueName: string, redName: string): Promise<string> {
  const r = await api<{ id: string }>('/drafts', { method: 'POST', body: JSON.stringify({ blueName, redName }) });
  return r.id;
}

export async function waitDraft(id: string, timeoutMs = 45000): Promise<DraftLinks> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const r = await api<any>(`/drafts/${id}`);
    if (r.status === 'ready') return r.links as DraftLinks;
    if (r.status === 'error') throw new Error(r.message || 'draft error');
    await new Promise(r => setTimeout(r, 2000));
  }
  throw new Error('draft timeout');
}

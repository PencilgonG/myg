// src/services/draft/client.ts
export type DraftLinks = { blue: string; red: string; spec: string };

const API = process.env.DRAFT_API_URL || 'http://localhost:4005';
const KEY = process.env.DRAFT_API_KEY || 'CHANGE_ME_SECRET';

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      'x-api-key': KEY,
      'content-type': 'application/json',
      ...(init?.headers || {})
    }
  });

  if (res.status === 202) {
    // Réponse "pending" (BullMQ job pas encore terminé)
    return { status: 'pending' } as any;
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${text || res.statusText}`);
  }

  return res.json() as Promise<T>;
}

export async function requestDraft(blueName: string, redName: string): Promise<string> {
  const r = await api<{ id: string }>('/drafts', {
    method: 'POST',
    body: JSON.stringify({ blueName, redName }),
  });
  return r.id;
}

export async function waitDraft(id: string, timeoutMs = 90000): Promise<DraftLinks> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const r = await api<{ status: 'pending' | 'ready' | 'error'; links?: DraftLinks; message?: string }>(`/drafts/${id}`);
    if (r.status === 'ready' && r.links) return r.links;
    if (r.status === 'error') throw new Error(r.message || 'draft error');
    await new Promise((res) => setTimeout(res, 2000));
  }
  throw new Error('draft timeout');
}

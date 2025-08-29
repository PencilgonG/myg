// drafts-service/src/index.ts
import Fastify from 'fastify';
import { enqueueDraft, draftsQueue } from './queue.js';
import type { DraftReq } from './types.js';

const API_KEY = process.env.API_KEY || 'CHANGE_ME_SECRET';
const PORT = Number(process.env.PORT || 4005);

const app = Fastify({ logger: { level: process.env.LOG_LEVEL || 'info' } });

app.addHook('preHandler', async (req, reply) => {
  if (req.url.startsWith('/health')) return;
  const key = (req.headers['x-api-key'] || req.headers['X-API-Key']) as string | undefined;
  if (!key || key !== API_KEY) return reply.code(401).send({ error: 'unauthorized' });
});

app.get('/health', async () => ({ ok: true }));

app.post<{ Body: DraftReq }>('/drafts', async (req, reply) => {
  const { blueName, redName, meta } = req.body || {};
  if (!blueName || !redName) return reply.code(400).send({ error: 'blueName/redName required' });
  const job = await enqueueDraft({ blueName, redName, meta });
  return reply.code(202).send({ id: job.id });
});

app.get('/drafts/:id', async (req, reply) => {
  const id = (req.params as any).id;
  const job = await draftsQueue.getJob(id);
  if (!job) return reply.code(404).send({ status: 'not_found' });
  const state = await job.getState();
  if (state === 'completed') {
    const val = await job.returnvalue;
    return reply.code(200).send({ status: 'ready', links: val });
  }
  if (state === 'failed') {
    const reason = (job as any).failedReason || 'failed';
    return reply.code(500).send({ status: 'error', message: reason });
  }
  return reply.code(202).send({ status: 'pending' });
});

app.post('/drafts/:id/retry', async (req, reply) => {
  const id = (req.params as any).id;
  const old = await draftsQueue.getJob(id);
  if (!old) return reply.code(404).send({ error: 'not_found' });
  const data = old.data as DraftReq;
  const job = await enqueueDraft(data);
  return reply.code(202).send({ id: job.id });
});

app.listen({ port: PORT, host: '0.0.0.0' });

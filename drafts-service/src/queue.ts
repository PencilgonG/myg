import { Queue, Worker, QueueEvents, JobsOptions } from 'bullmq';
import { Redis } from 'ioredis';
import pino from 'pino';
import { createLolProLinks } from './worker.js';
import type { DraftReq, DraftLinks } from './types.js';

const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';
const connection = new Redis(redisUrl);

export const log = pino({ level: process.env.LOG_LEVEL || 'info' });

export const draftsQueue = new Queue<DraftReq>('drafts', { connection });
export const draftsEvents = new QueueEvents('drafts', { connection });

export const worker = new Worker<DraftReq, DraftLinks>(
  'drafts',
  async (job) => {
    const { blueName, redName } = job.data;
    log.info({ jobId: job.id, blueName, redName }, 'creating lolprodraft…');
    const links = await createLolProLinks(blueName, redName);
    log.info({ jobId: job.id, ...links }, 'draft created');
    return links;
  },
  { connection, concurrency: 1 }
);

worker.on('failed', (job, err) => log.error({ jobId: job?.id, err }, 'draft failed'));

export async function enqueueDraft(data: DraftReq) {
  const opts: JobsOptions = {
    removeOnComplete: true,
    removeOnFail: true,
    attempts: 2,
    backoff: { type: 'exponential', delay: 2000 }
  };
  return draftsQueue.add('create', data, opts);
}

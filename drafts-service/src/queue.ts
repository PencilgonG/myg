import Queue from "bull";
import { createLolProDraftLinks, DraftJobData } from "./worker.js";

export const draftQueue = new Queue<DraftJobData>("drafts", {
  redis: { host: "redis", port: 6379 },
});

draftQueue.process(async (job) => {
  console.log("[Queue] Nouveau job:", job.data);
  return await createLolProDraftLinks(job.data);
});

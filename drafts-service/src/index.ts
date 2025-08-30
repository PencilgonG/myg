import express from "express";
import bodyParser from "body-parser";
import { draftQueue } from "./queue.js";

const app = express();
const PORT = process.env.PORT || 4005;
const API_KEY = process.env.API_KEY || "CHANGE_ME_SECRET";

app.use(bodyParser.json());

app.get("/health", (_, res) => {
  res.json({ ok: true });
});

app.post("/drafts", async (req, res) => {
  if (req.headers["x-api-key"] !== API_KEY) {
    return res.status(403).json({ error: "invalid api key" });
  }

  const { blueName, redName, matchName } = req.body;
  if (!blueName || !redName) {
    return res.status(400).json({ error: "blueName and redName are required" });
  }

  const job = await draftQueue.add({ id: "", blueName, redName, matchName });
  res.json({ id: job.id });
});

app.get("/drafts/:id", async (req, res) => {
  if (req.headers["x-api-key"] !== API_KEY) {
    return res.status(403).json({ error: "invalid api key" });
  }

  const job = await draftQueue.getJob(req.params.id);
  if (!job) return res.status(404).json({ error: "job not found" });

  const state = await job.getState();
  const result = await job.finished().catch(() => null);

  res.json(result ? result : { status: state });
});

app.listen(PORT, () => {
  console.log(`[Server] listening at http://0.0.0.0:${PORT}`);
});

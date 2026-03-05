"use strict";

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_HEARTBEAT_INTERVAL_MS = 60_000;
const MEMORY_RETRY_QUEUE_FILE = ".memory_retry_queue.json";
const DEFAULT_SEARCH_LIMIT = 5;
const DEFAULT_INSIGHTS_LIMIT = 10;
const DEFAULT_MIN_RELEVANCE = 0.6;
const COMMIT_FAILURE_SERVER_UNREACHABLE =
  "Memory commit failed — server unreachable. Queued for retry.";
const SESSION_ARC_SUMMARY_PROMPT =
  "Summarize this session arc: What was the goal? What approaches were tried? What decisions were made? What remains open?";
const PENDING_INSIGHT_PROMPT_GUIDANCE =
  "If pending insights appear in your context that relate to the current conversation, surface them naturally to the user. Do not force it — but if there is a genuine connection, seamlessly bring it up.";

module.exports = {
  DEFAULT_BASE_URL,
  DEFAULT_HEARTBEAT_INTERVAL_MS,
  MEMORY_RETRY_QUEUE_FILE,
  DEFAULT_SEARCH_LIMIT,
  DEFAULT_INSIGHTS_LIMIT,
  DEFAULT_MIN_RELEVANCE,
  COMMIT_FAILURE_SERVER_UNREACHABLE,
  SESSION_ARC_SUMMARY_PROMPT,
  PENDING_INSIGHT_PROMPT_GUIDANCE,
};

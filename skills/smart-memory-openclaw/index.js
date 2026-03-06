"use strict";

const path = require("path");

const {
  COMMIT_FAILURE_SERVER_UNREACHABLE,
  DEFAULT_BASE_URL,
  DEFAULT_HEARTBEAT_INTERVAL_MS,
  DEFAULT_INSIGHTS_LIMIT,
  DEFAULT_MIN_RELEVANCE,
  DEFAULT_SEARCH_LIMIT,
} = require("./constants");
const {
  formatActiveContextBlock,
  formatMemorySearchResults,
  formatPendingInsights,
} = require("./formatters");
const {
  CognitiveApiClient,
  HttpError,
  isServerUnreachableError,
} = require("./http-client");
const { PromptContextInjector } = require("./prompt-injection");
const { MemoryRetryQueue } = require("./retry-queue");
const { SessionArcCapturer } = require("./session-arc");
const { DEFAULT_TAG_RULES, buildAutoTags } = require("./tagging");
const { createOpenClawHooks } = require("./openclaw-hooks");

const ALLOWED_MEMORY_TYPES = new Set(["semantic", "episodic", "belief", "goal"]);
const ALLOWED_SEARCH_TYPES = new Set(["all", ...ALLOWED_MEMORY_TYPES]);

/**
 * Smart Memory OpenClaw Skill
 *
 * Core tools:
 * - memory_search
 * - memory_commit
 * - memory_insights
 *
 * Includes:
 * - required /health gate before each tool
 * - retry queue for failed commits
 * - queue flush on next healthy call / heartbeat
 * - session arc capture hooks
 * - system prompt active-context injector
 */
class SmartMemorySkill {
  /**
   * @param {{
   *   baseUrl?: string;
   *   timeoutMs?: number;
   *   retryQueuePath?: string;
   *   heartbeatIntervalMs?: number;
   *   logger?: Pick<Console, "log" | "warn" | "error">;
   *   tagRules?: Array<{ id: string; test: Function; add: string[] }>;
   *   autoStartHeartbeat?: boolean;
   * }} [options]
   */
  constructor(options = {}) {
    this.logger = options.logger || console;

    this.apiClient = new CognitiveApiClient({
      baseUrl: options.baseUrl || DEFAULT_BASE_URL,
      timeoutMs: Number(options.timeoutMs || 10_000),
    });

    this.retryQueue = new MemoryRetryQueue({
      queueFilePath: options.retryQueuePath || path.resolve(process.cwd(), ".memory_retry_queue.json"),
    });

    this.tagRules = Array.isArray(options.tagRules) && options.tagRules.length
      ? options.tagRules
      : DEFAULT_TAG_RULES;

    this.heartbeatIntervalMs = Number(
      options.heartbeatIntervalMs || DEFAULT_HEARTBEAT_INTERVAL_MS
    );
    this.heartbeatTimer = null;
    this._commitChain = Promise.resolve();
    this._retrieveSupportsFilterParams = true;

    this.promptInjector = new PromptContextInjector({
      apiClient: this.apiClient,
      healthCheck: () => this.apiClient.checkHealth(),
      logger: this.logger,
    });

    this.sessionArcCapturer = null;

    if (options.autoStartHeartbeat !== false) {
      this.startHeartbeat();
    }
  }

  startHeartbeat() {
    if (this.heartbeatTimer) {
      return;
    }

    this.heartbeatTimer = setInterval(() => {
      this.heartbeat().catch((error) => {
        this.logger.warn?.("[smart-memory-openclaw] heartbeat failed:", error.message);
      });
    }, this.heartbeatIntervalMs);

    if (typeof this.heartbeatTimer.unref === "function") {
      this.heartbeatTimer.unref();
    }
  }

  stopHeartbeat() {
    if (!this.heartbeatTimer) {
      return;
    }

    clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = null;
  }

  async heartbeat() {
    const health = await this.apiClient.checkHealth();
    if (health.healthy) {
      await this._flushRetryQueue();
    }
    return health;
  }

  async memorySearch(input = {}) {
    const query = String(input.query || "").trim();
    if (!query) {
      return "memory_search failed: query is required.";
    }

    const type = String(input.type || "all").toLowerCase();
    if (!ALLOWED_SEARCH_TYPES.has(type)) {
      return "memory_search failed: type must be one of all, semantic, episodic, belief, goal.";
    }

    const limit = clampInteger(input.limit, DEFAULT_SEARCH_LIMIT, 1, 50);
    const minRelevance = clampNumber(
      input.min_relevance,
      DEFAULT_MIN_RELEVANCE,
      0,
      1
    );
    const conversationHistory = String(input.conversation_history || "");

    const gate = await this._checkToolHealth("memory_search");
    if (!gate.ok) {
      return gate.message;
    }

    try {
      const retrieval = await this._retrieveWithCompatibility({
        query,
        conversationHistory,
        type,
        limit,
        minRelevance,
      });

      let selected = Array.isArray(retrieval?.selected) ? retrieval.selected : [];
      selected = selected.filter((item) => {
        const memory = item?.memory || {};
        const itemType = String(memory.type || "").toLowerCase();
        const score = Number(item?.score ?? item?.vector_score ?? 0);

        const typePass = type === "all" ? true : itemType === type;
        const scorePass = Number.isFinite(score) ? score >= minRelevance : false;
        return typePass && scorePass;
      });

      const sliced = selected.slice(0, limit);
      return formatMemorySearchResults(query, sliced);
    } catch (error) {
      return `memory_search failed: ${error.message}`;
    }
  }

  /**
   * Sequential commit gate to avoid overloading local embedding compute.
   * @param {import("./types").MemoryCommitInput} input
   */
  async memoryCommit(input = {}) {
    return this._enqueueCommit(() => this._memoryCommitInternal(input));
  }

  /**
   * @param {import("./types").MemoryInsightsInput} input
   */
  async memoryInsights(input = {}) {
    const limit = clampInteger(input.limit, DEFAULT_INSIGHTS_LIMIT, 1, 100);

    const gate = await this._checkToolHealth("memory_insights");
    if (!gate.ok) {
      return gate.message;
    }

    try {
      const response = await this.apiClient.pendingInsights();
      const insights = Array.isArray(response?.insights) ? response.insights : [];
      return formatPendingInsights(insights, limit);
    } catch (error) {
      return `memory_insights failed: ${error.message}`;
    }
  }

  /**
   * Middleware helper: fetch passive context and inject [ACTIVE CONTEXT] into the system prompt.
   */
  async injectActiveContext(input) {
    return this.promptInjector.inject({
      baseSystemPrompt: String(input?.baseSystemPrompt || ""),
      agentIdentity: String(input?.agentIdentity || "Smart Memory Agent"),
      currentUserMessage: String(input?.currentUserMessage || "Session message"),
      conversationHistory: String(input?.conversationHistory || ""),
      hotMemory: input?.hotMemory,
      maxPromptTokens: input?.maxPromptTokens,
      retrievalTimeoutMs: input?.retrievalTimeoutMs,
      maxCandidateMemories: input?.maxCandidateMemories,
      maxSelectedMemories: input?.maxSelectedMemories,
    });
  }

  /**
   * Optional direct formatter if host framework already has hot memory + insight data.
   */
  buildActiveContextBlock(payload) {
    return formatActiveContextBlock(payload);
  }

  /**
   * @param {{
   *   summarizeSessionArc: (payload: {
   *     prompt: string;
   *     conversationText: string;
   *     turns: Array<{ role: string; content: string }>;
   *     trigger: "checkpoint"|"session_end";
   *   }) => Promise<string>;
   *   checkpointTurns?: number;
   *   maxTurns?: number;
   * }} options
   */
  configureSessionArc(options) {
    this.sessionArcCapturer = new SessionArcCapturer({
      memoryCommit: (input) => this.memoryCommit(input),
      summarizeSessionArc: options.summarizeSessionArc,
      checkpointTurns: options.checkpointTurns || 20,
      maxTurns: options.maxTurns || 20,
      logger: this.logger,
    });

    return this.sessionArcCapturer;
  }

  /**
   * Mid-session checkpoint hook (every 20 turns by default).
   * @param {{ conversationHistory: Array<{ role: string; content: string }> }} payload
   */
  async onConversationTurn(payload) {
    if (!this.sessionArcCapturer) {
      return null;
    }
    return this.sessionArcCapturer.onTurn(payload);
  }

  /**
   * Session teardown hook.
   * @param {{ conversationHistory: Array<{ role: string; content: string }> }} payload
   */
  async onSessionEnd(payload) {
    if (!this.sessionArcCapturer) {
      return null;
    }
    return this.sessionArcCapturer.onSessionEnd(payload);
  }

  /**
   * Tool descriptors for frameworks that register tools from metadata.
   */
  getToolDefinitions() {
    return [
      {
        name: "memory_search",
        description: "Query long-term semantic memory.",
        input_schema: {
          type: "object",
          properties: {
            query: { type: "string" },
            type: {
              type: "string",
              enum: ["all", "semantic", "episodic", "belief", "goal"],
              default: "all",
            },
            limit: { type: "number", default: DEFAULT_SEARCH_LIMIT },
            min_relevance: { type: "number", default: DEFAULT_MIN_RELEVANCE },
          },
          required: ["query"],
        },
        execute: (input) => this.memorySearch(input),
      },
      {
        name: "memory_commit",
        description: "Persist an explicit memory item to long-term memory.",
        input_schema: {
          type: "object",
          properties: {
            content: { type: "string" },
            type: {
              type: "string",
              enum: ["semantic", "episodic", "belief", "goal"],
            },
            importance: { type: "number", default: 5 },
            tags: {
              type: "array",
              items: { type: "string" },
            },
          },
          required: ["content", "type"],
        },
        execute: (input) => this.memoryCommit(input),
      },
      {
        name: "memory_insights",
        description: "Retrieve pending background insights from REM cycles.",
        input_schema: {
          type: "object",
          properties: {
            limit: { type: "number", default: DEFAULT_INSIGHTS_LIMIT },
          },
        },
        execute: (input) => this.memoryInsights(input),
      },
    ];
  }

  /**
   * @param {import("./types").MemoryCommitInput} input
   */
  async _memoryCommitInternal(input = {}) {
    const content = String(input.content || "").trim();
    const type = String(input.type || "").toLowerCase();

    if (!content) {
      return "memory_commit failed: content is required.";
    }

    if (!ALLOWED_MEMORY_TYPES.has(type)) {
      return "memory_commit failed: type must be semantic, episodic, belief, or goal.";
    }

    const importanceRaw = clampInteger(input.importance, 5, 1, 10);
    const importanceNormalized = Number((importanceRaw / 10).toFixed(3));
    const tags = buildAutoTags(content, {
      tags: Array.isArray(input.tags) ? input.tags : [],
      rules: this.tagRules,
    });

    const payload = buildIngestPayload({
      content,
      type,
      importanceRaw,
      importanceNormalized,
      tags,
      source: input.source,
      participants: input.participants,
      activeProjects: input.active_projects,
      metadata: input.metadata,
    });

    const health = await this.apiClient.checkHealth();
    if (!health.healthy) {
      await this.retryQueue.enqueue(payload);
      if (!health.reachable) {
        return COMMIT_FAILURE_SERVER_UNREACHABLE;
      }
      return "Memory commit failed â€” embedder not loaded. Queued for retry.";
    }

    await this._flushRetryQueue();

    try {
      const response = await this.apiClient.ingest(payload);
      const stored = Boolean(response?.stored);
      const reason = String(response?.reason || "unknown");
      const memoryId = response?.memory_id ? String(response.memory_id) : "n/a";
      return `Memory commit processed: stored=${stored} type=${type} id=${memoryId} reason=${reason}.`;
    } catch (error) {
      if (isServerUnreachableError(error)) {
        await this.retryQueue.enqueue(payload);
        return COMMIT_FAILURE_SERVER_UNREACHABLE;
      }
      return `memory_commit failed: ${error.message}`;
    }
  }

  async _checkToolHealth(toolName) {
    const health = await this.apiClient.checkHealth();

    if (!health.healthy) {
      if (!health.reachable) {
        return {
          ok: false,
          message: `${toolName} aborted: memory server unreachable.`,
        };
      }

      return {
        ok: false,
        message: `${toolName} aborted: memory embedder is not loaded.`,
      };
    }

    await this._flushRetryQueue();
    return { ok: true };
  }

  async _retrieveWithCompatibility({
    query,
    conversationHistory,
    type,
    limit,
    minRelevance,
  }) {
    const basePayload = {
      user_message: query,
      conversation_history: conversationHistory,
    };

    if (!this._retrieveSupportsFilterParams) {
      return this.apiClient.retrieve(basePayload);
    }

    try {
      return await this.apiClient.retrieve({
        ...basePayload,
        type,
        limit,
        min_relevance: minRelevance,
      });
    } catch (error) {
      if (error instanceof HttpError && error.status === 422) {
        this._retrieveSupportsFilterParams = false;
        return this.apiClient.retrieve(basePayload);
      }
      throw error;
    }
  }
  async _flushRetryQueue() {
    try {
      const result = await this.retryQueue.flush(async (payload) => {
        await this.apiClient.ingest(payload);
      });

      if (result.flushed > 0) {
        this.logger.log?.(
          `[smart-memory-openclaw] flushed ${result.flushed} queued commit(s); ${result.remaining} remaining.`
        );
      }

      return result;
    } catch (error) {
      const remaining = await this.retryQueue.size().catch(() => 0);
      this.logger.warn?.(
        "[smart-memory-openclaw] retry queue flush failed:",
        error.message
      );
      return { flushed: 0, remaining };
    }
  }

  /**
   * @template T
   * @param {() => Promise<T>} task
   * @returns {Promise<T>}
   */
  _enqueueCommit(task) {
    const run = this._commitChain.then(task, task);
    this._commitChain = run.then(() => undefined, () => undefined);
    return run;
  }
}

/**
 * Framework-friendly factory wrapper.
 *
 * @param {ConstructorParameters<typeof SmartMemorySkill>[0] & {
 *   summarizeSessionArc?: (payload: {
 *     prompt: string;
 *     conversationText: string;
 *     turns: Array<{ role: string; content: string }>;
 *     trigger: "checkpoint"|"session_end";
 *   }) => Promise<string>;
 * }} [options]
 */
function createSmartMemorySkill(options = {}) {
  const skill = new SmartMemorySkill(options);

  if (typeof options.summarizeSessionArc === "function") {
    skill.configureSessionArc({ summarizeSessionArc: options.summarizeSessionArc });
  }

  return {
    name: "smart-memory-openclaw",
    description: "Native Smart Memory OpenClaw skill backed by the local FastAPI memory runtime.",
    start: () => skill.startHeartbeat(),
    stop: () => skill.stopHeartbeat(),

    // Tool wrappers
    memory_search: (input) => skill.memorySearch(input),
    memory_commit: (input) => skill.memoryCommit(input),
    memory_insights: (input) => skill.memoryInsights(input),

    // Lifecycle hooks
    on_turn: (payload) => skill.onConversationTurn(payload),
    on_session_end: (payload) => skill.onSessionEnd(payload),

    // Passive context injection middleware
    inject_active_context: (payload) => skill.injectActiveContext(payload),

    // Metadata tool definitions for tool-registration systems
    tools: skill.getToolDefinitions(),

    skill,
  };
}

/**
 * @param {{
 *   content: string;
 *   type: string;
 *   importanceRaw: number;
 *   importanceNormalized: number;
 *   tags: string[];
 *   source?: string;
 *   participants?: string[];
 *   activeProjects?: string[];
 *   metadata?: Record<string, unknown>;
 * }} args
 */
function buildIngestPayload(args) {
  const nowIso = new Date().toISOString();
  const source = String(args.source || "conversation");

  /** @type {Record<string, string>} */
  const typeHints = {
    semantic: "Explicit semantic memory commit: factual statement.",
    episodic: "Explicit episodic memory commit: event timeline.",
    belief: "Explicit belief memory commit: preference or inference.",
    goal: "Explicit goal memory commit: objective or task.",
  };

  return {
    user_message: args.content,
    assistant_message: typeHints[args.type] || "Explicit memory commit.",
    timestamp: nowIso,
    source,
    participants:
      Array.isArray(args.participants) && args.participants.length
        ? args.participants
        : ["user", "assistant"],
    active_projects: Array.isArray(args.activeProjects) ? args.activeProjects : [],
    metadata: {
      ...(args.metadata || {}),
      explicit_memory_commit: true,
      requested_type: args.type,
      importance_1_to_10: args.importanceRaw,
      importance_normalized: args.importanceNormalized,
      tags: args.tags,
      committed_at: nowIso,
    },
  };
}

/**
 * @param {unknown} value
 * @param {number} fallback
 * @param {number} min
 * @param {number} max
 */
function clampInteger(value, fallback, min, max) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, Math.floor(parsed)));
}

/**
 * @param {unknown} value
 * @param {number} fallback
 * @param {number} min
 * @param {number} max
 */
function clampNumber(value, fallback, min, max) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, parsed));
}

module.exports = {
  SmartMemorySkill,
  createSmartMemorySkill,
  buildIngestPayload,
  createOpenClawHooks,
};











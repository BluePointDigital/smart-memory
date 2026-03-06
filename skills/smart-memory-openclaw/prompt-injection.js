"use strict";

const {
  PENDING_INSIGHT_PROMPT_GUIDANCE,
} = require("./constants");
const { formatActiveContextBlock } = require("./formatters");

/**
 * Prompt Injection Helper
 *
 * Add this line to your base system prompt:
 *
 * "If pending insights appear in your context that relate to the current conversation,
 * surface them naturally to the user. Do not force it â€” but if there is a genuine
 * connection, seamlessly bring it up."
 */

class PromptContextInjector {
  /**
   * @param {{
   *   apiClient: import("./http-client").CognitiveApiClient;
   *   healthCheck: () => Promise<{ healthy: boolean; reachable: boolean; embedderLoaded: boolean; status: string | null }>;
   *   logger?: Pick<Console, "warn" | "error">;
   * }} options
   */
  constructor(options) {
    this.apiClient = options.apiClient;
    this.healthCheck = options.healthCheck;
    this.logger = options.logger || console;
  }

  /**
   * @param {{
   *   baseSystemPrompt: string;
   *   agentIdentity: string;
   *   currentUserMessage: string;
   *   conversationHistory?: string;
   *   hotMemory?: {
   *     agent_state?: { status?: string };
   *     active_projects?: string[];
   *     working_questions?: string[];
   *     top_of_mind?: string[];
   *   };
   *   maxPromptTokens?: number;
   *   retrievalTimeoutMs?: number;
   *   maxCandidateMemories?: number;
   *   maxSelectedMemories?: number;
   * }} params
   */
  async inject(params) {
    const health = await this.healthCheck();
    if (!health.healthy) {
      return {
        ok: false,
        systemPrompt: String(params.baseSystemPrompt || ""),
        reason: health.reachable
          ? "Memory context unavailable (embedder not loaded)."
          : "Memory context unavailable (server unreachable).",
        compose: null,
        pendingInsights: [],
      };
    }

    const composePayload = {
      agent_identity: params.agentIdentity,
      current_user_message: params.currentUserMessage,
      conversation_history: params.conversationHistory || "",
      max_prompt_tokens: Number(params.maxPromptTokens || 8192),
      retrieval_timeout_ms: Number(params.retrievalTimeoutMs || 500),
      max_candidate_memories: Number(params.maxCandidateMemories || 30),
      max_selected_memories: Number(params.maxSelectedMemories || 5),
    };

    if (params.hotMemory && typeof params.hotMemory === "object") {
      composePayload.hot_memory = params.hotMemory;
    }

    let compose = null;
    let pendingInsights = [];

    try {
      [compose, pendingInsights] = await Promise.all([
        this.apiClient.compose(composePayload),
        this.apiClient.pendingInsights(),
      ]);
    } catch (error) {
      this.logger.warn?.("[smart-memory-openclaw] prompt injection failed:", error.message);
      return {
        ok: false,
        systemPrompt: String(params.baseSystemPrompt || ""),
        reason: `Memory context request failed: ${error.message}`,
        compose: null,
        pendingInsights: [],
      };
    }

    const resolvedHotMemory = resolveHotMemory(params.hotMemory, compose);
    const insights = Array.isArray(pendingInsights?.insights)
      ? pendingInsights.insights
      : Array.isArray(compose?.selected_insights)
      ? compose.selected_insights
      : [];

    const contextBlock = formatActiveContextBlock({
      status:
        resolvedHotMemory.agent_state?.status || compose?.interaction_state || "idle",
      activeProjects: resolvedHotMemory.active_projects || [],
      workingQuestions: resolvedHotMemory.working_questions || [],
      topOfMind: resolvedHotMemory.top_of_mind || [],
      pendingInsights: insights,
    });

    const baseSystemPrompt = String(params.baseSystemPrompt || "").trim();
    const mergedPrompt = [
      baseSystemPrompt,
      "",
      contextBlock,
      "",
      `Prompt Guidance: ${PENDING_INSIGHT_PROMPT_GUIDANCE}`,
    ]
      .filter(Boolean)
      .join("\n");

    return {
      ok: true,
      systemPrompt: mergedPrompt,
      compose,
      pendingInsights: insights,
      activeContextBlock: contextBlock,
    };
  }
}

/**
 * @param {any} provided
 * @param {any} compose
 */
function resolveHotMemory(provided, compose) {
  if (provided && typeof provided === "object") {
    return {
      agent_state: provided.agent_state || { status: compose?.interaction_state || "idle" },
      active_projects: asArray(provided.active_projects),
      working_questions: asArray(provided.working_questions),
      top_of_mind: asArray(provided.top_of_mind),
    };
  }

  const metadataHot = compose?.metadata?.hot_memory;
  if (metadataHot && typeof metadataHot === "object") {
    return {
      agent_state: metadataHot.agent_state || { status: compose?.interaction_state || "idle" },
      active_projects: asArray(metadataHot.active_projects),
      working_questions: asArray(metadataHot.working_questions),
      top_of_mind: asArray(metadataHot.top_of_mind),
    };
  }

  return {
    agent_state: { status: compose?.interaction_state || "idle" },
    active_projects: [],
    working_questions: [],
    top_of_mind: [],
  };
}

/**
 * @param {unknown} value
 */
function asArray(value) {
  return Array.isArray(value) ? value : [];
}

module.exports = {
  PromptContextInjector,
};


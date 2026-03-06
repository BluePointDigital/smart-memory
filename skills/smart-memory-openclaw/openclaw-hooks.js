"use strict";

/**
 * OpenClaw lifecycle wiring helper.
 *
 * This gives a direct bridge for:
 * - passive prompt injection before model response
 * - session arc checkpoints every 20 turns
 * - session end arc capture
 */

/**
 * @param {{
 *   skill: import("./index").SmartMemorySkill;
 *   agentIdentity: string;
 *   summarizeWithLLM?: (payload: {
 *     prompt: string;
 *     conversationText: string;
 *     turns: Array<{ role: string; content: string }>;
 *     trigger: "checkpoint"|"session_end";
 *   }) => Promise<string>;
 *   checkpointTurns?: number;
 *   maxTurns?: number;
 * }} options
 */
function createOpenClawHooks(options) {
  const skill = options.skill;

  if (typeof options.summarizeWithLLM === "function") {
    skill.configureSessionArc({
      summarizeSessionArc: options.summarizeWithLLM,
      checkpointTurns: options.checkpointTurns || 20,
      maxTurns: options.maxTurns || 20,
    });
  }

  return {
    /**
     * Call before each model response.
     *
     * @param {{
     *   baseSystemPrompt: string;
     *   userMessage: string;
     *   conversationHistoryText?: string;
     *   hotMemory?: any;
     * }} ctx
     */
    beforeModelResponse: async (ctx) => {
      return skill.injectActiveContext({
        baseSystemPrompt: String(ctx.baseSystemPrompt || ""),
        agentIdentity: String(options.agentIdentity || "OpenClaw Agent"),
        currentUserMessage: String(ctx.userMessage || ""),
        conversationHistory: String(ctx.conversationHistoryText || ""),
        hotMemory: ctx.hotMemory,
      });
    },

    /**
     * Call on every appended turn.
     *
     * @param {{ conversationHistory: Array<{ role: string; content: string }> }} ctx
     */
    onTurn: async (ctx) => {
      return skill.onConversationTurn({
        conversationHistory: Array.isArray(ctx.conversationHistory)
          ? ctx.conversationHistory
          : [],
      });
    },

    /**
     * Call when the session is ending/resetting.
     *
     * @param {{ conversationHistory: Array<{ role: string; content: string }> }} ctx
     */
    onSessionEnd: async (ctx) => {
      return skill.onSessionEnd({
        conversationHistory: Array.isArray(ctx.conversationHistory)
          ? ctx.conversationHistory
          : [],
      });
    },
  };
}

module.exports = {
  createOpenClawHooks,
};

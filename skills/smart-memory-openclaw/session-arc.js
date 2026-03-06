"use strict";

const { SESSION_ARC_SUMMARY_PROMPT } = require("./constants");

class SessionArcCapturer {
  /**
   * @param {{
   *   memoryCommit: (input: {
   *     content: string;
   *     type: "episodic";
   *     importance?: number;
   *     tags?: string[];
   *   }) => Promise<unknown>;
   *   summarizeSessionArc: (payload: {
   *     prompt: string;
   *     conversationText: string;
   *     turns: Array<{ role: string; content: string }>;
   *     trigger: "checkpoint"|"session_end";
   *   }) => Promise<string>;
   *   checkpointTurns?: number;
   *   maxTurns?: number;
   *   logger?: Pick<Console, "warn" | "error">;
   * }} options
   */
  constructor(options) {
    this.memoryCommit = options.memoryCommit;
    this.summarizeSessionArc = options.summarizeSessionArc;
    this.checkpointTurns = Math.max(1, Number(options.checkpointTurns || 20));
    this.maxTurns = Math.max(1, Number(options.maxTurns || 20));
    this.logger = options.logger || console;
    this.turnCount = 0;
    this._captureChain = Promise.resolve();
  }

  /**
   * @param {{ conversationHistory: Array<{ role: string; content: string }> }} payload
   */
  async onTurn(payload) {
    this.turnCount += 1;

    if (this.turnCount % this.checkpointTurns !== 0) {
      return null;
    }

    return this._enqueueCapture(() => this.captureArc(payload, "checkpoint"));
  }

  /**
   * @param {{ conversationHistory: Array<{ role: string; content: string }> }} payload
   */
  async onSessionEnd(payload) {
    return this._enqueueCapture(() => this.captureArc(payload, "session_end"));
  }

  /**
   * @param {{ conversationHistory: Array<{ role: string; content: string }> }} payload
   * @param {"checkpoint"|"session_end"} trigger
   */
  async captureArc(payload, trigger) {
    const turns = normalizeConversationTurns(payload?.conversationHistory).slice(-this.maxTurns);
    if (!turns.length) {
      return null;
    }

    const conversationText = turns
      .map((turn) => `${capitalize(turn.role)}: ${turn.content}`)
      .join("\n");

    let summary;
    try {
      summary = await this.summarizeSessionArc({
        prompt: SESSION_ARC_SUMMARY_PROMPT,
        conversationText,
        turns,
        trigger,
      });
    } catch (error) {
      this.logger.warn?.("[smart-memory-openclaw] session arc summarization failed:", error.message);
      return null;
    }

    const normalizedSummary = String(summary || "").trim();
    if (!normalizedSummary) {
      return null;
    }

    const isoDate = new Date().toISOString().slice(0, 10);

    try {
      return await this.memoryCommit({
        content: normalizedSummary,
        type: "episodic",
        importance: 7,
        tags: ["session_arc", isoDate],
      });
    } catch (error) {
      this.logger.warn?.("[smart-memory-openclaw] session arc commit failed:", error.message);
      return null;
    }
  }

  /**
   * @template T
   * @param {() => Promise<T>} task
   * @returns {Promise<T>}
   */
  _enqueueCapture(task) {
    const run = this._captureChain.then(task, task);
    this._captureChain = run.then(() => undefined, () => undefined);
    return run;
  }
}

/**
 * @param {unknown} history
 * @returns {Array<{ role: string; content: string }>}
 */
function normalizeConversationTurns(history) {
  if (!Array.isArray(history)) {
    return [];
  }

  return history
    .map((turn) => {
      const role = String(turn?.role || "user").toLowerCase();
      const content = String(turn?.content || "").trim();
      return { role, content };
    })
    .filter((turn) => turn.content.length > 0);
}

/**
 * @param {string} value
 */
function capitalize(value) {
  return value ? value.slice(0, 1).toUpperCase() + value.slice(1) : value;
}

module.exports = {
  SessionArcCapturer,
  normalizeConversationTurns,
};


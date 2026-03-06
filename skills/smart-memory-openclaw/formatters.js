"use strict";

/**
 * @param {unknown} value
 * @param {number} fallback
 */
function asNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

/**
 * @param {string} query
 * @param {Array<{ memory?: any; score?: number; vector_score?: number }>} ranked
 * @returns {string}
 */
function formatMemorySearchResults(query, ranked) {
  if (!Array.isArray(ranked) || ranked.length === 0) {
    return `No relevant memories found for: ${query}`;
  }

  const lines = ["[MEMORY SEARCH RESULTS]"];

  ranked.forEach((item, idx) => {
    const memory = item.memory || item || {};
    const type = String(memory.type || "unknown");
    const content = String(memory.content || "").trim();
    const relevance = asNumber(item.score, asNumber(item.vector_score, 0));
    const createdAt = String(memory.created_at || memory.last_accessed || "unknown");

    lines.push(
      `${idx + 1}. [${type}] relevance=${relevance.toFixed(3)} created=${createdAt}`
    );
    lines.push(`   ${content || "(empty content)"}`);
  });

  return lines.join("\n");
}

/**
 * @param {Array<{ content?: string; confidence?: number; source_memory_ids?: string[]; generated_at?: string }>} insights
 * @param {number} limit
 * @returns {string}
 */
function formatPendingInsights(insights, limit) {
  const safeLimit = Math.max(1, Math.floor(Number(limit) || 10));
  const rows = Array.isArray(insights) ? insights.slice(0, safeLimit) : [];

  if (!rows.length) {
    return "No pending background insights.";
  }

  const lines = ["[PENDING INSIGHTS]"];
  rows.forEach((insight, idx) => {
    const content = String(insight.content || "").trim() || "(empty)";
    const confidence = asNumber(insight.confidence, 0);
    const related = Array.isArray(insight.source_memory_ids)
      ? insight.source_memory_ids.join(", ")
      : "none";
    const generatedAt = String(insight.generated_at || "unknown");

    lines.push(
      `${idx + 1}. confidence=${confidence.toFixed(2)} generated=${generatedAt}`
    );
    lines.push(`   insight: ${content}`);
    lines.push(`   related_memories: ${related || "none"}`);
  });

  return lines.join("\n");
}

/**
 * @param {string[]} values
 * @returns {string}
 */
function inlineList(values) {
  if (!Array.isArray(values) || !values.length) {
    return "none";
  }
  return values.map((item) => String(item).trim()).filter(Boolean).join(", ") || "none";
}

/**
 * @param {{
 *   status: string;
 *   activeProjects: string[];
 *   workingQuestions: string[];
 *   topOfMind: string[];
 *   pendingInsights: Array<{ content?: string }>;
 * }} input
 * @returns {string}
 */
function formatActiveContextBlock(input) {
  const insightLines = (Array.isArray(input.pendingInsights) ? input.pendingInsights : [])
    .map((insight) => String(insight.content || "").trim())
    .filter(Boolean)
    .map((line) => `- ${line}`);

  if (!insightLines.length) {
    insightLines.push("- none");
  }

  return [
    "[ACTIVE CONTEXT]",
    `Status: ${input.status || "idle"}`,
    `Active Projects: ${inlineList(input.activeProjects)}`,
    `Working Questions: ${inlineList(input.workingQuestions)}`,
    `Top of Mind: ${inlineList(input.topOfMind)}`,
    "",
    "Pending Insights:",
    ...insightLines,
    "[/ACTIVE CONTEXT]",
  ].join("\n");
}

module.exports = {
  asNumber,
  formatMemorySearchResults,
  formatPendingInsights,
  formatActiveContextBlock,
  inlineList,
};

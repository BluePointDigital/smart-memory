"use strict";

/**
 * @typedef {(text: string, context: { content: string; tags: string[] }) => boolean|string[]|null|undefined} TagRuleTestFn
 */

/**
 * @typedef {{ id: string; test: TagRuleTestFn; add: string[] }} TagRule
 */

/** @type {TagRule[]} */
const DEFAULT_TAG_RULES = [
  {
    id: "working_question",
    test: (text) => text.includes("?"),
    add: ["working_question"],
  },
  {
    id: "decision",
    test: (text) => /(\bdecided\b|\bchose\b|\bsettled on\b|\bresolved\b)/i.test(text),
    add: ["decision"],
  },
];

/**
 * @param {string} content
 * @param {{ tags?: string[]; rules?: TagRule[] }} [options]
 * @returns {string[]}
 */
function buildAutoTags(content, options = {}) {
  const inputTags = Array.isArray(options.tags) ? options.tags : [];
  const rules = Array.isArray(options.rules) && options.rules.length ? options.rules : DEFAULT_TAG_RULES;

  const normalized = dedupeTags(inputTags);
  if (normalized.length) {
    return normalized;
  }

  const text = String(content || "").trim();
  if (!text) {
    return [];
  }

  const generated = [];
  for (const rule of rules) {
    if (!rule || typeof rule.test !== "function") {
      continue;
    }

    const outcome = rule.test(text, { content: text, tags: generated.slice() });
    if (!outcome) {
      continue;
    }

    if (Array.isArray(outcome)) {
      generated.push(...outcome);
      continue;
    }

    if (outcome === true && Array.isArray(rule.add)) {
      generated.push(...rule.add);
    }
  }

  return dedupeTags(generated);
}

/**
 * @param {string[]} tags
 * @returns {string[]}
 */
function dedupeTags(tags) {
  const seen = new Set();
  const out = [];

  for (const tag of tags) {
    const value = String(tag || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "_");
    if (!value || seen.has(value)) {
      continue;
    }
    seen.add(value);
    out.push(value);
  }

  return out;
}

module.exports = {
  DEFAULT_TAG_RULES,
  buildAutoTags,
  dedupeTags,
};

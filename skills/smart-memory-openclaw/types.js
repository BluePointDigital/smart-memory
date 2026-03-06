"use strict";

/**
 * @typedef {"semantic"|"episodic"|"belief"|"goal"} MemoryType
 */

/**
 * @typedef {"all"|MemoryType} MemorySearchType
 */

/**
 * @typedef {Object} MemorySearchInput
 * @property {string} query
 * @property {MemorySearchType} [type]
 * @property {number} [limit]
 * @property {number} [min_relevance]
 * @property {string} [conversation_history]
 */

/**
 * @typedef {Object} MemoryCommitInput
 * @property {string} content
 * @property {MemoryType} type
 * @property {number} [importance]
 * @property {string[]} [tags]
 * @property {string} [source]
 * @property {string[]} [participants]
 * @property {string[]} [active_projects]
 * @property {Object.<string, unknown>} [metadata]
 */

/**
 * @typedef {Object} MemoryInsightsInput
 * @property {number} [limit]
 */

/**
 * @typedef {Object} RetrievalMemory
 * @property {string} id
 * @property {MemoryType} type
 * @property {string} content
 * @property {number} importance
 * @property {string} created_at
 * @property {string} [last_accessed]
 */

/**
 * @typedef {Object} RankedMemory
 * @property {RetrievalMemory} memory
 * @property {number} score
 * @property {number} [vector_score]
 */

/**
 * @typedef {Object} Insight
 * @property {string} id
 * @property {string} content
 * @property {number} confidence
 * @property {string[]} [source_memory_ids]
 * @property {string} [generated_at]
 */

module.exports = {};

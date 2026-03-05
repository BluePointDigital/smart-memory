"use strict";

const { DEFAULT_BASE_URL } = require("./constants");

class HttpError extends Error {
  /**
   * @param {string} message
   * @param {number} status
   * @param {unknown} [body]
   */
  constructor(message, status, body) {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.body = body;
  }
}

/**
 * @param {unknown} error
 * @returns {boolean}
 */
function isServerUnreachableError(error) {
  if (!error) {
    return false;
  }

  const message = String(error.message || error).toLowerCase();
  return (
    message.includes("fetch failed") ||
    message.includes("econnrefused") ||
    message.includes("enotfound") ||
    message.includes("network") ||
    message.includes("timed out") ||
    message.includes("aborted")
  );
}

/**
 * @param {string} baseUrl
 * @param {string} endpoint
 * @returns {string}
 */
function buildUrl(baseUrl, endpoint) {
  return `${baseUrl.replace(/\/$/, "")}${endpoint}`;
}

class CognitiveApiClient {
  /**
   * @param {{
   *   baseUrl?: string;
   *   timeoutMs?: number;
   *   fetchImpl?: typeof fetch;
   * }} [options]
   */
  constructor(options = {}) {
    this.baseUrl = options.baseUrl || DEFAULT_BASE_URL;
    this.timeoutMs = Number(options.timeoutMs || 10_000);
    this.fetchImpl = options.fetchImpl || globalThis.fetch;

    if (typeof this.fetchImpl !== "function") {
      throw new Error("Global fetch is not available. Use Node 18+ or pass fetchImpl.");
    }
  }

  /**
   * @template T
   * @param {"GET"|"POST"} method
   * @param {string} endpoint
   * @param {unknown} [payload]
   * @returns {Promise<T>}
   */
  async request(method, endpoint, payload) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    const headers = {};
    /** @type {RequestInit} */
    const init = {
      method,
      signal: controller.signal,
      headers,
    };

    if (payload !== undefined) {
      headers["content-type"] = "application/json";
      init.body = JSON.stringify(payload);
    }

    try {
      const response = await this.fetchImpl(buildUrl(this.baseUrl, endpoint), init);
      const text = await response.text();
      const body = text ? safeJsonParse(text) : {};

      if (!response.ok) {
        throw new HttpError(
          `HTTP ${response.status} calling ${endpoint}`,
          response.status,
          body
        );
      }

      return /** @type {T} */ (body);
    } finally {
      clearTimeout(timeout);
    }
  }

  /**
   * @returns {Promise<{
   *   healthy: boolean;
   *   reachable: boolean;
   *   embedderLoaded: boolean;
   *   status: string | null;
   *   detail?: unknown;
   *   error?: unknown;
   * }>}
   */
  async checkHealth() {
    try {
      const health = await this.request("GET", "/health");
      const embedderLoaded = Boolean(health.embedder_loaded);
      const status = typeof health.status === "string" ? health.status : null;

      return {
        healthy: embedderLoaded,
        reachable: true,
        embedderLoaded,
        status,
        detail: health,
      };
    } catch (error) {
      if (error instanceof HttpError) {
        return {
          healthy: false,
          reachable: true,
          embedderLoaded: false,
          status: "http_error",
          detail: error.body,
          error,
        };
      }

      return {
        healthy: false,
        reachable: false,
        embedderLoaded: false,
        status: "unreachable",
        error,
      };
    }
  }

  /**
   * @param {import("./types").MemorySearchInput & { conversation_history?: string }} payload
   */
  async retrieve(payload) {
    return this.request("POST", "/retrieve", payload);
  }

  /**
   * @param {Record<string, unknown>} payload
   */
  async ingest(payload) {
    return this.request("POST", "/ingest", payload);
  }

  /**
   * @param {Record<string, unknown>} payload
   */
  async compose(payload) {
    return this.request("POST", "/compose", payload);
  }

  async pendingInsights() {
    return this.request("GET", "/insights/pending");
  }

  /**
   * @param {boolean} [scheduled]
   */
  async runBackground(scheduled = true) {
    return this.request("POST", "/run_background", { scheduled: Boolean(scheduled) });
  }
}

/**
 * @param {string} raw
 * @returns {any}
 */
function safeJsonParse(raw) {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

module.exports = {
  CognitiveApiClient,
  HttpError,
  buildUrl,
  isServerUnreachableError,
};

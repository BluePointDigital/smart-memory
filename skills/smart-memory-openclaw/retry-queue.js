"use strict";

const fs = require("fs");
const path = require("path");
const { MEMORY_RETRY_QUEUE_FILE } = require("./constants");

class MemoryRetryQueue {
  /**
   * @param {{ queueFilePath?: string }} [options]
   */
  constructor(options = {}) {
    this.queueFilePath = options.queueFilePath
      ? path.resolve(options.queueFilePath)
      : path.resolve(process.cwd(), MEMORY_RETRY_QUEUE_FILE);

    this._opChain = Promise.resolve();
  }

  /**
   * @template T
   * @param {() => Promise<T>} task
   * @returns {Promise<T>}
   */
  _serialized(task) {
    const run = this._opChain.then(task, task);
    this._opChain = run.then(() => undefined, () => undefined);
    return run;
  }

  /**
   * @returns {Promise<Array<{ id: string; enqueued_at: string; payload: Record<string, unknown> }>>}
   */
  async load() {
    return this._serialized(async () => {
      return this._loadUnsafe();
    });
  }

  /**
   * @param {Record<string, unknown>} payload
   */
  async enqueue(payload) {
    return this._serialized(async () => {
      const queue = await this._loadUnsafe();
      queue.push({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
        enqueued_at: new Date().toISOString(),
        payload,
      });
      await this._saveUnsafe(queue);
      return queue.length;
    });
  }

  /**
   * @param {(payload: Record<string, unknown>) => Promise<unknown>} flushFn
   * @returns {Promise<{ flushed: number; remaining: number }>}
   */
  async flush(flushFn) {
    return this._serialized(async () => {
      const queue = await this._loadUnsafe();
      if (!queue.length) {
        return { flushed: 0, remaining: 0 };
      }

      let flushed = 0;
      const remaining = [];

      for (let i = 0; i < queue.length; i += 1) {
        const entry = queue[i];
        try {
          await flushFn(entry.payload);
          flushed += 1;
        } catch {
          remaining.push(...queue.slice(i));
          break;
        }
      }

      await this._saveUnsafe(remaining);
      return { flushed, remaining: remaining.length };
    });
  }

  async size() {
    const queue = await this.load();
    return queue.length;
  }

  async _loadUnsafe() {
    if (!fs.existsSync(this.queueFilePath)) {
      return [];
    }

    try {
      const raw = await fs.promises.readFile(this.queueFilePath, "utf8");
      if (!raw.trim()) {
        return [];
      }

      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) {
        return [];
      }

      return parsed.filter((item) => item && typeof item === "object" && item.payload);
    } catch {
      const corruptPath = `${this.queueFilePath}.corrupt-${Date.now()}`;
      try {
        await fs.promises.rename(this.queueFilePath, corruptPath);
      } catch {
        // Best effort.
      }
      return [];
    }
  }

  /**
   * @param {unknown[]} queue
   */
  async _saveUnsafe(queue) {
    const dir = path.dirname(this.queueFilePath);
    await fs.promises.mkdir(dir, { recursive: true });
    await fs.promises.writeFile(this.queueFilePath, JSON.stringify(queue, null, 2), "utf8");
  }
}

module.exports = {
  MemoryRetryQueue,
};

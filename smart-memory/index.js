import { spawn, spawnSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import process from 'process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PROJECT_ROOT = path.resolve(__dirname, '..');
const DEFAULT_HOST = process.env.COGNITIVE_API_HOST || '127.0.0.1';
const DEFAULT_PORT = Number(process.env.COGNITIVE_API_PORT || 8000);
const DEFAULT_STARTUP_TIMEOUT_MS = Number(
  process.env.COGNITIVE_API_STARTUP_TIMEOUT_MS || 120000
);
const DEFAULT_HEALTH_POLL_INTERVAL_MS = 300;
const DEFAULT_BACKGROUND_INTERVAL_MS = 60 * 60 * 1000;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isWindows() {
  return process.platform === 'win32';
}

function resolveVenvPython(projectRoot) {
  if (isWindows()) {
    return path.join(projectRoot, '.venv', 'Scripts', 'python.exe');
  }
  return path.join(projectRoot, '.venv', 'bin', 'python');
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      'content-type': 'application/json',
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`HTTP ${response.status} for ${url}: ${errorBody}`);
  }

  const text = await response.text();
  return text ? JSON.parse(text) : {};
}

async function waitForHealthy(baseUrl, timeoutMs) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(`${baseUrl}/health`, { method: 'GET' });
      if (response.ok) {
        return;
      }
    } catch {
      // Keep polling until timeout.
    }

    await sleep(DEFAULT_HEALTH_POLL_INTERVAL_MS);
  }

  throw new Error(`Cognitive API did not become healthy within ${timeoutMs}ms`);
}

class CognitiveApiAdapter {
  constructor(options = {}) {
    this.host = options.host || DEFAULT_HOST;
    this.port = Number(options.port || DEFAULT_PORT);
    this.baseUrl = options.baseUrl || `http://${this.host}:${this.port}`;
    this.startupTimeoutMs = Number(options.startupTimeoutMs || DEFAULT_STARTUP_TIMEOUT_MS);
    this.backgroundIntervalMs = Number(
      options.backgroundIntervalMs || DEFAULT_BACKGROUND_INTERVAL_MS
    );
    this.enableBackground =
      options.enableBackground === undefined ? true : Boolean(options.enableBackground);
    this.projectRoot = options.projectRoot || PROJECT_ROOT;

    this.pythonProcess = null;
    this.ownsPythonProcess = false;
    this.backgroundTimer = null;
    this.started = false;
    this.startPromise = null;
    this.cleanupRegistered = false;
  }

  async _isHealthy() {
    try {
      const response = await fetch(`${this.baseUrl}/health`, { method: 'GET' });
      return response.ok;
    } catch {
      return false;
    }
  }

  _registerCleanupHandlers() {
    if (this.cleanupRegistered) {
      return;
    }
    this.cleanupRegistered = true;

    const gracefulShutdown = async () => {
      try {
        await this.stop();
      } finally {
        process.exit(0);
      }
    };

    process.once('SIGINT', gracefulShutdown);
    process.once('SIGTERM', gracefulShutdown);

    process.once('exit', () => {
      this._killPythonSync();
    });
  }

  _startBackgroundCron() {
    if (!this.enableBackground || this.backgroundTimer) {
      return;
    }

    this.backgroundTimer = setInterval(() => {
      this.runBackground(true).catch((error) => {
        console.error('[smart-memory] Background run failed:', error.message);
      });
    }, this.backgroundIntervalMs);

    if (typeof this.backgroundTimer.unref === 'function') {
      this.backgroundTimer.unref();
    }
  }

  _stopBackgroundCron() {
    if (!this.backgroundTimer) {
      return;
    }
    clearInterval(this.backgroundTimer);
    this.backgroundTimer = null;
  }

  _killPythonSync() {
    if (!this.pythonProcess || !this.ownsPythonProcess) {
      return;
    }

    const pid = this.pythonProcess.pid;
    if (!pid) {
      return;
    }

    try {
      if (isWindows()) {
        spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], {
          stdio: 'ignore',
          windowsHide: true,
        });
      } else {
        try {
          process.kill(-pid, 'SIGTERM');
        } catch {
          process.kill(pid, 'SIGTERM');
        }
      }
    } catch {
      // Best effort cleanup.
    }
  }

  async start() {
    if (this.started) {
      return;
    }

    if (this.startPromise) {
      return this.startPromise;
    }

    this.startPromise = this._startInternal()
      .catch((error) => {
        this.started = false;
        throw error;
      })
      .finally(() => {
        this.startPromise = null;
      });

    return this.startPromise;
  }

  async _startInternal() {
    if (await this._isHealthy()) {
      this.started = true;
      this._registerCleanupHandlers();
      this._startBackgroundCron();
      return;
    }

    const venvPython = resolveVenvPython(this.projectRoot);
    if (!fs.existsSync(venvPython)) {
      throw new Error(
        `Python virtualenv not found at ${venvPython}. Run npm install to trigger postinstall.`
      );
    }

    const args = [
      '-m',
      'uvicorn',
      'server:app',
      '--host',
      this.host,
      '--port',
      String(this.port),
    ];

    this.pythonProcess = spawn(venvPython, args, {
      cwd: this.projectRoot,
      detached: true,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    });
    this.ownsPythonProcess = true;

    this.pythonProcess.stdout?.on('data', (chunk) => {
      if (process.env.COGNITIVE_API_DEBUG === '1') {
        process.stdout.write(`[cognitive-api] ${chunk.toString()}`);
      }
    });

    this.pythonProcess.stderr?.on('data', (chunk) => {
      if (process.env.COGNITIVE_API_DEBUG === '1') {
        process.stderr.write(`[cognitive-api] ${chunk.toString()}`);
      }
    });

    this.pythonProcess.on('exit', () => {
      this.pythonProcess = null;
      this.started = false;
      this.ownsPythonProcess = false;
    });

    await waitForHealthy(this.baseUrl, this.startupTimeoutMs);

    this.started = true;
    this._registerCleanupHandlers();
    this._startBackgroundCron();
  }

  async stop() {
    this._stopBackgroundCron();

    if (this.pythonProcess && this.ownsPythonProcess) {
      const pid = this.pythonProcess.pid;
      this._killPythonSync();
      this.pythonProcess = null;
      this.ownsPythonProcess = false;

      if (pid) {
        await sleep(150);
      }
    }

    this.started = false;
  }

  async ingestMessage(interaction) {
    await this.start();
    return fetchJson(`${this.baseUrl}/ingest`, {
      method: 'POST',
      body: JSON.stringify(interaction),
    });
  }

  async retrieveContext({ user_message, conversation_history = '' }) {
    await this.start();
    return fetchJson(`${this.baseUrl}/retrieve`, {
      method: 'POST',
      body: JSON.stringify({ user_message, conversation_history }),
    });
  }

  async getPromptContext(promptComposerRequest) {
    await this.start();
    return fetchJson(`${this.baseUrl}/compose`, {
      method: 'POST',
      body: JSON.stringify(promptComposerRequest),
    });
  }

  async runBackground(scheduled = true) {
    await this.start();
    return fetchJson(`${this.baseUrl}/run_background`, {
      method: 'POST',
      body: JSON.stringify({ scheduled }),
    });
  }
}

const adapter = new CognitiveApiAdapter();

export { CognitiveApiAdapter };
export async function init() {
  await adapter.start();
  return adapter;
}
export async function start() {
  return init();
}
export async function stop() {
  return adapter.stop();
}
export async function ingestMessage(interaction) {
  return adapter.ingestMessage(interaction);
}
export async function retrieveContext(payload) {
  return adapter.retrieveContext(payload);
}
export async function getPromptContext(payload) {
  return adapter.getPromptContext(payload);
}
export async function runBackground(scheduled = true) {
  return adapter.runBackground(scheduled);
}

export default adapter;

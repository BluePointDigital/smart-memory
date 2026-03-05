#!/usr/bin/env node
/**
 * Node.js Session Memory Primer
 * For agents built with Node.js (OpenAI assistants, custom bots, etc.)
 * 
 * Usage:
 *   const { primeMemory } = require('./nodejs-agent');
 *   const context = await primeMemory({ agentIdentity: 'MyBot' });
 * 
 * Or CLI:
 *   node nodejs-agent.js --agent-name "MyBot" --output context.json
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const DEFAULT_SERVER = 'http://127.0.0.1:8000';

async function httpRequest(url, options = {}, data = null) {
  return new Promise((resolve, reject) => {
    const req = http.request(url, { ...options, method: options.method || 'GET' }, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => resolve({ status: res.statusCode, body }));
    });
    req.on('error', reject);
    if (data) req.write(data);
    req.end();
  });
}

async function checkHealth(serverUrl = DEFAULT_SERVER) {
  try {
    const res = await httpRequest(`${serverUrl}/health`);
    return res.status === 200;
  } catch {
    return false;
  }
}

async function startServer() {
  const paths = ['./smart-memory', '../smart-memory', './skills/smart-memory'];
  
  for (const dir of paths) {
    const activatePath = path.join(dir, '.venv/bin/activate');
    if (fs.existsSync(activatePath)) {
      const proc = spawn('bash', [
        '-c',
        `cd ${dir} && . .venv/bin/activate && python -m uvicorn server:app --host 127.0.0.1 --port 8000 > /tmp/smart-memory-server.log 2>&1 &`
      ], { detached: true });
      proc.unref();
      
      // Wait for startup
      await new Promise(r => setTimeout(r, 3000));
      
      if (await checkHealth()) {
        return true;
      }
    }
  }
  
  return false;
}

async function ensureServerRunning(serverUrl = DEFAULT_SERVER) {
  if (await checkHealth(serverUrl)) {
    return true;
  }
  return await startServer();
}

async function primeMemory({
  agentIdentity,
  userMessage = 'Session start',
  serverUrl = DEFAULT_SERVER,
  activeProjects = [],
  workingQuestions = [],
} = {}) {
  if (!await ensureServerRunning(serverUrl)) {
    return { status: 'error', message: 'Memory server unavailable' };
  }
  
  const now = new Date().toISOString();
  
  const payload = {
    agent_identity: agentIdentity,
    current_user_message: userMessage,
    conversation_history: '',
    hot_memory: {
      agent_state: {
        status: 'engaged',
        last_interaction_timestamp: now,
        last_background_task: 'session_start',
      },
      active_projects: activeProjects,
      working_questions: workingQuestions,
      top_of_mind: [],
    },
  };
  
  try {
    const res = await httpRequest(
      `${serverUrl}/compose`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      },
      JSON.stringify(payload)
    );
    
    if (res.status === 200) {
      return JSON.parse(res.body);
    }
    return { status: 'error', message: `HTTP ${res.status}: ${res.body}` };
  } catch (err) {
    return { status: 'error', message: err.message };
  }
}

// CLI
async function main() {
  const args = process.argv.slice(2);
  const getArg = (flag) => {
    const idx = args.indexOf(flag);
    return idx !== -1 ? args[idx + 1] : undefined;
  };
  
  const agentName = getArg('--agent-name');
  const query = getArg('--query') || 'Session start';
  const output = getArg('--output');
  const server = getArg('--server') || DEFAULT_SERVER;
  
  if (!agentName) {
    console.error('Usage: node nodejs-agent.js --agent-name "MyBot" [--query "Session start"] [--output context.json]');
    process.exit(1);
  }
  
  const context = await primeMemory({
    agentIdentity: agentName,
    userMessage: query,
    serverUrl: server,
  });
  
  const outputJson = JSON.stringify(context, null, 2);
  
  if (output) {
    fs.writeFileSync(output, outputJson);
    console.error(`Context saved to ${output}`);
  } else {
    console.log(outputJson);
  }
  
  process.exit(context.status === 'error' ? 1 : 0);
}

if (require.main === module) {
  main().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

module.exports = { primeMemory, ensureServerRunning };

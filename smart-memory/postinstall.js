import { spawnSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const projectRoot = path.resolve(__dirname, '..');
const requirementsPath = path.join(projectRoot, 'requirements-cognitive.txt');
const venvDir = path.join(projectRoot, '.venv');

function runCommand(command, args, errorLabel) {
  const result = spawnSync(command, args, {
    stdio: 'inherit',
    cwd: projectRoot,
    env: process.env,
  });

  if (result.status !== 0) {
    throw new Error(`${errorLabel} failed: ${command} ${args.join(' ')}`);
  }
}

function commandExists(command, args = ['--version']) {
  const result = spawnSync(command, args, {
    stdio: 'ignore',
    cwd: projectRoot,
    env: process.env,
  });
  return result.status === 0;
}

function resolvePythonExecutable() {
  const candidates = [];
  if (process.env.PYTHON) {
    candidates.push(process.env.PYTHON);
  }

  if (process.platform === 'win32') {
    candidates.push('python', 'py');
  } else {
    candidates.push('python3', 'python');
  }

  for (const candidate of candidates) {
    if (commandExists(candidate)) {
      return candidate;
    }
  }

  throw new Error(
    'Python is required for smart-memory cognitive mode. Set PYTHON or install Python 3.11+.'
  );
}

function resolveVenvPython() {
  if (process.platform === 'win32') {
    return path.join(venvDir, 'Scripts', 'python.exe');
  }
  return path.join(venvDir, 'bin', 'python');
}

function main() {
  if (!fs.existsSync(requirementsPath)) {
    throw new Error(`Missing requirements file: ${requirementsPath}`);
  }

  const systemPython = resolvePythonExecutable();
  const venvPython = resolveVenvPython();

  runCommand(systemPython, ['-m', 'venv', venvDir], 'Creating virtual environment');

  if (!fs.existsSync(venvPython)) {
    throw new Error(`Virtual environment Python not found at ${venvPython}`);
  }

  runCommand(venvPython, ['-m', 'pip', 'install', '--upgrade', 'pip'], 'Upgrading pip');
  // CPU-only policy: keep torch installs pinned to the CPU index; do not use CUDA/generic torch here.
  runCommand(
    venvPython,
    [
      '-m',
      'pip',
      'install',
      'torch',
      'torchvision',
      'torchaudio',
      '--index-url',
      'https://download.pytorch.org/whl/cpu',
    ],
    'Installing CPU-only PyTorch'
  );
  runCommand(
    venvPython,
    ['-m', 'pip', 'install', '-r', requirementsPath],
    'Installing cognitive requirements'
  );

  console.log('Cognitive Python environment ready.');
}

try {
  main();
} catch (error) {
  console.error(error.message);
  process.exit(1);
}

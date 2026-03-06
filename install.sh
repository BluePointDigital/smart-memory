#!/bin/bash
# One-line installer for Smart Memory v3.1 experimental
# Usage: curl -sL https://raw.githubusercontent.com/BluePointDigital/smart-memory/master/install.sh | bash

set -e

echo "Installing Smart Memory v3.1 experimental for OpenClaw..."
echo ""

# Detect OpenClaw workspace
if [ -d "$HOME/.openclaw/workspace" ]; then
    WORKSPACE="$HOME/.openclaw/workspace"
elif [ -d "/config/.openclaw/workspace" ]; then
    WORKSPACE="/config/.openclaw/workspace"
else
    echo "Could not find OpenClaw workspace"
    echo "Please run from your OpenClaw workspace directory"
    exit 1
fi

echo "Found workspace: $WORKSPACE"
echo ""

# Check for Node.js
if ! command -v node >/dev/null 2>&1; then
    echo "Node.js not found. Please install Node.js 18+"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "Node.js version $NODE_VERSION found. Please upgrade to 18+"
    exit 1
fi

echo "Node.js $(node --version) found"

# Check for Python
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
    echo "Python 3.11+ is required for the cognitive engine"
    exit 1
fi

echo "Python found"
echo "CPU-only PyTorch is mandatory for Smart Memory v3.1 (GPU/CUDA builds are intentionally unsupported)."
echo ""

# Download latest repository snapshot
REPO_URL="https://github.com/BluePointDigital/smart-memory"
TARGET_DIR="$WORKSPACE/smart-memory"

rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"

if command -v git >/dev/null 2>&1; then
    cd /tmp
    rm -rf smart-memory-temp 2>/dev/null || true
    git clone --depth 1 "$REPO_URL.git" smart-memory-temp
    cp -r smart-memory-temp/* "$TARGET_DIR/"
    rm -rf smart-memory-temp
else
    cd /tmp
    rm -rf smart-memory-master 2>/dev/null || true
    curl -L "$REPO_URL/archive/refs/heads/master.tar.gz" | tar xz
    cp -r smart-memory-master/* "$TARGET_DIR/"
    rm -rf smart-memory-master
fi

echo "Files installed"
echo ""

# Install Node adapter dependencies (triggers Python venv + requirements via postinstall)
cd "$TARGET_DIR/smart-memory"
npm install --silent

echo ""
echo "Installation complete"
echo ""
echo "Smart Memory v3.1 experimental is ready."
echo "The Node adapter will start the local FastAPI cognitive server automatically when used."

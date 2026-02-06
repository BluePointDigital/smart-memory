#!/usr/bin/env node
/**
 * Smart Memory - Main CLI Entry Point
 * 
 * Hybrid search with SQLite backend:
 * - FTS5 for keyword search
 * - Vector embeddings for semantic search
 * - Auto-detects sqlite-vec for native vector ops
 * 
 * Usage:
 *   node smart_memory.js --sync
 *   node smart_memory.js --search "query" [--max-results 5]
 *   node smart_memory.js --status
 */

import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { fileURLToPath } from 'url';

import { initDatabase, upsertChunk, deleteFileChunks, setMeta, getMeta, getStats } from './db.js';
import { createChunks } from './chunker.js';
import { getEmbedding, getEmbeddingDimension } from './embed.js';
import { hybridSearch, vectorSearch, textSearch } from './search.js';
import { getSearchMode, enableFocus, disableFocus, getModeStatus } from './memory_mode.js';
import { focusSearch, shouldSuggestFocus } from './focus_agent.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Configuration
const MEMORY_DIR = process.env.MEMORY_DIR || '/config/.openclaw/workspace/memory';
const MEMORY_FILE = process.env.MEMORY_FILE || '/config/.openclaw/workspace/MEMORY.md';
const DB_PATH = process.env.MEMORY_DB_PATH || path.join(__dirname, 'vector-memory.db');

/**
 * Compute hash of file content
 */
function hashContent(content) {
    return crypto.createHash('sha256').update(content).digest('hex');
}

/**
 * Sync a single file to the database
 */
async function syncFile(db, filePath) {
    const content = fs.readFileSync(filePath, 'utf-8');
    const contentHash = hashContent(content);
    const relativePath = path.relative('/config/.openclaw/workspace', filePath);
    
    // Check if file needs syncing
    const existingChunks = db.prepare('SELECT content_hash FROM chunks WHERE path = ? LIMIT 1').all(relativePath);
    if (existingChunks.length > 0 && existingChunks[0].content_hash === contentHash) {
        return { path: relativePath, chunks: 0, skipped: true };
    }
    
    // Delete old chunks for this file
    deleteFileChunks(db, relativePath);
    
    // Create chunks
    const chunks = createChunks(content, 1);
    console.error(`  ${relativePath}: ${chunks.length} chunks`);
    
    let embedded = 0;
    for (const chunk of chunks) {
        try {
            const embedding = await getEmbedding(chunk.content.slice(0, 2000));
            upsertChunk(db, {
                path: relativePath,
                startLine: chunk.startLine,
                endLine: chunk.endLine,
                content: chunk.content,
                hash: contentHash,
            }, embedding);
            embedded++;
        } catch (err) {
            console.error(`    Error embedding chunk: ${err.message}`);
        }
    }
    
    return { path: relativePath, chunks: embedded, skipped: false };
}

/**
 * Sync all memory files
 */
async function syncAll() {
    console.error('Starting memory sync...\n');
    
    const db = initDatabase(DB_PATH);
    const results = [];
    
    // Sync MEMORY.md
    if (fs.existsSync(MEMORY_FILE)) {
        results.push(await syncFile(db, MEMORY_FILE));
    }
    
    // Sync memory/ directory
    if (fs.existsSync(MEMORY_DIR)) {
        const files = fs.readdirSync(MEMORY_DIR)
            .filter(f => f.endsWith('.md'))
            .map(f => path.join(MEMORY_DIR, f));
        
        for (const file of files) {
            results.push(await syncFile(db, file));
        }
    }
    
    // Update metadata
    setMeta(db, 'last_sync', new Date().toISOString());
    setMeta(db, 'model_name', 'Xenova/all-MiniLM-L6-v2');
    setMeta(db, 'embedding_dim', String(getEmbeddingDimension()));
    
    const totalChunks = results.reduce((sum, r) => sum + r.chunks, 0);
    const skippedFiles = results.filter(r => r.skipped).length;
    
    console.error(`\n✓ Sync complete: ${totalChunks} chunks (${skippedFiles} files unchanged)`);
    
    db.close();
}

/**
 * Search memory (fast mode - direct vector similarity)
 */
async function performSearchFast(query, maxResults = 5) {
    const db = initDatabase(DB_PATH);
    
    console.error(`[Fast Mode] Searching: "${query}"\n`);
    
    // Get query embedding
    const queryEmbedding = await getEmbedding(query);
    
    // Perform hybrid search
    const results = hybridSearch(db, query, queryEmbedding, { maxResults });
    
    // Format output
    const output = {
        query,
        mode: 'fast',
        results: results.map(r => ({
            path: r.path,
            from: r.startLine,
            lines: r.endLine - r.startLine + 1,
            score: Math.round(r.hybridScore * 100) / 100,
            snippet: r.content.slice(0, 500) + (r.content.length > 500 ? '...' : ''),
        })),
    };
    
    console.log(JSON.stringify(output, null, 2));
    
    db.close();
}

/**
 * Search memory (focus mode - curated retrieval)
 */
async function performSearchFocus(query, maxResults = 5) {
    const result = await focusSearch(query, { selectionCount: maxResults });
    
    // Wrap in consistent output format
    const output = {
        query,
        mode: 'focus',
        confidence: result.confidence,
        sources: result.sources,
        synthesis: result.synthesis,
        facts: result.facts,
    };
    
    console.log(JSON.stringify(output, null, 2));
}

/**
 * Search memory (auto-detect mode based on current setting)
 */
async function performSearch(query, maxResults = 5, forceMode = null) {
    const mode = forceMode || getSearchMode();
    
    if (mode === 'focus') {
        await performSearchFocus(query, maxResults);
    } else {
        await performSearchFast(query, maxResults);
    }
}

/**
 * Get status
 */
function showStatus() {
    const db = initDatabase(DB_PATH);
    const stats = getStats(db);
    const mode = getSearchMode();
    
    const output = {
        status: 'ok',
        database: DB_PATH,
        model: stats.modelName || 'Xenova/all-MiniLM-L6-v2',
        embeddingDimension: getEmbeddingDimension(),
        sqliteVec: stats.sqliteVecAvailable,
        chunks: stats.chunkCount,
        lastSync: stats.lastSync,
        searchMode: mode,
    };
    
    console.log(JSON.stringify(output, null, 2));
    
    db.close();
}

/**
 * Main CLI handler
 */
async function main() {
    const args = process.argv.slice(2);
    const command = args[0];
    
    switch (command) {
        case '--sync':
            await syncAll();
            break;
            
        case '--search': {
            const query = args[1];
            if (!query) {
                console.error('Usage: --search "query" [--max-results N] [--focus]');
                process.exit(1);
            }
            
            const maxResultsIdx = args.indexOf('--max-results');
            const maxResults = maxResultsIdx >= 0 
                ? parseInt(args[maxResultsIdx + 1]) || 5
                : 5;
            
            const forceFocus = args.includes('--focus');
            const forceFast = args.includes('--fast');
            
            let forceMode = null;
            if (forceFocus) forceMode = 'focus';
            if (forceFast) forceMode = 'fast';
            
            await performSearch(query, maxResults, forceMode);
            break;
        }
            
        case '--status':
            showStatus();
            break;
            
        case '--focus': {
            const result = enableFocus();
            console.error('[Focus Mode] Enabled');
            console.log(JSON.stringify(result, null, 2));
            break;
        }
            
        case '--unfocus':
        case '--fast': {
            const result = disableFocus();
            console.error('[Focus Mode] Disabled');
            console.log(JSON.stringify(result, null, 2));
            break;
        }
            
        case '--mode': {
            const result = getModeStatus();
            console.log(JSON.stringify(result, null, 2));
            break;
        }
            
        default:
            console.log(`
Smart Memory v2.0 - Hybrid Search with SQLite + Focus Agent

Usage:
  node smart_memory.js --sync
    Index all memory files (MEMORY.md + memory/*.md)

  node smart_memory.js --search "query" [--max-results N] [--focus|--fast]
    Search memory using current mode (or override with --focus/--fast)

  node smart_memory.js --status
    Show database statistics and current mode

  node smart_memory.js --focus
    Enable Focus Mode (curated retrieval)

  node smart_memory.js --unfocus (or --fast)
    Disable Focus Mode (standard retrieval)

  node smart_memory.js --mode
    Show current search mode status

Modes:
  fast (default)
    Direct vector similarity search
    Quick, efficient for simple lookups
    
  focus
    Multi-pass curation via Focus Agent:
      1. Retrieve 20+ chunks
      2. Rank by weighted relevance
      3. Synthesize into coherent narrative
    Higher quality for complex decisions

Environment:
  MEMORY_DIR      - Path to memory directory (default: ./memory)
  MEMORY_FILE     - Path to MEMORY.md (default: ./MEMORY.md)
  MEMORY_DB_PATH  - Path to SQLite database (default: ./vector-memory.db)
`);
    }
}

main().catch(err => {
    console.error('Error:', err.message);
    if (err.message.includes('better-sqlite3')) {
        console.error('\nSQLite is required. Install with:');
        console.error('  Ubuntu/Debian: sudo apt-get install sqlite3 libsqlite3-dev');
        console.error('  macOS: brew install sqlite3');
    }
    process.exit(1);
});

#!/usr/bin/env python3
"""One-off importer: ingest OpenClaw workspace markdown memories into Smart Memory v2.

- Reads MEMORY.md and memory/*.md
- Chunks by headings/blank lines to avoid giant payloads
- Sends to POST /ingest on localhost:8000

Safe to re-run: ingestion pipeline performs semantic dedup.
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests


def chunk_markdown(text: str, *, max_chars: int = 1800) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    # Split on blank lines and headings; keep delimiters implicit.
    parts = re.split(r"\n\s*\n|(?=\n#{1,6} )", text)
    parts = [p.strip() for p in parts if p and p.strip()]

    chunks: list[str] = []
    buf: list[str] = []
    size = 0

    def flush():
        nonlocal buf, size
        if not buf:
            return
        chunk = "\n\n".join(buf).strip()
        if chunk:
            chunks.append(chunk)
        buf = []
        size = 0

    for p in parts:
        if len(p) > max_chars:
            # Hard-wrap huge blocks.
            for i in range(0, len(p), max_chars):
                sub = p[i : i + max_chars].strip()
                if sub:
                    chunks.append(sub)
            continue

        if size + len(p) + 2 > max_chars and buf:
            flush()
        buf.append(p)
        size += len(p) + 2

    flush()

    # Filter tiny chunks (heuristics require min words).
    out = []
    for c in chunks:
        if len(c.split()) >= 8:
            out.append(c)
    return out


def ingest_chunk(
    session: requests.Session,
    url: str,
    *,
    content: str,
    timestamp: datetime | None,
    source_file: str,
    chunk_index: int,
    total_chunks: int,
) -> dict:
    payload = {
        "user_message": content,
        "assistant_message": "",
        "timestamp": timestamp.isoformat() if timestamp else None,
        "source": "openclaw_workspace",
        "participants": ["user", "assistant"],
        "metadata": {
            "source_file": source_file,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "importer": "ingest_workspace_memories.py",
        },
    }
    r = session.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument(
        "--workspace",
        default=str(Path.home() / ".openclaw" / "workspace"),
        help="Path to OpenClaw workspace (default: ~/.openclaw/workspace)",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base = Path(os.path.expanduser(args.workspace)).resolve()
    files: list[Path] = []
    if (base / "MEMORY.md").exists():
        files.append(base / "MEMORY.md")
    mem_dir = base / "memory"
    if mem_dir.exists():
        files.extend(sorted(p for p in mem_dir.glob("*.md") if p.is_file()))

    if not files:
        print("No memory markdown files found.")
        return 1

    ingest_url = args.base_url.rstrip("/") + "/ingest"

    session = requests.Session()

    total_stored = 0
    total_seen = 0

    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        chunks = chunk_markdown(text)
        ts = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)

        print(f"\n==> {f.relative_to(base)} ({len(chunks)} chunks)")

        for i, c in enumerate(chunks, start=1):
            total_seen += 1
            if args.dry_run:
                print(f"  [dry] chunk {i}/{len(chunks)}: {len(c)} chars")
                continue

            try:
                res = ingest_chunk(
                    session,
                    ingest_url,
                    content=c,
                    timestamp=ts,
                    source_file=str(f.relative_to(base)),
                    chunk_index=i,
                    total_chunks=len(chunks),
                )
            except Exception as e:  # noqa: BLE001
                print(f"  [ERR] chunk {i}/{len(chunks)}: {e}")
                continue

            stored = bool(res.get("stored"))
            if stored:
                total_stored += 1
            reason = res.get("reason", "")
            print(f"  [{'OK' if stored else '--'}] chunk {i}/{len(chunks)}: {reason}")

    print(f"\nDone. Stored {total_stored}/{total_seen} chunks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

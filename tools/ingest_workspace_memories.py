#!/usr/bin/env python3
"""One-off importer: ingest OpenClaw workspace markdown memories into Smart Memory v3.1.

- Reads MEMORY.md and memory/*.md
- Chunks by headings/blank lines to avoid giant payloads
- Sends to POST /ingest on localhost:8000

Safe to re-run: transcript-first ingestion still performs semantic dedup and revision-aware writes.
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
        "assistant_message": "Imported from workspace markdown.",
        "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
        "source": "imported",
        "metadata": {
            "imported_from": source_file,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
        },
    }
    response = session.post(f"{url.rstrip('/')}/ingest", json=payload, timeout=20)
    response.raise_for_status()
    return response.json()


def iter_markdown_files(workspace: Path) -> list[Path]:
    paths: list[Path] = []
    memory_md = workspace / "MEMORY.md"
    if memory_md.exists():
        paths.append(memory_md)

    memory_dir = workspace / "memory"
    if memory_dir.exists():
        paths.extend(sorted(memory_dir.rglob("*.md")))

    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Import markdown memory files into Smart Memory")
    parser.add_argument("--workspace", default=os.getcwd(), help="Workspace root")
    parser.add_argument("--server", default="http://127.0.0.1:8000", help="Smart Memory server URL")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    files = iter_markdown_files(workspace)
    if not files:
        print("No markdown memory files found.")
        return 0

    imported = 0
    with requests.Session() as session:
        for path in files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            chunks = chunk_markdown(text)
            for index, chunk in enumerate(chunks, start=1):
                ingest_chunk(
                    session,
                    args.server,
                    content=chunk,
                    timestamp=datetime.now(timezone.utc),
                    source_file=str(path.relative_to(workspace)),
                    chunk_index=index,
                    total_chunks=len(chunks),
                )
                imported += 1
                print(f"Imported {path.name} chunk {index}/{len(chunks)}")

    print(f"Imported {imported} chunks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

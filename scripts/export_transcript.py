#!/usr/bin/env python3
"""export_transcript.py — export the current agent session to a readable
Markdown transcript under doc/transcripts/, so conversations are logged in
the repository (transcript-as-artifact; link activities to it via
`provlog.py log --transcript doc/transcripts/<file>.md`).

Locates the newest session JSONL for this working directory in
~/.claude/projects/ unless --session-file is given. Embedded images and
oversized tool payloads are omitted, not embedded — the transcript records
the conversation, the artefacts live in the repository.

Usage: python3 scripts/export_transcript.py [--session-file F] [-o DIR]
                                            [--quiet]
AI note: drafted with AI assistance and verified by test-run.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import sys

TRUNC_IN = 400     # chars of tool input to keep
TRUNC_OUT = 700    # chars of tool output to keep


def find_session_file() -> pathlib.Path | None:
    slug = str(pathlib.Path.cwd()).replace("/", "-")
    base = pathlib.Path.home() / ".claude" / "projects" / slug
    if not base.is_dir():
        return None
    cands = sorted(base.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    return cands[-1] if cands else None


def clip(text: str, n: int) -> str:
    text = text.strip()
    return text if len(text) <= n else text[:n] + f" … [{len(text) - n} chars omitted]"


def render_content(content, lines: list[str]) -> None:
    if isinstance(content, str):
        if content.strip():
            lines.append(content.strip())
        return
    for item in content or []:
        t = item.get("type")
        if t == "text" and item.get("text", "").strip():
            lines.append(item["text"].strip())
        elif t == "image":
            lines.append("*[image omitted]*")
        elif t == "tool_use":
            inp = json.dumps(item.get("input", {}), ensure_ascii=False)
            lines.append(f"> **tool: {item.get('name', '?')}** `{clip(inp, TRUNC_IN)}`")
        elif t == "tool_result":
            sub: list[str] = []
            render_content(item.get("content"), sub)
            body = clip("\n".join(sub), TRUNC_OUT)
            if body:
                lines.append("> result:\n> " + body.replace("\n", "\n> "))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session-file", type=pathlib.Path)
    ap.add_argument("-o", "--out-dir", default="doc/transcripts")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    src = a.session_file or find_session_file()
    if not src or not src.exists():
        sys.exit(0 if a.quiet else "no session transcript found for this directory")

    turns: list[str] = []
    session_id = src.stem
    for raw in src.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            continue
        kind = d.get("type")
        msg = d.get("message") or {}
        stamp = (d.get("timestamp") or "")[:19].replace("T", " ")
        if kind == "user" and msg:
            lines: list[str] = []
            render_content(msg.get("content"), lines)
            if lines:
                turns.append(f"## Human — {stamp}\n\n" + "\n\n".join(lines))
        elif kind == "assistant" and msg:
            lines = []
            render_content(msg.get("content"), lines)
            if lines:
                turns.append(f"## Assistant — {stamp}\n\n" + "\n\n".join(lines))

    out_dir = pathlib.Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{session_id}.md"
    out.write_text(
        f"# Session transcript `{session_id}`\n\n"
        f"Auto-exported by export_transcript.py from the agent session "
        f"record; embedded images and oversized tool payloads omitted. "
        f"This file is regenerated on every turn — the latest committed "
        f"version is the transcript of record.\n\n"
        + "\n\n---\n\n".join(turns) + "\n",
        encoding="utf-8")
    if not a.quiet:
        print(f"{out}: {len(turns)} turns, {out.stat().st_size // 1024} KiB")


if __name__ == "__main__":
    main()

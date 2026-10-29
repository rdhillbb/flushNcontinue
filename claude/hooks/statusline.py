#!/usr/bin/env python3
"""statusline.py — Claude Code status line that tells you when to checkpoint and flush.

Claude cannot see its own context use; this line is how the person at the keyboard knows.
  under 50%  ctx 34%  ok
  50-61%     ctx 55%  /checkpoint after each decision
  62-69%     ctx 64%  FLUSH NOW: /flush, then start a new session
  70%+       ctx 71%  OVER LIMIT: /flush immediately, then new session
Reads the JSON Claude Code sends on stdin. Stdlib only; works on macOS, Linux and
Windows (Git Bash or PowerShell). Never fails loudly: on any error it prints a short line.
"""
import json
import os
import subprocess
import sys

CHECKPOINT_AT, FLUSH_AT, LIMIT_AT = 50, 62, 70
GREEN, YELLOW, RED, BOLD, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[0m"


def percent(data):
    cw = data.get("context_window") or {}
    pct = cw.get("used_percentage")
    if pct is not None:
        return int(float(pct))
    usage, size = cw.get("current_usage"), cw.get("context_window_size")
    if not usage or not size:
        return None
    used = sum(int(usage.get(k) or 0) for k in
               ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    return used * 100 // int(size)


def branch(cwd):
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
                             capture_output=True, text=True, timeout=2)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def advice(pct):
    if pct is None:
        return "", "ctx --"
    if pct >= LIMIT_AT:
        return RED + BOLD, f"ctx {pct}%  OVER LIMIT: /flush immediately, then new session"
    if pct >= FLUSH_AT:
        return RED + BOLD, f"ctx {pct}%  FLUSH NOW: /flush, then start a new session"
    if pct >= CHECKPOINT_AT:
        return YELLOW, f"ctx {pct}%  /checkpoint after each decision"
    return GREEN, f"ctx {pct}%  ok"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        data = {}
    model = (data.get("model") or {}).get("display_name") or "Claude"
    ws = data.get("workspace") or {}
    cwd = ws.get("current_dir") or data.get("cwd") or os.getcwd()
    project = os.path.basename((ws.get("project_dir") or cwd).rstrip("/\\")) or cwd
    try:
        pct = percent(data)
    except Exception:
        pct = None
    color, text = advice(pct)
    bits = [model, project]
    b = branch(cwd)
    if b:
        bits.append(b)
    print(" | ".join(bits) + " | " + (color + text + RESET if color else text))


if __name__ == "__main__":
    main()

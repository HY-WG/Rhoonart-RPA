#!/usr/bin/env python3
"""PreToolUse hook: blocks Edit/Write on sensitive files."""
import sys, json, re

BLOCKED = re.compile(
    r"^[.]env$|^[.]env[.]",
    re.IGNORECASE,
)
BLOCKED_EXT = re.compile(r"[.](key|pem)$", re.IGNORECASE)
BLOCKED_PREFIX = re.compile(r"^secrets[.]", re.IGNORECASE)

try:
    data = json.load(sys.stdin)
    fp = data.get("tool_input", {}).get("file_path", "")
except Exception:
    sys.exit(0)

name = fp.replace("\\", "/").split("/")[-1]

if BLOCKED.match(name) or BLOCKED_EXT.search(name) or BLOCKED_PREFIX.match(name):
    print(f"Blocked: {repr(fp)} is a protected sensitive file.")
    sys.exit(2)

sys.exit(0)

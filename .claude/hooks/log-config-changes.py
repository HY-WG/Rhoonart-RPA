#!/usr/bin/env python3
"""
ConfigChange hook: logs when Claude Code settings files are modified.
Appends entries to ~/.claude/config-changes.log.
"""
import sys
import json
import os
from datetime import datetime

try:
    data = json.load(sys.stdin)
    file_path = data.get('file_path', 'unknown').replace('\n', ' ').replace('\r', ' ')
except Exception:
    file_path = 'unknown'

log_path = os.path.expanduser('~/.claude/config-changes.log')
timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

try:
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f'[{timestamp}] Config changed: {file_path}\n')
except Exception:
    pass  # best-effort logging

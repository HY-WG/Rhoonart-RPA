# Claude Code Hooks Configuration

## Overview

This directory contains Claude Code hook scripts that enforce project-level
automation and security policies. Hooks run deterministically at specific
lifecycle events — unlike CLAUDE.md instructions, they cannot be skipped.

---

## Hooks Summary

| Event | Matcher | Script | Purpose |
|---|---|---|---|
| `PreToolUse` | `Edit\|Write` | `hooks/protect-sensitive-files.py` | Block writes to sensitive files |
| `ConfigChange` | *(all)* | `hooks/log-config-changes.py` | Audit log for settings changes |

---

## Hook Details

### 1. Sensitive File Protection (`PreToolUse`)

**Trigger:** Before every `Edit` or `Write` tool call
**Action:** Exits with code `2` (block) if the target file matches a protected pattern.

#### Protected Patterns

| Pattern | Matches |
|---|---|
| `.env`, `.env.*` | `.env`, `.env.local`, `.env.production` |
| `secrets.*` | `secrets.json`, `secrets.yaml`, `secrets.toml` |
| `*.key` | `server.key`, `api.key`, `private.key` |
| `*.pem` | `server.pem`, `cert.pem`, `ca.pem` |

#### Extending Protection

Edit `BLOCKED`, `BLOCKED_EXT`, or `BLOCKED_PREFIX` in
`hooks/protect-sensitive-files.py` to add more patterns.

---

### 2. Config Change Audit Log (`ConfigChange`)

**Trigger:** Whenever any Claude Code settings file is modified
**Action:** Appends a timestamped entry to `~/.claude/config-changes.log`
(runs `async: true` — never blocks Claude)

#### Log Format

```
[2026-04-14 11:06:27] Config changed: /path/to/settings.json
```

```bash
# Read the log
cat ~/.claude/config-changes.log
```

---

## When to Use Hooks (Decision Guide)

| Need | Right tool |
|---|---|
| Block writes to `.env` every time | Hook (`PreToolUse`) |
| Auto-format after file edits | Hook (`PostToolUse`) |
| Instructions Claude should follow | `CLAUDE.md` |
| One-time action | Ask Claude directly |
| Style/tone preferences | Memory |

### Key Hook Events

| Event | Fires when | Can block? |
|---|---|---|
| `PreToolUse` | Before a tool runs | Yes (exit 2) |
| `PostToolUse` | After tool completes | No |
| `ConfigChange` | Settings files change | No |
| `Stop` | Claude finishes responding | No |
| `SessionStart` | Session begins / context compacts | No |

---

## Session Notes: Why These Hooks Were Set Up

This configuration was created based on the following requests in session
2026-04-14:

1. **Hook use-case guidance** — Explored when `PreToolUse` vs `ConfigChange`
   hooks are appropriate for restricting file changes.

2. **Cost efficiency analysis** — Compared custom Claude API website vs.
   Claude.ai native integrations for email automation:
   - **Low volume / personal** → Claude.ai connect (flat subscription, zero infra)
   - **High volume / business** → Claude API (cheaper per-task at scale)
   - **Middle ground** → MCP server in Claude Code (API control, no full website)

3. **Hook implementation** — Created `PreToolUse` hook blocking edits to
   sensitive files (`.env`, `secrets.*`, `*.key`, `*.pem`) and `ConfigChange`
   hook for audit logging of settings modifications.

---

## File Structure

```
.claude/
├── hooks/
│   ├── protect-sensitive-files.py   # PreToolUse: blocks sensitive file edits
│   ├── log-config-changes.py        # ConfigChange: audit log
│   └── settings.json                # Hook configuration
└── HOOKS.md                         # This file
```

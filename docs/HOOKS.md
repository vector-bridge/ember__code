# Hooks

Hooks are shell commands or HTTP calls that execute in response to agent lifecycle events. They let you automate workflows around tool execution — auto-format after every file write, run linters before commits, enforce security policies, log tool usage, or inject context at session start.

Ember Code's hook system is **compatible with Claude Code's** hook format. If you already have Claude Code hooks, they work in Ember Code out of the box.

## Overview

```
Agent calls Edit tool
    │
    ▼
┌──────────────────────┐
│  PreToolUse hooks    │ ← can block, modify input, or add context
│  (run in parallel)   │
└──────────┬───────────┘
           │ approved
           ▼
┌──────────────────────┐
│  Tool executes       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  PostToolUse hooks   │ ← can log, format, validate output
│  (run in parallel)   │
└──────────────────────┘
```

---

## Hook Events

| Event | When It Fires | Can Block? | Use Case |
|---|---|---|---|
| `PreToolUse` | Before any tool call | Yes | Security validation, input modification, permission overrides |
| `PostToolUse` | After tool succeeds | No | Auto-formatting, logging, validation |
| `PostToolUseFailure` | After tool fails | No | Error logging, retry context |
| `UserPromptSubmit` | When user sends a message | Yes | Prompt validation, context injection |
| `SessionStart` | When session begins or resumes | No | Environment setup, context loading |
| `SessionEnd` | When session terminates | No | Cleanup, reporting |
| `Stop` | When agent wants to finish | Yes | Completion validation (did tests run?) |
| `SubagentStart` | When a sub-team spawns | No | Logging, resource tracking |
| `SubagentStop` | When a sub-team finishes | No | Result validation |
| `Notification` | System notifications | No | Custom notification handlers |

---

## Configuration

Hooks are defined in settings files, with the same format as Claude Code:

### File Locations

| Location | Scope | Shared? |
|---|---|---|
| `~/.ember/settings.json` | All projects | No (personal) |
| `.ember/settings.json` | This project | Yes (commit to repo) |
| `.ember/settings.local.json` | This project | No (gitignored) |

### Format

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "type": "command",
        "command": ".ember/hooks/validate.sh",
        "matcher": "Bash|Write|Edit",
        "timeout": 10000
      }
    ],
    "PostToolUse": [
      {
        "type": "command",
        "command": ".ember/hooks/format.sh",
        "matcher": "Write|Edit"
      }
    ],
    "SessionStart": [
      {
        "type": "command",
        "command": ".ember/hooks/setup-env.sh"
      }
    ],
    "Stop": [
      {
        "type": "command",
        "command": ".ember/hooks/check-tests.sh"
      }
    ]
  }
}
```

### Hook Types

**Command hooks** — run a shell script:
```json
{
  "type": "command",
  "command": ".ember/hooks/format.sh",
  "matcher": "Write|Edit",
  "timeout": 10000
}
```

**HTTP hooks** — POST to a URL:
```json
{
  "type": "http",
  "url": "https://hooks.internal.corp.com/validate",
  "headers": {
    "Authorization": "Bearer ${HOOK_API_KEY}"
  },
  "matcher": "Bash",
  "timeout": 5000
}
```

---

## Matchers

Matchers are regex patterns that filter when a hook fires. Only hooks whose matcher matches the tool name (or event type) will execute.

| Event | Matcher Field | Examples |
|---|---|---|
| `PreToolUse` / `PostToolUse` | Tool name | `Bash`, `Write\|Edit`, `mcp__.*` |
| `SessionStart` | Start mode | `startup`, `resume` |
| `SubagentStart` / `SubagentStop` | Agent name | `explorer`, `editor` |
| `Notification` | Notification type | `permission_prompt` |

**Examples:**
```json
"matcher": "Bash"           // only Bash tool calls
"matcher": "Write|Edit"     // Write or Edit
"matcher": "mcp__.*"        // any MCP tool
"matcher": ""               // all (or omit matcher)
```

---

## Input & Output Format

### Input (JSON on stdin)

Every hook receives a JSON object on stdin with common fields plus event-specific data:

**Common fields (all events):**
```json
{
  "session_id": "abc-123",
  "cwd": "/path/to/project",
  "hook_event_name": "PreToolUse"
}
```

**PreToolUse / PostToolUse:**
```json
{
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "/path/to/file.py",
    "old_string": "def foo():",
    "new_string": "def bar():"
  },
  "tool_result": "..."       // PostToolUse only
}
```

**UserPromptSubmit:**
```json
{
  "user_prompt": "Add tests for the auth module"
}
```

**Stop:**
```json
{
  "reason": "task_complete"
}
```

### Output (JSON on stdout)

```json
{
  "continue": true,
  "systemMessage": "Optional message shown to the agent"
}
```

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success — continue execution, parse stdout for JSON |
| `2` | Block — prevent the tool call (PreToolUse) or reject stop (Stop) |
| Other | Non-blocking error — log and continue |

---

## Examples

### 1. Auto-Format After File Writes

Run Prettier/Black/Ruff after every file write:

```bash
#!/bin/bash
# .ember/hooks/format.sh
# Hook: PostToolUse, matcher: Write|Edit

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

if [[ -z "$file_path" ]]; then
  exit 0
fi

case "$file_path" in
  *.py)
    ruff format "$file_path" 2>/dev/null
    ;;
  *.js|*.ts|*.jsx|*.tsx)
    npx prettier --write "$file_path" 2>/dev/null
    ;;
  *.go)
    gofmt -w "$file_path" 2>/dev/null
    ;;
esac

echo '{"continue": true}'
```

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "type": "command",
        "command": ".ember/hooks/format.sh",
        "matcher": "Write|Edit"
      }
    ]
  }
}
```

### 2. Block Dangerous Shell Commands

Prevent destructive operations:

```bash
#!/bin/bash
# .ember/hooks/validate-bash.sh
# Hook: PreToolUse, matcher: Bash

input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command // empty')

# Block dangerous patterns
if echo "$command" | grep -qE '(rm -rf /|:()\{|DROP TABLE|TRUNCATE|--force)'; then
  echo '{"continue": false, "systemMessage": "Blocked: destructive command detected"}' >&2
  exit 2
fi

echo '{"continue": true}'
```

### 3. Ensure Tests Run Before Completion

Don't let the agent stop without running tests:

```bash
#!/bin/bash
# .ember/hooks/check-tests.sh
# Hook: Stop

input=$(cat)
transcript=$(echo "$input" | jq -r '.transcript_path // empty')

# Check if any test command was run in this session
if [[ -n "$transcript" ]] && ! grep -q '"pytest\|npm test\|cargo test"' "$transcript"; then
  cat << 'EOF'
{"continue": false, "systemMessage": "Please run the test suite before finishing. Use pytest, npm test, or the project's test command."}
EOF
  exit 2
fi

echo '{"continue": true}'
```

### 4. Load Environment on Session Start

Set up project-specific environment:

```bash
#!/bin/bash
# .ember/hooks/setup-env.sh
# Hook: SessionStart

# Detect project type and set context
if [[ -f "pyproject.toml" ]]; then
  project_type="python"
elif [[ -f "package.json" ]]; then
  project_type="node"
elif [[ -f "Cargo.toml" ]]; then
  project_type="rust"
fi

cat << EOF
{
  "continue": true,
  "systemMessage": "Project type detected: ${project_type}. Environment configured."
}
EOF
```

### 5. Security: Block Writes to Sensitive Paths

```bash
#!/bin/bash
# .ember/hooks/protect-paths.sh
# Hook: PreToolUse, matcher: Write|Edit

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

# Block writes to sensitive files
if echo "$file_path" | grep -qE '(\.env|\.pem|\.key|credentials|secrets|\.ssh)'; then
  cat << EOF
{"continue": false, "systemMessage": "Blocked: ${file_path} is a protected path. Cannot write to sensitive files."}
EOF
  exit 2
fi

echo '{"continue": true}'
```

### 6. HTTP Hook: Send Tool Usage to Monitoring

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "type": "http",
        "url": "https://monitoring.internal.corp.com/ember-code/tool-usage",
        "headers": {
          "Authorization": "Bearer ${MONITORING_API_KEY}"
        },
        "matcher": ""
      }
    ]
  }
}
```

---

## Hook Execution Model

- All matching hooks for an event run **in parallel**
- Hooks don't see each other's output — design them to be independent
- For `PreToolUse`: if **any** hook exits with code 2, the tool call is blocked
- Hooks load at **session startup only** — changes require restarting the session
- Default timeout: 10 seconds for commands, 5 seconds for HTTP

---

## Directory Structure

```
.ember/
├── settings.json              # Hook definitions
├── hooks/
│   ├── format.sh              # Auto-format after writes
│   ├── validate-bash.sh       # Block dangerous commands
│   ├── protect-paths.sh       # Protect sensitive files
│   ├── check-tests.sh         # Ensure tests run
│   └── setup-env.sh           # Session environment setup
```

---

## Claude Code Compatibility

Ember Code hooks use the **same format** as Claude Code:
- Same event names (`PreToolUse`, `PostToolUse`, `Stop`, etc.)
- Same input/output JSON format
- Same exit code semantics (0 = success, 2 = block)
- Same matcher regex patterns
- Same settings file structure

If you have existing Claude Code hooks in `.claude/settings.json`, copy them to `.ember/settings.json` — they work as-is.

The one addition: Ember Code hooks also fire for **sub-team events** (`SubagentStart`, `SubagentStop`) since Ember Code has multi-agent teams. Claude Code has similar events for its subagents.

---

## Slash Commands

```
/hooks                    — list all loaded hooks
/hooks reload             — reload hooks from settings files
```

---

## Best Practices

1. **Keep hooks fast.** They run on every tool call. A 2-second hook on PostToolUse means 2 extra seconds per edit. Target <500ms.

2. **Use matchers.** Don't run a formatting hook on Grep calls. Match only `Write|Edit`.

3. **Exit 0 by default.** Only exit 2 when you need to block. Unhandled errors should not block the agent.

4. **Validate input.** Check that expected JSON fields exist before using them. `jq -r '.tool_input.file_path // empty'` handles missing fields gracefully.

5. **Don't mutate files in PreToolUse.** PreToolUse runs before the tool — if you modify the file there, the subsequent Edit tool may fail due to content mismatch.

6. **Log to files, not stdout.** Stdout is parsed as JSON response. Use stderr or log files for debugging.

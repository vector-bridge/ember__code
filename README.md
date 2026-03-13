# Ember Code

**One spark ignites a team.** An AI coding assistant built with [Agno](https://github.com/agno-agi/agno) orchestration.

```
 ◆ ignite-ember — ignite-ember.sh
```

Inspired by [Claude Code](https://github.com/anthropics/claude-code), Ember Code is a terminal-based coding agent that assembles specialized AI teams on the fly. Describe your task — the Orchestrator picks the right agents, the right team mode, and runs them.

## Why Ember Code?

Claude Code uses a single agent loop — powerful but monolithic. Ember Code takes a different approach: **dynamic multi-agent orchestration**. Instead of one agent doing everything, Agno's team system decomposes tasks, routes them to specialized agents, and synthesizes results — all automatically.

| Feature | Claude Code | Ember Code |
|---|---|---|
| Architecture | Single agent loop | Multi-agent teams (Agno) |
| Task routing | Manual sub-agent spawning | Automatic via Coordinate/Route modes |
| Code intelligence | Grep + file reads | VectorBridge semantic search (included free) |
| Planning | Plan mode (read-only) | Agno reasoning + Tasks mode |
| IDE integration | MCP server (stdio) | MCP server + client (Agno MCPTools) |
| Extensibility | Plugins, hooks, MCP | Agents + hooks + toolkits + MCP |
| Agent evals | Not built-in | Built-in regression testing framework |
| Memory | File-based MEMORY.md | Agno Memory + DB-backed storage |
| Default model | Anthropic Claude | MiniMax M2.5 (model-agnostic, swappable) |

## Quick Start

```bash
brew install ignite-ember
# or: pip install ignite-ember
ignite-ember login       # sign up / log in for hosted models
ignite-ember
```

Or bring your own model:

```bash
brew install ignite-ember
# or: pip install ignite-ember
export MINIMAX_API_KEY=your_key   # or OPENAI_API_KEY, etc.
ignite-ember
```

From source:

```bash
git clone https://github.com/ignite-ember/ember-code.git
cd ember-code
pip install -e ".[dev]"
ignite-ember login
ignite-ember
```

## IDE Integration

Ember Code integrates with IDEs via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/):

```json
{
  "mcpServers": {
    "ignite-ember": {
      "type": "stdio",
      "command": "ignite-ember",
      "args": ["mcp", "serve"]
    }
  }
}
```

Works with **VS Code**, **JetBrains** (IntelliJ, PyCharm, etc.), **Cursor**, and **Windsurf**. See [MCP docs](docs/MCP.md) for details.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — System design and agent topology
- [Agents](docs/AGENTS.md) — Specialized agents and their roles
- [Skills](docs/SKILLS.md) — Reusable prompted workflows (`/deploy`, `/review-pr`, etc.)
- [Onboarding](docs/ONBOARDING.md) — First-run setup, VectorBridge, and agent proposals
- [Tools](docs/TOOLS.md) — Available toolkits and capabilities
- [MCP](docs/MCP.md) — IDE integration via Model Context Protocol
- [Configuration](docs/CONFIGURATION.md) — Settings, permissions, and customization
- [VectorBridge](docs/VECTORBRIDGE.md) — Semantic code intelligence engine
- [Evals](docs/EVALS.md) — Agent evaluation framework and regression testing
- [Hooks](docs/HOOKS.md) — Pre/post tool execution hooks
- [Migration](docs/MIGRATION.md) — Coming from Claude Code or Codex
- [Security](docs/SECURITY.md) — Threat model, sandboxing, and enterprise hardening
- [Development](docs/DEVELOPMENT.md) — Contributing and extending Ember Code

## License

MIT

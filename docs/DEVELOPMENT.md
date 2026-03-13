# Development

Guide for contributing to Ember Code and understanding the codebase.

## Project Structure

```
ember-code/
├── docs/                          # Documentation (you are here)
│   ├── ARCHITECTURE.md
│   ├── AGENTS.md
│   ├── SKILLS.md
│   ├── ONBOARDING.md
│   ├── TOOLS.md
│   ├── MCP.md
│   ├── CONFIGURATION.md
│   ├── VECTORBRIDGE.md
│   ├── EVALS.md
│   ├── HOOKS.md
│   ├── MIGRATION.md
│   ├── SECURITY.md
│   └── DEVELOPMENT.md
├── agents/                            # Built-in agent definitions (.md)
│   ├── explorer.md
│   ├── planner.md
│   ├── editor.md
│   ├── reviewer.md
│   ├── git.md
│   └── conversational.md
├── skills/                            # Built-in skills (SKILL.md)
│   ├── commit/
│   │   └── SKILL.md
│   ├── review-pr/
│   │   ├── SKILL.md
│   │   └── templates/
│   ├── explain/
│   │   └── SKILL.md
│   └── simplify/
│       └── SKILL.md
├── src/
│   └── ember_code/
│       ├── __init__.py
│       ├── __main__.py            # CLI entry point
│       ├── cli.py                 # Terminal UI (Rich/Textual)
│       ├── session.py             # Session management
│       ├── orchestrator.py        # Orchestrator: task analysis + dynamic team assembly
│       ├── pool.py                # AgentPool: load, parse, manage .md agent definitions
│       ├── team_builder.py        # Build Agno Teams from Orchestrator's TeamPlan
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── edit.py            # EmberEditTools
│       │   ├── search.py          # GrepTools, GlobTools
│       │   ├── web.py             # WebTools
│       │   ├── vectorbridge.py    # VectorBridgeTools (semantic code intelligence)
│       │   ├── registry.py        # Tool identifier → Agno toolkit mapping
│       │   └── loader.py          # Custom tool discovery
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py        # Configuration loading & merging
│       │   ├── permissions.py     # Permission checks & prompts
│       │   └── defaults.py        # Default configuration values
│       ├── memory/
│       │   ├── __init__.py
│       │   └── manager.py         # Agno memory + storage setup
│       ├── mcp/
│       │   ├── __init__.py
│       │   ├── server.py          # MCP server (ignite-ember mcp serve)
│       │   ├── client.py          # MCP client (consume external servers)
│       │   ├── tools.py           # Tool definitions exposed via MCP
│       │   ├── config.py          # .mcp.json loading & env var expansion
│       │   └── transport.py       # Transport layer (stdio, http, sse)
│       ├── onboarding/
│       │   ├── __init__.py
│       │   ├── flow.py            # Main onboarding orchestration
│       │   ├── questionnaire.py   # User Q&A step
│       │   ├── proposer.py        # Agent proposal generation
│       │   ├── vectorbridge.py    # VectorBridge cloud client
│       │   ├── local_analyzer.py  # Fallback local project analysis
│       │   └── defaults.py        # Default agent file contents
│       ├── evals/
│       │   ├── __init__.py
│       │   ├── runner.py          # Loads YAML, translates to Agno evals, executes
│       │   ├── loader.py          # YAML eval file parser
│       │   ├── assertions.py      # Ember assertions (file, orchestrator, VB)
│       │   ├── fixtures.py        # Fixture setup and teardown
│       │   ├── scoring.py         # Score tracking, baselines, regression
│       │   └── reporter.py        # Output formatting (table, json, markdown)
│       ├── hooks/
│       │   ├── __init__.py
│       │   ├── loader.py          # Load hooks from settings files
│       │   ├── executor.py        # Hook execution (command, http)
│       │   └── events.py          # Hook event definitions & matching
│       ├── skills/
│       │   ├── __init__.py
│       │   ├── loader.py          # Discover SKILL.md from all directories
│       │   ├── parser.py          # Parse frontmatter + body + substitutions
│       │   └── executor.py        # Skill invocation (inline or forked)
│       ├── indexer/
│       │   ├── __init__.py
│       │   ├── pipeline.py        # Code analysis & summary generation pipeline
│       │   ├── categories.py      # Multi-category summary generators
│       │   ├── hierarchy.py       # Bottom-up hierarchical summary builder
│       │   └── client.py          # VectorBridge API client
│       └── utils/
│           ├── __init__.py
│           ├── context.py         # Project context loading (ember.md)
│           ├── display.py         # Terminal formatting helpers
│           └── audit.py           # Audit logging
├── tests/
│   ├── conftest.py
│   ├── test_orchestrator.py
│   ├── test_pool.py
│   ├── test_team_builder.py
│   ├── test_tools/
│   └── test_config/
├── pyproject.toml
├── ember.md                       # Project instructions for self-use
├── README.md
└── LICENSE
```

## Setup

```bash
# Clone
git clone https://github.com/ignite-ember/ember-code.git
cd ember-code

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Verify
ignite-ember --version
```

## Dependencies

**Core:**
- `agno` — Agent orchestration framework (includes `openai` as a transitive dependency via `agno[openai]` for OpenAI-compatible providers)
- `rich` — Terminal formatting and markdown rendering
- `textual` — Terminal UI framework (for interactive mode)
- `pyyaml` — Configuration file parsing
- `click` — CLI argument parsing
- `mcp` — Model Context Protocol SDK (server + client)

**Dev:**
- `pytest` — Testing
- `pytest-asyncio` — Async test support
- `ruff` — Linting and formatting
- `mypy` — Type checking
- `pre-commit` — Git hooks

## Key Implementation Details

### 1. Agent Pool (pool.py)

The AgentPool discovers, parses, and manages agent definitions from `.md` files:

```python
class AgentPool:
    """Loads agent definitions from .md files and builds Agno Agent objects."""

    def __init__(self, config: Settings):
        self.agents: dict[str, AgentEntry] = {}
        self._load_all(config)

    def _load_all(self, config: Settings):
        # Load in priority order (highest last, so they overwrite)
        dirs = [
            (Path(__file__).parent.parent / "agents", 0),     # built-in
            (Path.home() / ".ember-code" / "agents", 1),      # user global
            (Path(".ember/agents.local"), 2),             # project local
            (Path(".ember/agents"), 3),                   # project shared
        ]
        for path, priority in dirs:
            if path.is_dir():
                self._load_directory(path, priority)

    def _load_directory(self, path: Path, priority: int):
        for md_file in path.glob("*.md"):
            defn = parse_agent_md(md_file)  # YAML frontmatter + body
            name = defn.frontmatter["name"]
            if name not in self.agents or priority >= self.agents[name].priority:
                self.agents[name] = AgentEntry(
                    definition=defn,
                    priority=priority,
                    agent=build_agno_agent(defn),  # → agno.Agent instance
                )

    def describe(self) -> str:
        """Summary of all agents for the Orchestrator's context."""
        return "\n".join(
            f"- {a.name}: {a.description} [tools: {a.tools}] [tags: {a.tags}]"
            for a in self.agents.values()
        )

    def get(self, name: str) -> Agent:
        return self.agents[name].agent
```

### 2. Orchestrator (orchestrator.py)

The Orchestrator is the only hardcoded agent. It analyzes each task and outputs a `TeamPlan`:

```python
class Orchestrator:
    def __init__(self, pool: AgentPool, config: Settings):
        self.pool = pool
        self.meta_agent = Agent(
            model=get_model(config.models.default),
            reasoning=True,
            output_schema=TeamPlan,
            instructions=[self._build_system_prompt()],
        )

    async def plan(self, message: str, context: ConversationContext) -> TeamPlan:
        """Decide which agents and team mode to use."""
        return await self.meta_agent.arun(
            f"Agent pool:\n{self.pool.describe()}\n\n"
            f"Context:\n{context.summary()}\n\n"
            f"User message: {message}"
        )
```

The `TeamPlan` structured output:
```python
class TeamPlan(BaseModel):
    team_name: str
    team_mode: Literal["single", "route", "coordinate", "broadcast", "tasks"]
    agent_names: list[str]
    team_instructions: list[str]
    reasoning: str
```

### 3. Model Resolver (config/models.py)

Agent `.md` files specify models by name (`model: MiniMax-M2.5`). The model resolver maps that name to an Agno model instance using a config-driven registry.

```python
from agno.models.openai import OpenAILike

# Built-in registry — ships with Ember Code.
# All built-in models route through the Ember hosted endpoint.
BUILTIN_REGISTRY: dict[str, dict] = {
    "MiniMax-M2.5": {
        "provider": "openai_like",
        "model_id": "MiniMax-Text-01",
        "url": "https://api.ignite-ember.sh/v1",
        "api_key_env": "EMBER_API_KEY",
    },
    "MiniMax-M2.5-highspeed": {
        "provider": "openai_like",
        "model_id": "MiniMax-Text-01-highspeed",
        "url": "https://api.ignite-ember.sh/v1",
        "api_key_env": "EMBER_API_KEY",
    },
}

# Provider string → Agno model class
PROVIDERS = {
    "openai_like": OpenAILike,
}


def get_model(name: str, config: Settings) -> Model:
    """Resolve a model name from an agent .md file to an Agno model instance.

    Resolution order:
      1. User registry (config.models.registry) — overrides built-ins
      2. Built-in registry (BUILTIN_REGISTRY)
      3. provider:model_id syntax (e.g., "openai_like:gpt-4o")
    """
    # 1. Check user config registry
    entry = config.models.registry.get(name)

    # 2. Fall back to built-in registry
    if entry is None:
        entry = BUILTIN_REGISTRY.get(name)

    # 3. Try provider:model_id syntax
    if entry is None and ":" in name:
        provider, model_id = name.split(":", 1)
        entry = {"provider": provider, "model_id": model_id}

    if entry is None:
        raise ValueError(
            f"Unknown model '{name}'. Add it to models.registry in config "
            f"or use provider:model_id syntax (e.g., openai_like:gpt-4o)."
        )

    # Build the Agno model instance
    provider_cls = PROVIDERS[entry["provider"]]
    kwargs = {"id": entry["model_id"]}
    if "url" in entry:
        kwargs["base_url"] = entry["url"]
    if "api_key_env" in entry:
        kwargs["api_key"] = os.environ.get(entry["api_key_env"])
    elif "api_key_cmd" in entry:
        kwargs["api_key"] = subprocess.check_output(
            entry["api_key_cmd"], shell=True, text=True
        ).strip()

    return provider_cls(**kwargs)
```

The agent pool uses this when building agents from `.md` definitions:

```python
def build_agno_agent(defn: AgentDefinition, config: Settings) -> Agent:
    model_name = defn.frontmatter.get("model", config.models.default)
    return Agent(
        model=get_model(model_name, config),
        tools=resolve_tools(defn.tools),
        instructions=[defn.body],
        reasoning=defn.frontmatter.get("reasoning", False),
    )
```

### 4. Session Loop (session.py)

```python
async def run_session(orchestrator: Orchestrator, pool: AgentPool, config: Settings):
    context = ConversationContext(config)

    while True:
        user_input = await get_user_input()

        if user_input.startswith("/"):
            handle_command(user_input)
            continue

        # Orchestrator decides the team
        plan = await orchestrator.plan(user_input, context)

        # Build and execute
        if plan.team_mode == "single":
            response = await pool.get(plan.agent_names[0]).arun(user_input, stream=True)
        else:
            team = build_team(plan, pool)
            response = await team.arun(user_input, stream=True)

        display_response(response)
        context.append(user_input, response)
```

### 5. Permission System (config/permissions.py)

Wraps Agno tool execution with permission checks:

```python
class PermissionGuard:
    """Intercepts tool calls and checks against config permissions.

    Resolution order:
      1. Protected paths → always deny
      2. Allowlist (from "always allow similar" approvals) → allow
      3. Config permission level → allow / deny / ask
    """

    def __init__(self, config: Settings):
        self.config = config
        self.persistent = load_permissions("~/.ember/permissions.yaml")

    def check(self, tool_name: str, tool_input: dict) -> PermissionResult:
        # 1. Protected paths — always deny
        if self.is_protected_path(tool_input):
            return PermissionResult.DENY

        command = self.extract_command(tool_name, tool_input)

        # 2. Allowlist — patterns from "always allow similar" approvals
        if self.persistent.matches_allowlist(tool_name, command):
            return PermissionResult.ALLOW

        # 3. Config permission level
        level = self.config.permissions.get(tool_name, "ask")
        if level == "allow":
            return PermissionResult.ALLOW
        elif level == "deny":
            return PermissionResult.DENY
        else:
            return PermissionResult.ASK  # prompt: once / always / similar / deny

    def record_decision(self, decision: ApprovalDecision, tool_name: str, command: str):
        """Save an 'always allow' or 'allow similar' decision."""
        if decision == ApprovalDecision.ALWAYS:
            self.persistent.add_allowlist(tool_name, command)
        elif decision == ApprovalDecision.SIMILAR:
            pattern = self.generalize_pattern(command)  # "npm test" → "npm *"
            self.persistent.add_allowlist(tool_name, pattern)
```

### 6. EmberEditTools (tools/edit.py)

The targeted edit tool that makes Ember Code practical for real coding:

```python
@tool(description="Edit a file by replacing a specific string with new content")
def edit_file(file_path: str, old_string: str, new_string: str) -> str:
    content = Path(file_path).read_text()

    # Ensure old_string is unique (or fail with context)
    count = content.count(old_string)
    if count == 0:
        return f"Error: '{old_string}' not found in {file_path}"
    if count > 1:
        return f"Error: '{old_string}' found {count} times. Provide more context."

    new_content = content.replace(old_string, new_string, 1)
    Path(file_path).write_text(new_content)
    return f"Edited {file_path}: replaced 1 occurrence"
```

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_orchestrator.py

# Run with coverage
pytest --cov=ember_code

# Type checking
mypy src/

# Linting
ruff check src/ tests/
ruff format src/ tests/
```

### Test Strategy

- **Unit tests** — agent pool loading, .md parsing, tool registry, config merging
- **Integration tests** — Orchestrator decisions, team assembly, full session flow
- **Mock LLM calls** — use Agno's test utilities to mock model responses
- **Snapshot tests** — verify tool output format stability
- **Agent definition tests** — validate all built-in `.md` files parse correctly

## Slash Commands

Built-in commands available in interactive mode:

| Command | Description |
|---|---|
| `/help` | Show available commands |
| `/login` | Authenticate with Ember Code account (ignite-ember.sh) |
| `/logout` | Clear stored Ember Code credentials |
| `/clear` | Clear conversation history |
| `/compact` | Compress conversation context |
| `/config` | Show current configuration |
| `/context` | Show what's loaded in context |
| `/model <name>` | Switch model mid-session |
| `/agents` | List available agents |
| `/agents refresh` | Re-scan agent directories and reload pool |
| `/plan` | Enter planning mode (Planner agent only) |
| `/onboard` | Run the full onboarding flow |
| `/propose-agents` | Propose new agents based on current project |
| `/reset` | Remove `.ember/` and start fresh |
| `/mcp` | Show MCP server status |
| `/mcp add <name>` | Add a new MCP server |
| `/evals run` | Run agent evaluations |
| `/evals run --changed` | Run evals for modified agents only |
| `/evals baseline set` | Save current scores as baseline |
| `/skills` | List available skills |
| `/<skill-name> [args]` | Invoke a skill (e.g., `/deploy staging`) |
| `/quit` | Exit Ember Code |

## Architecture Decisions

### Why Agno over raw API calls?

- **Team orchestration** — dynamic task decomposition and routing
- **Memory management** — built-in persistent memory with DB backends
- **Tool ecosystem** — 100+ pre-built toolkits
- **Model agnostic** — swap models without code changes
- **Reasoning** — built-in chain-of-thought with `reasoning=True`

### Why dynamic team assembly instead of a fixed hierarchy?

A fixed Router → Agent hierarchy forces you to pre-decide what agents exist and how they interact. The dynamic approach lets:
- Users add agents without code changes (just drop a `.md` file)
- The Orchestrator adapt team composition to each specific task
- Different tasks use different team modes (coordinate for multi-step, broadcast for review, etc.)
- Project teams customize behavior by overriding built-in agent definitions

The one extra LLM call for orchestration is negligible for complex tasks and skipped entirely for simple ones (single-agent shortcut).

### Why agents as .md files?

- **Accessibility** — anyone can write markdown, no Python needed
- **Portability** — commit to repo, share across team
- **Overridability** — project definitions override built-ins by name
- **Transparency** — read the file, understand exactly what the agent does
- **Claude Code compatibility** — same YAML frontmatter format, easy migration

### Why an Orchestrator instead of letting users pick agents?

Users shouldn't need to know the agent topology. "Add rate limiting with tests" should just work — the Orchestrator figures out it needs a planner, editor, and reviewer in coordinate mode. This is Agno's strength: intelligent delegation.

## Roadmap

See [GitHub Issues](https://github.com/ignite-ember/ember-code/issues) for the current roadmap.

**Planned features:**
- [ ] Plugin system (installable agent/tool packages)
- [ ] Web UI (Agno Playground integration)
- [ ] Voice mode (speech-to-text input)
- [ ] Multi-repo support (workspaces)
- [ ] Cron tasks (scheduled agent runs)

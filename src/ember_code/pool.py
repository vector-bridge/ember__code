"""Agent Pool — loads, parses, and manages agent definitions from .md files."""

import re
import sys
from pathlib import Path
from typing import Any

import yaml
from agno.agent import Agent
from pydantic import BaseModel, Field

from ember_code.config.models import ModelRegistry
from ember_code.config.settings import Settings
from ember_code.config.tool_permissions import ToolPermissions
from ember_code.tools.registry import ToolRegistry


class AgentDefinition(BaseModel):
    """Parsed agent definition from a .md file."""

    name: str
    description: str
    tools: list[str] = Field(default_factory=list)
    model: str | None = None
    color: str | None = None
    reasoning: bool = False
    reasoning_min_steps: int = 1
    reasoning_max_steps: int = 10
    tags: list[str] = Field(default_factory=list)
    can_orchestrate: bool = True
    max_turns: int | None = None
    temperature: float | None = None
    system_prompt: str = ""
    source_path: Path | None = None


# ── Parsing ──────────────────────────────────────────────────────────


def parse_agent_file(path: Path) -> AgentDefinition:
    """Parse a .md file with YAML frontmatter into an AgentDefinition."""
    content = path.read_text()

    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
    if not frontmatter_match:
        raise ValueError(f"No YAML frontmatter found in {path}")

    yaml_str = frontmatter_match.group(1)
    body = frontmatter_match.group(2).strip()
    fm = yaml.safe_load(yaml_str) or {}

    if "name" not in fm:
        raise ValueError(f"Agent definition missing 'name' in {path}")
    if "description" not in fm:
        raise ValueError(f"Agent definition missing 'description' in {path}")

    # Parse tools
    tools_raw = fm.get("tools", [])
    if isinstance(tools_raw, str):
        tools = [t.strip() for t in tools_raw.split(",") if t.strip()]
    elif isinstance(tools_raw, list):
        tools = tools_raw
    else:
        tools = []

    # Parse tags
    tags = fm.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    return AgentDefinition(
        name=fm["name"],
        description=fm["description"],
        tools=tools,
        model=fm.get("model"),
        color=fm.get("color"),
        reasoning=fm.get("reasoning", False),
        reasoning_min_steps=fm.get("reasoning_min_steps", 1),
        reasoning_max_steps=fm.get("reasoning_max_steps", 10),
        tags=tags,
        can_orchestrate=fm.get("can_orchestrate", True),
        max_turns=fm.get("max_turns"),
        temperature=fm.get("temperature"),
        system_prompt=body,
        source_path=path,
    )


# ── Building ─────────────────────────────────────────────────────────


def build_agent(
    definition: AgentDefinition,
    settings: Settings,
    base_dir: str | None = None,
    mcp_clients: dict[str, Any] | None = None,
) -> Agent:
    """Build an Agno Agent from an AgentDefinition.

    This is the single place where an agent is constructed.  It gathers
    everything the agent needs — model, tools, MCP tools, prompts,
    reasoning config — and produces a ready-to-use ``Agent``.
    """
    # ── Model ──────────────────────────────────────────────────────
    BUILTIN_DEFAULT = "MiniMax-M2.5"
    agent_model = definition.model
    if not agent_model or agent_model == BUILTIN_DEFAULT:
        agent_model = settings.models.default
    model = ModelRegistry(settings).get_model(agent_model)

    if definition.temperature is not None:
        model.temperature = definition.temperature

    # ── Tools ──────────────────────────────────────────────────────
    tools: list[Any] = []
    if definition.tools:
        permissions = ToolPermissions(project_dir=Path(base_dir) if base_dir else None)
        registry = ToolRegistry(base_dir=base_dir, permissions=permissions)
        tools = registry.resolve(definition.tools)

    # ── Schedule tools (shared across all agents) ───────────────
    if tools:
        from ember_code.tools.schedule import ScheduleTools

        tools.append(ScheduleTools())

    # ── MCP tools (user-configured servers) ─────────────────────
    if tools and mcp_clients:
        for client in mcp_clients.values():
            if client not in tools:
                tools.append(client)

    # ── Instructions ────────────────────────────────────────────────
    instructions: list[str] = []
    if definition.system_prompt:
        instructions.append(definition.system_prompt)
    if base_dir:
        instructions.append(f"Working directory: {base_dir}")
    if mcp_clients:
        mcp_names = ", ".join(mcp_clients.keys())
        instructions.append(
            f"You have MCP tools from: {mcp_names}. "
            f"Project path: {base_dir}\n"
            f"If an MCP tool returns empty/no data, do NOT retry with different arguments. "
            f"Report what happened and ask the user."
        )

    # ── Construct ──────────────────────────────────────────────────
    kwargs: dict[str, Any] = {
        "name": definition.name,
        "model": model,
        "description": definition.description,
        "instructions": instructions if instructions else None,
        "tools": tools if tools else None,
        "markdown": True,
        "num_history_runs": settings.storage.max_history_runs,
    }

    if definition.reasoning:
        kwargs["reasoning"] = True
        kwargs["reasoning_min_steps"] = definition.reasoning_min_steps
        kwargs["reasoning_max_steps"] = definition.reasoning_max_steps

    return Agent(**kwargs)


# ── Pool ─────────────────────────────────────────────────────────────


class AgentPool:
    """Manages the pool of available agents.

    Two-phase lifecycle:
      1. ``load_definitions()`` — parse .md files, resolve priorities
      2. ``build_agents()`` — construct Agent objects (lazy by default)

    Agents are built lazily on first access via ``get()``, so startup
    only pays the cost of parsing .md files (~50ms), not importing
    LLM provider modules (~350ms).  Call ``build_agents()`` explicitly
    to force eager construction (e.g. after MCP servers connect).
    """

    def __init__(self):
        self._definitions: dict[str, tuple[AgentDefinition, int]] = {}
        self._agents: dict[str, Agent] = {}
        self._settings: Settings | None = None
        self._base_dir: str | None = None
        self._mcp_clients: dict[str, Any] | None = None

    # ── Phase 1: Load definitions ─────────────────────────────────

    def load_definitions(
        self,
        settings: Settings,
        project_dir: Path | None = None,
    ) -> None:
        """Parse all agent .md files and resolve priorities.

        No Agent objects are created — just AgentDefinition data.
        """
        if project_dir is None:
            project_dir = Path.cwd()

        self._settings = settings
        self._base_dir = str(project_dir)

        dirs = [
            (Path(__file__).parent.parent.parent / "agents", 0),
            (Path.home() / ".ember" / "agents", 1),
            (project_dir / ".ember" / "agents.local", 2),
            (project_dir / ".ember" / "agents", 3),
        ]

        if settings.agents.cross_tool_support:
            dirs.append((project_dir / ".claude" / "agents", 2))
            dirs.append((Path.home() / ".claude" / "agents", 1))

        for directory, priority in dirs:
            self._load_directory(directory, priority)

    def _load_directory(self, path: Path, priority: int) -> None:
        """Parse .md files from a directory, keeping highest-priority wins."""
        if not path.exists():
            return

        for md_file in sorted(path.glob("*.md")):
            try:
                definition = parse_agent_file(md_file)
                name = definition.name
                existing = self._definitions.get(name)

                if existing is None or priority > existing[1]:
                    self._definitions[name] = (definition, priority)
            except Exception as e:
                print(f"Warning: Failed to parse agent from {md_file}: {e}", file=sys.stderr)

    # ── Phase 2: Build agents ─────────────────────────────────────

    def build_agents(self, mcp_clients: dict[str, Any] | None = None) -> None:
        """Construct Agent objects from all loaded definitions.

        Call this after ``load_definitions()``.  Clears the agent cache
        and stores ``mcp_clients`` so agents are rebuilt with MCP tools
        on next access.  Agents are built lazily in ``get()``.
        """
        assert self._settings is not None, "Call load_definitions() first"
        self._mcp_clients = mcp_clients
        self._agents.clear()

    def _build_one(self, name: str) -> Agent:
        """Build a single agent on demand."""
        definition, _ = self._definitions[name]
        return build_agent(
            definition,
            self._settings,
            self._base_dir,
            mcp_clients=self._mcp_clients,
        )

    # ── Convenience: load + build in one call ─────────────────────

    def load_all(
        self,
        settings: Settings,
        project_dir: Path | None = None,
        mcp_clients: dict[str, Any] | None = None,
    ) -> None:
        """Parse definitions and build agents in one step.

        Shorthand for ``load_definitions()`` + ``build_agents()``.
        """
        self.load_definitions(settings, project_dir)
        self.build_agents(mcp_clients=mcp_clients)

    # ── Convenience: single directory load + build ──────────────────

    def load_directory(
        self,
        path: Path,
        priority: int,
        settings: Settings,
        base_dir: str | None = None,
    ) -> None:
        """Load and build agents from a single directory.

        Convenience method for tests and simple use cases.
        """
        self._settings = settings
        self._base_dir = base_dir or str(path.parent)
        self._load_directory(path, priority)
        self.build_agents()

    # ── Access ────────────────────────────────────────────────────

    def get(self, name: str) -> Agent:
        """Get an agent by name, building it lazily if needed."""
        if name not in self._agents:
            if name not in self._definitions:
                available = ", ".join(sorted(self._definitions.keys()))
                raise KeyError(f"Agent not found: '{name}'. Available: {available}")
            self._agents[name] = self._build_one(name)
        return self._agents[name]

    def get_definition(self, name: str) -> AgentDefinition:
        """Get an agent definition by name."""
        entry = self._definitions.get(name)
        if entry is None:
            available = ", ".join(sorted(self._definitions.keys()))
            raise KeyError(f"Agent definition not found: '{name}'. Available: {available}")
        return entry[0]

    def list_agents(self) -> list[AgentDefinition]:
        """List all agent definitions."""
        return [defn for defn, _pri in self._definitions.values()]

    def describe(self) -> str:
        """Generate a summary of all agents for the Orchestrator."""
        lines = []
        for defn, _pri in self._definitions.values():
            tools_str = ", ".join(defn.tools) if defn.tools else "none"
            tags_str = ", ".join(defn.tags) if defn.tags else "none"
            lines.append(
                f"- **{defn.name}**: {defn.description} [tools: {tools_str}] [tags: {tags_str}]"
            )
        return "\n".join(lines)

    def get_member_agents(self) -> list[Agent]:
        """Return all agents as a list (for use as team members)."""
        return [self.get(name) for name in sorted(self._definitions.keys())]

    @property
    def agent_names(self) -> list[str]:
        """Get sorted list of agent names."""
        return sorted(self._definitions.keys())

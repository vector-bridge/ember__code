"""Tool registry — maps Claude Code tool names to Agno toolkit instances."""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agno.tools.file import FileTools
from agno.tools.shell import ShellTools

from ember_code.config.tool_permissions import ToolPermissions
from ember_code.tools.edit import EmberEditTools
from ember_code.tools.schedule import ScheduleTools
from ember_code.tools.search import GlobTools, GrepTools
from ember_code.tools.web import WebTools

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Factory that maps tool names to Agno toolkit instances.

    Uses the same tool names as Claude Code (Read, Write, Edit, Bash, etc.)
    and maps them to Agno toolkit classes.

    Integrates with ToolPermissions to:
    - Skip denied tools entirely
    - Pass requires_confirmation_tools for "ask" tools
    """

    def __init__(self, base_dir: str | None = None, permissions: ToolPermissions | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.permissions = permissions or ToolPermissions(project_dir=self.base_dir)
        self._factories: dict[str, Callable] = {
            "Read": self._make_read,
            "Write": self._make_write,
            "Edit": self._make_edit,
            "Bash": self._make_bash,
            "BashOutput": self._make_bash,
            "Grep": self._make_grep,
            "Glob": self._make_glob,
            "LS": self._make_ls,
            "WebSearch": self._make_web_search,
            "WebFetch": self._make_web_fetch,
            "Python": self._make_python,
            "Schedule": self._make_schedule,
        }

    @property
    def available_tools(self) -> list[str]:
        """List all available tool names."""
        return sorted(self._factories.keys())

    def register(self, name: str, factory: Callable) -> None:
        """Register a custom tool factory."""
        self._factories[name] = factory

    def resolve(
        self,
        tool_names: list[str] | str,
        jetbrains_mcp: Any = None,
        vscode_mcp: Any = None,
        ide_mcp_clients: dict[str, Any] | None = None,
    ) -> list:
        """Resolve tool names to Agno toolkit instances.

        Denied tools are skipped. Tools with "ask" permission get
        ``requires_confirmation_tools`` set so Agno triggers HITL.

        When IDE MCP clients are provided, Agno tools that the IDE covers
        are replaced with MCP equivalents. JetBrains and VS Code are
        supported. Only one IDE override is applied (JetBrains takes
        priority if both are present).

        Args:
            tool_names: Comma-separated string or list of tool names.
            jetbrains_mcp: Optional connected JetBrains MCPTools instance.
            vscode_mcp: Optional connected VS Code MCPTools instance.
            ide_mcp_clients: Dict of IDE name → MCPTools (alternative to
                             individual params). Keys: ``"jetbrains"``, ``"vscode"``.

        Returns:
            List of Agno toolkit instances.
        """
        if isinstance(tool_names, str):
            tool_names = [name.strip() for name in tool_names.split(",") if name.strip()]

        tools = []
        seen: set[str] = set()

        for name in tool_names:
            if name.startswith("MCP:") or name == "Orchestrate":
                continue

            if self.permissions.is_denied(name):
                logger.info("Tool '%s' is denied by permissions — skipping", name)
                continue

            if name not in self._factories:
                raise ValueError(f"Unknown tool: '{name}'. Available: {self.available_tools}")

            # Deduplicate (Bash and BashOutput map to the same toolkit)
            canonical = "Bash" if name == "BashOutput" else name
            if canonical in seen:
                continue
            seen.add(canonical)

            needs_confirm = self.permissions.needs_confirmation(name)
            toolkit = self._factories[name](confirm=needs_confirm)
            tools.append(toolkit)

        # Resolve IDE MCP clients from both param styles
        jb = jetbrains_mcp or (ide_mcp_clients or {}).get("jetbrains")
        vsc = vscode_mcp or (ide_mcp_clients or {}).get("vscode")

        # Apply IDE MCP overrides (JetBrains takes priority)
        if jb is not None:
            from ember_code.mcp.jetbrains import filter_tools_with_jetbrains

            tools = filter_tools_with_jetbrains(tools, tool_names, jb)
        elif vsc is not None:
            from ember_code.mcp.vscode import filter_tools_with_vscode

            tools = filter_tools_with_vscode(tools, tool_names, vsc)

        return tools

    # ── Factory methods ───────────────────────────────────────────
    # Each accepts confirm=bool. When True, all functions in the
    # toolkit are marked with requires_confirmation_tools so Agno
    # pauses for HITL before executing them.

    def _make_read(self, confirm: bool = False):
        # Read-only FileTools — search handled by Grep/Glob toolkits
        kwargs: dict = dict(
            base_dir=self.base_dir,
            enable_read_file=True,
            enable_save_file=False,
            enable_list_files=True,
            enable_search_files=False,
            enable_read_file_chunk=True,
            enable_replace_file_chunk=False,
            enable_search_content=False,
        )
        if confirm:
            kwargs["requires_confirmation_tools"] = ["read_file", "list_files"]
        return FileTools(**kwargs)

    def _make_write(self, confirm: bool = False):
        # Write-only FileTools — only save_file (read ops handled by Read toolkit)
        kwargs: dict = dict(
            base_dir=self.base_dir,
            enable_read_file=False,
            enable_save_file=True,
            enable_list_files=False,
            enable_search_files=False,
            enable_read_file_chunk=False,
            enable_replace_file_chunk=False,
            enable_search_content=False,
        )
        if confirm:
            kwargs["requires_confirmation_tools"] = ["save_file"]
        return FileTools(**kwargs)

    def _make_edit(self, confirm: bool = False):
        kwargs: dict = dict(base_dir=str(self.base_dir))
        if confirm:
            kwargs["requires_confirmation_tools"] = [
                "edit_file",
                "edit_file_replace_all",
                "create_file",
            ]
        return EmberEditTools(**kwargs)

    def _make_bash(self, confirm: bool = False):
        kwargs: dict = {}
        if confirm:
            kwargs["requires_confirmation_tools"] = ["run_shell_command"]
        return ShellTools(**kwargs)

    def _make_ls(self, confirm: bool = False):
        return ShellTools()

    def _make_grep(self, confirm: bool = False):
        kwargs: dict = dict(base_dir=str(self.base_dir))
        if confirm:
            kwargs["requires_confirmation_tools"] = ["grep", "grep_files", "grep_count"]
        return GrepTools(**kwargs)

    def _make_glob(self, confirm: bool = False):
        kwargs: dict = dict(base_dir=str(self.base_dir))
        if confirm:
            kwargs["requires_confirmation_tools"] = ["glob_files"]
        return GlobTools(**kwargs)

    def _make_web_search(self, confirm: bool = False):
        try:
            from agno.tools.duckduckgo import DuckDuckGoTools

            kwargs: dict = {}
            if confirm:
                kwargs["requires_confirmation_tools"] = ["duckduckgo_search", "duckduckgo_news"]
            return DuckDuckGoTools(**kwargs)
        except ImportError:
            raise ImportError(
                "Web search requires duckduckgo-search. Install: pip install ember-code[web]"
            ) from None

    def _make_web_fetch(self, confirm: bool = False):
        kwargs: dict = {}
        if confirm:
            kwargs["requires_confirmation_tools"] = ["fetch_url", "fetch_json"]
        return WebTools(**kwargs)

    def _make_schedule(self, confirm: bool = False):
        return ScheduleTools()

    def _make_python(self, confirm: bool = False):
        from agno.tools.python import PythonTools

        kwargs: dict = dict(base_dir=str(self.base_dir))
        if confirm:
            kwargs["requires_confirmation_tools"] = ["run_python_code"]
        return PythonTools(**kwargs)

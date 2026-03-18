"""JetBrains MCP integration — maps Agno tool names to JetBrains MCP equivalents.

When a JetBrains MCP server is configured and connected, its tools take
priority over the built-in Agno toolkits. This gives agents access to
IDE-level search, refactoring, and diagnostics instead of raw grep/file ops.

Tool mapping:
    Grep   → search_in_project (IDE-indexed, symbol-aware)
    Glob   → search_in_project (file search mode)
    Read   → get_open_file + Agno FileTools fallback
    Edit   → refactor (when applicable) + Agno EmberEditTools fallback

Tools without a JetBrains equivalent (Bash, Write, Python, WebSearch, etc.)
always use the Agno toolkit.
"""

from typing import Any

# Agent tool names that JetBrains MCP can replace.
# Maps our tool name → set of JetBrains MCP function names that cover it.
JETBRAINS_TOOL_MAP: dict[str, set[str]] = {
    "Grep": {"search_in_project"},
    "Glob": {"search_in_project"},
    "Read": {"get_open_file"},
    "Edit": {"refactor"},
}

# JetBrains MCP server name as expected in .mcp.json
JETBRAINS_SERVER_NAME = "jetbrains"


def get_jetbrains_tools(mcp_tools: Any) -> set[str]:
    """Extract the set of function names provided by a JetBrains MCP connection.

    Args:
        mcp_tools: An Agno MCPTools instance (connected to JetBrains).

    Returns:
        Set of tool/function names the server exposes.
    """
    try:
        # Agno MCPTools exposes .functions after connection
        if hasattr(mcp_tools, "functions"):
            funcs = mcp_tools.functions
            if isinstance(funcs, dict):
                return set(funcs.keys())
            if isinstance(funcs, list):
                return {getattr(f, "name", None) or getattr(f, "__name__", str(f)) for f in funcs}
        # Fallback: check toolkit functions
        if hasattr(mcp_tools, "toolkit_functions"):
            return {f.name for f in mcp_tools.toolkit_functions}
    except Exception:
        pass
    return set()


def should_skip_agno_tool(
    tool_name: str,
    jetbrains_functions: set[str],
) -> bool:
    """Check if an Agno tool should be skipped because JetBrains provides it.

    Args:
        tool_name: The Agno tool name (e.g., "Grep", "Read").
        jetbrains_functions: Set of function names from the JetBrains MCP server.

    Returns:
        True if JetBrains fully covers this tool and the Agno version should be skipped.
    """
    required = JETBRAINS_TOOL_MAP.get(tool_name)
    if not required:
        return False

    # Skip the Agno tool only if JetBrains provides ALL required functions
    return required.issubset(jetbrains_functions)


def filter_tools_with_jetbrains(
    agno_tools: list[Any],
    tool_names: list[str],
    jetbrains_mcp: Any,
) -> list[Any]:
    """Replace Agno tools with JetBrains MCP equivalents where possible.

    Takes the list of resolved Agno toolkit instances and the connected
    JetBrains MCPTools. Returns a new list where:
    - Agno toolkits that JetBrains covers are removed
    - The JetBrains MCPTools instance is added (once)

    Args:
        agno_tools: List of Agno toolkit instances from ToolRegistry.resolve().
        tool_names: The original tool name list (e.g., ["Read", "Grep", "Edit"]).
        jetbrains_mcp: Connected Agno MCPTools instance for JetBrains.

    Returns:
        New list of toolkit instances with JetBrains replacements applied.
    """
    jb_functions = get_jetbrains_tools(jetbrains_mcp)
    if not jb_functions:
        # JetBrains server connected but exposes no tools — keep Agno tools
        return agno_tools

    # Figure out which Agno tools to skip
    skip_names = {name for name in tool_names if should_skip_agno_tool(name, jb_functions)}

    if not skip_names:
        # JetBrains doesn't cover any of the requested tools — keep as-is,
        # but still add JetBrains for its extra capabilities
        return [*agno_tools, jetbrains_mcp]

    # Map Agno toolkit instances back to their tool names for filtering.
    # We use the toolkit's name attribute to identify them.
    TOOLKIT_NAME_MAP = {
        "ember_grep": "Grep",
        "ember_glob": "Glob",
        "ember_edit": "Edit",
    }

    filtered = []
    for toolkit in agno_tools:
        toolkit_name = getattr(toolkit, "name", "")
        agent_tool_name = TOOLKIT_NAME_MAP.get(toolkit_name)

        if agent_tool_name and agent_tool_name in skip_names:
            continue  # JetBrains replaces this tool
        # For Read (FileTools), skip only if agent didn't also request Write
        if toolkit_name == "file_tools" and "Read" in skip_names and "Write" not in tool_names:
            continue

        filtered.append(toolkit)

    # Add JetBrains MCP tools (once)
    filtered.append(jetbrains_mcp)
    return filtered

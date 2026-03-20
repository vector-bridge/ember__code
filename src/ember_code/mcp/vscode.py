"""VS Code MCP integration — maps Agno tool names to VS Code MCP equivalents.

When a VS Code MCP server is configured and connected, its tools take
priority over the built-in Agno toolkits, just like JetBrains MCP.

Tool mapping (using vscode-mcp-server conventions):
    Grep   → search_symbols_code (symbol-aware search)
    Glob   → list_files_code (workspace file listing)
    Read   → read_file_code (file contents with encoding)
    Edit   → replace_lines_code (line-level edits)
    Write  → create_file_code (file creation)

Tools without a VS Code equivalent (Bash, Python, WebSearch, etc.)
always use the Agno toolkit.
"""

from typing import Any

# Agent tool names that VS Code MCP can replace.
VSCODE_TOOL_MAP: dict[str, set[str]] = {
    "Grep": {"search_symbols_code"},
    "Glob": {"list_files_code"},
    "Read": {"read_file_code"},
    "Edit": {"replace_lines_code"},
    "Write": {"create_file_code"},
}

# VS Code MCP server name as expected in .mcp.json
VSCODE_SERVER_NAME = "vscode"

# Toolkit name → agent tool name (for filtering Agno toolkits)
_TOOLKIT_NAME_MAP = {
    "ember_grep": "Grep",
    "ember_glob": "Glob",
    "ember_edit": "Edit",
    "file_tools": None,  # special handling — covers Read and Write
}


def get_vscode_tools(mcp_tools: Any) -> set[str]:
    """Extract the set of function names provided by a VS Code MCP connection."""
    try:
        if hasattr(mcp_tools, "functions"):
            funcs = mcp_tools.functions
            if isinstance(funcs, dict):
                return set(funcs.keys())
            if isinstance(funcs, list):
                return {getattr(f, "name", None) or getattr(f, "__name__", str(f)) for f in funcs}
        if hasattr(mcp_tools, "toolkit_functions"):
            return {f.name for f in mcp_tools.toolkit_functions}
    except Exception:
        pass
    return set()


def should_skip_agno_tool(tool_name: str, vscode_functions: set[str]) -> bool:
    """Check if an Agno tool should be skipped because VS Code provides it."""
    required = VSCODE_TOOL_MAP.get(tool_name)
    if not required:
        return False
    return required.issubset(vscode_functions)


def filter_tools_with_vscode(
    agno_tools: list[Any],
    tool_names: list[str],
    vscode_mcp: Any,
) -> list[Any]:
    """Replace Agno tools with VS Code MCP equivalents where possible.

    Same pattern as the JetBrains filter — removes Agno toolkits that
    VS Code covers and adds the VS Code MCPTools instance.
    """
    vsc_functions = get_vscode_tools(vscode_mcp)
    if not vsc_functions:
        return agno_tools

    skip_names = {name for name in tool_names if should_skip_agno_tool(name, vsc_functions)}

    if not skip_names:
        return [*agno_tools, vscode_mcp]

    filtered = []
    for toolkit in agno_tools:
        toolkit_name = getattr(toolkit, "name", "")
        agent_tool_name = _TOOLKIT_NAME_MAP.get(toolkit_name)

        # Regular toolkit mapping
        if agent_tool_name and agent_tool_name in skip_names:
            continue

        # FileTools covers both Read and Write — only skip if ALL requested ops are covered
        if toolkit_name == "file_tools":
            requested_file_ops = {"Read", "Write"} & set(tool_names)
            if requested_file_ops and requested_file_ops.issubset(skip_names):
                continue

        filtered.append(toolkit)

    filtered.append(vscode_mcp)
    return filtered

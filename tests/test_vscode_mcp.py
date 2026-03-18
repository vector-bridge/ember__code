"""Tests for VS Code MCP integration."""

from unittest.mock import MagicMock

from ember_code.mcp.vscode import (
    filter_tools_with_vscode,
    get_vscode_tools,
    should_skip_agno_tool,
)


class FakeToolkit:
    """Minimal fake Agno toolkit for testing."""

    def __init__(self, name: str):
        self.name = name


class TestGetVscodeTools:
    def test_extracts_from_dict_functions(self):
        mcp = MagicMock()
        mcp.functions = {"read_file_code": ..., "list_files_code": ..., "search_symbols_code": ...}
        result = get_vscode_tools(mcp)
        assert result == {"read_file_code", "list_files_code", "search_symbols_code"}

    def test_extracts_from_list_functions(self):
        mcp = MagicMock()
        func1 = MagicMock()
        func1.name = "read_file_code"
        func2 = MagicMock()
        func2.name = "get_diagnostics_code"
        mcp.functions = [func1, func2]
        result = get_vscode_tools(mcp)
        assert "read_file_code" in result
        assert "get_diagnostics_code" in result

    def test_returns_empty_on_no_functions(self):
        mcp = MagicMock(spec=[])
        result = get_vscode_tools(mcp)
        assert result == set()


class TestShouldSkipAgnoTool:
    def test_skip_grep_when_search_available(self):
        vsc = {"search_symbols_code", "read_file_code"}
        assert should_skip_agno_tool("Grep", vsc) is True

    def test_skip_glob_when_list_available(self):
        vsc = {"list_files_code"}
        assert should_skip_agno_tool("Glob", vsc) is True

    def test_skip_read_when_read_available(self):
        vsc = {"read_file_code"}
        assert should_skip_agno_tool("Read", vsc) is True

    def test_skip_edit_when_replace_available(self):
        vsc = {"replace_lines_code"}
        assert should_skip_agno_tool("Edit", vsc) is True

    def test_skip_write_when_create_available(self):
        vsc = {"create_file_code"}
        assert should_skip_agno_tool("Write", vsc) is True

    def test_keep_grep_when_search_missing(self):
        vsc = {"read_file_code"}
        assert should_skip_agno_tool("Grep", vsc) is False

    def test_never_skip_bash(self):
        vsc = {"read_file_code", "list_files_code", "search_symbols_code"}
        assert should_skip_agno_tool("Bash", vsc) is False

    def test_never_skip_unknown(self):
        vsc = {"read_file_code"}
        assert should_skip_agno_tool("CustomTool", vsc) is False


class TestFilterToolsWithVscode:
    def test_replaces_grep_with_vscode(self):
        grep_toolkit = FakeToolkit("ember_grep")
        bash_toolkit = FakeToolkit("shell_tools")
        vsc_mcp = MagicMock()
        vsc_mcp.functions = {"search_symbols_code": ...}

        result = filter_tools_with_vscode(
            [grep_toolkit, bash_toolkit],
            ["Grep", "Bash"],
            vsc_mcp,
        )

        names = [getattr(t, "name", None) for t in result]
        assert "ember_grep" not in names
        assert "shell_tools" in names
        assert vsc_mcp in result

    def test_replaces_read_and_write(self):
        file_tools = FakeToolkit("file_tools")
        vsc_mcp = MagicMock()
        vsc_mcp.functions = {"read_file_code": ..., "create_file_code": ...}

        result = filter_tools_with_vscode(
            [file_tools],
            ["Read", "Write"],
            vsc_mcp,
        )

        assert file_tools not in result
        assert vsc_mcp in result

    def test_keeps_file_tools_when_write_not_covered(self):
        file_tools = FakeToolkit("file_tools")
        vsc_mcp = MagicMock()
        # Only read is covered, not write
        vsc_mcp.functions = {"read_file_code": ...}

        result = filter_tools_with_vscode(
            [file_tools],
            ["Read", "Write"],
            vsc_mcp,
        )

        # file_tools should stay because Write isn't covered
        assert file_tools in result
        assert vsc_mcp in result

    def test_keeps_all_when_no_vsc_functions(self):
        grep = FakeToolkit("ember_grep")
        vsc_mcp = MagicMock(spec=[])

        result = filter_tools_with_vscode([grep], ["Grep"], vsc_mcp)
        assert grep in result
        assert vsc_mcp not in result

    def test_adds_vscode_even_when_no_overlap(self):
        bash = FakeToolkit("shell_tools")
        vsc_mcp = MagicMock()
        vsc_mcp.functions = {"get_diagnostics_code": ...}

        result = filter_tools_with_vscode([bash], ["Bash"], vsc_mcp)
        assert bash in result
        assert vsc_mcp in result

    def test_vscode_added_only_once(self):
        grep = FakeToolkit("ember_grep")
        glob = FakeToolkit("ember_glob")
        vsc_mcp = MagicMock()
        vsc_mcp.functions = {"search_symbols_code": ..., "list_files_code": ...}

        result = filter_tools_with_vscode(
            [grep, glob],
            ["Grep", "Glob"],
            vsc_mcp,
        )
        assert result.count(vsc_mcp) == 1

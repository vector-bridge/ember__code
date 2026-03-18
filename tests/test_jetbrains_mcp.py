"""Tests for JetBrains MCP integration."""

from unittest.mock import MagicMock

from ember_code.mcp.jetbrains import (
    filter_tools_with_jetbrains,
    get_jetbrains_tools,
    should_skip_agno_tool,
)


class FakeToolkit:
    """Minimal fake Agno toolkit for testing."""

    def __init__(self, name: str):
        self.name = name


class TestGetJetbrainsTools:
    def test_extracts_from_dict_functions(self):
        mcp = MagicMock()
        mcp.functions = {"search_in_project": ..., "get_open_file": ..., "refactor": ...}
        result = get_jetbrains_tools(mcp)
        assert result == {"search_in_project", "get_open_file", "refactor"}

    def test_extracts_from_list_functions(self):
        mcp = MagicMock()
        func1 = MagicMock()
        func1.name = "search_in_project"
        func2 = MagicMock()
        func2.name = "get_diagnostics"
        mcp.functions = [func1, func2]
        result = get_jetbrains_tools(mcp)
        assert "search_in_project" in result
        assert "get_diagnostics" in result

    def test_returns_empty_on_no_functions(self):
        mcp = MagicMock(spec=[])
        result = get_jetbrains_tools(mcp)
        assert result == set()

    def test_handles_exception(self):
        mcp = MagicMock()
        mcp.functions = property(lambda self: (_ for _ in ()).throw(RuntimeError))
        # Should not raise
        result = get_jetbrains_tools(mcp)
        assert isinstance(result, set)


class TestShouldSkipAgnoTool:
    def test_skip_grep_when_search_available(self):
        jb = {"search_in_project", "get_diagnostics"}
        assert should_skip_agno_tool("Grep", jb) is True

    def test_skip_glob_when_search_available(self):
        jb = {"search_in_project"}
        assert should_skip_agno_tool("Glob", jb) is True

    def test_keep_grep_when_search_missing(self):
        jb = {"get_diagnostics", "refactor"}
        assert should_skip_agno_tool("Grep", jb) is False

    def test_never_skip_bash(self):
        jb = {"search_in_project", "refactor", "get_open_file"}
        assert should_skip_agno_tool("Bash", jb) is False

    def test_never_skip_write(self):
        jb = {"search_in_project", "refactor", "get_open_file"}
        assert should_skip_agno_tool("Write", jb) is False

    def test_never_skip_unknown(self):
        jb = {"search_in_project"}
        assert should_skip_agno_tool("CustomTool", jb) is False

    def test_skip_edit_when_refactor_available(self):
        jb = {"refactor"}
        assert should_skip_agno_tool("Edit", jb) is True

    def test_keep_edit_when_refactor_missing(self):
        jb = {"search_in_project"}
        assert should_skip_agno_tool("Edit", jb) is False


class TestFilterToolsWithJetbrains:
    def test_replaces_grep_with_jetbrains(self):
        grep_toolkit = FakeToolkit("ember_grep")
        bash_toolkit = FakeToolkit("shell_tools")
        jb_mcp = MagicMock()
        jb_mcp.functions = {"search_in_project": ...}

        result = filter_tools_with_jetbrains(
            [grep_toolkit, bash_toolkit],
            ["Grep", "Bash"],
            jb_mcp,
        )

        names = [getattr(t, "name", None) for t in result]
        assert "ember_grep" not in names
        assert "shell_tools" in names
        assert jb_mcp in result

    def test_replaces_grep_and_glob(self):
        grep = FakeToolkit("ember_grep")
        glob = FakeToolkit("ember_glob")
        jb_mcp = MagicMock()
        jb_mcp.functions = {"search_in_project": ...}

        result = filter_tools_with_jetbrains(
            [grep, glob],
            ["Grep", "Glob"],
            jb_mcp,
        )

        names = [getattr(t, "name", None) for t in result]
        assert "ember_grep" not in names
        assert "ember_glob" not in names
        assert jb_mcp in result

    def test_keeps_all_when_no_jb_functions(self):
        grep = FakeToolkit("ember_grep")
        jb_mcp = MagicMock(spec=[])

        result = filter_tools_with_jetbrains(
            [grep],
            ["Grep"],
            jb_mcp,
        )

        assert grep in result
        assert jb_mcp not in result

    def test_adds_jetbrains_even_when_no_overlap(self):
        bash = FakeToolkit("shell_tools")
        jb_mcp = MagicMock()
        jb_mcp.functions = {"get_diagnostics": ...}

        result = filter_tools_with_jetbrains(
            [bash],
            ["Bash"],
            jb_mcp,
        )

        assert bash in result
        assert jb_mcp in result

    def test_jetbrains_added_only_once(self):
        grep = FakeToolkit("ember_grep")
        glob = FakeToolkit("ember_glob")
        jb_mcp = MagicMock()
        jb_mcp.functions = {"search_in_project": ...}

        result = filter_tools_with_jetbrains(
            [grep, glob],
            ["Grep", "Glob"],
            jb_mcp,
        )

        assert result.count(jb_mcp) == 1

    def test_keeps_file_tools_when_write_requested(self):
        file_tools = FakeToolkit("file_tools")
        jb_mcp = MagicMock()
        jb_mcp.functions = {"get_open_file": ...}

        result = filter_tools_with_jetbrains(
            [file_tools],
            ["Read", "Write"],
            jb_mcp,
        )

        assert file_tools in result

    def test_skips_file_tools_when_only_read(self):
        file_tools = FakeToolkit("file_tools")
        jb_mcp = MagicMock()
        jb_mcp.functions = {"get_open_file": ...}

        result = filter_tools_with_jetbrains(
            [file_tools],
            ["Read"],
            jb_mcp,
        )

        assert file_tools not in result
        assert jb_mcp in result

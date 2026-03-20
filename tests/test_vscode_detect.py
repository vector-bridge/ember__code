"""Tests for VS Code auto-detection."""

import json
from unittest.mock import MagicMock, patch

from ember_code.mcp.vscode_detect import (
    _has_vscode_config,
    _write_mcp_config,
    detect_vscode,
    ensure_vscode_mcp,
)


class TestDetectVscode:
    def test_detects_from_running_process(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "user 1234 /Applications/Visual Studio Code.app/Contents/MacOS/code helper"
        )

        with patch("ember_code.mcp.vscode_detect.subprocess.run", return_value=mock_result):
            result = detect_vscode()
        assert result is not None

    def test_detects_from_cli(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "nothing relevant"

        with (
            patch("ember_code.mcp.vscode_detect.subprocess.run", return_value=mock_result),
            patch(
                "ember_code.mcp.vscode_detect.shutil.which",
                side_effect=lambda x: "/usr/bin/code" if x == "code" else None,
            ),
        ):
            result = detect_vscode()
        assert result == "code"

    def test_returns_none_when_nothing_found(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "nothing relevant"

        with (
            patch("ember_code.mcp.vscode_detect.subprocess.run", return_value=mock_result),
            patch("ember_code.mcp.vscode_detect.shutil.which", return_value=None),
            patch("ember_code.mcp.vscode_detect._detect_macos_installed", return_value=None),
            patch("ember_code.mcp.vscode_detect._detect_linux_installed", return_value=None),
        ):
            result = detect_vscode()
        assert result is None

    def test_handles_process_check_failure(self):
        with (
            patch(
                "ember_code.mcp.vscode_detect.subprocess.run",
                side_effect=OSError("not found"),
            ),
            patch("ember_code.mcp.vscode_detect.shutil.which", return_value=None),
            patch("ember_code.mcp.vscode_detect._detect_macos_installed", return_value=None),
            patch("ember_code.mcp.vscode_detect._detect_linux_installed", return_value=None),
        ):
            result = detect_vscode()
        assert result is None


class TestHasVscodeConfig:
    def test_finds_config_in_project(self, tmp_path):
        (tmp_path / ".ember").mkdir()
        mcp_json = tmp_path / ".ember" / ".mcp.json"
        mcp_json.write_text(json.dumps({"mcpServers": {"vscode": {"command": "npx"}}}))
        assert _has_vscode_config(tmp_path) is True

    def test_returns_false_when_no_file(self, tmp_path):
        assert _has_vscode_config(tmp_path) is False

    def test_returns_false_when_no_vscode_entry(self, tmp_path):
        (tmp_path / ".ember").mkdir()
        mcp_json = tmp_path / ".ember" / ".mcp.json"
        mcp_json.write_text(json.dumps({"mcpServers": {"jetbrains": {}}}))
        assert _has_vscode_config(tmp_path) is False


class TestWriteMcpConfig:
    def test_creates_new_file(self, tmp_path):
        _write_mcp_config(tmp_path)
        mcp_path = tmp_path / ".ember" / ".mcp.json"
        assert mcp_path.exists()
        data = json.loads(mcp_path.read_text())
        assert "vscode" in data["mcpServers"]
        assert data["mcpServers"]["vscode"]["command"] == "npx"

    def test_preserves_existing_servers(self, tmp_path):
        (tmp_path / ".ember").mkdir()
        mcp_path = tmp_path / ".ember" / ".mcp.json"
        mcp_path.write_text(json.dumps({"mcpServers": {"jetbrains": {"command": "npx"}}}))

        _write_mcp_config(tmp_path)

        data = json.loads(mcp_path.read_text())
        assert "jetbrains" in data["mcpServers"]
        assert "vscode" in data["mcpServers"]


class TestEnsureVscodeMcp:
    def test_skips_when_already_configured(self, tmp_path):
        (tmp_path / ".ember").mkdir()
        mcp_path = tmp_path / ".ember" / ".mcp.json"
        mcp_path.write_text(json.dumps({"mcpServers": {"vscode": {}}}))
        assert ensure_vscode_mcp(tmp_path) is False

    def test_writes_config_when_detected(self, tmp_path):
        with patch(
            "ember_code.mcp.vscode_detect.detect_vscode",
            return_value="VS Code",
        ):
            result = ensure_vscode_mcp(tmp_path)

        assert result is True
        data = json.loads((tmp_path / ".ember" / ".mcp.json").read_text())
        assert "vscode" in data["mcpServers"]

    def test_noop_when_not_detected(self, tmp_path):
        with patch(
            "ember_code.mcp.vscode_detect.detect_vscode",
            return_value=None,
        ):
            result = ensure_vscode_mcp(tmp_path)

        assert result is False
        assert not (tmp_path / ".ember" / ".mcp.json").exists()

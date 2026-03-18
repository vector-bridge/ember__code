"""Tests for JetBrains IDE auto-detection."""

import json
from unittest.mock import MagicMock, patch

from ember_code.mcp.jetbrains_detect import (
    _has_jetbrains_config,
    _write_mcp_config,
    detect_jetbrains_ide,
    ensure_jetbrains_mcp,
)


class TestDetectJetbrainsIde:
    def test_detects_from_running_process(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "user 1234 /Applications/PyCharm CE.app/Contents/MacOS/pycharm"

        with patch("ember_code.mcp.jetbrains_detect.subprocess.run", return_value=mock_result):
            result = detect_jetbrains_ide()
        assert result is not None

    def test_returns_none_when_no_ide(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "user 1234 /usr/bin/python3 some_script.py"

        with (
            patch("ember_code.mcp.jetbrains_detect.subprocess.run", return_value=mock_result),
            patch("ember_code.mcp.jetbrains_detect._detect_macos_installed", return_value=None),
            patch("ember_code.mcp.jetbrains_detect._detect_linux_installed", return_value=None),
        ):
            result = detect_jetbrains_ide()
        assert result is None

    def test_handles_process_check_failure(self):
        with (
            patch(
                "ember_code.mcp.jetbrains_detect.subprocess.run",
                side_effect=OSError("not found"),
            ),
            patch("ember_code.mcp.jetbrains_detect._detect_macos_installed", return_value=None),
            patch("ember_code.mcp.jetbrains_detect._detect_linux_installed", return_value=None),
        ):
            result = detect_jetbrains_ide()
        assert result is None

    def test_falls_back_to_installed_check(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "nothing relevant"

        with (
            patch("ember_code.mcp.jetbrains_detect.subprocess.run", return_value=mock_result),
            patch("ember_code.mcp.jetbrains_detect.platform.system", return_value="Darwin"),
            patch(
                "ember_code.mcp.jetbrains_detect._detect_macos_installed",
                return_value="PyCharm",
            ),
        ):
            result = detect_jetbrains_ide()
        assert result == "PyCharm"


class TestHasJetbrainsConfig:
    def test_finds_config_in_project(self, tmp_path):
        (tmp_path / ".ember").mkdir()
        mcp_json = tmp_path / ".ember" / ".mcp.json"
        mcp_json.write_text(json.dumps({"mcpServers": {"jetbrains": {"command": "npx"}}}))
        assert _has_jetbrains_config(tmp_path) is True

    def test_returns_false_when_no_file(self, tmp_path):
        assert _has_jetbrains_config(tmp_path) is False

    def test_returns_false_when_no_jetbrains_entry(self, tmp_path):
        (tmp_path / ".ember").mkdir()
        mcp_json = tmp_path / ".ember" / ".mcp.json"
        mcp_json.write_text(json.dumps({"mcpServers": {"other": {}}}))
        assert _has_jetbrains_config(tmp_path) is False

    def test_handles_malformed_json(self, tmp_path):
        (tmp_path / ".ember").mkdir()
        mcp_json = tmp_path / ".ember" / ".mcp.json"
        mcp_json.write_text("not json")
        assert _has_jetbrains_config(tmp_path) is False


class TestWriteMcpConfig:
    def test_creates_new_file(self, tmp_path):
        _write_mcp_config(tmp_path)
        mcp_path = tmp_path / ".ember" / ".mcp.json"
        assert mcp_path.exists()
        data = json.loads(mcp_path.read_text())
        assert "jetbrains" in data["mcpServers"]
        assert data["mcpServers"]["jetbrains"]["command"] == "npx"

    def test_preserves_existing_servers(self, tmp_path):
        (tmp_path / ".ember").mkdir()
        mcp_path = tmp_path / ".ember" / ".mcp.json"
        mcp_path.write_text(json.dumps({"mcpServers": {"other": {"command": "foo"}}}))

        _write_mcp_config(tmp_path)

        data = json.loads(mcp_path.read_text())
        assert "other" in data["mcpServers"]
        assert "jetbrains" in data["mcpServers"]

    def test_handles_malformed_existing_file(self, tmp_path):
        (tmp_path / ".ember").mkdir()
        mcp_path = tmp_path / ".ember" / ".mcp.json"
        mcp_path.write_text("broken")

        _write_mcp_config(tmp_path)

        data = json.loads(mcp_path.read_text())
        assert "jetbrains" in data["mcpServers"]


class TestEnsureJetbrainsMcp:
    def test_skips_when_already_configured(self, tmp_path):
        (tmp_path / ".ember").mkdir()
        mcp_path = tmp_path / ".ember" / ".mcp.json"
        mcp_path.write_text(json.dumps({"mcpServers": {"jetbrains": {}}}))

        result = ensure_jetbrains_mcp(tmp_path)
        assert result is False

    def test_writes_config_when_ide_detected(self, tmp_path):
        with patch(
            "ember_code.mcp.jetbrains_detect.detect_jetbrains_ide",
            return_value="PyCharm",
        ):
            result = ensure_jetbrains_mcp(tmp_path)

        assert result is True
        data = json.loads((tmp_path / ".ember" / ".mcp.json").read_text())
        assert "jetbrains" in data["mcpServers"]

    def test_noop_when_no_ide_detected(self, tmp_path):
        with patch(
            "ember_code.mcp.jetbrains_detect.detect_jetbrains_ide",
            return_value=None,
        ):
            result = ensure_jetbrains_mcp(tmp_path)

        assert result is False
        assert not (tmp_path / ".ember" / ".mcp.json").exists()

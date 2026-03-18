"""Auto-detect VS Code and create .mcp.json entries.

Checks for VS Code installations on macOS and Linux. When found and no
``vscode`` MCP entry exists, writes the configuration so agents that
declare ``mcp_servers: [vscode]`` work out of the box.
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from pathlib import Path

from ember_code.mcp.ide_detect import IDEDetector

logger = logging.getLogger(__name__)

# VS Code variant identifiers
VSCODE_VARIANTS = [
    "code",           # VS Code
    "code-insiders",  # VS Code Insiders
    "codium",         # VSCodium
    "cursor",         # Cursor
]

# Default MCP server config for VS Code
VSCODE_MCP_CONFIG = {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "vscode-mcp-server@latest"],
    "env": {},
}


class VSCodeDetector(IDEDetector):
    """Detector for VS Code and its variants."""

    def __init__(self) -> None:
        super().__init__(name="vscode", mcp_config=VSCODE_MCP_CONFIG)

    def detect(self) -> str | None:
        """Detect if VS Code (or a variant) is installed or running.

        Returns the variant name if found, None otherwise.
        """
        # 1. Check running processes
        name = _detect_from_processes()
        if name:
            return name

        # 2. Check if 'code' CLI is on PATH
        name = _detect_from_cli()
        if name:
            return name

        # 3. Check installed applications
        system = platform.system()
        if system == "Darwin":
            return _detect_macos_installed()
        if system == "Linux":
            return _detect_linux_installed()

        return None


# Singleton instance
_detector = VSCodeDetector()


# ── Module-level convenience functions ────────────────────────────────


def detect_vscode() -> str | None:
    """Detect if VS Code (or a variant) is installed or running."""
    return _detector.detect()


def ensure_vscode_mcp(project_dir: Path) -> bool:
    """Auto-configure VS Code MCP if the editor is detected."""
    if _has_vscode_config(project_dir):
        return False

    variant = detect_vscode()
    if not variant:
        return False

    logger.info("Detected VS Code (%s) — adding MCP configuration", variant)
    _write_mcp_config(project_dir)
    return True


def _has_vscode_config(project_dir: Path) -> bool:
    """Check if a 'vscode' MCP entry already exists."""
    return _detector.has_config(project_dir)


def _write_mcp_config(project_dir: Path) -> None:
    """Write VS Code MCP entry to the project's .ember/.mcp.json."""
    _detector.write_config(project_dir)


# ── Detection strategies ─────────────────────────────────────────────


def _detect_from_processes() -> str | None:
    """Check running processes for VS Code instances."""
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        output = result.stdout.lower()
        # Check for specific VS Code process patterns
        patterns = [
            ("visual studio code", "VS Code"),
            ("code helper", "VS Code"),
            ("code-insiders", "VS Code Insiders"),
            ("vscodium", "VSCodium"),
            ("cursor", "Cursor"),
        ]
        for pattern, name in patterns:
            if pattern in output:
                return name
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _detect_from_cli() -> str | None:
    """Check if a VS Code CLI command is available on PATH."""
    for variant in VSCODE_VARIANTS:
        if shutil.which(variant):
            return variant
    return None


def _detect_macos_installed() -> str | None:
    """Check macOS /Applications for VS Code."""
    apps_dir = Path("/Applications")
    if not apps_dir.exists():
        return None

    app_names = [
        ("Visual Studio Code.app", "VS Code"),
        ("Visual Studio Code - Insiders.app", "VS Code Insiders"),
        ("VSCodium.app", "VSCodium"),
        ("Cursor.app", "Cursor"),
    ]
    for app_name, display_name in app_names:
        if (apps_dir / app_name).exists():
            return display_name

    return None


def _detect_linux_installed() -> str | None:
    """Check Linux paths for VS Code."""
    # Check common binary locations
    binary_paths = [
        (Path("/usr/bin/code"), "VS Code"),
        (Path("/usr/bin/code-insiders"), "VS Code Insiders"),
        (Path("/usr/bin/codium"), "VSCodium"),
        (Path("/snap/bin/code"), "VS Code"),
    ]
    for path, name in binary_paths:
        if path.exists():
            return name

    # Check config directories
    config_dir = Path.home() / ".config"
    config_names = [
        ("Code", "VS Code"),
        ("Code - Insiders", "VS Code Insiders"),
        ("VSCodium", "VSCodium"),
        ("Cursor", "Cursor"),
    ]
    for dir_name, display_name in config_names:
        if (config_dir / dir_name).exists():
            return display_name

    return None

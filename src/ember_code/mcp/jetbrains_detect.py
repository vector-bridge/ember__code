"""Auto-detect JetBrains IDEs and create .mcp.json entries.

Checks for installed JetBrains IDEs on macOS and Linux. When found and no
``jetbrains`` MCP entry exists, writes the configuration so agents that
declare ``mcp_servers: [jetbrains]`` work out of the box.

Detection runs at session start (not just first-run init) so it picks up
IDEs installed after the project was created.
"""

from __future__ import annotations

import logging
import platform
import subprocess
import urllib.request
from pathlib import Path

from ember_code.mcp.ide_detect import IDEDetector

logger = logging.getLogger(__name__)

# Port range where PyCharm's MCP Server plugin listens for SSE connections
_SSE_PORT_MIN = 64340
_SSE_PORT_MAX = 64360

# JetBrains IDE identifiers (used in config dirs and process names)
JETBRAINS_IDES = [
    "IntelliJIdea",
    "PyCharm",
    "WebStorm",
    "GoLand",
    "Rider",
    "CLion",
    "PhpStorm",
    "RubyMine",
    "DataGrip",
    "RustRover",
    "Fleet",
]

# Default MCP server config — SSE is preferred (direct connection to IDE),
# falls back to stdio proxy if the SSE port can't be detected.
JETBRAINS_MCP_CONFIG_STDIO = {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@jetbrains/mcp-proxy@latest"],
    "env": {},
}


def _detect_sse_port() -> int | None:
    """Scan for the JetBrains MCP Server SSE endpoint.

    The MCP Server plugin in JetBrains IDEs listens on a port in the
    64340-64360 range (separate from the built-in server on 63342+).
    """
    for port in range(_SSE_PORT_MIN, _SSE_PORT_MAX + 1):
        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/sse", timeout=1)
            if resp.status == 200:
                return port
        except Exception:
            continue
    return None


def _build_mcp_config() -> dict:
    """Build the best MCP config for the current environment."""
    port = _detect_sse_port()
    if port:
        logger.info("Found JetBrains MCP SSE endpoint on port %d", port)
        return {
            "type": "sse",
            "url": f"http://127.0.0.1:{port}/sse",
        }
    return JETBRAINS_MCP_CONFIG_STDIO


class JetBrainsDetector(IDEDetector):
    """Detector for JetBrains IDEs."""

    def __init__(self) -> None:
        super().__init__(name="jetbrains", mcp_config=JETBRAINS_MCP_CONFIG_STDIO)

    def detect(self) -> str | None:
        """Detect if a JetBrains IDE is installed or running.

        Returns the IDE name if found, None otherwise.
        Checks in order: running processes, then installed applications.
        """
        # 1. Check running processes (fastest, most reliable)
        name = _detect_from_processes()
        if name:
            return name

        # 2. Check installed applications
        system = platform.system()
        if system == "Darwin":
            return _detect_macos_installed()
        if system == "Linux":
            return _detect_linux_installed()

        return None


# Singleton instance
_detector = JetBrainsDetector()


# ── Module-level convenience functions ────────────────────────────────


def detect_jetbrains_ide() -> str | None:
    """Detect if a JetBrains IDE is installed or running."""
    return _detector.detect()


def ensure_jetbrains_mcp(project_dir: Path) -> bool:
    """Auto-configure JetBrains MCP if an IDE is detected."""
    if _has_jetbrains_config(project_dir):
        return False

    ide = detect_jetbrains_ide()
    if not ide:
        return False

    logger.info("Detected JetBrains IDE (%s) — adding MCP configuration", ide)
    # Build config dynamically — prefers SSE if the port is reachable
    config = _build_mcp_config()
    _detector.mcp_config = config
    _write_mcp_config(project_dir)
    return True


def _has_jetbrains_config(project_dir: Path) -> bool:
    """Check if a 'jetbrains' MCP entry already exists."""
    return _detector.has_config(project_dir)


def _write_mcp_config(project_dir: Path) -> None:
    """Write JetBrains MCP entry to the project's .ember/.mcp.json."""
    _detector.write_config(project_dir)


# ── Detection strategies ─────────────────────────────────────────────


def _detect_from_processes() -> str | None:
    """Check running processes for JetBrains IDE instances."""
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
        for ide in JETBRAINS_IDES:
            if ide.lower() in output:
                return ide

        # Also check for common JetBrains process patterns
        jb_patterns = ["jetbrains", "idea", "pycharm", "webstorm", "goland", "clion", "phpstorm"]
        for pattern in jb_patterns:
            if pattern in output:
                return pattern.title()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _detect_macos_installed() -> str | None:
    """Check macOS /Applications for JetBrains IDEs."""
    apps_dir = Path("/Applications")
    if not apps_dir.exists():
        return None

    # Check for .app bundles
    jb_app_prefixes = [
        "IntelliJ IDEA",
        "PyCharm",
        "WebStorm",
        "GoLand",
        "Rider",
        "CLion",
        "PhpStorm",
        "RubyMine",
        "DataGrip",
        "RustRover",
        "Fleet",
    ]
    for prefix in jb_app_prefixes:
        matches = list(apps_dir.glob(f"{prefix}*.app"))
        if matches:
            return prefix

    # Check JetBrains Toolbox managed apps
    toolbox_dir = Path.home() / "Library" / "Application Support" / "JetBrains" / "Toolbox" / "apps"
    if toolbox_dir.exists() and any(toolbox_dir.iterdir()):
        return "JetBrains (Toolbox)"

    # Check config directories (IDE was used at some point)
    config_dir = Path.home() / "Library" / "Application Support" / "JetBrains"
    if config_dir.exists():
        for ide in JETBRAINS_IDES:
            if list(config_dir.glob(f"{ide}*")):
                return ide

    return None


def _detect_linux_installed() -> str | None:
    """Check Linux paths for JetBrains IDEs."""
    # Toolbox managed
    toolbox_dir = Path.home() / ".local" / "share" / "JetBrains" / "Toolbox" / "apps"
    if toolbox_dir.exists() and any(toolbox_dir.iterdir()):
        return "JetBrains (Toolbox)"

    # Config directories
    config_dir = Path.home() / ".config" / "JetBrains"
    if config_dir.exists():
        for ide in JETBRAINS_IDES:
            if list(config_dir.glob(f"{ide}*")):
                return ide

    # Common install locations
    common_dirs = [
        Path("/opt"),
        Path("/usr/local"),
        Path("/snap"),
        Path.home() / ".local" / "share",
    ]
    for base in common_dirs:
        if not base.exists():
            continue
        for ide in JETBRAINS_IDES:
            if list(base.glob(f"*{ide.lower()}*")) or list(base.glob(f"*{ide}*")):
                return ide

    return None

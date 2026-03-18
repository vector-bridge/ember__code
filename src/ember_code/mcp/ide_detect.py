"""Base class for IDE detection and MCP configuration.

Provides shared logic for checking existing MCP configs, writing new ones,
and orchestrating detect-then-configure flows. Subclasses only need to
implement :meth:`detect` with IDE-specific discovery logic.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class IDEDetector:
    """Base class for IDE detection and MCP configuration."""

    def __init__(self, name: str, mcp_config: dict) -> None:
        self._name = name
        self._mcp_config = mcp_config

    @property
    def name(self) -> str:
        return self._name

    def detect(self) -> str | None:
        """Detect if the IDE is installed/running. Override in subclass."""
        raise NotImplementedError

    def has_config(self, project_dir: Path) -> bool:
        """Check if an MCP entry for this IDE already exists in any .mcp.json."""
        paths = [
            project_dir / ".ember" / ".mcp.json",
            project_dir / ".mcp.json",
            Path.home() / ".ember" / ".mcp.json",
        ]
        for path in paths:
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text())
                if self._name in data.get("mcpServers", {}):
                    return True
            except (json.JSONDecodeError, OSError):
                continue
        return False

    def write_config(self, project_dir: Path) -> None:
        """Write MCP entry to the project's .ember/.mcp.json."""
        ember_dir = project_dir / ".ember"
        ember_dir.mkdir(parents=True, exist_ok=True)
        mcp_path = ember_dir / ".mcp.json"

        data: dict = {}
        if mcp_path.exists():
            try:
                data = json.loads(mcp_path.read_text())
            except (json.JSONDecodeError, OSError):
                data = {}

        servers = data.setdefault("mcpServers", {})
        servers[self._name] = self._mcp_config

        mcp_path.write_text(json.dumps(data, indent=2) + "\n")
        logger.info("Wrote %s MCP config to %s", self._name, mcp_path)

    def ensure_mcp(self, project_dir: Path) -> bool:
        """Auto-configure if IDE detected. Returns True if config written."""
        if self.has_config(project_dir):
            return False

        ide = self.detect()
        if not ide:
            return False

        logger.info("Detected %s (%s) — adding MCP configuration", self._name, ide)
        self.write_config(project_dir)
        return True

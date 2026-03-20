"""MCP integration — Model Context Protocol server and client."""

from ember_code.mcp.client import MCPClientManager
from ember_code.mcp.config import MCPConfigLoader, MCPServerConfig
from ember_code.mcp.server import MCPServerFactory
from ember_code.mcp.tools import MCPToolProvider

__all__ = [
    "MCPServerFactory",
    "MCPClientManager",
    "MCPConfigLoader",
    "MCPServerConfig",
    "MCPToolProvider",
]

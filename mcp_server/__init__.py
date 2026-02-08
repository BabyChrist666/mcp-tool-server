"""
MCP Tool Server - Production MCP server with file, shell, and search tools.

The Model Context Protocol (MCP) enables AI assistants to interact with
external tools and data sources through a standardized interface.
"""

from .protocol import (
    MCPMessage,
    MCPRequest,
    MCPResponse,
    MCPError,
    MCPErrorCode,
    Tool,
    ToolParameter,
    ToolResult,
)
from .server import MCPServer, ServerConfig
from .tools import (
    BaseTool,
    FileReadTool,
    FileWriteTool,
    ShellTool,
    SearchTool,
    GlobTool,
    ToolRegistry,
)
from .transport import (
    Transport,
    StdioTransport,
    WebSocketTransport,
)

__version__ = "0.1.0"

__all__ = [
    # Protocol
    "MCPMessage",
    "MCPRequest",
    "MCPResponse",
    "MCPError",
    "MCPErrorCode",
    "Tool",
    "ToolParameter",
    "ToolResult",
    # Server
    "MCPServer",
    "ServerConfig",
    # Tools
    "BaseTool",
    "FileReadTool",
    "FileWriteTool",
    "ShellTool",
    "SearchTool",
    "GlobTool",
    "ToolRegistry",
    # Transport
    "Transport",
    "StdioTransport",
    "WebSocketTransport",
]

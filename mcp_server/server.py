"""
MCP Server implementation.

Main server that handles MCP protocol, tool execution, and lifecycle management.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .protocol import (
    MCPRequest,
    MCPResponse,
    MCPError,
    MCPErrorCode,
    ToolResult,
    parse_message,
)
from .tools import ToolRegistry, BaseTool
from .transport import Transport, StdioTransport


logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """Configuration for MCP server."""
    name: str = "mcp-tool-server"
    version: str = "0.1.0"
    allowed_paths: Optional[List[str]] = None
    enable_file_tools: bool = True
    enable_shell_tools: bool = True
    enable_search_tools: bool = True
    max_concurrent_requests: int = 10
    request_timeout: float = 60.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "enable_file_tools": self.enable_file_tools,
            "enable_shell_tools": self.enable_shell_tools,
            "enable_search_tools": self.enable_search_tools,
        }


class MCPServer:
    """
    MCP Server that handles tool registration, request processing, and lifecycle.
    """

    def __init__(
        self,
        config: Optional[ServerConfig] = None,
        registry: Optional[ToolRegistry] = None,
    ):
        self.config = config or ServerConfig()
        self.registry = registry or ToolRegistry()
        self._transport: Optional[Transport] = None
        self._running = False
        self._handlers: Dict[str, Callable] = {}
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

        # Register default handlers
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register built-in MCP method handlers."""
        self._handlers["initialize"] = self._handle_initialize
        self._handlers["initialized"] = self._handle_initialized
        self._handlers["tools/list"] = self._handle_list_tools
        self._handlers["tools/call"] = self._handle_call_tool
        self._handlers["shutdown"] = self._handle_shutdown
        self._handlers["ping"] = self._handle_ping

    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool with the server."""
        self.registry.register(tool)

    def register_handler(self, method: str, handler: Callable) -> None:
        """Register a custom method handler."""
        self._handlers[method] = handler

    async def _handle_initialize(self, params: Optional[dict]) -> dict:
        """Handle initialize request."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": True},
            },
            "serverInfo": {
                "name": self.config.name,
                "version": self.config.version,
            },
        }

    async def _handle_initialized(self, params: Optional[dict]) -> dict:
        """Handle initialized notification."""
        logger.info("Client initialized")
        return {}

    async def _handle_list_tools(self, params: Optional[dict]) -> dict:
        """Handle tools/list request."""
        tools = self.registry.list_tools()
        return {
            "tools": [t.to_dict() for t in tools],
        }

    async def _handle_call_tool(self, params: Optional[dict]) -> dict:
        """Handle tools/call request."""
        if not params:
            return {
                "content": [{"type": "text", "text": "Error: Missing parameters"}],
                "isError": True,
            }

        name = params.get("name")
        arguments = params.get("arguments", {})

        if not name:
            return {
                "content": [{"type": "text", "text": "Error: Missing tool name"}],
                "isError": True,
            }

        result = self.registry.execute(name, arguments)

        if not result.success:
            return {
                "content": [
                    {"type": "text", "text": f"Error: {result.error}"}
                ],
                "isError": True,
            }

        # Format content based on type
        if result.content_type == "json":
            import json
            content_text = json.dumps(result.content, indent=2)
        else:
            content_text = str(result.content)

        return {
            "content": [
                {"type": "text", "text": content_text}
            ],
        }

    async def _handle_shutdown(self, params: Optional[dict]) -> dict:
        """Handle shutdown request."""
        logger.info("Shutdown requested")
        self._running = False
        return {}

    async def _handle_ping(self, params: Optional[dict]) -> dict:
        """Handle ping request."""
        return {"pong": True}

    async def process_request(self, request: MCPRequest) -> MCPResponse:
        """Process a single MCP request."""
        handler = self._handlers.get(request.method)

        if handler is None:
            error = MCPError.from_code(
                MCPErrorCode.METHOD_NOT_FOUND,
                f"Unknown method: {request.method}",
            )
            return MCPResponse.failure(request.id, error)

        try:
            async with self._semaphore:
                result = await asyncio.wait_for(
                    handler(request.params),
                    timeout=self.config.request_timeout,
                )
                return MCPResponse.success(request.id, result)
        except asyncio.TimeoutError:
            error = MCPError.from_code(
                MCPErrorCode.TIMEOUT,
                f"Request timed out after {self.config.request_timeout}s",
            )
            return MCPResponse.failure(request.id, error)
        except Exception as e:
            logger.exception(f"Error processing request: {e}")
            error = MCPError.from_code(
                MCPErrorCode.INTERNAL_ERROR,
                str(e),
            )
            return MCPResponse.failure(request.id, error)

    async def handle_message(self, data: dict) -> Optional[dict]:
        """Handle an incoming message."""
        try:
            message = parse_message(data)

            if isinstance(message, MCPRequest):
                response = await self.process_request(message)
                return response.to_dict()

            return None
        except Exception as e:
            logger.exception(f"Error handling message: {e}")
            error = MCPError.from_code(
                MCPErrorCode.INTERNAL_ERROR,
                str(e),
            )
            return MCPResponse.failure(data.get("id"), error).to_dict()

    async def run(self, transport: Optional[Transport] = None) -> None:
        """Run the server main loop."""
        self._transport = transport or StdioTransport()
        self._running = True

        logger.info(f"MCP Server {self.config.name} v{self.config.version} starting")

        try:
            async with self._transport:
                while self._running:
                    try:
                        message = await self._transport.receive()

                        if message is None:
                            logger.info("EOF received, shutting down")
                            break

                        response = await self.handle_message(message)

                        if response is not None:
                            await self._transport.send(response)
                    except ValueError as e:
                        logger.error(f"Parse error: {e}")
                        error_response = MCPResponse.failure(
                            None,
                            MCPError.from_code(MCPErrorCode.PARSE_ERROR, str(e)),
                        )
                        await self._transport.send(error_response.to_dict())
                    except Exception as e:
                        logger.exception(f"Error in main loop: {e}")
        finally:
            self._running = False
            logger.info("Server stopped")

    def stop(self) -> None:
        """Signal the server to stop."""
        self._running = False


def create_server(
    config: Optional[ServerConfig] = None,
    tools: Optional[List[BaseTool]] = None,
) -> MCPServer:
    """
    Create an MCP server with configuration and tools.

    Args:
        config: Server configuration
        tools: List of tools to register

    Returns:
        Configured MCPServer instance
    """
    config = config or ServerConfig()
    server = MCPServer(config)

    # Register default tools based on config
    if config.enable_file_tools:
        from .tools import FileReadTool, FileWriteTool
        server.register_tool(FileReadTool(allowed_paths=config.allowed_paths))
        server.register_tool(FileWriteTool(allowed_paths=config.allowed_paths))

    if config.enable_search_tools:
        from .tools import SearchTool, GlobTool
        server.register_tool(SearchTool(allowed_paths=config.allowed_paths))
        server.register_tool(GlobTool(allowed_paths=config.allowed_paths))

    if config.enable_shell_tools:
        from .tools import ShellTool
        server.register_tool(ShellTool())

    # Register custom tools
    if tools:
        for tool in tools:
            server.register_tool(tool)

    return server

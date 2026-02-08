"""Tests for mcp_server.server module."""

import pytest
import asyncio

from mcp_server.server import MCPServer, ServerConfig, create_server
from mcp_server.protocol import MCPRequest, MCPResponse, MCPError, MCPErrorCode
from mcp_server.tools import BaseTool, ToolRegistry, FileReadTool
from mcp_server.protocol import ToolParameter, ToolResult


class EchoTool(BaseTool):
    """Simple echo tool for testing."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo the input"

    @property
    def parameters(self):
        return [
            ToolParameter("message", "string", "Message to echo", required=True),
        ]

    def execute(self, message: str) -> ToolResult:
        return ToolResult(success=True, content=message)


class TestServerConfig:
    def test_defaults(self):
        config = ServerConfig()
        assert config.name == "mcp-tool-server"
        assert config.enable_file_tools is True
        assert config.enable_shell_tools is True

    def test_custom_config(self):
        config = ServerConfig(
            name="custom-server",
            enable_shell_tools=False,
            allowed_paths=["/home/user"],
        )
        assert config.name == "custom-server"
        assert config.enable_shell_tools is False
        assert config.allowed_paths == ["/home/user"]

    def test_to_dict(self):
        config = ServerConfig()
        d = config.to_dict()
        assert d["name"] == "mcp-tool-server"
        assert d["version"] == "0.1.0"


class TestMCPServer:
    def test_create(self):
        server = MCPServer()
        assert server.config is not None
        assert server.registry is not None

    def test_create_with_config(self):
        config = ServerConfig(name="test-server")
        server = MCPServer(config=config)
        assert server.config.name == "test-server"

    def test_register_tool(self):
        server = MCPServer()
        tool = EchoTool()
        server.register_tool(tool)
        assert server.registry.get("echo") is tool

    def test_register_handler(self):
        server = MCPServer()

        async def custom_handler(params):
            return {"custom": "result"}

        server.register_handler("custom/method", custom_handler)
        assert "custom/method" in server._handlers

    @pytest.mark.asyncio
    async def test_handle_initialize(self):
        server = MCPServer()
        request = MCPRequest(id="1", method="initialize", params={})
        response = await server.process_request(request)

        assert response.error is None
        assert "protocolVersion" in response.result
        assert "capabilities" in response.result
        assert "serverInfo" in response.result

    @pytest.mark.asyncio
    async def test_handle_ping(self):
        server = MCPServer()
        request = MCPRequest(id="1", method="ping")
        response = await server.process_request(request)

        assert response.error is None
        assert response.result["pong"] is True

    @pytest.mark.asyncio
    async def test_handle_list_tools(self):
        server = MCPServer()
        server.register_tool(EchoTool())
        request = MCPRequest(id="1", method="tools/list")
        response = await server.process_request(request)

        assert response.error is None
        assert "tools" in response.result
        tool_names = [t["name"] for t in response.result["tools"]]
        assert "echo" in tool_names

    @pytest.mark.asyncio
    async def test_handle_call_tool(self):
        server = MCPServer()
        server.register_tool(EchoTool())

        request = MCPRequest(
            id="1",
            method="tools/call",
            params={"name": "echo", "arguments": {"message": "hello"}},
        )
        response = await server.process_request(request)

        assert response.error is None
        assert "content" in response.result
        assert response.result["content"][0]["text"] == "hello"

    @pytest.mark.asyncio
    async def test_handle_call_tool_missing_name(self):
        server = MCPServer()
        request = MCPRequest(
            id="1",
            method="tools/call",
            params={"arguments": {}},
        )
        response = await server.process_request(request)

        # Missing name returns isError in result, not protocol error
        assert response.result.get("isError") is True

    @pytest.mark.asyncio
    async def test_handle_call_tool_not_found(self):
        server = MCPServer()
        request = MCPRequest(
            id="1",
            method="tools/call",
            params={"name": "nonexistent", "arguments": {}},
        )
        response = await server.process_request(request)

        # Tool not found returns isError in result, not protocol error
        assert response.result.get("isError") is True

    @pytest.mark.asyncio
    async def test_handle_unknown_method(self):
        server = MCPServer()
        request = MCPRequest(id="1", method="unknown/method")
        response = await server.process_request(request)

        assert response.error is not None
        assert response.error.code == MCPErrorCode.METHOD_NOT_FOUND.value

    @pytest.mark.asyncio
    async def test_handle_shutdown(self):
        server = MCPServer()
        request = MCPRequest(id="1", method="shutdown")
        response = await server.process_request(request)

        assert response.error is None
        assert server._running is False

    @pytest.mark.asyncio
    async def test_handle_message(self):
        server = MCPServer()
        message = {"jsonrpc": "2.0", "id": "1", "method": "ping"}
        response = await server.handle_message(message)

        assert response is not None
        assert response["result"]["pong"] is True

    @pytest.mark.asyncio
    async def test_handle_message_error(self):
        server = MCPServer()
        message = {"jsonrpc": "2.0", "id": "1", "method": "unknown"}
        response = await server.handle_message(message)

        assert "error" in response

    def test_stop(self):
        server = MCPServer()
        server._running = True
        server.stop()
        assert server._running is False


class TestCreateServer:
    def test_create_default(self):
        server = create_server()
        assert "file_read" in server.registry.tools
        assert "file_write" in server.registry.tools
        assert "shell" in server.registry.tools
        assert "search" in server.registry.tools
        assert "glob" in server.registry.tools

    def test_create_without_shell(self):
        config = ServerConfig(enable_shell_tools=False)
        server = create_server(config=config)
        assert "shell" not in server.registry.tools

    def test_create_without_file_tools(self):
        config = ServerConfig(enable_file_tools=False)
        server = create_server(config=config)
        assert "file_read" not in server.registry.tools
        assert "file_write" not in server.registry.tools

    def test_create_without_search_tools(self):
        config = ServerConfig(enable_search_tools=False)
        server = create_server(config=config)
        assert "search" not in server.registry.tools
        assert "glob" not in server.registry.tools

    def test_create_with_custom_tools(self):
        server = create_server(
            config=ServerConfig(
                enable_file_tools=False,
                enable_shell_tools=False,
                enable_search_tools=False,
            ),
            tools=[EchoTool()],
        )
        assert "echo" in server.registry.tools
        assert len(server.registry.tools) == 1

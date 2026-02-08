"""Tests for mcp_server.protocol module."""

import pytest
import json

from mcp_server.protocol import (
    MCPMessage,
    MCPRequest,
    MCPResponse,
    MCPError,
    MCPErrorCode,
    Tool,
    ToolParameter,
    ToolResult,
    generate_id,
    parse_message,
)


class TestMCPError:
    def test_create(self):
        error = MCPError(code=-32600, message="Invalid Request")
        assert error.code == -32600
        assert error.message == "Invalid Request"

    def test_from_code(self):
        error = MCPError.from_code(MCPErrorCode.PARSE_ERROR, "Parse failed")
        assert error.code == -32700
        assert error.message == "Parse failed"

    def test_to_dict(self):
        error = MCPError(code=-32600, message="Test", data={"detail": "info"})
        d = error.to_dict()
        assert d["code"] == -32600
        assert d["message"] == "Test"
        assert d["data"]["detail"] == "info"

    def test_to_dict_no_data(self):
        error = MCPError(code=-32600, message="Test")
        d = error.to_dict()
        assert "data" not in d


class TestMCPMessage:
    def test_create(self):
        msg = MCPMessage(id="test-123")
        assert msg.jsonrpc == "2.0"
        assert msg.id == "test-123"

    def test_to_dict(self):
        msg = MCPMessage(id="abc")
        d = msg.to_dict()
        assert d["jsonrpc"] == "2.0"
        assert d["id"] == "abc"

    def test_to_json(self):
        msg = MCPMessage(id="test")
        j = msg.to_json()
        assert '"jsonrpc": "2.0"' in j

    def test_from_dict(self):
        msg = MCPMessage.from_dict({"jsonrpc": "2.0", "id": "xyz"})
        assert msg.id == "xyz"


class TestMCPRequest:
    def test_create(self):
        req = MCPRequest(id="1", method="tools/list", params={"foo": "bar"})
        assert req.method == "tools/list"
        assert req.params["foo"] == "bar"

    def test_to_dict(self):
        req = MCPRequest(id="1", method="test")
        d = req.to_dict()
        assert d["method"] == "test"
        assert d["id"] == "1"

    def test_from_dict(self):
        req = MCPRequest.from_dict({
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/call",
            "params": {"name": "test"},
        })
        assert req.method == "tools/call"
        assert req.params["name"] == "test"

    def test_from_json(self):
        json_str = '{"jsonrpc": "2.0", "id": "1", "method": "ping"}'
        req = MCPRequest.from_json(json_str)
        assert req.method == "ping"


class TestMCPResponse:
    def test_success(self):
        resp = MCPResponse.success("1", {"result": "ok"})
        assert resp.id == "1"
        assert resp.result["result"] == "ok"
        assert resp.error is None

    def test_failure(self):
        error = MCPError(code=-32600, message="Error")
        resp = MCPResponse.failure("1", error)
        assert resp.id == "1"
        assert resp.error.code == -32600

    def test_to_dict_success(self):
        resp = MCPResponse.success("1", "result")
        d = resp.to_dict()
        assert d["result"] == "result"
        assert "error" not in d

    def test_to_dict_failure(self):
        error = MCPError(code=-32600, message="Error")
        resp = MCPResponse.failure("1", error)
        d = resp.to_dict()
        assert d["error"]["code"] == -32600
        assert "result" not in d


class TestToolParameter:
    def test_create(self):
        param = ToolParameter(
            name="path",
            type="string",
            description="File path",
            required=True,
        )
        assert param.name == "path"
        assert param.required is True

    def test_to_dict(self):
        param = ToolParameter(
            name="mode",
            type="string",
            description="Mode",
            enum=["read", "write"],
        )
        d = param.to_dict()
        assert d["name"] == "mode"
        assert d["enum"] == ["read", "write"]

    def test_to_json_schema(self):
        param = ToolParameter(
            name="count",
            type="integer",
            description="Count",
            default=10,
        )
        schema = param.to_json_schema()
        assert schema["type"] == "integer"
        assert schema["default"] == 10


class TestTool:
    def test_create(self):
        tool = Tool(name="test", description="Test tool")
        assert tool.name == "test"

    def test_to_dict(self):
        tool = Tool(
            name="file_read",
            description="Read a file",
            parameters=[
                ToolParameter("path", "string", "File path", required=True),
            ],
        )
        d = tool.to_dict()
        assert d["name"] == "file_read"
        assert d["inputSchema"]["type"] == "object"
        assert "path" in d["inputSchema"]["properties"]
        assert "path" in d["inputSchema"]["required"]


class TestToolResult:
    def test_success_result(self):
        result = ToolResult(
            success=True,
            content="file contents",
            metadata={"size": 100},
        )
        assert result.success is True
        assert result.content == "file contents"

    def test_error_result(self):
        result = ToolResult(
            success=False,
            content="",
            error="File not found",
        )
        assert result.success is False
        assert result.error == "File not found"

    def test_to_dict(self):
        result = ToolResult(
            success=True,
            content="data",
            content_type="json",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["content_type"] == "json"


class TestHelpers:
    def test_generate_id(self):
        id1 = generate_id()
        id2 = generate_id()
        assert id1 != id2
        assert len(id1) > 0

    def test_parse_message_request(self):
        data = {"jsonrpc": "2.0", "id": "1", "method": "ping"}
        msg = parse_message(data)
        assert isinstance(msg, MCPRequest)
        assert msg.method == "ping"

    def test_parse_message_response(self):
        data = {"jsonrpc": "2.0", "id": "1", "result": "pong"}
        msg = parse_message(data)
        assert isinstance(msg, MCPResponse)

    def test_parse_message_from_string(self):
        json_str = '{"jsonrpc": "2.0", "id": "1", "method": "test"}'
        msg = parse_message(json_str)
        assert isinstance(msg, MCPRequest)

    def test_parse_message_invalid_json(self):
        with pytest.raises(ValueError):
            parse_message("not valid json")

    def test_parse_message_not_object(self):
        with pytest.raises(ValueError):
            parse_message([1, 2, 3])

"""
MCP Protocol definitions.

Implements the Model Context Protocol message types and structures.
"""

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class MCPErrorCode(Enum):
    """Standard MCP error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    # Custom error codes
    TOOL_NOT_FOUND = -32000
    TOOL_EXECUTION_ERROR = -32001
    PERMISSION_DENIED = -32002
    TIMEOUT = -32003


@dataclass
class MCPError:
    """MCP Error object."""
    code: int
    message: str
    data: Optional[Any] = None

    @classmethod
    def from_code(cls, code: MCPErrorCode, message: str, data: Any = None) -> "MCPError":
        return cls(code=code.value, message=message, data=data)

    def to_dict(self) -> dict:
        result = {"code": self.code, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result


@dataclass
class MCPMessage:
    """Base MCP message."""
    jsonrpc: str = "2.0"
    id: Optional[str] = None

    def to_dict(self) -> dict:
        result = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            result["id"] = self.id
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "MCPMessage":
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
        )


@dataclass
class MCPRequest(MCPMessage):
    """MCP Request message."""
    method: str = ""
    params: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["method"] = self.method
        if self.params is not None:
            result["params"] = self.params
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "MCPRequest":
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method", ""),
            params=data.get("params"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "MCPRequest":
        return cls.from_dict(json.loads(json_str))


@dataclass
class MCPResponse(MCPMessage):
    """MCP Response message."""
    result: Optional[Any] = None
    error: Optional[MCPError] = None

    def to_dict(self) -> dict:
        result = super().to_dict()
        if self.error is not None:
            result["error"] = self.error.to_dict()
        else:
            result["result"] = self.result
        return result

    @classmethod
    def success(cls, id: str, result: Any) -> "MCPResponse":
        return cls(id=id, result=result)

    @classmethod
    def failure(cls, id: str, error: MCPError) -> "MCPResponse":
        return cls(id=id, error=error)


@dataclass
class ToolParameter:
    """Tool parameter definition."""
    name: str
    type: str
    description: str
    required: bool = False
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None

    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }
        if self.default is not None:
            result["default"] = self.default
        if self.enum is not None:
            result["enum"] = self.enum
        return result

    def to_json_schema(self) -> dict:
        """Convert to JSON schema property."""
        schema = {
            "type": self.type,
            "description": self.description,
        }
        if self.enum is not None:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        return schema


@dataclass
class Tool:
    """Tool definition for MCP."""
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to MCP tool definition format."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    content: Any
    content_type: str = "text"
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        result = {
            "success": self.success,
            "content": self.content,
            "content_type": self.content_type,
        }
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result


def generate_id() -> str:
    """Generate a unique message ID."""
    return str(uuid.uuid4())


def parse_message(data: Union[str, dict]) -> MCPMessage:
    """Parse a raw message into an MCP message object."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

    if not isinstance(data, dict):
        raise ValueError("Message must be a JSON object")

    if "method" in data:
        return MCPRequest.from_dict(data)
    elif "result" in data or "error" in data:
        return MCPResponse.from_dict(data)
    else:
        return MCPMessage.from_dict(data)

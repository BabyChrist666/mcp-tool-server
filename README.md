# MCP Tool Server

[![Tests](https://github.com/BabyChrist666/mcp-tool-server/actions/workflows/tests.yml/badge.svg)](https://github.com/BabyChrist666/mcp-tool-server/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/BabyChrist666/mcp-tool-server/branch/master/graph/badge.svg)](https://codecov.io/gh/BabyChrist666/mcp-tool-server)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Production-ready Model Context Protocol (MCP) server with file, shell, and search tools.

MCP enables AI assistants to interact with external tools and data sources through a standardized interface. This server provides a complete implementation with built-in tools for common operations.

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```python
import asyncio
from mcp_server import MCPServer, ServerConfig, create_server

# Create server with default tools
server = create_server()

# Or customize configuration
config = ServerConfig(
    name="my-mcp-server",
    allowed_paths=["/home/user/projects"],
    enable_shell_tools=True,
)
server = create_server(config=config)

# Run the server
asyncio.run(server.run())
```

## Built-in Tools

### file_read
Read file contents with path restrictions and size limits.

```json
{
  "name": "file_read",
  "arguments": {
    "path": "/path/to/file.txt",
    "encoding": "utf-8"
  }
}
```

### file_write
Write or append content to files.

```json
{
  "name": "file_write",
  "arguments": {
    "path": "/path/to/file.txt",
    "content": "Hello, world!",
    "mode": "write"
  }
}
```

### shell
Execute shell commands with security controls.

```json
{
  "name": "shell",
  "arguments": {
    "command": "ls -la",
    "timeout": 30
  }
}
```

### search
Search for patterns in files (grep-like).

```json
{
  "name": "search",
  "arguments": {
    "pattern": "TODO",
    "path": "/path/to/project",
    "include": "*.py",
    "ignore_case": true
  }
}
```

### glob
Find files matching a glob pattern.

```json
{
  "name": "glob",
  "arguments": {
    "pattern": "**/*.py",
    "path": "/path/to/project"
  }
}
```

## Custom Tools

Create your own tools by extending `BaseTool`:

```python
from mcp_server import BaseTool, ToolParameter, ToolResult

class WeatherTool(BaseTool):
    @property
    def name(self) -> str:
        return "weather"

    @property
    def description(self) -> str:
        return "Get current weather for a location"

    @property
    def parameters(self):
        return [
            ToolParameter("location", "string", "City name", required=True),
        ]

    def execute(self, location: str) -> ToolResult:
        # Your implementation here
        return ToolResult(
            success=True,
            content=f"Weather for {location}: Sunny, 72F",
        )

# Register with server
server.register_tool(WeatherTool())
```

## Transport Options

### Stdio (Default)
Communication via stdin/stdout with JSON-RPC framing:

```python
from mcp_server import StdioTransport

transport = StdioTransport()
await server.run(transport)
```

### WebSocket
For web-based integrations:

```python
from mcp_server import WebSocketTransport

# Requires a WebSocket connection (e.g., from websockets library)
transport = WebSocketTransport(websocket)
await server.run(transport)
```

## Security Features

### Path Restrictions
Limit file operations to specific directories:

```python
config = ServerConfig(
    allowed_paths=["/home/user/projects", "/tmp"],
)
```

### Command Filtering
Block dangerous shell commands:

```python
from mcp_server import ShellTool

tool = ShellTool(
    blocked_commands=["rm -rf /", "mkfs"],
    allowed_commands=["ls", "cat", "grep"],  # Whitelist mode
    timeout=30,
)
```

### Request Limits
Control concurrent requests and timeouts:

```python
config = ServerConfig(
    max_concurrent_requests=10,
    request_timeout=60.0,
)
```

## Protocol

Implements MCP with JSON-RPC 2.0:

```json
// Request
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "tools/call",
  "params": {
    "name": "file_read",
    "arguments": {"path": "/etc/hostname"}
  }
}

// Response
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "content": [{"type": "text", "text": "myhost\n"}]
  }
}
```

### Standard Methods

| Method | Description |
|--------|-------------|
| `initialize` | Initialize connection, exchange capabilities |
| `initialized` | Client notification after init complete |
| `tools/list` | List available tools |
| `tools/call` | Execute a tool |
| `shutdown` | Request server shutdown |
| `ping` | Health check |

## Testing

```bash
pytest tests/ -v
```

112 tests covering:
- Protocol message parsing and serialization
- Tool execution and validation
- Transport layer (stdio, websocket)
- Server lifecycle and request handling

## License

MIT

"""
Demo: MCP Tool Server

This experiment demonstrates how to create and run an MCP server
with various tools, and how to handle requests.
"""

import asyncio
import json
import sys
sys.path.insert(0, "..")

from mcp_server import (
    MCPServer,
    ServerConfig,
    create_server,
    MCPRequest,
    BaseTool,
    ToolParameter,
    ToolResult,
)


class CalculatorTool(BaseTool):
    """Simple calculator tool for demonstration."""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Perform basic arithmetic operations"

    @property
    def parameters(self):
        return [
            ToolParameter("operation", "string", "Operation: add, sub, mul, div", required=True),
            ToolParameter("a", "number", "First number", required=True),
            ToolParameter("b", "number", "Second number", required=True),
        ]

    def execute(self, operation: str, a: float, b: float) -> ToolResult:
        ops = {
            "add": lambda x, y: x + y,
            "sub": lambda x, y: x - y,
            "mul": lambda x, y: x * y,
            "div": lambda x, y: x / y if y != 0 else float('inf'),
        }

        if operation not in ops:
            return ToolResult(
                success=False,
                content="",
                error=f"Unknown operation: {operation}",
            )

        result = ops[operation](a, b)
        return ToolResult(
            success=True,
            content=f"{a} {operation} {b} = {result}",
        )


async def main():
    print("=" * 60)
    print("MCP TOOL SERVER DEMO")
    print("=" * 60)
    print()

    # Create server with configuration
    print("[1] Creating server with default tools...")
    config = ServerConfig(
        name="demo-mcp-server",
        version="1.0.0",
        enable_file_tools=True,
        enable_shell_tools=True,
        enable_search_tools=True,
    )
    server = create_server(config=config)
    print(f"    Server: {config.name} v{config.version}")
    print()

    # Register custom tool
    print("[2] Registering custom calculator tool...")
    server.register_tool(CalculatorTool())
    print()

    # List all tools
    print("[3] Available tools:")
    print("-" * 40)
    tools = server.registry.list_tools()
    for tool in tools:
        print(f"    {tool.name}: {tool.description}")
    print()

    # Simulate some requests
    print("[4] Simulating MCP requests:")
    print("-" * 40)

    # Test ping
    request = MCPRequest(id="1", method="ping")
    response = await server.process_request(request)
    print(f"    ping -> {json.dumps(response.result)}")

    # Test initialize
    request = MCPRequest(id="2", method="initialize")
    response = await server.process_request(request)
    print(f"    initialize -> protocol: {response.result['protocolVersion']}")

    # Test tools/list
    request = MCPRequest(id="3", method="tools/list")
    response = await server.process_request(request)
    print(f"    tools/list -> {len(response.result['tools'])} tools")

    # Test calculator tool
    request = MCPRequest(
        id="4",
        method="tools/call",
        params={
            "name": "calculator",
            "arguments": {"operation": "mul", "a": 7, "b": 6},
        },
    )
    response = await server.process_request(request)
    print(f"    calculator(7*6) -> {response.result['content'][0]['text']}")

    # Test shell tool
    request = MCPRequest(
        id="5",
        method="tools/call",
        params={
            "name": "shell",
            "arguments": {"command": "echo Hello MCP!"},
        },
    )
    response = await server.process_request(request)
    output = response.result['content'][0]['text'].strip()
    print(f"    shell(echo) -> {output}")

    print()

    # Show protocol format
    print("[5] Example protocol message:")
    print("-" * 40)
    example = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {
            "name": "file_read",
            "arguments": {"path": "/etc/hostname"},
        },
    }
    print(json.dumps(example, indent=2))
    print()

    print("=" * 60)
    print("Demo complete!")
    print()
    print("To run as a real server:")
    print("  asyncio.run(server.run())")
    print()
    print("The server will communicate via stdin/stdout")
    print("using JSON-RPC with Content-Length headers.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

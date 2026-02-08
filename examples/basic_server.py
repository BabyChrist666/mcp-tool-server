#!/usr/bin/env python3
"""
Basic MCP Tool Server Example

This example demonstrates how to create a simple MCP server
with file, shell, and search tools.
"""

import asyncio
from mcp_tool_server import (
    MCPServer,
    ServerConfig,
    Tool,
    ToolRegistry,
)


def setup_basic_tools():
    """Set up basic tools for the server."""
    registry = ToolRegistry()

    @registry.register("read_file")
    async def read_file(path: str) -> str:
        """Read contents of a file."""
        try:
            with open(path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return f"Error: File not found: {path}"
        except Exception as e:
            return f"Error reading file: {e}"

    @registry.register("write_file")
    async def write_file(path: str, content: str) -> str:
        """Write content to a file."""
        try:
            with open(path, 'w') as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to {path}"
        except Exception as e:
            return f"Error writing file: {e}"

    @registry.register("list_directory")
    async def list_directory(path: str = ".") -> str:
        """List contents of a directory."""
        import os
        try:
            items = os.listdir(path)
            return "\n".join(items)
        except Exception as e:
            return f"Error listing directory: {e}"

    @registry.register("run_command")
    async def run_command(command: str) -> str:
        """Run a shell command (sandboxed)."""
        import subprocess

        # Whitelist safe commands
        allowed_commands = ['ls', 'pwd', 'echo', 'date', 'whoami', 'cat']
        cmd_parts = command.split()

        if not cmd_parts:
            return "Error: Empty command"

        if cmd_parts[0] not in allowed_commands:
            return f"Error: Command '{cmd_parts[0]}' not allowed"

        try:
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout or result.stderr
        except subprocess.TimeoutExpired:
            return "Error: Command timed out"
        except Exception as e:
            return f"Error running command: {e}"

    @registry.register("search_files")
    async def search_files(pattern: str, directory: str = ".") -> str:
        """Search for files matching a pattern."""
        import glob
        import os

        search_path = os.path.join(directory, "**", pattern)
        matches = glob.glob(search_path, recursive=True)

        if not matches:
            return f"No files matching '{pattern}' found"

        return "\n".join(matches[:20])  # Limit results

    return registry


async def main():
    print("=" * 60)
    print("MCP Tool Server - Basic Example")
    print("=" * 60)

    # Configure server
    config = ServerConfig(
        name="basic-tool-server",
        version="1.0.0",
        description="A basic MCP server with file and shell tools",
        host="localhost",
        port=8080,
    )

    # Create server with tools
    tools = setup_basic_tools()
    server = MCPServer(config, tools=tools)

    # List available tools
    print("\nAvailable tools:")
    for tool in server.list_tools():
        print(f"  - {tool.name}: {tool.description}")

    # Test tools locally
    print("\n" + "-" * 60)
    print("Testing tools locally...")
    print("-" * 60)

    # Test read_file
    result = await server.call_tool("list_directory", {"path": "."})
    print(f"\nlist_directory('.'):\n{result[:200]}...")

    # Test run_command
    result = await server.call_tool("run_command", {"command": "echo Hello, MCP!"})
    print(f"\nrun_command('echo Hello, MCP!'): {result}")

    # Start server
    print("\n" + "-" * 60)
    print("Starting MCP server...")
    print("-" * 60)
    print(f"Server running at http://{config.host}:{config.port}")
    print("Press Ctrl+C to stop")

    # Uncomment to actually run the server:
    # await server.start()


if __name__ == "__main__":
    asyncio.run(main())

"""
MCP Tools implementation.

Provides built-in tools for file operations, shell commands, and search.
"""

import os
import subprocess
import fnmatch
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type
from pathlib import Path

from .protocol import Tool, ToolParameter, ToolResult


class BaseTool(ABC):
    """Base class for MCP tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> List[ToolParameter]:
        """Tool parameters."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    def get_definition(self) -> Tool:
        """Get the MCP tool definition."""
        return Tool(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate parameters. Returns error message if invalid."""
        for param in self.parameters:
            if param.required and param.name not in params:
                return f"Missing required parameter: {param.name}"
        return None


class FileReadTool(BaseTool):
    """Read file contents."""

    def __init__(self, allowed_paths: Optional[List[str]] = None, max_size: int = 10_000_000):
        self.allowed_paths = allowed_paths
        self.max_size = max_size

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return "Read the contents of a file"

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path to the file to read",
                required=True,
            ),
            ToolParameter(
                name="encoding",
                type="string",
                description="File encoding (default: utf-8)",
                default="utf-8",
            ),
        ]

    def _is_path_allowed(self, path: str) -> bool:
        """Check if path is in allowed paths."""
        if self.allowed_paths is None:
            return True

        abs_path = os.path.abspath(path)
        for allowed in self.allowed_paths:
            allowed_abs = os.path.abspath(allowed)
            if abs_path.startswith(allowed_abs):
                return True
        return False

    def execute(self, path: str, encoding: str = "utf-8") -> ToolResult:
        if not self._is_path_allowed(path):
            return ToolResult(
                success=False,
                content="",
                error=f"Access denied: {path}",
            )

        if not os.path.exists(path):
            return ToolResult(
                success=False,
                content="",
                error=f"File not found: {path}",
            )

        if not os.path.isfile(path):
            return ToolResult(
                success=False,
                content="",
                error=f"Not a file: {path}",
            )

        file_size = os.path.getsize(path)
        if file_size > self.max_size:
            return ToolResult(
                success=False,
                content="",
                error=f"File too large: {file_size} bytes (max: {self.max_size})",
            )

        try:
            with open(path, "r", encoding=encoding) as f:
                content = f.read()
            return ToolResult(
                success=True,
                content=content,
                metadata={"size": file_size, "path": path},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=str(e),
            )


class FileWriteTool(BaseTool):
    """Write content to a file."""

    def __init__(self, allowed_paths: Optional[List[str]] = None):
        self.allowed_paths = allowed_paths

    @property
    def name(self) -> str:
        return "file_write"

    @property
    def description(self) -> str:
        return "Write content to a file"

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path to the file to write",
                required=True,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="Content to write",
                required=True,
            ),
            ToolParameter(
                name="mode",
                type="string",
                description="Write mode: 'write' (overwrite) or 'append'",
                default="write",
                enum=["write", "append"],
            ),
        ]

    def _is_path_allowed(self, path: str) -> bool:
        if self.allowed_paths is None:
            return True

        abs_path = os.path.abspath(path)
        for allowed in self.allowed_paths:
            allowed_abs = os.path.abspath(allowed)
            if abs_path.startswith(allowed_abs):
                return True
        return False

    def execute(
        self,
        path: str,
        content: str,
        mode: str = "write",
    ) -> ToolResult:
        if not self._is_path_allowed(path):
            return ToolResult(
                success=False,
                content="",
                error=f"Access denied: {path}",
            )

        file_mode = "w" if mode == "write" else "a"

        try:
            # Create parent directories if needed
            parent = os.path.dirname(path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent)

            with open(path, file_mode, encoding="utf-8") as f:
                f.write(content)

            return ToolResult(
                success=True,
                content=f"Written {len(content)} bytes to {path}",
                metadata={"path": path, "size": len(content)},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=str(e),
            )


class ShellTool(BaseTool):
    """Execute shell commands."""

    def __init__(
        self,
        allowed_commands: Optional[List[str]] = None,
        blocked_commands: Optional[List[str]] = None,
        timeout: int = 30,
        working_dir: Optional[str] = None,
    ):
        self.allowed_commands = allowed_commands
        self.blocked_commands = blocked_commands or ["rm -rf /", "mkfs", "dd if="]
        self.timeout = timeout
        self.working_dir = working_dir

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "Execute a shell command"

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="command",
                type="string",
                description="The command to execute",
                required=True,
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Timeout in seconds",
                default=self.timeout,
            ),
        ]

    def _is_command_allowed(self, command: str) -> bool:
        # Check blocked commands
        for blocked in self.blocked_commands:
            if blocked in command:
                return False

        # Check allowed commands if specified
        if self.allowed_commands is not None:
            cmd_parts = command.split()
            if not cmd_parts:
                return False
            base_cmd = cmd_parts[0]
            return base_cmd in self.allowed_commands

        return True

    def execute(self, command: str, timeout: Optional[int] = None) -> ToolResult:
        if not self._is_command_allowed(command):
            return ToolResult(
                success=False,
                content="",
                error=f"Command not allowed: {command}",
            )

        timeout = timeout or self.timeout

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.working_dir,
            )

            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"

            return ToolResult(
                success=result.returncode == 0,
                content=output,
                metadata={
                    "return_code": result.returncode,
                    "command": command,
                },
                error=result.stderr if result.returncode != 0 else None,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                content="",
                error=f"Command timed out after {timeout} seconds",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=str(e),
            )


class SearchTool(BaseTool):
    """Search for patterns in files."""

    def __init__(
        self,
        allowed_paths: Optional[List[str]] = None,
        max_results: int = 100,
    ):
        self.allowed_paths = allowed_paths
        self.max_results = max_results

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return "Search for a pattern in files (grep-like)"

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="pattern",
                type="string",
                description="Regex pattern to search for",
                required=True,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Directory or file to search in",
                required=True,
            ),
            ToolParameter(
                name="include",
                type="string",
                description="File pattern to include (e.g., '*.py')",
                default="*",
            ),
            ToolParameter(
                name="ignore_case",
                type="boolean",
                description="Case-insensitive search",
                default=False,
            ),
        ]

    def _is_path_allowed(self, path: str) -> bool:
        if self.allowed_paths is None:
            return True

        abs_path = os.path.abspath(path)
        for allowed in self.allowed_paths:
            allowed_abs = os.path.abspath(allowed)
            if abs_path.startswith(allowed_abs):
                return True
        return False

    def execute(
        self,
        pattern: str,
        path: str,
        include: str = "*",
        ignore_case: bool = False,
    ) -> ToolResult:
        if not self._is_path_allowed(path):
            return ToolResult(
                success=False,
                content="",
                error=f"Access denied: {path}",
            )

        if not os.path.exists(path):
            return ToolResult(
                success=False,
                content="",
                error=f"Path not found: {path}",
            )

        flags = re.IGNORECASE if ignore_case else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult(
                success=False,
                content="",
                error=f"Invalid regex: {e}",
            )

        matches = []

        def search_file(file_path: str):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            matches.append({
                                "file": file_path,
                                "line": line_num,
                                "content": line.rstrip()[:200],  # Truncate long lines
                            })
                            if len(matches) >= self.max_results:
                                return True
            except Exception:
                pass
            return False

        if os.path.isfile(path):
            search_file(path)
        else:
            for root, dirs, files in os.walk(path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for filename in files:
                    if fnmatch.fnmatch(filename, include):
                        file_path = os.path.join(root, filename)
                        if search_file(file_path):
                            break

                if len(matches) >= self.max_results:
                    break

        return ToolResult(
            success=True,
            content=matches,
            content_type="json",
            metadata={"match_count": len(matches), "truncated": len(matches) >= self.max_results},
        )


class GlobTool(BaseTool):
    """Find files matching a glob pattern."""

    def __init__(
        self,
        allowed_paths: Optional[List[str]] = None,
        max_results: int = 1000,
    ):
        self.allowed_paths = allowed_paths
        self.max_results = max_results

    @property
    def name(self) -> str:
        return "glob"

    @property
    def description(self) -> str:
        return "Find files matching a glob pattern"

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="pattern",
                type="string",
                description="Glob pattern (e.g., '**/*.py')",
                required=True,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Base directory to search from",
                required=True,
            ),
        ]

    def _is_path_allowed(self, path: str) -> bool:
        if self.allowed_paths is None:
            return True

        abs_path = os.path.abspath(path)
        for allowed in self.allowed_paths:
            allowed_abs = os.path.abspath(allowed)
            if abs_path.startswith(allowed_abs):
                return True
        return False

    def execute(self, pattern: str, path: str) -> ToolResult:
        if not self._is_path_allowed(path):
            return ToolResult(
                success=False,
                content=[],
                error=f"Access denied: {path}",
            )

        if not os.path.exists(path):
            return ToolResult(
                success=False,
                content=[],
                error=f"Path not found: {path}",
            )

        try:
            base_path = Path(path)
            matches = list(base_path.glob(pattern))[:self.max_results]
            files = [str(m) for m in matches]

            return ToolResult(
                success=True,
                content=files,
                content_type="json",
                metadata={
                    "match_count": len(files),
                    "truncated": len(matches) >= self.max_results,
                },
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content=[],
                error=str(e),
            )


@dataclass
class ToolRegistry:
    """Registry for managing tools."""
    tools: Dict[str, BaseTool] = field(default_factory=dict)

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self.tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name."""
        if name in self.tools:
            del self.tools[name]
            return True
        return False

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self.tools.get(name)

    def list_tools(self) -> List[Tool]:
        """List all registered tools as MCP Tool definitions."""
        return [tool.get_definition() for tool in self.tools.values()]

    def execute(self, name: str, params: Dict[str, Any]) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                content="",
                error=f"Tool not found: {name}",
            )

        error = tool.validate_params(params)
        if error:
            return ToolResult(
                success=False,
                content="",
                error=error,
            )

        return tool.execute(**params)

    def create_default_registry(
        allowed_paths: Optional[List[str]] = None,
    ) -> "ToolRegistry":
        """Create a registry with default tools."""
        registry = ToolRegistry()
        registry.register(FileReadTool(allowed_paths=allowed_paths))
        registry.register(FileWriteTool(allowed_paths=allowed_paths))
        registry.register(ShellTool())
        registry.register(SearchTool(allowed_paths=allowed_paths))
        registry.register(GlobTool(allowed_paths=allowed_paths))
        return registry

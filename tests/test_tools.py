"""Tests for mcp_server.tools module."""

import pytest
import tempfile
import os

from mcp_server.tools import (
    BaseTool,
    FileReadTool,
    FileWriteTool,
    ShellTool,
    SearchTool,
    GlobTool,
    ToolRegistry,
)
from mcp_server.protocol import ToolParameter


class TestFileReadTool:
    def test_create(self):
        tool = FileReadTool()
        assert tool.name == "file_read"

    def test_read_existing_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            path = f.name

        try:
            tool = FileReadTool()
            result = tool.execute(path=path)
            assert result.success is True
            assert result.content == "hello world"
        finally:
            os.unlink(path)

    def test_read_nonexistent_file(self):
        tool = FileReadTool()
        result = tool.execute(path="/nonexistent/file.txt")
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_read_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileReadTool()
            result = tool.execute(path=tmpdir)
            assert result.success is False
            assert "not a file" in result.error.lower()

    def test_path_restriction(self):
        with tempfile.TemporaryDirectory() as allowed:
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                f.write("secret")
                forbidden_path = f.name

            try:
                tool = FileReadTool(allowed_paths=[allowed])
                result = tool.execute(path=forbidden_path)
                assert result.success is False
                assert "denied" in result.error.lower()
            finally:
                os.unlink(forbidden_path)

    def test_file_too_large(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("x" * 1000)
            path = f.name

        try:
            tool = FileReadTool(max_size=100)
            result = tool.execute(path=path)
            assert result.success is False
            assert "too large" in result.error.lower()
        finally:
            os.unlink(path)

    def test_get_definition(self):
        tool = FileReadTool()
        defn = tool.get_definition()
        assert defn.name == "file_read"
        assert len(defn.parameters) > 0


class TestFileWriteTool:
    def test_create(self):
        tool = FileWriteTool()
        assert tool.name == "file_write"

    def test_write_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            tool = FileWriteTool()
            result = tool.execute(path=path, content="hello")
            assert result.success is True

            with open(path, "r") as f:
                assert f.read() == "hello"

    def test_append_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("first")
            path = f.name

        try:
            tool = FileWriteTool()
            result = tool.execute(path=path, content=" second", mode="append")
            assert result.success is True

            with open(path, "r") as f:
                assert f.read() == "first second"
        finally:
            os.unlink(path)

    def test_create_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "a", "b", "c", "test.txt")
            tool = FileWriteTool()
            result = tool.execute(path=path, content="nested")
            assert result.success is True
            assert os.path.exists(path)

    def test_path_restriction(self):
        with tempfile.TemporaryDirectory() as allowed:
            with tempfile.TemporaryDirectory() as forbidden:
                path = os.path.join(forbidden, "test.txt")
                tool = FileWriteTool(allowed_paths=[allowed])
                result = tool.execute(path=path, content="test")
                assert result.success is False
                assert "denied" in result.error.lower()


class TestShellTool:
    def test_create(self):
        tool = ShellTool()
        assert tool.name == "shell"

    def test_simple_command(self):
        tool = ShellTool()
        # Use a cross-platform command
        result = tool.execute(command="echo hello")
        assert result.success is True
        assert "hello" in result.content

    def test_command_failure(self):
        tool = ShellTool()
        result = tool.execute(command="exit 1")
        assert result.success is False

    def test_blocked_command(self):
        tool = ShellTool(blocked_commands=["rm -rf /"])
        result = tool.execute(command="rm -rf /")
        assert result.success is False
        assert "not allowed" in result.error.lower()

    def test_allowed_commands(self):
        tool = ShellTool(allowed_commands=["echo", "ls"])
        result = tool.execute(command="echo test")
        assert result.success is True

        result = tool.execute(command="cat /etc/passwd")
        assert result.success is False

    def test_timeout(self):
        tool = ShellTool(timeout=1)
        # Use Python to sleep - works cross-platform
        cmd = "python -c \"import time; time.sleep(10)\""
        result = tool.execute(command=cmd, timeout=1)
        assert result.success is False
        assert "timed out" in result.error.lower()


class TestSearchTool:
    def test_create(self):
        tool = SearchTool()
        assert tool.name == "search"

    def test_search_in_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("line one\nline two\nline three\n")
            path = f.name

        try:
            tool = SearchTool()
            result = tool.execute(pattern="two", path=path)
            assert result.success is True
            assert len(result.content) == 1
            assert result.content[0]["line"] == 2
        finally:
            os.unlink(path)

    def test_search_in_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "a.txt"), "w") as f:
                f.write("foo bar\n")
            with open(os.path.join(tmpdir, "b.txt"), "w") as f:
                f.write("baz qux\n")

            tool = SearchTool()
            result = tool.execute(pattern="foo", path=tmpdir)
            assert result.success is True
            assert len(result.content) == 1

    def test_search_with_include(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "a.py"), "w") as f:
                f.write("target\n")
            with open(os.path.join(tmpdir, "b.txt"), "w") as f:
                f.write("target\n")

            tool = SearchTool()
            result = tool.execute(pattern="target", path=tmpdir, include="*.py")
            assert result.success is True
            assert len(result.content) == 1
            assert result.content[0]["file"].endswith(".py")

    def test_search_case_insensitive(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello World\n")
            path = f.name

        try:
            tool = SearchTool()
            result = tool.execute(pattern="hello", path=path, ignore_case=True)
            assert result.success is True
            assert len(result.content) == 1
        finally:
            os.unlink(path)

    def test_invalid_regex(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = SearchTool()
            result = tool.execute(pattern="[invalid", path=tmpdir)
            assert result.success is False
            assert "regex" in result.error.lower()

    def test_path_not_found(self):
        tool = SearchTool()
        result = tool.execute(pattern="test", path="/nonexistent")
        assert result.success is False


class TestGlobTool:
    def test_create(self):
        tool = GlobTool()
        assert tool.name == "glob"

    def test_glob_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "a.py"), "w") as f:
                f.write("")
            with open(os.path.join(tmpdir, "b.py"), "w") as f:
                f.write("")
            with open(os.path.join(tmpdir, "c.txt"), "w") as f:
                f.write("")

            tool = GlobTool()
            result = tool.execute(pattern="*.py", path=tmpdir)
            assert result.success is True
            assert len(result.content) == 2

    def test_glob_recursive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "sub")
            os.makedirs(subdir)
            with open(os.path.join(tmpdir, "a.py"), "w") as f:
                f.write("")
            with open(os.path.join(subdir, "b.py"), "w") as f:
                f.write("")

            tool = GlobTool()
            result = tool.execute(pattern="**/*.py", path=tmpdir)
            assert result.success is True
            assert len(result.content) == 2

    def test_path_not_found(self):
        tool = GlobTool()
        result = tool.execute(pattern="*.py", path="/nonexistent")
        assert result.success is False


class TestToolRegistry:
    def test_create(self):
        registry = ToolRegistry()
        assert len(registry.tools) == 0

    def test_register(self):
        registry = ToolRegistry()
        tool = FileReadTool()
        registry.register(tool)
        assert "file_read" in registry.tools

    def test_unregister(self):
        registry = ToolRegistry()
        tool = FileReadTool()
        registry.register(tool)
        assert registry.unregister("file_read") is True
        assert "file_read" not in registry.tools

    def test_unregister_nonexistent(self):
        registry = ToolRegistry()
        assert registry.unregister("nonexistent") is False

    def test_get(self):
        registry = ToolRegistry()
        tool = FileReadTool()
        registry.register(tool)
        retrieved = registry.get("file_read")
        assert retrieved is tool

    def test_get_nonexistent(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_list_tools(self):
        registry = ToolRegistry()
        registry.register(FileReadTool())
        registry.register(FileWriteTool())
        tools = registry.list_tools()
        assert len(tools) == 2
        names = [t.name for t in tools]
        assert "file_read" in names
        assert "file_write" in names

    def test_execute(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("content")
            path = f.name

        try:
            registry = ToolRegistry()
            registry.register(FileReadTool())
            result = registry.execute("file_read", {"path": path})
            assert result.success is True
            assert result.content == "content"
        finally:
            os.unlink(path)

    def test_execute_tool_not_found(self):
        registry = ToolRegistry()
        result = registry.execute("nonexistent", {})
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_execute_missing_params(self):
        registry = ToolRegistry()
        registry.register(FileReadTool())
        result = registry.execute("file_read", {})
        assert result.success is False
        assert "missing" in result.error.lower()

    def test_create_default_registry(self):
        registry = ToolRegistry.create_default_registry()
        assert "file_read" in registry.tools
        assert "file_write" in registry.tools
        assert "shell" in registry.tools
        assert "search" in registry.tools
        assert "glob" in registry.tools

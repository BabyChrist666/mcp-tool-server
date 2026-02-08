"""
MCP Transport layer implementations.

Provides transport mechanisms for MCP communication:
- StdioTransport: Communication via stdin/stdout
- WebSocketTransport: Communication via WebSocket
"""

import sys
import json
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, AsyncIterator
from dataclasses import dataclass


class Transport(ABC):
    """Abstract base class for MCP transports."""

    @abstractmethod
    async def send(self, message: dict) -> None:
        """Send a message."""
        pass

    @abstractmethod
    async def receive(self) -> Optional[dict]:
        """Receive a message. Returns None on EOF/close."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the transport."""
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class StdioTransport(Transport):
    """
    Transport using stdin/stdout for communication.

    Uses JSON-RPC framing with Content-Length headers.
    """

    def __init__(
        self,
        input_stream=None,
        output_stream=None,
    ):
        self.input = input_stream or sys.stdin
        self.output = output_stream or sys.stdout
        self._closed = False
        self._read_buffer = ""

    async def send(self, message: dict) -> None:
        """Send a message to stdout."""
        if self._closed:
            raise RuntimeError("Transport is closed")

        content = json.dumps(message)
        encoded = content.encode("utf-8")

        header = f"Content-Length: {len(encoded)}\r\n\r\n"

        try:
            self.output.write(header)
            self.output.write(content)
            self.output.flush()
        except Exception as e:
            raise RuntimeError(f"Failed to send: {e}")

    async def receive(self) -> Optional[dict]:
        """Receive a message from stdin."""
        if self._closed:
            return None

        try:
            # Read headers
            content_length = None

            while True:
                line = self.input.readline()
                if not line:
                    return None  # EOF

                line = line.strip()
                if not line:
                    break  # Empty line = end of headers

                if line.startswith("Content-Length:"):
                    content_length = int(line.split(":")[1].strip())

            if content_length is None:
                # Fallback: try to read a line as JSON
                line = self.input.readline()
                if not line:
                    return None
                return json.loads(line)

            # Read content
            content = self.input.read(content_length)
            if not content:
                return None

            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        except Exception as e:
            if "EOF" in str(e) or "closed" in str(e).lower():
                return None
            raise

    async def close(self) -> None:
        """Close the transport."""
        self._closed = True


class WebSocketTransport(Transport):
    """
    Transport using WebSocket for communication.

    Requires an asyncio-compatible WebSocket implementation.
    """

    def __init__(self, websocket):
        self.websocket = websocket
        self._closed = False

    async def send(self, message: dict) -> None:
        """Send a message via WebSocket."""
        if self._closed:
            raise RuntimeError("Transport is closed")

        content = json.dumps(message)
        await self.websocket.send(content)

    async def receive(self) -> Optional[dict]:
        """Receive a message from WebSocket."""
        if self._closed:
            return None

        try:
            content = await self.websocket.recv()
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        except Exception as e:
            if "closed" in str(e).lower():
                return None
            raise

    async def close(self) -> None:
        """Close the WebSocket transport."""
        self._closed = True
        try:
            await self.websocket.close()
        except Exception:
            pass


@dataclass
class TransportMessage:
    """A message received from transport with metadata."""
    content: dict
    transport: Transport


class TransportPool:
    """
    Manages multiple transports for broadcasting messages.
    """

    def __init__(self):
        self._transports: list[Transport] = []

    def add(self, transport: Transport) -> None:
        """Add a transport to the pool."""
        self._transports.append(transport)

    def remove(self, transport: Transport) -> None:
        """Remove a transport from the pool."""
        if transport in self._transports:
            self._transports.remove(transport)

    async def broadcast(self, message: dict) -> None:
        """Send a message to all transports."""
        tasks = [t.send(message) for t in self._transports]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def close_all(self) -> None:
        """Close all transports."""
        tasks = [t.close() for t in self._transports]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._transports.clear()

    def __len__(self) -> int:
        return len(self._transports)

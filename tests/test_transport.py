"""Tests for mcp_server.transport module."""

import pytest
import asyncio
import io
import json

from mcp_server.transport import (
    Transport,
    StdioTransport,
    WebSocketTransport,
    TransportMessage,
    TransportPool,
)


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self):
        self.sent_messages = []
        self.receive_queue = asyncio.Queue()
        self.closed = False

    async def send(self, message):
        if self.closed:
            raise RuntimeError("WebSocket closed")
        self.sent_messages.append(message)

    async def recv(self):
        if self.closed:
            raise RuntimeError("WebSocket closed")
        return await self.receive_queue.get()

    async def close(self):
        self.closed = True

    def add_message(self, message):
        """Add a message to the receive queue."""
        self.receive_queue.put_nowait(message)


class TestStdioTransport:
    def test_create(self):
        transport = StdioTransport()
        assert transport is not None

    def test_create_with_streams(self):
        input_stream = io.StringIO()
        output_stream = io.StringIO()
        transport = StdioTransport(input_stream=input_stream, output_stream=output_stream)
        assert transport.input is input_stream
        assert transport.output is output_stream

    @pytest.mark.asyncio
    async def test_send(self):
        output = io.StringIO()
        transport = StdioTransport(output_stream=output)

        message = {"jsonrpc": "2.0", "id": "1", "result": "ok"}
        await transport.send(message)

        output.seek(0)
        content = output.read()
        assert "Content-Length:" in content
        assert '"result": "ok"' in content

    @pytest.mark.asyncio
    async def test_receive_with_headers(self):
        message = {"jsonrpc": "2.0", "id": "1", "method": "test"}
        json_content = json.dumps(message)
        content_length = len(json_content.encode("utf-8"))

        input_content = f"Content-Length: {content_length}\r\n\r\n{json_content}"
        input_stream = io.StringIO(input_content)
        transport = StdioTransport(input_stream=input_stream)

        received = await transport.receive()
        assert received["method"] == "test"

    @pytest.mark.asyncio
    async def test_receive_eof(self):
        input_stream = io.StringIO("")
        transport = StdioTransport(input_stream=input_stream)

        received = await transport.receive()
        assert received is None

    @pytest.mark.asyncio
    async def test_close(self):
        transport = StdioTransport()
        await transport.close()
        assert transport._closed is True

    @pytest.mark.asyncio
    async def test_send_after_close(self):
        transport = StdioTransport()
        await transport.close()

        with pytest.raises(RuntimeError):
            await transport.send({"test": "message"})

    @pytest.mark.asyncio
    async def test_context_manager(self):
        transport = StdioTransport()
        async with transport:
            assert transport._closed is False
        assert transport._closed is True


class TestWebSocketTransport:
    @pytest.mark.asyncio
    async def test_create(self):
        ws = MockWebSocket()
        transport = WebSocketTransport(ws)
        assert transport.websocket is ws

    @pytest.mark.asyncio
    async def test_send(self):
        ws = MockWebSocket()
        transport = WebSocketTransport(ws)

        message = {"jsonrpc": "2.0", "result": "test"}
        await transport.send(message)

        assert len(ws.sent_messages) == 1
        assert json.loads(ws.sent_messages[0]) == message

    @pytest.mark.asyncio
    async def test_receive(self):
        ws = MockWebSocket()
        transport = WebSocketTransport(ws)

        message = {"jsonrpc": "2.0", "id": "1", "method": "ping"}
        ws.add_message(json.dumps(message))

        received = await transport.receive()
        assert received == message

    @pytest.mark.asyncio
    async def test_receive_invalid_json(self):
        ws = MockWebSocket()
        transport = WebSocketTransport(ws)
        ws.add_message("not json")

        with pytest.raises(ValueError):
            await transport.receive()

    @pytest.mark.asyncio
    async def test_close(self):
        ws = MockWebSocket()
        transport = WebSocketTransport(ws)
        await transport.close()

        assert transport._closed is True
        assert ws.closed is True


class TestTransportMessage:
    def test_create(self):
        ws = MockWebSocket()
        transport = WebSocketTransport(ws)
        msg = TransportMessage(
            content={"test": "data"},
            transport=transport,
        )
        assert msg.content["test"] == "data"
        assert msg.transport is transport


class TestTransportPool:
    @pytest.mark.asyncio
    async def test_create(self):
        pool = TransportPool()
        assert len(pool) == 0

    @pytest.mark.asyncio
    async def test_add(self):
        pool = TransportPool()
        ws = MockWebSocket()
        transport = WebSocketTransport(ws)
        pool.add(transport)
        assert len(pool) == 1

    @pytest.mark.asyncio
    async def test_remove(self):
        pool = TransportPool()
        ws = MockWebSocket()
        transport = WebSocketTransport(ws)
        pool.add(transport)
        pool.remove(transport)
        assert len(pool) == 0

    @pytest.mark.asyncio
    async def test_broadcast(self):
        pool = TransportPool()
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        t1 = WebSocketTransport(ws1)
        t2 = WebSocketTransport(ws2)
        pool.add(t1)
        pool.add(t2)

        message = {"test": "broadcast"}
        await pool.broadcast(message)

        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_close_all(self):
        pool = TransportPool()
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        pool.add(WebSocketTransport(ws1))
        pool.add(WebSocketTransport(ws2))

        await pool.close_all()

        assert ws1.closed is True
        assert ws2.closed is True
        assert len(pool) == 0

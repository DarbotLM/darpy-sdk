"""Malformed-message and dependency boundaries around the pinned ACP transport."""

import anyio
import pytest
from acp.schema import SessionNotification
from inline_snapshot import snapshot
from pydantic import JsonValue

from darpy_sdk.protocols import _acp_compat
from darpy_sdk.protocols.acp import ACPAgent, ACPClient, connect_to_agent
from darpy_sdk.runtime import Runtime, Task


class BufferedTransport:
    def __init__(self, incoming: dict[str, JsonValue] | None = None) -> None:
        self.incoming = incoming
        self.sent: list[dict[str, JsonValue]] = []
        self.closed = False

    async def send(self, message: dict[str, JsonValue]) -> None:
        self.sent.append(message)

    async def receive(self) -> dict[str, JsonValue] | None:
        return self.incoming

    async def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_transport_preserves_uninterpreted_frames_and_rejects_corrupt_internal_metadata() -> None:
    """The typed ACP API cannot emit malformed frames or corrupted internal metadata.

    DARPy leaves non-adapted messages intact and rejects ambiguous internal envelopes before sending.
    """
    frames: list[dict[str, JsonValue]] = [
        {"jsonrpc": "2.0", "id": 1, "method": [], "params": {}},
        {"jsonrpc": "2.0", "method": {"invalid": True}, "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "session/prompt", "params": []},
        {"jsonrpc": "2.0", "method": "session/cancel", "params": None},
        {"jsonrpc": "2.0", "id": 3, "method": "session/prompt", "params": {"_meta": []}},
        {"jsonrpc": "2.0", "method": "session/cancel", "params": {"_meta": "invalid"}},
        {"jsonrpc": "2.0", "method": "session/cancel", "params": {"_meta": None}},
        {"jsonrpc": "2.0", "id": 4, "method": "_extension", "params": {"_meta": {"opaque": None}}},
        {"jsonrpc": "2.0", "method": "_event", "params": {"_meta": {"opaque": False}}},
        {"jsonrpc": "2.0", "id": 5, "result": {"_meta": {"opaque": [None, False]}}},
        {"jsonrpc": "2.0", "id": 6, "error": {"code": -32603, "message": "peer", "data": None}},
    ]
    with anyio.fail_after(5):
        for frame in frames:
            transport = BufferedTransport(frame)
            boundary = _acp_compat.MetadataTransport(transport)
            assert await boundary.receive() is frame
            await boundary.send(frame)
            assert transport.sent[0] is frame
            await boundary.close()
            assert transport.closed
        transport = BufferedTransport()
        boundary = _acp_compat.MetadataTransport(transport)
        assert await boundary.receive() is None
        with pytest.raises(ValueError) as ambiguous:
            await boundary.send(
                {
                    "method": "session/cancel",
                    "params": {"_meta": {_acp_compat.INTERNAL_META: {}, "unexpected": True}},
                }
            )
        assert str(ambiguous.value) == snapshot("Use the dedicated meta argument for ACP metadata")
        assert transport.sent == []
        with pytest.raises(ValueError) as malformed:
            _acp_compat.decode_meta({_acp_compat.INTERNAL_META: 17})
        assert str(malformed.value) == snapshot("Internal ACP metadata must contain an object")


@pytest.mark.anyio
async def test_unsupported_acp_version_prevents_guarded_client_and_agent_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DARPy refuses an unreviewed upstream version before opening either side of a connection."""

    def installed_version(distribution: str) -> str:
        assert distribution == "agent-client-protocol"
        return "0.0.0"

    async def update(notification: SessionNotification) -> None:
        raise NotImplementedError

    async def execute(task: Task) -> str:
        raise NotImplementedError

    monkeypatch.setattr(_acp_compat, "version", installed_version)
    transport = BufferedTransport()
    client = ACPClient(update)
    agent = ACPAgent(Runtime(execute))
    with pytest.raises(RuntimeError) as client_error:
        connect_to_agent(client, transport)
    with pytest.raises(RuntimeError) as agent_error:
        await agent.serve(transport)
    assert {"client": str(client_error.value), "agent": str(agent_error.value)} == snapshot(
        {
            "client": "The ACP compatibility bridge requires 0.12.1; found 0.0.0",
            "agent": "The ACP compatibility bridge requires 0.12.1; found 0.0.0",
        }
    )
    assert transport.sent == []
    assert not transport.closed

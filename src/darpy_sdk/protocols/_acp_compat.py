"""Version-pinned ACP framing and metadata boundary; no global monkeypatching."""

import asyncio
from importlib.metadata import version
from typing import Any, Protocol, cast

from acp import AGENT_METHODS, CLIENT_METHODS
from acp._transport import NdjsonTransport
from acp.task import MessageSender, TaskSupervisor

INTERNAL_META = "darpy.internal/acp-metadata"
_BUILTIN_METHODS = frozenset((*AGENT_METHODS.values(), *CLIENT_METHODS.values()))
SUPPORTED_ACP_VERSION = "0.12.1"


class MessageTransport(Protocol):
    """The decoded-message transport accepted by the official ACP SDK."""

    async def send(self, message: dict[str, Any]) -> None:
        """Send a JSON-RPC message."""
        ...

    async def receive(self) -> dict[str, Any] | None:
        """Receive a message, or None at EOF."""
        ...

    async def close(self) -> None:
        """Close the transport."""
        ...


def check_version() -> None:
    installed = version("agent-client-protocol")
    if installed != SUPPORTED_ACP_VERSION:
        raise RuntimeError(f"The ACP compatibility bridge requires {SUPPORTED_ACP_VERSION}; found {installed}")


def encode_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    return {INTERNAL_META: meta} if meta is not None else {}


def decode_meta(kwargs: dict[str, Any]) -> dict[str, Any] | None:
    value = kwargs.get(INTERNAL_META)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Internal ACP metadata must contain an object")
    return cast(dict[str, Any], value)


class MetadataTransport:
    """Separate opaque metadata from ACP's flattened Python handler arguments.

    Only builtin request/notification parameters change internally. The peer's
    wire metadata stays intact, including keys equal to the internal envelope.
    """

    def __init__(self, transport: MessageTransport) -> None:
        check_version()
        self._transport = transport

    async def receive(self) -> dict[str, Any] | None:
        message = await self._transport.receive()
        if message is None:
            return None
        params = message.get("params")
        method = message.get("method")
        if isinstance(method, str) and method in _BUILTIN_METHODS and isinstance(params, dict):
            params = cast(dict[str, Any], params)
            meta = params.get("_meta")
            if isinstance(meta, dict):
                return {**message, "params": {**params, "_meta": encode_meta(cast(dict[str, Any], meta))}}
        return message

    async def send(self, message: dict[str, Any]) -> None:
        params = message.get("params")
        method = message.get("method")
        if isinstance(method, str) and method in _BUILTIN_METHODS and isinstance(params, dict):
            params = cast(dict[str, Any], params)
            meta = params.get("_meta")
            if isinstance(meta, dict) and INTERNAL_META in meta:
                meta = cast(dict[str, Any], meta)
                if set(meta) != {INTERNAL_META}:
                    raise ValueError("Use the dedicated meta argument for ACP metadata")
                message = {**message, "params": {**params, "_meta": meta[INTERNAL_META]}}
        await self._transport.send(message)

    async def close(self) -> None:
        await self._transport.close()


class StdioTransport:
    """Reuse official NDJSON framing; isolate its non-public constructor here."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        check_version()
        self._supervisor = TaskSupervisor(source="darpy_sdk.acp.stdio")
        self._sender = MessageSender(writer, self._supervisor)
        self._framing = NdjsonTransport(reader, self._sender)

    async def send(self, message: dict[str, Any]) -> None:
        await self._framing.send(message)

    async def receive(self) -> dict[str, Any] | None:
        return await self._framing.receive()

    async def close(self) -> None:
        try:
            await self._framing.close()
        finally:
            await self._supervisor.shutdown()

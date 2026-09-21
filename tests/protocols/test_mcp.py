"""Public MCP bridge behavior through in-memory clients and runtime handlers."""

import json
from typing import Literal
from unittest.mock import AsyncMock

import pytest
from darpy_sdk_types import RequestParamsMeta
from inline_snapshot import snapshot
from pydantic import JsonValue

from darpy_sdk import Client
from darpy_sdk.protocols.mcp import create_server
from darpy_sdk.runtime import RunBudget, Runtime, Task
from darpy_sdk.server import ServerRequestContext
from darpy_sdk.server.context import CallNext, HandlerResult

pytestmark = pytest.mark.anyio


async def test_tool_schema_and_reply_match_the_runtime_task_in_both_modes() -> None:
    """SDK-defined: both client modes expose a typed tool and preserve its request context.

    Steps: list the typed tool, call it, then compare its runtime task with the
    independently observed public request context in each mode.
    """
    tasks: list[Task] = []
    requests: list[ServerRequestContext] = []
    replies: dict[str, dict[str, JsonValue]] = {}

    async def handle(task: Task) -> str:
        assert task.protocol == "mcp"
        tasks.append(task)
        return "runtime reply"

    async def observe(ctx: ServerRequestContext, call_next: CallNext) -> HandlerResult:
        if ctx.method == "tools/call":
            requests.append(ctx)
        return await call_next(ctx)

    modes: tuple[Literal["auto", "legacy"], ...] = ("auto", "legacy")
    for mode in modes:
        server = create_server(Runtime(handle), name="test-bridge")
        server.middleware.append(observe)
        async with Client(server, mode=mode) as client:
            listing = await client.list_tools()
            response = await client.call_tool("darpy_run", {"prompt": "hello", "session_id": "session-a"})

        replies[mode] = {
            "listing": listing.model_dump(mode="json", by_alias=True),
            "reply": response.model_dump(mode="json", by_alias=True),
        }
        task, request = tasks[-1], requests[-1]
        assert (task.prompt, task.session_id, task.protocol, task.cwd) == snapshot(("hello", "session-a", "mcp", None))
        assert task.request_id == str(request.request_id)
        assert task.payload_json is not None
        assert json.loads(task.payload_json) == {
            "name": "darpy_run",
            "arguments": {"prompt": "hello", "session_id": "session-a"},
            "_meta": request.meta,
        }

    assert len(tasks) == len(requests) == 2
    assert replies == snapshot(
        {
            "auto": {
                "listing": {
                    "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "test-bridge", "version": ""}},
                    "ttlMs": 0,
                    "cacheScope": "private",
                    "nextCursor": None,
                    "tools": [
                        {
                            "name": "darpy_run",
                            "title": None,
                            "description": "Run a handler in the caller-selected logical session.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "prompt": {"title": "Prompt", "type": "string"},
                                    "session_id": {"title": "Session Id", "type": "string"},
                                },
                                "required": ["prompt", "session_id"],
                                "title": "darpy_runArguments",
                            },
                            "execution": None,
                            "outputSchema": {
                                "properties": {"result": {"title": "Result", "type": "string"}},
                                "required": ["result"],
                                "title": "darpy_runOutput",
                                "type": "object",
                            },
                            "icons": None,
                            "annotations": None,
                            "_meta": None,
                        }
                    ],
                    "resultType": "complete",
                },
                "reply": {
                    "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "test-bridge", "version": ""}},
                    "content": [{"type": "text", "text": "runtime reply", "annotations": None, "_meta": None}],
                    "structuredContent": {"result": "runtime reply"},
                    "isError": False,
                    "resultType": "complete",
                },
            },
            "legacy": {
                "listing": {
                    "_meta": None,
                    "ttlMs": 0,
                    "cacheScope": "private",
                    "nextCursor": None,
                    "tools": [
                        {
                            "name": "darpy_run",
                            "title": None,
                            "description": "Run a handler in the caller-selected logical session.",
                            "inputSchema": {
                                "properties": {
                                    "prompt": {"title": "Prompt", "type": "string"},
                                    "session_id": {"title": "Session Id", "type": "string"},
                                },
                                "required": ["prompt", "session_id"],
                                "type": "object",
                                "title": "darpy_runArguments",
                            },
                            "execution": None,
                            "outputSchema": {
                                "properties": {"result": {"title": "Result", "type": "string"}},
                                "required": ["result"],
                                "type": "object",
                                "title": "darpy_runOutput",
                            },
                            "icons": None,
                            "annotations": None,
                            "_meta": None,
                        }
                    ],
                    "resultType": "complete",
                },
                "reply": {
                    "_meta": None,
                    "content": [{"type": "text", "text": "runtime reply", "annotations": None, "_meta": None}],
                    "structuredContent": {"result": "runtime reply"},
                    "isError": False,
                    "resultType": "complete",
                },
            },
        }
    )


async def test_metadata_remains_opaque_and_cannot_replace_task_controls() -> None:
    """SDK-defined: caller metadata survives, including nulls and keys named like runtime fields."""
    tasks: list[Task] = []
    opaque: RequestParamsMeta = {
        "session_id": "metadata-session",
        "prompt": None,
        "protocol": "activity",
        "request_id": "metadata-request",
        "_meta": {"nested": None, "values": [False, 0, "🙂"]},
    }
    progress_token = 0
    metadata: RequestParamsMeta = {**opaque, "progress_token": progress_token}

    async def handle(task: Task) -> str:
        assert task.protocol == "mcp"
        tasks.append(task)
        return "metadata preserved"

    server = create_server(Runtime(handle))
    async with Client(server) as client:
        response = await client.call_tool(
            "darpy_run", {"prompt": "actual prompt", "session_id": "actual-session"}, meta=metadata
        )

    assert response.model_dump(mode="json", by_alias=True) == snapshot(
        {
            "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "DARPy", "version": ""}},
            "content": [{"type": "text", "text": "metadata preserved", "annotations": None, "_meta": None}],
            "structuredContent": {"result": "metadata preserved"},
            "isError": False,
            "resultType": "complete",
        }
    )
    (task,) = tasks
    assert task.prompt == "actual prompt"
    assert task.session_id == "actual-session"
    assert task.request_id != opaque["request_id"]
    assert task.payload_json is not None
    payload = json.loads(task.payload_json)
    assert opaque.keys() <= payload["_meta"].keys()
    assert {key: payload["_meta"][key] for key in opaque} == opaque
    assert payload["_meta"]["progressToken"] == progress_token
    assert "progress_token" not in payload["_meta"]
    assert payload["arguments"] == {"prompt": "actual prompt", "session_id": "actual-session"}


async def test_input_budget_failure_returns_tool_error_without_running_handler() -> None:
    """SDK-defined: a runtime input limit becomes a complete MCP tool failure before the handler runs."""
    handler = AsyncMock(return_value="must not run")
    server = create_server(Runtime(handler, budget=RunBudget(max_input_chars=1)))
    async with Client(server) as client:
        response = await client.call_tool("darpy_run", {"prompt": "too large", "session_id": "session"})

    assert response.model_dump(mode="json", by_alias=True) == snapshot(
        {
            "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "DARPy", "version": ""}},
            "content": [
                {
                    "type": "text",
                    "text": "Error executing tool darpy_run: Input character budget exceeded",
                    "annotations": None,
                    "_meta": None,
                }
            ],
            "structuredContent": None,
            "isError": True,
            "resultType": "complete",
        }
    )
    handler.assert_not_called()

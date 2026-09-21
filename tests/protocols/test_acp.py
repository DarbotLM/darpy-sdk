"""Public ACP round trips through the SDK's metadata and session boundaries."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
import pytest
from acp.schema import (
    AgentMessageChunk,
    AllowedOutcome,
    PermissionOption,
    PromptResponse,
    RequestPermissionRequest,
    RequestPermissionResponse,
    ResourceContentBlock,
    SessionNotification,
    TextContentBlock,
    ToolCallUpdate,
)
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from inline_snapshot import snapshot
from pydantic import JsonValue

from darpy_sdk.protocols.acp import ACPAgent, ACPClient, ACPConnection, connect_to_agent, run_agent
from darpy_sdk.runtime import Runtime, Task


class _Endpoint:
    def __init__(
        self,
        outgoing: MemoryObjectSendStream[dict[str, JsonValue]],
        incoming: MemoryObjectReceiveStream[dict[str, JsonValue]],
    ) -> None:
        self.outgoing = outgoing
        self.incoming = incoming
        self.sent: list[dict[str, JsonValue]] = []

    async def send(self, message: dict[str, JsonValue]) -> None:
        self.sent.append(message)
        await self.outgoing.send(message)

    async def receive(self) -> dict[str, JsonValue] | None:
        try:
            return await self.incoming.receive()
        except anyio.EndOfStream:
            return None

    async def close(self) -> None:
        await self.outgoing.aclose()


@asynccontextmanager
async def _connected(agent: ACPAgent, client: ACPClient) -> AsyncIterator[tuple[ACPConnection, _Endpoint]]:
    left_send, right_receive = anyio.create_memory_object_stream[dict[str, JsonValue]](10)
    right_send, left_receive = anyio.create_memory_object_stream[dict[str, JsonValue]](10)
    left = _Endpoint(left_send, left_receive)
    right = _Endpoint(right_send, right_receive)
    async with left_send, left_receive, right_send, right_receive, anyio.create_task_group() as group:
        group.start_soon(run_agent, agent, right)
        async with connect_to_agent(client, left) as connection:
            yield connection, left


@pytest.mark.anyio
async def test_prompt_preserves_metadata_collisions_and_resource_links() -> None:
    """SDK metadata isolation preserves ACP's mandatory text and resource-link input."""
    tasks: list[Task] = []
    updates: list[SessionNotification] = []

    async def handle(task: Task) -> str:
        assert task.protocol == "acp"
        tasks.append(task)
        return task.prompt

    async def update(notification: SessionNotification) -> None:
        updates.append(notification)

    agent = ACPAgent(Runtime(handle))
    client = ACPClient(update)
    meta: dict[str, JsonValue] = {
        "session_id": "injected",
        "prompt": "injected",
        "self": "injected",
        "darpy.internal/acp-metadata": {"original": None},
        "traceparent": "opaque",
    }
    prompt = [
        TextContentBlock(type="text", text="Review"),
        ResourceContentBlock(type="resource_link", name="source", uri="file:///workspace/source.py"),
    ]
    with anyio.fail_after(5):
        async with _connected(agent, client) as (connection, endpoint):
            initialization = await connection.initialize()
            assert initialization.agent_capabilities is not None
            assert initialization.agent_capabilities.model_dump(
                mode="json", by_alias=True, exclude_none=True
            ) == snapshot(
                {
                    "loadSession": False,
                    "promptCapabilities": {"image": False, "audio": False, "embeddedContext": False},
                    "mcpCapabilities": {"http": False, "sse": False, "acp": False},
                    "sessionCapabilities": {},
                    "auth": {},
                }
            )
            session = await connection.new_session("/workspace", additional_directories=["/shared"])
            result = await connection.prompt(session.session_id, prompt, meta=meta)
            assert result.model_dump(mode="json", by_alias=True, exclude_none=True) == snapshot(
                {"stopReason": "end_turn"}
            )
    assert len(tasks) == 1
    assert tasks[0].session_id == session.session_id
    assert tasks[0].cwd == "/workspace"
    assert tasks[0].payload_json is not None
    payload = json.loads(tasks[0].payload_json)
    assert payload.pop("_meta") == meta
    assert payload == snapshot(
        {
            "additionalDirectories": ["/shared"],
            "prompt": [
                {"text": "Review", "type": "text"},
                {"name": "source", "uri": "file:///workspace/source.py", "type": "resource_link"},
            ],
        }
    )
    assert len(updates) == 1
    assert updates[0].session_id == session.session_id
    assert isinstance(updates[0].update, AgentMessageChunk)
    assert updates[0].update.model_dump(mode="json", by_alias=True, exclude_none=True) == snapshot(
        {
            "content": {
                "text": """\
Review
source: file:///workspace/source.py\
""",
                "type": "text",
            },
            "sessionUpdate": "agent_message_chunk",
        }
    )
    sent_prompt = next(message for message in endpoint.sent if message.get("method") == "session/prompt")
    params = sent_prompt["params"]
    assert isinstance(params, dict)
    assert params["_meta"] == meta


@pytest.mark.anyio
async def test_cancel_settles_permission_preserves_other_session_and_allows_reuse() -> None:
    """ACP cancellation settles permission responses without cancelling another session.

    Steps: 1. Block two sessions. 2. Cancel one permission turn. 3. Finish the other and reuse the cancelled session.
    """
    permission_started = anyio.Event()
    permission_finished = anyio.Event()
    second_started = anyio.Event()
    release_second = anyio.Event()
    first_finished = anyio.Event()
    results: dict[str, PromptResponse] = {}
    updates: list[SessionNotification] = []
    choice_send, choice_receive = anyio.create_memory_object_stream[RequestPermissionResponse]()

    async def permission(request: RequestPermissionRequest) -> RequestPermissionResponse:
        assert request.tool_call.tool_call_id == "tool-first"
        permission_started.set()
        try:
            return await choice_receive.receive()
        finally:
            permission_finished.set()

    async def handle(task: Task) -> str:
        if task.prompt == "first":
            await agent.request_permission(
                task.session_id,
                ToolCallUpdate(tool_call_id="tool-first"),
                [PermissionOption(option_id="allow", name="Allow", kind="allow_once")],
            )
        elif task.prompt == "second":
            second_started.set()
            await release_second.wait()
        return task.prompt

    async def update(notification: SessionNotification) -> None:
        updates.append(notification)

    agent = ACPAgent(Runtime(handle))
    client = ACPClient(update, on_permission=permission)
    with anyio.fail_after(5):
        async with choice_send, choice_receive, _connected(agent, client) as (connection, endpoint):
            await connection.initialize()
            first = await connection.new_session("/first")
            second = await connection.new_session("/second")

            async def run_prompt(label: str, session_id: str) -> None:
                results[label] = await connection.prompt(session_id, [TextContentBlock(type="text", text=label)])
                if label == "first":
                    first_finished.set()

            async with anyio.create_task_group() as group:
                group.start_soon(run_prompt, "first", first.session_id)
                group.start_soon(run_prompt, "second", second.session_id)
                await permission_started.wait()
                await second_started.wait()
                await connection.cancel(first.session_id, meta={"session_id": second.session_id})
                await first_finished.wait()
                await permission_finished.wait()
                assert "second" not in results
                assert results["first"].model_dump(mode="json", by_alias=True, exclude_none=True) == snapshot(
                    {"stopReason": "cancelled"}
                )
                release_second.set()
            assert results["second"].stop_reason == "end_turn"
            reuse = await connection.prompt(first.session_id, [TextContentBlock(type="text", text="again")])
            assert reuse.stop_reason == "end_turn"
    permission_responses = [message["result"] for message in endpoint.sent if "result" in message]
    assert permission_responses == snapshot([{"outcome": {"outcome": "cancelled"}}])
    assert [notification.session_id for notification in updates] == [second.session_id, first.session_id]


@pytest.mark.anyio
async def test_selected_rejection_preserves_permission_metadata_and_denies_execution() -> None:
    """ACP selected rejection options remain denials despite the upstream AllowedOutcome name."""
    received: list[RequestPermissionRequest] = []
    updates: list[SessionNotification] = []
    meta: dict[str, JsonValue] = {"session_id": "injected", "options": [], "self": "injected"}

    async def permission(request: RequestPermissionRequest) -> RequestPermissionResponse:
        assert request.tool_call.tool_call_id == "edit"
        received.append(request)
        return RequestPermissionResponse(outcome=AllowedOutcome(outcome="selected", option_id="reject"))

    async def handle(task: Task) -> str:
        allowed = await agent.request_permission(
            task.session_id,
            ToolCallUpdate(tool_call_id="edit", title="Edit source"),
            [
                PermissionOption(option_id="allow", name="Allow once", kind="allow_once"),
                PermissionOption(option_id="reject", name="Reject", kind="reject_once"),
            ],
            meta=meta,
        )
        return "executed" if allowed else "denied"

    async def update(notification: SessionNotification) -> None:
        updates.append(notification)

    agent = ACPAgent(Runtime(handle))
    client = ACPClient(update, on_permission=permission)
    with anyio.fail_after(5):
        async with _connected(agent, client) as (connection, _):
            await connection.initialize()
            session = await connection.new_session("/workspace")
            await connection.prompt(session.session_id, [TextContentBlock(type="text", text="edit")])
    assert len(received) == 1
    assert received[0].session_id == session.session_id
    assert received[0].field_meta == meta
    assert len(updates) == 1
    assert isinstance(updates[0].update, AgentMessageChunk)
    assert updates[0].update.model_dump(mode="json", by_alias=True, exclude_none=True) == snapshot(
        {"content": {"text": "denied", "type": "text"}, "sessionUpdate": "agent_message_chunk"}
    )

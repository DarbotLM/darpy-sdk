"""Protocol-visible rejection and permission policy for DARPy ACP adapters."""

from collections.abc import AsyncIterator, Awaitable, Iterator
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from typing import NoReturn

import anyio
import pytest
from acp import PROTOCOL_VERSION, Agent, Client, RequestError
from acp import connect_to_agent as connect_official_peer
from acp.client.connection import ClientSideConnection
from acp.schema import (
    AllowedOutcome,
    DeniedOutcome,
    ImageContentBlock,
    McpServerStdio,
    PermissionOption,
    RequestPermissionRequest,
    RequestPermissionResponse,
    SessionNotification,
    TextContentBlock,
    ToolCallUpdate,
)
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from inline_snapshot import snapshot
from pydantic import JsonValue

from darpy_sdk.protocols.acp import ACPAgent, ACPClient, ACPConnection, connect_to_agent, permission_granted, run_agent
from darpy_sdk.runtime import Runtime, Task


class Endpoint:
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
async def running_agent(agent: ACPAgent) -> AsyncIterator[tuple[Endpoint, Endpoint, AsyncExitStack]]:
    left_send, right_receive = anyio.create_memory_object_stream[dict[str, JsonValue]](10)
    right_send, left_receive = anyio.create_memory_object_stream[dict[str, JsonValue]](10)
    # Keep LIFO cleanup without nested async-with tracing gaps on Python 3.14.
    async with AsyncExitStack() as lifetime:
        await lifetime.enter_async_context(left_send)
        await lifetime.enter_async_context(left_receive)
        await lifetime.enter_async_context(right_send)
        await lifetime.enter_async_context(right_receive)
        left, right = Endpoint(left_send, left_receive), Endpoint(right_send, right_receive)
        group = await lifetime.enter_async_context(anyio.create_task_group())
        group.start_soon(run_agent, agent, right)
        yield left, right, lifetime


async def unexpected_callback(*args: object, **kwargs: object) -> NoReturn:
    raise NotImplementedError


class IdlePeer(Client):
    session_update = unexpected_callback
    request_permission = unexpected_callback
    read_text_file = unexpected_callback
    write_text_file = unexpected_callback
    create_terminal = unexpected_callback
    terminal_output = unexpected_callback
    release_terminal = unexpected_callback
    wait_for_terminal_exit = unexpected_callback
    kill_terminal = unexpected_callback
    create_elicitation = unexpected_callback
    complete_elicitation = unexpected_callback
    ext_method = unexpected_callback
    ext_notification = unexpected_callback

    def on_connect(self, conn: Agent) -> None:
        self.connection = conn


@pytest.mark.anyio
async def test_invalid_session_operations_return_protocol_errors_without_running_tasks() -> None:
    """DARPy invalid operations neither execute tasks nor consume its bounded session pool.

    Steps: 1. Reject premature and invalid setup. 2. Fill a one-session pool.
    3. Reject invalid or unsupported operations.
    """

    async def execute(task: Task) -> str:
        raise NotImplementedError

    agent = ACPAgent(Runtime(execute), max_sessions=1)
    errors: dict[str, JsonValue] = {}

    @contextmanager
    def rejected(label: str, expected: RequestError) -> Iterator[None]:
        with pytest.raises(RequestError) as error:
            yield
        assert error.value.code == expected.code
        errors[label] = error.value.to_error_obj()

    # Keep rejection handling outside the connection teardown frame for reliable coverage tracing.
    async def exercise_invalid_operations(peer: ClientSideConnection) -> None:
        with rejected("before initialization", RequestError.invalid_request()):
            await peer.new_session("/workspace")
        await peer.initialize(protocol_version=1)
        with rejected("relative cwd", RequestError.invalid_params()):
            await peer.new_session("workspace")
        with rejected("relative additional directory", RequestError.invalid_params()):
            await peer.new_session("/workspace", additional_directories=["relative"])
        with rejected("MCP server configuration", RequestError.invalid_params()):
            await peer.new_session(
                "/workspace", mcp_servers=[McpServerStdio(name="unused", command="unused", args=[], env=[])]
            )
        session = await peer.new_session("C:\\workspace", additional_directories=["/shared"])
        with rejected("session capacity", RequestError.invalid_request()):
            await peer.new_session("/overflow")
        with rejected("unknown session", RequestError.invalid_params()):
            await peer.prompt("unknown", [])
        with rejected("unsupported image", RequestError.invalid_params()):
            await peer.prompt(session.session_id, [ImageContentBlock(type="image", data="AA==", mime_type="image/png")])
        with rejected("unsupported load", RequestError.method_not_found("")):
            await peer.load_session("/workspace", session.session_id)
        with rejected("unsupported list", RequestError.method_not_found("")):
            await peer.list_sessions()
        with rejected("unsupported mode", RequestError.method_not_found("")):
            await peer.set_session_mode(session.session_id, "unknown")
        with rejected("unsupported authentication", RequestError.method_not_found("")):
            await peer.authenticate("unknown")
        with rejected("unsupported extension", RequestError.method_not_found("")):
            await peer.ext_method("unknown", {})

    with anyio.fail_after(5):
        async with running_agent(agent) as (left, _right, lifetime):
            peer: ClientSideConnection = connect_official_peer(IdlePeer(), left)
            await lifetime.enter_async_context(peer)
            await exercise_invalid_operations(peer)
    assert errors == snapshot(
        {
            "before initialization": {
                "code": -32600,
                "message": "Invalid request",
                "data": {"reason": "Initialize before creating a session"},
            },
            "relative cwd": {
                "code": -32602,
                "message": "Invalid params",
                "data": {"reason": "Workspace paths must be absolute"},
            },
            "relative additional directory": {
                "code": -32602,
                "message": "Invalid params",
                "data": {"reason": "Workspace paths must be absolute"},
            },
            "MCP server configuration": {
                "code": -32602,
                "message": "Invalid params",
                "data": {"reason": "MCP server launching is not supported by this agent"},
            },
            "session capacity": {
                "code": -32600,
                "message": "Invalid request",
                "data": {"reason": "Session capacity reached; reconnect to start a new pool"},
            },
            "unknown session": {"code": -32602, "message": "Invalid params", "data": {"reason": "Unknown session"}},
            "unsupported image": {
                "code": -32602,
                "message": "Invalid params",
                "data": {"reason": "This agent supports text and resource links only"},
            },
            "unsupported load": {
                "code": -32601,
                "message": "Method not found",
                "data": {"method": "Unsupported DARPy capability"},
            },
            "unsupported list": {
                "code": -32601,
                "message": "Method not found",
                "data": {"method": "Unsupported DARPy capability"},
            },
            "unsupported mode": {
                "code": -32601,
                "message": "Method not found",
                "data": {"method": "Unsupported DARPy capability"},
            },
            "unsupported authentication": {
                "code": -32601,
                "message": "Method not found",
                "data": {"method": "Unsupported DARPy capability"},
            },
            "unsupported extension": {
                "code": -32601,
                "message": "Method not found",
                "data": {"method": "Unsupported DARPy capability"},
            },
        }
    )


def test_only_unique_offered_allow_options_authorize_execution() -> None:
    """ACP selections authorize only an offered allow option; cancellation and ambiguous offers never grant access."""
    options = [
        PermissionOption(option_id="once", name="Once", kind="allow_once"),
        PermissionOption(option_id="always", name="Always", kind="allow_always"),
        PermissionOption(option_id="reject", name="Reject", kind="reject_once"),
        PermissionOption(option_id="never", name="Never", kind="reject_always"),
    ]
    outcomes: dict[str, bool] = {}
    for option_id in ("once", "always", "reject", "never", "not-offered"):
        response = RequestPermissionResponse(outcome=AllowedOutcome(outcome="selected", option_id=option_id))
        outcomes[option_id] = permission_granted(response, options)
    outcomes["cancelled"] = permission_granted(
        RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled")), options
    )
    selected = RequestPermissionResponse(outcome=AllowedOutcome(outcome="selected", option_id="once"))
    outcomes["duplicate IDs"] = permission_granted(selected, [options[0], options[0]])
    outcomes["empty options"] = permission_granted(selected, [])
    assert outcomes == snapshot(
        {
            "once": True,
            "always": True,
            "reject": False,
            "never": False,
            "not-offered": False,
            "cancelled": False,
            "duplicate IDs": False,
            "empty options": False,
        }
    )


@pytest.mark.anyio
async def test_unknown_or_mutated_permission_choices_are_rejected_against_the_original_offer() -> None:
    """DARPy validates callback selections against offered wire IDs, even when the callback mutates its request."""
    current_choice = "unknown"
    errors: dict[str, JsonValue] = {}
    offered = [PermissionOption(option_id="original", name="Allow", kind="allow_once")]

    async def permission(request: RequestPermissionRequest) -> RequestPermissionResponse:
        assert request.tool_call.tool_call_id == "edit"
        assert request.options[0].option_id == "original"
        if current_choice == "mutation":
            request.options[0].option_id = "mutated"
        return RequestPermissionResponse(
            outcome=AllowedOutcome(
                outcome="selected", option_id="mutated" if current_choice == "mutation" else "unknown"
            )
        )

    async def execute(task: Task) -> str:
        assert task.prompt == "edit"
        return str(await agent.request_permission(task.session_id, ToolCallUpdate(tool_call_id="edit"), offered))

    async def update(notification: SessionNotification) -> None:
        raise NotImplementedError

    agent = ACPAgent(Runtime(execute))
    client = ACPClient(update, on_permission=permission)
    with anyio.fail_after(5):
        async with running_agent(agent) as (left, right, lifetime):
            connection: ACPConnection = connect_to_agent(client, left)
            await lifetime.enter_async_context(connection)
            await connection.initialize()
            session = await connection.new_session("/workspace")
            for current_choice in ("unknown", "mutation"):
                with pytest.raises(RequestError) as error:
                    await connection.prompt(session.session_id, [TextContentBlock(type="text", text="edit")])
                assert error.value.code == RequestError.invalid_params().code
                errors[current_choice] = error.value.to_error_obj()
    assert errors == snapshot(
        {
            "unknown": {
                "code": -32602,
                "message": "Invalid params",
                "data": {"reason": "Permission callback selected an unknown option"},
            },
            "mutation": {
                "code": -32602,
                "message": "Invalid params",
                "data": {"reason": "Permission callback selected an unknown option"},
            },
        }
    )
    requests = [message for message in right.sent if message.get("method") == "session/request_permission"]
    wire_options: list[JsonValue] = []
    for request in requests:
        params = request["params"]
        assert isinstance(params, dict)
        wire_options.append(params["options"])
    assert wire_options == snapshot(
        [
            [{"optionId": "original", "name": "Allow", "kind": "allow_once"}],
            [{"optionId": "original", "name": "Allow", "kind": "allow_once"}],
        ]
    )
    assert offered[0].option_id == "original"


@pytest.mark.anyio
async def test_agents_and_clients_reject_invalid_capacity_and_unguarded_or_reused_bindings() -> None:
    """DARPy validates session capacity and permits each agent/client to bind only one guarded connection."""

    async def execute(task: Task) -> str:
        raise NotImplementedError

    async def update(notification: SessionNotification) -> None:
        raise NotImplementedError

    errors: dict[str, str] = {}
    with pytest.raises(ValueError) as capacity:
        ACPAgent(Runtime(execute), max_sessions=0)
    errors["invalid capacity"] = str(capacity.value)
    agent, client = ACPAgent(Runtime(execute)), ACPClient(update)
    with pytest.raises(RuntimeError) as agent_unguarded:
        agent.on_connect(client)
    errors["unguarded agent"] = str(agent_unguarded.value)
    with pytest.raises(RuntimeError) as client_unguarded:
        client.on_connect(agent)
    errors["unguarded client"] = str(client_unguarded.value)
    with anyio.fail_after(5):
        async with running_agent(agent) as (left, right, lifetime):
            connection = await lifetime.enter_async_context(client.connect(left))
            await connection.initialize()
            with pytest.raises(RuntimeError) as agent_reused:
                await agent.serve(right)
            errors["reused agent"] = str(agent_reused.value)
            with pytest.raises(RuntimeError) as client_reused:
                client.connect(left)
            errors["reused client"] = str(client_reused.value)
            with pytest.raises(RuntimeError) as client_hook_reused:
                client.on_connect(agent)
            errors["reused client hook"] = str(client_hook_reused.value)
            assert (await connection.new_session("/workspace")).session_id
    assert errors == snapshot(
        {
            "invalid capacity": "max_sessions must be positive",
            "unguarded agent": "Use darpy_sdk.protocols.acp.run_agent to install the metadata boundary",
            "unguarded client": "Use darpy_sdk.protocols.acp.connect_to_agent to install the metadata boundary",
            "reused agent": "Create a separate ACPAgent for each connection",
            "reused client": "Create a separate ACPClient for each connection",
            "reused client hook": "Create a separate ACPClient for each connection",
        }
    )


@pytest.mark.anyio
@pytest.mark.parametrize("peer_kind", ["official", "darpy"])
async def test_disconnected_and_overlapping_prompts_fail_without_disturbing_the_active_turn(peer_kind: str) -> None:
    """DARPy rejects unavailable or busy sessions at both the client facade and the actual agent boundary.

    Steps: 1. Reject disconnected operations. 2. Hold a live prompt.
    3. Reject an overlapping prompt and finish the first.
    """
    started, release = anyio.Event(), anyio.Event()
    errors: dict[str, JsonValue] = {}

    async def execute(task: Task) -> str:
        assert task.prompt == "active"
        started.set()
        await release.wait()
        raise RequestError.invalid_request({"reason": "The test handler finished"})

    async def update(notification: SessionNotification) -> None:
        raise NotImplementedError

    async def rejected(label: str, request: Awaitable[object], expected: RequestError) -> None:
        with pytest.raises(RequestError) as error:
            await request
        assert error.value.code == expected.code
        errors[label] = error.value.to_error_obj()

    disconnected = ACPAgent(Runtime(execute))
    await disconnected.initialize(PROTOCOL_VERSION)
    session = await disconnected.new_session("/workspace")
    tool = ToolCallUpdate(tool_call_id="unused")
    await rejected("disconnected prompt", disconnected.prompt(session.session_id, []), RequestError.invalid_request())
    await rejected(
        "disconnected permission",
        disconnected.request_permission(session.session_id, tool, []),
        RequestError.invalid_request(),
    )
    await rejected(
        "unknown permission", disconnected.request_permission("unknown", tool, []), RequestError.invalid_params()
    )
    agent = ACPAgent(Runtime(execute))
    with anyio.fail_after(5):
        async with running_agent(agent) as (left, _right, lifetime):
            peer = (
                connect_official_peer(IdlePeer(), left)
                if peer_kind == "official"
                else connect_to_agent(ACPClient(update), left)
            )
            await lifetime.enter_async_context(peer)
            await peer.initialize(protocol_version=PROTOCOL_VERSION)
            live = await peer.new_session("/workspace")

            async def active_prompt() -> None:
                await rejected(
                    "active turn finished",
                    peer.prompt(live.session_id, [TextContentBlock(type="text", text="active")]),
                    RequestError.invalid_request(),
                )

            prompts = await lifetime.enter_async_context(anyio.create_task_group())
            prompts.start_soon(active_prompt)
            await started.wait()
            await peer.cancel("unknown")
            await rejected(
                "overlapping prompt",
                peer.prompt(live.session_id, [TextContentBlock(type="text", text="overlap")]),
                RequestError.invalid_request(),
            )
            release.set()
    assert errors == snapshot(
        {
            "disconnected prompt": {
                "code": -32600,
                "message": "Invalid request",
                "data": {"reason": "Agent is not connected"},
            },
            "disconnected permission": {
                "code": -32600,
                "message": "Invalid request",
                "data": {"reason": "Agent is not connected"},
            },
            "unknown permission": {"code": -32602, "message": "Invalid params", "data": {"reason": "Unknown session"}},
            "overlapping prompt": {
                "code": -32600,
                "message": "Invalid request",
                "data": {"reason": "A prompt is already active in this session"},
            },
            "active turn finished": {
                "code": -32600,
                "message": "Invalid request",
                "data": {"reason": "The test handler finished"},
            },
        }
    )


@pytest.mark.anyio
async def test_missing_permission_policy_cancels_and_duplicate_options_fail_before_callback() -> None:
    """DARPy requires an explicit policy to approve work and rejects ambiguous option IDs before policy dispatch."""
    updates: list[SessionNotification] = []
    option = PermissionOption(option_id="allow", name="Allow", kind="allow_once")

    async def permission(request: RequestPermissionRequest) -> RequestPermissionResponse:
        raise NotImplementedError

    async def execute(task: Task) -> str:
        assert task.prompt in {"missing policy", "duplicate options"}
        options = [option, option] if task.prompt == "duplicate options" else [option]
        return str(await agent.request_permission(task.session_id, ToolCallUpdate(tool_call_id="work"), options))

    async def update(notification: SessionNotification) -> None:
        updates.append(notification)

    agent, client = ACPAgent(Runtime(execute)), ACPClient(update)
    with anyio.fail_after(5):
        async with running_agent(agent) as (left, _right, lifetime):
            connection = await lifetime.enter_async_context(connect_to_agent(client, left))
            await connection.initialize()
            session = await connection.new_session("/workspace")
            await connection.prompt(session.session_id, [TextContentBlock(type="text", text="missing policy")])
            client.on_permission = permission
            with pytest.raises(RequestError) as error:
                await connection.prompt(session.session_id, [TextContentBlock(type="text", text="duplicate options")])
            assert error.value.code == RequestError.invalid_params().code
            assert error.value.to_error_obj() == snapshot(
                {
                    "code": -32602,
                    "message": "Invalid params",
                    "data": {"reason": "Permission option identifiers must be unique"},
                }
            )
            assert len(updates) == 1
            assert updates[0].session_id == session.session_id
            assert updates[0].update.model_dump(mode="json", by_alias=True, exclude_none=True) == snapshot(
                {"content": {"text": "False", "type": "text"}, "sessionUpdate": "agent_message_chunk"}
            )
            assert [message["result"] for message in left.sent if "result" in message] == snapshot(
                [{"outcome": {"outcome": "cancelled"}}]
            )


@pytest.mark.anyio
async def test_permission_approval_during_cancellation_send_is_returned_as_cancelled() -> None:
    """An in-flight cancellation prevents approval even while its transport is still draining.

    Steps: 1. Hold permission. 2. Deliver cancel but hold send completion.
    3. Return an allow choice and inspect the wire.
    """
    permission_started, release_choice, permission_settled, prompt_finished = (anyio.Event() for _ in range(4))

    class DrainingEndpoint(Endpoint):
        async def send(self, message: dict[str, JsonValue]) -> None:
            await super().send(message)
            if message.get("method") == "session/cancel":
                release_choice.set()
                await permission_settled.wait()
            elif "result" in message:
                permission_settled.set()

    async def update(notification: SessionNotification) -> None:
        raise NotImplementedError

    async def permission(request: RequestPermissionRequest) -> RequestPermissionResponse:
        assert request.tool_call.tool_call_id == "work"
        permission_started.set()
        await release_choice.wait()
        return RequestPermissionResponse(outcome=AllowedOutcome(outcome="selected", option_id="allow"))

    async def execute(task: Task) -> str:
        assert task.prompt == "work"
        try:
            return str(
                await agent.request_permission(
                    task.session_id,
                    ToolCallUpdate(tool_call_id="work"),
                    [PermissionOption(option_id="allow", name="Allow", kind="allow_once")],
                )
            )
        finally:
            with anyio.CancelScope(shield=True):
                await permission_settled.wait()

    agent = ACPAgent(Runtime(execute))
    with anyio.fail_after(5):
        async with running_agent(agent) as (left, _right, lifetime):
            outgoing = DrainingEndpoint(left.outgoing, left.incoming)
            connection = await lifetime.enter_async_context(
                connect_to_agent(ACPClient(update, on_permission=permission), outgoing)
            )
            await connection.initialize()
            session = await connection.new_session("/workspace")

            async def prompt() -> None:
                result = await connection.prompt(session.session_id, [TextContentBlock(type="text", text="work")])
                assert result.stop_reason == "cancelled"
                prompt_finished.set()

            prompts = await lifetime.enter_async_context(anyio.create_task_group())
            prompts.start_soon(prompt)
            await permission_started.wait()
            await connection.cancel(session.session_id)
            await prompt_finished.wait()
            assert [message["result"] for message in outgoing.sent if "result" in message] == snapshot(
                [{"outcome": {"outcome": "cancelled"}}]
            )


@pytest.mark.anyio
async def test_settling_one_permission_retains_other_requests_for_session_cancellation() -> None:
    """Completing one permission preserves cancellation tracking for another request in the same session.

    Steps: 1. Hold two permission callbacks. 2. Allow the first. 3. Cancel the turn and inspect both wire responses.
    """
    first_started, second_started, release_first = (anyio.Event() for _ in range(3))
    first_completed, second_finished, prompt_finished = (anyio.Event() for _ in range(3))

    async def update(notification: SessionNotification) -> None:
        raise NotImplementedError

    async def permission(request: RequestPermissionRequest) -> RequestPermissionResponse:
        assert request.tool_call.tool_call_id in {"first", "second"}
        if request.tool_call.tool_call_id == "first":
            first_started.set()
            await release_first.wait()
            return RequestPermissionResponse(outcome=AllowedOutcome(outcome="selected", option_id="allow"))
        second_started.set()
        try:
            await anyio.Event().wait()
            raise NotImplementedError
        finally:
            second_finished.set()

    async def execute(task: Task) -> str:
        assert task.prompt == "parallel permissions"

        async def ask(tool_id: str) -> None:
            assert await agent.request_permission(
                task.session_id,
                ToolCallUpdate(tool_call_id=tool_id),
                [PermissionOption(option_id="allow", name="Allow", kind="allow_once")],
            )
            first_completed.set()

        async with anyio.create_task_group() as requests:
            requests.start_soon(ask, "first")
            requests.start_soon(ask, "second")
        raise NotImplementedError

    agent = ACPAgent(Runtime(execute))
    with anyio.fail_after(5):
        async with running_agent(agent) as (left, _right, lifetime):
            connection = await lifetime.enter_async_context(
                connect_to_agent(ACPClient(update, on_permission=permission), left)
            )
            await connection.initialize()
            session = await connection.new_session("/workspace")

            async def prompt() -> None:
                result = await connection.prompt(
                    session.session_id, [TextContentBlock(type="text", text="parallel permissions")]
                )
                assert result.stop_reason == "cancelled"
                prompt_finished.set()

            prompts = await lifetime.enter_async_context(anyio.create_task_group())
            prompts.start_soon(prompt)
            await first_started.wait()
            await second_started.wait()
            release_first.set()
            await first_completed.wait()
            assert not second_finished.is_set()
            await connection.cancel(session.session_id)
            await prompt_finished.wait()
            await second_finished.wait()
            assert [message["result"] for message in left.sent if "result" in message] == snapshot(
                [{"outcome": {"optionId": "allow", "outcome": "selected"}}, {"outcome": {"outcome": "cancelled"}}]
            )

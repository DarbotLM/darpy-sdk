"""Guarded Agent Client Protocol agents, clients, and stdio lifecycle helpers."""

import json
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, NoReturn
from uuid import uuid4

import anyio
from acp import PROTOCOL_VERSION, Agent, Client, RequestError, update_agent_message_text
from acp import connect_to_agent as upstream_connect
from acp import run_agent as upstream_run
from acp.client.connection import ClientSideConnection
from acp.schema import (
    AcpMcpServer,
    AgentCapabilities,
    AllowedOutcome,
    AudioContentBlock,
    ClientCapabilities,
    DeniedOutcome,
    EmbeddedResourceContentBlock,
    HttpMcpServer,
    ImageContentBlock,
    Implementation,
    InitializeResponse,
    McpServerStdio,
    NewSessionResponse,
    PermissionOption,
    PromptCapabilities,
    PromptResponse,
    RequestPermissionRequest,
    RequestPermissionResponse,
    ResourceContentBlock,
    SessionNotification,
    SseMcpServer,
    TextContentBlock,
    ToolCallUpdate,
)
from acp.stdio import stdio_streams
from acp.transports import spawn_stdio_transport

from darpy_sdk.protocols._acp_compat import (
    MessageTransport,
    MetadataTransport,
    StdioTransport,
    decode_meta,
    encode_meta,
)
from darpy_sdk.runtime import Runtime, Task

ContentBlock = (
    TextContentBlock | ImageContentBlock | AudioContentBlock | ResourceContentBlock | EmbeddedResourceContentBlock
)
McpServer = HttpMcpServer | SseMcpServer | AcpMcpServer | McpServerStdio
UpdateHandler = Callable[[SessionNotification], Awaitable[None]]
PermissionHandler = Callable[[RequestPermissionRequest], Awaitable[RequestPermissionResponse]]
_BUFFER_LIMIT = 50 * 1024 * 1024

__all__ = [
    "ACPAgent",
    "ACPClient",
    "ACPConnection",
    "MessageTransport",
    "connect_to_agent",
    "permission_granted",
    "run_agent",
    "spawn_agent_process",
]


async def _unsupported(*args: object, **kwargs: Any) -> NoReturn:
    raise RequestError.method_not_found("Unsupported DARPy capability")


def _absolute(path: str) -> bool:
    return PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute()


@dataclass
class _Session:
    cwd: str
    additional_directories: list[str]
    scope: anyio.CancelScope | None = None


class ACPAgent(Agent):
    """Serve text and resource links in bounded, connection-local sessions.

    Use this module's ``run_agent`` to install the metadata boundary. MCP server
    launching, persistence, session modes, filesystem, and terminals are not
    implemented. Supplied MCP server configurations are explicitly rejected.
    """

    load_session = _unsupported
    list_sessions = _unsupported
    set_session_mode = _unsupported
    set_config_option = _unsupported
    authenticate = _unsupported
    fork_session = _unsupported
    resume_session = _unsupported
    close_session = _unsupported
    ext_method = _unsupported

    def __init__(self, runtime: Runtime, *, name: str = "darpy-sdk", max_sessions: int = 128) -> None:
        if type(max_sessions) is not int or max_sessions < 1:
            raise ValueError("max_sessions must be positive")
        self.runtime = runtime
        self.name = name
        self.max_sessions = max_sessions
        self._client: Client | None = None
        self._guarded = False
        self._initialized = False
        self._sessions: dict[str, _Session] = {}

    def on_connect(self, conn: Client) -> None:
        """Bind one guarded connection to this agent instance."""
        if not self._guarded:
            raise RuntimeError("Use darpy_sdk.protocols.acp.run_agent to install the metadata boundary")
        if self._client is not None:
            raise RuntimeError("Create a separate ACPAgent for each connection")
        self._client = conn

    async def serve(self, transport: MessageTransport) -> None:
        """Serve a single connection with the required metadata boundary."""
        guarded_transport = MetadataTransport(transport)
        self._guarded = True
        await upstream_run(self, guarded_transport)

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: ClientCapabilities | None = None,
        client_info: Implementation | None = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        """Negotiate the protocol and advertise the baseline text/resource support."""
        self._initialized = True
        return InitializeResponse(
            protocol_version=PROTOCOL_VERSION,
            agent_info=Implementation(name=self.name, version=version("darpy-sdk")),
            agent_capabilities=AgentCapabilities(
                load_session=False,
                prompt_capabilities=PromptCapabilities(image=False, audio=False, embedded_context=False),
            ),
            auth_methods=[],
        )

    async def new_session(
        self,
        cwd: str,
        additional_directories: list[str] | None = None,
        mcp_servers: list[McpServer] | None = None,
        **kwargs: Any,
    ) -> NewSessionResponse:
        """Create an isolated session with absolute workspace roots.

        Raises:
            RequestError: Initialization, configuration, path, or capacity checks fail.
        """
        if not self._initialized:
            raise RequestError.invalid_request({"reason": "Initialize before creating a session"})
        if mcp_servers:
            raise RequestError.invalid_params({"reason": "MCP server launching is not supported by this agent"})
        if not all(_absolute(path) for path in [cwd, *(additional_directories or [])]):
            raise RequestError.invalid_params({"reason": "Workspace paths must be absolute"})
        if len(self._sessions) >= self.max_sessions:
            raise RequestError.invalid_request({"reason": "Session capacity reached; reconnect to start a new pool"})
        session_id = uuid4().hex
        self._sessions[session_id] = _Session(cwd, list(additional_directories or []))
        return NewSessionResponse(session_id=session_id)

    async def prompt(self, session_id: str, prompt: list[ContentBlock], **kwargs: Any) -> PromptResponse:
        """Emit output as a session update and return the turn's stop reason.

        Raises:
            RequestError: The session is unknown, busy, or content is unsupported.
        """
        session = self._session(session_id)
        if session.scope is not None:
            raise RequestError.invalid_request({"reason": "A prompt is already active in this session"})
        if not all(isinstance(block, TextContentBlock | ResourceContentBlock) for block in prompt):
            raise RequestError.invalid_params({"reason": "This agent supports text and resource links only"})
        if self._client is None:
            raise RequestError.invalid_request({"reason": "Agent is not connected"})
        task = Task(
            prompt="\n".join(
                block.text if isinstance(block, TextContentBlock) else f"{block.name}: {block.uri}"
                for block in prompt
                if isinstance(block, TextContentBlock | ResourceContentBlock)
            ),
            session_id=session_id,
            protocol="acp",
            cwd=session.cwd,
            payload_json=json.dumps(
                {
                    "additionalDirectories": session.additional_directories,
                    "prompt": [block.model_dump(mode="json", by_alias=True, exclude_none=True) for block in prompt],
                    "_meta": decode_meta(kwargs),
                },
                allow_nan=False,
            ),
        )
        try:
            with anyio.CancelScope() as scope:
                session.scope = scope
                result = await self.runtime.run(task)
                await self._client.session_update(session_id, update_agent_message_text(result.text))
            return PromptResponse(stop_reason="cancelled" if scope.cancel_called else "end_turn")
        finally:
            session.scope = None

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        """Cancel an active turn; its original prompt returns the outcome."""
        session = self._sessions.get(session_id)
        if session is not None and session.scope is not None:
            session.scope.cancel()

    async def request_permission(
        self,
        session_id: str,
        tool_call: ToolCallUpdate,
        options: list[PermissionOption],
        *,
        meta: dict[str, Any] | None = None,
    ) -> bool:
        """Ask the connected client and allow only an offered allow selection.

        Raises:
            RequestError: The session or connection is unavailable, or the peer rejects the request.
        """
        self._session(session_id)
        if self._client is None:
            raise RequestError.invalid_request({"reason": "Agent is not connected"})
        offered = [option.model_copy(deep=True) for option in options]
        response = await self._client.request_permission(session_id, tool_call, offered, **encode_meta(meta))
        return permission_granted(response, offered)

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Ignore unknown extension notifications, which cannot receive replies."""

    def _session(self, session_id: str) -> _Session:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise RequestError.invalid_params({"reason": "Unknown session"}) from exc


def permission_granted(response: RequestPermissionResponse, options: list[PermissionOption]) -> bool:
    """Authorize only a unique, explicitly selected offered allow option."""
    if len({option.option_id for option in options}) != len(options):
        return False
    outcome = response.outcome
    return isinstance(outcome, AllowedOutcome) and any(
        option.option_id == outcome.option_id and option.kind in {"allow_once", "allow_always"} for option in options
    )


class ACPClient(Client):
    """Receive updates and delegate permission decisions; default to cancellation.

    Filesystem, terminal, and elicitation capabilities are not implemented.
    """

    read_text_file = _unsupported
    write_text_file = _unsupported
    create_terminal = _unsupported
    terminal_output = _unsupported
    release_terminal = _unsupported
    wait_for_terminal_exit = _unsupported
    kill_terminal = _unsupported
    create_elicitation = _unsupported
    ext_method = _unsupported

    def __init__(self, on_update: UpdateHandler, *, on_permission: PermissionHandler | None = None) -> None:
        self.on_update = on_update
        self.on_permission = on_permission
        self._permissions: dict[str, set[anyio.CancelScope]] = {}
        self._active_sessions: set[str] = set()
        self._cancelled_sessions: set[str] = set()
        self._guarded = False
        self._connected = False

    def connect(self, transport: MessageTransport) -> "ACPConnection":
        """Bind this client to one guarded connection.

        Raises:
            RuntimeError: This client has already been bound to a connection.
        """
        if self._connected:
            raise RuntimeError("Create a separate ACPClient for each connection")
        self._guarded = True
        return ACPConnection(self, upstream_connect(self, MetadataTransport(transport)))

    def begin_prompt(self, session_id: str) -> None:
        """Open a prompt window for permission requests in this session.

        Raises:
            RequestError: Another prompt is already active in this client session.
        """
        if session_id in self._active_sessions:
            raise RequestError.invalid_request({"reason": "A prompt is already active in this session"})
        self._active_sessions.add(session_id)
        self._cancelled_sessions.discard(session_id)

    def cancel_permissions(self, session_id: str) -> None:
        """Cancel current and late-arriving permission requests for a session."""
        self.mark_cancelled(session_id)
        for scope in tuple(self._permissions.get(session_id, ())):
            scope.cancel()

    def mark_cancelled(self, session_id: str) -> None:
        """Prevent approvals while a cancellation notification is being sent."""
        self._cancelled_sessions.add(session_id)

    def end_prompt(self, session_id: str) -> None:
        """Close a prompt window and settle any remaining permission callbacks."""
        self.cancel_permissions(session_id)
        self._active_sessions.discard(session_id)

    def on_connect(self, conn: Agent) -> None:
        """Require a guarded, single-connection lifecycle."""
        if not self._guarded:
            raise RuntimeError("Use darpy_sdk.protocols.acp.connect_to_agent to install the metadata boundary")
        if self._connected:
            raise RuntimeError("Create a separate ACPClient for each connection")
        self._connected = True

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        """Deliver the typed update with opaque metadata kept separate."""
        await self.on_update(SessionNotification(session_id=session_id, update=update, field_meta=decode_meta(kwargs)))

    async def request_permission(
        self,
        session_id: str,
        tool_call: ToolCallUpdate,
        options: list[PermissionOption],
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        """Return the callback's selection, or cancel when no callback exists.

        Raises:
            RequestError: Options are ambiguous or the callback selects an unoffered identifier.
        """
        offered_ids = frozenset(option.option_id for option in options)
        if len(offered_ids) != len(options):
            raise RequestError.invalid_params({"reason": "Permission option identifiers must be unique"})
        if (
            self.on_permission is None
            or session_id not in self._active_sessions
            or session_id in self._cancelled_sessions
        ):
            return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))
        scopes = self._permissions.setdefault(session_id, set())
        scope = anyio.CancelScope()
        response = RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))
        try:
            with scope:
                scopes.add(scope)
                response = await self.on_permission(
                    RequestPermissionRequest(
                        session_id=session_id,
                        tool_call=tool_call,
                        options=options,
                        field_meta=decode_meta(kwargs),
                    )
                )
            if scope.cancel_called or session_id in self._cancelled_sessions:
                return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))
        finally:
            scopes.discard(scope)
            if not scopes:
                self._permissions.pop(session_id, None)
        if isinstance(response.outcome, AllowedOutcome) and response.outcome.option_id not in offered_ids:
            raise RequestError.invalid_params({"reason": "Permission callback selected an unknown option"})
        return response

    async def complete_elicitation(self, elicitation_id: str, **kwargs: Any) -> None:
        """Ignore completions for unsupported elicitations."""

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Ignore unknown extension notifications."""


class ACPConnection:
    """A guarded connection exposing the text/resource-link client lifecycle."""

    def __init__(self, client: ACPClient, connection: ClientSideConnection) -> None:
        self._client = client
        self._connection = connection

    async def initialize(self, *, protocol_version: int = PROTOCOL_VERSION) -> InitializeResponse:
        """Initialize without advertising unimplemented client capabilities."""
        return await self._connection.initialize(
            protocol_version=protocol_version, client_capabilities=ClientCapabilities()
        )

    async def new_session(
        self,
        cwd: str,
        *,
        additional_directories: list[str] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> NewSessionResponse:
        """Create a session without implicitly launching MCP servers."""
        return await self._connection.new_session(
            cwd=cwd, additional_directories=additional_directories, mcp_servers=[], **encode_meta(meta)
        )

    async def prompt(
        self,
        session_id: str,
        prompt: Sequence[ContentBlock],
        *,
        meta: dict[str, Any] | None = None,
    ) -> PromptResponse:
        """Send content and opaque metadata through distinct protocol fields."""
        self._client.begin_prompt(session_id)
        try:
            return await self._connection.prompt(session_id=session_id, prompt=list(prompt), **encode_meta(meta))
        finally:
            self._client.end_prompt(session_id)

    async def cancel(self, session_id: str, *, meta: dict[str, Any] | None = None) -> None:
        """Notify cancellation; await the original prompt for completion."""
        self._client.mark_cancelled(session_id)
        try:
            await self._connection.cancel(session_id=session_id, **encode_meta(meta))
        finally:
            self._client.cancel_permissions(session_id)

    async def close(self) -> None:
        """Close the connection and its owned transport."""
        await self._connection.close()

    async def __aenter__(self) -> "ACPConnection":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()


def connect_to_agent(client: ACPClient, transport: MessageTransport) -> ACPConnection:
    """Connect through the metadata boundary; close or use as an async context."""
    return client.connect(transport)


async def run_agent(agent: ACPAgent, transport: MessageTransport | None = None) -> None:
    """Serve an agent using guarded messages; default to official stdio framing.

    Uses ACP's asyncio transport implementation. Create one agent per connection.
    """
    if transport is None:
        reader, writer = await stdio_streams(limit=_BUFFER_LIMIT)
        transport = StdioTransport(reader, writer)
    await agent.serve(transport)


@asynccontextmanager
async def spawn_agent_process(
    client: ACPClient,
    command: str,
    *args: str,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> AsyncIterator[ACPConnection]:
    """Launch an ACP subprocess using official lifecycle/framing and guarded metadata."""
    async with spawn_stdio_transport(command, *args, cwd=cwd, env=env, stderr=None, limit=_BUFFER_LIMIT) as streams:
        reader, writer, _ = streams
        async with connect_to_agent(client, StdioTransport(reader, writer)) as connection:
            yield connection

"""Exercise the real ACP subprocess boundary and upstream NDJSON framing."""

import asyncio
import os
import sys
from collections.abc import AsyncIterator, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from importlib.metadata import version
from pathlib import Path

import anyio
import pytest
from acp.schema import AgentMessageChunk, SessionNotification, TextContentBlock
from acp.transports import spawn_stdio_transport
from inline_snapshot import snapshot
from pydantic import JsonValue

import darpy_sdk.protocols.acp as acp_adapter
from darpy_sdk.protocols.acp import ACPClient, spawn_agent_process

_ECHO_AGENT = """
import anyio
from darpy_sdk.protocols.acp import ACPAgent, run_agent
from darpy_sdk.runtime import Runtime, Task

async def echo(task: Task) -> str:
    return task.prompt

anyio.run(run_agent, ACPAgent(Runtime(echo)), backend="asyncio")
"""


def _coverage_env() -> dict[str, str]:
    # ACP filters inherited variables; coverage's serialized config retains absolute data/source paths.
    return {
        key: value for key, value in os.environ.items() if key in {"COVERAGE_PROCESS_CONFIG", "COVERAGE_PROCESS_START"}
    }


@pytest.mark.anyio
async def test_stdio_process_preserves_large_unicode_prompt_and_guarded_session(tmp_path: Path) -> None:
    """SDK subprocess integration preserves NDJSON framing beyond the default 64 KiB reader limit."""
    updates: list[SessionNotification] = []

    async def update(notification: SessionNotification) -> None:
        updates.append(notification)

    client = ACPClient(update)
    text = "ready 🌍\n" * 10_000
    assert version("agent-client-protocol") == "0.12.1"
    async with AsyncExitStack() as stack:
        # Cold coverage and ACP/Pydantic imports exceeded five seconds under hosted xdist.
        with anyio.fail_after(20):
            connection = await stack.enter_async_context(
                spawn_agent_process(client, sys.executable, "-c", _ECHO_AGENT, cwd=tmp_path, env=_coverage_env())
            )
            initialization = await connection.initialize()
            assert initialization.protocol_version == 1
        with anyio.fail_after(5):
            session = await connection.new_session(str(tmp_path))
            result = await connection.prompt(
                session.session_id,
                [TextContentBlock(type="text", text=text)],
                meta={"session_id": "injected", "self": "injected"},
            )
            assert result.stop_reason == "end_turn"
    assert len(updates) == 1
    assert updates[0].session_id == session.session_id
    assert isinstance(updates[0].update, AgentMessageChunk)
    assert isinstance(updates[0].update.content, TextContentBlock)
    assert updates[0].update.content.text == text


@pytest.mark.anyio
@pytest.mark.parametrize("blocked_write", [False, True])
async def test_cancellation_reaps_a_nonreading_child_during_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, blocked_write: bool
) -> None:
    """SDK cancellation reaps a child while initialization or a full input pipe is blocked.

    A typed ACP peer cannot intentionally stop reading its pipe; this child sends readiness then stops reading.
    Steps: 1. Observe wire readiness. 2. Observe the request's actual drain. 3. Cancel and assert the child is reaped.
    """
    bootstrap = """
import json
import threading

print(json.dumps({"jsonrpc": "2.0", "method": "_ready", "params": {}}), flush=True)
threading.Event().wait()
"""
    ready, drain_started, drain_completed = anyio.Event(), anyio.Event(), anyio.Event()
    processes: list[asyncio.subprocess.Process] = []
    buffer_sizes: list[int] = []

    @asynccontextmanager
    async def observe_process(
        command: str,
        *args: str,
        cwd: str | Path | None = None,
        env: Mapping[str, str] | None = None,
        stderr: int | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[tuple[asyncio.StreamReader, asyncio.StreamWriter, asyncio.subprocess.Process]]:
        async with spawn_stdio_transport(command, *args, cwd=cwd, env=env, stderr=stderr, limit=limit) as streams:
            processes.append(streams[2])
            writer = streams[1]
            original_drain = writer.drain

            async def observe_drain() -> None:
                buffer_sizes.append(writer.transport.get_write_buffer_size())
                drain_started.set()
                await original_drain()
                drain_completed.set()

            monkeypatch.setattr(writer, "drain", observe_drain)
            yield streams

    async def update(notification: SessionNotification) -> None:
        raise NotImplementedError

    class ReadyClient(ACPClient):
        async def ext_notification(self, method: str, params: dict[str, JsonValue]) -> None:
            assert method == "ready"
            assert params == {}
            ready.set()

    monkeypatch.setattr(acp_adapter, "spawn_stdio_transport", observe_process)
    with anyio.CancelScope() as owner:
        async with AsyncExitStack() as stack:
            # Readiness includes cold interpreter/coverage startup under hosted xdist.
            with anyio.fail_after(20):
                connection = await stack.enter_async_context(
                    spawn_agent_process(
                        ReadyClient(update), sys.executable, "-c", bootstrap, cwd=tmp_path, env=_coverage_env()
                    )
                )
                await ready.wait()

            async def request() -> None:
                if blocked_write:
                    await connection.new_session(str(tmp_path), meta={"large": "x" * 2_000_000})
                else:
                    await connection.initialize()

            requests = await stack.enter_async_context(anyio.create_task_group())
            with anyio.fail_after(5):
                requests.start_soon(request)
                await drain_started.wait()
                if blocked_write:
                    assert buffer_sizes[0] > 0
                    assert not drain_completed.is_set()
            owner.cancel()
    assert owner.cancelled_caught
    assert len(processes) == 1
    assert processes[0].returncode is not None
    assert processes[0].returncode != 0


@pytest.mark.anyio
async def test_reused_client_failure_closes_the_new_process_and_sender(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SDK binding failure releases the new child's resources without disturbing the original connection."""
    processes: list[asyncio.subprocess.Process] = []

    @asynccontextmanager
    async def observe_process(
        command: str,
        *args: str,
        cwd: str | Path | None = None,
        env: Mapping[str, str] | None = None,
        stderr: int | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[tuple[asyncio.StreamReader, asyncio.StreamWriter, asyncio.subprocess.Process]]:
        async with spawn_stdio_transport(command, *args, cwd=cwd, env=env, stderr=stderr, limit=limit) as streams:
            processes.append(streams[2])
            yield streams

    async def update(notification: SessionNotification) -> None:
        raise NotImplementedError

    monkeypatch.setattr(acp_adapter, "spawn_stdio_transport", observe_process)
    client = ACPClient(update)
    async with AsyncExitStack() as lifetime:
        # This readiness response includes cold interpreter/coverage/schema startup under hosted xdist.
        with anyio.fail_after(20):
            connection = await lifetime.enter_async_context(
                spawn_agent_process(client, sys.executable, "-c", _ECHO_AGENT, cwd=tmp_path, env=_coverage_env())
            )
            assert (await connection.initialize()).protocol_version == 1
        original_senders = {task.id for task in anyio.get_running_tasks() if task.name == "acp.Sender.loop"}
        with pytest.raises(RuntimeError) as error:
            await lifetime.enter_async_context(
                spawn_agent_process(
                    client,
                    sys.executable,
                    "-c",
                    "import sys; sys.stdin.buffer.read()",
                    cwd=tmp_path,
                    env=_coverage_env(),
                )
            )
        assert str(error.value) == snapshot("Create a separate ACPClient for each connection")
        assert len(processes) == 2
        assert processes[1].returncode is not None
        assert {task.id for task in anyio.get_running_tasks() if task.name == "acp.Sender.loop"} == original_senders
        with anyio.fail_after(5):
            assert (await connection.new_session(str(tmp_path))).session_id

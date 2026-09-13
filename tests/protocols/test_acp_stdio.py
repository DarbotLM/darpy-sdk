"""Exercise the real ACP subprocess boundary and upstream NDJSON framing."""

import os
import sys
from importlib.metadata import version
from pathlib import Path

import anyio
import pytest
from acp.schema import AgentMessageChunk, SessionNotification, TextContentBlock

from darpy_sdk.protocols.acp import ACPClient, spawn_agent_process


@pytest.mark.anyio
async def test_stdio_process_preserves_large_unicode_prompt_and_guarded_session(tmp_path: Path) -> None:
    """SDK subprocess integration preserves NDJSON framing beyond the default 64 KiB reader limit."""
    bootstrap = """
import anyio
from darpy_sdk.protocols.acp import ACPAgent, run_agent
from darpy_sdk.runtime import Runtime, Task

async def echo(task: Task) -> str:
    return task.prompt

anyio.run(run_agent, ACPAgent(Runtime(echo)), backend="asyncio")
"""
    updates: list[SessionNotification] = []

    async def update(notification: SessionNotification) -> None:
        updates.append(notification)

    client = ACPClient(update)
    text = "ready 🌍\n" * 10_000
    # ACP filters inherited variables; coverage's serialized config retains absolute data/source paths.
    coverage_env = {
        key: value for key, value in os.environ.items() if key in {"COVERAGE_PROCESS_CONFIG", "COVERAGE_PROCESS_START"}
    }
    assert version("agent-client-protocol") == "0.12.1"
    with anyio.fail_after(5):
        async with spawn_agent_process(
            client, sys.executable, "-c", bootstrap, cwd=tmp_path, env=coverage_env
        ) as connection:
            initialization = await connection.initialize()
            assert initialization.protocol_version == 1
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

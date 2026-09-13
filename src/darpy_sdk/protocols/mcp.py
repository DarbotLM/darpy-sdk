"""Expose runtime handlers through the SDK's inherited MCP implementation."""

import json

from darpy_sdk import Client
from darpy_sdk.runtime import BudgetExceededError, Runtime, Task
from darpy_sdk.server import MCPServer
from darpy_sdk.server.mcpserver import Context
from darpy_sdk.server.mcpserver.exceptions import ToolError
from darpy_sdk.types import RequestParams

__all__ = ["Client", "MCPServer", "create_server"]


def create_server(runtime: Runtime, *, name: str = "DARPy") -> MCPServer:
    """Create an MCP server exposing a typed ``darpy_run`` tool.

    The host configures transports and authentication. The caller-provided
    session identifier is correlation data, not an authorization credential.
    Runtime task payloads retain tool arguments and request metadata without
    treating metadata as trusted identity or runtime controls.
    Budget violations return an MCP tool error carrying the budget message.
    """
    server = MCPServer(name)

    async def darpy_run(prompt: str, session_id: str, ctx: Context) -> str:
        """Run a handler in the caller-selected logical session."""
        payload = {
            "name": "darpy_run",
            "arguments": {"prompt": prompt, "session_id": session_id},
            "_meta": RequestParams(_meta=ctx.request_context.meta).model_dump(
                mode="json", by_alias=True, exclude_unset=True
            )["_meta"],
        }
        try:
            result = await runtime.run(
                Task(
                    prompt,
                    session_id,
                    protocol="mcp",
                    payload_json=json.dumps(payload, ensure_ascii=False, allow_nan=False),
                    request_id=str(ctx.request_id),
                )
            )
        except BudgetExceededError as exc:
            raise ToolError(str(exc)) from exc
        return result.text

    server.tool()(darpy_run)
    return server

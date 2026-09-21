"""`docs/get-started/testing.md`: the page's own test, run for real.

The page shows this test against a `server.py` next to it; here the import path
is the only difference.
"""

import pytest
from darpy_sdk_types import CallToolResult, TextContent
from inline_snapshot import snapshot

from darpy_sdk import Client
from docs_src.testing.tutorial001 import mcp
from tests.docs_src._helpers import strip_server_info

# See test_index.py for why this is a per-module mark and not a conftest hook.
pytestmark = [pytest.mark.anyio, pytest.mark.filterwarnings("error::darpy_sdk.MCPDeprecationWarning")]


async def test_call_add_tool() -> None:
    async with Client(mcp, raise_exceptions=True) as client:
        result = await client.call_tool("add", {"a": 1, "b": 2})
        result = strip_server_info(result, mcp)
        assert result == snapshot(
            CallToolResult(content=[TextContent(type="text", text="3")], structured_content={"result": 3})
        )

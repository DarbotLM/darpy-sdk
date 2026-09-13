from collections.abc import Sequence
from typing import Any

from pydantic import Field

import darpy_sdk.types as types
from darpy_sdk.server.context import ServerRequestContext
from darpy_sdk.server.extension import Extension, MethodBinding
from darpy_sdk.server.mcpserver import MCPServer, require_client_extension

EXTENSION_ID = "com.example/search"


class SearchParams(types.RequestParams):
    query: str
    limit: int = Field(default=10, ge=1, le=100)


class SearchResult(types.Result):
    items: list[str]


async def search(ctx: ServerRequestContext[Any, Any], params: SearchParams) -> SearchResult:
    require_client_extension(ctx, EXTENSION_ID)
    return SearchResult(items=[f"{params.query}-{n}" for n in range(params.limit)])


class Search(Extension):
    """An extension that serves its own request method."""

    identifier = EXTENSION_ID

    def methods(self) -> Sequence[MethodBinding]:
        return [
            MethodBinding(
                "com.example/search",
                SearchParams,
                search,
                protocol_versions=frozenset({"2026-07-28"}),
            )
        ]


mcp = MCPServer("catalog", extensions=[Search()])

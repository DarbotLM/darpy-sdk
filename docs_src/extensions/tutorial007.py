from collections.abc import Sequence
from typing import Any

import darpy_sdk.types as types
from darpy_sdk.server.context import ServerRequestContext
from darpy_sdk.server.extension import Extension, MethodBinding
from darpy_sdk.server.mcpserver import MCPServer

EXTENSION_ID = "com.example/jobs"


class JobParams(types.RequestParams):
    job_id: str


class JobStatus(types.Result):
    status: str


async def job_status(ctx: ServerRequestContext[Any, Any], params: JobParams) -> JobStatus:
    return JobStatus(status=f"{params.job_id} is running")


class Jobs(Extension):
    """An extension whose verb names its subject, so the header can route on it."""

    identifier = EXTENSION_ID

    def methods(self) -> Sequence[MethodBinding]:
        return [MethodBinding("com.example/jobs.status", JobParams, job_status)]


mcp = MCPServer("worker", extensions=[Jobs()])

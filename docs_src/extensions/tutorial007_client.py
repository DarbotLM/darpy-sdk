from typing import Literal

import anyio

import darpy_sdk.types as types
from darpy_sdk import Client
from darpy_sdk.client import advertise

EXTENSION_ID = "com.example/jobs"


class JobParams(types.RequestParams):
    job_id: str


class JobStatus(types.Result):
    status: str


class JobStatusRequest(types.Request[JobParams, Literal["com.example/jobs.status"]]):
    method: Literal["com.example/jobs.status"] = "com.example/jobs.status"
    params: JobParams
    name_param = "jobId"  # params["jobId"] rides the Mcp-Name header


async def main() -> None:
    async with Client("http://localhost:8000/mcp", extensions=[advertise(EXTENSION_ID)]) as client:
        request = JobStatusRequest(params=JobParams(job_id="job-7"))
        result = await client.session.send_request(request, JobStatus)
        print(result.status)
        # job-7 is running


if __name__ == "__main__":
    anyio.run(main)

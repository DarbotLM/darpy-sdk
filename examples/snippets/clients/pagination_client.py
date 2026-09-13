"""Example of consuming paginated MCP endpoints from a client."""

import asyncio

from darpy_sdk.client.session import ClientSession
from darpy_sdk.client.stdio import StdioServerParameters, stdio_client
from darpy_sdk.types import PaginatedRequestParams, Resource


async def list_all_resources() -> None:
    """Fetch all resources using pagination."""
    async with stdio_client(StdioServerParameters(command="uv", args=["run", "darpy-sdk-simple-pagination"])) as (
        read,
        write,
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()

            all_resources: list[Resource] = []
            cursor = None

            while True:
                # Fetch a page of resources
                result = await session.list_resources(params=PaginatedRequestParams(cursor=cursor))
                all_resources.extend(result.resources)

                print(f"Fetched {len(result.resources)} resources")

                # Check if there are more pages
                if result.next_cursor:
                    cursor = result.next_cursor
                else:
                    break

            print(f"Total resources: {len(all_resources)}")


if __name__ == "__main__":
    asyncio.run(list_all_resources())

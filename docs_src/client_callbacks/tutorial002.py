from darpy_sdk import Client
from darpy_sdk.client import ClientRequestContext
from darpy_sdk.types import ElicitRequestParams, ElicitResult


async def handle_elicitation(
    context: ClientRequestContext,
    params: ElicitRequestParams,
) -> ElicitResult:
    return ElicitResult(action="accept", content={"name": "Ada Lovelace"})


async def main() -> None:
    async with Client(
        "http://127.0.0.1:8000/mcp",
        mode="legacy",
        elicitation_callback=handle_elicitation,
    ) as client:
        result = await client.call_tool("issue_card")
        print(result.content)

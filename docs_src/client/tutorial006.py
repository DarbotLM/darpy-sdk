import anyio

from darpy_sdk import Client
from darpy_sdk.types import PromptReference


async def main() -> None:
    async with Client("http://localhost:8000/mcp") as client:
        result = await client.complete(
            ref=PromptReference(type="ref/prompt", name="recommend"),
            argument={"name": "genre", "value": "p"},
        )
        print(result.completion.values)


if __name__ == "__main__":
    anyio.run(main)

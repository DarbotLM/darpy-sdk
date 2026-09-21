import anyio

from darpy_sdk import Client


async def main() -> None:
    async with Client("http://localhost:8000/mcp", mode="legacy") as client:
        print(client.protocol_version)


if __name__ == "__main__":
    anyio.run(main)

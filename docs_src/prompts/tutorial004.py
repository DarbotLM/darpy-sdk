from pathlib import Path

from darpy_sdk.server import MCPServer
from darpy_sdk.server.mcpserver import Message, UserMessage
from darpy_sdk.types import EmbeddedResource, TextResourceContents

mcp = MCPServer("Code Helper")

STYLE_GUIDE_FILE = Path(__file__).parent / "style-guide.md"  # or the path to your file on disk


@mcp.resource("style://python", mime_type="text/markdown")
def style_guide() -> str:
    """The team's Python style guide."""
    return STYLE_GUIDE_FILE.read_text(encoding="utf-8")


@mcp.prompt()
def review_code(code: str) -> list[Message]:
    """Review a piece of code against the team style guide."""
    guide = TextResourceContents(uri="style://python", mime_type="text/markdown", text=style_guide())
    return [
        UserMessage(EmbeddedResource(resource=guide)),
        UserMessage(f"Review this code against the style guide above:\n\n{code}"),
    ]

from pathlib import Path

from darpy_sdk.server import MCPServer
from darpy_sdk.server.mcpserver import Image

mcp = MCPServer("Brand kit")

LOGO_FILE = Path(__file__).parent / "logo.png"  # or the path to your file on disk


@mcp.tool()
def logo() -> Image:
    """The brand logo as a PNG."""
    return Image(path=LOGO_FILE)

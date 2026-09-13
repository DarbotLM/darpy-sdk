from pathlib import Path

from darpy_sdk.server import MCPServer
from darpy_sdk.server.mcpserver import Image

mcp = MCPServer("Brand kit")

LOGO_FILE = Path(__file__).parent / "logo.png"


@mcp.tool()
def logo_from_bytes() -> Image:
    """The brand logo as a PNG."""
    png = LOGO_FILE.read_bytes()  # a database read, an HTTP response, Pillow output...
    return Image(data=png, format="png")

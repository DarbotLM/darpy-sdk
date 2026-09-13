from pathlib import Path

from darpy_sdk.server import MCPServer
from darpy_sdk.server.mcpserver.exceptions import ResourceNotFoundError
from darpy_sdk.shared.path_security import safe_join

mcp = MCPServer("Bookshop")

DOCS_ROOT = Path("./manuals")


@mcp.resource("manuals://{+path}")
def read_manual(path: str) -> str:
    """A staff manual page, served from a directory on disk."""
    file = safe_join(DOCS_ROOT, path)
    if not file.is_file():
        raise ResourceNotFoundError(f"No manual at {path!r}.")
    return file.read_text(encoding="utf-8")

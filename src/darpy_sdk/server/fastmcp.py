"""Use `darpy_sdk.server.mcpserver.MCPServer` in the Darbot Python SDK.

This module has no API. Importing it, or anything below it, raises
`ModuleNotFoundError` with a message that points at the migration guide. It
exists only because the bare "No module named 'darpy_sdk.server.fastmcp'" gave v1
code no hint about the Darbot Python SDK's supported server API.
"""

_MESSAGE = (
    "No module named 'darpy_sdk.server.fastmcp'. The Darbot Python SDK provides MCPServer "
    "(from darpy_sdk.server.mcpserver import MCPServer). See the Darbot SDK documentation at "
    "https://github.com/DarbotLM/darpy-sdk#readme."
)

raise ModuleNotFoundError(_MESSAGE, name=__name__)

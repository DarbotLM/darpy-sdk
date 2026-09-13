"""The MCP protocol wire types, as the `darpy_sdk.types` namespace.

This module mirrors the standalone `darpy_sdk_types` package exactly (every name is the
same object), so SDK users can keep the familiar v1 spelling:

    import darpy_sdk.types as types

    types.TextContent(type="text", text="hi")

The `darpy_sdk.types.jsonrpc`, `darpy_sdk.types.methods`, and `darpy_sdk.types.version`
submodules mirror `darpy_sdk_types.jsonrpc`, `darpy_sdk_types.methods`, and
`darpy_sdk_types.version` the same way, so every supported `darpy_sdk_types` import has
an `darpy_sdk.types` spelling.

Depend on and import `darpy_sdk_types` directly instead when you only need to
(de)serialize MCP traffic and don't want the SDK's transport stack: its only
runtime dependencies are `pydantic` and `typing-extensions`.
"""

# A wildcard mirror of the darpy_sdk_types namespace is the whole point of this module.
# pyright: reportWildcardImportFromLibrary=false

from darpy_sdk_types import *
from darpy_sdk_types import __all__ as __all__

# Bind the mirror submodules on the package, so `darpy_sdk.types.version.X` is as
# reachable by attribute access as `darpy_sdk_types.version.X` (whose `__init__`
# binds `.version` by importing from it), not only via `from ... import`.
from . import jsonrpc as jsonrpc
from . import methods as methods
from . import version as version

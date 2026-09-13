"""The MCP method registry, as the `darpy_sdk.types.methods` namespace.

A mirror of `darpy_sdk_types.methods` (every name is the same object), so code that
depends on `darpy-sdk` can import from `darpy_sdk.types.methods` without importing the
`darpy_sdk_types` distribution directly. Depend on and import `darpy_sdk_types.methods`
instead when you use `darpy-sdk-types` without the SDK.
"""

# A wildcard mirror of the darpy_sdk_types.methods namespace is the whole point of this module.
# pyright: reportWildcardImportFromLibrary=false

from darpy_sdk_types.methods import *
from darpy_sdk_types.methods import __all__ as __all__

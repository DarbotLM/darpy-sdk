"""The JSON-RPC 2.0 message and error types, as the `darpy_sdk.types.jsonrpc` namespace.

A mirror of `darpy_sdk_types.jsonrpc` (every name is the same object), so code that
depends on `darpy-sdk` can import from `darpy_sdk.types.jsonrpc` without importing the
`darpy_sdk_types` distribution directly. Depend on and import `darpy_sdk_types.jsonrpc`
instead when you use `darpy-sdk-types` without the SDK.
"""

# A wildcard mirror of the darpy_sdk_types.jsonrpc namespace is the whole point of this module.
# pyright: reportWildcardImportFromLibrary=false

from darpy_sdk_types.jsonrpc import *
from darpy_sdk_types.jsonrpc import __all__ as __all__

"""The protocol-version registry, as the `darpy_sdk.types.version` namespace.

A mirror of `darpy_sdk_types.version` (every name is the same object), so code that
depends on `darpy-sdk` can write `from darpy_sdk.types.version import LATEST_MODERN_VERSION`
without importing the `darpy_sdk_types` distribution directly. Depend on and import
`darpy_sdk_types.version` instead when you use `darpy-sdk-types` without the SDK.
"""

# A wildcard mirror of the darpy_sdk_types.version namespace is the whole point of this module.
# pyright: reportWildcardImportFromLibrary=false

from darpy_sdk_types.version import *
from darpy_sdk_types.version import __all__ as __all__

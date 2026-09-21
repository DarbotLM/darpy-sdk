# Darbot Python SDK Types

The wire types for the [Model Context Protocol](https://modelcontextprotocol.io).

This package holds the protocol message models, JSON-RPC envelope types, per-version
surface validators, and the protocol-version registry. Its only runtime dependencies are
`pydantic` and `typing-extensions`, so it can be installed on its own when you need to
(de)serialize MCP traffic without pulling in the full `darpy-sdk` SDK.

```python
from darpy_sdk_types import Tool, CallToolRequest
from darpy_sdk_types.version import LATEST_PROTOCOL_VERSION
```

The `darpy_sdk` package re-exports these names, so `from darpy_sdk import Tool` imports
keep working.

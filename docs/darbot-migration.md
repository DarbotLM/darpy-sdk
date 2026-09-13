# Migrate to Darbot Python SDK

Darbot Python SDK is a framework fork with a new distribution, import namespace,
CLI, and release line. The root implementation lives in this repository; it is
not a wrapper requiring the upstream MCP SDK at runtime. Darbot 0.1.0 derives
from upstream MCP SDK 2.2.0, preserving its protocol implementation while adding
optional integrations described in [Protocol integrations](protocols.md).

## Package and command map

| Upstream identity | Darbot identity |
| --- | --- |
| `mcp` distribution | `darpy-sdk` distribution |
| `mcp` Python package | `darpy_sdk` Python package |
| `mcp-types` distribution | `darpy-sdk-types` distribution |
| `mcp_types` Python package | `darpy_sdk_types` Python package |
| `mcp` CLI | `darpy-sdk` CLI |
| MCP Python SDK product name | Darbot Python SDK |
| Upstream 2.2.0 code baseline | Independent Darbot 0.1.0 release line |
| Upstream repository | `DarbotLM/darpy-sdk` |

The separate [DARPy platform](https://github.com/DarbotLM/darpy) continues to use
`darpy` and the `darpy` CLI. Do not merge its import package with `darpy_sdk`.

## Python runtime baseline

Darbot Python SDK, its standalone types package, and all bundled example
projects require **Python 3.14 or newer**. Update application metadata to
`requires-python = ">=3.14"`, Ruff targets to `py314`, and Pyright's
`pythonVersion` to `3.14`. Recreate development environments with
`uv sync --frozen --python 3.14 --all-extras` from the SDK checkout.

The examples use standard-library `tomllib` and `typing.TypedDict` directly.
The SDK still uses typing extensions for features beyond the Python 3.14
standard library, such as `TypedDict(extra_items=...)`. MCP wire revisions and
schema dates are independent of the Python runtime version.

## Update current application imports

Before, with the upstream SDK:

```python
from mcp import Client
from mcp.server import MCPServer
from mcp.types import Tool
import mcp_types
```

After, with the Darbot SDK:

```python
from darpy_sdk import Client
from darpy_sdk.server import MCPServer
from darpy_sdk.types import Tool
import darpy_sdk_types
```

Nested public modules retain their relative layout: for example,
`mcp.client.stdio` becomes `darpy_sdk.client.stdio`, and
`mcp.server.mcpserver` becomes `darpy_sdk.server.mcpserver`.
The `darpy_sdk.types` surface mirrors the standalone `darpy_sdk_types` package;
choose the import corresponding to the distribution your project depends on.

Update string-based module references as well as normal imports: plugin/module
configuration, `python -m` invocations, monkeypatch targets, importlib lookups,
coverage/type-check paths, documentation references, and executable metadata.
The new packages do not install a top-level `mcp` compatibility alias that could
shadow an independently installed upstream SDK.

## Versions and dependency resolution

Install both Darbot distributions from the same release. The root SDK requires
`darpy-sdk-types==0.1.0`; later releases must retain an exact matching types pin.
Do not transfer an upstream constraint such as `mcp>=2,<3` to the Darbot name:
the initial Darbot release is 0.1.0, not 2.x. Use [Installation](get-started/installation.md)
for source-workspace use until the new package pair is published.

The public distribution names normalize to wheel names beginning with
`darpy_sdk-` and `darpy_sdk_types-`. Their import names are always underscore
forms. The standalone types wheel must work without the SDK's HTTP stack.
Application environments may contain unrelated upstream MCP dependents; this
rename removes the SDK's own dependency on `mcp`, not those other packages'
requirements.

## CLI and host configurations

In the synchronized Darbot checkout:

```bash
uv run --frozen darpy-sdk version
uv run --frozen darpy-sdk run server.py --transport streamable-http
```

After configuring an installable Darbot package source, replace `mcp dev`,
`mcp run`, and `mcp install` with `darpy-sdk dev`, `darpy-sdk run`, and
`darpy-sdk install`. The helpers that create fresh environments must resolve the
Darbot package and its matching types distribution. During checkout development,
a host can invoke:

```bash
uv run --frozen --directory /absolute/path/to/darpy-sdk darpy-sdk run /absolute/path/to/server.py
```

The CLI still recognizes a server instance named `mcp`, `server`, or `app`, or an
explicit `server.py:object` suffix. A local variable named `mcp` is not a package
import and does not require renaming.

## Keep the protocol unchanged

MCP remains Model Context Protocol. Preserve interoperable protocol identities:

- HTTP headers including `mcp-protocol-version`, `mcp-session-id`, and `Mcp-Param-*`.
- JSON keys such as `mcpServers`, specification method names, and `_meta` fields.
- MCP schema IDs, protocol revision dates, extension URIs, and conformance-harness variables.
- External package names such as `@modelcontextprotocol/inspector`.
- Protocol-specific classes such as `MCPServer`, `MCPError`, and `MCPDeprecationWarning`.

Keep upstream copyright notices and historical references. A blanket text
replacement of every `mcp` token would corrupt these contracts. Only owned
package, framework, CLI, tooling, and product identities move to Darbot names.

## Porting older MCP applications

An application using upstream MCP v1 first needs the API changes documented in
[the historical upstream migration guide](migration.md). Its old `FastMCP`
imports, camelCase model attributes, and low-level callbacks are not restored by
the Darbot namespace migration. The [framework tour](whats-new.md) explains the
inherited client/server architecture. Historical snippets retain their upstream
names so their provenance is unambiguous.

## Verify the migration

Exercise the application against the renamed public APIs, then test package
installation outside the source checkout. Confirm CLI subprocesses use
`darpy-sdk`, both distribution versions match, and the SDK's client/server
round trips work without an upstream `mcp` installation. Preserve the existing
MCP conformance scenarios and the separately scoped ACP/Activity tests.

Repository CI and the strict documentation build are release gates, not evidence
of automatic production readiness. Remaining protocol limitations and publication
requirements are recorded in the roadmap and release policy.

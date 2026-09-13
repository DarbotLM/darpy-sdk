# Darbot Python SDK

**`darpy-sdk` is the DarbotLabs Python framework for model, agent, client,
activity, and context protocol runtime integration.**

The framework lives in this repository under `darpy_sdk`, with its standalone
wire types under `darpy_sdk_types`. It derives from the MCP Python SDK 2.2.0
implementation at commit `9972c21aa42054fb1450c5fc614761ed11847ec6` and retains
its client/server, transport, authentication, type-generation, and conformance
infrastructure. This is a full framework fork, with its own packages and
release line, rather than a wrapper that installs the upstream `mcp` package.
See [source attribution](NOTICE.md).

The initial Darbot version is **0.1.0**. It does not imply an upstream 2.x
release or a completed production certification. The package supports MCP and
adds optional Agent Client Protocol and Microsoft Activity integrations. The
separate [DARPy platform](https://github.com/DarbotLM/darpy) provides `darpy`;
this SDK provides `darpy_sdk` and the `darpy-sdk` CLI.

## Start from this checkout

Python 3.14+ is required for the SDK, standalone types, and example projects.
The locked optional protocol integrations use the same Python 3.14 baseline.

```bash
git clone https://github.com/DarbotLM/darpy-sdk.git
cd darpy-sdk
uv sync --frozen --python 3.14 --all-extras
uv run --frozen darpy-sdk version
uv run --frozen darpy-sdk doctor
```

Use the checkout and its lockfile until a DarbotLabs package release is
published. The repository contains release tooling; that alone does not mean
PyPI projects, trusted publishers, or a hosted documentation site are active.
[Installation](docs/get-started/installation.md) describes the package layout,
optional extras, and local distribution builds.

## Build an MCP server

Create `server.py`:

<!-- snippet-source docs_src/index/tutorial001.py -->
```python
from darpy_sdk.server import MCPServer

mcp = MCPServer("Demo")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@mcp.resource("greeting://{name}")
def greeting(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"
```

_Full example: [docs_src/index/tutorial001.py](https://github.com/DarbotLM/darpy-sdk/blob/main/docs_src/index/tutorial001.py)_
<!-- /snippet-source -->

Run the server from the synchronized checkout:

```bash
uv run --frozen darpy-sdk run server.py --transport streamable-http
```

MCP remains the protocol name. Paths such as `/mcp`, protocol headers,
`mcpServers` host configuration keys, and MCP specification URLs remain
unchanged so existing clients and hosts can interoperate.

## Connect a client

```python
import asyncio

from darpy_sdk import Client


async def main() -> None:
    async with Client("http://localhost:8000/mcp") as client:
        result = await client.call_tool("add", {"a": 1, "b": 2})
        print(result.structured_content)


asyncio.run(main())
```

The MCP client supports HTTP, stdio subprocesses, custom transports, and
in-memory servers. Optional integrations use `darpy_sdk.protocols.acp` and
`darpy_sdk.protocols.activity`; see [protocol integrations](docs/protocols.md)
for supported behavior and limits. Verified dependency baselines for this
work are `agent-client-protocol==0.12.1`,
`microsoft-agents-activity==1.5.0`, and
`microsoft-agents-hosting-core==1.5.0`. The lockfile records exact resolved
versions; installing a dependency alone is not a conformance result.

## Documentation

- [Framework guide](docs/index.md) and [installation](docs/get-started/installation.md)
- [Migration from upstream packages](docs/darbot-migration.md)
- [MCP client and server framework tour](docs/whats-new.md)
- [Protocol integrations](docs/protocols.md) and [protocol versions](docs/protocol-versions.md)
- [Roadmap](ROADMAP.md), [version policy](VERSIONING.md), and [release gates](RELEASE.md)
- [Contribution guide](CONTRIBUTING.md) and [security policy](SECURITY.md)

Build the API reference and documentation locally with
`bash scripts/docs/build.sh`. The strict build checks links and API rendering.
Language editions use current English fallback while inherited translations
await regeneration under the Darbot namespace; [translation status](docs/translations.md)
explains this explicitly.

## Verification

```bash
uv run --frozen ruff check .
uv run --frozen pyright
./scripts/test
uv run --frozen --group codegen python scripts/gen_surface_types.py --check
```

The retained test gate requires 100% branch coverage and checks unnecessary
coverage exclusions. CI also defines cross-version/platform and MCP conformance
jobs. Configured checks do not mean every hosted job has already passed.

## License

The SDK is MIT licensed. See [LICENSE](LICENSE) and [NOTICE](NOTICE.md) for
retained upstream copyright, source history, and DarbotLabs changes.

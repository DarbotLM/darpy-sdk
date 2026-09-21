# Installation

Darbot Python SDK has two distributions: `darpy-sdk` and `darpy-sdk-types`,
both version **0.1.0** in this development line. Both distributions and the
example projects require **Python 3.14+**. This is a separate package identity
from the upstream MCP SDK.

## Use the checkout

Until DarbotLabs publishes a package release, use the workspace so both local
packages resolve together:

```bash
git clone https://github.com/DarbotLM/darpy-sdk.git
cd darpy-sdk
uv sync --frozen --python 3.14 --all-extras
uv run --frozen darpy-sdk version
uv run --frozen darpy-sdk doctor
```

The source lockfile pins the development resolution. For an application that
uses built artifacts, build both wheels with `uv build --package darpy-sdk`
and `uv build --package darpy-sdk-types`, then supply both to its dependency
resolver. The SDK exact-pins its matching types package; distributing only the
SDK wheel before the types package is available is insufficient.

After a verified package release is published, a normal project can use
`uv add "darpy-sdk[cli]"`. Do not assume that a README, local wheel, or release
workflow means that name is already published. See [Darbot migration](../darbot-migration.md)
for the complete package/import/CLI mapping. The historical upstream
[v1 to v2 guide](../migration.md) is relevant only when porting old MCP API code.

## What gets installed

You don't need to know any of this to use the SDK, but if you're wondering what each dependency is for:

* `darpy-sdk-types`: every protocol type (requests, results, content blocks) as its own package, versioned in lockstep with the SDK. Code that depends on `darpy-sdk` imports it through the `darpy_sdk.types` alias (every `from darpy_sdk.types import ...` in these docs); import `darpy_sdk_types` directly only in a project that installs `darpy-sdk-types` without the SDK.
* [`anyio`](https://anyio.readthedocs.io/): the async runtime. The whole SDK is written against anyio, so it runs on either `asyncio` or `trio`.
* [`pydantic`](https://docs.pydantic.dev/): what every `darpy_sdk.types` model is built on, plus all schema generation and validation.
* [`httpx2`](https://pypi.org/project/httpx2/): the HTTP client behind the Streamable HTTP and SSE *client* transports, with server-sent events support built in.
* [`starlette`](https://www.starlette.io/), [`uvicorn`](https://www.uvicorn.org/), [`sse-starlette`](https://pypi.org/project/sse-starlette/), and [`python-multipart`](https://pypi.org/project/python-multipart/): the HTTP *server* transports.
* [`jsonschema`](https://pypi.org/project/jsonschema/): validates a tool's structured output against its declared output schema.
* [`pyjwt[crypto]`](https://pyjwt.readthedocs.io/): OAuth token handling for authorization.
* [`opentelemetry-api`](https://opentelemetry-python.readthedocs.io/): just the lightweight API, so the SDK's tracing middleware costs nothing unless you install an OpenTelemetry SDK and exporter yourself.
* [`typing-extensions`](https://typing-extensions.readthedocs.io/) and [`typing-inspection`](https://pypi.org/project/typing-inspection/): runtime annotation inspection and typing features beyond the Python 3.14 standard library, including `TypedDict(extra_items=...)`.
* [`pywin32`](https://pypi.org/project/pywin32/): Windows only, used for `stdio` subprocess management.

## Optional extras

* `darpy-sdk[cli]` adds [`typer`](https://typer.tiangolo.com/) and [`python-dotenv`](https://pypi.org/project/python-dotenv/) for the `darpy-sdk` command-line tool (`darpy-sdk dev`, `darpy-sdk run`, `darpy-sdk install`). You'll want this during development; you may not need it in a deployed server.
* `darpy-sdk[rich]` adds [`rich`](https://rich.readthedocs.io/) for nicer server logs.

* `darpy-sdk[acp]` adds `agent-client-protocol` for Agent Client Protocol.
* `darpy-sdk[activity]` adds `microsoft-agents-activity` for typed Activity integration.
* `darpy-sdk[hosting]` adds the Activity and hosting-core packages for hosted turn handling.
* `darpy-sdk[protocols]` selects the protocol integration dependencies together.

The locked optional integrations use the same Python 3.14 baseline. Their
supported runtime behavior and dependency versions are documented in
[Protocol integrations](../protocols.md). The MCP implementation is part of the
root SDK; it does not require an external `mcp` installation.

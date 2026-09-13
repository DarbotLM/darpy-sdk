# Darbot Python SDK

Darbot Python SDK is the DarbotLabs framework for model, agent, client,
activity, and context protocol runtime integration. The root package is
`darpy-sdk`, imported as `darpy_sdk`, with standalone types in
`darpy-sdk-types`, imported as `darpy_sdk_types`.

!!! info "Darbot 0.1.0 development line"
    This fork retains the MCP framework derived from upstream SDK 2.2.0 and adds
    optional ACP and Activity integrations. Darbot versions are independent of
    upstream SDK versions and protocol dates. Follow [Installation](get-started/installation.md)
    for checkout-based use before package publication, and
    [Darbot migration](darbot-migration.md) for package and CLI changes.

The **Model Context Protocol (MCP)** remains the standard used by the inherited
client/server implementation. You can build MCP servers exposing tools,
resources, and prompts, connect MCP clients over supported transports, and
integrate optional [Agent Client Protocol and Activity adapters](protocols.md).
The separate [DARPy platform](https://github.com/DarbotLM/darpy) uses `darpy`.

## Requirements

Python 3.10+.

## Installation

From this repository:

```bash
uv sync --frozen --all-extras
uv run --frozen darpy-sdk version
```

The `[cli]` extra provides the `darpy-sdk` command. See
[Installation](get-started/installation.md) for package dependencies, extras,
and local builds. `darpy-sdk dev` and host-install recipes that resolve fresh
package environments require published packages or an explicitly configured
local package source; direct `darpy-sdk run` works in the synchronized checkout.

## Example

### Create it

Create a file `server.py`:

```python title="server.py"
--8<-- "docs_src/index/tutorial001.py"
```

That's a complete MCP server.

It exposes one **tool**, `add`, and one templated **resource**, `greeting://{name}`.

### Run it

```console
uv run --frozen darpy-sdk run server.py
```

This starts the stdio server in the checkout environment. A compatible MCP host
can launch that command. After configuring an installable package source,
`darpy-sdk dev` can launch the [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
for interactive inspection.

!!! note
    The Inspector is a Node.js app, so `darpy-sdk dev` needs `npx` on your `PATH`.

### Try it

When using the Inspector, go to **Tools** and call `add` with `a=1`, `b=2`.

You get `3` back. ✨

The Inspector built that form (a required integer field for `a`, another for `b`) from your type hints. So will Claude, and every other MCP host.

Now go to **Resources** and read `greeting://World`:

```text
Hello, World!
```

### Recap

Look again at what you did **not** write:

* No JSON Schema. `a: int, b: int` *is* the schema.
* No request parsing, no serialization, no validation code.
* No protocol handling at all.

You wrote two Python functions with type hints and a docstring. The SDK does the rest.

## Where to go next

* **[Get started](get-started/index.md)** takes you from install to a working, tested server.
* Building an application that *uses* MCP servers? Start with **[Clients](client/index.md)**.
* Already have a FastAPI or Starlette app? **[Add to an existing app](run/asgi.md)** mounts an MCP server inside it.
* Hunting an exact error message? **[Troubleshooting](troubleshooting.md)** is keyed by the verbatim text.
* Wondering how the inherited MCP framework changed? **[What's new in v2](whats-new.md)** is the five-minute tour.
* Migrating an upstream MCP v1 application? Start with the **[Migration Guide](migration.md)**.
* Hunting for an exact signature? The **[API Reference](api/darpy_sdk/index.md)** is generated from the source.
* Reading with an LLM? This documentation is also published in the [llms.txt](https://llmstxt.org/) format:
  a local strict documentation build emits `llms.txt` and `llms-full.txt` alongside
  the generated site. Hosting those artifacts is a separate deployment step.

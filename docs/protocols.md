# Protocol adapters

Darbot Python SDK combines its inherited MCP implementation with optional Agent Client
Protocol and Microsoft Activity adapters. The distribution is `darpy-sdk`; Python
imports use `darpy_sdk`. Wire protocol names remain MCP, ACP, and Activity.

| Integration | Tested baseline | Scope |
| --- | --- | --- |
| MCP | Upstream MCP SDK 2.2.0, commit `9972c21aa42054fb1450c5fc614761ed11847ec6` | Inherited clients, servers, transports, and wire types |
| Agent Client Protocol | `agent-client-protocol==0.12.1`, protocol version 1 | Text and resource links, session isolation, cancellation, permissions, guarded stdio |
| Activity | `microsoft-agents-activity==1.5.0` | Raw envelopes, typed projections, message dispatch |
| Activity hosting | `microsoft-agents-hosting-core==1.5.0` | Existing authenticated turn pipeline and reply dispatch |

From the SDK checkout, install optional integrations explicitly:

```sh
uv sync --frozen --extra protocols
```

The smaller extras are `acp`, `activity`, and `hosting`. Importing `darpy_sdk` or
`darpy_sdk.protocols` does not import ACP or Activity. Package availability from
`darpy_sdk.capabilities.capabilities()` does not imply full protocol conformance.
After the package pair is published, application projects can use
`uv add 'darpy-sdk[protocols]'` instead.

## Application handler runtime

An SDK `Task` carries a prompt, session identifier, protocol name, optional working
directory, protocol payload JSON, and request identifier. Identifiers correlate
work; they do not establish identity or authorize access. The host supplies an
async handler and owns authentication, tool permissions, and persistence.

```python
from darpy_sdk.runtime import Runtime, Task


async def answer(task: Task) -> str:
    return f"Received through {task.protocol}: {task.prompt}"


runtime = Runtime(answer, max_concurrency=4)
```

`RunBudget` limits input/output Unicode characters and cooperative execution time,
including time queued for a concurrency slot. These are not model token or memory
limits. Handlers must yield and honor cancellation. No model, shell, filesystem,
or network operation occurs merely because a handler is registered.

## MCP

```python
from darpy_sdk.protocols.mcp import create_server

server = create_server(runtime)
server.run(transport="stdio")
```

The server exposes `darpy_run(prompt, session_id)`. Configure authentication and
remote transports using the normal SDK server APIs. MCP clients default to
automatic discovery: modern peers use `2026-07-28`; older peers negotiate the
legacy handshake. Use `mode="legacy"` when an integration explicitly needs legacy
server-initiated sampling, push elicitation, or roots. Protocol version selection
and DARPy release versioning are separate contracts.

## Agent Client Protocol

Serve an agent with the SDK wrapper, which installs the required metadata boundary:

```python
import anyio

from darpy_sdk.protocols.acp import ACPAgent, run_agent

if __name__ == "__main__":
    anyio.run(run_agent, ACPAgent(runtime), backend="asyncio")
```

Save the runtime and serving code together in `agent.py`. A client can launch it
through the official subprocess lifecycle and NDJSON framing:

```python
import sys

from acp.schema import SessionNotification, TextContentBlock
from darpy_sdk.protocols.acp import ACPClient, spawn_agent_process


async def on_update(notification: SessionNotification) -> None:
    print(notification.update)


async def talk() -> None:
    client = ACPClient(on_update)
    async with spawn_agent_process(client, sys.executable, "agent.py") as connection:
        await connection.initialize()
        session = await connection.new_session(cwd="/absolute/workspace")
        result = await connection.prompt(
            session.session_id,
            [TextContentBlock(type="text", text="Review the project")],
            meta={"darbotlabs/request": "example"},
        )
        print(result.stop_reason)
```

Each agent and client belongs to one connection. Sessions remain in memory; one
prompt can run per session, while different sessions may execute concurrently.
Cancel with `await connection.cancel(session_id)`, then await the original prompt
for its final `cancelled` stop reason. Cancellation also settles pending permission
callbacks in that session. Callbacks must cooperate with cancellation.

Permission callbacks receive the complete typed `RequestPermissionRequest`,
including its opaque `field_meta`, and return `RequestPermissionResponse`.
Absent a callback, requests are cancelled. A selected `reject_once` or
`reject_always` option is a rejection, even though upstream represents all selected
options with `AllowedOutcome`. `permission_granted()` authorizes only an offered,
unambiguous allow option. Unknown selected identifiers are rejected.

Resource links are preserved in `Task.payload_json` and rendered as `name: uri`
context in the prompt. The adapter does not fetch their URLs. Images, audio,
embedded resources, filesystem operations, terminal operations, session loading,
modes, and MCP server launching are not implemented by this initial agent/client.
Unsupported requests fail explicitly instead of advertising those capabilities.

### Metadata boundary

ACP 0.12.1 flattens `_meta` into Python keyword arguments; colliding keys can
otherwise replace `session_id`, `prompt`, and permission parameters. The SDK
wraps the complete metadata object internally before upstream dispatch and
restores it before outbound wire transmission. User keys and nested values remain
unchanged, including keys equal to the internal envelope key. Builtin requests
and notifications are covered in both directions; extension payloads, responses,
and errors are not rewritten. Incoming prompt metadata is available inside
`Task.payload_json` under `_meta`.

Use this module's `run_agent`, `connect_to_agent`, and `spawn_agent_process`
helpers. Connecting these adapters through upstream helpers directly is rejected.
The narrow stdio bridge reuses an upstream internal framing constructor and
requires exactly ACP 0.12.1. The 1.0.0rc1 prerelease still has the collision and is
not an automatic upgrade. ACP HTTP/WebSocket hosting is not advertised by these
wrappers; it requires its own verified metadata boundary.

## Microsoft Activity

```python
from darpy_sdk.protocols.activity import ActivityEnvelope, ActivityHandler

handler = ActivityHandler(runtime)
envelope = ActivityEnvelope.from_dict({
    "type": "message",
    "id": "incoming-1",
    "channelId": "example",
    "conversation": {"id": "conversation-1"},
    "from": {"id": "user-1"},
    "recipient": {"id": "agent-1"},
    "text": "Hello",
    "vendorExtension": {"keep": None},
})
```

Capture an envelope at raw ingress, before constructing an official Activity
model. `envelope.to_dict()` returns the preserved wire fields; `envelope.activity`
returns a fresh typed projection. Official models can drop unknown fields and
normalize entity keys, so serializing that projection is not lossless forwarding.
Wire `callerId` is retained only as opaque input and discarded from the projection;
it must never substitute for authenticated host identity.

Inside the existing authenticated Microsoft Agents turn pipeline:

```python
from microsoft_agents.hosting.core import TurnContext
from darpy_sdk.protocols.activity_hosting import handle_turn


async def on_turn(context: TurnContext) -> None:
    # In a real host, pass the envelope captured for this same inbound request.
    await handle_turn(context, handler)
```

Pass `envelope=raw_envelope` to retain original unknown fields in
`Task.payload_json`; its typed projection must match the current turn. Without
that argument, the adapter uses the already-normalized host Activity and cannot
recover discarded fields. Reply routing and dispatch go through
`TurnContext.send_activity`, preserving host middleware and response behavior.
Non-message activities return `False` for another host handler. Invoke, OAuth,
attachments, and channel authentication remain the host's responsibility.

## Connect the DARPy platform

The SDK does not require an unpublished `darpy` distribution. Applications with
the DARPy platform installed can bridge the two runtime contracts structurally:

```python
from darpy import Runtime as PlatformRuntime
from darpy import Task as PlatformTask
from darpy_sdk.runtime import Runtime as SDKRuntime
from darpy_sdk.runtime import Task as SDKTask


def bind_platform(platform: PlatformRuntime) -> SDKRuntime:
    async def dispatch(task: SDKTask) -> str:
        result = await platform.run(PlatformTask(
            prompt=task.prompt,
            session_id=task.session_id,
            protocol=task.protocol,
            cwd=task.cwd,
            payload_json=task.payload_json,
            request_id=task.request_id,
        ))
        return result.text

    return SDKRuntime(dispatch)
```

For local development, install the two checkouts together in the application's
environment with:

```sh
uv add --editable ../darpy-platform ../darpy-sdk ../darpy-sdk/src/darpy-sdk-types
```

This is an application choice, not an SDK runtime dependency. The platform uses
Python 3.12+, while the standalone SDK supports Python 3.10+.
Run this bridge with the asyncio backend because the platform runtime uses asyncio;
the standalone SDK runtime also supports Trio.

All SDK task fields shown above map directly. Raw protocol content remains JSON;
neither runtime interprets it as platform capabilities, authenticated principals,
or executable permissions. Each runtime applies its own configured limits, and
the inner platform receipt is intentionally reduced to text before the SDK creates
its outer receipt. Applications needing both receipts should explicitly record
the platform receipt using the shared request identifier.

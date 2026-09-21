# Legacy Darbot Python SDK examples

These inherited single-file MCP server demos now import `darpy_sdk`. They are
retained as migration references. The supported examples for the current Darbot
Python SDK are the [self-verifying stories](../stories/) and the tutorials in
[`docs_src`](../../docs_src/).

Renaming an import does not validate an older demo's complete runtime behavior.
This directory is outside the repository's normal strict type-checking scope.
The current migration check identifies these follow-up items:

| Example | Remaining migration or setup requirement |
| --- | --- |
| `logging_and_progress.py` | Calls the deprecated `Context.info` protocol logging API. Adapt the demo to the intended protocol revision before using it as a current example; use the maintained logging/progress tutorials for the supported behavior. |
| `memory.py` | Requires additional `asyncpg`, NumPy, OpenAI, pgvector, and pydantic-ai dependencies, a PostgreSQL/pgvector service, and provider configuration. Its inherited agent/dependency annotations and APIs still need a separate compatibility migration. |
| `screenshot.py` | Requires the optional PyAutoGUI desktop dependency and a usable graphical session; it was not exercised in the headless SDK checks. |
| `text_me.py` | Needs a Pydantic settings annotation update (`model_config` currently overrides a class variable), Surge account configuration, and separate verification of its external messaging integration. |

Other files in this directory were parsed and had their SDK imports checked;
that does not establish that their graphical, network, or external-service
integrations work. The package rename does not claim to repair these integrations
or to complete the legacy example migration. Migration work should add
deterministic tests before moving a demo into the maintained example suite.

The memory demo's own local profile directory is now `~/.darpy-sdk/USER/memory`.
It does not automatically read or move an older `~/.mcp/USER/memory` directory.

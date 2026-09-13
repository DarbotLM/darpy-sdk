# Darbot Python SDK 0.1 foundation validation

Verified on 2026-09-13 against the initial Darbot fork migration from
`9972c21aa42054fb1450c5fc614761ed11847ec6`. This record describes checks actually
run locally; the pull request's hosted matrix is the authority for other
Python, operating-system, and dependency-resolution combinations.

## Required engineering gates

| Check | Observed result |
| --- | --- |
| Full `scripts/test` suite, Python 3.12 on Linux | 6,028 passed, 8 skipped, 1 inherited expected failure |
| Coverage, including tests | 53,813 statements and 4,266 branches; 100.00%, zero missing statements or branches |
| `strict-no-cover` | No lines incorrectly marked `pragma: no cover` |
| Ruff lint and formatting | Passed across 861 Python files |
| Pyright | Zero errors or warnings |
| Lockfile consistency | Passed; 143 resolved packages |
| Generated wire models | Schema regeneration check passed |
| README generated snippets | Passed |
| Workflow JavaScript tests | 46 passed |
| Documentation tooling tests | 49 passed |
| Documentation builds | All 12 language targets passed; stale translations use current English fallback |
| API documentation | Cross-reference, inventory, and alternate import-order checks passed |
| Non-Python pre-commit hooks | End-of-file fixer, Prettier, and markdownlint passed |

The coverage gate retains the four upstream module exclusions and existing
documented pragmas. The four paths now match from a subprocess working
directory as well as the checkout. No additional modules are excluded and the
100% statement/branch threshold is unchanged. Ambient proxy variables were
cleared for local network tests; test processes used four xdist workers.

## Distribution and migration checks

- Root and standalone types wheels and source distributions build with the
  names `darpy-sdk` and `darpy-sdk-types`, both version `0.1.0`.
- The SDK's types dependency is exactly `darpy-sdk-types==0.1.0`.
- Wheels contain `darpy_sdk` and `darpy_sdk_types`. They contain no top-level
  `mcp`, `mcp_types`, or `darpy` package. No dependency on the upstream `mcp`
  distribution remains.
- All 17 project manifests and 22 example executable entry points use Darbot
  package identities. An AST audit of 861 Python files found no old package
  imports or parse errors.
- Vendored schema files and `schema/PINNED.json` are byte-for-byte unchanged.
  MCP protocol fields, headers, URLs, and historical source attribution remain
  intact; the package rename does not rename the protocol.
- Both wheel layouts retain their required license files. The root wheel
  includes the fork's provenance notice; the types distribution also builds
  with its license directly from its own source archive.

## Installed-package integration checks

Two fresh Python 3.12 environments were resolved from local wheels without an
editable checkout or source-directory imports:

1. SDK and types only: optional ACP, Microsoft Activity, and DARPy packages were
   absent. The base SDK imported, capability reporting reflected absent extras,
   and an MCP client/server round trip preserved nested and null metadata.
2. SDK, types, and the DARPy platform wheel: an explicit asyncio bridge carried
   every task context field into the platform runtime and preserved the result
   and request identity through the SDK.

Protocol-specific integration tests exercise real ACP stdio framing beyond
64 KiB, concurrent session cancellation and permission completion, reserved
metadata collisions, and actual Microsoft Activity `TurnContext` send hooks
and response routing. The runtime tests cover queue-inclusive deadlines,
input/output limits, cancellation, and asyncio/Trio operation.

## Scope and remaining release work

This change provides the owned framework and documented initial protocol
adapters. ACP filesystem/terminal operations, persistence, session modes, and
MCP-server launching are not implemented or advertised. Activity handling
routes messages; other activity types remain the host application's concern.
The runtime's cooperative deadlines are not a process sandbox or hard CPU
deadline.

The separate DARPy platform implements a tested scientific subset and local
team runtime. Full NumPy/SymPy behavior parity, distributed swarms, trained SWE
agents, and an automatic SkillOpt optimizer remain staged specification work.

No PyPI release or documentation deployment is asserted by these checks.
Follow [RELEASE.md](RELEASE.md), review the hosted CI matrix, and configure
DarbotLabs publishing identities before releasing packages.

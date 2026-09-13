# Versioning and support policy

`darpy-sdk` and `darpy-sdk-types` start a DarbotLabs release line at **0.1.0**.
This number is independent of the MCP Python SDK 2.2.0 implementation from
which the fork derives. MCP protocol revision dates are independent again.

## Package versions

Both distributions declare a static version in their `pyproject.toml` files.
The SDK requires exactly the matching types version; release both together.
A Git tag identifies the already-versioned source commit and does not compute
or replace package metadata. Keep tags, package versions, exact dependency pins,
lockfile metadata, and release notes consistent.

Use PEP 440 versions, including `aN`, `bN`, or `rcN` for prereleases. During 0.x,
a minor release may introduce a documented breaking API change; patches are
reserved for compatible corrections. Do not silently break existing users:
record affected imports, behavior, and migration steps before release. A future
1.0 release must define its stable compatibility commitment explicitly.

## Public surface

The public surface is the documented API and names deliberately exported through
`darpy_sdk.__all__` and `darpy_sdk_types.__all__`, including documented package
paths, optional extras, and CLI commands. Underscore-prefixed implementation
modules and undocumented helpers are internal. Provisional and experimental APIs
must retain those labels wherever documented.

MCP-specific names such as `MCPServer`, `MCPError`, and
`MCPDeprecationWarning` describe the supported protocol; they do not make the
package an upstream release. A protocol feature can be unavailable when a
connection negotiates a revision that does not include it, independently of
Python API availability.

## Support and announcements

Python 3.14 is the supported development and validation baseline for the SDK,
wire types, protocol extras, and examples. Package metadata requires Python
3.14 or newer. CI verifies Python 3.14 on Windows and Linux using both locked
and lowest direct dependency versions; older interpreters are unsupported.

`main` is the Darbot development line. This fork does not inherit upstream
1.x maintenance promises, triage deadlines, project boards, or trusted-publisher
configuration. Release notes state tested Python/platform/dependency matrices,
known limitations, and whether a particular release is supported.

Public package publication and any stable-support claim require the checks in
[RELEASE.md](RELEASE.md). Keep upstream source history in [NOTICE.md](NOTICE.md)
and current namespace instructions in [the Darbot migration guide](docs/darbot-migration.md).

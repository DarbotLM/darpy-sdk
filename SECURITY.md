# Security policy

Security reports for Darbot Python SDK belong to the DarbotLabs fork. MCP
protocol issues may also affect upstream implementations, but this repository
does not inherit another project's private reporting channel or support SLA.

## Supported scope

The initial Darbot package line is `darpy-sdk==0.1.0` with the matching
`darpy-sdk-types`. It is a development foundation derived from the upstream
MCP SDK 2.2.0 codebase; the Darbot version is independent. No upstream 1.x or
2.x support promise applies to this fork. Release notes and
[VERSIONING.md](VERSIONING.md) identify the actual Darbot support policy.

## Reporting

Use this repository's **Security → Report a vulnerability** option when private
vulnerability reporting is enabled. If it is unavailable, use contact information
made available by the maintainers on the
[DarbotLM GitHub profile](https://github.com/DarbotLM) to arrange private disclosure.
Do not disclose exploit details, credentials, or private user data in public
issues or pull requests. No unverified security email address is advertised here.

Include the affected Darbot version or commit, Python/platform/dependency
versions, a minimal reproduction, impact, and relevant protocol configuration.
Provide synthetic or redacted data where possible. A passing unit test does
not establish that arbitrary tool execution or a network deployment is isolated;
applications must configure authorization and execution boundaries appropriate
to their handlers.

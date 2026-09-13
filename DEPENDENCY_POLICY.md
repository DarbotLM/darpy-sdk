# Dependency Policy

`darpy-sdk` is a library that lives inside other people's environments, so its requirements in the static `pyproject.toml` are chosen to constrain your resolver as little as possible while still describing what the SDK needs.

## How requirements are declared

Every runtime dependency is a `>=` floor set to the oldest version that provides what the SDK uses, with no upper bound unless a dependency's next major is known to break the SDK. The one exception is `darpy-sdk-types`, the wire-types package released in lockstep with `darpy-sdk`: each `darpy-sdk` release requires exactly its own version of it, so it is the other half of the SDK rather than an independent constraint.

## When a floor moves

A floor is raised only when the SDK starts relying on functionality or a fix that first appeared in that version — not because the dependency published a security advisory. The `>=` bound already lets, and expects, you to run the newest release your other constraints allow, so a higher floor would only shrink the environments the SDK installs into; nor does the SDK add code to work around a dependency's vulnerability, since the fix belongs upstream and in your lockfile ([background](https://github.com/Kludex/uvicorn/discussions/2643), [python-sdk#1552](https://github.com/modelcontextprotocol/python-sdk/issues/1552)). Floor raises may ship in a minor release under the [versioning policy](VERSIONING.md) and are called out in the release notes. Adding a new runtime dependency, or moving one to its next major version, is decided in an issue before the pull request.

## Automated updates

[Dependabot](https://github.com/DarbotLM/darpy-sdk/blob/main/.github/dependabot.yml) is configured for monthly, grouped pull requests for the `uv` lockfile and for GitHub Actions. These refresh the versions the SDK is developed and tested against; the requirements published to PyPI move only under the rules above.

## Optional protocol baselines

The initial ACP integration is tested against `agent-client-protocol==0.12.1`.
Activity integration is tested against `microsoft-agents-activity==1.5.0` and
`microsoft-agents-hosting-core==1.5.0`. These are dated validation baselines,
not assertions that an unconstrained newest release has passed our tests.
Keep the integration boundaries optional, record resolved versions in the
lockfile, and re-run their behavioral checks when upgrading. Refer to
[protocol integrations](docs/protocols.md) for the supported surface.

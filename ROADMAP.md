# Darbot Python SDK roadmap

The SDK provides the protocol framework for the separate
[DARPy platform](https://github.com/DarbotLM/darpy). DarbotLabs owns the
`darpy_sdk` and `darpy_sdk_types` namespaces and release metadata in this fork.

## Initial foundation

- Refactor the inherited SDK into `darpy-sdk` and `darpy-sdk-types`, with the
  `darpy-sdk` CLI and Darbot documentation, examples, build, and test paths.
- Retain inherited MCP client/server, transport, authorization, telemetry,
  protocol-version negotiation, and schema-generation behavior.
- Provide optional Agent Client Protocol and Microsoft Activity adapters with
  explicit supported behavior, tested dependency baselines, and failure modes.
- Keep wire schemas, protocol identifiers, upstream attribution, and the
  scientific platform's separate `darpy` namespace intact.

The initial Darbot version is 0.1.0. A completed rename or an installed protocol
package is not a claim of production certification or complete DARPy platform
implementation.

## Protocol workstreams

The current inherited schema snapshots and hashes are recorded in
[schema/PINNED.json](schema/PINNED.json). The MCP conformance suite and
[expected failures](.github/actions/conformance/expected-failures.yml) make
unsupported scenarios inspectable. Preserve these gates while adapting to later
specification revisions.

Agent Client Protocol and Activity package baselines, capabilities, transport
boundaries, and integration tests belong in [protocol integrations](docs/protocols.md).
Changes to those integrations must distinguish protocol fields that pass through
unchanged from behavior the Darbot runtime actually executes.

Upstream optional MCP work, including Tasks-extension behavior, DPoP-bound
authorization, and workload identity, remains separate work unless implemented
and verified in this fork. Upstream issues and boards are research references;
they are not Darbot delivery commitments.

## Runtime and platform integration

Extend typed task/context contracts, cancellation, session lifecycle, bounded
execution, tool authorization, and observable errors through measured increments.
The DARPy platform owns scientific computation, orchestration, and its broader
agent/team/swarm roadmap; the SDK provides interoperable protocol and transport
surfaces. Cross-repository integrations require explicit version and schema
contracts, rather than installing both packages into the same namespace.

## Release readiness

Before publication, meet [release gates](RELEASE.md), inspect built artifacts,
verify the configured platform matrix, and record remaining limitations.
Track concrete work through [Darbot SDK issues](https://github.com/DarbotLM/darpy-sdk/issues).
No upstream maintenance schedule, issue-response SLA, or automatically recursive
improvement guarantee is implied.

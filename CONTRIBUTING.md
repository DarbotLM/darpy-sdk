# Contributing to Darbot Python SDK

This is the DarbotLabs framework fork. Current source lives under `darpy_sdk`
and `darpy_sdk_types`; upstream protocol specifications and source attribution
remain intact. Read [AGENTS.md](AGENTS.md) for the engineering conventions and
[NOTICE.md](NOTICE.md) for provenance.

## Coordinate changes

For an outside contribution, open a concise issue explaining the observed
behavior, expected behavior, environment, and a minimal reproduction. Public
API additions, architectural changes, dependency changes, and protocol changes
need an agreed design before implementation. Existing explicit maintainer
instructions already provide that design authorization for their stated scope.

The retained intake workflow requires outside pull requests to reference an open
issue using `Fixes #123`, `Closes #123`, or `Resolves #123`, and to have the issue
assigned to their author or labeled `help wanted`. Check the workflow's actual
result if a pull request is closed; correct the linked issue or assignment rather
than creating duplicate pull requests. Do not imply that an upstream issue is an
assignment in this fork.

DarbotLabs does not inherit an upstream two-business-day triage SLA, organization
ban policy, maintainer roster, Discord contact channel, or release timetable.
Use this repository's [issue tracker](https://github.com/DarbotLM/darpy-sdk/issues)
for Darbot work. Security disclosures follow [SECURITY.md](SECURITY.md).

## Development setup

Python 3.10+ and uv are required for the core SDK. Optional protocol dependencies
may require a newer interpreter; their package markers and CI define that scope.

```bash
git clone https://github.com/DarbotLM/darpy-sdk.git
cd darpy-sdk
uv sync --frozen --all-extras --group codegen
```

Create a branch from `main`. This is the Darbot 0.1 development line; the fork
does not promise an upstream `v1.x` backport branch. Use uv only for project
management and always run tools with `--frozen`. Change static dependencies
intentionally, then regenerate the lockfile with `uv lock`.

## Verification

```bash
uv run --frozen ruff format .
uv run --frozen ruff check .
uv run --frozen pyright
./scripts/test
uv run --frozen --group codegen python scripts/gen_surface_types.py --check
uv run --frozen python scripts/update_readme_snippets.py --check
bash scripts/docs/build.sh
node --test '.github/scripts/*.test.js'
```

The retained test gate is 100% branch coverage, with warnings treated as errors
and `strict-no-cover` checking unnecessary exclusions. Read
[the test quality guide](.claude/skills/test-quality/SKILL.md) before designing
new tests. Use deterministic, in-memory public-API tests and AnyIO where possible;
coordinate asynchronous work with events and bound waits. Do not suppress warnings
or weaken gates to make a namespace change pass.

Preserve the configured Python/platform/dependency matrix and MCP conformance
checks. A new feature of the 2026-07-28 MCP specification requires a matching
upstream conformance scenario before claiming support. Protocol packages alone
are not conformance evidence; ACP and Activity adapters need integration-specific
checks too.

## Documentation and generated outputs

Update affected English documentation and runnable `docs_src` examples in the
same pull request. If a README snippet changes, regenerate it with
`uv run --frozen python scripts/update_readme_snippets.py`. API reference pages
are generated from the renamed package roots. Wire models are generated from
unchanged pinned schemas; use `scripts/gen_surface_types.py` instead of editing
those generated modules directly.

Translation prose is generated from English sources and language instructions.
The authorized initial namespace migration mechanically updates product and
package identifiers in retained translations, preserves their original section
hashes, and advances the translation tool provenance version. Existing generated
translations therefore fall back to current English until deliberately
regenerated. No external translation call is part of a normal build. See
[i18n/README.md](i18n/README.md).

## Review and contribution scope

A pull request should explain the problem, resulting behavior, tests, and
remaining limits. Link the agreed issue, update relevant documentation, and
address review feedback. Keep independent work separate so reviewers can assess
each change. Disclose AI assistance and review its output; a contributor remains
accountable for correctness, attribution, and the changes they submit.

Use [the dependency policy](DEPENDENCY_POLICY.md) for dependency changes and
[the version policy](VERSIONING.md) for API changes. Do not rename MCP wire fields,
headers, specification URIs, or third-party packages as part of product branding.
Contributions are MIT licensed and subject to [the Code of Conduct](CODE_OF_CONDUCT.md).

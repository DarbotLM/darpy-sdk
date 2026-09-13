# Release process

Darbot releases publish two distributions together: `darpy-sdk` and
`darpy-sdk-types`. The initial metadata version is `0.1.0`. Release automation
exists in this repository, but no Darbot PyPI project, trusted publisher,
documentation deployment, or production certification is inferred from it.

## Prepare the release commit

1. Update the static version in the root `pyproject.toml` and
   `src/darpy-sdk-types/pyproject.toml` together. Update the SDK's exact
   `darpy-sdk-types` requirement and any public version constant.
2. Follow [the dependency policy](DEPENDENCY_POLICY.md) for dependency changes,
   then run `uv lock`. Commit the normal locked resolution, not a temporary
   lowest-direct test resolution.
3. Update release notes and documentation with the actual implementation scope,
   namespace changes, protocol revisions, tested dependency baselines, and
   remaining limitations. Review source attribution in [NOTICE.md](NOTICE.md).
4. Verify the exact intended commit. A successful local subset does not replace
   the hosted Python 3.14 Windows/Linux dependency matrix and protocol conformance jobs.

## Required checks

```bash
uv sync --frozen --all-extras --group codegen --python 3.14
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
./scripts/test
uv run --frozen --group codegen python scripts/gen_surface_types.py --check
uv run --frozen python scripts/update_readme_snippets.py --check
bash scripts/docs/build.sh
node --test '.github/scripts/*.test.js'
uv build --package darpy-sdk
uv build --package darpy-sdk-types
```

Retain the 100% branch-coverage gate, `strict-no-cover`, warning-as-error checks,
standalone wire-types import check, and configured Python/platform/dependency
matrix. Run MCP conformance against the pinned supported revisions and review
expected failures. Optional ACP and Activity adapters need their own behavioral
checks; their package versions alone do not establish protocol support.

Inspect both wheels and source distributions. In an isolated environment outside
the checkout, install the built pair and verify imports, entry points, version
metadata, and exact types dependency. Confirm `darpy_sdk` can operate without the
upstream `mcp` or `mcp-types` distributions and without a source-tree path leak.
Check the standalone types distribution with only its declared dependencies.

## Publish deliberately

Configure and verify the DarbotLabs PyPI projects and trusted publishers for
both distributions before creating a publishing release. The trusted publisher
must name this repository, `.github/workflows/publish-pypi.yml`, and its release
environment. Do not use upstream publisher identities or assume fork settings
were inherited. Protect the release environment according to the maintainer's
release policy.

Tag the reviewed commit explicitly and ensure its static package versions match
the tag. Publishing a GitHub release can trigger the publishing workflow from
that commit, so create it only after the package-publication decision. Mark a
prerelease as a prerelease. Do not publish development artifacts as an upstream
MCP SDK release or reuse an upstream version/tag by accident.

The workflow builds and publishes both distributions. If an upload is partially
successful, inspect PyPI and the build artifacts before rerunning; do not reuse
a version for changed contents. A broken published release is corrected by a
new version, with both packages handled consistently and release notes pointing
to the correction.

## Documentation deployment

Build documentation from the current Darbot checkout. The configured canonical
site URL is a deployment target, not proof that the site is live. Enable a
Darbot-owned deployment only after its host/project settings are configured;
preview credentials and domains must belong to the intended Darbot project.
Do not rebuild or publish upstream v1.x/v2 histories as Darbot release sites.

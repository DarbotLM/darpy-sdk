# Documentation translations

The English pages under `docs/` are the source. This directory holds what steers their machine translation and the generated result; [`docs/translations.md`](../docs/translations.md) is the reader-facing explanation.

- `languages.yml` — the registry: one entry per translated site (served at `/<code>/`), the model id, and the nav pages that stay in English.
- `general-prompt.md` — translation rules shared by every language. `notices.md` — English source of the three notes staged onto the pages of a translated site.
- `<code>/instructions.md` (register, voice, typography, terminology) and `<code>/glossary.json` (`keep`: terms that stay in English; `terms`: required renderings, each with an optional `note` and banned `avoid` renderings, which are checked) — human-authored, sent with every request.
- `<code>/pages/**` and `<code>/notices.md` — **generated**, never manually rewritten as translated prose: a correction goes into that language's `instructions.md` or `glossary.json` (or the English page), and the affected pages are re-run.

## Darbot namespace migration

The initial Darbot fork migration performs a deliberate mechanical update of
owned package/import/CLI/product identifiers across the retained translation
files. It does not call a translation service or claim to retranslate prose.
Original English section hashes and tool-version-1 provenance remain intact.
The translation tool now writes version-2 provenance, so version-1 outputs are
unverified for this fork and the existing provenance check stages current
English instead of stale upstream product/support claims.

Regenerate a page deliberately with the version-2 tool after updating its English
source, language instructions, and glossary. Only a newly generated page receives
new section hashes; never rewrite hashes just to make an old translation appear
current. The historical files remain available for review and future translation
work, but are not presented as verified Darbot translations.

Normal documentation builds are offline with respect to translation services.
The explicit `translate` command makes external model calls and is a separate
operation. No such calls are needed to build English fallback editions.

## The tool

```text
uv run --frozen python scripts/docs/translations.py status [--lang CODE]
uv run --frozen --group translate python scripts/docs/translations.py translate [--lang CODE ...] [--pages PATH ...] [--jobs N]
uv run --frozen python scripts/docs/translations.py stage [--lang CODE]
```

`status` is offline: per language it lists missing, outdated (with the sections that changed), current and removable pages (translations whose English page is gone — `git rm` them). `translate` calls the Claude API (`ANTHROPIC_API_KEY` in the environment; the registry's model, or `DOCS_TRANSLATE_MODEL` to trial another) for the missing and outdated pages of every language (or just the `--lang` ones), several pages at a time (`--jobs`, default 8; each page is its own request, so this changes how long the run takes, not what the model sees), retranslating only the English sections that changed and keeping the rest byte for byte; `--pages` instead re-translates exactly the named pages from scratch (in every language unless `--lang` narrows it), which is also how a glossary or instructions change reaches existing pages (each generated page records the English section hashes it reflects, so editing those inputs invalidates nothing). `stage` assembles the tree each language site is built from (every language's, or one with `--lang`): each generated page exactly as it was generated, under an "outdated" notice linking the current English page when the English has changed since, and the English page where nothing was generated yet; `scripts/docs/build.sh` runs it before building them. Commit the generated pages in an ordinary pull request.

To add a language, add an entry to `languages.yml`, write `<code>/instructions.md` (the sections the `pt` file has) and `<code>/glossary.json`, then run `translate --lang <code>`.

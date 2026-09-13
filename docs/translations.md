# Documentation translations

English documentation under `docs/` is the current source of truth for Darbot
Python SDK. The repository retains inherited machine translations in twelve
languages, but they are not yet verified Darbot translations.

## Current behavior

The fork migration mechanically updates product, package, import, and CLI
identifiers in the retained files. Their original source-section hashes and
version-1 provenance remain unchanged. The translation tool now produces
version-2 provenance, so builds show **current English fallback** until a page is
deliberately regenerated. This prevents stale statements about upstream package
versions, official SDK identity, release support, or hosting from appearing as
current Darbot documentation.

Language navigation and notices remain available for Deutsch, español, français,
हिन्दी, 日本語, 한국어, português (Brasil), русский язык, Türkçe, українська мова,
简体中文, and 繁體中文. The API reference remains English. A local build is not a
claim that any language site has been deployed.

## Future regeneration

A translation run uses the current English page, language instructions, and
glossary, validates the generated structure, and records new source hashes and
version-2 provenance. Normal builds do not call translation services. Do not
refresh hashes manually to disguise stale prose as current.

After verified translations exist, the normal notices distinguish a current
machine translation, a translation behind its English source, and an English
fallback. English remains authoritative when editions disagree.

## Corrections

Report the language, page, and concrete problem in the
[Darbot SDK issue tracker](https://github.com/DarbotLM/darpy-sdk/issues).
Correct English source or language instructions/glossaries, then deliberately
regenerate affected translations. The workflow is described in the repository's
[i18n guide](https://github.com/DarbotLM/darpy-sdk/blob/main/i18n/README.md).

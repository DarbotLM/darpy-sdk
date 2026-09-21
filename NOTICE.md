# Source attribution

Darbot Python SDK (`darpy-sdk`, import `darpy_sdk`) and Darbot SDK wire types
(`darpy-sdk-types`, import `darpy_sdk_types`) are maintained as a DarbotLabs fork
of the [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk).
The starting implementation is the upstream 2.2.0 line at commit
[`9972c21aa42054fb1450c5fc614761ed11847ec6`](https://github.com/modelcontextprotocol/python-sdk/commit/9972c21aa42054fb1450c5fc614761ed11847ec6).

The upstream MIT copyright and permission notice in [LICENSE](LICENSE) is
retained. Existing authorship, code history, specification citations, and
third-party notices are not replaced by the Darbot product name.

DarbotLabs changes include the distribution/import/CLI namespace migration,
Darbot release metadata and documentation, and additional runtime and protocol
integration modules. Darbot `0.1.0` is a separate release line; it is not an
upstream 0.1, 1.x, or 2.x release.

Model Context Protocol identifiers, HTTP headers, JSON keys, specification
revisions, and upstream conformance contracts remain MCP identifiers. Agent
Client Protocol and Microsoft Activity names identify their respective external
protocols and packages. Rebranding the SDK does not rename those standards or
imply endorsement by their maintainers.

The vendored MCP schemas retain their recorded origins and hashes in
[schema/PINNED.json](schema/PINNED.json). Generated Python models are rebuilt
under the Darbot namespace from those schemas. The separate
[DARPy platform](https://github.com/DarbotLM/darpy) is not bundled into this
SDK's import namespace.

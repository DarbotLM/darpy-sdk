"""The extension-identifier grammar in `darpy_sdk.shared.extension`, shared by server and client."""

from typing import Any

import pytest

import darpy_sdk.server.extension
import darpy_sdk.shared.extension
from darpy_sdk.shared.extension import validate_extension_identifier


def test_server_extension_module_reexports_shared_validator() -> None:
    """SDK-defined: the server extension module re-exports the same shared validator object."""
    assert (
        darpy_sdk.server.extension.validate_extension_identifier
        is darpy_sdk.shared.extension.validate_extension_identifier
    )


@pytest.mark.parametrize(
    "identifier",
    [
        "io.modelcontextprotocol/ui",
        "com.example/my_ext",
        "com.x-y.z2/n.a-b_c",
        "example/x",
        "a/b",
        "com.example/9start",
    ],
)
def test_grammar_conformant_extension_identifiers_are_accepted(identifier: str) -> None:
    """Spec `_meta` key grammar: conformant `vendor-prefix/name` identifiers are accepted."""
    validate_extension_identifier(identifier, owner="T")


@pytest.mark.parametrize(
    "identifier",
    [
        "noprefix",
        "-foo/bar",
        ".leading/x",
        "a..b/x",
        "foo-/x",
        "9foo/x",
        "foo/-bar",
        "foo/bar-",
        "foo/",
        "/bar",
        "foo/ba r",
        "io.modelcontextprotocol/ui\n",
        "",
        None,
        42,
    ],
)
def test_malformed_extension_identifiers_are_rejected(identifier: Any) -> None:
    """Spec `_meta` key grammar: malformed prefixes, malformed names, and non-strings are rejected."""
    with pytest.raises(TypeError):
        validate_extension_identifier(identifier, owner="T")

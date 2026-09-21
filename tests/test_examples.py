"""Tests for example servers"""
# TODO(Marcelo): The `examples` directory needs to be importable as a package.
# pyright: reportMissingImports=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false

from pathlib import Path

import pytest
from darpy_sdk_types import SERVER_INFO_META_KEY, CallToolResult, TextContent, TextResourceContents
from inline_snapshot import snapshot
from pytest_examples import CodeExample, EvalExample, find_examples
from pytest_examples.config import ExamplesConfig

from darpy_sdk import Client


def strip_server_info(result: CallToolResult, server_name: str) -> CallToolResult:
    """Assert the 2026-era serverInfo stamp, then drop it from the result's meta.

    The example servers set no explicit version, so the stamp's version is
    empty; the snapshots stay about the behavior under test, not identity.
    """
    assert result.meta is not None
    assert result.meta[SERVER_INFO_META_KEY] == {"name": server_name, "version": ""}
    remaining = {k: v for k, v in result.meta.items() if k != SERVER_INFO_META_KEY}
    return result.model_copy(update={"meta": remaining or None})


@pytest.mark.anyio
async def test_simple_echo():
    """Test the simple echo server"""
    from examples.mcpserver.simple_echo import mcp

    async with Client(mcp) as client:
        result = strip_server_info(await client.call_tool("echo", {"text": "hello"}), "Echo Server")
        assert result == snapshot(
            CallToolResult(content=[TextContent(text="hello")], structured_content={"result": "hello"})
        )


@pytest.mark.anyio
async def test_complex_inputs():
    """Test the complex inputs server"""
    from examples.mcpserver.complex_inputs import mcp

    async with Client(mcp) as client:
        tank = {"shrimp": [{"name": "bob"}, {"name": "alice"}]}
        result = await client.call_tool("name_shrimp", {"tank": tank, "extra_names": ["charlie"]})
        result = strip_server_info(result, "Shrimp Tank")
        assert result == snapshot(
            CallToolResult(
                content=[
                    TextContent(text="bob"),
                    TextContent(text="alice"),
                    TextContent(text="charlie"),
                ],
                structured_content={"result": ["bob", "alice", "charlie"]},
            )
        )


@pytest.mark.anyio
async def test_direct_call_tool_result_return():
    """Test the CallToolResult echo server"""
    from examples.mcpserver.direct_call_tool_result_return import mcp

    async with Client(mcp) as client:
        # The serverInfo stamp merges alongside the handler-authored meta.
        result = strip_server_info(await client.call_tool("echo", {"text": "hello"}), "Echo Server")
        assert result == snapshot(
            CallToolResult(
                meta={"some": "metadata"},  # type: ignore[reportUnknownMemberType]
                content=[TextContent(text="hello")],
                structured_content={"text": "hello"},
            )
        )


@pytest.mark.anyio
async def test_desktop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test the desktop server"""
    # Build a real Desktop directory under tmp_path rather than patching
    # Path.iterdir — a class-level patch breaks jsonschema_specifications'
    # import-time schema discovery when this test happens to be the first
    # tool call in an xdist worker.
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "file1.txt").touch()
    (desktop / "file2.txt").touch()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    from examples.mcpserver.desktop import mcp

    async with Client(mcp) as client:
        # Test the sum function
        result = strip_server_info(await client.call_tool("sum", {"a": 1, "b": 2}), "Demo")
        assert result == snapshot(CallToolResult(content=[TextContent(text="3")], structured_content={"result": 3}))

        # Test the desktop resource
        result = await client.read_resource("dir://desktop")
        assert len(result.contents) == 1
        content = result.contents[0]
        assert isinstance(content, TextResourceContents)
        assert isinstance(content.text, str)
        assert "file1.txt" in content.text
        assert "file2.txt" in content.text


# `--8<--` include directives lint clean as Python, so pages built from
# `docs_src/` includes cost nothing here; the real validation of those files is
# pyright + ruff + tests/docs_src/.
class _Python314ExamplesConfig(ExamplesConfig):
    """Set Ruff's target beyond pytest-examples' stale Literal; Black is unused."""

    def ruff_config(self) -> tuple[str, ...]:
        args = super().ruff_config()
        return tuple(arg for arg in args if not arg.startswith("--target-version=")) + ("--target-version=py314",)


@pytest.mark.parametrize(
    "example",
    list(
        find_examples(
            "README.md",
            "docs/index.md",
            "docs/whats-new.md",
            "docs/protocol-versions.md",
            "docs/deprecated.md",
            "docs/troubleshooting.md",
            "docs/get-started",
            "docs/servers",
            "docs/handlers",
            "docs/run",
            "docs/client",
            "docs/advanced",
        )
    ),
    ids=str,
)
def test_docs_examples(example: CodeExample, eval_example: EvalExample):
    ruff_ignore: list[str] = ["F841", "I001", "F821"]  # F821: undefined names (snippets lack imports)

    # Use project's actual line length of 120
    eval_example.config = _Python314ExamplesConfig(ruff_ignore=ruff_ignore, line_length=120)
    assert tuple(arg for arg in eval_example.config.ruff_config() if arg.startswith("--target-version=")) == (
        "--target-version=py314",
    )

    # Use Ruff for both formatting and linting (skip Black)
    if eval_example.update_examples:  # pragma: no cover
        eval_example.format_ruff(example)
    else:
        eval_example.lint_ruff(example)

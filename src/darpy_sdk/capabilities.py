"""Inspect tested dependency baselines without importing optional integrations."""

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version


@dataclass(frozen=True)
class Capability:
    """Package availability, which is not a claim of protocol conformance."""

    name: str
    distribution: str
    tested_version: str
    installed_version: str | None
    extra: str | None


def capabilities() -> tuple[Capability, ...]:
    """Report installed packages and the integration baselines tested by DARPy."""
    entries = (
        ("mcp", "darpy-sdk", "0.1.0", None),
        ("acp", "agent-client-protocol", "0.12.1", "acp"),
        ("activity", "microsoft-agents-activity", "1.5.0", "activity"),
        ("activity-hosting", "microsoft-agents-hosting-core", "1.5.0", "hosting"),
    )
    result: list[Capability] = []
    for name, distribution, tested, extra in entries:
        try:
            installed = version(distribution)
        except PackageNotFoundError:
            installed = None
        result.append(Capability(name, distribution, tested, installed, extra))
    return tuple(result)

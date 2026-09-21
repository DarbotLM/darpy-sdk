import sys
from dataclasses import asdict
from importlib import reload
from importlib.metadata import PackageNotFoundError
from types import ModuleType
from typing import cast

import pytest
from inline_snapshot import snapshot

import darpy_sdk.capabilities as capability_module


def test_capabilities_report_metadata_without_importing_optional_protocols(monkeypatch: pytest.MonkeyPatch) -> None:
    """The SDK reports package metadata separately from tested baselines without importing optional integrations."""
    for module in ("acp", "microsoft_agents", "microsoft_agents.activity", "microsoft_agents.hosting.core"):
        monkeypatch.setitem(cast(dict[str, ModuleType | None], sys.modules), module, None)
    reload(capability_module)
    installed = {"darpy-sdk": "0.1.0", "agent-client-protocol": "0.12.2"}
    requested: list[str] = []

    def metadata_version(distribution: str) -> str:
        requested.append(distribution)
        if distribution not in installed:
            raise PackageNotFoundError(distribution)
        return installed[distribution]

    monkeypatch.setattr(capability_module, "version", metadata_version)
    result = capability_module.capabilities()
    assert {"requested": requested, "capabilities": [asdict(item) for item in result]} == snapshot(
        {
            "requested": [
                "darpy-sdk",
                "agent-client-protocol",
                "microsoft-agents-activity",
                "microsoft-agents-hosting-core",
            ],
            "capabilities": [
                {
                    "name": "mcp",
                    "distribution": "darpy-sdk",
                    "tested_version": "0.1.0",
                    "installed_version": "0.1.0",
                    "extra": None,
                },
                {
                    "name": "acp",
                    "distribution": "agent-client-protocol",
                    "tested_version": "0.12.1",
                    "installed_version": "0.12.2",
                    "extra": "acp",
                },
                {
                    "name": "activity",
                    "distribution": "microsoft-agents-activity",
                    "tested_version": "1.5.0",
                    "installed_version": None,
                    "extra": "activity",
                },
                {
                    "name": "activity-hosting",
                    "distribution": "microsoft-agents-hosting-core",
                    "tested_version": "1.5.0",
                    "installed_version": None,
                    "extra": "hosting",
                },
            ],
        }
    )


def test_capabilities_preserve_metadata_failure_instead_of_claiming_package_absence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only missing-distribution metadata becomes unavailable; other discovery failures remain visible to the caller."""
    failure = OSError("metadata storage is unreadable")

    def metadata_version(distribution: str) -> str:
        assert distribution == "darpy-sdk"
        raise failure

    monkeypatch.setattr(capability_module, "version", metadata_version)
    with pytest.raises(OSError) as error:
        capability_module.capabilities()
    assert error.value is failure

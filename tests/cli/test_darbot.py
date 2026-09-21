"""Darbot command behavior through the public CLI."""

import importlib.metadata
import json

import pytest
from inline_snapshot import snapshot
from typer.testing import CliRunner

import darpy_sdk.capabilities as capability_metadata
from darpy_sdk.cli.cli import app


def test_version_reports_the_installed_darbot_distribution(monkeypatch: pytest.MonkeyPatch) -> None:
    """The SDK command reads Darbot's distribution metadata."""

    def installed(distribution: str) -> str:
        assert distribution == "darpy-sdk"
        return "0.1.0"

    monkeypatch.setattr(importlib.metadata, "version", installed)
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout == snapshot("Darbot Python SDK version 0.1.0\n")


def test_version_missing_distribution_reports_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A source directory without installed metadata cannot claim a release."""

    def missing(distribution: str) -> str:
        raise importlib.metadata.PackageNotFoundError(distribution)

    monkeypatch.setattr(importlib.metadata, "version", missing)
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 1
    assert result.stdout == snapshot("Darbot Python SDK version unknown (package not installed)\n")


def test_doctor_discloses_available_and_missing_optional_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Package detection is disclosed separately from protocol certification."""
    versions = {"darpy-sdk": "0.1.0", "agent-client-protocol": "0.12.1"}

    def installed(distribution: str) -> str:
        if distribution in versions:
            return versions[distribution]
        raise importlib.metadata.PackageNotFoundError(distribution)

    monkeypatch.setattr(capability_metadata, "version", installed)
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == snapshot(
        {
            "sdk": "Darbot Python SDK",
            "scope": "Package availability; not protocol conformance certification",
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
                    "installed_version": "0.12.1",
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

"""Shared test fixtures and configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    """Read a fixture file as text."""
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):  # noqa: ARG001
    """Auto-enable custom integration loading for every test."""
    return

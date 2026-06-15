"""Shared fixtures for the Samsung AC (DPLUG) integration tests."""
import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations):
    """Allow Home Assistant to load this custom integration in every test."""
    yield

"""Global fixtures for custom integration."""

from typing import Any

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> None:  # noqa: ARG001
    """Enable custom integrations defined in the test dir."""
    return

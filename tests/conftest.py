"""Shared test fixtures."""

import pytest

from tests.fakes import FakeDriver, FakeElement


@pytest.fixture()
def element() -> FakeElement:
    """Return a plain visible element."""
    return FakeElement(text="hello")


@pytest.fixture()
def driver() -> FakeDriver:
    """Return a driver that knows no elements."""
    return FakeDriver()

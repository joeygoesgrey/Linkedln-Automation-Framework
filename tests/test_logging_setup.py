"""Prove logging setup is idempotent and writes the log file it returns."""

import logging
from pathlib import Path

import pytest

from laf.logging_setup import configure_logging


@pytest.fixture(autouse=True)
def clean_root_logger():
    """Remove and close the root handlers after each test.

    WHY
        The tests change the global root logger, so leftover open file
        handlers would keep temporary files busy for the next test.

    MUTATIONS
        write: removes every root handler and closes it after the test body.
    """
    yield
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()


def test_configure_twice_keeps_one_file_and_one_console_handler(tmp_path: Path) -> None:
    """Two calls leave exactly one file handler and one console handler."""
    first_path = configure_logging(False, str(tmp_path))
    second_path = configure_logging(True, str(tmp_path))

    root = logging.getLogger()
    file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
    console_handlers = [h for h in root.handlers if type(h) is logging.StreamHandler]

    assert len(root.handlers) == 2
    assert len(file_handlers) == 1
    assert len(console_handlers) == 1

    assert file_handlers[0].level == logging.DEBUG
    assert console_handlers[0].level == logging.INFO

    assert first_path.parent == tmp_path
    assert second_path.parent == tmp_path
    assert second_path.name.startswith("laf_")
    assert second_path.name.endswith(".log")
    assert second_path.exists()


def test_configure_writes_records_with_the_logger_name(tmp_path: Path) -> None:
    """A debug record reaches the file and carries the logger name."""
    log_path = configure_logging(True, str(tmp_path))

    logging.getLogger("laf.example").debug("a debug line")

    for handler in logging.getLogger().handlers:
        handler.flush()

    content = log_path.read_text(encoding="utf-8")
    assert "laf.example" in content
    assert "a debug line" in content


def test_configure_without_debug_keeps_the_file_at_info(tmp_path: Path) -> None:
    """A normal run keeps the file handler at INFO and skips debug lines."""
    log_path = configure_logging(False, str(tmp_path))

    logging.getLogger("laf.example").debug("hidden debug line")
    logging.getLogger("laf.example").info("visible info line")

    for handler in logging.getLogger().handlers:
        handler.flush()

    content = log_path.read_text(encoding="utf-8")
    assert "visible info line" in content
    assert "hidden debug line" not in content

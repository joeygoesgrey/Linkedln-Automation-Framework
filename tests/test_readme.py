"""Prove the README troubleshooting table matches the message table."""

import pathlib
import re

from laf.messages import MESSAGES

README = pathlib.Path(__file__).resolve().parent.parent / "README.md"
ROW_PATTERN = re.compile(r"^\|\s*`?([A-Z][A-Z0-9_]+)`?\s*\|")


def _readme_rows() -> list[str]:
    """Read the codes that the README table names.

    WHY
        The table is hand written, so a typo or a missing row can reach a user
        who is already stuck. One parse feeds every check below.

    Returns
        list[str]: the code in each table row, in the order the rows appear.
    """
    codes: list[str] = []
    for line in README.read_text(encoding="utf-8").splitlines():
        match = ROW_PATTERN.match(line)
        if match:
            codes.append(match.group(1))
    return codes


def test_readme_file_exists() -> None:
    """The README is there, so the table check has something to read."""
    assert README.is_file(), f"README.md is missing at {README}"


def test_every_message_code_has_a_row() -> None:
    """A user who sees a code can always find it in the table."""
    rows = set(_readme_rows())
    missing = sorted(set(MESSAGES) - rows)

    assert not missing, (
        "README.md Troubleshooting table is missing a row for: "
        + ", ".join(missing)
    )


def test_every_row_names_a_real_code() -> None:
    """A row points at a code the bot can print, so no row is a dead end."""
    rows = set(_readme_rows())
    unknown = sorted(rows - set(MESSAGES))

    assert not unknown, (
        "README.md Troubleshooting table names codes that do not exist in "
        "laf/messages.py: " + ", ".join(unknown)
    )


def test_no_row_duplicates_another() -> None:
    """Each code gets one row, so the table stays easy to scan."""
    rows = _readme_rows()
    seen: set[str] = set()
    repeated: set[str] = set()
    for code in rows:
        if code in seen:
            repeated.add(code)
        seen.add(code)

    assert not repeated, (
        "README.md Troubleshooting table repeats these codes: "
        + ", ".join(sorted(repeated))
    )


def test_unexpected_fallback_has_no_row() -> None:
    """The fallback sentence is not a code, so the table must not list it."""
    rows = set(_readme_rows())

    assert "UNEXPECTED" not in rows, (
        "README.md lists UNEXPECTED as a table row. It is the fallback "
        "sentence, so describe it in a line of text instead."
    )

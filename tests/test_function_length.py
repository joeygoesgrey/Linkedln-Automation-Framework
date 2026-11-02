"""Tests for the function length checker and its allowlist."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import check_function_length  # noqa: E402


def write_module(tmp_path: Path, body: str) -> Path:
    """
    WHY
        Each test needs a small real file on disk, so the checker reads files
        the same way it does in the repository.

    Args
        tmp_path: Path, the pytest temporary folder.
        body: str, the python source to write.

    Returns
        Path, the written module path.
    """
    module = tmp_path / "sample.py"
    module.write_text(body, encoding="utf-8")
    return module


def test_real_tree_passes(capsys) -> None:
    """
    WHY
        The committed tree and the committed allowlist must agree, otherwise
        the hook blocks every commit.

    Args
        capsys: pytest fixture, captures the checker output for a failure read.
    """
    paths, error = check_function_length.default_targets(REPO_ROOT)
    assert error is None
    allowlist = REPO_ROOT / "tools" / check_function_length.ALLOWLIST_NAME
    exit_code = check_function_length.check_paths(paths, allowlist, REPO_ROOT)
    assert exit_code == 0, capsys.readouterr().out


def test_long_function_is_reported(tmp_path: Path, capsys) -> None:
    """
    WHY
        A function over the ceiling must fail the run so a long body cannot land
        unnoticed.

    Args
        tmp_path: Path, the pytest temporary folder.
        capsys: pytest fixture, captures the printed report.
    """
    lines = ["def too_long():", '    """Do a thing."""']
    lines.extend(["    value = 1"] * 61)
    lines.append("    return value")
    module = write_module(tmp_path, "\n".join(lines) + "\n")
    exit_code = check_function_length.check_paths([module], None, tmp_path)
    output = capsys.readouterr().out
    assert exit_code == 1
    assert "too_long 62 lines" in output


def test_stale_allowlist_entry_fails(tmp_path: Path, capsys) -> None:
    """
    WHY
        An allowed name that is no longer over the ceiling keeps a dead entry
        alive, so the run must fail and name it.

    Args
        tmp_path: Path, the pytest temporary folder.
        capsys: pytest fixture, captures the printed report.
    """
    module = write_module(tmp_path, "def short():\n    return 1\n")
    allowlist = tmp_path / "allow.txt"
    allowlist.write_text("sample.py::short\n", encoding="utf-8")
    exit_code = check_function_length.check_paths([module], allowlist, tmp_path)
    output = capsys.readouterr().out
    assert exit_code == 1
    assert "stale allowlist entry: sample.py::short" in output


def test_count_body_lines_edge_cases(tmp_path: Path) -> None:
    """
    WHY
        A docstring only function and a one line function are the two shapes
        that crash or miscount a naive line counter.

    Args
        tmp_path: Path, the pytest temporary folder.
    """
    module = write_module(
        tmp_path,
        'def empty():\n    """Only a doc."""\n\n\ndef one(): return 1\n',
    )
    records, error = check_function_length.scan_file(module, tmp_path)
    assert error is None
    counts = {record.name: record.length for record in records}
    assert counts == {"empty": 0, "one": 1}


def test_bad_allowlist_line_names_its_line(tmp_path: Path, capsys) -> None:
    """
    WHY
        A malformed allowlist line must fail with the line number, so the person
        fixes the list instead of guessing.

    Args
        tmp_path: Path, the pytest temporary folder.
        capsys: pytest fixture, captures the printed report.
    """
    module = write_module(tmp_path, "def short():\n    return 1\n")
    allowlist = tmp_path / "allow.txt"
    allowlist.write_text("not a valid entry\n", encoding="utf-8")
    exit_code = check_function_length.check_paths([module], allowlist, tmp_path)
    output = capsys.readouterr().out
    assert exit_code == 1
    assert "allow.txt:1 bad allowlist line" in output

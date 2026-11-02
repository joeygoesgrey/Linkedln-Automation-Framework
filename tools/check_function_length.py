"""Find function bodies longer than the code line ceiling.

WHY
    Long functions hide bugs because nobody sees the whole body at once. This
    checker gives one command that fails when a function body passes the
    ceiling, so the pre-commit hook and pytest both catch it.

The count is physical code lines. It skips the def line, the signature, the
docstring, blank lines and comment only lines. A nested function is counted on
its own lines, and those lines are not counted toward the parent.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

CEILING = 60
ALLOWLIST_NAME = "function_length_allowlist.txt"
SCAN_FOLDERS = ("laf", "tools", "tests")
SCAN_FILES = ("main.py",)
REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class FunctionRecord:
    """One function found in a scanned file."""

    path: str
    line: int
    name: str
    length: int


def normalize_path(path: Path, root: Path) -> str:
    """
    WHY
        Scanned paths, allowlist paths and absolute paths must compare equal
        after one normalisation, so a stale entry is not hidden by spelling.

    Args
        path: Path, a relative or absolute file path.
        root: Path, the repository root to make paths relative to.

    Returns
        str, the posix style path relative to root when possible, otherwise
        the absolute posix path.
    """
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(root.resolve())
    except ValueError:
        return resolved.as_posix()
    return relative.as_posix()


def is_docstring(node: ast.stmt) -> bool:
    """
    WHY
        The docstring can be many lines and must not count toward the body.

    Args
        node: ast.stmt, the first statement of a function body.

    Returns
        bool, True when the statement is a string constant expression.
    """
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def nested_function_lines(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[int]:
    """
    WHY
        A nested function is checked on its own, so its whole span must be
        removed from the parent count.

    Args
        node: ast.FunctionDef or ast.AsyncFunctionDef, the parent function.

    Returns
        set[int], every 1 based line number that belongs to a nested function.
    """
    lines: set[int] = set()
    for child in ast.walk(node):
        if child is node:
            continue
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            end = child.end_lineno if child.end_lineno is not None else child.lineno
            start = child.lineno
            for decorator in child.decorator_list:
                start = min(start, decorator.lineno)
            lines.update(range(start, end + 1))
    return lines


def count_body_lines(
    node: ast.FunctionDef | ast.AsyncFunctionDef, source_lines: Sequence[str]
) -> int:
    """
    WHY
        The ceiling is about physical code lines, so the count walks the real
        source lines between the first and last body statement.

    Args
        node: ast.FunctionDef or ast.AsyncFunctionDef, the function to measure.
        source_lines: Sequence[str], the file lines, zero based from the start.

    Returns
        int, the number of code lines in the function body. A docstring only
        function returns 0.
    """
    body = list(node.body)
    if body and is_docstring(body[0]):
        body.pop(0)
    if not body:
        return 0
    start = body[0].lineno
    end = body[-1].end_lineno
    if end is None:
        end = start
    skipped = nested_function_lines(node)
    total = 0
    for lineno in range(start, end + 1):
        if lineno in skipped:
            continue
        text = source_lines[lineno - 1].strip()
        if not text or text.startswith("#"):
            continue
        total += 1
    return total


def scan_file(path: Path, root: Path) -> tuple[list[FunctionRecord], str | None]:
    """
    WHY
        One unparsable file must be reported and fail the run instead of being
        skipped, so a broken file cannot hide long functions.

    Args
        path: Path, the python file to scan.
        root: Path, the repository root for the displayed path.

    Returns
        tuple[list[FunctionRecord], str | None], the functions found and an
        error sentence when the file cannot be parsed.
    """
    relative = normalize_path(path, root)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as error:
        return [], f"{relative}: cannot read: {error.strerror}"
    except UnicodeDecodeError as error:
        return [], f"{relative}: cannot read as utf-8: {error.reason}"
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as error:
        return [], f"{relative}: cannot parse: {error.msg} (line {error.lineno})"
    source_lines = source.splitlines()
    records = [
        FunctionRecord(relative, node.lineno, node.name, count_body_lines(node, source_lines))
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    return records, None


def scan_paths(
    paths: Sequence[Path], root: Path
) -> tuple[list[FunctionRecord], list[str]]:
    """
    WHY
        One pass builds both the over ceiling report and the allowlist from the
        same measurements.

    Args
        paths: Sequence[Path], the python files to scan.
        root: Path, the repository root for the displayed path.

    Returns
        tuple[list[FunctionRecord], list[str]], every function sorted by path
        and line, and the errors from files that cannot be parsed.
    """
    records: list[FunctionRecord] = []
    errors: list[str] = []
    for path in paths:
        file_records, error = scan_file(path, root)
        records.extend(file_records)
        if error is not None:
            errors.append(error)
    records.sort(key=lambda record: (record.path, record.line, record.name))
    return records, errors


def default_targets(root: Path) -> tuple[list[Path], str | None]:
    """
    WHY
        The hook and the test must scan the same set of files, and a wrong root
        must fail loudly instead of reporting a clean run on an empty set.

    Args
        root: Path, the repository root to scan.

    Returns
        tuple[list[Path], str | None], the files to scan and an error sentence
        when the root has no laf folder.
    """
    if not (root / "laf").is_dir():
        return [], f"{root} has no laf folder, so it is not the repository root"
    paths: list[Path] = []
    for folder in SCAN_FOLDERS:
        directory = root / folder
        if directory.is_dir():
            paths.extend(sorted(directory.rglob("*.py")))
    for name in SCAN_FILES:
        candidate = root / name
        if candidate.is_file():
            paths.append(candidate)
    return paths, None


def load_allowlist(allowlist_path: Path, root: Path) -> tuple[set[tuple[str, str]], list[str]]:
    """
    WHY
        The allowlist holds the functions that were already over the ceiling,
        and a bad line must fail with its line number instead of being ignored.

    Args
        allowlist_path: Path, the allowlist file. A missing file means no entry.
        root: Path, the repository root used to normalise entry paths.

    Returns
        tuple[set[tuple[str, str]], list[str]], the (path, name) entries and the
        errors with the file name and line number.
    """
    entries: set[tuple[str, str]] = set()
    errors: list[str] = []
    if not allowlist_path.is_file():
        return entries, errors
    text = allowlist_path.read_text(encoding="utf-8")
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        file_part, separator, name_part = line.partition("::")
        file_part = file_part.strip()
        name_part = name_part.strip()
        if not separator or not file_part or not name_part.isidentifier():
            errors.append(f"{allowlist_path.name}:{number} bad allowlist line: {raw.strip()!r}")
            continue
        entries.add((normalize_path(Path(file_part), root), name_part))
    return entries, errors


def print_offenders(offenders: Sequence[FunctionRecord]) -> None:
    """
    WHY
        Every over ceiling function uses one readable line so a person sees the
        file, line, name and size at a glance.

    Args
        offenders: Sequence[FunctionRecord], the functions over the ceiling.

    MUTATIONS
        Prints one line per function.
    """
    for record in offenders:
        print(
            f"{record.path}:{record.line} {record.name} "
            f"{record.length} lines (ceiling {CEILING})"
        )


def list_offenders(paths: Sequence[Path], root: Path) -> int:
    """
    WHY
        The allowlist is built from machine output, so this mode prints only
        entries and always exits 1 to mark that it is not a check run.

    Args
        paths: Sequence[Path], the python files to scan.
        root: Path, the repository root for the displayed path.

    Returns
        int, always 1.
    """
    records, errors = scan_paths(paths, root)
    for error in errors:
        print(error)
    for record in records:
        if record.length > CEILING:
            print(f"{record.path}::{record.name}")
    return 1


def check_paths(
    paths: Sequence[Path], allowlist_path: Path | None, root: Path
) -> int:
    """
    WHY
        The hook and the test call this one function to learn whether the tree
        passes, and a missing entry or a stale entry both mean the list is out
        of date.

    Args
        paths: Sequence[Path], the python files to scan.
        allowlist_path: Path or None, the allowlist file. None means empty.
        root: Path, the repository root for the displayed path.

    Returns
        int, 0 when every over ceiling function is allowed and no entry is
        stale, 1 otherwise.
    """
    records, errors = scan_paths(paths, root)
    allowed, allowlist_errors = (
        load_allowlist(allowlist_path, root) if allowlist_path else (set(), [])
    )
    offenders = [record for record in records if record.length > CEILING]
    offending = {(record.path, record.name) for record in offenders}
    missing = sorted(offending - allowed)
    stale = sorted(allowed - offending)
    if missing or stale or errors or allowlist_errors:
        print_offenders(offenders)
    for path, name in missing:
        print(f"missing from allowlist: {path}::{name}")
    for path, name in stale:
        print(f"stale allowlist entry: {path}::{name}")
    for error in errors + allowlist_errors:
        print(error)
    failed = bool(errors or allowlist_errors or missing or stale)
    allowed_count = len(offending & allowed)
    print(
        f"{len(records)} functions checked, "
        f"{len(offenders)} over the ceiling, {allowed_count} allowed"
    )
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    """
    WHY
        A plain command line keeps the hook and a person on the same code path.

    Returns
        argparse.ArgumentParser, the parser with the two modes.
    """
    parser = argparse.ArgumentParser(description="Check function body lengths.")
    parser.add_argument(
        "--list", action="store_true", dest="list_mode", help="print allowlist lines"
    )
    parser.add_argument(
        "--check", action="store_true", help="check against the allowlist (default)"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """
    WHY
        The hook needs one entry point that always finds the repository root
        from this file, no matter which directory git runs it from.

    Args
        argv: Sequence[str] or None, the command line arguments after the script.

    Returns
        int, the exit code of the selected mode.
    """
    args = build_parser().parse_args(argv)
    paths, error = default_targets(REPO_ROOT)
    if error is not None:
        print(error)
        return 1
    if args.list_mode:
        return list_offenders(paths, REPO_ROOT)
    allowlist_path = REPO_ROOT / "tools" / ALLOWLIST_NAME
    return check_paths(paths, allowlist_path, REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())

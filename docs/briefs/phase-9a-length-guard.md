# Brief: enforce a function length ceiling

## Goal

Long functions go unnoticed because nothing checks them. Add a checker, a
pre-commit hook that runs it, and a pytest test that runs it too, so a function
over the ceiling cannot slip in again.

## Files you may touch

- `tools/check_function_length.py` (new)
- `tools/function_length_allowlist.txt` (new)
- `tests/test_function_length.py` (new)
- `.githooks/pre-commit` (new, executable)
- `AGENTS.md` (one short section added)

Files you may NOT touch: anything under `laf/`, `main.py`, `README.md`,
`docs/`, `pyproject.toml`, `tests/test_services.py`, `tests/test_composer.py`.
Two other agents are editing `laf/services/composer.py` and
`laf/services/profile_actions.py` right now.

## The counting rule, exactly

Count the physical code lines of one function body, and skip:

- the docstring, however many lines it takes
- blank lines
- lines whose first non-space character is `#`
- the `def` line, decorators and the signature

Start at the first statement after the docstring. End at the last line of the
last statement in the body. A nested function is counted on its own, and its
lines are not counted toward the parent.

The ceiling is 60. The target is 40, but only 60 fails.

## The checker

`python tools/check_function_length.py` scans `laf/`, `main.py`, `tools/` and
`tests/` for `.py` files and prints one line per function over the ceiling:

```
laf/services/composer.py:199 _schedule_post 118 lines (ceiling 60)
```

Exit code 1 when any function over the ceiling is missing from the allowlist,
or when the allowlist names a function that is no longer over the ceiling or no
longer exists. Exit 0 otherwise. Print a plain summary line, for example
`42 functions checked, 3 over the ceiling, 3 allowed`.

Two modes:

- `--list` prints every offending function in allowlist format, one per line,
  and exits 1. You will use this to build the file.
- `--check` is the default.

Allowlist file format, one per line, `#` starts a comment:

```
laf/services/engage_dom.py::comment_from_bar
```

Match on the file path and the function name. A method names its bare method
name, not `Class.method`.

## The hook

`.githooks/pre-commit`, executable, three commands:

```
uv run ruff check laf/ main.py tests/ tools/
uv run python tools/check_function_length.py
```

Fail the commit on the first failure, with a short plain message naming what
failed and how to see the details. Add one line to `AGENTS.md` saying the hook
is enabled with `git config core.hooksPath .githooks`.

## The test

`tests/test_function_length.py`:

- run the checker over the real tree and assert exit code 0
- write a temporary module with one function over the ceiling and assert the
  checker reports it (use `tmp_path`, call the checker as a function, not a
  subprocess, with a path argument)
- assert a stale allowlist entry fails the run

House docstrings on every function. No inline imports.

## Edge cases to handle and report

- A file that cannot be parsed: report the path and fail, do not skip silently.
- A function with only a docstring: zero code lines, not a crash.
- A one line function: `def f(): return 1`, counted as 1.
- A syntax error in the allowlist line: fail with the line number.
- Absolute versus relative paths: normalise to the repo root.
- Running from another directory: resolve the repo root from `__file__`, not
  from the current directory.

## Verify

```
uv run python tools/check_function_length.py --list
uv run python tools/check_function_length.py
uv run ruff check tools/ tests/test_function_length.py
uv run pyright tools/check_function_length.py
uv run pytest -q tests/test_function_length.py
```

The allowlist you commit should contain every function over 60 lines as the
tree stands when you finish. Report the full `--list` output. Do not commit,
do not run git add. Do not run `git config` yourself; report the command for me
to run.

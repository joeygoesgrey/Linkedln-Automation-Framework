# Phase 7 brief: every docstring in the house format

## Goal

Every function and every class docstring uses the house format, so a reader can
see why the code exists and what it changes without reading the body of two
style conventions.

The code must not change. Only docstrings change.

## The house format

```
"""
WHY
  <the outcome this code exists to produce, or the failure it prevents>

Args
  <name>: <type>, <where it comes from>

Returns
  <what it returns, when it returns a value>

Raises
  <ErrorClass>: <the edge case that causes it>

MUTATIONS
  <what it changes, when it changes state>
"""
```

Rules:

- `WHY` always appears. One or two sentences. Never a list of steps. Never
  "we needed it". If the sentence would not stop someone deleting the function,
  the sentence is wrong.
- `Args` appears only when the function takes parameters, and then lists every
  one. The type is the real annotation from the signature. "Where it comes
  from" is the caller or the source, not the type repeated.
- `Returns` appears only when the function returns a value other than None.
- `Raises` appears only when the function raises or passes an error through.
  Name only errors that the body can really raise. Never guess a code.
- `MUTATIONS` appears only when the function changes state: writes `self`,
  writes an argument, writes a file, or saves browser state.
- Delete a section the code does not need. Never write "none", a dash, "TBD",
  or an empty section.
- Plain simple English. No em dash characters anywhere.
- Classes: `WHY` plus `MUTATIONS` when the instance state can change after
  construction, plus `Raises` when the constructor raises. No `Args` on the
  class, because the constructor documents its own.

## How to convert an old docstring

The old shape is `Why:`, `When:`, `How:`, then `Args:` and `Returns:`.

- Old `Why` is the seed for `WHY`. Keep its meaning, rewrite it as the outcome.
- Old `When` is a caller note. Delete it, unless it states a condition that
  stops a real bug. In that case fold that condition into `WHY`.
- Old `How` is usually a list of steps. Delete the steps. If it states a real
  invariant, fold the invariant into `WHY` in one clause.
- Old `Args` keeps every parameter, rewritten to the house shape, with the type
  taken from the signature.
- Old `Returns` stays only when the function really returns a value.
- Add `Raises` and `MUTATIONS` only after checking the body. Do not copy them
  from anywhere.

Example. Old:

```
Locate an element by iterating through multiple selector options.

Why:
    LinkedIn frequently tweaks DOM structure; cycling selectors adds resilience.

When:
    Called by services when a single selector may not be stable.

How:
    Attempts each selector with a WebDriverWait until one succeeds or the list
    is exhausted.

Args:
    selectors (Iterable[str | tuple]): Candidate locator strings or (By, str) tuples.
    selector_type (str): Selenium locator strategy (e.g., By.CSS_SELECTOR).
    timeout (float | None): Optional timeout override in seconds.

Returns:
    WebElement | None: Element if found, otherwise ``None``.
```

New:

```
WHY
  Try each candidate locator until one is visible, so a change to one
  selector on the page does not break the action.

Args
  selectors: Iterable[Union[str, tuple]], the candidate locators from the caller.
  selector_type: str, the Selenium strategy used for plain string locators.
  timeout: Optional[float], the seconds to wait, or None to use the config.

Returns
  Optional[WebElement], the first visible match, or None when none matched.
```

## Fill the gap

`build_comment` in `laf/app.py` has no docstring. Read the body and write one
in the house format.

## Proof that only comments changed

Write a throwaway script at `/tmp/docproof.py` (keep it outside the repo) that
takes a file path and does this:

1. reads the old text with `git show HEAD:<path>` in the worktree,
2. parses each text,
3. removes every docstring node from both trees (for `Module`, `ClassDef`,
   `FunctionDef`, `AsyncFunctionDef`, set `body` to the statements that are not
   a bare string constant, and clear `body[0]` when it is one),
4. dumps both with `ast.dump(tree, include_attributes=False)`,
5. prints IDENTICAL or DIFFERS, then exits.

Run it once per file you changed and report each result. Any DIFFERS means you
changed code, so undo that change.

Also grep each changed file for `Why:`, `When:`, `How:` and for em dash
(U+2014). Both greps must come back empty.

## Files you may touch

ONLY the files named in the section for your slice. Do not touch any other
file, `docs/V2_PLAN.md`, `docs/briefs/`, `.env`, `pyproject.toml`, tests, or
`README.md`.

## Edge cases

- A function is a one line stub with no docstring today: it still gets a `WHY`.
- A docstring that contradicts the code: the code wins. Keep the docstring
  faithful to the body and report the contradiction in your final message.
- A decorator or nested function inside a function: give the nested function
  its own docstring only if the outer work would be unclear otherwise. Do not
  invent docs for lambdas.
- A property: document it like a function. `Returns` applies; `Args` does not.
- A `__init__` that only stores values: `WHY` says what the object needs to do
  its job, `MUTATIONS` says it stores the partners, and `Args` lists them.
- A placeholder code in an old `Raises`: replace it with the real class found
  in the body, or drop the section.
- Do not reformat code, reorder imports, change type hints, or "fix" anything
  you notice. Report it instead.
- Do not add words like "It", "This function", or "We" at the start of WHY.
  Start with the action or the outcome.

## Checks for your slice

```
uv run ruff check <your files>
uv run pytest -q
uv run python -c "import <each module you changed>"
```

Plus the docstring-only AST proof for every file you changed, and a grep that
the file no longer holds `Why:` or `When:` or `How:` as a section heading.

Report: files changed, the AST proof result per file, any contradiction found,
and any function where you could not write a real WHY. Do not commit.

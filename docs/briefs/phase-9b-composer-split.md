# Brief: split the composer flow into named steps

## Goal

`ComposerService.post_to_linkedin` is 125 lines and `_schedule_post` is 126.
Both read as a runbook of unnamed steps. Split each so the parent body reads
like a list of names, with no behaviour change.

## Files you may touch

- `laf/services/composer.py`
- `tests/test_composer.py`

Files you may NOT touch: `laf/ui.py`, `laf/services/profile_actions.py`,
selectors, `laf/app.py`, `main.py`, `docs/`, `README.md`, `pyproject.toml`,
`tests/test_services.py`, `tests/test_pursue_flow.py`. Two other agents are
working in this tree: one on `tools/` and one on `laf/services/profile_actions.py`.

## The rule

Inside one function every line must sit at the same level of detail. If a line
hides a smaller job, that job gets its own method with a name that says what it
does. If you need a comment to explain a block, the comment becomes the name.
A new method takes a docstring in the house format.

## Target shape

`post_to_linkedin` keeps its signature and its True or False contract. Its body
becomes about 25 lines of calls, in this order:

1. open the composer: load the feed, pause, dismiss overlays, find and click
   the start button
2. find and focus the editor
3. write the text, either the mention path or the plain path
4. focus the editor again and insert any mentions
5. upload images when paths were given
6. either schedule and return, or submit with the Post button

Every pause and every log line that exists today stays, inside the step it
belongs to. The schedule branch still returns before any Post lookup.

`_schedule_post` becomes a short sequence: open the date picker, fill the date,
fill the time, click Next, click confirm. Keep the retry loop around Next and
keep the final `return self._click_schedule_confirm()`.

No function in the file may exceed 60 code lines after this. Code lines means
physical lines excluding the docstring, comments and blank lines.

## Behaviour that must not change

- Return values, the order of clicks, the selector order, the pause lengths,
  the log messages and the results of the schedule path.
- `_find_start_post_button`, `_find_post_editor`, `_set_post_text`,
  `_find_post_button` and `_schedule_post` keep their names, because tests and
  the caller use them.
- The schedule path still returns False when the confirm click fails.

## Tests

`tests/test_composer.py` already proves the schedule path. Keep those three
tests passing. If a split changes what a test patches, update the patch target
in the test, not the assertion. Add one test that `post_to_linkedin` still
returns False when the start button is missing, if that path is not covered.

## Edge cases to handle and report

- Editor focus failing twice: today it warns and continues, keep that.
- Mentions failing: today it warns and continues, keep that.
- Image upload failing: today it warns and continues, keep that.
- A schedule date without a time, or a time without a date: today the flow
  falls through to the Post button, keep that.
- `_click_schedule_confirm` returning False: `_schedule_post` returns False and
  `post_to_linkedin` returns False, keep that.
- Do not change what happens when `self.ui.click_with_fallback` returns False
  at any step.

## Verify

```
uv run python tools/check_function_length.py --list
uv run ruff check laf/services/composer.py tests/test_composer.py
uv run pyright laf/services/composer.py
uv run pytest -q
uv run python main.py --help
```

Report: the line count of each function before and after, the names of the new
methods, the tests you changed and why, and any place where the split forced a
behaviour decision. Do not commit, do not run git add.

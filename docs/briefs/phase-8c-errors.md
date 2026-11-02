# Phase 8c brief: name every error, remove every catch-all

## Goal

`except Exception` appears 309 times under `laf/`. After this phase it appears
zero times. Every catch names the errors it expects, and every failure the user
can see becomes a named code from `laf/messages.py`.

The full global rule with examples is in the user's `CLAUDE.md` under
"NAME THE ERROR. NEVER CATCH EVERYTHING". Read it first. The short version:

- A catch exists for one of three reasons: try the next candidate, clean up or
  tear down, or turn the failure into the domain's named error.
- Catch the smallest set that covers the expected errors.
- A catch that cannot name its error means the input or the design is wrong.
- No bare `except`, no `except Exception: pass`, no silent `continue`.

## The types to use

Pick by what the body does, not by what logs well:

- Any Selenium call: `from selenium.common.exceptions import WebDriverException`.
  It already covers timeout, stale element, no such element and the rest.
- File read or write: `OSError`.
- `int()`, `float()`, `json.loads`, `re.compile`, dict lookups: the smallest set
  of `ValueError`, `TypeError`, `KeyError`, `json.JSONDecodeError`, `re.error`
  that the body can really raise.
- A call that already raises a named `LAFError`: no catch at all. Let it reach
  the boundary in `main.py`.
- Cleanup in a `finally` or before a re-raise: `WebDriverException`, and only
  when the cleanup really calls the browser.

## The user boundary

Some catches sit around a whole step and currently return False. Those become
one of these, in this order of preference:

1. No catch at all, so the named `LAFError` from below reaches `main.py`.
2. A catch that wraps the real error in an existing `LAFError` subclass and
   code, with the original error chained by `from`.
3. A new code, only when no existing code fits. Then add the code to
   `laf/messages.py`, to the README Troubleshooting table, and to
   `laf/errors.py` if a subclass is needed. `tests/test_readme.py` must pass.

Never invent wording in a service. Wording lives in `laf/messages.py`.

## Per item loops

A loop that processes posts catches at the item, logs the item, records one
sentence in the results and continues. It does not catch around the loop. The
catch names the expected errors for one item.

## Logging

In every file you touch, replace root logger calls like `logging.info(...)`
with the module logger that already exists in the file, for example
`logger.info(...)`. Keep the level and the message. Do not add new log lines
unless a catch now needs one to say which item or selector failed.

## What must not change

- The return values and the control flow, except where a swallowed error now
  becomes a named error on purpose.
- The sentence a user sees for an existing failure. If a site currently logs a
  message with no code, keep the log line and add the named error beside it,
  or convert it to the code that already holds the same wording.
- Pauses, retries, selector order, and the shape of the results dict.
- Docstrings stay in the house format.

## Verify

Per file:

```
uv run ruff check <files>
uv run pytest -q
uv run pyright laf/ main.py
grep -c "except Exception" <file>     must print 0
grep -n "except:" <file>              must print nothing
grep -n "logging\.\(info\|error\|warning\|debug\)" <file>   must print nothing
```

Then run the suite and `uv run python main.py --help`.

For every converted user boundary, add a test with the fakes where possible:
the fake raises the real exception type, and the test asserts the named code or
the recorded sentence.

## Edge cases to handle and report

- A catch whose body is only `pass` or `continue` with no log: either the code
  needs a log line naming what was skipped, or the catch is hiding a bug and
  should go. Report each one you deleted.
- A catch around `driver.quit()` or teardown: narrow to `WebDriverException`,
  keep the finally, keep going.
- A catch around `send_keys` or `click`: `WebDriverException`.
- A catch around a network or AI call: the client already raises `AiError`.
  Drop the catch unless the function must return a fallback, in which case
  catch `AiError` only.
- A catch that handles more than one unrelated failure: split the `try` into
  two blocks so each names its own error.
- A site where you cannot name the error: leave it unchanged, and report it in
  a list with file, line and the reason. Do not guess and do not widen.
- If converting a site would change what the user sees, stop and report it
  rather than choosing silently.

## Report

For each file: the number of sites before and after, a count of the error types
you used, the sites you could not name, any new code you added, and the command
outputs. Do not commit, do not run git add.

# Brief: phase 10e, repair the engage and profile selectors

## Goal

Make the engage and profile selectors match the live LinkedIn page on
2026-10-31, the same way phase 10c did for the composer, and prove it with
`tools/check_selectors.py`.

## Read first

- `docs/V2_PLAN.md`, phase 10. It records the live markup facts for the
  composer and the three layer plan.
- `laf/selectors/composer.py`. Copy its style: data attributes first, then
  aria labels and visible text, class names last.
- `laf/ui.py`, `find_by_selectors`. Every lookup goes through it and now logs
  each miss.

## Files you own

- `laf/selectors/engage.py`
- `laf/selectors/profile.py`
- `laf/services/engage_dom.py`
- `laf/services/profile_actions.py`

## Files you may touch only if a test forces it

- `tests/test_services.py`
- `tests/test_engage_dom.py` if it exists

## Files you must not touch

- `laf/services/composer.py`, `laf/selectors/composer.py`
- `laf/app.py`, `laf/messages.py`, `laf/errors.py`
- `tools/check_selectors.py`
- `README.md`
- `docs/V2_PLAN.md` (the coordinator updates it)

## How to learn the live markup

Write a throwaway script under `/tmp`, not in the repo, that:

1. builds a driver with `DriverFactory.setup_driver(load_config())`,
2. opens `config.linkedin_feed_url` and waits 8 seconds,
3. runs one JavaScript snippet that lists every element with a
   `data-view-name` attribute, every `aria-label`, and every `button` whose
   text matches the control you need, with its attributes,
4. prints the result as JSON,
5. quits the driver in a `finally` block.

The page ships hashed class names. Look for `data-view-name`, `aria-label`,
`data-testid` and visible text. Never click Like, Comment or Repost: reading
the page is enough. Do not publish, follow or send anything.

Useful facts already known: feed action buttons carry
`data-view-name="feed-comment-button"`, `"reaction-button"`,
`"feed-share-button"`, `"feed-control-menu"`. Post bodies sit in
`data-view-name="feed-commentary"`.

## Definition of done

- Every `EngageSelectors` and `ProfileSelectors` attribute has at least one
  selector that matches the live page, except attributes for a button that
  only appears after a click. For those, record the click that opens it in
  the module docstring.
- `uv run tools/check_selectors.py` shows `result=pass` for every selector
  you changed on the class you changed.
- `uv run ruff check laf/ main.py tests/ tools/` passes.
- `uv run pyright laf/` passes.
- `uv run pytest -q` passes.
- `uv run python tools/check_function_length.py` passes.
- No new error code, no message change, no em dash.

## Edge cases you must handle and report back on

- A selector that matches more than one element: the first visible one must be
  the right control. If it is not, narrow the selector.
- A selector that matches the logged in user's own post as well as others:
  say so in your report.
- A control that only exists after hovering or after clicking a menu: say
  which click reveals it, and whether the service already performs that click.
- A text input that is a React controlled field: `clear()` may not empty it.
  If you rely on it, state how you know.
- The page in a language other than English: do not add selectors that depend
  on English text alone without an attribute fallback.

## Report back

Name each attribute you changed, the old selector, the new selector, and the
live evidence (attribute name and value) that made you choose it. Name each
edge case above and what you did. If a control cannot be found, say so instead
of guessing a selector.

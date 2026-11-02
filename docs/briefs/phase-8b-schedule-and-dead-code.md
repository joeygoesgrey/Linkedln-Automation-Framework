# Phase 8b brief: finish the schedule flow and delete the duplicates

## Goal

Two small fixes in the services:

1. A scheduled post never clicks the final confirm button, so the flow goes on
   to look for a "Post" button that is not on screen. Wire the confirm click in.
2. `_like_post` and `_comment_on_post` in `laf/services/profile_actions.py`
   have no callers and repeat what `engage_profile_posts` already does. Delete
   them.

## Files you may touch

- `laf/services/composer.py`
- `laf/services/profile_actions.py`
- `tests/test_services.py` or a new `tests/test_composer.py`

Files you may NOT touch: selectors, other services, `laf/app.py`, `main.py`,
`docs/`, `README.md`.

## Part one: the schedule confirm

Read `post_to_linkedin` and `_schedule_post` and `_click_schedule_confirm`
before editing. Today:

- `post_to_linkedin` fills the date and time by calling `_schedule_post`.
- `_schedule_post` clicks the "Next" button in the modal and returns True as
  soon as the button disappears.
- `_click_schedule_confirm` exists, looks for `SCHEDULE_CONFIRM_BUTTONS`, and
  nothing calls it.
- `post_to_linkedin` then looks for a "Post" button and submits.

Change:

- At the end of the successful `_schedule_post` path, call
  `_click_schedule_confirm()` and return what it returns. When no confirm
  button is found, log an error and return False, so the caller stops instead
  of clicking Post.
- In `post_to_linkedin`, when a schedule was requested and `_schedule_post`
  returned True, the post has already been submitted by the confirm click.
  Return True without the Post button path, after a short pause, and log that
  the post was scheduled.
- Keep every existing pause and log line unless the change makes it wrong.
- Keep `_schedule_post` working for the case where the next button disappears
  before the loop ends.

If reading the code shows the confirm button is already inside the Next path,
or the flow cannot work this way, stop and report instead of guessing.

## Part two: delete the duplicates

In `laf/services/profile_actions.py`, delete `_like_post` and
`_comment_on_post`. Before deleting, prove with a grep over `laf/`, `main.py`,
`tools/` and `tests/` that nothing calls them and no `getattr` uses the names.
Then grep the selectors they used, `ProfileSelectors.POST_CONTAINER` and
`ProfileSelectors.ACTION_BAR_CSS`, and report whether those selectors now have
no user. Do not delete the selectors in this slice.

## Tests

Add a unit test with a fake driver if the schedule path can be driven without a
real browser: assert that a schedule run calls the confirm path and does not
call the Post button path. If the DOM fakes in `tests/fakes.py` cannot express
it, say so plainly in your report instead of writing a test that proves nothing.

Run the existing suite after the deletion and show the count.

## Docstrings

Use the house format for anything you change. Delete the docstrings with the
methods.

## Checks

```
uv run ruff check laf/ main.py tests/ tools/
uv run pytest -q
uv run pyright laf/ main.py
grep -rn "_like_post\|_comment_on_post" laf/ main.py tools/ tests/
```

Report the files changed, the test added or the reason it was not possible, the
grep results, and any risk you see in the schedule change that a live run must
confirm. Do not commit, do not run git add.

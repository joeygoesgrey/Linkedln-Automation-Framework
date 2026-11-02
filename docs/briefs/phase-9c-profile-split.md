# Brief: split the profile engagement loop into named steps

## Goal

`ProfileService.engage_profile_posts` is 173 lines. It loads saved state,
walks the posts, likes, comments, saves state and counts. Split it so the
parent body reads like a list of names, with no behaviour change.

## Files you may touch

- `laf/services/profile_actions.py`
- `tests/test_services.py`

Files you may NOT touch: `laf/services/engage_dom.py`, `laf/services/composer.py`,
`laf/ui.py`, selectors, `laf/app.py`, `main.py`, `docs/`, `README.md`,
`tests/test_composer.py`, `tests/test_pursue_flow.py`. Two other agents are
working in this tree: one on `tools/` and one on `laf/services/composer.py`.

## The rule

Inside one function every line must sit at the same level of detail. If a line
hides a smaller job, that job gets its own method with a name that says what it
does. If you need a comment to explain a block, the comment becomes the name.
A new method takes a docstring in the house format.

## Target shape

`engage_profile_posts` keeps its signature and its results dict, with the same
keys and starting values. Its body becomes: load the saved state, then a loop
that asks one method to handle one post and updates the counters from what it
returns.

Suggested steps, adjust the names if the code says otherwise:

- `_load_engage_lists()` returns the liked, commented and reposted lists, with
  the same reset behaviour when the file shape is wrong
- `_find_profile_posts(limit)` returns the visible posts
- `_handle_one_profile_post(post, ...)` returns whether anything was done, and
  does the like and the comment for that one post
- keep `save_engage_state` call and the stall counter behaviour in the parent,
  because they decide whether the loop continues

No function in the file may exceed 60 code lines after this. Code lines means
physical lines excluding the docstring, comments and blank lines.

## Behaviour that must not change

- The results keys: `posts_engaged`, `likes`, `comments`, `reposted`,
  `skipped`, `errors`.
- The early return when `max_posts <= 0`.
- The stall counter: reset on progress, increment otherwise, stop at 8.
- Per post failures append one sentence to `errors` and the loop continues.
- The like-before-comment order, the pauses, the counters, and the saved state
  written after the actions on that post.

## Tests

Add tests in `tests/test_services.py` with the fakes in `tests/fakes.py`, or
small local stubs:

- `max_posts=0` returns the zeroed results and touches no post
- one post where the like succeeds increments `posts_engaged` and `likes`
- one post where the handler raises the browser error appends one sentence and
  the loop survives
- the returned dict has exactly the documented keys

## Edge cases to handle and report

- No visible posts: the stall counter increments and the loop exits, no crash.
- The saved state file holds a list instead of a dict: same reset as today.
- Saving state failing: today it passes silently on a file error, keep that.
- A post handler that finds nothing to do: counts as skipped, not engaged.
- `max_posts` larger than the posts found: loop ends by stall, not by crash.

## Verify

```
uv run python tools/check_function_length.py --list
uv run ruff check laf/services/profile_actions.py tests/test_services.py
uv run pyright laf/services/profile_actions.py
uv run pytest -q
uv run python main.py --help
```

Report: the line count before and after, the new method names, the tests added,
and any place where the split forced a behaviour decision. Do not commit, do
not run git add.

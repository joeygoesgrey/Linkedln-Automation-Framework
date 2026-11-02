# Phase 8a brief: move the pursue flow out of the bot class

## Goal

`pursue_investor` is 161 lines in `laf/app.py`. It validates, logs in, searches
a profile, navigates, follows, opens the posts view, builds an AI comment
generator, engages the posts and collects errors. After this slice, one small
class owns those steps, each step is its own method, and `LinkedInBot` only
delegates.

## Files you may touch

- `laf/flows/__init__.py` (new, docstring only)
- `laf/flows/pursue.py` (new)
- `laf/app.py` (remove the flow body, keep a delegate)
- `tests/test_pursue_flow.py` (new)

Files you may NOT touch: anything else under `laf/`, `main.py`, `docs/`,
`README.md`, `pyproject.toml`.

## Shape

```python
class PursueFlow:
    def __init__(self, services, driver, openai_client, post_extractor) -> None:
        ...
```

Do not import `App` or `LinkedInBot` into this module, because `laf/app.py`
will import `PursueFlow` and that would make a cycle. Pass the pieces.

Methods, one job each:

- `run(profile_name, max_posts=5, should_follow=True, should_like=True,
  should_comment=True, comment_perspectives=None, bio_keywords=None) -> dict`
  validates, calls the steps below, returns the results dict with the same
  keys as today: `profile`, `followed`, `posts_engaged`, `likes_given`,
  `comments_made`, `errors`.
- `_validate(...) -> PursueModel`, no catch. A rejection reaches `main.py`,
  which already prints the fields and returns 1.
- `_find_profile(validated) -> str`, logs in, searches, raises the named error
  when nothing matches. Read `laf/services/login.py` and `laf/messages.py` and
  pick the real login code. If no code fits a failed login call, raise
  `LoginError` with the closest real code and say so in your report. Never
  invent a code.
- `_follow_profile(validated) -> bool`, returns False and appends one sentence
  to `errors` when the follow fails.
- `_build_comment_generator(validated) -> Callable[[object], str] | None`,
  holds the AI builder and the fixed fallback sentence.
- `_engage(validated, generator) -> dict`, calls
  `services.profile.engage_profile_posts`.
- Move `_get_random_perspective` from `LinkedInBot` into this module as a
  module level helper if nothing else uses it. Check first with grep.

No catch-all anywhere in the new module. No outer `try` around `run`.

`LinkedInBot.pursue_investor` keeps its signature and returns what
`PursueFlow.run` returns, so `main.py` does not change. It may build the flow
in `__init__` or in the method, your choice, but `build_app` stays the only
place that wires services.

## Behaviour that must not change

- The results dict keys and their starting values.
- The fallback comment sentence.
- The order of actions: login, search, navigate, follow, posts view, engage.
- `follow` failure is recorded, not raised, so the rest of the run continues.

## Edge cases to handle and report

- Login returns False: report it in the results as today, do not raise.
- Profile not found: raise `ProfileError("PROFILE_NOT_FOUND")` with the name.
  This is a behaviour change and is wanted: today a `ValueError` is swallowed
  into the errors list.
- No AI client: the generator still returns the fallback sentence.
- Post text extraction fails: fallback sentence, no exception.
- Empty bio keywords: search without the filter.
- Follow disabled: `followed` stays False and no follow call happens.
- An unexpected error in a step that today lands in `errors`: keep the same
  outcome where the test can show it, else let the named error reach `main.py`.

## Docstrings

House format for every method, the class and the module. See
`docs/briefs/phase-7-docstrings.md`.

## Tests

`tests/test_pursue_flow.py` with the fakes in `tests/fakes.py` or small local
stubs: profile not found raises `ProfileError` with the code, follow failure is
recorded and the run continues, the fallback generator returns the fixed
sentence when the AI client is None, and the results keys match the old set.

## Checks

```
uv run ruff check laf/ main.py tests/ tools/
uv run pytest -q
uv run pyright laf/ main.py
uv run python main.py --help
grep -n "pursue_investor" -A 12 laf/app.py
```

Report the files changed, the tests added, the login code you chose and why,
and any behaviour you could not keep. Do not commit, do not run git add.

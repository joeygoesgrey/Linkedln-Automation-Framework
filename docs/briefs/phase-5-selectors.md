# Phase 5 brief: split the selector registry by page

## Goal

`laf/selectors/__init__.py` is 557 lines and holds ten unrelated classes for
ten different pages. After this phase, one page equals one file. A change to
the feed selectors means opening `laf/selectors/feed.py` and nothing else.

This phase splits only. It does not fix stale selectors, because the live
check is blocked by the Cloudflare challenge and is a manual step for the user.

Files you may touch:

- `laf/selectors/__init__.py` (ends as a docstring, no classes)
- new files under `laf/selectors/`
- the service files that import selectors (import lines only)
- `tests/test_selectors.py` (new)
- `tools/check_selectors.py` (new)

Files you may NOT touch: `laf/ui.py`, `laf/app.py`, `main.py`, `laf/errors.py`,
`laf/messages.py`, `docs/`, `pyproject.toml`, anything under `laf/ai/`.

## What moves where

| class | new file |
|---|---|
| `LoginSelectors` | `laf/selectors/login.py` |
| `VerifySelectors` | `laf/selectors/verify.py` |
| `OverlaySelectors` | `laf/selectors/overlays.py` |
| `ComposerSelectors` | `laf/selectors/composer.py` |
| `MediaSelectors` | `laf/selectors/media.py` |
| `MentionSelectors` | `laf/selectors/mentions.py` |
| `PostExtractorSelectors` | `laf/selectors/feed.py` |
| `FeedActionSelectors` | `laf/selectors/feed.py` |
| `EngageSelectors` | `laf/selectors/engage.py` |
| `ProfileSelectors` | `laf/selectors/profile.py` |

`laf/selectors/profile.py` and `laf/selectors/feed.py` each hold two classes
because they describe one page each.

Cross-class references that must keep working, and the import each creates:

- `MediaSelectors.COMPOSER_ROOTS = ComposerSelectors.MODAL_ROOTS`, so
  `media.py` imports `composer.py`.
- `FeedActionSelectors.LIKE_BUTTONS`, `COMMENT_BUTTONS`, `SUBMIT_COMMENT`
  point at `EngageSelectors`, so `feed.py` imports `engage.py`.

Both edges point one way. If you find a cycle, stop and report it. Do not
copy a selector value to break one, because the copy will drift.

Delete each class from `__init__.py` as you move it. When the file is empty,
leave it as a module docstring saying the selectors live one page per file.
Do not re-export the classes from `__init__.py`: update the import in every
consumer instead. Eleven service files import them today, including
`laf/services/profile_actions.py`, which imports two classes.

## Its own bug

Line 1 of `__init__.py` is `from selenium.webdriver.common.by import By`, and
the module docstring sits on line 3, so it is not a docstring at all, just a
bare string expression. In every new file, put the docstring first and the
imports after it. Each file imports `By` only if it uses it.

## Text must not change

Before the split, dump every string constant reachable from
`laf.selectors` (class, attribute, value) to a JSON file sorted by key. After
the split, walk the new modules, build the same map, and diff. The two maps
must be identical, including order inside every list. Report the diff result.
This is the same proof used in phase 4.

## Tests to add

`tests/test_selectors.py`:

- every class listed above can be imported from its new module,
- no selector class is still reachable from `laf.selectors`,
- every locator that is a tuple starts with a `By` member,
- no selector string contains an em dash.

## Tools: `tools/check_selectors.py`

Read only. It opens each page, tries every selector in the classes for that
page, and prints one line per selector: page, class, attribute, pass or fail.
It must not click, type or post anything. It needs a live logged in browser,
so it will not run here. That is expected: it is built now and run by the user
later. Keep it small, one function per job, with the same docstring sections
as the rest of the code.

## Edge cases

- An empty selector list in a class: the tool must print "empty" for it, not
  crash, and the test must not fail on it.
- A selector that is a plain string instead of a tuple: `ui.find_by_selectors`
  takes both, so the tool must handle both.
- A class that no service imports: keep it, do not delete it, so a feature
  that is currently unused still has its selectors.
- Do not change indentation of any list literal by running a formatter over
  the whole folder.
- The `# linkedin_ui/...` trailing comments are provenance notes. Keep them
  next to the selector they belong to.

## Checks

```
uv run ruff check laf/ main.py tests/ tools/
uv run pytest -q
uv run pyright laf/ main.py
uv run python main.py --help
grep -rn "from laf.selectors import" laf/ tests/ tools/
```

The grep must show one import per consumer, naming only the class it uses.
Report the files created, the string map diff result, and the command outputs.
Do not commit.

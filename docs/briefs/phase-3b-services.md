# Phase 3b brief: mixins become services

## Goal

Replace `BaseInteraction` and the nine mixins with plain classes that receive
their partners in the constructor. Keep `laf/app.py` and `main.py` unchanged.
`LinkedInInteraction` stays for this slice as a thin temporary facade that
builds the services in one place and delegates to them. Phase 3c moves that
construction into `build_app()` and deletes the facade.

Files you may touch:

- `laf/services/*.py` (all of them), `laf/ui.py` (new, replace `base.py`)
- `laf/services/__init__.py`

Files you may NOT touch: `laf/app.py`, `main.py`, `laf/config.py`,
`laf/errors.py`, `laf/messages.py`, `laf/ai/*`, `laf/browser/*`,
`laf/selectors/*`, `tests/*`, `docs/V2_PLAN.md`.

## Contract

`laf/ui.py`:

```python
class UiActions:
    def __init__(self, driver: WebDriver, config: Config) -> None: ...
    def pause(self, min_delay=None, max_delay=None) -> None:
        # was BaseInteraction.random_delay
    def type_with_delays(self, element, text) -> None:
        # was _type_with_human_delays
    def find_by_selectors(self, selectors, selector_type, timeout=None):
        # was _find_element_from_selectors
    def click_with_fallback(self, element, name) -> bool:
        # was _click_element_with_fallback
    def caret_to_end(self, element) -> bool:
        # was _move_caret_to_end
    def caret_to_start(self, element) -> bool:
        # was _move_caret_to_start
```

Services and constructors. All classes live in their current files, except
the base class, which becomes `laf/ui.py`. Class names change as shown.

| File | Class | Constructor |
| --- | --- | --- |
| `overlays.py` | `OverlayService` | `(ui: UiActions)` |
| `verify.py` | `VerifyService` | `(ui: UiActions)` |
| `mentions.py` | `MentionService` | `(ui: UiActions, overlays: OverlayService)` |
| `engage_dom.py` | `EngageDomService` | `(ui: UiActions, overlays: OverlayService, mentions: MentionService)` |
| `media.py` | `MediaService` | `(ui: UiActions, overlays: OverlayService)` |
| `login.py` | `LoginService` | `(ui: UiActions, config: Config)` |
| `composer.py` | `ComposerService` | `(ui, config, overlays, media, mentions, verify)` |
| `feed_actions.py` | `FeedService` | `(ui, config, overlays, mentions, engage_dom)` |
| `profile_actions.py` | `ProfileService` | `(ui, config, engage_dom)` |
| `engage.py` | `EngageService` | `(ui, config, engage_dom, overlays, mentions, post_extractor, ai_client)` |

Methods called from another service lose the leading underscore and keep
their name otherwise: `dismiss_overlays`, `_dismiss_global_search_overlay`
becomes `dismiss_global_search_overlay`, `_post_text_contains_inline_mentions`
becomes `post_text_contains_inline_mentions`, `_compose_text_with_mentions`
becomes `compose_text_with_mentions`, `_insert_mentions` becomes
`insert_mentions`, `_verify_post_success` becomes `verify_post_success`, and
every method of `EngageDomService` that another service calls loses its
underscore in the same way. Methods used only inside their own class keep the
underscore.

Every `self.<helper>(...)` becomes `self.ui.<helper>(...)` or
`self.<partner>.<method>(...)` according to the table. Delete `base.py`.

`laf/services/interaction.py` becomes the temporary facade:

```python
class LinkedInInteraction:
    def __init__(self, driver, config=None) -> None:
        self.config = config or CONFIG
        self.ui = UiActions(driver, self.config)
        self.overlays = OverlayService(self.ui)
        ...
        self.engage = EngageService(...)

    @property
    def driver(self): ...
    # one thin delegating method per name app.py uses
```

The facade must keep every name `laf/app.py` calls today:
`login`, `post_to_linkedin`, `engage_stream`, `like_first_post`,
`comment_first_post`, `repost_first_post`, `search_profile`,
`follow_profile`, `open_profile_posts_view`, `engage_profile_posts`,
and the `driver` attribute. Check `laf/app.py` for the exact calls before you
finish.

`EngageExecutor` in `engage_flow.py` takes the services it needs
(`(ui, engage_dom, overlays, engage_service, ...)`) instead of the whole
facade. It must not import `interaction.py`; that would close a cycle.

## Config use

Inside services, replace every `config.<CONSTANT>` with
`self.config.<field>` using this map: `HEADLESS` -> `headless`,
`LINKEDIN_USERNAME` -> `linkedin_username`, `LINKEDIN_PASSWORD` ->
`linkedin_password`, `OPENAI_MODEL` -> `openai_model`,
`LINKEDIN_BASE_URL` -> `linkedin_base_url`, `LINKEDIN_FEED_URL` ->
`linkedin_feed_url`, `LINKEDIN_LOGIN_URL` -> `linkedin_login_url`,
`ELEMENT_TIMEOUT` -> `element_timeout`, `SHORT_TIMEOUT` -> `short_timeout`,
`MIN_TYPING_DELAY` -> `min_typing_delay`, `MAX_TYPING_DELAY` ->
`max_typing_delay`, `MIN_ACTION_DELAY` -> `min_action_delay`,
`MAX_ACTION_DELAY` -> `max_action_delay`, `MIN_PAGE_LOAD_DELAY` ->
`min_page_load_delay`, `MAX_PAGE_LOAD_DELAY` -> `max_page_load_delay`,
`USER_DATA_DIR` -> `user_data_dir`, `MAX_POST_LENGTH` -> `max_post_length`,
`DEFAULT_TOPIC_FILE` -> `default_topic_file`, `CUSTOM_POSTS_FILE` ->
`custom_posts_file`, `SUMMARIZE_INPUT` -> `summarize_input`,
`SUMMARIZE_RATIO` -> `summarize_ratio`, `MAX_INPUT_CHARS` -> `max_input_chars`,
`ENABLE_TEXT_PREPROCESSING` -> `enable_text_preprocessing`,
`CAPTURE_TYPEAHEAD_HTML` -> `capture_typeahead_html`,
`TYPEAHEAD_CAPTURE_DIR` -> `typeahead_capture_dir`, `MARKETING_MODE` ->
`marketing_mode`, `PROJECT_NAME` -> `project_name`, `PROJECT_URL` ->
`project_url`, `PROJECT_PITCH` -> `project_pitch`, `PROJECT_SHORT_PITCH` ->
`project_short_pitch`, `PROJECT_CONTEXT` -> `project_context`,
`PROJECT_TAGLINE` -> `project_tagline`, `WINDOW_SIZE` -> `window_size`,
`USER_AGENT` -> `user_agent`, `LOG_DIRECTORY` -> `log_directory`.

After the slice, `grep -rn "config\." laf/services laf/ui.py` must find only
`self.config.` uses and the `from laf.config import Config, CONFIG` line.

Each new class needs a one line docstring. Each new `__init__` needs the
`WHY` and `Args` sections in the house style. Do not rewrite existing method
docstrings; only fix the ones that name a class or argument that changed.

## Known bugs to fix in this slice

- `engage_flow.py` calls `self.x.time.time()` (line 549). Use `time.time()`.
- `engage_flow.py` calls `_is_liked` (412), `_mark_post_liked` (628, 668) and
  `_is_post_marked_liked` (657), and none of them exist anywhere. Define them
  on `EngageService`: a post is liked when its urn is in `context.liked`, and
  marking adds it. Keep the `EngageContext` sets as the one source of truth.
- Nothing else changes behaviour.

## Edge cases

- Every mixin has `self.driver`. After the split, a class that reads the
  driver uses `self.ui.driver`. Do not keep a second driver attribute.
- Cross-service calls that pass `self` today (for example
  `EngageExecutor(self, ctx)`) must pass the service objects instead.
- Circular imports are forbidden. The allowed direction is leaves first:
  ui, overlays, verify, mentions, engage_dom, media, login, composer, feed,
  profile, engage, interaction.
- A public method that nobody outside the class calls stays private. Only the
  names listed above and the ones `app.py` uses become public.
- `dismiss_overlays(preserve_share_modal=...)` keeps its keyword name.
- Do not add `try/except` anywhere new. Convert only the except sites in the
  files you rewrite, and only where the called code makes the narrow type
  obvious. Report the ones you leave.
- If a body cannot be moved without changing behaviour, stop and report it
  instead of guessing.

## Definition of done

- `laf/base.py` is deleted, `laf/ui.py` exists, no mixin class is left.
- The facade exposes every name `laf/app.py` uses.
- No module imports `interaction.py` except `laf/services/__init__.py`.
- Report: each new class, its constructor, the public methods made public,
  every cross-service call site changed, the three engage bug fixes, and
  every except site you left broad.

Then paste the result of:

```
uv run ruff check laf/
uv run pytest -q
uv run pyright laf/ui.py laf/services/
uv run python main.py --help
grep -rn "config\." laf/services laf/ui.py | head -20
```

`pytest` and `main.py --help` must pass. `ruff` must pass on the files you
touched; report any E501 that is pre-existing in the large service files.
Do not commit.

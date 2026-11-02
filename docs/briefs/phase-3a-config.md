# Phase 3a brief: frozen Config

## Goal

`laf/config.py` gets a frozen `Config` dataclass loaded once by
`load_config()`. Every existing module-level constant stays as an alias, so no
other file needs a change in this slice and behaviour stays the same.

Files you may touch: `laf/config.py`, `tests/test_config.py` (new).
Files you may NOT touch: any other module, `main.py`, `docs/V2_PLAN.md`,
`pyproject.toml`, `laf/errors.py`, `laf/messages.py`.

## What to build

```python
@dataclass(frozen=True)
class Config:
    ...one field per current constant, same meaning...

def load_config(
    env: Mapping[str, str] | None = None,
    headless_override: bool | None = None,
) -> Config: ...
```

- `env` defaults to `os.environ`. Read every value through it, not through
  `os.getenv`, so a test can pass a plain dict.
- `headless_override` wins over the `HEADLESS` value in `env`.
- Keep `load_dotenv()` at module level, as now.
- Build one instance: `CONFIG = load_config()`, then set each old constant
  from it, for example `HEADLESS = CONFIG.headless`.
- Keep the existing helper behaviour for numbers: a missing or malformed
  value returns the default, and a malformed value logs one warning.
  `_safe_float` and `_safe_int` may stay as module functions used by
  `load_config`.
- Keep `START_POST_SELECTORS`, `POST_EDITOR_SELECTORS` and
  `POST_BUTTON_SELECTORS` as they are. They come from the selectors module,
  not from the environment, so they are not `Config` fields.
- Keep `PROJECT_TAGLINE` as a derived field built from the pitch and the URL.
- Do not raise for a missing username or password. They stay `None`.

Field names are the old constant names in lower case: `linkedin_username`,
`linkedin_password`, `openai_api_key`, `openai_model`, `marketing_mode`,
`project_name`, `project_url`, `project_pitch`, `project_short_pitch`,
`project_context`, `project_tagline`, `headless`, `window_size`,
`user_agent`, `user_data_dir`, `linkedin_base_url`, `linkedin_feed_url`,
`linkedin_login_url`, `min_typing_delay`, `max_typing_delay`,
`min_action_delay`, `max_action_delay`, `min_page_load_delay`,
`max_page_load_delay`, `element_timeout`, `short_timeout`,
`default_topic_file`, `log_directory`, `custom_posts_file`,
`max_post_length`, `enable_text_preprocessing`, `summarize_input`,
`summarize_ratio`, `max_input_chars`, `capture_typeahead_html`,
`typeahead_capture_dir`.

## Edge cases

- A window size must stay a tuple of two ints so the frozen instance stays
  hashable. Do not put a dict or a list in `Config`.
- An empty string in `env` is a real value, not a missing one: `float("")`
  fails, so the default and one warning must follow.
- `HEADLESS` and the other booleans accept `"true"` in any letter case and
  treat every other value as false, as the old code did.
- `USER_DATA_DIR` default uses `os.getcwd()` at load time, so pass the
  calling directory in, or document that it is read once.
- Assigning to any `Config` attribute must raise `FrozenInstanceError`.

## Tests to write

- Defaults with an empty env dict.
- Each of these env overrides is read: credentials, model, boolean flags, a
  delay, a timeout, a path.
- A malformed float and a malformed int each keep the default.
- `headless_override=True` and `False` each win over env.
- Assigning to a field raises `FrozenInstanceError`.
- Two sample module constants equal the matching `CONFIG` field.

## Definition of done

Report the field list, the two helper functions as they now stand, and every
place where behaviour could differ from the old module. Then paste the result
of:

```
uv run ruff check laf/config.py tests/test_config.py
uv run pytest -q
uv run pyright laf/config.py tests/test_config.py
```

Do not commit.

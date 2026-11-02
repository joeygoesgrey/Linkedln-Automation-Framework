# Phase 3e brief: last config readers and the long lines

## Goal

Finish the config move and clear the remaining `E501` lines, so phase 3 ends
with `ruff check laf/ main.py tests/` clean and `pyright laf/ main.py` at zero
errors.

Files you may touch:

- `laf/ai/content.py`, `laf/config.py`, `laf/app.py`
- `tests/test_config.py`
- any file under `laf/` that still needs a long line wrapped

Files you may NOT touch: `laf/errors.py`, `laf/messages.py`,
`laf/logging_setup.py`, `main.py`, `docs/`, `pyproject.toml`.

## Part one: content.py

`ContentGenerator` still reads `laf.config` module constants in nine places.
Give it the same treatment as `OpenAIClient`:

- Constructor: `__init__(self, ai_client=None, config: Config = CONFIG)`, store
  `self.config`.
- Every `config.<CONSTANT>` becomes `self.config.<field>` with the lower case
  field name, for example `config.MAX_POST_LENGTH` ->
  `self.config.max_post_length`, `config.PROJECT_TAGLINE` ->
  `self.config.project_tagline`, `config.CUSTOM_POSTS_FILE` ->
  `self.config.custom_posts_file`, `config.OPENAI_API_KEY` ->
  `self.config.openai_api_key`.
- `build_app` passes `ContentGenerator(ai_client=openai_client, config=resolved_config)`.
- Remove the `from laf import config` import.

## Part two: drop the aliases

In `laf/config.py`, delete the module constant block (`LINKEDIN_USERNAME`,
`HEADLESS`, `ELEMENT_TIMEOUT` and the rest) and the selector aliases
(`START_POST_SELECTORS`, `POST_EDITOR_SELECTORS`, `POST_BUTTON_SELECTORS`).
Keep `Config`, `ConfigError`-free `load_config`, `CONFIG` and the helpers.

Then run `grep -rn "from laf.config import" laf/ main.py tests/` and fix every
import that names a deleted constant. The expected survivors are `Config`,
`load_config` and `CONFIG`. Do not add a new alias to keep an old name alive.

Update `tests/test_config.py`: remove any test that compares a module constant
with `CONFIG`, keep the `load_config` and frozen tests, and add one test that
`from laf.config import HEADLESS` now fails with `ImportError`.

## Part three: long lines

`uv run ruff check laf/ main.py tests/` currently reports 52 `E501`. Wrap
each one: move a long string into implicit concatenation, wrap prose in a
docstring, or wrap the call arguments. Do not change the value of any string
that reaches the screen, a prompt or a selector. Verify with an AST dump
before and after that every string constant is byte for byte identical. Do
not add `# noqa`.

## Edge cases

- No import cycle. `laf/ai/content.py` may import `laf.config`; it must not
  import `laf.app`.
- `ContentGenerator` with no config still works from `CONFIG`, so existing
  callers that pass only `ai_client` keep working.
- Do not change any selector string, prompt string or user facing sentence.
- Do not reformat whole files with `ruff format`; wrap only the reported
  lines, so the diff stays reviewable.

## Checks

```
uv run ruff check laf/ main.py tests/
uv run pytest -q
uv run pyright laf/ main.py
uv run python main.py --help
grep -rn "config\.[A-Z][A-Z_]*" laf/ main.py | grep -v "laf/config.py"
```

Report: every config import you changed, the string equality check you ran,
and the four command outputs. Do not commit.

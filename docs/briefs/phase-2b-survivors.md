# Phase 2b brief: surviving modules

## Goal

Make the modules that phase 3 keeps report failures in a specific way. No
behaviour change on the happy path.

Files you may touch:

- `laf/config.py` (3 except sites)
- `laf/ai/client.py` (3)
- `laf/ai/content.py` (4)
- `laf/services/engage_utils.py` (2)

Files you may NOT touch: `main.py`, `laf/errors.py`, `laf/messages.py`,
`laf/browser/driver.py`, anything under `laf/services/` other than
`engage_utils.py`, `docs/V2_PLAN.md`, `pyproject.toml`.

## Work

1. In each file add one module logger at the top:
   `logger = logging.getLogger(__name__)`, then replace every
   `logging.info`, `logging.error`, `logging.debug`, `logging.warning` call in
   that file with the same call on `logger`.
2. Replace every `except Exception` with the narrowest exceptions that the
   called code can really raise (`KeyError`, `ValueError`, `TypeError`,
   `OSError`, `json.JSONDecodeError`, Selenium errors, OpenAI errors, and so
   on). Read the called function before choosing.
3. Where the code raises its own failure to the caller, raise the existing
   named error instead of returning `None`, `False` or an empty string.
   Use only the codes in `laf/messages.py`. Do not invent a code. If a real
   failure has no code, keep the current behaviour, log it at warning or
   error level, and list it in your report as a missing code.
4. No `except ...: pass`. If a failure is truly safe to ignore, log it at
   `logger.debug` with the reason in the sentence.
5. Keep every import at the top of the file.

## Edge cases

- A field in a message template must be passed when you raise the error, or
  `messages.render` fails with `KeyError`. Check the template before raising.
- `AiError("AI_UNAVAILABLE")` covers a failed network or auth call to the
  model. `AiError("AI_EMPTY_RESPONSE")` covers an empty answer. Both take no
  fields.
- A missing environment key in `config.py` is `ConfigError("LOGIN_CREDENTIALS_MISSING")`
  only when the key is a login key. Other missing keys have no code yet: keep
  the current default, log a warning, and report it.
- Do not catch an error you then ignore without a log line.
- Do not add a `try` around code that cannot fail.

## Definition of done

Report back, for each of the four files: the except sites before and after,
the logger name used, every new `raise`, and every place you kept the old
behaviour because no code exists. Then run and paste the result of:

```
uv run ruff check laf/config.py laf/ai/client.py laf/ai/content.py laf/services/engage_utils.py
uv run pytest -q
uv run pyright laf/config.py laf/ai/client.py laf/ai/content.py laf/services/engage_utils.py
```

`ruff` must pass. `pytest` must pass. Say plainly if pyright reports errors.

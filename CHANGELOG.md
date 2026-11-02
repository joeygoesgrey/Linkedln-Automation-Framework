# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-10-30

The first release of the rewritten framework. The command line and the `.env`
keys stay the same. The Python code was rebuilt from scratch.

### Added

- Named error codes. Every failure now prints one plain sentence, one fix, and
  the code in square brackets, and `laf/messages.py` holds the text for each
  one. The README has a Troubleshooting table for every code.
- One log file per run, set up in `laf/logging_setup.py`. The config module no
  longer opens its own second file.
- `tools/check_selectors.py`, a helper that opens each page and reports which
  selectors still match. It only looks elements up and never acts.
- A `tests/` folder with a fake driver, so the code can be tested without a
  browser.
- `pyproject.toml` with `uv` for install and dependency locking.

### Changed

- Services replace the old mixins. Each service is a plain class that receives
  the parts it needs, so one workflow no longer depends on a shared base class.
- One frozen `Config` object holds every setting. It is built once at startup,
  and no code can change it after that.
- Every AI prompt sits in `laf/ai/prompts.py`, so the wording is in one place.
- Selectors are split by page under `laf/selectors/`, one file per page.
- The project now needs Python 3.10 or newer.

  **BREAKING CHANGE:** the Python API changed. Code that imported
  `LinkedInBot` from `linkedin_bot`, or used the old mixins, must import from
  `laf.app` and use the service classes. The command line and the `.env` keys
  did not change, so normal users do not need to edit anything.

### Fixed

- The engagement loop called methods that did not exist, so it crashed at once
  (issue 7).
- `post` without `--text` always failed validation, because it was checked
  against the direct post rules. It now uses the topics rules.
- `engage` exited with code 0 after a failed stream. It now returns 1.
- The config module wrote its own second log file beside the main one.

### Removed

- `LinkedInInteraction`, the old class that mixed every workflow into one.
- Every mixin that the browser actions were built from.
- The `linkedin_interaction` import shim.
- The module level config constants. Read settings from `laf.config.CONFIG`.

[2.0.0]: https://github.com/joeygoesgrey/linkedln-bot/releases/tag/v2.0.0

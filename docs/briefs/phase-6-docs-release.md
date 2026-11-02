# Phase 6 brief: docs, changelog, troubleshooting table, release

## Goal

A new user can install the tool, read the README, understand every command,
and fix any error the bot can print, without reading Python. The release notes
say what changed in 2.0.0 and why anyone should care.

Files you may touch: `README.md`, `CHANGELOG.md` (new), `CONTRIBUTING.md`,
`SECURITY.md`, `AGENTS.md`, `docs/FEATURES.md`, `tests/test_readme.py` (new),
`laf/messages.py` only if a code has no plain explanation yet.

Files you may NOT touch: everything under `laf/` except `laf/messages.py`,
`main.py`, `pyproject.toml`, `docs/V2_PLAN.md`, `.env`, anything git ignores.

## Plain text rule

No emojis anywhere in the docs. Nineteen lines carry one today, across
`README.md` and the other markdown files. Delete the emoji, keep the sentence.
No em dashes. No marketing voice: short sentences, a seventh grader can read
them. Keep the existing section order and the code blocks that show commands.

## Facts must match the code

Before writing, open `main.py` and copy the real flags, the real command names
and the real defaults from `laf/config.py`. Do not copy them from the old
README: the old README may be wrong. Where the README and the code disagree,
the code wins and you fix the README. If the code itself is wrong, stop and
report it instead of documenting the wrong thing.

## Troubleshooting table

The bot prints a code in square brackets, for example `[POST_REJECTED]`.
The README gets a "Troubleshooting" section with one table row per code:

| Code | What happened | What to do |

Rules for the table:

- Every code in `MESSAGES` in `laf/messages.py` gets a row. Read the dict, do
  not guess from memory.
- "What happened" is one sentence in plain words, not a copy of the hint.
- "What to do" is the exact action: the `.env` key to set, the file to create,
  the command to run again.
- No row for `UNEXPECTED`. It is the fallback sentence, not a code, and the
  table says in one line what to do if the user sees it.

## The test that keeps the table honest

`tests/test_readme.py` reads `README.md`, finds every row of the form
`| CODE |`, and fails when a code in `MESSAGES` has no row, or a row names a
code that does not exist. It must not import anything that starts a browser.
Write it so a typo in the README table fails the unit test run.

## CHANGELOG.md

Keep a Changelog format, version `2.0.0`, date `2026-10-30`, sections:
Added, Changed, Fixed, Removed. Use these facts, checked against `git log`
between the first commit and `HEAD`:

- Added: named error codes with a plain message and hint, one log file,
  `tools/check_selectors.py`, `tests/` with a fake driver, `pyproject.toml`
  with `uv`.
- Changed: services replace the mixins, one frozen `Config` built once,
  prompts in `laf/ai/prompts.py`, selectors split by page, Python 3.10+.
- Fixed: the engagement loop called methods that did not exist (issue 7),
  `post` without `--text` always failed validation, `engage` exited 0 after a
  failed stream, the config module wrote its own second log file.
- Removed: `LinkedInInteraction`, every mixin, the `linkedin_interaction`
  shim, module level config constants.
- Add a `BREAKING CHANGE:` note in the Changed section: the Python API
  changed, the command line and `.env` keys did not.

## Do not do these

- Do not run the bot live. The Cloudflare challenge blocks it here, and the
  live check of issues 6 and 7 is a manual step the user runs.
- Do not merge `v2` into `main` and do not tag. That happens after the user's
  live run passes.
- Do not touch `docs/V2_PLAN.md`. The session owner updates it.

## Checks

```
uv run ruff check laf/ main.py tests/ tools/
uv run pytest -q
uv run pyright laf/ main.py
uv run python main.py --help
grep -rnP "[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]" *.md docs/*.md
grep -rnP "\x{2014}" *.md docs/*.md
```

The two greps must print nothing. Report the files changed, the number of
table rows, and the command outputs. Do not commit.

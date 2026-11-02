# Phase 4 brief: one home for every AI prompt

## Goal

Every word sent to the language model lives in `laf/ai/prompts.py`. Changing a
prompt means opening one file. The text itself does not change.

Files you may touch:

- `laf/ai/prompts.py` (new), `laf/ai/client.py`, `laf/ai/content.py`
- `tests/test_prompts.py` (new)

Files you may NOT touch: every other module, `main.py`, `docs/`,
`pyproject.toml`.

## What moves

Read `laf/ai/client.py` and `laf/ai/content.py` and move every sentence that
is sent to the model:

- the post prompt template with its structure and rules,
- the comment prompt template,
- the content calendar prompt,
- every system message string passed as `role: system`,
- the persona sentences that name the writer.

Keep the order of the substitution fields and the wording exactly as they are
now. A prompt that becomes a module constant uses named braces, for example
`POST_PROMPT_TEMPLATE = """...{topic}...{style}..."""`, and the caller does
`POST_PROMPT_TEMPLATE.format(topic=..., style=...)`. Where a value today is an
f-string expression, pass it as a named field.

Do not move:

- selectors,
- the fixed local fallback post templates in `content.py`,
- project marketing text (that is settings data, not a prompt),
- docstrings and log sentences.

`laf/ai/prompts.py` must import nothing from `laf`. It holds strings only and
does no work at import.

## Proof that nothing changed

Before the move, render each prompt with sample values and save the output.
After the move, render the same values and diff. The rendered text must be
identical character for character, including newlines and arrows. Report the
diff result.

## Tests to add

`tests/test_prompts.py`:

- every exported template formats with its documented fields and leaves no
  `{` or `}` in the result,
- no prompt contains an em dash (U+2014),
- the persona name appears in the comment prompt path.

## Checks

```
uv run ruff check laf/ main.py tests/
uv run pytest -q
uv run pyright laf/ main.py
uv run python main.py --help
grep -rn "You are\|PROMPT\|role.*system" laf/ai/client.py laf/ai/content.py
```

The grep should find no prompt text left in the two client files, only
references to the imported constants. Report the files changed, the rendered
diff result and the command outputs. Do not commit.

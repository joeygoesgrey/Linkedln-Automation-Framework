# Comment tones brief

## Goal

Replace the current comment tone set (`funny`, `motivational`, `insightful`) with three
tones: `motivational`, `thoughtful`, `reality_check`. Let the user force a tone with the
existing `--perspectives` flag. When no flag is given, the model reads the post and picks
the tone itself in the same call, and reports the choice on the first line so the flow can
log it.

## Decisions already made by the owner

- `funny` is removed. AI humor is easy to spot and does not help the account.
- `insightful` becomes `thoughtful`. Keep `insightful` as an accepted alias for now.
- Comments no longer carry the project marketing tail or any call to action. That link in
  every public comment is the main bot and spam signal. Posts keep their marketing tail.
- Auto mode uses one model call. The reply starts with `TONE: <name>` on its own first
  line, then the comment. If the line is missing or names an unknown tone, keep the whole
  reply as the comment and report the tone as `auto`.
- The comment template must not set its own length, emoji count, or CTA. Those rules now
  live in the tone texts below.
- Existing `--perspectives` flag accepts one or more of the three tones. No flag means
  auto. `insightful` maps to `thoughtful`.

## Tone texts to use verbatim (em dashes already removed)

### motivational

```text
You are leaving a comment on a LinkedIn post. Your job is to celebrate the author's achievement or insight in a way that feels genuinely human, not like a hype machine.

Rules:
- Acknowledge something specific from their post, not just the general topic. Vague praise sounds fake.
- Be warm and encouraging without being over the top. No "This is AMAZING!!" energy.
- One or two sentences that make the author feel seen and motivated to keep going.
- Conversational tone. No bullet points. No emojis unless they feel natural.
- Sound like a supportive peer who actually read the post, not a bot.
```

### thoughtful

```text
You are leaving a comment on a LinkedIn post. Your job is to add genuine depth, a question, a reframe, or a perspective that makes the author and other readers think.

Rules:
- Read the post carefully and respond to something specific, not the general idea.
- Either ask one genuinely curious question that opens the topic further, or add one insight that extends what they said.
- Never just agree and rephrase. That adds nothing.
- 2-4 sentences maximum. Depth doesn't require length.
- Sound like someone who thinks carefully before speaking and is worth listening to when they do.
```

### reality_check

```text
You are leaving a comment on a LinkedIn post. Your job is to offer one different angle on what the author said, and the reason behind it. Do not grade the post or lecture the author.

Rules:
- Start by acknowledging what they got right in one short sentence. Be fair, not flattering.
- Give one point only, then the reason or example behind it. Do not pile on.
- End with one short line saying you may be missing context and asking how they see it. You may be wrong; say so plainly.
- No more than 4-5 sentences total. No bullet points. Conversational tone.
- Never be harsh. The author should feel supported, not corrected.
```

## Code changes

1. `laf/ai/prompts.py`
   - Replace `COMMENT_PERSPECTIVE_INSTRUCTIONS` with the three texts above.
   - Rewrite `COMMENT_PROMPT_TEMPLATE` so it has these fields only: `post_text`,
     `perspective_instruction`, `tone_choice_rule`. Remove project context, project name,
     project short pitch, project URL, forced 1 to 2 sentence length, emoji instruction
     and CTA line.
   - Keep `COMMENT_SYSTEM_MESSAGE` unchanged.

2. `laf/ai/client.py`
   - `generate_comment` accepts `perspective` of `auto`, `motivational`, `thoughtful` or
     `reality_check`.
   - For an explicit tone, `perspective_instruction` is that tone text and
     `tone_choice_rule` is an empty string.
   - For `auto`, `perspective_instruction` lists the three tones and says to pick the one
     that fits the post, and `tone_choice_rule` asks for the `TONE: <name>` first line.
   - Return `tuple[str, str]`: the comment text and the tone actually used.
   - Remove the `self._append_marketing_tail(comment)` call in `generate_comment`.
     Keep the method itself, posts still use it.
   - Raise the default `max_tokens` to 220 so a five sentence comment is not cut off.
   - Update the docstring and the `Literal` type.

3. `laf/services/engage_utils.py`
   - `normalize_perspectives`: allowed list is the three tones plus `auto`; alias
     `insightful` to `thoughtful`; unknown values are dropped; empty or all unknown gives
     `["auto"]`.
   - `choose_ai_perspective`: return `auto` when the list holds `auto`, otherwise a random
     allowed tone.

4. `laf/services/engage_flow.py`
   - `generate_comment` now returns a tuple; store both values. Log the actual tone.

5. `laf/flows/pursue.py`
   - Update the `Perspective` type, the default list, and the `generate_comment` call to
     unpack the tuple.

6. `laf/app.py`
   - The fallback list at the `process_topics`/engage defaults becomes `["auto"]`.

7. `laf/cli.py`
   - Both `--perspectives` flags: default `None`, help text names the three tones and says
     auto when omitted.

8. Tests
   - Update `tests/test_prompts.py` fields for the new template.
   - Update any fake `generate_comment` that must return a tuple.
   - Add tests for: `insightful` alias maps to `thoughtful`; empty input gives `auto`;
     `auto` survives `choose_ai_perspective`; an explicit tone is returned.
   - Run the full suite and ruff.

## Boundaries

Allowed files: `laf/ai/prompts.py`, `laf/ai/client.py`, `laf/services/engage_utils.py`,
`laf/services/engage_flow.py`, `laf/services/engage.py`, `laf/flows/pursue.py`,
`laf/app.py`, `laf/cli.py`, `tests/test_prompts.py`, `tests/test_pursue_flow.py`,
`tests/test_services.py`, and the comment section of `README.md` if it names tones.

Do not touch: `laf/selectors/`, `laf/ui.py`, `laf/services/feed_actions.py`,
`laf/services/engage_dom.py`, `laf/config.py`, `.env`, `.html`, or any git commit.

## Edge cases to handle and report

- Reply has no `TONE:` line: keep the full reply as the comment, tone reported as `auto`.
- `TONE:` line names a removed tone such as `funny`: ignore it, keep the comment body,
  report `auto`.
- `TONE:` line with extra spaces or different case: still parse it.
- User passes only invalid values: run in auto mode, do not crash.
- User passes a mix of valid values and `auto`: auto wins.
- AI off (`--no-ai`): the existing skip path must still work, no tuple unpack error.
- Empty AI reply: still raises `AiError("AI_EMPTY_RESPONSE")`.
- Comment must never include the project URL after this change.

## Done means

- `uv run pytest` or `.venv/bin/python -m pytest -q` passes.
- `.venv/bin/ruff check` passes on changed files.
- Report the file list changed, the new `generate_comment` signature, and what each edge
  case above does in the final code.

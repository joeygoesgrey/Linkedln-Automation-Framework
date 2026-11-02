"""Guard the prompt constants in ``laf.ai.prompts`` against silent breakage."""

from laf.ai import prompts

# The fields each exported prompt expects, so a rename or a missing brace fails here.
DOCUMENTED_FIELDS: dict[str, dict[str, object]] = {
    "POST_STYLE_TEMPLATES": {},
    "POST_PROMPT_TEMPLATE": {
        "topic": "AI safety",
        "style": "professional",
        "style_instruction": "Be clear.",
        "project_name": "Sample Project",
        "project_pitch": "a sample pitch",
        "project_url": "https://example.test/x",
        "project_context": "sample context",
    },
    "POST_SYSTEM_MESSAGE": {},
    "COMMENT_PERSPECTIVE_INSTRUCTIONS": {},
    "COMMENT_PROMPT_TEMPLATE": {
        "post_text": "A post about hiring.",
        "perspective_instruction": "Be thoughtful.",
        "tone_choice_rule": "",
    },
    "COMMENT_SYSTEM_MESSAGE": {},
    "CALENDAR_INSPIRATION_CLAUSE": {"inspiration": "Naval Ravikant"},
    "CALENDAR_PERSONAL_STORY_CLAUSE": {"personal_story": "my first launch"},
    "CALENDAR_PROMPT_TEMPLATE": {
        "total_posts": 2,
        "niche": "tech",
        "goal": "growth",
        "audience": "developers",
        "tone": "friendly",
        "content_types": "carousel, video",
        "frequency": "3 times a week",
        "hashtags": "#AI, #Tech",
        "inspiration_clause": "",
        "personal_clause": "",
    },
    "CALENDAR_SYSTEM_MESSAGE": {},
}

PERSONA_NAME = "Joseph Edomobi"


def _exported_prompts() -> dict[str, str | dict[str, str]]:
    """Return every public string or string map defined in the prompts module.

    WHY
        A prompt added later must be covered by these checks without anyone
        editing the test, so the test reads the module instead of a fixed list.

    Returns
        dict[str, str | dict[str, str]]: export name to its value.
    """
    return {
        name: value
        for name, value in vars(prompts).items()
        if not name.startswith("_") and isinstance(value, (str, dict))
    }


def _all_text() -> list[str]:
    """Return every prompt string, flattening the exported maps.

    WHY
        Style and perspective maps hold prompt sentences too, so a check that
        skips them would let a change slip through.

    Returns
        list[str]: all prompt text in the module.
    """
    texts: list[str] = []
    for value in _exported_prompts().values():
        if isinstance(value, str):
            texts.append(value)
        else:
            texts.extend(value.values())
    return texts


def test_every_export_is_documented_and_formats_cleanly() -> None:
    """Each exported template formats with its fields and leaves no braces.

    WHY
        A typo in a brace, or a new prompt with no sample fields, would send a
        literal ``{topic}`` to the model. This fails first.
    """
    exported = _exported_prompts()

    assert set(exported) == set(DOCUMENTED_FIELDS)

    for name, value in exported.items():
        fields = DOCUMENTED_FIELDS[name]
        rendered = (
            [value.format(**fields)]
            if isinstance(value, str)
            else [item.format(**fields) for item in value.values()]
        )
        for text in rendered:
            assert "{" not in text, name
            assert "}" not in text, name


def test_no_prompt_contains_an_em_dash() -> None:
    """No prompt text uses U+2014.

    WHY
        House style bans the em dash in all written output, prompts included.
    """
    for text in _all_text():
        assert chr(0x2014) not in text


def test_persona_name_is_in_the_comment_prompt_path() -> None:
    """The comment system message names the writer the model must imitate.

    WHY
        Without the persona sentence the model drops Joseph's voice, which is
        the whole point of the comment prompt.
    """
    assert PERSONA_NAME in prompts.COMMENT_SYSTEM_MESSAGE

"""Selectors for mentioning users and entities in the composer.

WHY
  Serve the mention typeahead, so the suggestion list and option selectors can
  change without touching the composer code.
"""


class MentionSelectors:
    """Selectors for mentioning users/entities in the composer.

    WHY
      Serve the mention typeahead list and its option items, so a popup change
      has one file to update.
    """

    SUGGESTIONS = [
        "//div[contains(@class,'typeahead') and contains(@class,'artdeco')]//li",
        "//div[contains(@class,'mentions') and contains(@class,'suggest')]//li",
        "//div[contains(@class,'ember-view') and contains(@class,'typeahead')]//li",
        "//div[contains(@class,'editor-typeahead-fetch')]//*[self::li or self::button or self::a]",
        "//div[contains(@role,'listbox')]//li",
        "//ul[contains(@class,'suggest') or contains(@class,'results')]//li",
    ]  # linkedin_ui/mentions.py:341

    TYPEAHEAD_CONTAINERS = [
        "//div[contains(@class,'editor-typeahead-fetch')]",
        "//div[contains(@class,'typeahead') and contains(@class,'artdeco')]",
        "//div[contains(@class,'mentions') and contains(@class,'suggest')]",
        "//div[contains(@role,'listbox')]",
    ]  # linkedin_ui/mentions.py:398

    ENTITY_TEMPLATES = [
        ".//*[contains(@class,'ql-mention') and contains(normalize-space(.), \"{t}\")]",
        ".//*[contains(@class,'mention') and contains(normalize-space(.), \"{t}\")]",
        ".//*[contains(@class,'entity') and contains(normalize-space(.), \"{t}\")]",
        './/a[contains(normalize-space(.), "{t}")]',
    ]  # linkedin_ui/mentions.py:497

    FIRST_SUGGESTION_ROOTS = [
        "//div[contains(@class,'editor-typeahead-fetch')]",
        "//div[contains(@class,'typeahead') and contains(@class,'artdeco')]",
    ]  # linkedin_ui/mentions.py:563

    FIRST_SUGGESTION_OPTIONS = [
        ".//div[contains(@class,'basic-typeahead__selectable') and @role='option'][1]",
        ".//*[@role='option'][1]",
        ".//li[1]",
    ]  # linkedin_ui/mentions.py:575

    FALLBACK_SUGGESTIONS = [
        "//div[contains(@class,'typeahead') and contains(@class,'artdeco')]//li[.//button or .]",
        "//div[contains(@class,'mentions') and contains(@class,'suggest')]//li",
        "//div[contains(@role,'listbox')]//li",
        "//ul[contains(@class,'suggest') or contains(@class,'results')]//li",
    ]  # linkedin_ui/mentions.py:602

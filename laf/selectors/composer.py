"""Selectors for the post composer and feed start buttons.

WHY
  Keep the composer and scheduling selectors in one file, so the editor markup
  can change without touching the page that hosts it.

The live LinkedIn page ships hashed class names, so every selector below keys
off a data attribute, an aria label or the visible text first. Class names are
the last resort.
"""


class ComposerSelectors:
    """Selectors for the post composer and feed start buttons.

    WHY
      Serve the post editor and its schedule controls, so a markup change there
      has one file to update.
    """

    START_POST_TRIGGERS = [
        "//div[@data-view-name='share-sharebox-focus']",
        "//button[@data-view-name='share-sharebox-focus']",
        "//div[@role='button'][normalize-space(.)='Start a post']",
        "//button[normalize-space(.)='Start a post']",
        "//button[@aria-label='Start a post']",
        "//div[@role='button'][contains(., 'Start a post')]",
    ]

    POST_EDITOR = [
        "//div[@contenteditable='true' and @role='textbox']",
        "//div[contains(@class, 'ProseMirror')]",
        "//div[contains(@class, 'ql-editor')]",
        "//div[contains(@aria-placeholder, 'What do you want to talk about?')]",
    ]

    POST_BUTTON = [
        "//button[@data-view-name='share-post']",
        "//button[normalize-space(.)='Post']",
        "//span[normalize-space(.)='Post']/parent::button",
        "//button[contains(@aria-label, 'Post')]",
    ]

    SCHEDULE_BUTTONS = [
        "//button[@data-view-name='share-schedule-picker-open']",
        "//button[@aria-label='Scheduled']",
        "//button[contains(@aria-label, 'Schedule')]",
    ]

    SCHEDULE_DATE_INPUTS = [
        "//input[@placeholder='mm/dd/yyyy']",
        "//input[@aria-label='Date']",
        "//label[contains(., 'Date')]/following::input[1]",
    ]

    SCHEDULE_TIME_INPUTS = [
        "//input[@data-testid='time-picker-input']",
        "//input[@aria-label='Time']",
        "//button[@aria-label='Open time picker']/preceding-sibling::input[1]",
    ]

    SCHEDULE_CONFIRM_BUTTONS = [
        "//button[normalize-space(.)='Confirm']",
        "//button[.//span[normalize-space()='Confirm']]",
        "//button[.//span[normalize-space()='Schedule']]",
    ]

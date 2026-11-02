"""Plain English messages and hints for every error code."""

from laf.errors import LAFError

MESSAGES: dict[str, tuple[str, str]] = {
    "LOGIN_CREDENTIALS_MISSING": (
        "The LinkedIn username or password is missing.",
        "Add LINKEDIN_USERNAME and LINKEDIN_PASSWORD to your .env file.",
    ),
    "LOGIN_REJECTED": (
        "LinkedIn did not accept the username or password.",
        "Check the credentials in your .env file and try again.",
    ),
    "LOGIN_TIMEOUT": (
        "The login page did not finish loading in time.",
        "Check your internet connection and run the command again.",
    ),
    "LOGIN_2FA_MISSING": (
        "LinkedIn asked for a two factor code but no code was given.",
        "Run the command again and type the code when the prompt appears.",
    ),
    "LOGIN_2FA_REJECTED": (
        "LinkedIn did not accept the two factor code.",
        "Wait for a new code and enter it carefully on the next run.",
    ),
    "COMPOSER_NOT_OPEN": (
        "The post composer did not open.",
        "Reload the feed, then run the command again.",
    ),
    "COMPOSER_EDITOR_MISSING": (
        "The text box inside the post composer was not found.",
        "Reload the feed, then run the command again.",
    ),
    "COMPOSER_POST_BUTTON_MISSING": (
        "The Post button was not found in the composer.",
        "Check that the page loaded fully, then run the command again.",
    ),
    "POST_TEXT_FAILED": (
        "The post text could not be written into the post box.",
        "Click inside the post box, then run the command again.",
    ),
    "POST_BUTTON_UNCLICKABLE": (
        "The Post button was found but could not be clicked.",
        "Wait for the page to finish loading, then run the command again.",
    ),
    "POST_BROWSER_FAILED": (
        "The browser reported an error during the post.",
        "Run the command again. If it keeps failing, check the log file.",
    ),
    "POST_REJECTED": (
        "LinkedIn did not accept the post.",
        "Shorten or edit the text, then run the command again.",
    ),
    "IMAGE_DIR_MISSING": (
        "The image folder {path} does not exist.",
        "Check the folder path and run the command again.",
    ),
    "IMAGE_NONE_FOUND": (
        "The folder {path} holds no image files.",
        "Add at least one jpg or png file and run the command again.",
    ),
    "IMAGE_UPLOAD_FAILED_PATH": (
        "The image at {path} could not be opened.",
        "Check that the file exists and that you can read it.",
    ),
    "IMAGE_UPLOAD_FAILED_SIZE": (
        "The image at {path} is too large for LinkedIn.",
        "Use an image smaller than the upload limit and try again.",
    ),
    "IMAGE_UPLOAD_FAILED_FORMAT": (
        "The file at {path} is not an image type LinkedIn accepts.",
        "Use a jpg or png file and try again.",
    ),
    "SCHEDULE_DATE_INVALID": (
        "The date {value} is not a valid future date.",
        "Use the mm/dd/yyyy format and pick a day after today.",
    ),
    "SCHEDULE_TIME_INVALID": (
        "The time {value} is not a valid clock time.",
        "Use a time such as 10:45 AM and pick a minute inside the day.",
    ),
    "SCHEDULE_CONTROL_MISSING": (
        "The {control} was not found in the composer.",
        "Check that you can schedule posts in the LinkedIn composer, then run the command again.",
    ),
    "TOPICS_FILE_MISSING": (
        "The topics file {path} does not exist.",
        "Check the file path and run the command again.",
    ),
    "TOPICS_FILE_EMPTY": (
        "The topics file {path} has no topics in it.",
        "Add one topic per line and run the command again.",
    ),
    "TOPICS_NONE_REMAINING": (
        "Every topic in the file was already posted.",
        "Add new topics to the file and run the command again.",
    ),
    "FEED_LOAD_FAILED": (
        "The feed did not load.",
        "Check your internet connection and run the command again.",
    ),
    "FEED_ACTION_BAR_MISSING": (
        "The action bar under the post was not found.",
        "Reload the feed, then run the command again.",
    ),
    "LIKE_BUTTON_MISSING": (
        "The Like button was not found on the post.",
        "Reload the feed, then run the command again.",
    ),
    "FEED_NO_POSTS": (
        "No posts were found in the feed.",
        "Scroll the feed or follow more people, then run the command again.",
    ),
    "COMMENT_BOX_MISSING": (
        "The comment box did not open.",
        "Reload the feed, then run the command again.",
    ),
    "COMMENT_TEXT_EMPTY": (
        "The comment text is empty.",
        "Write a comment or turn on the AI writer, then run the command again.",
    ),
    "COMMENT_SUBMIT_MISSING": (
        "The comment submit button was not found.",
        "Reload the feed, then run the command again.",
    ),
    "REPOST_MENU_MISSING": (
        "The repost menu did not open.",
        "Reload the feed, then run the command again.",
    ),
    "REPOST_OPTION_MISSING": (
        "The repost with thoughts option was not found.",
        "Reload the feed, then run the command again.",
    ),
    "REPOST_NO_THOUGHTS": (
        "The repost thoughts text is empty.",
        "Write your thoughts or turn on the AI writer, then run the command again.",
    ),
    "REPOST_SHARE_MISSING": (
        "The repost share button was not found.",
        "Reload the feed, then run the command again.",
    ),
    "AI_UNAVAILABLE": (
        "The AI service could not be reached.",
        "Check your API key and internet connection, then run the command again.",
    ),
    "AI_EMPTY_RESPONSE": (
        "The AI service returned no text.",
        "Run the command again, or write the text yourself.",
    ),
    "ENGAGE_POST_FAILED": (
        "One post could not be engaged because {reason}.",
        "Check the log file for the details and run the command again.",
    ),
    "PROFILE_NOT_FOUND": (
        "The profile for {name} was not found.",
        "Check the spelling of the name and run the command again.",
    ),
    "PROFILE_FOLLOW_MISSING": (
        "The Follow button was not found on the profile.",
        "Open the profile in a browser and check you can follow it.",
    ),
    "PROFILE_NO_POSTS": (
        "The profile has no posts to work on.",
        "Pick a different profile and run the command again.",
    ),
    "CALENDAR_WRITE_FAILED": (
        "The calendar file at {path} could not be written.",
        "Check that the folder exists and that you can write to it.",
    ),
    "MENTION_TYPEAHEAD_MISSING": (
        "The mention suggestion list did not open.",
        "Type the name slowly after the at sign and run the command again.",
    ),
    "MENTION_NO_MATCH": (
        "No suggestion matched the name {name}.",
        "Use the full name as it appears on LinkedIn and run the command again.",
    ),
    "MENTION_NOT_CONFIRMED": (
        "The mention for {name} was not confirmed.",
        "Pick the person from the list yourself, then run the command again.",
    ),
    "POST_VERIFY_TIMEOUT": (
        "The post was not seen on the profile in time.",
        "Check the profile in a browser before you run the command again.",
    ),
    "POST_VERIFY_ERROR_SHOWN": (
        "LinkedIn showed an error after the post was submitted.",
        "Read the error on screen and fix the post before you try again.",
    ),
    "CHROME_NOT_FOUND": (
        "No Chrome or Chromium browser was found on this computer.",
        "Install Google Chrome, then run the command again.",
    ),
    "DRIVER_ALL_ATTEMPTS_FAILED": (
        "The browser could not be started.",
        "Close any open Chrome windows, then run the command again.",
    ),
    "DRIVER_OPTIONAL_PACKAGE_MISSING": (
        "The optional package {package} is not installed.",
        "Install it with uv sync --extra stealth, then run the command again.",
    ),
}


UNEXPECTED: tuple[str, str] = (
    "The bot hit an unexpected problem.",
    "Run the command again with --debug and check the log file for the details.",
)


def render(error: LAFError) -> tuple[str, str]:
    """Turn an error into its message and hint sentences.

    WHY
        The error object carries data only, so one place must join that data
        with the templates without hiding a bad code or a missing field.

    Args
        error: a LAFError with a code and the fields the template needs.

    Returns
        tuple[str, str]: the message and the hint, both ready to print.

    Raises
        KeyError: when the code has no template.
        KeyError: when a template field is missing from the error fields.
    """
    message_template, hint_template = MESSAGES[error.code]
    return message_template.format(**error.fields), hint_template.format(**error.fields)

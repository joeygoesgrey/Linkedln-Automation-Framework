"""Prove every error code renders, and that render stays strict on bad input."""

from string import Formatter

import pytest

from laf.errors import (
    AiError,
    CalendarError,
    CommentError,
    ComposerError,
    DriverError,
    EngageError,
    FeedError,
    LAFError,
    LoginError,
    MediaError,
    MentionError,
    PostError,
    ProfileError,
    RepostError,
    ScheduleError,
    TopicsError,
    VerifyError,
)
from laf.messages import MESSAGES, render

EXPECTED_CODES = {
    "LOGIN_CREDENTIALS_MISSING",
    "LOGIN_REJECTED",
    "LOGIN_TIMEOUT",
    "LOGIN_2FA_MISSING",
    "LOGIN_2FA_REJECTED",
    "COMPOSER_NOT_OPEN",
    "COMPOSER_EDITOR_MISSING",
    "COMPOSER_POST_BUTTON_MISSING",
    "POST_REJECTED",
    "POST_TEXT_FAILED",
    "POST_BUTTON_UNCLICKABLE",
    "POST_BROWSER_FAILED",
    "IMAGE_DIR_MISSING",
    "IMAGE_NONE_FOUND",
    "IMAGE_UPLOAD_FAILED_PATH",
    "IMAGE_UPLOAD_FAILED_SIZE",
    "IMAGE_UPLOAD_FAILED_FORMAT",
    "SCHEDULE_DATE_INVALID",
    "SCHEDULE_TIME_INVALID",
    "SCHEDULE_CONTROL_MISSING",
    "TOPICS_FILE_MISSING",
    "TOPICS_FILE_EMPTY",
    "TOPICS_NONE_REMAINING",
    "FEED_LOAD_FAILED",
    "FEED_ACTION_BAR_MISSING",
    "LIKE_BUTTON_MISSING",
    "FEED_NO_POSTS",
    "COMMENT_BOX_MISSING",
    "COMMENT_TEXT_EMPTY",
    "COMMENT_SUBMIT_MISSING",
    "REPOST_MENU_MISSING",
    "REPOST_OPTION_MISSING",
    "REPOST_NO_THOUGHTS",
    "REPOST_SHARE_MISSING",
    "AI_UNAVAILABLE",
    "AI_EMPTY_RESPONSE",
    "ENGAGE_POST_FAILED",
    "PROFILE_NOT_FOUND",
    "PROFILE_FOLLOW_MISSING",
    "PROFILE_NO_POSTS",
    "CALENDAR_WRITE_FAILED",
    "MENTION_TYPEAHEAD_MISSING",
    "MENTION_NO_MATCH",
    "MENTION_NOT_CONFIRMED",
    "POST_VERIFY_TIMEOUT",
    "POST_VERIFY_ERROR_SHOWN",
    "CHROME_NOT_FOUND",
    "DRIVER_ALL_ATTEMPTS_FAILED",
    "DRIVER_OPTIONAL_PACKAGE_MISSING",
}

CLASS_BY_PREFIX: dict[str, type[LAFError]] = {
    "LOGIN": LoginError,
    "COMPOSER": ComposerError,
    "POST": PostError,
    "IMAGE": MediaError,
    "SCHEDULE": ScheduleError,
    "TOPICS": TopicsError,
    "FEED": FeedError,
    "LIKE": FeedError,
    "COMMENT": CommentError,
    "REPOST": RepostError,
    "AI": AiError,
    "ENGAGE": EngageError,
    "PROFILE": ProfileError,
    "CALENDAR": CalendarError,
    "MENTION": MentionError,
    "CHROME": DriverError,
    "DRIVER": DriverError,
}


def _class_for(code: str) -> type[LAFError]:
    """Pick the error subclass that owns one code.

    WHY
        The loop test must build a real subclass per code, not a bare LAFError,
        so a missing area class is caught.

    Args
        code: uppercase code from MESSAGES.

    Returns
        type[LAFError]: the subclass for that code's area.
    """
    if code.startswith("POST_VERIFY_"):
        return VerifyError
    prefix = code.split("_", 1)[0]
    return CLASS_BY_PREFIX[prefix]


def _template_fields(template: str) -> set[str]:
    """List the field names one message template needs.

    WHY
        The loop test needs dummy values for exactly the fields a template asks
        for, or render would raise for a reason unrelated to the code.

    Args
        template: a message or hint string with braces.

    Returns
        set[str]: field names found in the template.
    """
    return {name for _, name, _, _ in Formatter().parse(template) if name}


def _dummy_fields_for(code: str) -> dict[str, str]:
    """Build placeholder values for every field a code's templates use.

    WHY
        One code can ask for the same field in the message and in the hint, and
        the union keeps the loop simple.

    Args
        code: uppercase code from MESSAGES.

    Returns
        dict[str, str]: field names mapped to a test value.
    """
    message_template, hint_template = MESSAGES[code]
    names = _template_fields(message_template) | _template_fields(hint_template)
    return {name: "test" for name in names}


def test_messages_cover_exactly_the_expected_codes() -> None:
    """The message table has every agreed code and no extra code."""
    assert set(MESSAGES) == EXPECTED_CODES


def test_every_code_builds_its_subclass_and_renders() -> None:
    """Each code builds an area error and renders a message and a hint."""
    for code in sorted(MESSAGES):
        error_class = _class_for(code)
        error = error_class(code, **_dummy_fields_for(code))

        assert isinstance(error, LAFError)
        assert type(error) is not LAFError
        assert str(error) == code

        message, hint = render(error)
        assert message
        assert hint
        assert "{" not in message
        assert "{" not in hint


def test_render_raises_for_an_unknown_code() -> None:
    """A code with no template raises KeyError instead of printing a fallback."""
    with pytest.raises(KeyError):
        render(LAFError("NOT_A_REAL_CODE"))


def test_render_raises_when_a_field_is_missing() -> None:
    """A template field with no value raises KeyError instead of hiding it."""
    with pytest.raises(KeyError):
        render(LAFError("IMAGE_DIR_MISSING"))


def test_error_keeps_the_code_and_the_fields() -> None:
    """The error stores the code as text and the field data as a dict."""
    error = LAFError("PROFILE_NOT_FOUND", name="Ada")

    assert error.code == "PROFILE_NOT_FOUND"
    assert error.fields == {"name": "Ada"}


def test_driver_error_takes_the_package_field() -> None:
    """A optional package failure renders the package name from its field."""
    message, hint = render(
        DriverError("DRIVER_OPTIONAL_PACKAGE_MISSING", package="undetected-chromedriver")
    )

    assert message == "The optional package undetected-chromedriver is not installed."
    assert "uv sync --extra stealth" in hint

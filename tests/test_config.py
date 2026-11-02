"""Prove the frozen Config loads defaults, reads overrides and stays immutable."""

import logging
import pathlib
from dataclasses import FrozenInstanceError

import pytest

from laf.config import Config, load_config


def test_defaults_from_empty_env() -> None:
    """
    WHY
      An empty environment must reproduce the old module constants, or startup
      with no .env file would silently change defaults.
    """

    config = load_config({})

    assert isinstance(config, Config)
    assert config.linkedin_username is None
    assert config.linkedin_password is None
    assert config.openai_api_key is None
    assert config.openai_model == "gpt-4o-mini"
    assert config.marketing_mode is True
    assert config.project_name == "LinkedIn Bot"
    assert config.headless is True
    assert config.window_size == (1920, 1080)
    assert config.min_typing_delay == 0.05
    assert config.max_typing_delay == 0.15
    assert config.min_action_delay == 1
    assert config.max_action_delay == 3
    assert config.min_page_load_delay == 2
    assert config.max_page_load_delay == 5
    assert config.element_timeout == 10
    assert config.short_timeout == 5
    assert config.default_topic_file == "Topics.txt"
    assert config.log_directory == "logs"
    assert config.custom_posts_file == "CustomPosts.txt"
    assert config.max_post_length == 1300
    assert config.enable_text_preprocessing is False
    assert config.summarize_input is False
    assert config.summarize_ratio == 0.3
    assert config.max_input_chars == 3200
    assert config.capture_typeahead_html is False
    assert config.typeahead_capture_dir == str(
        pathlib.Path("logs") / "typeahead"
    )


def test_window_size_is_a_tuple_and_config_is_hashable() -> None:
    """
    WHY
      A dict or list window size would make the frozen instance unhashable, so
      this pins the field to a tuple of two ints.
    """

    config = load_config({})

    assert isinstance(config.window_size, tuple)
    assert all(isinstance(part, int) for part in config.window_size)
    assert isinstance(hash(config), int)


def test_env_overrides_are_read() -> None:
    """
    WHY
      Callers pass a plain dict, so every documented key must be read from that
      mapping instead of the real process environment.
    """

    env = {
        "LINKEDIN_USERNAME": "alice",
        "LINKEDIN_PASSWORD": "secret",
        "OPENAI_API_KEY": "key-123",
        "OPENAI_MODEL": "gpt-4o",
        "MARKETING_MODE": "FALSE",
        "HEADLESS": "false",
        "SUMMARIZE_INPUT": "TRUE",
        "ENABLE_TEXT_PREPROCESSING": "True",
        "MIN_TYPING_DELAY": "0.2",
        "ELEMENT_TIMEOUT": "30",
        "CUSTOM_POSTS_FILE": "posts.txt",
    }

    config = load_config(env)

    assert config.linkedin_username == "alice"
    assert config.linkedin_password == "secret"
    assert config.openai_api_key == "key-123"
    assert config.openai_model == "gpt-4o"
    assert config.marketing_mode is False
    assert config.headless is False
    assert config.summarize_input is True
    assert config.enable_text_preprocessing is True
    assert config.min_typing_delay == 0.2
    assert config.element_timeout == 30
    assert config.custom_posts_file == "posts.txt"


def test_malformed_float_keeps_default_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    """
    WHY
      A bad numeric value must not crash import; it falls back and leaves one
      warning so the mistake is visible.
    """

    with caplog.at_level(logging.WARNING, logger="laf.config"):
        config = load_config({"SUMMARIZE_RATIO": "not-a-number"})

    assert config.summarize_ratio == 0.3
    assert len(caplog.records) == 1
    assert "Invalid float value" in caplog.records[0].getMessage()


def test_malformed_int_keeps_default_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    """
    WHY
      A bad integer value must fall back to its default and warn once, matching
      the old helper behaviour.
    """

    with caplog.at_level(logging.WARNING, logger="laf.config"):
        config = load_config({"MAX_INPUT_CHARS": "many"})

    assert config.max_input_chars == 3200
    assert len(caplog.records) == 1
    assert "Invalid integer value" in caplog.records[0].getMessage()


def test_empty_numeric_string_is_malformed(caplog: pytest.LogCaptureFixture) -> None:
    """
    WHY
      An empty string counts as a real value, so float("") fails and the default
      plus one warning must follow.
    """

    with caplog.at_level(logging.WARNING, logger="laf.config"):
        config = load_config({"SUMMARIZE_RATIO": ""})

    assert config.summarize_ratio == 0.3
    assert len(caplog.records) == 1


def test_headless_override_true_beats_env_false() -> None:
    """
    WHY
      A runtime flag must win over the environment so a --headless call is never
      silently ignored.
    """

    config = load_config({"HEADLESS": "false"}, headless_override=True)

    assert config.headless is True


def test_headless_override_false_beats_env_true() -> None:
    """
    WHY
      The override must also force the browser visible when env asks for
      headless, so both directions of the flag are honoured.
    """

    config = load_config({"HEADLESS": "true"}, headless_override=False)

    assert config.headless is False


def test_headless_override_none_uses_env() -> None:
    """
    WHY
      Passing no override must leave the environment value untouched, which is
      the default call path.
    """

    config = load_config({"HEADLESS": "false"}, headless_override=None)

    assert config.headless is False


def test_frozen_config_rejects_assignment() -> None:
    """
    WHY
      A setting changed after startup would make different modules disagree, so
      every assignment must raise FrozenInstanceError.
    """

    config = load_config({})

    with pytest.raises(FrozenInstanceError):
        config.headless = False  # type: ignore[misc]


def test_module_alias_headless_is_gone() -> None:
    """
    WHY
      Settings now live only on Config, so importing an old module constant
      must fail loudly instead of quietly returning a second copy.
    """

    with pytest.raises(ImportError):
        exec("from laf.config import HEADLESS")

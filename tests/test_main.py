"""Prove the command line turns failures into plain text and exit codes."""

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import main
from laf.errors import PostError
from laf.models import CalendarModel
from laf.ui import SelectorMiss


class FakeBot:
    """A bot stand-in that records calls and can fail on demand."""

    def __init__(self, app) -> None:
        """Store the app the real bot takes and nothing else.

        WHY
            main builds the bot from the app, so the stand-in must accept it to
            stand in.

        Args
            app: the stand-in app main built.
        """
        self.app = app
        self.closed = False

    def close(self) -> None:
        """Record that main closed the bot.

        WHY
            main must always release the bot, including on failure.
        """
        self.closed = True

    def post_custom_text(self, **kwargs) -> None:
        """Fail the way a rejected post fails.

        WHY
            The test needs one real failure at the service layer.

        Args
            kwargs: the post values from main.

        Raises
            PostError: always, with the POST_REJECTED code.
        """
        raise PostError("POST_REJECTED")


def _run(monkeypatch, argv: list[str], app=None, log_file=None) -> tuple[int, FakeBot]:
    """Run main with a fixed command line and a fake bot.

    WHY
        The boundary tests share the same setup, and repeating it hides what
        each test really checks.

    Args
        monkeypatch: pytest fixture that patches names.
        argv: the command line without the program name.
        app: object, the app main receives, or None for a plain stand-in.
        log_file: Path, the file configure_logging should claim it opened.

    Returns
        tuple[int, FakeBot]: the exit code and the bot main built.
    """
    fake = FakeBot(object() if app is None else app)
    monkeypatch.setattr(main, "build_app", lambda **kwargs: fake.app)
    monkeypatch.setattr(main, "LinkedInBot", lambda app: fake)
    monkeypatch.setattr(main, "configure_logging", lambda debug: log_file)
    monkeypatch.setattr("sys.argv", ["main.py", *argv])
    return main.main(), fake


def test_named_error_prints_its_message_and_hint(monkeypatch, caplog) -> None:
    """A named error becomes its message and hint, and exit code 1."""
    with caplog.at_level(logging.ERROR):
        code, fake = _run(monkeypatch, ["post", "--text", "hello"])

    assert code == 1
    assert fake.closed
    assert "LinkedIn did not accept the post." in caplog.text
    assert "Shorten or edit the text" in caplog.text
    assert "POST_REJECTED" in caplog.text


def test_failed_run_names_the_log_file(monkeypatch, caplog) -> None:
    """A failed run tells the user where the selector detail lives.

    WHY
        The screen only holds a plain sentence, so the user needs the log path
        to find which selectors were tried.
    """
    log_file = Path("logs") / "laf_test.log"

    with caplog.at_level(logging.ERROR):
        code, _ = _run(monkeypatch, ["post", "--text", "hello"], log_file=log_file)

    assert code == 1
    assert "Log file: logs/laf_test.log" in caplog.text


def test_failed_run_names_the_last_selector_miss(monkeypatch, caplog) -> None:
    """A failed run says how many selectors were tried and on which page.

    WHY
        Without this line the user knows a control was missing but not how hard
        the bot looked or where, which is exactly what the selector hunt needs.
    """
    miss = SelectorMiss(
        candidates=("xpath //button[@data-view-name='share-post']", "xpath //button"),
        page="https://www.linkedin.com/feed/",
        seconds=2.0,
    )
    app = SimpleNamespace(
        services=SimpleNamespace(ui=SimpleNamespace(last_miss=miss))
    )

    with caplog.at_level(logging.ERROR):
        code, _ = _run(monkeypatch, ["post", "--text", "hello"], app=app)

    assert code == 1
    assert "Last selector miss: 2 selectors tried on https://www.linkedin.com/feed/" in caplog.text


def test_unexpected_error_prints_the_plain_sentence(monkeypatch, caplog) -> None:
    """An unnamed error becomes the plain unexpected sentence, not a trace."""
    fake = FakeBot(object())

    def explode(**kwargs) -> None:
        raise RuntimeError("a raw library error")

    fake.post_custom_text = explode
    monkeypatch.setattr(main, "build_app", lambda **kwargs: fake.app)
    monkeypatch.setattr(main, "LinkedInBot", lambda app: fake)
    monkeypatch.setattr(main, "configure_logging", lambda debug: None)
    monkeypatch.setattr("sys.argv", ["main.py", "post", "--text", "hello"])

    with caplog.at_level(logging.ERROR):
        code = main.main()

    assert code == 1
    assert "The bot hit an unexpected problem." in caplog.text
    assert "Run the command again with --debug" in caplog.text
    assert "Traceback" not in caplog.text


def test_bad_max_actions_is_rejected_at_the_border(monkeypatch, caplog) -> None:
    """A number below the model limit stops before the bot is built."""
    with caplog.at_level(logging.ERROR):
        code, _ = _run(monkeypatch, ["engage", "--max-actions", "0"])

    assert code == 1
    assert "The command values are not valid" in caplog.text
    assert "max_actions" in caplog.text


def test_describe_validation_names_every_field() -> None:
    """The helper lists each rejected field with its reason."""
    with pytest.raises(ValidationError) as caught:
        CalendarModel(niche="", total_posts=0)

    text = main._describe_validation(caught.value)

    assert "niche" in text
    assert "total_posts" in text


class _FakeLogin:
    """A login service that always succeeds."""

    def login(self) -> bool:
        """Report a finished login so the engage flow is reached.

        Returns
            bool: always True.
        """
        return True


class _FakeEngage:
    """An engage service that returns a fixed result."""

    def __init__(self, result: bool) -> None:
        """Store the result the stream should report.

        Args
            result: bool, the value engage_stream returns.
        """
        self.result = result

    def engage_stream(self, **kwargs) -> bool:
        """Report the stored result without touching a browser.

        Args
            kwargs: the values main passes to the real service.

        Returns
            bool: the stored result.
        """
        return self.result


@pytest.mark.parametrize(("result", "expected"), [(True, 0), (False, 1)])
def test_engage_exit_code_follows_the_stream_result(
    monkeypatch, result: bool, expected: int
) -> None:
    """A stream that reports failure must not exit 0.

    WHY
        The command is scripted. Exit 0 after a failed stream tells the caller
        the run worked, and the old code did exactly that.

    Args
        monkeypatch: pytest fixture that patches names.
        result: bool, what the fake engage service returns.
        expected: int, the exit code the caller should see.
    """
    app = SimpleNamespace(
        services=SimpleNamespace(
            login=_FakeLogin(),
            engage=_FakeEngage(result),
        ),
        openai_client=None,
        post_extractor=None,
    )
    fake = FakeBot(app)
    monkeypatch.setattr(main, "build_app", lambda **kwargs: app)
    monkeypatch.setattr(main, "LinkedInBot", lambda built: fake)
    monkeypatch.setattr(main, "configure_logging", lambda debug: None)
    monkeypatch.setattr("sys.argv", ["main.py", "engage"])

    assert main.main() == expected

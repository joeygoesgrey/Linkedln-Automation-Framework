"""Prove the schedule flow clicks confirm and never falls through to Post."""

from types import SimpleNamespace
from typing import Any, Callable

import pytest

from laf.errors import ComposerError, PostError, ScheduleError
from laf.selectors.composer import ComposerSelectors
from laf.services.composer import ComposerService
from tests.fakes import FakeDriver, FakeElement


class _InstantWait:
    """Replace WebDriverWait so a test never sleeps on a missing selector."""

    def __init__(self, driver: Any, timeout: float) -> None:
        """Store the driver and ignore the timeout.

        Args
          driver: Any, the fake driver the condition polls.
          timeout: float, the real wait length, unused here.
        """
        self.driver = driver

    def until(self, condition: Callable[[Any], Any]) -> Any:
        """Run the wait condition once and return or raise its result.

        WHY
          The real wait retries for seconds, and a test only needs to know
          whether the element resolves on the first poll.

        Args
          condition: Callable[[Any], Any], the expected-condition callable.

        Returns
          Any, whatever the condition resolves to.
        """
        return condition(self.driver)


def _service(
    driver: FakeDriver,
    click: Callable[[Any, str], bool],
    mentions: Any = None,
) -> ComposerService:
    """Build a ComposerService with fake partners for one test.

    WHY
      The composer only needs a driver, a click helper and a few no-op
      partners, and building real services would touch a browser.

    Args
      driver: FakeDriver, the driver the service reads.
      click: Callable[[Any, str], bool], the click_with_fallback stand-in.
      mentions: Any, the mention helper, or None for a no-op default.

    Returns
      ComposerService, ready to call.
    """
    ui = SimpleNamespace(driver=driver, pause=lambda *args: None, click_with_fallback=click)
    config = SimpleNamespace(
        linkedin_feed_url="https://www.linkedin.com/feed/",
        min_page_load_delay=0,
        max_page_load_delay=0,
    )
    overlays = SimpleNamespace(dismiss_overlays=lambda **kwargs: None)
    media = SimpleNamespace(upload_images_to_post=lambda paths: True)
    if mentions is None:
        mentions = SimpleNamespace(
            post_text_contains_inline_mentions=lambda text: False,
            insert_mentions=lambda area, names: None,
        )
    verify = SimpleNamespace(verify_post_success=lambda text: True)
    return ComposerService(
        ui=ui,  # type: ignore[arg-type]
        config=config,  # type: ignore[arg-type]
        overlays=overlays,  # type: ignore[arg-type]
        media=media,  # type: ignore[arg-type]
        mentions=mentions,
        verify=verify,  # type: ignore[arg-type]
    )


def _schedule_driver(with_confirm: bool) -> FakeDriver:
    """Build a fake driver holding every element the schedule modal needs.

    WHY
      The schedule flow looks up its controls by selector, so the fake needs
      one element per selector it tries first.

    Args
      with_confirm: bool, True to add a confirm button, False to leave it out.

    Returns
      FakeDriver, configured for the composer schedule path.
    """
    elements: dict[str, FakeElement] = {
        ComposerSelectors.SCHEDULE_BUTTONS[0]: FakeElement(displayed=True),
        ComposerSelectors.SCHEDULE_DATE_INPUTS[0]: FakeElement(),
        ComposerSelectors.SCHEDULE_TIME_INPUTS[0]: FakeElement(),
    }
    if with_confirm:
        elements[ComposerSelectors.SCHEDULE_CONFIRM_BUTTONS[0]] = FakeElement(text="Confirm")
    return FakeDriver(elements=elements)


def _click(element: Any, name: str) -> bool:
    """Click a fake element the way click_with_fallback would.

    WHY
      FakeElement is not a real WebElement, so the real helper refuses it; this
      stand-in still records the click for the assertion.

    Args
      element: Any, the fake element to click.
      name: str, the friendly name the real helper would log.

    Returns
      bool, always True after a click.
    """
    element.click()
    return True


def test_schedule_post_clicks_the_confirm_button(monkeypatch: pytest.MonkeyPatch) -> None:
    """A valid date and time end with the confirm click, not the Post path.

    WHY
      The bug was that _schedule_post returned True without confirming, so the
      caller went looking for a Post button that is not on screen.

    Args
      monkeypatch: pytest.MonkeyPatch, used to remove the real wait delays.
    """
    import laf.services.composer as composer_module

    monkeypatch.setattr(composer_module, "WebDriverWait", _InstantWait)
    driver = _schedule_driver(with_confirm=True)
    service = _service(driver, _click)

    result = service._schedule_post("2026-11-01", "09:00")

    confirm = driver.elements[ComposerSelectors.SCHEDULE_CONFIRM_BUTTONS[0]]
    assert result is None
    assert confirm.clicks == 1


def test_schedule_post_names_the_missing_confirm_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing confirm button raises SCHEDULE_CONTROL_MISSING for that control.

    WHY
      Falling through to the Post path after a failed confirm would submit the
      wrong action, so the schedule flow must stop with a named failure.

    Args
      monkeypatch: pytest.MonkeyPatch, used to remove the real wait delays.
    """
    import laf.services.composer as composer_module

    monkeypatch.setattr(composer_module, "WebDriverWait", _InstantWait)
    driver = _schedule_driver(with_confirm=False)
    service = _service(driver, _click)

    with pytest.raises(ScheduleError) as caught:
        service._schedule_post("2026-11-01", "09:00")

    assert caught.value.code == "SCHEDULE_CONTROL_MISSING"
    assert caught.value.fields == {"control": "confirm button"}


def test_schedule_post_rejects_a_missing_date_or_time() -> None:
    """An empty date or time is a caller bug and raises ValueError.

    WHY
      The schedule branch in post_to_linkedin only runs when both values are
      set, so reaching this guard means the caller skipped that check.
    """
    service = _service(FakeDriver(), _click)

    with pytest.raises(ValueError):
        service._schedule_post("", "09:00")


def test_post_to_linkedin_returns_after_a_schedule_without_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A scheduled post finishes and never searches for the Post button.

    WHY
      The confirm click inside the schedule flow already submits the post, so
      the old Post button path must be skipped or it submits twice.

    Args
      monkeypatch: pytest.MonkeyPatch, used to stub the composer steps that
        need a real page.
    """
    service = _service(FakeDriver(), lambda element, name: True)
    scheduled: list[tuple[str, str]] = []

    monkeypatch.setattr(service, "_find_start_post_button", lambda: object())
    monkeypatch.setattr(service, "_find_post_editor", lambda: object())
    monkeypatch.setattr(service, "_set_post_text", lambda area, text: True)
    monkeypatch.setattr(
        service,
        "_schedule_post",
        lambda date_str, time_str: scheduled.append((date_str, time_str)),
    )

    def _fail_post_lookup() -> Any:
        """Fail the test if the Post button path is reached.

        WHY
          Reaching this lookup is the bug being fixed, so it must never run.

        Raises
          AssertionError: always, because the call means the schedule branch
          did not stop early.
        """
        raise AssertionError("Post button lookup must not run after a schedule")

    monkeypatch.setattr(service, "_find_post_button", _fail_post_lookup)

    result = service.post_to_linkedin(
        "hello", schedule_date="2026-11-01", schedule_time="09:00"
    )

    assert result is None
    assert scheduled == [("2026-11-01", "09:00")]


def test_post_to_linkedin_names_a_missing_start_button(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing start control raises COMPOSER_NOT_OPEN.

    WHY
      Without the start control the composer never opens, so the caller must
      get a named failure and no later step may run.

    Args
      monkeypatch: pytest.MonkeyPatch, used to remove the start button lookup.
    """
    service = _service(FakeDriver(), lambda element, name: True)

    monkeypatch.setattr(service, "_find_start_post_button", lambda: None)

    with pytest.raises(ComposerError) as caught:
        service.post_to_linkedin("hello")

    assert caught.value.code == "COMPOSER_NOT_OPEN"


def test_post_to_linkedin_names_a_missing_editor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing editor raises COMPOSER_EDITOR_MISSING.

    WHY
      Typing without an editor would send keys to the wrong page, so the flow
      must stop with the exact control that was missing.

    Args
      monkeypatch: pytest.MonkeyPatch, used to stub the start button lookup.
    """
    service = _service(FakeDriver(), lambda element, name: True)

    monkeypatch.setattr(service, "_find_start_post_button", lambda: object())
    monkeypatch.setattr(service, "_find_post_editor", lambda: None)

    with pytest.raises(ComposerError) as caught:
        service.post_to_linkedin("hello")

    assert caught.value.code == "COMPOSER_EDITOR_MISSING"


def test_post_to_linkedin_names_a_failed_text_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rejected text write raises POST_TEXT_FAILED.

    WHY
      Posting an empty composer would publish nothing or the wrong text, so a
      write that both paths reject must stop the flow.

    Args
      monkeypatch: pytest.MonkeyPatch, used to stub the editor and the write.
    """
    service = _service(FakeDriver(), lambda element, name: True)

    monkeypatch.setattr(service, "_find_start_post_button", lambda: object())
    monkeypatch.setattr(service, "_find_post_editor", lambda: object())
    monkeypatch.setattr(service, "_set_post_text", lambda area, text: False)

    with pytest.raises(PostError) as caught:
        service.post_to_linkedin("hello")

    assert caught.value.code == "POST_TEXT_FAILED"


def test_post_to_linkedin_rejects_empty_text() -> None:
    """Empty text raises ValueError before any browser call.

    WHY
      The caller contract requires text, and an empty composer would submit an
      empty post if the flow carried on.
    """
    service = _service(FakeDriver(), lambda element, name: True)

    with pytest.raises(ValueError):
        service.post_to_linkedin("")

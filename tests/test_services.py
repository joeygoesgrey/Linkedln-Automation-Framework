"""Prove build_app wires every service with a fake driver and keeps like state."""

from selenium.common.exceptions import WebDriverException

from laf.ai.client import _parse_tone_reply
from laf.app import build_app
from laf.config import CONFIG
from laf.selectors.engage import EngageSelectors
from laf.services.engage_types import EngageContext
from laf.services.engage_utils import choose_ai_perspective, normalize_perspectives
from laf.services.profile_actions import ProfileService
from tests.fakes import FakeDriver, FakeElement


def test_insightful_alias_maps_to_thoughtful() -> None:
    """The old name still selects the new thoughtful tone.

    WHY
        Users and scripts may still pass insightful, and the change must not
        drop the choice.
    """
    assert normalize_perspectives(["insightful"]) == ["thoughtful"]


def test_empty_or_unknown_perspectives_become_auto() -> None:
    """No value, or only unknown values, falls back to auto.

    WHY
        An empty or broken flag must run in auto mode instead of crashing.
    """
    assert normalize_perspectives(None) == ["auto"]
    assert normalize_perspectives([]) == ["auto"]
    assert normalize_perspectives(["funny", "nonsense"]) == ["auto"]


def test_auto_survives_choose_ai_perspective() -> None:
    """Auto wins when it appears beside a real tone.

    WHY
        A mixed list must not silently pick the explicit tone and ignore
        auto.
    """
    assert choose_ai_perspective(["motivational", "auto"]) == "auto"
    assert choose_ai_perspective(["auto"]) == "auto"


def test_explicit_tone_is_returned_unchanged() -> None:
    """A single explicit tone is the tone used.

    WHY
        Forcing a tone must not be replaced by a random one.
    """
    assert choose_ai_perspective(["reality_check"]) == "reality_check"


def test_tone_line_is_removed_and_reported() -> None:
    """A valid TONE line gives the body and the named tone.

    WHY
        Auto mode uses this line to log the real tone, so it must not leak into
        the comment text.
    """
    assert _parse_tone_reply("TONE: thoughtful\nNice point.") == (
        "Nice point.",
        "thoughtful",
    )


def test_tone_line_parses_extra_spaces_and_case() -> None:
    """Different case and spacing still parse.

    WHY
        The model does not always match a strict shape, and that must not force
        a fallback.
    """
    assert _parse_tone_reply(" tone : REALITY_CHECK  \nFair take.") == (
        "Fair take.",
        "reality_check",
    )


def test_missing_or_unknown_tone_line_keeps_full_reply() -> None:
    """No line, or a removed tone, keeps the reply and reports auto.

    WHY
        A bad choice line must not delete words the author wrote or crash the
        run.
    """
    assert _parse_tone_reply("Nice point.") == ("Nice point.", "auto")
    assert _parse_tone_reply("TONE: funny\nNice point.") == (
        "TONE: funny\nNice point.",
        "auto",
    )


def _context() -> EngageContext:
    """Build the smallest valid engage context for a like test.

    WHY
        The like helpers only touch the liked set and a few fields, so the
        other values can be fixed defaults.

    Returns
        EngageContext: a context with empty state.
    """
    return EngageContext(
        mode="like",
        comment_text=None,
        max_actions=5,
        include_promoted=False,
        delay_min=0.05,
        delay_max=0.1,
        mention_author=False,
        mention_position="append",
        infinite=False,
        scroll_wait_min=0.05,
        scroll_wait_max=0.1,
    )


def test_build_app_builds_every_service_with_a_fake_driver() -> None:
    """The wiring works with a test driver and no browser process."""
    driver = FakeDriver()
    app = build_app(config=CONFIG, use_openai=False, driver=driver)

    assert app.driver is driver
    assert app.services.ui.driver is driver
    for name in (
        "ui",
        "overlays",
        "verify",
        "mentions",
        "engage_dom",
        "media",
        "login",
        "composer",
        "feed",
        "profile",
        "engage",
    ):
        assert getattr(app.services, name) is not None


def test_build_app_skips_openai_and_returns_the_same_fake_driver() -> None:
    """No AI client is built, and the fake driver comes back out unchanged."""
    driver = FakeDriver()
    app = build_app(config=CONFIG, use_openai=False, driver=driver)

    assert app.openai_client is None
    assert app.driver is driver


def test_liked_state_is_tracked_by_urn_and_key() -> None:
    """A marked post reads back as liked through either identifier."""
    app = build_app(config=CONFIG, use_openai=False, driver=FakeDriver())
    context = _context()

    assert not app.services.engage.is_liked(context, "urn:1", "key-1")

    app.services.engage.mark_post_liked(context, "urn:1", "key-1")

    assert app.services.engage.is_liked(context, "urn:1", None)
    assert app.services.engage.is_liked(context, None, "key-1")
    assert not app.services.engage.is_liked(context, "urn:2", "key-2")


def test_marking_without_identifiers_changes_nothing() -> None:
    """A post with no urn and no key is not added to the liked set."""
    app = build_app(config=CONFIG, use_openai=False, driver=FakeDriver())
    context = _context()

    app.services.engage.mark_post_liked(context, None, None)

    assert context.liked == set()


class _StubUi:
    """Stand in for UiActions that carries only a fake driver.

    WHY
      The profile loop reads the driver only for the scroll fallback, so a fake
      driver is enough and no browser opens.
    """

    def __init__(self) -> None:
        """
        WHY
          Give the service a driver attribute without building the real UI.

        MUTATIONS
          Stores a FakeDriver on the instance.
        """
        self.driver = FakeDriver()


class _StubEngageDom:
    """Stand in for EngageDomService that answers the profile loop calls.

    WHY
      The loop needs only a few post reader answers, so a stub keeps the test
      fast and free of Selenium.
    """

    def __init__(
        self,
        *,
        like_result: bool = True,
        like_error: bool = False,
        visible_passes: int = 1,
    ) -> None:
        """
        WHY
          Let each test choose whether the like works, fails or is offered and
          how many passes return the one post.

        Args
          like_result: bool, the value like_from_bar returns.
          like_error: bool, True to make like_from_bar raise.
          visible_passes: int, how many passes return the one post.

        MUTATIONS
          Sets the stub fields and builds one post element with an action bar.
        """
        self.like_result = like_result
        self.like_error = like_error
        self.visible_passes = visible_passes
        self.find_calls = 0
        self.saved: list[dict[str, list[str]]] = []
        self.post = FakeElement(
            children={EngageSelectors.ACTION_BAR: FakeElement()}
        )

    def load_engage_state(self) -> dict[str, list[str]]:
        """
        WHY
          The loop needs a clean saved state so it does not skip the test post.

        Returns
          dict[str, list[str]]: empty liked, commented and reposted lists.
        """
        return {"liked": [], "commented": [], "reposted": []}

    def find_visible_posts(self, limit: int = 8) -> list[FakeElement]:
        """
        WHY
          Let the loop see the one post for the chosen passes, then run dry so
          the stall counter can end the run.

        Args
          limit: int, unused by the stub.

        Returns
          list[FakeElement]: the one post, or an empty list after the passes.
        """
        self.find_calls += 1
        if self.find_calls <= self.visible_passes:
            return [self.post]
        return []

    def extract_post_urn(self, post: FakeElement) -> str:
        """
        WHY
          Give the post a stable identifier for the dedupe key.

        Args
          post: FakeElement, unused by the stub.

        Returns
          str: a fixed urn.
        """
        return "urn:1"

    def post_dedupe_key(self, post: FakeElement, urn: str | None) -> str:
        """
        WHY
          Give the post a stable dedupe key across passes.

        Args
          post: FakeElement, unused by the stub.
          urn: str | None, unused by the stub.

        Returns
          str: a fixed key.
        """
        return "key-1"

    def is_promoted_post(self, post: FakeElement) -> bool:
        """
        WHY
          Keep the test post as an ordinary post that the loop may engage.

        Args
          post: FakeElement, unused by the stub.

        Returns
          bool: always False.
        """
        return False

    def like_from_bar(self, action_bar: FakeElement) -> bool:
        """
        WHY
          Let a test pick a like that works or one that raises the browser
          error the loop must survive.

        Args
          action_bar: FakeElement, unused by the stub.

        Returns
          bool: the configured like result.

        Raises
          WebDriverException: when the test asks for a failing like.
        """
        if self.like_error:
            raise WebDriverException("like failed")
        return self.like_result

    def comment_from_bar(self, *args: object, **kwargs: object) -> bool:
        """
        WHY
          Keep the comment step quiet so a test can focus on the like.

        Args
          args: object, unused by the stub.
          kwargs: object, unused by the stub.

        Returns
          bool: always False.
        """
        return False

    def save_engage_state(self, state: dict[str, list[str]]) -> None:
        """
        WHY
          Record each saved state so a test can prove the save happened.

        Args
          state: dict[str, list[str]], the state written by the loop.

        MUTATIONS
          Appends the state to the saved list.
        """
        self.saved.append(state)

    def scroll_feed(self, *args: object, **kwargs: object) -> None:
        """
        WHY
          Let the stall path scroll without a browser.

        Args
          args: object, unused by the stub.
          kwargs: object, unused by the stub.
        """
        return None


def _profile_service(engage_dom: _StubEngageDom) -> ProfileService:
    """Build a ProfileService around the stub post reader.

    WHY
      Every profile test needs the same wiring, so one helper keeps the tests
      short.

    Args
      engage_dom: _StubEngageDom, the post reader the service will call.

    Returns
      ProfileService: the service under test with a fake driver.
    """
    return ProfileService(_StubUi(), CONFIG, engage_dom)  # type: ignore[arg-type]


def test_engage_profile_posts_zero_limit_touches_no_post(
    monkeypatch,
) -> None:
    """A zero limit returns the zeroed results and never looks for a post.

    WHY
        The caller may ask for nothing, and the run must answer the documented
        zeroed dict without any page work.
    """
    monkeypatch.setattr("laf.services.profile_actions.time.sleep", lambda _s: None)
    engage_dom = _StubEngageDom()
    service = _profile_service(engage_dom)

    results = service.engage_profile_posts(max_posts=0)

    assert results == {
        "posts_engaged": 0,
        "likes": 0,
        "comments": 0,
        "reposts": 0,
        "skipped": 0,
        "errors": [],
    }
    assert engage_dom.find_calls == 0


def test_engage_profile_posts_one_liked_post_counts_once(monkeypatch) -> None:
    """One post with a working like counts as engaged and liked.

    WHY
        The split loop must still count a successful like exactly once and save
        the state after acting.
    """
    monkeypatch.setattr("laf.services.profile_actions.time.sleep", lambda _s: None)
    engage_dom = _StubEngageDom(like_result=True)
    service = _profile_service(engage_dom)

    results = service.engage_profile_posts(max_posts=1, should_comment=False)

    assert results["posts_engaged"] == 1
    assert results["likes"] == 1
    assert results["skipped"] == 0
    assert results["errors"] == []
    assert engage_dom.saved == [
        {"liked": ["key-1"], "commented": [], "reposted": []}
    ]


def test_engage_profile_posts_like_error_is_one_sentence_and_loop_survives(
    monkeypatch,
) -> None:
    """A failing like appends one sentence and the loop returns instead of raising.

    WHY
        One browser error on one post must not end the run, so the loop reports
        it and keeps going until the stall limit.
    """
    monkeypatch.setattr("laf.services.profile_actions.time.sleep", lambda _s: None)
    engage_dom = _StubEngageDom(like_error=True, visible_passes=1)
    service = _profile_service(engage_dom)

    results = service.engage_profile_posts(max_posts=1, should_comment=False)

    assert results["posts_engaged"] == 0
    assert results["skipped"] == 1
    assert len(results["errors"]) == 1
    assert results["errors"][0].startswith("Like failed:")


def test_engage_profile_posts_returns_exactly_the_documented_keys() -> None:
    """The result dict holds the six documented keys and nothing else.

    WHY
        Callers read these keys by name, so the split must not rename or drop
        any of them.
    """
    service = _profile_service(_StubEngageDom())

    results = service.engage_profile_posts(max_posts=0)

    assert set(results) == {
        "posts_engaged",
        "likes",
        "comments",
        "reposts",
        "skipped",
        "errors",
    }

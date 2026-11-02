"""Tests for the pursue flow, run entirely with fakes and no browser."""

from typing import Any, Optional

import pytest
from pydantic import ValidationError
from selenium.common.exceptions import WebDriverException

from laf.errors import ProfileError
from laf.flows.pursue import (
    FALLBACK_COMMENT,
    LOGIN_FAILED_MESSAGE,
    PursueFlow,
)
from tests.fakes import FakeDriver


class FakeLogin:
    """Stand in for LoginService and record each login call."""

    def __init__(self, result: bool = True) -> None:
        """Store the answer the fake login should give."""
        self.result = result
        self.calls = 0

    def login(self) -> bool:
        """Return the configured answer and count the call."""
        self.calls += 1
        return self.result


class FakeProfile:
    """Stand in for ProfileService and record each search and follow."""

    def __init__(
        self,
        url: Optional[str] = "https://www.linkedin.com/in/ada/",
        follow_result: bool = True,
        follow_error: Optional[Exception] = None,
        engagement: Optional[dict[str, Any]] = None,
    ) -> None:
        """Store the URL, follow behaviour and engagement counts."""
        self.url = url
        self.follow_result = follow_result
        self.follow_error = follow_error
        self.engagement = engagement or {
            "posts_engaged": 2,
            "likes": 1,
            "comments": 1,
            "skipped": 0,
        }
        self.searched: list[tuple[str, Optional[list[str]]]] = []
        self.follow_calls = 0
        self.posts_view_calls = 0
        self.engage_calls = 0
        self.engage_kwargs: dict[str, Any] = {}

    def search_profile(
        self, name: str, bio_keywords: Optional[list[str]] = None
    ) -> Optional[str]:
        """Record the search and return the configured URL."""
        self.searched.append((name, bio_keywords))
        return self.url

    def follow_profile(self) -> bool:
        """Return the configured follow answer or raise the configured error."""
        self.follow_calls += 1
        if self.follow_error is not None:
            raise self.follow_error
        return self.follow_result

    def open_profile_posts_view(self) -> bool:
        """Report that the posts view opened."""
        self.posts_view_calls += 1
        return True

    def engage_profile_posts(self, **kwargs: Any) -> dict[str, Any]:
        """Record the engage options and return the configured counts."""
        self.engage_calls += 1
        self.engage_kwargs = kwargs
        return self.engagement


class FakeExtractor:
    """Stand in for PostExtractor with an optional failure."""

    def __init__(self, text: str = "A useful post", error: Optional[Exception] = None) -> None:
        """Store the text to return and the error to raise, if any."""
        self.text = text
        self.error = error

    def extract_text(self, root: object) -> str:
        """Return the configured text, or raise the configured error."""
        if self.error is not None:
            raise self.error
        return self.text


class FakeClient:
    """Stand in for OpenAIClient and count comment calls."""

    def __init__(self, comment: str = "AI comment", error: Optional[Exception] = None) -> None:
        """Store the comment to return and the error to raise, if any."""
        self.comment = comment
        self.error = error
        self.calls = 0

    def generate_comment(self, **kwargs: Any) -> tuple[str, str]:
        """Return the configured comment and tone, or raise the configured error."""
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.comment, "thoughtful"


class FakeServices:
    """Bundle the two services the flow calls."""

    def __init__(self, login: FakeLogin, profile: FakeProfile) -> None:
        """Store the login and profile fakes."""
        self.login = login
        self.profile = profile


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the real three second pause from every flow run."""
    monkeypatch.setattr("laf.flows.pursue.time.sleep", lambda *_: None)


def _flow(
    profile: Optional[FakeProfile] = None,
    login: Optional[FakeLogin] = None,
    openai_client: Optional[FakeClient] = None,
    extractor: Optional[FakeExtractor] = None,
) -> PursueFlow:
    """Build a flow with fakes and no real browser or AI client."""
    return PursueFlow(
        services=FakeServices(login or FakeLogin(), profile or FakeProfile()),
        driver=FakeDriver(),
        openai_client=openai_client,
        post_extractor=extractor or FakeExtractor(),
    )


def test_results_keys_match_the_old_set() -> None:
    """A normal run returns exactly the keys the old bot returned."""
    results = _flow().run("Ada")

    assert set(results) == {
        "profile",
        "followed",
        "posts_engaged",
        "likes_given",
        "comments_made",
        "errors",
    }
    assert results["profile"] == "Ada"
    assert results["posts_engaged"] == 2
    assert results["likes_given"] == 1
    assert results["comments_made"] == 1


def test_results_start_with_the_old_defaults_when_login_fails() -> None:
    """A failed login returns the starting values plus one error sentence."""
    results = _flow(login=FakeLogin(result=False)).run("Ada")

    assert results == {
        "profile": "Ada",
        "followed": False,
        "posts_engaged": 0,
        "likes_given": 0,
        "comments_made": 0,
        "errors": [LOGIN_FAILED_MESSAGE],
    }


def test_login_failure_does_not_search_or_engage() -> None:
    """No search, follow or engagement runs after a failed login."""
    profile = FakeProfile()
    results = _flow(profile=profile, login=FakeLogin(result=False)).run("Ada")

    assert profile.searched == []
    assert profile.follow_calls == 0
    assert profile.engage_calls == 0
    assert results["errors"] == [LOGIN_FAILED_MESSAGE]


def test_missing_profile_raises_profile_error_with_the_code() -> None:
    """A search that returns no URL raises ProfileError, not a swallowed error."""
    profile = FakeProfile(url=None)

    with pytest.raises(ProfileError) as info:
        _flow(profile=profile).run("Ada")

    assert info.value.code == "PROFILE_NOT_FOUND"
    assert info.value.fields["name"] == "Ada"


def test_follow_failure_is_recorded_and_the_run_continues() -> None:
    """A raised follow error lands in errors and engagement still runs."""
    profile = FakeProfile(follow_error=WebDriverException("button missing"))

    results = _flow(profile=profile).run("Ada")

    assert results["followed"] is False
    assert results["errors"] == [
        f"Failed to follow profile: {WebDriverException('button missing')}"
    ]
    assert profile.engage_calls == 1
    assert results["posts_engaged"] == 2


def test_follow_disabled_calls_nothing_and_stays_false() -> None:
    """Turning follow off leaves followed False and never calls the service."""
    profile = FakeProfile()

    results = _flow(profile=profile).run("Ada", should_follow=False)

    assert profile.follow_calls == 0
    assert results["followed"] is False


def test_empty_bio_keywords_search_without_the_filter() -> None:
    """No bio keywords are passed as None and an empty list stays empty."""
    profile = FakeProfile()
    flow = _flow(profile=profile)

    flow.run("Ada")
    flow.run("Ada", bio_keywords=[])

    assert profile.searched == [("Ada", None), ("Ada", [])]


def test_fallback_generator_returns_fixed_sentence_without_ai_client() -> None:
    """With no AI client the generator still returns the fixed sentence."""
    flow = _flow(openai_client=None)
    generator = flow._build_comment_generator(
        flow._validate("Ada", 5, True, True, True, None, None)
    )

    assert generator(object()) == FALLBACK_COMMENT


def test_fallback_generator_returns_fixed_sentence_when_extraction_fails() -> None:
    """An extractor error is caught and the fixed sentence comes back."""
    flow = _flow(
        openai_client=FakeClient(),
        extractor=FakeExtractor(error=WebDriverException("no text")),
    )
    generator = flow._build_comment_generator(
        flow._validate("Ada", 5, True, True, True, None, None)
    )

    assert generator(object()) == FALLBACK_COMMENT


def test_run_passes_a_fallback_generator_when_ai_is_missing() -> None:
    """A normal run without AI still hands a working generator to engagement."""
    profile = FakeProfile()

    _flow(profile=profile, openai_client=None).run("Ada")

    generator = profile.engage_kwargs["comment_generator"]
    assert callable(generator)
    assert generator(object()) == FALLBACK_COMMENT


def test_invalid_profile_name_raises_validation_error() -> None:
    """An empty name is rejected before any service call."""
    profile = FakeProfile()

    with pytest.raises(ValidationError):
        _flow(profile=profile).run("")

    assert profile.searched == []

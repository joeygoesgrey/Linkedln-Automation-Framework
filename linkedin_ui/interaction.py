"""
Composite LinkedIn interaction class assembling mixins.

Why:
    Provide a single public class with cohesive features while keeping the
    implementation modular.

When:
    Import `LinkedInInteraction` from `linkedin_ui` and use it as before.

How:
    Multiple mixins contribute methods; `BaseInteraction` supplies utilities.
"""

from .base import BaseInteraction
from .login import LoginMixin
from .overlays import OverlayMixin
from .mentions import MentionsMixin
from .media import MediaMixin
from .verify import VerifyMixin
from .composer import ComposerMixin
from .feed_actions import FeedActionsMixin
from .engage import EngageStreamMixin
from .profile_actions import ProfileActionsMixin

class LinkedInInteraction(
    LoginMixin,
    OverlayMixin,
    MentionsMixin,
    MediaMixin,
    VerifyMixin,
    ComposerMixin,
    FeedActionsMixin,
    EngageStreamMixin,
    BaseInteraction,
    ProfileActionsMixin,
):
    """High-level LinkedIn UI automation wrapper composing specialised mixins.

    Why:
        Present a unified interface for login, posting, mentions, media, feed
        actions, and engagement.

    When:
        Instantiated by :class:`LinkedInBot` during automation runs.

    How:
        Inherits behaviour from mixins and the base interaction utility class.
    """

    pass

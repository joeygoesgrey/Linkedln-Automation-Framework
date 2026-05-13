"""
LinkedIn UI package.

Why:
    Groups LinkedIn Selenium interaction logic into focused modules (login,
    overlays, composer, mentions, media, verification) to keep the codebase
    maintainable as LinkedIn’s UI evolves.

When:
    Import `LinkedInInteraction` to automate login, posting, mentions, and
    media uploads.

How:
    The `LinkedInInteraction` class composes multiple mixins that each
    encapsulate a coherent area. See module docstrings for details.
"""

from .interaction import LinkedInInteraction

__all__ = ["LinkedInInteraction"]


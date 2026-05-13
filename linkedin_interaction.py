"""
Compatibility shim for LinkedInInteraction.

Why:
    The monolithic interaction module was split into a modular package under
    `linkedin_ui/`. This shim preserves the public import path used elsewhere
    in the repo: `from linkedin_interaction import LinkedInInteraction`.

When:
    Continue importing `LinkedInInteraction` from this module; the class is
    re-exported from the new package.

How:
    Thin re-export to the composite class assembled from mixins.
"""

from linkedin_ui import LinkedInInteraction  # noqa: F401


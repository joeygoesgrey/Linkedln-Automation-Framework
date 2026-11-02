"""Selectors for checking that a post went out.

WHY
  Serve the post result check, so the toast and share box selectors can change
  apart from the composer itself.
"""


class VerifySelectors:
    """Selectors for checking that a post went out.

    WHY
      Serve the toasts and share box state after a post, so a change to that
      feedback has one file to update.
    """

    SUCCESS_INDICATORS = [
        (
            "//div[contains(@class, 'artdeco-toast') and "
            "(contains(translate(., 'POSTEDSHARED', 'postedshared'), 'posted') or "
            "contains(translate(., 'POSTEDSHARED', 'postedshared'), 'shared'))]"
        ),
        "//div[contains(@class, 'artdeco-toast-item')]",
        "//div[contains(@class, 'toast') and contains(@role, 'alert')]",
        "//div[contains(@class, 'feed-shared-update-v2')]",
    ]  # linkedin_ui/verify.py:57

    POST_MODAL = (
        "//div[@role='dialog' and contains(@class, 'share-box-modal')]"  # linkedin_ui/verify.py:74
    )
    POST_MODAL_ERROR = (
        ".//*[contains(@class, 'error') or contains(@class, 'alert')]"  # linkedin_ui/verify.py:79
    )
    CLOSED_SHARE_BOX = (
        "//div[contains(@class, "
        "'share-box-feed-entry__closed-share-box')]"
    )  # linkedin_ui/verify.py:91
    FEED_SNIPPET_TEMPLATE = (
        "//div[contains(@class,'feed') or contains(@class,'scaffold')]//*"
        "[contains(normalize-space(.), \"{snippet}\")]"
    )  # linkedin_ui/verify.py:98

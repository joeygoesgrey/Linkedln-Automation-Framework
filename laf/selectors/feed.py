"""Selectors for reading feed posts and acting on them.

WHY
  Serve the feed page's two jobs, reading post text and running like, comment and
  repost actions, so both are updated in the one file for that page.
"""

from laf.selectors.composer import ComposerSelectors
from laf.selectors.engage import EngageSelectors


class PostExtractorSelectors:
    """Selectors for extracting text and metadata from feed posts.

    WHY
      Serve reading a post's text and details on the feed, so a markup change to
      post content has one file to update.
    """

    SEE_MORE_BUTTONS = [
        (
            ".//button[contains(@class,'see-more') and "
            "contains(@class,'inline-show-more-text__button')]"
        ),
        ".//span[contains(@class,'line-clamp-show-more-button')]",
        ".//button[normalize-space()='...see more']",
        ".//button[normalize-space()='Show more']",
    ]  # linkedin_ui/post_extractor.py:98

    CONTENT_NODES = (
        ".//div[contains(@class,'update-components-text')]//*[normalize-space()]",
        ".//div[contains(@class,'feed-shared-inline-show-more-text')]//*[normalize-space()]",
        ".//div[contains(@class,'feed-shared-article__description')]//*[normalize-space()]",
        ".//span[contains(@class,'break-words') and normalize-space()]",
    )  # linkedin_ui/post_extractor.py:140


class FeedActionSelectors:
    """Selectors for feed actions (like, comment, repost).

    WHY
      Serve the like, comment and repost actions on the feed, so a markup change
      to the action bar has one file to update.
    """

    FIRST_ACTION_BAR = [
        "//button[@aria-label='Comment']/ancestor::div"
        "[.//*[starts-with(@aria-label,'Reaction button state')]][1]",
        "(//div[contains(@class,'feed-shared-social-action-bar')])[1]",
        "(//div[contains(@class,'update-v2-social-activity')]//div[contains(@class,'social-action')])[1]",
    ]  # linkedin_ui/feed_actions.py:80; ancestor fallback for the 2026 feed build

    LIKE_BUTTONS = EngageSelectors.LIKE_BUTTONS

    COMMENT_BUTTONS = EngageSelectors.COMMENT_BUTTONS

    COMMENT_EDITOR = [
        (
            "(//div[@contenteditable='true' and (contains(@class,'comments') or "
            "contains(@class,'ql-editor') or contains(@role,'textbox'))])[1]"
        ),
        "(//div[contains(@class,'comments') and @contenteditable='true'])[1]",
    ]  # linkedin_ui/feed_actions.py:204

    SUBMIT_COMMENT = EngageSelectors.SUBMIT_COMMENT

    REPOST_BUTTONS = [
        ".//button[@aria-label='Repost']",
        ".//button[.//svg[@id='repost-feed-compact']]",
        ".//button[contains(@class,'social-reshare-button')]",
        ".//button[.//span[normalize-space()='Repost']]",
        ".//button[@data-finite-scroll-hotkey='r']",
    ]  # linkedin_ui/feed_actions.py:326; aria label and svg id first

    REPOST_DROPDOWN_CONTAINERS_SCOPED = [
        ".//*[@popover='manual']",
    ]  # the 2026 menu opens as a popover, portaled outside the bar

    REPOST_DROPDOWN_CONTAINERS_GLOBAL = (
        "//*[@popover='manual']"  # the 2026 menu opens as a popover
    )

    REPOST_OPTION_TAGS = [
        ".//*[@role='button']",
        ".//button",
        ".//*[@role='menuitem']",
        ".//li",
        ".//div",
        ".//span",
    ]

    REPOST_OPTION_ROW = (
        "./ancestor-or-self::*[@role='button' or self::button][1]"
    )  # the 2026 row is a div role button that wraps the label

    REPOST_CANDIDATE_TEXTS = [
        "repost with thoughts",
        "repost with your thoughts",
        "share with your thoughts",
        "reshare with your thoughts",
    ]

    REPOST_GLOBAL_OPTION_XPATH_TEMPLATE = (
        "//*[contains(translate(normalize-space(.),"
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), '{cand}')]"
    )

    REPOST_EDITOR = [
        ComposerSelectors.POST_EDITOR[0],
        ComposerSelectors.POST_EDITOR[1],
        "//div[contains(@class,'editor-container')]//div[@contenteditable='true']",
        "//div[contains(@class,'ql-editor') and @contenteditable='true']",
        "//div[@contenteditable='true' and contains(@aria-label,'Text editor')]",
    ]  # linkedin_ui/feed_actions.py:457; the repost modal reuses the post editor

    SUBMIT_REPOST = [
        "//*[@role='dialog']//button[.//span[normalize-space()='Repost']]",
        "//*[@role='dialog']//button[normalize-space(.)='Repost']",
        "//button[.//span[normalize-space()='Repost']]",
    ]  # linkedin_ui/feed_actions.py:538; the repost modal has no Post button

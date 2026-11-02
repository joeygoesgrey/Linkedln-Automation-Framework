"""Selectors for DOM traversal and interaction during the engage stream.

WHY
  Serve the engage stream, so the post, author and action bar locators can change
  without touching the rest of the feed code.
"""


class EngageSelectors:
    """Selectors for DOM traversal and interaction during the engage stream.

    WHY
      Serve the post, author and action bar lookups in the engage stream, so a
      feed markup change has one file to update.
    """

    AUTHOR_NAME = [
        ".//a[contains(@href,'/in/')][.//p]//p//span[@aria-hidden='true'][normalize-space()]",
        (
            ".//span[contains(@class,'update-components-actor__title')]//span"
            "[normalize-space() and not(contains(@class,'visually-hidden'))]"
        ),
        ".//div[contains(@class,'update-components-actor__container')]//a[contains(@href,'/in/')][normalize-space()]",
        (
            ".//a[contains(@class,'update-components-actor__meta-link')]//*"
            "[normalize-space() and not(contains(@class,'visually-hidden'))]"
        ),
    ]  # linkedin_ui/engage_dom.py:62; first item for the 2026 feed build

    VISIBLE_POSTS = [
        "//div[@role='listitem'][starts-with(@componentkey,'update-card-focus')]",
        "//div[@data-id]",
        "//div[contains(@class,'fie-impression-container')]",
        "//div[contains(@class,'feed-shared-update-v2__control-menu-container')]/div[contains(@class,'fie-impression-container')]",
        "//div[contains(@class,'feed-shared-update-v2')]",
        "//div[@role='listitem']",
    ]  # linkedin_ui/engage_dom.py:149; role items for the 2026 feed build

    POST_ROOT_FROM_BAR = [
        ".//ancestor::div[@role='listitem'][1]",
        ".//ancestor::div[contains(@class,'feed-shared-update-v2')][1]",
        ".//ancestor::div[contains(@data-urn,'activity')][1]",
        ".//ancestor::article[1]",
    ]  # linkedin_ui/engage_dom.py:348; role item first for the 2026 feed build

    TEXT_SNIPPETS = (
        ".//*[@data-testid='expandable-text-box' and "
        "not(ancestor::div[starts-with(@componentkey,'CommentComponentReference_urn:li:comment:')])]"
        " | .//div[contains(@class,'update-components-text') or "
        "contains(@class,'feed-shared-inline-show-more-text')]//*[normalize-space()]"
    )  # linkedin_ui/engage_dom.py:487, 734; data-testid for the 2026 feed build

    USER_COMMENT_MARKERS = [
        (
            ".//div[starts-with(@componentkey,'CommentComponentReference_urn:li:comment:')]"
            "[.//span[normalize-space(.)='• You']]"
        ),
        ".//*[contains(@class,'comments-comment-item')]//*[contains(normalize-space(.),'You')]",
        ".//*[contains(@class,'comments-comment-item')]//*[contains(normalize-space(.),'you')]",
    ]  # linkedin_ui/engage_dom.py:520; componentkey marker for the 2026 feed build

    ALL_COMMENTS = [
        (
            ".//div[starts-with(@componentkey,'CommentComponentReference_urn:li:comment:')]"
            "//*[@data-testid='expandable-text-box']"
        ),
        ".//*[contains(@class,'comments-comment-item')]//*[normalize-space()]",
    ]  # linkedin_ui/engage_dom.py:567; componentkey marker for the 2026 feed build

    AI_TEXT_NODES = [
        ".//div[contains(@class,'update-components-text')]//*[normalize-space()]",
        ".//div[contains(@class,'feed-shared-update-v2__description')]//*[normalize-space()]",
        ".//span[contains(@class,'break-words') and normalize-space()]",
    ]  # linkedin_ui/engage_dom.py:616

    PROMOTED_MARKER = (
        ".//*[contains(translate(normalize-space(.),"
        "'PROMOTED','promoted'),'promoted')]"
    )  # linkedin_ui/engage_dom.py:770

    ACTION_BAR = (
        ".//div[contains(@class,'feed-shared-social-action-bar')]"
        " | .//button[@aria-label='Comment']/ancestor::div"
        "[.//*[starts-with(@aria-label,'Reaction button state')]][1]"
    )  # linkedin_ui/engage_flow.py:356; ancestor fallback for the 2026 feed build

    LIKE_BUTTONS = [
        ".//button[starts-with(@aria-label,'Reaction button state')]",
        (
            ".//*[starts-with(@aria-label,'Reaction button state')]"
            "/ancestor::*[@role='button' or self::button][1]"
        ),
        ".//button[contains(@class,'react-button__trigger')]",
        ".//button[@aria-label='React Like']",
        ".//button[.//span[normalize-space()='Like']]",
    ]  # linkedin_ui/engage_dom.py:805; state labels for the 2026 feed build

    COMMENT_BUTTONS = [
        ".//button[@aria-label='Comment']",
        ".//button[.//svg[@id='comment-feed-compact']]",
        ".//button[contains(@class,'comment-button')]",
        ".//button[.//span[normalize-space()='Comment']]",
    ]  # linkedin_ui/engage_dom.py:858; aria label and svg id first

    COMMENT_EDITOR = [
        ".//div[@contenteditable='true' and @aria-label='Text editor for creating comment']",
        ".//div[@contenteditable='true' and contains(@class,'comments')]",
        ".//div[@contenteditable='true' and contains(@role,'textbox')]",
        ".//form[contains(@class,'comments')]//div[@contenteditable='true']",
    ]  # linkedin_ui/engage_dom.py:881; labelled editor first for the 2026 feed build

    SUBMIT_COMMENT = [
        ".//div[contains(@id,'commentButtonSection')]//button",
        ".//button[.//span[normalize-space()='Comment']]",
        "//button[contains(@class,'comments-comment-box__submit-button')]",
        "//button[.//span[normalize-space()='Post']]",
        "//button[@data-control-name='submit_comment']",
    ]  # linkedin_ui/engage_dom.py:988; labelled section first for the 2026 feed build

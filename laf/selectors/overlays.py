"""Selectors for finding and dismissing UI overlays.

WHY
  Serve the chat, toast and dialog overlays, so a change to those popups has one
  file to update.
"""


class OverlaySelectors:
    """Selectors for finding and dismissing UI overlays.

    WHY
      Serve the chat bubbles, toasts and draft dialogs that cover the page, so an
      overlay change has one file to update.
    """

    CHAT_CLOSE_BUTTON = (
        "//button[contains(@class, "
        "'msg-overlay-bubble-header__control--close')]"
    )  # linkedin_ui/overlays.py:64
    TOAST_CLOSE_BUTTON = (
        "//button[contains(@class, 'artdeco-toast-item__dismiss')]"  # linkedin_ui/overlays.py:75
    )
    SAVE_DRAFT_DIALOG = "//div[contains(@class, 'save-draft-dialog')]"  # linkedin_ui/overlays.py:86
    UNSAVED_DETOUR_DIALOG = (
        "//div[contains(@class, 'unsaved-detour-dialog')]"  # linkedin_ui/overlays.py:100
    )
    DIALOG_SECONDARY_BUTTON = (
        ".//button[contains(@class, "
        "'artdeco-button--secondary')]"
    )  # linkedin_ui/overlays.py:89, 103
    MODAL_DISMISS_BUTTON = (
        "//button[contains(@class, 'artdeco-modal__dismiss')]"  # linkedin_ui/overlays.py:115
    )
    SHARE_MODAL_ANCESTOR = (
        "ancestor::div[contains(@class,'share-box-modal')]"  # linkedin_ui/overlays.py:119
    )

    COMPOSER_ROOTS = [
        "//div[@role='dialog' and contains(@class, 'share-creation-state')]",
        "//div[@role='dialog' and contains(@class, 'share-box-modal')]",
        "//div[contains(@class, 'share-box-modal')]",
    ]  # linkedin_ui/overlays.py:134

    DRAFT_MODAL = (
        "//div[contains(@class,'artdeco-modal') and "
        "(.//button[normalize-space(.)='Save as draft'] or "
        ".//button[normalize-space(.)='Discard'])]"
    )  # linkedin_ui/overlays.py:148
    DRAFT_MODAL_CLOSE_BUTTON = (
        ".//button[contains(@class,'artdeco-modal__dismiss') or "
        "@aria-label='Dismiss' or @aria-label='Close']"
    )  # linkedin_ui/overlays.py:153
    UNEXPECTED_CLOSE_BUTTON = (
        "//button[@aria-label='Close' or @aria-label='Dismiss' or "
        "contains(@class, 'close-btn')]"
    )  # linkedin_ui/overlays.py:172

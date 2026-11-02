"""Dismiss the LinkedIn overlays that block automation flows.

WHY
  Chat bubbles, toasts and modals regularly cover key controls, so removing
  them before a click keeps the interaction from landing on the wrong thing.
"""

import logging

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

from laf.selectors.overlays import OverlaySelectors

from ..ui import UiActions

logger = logging.getLogger(__name__)

class OverlayService:
    """Close the overlays that sit over LinkedIn page controls.

    WHY
      Let other services click their target without an overlay swallowing the
      click or hiding the element.
    """

    def __init__(self, ui: UiActions) -> None:
        """
        WHY
          Give the overlay code the shared driver and pacing helpers without
          tying it to any other service.

        Args
          ui: UiActions, the shared Selenium action helper.

        MUTATIONS
          Stores the driver helper on the instance.
        """
        self.ui = ui

    def dismiss_overlays(self, preserve_share_modal=False):
        """Close chat, toast and dialog overlays before a critical click.

        WHY
          Stop an overlay from intercepting the next click or hiding the control
          the caller needs.

        Args
          preserve_share_modal: bool, passed by the composer as True when the
            open post modal must be left alone.
        """
        self.dismiss_global_search_overlay()
        self._dismiss_chat_overlay()
        self._dismiss_notification_toast()

        if not preserve_share_modal:
            self._dismiss_save_draft_dialog()
            self._dismiss_unsaved_detour_dialog()
            self._dismiss_modal_dialog()

        self._dismiss_draft_modal()

        if not preserve_share_modal:
            self._dismiss_unexpected_overlay()
            self._remove_modal_backdrops()

    def _dismiss_chat_overlay(self) -> None:
        """Close the chat bubble if it is open."""
        try:
            btn = self.ui.driver.find_element(By.XPATH, OverlaySelectors.CHAT_CLOSE_BUTTON)
            btn.click()
            logger.info("Closed chat overlay.")
        except WebDriverException:
            logger.info("No chat overlay to close.")

    def _dismiss_notification_toast(self) -> None:
        """Close the notification toast if it is showing."""
        try:
            btn = self.ui.driver.find_element(By.XPATH, OverlaySelectors.TOAST_CLOSE_BUTTON)
            btn.click()
            logger.info("Closed notification toast.")
        except WebDriverException:
            logger.info("No notification toast to close.")

    def _dismiss_save_draft_dialog(self) -> None:
        """Discard the 'save draft' dialog if it is open."""
        try:
            dialog = self.ui.driver.find_element(By.XPATH, OverlaySelectors.SAVE_DRAFT_DIALOG)
            discard = dialog.find_element(By.XPATH, OverlaySelectors.DIALOG_SECONDARY_BUTTON)
            discard.click()
            logger.info("Dismissed save draft dialog.")
            self.ui.pause(1, 2)
        except WebDriverException:
            logger.info("No save draft dialog to dismiss.")

    def _dismiss_unsaved_detour_dialog(self) -> None:
        """Dismiss the unsaved changes detour dialog if present."""
        try:
            dialog = self.ui.driver.find_element(By.XPATH, OverlaySelectors.UNSAVED_DETOUR_DIALOG)
            dismiss = dialog.find_element(By.XPATH, OverlaySelectors.DIALOG_SECONDARY_BUTTON)
            dismiss.click()
            logger.info("Dismissed unsaved detour dialog.")
            self.ui.pause(1, 2)
        except WebDriverException:
            logger.info("No unsaved detour dialog to dismiss.")

    def _dismiss_modal_dialog(self) -> None:
        """Close a generic modal, preserving the share composer."""
        try:
            btn = self.ui.driver.find_element(By.XPATH, OverlaySelectors.MODAL_DISMISS_BUTTON)
            if btn.find_elements(By.XPATH, OverlaySelectors.SHARE_MODAL_ANCESTOR):
                logger.info("Detected share composer modal; preserving it.")
            btn.click()
            logger.info("Closed a modal dialog using dismiss button.")
            self.ui.pause(1, 2)
        except WebDriverException:
            logger.info("No modal dialog dismiss button found or preserved.")

    def _dismiss_draft_modal(self) -> None:
        """Close the 'Save as draft' modal if the composer is open."""
        composer_present = False
        for root in OverlaySelectors.COMPOSER_ROOTS:
            try:
                self.ui.driver.find_element(By.XPATH, root)
                composer_present = True
                break
            except WebDriverException:
                continue
        if not composer_present:
            return
        try:
            modal = self.ui.driver.find_element(By.XPATH, OverlaySelectors.DRAFT_MODAL)
            try:
                btn = modal.find_element(By.XPATH, OverlaySelectors.DRAFT_MODAL_CLOSE_BUTTON)
                btn.click()
                logger.info("Closed 'Save as draft' modal to resume composing.")
                self.ui.pause(0.5, 1.0)
            except WebDriverException:
                logger.info(
                    "Could not locate dismiss button on 'Save as draft' modal; "
                    "leaving it alone."
                )
        except WebDriverException:
            logger.debug("Draft modal not found while the composer is present")

    def _dismiss_unexpected_overlay(self) -> None:
        """Close an unexpected overlay with a close button."""
        try:
            btn = self.ui.driver.find_element(By.XPATH, OverlaySelectors.UNEXPECTED_CLOSE_BUTTON)
            btn.click()
            logger.info("Closed an unexpected overlay.")
            self.ui.pause(1, 2)
        except WebDriverException:
            logger.info("No unexpected overlay to close.")

    def _remove_modal_backdrops(self) -> None:
        """Remove modal backdrops via JavaScript."""
        try:
            self.ui.driver.execute_script(
                (
                    """
                var backdrops = document.querySelectorAll("""
                "'.artdeco-modal-overlay, .artdeco-modal__overlay');\n"
                "                backdrops.forEach(function(backdrop) { "
                "backdrop.remove(); });\n"
                """                document.body.style.overflow = 'auto';
                """
                )
            )
            logger.info("Attempted to remove modal backdrops with JavaScript.")
        except WebDriverException as e:
            logger.info(f"JavaScript modal removal unsuccessful: {e.msg}")

    def dismiss_global_search_overlay(self):
        """Hide the global search typeahead when it covers the page.

        WHY
          The header popover can sit over the composer or comment box and take
          the clicks meant for them.
        """
        try:
            js_probe = (
                """
                const sels = [
                  '.search-typeahead-v2',
                  '.search-typeahead-v2__hit',
                  '.search-global-typeahead',
                  'div[id*="global-nav"] .typeahead',
                ];
                let visible = 0;
                for (const s of sels) {
                  document.querySelectorAll(s).forEach(n => {
                    const shown = !!(n && (n.offsetWidth || n.offsetHeight """
                "|| n.getClientRects().length));\n"
                """                    if (shown) visible++;
                  });
                }
                return visible;
            """
            )
            visible_count = int(self.ui.driver.execute_script(js_probe) or 0)
        except (WebDriverException, TypeError, ValueError):
            visible_count = 0
        if visible_count <= 0:
            return
        try:
            js_hide = """
                const sels = [
                  '.search-typeahead-v2',
                  '.search-typeahead-v2__hit',
                  '.search-global-typeahead',
                  'div[id*="global-nav"] .typeahead',
                ];
                for (const s of sels) {
                  document.querySelectorAll(s).forEach(n => {
                    n.style.display = 'none';
                    n.style.visibility = 'hidden';
                    n.style.pointerEvents = 'none';
                  });
                }
                return true;
            """
            self.ui.driver.execute_script(js_hide)
        except WebDriverException:
            logger.debug("Could not hide the global search overlay")

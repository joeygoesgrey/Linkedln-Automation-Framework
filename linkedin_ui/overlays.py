"""Helpers for dismissing LinkedIn overlays that block automation flows.

Why:
    Chat bubbles, toasts, and modals regularly obscure key controls; removing
    them proactively keeps interactions reliable.

When:
    Mixed into :class:`LinkedInInteraction` and invoked before critical clicks.

How:
    Uses targeted selectors and conservative JavaScript to close overlays while
    avoiding disruption of active composer modals.
"""

import time
import logging
from selenium.webdriver.common.by import By

import config
from ui_selectors import OverlaySelectors


class OverlayMixin:
    """Utilities for dismissing overlays that obstruct LinkedIn automation.

    Why:
        Keeps overlay handling logic in one place so other mixins can focus on their primary tasks.

    When:
        Mixed into :class:`LinkedInInteraction` and used before major UI interactions.

    How:
        Exposes methods to close chat bubbles, toasts, modals, and search overlays via Selenium and JavaScript fallbacks.
    """
    def dismiss_overlays(self, preserve_share_modal=False):
        """Close common overlays that interfere with automation.

        Why:
            LinkedIn frequently surfaces chat bubbles, save-draft dialogs, and
            toasts that intercept clicks.

        When:
            Called before interacting with controls that may be blocked by such
            overlays.

        How:
            Attempts to close known overlay types via targeted selectors and JS,
            optionally preserving the share modal when requested.

        Args:
            preserve_share_modal (bool): If ``True``, avoids dismissing the post
                composer modal.

        Returns:
            None
        """
        try:
            self._dismiss_global_search_overlay()
        except Exception:
            pass

        # Chat overlay
        try:
            chat_overlay_close_button = self.driver.find_element(
                By.XPATH, OverlaySelectors.CHAT_CLOSE_BUTTON
            )
            chat_overlay_close_button.click()
            logging.info("Closed chat overlay.")
        except Exception:
            logging.info("No chat overlay to close.")

        # Notification toast
        try:
            toast_close_button = self.driver.find_element(
                By.XPATH, OverlaySelectors.TOAST_CLOSE_BUTTON
            )
            toast_close_button.click()
            logging.info("Closed notification toast.")
        except Exception:
            logging.info("No notification toast to close.")

        if not preserve_share_modal:
            # Save draft dialog
            try:
                save_draft_dialog = self.driver.find_element(
                    By.XPATH, OverlaySelectors.SAVE_DRAFT_DIALOG
                )
                discard_button = save_draft_dialog.find_element(
                    By.XPATH, OverlaySelectors.DIALOG_SECONDARY_BUTTON
                )
                discard_button.click()
                logging.info("Dismissed save draft dialog.")
                self.random_delay(1, 2)
            except Exception:
                logging.info("No save draft dialog to dismiss.")

            # Unsaved detour dialog
            try:
                unsaved_dialog = self.driver.find_element(
                    By.XPATH, OverlaySelectors.UNSAVED_DETOUR_DIALOG
                )
                dismiss_button = unsaved_dialog.find_element(
                    By.XPATH, OverlaySelectors.DIALOG_SECONDARY_BUTTON
                )
                dismiss_button.click()
                logging.info("Dismissed unsaved detour dialog.")
                self.random_delay(1, 2)
            except Exception:
                logging.info("No unsaved detour dialog to dismiss.")

        # Generic modal dismiss (avoid composer)
        if not preserve_share_modal:
            try:
                modal_close_button = self.driver.find_element(
                    By.XPATH, OverlaySelectors.MODAL_DISMISS_BUTTON
                )
                try:
                    modal_close_button.find_element(
                        By.XPATH, OverlaySelectors.SHARE_MODAL_ANCESTOR
                    )
                    logging.info("Detected share composer modal; preserving it.")
                    raise Exception("Preserve share composer")
                except Exception:
                    pass
                modal_close_button.click()
                logging.info("Closed a modal dialog using dismiss button.")
                self.random_delay(1, 2)
            except Exception:
                logging.info("No modal dialog dismiss button found or preserved.")

        # Special handling for draft modal while composer is present
        try:
            composer_present = False
            for root in OverlaySelectors.COMPOSER_ROOTS:
                try:
                    self.driver.find_element(By.XPATH, root)
                    composer_present = True
                    break
                except Exception:
                    continue
            if composer_present:
                try:
                    draft_modal = self.driver.find_element(
                        By.XPATH, OverlaySelectors.DRAFT_MODAL
                    )
                    try:
                        close_btn = draft_modal.find_element(
                            By.XPATH, OverlaySelectors.DRAFT_MODAL_CLOSE_BUTTON
                        )
                        close_btn.click()
                        logging.info("Closed 'Save as draft' modal to resume composing.")
                        self.random_delay(0.5, 1.0)
                    except Exception:
                        logging.info(
                            "Could not locate dismiss button on 'Save as draft' modal; leaving it alone."
                        )
                except Exception:
                    pass
        except Exception:
            pass

        # Unexpected overlay with close button
        if not preserve_share_modal:
            try:
                close_button = self.driver.find_element(
                    By.XPATH, OverlaySelectors.UNEXPECTED_CLOSE_BUTTON
                )
                close_button.click()
                logging.info("Closed an unexpected overlay.")
                self.random_delay(1, 2)
            except Exception:
                logging.info("No unexpected overlay to close.")

        # Remove modal backdrops via JS, conservative
        if not preserve_share_modal:
            try:
                self.driver.execute_script(
                    """
                    var backdrops = document.querySelectorAll('.artdeco-modal-overlay, .artdeco-modal__overlay');
                    backdrops.forEach(function(backdrop) { backdrop.remove(); });
                    document.body.style.overflow = 'auto';
                    """
                )
                logging.info("Attempted to remove modal backdrops with JavaScript.")
            except Exception as e:
                logging.info(f"JavaScript modal removal unsuccessful: {e}")

    def _dismiss_global_search_overlay(self):
        """Hide the global search typeahead when it obstructs interactions.

        Why:
            The global header popover can overlap the composer or comment box.

        When:
            Invoked as part of overlay dismissal before sensitive operations.

        How:
            Executes JavaScript to detect visible typeahead nodes and hide them
            by tweaking style attributes.

        Returns:
            None
        """
        try:
            js_probe = """
                const sels = [
                  '.search-typeahead-v2',
                  '.search-typeahead-v2__hit',
                  '.search-global-typeahead',
                  'div[id*="global-nav"] .typeahead',
                ];
                let visible = 0;
                for (const s of sels) {
                  document.querySelectorAll(s).forEach(n => {
                    const shown = !!(n && (n.offsetWidth || n.offsetHeight || n.getClientRects().length));
                    if (shown) visible++;
                  });
                }
                return visible;
            """
            visible_count = int(self.driver.execute_script(js_probe) or 0)
        except Exception:
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
            self.driver.execute_script(js_hide)
        except Exception:
            pass

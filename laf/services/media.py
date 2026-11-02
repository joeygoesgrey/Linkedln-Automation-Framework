"""Attach images to a post from inside the LinkedIn composer.

WHY
  Put images on a post through the page's file input, so a caller does not
  have to touch the hidden input or the native picker itself.
"""

import logging
from pathlib import Path
from typing import Iterable, Optional

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from laf.selectors.media import MediaSelectors

from ..ui import UiActions
from .overlays import OverlayService

logger = logging.getLogger(__name__)

class MediaService:
    """Upload images into the composer's media dialog.

    WHY
      Let a post carry images without anyone driving the media tray or the
      hidden file input by hand.
    """

    def __init__(self, ui: UiActions, overlays: OverlayService) -> None:
        """
        WHY
          Give media upload the shared driver, pacing helpers and overlay
          cleanup so the file input can be found and used reliably.

        Args
          ui: UiActions, the shared Selenium action helper.
          overlays: OverlayService, used to clear dialogs around the upload.

        MUTATIONS
          Stores the driver helper, the overlay service and the config on the
          instance.
        """
        self.ui = ui
        self.overlays = overlays
        self.config = ui.config

    def _open_media_tray_for_upload(self) -> Optional[WebElement]:
        """Open the media tray and return a usable file input element.

        WHY
          Keep the media tray opening and file input discovery out of the main
          upload method so it stays under the 60-line ceiling.

        Returns
          Optional[WebElement], the file input, or None when the input cannot
          be found after trying.
        """
        self.ui.pause()
        self.overlays.dismiss_overlays(preserve_share_modal=True)
        self.ui.pause()

        media_button = self._find_photo_button()
        if media_button:
            if not self.ui.click_with_fallback(media_button, "Add media"):
                logger.warning("Click on 'Add media' failed; will try to find input directly")
            else:
                self.ui.pause(1, 2)

        file_input = self._find_file_input()
        if not file_input:
            if media_button:
                self.ui.click_with_fallback(media_button, "Add media (retry)")
                self.ui.pause(1, 2)
            file_input = self._find_file_input()
            if not file_input:
                logger.error("Could not find file input element after opening media UI")
                return None
        return file_input

    def upload_images_to_post(self, image_paths: Iterable[str]) -> bool:
        """Send the given image files to the open composer.

        WHY
          Attach images to a post without a person opening the media tray and
          picking files.

        Args
          image_paths: Iterable[str], the file paths supplied by the posting
            workflow, relative or absolute.

        Returns
          bool, True when the paths were sent or no paths were given, False when
          the file input is missing or sending the paths raised.

        MUTATIONS
          Sends the image file paths to the page's file input and may unhide or
          create that input in the browser.
        """
        # Standard 3: Basic validation
        if not image_paths:
            logger.info("No images provided for upload, skipping")
            return True

        if not isinstance(image_paths, (list, tuple, set)):
            try:
                image_paths = list(image_paths)
            except TypeError:
                logger.error(f"Invalid image_paths type: {type(image_paths)}")
                return False

        try:
            logger.info(f"Uploading {len(image_paths)} images to LinkedIn post")
            file_input = self._open_media_tray_for_upload()
            if not file_input:
                return False
            abs_image_paths = [str(Path(path).absolute()) for path in image_paths]
            image_paths_str = "\n".join(abs_image_paths)
            self.ui.pause()
            try:
                file_input.send_keys(image_paths_str)
                logger.info(f"Sent image paths to file input: {abs_image_paths}")
                preview_selectors = MediaSelectors.PREVIEWS
                uploaded = False
                for sel in preview_selectors:
                    try:
                        WebDriverWait(self.ui.driver, self.config.element_timeout).until(
                            EC.presence_of_element_located((By.XPATH, sel))
                        )
                        logger.info(f"Detected uploaded media preview via selector: {sel}")
                        uploaded = True
                        break
                    except WebDriverException:
                        logger.debug(f"Media preview not found via selector: {sel}")
                        continue
                if not uploaded:
                    self.ui.pause(3, 5)
                self.overlays.dismiss_overlays(preserve_share_modal=True)
                self.ui.pause(1, 2)
                if self._handle_post_upload_buttons():
                    logger.info("Successfully processed post-upload buttons")
                    self.overlays.dismiss_overlays(preserve_share_modal=True)
                    return True
                else:
                    logger.info("No post-upload buttons found, continuing anyway")
                    return True
            except WebDriverException as e:
                logger.error(f"Failed to upload images: {e.msg}", exc_info=True)
                return False
        except (OSError, TypeError, WebDriverException) as e:
            logger.error(f"Error during image upload process: {e}", exc_info=True)
            return False

    def _find_photo_button(self) -> Optional[WebElement]:
        """Find the composer button that opens the media selector.

        WHY
          The photo control has different selectors between page variants, and
          trying them all keeps the media tray reachable.

        Returns
          Optional[WebElement], the first enabled media button, or None when no
          selector matched.
        """
        photo_button_selectors = MediaSelectors.PHOTO_BUTTONS
        modal_photo_button_selectors = MediaSelectors.MODAL_PHOTO_BUTTONS
        all_selectors = modal_photo_button_selectors + photo_button_selectors
        for selector in all_selectors:
            try:
                selector_type = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
                button = WebDriverWait(self.ui.driver, self.config.element_timeout).until(
                    EC.element_to_be_clickable((selector_type, selector))
                )
                logger.info(f"Found photo button with selector: {selector}")
                return button
            except WebDriverException as e:
                logger.info(f"Photo button selector {selector} not found: {e.msg}")
        logger.error("Could not find any photo upload button in composer")
        return None

    def _find_file_input(self) -> Optional[WebElement]:
        """Find, reveal or create the file input used by the media uploader.

        WHY
          Selenium cannot use the native file picker, so the paths must go to a
          real input, which is often hidden, inside a shadow root or absent.

        Returns
          Optional[WebElement], a usable file input, or None when every search
          and the create fallback failed.

        MUTATIONS
          Unhides known file inputs with JavaScript and, as a last resort,
          appends a new file input to the page.
        """
        logger.info("Finding file input element...")
        modal_roots = MediaSelectors.MODAL_ROOTS
        modal = None
        for root in modal_roots:
            try:
                modal = WebDriverWait(self.ui.driver, self.config.element_timeout).until(
                    EC.presence_of_element_located((By.XPATH, root))
                )
                break
            except WebDriverException:
                logger.debug(f"Modal root not found: {root}")
                continue
        file_input_selectors = MediaSelectors.FILE_INPUTS
        for selector in file_input_selectors:
            selector_type = By.CSS_SELECTOR if not selector.startswith("//") else By.XPATH
            try:
                logger.info(f"Trying file input selector: {selector}")
                if modal is not None and selector.startswith("//"):
                    candidate = modal.find_element(By.XPATH, "." + selector[1:])
                else:
                    candidate = WebDriverWait(self.ui.driver, self.config.short_timeout).until(
                        EC.presence_of_element_located((selector_type, selector))
                    )
                try:
                    self.ui.driver.execute_script(
                        "arguments[0].classList.remove('visually-hidden'); "
                        "arguments[0].disabled=false; "
                        "arguments[0].style.cssText='display:block!important;"
                        "visibility:visible!important;opacity:1!important;"
                        "position:static!important;width:1px;height:1px';",
                        candidate,
                    )
                except WebDriverException:
                    logger.debug("Could not unhide the located file input")
                logger.info(f"Found file input element with selector: {selector}")
                return candidate
            except WebDriverException as e:
                logger.info(f"File input selector {selector} failed: {e.msg}")
        try:
            logger.info("Trying to resolve file input via label 'Upload from computer'")
            label = None
            if modal is not None:
                try:
                    label = modal.find_element(By.XPATH, MediaSelectors.UPLOAD_LABEL)
                except WebDriverException:
                    logger.debug("Upload label not found inside the modal")
                    label = None
            if not label:
                label = self.ui.driver.find_element(By.XPATH, MediaSelectors.UPLOAD_LABEL)
            input_id = label.get_attribute("for")
            if input_id:
                by_id_xpath = f"//input[@id='{input_id}']"
                logger.info(f"Resolved input id via label: {input_id}")
                if modal is not None:
                    candidate = modal.find_element(By.XPATH, "." + by_id_xpath[1:])
                else:
                    candidate = self.ui.driver.find_element(By.XPATH, by_id_xpath)
                try:
                    self.ui.driver.execute_script(
                        "arguments[0].classList.remove('visually-hidden'); "
                        "arguments[0].disabled=false; "
                        "arguments[0].style.cssText='display:block!important;"
                        "visibility:visible!important;opacity:1!important;"
                        "position:static!important;width:1px;height:1px';",
                        candidate,
                    )
                except WebDriverException:
                    logger.debug("Could not unhide the file input resolved via label")
                return candidate
        except WebDriverException as e:
            logger.info(f"Label resolution failed: {e.msg}")
        logger.info("Trying JavaScript to reveal hidden file input...")
        try:
            js_to_reveal_file_inputs = (
                """
            let fileInput = document.getElementById('media-editor-file-selector__file-input');
            if (!fileInput) {
                const fileInputs = Array.from(document.querySelectorAll('input[type="file"]'));
                fileInputs.forEach(input => {
                    input.style.cssText = 'display: block !important; """
                "visibility: visible !important; opacity: 1 !important; "
                "position: static !important;';\n"
                """                    input.disabled = false;
                    input.classList.remove('visually-hidden');
                    let parent = input.parentElement;
                    for (let i = 0; i < 5 && parent; i++) {
                        parent.style.cssText = 'display: block !important; """
                "visibility: visible !important; opacity: 1 !important;';\n"
                """                        parent = parent.parentElement;
                    }
                });
                fileInput = fileInputs[0];
            } else {
                fileInput.style.cssText = 'display: block !important; """
                "visibility: visible !important; opacity: 1 !important; "
                "position: static !important;';\n"
                """                fileInput.classList.remove('visually-hidden');
                fileInput.disabled = false;
            }
            return fileInput ? true : false;
            """
            )
            self.ui.driver.execute_script(js_to_reveal_file_inputs)
            logger.info("JavaScript executed to reveal hidden file inputs")
            for selector in file_input_selectors:
                selector_type = By.CSS_SELECTOR if not selector.startswith("//") else By.XPATH
                try:
                    logger.info(f"Trying file input selector after JS reveal: {selector}")
                    file_input = WebDriverWait(self.ui.driver, self.config.short_timeout).until(
                        EC.presence_of_element_located((selector_type, selector))
                    )
                    logger.info(
                        f"Found file input element after JS reveal with selector: {selector}"
                    )
                    return file_input
                except WebDriverException:
                    logger.debug(f"File input not found after JS reveal: {selector}")
                    continue
            logger.info("No file input found after JavaScript reveal")
        except WebDriverException as e:
            logger.warning(f"Error executing JavaScript to reveal file inputs: {e.msg}")
        try:
            logger.info("Searching shadow roots for file inputs")
            deep_search_js = """
                const results = [];
                const seen = new Set();
                function walk(node){
                  if(!node || seen.has(node)) return;
                  seen.add(node);
                  if (node.querySelectorAll) {
                    node.querySelectorAll('input[type="file"]').forEach(el => results.push(el));
                  }
                  const children = node.children ? Array.from(node.children) : [];
                  for (const child of children) { walk(child); }
                  if (node.shadowRoot) { walk(node.shadowRoot); }
                }
                walk(document);
                return results;
            """
            inputs = self.ui.driver.execute_script(deep_search_js) or []
            logger.info(f"Deep search found {len(inputs)} candidate file inputs")
            for idx, candidate in enumerate(inputs):
                try:
                    acc = (candidate.get_attribute("accept") or "").lower()
                    cls = candidate.get_attribute("class") or ""
                    idv = candidate.get_attribute("id") or ""
                    if ("image" in acc) or (not acc):
                        self.ui.driver.execute_script(
                            "arguments[0].style.cssText='display:block!important;visibility:visible!important;opacity:1!important;position:static!important;width:1px;height:1px';",
                            candidate,
                        )
                        logger.info(
                            f"Using shadow file input candidate idx={idx} "
                            f"id='{idv}' class='{cls}' accept='{acc}'"
                        )
                        return candidate
                except WebDriverException:
                    logger.debug(f"Shadow file input candidate idx={idx} could not be used")
                    continue
        except WebDriverException as e:
            logger.info(f"Deep shadow search failed: {e.msg}")
        try:
            logger.info("Scanning iframes for file input")
            frames = self.ui.driver.find_elements(By.TAG_NAME, "iframe")
            for i, frame in enumerate(frames):
                try:
                    self.ui.driver.switch_to.frame(frame)
                    logger.info(f"Switched to iframe index {i}")
                    for selector in MediaSelectors.IFRAME_INPUTS:
                        try:
                            by = By.CSS_SELECTOR if not selector.startswith("//") else By.XPATH
                            fi = WebDriverWait(self.ui.driver, 2).until(
                                EC.presence_of_element_located((by, selector))
                            )
                            self.ui.driver.execute_script(
                                "arguments[0].style.cssText='display:block!important;visibility:visible!important;opacity:1!important;position:static!important;width:1px;height:1px';",
                                fi,
                            )
                            logger.info(
                                f"Found file input in iframe index {i} using selector {selector}"
                            )
                            return fi
                        except WebDriverException:
                            logger.debug(f"File input not found in iframe {i}: {selector}")
                            continue
                except WebDriverException as e:
                    logger.debug(f"Error scanning iframe {i}: {e.msg}")
                finally:
                    try:
                        self.ui.driver.switch_to.default_content()
                    except WebDriverException:
                        logger.debug("Could not switch back to the default frame")
        except WebDriverException as e:
            logger.info(f"Iframe scan failed: {e.msg}")
        logger.info("Creating a new file input element as a last resort")
        try:
            create_input_js = (
                """
            const newInput = document.createElement('input');
            newInput.type = 'file';
            newInput.id = 'linkedin-bot-file-input';
            newInput.style.cssText = 'position: fixed; top: 0; left: 0; """
            "display: block !important; z-index: 9999;';\n"
            """            document.body.appendChild(newInput);
            return true;
            """
            )
            self.ui.driver.execute_script(create_input_js)
            try:
                file_input = WebDriverWait(self.ui.driver, self.config.short_timeout).until(
                    EC.presence_of_element_located((By.ID, "linkedin-bot-file-input"))
                )
                logger.info("Successfully created and found new file input element")
                return file_input
            except WebDriverException as e:
                logger.error(f"Could not find created file input: {e.msg}")
        except WebDriverException as e:
            logger.error(f"Error creating new file input: {e.msg}")
        logger.error("All attempts to find or create file input element failed")
        return None

    def _handle_post_upload_buttons(self) -> bool:
        """Clear the follow-up buttons a media upload can show.

        WHY
          The media dialog may wait on a Done or Next button before the image
          becomes part of the post.

        Returns
          bool, True when a follow-up button was clicked or the Back button
          shows the upload finished, False when neither is present.
        """
        buttons_selectors = MediaSelectors.POST_UPLOAD_BUTTONS
        for selector in buttons_selectors:
            try:
                selector_type = By.CSS_SELECTOR if not selector.startswith("//") else By.XPATH
                next_button = WebDriverWait(self.ui.driver, self.config.element_timeout).until(
                    EC.element_to_be_clickable((selector_type, selector))
                )
                self.ui.pause()
                logger.info(f"Found post-upload button with selector: {selector}")
                self.ui.click_with_fallback(next_button, f"post-upload button ({selector})")
                self.ui.pause(1, 2)
                return True
            except WebDriverException as e:
                logger.debug(f"Post-upload button selector {selector} not found: {e.msg}")
        try:
            WebDriverWait(self.ui.driver, self.config.short_timeout).until(
                EC.presence_of_element_located((By.XPATH, MediaSelectors.BACK_BUTTON))
            )
            logger.info("Found 'Back' button, which suggests we're in the post-upload flow")
            return True
        except WebDriverException:
            logger.debug("Back button not found after the media upload")
        return False

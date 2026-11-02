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

    def _find_media_modal(self) -> Optional[WebElement]:
        """Find the media upload modal root element.

        WHY
          Keep the modal discovery out of the file input search for modularity.

        Returns
          Optional[WebElement], the modal element, or None.
        """
        for root in MediaSelectors.MODAL_ROOTS:
            try:
                return WebDriverWait(self.ui.driver, self.config.element_timeout).until(
                    EC.presence_of_element_located((By.XPATH, root))
                )
            except WebDriverException:
                continue
        return None

    def _find_by_selectors(self, modal, selectors, by) -> Optional[WebElement]:
        """Try each selector and return the first visible file input.

        WHY
          Keep the selector iteration out of each fallback method.

        Returns
          Optional[WebElement], the unhidden input, or None.
        """
        for selector in selectors:
            try:
                if modal is not None and selector.startswith("//"):
                    el = modal.find_element(By.XPATH, "." + selector[1:])
                else:
                    el = WebDriverWait(self.ui.driver, self.config.short_timeout).until(
                        EC.presence_of_element_located((by, selector))
                    )
                self._unhide_element(el)
                logger.info(f"Found file input with selector: {selector}")
                return el
            except WebDriverException:
                continue
        return None

    def _unhide_element(self, el) -> None:
        """Remove hidden styles from an element via JavaScript.

        WHY
          Selenium cannot interact with visually-hidden elements, so make
          them accessible before use.

        MUTATIONS
          Modifies the element's CSS classes and inline styles.
        """
        css = 'display:block!important;visibility:visible!important;'
        css += 'opacity:1!important;position:static!important;width:1px;height:1px'
        try:
            self.ui.driver.execute_script(
                'arguments[0].classList.remove("visually-hidden");'
                'arguments[0].disabled=false;'
                "arguments[0].style.cssText='" + css + "';",
                el,
            )
        except WebDriverException:
            pass

    def _find_file_input_by_label(self, modal) -> Optional[WebElement]:
        """Resolve a file input via its 'Upload from computer' label.

        Returns
          Optional[WebElement], the input, or None.
        """
        try:
            label = None
            if modal is not None:
                try:
                    label = modal.find_element(By.XPATH, MediaSelectors.UPLOAD_LABEL)
                except WebDriverException:
                    pass
            if not label:
                label = self.ui.driver.find_element(By.XPATH, MediaSelectors.UPLOAD_LABEL)
            input_id = label.get_attribute("for")
            if not input_id:
                return None
            xp = f"//input[@id='{input_id}']"
            candidate = (
                modal.find_element(By.XPATH, "." + xp[1:]) if modal else
                self.ui.driver.find_element(By.XPATH, xp)
            )
            self._unhide_element(candidate)
            return candidate
        except WebDriverException:
            return None

    def _reveal_and_find_via_js(self, selectors) -> Optional[WebElement]:
        """Use JavaScript to reveal hidden file inputs, then retry selectors.

        Returns
          Optional[WebElement], the first found input, or None.
        """
        vis_css = 'display:block!important;visibility:visible!important;'
        vis_css += 'opacity:1!important;position:static!important;'
        js = (
            'var fi=document.getElementById('
            + '"media-editor-file-selector__file-input");'
            'if(!fi){'
            'var all=Array.from(document.querySelectorAll('
            + "'input[type=\\\"file\\\"]'));"
            'all.forEach(function(inp){'
            "inp.style.cssText='" + vis_css + "';"
            'inp.disabled=false;'
            'inp.classList.remove("visually-hidden");'
            'var p=inp.parentElement;'
            'for(var i=0;i<5&&p;i++){'
            "p.style.cssText='" + vis_css + "';"
            'p=p.parentElement;}});'
            'fi=all[0];}else{'
            "fi.style.cssText='" + vis_css + "';"
            'fi.classList.remove("visually-hidden");'
            'fi.disabled=false;}'
            'return!!fi;'
        )
        try:
            self.ui.driver.execute_script(js)
            for selector in selectors:
                try:
                    by = By.CSS_SELECTOR if not selector.startswith("//") else By.XPATH
                    fi = WebDriverWait(self.ui.driver, self.config.short_timeout).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    return fi
                except WebDriverException:
                    continue
        except WebDriverException:
            pass
        return None

    def _find_in_shadow_roots(self) -> Optional[WebElement]:
        """Deep-search shadow roots for file inputs.

        Returns
          Optional[WebElement], a suitable input, or None.
        """
        js = (
            'var r=[],s=new Set();'
            'function w(n){if(!n||s.has(n))return;s.add(n);'
            "if(n.querySelectorAll)n.querySelectorAll('input[type=file]')"
            + '.forEach(function(e){r.push(e);});'
            'var c=(n.children?Array.from(n.children):[]);'
            'for(var i=0;i<c.length;i++)w(c[i]);'
            'if(n.shadowRoot)w(n.shadowRoot);}'
            'w(document);return r;'
        )
        try:
            inputs = self.ui.driver.execute_script(js) or []
            for idx, candidate in enumerate(inputs):
                try:
                    acc = (candidate.get_attribute("accept") or "").lower()
                    if ("image" in acc) or (not acc):
                        self._unhide_element(candidate)
                        return candidate
                except WebDriverException:
                    continue
        except WebDriverException:
            pass
        return None

    def _find_in_iframes(self) -> Optional[WebElement]:
        """Search each iframe for a file input.

        Returns
          Optional[WebElement], the first found input, or None.
        """
        try:
            frames = self.ui.driver.find_elements(By.TAG_NAME, "iframe")
            for i, frame in enumerate(frames):
                try:
                    self.ui.driver.switch_to.frame(frame)
                    for selector in MediaSelectors.IFRAME_INPUTS:
                        try:
                            by = By.CSS_SELECTOR if not selector.startswith("//") else By.XPATH
                            fi = WebDriverWait(self.ui.driver, 2).until(
                                EC.presence_of_element_located((by, selector))
                            )
                            self._unhide_element(fi)
                            return fi
                        except WebDriverException:
                            continue
                except WebDriverException:
                    pass
                finally:
                    try:
                        self.ui.driver.switch_to.default_content()
                    except WebDriverException:
                        pass
        except WebDriverException:
            pass
        return None

    def _create_new_file_input(self) -> Optional[WebElement]:
        """Create a new file input element as a last resort.

        Returns
          Optional[WebElement], the newly created input, or None.
        """
        js = """
            const n = document.createElement('input');
            n.type = 'file'; n.id = 'linkedin-bot-file-input';
            n.style.cssText = 'position:fixed;top:0;left:0;display:block!important;z-index:9999;';
            document.body.appendChild(n); return true;
        """
        try:
            self.ui.driver.execute_script(js)
            return WebDriverWait(self.ui.driver, self.config.short_timeout).until(
                EC.presence_of_element_located((By.ID, "linkedin-bot-file-input"))
            )
        except WebDriverException:
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
        modal = self._find_media_modal()
        file_input_selectors = MediaSelectors.FILE_INPUTS
        selector_type = By.CSS_SELECTOR

        result = self._find_by_selectors(modal, file_input_selectors, selector_type)
        if result:
            return result
        result = self._find_file_input_by_label(modal)
        if result:
            return result
        result = self._reveal_and_find_via_js(file_input_selectors)
        if result:
            return result
        result = self._find_in_shadow_roots()
        if result:
            return result
        result = self._find_in_iframes()
        if result:
            return result
        result = self._create_new_file_input()
        if result:
            return result

        logger.error("All methods to find/create file input exhausted.")
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

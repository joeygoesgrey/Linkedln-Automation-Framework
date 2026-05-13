"""
Media upload helpers for the composer.

Why:
    Attach images alongside post text using resilient discovery of upload
    buttons and file inputs.

When:
    After composing text/mentions, if image paths are provided.

How:
    Finds the photo/media button, resolves the file input (including hidden or
    shadow-root cases), sends absolute paths, then handles post-upload steps.
"""

import logging
from pathlib import Path
from typing import Optional, List, Iterable, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement

import config
from ui_selectors import MediaSelectors


class MediaMixin:
    """Handle media attachment flows within the LinkedIn composer.

    Why:
        Uploading images involves hidden inputs and confirmation steps that are easy to break.

    When:
        Mixed into :class:`LinkedInInteraction` to support posts with media attachments.

    How:
        Provides helpers to open the media tray, locate file inputs, send paths, and confirm uploads.
    """
    def upload_images_to_post(self, image_paths: Iterable[str]) -> bool:
        """Attach images to the current post using the LinkedIn media dialog.

        Why:
            Automating image uploads enables richer posts without manual steps.

        When:
            Called after text is composed when images are supplied.

        How:
            Opens the media tray, locates file inputs, sends absolute paths,
            waits for previews, and handles post-upload confirmation buttons.

        Args:
            image_paths (Iterable[str]): Absolute or relative image paths to upload.

        Returns:
            bool: ``True`` on success, ``False`` when uploads fail.
        """
        # Standard 3: Basic validation
        if not image_paths:
            logging.info("No images provided for upload, skipping")
            return True
        
        if not isinstance(image_paths, (list, tuple, set)):
            try:
                image_paths = list(image_paths)
            except Exception:
                logging.error(f"Invalid image_paths type: {type(image_paths)}")
                return False

        try:
            logging.info(f"Uploading {len(image_paths)} images to LinkedIn post")
            self.random_delay()
            self.dismiss_overlays(preserve_share_modal=True)
            self.random_delay()

            # Proactively open the media tray first; many UIs only create the input after this.
            media_button = self._find_photo_button()
            if media_button:
                if not self._click_element_with_fallback(media_button, "Add media"):
                    logging.warning("Click on 'Add media' failed; will try to find input directly")
                else:
                    self.random_delay(1, 2)

            # Now find a file input to avoid native OS picker
            file_input = self._find_file_input()
            if not file_input:
                # Try clicking media button once more and re-scan
                if media_button:
                    try:
                        self._click_element_with_fallback(media_button, "Add media (retry)")
                        self.random_delay(1, 2)
                    except Exception:
                        pass
                file_input = self._find_file_input()
                if not file_input:
                    logging.error("Could not find file input element after opening media UI")
                    return False
            abs_image_paths = [str(Path(path).absolute()) for path in image_paths]
            image_paths_str = "\n".join(abs_image_paths)
            self.random_delay()
            try:
                file_input.send_keys(image_paths_str)
                logging.info(f"Sent image paths to file input: {abs_image_paths}")
                preview_selectors = MediaSelectors.PREVIEWS
                uploaded = False
                for sel in preview_selectors:
                    try:
                        WebDriverWait(self.driver, config.ELEMENT_TIMEOUT).until(
                            EC.presence_of_element_located((By.XPATH, sel))
                        )
                        logging.info(
                            f"Detected uploaded media preview via selector: {sel}"
                        )
                        uploaded = True
                        break
                    except Exception:
                        continue
                if not uploaded:
                    self.random_delay(3, 5)
                self.dismiss_overlays(preserve_share_modal=True)
                self.random_delay(1, 2)
                if self._handle_post_upload_buttons():
                    logging.info("Successfully processed post-upload buttons")
                    self.dismiss_overlays(preserve_share_modal=True)
                    return True
                else:
                    logging.info("No post-upload buttons found, continuing anyway")
                    return True
            except Exception as e:
                logging.error(f"Failed to upload images: {e}", exc_info=True)
                return False
        except Exception as e:
            logging.error(f"Error during image upload process: {e}", exc_info=True)
            return False

    def _find_photo_button(self) -> Optional[WebElement]:
        """Locate the button that opens the media selector within the composer.

        Why:
            Different LinkedIn variants expose various selectors; this helper
            encapsulates them all.

        When:
            Called before attempting file uploads.

        How:
            Searches both global and modal-scoped selectors, returning the first
            enabled button.

        Returns:
            WebElement | None: Media button if found, otherwise ``None``.
        """
        photo_button_selectors = MediaSelectors.PHOTO_BUTTONS
        modal_photo_button_selectors = MediaSelectors.MODAL_PHOTO_BUTTONS
        all_selectors = modal_photo_button_selectors + photo_button_selectors
        composer_roots = MediaSelectors.COMPOSER_ROOTS
        composer = None
        for root in composer_roots:
            try:
                composer = WebDriverWait(self.driver, config.ELEMENT_TIMEOUT).until(
                    EC.presence_of_element_located((By.XPATH, root))
                )
                break
            except Exception:
                continue
        for selector in all_selectors:
            try:
                if selector.startswith("//") and composer is not None:
                    button = composer.find_element(By.XPATH, "." + selector[1:])
                    if button.is_enabled() and button.is_displayed():
                        logging.info(
                            f"Found photo button (scoped) with selector: {selector}"
                        )
                        return button
                else:
                    selector_type = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
                    button = WebDriverWait(self.driver, config.ELEMENT_TIMEOUT).until(
                        EC.element_to_be_clickable((selector_type, selector))
                    )
                    logging.info(f"Found photo button with selector: {selector}")
                    return button
            except Exception as e:
                logging.info(f"Photo button selector {selector} not found: {e}")
        logging.error("Could not find any photo upload button in composer")
        return None

    def _find_file_input(self) -> Optional[WebElement]:
        """Discover the hidden file input backing LinkedIn's media uploader.

        Why:
            Selenium cannot interact with native dialogs; we must send file paths
            directly to the hidden input.

        When:
            Invoked before sending image paths.

        How:
            Searches modal roots for input elements using a series of selectors
            and returns the first match.

        Returns:
            WebElement | None: File input element if located.
        """
        logging.info("Finding file input element...")
        modal_roots = MediaSelectors.MODAL_ROOTS
        modal = None
        for root in modal_roots:
            try:
                modal = WebDriverWait(self.driver, config.ELEMENT_TIMEOUT).until(
                    EC.presence_of_element_located((By.XPATH, root))
                )
                break
            except Exception:
                continue
        file_input_selectors = MediaSelectors.FILE_INPUTS
        for selector in file_input_selectors:
            selector_type = By.CSS_SELECTOR if not selector.startswith("//") else By.XPATH
            try:
                logging.info(f"Trying file input selector: {selector}")
                if modal is not None and selector.startswith("//"):
                    candidate = modal.find_element(By.XPATH, "." + selector[1:])
                else:
                    candidate = WebDriverWait(self.driver, config.SHORT_TIMEOUT).until(
                        EC.presence_of_element_located((selector_type, selector))
                    )
                try:
                    self.driver.execute_script(
                        "arguments[0].classList.remove('visually-hidden'); arguments[0].disabled=false; arguments[0].style.cssText='display:block!important;visibility:visible!important;opacity:1!important;position:static!important;width:1px;height:1px';",
                        candidate,
                    )
                except Exception:
                    pass
                logging.info(f"Found file input element with selector: {selector}")
                return candidate
            except Exception as e:
                logging.info(f"File input selector {selector} failed: {e}")
        try:
            logging.info("Trying to resolve file input via label 'Upload from computer'")
            label = None
            if modal is not None:
                try:
                    label = modal.find_element(
                        By.XPATH, MediaSelectors.UPLOAD_LABEL
                    )
                except Exception:
                    label = None
            if not label:
                label = self.driver.find_element(
                    By.XPATH, MediaSelectors.UPLOAD_LABEL
                )
            input_id = label.get_attribute("for")
            if input_id:
                by_id_xpath = f"//input[@id='{input_id}']"
                logging.info(f"Resolved input id via label: {input_id}")
                if modal is not None:
                    candidate = modal.find_element(By.XPATH, "." + by_id_xpath[1:])
                else:
                    candidate = self.driver.find_element(By.XPATH, by_id_xpath)
                try:
                    self.driver.execute_script(
                        "arguments[0].classList.remove('visually-hidden'); arguments[0].disabled=false; arguments[0].style.cssText='display:block!important;visibility:visible!important;opacity:1!important;position:static!important;width:1px;height:1px';",
                        candidate,
                    )
                except Exception:
                    pass
                return candidate
        except Exception as e:
            logging.info(f"Label resolution failed: {e}")
        logging.info("Trying JavaScript to reveal hidden file input...")
        try:
            js_to_reveal_file_inputs = """
            let fileInput = document.getElementById('media-editor-file-selector__file-input');
            if (!fileInput) {
                const fileInputs = Array.from(document.querySelectorAll('input[type="file"]'));
                fileInputs.forEach(input => {
                    input.style.cssText = 'display: block !important; visibility: visible !important; opacity: 1 !important; position: static !important;';
                    input.disabled = false;
                    input.classList.remove('visually-hidden');
                    let parent = input.parentElement;
                    for (let i = 0; i < 5 && parent; i++) {
                        parent.style.cssText = 'display: block !important; visibility: visible !important; opacity: 1 !important;';
                        parent = parent.parentElement;
                    }
                });
                fileInput = fileInputs[0];
            } else {
                fileInput.style.cssText = 'display: block !important; visibility: visible !important; opacity: 1 !important; position: static !important;';
                fileInput.classList.remove('visually-hidden');
                fileInput.disabled = false;
            }
            return fileInput ? true : false;
            """
            self.driver.execute_script(js_to_reveal_file_inputs)
            logging.info("JavaScript executed to reveal hidden file inputs")
            for selector in file_input_selectors:
                selector_type = By.CSS_SELECTOR if not selector.startswith("//") else By.XPATH
                try:
                    logging.info(f"Trying file input selector after JS reveal: {selector}")
                    file_input = WebDriverWait(self.driver, config.SHORT_TIMEOUT).until(
                        EC.presence_of_element_located((selector_type, selector))
                    )
                    logging.info(
                        f"Found file input element after JS reveal with selector: {selector}"
                    )
                    return file_input
                except Exception:
                    continue
            logging.info("No file input found after JavaScript reveal")
        except Exception as e:
            logging.warning(f"Error executing JavaScript to reveal file inputs: {e}")
        try:
            logging.info("Searching shadow roots for file inputs")
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
            inputs = self.driver.execute_script(deep_search_js) or []
            logging.info(f"Deep search found {len(inputs)} candidate file inputs")
            for idx, candidate in enumerate(inputs):
                try:
                    acc = (candidate.get_attribute('accept') or '').lower()
                    cls = candidate.get_attribute('class') or ''
                    idv = candidate.get_attribute('id') or ''
                    if ('image' in acc) or (not acc):
                        self.driver.execute_script(
                            "arguments[0].style.cssText='display:block!important;visibility:visible!important;opacity:1!important;position:static!important;width:1px;height:1px';",
                            candidate,
                        )
                        logging.info(
                            f"Using shadow file input candidate idx={idx} id='{idv}' class='{cls}' accept='{acc}'"
                        )
                        return candidate
                except Exception:
                    continue
        except Exception as e:
            logging.info(f"Deep shadow search failed: {e}")
        try:
            logging.info("Scanning iframes for file input")
            frames = self.driver.find_elements(By.TAG_NAME, "iframe")
            for i, frame in enumerate(frames):
                try:
                    self.driver.switch_to.frame(frame)
                    logging.info(f"Switched to iframe index {i}")
                    for selector in MediaSelectors.IFRAME_INPUTS:
                        try:
                            by = By.CSS_SELECTOR if not selector.startswith("//") else By.XPATH
                            fi = WebDriverWait(self.driver, 2).until(
                                EC.presence_of_element_located((by, selector))
                            )
                            self.driver.execute_script(
                                "arguments[0].style.cssText='display:block!important;visibility:visible!important;opacity:1!important;position:static!important;width:1px;height:1px';",
                                fi,
                            )
                            logging.info(
                                f"Found file input in iframe index {i} using selector {selector}"
                            )
                            return fi
                        except Exception:
                            continue
                except Exception as e:
                    logging.debug(f"Error scanning iframe {i}: {e}")
                finally:
                    try:
                        self.driver.switch_to.default_content()
                    except Exception:
                        pass
        except Exception as e:
            logging.info(f"Iframe scan failed: {e}")
        logging.info("Creating a new file input element as a last resort")
        try:
            create_input_js = """
            const newInput = document.createElement('input');
            newInput.type = 'file';
            newInput.id = 'linkedin-bot-file-input';
            newInput.style.cssText = 'position: fixed; top: 0; left: 0; display: block !important; z-index: 9999;';
            document.body.appendChild(newInput);
            return true;
            """
            self.driver.execute_script(create_input_js)
            try:
                file_input = WebDriverWait(self.driver, config.SHORT_TIMEOUT).until(
                    EC.presence_of_element_located((By.ID, "linkedin-bot-file-input"))
                )
                logging.info("Successfully created and found new file input element")
                return file_input
            except Exception as e:
                logging.error(f"Could not find created file input: {e}")
        except Exception as e:
            logging.error(f"Error creating new file input: {e}")
        logging.error("All attempts to find or create file input element failed")
        return None

    def _handle_post_upload_buttons(self) -> bool:
        """Click follow-up buttons shown after media uploads.

        Why:
            The media modal may require confirmation (e.g., "Done" or "Next")
            to finalise attachments.

        When:
            Invoked after detecting preview thumbnails for uploaded media.

        How:
            Iterates through selector variants to locate actionable buttons,
            clicks them using fallback strategies, and logs failures silently.

        Returns:
            bool: ``True`` if a button was handled or none were required.
        """
        buttons_selectors = MediaSelectors.POST_UPLOAD_BUTTONS
        for selector in buttons_selectors:
            try:
                selector_type = By.CSS_SELECTOR if not selector.startswith("//") else By.XPATH
                next_button = WebDriverWait(self.driver, config.ELEMENT_TIMEOUT).until(
                    EC.element_to_be_clickable((selector_type, selector))
                )
                self.random_delay()
                logging.info(f"Found post-upload button with selector: {selector}")
                self._click_element_with_fallback(next_button, f"post-upload button ({selector})")
                self.random_delay(1, 2)
                return True
            except Exception as e:
                logging.debug(f"Post-upload button selector {selector} not found: {e}")
        try:
            WebDriverWait(self.driver, config.SHORT_TIMEOUT).until(
                EC.presence_of_element_located((By.XPATH, MediaSelectors.BACK_BUTTON))
            )
            logging.info("Found 'Back' button, which suggests we're in the post-upload flow")
            return True
        except Exception:
            pass
        return False

"""Automate the LinkedIn post composer, its schedule modal and submission.

WHY
  Hide the brittle composer interactions behind one workflow, so a caller can
  publish a post without driving each button and dialog itself.
"""

import logging
import platform
from typing import Iterable, Optional

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from laf.config import Config
from laf.errors import ComposerError, PostError, ScheduleError
from laf.selectors.composer import ComposerSelectors

from ..ui import UiActions
from .media import MediaService
from .mentions import MentionService
from .overlays import OverlayService
from .verify import VerifyService

logger = logging.getLogger(__name__)

class ComposerService:
    """Publish a LinkedIn post through the composer modal.

    WHY
      Turn opening the composer, writing the post and submitting it into one
      call that reports success or failure.
    """

    def __init__(
        self,
        ui: UiActions,
        config: Config,
        overlays: OverlayService,
        media: MediaService,
        mentions: MentionService,
        verify: VerifyService,
    ) -> None:
        """
        WHY
          Give the posting flow its driver, settings, overlay cleanup, media,
          mention and verification partners in one constructor so the composer
          reads as one workflow instead of a pile of mixins.

        Args
          ui: UiActions, the shared Selenium action helper.
          config: Config, the frozen runtime settings.
          overlays: OverlayService, used to clear dialogs around the composer.
          media: MediaService, used to attach images.
          mentions: MentionService, used to insert mention entities.
          verify: VerifyService, used to confirm the post reached the feed.

        MUTATIONS
          Stores the driver, settings and the four partner services on the
          instance.
        """
        self.ui = ui
        self.config = config
        self.overlays = overlays
        self.media = media
        self.mentions = mentions
        self.verify = verify

    def post_to_linkedin(
        self,
        post_text: str,
        image_paths: Optional[Iterable[str]] = None,
        mentions: Optional[Iterable[str]] = None,
        schedule_date: Optional[str] = None,
        schedule_time: Optional[str] = None,
    ) -> None:
        """Publish one post, with optional images, mentions and a schedule.

        WHY
          Let a caller hand over content and get one call that either finishes
          the post or names the step that stopped it.

        Args
          post_text: str, the body to publish.
          image_paths: Optional[Iterable[str]], the images to attach, or None.
          mentions: Optional[Iterable[str]], the names to add as entities, or None.
          schedule_date: Optional[str], the schedule date, or None to post now.
          schedule_time: Optional[str], the schedule time, or None to post now.

        Raises
          ValueError: when post_text is empty, which is a caller bug.
          ComposerError: when the composer, its editor or a schedule control was
            not found, or the composer click was rejected.
          PostError: when the text could not be written, the Post button could
            not be clicked, or the browser failed during the post.
          ScheduleError: when the schedule modal is missing one of its controls.
        """
        if not post_text:
            raise ValueError("post_text must not be empty")

        try:
            self._open_composer()
            post_area = self._focus_editor()
            self._write_post_text(post_area, post_text)
            self.ui.pause()
            self._refocus_editor(post_area)
            self._insert_mentions(post_area, mentions)
            self._upload_images(image_paths)
            self.ui.pause()
            if schedule_date and schedule_time:
                self._schedule_post(schedule_date, schedule_time)
                self.ui.pause(1, 2)
                logger.info("Post scheduled successfully; the confirm click submitted it.")
                return

            self._submit_post()
            self.ui.pause(5, 8)
            self._report_post_result(post_text)
        except WebDriverException as error:
            logger.debug("The composer hit a browser error: %s", error)
            raise PostError("POST_BROWSER_FAILED") from error

    def _open_composer(self) -> None:
        """Load the feed and click the control that opens the composer.

        WHY
          Every posting path needs the composer modal open before it can write
          or submit, and this keeps the navigation and first click together.

        Raises
          ComposerError: COMPOSER_NOT_OPEN when the start control is missing or
            its click was rejected.
        """
        logger.info("Posting to LinkedIn.")
        self.ui.driver.get(self.config.linkedin_feed_url)
        self.ui.pause(self.config.min_page_load_delay, self.config.max_page_load_delay)
        self.overlays.dismiss_overlays()
        start_post_button = self._find_start_post_button()
        if not start_post_button:
            logger.debug("The 'Start a post' control was not found.")
            raise ComposerError("COMPOSER_NOT_OPEN")
        if not self.ui.click_with_fallback(start_post_button, "Start a post"):
            raise ComposerError("COMPOSER_NOT_OPEN")
        self.ui.pause(2, 3)

    def _focus_editor(self) -> WebElement:
        """Find the composer editor and click it to give it focus.

        WHY
          Typing only reaches the post body once the editor has focus, and a
          missing editor must stop the flow before any text is lost.

        Returns
          WebElement, the focused editor.

        Raises
          ComposerError: COMPOSER_EDITOR_MISSING when no editor was found.
        """
        post_area = self._find_post_editor()
        if not post_area:
            logger.debug("The composer text box was not found.")
            raise ComposerError("COMPOSER_EDITOR_MISSING")
        self._click_editor_to_focus(post_area)
        self.ui.pause()
        return post_area

    def _click_editor_to_focus(self, post_area: WebElement) -> None:
        """Click the editor and warn when focus did not take.

        WHY
          A failed focus click should not stop the post, so it warns and lets
          the next step try anyway, as the composer always has.

        Args
          post_area: WebElement, the editor element to click.
        """
        if not self.ui.click_with_fallback(post_area, "post editor"):
            logger.warning("Failed to focus editor, trying to continue anyway")

    def _write_post_text(self, post_area: WebElement, post_text: str) -> None:
        """Write the body, using the mention path when the text has mentions.

        WHY
          Inline mentions need their own composer call, and picking the path
          here keeps the caller free of that branch.

        Args
          post_area: WebElement, the focused editor.
          post_text: str, the body to write.

        Raises
          PostError: POST_TEXT_FAILED when the chosen path could not write the
            text into the editor.
        """
        if self.mentions.post_text_contains_inline_mentions(post_text):
            written = self.mentions.compose_text_with_mentions(post_area, post_text)
        else:
            written = self._set_post_text(post_area, post_text)
        if not written:
            logger.debug("The post text was not written into the editor.")
            raise PostError("POST_TEXT_FAILED")

    def _refocus_editor(self, post_area: WebElement) -> None:
        """Click the editor again before mentions are inserted.

        WHY
          Inserting mentions needs the editor focused, and the earlier write
          may have dropped focus on some layouts.

        Args
          post_area: WebElement, the editor element to click.
        """
        self._click_editor_to_focus(post_area)

    def _insert_mentions(self, post_area: WebElement, mentions: Optional[Iterable[str]]) -> None:
        """Insert the requested mentions, warning when any of them fails.

        WHY
          A failed mention should not lose the whole post, so it warns and the
          post continues without that entity.

        Args
          post_area: WebElement, the focused editor.
          mentions: Optional[Iterable[str]], the names to insert, or None.
        """
        if not mentions:
            return
        try:
            self.mentions.insert_mentions(post_area, mentions)
        except WebDriverException as mention_e:
            logger.warning(f"Failed to insert one or more mentions: {mention_e}")

    def _upload_images(self, image_paths: Optional[Iterable[str]]) -> None:
        """Attach the images, warning when the upload fails.

        WHY
          A failed upload should still leave a text-only post, so it warns and
          continues instead of returning False.

        Args
          image_paths: Optional[Iterable[str]], the images to attach, or None.
        """
        if not image_paths:
            return
        if not self.media.upload_images_to_post(image_paths):
            logger.warning("Image upload failed, continuing with text-only post")

    def _submit_post(self) -> None:
        """Submit the composed post through the Post button or its fallbacks.

        WHY
          LinkedIn's Post button can move or be blocked, so this tries the
          button, the keyboard shortcut and a scripted click in that order.

        Raises
          ComposerError: COMPOSER_POST_BUTTON_MISSING when no Post button was
            found.
          PostError: POST_BUTTON_UNCLICKABLE when the button was found but every
            click path failed.
        """
        post_button = self._find_post_button()
        if not post_button:
            logger.debug("The Post button was not found.")
            raise ComposerError("COMPOSER_POST_BUTTON_MISSING")
        self.overlays.dismiss_overlays(preserve_share_modal=True)
        self.ui.pause(1, 2)
        if self._click_post_button():
            return
        logger.info("Trying keyboard submit (Ctrl/Cmd + Enter)")
        if self._submit_via_keyboard():
            return
        logger.info("Trying JS-based Post button click")
        if self._click_post_via_js():
            return
        logger.debug("Every click path for the Post button failed.")
        raise PostError("POST_BUTTON_UNCLICKABLE")

    def _click_post_button(self) -> bool:
        """Click the Post button, retrying a few times when the click misses.

        WHY
          The footer button can appear while the modal is still moving, so a
          lost click is retried after scrolling it back into view.

        Returns
          bool, True when a click was accepted, False after both retries fail.
        """
        post_button = self._find_post_button()
        if post_button and self.ui.click_with_fallback(post_button, "Post"):
            return True
        logger.info("Re-locating 'Post' button after click failure and retrying")
        for _ in range(2):
            self.ui.pause(1, 2)
            post_button = self._find_post_button()
            if not post_button:
                continue
            try:
                self.ui.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", post_button
                )
            except WebDriverException:
                logger.debug("Could not scroll the Post button into view")
            if self.ui.click_with_fallback(post_button, "Post"):
                return True
        return False

    def _report_post_result(self, post_text: str) -> None:
        """Log whether the success indicator appeared, then stop.

        WHY
          The post is already submitted at this point, so both outcomes are a
          finished post and only the log line differs.

        Args
          post_text: str, the body that was posted, for the success check.
        """
        if self.verify.verify_post_success(post_text):
            logger.info("Successfully posted to LinkedIn - confirmed by success indicator.")
        else:
            logger.info(
                "Posted to LinkedIn but could not verify success indicator. Assuming success."
            )

    def _schedule_post(self, date_str: str, time_str: str) -> None:
        """Fill the schedule modal and confirm it.

        WHY
          Schedule a post for a later time without a person touching the date
          and time inputs.

        Args
          date_str: str, the date text from post_to_linkedin, in LinkedIn's format.
          time_str: str, the time text from post_to_linkedin, in LinkedIn's format.

        Raises
          ValueError: when either the date or the time is empty, which is a
            caller bug because post_to_linkedin only calls this with both set.
          ScheduleError: SCHEDULE_CONTROL_MISSING when the schedule button, an
            input or the confirm button was not found.
        """
        if not date_str or not time_str:
            raise ValueError("both schedule_date and schedule_time are required")

        self._open_schedule_modal()
        self._fill_schedule_date(date_str)
        self._fill_schedule_time(time_str)
        self._click_schedule_confirm()

    def _open_schedule_modal(self) -> None:
        """Click the composer button that opens the schedule modal.

        WHY
          The date and time inputs only exist after the modal opens, and a
          missing button must stop the flow before any lookup waits.

        Raises
          ScheduleError: SCHEDULE_CONTROL_MISSING when the button is missing or
            its click was rejected.
        """
        schedule_btn_selectors = ComposerSelectors.SCHEDULE_BUTTONS
        btn = None
        for xp in schedule_btn_selectors:
            try:
                btn = self.ui.driver.find_element(By.XPATH, xp)
                if btn and btn.is_displayed():
                    break
            except WebDriverException:
                logger.debug(f"Schedule button selector not found: {xp}")
                continue
        if not btn:
            logger.debug("Schedule button not found in composer")
            raise ScheduleError("SCHEDULE_CONTROL_MISSING", control="schedule button")
        if not self.ui.click_with_fallback(btn, "Schedule post"):
            raise ScheduleError("SCHEDULE_CONTROL_MISSING", control="schedule button")
        self.ui.pause(0.8, 1.4)

    def _fill_schedule_date(self, date_str: str) -> None:
        """Find the schedule date input and type the date into it.

        WHY
          The date field must be cleared and filled before Confirm accepts the
          schedule, and a missing field must end the flow.

        Args
          date_str: str, the date text from post_to_linkedin.

        Raises
          ScheduleError: SCHEDULE_CONTROL_MISSING when no date input was found.
        """
        date_input = None
        for sel in ComposerSelectors.SCHEDULE_DATE_INPUTS:
            try:
                date_input = WebDriverWait(self.ui.driver, 6).until(
                    EC.presence_of_element_located((By.XPATH, sel))
                )
                if date_input:
                    break
            except WebDriverException:
                logger.debug(f"Schedule date input selector not found: {sel}")
                continue
        if not date_input:
            logger.debug("Schedule modal: date input not found")
            raise ScheduleError("SCHEDULE_CONTROL_MISSING", control="date input")
        try:
            date_input.clear()
        except WebDriverException:
            logger.debug("Could not clear the schedule date input")
        date_input.send_keys(date_str)
        self.ui.pause(0.2, 0.4)

    def _fill_schedule_time(self, time_str: str) -> None:
        """Find the schedule time input and type the time into it.

        WHY
          The time field must be cleared and filled, then left with Tab, before
          Confirm accepts the schedule.

        Args
          time_str: str, the time text from post_to_linkedin.

        Raises
          ScheduleError: SCHEDULE_CONTROL_MISSING when no time input was found.
        """
        time_input = None
        for sel in ComposerSelectors.SCHEDULE_TIME_INPUTS:
            try:
                time_input = WebDriverWait(self.ui.driver, 6).until(
                    EC.presence_of_element_located((By.XPATH, sel))
                )
                if time_input:
                    break
            except WebDriverException:
                logger.debug(f"Schedule time input selector not found: {sel}")
                continue
        if not time_input:
            logger.debug("Schedule modal: time input not found")
            raise ScheduleError("SCHEDULE_CONTROL_MISSING", control="time input")
        try:
            time_input.clear()
        except WebDriverException:
            logger.debug("Could not clear the schedule time input")
        time_input.send_keys(time_str)
        time_input.send_keys(Keys.TAB)
        self.ui.pause(0.5, 1.0)

    def _click_schedule_confirm(self) -> None:
        """Click the button that confirms a scheduled post.

        WHY
          The confirm click is what submits the scheduled post, so a missed
          click would leave the composer open and the post unscheduled.

        Raises
          ScheduleError: SCHEDULE_CONTROL_MISSING when no confirmation button
            was found.
        """
        for xp in ComposerSelectors.SCHEDULE_CONFIRM_BUTTONS:
            try:
                btn = WebDriverWait(self.ui.driver, 6).until(
                    EC.element_to_be_clickable((By.XPATH, xp))
                )
                if btn and self.ui.click_with_fallback(btn, "Confirm Schedule"):
                    return
            except WebDriverException:
                logger.debug(f"Schedule confirm selector not found: {xp}")
                continue
        logger.debug("Schedule modal: confirm button not found")
        raise ScheduleError("SCHEDULE_CONTROL_MISSING", control="confirm button")

    def _find_start_post_button(self) -> Optional[WebElement]:
        """Find the control that opens the post composer.

        WHY
          The start control moves between DOM variants, and trying each known
          selector keeps the composer from failing on one layout.

        Returns
          Optional[WebElement], the first clickable start button, or None when
          no selector matched.
        """
        start_post_selectors = ComposerSelectors.START_POST_TRIGGERS
        for selector in start_post_selectors:
            try:
                logger.info(f"Trying post button selector: {selector}")
                button = WebDriverWait(self.ui.driver, self.config.short_timeout).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                if button:
                    logger.info(f"Found post button with selector: {selector}")
                    return button
            except WebDriverException as e:
                logger.info(f"Selector {selector} not found: {e.msg}")
        return None

    def _find_post_editor(self) -> Optional[WebElement]:
        """Find the contenteditable editor inside the open composer.

        WHY
          The editor markup changes often, so callers need one element to type
          into without knowing which selector won.

        Returns
          Optional[WebElement], the first matching editor, or None when the
          composer shows no known editor node.
        """
        editor_selectors = ComposerSelectors.POST_EDITOR
        for selector in editor_selectors:
            try:
                logger.info(f"Trying editor selector: {selector}")
                editor = WebDriverWait(self.ui.driver, self.config.short_timeout).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                if editor:
                    logger.info(f"Found post editor with selector: {selector}")
                    return editor
            except WebDriverException as e:
                logger.info(f"Editor selector {selector} not found: {e.msg}")
        return None

    def _find_post_button(self) -> Optional[WebElement]:
        """Find the button that submits the composer.

        WHY
          The submit button changes label and class between LinkedIn tests, so
          the selector list tries the stable data attribute first and the
          visible text after it.

        Returns
          Optional[WebElement], the first clickable submit button, or None when
          no candidate matched.
        """
        for selector in ComposerSelectors.POST_BUTTON:
            try:
                logger.info(f"Trying post button selector: {selector}")
                button = WebDriverWait(self.ui.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                if button:
                    logger.info(f"Found post button with selector: {selector}")
                    return button
            except WebDriverException as e:
                logger.info(f"Post button selector {selector} not found: {e.msg}")
        return None

    def _submit_via_keyboard(self) -> bool:
        """Submit the post with the platform's Ctrl or Cmd plus Enter shortcut.

        WHY
          Give a fallback path when the Post button is covered or ignores a
          click.

        Returns
          bool, True when the keystrokes were sent, False when sending raised.
        """
        try:
            actions = ActionChains(self.ui.driver)
            if platform.system() == "Darwin":
                actions.key_down(Keys.COMMAND)
            else:
                actions.key_down(Keys.CONTROL)
            actions.send_keys(Keys.ENTER).key_up(
                Keys.COMMAND if platform.system() == "Darwin" else Keys.CONTROL
            ).perform()
            self.ui.pause(1, 2)
            return True
        except WebDriverException as e:
            logger.info(f"Keyboard submit failed: {e.msg}")
            return False

    def _click_post_via_js(self) -> bool:
        """Click the Post button from JavaScript as a last resort.

        WHY
          Some experimental UIs block a native click, and a scripted click still
          gets the post out.

        Returns
          bool, True when the script reports that it clicked a button, False
          when the script failed or found nothing.
        """
        try:
            js = """
                const direct = document.querySelector('[data-view-name="share-post"]');
                if (direct && !direct.disabled) { direct.click(); return true; }
                const candidates = Array.from(document.querySelectorAll('button'));
                const isPost = (el) => (el.innerText || '').trim().toLowerCase() === 'post';
                for (const el of candidates) {
                  if (isPost(el) && !el.disabled) { el.click(); return true; }
                }
                return false;
            """
            clicked = self.ui.driver.execute_script(js)
            return bool(clicked)
        except WebDriverException as e:
            logger.info(f"JS post click failed: {e.msg}")
            return False

    def _set_post_text(self, post_area: WebElement, post_text: str) -> bool:
        """Write text into the composer editor, with a JavaScript fallback.

        WHY
          Native typing can fail when the editor loses focus, and the fallback
          keeps the post body from being lost.

        Args
          post_area: WebElement, the editor element from the opened composer.
          post_text: str, the body to write.

        Returns
          bool, True when either method wrote the text, False when both failed
          or post_area is not a WebElement.
        """
        if not isinstance(post_area, WebElement):
            return False
        if post_text is None:
            post_text = ""

        try:
            post_area.send_keys(post_text)
            logger.info("Sent text to editor using send_keys")
            return True
        except WebDriverException as e:
            logger.info(f"Standard send_keys failed: {e.msg}")
            try:
                cleaned_text = (
                    post_text.replace('"', '\\"').replace("'", "\\'").replace("\n", "\\n")
                )
                self.ui.driver.execute_script(
                    f'arguments[0].innerHTML = "{cleaned_text}";', post_area
                )
                logger.info("Set text using JavaScript")
                return True
            except WebDriverException as js_e:
                logger.error(f"Failed to set post text: {js_e}")
                return False

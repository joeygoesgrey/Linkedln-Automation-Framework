"""Selectors for uploading media and interacting with the media tray.

WHY
  Serve the media upload path, so the file input and tray selectors can change
  apart from the composer that opens them.
"""


class MediaSelectors:
    """Selectors for uploading media and interacting with the media tray.

    WHY
      Serve the photo button, file input and upload controls, so a media tray
      change has one file to update.
    """

    PHOTO_BUTTONS = [
        "button.share-box-feed-entry-toolbar__item[aria-label='Add a photo']",
        "button.image-detour-btn",
        "button[aria-label='Add a photo']",
        "//button[contains(@aria-label, 'photo')]",
        "//button[contains(@title, 'Add a photo')]",
        "//button[contains(@aria-label, 'Add to your post')]",
    ]  # linkedin_ui/media.py:148

    MODAL_PHOTO_BUTTONS = [
        "button[aria-label*='Add media']",
        "//button[contains(@aria-label, 'Add media')]",
        "//button[contains(normalize-space(.), 'Add media')]",
        "button.share-promoted-detour-button[aria-label='Add media']",
        (
            "//button[.//span[contains(@class, "
            "'share-promoted-detour-button__icon-container')]//*"
            "[contains(@data-test-icon, 'image-medium')]]"
        ),
        (
            "//li[contains(@class, 'artdeco-carousel__item')]//button"
            "[.//svg[contains(@data-test-icon, 'image')]]"
        ),
        ".share-creation-state__promoted-detour-button-item button",
        "//button[.//svg[contains(@data-test-icon, 'image')]]",
        "//button[.//*[local-name()='svg' and contains(@data-test-icon,'image')]]",
    ]  # linkedin_ui/media.py:156

    MODAL_ROOTS = [
        "//div[@role='dialog' and contains(@class,'share-box-v2__modal')]",
        "//div[@role='dialog' and contains(@class,'share-box-modal')]",
        "//div[contains(@class,'media-editor__container')]/ancestor::div[@role='dialog']",
    ]  # linkedin_ui/media.py:222

    FILE_INPUTS = [
        "#media-editor-file-selector__file-input",
        "input.media-editor-file-selector__upload-media-input",
        "input#media-editor-file-selector__file-input",
        "input[id='media-editor-file-selector__file-input']",
        "//input[@id='media-editor-file-selector__file-input']",
        "//input[contains(@class, 'media-editor-file-selector__upload-media-input')]",
        (
            "//div[contains(@class,'share') or contains(@class,'media') or "
            "contains(@class,'editor')]//input[@type='file']"
        ),
        "input[type='file']",
        "//input[@type='file']",
        "//div[contains(@class, 'share-box')]//input[@type='file']",
        "//div[contains(@class, 'share-creation-state')]//input[@type='file']",
        "//div[contains(@class, 'image-selector')]//input[@type='file']",
    ]  # linkedin_ui/media.py:236

    UPLOAD_LABEL = (
        "//label[contains(normalize-space(.), 'Upload from computer')]"  # linkedin_ui/media.py:288
    )

    PREVIEWS = [
        (
            "//div[contains(@class,'image') or contains(@class,'media') or "
            "contains(@class,'preview')]//img"
        ),
        "//div[contains(@class,'media-editor')]//img",
        "//img[contains(@src,'data:') or contains(@src,'media')]",
    ]  # linkedin_ui/media.py:94

    IFRAME_INPUTS = ["input[type='file']", "//input[@type='file']"]  # linkedin_ui/media.py:395

    POST_UPLOAD_BUTTONS = [
        "button.share-box-footer__primary-btn:not([disabled])",
        "button.artdeco-button--primary:not([disabled])",
        "button[aria-label='Next']",
        "button[aria-label='Done']",
        "button[aria-label='Add']",
        "button.media-editor-toolbar__submit-button",
        "//button[contains(text(),'Next')]",
        "//button[contains(text(),'Done')]",
        "//button[contains(text(),'Add')]",
        "//button[contains(@class, 'share-creation-state__submit')]",
        (
            "//div[contains(@class, 'share-box-footer')]//button"
            "[contains(@class, 'artdeco-button--primary')]"
        ),
    ]  # linkedin_ui/media.py:461

    BACK_BUTTON = "//button[contains(text(),'Back')]"  # linkedin_ui/media.py:489

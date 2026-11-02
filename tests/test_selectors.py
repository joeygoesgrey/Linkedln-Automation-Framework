"""Tests for the per-page selector modules.

Why:
    The split only works if every class moved, no class stayed in the package,
    and no selector text changed shape or picked up an em dash.
"""

import importlib
from typing import Iterator

from selenium.webdriver.common.by import By

CLASS_LOCATIONS = [
    ("laf.selectors.login", "LoginSelectors"),
    ("laf.selectors.verify", "VerifySelectors"),
    ("laf.selectors.overlays", "OverlaySelectors"),
    ("laf.selectors.composer", "ComposerSelectors"),
    ("laf.selectors.media", "MediaSelectors"),
    ("laf.selectors.mentions", "MentionSelectors"),
    ("laf.selectors.feed", "PostExtractorSelectors"),
    ("laf.selectors.feed", "FeedActionSelectors"),
    ("laf.selectors.engage", "EngageSelectors"),
    ("laf.selectors.profile", "ProfileSelectors"),
]

VALID_BY = {
    value
    for name, value in vars(By).items()
    if not name.startswith("_") and isinstance(value, str)
}


def iter_attributes(selector_class: type) -> Iterator[tuple[str, object]]:
    """
    WHY
        Walk every selector attribute of a class so the checks below run on all
        of them, including classes that hold an empty list.

    Args
        selector_class: type, a selector class taken from CLASS_LOCATIONS.

    Returns
        Iterator[tuple[str, object]]: attribute name and raw value pairs.
    """
    for name, value in vars(selector_class).items():
        if name.startswith("__"):
            continue
        yield name, value


def iter_locators(value: object) -> Iterator[object]:
    """
    WHY
        A selector attribute may be a bare string, a list of strings, a list
        with (By, str) tuples, or a tuple that holds several locator strings.
        This flattens all of those shapes so one check covers each one.

    Args
        value: object, the raw value of a selector attribute.

    Returns
        Iterator[object]: each locator, which is a string or a tuple.
    """
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, tuple) and len(value) == 2 and value[0] in VALID_BY:
        yield value
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield item


def iter_strings(value: object) -> Iterator[str]:
    """
    WHY
        The em dash check has to reach strings inside lists and tuples, not only
        top level attributes.

    Args
        value: object, any selector value.

    Returns
        Iterator[str]: every string found in the value.
    """
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from iter_strings(item)


def test_every_class_imports_from_its_module() -> None:
    """
    WHY
        A class left behind in the old package would still pass an import test
        that only checked the attrs exist, so this checks the module too.
    """
    for module_name, class_name in CLASS_LOCATIONS:
        module = importlib.import_module(module_name)
        selector_class = getattr(module, class_name)
        assert selector_class.__module__ == module_name


def test_no_selector_class_left_in_the_package() -> None:
    """
    WHY
        Re-exporting the classes from ``laf.selectors`` would hide the new
        layout and let old imports keep working, which defeats the split.
    """
    package = importlib.import_module("laf.selectors")
    for _module_name, class_name in CLASS_LOCATIONS:
        assert not hasattr(package, class_name)


def test_tuple_locators_start_with_a_by_member() -> None:
    """
    WHY
        ``find_by_selectors`` reads the first tuple item as a Selenium strategy,
        so a typo there fails only at run time on the live site.
    """
    for module_name, class_name in CLASS_LOCATIONS:
        module = importlib.import_module(module_name)
        selector_class = getattr(module, class_name)
        for attribute, value in iter_attributes(selector_class):
            for locator in iter_locators(value):
                if isinstance(locator, tuple):
                    assert locator[0] in VALID_BY, f"{class_name}.{attribute} has a bad By"


def test_no_selector_contains_an_em_dash() -> None:
    """
    WHY
        An em dash in a selector can come from a paste of prose and will never
        match the page, so it is worth failing fast.
    """
    for module_name, class_name in CLASS_LOCATIONS:
        module = importlib.import_module(module_name)
        selector_class = getattr(module, class_name)
        for attribute, value in iter_attributes(selector_class):
            for text in iter_strings(value):
                assert chr(0x2014) not in text, (
                    f"{class_name}.{attribute} has an em dash"
                )


def test_empty_selector_list_is_accepted() -> None:
    """
    WHY
        A class that currently has no members must not make the checks crash or
        fail, because an unused feature still keeps its selectors.
    """
    assert list(iter_locators([])) == []
    assert list(iter_strings([])) == []

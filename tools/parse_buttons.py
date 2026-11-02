"""Scratch script for reading a saved LinkedIn page and printing its buttons."""

from bs4 import BeautifulSoup

with open("after_back.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

dialogs = soup.find_all(role="dialog")
for dialog in dialogs:
    print(f"--- Dialog '{dialog.get('aria-label', 'No label')}' ---")
    for btn in dialog.find_all("button"):
        label = btn.get("aria-label", "")
        classes = btn.get("class", [])
        print(
            f"Button: text='{btn.get_text(strip=True)}', "
            f"aria-label='{label}', class='{classes}'"
        )

    print("\n")

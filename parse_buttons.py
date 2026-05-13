from bs4 import BeautifulSoup

with open("after_back.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

dialogs = soup.find_all(role="dialog")
for dialog in dialogs:
    print(f"--- Dialog '{dialog.get('aria-label', 'No label')}' ---")
    for btn in dialog.find_all("button"):
        print(f"Button: text='{btn.get_text(strip=True)}', aria-label='{btn.get('aria-label', '')}', class='{btn.get('class', [])}'")
        
    print("\n")

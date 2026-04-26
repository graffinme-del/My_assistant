import os
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = (os.getenv("MOY_ARBITR_BASE_URL") or "https://my.arbitr.ru").rstrip("/")
STATE_PATH = os.getenv("MOY_ARBITR_STATE_PATH", "/app/moy_arbitr/state.json")
HEADLESS = os.getenv("MOY_ARBITR_LOGIN_HEADLESS", "false").lower() in ("1", "true", "yes")


def main() -> None:
    state_path = Path(STATE_PATH)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Открою {BASE_URL}. Войдите в «Мой Арбитр», затем вернитесь в терминал и нажмите Enter.")
    print(f"Storage state будет сохранён в {state_path}. Пароль/КЭП не записываются в код проекта.")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            accept_downloads=True,
            locale="ru-RU",
            viewport={"width": 1440, "height": 950},
        )
        page = context.new_page()
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=120_000)
        input("После успешного входа нажмите Enter здесь...")
        context.storage_state(path=str(state_path))
        browser.close()
    print(f"Готово: сохранена сессия «Мой Арбитр» в {state_path}")


if __name__ == "__main__":
    main()

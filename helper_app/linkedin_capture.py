"""
LinkedIn login/session-capture logic for the Helper App.

Adapted from save_session.py, with two necessary changes:
1. No terminal available, so login completion is detected automatically
   by polling the page URL instead of waiting for a keypress.
2. A page.screenshot() call is taken on each poll. This was found to be
   empirically necessary, not decorative: repeated testing showed
   page.url reliably updates to reflect a completed login only when a
   screenshot (or similar CDP round-trip) is taken each cycle - likely
   because it forces Playwright to sync pending navigation state over
   the CDP connection. The screenshot itself is discarded (written to
   one reused temp file, never kept) - only its side effect matters.
"""
import time
import tempfile
import os
from playwright.sync_api import sync_playwright  # type: ignore

LOGIN_TIMEOUT_SECONDS = 600
POLL_INTERVAL_SECONDS = 2

_TEMP_SCREENSHOT_PATH = os.path.join(tempfile.gettempdir(), "_la_poll.png")


def capture_linkedin_session() -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.linkedin.com/login")

        deadline = time.time() + LOGIN_TIMEOUT_SECONDS

        while time.time() < deadline:
            page.screenshot(path=_TEMP_SCREENSHOT_PATH)  # forces CDP sync - required, see module docstring
            if "linkedin.com/feed" in page.url:
                storage_state = context.storage_state()
                browser.close()
                return storage_state
            time.sleep(POLL_INTERVAL_SECONDS)

        browser.close()
        raise TimeoutError("LinkedIn login was not completed within the time limit.")


if __name__ == "__main__":
    result = capture_linkedin_session()
    print("Capture successful.")
    print(f"Cookies captured: {len(result.get('cookies', []))}")
    print(f"Origins captured: {len(result.get('origins', []))}")
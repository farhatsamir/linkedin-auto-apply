from playwright.sync_api import sync_playwright # type: ignore
from app.core.config import settings


class PlaywrightService:

    @staticmethod
    def start_browser(storage_state: dict):
        try:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.set_event_loop(None)
            except RuntimeError:
                pass

            playwright = sync_playwright().start()

            browser = playwright.chromium.launch(
                headless=settings.browser_headless
            )
            context = browser.new_context(storage_state=storage_state)
            page = context.new_page()

            page.wait_for_timeout(1000)
            page.goto("https://www.linkedin.com/feed/", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            if "login" in page.url or "authwall" in page.url:
                try:
                    browser.close()
                    playwright.stop()
                except:
                    pass
                return None, None, None, None, "LinkedIn session has expired. Please re-import your session."

            return browser, context, page, playwright, None

        except Exception as e:
            try:
                if 'browser' in locals() and browser:
                    browser.close()
            except:
                pass
            try:
                if 'playwright' in locals() and playwright:
                    playwright.stop()
            except:
                pass
            return None, None, None, None, str(e)

    @staticmethod
    def stop_browser(browser, context, playwright):
        try:
            if context:
                context.close()
            if browser:
                browser.close()
            if playwright:
                playwright.stop()
        except:
            pass
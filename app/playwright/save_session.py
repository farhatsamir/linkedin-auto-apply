from playwright.sync_api import sync_playwright # type: ignore

def save_linkedin_session():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        context = browser.new_context()

        page = context.new_page()

        page.goto("https://www.linkedin.com")

        print("سجّل الدخول إلى LinkedIn بالكامل.")
        print("بعد الوصول للصفحة الرئيسية، ارجع للتيرمينال واضغط Enter.")

        input()

        context.storage_state(path="session.json")

        print("تم حفظ الجلسة بنجاح!")

        browser.close()

if __name__ == "__main__":
    save_linkedin_session()

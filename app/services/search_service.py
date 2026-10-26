import time
import urllib.parse
from playwright.sync_api import Page  # type: ignore


class SearchService:

    @staticmethod
    def search(page: Page, filters: dict, limit: int):
        """
        منطق مطابق للكود القديم:
        - البحث بكلمات المستخدم
        - Scroll لجلب كل الوظائف
        - جمع روابط /jobs/view/
        - فتح كل رابط
        - فلترة Easy Apply
        - فلترة الكلمات داخل نص الوظيفة (ANY match)
        """

        # الكلمات التي نبحث عنها (من المستخدم)
        SEARCH_KEYWORDS = filters.get("keywords") or []
        
        # الكلمات التي نفلتر بها نص الوظيفة (OR logic)
        KEYWORD_FILTERS = [k.lower().strip() for k in SEARCH_KEYWORDS]

        # فلترة Easy Apply فقط؟
        EASY_APPLY_ONLY = filters.get("easy_apply_only", True)

        # الموقع
        locations = filters.get("locations", [])
        location_param = locations[0] if locations else ""

        SCROLL_PAUSE_TIME = 2
        SCROLL_TIMES = 40

        all_job_links = set()

        # ---------------------------------------------------------
        # 1) البحث في كل كلمة (نفس الكود القديم)
        # ---------------------------------------------------------
        for keyword in SEARCH_KEYWORDS:

            params = {
                "keywords": keyword,
                "location": location_param,
                "f_TPR": "r604800",  # posted within last 7 days
            }
            if EASY_APPLY_ONLY:
                params["f_LF"] = "f_AL"   # LinkedIn's native Easy Apply filter

            search_url = (
                f"https://www.linkedin.com/jobs/search/?"
                + urllib.parse.urlencode(params)
            )

            page.goto(search_url)
            time.sleep(2)

            # Scroll لتحميل الوظائف
            for _ in range(SCROLL_TIMES):
                page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                time.sleep(SCROLL_PAUSE_TIME)

            # جمع روابط الوظائف
            job_links = page.eval_on_selector_all(
                'a[href*="/jobs/view/"]',
                'elements => elements.map(e => e.href)'
            )

            # تنظيف الروابط
            cleaned_links = [link.split("?")[0] for link in job_links]

            for link in cleaned_links:
                all_job_links.add(link)

        job_links = list(all_job_links)
        # تطبيق limit
        if limit and limit > 0:
            job_links = job_links[:limit]

        # ---------------------------------------------------------
        # 2) فلترة Easy Apply + الكلمات داخل نص الوظيفة
        # ---------------------------------------------------------
        filtered_jobs = list(set(job_links))

        return filtered_jobs

from sqlalchemy.orm import Session # type: ignore
from datetime import datetime
import time

from app.services.settings_service import SettingsService
from app.services.linkedin_session_service import LinkedInSessionService
from app.services.application_service import ApplicationService
from app.services.log_service import LogService

from app.services.playwright_service import PlaywrightService
from app.services.search_service import SearchService
from app.services.apply_service import ApplyService


class AutoApplyService:

    @staticmethod
    def run_auto_apply(db: Session, user_id: int):

        # 1) تحميل الإعدادات
        settings = SettingsService.get_user_settings(db, user_id)

        if not settings.auto_apply_enabled:
            raise ValueError("Auto Apply is disabled")

        # 2) التأكد من وجود session في قاعدة البيانات
        storage_state = LinkedInSessionService.get_storage_state(db, user_id)

        # 3) حساب عدد التقديمات اليوم
        today = datetime.utcnow().date()
        applications_today = db.query(ApplicationService.model).filter(
            ApplicationService.model.user_id == user_id,
            ApplicationService.model.status == "questions_extracted",
            ApplicationService.model.created_at >= datetime(today.year, today.month, today.day)
        ).count()

        if applications_today >= settings.daily_limit:
            raise ValueError("Daily limit reached")

        # 4) تجهيز الفلاتر
        filters = {
            "keywords": [k.strip() for k in settings.keywords.split(",") if k.strip()] if settings.keywords else [],
            "locations": [l.strip() for l in settings.locations.split(",") if l.strip()] if settings.locations else [],
            "easy_apply_only": getattr(settings, "easy_apply_only", True),
        }

        # 5) تشغيل المتصفح
        browser, context, page, playwright, error = PlaywrightService.start_browser(storage_state)
        if error:
            raise ValueError(error)

        # 6) البحث عن الوظائف
        job_links = SearchService.search(
            page=page,
            filters=filters,
            limit=settings.daily_limit - applications_today
        )
        applied_count = 0

        # ⭐⭐ الإضافة الجديدة ⭐⭐
        results = []   # ← هنا سنجمع db_record + apply_result

        # 7) التقديم على كل وظيفة
        for link in job_links:

            try:
                apply_result = ApplyService.apply(page, link)
                db_record = ApplicationService.create_application(db, user_id, apply_result)

                results.append({
                    "application_id": db_record.id,
                    "status": apply_result["status"],
                    "job_title": apply_result.get("job_title"),
                    "company": apply_result.get("company"),
                    "job_link": apply_result.get("job_link"),
                    "job_description": apply_result.get("job_description"),
                    "questions": apply_result.get("questions", []),
                    "session_id": apply_result.get("session_id"),
                    "error_message": apply_result.get("error_message"),
                })

                if apply_result["status"] == "questions_extracted":
                    applied_count += 1

            except Exception as e:
                # log and continue — one failed job must not stop the entire run
                LogService.create_log(db, user_id, "error", f"Failed to process {link}: {str(e)}")
                continue

            time.sleep(1)

        # 8) إغلاق المتصفح
        # (NEW) — لا نغلق المتصفح إذا كانت هناك وظيفة واحدة على الأقل في مرحلة استخراج الأسئلة
        should_close = True

        for r in results:
            if r.get("status") == "questions_extracted":
                should_close = False
                break

        if should_close:
            try:
                context.close()
                browser.close()
                playwright.stop()  # type: ignore
            except:
                pass


        # ⭐⭐ الإضافة الجديدة — إرجاع النتائج كاملة ⭐⭐
        return {
            "message": "Auto Apply completed",
            "applied": applied_count,
            "results": results   # ← هنا تظهر الأسئلة + الوصف + كل شيء
        }

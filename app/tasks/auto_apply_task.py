"""
app/tasks/auto_apply_task.py

Full auto-apply pipeline as a Celery task.
Runs entirely in a worker process — no HTTP concerns, no shared memory.

Pipeline:
  1. Load user settings and CV summary from DB
  2. Load LinkedIn session from DB
  3. Check daily limit
  4. Open Chromium browser with user's session
  5. Search for jobs
  6. For each job: navigate → Easy Apply → ApplyLoopService.run()
  7. Save result per job to DB
  8. Update AutoApplyRun status
  9. Close browser (always, in finally)
"""
import time
from datetime import datetime
from app.services.relevance_service import score_job

from celery.utils.log import get_task_logger # type: ignore

from app.workers.celery_app import celery_app
from app.database.database import SessionLocal as SessionFactory
from app.models.auto_apply_run import AutoApplyRun
from app.models.application import Application
from app.services.settings_service import SettingsService
from app.services.linkedin_session_service import LinkedInSessionService
from app.services.application_service import ApplicationService
from app.services.log_service import LogService
from app.services.playwright_service import PlaywrightService
from app.services.search_service import SearchService
from app.services.apply_service import ApplyService
from app.services.apply_loop_service import ApplyLoopService

logger = get_task_logger(__name__)


@celery_app.task(
    bind=True,
    name="auto_apply_task",
    max_retries=0,
    time_limit=3600,      # hard kill after 1 hour
    soft_time_limit=3500, # raises SoftTimeLimitExceeded before hard kill
)
def auto_apply_task(self, user_id: int, run_id: int):
    """
    Full auto-apply pipeline for one user.
    user_id: the user to apply for
    run_id:  the AutoApplyRun record to update with progress
    """
    db = SessionFactory()
    browser = None
    context = None
    playwright = None

    try:
        # ── 1. Mark run as running ─────────────────────────────────────────
        run = db.get(AutoApplyRun, run_id)
        if not run:
            logger.error(f"AutoApplyRun {run_id} not found")
            return

        run.status = "running"
        db.commit()

        LogService.create_log(db, user_id, "info", f"Run #{run_id} started")

        # ── 2. Load settings and CV summary ───────────────────────────────
        settings = SettingsService.get_user_settings(db, user_id)

        if not settings.auto_apply_enabled:
            _fail_run(db, run, "Auto Apply is disabled")
            LogService.create_log(db, user_id, "warning",
                f"Run #{run_id} stopped: Auto Apply is disabled in settings")
            return

        cv_summary = settings.cv_summary
        if not cv_summary:
            _fail_run(db, run, "No CV summary found. Please upload your CV first.")
            LogService.create_log(db, user_id, "warning",
                f"Run #{run_id} stopped: No CV summary found")
            return

        personal_info = settings.personal_info or {}

        # ── 3. Load LinkedIn session ───────────────────────────────────────
        try:
            storage_state = LinkedInSessionService.get_storage_state(db, user_id)
        except ValueError as e:
            _fail_run(db, run, str(e))
            LogService.create_log(db, user_id, "error",
                f"Run #{run_id} stopped: LinkedIn session error — {str(e)}")
            return

        # ── 4. Check daily limit ───────────────────────────────────────────
        today = datetime.utcnow().date()
        applications_today = db.query(Application).filter(
            Application.user_id == user_id,
            Application.status == "submitted",
            Application.created_at >= datetime(today.year, today.month, today.day)
        ).count()

        remaining = settings.daily_limit - applications_today
        if remaining <= 0:
            _fail_run(db, run, "Daily application limit already reached")
            LogService.create_log(db, user_id, "warning",
                f"Run #{run_id} stopped: Daily limit of {settings.daily_limit} already reached")
            return

        LogService.create_log(db, user_id, "info",
            f"Run #{run_id}: {applications_today} submitted today, "
            f"{remaining} remaining from daily limit of {settings.daily_limit}")

        # ── 5. Build filters ───────────────────────────────────────────────
        filters = {
            "keywords": [k.strip() for k in settings.keywords.split(",") if k.strip()] if settings.keywords else [],
            "locations": [l.strip() for l in settings.locations.split(",") if l.strip()] if settings.locations else [],
            "easy_apply_only": True,
        }

        # ── 6. Start browser ───────────────────────────────────────────────
        logger.info(f"[run={run_id}] Starting browser for user {user_id}")
        browser, context, page, playwright, error = PlaywrightService.start_browser(storage_state)

        if error:
            _fail_run(db, run, f"Browser failed to start: {error}")
            LogService.create_log(db, user_id, "error",
                f"Run #{run_id} failed: Browser could not start — {error}")
            return

        # ── 7. Search for jobs ─────────────────────────────────────────────
        logger.info(f"[run={run_id}] Searching jobs with filters: {filters}")
        try:
            job_links = SearchService.search(
                page=page,
                filters=filters,
                limit=remaining
            )
        except Exception as e:
            _fail_run(db, run, f"Job search failed: {str(e)}")
            LogService.create_log(db, user_id, "error",
                f"Run #{run_id} failed: Job search error — {str(e)}")
            return

        run.total_found = len(job_links)
        db.commit()
        logger.info(f"[run={run_id}] Found {len(job_links)} jobs")

        # ── 7.5. Filter already-submitted jobs ─────────────────────────────
        already_applied = set(
            row[0] for row in
            db.query(Application.job_link)
            .filter(
                Application.user_id == user_id,
                Application.status == "submitted",
                Application.job_link.isnot(None),
            )
            .all()
        )

        original_count = len(job_links)
        job_links = [link for link in job_links if link not in already_applied]
        filtered_count = original_count - len(job_links)

        if filtered_count > 0:
            logger.info(
                f"[run={run_id}] Filtered {filtered_count} already-submitted job(s). "
                f"Remaining: {len(job_links)}"
            )

        LogService.create_log(db, user_id, "info",
            f"Run #{run_id}: Found {original_count} jobs, "
            f"{filtered_count} already applied, {len(job_links)} to process")

        # ── 8. Apply loop ──────────────────────────────────────────────────
        applied_count = 0
        failed_count = 0

        for link in job_links:
            try:
                apply_result = ApplyService.apply(page, link)

                job_title = apply_result.get("job_title", "Unknown")
                company = apply_result.get("company", "Unknown")
                job_description = apply_result.get("job_description", "")
                status = apply_result.get("status")

                if status != "questions_extracted":
                    ApplicationService.create_application(db, user_id, {
                        **apply_result,
                        "run_id": run_id,
                    })
                    failed_count += 1
                    run.failed_count = failed_count
                    db.commit()
                    logger.info(f"[run={run_id}] Skipped {link}: {apply_result.get('error_message')}")
                    continue

                # ── Semantic relevance scoring ─────────────────────────────
                relevance = score_job(
                    job_title=apply_result.get("job_title") or "",
                    job_description=apply_result.get("job_description") or "",
                    cv_summary=cv_summary,
                )
                logger.info(
                    f"[run={run_id}] Relevance score={relevance['score']} "
                    f"bypass={relevance['bypass']} | {relevance['reason']} | "
                    f"matched={relevance['matched_terms']}"
                )

                if not relevance["accepted"]:
                    ApplicationService.create_application(db, user_id, {
                        "job_title": apply_result.get("job_title"),
                        "company": apply_result.get("company"),
                        "job_link": link,
                        "job_description": apply_result.get("job_description"),
                        "status": "failed",
                        "error_message": f"Irrelevant job — score={relevance['score']}",
                    })
                    failed_count += 1
                    run.failed_count = failed_count
                    db.commit()
                    continue

                # Easy Apply popup is open — run the automated loop
                logger.info(f"[run={run_id}] Applying to: {job_title} at {company}")

                loop_result = ApplyLoopService.run(
                    page=page,
                    job_description=job_description,
                    cv_summary=cv_summary,
                    personal_info=personal_info,
                )

                outcome = loop_result["outcome"]
                final_status = "submitted" if outcome == "submitted" else "failed"

                ApplicationService.create_application(db, user_id, {
                    "job_title": job_title,
                    "company": company,
                    "job_link": link,
                    "job_description": job_description,
                    "status": final_status,
                    "error_message": loop_result.get("error"),
                    "run_id": run_id,
                })

                if final_status == "submitted":
                    applied_count += 1
                    logger.info(f"[run={run_id}] Submitted: {job_title} at {company}")
                    LogService.create_log(db, user_id, "info",
                        f"Run #{run_id}: Submitted — {job_title} at {company}")
                else:
                    failed_count += 1
                    error_msg = loop_result.get("error", "Unknown error")
                    logger.warning(f"[run={run_id}] Failed: {job_title} — {error_msg}")
                    LogService.create_log(db, user_id, "warning",
                        f"Run #{run_id}: Failed — {job_title} at {company} — {error_msg}")

                # Update run progress after each job
                run.applied_count = applied_count
                run.failed_count = failed_count
                db.commit()

            except Exception as e:
                failed_count += 1
                run.failed_count = failed_count
                LogService.create_log(db, user_id, "error",
                    f"Run #{run_id}: Exception processing {link} — {str(e)}")
                db.commit()
                logger.exception(f"[run={run_id}] Exception processing {link}")
                continue

            time.sleep(1)

        # ── 9. Mark run complete ───────────────────────────────────────────
        run.status = "completed" if failed_count == 0 else "completed_with_errors"
        run.applied_count = applied_count
        run.failed_count = failed_count
        run.completed_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"[run={run_id}] Completed. Applied: {applied_count}, Failed: {failed_count}"
        )
        LogService.create_log(db, user_id, "info",
            f"Run #{run_id} completed — Submitted: {applied_count}, Failed: {failed_count}")

    except Exception as e:
        logger.exception(f"[run={run_id}] Unexpected task error")
        LogService.create_log(db, user_id, "error",
            f"Run #{run_id}: Unexpected error — {str(e)}")
        try:
            run = db.get(AutoApplyRun, run_id)
            if run:
                _fail_run(db, run, f"Unexpected error: {str(e)}")
        except Exception:
            pass

    finally:
        # ── 10. Always close the browser ───────────────────────────────────
        try:
            if context:
                context.close()
        except Exception:
            pass
        try:
            if browser:
                browser.close()
        except Exception:
            pass
        try:
            if playwright:
                playwright.stop()
        except Exception:
            pass
        try:
            db.close()
        except Exception:
            pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fail_run(db, run: AutoApplyRun, message: str) -> None:
    """Mark a run as failed with an error message."""
    try:
        run.status = "failed"
        run.error_message = message
        run.completed_at = datetime.utcnow()
        db.commit()
    except Exception:
        pass
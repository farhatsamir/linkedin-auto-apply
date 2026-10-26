"""
app/services/apply_loop_service.py

Automated page-by-page application engine.
Called from inside a Celery task — runs synchronously.
No HTTP concerns. No shared state. No in-memory session dict.

Flow per popup page:
  1. Extract questions from current popup state
  2. Call Ollama synchronously to generate answers
  3. Fill form fields with answers
  4. Click Next / Submit
  5. Wait for page transition
  6. Detect: new page appeared → loop | submitted → exit | stuck → exit

Returns a result dict describing the final outcome.
"""
import time
import json
import re
import ollama  # type: ignore
from playwright.sync_api import Page # type: ignore

from app.core.config import settings


# Maximum number of popup pages to process per application
# Prevents infinite loops on malformed LinkedIn forms
MAX_PAGES = 10


class ApplyLoopService:


    @staticmethod
    def _clean_unicode(s: str) -> str:
        """Strip Unicode bidirectional control characters from a string."""
        import unicodedata
        return "".join(
            c for c in s
            if not unicodedata.category(c).startswith("C")
            and c not in ("\u200f", "\u200e", "\u202a", "\u202b",
                          "\u202c", "\u202d", "\u202e", "\u2066",
                          "\u2067", "\u2068", "\u2069", "\u206a")
        )


    @staticmethod
    def run(
        page: Page,
        job_description: str,
        cv_summary: dict,
        personal_info: dict = None,
    ) -> dict:
        """
        Entry point. Call this after the Easy Apply popup is already open.

        Args:
            page:            Active Playwright Page with popup visible
            job_description: Extracted job description text
            cv_summary:      User's CV summary dict from settings

        Returns:
            {
                "outcome":  "submitted" | "failed" | "max_pages_reached",
                "pages_completed": int,
                "error": str | None
            }
        """
        pages_completed = 0

        import logging
        _log = logging.getLogger(__name__)

        for page_num in range(MAX_PAGES):
            # ── 1. Locate the popup ───────────────────────────────────────────
            popup = page.locator('div[role="dialog"]')
            if popup.count() == 0:
                outcome = "submitted" if pages_completed > 0 else "failed"
                return {
                    "outcome": outcome,
                    "pages_completed": pages_completed,
                    "error": None if outcome == "submitted" else "Popup closed before submission"
                }

            # ── 2. Check confirmation BEFORE doing anything else ───────────────
            # This catches the confirmation screen at the START of a loop iteration
            # so we never try to fill or click on a confirmation popup
            if pages_completed > 0 and ApplyLoopService._is_submission_confirmed(page, popup, page_num, _log):
                return {
                    "outcome": "submitted",
                    "pages_completed": pages_completed,
                    "error": None
                }

            # ── 3. Extract questions from current page ─────────────────────────
            questions = ApplyLoopService._extract_questions(page, popup)
            _log.info(f"[apply_loop] page {page_num+1}: extracted {len(questions)} questions")
            for q in questions:
                _log.info(f"[apply_loop]   field: label='{q['label']}' type={q['type']} options={q['options']}")


            # ── 3.4. Detect truly mandatory non-resume file fields ─────────────
            # File upload fields on page 1 that are DOM-required cannot be filled
            # programmatically. If such a field is required, skip the job.
            # If it is not required (no required attribute), proceed normally —
            # LinkedIn will not block submission for optional file fields.
            if pages_completed == 0 and questions:
                file_qs = [q for q in questions if q["type"] == "file"]
                non_resume_file_qs = [
                    q for q in file_qs
                    if not any(kw in q["label"].lower() for kw in
                               ["resume", "cv", "سيرة"])
                ]
                for fq in non_resume_file_qs:
                    try:
                        # Find the file input in the popup and check required attribute
                        file_inputs = popup.locator('input[type="file"]')
                        for fi in range(file_inputs.count()):
                            inp = file_inputs.nth(fi)
                            is_required = inp.evaluate(
                                "el => el.required || el.getAttribute('aria-required') === 'true'"
                            )
                            if is_required:
                                _log.warning(
                                    f"[apply_loop] page 1: required non-resume file field "
                                    f"'{fq['label']}' cannot be filled — skipping job"
                                )
                                return {
                                    "outcome": "failed",
                                    "pages_completed": 0,
                                    "error": f"Required file upload cannot be filled: {fq['label']}"
                                }
                    except Exception as e:
                        _log.warning(f"[apply_loop] page 1: file required check failed: {e}")



            # ── 3.5. Handle resume radio buttons ──────────────────────────────
            # LinkedIn shows Arabic radio buttons to select which uploaded resume
            # to use. These are identified by containing "تحديد" (select) or
            # "إلغاء تحديد" (deselect) in the label.
            #
            # Rule: always silently select the FIRST resume radio (most recent
            # upload) and remove all resume radio questions from the list before
            # passing to Ollama. This works for both cases:
            #   A) Pure resume page (only resume radios + file upload) → all
            #      questions removed → Ollama skipped → click Next immediately.
            #   B) Combined page (resume radios + Headline/Summary/Cover letter)
            #      → resume radio handled silently → Ollama gets only real fields.
            #
            # We never let Ollama see or answer resume radio questions because
            # Ollama answers both the deselect and select radio, causing
            # LinkedIn to end up with no resume selected.
            if questions:
                resume_radio_labels = {"إلغاء تحديد", "تحديد", "سيرة"}
                resume_qs = [
                    q for q in questions
                    if q["type"] == "radio" and any(
                        kw in q["label"] for kw in resume_radio_labels
                    )
                ]

                if resume_qs:
                    # Find and click the "تحديد" (select) radio — the one that
                    # selects a resume rather than deselecting it. Click only that
                    # one. Never click the deselect radio.
                    # "إلغاء تحديد" = deselect/cancel = this CV is currently selected.
                    # Clicking it confirms the pre-selected most-recent CV.
                    # "تحديد" without "إلغاء" = select an alternative CV — avoid.
                    # We always want the most-recently-uploaded CV (pre-selected by LinkedIn).
                    select_qs = [
                        q for q in resume_qs
                        if "إلغاء تحديد" in q["label"]
                    ]
                    target_q = select_qs[0] if select_qs else resume_qs[0]
                    try:
                        # Find the radio input whose parent label contains the
                        # target label text (after stripping Unicode marks)
                        import unicodedata as _ud_resume
                        def _strip_marks(s):
                            return "".join(
                                c for c in s
                                if not _ud_resume.category(c).startswith("C")
                                and c not in ("\u200f", "\u200e", "\u202a",
                                              "\u202b", "\u202c", "\u202d",
                                              "\u202e", "\u2066", "\u2067",
                                              "\u2068", "\u2069")
                            ).strip()

                        target_text_clean = _strip_marks(target_q["label"])
                        all_radios = popup.locator('input[type="radio"]')
                        for r in range(all_radios.count()):
                            try:
                                parent_text = _strip_marks(
                                    all_radios.nth(r).locator("xpath=..").inner_text()
                                )
                                if target_text_clean in parent_text or parent_text in target_text_clean:
                                    all_radios.nth(r).dispatch_event("click")
                                    page.wait_for_timeout(400)
                                    _log.info(
                                        f"[apply_loop] page {page_num+1}: "
                                        f"resume radio selected silently: '{parent_text[:60]}'"
                                    )
                                    break
                            except Exception:
                                continue
                    except Exception as e:
                        _log.warning(f"[apply_loop] page {page_num+1}: resume radio click failed: {e}")

                    # Remove all resume radio questions from the list.
                    # Ollama will only see and answer the remaining questions
                    # (Headline, Summary, Cover letter, etc.).
                    questions = [
                        q for q in questions
                        if not (
                            q["type"] == "radio" and any(
                                kw in q["label"] for kw in resume_radio_labels
                            )
                        )
                    ]

                    # If no questions remain after removing resume radios,
                    # this is a pure resume selection page — skip Ollama entirely.
                    non_file_remaining = [
                        q for q in questions if q["type"] not in ("file", None)
                    ]
                    if not non_file_remaining:
                        _log.info(
                            f"[apply_loop] page {page_num+1}: "
                            f"resume selection page — skipping Ollama, clicking Next"
                        )
                        ApplyLoopService._click_next(page, popup)
                        pages_completed += 1
                        time.sleep(2)
                        continue
                    # Otherwise fall through — Ollama will handle remaining questions
                    _log.info(
                        f"[apply_loop] page {page_num+1}: "
                        f"resume radio handled silently, {len(non_file_remaining)} "
                        f"remaining questions sent to Ollama"
                    )

            if not questions:
                # Check confirmation before clicking anything
                if pages_completed > 0 and ApplyLoopService._is_submission_confirmed(
                    page, popup, page_num, logging.getLogger(__name__)
                ):
                    return {
                        "outcome": "submitted",
                        "pages_completed": pages_completed,
                        "error": None
                    }

                clicked = ApplyLoopService._click_next(page, popup)
                if not clicked:
                    return {
                        "outcome": "submitted" if pages_completed > 0 else "failed",
                        "pages_completed": pages_completed,
                        "error": None
                    }
                pages_completed += 1

                # If we just clicked the final confirmation button (تم),
                # exit immediately — do not check for more popups
                time.sleep(1)
                popup_check = page.locator('div[role="dialog"]')
                if popup_check.count() == 0:
                    return {
                        "outcome": "submitted",
                        "pages_completed": pages_completed,
                        "error": None
                    }
                if pages_completed > 0 and ApplyLoopService._is_submission_confirmed(
                    page, popup_check, page_num, logging.getLogger(__name__)
                ):
                    return {
                        "outcome": "submitted",
                        "pages_completed": pages_completed,
                        "error": None
                    }
                time.sleep(1)
                continue

            # ── 3.6. Detect and handle work experience page ────────────────────
            # LinkedIn's work experience page contains structured fields:
            # 'Your title', 'Company', date dropdowns, 'Description', 'City'.
            # Ollama cannot fill these reliably — it hallucinates fictional data.
            # These fields map directly to cv_summary work history entries.
            # We bypass Ollama entirely and fill from cv_summary["work_history"][0].
            #
            # Detection: page has BOTH 'Your title' AND 'Company' text fields.
            # This combination is unique to LinkedIn's work experience form.
            _work_exp_labels = {
                ApplyLoopService._clean_unicode(q["label"]).lower()
                for q in questions
                if q["type"] in ("text", "textarea", "checkbox")
            }
            _is_work_exp_page = (
                "your title" in _work_exp_labels
                and "company" in _work_exp_labels
            )

            if _is_work_exp_page:
                _log.info(f"[apply_loop] page {page_num+1}: work experience page detected — filling from cv_summary")

                work_history = (cv_summary or {}).get("work_history") or []
                current_entry = work_history[0] if work_history else {}

                # Determine once whether this is a current job.
                # Used to skip To-date fields (LinkedIn hides them when
                # 'I currently work here' is checked, making their select
                # elements contain wrong/stale options that cause timeouts).
                _is_current_job = (
                    current_entry.get("is_current")
                    or not bool(current_entry.get("end_year"))
                )

                _month_ar = {
                    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
                    5: "مايو",   6: "يونيو",  7: "يوليو",  8: "أغسطس",
                    9: "سبتمبر",10: "أكتوبر",11: "نوفمبر",12: "ديسمبر",
                }

                # Country/region tokens that are not valid city names.
                # When cv_summary stores one of these as city, fall back
                # to personal_info["city"] instead.
                _COUNTRY_TOKENS = {
                    "uae", "united arab emirates", "syria", "syrian arab republic",
                    "lebanon", "jordan", "egypt", "ksa", "saudi arabia",
                    "qatar", "kuwait", "bahrain", "oman", "iraq", "turkey",
                    "germany", "france", "uk", "united kingdom", "usa",
                    "united states", "canada", "australia", "india", "pakistan",
                }

                answers = {}
                for q in questions:
                    label_clean = ApplyLoopService._clean_unicode(q["label"]).lower()
                    label_orig  = q["label"]
                    qtype       = q["type"]

                    # ── Job title ──────────────────────────────────────────────
                    if "your title" in label_clean or "job title" in label_clean:
                        answers[label_orig] = (
                            current_entry.get("title")
                            or (personal_info or {}).get("current_title", "")
                        )

                    # ── Company ────────────────────────────────────────────────
                    elif label_clean == "company":
                        answers[label_orig] = (
                            current_entry.get("company")
                            or (personal_info or {}).get("current_company", "")
                        )

                    # ── Currently employed checkbox ────────────────────────────
                    elif "i currently work here" in label_clean:
                        answers[label_orig] = _is_current_job

                    # ── Start month ────────────────────────────────────────────
                    elif (
                        ("شهر" in q["label"] and "from" in label_clean)
                        or label_clean in ("dates of employment", "شهر from")
                    ):
                        start_month = current_entry.get("start_month")
                        if start_month and qtype == "dropdown" and q.get("options"):
                            if isinstance(start_month, int):
                                answers[label_orig] = _month_ar.get(start_month, q["options"][0])
                            else:
                                answers[label_orig] = str(start_month)
                        elif qtype == "dropdown" and q.get("options"):
                            answers[label_orig] = q["options"][0]

                    # ── Start year ─────────────────────────────────────────────
                    elif "عام" in q["label"] and "from" in label_clean:
                        start_year = current_entry.get("start_year")
                        if start_year and qtype == "dropdown" and q.get("options"):
                            target = str(start_year)
                            # Strip Unicode marks from both target and options
                            # before comparing — LinkedIn embeds RTL marks in
                            # option text that break exact string equality.
                            cleaned_opts = [
                                ApplyLoopService._clean_unicode(o).strip()
                                for o in q["options"]
                            ]
                            target_clean = ApplyLoopService._clean_unicode(target).strip()
                            if target_clean in cleaned_opts:
                                answers[label_orig] = q["options"][cleaned_opts.index(target_clean)]
                            else:
                                # Numeric substring fallback: find option containing the year digits
                                matched_idx = next(
                                    (i for i, o in enumerate(cleaned_opts) if target_clean in o),
                                    None
                                )
                                answers[label_orig] = (
                                    q["options"][matched_idx]
                                    if matched_idx is not None
                                    else q["options"][0]
                                )
                        elif qtype == "dropdown" and q.get("options"):
                            answers[label_orig] = q["options"][0]

                    # ── End month — skip if current job ────────────────────────
                    elif "شهر" in q["label"] and "to" in label_clean:
                        if _is_current_job:
                            # LinkedIn hides this field when 'I currently work here'
                            # is checked. The select DOM changes state and contains
                            # wrong options. Attempting to fill it causes a 7-minute
                            # timeout and leaves the field in an invalid state.
                            continue
                        end_month = current_entry.get("end_month")
                        if end_month and qtype == "dropdown" and q.get("options"):
                            if isinstance(end_month, int):
                                answers[label_orig] = _month_ar.get(end_month, q["options"][0])
                            else:
                                answers[label_orig] = str(end_month)
                        elif qtype == "dropdown" and q.get("options"):
                            answers[label_orig] = q["options"][0]

                    # ── End year — skip if current job ─────────────────────────
                    elif "عام" in q["label"] and "to" in label_clean:
                        if _is_current_job:
                            continue
                        end_year = current_entry.get("end_year")
                        if end_year and qtype == "dropdown" and q.get("options"):
                            target = str(end_year)
                            cleaned_opts = [
                                ApplyLoopService._clean_unicode(o).strip()
                                for o in q["options"]
                            ]
                            target_clean = ApplyLoopService._clean_unicode(target).strip()
                            if target_clean in cleaned_opts:
                                answers[label_orig] = q["options"][cleaned_opts.index(target_clean)]
                            else:
                                matched_idx = next(
                                    (i for i, o in enumerate(cleaned_opts) if target_clean in o),
                                    None
                                )
                                answers[label_orig] = (
                                    q["options"][matched_idx]
                                    if matched_idx is not None
                                    else q["options"][0]
                                )
                        elif qtype == "dropdown" and q.get("options"):
                            answers[label_orig] = q["options"][0]

                    # ── City / Location ────────────────────────────────────────
                    elif "city" in label_clean or "location" in label_clean:
                        raw_city = (current_entry.get("city") or "").strip()
                        # If stored value is a country/region name, it cannot be
                        # matched against city autocomplete suggestions.
                        # Fall back to personal_info["city"] which is always a
                        # proper city name entered directly by the user.
                        if not raw_city or raw_city.lower() in _COUNTRY_TOKENS:
                            raw_city = (personal_info or {}).get("city", "Dubai")
                        answers[label_orig] = raw_city

                    # ── Description ────────────────────────────────────────────
                    elif "description" in label_clean:
                        answers[label_orig] = current_entry.get("description") or ""

                _log.info(
                    f"[apply_loop] page {page_num+1}: "
                    f"work experience answers built from cv_summary: {list(answers.keys())}"
                )

            else:
                # ── 4. Generate answers via Ollama ────────────────────────────────
                try:
                    answers = ApplyLoopService._generate_answers(
                        job_description=job_description,
                        cv_summary=cv_summary,
                        questions=questions,
                        personal_info=personal_info or {},
                    )
                except Exception as e:
                    _log.warning(f"[apply_loop] Ollama failed on page {page_num+1}: {e}")
                    answers = {}

            # ── 5. Fill fields ─────────────────────────────────────────────────
            # Always call _fill_fields — even if Ollama returned nothing,
            # the personal_info fallback inside _generate_answers may have
            # populated answers for standard fields (name, email, phone, salary).
            # An empty answers dict is safe — _fill_fields handles it gracefully.
            ApplyLoopService._fill_fields(page, popup, answers, questions)

            # ── 6. Click Next / Submit ─────────────────────────────────────────
            clicked = ApplyLoopService._click_next(page, popup)
            pages_completed += 1
            _log.info(f"[apply_loop] page {page_num+1}: clicked={clicked}, pages_completed={pages_completed}")

            if not clicked:
                _log.warning(f"[apply_loop] Next button not found on page {page_num+1}")
                return {
                    "outcome": "failed",
                    "pages_completed": pages_completed,
                    "error": "Could not find Next or Submit button"
                }

            # ── 7. Wait for page transition ────────────────────────────────────
            time.sleep(2)

            # ── 8. Check if popup is gone ──────────────────────────────────────
            popup_after = page.locator('div[role="dialog"]')
            _log.info(f"[apply_loop] page {page_num+1}: popup_after count={popup_after.count()}")
            if popup_after.count() == 0:
                return {
                    "outcome": "submitted",
                    "pages_completed": pages_completed,
                    "error": None
                }

            # ── 9. Check confirmation inside popup after click ─────────────────
            if ApplyLoopService._is_submission_confirmed(page, popup_after, page_num, _log):
                return {
                    "outcome": "submitted",
                    "pages_completed": pages_completed,
                    "error": None
                }

            # ── 10. Detect form validation errors ──────────────────────────────
            try:
                error_locator = popup_after.locator(
                    '.artdeco-inline-feedback--error, '
                    '[data-test-form-element-error], '
                    '.fb-dash-form-element__error-text'
                )
                if error_locator.count() > 0:
                    error_texts = [
                        error_locator.nth(i).inner_text().strip()
                        for i in range(min(error_locator.count(), 3))
                    ]
                    _log.warning(f"[apply_loop] Validation errors on page {page_num+1}: {error_texts}")

                    # ── Single retry — only if this page used Ollama ───────────
                    # Work experience pages (deterministic fill) and resume pages
                    # (no Ollama) are excluded — their errors are data problems,
                    # not answer-format problems. Retrying them wastes time.
                    # _is_work_exp_page is True when the work experience handler ran.
                    # answers is {} when resume page skipped Ollama.
                    _ollama_was_used = (
                        not _is_work_exp_page
                        and bool(answers)
                    )

                    if _ollama_was_used:
                        _log.info(
                            f"[apply_loop] page {page_num+1}: "
                            f"retrying with correction context — errors: {error_texts}"
                        )
                        try:
                            # Build corrected answers using error context
                            retry_answers = ApplyLoopService._generate_answers(
                                job_description=job_description,
                                cv_summary=cv_summary,
                                questions=questions,
                                personal_info=personal_info or {},
                                validation_errors=error_texts,
                                previous_answers=answers,
                            )
                        except Exception as retry_exc:
                            _log.warning(
                                f"[apply_loop] page {page_num+1}: "
                                f"retry Ollama call failed: {retry_exc}"
                            )
                            retry_answers = {}

                        if retry_answers:
                            # Re-fill the page with corrected answers
                            ApplyLoopService._fill_fields(
                                page, popup_after, retry_answers, questions
                            )

                            # Click Next again
                            retry_clicked = ApplyLoopService._click_next(
                                page, popup_after
                            )
                            # pages_completed was already incremented for the first
                            # attempt — decrement it so the counter stays accurate
                            # when the outer loop increments it again on next pass.
                            # Actually: we do NOT decrement. The retry click is the
                            # same page's final action. pages_completed stays as-is.
                            _log.info(
                                f"[apply_loop] page {page_num+1}: "
                                f"retry clicked={retry_clicked}"
                            )

                            time.sleep(2)
                            popup_retry = page.locator('div[role="dialog"]')

                            # Popup gone → submitted / advanced
                            if popup_retry.count() == 0:
                                _log.info(
                                    f"[apply_loop] page {page_num+1}: "
                                    f"retry succeeded — popup closed"
                                )
                                continue

                            # Check submission confirmed
                            if ApplyLoopService._is_submission_confirmed(
                                page, popup_retry, page_num, _log
                            ):
                                return {
                                    "outcome": "submitted",
                                    "pages_completed": pages_completed,
                                    "error": None,
                                }

                            # Check for validation errors again after retry
                            try:
                                retry_errors = popup_retry.locator(
                                    '.artdeco-inline-feedback--error, '
                                    '[data-test-form-element-error], '
                                    '.fb-dash-form-element__error-text'
                                )
                                if retry_errors.count() > 0:
                                    retry_error_texts = [
                                        retry_errors.nth(i).inner_text().strip()
                                        for i in range(min(retry_errors.count(), 3))
                                    ]
                                    _log.warning(
                                        f"[apply_loop] page {page_num+1}: "
                                        f"retry also failed — {retry_error_texts}"
                                    )
                                    return {
                                        "outcome": "failed",
                                        "pages_completed": pages_completed,
                                        "error": f"Form validation failed after retry: {retry_error_texts}",
                                    }
                            except Exception:
                                pass

                            # No errors on retry — page advanced normally, continue
                            continue

                    # No retry (work exp page, resume page, or empty answers),
                    # or retry produced no corrected answers — hard fail as before
                    return {
                        "outcome": "failed",
                        "pages_completed": pages_completed,
                        "error": f"Form validation failed: {error_texts}",
                    }

            except Exception:
                pass

        return {
            "outcome": "max_pages_reached",
            "pages_completed": pages_completed,
            "error": f"Reached maximum page limit of {MAX_PAGES}"
        }

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _extract_questions(page: Page, popup) -> list[dict]:
        """
        Extract all questions from the current popup page.

        For radio groups: detects the question label above the group
        and collects all radio options as a single question entry.
        For all other fields: uses the label element directly.
        """
        questions = []
        seen_labels = set()   # stores normalized labels for deduplication

        try:
            labels = popup.locator("label")
            for i in range(labels.count()):
                label_el = labels.nth(i)
                label_text = label_el.inner_text().strip().split("\n")[0].strip()
                if not label_text or len(label_text) < 2:
                    continue

                container = label_el.locator("xpath=..")
                q_type, options = ApplyLoopService._detect_field_type(page, container, label_text)

                # ── Radio group handling ───────────────────────────────────────
                # Individual radio buttons (Yes/No) have their own <label> elements.
                # We need to find the actual question text above the radio group.
                if q_type == "radio":
                    # Walk up DOM to find the fieldset or question container
                    question_text = ApplyLoopService._find_radio_question_label(
                        page, popup, label_el, label_text
                    )

                    if question_text and question_text not in seen_labels:
                        # Collect ALL options for this question group
                        all_options = ApplyLoopService._collect_radio_group_options(
                            page, popup, label_el, question_text
                        )
                        seen_labels.add(question_text)
                        questions.append({
                            "label": question_text,
                            "type": "radio",
                            "options": all_options,
                        })
                    # Skip individual Yes/No labels — they are part of a group
                    continue

                # ── All other field types ──────────────────────────────────────
                norm_label = re.sub(r"[^\w\s]", "", label_text.strip().lower())
                if norm_label not in seen_labels:
                    seen_labels.add(norm_label)
                    questions.append({
                        "label": label_text,
                        "type": q_type,
                        "options": options,
                    })

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[extract] Exception: {e}")

        return questions



    @staticmethod
    def _find_radio_question_label(page, popup, radio_label_el, fallback: str) -> str:
        """
        Given a label element for an individual radio option (e.g. 'Yes'),
        walk up the DOM to find the actual question text for the radio group.

        LinkedIn's structure is typically:
          <div class="question-container">
            <legend> or <span>  ← question text here
            <div>
              <label for="radio1">Yes</label>
              <label for="radio2">No</label>
            </div>
          </div>
        """
        try:
            # Try: parent → parent → first text-only child (not a label)
            grandparent = radio_label_el.locator("xpath=../..")
            if grandparent.count() > 0:
                # Look for legend element (fieldset-based questions)
                legend = grandparent.locator("legend")
                if legend.count() > 0:
                    text = legend.first.inner_text().strip().split("\n")[0].strip()
                    if text and len(text) > 2:
                        return text

                # Look for a span or div that contains the question text
                # (not a label, not an input)
                for tag in ["span", "div", "p", "h3", "h4"]:
                    candidates = grandparent.locator(tag)
                    for j in range(min(candidates.count(), 5)):
                        candidate = candidates.nth(j)
                        text = candidate.inner_text().strip().split("\n")[0].strip()
                        # Must be longer than a single option and not an option itself
                        if (text
                                and len(text) > 3
                                and text not in ("Yes", "No", "نعم", "لا", "True", "False")
                                and "radio" not in (candidate.get_attribute("type") or "")):
                            return text

            # Try: great-grandparent
            ggp = radio_label_el.locator("xpath=../../..")
            if ggp.count() > 0:
                legend = ggp.locator("legend")
                if legend.count() > 0:
                    text = legend.first.inner_text().strip().split("\n")[0].strip()
                    if text and len(text) > 2:
                        return text

        except Exception:
            pass

        # Fallback: use the option label itself (old behavior)
        return fallback

    @staticmethod
    def _collect_radio_group_options(page, popup, radio_label_el, question_text: str) -> list[str]:
        """
        Collect all radio button option texts for the group that contains
        the given radio label element.
        """
        options = []
        try:
            # Find the container that holds this radio button
            container = radio_label_el.locator("xpath=..")
            # Look for all sibling labels (other radio options in the same group)
            parent = radio_label_el.locator("xpath=../..")
            if parent.count() > 0:
                radios = parent.locator('input[type="radio"]')
                for r in range(radios.count()):
                    try:
                        opt = radios.nth(r).locator("xpath=..").inner_text().strip()
                        if opt and opt not in options:
                            options.append(opt)
                    except Exception:
                        pass
        except Exception:
            pass
        return options



    @staticmethod
    def _detect_field_type(page: Page, container, label_text: str) -> tuple:
        """Detect the type of a form field and its options if applicable."""
        options = []

        # Text input
        inp = container.locator("input")
        if inp.count() > 0:
            t = inp.first.get_attribute("type")
            if t in ("text", "email", "tel", "number"):
                return "text", []
            if t == "file":
                return "file", []

        # Custom LinkedIn dropdown (button-based)
        btn = container.locator('button[aria-haspopup="listbox"]')
        if btn.count() > 0:
            try:
                btn.first.click()
                page.wait_for_timeout(300)
                opts = page.locator('li[role="option"]')
                options = [opts.nth(j).inner_text().strip() for j in range(opts.count())]
                btn.first.click()
                page.wait_for_timeout(200)
            except Exception:
                pass
            return "dropdown", options

        # Native select — read options directly from DOM
        sel_el = container.locator("select")
        if sel_el.count() > 0:
            try:
                _arabic_months = {
                    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
                }
                _english_months = {
                    "january", "february", "march", "april", "may", "june",
                    "july", "august", "september", "october", "november", "december"
                }
                _all_months = _arabic_months | _english_months

                def _read_opts(sel):
                    return [
                        o.inner_text().strip()
                        for o in sel.locator("option").all()
                        if o.get_attribute("value") not in (None, "", "Select an option")
                        and o.inner_text().strip()
                    ]

                def _is_month_list(opts):
                    return bool(opts) and {o.lower() for o in opts}.issubset(_all_months)

                label_lower = label_text.lower()
                is_year_label = "عام" in label_text or "year" in label_lower

                if is_year_label:
                    # For year fields: the container may only contain the month <select>
                    # because LinkedIn sometimes scopes the year label's container to
                    # the wrong element. Walk up to the grandparent and search all
                    # <select> elements at that level to find the non-month one.
                    found_year_opts = None
                    for ancestor in [container, container.locator("xpath=.."), container.locator("xpath=../..")]:
                        try:
                            all_sel = ancestor.locator("select")
                            count = all_sel.count()
                            if count < 2:
                                continue
                            for i in range(count):
                                opts_i = _read_opts(all_sel.nth(i))
                                if opts_i and not _is_month_list(opts_i):
                                    found_year_opts = opts_i
                                    break
                            if found_year_opts is not None:
                                break
                        except Exception:
                            continue
                    options = found_year_opts if found_year_opts is not None else _read_opts(sel_el.first)
                else:
                    options = _read_opts(sel_el.first)

            except Exception:
                options = []
            return "dropdown", options

        # Radio buttons
        radios = container.locator('input[type="radio"]')
        if radios.count() > 0:
            for r in range(radios.count()):
                try:
                    opt = radios.nth(r).locator("xpath=..").inner_text().strip()
                    options.append(opt)
                except Exception:
                    pass
            return "radio", options

        # Checkbox
        if container.locator('input[type="checkbox"]').count() > 0:
            return "checkbox", []

        # Textarea
        if container.locator("textarea").count() > 0:
            return "textarea", []

        return None, []

    @staticmethod
    def _generate_answers(
        job_description: str,
        cv_summary: dict,
        questions: list[dict],
        personal_info: dict = None,
        validation_errors: list = None,
        previous_answers: dict = None,
    ) -> dict:
        import logging
        _log = logging.getLogger(__name__)

        question_list = [
            f"- {q['label']} (type: {q['type']}"
            + (f", options: {q['options']}" if q.get("options") else "")
            + ")"
            for q in questions
            if q["type"] not in ("file", None)
        ]

        if not question_list:
            _log.info("[ollama] No answerable questions — skipping Ollama call")
            return {}

        personal_info = personal_info or {}

        prompt = f"""You are a job application assistant helping a candidate fill in a LinkedIn Easy Apply form.

CANDIDATE PERSONAL INFORMATION:
{json.dumps(personal_info, ensure_ascii=False)}

CANDIDATE CV SUMMARY:
{json.dumps(cv_summary, ensure_ascii=False)[:2000]}

JOB DESCRIPTION:
{job_description[:1500]}

FORM FIELDS TO FILL:
{chr(10).join(question_list)}

INSTRUCTIONS:
- Return ONLY a valid JSON object. No explanations. No markdown.
- Keys must be the EXACT field labels as given above. Copy them character for character. Do NOT paraphrase, shorten, translate, or convert to snake_case. For example, if the label is "Do you have a UAE passport?" your key must be exactly "Do you have a UAE passport?" — never "uae_passport" or "has_uae_passport".
- Use the PERSONAL INFORMATION section first for any personal fields (name, phone, email, salary, notice period, location).
- For "First name" — use personal_info["first_name"] if available.
- For "Last name" — use personal_info["last_name"] if available.
- For "Mobile phone number" or "Phone" — use personal_info["mobile_number"] if available.
- For "Phone country code" — select the option closest to personal_info["country_code"] from the provided options. Default to "+971" (UAE).
- For "Email" — use personal_info["email"] if available.
- For "Current salary" — use personal_info["current_salary"] if available. Return ONLY digits and decimal point. No currency, no words, no "per month". Example: 15000 not "AED 15,000 per month".
- For "Expected salary" — use personal_info["expected_salary"] if available. Return ONLY digits and decimal point. No currency, no words, no "per month". Example: 20000 not "20,000 per month".
- For any salary, compensation, or pay field — return ONLY a plain number like 15000 or 20000.5. Never include currency symbols, text, or time periods.
- For "Notice period" or any field asking how many months or days notice — return ONLY the number, never the unit word. Example: return "30" not "30 days", return "1" not "1 month".
- For "When can you join" or similar — use personal_info["availability"] if available.
- For "Years of experience" — estimate from the CV summary. Return ONLY the number.
- For "Location" or "City" — use personal_info["city"] if available, otherwise use job location.
- For dropdown fields — return EXACTLY one of the provided options, nothing else.
- For radio fields — return EXACTLY one of the provided options, nothing else.
- For checkbox fields — return true or false.
- For text/textarea fields — return a concise professional string.
- Do NOT include file upload fields.
"""
        # ── Retry correction block ─────────────────────────────────────────────
        # Only injected when called from the retry path (validation_errors present).
        # Tells Ollama exactly what it answered before and what LinkedIn rejected.
        if validation_errors and previous_answers:
            retry_section = (
                "\n\nCORRECTION REQUIRED — YOUR PREVIOUS ANSWERS FAILED VALIDATION:\n"
                f"Validation errors returned by LinkedIn: {validation_errors}\n"
                f"Your previous answers that caused the failure: {json.dumps(previous_answers, ensure_ascii=False)}\n\n"
                "You MUST fix the answers that caused these errors.\n"
                "Return the COMPLETE corrected JSON for ALL fields — not just the failed ones.\n"
                "For fields that were accepted, keep your previous values.\n"
                "For fields that failed, provide a corrected value that satisfies the validation rule.\n"
                "If the error says 'whole number' or 'numeric', return only digits.\n"
                "If the error says 'valid answer', check that your value exactly matches one of the provided options.\n"
            )
            prompt = prompt + retry_section
            _log.info(f"[ollama] Retry prompt injected — errors: {validation_errors}")

        _log.info(f"[ollama] Sending {len(question_list)} questions:")
        for ql in question_list:
            _log.info(f"[ollama]   {ql}")

        _client = ollama.Client(
            host=settings.ollama_base_url,
            timeout=settings.ollama_timeout,
        )
        response = _client.chat(
            model=settings.ollama_model,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response["message"]["content"]
        _log.info(f"[ollama] Raw response: {content[:800]}")

        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            _log.warning("[ollama] No JSON found in response — using personal_info fallback only")
            result = {}
        else:
            try:
                result = json.loads(match.group(0))
            except json.JSONDecodeError as e:
                _log.warning(f"[ollama] JSON parse error: {e} — using personal_info fallback only")
                result = {}

        _log.info(f"[ollama] Parsed answers: {result}")

        # ── Re-map Ollama keys to exact question labels ────────────────────────
        # Ollama sometimes modifies labels: adds ?, changes spacing, drops words.
        # We normalize both sides and remap to exact question labels so _fill_fields
        # can match them correctly via exact key lookup.
        def _normalize_key(s: str) -> str:
            import re as _re2
            # Strip punctuation and parenthetical suffixes like "(in USD)"
            s = _re2.sub(r"\([^)]*\)", "", s)   # remove (anything in parens)
            s = s.replace("_", " ")              # underscores → spaces
            s = _re2.sub(r"[^\w\s]", "", s)       # remove remaining punctuation
            s = _re2.sub(r"\bplus\b", "", s)       # normalize "plus" → ""
            s = _re2.sub(r"\s+", " ", s)           # collapse whitespace
            return s.strip().lower()

        exact_labels = {q["label"]: _normalize_key(q["label"]) for q in questions}
        remapped = {}
        for ollama_key, ollama_value in result.items():
            norm_ollama = _normalize_key(ollama_key)
            matched_label = None

            # Pass 1: exact normalized match
            for exact_label, norm_label in exact_labels.items():
                if norm_label == norm_ollama:
                    matched_label = exact_label
                    break

            # Pass 2: prefix match — Ollama truncated the label
            # e.g. Ollama key "Minimum Splunk Core Certified Consultant?"
            # matches label "Minimum Splunk Core Certified Consultant? - provide certificate..."
            if matched_label is None and len(norm_ollama) >= 10:
                for exact_label, norm_label in exact_labels.items():
                    if norm_label.startswith(norm_ollama):
                        matched_label = exact_label
                        break

            # Pass 3: key-contains-significant-words match.
            # Handles the case where Ollama uses a descriptive snake_case key
            # whose significant words all appear in the question label.
            # e.g. 'notice_period_in_days' → 'notice period in days'
            # all words appear in 'please enter your notice period in days'
            if matched_label is None and len(norm_ollama) >= 6:
                ollama_words = set(norm_ollama.split())
                # Only attempt if Ollama key has at least 2 meaningful words
                # (exclude stop words to avoid false matches)
                _stop = {"a", "an", "the", "in", "of", "for", "to", "your",
                         "is", "are", "do", "you", "have", "with", "and",
                         "or", "on", "at", "by", "be", "per"}
                meaningful_words = ollama_words - _stop
                if len(meaningful_words) >= 2:
                    for exact_label, norm_label in exact_labels.items():
                        label_words = set(norm_label.split())
                        # All meaningful Ollama words must appear in the label
                        if meaningful_words.issubset(label_words):
                            matched_label = exact_label
                            _log.info(
                                f"[ollama] Key word-matched: '{ollama_key}' → '{exact_label}' "
                                f"via words {meaningful_words}"
                            )
                            break

            if matched_label:
                remapped[matched_label] = ollama_value
                if matched_label != ollama_key:
                    _log.info(f"[ollama] Key remapped: '{ollama_key}' → '{matched_label}'")
            else:
                # Keep original key — may be handled by fallback
                remapped[ollama_key] = ollama_value
        result = remapped

        # ── Personal info fallback for any field Ollama dropped ────────────────
        # Applied only to fields missing from Ollama's response.
        # Uses substring matching on the label — order is most-specific first.
        personal_info = personal_info or {}
        fallback_map = [
            (["first name", "الاسم الأول"],                         personal_info.get("first_name", "")),
            (["last name", "اسم العائلة"],                          personal_info.get("last_name", "")),
            (["mobile phone", "phone number", "هاتف"],              personal_info.get("mobile_number", "")),
            (["email", "البريد"],                                    personal_info.get("email", "")),
            # Notice period fallback.
            # notice_period_days is a plain number (e.g. "30") for numeric-only fields.
            # Falls back to notice_period if notice_period_days is not set.
            (["notice period", "notice", "إشعار"],
             personal_info.get("notice_period_days") or personal_info.get("notice_period", "")),
            (["availability", "when can you join", "joining"],       personal_info.get("availability", "")),
            (["current salary", "الراتب الحالي"],                   personal_info.get("current_salary", "")),
            (["expected salary", "الراتب المتوقع"],                 personal_info.get("expected_salary", "")),
            (["city", "location", "المدينة"],                       personal_info.get("city", "")),
            (["linkedin", "profile url"],                            personal_info.get("linkedin_url", "")),
            (["country of birth", "nationality"],                    personal_info.get("nationality", "")),
            (["years of experience", "years experience"],            personal_info.get("years_experience", "")),
        ]

        def _adapt_notice_period(value: str, label_lower: str) -> str:
            """
            Convert a stored notice period value to the unit the field expects.
            'in days'  → extract months, multiply by 30, return integer string
            'in months'→ extract months, return integer string
            Otherwise  → return value unchanged (free text field)
            """
            import re as _re_np
            if "in days" in label_lower:
                # Extract the numeric part from stored value like "1 month" or "2 months"
                m = _re_np.search(r"(\d+)", str(value))
                months = int(m.group(1)) if m else 1
                return str(months * 30)
            if "in months" in label_lower or "months notice" in label_lower:
                m = _re_np.search(r"(\d+)", str(value))
                return m.group(1) if m else str(value)
            return str(value)

        for q in questions:
            label = q["label"]
            if q["type"] in ("file", None):
                continue
            if label in result:
                continue  # already answered by Ollama
            label_lower = label.lower()
            for keywords, fallback_value in fallback_map:
                if fallback_value and any(kw in label_lower for kw in keywords):
                    # For notice period fields: adapt to the unit the field expects
                    if any(kw in label_lower for kw in ["notice period", "notice", "إشعار"]):
                        fallback_value = _adapt_notice_period(fallback_value, label_lower)
                    result[label] = fallback_value
                    _log.info(f"[ollama] Fallback: '{label}' = '{fallback_value}'")
                    break

        return result




    @staticmethod
    def _fill_fields(page: Page, popup, answers: dict, questions: list = None) -> None:
        """Fill form fields using the answers dict {label_text: value}."""
        import logging
        _log = logging.getLogger(__name__)

        # ── Pass 1: fill standard fields via label matching ────────────────────
        try:
            labels = popup.locator("label")
            for i in range(labels.count()):
                label_el = labels.nth(i)
                label_text = label_el.inner_text().strip().split("\n")[0].strip()

                # Strip Unicode bidirectional control characters from the DOM label
                # before dict lookup. LinkedIn embeds invisible marks (\u200f, \u202b,
                # etc.) in label text that make string equality fail even when the
                # visible text is identical to the key stored in the answers dict.
                import unicodedata as _ud_fill
                label_text_clean = "".join(
                    c for c in label_text
                    if not _ud_fill.category(c).startswith("C")
                    and c not in ("\u200f", "\u200e", "\u202a", "\u202b",
                                  "\u202c", "\u202d", "\u202e", "\u2066",
                                  "\u2067", "\u2068", "\u2069", "\u206a")
                )

                # Look up by clean label first, then raw label as fallback
                matched_key = None
                matched_value = None
                if label_text_clean in answers:
                    matched_key = label_text_clean
                    matched_value = answers[label_text_clean]
                elif label_text in answers:
                    matched_key = label_text
                    matched_value = answers[label_text]
                else:
                    continue

                container = label_el.locator("xpath=..")
                safe = matched_key.replace("\n", " ").strip()

                _log.info(f"[fill] Filling field: '{matched_key}' with value: '{matched_value}'")
                ApplyLoopService._fill_single_field(
                    page, popup, container, safe, matched_key, matched_value
                )
        except Exception as e:
            _log.warning(f"[fill_fields] Pass 1 exception: {e}")

        # ── Pass 2: fill radio groups by question text ─────────────────────────
        # Radio questions are keyed by the question text (e.g. "Are you in UAE?")
        # which does NOT appear as a <label> — it lives in a legend/span above the group.
        # We find the radio group by searching for the question text in the popup,
        # then click the radio option that matches the answer.
        try:
            for question_text, answer_value in answers.items():
                # Check if this answer was already handled in Pass 1.
                # Pass 1 only handles non-radio fields (text, select, textarea, checkbox).
                # Radio questions are NEVER handled in Pass 1 — their question text
                # lives in legend/span elements, not <label> elements.
                # We determine whether a question is a radio type by checking the
                # original questions list.
                q_type_for_this = None
                for q in (questions or []):
                    if q["label"] == question_text:
                        q_type_for_this = q["type"]
                        break

                if q_type_for_this != "radio":
                    # Non-radio: check if a label exists (was handled in Pass 1)
                    label_match = popup.locator(f'label:has-text("{question_text[:30]}")')
                    if label_match.count() > 0:
                        continue  # already handled in Pass 1

                # Look for the question text in legend, span, or div elements
                clicked = False
                for tag in ["legend", "span", "div", "p"]:
                    text_el = popup.locator(f'{tag}:has-text("{question_text[:40]}")')
                    if text_el.count() == 0:
                        continue

                    # Found the question container — look for radio inputs nearby
                    for j in range(text_el.count()):
                        el = text_el.nth(j)
                        # Walk up to find the radio group container
                        parent = el.locator("xpath=..")
                        radios = parent.locator('input[type="radio"]')

                        # Try grandparent if no radios in parent
                        if radios.count() == 0:
                            parent = el.locator("xpath=../..")
                            radios = parent.locator('input[type="radio"]')

                        if radios.count() == 0:
                            continue

                        # Collect radio options
                        radio_options = []
                        for r in range(radios.count()):
                            try:
                                opt = radios.nth(r).locator("xpath=..").inner_text().strip()
                                radio_options.append(opt)
                            except Exception:
                                radio_options.append("")

                        _log.info(f"[fill] radio group '{question_text[:60]}': answer='{answer_value}', options={radio_options}")

                        # Match and click
                        import unicodedata as _ud
                        import re as _re
                        def _clean(s):
                            return "".join(
                                c for c in s
                                if not _ud.category(c).startswith("C")
                                and c not in ("\u200f", "\u200e", "\u202a", "\u202b",
                                              "\u202c", "\u202d", "\u202e")
                            )
                        def normalize(s):
                            return _re.sub(r"[^\w\s]", "", _clean(s).strip().lower())

                        target = _clean(str(answer_value)).strip().lower()
                        target_norm = normalize(str(answer_value))
                        clicked = False

                        # Match by exact then normalized — click via dispatch_event
                        # dispatch_event is confirmed as the only reliable method
                        # for LinkedIn's hidden radio inputs (label intercepts pointer events)
                        clicked = False
                        for r in range(radios.count()):
                            opt = radio_options[r] if r < len(radio_options) else ""
                            opt_clean = _clean(opt).strip().lower()
                            opt_norm = normalize(opt)
                            if opt_clean == target or opt_norm == target_norm:
                                try:
                                    radio_input = radios.nth(r)
                                    radio_input.dispatch_event("click")
                                    page.wait_for_timeout(400)
                                    is_checked = radio_input.is_checked()
                                    _log.info(f"[fill] radio dispatch: '{opt}' is_checked={is_checked}")
                                    if not is_checked:
                                        # Secondary: dispatch on the label wrapper
                                        radio_input.locator("xpath=..").dispatch_event("click")
                                        page.wait_for_timeout(400)
                                    clicked = True
                                    break
                                except Exception as e:
                                    _log.warning(f"[fill] radio dispatch failed for '{opt}': {e}")

                        if clicked:
                            break  # stop searching for this question
                    if clicked:
                        break  # stop iterating tags for this question

        except Exception as e:
            _log.warning(f"[fill_fields] Pass 2 exception: {e}")




    @staticmethod
    def _fill_single_field(page, popup, container, safe, label_text, value) -> None:
        """Attempt to fill a single field — tries all field types in order."""
        import logging
        import re as _re
        _log = logging.getLogger(__name__)

        # ── Text / Number input — container first ─────────────────────────────
        inp = container.locator("input")
        if inp.count() > 0:
            inp_type = inp.first.get_attribute("type")
            if inp_type in ("text", "email", "tel", "number"):
                fill_value = str(value)

                # ── Autocomplete detection ─────────────────────────────────────
                # LinkedIn autocomplete inputs have role="combobox" or
                # aria-autocomplete="list". These require selecting from a
                # suggestion list — plain fill() is rejected by validation.
                _inp_role = inp.first.get_attribute("role") or ""
                _inp_autocomplete = inp.first.get_attribute("aria-autocomplete") or ""
                _inp_haspopup = inp.first.get_attribute("aria-haspopup") or ""
                _is_autocomplete = (
                    _inp_role == "combobox"
                    or _inp_autocomplete == "list"
                    or _inp_haspopup == "listbox"
                )

                if _is_autocomplete:
                    try:
                        # ── City/location equivalence map ──────────────────────────
                        # Maps Latin city names to their Arabic equivalents.
                        # Used when LinkedIn's suggestion list is in Arabic locale
                        # and Latin-script scoring produces no confident match.
                        # Keys are lowercase Latin. Values are Arabic strings to match
                        # against suggestion text using substring search.
                        _CITY_AR_MAP = {
                            "dubai":        "دبي",
                            "abu dhabi":    "أبوظبي",
                            "sharjah":      "الشارقة",
                            "ajman":        "عجمان",
                            "al ain":       "العين",
                            "ras al khaimah": "رأس الخيمة",
                            "fujairah":     "الفجيرة",
                            "umm al quwain": "أم القيوين",
                            "riyadh":       "الرياض",
                            "jeddah":       "جدة",
                            "cairo":        "القاهرة",
                            "amman":        "عمان",
                            "beirut":       "بيروت",
                            "kuwait city":  "الكويت",
                            "doha":         "الدوحة",
                            "manama":       "المنامة",
                            "muscat":       "مسقط",
                            "london":       "لندن",
                            "new york":     "نيويورك",
                            "paris":        "باريس",
                            "berlin":       "برلين",
                            "toronto":      "تورنتو",
                            "sydney":       "سيدني",
                            "singapore":    "سنغافورة",
                            "damascus":     "دمشق",
                            "baghdad":      "بغداد",
                        }

                        def _is_arabic_text(s: str) -> bool:
                            """Return True if the string contains Arabic script characters."""
                            return any("\u0600" <= c <= "\u06ff" for c in s)

                        def _score_option(opt_text: str, target_norm: str) -> int:
                            """
                            Score an option against the target (Latin script).
                            Returns: 3=exact, 2=first-segment exact, 1=starts-with,
                                     0=contains, -1=no match.
                            """
                            opt_norm = _re.sub(r"[^\w\s]", "", opt_text.lower())
                            first_seg = _re.sub(
                                r"[^\w\s]", "",
                                opt_text.split(",")[0].strip().lower()
                            )
                            if opt_norm == target_norm:
                                return 3
                            if first_seg == target_norm:
                                return 2
                            if opt_norm.startswith(target_norm):
                                return 1
                            if target_norm in opt_norm:
                                return 0
                            return -1

                        def _score_option_arabic(opt_text: str, arabic_equiv: str) -> int:
                            """
                            Score an Arabic-script option against the Arabic equivalent
                            of the Latin target.
                            Returns: 2=first-segment contains arabic_equiv,
                                     1=option contains arabic_equiv anywhere, -1=no match.
                            Score capped at 2 — Arabic matching is less precise than
                            Latin exact matching (score 3 reserved for Latin exact).
                            """
                            first_seg = opt_text.split("،")[0].strip()  # Arabic comma
                            if arabic_equiv in first_seg:
                                return 2
                            if arabic_equiv in opt_text:
                                return 1
                            return -1

                        # 1) Focus and clear the field
                        inp.first.click()
                        page.wait_for_timeout(200)
                        inp.first.fill("")
                        page.wait_for_timeout(200)

                        # 2) Type character by character to trigger React onChange
                        inp.first.type(fill_value, delay=80)

                        # 3) Wait for suggestion listbox to appear (up to 4 seconds)
                        try:
                            page.wait_for_selector(
                                'ul[role="listbox"], div[role="listbox"]',
                                timeout=4000
                            )
                        except Exception:
                            _log.warning(f"[fill] autocomplete '{label_text}': no listbox appeared, falling back to plain fill")
                            inp.first.fill(fill_value)
                            page.wait_for_timeout(300)
                            _log.info(f"[fill] autocomplete fallback plain fill '{label_text}' = '{fill_value}'")
                            return

                        # 4) Read all visible options
                        options = page.locator(
                            'ul[role="listbox"] li[role="option"], '
                            'div[role="listbox"] div[role="option"]'
                        )
                        option_count = options.count()

                        if option_count == 0:
                            _log.warning(f"[fill] autocomplete '{label_text}': listbox appeared but no options found")
                            return

                        # 5) Collect option texts (up to 10)
                        option_texts = []
                        for i in range(min(option_count, 10)):
                            try:
                                option_texts.append(options.nth(i).inner_text().strip())
                            except Exception:
                                option_texts.append("")

                        # 6) Detect whether suggestions are in Arabic script
                        suggestions_are_arabic = any(
                            _is_arabic_text(t) for t in option_texts if t
                        )
                        _log.info(
                            f"[fill] autocomplete '{label_text}': "
                            f"suggestions_are_arabic={suggestions_are_arabic}, "
                            f"options={option_texts[:3]}"
                        )

                        target_norm = _re.sub(r"[^\w\s]", "", fill_value.strip().lower())
                        best_index = -1
                        best_score = -1

                        if not suggestions_are_arabic:
                            # ── Latin UI: existing scoring logic ──────────────────
                            for i, opt_text in enumerate(option_texts):
                                score = _score_option(opt_text, target_norm)
                                if score > best_score:
                                    best_score = score
                                    best_index = i
                                if best_score == 3:
                                    break

                        else:
                            # ── Arabic UI: match via Arabic equivalence map ────────
                            arabic_equiv = _CITY_AR_MAP.get(fill_value.strip().lower())
                            if arabic_equiv:
                                for i, opt_text in enumerate(option_texts):
                                    score = _score_option_arabic(opt_text, arabic_equiv)
                                    if score > best_score:
                                        best_score = score
                                        best_index = i
                                    if best_score == 2:
                                        break
                                _log.info(
                                    f"[fill] autocomplete '{label_text}': "
                                    f"Arabic match for '{fill_value}' → '{arabic_equiv}', "
                                    f"best_score={best_score}, best_index={best_index}"
                                )
                            else:
                                _log.warning(
                                    f"[fill] autocomplete '{label_text}': "
                                    f"'{fill_value}' not in Arabic map, will use keyboard fallback"
                                )

                        # 7) Click if confident match found (score >= 2 for Latin,
                        #    score >= 1 for Arabic since Arabic substring match is reliable)
                        min_confidence = 2 if not suggestions_are_arabic else 1
                        if best_score >= min_confidence and best_index >= 0:
                            try:
                                opt_text = option_texts[best_index]
                                options.nth(best_index).click()
                                page.wait_for_timeout(400)
                                _log.info(
                                    f"[fill] autocomplete '{label_text}': "
                                    f"clicked '{opt_text}' (score={best_score}) "
                                    f"for value '{fill_value}'"
                                )
                                return
                            except Exception as e:
                                _log.warning(
                                    f"[fill] autocomplete '{label_text}': "
                                    f"click failed: {e}, falling back to keyboard"
                                )

                        # 8) Last resort: keyboard selection.
                        # Only reaches here if:
                        # - Arabic UI and city not in map, OR
                        # - Latin UI and no segment match, OR
                        # - Click failed after match
                        try:
                            inp.first.press("ArrowDown")
                            page.wait_for_timeout(300)
                            inp.first.press("Enter")
                            page.wait_for_timeout(400)
                            _log.info(
                                f"[fill] autocomplete '{label_text}': "
                                f"keyboard-selected first suggestion for value '{fill_value}' "
                                f"(suggestions_are_arabic={suggestions_are_arabic})"
                            )
                        except Exception as e:
                            _log.warning(
                                f"[fill] autocomplete '{label_text}': "
                                f"keyboard selection failed: {e}"
                            )
                        return

                    except Exception as e:
                        _log.warning(f"[fill] autocomplete '{label_text}': handler failed: {e}")
                        return

                # ── Numeric sanitization ───────────────────────────────────────
                # A field is numeric only when inp_type is explicitly "number",
                # OR when both min/step are present AND the value is already
                # a digit string. This prevents Yes/No text fields from being
                # misclassified as numeric just because LinkedIn sets min="0".
                _inp_pattern = inp.first.get_attribute("pattern") or ""
                _inp_id = inp.first.get_attribute("id") or ""
                _value_is_digit_string = bool(_re.match(r"^\d+\.?\d*$", fill_value.strip()))
                _is_numeric_field = (
                    inp_type == "number"
                    or (
                        (
                            inp.first.get_attribute("min") is not None
                            or inp.first.get_attribute("step") is not None
                            or bool(_re.search(r"[\d\\]", _inp_pattern))
                            or _inp_id.endswith("-numeric")
                        )
                        and _value_is_digit_string
                    )
                )
                if _is_numeric_field:
                    original = fill_value
                    digits = _re.sub(r"[^\d.]", "", fill_value)
                    parts = digits.split(".")
                    if len(parts) > 2:
                        digits = parts[0] + "." + "".join(parts[1:])
                    digits = digits.rstrip(".")
                    # Only apply minimum if the field explicitly requires > 0
                    # (inp_type == "number" with min > 0, or step attribute present).
                    # Do NOT override legitimate zero answers like "0 years experience".
                    _inp_min = inp.first.get_attribute("min")
                    _inp_step = inp.first.get_attribute("step")
                    _requires_positive = (
                        inp_type == "number"
                        and (
                            (_inp_min is not None and _inp_min not in ("", "0", "0.0"))
                            or _inp_step is not None
                        )
                    )
                    if digits in ("", ):
                        digits = "1"
                        _log.info(f"[fill] Numeric field '{label_text}': original='{original}' empty → minimum='1'")
                    elif digits in ("0", "0.0") and _requires_positive:
                        digits = "1"
                        _log.info(f"[fill] Numeric field '{label_text}': original='{original}' zero on required-positive field → '1'")
                    else:
                        _log.info(f"[fill] Numeric field '{label_text}': original='{original}' sanitized='{digits}'")
                    fill_value = digits
                # ── Detect decimal-validated fields ────────────────────────────
                # LinkedIn's decimal-validated type=text fields (e.g. "Expected
                # Salary (per month)") use React's onChange/onInput to validate.
                # Playwright's fill() injects the value directly into the DOM
                # without firing synthetic React events, so React never registers
                # the change. On submit, React treats the field as untouched and
                # the decimal validator fires ("Enter a decimal number between...").
                #
                # Detection: any combination of min/step/pattern/inputmode that
                # signals a numeric/decimal constraint on a type=text input.
                # We do NOT check inp_type == "number" here — native number inputs
                # handle fill() correctly via their own event wiring.
                #
                # Fix: replace fill() with a keyboard-driven sequence that goes
                # through the browser's input event pipeline and fires all React
                # synthetic events (focus → select-all → type → blur).
                # This is only applied when the field is type=text AND has decimal
                # validation attributes — all other fields keep the fast fill() path.
                _inp_inputmode = inp.first.get_attribute("inputmode") or ""
                _inp_min_attr  = inp.first.get_attribute("min")
                _inp_step_attr = inp.first.get_attribute("step")
                _has_decimal_validation = (
                    inp_type == "text"
                    and (
                        _inp_inputmode in ("decimal", "numeric")
                        or _inp_min_attr is not None
                        or _inp_step_attr is not None
                        or bool(_re.search(r"[\d.]", _inp_pattern))
                    )
                )

                if _has_decimal_validation:
                    # Keyboard-driven fill: triggers React synthetic events
                    try:
                        inp.first.click()
                        page.wait_for_timeout(150)
                        # Select-all then type replaces any pre-existing value
                        inp.first.press("Control+a")
                        page.wait_for_timeout(50)
                        inp.first.type(fill_value, delay=30)
                        # Dispatch input + change events explicitly to ensure
                        # React state update is committed before submit
                        inp.first.dispatch_event("input")
                        inp.first.dispatch_event("change")
                        page.wait_for_timeout(200)
                        _log.info(f"[fill] text/number (decimal keyboard) '{label_text}' = '{fill_value}'")
                        return
                    except Exception as e:
                        _log.warning(
                            f"[fill] decimal keyboard fill failed for '{label_text}': {e}"
                            f" — falling back to fill()"
                        )

                try:
                    inp.first.fill(fill_value)
                    page.wait_for_timeout(200)
                    _log.info(f"[fill] text/number '{label_text}' = '{fill_value}'")
                    return
                except Exception as e:
                    _log.warning(f"[fill] text input failed for '{label_text}': {e}")

        # ── Text input — aria-label fallback ──────────────────────────────────
        aria_inp = popup.locator(f'input[aria-label="{safe}"]')
        if aria_inp.count() > 0:
            inp_type = aria_inp.first.get_attribute("type")
            fill_value = str(value)
            _aria_pattern = aria_inp.first.get_attribute("pattern") or ""
            _is_aria_numeric = (
                inp_type == "number"
                or aria_inp.first.get_attribute("min") is not None
                or aria_inp.first.get_attribute("step") is not None
                or bool(_re.search(r"[\d\\]", _aria_pattern))
            )
            if _is_aria_numeric:
                original = fill_value
                digits = _re.sub(r"[^\d.]", "", fill_value)
                parts = digits.split(".")
                if len(parts) > 2:
                    digits = parts[0] + "." + "".join(parts[1:])
                digits = digits.rstrip(".")
                _log.info(f"[fill] Numeric aria-label '{label_text}': original='{original}' sanitized='{digits}'")
                fill_value = digits if digits else ""
            try:
                aria_inp.first.fill(fill_value)
                page.wait_for_timeout(200)
                _log.info(f"[fill] text aria-label '{label_text}' = '{fill_value}'")
                return
            except Exception as e:
                _log.warning(f"[fill] aria text input failed for '{label_text}': {e}")

        # ── Textarea ──────────────────────────────────────────────────────────
        for loc in [container.locator("textarea"), popup.locator(f'textarea[aria-label="{safe}"]')]:
            if loc.count() > 0:
                try:
                    loc.first.fill(str(value))
                    page.wait_for_timeout(200)
                    _log.info(f"[fill] textarea '{label_text}' = '{str(value)[:80]}'")
                    return
                except Exception:
                    pass

        # ── Native select ─────────────────────────────────────────────────────
        for loc in [container.locator("select"), popup.locator(f'select[aria-label="{safe}"]')]:
            if loc.count() > 0:
                import unicodedata as _ud2
                def _clean2(s):
                    return "".join(
                        c for c in s
                        if not _ud2.category(c).startswith("C")
                        and c not in ("\u200f", "\u200e", "\u202a", "\u202b",
                                      "\u202c", "\u202d", "\u202e")
                    )

                target_val = _clean2(str(value)).strip().lower()

                # Get all options from the select element
                try:
                    all_opts = loc.first.locator("option").all()
                    opt_texts = [o.inner_text().strip() for o in all_opts]
                    opt_values = [o.get_attribute("value") or "" for o in all_opts]
                except Exception:
                    opt_texts, opt_values = [], []

                # Pass 1: try direct select_option (exact value or label)
                try:
                    loc.first.select_option(str(value))
                    page.wait_for_timeout(200)
                    _log.info(f"[fill] select exact '{label_text}' = '{value}'")
                    return
                except Exception:
                    pass

                # Pass 2: case-insensitive + cleaned label match
                matched = None
                for i, opt_text in enumerate(opt_texts):
                    if _clean2(opt_text).strip().lower() == target_val:
                        matched = opt_values[i] if opt_values[i] else opt_text
                        break

                # Pass 3: normalized fuzzy match
                if matched is None:
                    import re as _re2
                    def norm2(s):
                        return _re2.sub(r"[^\w\s]", "", _clean2(s).strip().lower())
                    target_norm2 = norm2(str(value))
                    for i, opt_text in enumerate(opt_texts):
                        if norm2(opt_text) == target_norm2:
                            matched = opt_values[i] if opt_values[i] else opt_text
                            break

                # Pass 4: substring match
                if matched is None:
                    for i, opt_text in enumerate(opt_texts):
                        if target_val in _clean2(opt_text).strip().lower():
                            matched = opt_values[i] if opt_values[i] else opt_text
                            break

                if matched is not None:
                    try:
                        loc.first.select_option(matched)
                        page.wait_for_timeout(200)
                        _log.info(f"[fill] select fallback '{label_text}' = '{matched}'")
                        return
                    except Exception:
                        pass

                # Pass 5: first non-empty option as last resort
                for i, opt_text in enumerate(opt_texts):
                    if opt_text and opt_text.lower() not in ("select an option", "select", "اختر"):
                        try:
                            loc.first.select_option(index=i)
                            page.wait_for_timeout(200)
                            _log.warning(f"[fill] select last-resort '{label_text}' chose first option: '{opt_text}'")
                            return
                        except Exception:
                            pass

                _log.warning(f"[fill] select '{label_text}': no match for '{value}' in {opt_texts}")

        # ── Radio buttons — robust matching ───────────────────────────────────
        radios = container.locator('input[type="radio"]')
        if radios.count() > 0:
            # Collect all options for logging
            radio_options = []
            for r in range(radios.count()):
                try:
                    opt_text = radios.nth(r).locator("xpath=..").inner_text().strip()
                    radio_options.append(opt_text)  # keep original for clicking
                except Exception:
                    radio_options.append("")

            _log.info(f"[fill] radio '{label_text}': value='{value}', options={radio_options}")
            

            import unicodedata as _ud
            def _clean(s):
                return "".join(
                    c for c in s
                    if not _ud.category(c).startswith("C")
                    and c not in ("\u200f", "\u200e", "\u202a", "\u202b",
                                  "\u202c", "\u202d", "\u202e")
                )
            target = _clean(str(value)).strip().lower()
            # Remove common punctuation for fuzzy match
            def normalize(s):
                # Strip Unicode bidirectional marks and control characters
                # before comparison — LinkedIn embeds \u200f, \u200e etc.
                import unicodedata
                cleaned = "".join(
                    c for c in s
                    if not unicodedata.category(c).startswith("C")
                    and c not in ("\u200f", "\u200e", "\u202a", "\u202b",
                                  "\u202c", "\u202d", "\u202e", "\u2066",
                                  "\u2067", "\u2068", "\u2069", "\u206a")
                )
                return _re.sub(r"[^\w\s]", "", cleaned.strip().lower())


            # Pass 1: exact case-insensitive match
            # Pass 2: normalized fuzzy match
            # dispatch_event is the only reliable click method for LinkedIn hidden radios
            target_norm = normalize(_clean(str(value)))
            clicked = False
            for r in range(radios.count()):
                opt_text = radio_options[r]
                opt_clean = _clean(opt_text).strip().lower()
                opt_norm = normalize(_clean(opt_text))
                if opt_clean == target or opt_norm == target_norm:
                    try:
                        radio_input = radios.nth(r)
                        radio_input.dispatch_event("click")
                        page.wait_for_timeout(400)
                        is_checked = radio_input.is_checked()
                        _log.info(f"[fill] radio dispatch: '{opt_text}' is_checked={is_checked}")
                        if not is_checked:
                            radio_input.locator("xpath=..").dispatch_event("click")
                            page.wait_for_timeout(400)
                        clicked = True
                        return
                    except Exception as e:
                        _log.warning(f"[fill] radio dispatch failed for '{opt_text}': {e}")

            # Pass 3: substring fallback
            if not clicked:
                for r in range(radios.count()):
                    opt_text = radio_options[r]
                    if target in _clean(opt_text).strip().lower():
                        try:
                            radio_input = radios.nth(r)
                            radio_input.dispatch_event("click")
                            page.wait_for_timeout(400)
                            _log.warning(f"[fill] radio substring fallback: value='{value}' matched '{opt_text}'")
                            clicked = True
                            return
                        except Exception:
                            pass

            if not clicked:
                _log.warning(f"[fill] radio '{label_text}': no match found for '{value}' in {radio_options}")
            return

        # ── Checkbox ──────────────────────────────────────────────────────────
        checks = container.locator('input[type="checkbox"]')
        if checks.count() > 0 and isinstance(value, bool):
            try:
                cb = checks.first
                # Use JS to read checked state — avoids blocking on hidden inputs
                is_checked = cb.evaluate("el => el.checked")
                if value and not is_checked:
                    # dispatch_event bypasses pointer-event blocking on styled checkboxes
                    cb.dispatch_event("click")
                elif not value and is_checked:
                    cb.dispatch_event("click")
                page.wait_for_timeout(200)
                _log.info(f"[fill] checkbox '{label_text}' = {value}")
            except Exception as e:
                _log.warning(f"[fill] checkbox '{label_text}' failed: {e}")




    @staticmethod
    def _click_next(page: Page, popup) -> bool:
        """Click the Next, Continue, Review, or Submit button. Returns True if clicked."""
        selectors = [
            'button[aria-label="Submit application"]',
            'button[aria-label*="Submit"]',
            'button[aria-label*="تقديم"]',
            'button[aria-label*="إرسال"]',
            'button[aria-label="Continue to next step"]',
            'button[aria-label="الاستمرار للخطوة التالية"]',
            'button[aria-label="Review your application"]',
            'button[aria-label="Review"]',
            'button:has-text("Submit application")',
            'button:has-text("Submit")',
            'button:has-text("Review")',
            'button:has-text("Review application")',
            'button:has-text("Review your application")',
            'button:has-text("Next")',
            'button:has-text("Continue")',
            'button:has-text("Continue to next step")',
            'button:has-text("Done")',
            'button:has-text("مراجعة")',
            'button:has-text("مراجعة الطلب")',
            'button:has-text("التالي")',
            'button:has-text("إرسال")',
            'button:has-text("إرسال الطلب")',
            'button:has-text("تقديم الطلب")',
            'button:has-text("تم")',
        ]

        import logging
        _log = logging.getLogger(__name__)

        for selector in selectors:
            btn = popup.locator(selector)
            if btn.count() == 0:
                btn = page.locator(selector)

            if btn.count() > 0:

                # 1) Scroll inside the popup
                try:
                    popup.evaluate("el => el.scrollTo(0, el.scrollHeight)")
                except Exception:
                    pass

                # 2) Remove LinkedIn overlay that intercepts clicks
                try:
                    page.evaluate("""
                        () => {
                            const overlays = document.querySelectorAll(
                                '[data-test-modal-overlay], .artdeco-modal-overlay'
                            );
                            overlays.forEach(o => o.style.display = 'none');
                        }
                    """)
                except Exception:
                    pass

                # 3) Scroll button into view
                try:
                    btn.first.scroll_into_view_if_needed()
                except Exception:
                    pass

                # 4) Normal click — goes through React event system
                # Do NOT use force=True — it bypasses React onClick handlers
                try:
                    btn_text = btn.first.inner_text().strip()
                    btn.first.click(timeout=5000)
                    page.wait_for_timeout(1500)
                    _log.info(f"[click_next] Clicked: '{btn_text}'")
                    return True
                except Exception as e:
                    # If normal click fails due to overlay, try dispatching click event via JS
                    # This triggers React's synthetic event system directly
                    try:
                        btn_text = btn.first.inner_text().strip()
                        btn.first.dispatch_event("click")
                        page.wait_for_timeout(1500)
                        _log.info(f"[click_next] JS dispatch clicked: '{btn_text}'")
                        return True
                    except Exception as e2:
                        _log.warning(f"[click_next] Both click methods failed: {e2}")
                        pass

        return False




    @staticmethod
    def _is_submission_confirmed(page, popup, page_num: int, _log) -> bool:
        """
        Determine whether LinkedIn is showing a submission confirmation screen.

        Uses three independent signals — all must agree:
          1. No form input fields remain (inputs, selects, textareas)
          2. No navigation buttons remain (Next, Submit, Review, التالي...)
          3. Text confirmation — either a long known phrase OR
             the popup's trimmed text is exactly "تم" (the short Arabic confirmation)

        "تم" is NEVER matched as a substring — only as the complete trimmed text
        of a short confirmation popup that also passes signals 1 and 2.
        """
        try:
            popup_el = popup.first

            # ── Signal 1: No form input fields ────────────────────────────────
            has_inputs = popup_el.locator(
                "input, select, textarea"
            ).count() > 0

            # ── Signal 2: No navigation/submit buttons ─────────────────────────
            nav_selectors = [
                'button:has-text("Next")',
                'button:has-text("Continue")',
                'button:has-text("Review")',
                'button:has-text("Submit")',
                'button:has-text("التالي")',
                'button:has-text("متابعة")',
                'button:has-text("مراجعة")',
                'button:has-text("إرسال")',
                'button:has-text("تقديم")',
                'button[aria-label*="Submit"]',
                'button[aria-label*="Continue"]',
                'button[aria-label*="الاستمرار"]',
            ]
            has_nav_buttons = any(
                popup_el.locator(sel).count() > 0
                for sel in nav_selectors
            )

            popup_text = popup_el.inner_text().strip()
            popup_text_lower = popup_text.lower()
            _log.info(
                f"[apply_loop] page {page_num+1}: "
                f"has_inputs={has_inputs}, has_nav_buttons={has_nav_buttons}, "
                f"popup_text_snippet='{popup_text[:150]}'"
            )

            # ── Signal 3a: Long known confirmation phrases ─────────────────────
            # These are long enough to never appear in file names or timestamps
            long_confirmations = [
                "your application was sent",
                "application was sent",
                "application submitted",
                "successfully applied",
                "تم إرسال طلبك",
                "تم تقديم طلبك",
                "تم التقديم بنجاح",
                "تم إرسال طلب التوظيف",
                "تم إرسال الاستمارة",
                "تم إرسال استمارتك",
            ]
            has_long_confirmation = any(
                phrase in popup_text_lower
                for phrase in long_confirmations
            )

            # ── Signal 3b: Exact short Arabic confirmation ─────────────────────
            # "تم" is valid ONLY when:
            #   - it is the entire trimmed popup text, OR
            #   - the popup is very short (< 20 chars) and contains only "تم"
            # Never matched as substring inside longer text.
            short_confirmation_phrases = ["تم", "تم بنجاح", "done"]
            has_short_confirmation = (
                popup_text.strip() in short_confirmation_phrases
                or (
                    len(popup_text.strip()) <= 20
                    and popup_text.strip() in short_confirmation_phrases
                )
            )

            has_text_confirmation = has_long_confirmation or has_short_confirmation

            # ── Final decision ─────────────────────────────────────────────────
            # Confirmed if text matches AND the form state agrees
            # (no inputs + no nav buttons = not a form page)
            if has_text_confirmation and not has_inputs and not has_nav_buttons:
                _log.info(
                    f"[apply_loop] Submission confirmed: "
                    f"text_confirmed={has_text_confirmation}, "
                    f"no_inputs={not has_inputs}, no_nav_buttons={not has_nav_buttons}"
                )
                return True

            # ── Partial signal: text confirmed but UI ambiguous ────────────────
            # Only trust long phrases even without UI agreement
            if has_long_confirmation:
                _log.info(
                    f"[apply_loop] Submission confirmed via long phrase "
                    f"(UI state ambiguous)"
                )
                return True

            return False

        except Exception as e:
            _log.warning(f"[apply_loop] Confirmation check error: {e}")
            return False
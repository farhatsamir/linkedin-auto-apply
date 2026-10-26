from playwright.sync_api import Page # type: ignore
import time
import urllib.parse as urlparse
import uuid


class ApplyService:

    sessions = {}

    @staticmethod
    def apply(page: Page, job_link: str):

        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.set_event_loop(None)
        except RuntimeError:
            pass

        # ---------------------------------------------------------
        # 0) تحويل رابط search إلى رابط view
        # ---------------------------------------------------------
        try:
            if "currentJobId=" in job_link:
                parsed = urlparse.urlparse(job_link)
                params = urlparse.parse_qs(parsed.query)
                if "currentJobId" in params:
                    job_id = params["currentJobId"][0]
                    job_link = f"https://www.linkedin.com/jobs/view/{job_id}/"
        except:
            pass

        # ---------------------------------------------------------
        # 1) فتح صفحة الوظيفة
        # ---------------------------------------------------------
        try:
            page.goto(job_link, timeout=20000)
            time.sleep(2.5)
        except:
            return {
                "status": "failed",
                "job_title": "Unknown",
                "company": "Unknown",
                "job_link": job_link,
                "job_description": "Not Found",
                "questions": [],
                "session_id": None,
                "error_message": "Failed to load job page"
            }

        # 2) إيجاد زر Easy Apply (الإصلاح هنا)
        # ---------------------------------------------------------
        easy_apply_element = None
        easy_texts = ["Easy Apply", "التقديم السريع"]

        try:
            for txt in easy_texts:
                locator = page.locator(f"text={txt}")  # ← Locator كامل
                if locator.count() > 0:
                    easy_apply_element = locator.first  # ← نأخذ first بعد count
                    break
        except:
            pass

        if not easy_apply_element:
            return {
                "status": "failed",
                "job_title": "Unknown",
                "company": "Unknown",
                "job_link": job_link,
                "job_description": "Not Found",
                "questions": [],
                "session_id": None,
                "error_message": "Easy Apply not found"
            }

        # ---------------------------------------------------------
        # 3) استخراج وصف الوظيفة
        # ---------------------------------------------------------
        job_description = "Not Found"

        try:
            # Step 1: Wait intelligently for the description container to appear.
            # LinkedIn renders the description asynchronously — we wait for a known
            # stable selector rather than using a fixed timeout.
            # Timeout of 8s covers slow connections; fails gracefully if not found.
            try:
                page.wait_for_selector(
                    ".jobs-description__content, "
                    ".jobs-description-content__text, "
                    "[data-test-job-description], "
                    ".jobs-box__html-content",
                    timeout=8000
                )
            except:
                # Selector not found within timeout — page may use a different layout.
                # Proceed anyway; the extraction below has its own fallback chain.
                pass

            # Step 2: Expand the description if truncated ("See more" button).
            page.evaluate("""
                () => {
                    const buttons = [...document.querySelectorAll('button, span, a')];
                    const targets = [
                        'المزيد', 'عرض المزيد', 'See more', 'Show more', 'More'
                    ];
                    for (const btn of buttons) {
                        const text = btn.innerText?.trim();
                        if (text && targets.includes(text)) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            page.wait_for_timeout(600)

            # Step 3: Extract from known LinkedIn description containers.
            # Selectors are tried in priority order — most specific first.
            # None of these selectors can match the sidebar or recommendations panel.
            job_description = page.evaluate("""
                () => {
                    const selectors = [
                        '.jobs-description__content',
                        '.jobs-description-content__text',
                        '[data-test-job-description]',
                        '.jobs-box__html-content',
                        '.description__text',
                        '.job-view-layout .jobs-description',
                        'article.jobs-description',
                    ];

                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const text = el.innerText.trim();
                            if (text.length > 80) return text;
                        }
                    }

                    // Fallback: find the section whose heading indicates job details.
                    // This handles LinkedIn layout variants that use custom containers.
                    const headingKeywords = [
                        'about this job', 'about the job', 'job description',
                        'role description', 'about the role', 'responsibilities',
                        'لمحة حول', 'وصف الوظيفة', 'عن الوظيفة'
                    ];
                    const headings = [...document.querySelectorAll('h1, h2, h3, h4, strong')];
                    for (const h of headings) {
                        const hText = h.innerText.trim().toLowerCase();
                        if (headingKeywords.some(kw => hText.includes(kw))) {
                            // Walk up to find the section container
                            let container = h.parentElement;
                            for (let i = 0; i < 3; i++) {
                                if (container && container.innerText.trim().length > 200) {
                                    return container.innerText.trim();
                                }
                                container = container?.parentElement;
                            }
                        }
                    }

                    return "Not Found";
                }
            """)
        except:
            pass

        # ---------------------------------------------------------
        # 4) استخراج اسم الشركة
        # ---------------------------------------------------------
        company = "Unknown"
        try:
            company_el = page.locator('a[href*="/company/"]')
            if company_el.count() > 0:
                company_el = company_el.first
                if company_el.is_visible():
                    text = company_el.inner_text().strip()
                    if text:
                        company = text
        except:
            pass

        # ---------------------------------------------------------
        # 5) استخراج اسم الوظيفة
        # ---------------------------------------------------------
        job_title = "Unknown"
        try:
            p_tags = page.locator("p").all()
            for p in p_tags:
                text = p.inner_text().strip()
                if not text or len(text) < 3:
                    continue
                if text == company:
                    continue
                bad_keywords = ["Premium", "حساب", "AED", "جرب", "تجربة", "ترقية"]
                if any(bad in text for bad in bad_keywords):
                    continue
                bad_location = ["الإمارات", "دبي", "منذ", "متقدم", "·"]
                if any(bad in text for bad in bad_location):
                    continue
                has_english = any("a" <= ch.lower() <= "z" for ch in text)
                if not has_english:
                    continue
                job_title = text
                break
        except:
            pass
        

        # ---------------------------------------------------------
        # 6) الضغط على Easy Apply
        # ---------------------------------------------------------
        try:
            easy_apply_element.click()
            time.sleep(2)
        except:
            return {
                "status": "failed",
                "job_title": job_title,
                "company": company,
                "job_link": job_link,
                "job_description": job_description,
                "questions": [],
                "session_id": None,
                "error_message": "Failed to click Easy Apply"
            }

        # ---------------------------------------------------------
        # 7) التأكد من ظهور Popup أو Full Apply
        # ---------------------------------------------------------

        # 7.1 — فحص: هل ظهرت البوب‑أب؟
        popup = page.locator('div[role="dialog"]')
        if popup.count() > 0 and popup.first.is_visible():
            pass  # ممتاز، البوب‑أب ظهرت

        else:
            # 7.2 — فحص: هل انتقل لصفحة Full Apply؟
            if "/apply/" in page.url or "/jobs/apply/" in page.url:
                return {
                    "status": "full_apply_page",
                    "job_title": job_title,
                    "company": company,
                    "job_link": job_link,
                    "job_description": job_description,
                    "questions": [],
                    "session_id": None,
                    "error_message": "Full Apply page detected"
                }

            # 7.3 — فحص: هل الزر لم يعمل؟
            easy_apply_button = page.locator('button:has-text("Easy Apply")')
            if easy_apply_button.count() > 0 and easy_apply_button.first.is_visible():
                return {
                    "status": "failed",
                    "job_title": job_title,
                    "company": company,
                    "job_link": job_link,
                    "job_description": job_description,
                    "questions": [],
                    "session_id": None,
                    "error_message": "Easy Apply button did not trigger popup"
                }

            # 7.4 — فحص: overlay يمنع ظهور البوب‑أب
            page.wait_for_timeout(2000)
            popup = page.locator('div[role="dialog"]')
            if popup.count() == 0:
                return {
                    "status": "failed",
                    "job_title": job_title,
                    "company": company,
                    "job_link": job_link,
                    "job_description": job_description,
                    "questions": [],
                    "session_id": None,
                    "error_message": "Popup not found after Easy Apply"
                }


        # ---------------------------------------------------------
        # 8) استخراج الأسئلة
        # ---------------------------------------------------------
        questions = []
        try:
            label_elements = popup.locator("label")
            count = label_elements.count()

            for i in range(count):
                label_el = label_elements.nth(i)
                label_text = label_el.inner_text().strip().split("\n")[0].strip()
                if not label_text or len(label_text) < 2:
                    continue

                field_type = "unknown"
                container = label_el.locator("xpath=..")
                input_el = container.locator("input, select, textarea, button")

                if input_el.count() > 0:
                    tag = input_el.first.evaluate("el => el.tagName.toLowerCase()")
                    input_type = input_el.first.get_attribute("type")

                    if tag == "input":
                        if input_type in ["text", "email", "tel", "number"]:
                            field_type = "text"
                        elif input_type == "file":
                            field_type = "file"
                    elif tag == "select":
                        field_type = "dropdown"
                    elif tag == "textarea":
                        field_type = "textarea"
                    elif tag == "button":
                        field_type = "dropdown"

                questions.append({
                    "question": label_text,
                    "type": field_type
                })

        except Exception as e:
            print("Question extraction error:", e)

        # ---------------------------------------------------------
        # 9) إنشاء session_id وتخزين الصفحة
        # ---------------------------------------------------------
        session_id = str(uuid.uuid4())
        ApplyService.sessions[session_id] = page

        # ---------------------------------------------------------
        # 10) إرجاع النتيجة
        # ---------------------------------------------------------
        return {
            "status": "questions_extracted",
            "job_title": job_title,
            "company": company,
            "job_link": job_link,
            "job_description": job_description,
            "questions": questions,
            "session_id": session_id,
            "error_message": None
        }








    @staticmethod
    def continue_apply(session_id: str, answers: dict):

        # ---------------------------------------------------------
        # 1) التأكد أن session_id موجود
        # ---------------------------------------------------------
        if session_id not in ApplyService.sessions:
            return {"status": "failed", "error_message": "Session not found"}

        # ---------------------------------------------------------
        # 2) استرجاع الصفحة
        # ---------------------------------------------------------
        page = ApplyService.sessions[session_id]

        if page is None:
            return {"status": "failed", "error_message": "Page not found in session"}

        # ---------------------------------------------------------
        # 3) التأكد أن الصفحة ما زالت مفتوحة
        # ---------------------------------------------------------
        try:
            page.title()
        except:
            return {"status": "failed", "error_message": "Page is closed or unreachable"}

        # ---------------------------------------------------------
        # 4) تعبئة الحقول
        # ---------------------------------------------------------
        filled_fields = []
        dropdown_filled = []
        radio_filled = []
        checkbox_filled = []
        textarea_filled = []

        try:
            popup = page.locator('div[role="dialog"]')
            if popup.count() == 0:
                popup = page  # fallback للصفحة كاملة

            label_elements = popup.locator("label")
            count = label_elements.count()

            for i in range(count):

                label_el = label_elements.nth(i)
                label_text = label_el.inner_text().strip().split("\n")[0].strip()

                if label_text not in answers:
                    continue

                value = answers[label_text]
                container = label_el.locator("xpath=..")

                safe_label = label_text.replace("\n", " ").strip()

                # ---------------------------------------------------------
                # TEXT INPUT داخل container
                # ---------------------------------------------------------
                input_el = container.locator("input")
                if input_el.count() > 0:
                    input_type = input_el.first.get_attribute("type")
                    if input_type in ["text", "email", "tel", "number"]:
                        try:
                            input_el.first.fill(str(value))
                            page.wait_for_timeout(200)
                            filled_fields.append(label_text)
                            continue
                        except:
                            pass

                # ---------------------------------------------------------
                # TEXT INPUT aria-label مطابق فقط
                # ---------------------------------------------------------
                aria_input = popup.locator(f'input[aria-label="{safe_label}"]')
                if aria_input.count() > 0:
                    try:
                        aria_input.first.fill(str(value))
                        page.wait_for_timeout(200)
                        filled_fields.append(label_text)
                        continue
                    except:
                        pass

                # ---------------------------------------------------------
                # TEXTAREA داخل نفس الـ container (الأدق)
                # ---------------------------------------------------------
                textarea_local = container.locator("textarea")
                if textarea_local.count() > 0:
                    try:
                        textarea_local.first.fill(str(value))
                        page.wait_for_timeout(200)
                        textarea_filled.append(label_text)
                        continue
                    except:
                        pass

                # ---------------------------------------------------------
                # TEXTAREA aria-label مطابق فقط
                # ---------------------------------------------------------
                textarea_el = popup.locator(f'textarea[aria-label="{safe_label}"]')
                if textarea_el.count() > 0:
                    try:
                        textarea_el.first.fill(str(value))
                        page.wait_for_timeout(200)
                        textarea_filled.append(label_text)
                        continue
                    except:
                        pass

                # ---------------------------------------------------------
                # SELECT داخل container
                # ---------------------------------------------------------
                select_el = container.locator("select")
                if select_el.count() > 0:
                    try:
                        select_el.first.select_option(str(value))
                        page.wait_for_timeout(200)
                        dropdown_filled.append(label_text)
                        continue
                    except:
                        pass

                # ---------------------------------------------------------
                # SELECT خارج container (aria-label مطابق فقط)
                # ---------------------------------------------------------
                select_global = popup.locator(f'select[aria-label="{safe_label}"]')
                if select_global.count() > 0:
                    try:
                        select_global.first.select_option(str(value))
                        page.wait_for_timeout(200)
                        dropdown_filled.append(label_text)
                        continue
                    except:
                        pass

                # ---------------------------------------------------------
                # RADIO خارج container (باستخدام safe_label)
                # ---------------------------------------------------------
                radio_global = popup.locator(f"label:has-text('{safe_label}')")
                if radio_global.count() > 0:
                    try:
                        radio_global.first.click()
                        page.wait_for_timeout(200)
                        radio_filled.append(label_text)
                        continue
                    except:
                        pass

                # ---------------------------------------------------------
                # RADIO داخل container
                # ---------------------------------------------------------
                radio_inputs = container.locator('input[type="radio"]')
                if radio_inputs.count() > 0:
                    try:
                        radio_count = radio_inputs.count()
                        for r in range(radio_count):
                            radio = radio_inputs.nth(r)
                            parent_label = radio.locator("xpath=..")
                            radio_text = parent_label.inner_text().strip()
                            if str(value).lower() in radio_text.lower():
                                radio.click()
                                page.wait_for_timeout(200)
                                radio_filled.append(label_text)
                                break
                        continue
                    except:
                        pass

                # ---------------------------------------------------------
                # CHECKBOX
                # ---------------------------------------------------------
                checkbox_inputs = container.locator('input[type="checkbox"]')
                if checkbox_inputs.count() > 0 and isinstance(value, bool):
                    try:
                        checkbox = checkbox_inputs.first
                        is_checked = checkbox.is_checked()
                        if value is True and not is_checked:
                            checkbox.click()
                        if value is False and is_checked:
                            checkbox.click()
                        page.wait_for_timeout(200)
                        checkbox_filled.append(label_text)
                        continue
                    except:
                        pass

        except Exception as e:
            return {"status": "failed", "error_message": f"Error: {e}"}

        # ---------------------------------------------------------
        # ---------------------------------------------------------
        # 5) الضغط على Next / Continue / Review / Submit
        # ---------------------------------------------------------
        next_clicked = False

        try:
            next_selectors = [
                # English
                'button[aria-label="Continue to next step"]',
                'button[aria-label="Continue"]',
                'button:has-text("Next")',
                'button:has-text("Continue")',
                'button:has-text("Review")',
                'button:has-text("Review application")',
                'button:has-text("Review your application")',
                'button:has-text("Submit application")',
                'button:has-text("Submit")',
                'button:has-text("Continue to review")',
                'button:has-text("Continue to next")',
                'button:has-text("Done")',

                # Arabic
                'button:has-text("التالي")',
                'button:has-text("متابعة")',
                'button:has-text("مراجعة")',
                'button:has-text("مراجعة الطلب")',
                'button:has-text("مراجعة 1 من")',
                'button:has-text("مراجعة 2 من")',
                'button:has-text("إرسال")',
                'button:has-text("إرسال الطلب")',
                'button:has-text("تقديم الطلب")',
                'button:has-text("تم")'
            ]

            for selector in next_selectors:
                btn = popup.locator(selector)
                if btn.count() == 0:
                    btn = page.locator(selector)

                if btn.count() > 0:

                    # 1) Scroll داخل البوب‑أب
                    try:
                        popup.evaluate("el => el.scrollTo(0, el.scrollHeight)")
                    except:
                        pass

                    # 2) Scroll للزر نفسه
                    try:
                        btn.first.scroll_into_view_if_needed()
                    except:
                        pass

                    # 3) إزالة أي overlay شفاف
                    try:
                        page.evaluate("""
                            () => {
                                const overlays = document.querySelectorAll('[data-test-modal-overlay], .artdeco-modal-overlay');
                                overlays.forEach(o => o.style.display = 'none');
                            }
                        """)
                    except:
                        pass

                    # 4) Force click
                    btn.first.click(force=True)

                    page.wait_for_timeout(1200)
                    next_clicked = True
                    break

        except Exception as e:
            next_clicked = False



        # ---------------------------------------------------------
        # 6) إرجاع النتيجة
        # ---------------------------------------------------------
        return {
            "status": "fields_filled",
            "session_id": session_id,
            "text_filled": filled_fields,
            "textarea_filled": textarea_filled,
            "dropdown_filled": dropdown_filled,
            "radio_filled": radio_filled,
            "checkbox_filled": checkbox_filled,
            "next_clicked": next_clicked
        }











    @staticmethod
    def extract_questions(session_id: str):

        if session_id not in ApplyService.sessions:
            return {"status": "failed", "error_message": "Session not found"}

        page = ApplyService.sessions[session_id]

        try:
            page.title()
        except:
            return {"status": "failed", "error_message": "Page is closed"}

        questions = []

        try:
            popup = page.locator('div[role="dialog"]')
            label_elements = popup.locator("label")
            count = label_elements.count()

            for i in range(count):
                label_el = label_elements.nth(i)
                label_text = label_el.inner_text().strip().split("\n")[0].strip()
                container = label_el.locator("xpath=..")

                question_type = None
                options = []

                # ---------------------------------------------------------
                # ORIGINAL LOGIC — TEXT INPUT
                # ---------------------------------------------------------
                input_el = container.locator("input")
                if input_el.count() > 0:
                    input_type = input_el.first.get_attribute("type")
                    if input_type in ["text", "email", "tel", "number"]:
                        question_type = "text"

                # ---------------------------------------------------------
                # ORIGINAL LOGIC — DROPDOWN
                # ---------------------------------------------------------
                if question_type is None:
                    dropdown_btn = container.locator('button[aria-haspopup="listbox"]')
                    if dropdown_btn.count() > 0:
                        question_type = "dropdown"
                        dropdown_btn.first.click()
                        page.wait_for_timeout(300)
                        option_elements = page.locator('li[role="option"]')
                        opt_count = option_elements.count()
                        for j in range(opt_count):
                            opt = option_elements.nth(j)
                            options.append(opt.inner_text().strip())
                        dropdown_btn.first.click()
                        page.wait_for_timeout(200)

                # ---------------------------------------------------------
                # ORIGINAL LOGIC — RADIO
                # ---------------------------------------------------------
                if question_type is None:
                    radio_inputs = container.locator('input[type="radio"]')
                    if radio_inputs.count() > 0:
                        question_type = "radio"
                        radio_count = radio_inputs.count()
                        for r in range(radio_count):
                            radio = radio_inputs.nth(r)
                            parent_label = radio.locator("xpath=..")
                            radio_text = parent_label.inner_text().strip()
                            options.append(radio_text)

                # ---------------------------------------------------------
                # ORIGINAL LOGIC — CHECKBOX
                # ---------------------------------------------------------
                if question_type is None:
                    checkbox_inputs = container.locator('input[type="checkbox"]')
                    if checkbox_inputs.count() > 0:
                        question_type = "checkbox"

                # ---------------------------------------------------------
                # NEW 1 — TEXTAREA WITHOUT LABEL (Summary / Cover letter / Web3)
                # ---------------------------------------------------------
                if question_type is None:
                    textarea_el = page.locator(f"textarea[placeholder*='{label_text.split()[0]}']")
                    if textarea_el.count() > 0:
                        question_type = "textarea"

                # ---------------------------------------------------------
                # NEW 2 — TEXTAREA LOOSE MATCH (no placeholder)
                # ---------------------------------------------------------
                if question_type is None:
                    loose_textarea = container.locator("textarea")
                    if loose_textarea.count() > 0:
                        question_type = "textarea"

                # ---------------------------------------------------------
                # NEW 3 — RADIO OUTSIDE CONTAINER (LinkedIn language levels)
                # ---------------------------------------------------------
                if question_type is None:
                    radio_global = page.locator(f"label:has-text('{label_text}')")
                    if radio_global.count() > 0:
                        question_type = "radio"
                        options.append(label_text)

                # ---------------------------------------------------------
                # إضافة السؤال للنتيجة
                # ---------------------------------------------------------
                questions.append({
                    "label": label_text,
                    "type": question_type,
                    "options": options
                })

        except Exception as e:
            return {"status": "failed", "error_message": f"Extract error: {e}"}

        return {
            "status": "questions_extracted",
            "session_id": session_id,
            "questions": questions
        }






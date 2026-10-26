import json
import re
import ollama  # type: ignore
from app.core.config import settings


class AISummaryService:

    @staticmethod
    async def summarize_cv_with_ollama(raw_text: str) -> dict:

        prompt = (
            "Summarize the following CV into a clean JSON object.\n"
            "Return ONLY valid JSON. No explanations. No markdown. No code fences.\n\n"
            f"CV TEXT:\n{raw_text}\n\n"
            "JSON FORMAT:\n"
            "{\n"
            '  "summary": "2-3 sentence professional summary",\n'
            '  "core_skills": ["skill1", "skill2"],\n'
            '  "experience_highlights": ["Company – Role – key achievement"],\n'
            '  "technical_skills": ["tool1", "tool2"],\n'
            '  "domains": ["domain1", "domain2"],\n'
            '  "certifications": ["cert1", "cert2"],\n'
            '  "work_history": [\n'
            '    {\n'
            '      "title": "exact job title from CV",\n'
            '      "company": "exact company name from CV",\n'
            '      "city": "city where the job was based",\n'
            '      "start_month": 1,\n'
            '      "start_year": 2021,\n'
            '      "end_month": null,\n'
            '      "end_year": null,\n'
            '      "is_current": true,\n'
            '      "description": "2-3 sentence description of responsibilities and achievements using only information present in the CV. Never invent details."\n'
            '    }\n'
            '  ]\n'
            "}\n\n"
            "RULES FOR work_history:\n"
            "- List ALL work experience entries found in the CV, most recent first.\n"
            "- Use ONLY data present in the CV text. Never invent companies, titles, dates, or descriptions.\n"
            "- start_month and end_month must be integers 1-12 (January=1, December=12).\n"
            "- start_year and end_year must be 4-digit integers (e.g. 2021).\n"
            "- If the candidate currently works there, set end_month=null, end_year=null, is_current=true.\n"
            "- If a date is not mentioned in the CV, set that field to null.\n"
            "- city: use the city mentioned for that job, or the candidate's city if not specified.\n"
            "- description: write from the CV content only. Do not use generic phrases like 'highly motivated' or 'proven track record'.\n"
        )

        _client = ollama.Client(
        host=settings.ollama_base_url,
        timeout=settings.ollama_timeout,
        )
        response = _client.chat(
            model=settings.ollama_model,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response["message"]["content"]
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        content = re.sub(r"```json|```", "", content).strip()

        json_match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not json_match:
            raise ValueError("Model did not return valid JSON")

        json_text = json_match.group(0)
        data = json.loads(json_text)

        # ── Normalize experience_highlights ───────────────────────────────────
        # Legacy: model sometimes returns list of dicts instead of strings
        fixed_experience = []
        for item in data.get("experience_highlights", []):
            if isinstance(item, dict):
                parts = []
                if "company" in item:
                    parts.append(item["company"])
                if "role" in item:
                    parts.append(item["role"])
                if "details" in item:
                    parts.append(item["details"])
                fixed_experience.append(" – ".join(parts))
            else:
                fixed_experience.append(item)
        data["experience_highlights"] = fixed_experience

        # ── Normalize work_history ────────────────────────────────────────────
        # Ensure all required keys exist with correct types.
        # Protects against model returning partial or malformed entries.
        raw_history = data.get("work_history", [])
        normalized_history = []
        for entry in raw_history:
            if not isinstance(entry, dict):
                continue

            def _safe_int(val):
                try:
                    return int(val) if val is not None else None
                except (ValueError, TypeError):
                    return None

            normalized_history.append({
                "title":       str(entry.get("title") or ""),
                "company":     str(entry.get("company") or ""),
                "city":        str(entry.get("city") or ""),
                "start_month": _safe_int(entry.get("start_month")),
                "start_year":  _safe_int(entry.get("start_year")),
                "end_month":   _safe_int(entry.get("end_month")),
                "end_year":    _safe_int(entry.get("end_year")),
                "is_current":  bool(entry.get("is_current", False)),
                "description": str(entry.get("description") or ""),
            })

        data["work_history"] = normalized_history

        return data


    @staticmethod
    async def ask_ollama(prompt: str) -> dict:

        _client = ollama.Client(
        host=settings.ollama_base_url,
        timeout=settings.ollama_timeout,
        )
        response = _client.chat(
            model=settings.ollama_model,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response["message"]["content"]
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        json_match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not json_match:
            raise ValueError("Model did not return valid JSON")

        json_text = json_match.group(0)
        data = json.loads(json_text)

        return data
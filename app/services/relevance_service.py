"""
app/services/relevance_service.py

LLM-powered semantic relevance scoring engine.

Scores job postings against the candidate's CV summary using a local
Ollama model. The LLM evaluates semantic fit — not just keyword overlap —
which handles synonyms, related terms, and domain variations correctly.

Fallback: if Ollama is unavailable, uses the token-frequency engine.

Score: 0–100
Threshold: DEFAULT_THRESHOLD = 55
Title bypass: removed — the LLM handles this implicitly via semantic match.
"""

import re
import json
import logging

_log = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 55


# ── Fallback token engine (used only when Ollama is unavailable) ──────────────

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "nor", "so", "yet",
    "both", "either", "neither", "in", "on", "at", "to", "for",
    "of", "with", "as", "by", "from", "into", "onto", "upon",
    "about", "above", "below", "between", "through", "during",
    "before", "after", "under", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall",
    "can", "need", "dare", "must", "i", "you", "he", "she", "it",
    "we", "they", "me", "him", "her", "us", "them", "my", "your",
    "his", "its", "our", "their", "this", "that", "these", "those",
    "not", "no", "more", "most", "also", "such", "other", "than",
    "then", "when", "where", "who", "which", "what", "how", "any",
    "all", "each", "every", "some", "few", "new", "own", "same",
    "well", "over", "just",
}

WEIGHT_TITLE       = 40
WEIGHT_CORE_SKILLS = 25
WEIGHT_TECH_SKILLS = 20
WEIGHT_DOMAINS     = 15
FALLBACK_THRESHOLD = 30


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    tokens = [t for t in text.split() if t not in _STOPWORDS and len(t) >= 2]
    return " ".join(tokens)


def _extract_terms(cv_field: list[str]) -> list[str]:
    terms = []
    for item in (cv_field or []):
        normalized = _normalize(item)
        if normalized:
            terms.append(normalized)
            terms.extend(normalized.split())
    seen: set[str] = set()
    result = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _match_score(terms, text, max_score):
    if not terms or not text:
        return 0, []
    matched = [t for t in terms if t in text]
    if not matched:
        return 0, []
    ratio = len(set(matched)) / len(set(terms))
    score = min(int(max_score * ratio), max_score)
    return score, list(set(matched))


def _token_score_job(job_title, job_description, cv_summary, threshold):
    """Original token-frequency engine used as fallback."""
    norm_title    = _normalize(job_title or "")
    norm_combined = norm_title + " " + _normalize(job_description or "")

    core_terms   = _extract_terms(cv_summary.get("core_skills")     or [])
    tech_terms   = _extract_terms(cv_summary.get("technical_skills") or [])
    domain_terms = _extract_terms(cv_summary.get("domains")          or [])
    all_cv_terms = core_terms + tech_terms + domain_terms

    # Title bypass — domains only, no generic terms like 'engineer'
    bypass_sources = cv_summary.get("domains") or []
    bypass_terms = []
    for item in bypass_sources:
        normalized = _normalize(item)
        bypass_terms.extend(normalized.split())
    bypass_terms = [t for t in bypass_terms if len(t) >= 6]
    seen: set[str] = set()
    unique_bypass = []
    for t in bypass_terms:
        if t not in seen:
            seen.add(t)
            unique_bypass.append(t)
    title_bypass = any(term in norm_title for term in unique_bypass)

    title_score,  title_matched  = _match_score(all_cv_terms,  norm_title,    WEIGHT_TITLE)
    core_score,   core_matched   = _match_score(core_terms,    norm_combined, WEIGHT_CORE_SKILLS)
    tech_score,   tech_matched   = _match_score(tech_terms,    norm_combined, WEIGHT_TECH_SKILLS)
    domain_score, domain_matched = _match_score(domain_terms,  norm_combined, WEIGHT_DOMAINS)

    total_score = title_score + core_score + tech_score + domain_score
    accepted = total_score >= threshold or title_bypass

    if accepted:
        if title_bypass and total_score < threshold:
            reason = (
                f"ACCEPTED via title bypass (score={total_score} < threshold={threshold}). "
                f"Title '{job_title}' matches candidate's declared domains."
            )
        else:
            reason = f"ACCEPTED (score={total_score} >= threshold={threshold})"
    else:
        reason = (
            f"REJECTED (score={total_score} < threshold={threshold}). "
            f"No sufficient match between job content and candidate CV terms."
        )

    return {
        "score":    total_score,
        "accepted": accepted,
        "bypass":   title_bypass,
        "reason":   reason,
        "matched_terms": {
            "title":            title_matched,
            "core_skills":      core_matched,
            "technical_skills": tech_matched,
            "domains":          domain_matched,
        },
    }


# ── LLM scoring engine ────────────────────────────────────────────────────────

def _llm_score_job(job_title, job_description, cv_summary, threshold):
    """
    Ask the local Ollama model to score the job against the CV summary.

    The model returns a JSON object with a score (0-100) and a decision.
    This is strictly a yes/no relevance decision — the model does not
    fill any form fields here.
    """
    try:
        import ollama # type: ignore
        from app.core.config import settings

        cv_text = json.dumps(cv_summary, ensure_ascii=False)

        prompt = f"""You are a strict job relevance classifier. Your only job is to decide whether a job posting is relevant to a candidate's CV.

CANDIDATE CV SUMMARY:
{cv_text}

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description[:2000]}

TASK:
Score how relevant this job is to the candidate on a scale of 0 to 100.

SCORING RULES:
- 80-100: The job directly matches the candidate's core domain, title, and skills. The candidate is clearly qualified.
- 60-79: The job is in the candidate's domain and uses overlapping skills. Candidate has relevant background.
- 40-59: Partial overlap. The job touches some of the candidate's skills but the domain or role differs.
- 20-39: Minor overlap. A few shared keywords but the role is fundamentally different.
- 0-19: No meaningful overlap. Different domain, different skills, different role entirely.

DISQUALIFICATION RULES (override all other scoring — set score to 0):
- If the job title or description explicitly requires a specific nationality or citizenship the candidate does not have (e.g. "UAE Nationals only", "Emiratis only", "Saudi nationals only", "must hold British passport"), set score=0.
- If the job requires a security clearance tied to a specific citizenship the candidate does not hold, set score=0.
- The candidate's nationality is available in the CV summary. Use it.
- Do not apply this rule for general "must be based in UAE" or "visa sponsorship available" — those are location requirements, not nationality requirements.

IMPORTANT:
- Judge by domain fit and role fit, not just shared words.
- A cybersecurity engineer applying for a DevOps role is a 50-65 if it mentions security, not a 90.
- A cybersecurity engineer applying for an FM (Facilities Management) engineer role is a 5.
- A cybersecurity engineer applying for a SOC analyst, SIEM engineer, penetration tester, or security operations role is an 85-95.
- Do not be fooled by generic words like "engineer", "manager", "system" — these appear in all jobs.

Return ONLY a valid JSON object with no explanation, no markdown, no preamble:
{{"score": <integer 0-100>, "reason": "<one sentence>"}}"""

        _client = ollama.Client(
            host=settings.ollama_base_url,
            timeout=settings.ollama_timeout,
        )
        response = _client.chat(
            model=settings.ollama_model,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response["message"]["content"].strip()
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        # Strip markdown fences if present
        content = re.sub(r"```json|```", "", content).strip()

        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise ValueError(f"No JSON in LLM response: {content[:200]}")

        result = json.loads(match.group(0))
        score = int(result.get("score", 0))
        reason_text = result.get("reason", "")
        score = max(0, min(100, score))
        accepted = score >= threshold

        if accepted:
            reason = f"ACCEPTED (LLM score={score} >= threshold={threshold}). {reason_text}"
        else:
            reason = f"REJECTED (LLM score={score} < threshold={threshold}). {reason_text}"

        _log.info(f"[relevance] LLM score={score}, accepted={accepted}: {reason_text}")

        return {
            "score":    score,
            "accepted": accepted,
            "bypass":   False,
            "reason":   reason,
            "matched_terms": {"llm": [reason_text]},
        }

    except Exception as e:
        _log.warning(f"[relevance] LLM scoring failed: {e} — falling back to token engine")
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def score_job(
    job_title: str,
    job_description: str,
    cv_summary: dict,
    threshold: int = DEFAULT_THRESHOLD,
) -> dict:
    """
    Score a job posting for relevance to the candidate's CV.

    Attempts LLM scoring first. Falls back to token-frequency engine
    if Ollama is unavailable or returns invalid output.

    Args:
        job_title:        Raw job title string
        job_description:  Raw job description text
        cv_summary:       The cv_summary dict from user settings
        threshold:        Minimum score to accept (default: 55 for LLM, 30 for fallback)

    Returns:
        {
            "score":         int (0–100),
            "accepted":      bool,
            "bypass":        bool,
            "reason":        str,
            "matched_terms": dict,
        }
    """
    # Attempt LLM scoring
    llm_result = _llm_score_job(job_title, job_description, cv_summary, threshold)
    if llm_result is not None:
        return llm_result

    # Fallback to token engine with lower threshold
    _log.info("[relevance] Using token-frequency fallback engine")
    return _token_score_job(job_title, job_description, cv_summary, FALLBACK_THRESHOLD)
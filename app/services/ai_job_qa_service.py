from app.services.ai_summary_service import AISummaryService

class AIJobQAService:

    @staticmethod
    async def generate_answers(job_description: str, cv_summary: dict, questions: list):

        prompt = f"""
أنت مساعد توظيف ذكي.
مهمتك الإجابة على أسئلة التقديم بناءً على:

1) وصف الوظيفة:
{job_description}

2) ملخص السيرة الذاتية:
{cv_summary}

3) الأسئلة المطلوب الإجابة عليها:
{questions}

أرجع الإجابات بصيغة JSON فقط:
{{
  "answers": [
    {{"question": "...", "answer": "..." }}
  ]
}}
"""

        result = await AISummaryService.ask_ollama(prompt)
        return result

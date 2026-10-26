# app/services/cv_service.py

import io
import pdfplumber # type: ignore
from fastapi import UploadFile, HTTPException # type: ignore

class CVService:

    @staticmethod
    async def extract_text_from_pdf(file: UploadFile) -> str:
        # 1) التحقق من أن الملف PDF
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

        # 2) قراءة الملف
        file_bytes = await file.read()

        # 3) استخراج النص
        try:
            raw_text = ""

            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    raw_text += page_text + "\n"

            raw_text = raw_text.strip()

            if not raw_text:
                raise HTTPException(status_code=400, detail="Could not extract text from PDF")

            return raw_text

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading PDF: {str(e)}")

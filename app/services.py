# app/services.py
from fastapi import HTTPException, UploadFile

from .parser import parse_document  # <-- NEW import
from .summarization import detect_headings_and_summarize_llm


class SolicitationService:
    def __init__(self, openai_api_key: str):
        self.openai_api_key = openai_api_key

    async def summarize_document(self, file: UploadFile) -> list:
        """
        Summarize an uploaded document by:
          1) Parsing it via parser.py (LlamaParse).
          2) Running detect_headings_and_summarize_llm on the result.
          3) Returning a list of { heading, summary }.
        """
        # 1) Parse the doc to get combined text
        parsed_text = await parse_document(file)
        if not parsed_text:
            raise HTTPException(
                status_code=400, detail="No text found in uploaded document.")

        # 2) Summarize
        summarized_sections = await detect_headings_and_summarize_llm(
            parsed_text,
            self.openai_api_key
        )

        return summarized_sections

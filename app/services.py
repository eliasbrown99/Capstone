from fastapi import HTTPException
from .document_loader import DocumentLoader
from .summarization import detect_headings_and_summarize


class SolicitationService:
    def __init__(self, openai_api_key: str):
        """
        Initialize the SolicitationService with:
          - A DocumentLoader for reading and chunking PDFs/DOCs.
        """
        self.document_loader = DocumentLoader()
        self.openai_api_key = openai_api_key

    async def summarize_document(self, file) -> list:
        """
        Summarizes an uploaded document by:
          1. Loading & splitting text via DocumentLoader.
          2. Using detect_headings_and_summarize() to do LLM-based heading detection & summarization.
          3. Returning a list of { heading, summary } for rendering.
        """
        # 1) Load text chunks from the file
        text_chunks = await self.document_loader.load_document(file)
        if not text_chunks:
            raise HTTPException(
                status_code=400,
                detail="No text found in uploaded document."
            )

        # 2) Combine them into one large string
        full_text = "\n".join(text_chunks)

        # 3) Let summarization.py handle the headings & summarizing
        summarized_sections = await detect_headings_and_summarize(
            full_text, self.openai_api_key, debug=True
        )

        return summarized_sections

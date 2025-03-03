import os
from fastapi import HTTPException

from .document_loader import DocumentLoader
from .summarization import (
    create_summary_llm,
    detect_headings_and_sections,
    is_heading_relevant,
    is_content_relevant,
    summarize_section
)


class SolicitationService:
    def __init__(self, openai_api_key: str):
        """
        Initialize the SolicitationService with:
          - A DocumentLoader for reading and chunking PDFs/DOCs.
          - An LLM for summarization, configured via create_summary_llm.
        """
        self.document_loader = DocumentLoader()
        self.llm = create_summary_llm(openai_api_key, model_name="gpt-4")

    async def summarize_document(self, file) -> list:
        """
        Summarizes an uploaded document by:
          1. Loading & splitting text via DocumentLoader.
          2. Detecting headings in the combined text.
          3. Deciding if each section is relevant to scope-of-work tasks.
          4. Summarizing each section with an appropriate prompt.
          5. Returning a list of { heading, summary } for rendering.
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

        # 3) Detect headings & group lines by section
        sections = detect_headings_and_sections(full_text)

        # 4) Summarize each section, focusing on tasks or scope-of-work
        summarized_sections = []
        for sec in sections:
            heading = sec["heading"]
            content = sec["content"]

            # Determine relevance by heading or content keywords
            relevant = is_heading_relevant(heading) or is_content_relevant(content)

            # Summarize the section with the correct prompt
            summary = await summarize_section(self.llm, heading, content, relevant)

            # If the model returns a non-empty summary, store it
            if summary.strip():
                summarized_sections.append({
                    "heading": heading,
                    "summary": summary
                })

        return summarized_sections

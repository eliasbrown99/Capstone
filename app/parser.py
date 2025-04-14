# app/parser.py

import os
import tempfile
from pathlib import Path
from fastapi import UploadFile, HTTPException
from dotenv import load_dotenv
from llama_index.core import SimpleDirectoryReader
from llama_cloud_services import LlamaParse

load_dotenv()


def get_llama_parser():
    """
    Utility to create the LlamaParse() object with any custom settings/prompts.
    """
    parser = LlamaParse(
        result_type="markdown",
        parse_mode="parse_page_with_layout_agent",
        html_remove_navigation_elements=True,
        preserve_layout_alignment_across_pages=True,
        extract_layout=True,
        system_prompt=""" 
            Items which look like document titles, dates, table of contents, etc should be completely eliminated from the output.
            Only output section, subsection, subsubsection, etc -titles, narrative text, list elements, and table elements.
            Be sure to capture to the best of your ability the differences between section titles and subsection titles and denote this in markdown.
            Key remark: all top level headings (i.e., single # in markdown) will be those that start with a number followed by either a period or a period and a zero.
        """,
        system_prompt_append="""
            Though not a rigid rule, bold text is a better litmus test to deem a line (or lines) as section headers rather than capitalization 
            at the beginning of a page, though section headers/titles often are capitalized. 
            Remain "page number agnostic" when deciding on section titles.
            Also elements which look like section titles but are not numbered, should be rendered as subsections.
        """
    )
    return parser


async def parse_document(file: UploadFile) -> str:
    """
    Given an uploaded file (PDF, Word, etc.), parse it with LlamaParse
    and return the combined markdown/text as one string.
    """
    # Validate file extension (optional).
    suffix = Path(file.filename).suffix.lower()
    if suffix not in [".pdf", ".doc", ".docx"]:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    # Write the uploaded file to a temp location
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        temp_path = tmp.name

    try:
        # Set up the Llama parser for PDFs, etc.
        parser = get_llama_parser()
        file_extractor = {
            ".pdf": parser,
            ".doc": parser,
            ".docx": parser
        }

        # Use SimpleDirectoryReader to parse the single file with Llama
        documents = SimpleDirectoryReader(
            input_files=[temp_path],
            file_extractor=file_extractor
        ).load_data()

        # Combine text from all Document objects
        all_text = "\n\n".join(doc.text for doc in documents)

        if not all_text.strip():
            raise HTTPException(
                status_code=400, detail="No text extracted from document.")

        return all_text

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error parsing document: {str(e)}")

    finally:
        # Clean up temp file
        os.remove(temp_path)


# (Optional) If you want to debug by direct call:
# if __name__ == "__main__":
#     # Example usage
#     # But typically, you won't run parse_document() directly;
#     # it will be invoked via the SolicitationService in your FastAPI app.
#     pass

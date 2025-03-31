# app/summarization.py

import re
from typing import List, Dict, Any
import asyncio

# If you're using "langchain_openai" for ChatOpenAI, import that:
from langchain_openai import ChatOpenAI

# Otherwise, if you're using official LangChain, you can do:
# from langchain.chat_models import ChatOpenAI

from langchain.schema import HumanMessage
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter

##############################################################################
# (A) PARSE MARKDOWN HEADINGS
##############################################################################


def parse_markdown_headings(document_text: str) -> List[Dict[str, str]]:
    """
    Reads markdown line by line. 
    If a line starts with one or more '#' chars, treat it as heading-level-1..3.
    Otherwise treat it as body-text.

    Returns a list of dicts: 
      [ {"text": line_text, "class": "heading-level-x" or "body-text"}, ... ]
    """
    lines = [ln.strip() for ln in document_text.splitlines()]
    pattern = re.compile(r'^(#{1,6})\s+(.*)$')
    results = []

    for ln in lines:
        if not ln:
            continue  # skip blank lines
        match = pattern.match(ln)
        if match:
            hashes = match.group(1)
            heading_text = match.group(2).strip()
            level = min(len(hashes), 3)  # clamp headings to level-3
            heading_class = f"heading-level-{level}"
            results.append({"text": heading_text, "class": heading_class})
        else:
            # It's body text
            results.append({"text": ln, "class": "body-text"})
    return results

##############################################################################
# (B) BUILD HIERARCHICAL STRUCTURE
##############################################################################


def build_hierarchical_structure(classified_lines: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Given lines labeled heading-level-1..3 or body-text, build a nested structure:
       [
         {
           "title": <heading-level-1 text>,
           "content": [list of body text strings],
           "subsections": [
             {
               "title": <heading-level-2 text>,
               "content": [...],
               "subsections": [
                 {
                   "title": <heading-level-3 text>,
                   "content": [...]
                 },
                 ...
               ]
             },
             ...
           ]
         },
         ...
       ]
    """
    structured_doc = []
    current_h1 = None
    current_h2 = None
    current_h3 = None

    for item in classified_lines:
        line_text = item["text"]
        line_class = item["class"]

        if line_class == "heading-level-1":
            current_h1 = {
                "title": line_text,
                "content": [],
                "subsections": []
            }
            structured_doc.append(current_h1)
            current_h2 = None
            current_h3 = None

        elif line_class == "heading-level-2":
            if current_h1 is None:
                # If there's no H1 yet, create a dummy one
                current_h1 = {
                    "title": "Untitled Section",
                    "content": [],
                    "subsections": []
                }
                structured_doc.append(current_h1)
            current_h2 = {
                "title": line_text,
                "content": [],
                "subsections": []
            }
            current_h1["subsections"].append(current_h2)
            current_h3 = None

        elif line_class == "heading-level-3":
            if current_h2 is None:
                # If there's no H2, attach to H1 or create it implicitly
                if current_h1 is None:
                    current_h1 = {
                        "title": "Untitled Section",
                        "content": [],
                        "subsections": []
                    }
                    structured_doc.append(current_h1)
                current_h2 = {
                    "title": "Untitled Subsection",
                    "content": [],
                    "subsections": []
                }
                current_h1["subsections"].append(current_h2)

            current_h3 = {
                "title": line_text,
                "content": []
            }
            current_h2["subsections"].append(current_h3)

        else:
            # body-text
            if current_h3 is not None:
                current_h3["content"].append(line_text)
            elif current_h2 is not None:
                current_h2["content"].append(line_text)
            elif current_h1 is not None:
                current_h1["content"].append(line_text)
            else:
                # No heading at all so far
                current_h1 = {
                    "title": "Untitled Section",
                    "content": [line_text],
                    "subsections": []
                }
                structured_doc.append(current_h1)

    return structured_doc


def gather_section_text(section: Dict[str, Any]) -> str:
    """
    Recursively gather all text in this section and its subsections.
    Return as a single string. 
    """
    texts = []
    # Add top-level content
    texts.extend(section["content"])

    # Gather nested
    if "subsections" in section:
        for subsec in section["subsections"]:
            texts.append(gather_section_text(subsec))

    return "\n".join(texts)

##############################################################################
# (C) OLD-STYLE KEYWORD RELEVANCE CHECK
##############################################################################


RELEVANT_HEADING_KEYWORDS = [
    "statement of work",
    "scope of work",
    "scope",
    "work scope",
    "tasks",
    "deliverables",
    "responsibility",
    "services",
    "requirements",
    "objectives",
    "personnel",
    "introduction",
    "background",
    "task",
    "objectives",
    'background',
    'introduction',
    'intro',
    'objective',
    'purpose'
]


def is_heading_relevant(heading: str) -> bool:
    """Checks if the heading suggests tasks or scope-of-work (simple substring check)."""
    heading_lower = heading.lower()
    return any(kw in heading_lower for kw in RELEVANT_HEADING_KEYWORDS)

##############################################################################
# (D) PROMPT TEMPLATE FOR SUMMARIZATION
##############################################################################


SOW_SUMMARY_PROMPT = PromptTemplate(
    input_variables=["heading", "text"],
    template="""
You are summarizing a document section titled: "{heading}" which likely contains tasks, scope of work, 
or responsibilities for Acato's testing/QA role.

Your goal: Provide a concise set of EXACTLY 5 bullet points. Only create fewer than 5 bullet points if and only if 
the section has fewer than 5 unique items. 
Each bullet should focus on the specific scope of work or tasks relevant to THIS SECTION ONLY.
DO NOT assume tasks from previous sections—summarize only the text given.

Ignore excessive legal or administrative details (e.g., contract boilerplate, 
travel policy) unless they directly impact these tasks.

If this section is part of a TASK breakdown (e.g., "TASK 1, TASK 2, etc."), 
treat it as an independent section and summarize it on its own.

Also:
1) If abbreviations appear, expand them at least once.
2) Keep the summary high-level and actionable.
3) If the section has a lot of repetitive text or references, combine or condense them.

SECTION TEXT:
{text}
"""
)

##############################################################################
# (E) CREATE LLM
##############################################################################


def create_summary_llm(openai_api_key: str, model_name="gpt-3.5-turbo"):
    return ChatOpenAI(
        model_name=model_name,
        temperature=0.0,
        openai_api_key=openai_api_key
    )

##############################################################################
# (F) SUMMARIZE A SINGLE SECTION
##############################################################################


async def summarize_section(llm, heading: str, text: str) -> str:
    """
    Summarizes a document section using SOW_SUMMARY_PROMPT.
    Skips summarization for sections not matching `is_heading_relevant()`
    UNLESS heading explicitly starts with 'task'.
    """
    if not is_heading_relevant(heading) and not heading.lower().startswith("task"):
        # Not relevant -> skip
        return ""

    response = await (SOW_SUMMARY_PROMPT | llm).ainvoke({"heading": heading, "text": text})
    return response.content.strip() if response.content else ""

##############################################################################
# (G) MAIN FUNCTION: PARSE -> BUILD -> FLATTEN TOP-LEVEL -> CHUNK -> SUMMARIZE
##############################################################################


async def detect_headings_and_summarize(
    document_text: str,
    openai_api_key: str,
    debug: bool = True
) -> List[Dict[str, str]]:
    """
    1) Parse doc lines as markdown headings or body-text
    2) Build hierarchical structure
    3) Flatten only the top-level sections
    4) For each top-level section, chunk if large, then summarize if relevant
    Returns list of { "heading": <h>, "summary": <s> }.
    """
    # 1) Parse lines
    lines_classified = parse_markdown_headings(document_text)
    if not lines_classified:
        if debug:
            print("[DEBUG] No lines found or doc is empty.")
        return []

    # 2) Build hierarchical structure
    structured_doc = build_hierarchical_structure(lines_classified)

    # 3) Flatten only the top-level sections
    #    (This means headings-level-2 and -3 get merged into the parent's content.)
    top_sections = []
    for top_section in structured_doc:
        heading = top_section["title"]
        content = gather_section_text(top_section)
        top_sections.append({"heading": heading, "content": content})

    if debug:
        print("\n[DEBUG] === Top-Level Sections Detected ===")
        for i, sec in enumerate(top_sections):
            print(
                f"Section {i+1} Heading: '{sec['heading']}' | content length: {len(sec['content'])}")

    # Create the ChatOpenAI instance
    summary_llm = create_summary_llm(openai_api_key)

    # We'll chunk each section if it's large
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=100
    )

    summarized_sections = []

    for sec in top_sections:
        heading = sec["heading"]
        text = sec["content"]

        # Split the text for this heading
        docs = text_splitter.create_documents([text])
        partial_summaries = []

        for d in docs:
            chunk_text = d.page_content.strip()
            if not chunk_text:
                continue

            # Summarize if relevant
            chunk_summary = await summarize_section(summary_llm, heading, chunk_text)
            if chunk_summary:
                partial_summaries.append(chunk_summary)

        final_summary = "\n".join(partial_summaries).strip()
        if final_summary:
            summarized_sections.append({
                "heading": heading,
                "summary": final_summary
            })
            if debug:
                print(
                    f"[DEBUG] Summarized heading: '{heading}' -> {len(final_summary)} chars total")
        else:
            if debug:
                print(
                    f"[DEBUG] Skipped heading: '{heading}' (no relevant summary)")

    return summarized_sections

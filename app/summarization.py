import re
import asyncio
from typing import List, Dict, Any

# ✅ modern import – no more deprecation warning
from langchain_openai import ChatOpenAI

from langchain.schema import HumanMessage, SystemMessage
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter


##############################################################################
# (A) PARSE (REGEX) -> REFINE (LLM) FOR TRUE NUMBERED HEADINGS
##############################################################################

def parse_markdown_headings(document_text: str) -> List[Dict[str, str]]:
    """
    Solution A: treat ANY line that starts with '#' as a top-level heading,
    ignoring how many '#' characters are present.

    Returns a list of dicts:
      [{"text": line_text, "class": "heading-level-1" or "body-text"}, ...]
    """
    lines = [ln.strip() for ln in document_text.splitlines() if ln.strip()]

    # Regex: line starts with one or more '#' followed by optional whitespace
    pattern = re.compile(r'^(#+)\s*(.*)$')
    results = []

    for ln in lines:
        match = pattern.match(ln)
        if match:
            # We ignore how many '#' are present and treat them all as heading-level-1
            heading_text = match.group(2).strip()
            results.append({"text": heading_text, "class": "heading-level-1"})
        else:
            # It's body text
            results.append({"text": ln, "class": "body-text"})
    return results


# Prompt for heading refinement
REFINE_HEADING_PROMPT = PromptTemplate(
    input_variables=["heading_text"],
    template="""
You are given a heading line from a Markdown file. It starts with one or more '#' characters.
We suspect it might be a "numbered heading" (i.e., it has a numeric or roman-numeral scheme in its text).
Examples of valid numbering: "1.", "1.2", "III.", "XIV", "2.1.3", etc.

If the heading text has a numbering or roman-numeral scheme, respond exactly "TRUE_HEADING".
Otherwise respond exactly "NOT_HEADING".

Heading text: "{heading_text}"
"""
)


async def refine_headings_by_numbering(llm, lines: List[Dict[str, str]]) -> None:
    """
    For each line that is labeled heading-level-* by the regex pass,
    confirm via LLM whether it truly has a numbering/roman-numeral scheme.
    If it does not, demote it to body-text.

    This function mutates the 'lines' list in place.
    """
    tasks = []

    # We'll only refine lines that were labeled as headings
    to_refine_indices = [
        i for i, item in enumerate(lines)
        if item["class"].startswith("heading-level")
    ]

    for idx in to_refine_indices:
        heading_text = lines[idx]["text"]

        system_msg = SystemMessage(
            content="You are a strict classifier for heading lines. Output EXACTLY 'TRUE_HEADING' or 'NOT_HEADING'."
        )
        user_msg = HumanMessage(
            content=REFINE_HEADING_PROMPT.format(heading_text=heading_text)
        )

        # Gather tasks to run concurrently
        tasks.append((idx, llm.ainvoke([system_msg, user_msg])))

    # Run all LLM tasks
    results = await asyncio.gather(*[task[1] for task in tasks])

    # Update lines in-place
    for (idx, _), response in zip(tasks, results):
        verdict = response.content.strip().upper()
        if verdict != "TRUE_HEADING":
            # If not confirmed as a valid numbered heading, demote to body-text
            lines[idx]["class"] = "body-text"

##############################################################################
# (B.2) BUILD A FLAT LIST OF SECTIONS (FOR SOLUTION A)
##############################################################################


def build_flat_sections(lines_classified: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    For Solution A:
    Create a flat list of sections. Each section = {"heading": ..., "content": [...]}
    We treat *any* heading-level-1 as the start of a new section, and accumulate
    body-text lines until the next heading.
    """
    sections = []
    current_section = None

    for item in lines_classified:
        if item["class"] == "heading-level-1":
            # If we were already in a section, close it out
            if current_section is not None:
                sections.append(current_section)

            # Start a new one
            current_section = {
                "heading": item["text"],
                "content": []
            }
        else:
            # body-text
            if current_section is not None:
                current_section["content"].append(item["text"])
            else:
                # If no heading started yet, place it under a dummy heading
                current_section = {
                    "heading": "Untitled Section",
                    "content": [item["text"]]
                }

    # If there's a final open section, append it
    if current_section is not None:
        sections.append(current_section)

    return sections


##############################################################################
# (C) LLM-BASED HEADING RELEVANCE (PASS 1)
##############################################################################

HEADING_CLASSIFICATION_PROMPT = PromptTemplate(
    input_variables=["capabilities", "heading_text", "content_snippet"],
    template="""
You are an expert analyst reviewing section headers and content from government solicitations.
Acato is a company with the following capabilities:

{capabilities}

Your task is to determine whether the **section below** is RELEVANT or IRRELEVANT to Acato’s potential role — such as being awarded or performing substantive work.

Use the following heuristics:

- **RELEVANT** if the section covers topics like:
    • Scope of Work
    • Tasks, Deliverables, Requirements
    • Optional Surge Support
    • Strategic Priorities (that may tie into software systems or testing)
    • Key Personnel descriptions or requirements
    • Software Testing, Evaluation, or Support
    • Specific objectives or performance goals
    • General, introductory, or background sections (e.g. "General Information") that might contain context for the scope or project

- **IRRELEVANT** if the section is mainly about:
    • Government-Furnished Equipment / Property / Information
    • Certifications, Regulations, FAR clauses
    • Travel or Access logistics
    • Inspection & Acceptance
    • Contract structure or section listings
    • Reporting logistics (unless it includes strategy or testing details)
    • Reference documents (e.g. “Applicable Documents”)
    • Place of Performance details
    • Period of Performance details
    • Any purely administrative or legal clauses that do not affect tasks or deliverables

Output exactly one word: "RELEVANT" or "IRRELEVANT"

Heading: {heading_text}

Content:
{content_snippet}
"""
)


async def classify_heading_with_llm(
    llm,
    heading: str,
    snippet: str,
    capabilities_text: str,
) -> bool:
    """
    Calls an LLM to decide if heading is relevant (True) or not (False).
    We feed a system message describing the role, plus a prompt containing the heading and snippet.
    """
    system_msg = SystemMessage(
        content=(
            "You are a helpful classifier. You will return only 'RELEVANT' or 'IRRELEVANT' "
            "for the user's heading and snippet, based on whether the content matches Acato's capabilities."
        )
    )

    user_prompt = HEADING_CLASSIFICATION_PROMPT.format(
        capabilities=capabilities_text,
        heading_text=heading,
        content_snippet=snippet
    )
    user_msg = HumanMessage(content=user_prompt)

    response = await llm.ainvoke([system_msg, user_msg])
    classification = response.content.strip().upper()

    return classification.startswith("RELEVANT")


##############################################################################
# (D) PROMPT TEMPLATE FOR SUMMARIZATION (PASS 2)
##############################################################################

SOW_SUMMARY_PROMPT = PromptTemplate(
    input_variables=["heading", "text"],
    template="""
You are summarizing a document section titled: "{heading}" which likely contains tasks, scope of work, 
or responsibilities for Acato's QA/test role.

Your goal: Provide a concise set of bullet points focusing on tasks or responsibilities relevant to THIS SECTION.
Do NOT exceed 5 bullet points total.

SECTION TEXT:
{text}
"""
)


async def summarize_section(llm, heading: str, text: str) -> str:
    """
    Summarizes a document section using the SOW_SUMMARY_PROMPT.
    Returns raw string (which may exceed 5 bullets if the LLM doesn't follow instructions).
    """
    response = await (SOW_SUMMARY_PROMPT | llm).ainvoke({"heading": heading, "text": text})
    return response.content.strip() if response.content else ""


##############################################################################
# (D.2) SECOND PASS PROMPT TO ENFORCE 5 BULLET LIMIT STRICTLY
##############################################################################

ENFORCE_BULLET_LIMIT_PROMPT = PromptTemplate(
    input_variables=["raw_summary"],
    template="""
You are given a bullet-list summary that may exceed 5 bullet points.

Task: Rewrite it so there are at most 5 bullet points.
If there are more, you must combine or omit items.

Output ONLY the final bullet list (nothing else).

Raw summary:
{raw_summary}
"""
)


async def enforce_bullet_limit(llm, text: str) -> str:
    """
    A second LLM pass that ensures the final text has no more than 5 bullets.
    """
    if not text:
        return ""

    system_msg = SystemMessage(
        content=(
            "You must ensure there are no more than 5 bullet points total. "
            "Combine or omit if needed."
        )
    )
    user_msg = HumanMessage(
        content=ENFORCE_BULLET_LIMIT_PROMPT.format(raw_summary=text)
    )

    response = await llm.ainvoke([system_msg, user_msg])
    return response.content.strip() if response.content else ""


##############################################################################
# (E) MAIN: PARSE -> REFINE -> BUILD FLAT -> PASS1 (CLASSIFY) -> PASS2 (SUMMARIZE)
##############################################################################

async def detect_headings_and_summarize_llm(
    document_text: str,
    openai_api_key: str,
    debug: bool = True
) -> List[Dict[str, str]]:
    """
    SOLUTION A: 
    1) Parse doc lines using a simplified approach that treats ANY '#' as top-level heading
    2) LLM-based refinement: lines with '#' are checked to confirm they have numbering or roman numerals
       - If not, convert them to body-text.
    3) Build a FLAT structure (no nested hierarchy)
    4) Pass 1: For each section, do an LLM-based classification
       (given some internal 'capabilities_text').
    5) Pass 2: Summarize only the headings deemed RELEVANT, chunking if necessary.
    6) A second LLM prompt strictly enforces no more than 5 bullet points.

    Returns list of { "heading": <h>, "summary": <s> }.
    """

    # Example text describing Acato's capabilities
    capabilities_text = (
        "Acato is a software testing and QA company specializing in automation testing, "
        "performance testing, compliance auditing, and continuous integration. "
        "They also handle documentation, scope-of-work analysis, deliverable management, "
        "and test environment maintenance."
    )

    # 1) Parse lines (REGEX) - treat all # as heading-level-1
    lines_classified = parse_markdown_headings(document_text)
    if not lines_classified:
        if debug:
            print("[DEBUG] No headings or text found.")
        return []

    # 2) Refine headings using LLM
    llm_refine = ChatOpenAI(
        model_name="gpt-3.5-turbo",
        temperature=0.0,
        openai_api_key=openai_api_key
    )
    await refine_headings_by_numbering(llm_refine, lines_classified)

    # 3) Build FLAT sections
    flat_sections = build_flat_sections(lines_classified)

    if debug:
        print("\n[DEBUG] === Found Flat Sections ===")
        for i, sec in enumerate(flat_sections):
            text_len = len(" ".join(sec["content"]))
            print(
                f"Section {i+1} Heading: '{sec['heading']}' | length: {text_len}")

    # Create LLMs for classification and summarization
    llm_classify = ChatOpenAI(
        model_name="gpt-3.5-turbo",
        temperature=0.1,
        openai_api_key=openai_api_key
    )
    llm_summary = ChatOpenAI(
        model_name="gpt-3.5-turbo",
        temperature=0.0,
        openai_api_key=openai_api_key
    )

    # We'll chunk each section if it’s large
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=100
    )

    summarized_sections = []

    # Pass 1: Classification
    for sec in flat_sections:
        heading = sec["heading"]
        text = "\n".join(sec["content"]).strip()

        # We'll feed just a snippet of the text for classification
        sample_snippet = text[:1000]

        relevant = await classify_heading_with_llm(
            llm=llm_classify,
            heading=heading,
            snippet=sample_snippet,
            capabilities_text=capabilities_text,
        )

        if not relevant:
            if debug:
                print(
                    f"[DEBUG] Skipping heading '{heading}' - classified IRRELEVANT.")
            continue

        if debug:
            print(f"[DEBUG] Heading '{heading}' is RELEVANT. Summarizing...")

        # Pass 2: Summarize if relevant
        docs = text_splitter.create_documents([text])
        partial_summaries = []
        for d in docs:
            chunk_text = d.page_content.strip()
            if not chunk_text:
                continue
            chunk_summary = await summarize_section(llm_summary, heading, chunk_text)
            if chunk_summary:
                partial_summaries.append(chunk_summary)

        combined_summary = "\n".join(partial_summaries).strip()
        if not combined_summary:
            if debug:
                print(f"[DEBUG] Summary empty for heading '{heading}'")
            continue

        # Strictly enforce no more than 5 bullet points in final output
        final_summary = await enforce_bullet_limit(llm_summary, combined_summary)

        summarized_sections.append({
            "heading": heading,
            "summary": final_summary
        })

        if debug:
            print(
                f"[DEBUG] Final summary for '{heading}':\n{final_summary}\n"
            )

    return summarized_sections

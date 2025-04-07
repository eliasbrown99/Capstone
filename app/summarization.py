import re
import asyncio
from typing import List, Dict, Any

# If you're using "langchain_openai" for ChatOpenAI:
# from langchain_openai import ChatOpenAI

# Otherwise, for official LangChain:
from langchain.chat_models import ChatOpenAI

from langchain.schema import HumanMessage, SystemMessage
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter

##############################################################################
# (A) PARSE (REGEX) -> Label lines as heading-level-x or body-text
##############################################################################


def parse_markdown_headings(document_text: str) -> List[Dict[str, str]]:
    """
    Identify lines that start with # (1..6) as headings (clamped to level 3).
    Everything else is body-text.
    """
    lines = [ln.strip() for ln in document_text.splitlines() if ln.strip()]
    pattern = re.compile(r'^(#{1,6})\s+(.*)$')
    results = []

    for ln in lines:
        match = pattern.match(ln)
        if match:
            hashes = match.group(1)
            heading_text = match.group(2).strip()
            level = min(len(hashes), 3)  # clamp heading-level to 3
            heading_class = f"heading-level-{level}"
            results.append({"text": heading_text, "class": heading_class})
        else:
            results.append({"text": ln, "class": "body-text"})

    return results

##############################################################################
# (B) LLM REFINEMENT -> Confirm actual numbering / roman numeral
##############################################################################


REFINE_HEADING_PROMPT = PromptTemplate(
    input_variables=["heading_text"],
    template="""
You are given a heading line from a Markdown file that starts with '#' characters.
We suspect it might be a "numbered heading" (e.g., "1.", "2.1", "III.", "XIV", etc.).

If the heading truly has a numbering or roman numeral scheme, output EXACTLY:
TRUE_HEADING

Otherwise output EXACTLY:
NOT_HEADING

Heading text: "{heading_text}"
"""
)


async def refine_headings_by_numbering(llm, lines: List[Dict[str, str]]) -> None:
    """
    For each heading line, ask the LLM if it truly has numbering/roman numerals.
    If not, convert that line's class to 'body-text'.
    """
    tasks = []
    to_refine_indices = [
        i for i, item in enumerate(lines)
        if item["class"].startswith("heading-level")
    ]

    for idx in to_refine_indices:
        heading_text = lines[idx]["text"]
        system_msg = SystemMessage(
            content="Output EXACTLY 'TRUE_HEADING' or 'NOT_HEADING'. No extra text.")
        user_msg = HumanMessage(
            content=REFINE_HEADING_PROMPT.format(heading_text=heading_text))

        tasks.append((idx, llm.ainvoke([system_msg, user_msg])))

    results = await asyncio.gather(*[t[1] for t in tasks])

    for (idx, _), response in zip(tasks, results):
        verdict = response.content.strip().upper()
        if verdict != "TRUE_HEADING":
            # Convert to body text
            lines[idx]["class"] = "body-text"

##############################################################################
# (C) CLASSIFY HEADING RELEVANCE
##############################################################################

HEADING_CLASSIFICATION_PROMPT = PromptTemplate(
    input_variables=["capabilities", "heading_text", "content_snippet"],
    template="""
You are an expert analyst reviewing section headers and content from government solicitations.
Acato is a company with the following capabilities:

{capabilities}

Your task is to decide if the **section** is RELEVANT or IRRELEVANT to Acato’s likely role (e.g., awarding or performance).

Heuristics:
- RELEVANT if content includes scope of work, tasks, deliverables, requirements, optional surge support, 
  strategic or operational priorities, key personnel responsibilities, software/testing efforts, etc.
- IRRELEVANT if the content focuses on government-furnished equipment, certifications/regulations, 
  travel/logistics, FAR clauses, place of performance, references, etc.

Output exactly one word: "RELEVANT" or "IRRELEVANT".

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
    Returns True if the LLM says "RELEVANT", False if "IRRELEVANT".
    """
    system_msg = SystemMessage(
        content=(
            "You are a strict binary classifier. Return only 'RELEVANT' or 'IRRELEVANT'."
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
# (D) SUMMARIZE SECTION - Strong prompt for 5 bullet points
##############################################################################

SOW_SUMMARY_PROMPT = PromptTemplate(
    input_variables=["heading", "text"],
    template="""
You are summarizing a document section titled: "{heading}" that likely contains tasks, scope of work,
or responsibilities related to a QA/test role.

**RULES**:
1. You MUST produce no more than 5 bullet points in total.
2. If the text contains more potential items, combine or omit details.
3. Output ONLY those bullet points (no extra commentary).

SECTION TEXT:
{text}
"""
)


async def summarize_section(llm, heading: str, text: str) -> str:
    """
    Summarizes the text, instructing the LLM to create at most 5 bullet points.
    Returns the raw summary from the LLM (which may sometimes exceed 5).
    """
    response = await (SOW_SUMMARY_PROMPT | llm).ainvoke({"heading": heading, "text": text})
    return response.content.strip() if response.content else ""

##############################################################################
# (E) SECOND PASS TO ENFORCE 5 BULLETS IF NEEDED
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
    If the original has more, it must combine or drop them.
    """
    if not text:
        return ""

    system_msg = SystemMessage(
        content=(
            "You must enforce the bullet limit. "
            "Ensure there are no more than 5 bullet points total. Combine or omit if needed."
        )
    )
    user_msg = HumanMessage(
        content=ENFORCE_BULLET_LIMIT_PROMPT.format(raw_summary=text))
    response = await llm.ainvoke([system_msg, user_msg])
    return response.content.strip() if response.content else ""

##############################################################################
# (F) MAIN PIPELINE
##############################################################################


async def detect_headings_and_summarize_llm(
    document_text: str,
    openai_api_key: str,
    debug: bool = True
) -> List[Dict[str, str]]:
    """
    Steps:
    1) Parse doc lines -> heading vs. body (regex).
    2) LLM refinement to confirm heading is truly numbered.
    3) Flat structure: each heading + subsequent body text is a "section."
    4) Classify heading RELEVANT vs IRRELEVANT.
    5) If relevant, feed entire section (chunked if large) to summarization prompt
       that demands at most 5 bullets.
    6) Use a second LLM pass to strictly enforce 5 bullet limit if the model returned more.

    Returns list of dicts: [{ "heading": heading, "summary": summary }, ...].
    """

    # Example text describing Acato's capabilities
    capabilities_text = (
        "Acato is a software testing and QA company specializing in automation testing, "
        "performance testing, compliance auditing, and continuous integration. "
        "They also handle documentation, scope-of-work analysis, deliverable management, "
        "and test environment maintenance."
    )

    # Step 1) Parse lines
    lines_classified = parse_markdown_headings(document_text)
    if not lines_classified:
        if debug:
            print("[DEBUG] No headings or body text found.")
        return []

    # Step 2) LLM-based heading refinement
    llm_refine = ChatOpenAI(
        model_name="gpt-3.5-turbo",
        temperature=0.0,
        openai_api_key=openai_api_key
    )
    await refine_headings_by_numbering(llm_refine, lines_classified)

    # Build a flat list of (heading, content)
    headings_and_content = []
    current_heading = None
    current_content = []

    for item in lines_classified:
        if item["class"].startswith("heading-level"):
            # Finish any previous heading
            if current_heading is not None:
                headings_and_content.append({
                    "heading": current_heading,
                    "content": "\n".join(current_content)
                })
            current_heading = item["text"]
            current_content = []
        else:
            # body text
            current_content.append(item["text"])

    # Catch the last heading if present
    if current_heading is not None:
        headings_and_content.append({
            "heading": current_heading,
            "content": "\n".join(current_content)
        })

    # Step 3) We'll use one LLM for classification, another for summarization
    llm_classify = ChatOpenAI(
        model_name="gpt-3.5-turbo",
        temperature=0.0,
        openai_api_key=openai_api_key
    )
    llm_summary = ChatOpenAI(
        model_name="gpt-3.5-turbo",
        temperature=0.0,
        openai_api_key=openai_api_key
    )

    # If sections can be large, chunk them
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=100
    )

    results = []

    for section in headings_and_content:
        heading = section["heading"]
        content = section["content"]
        snippet = content[:1000]  # classification snippet

        # Step 4) Classify heading
        is_relevant = await classify_heading_with_llm(
            llm=llm_classify,
            heading=heading,
            snippet=snippet,
            capabilities_text=capabilities_text
        )

        if not is_relevant:
            if debug:
                print(f"[DEBUG] Heading '{heading}' -> IRRELEVANT")
            continue

        if debug:
            print(f"[DEBUG] Heading '{heading}' -> RELEVANT. Summarizing...")

        # Step 5) Summarize if relevant
        docs = text_splitter.create_documents([content])
        partial_summaries = []

        for d in docs:
            chunk_text = d.page_content.strip()
            if not chunk_text:
                continue
            chunk_summary = await summarize_section(llm_summary, heading, chunk_text)
            if chunk_summary:
                partial_summaries.append(chunk_summary)

        # Combine chunk summaries
        combined_summary = "\n".join(partial_summaries).strip()
        if not combined_summary:
            continue

        # Step 6) ENFORCE bullet limit with a second LLM pass
        final_summary = await enforce_bullet_limit(llm_summary, combined_summary)

        # Store final
        results.append({
            "heading": heading,
            "summary": final_summary
        })

    return results

# ------------------------------------------------------------------------------
# # Sample usage (uncomment to run directly):
# if __name__ == "__main__":
#     sample_document = """# 1. Introduction
# Acato is being considered for QA tasks...
#
# # I. This Has Roman Numerals
# - Some bullet in the text
# - Another bullet
# Some table or other content
#
# # This is a heading without numbering
# Should become body text, not a heading.
#
# # 2. Scope
# Here are multiple bullet points:
# - Task A
# - Task B
# - Task C
# - Task D
# - Task E
# - Task F
# This might produce more than 5 bullets if the model tries to replicate them all.
# """
#
#     summaries = asyncio.run(
#         detect_headings_and_summarize_llm(
#             sample_document,
#             openai_api_key="YOUR_OPENAI_KEY",
#             debug=True
#         )
#     )
#
#     for s in summaries:
#         print(f"HEADING: {s['heading']}")
#         print(f"SUMMARY:\n{s['summary']}\n")

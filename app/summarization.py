import re
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

##############################################################################
# (A) DETECTING HEADINGS VIA REGEX
##############################################################################

##############################################################################
# (A) DETECTING HEADINGS VIA REGEX
##############################################################################


POTENTIAL_HEADING_PATTERN = re.compile(
    r"""
    ^                           # Start of line
    (\d+(\.\d+)+)\s*           # Require numbering schema like 1.0, 2.1.3 (mandatory)
    (.*)                        # Capture anything following the numbering schema
    $                           # End of line
    """,
    re.VERBOSE | re.IGNORECASE
)


def detect_headings_and_sections(document_text: str):
    """
    Scan each line, see if it looks like a heading using regex, then group subsequent lines
    until the next heading.
    """
    lines = document_text.splitlines()
    sections = []
    current_heading = ""
    current_content = []

    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            continue

        if POTENTIAL_HEADING_PATTERN.search(stripped_line):
            if current_content:
                sections.append({"heading": current_heading,
                                "content": "\n".join(current_content)})
                current_content = []
            current_heading = stripped_line
        else:
            current_content.append(stripped_line)

    if current_content:
        sections.append({"heading": current_heading,
                        "content": "\n".join(current_content)})

    return sections


##############################################################################
# (B) RELEVANCE CHECKS
##############################################################################


RELEVANT_HEADING_KEYWORDS = [
    "scope of work", "tasks", "work expected", "deliverables", "task",
    "responsibility", "services", "requirements", "objectives", "personnel", "introduction", "background"
]


def is_heading_relevant(heading: str) -> bool:
    """Checks if the heading suggests tasks or scope-of-work."""
    return any(kw in heading.lower() for kw in RELEVANT_HEADING_KEYWORDS)

##############################################################################
# (C) PROMPT TEMPLATE
##############################################################################


SOW_SUMMARY_PROMPT = PromptTemplate(
    input_variables=["heading", "text"],
    template="""
You are summarizing a document section titled: "{heading}" which likely contains tasks, scope of work, 
or responsibilities for Acato's testing/QA role.

Your goal: Provide a concise set of EXACTLY 5 bullet points. Only create less than 5 bullet points if and only if the section contains fewer than 
5 unique items.
Each bullet should focus on the specific scope of work or tasks relevant to THIS SECTION ONLY.
DO NOT assume tasks from previous sections—summarize only the text given.

Ignore excessive legal or administrative details (e.g., contract boilerplate, 
travel policy) unless they directly impact these tasks.

If this section is part of a TASK breakdown (e.g., "TASK 1, TASK 2, etc."), treat it as an independent section 
and summarize it on its own.

Also:
1) If abbreviations appear, expand them at least once.
2) Keep the summary high-level and actionable.
3) If the section has a lot of repetitive text or references, combine or condense them.

SECTION TEXT:
{text}
"""
)

##############################################################################
# (D) LLM CREATOR
##############################################################################


def create_summary_llm(openai_api_key: str, model_name="gpt-3.5-turbo"):
    """Initialize an LLM (ChatOpenAI) for summarization."""
    return ChatOpenAI(
        model_name=model_name,
        temperature=0.0,
        openai_api_key=openai_api_key
    )

##############################################################################
# (E) SUMMARIZING A SINGLE SECTION
##############################################################################


async def summarize_section(llm, heading: str, text: str) -> str:
    """
    Summarizes a document section using SOW_SUMMARY_PROMPT.
    Non-relevant sections are discarded entirely.
    Ensures TASK sections are always included.
    """
    if not is_heading_relevant(heading) and not heading.lower().startswith("task"):
        return ""  # Discard non-relevant sections

    result = await (SOW_SUMMARY_PROMPT | llm).ainvoke({"heading": heading, "text": text})
    return result.content.strip() if result.content.strip() else ""

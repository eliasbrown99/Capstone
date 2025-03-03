import re
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

##############################################################################
# (A) DETECTING HEADINGS VIA REGEX
##############################################################################

# Example pattern to detect lines that might be headings:
#  - Lines that contain "scope," "task," etc.
#  - Lines that look like "1.0 INTRODUCTION" or "2.1 SCOPE OF WORK"
# This is a naive approach; adapt as needed for your docs.
POTENTIAL_HEADING_PATTERN = re.compile(
    r"^(?P<heading>[\dA-Z][\dA-Za-z\.\-\s]{0,60}(scope of work|work scope|tasks|deliverables|requirements|section|chapter|part|sow|services).*|\d+(\.\d+)+\s+.*)$",
    re.IGNORECASE
)

def detect_headings_and_sections(document_text: str):
    """
    A naive approach: Scan each line, see if it looks like a heading
    using a regex pattern or known keywords. Then group subsequent lines
    until the next heading.

    Returns a list of dicts:
      [
        { "heading": "X", "content": "..." },
        ...
      ]
    """
    lines = document_text.splitlines()
    sections = []
    current_heading = "Introduction"
    current_content = []

    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            # Skip blank lines
            continue

        # Check if this line matches our heading pattern
        if POTENTIAL_HEADING_PATTERN.search(stripped_line):
            # If we already have a heading & content, store it
            if current_content:
                sections.append({
                    "heading": current_heading,
                    "content": "\n".join(current_content)
                })
                current_content = []
            current_heading = stripped_line
        else:
            current_content.append(stripped_line)

    # Add any leftover content as a final section
    if current_content:
        sections.append({
            "heading": current_heading,
            "content": "\n".join(current_content)
        })

    return sections

##############################################################################
# (B) RELEVANCE CHECKS: HEADING & CONTENT
##############################################################################

# Keywords that might appear in headings relevant to scope of work
RELEVANT_HEADING_KEYWORDS = [
    "scope of work",
    "tasks",
    "work expected",
    "deliverables",
    "responsibilit",
    "services",
    "requirements"
]

def is_heading_relevant(heading: str) -> bool:
    """
    Checks if the heading itself strongly suggests tasks or scope-of-work.
    """
    heading_lower = heading.lower()
    for kw in RELEVANT_HEADING_KEYWORDS:
        if kw in heading_lower:
            return True
    return False

def is_content_relevant(content: str) -> bool:
    """
    Checks if the section content itself contains keywords related to tasks, scope, or QA.
    This is helpful if the heading wasn't obviously relevant, but the text might be.
    """
    relevance_keywords = [
        "scope", "task", "responsibilit", "deliverable", 
        "work statement", "testing", "test", "acato",
        "qa", "quality assurance", "sow"
    ]
    clower = content.lower()
    return any(kw in clower for kw in relevance_keywords)

##############################################################################
# (C) PROMPT TEMPLATES
##############################################################################

# Prompt for sections likely describing tasks or scope-of-work
SOW_SUMMARY_PROMPT = PromptTemplate(
    input_variables=["heading", "text"],
    template="""
You are summarizing a document section titled: "{heading}" which likely contains tasks, scope of work, 
or responsibilities for Acato's testing/QA role.

Your goal: Provide a concise set of bullet points (NO more than 5 bullets).
Each bullet should focus on the scope of work or tasks relevant to Acato.
Ignore excessive legal or administrative details (e.g., contract boilerplate, 
travel policy) unless they directly impact these tasks.

Also:
1) If abbreviations appear, expand them at least once.
2) Keep the summary high-level and actionable.
3) If the section has a lot of repetitive text or references, combine or condense them.

SECTION TEXT:
{text}
"""
)

# Prompt for sections that do NOT mention tasks or scope-of-work
GENERIC_SUMMARY_PROMPT = PromptTemplate(
    input_variables=["heading", "text"],
    template="""
You are summarizing the document section titled: "{heading}" 
which is likely contractual or administrative in nature.

Requirements:
1) If this section does NOT describe tasks or scope-of-work for Acato, 
   produce at most 1 bullet summarizing it at a very high level.
2) If it has absolutely no relevance to tasks, you can skip it (return an empty string).
3) Expand any critical abbreviations once if they appear.

SECTION TEXT:
{text}
"""
)

##############################################################################
# (D) LLM CREATOR
##############################################################################

def create_summary_llm(openai_api_key: str, model_name="gpt-4"):
    """
    Initialize an LLM (ChatOpenAI) for summarization.
    """
    return ChatOpenAI(
        model_name=model_name,
        temperature=0.0,
        openai_api_key=openai_api_key
    )

##############################################################################
# (E) SUMMARIZING A SINGLE SECTION
##############################################################################

async def summarize_section(llm, heading: str, text: str, relevant: bool) -> str:
    """
    Summarizes a single document section.
    If relevant to scope-of-work, uses the SOW_SUMMARY_PROMPT (up to 5 bullets).
    Otherwise, uses GENERIC_SUMMARY_PROMPT (up to 1 bullet or skip).
    Enforces bullet limit in post-processing.
    """
    if relevant:
        prompt = SOW_SUMMARY_PROMPT
    else:
        prompt = GENERIC_SUMMARY_PROMPT

    chain_input = {"heading": heading, "text": text}
    result = await (prompt | llm).ainvoke(chain_input)
    summary = result.content.strip()

    # If the LLM returns empty or "skip", just return that
    if not summary:
        return ""

    # Post-processing to enforce bullet limits
    lines = summary.split("\n")
    clean_lines = []
    bullet_count = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # If the line starts with a dash or bullet, track how many
        if line.startswith("-"):
            bullet_count += 1
        # If relevant, we cut off after 5 bullets
        if relevant and bullet_count > 5:
            break
        # If not relevant, we cut off after 1 bullet
        if not relevant and bullet_count > 1:
            break

        clean_lines.append(line)

    final_summary = "\n".join(clean_lines)
    return final_summary

##############################################################################
# (F) OPTIONAL: HIERARCHICAL OR MULTI-PASS SUMMARIZATION
##############################################################################

# If you still want multi-pass summarization for extremely large documents, 
# you can keep your old hierarchical_summarize approach or do chunk-level merges. 
# However, the code shown here is a direct "detect headings -> summarize each" approach.
#
# For example:
#
# async def hierarchical_summarize(text_list, summarization_chain, max_batch_chars=3000, pass_limit=5) -> str:
#     # Implementation from your prior code if needed
#     ...
#
# Or you can integrate that concept if your docs are extremely large or you need iterative refinement.

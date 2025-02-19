import re
from .models import ACATO_CRITERIA

def chunk_is_relevant_or_exclusion(chunk: str) -> bool:
    """
    Returns True if the chunk mentions any of Acato's core keywords/capabilities,
    or if it mentions any exclusion text. Otherwise False.
    """
    clower = chunk.lower()
    for _, kw_list in ACATO_CRITERIA["core_keywords"].items():
        for kw in kw_list:
            if kw.lower() in clower:
                return True
    for cap in ACATO_CRITERIA["core_capabilities"]:
        if cap.lower() in clower:
            return True
    for exc in ACATO_CRITERIA["exclusions"]:
        if exc.lower() in clower:
            return True
    return False

def analyze_keywords(text: str) -> dict:
    """Analyze keyword matches in the text."""
    matches = {}
    for category, keywords in ACATO_CRITERIA["core_keywords"].items():
        found = []
        for keyword in keywords:
            pattern = f".{{30}}{keyword}.{{30}}"
            contexts = re.finditer(pattern, text.lower())
            for match in contexts:
                found.append(match.group())
        if found:
            matches[category] = found
    return matches

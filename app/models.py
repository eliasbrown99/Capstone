from pydantic import BaseModel
from typing import List

class SectionSummary(BaseModel):
    heading: str
    summary: str

class SummariesResponse(BaseModel):
    summaries: List[SectionSummary]

#
# Keep or remove any old classification logic as needed.
#

from pydantic import BaseModel
from typing import Dict, List

class SolicitationClassification(BaseModel):
    classification: str
    confidence: float
    reasoning: str
    keyword_matches: Dict[str, List[str]]
    scope_analysis: Dict[str, bool]
    exclusion_flags: List[str]

ACATO_CRITERIA = {
    "core_keywords": {
        "testing": [
            "testing", "test", "quality assurance", "QA",
            "software quality", "integration testing",
            "system acceptability testing", "performance testing",
            "functional testing", "exploratory testing",
            "regression testing", "UI testing", "UX testing", "UI/UX testing"
        ],
        "software": [
            "software", "application", "system", "platform",
            "enterprise software", "software quality"
        ]
    },
    "exclusions": [
        "cyber security testing",
        "hardware testing",
        "software development",
        "security testing"
    ],
    "core_capabilities": [
        "functional testing",
        "exploratory testing",
        "regression testing",
        "UI/UX testing",
        "test automation",
        "quality assurance",
        "cross-platform testing",
        "agile testing",
        "quality program implementation"
    ]
}

EVALUATION_SCHEMA = {
    "title": "EvaluationSchema",
    "description": "Schema for evaluating solicitations for Acato",
    "type": "object",
    "properties": {
        "has_testing_focus": {
            "type": "boolean",
            "description": "Does the solicitation primarily focus on software testing or quality assurance?"
        },
        "full_scope_delivery": {
            "type": "boolean",
            "description": "Can Acato independently deliver the full scope of work?"
        },
        "requires_partners": {
            "type": "boolean",
            "description": "Does the work require partnership with other organizations?"
        },
        "matches_past_work": {
            "type": "boolean",
            "description": "Is this similar to work done in the past 12-18 months?"
        },
        "contains_exclusions": {
            "type": "boolean",
            "description": "Does it involve excluded areas (cyber security, hardware testing, software development)?"
        }
    },
    "required": [
        "has_testing_focus",
        "full_scope_delivery",
        "requires_partners",
        "matches_past_work",
        "contains_exclusions"
    ]
}

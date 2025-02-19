import os
from fastapi import HTTPException
from langchain_openai import ChatOpenAI
from langchain.schema import Document
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain

from .models import ACATO_CRITERIA, EVALUATION_SCHEMA
from .summarization import create_summarization_chain, hierarchical_summarize
from .document_loader import DocumentLoader
from .utils import chunk_is_relevant_or_exclusion, analyze_keywords

class SolicitationService:
    def __init__(self, openai_api_key: str):
        debug_api_key = openai_api_key

        # LLM for evaluation & classification (using GPT-4)
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0.1,
            openai_api_key=debug_api_key
        )

        # Setup Document Loader
        self.document_loader = DocumentLoader()

        # Summarization chain for chunk-level summaries using new composition approach
        self.summarization_chain = create_summarization_chain(debug_api_key)

        # Updated evaluation chain using with_structured_output with method set explicitly.
        self.evaluation_chain = self.llm.with_structured_output(EVALUATION_SCHEMA, method="function_calling")

        # Classification chain with custom prompt
        classification_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                """You are an expert at evaluating solicitations for Acato, a software testing and quality assurance company.

Key Evaluation Criteria:
1. Testing Focus: Look for keywords like "testing", "quality assurance", "QA" in proper context
2. Scope Analysis: Focus on scope of work/tasks sections
3. Capability Match: Evaluate against Acato's core capabilities:
   {core_capabilities}

Exclusions (Automatic Bad Fit):
- Cyber security testing
- Hardware testing
- Pure software development

Classification Guidelines:
- "good_fit": Can independently deliver full scope, matches past work (12-18 months)
- "needs_partners": Can deliver portion of scope but needs partners
- "bad_fit": Cannot deliver full scope or contains exclusion criteria

Evaluate based on keyword matches, scope analysis, and exclusion criteria."""
            ),
            HumanMessagePromptTemplate.from_template(
                """Solicitation Content: {text}

Evaluation Results: {evaluation_results}

Keyword Matches: {keyword_matches}

Provide your classification with detailed reasoning."""
            )
        ])

        self.classification_chain = create_stuff_documents_chain(
            llm=self.llm,
            prompt=classification_prompt,
            document_variable_name="text"
        )

    async def classify_solicitation(self, documents: list) -> dict:
        """
        Multi-step logic with chunk filtering, hierarchical summarization,
        and "sole exclusion" logic.
        """
        full_text = "\n".join(documents)
        filtered_docs = [chunk for chunk in documents if chunk_is_relevant_or_exclusion(chunk)]
        
        if not filtered_docs:
            found_exclusion = any(exc.lower() in full_text.lower() for exc in ACATO_CRITERIA["exclusions"])
            if found_exclusion:
                return {
                    "classification": "bad_fit",
                    "confidence": 0.85,
                    "reasoning": "Document is solely about exclusion criteria; no relevant testing content.",
                    "keyword_matches": {},
                    "scope_analysis": {
                        "has_testing_focus": False,
                        "full_scope_delivery": False,
                        "requires_partners": False,
                        "matches_past_work": False,
                        "contains_exclusions": True
                    },
                    "exclusion_flags": [exc for exc in ACATO_CRITERIA["exclusions"] if exc.lower() in full_text.lower()]
                }
            else:
                return {
                    "classification": "bad_fit",
                    "confidence": 0.85,
                    "reasoning": "Document has no relevant or exclusion content, so no scope for Acato.",
                    "keyword_matches": {},
                    "scope_analysis": {
                        "has_testing_focus": False,
                        "full_scope_delivery": False,
                        "requires_partners": False,
                        "matches_past_work": False,
                        "contains_exclusions": False
                    },
                    "exclusion_flags": []
                }
        final_summary = await hierarchical_summarize(
            filtered_docs,
            self.summarization_chain,
            max_batch_chars=3000,
            pass_limit=5
        )
        keyword_matches = analyze_keywords(full_text)
        exclusion_flags = [exclusion for exclusion in ACATO_CRITERIA["exclusions"] if exclusion.lower() in full_text.lower()]

        evaluation_results = await self.evaluation_chain.ainvoke(final_summary)
        doc_objects = [Document(page_content=final_summary)]
        classification_result = await self.classification_chain.ainvoke({
            "text": doc_objects,
            "core_capabilities": ", ".join(ACATO_CRITERIA["core_capabilities"]),
            "evaluation_results": str(evaluation_results),
            "keyword_matches": str(keyword_matches)
        })
        classification_str = classification_result.lower()
        if "needs partners" in classification_str:
            classification = "needs_partners"
        elif "good_fit" in classification_str:
            classification = "good_fit"
        elif "bad_fit" in classification_str:
            classification = "bad_fit"
        else:
            classification = "bad_fit"
        scope_analysis = {
            "has_testing_focus": False,
            "full_scope_delivery": False,
            "requires_partners": False,
            "matches_past_work": False,
            "contains_exclusions": False
        }
        final_result = {
            "classification": classification,
            "confidence": 0.85,
            "reasoning": classification_result,
            "keyword_matches": keyword_matches,
            "scope_analysis": scope_analysis,
            "exclusion_flags": exclusion_flags
        }
        return final_result

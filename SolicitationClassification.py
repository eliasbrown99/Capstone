from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
# Removed deprecated create_tagging_chain import
# from langchain.chains import create_tagging_chain
from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader
from langchain_openai import ChatOpenAI
# Removed deprecated LLMChain import since we now use composition (pipe operator)
# from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
import re
from pathlib import Path
from typing import List, Dict, Union

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load environment variables
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError(
        "OPENAI_API_KEY environment variable is not set. Please set it in your .env file."
    )

###############################################################################
# Pydantic Model (response schema)
###############################################################################


class SolicitationClassification(BaseModel):
    classification: str
    confidence: float
    reasoning: str
    keyword_matches: Dict[str, List[str]]
    scope_analysis: Dict[str, bool]
    exclusion_flags: List[str]

###############################################################################
# Criteria and Evaluation Schema
###############################################################################


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

# Updated evaluation schema with required top-level keys for function calling
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

###############################################################################
# Summarization Prompt + Single-Chunk Summaries
###############################################################################

SUMMARY_PROMPT = PromptTemplate(
    input_variables=["chunk_text"],
    template="""
You are an expert at summarizing text. Summarize the following chunk:

{chunk_text}

Return a concise summary highlighting only essential details.
"""
)


def create_summarization_chain(openai_api_key: str):
    """Builds a chain that summarizes a single text chunk using the new composition approach."""
    llm = ChatOpenAI(
        model_name="gpt-3.5-turbo",  # or "gpt-4" if preferred for summarization
        temperature=0.0,
        openai_api_key=openai_api_key
    )
    # Compose the chain by piping the prompt to the LLM
    return SUMMARY_PROMPT | llm

###############################################################################
# Filtering Step
###############################################################################


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

###############################################################################
# Hierarchical Summarization Utility
###############################################################################


async def hierarchical_summarize(
    text_list: List[str],
    summarization_chain,
    max_batch_chars: int = 3000,
    pass_limit: int = 5
) -> str:
    """
    Summarize a list of text chunks in multiple passes if necessary.

    1) Group chunks into batches of ~max_batch_chars.
    2) Summarize each batch to produce partial summaries.
    3) Repeat until a single summary remains or pass_limit is reached.

    Return the final summary.
    """
    current_list = text_list
    pass_count = 0

    while len(current_list) > 1 and pass_count < pass_limit:
        pass_count += 1

        batch_summaries = []
        buffer = []
        buffer_size = 0

        for chunk in current_list:
            chunk_len = len(chunk)
            if buffer and (buffer_size + chunk_len > max_batch_chars):
                buffer_text = "\n\n".join(buffer)
                result_message = await summarization_chain.ainvoke({"chunk_text": buffer_text})
                batch_summaries.append(result_message.content.strip())
                buffer = [chunk]
                buffer_size = chunk_len
            else:
                buffer.append(chunk)
                buffer_size += chunk_len

        if buffer:
            buffer_text = "\n\n".join(buffer)
            result_message = await summarization_chain.ainvoke({"chunk_text": buffer_text})
            batch_summaries.append(result_message.content.strip())

        current_list = batch_summaries

    if len(current_list) == 1:
        return current_list[0]
    else:
        return "\n\n".join(current_list)


###############################################################################
# SolicitationService with Multi-Pass Summarization + "Sole Exclusion" Logic
###############################################################################


class SolicitationService:
    def __init__(self):
        debug_api_key = api_key

        # LLM for evaluation & classification (using GPT-4)
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0.1,
            openai_api_key=debug_api_key
        )

        # Text splitter setup
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

        # Summarization chain for chunk-level summaries using new composition approach
        self.summarization_chain = create_summarization_chain(debug_api_key)

        # Updated evaluation chain using with_structured_output with method set explicitly.
        self.evaluation_chain = self.llm.with_structured_output(
            EVALUATION_SCHEMA, method="function_calling"
        )

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

    def analyze_keywords(self, text: str) -> Dict[str, List[str]]:
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

    async def load_document(self, file: UploadFile) -> List[str]:
        """
        Load and process a document file, returning a list of text chunks.
        Supports PDF and Word documents.
        """
        temp_path = Path(f"/tmp/{file.filename}")
        try:
            with temp_path.open("wb") as f:
                content = await file.read()
                f.write(content)
            if file.filename.endswith('.pdf'):
                loader = PyPDFLoader(str(temp_path))
            elif file.filename.endswith(('.doc', '.docx')):
                loader = UnstructuredWordDocumentLoader(str(temp_path))
            else:
                raise HTTPException(
                    status_code=400, detail="Unsupported file type")
            docs = loader.load()
            splits = self.text_splitter.split_documents(docs)
            text_chunks = [d.page_content for d in splits]
            temp_path.unlink()
            return text_chunks
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise HTTPException(
                status_code=500,
                detail=f"Error loading document: {str(e)}"
            )

    async def classify_solicitation(self, documents: List[str]) -> Dict[str, Union[str, float, List[str], Dict]]:
        """
        Multi-step logic with chunk filtering, hierarchical summarization,
        and "sole exclusion" logic:

        1) Filter out chunks that mention no relevant or exclusion terms.
        2) If no chunks are kept, check if the document is solely about an exclusion.
        3) If relevant chunks exist, hierarchically summarize them.
        4) Evaluate the summary and perform final classification.
        """
        full_text = "\n".join(documents)
        filtered_docs = []
        for chunk_str in documents:
            if chunk_is_relevant_or_exclusion(chunk_str):
                filtered_docs.append(chunk_str)
        if not filtered_docs:
            found_exclusion = any(exc.lower() in full_text.lower()
                                  for exc in ACATO_CRITERIA["exclusions"])
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
        keyword_matches = self.analyze_keywords(full_text)
        exclusion_flags = [exclusion for exclusion in ACATO_CRITERIA["exclusions"]
                           if exclusion.lower() in full_text.lower()]
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

###############################################################################
# FastAPI App
###############################################################################


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

solicitation_service = SolicitationService()


@app.post("/classify/", response_model=SolicitationClassification)
async def classify_document(file: UploadFile):
    documents = await solicitation_service.load_document(file)
    result = await solicitation_service.classify_solicitation(documents)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
# Removed deprecated create_tagging_chain import
# from langchain.chains import create_tagging_chain
# Removed deprecated LLMChain import since we now use composition (pipe operator)
# from langchain.chains import LLMChain


# Load environment variables
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError(
        "OPENAI_API_KEY environment variable is not set. Please set it in your .env file."
    )

###############################################################################
# Pydantic Model (response schema)
###############################################################################


class SolicitationClassification(BaseModel):
    classification: str
    confidence: float
    reasoning: str
    keyword_matches: Dict[str, List[str]]
    scope_analysis: Dict[str, bool]
    exclusion_flags: List[str]

###############################################################################
# Criteria and Evaluation Schema
###############################################################################


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

# Updated evaluation schema with required top-level keys for function calling
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

###############################################################################
# Summarization Prompt + Single-Chunk Summaries
###############################################################################

SUMMARY_PROMPT = PromptTemplate(
    input_variables=["chunk_text"],
    template="""
You are an expert at summarizing text. Summarize the following chunk:

{chunk_text}

Return a concise summary highlighting only essential details.
"""
)


def create_summarization_chain(openai_api_key: str):
    """Builds a chain that summarizes a single text chunk using the new composition approach."""
    llm = ChatOpenAI(
        model_name="gpt-3.5-turbo",  # or "gpt-4" if preferred for summarization
        temperature=0.0,
        openai_api_key=openai_api_key
    )
    # Compose the chain by piping the prompt to the LLM
    return SUMMARY_PROMPT | llm

###############################################################################
# Filtering Step
###############################################################################


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

###############################################################################
# Hierarchical Summarization Utility
###############################################################################


async def hierarchical_summarize(
    text_list: List[str],
    summarization_chain,
    max_batch_chars: int = 3000,
    pass_limit: int = 5
) -> str:
    """
    Summarize a list of text chunks in multiple passes if necessary.

    1) Group chunks into batches of ~max_batch_chars.
    2) Summarize each batch to produce partial summaries.
    3) Repeat until a single summary remains or pass_limit is reached.

    Return the final summary.
    """
    current_list = text_list
    pass_count = 0

    while len(current_list) > 1 and pass_count < pass_limit:
        pass_count += 1

        batch_summaries = []
        buffer = []
        buffer_size = 0

        for chunk in current_list:
            chunk_len = len(chunk)
            if buffer and (buffer_size + chunk_len > max_batch_chars):
                buffer_text = "\n\n".join(buffer)
                # Use ainvoke() for asynchronous invocation
                summary = await summarization_chain.ainvoke({"chunk_text": buffer_text})
                batch_summaries.append(summary.strip())
                buffer = [chunk]
                buffer_size = chunk_len
            else:
                buffer.append(chunk)
                buffer_size += chunk_len

        if buffer:
            buffer_text = "\n\n".join(buffer)
            summary = await summarization_chain.ainvoke({"chunk_text": buffer_text})
            batch_summaries.append(summary.strip())

        current_list = batch_summaries

    if len(current_list) == 1:
        return current_list[0]
    else:
        return "\n\n".join(current_list)

###############################################################################
# SolicitationService with Multi-Pass Summarization + "Sole Exclusion" Logic
###############################################################################


class SolicitationService:
    def __init__(self):
        debug_api_key = api_key

        # LLM for evaluation & classification (using GPT-4)
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0.1,
            openai_api_key=debug_api_key
        )

        # Text splitter setup
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

        # Summarization chain for chunk-level summaries using new composition approach
        self.summarization_chain = create_summarization_chain(debug_api_key)

        # Updated evaluation chain using with_structured_output with method set explicitly.
        self.evaluation_chain = self.llm.with_structured_output(
            EVALUATION_SCHEMA, method="function_calling"
        )

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

    def analyze_keywords(self, text: str) -> Dict[str, List[str]]:
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

    async def load_document(self, file: UploadFile) -> List[str]:
        """
        Load and process a document file, returning a list of text chunks.
        Supports PDF and Word documents.
        """
        temp_path = Path(f"/tmp/{file.filename}")
        try:
            with temp_path.open("wb") as f:
                content = await file.read()
                f.write(content)
            if file.filename.endswith('.pdf'):
                loader = PyPDFLoader(str(temp_path))
            elif file.filename.endswith(('.doc', '.docx')):
                loader = UnstructuredWordDocumentLoader(str(temp_path))
            else:
                raise HTTPException(
                    status_code=400, detail="Unsupported file type")
            docs = loader.load()
            splits = self.text_splitter.split_documents(docs)
            text_chunks = [d.page_content for d in splits]
            temp_path.unlink()
            return text_chunks
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise HTTPException(
                status_code=500,
                detail=f"Error loading document: {str(e)}"
            )

    async def classify_solicitation(self, documents: List[str]) -> Dict[str, Union[str, float, List[str], Dict]]:
        """
        Multi-step logic with chunk filtering, hierarchical summarization,
        and "sole exclusion" logic:

        1) Filter out chunks that mention no relevant or exclusion terms.
        2) If no chunks are kept, check if the document is solely about an exclusion.
        3) If relevant chunks exist, hierarchically summarize them.
        4) Evaluate the summary and perform final classification.
        """
        full_text = "\n".join(documents)
        filtered_docs = []
        for chunk_str in documents:
            if chunk_is_relevant_or_exclusion(chunk_str):
                filtered_docs.append(chunk_str)
        if not filtered_docs:
            found_exclusion = any(exc.lower() in full_text.lower()
                                  for exc in ACATO_CRITERIA["exclusions"])
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
        keyword_matches = self.analyze_keywords(full_text)
        exclusion_flags = [exclusion for exclusion in ACATO_CRITERIA["exclusions"]
                           if exclusion.lower() in full_text.lower()]
        # Update here: pass final_summary directly (a str) instead of a dict
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


###############################################################################
# FastAPI App
###############################################################################


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

solicitation_service = SolicitationService()


@app.post("/classify/", response_model=SolicitationClassification)
async def classify_document(file: UploadFile):
    documents = await solicitation_service.load_document(file)
    result = await solicitation_service.classify_solicitation(documents)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

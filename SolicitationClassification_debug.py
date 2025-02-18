from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_tagging_chain
from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Union

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# For verbose HTTP-level logging from httpx (used by OpenAI's library)
import httpx
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.DEBUG)

###############################################################################
# 1. Configure logging
###############################################################################
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

###############################################################################
# 2. Load .env & Debug
###############################################################################
logger.debug("Loading .env file...")
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError(
        "OPENAI_API_KEY environment variable is not set. Please set it in your .env file."
    )
masked_key = api_key[:5] + "..." if api_key else None
logger.debug(f"OPENAI_API_KEY found (masked): {masked_key}")

###############################################################################
# 3. Pydantic Model (response schema)
###############################################################################


class SolicitationClassification(BaseModel):
    classification: str
    confidence: float
    reasoning: str
    keyword_matches: Dict[str, List[str]]
    scope_analysis: Dict[str, bool]
    exclusion_flags: List[str]


###############################################################################
# 4. Criteria, etc.
###############################################################################


# A dictionary that defines:
# Core Keywords: 'testing' and 'software' listing phrases that signal relevance
# Exclusions: Keywords for topics that should trigger a 'bad_fit' fit if they dominate the content
# Core Capabilities: Lists Acato's service capabilities used later for matching
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


# A JSON schema outlining properties (each with type and descrption) that the evaluation chainn must address
EVALUATION_SCHEMA = {
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
# 5. Summarization Prompt + Single-Chunk Summaries
###############################################################################


# A prompt template is defined that instructs the gpt to summarize a given chunck of texst, focusing on only essential details
SUMMARY_PROMPT = PromptTemplate(
    input_variables=["chunk_text"],
    template="""
You are an expert at summarizing text. Summarize the following chunk:

{chunk_text}

Return a concise summary highlighting only essential details.
"""
)


# This function initializes a new LLMChain configured with the gpt of choice and one that follows the summarization prompt defined above
# It returns a chain that takes a single text chunk and outputs its summary
def create_summarization_chain(openai_api_key: str) -> LLMChain:
    """Builds a chain that summarizes a single text chunk."""
    llm = ChatOpenAI(
        model_name="gpt-3.5-turbo",  # or "gpt-4" if you prefer for summarization
        temperature=0.0,
        openai_api_key=openai_api_key
    )
    return LLMChain(llm=llm, prompt=SUMMARY_PROMPT)

###############################################################################
# 6. Filtering Step
###############################################################################


# This function receives a chunk, converts it to lowercase, and checks if 'core_keywords' appear in the chunk,
# if core_capabilities appear in the chunk, and if any 'exclusions' appear in the chunk.
# Returns True if any match is found, otherwise False
def chunk_is_relevant_or_exclusion(chunk: str) -> bool:
    """
    Returns True if the chunk mentions any of Acato's core keywords/capabilities,
    or if it mentions any exclusion text. Otherwise False (skip it).
    """
    clower = chunk.lower()

    # Check for core_keywords
    for _, kw_list in ACATO_CRITERIA["core_keywords"].items():
        for kw in kw_list:
            if kw.lower() in clower:
                return True

    # Check for core_capabilities
    for cap in ACATO_CRITERIA["core_capabilities"]:
        if cap.lower() in clower:
            return True

    # Check for exclusions
    for exc in ACATO_CRITERIA["exclusions"]:
        if exc.lower() in clower:
            return True

    return False

###############################################################################
# 7. Hierarchical Summarization Utility
###############################################################################

# Hanndles cases where the document is too large to summarize in one go
# Groups text chunks into batches such that the total char count does not exceed 3000 limit
# For each batch, calls the summarization chain (via 'arun', an async version) to produce a summary
# If more than one summary is produced, it repeats the batching and summarization on the partial summaries. This loop continues until only one final summary is obtained
# or max number of passes is reached
# returns the final condensed summary


async def hierarchical_summarize(
    text_list: List[str],
    summarization_chain: LLMChain,
    max_batch_chars: int = 3000,
    pass_limit: int = 5
) -> str:
    """
    Summarize a list of text chunks in multiple passes if necessary, so no single
    request is too large for GPT.

    1) Group chunks into ~max_batch_chars each.
    2) Summarize each batch => partial summaries.
    3) If we produce >1 partial summary, repeat until we're down to 1 or pass_limit is reached.

    Return the final summary (string).
    """
    current_list = text_list
    pass_count = 0

    while len(current_list) > 1 and pass_count < pass_limit:
        pass_count += 1
        logging.debug(
            f"[hierarchical_summarize] Pass #{pass_count}, input items: {len(current_list)}")

        batch_summaries = []
        buffer = []
        buffer_size = 0

        for chunk in current_list:
            chunk_len = len(chunk)
            if buffer and (buffer_size + chunk_len > max_batch_chars):
                # Summarize the current buffer
                buffer_text = "\n\n".join(buffer)
                summary = await summarization_chain.arun({"chunk_text": buffer_text})
                batch_summaries.append(summary.strip())
                buffer = [chunk]
                buffer_size = chunk_len
            else:
                buffer.append(chunk)
                buffer_size += chunk_len

        # Leftover buffer
        if buffer:
            buffer_text = "\n\n".join(buffer)
            summary = await summarization_chain.arun({"chunk_text": buffer_text})
            batch_summaries.append(summary.strip())

        logging.debug(
            f"[hierarchical_summarize] pass #{pass_count} => partial summaries: {len(batch_summaries)}")
        current_list = batch_summaries

    if len(current_list) == 1:
        return current_list[0]
    else:
        # Pass limit reached but still multiple partial summaries => just join them
        return "\n\n".join(current_list)

###############################################################################
# 8. SolicitationService with Multi-Pass Summarization + "Sole Exclusion" Logic
###############################################################################


class SolicitationService:
    def __init__(self):
        logger.debug("Initializing SolicitationService...")

        # Reuse the globally loaded API key
        debug_api_key = api_key
        logger.debug(
            f"[SolicitationService] ENV KEY (masked): {debug_api_key[:5]}...")

        # 8.1. LLM for evaluation & classification
        logger.debug(
            "Creating ChatOpenAI instance for evaluation/classification (GPT-4)...")
        self.llm = ChatOpenAI(
            model_name="gpt-4",  # The final classification uses GPT-4
            temperature=0.1,
            openai_api_key=debug_api_key
        )
        logger.debug("ChatOpenAI instance created.")

        # 8.2. Text splitter
        logger.debug("Setting up RecursiveCharacterTextSplitter...")
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

        # 8.3. Summarization chain (for chunk-level)
        logger.debug(
            "Creating summarization chain for chunk-level summaries...")
        self.summarization_chain = create_summarization_chain(debug_api_key)

        # 8.4. Create the evaluation chain (tagging)
        logger.debug("Creating tagging chain (evaluation_chain)...")
        self.evaluation_chain = create_tagging_chain(
            EVALUATION_SCHEMA,
            self.llm
        )

        # 8.5. Create the final classification chain (stuff documents chain)
        logger.debug(
            "Creating classification chain with create_stuff_documents_chain...")
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

        logger.debug(
            "SolicitationService initialized with hierarchical summarization + updated exclusion logic.")

    def analyze_keywords(self, text: str) -> Dict[str, List[str]]:
        """Analyze keyword matches in the text."""
        logger.debug("Analyzing keywords in text...")
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
        logger.debug(f"Keyword analysis found matches: {matches}")
        return matches

    async def load_document(self, file: UploadFile) -> List[str]:
        """Load and process a document file, returning a list of text chunks."""
        logger.debug(f"load_document called with file: {file.filename}")
        temp_path = Path(f"/tmp/{file.filename}")

        try:
            # Save file
            logger.debug(f"Saving upload to {temp_path}...")
            with temp_path.open("wb") as f:
                content = await file.read()
                f.write(content)
            logger.debug("File saved successfully.")

            # Detect file type
            if file.filename.endswith('.pdf'):
                logger.debug(
                    f"Detected PDF. Loading {temp_path} with PyPDFLoader...")
                loader = PyPDFLoader(str(temp_path))
            elif file.filename.endswith(('.doc', '.docx')):
                logger.debug(
                    f"Detected Word doc. Loading {temp_path} with UnstructuredWordDocumentLoader...")
                loader = UnstructuredWordDocumentLoader(str(temp_path))
            else:
                logger.error("Unsupported file type attempted.")
                raise HTTPException(
                    status_code=400, detail="Unsupported file type")

            # Load & split
            logger.debug("Loading the file via the chosen loader...")
            docs = loader.load()
            logger.debug(f"Loaded docs: {docs}")
            logger.debug("Splitting documents...")
            splits = self.text_splitter.split_documents(docs)
            logger.debug(f"Number of chunks: {len(splits)}")

            # Convert each split to raw text
            text_chunks = [d.page_content for d in splits]
            logger.debug(f"Generated {len(text_chunks)} text chunks.")

            temp_path.unlink()
            logger.debug("Temp file deleted.")
            return text_chunks

        except Exception as e:
            logger.error(f"Error loading document: {e}")
            if temp_path.exists():
                temp_path.unlink()
            raise HTTPException(
                status_code=500,
                detail=f"Error loading document: {str(e)}"
            )

    async def classify_solicitation(self, documents: List[str]) -> Dict[str, Union[str, float, List[str], Dict]]:
        """
        Multi-step logic with chunk filtering + hierarchical summarization,
        and "sole exclusion" logic:

        1) Filter out chunks that mention no relevant or exclusion terms.
        2) If none kept => check if doc is solely about an exclusion. If so => "bad_fit".
        3) If we keep some => hierarchical summarize them in multiple passes.
        4) Evaluate chain + classification chain on final summary.
        5) Do full-text keyword analysis + gather exclusion flags, but only treat
           them as "bad_fit" if the doc has no relevant chunks (solely about exclusion).
        """
        logger.debug("classify_solicitation called.")
        try:
            # (A) Full text for global analysis
            full_text = "\n".join(documents)
            logger.debug(f"Full text length: {len(full_text)}")

            # (B) Filter out irrelevant chunks
            logger.debug("Filtering chunks for relevant or exclusion terms...")
            filtered_docs = []
            for i, chunk_str in enumerate(documents, start=1):
                if chunk_is_relevant_or_exclusion(chunk_str):
                    filtered_docs.append(chunk_str)
                else:
                    logger.debug(
                        f"Skipping chunk {i}/{len(documents)} - no relevant/exclusion keywords.")

            logger.debug(
                f"Kept {len(filtered_docs)} chunks out of {len(documents)} total.")

            # (C) Check if we have zero kept chunks
            if not filtered_docs:
                logger.debug(
                    "No relevant chunks found. Checking if doc mentions an exclusion at all.")
                found_exclusion = any(exc.lower() in full_text.lower()
                                      for exc in ACATO_CRITERIA["exclusions"])

                if found_exclusion:
                    logger.debug(
                        "Doc is solely about an exclusion. Marking as bad_fit.")
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
                    logger.debug(
                        "Doc has no relevant content nor any recognized exclusions => bad_fit.")
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

            # (D) We have some relevant or exclusion chunks => Summarize them in multiple passes
            logger.debug("Using hierarchical summarization on kept chunks...")
            final_summary = await hierarchical_summarize(
                filtered_docs,
                self.summarization_chain,
                max_batch_chars=3000,
                pass_limit=5
            )
            logger.debug(
                f"Final summary length after multi-pass: {len(final_summary)}")

            # (E) Analyze keywords on full original text
            keyword_matches = self.analyze_keywords(full_text)

            # Gather exclusion flags (for reference)
            exclusion_flags = [exclusion for exclusion in ACATO_CRITERIA["exclusions"]
                               if exclusion.lower() in full_text.lower()]

            # (F) Evaluate chain with final_summary
            logger.debug(
                "Invoking evaluation_chain on final_summary (just for logging).")
            evaluation_results = await self.evaluation_chain.ainvoke({"input": final_summary})
            logger.debug(f"evaluation_results: {evaluation_results}")

            # (G) classification_chain with final_summary
            doc_objects = [Document(page_content=final_summary)]
            logger.debug("Invoking classification_chain on final_summary doc.")
            classification_result = await self.classification_chain.ainvoke({
                "text": doc_objects,
                "core_capabilities": ", ".join(ACATO_CRITERIA["core_capabilities"]),
                "evaluation_results": str(evaluation_results),
                "keyword_matches": str(keyword_matches)
            })
            logger.debug(f"classification_result: {classification_result}")

            # (H) Parse final GPT text
            classification_str = classification_result.lower()
            if "needs partners" in classification_str:
                classification = "needs_partners"
            elif "good_fit" in classification_str:
                classification = "good_fit"
            elif "bad_fit" in classification_str:
                classification = "bad_fit"
            else:
                classification = "bad_fit"

            logger.debug(f"Classification from GPT: {classification}")

            # (I) Return a default scope_analysis to satisfy Pydantic
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
            logger.debug(f"Final classification result: {final_result}")
            return final_result

        except Exception as e:
            logger.error(f"Error in classification: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Classification error: {str(e)}"
            )


###############################################################################
# 9. FastAPI App
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
    """Endpoint to classify an uploaded solicitation document using hierarchical summarization + updated exclusion logic:
       'Exclusion criteria' only cause bad_fit if they are the sole topics."""
    logger.debug(f"Received POST /classify/ with file: {file.filename}")
    documents = await solicitation_service.load_document(file)
    logger.debug(
        "Document load complete; now classifying with multi-step summarization & updated exclusion logic...")
    result = await solicitation_service.classify_solicitation(documents)
    logger.debug("Classification complete; returning response...")
    return result

if __name__ == "__main__":
    import uvicorn
    logger.debug("Starting uvicorn on 0.0.0.0:8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

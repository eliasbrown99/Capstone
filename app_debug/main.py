import logging
import httpx

# Configure HTTPX debug
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.DEBUG)

# Configure overall logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

logger.debug("Loading .env file...")

import os
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app_debug.services import SolicitationService
from app_debug.models import SolicitationClassification

# Load environment
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set. Please set it in your .env file.")

# Masked key for debug logs
masked_key = api_key[:5] + "..." if api_key else None
logger.debug(f"OPENAI_API_KEY found (masked): {masked_key}")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate the service with debug logging
solicitation_service = SolicitationService(api_key)

@app.post("/classify/", response_model=SolicitationClassification)
async def classify_document(file: UploadFile):
    logger.debug(f"Received POST /classify/ with file: {file.filename}")
    documents = await solicitation_service.document_loader.load_document(file)
    logger.debug("Document load complete; now classifying...")
    result = await solicitation_service.classify_solicitation(documents)
    logger.debug("Classification complete; returning response.")
    return result

if __name__ == "__main__":
    logger.debug("Starting uvicorn on 0.0.0.0:8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

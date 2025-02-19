from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv

from app.services import SolicitationService
from app.models import SolicitationClassification

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set. Please set it in your .env file.")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

solicitation_service = SolicitationService(api_key)

@app.post("/classify/", response_model=SolicitationClassification)
async def classify_document(file: UploadFile):
    documents = await solicitation_service.document_loader.load_document(file)
    result = await solicitation_service.classify_solicitation(documents)
    return result

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

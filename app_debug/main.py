from fastapi import FastAPI, UploadFile, Depends, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import SessionLocal, Summary
from app.services import SolicitationService
from fastapi import HTTPException
from fastapi import Query
from fastapi import UploadFile
from datetime import datetime, timezone

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

async def get_db():
    async with SessionLocal() as session:
        yield session

@app.post("/summarize/")
async def summarize_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """
    Accepts an uploaded document, summarizes it, and stores the result in the database.
    """
    filename = file.filename
    upload_time = datetime.now(timezone.utc)

    result = await solicitation_service.summarize_document(file)

    new_summary = Summary(
        filename = filename,
        upload_time=upload_time,
        summary = result,
    )
    
    db.add(new_summary)
    db.commit()
    db.refresh(new_summary)
    await db.commit()

    return {"summaries": [{"id": new_summary.id, "filename": filename, "upload_time": upload_time, "summary": result}]}

@app.get("/summaries/")
async def get_summaries(
    db: AsyncSession = Depends(get_db), 
    search: str = Query(None, description="Search summaries by heading or content")
):
    """
    Retrieves all stored summaries from the database, with optional search functionality.
    """
    query = select(Summary)
    
    if search:
        query = query.where(
            (Summary.filename.ilike(f"%{search}%")) | (Summary.summary.ilike(f"%{search}%"))
        )

    result = await db.execute(query)
    summaries = result.scalars().all()

    return [{"id": s.id, "filename": s.filename, "upload_time": s.upload_time, "summary": s.summary} for s in summaries]



@app.delete("/summaries/{summary_id}")
async def delete_summary(summary_id: int, db: AsyncSession = Depends(get_db)):
    """
    Deletes a summary entry from the database by its ID.
    """
    query = select(Summary).where(Summary.id == summary_id)
    result = await db.execute(query)
    summary = result.scalars().first()

    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")

    await db.delete(summary)
    await db.commit()
    return {"message": "Summary deleted"}

@app.get("/document-exists/{filename}")
async def check_document_exists(filename: str, db: AsyncSession = Depends(get_db)):
    """
    Checks if a document with the given filename already exists in the database.
    """
    query = select(Summary).where(Summary.filename == filename)
    result = await db.execute(query)
    existing_summary = result.scalars().first()
    
    return {"exists": existing_summary is not None, "id": existing_summary.id if existing_summary else None}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

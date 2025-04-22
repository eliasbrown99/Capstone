from fastapi import FastAPI, UploadFile, Depends, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import json
from dotenv import load_dotenv
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import SessionLocal, Summary, init_db
from app.services import SolicitationService

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set.")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

solicitation_service = SolicitationService(api_key)


@app.on_event("startup")
async def startup_event():
    """
    Ensure the 'summaries' table is created before handling requests.
    """
    await init_db()


async def get_db():
    async with SessionLocal() as session:
        yield session


@app.post("/summarize/")
async def summarize_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    filename = file.filename
    upload_time = datetime.now(timezone.utc)

    # 1) Summarize -> returns Python list of {heading, summary} objects
    result_list = await solicitation_service.summarize_document(file)

    if not result_list:
        raise HTTPException(
            status_code=400, detail="No summary generated from document."
        )

    # 2) Convert the Python list -> JSON string
    result_json = json.dumps(result_list)

    # 3) Create & insert a new Summary row
    new_summary = Summary(
        filename=filename,
        upload_time=upload_time,
        summary=result_json
    )
    db.add(new_summary)
    await db.commit()
    await db.refresh(new_summary)

    return {
        "summaries": [
            {
                "id": new_summary.id,
                "filename": filename,
                "upload_time": upload_time,
                "summary": result_list  # Return the original list
            }
        ]
    }


@app.get("/summaries/")
async def get_summaries(
    db: AsyncSession = Depends(get_db),
    search: str = Query(None, description="Search by heading or content")
):
    query = select(Summary)
    if search:
        query = query.where(
            (Summary.filename.ilike(f"%{search}%")) |
            (Summary.summary.ilike(f"%{search}%"))
        )

    result = await db.execute(query)
    summaries = result.scalars().all()

    # Convert each summary (JSON string) back to a Python list/dict
    output = []
    for s in summaries:
        try:
            summary_list = json.loads(s.summary)
        except json.JSONDecodeError:
            summary_list = None
        output.append({
            "id": s.id,
            "filename": s.filename,
            "upload_time": s.upload_time,
            "summary": summary_list,
        })

    return output


@app.delete("/summaries/{summary_id}")
async def delete_summary(summary_id: int, db: AsyncSession = Depends(get_db)):
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
    query = select(Summary).where(Summary.filename == filename)
    result = await db.execute(query)
    existing_summary = result.scalars().first()

    return {
        "exists": existing_summary is not None,
        "id": existing_summary.id if existing_summary else None
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

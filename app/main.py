# app/main.py
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from starlette.datastructures import UploadFile as StarletteUploadFile
from io import BytesIO
import json
import os
import uvicorn
from dotenv import load_dotenv

from app.database import SessionLocal, Summary, init_db
from app.parser import parse_document
from app.summarization import detect_headings_and_summarize_llm

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY env var not set.")


# ─────────────────────────── helpers ───────────────────────────
def _sse(data: str) -> str:
    """Format a Server-Sent-Events line."""
    return f"data: {data}\n\n"


def iso_utc(dt: datetime) -> str:
    """
    Return an ISO-8601 string in **UTC** with a trailing Z,
    regardless of whether the input is naive or offset-aware.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


async def get_db():
    async with SessionLocal() as session:
        yield session


# ─────────────────────────── FastAPI lifespan ───────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()          # create tables once on startup
    yield                     # app runs
    # no shutdown tasks needed

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────── /summarize-stream/ ───────────────────────────
@app.post("/summarize-stream/")
async def summarize_stream(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Streams progress tokens + final summary payload.
    Ensures the DB connection is always returned to the pool to
    avoid SAWarnings about unchecked-in connections.
    """
    file_bytes: bytes = await file.read()
    filename: str = file.filename

    async def event_generator():
        try:
            # 1⃣  parsing
            yield _sse("PARSING")
            pseudo_upload = StarletteUploadFile(
                filename=filename, file=BytesIO(file_bytes))
            parsed_text = await parse_document(pseudo_upload)

            # 2⃣  classification + summarisation
            yield _sse("IDENTIFYING_RELEVANT_SECTIONS")
            yield _sse("SUMMARIZING_SECTIONS")
            result_list = await detect_headings_and_summarize_llm(
                parsed_text, openai_api_key=OPENAI_API_KEY, debug=False
            )
            if not result_list:
                raise HTTPException(400, "No summary generated")

            # 3⃣  DB storage
            yield _sse("STORING_IN_DATABASE")
            new_row = Summary(
                filename=filename,
                upload_time=datetime.now(timezone.utc),
                summary=json.dumps(result_list),
            )
            db.add(new_row)
            await db.commit()
            await db.refresh(new_row)

            # 4⃣  final payload
            payload = {
                "id": new_row.id,
                "filename": new_row.filename,
                "upload_time": iso_utc(new_row.upload_time),
                "summary": result_list,
            }
            yield _sse(json.dumps(payload))
            yield _sse("COMPLETE")
        finally:
            # make sure pooled connection is returned
            await db.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─────────────────────────── CRUD routes ───────────────────────────
@app.get("/summaries/")
async def get_summaries(db: AsyncSession = Depends(get_db), search: str | None = None):
    query = select(Summary)
    if search:
        query = query.where(
            (Summary.filename.ilike(f"%{search}%")) |
            (Summary.summary.ilike(f"%{search}%"))
        )
    res = await db.execute(query)
    rows = res.scalars().all()

    output = []
    for r in rows:
        try:
            summary_list = json.loads(r.summary)
        except json.JSONDecodeError:
            summary_list = r.summary
        output.append({
            "id": r.id,
            "filename": r.filename,
            "upload_time": iso_utc(r.upload_time),
            "summary": summary_list,
        })
    return output


@app.delete("/summaries/{summary_id}")
async def delete_summary(summary_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Summary).where(Summary.id == summary_id))
    row = res.scalars().first()
    if not row:
        raise HTTPException(404, "Summary not found")
    await db.delete(row)
    await db.commit()
    return {"message": "Summary deleted"}


@app.get("/document-exists/{filename}")
async def check_document_exists(filename: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Summary).where(Summary.filename == filename))
    row = res.scalars().first()
    return {"exists": row is not None, "id": row.id if row else None}


# ─────────────────────────── run (dev) ───────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

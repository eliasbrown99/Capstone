from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime
import sqlite3
from datetime import datetime

# Main database for the backend
DATABASE_URL = "sqlite+aiosqlite:///./summaries.db"
engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    upload_time = Column(DateTime)
    summary = Column(Text, nullable=False)

# === Dummy Test Database === #
#This is making a new summary line for the dummy summaries every time its ran (need to fix)

def setup_dummy_db():
    conn = sqlite3.connect("summaries.db")
    cursor = conn.cursor()

    # Create a dummy table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename STRING,
        upload_time DATETIME,
        summary TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()

    print("Dummy entry added to summaries.db successfully!")

# Run dummy setup
setup_dummy_db()

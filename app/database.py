# app/database.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime

# Point to the same SQLite file, but handle table creation via the async engine
DATABASE_URL = "sqlite+aiosqlite:///./summaries.db"
engine = create_async_engine(DATABASE_URL, echo=True)

SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    upload_time = Column(DateTime)
    # We'll store the entire JSON summary as a TEXT field
    summary = Column(Text, nullable=False)


async def init_db():
    """
    Create all tables if they don't exist, using the same async engine.
    """
    async with engine.begin() as conn:
        # This will issue CREATE TABLE statements for all tables defined in Base
        await conn.run_sync(Base.metadata.create_all)

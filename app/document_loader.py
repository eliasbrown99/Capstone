# app/document_loader.py
import os
import tempfile
from pathlib import Path

from fastapi import HTTPException
from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document


class DocumentLoader:
    def __init__(self, text_splitter=None):
        """
        Initialize with a default text splitter if none is provided.
        """
        if text_splitter is None:
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1500,
                chunk_overlap=0
            )
        else:
            self.text_splitter = text_splitter

    async def load_document(self, file) -> list:
        """
        Load and process a PDF, Word, plain-text, or Markdown document, returning a list of text chunks.
        """
        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            temp_path = tmp.name

        try:
            if file.filename.lower().endswith('.pdf'):
                loader = PyPDFLoader(temp_path)
                docs = loader.load()

            elif file.filename.lower().endswith(('.doc', '.docx')):
                loader = UnstructuredWordDocumentLoader(temp_path)
                docs = loader.load()

            elif file.filename.lower().endswith(('.txt', '.md')):
                # Decode the raw bytes into a string
                text = content.decode("utf-8", errors="ignore")
                # Wrap as a single Document
                doc = Document(page_content=text)
                docs = [doc]

            else:
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported file type"
                )

            # Split into smaller text chunks (optional).
            # For PDFs/DOCs, you might still want to chunk them here.
            # For .md, you may choose to skip chunking so the headings remain intact.
            # But for simplicity, we'll do it the same for all.
            splits = self.text_splitter.split_documents(docs)
            text_chunks = [d.page_content for d in splits]

            return text_chunks

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error loading document: {str(e)}"
            )
        finally:
            os.remove(temp_path)

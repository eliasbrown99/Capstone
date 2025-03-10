import os
import tempfile
from pathlib import Path

from fastapi import HTTPException
from langchain.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter


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
        Load and process a PDF or Word document, returning a list of text chunks.
        Uses PyPDFLoader for PDFs and UnstructuredWordDocumentLoader for Word docs.
        """
        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            temp_path = tmp.name

        try:
            # Decide the loader based on file extension
            if file.filename.lower().endswith('.pdf'):
                loader = PyPDFLoader(temp_path)
            elif file.filename.lower().endswith(('.doc', '.docx')):
                loader = UnstructuredWordDocumentLoader(temp_path)
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported file type"
                )

            # Load documents via the chosen loader
            docs = loader.load()

            # Split into smaller text chunks
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

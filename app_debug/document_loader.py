import os
import logging
from pathlib import Path
from fastapi import HTTPException, UploadFile
from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import tempfile

logger = logging.getLogger(__name__)

class DocumentLoader:
    def __init__(self, text_splitter=None):
        if text_splitter is None:
            self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        else:
            self.text_splitter = text_splitter

    async def load_document(self, file: UploadFile) -> list:
        """
        Load and process a document file, returning a list of text chunks.
        Supports PDF and Word documents.
        """
        logger.debug(f"[DocumentLoader] load_document called with file: {file.filename}")
        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            temp_path = tmp.name
        logger.debug(f"[DocumentLoader] Temp file created at {temp_path}")

        try:
            if file.filename.endswith('.pdf'):
                logger.debug(f"[DocumentLoader] Detected PDF => using PyPDFLoader.")
                loader = PyPDFLoader(str(temp_path))
            elif file.filename.endswith(('.doc', '.docx')):
                logger.debug(f"[DocumentLoader] Detected Word doc => using UnstructuredWordDocumentLoader.")
                loader = UnstructuredWordDocumentLoader(str(temp_path))
            else:
                logger.error(f"[DocumentLoader] Unsupported file type: {file.filename}")
                raise HTTPException(status_code=400, detail="Unsupported file type")

            docs = loader.load()
            logger.debug(f"[DocumentLoader] Loaded {len(docs)} documents from file.")
            splits = self.text_splitter.split_documents(docs)
            text_chunks = [d.page_content for d in splits]
            logger.debug(f"[DocumentLoader] Split into {len(text_chunks)} text chunks.")

            return text_chunks
        except Exception as e:
            logger.error(f"[DocumentLoader] Error loading document: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error loading document: {str(e)}"
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logger.debug(f"[DocumentLoader] Temp file {temp_path} removed.")

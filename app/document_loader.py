import os
from pathlib import Path
from fastapi import HTTPException
from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import tempfile

class DocumentLoader:
    def __init__(self, text_splitter=None):
        if text_splitter is None:
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1500,
                chunk_overlap=200
            )
        else:
            self.text_splitter = text_splitter

    async def load_document(self, file) -> list:
        """
        Load and process a document file, returning a list of text chunks.
        Supports PDF and Word documents.
        """
        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            temp_path = tmp.name

        try:
            if file.filename.endswith('.pdf'):
                loader = PyPDFLoader(str(temp_path))
            elif file.filename.endswith(('.doc', '.docx')):
                loader = UnstructuredWordDocumentLoader(str(temp_path))
            else:
                raise HTTPException(status_code=400, detail="Unsupported file type")

            docs = loader.load()
            # Split docs into textual chunks
            splits = self.text_splitter.split_documents(docs)
            text_chunks = [d.page_content for d in splits]
            return text_chunks

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error loading document: {str(e)}")
        finally:
            os.remove(temp_path)

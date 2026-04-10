import os
import uuid
import shutil
from typing import Dict, List, Optional
from backend.models.schemas import DocumentInfo


class DocumentService:
    def __init__(self, upload_dir: str, pipeline=None):
        self.upload_dir = upload_dir
        self.pipeline = pipeline
        self._documents: Dict[str, DocumentInfo] = {}
        self._paths: Dict[str, str] = {}
        os.makedirs(upload_dir, exist_ok=True)

    async def upload(self, filename: str, content: bytes) -> DocumentInfo:
        doc_id = str(uuid.uuid4())[:8]
        doc_dir = os.path.join(self.upload_dir, doc_id)
        os.makedirs(doc_dir, exist_ok=True)
        pdf_path = os.path.join(doc_dir, filename)
        with open(pdf_path, "wb") as f:
            f.write(content)
        info = DocumentInfo(id=doc_id, filename=filename, total_pages=0, status="pending")
        self._documents[doc_id] = info
        self._paths[doc_id] = pdf_path
        return info

    async def index_document(self, doc_id: str) -> DocumentInfo:
        info = self._documents.get(doc_id)
        if not info:
            raise ValueError(f"Document {doc_id} not found")
        info.status = "indexing"
        pdf_path = self._paths[doc_id]
        try:
            pages = await self.pipeline.index_document(pdf_path, doc_id)
            info.total_pages = len(pages)
            info.indexed_pages = len(pages)
            info.status = "completed"
        except Exception:
            info.status = "failed"
            raise
        return info

    def get_document(self, doc_id: str) -> Optional[DocumentInfo]:
        return self._documents.get(doc_id)

    def list_documents(self) -> List[DocumentInfo]:
        return list(self._documents.values())

    async def delete_document(self, doc_id: str) -> None:
        if doc_id in self._documents:
            if self.pipeline:
                await self.pipeline.retriever.delete(doc_id)
            doc_dir = os.path.join(self.upload_dir, doc_id)
            if os.path.exists(doc_dir):
                shutil.rmtree(doc_dir)
            del self._documents[doc_id]
            self._paths.pop(doc_id, None)

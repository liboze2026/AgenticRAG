import os
import uuid
import shutil
import sqlite3
import logging
from typing import List, Optional

from backend.models.schemas import DocumentInfo

logger = logging.getLogger(__name__)


class DocumentService:
    """Manages document lifecycle with SQLite persistence."""

    def __init__(self, upload_dir: str, pipeline=None, db_path: Optional[str] = None):
        self.upload_dir = upload_dir
        self.pipeline = pipeline
        self.db_path = db_path or os.path.join(upload_dir, "documents.db")
        os.makedirs(upload_dir, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    pdf_path TEXT NOT NULL,
                    total_pages INTEGER NOT NULL DEFAULT 0,
                    indexed_pages INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending'
                )
            """)
            conn.commit()

    def _row_to_info(self, row) -> DocumentInfo:
        return DocumentInfo(
            id=row["id"],
            filename=row["filename"],
            total_pages=row["total_pages"],
            indexed_pages=row["indexed_pages"],
            status=row["status"],
        )

    def _get_pdf_path(self, doc_id: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT pdf_path FROM documents WHERE id = ?", (doc_id,)).fetchone()
            return row["pdf_path"] if row else None

    async def upload(self, filename: str, content: bytes) -> DocumentInfo:
        doc_id = str(uuid.uuid4())[:8]
        doc_dir = os.path.join(self.upload_dir, doc_id)
        os.makedirs(doc_dir, exist_ok=True)
        pdf_path = os.path.join(doc_dir, filename)
        with open(pdf_path, "wb") as f:
            f.write(content)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO documents (id, filename, pdf_path, total_pages, indexed_pages, status) "
                "VALUES (?, ?, ?, 0, 0, 'pending')",
                (doc_id, filename, pdf_path),
            )
            conn.commit()
        return DocumentInfo(id=doc_id, filename=filename, total_pages=0, indexed_pages=0, status="pending")

    async def index_document(self, doc_id: str) -> DocumentInfo:
        pdf_path = self._get_pdf_path(doc_id)
        if not pdf_path:
            raise ValueError(f"Document {doc_id} not found")

        with self._connect() as conn:
            conn.execute("UPDATE documents SET status = 'indexing' WHERE id = ?", (doc_id,))
            conn.commit()

        try:
            pages = await self.pipeline.index_document(pdf_path, doc_id)
            with self._connect() as conn:
                conn.execute(
                    "UPDATE documents SET status = 'completed', total_pages = ?, indexed_pages = ? WHERE id = ?",
                    (len(pages), len(pages), doc_id),
                )
                conn.commit()
        except Exception:
            logger.exception("Failed to index document %s", doc_id)
            with self._connect() as conn:
                conn.execute("UPDATE documents SET status = 'failed' WHERE id = ?", (doc_id,))
                conn.commit()
            raise

        return self.get_document(doc_id)

    def get_document(self, doc_id: str) -> Optional[DocumentInfo]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
            return self._row_to_info(row) if row else None

    def list_documents(self) -> List[DocumentInfo]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM documents ORDER BY id").fetchall()
            return [self._row_to_info(r) for r in rows]

    async def delete_document(self, doc_id: str) -> None:
        if not self.get_document(doc_id):
            return
        if self.pipeline:
            try:
                await self.pipeline.retriever.delete(doc_id)
            except Exception:
                logger.exception("Failed to delete vectors for %s", doc_id)
        doc_dir = os.path.join(self.upload_dir, doc_id)
        if os.path.exists(doc_dir):
            shutil.rmtree(doc_dir)
        with self._connect() as conn:
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            conn.commit()

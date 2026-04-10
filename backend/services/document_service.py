import os
import uuid
import shutil
import sqlite3
import logging
from typing import Dict, List, Optional

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
                    status TEXT NOT NULL DEFAULT 'pending',
                    dataset_id INTEGER
                )
            """)
            # Migration: add column if missing
            cols = [r[1] for r in conn.execute("PRAGMA table_info(documents)").fetchall()]
            if "dataset_id" not in cols:
                conn.execute("ALTER TABLE documents ADD COLUMN dataset_id INTEGER")
            conn.commit()

    def _row_to_info(self, row) -> DocumentInfo:
        return DocumentInfo(
            id=row["id"],
            filename=row["filename"],
            total_pages=row["total_pages"],
            indexed_pages=row["indexed_pages"],
            status=row["status"],
            dataset_id=row["dataset_id"] if "dataset_id" in row.keys() else None,
        )

    def _get_pdf_path(self, doc_id: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT pdf_path FROM documents WHERE id = ?", (doc_id,)).fetchone()
            return row["pdf_path"] if row else None

    async def upload(self, filename: str, content: bytes, dataset_id: Optional[int] = None) -> DocumentInfo:
        doc_id = str(uuid.uuid4())[:8]
        doc_dir = os.path.join(self.upload_dir, doc_id)
        os.makedirs(doc_dir, exist_ok=True)
        pdf_path = os.path.join(doc_dir, filename)
        with open(pdf_path, "wb") as f:
            f.write(content)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO documents (id, filename, pdf_path, total_pages, indexed_pages, status, dataset_id) "
                "VALUES (?, ?, ?, 0, 0, 'pending', ?)",
                (doc_id, filename, pdf_path, dataset_id),
            )
            conn.commit()
        return DocumentInfo(id=doc_id, filename=filename, total_pages=0, indexed_pages=0, status="pending", dataset_id=dataset_id)

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

    def list_documents(self, dataset_id: Optional[int] = None) -> List[DocumentInfo]:
        with self._connect() as conn:
            if dataset_id is not None:
                rows = conn.execute("SELECT * FROM documents WHERE dataset_id = ? ORDER BY id", (dataset_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM documents ORDER BY id").fetchall()
            return [self._row_to_info(r) for r in rows]

    def recover_orphaned(self) -> List[str]:
        """Find documents stuck in 'indexing' state (orphaned by crash) and mark them failed.
        Returns the list of recovered document IDs.
        """
        with self._connect() as conn:
            rows = conn.execute("SELECT id FROM documents WHERE status = 'indexing'").fetchall()
            ids = [r["id"] for r in rows]
            if ids:
                conn.execute(
                    "UPDATE documents SET status = 'failed' WHERE status = 'indexing'"
                )
                conn.commit()
                logger.warning("Recovered %d orphaned indexing documents: %s", len(ids), ids)
        return ids

    def count_by_dataset(self) -> Dict[int, int]:
        """Return {dataset_id: count} for documents grouped by dataset."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT dataset_id, COUNT(*) as cnt FROM documents WHERE dataset_id IS NOT NULL GROUP BY dataset_id"
            ).fetchall()
            return {r["dataset_id"]: r["cnt"] for r in rows}

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

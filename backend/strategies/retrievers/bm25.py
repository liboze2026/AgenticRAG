import os
import pickle
from typing import List, Optional, Dict

from backend.interfaces.retriever import BaseRetriever
from backend.models.schemas import RetrievalResult
from backend.strategies import retriever_registry

try:
    from rank_bm25 import BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:
    BM25Okapi = None
    _BM25_AVAILABLE = False

try:
    import pdfplumber
    _PDFPLUMBER_AVAILABLE = True
except ImportError:
    pdfplumber = None
    _PDFPLUMBER_AVAILABLE = False


def _extract_page_text(pdf_path: str, page_number: int) -> str:
    """Extract text from a specific page (1-indexed). Returns empty string on failure."""
    if not _PDFPLUMBER_AVAILABLE or not os.path.exists(pdf_path):
        return ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_number - 1 < len(pdf.pages):
                return pdf.pages[page_number - 1].extract_text() or ""
    except Exception:
        return ""
    return ""


def _tokenize(text: str) -> List[str]:
    """Simple whitespace + punctuation tokenizer."""
    import re
    return re.findall(r"\w+", text.lower())


@retriever_registry.register("bm25")
class BM25Retriever(BaseRetriever):
    """Sparse text-based retrieval over page-extracted text using BM25."""

    def __init__(self, persist_path: Optional[str] = None):
        self.persist_path = persist_path
        # Each entry: {"doc_id": str, "page_number": int, "image_path": str, "tokens": List[str]}
        self._docs: List[dict] = []
        self._bm25 = None
        if persist_path and os.path.exists(persist_path):
            self._load()

    def _save(self):
        if not self.persist_path:
            return
        os.makedirs(os.path.dirname(self.persist_path) or ".", exist_ok=True)
        with open(self.persist_path, "wb") as f:
            pickle.dump(self._docs, f)

    def _load(self):
        try:
            with open(self.persist_path, "rb") as f:
                self._docs = pickle.load(f)
            self._rebuild_index()
        except Exception:
            self._docs = []

    def _rebuild_index(self):
        if not _BM25_AVAILABLE or not self._docs:
            self._bm25 = None
            return
        self._bm25 = BM25Okapi([d["tokens"] for d in self._docs])

    async def index(self, document_id: str, page_number: int, vectors, image_path: str, pdf_path: Optional[str] = None) -> None:
        # vectors are ignored for BM25; we extract text from the PDF
        text = ""
        if pdf_path:
            text = _extract_page_text(pdf_path, page_number)
        tokens = _tokenize(text)
        self._docs.append({
            "doc_id": document_id,
            "page_number": page_number,
            "image_path": image_path,
            "tokens": tokens,
        })
        self._rebuild_index()
        self._save()

    async def retrieve(self, query_vectors, top_k: int = 5) -> List[RetrievalResult]:
        # If query_vectors is actually a flat token list (passed by hybrid wrapper)
        tokens = query_vectors if isinstance(query_vectors, list) and query_vectors and isinstance(query_vectors[0], str) else []
        if not tokens:
            return []
        return self._retrieve_with_tokens(tokens, top_k)

    async def retrieve_text(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """Convenience method for direct text retrieval, used by hybrid wrapper."""
        if not self._bm25 or not self._docs:
            return []
        return self._retrieve_with_tokens(_tokenize(query), top_k)

    def _retrieve_with_tokens(self, tokens: List[str], top_k: int) -> List[RetrievalResult]:
        if not tokens or not self._bm25:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for idx, score in ranked:
            d = self._docs[idx]
            results.append(RetrievalResult(
                document_id=d["doc_id"],
                page_number=d["page_number"],
                score=float(score),
                image_path=d["image_path"],
            ))
        return results

    async def delete(self, document_id: str) -> None:
        self._docs = [d for d in self._docs if d["doc_id"] != document_id]
        self._rebuild_index()
        self._save()

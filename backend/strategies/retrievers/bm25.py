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


_CN_RANGE = "一-鿿㐀-䶿"   # CJK Unified + Extension A
_TOK_RE = None
_CN_RE = None


def _tokenize(text: str) -> List[str]:
    """Bilingual tokenizer.

    For ASCII / Latin: split on punctuation/whitespace, lowercase, keep
    words ≥ 2 chars (BM25 doesn't benefit from single chars).
    For CJK runs: emit unigrams + bigrams (so a query like
    "文档结构化解析" tokenizes to {文档, 档结, 结构, ...} which can
    actually match indexed pages).
    """
    import re
    global _TOK_RE, _CN_RE
    if _TOK_RE is None:
        _TOK_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]+")
        _CN_RE  = re.compile(f"[{_CN_RANGE}]+")
    text = (text or "").lower()
    out: List[str] = []
    out.extend(_TOK_RE.findall(text))
    for run in _CN_RE.findall(text):
        # unigrams (skip single-char-only matches but include them when run is short)
        for ch in run:
            out.append(ch)
        # bigrams
        for i in range(len(run) - 1):
            out.append(run[i:i + 2])
    return out


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
        # BM25Okapi raises ZeroDivisionError when every document has empty tokens
        if not any(d["tokens"] for d in self._docs):
            self._bm25 = None
            return
        self._bm25 = BM25Okapi([d["tokens"] for d in self._docs])

    async def index(
        self,
        document_id: str,
        page_number: int,
        vectors,
        image_path: str,
        pdf_path: Optional[str] = None,
        layout_metadata=None,
    ) -> None:
        # vectors are ignored for BM25; we extract text from the PDF
        text = ""
        if pdf_path:
            text = _extract_page_text(pdf_path, page_number)
        tokens = _tokenize(text)
        entry = {
            "doc_id": document_id,
            "page_number": page_number,
            "image_path": image_path,
            "tokens": tokens,
        }
        if layout_metadata is not None:
            entry["layout"] = layout_metadata
        self._docs.append(entry)
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
        from backend.models.schemas import PageLayout
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for idx, score in ranked:
            d = self._docs[idx]
            layout = None
            if "layout" in d and d["layout"] is not None:
                try:
                    raw = d["layout"]
                    layout = raw if isinstance(raw, PageLayout) else PageLayout(**raw)
                except Exception:
                    pass
            results.append(RetrievalResult(
                document_id=d["doc_id"],
                page_number=d["page_number"],
                score=float(score),
                image_path=d["image_path"],
                layout=layout,
            ))
        return results

    async def delete(self, document_id: str) -> None:
        self._docs = [d for d in self._docs if d["doc_id"] != document_id]
        self._rebuild_index()
        self._save()

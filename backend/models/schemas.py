from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class PageImage(BaseModel):
    document_id: str
    page_number: int
    image_path: str
    pdf_path: Optional[str] = None  # needed by text-based retrievers in Batch 2


class Embedding(BaseModel):
    document_id: str
    page_number: int
    vectors: List[List[float]]


class RetrievalResult(BaseModel):
    document_id: str
    page_number: int
    score: float
    image_path: str


class RetrievalBundle(BaseModel):
    """Wraps retrieval results with timing metadata."""
    results: List[RetrievalResult]
    timing: Dict[str, float] = {}


class Answer(BaseModel):
    text: str
    sources: List[RetrievalResult]
    timing: Dict[str, float] = {}  # per-stage latency


class DocumentInfo(BaseModel):
    id: str
    filename: str
    total_pages: int
    status: str
    indexed_pages: int = 0
    dataset_id: Optional[int] = None


class DatasetInfo(BaseModel):
    id: int
    name: str
    description: str = ""
    created_at: str
    document_count: int = 0


class EvalMetrics(BaseModel):
    recall_at_k: Dict[int, float] = {}
    mrr: float = 0.0
    total_queries: int = 0


class PerQueryResult(BaseModel):
    query: str
    relevant: List[str]
    retrieved: List[str]
    rr: float
    recall_at_k: Dict[int, float]
    timing_ms: Dict[str, float] = {}

from typing import List, Optional, Dict, Any
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Layout Analysis Models
# ---------------------------------------------------------------------------

class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class LayoutElement(BaseModel):
    element_type: str          # "text_block" | "table" | "figure" | "heading"
    bbox: BoundingBox
    text: Optional[str] = None
    image_path: Optional[str] = None   # for figures: path to cropped image
    confidence: float = 1.0


class PageLayout(BaseModel):
    document_id: str
    page_number: int
    page_width: float
    page_height: float
    elements: List[LayoutElement] = []


# ---------------------------------------------------------------------------
# Core Pipeline Models
# ---------------------------------------------------------------------------

class PageImage(BaseModel):
    document_id: str
    page_number: int
    image_path: str
    pdf_path: Optional[str] = None
    layout_metadata: Optional[PageLayout] = None


class Embedding(BaseModel):
    document_id: str
    page_number: int
    vectors: List[List[float]]


class RetrievalResult(BaseModel):
    document_id: str
    page_number: int
    score: float
    image_path: str
    layout: Optional[PageLayout] = None


class RetrievalBundle(BaseModel):
    """Wraps retrieval results with timing metadata."""
    results: List[RetrievalResult]
    timing: Dict[str, float] = {}


class Answer(BaseModel):
    text: str
    sources: List[RetrievalResult]
    timing: Dict[str, float] = {}


# ---------------------------------------------------------------------------
# Chat / Session Models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str                              # "user" | "assistant"
    content: str
    sources: List[RetrievalResult] = []   # assistant messages carry retrieval sources
    timestamp: str = ""


class ChatSession(BaseModel):
    session_id: str
    document_ids: List[str] = []
    messages: List[ChatMessage] = []
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Document / Dataset / Evaluation Models
# ---------------------------------------------------------------------------

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

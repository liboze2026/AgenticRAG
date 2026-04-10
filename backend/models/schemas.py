from typing import List, Optional, Dict
from pydantic import BaseModel


class PageImage(BaseModel):
    document_id: str
    page_number: int
    image_path: str


class Embedding(BaseModel):
    document_id: str
    page_number: int
    vectors: List[List[float]]


class RetrievalResult(BaseModel):
    document_id: str
    page_number: int
    score: float
    image_path: str


class Answer(BaseModel):
    text: str
    sources: List[RetrievalResult]


class DocumentInfo(BaseModel):
    id: str
    filename: str
    total_pages: int
    status: str
    indexed_pages: int = 0


class EvalMetrics(BaseModel):
    recall_at_k: Dict[int, float] = {}
    mrr: float = 0.0
    total_queries: int = 0

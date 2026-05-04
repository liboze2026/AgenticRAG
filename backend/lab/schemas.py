"""Pydantic schemas for lab features.

Kept separate from backend.models.schemas to make it obvious which fields
belong to lab features vs. the main pipeline.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

from backend.models.schemas import BoundingBox, RetrievalResult


# ---------------------------------------------------------------------------
# Phase 1: Hybrid (dual-channel) — side-by-side compare
# ---------------------------------------------------------------------------

class ChannelResult(BaseModel):
    """Result list from one retrieval channel (bm25 / colpali / fused)."""
    channel: str                              # "bm25" | "colpali" | "rrf"
    results: List[RetrievalResult]
    timing_ms: float = 0.0
    note: str = ""                            # e.g. "BM25 索引为空 — 已降级"


class HybridCompareResponse(BaseModel):
    query: str
    channels: List[ChannelResult]
    answer: Optional[str] = None              # generated from fused channel
    fused_channel: str = "rrf"


# ---------------------------------------------------------------------------
# Phase 2: VISA — evidence attribution (bbox)
# ---------------------------------------------------------------------------

class EvidenceRegion(BaseModel):
    """One attributed region: 'answer claim X is supported by this bbox'."""
    document_id: str
    page_number: int
    bbox: BoundingBox
    label: str = ""                           # e.g. "table" / "图表" / "正文"
    score: float = 1.0
    quote: str = ""                           # supporting text snippet (may be empty for figures)
    citation: int = 0                         # 1-indexed marker matching answer text "[1]"


class VisaResponse(BaseModel):
    query: str
    answer: str
    sources: List[RetrievalResult]
    evidence_regions: List[EvidenceRegion]
    timing_ms: Dict[str, float] = {}
    note: str = ""                            # set when degrading (no layout, etc.)


# ---------------------------------------------------------------------------
# Phase 3: GMM dynamic top-k
# ---------------------------------------------------------------------------

class ScoreBucket(BaseModel):
    bin_start: float
    bin_end: float
    count: int


class GmmComponent(BaseModel):
    mean: float
    variance: float
    weight: float


class GmmResponse(BaseModel):
    query: str
    fixed_top_k: int                          # the input top_k baseline
    dynamic_top_k: int                        # GMM-chosen depth
    cutoff_score: float                       # boundary between high/low cluster
    histogram: List[ScoreBucket]
    components: List[GmmComponent]            # 2 entries: low / high cluster
    results: List[RetrievalResult]            # truncated to dynamic_top_k
    note: str = ""
    timing_ms: Dict[str, float] = {}


# ---------------------------------------------------------------------------
# Phase 4: Region-level retrieval
# ---------------------------------------------------------------------------

class RegionHit(BaseModel):
    document_id: str
    page_number: int
    element_index: int                        # index into PageLayout.elements
    element_type: str
    bbox: BoundingBox
    score: float
    image_path: str                           # parent page screenshot
    text: str = ""


class RegionResponse(BaseModel):
    query: str
    hits: List[RegionHit]
    timing_ms: Dict[str, float] = {}
    note: str = ""


# ---------------------------------------------------------------------------
# Phase 5: Lab health
# ---------------------------------------------------------------------------

class LabHealth(BaseModel):
    bm25_ready: bool
    bm25_doc_count: int
    layout_ready: bool                        # any indexed page has layout metadata?
    sklearn_available: bool
    region_collection_ready: bool
    region_point_count: int
    main_pipeline_ok: bool
    notes: List[str] = []

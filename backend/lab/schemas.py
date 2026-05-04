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


# ---------------------------------------------------------------------------
# Phase 6: Local relation graph (caption / heading / cross-page / text-to-figure)
# ---------------------------------------------------------------------------

class GraphNode(BaseModel):
    id: str                                   # f"{doc_id}:p{page}:e{idx}"
    document_id: str
    page_number: int
    element_index: int
    element_type: str
    bbox: BoundingBox
    text: str = ""


class GraphEdge(BaseModel):
    source: str
    target: str
    edge_type: str                            # caption_of | heading_to_text | cross_page_continuation | text_to_figure_ref
    score: float = 0.0
    note: str = ""


class GraphSeed(BaseModel):
    document_id: str
    page_number: int


class GraphResponse(BaseModel):
    query: str
    seeds: List[GraphSeed]
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    timing_ms: Dict[str, float] = {}
    note: str = ""


# ---------------------------------------------------------------------------
# Phase 7: Feedback-driven supplementary retrieval
# ---------------------------------------------------------------------------

class FeedbackRound(BaseModel):
    round_index: int
    trigger_reason: str                       # "initial" | "low_density" | "missing_caption" | "missing_heading" | "missing_table" | "neighbor_expand"
    query_used: str
    candidate_count: int = 0
    high_score_count: int = 0
    new_pages_added: int = 0
    note: str = ""


class FeedbackResponse(BaseModel):
    query: str
    rounds: List[FeedbackRound]
    final_results: List[RetrievalResult]
    answer: Optional[str] = None
    evidence_regions: List[EvidenceRegion] = []
    converged: bool = True
    max_rounds_hit: bool = False
    timing_ms: Dict[str, float] = {}
    note: str = ""


# ---------------------------------------------------------------------------
# Phase 8: Unified orchestration (combines all lab features in one pipeline)
# ---------------------------------------------------------------------------

class UnifiedStage(BaseModel):
    name: str                                 # "hybrid" | "gmm" | "feedback" | "visa" | "region" | "graph" | "generate"
    ok: bool = True
    note: str = ""
    timing_ms: float = 0.0
    summary: Dict[str, Any] = {}


class UnifiedResponse(BaseModel):
    query: str
    stages: List[UnifiedStage]
    final_results: List[RetrievalResult]
    answer: Optional[str] = None
    evidence_regions: List[EvidenceRegion] = []
    graph_nodes: List[GraphNode] = []
    graph_edges: List[GraphEdge] = []
    region_hits: List[RegionHit] = []
    timing_ms: Dict[str, float] = {}
    note: str = ""


# ---------------------------------------------------------------------------
# Phase 9: Benchmark suite
# ---------------------------------------------------------------------------

class BenchmarkQueryItem(BaseModel):
    query: str
    relevant_pages: List[GraphSeed] = []      # ground-truth (document_id, page_number)


class BenchmarkPerQuery(BaseModel):
    query: str
    channel: str
    retrieved: List[GraphSeed] = []           # in rank order
    relevant: List[GraphSeed] = []
    rr: float = 0.0                           # reciprocal rank of first hit
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    hit_at_1: float = 0.0
    note: str = ""


class BenchmarkChannelMetrics(BaseModel):
    channel: str
    queries: int
    mrr: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    hit_at_1: float = 0.0
    avg_latency_ms: float = 0.0


class BenchmarkResponse(BaseModel):
    metrics: List[BenchmarkChannelMetrics]
    per_query: List[BenchmarkPerQuery]
    total_queries: int = 0
    channels: List[str] = []
    timing_ms: Dict[str, float] = {}
    note: str = ""

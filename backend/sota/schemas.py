"""Pydantic schemas for SOTA package — request/response/persistence shapes."""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MethodStatus(str, Enum):
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    CIRCUIT_OPEN = "circuit_open"


class RunConfig(BaseModel):
    subsets: List[str] = Field(default_factory=lambda: ["fetatab", "mmlongbench", "papertab", "slidevqa"])
    methods: List[str] = Field(default_factory=lambda: ["baseline_colpali", "baseline_bm25", "baseline_rrf"])
    top_k: int = Field(10, ge=1, le=50)
    n_queries_per_subset: Optional[int] = Field(50, ge=1, le=10000)
    split: Literal["test", "train", "all"] = "test"
    notes: str = ""


class MetricCell(BaseModel):
    method: str
    subset: str
    metric: str
    value: float
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    n_queries: int


class MethodResult(BaseModel):
    method: str
    status: MethodStatus
    duration_ms: int
    error_kind: Optional[str] = None


class RunSummary(BaseModel):
    id: str
    created_at: int
    status: RunStatus
    config: RunConfig
    duration_ms: Optional[int] = None
    methods: List[MethodResult] = Field(default_factory=list)
    metrics: List[MetricCell] = Field(default_factory=list)
    notes: str = ""

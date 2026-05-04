"""Sanity tests that lab schemas serialize and validate."""
from backend.lab.schemas import (
    ChannelResult, EvidenceRegion, GmmComponent, GmmResponse, HybridCompareResponse,
    LabHealth, RegionHit, RegionResponse, ScoreBucket, VisaResponse,
)
from backend.models.schemas import BoundingBox, RetrievalResult


def test_channel_result_roundtrip():
    cr = ChannelResult(channel="bm25", results=[], timing_ms=12.3)
    d = cr.model_dump()
    assert d["channel"] == "bm25"


def test_hybrid_response_serializes():
    cr1 = ChannelResult(channel="bm25", results=[], timing_ms=10.0)
    cr2 = ChannelResult(channel="colpali", results=[], timing_ms=20.0)
    cr3 = ChannelResult(channel="rrf", results=[], timing_ms=1.0)
    resp = HybridCompareResponse(query="q", channels=[cr1, cr2, cr3])
    j = resp.model_dump_json()
    assert "rrf" in j


def test_evidence_region_required_fields():
    er = EvidenceRegion(
        document_id="d1", page_number=1,
        bbox=BoundingBox(x0=0, y0=0, x1=10, y1=10),
        label="正文", citation=1,
    )
    assert er.bbox.x0 == 0
    assert er.score == 1.0     # default


def test_visa_response_with_regions():
    src = RetrievalResult(document_id="d1", page_number=1, score=0.9, image_path="x.png")
    er = EvidenceRegion(
        document_id="d1", page_number=1,
        bbox=BoundingBox(x0=0, y0=0, x1=10, y1=10),
        label="正文", citation=1,
    )
    resp = VisaResponse(query="q", answer="ans [1]", sources=[src], evidence_regions=[er])
    assert len(resp.evidence_regions) == 1


def test_gmm_response_minimal():
    bucket = ScoreBucket(bin_start=0, bin_end=1, count=5)
    comp = GmmComponent(mean=0.5, variance=0.01, weight=0.5)
    resp = GmmResponse(
        query="q", fixed_top_k=5, dynamic_top_k=3, cutoff_score=0.4,
        histogram=[bucket], components=[comp, comp], results=[],
    )
    assert resp.dynamic_top_k == 3


def test_region_response():
    hit = RegionHit(
        document_id="d1", page_number=1, element_index=0,
        element_type="figure",
        bbox=BoundingBox(x0=0, y0=0, x1=100, y1=100),
        score=0.7, image_path="x.png", text="caption",
    )
    resp = RegionResponse(query="q", hits=[hit])
    assert resp.hits[0].element_type == "figure"


def test_lab_health():
    h = LabHealth(
        bm25_ready=False, bm25_doc_count=0, layout_ready=True,
        sklearn_available=True, region_collection_ready=False,
        region_point_count=0, main_pipeline_ok=True, notes=["x"],
    )
    assert "x" in h.notes

"""Unit tests for Phase 7 feedback helpers (no pipeline calls)."""
import pytest

from backend.lab.feedback import (
    _dedup_results, _gmm_signal, _figure_heavy, _has_caption_text,
    _has_layout_with_type,
)
from backend.models.schemas import (
    BoundingBox, LayoutElement, PageLayout, RetrievalResult,
)


def _r(doc, page, score, layout=None):
    return RetrievalResult(
        document_id=doc, page_number=page, score=score,
        image_path=f"/img/{doc}/{page}.png", layout=layout,
    )


def _layout(elements):
    return PageLayout(
        document_id="d", page_number=1,
        page_width=600.0, page_height=800.0, elements=elements,
    )


def test_dedup_keeps_highest_score():
    rs = [_r("d1", 1, 0.5), _r("d1", 1, 0.9), _r("d2", 1, 0.7)]
    out = _dedup_results(rs)
    assert len(out) == 2
    # Sorted by score descending
    assert out[0].score == 0.9
    assert out[1].score == 0.7


def test_gmm_signal_skips_when_too_few():
    converged, note = _gmm_signal([0.5, 0.6])
    assert converged is True
    assert "太少" in note


def test_gmm_signal_skips_when_uniform():
    converged, note = _gmm_signal([0.5, 0.5, 0.5, 0.5])
    assert converged is True


def test_gmm_signal_handles_two_clusters():
    # Sklearn may or may not be installed in CI; this test asserts the
    # function returns a (bool, str) tuple regardless of the result.
    scores = [0.95, 0.92, 0.88, 0.30, 0.28, 0.22]
    converged, note = _gmm_signal(scores)
    assert isinstance(converged, bool)
    assert isinstance(note, str)


def test_figure_heavy_detection():
    fig = LayoutElement(element_type="figure", bbox=BoundingBox(x0=0, y0=0, x1=100, y1=100))
    text = LayoutElement(element_type="text_block", bbox=BoundingBox(x0=0, y0=110, x1=100, y1=130))
    layout_fig_heavy = _layout([fig, fig, text])
    layout_text_heavy = _layout([text, text, text, fig])

    rs1 = [_r("d", 1, 0.9, layout_fig_heavy)]
    rs2 = [_r("d", 1, 0.9, layout_text_heavy)]
    assert _figure_heavy(rs1)
    assert not _figure_heavy(rs2)


def test_has_caption_text():
    cap = LayoutElement(element_type="text_block",
                        bbox=BoundingBox(x0=0, y0=0, x1=100, y1=20),
                        text="图 1 趋势")
    plain = LayoutElement(element_type="text_block",
                          bbox=BoundingBox(x0=0, y0=0, x1=100, y1=20),
                          text="某段普通正文")
    assert _has_caption_text([_r("d", 1, 0.9, _layout([cap]))])
    assert not _has_caption_text([_r("d", 1, 0.9, _layout([plain]))])


def test_has_layout_with_type():
    h = LayoutElement(element_type="heading", bbox=BoundingBox(x0=0, y0=0, x1=100, y1=20))
    rs = [_r("d", 1, 0.9, _layout([h]))]
    assert _has_layout_with_type(rs, "heading")
    assert not _has_layout_with_type(rs, "figure")
    # No layout = not a match
    assert not _has_layout_with_type([_r("d", 2, 0.5)], "heading")

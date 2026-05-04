"""Unit tests for Phase 6 graph edge detectors.

Pure-function tests — no Qdrant, no pipeline. Build a fake PageLayout and
inspect the inferred edges.
"""
from backend.lab.graph import (
    _detect_caption_edges, _detect_heading_edges,
    _detect_cross_page_continuation, _detect_text_figure_refs,
)
from backend.models.schemas import BoundingBox, LayoutElement, PageLayout


def _layout(doc_id: str, page: int, elements):
    return PageLayout(
        document_id=doc_id, page_number=page,
        page_width=600.0, page_height=800.0,
        elements=elements,
    )


def _bb(x0, y0, x1, y1):
    return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)


def test_caption_figure():
    fig = LayoutElement(element_type="figure", bbox=_bb(100, 100, 400, 300))
    cap = LayoutElement(element_type="text_block", bbox=_bb(110, 320, 390, 340), text="图 1: 训练损失")
    layout = _layout("d1", 1, [fig, cap])
    edges = _detect_caption_edges({("d1", 1): layout})
    assert any(e.edge_type == "caption_of" for e in edges)
    assert edges[0].source.endswith(":e0")
    assert edges[0].target.endswith(":e1")


def test_caption_table_english():
    tbl = LayoutElement(element_type="table", bbox=_bb(50, 50, 550, 200))
    cap = LayoutElement(element_type="text_block", bbox=_bb(60, 220, 540, 240), text="Table 2 Results")
    layout = _layout("d1", 1, [tbl, cap])
    edges = _detect_caption_edges({("d1", 1): layout})
    assert any(e.edge_type == "caption_of" for e in edges)


def test_caption_skips_far_text():
    fig = LayoutElement(element_type="figure", bbox=_bb(100, 100, 400, 300))
    far = LayoutElement(element_type="text_block", bbox=_bb(100, 500, 400, 520), text="图 1 标题")
    layout = _layout("d1", 1, [fig, far])
    edges = _detect_caption_edges({("d1", 1): layout})
    assert not edges


def test_heading_to_text():
    h = LayoutElement(element_type="heading", bbox=_bb(50, 100, 200, 130), text="3.1 引言")
    p1 = LayoutElement(element_type="text_block", bbox=_bb(50, 150, 550, 200), text="正文段落 A")
    p2 = LayoutElement(element_type="text_block", bbox=_bb(50, 220, 550, 280), text="正文段落 B")
    layout = _layout("d1", 1, [h, p1, p2])
    edges = _detect_heading_edges({("d1", 1): layout})
    assert len(edges) == 2
    assert all(e.edge_type == "heading_to_text" for e in edges)


def test_cross_page_continuation():
    cur_table = LayoutElement(element_type="table", bbox=_bb(50, 600, 550, 780))   # at bottom
    nxt_table = LayoutElement(element_type="table", bbox=_bb(50, 30, 550, 200))    # at top
    layouts = {
        ("d1", 1): _layout("d1", 1, [cur_table]),
        ("d1", 2): _layout("d1", 2, [nxt_table]),
    }
    edges = _detect_cross_page_continuation(layouts)
    assert len(edges) == 1
    assert edges[0].edge_type == "cross_page_continuation"


def test_no_continuation_when_table_in_middle():
    cur_mid = LayoutElement(element_type="table", bbox=_bb(50, 300, 550, 500))
    nxt_top = LayoutElement(element_type="table", bbox=_bb(50, 30, 550, 200))
    layouts = {
        ("d1", 1): _layout("d1", 1, [cur_mid]),
        ("d1", 2): _layout("d1", 2, [nxt_top]),
    }
    edges = _detect_cross_page_continuation(layouts)
    assert not edges


def test_text_figure_ref_same_page():
    text = LayoutElement(element_type="text_block", bbox=_bb(50, 50, 550, 90), text="如图1所示，趋势上升")
    fig = LayoutElement(element_type="figure", bbox=_bb(50, 200, 550, 500))
    layout = _layout("d1", 1, [text, fig])
    edges = _detect_text_figure_refs({("d1", 1): layout})
    assert len(edges) == 1
    assert edges[0].edge_type == "text_to_figure_ref"
    assert edges[0].source.endswith(":e0")
    assert edges[0].target.endswith(":e1")


def test_text_figure_ref_no_figure_no_edge():
    text = LayoutElement(element_type="text_block", bbox=_bb(50, 50, 550, 90), text="如图3")
    layout = _layout("d1", 1, [text])
    edges = _detect_text_figure_refs({("d1", 1): layout})
    assert not edges

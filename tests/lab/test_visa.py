"""Unit tests for Phase 2 — VISA evidence attribution."""
import pytest

from backend.lab.visa import (
    _split_answer_by_citations,
    _tokenize,
    _score_element,
    attribute_evidence,
)
from backend.models.schemas import (
    Answer, BoundingBox, LayoutElement, PageLayout, RetrievalResult,
)


def make_layout(doc_id: str, page: int, elements):
    return PageLayout(
        document_id=doc_id, page_number=page,
        page_width=1000, page_height=1400,
        elements=elements,
    )


def make_element(typ: str, text: str, x0=0, y0=0, x1=200, y1=100):
    return LayoutElement(
        element_type=typ,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
        text=text,
    )


def test_tokenize_chinese_bigrams():
    toks = _tokenize("注意力机制")
    assert "注意" in toks
    assert "意力" in toks


def test_tokenize_english_words():
    toks = _tokenize("The Attention Mechanism uses softmax")
    assert "attention" in toks
    assert "mechanism" in toks
    assert "softmax" in toks
    # Single-char words filtered; "the" (3 chars) is kept and that's fine —
    # Jaccard overlap is symmetric so common words don't bias rankings.
    assert "i" not in toks


def test_split_by_citations_single():
    pieces = _split_answer_by_citations("First sentence [1]. Second one [2].")
    citations = [c for c, _ in pieces if c is not None]
    assert citations == [1, 2]


def test_split_by_citations_chinese_punct():
    pieces = _split_answer_by_citations("第一句话引用[1]。第二句引用[2]。")
    citations = [c for c, _ in pieces if c is not None]
    assert citations == [1, 2]


def test_score_element_overlap_higher_wins():
    el_relevant = make_element("text_block", "transformer attention mechanism")
    el_unrelated = make_element("text_block", "stock market analysis report")
    window = "the transformer's attention mechanism is..."
    s_rel = _score_element(el_relevant, window)
    s_unr = _score_element(el_unrelated, window)
    assert s_rel > s_unr


def test_score_table_boost_when_table_mentioned():
    el_table = make_element("table", "data 12.3 45.6")
    el_text = make_element("text_block", "data 12.3 45.6")
    window = "如表 1 所示, 数据是 12.3"
    s_table = _score_element(el_table, window)
    s_text = _score_element(el_text, window)
    # Same text content but table boost kicks in
    assert s_table > s_text


def test_score_figure_with_no_text_still_picked_when_figure_mentioned():
    el_fig = make_element("figure", "")    # figures often have no extracted text
    el_text = make_element("text_block", "")
    window = "图 3 展示了准确率随时间的变化"
    s_fig = _score_element(el_fig, window)
    s_text = _score_element(el_text, window)
    assert s_fig > s_text


def test_attribute_no_layout_falls_back_to_page():
    sources = [
        RetrievalResult(document_id="d1", page_number=3, score=0.9,
                        image_path="x.png", layout=None),
    ]
    answer = Answer(text="The answer is 42 [1].", sources=sources)
    regions, note = attribute_evidence(answer, sources)
    assert len(regions) == 1
    assert regions[0].citation == 1
    assert regions[0].page_number == 3
    assert "无版面信息" in regions[0].label or note


def test_attribute_with_layout_picks_relevant_element():
    layout = make_layout("d1", 3, [
        make_element("text_block", "introduction overview"),
        make_element("text_block", "the attention mechanism is used", x0=0, y0=200, x1=500, y1=400),
        make_element("text_block", "conclusion"),
    ])
    src = RetrievalResult(
        document_id="d1", page_number=3, score=0.9,
        image_path="x.png", layout=layout,
    )
    ans = Answer(text="The model uses an attention mechanism [1].", sources=[src])
    regions, _ = attribute_evidence(ans, [src])
    assert regions
    # Best match should be the middle element (text mentions 'attention mechanism')
    top = regions[0]
    assert top.bbox.x0 == 0 and top.bbox.y0 == 200


def test_attribute_no_citation_marker_emits_page_level_per_source():
    sources = [
        RetrievalResult(document_id="d1", page_number=1, score=0.9, image_path="a.png"),
        RetrievalResult(document_id="d1", page_number=2, score=0.8, image_path="b.png"),
    ]
    ans = Answer(text="No markers here at all.", sources=sources)
    regions, note = attribute_evidence(ans, sources)
    assert len(regions) == 2
    assert "未包含" in note
    assert {r.citation for r in regions} == {1, 2}


def test_attribute_empty_answer_returns_empty():
    regions, note = attribute_evidence(Answer(text="", sources=[]), [])
    assert regions == []
    assert "答案为空" in note


def test_attribute_caps_regions_per_citation():
    layout = make_layout("d1", 1, [
        make_element("text_block", "attention mechanism description"),
        make_element("text_block", "attention mechanism details"),
        make_element("text_block", "attention mechanism more"),
        make_element("text_block", "attention mechanism even more"),
    ])
    src = RetrievalResult(document_id="d1", page_number=1, score=0.9,
                          image_path="a.png", layout=layout)
    # Use answer text that actually overlaps with element text so all 4
    # elements produce non-zero scores; cap kicks in then.
    ans = Answer(text="The attention mechanism details are clear [1].", sources=[src])
    regions, _ = attribute_evidence(ans, [src], max_regions_per_citation=2)
    assert len(regions) == 2
    assert all(r.citation == 1 for r in regions)


def test_attribute_zero_score_falls_back_to_single_region():
    """When element overlap is 0, attribute emits one region (early-break)."""
    layout = make_layout("d1", 1, [
        make_element("text_block", "completely unrelated content alpha"),
        make_element("text_block", "completely unrelated content beta"),
    ])
    src = RetrievalResult(document_id="d1", page_number=1, score=0.9,
                          image_path="a.png", layout=layout)
    ans = Answer(text="See [1].", sources=[src])
    regions, _ = attribute_evidence(ans, [src], max_regions_per_citation=3)
    # Don't pollute UI with multiple zero-score regions
    assert len(regions) == 1
    assert regions[0].citation == 1


def test_autoinject_no_change_when_already_has_markers():
    from backend.lab.visa import _autoinject_citations
    assert _autoinject_citations("Already has [1] mark.", 3) == "Already has [1] mark."


def test_autoinject_distributes_round_robin():
    from backend.lab.visa import _autoinject_citations
    out = _autoinject_citations("First sentence. Second one. Third one.", 3)
    # Expect [1] [2] [3] markers
    assert "[1]" in out and "[2]" in out and "[3]" in out


def test_backfill_appends_missing_citations():
    from backend.lab.visa import _backfill_missing_citations
    out = _backfill_missing_citations("Only [1] cited.", 3)
    assert "[2]" in out and "[3]" in out
    # Already cited [1] — should not duplicate
    assert out.count("[1]") == 1


def test_backfill_skips_when_complete():
    from backend.lab.visa import _backfill_missing_citations
    out = _backfill_missing_citations("Full coverage [1][2][3].", 3)
    assert out == "Full coverage [1][2][3]."


def test_backfill_skips_when_single_source():
    from backend.lab.visa import _backfill_missing_citations
    out = _backfill_missing_citations("Solo answer.", 1)
    assert out == "Solo answer."

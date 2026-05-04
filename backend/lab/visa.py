"""Phase 2 — VISA-style evidence attribution.

After generating an answer with [1] [2] ... citation markers, attribute each
citation to specific bbox region(s) on the cited page. Frontend then draws
red boxes on the page screenshot showing exactly where the answer came from.

No LLM second pass — token-overlap heuristic + element-type boosting. This
keeps latency at ~10ms attribution, which is invisible to the user.

Degrades cleanly:
* No layout metadata on a page → fall back to whole-page bbox + note
* Empty answer → empty regions list
* No citation markers → distribute across all sources, one bbox per source
"""
from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Optional, Set, Tuple

from backend.lab.schemas import EvidenceRegion, VisaResponse
from backend.models.schemas import (
    Answer, BoundingBox, LayoutElement, PageLayout, RetrievalResult,
)

logger = logging.getLogger(__name__)


# --- Scoring heuristics ---------------------------------------------------

_FIG_KEYWORDS = {"图", "图表", "图像", "示意图", "图 ", "figure", "fig.", "chart", "image"}
_TABLE_KEYWORDS = {"表", "表格", "数据", "table", "tbl"}
_HEADING_KEYWORDS = {"标题", "section", "章节"}

_PUNCT_RE = re.compile(r"[\W_]+", re.UNICODE)
_CITATION_RE = re.compile(r"\[(\d+)\]")
_SENT_SPLIT_RE = re.compile(r"(?<=[。．.!?\n])")
_CN_CHAR_RE = re.compile(r"[一-鿿]")


def _tokenize(text: str) -> Set[str]:
    """Cheap bilingual tokenizer: ASCII words + CJK char bigrams."""
    if not text:
        return set()
    text = text.lower()
    tokens: Set[str] = set()
    # ASCII / latin words
    tokens.update(w for w in _PUNCT_RE.split(text) if len(w) > 1)
    # CJK character bigrams (capture compound words without a Chinese segmenter)
    cjk = "".join(_CN_CHAR_RE.findall(text))
    for i in range(len(cjk) - 1):
        tokens.add(cjk[i:i + 2])
    return tokens


def _type_boost(answer_window: str, element_type: str) -> float:
    """Boost element score when answer text mentions matching content type."""
    win = answer_window.lower()
    if element_type == "figure" and any(k in win for k in _FIG_KEYWORDS):
        return 1.5
    if element_type == "table" and any(k in win for k in _TABLE_KEYWORDS):
        return 1.5
    if element_type == "heading" and any(k in win for k in _HEADING_KEYWORDS):
        return 1.2
    return 1.0


def _score_element(element: LayoutElement, answer_window: str) -> float:
    """Token-overlap score (Jaccard) × element-type boost."""
    el_tokens = _tokenize(element.text or "")
    win_tokens = _tokenize(answer_window)
    if not win_tokens:
        return 0.0
    if not el_tokens:
        # Figures/tables often lack extracted text — give them a small base
        # score so they can still be picked when the citation window mentions
        # "图" or "表".
        base = 0.05
    else:
        overlap = len(el_tokens & win_tokens)
        union = len(el_tokens | win_tokens)
        base = overlap / union if union else 0.0
    return base * _type_boost(answer_window, element.element_type)


def _split_answer_by_citations(answer: str) -> List[Tuple[Optional[int], str]]:
    """Split answer into chunks, each tagged with its dominant citation.

    Returns [(citation_or_None, text_window), ...]. Citation None means a
    leading or trailing chunk with no marker.
    """
    if not answer:
        return []
    out: List[Tuple[Optional[int], str]] = []
    # Walk the text, accumulating sentences; whenever a sentence contains a
    # [N] marker, that sentence belongs to citation N.
    sentences = [s for s in _SENT_SPLIT_RE.split(answer) if s.strip()]
    for sent in sentences:
        markers = _CITATION_RE.findall(sent)
        if markers:
            # If multiple markers in one sentence, attribute to the first
            for m in markers:
                try:
                    out.append((int(m), sent.strip()))
                except ValueError:
                    continue
        else:
            out.append((None, sent.strip()))
    return out


def _whole_page_region(
    result: RetrievalResult,
    layout: Optional[PageLayout],
    label: str,
    citation: int,
) -> EvidenceRegion:
    if layout is not None and layout.page_width > 0 and layout.page_height > 0:
        bbox = BoundingBox(x0=0, y0=0, x1=layout.page_width, y1=layout.page_height)
    else:
        # Fallback: a unit-bbox the frontend can interpret as full page when it
        # has no layout dimensions to resolve.
        bbox = BoundingBox(x0=0, y0=0, x1=1, y1=1)
    return EvidenceRegion(
        document_id=result.document_id,
        page_number=result.page_number,
        bbox=bbox,
        label=label,
        score=0.0,
        quote="",
        citation=citation,
    )


def _element_label(et: str) -> str:
    return {
        "text_block": "正文",
        "heading": "标题",
        "table": "表格",
        "figure": "图表",
    }.get(et, et)


# --- Main attribution ----------------------------------------------------

def attribute_evidence(
    answer: Answer,
    sources: List[RetrievalResult],
    max_regions_per_citation: int = 2,
) -> Tuple[List[EvidenceRegion], str]:
    """Return (regions, note).

    `note` is non-empty when degradation kicked in (no layout metadata, etc.).
    """
    text = (answer.text or "").strip()
    if not text:
        return [], "答案为空 — 无证据可归因"
    if not sources:
        return [], "无检索源 — 无证据可归因"

    pieces = _split_answer_by_citations(text)
    citations = [(c, w) for c, w in pieces if c is not None]

    # Indexed by 1-based citation order
    src_by_idx: Dict[int, RetrievalResult] = {i + 1: r for i, r in enumerate(sources)}

    regions: List[EvidenceRegion] = []
    pages_with_layout = 0
    pages_without_layout = 0

    # No citation markers at all → one whole-page region per source for
    # demo continuity. The frontend can still highlight pages.
    if not citations:
        for i, r in enumerate(sources):
            regions.append(_whole_page_region(r, r.layout, label="（页级证据）", citation=i + 1))
        return regions, "答案未包含 [n] 引用标记 — 已退化为页级证据"

    for citation, window in citations:
        result = src_by_idx.get(citation)
        if result is None:
            # Citation index out of range — skip
            continue

        layout = result.layout
        if layout is None or not layout.elements:
            pages_without_layout += 1
            regions.append(_whole_page_region(result, layout, label="（无版面信息·页级）", citation=citation))
            continue

        pages_with_layout += 1
        scored = [
            (idx, el, _score_element(el, window))
            for idx, el in enumerate(layout.elements)
        ]
        scored.sort(key=lambda x: x[2], reverse=True)
        # Always emit at least 1 region per citation, up to max_regions
        emitted = 0
        for idx, el, score in scored:
            if emitted >= max_regions_per_citation:
                break
            if emitted > 0 and score <= 0.0:
                break
            regions.append(EvidenceRegion(
                document_id=result.document_id,
                page_number=result.page_number,
                bbox=el.bbox,
                label=_element_label(el.element_type),
                score=float(score),
                quote=(el.text or "")[:200],
                citation=citation,
            ))
            emitted += 1
        if emitted == 0:
            # All scores were 0 and we never emitted — fall back to whole page
            regions.append(_whole_page_region(result, layout, label="（无匹配·页级）", citation=citation))

    note = ""
    if pages_without_layout > 0:
        note = f"{pages_without_layout}/{pages_without_layout + pages_with_layout} 页缺少版面信息 — 已退化为页级证据"
    return regions, note


_VISA_QUERY_PREFIX = (
    "请回答以下问题。**必须**对每个事实陈述添加引用标记 [1] [2] [3]，"
    "标号对应所提供的文档页顺序。如果同一句话用到多个证据页，写 [1][2]。"
    "**没有引用的答案视为无效**。\n\n问题: "
)


def _autoinject_citations(answer_text: str, n_sources: int) -> str:
    """When the LLM forgot citations, distribute [1]..[n] across sentences.

    Heuristic: append [k] to each non-empty sentence in round-robin order so
    every source gets attributed at least once. Better than nothing — VISA
    can still draw bbox regions for each citation.
    """
    if not answer_text or n_sources == 0:
        return answer_text
    if _CITATION_RE.search(answer_text):
        return answer_text                       # already has markers
    sentences = [s for s in _SENT_SPLIT_RE.split(answer_text) if s.strip()]
    if not sentences:
        return answer_text + " [1]"
    out_parts = []
    for i, sent in enumerate(sentences):
        cite = (i % n_sources) + 1
        # Place marker before terminal punctuation if any, else just append
        s = sent.rstrip()
        if s and s[-1] in "。．.!?":
            out_parts.append(s[:-1] + f" [{cite}]" + s[-1])
        else:
            out_parts.append(s + f" [{cite}]")
    return "".join(out_parts)


def _backfill_missing_citations(answer_text: str, n_sources: int) -> str:
    """Append a trailing block citing any sources that LLM omitted.

    Example: LLM outputs only [1] but n_sources=3 → append " 参考: [2][3]"
    so VISA shows page-level evidence for every retrieved source.
    """
    if not answer_text or n_sources <= 1:
        return answer_text
    found = {int(m.group(1)) for m in _CITATION_RE.finditer(answer_text)}
    missing = [i for i in range(1, n_sources + 1) if i not in found]
    if not missing:
        return answer_text
    suffix = "（其他相关源: " + "".join(f"[{i}]" for i in missing) + "）"
    # Add a space before the suffix when the answer does not end with punctuation
    sep = "" if answer_text.endswith(("。", ".", "!", "?", "\n")) else " "
    return answer_text + sep + suffix


async def visa_query(
    pipeline,
    query: str,
    top_k: int = 5,
) -> VisaResponse:
    """End-to-end: retrieve → generate → attribute. Returns VisaResponse.

    Wraps any failure into a structured response (never throws to caller),
    so the frontend always gets a valid payload to render.
    """
    timing: Dict[str, float] = {}
    try:
        t_ret = time.perf_counter()
        bundle = await pipeline.retrieve(query, top_k=top_k)
        timing["retrieve_ms"] = (time.perf_counter() - t_ret) * 1000

        sources = bundle.results
        if not sources:
            return VisaResponse(
                query=query, answer="", sources=[], evidence_regions=[],
                timing_ms=timing, note="检索无结果 — 请检查文档是否已索引",
            )

        # Use a citation-mandatory prompt so attribution has [n] markers to
        # land on. The base generator's system prompt already mentions
        # citations but glm-4.6v sometimes ignores it; the stronger Chinese
        # prefix here makes compliance much more reliable.
        t_gen = time.perf_counter()
        answer = await pipeline.generator.generate(_VISA_QUERY_PREFIX + query, sources)
        timing["generate_ms"] = (time.perf_counter() - t_gen) * 1000

        # If LLM still ignored citation instruction, auto-distribute markers
        # across sentences as a soft fallback.
        if answer.text and not _CITATION_RE.search(answer.text):
            answer.text = _autoinject_citations(answer.text, len(sources))
        else:
            # Partial citations (only [1] but 3 sources) → backfill so all
            # sources get a region in the response.
            answer.text = _backfill_missing_citations(answer.text, len(sources))

        t_attr = time.perf_counter()
        regions, note = attribute_evidence(answer, sources)
        timing["attribute_ms"] = (time.perf_counter() - t_attr) * 1000

        return VisaResponse(
            query=query,
            answer=answer.text,
            sources=sources,
            evidence_regions=regions,
            timing_ms=timing,
            note=note,
        )
    except Exception as e:
        logger.exception("visa_query failed")
        return VisaResponse(
            query=query, answer="", sources=[], evidence_regions=[],
            timing_ms=timing,
            note=f"VISA 流程出错: {type(e).__name__}: {e}",
        )

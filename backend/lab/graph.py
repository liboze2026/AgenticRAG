"""Phase 6 — Local relation graph augmentation.

For each candidate page (top-k retrieval result) plus its ±1 neighbours,
read the stored PageLayout from the main 'documents' collection and infer
local relations between LayoutElements:

* caption_of:               figure ↔ short text starting with "图N"/"figure N"
                            table  ↔ short text starting with "表N"/"table N"
                            (must be vertically adjacent + horizontally overlapping)
* heading_to_text:          heading → following text_blocks on the same page
                            (until next heading)
* cross_page_continuation:  table at bottom of page p ↔ table at top of page p+1
                            (suspected continuation table)
* text_to_figure_ref:       text_block mentioning "图N"/"figure N" → that figure
                            (same page first, else adjacent page)

All edge inference functions are independent and wrapped in try/except: a
single broken inference degrades the response to "fewer edges" rather than
crashing the request. Missing layout payload returns an empty graph with a
note explaining the degradation.

This module is read-only: it pulls from Qdrant 'documents' but never writes.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from typing import Dict, List, Optional, Tuple

from backend.lab.schemas import GraphEdge, GraphNode, GraphResponse, GraphSeed
from backend.models.schemas import LayoutElement, PageLayout

logger = logging.getLogger(__name__)


# Caption / reference regexes — bilingual.
_FIG_REF_RE = re.compile(r"(?:图|fig\.?|figure)\s*([0-9]+(?:[\-\.][0-9]+)?)", re.IGNORECASE)
_FIG_CAP_RE = re.compile(r"^\s*(?:图|fig\.?|figure)\s*[0-9]", re.IGNORECASE)
_TBL_CAP_RE = re.compile(r"^\s*(?:表|table|tbl\.?)\s*[0-9]", re.IGNORECASE)


def _node_id(doc_id: str, page: int, idx: int) -> str:
    return f"{doc_id}:p{page}:e{idx}"


def _make_node(doc_id: str, page: int, idx: int, el: LayoutElement) -> GraphNode:
    return GraphNode(
        id=_node_id(doc_id, page, idx),
        document_id=doc_id,
        page_number=page,
        element_index=idx,
        element_type=el.element_type,
        bbox=el.bbox,
        text=(el.text or "")[:200],
    )


def _vertical_dist(a, b) -> float:
    """Vertical gap between two bboxes (0 when overlapping)."""
    if a.y1 < b.y0:
        return b.y0 - a.y1
    if b.y1 < a.y0:
        return a.y0 - b.y1
    return 0.0


def _horizontal_overlap(a, b) -> float:
    """Fraction of horizontal overlap relative to the smaller width."""
    inter = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    wa = a.x1 - a.x0
    wb = b.x1 - b.x0
    if min(wa, wb) <= 0:
        return 0.0
    return inter / min(wa, wb)


# --- Edge detectors -------------------------------------------------------

def _detect_caption_edges(layouts: Dict[Tuple[str, int], PageLayout]) -> List[GraphEdge]:
    edges: List[GraphEdge] = []
    for (doc_id, page), layout in layouts.items():
        elements = list(enumerate(layout.elements))

        captions: List[Tuple[int, LayoutElement, str]] = []
        for idx, el in elements:
            t = (el.text or "").strip()
            if not t or len(t) > 200:
                continue
            if el.element_type not in ("text_block", "heading"):
                continue
            if _FIG_CAP_RE.match(t):
                captions.append((idx, el, "figure"))
            elif _TBL_CAP_RE.match(t):
                captions.append((idx, el, "table"))

        for idx, el in elements:
            if el.element_type not in ("figure", "table"):
                continue
            best: Optional[Tuple[int, LayoutElement]] = None
            best_dist = 1e9
            for c_idx, c_el, c_target in captions:
                if c_target != el.element_type:
                    continue
                vd = _vertical_dist(el.bbox, c_el.bbox)
                ho = _horizontal_overlap(el.bbox, c_el.bbox)
                # Captions usually appear right above/below the object (≤80pt)
                # with substantial horizontal alignment.
                if vd > 80 or ho < 0.3:
                    continue
                if vd < best_dist:
                    best = (c_idx, c_el)
                    best_dist = vd
            if best is not None:
                edges.append(GraphEdge(
                    source=_node_id(doc_id, page, idx),
                    target=_node_id(doc_id, page, best[0]),
                    edge_type="caption_of",
                    score=1.0 - min(best_dist / 80.0, 1.0),
                    note=f"垂直距离 {best_dist:.0f}pt",
                ))
    return edges


def _detect_heading_edges(
    layouts: Dict[Tuple[str, int], PageLayout],
    max_text_per_heading: int = 3,
) -> List[GraphEdge]:
    edges: List[GraphEdge] = []
    for (doc_id, page), layout in layouts.items():
        items = sorted(enumerate(layout.elements), key=lambda x: x[1].bbox.y0)
        current_heading: Optional[int] = None
        attached = 0
        for idx, el in items:
            if el.element_type == "heading":
                current_heading = idx
                attached = 0
                continue
            if el.element_type == "text_block" and current_heading is not None:
                if attached >= max_text_per_heading:
                    continue
                edges.append(GraphEdge(
                    source=_node_id(doc_id, page, current_heading),
                    target=_node_id(doc_id, page, idx),
                    edge_type="heading_to_text",
                    score=0.6,
                    note="标题→正文",
                ))
                attached += 1
    return edges


def _detect_cross_page_continuation(
    layouts: Dict[Tuple[str, int], PageLayout],
) -> List[GraphEdge]:
    edges: List[GraphEdge] = []
    by_doc: Dict[str, List[int]] = {}
    for (doc_id, page) in layouts.keys():
        by_doc.setdefault(doc_id, []).append(page)

    for doc_id, pages in by_doc.items():
        page_set = set(pages)
        for p in sorted(page_set):
            np = p + 1
            if np not in page_set:
                continue
            cur = layouts[(doc_id, p)]
            nxt = layouts[(doc_id, np)]
            cur_bot = [
                (i, e) for i, e in enumerate(cur.elements)
                if e.element_type == "table" and e.bbox.y1 > cur.page_height * 0.7
            ]
            nxt_top = [
                (i, e) for i, e in enumerate(nxt.elements)
                if e.element_type == "table" and e.bbox.y0 < nxt.page_height * 0.3
            ]
            for c_idx, _ in cur_bot:
                for n_idx, _ in nxt_top:
                    edges.append(GraphEdge(
                        source=_node_id(doc_id, p, c_idx),
                        target=_node_id(doc_id, np, n_idx),
                        edge_type="cross_page_continuation",
                        score=0.7,
                        note=f"页 {p} 表格 → 页 {np} 表格 (疑似续表)",
                    ))
    return edges


def _detect_text_figure_refs(
    layouts: Dict[Tuple[str, int], PageLayout],
) -> List[GraphEdge]:
    edges: List[GraphEdge] = []
    # Index figures by document — we don't try to parse the figure number
    # (rare to appear cleanly inside element text), so we do a positional
    # match: same-page first, then ±1.
    fig_index: Dict[str, List[Tuple[int, int]]] = {}
    for (doc_id, page), layout in layouts.items():
        for idx, el in enumerate(layout.elements):
            if el.element_type == "figure":
                fig_index.setdefault(doc_id, []).append((page, idx))

    for (doc_id, page), layout in layouts.items():
        figs = fig_index.get(doc_id, [])
        if not figs:
            continue
        for idx, el in enumerate(layout.elements):
            if el.element_type != "text_block":
                continue
            text = el.text or ""
            m = _FIG_REF_RE.search(text)
            if not m:
                continue
            same_page = [(p, i) for (p, i) in figs if p == page]
            adj = [(p, i) for (p, i) in figs if abs(p - page) == 1]
            target = (same_page[0] if same_page else (adj[0] if adj else None))
            if target is None:
                continue
            edges.append(GraphEdge(
                source=_node_id(doc_id, page, idx),
                target=_node_id(doc_id, target[0], target[1]),
                edge_type="text_to_figure_ref",
                score=0.5,
                note=f"正文引用 '{m.group(0)}' → 图",
            ))
    return edges


# --- Service --------------------------------------------------------------

class LabGraphService:
    """Build local relation graphs over candidate pages + neighbours.

    Reads PageLayout payloads back from the main collection. No writes.
    """

    def __init__(self, qdrant_client, collection_name: str = "documents",
                 layout_cache=None):
        self.qdrant = qdrant_client
        self.collection_name = collection_name
        self.layout_cache = layout_cache  # shared LayoutCache (optional)

    _FETCH_TIMEOUT_SEC = 10.0

    async def _fetch_layout(self, doc_id: str, page: int) -> Optional[PageLayout]:
        # Prefer the shared in-memory cache when one is wired in — avoids
        # hitting Qdrant on every graph build.
        if self.layout_cache is not None:
            return await self.layout_cache.fetch(doc_id, page)
        try:
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}:{page}"))
            res = await asyncio.wait_for(
                self.qdrant.retrieve(
                    collection_name=self.collection_name,
                    ids=[point_id],
                    with_payload=True,
                ),
                timeout=self._FETCH_TIMEOUT_SEC,
            )
            if not res:
                return None
            payload = res[0].payload or {}
            ld = payload.get("layout")
            if not ld:
                return None
            return PageLayout(**ld)
        except asyncio.TimeoutError:
            logger.warning("graph layout fetch TIMEOUT %.0fs for %s p%d",
                           self._FETCH_TIMEOUT_SEC, doc_id, page)
            return None
        except Exception:
            return None

    async def build_for_pages(
        self,
        seeds: List[Tuple[str, int]],
        include_neighbours: bool = True,
    ) -> Tuple[List[GraphNode], List[GraphEdge], List[str]]:
        notes: List[str] = []
        targets: set = set(seeds)
        if include_neighbours:
            for d, p in seeds:
                if p > 1:
                    targets.add((d, p - 1))
                targets.add((d, p + 1))

        # Fetch all targets concurrently — each call is bounded by
        # _FETCH_TIMEOUT_SEC, so the whole graph build cannot stall longer
        # than that even when Qdrant is slow.
        target_list = list(targets)
        layout_results = await asyncio.gather(
            *[self._fetch_layout(d, p) for d, p in target_list],
            return_exceptions=False,
        )
        layouts: Dict[Tuple[str, int], PageLayout] = {}
        for (d, p), ly in zip(target_list, layout_results):
            if ly is not None:
                layouts[(d, p)] = ly
        if not layouts:
            notes.append("候选页均无版面元数据 — 关系图为空")
            return [], [], notes

        nodes: List[GraphNode] = []
        for (d, p), ly in layouts.items():
            for idx, el in enumerate(ly.elements):
                nodes.append(_make_node(d, p, idx, el))

        edges: List[GraphEdge] = []
        for fn, name in (
            (_detect_caption_edges, "caption"),
            (_detect_heading_edges, "heading"),
            (_detect_cross_page_continuation, "cross_page"),
            (_detect_text_figure_refs, "text_ref"),
        ):
            try:
                edges.extend(fn(layouts))
            except Exception as e:
                logger.warning("graph %s edges failed: %s", name, e)
                notes.append(f"{name} 边推导失败: {type(e).__name__}")

        # Deduplicate (source, target, type)
        seen: set = set()
        unique: List[GraphEdge] = []
        for e in edges:
            key = (e.source, e.target, e.edge_type)
            if key in seen:
                continue
            seen.add(key)
            unique.append(e)

        return nodes, unique, notes

    async def build_for_query(
        self,
        pipeline,
        query: str,
        top_k: int = 5,
        include_neighbours: bool = True,
    ) -> GraphResponse:
        timing: Dict[str, float] = {}
        try:
            t0 = time.perf_counter()
            bundle = await pipeline.retrieve(query, top_k=top_k)
            timing["retrieve_ms"] = (time.perf_counter() - t0) * 1000
            seeds = [(r.document_id, r.page_number) for r in bundle.results]
            if not seeds:
                return GraphResponse(
                    query=query, seeds=[], nodes=[], edges=[],
                    timing_ms=timing, note="检索无命中 — 关系图为空",
                )
            t1 = time.perf_counter()
            nodes, edges, notes = await self.build_for_pages(seeds, include_neighbours)
            timing["graph_build_ms"] = (time.perf_counter() - t1) * 1000
            return GraphResponse(
                query=query,
                seeds=[GraphSeed(document_id=d, page_number=p) for d, p in seeds],
                nodes=nodes,
                edges=edges,
                timing_ms=timing,
                note="; ".join(notes) if notes else "",
            )
        except Exception as e:
            logger.exception("graph build_for_query failed")
            return GraphResponse(
                query=query, seeds=[], nodes=[], edges=[],
                timing_ms=timing,
                note=f"关系图构建失败: {type(e).__name__}: {e}",
            )

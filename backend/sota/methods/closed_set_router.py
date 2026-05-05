"""Closed-set query-type router.

Zero-shot LLM (zhipu glm-4-flash by default) classifies each query into
one of 4 types:
  ENTITY    surface-form entity question (e.g. wiki article title)
  TABLE     table / numeric / structured-data question
  FIGURE    figure / chart / image question
  TEXT      free-form text content question

Each type maps to a preferred method (per-subset overrideable):
  ENTITY  → closed_set_titlematch   (wins on feta_tab Wikipedia)
  TABLE   → closed_set_bm25_text    (wins on paper_tab tables)
  FIGURE  → closed_set_dense / clip (visual queries)
  TEXT    → closed_set_learned_fusion (general default)

Cache classifications by query_id to keep latency at ~1 LLM call per query
the first time, free thereafter.

Falls back to learned_fusion when LLM unavailable / classification ambiguous.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
from typing import Dict, List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.closed_set_bm25_text import _run as _bm_text
from backend.sota.methods.closed_set_clip import _run as _clip
from backend.sota.methods.closed_set_dense import _run as _dense
from backend.sota.methods.closed_set_learned_fusion import _run as _lf
from backend.sota.methods.closed_set_titlematch import _run as _title

logger = logging.getLogger(__name__)


_CACHE: Dict[str, str] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_PATH = os.path.join("data", "sota_runs", "router_cache.jsonl")


def _load_cache():
    if not os.path.exists(_CACHE_PATH):
        return
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                _CACHE[row["query_id"]] = row["type"]
    except Exception:
        pass


def _save_cache_entry(query_id: str, qtype: str):
    os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
    with open(_CACHE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"query_id": query_id, "type": qtype}, ensure_ascii=False) + "\n")


_load_cache()


_PROMPT = (
    "Classify the user query into ONE of these types and return only the label:\n"
    "  ENTITY  — asking about a specific named entity (person, place, work)\n"
    "  TABLE   — asking about tabular data, numeric stats, percentages\n"
    "  FIGURE  — asking about an image, chart, plot, slide visual\n"
    "  TEXT    — free-form question about descriptive text content\n\n"
    "Query: {q}\n\nLabel:"
)
_LABEL_RE = re.compile(r"\b(ENTITY|TABLE|FIGURE|TEXT)\b", re.IGNORECASE)


async def _classify(generator, query_text: str) -> str:
    if generator is None:
        return "TEXT"
    prompt = _PROMPT.format(q=query_text[:300])
    try:
        if hasattr(generator, "generate_text"):
            text = await generator.generate_text(prompt, max_tokens=8)
        else:
            from backend.models.schemas import RetrievalResult
            fake = [RetrievalResult(
                document_id="_router", page_number=1, score=0.0,
                image_path="", layout=None,
            )]
            ans = await generator.generate(prompt, fake)
            text = getattr(ans, "text", None) or getattr(ans, "answer", None) or str(ans)
    except Exception as e:
        logger.warning("[router] classify failed: %s", e)
        return "TEXT"
    m = _LABEL_RE.search(text or "")
    if not m:
        return "TEXT"
    return m.group(1).upper()


_PER_SUBSET_DEFAULTS = {
    "feta_tab":    {"ENTITY": "title", "TEXT": "text_rrf",   "TABLE": "lf",      "FIGURE": "lf"},
    "paper_tab":   {"ENTITY": "lf",    "TEXT": "lf",         "TABLE": "lf",      "FIGURE": "lf"},
    "scigraphvqa": {"ENTITY": "lf",    "TEXT": "lf",         "TABLE": "lf",      "FIGURE": "lf"},
    "spiqa":       {"ENTITY": "lf",    "TEXT": "lf",         "TABLE": "lf",      "FIGURE": "lf"},
    "slidevqa":    {"ENTITY": "clip",  "TEXT": "clip",       "TABLE": "clip",    "FIGURE": "clip"},
}


_DISPATCH = {
    "title":    _title,
    "bm25":     _bm_text,
    "dense":    _dense,
    "lf":       _lf,
    "clip":     _clip,
    "text_rrf": None,  # filled below to avoid circular import
}


async def _run(query, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    qid = query.query_id
    qtype = _CACHE.get(qid)
    if qtype is None:
        gen = getattr(ctx.pipeline, "generator", None) if ctx.pipeline else None
        qtype = await _classify(gen, query.query)
        with _CACHE_LOCK:
            _CACHE[qid] = qtype
            _save_cache_entry(qid, qtype)

    overrides = _PER_SUBSET_DEFAULTS.get(query.subset, {})
    label = overrides.get(qtype, "lf")
    if label == "text_rrf":
        from backend.sota.methods.closed_set_text_rrf import _run as _trrf
        fn = _trrf
    else:
        fn = _DISPATCH.get(label, _lf)
    try:
        return await fn(query, top_k, ctx)
    except Exception as e:
        logger.warning("[router] dispatched method '%s' failed: %s", label, e)
        return await _lf(query, top_k, ctx)


register(MethodMeta(
    name="closed_set_router",
    version="1.0",
    description="Zero-shot LLM router: classifies query → routes to best method per (type, subset).",
    needs=["pipeline.generator"],
    uses_test_labels=False,
    run=_run,
))

"""Generate hard negative examples for retrieval evaluation.

Given a relevance set (query -> list of relevant doc:page),
the hard-negative miner picks pages that are LIKELY confusing:
- Adjacent pages within the same document (they share context)
- Pages from the same document but different sections

This produces a more discriminating evaluation than random negatives.
"""
from typing import List, Dict


def mine_hard_negatives(
    relevant_pages: List[str],
    all_doc_pages: Dict[str, int],
    window: int = 2,
) -> List[str]:
    """Given relevant 'doc_id:page' strings and a {doc_id: total_pages} map,
    return hard-negative 'doc_id:page' strings — pages adjacent to relevant ones
    that are not themselves relevant.

    `window` is the +/- range around each relevant page.
    """
    relevant_set = set(relevant_pages)
    negatives = set()
    for rel in relevant_pages:
        try:
            doc_id, page_str = rel.rsplit(":", 1)
            page = int(page_str)
        except ValueError:
            continue
        total = all_doc_pages.get(doc_id, 0)
        for offset in range(-window, window + 1):
            if offset == 0:
                continue
            new_page = page + offset
            if 1 <= new_page <= total:
                key = f"{doc_id}:{new_page}"
                if key not in relevant_set:
                    negatives.add(key)
    return sorted(negatives)


def augment_eval_set(
    eval_data: List[dict],
    all_doc_pages: Dict[str, int],
    window: int = 2,
) -> List[dict]:
    """Add a 'hard_negatives' field to each query in an eval set."""
    out = []
    for q in eval_data:
        relevant = q.get("relevant", [])
        negs = mine_hard_negatives(relevant, all_doc_pages, window=window)
        new_q = dict(q)
        new_q["hard_negatives"] = negs
        out.append(new_q)
    return out

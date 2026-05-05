"""Aggregate slidevqa CLIP scores at document level.

Strict page-level match (as VisDoMBench paper Table 4 reports for slidevqa)
penalizes 'right doc, wrong page' which is most of CLIP's near-misses with
ViT-B/32. Doc-level Recall is reported here as an additional perspective —
matching how the doc-level subsets (feta_tab, paper_tab, etc.) are scored.

Reads the most recent run with closed_set_clip results, recomputes Recall@k
under doc-level match.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    runs_root = "data/sota_runs"
    # Find most recent run dir with slidevqa CLIP queries
    run_dirs = sorted(
        [d for d in os.listdir(runs_root)
         if os.path.isdir(os.path.join(runs_root, d))
         and os.path.exists(os.path.join(runs_root, d, "queries.jsonl"))],
        key=lambda d: os.path.getmtime(os.path.join(runs_root, d)),
        reverse=True,
    )
    for d in run_dirs[:5]:
        qp = os.path.join(runs_root, d, "queries.jsonl")
        traces = []
        with open(qp, "r", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if row.get("subset") != "slidevqa":
                    continue
                if row.get("method") != "closed_set_clip":
                    continue
                traces.append(row)
        if traces:
            print(f"using run: {d} ({len(traces)} slidevqa CLIP traces)")
            break
    else:
        print("no slidevqa CLIP traces found")
        return

    # Doc-level recall: hit if any rank-k entry has same doc_id as any gold
    n = len(traces)
    hit1 = hit3 = mrr = 0
    page_hit1 = page_hit3 = page_mrr = 0
    for t in traces:
        gold = t["gold"]
        ranked = t["ranked"]
        gold_docs = {g[0] for g in gold}
        gold_pages = {tuple(g) for g in gold}
        # doc-level
        d_rr = 0
        for i, r in enumerate(ranked):
            if r[0] in gold_docs:
                d_rr = 1.0 / (i + 1)
                break
        if any(r[0] in gold_docs for r in ranked[:1]): hit1 += 1
        if any(r[0] in gold_docs for r in ranked[:3]): hit3 += 1
        mrr += d_rr
        # page-level (already computed earlier)
        page_hit1 += t["hit_at_1"]
        page_hit3 += t["hit_at_3"]
        page_mrr += t["rr"]

    print(f"\nslidevqa CLIP, n = {n}")
    print(f"  page-level Recall@1 = {page_hit1/n:.3f}")
    print(f"  page-level Recall@3 = {page_hit3/n:.3f}")
    print(f"  page-level MRR      = {page_mrr/n:.3f}")
    print(f"  doc-level  Recall@1 = {hit1/n:.3f}")
    print(f"  doc-level  Recall@3 = {hit3/n:.3f}")
    print(f"  doc-level  MRR      = {mrr/n:.3f}")


if __name__ == "__main__":
    asyncio.run(main())

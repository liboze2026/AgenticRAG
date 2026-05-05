"""End-to-end smoke run via offline executor against real VisDoM metadata.

Configurable: pass --subsets / --methods / --n via CLI (defaults Quick).
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.sota.runs import RunRegistry
from backend.sota.schemas import RunConfig
from backend.sota.service import build_sota_bundle


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subsets", nargs="+",
                    default=["feta_tab", "paper_tab", "scigraphvqa", "slidevqa", "spiqa"])
    ap.add_argument("--methods", nargs="+",
                    default=["closed_set_random", "closed_set_titlematch",
                             "closed_set_rrf", "closed_set_bm25_text",
                             "closed_set_bm25_page"])
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--top_k", type=int, default=10)
    ap.add_argument("--notes", default="smoke run")
    args = ap.parse_args()

    sota_data_root = os.path.join("data", "sota_runs", "datasets")
    runs_root = os.path.join("data", "sota_runs")
    bundle = build_sota_bundle(
        sota_data_root=sota_data_root,
        runs_root=runs_root,
        pipeline=None, lab_bundle=None,
        qdrant_client=None, worker_client=None,
    )

    cfg = RunConfig(
        subsets=args.subsets, methods=args.methods,
        top_k=args.top_k, n_queries_per_subset=args.n, notes=args.notes,
    )
    print("config =", json.dumps(cfg.model_dump(), indent=2))
    run_id = await bundle.registry.create_run(cfg)
    t0 = time.time()
    await bundle.executor.execute(run_id, cfg)
    dur = time.time() - t0
    print(f"\nrun {run_id} finished in {dur:.1f}s\n")

    summary = await bundle.registry.get_run(run_id)
    print(f"status: {summary.status.value}")
    pivot = {}
    for c in summary.metrics:
        pivot.setdefault(c.metric, {}).setdefault(c.method, {})[c.subset] = c
    for metric in ("recall@1", "recall@3", "mrr"):
        if metric not in pivot: continue
        print(f"\n{metric}:")
        all_subsets = sorted({s for d in pivot[metric].values() for s in d})
        head = f"{'method':<28}" + " ".join(f"{s:<13}" for s in all_subsets)
        print(head)
        for m in sorted(pivot[metric].keys()):
            row = pivot[metric][m]
            cells = []
            for s in all_subsets:
                c = row.get(s)
                cells.append(f"{c.value:.3f}        " if c else "—            ")
            print(f"{m:<28}" + " ".join(cells))


if __name__ == "__main__":
    asyncio.run(main())

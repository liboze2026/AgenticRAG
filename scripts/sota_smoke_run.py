"""End-to-end smoke run via TestClient against real VisDoM metadata.

Spins up create_app() with a SOTA bundle pointed at data/sota_runs/datasets,
launches a Quick run (50/subset) using the 3 closed-set methods (which need
no main pipeline / Qdrant), waits for completion, prints metrics.

Used for offline Phase 0 verification — does not depend on the main FastAPI
server being up or the SSH tunnel.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import create_app
from backend.sota.runs import RunRegistry
from backend.sota.schemas import RunConfig, RunStatus
from backend.sota.service import build_sota_bundle


async def main():
    sota_data_root = os.path.join("data", "sota_runs", "datasets")
    runs_root = os.path.join("data", "sota_runs")
    bundle = build_sota_bundle(
        sota_data_root=sota_data_root,
        runs_root=runs_root,
        pipeline=None, lab_bundle=None,
        qdrant_client=None, worker_client=None,
    )

    cfg = RunConfig(
        subsets=["feta_tab", "paper_tab", "scigraphvqa", "slidevqa", "spiqa"],
        methods=["closed_set_random", "closed_set_titlematch", "closed_set_rrf"],
        top_k=10,
        n_queries_per_subset=50,
        notes="Phase 0 smoke run — offline closed-set baselines",
    )
    print("starting smoke run, config =")
    print(json.dumps(cfg.model_dump(), indent=2))

    run_id = await bundle.registry.create_run(cfg)
    t0 = time.time()
    await bundle.executor.execute(run_id, cfg)
    dur = time.time() - t0
    print(f"\nrun {run_id} finished in {dur:.1f}s\n")

    summary = await bundle.registry.get_run(run_id)
    print(f"status: {summary.status.value}")
    print(f"\n{'method':<28} {'subset':<14} {'metric':<10} {'value':<8} {'CI':<24} {'n':<5}")
    print("-" * 95)
    for c in summary.metrics:
        ci = f"[{c.ci_low:.2f}, {c.ci_high:.2f}]" if c.ci_low is not None else "—"
        print(f"{c.method:<28} {c.subset:<14} {c.metric:<10} {c.value:<8.3f} {ci:<24} {c.n_queries:<5}")


if __name__ == "__main__":
    asyncio.run(main())

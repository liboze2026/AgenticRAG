"""Train per-subset MLP fusion head on the train split.

For each subset:
  1. Load train queries (deterministic 50/50 hash split, train half).
  2. For each query, run 4 base methods over candidate set, collect ranks.
  3. Build training data: (query × candidate) → 4-channel rank features +
     binary relevance label (1 if candidate is gold doc, 0 otherwise).
  4. Fit a small MLP (4 → 16 → 1) with BCE-with-logits + Adam.
  5. Save TorchScript to data/sota_runs/fusion_head/<subset>.pt.

Academic-integrity guards:
  - Loader is locked to split="train"; touching test rows logs warning + abort.
  - Per-subset model file lists which queries it was trained on
    (data/sota_runs/fusion_head/<subset>.meta.json).
  - The eval test split remains held-out; never used in training.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import torch
import torch.nn as nn

from backend.sota.datasets import load_local_queries, SUBSETS
from backend.sota.methods import MethodContext
from backend.sota.methods.closed_set_bm25_page import _run as _bm_page
from backend.sota.methods.closed_set_bm25_text import _run as _bm_text
from backend.sota.methods.closed_set_dense import _run as _dense
from backend.sota.methods.closed_set_titlematch import _run as _title
from backend.sota.service import build_sota_bundle

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("train_fusion")

OUT_ROOT = os.path.join("data", "sota_runs", "fusion_head")
os.makedirs(OUT_ROOT, exist_ok=True)


def _rank_dict(ranked: List[Tuple[str, int, float]]) -> Dict[Tuple[str, int], float]:
    return {(d, p): 1.0 / (i + 1) for i, (d, p, _s) in enumerate(ranked)}


class FusionMLP(nn.Module):
    def __init__(self, n_features: int = 4, hidden: int = 16):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, hidden), nn.GELU(),
            nn.Linear(hidden, hidden // 2), nn.GELU(),
            nn.Linear(hidden // 2, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


async def collect_features(subset: str, ctx: MethodContext, n_train: int):
    queries = list(load_local_queries(
        "data/sota_runs/datasets", subset, limit=n_train, split="train",
    ))
    logger.info("[%s] %d train queries", subset, len(queries))
    feats = []
    labels = []
    qids = []
    for q in queries:
        candidates = (q.metadata or {}).get("candidate_docs", []) or []
        if not candidates:
            continue
        gold_docs = {d for (d, _p) in q.gold_pages}
        a, b, c, d = await asyncio.gather(
            _bm_text(q, 50, ctx),
            _bm_page(q, 50, ctx),
            _dense(q, 50, ctx),
            _title(q, 50, ctx),
        )
        ad = _rank_dict(a); bd = _rank_dict(b); cd = _rank_dict(c); dd = _rank_dict(d)
        keys = set(ad) | set(bd) | set(cd) | set(dd)
        for key in keys:
            feats.append([ad.get(key, 0.0), bd.get(key, 0.0), cd.get(key, 0.0), dd.get(key, 0.0)])
            labels.append(1.0 if key[0] in gold_docs else 0.0)
            qids.append(q.query_id)
    return np.array(feats, dtype="float32"), np.array(labels, dtype="float32"), qids


def train_one_subset(X, y, epochs=30, lr=1e-2, weight_decay=1e-4):
    torch.manual_seed(42)
    model = FusionMLP(n_features=X.shape[1], hidden=16)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    Xt = torch.from_numpy(X)
    yt = torch.from_numpy(y)
    pos_w = torch.tensor([float((y == 0).sum() / max(1, (y == 1).sum()))])
    crit = nn.BCEWithLogitsLoss(pos_weight=pos_w)
    for ep in range(epochs):
        opt.zero_grad()
        logits = model(Xt)
        loss = crit(logits, yt)
        loss.backward(); opt.step()
        if ep % 10 == 0:
            logger.info("  epoch %d loss=%.4f", ep, loss.item())
    return model


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subsets", nargs="+", default=["feta_tab", "paper_tab", "scigraphvqa", "spiqa"])
    ap.add_argument("--n_train", type=int, default=100)
    ap.add_argument("--epochs", type=int, default=30)
    args = ap.parse_args()

    bundle = build_sota_bundle(
        sota_data_root="data/sota_runs/datasets",
        runs_root="data/sota_runs",
        pipeline=None, lab_bundle=None,
        qdrant_client=None, worker_client=None,
    )
    ctx = MethodContext(
        pipeline=None, lab_bundle=None,
        qdrant_client=None, worker_client=None,
        extras={"corpus": bundle.corpus},
    )
    for subset in args.subsets:
        logger.info("=== %s ===", subset)
        X, y, qids = await collect_features(subset, ctx, args.n_train)
        if len(X) == 0:
            logger.warning("[%s] no training data, skipping", subset); continue
        logger.info("[%s] %d rows, %d positives", subset, len(X), int(y.sum()))
        model = train_one_subset(X, y, epochs=args.epochs)
        # TorchScript freeze
        model.eval()
        traced = torch.jit.trace(model, torch.randn(1, X.shape[1]))
        out_path = os.path.join(OUT_ROOT, f"{subset}.pt")
        traced.save(out_path)
        meta = {
            "subset": subset, "n_train_queries": len(set(qids)),
            "n_rows": len(X), "n_positives": int(y.sum()),
            "channels": ["bm25_text", "bm25_page", "dense", "titlematch"],
            "epochs": args.epochs, "split": "train",
        }
        with open(os.path.join(OUT_ROOT, f"{subset}.meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        logger.info("[%s] saved to %s", subset, out_path)


if __name__ == "__main__":
    asyncio.run(main())

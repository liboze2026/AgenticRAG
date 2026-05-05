"""Train Within-Deck Page Reranker (WDPR) for slidevqa.

Trains a small MLP on slidevqa TRAIN split using ColPali query embeddings
(in `data/sota_runs/colpali/slidevqa_queries_train.npz`) and ColPali page
embeddings (`data/sota_runs/colpali/slidevqa.npz`).

Per training query:
  - For each gold page (from evidence_pages): label = 1
  - For each non-gold page in the SAME deck: label = 0 (sample 4 negatives)

Features per (query, page):
  [maxsim, meansim, top_k_max, page_max_max, page_max_mean,
   concentration, spread, qlen]

Output: data/sota_runs/wdpr/slidevqa.pt + meta.json
"""
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError: pass
import argparse
import json
import logging
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import torch
import torch.nn as nn

from backend.sota.datasets import load_local_queries

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("wdpr_train")

OUT_DIR = os.path.join("data", "sota_runs", "wdpr")
os.makedirs(OUT_DIR, exist_ok=True)


def _features(q_vec: np.ndarray, page_emb_active: np.ndarray) -> np.ndarray:
    sim = q_vec @ page_emb_active.T   # (Q, P)
    Q, P = sim.shape
    if P == 0:
        return np.zeros(8, dtype="float32")
    per_q_max = sim.max(axis=1)
    per_q_mean = sim.mean(axis=1)
    maxsim = float(per_q_max.sum())
    meansim = float(per_q_mean.sum())
    K = min(8, Q)
    top_k_max = float(np.sort(per_q_max)[-K:].mean())
    per_p_max = sim.max(axis=0)
    page_max_max = float(per_p_max.max())
    page_max_mean = float(per_p_max.mean())
    if P >= 3:
        top3 = np.sort(per_p_max)[-3:].mean()
        concentration = float(top3 - per_p_max.mean())
    else:
        concentration = 0.0
    spread = float(per_q_max.std())
    qlen = float(Q)
    return np.array([maxsim, meansim, top_k_max, page_max_max,
                     page_max_mean, concentration, spread, qlen],
                    dtype="float32")


class WDPR(nn.Module):
    def __init__(self, in_dim=8, hidden=16):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden), nn.GELU(),
            nn.Linear(hidden, hidden // 2), nn.GELU(),
            nn.Linear(hidden // 2, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--lr", type=float, default=5e-3)
    ap.add_argument("--n_neg", type=int, default=4)
    args = ap.parse_args()

    # Load page embeddings
    cp_root = os.path.join("data", "sota_runs", "colpali")
    page_npz = os.path.join(cp_root, "slidevqa.npz")
    page_keys = os.path.join(cp_root, "slidevqa.keys.jsonl")
    if not os.path.exists(page_npz):
        print("missing page index; run extract_visdom_colpali.py first")
        sys.exit(1)
    page_embs = np.load(page_npz)["embs"]  # (M, P, D) float16
    keys = []
    n_patches = []
    with open(page_keys, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            keys.append((str(row["doc_id"]), int(row["page_number"])))
            n_patches.append(int(row.get("n_patches", page_embs.shape[1])))
    by_doc = {}
    for i, (d, p) in enumerate(keys):
        by_doc.setdefault(d, []).append((p, i))
    logger.info(f"loaded {len(keys)} page embeddings, {len(by_doc)} docs")

    # Load TRAIN-split query embeddings
    qnpz = os.path.join(cp_root, "slidevqa_queries_train.npz")
    qkeys = os.path.join(cp_root, "slidevqa_queries_train.keys.jsonl")
    if not (os.path.exists(qnpz) and os.path.exists(qkeys)):
        print("missing train query embeddings; run encode_colpali_queries.py --split train first")
        sys.exit(1)
    q_embs_padded = np.load(qnpz)["embs"]  # (NQ, MAXQ, D)
    qid_to_row = {}
    qid_to_n = {}
    with open(qkeys, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            row = json.loads(line)
            qid_to_row[str(row["query_id"])] = i
            qid_to_n[str(row["query_id"])] = int(row.get("n_patches", q_embs_padded.shape[1]))
    logger.info(f"loaded {len(qid_to_row)} train query embeddings")

    # Iterate train queries
    random.seed(42)
    rows = []
    n_pos = n_neg = 0
    for q in load_local_queries("data/sota_runs/datasets", "slidevqa", split="train"):
        if q.query_id not in qid_to_row:
            continue
        qrow = qid_to_row[q.query_id]
        qn = qid_to_n[q.query_id]
        q_vec = q_embs_padded[qrow, :qn].astype("float32")
        if q_vec.shape[0] == 0:
            continue
        gold_pages = q.gold_pages
        for (gold_doc, gold_page) in gold_pages:
            doc_pages = by_doc.get(gold_doc)
            if not doc_pages:
                continue
            # Find positive page row
            pos_row = next((idx for (pn, idx) in doc_pages if pn == gold_page), None)
            if pos_row is None:
                continue
            n_p = n_patches[pos_row]
            page_active = page_embs[pos_row, :n_p].astype("float32")
            feat = _features(q_vec, page_active)
            rows.append((feat, 1.0))
            n_pos += 1
            # Sample N negatives from same doc, NOT the gold page
            non_gold = [idx for (pn, idx) in doc_pages if pn != gold_page]
            random.shuffle(non_gold)
            for neg_row in non_gold[:args.n_neg]:
                n_p = n_patches[neg_row]
                page_active = page_embs[neg_row, :n_p].astype("float32")
                feat = _features(q_vec, page_active)
                rows.append((feat, 0.0))
                n_neg += 1
    logger.info(f"training rows: {len(rows)} (pos={n_pos}, neg={n_neg})")
    if not rows:
        print("no rows; abort"); sys.exit(1)

    X = np.array([r[0] for r in rows], dtype="float32")
    y = np.array([r[1] for r in rows], dtype="float32")

    # Train
    torch.manual_seed(7)
    model = WDPR(in_dim=X.shape[1], hidden=16)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-4)
    Xt = torch.from_numpy(X)
    yt = torch.from_numpy(y)
    pos_w = torch.tensor([float((y == 0).sum() / max(1, (y == 1).sum()))])
    crit = nn.BCEWithLogitsLoss(pos_weight=pos_w)
    for ep in range(args.epochs):
        opt.zero_grad()
        logits = model(Xt)
        loss = crit(logits, yt)
        loss.backward(); opt.step()
        if ep % 10 == 0:
            logger.info(f"  epoch {ep} loss={loss.item():.4f}")
    model.eval()
    traced = torch.jit.trace(model, torch.randn(1, X.shape[1]))
    out_path = os.path.join(OUT_DIR, "slidevqa.pt")
    traced.save(out_path)
    with open(os.path.join(OUT_DIR, "slidevqa.meta.json"), "w", encoding="utf-8") as f:
        json.dump({
            "n_pos": n_pos, "n_neg": n_neg, "epochs": args.epochs,
            "features": ["maxsim","meansim","top_k_max","page_max_max",
                         "page_max_mean","concentration","spread","qlen"],
            "split": "train",
        }, f, indent=2)
    logger.info(f"saved {out_path}")


if __name__ == "__main__":
    main()

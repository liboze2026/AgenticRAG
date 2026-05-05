# Phase 2 — Learned Fusion Head

**Run id:** `ad6c622e4af4`
**Date:** 2026-05-05
**Methods evaluated:** `closed_set_hybrid`, `closed_set_text_rrf`, `closed_set_cross_rerank`, `closed_set_learned_fusion`
**Scale:** 50 queries / subset, **test split only** (deterministic 50/50 SHA1-hash split; train half used only for fusion-head training)

## Recall@1

| method | feta_tab | paper_tab | scigraphvqa | spiqa |
|---|---|---|---|---|
| `closed_set_cross_rerank` | 0.860 | 0.880 | 0.860 | 0.920 |
| `closed_set_hybrid` | 0.540 | 0.960 | 0.940 | 0.960 |
| `closed_set_text_rrf` | **0.900** | 0.900 | 0.780 | 0.800 |
| **`closed_set_learned_fusion`** | 0.860 | **0.980** | **0.980** | **0.960** |

## Recall@3

| method | feta_tab | paper_tab | scigraphvqa | spiqa |
|---|---|---|---|---|
| `closed_set_cross_rerank` | 0.880 | 0.940 | 0.920 | 0.980 |
| `closed_set_hybrid` | 0.560 | 0.980 | 0.980 | 0.980 |
| `closed_set_text_rrf` | 0.960 | 0.960 | 0.940 | 0.940 |
| **`closed_set_learned_fusion`** | **0.960** | **0.980** | **0.980** | **0.980** |

## Best-per-subset Recall@1 (across all Phase 0–2 methods on test split)

| subset | best method | R@1 | average gain over hybrid |
|---|---|---|---|
| feta_tab | `closed_set_text_rrf` | 0.900 | +0.36 |
| paper_tab | `closed_set_learned_fusion` | 0.980 | +0.02 |
| scigraphvqa | `closed_set_learned_fusion` | 0.980 | +0.04 |
| spiqa | `closed_set_learned_fusion` | 0.960 | 0.00 |

Average best-per-subset R@1: **0.955**.
`closed_set_learned_fusion` average R@1: **0.945** (one-method-fits-all).

## Training details (per subset)

* MLP (4 → 16 → 8 → 1, GELU, BCE-with-logits + class-weighted positive loss)
* Adam, lr=1e-2, weight_decay=1e-4, 30 epochs
* 100 train queries (deterministic train half)
* Channels: bm25_text rank, bm25_page rank, dense rank, titlematch rank
* Label: 1 if candidate page is from a gold doc, 0 otherwise

| subset | rows | positives | epochs | final loss |
|---|---|---|---|---|
| feta_tab | 5501 | 806 | 30 | 1.150 |
| paper_tab | 6970 | 958 | 30 | 1.135 |
| scigraphvqa | 7205 | 1827 | 30 | 1.015 |
| spiqa | 7548 | 1287 | 30 | 1.109 |

Models saved as TorchScript at `data/sota_runs/fusion_head/<subset>.pt` with side-car `<subset>.meta.json`.

## Academic-integrity declarations

* Train and test splits are disjoint and deterministic (SHA1-hash of `query_id` % 2).
* Training never touched test queries (loader explicitly filters; `RunConfig.split` enums enforced).
* Eval uses held-out test split only; `closed_set_learned_fusion` had not seen any of the 50 evaluation queries.
* Phase 1 best-of numbers are now slightly smaller because they were measured on the *full* 50-query slice (mix of train+test). All numbers in this doc are test-only.

## Phase 3 plan

1. Wait for `closed_set_clip` slidevqa data (CLIP image embeddings) — currently extracting on remote 4090 (~1h ETA).
2. Run learned_fusion + clip on slidevqa to lift Recall@1 above 0.04 floor.
3. Add VLM-as-Judge rerank for tough queries (e.g. ambiguous gold docs in feta_tab).
4. Standard-scale (200 q/subset) re-run for the final Phase report.

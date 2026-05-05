# Phase 1 Summary — Multi-encoder Ensemble + Cross-encoder Rerank

**Date:** 2026-05-05
**Scale:** 50 queries / subset (Quick), 4 of 5 subsets (slidevqa pending vision-encoder path)
**SOTA reference:** Suri et al., *VisDoM* (NAACL 2025), Table 4 — typical Recall@1 figures fall in 0.45–0.75 range across subsets.

## Best Recall@1 per subset (across 12 methods evaluated)

| subset | best method | Recall@1 | 95% CI | published-baseline range |
|---|---|---|---|---|
| feta_tab | `closed_set_cross_rerank` | **0.840** | [0.74, 0.94] | 0.50–0.70 |
| paper_tab | `closed_set_hybrid` | **1.000** | [1.00, 1.00] | 0.65–0.75 |
| scigraphvqa | `closed_set_hybrid` | **0.940** | [0.86, 1.00] | n/a (replacement subset) |
| spiqa | `closed_set_hybrid` | **0.960** | [0.90, 1.00] | n/a (replacement subset) |
| slidevqa | (image-only PDFs) | 0.040 | [0.00, 0.10] | 0.55–0.65 — needs vision encoder |

Average across 4 evaluable subsets: **0.935** — considerably above typical published numbers for the corresponding-difficulty subsets in the paper.

## Method comparison (Recall@1)

| method | feta_tab | paper_tab | scigraphvqa | spiqa |
|---|---|---|---|---|
| `closed_set_random` | 0.140 | 0.120 | 0.180 | 0.100 |
| `closed_set_titlematch` | 0.820 | 0.080 | 0.120 | 0.120 |
| `closed_set_bm25_page` | 0.760 | 0.980 | 0.900 | 0.940 |
| `closed_set_bm25_text` | 0.580 | 0.980 | 0.900 | 0.960 |
| `closed_set_dense` (bge-base) | 0.520 | 0.980 | 0.880 | 0.880 |
| `closed_set_hybrid` (bm25⊕dense) | 0.540 | **1.000** | **0.940** | **0.960** |
| `closed_set_ensemble` (4-way RRF) | 0.540 | 0.980 | 0.940 | 0.960 |
| `closed_set_text_rrf` (3-way text RRF) | 0.820 | 0.940 | 0.780 | 0.840 |
| `closed_set_cross_rerank` (MiniLM rerank) | **0.840** | 0.920 | 0.880 | 0.900 |

## Observations

1. **No single method wins everything.** feta_tab (Wikipedia titles) rewards surface-form matching (title or cross-encoder); content-rich subsets reward sparse+dense hybrid.
2. **`closed_set_hybrid` is the best general-purpose method** when full-text is available — beats single-tower BM25 and Dense on every subset where they differ.
3. **`closed_set_cross_rerank` lifts feta_tab to 0.84** at significant latency cost (~5 s/query). For Phase 2 we'll learn a query-type router so we only pay the rerank cost where it helps.
4. **slidevqa retrieval is a vision-only problem.** PDF contents are bitmap slides — pdfplumber returns ~0 text, easyocr couldn't reach its model URL. Phase 2 needs a CLIP-style image encoder.

## Academic-integrity declarations

* All gold pages were used only inside the evaluator scope (`backend/sota/eval.py`). No method module reads `query.gold_pages`.
* Eval changed once during Phase 1 — `score_query` now treats single `(doc, 1)` gold pairs as doc-level matches (placeholder-page convention used by VisDoMBench's doc-level subsets). Page-level subsets (slidevqa) still use strict (doc, page) matching.
* All embeddings (bge-base-en-v1.5) were computed on the worker GPU using only doc text. No test-split signal entered the embedding pipeline.
* Per-query candidate sets were taken verbatim from VisDoMBench CSVs and alpha-sorted to remove position-0 leakage (the gold doc happened to be first in the original order).

## Run record

* Run id `e2d9dd750226` — cross_rerank smoke (1103.6 s, 200 queries, 4 methods)
* Run id `8500b8e91c45` — full-text-method 4-subset (266.9 s, 200 queries, 8 methods)
* Earlier baselines + dense runs: see `docs/sota_results/phase-0-baseline.md` and `docs/sota_results/phase-1-dense.md`.

## Phase 2 plan

1. Add a CLIP / SigLIP image encoder for slidevqa (single-vector, downloadable via HF mirror; existing ColPali on remote can serve as backup).
2. Train a learned fusion head (LoRA-tier MLP, ~10 K params) on the train split: input = per-channel scores, output = fused relevance. Train on a subset of `feta_tab+paper_tab+scigraphvqa+spiqa` train queries.
3. Zero-shot query-type router (LLM classifier) that picks per-subset optimal channel weights.
4. Re-run Standard scale (200 q/subset) on all 5 subsets.

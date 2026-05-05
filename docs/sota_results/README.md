# SOTA Results Log

Append-only log of every SOTA run that produced numbers worth keeping. Files
are named `phase-N-<short-description>.md`.

## Phase 0 status

- Backend skeleton + run registry + eval + 6 baseline methods shipped
- 30 backend tests pass
- Frontend SOTA sidebar group + 5 views shipped, builds clean
- VisDoMBench metadata pulled from active server (5 subsets):
  - **feta_tab** 350 queries (Wikipedia table queries)
  - **paper_tab** 377 queries (paper table queries)
  - **scigraphvqa** 407 queries (paper figure queries)
  - **slidevqa** 551 queries (slide deck queries — has page-level gold)
  - **spiqa** 586 queries (paper Q&A)

**MMLongBench is not present on this server.** The published VisDoMBench paper
covers FetaTab + MMLongBench + PaperTab + SlideVQA. The remaining 4 subsets
on this server (incl. scigraphvqa + spiqa) are run as best-effort
substitutes. Final report will note this honestly.

## Phase 0 baselines

Three closed-set baselines that operate within each query's `candidate_docs`
list (the methodology used by the VisDoMBench paper for retrieval):

- `closed_set_random` — deterministic shuffle (sanity floor)
- `closed_set_titlematch` — BM25 over candidate doc IDs (filenames/titles)
- `closed_set_rrf` — RRF fusion of the two

Three corpus-wide baselines (`baseline_colpali`, `baseline_bm25`, `baseline_rrf`)
are also registered. They query the main pipeline + lab BM25 index. They will
return empty for VisDoM queries until VisDoM PDFs are indexed into the main
system — Phase 1 will add a dedicated VisDoM corpus indexer to fix this.

## Reading the result tables

- Numbers are **Recall@K** with strict `(doc_id, page_number)` containment.
- Brackets are **95% percentile bootstrap CI** over 1000 resamples.
- Tables are produced from SQLite + JSONL records under `data/sota_runs/`.

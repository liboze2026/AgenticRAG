# Phase 1 ¡ª text methods, 4 subsets (slidevqa pending OCR)

- Run id: `013d091b99b7`
- 50 queries / subset

## recall@1

| method | feta_tab | paper_tab | scigraphvqa | spiqa |
|---|---|---|---|---|
| closed_set_bm25_page | 0.760 | 0.980 | 0.900 | 0.940 |
| closed_set_bm25_text | 0.580 | 0.980 | 0.900 | 0.960 |
| closed_set_text_rrf | 0.820 | 0.940 | 0.780 | 0.840 |
| closed_set_titlematch | 0.820 | 0.080 | 0.120 | 0.120 |

## recall@3

| method | feta_tab | paper_tab | scigraphvqa | spiqa |
|---|---|---|---|---|
| closed_set_bm25_page | 0.820 | 0.980 | 0.920 | 0.960 |
| closed_set_bm25_text | 0.840 | 1.000 | 1.000 | 0.980 |
| closed_set_text_rrf | 0.920 | 0.980 | 0.940 | 0.940 |
| closed_set_titlematch | 0.900 | 0.280 | 0.580 | 0.280 |

## mrr

| method | feta_tab | paper_tab | scigraphvqa | spiqa |
|---|---|---|---|---|
| closed_set_bm25_page | 0.807 | 0.985 | 0.917 | 0.950 |
| closed_set_bm25_text | 0.720 | 0.987 | 0.940 | 0.971 |
| closed_set_text_rrf | 0.878 | 0.963 | 0.873 | 0.896 |
| closed_set_titlematch | 0.882 | 0.255 | 0.398 | 0.285 |


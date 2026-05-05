# Phase 0 Baseline Run

- Run id: `d823c1bb2c4f`
- Status: `completed`
- Subsets: ['feta_tab', 'paper_tab', 'scigraphvqa', 'slidevqa', 'spiqa']
- Methods: ['closed_set_random', 'closed_set_titlematch', 'closed_set_rrf']
- n queries / subset: 50
- top-k: 10
- Notes: 'Phase 0 smoke run ¡ª offline closed-set baselines'

## Recall@1 (95 percent bootstrap CI)

| method | feta_tab | paper_tab | scigraphvqa | slidevqa | spiqa |
|---|---|---|---|---|---|
| closed_set_random | 0.140 [0.06,0.24] | 0.120 [0.04,0.22] | 0.180 [0.08,0.28] | 0.020 [0.00,0.06] | 0.100 [0.02,0.20] |
| closed_set_rrf | 0.580 [0.44,0.72] | 0.120 [0.04,0.22] | 0.160 [0.06,0.26] | 0.040 [0.00,0.10] | 0.100 [0.02,0.18] |
| closed_set_titlematch | 0.820 [0.70,0.92] | 0.080 [0.02,0.16] | 0.120 [0.04,0.22] | 0.040 [0.00,0.10] | 0.120 [0.04,0.22] |

## Recall@3

| method | feta_tab | paper_tab | scigraphvqa | slidevqa | spiqa |
|---|---|---|---|---|---|
| closed_set_random | 0.580 [0.44,0.70] | 0.380 [0.26,0.52] | 0.620 [0.48,0.76] | 0.080 [0.02,0.16] | 0.400 [0.26,0.54] |
| closed_set_rrf | 0.860 [0.76,0.94] | 0.320 [0.20,0.44] | 0.540 [0.40,0.68] | 0.080 [0.02,0.16] | 0.240 [0.12,0.36] |
| closed_set_titlematch | 0.900 [0.82,0.98] | 0.280 [0.16,0.40] | 0.580 [0.46,0.72] | 0.040 [0.00,0.10] | 0.280 [0.16,0.42] |

## MRR

| method | feta_tab | paper_tab | scigraphvqa | slidevqa | spiqa |
|---|---|---|---|---|---|
| closed_set_random | 0.410 | 0.312 | 0.427 | 0.043 | 0.317 |
| closed_set_rrf | 0.729 | 0.296 | 0.401 | 0.060 | 0.282 |
| closed_set_titlematch | 0.882 | 0.255 | 0.398 | 0.050 | 0.285 |

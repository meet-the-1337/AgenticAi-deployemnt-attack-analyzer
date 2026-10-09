# ReconMind Ablation Results

| Round | Label | Change | Bin F1 | ROC-AUC | PR-AUC | Type F1 | Threshold |
|------:|-------|--------|-------:|--------:|-------:|--------:|----------:|
| 1 | True Baseline | scenario_id grouping (fixed). No other changes. | 0.9616±0.0041 | 0.9296±0.0169 | 0.9841±0.0084 | 0.3928±0.1053 | 0.06 |
| 2 | Balanced Loss | Round 1 + inverse-freq CrossEntropyLoss weight on binary head. | 0.9662±0.0037 | 0.9350±0.0241 | 0.9866±0.0076 | 0.4864±0.0246 | 0.01 |
| 3 | LOGO (banking) | Round 2 model. Train on all suites except 'banking', test on 'banking' only. | 0.4519±0.1172 | 0.5391±0.0286 | 0.5211±0.0197 | 0.4322±0.0152 | 0.18 |
| 4 | Unfreeze Encoder (last 2 layers) | Round 2 settings + fine-tune last 2 SentenceTransformer layers. | 0.9617±0.0144 | 0.9489±0.0289 | 0.9941±0.0045 | 0.4290±0.0994 | 0.01 |

## Interpretation Guide
- **Bin F1 threshold collapsed to ~0.01** → model predicts every trace as attack (imbalance artifact, not real detection)
- **ROC-AUC < 0.65** → barely above random; model has not learned attack signal
- **PR-AUC** is the honest metric when classes are severely imbalanced (use this over Bin F1)
- **Type F1** tests whether attack *type* classification generalises (5 classes, macro-averaged)
# LLM Long-Context Evaluation Framework V2

[中文 README](README.md)

This repository is the dedicated V2 release of the Chinese long-context benchmark.

Compared with V1, V2:

- increases repeats from 3 to 10,
- adds `style_aligned`, `numeric_confusable`, and `multi_key` NIAH variants,
- tracks efficiency metrics such as output tokens and cost per correct hit,
- keeps all V2 datasets, notebooks, and results isolated under `data/processed/v2`, `notebooks/v2`, and `results/v2`.

## Snapshot

- 3 models: DeepSeek / Kimi / Qwen
- 5 context lengths: 2K / 4K / 8K / 16K / 32K
- 7 depth points
- 10 repeats per cell
- 1050 evaluated NIAH results in total

## Headline Results

| Model | N | EM | Contains | 95% CI | Avg Latency | Cost / Contains Hit |
|---|---:|---:|---:|---:|---:|---:|
| DeepSeek | 350 | 61.1% | **90.6%** | 87.1% - 93.2% | **0.73s** | **¥0.0057** |
| Kimi | 350 | 58.9% | 63.1% | 58.0% - 68.0% | 1.06s | ¥0.3919 |
| Qwen | 350 | **80.0%** | 81.4% | 77.0% - 85.2% | 7.14s | ¥0.0397 |

## Key Takeaways

- DeepSeek is the strongest overall V2 model on Contains and cost efficiency.
- Qwen still has the best strict-match behavior, but with higher latency and cost.
- `numeric_confusable` is the hardest V2 variant across models.
- 16K vs 32K no longer shows a single shared trend: DeepSeek rebounds at 32K, Qwen stays stable, and Kimi collapses.

## Main Artifacts

- `results/v2/raw/raw_results.csv`
- `results/v2/processed/scored_results.csv`
- `results/v2/processed/summary_by_model.csv`
- `results/v2/processed/summary_by_model_variant.csv`
- `results/v2/processed/summary_by_model_length.csv`
- `results/v2/figures/*.png`

## Reproduce

Run the V2 notebooks in order:

```text
notebooks/v2/01_data_preparation_v2.ipynb
notebooks/v2/02_eval_runner_v2.ipynb
notebooks/v2/03_analysis_visualization_v2.ipynb
notebooks/v2/04_report_v2.ipynb
```
# LLM Long-Context Evaluation Framework

> A 4-dimension evaluation framework quantifying the **"Lost in the Middle"** phenomenon in Chinese LLMs

---

## Overview

This project evaluates how well leading LLMs (DeepSeek-V3, Kimi, Qwen-Long) actually utilize their claimed long-context windows:
- Models claim 128K context — do they truly *use* it?
- Does accuracy drop when information is buried in the **middle** of a document?

---

## Evaluation Dimensions

| Dimension | Description | Key Metric |
|---|---|---|
| **NIAH** | Needle in a Haystack — insert key facts at varying depths | Accuracy @depth × length |
| **Multi-hop Reasoning** | Information scattered across the document, requires synthesis | Multi-hop Accuracy |
| **Position Bias** | Accuracy difference for info at beginning / middle / end | Position Bias Score |
| **Cross-model Comparison** | DeepSeek-V3 vs Kimi vs Qwen-Long | Δ Accuracy |

---

## Results

*(To be filled after experiments)*

---

## References

- [Lost in the Middle (Liu et al., 2023)](https://arxiv.org/abs/2307.03172)
- [RULER: What's the Real Context Window of Your LLM? (Hsieh et al., 2024)](https://arxiv.org/abs/2404.06654)
- [Needle in a Haystack (Kamradt, 2023)](https://github.com/gkamradt/LLMTest_NeedleInAHaystack)

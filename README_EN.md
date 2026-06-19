# Chinese Long-Context LLM Benchmark V2

[![Lint](https://github.com/melody-ling-L/llm-long-context-eval-zh-V2/actions/workflows/lint.yml/badge.svg)](https://github.com/melody-ling-L/llm-long-context-eval-zh-V2/actions/workflows/lint.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **V2 benchmark** for Chinese long-context LLMs. This release raises per-cell repeats from 3 to 10 and adds three harder NIAH variants: `style_aligned`, `numeric_confusable`, and `multi_key`.
>
> The repo ships the **full V2 result layer**: 3 models, 5 context lengths, 7 depth points, 10 repeats — **1,050 NIAH API calls + 64 multi-hop rows** — with summary tables, badcase taxonomy CSVs, and report figures under `results/v2/`.
>
> **Primary metric (Scheme A):** model capability stats use `eval_valid` samples only, excluding `content_filter` (platform moderation blocks) and `infra_api_failed` (billing exhaustion, rate limits, etc.). Those failures must not be counted as retrieval misses.

V1 baseline: [llm-long-context-eval-zh](https://github.com/melody-ling-L/llm-long-context-eval-zh)

---

## Quick Links

- Executed report: `results/v2/report/04_report_v2.executed.ipynb`
- Source notebook: `notebooks/v2/04_report_v2.ipynb`
- HTML release: [v2.0.0](https://github.com/melody-ling-L/llm-long-context-eval-zh-V2/releases/tag/v2.0.0)
- **Primary NIAH summary:** `results/v2/processed/summary_by_model_niah_valid_only.csv`
- Call-status diagnostics: `results/v2/processed/summary_call_status.csv`

---

## V2 Results

| DeepSeek | Kimi | Qwen |
|---|---|---|
| ![DeepSeek](results/v2/figures/niah_heatmap_deepseek.png) | ![Kimi](results/v2/figures/niah_heatmap_kimi.png) | ![Qwen](results/v2/figures/niah_heatmap_qwen.png) |

### NIAH Headline Metrics (`eval_valid`)

| Model | eval_valid / 350 | EM | Contains | 95% CI | Avg latency | Avg output tokens | Cost per hit |
|-------|:--:|:--:|:--------:|:------:|:-----------:|:-----------------:|:------------:|
| DeepSeek | 328 | 65.2% | **96.6%** | 94.1% - 98.1% | **0.78s** | 5.1 | **¥0.0057** |
| Kimi | 319 | **89.7%** | 94.4% | 91.3% - 96.4% | 2.25s | 6.8 | ¥0.6388 |
| Qwen | 319 | 87.8% | 89.3% | 85.5% - 92.3% | 7.83s | 6.1 | ¥0.0397 |

> Averaging all 350 raw rows would deflate Kimi Contains to **86.0%** (31 `content_filter` blocks plus early 32K infra failures). **Do not use that as the headline.**

### Call Status

| Model | Total | eval_valid | content_filter | infra_api_failed |
|-------|:-----:|:----------:|:--------------:|:----------------:|
| DeepSeek | 350 | 328 (93.7%) | 0 | 22 (6.3%) |
| Kimi | 350 | 319 (91.1%) | **31 (8.9%)** | 0 |
| Qwen | 350 | 319 (91.1%) | 0 | 31 (8.9%) |

### Variant Breakdown (`eval_valid`)

| Model | style_aligned | numeric_confusable | multi_key |
|-------|:--:|:--:|:--:|
| DeepSeek | **100.0%** | 89.9% | **100.0%** |
| Kimi | **100.0%** | 82.9% | **100.0%** |
| Qwen | **100.0%** | **67.6%** | **100.0%** |

### Accuracy by Context Length (`eval_valid` Contains)

| Model | 2K | 4K | 8K | 16K | 32K |
|-------|:--:|:--:|:--:|:--:|:--:|
| DeepSeek | 97.1% | 98.4% | 95.1% | 93.8% | 98.6% |
| Kimi | 90.0% | 90.5% | 95.1% | 96.9% | **100.0%** |
| Qwen | 87.1% | 87.3% | 86.9% | 90.6% | 95.1% |

### Key Findings

- **DeepSeek leads on Contains (96.6%) and cost efficiency (¥0.0057 / hit)** under the `eval_valid` primary metric.
- **Kimi 32K is not a model collapse.** The earlier "0% at 32K" narrative came from Moonshot **billing exhaustion** (`prompt_tokens=0`) plus **content_filter** blocks. On 61 valid 32K samples, Kimi Contains is **100.0%**.
- **`numeric_confusable` remains the hardest variant** — especially for Qwen (67.6%).
- **Most badcases are format noise, not retrieval failure:** 66.1% are "verbose output but contains the correct answer"; 33.9% are "confused by similar numbers."
- **Always persist `error` and token counts** and separate failure types; otherwise billing failures look like "lost in the middle."

### multi-hop Pilot

| Model | N | EM | Contains | Notes |
|-------|:--:|:--:|:--------:|-------|
| DeepSeek | 32 | 43.8% | 65.6% | 2-hop 74.1%, 3-hop 20.0% |
| Qwen | 32 | 68.8% | 68.8% | 2-hop 74.1%, 3-hop 40.0% |
| Kimi | — | — | — | Not run yet |

---

## Reproduce

```bash
pip install -r requirements.txt
cp .env.example .env   # DEEPSEEK_API_KEY / MOONSHOT_API_KEY / DASHSCOPE_API_KEY
python src/data_prep_v2.py
# notebooks/v2/02_eval_runner_v2.ipynb
python scripts/rerun_kimi_v2.py --analyze-only
python scripts/regenerate_v2_figures.py
```

> Kimi NIAH requires **`MOONSHOT_API_KEY`** (`api.moonshot.cn`). `KIMI_API_KEY` is for the Coding Agent only.

---

## References

- [Lost in the Middle (Liu et al., 2023)](https://arxiv.org/abs/2307.03172)
- [RULER (Hsieh et al., 2024)](https://arxiv.org/abs/2404.06654)
- [Needle in a Haystack (Kamradt, 2023)](https://github.com/gkamradt/LLMTest_NeedleInAHaystack)

# LLM Long-Context Evaluation Framework V2

[中文 README](README.md)

This repository is the dedicated V2 release of the Chinese long-context benchmark.

Compared with V1, V2:

- increases repeats from 3 to 10,
- adds `style_aligned`, `numeric_confusable`, and `multi_key` NIAH variants,
- adds a formal `multi_hop` pilot slice to the unified report,
- tracks efficiency metrics such as output tokens and cost per correct hit,
- keeps all V2 datasets, notebooks, and results isolated under `data/processed/v2`, `notebooks/v2`, and `results/v2`.

The current public snapshot now includes **1050 NIAH results + 12 formal multi-hop pilot results**, plus processed taxonomy CSVs that expose where models fail rather than only whether they fail.

## View On GitHub

- GitHub-rendered report: [`results/v2/report/04_report_v2.executed.ipynb`](results/v2/report/04_report_v2.executed.ipynb)
- Source notebook: [`notebooks/v2/04_report_v2.ipynb`](notebooks/v2/04_report_v2.ipynb)
- HTML download: [`v2.0.0 HTML report`](https://github.com/melody-ling-L/llm-long-context-eval-zh-V2/releases/download/v2.0.0/llm-long-context-eval-zh-V2-report.html)
- Badcase taxonomy summary: [`results/v2/processed/summary_by_badcase_taxonomy.csv`](results/v2/processed/summary_by_badcase_taxonomy.csv)
- Task-level summary: [`results/v2/processed/summary_by_model_task.csv`](results/v2/processed/summary_by_model_task.csv)

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
- `numeric_confusable` is the hardest V2 variant across models, and should be treated as a headline robustness finding rather than a side detail.
- Badcase taxonomy now turns V2 from a pure benchmark snapshot into an optimization asset: the single largest failure bucket is "verbose but still contains the answer" (35.1%), while the main retrieval-robustness gaps are "confused by similar numbers" (32.0%) and "fails under multi-key conditions" (17.4%).
- Kimi does not just wobble at 32K: its Contains drops to 0.0%, and the Wilson 95% CI upper bound is only 5.2%, which looks much closer to a stable failure signal.
- Multi-hop is no longer only a prepared dataset. It is now included as a formal real-task pilot slice in the same report, with 12 evaluated rows in total and all three models currently sitting at 50.0% Contains under wide confidence intervals.
- 16K vs 32K no longer shows a single shared trend: DeepSeek rebounds at 32K, Qwen stays broadly stable, and Kimi collapses.

## Badcase Taxonomy Headline

| Error Type | Share of All Badcases | Homepage Interpretation |
|---|---:|---|
| Verbose but contains the correct answer | **35.1%** | DeepSeek's main weakness looks more like extraction / answer-format control than raw retrieval failure. |
| Confused by similar numbers | **32.0%** | Similar percentages, dates, units, and nearby numeric cues are the single highest-value next data augmentation target. |
| Fails under multi-key conditions | 17.4% | Models still struggle when the target and distractors coexist, with the largest concentration on Kimi. |

Model-level taxonomy breakdown: [`results/v2/processed/summary_by_model_badcase_taxonomy.csv`](results/v2/processed/summary_by_model_badcase_taxonomy.csv)

## Multi-hop Pilot

| Model | N | EM | Contains | 95% CI | Note |
|---|---:|---:|---:|---:|---|
| DeepSeek | 4 | 50.0% | 50.0% | 15.0% - 85.0% | Lowest multi-hop cost per hit in the pilot slice. |
| Kimi | 4 | 25.0% | 50.0% | 15.0% - 85.0% | Can often hit the answer span, but exact formatting is less stable. |
| Qwen | 4 | 50.0% | 50.0% | 15.0% - 85.0% | Close to DeepSeek on this pilot, but at higher cost. |

This is already part of the formal report, but it should still be read as a real-task pilot slice rather than a final cross-model ranking. Task-level summary: [`results/v2/processed/summary_by_model_task.csv`](results/v2/processed/summary_by_model_task.csv)

## Actionable Assets

- Overall badcase taxonomy: [`results/v2/processed/summary_by_badcase_taxonomy.csv`](results/v2/processed/summary_by_badcase_taxonomy.csv)
- Per-model badcase taxonomy: [`results/v2/processed/summary_by_model_badcase_taxonomy.csv`](results/v2/processed/summary_by_model_badcase_taxonomy.csv)
- Representative badcase examples: [`results/v2/processed/badcase_examples.csv`](results/v2/processed/badcase_examples.csv)
- Real-task subset roadmap: [`results/v2/processed/real_task_subset_roadmap.csv`](results/v2/processed/real_task_subset_roadmap.csv)

## Main Figures

- `results/v2/figures/niah_heatmap_deepseek.png`
- `results/v2/figures/niah_heatmap_kimi.png`
- `results/v2/figures/niah_heatmap_qwen.png`
- `results/v2/figures/accuracy_by_length_with_ci.png`
- `results/v2/figures/efficiency_tradeoff.png`

## Main Artifacts

- `results/v2/raw/raw_results.csv`
- `results/v2/processed/scored_results.csv`
- `results/v2/processed/summary_by_model.csv`
- `results/v2/processed/summary_by_model_variant.csv`
- `results/v2/processed/summary_by_model_length.csv`
- `results/v2/processed/summary_by_model_task.csv`
- `results/v2/processed/summary_by_model_badcase_taxonomy.csv`
- `results/v2/processed/summary_by_badcase_taxonomy.csv`
- `results/v2/processed/badcase_examples.csv`
- `results/v2/processed/real_task_subset_roadmap.csv`
- `results/v2/figures/*.png`

## Reproduce

Run the V2 notebooks in order:

```text
notebooks/v2/01_data_preparation_v2.ipynb
notebooks/v2/02_eval_runner_v2.ipynb
notebooks/v2/03_analysis_visualization_v2.ipynb
notebooks/v2/04_report_v2.ipynb
```

## Current Limits

- `multi_hop` is now part of the formal report, but it still has only 12 evaluated rows in total, so it should be treated as a pilot slice rather than a stable benchmark.
- The repository reflects one public V2 snapshot; the next meaningful extension is to scale the real-task slice from 4 samples per model to 30-50 samples.
- Kimi's 32K failure now looks real enough to discuss directly, but root-cause analysis still needs a separate interface / prompting / context-handling audit.
- The current badcase taxonomy is intentionally pragmatic and heuristic; a stronger next step is to split it into finer subtypes such as wrong target value, unit confusion, and time-reasoning failure.

## References

- [Lost in the Middle (Liu et al., 2023)](https://arxiv.org/abs/2307.03172)
- [RULER: What's the Real Context Window of Your LLM? (Hsieh et al., 2024)](https://arxiv.org/abs/2404.06654)
- [Needle in a Haystack (Kamradt, 2023)](https://github.com/gkamradt/LLMTest_NeedleInAHaystack)

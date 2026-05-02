# LLM 长上下文能力评测框架 V2

[![Lint](https://github.com/melody-ling-L/llm-long-context-eval-zh-V2/actions/workflows/lint.yml/badge.svg)](https://github.com/melody-ling-L/llm-long-context-eval-zh-V2/actions/workflows/lint.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![V2 Samples](https://img.shields.io/badge/v2_samples-1050-blue)](#v2-results)
[![Models](https://img.shields.io/badge/models-3-green)](#v2-results)
[![Repeats](https://img.shields.io/badge/repeats-10-orange)](#methodology)
[![Status](https://img.shields.io/badge/status-v2_published-success)](#v2-results)

> 面向中文长上下文场景的 **V2 基准仓库**，在 V1 的基础上把重复数从 3 提升到 10，并引入 `style_aligned`、`numeric_confusable`、`multi_key` 三类更难的 NIAH 变体。
>
> 当前仓库已经包含 **完整 V2 结果**：3 个模型、5 个上下文长度、7 个深度点、10 次重复，共 **1050 条有效 NIAH 评测结果**，并附带 `results/v2/` 下的汇总表和图表。

V1 基线仓库见：[llm-long-context-eval-zh](https://github.com/melody-ling-L/llm-long-context-eval-zh)

---

## V2 Results

| DeepSeek | Kimi | Qwen |
|---|---|---|
| ![DeepSeek V2 Heatmap](results/v2/figures/niah_heatmap_deepseek.png) | ![Kimi V2 Heatmap](results/v2/figures/niah_heatmap_kimi.png) | ![Qwen V2 Heatmap](results/v2/figures/niah_heatmap_qwen.png) |

| Accuracy by Length | Efficiency Tradeoff |
|---|---|
| ![Accuracy by Length](results/v2/figures/accuracy_by_length.png) | ![Efficiency Tradeoff](results/v2/figures/efficiency_tradeoff.png) |

### Headline Metrics

| 模型 | N | EM | Contains | 95% CI | 平均延迟 | 平均输出 tokens | 单位命中成本 |
|---|---:|---:|---:|---:|---:|---:|---:|
| DeepSeek | 350 | 61.1% | **90.6%** | 87.1% - 93.2% | **0.73s** | 4.8 | **¥0.0057 / hit** |
| Kimi | 350 | 58.9% | 63.1% | 58.0% - 68.0% | 1.06s | **4.5** | ¥0.3919 / hit |
| Qwen | 350 | **80.0%** | 81.4% | 77.0% - 85.2% | 7.14s | 5.5 | ¥0.0397 / hit |

### Variant Breakdown

| 模型 | style_aligned | numeric_confusable | multi_key |
|---|---:|---:|---:|
| DeepSeek | **94.0%** | 86.0% | 91.7% |
| Kimi | 69.8% | 53.5% | 65.8% |
| Qwen | 89.7% | 62.3% | **91.7%** |

### Key Findings

- **DeepSeek 在 V2 中拿到了最高的 Contains 和最低的单位命中成本。** 90.6% 的 Contains 配合 ¥0.0057 / hit，使它成为当前这版 V2 中最强的综合效率模型。
- **Qwen 的严格精度仍然最高，但效率明显弱于 DeepSeek。** 它的 EM 达到 80.0%，说明答案更短、更贴近标准字符串；但平均延迟和单位成本都更高。
- **Kimi 对更难变体和更长长度更脆弱。** `numeric_confusable` 是三类变体里最难的，而 Kimi 在 32K 上已经出现明显塌陷，当前 32K 汇总为 0.0%。
- **16K / 32K 在 V2 中不再表现为“所有模型统一退化”。** DeepSeek 在 32K 出现强反弹，Qwen 在 16K 和 32K 持平，Kimi 则在 32K 崩塌。这说明更高重复数确实把“模型差异”放大了出来。

---

## Methodology

V2 相比 V1 的关键变化：

1. 将单格重复数从 3 提高到 10，使 `context_length × depth_pct` 的统计更稳。
2. 引入三类更难的中文 NIAH 变体：
   - `style_aligned`：needle 与上下文文风更接近。
   - `numeric_confusable`：存在多个相近数字或近义指标，不能靠关键词秒取。
   - `multi_key`：同时插入 target 和 distractor，需要做更精细的定位。
3. 增加 V2 效率指标：`response_chars`、`completion_tokens`、`row_cost_cny`、`cost_per_contains_hit_cny`、`contains_per_1k_output_tokens`。
4. 所有 V2 数据、结果和 notebook 都与 V1 隔离，避免覆盖既有结论。

本轮完整 V2 NIAH 规模为：

- 3 个模型：DeepSeek / Kimi / Qwen
- 5 个长度：2K / 4K / 8K / 16K / 32K
- 7 个深度点：0 / 10 / 25 / 50 / 75 / 90 / 100
- 10 次重复
- 合计 350 条样本 / 模型，1050 条评测结果

---

## Repository Layout

```text
llm-long-context-eval-zh-V2/
├── configs/
│   ├── eval_config.yaml
│   └── eval_config_v2.yaml
├── data/
│   ├── needles/
│   │   ├── multihop_qa.json
│   │   ├── multihop_qa_v2.json
│   │   └── v2_needle_bank.json
│   ├── processed/
│   └── processed/v2/
├── docs/
│   ├── eval_design.md
│   └── eval_design_v2.md
├── notebooks/
│   ├── 01_data_preparation.ipynb
│   ├── 02_eval_runner.ipynb
│   ├── 03_analysis_visualization.ipynb
│   ├── 04_report.ipynb
│   └── v2/
├── results/
│   ├── figures/
│   ├── processed/
│   ├── raw/
│   └── v2/
│       ├── figures/
│       ├── processed/
│       └── raw/
└── src/
	├── data_prep.py
	├── data_prep_v2.py
	├── eval_runner.py
	├── eval_runner_v2.py
	├── metrics.py
	├── metrics_v2.py
	└── visualize.py
```

---

## Reproduce V2

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
# fill in DEEPSEEK_API_KEY / MOONSHOT_API_KEY / DASHSCOPE_API_KEY
```

### 3. Generate V2 datasets

```bash
python src/data_prep_v2.py
```

或直接运行：

```text
notebooks/v2/01_data_preparation_v2.ipynb
```

### 4. Run V2 evaluation

```text
notebooks/v2/02_eval_runner_v2.ipynb
```

### 5. Run V2 analysis and report

```text
notebooks/v2/03_analysis_visualization_v2.ipynb
notebooks/v2/04_report_v2.ipynb
```

V2 关键产物路径：

- `results/v2/raw/raw_results.csv`
- `results/v2/processed/scored_results.csv`
- `results/v2/processed/summary_by_model.csv`
- `results/v2/processed/summary_by_model_variant.csv`
- `results/v2/processed/summary_by_model_length.csv`
- `results/v2/figures/*.png`

---

## Current Limits

- `multi_hop` 数据集已经生成到 `data/processed/v2/multihop_dataset.jsonl`，但当前对外主结论仍以 NIAH 为主。
- Kimi 在 32K 的结果当前极差，这很可能是真实退化，也可能意味着该模型需要进一步单独排查接口或上下文策略。
- 这版已经比 V1 稳很多，但仍是单轮公开快照；更完整的下一步应该是补齐 multi-hop 结果，并把跨任务摘要纳入同一份报告。

---

## References

- [Lost in the Middle (Liu et al., 2023)](https://arxiv.org/abs/2307.03172)
- [RULER: What's the Real Context Window of Your LLM? (Hsieh et al., 2024)](https://arxiv.org/abs/2404.06654)
- [Needle in a Haystack (Kamradt, 2023)](https://github.com/gkamradt/LLMTest_NeedleInAHaystack)
# LLM 长上下文能力评测框架

[![Lint](https://github.com/melody-ling-L/llm-long-context-eval-zh/actions/workflows/lint.yml/badge.svg)](https://github.com/melody-ling-L/llm-long-context-eval-zh/actions/workflows/lint.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Samples](https://img.shields.io/badge/samples-315-blue)](#最终结果--final-v1)
[![Models](https://img.shields.io/badge/models-3-green)](#最终结果--final-v1)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)](#最终结果--final-v1)
[![Budget](https://img.shields.io/badge/budget-¥5~15%2Fmodel-orange)](#预算估算)
[![Status](https://img.shields.io/badge/status-final_v1-success)](#最终结果--final-v1)

> 面向中文长上下文场景的 NIAH / 位置偏差评测框架，用于验证 **"Lost in the Middle"** 是否稳定出现，以及不同模型是否真的能把长上下文用起来。
>
> 当前 README 展示的是 **final v1** 结果：已完成 **315 / 315** 条有效样本，覆盖率 **100%**。这版结论可以作为项目定稿发布；下一步优化重点不再是“补齐数据”，而是提升统计置信度和评测难度。

---

## 最终结果 / Final v1

| DeepSeek-V3 | Kimi | Qwen-Long |
|---|---|---|
| ![DeepSeek Heatmap](results/figures/niah_heatmap_deepseek.png) | ![Kimi Heatmap](results/figures/niah_heatmap_kimi.png) | ![Qwen Heatmap](results/figures/niah_heatmap_qwen.png) |

本轮完整评测共 **315 条有效样本**：3 个模型 × 5 个上下文长度 × 7 个深度点 × 3 次重复。每个模型在每个 `context_length × depth_pct` 格子中都恰好有 **3 次重复**，数据已经齐平。

| 模型 | N | EM | Contains | Gap (Contains - EM) | 平均延迟 |
|------|:--:|:--:|:--------:|:-------------------:|:-------:|
| Qwen-Long | 105 | **80.0%** | **82.9%** | **2.9pp** | 1.10s |
| DeepSeek-V3 | 105 | 64.8% | **82.9%** | 18.1pp | **1.01s** |
| Kimi (Moonshot) | 105 | 65.7% | 76.2% | 10.5pp | 1.70s |

### Key Findings

- **位置偏差被完整复现，但形状更接近 W 型而不是标准 U 型。** 整体准确率在 depth=0% / 10% 时最高（91.1% / 86.7%），在 50% 处降到最低点（73.3%），75% 仍处低位（75.6%），随后在 90%-100% 回升到 80.0%。
- **Qwen 的严格精度最高，DeepSeek 的综合效率最佳。** Qwen 的 EM 达到 80.0%，而 DeepSeek 用 1.01s 的平均延迟拿到了与 Qwen 持平的 Contains（82.9%）；如果业务更看重“答对且答得短”，Qwen 更稳，如果更看重吞吐与成本，DeepSeek 更实用。
- **Kimi 在长上下文下退化最明显。** Kimi 的 Contains 只有 76.2%，且在 8K 与 32K 场景都掉到 66.7%，同时平均延迟 1.70s，是三者中最慢的一档。
- **16K 是这一轮中文 NIAH 的共同峰值。** DeepSeek 与 Qwen 在 16K 都达到 95.2%，Kimi 也达到 90.5%；当窗口扩到 32K 后，三个模型都出现回落，说明“支持更长 context window”不等于“对更长上下文的稳定利用”。

## 实验局限 / Limitations

- 这版数据已经完整，但**每个格子仍只有 3 次重复**。它足以支撑 v1 的方向性结论，却不足以对局部异常点做强统计推断；下一版应把重复数提升到 `N >= 10`。
- 当前结果呈现 **W 型 / 双低谷结构**，而不是英文文献中的标准 U 型。这可能反映中文长文本的注意力分布差异，也可能仍受小样本波动影响，需要更高重复数才能做稳健判断。
- 这版 NIAH 的 needle 与 haystack 风格差异较大，模型可能部分依赖关键词检索，而不是真正的长程语义整合。下一版需要引入**风格对齐的 needle**和 **multi-key NIAH**，降低模式匹配带来的虚高准确率。
- EM 与 Contains 的差值不只是“评分松紧差异”，它也在测量模型的**答案简洁度**。后续版本应把答案长度、输出 token 成本与两类准确率一起纳入分析，而不只盯着正确率本身。

## V2 Roadmap

1. 把单格重复数从 3 提升到 10，收窄置信区间，验证 16K / 32K 段是否真的存在反弹或塌陷。
2. 引入风格对齐的 needle、真假难辨的数值 needle，以及 multi-key NIAH，降低关键词检索偏置。
3. 增加答案长度、输出 token、单位正确率成本等指标，把“答对”与“答得省”分开看。
4. 扩展多跳推理和跨领域文档，验证结论能否从 NIAH 泛化到更贴近真实业务的中文长文档场景。

---

## 项目简介

本项目评测主流 LLM（DeepSeek-V3、Kimi、Qwen-Long）在长上下文场景下的真实能力：
- 官宣支持 128K，但模型真的能**用**这 128K 吗？
- 信息藏在文档**中间**时，模型是否会"失忆"？

---

## 评测维度

| 维度 | 说明 | 关键指标 |
|---|---|---|
| **NIAH** | Needle in a Haystack，在不同位置插入关键信息 | Accuracy @depth × length |
| **多跳推理** | 信息分散在文档多处，需综合推理 | Multi-hop Accuracy |
| **位置偏差** | 信息在开头/中间/结尾的准确率差异 | Position Bias Score |
| **跨模型对比** | DeepSeek-V3 vs Kimi vs Qwen-Long | Δ Accuracy |

---

## 项目结构

```
Eval/
├── configs/
│   └── eval_config.yaml        # 模型配置、评测参数
├── data/
│   ├── raw/                    # 放入原始长文档 (.txt / .md)
│   ├── needles/                # 多跳推理 QA 标注文件
│   └── processed/              # 生成的数据集 .jsonl
├── src/
│   ├── data_prep.py            # 构造 NIAH / 多跳数据集
│   ├── eval_runner.py          # 调用模型 API，存储结果
│   ├── metrics.py              # EM / Contains 评分
│   └── visualize.py            # 热力图、折线图、位置偏差图
├── notebooks/
│   ├── 01_data_preparation.ipynb
│   ├── 02_eval_runner.ipynb
│   ├── 03_analysis_visualization.ipynb
│   └── 04_report.ipynb
├── results/
│   ├── raw/                    # 原始 API 结果 .csv
│   ├── processed/              # 评分后结果 .csv
│   └── figures/                # 可视化图表
├── docs/
│   └── eval_design.md          # 评测方案设计文档
├── .env.example                # API Key 配置模板
└── requirements.txt
```

---

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置 API Key
```bash
cp .env.example .env
# 编辑 .env，填入各模型 API Key
```

### 3. 准备数据
在 `data/raw/` 放入中文长文档（财报 PDF 转文本、论文、小说等），然后：
```bash
python src/data_prep.py
```

### 4. 运行评测（推荐在 Notebook 中逐步执行）
```
notebooks/01_data_preparation.ipynb  →  构造数据集
notebooks/02_eval_runner.ipynb       →  调用模型 API
notebooks/03_analysis_visualization.ipynb  →  分析 + 可视化
```

<details>
<summary>如何复现当前 final v1 结果</summary>

1. 运行 `notebooks/01_data_preparation.ipynb`，生成 `data/processed/niah_dataset.jsonl`。
2. 运行 `notebooks/02_eval_runner.ipynb`，保持 `RESUME=True`，直到 `results/raw/raw_results.csv` 达到 315 条目标样本。
3. 运行 `notebooks/03_analysis_visualization.ipynb`，确认 Step 1 输出 coverage = 100%，并生成 `results/figures/` 下的全部图表。
4. 最后运行 `notebooks/04_report.ipynb`，导出最终报告 HTML。

</details>

---

## 预算估算

| 模型 | 约 200 样本 × 平均 32K tokens |
|---|---|
| DeepSeek-V3 | ~¥5 |
| Kimi (moonshot-v1-128k) | ~¥15 |
| Qwen-Long | ~¥5 |

---

## 参考论文

- [Lost in the Middle (Liu et al., 2023)](https://arxiv.org/abs/2307.03172)
- [RULER: What's the Real Context Window of Your LLM? (Hsieh et al., 2024)](https://arxiv.org/abs/2404.06654)
- [Needle in a Haystack (Kamradt, 2023)](https://github.com/gkamradt/LLMTest_NeedleInAHaystack)

---

## 简历描述模板

> **LLM 长上下文能力评测项目** | 个人项目
> - 设计 4 维度评测框架（NIAH、多跳推理、位置偏差、跨模型对比），覆盖 200+ 测试样本
> - 在 DeepSeek-V3、Kimi、Qwen-Long 上定量验证 "Lost in the Middle" 在中文场景的表现
> - 输出位置-准确率热力图等可视化分析报告，[GitHub 链接]

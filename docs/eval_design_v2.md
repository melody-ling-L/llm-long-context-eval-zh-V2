# V2 评测设计

## 目标

V2 在不覆盖 V1 的前提下，验证四个问题：

1. 把单格重复数从 3 提升到 10 后，16K / 32K 的局部峰谷是否仍然存在。
2. 当 needle 与 haystack 文风更接近时，模型是否还能保持 V1 的准确率。
3. 当上下文里同时存在多个相似候选信息时，模型是否会被干扰。
4. 在“答对”之外，模型是否还能“答得省”，即更短输出、更低 completion token、更低单位正确率成本。

## 与 V1 的隔离策略

- V1 路径保持不变：`data/processed/`、`results/raw/`、`results/processed/`、`results/figures/`
- V2 单独使用：`data/processed/v2/`、`results/v2/raw/`、`results/v2/processed/`、`results/v2/figures/`
- V1 notebook 保持原样；V2 在 `notebooks/v2/` 下提供独立副本。
- V1 README 继续展示 final v1；V2 先在 notebook 和文档内迭代，稳定后再决定是否单独写报告页。

## V2 核心变更

### 1. 更高重复数

- `num_samples_per_config = 10`
- 每个 `context_length × depth_pct` 组合都做 10 次采样
- 目标是为热力图格子和 16K / 32K 波动提供更稳定的置信区间

### 2. 更难的 NIAH 变体

- `style_aligned`: needle 文风与正文更一致
- `numeric_confusable`: 同一句里放入多个近似数字，问题只指向其中一个
- `multi_key`: 在同一上下文插入 1 个目标 needle + 2 个干扰 needle

### 3. 更丰富的分析指标

- `response_chars`: 回答长度
- `completion_tokens`: 输出 token
- `row_cost_cny`: 单条样本估算成本
- `contains_per_cny`: 单位成本正确率
- `contains_per_1k_output_tokens`: 单位输出 token 正确率

### 4. 扩展任务

- 保留 NIAH 作为主任务
- 新增 `multihop_qa_v2.json` 作为 V2 多跳样本起点
- 通过 `domain` 字段把 finance / manufacturing / healthcare / retail 区分开

## 建议执行顺序

1. 先运行 `notebooks/v2/01_data_preparation_v2.ipynb` 构建 V2 数据集
2. 再运行 `notebooks/v2/02_eval_runner_v2.ipynb` 完成 V2 评测
3. 然后在 `notebooks/v2/03_analysis_visualization_v2.ipynb` 看变体与效率指标
4. 最后在 `notebooks/v2/04_report_v2.ipynb` 写 V2 报告

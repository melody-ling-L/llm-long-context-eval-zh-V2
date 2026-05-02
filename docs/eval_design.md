# 评测方案设计文档

## 核心问题

> 模型官宣支持 128K 上下文，但真的能"用"这 128K 吗？
> 当关键信息位于文档**中间**时，模型是否会"丢失"它？

---

## 参考论文

| 论文 | 核心发现 | 与本项目的关系 |
|---|---|---|
| [Lost in the Middle (Liu et al., 2023)](https://arxiv.org/abs/2307.03172) | 信息位置严重影响 LLM 检索准确率，中间位置最差 | 本项目的核心验证方向 |
| [RULER (Hsieh et al., 2024)](https://arxiv.org/abs/2404.06654) | 大多数模型声称的上下文窗口远大于有效利用范围 | 多维度测试框架参考 |
| [Needle in a Haystack (Kamradt, 2023)](https://github.com/gkamradt/LLMTest_NeedleInAHaystack) | 业界标准长文本评测范式 | NIAH 实现参考 |

---

## 评测维度设计

### 维度 1：NIAH（Needle in a Haystack）

**实验设计**：
- 在中文长文档中，以不同深度（0%~100%）插入一句不相关的关键信息（"针"）
- 要求模型从文档中提取该信息
- 遍历所有 (上下文长度 × 深度) 组合

**变量**：
- 上下文长度：2K / 4K / 8K / 16K / 32K / 64K 字符
- 深度：0% / 10% / 25% / 50% / 75% / 90% / 100%

**指标**：Contains Accuracy（输出包含标准答案则得 1 分）

**可视化**：热力图（行=长度，列=深度，颜色=准确率）

---

### 维度 2：多跳推理

**实验设计**：
- 信息分散在文档多个位置（如：人物 A 的年龄在第 1 段，工作在第 8 段）
- 问题需要综合多处信息才能回答

**难点**：需要手动标注 QA 对，放在 `data/needles/multihop_qa.json`

**指标**：Exact Match / Contains Accuracy

---

### 维度 3：位置偏差分析

**实验设计**：
- 将 NIAH 结果按深度分三段：开头（0-20%）/ 中间（20-70%）/ 结尾（70-100%）
- 比较三段的准确率均值

**预期发现**：中间段准确率 < 开头/结尾，验证"Lost in the Middle"现象

**可视化**：分组柱状图

---

### 维度 4：跨模型对比

**待测模型**：

| 模型 | API | 上下文窗口 | 定价（大约） |
|---|---|---|---|
| DeepSeek-V3 | deepseek-chat | 64K | ¥1/M tokens |
| Kimi (Moonshot) | moonshot-v1-128k | 128K | ¥12/M tokens |
| Qwen-Long | qwen-long | 1M | ¥4/M tokens |

**分析维度**：在相同测试条件下，哪个模型的"有效上下文窗口"最大？

---

## 评分体系

| 指标 | 计算方式 | 备注 |
|---|---|---|
| Exact Match (EM) | 标准化后完全匹配 | 严格，用于短答案 |
| Contains Match | 标准答案是否出现在输出中 | 宽松，主要指标 |

**标准化规则**：去除空白、全角转半角

---

## 数据规格

### NIAH 数据集格式（每行 JSON）

```json
{
  "task": "niah",
  "context_length": 8000,
  "depth_pct": 50,
  "context": "...(文档内容，含插入的 needle)...",
  "question": "会议室临时预订密码是什么？",
  "answer": "Rainbow-512",
  "needle": "会议室的临时预订密码已更新为 Rainbow-512。",
  "insert_char_pos": 4123
}
```

### 结果 CSV 字段

| 字段 | 说明 |
|---|---|
| model | 模型名 |
| task | 任务类型 |
| context_length | 上下文长度（字符） |
| depth_pct | needle 深度（%） |
| question | 问题 |
| expected_answer | 标准答案 |
| model_response | 模型输出 |
| tokens_used | 消耗 token 数 |
| latency_s | 响应延迟（秒） |
| em_score | Exact Match（0/1） |
| contains_score | Contains Match（0/1） |

---

## 预算控制

| 阶段 | 样本数 | 估算费用 |
|---|---|---|
| 调试（仅 DeepSeek） | 20 条 × 短上下文 | < ¥0.1 |
| 正式跑（仅 DeepSeek） | ~200 条 | ~ ¥5 |
| 加入 Kimi 对比 | ~200 条 | ~ ¥15 |
| 加入 Qwen-Long | ~200 条 | ~ ¥5 |

"""
数据准备模块

功能：
1. 加载 data/raw/ 下的长文档
2. 构造 NIAH（Needle in a Haystack）测试样本
3. 构造多跳推理测试样本
4. 输出标准数据集 data/processed/*.jsonl

用法：
    python src/data_prep.py
"""

import json
import random
import re
from pathlib import Path

import yaml


# ──────────────────────────────────────────────
# 内置 Needle 列表（可在 data/needles/ 中扩展）
# ──────────────────────────────────────────────

NEEDLES_ZH = [
    {
        "needle": "张伟的私人银行账户密码是 X7K9-BLUE-2024。",
        "question": "张伟的私人银行账户密码是什么？",
        "answer": "X7K9-BLUE-2024",
    },
    {
        "needle": "公司今年第三季度净利润为 47.3 亿元人民币。",
        "question": "公司今年第三季度净利润是多少？",
        "answer": "47.3亿元人民币",
    },
    {
        "needle": "会议室的临时预订密码已更新为 Rainbow-512。",
        "question": "会议室临时预订密码是什么？",
        "answer": "Rainbow-512",
    },
    {
        "needle": "内部项目代号为\u201c暗星计划\u201d，正式启动日期为 2024 年 11 月 8 日。",
        "question": "内部项目代号是什么，启动日期是哪天？",
        "answer": "暗星计划，2024年11月8日",
    },
    {
        "needle": "李明的员工编号为 EMP-2024-08831。",
        "question": "李明的员工编号是多少？",
        "answer": "EMP-2024-08831",
    },
    {
        "needle": "数据中心备用电源的启动口令是 GoldenKey-7749。",
        "question": "数据中心备用电源的启动口令是什么？",
        "answer": "GoldenKey-7749",
    },
    {
        "needle": "本次合并的换股比例为每 3 股 A 公司股票换 1 股 B 公司股票。",
        "question": "本次合并的换股比例是多少？",
        "answer": "每3股A公司股票换1股B公司股票",
    },
    {
        "needle": "首席技术官王磊的直线电话是 010-88887777 转 301。",
        "question": "首席技术官王磊的直线电话是多少？",
        "answer": "010-88887777转301",
    },
]


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def load_document(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def truncate_to_chars(text: str, target_chars: int) -> str:
    """截断文档到 target_chars 字符，在句子边界处截断避免破坏语义。"""
    if len(text) <= target_chars:
        return text
    truncated = text[:target_chars]
    # 从截断点往回找最近的句子边界
    for i in range(len(truncated) - 1, max(0, len(truncated) - 300), -1):
        if truncated[i] in ("。", "\n", "！", "？", ".", "!", "?"):
            return truncated[: i + 1]
    return truncated


def insert_needle(document: str, needle: str, depth_pct: float) -> tuple:
    """
    在文档的指定深度百分比位置插入 needle。

    Args:
        document:  原始文档文本
        needle:    要插入的关键信息句
        depth_pct: 0.0 = 文档开头，1.0 = 文档结尾

    Returns:
        (modified_document, insertion_char_pos)
    """
    chars = len(document)
    target_pos = int(chars * depth_pct)

    # 在 target_pos 附近 ±150 字符内找句子边界
    search_start = max(0, target_pos - 150)
    search_end = min(chars, target_pos + 150)
    segment = document[search_start:search_end]

    boundary = target_pos  # 默认直接插入
    for i, ch in enumerate(segment):
        if ch in ("。", "\n", "！", "？", ".", "!", "?"):
            candidate = search_start + i + 1
            if candidate <= target_pos:
                boundary = candidate

    modified = document[:boundary] + "\n" + needle + "\n" + document[boundary:]
    return modified, boundary


# ──────────────────────────────────────────────
# NIAH 数据集构造
# ──────────────────────────────────────────────

def build_niah_samples(
    documents: list,
    context_lengths: list,
    depth_percentages: list,
    needles: list = None,
    samples_per_config: int = 1,
    seed: int = 42,
) -> list:
    """
    生成 NIAH 测试样本。

    每个样本包含：
        task, context_length, depth_pct, context, question, answer, needle

    Returns:
        list of dict
    """
    if needles is None:
        needles = NEEDLES_ZH

    random.seed(seed)
    samples = []

    for ctx_len in context_lengths:
        for depth_pct in depth_percentages:
            for _ in range(samples_per_config):
                doc = random.choice(documents)
                needle_item = random.choice(needles)

                # 截断文档（预留 needle + 少量 padding 的空间）
                base_doc = truncate_to_chars(
                    doc, ctx_len - len(needle_item["needle"]) - 100
                )

                modified_doc, insert_pos = insert_needle(
                    base_doc, needle_item["needle"], depth_pct / 100.0
                )

                samples.append(
                    {
                        "task": "niah",
                        "context_length": ctx_len,
                        "depth_pct": depth_pct,
                        "context": modified_doc,
                        "question": needle_item["question"],
                        "answer": needle_item["answer"],
                        "needle": needle_item["needle"],
                        "insert_char_pos": insert_pos,
                    }
                )

    return samples


# ──────────────────────────────────────────────
# 多跳推理数据集（从标注文件加载）
# ──────────────────────────────────────────────

def build_multihop_samples(needles_dir: str) -> list:
    """
    从 data/needles/multihop_qa.json 加载多跳推理样本。

    文件格式（每条）：
    {
        "context": "...",
        "question": "...",
        "answer": "...",
        "hops": 2
    }
    """
    qa_path = Path(needles_dir) / "multihop_qa.json"
    if not qa_path.exists():
        print(f"⚠️  未找到多跳 QA 文件: {qa_path}，跳过多跳推理数据集")
        return []

    with open(qa_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    samples = []
    for item in raw:
        samples.append(
            {
                "task": "multi_hop",
                "context_length": len(item.get("context", "")),
                "depth_pct": None,
                "context": item["context"],
                "question": item["question"],
                "answer": item["answer"],
                "hops": item.get("hops", 2),
            }
        )
    return samples


# ──────────────────────────────────────────────
# I/O
# ──────────────────────────────────────────────

def save_jsonl(samples: list, output_path: str):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
    print(f"✅ 保存 {len(samples)} 条样本 → {output_path}")


def load_jsonl(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────

def main():
    config = yaml.safe_load(open("configs/eval_config.yaml", encoding="utf-8"))

    raw_dir = Path(config["data"]["raw_dir"])
    doc_files = sorted(raw_dir.glob("*.txt")) + sorted(raw_dir.glob("*.md"))

    if not doc_files:
        print(
            "⚠️  data/raw/ 下没有找到文档。\n"
            "请将中文长文档（.txt 或 .md）放入 data/raw/ 后重新运行。\n"
            "推荐来源：上市公司年报、学术论文、中文小说等，单篇建议 > 10 万字符。"
        )
        return

    documents = [load_document(str(f)) for f in doc_files]
    total_chars = sum(len(d) for d in documents)
    print(f"✅ 加载 {len(documents)} 篇文档，总字符数: {total_chars:,}")

    # 1. NIAH
    niah_samples = build_niah_samples(
        documents=documents,
        context_lengths=config["eval"]["context_lengths"],
        depth_percentages=config["eval"]["depth_percentages"],
        samples_per_config=config["eval"]["niah"]["num_samples_per_config"],
    )
    save_jsonl(niah_samples, f"{config['data']['processed_dir']}/niah_dataset.jsonl")

    # 2. 多跳推理
    multihop_samples = build_multihop_samples(config["data"]["needles_dir"])
    if multihop_samples:
        save_jsonl(
            multihop_samples,
            f"{config['data']['processed_dir']}/multihop_dataset.jsonl",
        )

    print(
        f"\n📊 数据集生成完毕："
        f"\n   NIAH:     {len(niah_samples)} 条"
        f"\n   多跳推理: {len(multihop_samples)} 条"
        f"\n\n下一步：运行 notebooks/02_eval_runner.ipynb 开始评测"
    )


if __name__ == "__main__":
    main()

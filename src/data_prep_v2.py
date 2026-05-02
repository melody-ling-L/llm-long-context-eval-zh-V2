"""V2 数据准备模块。

目标：
- 保留 V1 数据准备逻辑不变
- 为 V2 引入 style-aligned / numeric-confusable / multi-key NIAH
- 扩展多跳与跨领域样本，统一写入 data/processed/v2/
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Iterable

import yaml

from src.data_prep import (
    insert_needle,
    load_document,
    save_jsonl,
    truncate_to_chars,
)


def load_documents(raw_dir: str | Path) -> list[str]:
    raw_path = Path(raw_dir)
    doc_files = sorted(raw_path.glob("*.txt")) + sorted(raw_path.glob("*.md"))
    return [load_document(str(path)) for path in doc_files]


def load_needle_bank(path: str | Path, variants: Iterable[str] | None = None) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        bank = json.load(f)
    if variants is None:
        return bank
    variant_set = set(variants)
    return [item for item in bank if item.get("variant") in variant_set]


def _target_and_distractor_depths(depth_pct: float, distractor_count: int) -> list[float]:
    if distractor_count <= 0:
        return [depth_pct]

    candidate_offsets = [-35, 30, -20, 18]
    depths = [depth_pct]
    for offset in candidate_offsets:
        if len(depths) >= distractor_count + 1:
            break
        candidate = min(95, max(5, depth_pct + offset))
        if all(abs(candidate - existing) >= 12 for existing in depths):
            depths.append(candidate)
    while len(depths) < distractor_count + 1:
        candidate = min(95, max(5, depth_pct + (len(depths) * 9)))
        depths.append(candidate)
    return depths[: distractor_count + 1]


def insert_multi_key_needles(document: str, entry: dict, depth_pct: float) -> tuple[str, int, list[dict]]:
    target = {"role": "target", "text": entry["needle"], "depth_pct": depth_pct}
    distractors = [
        {"role": "distractor", "text": text}
        for text in entry.get("distractor_needles", [])
    ]
    all_items = [target] + distractors
    planned_depths = _target_and_distractor_depths(depth_pct, len(distractors))
    all_items[0]["depth_pct"] = planned_depths[0]
    for item, planned in zip(all_items[1:], planned_depths[1:]):
        item["depth_pct"] = planned

    modified = document
    inserted_meta = []
    for item in sorted(all_items, key=lambda x: x["depth_pct"]):
        modified, insert_pos = insert_needle(modified, item["text"], item["depth_pct"] / 100.0)
        inserted_meta.append(
            {
                "role": item["role"],
                "text": item["text"],
                "depth_pct": item["depth_pct"],
                "insert_char_pos": insert_pos,
            }
        )

    target_insert = next(meta["insert_char_pos"] for meta in inserted_meta if meta["role"] == "target")
    return modified, target_insert, inserted_meta


def build_v2_niah_samples(
    documents: list[str],
    context_lengths: list[int],
    depth_percentages: list[int],
    needle_bank: list[dict],
    samples_per_config: int = 10,
    seed: int = 2026,
) -> list[dict]:
    rng = random.Random(seed)
    by_variant: dict[str, list[dict]] = {}
    for item in needle_bank:
        by_variant.setdefault(item["variant"], []).append(item)
    variants = list(by_variant)

    samples = []
    variant_counter = Counter()

    for context_length in context_lengths:
        for depth_pct in depth_percentages:
            for repeat_idx in range(samples_per_config):
                variant = variants[(repeat_idx + context_length + depth_pct) % len(variants)]
                entry = rng.choice(by_variant[variant])

                num_needles = 1 + len(entry.get("distractor_needles", []))
                reserved_chars = sum(len(text) for text in [entry["needle"], *entry.get("distractor_needles", [])])
                required_chars = max(800, context_length - reserved_chars - num_needles * 80)
                candidate_docs = [doc for doc in documents if len(doc) >= required_chars]
                if not candidate_docs:
                    raise ValueError(
                        f"没有足够长的原始文档来构造 {context_length} chars 的 V2 样本；"
                        f"至少需要 {required_chars} chars 的原始文档。"
                    )
                base_doc = truncate_to_chars(rng.choice(candidate_docs), required_chars)

                if variant == "multi_key":
                    modified_doc, insert_pos, inserted_meta = insert_multi_key_needles(base_doc, entry, depth_pct)
                else:
                    modified_doc, insert_pos = insert_needle(base_doc, entry["needle"], depth_pct / 100.0)
                    inserted_meta = [
                        {
                            "role": "target",
                            "text": entry["needle"],
                            "depth_pct": depth_pct,
                            "insert_char_pos": insert_pos,
                        }
                    ]

                variant_counter[variant] += 1
                samples.append(
                    {
                        "sample_id": f"v2-niah-{context_length}-{depth_pct}-{repeat_idx:02d}-{entry['id']}",
                        "experiment": "v2",
                        "task": "niah",
                        "variant": variant,
                        "needle_style": variant,
                        "domain": entry.get("domain", "general"),
                        "difficulty": entry.get("difficulty", "medium"),
                        "answer_type": entry.get("answer_type", "short_span"),
                        "context_length": context_length,
                        "depth_pct": depth_pct,
                        "context": modified_doc,
                        "question": entry["question"],
                        "answer": entry["answer"],
                        "needle": entry["needle"],
                        "num_needles": len(inserted_meta),
                        "distractor_count": max(len(inserted_meta) - 1, 0),
                        "insert_char_pos": insert_pos,
                        "target_needle_id": entry["id"],
                        "inserted_needles": [meta["text"] for meta in inserted_meta],
                    }
                )

    print("V2 NIAH 变体分布：")
    for variant, count in sorted(variant_counter.items()):
        print(f"  {variant:18s}: {count}")
    return samples


def build_multihop_samples_v2(qa_path: str | Path, max_samples: int | None = None) -> list[dict]:
    qa_file = Path(qa_path)
    if not qa_file.exists():
        print(f"⚠️  未找到 V2 多跳文件: {qa_file}")
        return []

    with open(qa_file, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if max_samples is not None:
        raw = raw[:max_samples]

    samples = []
    for idx, item in enumerate(raw, start=1):
        samples.append(
            {
                "sample_id": f"v2-multihop-{idx:03d}",
                "experiment": "v2",
                "task": "multi_hop",
                "variant": "multi_hop",
                "needle_style": "multi_hop",
                "domain": item.get("domain", "general"),
                "difficulty": item.get("difficulty", "medium"),
                "context_length": len(item["context"]),
                "depth_pct": None,
                "context": item["context"],
                "question": item["question"],
                "answer": item["answer"],
                "num_needles": item.get("hops", 2),
                "distractor_count": None,
                "insert_char_pos": None,
                "target_needle_id": None,
                "inserted_needles": None,
                "hops": item.get("hops", 2),
                "answer_type": item.get("answer_type", "short_span"),
            }
        )
    return samples


def main(config_path: str = "configs/eval_config_v2.yaml"):
    config = yaml.safe_load(open(config_path, encoding="utf-8"))

    documents = load_documents(config["data"]["raw_dir"])
    if not documents:
        print("⚠️  data/raw/ 下没有可用文档，请先准备原始长文档。")
        return

    total_chars = sum(len(doc) for doc in documents)
    print(f"✅ 加载 {len(documents)} 篇原始文档，总字符数: {total_chars:,}")

    needle_bank = load_needle_bank(
        config["eval"]["niah"]["needle_bank_path"],
        variants=config["eval"]["niah"].get("variants"),
    )
    niah_samples = build_v2_niah_samples(
        documents=documents,
        context_lengths=config["eval"]["context_lengths"],
        depth_percentages=config["eval"]["depth_percentages"],
        needle_bank=needle_bank,
        samples_per_config=config["eval"]["niah"]["num_samples_per_config"],
        seed=config["eval"]["niah"].get("seed", 2026),
    )

    processed_dir = Path(config["data"]["processed_dir"])
    save_jsonl(niah_samples, processed_dir / "niah_dataset.jsonl")

    multihop_samples = build_multihop_samples_v2(
        config["eval"]["multi_hop"]["qa_path"],
        max_samples=config["eval"]["multi_hop"].get("num_samples"),
    )
    if multihop_samples:
        save_jsonl(multihop_samples, processed_dir / "multihop_dataset.jsonl")

    print(
        f"\n📊 V2 数据集生成完毕："
        f"\n   NIAH:     {len(niah_samples)} 条"
        f"\n   多跳推理: {len(multihop_samples)} 条"
        f"\n   输出目录: {processed_dir}"
    )


if __name__ == "__main__":
    main()

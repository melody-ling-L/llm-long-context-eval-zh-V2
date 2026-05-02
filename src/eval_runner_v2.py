"""V2 评测运行器。

相对 V1 的变化：
- 保留 sample_id / variant / domain / num_needles 等元数据
- 使用 sample_id 作为断点续跑主键，避免重复问题
- 原始结果写入 results/v2/raw/，不覆盖 V1
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv
from tqdm import tqdm

from src.eval_runner import _API_KEY_ENV, call_model, get_client

load_dotenv()

PASS_THROUGH_FIELDS = [
    "sample_id",
    "experiment",
    "variant",
    "needle_style",
    "domain",
    "difficulty",
    "answer_type",
    "num_needles",
    "distractor_count",
    "target_needle_id",
    "hops",
]


def _resume_key(model_key: str, sample: dict) -> tuple:
    if sample.get("sample_id"):
        return model_key, sample["sample_id"]
    return (
        model_key,
        sample["question"],
        str(sample.get("context_length")),
        str(sample.get("depth_pct")),
        sample.get("variant", "niah"),
    )


def _existing_resume_counts(existing_df: pd.DataFrame) -> Counter:
    if "sample_id" in existing_df.columns:
        return Counter(zip(existing_df["model"], existing_df["sample_id"]))
    return Counter(
        zip(
            existing_df["model"],
            existing_df["question"],
            existing_df["context_length"].astype(str),
            existing_df["depth_pct"].astype(str),
            existing_df.get("variant", pd.Series(["niah"] * len(existing_df))).astype(str),
        )
    )


def run_eval_v2(
    dataset_path: str,
    model_keys: list[str],
    config: dict,
    output_dir: str,
    max_samples: int | None = None,
    resume: bool = True,
) -> pd.DataFrame:
    samples = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    if max_samples:
        samples = samples[:max_samples]

    print(f"📂 加载 {len(samples)} 条 V2 样本，来自: {dataset_path}")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(output_dir) / "raw_results.csv"
    existing_counts = Counter()
    if resume and out_path.exists():
        existing_df = pd.read_csv(out_path)
        existing_counts = _existing_resume_counts(existing_df)
        print(f"   已有 {len(existing_df)} 条结果，启用 V2 断点续跑")

    rows = []
    for model_key in model_keys:
        if not os.getenv(_API_KEY_ENV.get(model_key, ""), ""):
            print(f"⚠️  {model_key} 未配置 API Key，跳过")
            continue

        client, model_name = get_client(model_key, config)
        rpm_limit = config["models"][model_key].get("rpm_limit", 30)
        request_interval = 60.0 / rpm_limit
        print(f"\n🚀 [V2:{model_key}] {model_name} — RPM 限制: {rpm_limit}")

        for sample in tqdm(samples, desc=f"v2-{model_key}", unit="req"):
            key = _resume_key(model_key, sample)
            if existing_counts[key] > 0:
                existing_counts[key] -= 1
                continue

            response, prompt_tokens, completion_tokens, cached_tokens, latency = call_model(
                client,
                model_name,
                sample["context"],
                sample["question"],
                max_tokens=config["models"][model_key].get("max_tokens", 256),
            )

            row = {
                "model": model_key,
                "task": sample.get("task", "niah"),
                "context_length": sample.get("context_length"),
                "depth_pct": sample.get("depth_pct"),
                "question": sample["question"],
                "expected_answer": sample["answer"],
                "model_response": response,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cached_tokens": cached_tokens,
                "tokens_used": prompt_tokens + completion_tokens,
                "latency_s": round(latency, 2),
                "response_chars": len(response),
                "question_chars": len(sample["question"]),
                "context_chars": len(sample["context"]),
            }
            for field in PASS_THROUGH_FIELDS:
                if field in sample:
                    row[field] = sample[field]
            if "inserted_needles" in sample and sample["inserted_needles"] is not None:
                row["inserted_needles"] = json.dumps(sample["inserted_needles"], ensure_ascii=False)
            rows.append(row)
            time.sleep(request_interval)

    if not rows:
        print("ℹ️  无新结果（所有样本已处理或无可用 API Key）")
        return pd.read_csv(out_path) if out_path.exists() else pd.DataFrame()

    new_df = pd.DataFrame(rows)
    if resume and out_path.exists():
        old_df = pd.read_csv(out_path)
        final_df = pd.concat([old_df, new_df], ignore_index=True)
    else:
        final_df = new_df

    final_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n✅ V2 结果保存至: {out_path}（共 {len(final_df)} 条）")
    return final_df


def main(config_path: str = "configs/eval_config_v2.yaml"):
    config = yaml.safe_load(open(config_path, encoding="utf-8"))
    run_eval_v2(
        dataset_path=f"{config['data']['processed_dir']}/niah_dataset.jsonl",
        model_keys=["deepseek"],
        config=config,
        output_dir=config["results"]["raw_dir"],
        max_samples=None,
        resume=True,
    )


if __name__ == "__main__":
    main()

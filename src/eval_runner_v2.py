"""V2 评测运行器。

相对 V1 的变化：
- 保留 sample_id / variant / domain / num_needles 等元数据
- 使用 sample_id 作为断点续跑主键，避免重复问题
- 原始结果写入 results/v2/raw/，不覆盖 V1
- 每条结果写入 error 列，记录 API 失败原因（空字符串表示成功）
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

from src.eval_runner import call_model, get_api_key, get_client
from src.metrics_v2 import is_content_filter_failure, is_infra_api_failure

load_dotenv()

PASS_THROUGH_FIELDS = [
    "sample_id",
    "experiment",
    "variant",
    "needle_style",
    "domain",
    "difficulty",
    "answer_type",
    "scoring_mode",
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


def _row_failed(row: pd.Series) -> bool:
    if is_content_filter_failure(row):
        return False
    error = row.get("error")
    if pd.notna(error) and str(error).strip():
        return True
    return (
        float(row.get("prompt_tokens", 0) or 0) == 0
        and float(row.get("latency_s", 0) or 0) == 0
        and not str(row.get("model_response", "") or "").strip()
    )


def _row_skip_resume(row: pd.Series) -> bool:
    """成功或 content_filter 均不再续跑。"""
    if is_content_filter_failure(row):
        return True
    return not _row_failed(row)


def _existing_resume_counts(existing_df: pd.DataFrame) -> Counter:
    skip_df = existing_df[existing_df.apply(_row_skip_resume, axis=1)]
    if "sample_id" in skip_df.columns:
        return Counter(zip(skip_df["model"], skip_df["sample_id"]))
    return Counter(
        zip(
            skip_df["model"],
            skip_df["question"],
            skip_df["context_length"].astype(str),
            skip_df["depth_pct"].astype(str),
            skip_df.get("variant", pd.Series(["niah"] * len(skip_df))).astype(str),
        )
    )


def _flush_row(out_path: Path, row: dict, model_key: str, sample: dict) -> None:
    """逐条落盘；若同 key 存在失败行则覆盖，避免断点续跑重复计费。"""
    new_df = pd.DataFrame([row])
    if not out_path.exists():
        new_df.to_csv(out_path, index=False, encoding="utf-8-sig")
        return

    old_df = pd.read_csv(out_path)
    if "sample_id" in old_df.columns and sample.get("sample_id"):
        dup_mask = (old_df["model"] == model_key) & (old_df["sample_id"] == sample["sample_id"])
    else:
        variant = sample.get("variant", "niah")
        dup_mask = (
            (old_df["model"] == model_key)
            & (old_df["question"] == sample["question"])
            & (old_df["context_length"].astype(str) == str(sample.get("context_length")))
            & (old_df["depth_pct"].astype(str) == str(sample.get("depth_pct")))
            & (old_df.get("variant", pd.Series(["niah"] * len(old_df))).astype(str) == str(variant))
        )
    failed_dup = dup_mask & old_df.apply(
        lambda row: _row_failed(row) and not is_content_filter_failure(row), axis=1
    )
    old_df = old_df[~failed_dup]
    pd.concat([old_df, new_df], ignore_index=True).to_csv(
        out_path, index=False, encoding="utf-8-sig"
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
        if not get_api_key(model_key, config["models"][model_key]):
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

            response, prompt_tokens, completion_tokens, cached_tokens, latency, error = call_model(
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
                "error": error,
                "response_chars": len(response),
                "question_chars": len(sample["question"]),
                "context_chars": len(sample["context"]),
            }
            for field in PASS_THROUGH_FIELDS:
                if field in sample:
                    row[field] = sample[field]
            if "inserted_needles" in sample and sample["inserted_needles"] is not None:
                row["inserted_needles"] = json.dumps(sample["inserted_needles"], ensure_ascii=False)
            if sample.get("answer_aliases"):
                row["answer_aliases"] = json.dumps(sample["answer_aliases"], ensure_ascii=False)
            rows.append(row)
            _flush_row(out_path, row, model_key, sample)
            time.sleep(request_interval)

    if not rows:
        print("ℹ️  无新结果（所有样本已处理或无可用 API Key）")
        return pd.read_csv(out_path) if out_path.exists() else pd.DataFrame()

    final_df = pd.read_csv(out_path)
    print(f"\n✅ V2 结果保存至: {out_path}（共 {len(final_df)} 条，本次新增 {len(rows)} 条）")
    return final_df


def run_eval_bundle_v2(
    config: dict,
    model_keys: list[str],
    output_dir: str,
    resume: bool = True,
) -> pd.DataFrame:
    dataset_specs = [
        (
            "niah",
            f"{config['data']['processed_dir']}/niah_dataset.jsonl",
            config.get("eval", {}).get("niah", {}).get("num_samples"),
        ),
        (
            "multi_hop",
            f"{config['data']['processed_dir']}/multihop_dataset.jsonl",
            config.get("eval", {}).get("multi_hop", {}).get("num_samples"),
        ),
    ]

    latest_df = pd.DataFrame()
    for task_name, dataset_path, max_samples in dataset_specs:
        if not Path(dataset_path).exists():
            print(f"ℹ️  V2 {task_name} 数据集不存在，跳过: {dataset_path}")
            continue

        print(f"\n{'=' * 72}\n开始执行 V2 任务: {task_name}\n{'=' * 72}")
        latest_df = run_eval_v2(
            dataset_path=dataset_path,
            model_keys=model_keys,
            config=config,
            output_dir=output_dir,
            max_samples=max_samples,
            resume=resume,
        )
    return latest_df


def main(config_path: str = "configs/eval_config_v2.yaml"):
    config = yaml.safe_load(open(config_path, encoding="utf-8"))
    run_eval_bundle_v2(
        config=config,
        model_keys=["deepseek"],
        output_dir=config["results"]["raw_dir"],
        resume=True,
    )


if __name__ == "__main__":
    main()

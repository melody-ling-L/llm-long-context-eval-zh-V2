"""
评测运行器

功能：
- 统一调用 DeepSeek / Kimi / Qwen-Long API
- 限速控制（避免触发 RPM 限制）
- 结果存储为 results/raw/raw_results.csv

用法：
    python src/eval_runner.py
"""

import json
import os
import time
from collections import Counter
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

load_dotenv()

# ──────────────────────────────────────────────
# Prompt 模板
# ──────────────────────────────────────────────

SYSTEM_PROMPT = (
    "你是一个精准的信息提取助手。"
    "请根据用户提供的文档内容回答问题，答案应简洁准确，直接给出答案，不要解释推理过程。"
)

USER_PROMPT_TEMPLATE = """\
请仔细阅读以下文档，然后回答问题。

<document>
{context}
</document>

问题：{question}

请直接给出答案（一句话或一个短语即可，不需要解释）。"""


# ──────────────────────────────────────────────
# API Key 映射
# ──────────────────────────────────────────────

_API_KEY_ENV = {
    "deepseek": "DEEPSEEK_API_KEY",
    "kimi": "MOONSHOT_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
}


def get_client(model_key: str, config: dict) -> tuple:
    """返回 (OpenAI client, model_name)"""
    model_cfg = config["models"][model_key]
    api_key = os.getenv(_API_KEY_ENV[model_key], "")
    if not api_key:
        raise ValueError(
            f"未找到 {_API_KEY_ENV[model_key]}，请在 .env 文件中配置。"
        )
    client = OpenAI(api_key=api_key, base_url=model_cfg["api_base"])
    return client, model_cfg["model_name"]


# ──────────────────────────────────────────────
# 单次 API 调用
# ──────────────────────────────────────────────

def call_model(
    client: OpenAI,
    model_name: str,
    context: str,
    question: str,
    max_tokens: int = 256,
    retries: int = 3,
    retry_wait: float = 5.0,
) -> tuple:
    """
    调用模型并返回 (response_text, total_tokens, latency_s)。
    失败时最多重试 retries 次。
    """
    prompt = USER_PROMPT_TEMPLATE.format(context=context, question=question)

    for attempt in range(retries):
        try:
            t0 = time.time()
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.0,
            )
            elapsed = time.time() - t0
            text = response.choices[0].message.content.strip()
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            cached_tokens = getattr(usage, "prompt_cache_hit_tokens", 0) or 0
            return text, prompt_tokens, completion_tokens, cached_tokens, elapsed

        except Exception as e:
            print(f"  ⚠️  API 调用失败（尝试 {attempt + 1}/{retries}）: {e}")
            if attempt < retries - 1:
                time.sleep(retry_wait)

    return "", 0, 0, 0, 0.0


# ──────────────────────────────────────────────
# 批量评测
# ──────────────────────────────────────────────

def run_eval(
    dataset_path: str,
    model_keys: list,
    config: dict,
    output_dir: str = "results/raw",
    max_samples: int = None,
    resume: bool = True,
) -> pd.DataFrame:
    """
    对 dataset_path 中的样本逐条调用 model_keys 中的模型，保存结果 CSV。

    Args:
        dataset_path:  .jsonl 文件路径
        model_keys:    模型列表，如 ["deepseek", "kimi"]
        config:        eval_config.yaml 解析结果
        output_dir:    结果保存目录
        max_samples:   调试时限制样本数
        resume:        是否跳过已存在的结果行（断点续跑）
    """
    # 加载数据集
    samples = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    if max_samples:
        samples = samples[:max_samples]
    print(f"📂 加载 {len(samples)} 条样本，来自: {dataset_path}")

    # 断点续跑：加载已有结果
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(output_dir) / "raw_results.csv"
    existing_counts = Counter()
    if resume and out_path.exists():
        existing_df = pd.read_csv(out_path)
        existing_counts = Counter(zip(
            existing_df["model"],
            existing_df["question"],
            existing_df["context_length"].astype(str),
            existing_df["depth_pct"].astype(str),
        ))
        print(f"   已有 {len(existing_df)} 条结果，启用断点续跑")

    all_results = []

    for model_key in model_keys:
        if not os.getenv(_API_KEY_ENV.get(model_key, ""), ""):
            print(f"⚠️  {model_key} 未配置 API Key，跳过")
            continue

        client, model_name = get_client(model_key, config)
        rpm_limit = config["models"][model_key].get("rpm_limit", 30)
        request_interval = 60.0 / rpm_limit  # 最小间隔秒数

        print(f"\n🚀 [{model_key}] {model_name} — RPM 限制: {rpm_limit}")

        for sample in tqdm(samples, desc=f"{model_key}", unit="req"):
            key = (
                model_key,
                sample["question"],
                str(sample.get("context_length")),
                str(sample.get("depth_pct")),
            )
            if existing_counts[key] > 0:
                existing_counts[key] -= 1
                continue  # 跳过已计算的

            response, prompt_tokens, completion_tokens, cached_tokens, latency = call_model(
                client,
                model_name,
                sample["context"],
                sample["question"],
                max_tokens=config["models"][model_key].get("max_tokens", 256),
            )

            all_results.append(
                {
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
                }
            )

            time.sleep(request_interval)

    if not all_results:
        print("ℹ️  无新结果（所有样本已处理或无可用 API Key）")
        return pd.read_csv(out_path) if out_path.exists() else pd.DataFrame()

    new_df = pd.DataFrame(all_results)

    # 合并断点续跑数据
    if resume and out_path.exists():
        old_df = pd.read_csv(out_path)
        final_df = pd.concat([old_df, new_df], ignore_index=True)
    else:
        final_df = new_df

    final_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n✅ 结果保存至: {out_path}（共 {len(final_df)} 条）")
    return final_df


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────

def main():
    config = yaml.safe_load(open("configs/eval_config.yaml", encoding="utf-8"))

    # 优先跑 DeepSeek（便宜），确认流程后再加其他模型
    model_keys = ["deepseek"]

    run_eval(
        dataset_path="data/processed/niah_dataset.jsonl",
        model_keys=model_keys,
        config=config,
        output_dir=config["results"]["raw_dir"],
        max_samples=None,
        resume=True,
    )


if __name__ == "__main__":
    main()

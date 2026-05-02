"""V2 指标模块。

相对 V1 的变化：
- 增加回答长度、输出 token、单条样本成本等效率指标
- 提供 Wilson 置信区间，帮助比较 16K / 32K 波动是否稳定
- 返回 per-model / per-variant 聚合表，便于 notebook 直接展示
"""

from __future__ import annotations

from math import sqrt

import pandas as pd

from src.metrics import _PRICE_TABLE, contains_match, exact_match


def score_results_v2(df: pd.DataFrame) -> pd.DataFrame:
    scored = df.copy()
    scored["em_score"] = scored.apply(
        lambda row: exact_match(str(row["model_response"]), str(row["expected_answer"])),
        axis=1,
    )
    scored["contains_score"] = scored.apply(
        lambda row: contains_match(str(row["model_response"]), str(row["expected_answer"])),
        axis=1,
    )

    scored["response_chars"] = scored["model_response"].fillna("").astype(str).str.len()
    scored["expected_answer_chars"] = scored["expected_answer"].fillna("").astype(str).str.len()
    scored["completion_tokens"] = scored.get("completion_tokens", pd.Series([0] * len(scored))).fillna(0)
    scored["prompt_tokens"] = scored.get("prompt_tokens", pd.Series([0] * len(scored))).fillna(0)
    scored["cached_tokens"] = scored.get("cached_tokens", pd.Series([0] * len(scored))).fillna(0)
    scored["row_cost_cny"] = scored.apply(_row_cost_cny, axis=1)
    scored["contains_per_1k_output_tokens"] = scored.apply(
        lambda row: row["contains_score"] / max(row["completion_tokens"], 1) * 1000,
        axis=1,
    )
    scored["contains_per_cny"] = scored.apply(
        lambda row: row["contains_score"] / max(row["row_cost_cny"], 1e-9),
        axis=1,
    )
    return scored


def _row_cost_cny(row: pd.Series) -> float:
    prompt_price, completion_price, cached_price = _PRICE_TABLE.get(row["model"], (5.0, 5.0, 5.0))
    prompt_tokens = float(row.get("prompt_tokens", 0) or 0)
    completion_tokens = float(row.get("completion_tokens", 0) or 0)
    cached_tokens = float(row.get("cached_tokens", 0) or 0)
    non_cached_prompt = max(prompt_tokens - cached_tokens, 0)
    return round(
        (non_cached_prompt * prompt_price + completion_tokens * completion_price + cached_tokens * cached_price) / 1e6,
        6,
    )


def wilson_interval(successes: float, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    phat = successes / total
    denominator = 1 + z**2 / total
    center = (phat + z**2 / (2 * total)) / denominator
    margin = z * sqrt((phat * (1 - phat) + z**2 / (4 * total)) / total) / denominator
    return center - margin, center + margin


def summarize_v2(df: pd.DataFrame, group_cols: list[str] | None = None) -> pd.DataFrame:
    if group_cols is None:
        group_cols = ["model"]

    records = []
    for key, sub in df.groupby(group_cols, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        record = dict(zip(group_cols, key))
        contains_hits = float(sub["contains_score"].sum())
        em_hits = float(sub["em_score"].sum())
        n = int(len(sub))
        ci_low, ci_high = wilson_interval(contains_hits, n)
        record.update(
            {
                "n": n,
                "em_pct": round(sub["em_score"].mean() * 100, 1),
                "contains_pct": round(sub["contains_score"].mean() * 100, 1),
                "contains_ci_low_pct": round(ci_low * 100, 1),
                "contains_ci_high_pct": round(ci_high * 100, 1),
                "avg_latency_s": round(sub["latency_s"].mean(), 2) if "latency_s" in sub.columns else None,
                "avg_response_chars": round(sub["response_chars"].mean(), 1),
                "avg_completion_tokens": round(sub["completion_tokens"].mean(), 1),
                "total_cost_cny": round(sub["row_cost_cny"].sum(), 4),
                "cost_per_contains_hit_cny": round(sub["row_cost_cny"].sum() / max(contains_hits, 1), 4),
                "cost_per_em_hit_cny": round(sub["row_cost_cny"].sum() / max(em_hits, 1), 4),
                "contains_per_1k_output_tokens": round(sub["contains_per_1k_output_tokens"].mean(), 2),
            }
        )
        records.append(record)
    return pd.DataFrame(records)


def summarize_variant_matrix(df: pd.DataFrame) -> pd.DataFrame:
    if "variant" not in df.columns:
        return pd.DataFrame()
    return summarize_v2(df, group_cols=["model", "variant"])


def print_v2_summary(df: pd.DataFrame):
    summary = summarize_v2(df)
    print("\n" + "=" * 72)
    print("                      V2 评测结果摘要")
    print("=" * 72)
    cols = [
        "model",
        "n",
        "em_pct",
        "contains_pct",
        "contains_ci_low_pct",
        "contains_ci_high_pct",
        "avg_latency_s",
        "avg_response_chars",
        "avg_completion_tokens",
        "cost_per_contains_hit_cny",
    ]
    print(summary[cols].to_string(index=False))
    if "variant" in df.columns:
        print("\n按变体拆分：")
        print(summarize_variant_matrix(df)[["model", "variant", "n", "contains_pct", "contains_ci_low_pct", "contains_ci_high_pct"]].to_string(index=False))
    print("=" * 72 + "\n")

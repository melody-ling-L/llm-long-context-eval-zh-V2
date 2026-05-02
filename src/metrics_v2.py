"""V2 指标模块。

相对 V1 的变化：
- 增加回答长度、输出 token、单条样本成本等效率指标
- 提供 Wilson 置信区间，帮助比较 16K / 32K 波动是否稳定
- 返回 per-model / per-variant 聚合表，便于 notebook 直接展示
"""

from __future__ import annotations

import re
from math import sqrt

import pandas as pd

from src.metrics import _PRICE_TABLE, contains_match, exact_match, normalize_answer


_NUMBER_LIKE_PATTERN = re.compile(
    r"(?:\d+(?:\.\d+)?%?)|(?:\d{1,2}:\d{2})|(?:\d{4}年\d{1,2}月\d{1,2}日)|(?:\d+(?:\.\d+)?(?:亿元|万元|元|件|张|天|人|小时))"
)


def _safe_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _looks_empty_answer(value) -> bool:
    normalized = normalize_answer(_safe_text(value))
    return normalized in {"", "nan", "none"}


def _has_number_like_signal(value) -> bool:
    return bool(_NUMBER_LIKE_PATTERN.search(_safe_text(value)))


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


def classify_badcase_taxonomy(row: pd.Series) -> str:
    response = _safe_text(row.get("model_response", ""))
    expected = _safe_text(row.get("expected_answer", ""))
    task = str(row.get("task", "niah") or "niah")
    variant = str(row.get("variant", "") or "")

    contains = int(row.get("contains_score", contains_match(response, expected)))
    em = int(row.get("em_score", exact_match(response, expected)))

    if contains == 1 and em == 0:
        return "输出冗余但包含正确答案"

    if task == "multi_hop":
        if _looks_empty_answer(response):
            return "多跳推理未作答"
        if _has_number_like_signal(response):
            return "多跳推理链条或计算失败"
        return "多跳推理答案偏移"

    if variant == "multi_key":
        return "多 key 条件下定位失败"
    if variant == "numeric_confusable":
        return "被相似数字干扰"

    depth_pct = row.get("depth_pct")
    if pd.notna(depth_pct):
        try:
            depth_value = float(depth_pct)
        except (TypeError, ValueError):
            depth_value = None
        if depth_value is not None and 25 <= depth_value <= 75 and _looks_empty_answer(response):
            return "深层位置召回失败"

    if not _looks_empty_answer(response):
        return "找到了附近信息但抽错目标值"
    return "未作答或信息未命中"


def attach_badcase_taxonomy(df: pd.DataFrame) -> pd.DataFrame:
    annotated = df.copy()
    if annotated.empty:
        annotated["badcase_taxonomy"] = pd.Series(dtype="object")
        annotated["is_badcase"] = pd.Series(dtype="int")
        return annotated

    annotated["badcase_taxonomy"] = annotated.apply(classify_badcase_taxonomy, axis=1)
    annotated["is_badcase"] = ((annotated["contains_score"] == 0) | (annotated["em_score"] == 0)).astype(int)
    return annotated


def summarize_badcase_taxonomy(
    df: pd.DataFrame,
    group_cols: list[str] | None = None,
    only_badcases: bool = True,
) -> pd.DataFrame:
    if group_cols is None:
        group_cols = ["model", "badcase_taxonomy"]

    annotated = attach_badcase_taxonomy(df)
    if only_badcases:
        annotated = annotated[annotated["is_badcase"] == 1].copy()
    if annotated.empty:
        return pd.DataFrame(columns=[*group_cols, "n", "share_pct", "contains_failures", "em_only_misses"])

    total = max(len(annotated), 1)
    summary = (
        annotated.groupby(group_cols, dropna=False)
        .agg(
            n=("badcase_taxonomy", "size"),
            contains_failures=("contains_score", lambda s: int((s == 0).sum())),
            em_only_misses=("contains_score", lambda s: int((s == 1).sum())),
        )
        .reset_index()
    )
    summary["share_pct"] = (summary["n"] / total * 100).round(1)
    return summary.sort_values(["n", *group_cols], ascending=[False, *([True] * len(group_cols))])


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
